"""Produktions-Verdrahtung: uvicorn bc1_service.main:app

Pflicht: BC1_DB_DSN. Optional: BC1_SNAPSHOT_PFAD (BC0-Baseline), BC1_CLAUDE_MODELL,
ANTHROPIC_API_KEY (liest das SDK selbst), BC1_LLM ("claude" | "ollama", Default claude —
ollama = lokaler Test-/Dev-Ersatz ohne API-Key, braucht die dev-Dependency ollama),
BC1_OLLAMA_MODELL, BC1_PAKET ("discovery" | "toy", Default discovery).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from bc1_service.api import create_app
from bc1_service.llm_wahl import waehle_llm
from bc1_service.paket_wahl import waehle_paket
from bc1_service.postgres_store import PostgresStateStore
from bc1_service.snapshot import lade_snapshot

_dsn = os.environ.get("BC1_DB_DSN")
if not _dsn:
    raise RuntimeError(
        "BC1_DB_DSN ist nicht gesetzt — ohne Datenbank-DSN kann der Dienst "
        "keine Sessions speichern. Beispiel: "
        'export BC1_DB_DSN="postgresql://user:pass@host:5432/datenbank"'
    )

_snapshot_pfad = os.environ.get("BC1_SNAPSHOT_PFAD")
_snapshot = lade_snapshot(_snapshot_pfad) if _snapshot_pfad else None
_prozesse = (
    [(p["process_id"], p["process_name"]) for p in _snapshot.prozess_liste()]
    if _snapshot is not None else None
)
_store = PostgresStateStore(_dsn)


@asynccontextmanager
async def _lebenszyklus(app):
    # Beim Herunterfahren den Verbindungspool sauber schliessen.
    yield
    _store.close()


app = create_app(
    _store,
    waehle_llm(os.environ),
    waehle_paket(os.environ, _prozesse),
    _snapshot,
    lifespan=_lebenszyklus,
)
