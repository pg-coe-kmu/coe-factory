"""Wählt die LLM-Implementierung anhand von BC1_LLM (Default: claude)."""
from __future__ import annotations

from typing import Mapping

from bc1_core.llm import LLMClient
from bc1_service.claude_llm import ClaudeLLM


def waehle_llm(umgebung: Mapping[str, str]) -> LLMClient:
    wahl = umgebung.get("BC1_LLM", "claude")
    if wahl == "claude":
        return ClaudeLLM()
    if wahl == "ollama":
        # Import nur hier: der Claude-Produktionspfad braucht das
        # ollama-Paket (dev-Dependency) nie.
        from bc1_service.ollama_llm import OllamaLLM

        return OllamaLLM()
    if wahl == "gemini":
        # Import nur hier: gleiches Muster — der Claude-Pfad lädt die
        # google-genai-Lib nie.
        from bc1_service.gemini_llm import GeminiLLM

        return GeminiLLM()
    raise RuntimeError(
        f"BC1_LLM='{wahl}' ist unbekannt — erlaubt sind 'claude' (Default), "
        "'ollama' (lokaler Test-/Dev-Ersatz) oder 'gemini' (Gemini API, "
        "GEMINI_API_KEY nötig)."
    )
