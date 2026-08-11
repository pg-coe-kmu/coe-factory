"""BC1_LLM wählt die LLM-Implementierung — Default bleibt Claude.

Eigenes Modul statt Logik in main.py: der main-Import zieht den
Postgres-Pool hoch und wäre nicht isoliert testbar.
"""
import pytest

from bc1_service.claude_llm import ClaudeLLM
from bc1_service.gemini_llm import GeminiLLM
from bc1_service.llm_wahl import waehle_llm
from bc1_service.ollama_llm import OllamaLLM


def test_default_ist_claude(monkeypatch):
    # Dummy-Key: das Anthropic-SDK verlangt beim Konstruieren einen Key,
    # es wird aber kein Netz angefasst.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert isinstance(waehle_llm({}), ClaudeLLM)


def test_ollama_waehlt_den_ollama_adapter():
    assert isinstance(waehle_llm({"BC1_LLM": "ollama"}), OllamaLLM)


def test_gemini_liefert_gemini_llm(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    llm = waehle_llm({"BC1_LLM": "gemini"})
    assert isinstance(llm, GeminiLLM)


def test_unbekannte_wahl_nennt_alle_drei_optionen():
    with pytest.raises(RuntimeError) as fehler:
        waehle_llm({"BC1_LLM": "quatsch"})
    for option in ("claude", "ollama", "gemini"):
        assert option in str(fehler.value)
