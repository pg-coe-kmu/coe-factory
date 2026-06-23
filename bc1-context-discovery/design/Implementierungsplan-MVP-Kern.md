# BC1 MVP-Code-Kern — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen testbaren BC1-Code-Kern bauen, der einen Text-Dialog führt und daraus ein strukturiertes Prozessprofil (JSON) mit Vollständigkeits-Status erzeugt.

**Architecture:** Reiner Python-Kern hinter einer Funktion `process_turn(...)` (das spätere n8n-Endpoint-Verhalten). Sechs interne Module mit je einer Verantwortung; das LLM steckt hinter einem `LLMClient`-Protocol und wird in Tests durch ein `FakeLLM` ersetzt. Keine n8n-, Netz- oder DB-Abhängigkeit im MVP.

**Tech Stack:** Python 3.11+, `pytest`, nur Standardbibliothek (dataclasses). Kein pydantic/Netzwerk im Kern.

## Global Constraints

- Python **3.11+** (Syntax `str | None`).
- Abhängigkeiten im Kern: **nur `pytest`** (dev). Kein pydantic, kein HTTP, kein echtes LLM.
- LLM **nur** hinter `LLMClient`-Protocol; Tests nutzen **ausschließlich `FakeLLM`** (keine Netzaufrufe).
- Persistenz gehört dem Kern: **atomar laden/speichern mit `version` (optimistic locking)**; Transport (später n8n) schreibt **nie** den State.
- **Idempotenz über `message_id`** — eine Nachricht wird nie doppelt angewandt.
- **Nie Daten verlieren:** Rohnachricht wird **vor** jedem LLM-Aufruf persistiert (`store.save` vor `extract`).
- **Keine erfundenen Zahlen:** pro Feld nur Status-Enum (`fehlt/gueltig/ungueltig/unklar/ungeloest`); `vollstaendigkeit` = erfüllte Pflichtfelder / Pflichtfelder gesamt.
- Output trägt **immer** `vollstaendigkeit`, `ungeloeste_felder`, `schema_version`.
- **Generik:** der Kern darf **nicht** auf Use-Case-/Package-Namen verzweigen (durch Naht-Test erzwungen, Task 9).
- Feld-/Status-Namen **deutsch** (konsistent mit dem Spec).
- **Commit** nach jeder Task.

## File Structure

- `pyproject.toml` — Projekt + pytest-Konfiguration
- `bc1_core/__init__.py`
- `bc1_core/types.py` — Enums + State-Dataclasses
- `bc1_core/package.py` — `UseCasePackage`, `FieldSpec` + Spielzeug-Paket
- `bc1_core/store.py` — `StateStore` (abstrakt) + `InMemoryStateStore` (versioniert)
- `bc1_core/confidence.py` — `confidence_check()`
- `bc1_core/llm.py` — `LLMClient`-Protocol + `FakeLLM`
- `bc1_core/extractor.py` — `extract_and_merge()`
- `bc1_core/dialog.py` — `decide_next()`
- `bc1_core/core.py` — `process_turn()` (die eine Schnittstelle)
- `bc1_core/cli.py` — minimaler Treiber zum Beweisen
- `tests/test_*.py` — je Modul

---

### Task 1: Scaffold + Kern-Typen

**Files:**
- Create: `pyproject.toml`, `bc1_core/__init__.py`, `bc1_core/types.py`, `tests/test_types.py`

**Interfaces:**
- Produces: `FieldStatus` (Enum: `fehlt/gueltig/ungueltig/unklar/ungeloest`), `SessionStatus` (Enum: `aktiv/wartet_auf_antwort/fertig/fehler_fortsetzbar`), `FieldValue(value,status,source_message_id,candidates,attempts)`, `SessionState(session_id,schema_version,status,version,rounds,values,processed_message_ids,raw_log,last_response)`.

- [ ] **Step 1: Write the failing test** — `tests/test_types.py`

```python
from bc1_core.types import FieldStatus, SessionStatus, FieldValue, SessionState

def test_fieldvalue_defaults_to_fehlt():
    fv = FieldValue()
    assert fv.value is None
    assert fv.status is FieldStatus.FEHLT
    assert fv.attempts == 0

def test_sessionstate_starts_active_version_zero():
    st = SessionState(session_id="s1", schema_version="0.1")
    assert st.status is SessionStatus.AKTIV
    assert st.version == 0
    assert st.values == {}
    assert st.processed_message_ids == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_types.py -v`
Expected: FAIL (`ModuleNotFoundError: bc1_core`).

- [ ] **Step 3: Create scaffold + implementation**

`pyproject.toml`:
```toml
[project]
name = "bc1-core"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`bc1_core/__init__.py`: (leer)

`bc1_core/types.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_types.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml bc1_core/ tests/test_types.py
git commit -m "feat(bc1): scaffold + core types"
```

---

### Task 2: Use-Case-Paket

**Files:**
- Create: `bc1_core/package.py`, `tests/test_package.py`

**Interfaces:**
- Consumes: nichts.
- Produces: `FieldSpec(name,question,required=True,validator=None)`; `UseCasePackage(name,schema_version,fields)` mit `.required_fields() -> list[FieldSpec]` und `.field(name) -> FieldSpec | None`; Konstante `TOY_PROZESS: UseCasePackage`.

- [ ] **Step 1: Write the failing test** — `tests/test_package.py`

```python
from bc1_core.package import UseCasePackage, FieldSpec, TOY_PROZESS

def test_required_fields_excludes_optional_and_keeps_order():
    namen = [f.name for f in TOY_PROZESS.required_fields()]
    assert namen == ["prozess_name", "ausloeser", "haeufigkeit"]

def test_field_lookup():
    assert TOY_PROZESS.field("ausloeser").question != ""
    assert TOY_PROZESS.field("gibt_es_nicht") is None

def test_validator_runs():
    h = TOY_PROZESS.field("haeufigkeit")
    assert h.validator("100 mal") is True
    assert h.validator("oft") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_package.py -v`
Expected: FAIL (`ModuleNotFoundError: bc1_core.package`).

- [ ] **Step 3: Write implementation** — `bc1_core/package.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

@dataclass
class FieldSpec:
    name: str
    question: str
    required: bool = True
    validator: Callable[[str], bool] | None = None

@dataclass
class UseCasePackage:
    name: str
    schema_version: str
    fields: list[FieldSpec]

    def required_fields(self) -> list[FieldSpec]:
        return [f for f in self.fields if f.required]

    def field(self, name: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.name == name), None)

TOY_PROZESS = UseCasePackage(
    name="toy_prozess",
    schema_version="0.1",
    fields=[
        FieldSpec("prozess_name", "Wie heißt der Prozess?"),
        FieldSpec("ausloeser", "Was löst den Prozess aus?"),
        FieldSpec("haeufigkeit", "Wie oft kommt er vor?",
                  validator=lambda v: any(c.isdigit() for c in v)),
        FieldSpec("notiz", "Sonstige Hinweise?", required=False),
    ],
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_package.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bc1_core/package.py tests/test_package.py
git commit -m "feat(bc1): declarative use-case package + toy fixture"
```

---

### Task 3: StateStore (versioniert, idempotenz-fähig)

**Files:**
- Create: `bc1_core/store.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `SessionState` (Task 1).
- Produces: `StaleStateError(Exception)`; `StateStore` (abstrakt, `load(session_id)->SessionState|None`, `save(state)->None`); `InMemoryStateStore`. `save` erhöht `state.version` und wirft `StaleStateError`, wenn die gespeicherte Version abweicht.

- [ ] **Step 1: Write the failing test** — `tests/test_store.py`

```python
import pytest
from bc1_core.types import SessionState
from bc1_core.store import InMemoryStateStore, StaleStateError

def test_load_unknown_returns_none():
    assert InMemoryStateStore().load("x") is None

def test_save_then_load_roundtrip_and_isolation():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1")
    store.save(st)
    loaded = store.load("s1")
    assert loaded.session_id == "s1"
    loaded.rounds = 99          # Änderung an der Kopie
    assert store.load("s1").rounds == 0   # darf den Store nicht berühren

def test_optimistic_locking_rejects_stale_write():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1")
    store.save(st)              # version 0 -> 1
    stale = store.load("s1")    # version 1
    store.save(store.load("s1"))  # jemand anderes speichert: version 1 -> 2
    with pytest.raises(StaleStateError):
        store.save(stale)       # stale hat version 1, gespeichert ist 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_store.py -v`
Expected: FAIL (`ModuleNotFoundError: bc1_core.store`).

- [ ] **Step 3: Write implementation** — `bc1_core/store.py`

```python
from __future__ import annotations
import copy
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

    def load(self, session_id: str) -> SessionState | None:
        st = self._data.get(session_id)
        return copy.deepcopy(st) if st is not None else None

    def save(self, state: SessionState) -> None:
        existing = self._data.get(state.session_id)
        if existing is not None and existing.version != state.version:
            raise StaleStateError(
                f"stale write for {state.session_id}: "
                f"have {existing.version}, got {state.version}"
            )
        state.version += 1
        self._data[state.session_id] = copy.deepcopy(state)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_store.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bc1_core/store.py tests/test_store.py
git commit -m "feat(bc1): versioned in-memory state store"
```

---

### Task 4: Confidence-Check (reine Logik)

**Files:**
- Create: `bc1_core/confidence.py`, `tests/test_confidence.py`

**Interfaces:**
- Consumes: `SessionState`, `FieldStatus`, `FieldValue` (Task 1), `UseCasePackage` (Task 2).
- Produces: `ConfidenceResult(statuses: dict[str,FieldStatus], completeness: float, offene_pflichtfelder: list[str], ungeloeste_felder: list[str])`; `confidence_check(state, package) -> ConfidenceResult`. `offene_pflichtfelder` in Paket-Reihenfolge; ein Feld zählt als „erfüllt" nur bei Status `GUELTIG`.

- [ ] **Step 1: Write the failing test** — `tests/test_confidence.py`

```python
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.confidence import confidence_check

def _state_with(**felder):
    st = SessionState(session_id="s1", schema_version="0.1")
    for name, status in felder.items():
        st.values[name] = FieldValue(value="x", status=status)
    return st

def test_empty_state_all_required_open():
    res = confidence_check(SessionState("s1", "0.1"), TOY_PROZESS)
    assert res.completeness == 0.0
    assert res.offene_pflichtfelder == ["prozess_name", "ausloeser", "haeufigkeit"]

def test_completeness_counts_only_gueltig():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.UNGUELTIG,
                     haeufigkeit=FieldStatus.GUELTIG)
    res = confidence_check(st, TOY_PROZESS)
    assert res.completeness == 2 / 3
    assert res.offene_pflichtfelder == ["ausloeser"]

def test_ungeloest_is_not_open_but_listed():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.GUELTIG,
                     haeufigkeit=FieldStatus.UNGELOEST)
    res = confidence_check(st, TOY_PROZESS)
    assert res.offene_pflichtfelder == []
    assert res.ungeloeste_felder == ["haeufigkeit"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_confidence.py -v`
Expected: FAIL (`ModuleNotFoundError: bc1_core.confidence`).

- [ ] **Step 3: Write implementation** — `bc1_core/confidence.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from bc1_core.types import FieldStatus, SessionState
from bc1_core.package import UseCasePackage

@dataclass
class ConfidenceResult:
    statuses: dict[str, FieldStatus]
    completeness: float
    offene_pflichtfelder: list[str]
    ungeloeste_felder: list[str]

def confidence_check(state: SessionState, package: UseCasePackage) -> ConfidenceResult:
    statuses: dict[str, FieldStatus] = {}
    for spec in package.fields:
        fv = state.values.get(spec.name)
        statuses[spec.name] = fv.status if fv is not None else FieldStatus.FEHLT

    required = package.required_fields()
    erfuellt = sum(1 for s in required if statuses[s.name] is FieldStatus.GUELTIG)
    completeness = erfuellt / len(required) if required else 1.0

    offen = [s.name for s in required
             if statuses[s.name] not in (FieldStatus.GUELTIG, FieldStatus.UNGELOEST)]
    ungeloest = [name for name, st in statuses.items() if st is FieldStatus.UNGELOEST]
    return ConfidenceResult(statuses, completeness, offen, ungeloest)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_confidence.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bc1_core/confidence.py tests/test_confidence.py
git commit -m "feat(bc1): deterministic confidence check (status + completeness)"
```

---

### Task 5: LLM-Client-Protocol + FakeLLM

**Files:**
- Create: `bc1_core/llm.py`, `tests/test_llm.py`

**Interfaces:**
- Consumes: `SessionState` (Task 1), `UseCasePackage`, `FieldSpec` (Task 2).
- Produces: `ExtractionCandidate(field_name: str, value: str)`; `LLMClient` (Protocol mit `extract(message, package, state) -> list[ExtractionCandidate]` und `phrase(field, state) -> str`); `FakeLLM(extractions: dict[str, list[ExtractionCandidate]] | None = None)`.

- [ ] **Step 1: Write the failing test** — `tests/test_llm.py`

```python
from bc1_core.types import SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.llm import FakeLLM, ExtractionCandidate

def test_fake_extract_returns_scripted_candidates():
    fake = FakeLLM({"Bestellfreigabe, monatlich":
                    [ExtractionCandidate("prozess_name", "Bestellfreigabe")]})
    out = fake.extract("Bestellfreigabe, monatlich", TOY_PROZESS, SessionState("s1", "0.1"))
    assert out == [ExtractionCandidate("prozess_name", "Bestellfreigabe")]

def test_fake_extract_unknown_message_is_empty():
    assert FakeLLM().extract("hä?", TOY_PROZESS, SessionState("s1", "0.1")) == []

def test_fake_phrase_uses_field_question():
    fake = FakeLLM()
    assert fake.phrase(TOY_PROZESS.field("ausloeser"), SessionState("s1", "0.1")) \
        == "Was löst den Prozess aus?"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL (`ModuleNotFoundError: bc1_core.llm`).

- [ ] **Step 3: Write implementation** — `bc1_core/llm.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from bc1_core.types import SessionState
from bc1_core.package import UseCasePackage, FieldSpec

@dataclass(frozen=True)
class ExtractionCandidate:
    field_name: str
    value: str

class LLMClient(Protocol):
    def extract(self, message: str, package: UseCasePackage,
                state: SessionState) -> list[ExtractionCandidate]: ...
    def phrase(self, field: FieldSpec, state: SessionState) -> str: ...

class FakeLLM:
    """Skript-gesteuertes LLM für deterministische Tests."""
    def __init__(self, extractions: dict[str, list[ExtractionCandidate]] | None = None) -> None:
        self._extractions = extractions or {}

    def extract(self, message: str, package: UseCasePackage,
                state: SessionState) -> list[ExtractionCandidate]:
        return list(self._extractions.get(message, []))

    def phrase(self, field: FieldSpec, state: SessionState) -> str:
        return field.question
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bc1_core/llm.py tests/test_llm.py
git commit -m "feat(bc1): LLM client protocol + fake LLM for tests"
```

---

### Task 6: Extractor + Merge-Regel

**Files:**
- Create: `bc1_core/extractor.py`, `tests/test_extractor.py`

**Interfaces:**
- Consumes: `SessionState`, `FieldValue`, `FieldStatus` (Task 1); `UseCasePackage` (Task 2); `LLMClient`, `ExtractionCandidate` (Task 5).
- Produces: `extract_and_merge(state, message, message_id, package, llm) -> None`. Neue Felder: Status via Validator (`GUELTIG`/`UNGUELTIG`), Quelle = `message_id`. Konflikt (anderer Wert auf bestätigtem Feld): nicht überschreiben → Wert in `candidates`, Status `UNKLAR`. Unbekannte Feldnamen werden ignoriert.

- [ ] **Step 1: Write the failing test** — `tests/test_extractor.py`

```python
from bc1_core.types import FieldStatus, SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.extractor import extract_and_merge

def test_new_value_is_stored_with_source_and_validated():
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("prozess_name", "Freigabe"),
                         ExtractionCandidate("haeufigkeit", "oft")]})
    extract_and_merge(st, "m", "msg-1", TOY_PROZESS, llm)
    assert st.values["prozess_name"].value == "Freigabe"
    assert st.values["prozess_name"].status is FieldStatus.GUELTIG
    assert st.values["prozess_name"].source_message_id == "msg-1"
    assert st.values["haeufigkeit"].status is FieldStatus.UNGUELTIG  # kein Digit

def test_unknown_field_is_ignored():
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("gibt_es_nicht", "x")]})
    extract_and_merge(st, "m", "msg-1", TOY_PROZESS, llm)
    assert "gibt_es_nicht" not in st.values

def test_conflict_does_not_overwrite_and_marks_unklar():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"                # nicht überschrieben
    assert fv.candidates == ["Bestellung"]
    assert fv.status is FieldStatus.UNKLAR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extractor.py -v`
Expected: FAIL (`ModuleNotFoundError: bc1_core.extractor`).

- [ ] **Step 3: Write implementation** — `bc1_core/extractor.py`

```python
from __future__ import annotations
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import UseCasePackage, FieldSpec
from bc1_core.llm import LLMClient

def _status_for(spec: FieldSpec, value: str) -> FieldStatus:
    if spec.validator is not None and not spec.validator(value):
        return FieldStatus.UNGUELTIG
    return FieldStatus.GUELTIG

def extract_and_merge(state: SessionState, message: str, message_id: str,
                      package: UseCasePackage, llm: LLMClient) -> None:
    for cand in llm.extract(message, package, state):
        spec = package.field(cand.field_name)
        if spec is None:
            continue
        fv = state.values.get(cand.field_name)
        if fv is None or fv.value is None:
            state.values[cand.field_name] = FieldValue(
                value=cand.value,
                status=_status_for(spec, cand.value),
                source_message_id=message_id,
            )
        elif fv.value == cand.value:
            continue
        else:
            if cand.value not in fv.candidates:
                fv.candidates.append(cand.value)
            fv.status = FieldStatus.UNKLAR
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extractor.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bc1_core/extractor.py tests/test_extractor.py
git commit -m "feat(bc1): extractor with source tagging + non-destructive conflict merge"
```

---

### Task 7: Dialog-Manager (Auswahl, Caps, Fertig-Entscheidung)

**Files:**
- Create: `bc1_core/dialog.py`, `tests/test_dialog.py`

**Interfaces:**
- Consumes: `SessionState`, `FieldStatus`, `FieldValue` (Task 1); `UseCasePackage` (Task 2); `ConfidenceResult` (Task 4); `LLMClient` (Task 5).
- Produces: Konstanten `MAX_ATTEMPTS_PER_FIELD = 2`, `MAX_ROUNDS = 20`; `Decision(done: bool, next_field: str|None=None, question: str|None=None)`; `decide_next(state, package, conf, llm) -> Decision`. Felder über dem Versuchs-Limit werden auf `UNGELOEST` gesetzt; „fertig", wenn keine offenen Pflichtfelder mehr **oder** `rounds >= MAX_ROUNDS`.

- [ ] **Step 1: Write the failing test** — `tests/test_dialog.py`

```python
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.confidence import confidence_check
from bc1_core.llm import FakeLLM
from bc1_core.dialog import decide_next, Decision, MAX_ATTEMPTS_PER_FIELD

def test_asks_first_open_field_and_counts_attempt():
    st = SessionState("s1", "0.1")
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf, FakeLLM())
    assert d.done is False
    assert d.next_field == "prozess_name"
    assert d.question == "Wie heißt der Prozess?"
    assert st.values["prozess_name"].attempts == 1

def test_done_when_no_open_required_fields():
    st = SessionState("s1", "0.1")
    for n in ("prozess_name", "ausloeser", "haeufigkeit"):
        st.values[n] = FieldValue(value="x", status=FieldStatus.GUELTIG)
    conf = confidence_check(st, TOY_PROZESS)
    assert decide_next(st, TOY_PROZESS, conf, FakeLLM()) == Decision(done=True)

def test_field_over_attempt_cap_becomes_ungeloest():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(status=FieldStatus.FEHLT,
                                           attempts=MAX_ATTEMPTS_PER_FIELD)
    st.values["ausloeser"] = FieldValue(value="x", status=FieldStatus.GUELTIG)
    st.values["haeufigkeit"] = FieldValue(value="3", status=FieldStatus.GUELTIG)
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf, FakeLLM())
    assert st.values["prozess_name"].status is FieldStatus.UNGELOEST
    assert d.done is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dialog.py -v`
Expected: FAIL (`ModuleNotFoundError: bc1_core.dialog`).

- [ ] **Step 3: Write implementation** — `bc1_core/dialog.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import UseCasePackage
from bc1_core.confidence import ConfidenceResult
from bc1_core.llm import LLMClient

MAX_ATTEMPTS_PER_FIELD = 2
MAX_ROUNDS = 20

@dataclass
class Decision:
    done: bool
    next_field: str | None = None
    question: str | None = None

def decide_next(state: SessionState, package: UseCasePackage,
                conf: ConfidenceResult, llm: LLMClient) -> Decision:
    # Cap-Politik: über dem Limit -> als ungeloest markieren
    for name in conf.offene_pflichtfelder:
        fv = state.values.get(name)
        if fv is not None and fv.attempts >= MAX_ATTEMPTS_PER_FIELD:
            fv.status = FieldStatus.UNGELOEST

    offen = [n for n in conf.offene_pflichtfelder
             if state.values.get(n) is None
             or state.values[n].status is not FieldStatus.UNGELOEST]

    if not offen or state.rounds >= MAX_ROUNDS:
        return Decision(done=True)

    target = offen[0]
    fv = state.values.get(target)
    if fv is None:
        fv = FieldValue()
        state.values[target] = fv
    fv.attempts += 1
    return Decision(done=False, next_field=target,
                    question=llm.phrase(package.field(target), state))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dialog.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bc1_core/dialog.py tests/test_dialog.py
git commit -m "feat(bc1): dialog manager with attempt caps and done-decision"
```

---

### Task 8: Orchestrator `process_turn`

**Files:**
- Create: `bc1_core/core.py`, `tests/test_core.py`

**Interfaces:**
- Consumes: alle vorherigen Module.
- Produces: `process_turn(store, llm, package, session_id, message_id, message) -> dict`. Antwort: `{"status": "frage"|"fertig", "payload": {...}}`. Reihenfolge: Idempotenz-Check → Rohnachricht loggen → `store.save` (vor LLM) → extract → confidence → dialog → finaler `store.save`. Bei „fertig" enthält payload `felder`, `vollstaendigkeit`, `ungeloeste_felder`, `schema_version`.

- [ ] **Step 1: Write the failing test** — `tests/test_core.py`

```python
from bc1_core.types import SessionStatus
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.core import process_turn

def test_first_turn_asks_first_open_field():
    store = InMemoryStateStore()
    r = process_turn(store, FakeLLM(), TOY_PROZESS, "s1", "msg-1", "hallo")
    assert r["status"] == "frage"
    assert r["payload"]["feld"] == "prozess_name"
    assert store.load("s1").raw_log == [("msg-1", "hallo")]   # roh geloggt

def test_idempotent_replay_returns_same_response_without_double_log():
    store = InMemoryStateStore()
    llm = FakeLLM({"hallo": [ExtractionCandidate("prozess_name", "Freigabe")]})
    first = process_turn(store, llm, TOY_PROZESS, "s1", "msg-1", "hallo")
    again = process_turn(store, llm, TOY_PROZESS, "s1", "msg-1", "hallo")
    assert again == first
    assert store.load("s1").raw_log == [("msg-1", "hallo")]   # nicht doppelt

def test_full_run_reaches_fertig_with_completeness():
    store = InMemoryStateStore()
    llm = FakeLLM({
        "a": [ExtractionCandidate("prozess_name", "Freigabe")],
        "b": [ExtractionCandidate("ausloeser", "Antrag geht ein")],
        "c": [ExtractionCandidate("haeufigkeit", "100 mal")],
    })
    process_turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    process_turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
    r = process_turn(store, llm, TOY_PROZESS, "s1", "m3", "c")
    assert r["status"] == "fertig"
    assert r["payload"]["vollstaendigkeit"] == 1.0
    assert r["payload"]["schema_version"] == "0.1"
    assert store.load("s1").status is SessionStatus.FERTIG
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py -v`
Expected: FAIL (`ModuleNotFoundError: bc1_core.core`).

- [ ] **Step 3: Write implementation** — `bc1_core/core.py`

```python
from __future__ import annotations
from bc1_core.types import SessionState, SessionStatus
from bc1_core.package import UseCasePackage
from bc1_core.store import StateStore
from bc1_core.llm import LLMClient
from bc1_core.extractor import extract_and_merge
from bc1_core.confidence import confidence_check, ConfidenceResult
from bc1_core.dialog import decide_next

def _profil(state: SessionState, conf: ConfidenceResult) -> dict:
    felder = {
        name: {"wert": fv.value, "status": fv.status.value,
               "quelle": fv.source_message_id, "kandidaten": fv.candidates}
        for name, fv in state.values.items()
    }
    return {
        "felder": felder,
        "vollstaendigkeit": conf.completeness,
        "ungeloeste_felder": conf.ungeloeste_felder,
        "schema_version": state.schema_version,
    }

def process_turn(store: StateStore, llm: LLMClient, package: UseCasePackage,
                 session_id: str, message_id: str, message: str) -> dict:
    state = store.load(session_id) or SessionState(session_id, package.schema_version)

    if message_id in state.processed_message_ids:
        return state.last_response

    # Rohnachricht zuerst sichern (vor jedem LLM-Aufruf)
    state.raw_log.append((message_id, message))
    state.processed_message_ids.add(message_id)
    store.save(state)

    state.rounds += 1
    extract_and_merge(state, message, message_id, package, llm)
    conf = confidence_check(state, package)
    decision = decide_next(state, package, conf, llm)

    if decision.done:
        state.status = SessionStatus.FERTIG
        resp = {"status": "fertig", "payload": _profil(state, conf)}
    else:
        state.status = SessionStatus.WARTET
        resp = {"status": "frage",
                "payload": {"naechste_frage": decision.question,
                            "feld": decision.next_field}}

    state.last_response = resp
    store.save(state)
    return resp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bc1_core/core.py tests/test_core.py
git commit -m "feat(bc1): process_turn orchestrator (raw-first, idempotent, versioned)"
```

---

### Task 9: CLI-Treiber + Naht-Test (Generik)

**Files:**
- Create: `bc1_core/cli.py`, `tests/test_seam.py`

**Interfaces:**
- Consumes: `process_turn` (Task 8), `InMemoryStateStore` (Task 3), `FakeLLM` (Task 5), `UseCasePackage`/`FieldSpec` (Task 2).
- Produces: `bc1_core/cli.py` mit `run_scripted(package, script: list[tuple[str,str]]) -> list[dict]` (script = Liste `(message_id, message)`), aufrufbar via `python -m bc1_core.cli`. Naht-Test beweist: zwei verschiedene Pakete laufen ohne Kern-Verzweigung auf Namen.

- [ ] **Step 1: Write the failing seam test** — `tests/test_seam.py`

```python
from bc1_core.package import UseCasePackage, FieldSpec
from bc1_core.store import InMemoryStateStore
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.core import process_turn

# Zweites, bewusst anderes Paket (anderer Name, andere Felder)
RECHNUNG = UseCasePackage(
    name="rechnungspruefung",
    schema_version="9.9",
    fields=[FieldSpec("lieferant", "Wer ist der Lieferant?"),
            FieldSpec("betrag", "Welcher Betrag?", validator=lambda v: any(c.isdigit() for c in v))],
)

def test_core_handles_a_different_package_unchanged():
    store = InMemoryStateStore()
    llm = FakeLLM({"x": [ExtractionCandidate("lieferant", "ACME"),
                         ExtractionCandidate("betrag", "500 EUR")]})
    r = process_turn(store, llm, RECHNUNG, "s9", "m1", "x")
    # Kern kennt RECHNUNG nicht vorab -> trotzdem korrekt, ohne Sonderlogik
    assert r["status"] == "fertig"
    assert r["payload"]["schema_version"] == "9.9"
    assert r["payload"]["vollstaendigkeit"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seam.py -v`
Expected: FAIL (`ModuleNotFoundError: ... cli` is not needed yet; this test should already PASS if the core is generic). If it FAILS for any reason other than import, the abstraction leaked — fix the core, do not special-case the package.

- [ ] **Step 3: Write the CLI driver** — `bc1_core/cli.py`

```python
from __future__ import annotations
from bc1_core.package import UseCasePackage, TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.core import process_turn

def run_scripted(package: UseCasePackage, llm: FakeLLM,
                 script: list[tuple[str, str]], session_id: str = "demo") -> list[dict]:
    store = InMemoryStateStore()
    out: list[dict] = []
    for message_id, message in script:
        out.append(process_turn(store, llm, package, session_id, message_id, message))
    return out

def main() -> None:
    llm = FakeLLM({
        "Freigabe": [ExtractionCandidate("prozess_name", "Freigabe")],
        "Antrag": [ExtractionCandidate("ausloeser", "Antrag geht ein")],
        "100 mal/Jahr": [ExtractionCandidate("haeufigkeit", "100 mal/Jahr")],
    })
    script = [("m1", "Freigabe"), ("m2", "Antrag"), ("m3", "100 mal/Jahr")]
    for resp in run_scripted(TOY_PROZESS, llm, script):
        print(resp)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run seam test + the CLI**

Run: `pytest tests/test_seam.py -v`
Expected: PASS (1 passed).
Run: `python -m bc1_core.cli`
Expected: drei `dict`-Zeilen; die letzte hat `'status': 'fertig'` mit `'vollstaendigkeit': 1.0`.

- [ ] **Step 5: Run the FULL suite + commit**

Run: `pytest -v`
Expected: alle Tests grün.
```bash
git add bc1_core/cli.py tests/test_seam.py
git commit -m "feat(bc1): scripted CLI driver + generic-seam test"
```

---

## Roadmap-Anker (NICHT Teil dieses Plans)

Folgt eigenen, späteren Plänen — hier nur als Erinnerung, damit nichts verloren geht:
- **n8n-Hülle** vor `process_turn` (Chat-Trigger, Persistenz an die geteilte Platform-DB, Antwort-Transport).
- **Echter `LLMClient`** (Anbieter offen) hinter demselben Protocol.
- **Persistenter `StateStore`** (Platform-DB) statt In-Memory.
- Spätere Schichten: Voice/OCR (#49), PII-Filter (#50), Doku-Generator (#52), Baseline-Mapper (#53).
- **BC1→BC2-Vertrag** in `contracts/bc1-to-bc2/` (Schema + Mock, gemeinsam mit BC2 + Platform); hier kommt ggf. pydantic-Validierung an der Grenze dazu.

## Self-Review (vom Autor durchgeführt)

- **Spec-Abdeckung:** B1 Schnittstelle/Versionierung → Task 3/8 · B2 Module → Task 1–8 · B3 Datenfluss/State-Machine/raw-first/Idempotenz → Task 8 · B4 Fehlerfälle (Caps→ungeloest, Konflikt, ungültig) → Task 6/7 · B5 Tests/Fake-LLM/Naht → alle + Task 9 · B6 Use-Case-Paket → Task 2/9 · B7 Observability → bewusst vertagt (Roadmap) · B8 Abgrenzung → Roadmap-Anker.
- **Platzhalter:** keine (jeder Schritt enthält lauffähigen Code/Befehl).
- **Typ-Konsistenz:** `process_turn`/`extract_and_merge`/`confidence_check`/`decide_next`/`StateStore`/`FakeLLM`/`ConfidenceResult`/`Decision`/`ExtractionCandidate` über alle Tasks gleich verwendet.
