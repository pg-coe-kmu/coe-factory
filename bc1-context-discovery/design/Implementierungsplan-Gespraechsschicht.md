# BC1 Gesprächsschicht — Implementierungsplan

**Goal:** Der Interviewer antwortet pro Turn mit EINER natürlichen Gesprächsantwort — Bestätigung nur echter erfasster Werte, Reaktion/Erklärung, dann die Katalogfrage (Erstfragen wörtlich verankert) — plus deterministischer Fortschrittszeile; beim Abschluss eine Ergebnis-Zusammenfassung.

**Architecture:** Entscheidung und Versprachlichung werden getrennt: `dialog.decide_next` entscheidet nur noch (Zielfeld / fertig) und ruft kein LLM mehr; `process_turn` — der einzige Ort mit Nachricht, Vorher/Nachher-State und Entscheidung — baut einen frozen `TurnKontext` (neues Modul `bc1_core/gespraech.py`) und ruft die neue Protocol-Methode `antworte(kontext)`, die `phrase(field, state)` ersetzt (bewusster Breaking Change, Migration in diesem Plan). Felder werden gegenüber dem LLM ausschließlich über ihre Kernfrage identifiziert — technische Feldnamen verlassen den Kern nicht. Der Transport hängt die Fortschrittszeile aus neuen additiven Payload-Feldern an; kein LLM im Transport.

**Tech Stack:** Python 3.11+ Stdlib (Kern) · bestehende Nähte: `process_turn`/`decide_next` (core/dialog), `LLMClient`-Protocol (llm.py), geteilte Prompts (`bc1_service/prompts.py`), Adapter Claude/Ollama, `create_app`/`_chat_text` (api.py) · pytest + FakeLLM (kein Netz).

**Bindende Design-Spec:** `2026-08-08-bc1-gespraechsschicht-design.md` (lokal); die bindenden Verhaltensregeln stehen vollständig in den Global Constraints unten.

## Global Constraints

- **Branch:** `bc1-gespraechsschicht`, abgezweigt von `bc1-ollama-adapter` (Stand d43dfac, nach Merge PR #154). Task 1 committet diesen Plan.
- **TDD.** Pro Task: erst der rote Test, dann Implementierung. pytest IMMER aus `bc1-context-discovery/` und IMMER mit Test-DB: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest` (Container `bc1-test-pg` auf Port 55432; falls er nicht läuft: `docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16`).
- **Verhaltensregeln (BC2-/Nutzer-relevant, wörtlich aus der Spec):**
  1. Antwortstruktur: kurze **Bestätigung nur echter, in diesem Turn erfasster Werte** → ggf. Reaktion/Erklärung → genau eine Frage.
  2. **Erstfragen übernehmen die Kernfrage wörtlich**; Nachfragen dürfen umformulieren, müssen in der Frage enthaltene Optionen vollständig nennen und erklären, dass Offenes offen bleiben darf.
  3. **Keine technischen Feldnamen** Richtung LLM/Nutzer — Felder werden nur über ihre Kernfrage identifiziert (Leak-Schutz per Konstruktion im `TurnKontext`).
  4. Abschluss: Prosa-Zusammenfassung nur echter Werte + ehrliche Nennung offener Pflichtfelder.
  5. Fortschrittszeile deterministisch im Transport (`✓ X von Y Pflichtfeldern erfasst`), Zahlen aus den neuen Payload-Feldern `pflicht_erfasst`/`pflicht_gesamt`.
  6. **Interview-Mechanik unverändert** (Nachfrage-Zählung, ungelöst nach 2 Versuchen, Merge-/Klärungsregeln, Idempotenz, Fehlerpfad); **kein stiller Fallback** bei `antworte`-Fehlern (→ `fehler_fortsetzbar` wie heute).
- **Kern-Änderungen exakt diese und keine weiteren:** `gespraech.py` (neu) · `llm.py` (Protocol + FakeLLM) · `dialog.py` (`decide_next` ohne LLM) · `core.py` (`process_turn`-Versprachlichung, additive Payload-Felder). Service: `prompts.py`, `claude_llm.py`, `ollama_llm.py`, `api.py`. KEINE neuen Dependencies.
- **Suite-Basis: 205 passed, 2 skipped, 0 Warnings.** Die „Expected"-Zahlen pro Task sind Momentaufnahmen — exakte Zahlen laufen lassen und berichten, Abweichungen explizit.
- Sprache deutsch (Docstrings/Kommentare/Commits); Conventional Commits Scope `bc1`; Commit je RED→GREEN-Paar.

## File Structure

- `bc1_core/gespraech.py` — Create: `Erfassung`, `TurnKontext` (frozen), `werte_schnappschuss()`, `baue_turn_kontext()` — reine Funktionen, isoliert testbar
- `bc1_core/llm.py` — Modify: Protocol-Methode `antworte(kontext)` (Task 2 additiv, Task 5 entfernt `phrase`), `FakeLLM.antworte` deterministisch
- `bc1_core/dialog.py` — Modify: `Decision` ohne `question`, `decide_next` ohne `llm`-Parameter
- `bc1_core/core.py` — Modify: Schnappschuss → Kontext → `antworte`-Aufruf im try-Block; Payload additiv (`abschluss_text`, `pflicht_erfasst`, `pflicht_gesamt`)
- `bc1_service/prompts.py` — Modify: `SYSTEM_GESPRAECH` + `gespraech_nutzer_prompt(kontext)` (Task 4); `SYSTEM_FRAGE` + `frage_nutzer_prompt` entfallen (Task 5)
- `bc1_service/claude_llm.py`, `bc1_service/ollama_llm.py` — Modify: `antworte` (Task 4); `phrase` entfällt (Task 5)
- `bc1_service/api.py` — Modify: `_chat_text` mit Fortschrittszeile (Task 6)
- `bc1_service/n8n/SMOKE.md` — Modify: Abschnitt „Gesprächsschicht live" (Task 6)
- Tests: `tests/test_gespraech.py` (neu) · gezielte Ergänzungen/Migrationen in `test_llm.py`, `test_dialog.py`, `test_core.py`, `test_prompts.py`, `test_claude_llm.py`, `test_ollama_llm.py`, `test_api.py`

## Reihenfolge

Task 1 → 2 → 3 sequenziell (Kontext-Typen → Fake/Protocol → Kern-Umbau). Task 4 (Prompts+Adapter) braucht 1–2. Task 5 (phrase-Rückbau) braucht 3+4 (erst wenn kein Konsument mehr existiert). Task 6 (Transport+SMOKE) braucht 3.

---

### Task 1: `bc1_core/gespraech.py` — Kontext-Typen + Builder

**Files:**
- Create: `bc1_core/gespraech.py`
- Test: `tests/test_gespraech.py`

**Interfaces:**
- Consumes: `FieldStatus`, `SessionState` (types), `UseCasePackage` (package), `ConfidenceResult` (confidence) — alles Bestand.
- Produces: `Erfassung(frage: str, wert: str)` · `TurnKontext(nutzer_nachricht, neu_erfasst: tuple[Erfassung, ...], naechste_frage: str | None, ist_nachfrage: bool, ist_abschluss: bool, profil_uebersicht: tuple[Erfassung, ...] = (), offene_fragen: tuple[str, ...] = ())` · `werte_schnappschuss(state) -> dict[str, str]` · `baue_turn_kontext(nachricht, vorher, state, package, conf, ziel_feld, ist_abschluss) -> TurnKontext`. Task 2 hängt das Protocol daran, Task 3 ruft Schnappschuss + Builder in `process_turn`.

- [ ] **Step 1: Branch anlegen + Plan committen**

```bash
cd coe-factory && git checkout -b bc1-gespraechsschicht bc1-ollama-adapter
git add bc1-context-discovery/design/Implementierungsplan-Gespraechsschicht.md
git commit -m "docs(bc1): Implementierungsplan Gesprächsschicht"
```

- [ ] **Step 2: Write the failing tests** — `tests/test_gespraech.py`

```python
"""TurnKontext: der Kern befüllt, das LLM gibt nur wieder (Spec Gesprächsschicht).

Felder werden NUR über ihre Kernfrage identifiziert — technische Feldnamen
dürfen den Kontext nie erreichen (Leak-Schutz per Konstruktion).
"""
from bc1_core.confidence import confidence_check
from bc1_core.gespraech import (
    Erfassung,
    TurnKontext,
    baue_turn_kontext,
    werte_schnappschuss,
)
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import Candidate, FieldStatus, FieldValue, SessionState

PAKET = UseCasePackage(
    name="kontext_test", schema_version="0.1",
    fields=(FieldSpec("zweck", "Was ist der Zweck?"),
            FieldSpec("menge", "Wie viele pro Jahr?"),
            FieldSpec("notiz", "Noch etwas?", required=False)))


def _state(**werte: FieldValue) -> SessionState:
    state = SessionState("s1", "0.1")
    state.values.update(werte)
    return state


def test_neu_erfasst_enthaelt_nur_in_diesem_turn_gueltig_gewordenes():
    state = _state(
        zweck=FieldValue(value="Automatisieren", status=FieldStatus.GUELTIG),
        menge=FieldValue(value="600", status=FieldStatus.UNKLAR,
                         candidates=[Candidate("1200", "m1")]))
    kontext = baue_turn_kontext("msg", {}, state, PAKET,
                                confidence_check(state, PAKET), "menge", False)
    assert kontext.neu_erfasst == (Erfassung("Was ist der Zweck?", "Automatisieren"),)


def test_neu_erfasst_erkennt_wertaenderung_und_ignoriert_unveraendertes():
    state = _state(
        zweck=FieldValue(value="Neu", status=FieldStatus.GUELTIG),
        menge=FieldValue(value="600", status=FieldStatus.GUELTIG))
    vorher = {"zweck": "Alt", "menge": "600"}
    kontext = baue_turn_kontext("msg", vorher, state, PAKET,
                                confidence_check(state, PAKET), "notiz", False)
    assert kontext.neu_erfasst == (Erfassung("Was ist der Zweck?", "Neu"),)


def test_werte_schnappschuss_nur_gueltige():
    state = _state(
        zweck=FieldValue(value="X", status=FieldStatus.GUELTIG),
        menge=FieldValue(value="kaputt", status=FieldStatus.UNGUELTIG))
    assert werte_schnappschuss(state) == {"zweck": "X"}


def test_nachfrage_flag_ab_zweitem_versuch():
    state = _state(menge=FieldValue(attempts=2))
    kontext = baue_turn_kontext("msg", {}, state, PAKET,
                                confidence_check(state, PAKET), "menge", False)
    assert kontext.ist_nachfrage is True
    assert kontext.naechste_frage == "Wie viele pro Jahr?"

    frisch = _state(menge=FieldValue(attempts=1))
    kontext2 = baue_turn_kontext("msg", {}, frisch, PAKET,
                                 confidence_check(frisch, PAKET), "menge", False)
    assert kontext2.ist_nachfrage is False


def test_abschluss_traegt_uebersicht_und_offene_fragen():
    state = _state(
        zweck=FieldValue(value="Automatisieren", status=FieldStatus.GUELTIG),
        menge=FieldValue(value=None, status=FieldStatus.UNGELOEST))
    conf = confidence_check(state, PAKET)
    kontext = baue_turn_kontext("msg", {}, state, PAKET, conf, None, True)
    assert kontext.ist_abschluss is True
    assert kontext.naechste_frage is None
    assert kontext.profil_uebersicht == (
        Erfassung("Was ist der Zweck?", "Automatisieren"),)
    assert kontext.offene_fragen == ("Wie viele pro Jahr?",)


def test_kontext_transportiert_keine_technischen_feldnamen():
    state = _state(zweck=FieldValue(value="X", status=FieldStatus.GUELTIG))
    kontext = baue_turn_kontext("msg", {}, state, PAKET,
                                confidence_check(state, PAKET), "menge", False)
    # Leak-Schutz per Konstruktion: nirgendwo im Kontext taucht ein
    # technischer Feldname auf — nur Kernfragen und Werte.
    assert "zweck" not in repr(kontext)
    assert "menge" not in repr(kontext)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest` (aus `bc1-context-discovery/`)
Expected: FAIL mit `ModuleNotFoundError: No module named 'bc1_core.gespraech'`; Rest der Suite grün.

- [ ] **Step 4: Write minimal implementation** — `bc1_core/gespraech.py`

```python
"""Gesprächskontext für die Versprachlichung eines Turns (Spec Gesprächsschicht).

Der Kern befüllt, das LLM gibt nur wieder: alle Inhalte stammen aus dem
echten State. Felder werden gegenüber dem LLM ausschließlich über ihre
Kernfrage identifiziert — technische Feldnamen verlassen den Kern nicht
(Leak-Schutz per Konstruktion).
"""
from __future__ import annotations

from dataclasses import dataclass

from bc1_core.confidence import ConfidenceResult
from bc1_core.package import UseCasePackage
from bc1_core.types import FieldStatus, SessionState


@dataclass(frozen=True)
class Erfassung:
    frage: str   # Kernfrage des Feldes — NICHT der technische Name
    wert: str    # normalisierter Wert aus dem State


@dataclass(frozen=True)
class TurnKontext:
    nutzer_nachricht: str
    neu_erfasst: tuple[Erfassung, ...]
    naechste_frage: str | None          # wörtliche Kernfrage; None beim Abschluss
    ist_nachfrage: bool
    ist_abschluss: bool
    profil_uebersicht: tuple[Erfassung, ...] = ()
    offene_fragen: tuple[str, ...] = ()


def werte_schnappschuss(state: SessionState) -> dict[str, str]:
    """GUELTIGE Werte VOR der Extraktion — Basis der Delta-Berechnung."""
    return {name: fv.value for name, fv in state.values.items()
            if fv.status is FieldStatus.GUELTIG}


def _gueltige(state: SessionState, package: UseCasePackage):
    for spec in package.fields:
        fv = state.values.get(spec.name)
        if fv is not None and fv.status is FieldStatus.GUELTIG:
            yield spec, fv


def baue_turn_kontext(nachricht: str, vorher: dict[str, str],
                      state: SessionState, package: UseCasePackage,
                      conf: ConfidenceResult, ziel_feld: str | None,
                      ist_abschluss: bool) -> TurnKontext:
    """Kontext aus echtem State — in Paket-Reihenfolge, deterministisch."""
    neu = tuple(Erfassung(spec.question, fv.value)
                for spec, fv in _gueltige(state, package)
                if vorher.get(spec.name) != fv.value)

    if ist_abschluss:
        uebersicht = tuple(Erfassung(spec.question, fv.value)
                           for spec, fv in _gueltige(state, package))
        offene = tuple(spec.question for spec in package.required_fields()
                       if conf.statuses[spec.name] is not FieldStatus.GUELTIG)
        return TurnKontext(nachricht, neu, None, ist_nachfrage=False,
                           ist_abschluss=True, profil_uebersicht=uebersicht,
                           offene_fragen=offene)

    ziel = state.values.get(ziel_feld)
    return TurnKontext(nachricht, neu, package.field(ziel_feld).question,
                       ist_nachfrage=ziel is not None and ziel.attempts > 1,
                       ist_abschluss=False)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **211 passed, 2 skipped** (205 + 6 neue)

- [ ] **Step 6: Commit**

```bash
git add bc1-context-discovery/bc1_core/gespraech.py bc1-context-discovery/tests/test_gespraech.py
git commit -m "feat(bc1): TurnKontext + Builder — Gesprächskontext aus echtem State, Felder nur über Kernfragen"
```

---

### Task 2: Protocol-Methode `antworte` + deterministisches `FakeLLM.antworte`

**Files:**
- Modify: `bc1_core/llm.py`
- Test: `tests/test_llm.py` (Ergänzungen)

**Interfaces:**
- Consumes: `TurnKontext`, `Erfassung` aus Task 1.
- Produces: `LLMClient.antworte(kontext: TurnKontext) -> str` (Protocol, ADDITIV — `phrase` bleibt bis Task 5 bestehen, damit jeder Task grün endet) · `FakeLLM.antworte` mit dem Test-Vertrag: enthält alle `neu_erfasst`-Werte wörtlich und die `naechste_frage` wörtlich; beim Abschluss die `profil_uebersicht`-Werte und `offene_fragen`. Task 3 ruft genau das aus `process_turn`.

- [ ] **Step 1: Write the failing tests** — ergänzen in `tests/test_llm.py` (Import-Block der Datei um `from bc1_core.gespraech import Erfassung, TurnKontext` erweitern)

```python
def test_fake_antworte_enthaelt_werte_und_kernfrage_woertlich():
    kontext = TurnKontext(
        nutzer_nachricht="msg",
        neu_erfasst=(Erfassung("Wie oft?", "600"), Erfassung("Zweck?", "Sparen")),
        naechste_frage="Wie lange dauert es?",
        ist_nachfrage=False, ist_abschluss=False)
    text = FakeLLM().antworte(kontext)
    assert "600" in text and "Sparen" in text
    assert "Wie lange dauert es?" in text


def test_fake_antworte_abschluss_mit_uebersicht_und_offenem():
    kontext = TurnKontext(
        nutzer_nachricht="msg", neu_erfasst=(),
        naechste_frage=None, ist_nachfrage=False, ist_abschluss=True,
        profil_uebersicht=(Erfassung("Wie oft?", "600"),),
        offene_fragen=("Wer ist verantwortlich?",))
    text = FakeLLM().antworte(kontext)
    assert "600" in text
    assert "Wer ist verantwortlich?" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_llm.py -v`
Expected: FAIL mit `AttributeError: 'FakeLLM' object has no attribute 'antworte'`. Danach voller Lauf.

- [ ] **Step 3: Write minimal implementation** — in `bc1_core/llm.py`

Import ergänzen und beide Klassen erweitern (bestehende Methoden unverändert lassen):

```python
from bc1_core.gespraech import TurnKontext
```

Im `LLMClient`-Protocol nach `phrase`:

```python
    def antworte(self, kontext: TurnKontext) -> str: ...
```

In `FakeLLM` nach `phrase`:

```python
    def antworte(self, kontext: TurnKontext) -> str:
        # Deterministische Komposition — Test-Vertrag: alle neu_erfasst-Werte
        # und die Kernfrage (bzw. Übersicht/Offenes) erscheinen WÖRTLICH.
        teile = []
        if kontext.neu_erfasst:
            teile.append("Notiert: "
                         + "; ".join(e.wert for e in kontext.neu_erfasst) + ".")
        if kontext.ist_abschluss:
            teile.append("Zusammenfassung: "
                         + "; ".join(e.wert for e in kontext.profil_uebersicht)
                         + ".")
            if kontext.offene_fragen:
                teile.append("Offen: " + " | ".join(kontext.offene_fragen))
        else:
            teile.append(kontext.naechste_frage)
        return " ".join(teile)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **213 passed, 2 skipped** (211 + 2 neue)

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_core/llm.py bc1-context-discovery/tests/test_llm.py
git commit -m "feat(bc1): LLMClient.antworte + deterministisches FakeLLM.antworte (additiv, phrase folgt in Task 5)"
```

---

### Task 3: Kern-Umbau — `decide_next` entscheidet nur, `process_turn` versprachlicht

**Files:**
- Modify: `bc1_core/dialog.py`, `bc1_core/core.py`
- Test: `tests/test_core.py` (Ergänzungen + gezielte Migration), `tests/test_dialog.py` (Migration)

**Interfaces:**
- Consumes: `werte_schnappschuss`/`baue_turn_kontext` (Task 1), `llm.antworte` (Task 2).
- Produces: `Decision(done, next_field)` OHNE `question`; `decide_next(state, package, conf)` OHNE `llm`-Parameter; `process_turn`-Payload additiv: Frage-Fall `{"naechste_frage": <Gesprächstext>, "feld": ..., "pflicht_erfasst": int, "pflicht_gesamt": int}`, Fertig-Fall `_profil(...)` plus `"abschluss_text"`, `"pflicht_erfasst"`, `"pflicht_gesamt"`. Task 6 liest die Zähler im Transport.

- [ ] **Step 1: Write the failing tests** — ergänzen in `tests/test_core.py` (Import-Block um `from bc1_core.llm import FakeLLM, ExtractionCandidate` erweitern, soweit nicht vorhanden; Muster der Datei übernehmen — TOY_PROZESS-Felder: `prozess_name`/`ausloeser`/`haeufigkeit`)

```python
def test_frage_traegt_gespraechstext_mit_bestaetigung_und_kernfrage():
    store = InMemoryStateStore()
    llm = FakeLLM({"Der Prozess heißt Urlaubsantrag":
                   [ExtractionCandidate("prozess_name", "Urlaubsantrag")]})
    resp = process_turn(store, llm, TOY_PROZESS, "s-gespraech", "m1",
                        "Der Prozess heißt Urlaubsantrag")
    p = resp["payload"]
    # Fake-Komposition: Bestätigung der echten Werte + nächste Kernfrage wörtlich.
    assert "Urlaubsantrag" in p["naechste_frage"]
    assert TOY_PROZESS.field(p["feld"]).question in p["naechste_frage"]
    assert p["pflicht_erfasst"] == 1
    assert p["pflicht_gesamt"] == len(TOY_PROZESS.required_fields())


def test_abschluss_traegt_zusammenfassung_und_zaehler():
    store = InMemoryStateStore()
    llm = FakeLLM({
        "A": [ExtractionCandidate("prozess_name", "Urlaubsantrag")],
        "B": [ExtractionCandidate("ausloeser", "Antrag")],
        "C": [ExtractionCandidate("haeufigkeit", "100 mal pro Jahr")]})
    process_turn(store, llm, TOY_PROZESS, "s-abschluss", "m1", "A")
    process_turn(store, llm, TOY_PROZESS, "s-abschluss", "m2", "B")
    resp = process_turn(store, llm, TOY_PROZESS, "s-abschluss", "m3", "C")
    assert resp["status"] == "fertig"
    p = resp["payload"]
    assert "Urlaubsantrag" in p["abschluss_text"]
    assert p["pflicht_erfasst"] == p["pflicht_gesamt"]


def test_gespraechstext_kommt_aus_llm_antworte_nicht_aus_dem_paket():
    # Invariante „LLM nur hinter dem LLM-Client" — ersetzt den bisherigen
    # phrase-Beweis aus test_dialog.py auf der neuen Naht.
    class EigeneWorte(FakeLLM):
        def antworte(self, kontext):
            return "GANZ EIGENE FORMULIERUNG"

    store = InMemoryStateStore()
    resp = process_turn(store, EigeneWorte(), TOY_PROZESS, "s-inv", "m1", "Hallo")
    assert resp["payload"]["naechste_frage"] == "GANZ EIGENE FORMULIERUNG"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_core.py -v`
Expected: FAIL — `KeyError: 'pflicht_erfasst'` bzw. Bestätigungs-Assertions (naechste_frage ist heute die nackte phrase-Frage). Danach voller Lauf.

- [ ] **Step 3: Write minimal implementation**

`bc1_core/dialog.py` — `Decision` und Signatur ändern, LLM-Bezug entfernen:

```python
@dataclass
class Decision:
    done: bool
    next_field: str | None = None
```

Signatur: `def decide_next(state: SessionState, package: UseCasePackage, conf: ConfidenceResult) -> Decision:` — der Import `from bc1_core.llm import LLMClient` entfällt. Die letzte Zeile wird zu:

```python
    return Decision(done=False, next_field=target)
```

(Alles andere in `decide_next` — Cap-Politik, Runden-Limit, attempts-Zählung — bleibt wörtlich unverändert.)

`bc1_core/core.py` — Imports ergänzen:

```python
from bc1_core.types import FieldStatus, FieldValue, SessionState, SessionStatus
from bc1_core.gespraech import baue_turn_kontext, werte_schnappschuss
```

Den Block ab `state.rounds += 1` bis zum Ende von `process_turn` ersetzen durch:

```python
    state.rounds += 1
    try:
        vorher = werte_schnappschuss(state)
        extract_and_merge(state, message, message_id, package, llm)
        conf = confidence_check(state, package)
        decision = decide_next(state, package, conf)
        if decision.done:
            # decide_next kann Felder frisch gecappt haben — für Payload und
            # Abschluss-Kontext zählt der Stand NACH der Entscheidung.
            conf = confidence_check(state, package)
        kontext = baue_turn_kontext(message, vorher, state, package, conf,
                                    decision.next_field, decision.done)
        antwortetext = llm.antworte(kontext)
    except Exception:
        # LLM-Aussetzer (Spec B4): fortsetzbar melden. NUR der FEHLER-Marker
        # wird persistiert — auf dem letzten dauerhaften Stand, nicht auf dem
        # halb verarbeiteten Turn (sonst verbrauchte der Ausfall unsichtbar
        # rounds/attempts). Die Nachricht bleibt geloggt und UNBEANTWORTET —
        # der Retry setzt fort. Retries/Backoff → echter LLM-Client (Roadmap).
        state = store.load(session_id)
        state.status = SessionStatus.FEHLER
        store.save(state)
        return {"status": "fehler_fortsetzbar",
                "payload": {"grund": "verarbeitung_fehlgeschlagen"}}

    pflicht = package.required_fields()
    erfasst = sum(1 for s in pflicht
                  if conf.statuses[s.name] is FieldStatus.GUELTIG)
    if decision.done:
        state.status = SessionStatus.FERTIG
        payload = _profil(state, conf, package)
        payload["abschluss_text"] = antwortetext
        payload["pflicht_erfasst"] = erfasst
        payload["pflicht_gesamt"] = len(pflicht)
        resp = {"status": "fertig", "payload": payload}
    else:
        state.status = SessionStatus.WARTET
        resp = {"status": "frage",
                "payload": {"naechste_frage": antwortetext,
                            "feld": decision.next_field,
                            "pflicht_erfasst": erfasst,
                            "pflicht_gesamt": len(pflicht)}}

    state.antworten[message_id] = resp
    store.save(state)
    return resp
```

- [ ] **Step 4: Migrate existing tests (gezielt, mechanisch)**

1. `tests/test_dialog.py`: alle `decide_next(...)`-Aufrufe verlieren das LLM-Argument (`decide_next(state, paket, conf, FakeLLM())` → `decide_next(state, paket, conf)`); Assertions auf `d.question` entfallen ersatzlos (die Frage-Formulierung ist jetzt Sache von `process_turn`/`antworte` — Kern-Beweis dafür ist der neue Invarianten-Test in `test_core.py`). Der Test `test_frage_kommt_aus_llm_phrase_nicht_aus_dem_paket` (samt lokaler Testklasse) wird ERSATZLOS gelöscht — sein Nachfolger ist `test_gespraechstext_kommt_aus_llm_antworte_nicht_aus_dem_paket` aus Step 1.
2. `tests/test_core.py`: die lokale Testklasse mit eigener `phrase`-Methode (um Zeile 371) implementiert stattdessen `antworte(self, kontext)` mit gleichem Rückgabe-String; Assertions, die `naechste_frage == <Kernfrage>` exakt vergleichen, werden zu `in`-Prüfungen (`<Kernfrage> in naechste_frage`), weil die Fake-Komposition Bestätigungen voranstellt.
3. `tests/test_api.py`: `a1.json()["chat_text"] == a1.json()["payload"]["naechste_frage"]` bleibt in diesem Task GÜLTIG (Transport unverändert bis Task 6) — nur exakte `naechste_frage == <Frage>`-Vergleiche (falls vorhanden) werden zu `in`-Prüfungen.
4. `tests/test_demo_durchlaeufe.py`: KEINE Änderung erwartet (Demos asserten Payload-Felder/Status, nicht den Fragetext) — Lauf beweist es.

- [ ] **Step 5: Run tests to verify they pass (VOLLER Lauf — beweist die Migration)**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **~216 passed, 2 skipped** (213 + 3 neue, ±Migrationssaldo — exakt berichten)

- [ ] **Step 6: Commit**

```bash
git add bc1-context-discovery/bc1_core/dialog.py bc1-context-discovery/bc1_core/core.py bc1-context-discovery/tests/test_core.py bc1-context-discovery/tests/test_dialog.py bc1-context-discovery/tests/test_api.py
git commit -m "feat(bc1): Entscheidung und Versprachlichung getrennt — process_turn ruft antworte, Payload additiv (abschluss_text, Zähler)"
```

---

### Task 4: Geteilte Gesprächs-Prompts + Adapter `antworte` (Claude, Ollama)

**Files:**
- Modify: `bc1_service/prompts.py`, `bc1_service/claude_llm.py`, `bc1_service/ollama_llm.py`
- Test: `tests/test_prompts.py`, `tests/test_claude_llm.py`, `tests/test_ollama_llm.py` (Ergänzungen)

**Interfaces:**
- Consumes: `TurnKontext` (Task 1), Protocol-Vertrag `antworte` (Task 2), bestehende Guards `_text_inhalt` (Claude) / `_chat` (Ollama).
- Produces: `SYSTEM_GESPRAECH: str` + `gespraech_nutzer_prompt(kontext: TurnKontext) -> str` in `prompts.py`; `ClaudeLLM.antworte` / `OllamaLLM.antworte`. Task 5 entfernt danach `phrase`/`SYSTEM_FRAGE`/`frage_nutzer_prompt`.

- [ ] **Step 1: Write the failing tests** — ergänzen in `tests/test_prompts.py` (Import um `SYSTEM_GESPRAECH, gespraech_nutzer_prompt` und `from bc1_core.gespraech import Erfassung, TurnKontext` erweitern)

```python
def _kontext(**kwargs) -> TurnKontext:
    basis = dict(nutzer_nachricht="msg", neu_erfasst=(),
                 naechste_frage="Wie oft läuft der Prozess?",
                 ist_nachfrage=False, ist_abschluss=False)
    basis.update(kwargs)
    return TurnKontext(**basis)


def test_system_gespraech_pinnt_die_kernregeln():
    assert "NUR die gelieferten Werte" in SYSTEM_GESPRAECH
    assert "NIE technische Feldnamen" in SYSTEM_GESPRAECH
    # Entscheidung 6 (10.08.): Beispiele nur bei Rück-/Nachfragen,
    # Erstfragen bleiben beispielfrei (Anker-Effekt).
    assert "in Erstfragen nie ein Beispiel" in SYSTEM_GESPRAECH


def test_erstfrage_wird_woertlich_verlangt():
    prompt = gespraech_nutzer_prompt(_kontext(
        neu_erfasst=(Erfassung("Zweck?", "Sparen"),)))
    assert "wörtlich" in prompt
    assert "Wie oft läuft der Prozess?" in prompt
    assert "Zweck? → Sparen" in prompt


def test_nachfrage_verlangt_optionen_und_zweck():
    prompt = gespraech_nutzer_prompt(_kontext(ist_nachfrage=True))
    assert "NACHFRAGE" in prompt
    assert "Optionen vollständig" in prompt
    assert "offen bleiben darf" in prompt
    assert "neutralen Beispiel" in prompt


def test_abschluss_prompt_traegt_uebersicht_und_offenes():
    prompt = gespraech_nutzer_prompt(_kontext(
        naechste_frage=None, ist_abschluss=True,
        profil_uebersicht=(Erfassung("Wie oft?", "600"),),
        offene_fragen=("Wer ist verantwortlich?",)))
    assert "Wie oft? → 600" in prompt
    assert "Wer ist verantwortlich?" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_prompts.py -v`
Expected: FAIL mit `ImportError` (`SYSTEM_GESPRAECH`). Danach voller Lauf.

- [ ] **Step 3: Write minimal implementation** — `bc1_service/prompts.py` ergänzen (Import `from bc1_core.gespraech import TurnKontext` an den bestehenden Import-Block; `SYSTEM_FRAGE`/`frage_nutzer_prompt` bleiben bis Task 5 unangetastet)

```python
SYSTEM_GESPRAECH = (
    "Du führst ein freundliches, professionelles Prozess-Interview auf "
    "Deutsch. Du bekommst, was der Nutzer gesagt hat, was daraus erfasst "
    "wurde und die nächste Kernfrage. Regeln: Bestätige NUR die gelieferten "
    "Werte — erfinde und ergänze nichts. Nenne NIE technische Feldnamen "
    "oder Interna. Struktur: kurze Bestätigung, falls nötig eine kurze "
    "Reaktion oder Erklärung, dann genau eine Frage. Bei Rückfragen und "
    "Nachfragen darfst du ein kurzes, neutrales Beispiel geben; in "
    "Erstfragen nie ein Beispiel. Antworte kompakt "
    "(2–4 Sätze plus Frage), ohne Meta-Kommentare."
)


def gespraech_nutzer_prompt(kontext: TurnKontext) -> str:
    """Nutzer-Prompt der Gesprächsschicht — von beiden Adaptern geteilt."""
    teile = [f"Nutzer-Nachricht:\n{kontext.nutzer_nachricht}"]
    if kontext.neu_erfasst:
        teile.append(
            "In diesem Turn erfasst (nur DIESE Werte bestätigen):\n"
            + "\n".join(f"- {e.frage} → {e.wert}" for e in kontext.neu_erfasst))
    else:
        teile.append("In diesem Turn wurde nichts Neues erfasst.")
    if kontext.ist_abschluss:
        teile.append(
            "Das Interview ist abgeschlossen. Fasse die Kernergebnisse in "
            "3–5 Sätzen zusammen:\n"
            + "\n".join(f"- {e.frage} → {e.wert}"
                        for e in kontext.profil_uebersicht))
        if kontext.offene_fragen:
            teile.append("Nenne ehrlich, was offen blieb:\n"
                         + "\n".join(f"- {f}" for f in kontext.offene_fragen))
    elif kontext.ist_nachfrage:
        teile.append(
            "NACHFRAGE — die bisherige Antwort war unklar oder ungültig. "
            "Formuliere die Kernfrage anders und konkreter, nenne in der "
            "Frage enthaltene Optionen vollständig, erkläre kurz den Zweck "
            "(gern mit einem kurzen, neutralen Beispiel) und sage, dass das "
            "Feld offen bleiben darf, wenn der Nutzer es nicht weiß.\n"
            f"Kernfrage: {kontext.naechste_frage}")
    else:
        teile.append("Stelle als Nächstes GENAU diese Frage, wörtlich "
                     f"übernommen:\n{kontext.naechste_frage}")
    return "\n\n".join(teile)
```

`bc1_service/claude_llm.py` — Import-Block um `SYSTEM_GESPRAECH, gespraech_nutzer_prompt` erweitern, `from bc1_core.gespraech import TurnKontext` ergänzen; nach `phrase` einfügen:

```python
    def antworte(self, kontext: TurnKontext) -> str:
        antwort = self._client.messages.create(
            model=self._modell,
            max_tokens=4096,
            system=SYSTEM_GESPRAECH,
            output_config={"effort": "low"},   # Versprachlichen, nicht knobeln
            messages=[{
                "role": "user",
                "content": gespraech_nutzer_prompt(kontext),
            }],
        )
        text = self._text_inhalt(antwort).strip()
        if not text:
            # Leer-Guard auf den GESTRIPPTEN Inhalt (Spec §5; Lektion aus dem
            # Ollama-Review): eine leere Antwort darf nie beim Nutzer landen.
            raise RuntimeError("LLM-Antwort ohne Inhalt")
        return text
```

Zusätzlicher Stub-Test in `tests/test_claude_llm.py` (RED zusammen mit Step 4 registrieren):

```python
def test_antworte_nur_whitespace_wirft():
    stub = _StubClient([_Antwort("   ")])
    kontext = TurnKontext(nutzer_nachricht="msg", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    with pytest.raises(RuntimeError, match="ohne Inhalt"):
        ClaudeLLM(client=stub).antworte(kontext)
```

`bc1_service/ollama_llm.py` — Imports analog erweitern; nach `phrase` einfügen:

```python
    def antworte(self, kontext: TurnKontext) -> str:
        inhalt = self._chat([
            {"role": "system", "content": SYSTEM_GESPRAECH},
            {"role": "user", "content": gespraech_nutzer_prompt(kontext)},
        ])
        return inhalt.strip()
```

- [ ] **Step 4: Adapter-Stub-Tests ergänzen** (RED war Step 2; diese laufen nach Step 3 grün mit — Muster/Stubs der jeweiligen Datei übernehmen). In `tests/test_claude_llm.py`:

```python
def test_antworte_nutzt_gespraechsprompt_und_strippt():
    stub = _StubClient([_Antwort("  Notiert. Wie oft?  ")])
    kontext = TurnKontext(nutzer_nachricht="msg", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    text = ClaudeLLM(client=stub).antworte(kontext)
    assert text == "Notiert. Wie oft?"
    aufruf = stub.messages.aufrufe[0]
    assert aufruf["system"] == SYSTEM_GESPRAECH
    assert "Wie oft?" in aufruf["messages"][0]["content"]
    assert aufruf["output_config"]["effort"] == "low"
```

In `tests/test_ollama_llm.py` (Stub-Muster der Datei):

```python
def test_antworte_nutzt_gespraechsprompt_und_strippt():
    stub = _StubClient(_antwort("  Notiert. Wie oft?  "))
    kontext = TurnKontext(nutzer_nachricht="msg", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    text = OllamaLLM(client=stub).antworte(kontext)
    assert text == "Notiert. Wie oft?"
    assert stub.aufrufe[0]["messages"][0]["content"] == SYSTEM_GESPRAECH
    assert "Wie oft?" in stub.aufrufe[0]["messages"][1]["content"]
```

(Die exakten Stub-Klassennamen/Helfer der beiden Dateien übernehmen — Aufbau ist in beiden vorhanden; die Assertions oben sind der Vertrag.)

- [ ] **Step 5: Run tests to verify they pass (voller Lauf)**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **~222 passed, 2 skipped** (216 + 4 Prompt- + 2 Adapter-Tests — exakt berichten)

- [ ] **Step 6: Commit**

```bash
git add bc1-context-discovery/bc1_service/prompts.py bc1-context-discovery/bc1_service/claude_llm.py bc1-context-discovery/bc1_service/ollama_llm.py bc1-context-discovery/tests/test_prompts.py bc1-context-discovery/tests/test_claude_llm.py bc1-context-discovery/tests/test_ollama_llm.py
git commit -m "feat(bc1): Gesprächs-Prompts (geteilt) + antworte in Claude- und Ollama-Adapter"
```

---

### Task 5: `phrase`-Rückbau (Abschluss des Breaking Change)

**Files:**
- Modify: `bc1_core/llm.py`, `bc1_service/prompts.py`, `bc1_service/claude_llm.py`, `bc1_service/ollama_llm.py`
- Test: `tests/test_llm.py`, `tests/test_prompts.py`, `tests/test_claude_llm.py`, `tests/test_ollama_llm.py` (Migration/Löschung)

**Interfaces:**
- Consumes: nichts Neues — Voraussetzung ist, dass nach Task 3+4 KEIN Produktionscode mehr `phrase` ruft.
- Produces: Endzustand laut Spec („kein Parallelbetrieb"): `LLMClient` hat `extract` + `antworte`; `SYSTEM_FRAGE`/`frage_nutzer_prompt` existieren nicht mehr.

- [ ] **Step 1: Konsumenten-Beweis VOR dem Rückbau**

Run: `grep -rn "\.phrase(\|SYSTEM_FRAGE\|frage_nutzer_prompt" bc1_core bc1_service`
Expected: Treffer NUR noch in den Definitionen (`llm.py`, `prompts.py`, beiden Adaptern) — kein Aufrufer. Bei unerwarteten Treffern: STOPP, Befund melden.

- [ ] **Step 2: Tests migrieren (Löschungen bei grüner Suite = Refactor-Schritt)**

1. `tests/test_llm.py`: `test_fake_phrase_uses_field_question` ersatzlos löschen (Nachfolger sind die `antworte`-Tests aus Task 2).
2. `tests/test_prompts.py`: die Tests zu `SYSTEM_FRAGE`/`frage_nutzer_prompt` (Imports + die betroffenen Testfunktionen, u. a. der Nachfrage-Hinweis-Test) ersatzlos löschen — der Nachfrage-Vertrag lebt jetzt in `test_nachfrage_verlangt_optionen_und_zweck`.
3. `tests/test_claude_llm.py`: `test_phrase_liefert_frage_und_markiert_nachfragen`, `test_phrase_erstfrage_ist_keine_nachfrage`, `test_phrase_abgeschnitten_wirft` löschen; der effort-low-Nachweis um Zeile 80–84 wechselt von `phrase` auf `antworte` (Kontext-Objekt statt Feld/State — Muster aus dem Task-4-Test).
4. `tests/test_ollama_llm.py`: die beiden `phrase`-Tests löschen; der Nur-Whitespace-Guard-Test (um Zeile 75–80) wechselt von `phrase` auf `antworte` (gleiche Stub-Antwort, gleicher `RuntimeError`-Erwartungswert — der Guard sitzt in `_chat` und bleibt damit bewiesen).

- [ ] **Step 3: Rückbau der Implementierungen**

1. `bc1_core/llm.py`: `phrase` aus Protocol UND `FakeLLM` entfernen (der `FieldSpec`-Import bleibt nur, falls noch gebraucht — sonst mit entfernen).
2. `bc1_service/prompts.py`: `SYSTEM_FRAGE` und `frage_nutzer_prompt` entfernen; dadurch ungenutzte Imports (`FieldSpec`, `SessionState`) mit entfernen.
3. `bc1_service/claude_llm.py` + `bc1_service/ollama_llm.py`: `phrase`-Methode entfernen; Import-Blöcke bereinigen (`SYSTEM_FRAGE`, `frage_nutzer_prompt`, ggf. `FieldSpec`).

- [ ] **Step 4: Run tests to verify they pass (voller Lauf) + Grep-Beweis**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **~216 passed, 2 skipped** (222 − ~6 gelöschte/umgezogene — exakt berichten), 0 Warnings.
Run: `grep -rn "phrase\|SYSTEM_FRAGE\|frage_nutzer_prompt" bc1_core bc1_service tests`
Expected: 0 Code-Treffer (höchstens Wortteile in unbeteiligten Strings — einzeln begründen).

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_core/llm.py bc1-context-discovery/bc1_service/prompts.py bc1-context-discovery/bc1_service/claude_llm.py bc1-context-discovery/bc1_service/ollama_llm.py bc1-context-discovery/tests/test_llm.py bc1-context-discovery/tests/test_prompts.py bc1-context-discovery/tests/test_claude_llm.py bc1-context-discovery/tests/test_ollama_llm.py
git commit -m "refactor(bc1): phrase-Rückbau — antworte ist der einzige Versprachlichungs-Weg (Spec: kein Parallelbetrieb)"
```

---

### Task 6: Transport-Fortschrittszeile + SMOKE-Abschnitt

**Files:**
- Modify: `bc1_service/api.py` (`_chat_text`), `bc1_service/n8n/SMOKE.md`
- Test: `tests/test_api.py` (Ergänzung + gezielte Migration)

**Interfaces:**
- Consumes: Payload-Felder `pflicht_erfasst`/`pflicht_gesamt`/`abschluss_text` aus Task 3.
- Produces: nichts für weitere Tasks — Nutzer-sichtbarer Abschluss der Schicht.

- [ ] **Step 1: Write the failing tests** — ergänzen in `tests/test_api.py` (Muster der Datei: TestClient + FakeLLM-Verdrahtung übernehmen)

```python
def test_chat_text_traegt_fortschrittszeile():
    client = _client()
    antwort = _turn(client, "m1", "Der Prozess heißt Urlaubsantrag",
                    session="s-fortschritt")
    daten = antwort.json()
    p = daten["payload"]
    erwartet = (f"✓ {p['pflicht_erfasst']} von {p['pflicht_gesamt']} "
                "Pflichtfeldern erfasst")
    assert daten["chat_text"].endswith(erwartet)
    assert daten["chat_text"].startswith(p["naechste_frage"])
```

Bestehende Assertions migrieren: `a1.json()["chat_text"] == a1.json()["payload"]["naechste_frage"]` → `a1.json()["chat_text"].startswith(a1.json()["payload"]["naechste_frage"])`; `"abgeschlossen" in a3.json()["chat_text"]` → `"Zusammenfassung" in a3.json()["chat_text"]` (Fake-Kompositionsformat) und zusätzlich `"✓ " in a3.json()["chat_text"]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_api.py -v`
Expected: FAIL — `chat_text` endet heute nicht auf die Fortschrittszeile. Danach voller Lauf.

- [ ] **Step 3: Write minimal implementation** — `bc1_service/api.py`, `_chat_text` ersetzen:

```python
def _chat_text(antwort: dict) -> str:
    if antwort["status"] == "frage":
        p = antwort["payload"]
        return ((p["naechste_frage"] or "")
                + f"\n\n✓ {p['pflicht_erfasst']} von {p['pflicht_gesamt']} "
                  "Pflichtfeldern erfasst")
    if antwort["status"] == "fertig":
        p = antwort["payload"]
        return ((p["abschluss_text"] or "Danke! Das Interview ist abgeschlossen.")
                + f"\n\n✓ {p['pflicht_erfasst']} von {p['pflicht_gesamt']} "
                  "Pflichtfeldern erfasst")
    return ("Da ist gerade etwas schiefgegangen — "
            "bitte schick deine Nachricht einfach noch einmal.")
```

- [ ] **Step 4: SMOKE.md-Abschnitt ergänzen** — ans Datei-Ende:

```markdown
## Gesprächsschicht live

Seit der Gesprächsschicht antwortet der Interviewer pro Turn mit Bestätigung
(nur echte erfasste Werte) + Reaktion + Katalogfrage; darunter steht die
deterministische Fortschrittszeile („✓ X von Y Pflichtfeldern erfasst").
Beim Abschluss kommt eine Ergebnis-Zusammenfassung inkl. offener Felder.

Erwartung ehrlich: Mit `BC1_LLM=ollama` (8B) ist die STRUKTUR nachweisbar
(Bestätigung, keine Feldnamen-Leaks, KP-Optionsliste überlebt in Erstfragen
wörtlich) — gut KLINGEN wird es erst mit dem Claude-Adapter. Die
Klang-Abnahme ist ein offener Punkt wie der Echt-Claude-Smoke (P2).
```

- [ ] **Step 5: Run tests to verify they pass (voller Lauf)**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -W error`
Expected: **~217 passed, 2 skipped, 0 Warnings** (exakt berichten)

- [ ] **Step 6: Commit**

```bash
git add bc1-context-discovery/bc1_service/api.py bc1-context-discovery/tests/test_api.py bc1-context-discovery/bc1_service/n8n/SMOKE.md
git commit -m "feat(bc1): deterministische Fortschrittszeile im Chat-Text + SMOKE-Abschnitt Gesprächsschicht"
```

---

## Abnahme (Gesamtergebnis)

- Suite grün, 0 Warnings (`-W error`); exakte Endzahl berichten (Zwischenstände oben sind Momentaufnahmen).
- Kern-Invarianten intakt: Bestätigungen/Zusammenfassungen enthalten NUR Werte aus dem echten State (FakeLLM-Verträge beweisen es); technische Feldnamen erreichen den `TurnKontext` nie (Konstruktions-Test).
- Die 3 Demo-Durchläufe laufen unverändert bis `fertig` (Payload-Assertions unberührt).
- `grep`-Beweis aus Task 5: kein `phrase`-Konsument mehr.
- Live-Stichprobe gegen Ollama (Dienst wie in SMOKE beschrieben): Struktur-Nachweis — Bestätigung sichtbar, Erstfragen wörtlich (B4-Optionsliste intakt), Fortschrittszeile korrekt. **Ausdrücklich keine Klang-Abnahme** — die erfolgt mit dem Claude-Key und bleibt als offener Abnahme-Punkt geführt.
