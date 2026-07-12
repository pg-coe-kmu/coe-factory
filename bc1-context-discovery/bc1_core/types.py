from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

class FieldStatus(str, Enum):
    FEHLT = "fehlt"
    GUELTIG = "gueltig"
    UNGUELTIG = "ungueltig"
    UNKLAR = "unklar"
    UNGELOEST = "ungeloest"

class SessionStatus(str, Enum):
    AKTIV = "aktiv"
    WARTET = "wartet_auf_antwort"
    FERTIG = "fertig"
    FEHLER = "fehler_fortsetzbar"

@dataclass
class FieldValue:
    value: str | None = None
    status: FieldStatus = FieldStatus.FEHLT
    source_message_id: str | None = None
    candidates: list[str] = field(default_factory=list)
    attempts: int = 0

@dataclass
class SessionState:
    session_id: str
    schema_version: str
    status: SessionStatus = SessionStatus.AKTIV
    version: int = 0
    rounds: int = 0
    values: dict[str, FieldValue] = field(default_factory=dict)
    processed_message_ids: set[str] = field(default_factory=set)
    raw_log: list[tuple[str, str]] = field(default_factory=list)
    last_response: dict | None = None
