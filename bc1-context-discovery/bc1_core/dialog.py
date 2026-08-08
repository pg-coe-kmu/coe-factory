from __future__ import annotations
from dataclasses import dataclass
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import UseCasePackage
from bc1_core.confidence import ConfidenceResult
from bc1_core.llm import LLMClient

MAX_ATTEMPTS_PER_FIELD = 2
MAX_ROUNDS = 20

# Wire-Werte für FieldValue.grund (Spec B4) — Vertrag Richtung BC2.
GRUND_NACHFRAGE_LIMIT = "nachfrage_limit_erreicht"
GRUND_RUNDEN_LIMIT = "runden_limit_erreicht"

@dataclass
class Decision:
    done: bool
    next_field: str | None = None
    question: str | None = None

def decide_next(state: SessionState, package: UseCasePackage,
                conf: ConfidenceResult, llm: LLMClient) -> Decision:
    # Cap-Politik: über dem Limit -> als ungeloest markieren
    for name in conf.offene_pflichtfelder:
        fv = state.values.get(name)
        if fv is not None and fv.attempts >= MAX_ATTEMPTS_PER_FIELD:
            fv.status = FieldStatus.UNGELOEST
            fv.grund = GRUND_NACHFRAGE_LIMIT

    offen = [n for n in conf.offene_pflichtfelder
             if state.values.get(n) is None
             or state.values[n].status is not FieldStatus.UNGELOEST]

    if state.rounds >= package.max_rounds:
        # Runden-Limit: alle noch offenen Pflichtfelder aufgeben — auch nie
        # angefragte —, damit sie im Gate-0-Payload sichtbar bleiben (Spec Z. 81).
        for name in offen:
            fv = state.values.get(name)
            if fv is None:
                fv = FieldValue()
                state.values[name] = fv
            fv.status = FieldStatus.UNGELOEST
            fv.grund = GRUND_RUNDEN_LIMIT
        return Decision(done=True)
    if not offen:
        return Decision(done=True)

    target = offen[0]
    fv = state.values.get(target)
    if fv is None:
        fv = FieldValue()
        state.values[target] = fv
    fv.attempts += 1
    return Decision(done=False, next_field=target,
                    question=llm.phrase(package.field(target), state))
