# B8 — Snapshot-Modus ablösen, `GET /prozesse` streichen: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Kernprozess-Auswahl (B4) kommt aus BC0s Sicht `v_prozesse_lesen` statt aus einer Datei; Snapshot-Modul, `BC1_SNAPSHOT_PFAD` und `GET /prozesse` entfallen; der Docker-Start bindet nur an `127.0.0.1`.

**Architecture:** Ein neuer Lesepfad `kernprozesse` füllt beim Start das neue Feld `Bc0Kontext.prozesse`. Das Discovery-Paket nimmt B4-Auswahl und Fingerabdruck nur noch aus dem Kontext. Der Parameter `prozesse` der Paket-Fabriken entfällt, `kontext` wird Schlüsselwort-Parameter. Dienst und Testprofil-Werkzeug bekommen die Liste so ohne eigene Verdrahtung.

**Tech Stack:** Python 3.11, psycopg 3, FastAPI, pytest, uv. Test-Postgres im Container `bc1-test-pg`.

**Spec:** `bc1-context-discovery/design/Spec-B8-Snapshot-abloesen.md` (Entwurf 2, abgenommen 24.10.2026 einschließlich 9.2–9.10)

## Global Constraints

- **TDD-Guard nie umgehen.** `*.py` unter `coe-factory/` NUR mit Edit/Write/MultiEdit ändern; Bash nur für pytest, git und Messungen. Wer per Bash schreibt, umgeht den Guard. Bei einem Block: Skill `tdd-guard` aufrufen; jeder NEU gelöste Block kommt dort in die Lessons-Tabelle.
- **Einzige Ausnahme, ausdrücklich:** ganze Dateien löschen (Task 5) geht nur mit `git rm`, weil kein Guard-Werkzeug Dateien löscht. Voraussetzungen: Suite grün, ein grep belegt, dass kein Code das Modul mehr importiert, Modul und Test im selben Schritt; danach voller Lauf grün.
- **pytest** immer aus `bc1-context-discovery/`:
  - mit DB: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`;
  - ohne DB dasselbe ohne die Variable.
  - Stand auf `main` @ `b0071f3`: mit DB 807 passed / 4 skipped, ohne DB 550 / 261.
- **Paketfassung bleibt `1.2`** (`SCHEMA_VERSION_CTX`); die kontextfreie bleibt `1.0`.
- **Feste Kennungen** (mit dem Testkontext `KONTEXT` aus `tests/test_discovery_paket.py`, gemessen auf `b0071f3`):
  - leere Kernprozess-Liste → `1.2+ctx-0a6cdaacdfde28de`;
  - Liste `(("KP-01", "Auftrag"),)` → `1.2+ctx-9e81785de2c8b1d8`.
- **Unverändert:** `contracts/`, `bc1_service/db/*.sql` (DDL, Signaturen), Gerüst-Rechte, `bc1_core/`.
- **SQL des Lesepfads wörtlich:** `SELECT process_id, process_name FROM v_prozesse_lesen WHERE company_id = %s ORDER BY process_id`.
- **Keine Mandantendaten, keine Zugangsdaten** in Commits; das Repo ist öffentlich. Kein Push ohne OK der BC1-Projektleitung.
- Commits auf Zweig `bc1-b8-snapshot-abloesen`, Nachrichten auf Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Antwort mit Namen statt ID** („Logistik"): Ob der Extraktor den Namen auf die ID abbildet, zeigen FakeLLM-Tests nicht. Kein Offline-Test möglich; Live-Bewertung beim Lauf von Version 3 bzw. beim Durchstich, wie Abschlussplan (4g). Wird im Abschlussplan unter (4g) ergänzt (Task 6).
2. **`BC1_SNAPSHOT_PFAD` steht noch in einer alten Umgebung:** Der Dienst muss trotzdem starten und darf die Datei nicht lesen → Test in Task 5 (gesetzt auf einen nicht existierenden Pfad, Start gelingt).
3. **Kernprozess ohne Teilprozesse oder außerhalb der Anfrage** muss wählbar sein → Tests in Task 1 (KP-03 bei Mandant B hat keine Teilprozesse) und Task 2 (KP-02 liegt außerhalb von `ANFRAGE_A`).
4. **Testprofil-Antworten gegen die neue Auswahl:** Die drei Fälle antworten `KP-05`/`KP-06` und müssen gültig bleiben → Task 4 (Offline-Fixture mit Kernprozessen, DB-Lauf prüft Status `gueltig` und keinen Befund).
5. **Übrig gebliebene Snapshot-Übergabe an `create_app`:** Ein tolerantes Test-Double würde sie verdecken → Task 5 macht das Double streng (nur `lifespan` per Name).

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
- [ ] **Step 3:** Funktion anlegen. Lehnt der Guard die volle SQL ab, erst ein Rückgabe-Stub `[]` (Assertion-RED), dann die Abfrage aus den Global Constraints. Docstring: aktive Kernprozesse; die Sicht filtert `aktiv`.
- [ ] **Step 4:** Voller Lauf mit DB → GREEN.
- [ ] **Step 5: Zweiter Test** in `tests/test_bc0_lesepfade_aktiv.py` (eigene frische DB wie die Nachbartests):

```python
def test_stillgelegter_kernprozess_fehlt_in_der_kernprozessliste():
    frische_db(DSN)
    _stilllegen("ref_prozesse", "process_id", "KP-02")
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.kernprozesse(conn, MANDANT_A) == [("KP-01", "Auftrag A")]
```

- [ ] **Step 6:** Voller Lauf mit DB → GREEN (grün bei Ankunft ist hier richtig: die Sicht filtert).
- [ ] **Step 7: Commit** `feat(bc1): Lesepfad kernprozesse aus v_prozesse_lesen (B8)`.

### Task 2: Startkontext trägt die Kernprozesse

**Files:**
- Modify: `bc1_service/discovery_paket.py` (`Bc0Kontext`), `bc1_service/start.py` (`lade_kontext`)
- Test: `tests/test_start.py`

**Interfaces:**
- Consumes: `bc0_lesepfade.kernprozesse` (Task 1).
- Produces: `Bc0Kontext.prozesse: tuple[tuple[str, str], ...] = ()` als **letztes** Feld, nach `eigner`. Kommentar: aktive Kernprozesse des Mandanten beim Laden; IDs gehen in den Fingerabdruck ein, Namen nicht. `lade_kontext` füllt es mit `tuple(bc0_lesepfade.kernprozesse(conn, company_id))`.

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
- [ ] **Step 4:** Voller Lauf → RED als Assertion (`() != (...)`).
- [ ] **Step 5:** `lade_kontext` füllt `prozesse=` (siehe Interfaces). Kein zusätzlicher Abbruch bei leerer Liste (Spec 9.9).
- [ ] **Step 6:** Voller Lauf mit DB → GREEN.
- [ ] **Step 7: Commit** `feat(bc1): Startkontext traegt die aktiven Kernprozesse (B8)`.

### Task 3: B4 und Fingerabdruck aus dem Kontext

**Files:**
- Modify: `bc1_service/discovery_paket.py` (`baue_discovery_paket`, Kontext-Zweig)
- Test: `tests/test_discovery_paket.py`, `tests/test_profil_bau.py`

**Interfaces:**
- Consumes: `Bc0Kontext.prozesse` (Task 2).
- Produces: Im Kontext-Zweig kommen B4-Typ, B4-Frage und die KP-IDs für `_ctx_fingerprint` **nur** aus `kontext.prozesse`. Ist die Liste nicht leer: `AUSWAHL` der IDs und die Frage „Zu welchem Ihrer Kernprozesse gehört das? (KP-01 = Name, …)", wie bisher mit Datei. Ist sie leer: Freitext. Der Parameter `prozesse` bleibt in dieser Task noch stehen (Task 4 entfernt ihn), wird im Kontext-Zweig aber nicht mehr gelesen.

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
- [ ] **Step 3:** Kontext-Zweig auf `kontext.prozesse` umstellen (siehe Interfaces).
- [ ] **Step 4:** Voller Lauf → GREEN. `test_kp_liste_bleibt_teil_der_paket_identitaet` übergibt die Liste noch per Parameter. Wird er rot, weil der Kontext-Zweig den Parameter nicht mehr liest, ist das der erwartete RED für Step 5.
- [ ] **Step 5: Kennungen festnageln.** Je einen Test hinzufügen, jeweils mit eigenem Lauf:

```python
def test_kennung_ohne_kernprozesse_bleibt_wie_bisher():
    assert baue_discovery_paket(kontext=KONTEXT).schema_version == "1.2+ctx-0a6cdaacdfde28de"


def test_kennung_mit_kernprozessen_wie_bisher_mit_datei():
    # Gleiche KP-IDs ergeben dieselbe Kennung wie frueher der Snapshot-Weg (Spec 2).
    kontext = replace(KONTEXT, prozesse=(("KP-01", "Auftrag"),))
    assert baue_discovery_paket(kontext=kontext).schema_version == "1.2+ctx-9e81785de2c8b1d8"
```

  `test_kp_liste_bleibt_teil_der_paket_identitaet` stellt den Aufruf auf `replace(KONTEXT, prozesse=(("KP-01", "Auftrag"),))` um, die Assertion bleibt. Erst das Aufrufargument ändern (Lesson 05.10.).
- [ ] **Step 6: Eigenschaften des Fingerabdrucks** als neue Tests, einzeln hinzufügen:
  - **ID dazu/weg** ändert die Kennung: `KONTEXT_KP` gegen `replace(KONTEXT, prozesse=(("KP-01", "Auftrag"),))`.
  - **Umbenennung** ändert sie nicht: gleiche IDs, Name „Auftragsabwicklung" statt „Auftrag".
  - **Reihenfolge** ändert sie nicht: `KONTEXT_KP.prozesse[::-1]`.
  - **16 Hex-Zeichen:** `re.fullmatch(r"1\.2\+ctx-[0-9a-f]{16}", …)` für `KONTEXT_KP`.
- [ ] **Step 7: Paket-Guard, zwei Wege im Kern** (der dritte, die API, folgt in Step 8):

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

  Imports: `SessionState`, `SessionStatus` aus `bc1_core.types`, `darf_recovery_replay` aus `bc1_core.core`.
- [ ] **Step 8: Paket-Guard, Weg 2 (API):** in `tests/test_api.py` ein neuer Test. `create_app` bekommt das Paket aus `KONTEXT_KP` (Kontext dort neu anlegen oder importieren). Ein Turn mit `schema_version` des Pakets mit anderer Kernprozess-Liste ergibt 409 und `detail == "schema_version_passt_nicht"`.
- [ ] **Step 9: Befund bei ungelöstem B4** in `tests/test_profil_bau.py`:

```python
def test_ungeloestes_b4_erzeugt_keinen_diskrepanz_befund():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         process_id=("KP-02", FieldStatus.UNGELOEST)))
    assert "kp_tp_diskrepanz" not in inhalt.profil["befunde"]
```

  Im Nachbartest `test_freitext_kernprozess_erzeugt_keinen_diskrepanz_befund` den Kommentar auf den neuen Stand bringen: Freitext gibt es nur noch im Minimalkontext und im kontextfreien Zweig; `BC1_SNAPSHOT_PFAD` nicht mehr erwähnen. Ebenso den Kommentar in `profil_writer.py` vor `interview_kp` (Zeilen ~165–168): ohne Kernprozess-Liste ist das Feld Freitext. Nur Kommentar, bei grüner Suite.
- [ ] **Step 10:** Steps 5–9 sind grün bei Ankunft, bis auf die Umstellung in Step 5. Nach jedem neuen Test ein voller Lauf, Tests einzeln hinzufügen (Lesson „Multiple test addition").
- [ ] **Step 11: Commit** `feat(bc1): B4-Auswahl und Fingerabdruck aus dem Startkontext (B8)`.

### Task 4: Parameter `prozesse` entfällt, `kontext` nur per Name; Werkzeug-Parität

**Files:**
- Modify: `bc1_service/discovery_paket.py`, `bc1_service/paket_wahl.py`, `bc1_service/main.py` (nur der `waehle_paket`-Aufruf und `_prozesse`)
- Test: `tests/test_discovery_paket.py`, `tests/test_paket_wahl.py`, `tests/test_demo_durchlaeufe.py`, `tests/test_api_profil.py` (Verdrahtungstest), `tests/test_use_case_testprofile.py`

**Interfaces:**
- Produces:
  - `baue_discovery_paket(*, kontext: Bc0Kontext | None = None) -> UseCasePackage`;
  - `waehle_paket(umgebung: Mapping[str, str], *, kontext: Bc0Kontext | None = None) -> UseCasePackage`.
  - Die kontextfreie Variante `1.0+kp-…` gibt es nicht mehr; ohne Kontext gilt `1.0`, und B4 ist Freitext.

- [ ] **Step 1: Failing tests**, einzeln, mit je einem Lauf:

```python
def test_fabrik_nimmt_keine_prozessliste_mehr():          # tests/test_discovery_paket.py
    with pytest.raises(TypeError):
        baue_discovery_paket([("KP-01", "X")])


def test_paketwahl_nimmt_keine_prozessliste_mehr():       # tests/test_paket_wahl.py
    with pytest.raises(TypeError):
        waehle_paket({}, [("KP-01", "Angebotserstellung")])
```

- [ ] **Step 2:** Lauf → RED (kein `TypeError`).
- [ ] **Step 3: Signaturen** nach Interfaces. Der `if prozesse`-Pfad im kontextfreien Zweig entfällt mit seinem Kommentar. Docstring von `baue_discovery_paket`: Snapshot nicht mehr erwähnen.
- [ ] **Step 4:** Lauf → jetzt sind die Aufrufer rot. Sie werden in dieser Reihenfolge nachgezogen, erst die Aufrufargumente:
  - **`main.py`:** `waehle_paket(os.environ, kontext=_kontext)`. Die Zuweisung `_prozesse` entfällt, weil sie erst durch diese Änderung ungenutzt wird; `_snapshot` bleibt bis Task 5.
  - **`tests/test_demo_durchlaeufe.py`:** `baue_discovery_paket()` statt `baue_discovery_paket(None)`.
  - **`test_paket_metadaten`:** Die Zeile mit `baue_discovery_paket([])` und ihr Kommentar entfallen; die Kennung `1.0` ohne Kontext prüft der Test schon oben.
  - **Snapshot-Tests:** `test_b4_mit_snapshot_wird_auswahl_ueber_die_ids`, `test_b4_snapshot_fingerprint_in_schema_version`, `test_b4_fingerprint_haengt_nur_von_den_prozess_ids_ab`, `test_b4_snapshot_wechsel_wird_vom_bestehenden_paket_guard_abgelehnt` und `test_b4_leere_snapshot_liste_ist_ebenfalls_freitext` entfallen. Ihre Eigenschaften belegen jetzt die Tests aus Task 3, Steps 1 und 5–7. Die alten Kollisionsbeispiele galten für die Eingabeform `repr(sorted(ids))` und beweisen für den Kontext-Fingerabdruck nichts (Spec 2).
  - **`test_b4_ohne_snapshot_ist_freitext`** wird umbenannt in `test_b4_ohne_kontext_ist_freitext` und ruft `baue_discovery_paket()` auf.
  - **`tests/test_paket_wahl.py`:** `test_prozessliste_wird_an_die_fabrik_durchgereicht` entfällt; Ersatz ist `test_paketwahl_nimmt_keine_prozessliste_mehr` zusammen mit dem bestehenden `test_kontext_wird_an_die_fabrik_durchgereicht`.

  Lehnt der Guard das Löschen eines Tests ab: Skill `tdd-guard` (Lesson „Ungeprüfter Implementierungsblock … entfernen"), nicht umgehen.
- [ ] **Step 5:** Voller Lauf mit und ohne DB → GREEN.
- [ ] **Step 6: Verdrahtung des Dienstes.** Im Test, der `bc1_service.main` mit gestubbtem `create_app` importiert (`tests/test_api_profil.py`, um Zeile 436), eine Assertion ergänzen. Er läuft gegen die Gerüst-DB, die Liste kommt also echt aus `lade_kontext`:

```python
        b4 = gesehen["package"].field("process_id").typ
        assert b4.validator("KP-02") is True and b4.validator("KP-03") is False
```

  Lauf → GREEN (bei Ankunft grün, weil `main` seit Step 4 den Kontext übergibt).
- [ ] **Step 7: Werkzeug offline.** In `tests/test_use_case_testprofile.py` bekommt `KONTEXT` den Eintrag `prozesse=(("KP-05", "Wissen"), ("KP-06", "Personal"))`. `test_jeder_fall_endet_fertig_und_vollstaendig` belegt dann, dass die Antworten `KP-05`/`KP-06` gegen die Auswahl gültig sind. Lauf → GREEN.
- [ ] **Step 8: Werkzeug gegen DB, Parität mit dem Dienst** (neuer Test, Fixture `pool` wie die Nachbartests):

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

  (`_zeilen` nimmt keine Parameter, deshalb die Verbindung direkt; `waehle_paket` neu importieren.)
- [ ] **Step 9:** Voller Lauf mit DB → GREEN.
- [ ] **Step 10: Commit** `refactor(bc1): Paket nur noch aus dem Kontext — Parameter prozesse entfaellt (B8)`.

### Task 5: Dienst ohne Snapshot, `GET /prozesse` entfällt

**Files:**
- Modify: `bc1_service/api.py`, `bc1_service/main.py` (Snapshot-Zeilen, Docstring)
- Delete: `bc1_service/snapshot.py`, `bc1_service/snapshot_schema.json`, `tests/test_snapshot.py`
- Test: `tests/test_api.py`, `tests/test_api_profil.py`

**Interfaces:**
- Produces: `create_app(store, llm, package, lifespan=None, *, company_id, anfrage_id=None, writer=None, melder=None) -> FastAPI` ohne `snapshot` und ohne Route `/prozesse`.

- [ ] **Step 1: Failing test** in `tests/test_api.py`:

```python
def test_prozesse_gibt_es_nicht_mehr():
    client = _client()
    assert "/prozesse" not in client.app.openapi()["paths"]
    antwort = client.get("/prozesse")
    assert antwort.status_code == 404
    assert antwort.json() == {"detail": "Not Found"}
```

- [ ] **Step 2:** Lauf → RED (Pfad steht in OpenAPI; Detail `kein_snapshot_konfiguriert`).
- [ ] **Step 3:** Route `/prozesse` und Parameter `snapshot` aus `create_app` entfernen. Im `create_app`-Aufruf in `main.py` entfällt im selben Schritt das vierte Positionsargument `_snapshot`, sonst bekäme `lifespan` zwei Werte. Laden des Snapshots (`_snapshot_pfad`, `_snapshot`) bleibt bis Step 7 stehen.
- [ ] **Step 4:** Lauf. `test_prozesse_ohne_snapshot_404` und `test_kein_snapshot_bleibt_ohne_chat_text` sind jetzt überholt.
  - Ersatz für den Durchreich-Zweig (P3-Zusage) als neuer Test:

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

  - Danach die beiden überholten Tests entfernen.
- [ ] **Step 5: Test-Double streng machen.** In `tests/test_api_profil.py` lautet `_stub_create_app` jetzt `(store, llm, package, *, lifespan=None, **kw)`. Eine positional übergebene Snapshot-Altlast scheitert dann laut.
- [ ] **Step 6: Failing test, alte Variable wirkungslos.** Im selben Verdrahtungstest (oder als Geschwister mit gleichem Aufbau) `monkeypatch.setenv("BC1_SNAPSHOT_PFAD", "/gibt/es/nicht.json")` setzen; der Import von `main` muss gelingen. Lauf → RED (`FileNotFoundError` aus `lade_snapshot`).
- [ ] **Step 7:** In `main.py` den Import von `lade_snapshot`, `_snapshot_pfad` und `_snapshot` entfernen; im Kopf-Docstring die Zeile zu `BC1_SNAPSHOT_PFAD` streichen. Lauf → GREEN.
- [ ] **Step 8: Dateien löschen** (Ausnahme aus den Global Constraints):
  1. `grep -rn "snapshot" --include='*.py' bc1_service bc1_core tests` zeigt keinen Import von `bc1_service.snapshot` mehr; Kommentartreffer sind erlaubt.
  2. `git rm bc1_service/snapshot.py bc1_service/snapshot_schema.json tests/test_snapshot.py`.
  3. Voller Lauf mit und ohne DB → GREEN.
- [ ] **Step 9: Commit** `feat(bc1): GET /prozesse und Snapshot-Modus entfallen (B8)`.

### Task 6: Abhängigkeit, Betrieb, Doku, Roadmap

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `.dockerignore`, `Dockerfile` (Kommentar), `README.md`, `bc1_service/n8n/SMOKE.md`, `design/Abschlussplan-BC1.md`, `design/Spec-B8-Snapshot-abloesen.md` (Kopf: abgenommen)
- Lokal, nicht im Repo: Meldungsentwürfe in `AutoCoE_Projekt/`

- [ ] **Step 1: `jsonschema` von `service` nach `dev`:**
  - `uv remove --group service jsonschema && uv add --group dev jsonschema` in `bc1-context-discovery/`.
  - `git diff uv.lock` lesen: Nur die Gruppenzugehörigkeit von `jsonschema` ändert sich, keine andere Version. Steigt etwas anderes, mit `git checkout -- pyproject.toml uv.lock` zurück und gezielter vorgehen.
- [ ] **Step 2: Abnahme der Abhängigkeiten:**
  - `uv export --frozen --no-dev --group service | grep -c jsonschema` → `0`.
  - `.venv/bin/pytest -v -k test_paket_metadaten 2>&1 | head -5` → die Kopfzeile nennt `tdd-guard-pytest`.
  - Aus `coe-factory/`: `bc1-context-discovery/.venv/bin/python bc2-strategic-advisor/tools/validate.py` → grün.
- [ ] **Step 3: `.dockerignore`:** Die Zeile `!bc1_service/snapshot_schema.json` entfällt; `**/*snapshot*.json` bleibt; der Kopfkommentar ist unverändert.
- [ ] **Step 4: `Dockerfile`:** Im Kommentar vor `CMD` entfällt der Satzteil zum Snapshot. Dazu kommt: „Den Port nur an 127.0.0.1 veröffentlichen (README), solange der Dienst keine Zugangsprüfung hat." Die Zeile `COPY bc1_core/ …` und der Kommentar „Snapshots … bleiben draussen" bleiben.
- [ ] **Step 5: `README.md`:**
  - Container-Start mit `-p 127.0.0.1:8000:8000`.
  - Test-Postgres mit `-p 127.0.0.1:55432:5432`.
  - Der Satz zum Snapshot-Mount entfällt.
  - Ein Satz zur Betriebsvoraussetzung (Spec 6): nur auf dem eigenen Rechner oder im internen Docker-Netz erreichbar, bis es eine Zugangsprüfung gibt.
  - In der Liste der Vorprüfungsregeln und Variablen kommt `BC1_SNAPSHOT_PFAD` nicht mehr vor (grep).
- [ ] **Step 6: `SMOKE.md`:**
  - Die ausführbare Demo-Verdrahtung (Abschnitt „Ohne Claude-Key", Zeilen ~103–140): Import von `lade_snapshot`, `_snapshot_pfad` und das vierte Positionsargument entfallen; `lifespan` wird nicht übergeben.
  - Die Anleitungsschritte „Snapshot setzen" und `curl /prozesse` (Zeilen ~244–250, ~306, ~323–325) werden gestrichen oder durch „B4 kommt aus der DB (`v_prozesse_lesen`)" ersetzt.
  - Protokolle vergangener Läufe (z. B. ~395, ~496) bleiben unverändert.
- [ ] **Step 7: Messung n8n ↔ Dienst bei Loopback-Bindung — nur mit OK der BC1-Projektleitung** (startet Container):
  - Image bauen, Dienst mit `-p 127.0.0.1:8000:8000` und `BC1_BC0_MELDUNGEN=aus` gegen die Test-DB starten.
  - Aus einem Container: `curl -s -o /dev/null -w '%{http_code}' http://host.docker.internal:8000/gesundheit` → `200`.
  - Ergebnis in die Spec (Abschnitt 5) und ins README.
  - Gelingt es nicht: Weg über ein gemeinsames Docker-Netz beschreiben und der BC1-Projektleitung vorlegen.
- [ ] **Step 8: `Abschlussplan-BC1.md`:**
  - B8-Zeile: erledigt (Spec, Plan, Zweig).
  - B3 (d): erledigt durch Streichen.
  - Kleinpunkt „Snapshot-Modus filtert `aktiv` nicht": erledigt, seit 23.09. ohnehin gegenstandslos.
  - **Neuer Roadmap-Punkt unter B3 Teil 2:** Zugangsprüfung des Dienstes, wörtlich aus Spec 6.
  - (4e) um `kp_tp_diskrepanz` ergänzen.
  - (4g) um „B4: Antwort mit Namen statt ID" ergänzen (Review Focus 1).
  - „Nächstes Go" nachziehen.
- [ ] **Step 9: Spec-Kopf:** „Entwurf 2, abgenommen 24.10.2026 (einschließlich 9.2–9.10)".
- [ ] **Step 10: Meldungsentwürfe lokal**, nicht posten: `AutoCoE_Projekt/Entwurf-Kommentar-B8-265-206-286.md` mit drei kurzen Abschnitten:
  - **#265:** Haken entfällt.
  - **BC0 (#206):** Snapshot wird nicht mehr gelesen; Hinweis auf ADR-003.
  - **BC2 (#286):** ein Satz zu `ungeloeste_felder`.
- [ ] **Step 11: Commit** `docs(bc1): B8 — Abhaengigkeit, Betrieb (127.0.0.1), README, SMOKE, Abschlussplan`.

### Task 7: Gesamtabnahme

- [ ] **Step 1: Volle Suite:**
  - Mit DB: erwartet 807 − 11 entfernte Tests (5 in `test_discovery_paket.py`, 1 in `test_paket_wahl.py`, 2 in `test_api.py`, 3 in `test_snapshot.py`) + neue Tests, 4 skipped. Die genaue Zahl im Bericht nennen; jede Abweichung von der Rechnung erklären.
  - Ohne DB: alle DB-Tests skipped, keine Fehler.
- [ ] **Step 2: Reste suchen:**
  - `grep -rn "BC1_SNAPSHOT_PFAD\|lade_snapshot\|kein_snapshot_konfiguriert\|/prozesse" bc1_service bc1_core tests README.md Dockerfile .dockerignore` → nur erklärbare Treffer (historische SMOKE-Protokolle).
  - `git grep -n "snapshot" -- bc1-context-discovery/bc1_service` → keine.
- [ ] **Step 3: Gegenproben** (Lesson „Mutationsprobe": Mini-Plugin im Scratchpad, keine Projektdatei ändern). Jede Probe muss mindestens einen Test rot machen:
  1. `bc0_lesepfade.kernprozesse` ohne Mandantenfilter (liefert A ∪ B);
  2. `_ctx_fingerprint` bekommt immer `[]` als KP-Liste;
  3. B4 im Kontext-Zweig immer Freitext.
- [ ] **Step 4:** Ergebnisse von Suite, Abnahme aus Task 6 Step 2, Gegenproben und Messung aus Task 6 Step 7 (oder „nicht freigegeben") ins Ledger und in den Bericht an die BC1-Projektleitung. Kein Push ohne OK.
