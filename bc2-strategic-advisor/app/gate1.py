"""
BC2 · Gate 1 — die Entscheidung des Menschen über einen Lauf.

Drei Dinge liegen hier, und nur diese drei:

- ``Gate1Entscheidung`` — was der Mensch entschieden hat, in der Form, die
  ``priorisierung.schema.json`` v3.0 unter ``gate1`` verlangt.
- ``pruefe`` — **die Regeln, die der Vertrag aufstellt**, als Prüfung auf dem
  Server. Der Prototyp zu #167 hatte sie nur im Browser (der Freigabeknopf blieb
  grau); damit sind sie eine Bitte, keine Regel. Wer die Oberfläche umgeht, käme
  an ihnen vorbei — und die Begründungspflicht ist genau der Punkt, an dem ein
  späterer Leser versteht, warum ein gerechnetes Potenzial in der Lieferung
  fehlt.
- ``Gate1Buch`` — das Protokoll der Ablage, samt Doppelgänger im
  Arbeitsspeicher.

**Die Postgres-Umsetzung steht seit #290** (ADR-008 · BC2, 2.3). Zwei Regeln
haben sich dabei geändert, und beide setzt die Datenbank durch, nicht dieser
Code:

- Der Schlüssel ist der **Lauf** ``(paket_id, fassung)``, nicht mehr das Paket.
  Nach einem Reject rechnet BC2 eine neue Fassung, und die hat ihr eigenes Gate 1.
- ``pending`` ist überschreibbar, ``approved`` und ``rejected`` sind
  **endgültig**. Ein zweites Schreiben danach ist ein ``Gate1Konflikt`` — an der
  Oberfläche ein ``409`` —, kein stilles Ersetzen. Der Konflikt bleibt allein
  zwischen zwei offenen Browsern, und den fängt die Zustandsbedingung
  ``… WHERE status = 'pending'``.

Der Doppelgänger zieht beide Regeln mit; die Garantie gegen zwei gleichzeitige
Schreiber gibt trotzdem nur die Datenbank (``tests/test_vertrag_postgres.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # nur für die Signatur; ablage.py importiert gate1 nicht
    from ablage import SpeicherErgebnisbuch

# Der Vertrag verlangt ``minLength: 5`` für eine Begründung. Fünf Zeichen sind
# keine gute Begründung, aber sie sind die Grenze, unterhalb derer sicher keine
# steht ("ok", "-", "nein"). Mehr zu verlangen wäre eine Qualitätsaussage, die
# eine Zeichenzahl nicht treffen kann.
MINDESTLAENGE_BEGRUENDUNG = 5

ZUSTAENDE = ("pending", "approved", "rejected")
ENDGUELTIG = ("approved", "rejected")


class Gate1Konflikt(Exception):
    """Gate 1 dieses Laufs ist schon entschieden und damit endgültig."""

    def __init__(self, paket_id: str, fassung: int, bisher: str) -> None:
        super().__init__(
            f"Gate 1 fuer {paket_id} (Fassung {fassung}) ist bereits {bisher} "
            "entschieden und endgueltig."
        )
        self.bisher = bisher


class LaufUnbekannt(Exception):
    """Zu diesem ``(paket_id, fassung)`` liegt kein gerechneter Lauf."""


@dataclass(frozen=True)
class NichtFreigegeben:
    """Ein Potenzial, das der Mensch herausgenommen hat, samt Grund."""

    potenzial_id: str
    begruendung: str


@dataclass(frozen=True)
class Gate1Entscheidung:
    """Die Entscheidung über **einen Lauf** — nicht über ein Konzept.

    Seit v3.0 sitzt ``gate1`` bei der Priorisierung und nicht mehr im Konzept
    (ADR-007 · BC2, 2.1): entschieden wird über den Lauf, und vorher wurde an
    einer Stelle entschieden und an *n* anderen protokolliert.
    """

    paket_id: str
    company_id: str
    status: str
    fassung: int = 1
    approved_potenzial_ids: tuple[str, ...] = ()
    nicht_freigegeben: tuple[NichtFreigegeben, ...] = ()
    finale_reihenfolge_potenzial_ids: tuple[str, ...] = ()
    finale_prozessreihenfolge_kp_ids: tuple[str, ...] = ()
    abweichungsbegruendung: str = ""
    entscheider: str = ""
    kommentar: str = ""
    entschieden_am: datetime | None = None

    def als_vertrag(self) -> dict:
        """Der ``gate1``-Block, wie ``priorisierung.schema.json`` ihn verlangt.

        Leere Felder werden **weggelassen** statt als ``[]`` oder ``""``
        geschrieben: der Block ist ``additionalProperties: false`` mit nur
        ``status`` als Pflicht, und ein fehlendes
        ``finale_reihenfolge_potenzial_ids`` bedeutet ausdrücklich "es gilt der
        gerechnete Rang". Eine leere Liste hiesse dagegen "die gesetzte Folge
        ist leer" — etwas anderes.
        """
        block: dict = {"status": self.status}
        if self.entscheider:
            block["entscheider"] = self.entscheider
        if self.kommentar:
            block["kommentar"] = self.kommentar
        if self.entschieden_am is not None:
            block["entschieden_am"] = self.entschieden_am.isoformat()
        if self.approved_potenzial_ids:
            block["approved_potenzial_ids"] = list(self.approved_potenzial_ids)
        if self.nicht_freigegeben:
            block["nicht_freigegeben"] = [
                {"potenzial_id": n.potenzial_id, "begruendung": n.begruendung}
                for n in self.nicht_freigegeben
            ]
        if self.finale_reihenfolge_potenzial_ids:
            block["finale_reihenfolge_potenzial_ids"] = list(
                self.finale_reihenfolge_potenzial_ids
            )
        if self.finale_prozessreihenfolge_kp_ids:
            block["finale_prozessreihenfolge_kp_ids"] = list(
                self.finale_prozessreihenfolge_kp_ids
            )
        if self.abweichungsbegruendung:
            block["abweichungsbegruendung"] = self.abweichungsbegruendung
        return block


# ----------------------------------------------------------------------------
# Prüfung
# ----------------------------------------------------------------------------


def pruefe(
    entscheidung: Gate1Entscheidung,
    *,
    potenzial_ids: list[str],
    kp_ids: list[str],
    gerechnete_reihenfolge: list[str],
    gerechnete_prozessfolge: list[str],
) -> list[str]:
    """Prüft die Entscheidung gegen den Lauf. Gibt die Mängel als Klartext.

    Leere Liste heisst: die Entscheidung darf geschrieben werden. Der Klartext
    geht so an die Oberfläche — wer einen ``400`` bekommt, soll nicht raten
    müssen, welches der elf Potenziale die Begründung vermisst.

    Geprüft wird gegen **diesen Lauf**, nicht nur gegen sich selbst: eine
    Entscheidung über ein Potenzial, das das Paket gar nicht trägt, ist kein
    Formfehler, sondern ein Hinweis, dass die Oberfläche auf einem anderen Stand
    gearbeitet hat als der Server.
    """
    maengel: list[str] = []
    bekannt = set(potenzial_ids)

    if entscheidung.status not in ZUSTAENDE:
        maengel.append(
            f"status muss einer von {', '.join(ZUSTAENDE)} sein, war {entscheidung.status!r}."
        )

    freigegeben = list(entscheidung.approved_potenzial_ids)
    abgelehnt = [n.potenzial_id for n in entscheidung.nicht_freigegeben]

    # --- Bezug auf diesen Lauf ---
    for gruppe, bezeichnung in ((freigegeben, "freigegeben"), (abgelehnt, "nicht freigegeben")):
        for pid in gruppe:
            if pid not in bekannt:
                maengel.append(
                    f"Potenzial {pid} ist als {bezeichnung} gemeldet, gehoert aber nicht zu diesem Lauf."
                )

    doppelt = sorted(set(freigegeben) & set(abgelehnt))
    for pid in doppelt:
        maengel.append(f"Potenzial {pid} ist gleichzeitig freigegeben und nicht freigegeben.")

    for gruppe, bezeichnung in ((freigegeben, "approved_potenzial_ids"),
                                (abgelehnt, "nicht_freigegeben")):
        if len(gruppe) != len(set(gruppe)):
            maengel.append(f"{bezeichnung} enthaelt dieselbe potenzial_id mehrfach.")

    # --- Die Begründungspflicht (#167, Fassung D) ---
    #
    # Sie gilt nur bei 'approved'. Wird der **ganze Lauf** abgelehnt, ist die
    # Begründung eine einzige, und sie gehört in 'kommentar' — elf Mal
    # dasselbe zu schreiben wäre die Zumutung, die die Vorbelegung gerade
    # vermeidet.
    if entscheidung.status == "approved":
        fehlend = sorted(bekannt - set(freigegeben) - set(abgelehnt))
        for pid in fehlend:
            maengel.append(
                f"Potenzial {pid} ist weder freigegeben noch mit Begruendung herausgenommen."
            )
        for n in entscheidung.nicht_freigegeben:
            if len(n.begruendung.strip()) < MINDESTLAENGE_BEGRUENDUNG:
                maengel.append(
                    f"Potenzial {n.potenzial_id} ist nicht freigegeben, aber die Begruendung "
                    f"fehlt oder ist kuerzer als {MINDESTLAENGE_BEGRUENDUNG} Zeichen."
                )
        if not freigegeben:
            maengel.append(
                "Kein einziges Potenzial ist freigegeben — dann ist der Lauf abgelehnt "
                "(status 'rejected'), nicht freigegeben."
            )

    if entscheidung.status == "rejected" and not entscheidung.kommentar.strip():
        maengel.append("Ein abgelehnter Lauf braucht einen Kommentar, der die Ablehnung traegt.")

    # --- Die gesetzten Reihenfolgen ---
    #
    # Sie sind Permutationen, keine Teilmengen: die Liste trägt auch die
    # herausgenommenen Potenziale, sonst liesse sich nach einer Ablehnung nicht
    # mehr sagen, wo das Potenzial gestanden hätte.
    folge = list(entscheidung.finale_reihenfolge_potenzial_ids)
    if folge and sorted(folge) != sorted(potenzial_ids):
        maengel.append(
            "finale_reihenfolge_potenzial_ids muss genau die Potenziale dieses Laufs "
            f"enthalten ({len(potenzial_ids)} Stueck), jedes genau einmal."
        )

    prozessfolge = list(entscheidung.finale_prozessreihenfolge_kp_ids)
    if prozessfolge and sorted(prozessfolge) != sorted(kp_ids):
        maengel.append(
            "finale_prozessreihenfolge_kp_ids muss genau die Kernprozesse dieses Laufs "
            f"enthalten ({len(kp_ids)} Stueck), jeden genau einmal."
        )

    # --- Die Abweichungsbegründung ---
    #
    # "Pflicht, sobald eine der beiden finalen Reihenfolgen vom gerechneten Rang
    # abweicht" (priorisierung.schema.json). Gleiche Liste in gleicher Folge ist
    # keine Abweichung — wer den Vorschlag bestätigt, schuldet keine Begründung.
    weicht_ab = (folge and folge != gerechnete_reihenfolge) or (
        prozessfolge and prozessfolge != gerechnete_prozessfolge
    )
    if weicht_ab and len(entscheidung.abweichungsbegruendung.strip()) < MINDESTLAENGE_BEGRUENDUNG:
        maengel.append(
            "Die Reihenfolge weicht vom gerechneten Rang ab — dann ist "
            "abweichungsbegruendung Pflicht."
        )

    return maengel


# ----------------------------------------------------------------------------
# Ablage
# ----------------------------------------------------------------------------


class Gate1Buch(Protocol):
    """Was die Oberfläche von ihrer Ablage braucht — mehr nicht."""

    def merken(self, entscheidung: Gate1Entscheidung) -> None:
        """Legt die Entscheidung über den Lauf ``(paket_id, fassung)`` ab.

        Solange sie ``pending`` ist, ersetzt eine neue die alte. Ist sie
        ``approved`` oder ``rejected``, wirft jedes weitere ``merken``
        ``Gate1Konflikt``. Die Geschichte des Pendelns trägt die **Fassung**
        (ADR-007 · BC2, 2.3), nicht ein Überschreiben.
        """
        ...

    def lesen(self, paket_id: str, fassung: int = 1) -> Gate1Entscheidung | None:
        """Die Entscheidung zu diesem Lauf, oder ``None``."""
        ...


@dataclass
class SpeicherGate1Buch:
    """Doppelgänger im Arbeitsspeicher — für die Tests und die Vorschau.

    Ahmt die Endgültigkeit nach. Hängt ein ``SpeicherErgebnisbuch`` daran,
    schließt er dort den Lauf ab, wie es ``PostgresGate1Buch`` in derselben
    Transaktion tut — sonst wüsste das Ergebnisbuch nicht, dass nach einem
    Reject eine neue Fassung zulässig ist.
    """

    abgelegt: dict[tuple[str, int], Gate1Entscheidung] = field(default_factory=dict)
    ergebnisse: SpeicherErgebnisbuch | None = None

    def merken(self, entscheidung: Gate1Entscheidung) -> None:
        schluessel = (entscheidung.paket_id, entscheidung.fassung)
        bisher = self.abgelegt.get(schluessel)
        if bisher is not None and bisher.status in ENDGUELTIG:
            raise Gate1Konflikt(entscheidung.paket_id, entscheidung.fassung, bisher.status)
        self.abgelegt[schluessel] = entscheidung
        if self.ergebnisse is not None:
            self.ergebnisse.abschliessen(
                entscheidung.paket_id, entscheidung.fassung, entscheidung.status
            )

    def lesen(self, paket_id: str, fassung: int = 1) -> Gate1Entscheidung | None:
        return self.abgelegt.get((paket_id, fassung))


# ----------------------------------------------------------------------------
# Postgres
# ----------------------------------------------------------------------------

_SQL_LAUF = """
SELECT priorisierung_id::text, company_id, zustand
  FROM bc2.lauf
 WHERE paket_id = %(paket_id)s AND fassung = %(fassung)s
"""

# Schritt 1 einer Entscheidung: die Zeile sichern — als ``pending``. Die
# Bedingung im DO UPDATE ist der Konflikt: steht der Lauf schon auf
# approved/rejected, ändert die Anweisung null Zeilen. Zwei gleichzeitige
# Schreiber: der zweite wartet auf die Zeilensperre des ersten und sieht danach
# dessen endgültigen Zustand.
_SQL_SICHERN = """
INSERT INTO bc2.gate1 (priorisierung_id, status)
VALUES (%(priorisierung_id)s, 'pending')
ON CONFLICT (priorisierung_id) DO UPDATE
   SET geschrieben_am = now()
 WHERE bc2.gate1.status = 'pending'
"""

_SQL_STATUS = "SELECT status FROM bc2.gate1 WHERE priorisierung_id = %(priorisierung_id)s"

_SQL_LEEREN = """
DELETE FROM bc2.gate1_potenzial WHERE priorisierung_id = %(priorisierung_id)s;
DELETE FROM bc2.gate1_prozess   WHERE priorisierung_id = %(priorisierung_id)s;
"""

_SQL_POTENZIAL = """
INSERT INTO bc2.gate1_potenzial (priorisierung_id, potenzial_id, freigegeben,
                                 begruendung, finaler_rang)
VALUES (%(priorisierung_id)s, %(potenzial_id)s, %(freigegeben)s,
        %(begruendung)s, %(finaler_rang)s)
"""

_SQL_PROZESS = """
INSERT INTO bc2.gate1_prozess (priorisierung_id, kp_id, finaler_rang)
VALUES (%(priorisierung_id)s, %(kp_id)s, %(finaler_rang)s)
"""

# Schritt 3: erst jetzt der eigentliche Zustand. Die Einzelzeilen sind schon
# geschrieben — andersherum wiese der Trigger ``gate1_endgueltig`` sie ab,
# weil der Kopf dann schon endgültig wäre.
_SQL_ENTSCHEIDEN = """
UPDATE bc2.gate1
   SET status = %(status)s, entscheider = %(entscheider)s, kommentar = %(kommentar)s,
       abweichungsbegruendung = %(abweichungsbegruendung)s,
       entschieden_am = %(entschieden_am)s, geschrieben_am = now()
 WHERE priorisierung_id = %(priorisierung_id)s AND status = 'pending'
"""

# Der Lauf ist damit nicht mehr offen — erst danach lässt der partielle Index
# eine neue Fassung zu. Das Ergebnisdokument bleibt unberührt.
_SQL_ABSCHLIESSEN = """
UPDATE bc2.lauf SET zustand = 'abgeschlossen', abgeschlossen_am = now()
 WHERE priorisierung_id = %(priorisierung_id)s AND zustand = 'offen'
"""

_SQL_LESEN = """
SELECT g.status, g.entscheider, g.kommentar, g.abweichungsbegruendung, g.entschieden_am
  FROM bc2.gate1 g
 WHERE g.priorisierung_id = %(priorisierung_id)s
"""

_SQL_LESEN_POTENZIALE = """
SELECT potenzial_id, freigegeben, begruendung, finaler_rang
  FROM bc2.gate1_potenzial
 WHERE priorisierung_id = %(priorisierung_id)s
 ORDER BY finaler_rang NULLS LAST, potenzial_id
"""

_SQL_LESEN_PROZESSE = """
SELECT kp_id FROM bc2.gate1_prozess
 WHERE priorisierung_id = %(priorisierung_id)s
 ORDER BY finaler_rang
"""


def zeilen_aus(entscheidung: Gate1Entscheidung) -> tuple[list[dict], list[dict]]:
    """Zerlegt die Entscheidung in Rang-Zeilen (ADR-008 · BC2, 2.3).

    Je Potenzial eine Zeile, sobald es in irgendeiner der drei Angaben
    vorkommt: freigegeben, herausgenommen, oder in der gesetzten Folge.
    ``finaler_rang`` bleibt leer, wenn keine Folge gesetzt ist — das heisst im
    Vertrag „es gilt der gerechnete Rang“, und eine Zahl hiesse etwas anderes.
    """
    rang = {pid: i for i, pid in enumerate(entscheidung.finale_reihenfolge_potenzial_ids, 1)}
    frei = set(entscheidung.approved_potenzial_ids)
    grund = {n.potenzial_id: n.begruendung for n in entscheidung.nicht_freigegeben}

    alle = list(dict.fromkeys(
        [*entscheidung.approved_potenzial_ids, *grund, *entscheidung.finale_reihenfolge_potenzial_ids]
    ))
    potenziale = [
        {
            "potenzial_id": pid,
            "freigegeben": True if pid in frei else False if pid in grund else None,
            "begruendung": grund.get(pid),
            "finaler_rang": rang.get(pid),
        }
        for pid in alle
    ]
    prozesse = [
        {"kp_id": kp, "finaler_rang": i}
        for i, kp in enumerate(entscheidung.finale_prozessreihenfolge_kp_ids, 1)
    ]
    return potenziale, prozesse


class PostgresGate1Buch:
    """Gate 1 in Schema ``bc2``. Verbindet je Vorgang neu, wie die anderen Ablagen."""

    def __init__(self, dsn: str | None = None) -> None:
        import os

        self._dsn = dsn or (os.environ.get("DATABASE_URL") or "").strip()
        if not self._dsn:
            raise RuntimeError(
                "DATABASE_URL ist nicht gesetzt. Die Zugangsdaten gehoeren "
                "ausschliesslich in eine Umgebungsvariable (ADR-003)."
            )

    def _verbindung(self):
        import psycopg2

        return psycopg2.connect(self._dsn)

    def merken(self, entscheidung: Gate1Entscheidung) -> None:
        import psycopg2.extras

        potenziale, prozesse = zeilen_aus(entscheidung)
        with self._verbindung() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(
                _SQL_LAUF, {"paket_id": entscheidung.paket_id, "fassung": entscheidung.fassung}
            )
            lauf = cur.fetchone()
            if lauf is None or lauf["zustand"] not in ("offen", "abgeschlossen"):
                raise LaufUnbekannt(f"{entscheidung.paket_id} f{entscheidung.fassung}")
            pid = {"priorisierung_id": lauf["priorisierung_id"]}

            cur.execute(_SQL_SICHERN, pid)
            if cur.rowcount != 1:
                cur.execute(_SQL_STATUS, pid)
                bisher = cur.fetchone()["status"]
                raise Gate1Konflikt(entscheidung.paket_id, entscheidung.fassung, bisher)

            cur.execute(_SQL_LEEREN, pid)
            for z in potenziale:
                cur.execute(_SQL_POTENZIAL, {**pid, **z})
            for z in prozesse:
                cur.execute(_SQL_PROZESS, {**pid, **z})

            cur.execute(
                _SQL_ENTSCHEIDEN,
                {
                    **pid,
                    "status": entscheidung.status,
                    "entscheider": entscheidung.entscheider or None,
                    "kommentar": entscheidung.kommentar or None,
                    "abweichungsbegruendung": entscheidung.abweichungsbegruendung or None,
                    "entschieden_am": entscheidung.entschieden_am,
                },
            )
            if entscheidung.status in ENDGUELTIG:
                cur.execute(_SQL_ABSCHLIESSEN, pid)

    def lesen(self, paket_id: str, fassung: int = 1) -> Gate1Entscheidung | None:
        import psycopg2.extras

        with self._verbindung() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(_SQL_LAUF, {"paket_id": paket_id, "fassung": fassung})
            lauf = cur.fetchone()
            if lauf is None:
                return None
            pid = {"priorisierung_id": lauf["priorisierung_id"]}
            cur.execute(_SQL_LESEN, pid)
            kopf = cur.fetchone()
            if kopf is None:
                return None
            cur.execute(_SQL_LESEN_POTENZIALE, pid)
            potenziale = cur.fetchall()
            cur.execute(_SQL_LESEN_PROZESSE, pid)
            prozesse = [z["kp_id"] for z in cur.fetchall()]

        gesetzt = [z for z in potenziale if z["finaler_rang"] is not None]
        return Gate1Entscheidung(
            paket_id=paket_id,
            company_id=lauf["company_id"],
            status=kopf["status"],
            fassung=fassung,
            approved_potenzial_ids=tuple(
                z["potenzial_id"] for z in potenziale if z["freigegeben"] is True
            ),
            nicht_freigegeben=tuple(
                NichtFreigegeben(z["potenzial_id"], z["begruendung"] or "")
                for z in potenziale
                if z["freigegeben"] is False
            ),
            finale_reihenfolge_potenzial_ids=tuple(
                z["potenzial_id"] for z in sorted(gesetzt, key=lambda z: z["finaler_rang"])
            ),
            finale_prozessreihenfolge_kp_ids=tuple(prozesse),
            abweichungsbegruendung=kopf["abweichungsbegruendung"] or "",
            entscheider=kopf["entscheider"] or "",
            kommentar=kopf["kommentar"] or "",
            entschieden_am=kopf["entschieden_am"],
        )


def jetzt() -> datetime:
    """Der Entscheidungszeitpunkt, immer mit Zeitzone.

    Eine eigene Funktion, damit die Tests sie ersetzen können und der Zeitpunkt
    nicht an drei Stellen verschieden entsteht.
    """
    return datetime.now(timezone.utc)
