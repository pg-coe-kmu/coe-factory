"""Claude-Adapter hinter dem LLMClient-Protocol des Kerns.

Der Kern kennt diese Klasse nicht (Protocol, strukturell). Retries/Timeout
bewusst eng (Design-Spec: Chat darf nicht in n8n-Timeouts laufen); bei
anhaltendem Ausfall fliegt die Exception — process_turn macht daraus den
fehler_fortsetzbar-Vertrag. Structured Outputs garantieren valides JSON.
"""
from __future__ import annotations

import json
import os

import anthropic

from bc1_core.llm import ExtractionCandidate
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import SessionState

STANDARD_MODELL = "claude-opus-5"

_EXTRAKTIONS_SCHEMA = {
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

_SYSTEM_EXTRAKTION = (
    "Du extrahierst Fakten aus einer Interview-Antwort für ein Prozessprofil. "
    "Extrahiere NUR, was die Nachricht wirklich belegt — nichts erfinden, "
    "nichts aus Vorwissen ergänzen. Werte wörtlich bzw. minimal normalisiert."
)

_SYSTEM_FRAGE = (
    "Du führst ein freundliches, professionelles Prozess-Interview auf Deutsch. "
    "Antworte NUR mit der Frage selbst — ohne Einleitung, ohne Anführungszeichen."
)


class ClaudeLLM:
    def __init__(self, client=None, modell: str | None = None) -> None:
        self._client = client or anthropic.Anthropic(timeout=30.0, max_retries=1)
        self._modell = modell or os.environ.get("BC1_CLAUDE_MODELL", STANDARD_MODELL)

    def extract(
        self, message: str, package: UseCasePackage, state: SessionState
    ) -> list[ExtractionCandidate]:
        felder = "\n".join(f"- {f.name}: {f.question}" for f in package.fields)
        antwort = self._client.messages.create(
            model=self._modell,
            max_tokens=4096,
            system=_SYSTEM_EXTRAKTION,
            output_config={
                "format": {"type": "json_schema", "schema": _EXTRAKTIONS_SCHEMA},
                # Triviale Aufgabe: ohne effort low denkt das Modell per
                # Default lange und verbraucht das max_tokens-Budget.
                "effort": "low",
            },
            messages=[{
                "role": "user",
                "content": (
                    f"Felder des Prozessprofils:\n{felder}\n\n"
                    f"Interview-Nachricht:\n{message}\n\n"
                    "Gib alle Feld-Wert-Paare zurück, die diese Nachricht belegt."
                ),
            }],
        )
        daten = json.loads(self._text_inhalt(antwort))
        bekannte = {f.name for f in package.fields}
        return [
            ExtractionCandidate(e["feld"], e["wert"].strip())
            for e in daten["extraktionen"]
            if e["feld"] in bekannte and e["wert"].strip()
        ]

    def phrase(self, field: FieldSpec, state: SessionState) -> str:
        bisher = state.values.get(field.name)
        hinweis = (
            "\nEs ist eine Nachfrage: Die bisherige Antwort war unklar oder "
            "ungültig — formuliere die Frage anders und konkreter."
            # Der Dialog zählt attempts VOR diesem Aufruf hoch: 1 = Erstfrage,
            # ab 2 ist es wirklich eine Nachfrage.
            if bisher is not None and bisher.attempts > 1
            else ""
        )
        antwort = self._client.messages.create(
            model=self._modell,
            max_tokens=4096,
            system=_SYSTEM_FRAGE,
            output_config={"effort": "low"},   # eine Frage formulieren, mehr nicht
            messages=[{
                "role": "user",
                "content": (
                    "Formuliere genau eine Chat-Frage für dieses Feld:\n"
                    f"Feld: {field.name}\nKernfrage: {field.question}{hinweis}"
                ),
            }],
        )
        return self._text_inhalt(antwort).strip()

    @staticmethod
    def _text_inhalt(antwort) -> str:
        if antwort.stop_reason == "refusal":
            raise RuntimeError("LLM hat die Anfrage abgelehnt (refusal)")
        if antwort.stop_reason == "max_tokens":
            # Abgeschnitten = unbrauchbar (halbes JSON, halbe Frage). Ohne
            # diesen Guard scheitert erst json.loads — mit irreführender Meldung.
            raise RuntimeError("LLM-Antwort abgeschnitten (max_tokens)")
        for block in antwort.content:
            if block.type == "text":
                return block.text
        raise RuntimeError("LLM-Antwort ohne Textblock")
