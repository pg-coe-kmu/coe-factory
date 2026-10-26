# Format-Test BC1 → BC2 — Plan

> Stand 26.10.2026, Fassung 1. Go der BC1-Projektleitung am 26.10. („Schritt 4: Format-Test. Erst Plan, dann TDD, dann unabhängige Prüfung. Push nur nach OK“).
> Quelle: Abschlussplan „Neu 25.10. — beim Abgleich von #48/#51 vor dem Schließen“.
> Größe S: eine neue Testdatei mit zwei Tests, kein Produktionscode, dazu Doku. Zweitmeinung: eine unabhängige Prüfung nach dem Bau, mit eigener Datenbank.
> **Gebaut 26.10.** auf Zweig `bc1-format-test`, ohne Abweichung von E1–E6. Beide Tests kamen grün an, je einzeln mit vollem Lauf (916/4, dann 917/4). Mutationsproben in einer Scratchpad-Kopie mit eigener DB: **M1** (ohne `p.paket_version` in `lesen.sql`) macht **beide** Tests rot — auch Fall 2 liest über die Datei; **M2** (`frequency_per_year` nicht nullbar) macht nur Fall 2 rot. Rückbau: wieder 2 grün. Eine eigene Planprüfung entfiel (zwei Tests, kein Produktionscode); die Gesamtprüfung bekommt Plan und Code zusammen.

## Big Picture

BC2 liest unsere Profile über die Leseregel `contracts/bc1-to-bc2/lesen.sql`. Wie das gelesene Objekt aussehen muss, legt `contracts/bc1-to-bc2/prozessprofil.schema.json` fest. Die Vertrags-CI prüft heute nur ein **Beispiel** gegen das Schema (`contracts/examples/beispiel_bc1_prozessprofil.json`, ein Export vom 12.09.). **Kein Test prüft, ob das, was unser Writer heute einfriert, über die Leseregel gelesen das Schema erfüllt.** Ändert sich der Writer, die Tabelle, `lesen.sql` oder das Schema, fällt ein Bruch erst bei BC2 auf.

**Neu:** Ein BC1-Test schreibt Profile über den echten Writer in die Test-DB, liest sie mit `lesen.sql` selbst (nicht mit einer Kopie der Abfrage) und prüft jedes gelesene Objekt gegen das Schema. Zwei Fälle:
1. die drei Use-Case-Testprofile (Version 3), also volle Profile, wie sie der Betrieb schreibt;
2. ein Profil, das `fertig` wird, obwohl die vier Rechengrößen ungelöst blieben. Dann sind die Spalten `NULL`, und der Vertrag sagt ausdrücklich, dass das erlaubt ist.

**Machbarkeit ist gemessen (Spike 26.10., eigene DB):** Beide Fälle ergeben 0 Schemafehler. Der Test kommt also grün an; dass er Zähne hat, belegen zwei Mutationsproben (Task 2).

**Was sich nicht ändert:** Produktionscode, Datenbank, Vertrag, Schema, `lesen.sql`, CI.

**Nicht in diesem Paket (Entscheidung BC1-Projektleitung):** Die DoD von #48/#51 sagt „validiert **in CI**“. BC1s Tests laufen in keiner CI; der einzige Workflow ist `vertraege-pruefen.yml` (Vertragspaare und Lieferungen, ohne Datenbank). Der neue Test läuft deshalb in BC1s Suite mit Test-DB, nicht in der CI. Ein CI-Job mit Postgres-Dienst wäre eine Änderung an einer gemeinsamen Datei im öffentlichen Repo und gehört in ein eigenes Paket, falls gewollt.

## Entscheidungen

| # | Entscheidung | Warum |
|---|---|---|
| E1 | Das JSON baut Postgres: jede Anweisung aus `lesen.sql` wird als `SELECT row_to_json(t) FROM (<Anweisung>) t` ausgeführt | Der Vertrag beschreibt die **Leseprojektion**, nicht Postgres-Typen („Einig werden müssen sich beide Seiten über Feldnamen, Einheiten und Nullbarkeit — nicht über Postgres-Typen“, README). Das Beispiel im Vertrag ist genau so entstanden (`export_kp06tp2.sql`, `row_to_json`), und das Schema nennt `row_to_json` bei `erstellt_am`. BC2s Leser (`bc2-strategic-advisor/app/erkennung/bestand.py`) baut das ganze Objekt gar nicht: Er liest eine Teilmenge der Spalten mit psycopg2 und prüft nicht gegen das Schema. Eine eigene Python-Umwandlung (`Decimal`, `datetime` → JSON) wäre erfunden. |
| E2 | `lesen.sql` wird aus der Datei gelesen und an `;` + Zeilenende geteilt; Teile, die nach dem Entfernen von `--`-Kommentaren leer sind, fallen weg. Erwartet sind genau zwei Anweisungen (Profile, Rollen) | Wiederverwendet aus BC1s Gegenprobe zu #255 (`lesen_gegenprobe.py`, `re.split(r";\s*\n", …)`). Läuft die Datei in eine dritte Anweisung oder verliert sie eine, scheitert das Entpacken laut. |
| E3 | Auch die Rollen-Abfrage läuft. Ihr Ergebnis hängt als `rollen` am Objekt (Zeilen mit gleicher `focus_step_id`), so wie im Beispiel | Belegt, dass auch die zweite Anweisung gegen die echte DDL läuft. `profil_rollen` ist leer und bleibt es (Rollenachse abgewählt, #172); der Test erwartet `rollen == []`. |
| E4 | Validiert wird wie in `validate.py`: `Draft202012Validator(schema)`, ohne Formatprüfung | Dieselbe Prüfung wie die Vertrags-CI. Strenger zu prüfen als BC2 selbst wäre ein eigener Vertrag. |
| E5 | Neue Datei `tests/test_vertrag_bc2.py`. Gerüst und Anfragen kommen aus `tests/test_use_case_testprofile.py` (`_noro_geruest`, `ANFRAGEN`), die `pool`-Fixture wird dort nachgebaut (sieben Zeilen) | Das Thema ist der Vertrag, nicht die Testprofile. Das Noro-Gerüst nach `db_fixture.py` zu ziehen wäre ein Umbau fremder Tests ohne Not; eine importierte Fixture aus einem Testmodul ist schwerer zu lesen als die sieben Zeilen. |
| E6 | Fall 2 baut den Sitzungsstand von Hand (Fokus-Schritt gültig, vier Rechengrößen `ungeloest` mit Grund `nachfrage_limit_erreicht`) und friert ihn mit dem echten Writer und dem echten Discovery-Paket ein | So machen es die Writer-Tests auch. Den Dialog bis zum Nachfrage-Limit zu treiben, prüft den Dialog, nicht das Format. |

## Global Constraints

- TDD unter dem tdd-guard, nie umgangen. `*.py` unter `coe-factory/` nur mit Edit/Write; Bash nur für pytest, git und Messungen. **Ein Test je Edit**, nach jedem Schritt ein voller Lauf (Lesson „gilt auch für grün-bei-Ankunft-Contract-Tests“).
- pytest aus `bc1-context-discovery/`: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`. Ausgangsstand auf `main` @ `6a88686`: 915/4 mit DB, 624/295 ohne DB.
- Zweig `bc1-format-test` ab `main` @ `6a88686`. Commits auf Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Kein Push ohne OK.
- Mutationsproben nur in einer Scratchpad-Kopie mit eigener Datenbank (Lesson 07.10., B4 Task 4); im Projekt entsteht nichts auf diesem Weg.

## Review Focus

1. **Kein leerer Erfolg.** Liefert `lesen.sql` keine Zeile (falscher Mandant, falsche TP-IDs), validiert eine Schleife über nichts. Beide Tests prüfen deshalb vorher, welche Zeilen ankommen.
2. **Der NULL-Pfad ist wirklich geprüft.** Fall 2 prüft, dass die vier Rechengrößen im Objekt `null` sind und in `ungeloeste_felder` stehen; Mutationsprobe M2 zeigt, dass nur Fall 2 rot wird, wenn das Schema `null` verbietet.
3. **Es läuft die Datei, nicht eine Kopie.** Mutationsprobe M1 entfernt eine Pflichtspalte aus `lesen.sql`; Fall 1 muss rot werden.
4. **`rollen`:** leer, und trotzdem lief die zweite Anweisung (E3).
5. **Zeitstempel und Zahlen:** `erstellt_am` als Zeichenkette, Zahlen als JSON-Zahl, `focus_step_duration_confidence_pct` als ganze Zahl. Prüft das Schema in Fall 1.

---

### Task 1: Testdatei mit Fall 1 (die drei Testprofile)

**Files:**
- Create: `bc1-context-discovery/tests/test_vertrag_bc2.py`

**Interfaces:**
- Consumes: `schreibe_testprofile(pool, company_id, anfragen)` (`bc1_service.use_case_testprofile`); `_noro_geruest(conn)`, `ANFRAGEN` (`tests.test_use_case_testprofile`); `DSN`, `MANDANT_A`, `frische_db`, `verbindung` (`tests.db_fixture`).
- Produces (nur in der Datei): `VERTRAG: Path` (= `parents[2] / "contracts" / "bc1-to-bc2"`), `_anweisungen() -> list[str]` (E2), `_projektionen(pool, focus_step_ids: list[str]) -> list[dict]` (E1, E3; Reihenfolge wie `lesen.sql`), `_fehler(objekt: dict) -> list[str]` (E4; je Fehler `"<pfad>: <meldung>"`), Fixture `pool` (wie in `test_use_case_testprofile.py`: `frische_db`, `_noro_geruest`, Pool mit `-c role=bc1_role`).

- [ ] **Schritt 1: Testdatei mit Modul-Docstring, Helfern und genau einem Test anlegen**

```python
def test_testprofile_erfuellen_das_schema_ueber_die_leseregel(pool):
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    objekte = _projektionen(pool, list(ANFRAGEN))
    assert [o["focus_step_id"] for o in objekte] == sorted(ANFRAGEN)
    for o in objekte:
        assert o["rollen"] == []
        assert _fehler(o) == []
```

- [ ] **Schritt 2: Voller Lauf.** Erwartet: neuer Test grün, 916/4.
- [ ] **Schritt 3: Commit** `BC1: Format-Test — Testprofile über lesen.sql gegen das Vertragsschema`

### Task 2: Fall 2 (fertig mit ungelösten Rechengrößen) und Mutationsproben

**Files:**
- Modify: `bc1-context-discovery/tests/test_vertrag_bc2.py`

**Interfaces:**
- Consumes: Task 1; `ProfilWriter(pool, company_id, paket).reconcile(state, {"status": "fertig", "payload": {}})`; `lade_kontext(conn, company_id, anfrage_id)`; `baue_discovery_paket(kontext=…)`; `SessionState`, `FieldValue`, `FieldStatus`.

- [ ] **Schritt 1: Genau einen Test ergänzen**

```python
RECHENGROESSEN = ("frequency_per_year", "executions_per_run",
                  "total_duration_minutes", "focus_step_duration_minutes")

def test_fertiges_profil_mit_ungeloesten_rechengroessen_erfuellt_das_schema(pool):
    # Zustand nach E6, Anfrage ANFRAGEN["KP-06.TP-2"], dann reconcile(..., fertig)
    [o] = _projektionen(pool, ["KP-06.TP-2"])
    assert all(o[f] is None for f in RECHENGROESSEN)
    assert set(o["profil"]["ungeloeste_felder"]) == set(RECHENGROESSEN)
    assert _fehler(o) == []
```

- [ ] **Schritt 2: Voller Lauf.** Erwartet: 917/4.
- [ ] **Schritt 3: Mutationsproben in einer Scratchpad-Kopie** (`bc1-context-discovery` ohne `.venv` und `contracts/bc1-to-bc2` in denselben relativen Lagen, eigene DB `mut_format`, Lauf mit `-p no:tdd-guard -p no:cacheprovider`; vorher prüfen, dass die Kopie importiert wird):
  - **M1:** in der Kopie von `lesen.sql` die Zeile `p.paket_version,` der ersten Anweisung entfernen → Fall 1 rot mit `'paket_version' is a required property`.
  - **M2:** in der Kopie des Schemas `frequency_per_year.type` auf `"number"` → nur Fall 2 rot, Fall 1 grün.
- [ ] **Schritt 4: Commit** `BC1: Format-Test — fertiges Profil mit ungelösten Rechengrößen`

### Task 3: Doku

**Files:**
- Modify: `bc1-context-discovery/design/Abschlussplan-BC1.md`, dieser Plan (Kopf: „gebaut“, Abweichungen, Ergebnis der Proben)

- [ ] **Schritt 1:** Abschlussplan „Neu 25.10. — beim Abgleich von #48/#51“: Stand „gebaut 26.10. (Plan `design/Plan-Format-Test-Vertrag-BC2.md`)“, die CI-Frage als offene Entscheidung mit Ziel. Dazu die aufgelaufenen Nachträge aus dem Übergabestand: „Neu 25.10. — aus der Auswirkungsprüfung BC0 v3.8–v3.20.1“ (2) „gemessen 26.10.“, (1) Frage 3 durch die Messung beantwortet, die Fragen an BC0 gestellt (#354, 26.10.); Reihenfolge Schritt 2/3 „auf `main` (#358/#359)“; `design/Plan-Geruest-BC0-v3.19.md` und `design/Plan-Konvertierung-im-Frage-Turn.md` Status „auf `main`“.
- [ ] **Schritt 2: Commit** `BC1: Doku — Format-Test, Nachträge aus Session 26`
