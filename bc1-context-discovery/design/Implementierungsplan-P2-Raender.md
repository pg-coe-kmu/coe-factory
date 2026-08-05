# BC1 P2 „Ränder" — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der MVP-Kern (Text-Interview → strukturiertes JSON, 82 Tests) bekommt seine Ränder: persistenter `PostgresStateStore` (Supabase-Schema `bc1`), `ClaudeLLM`-Adapter hinter dem bestehenden `LLMClient`-Protocol, FastAPI-Transportschicht um `process_turn()`, BC0-Snapshot-Reader über stabile IDs und die n8n-Chat-Anbindung — Ergebnis laut Bauplan B3: **echtes Interview im Chat gegen laufenden Dienst, Baseline angebunden.**

**Architecture:** Der Kern (`bc1_core/`) bleibt Stdlib-only und unverändert in seiner Logik; er wächst nur um die reine Stdlib-Serialisierung (`serialize.py`) und eine Thread-Sicherung des In-Memory-Stores. ALLES mit externen Dependencies kommt in ein neues Package `bc1_service/` (Store, Adapter, API, Snapshot). Die Nähte sind exakt die vorhandenen: `StateStore`-ABC, `LLMClient`-Protocol, `process_turn()`-Signatur. Die Transportschicht übernimmt die ihr laut Design-Spec delegierten Pflichten (`schema_version`-Check im Request, aktives Zurückweisen nach FERTIG).

**Tech Stack:** Python 3.11+ · FastAPI (Lifespan-Pattern, Pydantic v2 nur in der Transportschicht) · psycopg 3 (`psycopg[binary,pool]`, `Jsonb`) · Anthropic Python SDK (`anthropic`, Messages API mit Structured Outputs) · `jsonschema` (BC0-Snapshot-Validierung) · pytest + `httpx`/TestClient · n8n (Docker) als Übergangs-Chat-UI.

## Global Constraints

- **Branch:** `bc1-p2-raender`, abgezweigt von `bc1-mvp-kern` (PR #129 ist noch unmerged). Alles lokal; **kein Push ohne Richards ausdrückliches OK.**
- **TDD-Guard NIE bypassen.** Pro Task: erst der rote Test (voller `.venv/bin/pytest`-Lauf aus `bc1-context-discovery/`, damit der Reporter `test.json` schreibt), dann Implementierung. Bei einem Block: Skill `tdd-guard` aufrufen.
- **Kern bleibt Stdlib-only:** `bc1_core/` bekommt KEINE neuen Dependencies (Task 1 = reine Stdlib). Alles mit Dependencies liegt in `bc1_service/`.
- **Die bestehenden 82 Tests bleiben grün.** Einzige sanktionierte Umstellung: `tests/test_store.py` wird zur wiederverwendbaren Vertrags-Suite umgebaut (Richard-Auftrag, P2-Teststrategie Punkt 1 im Ledger) — dieselben Zusicherungen, neue Form.
- **Kein Netz in Tests** (Architektur-Invariante): Claude nur über injizierte Stubs; Echt-API-Stichproben und Postgres-Tests laufen NUR, wenn `BC1_ECHT_LLM` bzw. `BC1_TEST_DB_DSN` explizit gesetzt sind (sonst skip).
- **Vertraulichkeit:** Der NoroAI-Referenz-Snapshot und alles aus `Drive/` bleibt strikt lokal — NIE ins Repo. Tests nutzen ausschließlich synthetische, generische Daten („Beispielprozess"). Einzige Kopie ins Repo: `snapshot_schema.json` (BC0-Vertrags-Artefakt, firmenfrei).
- **Keine `.env`-Datei anlegen** (die Security-Deny-Liste blockt `Read(**/.env*)`): Konfiguration ausschließlich über exportierte Umgebungsvariablen (`BC1_DB_DSN`, `ANTHROPIC_API_KEY`, `BC1_CLAUDE_MODELL`, `BC1_SNAPSHOT_PFAD`). Secrets nie loggen, nie committen.
- **Neue Dependencies nur die hier genannten:** `fastapi`, `uvicorn[standard]`, `psycopg[binary,pool]`, `anthropic`, `jsonschema`; dev zusätzlich `httpx`. Installation:
  ```bash
  cd coe-factory/bc1-context-discovery
  uv pip install --python .venv/bin/python fastapi "uvicorn[standard]" "psycopg[binary,pool]" anthropic jsonschema httpx
  ```
- Deutsche Namen und Docstrings wie im Kern; Conventional Commits mit Scope `bc1`; **Commit nach jeder Task** (bzw. nach jedem RED→GREEN-Paar, wie in P1).
- Generik-Invariante gilt weiter: keine Verzweigung auf Use-Case- oder Feldnamen außerhalb des Use-Case-Pakets; die API bedient jedes `UseCasePackage`.

## File Structure

- `bc1_core/serialize.py` — Create: SessionState ⇄ JSON-Dict (Stdlib), inkl. value⇒source-Invariante
- `bc1_core/store.py` — Modify: `threading.Lock` um `save`/`load` des `InMemoryStateStore`
- `bc1_service/__init__.py` — Create: leer (Package-Marker)
- `bc1_service/postgres_store.py` — Create: `PostgresStateStore` (Schema `bc1`, CAS-Locking, Pool)
- `bc1_service/claude_llm.py` — Create: `ClaudeLLM` (extract/phrase, Structured Outputs, enge Retries)
- `bc1_service/api.py` — Create: `create_app()`-Factory, `POST /turn`, `GET /gesundheit`, `GET /prozesse`
- `bc1_service/main.py` — Create: Verdrahtung aus Umgebungsvariablen für uvicorn
- `bc1_service/snapshot.py` — Create: BC0-Snapshot laden/validieren, Zugriff über stabile IDs
- `bc1_service/snapshot_schema.json` — Create: Kopie des BC0-Vertragsschemas (aus `Drive/`)
- `bc1_service/n8n/SMOKE.md` — Create: n8n-Aufbauanleitung + 4 Smoke-Szenarien (Checkliste)
- `bc1_service/n8n/bc1-chat-workflow.json` — Create (in Task 7, als Export aus dem funktionierenden n8n)
- `tests/store_contract.py` — Create: wiederverwendbare Store-Vertrags-Suite (`StoreVertrag`)
- `tests/test_serialize.py`, `tests/test_store_postgres.py`, `tests/test_claude_llm.py`, `tests/test_api.py`, `tests/test_snapshot.py` — Create
- `tests/test_store.py` — Modify: wird `TestInMemoryStore(StoreVertrag)` (sanktionierter Umbau)
- `pyproject.toml` — Modify: `[dependency-groups]` um `service` erweitern, `httpx` zu `dev`

## Reihenfolge & Parallelisierung

Task 1 → 2 → 3 sind sequenziell (Serialisierung → Vertrags-Suite → Postgres). Task 4 (Claude-Adapter) und Task 6 (Snapshot-Reader) sind davon unabhängig und jederzeit parallelisierbar. Task 5 (FastAPI) braucht 1–4 (6 nur für `/prozesse`). Task 7 (n8n) braucht den laufenden Dienst aus Task 5.

Abgedeckte Deferrals (Ledger/Design-Spec): value⇒source-Invariante + set/tuple-Roundtrip (Task 1) · Store-Thread-Sicherheit, der einzige adjudiziert-offene Gesamt-Review-Punkt (Task 2/3) · LLM-Retries/Backoff + kaputtes Extraktions-JSON (Task 4) · `schema_version`-Request-Check + aktives Zurückweisen nach FERTIG (Task 5).

---

### Task 1: SessionState-Serialisierung (`bc1_core/serialize.py`)

**Files:**
- Create: `bc1_core/serialize.py`
- Test: `tests/test_serialize.py`

**Interfaces:**
- Consumes: `SessionState`, `FieldValue`, `Candidate`, `FieldStatus`, `SessionStatus` aus `bc1_core.types` (exakt die Felder aus `types.py:19-49`).
- Produces: `state_to_dict(state: SessionState) -> dict` (JSON-fähig: Enums→Wire-Strings, set→sortierte Liste, Tupel→Listen) und `state_from_dict(data: dict) -> SessionState` (exakter Roundtrip inkl. Re-Tupeln von `raw_log` und Re-Set von `processed_message_ids`). `state_from_dict` wirft `ValueError` bei verletzter Invariante „value gesetzt ⇒ source_message_id gesetzt" (FieldValue und Candidate) und bei unbekannten Enum-Werten. Task 3 verlässt sich exakt auf diese zwei Funktionen.

- [ ] **Step 1: Write the failing test** — `tests/test_serialize.py`

```python
import json

import pytest

from bc1_core.serialize import state_from_dict, state_to_dict
from bc1_core.types import (
    Candidate,
    FieldStatus,
    FieldValue,
    SessionState,
    SessionStatus,
)


def _voller_state() -> SessionState:
    return SessionState(
        session_id="s1",
        schema_version="0.1",
        paket_name="toy_prozess",
        status=SessionStatus.WARTET,
        version=3,
        rounds=2,
        values={
            "prozess_name": FieldValue(
                value="Urlaubsantrag",
                status=FieldStatus.GUELTIG,
                source_message_id="m1",
                candidates=[Candidate("Urlaub", "m0")],
                attempts=1,
            ),
            "haeufigkeit": FieldValue(
                status=FieldStatus.UNGELOEST,
                attempts=2,
                grund="nachfrage_limit_erreicht",
            ),
        },
        processed_message_ids={"m0", "m1"},
        raw_log=[("m0", "erste Nachricht"), ("m1", "zweite Nachricht")],
        antworten={
            "m1": {
                "status": "frage",
                "payload": {"naechste_frage": "Wie oft?", "feld": "haeufigkeit"},
            }
        },
    )


def test_roundtrip_ueber_echtes_json():
    original = _voller_state()
    wieder = state_from_dict(json.loads(json.dumps(state_to_dict(original))))
    assert wieder == original


def test_raw_log_wird_re_getupelt_und_set_wiederhergestellt():
    wieder = state_from_dict(json.loads(json.dumps(state_to_dict(_voller_state()))))
    assert all(isinstance(eintrag, tuple) for eintrag in wieder.raw_log)
    assert isinstance(wieder.processed_message_ids, set)


def test_enums_landen_als_wire_strings_im_dict():
    daten = state_to_dict(_voller_state())
    assert daten["status"] == "wartet_auf_antwort"
    assert daten["values"]["prozess_name"]["status"] == "gueltig"


def test_wert_ohne_quelle_wird_abgelehnt():
    daten = state_to_dict(_voller_state())
    daten["values"]["prozess_name"]["source_message_id"] = None
    with pytest.raises(ValueError):
        state_from_dict(daten)


def test_kandidat_ohne_quelle_wird_abgelehnt():
    daten = state_to_dict(_voller_state())
    daten["values"]["prozess_name"]["candidates"][0]["source_message_id"] = None
    with pytest.raises(ValueError):
        state_from_dict(daten)


def test_unbekannter_statuswert_wird_abgelehnt():
    daten = state_to_dict(_voller_state())
    daten["status"] = "kaputt"
    with pytest.raises(ValueError):
        state_from_dict(daten)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_serialize.py -v` (aus `bc1-context-discovery/`, voller Lauf danach: `.venv/bin/pytest`)
Expected: FAIL — `ModuleNotFoundError: No module named 'bc1_core.serialize'`

- [ ] **Step 3: Write implementation** — `bc1_core/serialize.py`

```python
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
    return {
        "session_id": state.session_id,
        "schema_version": state.schema_version,
        "paket_name": state.paket_name,
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
    if daten["value"] is not None and daten["source_message_id"] is None:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_serialize.py -v` und danach voll `.venv/bin/pytest`
Expected: PASS (6 passed; Gesamt 88 passed)

- [ ] **Step 5: Commit**

```bash
git add bc1_core/serialize.py tests/test_serialize.py
git commit -m "feat(bc1): SessionState-JSON-Roundtrip inkl. value=>source-Invariante"
```

---

### Task 2: Store-Vertrags-Suite + Thread-Sicherheit `InMemoryStateStore`

**Files:**
- Create: `tests/store_contract.py`
- Modify: `tests/test_store.py` (wird Subklasse der Suite — sanktionierter Umbau)
- Modify: `bc1_core/store.py` (nur: `threading.Lock` in `InMemoryStateStore`)

**Interfaces:**
- Consumes: `StateStore`, `InMemoryStateStore`, `StaleStateError` (`bc1_core/store.py`), `SessionState`.
- Produces: Klasse `StoreVertrag` (in `tests/store_contract.py`, bewusst OHNE `Test`-Präfix, damit pytest sie nicht direkt einsammelt) mit allen Vertragstests; Subklassen liefern nur eine pytest-Fixture `store`, die eine **frische, leere** Store-Instanz erzeugt. Task 3 hängt seine Postgres-Tests an genau diese Klasse.

- [ ] **Step 1: Write the failing test** — `tests/store_contract.py` + Umbau `tests/test_store.py`

`tests/store_contract.py` (die 7 bisherigen Zusicherungen aus `test_store.py`, unverändert in der Sache, plus der neue Nebenläufigkeitstest):

```python
"""Wiederverwendbare Vertrags-Suite für StateStore-Implementierungen.

Läuft gegen jede Implementierung (InMemory, Postgres, ...). Subklassen
liefern eine `store`-Fixture mit einer frischen, leeren Instanz.
"""
from __future__ import annotations

import threading

import pytest

from bc1_core.store import StaleStateError
from bc1_core.types import Candidate, FieldStatus, FieldValue, SessionState


def _fetter_state(session_id: str = "s1") -> SessionState:
    # Breiter State: verbreitert beim InMemory-Store das Rennfenster
    # (deepcopy zwischen Versions-Check und Schreiben) und prüft beim
    # Postgres-Store nebenbei den vollen Serialisierungs-Roundtrip.
    st = SessionState(session_id=session_id, schema_version="0.1")
    for i in range(300):
        st.values[f"feld_{i}"] = FieldValue(
            value=f"wert_{i}",
            status=FieldStatus.GUELTIG,
            source_message_id="m1",
            candidates=[Candidate(f"alt_{i}", "m0")],
        )
    return st


class StoreVertrag:
    def test_load_unbekannter_session_gibt_none(self, store):
        assert store.load("gibt-es-nicht") is None

    def test_roundtrip_erhaelt_den_zustand(self, store):
        original = _fetter_state()
        store.save(original)
        geladen = store.load("s1")
        assert geladen == original
        assert geladen.version == 1

    def test_save_bumpt_caller_version_um_genau_eins(self, store):
        st = SessionState("s1", "0.1")
        store.save(st)
        assert st.version == 1
        store.save(st)  # ohne Neuladen weiterspeichern muss funktionieren
        assert st.version == 2

    def test_erst_save_mit_version_ungleich_null_wird_abgelehnt(self, store):
        st = SessionState("s1", "0.1", version=3)
        with pytest.raises(StaleStateError):
            store.save(st)
        assert st.version == 3  # Fehlerpfad mutiert den Caller nicht

    def test_stale_write_wird_abgelehnt(self, store):
        st = SessionState("s1", "0.1")
        store.save(st)              # gespeichert: Version 1
        veraltet = store.load("s1")
        store.save(st)              # gespeichert: Version 2
        with pytest.raises(StaleStateError):
            store.save(veraltet)    # Version 1 gegen gespeicherte 2

    def test_vorauseilende_version_wird_abgelehnt(self, store):
        st = SessionState("s1", "0.1")
        store.save(st)
        voraus = store.load("s1")
        voraus.version = 99
        with pytest.raises(StaleStateError):
            store.save(voraus)

    def test_load_liefert_isolierte_kopie(self, store):
        store.save(_fetter_state())
        a = store.load("s1")
        a.values["feld_0"].value = "manipuliert"
        assert store.load("s1").values["feld_0"].value == "wert_0"

    def test_save_isoliert_gegen_spaetere_caller_mutation(self, store):
        st = _fetter_state()
        store.save(st)
        st.values["feld_0"].value = "manipuliert"
        assert store.load("s1").values["feld_0"].value == "wert_0"

    def test_nebenlaeufige_saves_genau_einer_gewinnt(self, store):
        # Schließt den einzigen adjudiziert-offenen Gesamt-Review-Punkt
        # (Store-Thread-Sicherheit) an der StateStore-Naht.
        for runde in range(10):
            sid = f"race_{runde}"
            store.save(_fetter_state(sid))  # gespeichert: Version 1
            n = 8
            barriere = threading.Barrier(n)
            erfolge: list[int] = []
            fehler: list[int] = []

            def schreiber(i: int) -> None:
                st = store.load(sid)
                st.rounds = i
                barriere.wait()
                try:
                    store.save(st)
                    erfolge.append(i)
                except StaleStateError:
                    fehler.append(i)

            threads = [
                threading.Thread(target=schreiber, args=(i,)) for i in range(n)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert len(erfolge) == 1, f"Runde {runde}: {len(erfolge)} Gewinner"
            assert len(fehler) == n - 1
            assert store.load(sid).version == 2
```

`tests/test_store.py` (ersetzt die bisherigen 7 Direkt-Tests vollständig — identische Zusicherungen leben jetzt in der Suite):

```python
import pytest

from bc1_core.store import InMemoryStateStore
from tests.store_contract import StoreVertrag


class TestInMemoryStore(StoreVertrag):
    @pytest.fixture
    def store(self):
        return InMemoryStateStore()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_store.py -v`
Expected: 8 von 9 PASS, `test_nebenlaeufige_saves_genau_einer_gewinnt` FAIL (mehrere „Gewinner" — der ungeschützte Check-then-Write lässt bei 10 Runden × 8 Threads mit breitem Rennfenster praktisch sicher mehr als einen Save durch). Falls der Lauf wider Erwarten grün ist: Rundenzahl erhöhen statt den Test abzuschwächen.

- [ ] **Step 3: Write implementation** — `bc1_core/store.py` (chirurgisch: nur Lock ergänzen)

```python
from __future__ import annotations
import copy
import threading
from abc import ABC, abstractmethod
from bc1_core.types import SessionState

class StaleStateError(Exception):
    pass

class StateStore(ABC):
    @abstractmethod
    def load(self, session_id: str) -> SessionState | None: ...
    @abstractmethod
    def save(self, state: SessionState) -> None: ...

class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._data: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def load(self, session_id: str) -> SessionState | None:
        with self._lock:
            st = self._data.get(session_id)
            return copy.deepcopy(st) if st is not None else None

    def save(self, state: SessionState) -> None:
        with self._lock:
            existing = self._data.get(state.session_id)
            if existing is None:
                if state.version != 0:
                    raise StaleStateError(
                        f"first save for {state.session_id} must have version 0, "
                        f"got {state.version}"
                    )
            elif existing.version != state.version:
                raise StaleStateError(
                    f"stale write for {state.session_id}: "
                    f"have {existing.version}, got {state.version}"
                )
            state.version += 1
            self._data[state.session_id] = copy.deepcopy(state)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_store.py -v` und danach voll `.venv/bin/pytest`
Expected: PASS (9 passed; Gesamt 90 passed — 82 alte, davon 7 in die Suite überführt und um 2 ergänzt, + 6 aus Task 1)

- [ ] **Step 5: Commit**

```bash
git add tests/store_contract.py tests/test_store.py bc1_core/store.py
git commit -m "feat(bc1): Store-Vertrags-Suite (wiederverwendbar) + threadsicherer InMemoryStateStore"
```

---

### Task 3: `PostgresStateStore` + Schema `bc1`

**Files:**
- Create: `bc1_service/__init__.py` (leer), `bc1_service/postgres_store.py`
- Modify: `pyproject.toml` (dependency-groups)
- Test: `tests/test_store_postgres.py`

**Interfaces:**
- Consumes: `state_to_dict`/`state_from_dict` (Task 1), `StateStore`/`StaleStateError`, `StoreVertrag` (Task 2).
- Produces: `PostgresStateStore(dsn: str)` mit exakt der `InMemoryStateStore`-Semantik (load = Kopie oder `None`; Erst-Save nur mit `version == 0`; `save` bumpt die Caller-Version um genau 1 NUR bei Erfolg; konkurrierende Saves auf demselben Stand verlieren mit `StaleStateError` — atomar via Compare-and-Swap-UPDATE) plus `close()`. Legt Schema/Tabelle beim Konstruieren idempotent an (`CREATE SCHEMA IF NOT EXISTS bc1`). Task 5 (`main.py`) konsumiert genau diesen Konstruktor.

**Lokale Test-DB** (die Tests skippen ohne DSN; Supabase wird später nur per DSN getauscht — Session Pooler, Port 5432):

```bash
docker run --rm -d --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16
export BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres"
```

- [ ] **Step 1: Write the failing test** — `tests/test_store_postgres.py`

```python
import os

import pytest

from tests.store_contract import StoreVertrag

DSN = os.environ.get("BC1_TEST_DB_DSN")

pytestmark = pytest.mark.skipif(
    not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt (lokales Test-Postgres nötig)"
)


class TestPostgresStore(StoreVertrag):
    @pytest.fixture
    def store(self):
        import psycopg

        from bc1_service.postgres_store import PostgresStateStore

        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS bc1.sessions")
        s = PostgresStateStore(DSN)  # legt Schema + Tabelle neu an
        yield s
        s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `BC1_TEST_DB_DSN=$BC1_TEST_DB_DSN .venv/bin/pytest tests/test_store_postgres.py -v` (Docker-Postgres muss laufen)
Expected: FAIL — `ModuleNotFoundError: No module named 'bc1_service.postgres_store'` (9 Errors)

- [ ] **Step 3: Write implementation** — `bc1_service/postgres_store.py` + `pyproject.toml`

`pyproject.toml` (nur der geänderte Abschnitt):

```toml
[dependency-groups]
dev = ["pytest", "httpx"]
service = [
    "fastapi",
    "uvicorn[standard]",
    "psycopg[binary,pool]",
    "anthropic",
    "jsonschema",
]
```

`bc1_service/postgres_store.py`:

```python
"""Persistenter StateStore auf PostgreSQL (Supabase-Schema `bc1`).

Vertrag identisch zum InMemoryStateStore (siehe tests/store_contract.py).
Optimistisches Locking atomar per Compare-and-Swap-UPDATE — damit ist die
Nebenläufigkeit hier per Konstruktion sicher, nicht per Prozess-Lock.
Nur Standard-Postgres (Bauplan B1), keine Supabase-Spezialfeatures.
"""
from __future__ import annotations

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from bc1_core.serialize import state_from_dict, state_to_dict
from bc1_core.store import StaleStateError, StateStore
from bc1_core.types import SessionState

_TABELLE_SQL = """
CREATE TABLE IF NOT EXISTS bc1.sessions (
    session_id text PRIMARY KEY,
    version    integer NOT NULL,
    state      jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
)
"""


class PostgresStateStore(StateStore):
    def __init__(self, dsn: str) -> None:
        self._pool = ConnectionPool(dsn, min_size=1, max_size=10, open=True)
        with self._pool.connection() as conn:
            conn.execute("CREATE SCHEMA IF NOT EXISTS bc1")
            conn.execute(_TABELLE_SQL)

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
                    "INSERT INTO bc1.sessions (session_id, version, state) "
                    "VALUES (%s, %s, %s) "
                    "ON CONFLICT (session_id) DO NOTHING",
                    (state.session_id, neue_version, Jsonb(daten)),
                )
                if cursor.rowcount == 0:
                    raise StaleStateError(
                        f"stale write for {state.session_id}: "
                        f"Session existiert bereits, got 0"
                    )
            else:
                cursor = conn.execute(
                    "UPDATE bc1.sessions "
                    "SET state = %s, version = %s, updated_at = now() "
                    "WHERE session_id = %s AND version = %s",
                    (Jsonb(daten), neue_version, state.session_id, state.version),
                )
                if cursor.rowcount == 0:
                    raise StaleStateError(
                        f"stale write for {state.session_id}: "
                        f"gespeicherter Stand weicht ab, got {state.version}"
                    )
        state.version = neue_version
```

Hinweis zur Semantik-Feinheit: `save` bei unbekannter Session mit `version != 0` läuft in den UPDATE-Zweig, trifft keine Zeile und wirft `StaleStateError` — dieselbe Fehlerklasse wie beim InMemory-Erst-Save-Guard; die Vertrags-Suite prüft die Exception-Klasse, nicht den Text.

- [ ] **Step 4: Run test to verify it passes**

Run: `BC1_TEST_DB_DSN=$BC1_TEST_DB_DSN .venv/bin/pytest tests/test_store_postgres.py -v`, danach voll `.venv/bin/pytest` (ohne DSN: 9 skipped)
Expected: PASS (9 passed gegen Postgres, inkl. Nebenläufigkeitstest)

- [ ] **Step 5: Commit**

```bash
git add bc1_service/__init__.py bc1_service/postgres_store.py tests/test_store_postgres.py pyproject.toml
git commit -m "feat(bc1): PostgresStateStore (Schema bc1, CAS-Locking) gegen die Store-Vertrags-Suite"
```

---

### Task 4: Claude-Adapter (`bc1_service/claude_llm.py`)

**Files:**
- Create: `bc1_service/claude_llm.py`
- Test: `tests/test_claude_llm.py`

**Interfaces:**
- Consumes: `LLMClient`-Protocol-Signaturen (`extract(message, package, state) -> list[ExtractionCandidate]`, `phrase(field, state) -> str`), `ExtractionCandidate`, `UseCasePackage`/`FieldSpec`.
- Produces: `ClaudeLLM(client=None, modell=None)` — erfüllt das Protocol strukturell. `client` ist injizierbar (Tests: Stub, kein Netz). Default-Client: `anthropic.Anthropic(timeout=30.0, max_retries=1)` — das sind die „eng begrenzten Retries mit Backoff" aus Design-Spec Z. 86 (SDK-eigener exponentieller Backoff, 1 Retry, damit kein n8n-Timeout). Modell aus `BC1_CLAUDE_MODELL`, Default `claude-opus-5`. Wirft bei API-Fehlern/Refusal — `process_turn` übersetzt das bereits in `fehler_fortsetzbar` (Kern-Vertrag, Task-8-Review).
- Deferral-Abdeckung: „Kaputtes Extraktions-JSON" (Design-Spec Z. 87) ist per **Structured Outputs** (`output_config.format` mit JSON-Schema) konstruktiv eliminiert — die API garantiert schema-valides JSON; das „einmal strenger nachfordern" entfällt damit. Unbekannte Feldnamen und leere Werte werden gefiltert (betroffene Felder bleiben `fehlt`, kein Absturz).

- [ ] **Step 1: Write the failing test** — `tests/test_claude_llm.py`

```python
import json
import os

import pytest

from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.core import process_turn
from bc1_core.types import FieldValue, SessionState
from bc1_service.claude_llm import ClaudeLLM


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Antwort:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [_Block(text)]
        self.stop_reason = stop_reason


class _StubMessages:
    def __init__(self, antworten: list) -> None:
        self._antworten = list(antworten)
        self.aufrufe: list[dict] = []

    def create(self, **kwargs):
        self.aufrufe.append(kwargs)
        return self._antworten.pop(0)


class _StubClient:
    def __init__(self, antworten: list) -> None:
        self.messages = _StubMessages(antworten)


def _extraktions_json(*paare: tuple[str, str]) -> str:
    return json.dumps(
        {"extraktionen": [{"feld": f, "wert": w} for f, w in paare]}
    )


def test_extract_liefert_kandidaten_und_filtert_unbekannte_felder():
    stub = _StubClient([_Antwort(_extraktions_json(
        ("prozess_name", "Urlaubsantrag"),
        ("erfundenes_feld", "x"),
        ("ausloeser", "   "),
    ))])
    llm = ClaudeLLM(client=stub)
    kandidaten = llm.extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    assert [(k.field_name, k.value) for k in kandidaten] == [
        ("prozess_name", "Urlaubsantrag")
    ]


def test_extract_nutzt_structured_outputs_mit_json_schema():
    stub = _StubClient([_Antwort(_extraktions_json())])
    ClaudeLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    aufruf = stub.messages.aufrufe[0]
    assert aufruf["output_config"]["format"]["type"] == "json_schema"


def test_refusal_wirft_statt_leise_zu_scheitern():
    stub = _StubClient([_Antwort("", stop_reason="refusal")])
    with pytest.raises(RuntimeError):
        ClaudeLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))


def test_phrase_liefert_frage_und_markiert_nachfragen():
    stub = _StubClient([_Antwort("  Wie oft kommt der Prozess vor?  ")])
    state = SessionState("s1", "0.1")
    state.values["haeufigkeit"] = FieldValue(attempts=1)
    frage = ClaudeLLM(client=stub).phrase(TOY_PROZESS.field("haeufigkeit"), state)
    assert frage == "Wie oft kommt der Prozess vor?"
    assert "Nachfrage" in stub.messages.aufrufe[0]["messages"][0]["content"]


def test_protocol_konformitaet_ein_turn_durch_process_turn():
    stub = _StubClient([
        _Antwort(_extraktions_json(("prozess_name", "Urlaubsantrag"))),
        _Antwort("Was löst den Prozess aus?"),
    ])
    antwort = process_turn(
        InMemoryStateStore(), ClaudeLLM(client=stub), TOY_PROZESS,
        "s1", "m1", "Der Prozess heißt Urlaubsantrag",
    )
    assert antwort["status"] == "frage"
    assert antwort["payload"]["feld"] == "ausloeser"
    assert antwort["payload"]["naechste_frage"] == "Was löst den Prozess aus?"


@pytest.mark.skipif(
    not os.environ.get("BC1_ECHT_LLM"),
    reason="Echt-API-Stichprobe nur mit BC1_ECHT_LLM=1 (Kosten!)",
)
def test_echt_api_stichprobe_extraktion():
    llm = ClaudeLLM()
    kandidaten = llm.extract(
        "Der Prozess heißt Urlaubsantrag und läuft etwa 50 mal pro Jahr.",
        TOY_PROZESS,
        SessionState("s1", "0.1"),
    )
    felder = {k.field_name for k in kandidaten}
    assert "prozess_name" in felder
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_claude_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bc1_service.claude_llm'`

- [ ] **Step 3: Write implementation** — `bc1_service/claude_llm.py`

```python
"""Claude-Adapter hinter dem LLMClient-Protocol des Kerns.

Der Kern kennt diese Klasse nicht (Protocol, strukturell). Retries/Timeout
bewusst eng (Design-Spec: Chat darf nicht in n8n-Timeouts laufen); bei
anhaltendem Ausfall fliegt die Exception — process_turn macht daraus den
fehler_fortsetzbar-Vertrag. Structured Outputs garantieren valides JSON.
"""
from __future__ import annotations

import json
import os

import anthropic

from bc1_core.llm import ExtractionCandidate
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import SessionState

STANDARD_MODELL = "claude-opus-5"

_EXTRAKTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "extraktionen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feld": {"type": "string"},
                    "wert": {"type": "string"},
                },
                "required": ["feld", "wert"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["extraktionen"],
    "additionalProperties": False,
}

_SYSTEM_EXTRAKTION = (
    "Du extrahierst Fakten aus einer Interview-Antwort für ein Prozessprofil. "
    "Extrahiere NUR, was die Nachricht wirklich belegt — nichts erfinden, "
    "nichts aus Vorwissen ergänzen. Werte wörtlich bzw. minimal normalisiert."
)

_SYSTEM_FRAGE = (
    "Du führst ein freundliches, professionelles Prozess-Interview auf Deutsch. "
    "Antworte NUR mit der Frage selbst — ohne Einleitung, ohne Anführungszeichen."
)


class ClaudeLLM:
    def __init__(self, client=None, modell: str | None = None) -> None:
        self._client = client or anthropic.Anthropic(timeout=30.0, max_retries=1)
        self._modell = modell or os.environ.get("BC1_CLAUDE_MODELL", STANDARD_MODELL)

    def extract(
        self, message: str, package: UseCasePackage, state: SessionState
    ) -> list[ExtractionCandidate]:
        felder = "\n".join(f"- {f.name}: {f.question}" for f in package.fields)
        antwort = self._client.messages.create(
            model=self._modell,
            max_tokens=4096,
            system=_SYSTEM_EXTRAKTION,
            output_config={
                "format": {"type": "json_schema", "schema": _EXTRAKTIONS_SCHEMA}
            },
            messages=[{
                "role": "user",
                "content": (
                    f"Felder des Prozessprofils:\n{felder}\n\n"
                    f"Interview-Nachricht:\n{message}\n\n"
                    "Gib alle Feld-Wert-Paare zurück, die diese Nachricht belegt."
                ),
            }],
        )
        daten = json.loads(self._text_inhalt(antwort))
        bekannte = {f.name for f in package.fields}
        return [
            ExtractionCandidate(e["feld"], e["wert"].strip())
            for e in daten["extraktionen"]
            if e["feld"] in bekannte and e["wert"].strip()
        ]

    def phrase(self, field: FieldSpec, state: SessionState) -> str:
        bisher = state.values.get(field.name)
        hinweis = (
            "\nEs ist eine Nachfrage: Die bisherige Antwort war unklar oder "
            "ungültig — formuliere die Frage anders und konkreter."
            if bisher is not None and bisher.attempts > 0
            else ""
        )
        antwort = self._client.messages.create(
            model=self._modell,
            max_tokens=4096,
            system=_SYSTEM_FRAGE,
            messages=[{
                "role": "user",
                "content": (
                    "Formuliere genau eine Chat-Frage für dieses Feld:\n"
                    f"Feld: {field.name}\nKernfrage: {field.question}{hinweis}"
                ),
            }],
        )
        return self._text_inhalt(antwort).strip()

    @staticmethod
    def _text_inhalt(antwort) -> str:
        if antwort.stop_reason == "refusal":
            raise RuntimeError("LLM hat die Anfrage abgelehnt (refusal)")
        for block in antwort.content:
            if block.type == "text":
                return block.text
        raise RuntimeError("LLM-Antwort ohne Textblock")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_claude_llm.py -v` (5 passed, 1 skipped) und voll `.venv/bin/pytest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bc1_service/claude_llm.py tests/test_claude_llm.py
git commit -m "feat(bc1): ClaudeLLM-Adapter (Structured Outputs, enge Retries, Refusal-Kontrakt)"
```

---

### Task 5: FastAPI-Transportschicht (`bc1_service/api.py` + `main.py`)

**Files:**
- Create: `bc1_service/api.py`, `bc1_service/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `process_turn`, `SessionStatus`, `StateStore`, `LLMClient`, `UseCasePackage`, `TOY_PROZESS`; für `main.py`: `PostgresStateStore` (Task 3), `ClaudeLLM` (Task 4), `lade_snapshot` (Task 6 — bis dahin `snapshot=None`).
- Produces: `create_app(store, llm, package, snapshot=None) -> FastAPI` mit:
  - `POST /turn` — Request `{session_id, message_id, message, schema_version?}` (exakt Design-Spec B1). Antwort: das `process_turn`-Dict plus Zusatzkey `chat_text` (für n8n). HTTP 200 auch bei `fehler_fortsetzbar` (Vertragsantwort, kein Transportfehler).
  - Transport-Pflichten (Design-Spec-Deferrals): `schema_version`-Mismatch → **409** `schema_version_passt_nicht` · neue Nachricht an FERTIG-Session → **409** `session_abgeschlossen` (Replays bekannter message_ids laufen weiter idempotent durch) · `ValueError` des Paket-Guards → **409**.
  - `GET /gesundheit` (statisch) und `GET /prozesse` (404 `kein_snapshot_konfiguriert`, wenn kein Snapshot geladen).
- `main.py` verdrahtet aus Umgebungsvariablen: `BC1_DB_DSN` (Pflicht), `BC1_SNAPSHOT_PFAD` (optional) → `app` für `uvicorn bc1_service.main:app`.

- [ ] **Step 1: Write the failing test** — `tests/test_api.py`

```python
import pytest
from fastapi.testclient import TestClient

from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.types import SessionState
from bc1_service.api import create_app


def _fake_llm() -> FakeLLM:
    return FakeLLM({
        "Der Prozess heißt Urlaubsantrag": [
            ExtractionCandidate("prozess_name", "Urlaubsantrag")
        ],
        "Ausgelöst durch einen Antrag": [
            ExtractionCandidate("ausloeser", "Antrag")
        ],
        "Etwa 100 mal pro Jahr": [
            ExtractionCandidate("haeufigkeit", "100 mal pro Jahr")
        ],
    })


class ExplodierendesLLM(FakeLLM):
    def extract(self, message, package, state):
        raise RuntimeError("LLM kaputt")


def _client(llm=None, store=None) -> TestClient:
    return TestClient(create_app(store or InMemoryStateStore(),
                                 llm or _fake_llm(), TOY_PROZESS))


def _turn(client, mid, text, session="s1", **extra):
    return client.post("/turn", json={
        "session_id": session, "message_id": mid, "message": text, **extra
    })


def test_gesundheit():
    antwort = _client().get("/gesundheit")
    assert antwort.status_code == 200
    assert antwort.json()["paket"] == "toy_prozess"


def test_interview_bis_fertig_mit_chat_text():
    client = _client()
    a1 = _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    assert a1.status_code == 200
    assert a1.json()["status"] == "frage"
    assert a1.json()["chat_text"] == a1.json()["payload"]["naechste_frage"]
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    a3 = _turn(client, "m3", "Etwa 100 mal pro Jahr")
    assert a3.json()["status"] == "fertig"
    assert a3.json()["payload"]["vollstaendigkeit"] == 1.0
    assert "abgeschlossen" in a3.json()["chat_text"]


def test_gleiche_message_id_ist_idempotent():
    client = _client()
    a1 = _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    a2 = _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    assert a2.status_code == 200
    assert a2.json() == a1.json()


def test_schema_version_mismatch_gibt_409():
    antwort = _turn(_client(), "m1", "egal", schema_version="99.9")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "schema_version_passt_nicht"


def test_fertige_session_weist_neue_nachricht_aktiv_ab():
    client = _client()
    _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    alt = _turn(client, "m3", "Etwa 100 mal pro Jahr")
    neu = _turn(client, "m4", "noch etwas!")
    assert neu.status_code == 409
    assert neu.json()["detail"] == "session_abgeschlossen"
    # Replay einer bekannten message_id bleibt idempotent erlaubt:
    replay = _turn(client, "m3", "Etwa 100 mal pro Jahr")
    assert replay.status_code == 200
    assert replay.json()["status"] == "fertig"
    assert replay.json()["payload"] == alt.json()["payload"]


def test_llm_ausfall_gibt_vertragsantwort_mit_status_200():
    antwort = _turn(_client(llm=ExplodierendesLLM()), "m1", "Hallo")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fehler_fortsetzbar"
    assert antwort.json()["chat_text"]  # Nutzer bekommt eine Chat-Erklärung


def test_paket_guard_wird_als_409_gemappt():
    store = InMemoryStateStore()
    store.save(SessionState("s9", "9.9", paket_name="fremdes_paket"))
    antwort = _turn(_client(store=store), "m1", "Hallo", session="s9")
    assert antwort.status_code == 409


def test_prozesse_ohne_snapshot_404():
    assert _client().get("/prozesse").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bc1_service.api'`

- [ ] **Step 3: Write implementation** — `bc1_service/api.py` und `bc1_service/main.py`

`bc1_service/api.py`:

```python
"""FastAPI-Transportschicht um process_turn.

Zustandslos gegenüber der Fachlogik: Persistenz macht der Kern (Architektur-
Invariante). Hier liegen nur die laut Design-Spec an die Transportschicht
delegierten Pflichten: schema_version-Check im Request und aktives
Zurückweisen neuer Nachrichten an fertige Sessions (Gate 0).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from bc1_core.core import process_turn
from bc1_core.llm import LLMClient
from bc1_core.package import UseCasePackage
from bc1_core.store import StateStore
from bc1_core.types import SessionStatus


class TurnRequest(BaseModel):
    session_id: str
    message_id: str
    message: str
    schema_version: str | None = None


def create_app(
    store: StateStore,
    llm: LLMClient,
    package: UseCasePackage,
    snapshot=None,
) -> FastAPI:
    app = FastAPI(title="BC1 Context Discovery", version="0.2.0")

    @app.get("/gesundheit")
    def gesundheit() -> dict:
        return {
            "status": "ok",
            "paket": package.name,
            "schema_version": package.schema_version,
        }

    @app.get("/prozesse")
    def prozesse() -> dict:
        if snapshot is None:
            raise HTTPException(status_code=404, detail="kein_snapshot_konfiguriert")
        return {"prozesse": snapshot.prozess_liste()}

    @app.post("/turn")
    def turn(req: TurnRequest) -> dict:
        if (req.schema_version is not None
                and req.schema_version != package.schema_version):
            raise HTTPException(status_code=409, detail="schema_version_passt_nicht")
        state = store.load(req.session_id)
        if (state is not None
                and state.status is SessionStatus.FERTIG
                and req.message_id not in state.antworten):
            raise HTTPException(status_code=409, detail="session_abgeschlossen")
        try:
            antwort = process_turn(
                store, llm, package, req.session_id, req.message_id, req.message
            )
        except ValueError as fehler:  # Paket-/Versions-Guard des Kerns
            raise HTTPException(status_code=409, detail=str(fehler))
        antwort["chat_text"] = _chat_text(antwort)
        return antwort

    return app


def _chat_text(antwort: dict) -> str:
    if antwort["status"] == "frage":
        return antwort["payload"]["naechste_frage"] or ""
    if antwort["status"] == "fertig":
        v = antwort["payload"]["vollstaendigkeit"]
        return f"Danke! Das Interview ist abgeschlossen (Vollständigkeit: {v:.0%})."
    return ("Da ist gerade etwas schiefgegangen — "
            "bitte schick deine Nachricht einfach noch einmal.")
```

`bc1_service/main.py`:

```python
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
from bc1_service.snapshot import lade_snapshot

_snapshot_pfad = os.environ.get("BC1_SNAPSHOT_PFAD")

app = create_app(
    PostgresStateStore(os.environ["BC1_DB_DSN"]),
    ClaudeLLM(),
    TOY_PROZESS,
    lade_snapshot(_snapshot_pfad) if _snapshot_pfad else None,
)
```

(Hinweis: `main.py` importiert `lade_snapshot` aus Task 6 — wer streng in Reihenfolge arbeitet, legt `main.py` erst nach Task 6 an oder lässt den Snapshot-Import bis dahin weg. `tests/test_api.py` importiert nur `api.py` und bleibt davon unberührt.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_api.py -v` und voll `.venv/bin/pytest`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add bc1_service/api.py bc1_service/main.py tests/test_api.py
git commit -m "feat(bc1): FastAPI-Transportschicht (/turn) mit schema_version-Check und Gate-0-Reject"
```

---

### Task 6: Snapshot-Reader (`bc1_service/snapshot.py`)

**Files:**
- Create: `bc1_service/snapshot.py`, `bc1_service/snapshot_schema.json` (Kopie des BC0-Vertragsschemas)
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: BC0-Schema (Draft-07; stabile IDs: `stammdaten.prozesse[].process_id` `^KP-[0-9]{2}$`, `…teilprozesse[].sub_process_id` `^KP-[0-9]{2}\.TP-[0-9]+$`).
- Produces: `lade_snapshot(pfad) -> Snapshot` (validiert via `jsonschema`, wirft `SnapshotFehler` bei Schema-Verstoß); `Snapshot.prozess_ids() -> list[str]`, `Snapshot.prozess(process_id) -> dict | None`, `Snapshot.teilprozess(sub_process_id) -> dict | None`, `Snapshot.prozess_liste() -> list[dict]` (nur `process_id` + `process_name`, für `/prozesse`). Read-only — BC1 schreibt NIE in BC0-Daten (Bauplan).

Vorbereitung (einmalig, Schema-Kopie aus dem lokalen BC0-Handover):

```bash
cp "/Users/rprezer/Desktop/Claude_Projekte/AutoCoE_Projekt/Drive/BC0 Vorarbeiten/Handover_BC1/09_Handover_BC0_to_BC1/snapshot_schema.json" bc1_service/snapshot_schema.json
```

- [ ] **Step 1: Write the failing test** — `tests/test_snapshot.py` (rein synthetische, generische Daten — NIE der NoroAI-Snapshot)

```python
import json

import pytest

from bc1_service.snapshot import Snapshot, SnapshotFehler, lade_snapshot


def _mini_snapshot() -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-08-01T00:00:00Z",
        "mandant": {
            "id": 1,
            "name": "Beispiel GmbH",
            "unternehmensdaten": {},
        },
        "stammdaten": {
            "items": [],
            "dimensionen": [],
            "prozesse": [
                {
                    "process_id": "KP-01",
                    "process_name": "Beispielprozess",
                    "teilprozesse": [
                        {
                            "sub_process_id": "KP-01.TP-1",
                            "step_no": 1,
                            "name": "Erster Schritt",
                        }
                    ],
                }
            ],
        },
        "bewertungen": [],
        "reifegrad": {"gesamt": 0, "dimension_durchschnitt": {}, "kp_rows": []},
    }


def _schreibe(tmp_path, daten: dict):
    pfad = tmp_path / "snapshot.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


def test_laedt_validen_snapshot_und_findet_stabile_ids(tmp_path):
    snap = lade_snapshot(_schreibe(tmp_path, _mini_snapshot()))
    assert snap.prozess_ids() == ["KP-01"]
    assert snap.prozess("KP-01")["process_name"] == "Beispielprozess"
    assert snap.teilprozess("KP-01.TP-1")["step_no"] == 1
    assert snap.prozess("KP-99") is None
    assert snap.prozess_liste() == [
        {"process_id": "KP-01", "process_name": "Beispielprozess"}
    ]


def test_schema_verstoss_wird_abgelehnt(tmp_path):
    kaputt = _mini_snapshot()
    kaputt["stammdaten"]["prozesse"][0]["process_id"] = "P1"  # verletzt Pattern
    with pytest.raises(SnapshotFehler):
        lade_snapshot(_schreibe(tmp_path, kaputt))


def test_fehlender_pflichtblock_wird_abgelehnt(tmp_path):
    kaputt = _mini_snapshot()
    del kaputt["reifegrad"]
    with pytest.raises(SnapshotFehler):
        lade_snapshot(_schreibe(tmp_path, kaputt))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bc1_service.snapshot'`

- [ ] **Step 3: Write implementation** — `bc1_service/snapshot.py`

```python
"""Read-only-Zugriff auf den BC0-Baseline-Snapshot über stabile IDs.

Vertrag: BC0-Handover v1.0 (Simeon, 16.06.) — Snapshot-Datei heute, Live-API
mit identischer Struktur später; BC1 liest nur, Rückgaben laufen über den
Anreicherungs-Pfad (nicht Teil dieses Moduls).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

_SCHEMA_PFAD = Path(__file__).with_name("snapshot_schema.json")


class SnapshotFehler(ValueError):
    pass


class Snapshot:
    def __init__(self, daten: dict) -> None:
        self._daten = daten
        self._prozesse = {
            p["process_id"]: p for p in daten["stammdaten"]["prozesse"]
        }
        self._teilprozesse = {
            tp["sub_process_id"]: tp
            for p in daten["stammdaten"]["prozesse"]
            for tp in p["teilprozesse"]
        }

    def prozess_ids(self) -> list[str]:
        return list(self._prozesse)

    def prozess(self, process_id: str) -> dict | None:
        return self._prozesse.get(process_id)

    def teilprozess(self, sub_process_id: str) -> dict | None:
        return self._teilprozesse.get(sub_process_id)

    def prozess_liste(self) -> list[dict]:
        return [
            {"process_id": p["process_id"], "process_name": p["process_name"]}
            for p in self._daten["stammdaten"]["prozesse"]
        ]


def lade_snapshot(pfad: str | Path) -> Snapshot:
    daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA_PFAD.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(daten, schema)
    except jsonschema.ValidationError as fehler:
        raise SnapshotFehler(
            f"Snapshot verletzt das BC0-Schema: {fehler.message}"
        ) from fehler
    return Snapshot(daten)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_snapshot.py -v` und voll `.venv/bin/pytest`. Zusätzlich lokaler Smoke (nicht committen, nur ausführen): `BC1_SNAPSHOT_PFAD` auf den lokalen NoroAI-Snapshot zeigen lassen und in einer Python-One-Liner-Session `lade_snapshot(...)` aufrufen — muss 10 `prozess_ids` liefern.
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add bc1_service/snapshot.py bc1_service/snapshot_schema.json tests/test_snapshot.py
git commit -m "feat(bc1): BC0-Snapshot-Reader (Schema-validiert, Zugriff ueber stabile IDs)"
```

---

### Task 7: n8n-Chat-Anbindung + Smoke-Checkliste (manuell, kein pytest)

**Files:**
- Create: `bc1_service/n8n/SMOKE.md` (Aufbauanleitung + Checkliste)
- Create: `bc1_service/n8n/bc1-chat-workflow.json` (Export aus dem funktionierenden n8n — erst NACH bestandenem Smoke committen, kein handgeschriebenes JSON)

**Interfaces:**
- Consumes: laufender Dienst aus Task 5 (`uvicorn bc1_service.main:app --port 8000`), dessen `/turn`-Vertrag und `chat_text`.
- Produces: n8n-Workflow (zustandslos, keine Fachlogik — Bauplan B1) + abgehakte 4-Szenarien-Checkliste (P2-Teststrategie Punkt 4) als Nachweis „echtes Interview im Chat gegen laufenden Dienst".

- [ ] **Step 1: Dienst starten** (eigenes Terminal; Supabase-DSN, sobald vorhanden — bis dahin lokales Docker-Postgres aus Task 3):

```bash
cd coe-factory/bc1-context-discovery
export BC1_DB_DSN="postgresql://postgres:test@localhost:55432/postgres"
export ANTHROPIC_API_KEY="..."   # nie committen
.venv/bin/uvicorn bc1_service.main:app --port 8000
```

- [ ] **Step 2: n8n starten** (Docker, Datenvolume für Wiederverwendung):

```bash
docker volume create n8n_data
docker run -it --rm --name n8n -p 5678:5678 \
  -e GENERIC_TIMEZONE="Europe/Berlin" -e TZ="Europe/Berlin" \
  -e N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true -e N8N_RUNNERS_ENABLED=true \
  -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

- [ ] **Step 3: Workflow in der n8n-UI bauen** (http://localhost:5678) — drei Nodes, exakt diese Parameter:
  1. **Chat Trigger**: „Make Chat Publicly Available" ✓ · Response Mode **„When Last Node Finishes"**. (Liefert `sessionId` + `chatInput`.)
  2. **HTTP Request**: Method POST · URL `http://host.docker.internal:8000/turn` (n8n läuft im Container — NICHT `localhost`) · Body (JSON): `session_id` = `{{ $json.sessionId }}` · `message_id` = `exec-{{ $execution.id }}` (stabil bei Node-Retries innerhalb einer Execution → Idempotenz) · `message` = `{{ $json.chatInput }}` · Options → Response → „Never Error" ✓ (damit 409 als Text ankommt statt als Workflow-Fehler).
  3. **Edit Fields (Set)**: Feld `output` (String) = `{{ $json.chat_text ?? $json.detail }}`.
- [ ] **Step 4: `SMOKE.md` schreiben** (Anleitung aus Step 1–3 + die folgende Checkliste) und die 4 Szenarien im Hosted Chat durchspielen, Ergebnis dokumentieren:
  1. **Normales Interview bis fertig:** 3–4 Antworten zum Spielzeug-Paket → Abschluss-Nachricht mit Vollständigkeit; danach in der DB prüfen: `SELECT session_id, version, state->>'status' FROM bc1.sessions;` → `fertig`.
  2. **Gleiche message_id doppelt (Idempotenz):** im n8n-Editor den HTTP-Node mit „Execute step" auf derselben Execution wiederholen ODER per curl denselben `/turn`-Body zweimal senden → identische Antwort, `rounds` wächst nicht.
  3. **LLM absichtlich kaputt:** Dienst mit `ANTHROPIC_API_KEY=ungueltig` neu starten → Chat-Nachricht ergibt die freundliche `fehler_fortsetzbar`-Erklärung, kein 500.
  4. **Danach Resume:** Key wieder korrekt setzen, Dienst neu starten, im selben Chat dieselbe Nachricht erneut senden → Interview läuft an der richtigen Stelle weiter (Crash-Resume-Pfad des Kerns).
- [ ] **Step 5: Workflow exportieren + Commit** — n8n-UI → Workflow → „Download" → als `bc1_service/n8n/bc1-chat-workflow.json` speichern.

```bash
git add bc1_service/n8n/SMOKE.md bc1_service/n8n/bc1-chat-workflow.json
git commit -m "feat(bc1): n8n-Chat-Workflow + Smoke-Checkliste (4 Szenarien, abgehakt)"
```

---

## Roadmap-Anker (NICHT Teil dieses Plans)

Nachgehalten, mit Ziel — nichts fällt still weg:

- **Gate-0-Payload gegen Schema validieren** → `contracts/bc1-to-bc2/` existiert noch nicht; entsteht mit BC2 + Platform (P4; CODEOWNERS verlangt beide Teams). Teststrategie-Punkt 5 wird dort eingelöst.
- **Dockerfile/Deployment** des FastAPI-Dienstes → sobald die Hosting-Frage (Gruppe) geklärt ist; bis dahin uvicorn lokal. (B1 nennt Docker als Ziel — bewusst vertagt, YAGNI für „läuft lokal im Chat".)
- **B7-Observability** (strukturiertes Logging inkl. verschluckter Validator-Fehler) → bewusst vertagt (Ledger); nächster Schritt: Logging-Konzept zusammen mit PII-Schicht (#50), damit nichts Sensibles geloggt wird.
- **Discovery-/Nachfass-Paket** aus Simeons Katalog + Feldtypen + Session-Bindung an `prozess_id` → P3 (der Snapshot-Reader liefert dafür bereits die Prozessliste).
- **Wert/Kandidaten-Überlappung** bei UNGUELTIG-Korrektur-Zyklen → kosmetisch, im Test gepinnt (unverändert aus P1).
- **Supabase-DSN produktiv** (Team-Projekt Frankfurt, Session Pooler) → sobald Creds da sind; Code ist DSN-agnostisch.
- **Prompt-Feinschliff des Adapters** (Feldtypen aus B1, Mehrsprachigkeit, Beispiele) → P3, wenn die echten Pakete existieren.

## Self-Review (vom Autor durchgeführt)

- **Spec-Abdeckung:** Bauplan-P2-Spalte vollständig: Claude-Adapter (Task 4) · FastAPI (Task 5) · n8n-Chat (Task 7) · Supabase-Schema `bc1` + PostgresStateStore (Task 3) · Snapshot-Reader (Task 6). Teststrategie-Punkte 1–4 abgedeckt (Punkt 5 → Roadmap-Anker, Vertrag existiert noch nicht). Ledger-Deferrals: value⇒source + set/tuple (Task 1), Thread-Sicherheit (Task 2/3), Retries/kaputtes JSON (Task 4), schema_version-Check + Gate-0-Reject (Task 5).
- **Platzhalter:** keine — jeder Code-Schritt enthält lauffähigen Code, jeder Run-Schritt den exakten Befehl mit erwartetem Ergebnis; Task 7 ist bewusst manuell (Checkliste statt pytest), das Workflow-JSON entsteht als Export, nicht als handgeschriebener Platzhalter.
- **Typ-Konsistenz:** `state_to_dict`/`state_from_dict` (Task 1) werden in Task 3 exakt so konsumiert; `StoreVertrag`-Fixture-Name `store` in beiden Subklassen identisch; `ClaudeLLM.extract/phrase` entsprechen wörtlich dem Protocol aus `bc1_core/llm.py`; `create_app(store, llm, package, snapshot=None)` wird von `main.py` und allen API-Tests mit denselben Positionen aufgerufen; `chat_text`/`detail`-Mapping in Task 7 entspricht den Antworten aus Task 5.
- **Ehrlichkeits-Hinweise:** (1) Der Nebenläufigkeits-RED in Task 2 ist probabilistisch (Race), durch breiten State + 10 Runden praktisch sicher — falls er doch grün startet, Rundenzahl erhöhen, nicht abschwächen. (2) `output_config`/Structured-Outputs-Aufruf in Task 4 folgt der aktuellen Claude-API-Referenz (geladenes Skill, Stand 2026); die Echt-API-Stichprobe verifiziert das gegen die echte API, sobald ein Key da ist.
