from __future__ import annotations
from bc1_core.types import SessionState, SessionStatus
from bc1_core.package import UseCasePackage
from bc1_core.store import StateStore
from bc1_core.llm import LLMClient
from bc1_core.extractor import extract_and_merge
from bc1_core.confidence import confidence_check, ConfidenceResult
from bc1_core.dialog import decide_next

def _profil(state: SessionState, conf: ConfidenceResult) -> dict:
    felder = {
        name: {"wert": fv.value, "status": fv.status.value,
               "quelle": fv.source_message_id, "grund": fv.grund,
               "kandidaten": [{"wert": k.value, "quelle": k.source_message_id}
                              for k in fv.candidates]}
        for name, fv in state.values.items()
    }
    return {
        "felder": felder,
        "vollstaendigkeit": conf.completeness,
        "ungeloeste_felder": conf.ungeloeste_felder,
        "schema_version": state.schema_version,
    }

def process_turn(store: StateStore, llm: LLMClient, package: UseCasePackage,
                 session_id: str, message_id: str, message: str) -> dict:
    state = store.load(session_id) or SessionState(session_id, package.schema_version)

    if message_id in state.processed_message_ids:
        unbeantwortet = state.last_response is None
        ist_letzte = bool(state.raw_log) and state.raw_log[-1][0] == message_id
        if not (unbeantwortet and ist_letzte):
            # Beantwortete Nachricht (n8n-/HTTP-Retry) → gespeicherte Antwort.
            # Degenerierter Doppelfehler (alte Nachricht wiederholt, während
            # die letzte unbeantwortet ist) liefert wie der Plan None.
            return state.last_response
        # Geloggt, aber nie beantwortet (Crash zwischen den Saves):
        # Turn fortsetzen, ohne erneut zu loggen.
    else:
        # Rohnachricht zuerst sichern (vor jedem LLM-Aufruf); bis zur
        # finalen Antwort gilt der Turn als offen (last_response = None).
        state.raw_log.append((message_id, message))
        state.processed_message_ids.add(message_id)
        state.last_response = None
        store.save(state)

    state.rounds += 1
    extract_and_merge(state, message, message_id, package, llm)
    conf = confidence_check(state, package)
    decision = decide_next(state, package, conf, llm)

    if decision.done:
        state.status = SessionStatus.FERTIG
        # decide_next kann Felder frisch auf UNGELOEST gecappt haben —
        # fürs Gate-0-Payload zählt der Stand NACH der Entscheidung.
        conf = confidence_check(state, package)
        resp = {"status": "fertig", "payload": _profil(state, conf)}
    else:
        state.status = SessionStatus.WARTET
        resp = {"status": "frage",
                "payload": {"naechste_frage": decision.question,
                            "feld": decision.next_field}}

    state.last_response = resp
    store.save(state)
    return resp
