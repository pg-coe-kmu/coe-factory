"""JSON-Serialisierung für SessionState — der Roundtrip für den persistenten Store.

Reine Stdlib. Erzwingt beim Deserialisieren die Invariante
"value gesetzt ⇒ source_message_id gesetzt" (Ledger, Pflichtpunkt 2 aus #123).
"""
from __future__ import annotations

from bc1_core.types import (
    Candidate,
    FieldStatus,
    FieldValue,
    SessionState,
    SessionStatus,
)


def state_to_dict(state: SessionState) -> dict:
    # antworten wird by-reference gereicht (keine Kopie) — Konsumenten muessen
    # synchron serialisieren, solange der Caller den State nicht weiter
    # mutiert; siehe PostgresStateStore.save.
    return {
        "session_id": state.session_id,
        "schema_version": state.schema_version,
        "paket_name": state.paket_name,
        "company_id": state.company_id,
        "status": state.status.value,
        "version": state.version,
        "rounds": state.rounds,
        "values": {name: _feldwert_to_dict(fw) for name, fw in state.values.items()},
        "processed_message_ids": sorted(state.processed_message_ids),
        "raw_log": [list(eintrag) for eintrag in state.raw_log],
        "antworten": state.antworten,
    }


def state_from_dict(daten: dict) -> SessionState:
    return SessionState(
        session_id=daten["session_id"],
        schema_version=daten["schema_version"],
        paket_name=daten["paket_name"],
        company_id=daten.get("company_id"),
        status=SessionStatus(daten["status"]),
        version=daten["version"],
        rounds=daten["rounds"],
        values={
            name: _feldwert_from_dict(name, fw)
            for name, fw in daten["values"].items()
        },
        processed_message_ids=set(daten["processed_message_ids"]),
        raw_log=[(mid, text) for mid, text in daten["raw_log"]],
        antworten=daten["antworten"],
    )


def _feldwert_to_dict(fw: FieldValue) -> dict:
    return {
        "value": fw.value,
        "status": fw.status.value,
        "source_message_id": fw.source_message_id,
        "candidates": [
            {"value": k.value, "source_message_id": k.source_message_id}
            for k in fw.candidates
        ],
        "attempts": fw.attempts,
        "grund": fw.grund,
    }


def _feldwert_from_dict(feldname: str, daten: dict) -> FieldValue:
    # Leerstring zaehlt wie fehlend: eine leere Quelle ist keine Quelle.
    if daten["value"] is not None and not daten["source_message_id"]:
        raise ValueError(
            f"Feld {feldname}: value gesetzt, aber source_message_id fehlt"
        )
    kandidaten = []
    for k in daten["candidates"]:
        if not k["value"] or not k["source_message_id"]:
            raise ValueError(
                f"Feld {feldname}: Kandidat ohne value oder source_message_id"
            )
        kandidaten.append(Candidate(k["value"], k["source_message_id"]))
    return FieldValue(
        value=daten["value"],
        status=FieldStatus(daten["status"]),
        source_message_id=daten["source_message_id"],
        candidates=kandidaten,
        attempts=daten["attempts"],
        grund=daten["grund"],
    )
