"""Produktions-Verdrahtung: uvicorn bc1_service.main:app

Pflicht: BC1_DB_DSN, BC1_COMPANY_ID, BC1_ANFRAGE_ID — seit B4 außerdem BC1_BC0_URL,
BC1_BC0_KONTO_EMAIL, BC1_BC0_KONTO_PASSWORT (oder bewusst BC1_BC0_MELDUNGEN=aus).
Optional: BC1_CLAUDE_MODELL,
ANTHROPIC_API_KEY (liest das SDK selbst), BC1_LLM ("claude" | "ollama" | "gemini",
Default claude — ollama = lokaler Test-/Dev-Ersatz ohne API-Key; gemini = Gemini API,
braucht GEMINI_API_KEY), BC1_OLLAMA_MODELL, BC1_GEMINI_MODELL,
BC1_PAKET ("discovery" | "toy", Default discovery).

uvicorn ohne `--host` lauscht nur auf dem eigenen Rechner; so betreiben (oder im
Container nur an 127.0.0.1 veröffentlichen), bis es eine Zugangsprüfung gibt.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from psycopg_pool import ConnectionPool

from bc1_service import bc0_lesepfade, bc0_meldungen
from bc1_service.api import create_app
from bc1_service.llm_wahl import waehle_llm
from bc1_service.paket_wahl import waehle_paket
from bc1_service.postgres_store import PostgresStateStore
from bc1_service.profil_writer import ProfilWriter
from bc1_service.start import (lade_kontext, lies_anfrage_id, lies_company_id,
                               melde_interview_beginn, pruefe_bc0_vor_dem_start)

# P5 (#271): Betriebsprotokoll auf die Standardausgabe — nur, wenn noch niemand das
# Logging eingerichtet hat (Tests konfigurieren selbst; uvicorn nur seine eigenen Logger).
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")

_dsn = os.environ.get("BC1_DB_DSN")
if not _dsn:
    raise RuntimeError(
        "BC1_DB_DSN ist nicht gesetzt — ohne Datenbank-DSN kann der Dienst "
        "keine Sessions speichern. Beispiel: "
        'export BC1_DB_DSN="postgresql://user:pass@host:5432/datenbank"'
    )

_company_id = lies_company_id(os.environ)
_anfrage_id = lies_anfrage_id(os.environ)

# B4: vor den Pools — ein Konfigurationsfehler bricht ohne offene Verbindungen ab.
_melder = bc0_meldungen.baue_melder(os.environ, _company_id)

_store = PostgresStateStore(_dsn)

# Zweiter, kleiner Pool fuer die Profil-Seite. Der Session-Store behaelt seinen
# eigenen — kein Umbau am bewaehrten Store.
_profil_pool = ConnectionPool(_dsn, min_size=1, max_size=5, open=True)
try:
    # Ergaenzung 2: vor dem Lesen aus der DB — Zugang pruefen, Gate fuer die eigene Anfrage
    # nachziehen. Hat ein frueherer Lauf das Gate verpasst, steht die Anfrage danach auf
    # am_gate und lade_kontext bricht mit der B5-Meldung ab.
    pruefe_bc0_vor_dem_start(_melder, _anfrage_id)
    with _profil_pool.connection() as _conn:
        _kontext = lade_kontext(_conn, _company_id, _anfrage_id)
        _status = bc0_lesepfade.anfrage_status(_conn, _company_id, _anfrage_id)
    # Nach dem with: die Verbindung ist zurueck im Pool und wartet nicht bis zu
    # 10 s auf BC0. Im try: scheitert die Meldung, schliessen beide Pools.
    melde_interview_beginn(_melder, _anfrage_id, _status)
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


_paket = waehle_paket(os.environ, kontext=_kontext)

app = create_app(
    _store,
    waehle_llm(os.environ),
    _paket,
    lifespan=_lebenszyklus,
    company_id=_company_id,
    anfrage_id=_anfrage_id,
    writer=ProfilWriter(_profil_pool, _company_id, _paket),
    melder=_melder,
)

logging.getLogger("bc1.dienst").info(
    "dienst gestartet paket=%s schema_version=%s mandant=%s",
    _paket.name, _paket.schema_version, _company_id)
