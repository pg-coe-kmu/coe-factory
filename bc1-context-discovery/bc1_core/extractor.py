from __future__ import annotations
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import UseCasePackage, FieldSpec
from bc1_core.llm import LLMClient

def _status_for(spec: FieldSpec, value: str) -> FieldStatus:
    if spec.validator is not None and not spec.validator(value):
        return FieldStatus.UNGUELTIG
    return FieldStatus.GUELTIG

def extract_and_merge(state: SessionState, message: str, message_id: str,
                      package: UseCasePackage, llm: LLMClient) -> None:
    for cand in llm.extract(message, package, state):
        spec = package.field(cand.field_name)
        if spec is None:
            continue
        fv = state.values.get(cand.field_name)
        if fv is None or fv.value is None:
            state.values[cand.field_name] = FieldValue(
                value=cand.value,
                status=_status_for(spec, cand.value),
                source_message_id=message_id,
            )
        elif fv.value == cand.value:
            continue
        elif fv.status is FieldStatus.UNGUELTIG:
            # Korrektur: UNGUELTIG ist nicht bestätigt → ersetzen, alter Wert bleibt als Kandidat.
            if fv.value not in fv.candidates:
                fv.candidates.append(fv.value)
            fv.value = cand.value
            fv.status = _status_for(spec, cand.value)
            fv.source_message_id = message_id
        else:
            if cand.value not in fv.candidates:
                fv.candidates.append(cand.value)
            fv.status = FieldStatus.UNKLAR
