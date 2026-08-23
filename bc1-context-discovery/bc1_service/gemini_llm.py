"""Gemini-Adapter hinter dem LLMClient-Protocol des Kerns.

Dritter Adapter neben Claude und Ollama — gleiche Naht, geteilte Prompts.
Free-Tier-Realität (20 Requests/Tag je Modell): SDK-Retries explizit AUS
(SDK-Default wäre 5 Versuche!), kein eigener Retry; ein 429 wird zur
neutralen Kontingent-Diagnose („Rate-Limit" kann Minuten-, Tages- oder
Token-Limit sein) und fliegt durch — process_turn macht daraus den
fehler_fortsetzbar-Vertrag. response_json_schema erzwingt valides JSON
(deckt das volle EXTRAKTIONS_SCHEMA inkl. additionalProperties ab).
SDK-Semantik (verifiziert an google-genai 2.17.0): HttpOptions.timeout
ist in MILLISEKUNDEN; HttpRetryOptions.attempts zählt inkl. Erstversuch.
"""
from __future__ import annotations

import json
import os

from google import genai
from google.genai import errors, types

from bc1_core.gespraech import TurnKontext
from bc1_core.llm import ExtractionCandidate
from bc1_core.package import UseCasePackage
from bc1_core.types import SessionState
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_GESPRAECH,
    gespraech_nutzer_prompt,
)

# gemini-2.5-flash ist fuer Neukonten gesperrt (404 "no longer available to
# new users", live 23.08.2026) — Default daher aus der 3er-Generation.
STANDARD_MODELL = "gemini-3.7-flash"
# FESTER Text ohne Interpolation — weder Key noch Environment einbetten
# (Sentinel-Test pinnt das).
KEY_FEHLT = (
    "GEMINI_API_KEY ist nicht gesetzt. Ohne Key kann der Gemini-Adapter "
    "(BC1_LLM=gemini) nicht starten."
)
# Gepinnte Generierungs-Konfiguration je Modellfamilie (Spec: Versprachlichen
# ist kein Knobeln — niedrigste Thinking-Stufe, deterministisch wo möglich):
# 2.5-Familie: thinking_budget 0 = AUS, temperature 0.
# 3er-Generation (gemini-3-… und gemini-3.5/3.6/3.7-…): niedrigste
# unterstützte Stufe ist LOW ("minimal … returns an error"), und die
# Migrationsanleitung verlangt "Strip temperature" → None = nicht senden.
# (API-Doku-Stand 23.08.2026; beide Punkt-/Strich-Präfixe nötig, weil
# "gemini-3-" den Punkt in "gemini-3.7" nicht matcht.)
_FAMILIEN = {
    "gemini-2.5-": (types.ThinkingConfig(thinking_budget=0), 0),
    "gemini-3-": (types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW), None),
    "gemini-3.": (types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW), None),
}


def _familien_konfig(modell: str) -> tuple[types.ThinkingConfig, int | None]:
    for praefix, konfig in _FAMILIEN.items():
        if modell.startswith(praefix):
            return konfig
    # Kein stilles Weglassen (Spec): unbekannte Familie = ungeklärte Semantik.
    raise RuntimeError(
        f"BC1_GEMINI_MODELL '{modell}': keine gepinnte Thinking-Konfiguration "
        "für diese Modellfamilie (bekannt: gemini-2.5-*, gemini-3-*, gemini-3.*)."
    )


class GeminiLLM:
    def __init__(self, client=None, modell: str | None = None) -> None:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if client is None and not key:
            # Fail-fast beim Dienststart statt fehler_fortsetzbar beim
            # ersten Turn; Key-Prüfung NUR ohne injizierten Client (Stubs).
            raise RuntimeError(KEY_FEHLT)
        self._client = client or genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=30_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        self._modell = modell or os.environ.get("BC1_GEMINI_MODELL", STANDARD_MODELL)
        self._thinking, self._temperature = _familien_konfig(self._modell)

    def extract(
        self, message: str, package: UseCasePackage, state: SessionState
    ) -> list[ExtractionCandidate]:
        felder = "\n".join(f"- {f.name}: {f.question}" for f in package.fields)
        inhalt = self._generate(
            system=SYSTEM_EXTRAKTION,
            nutzer=(
                f"Felder des Prozessprofils:\n{felder}\n\n"
                f"Interview-Nachricht:\n{message}\n\n"
                "Gib alle Feld-Wert-Paare zurück, die diese Nachricht belegt."
            ),
            json_schema=EXTRAKTIONS_SCHEMA,
        )
        daten = json.loads(inhalt)
        bekannte = {f.name for f in package.fields}
        return [
            ExtractionCandidate(e["feld"], e["wert"].strip())
            for e in daten["extraktionen"]
            if e["feld"] in bekannte and e["wert"].strip()
        ]

    def antworte(self, kontext: TurnKontext) -> str:
        return self._generate(
            system=SYSTEM_GESPRAECH, nutzer=gespraech_nutzer_prompt(kontext)
        ).strip()

    def _generate(self, system: str, nutzer: str, json_schema=None) -> str:
        konfig = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self._temperature,
            max_output_tokens=4096,
            thinking_config=self._thinking,
            response_mime_type=(
                "application/json" if json_schema is not None else None
            ),
            response_json_schema=json_schema,
        )
        try:
            antwort = self._client.models.generate_content(
                model=self._modell, contents=nutzer, config=konfig
            )
        except errors.ClientError as fehler:
            if fehler.code == 429:
                # Neutrale Diagnose für Logs/Abnahme-Protokoll; /turn zeigt
                # dem Nutzer weiterhin den generischen fehler_fortsetzbar-
                # Text (der Kern verwirft Exception-Texte bewusst).
                raise RuntimeError(
                    "Gemini-Kontingent/Rate-Limit erreicht (HTTP 429)"
                ) from None
            raise
        feedback = getattr(antwort, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            # Gemini hat den PROMPT blockiert (keine Kandidaten) — eigener
            # fester Text statt generischem „ohne Kandidaten"; KEINE
            # Feedback-Details interpolieren (könnten Details verraten).
            raise RuntimeError("LLM-Anfrage blockiert (Prompt-Sicherheitsfilter)")
        if not antwort.candidates:
            raise RuntimeError("LLM-Antwort ohne Kandidaten")
        grund = antwort.candidates[0].finish_reason
        if grund == types.FinishReason.MAX_TOKENS:
            # Abgeschnitten = unbrauchbar (halbes JSON, halbe Frage).
            raise RuntimeError("LLM-Antwort abgeschnitten (max_output_tokens)")
        if grund != types.FinishReason.STOP:
            # SAFETY/PROHIBITED_CONTENT/RECITATION/…: Ablehnung statt Inhalt.
            raise RuntimeError(f"LLM hat nicht normal geendet ({grund})")
        inhalt = antwort.text
        if not inhalt or not inhalt.strip():
            raise RuntimeError("LLM-Antwort ohne Inhalt")
        return inhalt
