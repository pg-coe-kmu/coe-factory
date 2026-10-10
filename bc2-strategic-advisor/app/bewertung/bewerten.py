"""
BC2 · Der Bewertungsschritt — von erkannten Potenzialen zu vollständigen Eingängen.

Zwischen Erkennung (#248) und Rechenkern (#238). Er sieht das **geschnittene**
Potenzial und läuft darum nach der Erkennung, nie vorher (ADR-006 · BC2, §6).
Was er liefert, ist genau das, was einem ``modell.Potenzialeingang`` bis #288
fehlte:

===========================================  ===================================
Urteilsstelle (ADR-006, 2.0 und Nachtrag 7)  wo
===========================================  ===================================
Lösungsansatz-Klasse                         Erkennung — hier **unverändert** (6.4)
Lage im Korridor                             hier
Die fünf Nutzwert-Kategorien                 hier
Begründetes Überschreiben der Komplexität    hier
Umsetzungsaufwand in Personentagen           hier (Nachtrag 7)
===========================================  ===================================

Dazu kommen die **Messungen** je berührtem Teilprozess aus BC1s Profilen — sie
urteilt niemand, sie werden nur durchgereicht.

**Ein Aufruf je Lauf** (6.2): ein Urteiler, ein Maßstab — aber **dreimal**
gestellt, und je Feld gilt der Median (6.7, #299). Ein einzelner Aufruf hielt
die Stabilitätsabnahme aus #288 nicht: jeder trägt eine eigene Verschiebung,
die in der Rangfolge landet. Gemessen wird mit ``tools/bewertung_messen.py``,
zusammengeführt in :mod:`~bewertung.zusammenfuehren`.

**Die Kennung entsteht hier.** Die Erkennung zählt ``P1``, ``P2`` …; der
Vertrag verlangt eine UUID je Potenzial, und jede Rechnung schneidet neu
(ADR-008 · BC2, 4.2). Die Kennung wird darum je Lauf vergeben und **nicht** aus
Paket und Erkennungsnummer abgeleitet: ``P1`` ist in zwei Rechnungen nicht
dasselbe Potenzial, und eine gleiche UUID behauptete das (ADR-002: eine
Kennung, ein Inhalt). Die Zuordnung zur Erkennungsnummer bleibt in
:attr:`Bewertung.kennungen`, damit ein Mensch den Weg zurückfindet.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from erkennung.bestand import Paketbestand
from erkennung.erkennen import Aufrufprotokoll, Erkennung
from erkennung.modellruf import Modellruf
from modell import (
    STANDARD,
    Nutzwert,
    Nutzwertkategorie,
    Parameter,
    Potenzialeingang,
    gemessene_komplexitaet,
)

from .anweisung import ANTWORTSCHEMA, baue_frage
from .nutzlast import baue_nutzlast, messungen_je_teilprozess
from .pruefen import KATEGORIEN, Erwartung, pruefe_bewertung
from .zusammenfuehren import fuehre_zusammen

#: Wie oft ein Lauf geurteilt wird (#299, ADR-006 · BC2, 6.7). Eine Setzung:
#: an zehn Urteilen hielten Mediane aus drei die Grenze in genau 95 % der Paare,
#: aus fünf in allen. Fällt die Wiederholung der Messung am ersten echten Lauf
#: (#206) unter 95 %, wird hier 5 eingetragen.
URTEILE = 3

__all__ = ["Bewertung", "BewertungAbgebrochen", "baue_eingaenge", "bewerte", "erwartungen"]


class BewertungAbgebrochen(RuntimeError):
    """Der Lauf wurde angehalten, weil die Bewertung auch in der Wiederholung brach.

    Wie :class:`erkennung.ErkennungAbgebrochen`: die Gründe und die rohe
    Antwort reisen mit, damit ein Mensch nachsehen kann, ohne den Aufruf zu
    wiederholen.
    """

    def __init__(self, gruende: tuple[str, ...], roh: str = "") -> None:
        super().__init__("Bewertung angehalten: " + "; ".join(gruende))
        self.gruende = gruende
        self.roh = roh


@dataclass(frozen=True)
class Bewertung:
    """Das Ergebnis des Bewertungsschritts für einen Lauf."""

    eingaenge: tuple[Potenzialeingang, ...]
    #: Erkennungsnummer → vergebene ``potenzial_id``.
    kennungen: dict[str, str] = field(default_factory=dict)
    #: ``None``, wenn es nichts zu bewerten gab und darum nicht gefragt wurde.
    aufruf: Aufrufprotokoll | None = None
    #: Die geprüfte Antwort — bei mehreren Urteilen die zusammengeführte.
    antwort: dict[str, Any] | None = None
    #: Jedes geprüfte Einzelurteil, in Aufrufreihenfolge — für die Stabilitätsmessung.
    urteile: tuple[dict[str, Any], ...] = ()
    #: Potenzial (Erkennungsnummer) → Feld → (kleinster, größter) Wert über die Urteile.
    streuung: dict[str, dict[str, tuple[float, float]]] = field(default_factory=dict)


def _nutzwert(roh: dict[str, Any]) -> Nutzwert:
    return Nutzwert(
        **{
            k: Nutzwertkategorie(int(roh[k]["wert"]), str(roh[k]["begruendung"]).strip())
            for k in KATEGORIEN
        }
    )


def _text(wert: Any) -> str | None:
    if wert is None:
        return None
    t = str(wert).strip()
    return t or None


def erwartungen(
    erkennung: Erkennung, bestand: Paketbestand, parameter: Parameter = STANDARD
) -> dict[str, Erwartung]:
    """Was der Wächter je erkanntem Potenzial wissen muss: Korridor und gemessene Komplexität."""
    messungen = messungen_je_teilprozess(bestand)
    erwartet: dict[str, Erwartung] = {}
    for p in erkennung.potenziale:
        lo, hi = parameter.korridore[p.klasse]
        gemessen = gemessene_komplexitaet(
            p.beruehrte_teilprozess_ids,
            tuple(messungen[t] for t in p.beruehrte_teilprozess_ids if t in messungen),
        )
        erwartet[p.potenzial_id] = Erwartung(
            korridor_pct=(round(lo * 100, 6), round(hi * 100, 6)),
            gemessene_komplexitaet=None if gemessen is None else gemessen[0],
        )
    return erwartet


def baue_eingaenge(
    erkennung: Erkennung,
    bestand: Paketbestand,
    antwort: dict[str, Any],
    kennung: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> tuple[tuple[Potenzialeingang, ...], dict[str, str]]:
    """Macht aus einer geprüften Antwort die Eingänge des Rechenkerns.

    :returns: die Eingänge und die Zuordnung Erkennungsnummer → ``potenzial_id``.
    """
    messungen = messungen_je_teilprozess(bestand)
    je_id = {str(b["id"]): b for b in antwort["bewertungen"]}

    eingaenge: list[Potenzialeingang] = []
    kennungen: dict[str, str] = {}
    for p in erkennung.potenziale:
        b = je_id[p.potenzial_id]
        pid = kennung()
        kennungen[p.potenzial_id] = pid
        k = b.get("komplexitaet_ueberschrieben")
        eingaenge.append(
            Potenzialeingang(
                potenzial_id=pid,
                titel=p.titel,
                kp_id=p.kernprozess_id,
                betroffene_teilprozess_ids=p.beruehrte_teilprozess_ids,
                klasse=p.klasse,  # type: ignore[arg-type]  # 6.4: die der Erkennung
                automatisierungsgrad_begruendung=str(b["korridor_begruendung"]).strip(),
                nutzwert=_nutzwert(b["nutzwert"]),
                messungen=tuple(
                    messungen[t] for t in p.beruehrte_teilprozess_ids if t in messungen
                ),
                angesetzt_min_pct=float(b["angesetzt_min_pct"]),
                angesetzt_max_pct=float(b["angesetzt_max_pct"]),
                aufwand_schaetzung_pt=float(b["aufwand_schaetzung_pt"]),
                aufwand_begruendung=_text(b.get("aufwand_begruendung")),
                komplexitaet_ueberschrieben=None if k is None else int(k),
                komplexitaet_begruendung=_text(b.get("komplexitaet_begruendung")),
                klassenzweifel=_text(b.get("klassenzweifel")),
            )
        )
    return tuple(eingaenge), kennungen


def bewerte(
    erkennung: Erkennung,
    bestand: Paketbestand,
    modell: Modellruf,
    *,
    parameter: Parameter = STANDARD,
    urteile: int = URTEILE,
    gleichzeitig: int | None = None,
    wiederholungen: int = 1,
    kennung: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> Bewertung:
    """Bewertet alle Potenziale eines Laufs — *n*-mal in je **einem** Aufruf.

    :param urteile: wie oft der ganze Lauf geurteilt wird; je Feld gilt dann
        der Median (#299). Ungerade.
    :param gleichzeitig: wie viele Urteile zugleich laufen; Voreinstellung alle.
        ``1`` stellt sie nacheinander — für Doppelgänger, die in fester
        Reihenfolge antworten.
    :param wiederholungen: wie oft ein verworfener Aufruf wiederholt wird,
        bevor der Lauf anhält (6.5: einmal). Gilt je Urteil.
    :param kennung: vergibt die ``potenzial_id``. Für Tests austauschbar.
    :raises BewertungAbgebrochen: wenn der Wächter auch die Wiederholung eines
        Urteils verwirft. Aus den übrigen wird nicht weitergerechnet — ein
        Median aus einer geraden Zahl ist keiner (Q8 in #299).
    """
    if urteile < 1 or urteile % 2 == 0:
        raise ValueError(f"urteile muss ungerade und positiv sein, nicht {urteile}.")
    if not erkennung.potenziale:
        # Ohne Potenzial keine Frage — der Kunde zahlte sonst fuer einen Aufruf
        # ohne Gegenstand. Dieselbe Regel wie beim Packen der Erkennung.
        return Bewertung(eingaenge=())

    messungen = messungen_je_teilprozess(bestand)
    nutzlast = baue_nutzlast(erkennung, bestand, parameter, messungen)
    erwartet = erwartungen(erkennung, bestand, parameter)

    angehalten = threading.Event()

    def ein_urteil(_: int) -> tuple[dict[str, Any], int, list[str], str, str] | None:
        if angehalten.is_set():
            return None  # ein anderes Urteil hat den Lauf schon angehalten
        gruende: list[str] = []
        verworfen: list[str] = []
        versuch = 0
        while True:
            versuch += 1
            frage = baue_frage(nutzlast, gruende or None)
            antwort = modell.frage(frage, schema=ANTWORTSCHEMA)
            gruende = list(pruefe_bewertung(antwort.ergebnis, erwartet))
            if antwort.lesefehler:
                gruende.append(antwort.lesefehler)
            if not gruende:
                break
            verworfen.extend(gruende)
            if versuch > wiederholungen:
                angehalten.set()
                raise BewertungAbgebrochen(tuple(gruende), antwort.roh)
        assert antwort.ergebnis is not None
        return antwort.ergebnis, versuch, verworfen, frage, antwort.modell

    # Parallel gestellt: der Median kennt keine Reihenfolge, und die
    # Begründung kommt aus dem ersten passenden Urteil in *Aufruf*reihenfolge
    # — ``map`` hält sie, gleich wann ein Aufruf zurückkommt. Bricht ein
    # Urteil, bricht der Lauf (Q8 in #299).
    with ThreadPoolExecutor(max_workers=gleichzeitig or urteile) as pool:
        roh = list(pool.map(ein_urteil, range(urteile)))
    ergebnisse = [e for e in roh if e is not None]

    geprueft = [e[0] for e in ergebnisse]
    versuche = sum(e[1] for e in ergebnisse)
    verworfen = [g for e in ergebnisse for g in e[2]]
    frage, modellname = ergebnisse[0][3], ergebnisse[0][4]

    zusammen = fuehre_zusammen(geprueft, erwartet)
    eingaenge, kennungen = baue_eingaenge(erkennung, bestand, zusammen.antwort, kennung)

    return Bewertung(
        eingaenge=eingaenge,
        kennungen=kennungen,
        aufruf=Aufrufprotokoll(
            name=erkennung.paket_id,
            schnitt="Bewertung" if urteile == 1 else f"Bewertung, Median aus {urteile}",
            zeichen=len(frage),
            modell=modellname,
            versuche=versuche,
            verworfen=tuple(verworfen),
        ),
        antwort=zusammen.antwort,
        urteile=tuple(geprueft),
        streuung=zusammen.streuung,
    )
