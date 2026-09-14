"""PII-Filter (B2): ersetzt personenbezogene Angaben durch Platzhalter, BEVOR der
Kern eine Nachricht speichert oder an einen Anbieter gibt.

Total (wirft nie), deterministisch, idempotent — nur Standardbibliothek.
Was erkannt wird, was bewusst nicht (nackte Nachnamen, Kartennummern,
Konsistenz über Turns) und warum: design/Konzept-B2-PII-Filter.md.
"""
from __future__ import annotations

import re

# Reihenfolge = Anwendungsreihenfolge: spezifisch vor allgemein.
_MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("E-Mail", re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
    # Geschütztes Leerzeichen (U+00A0) kommt beim Einfügen aus Dokumenten vor.
    ("IBAN", re.compile(r"\b[a-z]{2}\d{2}(?:[  ]?[a-z0-9]{4}){2,7}"
                        r"(?:[  ]?[a-z0-9]{1,4})?\b", re.IGNORECASE)),
    ("Telefon", re.compile(r"(?<![\d,.])(?:\+\d{1,3}(?:[ /-]*\(0\))?|\b0)[ /-]*\d"
                           r"(?:[ /-]{0,3}\d){6,13}\b(?![:.]\d)")),
)
# Soll-Länge je Land (Zeichen ohne Leerzeichen): Folgetext wird nicht verschluckt.
_IBAN_LAENGE = {"AT": 20, "BE": 16, "CH": 21, "CZ": 24, "DE": 22, "DK": 18, "ES": 24,
                "FI": 18, "FR": 27, "GB": 22, "HU": 28, "IE": 22, "IT": 27, "LI": 21,
                "LU": 20, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "SE": 24, "SK": 24}
# Datumsformen, die das Telefon-Muster sonst träfe ("01/02/2026", "01-02-2026").
_DATUM = re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}")


def _buchstabe(n: int) -> str:
    """0 → A, 25 → Z, 26 → AA (wie Tabellenspalten)."""
    kennung = ""
    n += 1
    while n:
        n, rest = divmod(n - 1, 26)
        kennung = chr(65 + rest) + kennung
    return kennung


class _Vergabe:
    """Platzhalter je Klasse und Turn: gleicher Wert → gleicher Buchstabe."""

    def __init__(self) -> None:
        self._kennung: dict[tuple[str, str], str] = {}
        self._belegt: dict[str, set[str]] = {}

    def platzhalter(self, klasse: str, wert: str) -> str:
        schluessel = (klasse, " ".join(wert.split()).lower())
        if schluessel not in self._kennung:
            belegt = self._belegt.setdefault(klasse, set())
            kennung = _buchstabe(len(belegt))
            belegt.add(kennung)
            self._kennung[schluessel] = f"[{klasse} {kennung}]"
        return self._kennung[schluessel]


def _iban_ersatz(treffer: str, vergabe: _Vergabe) -> str:
    laenge = _IBAN_LAENGE.get(treffer[:2].upper())
    if laenge is not None:
        gezaehlt = 0
        for i, zeichen in enumerate(treffer):
            gezaehlt += not zeichen.isspace()
            if gezaehlt == laenge:
                return vergabe.platzhalter("IBAN", treffer[:i + 1]) + treffer[i + 1:]
    return vergabe.platzhalter("IBAN", treffer)   # unbekanntes Land / kürzer: ganz ersetzen


def _ersatz(klasse: str, m: re.Match[str], vergabe: _Vergabe) -> str:
    if klasse == "IBAN":
        return _iban_ersatz(m.group(0), vergabe)
    if klasse == "Telefon" and _DATUM.fullmatch(m.group(0)):
        return m.group(0)
    return vergabe.platzhalter(klasse, m.group(0))


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[E-Mail A]"."""
    vergabe = _Vergabe()
    for klasse, muster in _MUSTER:
        text = muster.sub(lambda m, k=klasse: _ersatz(k, m, vergabe), text)
    return text
