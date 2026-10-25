# Test-Aufräumen: gemeinsame Fixture für die `main`-Importtests — Plan (Paket (5))

> Stand 25.10.2026, Fassung 1. Go der BC1-Projektleitung am 25.10. („Go Paket 5").
> Quelle: Abschlussplan „Neu 24.10. — aus B8" (1) und (2); „Neu 25.10. — aus B7 Teil 2" (3) als Option.
> **Gebaut 25.10.** auf Zweig `bc1-test-aufraeumen`, ohne Abweichung vom Plan: Der Guard ließ den ersten Edit (Fixture und Test 1) als Refactoring bei Grün durch, der Ausweichweg war nicht nötig. Alle drei Gegenproben verhielten sich wie erwartet, G2 auch mit dem Zusatz. Testnamen vorher und nachher gleich (913), Suite mit DB 909/4. Außerhalb des Plans steht im Doku-Commit ein Prüfbefund zum Nebenbefund Konvertierungs-Widerspruch (Abschlussplan „Neu 25.10. — aus der Prüfung von Paket (4)"); die Entscheidung dazu bleibt offen. Gesamtprüfung: 0 Critical, 0 Important, 3 Minor. Eingearbeitet: Einmal-Vertrag für `main_laden()` (Zusicherung, Gegenprobe in einer Kopie), Zahl der Melder-Tests korrigiert, dieser Hinweis ergänzt.
> Größe XS, nur Testcode, eine Datei. Zweitmeinung: eine unabhängige Prüfung nach dem Bau (Plan und Diff zusammen). Mehr ist nicht nötig, weil kein Produktionscode und kein Vertrag berührt wird.

## Big Picture

Vier Tests in `tests/test_api_profil.py` prüfen, wie `bc1_service/main.py` den Dienst zusammensetzt: Writer verdrahtet, Kernprozess-Auswahl B4, nur drei Positionsargumente an `create_app`, Start trotz alter Snapshot-Variable. Jeder dieser Tests wiederholt rund 20 Zeilen: einen Ersatz für `create_app`, fünf Umgebungsvariablen, einen frischen Import von `main` und das Aufräumen im `finally`. Zwei der Tests benutzen einen nachsichtigen Ersatz (einer davon mit dem toten Parameter `snapshot=None` aus der Zeit vor B8), der ein überzähliges Positionsargument verschluckt. Die anderen zwei benutzen einen strengen Ersatz.

**Danach:** Eine Fixture `main_laden` übernimmt Ersatz, Umgebung, Import und Aufräumen. Die vier Tests behalten ihre Prüfungen Wort für Wort und zeigen nur noch, was sie prüfen.

**Was sich ändert:** Alle vier Tests laufen mit dem strengen Ersatz. Würde `main.py` ein viertes Positionsargument übergeben, schlügen damit alle vier fehl, nicht nur einer. Das ist gewollt: Die Regel aus B8 gilt dann überall.

**Was sich nicht ändert:** Produktionscode, Anzahl und Namen der Tests (Suite mit DB 909/4), die acht Melder-Tests mit ihrem eigenen Helfer `_main_mit_melder`.

## Entscheidungen

| # | Entscheidung | Warum |
|---|---|---|
| E1 | Fixture als **Fabrik**: `main_laden()` importiert erst beim Aufruf und gibt `(main, gesehen)` zurück | Test 4 muss `BC1_SNAPSHOT_PFAD` **vor** dem Import setzen. Eine Fixture, die selbst importiert, liefe vor dem Testkörper. |
| E2 | Fixture direkt **über dem ersten Test** der Gruppe, nicht oben bei `umgebung` | So steht es in der Datei schon bei `_StartMelder` und `_main_mit_melder`: Helfer stehen bei ihren Tests. Außerdem kann der erste Umbau so in einem zusammenhängenden Edit geschehen. |
| E3 | Ein **strenger** Ersatz `_stub_create_app(store, llm, package, **kw)` für alle vier | Ein nachsichtiger Ersatz kann einen Verdrahtungsfehler verdecken. `lifespan` landet benannt in `kw`, also in `gesehen["lifespan"]`. |
| E4 | **Vorschlag, Entscheidung bei der Planabnahme:** Die acht Melder-Tests (ca. Z. 581–738) bleiben, wie sie sind | Sie haben schon einen gemeinsamen Helfer. Wiederholt wird nur das dreizeilige Aufräumen, und zwar in vier von ihnen. Sie umzubauen hieße vier weitere Umbauten unter dem Guard für wenig Gewinn. *(Zahlen nach der Gesamtprüfung korrigiert; die Entscheidung ändert sich dadurch nicht.)* **Ziel:** `_main_mit_melder` auf das Aufräumen von `main_laden` stützen, sobald ein weiterer Melder-Test dazukommt (neuer Kleinpunkt im Abschlussplan). |
| E5 | **Vorschlag, Entscheidung bei der Planabnahme:** Die eigene Protokollzeile für einen Startabbruch (B7 Teil 2, A2) ist **nicht** Teil dieses Pakets | Sie wäre Produktionscode. Heute gibt es keinen Leser, den der Traceback stört, also gilt YAGNI. **Neues Ziel:** B3 Teil 2, sobald Startabbrüche im Server-Log gelesen werden müssen. Das Ziel im Abschlussplan wird umgeschrieben. |

## Global Constraints

- TDD unter dem tdd-guard, nie umgangen. `*.py` unter `coe-factory/` nur mit Edit/Write; Bash nur für pytest, git und Messungen. Ein Test je Edit, nach jedem Edit ein voller pytest-Lauf.
- pytest aus `bc1-context-discovery/`: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`. Ausgangsstand auf `main` @ `4b5d5c0`: mit DB 909 bestanden, 4 übersprungen; ohne DB 624/289.
- Die **Prüfungen** (`assert …`) der vier Tests bleiben Wort für Wort. Kommentare werden nur geändert, wo ihr Text falsch wird.
- Zweig `bc1-test-aufraeumen` von `main` @ `4b5d5c0`. Commits auf Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Kein Push ohne OK.

## Review Focus

1. **Aufräumen auch bei rotem Test:** Die Fixture schließt beide Pools und entfernt `bc1_service.main` aus `sys.modules`, auch wenn eine Prüfung scheitert. Sonst gibt es Folgeroten in `test_postgres_init.py` („DID NOT RAISE", Lesson 08.10.). Beleg: Gegenprobe G2.
2. **Der strenge Ersatz greift in allen vier Tests:** Beleg: Gegenprobe G1.
3. **Test 4 setzt die Variable vor dem Import:** Sonst prüft er nichts. Beleg: Gegenprobe G3.
4. **Kein Test geht verloren:** Die Liste der gesammelten Testnamen ist vorher und nachher gleich.

## Tasks

### Task 1 — Fixture und erster Test

Datei: `tests/test_api_profil.py`, Test `test_main_verdrahtet_den_profil_writer` (ca. Z. 432–468).

- [ ] Ausgangslauf (volle Suite) → 909/4. Damit kennt der Guard den grünen Stand. Testnamen sichern: `.venv/bin/pytest --co -q -p no:tdd-guard -p no:cacheprovider > <scratchpad>/namen-vorher.txt`.
- [ ] **Ein Edit, Refactoring bei Grün:** Fixture `main_laden(umgebung, monkeypatch)` direkt über dem Test einfügen und den Test darauf umstellen.
  - Die Fixture übernimmt aus dem heutigen Testkörper: Ersatz nach E3, `gesehen.update(kw, package=package)`, Rückgabe `"app"`, die fünf `setenv` (DSN, Mandant, `ANFRAGE_A`, `BC1_LLM=ollama`, `BC1_BC0_MELDUNGEN=aus`).
  - Sie liefert eine Funktion ohne Argumente. Diese nimmt `bc1_service.main` per `monkeypatch.delitem(…, raising=False)` aus `sys.modules`, importiert es frisch, merkt sich das Modul und gibt `(main, gesehen)` zurück.
  - Nach dem `yield` schließt sie für ein geladenes Modul `_store` und `_profil_pool` und ruft immer `sys.modules.pop("bc1_service.main", None)` auf.
  - Der Test: Signatur `(main_laden)`, erste Zeile `main, gesehen = main_laden()`, danach die bisherigen Prüfungen ohne `try/finally`. Der Kommentar bleibt.
- [ ] Volle Suite → 909/4.
- [ ] **Falls der Guard den Edit ablehnt** (z. B. „behavioral change", weil der Ersatz strenger wird): erst nur den Test auf `main_laden` umstellen → voller Lauf (Fehler „fixture 'main_laden' not found" ist der RED) → dann die Fixture → voller Lauf. Lehnt er auch das ab: anhalten und melden. Kein Ausweichen auf Bash.
- [ ] Commit `test(bc1): gemeinsame Fixture main_laden für die main-Importtests (Paket (5))`.

### Task 2 — Die drei übrigen Tests

Jeder Schritt ist ein eigener Edit mit eigenem vollem Lauf (909/4).

- [ ] `test_main_baut_b4_aus_den_kernprozessen_des_mandanten` → `(main_laden)`, `_, gesehen = main_laden()`.
- [ ] `test_main_uebergibt_create_app_keine_weiteren_positionsargumente` → wie oben. Der Kommentarsatz „Das tolerante Double der Geschwistertests verschluckt ein ueberzaehliges viertes Argument." wird zu „Das Double der Fixture `main_laden` ist streng; dieser Test haelt die Regel ausdruecklich fest."
- [ ] `test_main_startet_trotz_alter_snapshot_variable` → `(main_laden, monkeypatch)`, `monkeypatch.setenv("BC1_SNAPSHOT_PFAD", "/gibt/es/nicht.json")` **vor** `_, gesehen = main_laden()`.
- [ ] Prüfen: `grep -n "snapshot=None" tests/` findet nichts. `grep -n 'import_module("bc1_service.main")' tests/test_api_profil.py` findet nur noch die Fixture und `_main_mit_melder`. Die Testnamen sind gleich: `--co` wie oben, `diff` gegen `namen-vorher.txt` ist leer.
- [ ] Commit `test(bc1): main-Importtests auf main_laden umgestellt, toter Parameter snapshot=None entfernt (Paket (5))`.

### Task 3 — Gegenproben und Doku

- [ ] **Gegenproben** im Scratchpad-Kopie-Verfahren (Skill `tdd-guard`; im Projekt wird nichts editiert). Jede Probe in einer frischen Kopie, Lauf nur über `tests/test_api_profil.py` und `tests/test_postgres_init.py` mit `-p no:tdd-guard -p no:cacheprovider`:
  - G1: `main.py` übergibt `create_app` zusätzlich ein viertes Positionsargument → alle vier Tests rot.
  - G2: In Test 1 wird eine Prüfung falsch gemacht → nur Test 1 rot, `test_postgres_init.py` grün. Zusatz in derselben Kopie: Ohne `sys.modules.pop` in der Fixture wird `test_postgres_init.py` rot. Das zeigt, dass die Probe Zähne hat. Beide Läufe nur über `tests/test_api_profil.py::test_main_verdrahtet_den_profil_writer tests/test_postgres_init.py`, denn im Dateilauf räumen die späteren Melder-Tests ohnehin auf und verdecken einen Fehler.
  - G3: `main.py` bricht ab, wenn `BC1_SNAPSHOT_PFAD` gesetzt ist → Test 4 rot.
- [ ] **Doku, ein Commit:**
  - Abschlussplan: „Neu 24.10. — aus B8" (1)/(2) als erledigt markieren, mit Plan-Verweis. Paket (5) in der Reihenfolge auf „gebaut auf Zweig". Bei B7 (3) das Ziel nach E5 umschreiben. E4 als neuer Kleinpunkt.
  - Fälliger Nachtrag aus Paket (4): Stand-Zeile, „Neu 23.10." (2) und Reihenfolge (4) auf „auf `main` (#356)"; `design/Spec-Abschluss-nachholen.md` Status „auf `main` (#356)"; Minor 6 als Satz in `bc1_service/n8n/SMOKE.md`.
  - Bauvermerk im Kopf dieses Plans.
- [ ] Volle Suite mit DB (909/4) und ohne DB (624/289).
- [ ] Unabhängige Gesamtprüfung (Plan und Diff `main..bc1-test-aufraeumen`; jeder pytest-Aufruf mit `-p no:tdd-guard -p no:cacheprovider`). Befunde nach Schwere einarbeiten oder mit Ziel zurückstellen.
- [ ] Bericht an die BC1-Projektleitung; Push/PR nur nach OK.
