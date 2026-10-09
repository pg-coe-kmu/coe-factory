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

**Warum hier keine Postgres-Umsetzung steht.** Die Entscheidung gehört nach
Schema ``bc2``, und dessen Tabellenentwurf ist noch nicht getroffen (Nebel der
Karte #158, herausgehoben als eigenes Ticket beim Bau von #243): er trägt mehr
als Gate 1 — den Lauf selbst, die Konzepte, die **abgelehnten** Läufe, für die
nach ADR-007 nichts an BC3 geht, und den Rückkanal an BC0. Eine Tabelle daraus
vorwegzunehmen hiesse, sie zu schneiden, ohne den Rest zu kennen.

Die Naht ist deshalb dieselbe wie in ``eingang.py``: ein Protokoll, ein
Doppelgänger für die Tests, und die Umsetzung gegen die echte Datenbank kommt,
wenn das Schema steht. Der Unterschied zu ``eingang.py`` ist ehrlich zu
benennen: dort **gibt** es die Postgres-Umsetzung, hier noch nicht. Bis dahin
überlebt eine Entscheidung den Neustart nicht.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

# Der Vertrag verlangt ``minLength: 5`` für eine Begründung. Fünf Zeichen sind
# keine gute Begründung, aber sie sind die Grenze, unterhalb derer sicher keine
# steht ("ok", "-", "nein"). Mehr zu verlangen wäre eine Qualitätsaussage, die
# eine Zeichenzahl nicht treffen kann.
MINDESTLAENGE_BEGRUENDUNG = 5

ZUSTAENDE = ("pending", "approved", "rejected")


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
        """Legt die Entscheidung ab; eine frühere zum selben Paket wird ersetzt.

        Ersetzen und nicht anhängen: Gate 1 ist **ein** Zustand je Lauf. Die
        Geschichte des Pendelns trägt nach ADR-007 die **Fassung** — ein
        erneuter Lauf erzeugt eine neue, die alte bleibt abrufbar.
        """
        ...

    def lesen(self, paket_id: str) -> Gate1Entscheidung | None:
        """Die Entscheidung zu diesem Paket, oder ``None``."""
        ...


@dataclass
class SpeicherGate1Buch:
    """Doppelgänger im Arbeitsspeicher.

    **Er ist derzeit die einzige Umsetzung**, und das ist ein bekannter Mangel,
    kein Versehen: die Postgres-Umsetzung wartet auf den Tabellenentwurf für
    Schema ``bc2``. Eine Entscheidung überlebt den Neustart des Dienstes nicht.
    Die Oberfläche sagt das ausdrücklich an, statt Dauerhaftigkeit vorzutäuschen
    (``GET /api/oberflaeche/zustand`` → ``ablage: "arbeitsspeicher"``).
    """

    abgelegt: dict[str, Gate1Entscheidung] = field(default_factory=dict)

    def merken(self, entscheidung: Gate1Entscheidung) -> None:
        self.abgelegt[entscheidung.paket_id] = entscheidung

    def lesen(self, paket_id: str) -> Gate1Entscheidung | None:
        return self.abgelegt.get(paket_id)


def jetzt() -> datetime:
    """Der Entscheidungszeitpunkt, immer mit Zeitzone.

    Eine eigene Funktion, damit die Tests sie ersetzen können und der Zeitpunkt
    nicht an drei Stellen verschieden entsteht.
    """
    return datetime.now(timezone.utc)
