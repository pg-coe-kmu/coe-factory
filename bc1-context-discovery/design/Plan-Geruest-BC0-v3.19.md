# Test-Nachbildung von BC0 auf v3.19 nachziehen — Plan

> Stand 25.10.2026, Fassung 1. Go der BC1-Projektleitung am 25.10. für die Reihenfolge; dies ist Schritt 2: der Abgleich mit BC0s PR #354 und, falls nötig, das Nachziehen der Test-Nachbildung.
> Grundlage: `design/Auswirkungspruefung-BC0-v3.8-v3.20.1.md` (unabhängige Prüfung, die Kernaussage zur neuen Abhängigkeit von BC1 am Code nachgeprüft).
> Größe S: Gerüst-SQL, fünf Bestandstests, ein Handbuch-Abschnitt, Doku. Kein Produktionscode außer einem Kommentar.

## Big Picture

Unsere Tests laufen gegen eine Nachbildung der BC0-Datenbank (`tests/db/bc0_geruest.sql`). Für alles, was BC1 berührt, beansprucht sie, wortgleich zu sein. Seit BC0 v3.8–v3.19 stimmt das an einigen Stellen nicht mehr. Falsche Grünstände hat die Prüfung nicht gefunden: Mit BC0s Regeln im Gerüst werden genau fünf Tests laut rot, alle anderen bleiben grün. Die fünf rechnen mit Zuständen, die BC0 inzwischen verbietet, oder mit Rechten, die BC0 inzwischen ausdrücklich vergibt.

**Neu für den Betrieb:** BC0s Sicht `v_anfrage_teilprozesse` liest seit v3.16 direkt aus `bc1.prozessprofil` und bindet sich in PostgreSQL an fünf Spalten. Für die heutige DDL ist das folgenlos. Künftige Migrationen brauchen aber eine Regel: Typ ändern oder Spalte entfernen an diesen Spalten nur mit BC0 zusammen, und **nie `CASCADE`** auf unsere Tabelle oder das Schema `bc1`, sonst verschwindet BC0s Sicht still.

## Entscheidungen (Claude, nach dem Go für die Reihenfolge; im Bericht genannt)

| # | Entscheidung | Warum |
|---|---|---|
| E1 | Gerüst nachziehen, BC0-Definitionen wortgleich: `teilprozess_unbenannt` (v3.17), die Filterzeile in `v_anfrage_teilprozesse` (v3.19b), Trigger `anfrage_prozesse_benannt` (v3.19b), Trigger `kernprozess_bleibt_aktiv` (v3.8), zwei Indizes für eindeutige Namen (v3.17), `GRANT SELECT ON companies TO bc1_role` (v3.9). Den Freigabe-Teil der Sicht nicht nachbilden. | Der Anspruch „definitionsgleich“ gilt für berührte Objekte. Der Freigabe-Teil berührt BC1 nicht, und seine Abhängigkeit auf `bc1.prozessprofil` ließe sich im Gerüst nur nach unserer DDL anlegen. Beim Meldungstext des v3.8-Triggers wird gekürzt: Prüfung und Fehlercode bleiben gleich, der Text nennt keine Person. |
| E2 | BC1s Zusatzschutz „aktiver Elternprozess“ bleibt. Die drei Tests legen den Kernprozess weiter per `UPDATE` still, schalten dafür aber BC0s Trigger sichtbar ab (`_stilllegen`). | BC0 verbietet seit v3.8 das Stilllegen per `UPDATE`, nicht aber ein `INSERT … aktiv = false` (Frage 2 an BC0). Bis zur Antwort ist die strengere Lesart die sichere. |
| E3 | `test_bc1_role_liest_bc0_objekte_nur_ueber_bc_leser` nimmt `companies` aus und prüft das direkte Recht ausdrücklich. `test_kaskade_scheitert_laut_ohne_select…` kappt den Weg bei `bc_leser` **und** `bc1_role`. | v3.9 ist BC0s Dauerzusage für unsere Löschkaskade. Der Kaskaden-Test prüft dann weiter, was er soll: Fehlt das Recht, scheitert die Löschung laut. |
| E4 | Kein Test „DDL bleibt Fall 2 mit abhängiger BC0-Sicht“ | Die Prüfung hat das gemessen. Ein Test wäre nur mit der Sicht nach unserer DDL möglich (YAGNI). Dafür kommt die Regel ins Handbuch. |

## Global Constraints

- TDD unter dem tdd-guard, nie umgangen. `*.py` unter `coe-factory/` nur mit Edit/Write; `tests/db/bc0_geruest.sql` und Markdown bewacht der Guard nicht. Nach jedem Schritt ein voller Lauf.
- pytest aus `bc1-context-discovery/`: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`. Ausgangsstand auf dem Zweig: 911/4.
- Zweig `bc1-geruest-nachziehen`, aufgesetzt auf `bc1-konvertierung-frageturn`; nach dessen Merge umsetzen. Kein Push ohne OK.

## Review Focus

1. **Wortgleichheit:** Jede übernommene Definition gleicht BC0s Datei, mit Fundstelle im Kommentar. Einzige Ausnahme ist der Meldungstext von v3.8.
2. **Keine Abschwächung der Tests:** Die fünf angepassten Tests prüfen danach mindestens so viel wie vorher. Die Gegenproben zeigen, dass sie noch Zähne haben.
3. **Testdaten passieren die neuen Regeln**, die Indizes und Trigger stehen also nicht nur auf dem Papier.

## Tasks

### Task 1 — Gerüst nachziehen (E1)

- [ ] `tests/db/bc0_geruest.sql`: die sechs Bausteine nach E1, je mit Kommentar und Fundstelle. Den Dateikopf und den Kommentar an `v_anfrage_teilprozesse` ehrlich fassen: Herleitung der Zeilen wortgleich v3.19b, der Freigabe-Teil ein Ausschnitt.
- [ ] Voller Lauf → genau fünf rot:
  - `test_bc0_lesepfade_aktiv.py`: drei Tests mit stillgelegtem Kernprozess,
  - `test_db_fixture.py::test_bc1_role_liest_bc0_objekte_nur_ueber_bc_leser`,
  - `test_ddl_trigger.py::test_kaskade_scheitert_laut_ohne_select_von_bc1_role_auf_companies`.

### Task 2 — Die fünf Tests (E2, E3)

- [ ] `_stilllegen`: Bei `ref_prozesse` schaltet die Hilfsfunktion `kernprozess_bleibt_aktiv` um das `UPDATE` ab und wieder an, mit Kommentar. Lauf → drei grün.
- [ ] `test_db_fixture.py`: `companies` aus der Schleife nehmen, eigene Prüfung „direktes SELECT an `bc1_role` (v3.9)“. Lauf.
- [ ] `test_ddl_trigger.py`: `REVOKE SELECT ON companies FROM bc_leser, bc1_role`. Lauf → 911/4.
- [ ] Veraltete Kommentare „ob BC0 kaskadiert, ist erfragt“ in `bc1_service/bc0_lesepfade.py` und `tests/test_bc0_lesepfade_aktiv.py` berichtigen (v3.8: Kernprozesse werden nicht stillgelegt; Frage 2 offen).
- [ ] Gegenproben im Scratchpad-Kopie-Verfahren:
  - Ohne das Abschalten in `_stilllegen` werden die drei Tests rot.
  - Ohne das `REVOKE` an `bc1_role` scheitert der Kaskaden-Test an seiner eigenen Wache.
  - Ein Testdatensatz mit „Teilprozess 3“ als direktem Bezug wird vom Trigger abgewiesen.

### Task 3 — Handbuch und Doku

- [ ] `bc1_service/db/EINSPIELEN.md`, neuer Abschnitt „BC0-Sicht hängt an `bc1.prozessprofil` (seit BC0 v3.16)“. Er enthält:
  - die fünf Spalten,
  - kein `CASCADE`,
  - Typänderung oder Spaltenentfernung nur mit BC0,
  - die Einspielreihenfolge in einer frischen Umgebung,
  - die Rolle des `GRANT … TO bc_leser` für unseren eigenen Start.
- [ ] Abschlussplan: Schritt 2 eintragen; die vier Fragen an BC0 mit Ziel; die Live-Messung als `bc1_role` (Sichtdefinition, `pg_depend`, Rechte) als vorbereitetes Skript für die BC1-Projektleitung.
- [ ] Volle Suite mit DB und ohne DB. Unabhängige Gesamtprüfung. Bericht. Push nur nach OK.
