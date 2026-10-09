"""
BC2 · Wie Zahlen auf eine Folie kommen — die Darstellungsregeln aus #244 als Code.

Die Folie zwingt zur Kürze, und Kürze frisst Spannen: hier kann ADR-006 · BC2
unterlaufen werden, ohne dass es jemand merkt. Deshalb entsteht **jeder** Satz
mit einer Zahl in diesem Modul, und nirgends sonst:

1. **Nie eine Zahl ohne ihre Spanne, Herkunft im selben Satz** —
   „18.000–29.000 €/Jahr (Dauer geschätzt, ±40 %)", nicht „23.500 €". Die Mitte
   tritt nirgends allein auf.
2. **Bei ``value_quelle: "keine"`` steht der Grund**, kein „n/a", kein Strich,
   keine 0.
3. **Keine 0 als Ersatz für eine fehlende Größe.** Der Vertrag selbst trägt an
   zwei Stellen eine Ersatz-0: ``manueller_aufwand_heute.stunden_jahr`` bei
   Herkunft ``unbekannt`` und ``investition_eur_richtwert`` ohne
   Aufwandsschätzung (beide aus ``modell/ausgabe.py``, ``… or 0``). Auf der
   Folie wird daraus der Grund, nicht „0 h" und nicht „0 €".

**Eine Ausnahme von Regel 1, offen benannt:** der Investitions-Richtwert ist im
Vertrag ein Punktwert (Aufwand in PT × Bausatz), keine Spanne. Eine Spanne
daraus zu machen hieße, Information zu erfinden; ihn wegzulassen hieße, Teil 3
zu leeren. Er erscheint deshalb nur in **einer** Form — „Richtwert 12.000 € aus
15 PT Aufwand" —, die Herleitung im selben Satz, und die Prüfung in den Tests
lässt genau diese Form zu und keine andere.
"""

from __future__ import annotations

from typing import Mapping

from modell.parameter import STANDARD

__all__ = [
    "amortisation",
    "automatisierungsgrad",
    "datum",
    "einsparung",
    "eur",
    "eur_spanne",
    "investition",
    "luecke",
    "manueller_aufwand",
    "zahl",
]

#: Wie eine fehlende Angabe auf der Folie heißt. Ein Wort, keine Zeichen: ein
#: Strich oder „n/a" sieht aus wie ein Wert, den jemand vergessen hat.
LUECKE = "nicht erhoben"

_HERKUNFT_DER_DAUER = {
    "gemessen": "gemessen",
    "aus_system": "aus dem System",
    "geschaetzt": "geschätzt",
}

_VALUE_QUELLE = {
    "berechnet": "",
    "annahme": "Annahme, Größen gesetzt; ",
    "default": "Vorgabewert, nicht erhoben; ",
}


def zahl(x: float, stellen: int = 0) -> str:
    """Deutsche Schreibweise: Tausenderpunkt, Dezimalkomma."""
    roh = f"{x:,.{stellen}f}"
    return roh.replace(",", " ").replace(".", ",").replace(" ", ".")


def eur(x: float) -> str:
    return f"{zahl(x)} €"


def eur_spanne(spanne: Mapping) -> str:
    """„18.000–29.000 €" — immer beide Enden, auch wenn sie zusammenfallen."""
    return f"{zahl(spanne['min'])}–{zahl(spanne['max'])} €"


def luecke(wert) -> str:
    """Eine Angabe oder das Wort für ihr Fehlen — nie leer, nie 0, nie ein Strich."""
    if wert is None:
        return LUECKE
    text = str(wert).strip()
    return text or LUECKE


def datum(iso: str | None) -> str:
    """``2026-09-20T14:32:11+00:00`` → ``20.09.2026``."""
    if not iso:
        return LUECKE
    jahr, monat, tag = iso[:10].split("-")
    return f"{tag}.{monat}.{jahr}"


def _herkunft(potenzial: Mapping) -> str:
    """Die Herkunft der Zahl, für den Satz, in dem sie steht."""
    aufwand = potenzial.get("manueller_aufwand_heute") or {}
    herkunft = aufwand.get("herkunft")
    quelle = (potenzial.get("value") or {}).get("value_quelle", "berechnet")
    vorsatz = _VALUE_QUELLE.get(quelle, "")
    if herkunft in _HERKUNFT_DER_DAUER:
        breite = round(STANDARD.breite_je_herkunft[herkunft] * 100)
        return f"{vorsatz}Dauer {_HERKUNFT_DER_DAUER[herkunft]}, ±{breite} %"
    return f"{vorsatz}Herkunft der Dauer {LUECKE}".strip()


def manueller_aufwand(potenzial: Mapping) -> str:
    """„540 h/Jahr (Dauer geschätzt, ±40 %)" — oder der Grund, warum es keine Zahl gibt.

    Bei Herkunft ``unbekannt`` schreibt der Vertrag ``stunden_jahr: 0``. Das ist
    keine Messung, sondern ihr Fehlen.
    """
    aufwand = potenzial.get("manueller_aufwand_heute")
    if not aufwand:
        return "Manueller Aufwand heute: liegt für diesen Lauf nicht vor"
    if aufwand.get("herkunft") not in _HERKUNFT_DER_DAUER:
        return "Manueller Aufwand heute: keine Dauer erhoben, deshalb keine Stundenzahl"
    stunden = zahl(aufwand["stunden_jahr"], 0 if aufwand["stunden_jahr"] >= 100 else 1)
    return f"Manueller Aufwand heute: {stunden} h/Jahr ({_herkunft(potenzial)})"


def _grund(potenzial: Mapping) -> str:
    value = potenzial.get("value") or {}
    grund = (value.get("grund") or "").strip()
    return grund or "keine Dauer erhoben, deshalb keine Wertaussage"


def hat_wertaussage(potenzial: Mapping) -> bool:
    value = potenzial.get("value") or {}
    return value.get("value_quelle") not in (None, "keine") and bool(value.get("einsparung_eur_jahr"))


def einsparung(potenzial: Mapping) -> str:
    """„3.096–12.040 €/Jahr (Annahme, Größen gesetzt; Dauer geschätzt, ±40 %)" oder der Grund."""
    if not hat_wertaussage(potenzial):
        return f"Keine Wertaussage: {_grund(potenzial)}"
    spanne = potenzial["value"]["einsparung_eur_jahr"]
    return f"{eur_spanne(spanne)}/Jahr ({_herkunft(potenzial)})"


def amortisation(potenzial: Mapping) -> str:
    value = potenzial.get("value") or {}
    spanne = value.get("amortisation_monate")
    if not hat_wertaussage(potenzial) or not spanne:
        return "Amortisation: ohne Wertaussage keine"
    return f"Amortisation {zahl(spanne['min'], 1)}–{zahl(spanne['max'], 1)} Monate"


def investition(potenzial: Mapping) -> str:
    """„Richtwert 12.000 € aus 15 PT Aufwand" — der einzige Euro-Betrag ohne Spanne.

    Steht nur mit seiner Herleitung da. Fehlt die Aufwandsschätzung, schreibt
    der Vertrag ``investition_eur_richtwert: 0``; daraus wird hier kein „0 €".
    """
    pt = potenzial.get("aufwand_schaetzung_pt")
    richtwert = (potenzial.get("value") or {}).get("investition_eur_richtwert")
    if pt is None or pt <= 0:
        return "Investition: kein Aufwand geschätzt, deshalb kein Richtwert"
    pt_text = zahl(pt, 0 if float(pt).is_integer() else 1)
    if not hat_wertaussage(potenzial) or not richtwert:
        return f"Investition: {pt_text} PT Aufwand geschätzt, ohne Euro-Richtwert"
    return f"Investition: Richtwert {eur(richtwert)} aus {pt_text} PT Aufwand"


def automatisierungsgrad(potenzial: Mapping) -> str:
    grad = potenzial.get("automatisierungsgrad")
    if not grad:
        return "Automatisierungsgrad: liegt für diesen Lauf nicht vor"
    return (
        f"Lösungsklasse {grad['klasse']}, Automatisierungsgrad "
        f"{zahl(grad['angesetzt_min_pct'])}–{zahl(grad['angesetzt_max_pct'])} %"
    )
