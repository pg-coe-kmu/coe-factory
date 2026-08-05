"""Produktions-Verdrahtung: uvicorn bc1_service.main:app

Pflicht: BC1_DB_DSN. Optional: BC1_SNAPSHOT_PFAD, BC1_CLAUDE_MODELL,
ANTHROPIC_API_KEY (liest das SDK selbst).
"""
from __future__ import annotations

import os

from bc1_core.package import TOY_PROZESS
from bc1_service.api import create_app
from bc1_service.claude_llm import ClaudeLLM
from bc1_service.postgres_store import PostgresStateStore

# Snapshot-Verdrahtung folgt in Task 6
app = create_app(
    PostgresStateStore(os.environ["BC1_DB_DSN"]),
    ClaudeLLM(),
    TOY_PROZESS,
    None,
)
