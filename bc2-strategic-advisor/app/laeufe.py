"""
BC2 · Läufe für die Oberfläche — die Naht zwischen Anzeige und Herkunft.

Die Oberfläche (#243) zeigt **einen Lauf**: seine Potenziale, in Rangfolge,
gegliedert nach Kernprozess. Woher die kommen, geht sie nichts an. Hier liegt
das Protokoll dazwischen.

**Zwei Quellen, eine Form.** Die Form ist der Vertrag v3.0 — die Oberfläche
zeigt, was an BC3 geht, und nicht eine eigene Sicht daneben. Das ist kein
Schönheitsargument: eine Oberfläche mit eigener Datenform behauptet früher oder
später etwas anderes als die Lieferung, und der Mensch gibt dann frei, was er
nicht gesehen hat.

- ``MesssatzLaufquelle`` rechnet einen Messsatz durch (siehe
  ``modell/laden.py``). **Das ist die Voreinstellung des Betriebs**, bis
  ``BC2_LAUFQUELLE=pakete`` den echten Weg einschaltet (#288, siehe
  ``app.laufquelle_aus_umgebung``) — und sie ist eine Behelfslösung.
  Ein Messsatz ist nicht auf ``stand_zum(uebergeben_am)`` gelesen, seine Zahlen
  sind darum nicht nachrechenbar — die Quelle reicht die Warnung
  der Datei bis in die Oberfläche durch, statt sie zu schlucken.
- ``SpeicherLaufquelle`` nimmt fertige Ansichten entgegen; die Tests benutzen
  sie.
- ``PaketLaufquelle`` ist der **echte Weg** (#288): Paket lesen auf
  ``stand_zum(uebergeben_am)`` → Erkennung → Bewertung → ``rechne_lauf()`` →
  Ausarbeitung (#301).
  Sie rechnet bei jedem Aufruf; abgelegt wird von der ``AblegendeLaufquelle``
  darum herum (``ablage.py``, #290).

Was **nicht** hier liegt: die Gate-1-Entscheidung. Die hat ihr eigenes Modul
(``gate1.py``), weil sie einen anderen Lebenslauf hat — sie wird geschrieben,
der Lauf wird gerechnet.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Protocol

from modell import STANDARD, Lauf, Parameter, Potenzialeingang, rechne_lauf
from modell.ausgabe import als_eintraege, als_konzept_potenzial, als_prozess_raenge
from modell.laden import lies_messsatz
from nachfolge import Kandidat, Nachfolge

__all__ = [
    "SCORE_FORMEL",
    "Laufkopf",
    "Laufansicht",
    "Laufquelle",
    "LaufAngehalten",
    "MesssatzLaufquelle",
    "PaketLaufquelle",
    "Paketeintrag",
    "Paketverzeichnis",
    "PostgresPaketverzeichnis",
    "SpeicherLaufquelle",
    "SpeicherPaketverzeichnis",
    "aus_lauf",
]

# Das Vertragsfeld ``score_formel`` ist Markdown, kein Parameter: es soll einen
# Prüfer die Zahl **ohne Datenbank** nachrechnen lassen. Es steht deshalb hier
# als Text und nicht in ``modell/parameter.py``, wo die Zahlen liegen.
SCORE_FORMEL = (
    "`score = impact × (11 − umsetzungskomplexitaet)`, Bereich 1…100.\n\n"
    "- `impact = round((impact_monetaer + nutzwert) / 2)` — beide auf 1–10.\n"
    "- `umsetzungskomplexitaet = round(11 − 2 × Mittel der vier BC1-Skalen)`; "
    "fehlen die Skalen, urteilt das LLM und die Herkunft ist `geurteilt`.\n"
    "- Die **lineare** Umkehrung der Komplexität ist bewusst gesetzt, obwohl der "
    "Sprung ins sehr Aufwendige fachlich überproportional wäre — offengelegt, "
    "nicht kaschiert (ADR-006 · BC2)."
)


@dataclass(frozen=True)
class Laufkopf:
    """Was in der **Liste der Läufe** steht — dem Einstieg der Oberfläche.

    Kein Profil, keine Mandantenwahl: seit #165 stößt BC0 an und seit ADR-005
    ist der Lauf das Paket. Die Liste ist deshalb die Startseite und nicht eine
    Seite davor (#167, Frage 1).
    """

    paket_id: str
    company_id: str
    uebergeben_am: datetime
    fassung: int = 1
    anzahl_potenziale: int = 0
    kp_ids: tuple[str, ...] = ()
    gate1_status: str = "pending"
    #: Warum dieser Lauf nicht nachrechenbar ist, falls er es nicht ist.
    warnung: str | None = None
    #: Die Teilprozesse des **Pakets**, auch die, aus denen kein Potenzial
    #: entstand. An ihnen hängt die Suche nach Vorgängern (ADR-009 · BC2 §2.2):
    #: ein schon gelieferter Teilprozess, den das Paket neu bringt, ist neu
    #: gesehen — auch wenn diesmal nichts aus ihm geschnitten wird. Eine Quelle
    #: ohne Paketliste (Messsatz) trägt hier die berührten Teilprozesse.
    teilprozess_ids: tuple[str, ...] = ()

    def als_json(self) -> dict:
        eintrag = {
            "paket_id": self.paket_id,
            "company_id": self.company_id,
            "uebergeben_am": self.uebergeben_am.isoformat(),
            "fassung": self.fassung,
            "anzahl_potenziale": self.anzahl_potenziale,
            "kp_ids": list(self.kp_ids),
            "gate1_status": self.gate1_status,
        }
        if self.warnung:
            eintrag["warnung"] = self.warnung
        return eintrag


@dataclass(frozen=True)
class Laufansicht:
    """Ein ganzer Lauf, in Vertragsform v3.0 plus dem, was die Anzeige braucht.

    ``eintraege`` und ``prozess_raenge`` sind **wörtlich** die Blöcke aus
    ``priorisierung.schema.json``. ``potenziale`` trägt je Potenzial zusätzlich
    die gerechneten Felder des Konzepts (Value-Spannen, Nutzwert-Kategorien,
    Automatisierungsgrad, Hinweise) — das ist der Inhalt der Detail-Schublade.

    Die **Texte** (``beschreibung``, ``to_be_vision``, ``user_story``, die
    Akzeptanzkriterien …) schreibt der Ausarbeitungsschritt (#301); trägt die
    Quelle sie, stehen sie hier mit. Eine Quelle ohne ihn (Messsatz) lässt sie
    weg, statt einen Platzhalter zu erfinden.
    """

    kopf: Laufkopf
    score_formel: str
    eintraege: list[dict]
    prozess_raenge: list[dict]
    potenziale: dict[str, dict]
    #: ``kp_id`` → Klartextname, soweit bekannt.
    kp_namen: dict[str, str] = field(default_factory=dict)
    #: ``priorisierung.ausgangslage`` (v3.1, #254), sobald die Quelle sie trägt.
    #: Ein Messsatz trägt sie nicht — er kennt weder Mandantensatz noch
    #: Schmerzpunkte —, und dann fehlt sie, statt erfunden zu werden.
    ausgangslage: dict | None = None
    #: Die Konzepte in Vertragsform, sobald die Quelle sie trägt
    #: (Ausarbeitungsschritt, #301; Lieferordner). Ohne sie baut :meth:`als_vertrag` Konzepte aus den
    #: gerechneten Hälften der Potenziale.
    konzepte: list[dict] | None = None
    #: Wie der Lauf mit seinen Vorgänger-Kandidaten verfahren ist (#295).
    #: ``None`` heißt: die Quelle hat keine beurteilt — nicht „es gab keine“.
    nachfolge: Nachfolge | None = None
    #: ``priorisierung.gestrichene_potenziale`` (v3.1), wie abgelegt.
    gestrichene_potenziale: list[dict] | None = None
    #: Die gelieferten Potenziale, auf die dieser Lauf verweist — Vorgänger und
    #: Gestrichene —, ``potenzial_id → {titel, paket_id, kp_id}``. Nur für das
    #: Auge am Gate 1: im Vertrag steht allein die Kennung.
    verwiesen: dict[str, dict] = field(default_factory=dict)

    def potenzial_ids(self) -> list[str]:
        """Alle Potenziale des Laufs, in **gerechneter** Rangfolge."""
        return [e["potenzial_id"] for e in self.eintraege]

    def kp_ids(self) -> list[str]:
        """Alle Kernprozesse, in **gerechneter** Prozessrangfolge."""
        return [r["kp_id"] for r in self.prozess_raenge]

    def als_vertrag(self, gate1: dict) -> tuple[list[dict], dict]:
        """Konzepte und Priorisierung dieses Laufs, soweit die Quelle sie trägt.

        Das ist die Eingabe des Foliengenerators (#257). Die Priorisierung ist
        vollständig bis auf das, was die Quelle nicht hat: ``ausgangslage``
        steht nur da, wenn sie da ist (dann ``schema_version`` 3.1, sonst 3.0).
        Die **Konzepte** sind ohne eigene Quelle nur die gerechneten Hälften
        der Potenziale (``modell/ausgabe.py``) — ohne Beschreibung, Vision und
        Lösungsansatz, die das LLM schreibt. Sie sind damit **nicht
        schemagültig** und gehen nirgends hin als in die Präsentation, die das
        Fehlen ansagt. An BC3 geht nur, was der Ausarbeitungsschritt
        vollständig liefert (#301).
        """
        konzept_ids = {r["kp_id"]: r["konzept_id"] for r in self.prozess_raenge}
        if self.konzepte is not None:
            konzepte = self.konzepte
        else:
            konzepte = []
            for kp_id, konzept_id in konzept_ids.items():
                konzepte.append({
                    "konzept_id": konzept_id,
                    "kontext": {"kp_id": kp_id},
                    "potenziale": [
                        self.potenziale[e["potenzial_id"]]
                        for e in self.eintraege
                        if e["kp_id"] == kp_id
                    ],
                })
        k = self.kopf
        priorisierung: dict = {
            "schema_version": "3.1" if self.ausgangslage else "3.0",
            "company_id": k.company_id,
            "paket_id": k.paket_id,
            "uebergeben_am": k.uebergeben_am.isoformat(),
            "fassung": k.fassung,
            "score_formel": self.score_formel,
            "konzept_ids": list(konzept_ids.values()),
            "eintraege": self.eintraege,
            "prozess_raenge": self.prozess_raenge,
            "gate1": gate1,
        }
        if self.ausgangslage:
            priorisierung["ausgangslage"] = self.ausgangslage
            # Pflicht ab 3.1 wie die Ausgangslage (ADR-009 · BC2 §2.7).
            priorisierung["gestrichene_potenziale"] = list(self.gestrichene_potenziale or [])
        return konzepte, priorisierung

    def als_json(self) -> dict:
        return {
            "kopf": self.kopf.als_json(),
            "score_formel": self.score_formel,
            "eintraege": self.eintraege,
            "prozess_raenge": self.prozess_raenge,
            "potenziale": self.potenziale,
            "kp_namen": self.kp_namen,
            # Die Kette über Pakete hinweg (#295): je Potenzial steht sie in
            # ``potenziale[].ersetzt_potenzial_ids``, hier die Streichliste und
            # was hinter den Kennungen steht.
            "gestrichene_potenziale": list(self.gestrichene_potenziale or []),
            "verwiesen": self.verwiesen,
        }


def aus_lauf(
    lauf: Lauf,
    eingaenge: list[Potenzialeingang],
    *,
    uebergeben_am: datetime,
    fassung: int = 1,
    warnung: str | None = None,
    kp_namen: dict[str, str] | None = None,
) -> Laufansicht:
    """Baut die Ansicht aus einem gerechneten :class:`~modell.rechnen.Lauf`.

    ``eingaenge`` muss mitkommen, weil ein gerechnetes ``Potenzial`` nur das
    **Mittel** des Nutzwerts trägt, nicht die fünf Kategorien mit ihren
    Begründungssätzen — die gehören zum Urteil des LLM und nicht ins
    Rechenergebnis (so der Schnitt in ``modell/ausgabe.py``). Die Oberfläche
    zeigt sie im Detail, also müssen sie von hier kommen.

    ``konzept_ids`` verlangt die Vertragsabbildung, weil jede **Fassung** eine
    neue Konzept-Kennung bekommt (ADR-007 · BC2, 2.5). Solange nicht
    ausgeliefert wird, gibt es noch keine — hier steht deshalb eine ableitbare
    Kennung aus Paket, Fassung und Kernprozess. Sie ist stabil (derselbe Lauf
    ergibt dieselbe) und ersetzt die echte nicht: die entsteht beim Ausliefern.
    """
    konzept_ids = {
        r.kp_id: f"{lauf.paket_id}-f{fassung}-{r.kp_id}" for r in lauf.prozess_raenge
    }
    nutzwerte = {e.potenzial_id: e.nutzwert for e in eingaenge}

    return Laufansicht(
        kopf=Laufkopf(
            paket_id=lauf.paket_id,
            company_id=lauf.company_id,
            uebergeben_am=uebergeben_am,
            fassung=fassung,
            anzahl_potenziale=len(lauf.potenziale),
            kp_ids=tuple(r.kp_id for r in lauf.prozess_raenge),
            warnung=warnung,
            teilprozess_ids=tuple(
                sorted({t for p in lauf.potenziale for t in p.betroffene_teilprozess_ids})
            ),
        ),
        score_formel=SCORE_FORMEL,
        eintraege=als_eintraege(lauf, konzept_ids),
        prozess_raenge=als_prozess_raenge(lauf, konzept_ids),
        potenziale={
            pot.potenzial_id: als_konzept_potenzial(pot, nutzwerte[pot.potenzial_id])
            for pot in lauf.potenziale
        },
        kp_namen=dict(kp_namen or {}),
    )


class Laufquelle(Protocol):
    """Was die Oberfläche von ihrer Datenquelle braucht — mehr nicht."""

    def uebersicht(self, company_id: str | None = None) -> list[Laufkopf]:
        """Die Läufe, neueste zuerst.

        ``company_id`` filtert. **Der Filter ist keine Bequemlichkeit:** es
        liegen zwei Mandanten in derselben Datenbank, und die Datenbank trennt
        sie nicht (Invariante aus ``CLAUDE.md``, bestätigt in #167 Frage 1 —
        im Eingang liegt ein Paket des Übungsmandanten neben denen von NoroAI).
        """
        ...

    def ansicht(
        self, paket_id: str, kandidaten: tuple[Kandidat, ...] = ()
    ) -> Laufansicht | None:
        """Der ganze Lauf, oder ``None``, wenn es ihn nicht gibt.

        ``kandidaten`` sind die schon gelieferten Potenziale, die das Paket
        berührt (ADR-009 · BC2 §2.2). Eine Quelle, die sie beurteilen kann,
        trägt das Ergebnis in ``Laufansicht.nachfolge``; eine, die es nicht
        kann, lässt das Feld leer, und die Ablage bricht ab.
        """
        ...


class MesssatzLaufquelle:
    """Rechnet Messsätze aus einem Verzeichnis durch.

    **Behelfsquelle, bis der Erkennungsschritt gebaut ist (#248).** Sie liest
    keine Datenbank und kann darum auch nicht auf dem Freigabestand rechnen;
    die ``warnung`` der Datei reist deshalb bis in die Kopfzeile der Oberfläche.
    """

    def __init__(self, verzeichnis: Path | str, uebergeben_am: datetime | None = None) -> None:
        self._verzeichnis = Path(verzeichnis)
        # Ein Messsatz trägt keinen Freigabezeitpunkt — er kommt nicht von BC0.
        # Statt einen zu erfinden, wird die Änderungszeit der Datei genommen und
        # in der Oberfläche als das ausgewiesen, was sie ist.
        self._uebergeben_am = uebergeben_am

    def _dateien(self) -> list[Path]:
        if not self._verzeichnis.is_dir():
            return []
        return sorted(self._verzeichnis.glob("*.json"))

    def _ansicht_aus_datei(self, pfad: Path) -> Laufansicht:
        satz = lies_messsatz(pfad)
        lauf = rechne_lauf(satz.company_id, satz.paket_id, satz.eingaenge)
        zeitpunkt = self._uebergeben_am or datetime.fromtimestamp(
            pfad.stat().st_mtime
        ).astimezone()
        return aus_lauf(
            lauf, satz.eingaenge, uebergeben_am=zeitpunkt, warnung=satz.warnung
        )

    def uebersicht(self, company_id: str | None = None) -> list[Laufkopf]:
        koepfe = []
        for pfad in self._dateien():
            kopf = self._ansicht_aus_datei(pfad).kopf
            if company_id is None or kopf.company_id == company_id:
                koepfe.append(kopf)
        return sorted(koepfe, key=lambda k: k.uebergeben_am, reverse=True)

    def ansicht(
        self, paket_id: str, kandidaten: tuple[Kandidat, ...] = ()
    ) -> Laufansicht | None:
        # Ein Messsatz kennt kein Modell und beurteilt darum keine Kandidaten.
        for pfad in self._dateien():
            ansicht = self._ansicht_aus_datei(pfad)
            if ansicht.kopf.paket_id == paket_id:
                return ansicht
        return None


@dataclass
class SpeicherLaufquelle:
    """Fertige Ansichten im Arbeitsspeicher — für die Tests."""

    ansichten: list[Laufansicht] = field(default_factory=list)

    def uebersicht(self, company_id: str | None = None) -> list[Laufkopf]:
        koepfe = [
            a.kopf
            for a in self.ansichten
            if company_id is None or a.kopf.company_id == company_id
        ]
        return sorted(koepfe, key=lambda k: k.uebergeben_am, reverse=True)

    def ansicht(
        self, paket_id: str, kandidaten: tuple[Kandidat, ...] = ()
    ) -> Laufansicht | None:
        # Die Ansicht, wie sie gelegt wurde — samt der ``nachfolge``, die ein
        # Test ihr mitgegeben hat.
        for a in self.ansichten:
            if a.kopf.paket_id == paket_id:
                return a
        return None


# ---------------------------------------------------------------------------
# Der echte Weg: Paket → Erkennung → Bewertung → Rechnung (#288)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Paketeintrag:
    """Ein angenommenes Paket mit den Teilprozessen, die BC0 darin freigab."""

    paket_id: str
    company_id: str
    uebergeben_am: datetime
    teilprozess_ids: tuple[str, ...]


class Paketverzeichnis(Protocol):
    """Welche Pakete BC2 angenommen hat — und was in ihnen steht."""

    def pakete(self) -> list[Paketeintrag]:
        ...


@dataclass
class SpeicherPaketverzeichnis:
    """Für Tests und die Werkbank."""

    eintraege: list[Paketeintrag] = field(default_factory=list)

    def pakete(self) -> list[Paketeintrag]:
        return list(self.eintraege)


# BC0 schickt beim Anstoss bewusst **nur die Kennungen** (app.py, #205) — der
# Paketinhalt steht in BC0s `gate_paket_inhalt`, nicht in `bc2.eingang`. Beide
# Seiten werden darum hier verbunden, durchgehend als `text`: in BC0s Schema
# sind die Kennungen `uuid`, in `bc2.eingang` `text` (derselbe Fallstrick wie in
# eingang.py, #190).
_SQL_PAKETE = """
SELECT e.paket_id,
       e.company_id,
       e.uebergeben_am,
       array_agg(i.sub_process_id::text ORDER BY i.sub_process_id) AS teilprozesse
  FROM bc2.eingang e
  JOIN public.gate_paket_inhalt i
    ON i.paket_id::text = e.paket_id
   AND i.company_id::text = e.company_id
 GROUP BY e.paket_id, e.company_id, e.uebergeben_am
 ORDER BY e.uebergeben_am DESC
"""


class PostgresPaketverzeichnis:
    """Die angenommenen Pakete aus der gemeinsamen Datenbank.

    .. warning::
       **Beim Bau (#288) nicht gegen die laufende Datenbank gefahren** — lokal
       gibt es bewusst keine ``DATABASE_URL`` (Entscheidung vom 21.09.2026).
       Ob ``bc2_role`` ``gate_paket_inhalt`` lesen darf, ist damit ungeprüft;
       ``v_uebergabe_offen`` liest sie, die Rolle selbst ist nicht gemessen.
       Die Gegenprobe gehört zum ersten echten Lauf (#206).
    """

    def __init__(self, dsn: str | None = None) -> None:
        import os

        self._dsn = dsn or (os.environ.get("DATABASE_URL") or "").strip()
        if not self._dsn:
            raise RuntimeError(
                "DATABASE_URL ist nicht gesetzt. Die Zugangsdaten gehoeren "
                "ausschliesslich in eine Umgebungsvariable (ADR-003)."
            )

    def pakete(self) -> list[Paketeintrag]:
        import psycopg2
        import psycopg2.extras

        with psycopg2.connect(self._dsn) as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(_SQL_PAKETE)
            zeilen = cur.fetchall()
        return [
            Paketeintrag(
                paket_id=z["paket_id"],
                company_id=z["company_id"],
                uebergeben_am=z["uebergeben_am"],
                teilprozess_ids=tuple(z["teilprozesse"] or ()),
            )
            for z in zeilen
        ]


#: Was jeder so gerechnete Lauf ansagt. Er ist auf ``stand_zum`` gelesen, aber
#: der **Schnitt** ist ein Modellurteil: ein Neulauf schneidet neu, und nicht
#: zwingend gleich — und ob das Urteil stabil genug ist, ist offen (#299).
MODELLURTEIL = (
    "Schnitt und Bewertung sind Modellurteile: ein Neulauf desselben Pakets schneidet "
    "und bewertet neu, nicht zwingend gleich. Die Stabilitaetsabnahme des "
    "Bewertungsschritts ist gescheitert (#288); der Schnitt wird in #299 neu gestellt."
)


class LaufAngehalten(RuntimeError):
    """Ein Lauf ist nicht zustande gekommen — und das ist kein Absturz.

    Das Modell brach seine Zusage auch in der Wiederholung, oder der
    Freigabestand liegt vor dem Beginn der Historie. **Geworfen, nicht als
    leerer Lauf verpackt:** die ``AblegendeLaufquelle`` vermerkt den Lauf dann
    als gescheitert und versucht beim nächsten Öffnen dieselbe Fassung neu; ein
    leerer Lauf läge dagegen als gültiges Ergebnis in Schema ``bc2`` (#290).
    """


class PaketLaufquelle:
    """Rechnet ein angenommenes Paket — Erkennung, Bewertung, Rechenkern.

    **Zustandslos, mit Absicht.** Jeder Aufruf von :meth:`ansicht` rechnet neu.
    Einmal rechnen und dann zeigen ist die Aufgabe der ``AblegendeLaufquelle``
    darum herum (#290) — und ``neu_rechnen`` nach einem Reject verlässt sich
    darauf, dass die innere Quelle einen **neuen** Schnitt liefert. Ein
    Zwischenspeicher hier gäbe dort den alten zurück.

    **Die Liste rechnet nicht.** Ein Lauf kostet einen Erkennungs- und drei
    Bewertungsaufrufe (#299) und je Konzept einen Ausarbeitungsaufruf (#301); die
    Übersicht zeigt ein ungerechnetes Paket darum mit ``0`` Potenzialen und sagt
    das an, statt eine Zahl zu erfinden.
    """

    def __init__(
        self,
        verzeichnis: Paketverzeichnis,
        bestand,  # erkennung.Bestandsquelle
        modell,  # erkennung.Modellruf
        parameter: Parameter = STANDARD,
        urteile: int | None = None,
        ausarbeiten: bool = True,
        gleichzeitig: int | None = None,
    ) -> None:
        self._verzeichnis = verzeichnis
        self._bestand = bestand
        self._modell = modell
        self._parameter = parameter
        #: ``None`` ⇒ die Voreinstellung des Bewertungsschritts (#299).
        self._urteile = urteile
        #: ``False`` nur für Tests, die den Rechenweg ohne Texte prüfen: ohne
        #: Ausarbeitung ist ein Lauf nicht lieferbar (#301).
        self._ausarbeiten = ausarbeiten
        #: Wie viele Konzepte zugleich ausgearbeitet werden; ``None`` ⇒ alle.
        self._gleichzeitig = gleichzeitig

    def uebersicht(self, company_id: str | None = None) -> list[Laufkopf]:
        koepfe = [
            Laufkopf(
                paket_id=e.paket_id,
                company_id=e.company_id,
                uebergeben_am=e.uebergeben_am,
                anzahl_potenziale=0,
                kp_ids=tuple(sorted({t.split(".")[0] for t in e.teilprozess_ids})),
                warnung="Noch nicht gerechnet — Oeffnen schneidet und bewertet das Paket.",
                teilprozess_ids=e.teilprozess_ids,
            )
            for e in self._verzeichnis.pakete()
            if company_id is None or e.company_id == company_id
        ]
        return sorted(koepfe, key=lambda k: k.uebergeben_am, reverse=True)

    def ansicht(
        self, paket_id: str, kandidaten: tuple[Kandidat, ...] = ()
    ) -> Laufansicht | None:
        """Rechnet den Lauf. ``None``, wenn es das Paket nicht gibt.

        Die ``kandidaten`` gehen in den Paketaufruf der Erkennung, und das
        Modell ordnet sie dort zu (ADR-009 · BC2 §2.5).

        :raises LaufAngehalten: wenn Erkennung oder Bewertung auch in der
            Wiederholung brechen, oder der Freigabestand nicht rekonstruierbar ist.
        """
        eintrag = next((e for e in self._verzeichnis.pakete() if e.paket_id == paket_id), None)
        if eintrag is None:
            return None
        return self._rechne(eintrag, kandidaten)

    def _rechne(self, e: Paketeintrag, kandidaten: tuple[Kandidat, ...]) -> Laufansicht:
        # Lokal importiert: die Messsatz-Quelle und die Tests der Oberflaeche
        # kommen ohne Erkennung und Bewertung aus.
        from bewertung import BewertungAbgebrochen, bewerte
        from erkennung import ErkennungAbgebrochen, HistorieZuAlt, erkenne

        try:
            bestand = self._bestand.lies_paket(
                e.company_id, e.paket_id, e.uebergeben_am, list(e.teilprozess_ids)
            )
            erkennung = erkenne(bestand, self._modell, kandidaten=kandidaten)
            bewertung = bewerte(
                erkennung,
                bestand,
                self._modell,
                parameter=self._parameter,
                **({} if self._urteile is None else {"urteile": self._urteile}),
            )
        except (ErkennungAbgebrochen, BewertungAbgebrochen) as fehler:
            raise LaufAngehalten(
                f"Lauf {e.paket_id} angehalten — das Modell brach seine Zusage auch in "
                f"der Wiederholung: {fehler}"
            ) from fehler
        except HistorieZuAlt as fehler:
            raise LaufAngehalten(
                f"Lauf {e.paket_id} nicht nachrechenbar: {fehler}. Ein Ergebnis auf dem "
                "Livestand waere etwas anderes als das Bestellte."
            ) from fehler

        kopf = Laufkopf(
            paket_id=e.paket_id,
            company_id=e.company_id,
            uebergeben_am=e.uebergeben_am,
            teilprozess_ids=e.teilprozess_ids,
        )
        # Die Erkennung nennt Nachfolger mit ihrer Nummer, der Vertrag mit der
        # UUID aus dem Bewertungsschritt.
        nachfolge = erkennung.nachfolge.umbenannt(bewertung.kennungen)
        hinweise = list(erkennung.hinweise)
        kp_namen = {kp.kernprozess_id: kp.name for kp in bestand.kernprozesse}
        if not bewertung.eingaenge:
            # Ein Paket ohne Potenzial ist ein Ergebnis, kein Fehler: die
            # Erkennung hat seine Teilprozesse als nicht geschnitten gemeldet.
            return Laufansicht(
                kopf=replace(
                    kopf,
                    warnung=" ".join(
                        ["Aus diesem Paket ist kein Potenzial geschnitten worden.", *hinweise]
                    ),
                ),
                score_formel=SCORE_FORMEL,
                eintraege=[],
                prozess_raenge=[],
                potenziale={},
                kp_namen=kp_namen,
                nachfolge=nachfolge,
            )

        lauf = rechne_lauf(e.company_id, e.paket_id, bewertung.eingaenge, self._parameter)
        ansicht = aus_lauf(
            lauf,
            list(bewertung.eingaenge),
            uebergeben_am=e.uebergeben_am,
            warnung=" ".join([*hinweise, MODELLURTEIL]),
            kp_namen=kp_namen,
        )
        ansicht = replace(
            ansicht,
            kopf=replace(ansicht.kopf, teilprozess_ids=e.teilprozess_ids),
            nachfolge=nachfolge,
        )
        if not self._ausarbeiten:
            return ansicht

        # Nach der Rechnung, nie davor (ADR-010 · BC2): die Texte kennen den
        # Rang, bewegen ihn aber nicht.
        from ausarbeitung import AusarbeitungAbgebrochen, arbeite_aus

        try:
            ausarbeitung = arbeite_aus(
                lauf,
                ansicht.potenziale,
                erkennung,
                bewertung.kennungen,
                bestand,
                self._modell,
                gleichzeitig=self._gleichzeitig,
            )
        except AusarbeitungAbgebrochen as fehler:
            raise LaufAngehalten(
                f"Lauf {e.paket_id} angehalten — das Modell brach seine Zusage auch in "
                f"der Wiederholung: {fehler}"
            ) from fehler
        return replace(
            ansicht,
            konzepte=list(ausarbeitung.konzepte),
            ausgangslage=ausarbeitung.ausgangslage,
            # Die Detail-Schublade zeigt die Texte mit (#301, Q8): sehen ja,
            # ändern nein.
            potenziale={
                p["potenzial_id"]: p for k in ausarbeitung.konzepte for p in k["potenziale"]
            },
        )
