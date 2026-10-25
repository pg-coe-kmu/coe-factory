# Abschluss nachholen (B2 eng + H) — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Stand 25.10.2026, Fassung 2. Entscheidung der BC1-Projektleitung am 25.10.: B2 in enger Form plus H,
> Wortlaut wie vorgeschlagen, R4-I1 wird ersetzt; „danach Plan“. Fassung 2 nach unabhängiger Prüfung
> des Plans (0 Critical, 3 Important, 12 Minor — alle eingearbeitet).

**Goal:** Eine neue Nachricht an eine `fertig`-Sitzung holt das Einfrieren des Profils nach, wenn ihr eigener Entwurf noch offen ist (B2 eng), und bekommt sonst bei ausstehendem Profil einen ehrlichen Text statt „bereits abgeschlossen“ (H).

**Architecture:** Eine Lese-Methode im `ProfilWriter` meldet, ob der Abschluss einer Sitzung nachholbar oder nur ausstehend ist. Das Terminal-Gate in `api.py` verzweigt danach: nachholbar → weiter durch den bestehenden Kern- und Writer-Pfad (kein neuer Schreibweg); ausstehend → 409 mit neuem Schlüssel; sonst wie heute. Die Paket-Prüfung des Kerns wird zu einer gemeinsamen Funktion, die auch das Gate nutzt.

**Tech Stack:** Python 3.11, FastAPI, psycopg 3 + psycopg_pool, pytest, Test-Postgres im Container.

**Spec:** `bc1-context-discovery/design/Spec-Abschluss-nachholen.md` (entschieden 25.10.), vor allem Abschnitt 4.

## Global Constraints

- TDD unter dem tdd-guard, **nie umgangen**. `*.py` unter `coe-factory/` nur mit Edit/Write; Bash nur für pytest, git und Messungen. **Ein neuer Test je Edit**, nach jedem Edit ein voller Lauf. Der Plan zeigt das **Endergebnis**; der Guard verlangt den Weg in kleinsten Schritten (erst Konstante, dann Logik; Helfer nach dem Aufrufer; Fakes erst nach dem Test, der sie verlangt; im roten Schritt nicht umbauen — Skill `tdd-guard`, Lessons 07.10./08.10./24.10.). Neue Imports in Testdateien in der Testfunktion, solange die Funktion noch nicht existiert (wie `test_core.py:583`), damit keine ganze Datei zum Sammelfehler wird.
- pytest **immer** aus `bc1-context-discovery/` und mit DB: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`. Ausgangsstand auf `main` @ `3fe21c1`: 888 bestanden, 4 übersprungen; ohne DB 619/273.
- Zweig `bc1-abschluss-nachholen`, abgezweigt von `bc1-abschluss-nachholen-spec` (PR #353). Nach dem Merge von #353: `git rebase --onto origin/main bc1-abschluss-nachholen-spec bc1-abschluss-nachholen`. Commits auf Deutsch mit Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; Nachrichten mit „…“ über `git commit -F <datei>`. Kein Push ohne OK.
- Neuer Fehlerschlüssel **`abschluss_ausstehend`**, Text wörtlich: `Ihr Interview ist abgeschlossen, das Ergebnis konnte aber noch nicht gespeichert werden. Bitte wenden Sie sich an Ihre Ansprechperson.`
- Neue Protokollzeilen (nur Kennungen, B7): `bc1.writer` ERROR `abschlussstand_unlesbar session=<id> grund=<…>`; `bc1.api` WARNING `abschluss_ausstehend session=<id> message=<neue Kennung> abschluss=<Kennung des Abschluss-Turns>`; `bc1.api` INFO `abschluss_nachgeholt session=<id> message=<neue Kennung>`. *Die WARNING-Zeile ist eine Entscheidung dieses Plans (Spec ließ sie offen): Der Betrieb braucht das Signal „Person war wieder da, Profil steht aus“ und die Kennung für das Nachholen von Hand.*
- Keine Änderung an Datenbank, Vertrag BC1→BC2, Paketfassung oder n8n-Workflow.

## Review Focus

1. **Paket zwischen Abschluss und Neusenden geändert** (Neustart mit anderem ctx-Hash): Die Nachricht darf nicht in den Kern laufen (dort käme `paket_konflikt`), sondern bekommt H. → `test_nachholbar_aber_paket_geaendert_gibt_abschluss_ausstehend` (Task 3).
2. **Lesefehler im Writer** (Pool-Wartezeit, Rechte): 503, nie 409 (würde den offenen Abschluss verschweigen) und nie 500. → `test_abschluss_offen_meldet_lesefehler_als_profil_write_error` (Task 1), `test_lesefehler_im_gate_gibt_503` (Task 3).
3. **Abgebrochene Sitzung bzw. fremder Mandant / fremde Anfrage:** Der Writer wird gar nicht gefragt. → `test_abgebrochene_sitzung_fragt_den_writer_nicht`, `test_fremde_anfrage_fragt_den_writer_nicht` (Task 3).
4. **Text der neuen Nachricht:** wird weder gespeichert noch protokolliert. → `test_nachholen_speichert_die_neue_nachricht_nicht`, `test_abschluss_ausstehend_protokolliert_keinen_text` (Task 3).
5. **Neusenden nach erfolgreichem Nachholen** — auch mit derselben neuen Kennung: 409 `session_abgeschlossen`, kein zweites Einfrieren, das Gate bei BC0 genau einmal. → `test_kurze_stoerung_wird_beim_neusenden_nachgeholt` (Task 4). Gleichzeitiges Neusenden serialisiert der bestehende Sitzungs-Lock (`api.py:225`); kein eigener Test.

---

### Task 1: Lese-Methode `ProfilWriter.abschluss_offen`

**Files:**
- Modify: `bc1_service/profil_writer.py` (Klasse `ProfilWriter`, neben `_bindung`)
- Test: `tests/test_profil_writer.py` (Fixtures `pool`, `_state`, `PAKET`, `FRAGE`, `FERTIG` vorhanden)

**Interfaces:**
- Produces: `ProfilWriter.abschluss_offen(self, state: SessionState) -> str | None` — `None`: nichts offen (Writer schreibt nicht — dann **ohne** DB-Zugriff —, oder Profil eingefroren); `"nachholbar"`: Bindung `in_erhebung` und `bindung.focus_step_id == _gueltiger_wert(state, "focus_step")`; `"ausstehend"`: alles andere (keine Bindung, Entwurf auf anderem Schritt, kein gültiger Fokus-Schritt). Jeder Fehler beim Lesen → `ProfilWriteError`, dazu die ERROR-Zeile `abschlussstand_unlesbar` (Global Constraints) mit `_fehlergrund(fehler)`.

- [ ] **Step 1: Test `test_abschluss_offen_eigener_entwurf_auf_eigenem_schritt_ist_nachholbar`** — `writer.reconcile(_state(), FRAGE)`, dann `assert writer.abschluss_offen(_state()) == "nachholbar"`. Lauf → RED (`AttributeError`) → Methode mit `return "nachholbar"` → GREEN.
- [ ] **Step 2: Test `test_abschluss_offen_nach_dem_einfrieren_ist_none`** — `writer.reconcile(_state(), FERTIG)`; `is None`. RED → Bindung lesen (eine Verbindung aus `self._pool`, `self._bindung`), Status `fertig` → `None` → GREEN.
- [ ] **Step 3: Test `test_abschluss_offen_ohne_bindung_ist_ausstehend`** — frischer Writer, kein `reconcile`; `== "ausstehend"`. RED → GREEN.
- [ ] **Step 4: Test `test_abschluss_offen_mit_entwurf_auf_anderem_schritt_ist_ausstehend`** — `reconcile(_state(tp="KP-01.TP-1"), FRAGE)`; `abschluss_offen(_state(tp="KP-01.TP-2")) == "ausstehend"`. RED → Vergleich mit `_gueltiger_wert(state, "focus_step")` → GREEN.
- [ ] **Step 5: Test `test_abschluss_offen_ohne_identitaetsfeld_im_paket_ist_none_ohne_db`** — Paket ohne identitätskritisches Feld lokal im Test bauen (Muster `test_profil_writer.py:517–521`), Writer mit **nicht geöffnetem** Pool (`ConnectionPool(DSN, open=False)`); `abschluss_offen(_state()) is None` — kein `PoolClosed`, also kein DB-Zugriff. RED → `_schreibt`-Prüfung zuerst → GREEN.
- [ ] **Step 6: Test `test_abschluss_offen_meldet_lesefehler_als_profil_write_error`** — Writer mit `PAKET` und `ConnectionPool(DSN, open=False)`; `pytest.raises(ProfilWriteError)`. RED → `except Exception … raise ProfilWriteError(...) from fehler` → GREEN.
- [ ] **Step 7: Test `test_lesefehler_im_abschlussstand_wird_geloggt`** — wie Step 6 mit `caplog` auf `bc1.writer`: genau eine ERROR-Zeile, beginnt mit `abschlussstand_unlesbar session=s1 grund=`. RED → `log.error` → GREEN.
- [ ] **Step 8:** Voller Lauf grün; Commit `feat(bc1): Writer meldet, ob ein Abschluss nachholbar ist (Paket (4))`.

### Task 2: Gemeinsame Paket-Prüfung `paket_passt`

**Files:**
- Modify: `bc1_core/core.py` (neben `darf_recovery_replay`; Aufruf in `process_turn`, heute Zeilen 116–117)
- Test: `tests/test_core.py`

**Interfaces:**
- Produces: `paket_passt(state: SessionState, package: UseCasePackage) -> bool` — genau `state.schema_version == package.schema_version and state.paket_name in (None, package.name)`.

- [ ] **Step 1: Test `test_paket_passt`**, Import in der Testfunktion, parametrisiert über `(schema_version der Sitzung, paket_name der Sitzung, erwartet)` mit `TOY_PROZESS`: gleich + `"toy_prozess"` → `True`; gleich + `None` → `True`; andere `schema_version` + `"toy_prozess"` → `False`; andere `schema_version` + `None` → `False`; gleich + `"anderes"` → `False`. Lauf → RED (`ImportError`) → Funktion anlegen → GREEN.
- [ ] **Step 2 (Refactoring bei grüner Suite):** `process_turn` prüft mit `if not paket_passt(state, package):` statt der zweizeiligen Bedingung. Voller Lauf grün (Paket-Schutz getragen von `test_core.py:230`, `:240`, `:253`, `:556`, `test_api.py:146`, `test_api_profil.py:285`).
- [ ] **Step 3:** Commit `refactor(bc1): Paket-Prüfung des Kerns als paket_passt (Paket (4))`.

### Task 3: Terminal-Gate mit B2 eng und H

**Files:**
- Modify: `bc1_service/api.py` (Gate `:251–256`, `FEHLER_TEXTE`, Ende des Writer-Blocks `:297–306`)
- Test: `tests/test_api.py`, `tests/test_protokoll.py`

**Interfaces:**
- Consumes: `ProfilWriter.abschluss_offen(state) -> str | None` (Task 1), `paket_passt(state, package) -> bool` (Task 2).
- Produces: Regel aus Spec Abschnitt 4. Für eine **neue** `message_id` an eine terminale Sitzung (Mandanten- und Anfrage-Schutz laufen wie heute davor): Status `fertig` **und** Writer vorhanden → `abschluss_offen(state)`; `"nachholbar"` und `paket_passt` → weiter zu `process_turn`; `"nachholbar"` ohne `paket_passt` oder `"ausstehend"` → 409 `abschluss_ausstehend` plus WARNING-Zeile (`abschluss=` ist `state.raw_log[-1][0]`); `None`, kein Writer oder `abgebrochen_ohne_identitaet` → 409 `session_abgeschlossen` wie heute; `ProfilWriteError` aus `abschluss_offen` → 503 `profil_write_fehlgeschlagen`. Nach erfolgreichem Nachholen (Reconcile ohne Fehler) die INFO-Zeile `abschluss_nachgeholt`.

Testgerüst in `test_api.py`: neues Fake `_OffenerWriter(stand, fehler=None, reconcile_fehler=None)` mit `reconcile` (zählt `self.abgeglichen`; wirft `reconcile_fehler` nur bei `antwort["status"] == "fertig"`, sonst `None`) und `abschluss_offen` (zählt `self.gefragt`, wirft `fehler`, sonst `stand`). Für B2/H Clients mit `TOY_PROZESS` und `_bis_fertig(client)` (`:576`); für den Abbruch `IDENT_PAKET` (`:23`, Muster `:359`). Wo der Test den Store lesen muss, eigenes `create_app` mit eigenem `InMemoryStateStore` statt `_gate_client`. Fake schrittweise nach Lesson 08.10.: zuerst `reconcile` (getrieben durch `assert abschluss.status_code == 200` nach `_bis_fertig` in Step 1), dann `abschluss_offen`, dann jede weitere Fähigkeit mit dem Test, der sie verlangt.

- [ ] **Step 1: Test `test_ausstehender_abschluss_gibt_abschluss_ausstehend_mit_ehrlichem_text`** — Writer `_OffenerWriter("ausstehend")`; `abschluss = _bis_fertig(client)`, `assert abschluss.status_code == 200`; `antwort = _turn(client, "m4", "noch etwas")`; `_fehler(antwort, 409, "abschluss_ausstehend")`, `chat_text` gleich dem wörtlichen Text; `writer.abgeglichen` nach `m4` unverändert (kein Reconcile, also kein Umbinden). RED → Gate-Zweig und Eintrag in `FEHLER_TEXTE` → GREEN.
- [ ] **Step 2: Test `test_eingefrorener_abschluss_bleibt_session_abgeschlossen`** — `_OffenerWriter(None)` → 409 `session_abgeschlossen`. Kommt voraussichtlich grün an → Gegenprobe im Scratchpad-Kopie-Verfahren (Skill `tdd-guard`).
- [ ] **Step 3: Test `test_nachholbarer_abschluss_liefert_die_zusammenfassung`** — `_OffenerWriter("nachholbar")`, `_gate_client`-Muster mit `_GateMelder`: `abschluss = _bis_fertig(client)`; `m4` → 200, `status == "fertig"`, `antwort.json()["chat_text"] == abschluss.json()["chat_text"]`, `melder.aufrufe == 2`. RED → Durchlass zu `process_turn` → GREEN.
- [ ] **Step 4: Test `test_gescheitertes_nachholen_stoesst_das_gate_nicht_an`** — `_OffenerWriter("nachholbar", reconcile_fehler=ProfilWriteError("x"))` mit `_GateMelder`: `m3` → 503, `m4` → 503, `melder.aufrufe == 0`. RED (zuerst im Fake) → Fake nachziehen → GREEN.
- [ ] **Step 5: Test `test_nachholen_speichert_die_neue_nachricht_nicht`** — eigenes `create_app` mit eigenem Store, `_OffenerWriter("nachholbar")`; nach `m4`: `"m4" not in store.load("s1").processed_message_ids` und `raw_log` gleich lang wie vor `m4`. Kommt voraussichtlich grün an → Gegenprobe.
- [ ] **Step 6: Test `test_nachholbar_aber_paket_geaendert_gibt_abschluss_ausstehend`** — gemeinsamer `InMemoryStateStore`; Sitzung mit `TOY_PROZESS` bis `fertig`, dann zweite App mit `replace(TOY_PROZESS, schema_version="0.1-anders")` und `_OffenerWriter("nachholbar")`; `m4` → 409 `abschluss_ausstehend`. RED (`paket_konflikt`) → `paket_passt` im Gate → GREEN.
- [ ] **Step 7: Test `test_lesefehler_im_gate_gibt_503`** — `_OffenerWriter("nachholbar", fehler=ProfilWriteError("x"))` → `m4` 503 `profil_write_fehlgeschlagen`. RED → Übersetzung → GREEN.
- [ ] **Step 8: Test `test_abgebrochene_sitzung_fragt_den_writer_nicht`** — `IDENT_PAKET`, Sitzung bis `abgebrochen_ohne_identitaet` (Muster `:359`), neue Kennung → 409 `session_abgeschlossen`, `writer.gefragt == 0`.
- [ ] **Step 9: Test `test_fremde_anfrage_fragt_den_writer_nicht`** — gemeinsamer Store; Sitzung mit `anfrage_id=ANFRAGE` bis `fertig`, zweite App mit anderer `anfrage_id` und `_OffenerWriter("nachholbar")`; neue Kennung → 409 `anfrage_konflikt`, `writer.gefragt == 0`.
- [ ] **Step 10: Test `test_nachgeholter_abschluss_wird_protokolliert`** — `caplog` auf `bc1.api`, Melder `None`; unter den Zeilen genau eine, die mit `abschluss_nachgeholt` beginnt: `abschluss_nachgeholt session=s1 message=m4`. RED → GREEN.
- [ ] **Step 11: Test `test_abschluss_ausstehend_protokolliert_keinen_text`** in `tests/test_protokoll.py` — eigenes Fake in dieser Datei (wie `_OffenerWriter`, Stand `"ausstehend"`); WARNING `abschluss_ausstehend session=s1 message=m4 abschluss=m3` auf `bc1.api`, Turn-Zeile `http=409 status=abschluss_ausstehend`, `GEHEIM` in keiner Zeile. RED → GREEN.
- [ ] **Step 12:** Voller Lauf grün (`test_fehlertexte_tragen_keine_schluessel_und_keine_interna` prüft den neuen Text mit; fremder Mandant vor dem Gate: `test_fremder_mandant_wird_auch_bei_terminaler_session_abgewiesen`, `:392`); Commit `feat(bc1): Gate holt einen offenen Abschluss nach, sonst ehrlicher Text (Paket (4))` mit den Gegenproben im Text.

### Task 4: Ende zu Ende gegen die Test-DB

**Files:**
- Test: `tests/test_api_profil.py` (Fixtures `umgebung`, `_llm`, `_turn`, `verbindung`, `_GateZaehler` `:873`)

**Interfaces:**
- Consumes: alles aus Task 1–3, echter `ProfilWriter`.

Jeder Test baut sein `create_app` selbst (wie `:792–803`), weil `_client` einen normalen Writer ohne Melder verdrahtet. Writer-Unterklassen **lokal in der Testfunktion**. Die Tests kommen voraussichtlich grün an; jeder bekommt eine Gegenprobe im Scratchpad-Kopie-Verfahren (Gate-Zweig dort zurückdrehen, der Test muss rot werden). Ergebnis im Commit nennen.

- [ ] **Step 1: Test `test_kurze_stoerung_wird_beim_neusenden_nachgeholt`** — lokale Unterklasse von `ProfilWriter`, deren `_einfrieren` beim **ersten** Aufruf erst `super()._einfrieren(...)` ausführt (UPDATE auf `fertig` läuft) und dann `RuntimeError("kurze Störung")` wirft; danach normal. Eigener Store, `_llm(ohne=("pii_involved",))`, Melder `_GateZaehler`. Ablauf und Assertions:
  - `m1 "alles"` → Frage; `m2 "rest"` → 503; DB `SELECT status FROM bc1.prozessprofil` → `[("in_erhebung",)]` (**Rückroll belegt**); `melder.aufrufe == 0`.
  - `m3 "nochmal"` → 200 `fertig`; `chat_text.startswith(payload["abschluss_text"])`; `payload["befunde"]` gleich `befunde` aus dem DB-Profil (Overlay; die Eigner-Abweichung R-01/R-02 sorgt für einen nicht leeren Wert); DB → `[("fertig",)]`; `melder.aufrufe == 1`.
  - `m3 "nochmal"` erneut (dieselbe neue Kennung) → 409 `session_abgeschlossen`; `m4 "danke"` → 409 `session_abgeschlossen`; `melder.aufrufe == 1`; DB weiter eine Zeile.
- [ ] **Step 2: Test `test_stillgelegter_teilprozess_bleibt_bei_503_ohne_neuen_entwurf`** — eigener Store; nach `m1` `UPDATE ref_teilprozesse SET aktiv = false … 'KP-01.TP-1'` (Muster `test_profil_writer.py:211`); `m2` → 503; Länge von `store.load("s1").raw_log` merken; `m3` → 503; `raw_log` gleich lang, `"m3"` nicht in `processed_message_ids`; DB-Zeilen unverändert `[("KP-01.TP-1", 1, "in_erhebung")]`.
- [ ] **Step 3: Test `test_fremder_entwurf_gibt_beim_neusenden_abschluss_ausstehend`** — Aufbau wie `test_503_traegt_den_stabilen_detail_string` (`:837`); `m1` → 503; `m2` → 409 `abschluss_ausstehend`; DB: nur der fremde Entwurf.
- [ ] **Step 4:** Voller Lauf grün; Commit `test(bc1): Abschluss nachholen Ende zu Ende gegen die DB (Paket (4))` mit den Gegenproben im Text.

### Task 5: Doku, Spec-Regel, Roadmap und Nebenbefund

**Files:**
- Modify: `bc1_service/n8n/SMOKE.md`, `README.md` (Betriebsprotokoll), Modul-Kopf `bc1_service/api.py`, Kommentare `bc1_core/core.py:146–148` und `bc1_core/types.py:22–23`, Kommentar `tests/test_api.py:784–786`, `design/Spec-Abschluss-nachholen.md` (Status „gebaut“), `design/Abschlussplan-BC1.md`; lokal außerhalb des Repos `docs/superpowers/specs/2026-08-23-bc1-db-profil-fundament-design.md` (R4-I1).

- [ ] **Step 1: Doku.**
  - `SMOKE.md`: Absatz „Im Chat reicht Neusenden nicht immer“ neu fassen (nachholbar → Zusammenfassung; sonst Text `abschluss_ausstehend`, Nachholen von Hand mit der Kennung aus `abschluss=` der WARNING-Zeile). K5-Rezept: Ein gelöschter Entwurf einer `fertig`-Sitzung wird nicht nachgeholt; die Person sieht den neuen Text. **Grenzen** nennen: (a) Löscht der Betrieb den Entwurf genau zwischen Prüfung und Abgleich (Millisekunden), legt der Abgleich ihn neu an; (b) eine Nachricht nach einem erfolgreichen Abschluss liest jetzt die DB — scheitert das, kommt 503 „konnte gerade nicht gespeichert werden“, obwohl das Profil steht.
  - `README.md`: Schlüssel `abschluss_ausstehend` in der Liste, die drei neuen Zeilen in der Tabelle.
  - Code-Kommentare per Edit (Modul-Kopf `api.py`, `core.py:146–148`, `types.py:22–23`, Testkommentar `test_api.py:784–786`), voller Lauf danach.
  - R4-I1 neu: „Neue `message_id`s an fertige Sitzungen: nachholen, wenn der eigene Entwurf auf dem eigenen Fokus-Schritt offen ist und das Paket passt; sonst bei ausstehendem Profil 409 `abschluss_ausstehend`, bei eingefrorenem 409 `session_abgeschlossen` (Entscheidung 25.10., Paket (4)).“
- [ ] **Step 2: Roadmap (Prinzip 4).** Im Abschlussplan „Neu 23.10.“ (2) auf erledigt, Paket (4) in der Reihenfolge erledigt, und aus Spec §7 **jeden** Punkt mit Ziel und Auslöser eintragen: G (Nachholen beim Start; Ziel B3 Teil 2, Auslöser erster Fall „Person weg“), E (Hintergrund; B3 Teil 2/C4, mehr als ein Worker), F (Wiederholung im Aufruf bzw. n8n-Knoten; Auslöser gemessene kurze Störungen, dann n8n-Doku lesen), anderer Text für die 503-Schleife (Ziel Paket (6) bzw. erster dauerhafter 503), weite Form von B2 (Auslöser K5-Häufung, vorher mit BC0 klären), Ursache „Sitzung `fertig` vor dem 503“ (bleibt C4). Den C4-Punkt „Outbox/Reconciler“ auf G/E verweisen lassen.
- [ ] **Step 3: Nebenbefund klären, nicht bauen.** Mit einem Test im Scratchpad oder durch Lesen belegen, ob ein Konvertierungs-Widerspruch mitten im Interview (`profil_writer.py:203–211`, `:356–359`) einen 503 erzeugt (die Planprüfung hat es durch Lesen bestätigt). Ergebnis mit Ziel in den Abschlussplan („Neu 25.10. — aus der Prüfung von Paket (4)“). Eine Code-Änderung nur nach Entscheidung der BC1-Projektleitung.
- [ ] **Step 4:** Voller Lauf mit und ohne DB, Zahlen notieren; Commit `docs(bc1): Abschluss nachholen dokumentiert, R4-I1 ersetzt (Paket (4))`.
- [ ] **Step 5:** Unabhängige Gesamtprüfung des Zweigs (Plan, Spec, Diff) durch einen frischen Prüfer; Befunde nach Schwere einarbeiten bzw. mit Ziel nachhalten; dann Bericht an die BC1-Projektleitung, Push erst nach OK.
