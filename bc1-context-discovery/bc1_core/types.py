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
    # Definiertes Ende, wenn die Prozess-Identitaet ungeklaert bleibt (Spec K0).
    # Terminal wie FERTIG — aber ohne Profil und ohne 503.
    ABGEBROCHEN_OHNE_IDENTITAET = "abgebrochen_ohne_identitaet"


# Zustaende, aus denen es keinen Weg zurueck gibt. Replay-Weiche (core) und
# Terminal-Gate (api) pruefen BEIDE, nie nur FERTIG.
TERMINALE_STATUS = (SessionStatus.FERTIG, SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET)


class Ergebnis(str, Enum):
    """Ausgang eines Turns. Ersetzt das frühere Decision.done (nur zwei Ausgänge)."""
    WEITER = "weiter"
    FERTIG = "fertig"
    ABGEBROCHEN_OHNE_IDENTITAET = "abgebrochen_ohne_identitaet"

# Design-Spec B2/B4: jeder Kandidat behält seine Quelle (message_id).
@dataclass(frozen=True)
class Candidate:
    value: str
    source_message_id: str

@dataclass
class FieldValue:
    value: str | None = None
    status: FieldStatus = FieldStatus.FEHLT
    source_message_id: str | None = None
    candidates: list[Candidate] = field(default_factory=list)
    attempts: int = 0
    # Nur bei UNGELOEST gesetzt: warum das Feld aufgegeben wurde (Spec B4).
    grund: str | None = None

@dataclass
class SessionState:
    session_id: str
    schema_version: str
    # Paket-Bindung der Session (None nur in direkt konstruierten Test-States;
    # process_turn setzt und prüft den Namen — Version allein ist nicht eindeutig).
    paket_name: str | None = None
    # Mandanten-Bindung der Session (Spec K3, R11-C1). Wird beim ersten Turn
    # gesetzt und danach bei JEDEM Turn geprueft — der Paket-Fingerprint taugt
    # dafuer nicht, weil der Recovery-Replay ihn passieren darf.
    company_id: str | None = None
    status: SessionStatus = SessionStatus.AKTIV
    version: int = 0
    rounds: int = 0
    values: dict[str, FieldValue] = field(default_factory=dict)
    processed_message_ids: set[str] = field(default_factory=set)
    raw_log: list[tuple[str, str]] = field(default_factory=list)
    # Antwort je verarbeiteter message_id (Idempotenz, Spec Z. 43). Eine
    # geloggte Nachricht ohne Eintrag hier = offener/abgebrochener Turn.
    antworten: dict[str, dict] = field(default_factory=dict)
