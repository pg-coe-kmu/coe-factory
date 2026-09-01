"""Produktions-Verdrahtung: uvicorn bc1_service.main:app

Pflicht: BC1_DB_DSN, BC1_COMPANY_ID. Optional: BC1_SNAPSHOT_PFAD (BC0-Baseline), BC1_CLAUDE_MODELL,
ANTHROPIC_API_KEY (liest das SDK selbst), BC1_LLM ("claude" | "ollama" | "gemini",
Default claude — ollama = lokaler Test-/Dev-Ersatz ohne API-Key; gemini = Gemini API,
braucht GEMINI_API_KEY), BC1_OLLAMA_MODELL, BC1_GEMINI_MODELL,
BC1_PAKET ("discovery" | "toy", Default discovery).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from psycopg_pool import ConnectionPool

from bc1_service.api import create_app
from bc1_service.llm_wahl import waehle_llm
from bc1_service.paket_wahl import waehle_paket
from bc1_service.postgres_store import PostgresStateStore
from bc1_service.snapshot import lade_snapshot
from bc1_service.start import lade_kontext, lies_company_id

_dsn = os.environ.get("BC1_DB_DSN")
if not _dsn:
    raise RuntimeError(
        "BC1_DB_DSN ist nicht gesetzt — ohne Datenbank-DSN kann der Dienst "
        "keine Sessions speichern. Beispiel: "
        'export BC1_DB_DSN="postgresql://user:pass@host:5432/datenbank"'
    )

_company_id = lies_company_id(os.environ)

_snapshot_pfad = os.environ.get("BC1_SNAPSHOT_PFAD")
_snapshot = lade_snapshot(_snapshot_pfad) if _snapshot_pfad else None
_prozesse = (
    [(p["process_id"], p["process_name"]) for p in _snapshot.prozess_liste()]
    if _snapshot is not None else None
)
_store = PostgresStateStore(_dsn)

# Zweiter, kleiner Pool fuer die Profil-Seite. Der Session-Store behaelt seinen
# eigenen — kein Umbau am bewaehrten Store.
_profil_pool = ConnectionPool(_dsn, min_size=1, max_size=5, open=True)
try:
    with _profil_pool.connection() as _conn:
        _kontext = lade_kontext(_conn, _company_id)
except Exception:
    # Wie beim Session-Store (postgres_store.py): beide Pools sind bereits
    # offen — ohne close() blieben ihre Verbindungen und Worker-Threads als
    # Leiche zurueck, wenn der Mandant unbekannt ist oder die DB nicht
    # erreichbar ist. _store ist zu diesem Zeitpunkt schon offen (Zeile
    # oben) und muss hier mitgeschlossen werden, nicht nur _profil_pool.
    _profil_pool.close()
    _store.close()
    raise


@asynccontextmanager
async def _lebenszyklus(app):
    # Beim Herunterfahren beide Verbindungspools sauber schliessen.
    yield
    _store.close()
    _profil_pool.close()


app = create_app(
    _store,
    waehle_llm(os.environ),
    waehle_paket(os.environ, _prozesse, _kontext),
    _snapshot,
    lifespan=_lebenszyklus,
    company_id=_company_id,
)
