"""Gemeinsame Test-Hilfen für alle Testdateien."""
import logging

import pytest

# Dieselben Namen, die bc1_service/main.py beim Import auf INFO setzt (B3 Teil 2).
_GESETZTE_LOGGER = ("bc1", "anthropic", "google_genai", "google.genai", "httpx", "httpcore")


@pytest.fixture(autouse=True)
def _logger_stufen_zuruecksetzen():
    # Ohne Rücksetzen trüge ein Test, der main lädt, die Stufen in alle späteren Tests:
    # Ein Test, der mit DEBUG nach Inhalten im Protokoll sucht, prüfte dann still nichts.
    vorher = {name: logging.getLogger(name).level for name in _GESETZTE_LOGGER}
    yield
    for name, stufe in vorher.items():
        logging.getLogger(name).setLevel(stufe)
