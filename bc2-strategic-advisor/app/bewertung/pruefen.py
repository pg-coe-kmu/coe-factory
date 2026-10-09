"""
BC2 · Der Wächter des Bewertungsschritts (ADR-006 · BC2, 6.5).

Deterministisch, **vor** dem Rechenkern. Der Kern prüft einiges davon selbst —
er steigt dann aber mit ``ValueError`` mitten im Lauf aus, ohne Wiederholung und
ohne dass der Verstoß benannt beim Modell ankommt. Hier wird er benannt, einmal
wiederholt, und erst dann bricht der Lauf ab.

Geprüft wird:

- ``angesetzt_min_pct`` / ``angesetzt_max_pct`` liegen im Korridor der Klasse;
- jeder Nutzwert ist eine ganze Zahl 1–10 und trägt eine Begründung;
- ein Überschreiben der Komplexität nur mit Begründung — **Pflicht**, wo sie
  nicht gemessen ist (Nachtrag 5);
- der Aufwand in Personentagen ist eine Zahl größer null mit Begründung
  (Nachtrag 7);
- jedes erkannte Potenzial ist **genau einmal** bewertet;
- **keine Zahl mit Einheit in Begründungstexten** — die Zahlenfelder sind
  ausgenommen. Genau diese Trennung kennt der Wächter aus #248 nicht.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from erkennung.pruefen import ZAHL_MIT_EINHEIT

__all__ = ["Erwartung", "KATEGORIEN", "TEXTFELDER", "pruefe_bewertung"]

#: Die fünf Nutzwert-Kategorien (ADR-006, 2.4), in der Schreibweise von
#: :class:`modell.Nutzwert`.
KATEGORIEN = (
    "qualitaet",
    "durchlaufzeit",
    "fehlerreduktion",
    "mitarbeiterzufriedenheit",
    "compliance",
)

#: Die Felder, in denen **keine** Zahl mit Einheit stehen darf. Alles andere
#: sind Zahlenfelder und dürfen Zahlen tragen — dafür sind sie da.
TEXTFELDER = (
    "korridor_begruendung",
    "komplexitaet_begruendung",
    "aufwand_begruendung",
    "klassenzweifel",
)


@dataclass(frozen=True)
class Erwartung:
    """Was der Wächter über ein erkanntes Potenzial wissen muss."""

    korridor_pct: tuple[float, float]
    #: ``None`` ⇒ die Komplexität ist nicht gemessen, Überschreiben ist Pflicht.
    gemessene_komplexitaet: int | None


def _ist_zahl(wert: Any) -> bool:
    # bool ist in Python eine Unterklasse von int; ``true`` ist keine Note.
    return isinstance(wert, (int, float)) and not isinstance(wert, bool)


def _ganz(wert: Any) -> bool:
    return _ist_zahl(wert) and float(wert).is_integer()


def _texte(b: dict[str, Any]) -> list[tuple[str, str]]:
    texte = [(f, b.get(f)) for f in TEXTFELDER]
    nw = b.get("nutzwert")
    if isinstance(nw, dict):
        for k in KATEGORIEN:
            eintrag = nw.get(k)
            if isinstance(eintrag, dict):
                texte.append((f"nutzwert.{k}.begruendung", eintrag.get("begruendung")))
    return [(f, t) for f, t in texte if isinstance(t, str) and t]


def _pruefe_eine(pid: str, b: dict[str, Any], e: Erwartung) -> list[str]:
    v: list[str] = []
    lo, hi = e.korridor_pct

    a_lo, a_hi = b.get("angesetzt_min_pct"), b.get("angesetzt_max_pct")
    if not (_ist_zahl(a_lo) and _ist_zahl(a_hi)):
        v.append(f"{pid}: angesetzt_min_pct und angesetzt_max_pct muessen Zahlen sein.")
    elif a_lo > a_hi:
        v.append(f"{pid}: angesetzt_min_pct liegt ueber angesetzt_max_pct.")
    elif a_lo < lo or a_hi > hi:
        v.append(
            f"{pid}: Lage {a_lo:g}–{a_hi:g} liegt ausserhalb des Korridors "
            f"{lo:g}–{hi:g} der Klasse. Die Klasse bleibt; die Lage muss hinein."
        )
    if not (b.get("korridor_begruendung") or "").strip():
        v.append(f"{pid}: korridor_begruendung fehlt.")

    nw = b.get("nutzwert")
    if not isinstance(nw, dict):
        v.append(f"{pid}: nutzwert fehlt.")
    else:
        for k in KATEGORIEN:
            eintrag = nw.get(k)
            if not isinstance(eintrag, dict):
                v.append(f"{pid}: Nutzwert-Kategorie {k} fehlt.")
                continue
            w = eintrag.get("wert")
            if not _ganz(w) or not 1 <= w <= 10:
                v.append(f"{pid}: Nutzwert {k} = {w!r} ist keine ganze Zahl von 1 bis 10.")
            if not (eintrag.get("begruendung") or "").strip():
                v.append(f"{pid}: Nutzwert {k} ohne Begruendung.")
        fremd = sorted(set(nw) - set(KATEGORIEN))
        if fremd:
            v.append(f"{pid}: unbekannte Nutzwert-Kategorien {fremd}.")

    k = b.get("komplexitaet_ueberschrieben")
    kb = (b.get("komplexitaet_begruendung") or "").strip()
    if k is None:
        if e.gemessene_komplexitaet is None:
            v.append(
                f"{pid}: die Komplexitaet ist nicht gemessen — komplexitaet_ueberschrieben "
                "ist hier Pflicht, mit Begruendung."
            )
    else:
        if not _ganz(k) or not 1 <= k <= 10:
            v.append(f"{pid}: komplexitaet_ueberschrieben = {k!r} ist keine ganze Zahl von 1 bis 10.")
        if not kb:
            v.append(f"{pid}: Komplexitaet ueberschrieben ohne Begruendung.")

    pt = b.get("aufwand_schaetzung_pt")
    if not _ist_zahl(pt) or pt <= 0:
        v.append(f"{pid}: aufwand_schaetzung_pt = {pt!r} ist keine Zahl groesser null.")
    if not (b.get("aufwand_begruendung") or "").strip():
        v.append(f"{pid}: aufwand_begruendung fehlt.")

    mit_einheit = [f for f, t in _texte(b) if ZAHL_MIT_EINHEIT.search(t)]
    if mit_einheit:
        v.append(
            f"{pid}: Zahl mit Einheit in Begruendungstexten ({', '.join(mit_einheit)}). "
            "Zahlen gehoeren in die Zahlenfelder."
        )
    return v


def pruefe_bewertung(
    ergebnis: dict[str, Any] | None,
    erwartet: dict[str, Erwartung],
) -> tuple[str, ...]:
    """Die Verstöße einer Antwort — leer, wenn sie in den Rechenkern darf."""
    if ergebnis is None:
        return ("Die Antwort enthielt kein lesbares JSON-Objekt.",)
    bewertungen = ergebnis.get("bewertungen")
    if not isinstance(bewertungen, list):
        return ("Die Antwort traegt keine Liste 'bewertungen'.",)

    verstoesse: list[str] = []
    gesehen: dict[str, int] = {}
    for b in bewertungen:
        if not isinstance(b, dict):
            verstoesse.append("Ein Eintrag in 'bewertungen' ist kein Objekt.")
            continue
        pid = str(b.get("id"))
        gesehen[pid] = gesehen.get(pid, 0) + 1
        if pid not in erwartet:
            verstoesse.append(f"{pid}: kein erkanntes Potenzial dieses Laufs.")
            continue
        if gesehen[pid] == 1:
            verstoesse.extend(_pruefe_eine(pid, b, erwartet[pid]))

    mehrfach = sorted(p for p, n in gesehen.items() if n > 1)
    if mehrfach:
        verstoesse.append(f"Mehrfach bewertet: {', '.join(mehrfach)}.")
    fehlend = sorted(set(erwartet) - set(gesehen))
    if fehlend:
        verstoesse.append(f"Nicht bewertet: {', '.join(fehlend)}.")
    return tuple(verstoesse)
