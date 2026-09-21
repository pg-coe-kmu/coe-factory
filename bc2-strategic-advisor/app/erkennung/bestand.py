"""
BC2 · Der Datenstand eines Pakets — die Leseseite des Erkennungsschritts.

Ein ``Paketbestand`` ist alles, was BC2 über die freigegebenen Teilprozesse
eines Pakets weiß, gelesen **auf dem Stand, der der Freigabe zugrunde lag**
(``stand_zum(uebergeben_am)``, ADR-005 · BC2). Er ist die einzige Eingabe der
Nutzlast und damit die einzige Stelle, an der Rohdaten in den Erkennungsschritt
kommen.

**Die Naht liegt hier, aus demselben Grund wie bei** :mod:`eingang` **.** BC2
liest 26 Tabellen und 22 Views fremden Schemas. Ein Test, der eine echte
Postgres-Verbindung braucht, ist in der Vorschleife nicht bezahlbar; ein Test,
der SQLite unterschiebt, prüfte eine andere Datenbank als die, gegen die
gelaufen wird. Also: ein Protokoll ``Bestandsquelle``, dahinter
:class:`PostgresBestand` für den Betrieb und :class:`SnapshotBestand` für Tests
und Messungen ohne Zugangsdaten.

**Auflage 4 aus #248 greift hier und nicht später.** Ein Teilprozess ohne
Bewertungen bekommt gar kein Automatisierungsprofil (``None``), keines voller
Nullen: ``bewertet`` fragt nach dem **Vorhandensein**, nie nach ``avg > 0``.
Sonst hielte man den unerhobenen Teilprozess für den am schlechtesten
automatisierbaren im Bestand — dieselbe Falle wie
``v_gate_prozessstand.tp_mit_medienbruch`` (Fund aus #163), dieselbe Regel wie
#167 („Etikett statt Zahl, nie eine 0").

*(Berichtigt am 21.09.2026 nach der Gegenprobe #249: die Begründung aus #194 —
„27 von 50 stehen in ``prozessautomatisierung_matrix`` mit ``avg: 0``" — gilt
**nur für den Snapshot-Export**. An der laufenden Datenbank hat
``v_prozessautomatisierung`` 23 Zeilen und keine einzige Null; ein ``GROUP BY``
über die Bewertungen kann keinen unbewerteten Teilprozess erzeugen. Die Lücke
besteht (27 von 50 sind unbewertet), nur erzeugt nicht die Datenbank die Null,
sondern der Export. Für den Produktionsweg ist die Auflage damit
gegenstandslos — **für die Test-Fixture wiegt sie schwerer**, und genau auf ihr
läuft :class:`SnapshotBestand`.)*

**Was diese Schicht nicht kann: BC1 in die Vergangenheit lesen.** BC0s
Historisierung (``audit_log``) deckt ``public`` ab, nicht Schema ``bc1``.
``bc1.prozessprofil`` wird darum nach der Vertragsregel gelesen — jüngste
``profil_version`` mit ``status='fertig'`` (``contracts/bc1-to-bc2/lesen.sql``)
—, also **live statt zum Freigabezeitpunkt**. Das ist keine Nachlässigkeit,
sondern der Stand der fremden Schemas; es steht als ``hinweise`` am Bestand,
damit es in der Lieferung sichtbar wird statt still zu bleiben.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "Bestandsquelle",
    "Bewertung",
    "Bc1Profil",
    "Kernprozess",
    "Mandant",
    "Paketbestand",
    "PostgresBestand",
    "SnapshotBestand",
    "Teilprozess",
    "HistorieZuAlt",
]

#: BC0s Platzhalter-Teilprozesse heißen wörtlich „Teilprozess 3". Sie tragen
#: keinen erhobenen Ablauf und dürfen nicht geschnitten werden (#194: alle drei
#: Schnitte ließen ``KP-05.TP-2…5`` von sich aus unangetastet — die Regel hält,
#: aber sie wird hier trotzdem gesetzt statt erhofft).
_PLATZHALTER = re.compile(r"^\s*teilprozess\s*\d+\s*$", re.IGNORECASE)


class HistorieZuAlt(RuntimeError):
    """``uebergeben_am`` liegt vor ``historie_beginn()``.

    BC0s ``stand_zum()`` wirft dann selbst eine Ausnahme: vor dem Beginn der
    Historie ist nichts rekonstruierbar. Hier bekommt sie einen eigenen Typ,
    weil die Folge eine andere ist als bei einem Verbindungsfehler — der Lauf
    ist nicht *gestört*, er ist **nicht nachrechenbar**, und ein Ergebnis auf
    dem Livestand wäre etwas anderes als das Bestellte.
    """


# ---------------------------------------------------------------------------
# Was ein Bestand trägt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Bewertung:
    """Eine Bitkom-Bewertung je Teilprozess und Item.

    ``stufe`` ist eine **ordinale Stufe**, kein Erfüllungsgrad. Die Übersetzung
    in Prozentbänder (Checklisten-Skala, #171) gehört ins Value-Modell und
    ausdrücklich nicht hierher.
    """

    item_nr: int
    kriterium: str
    frage: str
    stufe: int
    beleg: str


@dataclass(frozen=True)
class Bc1Profil:
    """BC1s Erhebung zu einem Fokus-Schritt, in BC1s eigenen Feldnamen.

    Die Namen sind **1:1 die des BC1-Vertrags** (#184) — das ist dort
    Vertragsbestandteil und erspart eine Übersetzungstabelle, an der sich ein
    Missverständnis festsetzen könnte. ``executions_per_run`` fehlt mit
    Absicht: es ist **kein Multiplikator** (Invariante I2), und ein Feld, das
    nicht da ist, kann auch nicht versehentlich multipliziert werden.
    """

    focus_step_id: str
    profil_version: int | None = None
    erhebung_id: str | None = None
    frequency_per_year: float | None = None
    step_frequency_per_year: float | None = None
    total_duration_minutes: float | None = None
    focus_step_duration_minutes: float | None = None
    focus_step_duration_source: str | None = None
    focus_step_duration_confidence_pct: float | None = None
    documentation_status: int | None = None
    standardization_level: int | None = None
    data_availability_score: int | None = None
    stability_score: int | None = None
    automation_potential_estimate_pct: float | None = None
    kennzeichnung: str | None = None

    @property
    def reifeskalen(self) -> tuple[int, int, int, int] | None:
        """Die vier 1-bis-5-Skalen, die die Umsetzungskomplexität tragen.

        Nur vollständig oder gar nicht: drei von vier Skalen ergäben einen
        Mittelwert auf anderer Grundlage als die übrigen Potenziale, und die
        Komplexität ist eine **gemessene** Größe (ADR-006, 2.6) — ein
        teilgemessener Wert wäre ein Urteil, das sich als Messung ausgibt.
        """
        werte = (
            self.documentation_status,
            self.standardization_level,
            self.data_availability_score,
            self.stability_score,
        )
        if any(w is None for w in werte):
            return None
        return tuple(int(w) for w in werte)  # type: ignore[return-value]


@dataclass(frozen=True)
class Teilprozess:
    """Ein freigegebener Teilprozess mit allem, was BC2 über ihn weiß."""

    teilprozess_id: str
    kernprozess_id: str
    name: str
    schritt_nr: int | None = None
    ablauf: str | None = None
    werkzeuge: str | None = None
    medienbrueche: str | None = None
    schnittstellen: str | None = None
    api: str | None = None
    bitkom: tuple[Bewertung, ...] = ()
    bc1_profil: Bc1Profil | None = None

    @property
    def bewertet(self) -> bool:
        """Trägt der Teilprozess überhaupt Bewertungen?

        **Das ist Auflage 4.** Nicht ``avg > 0`` fragen — eine 0 ist hier keine
        schlechte Note, sondern eine fehlende Erhebung.
        """
        return bool(self.bitkom)

    @property
    def ist_platzhalter(self) -> bool:
        return bool(_PLATZHALTER.match(self.name or ""))

    @property
    def schneidbar(self) -> bool:
        """Darf aus diesem Teilprozess ein Potenzial geschnitten werden?

        Nein, wenn er nichts Eigenes trägt. Er wird dann gemeldet
        (``nicht_geschnitten``), nicht weggelassen — sonst verschwände er
        lautlos aus einem Paket, das ihn ausdrücklich freigegeben hat.
        """
        return self.bewertet and not self.ist_platzhalter


@dataclass(frozen=True)
class Kernprozess:
    """Ein Kernprozess mit seinen im Paket freigegebenen Teilprozessen."""

    kernprozess_id: str
    name: str
    kategorie: str | None = None
    ausloeser: str | None = None
    eingang: str | None = None
    ausgang: str | None = None
    teilprozesse: tuple[Teilprozess, ...] = ()


@dataclass(frozen=True)
class Mandant:
    company_id: str
    name: str | None = None
    branche: str | None = None
    mitarbeitende: int | None = None


@dataclass(frozen=True)
class Paketbestand:
    """Der Datenstand eines Analyselaufs ``(company_id, paket_id)``.

    ``uebergeben_am`` **und** ``gelesen_am`` reisen beide mit: das erste ist der
    Zeitanker der Rechnung, das zweite der Zeitpunkt des Lesens. Ihre Differenz
    zeigt, wie viel sich zwischen Freigabe und Rechnung bewegt haben kann —
    genau die Unterscheidung zwischen *Reproduzierbarkeit* und
    *Nachvollziehbarkeit* aus #166.
    """

    mandant: Mandant
    paket_id: str
    uebergeben_am: datetime
    gelesen_am: datetime
    kernprozesse: tuple[Kernprozess, ...] = ()
    hinweise: tuple[str, ...] = ()

    @property
    def company_id(self) -> str:
        return self.mandant.company_id

    @property
    def teilprozesse(self) -> tuple[Teilprozess, ...]:
        return tuple(t for kp in self.kernprozesse for t in kp.teilprozesse)

    @property
    def teilprozess_ids(self) -> tuple[str, ...]:
        return tuple(t.teilprozess_id for t in self.teilprozesse)

    @property
    def schneidbare_ids(self) -> tuple[str, ...]:
        return tuple(t.teilprozess_id for t in self.teilprozesse if t.schneidbar)


class Bestandsquelle(Protocol):
    """Was der Erkennungsschritt von seiner Lesequelle braucht — mehr nicht."""

    def lies_paket(
        self,
        company_id: str,
        paket_id: str,
        uebergeben_am: datetime,
        teilprozess_ids: list[str],
    ) -> Paketbestand:
        """Liest den Bestand eines Pakets auf ``stand_zum(uebergeben_am)``."""
        ...


# ---------------------------------------------------------------------------
# Gemeinsamer Zusammenbau
# ---------------------------------------------------------------------------


def _baue_kernprozesse(
    kp_kopf: dict[str, dict[str, Any]],
    tps: list[Teilprozess],
) -> tuple[Kernprozess, ...]:
    """Ordnet Teilprozesse ihren Kernprozessen zu.

    Der Kernprozess ist das **Präfix der Teilprozess-ID**, keine eigene
    Erhebung (Invariante aus ``CLAUDE.md``). Fehlt ein Kopf, entsteht trotzdem
    ein Kernprozess — mit der ID als Namen. Einen freigegebenen Teilprozess
    wegzulassen, nur weil sein Kopf fehlt, wäre die teurere Stille.
    """
    nach_kp: dict[str, list[Teilprozess]] = {}
    for tp in tps:
        nach_kp.setdefault(tp.kernprozess_id, []).append(tp)

    kps: list[Kernprozess] = []
    for kp_id in sorted(nach_kp):
        kopf = kp_kopf.get(kp_id, {})
        kps.append(
            Kernprozess(
                kernprozess_id=kp_id,
                name=kopf.get("process_name") or kp_id,
                kategorie=kopf.get("kategorie"),
                ausloeser=kopf.get("trigger_text"),
                eingang=kopf.get("input_text"),
                ausgang=kopf.get("output_text"),
                teilprozesse=tuple(
                    sorted(nach_kp[kp_id], key=lambda t: (t.schritt_nr or 0, t.teilprozess_id))
                ),
            )
        )
    return tuple(kps)


# ---------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------

# Die Stammdaten kommen über die Zeitreise. `stand_zum` liefert **SETOF JSONB**,
# je Zeile das Zeilenbild als JSON — darum durchgehend `->>` statt Spalten.
# Die Form stammt wörtlich aus BC0s eigenem Beispiel im COMMENT der Funktion:
#     SELECT * FROM stand_zum('bitkom_bewertungen', p.uebergeben_am, p.company_id)
_SQL_PROZESSE = """
SELECT s ->> 'process_id'   AS process_id,
       s ->> 'process_name' AS process_name,
       s ->> 'kategorie'    AS kategorie,
       s ->> 'trigger_text' AS trigger_text,
       s ->> 'input_text'   AS input_text,
       s ->> 'output_text'  AS output_text
  FROM stand_zum('ref_prozesse', %(stand)s, %(company_id)s) s
"""

_SQL_TEILPROZESSE = """
SELECT s ->> 'sub_process_id'      AS sub_process_id,
       s ->> 'process_id'          AS process_id,
       (s ->> 'step_no')::int      AS step_no,
       s ->> 'sub_process_name'    AS sub_process_name,
       s ->> 'notation'            AS notation,
       s ->> 'tools'               AS tools,
       s ->> 'medienbrueche'       AS medienbrueche,
       s ->> 'schnittstellen'      AS schnittstellen,
       s ->> 'api'                 AS api
  FROM stand_zum('ref_teilprozesse', %(stand)s, %(company_id)s) s
 WHERE s ->> 'sub_process_id' = ANY(%(teilprozesse)s)
"""

# Die Bewertungen NICHT aus `stand_zum('bitkom_bewertungen', …)` roh: das liefert
# auch überschriebene Stände. `bewertung_aktuell_zum` ist die Regel von
# `v_bewertung_aktuell` auf einen Zeitpunkt angewandt — je Teilprozess und Item
# die jüngste nicht verworfene Erhebung. Genau davor warnt auch
# contracts/bc1-to-bc2/lesen.sql am Ende ("NICHT SO die Bitkom-Bewertungen
# holen"), dort für den Weg über `erhebung_id`.
#
# Der Belegtext hängt an der Bewertungszeile, nicht an der Sicht — er kommt
# darum über einen Verbund auf das Zeilenbild derselben Erhebung dazu.
_SQL_BEWERTUNGEN = """
SELECT b.sub_process_id,
       b.item_nr,
       b.stufe,
       i.kriterium,
       i.frage,
       coalesce(roh ->> 'beleg', '') AS beleg
  FROM bewertung_aktuell_zum(%(company_id)s, %(stand)s) b
  JOIN ref_items i ON i.item_nr = b.item_nr
  LEFT JOIN stand_zum('bitkom_bewertungen', %(stand)s, %(company_id)s) roh
         ON roh ->> 'sub_process_id' = b.sub_process_id
        AND (roh ->> 'item_nr')::int = b.item_nr
        AND roh ->> 'erhebung_id'    = b.erhebung_id
 WHERE b.sub_process_id = ANY(%(teilprozesse)s)
 ORDER BY b.sub_process_id, b.item_nr
"""

_SQL_MANDANT = """
SELECT s ->> 'company_name' AS name,
       s ->> 'branche'      AS branche,
       (s ->> 'mitarbeitende')::int AS mitarbeitende
  FROM stand_zum('companies', %(stand)s, %(company_id)s) s
 LIMIT 1
"""

#: Die Leseregel des BC1-Vertrags, nach ``contracts/bc1-to-bc2/lesen.sql``.
#: Sie ist Vertragsbestandteil: es liegen **mehrere** fertige Versionen je
#: Fokus-Schritt vor, und wer „irgendeine" liest, liest still die falsche.
#:
#: **Eine Abweichung vom Vertragstext, mit Grund.** ``lesen.sql`` führt
#: ``p.step_frequency_per_year`` als Spalte, und genau daran **bricht die
#: Abfrage an der laufenden Datenbank** (``column p.step_frequency_per_year
#: does not exist``, gemessen in #249 am 21.09.2026): BC1 führt D3 als
#: JSON-Feld und hatte die Schema-Ergänzung ausdrücklich an das Binden
#: geknüpft. Die Abfrage scheitert **beim Parsen**, BC2 liest über den
#: Vertragsweg also *kein einziges* Profil — nicht eines weniger, keines.
#: Hier wird das Feld darum aus ``profil`` gelesen statt aus einer Spalte, die
#: es nicht gibt. Die Reparatur des Vertrags selbst ist
#: `#255 <https://github.com/pg-coe-kmu/coe-factory/issues/255>`_; bis dahin
#: liest BC2 wenigstens.
_SQL_BC1 = """
SELECT DISTINCT ON (p.focus_step_id)
       p.focus_step_id,
       p.profil_version,
       p.erhebung_id,
       p.frequency_per_year,
       p.total_duration_minutes,
       p.focus_step_duration_minutes,
       p.focus_step_duration_source,
       p.focus_step_duration_confidence_pct,
       p.profil
  FROM bc1.prozessprofil p
 WHERE p.company_id = %(company_id)s
   AND p.focus_step_id = ANY(%(teilprozesse)s)
   AND p.status = 'fertig'
 ORDER BY p.focus_step_id, p.profil_version DESC
"""

#: Die namentlich gebundenen Felder aus BC1s Profil-JSON (#184). Nur diese —
#: ein Profil trägt 43 Interviewfelder, gebunden sind acht.
#:
#: ``step_frequency_per_year`` steht hier und **nicht** in der Spaltenliste:
#: es ist die Größe mit Vorrang für den Fokus-Schritt (Invariante I8), aber
#: es existiert in BC1s Schema nur im JSON (#249 → #255).
_BC1_JSON_FELDER = (
    "step_frequency_per_year",
    "documentation_status",
    "standardization_level",
    "data_availability_score",
    "stability_score",
    "automation_potential_estimate_pct",
)


class PostgresBestand:
    """Liest den Paketbestand aus der gemeinsamen Datenbank.

    .. warning::
       **In dieser Fassung nicht gegen die laufende Datenbank gefahren.** Beim
       Bau (#248, 21.09.2026) lag keine ``DATABASE_URL`` vor. Die Abfragen sind
       gegen BC0s Schemadateien geschnitten — ``schema_v2.6_historie_und_paket.sql``
       für ``stand_zum``/``bewertung_aktuell_zum``, ``schema_v1.2_stammdaten_und_gate.sql``
       für die Spalten — und die Leseregel für BC1 stammt wörtlich aus dem
       Vertrag. Das ist der **Schluss vom Code auf das Verhalten**, und die
       Karte #158 verzeichnet dreimal, dass genau der danebengehen kann. Die
       Gegenprobe am Livestand ist
       `#249 <https://github.com/pg-coe-kmu/coe-factory/issues/249>`_.
    """

    def __init__(self, dsn: str | None = None) -> None:
        import os

        self._dsn = dsn or (os.environ.get("DATABASE_URL") or "").strip()
        if not self._dsn:
            raise RuntimeError(
                "DATABASE_URL ist nicht gesetzt. Die Zugangsdaten gehoeren "
                "ausschliesslich in eine Umgebungsvariable (ADR-003)."
            )

    def _verbindung(self):
        import psycopg2  # lokal: die Tests brauchen den Treiber nicht

        return psycopg2.connect(self._dsn)

    def lies_paket(
        self,
        company_id: str,
        paket_id: str,
        uebergeben_am: datetime,
        teilprozess_ids: list[str],
    ) -> Paketbestand:
        import psycopg2
        import psycopg2.extras

        p = {
            "company_id": company_id,
            "stand": uebergeben_am,
            "teilprozesse": list(teilprozess_ids),
        }
        hinweise: list[str] = []

        with self._verbindung() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            try:
                cur.execute(_SQL_MANDANT, p)
                m = cur.fetchone() or {}
                cur.execute(_SQL_PROZESSE, p)
                kp_kopf = {z["process_id"]: dict(z) for z in cur.fetchall()}
                cur.execute(_SQL_TEILPROZESSE, p)
                tp_zeilen = [dict(z) for z in cur.fetchall()]
                cur.execute(_SQL_BEWERTUNGEN, p)
                bew_zeilen = [dict(z) for z in cur.fetchall()]
            except psycopg2.errors.CheckViolation as fehler:
                # historie_beginn() bzw. historie_ausgenommen() haben zugeschlagen.
                raise HistorieZuAlt(
                    f"Der Stand vom {uebergeben_am.isoformat()} ist nicht "
                    f"rekonstruierbar: {fehler}"
                ) from fehler

            # BC1 liegt in Schema `bc1` und damit AUSSERHALB von BC0s
            # audit_log. Es gibt für BC1 keine Zeitreise — gelesen wird nach der
            # Vertragsregel (juengste fertige Version), also live.
            bc1: dict[str, Bc1Profil] = {}
            try:
                cur.execute(_SQL_BC1, p)
                for z in cur.fetchall():
                    bc1[z["focus_step_id"]] = _bc1_aus_zeile(dict(z))
            except psycopg2.Error:
                # Kein Lesezugriff oder Schema noch leer: kein Grund, den Lauf
                # anzuhalten. BC2 rechnet ohne BC1 qualitativ weiter und
                # scheitert allein an der monetaeren Wertaussage (#163).
                conn.rollback()
                hinweise.append(
                    "bc1.prozessprofil war nicht lesbar — der Lauf traegt keine "
                    "gemessenen Aufwandsgroessen."
                )

        if bc1:
            hinweise.append(
                "BC1s Profile sind LIVE gelesen, nicht auf stand_zum(uebergeben_am): "
                "Schema bc1 liegt ausserhalb von BC0s Historisierung. Es gilt die "
                "juengste profil_version mit status='fertig'."
            )

        bew_je_tp: dict[str, list[Bewertung]] = {}
        for z in bew_zeilen:
            bew_je_tp.setdefault(z["sub_process_id"], []).append(
                Bewertung(
                    item_nr=int(z["item_nr"]),
                    kriterium=z["kriterium"],
                    frage=z["frage"],
                    stufe=int(z["stufe"]),
                    beleg=z["beleg"] or "",
                )
            )

        tps = [
            Teilprozess(
                teilprozess_id=z["sub_process_id"],
                kernprozess_id=z["process_id"] or z["sub_process_id"].split(".")[0],
                name=z["sub_process_name"],
                schritt_nr=z["step_no"],
                ablauf=z["notation"],
                werkzeuge=z["tools"],
                medienbrueche=z["medienbrueche"],
                schnittstellen=z["schnittstellen"],
                api=z["api"],
                # Auflage 4: leer heisst leer. Kein Nullwert-Profil.
                bitkom=tuple(bew_je_tp.get(z["sub_process_id"], ())),
                bc1_profil=bc1.get(z["sub_process_id"]),
            )
            for z in tp_zeilen
        ]

        fehlend = sorted(set(teilprozess_ids) - {t.teilprozess_id for t in tps})
        if fehlend:
            hinweise.append(
                "Im Paket freigegeben, aber zum Stand nicht auffindbar: "
                + ", ".join(fehlend)
            )

        return Paketbestand(
            mandant=Mandant(
                company_id=company_id,
                name=m.get("name"),
                branche=m.get("branche"),
                mitarbeitende=m.get("mitarbeitende"),
            ),
            paket_id=paket_id,
            uebergeben_am=uebergeben_am,
            gelesen_am=datetime.now(timezone.utc),
            kernprozesse=_baue_kernprozesse(kp_kopf, tps),
            hinweise=tuple(hinweise),
        )


def _bc1_aus_zeile(z: dict[str, Any]) -> Bc1Profil:
    """Zieht die gebundenen Felder aus einer BC1-Profilzeile.

    Aus dem JSON kommen **nur** die acht namentlich gebundenen Felder, und nur
    solche mit ``status='gueltig'`` (Vertragsregel #184) — ein Feld mit einem
    anderen Status trägt keine Zahl, sondern einen offenen Klärpunkt.
    """
    profil = z.get("profil") or {}
    if isinstance(profil, str):
        profil = json.loads(profil)

    werte: dict[str, Any] = {}
    for feld in _BC1_JSON_FELDER:
        roh = profil.get(feld)
        if isinstance(roh, dict):
            if roh.get("status") == "gueltig":
                werte[feld] = roh.get("wert")
        elif roh is not None:
            werte[feld] = roh

    return Bc1Profil(
        focus_step_id=z["focus_step_id"],
        profil_version=z.get("profil_version"),
        erhebung_id=z.get("erhebung_id"),
        frequency_per_year=z.get("frequency_per_year"),
        step_frequency_per_year=werte.get("step_frequency_per_year"),
        total_duration_minutes=z.get("total_duration_minutes"),
        focus_step_duration_minutes=z.get("focus_step_duration_minutes"),
        focus_step_duration_source=z.get("focus_step_duration_source"),
        focus_step_duration_confidence_pct=z.get("focus_step_duration_confidence_pct"),
        documentation_status=werte.get("documentation_status"),
        standardization_level=werte.get("standardization_level"),
        data_availability_score=werte.get("data_availability_score"),
        stability_score=werte.get("stability_score"),
        automation_potential_estimate_pct=werte.get("automation_potential_estimate_pct"),
        kennzeichnung=profil.get("kennzeichnung") if isinstance(profil, dict) else None,
    )


# ---------------------------------------------------------------------------
# Snapshot (Tests und Messungen ohne Zugangsdaten)
# ---------------------------------------------------------------------------


@dataclass
class SnapshotBestand:
    """Liest aus BC0s eingefrorenem Baseline-Snapshot.

    **Kein Doppelgänger der Datenbank, sondern eine zweite echte Quelle.** Der
    Snapshot ist die eingefrorene Test-Fixture aus der Charting-Entscheidung
    vom 30.08.2026, und er ist es, gegen den #194 gemessen hat.

    Seine Grenze ist sein Datum: er stammt vom **27.08.2026** und ist damit
    älter als BC1s erste Lieferung (08.09.) und älter als die erste
    Gate-0-Freigabe (18.09.). ``uebergeben_am`` wird hier deshalb **nicht**
    angewandt — es gibt nur einen Stand. Der Bestand trägt das als Hinweis,
    damit aus einer Messung auf ihm keine Aussage über den Livestand wird.
    """

    pfad: Path
    _roh: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._roh = json.loads(Path(self.pfad).read_text(encoding="utf-8"))

    def lies_paket(
        self,
        company_id: str,
        paket_id: str,
        uebergeben_am: datetime,
        teilprozess_ids: list[str],
    ) -> Paketbestand:
        d = self._roh
        gesucht = set(teilprozess_ids)

        items = {i["item_nr"]: i for i in d["stammdaten"]["items"]}
        bew_je_tp: dict[str, list[Bewertung]] = {}
        for b in d.get("bewertungen", []):
            if b["sub_process_id"] not in gesucht:
                continue
            i = items.get(b["item_nr"], {})
            bew_je_tp.setdefault(b["sub_process_id"], []).append(
                Bewertung(
                    item_nr=b["item_nr"],
                    kriterium=i.get("kriterium", ""),
                    frage=i.get("frage", ""),
                    stufe=b["stufe"],
                    beleg=b.get("beleg", ""),
                )
            )

        kp_kopf: dict[str, dict[str, Any]] = {}
        tps: list[Teilprozess] = []
        for p in d["stammdaten"]["prozesse"]:
            kp_kopf[p["process_id"]] = {
                "process_name": p.get("process_name"),
                "kategorie": p.get("kategorie"),
                "trigger_text": p.get("trigger"),
                "input_text": p.get("input"),
                "output_text": p.get("output"),
            }
            for t in p["teilprozesse"]:
                if t["sub_process_id"] not in gesucht:
                    continue
                tps.append(
                    Teilprozess(
                        teilprozess_id=t["sub_process_id"],
                        kernprozess_id=p["process_id"],
                        name=t.get("name") or t.get("sub_process_name") or "",
                        schritt_nr=t.get("step_no"),
                        ablauf=t.get("notation"),
                        werkzeuge=t.get("tools"),
                        medienbrueche=t.get("medienbrueche"),
                        schnittstellen=t.get("schnittstellen"),
                        api=t.get("api"),
                        # Auflage 4: kein Eintrag heisst kein Profil, keine Null.
                        bitkom=tuple(
                            sorted(
                                bew_je_tp.get(t["sub_process_id"], ()),
                                key=lambda b: b.item_nr,
                            )
                        ),
                        bc1_profil=None,
                    )
                )

        fehlend = sorted(gesucht - {t.teilprozess_id for t in tps})
        hinweise = [
            "Gelesen aus BC0s Snapshot vom 27.08.2026, NICHT aus der laufenden "
            "Datenbank: uebergeben_am ist hier ohne Wirkung, es gibt nur einen "
            "Stand. BC1-Profile traegt der Snapshot nicht.",
        ]
        if fehlend:
            hinweise.append(
                "Im Paket freigegeben, aber im Snapshot nicht enthalten: "
                + ", ".join(fehlend)
            )

        mand = d.get("mandant", {})
        return Paketbestand(
            mandant=Mandant(
                company_id=company_id,
                name=mand.get("name"),
                branche=mand.get("branche"),
                mitarbeitende=mand.get("mitarbeitende"),
            ),
            paket_id=paket_id,
            uebergeben_am=uebergeben_am,
            gelesen_am=datetime.now(timezone.utc),
            kernprozesse=_baue_kernprozesse(kp_kopf, tps),
            hinweise=tuple(hinweise),
        )
