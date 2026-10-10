"""
BC2 · Der Ausarbeitungsschritt — vom gerechneten Lauf zum lieferbaren Konzept.

Läuft **nach** dem Rechenkern (ADR-010 · BC2, 2.1): Erkennung → Bewertung →
Rechnung → Ausarbeitung. Er schreibt nur Text, keine Zahl, die in den Rang
eingeht — ein Neulauf schreibt darum andere Sätze, verschiebt aber keinen
Rang. Dafür sieht er Rang und Prioritätsgruppe und kann die Gesamtempfehlung
begründen.

**Ein Aufruf je Konzept, parallel** (2.2), mit einer Wiederholung wie Erkennung
und Bewertung. Bricht auch die Wiederholung, hält der ganze Lauf an (2.6): ein
Lauf ohne Texte ist kein lieferbarer Lauf, und ein dritter Laufzustand „Texte
fehlen“ in Schema ``bc2`` lohnt für einen Fall nicht, den es noch nie gab.

Was **maschinell** entsteht (2.3) und darum hier statt beim Modell:

- ``betroffene_prozessschritte`` — die Namen der berührten Teilprozesse. Das
  Vertragsfeld heißt nach einem Wort, das das Glossar meidet; gemeint sind
  Teilprozesse.
- ``querschnitte.reifegrad`` — das Mittel der Bitkom-Stufen der berührten
  Teilprozesse.
- ``querschnitte.abhaengigkeiten`` — ausgeschrieben aus der Nummer, die das
  Modell nennt, mit UUID und Titel.
- ``gesamtempfehlung.reihenfolge_potenzial_ids`` — der Potenzialrang.
- ``eingangswerte``, ``gelesen_am`` und die Ausgangslage des Laufs
  (``modell.ausgabe.als_ausgangslage``).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from statistics import fmean
from typing import Any, Mapping

from erkennung.bestand import Kernprozess, Paketbestand
from erkennung.erkennen import Aufrufprotokoll, Erkennung, ErkanntesPotenzial
from erkennung.modellruf import Modellruf
from modell.ausgabe import als_ausgangslage, als_eingangswerte
from modell.rechnen import Lauf

from .anweisung import ANTWORTSCHEMA, PLATZHALTER, baue_frage
from .nutzlast import baue_nutzlast
from .pruefen import Erwartung, normalisiere, pruefe_ausarbeitung

__all__ = ["Ausarbeitung", "AusarbeitungAbgebrochen", "arbeite_aus", "setze_ein"]


class AusarbeitungAbgebrochen(RuntimeError):
    """Ein Konzept ließ sich auch in der Wiederholung nicht ausarbeiten.

    Wie :class:`erkennung.ErkennungAbgebrochen`: Gründe und rohe Antwort reisen
    mit, damit ein Mensch nachsehen kann, ohne den Aufruf zu wiederholen.
    """

    def __init__(self, kp_id: str, gruende: tuple[str, ...], roh: str = "") -> None:
        super().__init__(f"Ausarbeitung von {kp_id} angehalten: " + "; ".join(gruende))
        self.kp_id = kp_id
        self.gruende = gruende
        self.roh = roh


@dataclass(frozen=True)
class Ausarbeitung:
    """Das Ergebnis für einen Lauf: die Konzepte in Vertragsform und die Ausgangslage.

    Die Konzepte tragen alles außer dem Kopf, den erst die Ablage kennt
    (``konzept_id``, ``fassung``, ``erzeugt_am`` …, siehe ``ablage.py``).
    """

    konzepte: tuple[dict[str, Any], ...]
    ausgangslage: dict[str, Any]
    aufrufe: tuple[Aufrufprotokoll, ...] = ()


def _zahl(wert: float) -> str:
    """``65.0`` → ``65``, ``67.5`` → ``67,5`` — deutsch, ohne Nachkommanull."""
    text = f"{wert:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def setze_ein(wert: Any, grad: Mapping[str, float]) -> Any:
    """Setzt die Platzhalter in allen Texten eines Potenzials ein (ADR-010 · BC2, 2.4)."""
    if isinstance(wert, str):
        for name in PLATZHALTER:
            wert = wert.replace("{" + name + "}", _zahl(grad[name]))
        return wert
    if isinstance(wert, dict):
        return {k: setze_ein(v, grad) for k, v in wert.items()}
    if isinstance(wert, list):
        return [setze_ein(v, grad) for v in wert]
    return wert


def _systemtext(tps) -> str:
    return " ".join(
        str(w)
        for tp in tps
        for w in (tp.werkzeuge, tp.schnittstellen, tp.api, tp.medienbrueche, tp.ablauf)
        if w and str(w).strip()
    )


def _systeme(erkannt: ErkanntesPotenzial, kp: Kernprozess, tech_stack: str | None) -> str | None:
    """Der Text, in dem ein genanntes System vorkommen muss (normalisiert).

    Zuerst die berührten Teilprozesse; nennen die keines, der ganze Kernprozess.
    **Der Ablauf zählt mit:** bei KP-05 sind die Werkzeugfelder leer, und das
    Quellsystem steht nur dort („durchsuchen Google-Drive-Ordner“, gemessen am
    09.10.2026). Der Tech-Stack gilt immer mit: ein Zielsystem darf eines sein,
    das der Mandant schon führt, auch wenn der Prozess es heute nicht berührt.
    """
    beruehrt = [tp for tp in kp.teilprozesse if tp.teilprozess_id in erkannt.beruehrte_teilprozess_ids]
    text = _systemtext(beruehrt) or _systemtext(kp.teilprozesse)
    text = " ".join(t for t in (text, tech_stack or "") if t)
    return normalisiere(text) or None


def _reifegrad(erkannt: ErkanntesPotenzial, kp: Kernprozess) -> str | None:
    stufen = [
        b.stufe
        for tp in kp.teilprozesse
        if tp.teilprozess_id in erkannt.beruehrte_teilprozess_ids
        for b in tp.bitkom
        if b.stufe > 0
    ]
    if not stufen:
        return None
    return (
        f"Bitkom-Stufe im Mittel {_zahl(fmean(stufen))} von 5, aus {len(stufen)} Bewertungen "
        "der berührten Teilprozesse. Rangiert, trennt aber nicht (#161)."
    )


def _konzept(
    kp: Kernprozess,
    stuecke: list[tuple[ErkanntesPotenzial, dict]],
    antwort: dict[str, Any],
    kennungen: Mapping[str, str],
    titel: Mapping[str, str],
    lauf: Lauf,
    bestand: Paketbestand,
    modellname: str,
) -> dict[str, Any]:
    texte = {str(p["id"]): p for p in antwort["potenziale"]}
    namen = {tp.teilprozess_id: tp.name for tp in kp.teilprozesse}
    gerechnet_je_id = {p.potenzial_id: p for p in lauf.potenziale}

    potenziale = []
    eingangswerte: list[dict] = []
    for erkannt, gerechnet in stuecke:
        t = texte[erkannt.potenzial_id]
        grad = gerechnet["automatisierungsgrad"]
        t = setze_ein(
            t, {"grad_min": grad["angesetzt_min_pct"], "grad_max": grad["angesetzt_max_pct"]}
        )
        loesung = {"ansatz": t["loesungsansatz"].strip(), "tech_stack_empfehlung": t["tech_stack_empfehlung"]}
        if str(t.get("to_be_kurz") or "").strip():
            loesung["to_be_kurz"] = t["to_be_kurz"].strip()
        querschnitte: dict[str, Any] = {"zukunftssicherheit": t["zukunftssicherheit"].strip()}
        reife = _reifegrad(erkannt, kp)
        if reife:
            querschnitte["reifegrad"] = reife
        querschnitte["abhaengigkeiten"] = [
            f"{kennungen[a['potenzial']]} ({titel[a['potenzial']]}): {a['grund'].strip()}"
            for a in t.get("abhaengigkeiten") or []
        ]
        risiken = []
        for r in t.get("risiken") or []:
            risiko = {k: r[k] for k in ("beschreibung", "wahrscheinlichkeit", "auswirkung")}
            if str(r.get("gegenmassnahme") or "").strip():
                risiko["gegenmassnahme"] = r["gegenmassnahme"].strip()
            risiken.append(risiko)

        potenziale.append(
            {
                **gerechnet,
                "beschreibung": t["beschreibung"].strip(),
                "to_be_vision": t["to_be_vision"].strip(),
                "user_story": t["user_story"].strip(),
                "akzeptanzkriterien_geschaeftlich": [
                    {"kriterium": k["kriterium"].strip(), "messverfahren": k["messverfahren"].strip()}
                    for k in t["akzeptanzkriterien"]
                ],
                "fachliche_anforderungen": [s.strip() for s in t["fachliche_anforderungen"]],
                "betroffene_prozessschritte": [
                    namen.get(tp) or tp for tp in erkannt.beruehrte_teilprozess_ids
                ],
                "betroffene_systeme": [
                    {"name": s["name"].strip(), "rolle": s["rolle"], "integration": s["integration"]}
                    for s in t["betroffene_systeme"]
                ],
                "potenzielle_loesung": loesung,
                "voraussetzungen": [s.strip() for s in t.get("voraussetzungen") or []],
                "risiken": risiken,
                "querschnitte": querschnitte,
            }
        )
        eingangswerte += als_eingangswerte(
            gerechnet_je_id[gerechnet["potenzial_id"]], bestand.gelesen_am
        )

    kontext_roh = antwort["kontext"]
    schmerzpunkte = []
    for s in kontext_roh["hauptschmerzpunkte"]:
        punkt = {"beschreibung": s["beschreibung"].strip(), "auswirkung": s["auswirkung"].strip()}
        if str(s.get("haeufigkeit") or "").strip():
            punkt["haeufigkeit"] = s["haeufigkeit"].strip()
        schmerzpunkte.append(punkt)
    kontext: dict[str, Any] = {
        "prozess_kurzbeschreibung": kontext_roh["prozess_kurzbeschreibung"].strip(),
        "kp_id": kp.kernprozess_id,
    }
    if bestand.mandant.name:
        kontext["unternehmen"] = bestand.mandant.name
    kontext["hauptschmerzpunkte"] = schmerzpunkte

    return {
        "gelesen_am": bestand.gelesen_am.isoformat(),
        "erzeugt_von": f"bc2-strategic-advisor · Ausarbeitung · {modellname}",
        "kontext": kontext,
        "potenziale": potenziale,
        "gesamtempfehlung": {
            "reihenfolge_potenzial_ids": [g["potenzial_id"] for _, g in stuecke],
            "begruendung": antwort["gesamtempfehlung_begruendung"].strip(),
        },
        "eingangswerte": eingangswerte,
    }


def arbeite_aus(
    lauf: Lauf,
    potenziale: Mapping[str, dict],
    erkennung: Erkennung,
    kennungen: Mapping[str, str],
    bestand: Paketbestand,
    modell: Modellruf,
    *,
    gleichzeitig: int | None = None,
    wiederholungen: int = 1,
) -> Ausarbeitung:
    """Arbeitet jedes Konzept des Laufs aus und setzt die Ausgangslage zusammen.

    :param potenziale: die gerechneten Hälften in Vertragsform, je
        ``potenzial_id`` (``Laufansicht.potenziale``).
    :param kennungen: Erkennungsnummer → ``potenzial_id`` (``Bewertung.kennungen``).
    :param gleichzeitig: wie viele Konzepte zugleich ausgearbeitet werden;
        Voreinstellung alle. ``1`` für Doppelgänger mit fester Reihenfolge.
    :raises AusarbeitungAbgebrochen: wenn ein Konzept auch in der Wiederholung bricht.
    """
    nummer = {pid: nr for nr, pid in kennungen.items()}
    erkannt = {p.potenzial_id: p for p in erkennung.potenziale}
    kps = {kp.kernprozess_id: kp for kp in bestand.kernprozesse}
    titel = {nr: p.titel for nr, p in erkannt.items()}

    rangfolge = sorted(lauf.potenziale, key=lambda p: p.potenzialrang)
    reihe: list[tuple[Kernprozess, list[tuple[ErkanntesPotenzial, dict]]]] = []
    for r in lauf.prozess_raenge:
        stuecke = [
            (erkannt[nummer[p.potenzial_id]], potenziale[p.potenzial_id])
            for p in rangfolge
            if p.kp_id == r.kp_id
        ]
        reihe.append((kps[r.kp_id], stuecke))

    alle = frozenset(nummer[p.potenzial_id] for p in lauf.potenziale)

    def ein_konzept(eintrag) -> tuple[dict, Aufrufprotokoll]:
        kp, stuecke = eintrag
        eigene = {e.potenzial_id for e, _ in stuecke}
        uebrige = [
            {
                "id": nummer[p.potenzial_id],
                "titel": p.titel,
                "kernprozess_id": p.kp_id,
                "loesungsklasse": p.automatisierungsgrad.klasse,
            }
            for p in rangfolge
            if nummer[p.potenzial_id] not in eigene
        ]
        nutzlast = baue_nutzlast(bestand.mandant, kp, stuecke, uebrige)
        erwartung = Erwartung(
            nummern=tuple(e.potenzial_id for e, _ in stuecke),
            alle_nummern=alle,
            systeme={e.potenzial_id: _systeme(e, kp, bestand.mandant.tech_stack) for e, _ in stuecke},
        )
        gruende: list[str] = []
        verworfen: list[str] = []
        versuch = 0
        while True:
            versuch += 1
            frage = baue_frage(nutzlast, gruende or None)
            antwort = modell.frage(frage, schema=ANTWORTSCHEMA)
            gruende = list(pruefe_ausarbeitung(antwort.ergebnis, erwartung))
            if antwort.lesefehler:
                gruende.append(antwort.lesefehler)
            if not gruende:
                break
            verworfen.extend(gruende)
            if versuch > wiederholungen:
                raise AusarbeitungAbgebrochen(kp.kernprozess_id, tuple(gruende), antwort.roh)
        assert antwort.ergebnis is not None
        konzept = _konzept(
            kp, stuecke, antwort.ergebnis, kennungen, titel, lauf, bestand, antwort.modell
        )
        return konzept, Aufrufprotokoll(
            name=kp.kernprozess_id,
            schnitt="Ausarbeitung je Konzept",
            zeichen=len(frage),
            modell=antwort.modell,
            versuche=versuch,
            verworfen=tuple(verworfen),
        )

    if not reihe:
        return Ausarbeitung(konzepte=(), ausgangslage=als_ausgangslage(bestand.mandant, []))
    # ``map`` hält die Reihenfolge der Prozessränge, gleich wann ein Aufruf
    # zurückkommt; bricht ein Konzept, bricht der Lauf.
    with ThreadPoolExecutor(max_workers=gleichzeitig or len(reihe)) as pool:
        ergebnisse = list(pool.map(ein_konzept, reihe))
    konzepte = tuple(k for k, _ in ergebnisse)
    return Ausarbeitung(
        konzepte=konzepte,
        ausgangslage=als_ausgangslage(bestand.mandant, konzepte),
        aufrufe=tuple(a for _, a in ergebnisse),
    )
