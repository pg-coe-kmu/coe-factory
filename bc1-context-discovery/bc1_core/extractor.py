from __future__ import annotations
from bc1_core.types import Candidate, FieldStatus, FieldValue, SessionState
from bc1_core.package import UseCasePackage, FieldSpec
from bc1_core.llm import LLMClient

def _status_for(spec: FieldSpec, value: str) -> FieldStatus:
    # Policy: ein werfender Validator macht den Wert UNGUELTIG, bricht aber
    # nie den Turn ab — sonst ginge die Nachricht nach Raw-First-Save (Task 8)
    # beim Idempotenz-Replay dauerhaft verloren.
    pruefer = spec.validator if spec.validator is not None else spec.typ.validator
    try:
        gueltig = pruefer(value)
    except Exception:
        return FieldStatus.UNGUELTIG
    return FieldStatus.GUELTIG if gueltig else FieldStatus.UNGUELTIG

def _merke_kandidat(fv: FieldValue, wert: str, quelle: str) -> None:
    # Dedup nach Wert: die erste Quelle eines Werts bleibt maßgeblich.
    if all(k.value != wert for k in fv.candidates):
        fv.candidates.append(Candidate(wert, quelle))

def extract_and_merge(state: SessionState, message: str, message_id: str,
                      package: UseCasePackage, llm: LLMClient) -> None:
    for cand in llm.extract(message, package, state):
        spec = package.field(cand.field_name)
        if spec is None:
            continue
        # Normalisierung VOR dem Merge: Vergleiche, Klärung und Kandidaten
        # arbeiten auf dem normalisierten Wert; gespeichert wird er auch.
        wert = spec.typ.normalisiere(cand.value)
        fv = state.values.get(cand.field_name)
        if fv is None or fv.value is None:
            state.values[cand.field_name] = FieldValue(
                value=wert,
                status=_status_for(spec, wert),
                source_message_id=message_id,
                # Nachfrage-Zähler gehört dem Dialog (Task 7) — beim Befüllen
                # eines angefragten Felds nicht zurücksetzen (Cap-Politik).
                attempts=fv.attempts if fv is not None else 0,
            )
        elif fv.value == wert:
            # Erneute Nennung desselben Werts: für UNKLAR ist das die Klärung
            # (Spec B4 „Nutzer klären lassen"), sonst No-op.
            if fv.status is FieldStatus.UNKLAR:
                fv.status = _status_for(spec, wert)
        elif (fv.status is FieldStatus.UNKLAR
              and any(k.value == wert for k in fv.candidates)):
            # Klärung zugunsten eines Kandidaten (Spec B4): Tausch — der alte
            # Wert bleibt mit seiner Quelle als Kandidat, nichts geht verloren.
            fv.candidates = [k for k in fv.candidates if k.value != wert]
            _merke_kandidat(fv, fv.value, fv.source_message_id)
            fv.value = wert
            fv.status = _status_for(spec, wert)
            fv.source_message_id = message_id
        elif fv.status is FieldStatus.UNGUELTIG:
            # Korrektur: UNGUELTIG ist nicht bestätigt → ersetzen, alter Wert
            # bleibt als Kandidat — mit der Quelle, aus der er stammte.
            _merke_kandidat(fv, fv.value, fv.source_message_id)
            fv.value = wert
            fv.status = _status_for(spec, wert)
            fv.source_message_id = message_id
        else:
            _merke_kandidat(fv, wert, message_id)
            fv.status = FieldStatus.UNKLAR
