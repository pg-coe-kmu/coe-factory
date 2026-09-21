"""
BC2 · Die Nutzlast des Erkennungsschritts — Schnitt C, entdoppelt.

#194 hat den Schnitt entschieden: **ein Aufruf je Paket**, alle freigegebenen
Teilprozesse nach Kernprozess gruppiert in einer Nutzlast. Dieses Modul baut
sie und setzt dabei zwei der vier Auflagen aus #248 um.

Auflage 2 — Kernprozess-Text einmal stellen
-------------------------------------------

``tools``, ``medienbrueche``, ``schnittstellen`` und ``api`` sind bei **10 von
10** Kernprozessen über alle Teilprozesse wortgleich, und die Bitkom-Belegtexte
ebenso: die *Stufen* unterscheiden sich, ihre *Begründung* nicht. Der Aufruf für
„Vertragsabschluss" las damit den Medienbruch von „Lead erfassen". Was für alle
Geschwister gilt, wird deshalb **einmal am Kernprozess** gestellt.

Gemessen am 21.09.2026 beim Bau:

===================================================  ==================
Nutzlast                                             Zeichen
===================================================  ==================
Prototyp-Paket, 16 Teilprozesse, wie in #194 gebaut  80.431
Ganzer NoroAI-Bestand, 50 Teilprozesse, so gebaut    150.377
Ganzer Bestand, **entdoppelt**                       **33.918**
===================================================  ==================

**Damit steht Auflage 1 des Tickets auf dem Kopf.** Der Ticketkopf rechnete mit
dem Dreifachen für ein Paket über alle 50 Teilprozesse; gemessen sind es 1,9-fach
— und *nach* der Entdopplung ist der größtmögliche Fall **kleiner als der
gemessene Prototyp-Aufruf über 16 Teilprozesse**. Die Aufteilung nach Kernprozess
bleibt gebaut, aber sie ist ein Notausgang, kein Regelweg.

**Entdoppelt wird bedingt, nie blind.** Der Befund „bei 10 von 10 wortgleich"
stammt vom Snapshot des 27.08.2026, und seine Gegenprobe am Livestand ist
`#249 <https://github.com/pg-coe-kmu/coe-factory/issues/249>`_. Gehoben wird
darum nur, was unter den Geschwistern **dieses** Kernprozesses tatsächlich
übereinstimmt; wo sie sich unterscheiden, bleibt das Feld beim Teilprozess. Eine
Messung zur Invariante zu erklären, bevor sie gegengeprüft ist, ist genau der
Schluss vom Artefakt auf die Absicht, den die Karte dreimal verzeichnet.

Auflage 1 — Obergrenze
----------------------

Über :data:`GRENZE_ZEICHEN` fällt der Bau auf **Schnitt B** zurück, einen Aufruf
je Kernprozess. #194 hat erwiesen, dass B und C gleichwertig schneiden; der
Unterschied liegt allein darin, dass B kernprozessübergreifende Doppelgänger
nicht mehr sehen kann — der Preis des Notausgangs, nicht des Regelwegs.

.. note::
   **Die Grenze hat heute keinen Gegenstand, und zwar aus einem zweiten Grund.**
   Die Gegenprobe am Livestand (#249, 21.09.2026) hat gemessen, dass die bisher
   geschnürten Pakete **1–2 Teilprozesse aus genau einem Kernprozess** tragen —
   Gate 0 hat bei NoroAI einen einzigen freigegeben. Bei einem Kernprozess
   fallen B und C zusammen, bei einem Teilprozess alle drei Schnitte. Ob das
   Aufbaustand oder Absicht ist, ist bei BC0 zu bestätigen (#256). Bis dahin
   gilt: gebaut ist der Weg für Pakete, die es noch nicht gibt — was richtig
   ist, aber nicht mit „erprobt" verwechselt werden darf.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .bestand import Kernprozess, Paketbestand, Teilprozess

__all__ = ["Aufruf", "GRENZE_ZEICHEN", "HEBBARE_FELDER", "packe"]

#: Ab wie vielen Zeichen ein Aufruf nach Kernprozess aufgeteilt wird.
#:
#: 120.000 Zeichen sind rund 30.000 Token — das 3,5-fache des größten heute
#: belegbaren Falls (33.918 Zeichen für den ganzen NoroAI-Bestand, entdoppelt)
#: und zugleich weniger als das, was im Prototyp nachweislich noch durchlief
#: (80.431 Zeichen, 21 Aufrufe ohne Abschneiden). Eine Grenze, die heute nicht
#: greift und erst bei echtem Wachstum anschlägt — nicht erst im Fehlerfall.
GRENZE_ZEICHEN = 120_000

#: Felder eines Teilprozesses, die an den Kernprozess gehoben werden **dürfen**,
#: wenn alle Geschwister denselben Wert tragen. ``name`` und ``ablauf`` stehen
#: bewusst nicht darin: sie sind das Einzige, was einen Teilprozess von seinen
#: Geschwistern unterscheidet (``name`` bei 0 von 10 Kernprozessen identisch,
#: ``notation`` bei 4 von 10). Sie zu heben hieße, den Teilprozess zu löschen.
HEBBARE_FELDER = ("werkzeuge", "medienbrueche", "schnittstellen", "api")


@dataclass(frozen=True)
class Aufruf:
    """Eine fertige Nutzlast für genau einen Modellaufruf."""

    name: str
    #: ``"C"`` — ein Aufruf je Paket. ``"B"`` — ein Aufruf je Kernprozess.
    schnitt: str
    inhalt: dict[str, Any]
    #: Die Teilprozesse, für die **dieser** Aufruf zuständig ist. Die
    #: Deckungsprüfung misst gegen genau diese Menge, nicht gegen das ganze
    #: Paket — sonst meldete Schnitt B bei jedem Aufruf die Teilprozesse der
    #: anderen Kernprozesse als unbedeckt.
    teilprozess_ids: tuple[str, ...]

    @property
    def zeichen(self) -> int:
        return len(json.dumps(self.inhalt, ensure_ascii=False))


def _tp_block(tp: Teilprozess, gehoben: set[str], belege_gehoben: bool) -> dict[str, Any]:
    """Ein Teilprozess, ohne das, was schon am Kernprozess steht."""
    block: dict[str, Any] = {
        "teilprozess_id": tp.teilprozess_id,
        "name": tp.name,
    }
    if tp.schritt_nr is not None:
        block["schritt_nr"] = tp.schritt_nr
    if tp.ablauf:
        block["ablauf"] = tp.ablauf

    for feld in HEBBARE_FELDER:
        if feld in gehoben:
            continue
        wert = getattr(tp, feld)
        if wert:
            block[feld] = wert

    if tp.bitkom:
        block["bitkom"] = [
            ({"item": b.item_nr, "stufe": b.stufe} if belege_gehoben
             else {"item": b.item_nr, "stufe": b.stufe, "beleg": b.beleg})
            for b in tp.bitkom
        ]
    else:
        # Auflage 4, hier sichtbar gemacht statt stillschweigend: der
        # Teilprozess traegt keine Bewertungen. Eine 0 stuende an dieser Stelle
        # fuer "am schlechtesten automatisierbar" -- das Gegenteil der Wahrheit.
        block["bewertungen"] = "nicht erhoben"

    if tp.ist_platzhalter:
        block["hinweis"] = "Platzhalter-Name, kein erhobener Ablauf"

    if tp.bc1_profil is not None:
        p = tp.bc1_profil
        gemessen = {
            k: v
            for k, v in (
                ("frequency_per_year", p.frequency_per_year),
                ("step_frequency_per_year", p.step_frequency_per_year),
                ("total_duration_minutes", p.total_duration_minutes),
                ("focus_step_duration_minutes", p.focus_step_duration_minutes),
                ("herkunft_der_dauer", p.focus_step_duration_source),
            )
            if v is not None
        }
        if gemessen:
            # Die Zahlen reisen mit, damit das Modell den Umfang einschaetzen
            # kann -- und genau sie sind es, an denen das Rechenverbot in 2 von
            # 21 Aufrufen brach (#194). Der Waechter in pruefen.py haengt daran.
            block["bc1_gemessen"] = gemessen
    return block


def _kp_block(kp: Kernprozess) -> dict[str, Any]:
    """Ein Kernprozess mit allem, was für alle seine Teilprozesse gilt."""
    block: dict[str, Any] = {"kernprozess_id": kp.kernprozess_id, "name": kp.name}
    for schluessel, wert in (
        ("kategorie", kp.kategorie),
        ("ausloeser", kp.ausloeser),
        ("eingang", kp.eingang),
        ("ausgang", kp.ausgang),
    ):
        if wert:
            block[schluessel] = wert

    tps = kp.teilprozesse

    # --- Auflage 2, bedingt ------------------------------------------------
    gehoben: dict[str, Any] = {}
    for feld in HEBBARE_FELDER:
        werte = {getattr(t, feld) or "" for t in tps}
        if len(werte) == 1 and len(tps) > 1:
            einziger = werte.pop()
            if einziger:
                gehoben[feld] = einziger
    if gehoben:
        gehoben["_hinweis"] = "gilt wortgleich fuer alle Teilprozesse dieses Kernprozesses"
        block["gilt_fuer_alle_teilprozesse"] = gehoben

    # Belege: nur heben, wenn JEDES Item ueber alle bewerteten Geschwister
    # denselben Text traegt. Sonst bleiben sie am Teilprozess -- die Pruefung
    # ist bewusst streng, weil ein falsch gehobener Beleg eine Begruendung an
    # einen Teilprozess haengte, fuer den sie nie erhoben wurde.
    bewertet = [t for t in tps if t.bitkom]
    belege: dict[int, str] = {}
    belege_gehoben = False
    if len(bewertet) > 1:
        je_item: dict[int, set[str]] = {}
        for t in bewertet:
            for b in t.bitkom:
                je_item.setdefault(b.item_nr, set()).add(b.beleg)
        if je_item and all(len(v) == 1 for v in je_item.values()):
            belege = {i: next(iter(v)) for i, v in sorted(je_item.items())}
            belege_gehoben = True

    block["teilprozesse"] = [
        _tp_block(t, set(gehoben) - {"_hinweis"}, belege_gehoben) for t in tps
    ]
    if belege_gehoben:
        block["bitkom_belege"] = {
            str(i): t for i, t in belege.items()
        }
        block["bitkom_belege_hinweis"] = (
            "Ein Belegtext je Item, wortgleich fuer alle Teilprozesse dieses "
            "Kernprozesses. Die STUFEN unterscheiden sich, die Begruendung nicht."
        )
    return block


def _rahmen(bestand: Paketbestand, bitkom_items: dict[int, dict[str, str]]) -> dict[str, Any]:
    r: dict[str, Any] = {
        "company_id": bestand.company_id,
        "paket_id": bestand.paket_id,
        "uebergeben_am": bestand.uebergeben_am.isoformat(),
        "gelesen_am": bestand.gelesen_am.isoformat(),
    }
    m = bestand.mandant
    for schluessel, wert in (
        ("mandant", m.name),
        ("branche", m.branche),
        ("mitarbeitende", m.mitarbeitende),
    ):
        if wert:
            r[schluessel] = wert
    if bestand.hinweise:
        r["hinweise_zum_datenstand"] = list(bestand.hinweise)
    if bitkom_items:
        # Der Item-Katalog haengt am Item, nicht am Teilprozess -- 30 Items
        # mal 50 Teilprozessen waere derselbe Text 1500-mal.
        r["bitkom_items"] = [
            {"item": nr, **text} for nr, text in sorted(bitkom_items.items())
        ]
    return r


def _katalog(bestand: Paketbestand) -> dict[int, dict[str, str]]:
    katalog: dict[int, dict[str, str]] = {}
    for tp in bestand.teilprozesse:
        for b in tp.bitkom:
            katalog.setdefault(b.item_nr, {"kriterium": b.kriterium, "frage": b.frage})
    return katalog


def packe(bestand: Paketbestand, grenze: int = GRENZE_ZEICHEN) -> tuple[Aufruf, ...]:
    """Baut die Aufrufe für einen Paketbestand.

    Erst Schnitt C — ein Aufruf über alles. Bleibt der unter ``grenze``, ist es
    dabei; sonst wird auf Schnitt B je Kernprozess zurückgefallen.

    Ein Paket ohne Kernprozesse ergibt **keinen** Aufruf. Ein leerer Aufruf
    liefe durch das Modell und käme leer zurück — der Kunde zahlte für eine
    Frage ohne Gegenstand, und die Deckungsprüfung meldete nichts, weil nichts
    zu decken war.
    """
    if not bestand.kernprozesse:
        return ()

    katalog = _katalog(bestand)
    rahmen = _rahmen(bestand, katalog)
    kp_bloecke = [_kp_block(kp) for kp in bestand.kernprozesse]

    ganz = Aufruf(
        name=bestand.paket_id,
        schnitt="C",
        inhalt={"rahmen": rahmen, "kernprozesse": kp_bloecke},
        teilprozess_ids=bestand.teilprozess_ids,
    )
    if ganz.zeichen <= grenze:
        return (ganz,)

    return tuple(
        Aufruf(
            name=kp.kernprozess_id,
            schnitt="B",
            inhalt={
                "rahmen": {
                    **rahmen,
                    "hinweis_zum_schnitt": (
                        f"Dieser Aufruf deckt nur {kp.kernprozess_id} ab. Das Paket "
                        f"traegt {len(bestand.kernprozesse)} Kernprozesse; es wurde "
                        f"aufgeteilt, weil die Nutzlast ueber alle "
                        f"{ganz.zeichen} Zeichen ergaebe (Grenze {grenze})."
                    ),
                },
                "kernprozesse": [block],
            },
            teilprozess_ids=tuple(t.teilprozess_id for t in kp.teilprozesse),
        )
        for kp, block in zip(bestand.kernprozesse, kp_bloecke)
    )
