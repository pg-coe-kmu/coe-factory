"""
BC2 · Ablage des Ergebnisses — Lauf, Konzepte und Potenziale in Schema ``bc2``.

Bis #290 lebte ein Lauf nur, solange er angesehen wurde: die ``Laufquelle``
rechnete ihn bei jedem Aufruf neu, und die Gate-1-Entscheidung hing im
Arbeitsspeicher daneben. Hier bekommt er einen Ort (ADR-008 · BC2).

Drei Dinge liegen hier:

- ``Ergebnisbuch`` — das Protokoll der Ablage, mit ``PostgresErgebnisbuch``
  gegen die gemeinsame Datenbank und ``SpeicherErgebnisbuch`` für die Tests.
  Dieselbe Naht wie in ``eingang.py``.
- ``AblegendeLaufquelle`` — umhüllt **irgendeine** ``Laufquelle``: rechnet
  einmal, legt ab und zeigt danach nur noch das Abgelegte. Die innere Quelle
  ist heute der Messsatz; der Bewertungsschritt (#288) tauscht sie aus, ohne
  dass hier etwas nachzuziehen ist.
- Die Abbildung zwischen ``Laufansicht`` und den abgelegten Dokumenten.
- Die Kette über Pakete hinweg (ADR-009 · BC2, #295): ``kandidaten`` liest,
  was schon geliefert ist und das Paket berührt, ``rechnen`` gibt es der
  inneren Quelle mit und prüft ihr Urteil nach, bevor es abgelegt wird.

**Was die Datenbank garantiert und was nicht.** Fassungsvergabe, höchstens ein
offener Lauf je Paket und die Unveränderlichkeit des Ergebnisses stehen in
``migration_bc2.2_lauf.sql``. Der Speicher-Doppelgänger ahmt sie nach — wer
hier einen grünen Test sieht, hat sie noch nicht bewiesen; das tut
``tests/test_vertrag_postgres.py``.

**Was die Dokumente heute sind.** Vertragsform v3, aber nicht vollständig: die
Texte eines Potenzials (``beschreibung``, ``user_story`` …) entstehen beim LLM
und fehlen, solange die innere Quelle ein Messsatz ist. Abgelegt wird, was die
Rechnung liefert — ohne Platzhalter. Schema-gültig wird erst die Lieferung an
BC3, und die prüft ``tools/validate.py`` im PR (#253).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Protocol

from laeufe import LaufAngehalten, Laufansicht, Laufkopf, Laufquelle
from nachfolge import Kandidat, Nachfolge, pruefe_ausgaenge

__all__ = [
    "KetteUngueltig",
    "NachfolgerOffen",
    "AbgelegterLauf",
    "AblegendeLaufquelle",
    "Ergebnisbuch",
    "Laufbeleg",
    "NeulaufNichtErlaubt",
    "PostgresErgebnisbuch",
    "SpeicherErgebnisbuch",
]

#: Zustände von ``bc2.lauf.zustand``. ``offen`` und ``in_arbeit`` sind die
#: nicht abgeschlossenen — davon höchstens einer je Paket.
OFFEN = ("in_arbeit", "offen")


class NeulaufNichtErlaubt(Exception):
    """Eine neue Fassung ist nur nach ``rejected`` zulässig (ADR-008 · BC2, 2.1)."""


class NachfolgerOffen(Exception):
    """Der Lauf hat Vorgänger-Kandidaten und kann die Kette nicht tragen.

    Die Auflage aus ADR-009 · BC2 §4.3 überlebt den Bau der Verknüpfung (#295)
    an genau zwei Stellen — überall dort, wo sonst still ``[]`` läge und für
    BC3 „neues Potenzial“ hieße, sodass BC4 neben das bestehende Ticket ein
    zweites legte:

    - Die innere Quelle **beurteilt keine Kandidaten** (ein Messsatz kennt kein
      Modell).
    - Der Lauf kommt **ohne Ausgangslage** und damit als Vertrag 3.0, und 3.0
      hat keine Felder für die Kette (§2.7).
    """

    def __init__(self, paket_id: str, kandidaten: list[Kandidat], grund: str) -> None:
        pakete = sorted({k.paket_id for k in kandidaten})
        super().__init__(
            f"Paket {paket_id} beruehrt Teilprozesse, zu denen schon freigegebene "
            f"Potenziale vorliegen ({len(kandidaten)} aus {', '.join(pakete)}). {grund} "
            "Der Lauf bricht ab, statt die Kette still leer zu liefern (ADR-009 · BC2 §4.3)."
        )
        self.kandidaten = [asdict(k) for k in kandidaten]


class KetteUngueltig(LaufAngehalten):
    """Die Quelle hat die Kandidaten beurteilt, aber die Nachprüfung hält nicht.

    Der Wächter der Erkennung prüft dasselbe schon und fragt einmal nach; hier
    steht die zweite Prüfung vor dem Schreiben, damit keine Quelle eine Kette in
    Schema ``bc2`` legt, die ADR-009 · BC2 §2.3–§2.5 bricht.
    """


class LaufNichtInArbeit(Exception):
    """Das Ergebnis sollte in einen Lauf, der nicht mehr ``in_arbeit`` ist.

    Dann hat ein anderer Schreiber schneller abgelegt. Kein Fehler des Laufs,
    sondern der Beleg, dass die Zustandsbedingung gegriffen hat.
    """


@dataclass(frozen=True)
class Laufbeleg:
    """Was ``beginnen`` zurückgibt: welcher Lauf, welche Fassung, in welchem Zustand."""

    priorisierung_id: str
    company_id: str
    paket_id: str
    uebergeben_am: datetime
    fassung: int
    zustand: str


@dataclass(frozen=True)
class AbgelegterLauf:
    """Ein Lauf, wie er in ``bc2`` liegt."""

    beleg: Laufbeleg
    #: Priorisierung in Vertragsform, ohne ``gate1``. ``None`` solange nicht gerechnet.
    dokument: dict | None
    #: Die Konzeptdokumente, je Kernprozess eines.
    konzepte: list[dict] = field(default_factory=list)
    #: ``kp_id`` → Klartextname, soweit bekannt.
    kp_namen: dict[str, str] = field(default_factory=dict)
    warnung: str | None = None
    #: Gate-1-Zustand, wie die Datenbank ihn kennt; ``pending`` ohne Entscheidung.
    gate1_status: str = "pending"


class Ergebnisbuch(Protocol):
    """Was die ``AblegendeLaufquelle`` von ihrer Ablage braucht."""

    def letzter(self, paket_id: str) -> AbgelegterLauf | None:
        """Die jüngste Fassung zu diesem Paket, oder ``None``."""
        ...

    def beginnen(
        self, company_id: str, paket_id: str, uebergeben_am: datetime, *, neu: bool
    ) -> Laufbeleg:
        """Gibt den Lauf, in den jetzt gerechnet wird.

        ``neu=False``: der erste Lauf eines Pakets, oder der Neuversuch eines
        gescheiterten (dieselbe Fassung). Gibt es schon einen anderen, kommt
        der zurück — mit seinem Zustand, damit der Aufrufer nicht doppelt rechnet.

        ``neu=True``: die nächste Fassung, **nur** wenn die jüngste an Gate 1
        abgelehnt wurde. Sonst ``NeulaufNichtErlaubt``.
        """
        ...

    def ablegen(
        self,
        beleg: Laufbeleg,
        dokument: dict,
        konzepte: list[dict],
        *,
        kp_namen: dict[str, str] | None = None,
        warnung: str | None = None,
    ) -> None:
        """Lauf, Konzepte und Potenziale in **einer** Transaktion."""
        ...

    def fehler_melden(self, beleg: Laufbeleg, text: str) -> None:
        """Markiert den Lauf als gescheitert. Keine Fassung (ADR-008 · BC2, 2.1)."""
        ...

    def kandidaten(
        self, company_id: str, paket_id: str, teilprozess_ids: list[str]
    ) -> list[Kandidat]:
        """Die **geltenden** gelieferten Potenziale desselben Mandanten, die
        einen dieser Teilprozesse berühren (ADR-009 · BC2 §2.2).

        Geliefert heißt: aus einem ``approved``-Lauf eines **anderen** Pakets.
        Abgelehnte Fassungen zählen nicht, an Gate 1 herausgenommene Potenziale
        eines freigegebenen Laufs schon — sie stehen markiert in der gelieferten
        Datei. Geltend heißt: kein freigegebener Lauf hat es seither
        fortgeschrieben oder gestrichen.

        *Das ist die baubare Lesart von §2.2* („jeweils aus dem jüngsten
        ``approved``-Lauf, der diesen Teilprozess enthielt“): Schema ``bc2``
        kennt die Teilprozesse eines Pakets nicht, nur die seiner Potenziale.
        Und wörtlich genommen bekäme ein Potenzial, das ein späteres Paket über
        einen anderen Teilprozess schon fortgeschrieben hat, einen zweiten
        Nachfolger — das bräche §2.4.
        """
        ...

    def nachschlagen(self, company_id: str, potenzial_ids: list[str]) -> dict[str, dict]:
        """Was hinter gelieferten Kennungen steht: ``id → {titel, paket_id, kp_id}``.

        Für die Gate-1-Ansicht: der Vertrag nennt Vorgänger und Gestrichene nur
        mit Kennung, der Mensch muss sie wiedererkennen.
        """
        ...

    def erreichbar(self) -> bool:
        ...


# ----------------------------------------------------------------------------
# Abbildung Laufansicht ↔ Dokumente
# ----------------------------------------------------------------------------


def _iso(zeitpunkt: datetime) -> str:
    return zeitpunkt.isoformat()


def dokumente_aus_ansicht(
    ansicht: Laufansicht,
    beleg: Laufbeleg,
    *,
    vorige_konzepte: list[dict] | None = None,
    erzeugt_am: datetime | None = None,
) -> tuple[dict, list[dict]]:
    """Zerlegt eine gerechnete Ansicht in Priorisierung und Konzepte.

    **Hier entstehen die echten Kennungen.** ``laeufe.aus_lauf`` vergibt nur
    ableitbare Platzhalter (``<paket>-f<n>-<kp>``), weil es nicht weiß, ob
    ausgeliefert wird. Abgelegt wird mit ``priorisierung_id`` aus der Datenbank
    und einer neuen ``konzept_id`` je Fassung (ADR-007 · BC2, 2.5); die
    Verweise in ``eintraege`` und ``prozess_raenge`` werden umgeschrieben.

    ``ersetzt_konzept_id`` zeigt auf das Konzept **derselben** ``kp_id`` aus der
    vorigen Fassung desselben Pakets — und nur dorthin (ADR-008 · BC2, 2.1).
    """
    erzeugt_am = erzeugt_am or datetime.now(timezone.utc)
    vorher = {k["kontext"]["kp_id"]: k["konzept_id"] for k in (vorige_konzepte or [])}

    kp_ids = [r["kp_id"] for r in ansicht.prozess_raenge]
    neue_ids = {kp: str(uuid.uuid4()) for kp in kp_ids}
    # Wie ``Laufansicht.als_vertrag``: 3.1 nur, wenn die Quelle die
    # Ausgangslage trägt (#254). Ein Messsatz trägt sie nicht.
    v31 = bool(ansicht.ausgangslage)

    kopf = {
        "schema_version": "3.1" if v31 else "3.0",
        "company_id": beleg.company_id,
        "paket_id": beleg.paket_id,
        "uebergeben_am": _iso(beleg.uebergeben_am),
        "fassung": beleg.fassung,
        "erzeugt_am": _iso(erzeugt_am),
    }

    # Die Vertragskonzepte der Quelle, sofern sie welche trägt (Erkennung und
    # Bewertung, #288) — sonst nur die gerechneten Hälften. Ein Vertrags-
    # potenzial ist beides zusammen: die Rechnung (``modell/ausgabe.py``) und
    # das Urteil des LLM. Bei Gleichstand gilt das Vertragskonzept.
    aus_quelle = {k["kontext"]["kp_id"]: k for k in (ansicht.konzepte or [])}
    nachfolge = ansicht.nachfolge or Nachfolge()
    vorgaenger = nachfolge.vorgaenger()

    def _potenziale(kp: str) -> list[dict]:
        vertrag = {p["potenzial_id"]: p for p in aus_quelle.get(kp, {}).get("potenziale", [])}
        liste = [
            {**ansicht.potenziale[e["potenzial_id"]], **vertrag.get(e["potenzial_id"], {})}
            for e in ansicht.eintraege
            if e["kp_id"] == kp
        ]
        if v31:
            # Pflicht ab 3.1 (ADR-009 · BC2 §2.7). Gesetzt wird allein aus der
            # nachgeprüften ``nachfolge``, nie aus dem, was eine Quelle selbst in
            # ihre Konzepte schrieb: ``[]`` heißt für BC3 „neu“, und das ist nur
            # richtig, weil ``rechnen`` vorher jeden Kandidaten zugeordnet hat.
            for p in liste:
                alt = vorgaenger.get(p["potenzial_id"])
                p["ersetzt_potenzial_ids"] = [alt] if alt else []
        return liste

    konzepte = [
        {
            **aus_quelle.get(kp, {"kontext": {"kp_id": kp}}),
            "konzept_id": neue_ids[kp],
            "ersetzt_konzept_id": vorher.get(kp),
            **kopf,
            "potenziale": _potenziale(kp),
        }
        for kp in kp_ids
    ]

    dokument = {
        "priorisierung_id": beleg.priorisierung_id,
        **kopf,
        "score_formel": ansicht.score_formel,
        "konzept_ids": [neue_ids[kp] for kp in kp_ids],
        "eintraege": [{**e, "konzept_id": neue_ids[e["kp_id"]]} for e in ansicht.eintraege],
        "prozess_raenge": [
            {**r, "konzept_id": neue_ids[r["kp_id"]]} for r in ansicht.prozess_raenge
        ],
    }
    if v31:
        dokument["ausgangslage"] = ansicht.ausgangslage
        dokument["gestrichene_potenziale"] = nachfolge.gestrichen()
    return dokument, konzepte


def ansicht_aus_ablage(lauf: AbgelegterLauf) -> Laufansicht:
    """Baut die Ansicht aus den **abgelegten Dokumenten** — nie aus Spalten.

    Das ist die Umkehrung von ``dokumente_aus_ansicht``. Die Oberfläche zeigt
    damit genau das, was an BC3 ginge: hätte die Ablage etwas anders
    geschrieben, sähe der Mensch es hier und nicht erst in der Lieferung.
    """
    assert lauf.dokument is not None, "nur gerechnete Läufe haben eine Ansicht"
    dok = lauf.dokument
    potenziale = {
        p["potenzial_id"]: p for k in lauf.konzepte for p in k.get("potenziale", [])
    }
    b = lauf.beleg
    return Laufansicht(
        kopf=Laufkopf(
            paket_id=b.paket_id,
            company_id=b.company_id,
            uebergeben_am=b.uebergeben_am,
            fassung=b.fassung,
            anzahl_potenziale=len(dok["eintraege"]),
            kp_ids=tuple(r["kp_id"] for r in dok["prozess_raenge"]),
            gate1_status=lauf.gate1_status,
            warnung=lauf.warnung,
            # Die Paketliste liegt nicht in ``bc2``; zum Zeigen genügen die
            # berührten Teilprozesse.
            teilprozess_ids=tuple(sorted({
                t for e in dok["eintraege"] for t in e["betroffene_teilprozess_ids"]
            })),
        ),
        score_formel=dok["score_formel"],
        eintraege=dok["eintraege"],
        prozess_raenge=dok["prozess_raenge"],
        potenziale=potenziale,
        kp_namen=dict(lauf.kp_namen),
        ausgangslage=dok.get("ausgangslage"),
        # Die abgelegten Konzepte, damit ``als_vertrag`` — und damit die
        # Präsentation (#257) — dieselben Kennungen und Inhalte sieht wie die
        # Ablage, statt sie aus den Potenzialen neu zusammenzusetzen.
        konzepte=list(lauf.konzepte),
        gestrichene_potenziale=dok.get("gestrichene_potenziale"),
    )


def verwiesene_ids(ansicht: Laufansicht) -> list[str]:
    """Die gelieferten Kennungen, auf die ein Lauf zeigt: Vorgänger und Gestrichene."""
    ids = [
        alt
        for k in ansicht.konzepte or []
        for p in k.get("potenziale", [])
        for alt in p.get("ersetzt_potenzial_ids") or []
    ]
    ids += [g["potenzial_id"] for g in ansicht.gestrichene_potenziale or []]
    return sorted(set(ids))


def potenzialzeilen(dokument: dict, konzepte: list[dict]) -> list[dict]:
    """Die Projektion für ``bc2.potenzial`` — aus denselben Dokumenten.

    Rang, Gruppe und Score stehen in den ``eintraege`` der Priorisierung, die
    Zuordnung zum Konzept über ``konzept_id``. Eine Quelle für beides, damit
    Spalte und Dokument nicht auseinanderlaufen können.
    """
    kette = {
        p["potenzial_id"]: p.get("ersetzt_potenzial_ids")
        for k in konzepte
        for p in k.get("potenziale", [])
    }
    return [
        {
            "potenzial_id": e["potenzial_id"],
            "konzept_id": e["konzept_id"],
            "kp_id": e["kp_id"],
            "teilprozess_ids": list(e["betroffene_teilprozess_ids"]),
            "score": e.get("score"),
            "potenzialrang": e.get("potenzialrang"),
            "prioritaetsgruppe": e.get("prioritaetsgruppe"),
            # NULL bei 3.0 (das Feld gibt es dort nicht), ``{}`` bei 3.1 ohne
            # Vorgänger. Beides kommt aus dem Dokument, nicht von hier.
            "ersetzt_potenzial_ids": kette.get(e["potenzial_id"]),
        }
        for e in dokument["eintraege"]
    ]


# ----------------------------------------------------------------------------
# Die umhüllende Laufquelle
# ----------------------------------------------------------------------------


class AblegendeLaufquelle:
    """Rechnet einmal, legt ab, zeigt danach das Abgelegte.

    **Wann gerechnet wird.** Heute beim ersten Ansehen — die innere Quelle ist
    ein Messsatz und kennt BC0s Anstoß nicht. Sobald der Bewertungsschritt
    angeschlossen ist (#288), gehört ``rechnen`` hinter den Eingang: dann liegt
    das Ergebnis schon, wenn der Mensch die Seite öffnet. An der Ablage ändert
    das nichts.
    """

    def __init__(self, innen: Laufquelle, buch: Ergebnisbuch) -> None:
        self._innen = innen
        self._buch = buch

    def _zeigen(self, abgelegt: AbgelegterLauf) -> Laufansicht:
        ansicht = ansicht_aus_ablage(abgelegt)
        ids = verwiesene_ids(ansicht)
        if not ids:
            return ansicht
        return replace(
            ansicht, verwiesen=self._buch.nachschlagen(abgelegt.beleg.company_id, ids)
        )

    def uebersicht(self, company_id: str | None = None) -> list[Laufkopf]:
        koepfe = []
        for kopf in self._innen.uebersicht(company_id):
            abgelegt = self._buch.letzter(kopf.paket_id)
            if abgelegt is not None and abgelegt.dokument is not None:
                koepfe.append(ansicht_aus_ablage(abgelegt).kopf)
            else:
                koepfe.append(kopf)
        return koepfe

    def ansicht(self, paket_id: str) -> Laufansicht | None:
        abgelegt = self._buch.letzter(paket_id)
        if abgelegt is not None and abgelegt.dokument is not None:
            return self._zeigen(abgelegt)
        return self.rechnen(paket_id, neu=False)

    def neu_rechnen(self, paket_id: str) -> Laufansicht | None:
        """Die nächste Fassung nach einem Reject (ADR-008 · BC2, 2.1)."""
        return self.rechnen(paket_id, neu=True)

    def rechnen(self, paket_id: str, *, neu: bool) -> Laufansicht | None:
        """Legt den Lauf an, liest die Kandidaten, rechnet, prüft, legt ab.

        **Erst anlegen, dann rechnen.** Die Kandidaten gehen in den Paketaufruf
        der Erkennung (ADR-009 · BC2 §2.5); sie müssen also feststehen, bevor
        gerechnet wird, und dafür reicht der Kopf aus der Übersicht. Ein Lauf,
        der schon gerechnet oder in Arbeit ist, kostet damit keinen
        Modellaufruf mehr, dessen Ergebnis dann verworfen würde.
        """
        k = next((x for x in self._innen.uebersicht() if x.paket_id == paket_id), None)
        if k is None:
            return None
        vorher = self._buch.letzter(paket_id)
        beleg = self._buch.beginnen(k.company_id, paket_id, k.uebergeben_am, neu=neu)

        if beleg.zustand == "in_arbeit":
            try:
                kandidaten = tuple(
                    self._buch.kandidaten(k.company_id, paket_id, list(k.teilprozess_ids))
                )
                gerechnet = self._innen.ansicht(paket_id, kandidaten)
                if gerechnet is None:
                    raise LaufAngehalten(f"Paket {paket_id} ist aus der Quelle verschwunden.")
                if kandidaten:
                    self._kette_pruefen(paket_id, gerechnet, kandidaten)
                dokument, konzepte = dokumente_aus_ansicht(
                    gerechnet,
                    beleg,
                    vorige_konzepte=vorher.konzepte
                    if vorher is not None and vorher.beleg.fassung < beleg.fassung
                    else None,
                )
                self._buch.ablegen(
                    beleg,
                    dokument,
                    konzepte,
                    kp_namen=gerechnet.kp_namen,
                    warnung=gerechnet.kopf.warnung,
                )
            except LaufNichtInArbeit:
                pass  # ein anderer Schreiber war schneller — sein Ergebnis gilt
            except Exception as e:
                self._buch.fehler_melden(beleg, f"{type(e).__name__}: {e}")
                raise

        abgelegt = self._buch.letzter(paket_id)
        if abgelegt is None or abgelegt.dokument is None:
            return None
        return self._zeigen(abgelegt)

    @staticmethod
    def _kette_pruefen(
        paket_id: str, gerechnet: Laufansicht, kandidaten: tuple[Kandidat, ...]
    ) -> None:
        """Hält den Lauf an, wenn er die Kette nicht tragen kann oder sie bricht."""
        if gerechnet.nachfolge is None:
            raise NachfolgerOffen(
                paket_id,
                list(kandidaten),
                "Die Quelle dieses Laufs beurteilt keine Vorgaenger (ein Messsatz kennt "
                "kein Modell).",
            )
        if not gerechnet.ausgangslage:
            raise NachfolgerOffen(
                paket_id,
                list(kandidaten),
                "Die Kette braucht Vertrag 3.1, und der Lauf traegt keine Ausgangslage "
                "(der echte Weg setzt noch keine Vertragskonzepte zusammen).",
            )
        neue = {
            e["potenzial_id"]: {
                "klasse": gerechnet.potenziale[e["potenzial_id"]]["automatisierungsgrad"]["klasse"],
                "kp_id": e["kp_id"],
            }
            for e in gerechnet.eintraege
        }
        paket = set(gerechnet.kopf.teilprozess_ids) | {
            t for e in gerechnet.eintraege for t in e["betroffene_teilprozess_ids"]
        }
        verstoesse = pruefe_ausgaenge(kandidaten, gerechnet.nachfolge.ausgaenge, neue, paket)
        if verstoesse:
            raise KetteUngueltig(
                f"Lauf {paket_id}: die Kette ueber Pakete haelt nicht — " + "; ".join(verstoesse)
            )


# ----------------------------------------------------------------------------
# Postgres
# ----------------------------------------------------------------------------

_SQL_LETZTER = """
SELECT l.priorisierung_id::text, l.company_id, l.paket_id, l.uebergeben_am,
       l.fassung, l.zustand, l.dokument, l.warnung,
       coalesce(g.status, 'pending') AS gate1_status
  FROM bc2.lauf l
  LEFT JOIN bc2.gate1 g USING (priorisierung_id)
 WHERE l.paket_id = %(paket_id)s
 ORDER BY l.fassung DESC
 LIMIT 1
"""

_SQL_KONZEPTE = """
SELECT dokument, kp_id, kp_name
  FROM bc2.konzept
 WHERE priorisierung_id = %(priorisierung_id)s
"""

# Die Fassung vergibt die Datenbank: höchste plus eins, abgesichert durch
# UNIQUE (paket_id, fassung) und den partiellen Index. Zwei gleichzeitige
# Schreiber berechnen dieselbe Nummer — einer gewinnt, der andere läuft auf.
_SQL_ANLEGEN = """
INSERT INTO bc2.lauf (company_id, paket_id, uebergeben_am, fassung)
SELECT %(company_id)s, %(paket_id)s, %(uebergeben_am)s,
       coalesce(max(fassung), 0) + 1
  FROM bc2.lauf
 WHERE paket_id = %(paket_id)s
RETURNING priorisierung_id::text, fassung
"""

_SQL_NEUVERSUCH = """
UPDATE bc2.lauf SET zustand = 'in_arbeit', fehler = NULL, begonnen_am = now()
 WHERE priorisierung_id = %(priorisierung_id)s AND zustand = 'fehler'
"""

_SQL_ERGEBNIS = """
UPDATE bc2.lauf
   SET dokument = %(dokument)s, zustand = 'offen', gerechnet_am = now(),
       warnung = %(warnung)s
 WHERE priorisierung_id = %(priorisierung_id)s AND zustand = 'in_arbeit'
"""

_SQL_KONZEPT = """
INSERT INTO bc2.konzept (konzept_id, priorisierung_id, company_id, paket_id, kp_id,
                         kp_name, ersetzt_konzept_id, dokument)
VALUES (%(konzept_id)s, %(priorisierung_id)s, %(company_id)s, %(paket_id)s, %(kp_id)s,
        %(kp_name)s, %(ersetzt_konzept_id)s, %(dokument)s)
"""

_SQL_POTENZIAL = """
INSERT INTO bc2.potenzial (priorisierung_id, potenzial_id, konzept_id, kp_id,
                           teilprozess_ids, score, potenzialrang, prioritaetsgruppe,
                           ersetzt_potenzial_ids)
VALUES (%(priorisierung_id)s, %(potenzial_id)s, %(konzept_id)s, %(kp_id)s,
        %(teilprozess_ids)s, %(score)s, %(potenzialrang)s, %(prioritaetsgruppe)s,
        %(ersetzt_potenzial_ids)s::text[])
"""

# ADR-009 · BC2 §2.2, in der Lesart aus ``Ergebnisbuch.kandidaten``: geliefert
# und nicht seither erledigt. ``&&`` ist die Überschneidung zweier Felder. Titel,
# Beschreibung und Klasse stehen nur im Konzeptdokument — ``bc2.potenzial`` ist
# eine Projektion zum Filtern, kein zweiter Ort für Inhalt (ADR-008 · BC2, 2.2).
_SQL_KANDIDATEN = """
WITH geliefert AS (
  SELECT l.priorisierung_id, l.paket_id, l.dokument
    FROM bc2.lauf  l
    JOIN bc2.gate1 g USING (priorisierung_id)
   WHERE g.status = 'approved'
     AND l.company_id = %(company_id)s
),
erledigt AS (
  SELECT unnest(p.ersetzt_potenzial_ids) AS potenzial_id
    FROM bc2.potenzial p
    JOIN geliefert USING (priorisierung_id)
  UNION
  SELECT s ->> 'potenzial_id'
    FROM geliefert,
         jsonb_array_elements(coalesce(dokument -> 'gestrichene_potenziale', '[]'::jsonb)) s
)
SELECT f.paket_id, p.potenzial_id, p.kp_id, p.teilprozess_ids,
       e ->> 'titel'                             AS titel,
       e ->> 'beschreibung'                      AS beschreibung,
       e -> 'automatisierungsgrad' ->> 'klasse'  AS klasse
  FROM bc2.potenzial p
  JOIN geliefert f USING (priorisierung_id)
  JOIN bc2.konzept k ON k.konzept_id = p.konzept_id
  CROSS JOIN LATERAL jsonb_array_elements(k.dokument -> 'potenziale') e
 WHERE e ->> 'potenzial_id' = p.potenzial_id
   AND f.paket_id <> %(paket_id)s
   AND p.teilprozess_ids && %(teilprozess_ids)s::text[]
   AND NOT EXISTS (SELECT 1 FROM erledigt d WHERE d.potenzial_id = p.potenzial_id)
 ORDER BY f.paket_id, p.potenzial_id
"""

_SQL_NACHSCHLAGEN = """
SELECT p.potenzial_id, l.paket_id, p.kp_id, e ->> 'titel' AS titel
  FROM bc2.potenzial p
  JOIN bc2.lauf  l USING (priorisierung_id)
  JOIN bc2.gate1 g USING (priorisierung_id)
  JOIN bc2.konzept k ON k.konzept_id = p.konzept_id
  CROSS JOIN LATERAL jsonb_array_elements(k.dokument -> 'potenziale') e
 WHERE g.status = 'approved'
   AND l.company_id = %(company_id)s
   AND p.potenzial_id = ANY(%(ids)s::text[])
   AND e ->> 'potenzial_id' = p.potenzial_id
"""

_SQL_FEHLER = """
UPDATE bc2.lauf SET zustand = 'fehler', fehler = %(text)s
 WHERE priorisierung_id = %(priorisierung_id)s AND zustand = 'in_arbeit'
"""


def _dsn(dsn: str | None) -> str:
    wert = dsn or (os.environ.get("DATABASE_URL") or "").strip()
    if not wert:
        raise RuntimeError(
            "DATABASE_URL ist nicht gesetzt. Die Zugangsdaten gehoeren "
            "ausschliesslich in eine Umgebungsvariable (ADR-003)."
        )
    return wert


class PostgresErgebnisbuch:
    """Ablage in Schema ``bc2``. Verbindet je Vorgang neu, wie ``PostgresEingangsbuch``."""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = _dsn(dsn)

    def _verbindung(self):
        import psycopg2

        return psycopg2.connect(self._dsn)

    @staticmethod
    def _beleg(z: dict) -> Laufbeleg:
        return Laufbeleg(
            priorisierung_id=z["priorisierung_id"],
            company_id=z["company_id"],
            paket_id=z["paket_id"],
            uebergeben_am=z["uebergeben_am"],
            fassung=z["fassung"],
            zustand=z["zustand"],
        )

    def letzter(self, paket_id: str) -> AbgelegterLauf | None:
        import psycopg2.extras

        with self._verbindung() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(_SQL_LETZTER, {"paket_id": paket_id})
            z = cur.fetchone()
            if z is None:
                return None
            cur.execute(_SQL_KONZEPTE, {"priorisierung_id": z["priorisierung_id"]})
            konzepte = cur.fetchall()
        reihe = {kp: i for i, kp in enumerate(
            (z["dokument"] or {}).get("konzept_ids", [])
        )}
        geordnet = sorted(
            konzepte, key=lambda k: reihe.get(k["dokument"]["konzept_id"], len(reihe))
        )
        return AbgelegterLauf(
            beleg=self._beleg(z),
            dokument=z["dokument"],
            konzepte=[k["dokument"] for k in geordnet],
            kp_namen={k["kp_id"]: k["kp_name"] for k in geordnet if k["kp_name"]},
            warnung=z["warnung"],
            gate1_status=z["gate1_status"],
        )

    def beginnen(
        self, company_id: str, paket_id: str, uebergeben_am: datetime, *, neu: bool
    ) -> Laufbeleg:
        import psycopg2
        import psycopg2.extras

        # Ein Neuversuch nach einem Wettlauf genügt: der Gewinner hat den
        # offenen Lauf angelegt, und der wird beim zweiten Lesen gefunden.
        for versuch in range(2):
            with self._verbindung() as conn, conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute(_SQL_LETZTER, {"paket_id": paket_id})
                z = cur.fetchone()
                entscheid = _beginnen_entscheiden(
                    None if z is None else (self._beleg(z), z["gate1_status"]), neu=neu
                )
                if isinstance(entscheid, Laufbeleg):
                    return entscheid
                if entscheid == "neuversuch":
                    cur.execute(_SQL_NEUVERSUCH, {"priorisierung_id": z["priorisierung_id"]})
                    if cur.rowcount == 1:
                        return replace(self._beleg(z), zustand="in_arbeit")
                    continue
                try:
                    cur.execute(
                        _SQL_ANLEGEN,
                        {"company_id": company_id, "paket_id": paket_id,
                         "uebergeben_am": uebergeben_am},
                    )
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    if versuch == 0:
                        continue
                    raise
                neu_z = cur.fetchone()
                return Laufbeleg(
                    priorisierung_id=neu_z["priorisierung_id"],
                    company_id=company_id,
                    paket_id=paket_id,
                    uebergeben_am=uebergeben_am,
                    fassung=neu_z["fassung"],
                    zustand="in_arbeit",
                )
        raise RuntimeError(f"Lauf fuer {paket_id} liess sich nicht beginnen.")

    def ablegen(
        self,
        beleg: Laufbeleg,
        dokument: dict,
        konzepte: list[dict],
        *,
        kp_namen: dict[str, str] | None = None,
        warnung: str | None = None,
    ) -> None:
        from psycopg2.extras import Json

        kp_namen = kp_namen or {}
        # Ein `with`-Block um die Verbindung ist **eine** Transaktion: commit
        # am Ende, rollback bei einer Ausnahme. Lauf, Konzepte und Potenziale
        # liegen danach ganz oder gar nicht.
        with self._verbindung() as conn, conn.cursor() as cur:
            cur.execute(
                _SQL_ERGEBNIS,
                {"priorisierung_id": beleg.priorisierung_id, "dokument": Json(dokument),
                 "warnung": warnung},
            )
            if cur.rowcount != 1:
                raise LaufNichtInArbeit(beleg.priorisierung_id)
            for k in konzepte:
                kp = k["kontext"]["kp_id"]
                cur.execute(
                    _SQL_KONZEPT,
                    {"konzept_id": k["konzept_id"], "priorisierung_id": beleg.priorisierung_id,
                     "company_id": beleg.company_id, "paket_id": beleg.paket_id,
                     "kp_id": kp, "kp_name": kp_namen.get(kp),
                     "ersetzt_konzept_id": k.get("ersetzt_konzept_id"), "dokument": Json(k)},
                )
            for p in potenzialzeilen(dokument, konzepte):
                cur.execute(_SQL_POTENZIAL, {"priorisierung_id": beleg.priorisierung_id, **p})

    def fehler_melden(self, beleg: Laufbeleg, text: str) -> None:
        with self._verbindung() as conn, conn.cursor() as cur:
            cur.execute(_SQL_FEHLER, {"priorisierung_id": beleg.priorisierung_id,
                                      "text": text[:2000]})

    def kandidaten(
        self, company_id: str, paket_id: str, teilprozess_ids: list[str]
    ) -> list[Kandidat]:
        import psycopg2.extras

        if not teilprozess_ids:
            return []
        with self._verbindung() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(_SQL_KANDIDATEN, {"company_id": company_id, "paket_id": paket_id,
                                          "teilprozess_ids": list(teilprozess_ids)})
            return [
                Kandidat(
                    potenzial_id=z["potenzial_id"],
                    paket_id=z["paket_id"],
                    kp_id=z["kp_id"],
                    titel=z["titel"] or "",
                    klasse=z["klasse"] or "",
                    teilprozess_ids=tuple(z["teilprozess_ids"]),
                    beschreibung=z["beschreibung"],
                )
                for z in cur.fetchall()
            ]

    def nachschlagen(self, company_id: str, potenzial_ids: list[str]) -> dict[str, dict]:
        import psycopg2.extras

        if not potenzial_ids:
            return {}
        with self._verbindung() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(_SQL_NACHSCHLAGEN, {"company_id": company_id,
                                            "ids": list(potenzial_ids)})
            return {
                z["potenzial_id"]: {"titel": z["titel"], "paket_id": z["paket_id"],
                                    "kp_id": z["kp_id"]}
                for z in cur.fetchall()
            }

    def erreichbar(self) -> bool:
        try:
            with self._verbindung() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1 FROM bc2.lauf LIMIT 1")
                return True
        except Exception:
            return False


def _beginnen_entscheiden(
    letzter: tuple[Laufbeleg, str] | None, *, neu: bool
) -> Laufbeleg | str:
    """Die Regel aus ADR-008 · BC2, 2.1 — einmal, für beide Umsetzungen.

    Gibt einen bestehenden Beleg zurück, oder ``"anlegen"`` bzw.
    ``"neuversuch"`` als Auftrag an die Ablage. Die **Durchsetzung** gegen
    gleichzeitige Schreiber leistet trotzdem die Datenbank; hier steht nur,
    was im ruhigen Fall zu tun ist.
    """
    if letzter is None:
        return "anlegen"
    beleg, gate1 = letzter
    if beleg.zustand == "fehler":
        return "neuversuch"
    if not neu:
        return beleg
    if beleg.zustand in OFFEN:
        raise NeulaufNichtErlaubt(
            f"Fassung {beleg.fassung} von {beleg.paket_id} ist noch offen — "
            "erst an Gate 1 entscheiden."
        )
    if gate1 == "approved":
        raise NeulaufNichtErlaubt(
            f"Fassung {beleg.fassung} von {beleg.paket_id} ist freigegeben. Nach der "
            "Freigabe gibt es keine neue Fassung; neue Daten kommen als neues Paket von BC0."
        )
    return "anlegen"


# ----------------------------------------------------------------------------
# Arbeitsspeicher (Tests)
# ----------------------------------------------------------------------------


@dataclass
class _Zeile:
    beleg: Laufbeleg
    dokument: dict | None = None
    konzepte: list[dict] = field(default_factory=list)
    kp_namen: dict[str, str] = field(default_factory=dict)
    warnung: str | None = None
    gate1_status: str = "pending"
    fehler: str | None = None


@dataclass
class SpeicherErgebnisbuch:
    """Doppelgänger. Ahmt Fassungsvergabe und Zustandsbedingungen nach.

    **Die Garantie gibt er nicht** — gegen zwei gleichzeitige Schreiber hilft
    hier nichts, in der Datenbank der partielle Index.
    """

    zeilen: dict[str, list[_Zeile]] = field(default_factory=dict)
    antwortet: bool = True

    def _pruefe(self) -> None:
        if not self.antwortet:
            raise RuntimeError("Ablage antwortet nicht (Testfall).")

    def _letzte(self, paket_id: str) -> _Zeile | None:
        reihe = self.zeilen.get(paket_id) or []
        return reihe[-1] if reihe else None

    def _finden(self, priorisierung_id: str) -> _Zeile:
        for reihe in self.zeilen.values():
            for z in reihe:
                if z.beleg.priorisierung_id == priorisierung_id:
                    return z
        raise KeyError(priorisierung_id)

    def letzter(self, paket_id: str) -> AbgelegterLauf | None:
        self._pruefe()
        z = self._letzte(paket_id)
        if z is None:
            return None
        return AbgelegterLauf(
            beleg=z.beleg, dokument=z.dokument, konzepte=list(z.konzepte),
            kp_namen=dict(z.kp_namen), warnung=z.warnung, gate1_status=z.gate1_status,
        )

    def beginnen(
        self, company_id: str, paket_id: str, uebergeben_am: datetime, *, neu: bool
    ) -> Laufbeleg:
        self._pruefe()
        z = self._letzte(paket_id)
        entscheid = _beginnen_entscheiden(
            None if z is None else (z.beleg, z.gate1_status), neu=neu
        )
        if isinstance(entscheid, Laufbeleg):
            return entscheid
        if entscheid == "neuversuch":
            assert z is not None
            z.beleg = replace(z.beleg, zustand="in_arbeit")
            z.fehler = None
            return z.beleg
        beleg = Laufbeleg(
            priorisierung_id=str(uuid.uuid4()),
            company_id=company_id,
            paket_id=paket_id,
            uebergeben_am=uebergeben_am,
            fassung=(z.beleg.fassung + 1) if z is not None else 1,
            zustand="in_arbeit",
        )
        self.zeilen.setdefault(paket_id, []).append(_Zeile(beleg=beleg))
        return beleg

    def ablegen(
        self,
        beleg: Laufbeleg,
        dokument: dict,
        konzepte: list[dict],
        *,
        kp_namen: dict[str, str] | None = None,
        warnung: str | None = None,
    ) -> None:
        self._pruefe()
        z = self._finden(beleg.priorisierung_id)
        if z.beleg.zustand != "in_arbeit":
            raise LaufNichtInArbeit(beleg.priorisierung_id)
        # Wie die Datenbank: die Projektion muss sich bilden lassen, sonst
        # liegt gar nichts — nicht der Lauf ohne seine Potenziale.
        potenzialzeilen(dokument, konzepte)
        z.dokument = dokument
        z.konzepte = list(konzepte)
        z.kp_namen = dict(kp_namen or {})
        z.warnung = warnung
        z.beleg = replace(z.beleg, zustand="offen")

    def fehler_melden(self, beleg: Laufbeleg, text: str) -> None:
        z = self._finden(beleg.priorisierung_id)
        if z.beleg.zustand == "in_arbeit":
            z.beleg = replace(z.beleg, zustand="fehler")
            z.fehler = text

    def _geliefert(self, company_id: str) -> list[_Zeile]:
        return [
            z
            for reihe in self.zeilen.values()
            for z in reihe
            if z.gate1_status == "approved" and z.beleg.company_id == company_id
        ]

    def kandidaten(
        self, company_id: str, paket_id: str, teilprozess_ids: list[str]
    ) -> list[Kandidat]:
        self._pruefe()
        gesucht = set(teilprozess_ids)
        geliefert = self._geliefert(company_id)
        erledigt = {
            alt
            for z in geliefert
            for k in z.konzepte
            for p in k.get("potenziale", [])
            for alt in p.get("ersetzt_potenzial_ids") or []
        } | {
            g["potenzial_id"]
            for z in geliefert
            for g in z.dokument.get("gestrichene_potenziale") or []
        }
        treffer = []
        for z in geliefert:
            if z.beleg.paket_id == paket_id:
                continue
            for k in z.konzepte:
                for p in k.get("potenziale", []):
                    tps = tuple(p["betroffene_teilprozess_ids"])
                    if p["potenzial_id"] in erledigt or not gesucht & set(tps):
                        continue
                    treffer.append(
                        Kandidat(
                            potenzial_id=p["potenzial_id"],
                            paket_id=z.beleg.paket_id,
                            kp_id=k["kontext"]["kp_id"],
                            titel=p.get("titel") or "",
                            klasse=p["automatisierungsgrad"]["klasse"],
                            teilprozess_ids=tps,
                            beschreibung=p.get("beschreibung"),
                        )
                    )
        return sorted(treffer, key=lambda t: (t.paket_id, t.potenzial_id))

    def nachschlagen(self, company_id: str, potenzial_ids: list[str]) -> dict[str, dict]:
        self._pruefe()
        gesucht = set(potenzial_ids)
        return {
            p["potenzial_id"]: {"titel": p.get("titel"), "paket_id": z.beleg.paket_id,
                                "kp_id": k["kontext"]["kp_id"]}
            for z in self._geliefert(company_id)
            for k in z.konzepte
            for p in k.get("potenziale", [])
            if p["potenzial_id"] in gesucht
        }

    def abschliessen(self, paket_id: str, fassung: int, status: str) -> None:
        """Was in Postgres ``PostgresGate1Buch.merken`` in derselben Transaktion tut."""
        for z in self.zeilen.get(paket_id, []):
            if z.beleg.fassung == fassung:
                z.gate1_status = status
                if status in ("approved", "rejected"):
                    z.beleg = replace(z.beleg, zustand="abgeschlossen")
                return

    def erreichbar(self) -> bool:
        return self.antwortet

