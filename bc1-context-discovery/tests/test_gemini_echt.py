"""Gemini-Echt-Stichprobe — NUR gezielt starten (Free Tier: 20 Requests/Tag!).

Aufruf (aus bc1-context-discovery/, verbraucht 2 echte Requests):
  BC1_ECHT_LLM=1 .venv/bin/pytest tests/test_gemini_echt.py -v
Modell-Vergleich: zusätzlich BC1_GEMINI_MODELL=gemini-3-flash setzen.
NIE über das globale Flag allein laufen lassen (das würde auch die
Claude-/Ollama-Echt-Tests scharf schalten).
"""
import os

import pytest

from bc1_core.gespraech import Erfassung, TurnKontext
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_service.gemini_llm import GeminiLLM

pytestmark = pytest.mark.skipif(
    not (os.environ.get("BC1_ECHT_LLM") == "1" and os.environ.get("GEMINI_API_KEY")),
    reason="Echt-Stichprobe: BC1_ECHT_LLM=1 und GEMINI_API_KEY nötig",
)

PAKET = UseCasePackage(
    name="echt_test", schema_version="0.1",
    fields=(FieldSpec("prozess_name", "Wie heißt der Prozess?"),))


def test_extract_echt_mit_vollem_schema():
    # Beweist live: response_json_schema akzeptiert unser volles Schema
    # (inkl. additionalProperties) UND die Thinking-Konfig des Modells.
    kandidaten = GeminiLLM().extract(
        "Der Prozess heißt Reisebuchung.", PAKET, None)
    assert any(k.field_name == "prozess_name" and "Reisebuchung" in k.value
               for k in kandidaten)


def test_antworte_echt_bestaetigt_und_fragt():
    text = GeminiLLM().antworte(TurnKontext(
        nutzer_nachricht="Der Prozess heißt Reisebuchung.",
        neu_erfasst=(Erfassung("Wie heißt der Prozess?", "Reisebuchung"),),
        naechste_frage="Wie oft läuft der Prozess (pro Woche, Monat oder Jahr)?",
        ist_nachfrage=False, ist_abschluss=False))
    assert "Reisebuchung" in text
    assert "Wie oft läuft der Prozess" in text
