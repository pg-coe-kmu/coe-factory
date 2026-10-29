# Kurzantworten landen im gefragten Feld — Implementierungsplan

> **Für ausführende Agenten:** PFLICHT-SUB-SKILL: superpowers:subagent-driven-development (empfohlen) oder superpowers:executing-plans, Task für Task. Schritte als Checkboxen (`- [ ]`).
>
> Fassung 2 (29.10.2026): Prüfung von Fassung 1 durch einen unabhängigen Claude-Prüfer (0C/4I/17M) und agy (0C/3I/3M) eingearbeitet; Codex-Lauf brach am Nutzungslimit ab.

**Ziel:** Eine Antwort, die nur aus einem Wert in der Form des zuletzt gefragten Felds besteht, landet ohne KI direkt in diesem Feld.

**Architektur:** Jeder `Feldtyp` bekommt ein optionales Merkmal `kurzform`, das für eine Nachricht den reinen Wert liefert oder `None` (Vorgabe: keins). `process_turn` bestimmt das zuletzt gefragte Feld aus `raw_log` und `antworten`; `extract_and_merge` nutzt vor dem KI-Aufruf die Kurzform dieses Felds und gibt den reinen Wert als einzigen Kandidaten in das bestehende Zusammenführen.

**Technik:** Python 3.11+, Standardbibliothek, pytest, Test-KI `FakeLLM`.

**Spec:** `design/Spec-Extraktion-gestellte-Frage.md` (Entwurf 3, abgenommen 29.10.2026, Entscheidungen 7.1–7.3 wie empfohlen).

## Globale Vorgaben

- **TDD-Guard nie umgehen.** `*.py` unter `coe-factory/` NUR mit Edit/Write/MultiEdit ändern; Bash nur für pytest, git und Messungen. Je Edit genau **eine neue Testfunktion** (Parametrisierung innerhalb einer Funktion ist erlaubt; blockt der Guard, Skill `tdd-guard`). Nach jedem Edit `.venv/bin/pytest` aus `bc1-context-discovery/` (voller Lauf). Bei jedem Block das Skill `tdd-guard` aufrufen und neue Blöcke dort eintragen.
- **Kette je neuer Kurzform** (der erste RED wäre sonst ein Error, und „Hilfsfunktion vor Aufrufer“ blockt): (1) Aufrufer `Feldtyp(..., kurzform=_kurzform_x)` bzw. in der Fabrik eintragen → pytest (NameError ist der RED); (2) `def _kurzform_x(wert: str) -> str | None: return None` → pytest (Assertion-RED); (3) Logik → pytest grün.
- **Keine KI-Anbindung ändern:** `llm.py`, `gemini_llm.py`, `claude_llm.py`, `ollama_llm.py`, `prompts.py` bleiben unverändert (Entscheidung 7.1).
- **Fragetexte und Paketfassung bleiben** (Entscheidung 7.2): `discovery_paket.py` wird nicht geändert; `schema_version` bleibt.
- **Kein neues Feld im Sitzungszustand**, keine Datenbank-, Vertrags- oder Schemaänderung.
- **Bestehende Normalisierer und Prüfer bleiben im Verhalten unverändert.** Einzige Ausnahme ist das Refactoring von `_ANZAHL_MUSTER` auf die gemeinsame Konstante (Task 2), bei gleichem Verhalten: `ca\.?` und `\s+` danach bleiben, `"ca.. 3"` und `"ca3"` bleiben ungültig. `_ZAHL_TOKEN` wird nur benutzt, nicht geändert; die Rückstellung (4)(b) im Abschlussplan wird damit nicht ausgelöst.
- **Kurzformen sind total:** Sie werfen nie; jede Eingabe liefert einen String oder `None`.
- **Kurzform, allgemein:** fullmatch nach `strip()`; Groß/Klein egal; am Ende höchstens **ein** „.“ oder „!“, **direkt** angehängt (kein Leerraum davor; `"Ja !"`, `"ja.."`, `"ja,"` sind keine Kurzform); ein „?“ irgendwo → keine Kurzform. `_entferne_rand` NICHT verwenden (entfernt beliebig viele Zeichen).
- **Näherungswörter** (eine gemeinsame Konstante, dieselbe Liste wie `_ANZAHL_MUSTER`): `etwa`, `ca.`, `ca`, `circa`, `ungefähr`, `ungefaehr`, `rund`, `im schnitt`, `durchschnittlich`; danach Leerraum.
- **Einheiten MINUTEN:** `(minuten?|min|stunden?|std|h)` mit dem einen optionalen Schlusszeichen `[.!]?` direkt dahinter — so ist „Min.“/„Std.“ abgedeckt und „90 min..“, „2 Std.!“ sind keine Kurzform. Leerraum zwischen Zahl und Einheit optional. Reiner Wert: `"<Zahl> <Einheit>"` mit genau einem Leerzeichen, Einheit wie geschrieben ohne Punkt (z. B. `"90 Min"`, `"1,5 h"`, `"45 min"`).
- **Zeiträume ZAHL:** optional `mal` oder `x` (direkt, mit Leerraum oder Bindestrich: „2mal“, „2 mal“, „2-mal“), dann `pro` | `im` | `je`, dann `woche` | `monat` | `jahr`. Reiner Wert: `"<Zahl> pro <Woche|Monat|Jahr>"` (z. B. `"2 pro Jahr"`).
- **Prozent:** Zahl, optional `%` (Leerraum optional) oder ` prozent` (mit Leerraum). Reiner Wert: das Zahl-Token.
- **Erwartete Werte sind Strings** (`"180"`, nicht `180`).
- **Testdaten generisch** (öffentliches Repo): Kontext lokal nach dem Muster von `KONTEXT` in `tests/test_discovery_paket.py` nachbauen (nicht importieren — `tests/` ist kein Paket), Teilprozess `"KP-01.TP-1"` „Erfassen“; keine Namen aus der Generalprobe.
- **Tests, die bei Ankunft grün sind** (Absicherungs- und Abnahmetests), bekommen eine Mutationsprobe: die geprüfte Stelle in einer Kopie im Scratchpad absichtlich verbiegen, Test muss dort rot werden; im Bericht festhalten. Nie im Repo mutieren.

## Bekannt und bewusst nicht geändert

- Im kontextfreien Zweig (Fassung 1.0, nur Demo und Tests) ist D4 vom Typ `ZAHL`. „5 pro Woche“ auf die Fallzahl-Frage wird dort ohne KI 260 — genau wie heute über die KI. Mit BC0-Kontext ist D4 `ANZAHL`; dort bleibt „5 pro Woche“ ungültig.
- „2x pro Monat“ ist keine Kurzform (nicht in der Spec) und geht an die KI. Hinweis für die Antwortliste der zweiten Generalprobe. **Überholt (Nachtrag 29.10.):** „x“ ist jetzt wie „mal“ Kurzform.

## Prüfschwerpunkte (Review Focus)

1. **Längere Antwort mit genau einer Zahl samt Einheit** auf eine Dauer-Frage → keine Kurzform, KI-Kandidaten bleiben. Tests in Task 3 und Task 5.
2. **Nackte Zahl auf Dauer oder Häufigkeit** („40“, „2“) → keine Kurzform, keine erfundene Einheit. Test in Task 3.
3. **Kurzform erkannt, Wert danach ungültig** („150 %“, „70,5 %“ bei ganzzahligen Prozent) → `ungueltig`, KI nicht gefragt. Task 5.
4. **Telefonnummer auf die Anzahl-Frage** → über `process_turn` keine Kurzform (PII-Filter vorher). Task 5, mit Mutationsprobe.
5. **Kurzantwort beim identitätskritischen `focus_step`**: genaue ID ohne KI, alles andere über die KI. Task 5.

---

### Task 1: Merkmal `kurzform`; Kurzformen für Ja/Nein, Skala, Auswahl, Anzahl

**Dateien:** Ändern `bc1_core/feldtypen.py` (`Feldtyp`, `JA_NEIN`, `SKALA_1_5`, `ANZAHL`, Fabrik `AUSWAHL`). Test `tests/test_feldtypen.py`.

**Schnittstellen:**
- Erzeugt: `Feldtyp.kurzform: Callable[[str], str | None] | None = None` — letztes Feld der frozen Dataclass, Vorgabe `None`.
- Reine Werte: `JA_NEIN` → `"ja"`/`"nein"`; `SKALA_1_5` → die Ziffer; `AUSWAHL(*optionen)` → die kanonische Option (Kurzform als Closure in der Fabrik, Optionen mit `re.escape` bzw. Stringvergleich; bei `AUSWAHL()` ohne Optionen immer `None`); `ANZAHL` → `_ANZAHL_MUSTER.fullmatch(...).group(1)`.

- [ ] **Schritt 1:** Test `test_freie_typen_haben_keine_kurzform`: `FREITEXT.kurzform is None`, `LISTE.kurzform is None`. Rot (AttributeError) → Feld ergänzen → grün.
- [ ] **Schritt 2:** Test `test_kurzform_ja_nein`: `"Ja"`→`"ja"`, `"nein."`→`"nein"`, `"JA!"`→`"ja"`; `None` für `"Ja, aber selten"`, `"ja?"`, `"jein"`, `""`, `"ja.."`, `"ja,"`, `"Ja !"`. Kette (1)–(3).
- [ ] **Schritt 3:** Test `test_kurzform_skala`: `"4"`→`"4"`, `"4."`→`"4"`; `None` für `"eher 4"`, `"etwa 4"`, `"4 von 5"`, `"6"`, `"4?"`, `"4.."`. Kette.
- [ ] **Schritt 4:** Test `test_kurzform_auswahl` mit `AUSWAHL("geschaetzt", "KP-01.TP-1")`: `"geschaetzt"`→`"geschaetzt"`, `"KP-01.TP-1"`→`"KP-01.TP-1"`, `"kp-01.tp-1."`→`"KP-01.TP-1"`; `None` für `"KP-01.TP-1?"`, `"KP-01.TP-9"`, `"Erfassen"`, `"geschätzt"`, `"geschaetzt.."`; dazu `AUSWAHL().kurzform("")` und `AUSWAHL().kurzform("x")` sind `None`. Kette.
- [ ] **Schritt 5:** Test `test_kurzform_anzahl`: `"1"`→`"1"`, `"etwa 3 Fälle"`→`"3"`, `"ca 3."`→`"3"`; `None` für `"5 pro Woche"`, `"3?"`, `"ein Fall, manchmal 3"`. Kette.
- [ ] **Schritt 6: Commit** `BC1: Feldtyp-Merkmal kurzform; Kurzformen für Ja/Nein, Skala, Auswahl, Anzahl`

### Task 2: Kurzform für Prozent; gemeinsame Näherungswörter

**Dateien:** Ändern `bc1_core/feldtypen.py` (`PROZENT_0_100`, Konstante der Näherungswörter, `_ANZAHL_MUSTER`), `bc1_service/paket_feldtypen.py` (`PROZENT_GANZ_0_100`). Tests `tests/test_feldtypen.py`, `tests/test_paket_feldtypen.py`.

**Schnittstellen:** Kurzform `PROZENT_0_100` → das Zahl-Token (`"70"`, `"70,5"`, `"150"`); Bereichsprüfung bleibt beim Prüfer. `PROZENT_GANZ_0_100.kurzform is PROZENT_0_100.kurzform`. Der Systemtyp aus `baue_system_typ` hat keine Kurzform.

- [ ] **Schritt 1:** Test `test_kurzform_prozent`: `"70"`, `"ca. 70 %"`, `"70%"`, `"70 Prozent"`, `"70."`, `"im Schnitt 70 %"` → `"70"`; je ein Fall mit `circa`, `ungefähr`, `ungefaehr`, `rund`, `durchschnittlich`, `etwa`, `ca` → `"70"`; `"150 %"`→`"150"`, `"70,5 %"`→`"70,5"`; `None` für `"70 bis 80"`, `"70?"`, `"etwa 70 bis 80 %"`, `"70 %.."`. Kette.
- [ ] **Schritt 2:** Test `test_prozent_ganz_teilt_die_kurzform` (test_paket_feldtypen): `PROZENT_GANZ_0_100.kurzform is PROZENT_0_100.kurzform`. Rot → `kurzform=PROZENT_0_100.kurzform` → grün.
- [ ] **Schritt 3:** Test `test_systemtyp_hat_keine_kurzform` (test_paket_feldtypen): `baue_system_typ(frozenset({"S-01"})).kurzform is None`. Grün bei Ankunft (Vorgabe `None`) — gewollt als Wächter.
- [ ] **Schritt 4:** Netz-Test `test_anzahl_kennt_alle_naeherungswoerter`: für jedes der neun Wörter `ANZAHL.normalisiere("<wort> 3") == "3"` und `ANZAHL.kurzform("<wort> 3") == "3"`. Grün bei Ankunft; Mutationsprobe (ein Wort aus `_ANZAHL_MUSTER` in einer Kopie streichen → rot).
- [ ] **Schritt 5: Refactoring bei grüner Suite:** Näherungswörter als gemeinsame Konstante; `_ANZAHL_MUSTER` und die Prozent-Kurzform nutzen sie. pytest grün (inkl. `"ca.. 3"`, `"ca3"` ungültig).
- [ ] **Schritt 6: Commit** `BC1: Kurzform für Prozent; gemeinsame Näherungswörter`

### Task 3: Kurzformen für Dauer und Häufigkeit; Totalität

**Dateien:** Ändern `bc1_core/feldtypen.py` (`MINUTEN`, `ZAHL`). Test `tests/test_feldtypen.py`.

**Schnittstellen:** Kurzform `MINUTEN` → `"<Zahl> <Einheit>"`; Kurzform `ZAHL` → `"<Zahl> pro <Woche|Monat|Jahr>"` (siehe Globale Vorgaben).

- [ ] **Schritt 1:** Test `test_kurzform_minuten` — reiner Wert UND Wert nach `MINUTEN.normalisiere`: `"3 Stunden"`→`"3 Stunden"`/`"180"`, `"ca 90 Min."`→`"90 Min"`/`"90"`, `"45min"`→`"45 min"`/`"45"`, `"1,5h"`→`"1,5 h"`/`"90"`, `"40 Stunden"`→`"40 Stunden"`/`"2400"`, `"im Schnitt 2 Std."`→`"2 Std"`/`"120"`, je ein Fall mit `circa`, `ungefähr`, `ungefaehr`, `rund`, `durchschnittlich`, `etwa` (`"<wort> 3 Stunden"` → `"180"`); `None` für `"3"`, `"40"`, `"90 min.."`, `"2 Std.!"`, `"Der Prozess dauert 3 Stunden."`, `"nicht 3 Stunden"`, `"3 Stunden?"`, `"1 Stunde 30 Minuten"`, `"3 Stunden, der Gesamtprozess dauert aber eine Woche"`. Kette.
- [ ] **Schritt 2:** Test `test_kurzform_haeufigkeit` — reiner Wert UND Wert nach `ZAHL.normalisiere`: `"2 pro Monat"`→`"2 pro Monat"`/`"24"`, `"2 mal im Monat"`→`"2 pro Monat"`/`"24"`, `"2mal im Monat"`→`"24"`, `"2mal pro Woche"`→`"104"`, `"2-mal je Jahr"`→`"2 pro Jahr"`/`"2"`, `"etwa 4 pro Monat"`→`"48"`, je ein Fall mit den übrigen Näherungswörtern; `None` für `"2"`, `"2 pro Tag"`, `"2 mal pro Monat, im Dezember mehr"`, `"Der Gesamtprozess läuft 2 mal pro Monat"`, `"2 pro Monat?"`, `"2 pro Monat.."`. Kette.
- [ ] **Schritt 3:** Test `test_kurzformen_sind_total`: für jeden Typ mit Kurzform (`JA_NEIN`, `SKALA_1_5`, `AUSWAHL("a")`, `ANZAHL`, `PROZENT_0_100`, `MINUTEN`, `ZAHL`) liefern `""`, `"\n"`, `"9" * 400`, `"9" * 400 + " Stunden"`, `"äöü?…"`, `"1.000.000 pro Jahr"` einen String oder `None` und werfen nie. Grün bei Ankunft oder rot → Fehler beheben.
- [ ] **Schritt 4: Commit** `BC1: Kurzformen für Dauer und Häufigkeit, nur mit Einheit bzw. Zeitraum`

### Task 4: Das zuletzt gefragte Feld

**Dateien:** Ändern `bc1_core/core.py` (neue Funktion, noch nicht verdrahtet). Test `tests/test_core.py`.

**Schnittstellen:** `zuletzt_gefragt(state: SessionState) -> str | None` — `state.raw_log` rückwärts, erster Eintrag, dessen `message_id` in `state.antworten` steht; liefert `(antwort.get("payload") or {}).get("feld")`, wenn `antwort.get("status") == "frage"`, sonst `None`.

- [ ] **Schritt 1:** Test `test_zuletzt_gefragt_erster_turn_ist_none` (frischer Zustand, eine Nachricht in `raw_log`, `antworten` leer). Rot (ImportError) → **nur** Stub `return None` → grün.
- [ ] **Schritt 2:** Test `test_zuletzt_gefragt_nach_frage`: Paket `TOY_PROZESS`; erster Turn über `_turn` mit `FakeLLM`, das `prozess_name` füllt; zweiter Turn ohne Kandidaten; dritte Nachricht nur an `raw_log` gehängt → Ergebnis ist `payload["feld"]` der Antwort des zweiten Turns, und sie unterscheidet sich vom `feld` der ersten Antwort. Rot → Rückwärtssuche bauen → grün.
- [ ] **Schritt 3:** Test `test_zuletzt_gefragt_ueberspringt_unbeantwortete` (nach einer Frage zwei unbeantwortete Einträge) → weiterhin das Feld dieser Frage.
- [ ] **Schritt 4:** Test `test_zuletzt_gefragt_letzte_antwort_keine_frage` (Status `fertig`) → `None`. Rot → Statusprüfung → grün.
- [ ] **Schritt 5:** Test `test_zuletzt_gefragt_antwort_ohne_payload` (Antwort `{"status": "frage"}`) → `None`, wirft nicht.
- [ ] **Schritt 6:** Test `test_zuletzt_gefragt_nach_json_rundreise`: Zustand aus Schritt 2 über `state_to_dict`/`state_from_dict`, `antworten` dabei absichtlich umsortiert → gleiches Ergebnis.
- [ ] **Schritt 7: Commit** `BC1: zuletzt gefragtes Feld aus raw_log und antworten`

### Task 5: Die Regel in Extraktion und Turn

**Dateien:** Ändern `bc1_core/extractor.py` (`extract_and_merge`, Import `ExtractionCandidate`), `bc1_core/core.py` (`process_turn`). Tests `tests/test_extractor.py`, `tests/test_core.py`.

**Schnittstellen:**
- Verbraucht: `Feldtyp.kurzform` (Tasks 1–3), `zuletzt_gefragt` (Task 4).
- Erzeugt: `extract_and_merge(state, message, message_id, package, llm, *, gefragt: FieldSpec | None = None) -> None`. Liefert `gefragt.typ.kurzform(message)` einen Wert: Kandidatenliste = `[ExtractionCandidate(gefragt.name, wert)]`, **kein** `llm.extract` und kein `ki_aufruf("extraktion")`; sonst unverändert. Danach dieselbe Zusammenführung. Die Logzeile `kurzantwort_direkt` kommt **erst in Schritt 7**.
- `process_turn` bestimmt direkt vor `extract_and_merge`: `feld = zuletzt_gefragt(state)`; `gefragt = package.field(feld) if feld else None`; übergibt `gefragt=gefragt`.
- Test-KI: Zähler-KI im Test (zählt `extract`-Aufrufe, liefert eine einstellbare Liste), im selben Edit wie der erste Test, der sie braucht.

- [ ] **Schritt 1:** Test `test_kurzantwort_ohne_ki` (parametrisiert, eine Funktion): Feld mit `PROZENT_0_100` und `"ca. 70 %"`→`"70"`; `SKALA_1_5` und `"4."`→`"4"`; `MINUTEN` und `"1,5h"`→`"90"`; `ZAHL` und `"2mal im Monat"`→`"24"`. Je: Wert, `GUELTIG`, Quelle `"m1"`, `ki.aufrufe == 0`. Rot (TypeError Signatur) → Signatur → rot (Assertion) → Weiche → grün.
- [ ] **Schritt 2:** Test `test_kurzantwort_ungueltiger_wert`: `PROZENT_0_100`, `"150 %"` → `UNGUELTIG`, `ki.aufrufe == 0`.
- [ ] **Schritt 3:** Test `test_kurzantwort_ganzzahl_prozent_mit_komma`: `PROZENT_GANZ_0_100`, `"70,5 %"` → `UNGUELTIG`, `ki.aufrufe == 0`.
- [ ] **Schritt 4:** Test `test_lange_antwort_geht_an_die_ki`: `MINUTEN`-Feld `schrittdauer` gefragt, `"Der Prozess dauert 3 Stunden."`, KI liefert `gesamtdauer="3 Stunden"` → `gesamtdauer == "180"`, `schrittdauer` nicht gesetzt, `ki.aufrufe == 1`.
- [ ] **Schritt 5:** Test `test_ohne_kurzform_ruft_die_ki`: (a) `gefragt=None`, `"4"`; (b) gefragtes `FREITEXT`-Feld, `"4"` → je `ki.aufrufe == 1`, kein Feld aus der Regel gesetzt.
- [ ] **Schritt 6:** Tests zum Zusammenführen über die Regel, **je ein Edit**, Feld `MINUTEN`:
  - `test_kurzantwort_bestaetigt_kandidaten`: `unklar`, Wert `"2400"` (Quelle `"m1"`), Kandidat `"180"` (Quelle `"m2"`); `"3 Stunden"` in `"m3"` → Wert `"180"` mit Quelle `"m3"`, Kandidat `"2400"` mit Quelle `"m1"`, `GUELTIG`, `attempts` unverändert.
  - `test_kurzantwort_bestaetigt_bisherigen_wert`: wie oben; `"40 Stunden"` → Wert `"2400"`, Quelle `"m1"`, `GUELTIG`.
  - `test_kurzantwort_dritter_wert_bleibt_unklar`: wie oben; `"5 Stunden"` → `UNKLAR`, `"300"` als Kandidat mit Quelle der neuen Nachricht.
  - `test_kurzantwort_korrigiert_ungueltig`: `ungueltig`, Wert `"viel"`; `"3 Stunden"` → Wert `"180"`, `GUELTIG`, `"viel"` als Kandidat mit alter Quelle.
- [ ] **Schritt 7:** Test `test_kurzantwort_protokolliert_nur_feldname` (Extraktor-Ebene, caplog `bc1.kern`, gefragtes `AUSWAHL("geschaetzt", "gemessen")`-Feld, `"geschaetzt"`): genau eine Zeile `kurzantwort_direkt korrelation=… feld=<name>`, `"geschaetzt"` steht in keiner Zeile, keine Zeile `ki_aufruf … art=extraktion`. Rot → Logzeile → grün.
- [ ] **Schritt 8:** Test `test_focus_step_kurzantwort` (Paket aus `baue_discovery_paket(kontext=…)`, Kontext lokal mit Teilprozessen `("KP-01.TP-1", "Erfassen")`, `("KP-01.TP-2", "Pruefen")`; gefragt `focus_step`): `"KP-01.TP-1"` → gültig, `ki.aufrufe == 0`; `"KP-01.TP-9"`, `"Erfassen"`, `"KP-01.TP-1?"` → je `ki.aufrufe == 1`.
- [ ] **Schritt 9:** Test `test_turn_nutzt_zuletzt_gefragtes_feld` (test_core): kleines Paket mit Pflichtfeldern `name` (FREITEXT) und `note` (`SKALA_1_5`); erster Turn füllt `name` über `FakeLLM`, Antwort fragt `note`; zweiter Turn `"4"`, `FakeLLM` ohne Kandidaten → `note == "4"`, `GUELTIG`. Rot → `process_turn` verdrahten → grün.
- [ ] **Schritt 10:** Test `test_schrittdauer_kurzantwort_laesst_gesamtdauer` (test_core): Gesamtdauer gültig `"2400"`, gefragt Schrittdauer, `"3 Stunden"`, `FakeLLM` liefert fälschlich `gesamtdauer="3 Stunden"` → Schrittdauer `"180"`, Gesamtdauer `"2400"`, beide `GUELTIG`.
- [ ] **Schritt 11:** Test `test_telefonnummer_auf_anzahl_frage_keine_kurzform` (test_core): gefragt ein `ANZAHL`-Feld, `"015112345678"` → Feld ohne Wert, `raw_log` enthält `[Telefon A]`. Mutationsprobe: in einer Kopie die Regel auf den ungefilterten Text anwenden → rot.
- [ ] **Schritt 12:** Test `test_fortsetzen_nach_absturz_nutzt_geloggten_text` (Muster `test_replay_nach_crash_zwischen_den_saves_setzt_turn_fort`): geloggter Text `"4"`, Retry-Body abweichend → Feld `"4"`. Mutationsprobe.
- [ ] **Schritt 13:** Test `test_fehler_bei_antwortformulierung_dann_kurzantwort`: Turn mit `"4"`, KI wirft in `antworte` → `fehler_fortsetzbar`, Feld nicht gespeichert; erneuter Aufruf mit gleicher `message_id` und funktionierender KI → Feld `"4"`, `GUELTIG`.
- [ ] **Schritt 14:** Test `test_replay_einer_kurzantwort_extrahiert_nicht_neu`: `"4"` beantwortet; gleicher Aufruf noch einmal mit einer KI, die in `extract` **und** `antworte` wirft → gleiche Antwort, Werte und `rounds` unverändert.
- [ ] **Schritt 15:** Test `test_nachricht_nach_abschluss_extrahiert_nicht`: Sitzung `fertig`; neue `message_id` mit `"4"`, KI wirft in `extract` und `antworte` → gespeicherte Abschlussantwort, Werte unverändert.
- [ ] **Schritt 16: Commit** `BC1: Kurzantwort landet ohne KI im gefragten Feld`

### Task 6: Nachspiel der Generalprobe

**Dateien:** Neu `tests/test_kurzantwort_nachspiel.py`.

**Schnittstellen:** `baue_discovery_paket(kontext=...)`, `Bc0Kontext` lokal gebaut mit `company_id`, Teilprozessen `("KP-01.TP-1", "Erfassen")`, `("KP-01.TP-2", "Pruefen")`, `system_ids=("S-01", "S-02")`, **`rollen` Pflicht** (z. B. `("R-01", "Leitung")`, `("R-02", "Fachbereich")`; ohne Rollen ist B3 `AUSWAHL()` und nie gültig), `prozesse=(("KP-01", "Auftrag"), ("KP-02", "Einkauf"))`; `process_turn`, `InMemoryStateStore`, `FakeLLM`.

- [ ] **Schritt 1:** Test `test_nachspiel_kurzantworten_fuellen_alle_pflichtfelder`: Startnachricht; `FakeLLM` liefert für sie die elf Pflichtfelder A1, A2, A3, B1, B3, B4, B5, C1, C2, C3, C4 mit gültigen Werten (B3 `"R-01"`, B4 `"KP-01"`). Danach 15 Turns in dieser Reihenfolge (Feld vor jedem Turn = `payload["feld"]` der vorigen Antwort): D1 `"2 pro Monat"`, D4 `"1"`, E1 `"40 Stunden"`, E5 `"KP-01.TP-1"`, E2 `"3 Stunden"`, E3 `"geschaetzt"`, E4 `"70"`, F1 Rollenliste (LISTE → `FakeLLM` liefert sie für genau diese Nachricht), F2 `"S-01, S-02"` (Systemtyp → `FakeLLM` liefert sie), F3 `"ja"`, G1 `"2"`, G2 `"4"`, G4 `"3"`, G5 `"4"`, I1 `"Ja"`. `FakeLLM` liefert für alle übrigen Kurzantworten nichts. Am Ende: Status `fertig`, `pflicht_erfasst == 26`, **alle 26 Werte** wie erwartet (u. a. `frequency_per_year == "24"`, `executions_per_run == "1"`, `total_duration_minutes == "2400"`, `focus_step == "KP-01.TP-1"`, `focus_step_duration_minutes == "180"`, `focus_step_duration_confidence_pct == "70"`, `documentation_status == "2"`, `standardization_level == "4"`, `data_availability_score == "3"`, `stability_score == "4"`, `pii_involved == "ja"`); kein Feld trägt als Quelle die `message_id` einer Kurzantwort, die nicht zu ihm gehört.
- [ ] **Schritt 2:** pytest. Grün bei Ankunft ist gewollt (Abnahmetest); Mutationsprobe: in einer Kopie die Weiche in `extract_and_merge` deaktivieren → rot.
- [ ] **Schritt 3: Commit** `BC1: Nachspiel der Generalprobe als Abnahmetest`

### Task 7: Doku, Roadmap, Abschluss

**Dateien:** Ändern `README.md` (Tabelle „Betriebsprotokoll“), `design/Abschlussplan-BC1.md`, `design/Spec-Extraktion-gestellte-Frage.md` (Status).

- [ ] **Schritt 1:** README: Zeile `| \`bc1.kern\` | \`kurzantwort_direkt korrelation=<id> feld=<Feldname>\` | INFO |` nach der Zeile `validierung …`; ein Satz: auf solchen Turns fehlt `ki_aufruf … art=extraktion`.
- [ ] **Schritt 2:** Abschlussplan: Stand-Zeile und Block „Neu 29.10. — aus der Generalprobe“ mit den Roadmap-Punkten aus Spec Abschnitt 6 (je Ziel und nächster Schritt) und den zwei Punkten aus „Bekannt und bewusst nicht geändert“; die Grenze aus Spec C1a: Kurzantworten mit festem Typ erledigt, „KI kennt die Frage“ offen.
- [ ] **Schritt 3:** Spec-Status auf „gebaut auf Zweig `bc1-extraktion-gestellte-frage`“.
- [ ] **Schritt 4:** Volle Suite `.venv/bin/pytest`; erwartet: Ausgangsstand ohne DB 654 passed, 297 skipped, plus die neuen Tests, kein Fehler.
- [ ] **Schritt 5: Commit** `BC1: Doku und Roadmap zu Kurzantworten`

## Danach (nicht Teil der Tasks)

- Gesamtprüfung des Zweigs (unabhängiger Prüfer auf dem stärksten Modell, Codex, agy).
- Push und PR nur nach OK der BC1-Projektleitung und Vertraulichkeits-Befund.
- Tag, `bc1-update` auf dem Server mit Ansage an BC0, Messung vorher.
- Neue Testanfrage an KP-02.TP-2 oder KP-03.TP-1, zweite Generalprobe; Antwortliste anpassen (Dauer und Häufigkeit mit Einheit; „2x pro Monat“ ist seit dem Nachtrag 29.10. Kurzform wie „mal“).
