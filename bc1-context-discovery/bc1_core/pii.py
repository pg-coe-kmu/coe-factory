"""PII-Filter (B2): ersetzt personenbezogene Angaben durch Platzhalter, BEVOR der
Kern eine Nachricht speichert oder an einen Anbieter gibt.

Total (wirft nie), deterministisch, idempotent — nur Standardbibliothek.
Was erkannt wird, was bewusst nicht (nackte Nachnamen, Kartennummern,
Konsistenz über Turns) und warum: design/Konzept-B2-PII-Filter.md.
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[E-Mail A]"."""
    return _EMAIL.sub("[E-Mail A]", text)
