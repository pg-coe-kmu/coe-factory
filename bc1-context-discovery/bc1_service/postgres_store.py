"""Persistenter StateStore auf PostgreSQL (Supabase-Schema `bc1`).

Vertrag identisch zum InMemoryStateStore (siehe tests/store_contract.py).
Optimistisches Locking atomar per Compare-and-Swap-UPDATE — damit ist die
Nebenläufigkeit hier per Konstruktion sicher, nicht per Prozess-Lock.
Nur Standard-Postgres, keine Supabase-Spezialfeatures.

Die Tabelle bc1.sessions legt seit B1 NICHT mehr der Store an, sondern die
signierte Einspiel-Datei bc1_service/db/sessions.sql (EINSPIELEN.md) — als
bc1_role, mit ausdruecklichem REVOKE fuer bc_leser.
"""
from __future__ import annotations

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from bc1_core.serialize import state_from_dict, state_to_dict
from bc1_core.store import StaleStateError, StateStore
from bc1_core.types import SessionState

_TABELLE_VORHANDEN_SQL = "SELECT to_regclass('bc1.sessions') IS NOT NULL"


class PostgresStateStore(StateStore):
    def __init__(self, dsn: str) -> None:
        self._pool = ConnectionPool(dsn, min_size=1, max_size=10, open=True)
        try:
            with self._pool.connection() as conn:
                vorhanden = conn.execute(_TABELLE_VORHANDEN_SQL).fetchone()[0]
            if not vorhanden:
                raise RuntimeError(
                    "bc1.sessions fehlt — der Dienst legt die Tabelle nicht mehr an. "
                    "Einspielen als bc1_role: bc1_service/db/sessions.sql "
                    "(Anleitung: bc1_service/db/EINSPIELEN.md)."
                )
        except Exception:
            # Der Pool ist bereits offen: ohne close() blieben seine
            # Verbindungen und Worker-Threads als Leiche zurueck.
            self._pool.close()
            raise

    def close(self) -> None:
        self._pool.close()

    def load(self, session_id: str) -> SessionState | None:
        with self._pool.connection() as conn:
            zeile = conn.execute(
                "SELECT state FROM bc1.sessions WHERE session_id = %s",
                (session_id,),
            ).fetchone()
        return state_from_dict(zeile[0]) if zeile else None

    def save(self, state: SessionState) -> None:
        neue_version = state.version + 1
        daten = state_to_dict(state)
        daten["version"] = neue_version
        with self._pool.connection() as conn:
            if state.version == 0:
                cursor = conn.execute(
                    "INSERT INTO bc1.sessions (session_id, company_id, version, state) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (session_id) DO NOTHING",
                    (state.session_id, state.company_id, neue_version, Jsonb(daten)),
                )
                if cursor.rowcount == 0:
                    raise StaleStateError(
                        f"stale write for {state.session_id}: "
                        f"Session existiert bereits, got 0"
                    )
            else:
                cursor = conn.execute(
                    "UPDATE bc1.sessions "
                    "SET state = %s, version = %s, aktualisiert_am = now() "
                    "WHERE session_id = %s AND version = %s",
                    (Jsonb(daten), neue_version, state.session_id, state.version),
                )
                if cursor.rowcount == 0:
                    raise StaleStateError(
                        f"stale write for {state.session_id}: "
                        f"gespeicherter Stand weicht ab, got {state.version}"
                    )
        state.version = neue_version
