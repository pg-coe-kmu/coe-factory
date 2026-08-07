"""Ollama-Adapter hinter dem LLMClient-Protocol des Kerns — Test-/Dev-Ersatz.

Lokales Llama via Ollama: kostenlos, ohne API-Key. Claude bleibt der
Produktionsweg; dieser Adapter entsperrt Echt-LLM-End-to-End-Tests und
erreicht bewusst NICHT Claudes Extraktionsqualität (8B-Modell, kein
Prompt-Tuning). Exceptions fliegen durch — process_turn macht daraus den
fehler_fortsetzbar-Vertrag. format=JSON-Schema (Constrained Decoding)
garantiert valides JSON, temperature 0 macht Läufe deterministisch.
"""
from __future__ import annotations

import json
import os

import ollama

from bc1_core.llm import ExtractionCandidate
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import SessionState
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_FRAGE,
    frage_nutzer_prompt,
)

STANDARD_MODELL = "llama3.1:8b"


class OllamaLLM:
    def __init__(self, client=None, modell: str | None = None) -> None:
        # 120 s statt Claudes 30 s: die erste lokale Anfrage lädt das
        # Modell erst in den Speicher (bis ~30 s auf 16-GB-Hardware).
        self._client = client or ollama.Client(timeout=120.0)
        self._modell = modell or os.environ.get("BC1_OLLAMA_MODELL", STANDARD_MODELL)

    def extract(
        self, message: str, package: UseCasePackage, state: SessionState
    ) -> list[ExtractionCandidate]:
        felder = "\n".join(f"- {f.name}: {f.question}" for f in package.fields)
        inhalt = self._chat(
            [
                {"role": "system", "content": SYSTEM_EXTRAKTION},
                {
                    "role": "user",
                    "content": (
                        f"Felder des Prozessprofils:\n{felder}\n\n"
                        f"Interview-Nachricht:\n{message}\n\n"
                        "Gib alle Feld-Wert-Paare zurück, die diese Nachricht "
                        "belegt — als JSON nach dem vorgegebenen Schema "
                        "(extraktionen: Liste aus feld/wert)."
                    ),
                },
            ],
            format=EXTRAKTIONS_SCHEMA,
        )
        daten = json.loads(inhalt)
        bekannte = {f.name for f in package.fields}
        return [
            ExtractionCandidate(e["feld"], e["wert"].strip())
            for e in daten["extraktionen"]
            if e["feld"] in bekannte and e["wert"].strip()
        ]

    def phrase(self, field: FieldSpec, state: SessionState) -> str:
        inhalt = self._chat([
            {"role": "system", "content": SYSTEM_FRAGE},
            {"role": "user", "content": frage_nutzer_prompt(field, state)},
        ])
        return inhalt.strip()

    def _chat(self, nachrichten: list[dict], format=None) -> str:
        try:
            antwort = self._client.chat(
                model=self._modell,
                messages=nachrichten,
                format=format,
                stream=False,
                # Primärdoku-Empfehlung: temperature 0 für Determinismus.
                options={"temperature": 0, "num_predict": 4096},
            )
        except ConnectionError as fehler:
            # Die ollama-Lib übersetzt httpx.ConnectError selbst in den
            # builtin ConnectionError — deshalb DIESER Typ (Gesamt-Review 07.08.).
            raise RuntimeError(
                f"Ollama ist nicht erreichbar ({fehler}). Läuft `ollama serve`?"
            ) from fehler
        if antwort.done_reason == "length":
            raise RuntimeError("LLM-Antwort abgeschnitten (num_predict)")
        if not antwort.message.content:
            raise RuntimeError("LLM-Antwort ohne Inhalt")
        return antwort.message.content
