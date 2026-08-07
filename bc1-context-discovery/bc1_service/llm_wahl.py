"""Wählt die LLM-Implementierung anhand von BC1_LLM (Default: claude)."""
from __future__ import annotations

from typing import Mapping

from bc1_service.claude_llm import ClaudeLLM


def waehle_llm(umgebung: Mapping[str, str]):
    wahl = umgebung.get("BC1_LLM", "claude")
    if wahl == "claude":
        return ClaudeLLM()
    if wahl == "ollama":
        # Import nur hier: der Claude-Produktionspfad braucht das
        # ollama-Paket (dev-Dependency) nie.
        from bc1_service.ollama_llm import OllamaLLM

        return OllamaLLM()
    raise RuntimeError(
        f"BC1_LLM='{wahl}' ist unbekannt — erlaubt sind 'claude' (Default) "
        "oder 'ollama' (lokaler Test-/Dev-Ersatz)."
    )
