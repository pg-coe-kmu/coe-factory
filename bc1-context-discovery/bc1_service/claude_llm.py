"""Claude-Adapter hinter dem LLMClient-Protocol des Kerns.

Der Kern kennt diese Klasse nicht (Protocol, strukturell). Retries/Timeout
bewusst eng (Design-Spec: Chat darf nicht in n8n-Timeouts laufen); bei
anhaltendem Ausfall fliegt die Exception — process_turn macht daraus den
fehler_fortsetzbar-Vertrag. Structured Outputs garantieren valides JSON.
"""
from __future__ import annotations

import json
import logging
import os

import anthropic

from bc1_core.gespraech import TurnKontext
from bc1_core.llm import ExtractionCandidate
from bc1_core.package import UseCasePackage
from bc1_core.protokoll import aktuelle_korrelation
from bc1_core.types import SessionState
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_GESPRAECH,
    extraktions_nutzer_prompt,
    gespraech_nutzer_prompt,
)

STANDARD_MODELL = "claude-opus-5"

log = logging.getLogger("bc1.ki")


def _wiederholung_protokollieren(anfrage, weiter):
    # B7 Teil 2: SDK-Middleware (anthropic._middleware) — laeuft im Wiederholungskreis
    # des SDK einmal je Versuch, im aufrufenden Thread; der erste Versuch hat 0.
    if anfrage.retries_taken:
        log.warning("ki_wiederholung korrelation=%s anbieter=claude versuch=%d",
                    aktuelle_korrelation.get(), anfrage.retries_taken + 1)
    return weiter(anfrage)


class ClaudeLLM:
    def __init__(self, client=None, modell: str | None = None) -> None:
        self._client = client or anthropic.Anthropic(
            timeout=30.0, max_retries=1, middleware=[_wiederholung_protokollieren])
        self._modell = modell or os.environ.get("BC1_CLAUDE_MODELL", STANDARD_MODELL)

    def extract(
        self, message: str, package: UseCasePackage, state: SessionState
    ) -> list[ExtractionCandidate]:
        antwort = self._client.messages.create(
            model=self._modell,
            max_tokens=4096,
            system=SYSTEM_EXTRAKTION,
            output_config={
                "format": {"type": "json_schema", "schema": EXTRAKTIONS_SCHEMA},
                # Triviale Aufgabe: ohne effort low denkt das Modell per
                # Default lange und verbraucht das max_tokens-Budget.
                "effort": "low",
            },
            messages=[{
                "role": "user",
                "content": extraktions_nutzer_prompt(message, package, state),
            }],
        )
        daten = json.loads(self._text_inhalt(antwort))
        bekannte = {f.name for f in package.fields}
        return [
            ExtractionCandidate(e["feld"], e["wert"].strip())
            for e in daten["extraktionen"]
            if e["feld"] in bekannte and e["wert"].strip()
        ]

    def antworte(self, kontext: TurnKontext) -> str:
        antwort = self._client.messages.create(
            model=self._modell,
            max_tokens=4096,
            system=SYSTEM_GESPRAECH,
            output_config={"effort": "low"},   # Versprachlichen, nicht knobeln
            messages=[{
                "role": "user",
                "content": gespraech_nutzer_prompt(kontext),
            }],
        )
        text = self._text_inhalt(antwort).strip()
        if not text:
            # Leer-Guard auf den GESTRIPPTEN Inhalt (Spec §5; Lektion aus dem
            # Ollama-Review): eine leere Antwort darf nie beim Nutzer landen.
            raise RuntimeError("LLM-Antwort ohne Inhalt")
        return text

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
