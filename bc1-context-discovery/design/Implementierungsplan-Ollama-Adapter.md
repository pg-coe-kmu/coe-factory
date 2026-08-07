# BC1 Ollama-Adapter — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein `OllamaLLM`-Adapter (lokales Llama via Ollama, kostenlos, ohne API-Key) hinter dem bestehenden `LLMClient`-Protocol als **Test-/Dev-Ersatz** — entsperrt das Echt-LLM-End-to-End (FastAPI + n8n-Chat), solange der `ANTHROPIC_API_KEY` fehlt. Claude bleibt der Produktionsweg.

**Architecture:** Spiegelbild von `ClaudeLLM`: neue Datei `bc1_service/ollama_llm.py`, injizierbarer Client, natives Constrained Decoding (`format`=JSON-Schema) als Gegenstück zu Claudes Structured Outputs. Die drei geteilten Prompt-Konstanten und die Frage-Prompt-Konstruktion (`frage_nutzer_prompt`, Pre-Flight-Entscheidung 07.08.) ziehen in ein neues `bc1_service/prompts.py` (Wire-Vertrag, kein Drift-Risiko). Die LLM-Wahl (`BC1_LLM`: `claude`|`ollama`) liegt als direkt testbare Funktion in `bc1_service/llm_wahl.py`, die `main.py` aufruft — **bewusste Detail-Abweichung von der Spec** (dort „Umschalter in main.py"): ein `main.py`-Import zieht den Postgres-Pool hoch und ist damit nicht isoliert testbar; das Verhalten (`BC1_LLM`-Env-Var) ist exakt das spezifizierte. Der Kern (`bc1_core/`) bleibt unberührt.

**Tech Stack:** Python 3.11+ · offizielle `ollama`-Python-Lib (dev-Dependency; httpx-Kwargs werden an `httpx.Client` durchgereicht) · pytest mit Stub-Clients (kein Netz) · Ollama lokal (`llama3.1:8b`, ~5 GB, verifiziert passend für 16 GB / Apple M5).

**Spec:** lokale Design-Spec `2026-08-06-bc1-ollama-adapter-design.md` (bleibt außerhalb des Repos).

## Global Constraints

- **Branch:** `bc1-ollama-adapter`, abgezweigt von `bc1-p2-raender` (PR #130 unmerged). Alles lokal; **kein Push ohne ausdrückliches OK.**
- **TDD-Guard NIE bypassen.** Pro Task: erst der rote Test (voller `.venv/bin/pytest`-Lauf aus `bc1-context-discovery/`, damit der Reporter `test.json` schreibt), dann Implementierung. Bei einem Block: Skill `tdd-guard` aufrufen.
- **Kern bleibt unberührt:** KEINE Änderung unter `bc1_core/`.
- **Die bestehenden 131 Tests bleiben grün** (1 bestehender Skip: Claude-Echt-Stichprobe). Einzige Änderung an Bestehendem: Import-Tausch in `claude_llm.py` (Task 1) und die `waehle_llm`-Verdrahtung in `main.py` (Task 4) — beides verhaltensneutral, durch die bestehende Suite abgedeckt.
- **Kein Netz in Tests:** Ollama nur über injizierte Stubs. Echt-Stichprobe NUR mit `BC1_ECHT_LLM=1` und laufendem Ollama (sonst skip) — dasselbe Flag wie beim Claude-Echt-Test, kein zweites (YAGNI).
- **Einzige neue Dependency:** `ollama`, in die **dev-Gruppe** (Dev-Werkzeug, bringt nur httpx + pydantic mit — beides faktisch da). NICHT in `service`. Installation in Task 2:
  ```bash
  cd coe-factory/bc1-context-discovery
  uv pip install --python .venv/bin/python ollama
  ```
- **Temperature 0, `stream=False`, `num_predict` 4096** bei jedem Ollama-Aufruf (Primärdoku-Empfehlung für Determinismus; Stream-Default der REST-API ist true).
- Deutsche Namen und Docstrings wie im Bestand; Conventional Commits mit Scope `bc1`; Commit nach jedem RED→GREEN-Paar.
- Generik-Invariante gilt weiter: keine Verzweigung auf Use-Case- oder Feldnamen.
- **Rolle „Test-/Dev-Ersatz" nicht aufweichen:** kein Prompt-Tuning pro Modell, keine Qualitäts-Evals, keine zusätzlichen Retry-Schleifen.

## File Structure

- `bc1_service/prompts.py` — Create: geteilte Konstanten `EXTRAKTIONS_SCHEMA`, `SYSTEM_EXTRAKTION`, `SYSTEM_FRAGE` + Funktion `frage_nutzer_prompt(field, state)`
- `bc1_service/claude_llm.py` — Modify: Import-Tausch auf `prompts.py` (mechanisch, kein Verhaltens-Change)
- `bc1_service/ollama_llm.py` — Create: `OllamaLLM` (extract/phrase, Guards)
- `bc1_service/llm_wahl.py` — Create: `waehle_llm(umgebung)` (BC1_LLM-Umschalter)
- `bc1_service/main.py` — Modify: `waehle_llm(os.environ)` statt festem `ClaudeLLM()`, Docstring-Ergänzung
- `bc1_service/n8n/SMOKE.md` — Modify: neuer Abschnitt „Smoke mit Ollama"
- `pyproject.toml` — Modify: `dev`-Gruppe um `ollama`
- `tests/test_prompts.py`, `tests/test_ollama_llm.py`, `tests/test_llm_wahl.py` — Create

## Reihenfolge

Task 1 → 2 → 3 → 4 sequenziell (Konstanten → extract → phrase → Wahl). Task 5 (Echt-Stichprobe, SMOKE, Setup) braucht 2–4.

---

### Task 1: Geteilte Prompt-Konstanten (`bc1_service/prompts.py`)

**Files:**
- Create: `bc1_service/prompts.py`
- Modify: `bc1_service/claude_llm.py` (Import-Tausch)
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: die drei Modul-Konstanten aus `claude_llm.py:21-50` (werden wörtlich verschoben) und die Nutzer-Prompt-Konstruktion aus `ClaudeLLM.phrase` (wird als Funktion herausgezogen).
- Produces: `EXTRAKTIONS_SCHEMA: dict` (JSON-Schema: `{"extraktionen": [{"feld", "wert"}]}`, `additionalProperties: False`), `SYSTEM_EXTRAKTION: str`, `SYSTEM_FRAGE: str`, `frage_nutzer_prompt(field: FieldSpec, state: SessionState) -> str` (Nutzer-Prompt inkl. Nachfrage-Hinweis ab `attempts > 1`) — öffentliche Namen ohne Unterstrich. Task 2/3 importieren exakt diese vier Namen.

- [ ] **Step 1: Branch anlegen + Plan committen**

```bash
cd coe-factory && git checkout -b bc1-ollama-adapter bc1-p2-raender
git add bc1-context-discovery/design/Implementierungsplan-Ollama-Adapter.md
git commit -m "docs(bc1): Implementierungsplan Ollama-Adapter"
```

- [ ] **Step 2: Write the failing test** — `tests/test_prompts.py`

```python
"""Die geteilten Prompt-Konstanten sind ein Wire-Vertrag zwischen den
LLM-Adaptern und dem Extractor — beide Adapter importieren aus prompts.py,
damit nichts driftet."""
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_FRAGE,
)


def test_extraktions_schema_ist_der_wire_vertrag():
    eintrag = EXTRAKTIONS_SCHEMA["properties"]["extraktionen"]["items"]
    assert eintrag["required"] == ["feld", "wert"]
    assert eintrag["additionalProperties"] is False
    assert EXTRAKTIONS_SCHEMA["required"] == ["extraktionen"]


def test_system_prompts_sind_die_bekannten_deutschen_prompts():
    assert "extrahierst" in SYSTEM_EXTRAKTION
    assert "Interview" in SYSTEM_FRAGE


def test_frage_prompt_markiert_nachfragen_ab_zweitem_versuch():
    state = SessionState("s1", "0.1")
    # attempts zählt der Dialog VOR dem phrase-Aufruf hoch: 1 = Erstfrage,
    # ab 2 ist es wirklich eine Nachfrage.
    state.values["haeufigkeit"] = FieldValue(attempts=2)
    prompt = frage_nutzer_prompt(TOY_PROZESS.field("haeufigkeit"), state)
    assert "Nachfrage" in prompt
    assert "haeufigkeit" in prompt


def test_frage_prompt_erstfrage_ohne_nachfrage_hinweis():
    state = SessionState("s1", "0.1")
    state.values["haeufigkeit"] = FieldValue(attempts=1)
    prompt = frage_nutzer_prompt(TOY_PROZESS.field("haeufigkeit"), state)
    assert "Nachfrage" not in prompt
```

Die Import-Zeilen der Testdatei entsprechend:

```python
from bc1_core.package import TOY_PROZESS
from bc1_core.types import FieldValue, SessionState
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_FRAGE,
    frage_nutzer_prompt,
)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_prompts.py -v` (aus `bc1-context-discovery/`)
Expected: FAIL mit `ModuleNotFoundError: No module named 'bc1_service.prompts'`

- [ ] **Step 4: `prompts.py` anlegen (Konstanten wörtlich aus `claude_llm.py` verschieben)**

```python
"""Geteilte Prompt-Bausteine der LLM-Adapter (Claude, Ollama).

Das Extraktionsschema ist de facto ein Wire-Vertrag mit dem Extractor,
und der Frage-Prompt (inkl. Nachfrage-Hinweis) ist Dialog-Verhalten —
deshalb EIN Ort statt Kopien pro Adapter (Drift-Risiko).
"""
from __future__ import annotations

from bc1_core.package import FieldSpec
from bc1_core.types import SessionState

EXTRAKTIONS_SCHEMA = {
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

SYSTEM_EXTRAKTION = (
    "Du extrahierst Fakten aus einer Interview-Antwort für ein Prozessprofil. "
    "Extrahiere NUR, was die Nachricht wirklich belegt — nichts erfinden, "
    "nichts aus Vorwissen ergänzen. Werte wörtlich bzw. minimal normalisiert."
)

SYSTEM_FRAGE = (
    "Du führst ein freundliches, professionelles Prozess-Interview auf Deutsch. "
    "Antworte NUR mit der Frage selbst — ohne Einleitung, ohne Anführungszeichen."
)


def frage_nutzer_prompt(field: FieldSpec, state: SessionState) -> str:
    """Nutzer-Prompt für die Frage-Formulierung — von beiden Adaptern geteilt."""
    bisher = state.values.get(field.name)
    hinweis = (
        "\nEs ist eine Nachfrage: Die bisherige Antwort war unklar oder "
        "ungültig — formuliere die Frage anders und konkreter."
        # Der Dialog zählt attempts VOR diesem Aufruf hoch: 1 = Erstfrage,
        # ab 2 ist es wirklich eine Nachfrage.
        if bisher is not None and bisher.attempts > 1
        else ""
    )
    return (
        "Formuliere genau eine Chat-Frage für dieses Feld:\n"
        f"Feld: {field.name}\nKernfrage: {field.question}{hinweis}"
    )
```

In `claude_llm.py`:
1. Die drei Konstanten-Definitionen (Zeilen 21–50) löschen und ersetzen durch

```python
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_FRAGE,
    frage_nutzer_prompt,
)
```

2. Die Verwendungsstellen umbenennen: `_EXTRAKTIONS_SCHEMA` → `EXTRAKTIONS_SCHEMA` (in `extract`), `_SYSTEM_EXTRAKTION` → `SYSTEM_EXTRAKTION` (in `extract`), `_SYSTEM_FRAGE` → `SYSTEM_FRAGE` (in `phrase`).
3. In `phrase` die lokale `bisher`/`hinweis`-Konstruktion und den Inline-Content ersetzen — der Methodenrumpf wird zu:

```python
    def phrase(self, field: FieldSpec, state: SessionState) -> str:
        antwort = self._client.messages.create(
            model=self._modell,
            max_tokens=4096,
            system=SYSTEM_FRAGE,
            output_config={"effort": "low"},   # eine Frage formulieren, mehr nicht
            messages=[{
                "role": "user",
                "content": frage_nutzer_prompt(field, state),
            }],
        )
        return self._text_inhalt(antwort).strip()
```

Die bestehenden Tests `test_phrase_liefert_frage_und_markiert_nachfragen` und `test_phrase_erstfrage_ist_keine_nachfrage` in `test_claude_llm.py` bleiben unverändert und beweisen die Verhaltensneutralität des Umbaus.

- [ ] **Step 5: Run tests to verify green (VOLLER Lauf — beweist den verhaltensneutralen Umbau)**

Run: `.venv/bin/pytest -q`
Expected: **135 passed, 1 skipped** (131 + 4 neue; Skip = Claude-Echt-Stichprobe)

- [ ] **Step 6: Commit**

```bash
git add bc1-context-discovery/bc1_service/prompts.py bc1-context-discovery/bc1_service/claude_llm.py bc1-context-discovery/tests/test_prompts.py
git commit -m "refactor(bc1): geteilte Prompt-Konstanten nach bc1_service/prompts.py (Wire-Vertrag, Drift-Schutz)"
```

---

### Task 2: `OllamaLLM.extract` (`bc1_service/ollama_llm.py`)

**Files:**
- Create: `bc1_service/ollama_llm.py`
- Modify: `pyproject.toml` (dev-Gruppe um `ollama`)
- Test: `tests/test_ollama_llm.py`

**Interfaces:**
- Consumes: `EXTRAKTIONS_SCHEMA`, `SYSTEM_EXTRAKTION` aus Task 1; `ExtractionCandidate` aus `bc1_core.llm`; `UseCasePackage`, `FieldSpec` aus `bc1_core.package`; `SessionState` aus `bc1_core.types`.
- Produces: Klasse `OllamaLLM` mit `__init__(client=None, modell: str | None = None)`, `extract(message: str, package: UseCasePackage, state: SessionState) -> list[ExtractionCandidate]` und interner Helfer `_chat(nachrichten: list[dict], format=None) -> str` (gibt `message.content` zurück; Guards siehe unten). Task 3 ergänzt `phrase` in derselben Klasse; Task 4 instanziert `OllamaLLM()` ohne Argumente. `STANDARD_MODELL = "llama3.1:8b"`; Modell-Override per `BC1_OLLAMA_MODELL`.

- [ ] **Step 1: Dependency installieren + eintragen**

```bash
cd coe-factory/bc1-context-discovery
uv pip install --python .venv/bin/python ollama
```

`pyproject.toml` Zeile 7 ändern zu:

```toml
dev = ["pytest", "httpx", "httpx2", "ollama"]
```

- [ ] **Step 2: Write the failing tests** — `tests/test_ollama_llm.py`

```python
import json
import os

import httpx
import pytest

from bc1_core.package import TOY_PROZESS
from bc1_core.types import SessionState
from bc1_service.ollama_llm import OllamaLLM


class _Nachricht:
    def __init__(self, content: str) -> None:
        self.content = content


class _Antwort:
    def __init__(self, content: str, done_reason: str = "stop") -> None:
        self.message = _Nachricht(content)
        self.done_reason = done_reason


class _StubClient:
    """Zeichnet chat()-Aufrufe auf — Muster wie _StubClient in test_claude_llm.py."""

    def __init__(self, antworten: list) -> None:
        self._antworten = list(antworten)
        self.aufrufe: list[dict] = []

    def chat(self, **kwargs):
        self.aufrufe.append(kwargs)
        return self._antworten.pop(0)


class _KaputterClient:
    def chat(self, **kwargs):
        raise httpx.ConnectError("All connection attempts failed")


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
    llm = OllamaLLM(client=stub)
    kandidaten = llm.extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    assert [(k.field_name, k.value) for k in kandidaten] == [
        ("prozess_name", "Urlaubsantrag")
    ]


# Constrained Decoding + Determinismus sind der Kern des Adapters: das Schema
# erzwingt valides JSON, temperature 0 macht Dev-Läufe reproduzierbar, und
# stream=False ist Pflicht (REST-Default wäre streaming).
def test_extract_nutzt_schema_temperature_null_und_kein_streaming():
    stub = _StubClient([_Antwort(_extraktions_json())])
    OllamaLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    aufruf = stub.aufrufe[0]
    assert aufruf["format"]["required"] == ["extraktionen"]
    assert aufruf["stream"] is False
    assert aufruf["options"]["temperature"] == 0
    assert aufruf["options"]["num_predict"] == 4096


# Abgeschnittene Antworten sind kaputte Antworten (halbes JSON) — muss laut
# werden, statt dass json.loads mit irreführender Meldung scheitert.
def test_abgeschnittene_antwort_wirft():
    stub = _StubClient([_Antwort("{\"extrakt", done_reason="length")])
    with pytest.raises(RuntimeError):
        OllamaLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))


# DER typische Dev-Stolperer: Ollama läuft nicht. Der nackte httpx-Fehler
# ist kryptisch — die Meldung muss den Fix nennen.
def test_verbindungsfehler_nennt_ollama_serve():
    with pytest.raises(RuntimeError, match="ollama serve"):
        OllamaLLM(client=_KaputterClient()).extract(
            "...", TOY_PROZESS, SessionState("s1", "0.1")
        )


def test_modell_override_aus_umgebung(monkeypatch):
    monkeypatch.setenv("BC1_OLLAMA_MODELL", "test-modell")
    stub = _StubClient([_Antwort(_extraktions_json())])
    OllamaLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    assert stub.aufrufe[0]["model"] == "test-modell"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ollama_llm.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'bc1_service.ollama_llm'`

- [ ] **Step 4: Write minimal implementation** — `bc1_service/ollama_llm.py`

```python
"""Ollama-Adapter hinter dem LLMClient-Protocol des Kerns — Test-/Dev-Ersatz.

Lokales Llama via Ollama: kostenlos, ohne API-Key. Claude bleibt der
Produktionsweg; dieser Adapter entsperrt Echt-LLM-End-to-End-Tests und
erreicht bewusst NICHT Claudes Extraktionsqualität (8B-Modell, kein
Prompt-Tuning). Exceptions fliegen durch — process_turn macht daraus den
fehler_fortsetzbar-Vertrag. format=JSON-Schema (Constrained Decoding)
garantiert valides JSON, temperature 0 macht Läufe deterministisch.
"""
from __future__ import annotations

import json
import os

import httpx
import ollama

from bc1_core.llm import ExtractionCandidate
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import SessionState
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_FRAGE,
)

STANDARD_MODELL = "llama3.1:8b"


class OllamaLLM:
    def __init__(self, client=None, modell: str | None = None) -> None:
        # 120 s statt Claudes 30 s: die erste lokale Anfrage lädt das
        # Modell erst in den Speicher (bis ~30 s auf 16-GB-Hardware).
        self._client = client or ollama.Client(timeout=120.0)
        self._modell = modell or os.environ.get("BC1_OLLAMA_MODELL", STANDARD_MODELL)

    def extract(
        self, message: str, package: UseCasePackage, state: SessionState
    ) -> list[ExtractionCandidate]:
        felder = "\n".join(f"- {f.name}: {f.question}" for f in package.fields)
        inhalt = self._chat(
            [
                {"role": "system", "content": SYSTEM_EXTRAKTION},
                {
                    "role": "user",
                    "content": (
                        f"Felder des Prozessprofils:\n{felder}\n\n"
                        f"Interview-Nachricht:\n{message}\n\n"
                        "Gib alle Feld-Wert-Paare zurück, die diese Nachricht "
                        "belegt — als JSON nach dem vorgegebenen Schema "
                        "(extraktionen: Liste aus feld/wert)."
                    ),
                },
            ],
            format=EXTRAKTIONS_SCHEMA,
        )
        daten = json.loads(inhalt)
        bekannte = {f.name for f in package.fields}
        return [
            ExtractionCandidate(e["feld"], e["wert"].strip())
            for e in daten["extraktionen"]
            if e["feld"] in bekannte and e["wert"].strip()
        ]

    def _chat(self, nachrichten: list[dict], format=None) -> str:
        try:
            antwort = self._client.chat(
                model=self._modell,
                messages=nachrichten,
                format=format,
                stream=False,
                # Primärdoku-Empfehlung: temperature 0 für Determinismus.
                options={"temperature": 0, "num_predict": 4096},
            )
        except httpx.ConnectError as fehler:
            raise RuntimeError(
                f"Ollama ist nicht erreichbar ({fehler}). Läuft `ollama serve`?"
            ) from fehler
        if antwort.done_reason == "length":
            raise RuntimeError("LLM-Antwort abgeschnitten (num_predict)")
        return antwort.message.content
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: **140 passed, 1 skipped** (135 + 5 neue)

- [ ] **Step 6: Commit**

```bash
git add bc1-context-discovery/bc1_service/ollama_llm.py bc1-context-discovery/tests/test_ollama_llm.py bc1-context-discovery/pyproject.toml
git commit -m "feat(bc1): OllamaLLM.extract — lokaler Llama-Adapter (Constrained Decoding, Guards)"
```

---

### Task 3: `OllamaLLM.phrase` + Protocol-Nachweis

**Files:**
- Modify: `bc1_service/ollama_llm.py`
- Test: `tests/test_ollama_llm.py`

**Interfaces:**
- Consumes: `_chat` und Klassen-Gerüst aus Task 2; `SYSTEM_FRAGE` aus Task 1; `FieldValue` aus `bc1_core.types`; `process_turn` aus `bc1_core.core`; `InMemoryStateStore` aus `bc1_core.store`.
- Produces: `phrase(field: FieldSpec, state: SessionState) -> str` — damit erfüllt `OllamaLLM` das komplette `LLMClient`-Protocol; Task 4/5 verlassen sich darauf.

- [ ] **Step 1: Write the failing tests** — ergänzen in `tests/test_ollama_llm.py`

```python
from bc1_core.core import process_turn
from bc1_core.store import InMemoryStateStore
from bc1_core.types import FieldValue


def test_phrase_liefert_frage_und_markiert_nachfragen():
    stub = _StubClient([_Antwort("  Wie oft kommt der Prozess vor?  ")])
    state = SessionState("s1", "0.1")
    # attempts zählt der Dialog VOR dem phrase-Aufruf hoch: 1 = Erstfrage,
    # 2 = erste Nachfrage (MAX_ATTEMPTS_PER_FIELD = 2).
    state.values["haeufigkeit"] = FieldValue(attempts=2)
    frage = OllamaLLM(client=stub).phrase(TOY_PROZESS.field("haeufigkeit"), state)
    assert frage == "Wie oft kommt der Prozess vor?"
    assert "Nachfrage" in stub.aufrufe[0]["messages"][1]["content"]


def test_phrase_erstfrage_ist_keine_nachfrage():
    stub = _StubClient([_Antwort("Wie oft kommt der Prozess vor?")])
    state = SessionState("s1", "0.1")
    state.values["haeufigkeit"] = FieldValue(attempts=1)   # Erstfrage
    OllamaLLM(client=stub).phrase(TOY_PROZESS.field("haeufigkeit"), state)
    assert "Nachfrage" not in stub.aufrufe[0]["messages"][1]["content"]


def test_phrase_abgeschnitten_wirft():
    stub = _StubClient([_Antwort("Wie oft", done_reason="length")])
    with pytest.raises(RuntimeError):
        OllamaLLM(client=stub).phrase(
            TOY_PROZESS.field("haeufigkeit"), SessionState("s1", "0.1")
        )


def test_protocol_konformitaet_ein_turn_durch_process_turn():
    stub = _StubClient([
        _Antwort(_extraktions_json(("prozess_name", "Urlaubsantrag"))),
        _Antwort("Was löst den Prozess aus?"),
    ])
    antwort = process_turn(
        InMemoryStateStore(), OllamaLLM(client=stub), TOY_PROZESS,
        "s1", "m1", "Der Prozess heißt Urlaubsantrag",
    )
    assert antwort["status"] == "frage"
    assert antwort["payload"]["feld"] == "ausloeser"
    assert antwort["payload"]["naechste_frage"] == "Was löst den Prozess aus?"
```

Hinweis: In `phrase` ist der User-Prompt `messages[1]` (Index 0 = System) — anders als bei Claude, wo `system=` ein eigener Parameter ist und der User-Prompt `messages[0]` ist.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ollama_llm.py -v`
Expected: die 4 neuen FAIL mit `AttributeError: 'OllamaLLM' object has no attribute 'phrase'`

- [ ] **Step 3: Write minimal implementation** — `phrase` in der Klasse ergänzen; im Import-Block von `ollama_llm.py` zusätzlich `frage_nutzer_prompt` aus `bc1_service.prompts` importieren (der Block hat dann dieselben vier Namen wie in `claude_llm.py`).

```python
    def phrase(self, field: FieldSpec, state: SessionState) -> str:
        inhalt = self._chat([
            {"role": "system", "content": SYSTEM_FRAGE},
            {"role": "user", "content": frage_nutzer_prompt(field, state)},
        ])
        return inhalt.strip()
```

(Die Nachfrage-Logik lebt im geteilten `frage_nutzer_prompt` — Pre-Flight-Entscheidung 07.08., kein Duplikat der Claude-Logik.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: **144 passed, 1 skipped**

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_service/ollama_llm.py bc1-context-discovery/tests/test_ollama_llm.py
git commit -m "feat(bc1): OllamaLLM.phrase — Protocol komplett, Turn-Nachweis über process_turn"
```

---

### Task 4: LLM-Wahl (`bc1_service/llm_wahl.py`) + `main.py`-Verdrahtung

**Files:**
- Create: `bc1_service/llm_wahl.py`
- Modify: `bc1_service/main.py`
- Test: `tests/test_llm_wahl.py`

**Interfaces:**
- Consumes: `ClaudeLLM` aus `bc1_service.claude_llm`, `OllamaLLM` aus Task 2/3.
- Produces: `waehle_llm(umgebung: Mapping[str, str]) -> ClaudeLLM | OllamaLLM` — liest `BC1_LLM` (`"claude"` = Default | `"ollama"`), wirft `RuntimeError` bei unbekanntem Wert. `main.py` ruft `waehle_llm(os.environ)` auf.

- [ ] **Step 1: Write the failing tests** — `tests/test_llm_wahl.py`

```python
"""BC1_LLM wählt die LLM-Implementierung — Default bleibt Claude.

Eigenes Modul statt Logik in main.py: der main-Import zieht den
Postgres-Pool hoch und wäre nicht isoliert testbar.
"""
import os

import pytest

from bc1_service.claude_llm import ClaudeLLM
from bc1_service.llm_wahl import waehle_llm
from bc1_service.ollama_llm import OllamaLLM


def test_default_ist_claude(monkeypatch):
    # Dummy-Key: das Anthropic-SDK verlangt beim Konstruieren einen Key,
    # es wird aber kein Netz angefasst.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert isinstance(waehle_llm({}), ClaudeLLM)


def test_ollama_waehlt_den_ollama_adapter():
    assert isinstance(waehle_llm({"BC1_LLM": "ollama"}), OllamaLLM)


def test_unbekannter_wert_wirft_lesbar():
    with pytest.raises(RuntimeError, match="BC1_LLM"):
        waehle_llm({"BC1_LLM": "gpt"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_llm_wahl.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'bc1_service.llm_wahl'`

- [ ] **Step 3: Write minimal implementation** — `bc1_service/llm_wahl.py`

```python
"""Wählt die LLM-Implementierung anhand von BC1_LLM (Default: claude)."""
from __future__ import annotations

from typing import Mapping

from bc1_service.claude_llm import ClaudeLLM


def waehle_llm(umgebung: Mapping[str, str]):
    wahl = umgebung.get("BC1_LLM", "claude")
    if wahl == "claude":
        return ClaudeLLM()
    if wahl == "ollama":
        # Import nur hier: der Claude-Produktionspfad braucht das
        # ollama-Paket (dev-Dependency) nie.
        from bc1_service.ollama_llm import OllamaLLM

        return OllamaLLM()
    raise RuntimeError(
        f"BC1_LLM='{wahl}' ist unbekannt — erlaubt sind 'claude' (Default) "
        "oder 'ollama' (lokaler Test-/Dev-Ersatz)."
    )
```

In `main.py`:
1. Docstring-Zeile 3–4 ergänzen um: `BC1_LLM ("claude" | "ollama", Default claude — ollama = lokaler Test-/Dev-Ersatz ohne API-Key, braucht die dev-Dependency ollama), BC1_OLLAMA_MODELL.`
2. Import `from bc1_service.claude_llm import ClaudeLLM` ersetzen durch `from bc1_service.llm_wahl import waehle_llm`.
3. Im `create_app(...)`-Aufruf `ClaudeLLM()` ersetzen durch `waehle_llm(os.environ)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: **147 passed, 1 skipped** (der bestehende `test_main_ohne_dsn_meldet_die_fehlende_variable` bleibt grün: die DSN-Prüfung läuft vor der LLM-Wahl)

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_service/llm_wahl.py bc1-context-discovery/bc1_service/main.py bc1-context-discovery/tests/test_llm_wahl.py
git commit -m "feat(bc1): BC1_LLM-Umschalter (claude|ollama) als testbare Wahl-Funktion"
```

---

### Task 5: Echt-Stichprobe, SMOKE.md-Abschnitt, Ollama-Setup

**Files:**
- Modify: `tests/test_ollama_llm.py` (Echt-Stichprobe), `bc1_service/n8n/SMOKE.md` (neuer Abschnitt)

**Interfaces:**
- Consumes: `OllamaLLM` komplett (Task 2/3); Guard-Meldung „Läuft \`ollama serve\`?" aus Task 2 (die Stichprobe erkennt daran „Ollama läuft nicht" → skip).
- Produces: nichts für weitere Tasks — Abschluss-Task.

- [ ] **Step 1: Echt-Stichprobe ergänzen** — ans Ende von `tests/test_ollama_llm.py`

```python
@pytest.mark.skipif(
    not os.environ.get("BC1_ECHT_LLM"),
    reason="Echt-Stichprobe nur mit BC1_ECHT_LLM=1 (lokal, aber langsam)",
)
def test_echt_ollama_stichprobe_extraktion():
    llm = OllamaLLM()
    try:
        kandidaten = llm.extract(
            "Der Prozess heißt Urlaubsantrag und läuft etwa 50 mal pro Jahr.",
            TOY_PROZESS,
            SessionState("s1", "0.1"),
        )
    except RuntimeError as fehler:
        if "ollama serve" in str(fehler):
            pytest.skip("Ollama läuft nicht")
        raise
    felder = {k.field_name for k in kandidaten}
    assert "prozess_name" in felder
```

(Kein RED-Schritt: der Test ist ohne `BC1_ECHT_LLM=1` per Design ein Skip — reine Test-Datei-Ergänzung, keine Implementierung.)

- [ ] **Step 2: Ollama auf dem Mac installieren + Modell ziehen** (einmalig; ~5 GB Download)

```bash
brew install ollama
ollama serve &
ollama pull llama3.1:8b
```

- [ ] **Step 3: Echt-Stichprobe real laufen lassen**

Run: `BC1_ECHT_LLM=1 .venv/bin/pytest tests/test_ollama_llm.py::test_echt_ollama_stichprobe_extraktion -v`
Expected: PASS (erste Anfrage bis ~30 s — Modell-Load). Falls stattdessen der Claude-Echt-Test mitläuft: nur diesen einen Test-Node aufrufen wie angegeben.

- [ ] **Step 4: SMOKE.md-Abschnitt ergänzen** — nach dem Abschnitt „Wiederholung mit echtem Claude" (Zeile 108 ff.) anfügen:

```markdown
## Smoke mit Ollama (lokal, ohne API-Key)

Ersetzt die Claude-Abnahme NICHT (die bleibt offen, bis der Key da ist) —
erlaubt aber Echt-LLM-End-to-End jederzeit lokal. Erwartung ehrlich: das
8B-Modell extrahiert schwächer als Claude; es testet die Maschinerie,
nicht die Interview-Qualität.

Voraussetzungen (einmalig): `brew install ollama` · `ollama pull llama3.1:8b` (~5 GB).

1. Ollama starten: `ollama serve` (oder `brew services start ollama`).
2. Dienst starten wie oben (Postgres-Container, DSN), zusätzlich:
   `export BC1_LLM=ollama` (optional `BC1_OLLAMA_MODELL=<modell>`).
   Das ollama-Paket ist dev-Dependency — im .venv vorhanden.
3. Die 4 Smoke-Szenarien aus der Checkliste oben unverändert durchspielen.
   Hinweis: erste Antwort bis ~30 s (Modell-Load), danach schneller.
4. Echt-Stichprobe der Suite:
   `BC1_ECHT_LLM=1 .venv/bin/pytest tests/test_ollama_llm.py -v -k echt`
```

- [ ] **Step 5: Voller Suite-Lauf + Commit**

Run: `.venv/bin/pytest -q`
Expected: **147 passed, 2 skipped** (neu: Ollama-Echt-Stichprobe skippt ohne Flag)

```bash
git add bc1-context-discovery/tests/test_ollama_llm.py bc1-context-discovery/bc1_service/n8n/SMOKE.md
git commit -m "test(bc1): Ollama-Echt-Stichprobe (Flag-gated) + Smoke-Anleitung Ollama"
```

---

## Abnahme (Gesamtergebnis)

- Suite: **147 passed, 2 skipped** (Claude-Echt + Ollama-Echt ohne Flags), 0 Warnings.
- `BC1_LLM=ollama` + laufendes Ollama: die 4 Smoke-Szenarien aus SMOKE.md real bestanden.
- `bc1_core/` unverändert (`git diff bc1-p2-raender -- bc1-context-discovery/bc1_core/` ist leer).
- Kein Push ohne ausdrückliches OK.
