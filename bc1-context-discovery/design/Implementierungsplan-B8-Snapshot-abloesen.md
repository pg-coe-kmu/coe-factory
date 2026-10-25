# B8 — Snapshot-Modus ablösen, `GET /prozesse` streichen: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Stand:** 24.10.2026, Fassung 2. Unabhängig geprüft am 24.10. (Claude-Prüfer; Codex war am Nutzungslimit): „bereit mit Korrekturen", 0 Critical, 6 Important, 13 Minor. Alle eingearbeitet; M12 (Sortierung) begründet nicht getestet, siehe Task 1.

**Goal:** Die Kernprozess-Auswahl (B4) kommt aus BC0s Sicht `v_prozesse_lesen` statt aus einer Datei; Snapshot-Modul, `BC1_SNAPSHOT_PFAD` und `GET /prozesse` entfallen; der Docker-Start bindet nur an `127.0.0.1`.

**Architecture:** Ein neuer Lesepfad `kernprozesse` füllt beim Start das neue Feld `Bc0Kontext.prozesse`. Das Discovery-Paket nimmt B4-Auswahl und Fingerabdruck nur noch aus dem Kontext. Der Parameter `prozesse` der Paket-Fabriken entfällt, `kontext` wird Schlüsselwort-Parameter. Dienst und Testprofil-Werkzeug bekommen die Liste so ohne eigene Verdrahtung.

**Tech Stack:** Python 3.11, psycopg 3, FastAPI, pytest, uv 0.11. Test-Postgres im Container `bc1-test-pg`.

**Spec:** `bc1-context-discovery/design/Spec-B8-Snapshot-abloesen.md` (Entwurf 2, abgenommen 24.10.2026 einschließlich 9.2–9.10)

## Global Constraints

- **TDD-Guard nie umgehen.** `*.py` unter `coe-factory/` NUR mit Edit/Write/MultiEdit ändern; Bash nur für pytest, git und Messungen. Wer per Bash schreibt, umgeht den Guard. Bei einem Block: Skill `tdd-guard` aufrufen; jeder NEU gelöste Block kommt dort in die Lessons-Tabelle.
- **Dateien löschen (Task 5):** Der Inhalt einer `*.py` wird per Edit geleert, damit der Guard ihn prüft. `git rm` entfernt danach nur noch leere `*.py` und die Nicht-Python-Datei `snapshot_schema.json`. Lehnt der Guard das Leeren ab und gibt es keinen guard-konformen Weg: anhalten und der BC1-Projektleitung vorlegen. Kein `git rm` einer Datei mit Inhalt.
- **Neue Assertionen und Fixture-Umbauten nie in grüne Bestandstests** (Lessons 08.10. und 22.09.): Dafür gibt es neue Geschwistertests. Aufrufargumente in Bestandstests nachziehen ist erlaubt, wenn sie rot sind (Lesson 05.10.).
- **pytest** immer aus `bc1-context-discovery/`:
  - mit DB: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`;
  - ohne DB dasselbe ohne die Variable.
  - Bei Schritten, die `main.py` oder `start.py` betreffen, **immer mit DB**, sonst sind die Verdrahtungstests übersprungen.
  - Stand auf `main` @ `b0071f3`: mit DB 807 passed / 4 skipped, ohne DB 550 / 261.
- **Paketfassung bleibt `1.2`** (`SCHEMA_VERSION_CTX`); die kontextfreie bleibt `1.0`.
- **Feste Kennungen** (mit `KONTEXT` aus `tests/test_discovery_paket.py`, gemessen auf `b0071f3`, Werte unabhängig nachgerechnet):
  - leere Kernprozess-Liste → `1.2+ctx-0a6cdaacdfde28de`;
  - Liste `(("KP-01", "Auftrag"),)` → `1.2+ctx-9e81785de2c8b1d8`.
- **Unverändert:** `contracts/`, `bc1_service/db/*.sql` (DDL, Signaturen), Gerüst-Rechte, `bc1_core/`, die JSON-Form von `_ctx_fingerprint`.
- **SQL des Lesepfads wörtlich:** `SELECT process_id, process_name FROM v_prozesse_lesen WHERE company_id = %s ORDER BY process_id`.
- **Keine Mandantendaten, keine Zugangsdaten** in Commits; das Repo ist öffentlich. Kein Push ohne OK der BC1-Projektleitung. **Merge erst nach der Messung aus Task 6 Step 7** (Spec 5).
- Commits auf Zweig `bc1-b8-snapshot-abloesen`, Nachrichten auf Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Antwort mit Namen statt ID** („Logistik"): Ob der Extraktor den Namen auf die ID abbildet, zeigen FakeLLM-Tests nicht. Kein Offline-Test möglich; Live-Bewertung beim Lauf von Version 3 bzw. beim Durchstich. Wird im Abschlussplan unter (4g) ergänzt (Task 6).
2. **`BC1_SNAPSHOT_PFAD` steht noch in einer alten Umgebung:** Der Dienst muss trotzdem starten und darf die Datei nicht lesen → Test in Task 5.
3. **Kernprozess ohne Teilprozesse oder außerhalb der Anfrage** muss wählbar sein, E5 bleibt auf die Anfrage begrenzt → Tests in Task 1 (KP-03 bei Mandant B ohne Teilprozesse) und Task 4 (Dienst: B4 nimmt KP-02, E5 nimmt `KP-02.TP-1` nicht).
4. **Testprofil-Antworten gegen die neue Auswahl:** Die drei Fälle antworten `KP-05`/`KP-06` und müssen gültig bleiben → Task 4 (offline und gegen DB).
5. **Übrig gebliebene Snapshot-Übergabe an `create_app`:** Die beiden vorhandenen Test-Doubles sind tolerant (`tests/test_api_profil.py:443` mit `snapshot=None`, `:494` mit `*a, **kw`) und würden sie verdecken → Task 5 Step 1: neuer Geschwistertest mit strengem Double. Die beiden toleranten bleiben bewusst stehen; ein Umbau bei Grün wäre gegen die Guard-Lessons.

---

### Task 1: Lesepfad `kernprozesse`

**Files:**
- Modify: `bc1_service/bc0_lesepfade.py` (neue Funktion nach `rollen`)
- Test: `tests/test_bc0_lesepfade.py`, `tests/test_bc0_lesepfade_aktiv.py`

**Interfaces:**
- Produces: `bc0_lesepfade.kernprozesse(conn, company_id: str) -> list[tuple[str, str]]` — `(process_id, process_name)` der aktiven Kernprozesse des Mandanten, nach ID sortiert.

- [ ] **Step 1: Failing test** in `tests/test_bc0_lesepfade.py` (Fixture: A hat KP-01 „Auftrag A", KP-02 „Einkauf A"; B zusätzlich KP-03 „Nur bei B", ohne Teilprozesse):

```python
def test_kernprozesse_liefern_nur_den_eigenen_mandanten():
    # Gleiche IDs, andere Namen: ein fehlender company_id-Filter faellt sofort auf.
    # KP-03 hat bei B keinen Teilprozess und gehoert trotzdem in die Auswahl (Spec 9.2).
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.kernprozesse(conn, MANDANT_A) == [
            ("KP-01", "Auftrag A"), ("KP-02", "Einkauf A")]
        assert bc0_lesepfade.kernprozesse(conn, MANDANT_B) == [
            ("KP-01", "Auftrag B"), ("KP-02", "Einkauf B"), ("KP-03", "Nur bei B")]
```

- [ ] **Step 2:** Voller Lauf mit DB → RED (`AttributeError: … has no attribute 'kernprozesse'`).
- [ ] **Step 3:** Funktion anlegen. Lehnt der Guard die volle Abfrage ab, erst einen Rückgabe-Stub `[]` (Assertion-RED), dann die Abfrage aus den Global Constraints. Docstring: aktive Kernprozesse; die Sicht filtert `aktiv`.
- [ ] **Step 4:** Voller Lauf mit DB → GREEN.
- [ ] **Step 5: Zweiter Test** in `tests/test_bc0_lesepfade_aktiv.py` (eigene frische DB wie die Nachbartests):

```python
def test_stillgelegter_kernprozess_fehlt_in_der_kernprozessliste():
    frische_db(DSN)
    _stilllegen("ref_prozesse", "process_id", "KP-02")
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.kernprozesse(conn, MANDANT_A) == [("KP-01", "Auftrag A")]
```

- [ ] **Step 6:** Voller Lauf mit DB → GREEN. Grün bei Ankunft ist hier richtig, denn die Sicht filtert.
- [ ] **Step 7: Commit** `feat(bc1): Lesepfad kernprozesse aus v_prozesse_lesen (B8)`.

*Sortierung (Prüfer M12):* Die Testdaten fügen KP-01 vor KP-02 ein; ein Wegfall von `ORDER BY` fiele nicht auf. *Ruling:* nicht eigens testen.
- Der Fingerabdruck sortiert die IDs selbst.
- Für die Auswahl ist die Reihenfolge nur Anzeige.
- `ORDER BY` steht wörtlich in den Global Constraints.

### Task 2: Startkontext trägt die Kernprozesse

**Files:**
- Modify: `bc1_service/discovery_paket.py` (`Bc0Kontext`), `bc1_service/start.py` (`lade_kontext`)
- Test: `tests/test_start.py`

**Interfaces:**
- Consumes: `bc0_lesepfade.kernprozesse` (Task 1).
- Produces: `Bc0Kontext.prozesse: tuple[tuple[str, str], ...] = ()` als **letztes** Feld, nach `eigner`. Kommentar: aktive Kernprozesse des Mandanten beim Laden; die IDs gehen in den Fingerabdruck ein, die Namen nicht. `lade_kontext` füllt es mit `tuple(bc0_lesepfade.kernprozesse(conn, company_id))`.

- [ ] **Step 1: Failing test** in `tests/test_start.py`:

```python
@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_start_laedt_alle_aktiven_kernprozesse_des_mandanten():
    # ANFRAGE_A umfasst nur KP-01-Teilprozesse; KP-02 gehoert trotzdem in die
    # B4-Auswahl (Spec 9.2: Zuordnung ausserhalb der Anfrage wird so sichtbar).
    frische_db(DSN)
    with verbindung(DSN) as conn:
        kontext = lade_kontext(conn, MANDANT_A, ANFRAGE_A)
    assert kontext.prozesse == (("KP-01", "Auftrag A"), ("KP-02", "Einkauf A"))
```

- [ ] **Step 2:** Voller Lauf mit DB → RED (`AttributeError: 'Bc0Kontext' object has no attribute 'prozesse'`).
- [ ] **Step 3:** Nur das Feld am Ende von `Bc0Kontext` ergänzen (Vorgabe `()`).
- [ ] **Step 4:** Voller Lauf mit DB → RED als Assertion (`() != (...)`).
- [ ] **Step 5:** `lade_kontext` füllt `prozesse=` (siehe Interfaces). Kein zusätzlicher Abbruch bei leerer Liste (Spec 9.9).
- [ ] **Step 6:** Voller Lauf mit DB → GREEN.
- [ ] **Step 7: Commit** `feat(bc1): Startkontext traegt die aktiven Kernprozesse (B8)`.

### Task 3: B4 und Fingerabdruck aus dem Kontext

**Files:**
- Modify: `bc1_service/discovery_paket.py` (Kontext-Zweig von `baue_discovery_paket`), `bc1_service/profil_writer.py` (nur Kommentar)
- Test: `tests/test_discovery_paket.py`, `tests/test_api.py`, `tests/test_profil_bau.py`

**Interfaces:**
- Consumes: `Bc0Kontext.prozesse` (Task 2).
- Produces: Im Kontext-Zweig kommen B4-Typ, B4-Frage und die KP-IDs für `_ctx_fingerprint` **nur** aus `kontext.prozesse`.
  - Liste nicht leer: `AUSWAHL` der IDs und die Frage „Zu welchem Ihrer Kernprozesse gehört das? (KP-01 = Name, …)", wie bisher mit Datei.
  - Liste leer: Freitext.
  - Der Parameter `prozesse` bleibt in dieser Task stehen (Task 4 entfernt ihn), wird im Kontext-Zweig aber nicht mehr gelesen.

Testkontext für diese Task, oben bei `KONTEXT` in `tests/test_discovery_paket.py`:

```python
KONTEXT_KP = replace(KONTEXT, prozesse=(("KP-01", "Auftrag"), ("KP-02", "Einkauf")))
```

- [ ] **Step 1: Failing test:**

```python
def test_b4_im_kontext_ist_auswahl_der_kernprozesse():
    spec = _feld(baue_discovery_paket(kontext=KONTEXT_KP), "process_id")
    assert spec.typ.validator("KP-02") is True
    assert spec.typ.validator("KP-03") is False
    assert spec.typ.normalisiere("kp-02") == "KP-02"
    assert "KP-01 = Auftrag" in spec.question
```

- [ ] **Step 2:** Voller Lauf → RED (B4 ist im Kontext-Zweig noch Freitext).
- [ ] **Step 3 (3a):** **Nur** B4-Typ und B4-Frage im Kontext-Zweig auf `kontext.prozesse` umstellen. Der Fingerabdruck bleibt in diesem Schritt unverändert (Lesson „Over-implementation for the current failure stage").
- [ ] **Step 4:** Voller Lauf → GREEN.
- [ ] **Step 5: Leere Liste bleibt Freitext** (neuer Test, grün bei Ankunft; er fängt die Mutation „leere Liste → `AUSWAHL()` ohne Optionen"):

```python
def test_b4_im_kontext_ohne_kernprozesse_bleibt_freitext():
    assert _feld(baue_discovery_paket(kontext=KONTEXT), "process_id").typ.name == "freitext"
```

- [ ] **Step 6: Failing test** für den Fingerabdruck:

```python
def test_kennung_mit_kernprozessen_wie_bisher_mit_datei():
    # Gleiche KP-IDs ergeben dieselbe Kennung wie frueher der Snapshot-Weg (Spec 2).
    kontext = replace(KONTEXT, prozesse=(("KP-01", "Auftrag"),))
    assert baue_discovery_paket(kontext=kontext).schema_version == "1.2+ctx-9e81785de2c8b1d8"
```

  Lauf → RED (`…0a6cdaacdfde28de` ≠ `…9e81785de2c8b1d8`).
- [ ] **Step 7 (3b):** Die KP-IDs für `_ctx_fingerprint` im Kontext-Zweig aus `kontext.prozesse` nehmen. Lauf: Der neue Test ist grün, `test_kp_liste_bleibt_teil_der_paket_identitaet` ist jetzt rot (der Parameter wird nicht mehr gelesen).
- [ ] **Step 8:** In `test_kp_liste_bleibt_teil_der_paket_identitaet` nur das Aufrufargument umstellen: `baue_discovery_paket(kontext=replace(KONTEXT, prozesse=(("KP-01", "Auftrag"),)))`. Die Assertion bleibt. Lauf → GREEN.
- [ ] **Step 9: Kennung ohne Kernprozesse** (neuer Test, grün bei Ankunft):

```python
def test_kennung_ohne_kernprozesse_bleibt_wie_bisher():
    assert baue_discovery_paket(kontext=KONTEXT).schema_version == "1.2+ctx-0a6cdaacdfde28de"
```

- [ ] **Step 10: Eigenschaften des Fingerabdrucks** als neue Tests, einzeln, je ein Lauf (grün bei Ankunft):
  - **ID dazu/weg** ändert die Kennung: `KONTEXT_KP` gegen `replace(KONTEXT, prozesse=(("KP-01", "Auftrag"),))`.
  - **Umbenennung** ändert sie nicht: gleiche IDs, Name „Auftragsabwicklung" statt „Auftrag".
  - **Reihenfolge** ändert sie nicht: `KONTEXT_KP.prozesse[::-1]`.
  - **16 Hex-Zeichen:** `re.fullmatch(r"1\.2\+ctx-[0-9a-f]{16}", …)` für `KONTEXT_KP`.
- [ ] **Step 11: Paket-Guard im Kern**, zwei neue Tests, einzeln (grün bei Ankunft):

```python
def test_offene_sitzung_mit_anderer_kernprozess_liste_wird_abgelehnt():
    paket_a = baue_discovery_paket(kontext=KONTEXT_KP)
    paket_b = baue_discovery_paket(kontext=replace(KONTEXT, prozesse=(("KP-01", "Auftrag"),)))
    store = InMemoryStateStore()
    process_turn(store, FakeLLM(), paket_a, "s1", "m1", "hallo", company_id=MANDANT)
    with pytest.raises(PaketKonfliktError):
        process_turn(store, FakeLLM(), paket_b, "s1", "m2", "hallo", company_id=MANDANT)


def test_wiederholung_eines_abschluss_turns_passiert_eine_andere_kernprozess_liste():
    # Recovery (core.darf_recovery_replay): fertige Sitzung, bekannte Nachrichten-ID,
    # alte Versionsangabe — der geaenderte Fingerabdruck darf passieren (Spec 3).
    paket_a = baue_discovery_paket(kontext=KONTEXT_KP)
    paket_b = baue_discovery_paket(kontext=replace(KONTEXT, prozesse=(("KP-01", "Auftrag"),)))
    state = SessionState("s1", paket_a.schema_version, paket_name="discovery",
                         company_id=MANDANT, status=SessionStatus.FERTIG)
    state.processed_message_ids.add("m9")
    assert darf_recovery_replay(state, paket_b, "m9", paket_a.schema_version) is True
    state.status = SessionStatus.AKTIV
    assert darf_recovery_replay(state, paket_b, "m9", paket_a.schema_version) is False
```

  Imports: `SessionState`, `SessionStatus` aus `bc1_core.types`; `darf_recovery_replay` aus `bc1_core.core`.
- [ ] **Step 12: Paket-Guard an der API** (neuer Test in `tests/test_api.py`, grün bei Ankunft):
  - In `tests/test_api.py` einen eigenen Kontext mit Kernprozessen anlegen (`Bc0Kontext` mit zwei Kernprozessen); **nicht** aus `tests.test_discovery_paket` importieren, sonst würde das Testmodul doppelt geladen.
  - `create_app` mit dem Paket aus diesem Kontext.
  - Ein Turn mit der `schema_version` eines Pakets mit anderer Kernprozess-Liste ergibt 409 und `detail == "schema_version_passt_nicht"`.
- [ ] **Step 13: Befund bei ungelöstem B4** in `tests/test_profil_bau.py` (neuer Test, grün bei Ankunft):

```python
def test_ungeloestes_b4_erzeugt_keinen_diskrepanz_befund():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         process_id=("KP-02", FieldStatus.UNGELOEST)))
    assert "kp_tp_diskrepanz" not in inhalt.profil["befunde"]
```

  Danach, bei grüner Suite und nur Kommentare:
  - In `test_freitext_kernprozess_erzeugt_keinen_diskrepanz_befund` (`tests/test_profil_bau.py`): Freitext gibt es nur noch im Minimalkontext und im kontextfreien Zweig; `BC1_SNAPSHOT_PFAD` nicht mehr erwähnen.
  - In `profil_writer.py` vor `interview_kp` (Zeilen ~165–168): ohne Kernprozess-Liste ist das Feld Freitext.
- [ ] **Step 14: Commit** `feat(bc1): B4-Auswahl und Fingerabdruck aus dem Startkontext (B8)`.

### Task 4: Parameter `prozesse` entfällt, `kontext` nur per Name; Dienst und Werkzeug

**Files:**
- Modify: `bc1_service/discovery_paket.py`, `bc1_service/paket_wahl.py`, `bc1_service/main.py` (nur der `waehle_paket`-Aufruf und `_prozesse`)
- Test: `tests/test_discovery_paket.py`, `tests/test_paket_wahl.py`, `tests/test_demo_durchlaeufe.py`, `tests/test_api_profil.py`, `tests/test_use_case_testprofile.py`

**Interfaces:**
- Produces:
  - `baue_discovery_paket(*, kontext: Bc0Kontext | None = None) -> UseCasePackage`;
  - `waehle_paket(umgebung: Mapping[str, str], *, kontext: Bc0Kontext | None = None) -> UseCasePackage`.
  - Die kontextfreie Variante `1.0+kp-…` gibt es nicht mehr; ohne Kontext gilt `1.0`, und B4 ist Freitext.

- [ ] **Step 1: Failing tests**, einzeln, je ein Lauf:

```python
def test_fabrik_nimmt_keine_prozessliste_mehr():          # tests/test_discovery_paket.py
    with pytest.raises(TypeError, match=r"baue_discovery_paket\(\) takes 0 positional"):
        baue_discovery_paket([("KP-01", "X")])


def test_paketwahl_nimmt_keine_prozessliste_mehr():       # tests/test_paket_wahl.py
    # match: sonst waere der Test auch gruen, wenn erst der innere Aufruf in
    # waehle_paket scheitert.
    with pytest.raises(TypeError, match=r"waehle_paket\(\) takes 1 positional"):
        waehle_paket({}, [("KP-01", "Angebotserstellung")])
```

- [ ] **Step 2:** Lauf → RED (kein `TypeError`).
- [ ] **Step 3: Signaturen** nach Interfaces. Mit ihnen entfallen:
  - der `if prozesse`-Pfad im kontextfreien Zweig samt Kommentar;
  - im Docstring von `baue_discovery_paket` die Erwähnung des Snapshots;
  - der Kommentar in `_ctx_fingerprint` (Zeilen ~63–67), der auf den „B4-Fingerprint unten" und den „BC0-Snapshot" verweist. Der Satz „nur die IDs, nicht die Namen" bleibt sinngemäß.
- [ ] **Step 4:** Lauf **mit DB**. Jetzt sind die Aufrufer rot. Erst die Aufrufargumente nachziehen, in dieser Reihenfolge:
  - **`main.py`:** `waehle_paket(os.environ, kontext=_kontext)`. Die Zuweisung `_prozesse` entfällt, weil sie erst durch diese Änderung ungenutzt wird. `_snapshot` bleibt bis Task 5.
  - **`tests/test_demo_durchlaeufe.py`:** `baue_discovery_paket()` statt `baue_discovery_paket(None)`.
  - **`test_paket_metadaten`:** Die Zeile mit `baue_discovery_paket([])` und ihr Kommentar entfallen; die Kennung `1.0` ohne Kontext prüft der Test schon oben.
  - **`test_b4_ohne_snapshot_ist_freitext`:** umbenennen in `test_b4_ohne_kontext_ist_freitext`, Aufruf `baue_discovery_paket()`.
  - **Rote Snapshot-Tests entfernen:** `test_b4_mit_snapshot_wird_auswahl_ueber_die_ids`, `test_b4_snapshot_fingerprint_in_schema_version`, `test_b4_fingerprint_haengt_nur_von_den_prozess_ids_ab`, `test_b4_snapshot_wechsel_wird_vom_bestehenden_paket_guard_abgelehnt` und `test_b4_leere_snapshot_liste_ist_ebenfalls_freitext`. Ihre Eigenschaften belegen jetzt die Tests aus Task 3 (Steps 1, 5, 6, 9–11). Die alten Kollisionsbeispiele galten für die Eingabeform `repr(sorted(ids))` und beweisen für den Kontext-Fingerabdruck nichts (Spec 2).
  - **`tests/test_paket_wahl.py`:** `test_prozessliste_wird_an_die_fabrik_durchgereicht` entfällt; Ersatz ist der neue TypeError-Test zusammen mit dem bestehenden `test_kontext_wird_an_die_fabrik_durchgereicht`.

  Lehnt der Guard das Entfernen eines Tests ab: Skill `tdd-guard`, nicht umgehen.
- [ ] **Step 5:** Voller Lauf mit und ohne DB → GREEN.
- [ ] **Step 6: Dienst baut B4 aus der DB** — ein **neuer Geschwistertest** in `tests/test_api_profil.py`, gleich aufgebaut wie `test_main_verdrahtet_den_profil_writer` (Zeile ~432; `main` mit gestubbtem `create_app` gegen die Gerüst-DB importieren). Kein Eingriff in den Bestandstest. Grün bei Ankunft, denn `main` übergibt seit Step 4 den Kontext. Assertionen:

```python
    paket = gesehen["package"]
    b4 = paket.field("process_id").typ
    assert b4.validator("KP-02") is True and b4.validator("KP-03") is False
    e5 = paket.field("focus_step").typ          # E5 bleibt auf ANFRAGE_A begrenzt
    assert e5.validator("KP-01.TP-1") is True and e5.validator("KP-02.TP-1") is False
```

  Testname: `test_main_baut_b4_aus_den_kernprozessen_des_mandanten`.
- [ ] **Step 7: Werkzeug offline.** In `tests/test_use_case_testprofile.py` ein neuer Testkontext neben `KONTEXT`; `KONTEXT` selbst bleibt unverändert (Fixture-Umbau bei Grün):

```python
KONTEXT_KP = dataclasses.replace(KONTEXT, prozesse=(("KP-05", "Wissen"), ("KP-06", "Personal")))
```

  Dazu ein neuer Test `test_jeder_fall_endet_mit_kernprozess_auswahl_fertig_und_b4_gueltig`: Er führt alle drei Fälle mit `baue_discovery_paket(kontext=KONTEXT_KP)` durch, wie `_antworten()`, und prüft:
  - `status == "fertig"`;
  - `vollstaendigkeit == 1.0`;
  - `payload["felder"]["process_id"]["status"] == "gueltig"`.

  Lauf → GREEN.
- [ ] **Step 8: Werkzeug gegen DB, Parität mit dem Dienst** (neuer Test, Fixture `pool` wie die Nachbartests; `waehle_paket` neu importieren):

```python
def test_werkzeug_schreibt_mit_derselben_paketkennung_wie_der_dienst(pool):
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    for fall in FAELLE:
        with pool.connection() as conn:
            kontext = lade_kontext(conn, MANDANT_A, ANFRAGEN[fall.fokus_tp])
        assert kontext.prozesse                               # Liste kommt aus der DB
        dienst = waehle_paket({}, kontext=kontext)            # Weg des Dienstes
        with verbindung(DSN) as conn:
            zeile = conn.execute(
                "SELECT paket_version, profil->'felder'->'process_id'->>'status', "
                "       profil->'befunde' ? 'kp_tp_diskrepanz' "
                "  FROM bc1.prozessprofil WHERE focus_step_id = %s",
                (fall.fokus_tp,)).fetchall()
        assert zeile == [(dienst.schema_version, "gueltig", False)]
```

  (`_zeilen` nimmt keine Parameter, deshalb die Verbindung direkt. psycopg 3 behandelt `?` nicht als Platzhalter; `befunde` ist immer ein Objekt.)
- [ ] **Step 9:** Voller Lauf mit DB → GREEN.
- [ ] **Step 10: Commit** `refactor(bc1): Paket nur noch aus dem Kontext — Parameter prozesse entfaellt (B8)`.

### Task 5: Dienst ohne Snapshot, `GET /prozesse` entfällt

**Files:**
- Modify: `bc1_service/api.py`, `bc1_service/main.py` (Aufruf, Snapshot-Zeilen, Kopf-Docstring)
- Delete: `bc1_service/snapshot.py`, `bc1_service/snapshot_schema.json`, `tests/test_snapshot.py`
- Test: `tests/test_api.py`, `tests/test_api_profil.py`

**Interfaces:**
- Produces: `create_app(store, llm, package, lifespan=None, *, company_id, anfrage_id=None, writer=None, melder=None) -> FastAPI` ohne `snapshot` und ohne Route `/prozesse`.

- [ ] **Step 1: Failing test, strenges Double** — neuer Geschwistertest in `tests/test_api_profil.py`, gleich aufgebaut wie `test_main_verdrahtet_den_profil_writer`, aber mit `_stub(store, llm, package, *, lifespan=None, **kw)`. Name: `test_main_uebergibt_create_app_keine_weiteren_positionsargumente`. Assertion: Der Import gelingt, und `lifespan` ist gesetzt.
- [ ] **Step 2:** Lauf mit DB → RED (`TypeError: … takes 3 positional arguments but 4 were given`; `main` übergibt heute `_snapshot` positional).
- [ ] **Step 3:** In `main.py` entfällt im `create_app`-Aufruf das vierte Positionsargument `_snapshot`. Lauf mit DB → GREEN. Das Laden des Snapshots (`_snapshot_pfad`, `_snapshot`) bleibt bis Step 10 stehen.
- [ ] **Step 4: Failing test** in `tests/test_api.py`:

```python
def test_prozesse_gibt_es_nicht_mehr():
    client = _client()
    assert "/prozesse" not in client.app.openapi()["paths"]
    antwort = client.get("/prozesse")
    assert antwort.status_code == 404
    assert antwort.json() == {"detail": "Not Found"}
```

- [ ] **Step 5:** Lauf → RED. Dann die Route `/prozesse` aus `create_app` entfernen. Lauf: Der neue Test ist grün, `test_kein_snapshot_bleibt_ohne_chat_text` ist rot.
- [ ] **Step 6: P3-Zusage neu belegen** (neuer Test, grün bei Ankunft; Import `from fastapi import HTTPException` ergänzen):

```python
def test_unbekannter_fehlerschluessel_geht_ohne_chat_text_durch():
    app = create_app(InMemoryStateStore(), _fake_llm(), TOY_PROZESS, company_id=MANDANT)

    @app.get("/test-unbekannt")
    def _wirft():
        raise HTTPException(status_code=418, detail="unbekannter_schluessel")

    antwort = TestClient(app).get("/test-unbekannt")
    assert antwort.status_code == 418
    assert antwort.json() == {"detail": "unbekannter_schluessel"}
```

  Danach entfallen der rote `test_kein_snapshot_bleibt_ohne_chat_text` und der überholte `test_prozesse_ohne_snapshot_404`; Letzteren ersetzt `test_prozesse_gibt_es_nicht_mehr`.
- [ ] **Step 7:** Parameter `snapshot` aus `create_app` entfernen. Das ist Refactoring bei grüner Suite, denn kein Aufrufer übergibt ihn mehr. Lauf mit und ohne DB → GREEN.
- [ ] **Step 8: Failing test, alte Variable wirkungslos** — neuer Geschwistertest mit dem Aufbau aus Step 1: `monkeypatch.setenv("BC1_SNAPSHOT_PFAD", "/gibt/es/nicht.json")`; der Import von `main` muss gelingen. Name: `test_main_startet_trotz_alter_snapshot_variable`.
- [ ] **Step 9:** Lauf mit DB → RED (`FileNotFoundError` aus `lade_snapshot`).
- [ ] **Step 10:** In `main.py` entfallen der Import von `lade_snapshot`, `_snapshot_pfad` und `_snapshot`. Im Kopf-Docstring entfällt die Zeile zu `BC1_SNAPSHOT_PFAD`; dazu kommt ein Satz (Spec 6): „uvicorn ohne `--host` lauscht nur auf dem eigenen Rechner; so betreiben (oder im Container nur an 127.0.0.1 veröffentlichen), bis es eine Zugangsprüfung gibt." Lauf mit DB → GREEN.
- [ ] **Step 11: Dateien löschen** (Global Constraints):
  1. `grep -rnI --exclude-dir=__pycache__ "bc1_service.snapshot\|lade_snapshot" bc1_service bc1_core tests` → kein Treffer.
  2. **Per Edit leeren:** erst `tests/test_snapshot.py` (alle drei Tests), dann `bc1_service/snapshot.py`. Lehnt der Guard ab, die umgekehrte Reihenfolge versuchen: Erst das leere Modul macht die Tests rot (ImportError), dann ist das Entfernen roter Tests erlaubt. Hält der Guard beide Wege an: Skill `tdd-guard`; findet sich kein guard-konformer Weg, anhalten und der BC1-Projektleitung vorlegen.
  3. `git rm bc1_service/snapshot.py bc1_service/snapshot_schema.json tests/test_snapshot.py`. Das sind jetzt nur noch leere Dateien und die JSON-Datei.
  4. Voller Lauf mit und ohne DB → GREEN.
  5. Ist das Verfahren aus Punkt 2 neu für den Guard, kommt es als Lesson in den Skill `tdd-guard`.
- [ ] **Step 12: Commit** `feat(bc1): GET /prozesse und Snapshot-Modus entfallen (B8)`.

### Task 6: Abhängigkeit, Betrieb, Doku, Roadmap

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `.dockerignore`, `Dockerfile` (Kommentar), `README.md`, `bc1_service/n8n/SMOKE.md`, `design/Abschlussplan-BC1.md`, `design/Spec-B8-Snapshot-abloesen.md` (Kopf, Messergebnis)
- Lokal, nicht im Repo: Meldungsentwurf in `AutoCoE_Projekt/`

- [ ] **Step 1: `jsonschema` von `service` nach `dev`**, in dieser Reihenfolge, damit das Paket durchgehend im Lock bleibt:

```bash
uv add --raw --group dev jsonschema
uv remove --group service jsonschema
```

  `git diff pyproject.toml uv.lock` lesen. Erwartet:
  - In `pyproject.toml` wandert der nackte Name `jsonschema` von `service` nach `dev`, ohne Untergrenze.
  - In `uv.lock` ändern sich nur die Abschnitte `[package.dev-dependencies]` und `[package.metadata.requires-dev]` von `bc1-core`.
  - Keine andere Paketversion ändert sich (`jsonschema` 4.26.0, `attrs`, `referencing`, `rpds-py` und `jsonschema-specifications` bleiben, wie sie sind).
  - Weicht es ab: `git checkout -- pyproject.toml uv.lock` und anhalten.
- [ ] **Step 2: Abnahme der Abhängigkeiten:**
  - `uv export --frozen --no-dev --group service | grep -c jsonschema` → `0`.
  - `.venv/bin/pytest -v -k test_paket_metadaten 2>&1 | grep '^plugins:'` → die Zeile enthält `tdd-guard-pytest`.
  - Aus `coe-factory/`: `bc1-context-discovery/.venv/bin/python bc2-strategic-advisor/tools/validate.py` → grün.
- [ ] **Step 3: `.dockerignore`:** Die Zeile `!bc1_service/snapshot_schema.json` entfällt; `**/*snapshot*.json` bleibt; der Kopfkommentar ist unverändert.
- [ ] **Step 4: `Dockerfile`:**
  - Im Kommentar vor `CMD` entfällt der Satzteil zum Snapshot.
  - Neu dazu: „Den Port nur an 127.0.0.1 veröffentlichen (README), solange der Dienst keine Zugangsprüfung hat."
  - Der Kommentar „Snapshots … bleiben draussen" bei `COPY` bleibt.
- [ ] **Step 5: `README.md`:**
  - Container-Start mit `-p 127.0.0.1:8000:8000`.
  - Test-Postgres mit `-p 127.0.0.1:55432:5432`.
  - Der Satz zum Snapshot-Mount entfällt.
  - Ein Satz zur Betriebsvoraussetzung (Spec 6): nur auf dem eigenen Rechner oder im internen Docker-Netz erreichbar, bis es eine Zugangsprüfung gibt.
  - `grep -n BC1_SNAPSHOT_PFAD README.md` → kein Treffer.
- [ ] **Step 6: `SMOKE.md`:**
  - Die **ausführbare** Demo-Verdrahtung im Abschnitt „Ohne Claude-Key" (Zeilen ~103–140): Import von `lade_snapshot`, `_snapshot_pfad` und das vierte Positionsargument entfallen.
  - Der Anleitungsschritt mit `BC1_SNAPSHOT_PFAD` (Zeile ~306) wird ersetzt durch „B4 kommt aus der DB (`v_prozesse_lesen`)".
  - **Protokolle vergangener Läufe bleiben stehen** (~244–250, ~323–325, ~395, ~496), höchstens mit dem Zusatz „(seit B8 entfallen)" (Spec 6).
- [ ] **Step 7: Messung — nur mit OK der BC1-Projektleitung, weil sie Container startet. Vom Ergebnis hängt der Merge ab.**
  1. Image bauen. Den Dienst mit `-p 127.0.0.1:8000:8000`, `BC1_BC0_MELDUNGEN=aus` und `BC1_LLM=ollama` gegen die Test-DB starten, mit einer interviewbaren Gerüst-Anfrage.
  2. **Aus dem echten n8n-Container:** `docker exec n8n wget -qO- http://host.docker.internal:8000/gesundheit` → JSON mit `"status": "ok"`.
  3. **Container → Test-DB bei Loopback-Bindung** (der README-Weg „Datenbank auf dem eigenen Rechner unter `host.docker.internal`"): Test-Postgres testweise mit `-p 127.0.0.1:55432:5432`, dann aus einem Container `pg_isready -h host.docker.internal -p 55432` → „accepting connections".
  4. **Ergebnis** in Spec Abschnitt 5 und ins README.
  5. **Scheitert 2 oder 3:** den Weg über ein gemeinsames Docker-Netz ohne veröffentlichten Port beschreiben und der BC1-Projektleitung vorlegen, vor dem Merge.
- [ ] **Step 8: `Abschlussplan-BC1.md`:**
  - B8-Zeile: erledigt (Spec, Plan, Zweig). **Dazu die Vorbedingung der Auslieferung** (Spec, Big Picture): Unmittelbar vor dem Neustart mit B8 werden M1–M3 neu gemessen und müssen 0 sein; bis zum Wechsel laufen weder der alte Dienst noch das Testprofil-Werkzeug; beim Rückfall gilt dasselbe. Ziel: Neustart mit B8. Querverweis bei „Neu 24.10." (4a).
  - B3 (d): erledigt durch Streichen.
  - Kleinpunkt „Snapshot-Modus filtert `aktiv` nicht": erledigt, seit 23.09. ohnehin gegenstandslos.
  - **Neuer Roadmap-Punkt unter B3 Teil 2:** Zugangsprüfung des Dienstes, wörtlich aus Spec 6.
  - (4e) um `kp_tp_diskrepanz` ergänzen.
  - (4g) um „B4: Antwort mit Namen statt ID" ergänzen (Review Focus 1).
  - „Nächstes Go" nachziehen.
- [ ] **Step 9: Spec-Kopf:** „Entwurf 2, abgenommen 24.10.2026 (einschließlich 9.2–9.10)", dazu das Messergebnis aus Step 7.
- [ ] **Step 10: Meldungsentwürfe lokal**, nicht posten: `AutoCoE_Projekt/Entwurf-Kommentar-B8-265-206-286.md` mit drei kurzen Abschnitten:
  - **#265:** Haken entfällt.
  - **BC0 (#206):** Snapshot wird nicht mehr gelesen; Hinweis auf ADR-003.
  - **BC2 (#286):** ein Satz zu `ungeloeste_felder`.
- [ ] **Step 11: Commit** `docs(bc1): B8 — Abhaengigkeit, Betrieb (127.0.0.1), README, SMOKE, Abschlussplan`.

### Task 7: Gesamtabnahme

- [ ] **Step 1: Volle Suite.** Rechnung: 24 neue und 11 entfernte Tests.
  - Entfernt: 5 in `test_discovery_paket.py`, 1 in `test_paket_wahl.py`, 2 in `test_api.py`, 3 in `test_snapshot.py`.
  - Davon 7 neue mit DB: Task 1 zwei, Task 2 einer, Task 4 zwei, Task 5 zwei.
  - **Erwartet mit DB 820 passed / 4 skipped, ohne DB 556 / 268.** Die tatsächlichen Zahlen nennen und jede Abweichung erklären.
- [ ] **Step 2: Reste suchen** (aus `bc1-context-discovery/`):
  - `grep -rnI --exclude-dir=__pycache__ --exclude-dir=.venv "BC1_SNAPSHOT_PFAD\|lade_snapshot\|kein_snapshot_konfiguriert\|/prozesse" bc1_service bc1_core tests README.md Dockerfile .dockerignore` → nur erklärbare Treffer (historische SMOKE-Protokolle).
  - `git grep -n snapshot -- bc1_service` → nur `SMOKE.md`-Protokolle.
- [ ] **Step 3: Gegenproben.** Jede Probe muss mindestens einen Test rot machen; keine Projektdatei wird geändert.
  1. `bc0_lesepfade.kernprozesse` ohne Mandantenfilter (liefert A ∪ B) — Mini-Plugin im Scratchpad (Lesson 07.10., Weg 1).
  2. `_ctx_fingerprint` bekommt immer `[]` als KP-Liste — Mini-Plugin, das `_ctx_fingerprint` umhüllt.
  3. B4 im Kontext-Zweig immer Freitext. Die Stelle liegt in der Funktion, ein Monkeypatch reicht also nicht. Deshalb das Kopie-Verfahren: Arbeitskopie des Pakets im Scratchpad, dort ändern, Suite mit `PYTHONPATH` auf die Kopie laufen lassen.
- [ ] **Step 4:** Ins Ledger und in den Bericht an die BC1-Projektleitung:
  - Suite, Abnahme aus Task 6 Step 2, Gegenproben;
  - Messung aus Task 6 Step 7 (oder „nicht freigegeben");
  - neue Guard-Lessons.

  Kein Push und kein Merge ohne OK.
