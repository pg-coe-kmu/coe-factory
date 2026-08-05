"""Produktions-Verdrahtung: uvicorn bc1_service.main:app

Pflicht: BC1_DB_DSN. Optional: BC1_SNAPSHOT_PFAD (BC0-Baseline), BC1_CLAUDE_MODELL,
ANTHROPIC_API_KEY (liest das SDK selbst).
"""
from __future__ import annotations

import os

from bc1_core.package import TOY_PROZESS
from bc1_service.api import create_app
from bc1_service.claude_llm import ClaudeLLM
from bc1_service.postgres_store import PostgresStateStore
from bc1_service.snapshot import lade_snapshot

_snapshot_pfad = os.environ.get("BC1_SNAPSHOT_PFAD")

app = create_app(
    PostgresStateStore(os.environ["BC1_DB_DSN"]),
    ClaudeLLM(),
    TOY_PROZESS,
    lade_snapshot(_snapshot_pfad) if _snapshot_pfad else None,
)
