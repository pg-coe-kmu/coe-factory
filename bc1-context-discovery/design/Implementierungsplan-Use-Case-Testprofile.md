# Use-Case-Testprofile (Rev. 12) — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) — Tasks einzeln, nach jedem Test ein voller `.venv/bin/pytest`-Lauf aus `bc1-context-discovery/` (tdd-guard). `*.py` nur über Edit/Write anlegen, nie per Bash.

**Ziel:** Die drei Use-Case-Testprofile (Anhang A des DB-Profil-Plans) sind **aus dem Repo reproduzierbar**: ein Modul trägt die Interview-Skripte, ein Test beweist, dass jedes über den regulären Weg (`process_turn` → `ProfilWriter`) `fertig` wird, die Testdaten-Kennzeichnung trägt und ein Wiederholungslauf keine zweite Version erzeugt.

**Architektur:** Ein kleines Modul `bc1_service/use_case_testprofile.py` mit den drei Fällen als **Daten** (session_id, Anfrage, Fokus-TP, Nachrichten mit FakeLLM-Extraktionen), einer Funktion, die einen Fall durch den Kern fährt, und einer Funktion, die alle drei gegen eine Datenbank schreibt. Session-Store bewusst In-Memory (kein ungeprüftes `bc1.sessions` in der Produktions-DB). Der Profil-Schreibweg folgt `api.py`: Writer nach jedem Turn, Rückgabe der Datenbank als Overlay über den Payload. Die Transport-Guards von `api.py` (`pruefe_mandant`, HTTP-Fehlercodes) entfallen bewusst — der Store ist je Lauf frisch, ein fremder Zustand kann nicht geladen werden.

**Tech Stack:** Python 3.11+, pytest, psycopg 3 / psycopg_pool, Test-Container PostgreSQL 17 (`tests/db_fixture.py`).

**Spec:** `Implementierungsplan-DB-Profil-Fundament.md`, Anhang A (Abnahmekriterien 1–5) + Nachtrag 08.09. (Lehre: Kennzeichnung in dieselbe Nachricht wie das letzte Pflichtfeld).

## Global Constraints

- Kein Hand-INSERT — nur `process_turn` + `ProfilWriter` (Kriterium 1).
- Werte passend zu NoroAI (rund 10 Mitarbeitende), als gesetzt gekennzeichnet, Quelle Projektgruppe, keine Person (Kriterium 2). **Die Zahlenwerte sind exakt die vom 08.09. in der Datenbank** — das Modul darf sie nicht verändern, sonst widerspricht das Repo dem Ist-Stand.
- Kennzeichnung per SQL wiederfindbar: `profil->'felder'->'open_remarks'->>'wert' LIKE 'Testdaten%'` (Kriterium 3).
- Wiederholbar: gleiche `session_id`/`message_id` ⇒ keine zweite Version (Kriterium 4).
- Zeilen werden `fertig` (Freeze final) — bewusst, damit BC0s `am_gate` greift (Kriterium 5).
- Generisch: keine Verzweigung auf Use-Case-Namen im Kern; die Fälle sind Daten in einem Service-Modul.

---

## Dateien

- Create: `bc1_service/use_case_testprofile.py` — Fälle als Daten, `fuehre_interview`, `schreibe_testprofile`, `main`
- Create: `tests/test_use_case_testprofile.py`
- Modify (Doku): `Implementierungsplan-DB-Profil-Fundament.md` Anhang A → „ausgeführt, siehe Rev. 12"

**Interfaces (Produces):**
- `KENNZEICHEN: str` — beginnt mit `"Testdaten"`
- `@dataclass(frozen=True) Fall(session_id: str, anfrage_id: str, fokus_tp: str, nachrichten: tuple[tuple[str, tuple[tuple[str, str], ...]], ...])`
- `FAELLE: tuple[Fall, ...]` (drei Fälle)
- `fuehre_interview(store, paket, fall, *, company_id, writer=None) -> dict` — letzte Antwort von `process_turn`; mit `writer` wird nach jedem Turn `writer.reconcile(store.load(fall.session_id), antwort)` aufgerufen
- `schreibe_testprofile(pool, company_id) -> list[dict]` — je Fall `{"session_id", "status", "vollstaendigkeit"}`

---

### Task 1: Die drei Fälle enden offline `fertig` und vollständig

**Files:** Create `tests/test_use_case_testprofile.py`, Create `bc1_service/use_case_testprofile.py`

- [ ] **Step 1: Failing test schreiben** (ganze Datei, ein Test)

```python
"""Anhang A (Rev. 12): die drei Use-Case-Testprofile sind aus dem Repo reproduzierbar."""
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.store import InMemoryStateStore
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket
from bc1_service.use_case_testprofile import FAELLE, fuehre_interview

KONTEXT = Bc0Kontext(MANDANT_A, (("KP-05.TP-1", "Wissenstransfer"),
                            ("KP-06.TP-1", "Consulting-Matching"),
                            ("KP-06.TP-2", "Reise- und Einsatzplanung")),
                     tuple(f"S-0{i}" for i in range(1, 7)))


def _antworten():
    paket = baue_discovery_paket(kontext=KONTEXT)
    return [(fall, fuehre_interview(InMemoryStateStore(), paket, fall, company_id=MANDANT_A))
            for fall in FAELLE]


def test_jeder_fall_endet_fertig_und_vollstaendig():
    for fall, antwort in _antworten():
        assert antwort["status"] == "fertig", fall.session_id
        assert antwort["payload"]["vollstaendigkeit"] == 1.0, fall.session_id
```

- [ ] **Step 2: Voller Lauf — RED registrieren** (`ModuleNotFoundError: bc1_service.use_case_testprofile`)

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q -W error 2>&1 | tail -3`
Expected: 1 error (collection), Rest grün.

- [ ] **Step 3: Modul anlegen — minimal** (`FAELLE` mit drei Fällen, `fuehre_interview`; `fuehre_interview` baut das FakeLLM aus `fall.nachrichten` und ruft `process_turn` je Nachricht mit `message_id="m<i>"`)

```python
"""Use-Case-Testprofile (Anhang A, Rev. 12) — die drei Faelle als Daten.

Ueber den REGULAEREN Schreibweg: process_turn -> ProfilWriter, wie in api.py.
Werte: NoroAI (rund 10 Mitarbeitende), GESETZT, nicht erhoben — exakt die Zahlen,
die am 08.09.2026 in bc1.prozessprofil geschrieben wurden.

Kennzeichnung (open_remarks) steht in derselben Nachricht wie das letzte
Pflichtfeld: mit dem letzten Pflichtfeld wird der Kern terminal (status=fertig)
und der Writer friert die Zeile ein — eine spaetere Nachricht bleibt 'fehlt'
(am 08.09. an Version 1 gemessen).
"""
from __future__ import annotations

from dataclasses import dataclass

from bc1_core.core import process_turn
from bc1_core.llm import ExtractionCandidate, FakeLLM

KENNZEICHEN = ("Testdaten Use-Case-Definition 24.08., nicht erhoben. "
               "Quelle: Projektgruppe CoE-Factory.")

Nachricht = tuple[str, tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class Fall:
    session_id: str
    anfrage_id: str
    fokus_tp: str
    nachrichten: tuple[Nachricht, ...]


def _skript(intent, name, owner, prozess, schritte, trigger, eingang,
            eingangsformat, ausgang, frequenz, faelle, gesamtdauer,
            fokus, fokusdauer, quelle, sicherheit, rollen, systeme,
            medienbruch, doku, standard, daten, stabil, pii) -> tuple[Nachricht, ...]:
    return (
        (f"Wir wollen {intent} — es geht um den ganzen Prozess, Ziel ist Zeit sparen.", (
            ("request_intent", intent), ("request_goal", "zeit_sparen"),
            ("scope_focus", "ganzer_prozess"), ("process_name", name))),
        ("Verantwortlich und Ablauf.", (
            ("process_owner_role", owner), ("process_id", prozess),
            ("process_steps", schritte))),
        ("Auslöser, Eingang und Ergebnis.", (
            ("trigger_text", trigger), ("input_text", eingang),
            ("input_format", eingangsformat), ("output_text", ausgang))),
        ("Mengen und Dauer.", (
            ("frequency_per_year", frequenz), ("executions_per_run", faelle),
            ("total_duration_minutes", gesamtdauer))),
        ("Der anstrengendste Schritt.", (
            ("focus_step", fokus), ("focus_step_duration_minutes", fokusdauer),
            ("focus_step_duration_source", quelle),
            ("focus_step_duration_confidence_pct", sicherheit))),
        ("Beteiligte und Systeme.", (
            ("focus_step_roles", rollen), ("focus_step_systems", systeme),
            ("focus_step_media_break", medienbruch),
            ("documentation_status", doku))),
        ("Voraussetzungen und Herkunft dieser Angaben.", (
            ("standardization_level", standard),
            ("data_availability_score", daten), ("stability_score", stabil),
            ("pii_involved", pii), ("open_remarks", KENNZEICHEN))),
    )


FAELLE: tuple[Fall, ...] = (
    Fall("uc1-reisebuchung-testdaten-v2", "A-2026-01", "KP-06.TP-2", _skript(
        "die Reise- und Einsatzplanung automatisieren", "Reise- und Einsatzplanung",
        "Office Management", "KP-06",
        "Bedarf melden, Termine abstimmen, Reise buchen, Abrechnung",
        "Ein Einsatz beim Kunden steht an", "Einsatztermine und Reisewunsch",
        "mail", "gebuchte Reise mit Bestätigungen",
        "15 pro Monat", "180", "3 Stunden",
        "KP-06.TP-2", "90 Minuten", "geschaetzt", "60%",
        "Office Management, Consultants", "S-01, S-02",
        "Ja.", "2", "2", "3", "3", "ja")),
    Fall("uc2-wissensbasis-testdaten-v2", "A-2026-02", "KP-05.TP-1", _skript(
        "den Wissenstransfer aus Projekten automatisieren", "Wissenstransfer",
        "Fachexperte", "KP-05",
        "Anfrage sichten, Dokumente suchen, Antwort schreiben, ablegen",
        "Anfrage eines Kollegen oder Kunden", "Anfragetext und Dokumentenablage",
        "digital", "beantwortete Anfrage mit Quellen",
        "5 pro Woche", "260", "45 Minuten",
        "KP-05.TP-1", "25 Minuten", "geschaetzt", "50%",
        "Fachexperten, Projektleitung", "S-03, S-04",
        "ja", "3", "3", "3", "4", "nein")),
    Fall("uc3-consultant-matching-testdaten-v2", "A-2026-03", "KP-06.TP-1", _skript(
        "das Consulting-Matching beschleunigen", "Consulting-Matching",
        "Staffing Manager", "KP-06",
        "Anfrage erfassen, Profile suchen, Matching, Vorschlag versenden",
        "Kundenanfrage nach einem Consultant", "Anforderungsprofil des Kunden",
        "mail", "Personalvorschlag mit passenden Profilen",
        "40 pro Jahr", "40", "2 Stunden",
        "KP-06.TP-1", "1 Stunden", "geschaetzt", "70 %",
        "Staffing, Vertrieb", "S-05, S-06",
        "nein", "2", "3", "3", "3", "ja")),
)


def fuehre_interview(store, paket, fall: Fall, *, company_id: str, writer=None) -> dict:
    llm = FakeLLM({text: [ExtractionCandidate(f, w) for f, w in felder]
                   for text, felder in fall.nachrichten})
    antwort: dict = {}
    for i, (text, _) in enumerate(fall.nachrichten, start=1):
        antwort = process_turn(store, llm, paket, fall.session_id, f"m{i}", text,
                               company_id=company_id)
        if writer is not None:
            writer.reconcile(store.load(fall.session_id), antwort)
    return antwort
```

Der Guard lässt ggf. nur Teilschritte zu (erst Modul + Namen, dann Logik) — dann so vorgehen, jeder Zwischenschritt mit vollem Lauf.

- [ ] **Step 4: Voller Lauf — GREEN**

Run: wie Step 2. Expected: `452 passed, 4 skipped`.

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_service/use_case_testprofile.py bc1-context-discovery/tests/test_use_case_testprofile.py
git commit -m "feat(bc1): Use-Case-Testprofile als Daten im Repo — drei Faelle enden fertig (Rev. 12, Task 1)"
```

### Task 2: Die Kennzeichnung ist gültig und steht bei einem Pflichtfeld

- [ ] **Step 1: Test ergänzen** (einzeln — ein Test je Edit)

```python
def test_kennzeichnung_ist_gueltig_und_beginnt_mit_testdaten():
    for fall, antwort in _antworten():
        feld = antwort["payload"]["felder"]["open_remarks"]
        assert feld["status"] == "gueltig", fall.session_id
        assert feld["wert"].startswith("Testdaten"), fall.session_id
```

- [ ] **Step 2: Voller Lauf** — Erwartung: grün bei Ankunft (die Daten aus Task 1 tragen die Kennzeichnung). Grün-bei-Ankunft ist hier korrekt: der Test nagelt das Verhalten fest, das Version 1 am 08.09. NICHT hatte.

- [ ] **Step 3: Zweiten Test ergänzen** (die Lehre als Strukturtest)

```python
def test_kennzeichnung_steht_in_derselben_nachricht_wie_ein_pflichtfeld():
    paket = baue_discovery_paket(kontext=KONTEXT)
    pflicht = {s.name for s in paket.required_fields()}
    for fall in FAELLE:
        traeger = [felder for _, felder in fall.nachrichten
                   if any(name == "open_remarks" for name, _ in felder)]
        assert len(traeger) == 1, fall.session_id
        assert pflicht & {name for name, _ in traeger[0]}, (
            f"{fall.session_id}: open_remarks ohne Pflichtfeld in derselben Nachricht "
            "— nach dem letzten Pflichtfeld ist der Kern terminal, spaetere Werte bleiben 'fehlt'")
```

- [ ] **Step 4: Voller Lauf** — grün. **Gegenprobe (Mutation, nicht committen):** `("open_remarks", KENNZEICHEN)` in eine eigene achte Nachricht verschieben → Test 1 UND dieser Test müssen rot werden. Zurückdrehen.

- [ ] **Step 5: Commit** — `test(bc1): Kennzeichnung gueltig und an ein Pflichtfeld gebunden (Rev. 12, Task 2)`

### Task 3: `schreibe_testprofile` legt drei fertige Zeilen an und ist wiederholbar

**Files:** Modify `tests/test_use_case_testprofile.py`, Modify `bc1_service/use_case_testprofile.py`

- [ ] **Step 1: DB-Test ergänzen** (Gerüst kennt nur KP-01/KP-02 — der Test legt die drei Fokus-TPs für Mandant A an, mit je einer Bewertung in `E-2026-01`, plus S-03..S-06)

```python
import pytest
from psycopg_pool import ConnectionPool

from bc1_service.use_case_testprofile import schreibe_testprofile
from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung


def _noro_geruest(conn) -> None:
    conn.execute(
        "INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) VALUES "
        "(%s, 'KP-05', 'Wissen', 'Kerngeschäftsprozess'), "
        "(%s, 'KP-06', 'Personal', 'Unterstützungsprozess')", (MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO ref_teilprozesse (company_id, sub_process_id, process_id, step_no, sub_process_name) VALUES "
        "(%s, 'KP-05.TP-1', 'KP-05', 1, 'Wissenstransfer'), "
        "(%s, 'KP-06.TP-1', 'KP-06', 1, 'Consulting-Matching'), "
        "(%s, 'KP-06.TP-2', 'KP-06', 2, 'Reise- und Einsatzplanung')",
        (MANDANT_A, MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO mandant_systeme (company_id, system_id, bezeichnung) VALUES "
        "(%s, 'S-03', 'Wiki'), (%s, 'S-04', 'Ablage'), (%s, 'S-05', 'CRM'), (%s, 'S-06', 'Skills')",
        (MANDANT_A, MANDANT_A, MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO bitkom_bewertungen (company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg, bewertet_am) VALUES "
        "(%s, 'E-2026-01', 'KP-05.TP-1.I-01', 'KP-05.TP-1', 1, 3, 'Testdaten', '2026-01-15'), "
        "(%s, 'E-2026-01', 'KP-06.TP-1.I-01', 'KP-06.TP-1', 1, 2, 'Testdaten', '2026-01-15'), "
        "(%s, 'E-2026-01', 'KP-06.TP-2.I-01', 'KP-06.TP-2', 1, 2, 'Testdaten', '2026-01-15')",
        (MANDANT_A, MANDANT_A, MANDANT_A))


@pytest.fixture
def pool():
    frische_db(DSN)
    with verbindung(DSN, rolle=None) as conn:
        _noro_geruest(conn)
    p = ConnectionPool(DSN, min_size=1, max_size=4, open=True,
                       kwargs={"options": "-c role=bc1_role"})
    yield p
    p.close()


def _zeilen(sql):
    with verbindung(DSN) as conn:
        return conn.execute(sql).fetchall()


def test_schreibe_legt_drei_fertige_gekennzeichnete_zeilen_an(pool):
    ergebnis = schreibe_testprofile(pool, MANDANT_A)
    assert [e["status"] for e in ergebnis] == ["fertig"] * 3
    zeilen = _zeilen("SELECT focus_step_id, status, erhebung_id FROM bc1.prozessprofil ORDER BY 1")
    assert zeilen == [("KP-05.TP-1", "fertig", "E-2026-01"),
                      ("KP-06.TP-1", "fertig", "E-2026-01"),
                      ("KP-06.TP-2", "fertig", "E-2026-01")]
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE profil->'felder'->'open_remarks'->>'wert' LIKE 'Testdaten%'") == [(3,)]
```

(`verbindung(DSN, rolle=None)` = Login-Benutzer der Test-DSN ohne `SET ROLE`; der Kontextmanager committet bei sauberem Ende — **gemessen (Review 08.09.)**, kein eigenes `conn.commit()` nötig.)

- [ ] **Step 2: Voller Lauf — RED** (`ImportError: schreibe_testprofile`)

- [ ] **Step 3: Implementieren**

```python
from bc1_core.store import InMemoryStateStore
from bc1_service.discovery_paket import baue_discovery_paket
from bc1_service.profil_writer import ProfilWriter
from bc1_service.start import lade_kontext


def schreibe_testprofile(pool, company_id: str) -> list[dict]:
    with pool.connection() as conn:
        kontext = lade_kontext(conn, company_id)
    paket = baue_discovery_paket(kontext=kontext)
    writer = ProfilWriter(pool, company_id, paket)
    ergebnis = []
    for fall in FAELLE:
        antwort = fuehre_interview(InMemoryStateStore(), paket, fall,
                                   company_id=company_id, writer=writer)
        ergebnis.append({"session_id": fall.session_id, "status": antwort["status"],
                         "vollstaendigkeit": antwort["payload"].get("vollstaendigkeit")})
    return ergebnis
```

- [ ] **Step 4: Voller Lauf — GREEN.** Fehlschlag bei `erhebung_id`? Dann liefert Task-13-Lookup eine andere Erhebung — Erwartung aus der Messung korrigieren, nicht den Lookup.

- [ ] **Step 5: Wiederholbarkeits-Test ergänzen**

```python
def test_zweiter_lauf_erzeugt_keine_zweite_version(pool):
    schreibe_testprofile(pool, MANDANT_A)
    schreibe_testprofile(pool, MANDANT_A)
    assert _zeilen("SELECT focus_step_id, count(*) FROM bc1.prozessprofil GROUP BY 1 ORDER BY 1") == [
        ("KP-05.TP-1", 1), ("KP-06.TP-1", 1), ("KP-06.TP-2", 1)]
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil WHERE status = 'in_erhebung'") == [(0,)]
```

- [ ] **Step 6: Voller Lauf** — Erwartung grün bei Ankunft. **Mechanismus, gemessen (Review 08.09.):** der Store ist je Lauf frisch, die Replay-Weiche des Kerns greift hier NICHT — der zweite Lauf rechnet alle Turns neu. Was die zweite Version verhindert, ist allein die **Writer-Bindung** in `profil_write_status`: bei fertiger Zeile liefert `reconcile` das gespeicherte Profil zurück. Wenn rot: echter Befund am Writer, nicht am Test.

- [ ] **Step 7: Commit** — `feat(bc1): schreibe_testprofile — drei Zeilen ueber den Writer, wiederholbar (Rev. 12, Task 3)`

### Task 4: CLI-Einstieg und Doku

- [ ] **Step 1: Test für den Einstieg** (kein Netz, kein DB — nur Argument-Verhalten)

```python
from bc1_service.use_case_testprofile import main


def test_main_ohne_echt_schreibt_nicht(monkeypatch, capsys):
    monkeypatch.setenv("BC1_DB_DSN", "postgresql://unbenutzt")
    monkeypatch.setattr("bc1_service.use_case_testprofile.schreibe_testprofile",
                        _darf_nicht_schreiben)   # benannter Helfer, der AssertionError wirft
    assert main(["--company-id", MANDANT_A]) == 0
    assert "TROCKENLAUF" in capsys.readouterr().out
```

- [ ] **Step 2: Voller Lauf — RED** (`ImportError: main`)

- [ ] **Step 3: Implementieren**

```python
import argparse
import os
import sys

from psycopg_pool import ConnectionPool


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Use-Case-Testprofile ueber den Writer schreiben.")
    ap.add_argument("--company-id", required=True)
    ap.add_argument("--echt", action="store_true", help="wirklich schreiben (sonst Trockenlauf)")
    args = ap.parse_args(argv)
    print(f"{len(FAELLE)} Faelle: " + ", ".join(f.session_id for f in FAELLE))
    if not args.echt:
        print("TROCKENLAUF — nichts geschrieben. Mit --echt schreiben.")
        return 0
    pool = ConnectionPool(os.environ["BC1_DB_DSN"], min_size=1, max_size=3, open=True)
    try:
        ergebnis = schreibe_testprofile(pool, args.company_id)
    finally:
        pool.close()
    for e in ergebnis:
        print(f"{'OK ' if e['status'] == 'fertig' else 'FEHLER'} {e['session_id']}: "
              f"{e['status']} vollstaendigkeit={e['vollstaendigkeit']}")
    return 0 if all(e["status"] == "fertig" for e in ergebnis) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Voller Lauf — GREEN**, dann Doku: in `Implementierungsplan-DB-Profil-Fundament.md` Anhang A den Kopf ergänzen: „**Ausgeführt 08.09., reproduzierbar seit Rev. 12:** `bc1_service/use_case_testprofile.py`, Tests `tests/test_use_case_testprofile.py`. Aufruf: `BC1_DB_DSN=… .venv/bin/python -m bc1_service.use_case_testprofile --company-id <uuid> --echt`."

- [ ] **Step 5: Commit** — `feat(bc1): CLI fuer die Use-Case-Testprofile + Anhang A als ausgefuehrt markiert (Rev. 12, Task 4)`

---

## Selbstprüfung (Autor)

- **Spec-Abdeckung:** Kriterium 1 (regulärer Weg) → Task 3 nutzt `ProfilWriter`, kein INSERT · 2 (Werte/Kennzeichnung/Quelle) → Task 1 Daten + Task 2 · 3 (SQL-wiederfindbar) → Task 3 Assertion `LIKE 'Testdaten%'` · 4 (wiederholbar) → Task 3 Step 5 · 5 (fertig = Freeze) → Task 3 Assertion `fertig` · Lehre 08.09. → Task 2 Strukturtest + Mutation.
- **Platzhalter:** keine. **Typen:** `Fall`, `FAELLE`, `fuehre_interview(store, paket, fall, *, company_id, writer)`, `schreibe_testprofile(pool, company_id)`, `main(argv)` in allen Tasks gleich.
- **Ehrlich:** Der Gerüst-Zusatz im Test (`_noro_geruest`) dupliziert Wissen aus `db_fixture._testdaten`; bewusst lokal gehalten (YAGNI), bis ein zweiter Test dieselben TPs braucht. `erhebung_id`-Erwartung `E-2026-01` folgt aus der Task-13-Regel (jüngste nicht verworfene Bewertung) — im Lauf verifizieren.

---

## Review — adjudiziert am 08.09.2026

Zwei unabhängige Reviews des Commit-Bereichs `e99d81d..f2e56d5`: **Claude messend** (Suite, Mutationen, Zähler-Wrapper, CLI End-to-End gegen den Container) und **Codex statisch** (ohne DB-Zugriff, ausdrücklich so gekennzeichnet). Kein Critical. Befunde nach Schwere; Doppelnennungen zusammengeführt.

| Befund | Schwere | Entscheidung | Beleg |
|---|---|---|---|
| Writer-Rückgabe verworfen — bei bestehender Bindung meldet der Lauf den frischen Kern statt der eingefrorenen Zeile (Codex B3, Claude I2) | Important | **gefixt:** Overlay mit `OVERLAY_SCHLUESSEL` aus `api.py` (eine Wahrheit) | Test mit echtem Writer: gleiche `session_id`, 900 statt 90 Minuten im Skript → gemeldet 90 (RED→GREEN) |
| „exakt die Zahlen vom 08.09." nirgends gepinnt; Kennzeichnung nur per Präfix geprüft (Codex B4, Claude I2) | Important | **gefixt:** unabhängige Erwartungstabelle der sechs Spalten je TP + vollständiger Kennzeichnungstext, nicht aus `FAELLE` abgeleitet | `test_gespeicherte_spalten_und_kennzeichnung_sind_die_werte_vom_08_09` |
| Ohne `BC1_TEST_DB_DSN` zwei Errors statt Skips (Codex B1, Claude I1) | Important | **gefixt:** `pytest.skip` in der `pool`-Fixture — die Offline-Tests laufen weiter | gemessen: `4 passed, 2 skipped` ohne DSN |
| Kriterium 4, zweite Hälfte fehlt; Mechanismus „Replay-Weiche" gemessen falsch — Träger ist die Writer-Bindung (Claude I3, Codex B8) | Important | **gefixt:** Docstring, Testkommentar, Plan korrigiert; `test_neue_session_id_erzeugt_version_2` | Version 1+2 je TP nach zweitem Lauf mit neuer `session_id` |
| `--echt`-Pfad ohne Test (Claude I4, Codex B5) | Important | **gefixt:** Erfolg (3× OK, Exit 0, 3 Zeilen), fehlende DSN (klare Meldung, Exit 1 — vorher nackter `KeyError`, Claude M4), Mandant ohne die TPs (3× FEHLER, Exit 1, 0 Zeilen) | drei CLI-Tests |
| **`executions_per_run` = Jahreshäufigkeit** in allen drei Fällen — „Fälle je Durchlauf" fachlich fraglich (Codex B2) | Important | **nicht geändert, Entscheidung offen:** die Werte reproduzieren den Ist-Stand vom 08.09.; die Einheit ist eine Vertragsfrage mit BC2 (`menge`), Abschlussplan **A1**. Kommentar am Datenblock; Korrektur nur als neuer Lauf mit neuer `session_id` | Richard / BC2 |
| Tote Metadaten `anfrage_id`/`fokus_tp`, 24 Positionsargumente (Codex B7, Claude M2) | Minor | **gefixt:** `_skript` nur mit benannten Argumenten; `fokus_tp` per Test gegen das Skript geprüft; `anfrage_id` als dokumentarisch erklärt | `test_fokus_tp_stimmt_mit_dem_skript_ueberein` |
| Mandanten-UUID im Offline-Test/Plan unnötig (Codex B6) | Minor | **gefixt:** synthetischer Fixture-Mandant; die echte Kennung kommt nur per CLI-Argument | — |
| „dieselbe Reihenfolge wie api.py" überzeichnet (Claude M3) | Minor | **gefixt:** Docstring nennt, was entfällt und warum | — |
| Anhang-A-Hinweis „Kriterien 1–5 festgenagelt" zu weitgehend (Claude M7) | Minor | **gefixt:** Hinweis präzisiert, offene Vertragsfrage genannt | — |
| Trivialer Doku-Drift: Tupel-Typ, Commit-Hinweis, Lambda-Stub (Claude M8) | Minor | **gefixt** im Plan | — |
| Trockenlauf beweist nichts über das Ziel (Claude M1, M6) | Minor | **deferiert:** `--echt` scheitert bei falschem Mandanten schnell und sauber (gemessen: `RuntimeError`, Exit 1, keine Zeile); ein Pre-Flight dupliziert `lade_kontext` für ein Werkzeug mit einer Handvoll Aufrufe (YAGNI). **Nächster Schritt:** sobald ein zweiter Nutzer die CLI bedient, Kontextprüfung im Trockenlauf | — |
| TP-Name „Consulting-Matching" vs. Snapshot „Neueinstellung und Onboarding" (Claude M5) | Minor | **kein Handlungsbedarf:** die Live-Datenbank führt seit BC0s v3.0 „Consulting-Matching" (Kontextmessung 08.09.); der Snapshot v3 auf `main` ist älter. **Nächster Schritt:** Snapshot-Abgleich in Abschlussplan A5 | `kontext.log` 08.09. |

**Nicht geprüft (beide Reviewer):** Verhalten gegen die Live-Supabase (nur Container); fachliche Passung zu BC0s Anfragetexten.
