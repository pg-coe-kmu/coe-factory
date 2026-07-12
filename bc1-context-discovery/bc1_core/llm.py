from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from bc1_core.types import SessionState
from bc1_core.package import UseCasePackage, FieldSpec

@dataclass(frozen=True)
class ExtractionCandidate:
    field_name: str
    value: str

class LLMClient(Protocol):
    def extract(self, message: str, package: UseCasePackage,
                state: SessionState) -> list[ExtractionCandidate]: ...
    def phrase(self, field: FieldSpec, state: SessionState) -> str: ...

class FakeLLM:
    """Skript-gesteuertes LLM für deterministische Tests."""
    def __init__(self, extractions: dict[str, list[ExtractionCandidate]] | None = None) -> None:
        self._extractions = extractions or {}

    def extract(self, message: str, package: UseCasePackage,
                state: SessionState) -> list[ExtractionCandidate]:
        return list(self._extractions.get(message, []))

    def phrase(self, field: FieldSpec, state: SessionState) -> str:
        return field.question
