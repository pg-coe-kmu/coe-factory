"""PII-Filter (B2): ersetzt personenbezogene Angaben durch Platzhalter, BEVOR der
Kern eine Nachricht speichert oder an einen Anbieter gibt.

Total (wirft nie), deterministisch, idempotent — nur Standardbibliothek.
Was erkannt wird, was bewusst nicht (nackte Nachnamen, Kartennummern,
Konsistenz über Turns) und warum: design/Konzept-B2-PII-Filter.md.
"""
from __future__ import annotations

import re

_MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("E-Mail", re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
)


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


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[E-Mail A]"."""
    vergabe = _Vergabe()
    for klasse, muster in _MUSTER:
        text = muster.sub(lambda m, k=klasse: vergabe.platzhalter(k, m.group(0)), text)
    return text
