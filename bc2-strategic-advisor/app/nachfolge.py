"""
BC2 · Nachfolger über Pakete hinweg — Kandidaten, Ausgänge, Nachprüfung.

ADR-009 · BC2, gebaut in #295. Ein neues Paket trägt nur die neu
freigegebenen Teilprozesse; berührt es einen, zu dem BC3 schon Potenziale hat,
muss der Lauf sagen, was aus jedem davon wird (§2.3):

============== ================================= ===============================
Ausgang        Bedeutung                         im Vertrag
============== ================================= ===============================
fortgeschrieben ein neues Potenzial ist dasselbe  ``ersetzt_potenzial_ids`` des
               Vorhaben, neu bewertet            Nachfolgers
gestrichen     das Vorhaben fällt weg            ``gestrichene_potenziale[]``
unveraendert   aus diesem Paket nicht zu         nichts
               beurteilen
============== ================================= ===============================

Die Arbeitsteilung aus §2.5: **Python** bestimmt die Kandidaten (``ablage.py``),
**das Modell** ordnet zu (``erkennung``), **Python** prüft nach (hier), **der
Mensch** gibt frei. Die Nachprüfung läuft zweimal mit derselben Funktion: im
Wächter der Erkennung, damit ein Verstoß das Modell noch einmal fragen lässt,
und vor dem Ablegen, damit keine Quelle eine Kette in Schema ``bc2`` schreibt,
die hier nicht durchginge.

Rein und ohne Abhängigkeiten auf Datenbank oder Modell.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

__all__ = [
    "AUSGAENGE",
    "Ausgang",
    "Kandidat",
    "Nachfolge",
    "pruefe_ausgaenge",
]

#: Die drei Ausgänge aus ADR-009 · BC2 §2.3, wörtlich.
AUSGAENGE = ("fortgeschrieben", "gestrichen", "unveraendert")


@dataclass(frozen=True)
class Kandidat:
    """Ein schon geliefertes Potenzial, das einen Teilprozess des Pakets berührt.

    Nur das Qualitative (§2.5): wer mit Zahlen in die Nutzlast geht, lädt das
    Modell zum Rechnen ein, und genau dort brach das Rechenverbot in #194.
    """

    potenzial_id: str
    paket_id: str
    kp_id: str
    titel: str
    klasse: str
    teilprozess_ids: tuple[str, ...]
    beschreibung: str | None = None

    def ausserhalb(self, paket_teilprozesse: Iterable[str]) -> tuple[str, ...]:
        """Die Teilprozesse des Kandidaten, die dieses Paket **nicht** trägt."""
        paket = set(paket_teilprozesse)
        return tuple(t for t in self.teilprozess_ids if t not in paket)


@dataclass(frozen=True)
class Ausgang:
    """Was ein Lauf mit **einem** Kandidaten macht."""

    kandidat_id: str
    art: str
    #: Das neue Potenzial, das ihn fortschreibt — nur bei ``fortgeschrieben``.
    nachfolger: str | None = None
    #: Pflicht bei ``gestrichen``: sie geht an BC3 und BC4.
    begruendung: str | None = None


@dataclass(frozen=True)
class Nachfolge:
    """Wie ein Lauf mit seinen Kandidaten verfahren ist.

    Eine Quelle, die **keine** ``Nachfolge`` liefert, hat die Kandidaten nicht
    beurteilt — dann bricht die Ablage ab, statt eine leere Kette zu schreiben
    (Auflage §4.3). Eine leere ``Nachfolge`` heißt dagegen: es gab keine.
    """

    kandidaten: tuple[Kandidat, ...] = ()
    ausgaenge: tuple[Ausgang, ...] = ()

    def vorgaenger(self) -> dict[str, str]:
        """Neues Potenzial → das gelieferte, das es fortschreibt."""
        return {
            a.nachfolger: a.kandidat_id
            for a in self.ausgaenge
            if a.art == "fortgeschrieben" and a.nachfolger
        }

    def gestrichen(self) -> list[dict]:
        """Die Streichliste in Vertragsform (``priorisierung.gestrichene_potenziale``)."""
        je_id = {k.potenzial_id: k for k in self.kandidaten}
        return [
            {
                "potenzial_id": a.kandidat_id,
                "kp_id": je_id[a.kandidat_id].kp_id,
                "begruendung": (a.begruendung or "").strip(),
            }
            for a in self.ausgaenge
            if a.art == "gestrichen"
        ]

    def umbenannt(self, kennungen: Mapping[str, str]) -> "Nachfolge":
        """Dieselben Ausgänge mit anderen Nachfolger-Kennungen.

        Die Erkennung zählt ``P1``, ``P2`` …; die UUID vergibt erst der
        Bewertungsschritt. Ein Nachfolger ohne Eintrag in ``kennungen`` bleibt
        stehen und fällt danach in der Nachprüfung auf.
        """
        return Nachfolge(
            kandidaten=self.kandidaten,
            ausgaenge=tuple(
                Ausgang(
                    kandidat_id=a.kandidat_id,
                    art=a.art,
                    nachfolger=kennungen.get(a.nachfolger, a.nachfolger) if a.nachfolger else None,
                    begruendung=a.begruendung,
                )
                for a in self.ausgaenge
            ),
        )


def pruefe_ausgaenge(
    kandidaten: Iterable[Kandidat],
    ausgaenge: Iterable[Ausgang],
    potenziale: Mapping[str, Mapping[str, Any]],
    paket_teilprozesse: Iterable[str],
) -> list[str]:
    """Die Nachprüfung aus ADR-009 · BC2 §2.5, Schritt 3. Leer heißt: hält.

    :param potenziale: die neuen Potenziale des Laufs, ``id → {"klasse", "kp_id"}``.
    :param paket_teilprozesse: alle Teilprozesse des Pakets, nicht nur die
        geschnittenen — „unverändert“ hängt daran, was das Paket **trägt**.
    """
    kandidaten = list(kandidaten)
    je_id = {k.potenzial_id: k for k in kandidaten}
    paket = set(paket_teilprozesse)
    verstoesse: list[str] = []

    gesehen: dict[str, int] = {}
    nachfolger_von: dict[str, str] = {}
    for a in ausgaenge:
        k = je_id.get(a.kandidat_id)
        if k is None:
            verstoesse.append(f"{a.kandidat_id} ist kein Kandidat dieses Laufs")
            continue
        gesehen[a.kandidat_id] = gesehen.get(a.kandidat_id, 0) + 1
        if a.art not in AUSGAENGE:
            verstoesse.append(
                f"{a.kandidat_id}: Ausgang {a.art!r} gibt es nicht "
                f"(nur {', '.join(AUSGAENGE)})"
            )
            continue

        if a.art == "fortgeschrieben":
            neu = potenziale.get(a.nachfolger or "")
            if neu is None:
                verstoesse.append(
                    f"{a.kandidat_id} fortgeschrieben, aber der Nachfolger "
                    f"{a.nachfolger!r} ist kein Potenzial dieses Laufs"
                )
                continue
            if a.nachfolger in nachfolger_von:
                verstoesse.append(
                    f"{a.nachfolger} schreibt zwei Kandidaten fort "
                    f"({nachfolger_von[a.nachfolger]}, {a.kandidat_id}) — nur 1:1, "
                    "eine Zusammenlegung macht ein neues Potenzial"
                )
            nachfolger_von[a.nachfolger] = a.kandidat_id
            if neu.get("klasse") != k.klasse:
                verstoesse.append(
                    f"{a.nachfolger} schreibt {a.kandidat_id} fort, aber mit Loesungsklasse "
                    f"{neu.get('klasse')!r} statt {k.klasse!r} — dann ist es ein neues "
                    "Potenzial, und der Kandidat ist gestrichen"
                )
            if neu.get("kp_id") != k.kp_id:
                verstoesse.append(
                    f"{a.nachfolger} liegt in {neu.get('kp_id')}, sein Vorgaenger "
                    f"{a.kandidat_id} in {k.kp_id}"
                )
        elif a.art == "gestrichen":
            if not (a.begruendung or "").strip():
                verstoesse.append(f"{a.kandidat_id} gestrichen ohne Begruendung")
        elif not k.ausserhalb(paket):
            verstoesse.append(
                f"{a.kandidat_id} als unveraendert gemeldet, liegt aber ganz in diesem "
                "Paket — er wurde vollstaendig neu gesehen: fortschreiben oder streichen"
            )

    for k in kandidaten:
        anzahl = gesehen.get(k.potenzial_id, 0)
        if anzahl == 0:
            verstoesse.append(f"{k.potenzial_id} ({k.titel}) hat keinen Ausgang")
        elif anzahl > 1:
            verstoesse.append(f"{k.potenzial_id} hat {anzahl} Ausgaenge statt einem")
    return verstoesse
