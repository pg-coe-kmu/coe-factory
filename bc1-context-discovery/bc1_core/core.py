from __future__ import annotations
from bc1_core.types import FieldValue, SessionState, SessionStatus
from bc1_core.package import UseCasePackage
from bc1_core.store import StateStore
from bc1_core.llm import LLMClient
from bc1_core.extractor import extract_and_merge
from bc1_core.confidence import confidence_check, ConfidenceResult
from bc1_core.dialog import decide_next

def _profil(state: SessionState, conf: ConfidenceResult,
            package: UseCasePackage) -> dict:
    # Über die Paketfelder iterieren, nicht über state.values: Gate 0 sieht
    # das ganze Paket (nie berührte Felder als FEHLT), Fremdeinträge nicht —
    # konsistent zu conf.statuses.
    felder = {}
    for spec in package.fields:
        fv = state.values.get(spec.name) or FieldValue()
        felder[spec.name] = {
            "wert": fv.value, "status": fv.status.value,
            "quelle": fv.source_message_id, "grund": fv.grund,
            "kandidaten": [{"wert": k.value, "quelle": k.source_message_id}
                           for k in fv.candidates]}
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
        if message_id in state.antworten:
            # Beantwortete Nachricht (n8n-/HTTP-Retry) → IHRE Antwort,
            # nicht die der neuesten Nachricht (Idempotenz je message_id).
            return state.antworten[message_id]
        # Geloggt, aber nie beantwortet (Crash zwischen den Saves):
        # Turn fortsetzen, ohne erneut zu loggen. Das kann nur die
        # zuletzt geloggte Nachricht sein — Turns laufen sequenziell.
    elif state.status is SessionStatus.FERTIG:
        # Nach der Gate-0-Übergabe gibt es keinen Übergang zurück (Spec B3).
        # Neue Nachrichten erhalten idempotent das Abschlussergebnis;
        # aktives Zurückweisen ist Sache der Transportschicht (P2).
        return state.antworten[state.raw_log[-1][0]]
    else:
        # Rohnachricht zuerst sichern (vor jedem LLM-Aufruf).
        state.raw_log.append((message_id, message))
        state.processed_message_ids.add(message_id)
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
        resp = {"status": "fertig", "payload": _profil(state, conf, package)}
    else:
        state.status = SessionStatus.WARTET
        resp = {"status": "frage",
                "payload": {"naechste_frage": decision.question,
                            "feld": decision.next_field}}

    state.antworten[message_id] = resp
    store.save(state)
    return resp
