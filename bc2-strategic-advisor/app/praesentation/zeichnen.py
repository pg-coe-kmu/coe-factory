"""
BC2 · Zeichenmittel der Präsentation — Palette und Hilfsfunktionen im KIsult-Schnitt.

**Übernommen aus** ``architektur/archiv/build_template.py`` (#244): die Palette und
``box``/``txt``/``header``/``divider``/``foot``. Was **nicht** übernommen ist: der
Platzhalter-Block ``ph`` (er zeichnete ``{{…}}``-Felder, die ein Mensch füllen
sollte — hier füllt der Code) und das Speichern auf einen absoluten Pfad
außerhalb des Repos.

Die Funktionen nehmen die Folie entgegen statt eine Präsentation aus dem
Modulzustand zu lesen: das Template hielt ``prs`` global, und damit hätte jeder
Aufruf denselben Foliensatz verlängert.
"""

from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from .absaetze import EINZUG_PT, INNEN_BREITE_PT, INNEN_HOEHE_PT, Absatz, Lauf, hoehe_pt, passt

INK = RGBColor(0x1A, 0x1A, 0x2E)
DEEP = RGBColor(0x10, 0x2A, 0x43)
BLUE = RGBColor(0x0F, 0x4C, 0x81)
ACCENT = RGBColor(0x2E, 0x86, 0xDE)
TEAL = RGBColor(0x12, 0x9C, 0x9C)
GREEN = RGBColor(0x1E, 0x88, 0x5E)
AMBER = RGBColor(0xE6, 0x7E, 0x22)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREY = RGBColor(0x5A, 0x6B, 0x7B)
LIGHT = RGBColor(0xEC, 0xF2, 0xF9)
CARD = RGBColor(0xF5, 0xF7, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0x9F, 0xB3, 0xC8)
WARN_FILL = RGBColor(0xFD, 0xED, 0xEC)
HELLBLAU = RGBColor(0xBF, 0xD9, 0xF2)
TITELBLAU = RGBColor(0x8F, 0xB7, 0xE0)

BREITE = Inches(13.333)
HOEHE = Inches(7.5)

__all__ = [
    "ACCENT", "AMBER", "BLUE", "BREITE", "CARD", "DEEP", "GREEN", "GREY", "HELLBLAU", "HOEHE",
    "INK", "LIGHT", "LINE", "RED", "TEAL", "TITELBLAU", "WARN_FILL", "WHITE",
    "box", "box_groesse", "box_hoehe", "divider", "flaeche", "foot", "gelesene_absaetze", "header", "karte", "passende_groesse",
    "rahmen", "txt", "txt_hoehe", "ueberlaeuft",
]


def _groesse_fuer(baue, w, h, size: float, mindest: float) -> float:
    """Die größte Schrift bis ``size`` in halben Punkten, bei der ``baue(groesse)`` passt."""
    groesse = size
    while groesse > mindest:
        if passt(baue(groesse), w / 12700, h / 12700):
            return groesse
        groesse -= 0.5
    return mindest


def passende_groesse(text: str, w, h, size: float, mindest: float = 8.0, fett: bool = False) -> float:
    """Die größte Schrift bis ``size``, bei der ``text`` in ``w`` × ``h`` passt — geschätzt.

    **Warum geschätzt und nicht gemessen.** PowerPoint rechnet ``normAutofit``
    erst nach, wenn jemand den Text bearbeitet; eine frisch erzeugte Datei
    zeigt überlaufenden Text also in voller Größe. ``python-pptx`` kann exakt
    messen (``fit_text``), braucht dafür aber eine Schriftdatei auf dem Server.
    Die Schätzung steht in :mod:`praesentation.absaetze` — mittlere
    Zeichenbreite 0,5 em (fett 0,58 em), Zeilenhöhe 1,2 em, Umbruch an
    Wortgrenzen — und liegt eher zu groß.

    **Unter ``mindest`` geht es nicht.** Passt der Text auch dort nicht, ist
    das kein Fall zum Schrumpfen, sondern zum Teilen (:func:`absaetze.teile`);
    der Test gegen Rückfall (#380) fängt jeden Rahmen, der dann noch überläuft.
    """
    def baue(g):
        return [Absatz((Lauf(z, fett),), g) for z in text.split("\n")]
    return _groesse_fuer(baue, w, h, size, mindest)


def _setze(tf, absaetze, color, align) -> None:
    """Schreibt Absätze in einen Textrahmen: Läufe, Fettung, Aufzählung, Abstand davor."""
    for i, a in enumerate(absaetze):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if i and a.abstand_vor:
            p.space_before = Pt(a.abstand_vor)
        if a.punkt:
            _aufzaehlung(p, mit_zeichen=not a.extra.get("fortsetzung"))
        for lauf in a.laeufe:
            r = p.add_run()
            r.text = lauf.text
            r.font.size = Pt(a.groesse)
            r.font.bold = lauf.fett
            r.font.color.rgb = a.farbe or color
            r.font.name = "Calibri"


def _aufzaehlung(p, mit_zeichen: bool) -> None:
    """Hängender Einzug mit „•"; die Fortsetzung eines geteilten Punkts ohne Zeichen."""
    ppr = p._p.get_or_add_pPr()
    ppr.set("marL", str(Pt(EINZUG_PT)))
    ppr.set("indent", str(-Pt(EINZUG_PT) if mit_zeichen else 0))
    for alt in ppr.findall(qn("a:buNone")) + ppr.findall(qn("a:buChar")):
        ppr.remove(alt)
    if mit_zeichen:
        bu = ppr.makeelement(qn("a:buChar"), {"char": "•"})
    else:
        bu = ppr.makeelement(qn("a:buNone"), {})
    ppr.append(bu)


def _absaetze(tf, text: str, size: float, color, bold: bool, align) -> None:
    _setze(tf, [Absatz((Lauf(z, bold),), size) for z in text.split("\n")], color, align)


def _box_absaetze(text: str, size: float, bold: bool) -> list[Absatz]:
    """Erste Zeile in ``size`` und ``bold``, die übrigen normal und zwei Punkt kleiner."""
    zeilen = text.split("\n")
    return [Absatz((Lauf(zeilen[0], bold),), size)] + [
        Absatz((Lauf(z, False),), max(size - 2, 8)) for z in zeilen[1:]]


def box_groesse(text: str, w, h, size: float, bold: bool = True) -> float:
    """Die Größe, die :func:`box` mit ``passend=True`` wählen würde — für eine
    gemeinsame Größe mehrerer Formen auf einer Folie."""
    return _groesse_fuer(lambda g: _box_absaetze(text, g, bold), w, h, size, 8.0)


def txt_hoehe(text: str, w, size: float, bold: bool = False):
    """Die Höhe, die ein Rahmen aus :func:`txt` braucht, damit ``text`` bei ``size`` passt."""
    absaetze = [Absatz((Lauf(zeile, bold),), size) for zeile in text.split("\n")]
    return int(Pt(hoehe_pt(absaetze, w / 12700) + INNEN_HOEHE_PT + 1))


def box_hoehe(text: str, w, size: float, bold: bool = True):
    """Die Höhe, die eine Form aus :func:`box` braucht, damit ``text`` bei ``size`` passt."""
    breite = w / 12700 - 2 * 0.08 * 72 + INNEN_BREITE_PT
    return int(Pt(hoehe_pt(_box_absaetze(text, size, bold), breite) + 2 * 0.03 * 72 + 1))


def box(s, x, y, w, h, text, fill, font=WHITE, size=12, bold=True,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, align=PP_ALIGN.CENTER, line=None, lw=0.75,
        anchor=MSO_ANCHOR.MIDDLE, passend=True):
    """Eine gefüllte Form mit Text. Erste Zeile fett, die übrigen normal und kleiner.

    Langer Text wird **umgebrochen und verkleinert, nie abgeschnitten** — die
    Regel „Überlauf wird umgebrochen, nie begrenzt" (#244) gilt auch innerhalb
    einer Form; reicht die Mindestgröße nicht, muss der Aufrufer teilen.
    """
    sp = s.shapes.add_shape(shape, x, y, w, h)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(lw)
    sp.shadow.inherit = False
    tf = sp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.08)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    if passend:
        size = box_groesse(text, w, h, size, bold)
    _setze(tf, _box_absaetze(text, size, bold), font, align)
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    return sp


def flaeche(s, x, y, w, h, fill, line=None, lw=0.75, shape=MSO_SHAPE.RECTANGLE):
    """Eine Form ohne Text — Hintergrund, Band, Rahmen."""
    sp = s.shapes.add_shape(shape, x, y, w, h)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(lw)
    sp.shadow.inherit = False
    return sp


def txt(s, x, y, w, h, text, size=12, color=INK, bold=False, align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.TOP, schrumpfen=True):
    """Ein Textrahmen ohne Füllung. Schrumpft bis 8 pt, schneidet nie ab."""
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    if schrumpfen:
        size = passende_groesse(text, w, h, size, fett=bold)
    _absaetze(tf, text, size, color, bold, align)
    if schrumpfen:
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    return tb


def rahmen(s, x, y, w, h, absaetze, color=INK, align=PP_ALIGN.LEFT):
    """Ein Textrahmen aus fertigen Absätzen, **ohne** Schrumpfen.

    Für Text, der vorher mit :func:`absaetze.teile` auf die Fläche zugeschnitten
    wurde: er passt, also wird nichts verkleinert — und PowerPoint und
    LibreOffice zeigen dieselbe Größe.
    """
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.auto_size = MSO_AUTO_SIZE.NONE
    _setze(tf, absaetze, color, align)
    return tb


def gelesene_absaetze(sp) -> list[Absatz]:
    """Liest aus einem gezeichneten Rahmen zurück, was :func:`ueberlaeuft` schätzt."""
    absaetze = []
    for p in sp.text_frame.paragraphs:
        laeufe = tuple(Lauf(r.text, bool(r.font.bold)) for r in p.runs)
        if not "".join(l.text for l in laeufe):
            continue
        groesse = max((r.font.size.pt for r in p.runs if r.font.size), default=18.0)
        ppr = p._p.pPr
        punkt = ppr is not None and int(ppr.get("marL", "0")) > 0
        vor = p.space_before.pt if p.space_before is not None else 0.0
        absaetze.append(Absatz(laeufe, groesse, punkt=punkt, abstand_vor=vor))
    return absaetze


def ueberlaeuft(sp) -> bool:
    """Läuft der Text dieses Rahmens nach der Schätzung über? (Test gegen Rückfall, #380)

    Gerechnet mit den tatsächlichen Innenabständen des Rahmens: eine Form aus
    :func:`box` hat schmalere als ein Textrahmen.
    """
    absaetze = gelesene_absaetze(sp)
    if not absaetze:
        return False
    tf = sp.text_frame
    innen_b = (tf.margin_left + tf.margin_right) / 12700
    innen_h = (tf.margin_top + tf.margin_bottom) / 12700
    breite = sp.width / 12700 - innen_b + INNEN_BREITE_PT
    hoehe = sp.height / 12700 - innen_h + INNEN_HOEHE_PT
    return not passt(absaetze, breite, hoehe)


def header(s, kicker, title, color=BLUE, titelbreite=Inches(12.2)):
    """Kopfbalken. ``titelbreite`` schmaler, wenn rechts ein Etikett steht — der
    Titel bricht dann um und schrumpft, statt unter das Etikett zu laufen."""
    flaeche(s, 0, 0, BREITE, Inches(1.1), color)
    flaeche(s, 0, Inches(1.1), BREITE, Inches(0.05), ACCENT)
    txt(s, Inches(0.55), Inches(0.16), Inches(12), Inches(0.3), kicker, 12, HELLBLAU, True)
    txt(s, Inches(0.55), Inches(0.44), titelbreite, Inches(0.62), title, 24, WHITE, True)


def foot(s, n: int, fusszeile: str):
    """Fußzeile. Trägt Mandant, Paket und Fassung — wo sie vom Inhalt nicht abfallen."""
    txt(s, Inches(0.55), Inches(7.08), Inches(11.4), Inches(0.3), fusszeile, 9, GREY)
    txt(s, Inches(12.3), Inches(7.08), Inches(0.7), Inches(0.3), str(n), 9, GREY,
        align=PP_ALIGN.RIGHT)


def karte(s, x, y, w, h, titel, farbe, kopf_h=Inches(0.55), radius=Inches(0.12)):
    """Eine Karte mit farbigem Kopfbalken, dessen obere Ecken genau auf denen der Karte liegen.

    Vorher waren es zwei Rechtecke mit je eigener Rundung; der Kopf saß mit
    seinen unteren Ecken sichtbar versetzt in der Karte (#380). Jetzt hat der
    Kopf nur oben runde Ecken, mit demselben Radius wie die Karte.
    """
    rahmen_ = flaeche(s, x, y, w, h, WHITE, line=farbe, lw=1.5, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    rahmen_.adjustments[0] = radius / min(w, h)
    kopf = box(s, x, y, w, kopf_h, titel, farbe, size=13, passend=False,
               shape=MSO_SHAPE.ROUND_2_SAME_RECTANGLE)
    kopf.adjustments[0] = radius / min(w, kopf_h)
    kopf.adjustments[1] = 0.0
    return rahmen_


def divider(s, num: str, title: str, sub: str):
    """Trennfolie. Die Ziffer in derselben Schrift wie der Titel, der Balken mit Luft darunter."""
    flaeche(s, 0, 0, BREITE, HOEHE, DEEP)
    txt(s, Inches(0.9), Inches(1.85), Inches(4), Inches(1.7), num, 90, RGBColor(0x2E, 0x6B, 0xA8), True,
        anchor=MSO_ANCHOR.BOTTOM, schrumpfen=False)
    flaeche(s, Inches(1.0), Inches(3.72), Inches(2.2), Inches(0.09), ACCENT)
    txt(s, Inches(0.9), Inches(4.0), Inches(11), Inches(0.9), title, 38, WHITE, True)
    txt(s, Inches(0.9), Inches(5.0), Inches(11.5), Inches(1.2), sub, 16, RGBColor(0x9F, 0xB9, 0xD6))
