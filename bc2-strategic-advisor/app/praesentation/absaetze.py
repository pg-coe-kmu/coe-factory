"""
BC2 · Text für die Folie: Markdown in Absätze, Höhe schätzen, teilen statt schrumpfen (#380).

Die Felder, die das Modell schreibt (``beschreibung``, ``to_be_vision``,
``potenzielle_loesung.ansatz``), sind Markdown. Auf der Folie standen sie roh —
„Lösungsansatz: ### Technischer Lösungsansatz". Hier wird daraus, was
``python-pptx`` zeichnen kann: Absätze, Aufzählungen, fette Läufe. **Am Inhalt
ändert sich nichts**; eine Überschrift wird eine fette Zeile, ein Listenpunkt ein
Aufzählungspunkt, ``**x**`` ein fetter Lauf, und kein Zeichen kommt hinzu.

**Die Schätzung** rechnet mit den Zeichenbreiten von Calibri
(:mod:`praesentation.calibri`) und bricht an Wortgrenzen um wie ein Textrahmen.
Vorher galt eine mittlere Breite von 0,5 em; Calibri ist im Mittel 0,41 em
breit, und die zu große Schätzung ließ fast ein Fünftel jeder Spalte leer.
Dafür ein Zuschlag von :data:`SICHERHEIT` auf jede Zeile — Kerning und der
Umbruch von PowerPoint und LibreOffice weichen im Einzelnen ab — und die
Zeilenhöhe von Calibri, 1,22 em. **Eine** Schätzung für Zeichnen und Prüfen:
der Test gegen Rückfall misst mit :func:`passt` dieselben Absätze, die
gezeichnet wurden.

**Teilen statt Schrumpfen.** PowerPoint rechnet ``normAutofit`` erst beim
Bearbeiten nach; ein überlaufender Text überdeckt beim Öffnen, was darunter
steht. Was nicht passt, wird darum nicht kleiner gesetzt, sondern an einer
Wortgrenze geteilt (:func:`teile`), und der Rest geht auf die nächste Fläche.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from . import calibri

__all__ = [
    "Absatz", "Lauf", "aus_markdown", "hoehe_pt", "klartext", "passt", "teile",
    "INNEN_BREITE_PT", "INNEN_HOEHE_PT", "EINZUG_PT",
]

#: Innenabstände eines Textrahmens, wie ``python-pptx`` sie setzt (0,1 Zoll
#: links und rechts, 0,05 Zoll oben und unten), in Punkt.
INNEN_BREITE_PT = 14.4
INNEN_HOEHE_PT = 7.2
#: Einzug eines Aufzählungspunkts.
EINZUG_PT = 11.0

#: Zuschlag auf die geschätzte Zeilenbreite.
SICHERHEIT = 1.06
ZEILENHOEHE = calibri.ZEILENHOEHE


@dataclass(frozen=True)
class Lauf:
    text: str
    fett: bool = False


@dataclass(frozen=True)
class Absatz:
    """Ein Absatz auf der Folie. ``groesse`` in Punkt; ``farbe`` ``None`` heißt Rahmenfarbe."""

    laeufe: tuple[Lauf, ...]
    groesse: float
    punkt: bool = False
    abstand_vor: float = 0.0
    farbe: object = None
    #: Abschnittskopf („HEUTIGER PROZESS"); vor dessen Fortsetzung steht wieder einer.
    kopf: bool = False
    #: Bleibt nie allein unten in einer Spalte: Abschnittsköpfe und Überschriften.
    halten: bool = False
    extra: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def text(self) -> str:
        return "".join(l.text for l in self.laeufe)


def klartext(absaetze) -> str:
    return "\n".join(a.text for a in absaetze)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

_UEBERSCHRIFT = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_PUNKT = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+(.*)$")
_FETT = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_KURSIV = re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])|(?<![_\w])_(?!\s)(.+?)(?<!\s)_(?![_\w])")
_CODE = re.compile(r"`([^`]*)`")


def _ohne_zeichen(text: str) -> str:
    """``*x*``, ``_x_`` und ```x``` verlieren nur ihre Zeichen — die Folie kennt keine Kursive."""
    return _KURSIV.sub(lambda m: m.group(1) or m.group(2), _CODE.sub(r"\1", text))


def _laeufe(zeile: str, fett: bool = False) -> tuple[Lauf, ...]:
    """Inline-Markdown in Läufe: ``**x**`` wird fett. Erst die Fettung, dann der Rest —
    sonst hielte die Kursiv-Regel ``**x**`` für ``*`` + ``*x*`` + ``*``."""
    laeufe, pos = [], 0
    for m in _FETT.finditer(zeile):
        if m.start() > pos:
            laeufe.append(Lauf(_ohne_zeichen(zeile[pos:m.start()]), fett))
        laeufe.append(Lauf(_ohne_zeichen(m.group(1) or m.group(2)), True))
        pos = m.end()
    if pos < len(zeile):
        laeufe.append(Lauf(_ohne_zeichen(zeile[pos:]), fett))
    return tuple(l for l in laeufe if l.text) or (Lauf("", fett),)


def aus_markdown(text: str, groesse: float, *, fett: bool = False) -> list[Absatz]:
    """Markdown in Absätze. Überschriften fett mit etwas Luft davor, Listen als Aufzählung.

    Leerzeilen trennen nur; sie werden kein leerer Absatz. Jede andere Zeile
    bleibt ein eigener Absatz — so steht auf der Folie, was im Text steht.
    """
    absaetze: list[Absatz] = []
    luft = False
    for zeile in text.splitlines():
        if not zeile.strip():
            luft = bool(absaetze)
            continue
        abstand = groesse * 0.4 if luft else 0.0
        if m := _UEBERSCHRIFT.match(zeile):
            absaetze.append(Absatz(_laeufe(m.group(1), True), groesse, halten=True,
                                   abstand_vor=groesse * 0.5 if absaetze else 0.0))
        elif m := _PUNKT.match(zeile):
            absaetze.append(Absatz(_laeufe(m.group(1), fett), groesse, punkt=True, abstand_vor=abstand))
        else:
            absaetze.append(Absatz(_laeufe(zeile.strip(), fett), groesse, abstand_vor=abstand))
        luft = False
    return absaetze


# ---------------------------------------------------------------------------
# Schätzen
# ---------------------------------------------------------------------------


def _breite(zeichen: str, fett: bool) -> float:
    """Breite eines Zeichens in em."""
    return (calibri.FETT if fett else calibri.NORMAL).get(zeichen, calibri.UNBEKANNT) / 1000


def _umbrechen_absatz(a: Absatz, breite_pt: float) -> list[str]:
    """Bricht an Wortgrenzen um, wie ein Textrahmen; zu lange Wörter werden zerteilt.

    Gibt die Zeilen als Text zurück; ihre Längen addieren sich mit je einem
    Leerzeichen zwischen den Zeilen wieder zur Länge des Absatzes.
    """
    nutzbar = (breite_pt - INNEN_BREITE_PT - (EINZUG_PT if a.punkt else 0.0)) / a.groesse / SICHERHEIT
    zeichen = [(c, l.fett) for l in a.laeufe for c in l.text]
    woerter, wort = [], []
    for c, f in zeichen:
        if c == " ":
            woerter.append(wort)
            wort = []
        else:
            wort.append((c, f))
    woerter.append(wort)

    zeilen: list[str] = []
    aktuell, breite = "", 0.0
    for wort in woerter:
        w = sum(_breite(c, f) for c, f in wort)
        leer = _breite(" ", False) if aktuell else 0.0
        if aktuell and breite + leer + w > nutzbar:
            zeilen.append(aktuell)
            aktuell, breite, leer = "", 0.0, 0.0
        if not aktuell and w > nutzbar:
            # Ein Wort breiter als die Zeile: zeichenweise zerteilen.
            for c, f in wort:
                b = _breite(c, f)
                if aktuell and breite + b > nutzbar:
                    zeilen.append(aktuell)
                    aktuell, breite = "", 0.0
                aktuell += c
                breite += b
            continue
        text = "".join(c for c, _f in wort)
        aktuell = f"{aktuell} {text}" if aktuell else text
        breite += leer + w
    zeilen.append(aktuell)
    return zeilen


def _zeilen(a: Absatz, breite_pt: float) -> int:
    return len(_umbrechen_absatz(a, breite_pt))


def _hoehe(a: Absatz, breite_pt: float, erster: bool) -> float:
    return (0.0 if erster else a.abstand_vor) + _zeilen(a, breite_pt) * a.groesse * ZEILENHOEHE


def hoehe_pt(absaetze, breite_pt: float) -> float:
    """Geschätzte Höhe des Textes, ohne Innenabstände."""
    return sum(_hoehe(a, breite_pt, i == 0) for i, a in enumerate(absaetze))


def passt(absaetze, breite_pt: float, hoehe_rahmen_pt: float) -> bool:
    return hoehe_pt(absaetze, breite_pt) <= hoehe_rahmen_pt - INNEN_HOEHE_PT


# ---------------------------------------------------------------------------
# Teilen
# ---------------------------------------------------------------------------


def _schneide_laeufe(laeufe: tuple[Lauf, ...], n: int) -> tuple[tuple[Lauf, ...], tuple[Lauf, ...]]:
    """Teilt Läufe nach ``n`` Zeichen; die Fettung bleibt auf beiden Seiten erhalten."""
    vorn, hinten, rest = [], [], n
    for l in laeufe:
        if rest >= len(l.text):
            vorn.append(l)
            rest -= len(l.text)
        elif rest > 0:
            vorn.append(Lauf(l.text[:rest], l.fett))
            hinten.append(Lauf(l.text[rest:], l.fett))
            rest = 0
        else:
            hinten.append(l)
    return tuple(vorn), tuple(hinten)


def _teile_absatz(a: Absatz, breite_pt: float, zeilen: int) -> tuple[Absatz | None, Absatz]:
    """Die ersten ``zeilen`` Zeilen von ``a`` und der Rest, geteilt an einer Wortgrenze."""
    umbruch = _umbrechen_absatz(a, breite_pt)
    if zeilen <= 0:
        return None, a
    vorn_text = " ".join(umbruch[:zeilen])
    schnitt = len(vorn_text)
    # Die Leerstelle an der Schnittkante gehört keiner Seite.
    vorn_l, hinten_l = _schneide_laeufe(a.laeufe, schnitt)
    hinten_l = _schneide_laeufe(hinten_l, 1)[1] if a.text[schnitt:schnitt + 1] == " " else hinten_l
    vorn = replace(a, laeufe=vorn_l)
    # Der Rest eines Listenpunkts ist kein neuer Punkt; er läuft eingerückt weiter.
    hinten = replace(a, laeufe=hinten_l, abstand_vor=0.0, extra={**a.extra, "fortsetzung": True})
    return vorn, hinten


def teile(absaetze, breite_pt: float, hoehe_rahmen_pt: float) -> tuple[list[Absatz], list[Absatz]]:
    """Was in den Rahmen passt, und der Rest. Abgeschnitten wird nichts.

    Ein Kopf oder eine Überschrift bleibt nie als letzte Zeile stehen, und ein Absatz wird
    nur geteilt, wenn mindestens zwei seiner Zeilen auf die Fläche passen.
    """
    frei = hoehe_rahmen_pt - INNEN_HOEHE_PT
    drin: list[Absatz] = []
    liste = list(absaetze)
    for i, a in enumerate(liste):
        h = _hoehe(a, breite_pt, not drin)
        if h <= frei:
            # Allein unten bleibt ein Kopf nur in einer leeren Spalte — sonst wanderte er endlos weiter.
            if a.halten and drin and i + 1 < len(liste):
                folgend = liste[i + 1]
                zwei = min(2, _zeilen(folgend, breite_pt)) * folgend.groesse * ZEILENHOEHE
                if h + folgend.abstand_vor + zwei > frei:
                    return drin, liste[i:]
            drin.append(a)
            frei -= h
            continue
        vorlauf = 0.0 if not drin else a.abstand_vor
        passen = int((frei - vorlauf) // (a.groesse * ZEILENHOEHE))
        if passen >= 2 and not a.halten:
            vorn, hinten = _teile_absatz(a, breite_pt, passen)
            drin.append(vorn)
            return drin, [hinten, *liste[i + 1:]]
        if not drin and passen >= 1 and not a.halten:
            # Nur eine Zeile hat Platz: dann eben eine — ein leerer Rahmen hilft niemandem.
            vorn, hinten = _teile_absatz(a, breite_pt, passen)
            return [vorn], [hinten, *liste[i + 1:]]
        return drin, liste[i:]
    return drin, []
