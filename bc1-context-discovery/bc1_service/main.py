"""Produktions-Verdrahtung: uvicorn bc1_service.main:app

Pflicht: BC1_DB_DSN. Optional: BC1_SNAPSHOT_PFAD (BC0-Baseline), BC1_CLAUDE_MODELL,
ANTHROPIC_API_KEY (liest das SDK selbst).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from bc1_core.package import TOY_PROZESS
from bc1_service.api import create_app
from bc1_service.claude_llm import ClaudeLLM
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
_store = PostgresStateStore(_dsn)


@asynccontextmanager
async def _lebenszyklus(app):
    # Beim Herunterfahren den Verbindungspool sauber schliessen.
    yield
    _store.close()


app = create_app(
    _store,
    ClaudeLLM(),
    TOY_PROZESS,
    lade_snapshot(_snapshot_pfad) if _snapshot_pfad else None,
    lifespan=_lebenszyklus,
)
