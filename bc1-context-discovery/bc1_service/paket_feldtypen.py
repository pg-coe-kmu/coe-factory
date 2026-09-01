"""Paketlokale Feldtypen des Discovery-Pakets — Dienst-Ebene, kein Kern-Eingriff.

Feldtypen sind Paket-Bausteine (wie AUSWAHL): der Kern kennt nur das Protokoll
normalisiere/validator, nicht die Bedeutung.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from decimal import Decimal, InvalidOperation

from bc1_core.feldtypen import LISTE, PROZENT_0_100, Feldtyp

# Wortbegrenzt, damit 'MS-01' oder 'S-011' nicht faelschlich als Systemkennung
# gelesen werden. IGNORECASE, weil Nutzer 's-01' schreiben.
_SNN = re.compile(r"\bS-[0-9]{2}\b", re.IGNORECASE)


def snn_tokens(text: str) -> list[str]:
    """Alle Vorkommen in kanonischer Form (S-01), in Textreihenfolge."""
    return [treffer.upper() for treffer in _SNN.findall(text)]


def kanonisiere_snn(text: str) -> str:
    return _SNN.sub(lambda m: m.group(0).upper(), text)


def entferne_snn(text: str, ids: Iterable[str]) -> str:
    """Streicht die genannten Kennungen und raeumt die Reste auf.

    Deterministisch (Spec K3, Sweep): Token raus, danach leere Klammerpaare und
    ueberzaehlige Separatoren/Leerzeichen trimmen. Der Freitext-Name bleibt.
    """
    zu_entfernen = {kennung.upper() for kennung in ids}
    rest = _SNN.sub(
        lambda m: "" if m.group(0).upper() in zu_entfernen else m.group(0), text)
    rest = re.sub(r"\(\s*\)", "", rest)          # leere Klammern
    rest = re.sub(r"\[\s*\]", "", rest)
    rest = re.sub(r"\s{2,}", " ", rest)          # doppelte Leerzeichen
    rest = re.sub(r"\s+([,;])", r"\1", rest)     # Leerzeichen vor Trenner
    # Fix-Runde 1: Semikolon zaehlt als ERSTER Trenner genauso wie Komma — sonst
    # bleibt bei "SAP; S-01; DATEV" ein doppeltes ";;" stehen (Konsolidierung
    # griff nur nach einem vorangehenden Komma/Zeilenanfang).
    rest = re.sub(r"(^|[,;])\s*([,;])", r"\1", rest)
    return rest.strip(" ,;-").strip()


# Prozent OHNE Nachkommastelle: die Zielspalte ist integer (Brief Abschnitt 3).
# Ein 'gueltiges' 70,5 waere sonst nicht schreibbar und die fertige Session haenge
# dauerhaft im 503 (Codex R1-C4). Normalisierung wie PROZENT_0_100, nur die
# Pruefung ist strenger.
def _ist_ganzer_prozentwert(wert: str) -> bool:
    """TOTAL wie jeder Feldtyp-Validator: wirft nie (Codex R2-N-I3).

    Achtung: PROZENT_0_100.validator('70,5') ist WAHR — ein direktes
    Decimal('70,5') wuerde werfen. Deshalb intern erst normalisieren.
    """
    if not PROZENT_0_100.validator(wert):
        return False
    try:
        zahl = Decimal(PROZENT_0_100.normalisiere(wert))
    except (InvalidOperation, ValueError):
        return False
    return zahl == zahl.to_integral_value()


PROZENT_GANZ_0_100 = Feldtyp(
    name="prozent_ganz_0_100",
    validator=_ist_ganzer_prozentwert,
    normalisiere=PROZENT_0_100.normalisiere,
)


def baue_system_typ(bekannte_ids: frozenset[str]) -> Feldtyp:
    """Listen-Feldtyp, der S-NN kanonisiert UND gegen die Mandanten-Menge prueft."""
    def normalisiere(wert: str) -> str:
        return kanonisiere_snn(LISTE.normalisiere(wert))

    def validator(wert: str) -> bool:
        # Komposition explizit (R5-I2): ohne den LISTE-Validator schluepfte ein
        # Leerstring durch, weil er keine unbekannte ID enthaelt.
        return (LISTE.validator(wert)
                and all(token in bekannte_ids for token in snn_tokens(wert)))

    return Feldtyp(name="systeme", validator=validator, normalisiere=normalisiere)
