"""
BC2 · Der Wächter des Ausarbeitungsschritts (#301, ADR-010 · BC2, 2.5).

Er prüft **formal**, nicht fachlich: ob jedes Potenzial genau einmal da ist, ob
die Pflichtfelder des Vertrags tragen, ob Story und Kriterien ihre Schablone
haben — und das Rechenverbot. Ob eine Beschreibung *gut* ist, prüft er nicht;
das sieht der Mensch am Gate 1.

Das Rechenverbot ist dieselbe Regel wie in Erkennung und Bewertung
(``erkennung.pruefen.ZAHL_MIT_EINHEIT``), mit **einer** Erweiterung: die
Platzhalter aus :data:`~ausarbeitung.anweisung.PLATZHALTER` sind in den Texten
eines Potenzials erlaubt, jeder andere Ausdruck in geschweiften Klammern ist ein
Verstoß, und im Kontext und in der Gesamtempfehlung ist auch ein erlaubter
Platzhalter einer — dort gibt es keinen Automatisierungsgrad, den Python
einsetzen könnte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from erkennung.pruefen import ZAHL_MIT_EINHEIT

from .anweisung import INTEGRATIONEN, PLATZHALTER, ROLLEN, STUFEN

__all__ = ["Erwartung", "ROLLEN", "INTEGRATIONEN", "STUFEN", "normalisiere", "pruefe_ausarbeitung"]

#: Mindestlängen aus dem Vertrag. ``beschreibung`` und ``to_be_vision`` werden
#: am **Rohtext** gemessen, vor dem Einsetzen — ein Platzhalter macht einen zu
#: kurzen Text nicht lang genug.
_MIN = {"beschreibung": 300, "to_be_vision": 300, "loesungsansatz": 30, "zukunftssicherheit": 10}

_KLAMMER = re.compile(r"\{([^{}]*)\}")
_NICHT_ALNUM = re.compile(r"[^0-9a-zäöüß]")


def normalisiere(text: str) -> str:
    """Kleingeschrieben, ohne Leer-, Binde- und Satzzeichen.

    Damit trifft „Google Drive“ den Ablauf „durchsuchen Google-Drive-Ordner“ —
    gemessen am 09.10.2026 (#301): der Bestand nennt das System dort und nur
    dort, und eine wörtliche Prüfung verwarf das tatsächliche Quellsystem.
    """
    return _NICHT_ALNUM.sub("", text.lower())
_SOPHIST = re.compile(r"^\s*als\b.+\bm(ö|oe)chte\b.+\bdamit\b", re.IGNORECASE | re.DOTALL)
_GWT = re.compile(r"^\s*gegeben\b.+\bwenn\b.+\bdann\b", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Erwartung:
    """Was der Wächter für ein Konzept wissen muss."""

    #: Die Potenziale dieses Konzepts (Erkennungsnummern).
    nummern: tuple[str, ...]
    #: Alle Potenziale des Laufs — Ziel erlaubter Abhängigkeiten.
    alle_nummern: frozenset[str]
    #: Je Potenzial der Text, in dem ein genanntes System vorkommen muss
    #: (:func:`normalisiere`). ``None`` heißt: der Bestand nennt keines — dann
    #: wird nicht geprüft, sonst hinge der Lauf an einer Datenlücke fest.
    systeme: dict[str, str | None] = field(default_factory=dict)


def _texte(wert: Any, pfad: str) -> Iterator[tuple[str, str]]:
    if isinstance(wert, str):
        yield pfad, wert
    elif isinstance(wert, dict):
        for k, v in wert.items():
            yield from _texte(v, f"{pfad}.{k}")
    elif isinstance(wert, list):
        for i, v in enumerate(wert):
            yield from _texte(v, f"{pfad}[{i}]")


def _rechenverbot(wert: Any, pfad: str, platzhalter_erlaubt: bool) -> list[str]:
    gruende = []
    for ort, text in _texte(wert, pfad):
        for name in _KLAMMER.findall(text):
            if not platzhalter_erlaubt:
                gruende.append(f"{ort}: Platzhalter {{{name}}} ist hier nicht erlaubt")
            elif name not in PLATZHALTER:
                gruende.append(
                    f"{ort}: unbekannter Platzhalter {{{name}}} — erlaubt sind nur "
                    + ", ".join(f"{{{p}}}" for p in PLATZHALTER)
                )
        treffer = ZAHL_MIT_EINHEIT.search(_KLAMMER.sub("", text))
        if treffer:
            gruende.append(f"{ort}: Zahl mit Einheit im Text ({treffer.group(0)!r})")
    return gruende


def _text(d: dict, feld: str, ort: str, mindestens: int = 1) -> list[str]:
    wert = d.get(feld)
    if not isinstance(wert, str) or len(wert.strip()) < mindestens:
        if mindestens > 1:
            return [f"{ort}.{feld}: fehlt oder kürzer als {mindestens} Zeichen"]
        return [f"{ort}.{feld}: fehlt oder leer"]
    return []


def _textliste(d: dict, feld: str, ort: str, mindestens: int) -> list[str]:
    wert = d.get(feld)
    if not isinstance(wert, list) or any(not isinstance(x, str) or not x.strip() for x in wert):
        return [f"{ort}.{feld}: muss eine Liste von Sätzen sein"]
    if len(wert) < mindestens:
        return [f"{ort}.{feld}: mindestens {mindestens} Eintrag nötig"]
    return []


def _potenzial(p: dict, erwartung: Erwartung) -> list[str]:
    nr = str(p.get("id"))
    ort = f"potenziale[{nr}]"
    g: list[str] = []
    for feld, n in _MIN.items():
        g += _text(p, feld, ort, n)
    story = _text(p, "user_story", ort, 20)
    g += story
    if not story and not _SOPHIST.match(p["user_story"]):
        g.append(f"{ort}.user_story: nicht in SOPHIST-Form („Als … möchte ich …, damit …“)")

    kriterien = p.get("akzeptanzkriterien")
    if not isinstance(kriterien, list) or not kriterien:
        g.append(f"{ort}.akzeptanzkriterien: mindestens ein Kriterium nötig")
    else:
        for i, k in enumerate(kriterien):
            if not isinstance(k, dict):
                g.append(f"{ort}.akzeptanzkriterien[{i}]: kein Objekt")
                continue
            if not _GWT.match(str(k.get("kriterium", ""))) or len(str(k.get("kriterium", ""))) < 20:
                g.append(
                    f"{ort}.akzeptanzkriterien[{i}].kriterium: nicht in Given/When/Then-Form "
                    "(„Gegeben …, wenn …, dann …“)"
                )
            g += _text(k, "messverfahren", f"{ort}.akzeptanzkriterien[{i}]", 5)

    g += _textliste(p, "fachliche_anforderungen", ort, 1)
    g += _textliste(p, "tech_stack_empfehlung", ort, 1)
    g += _textliste(p, "voraussetzungen", ort, 0)

    systeme = p.get("betroffene_systeme")
    if not isinstance(systeme, list) or not systeme:
        g.append(f"{ort}.betroffene_systeme: mindestens ein System nötig")
    else:
        bestand = erwartung.systeme.get(nr)
        for i, s in enumerate(systeme):
            o = f"{ort}.betroffene_systeme[{i}]"
            if not isinstance(s, dict) or not str(s.get("name", "")).strip():
                g.append(f"{o}: ohne Namen")
                continue
            if s.get("rolle") not in ROLLEN:
                g.append(f"{o}.rolle: {s.get('rolle')!r} ist keines von {', '.join(ROLLEN)}")
            if s.get("integration") not in INTEGRATIONEN:
                g.append(
                    f"{o}.integration: {s.get('integration')!r} ist keines von "
                    + ", ".join(INTEGRATIONEN)
                )
            name = str(s["name"]).strip()
            if bestand is not None and normalisiere(name) not in bestand:
                g.append(
                    f"{o}.name: {name!r} kommt im Bestand und im Tech-Stack nicht vor — "
                    "nur genannte Systeme, in deren Schreibweise"
                )

    risiken = p.get("risiken", [])
    if not isinstance(risiken, list):
        g.append(f"{ort}.risiken: muss eine Liste sein")
    else:
        for i, r in enumerate(risiken):
            o = f"{ort}.risiken[{i}]"
            if not isinstance(r, dict) or not str(r.get("beschreibung", "")).strip():
                g.append(f"{o}: ohne Beschreibung")
                continue
            for feld in ("wahrscheinlichkeit", "auswirkung"):
                if r.get(feld) not in STUFEN:
                    g.append(f"{o}.{feld}: {r.get(feld)!r} ist keines von low, med, high")

    abh = p.get("abhaengigkeiten", [])
    if not isinstance(abh, list):
        g.append(f"{ort}.abhaengigkeiten: muss eine Liste sein")
    else:
        for i, a in enumerate(abh):
            o = f"{ort}.abhaengigkeiten[{i}]"
            ziel = str(a.get("potenzial") or "") if isinstance(a, dict) else ""
            if not ziel or not str(a.get("grund", "")).strip():
                g.append(f"{o}: braucht potenzial und grund")
            elif ziel == nr:
                g.append(f"{o}: ein Potenzial hängt nicht von sich selbst ab")
            elif ziel not in erwartung.alle_nummern:
                g.append(f"{o}: {ziel!r} ist kein Potenzial dieses Laufs")

    g += _rechenverbot(p, ort, platzhalter_erlaubt=True)
    return g


def pruefe_ausarbeitung(ergebnis: dict | None, erwartung: Erwartung) -> tuple[str, ...]:
    """Die Gründe, aus denen eine Antwort verworfen wird — leer, wenn sie trägt."""
    if not isinstance(ergebnis, dict):
        return ("Die Antwort enthält kein JSON-Objekt.",)
    g: list[str] = []

    kontext = ergebnis.get("kontext")
    if not isinstance(kontext, dict):
        g.append("kontext: fehlt")
    else:
        kurz = kontext.get("prozess_kurzbeschreibung")
        if not isinstance(kurz, str) or not kurz.strip():
            g.append("kontext.prozess_kurzbeschreibung: fehlt oder leer")
        elif len(kurz.strip()) > 280:
            g.append("kontext.prozess_kurzbeschreibung: länger als 280 Zeichen")
        schmerz = kontext.get("hauptschmerzpunkte")
        if not isinstance(schmerz, list) or not schmerz:
            g.append("kontext.hauptschmerzpunkte: mindestens ein Schmerzpunkt nötig")
        else:
            for i, s in enumerate(schmerz):
                o = f"kontext.hauptschmerzpunkte[{i}]"
                if not isinstance(s, dict):
                    g.append(f"{o}: kein Objekt")
                    continue
                g += _text(s, "beschreibung", o) + _text(s, "auswirkung", o)
                if s.get("haeufigkeit") is not None and not isinstance(s["haeufigkeit"], str):
                    g.append(f"{o}.haeufigkeit: muss Text oder null sein")
        g += _rechenverbot(kontext, "kontext", platzhalter_erlaubt=False)

    g += _text(ergebnis, "gesamtempfehlung_begruendung", "antwort")
    g += _rechenverbot(
        ergebnis.get("gesamtempfehlung_begruendung"),
        "gesamtempfehlung_begruendung",
        platzhalter_erlaubt=False,
    )

    potenziale = ergebnis.get("potenziale")
    if not isinstance(potenziale, list):
        return tuple(g + ["potenziale: fehlt"])
    gesehen = [str(p.get("id")) if isinstance(p, dict) else None for p in potenziale]
    erwartet = set(erwartung.nummern)
    for nr in sorted(erwartet - set(gesehen)):
        g.append(f"potenziale: {nr} fehlt — jedes Potenzial genau einmal")
    for nr in sorted({n for n in gesehen if n not in erwartet}, key=str):
        g.append(f"potenziale: {nr} gehört nicht zu diesem Konzept")
    for nr in sorted({n for n in gesehen if gesehen.count(n) > 1}, key=str):
        g.append(f"potenziale: {nr} steht mehrfach da")
    for p in potenziale:
        if isinstance(p, dict) and str(p.get("id")) in erwartet:
            g += _potenzial(p, erwartung)
    return tuple(g)
