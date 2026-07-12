from __future__ import annotations
from dataclasses import dataclass
from bc1_core.types import FieldStatus, SessionState
from bc1_core.package import UseCasePackage

@dataclass
class ConfidenceResult:
    statuses: dict[str, FieldStatus]
    completeness: float
    offene_pflichtfelder: list[str]
    ungeloeste_felder: list[str]

def confidence_check(state: SessionState, package: UseCasePackage) -> ConfidenceResult:
    statuses: dict[str, FieldStatus] = {}
    for spec in package.fields:
        fv = state.values.get(spec.name)
        statuses[spec.name] = fv.status if fv is not None else FieldStatus.FEHLT

    required = package.required_fields()
    erfuellt = sum(1 for s in required if statuses[s.name] is FieldStatus.GUELTIG)
    completeness = erfuellt / len(required) if required else 1.0

    offen = [s.name for s in required
             if statuses[s.name] not in (FieldStatus.GUELTIG, FieldStatus.UNGELOEST)]
    ungeloest = [name for name, st in statuses.items() if st is FieldStatus.UNGELOEST]
    return ConfidenceResult(statuses, completeness, offen, ungeloest)
