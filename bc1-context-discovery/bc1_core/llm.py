from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from bc1_core.types import SessionState
from bc1_core.package import UseCasePackage, FieldSpec
from bc1_core.gespraech import TurnKontext

@dataclass(frozen=True)
class ExtractionCandidate:
    field_name: str
    value: str

class LLMClient(Protocol):
    def extract(self, message: str, package: UseCasePackage,
                state: SessionState) -> list[ExtractionCandidate]: ...
    def phrase(self, field: FieldSpec, state: SessionState) -> str: ...
    def antworte(self, kontext: TurnKontext) -> str: ...

class FakeLLM:
    """Skript-gesteuertes LLM für deterministische Tests."""
    def __init__(self, extractions: dict[str, list[ExtractionCandidate]] | None = None) -> None:
        self._extractions = extractions or {}

    def extract(self, message: str, package: UseCasePackage,
                state: SessionState) -> list[ExtractionCandidate]:
        return list(self._extractions.get(message, []))

    def phrase(self, field: FieldSpec, state: SessionState) -> str:
        return field.question

    def antworte(self, kontext: TurnKontext) -> str:
        # Deterministische Komposition — Test-Vertrag: alle neu_erfasst-Werte
        # und die Kernfrage (bzw. Übersicht/Offenes) erscheinen WÖRTLICH.
        teile = []
        if kontext.neu_erfasst:
            teile.append("Notiert: "
                         + "; ".join(e.wert for e in kontext.neu_erfasst) + ".")
        if kontext.ist_abschluss:
            teile.append("Zusammenfassung: "
                         + "; ".join(e.wert for e in kontext.profil_uebersicht)
                         + ".")
            if kontext.offene_fragen:
                teile.append("Offen: " + " | ".join(kontext.offene_fragen))
        else:
            teile.append(kontext.naechste_frage)
        return " ".join(teile)
