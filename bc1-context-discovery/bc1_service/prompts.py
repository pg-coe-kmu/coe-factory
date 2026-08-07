"""Geteilte Prompt-Bausteine der LLM-Adapter (Claude, Ollama).

Das Extraktionsschema ist de facto ein Wire-Vertrag mit dem Extractor,
und der Frage-Prompt (inkl. Nachfrage-Hinweis) ist Dialog-Verhalten —
deshalb EIN Ort statt Kopien pro Adapter (Drift-Risiko).
"""
from __future__ import annotations

from bc1_core.package import FieldSpec
from bc1_core.types import SessionState

EXTRAKTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "extraktionen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feld": {"type": "string"},
                    "wert": {"type": "string"},
                },
                "required": ["feld", "wert"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["extraktionen"],
    "additionalProperties": False,
}

SYSTEM_EXTRAKTION = (
    "Du extrahierst Fakten aus einer Interview-Antwort für ein Prozessprofil. "
    "Extrahiere NUR, was die Nachricht wirklich belegt — nichts erfinden, "
    "nichts aus Vorwissen ergänzen. Werte wörtlich bzw. minimal normalisiert."
)

SYSTEM_FRAGE = (
    "Du führst ein freundliches, professionelles Prozess-Interview auf Deutsch. "
    "Antworte NUR mit der Frage selbst — ohne Einleitung, ohne Anführungszeichen."
)


def frage_nutzer_prompt(field: FieldSpec, state: SessionState) -> str:
    """Nutzer-Prompt für die Frage-Formulierung — von beiden Adaptern geteilt."""
    bisher = state.values.get(field.name)
    hinweis = (
        "\nEs ist eine Nachfrage: Die bisherige Antwort war unklar oder "
        "ungültig — formuliere die Frage anders und konkreter."
        # Der Dialog zählt attempts VOR diesem Aufruf hoch: 1 = Erstfrage,
        # ab 2 ist es wirklich eine Nachfrage.
        if bisher is not None and bisher.attempts > 1
        else ""
    )
    return (
        "Formuliere genau eine Chat-Frage für dieses Feld:\n"
        f"Feld: {field.name}\nKernfrage: {field.question}{hinweis}"
    )
