# C1a Eigner-Rolle, D4 als Anzahl, E2, Testprofile Version 3 — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Interview erfasst den Eigner als Rolle aus `mandant_rollen` und schreibt sie in `process_owner_rolle_id`. D4 ist eine reine Anzahl, E2 fragt nach einem Lauf des Schritts. Das Testprofil-Werkzeug schreibt Version 3 zu übergebenen Anfragen und meldet BC0 wie der Dienst.

**Architecture:**
- Rollen und Eigner kommen beim Start in den `Bc0Kontext`. Das Paket baut daraus die Auswahl für B3 samt Vorschlag; die Rollen-IDs fließen in den Fingerabdruck.
- Der Writer leitet die Spalte aus dem gültigen B3-Wert ab. Den BC0-Eigner für den Befund liest er beim Schreiben aus der DB, wie `kp_existiert`/`system_ids`.
- Keine DDL-Änderung.

**Tech Stack:** Python 3.11, psycopg 3 / psycopg_pool, pytest, PostgreSQL 17 (Test-Container), uv.

**Spec:** `bc1-context-discovery/design/Spec-C1a-Eigner-und-Version3.md` (Entwurf 3, abgenommen 24.10.2026).

**Geprüft:** Zweitmeinung Codex in zwei Runden.
- Runde 1 zum Entwurf: 11 Befunde.
- Runde 2 zur Überarbeitung: 3 neue Fehler, 2 Kleinpunkte.

Alle sind eingearbeitet. Die Einordnung steht am Ende.

**Zwei Abweichungen von der Spec**, beide vom Verfasser entschieden. Beide wurden von der BC1-Projektleitung am 24.10. bestätigt, die Spec ist angeglichen.

1. **Der Writer liest den BC0-Eigner beim Schreiben**, statt ihn aus dem Startkontext durchzureichen. Laut Spec 1 ist die Bezugsbasis der jüngste Dienststart.
   - **Grund:** Das bestehende Writer-Muster liest BC0 ebenfalls beim Schreiben (`kp_existiert`, `system_ids`). So ist der Befund aktueller, und der Writer braucht keinen neuen Konstruktorparameter.
   - **Folge:** Ändert BC0 den Eigner während eines Interviews, vergleicht der Befund mit dem neuen Stand. Wer den alten Vorschlag bestätigt hat, bekommt dann einen Befund (Test in Task 6).
   - Der Vorschlag im Fragetext kommt weiter aus dem Startkontext.
2. **ANZAHL akzeptiert vorn ein Näherungswort:** `etwa`, `ca.`, `circa`, `ungefähr`, `rund`, `im Schnitt`, `durchschnittlich`. Sonst wäre die häufige Antwort „etwa 3" ungültig, und das Interview müsste nachfragen. *(Korrigiert nach Codex: `ZAHL` akzeptiert solche Wörter heute nur zusammen mit einer Periode, nicht allein. Die Erweiterung ist also neu und hier eigens begründet.)*

## Global Constraints

- Arbeitsverzeichnis `coe-factory/bc1-context-discovery/`, Zweig `bc1-c1a-eigner-version3`.
- Tests mit `uv run pytest … -q -W error`. DB-Tests brauchen `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres`, sonst werden sie übersprungen.
- **TDD-Guard aktiv, NIE umgehen.** Bei einem Block das Skill `tdd-guard` aufrufen und jeden neu gelösten Block dort nachtragen.
- **Ein neuer Test je Edit.**
  - Für jede **Verhaltensänderung** gilt ein eigener Zyklus: RED sehen, dann genau dafür implementieren.
  - **Regressionstests** prüfen bestehendes Verhalten oder einen Fall, den eine schon gebaute Regel abdeckt. Sie dürfen sofort grün sein und sind in den Steps mit *(Regression)* markiert.
  - Kein künstlicher Produktfehler, um RED zu erzwingen.
- **Bestandsaufrufer und Bestandstests mitziehen:** Jede Signatur- oder Verhaltensänderung wird im selben Task in allen Aufrufern und betroffenen Tests nachgezogen (`git grep -n '<name>' -- bc1_core bc1_service tests`). Am Ende jedes Tasks ist die **volle Suite mit DB grün**.
- `SCHEMA_VERSION_CTX = "1.2"`. Der kontextfreie Zweig (1.0) bleibt unverändert.
- Aus BC0 nur mit `company_id`-Filter lesen. `mandant_rollen` ist eine Tabelle (Recht über `bc_leser`), `v_prozesse_lesen` eine Sicht.
- `process_owner_rolle_id` = der Wert von `process_owner_role` mit Status `gueltig`, sonst `NULL`. Keine zweite Prüfung gegen den Kontext.
- Befund-Schlüssel `eigner_rolle_abweichung` mit genau `process_id`, `interview_rolle`, `bc0_rolle`. Logzeile `eigner_rolle_abweichung session=%s kp=%s interview=%s bc0=%s`, nur IDs.
- Keine DDL-Änderung außer der SELECT-Vorprüfung in `prozessprofil.sql` Abschnitt 0. Die Sollsignatur bleibt gleich.
- Deutsche Anführungszeichen („ ") nie in Python-String-Literalen.
- `contracts/bc1-to-bc2/` erst ändern, wenn BC2 in #286 zugestimmt hat (Task 8). **Ohne Zustimmung kein Merge.** *(Geändert am 24.10. abends: BC2 hat nicht geantwortet, die BC1-Projektleitung geht von Zustimmung aus — Spec, Nachtrag im Kopf. Vertrag als Fassung 1.4 geändert.)*
- Kein Push, kein PR, kein Posten ohne OK der BC1-Projektleitung. **Pause nach jedem Task** für das Go.
- Commit-Nachrichten enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Bloßes „ja" auf die Eigner-Frage.** Der Extraktor liefert dann `process_owner_role = "ja"`. Erwartet: Das Feld ist im Turn-Ergebnis nicht `gueltig`, das Interview fragt B3 erneut, und es entsteht kein Spaltenwert. → Test über `process_turn` in Task 5, Spalte in Task 6.
2. **„etwa 3" / „ca. 3 Fälle" auf D4** sind gültig, Ergebnis `3`. „1 Fall pro Woche" ist ungültig. → Task 2.
3. **Gleiche Rollen-ID bei beiden Mandanten mit anderer Bezeichnung, dazu eine Rolle nur bei Mandant B.** Mandant A sieht nur seine Bezeichnungen und kann die B-Rolle nicht wählen. → Tasks 3 und 5.
4. **Die BC0-Eigner-Rolle ist stillgelegt.** Dann gibt es keinen Vorschlag, und die Rolle ist nicht wählbar (Task 5). Der Befund vergleicht trotzdem mit ihr, also `bc0_rolle` = die stillgelegte Rolle (Task 6).
5. **Die gewählte Rolle wird nach einem gescheiterten Abschluss stillgelegt, dann folgen Neustart und Recovery-Replay.** Erwartet: Die Zeile wird `fertig`, die Spalte trägt die gewählte Rolle, und im JSON bleibt `process_owner_role` `gueltig`. → Bau-Test und API-Recovery-Test in Task 6.

---

## Dateistruktur

| Datei | Task |
|---|---|
| `tests/db_fixture.py`, `tests/test_db_fixture.py` | 1 |
| `bc1_core/feldtypen.py`, `tests/test_feldtypen.py` | 2 |
| `bc1_service/bc0_lesepfade.py`, `tests/test_bc0_lesepfade.py` | 3 |
| `bc1_service/discovery_paket.py`, `bc1_service/start.py`, `bc1_service/db/prozessprofil.sql`, `tests/test_start.py`, `tests/test_discovery_paket.py`, `tests/test_ddl_einspielen.py` | 4 |
| `bc1_service/discovery_paket.py`, `bc1_service/use_case_testprofile.py` (nur Eigner-Werte), `tests/test_discovery_paket.py`, `tests/test_api_profil.py`, `tests/test_use_case_testprofile.py` (Kontext, Gerüst) | 5 |
| `bc1_service/profil_writer.py`, `tests/test_profil_bau.py`, `tests/test_profil_writer.py`, `tests/test_use_case_testprofile.py` (Spaltenerwartung) | 6 |
| `bc1_service/use_case_testprofile.py`, `tests/test_use_case_testprofile.py` | 7 |
| `README.md`, `bc1_service/db/EINSPIELEN.md`, `design/Abschlussplan-BC1.md`, `design/Spec-C1a-…`, `contracts/bc1-to-bc2/*` | 8 |

---

### Task 1: Testdaten — Rollen und Eigner je Mandant

**Files:** Modify `tests/db_fixture.py` (`_testdaten`) · Test `tests/test_db_fixture.py`

**Interfaces — Produces** (Testdaten für die Tasks 3–6):

| | Mandant A | Mandant B |
|---|---|---|
| Rollen | `R-01` Sachbearbeitung · `R-02` Einkauf A · `R-03` Archiv (`aktiv = false`) | `R-01` Sachbearbeitung · `R-02` Einkauf B · `R-04` Nur bei B |
| Eigner `KP-01` | Person `P-01` mit Rolle `R-02` | Person `P-01` mit Rolle `R-04` |
| Eigner `KP-02` | Person `P-02` mit Rolle `R-03` (stillgelegt) | keiner |
| Eigner `KP-03` | — | keiner |

Personen-IDs `P-01`/`P-02` sind je Mandant; spätere Ergänzungen (Task 5) nehmen freie IDs ab `P-05`.

- [ ] **Step 1: Failing test** `test_geruest_liefert_eigner_je_mandant`: Als `bc1_role` `owner_rolle_id` aus `v_prozesse_lesen` lesen. Erwartet:
  - A: `{KP-01: 'R-02', KP-02: 'R-03'}`
  - B: `{KP-01: 'R-04', KP-02: None, KP-03: None}`
- [ ] **Step 2:** `uv run pytest tests/test_db_fixture.py -q -k eigner`, erwartet FAIL.
- [ ] **Step 3:** Daten in `_testdaten` ergänzen:
  - `mandant_rollen`
  - `ref_personen`, mit gesetzter `funktion` wegen `ck_person_bezeichnet`
  - `prozess_personen` mit `funktion = 'eigner'`

  Keine Klarnamen.
- [ ] **Step 4:** Test grün, dazu die volle Suite mit DB. Erwartet: `733 passed` plus der neue Test, kein Bestandstest bricht (am 24.10. geprüft: kein Test rechnet mit fehlendem `R-02`).
- [ ] **Step 5:** Commit `BC1 C1a: Testdaten mit Rollen und Eignern je Mandant`.

### Task 2: Feldtyp `ANZAHL`

**Files:** Modify `bc1_core/feldtypen.py` · Test `tests/test_feldtypen.py`

**Interfaces — Produces:**
- `ANZAHL: Feldtyp`, Name `"anzahl"`, Validator `_ist_nichtnegative_zahl` (vorhanden)
- `_normalisiere_anzahl(wert: str) -> str`

- [ ] **Step 1: Failing test** `test_anzahl_gueltig`, parametrisiert. Eingabe → normalisierter Wert, Validator wahr:
  - `"0"` → `"0"`, `"1"` → `"1"`, `"3"` → `"3"`, `"2,5"` → `"2.5"`, `"1.000"` → `"1000"`
  - `"3 Fälle"` → `"3"`, `"1 Fall"` → `"1"`, `"3 Vorgänge pro Durchlauf"` → `"3"`
  - `"etwa 3"` → `"3"`, `"ca. 3 Fälle"` → `"3"`, `"im Schnitt 2 Vorgänge je Durchlauf"` → `"2"`
- [ ] **Step 2:** `uv run pytest tests/test_feldtypen.py -q -k anzahl`, erwartet FAIL (ImportError).
- [ ] **Step 3: Implementieren.** Ein einziges Muster, ohne Beachtung von Groß- und Kleinschreibung, per Fullmatch:

  ```python
  _ANZAHL_MUSTER = re.compile(
      rf"\s*(?:(?:etwa|ca\.|circa|ungefähr|ungefaehr|rund|im schnitt|durchschnittlich)\s+)?"
      rf"({_ZAHL_TOKEN})"
      rf"(?:\s+(?:fall|fälle|faelle|vorgang|vorgänge|vorgaenge|stück|stueck))?"
      rf"(?:\s+(?:je|pro)\s+durchlauf)?\s*", re.IGNORECASE)
  ```

  Bei Treffer `_zahl_aus_token(gruppe)`. Ist das Ergebnis endlich, `_formatiere(...)`, sonst bleibt `wert` unverändert und ist damit ungültig.
- [ ] **Step 4:** Grün.
- [ ] **Step 5:** *(Regression)* `test_anzahl_ungueltig`, Validator nach der Normalisierung falsch für: `"5 pro Woche"`, `"15 im Monat"`, `"40 im Jahr"`, `"5/Monat"`, `"5 täglich"`, `"3 %"`, `"3 Stunden"`, `"1 Fall pro Woche"`, `"-1"`, `""`, `"3 oder 4"`, `"9" * 400`. Erwartet sofort grün, weil der Fullmatch das trägt.
- [ ] **Step 6:** Commit `BC1 C1a: Feldtyp ANZAHL (reine Anzahl, keine Periode)`.

### Task 3: Lesepfade `rollen` und `eigner_rollen`

**Files:** Modify `bc1_service/bc0_lesepfade.py` · Test `tests/test_bc0_lesepfade.py`

**Interfaces:**
- Consumes: Testdaten aus Task 1.
- Produces: `rollen(conn, company_id: str) -> list[tuple[str, str]]`, nur `aktiv`, sortiert nach `rolle_id`.
- Produces: `eigner_rollen(conn, company_id: str, process_ids: Sequence[str]) -> dict[str, str | None]`. Ein Schlüssel je angefragter, in `v_prozesse_lesen` vorhandener Prozess-ID. `None` heißt: keine ableitbare Eigner-Hauptrolle.

- [ ] **Step 1:** `test_rollen_nur_aktive_des_mandanten` (DB, als `bc1_role`): A → `[("R-01","Sachbearbeitung"),("R-02","Einkauf A")]`. RED, dann `rollen` nach dem Muster von `system_ids` umsetzen, GREEN.
- [ ] **Step 2:** *(Regression)* `test_rollen_mandantengetrennt`: B → `[("R-01","Sachbearbeitung"),("R-02","Einkauf B"),("R-04","Nur bei B")]`.
- [ ] **Step 3:** `test_eigner_rollen_je_prozess`: A, `["KP-01","KP-02"]` → `{"KP-01":"R-02","KP-02":"R-03"}`. RED, dann umsetzen mit `process_id = ANY(%s)`, GREEN.
- [ ] **Step 4:** *(Regression)* Zwei weitere Fälle:
  - `test_eigner_rollen_ohne_eigner_ist_none`: B, `["KP-02"]` → `{"KP-02": None}`
  - `test_eigner_rollen_mandantengetrennt`: A, `["KP-03"]` → `{}`
- [ ] **Step 5:** Commit `BC1 C1a: Lesepfade Rollen und Eigner-Rolle`.

### Task 4: Kontext, Startabbruch, Fingerabdruck, Vorprüfung

**Files:**
- Modify: `bc1_service/discovery_paket.py` (`Bc0Kontext`, `_ctx_fingerprint`), `bc1_service/start.py` (`lade_kontext`, Meldung), `bc1_service/db/prozessprofil.sql` (Abschnitt 0)
- Test: `tests/test_start.py`, `tests/test_discovery_paket.py`, `tests/test_ddl_einspielen.py`

**Interfaces:**
- Consumes: `rollen`, `eigner_rollen` (Task 3).
- Produces: `Bc0Kontext.rollen: tuple[tuple[str, str], ...] = ()`.
- Produces: `Bc0Kontext.eigner: tuple[tuple[str, str | None], ...] = ()`. Sortiert nach Prozess-ID. Es sind die Kernprozesse der Anfrage-TPs, also der Präfix vor dem ersten Punkt.
- Produces: `start.MELDUNG_KEINE_ROLLEN = ("Für diesen Mandanten ist keine aktive Rolle erfasst. Das Interview fragt nach der verantwortlichen Rolle und kann erst geführt werden, wenn BC0 Rollen gepflegt hat.")`

- [ ] **Step 1:** `test_start_laedt_rollen_und_eigner` (DB): Eine Anfrage auf A KP-01 ergibt `rollen` wie in Task 3 und `eigner == (("KP-01","R-02"),)`. RED, dann Felder anlegen und in `lade_kontext` laden, GREEN.
- [ ] **Step 2:** `test_start_ohne_aktive_rolle_bricht_ab` (DB): Alle Rollen von A auf `aktiv = false` setzen. Dann wirft `lade_kontext` einen `RuntimeError` mit `MELDUNG_KEINE_ROLLEN`. RED, dann die Prüfung **nach** den Anfrage-Prüfungen einbauen, GREEN.
- [ ] **Step 3:** `test_fingerabdruck_aendert_sich_mit_den_rollen_ids`: Zwei Kontexte, die sich nur in den Rollen-IDs unterscheiden, haben verschiedene ctx-Hashes. RED, dann `"rollen": sorted(r for r, _ in kontext.rollen)` in `_ctx_fingerprint` aufnehmen, GREEN. Bestehende Hash-Erwartungen in Tests, falls es welche gibt, nachziehen.
- [ ] **Step 4:** *(Regression)* `test_fingerabdruck_unabhaengig_von_eigner_und_bezeichnung`: gleiche Rollen-IDs, andere Bezeichnung und anderer Eigner, gleicher Hash.
- [ ] **Step 5:** `test_vorpruefung_verlangt_select_auf_mandant_rollen` (DB, `test_ddl_einspielen.py`): `REVOKE SELECT ON mandant_rollen FROM bc_leser`, dann wirft `spiele_ddl_ein`, und die Meldung enthält `mandant_rollen`. RED, dann `'mandant_rollen'` in die SELECT-Liste von Abschnitt 0 aufnehmen, GREEN. Die Sollsignatur wird nicht neu erzeugt, `test_fall_2_…` bleibt grün.
- [ ] **Step 6:** Volle Suite mit DB grün. Commit `BC1 C1a: Rollen und Eigner im Startkontext, Fingerabdruck, Vorpruefung`.

### Task 5: Paket 1.2 — B3 als Rollenauswahl, D4 als Anzahl, E2 je Schrittlauf

**Files:**
- Modify: `bc1_service/discovery_paket.py`; `bc1_service/use_case_testprofile.py`, dort nur `owner="R-05"` in allen drei Fällen
- Test: `tests/test_discovery_paket.py`, `tests/test_api_profil.py`, `tests/test_use_case_testprofile.py`

**Interfaces:**
- Consumes: `Bc0Kontext.rollen/eigner` (Task 4), `ANZAHL` (Task 2).
- Produces, im Kontext-Zweig:
  - `SCHEMA_VERSION_CTX == "1.2"`
  - `process_owner_role` hat Typ `AUSWAHL(*rolle_ids)` und bleibt Pflicht
  - `executions_per_run` hat Typ `ANZAHL`
  - E2 hat den neuen Text

**Festgelegte Texte:**
- B3: `"Welche Rolle ist für diesen Prozess verantwortlich? Bitte nennen Sie die Rolle (" + ", ".join(f"{id} = {bez}" …) + ")."`
- Mit Vorschlag kommt `f" Laut BC0 ist das {bez} ({id})."` dazu.
- E2: `"Wie lange dauert ein einzelner Lauf dieses Schritts im Schnitt?"`

**Vorschlagsregel:** Der Vorschlag erscheint genau dann, wenn `kontext.eigner` **genau einen** Eintrag hat, dessen Rolle nicht `None` ist und in `kontext.rollen` vorkommt, also aktiv ist.

- [ ] **Step 1:** `test_kontext_version_ist_1_2`. RED, dann Konstante auf `"1.2"`, GREEN.
- [ ] **Step 2:** `test_b3_ist_auswahl_der_aktiven_rollen`: Gültig sind genau die Rollen-IDs des Kontexts. `"R-03"` und `"ja"` sind ungültig. Der Text enthält `"R-01 = Sachbearbeitung"` und `"nennen"`. RED, dann B3 im Kontext-Zweig wie E5 umsetzen, GREEN.
- [ ] **Step 3:** `test_b3_vorschlag_bei_einem_kernprozess_mit_aktiver_rolle`: `eigner=(("KP-01","R-02"),)` → der Text enthält `"Laut BC0 ist das Einkauf A (R-02)."`. RED, dann Vorschlagsregel einbauen, GREEN.
- [ ] **Step 4:** *(Regression)* Text ohne `"Laut BC0"` in drei Fällen:
  - `test_b3_kein_vorschlag_bei_stillgelegter_rolle`: `(("KP-02","R-03"),)`
  - `test_b3_kein_vorschlag_bei_mehreren_kernprozessen`
  - `test_b3_kein_vorschlag_ohne_eigner`: `(("KP-01", None),)`
- [ ] **Step 5:** `test_ja_auf_eigner_frage_bleibt_ungueltig_und_wird_erneut_gefragt` (Review Focus 1). Ein laufender Turn liefert keine Feldstatus im Payload, und der Dialog fragt das erste offene Pflichtfeld. Der Test stellt den Gesprächsstand deshalb bis B3 her:
  - **Turn 1** liefert per `FakeLLM` gültige Werte für `request_intent`, `request_goal`, `scope_focus` und `process_name`. Damit ist B3 das erste offene Pflichtfeld.
  - **Turn 2** mit der Nachricht `"ja"` liefert den Kandidaten `("process_owner_role","ja")`.
  - **Erwartet:** `store.load(sid).values["process_owner_role"].status` ist nicht `GUELTIG`, und `antwort["payload"]["feld"] == "process_owner_role"`.

  Je nachdem, was Step 2 schon trägt, ist der Test RED oder *(Regression)*; der Ausführende vermerkt, was zutrifft.
- [ ] **Step 6:** `test_d4_ist_anzahl` (Typname `"anzahl"`) und `test_e2_fragt_nach_einem_schrittlauf` (wörtlicher Text), je ein eigener RED/GREEN-Zyklus.
- [ ] **Step 7:** *(Regression)* `test_kontextfreier_zweig_unveraendert`: Version 1.0, B3 Freitext, D4 `ZAHL`, alter E2-Text.
- [ ] **Step 8: Bestandstests auf B3 als Auswahl umstellen** (Codex Befund 4):
  - `tests/test_api_profil.py`: Der Kontext bekommt `rollen=(("R-01","Sachbearbeitung"),)`, die B3-Antwort `"R-01"` statt `"Vertriebsleitung"`, die Versionsassertion `1.2+ctx-`.
  - `tests/test_use_case_testprofile.py`:
    - `KONTEXT` bekommt `rollen=(("R-05","Logistik"),)` und `eigner=(("KP-05","R-05"),("KP-06","R-05"))`.
    - `_noro_geruest` legt bei Mandant A `R-05` „Logistik" an, dazu Person `P-05` (`funktion` gesetzt, Rolle `R-05`) als Eigner von KP-05 und KP-06.
  - `bc1_service/use_case_testprofile.py`: `owner="R-05"` in allen drei Fällen. Sonst nichts, Version 3 kommt in Task 7.
  - Danach die Versionserwartungen nachziehen:
    - `git grep -n "1.1+ctx" -- tests`
    - **ausdrücklich** auch die Regex `r"1\.1\+ctx-[0-9a-f]{16}"` in `test_discovery_paket.py` (`test_mit_kontext_traegt_das_paket_den_ctx_fingerprint`), die die einfache Suche nicht findet, auf `1\.2`

    Synthetische 1.1-Testpakete in anderen Tests bleiben, wie sie sind.
- [ ] **Step 9:** Volle Suite ohne und mit DB grün. Commit `BC1 C1a: Paket 1.2 — Eigner-Auswahl, D4 Anzahl, E2 je Schrittlauf`.

### Task 6: Writer — Spalte und Befund

**Files:** Modify `bc1_service/profil_writer.py` (`baue_profilinhalt`, `ProfilWriter._abgleich`) · Test `tests/test_profil_bau.py`, `tests/test_profil_writer.py`, `tests/test_use_case_testprofile.py`

**Interfaces:**
- Consumes: Paket 1.2 (Task 5), `eigner_rollen` (Task 3).
- Produces: `baue_profilinhalt(state, package, *, kp_bekannt: Callable[[str], bool], bekannte_systeme: frozenset[str], bc0_eigner: Callable[[str], str | None]) -> Profilinhalt | None`.
- `ProfilWriter._abgleich` übergibt `bc0_eigner=lambda kp: bc0_lesepfade.eigner_rollen(conn, self._company_id, [kp]).get(kp)`.

**Testpakete:** `PAKET`/`VOLL_PAKET` in `test_profil_bau.py` haben kein B3. Ihre bestehenden Erwartungen `process_owner_rolle_id is None` (Zeilen 141, 269) **bleiben**, sie sichern den Fall „B3 fehlt". Für die neuen Tests kommt ein eigenes `EIGNER_PAKET` hinzu, `PAKET` plus `FieldSpec("process_owner_role", …, typ=AUSWAHL("R-01","R-02"))`. `_bau` reicht `bc0_eigner` durch, Default `lambda kp: None`.

- [ ] **Step 1:** `test_eigner_spalte_aus_gueltigem_b3`: `EIGNER_PAKET`, B3 `gueltig` `"R-02"`, ergibt `spalten["process_owner_rolle_id"] == "R-02"`. RED, dann Parameter einführen, Konstante „Etappe 1" streichen, Spalte aus `_payload_wert(profil, "process_owner_role")` nach dem Sweep ableiten, Aufrufer nachziehen, GREEN.
- [ ] **Step 2:** *(Regression)* Drei Fälle:
  - `test_eigner_spalte_null_bei_ungeloest`
  - `test_eigner_spalte_null_bei_ungueltigem_wert`: B3 `ungueltig` mit Wert `"ja"` (Review Focus 1)
  - `test_spalte_bleibt_bei_inzwischen_stillgelegter_rolle` (Review Focus 5): B3 `gueltig` `"R-03"` in einem Paket, dessen Auswahl R-03 nicht enthält, ergibt `"R-03"`.
- [ ] **Step 3:** `test_eigner_abweichung_ergibt_befund_und_warnung` (caplog): Wahl `"R-01"`, `bc0_eigner → "R-02"`, KP-01. Erwartet `befunde["eigner_rolle_abweichung"] == {"process_id":"KP-01","interview_rolle":"R-01","bc0_rolle":"R-02"}` und eine WARNING, die `eigner_rolle_abweichung session=` enthält. RED, dann nach dem Muster `kp_tp_diskrepanz` implementieren, GREEN.
- [ ] **Step 4:** *(Regression)* Drei Fälle:
  - `test_kein_befund_bei_gleicher_rolle`
  - `test_kein_befund_ohne_bc0_eigner`
  - `test_befund_vergleicht_mit_stillgelegter_bc0_rolle` (Review Focus 4): Wahl `"R-02"`, `bc0_eigner → "R-03"`, ergibt einen Befund mit `bc0_rolle == "R-03"`.
- [ ] **Step 5:** *(Regression, DB, `test_profil_writer.py`)* Dessen Testpaket bekommt B3, wie oben.
  - `test_interview_mit_abweichung_endet_fertig_mit_spalte_und_befund`: Mandant A, KP-01, Wahl `"R-01"` (BC0: R-02). Ergebnis: Zeile `fertig`, Spalte `R-01`, Befund im `profil`. Ein `UPDATE … SET process_owner_rolle_id = 'R-02'` scheitert mit `eingefroren`.
  - `test_befund_nimmt_den_bc0_stand_beim_schreiben` (Abweichung 1): Nach einem nichtterminalen Turn wechselt BC0 den Eigner von KP-01 im Gerüst auf `R-01`. Im Terminal-Turn mit Wahl `"R-02"` entsteht ein Befund mit `bc0_rolle == "R-01"`.
  - `test_geloeschte_rolle_bricht_erst_den_abschluss`: Die gewählte Rolle wird vor dem ersten Schreiben gelöscht. Im Gerüst räumt die Kaskade `ref_personen`/`prozess_personen` mit. Ein nichtterminaler Turn liefert `None` und `profil_write_uebersprungen` im Log. Im Terminal-Turn wirft `reconcile` einen `ProfilWriteError`.
  - `test_recovery_mit_inzwischen_stillgelegter_rolle` (Review Focus 5, `tests/test_api_profil.py`, nach dem Muster `test_recovery_nach_neustart_mit_geaendertem_ctx_holt_den_write_nach`):
    1. Der Abschluss scheitert mit 503, weil ein fremder Draft blockiert. Danach wird der Draft entfernt.
    2. Die gewählte Rolle wird auf `aktiv = false` gesetzt. Der Neustart nutzt einen Kontext, dessen `rollen` sie nicht mehr enthält, also einen anderen Fingerabdruck.
    3. Replay mit der alten `schema_version`.

    Erwartet: Die Zeile ist `fertig`, `process_owner_rolle_id` ist die gewählte Rolle, und im `profil` ist `process_owner_role` `gueltig` mit derselben ID.
- [ ] **Step 6:** `tests/test_use_case_testprofile.py`: Der Spaltentest liest `process_owner_rolle_id` und `befunde` bisher nicht. Abfrage und Assertions werden **ergänzt**: `process_owner_rolle_id = 'R-05'`, `profil->'befunde'` ohne `eigner_rolle_abweichung`. Danach volle Suite mit DB grün. Commit `BC1 C1a: Writer fuellt process_owner_rolle_id, Befund bei Abweichung von BC0`.

### Task 7: Testprofile Version 3 — Anfragen als Parameter, erst prüfen, BC0 melden, wiederholbar

**Files:** Modify `bc1_service/use_case_testprofile.py` · Test `tests/test_use_case_testprofile.py`

**Interfaces:**
- Consumes:
  - Paket 1.2 und Writer (Tasks 5 und 6)
  - aus `bc1_service.start`: `lade_kontext`, `melde_interview_beginn`
  - aus `bc0_lesepfade`: `anfrage_status`
  - aus `bc0_meldungen`: `baue_melder`
- Produces: `Fall(session_id: str, fokus_tp: str, nachrichten)`. Das Feld `anfrage_id` entfällt.
- Produces: `fuehre_interview(store, paket, fall, *, company_id, anfrage_id: str, writer=None) -> dict`.
- Produces: `@dataclass(frozen=True) class Vorpruefung: fehler: tuple[str, ...]; erledigt: frozenset[str]`. `erledigt` enthält die Sitzungsnummern, die schon fertig zur selben Anfrage gebunden sind.
- Produces: `pruefe_anfragen(pool, company_id: str, anfragen: Mapping[str, str]) -> Vorpruefung`. Schlüssel ist der Fokus-TP, Wert die Anfrage.
- Produces: `schreibe_testprofile(pool, company_id: str, anfragen: Mapping[str, str], melder=None) -> list[dict]`.
- CLI:
  - `--anfrage TP=A-JJJJ-NN` ist mehrfach erlaubt und mit `--echt` für alle Fälle Pflicht.
  - Der Melder wird nur mit `--echt` erzeugt, über `baue_melder(os.environ, company_id)`. `BC1_BC0_MELDUNGEN=aus` liefert `None`.

**Werte Version 3:**
- Sitzungsnummern `uc1-reisebuchung-testdaten-v3`, `uc2-wissensbasis-testdaten-v3`, `uc3-consultant-matching-testdaten-v3`
- `faelle="1"` in allen drei Fällen
- `KENNZEICHEN = "Testdaten Use-Case-Definition 24.08., nicht erhoben, Version 3. Quelle: Projektgruppe CoE-Factory."`
- Alles Übrige unverändert, auch `owner="R-05"` aus Task 5.

**`pruefe_anfragen` je Fall, in dieser Reihenfolge:**
1. **Anfrage fehlt** in `anfragen`: Fehler `f"Für {tp} fehlt --anfrage {tp}=A-JJJJ-NN."`.
2. **Bindung vorhanden:** Bindung der Sitzungsnummer lesen, wie `ProfilWriter._bindung`, plus `anfrage_id` der gebundenen Zeile.
   - Gebunden an eine **andere** Anfrage: Fehler `f"{session_id} ist schon zu {alt} geschrieben; für {neu} braucht es eine neue Sitzungsnummer."`
   - Gebunden an **dieselbe** Anfrage und `fertig`: Die Sitzungsnummer kommt in `erledigt`. Status und Kontext werden **nicht** mehr geprüft, die Anfrage darf inzwischen auf `im_interview` oder `am_gate` stehen.
3. **Sonst** `lade_kontext(conn, company_id, anfrage)`. Ein `RuntimeError` geht als `str(fehler)` in die Fehlerliste.
4. **Teilprozess fehlt:** `kontext.teilprozesse` besteht aus Paaren `(ID, Name)`, geprüft wird deshalb gegen die IDs: Ist `fall.fokus_tp not in dict(kontext.teilprozesse)`, Fehler `f"Die Anfrage {anfrage} umfasst {tp} nicht."`.

**Ablauf von `schreibe_testprofile`:**
1. **Prüfen.** Bei Fehlern `RuntimeError` mit allen Meldungen, zeilenweise. Es wird nichts gemeldet und nichts geschrieben.
2. **Melden**, nur wenn `melder is not None`: `melder.pruefe_konto()`, dann `melde_interview_beginn(melder, anfrage, anfrage_status(...))` für jede **nicht erledigte** Anfrage.
3. **Schreiben**, für alle nicht erledigten Fälle. Erledigte erscheinen im Ergebnis als `{"session_id": …, "status": "fertig", "vollstaendigkeit": None, "vermerk": "bereits geschrieben"}`.
4. **Gate**, nur wenn `melder is not None`: `melder.ziehe_gate_nach(anfrage)` für jede Anfrage, deren Fall jetzt `fertig` ist, die erledigten eingeschlossen.
   - So holt ein zweiter Aufruf mit denselben Parametern ein gescheitertes Gate nach.
   - Ein Fehler hier ergibt nur eine Warnzeile in der Ausgabe, wie `_gate_im_hintergrund`. Kein Abbruch.

`main` fängt den `RuntimeError` aus Schritt 1, schreibt die Meldungen nach `stderr` und gibt `1` zurück, ohne Traceback.

**Ausgabe:** Für einen Eintrag mit `vermerk` gibt `main` die Zeile `OK {session_id}: bereits geschrieben` aus. Alle anderen Einträge behalten die bisherige Zeile mit `vollstaendigkeit`. Der Exitcode bleibt 0, wenn alle Einträge `fertig` sind.

**Tests:** Der Ersatz-Melder zeichnet Aufrufe auf. Für die Gate-Tests setzt er die Anfrage im Gerüst auf `am_gate`, wie BC0 es täte. CLI-Tests setzen `BC1_BC0_MELDUNGEN=aus` oder ersetzen `baue_melder`. Die Anfragen kommen aus `ANFRAGEN = {"KP-06.TP-2":"A-2026-01","KP-05.TP-1":"A-2026-02","KP-06.TP-1":"A-2026-03"}`. Bestehende Tests werden auf die neuen Signaturen gezogen.

- [ ] **Step 1:** `test_version_3_werte`: Für alle Fälle gilt `executions_per_run = "1"`, Sitzungsnummer endet auf `-v3`, die Kennzeichnung enthält `"Version 3"`. RED, dann die Werte ändern, GREEN. `test_gespeicherte_spalten_…` auf Version 3 ziehen: `executions_per_run = 1`, Frequenzen und Dauern wie bisher.
- [ ] **Step 2:** `test_fehlende_anfrage_wird_gemeldet`. RED, dann `Fall` ohne `anfrage_id`, `anfragen`-Parameter, `pruefe_anfragen` (Regel 1 und 3), GREEN.
- [ ] **Step 2a:** *(Regression)* `test_vorpruefung_bereit`: Mit `ANFRAGEN` im frischen Gerüst ist `Vorpruefung.fehler == ()` und `erledigt == frozenset()`. Der Test sichert den positiven Weg, nach Regel 4 erneut laufen lassen.
- [ ] **Step 3:** `test_erst_pruefen_dann_schreiben`: Eine Anfrage steht auf `eingegangen`. Ergebnis: `RuntimeError` nennt sie, **0** Zeilen, 0 Melder-Aufrufe. *(Regression nach Step 2, falls schon grün.)*
- [ ] **Step 4:** `test_falsch_zugeordnete_anfrage_wird_vor_dem_schreiben_erkannt`: Für den zweiten Fall wird eine interviewbare Anfrage eines anderen TP übergeben. Ergebnis: 0 Zeilen, 0 Melder-Aufrufe. RED, dann Regel 4, GREEN.
- [ ] **Step 5:** `test_andere_anfrage_fuer_geschriebenen_fall_wird_abgelehnt`: erst ein Lauf mit `ANFRAGEN`, dann ein zweiter mit einer anderen Anfrage für KP-05.TP-1. Erwartet: Fehler mit `"neue Sitzungsnummer"`, keine neue Zeile. RED, dann Regel 2 (andere Anfrage), GREEN.
- [ ] **Step 6:** `test_melder_reihenfolge`: Aufrufe in dieser Reihenfolge: `pruefe_konto`, dreimal `melde_interview_laeuft`, dreimal `ziehe_gate_nach`. Zum Zeitpunkt jedes Gate-Aufrufs ist die zugehörige Zeile bereits `fertig`, der Ersatz-Melder prüft das in der DB. RED, dann Ablaufschritte 2 und 4, GREEN.
- [ ] **Step 7:** `test_zweiter_lauf_holt_gescheitertes_gate_nach`, über `main` mit ersetztem `baue_melder`.
  - **Lauf 1:** `ziehe_gate_nach` wirft für A-2026-02. Exit 0, eine Warnzeile.
  - **Lauf 2**, mit denselben Parametern: Exit 0, dreimal `bereits geschrieben` in der Ausgabe, keine neue Zeile, kein `melde_interview_laeuft`, und `ziehe_gate_nach` wird für alle drei Anfragen aufgerufen.

  RED, dann Regel 2 (dieselbe Anfrage, erledigt), Gate für erledigte und die Ausgabezeile umsetzen, GREEN.
- [ ] **Step 8:** *(Regression)* Drei Fälle:
  - `test_ohne_melder_wird_nichts_gemeldet`: `melder=None`, 3 fertige Zeilen, kein Fehler
  - `test_main_ohne_echt_erzeugt_keinen_melder`: Trockenlauf, `baue_melder` wird nicht aufgerufen
  - `test_main_echt_ohne_bereite_anfrage_exit_1_ohne_traceback`: ersetzt `…_bricht_im_start_ab…`; Exit `1`, Meldung auf `stderr`
- [ ] **Step 9:** Volle Suite mit DB grün. Docstring nennt Version 3 und den Ablauf. Commit `BC1 C1a: Testprofile Version 3 — Anfragen als Parameter, erst pruefen, BC0 melden, wiederholbar`.

### Task 8: Doku, Spec-Angleich, Vertrag

**Files:**
- `README.md`
- `bc1_service/db/EINSPIELEN.md`
- `design/Abschlussplan-BC1.md`
- `design/Spec-C1a-Eigner-und-Version3.md`
- `contracts/bc1-to-bc2/README.md`, `contracts/bc1-to-bc2/prozessprofil.schema.json`: **nur nach Zustimmung von BC2 in #286**

- [ ] **Step 1: README.** Neuer Aufruf `uv run python -m bc1_service.use_case_testprofile --company-id <uuid> --anfrage KP-06.TP-2=A-… --anfrage KP-05.TP-1=A-… --anfrage KP-06.TP-1=A-… [--echt]`, dazu der Hinweis auf die BC0-Meldungen und den wiederholbaren Lauf.
- [ ] **Step 2: EINSPIELEN Abschnitt 1:** `mandant_rollen` als Leserecht des Dienstes.
- [ ] **Step 3: Spec angleichen.** Die zwei Abweichungen aus dem Plankopf werden übernommen, sobald die BC1-Projektleitung sie bestätigt hat.
- [ ] **Step 4: Abschlussplan.**
  - C1a als gebaut eintragen.
  - Kleinpunkt „Neu 06.10." (10) „erst alle Anfragen prüfen" ist erledigt.
  - Rückstellungen: Fragesteller vorbelegen (bleibt); Eigner-Schnappschuss je Sitzung (bewusst nicht).
  - Zeile „Nächstes Go" aktualisieren.
- [ ] **Step 5: Abstimmungen mit Nachweis.**
  - Erledigt: #286 Teil 1 (24.10., `#issuecomment-6382724956`) und Teil 2 (24.10., `#issuecomment-6382974986`).
  - BC0-Brief vom 24.10.: wird von der BC1-Projektleitung verschickt, Antwort offen.
  - Eintrag im PR-Text.
- [x] **Step 6: Vertrag**, erst nach Zustimmung von BC2 in #286. Liste aus Spec Abschnitt 8, Wortlaut nach der Antwort von BC2. *(24.10. abends: ohne Antwort, von Zustimmung ausgegangen; Fassung 1.4.)*
- [ ] **Step 7: Commits.**
  - Doku: `BC1 C1a: Doku, Spec-Angleich, Abschlussplan`.
  - Vertrag, getrennt: `BC1→BC2 Vertrag: Eigner-Spalte, D4, E2 (mit BC2 abgestimmt in #286)`.

### Task 9: Abschluss und Auslieferung

- [ ] **Step 1:** Volle Suite mit und ohne DB, `-W error`. Ergebnis notieren.
- [ ] **Step 2: Gegenproben** auf einer Wegwerfkopie im Scratchpad. Bei jeder muss **mindestens** der zugeordnete Wächtertest wegen der beabsichtigten Verhaltensänderung rot werden:

  | Gegenprobe | Wächtertest |
  |---|---|
  | Vorschlagsregel ignoriert `aktiv` | `…stillgelegter_rolle` |
  | Spalte wieder `None` | `…aus_gueltigem_b3` |
  | Befund ohne Abweichungsprüfung | `…bei_gleicher_rolle` |
  | `ANZAHL` akzeptiert Perioden | `test_anzahl_ungueltig` |
  | Regel 4 entfernt | `…falsch_zugeordnete…` |
  | Gate nicht für erledigte | `…holt_gescheitertes_gate_nach` |
- [x] **Step 3: Zweitmeinung** auf den ganzen Zweig, nur lesend (unabhängiges Review und Codex). Befunde nach Schwere einordnen.
- [x] **Step 4: Befund an die BC1-Projektleitung.** Push und PR erst nach OK. Merge erst nach Zustimmung von BC2 (Task 8 Step 6). *(24.10.: PR #341 nach OK gemergt; BC2 hat nicht geantwortet, Zustimmung angenommen, siehe Spec-Nachtrag.)*
- [x] **Step 5: Unmittelbar vor dem Deployment**, nach dem Merge und vor dem Neustart des Dienstes mit 1.2: nur lesend als `bc1_role` messen, Ziel `bc1.sessions` = 0 und `in_erhebung` = 0.
  - Gibt es Offenes, gilt das Spec-Verfahren: unter 1.1 abschließen oder nach K5 verwerfen, erst dann umstellen.
  - Die Messung aus dem PR ersetzt diese nicht.
  - *25.10.: gemessen vor dem Live-Lauf. Keine offene Sitzung, kein Entwurf `in_erhebung`, kein ausstehender Abschluss, Leserechte vollständig, `R-05` aktiv. Der Dienst ist damit noch nicht neu gestartet; vor dem Neustart wird erneut gemessen (Abschlussplan, Zeile B8).*
- [x] **Step 6: Live-Lauf Version 3**, erst wenn BC0 die Anfragen bereitgestellt hat (neue Anfrage für KP-05.TP-1, die anderen auf `zugeordnet`). Die BC1-Projektleitung stößt ihn an. Danach Termin und Ergebnis in #286 und #195.
  - *25.10.: bestanden.* Mit OK von BC0 hat BC1 A-2026-01 und A-2026-03 auf `zugeordnet` gesetzt und für KP-05.TP-1 die Anfrage A-2026-05 angelegt. Ergebnis: drei Profile Version 3 `fertig`, Vollständigkeit 1.0, Eigner `R-05`, keine Befunde, kein offener Entwurf; BC0 hat alle drei Anfragen auf `am_gate` gezogen. Ein zweiter Lauf hat nichts doppelt geschrieben („bereits geschrieben“). Gemeldet in #286, #195 und #206.

---

## Einordnung der Codex-Befunde zum Planentwurf (24.10.)

| # | Schwere | Befund | Umgang |
|---|---|---|---|
| 1 | Important | Feste v3-Sitzungsnummer bei einer anderen Anfrage liefert die alte Bindung zurück | Regel 2 in `pruefe_anfragen`, Test Task 7 Step 5 |
| 2 | Important | Vorprüfung gleicht den Fokus-TP nicht ab | Regel 4, Test Task 7 Step 4 |
| 3 | Important | Gate-Fehler im nächsten Lauf nicht nachholbar | Erledigte Fälle übersprungen, Gate auch für sie; Test Task 7 Step 7 |
| 4 | Important | Task 5 lässt API- und Testprofil-Tests rot | Task 5 Step 8 zieht sie mit, Eigner der Testfälle schon in Task 5 |
| 5 | Important | Testpakete in `test_profil_bau` haben kein B3 | Eigenes `EIGNER_PAKET`, Bestandserwartungen bleiben (Task 6) |
| 6 | Important | `melder=None` vs. unbedingte Aufrufe | Schritte 2 und 4 nur mit Melder, Regressionstests |
| 7 | Important | „Jeden Test RED" für Regressionsfälle unerfüllbar | Globale Regel präzisiert, *(Regression)* markiert |
| 8 | Important | Auslieferungsmessung zu früh | Task 9 Step 5 unmittelbar vor dem Deployment |
| 9 | Minor | Abstimmungen nicht als Schritte | Task 8 Step 5 mit Nachweis |
| 10 | Minor | Abdeckung im Review Focus zu weit behauptet | Präzisiert, Tests für „ja" über `process_turn` und für stillgelegten BC0-Eigner ergänzt |
| 11 | Minor | Gegenprobe „genau ihr Wächtertest" zu streng | „mindestens" |
| — | Sachfehler | Begründung „ZAHL akzeptiert Näherungswörter" falsch | Im Plankopf korrigiert |

**Runde 2 (zur überarbeiteten Fassung).** Codex bestätigt 7 der 11 alten Befunde als behoben, 3 als teilweise behoben (2, 3, 10), den Sachfehler als behoben. Neu:

| # | Schwere | Befund | Umgang |
|---|---|---|---|
| R2-1 | Important | Regel 4 vergleicht die TP-ID mit Paaren aus ID und Name | `dict(kontext.teilprozesse)`, dazu Positivtest Step 2a |
| R2-2 | Important | Der „ja"-Test erwartet Feldstatus im Payload eines laufenden Turns, den es nicht gibt, und B3 als nächste Frage ohne Vorlauf | Gesprächsstand bis B3 vorbereiten, Status aus dem Store, `payload["feld"]` (Task 5 Step 5). NULL-Test mit ungültigem Wert in Task 6 |
| R2-3 | Important | CLI erwartet `vollstaendigkeit` auch für erledigte Fälle | Ergebnisformat und Ausgabezeile festgelegt, zweiter Lauf über `main` getestet |
| R2-4 | Minor | Regex-Versionsassertion entgeht der Suche nach `1.1+ctx` | In Task 5 Step 8 ausdrücklich genannt |
| R2-5 | Minor | Recovery nur als Bau-Test | API-Recovery-Test mit stillgelegter Rolle in Task 6 |
| — | Klarstellung | Spaltentest der Testprofile liest Eigner und Befunde nicht | „ergänzen" statt „umstellen" (Task 6 Step 6) |
