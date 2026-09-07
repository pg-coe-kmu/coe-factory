# BC1 Gemini-Adapter — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dritter LLM-Adapter `GeminiLLM` (Google Gemini API, Free Tier) hinter dem
bestehenden `LLMClient`-Protocol — entsperrt die Klang-Abnahme der Gesprächsschicht.

**Architecture:** Spiegel des Ollama-Adapters: `extract()` mit JSON-Schema-erzwungener
Ausgabe über `response_json_schema`, `antworte()` über die geteilten Prompts; ein privater
`_generate()`-Helfer bündelt Konfiguration und Guards. Umschalten per `BC1_LLM=gemini`
(lazy import — der Claude-Pfad lädt die Lib nie). Kern, Prompts und Transport bleiben
unverändert.

**Tech Stack:** Python 3.12 · `google-genai` (SDK, neue service-Dependency) · pytest mit
Stubs (kein Netz) · Echt-Stichprobe hinter Flag.

**Bindende Design-Spec:** `docs/superpowers/specs/2026-08-11-bc1-gemini-adapter-design.md`
(im Projekt-Root über dem Clone; freigegeben 11.08. nach Codex-Design-Review).

## Global Constraints

- **Branch:** `bc1-gemini-adapter`, abgezweigt von `bc1-ollama-adapter` (Stand 7f29a8d,
  nach Merge PR #155). Task 1 committet diesen Plan.
- **TDD.** pytest IMMER aus `bc1-context-discovery/` und IMMER mit Test-DB:
  `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
  (Container `bc1-test-pg` auf Port 55432; falls er nicht läuft:
  `docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16`).
- **Suite-Basis: 220 passed, 2 skipped, 0 Warnings.** Expected-Zahlen sind Momentaufnahmen —
  reale Zahlen laufen lassen und berichten, Abweichungen explizit.
- **SDK-Fakten (am Quelltext google-genai 2.17.0 verifiziert — Feasibility-Gate 11.08.,
  NICHT anzweifeln, NICHT umdeuten):**
  - `types.HttpOptions.timeout` ist in **MILLISEKUNDEN** → 30 s = `30_000`.
  - `types.HttpRetryOptions.attempts` zählt **inklusive Erstversuch**; Default wäre 5 →
    `attempts=1` bedeutet: keine Retries.
  - `response_json_schema` + `response_mime_type="application/json"` akzeptiert unser
    volles `EXTRAKTIONS_SCHEMA` (unterstützte Keywords laut SDK-Doku ausdrücklich inkl.
    `properties`, `items`, `additionalProperties`, `required`).
  - Thinking: `types.ThinkingConfig(thinking_budget=0)` = AUS (2.5-Familie);
    `types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL)` (3er-Familie).
  - `types.FinishReason`: `STOP` = normal, `MAX_TOKENS` = abgeschnitten, alles andere
    (`SAFETY`, `PROHIBITED_CONTENT`, `RECITATION`, …) = kein normales Ende.
  - `errors.ClientError(code, response_json)` mit Attribut `.code` (429-Erkennung).
- **KEINE Echt-API-Calls in den Tasks.** `GEMINI_API_KEY` liegt NUR in der lokalen
  Shell des Maintainers, nicht in der Agent-Umgebung. Task 4 legt die Echt-Tests an
  (skippen ohne Key), führt sie nicht aus. Die Klang-Abnahme (Spec §4) läuft NACH dem
  Bau manuell durch den Maintainer.
- **Key-Hygiene:** fester Fehlertext `KEY_FEHLT` ohne jede Interpolation; weder Key noch
  Environment noch rohe SDK-Exceptions in Meldungen einbetten (Sentinel-Test beweist es).
- Sprache deutsch (Docstrings/Kommentare/Commits); Conventional Commits Scope `bc1`;
  Commit je RED→GREEN-Paar.

## File Structure

- `pyproject.toml` — Modify: `google-genai` in `[dependency-groups].service` (Task 1)
- `bc1_service/gemini_llm.py` — Create: kompletter Adapter (Task 2)
- `tests/test_gemini_llm.py` — Create: Stub-Tests (Task 2)
- `bc1_service/llm_wahl.py` — Modify: dritter Zweig `gemini`, lazy import (Task 3)
- `tests/test_llm_wahl.py` — Modify: Gemini-Zweig + Fehlermeldung (Task 3)
- `bc1_service/main.py` — Modify: nur Docstring (Task 3)
- `bc1_service/prompts.py` — Modify: nur 2 Docstring-Zeilen generalisieren (Task 3)
- `tests/test_gemini_echt.py` — Create: Echt-Stichprobe hinter Flag+Key (Task 4)
- `bc1_service/n8n/SMOKE.md` — Modify: Gemini-Startanleitung + Klang-Abnahme-Ablauf (Task 4)

## Reihenfolge

Task 1 → 2 → 3 → 4 strikt sequenziell (Dependency → Adapter → Verdrahtung → Abnahme-Doku).

---

### Task 1: Branch, Plan, Dependency

**Files:**
- Modify: `pyproject.toml` (service-Gruppe)
- Commit: `design/Implementierungsplan-Gemini-Adapter.md` (diese Datei, aktuell untracked)

**Interfaces:**
- Produces: importierbares Paket `google.genai` im `.venv`; Branch `bc1-gemini-adapter`.

- [ ] **Step 1: Branch anlegen + Plan committen**

```bash
cd coe-factory && git checkout -b bc1-gemini-adapter bc1-ollama-adapter
git add bc1-context-discovery/design/Implementierungsplan-Gemini-Adapter.md
git commit -m "docs(bc1): Implementierungsplan Gemini-Adapter"
```

- [ ] **Step 2: Dependency eintragen** — in `bc1-context-discovery/pyproject.toml` die
  service-Gruppe erweitern (google-genai ans Ende):

```toml
service = [
    "fastapi",
    "uvicorn[standard]",
    "psycopg[binary,pool]",
    "anthropic",
    "jsonschema",
    "google-genai",
]
```

- [ ] **Step 3: Installieren + Import beweisen**

Run (aus `bc1-context-discovery/`):
```bash
/opt/homebrew/bin/uv sync --group dev --group service
.venv/bin/python -c "import google.genai; print(google.genai.__version__)"
```
Expected: Versionsausgabe (≥ 2.17.0), kein ImportError.

- [ ] **Step 4: Suite unverändert grün**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q`
Expected: **220 passed, 2 skipped** (unverändert — reine Dependency-Erweiterung).

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/pyproject.toml bc1-context-discovery/uv.lock
git commit -m "build(bc1): google-genai als service-Dependency (Gemini-Adapter)"
```
(Hinweis: existiert kein `uv.lock` im Repo, nur `pyproject.toml` adden.)

---

### Task 2: `bc1_service/gemini_llm.py` — kompletter Adapter

**Files:**
- Create: `bc1_service/gemini_llm.py`
- Test: `tests/test_gemini_llm.py`

**Interfaces:**
- Consumes: `LLMClient`-Protocol (`extract`, `antworte`), geteilte Prompts aus
  `bc1_service.prompts`, `TurnKontext`, `ExtractionCandidate`.
- Produces: `GeminiLLM(client=None, modell: str | None = None)` mit
  `extract(message, package, state) -> list[ExtractionCandidate]` und
  `antworte(kontext: TurnKontext) -> str` · Konstante `KEY_FEHLT: str` ·
  `STANDARD_MODELL = "gemini-2.5-flash"`. Task 3 importiert `GeminiLLM` in `llm_wahl`.

- [ ] **Step 1: Write the failing tests** — `tests/test_gemini_llm.py` (WÖRTLICH; bei
  tdd-guard-Block wegen mehrerer Tests: guard-konform in Teilschritten mit je einem
  RED-Lauf anlegen, Skill `tdd-guard` konsultieren, nie umgehen):

```python
"""GeminiLLM: Konfiguration, Guards, Key-Hygiene — Stubs, kein Netz."""
import json

import pytest
from google.genai import errors, types

from bc1_core.core import process_turn
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.store import InMemoryStateStore
from bc1_service.gemini_llm import KEY_FEHLT, GeminiLLM
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_GESPRAECH,
)

PAKET = UseCasePackage(
    name="gemini_test", schema_version="0.1",
    fields=(FieldSpec("zweck", "Was ist der Zweck?"),))


class _Kandidat:
    def __init__(self, finish):
        self.finish_reason = finish


class _Antwort:
    def __init__(self, text, finish=types.FinishReason.STOP, kandidaten=True):
        self.text = text
        self.candidates = [_Kandidat(finish)] if kandidaten else []


class _Models:
    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.aufrufe = []

    def generate_content(self, **kwargs):
        self.aufrufe.append(kwargs)
        ergebnis = self._antworten.pop(0)
        if isinstance(ergebnis, Exception):
            raise ergebnis
        return ergebnis


class _StubClient:
    def __init__(self, antworten):
        self.models = _Models(antworten)


def _llm(antworten, modell=None):
    return GeminiLLM(client=_StubClient(antworten), modell=modell)


def test_extract_reicht_prompts_schema_und_konfig_durch():
    stub = _StubClient([_Antwort('{"extraktionen": [{"feld": "zweck", "wert": " X "}]}')])
    ergebnis = GeminiLLM(client=stub).extract("Nachricht", PAKET, None)
    aufruf = stub.models.aufrufe[0]
    konfig = aufruf["config"]
    assert aufruf["model"] == "gemini-2.5-flash"
    assert konfig.system_instruction == SYSTEM_EXTRAKTION
    assert konfig.response_mime_type == "application/json"
    assert konfig.response_json_schema is EXTRAKTIONS_SCHEMA
    assert konfig.temperature == 0
    assert konfig.max_output_tokens == 4096
    assert "Was ist der Zweck?" in aufruf["contents"]
    assert "Nachricht" in aufruf["contents"]
    assert [(k.field_name, k.value) for k in ergebnis] == [("zweck", "X")]


def test_extract_filtert_unbekannte_felder_und_leere_werte():
    stub = _StubClient([_Antwort(json.dumps({"extraktionen": [
        {"feld": "zweck", "wert": "A"},
        {"feld": "fremd", "wert": "B"},
        {"feld": "zweck", "wert": "   "},
    ]}))])
    ergebnis = GeminiLLM(client=stub).extract("m", PAKET, None)
    assert [(k.field_name, k.value) for k in ergebnis] == [("zweck", "A")]


def test_antworte_nutzt_gespraechs_prompts_und_strippt():
    from bc1_core.gespraech import TurnKontext
    stub = _StubClient([_Antwort("  Hallo! Wie oft läuft es?  ")])
    kontext = TurnKontext(nutzer_nachricht="m", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    text = GeminiLLM(client=stub).antworte(kontext)
    konfig = stub.models.aufrufe[0]["config"]
    assert konfig.system_instruction == SYSTEM_GESPRAECH
    assert konfig.response_mime_type is None
    assert text == "Hallo! Wie oft läuft es?"


def test_thinking_budget_null_fuer_25_familie():
    stub = _StubClient([_Antwort("ok")])
    _llm_mit_stub = GeminiLLM(client=stub, modell="gemini-2.5-flash")
    from bc1_core.gespraech import TurnKontext
    _llm_mit_stub.antworte(TurnKontext("m", (), "F?", False, False))
    tk = stub.models.aufrufe[0]["config"].thinking_config
    assert tk.thinking_budget == 0


def test_thinking_level_minimal_fuer_3er_familie():
    stub = _StubClient([_Antwort("ok")])
    from bc1_core.gespraech import TurnKontext
    GeminiLLM(client=stub, modell="gemini-3-flash").antworte(
        TurnKontext("m", (), "F?", False, False))
    tk = stub.models.aufrufe[0]["config"].thinking_config
    assert tk.thinking_level == types.ThinkingLevel.MINIMAL


def test_unbekannte_modellfamilie_wirft_klaren_fehler():
    with pytest.raises(RuntimeError, match="keine gepinnte Thinking-Konfiguration"):
        _llm([], modell="gemma-7b")


def test_ohne_key_und_ohne_client_wirft_festen_text(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as fehler:
        GeminiLLM()
    assert str(fehler.value) == KEY_FEHLT


def test_stub_client_braucht_keinen_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _llm([])  # kein Raise: Key-Prüfung nur ohne injizierten Client


def test_echter_client_pinnt_timeout_und_keine_retries(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SENTINEL-TESTKEY-123")
    erfasst = {}

    def fake_client(**kwargs):
        erfasst.update(kwargs)
        return _StubClient([])

    import bc1_service.gemini_llm as modul
    monkeypatch.setattr(modul.genai, "Client", fake_client)
    GeminiLLM()
    ho = erfasst["http_options"]
    # SDK-Doku: timeout in MILLISEKUNDEN; attempts inkl. Erstversuch.
    assert ho.timeout == 30_000
    assert ho.retry_options.attempts == 1


def test_429_neutrale_diagnose_genau_ein_aufruf_kein_sentinel(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SENTINEL-TESTKEY-123")
    stub = _StubClient([errors.ClientError(429, {"error": {"message": "quota"}})])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(RuntimeError) as fehler:
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))
    assert "Kontingent/Rate-Limit" in str(fehler.value)
    assert "SENTINEL-TESTKEY-123" not in str(fehler.value)
    assert len(stub.models.aufrufe) == 1


def test_andere_client_fehler_fliegen_unveraendert():
    stub = _StubClient([errors.ClientError(400, {})])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(errors.ClientError):
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))


def test_abgeschnitten_wirft():
    stub = _StubClient([_Antwort("halb", finish=types.FinishReason.MAX_TOKENS)])
    with pytest.raises(RuntimeError, match="abgeschnitten"):
        GeminiLLM(client=stub).extract("m", PAKET, None)


def test_safety_ende_wirft():
    stub = _StubClient([_Antwort("x", finish=types.FinishReason.SAFETY)])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(RuntimeError, match="nicht normal geendet"):
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))


def test_ohne_kandidaten_wirft():
    stub = _StubClient([_Antwort("x", kandidaten=False)])
    with pytest.raises(RuntimeError, match="ohne Kandidaten"):
        GeminiLLM(client=stub).extract("m", PAKET, None)


def test_nur_whitespace_wirft():
    stub = _StubClient([_Antwort("   ")])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(RuntimeError, match="ohne Inhalt"):
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))


def test_protokoll_konformitaet_ein_turn_durch_process_turn():
    stub = _StubClient([
        _Antwort('{"extraktionen": [{"feld": "zweck", "wert": "Automatisieren"}]}'),
        _Antwort("Notiert: Automatisieren. Fertig!"),
    ])
    antwort = process_turn(InMemoryStateStore(), GeminiLLM(client=stub),
                           PAKET, "s-gemini", "m1", "Wir wollen automatisieren")
    assert antwort["status"] == "fertig"
    assert "Automatisieren" in antwort["payload"]["abschluss_text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: Collection-Error `ModuleNotFoundError: No module named 'bc1_service.gemini_llm'`.
Zur Absicherung „Rest grün" vorher einen separaten Baseline-Lauf dokumentieren (Lektion
Gesprächsschicht-Task-1).

- [ ] **Step 3: Write minimal implementation** — `bc1_service/gemini_llm.py` (WÖRTLICH):

```python
"""Gemini-Adapter hinter dem LLMClient-Protocol des Kerns.

Dritter Adapter neben Claude und Ollama — gleiche Naht, geteilte Prompts.
Free-Tier-Realität (20 Requests/Tag je Modell): SDK-Retries explizit AUS
(SDK-Default wäre 5 Versuche!), kein eigener Retry; ein 429 wird zur
neutralen Kontingent-Diagnose („Rate-Limit" kann Minuten-, Tages- oder
Token-Limit sein) und fliegt durch — process_turn macht daraus den
fehler_fortsetzbar-Vertrag. response_json_schema erzwingt valides JSON
(deckt das volle EXTRAKTIONS_SCHEMA inkl. additionalProperties ab).
SDK-Semantik (verifiziert an google-genai 2.17.0): HttpOptions.timeout
ist in MILLISEKUNDEN; HttpRetryOptions.attempts zählt inkl. Erstversuch.
"""
from __future__ import annotations

import json
import os

from google import genai
from google.genai import errors, types

from bc1_core.gespraech import TurnKontext
from bc1_core.llm import ExtractionCandidate
from bc1_core.package import UseCasePackage
from bc1_core.types import SessionState
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_GESPRAECH,
    gespraech_nutzer_prompt,
)

STANDARD_MODELL = "gemini-2.5-flash"
# FESTER Text ohne Interpolation — weder Key noch Environment einbetten
# (Sentinel-Test pinnt das).
KEY_FEHLT = (
    "GEMINI_API_KEY ist nicht gesetzt. Ohne Key kann der Gemini-Adapter "
    "(BC1_LLM=gemini) nicht starten."
)
# Niedrigste Thinking-Stufe je Modellfamilie (Spec: Versprachlichen ist
# kein Knobeln): 2.5-Familie kennt budget 0 = AUS; die 3er-Familie steuert
# über Level, Minimum ist MINIMAL.
_THINKING = {
    "gemini-2.5-": types.ThinkingConfig(thinking_budget=0),
    "gemini-3-": types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
}


def _thinking_fuer(modell: str) -> types.ThinkingConfig:
    for praefix, konfig in _THINKING.items():
        if modell.startswith(praefix):
            return konfig
    # Kein stilles Weglassen (Spec): unbekannte Familie = ungeklärte Semantik.
    raise RuntimeError(
        f"BC1_GEMINI_MODELL '{modell}': keine gepinnte Thinking-Konfiguration "
        "für diese Modellfamilie (bekannt: gemini-2.5-*, gemini-3-*)."
    )


class GeminiLLM:
    def __init__(self, client=None, modell: str | None = None) -> None:
        if client is None and not os.environ.get("GEMINI_API_KEY"):
            # Fail-fast beim Dienststart statt fehler_fortsetzbar beim
            # ersten Turn; Key-Prüfung NUR ohne injizierten Client (Stubs).
            raise RuntimeError(KEY_FEHLT)
        self._client = client or genai.Client(
            http_options=types.HttpOptions(
                timeout=30_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            )
        )
        self._modell = modell or os.environ.get("BC1_GEMINI_MODELL", STANDARD_MODELL)
        self._thinking = _thinking_fuer(self._modell)

    def extract(
        self, message: str, package: UseCasePackage, state: SessionState
    ) -> list[ExtractionCandidate]:
        felder = "\n".join(f"- {f.name}: {f.question}" for f in package.fields)
        inhalt = self._generate(
            system=SYSTEM_EXTRAKTION,
            nutzer=(
                f"Felder des Prozessprofils:\n{felder}\n\n"
                f"Interview-Nachricht:\n{message}\n\n"
                "Gib alle Feld-Wert-Paare zurück, die diese Nachricht belegt."
            ),
            json_schema=EXTRAKTIONS_SCHEMA,
        )
        daten = json.loads(inhalt)
        bekannte = {f.name for f in package.fields}
        return [
            ExtractionCandidate(e["feld"], e["wert"].strip())
            for e in daten["extraktionen"]
            if e["feld"] in bekannte and e["wert"].strip()
        ]

    def antworte(self, kontext: TurnKontext) -> str:
        return self._generate(
            system=SYSTEM_GESPRAECH, nutzer=gespraech_nutzer_prompt(kontext)
        ).strip()

    def _generate(self, system: str, nutzer: str, json_schema=None) -> str:
        konfig = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            max_output_tokens=4096,
            thinking_config=self._thinking,
            response_mime_type=(
                "application/json" if json_schema is not None else None
            ),
            response_json_schema=json_schema,
        )
        try:
            antwort = self._client.models.generate_content(
                model=self._modell, contents=nutzer, config=konfig
            )
        except errors.ClientError as fehler:
            if fehler.code == 429:
                # Neutrale Diagnose für Logs/Abnahme-Protokoll; /turn zeigt
                # dem Nutzer weiterhin den generischen fehler_fortsetzbar-
                # Text (der Kern verwirft Exception-Texte bewusst).
                raise RuntimeError(
                    "Gemini-Kontingent/Rate-Limit erreicht (HTTP 429)"
                ) from fehler
            raise
        if not antwort.candidates:
            raise RuntimeError("LLM-Antwort ohne Kandidaten")
        grund = antwort.candidates[0].finish_reason
        if grund == types.FinishReason.MAX_TOKENS:
            # Abgeschnitten = unbrauchbar (halbes JSON, halbe Frage).
            raise RuntimeError("LLM-Antwort abgeschnitten (max_output_tokens)")
        if grund != types.FinishReason.STOP:
            # SAFETY/PROHIBITED_CONTENT/RECITATION/…: Ablehnung statt Inhalt.
            raise RuntimeError(f"LLM hat nicht normal geendet ({grund})")
        inhalt = antwort.text
        if not inhalt or not inhalt.strip():
            raise RuntimeError("LLM-Antwort ohne Inhalt")
        return inhalt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **236 passed, 2 skipped, 0 Warnings** (220 + 16 neue).

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_service/gemini_llm.py bc1-context-discovery/tests/test_gemini_llm.py
git commit -m "feat(bc1): GeminiLLM-Adapter — geteilte Prompts, Schema-Zwang, Guards, Key-Hygiene"
```

---

### Task 3: Umschalter + Betriebs-Doku

**Files:**
- Modify: `bc1_service/llm_wahl.py`
- Modify: `bc1_service/main.py` (NUR Docstring)
- Modify: `bc1_service/prompts.py` (NUR 2 Docstring-Zeilen)
- Test: `tests/test_llm_wahl.py` (Ergänzungen)

**Interfaces:**
- Consumes: `GeminiLLM` (Task 2).
- Produces: `waehle_llm({"BC1_LLM": "gemini", ...})` liefert `GeminiLLM`.

- [ ] **Step 1: Write the failing tests** — ergänzen in `tests/test_llm_wahl.py`
  (Import um `GeminiLLM` erweitern: `from bc1_service.gemini_llm import GeminiLLM`):

```python
def test_gemini_liefert_gemini_llm(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    llm = waehle_llm({"BC1_LLM": "gemini"})
    assert isinstance(llm, GeminiLLM)


def test_unbekannte_wahl_nennt_alle_drei_optionen():
    with pytest.raises(RuntimeError) as fehler:
        waehle_llm({"BC1_LLM": "quatsch"})
    for option in ("claude", "ollama", "gemini"):
        assert option in str(fehler.value)
```

(Hinweis: Existiert bereits ein Fehlermeldungs-Test, der nur zwei Optionen prüft, wird
er zu `test_unbekannte_wahl_nennt_alle_drei_optionen` MIGRIERT statt dupliziert —
Testinhalt darf nicht ersatzlos verschwinden, Doppelung aber auch nicht entstehen.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_llm_wahl.py -v`
Expected: FAIL (`ImportError` bzw. RuntimeError „unbekannt" ohne gemini-Nennung).
Danach voller Lauf (RED registrieren).

- [ ] **Step 3: Write minimal implementation**

`bc1_service/llm_wahl.py` — den `ollama`-Zweig um einen `gemini`-Zweig ergänzen und die
Fehlermeldung erweitern; Endzustand der Funktion:

```python
def waehle_llm(umgebung: Mapping[str, str]) -> LLMClient:
    wahl = umgebung.get("BC1_LLM", "claude")
    if wahl == "claude":
        return ClaudeLLM()
    if wahl == "ollama":
        # Import nur hier: der Claude-Produktionspfad braucht das
        # ollama-Paket (dev-Dependency) nie.
        from bc1_service.ollama_llm import OllamaLLM

        return OllamaLLM()
    if wahl == "gemini":
        # Import nur hier: gleiches Muster — der Claude-Pfad lädt die
        # google-genai-Lib nie.
        from bc1_service.gemini_llm import GeminiLLM

        return GeminiLLM()
    raise RuntimeError(
        f"BC1_LLM='{wahl}' ist unbekannt — erlaubt sind 'claude' (Default), "
        "'ollama' (lokaler Test-/Dev-Ersatz) oder 'gemini' (Gemini API, "
        "GEMINI_API_KEY nötig)."
    )
```

`bc1_service/main.py` — Docstring-Zeilen 3–6 ersetzen durch:

```python
Pflicht: BC1_DB_DSN. Optional: BC1_SNAPSHOT_PFAD (BC0-Baseline), BC1_CLAUDE_MODELL,
ANTHROPIC_API_KEY (liest das SDK selbst), BC1_LLM ("claude" | "ollama" | "gemini",
Default claude — ollama = lokaler Test-/Dev-Ersatz ohne API-Key; gemini = Gemini API,
braucht GEMINI_API_KEY), BC1_OLLAMA_MODELL, BC1_GEMINI_MODELL,
BC1_PAKET ("discovery" | "toy", Default discovery).
```

`bc1_service/prompts.py` — genau zwei Docstring-Änderungen:
Zeile 1: `"""Geteilte Prompt-Bausteine der LLM-Adapter (Claude, Ollama).` →
`"""Geteilte Prompt-Bausteine der LLM-Adapter (Claude, Ollama, Gemini).`
Zeile ~53: `"""Nutzer-Prompt der Gesprächsschicht — von beiden Adaptern geteilt."""` →
`"""Nutzer-Prompt der Gesprächsschicht — von allen Adaptern geteilt."""`

- [ ] **Step 4: Run tests to verify they pass**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **238 passed, 2 skipped, 0 Warnings** (± Migration laut Step-1-Hinweis;
reale Zahlen berichten).

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_service/llm_wahl.py bc1-context-discovery/bc1_service/main.py bc1-context-discovery/bc1_service/prompts.py bc1-context-discovery/tests/test_llm_wahl.py
git commit -m "feat(bc1): BC1_LLM=gemini — dritter Zweig, Betriebs-Doku generalisiert"
```

---

### Task 4: Echt-Stichprobe (hinter Flag) + SMOKE-Anleitung + Abnahme-Ablauf

**Files:**
- Create: `tests/test_gemini_echt.py`
- Modify: `bc1_service/n8n/SMOKE.md`

**Interfaces:**
- Consumes: `GeminiLLM` (Task 2), Umschalter (Task 3).
- Produces: gezielt startbare Echt-Stichprobe; dokumentierter Klang-Abnahme-Ablauf.
  **Dieser Task führt KEINE Echt-Calls aus** (Key nur in der Shell des Maintainers).

- [ ] **Step 1: Write the test file** — `tests/test_gemini_echt.py` (skippt ohne
  Flag+Key; zählt als neue Testdatei → RED-Registrierung wie üblich):

```python
"""Gemini-Echt-Stichprobe — NUR gezielt starten (Free Tier: 20 Requests/Tag!).

Aufruf (aus bc1-context-discovery/, verbraucht 2 echte Requests):
  BC1_ECHT_LLM=1 .venv/bin/pytest tests/test_gemini_echt.py -v
Modell-Vergleich: zusätzlich BC1_GEMINI_MODELL=gemini-3-flash setzen.
NIE über das globale Flag allein laufen lassen (das würde auch die
Claude-/Ollama-Echt-Tests scharf schalten).
"""
import os

import pytest

from bc1_core.gespraech import Erfassung, TurnKontext
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_service.gemini_llm import GeminiLLM

pytestmark = pytest.mark.skipif(
    not (os.environ.get("BC1_ECHT_LLM") and os.environ.get("GEMINI_API_KEY")),
    reason="Echt-Stichprobe: BC1_ECHT_LLM=1 und GEMINI_API_KEY nötig",
)

PAKET = UseCasePackage(
    name="echt_test", schema_version="0.1",
    fields=(FieldSpec("prozess_name", "Wie heißt der Prozess?"),))


def test_extract_echt_mit_vollem_schema():
    # Beweist live: response_json_schema akzeptiert unser volles Schema
    # (inkl. additionalProperties) UND die Thinking-Konfig des Modells.
    kandidaten = GeminiLLM().extract(
        "Der Prozess heißt Reisebuchung.", PAKET, None)
    assert any(k.field_name == "prozess_name" and "Reisebuchung" in k.value
               for k in kandidaten)


def test_antworte_echt_bestaetigt_und_fragt():
    text = GeminiLLM().antworte(TurnKontext(
        nutzer_nachricht="Der Prozess heißt Reisebuchung.",
        neu_erfasst=(Erfassung("Wie heißt der Prozess?", "Reisebuchung"),),
        naechste_frage="Wie oft läuft der Prozess (pro Woche, Monat oder Jahr)?",
        ist_nachfrage=False, ist_abschluss=False))
    assert "Reisebuchung" in text
    assert "Wie oft läuft der Prozess" in text
```

- [ ] **Step 2: RED + GREEN nachweisen (ohne Netz)**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_gemini_echt.py -v`
Expected: **2 skipped** (Flag/Key fehlen in der Agent-Umgebung — genau so gewollt).
Voller Lauf: **238 passed, 4 skipped, 0 Warnings** (2 bestehende + 2 neue Skips;
reale Zahlen berichten).

- [ ] **Step 3: SMOKE.md ergänzen** — neuer Abschnitt nach „Gesprächsschicht live":

```markdown
## Gemini-Adapter (Gesprächsschicht mit starkem Modell)

**Start (Key nur in der eigenen Shell, NIE committen):**

    export GEMINI_API_KEY="<eigener Key>"   # bzw. aus ~/.zshrc
    BC1_LLM=gemini BC1_DB_DSN=... .venv/bin/uvicorn bc1_service.main:app
    # Modellwahl: BC1_GEMINI_MODELL=gemini-3-flash (Default: gemini-2.5-flash)

**Free-Tier-Leitplanken (Stand 11.08.2026, Konto-abhängig — im AI Studio prüfen):**
je Modell 5 Requests/min · 20 Requests/Tag. Ein Turn = 2 Requests.
⚠️ Bis Tier 1 (Kreditkarte) kann Google Free-Tier-Eingaben fürs Training nutzen —
NUR Demo-Daten ohne echte Personennamen.

**Echt-Stichprobe (2 Requests):**

    BC1_ECHT_LLM=1 .venv/bin/pytest tests/test_gemini_echt.py -v

**Klang-Abnahme (Spec §4) — Call-Plan, Requests mitzählen (max. 16 + 4 Puffer/Tag/Modell):**
1. Toy-Interview komplett (BC1_PAKET=toy, 3 Turns = 6 Requests): Struktur, Fortschritt,
   Abschluss ohne Schlussfrage.
2. Discovery, Auftakt-Nachricht (1 Turn = 2 Requests) — Wortlaut exakt:
   „Wir möchten unser Consultant-Staffing beschleunigen, um Zeit zu sparen — es geht um
   den ganzen Prozess. Der Prozess heißt Consultant Placement, verantwortlich ist der
   Staffing Manager." → erwartete Folgefrage: B4 (Kernprozess) —
   **überlebt die KP-Optionsliste wörtlich?** (offener Abnahmepunkt aus der
   Gesprächsschicht).
3. Nachfrage mit Beispiel (2 Requests) · Rückfrage „Was meinen Sie mit …?" (2 Requests) ·
   Abschluss-Zusammenfassung auf unbelegte Aussagen prüfen (2 Requests).
4. Zweites Modell: identischer Ablauf mit BC1_GEMINI_MODELL=gemini-3-flash.
Roh-JSON (Dienst-Request/-Response, kein SDK-Trace) hier protokollieren; das
Erstfragen-Ergebnis aktualisiert den offenen Abnahmepunkt oben.
```

- [ ] **Step 4: Voller Lauf + Commit**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q`
Expected: 238 passed, 4 skipped, 0 Warnings.

```bash
git add bc1-context-discovery/tests/test_gemini_echt.py bc1-context-discovery/bc1_service/n8n/SMOKE.md
git commit -m "test(bc1): Gemini-Echt-Stichprobe hinter Flag + SMOKE-Anleitung & Klang-Abnahme-Ablauf"
```

---

## Nach den Tasks (Controller/Maintainer, NICHT Subagent)

1. Gesamt-Review + Codex-Zweitmeinung (wie gehabt), Fix-Wellen, Re-Verify.
2. **Klang-Abnahme-Durchführung durch den Maintainer** (Key liegt nur in dessen Shell;
   Alternative: Export zusätzlich in `~/.zprofile`, dann sehen ihn auch Agent-Shells):
   Ablauf exakt nach SMOKE-Abschnitt, Protokoll + Klang-Urteil, Erstfragen-Ergebnis in
   den offenen Abnahmepunkt eintragen.
3. Push/PR nur mit explizitem Maintainer-OK.
