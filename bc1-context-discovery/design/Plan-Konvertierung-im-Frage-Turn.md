# Konvertierungs-Widerspruch im Frage-Turn — Plan

> Stand 25.10.2026, Fassung 1. Entscheidung der BC1-Projektleitung am 25.10.: Variante **(a) mit Auflage**; Go für die Reihenfolge am selben Tag (dieses Paket ist Schritt 3).
> Quelle: Abschlussplan „Neu 25.10. — aus der Prüfung von Paket (4)“, mit Prüfbefund und Zweitmeinung. Dazu die Minor (1) und (2) aus der Gesamtprüfung von Paket (4), weil sie dieselbe Datei betreffen.
> **Gebaut 25.10.** auf Zweig `bc1-konvertierung-frageturn` (umgesetzt auf `main` @ `796ac2c` nach dem Merge von #357). Abweichung beim Bau: Der Guard lehnte den ersten Edit im `except`-Zweig mit sachlich falscher Begründung ab. Mit einem Anker ab dem `try` ging derselbe Inhalt durch; die Lesson steht im Skill `tdd-guard`. T1 war rot, T2 kam grün an. Die Gegenprobe (Abschluss ebenfalls übersprungen) macht T2 und fünf bestehende Abschluss-Tests rot. Suite mit DB 911/4.
> Größe S: eine Stelle in `ProfilWriter.reconcile`, zwei neue Tests und Doku. Zweitmeinung: eine unabhängige Prüfung nach dem Bau.

## Big Picture

Gibt ein Interview einen Zahlwert, den die Prüfung als gültig ansieht, der Konverter für die Datenbank-Spalte aber nicht lesen kann, ist das ein Code-Fehler (Validator und Spaltentyp widersprechen sich). Heute antwortet der Dienst dann schon **mitten im Interview** mit 503, und das in jedem weiteren Turn. Für die Person sieht das aus wie „bitte später noch einmal“. Jedes Neusenden zählt der Kern aber als Antwort auf eine Frage, die sie nie gesehen hat. Felder werden `ungeloest`, und am Ende greift das Runden-Limit.

**Neu:** Mitten im Interview wird der Fehler protokolliert, blockiert aber nicht, wie jeder andere Fehler des Writers in einem Frage-Turn. Das Interview läuft normal weiter. Erst im **Abschluss** antwortet der Dienst mit 503 wie bisher: Ein Profil mit diesem Widerspruch wird nie eingefroren. Ist der Code-Fehler behoben, holt die nächste Nachricht den Abschluss nach (Paket (4)), und zwar mit den vollständigen Daten des Interviews.

**Auflage:** Im Protokoll steht nie der Rohwert, denn er ist Nutzertext. Die Meldung der Konverter enthält ihn (`'{wert}'`). Deshalb protokolliert der Frage-Turn nur einen festen Grund, nicht die Meldung.

**Was sich nicht ändert:** Abschluss-Turn (503, keine Antwort ausgeliefert), Nachholen, Abbruch-Pfad, Datenbank, Vertrag, Paketfassung, n8n.

**Grenze (bleibt):** Scheitert die Konvertierung schon, bevor es einen Entwurf gibt (Werte, die vor dem Fokus-Schritt gefragt werden), entsteht keiner. Am Ende kommt dann 409 `abschluss_ausstehend`, und der Betrieb holt per Replay nach.

## Entscheidungen

| # | Entscheidung | Warum |
|---|---|---|
| E1 | Im Zweig `except ProfilWriteError` von `reconcile`: bei `status != "fertig"` WARNING `profil_write_uebersprungen session=<id> grund=ProfilWriteError` und `None`; bei `fertig` unverändert `raise` | Gleiche Zeile wie bei anderen übersprungenen Fehlern, damit der Betrieb nur eine Suchzeile braucht. Als Grund nur der Klassenname: `_fehlergrund` übernähme die erste Meldungszeile samt Rohwert. Feld und Ziel nennt schon die ERROR-Zeile `profil_konvertierung_widerspruch` aus dem Bau. |
| E2 | Kein Ende-zu-Ende-Test über `/turn` | Die API übersetzt `ProfilWriteError` unverändert. Das Verhalten entsteht vollständig im Writer und ist dort gegen die Test-DB prüfbar (YAGNI, Zweitmeinung). |
| E3 | Minor (1) aus Paket (4): `abschluss_offen` aus dem Abschnitt „innerhalb EINER Transaktion“ direkt hinter `reconcile` verschieben | Die Methode öffnet eine eigene Verbindung und liest nur. Unter der Überschrift steht sie falsch. Verschoben wird guard-konform nach der Lesson vom 05.10.: erst entfernen, Lauf, dann einfügen. |
| E4 | Minor (2): Rückgabe als `Literal["nachholbar", "ausstehend"] \| None` | Die zwei Werte sind ein fester Vertrag mit dem Gate in `api.py`. |

## Global Constraints

- TDD unter dem tdd-guard, nie umgangen. `*.py` unter `coe-factory/` nur mit Edit/Write; Bash nur für pytest, git und Messungen. Ein Test je Edit, nach jedem Schritt ein voller Lauf.
- pytest aus `bc1-context-discovery/`: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`. Ausgangsstand: 909/4 mit DB, 624/289 ohne DB.
- Zweig `bc1-konvertierung-frageturn`, aufgesetzt auf `bc1-test-aufraeumen` (PR #357). Nach dessen Merge: `git rebase --onto origin/main bc1-test-aufraeumen bc1-konvertierung-frageturn`. Commits auf Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Kein Push ohne OK.

## Review Focus

1. **Kein Rohwert im Protokoll**, weder im Frage-Turn noch im Abschluss. Das prüfen beide Tests.
2. **Abschluss bleibt hart:** Ein Profil mit Widerspruch wird nie `fertig`, und `abschluss_offen` meldet danach „nachholbar“ (T2).
3. **Andere `ProfilWriteError` im Frage-Turn:** Heute gibt es keine weitere Quelle (`_abgleich` wirft sonst nur bei `fertig`). Würde später eine dazukommen, liefe sie ebenfalls still durch. Der Kommentar an der Stelle muss das sagen.

## Tasks

### Task 1 — Frage-Turn blockiert nicht, ohne Rohwert (E1)

Datei: `tests/test_profil_writer.py`, `bc1_service/profil_writer.py`.

- [ ] Testpaket `KONV_PAKET` = `PAKET.fields` plus `FieldSpec("frequency_per_year", "Wie oft im Jahr?", required=False)` ohne Feldtyp (wie das bestehende `EIGNER_PAKET`).
- [ ] T1 `test_konvertierungswiderspruch_im_frage_turn_blockiert_nicht(pool, caplog)`:
  - Ein Frage-Turn ohne den Wert legt den Entwurf an.
  - Danach liefert ein Frage-Turn mit `frequency_per_year=("dreimal jaehrlich", GUELTIG)` unter `caplog.at_level("WARNING")` `None` und wirft nicht.
  - Im Protokoll stehen `profil_konvertierung_widerspruch` und `profil_write_uebersprungen`, aber nicht `dreimal jaehrlich`.
  - `_zeilen()` ist `[("KP-01.TP-1", 1, "in_erhebung")]`.
- [ ] Voller Lauf → RED (`ProfilWriteError`).
- [ ] Im `except ProfilWriteError` von `reconcile` den Zweig nach E1. Er wächst in kleinen Schritten, je mit Lauf (Lesson „Over-implementation for the current failure stage“): erst `return None` bei Nicht-`fertig`, dann die WARNING-Zeile. Den Kommentar nach Review Focus 3 setzen. Voller Lauf → GREEN.
- [ ] Commit `fix(bc1): Konvertierungs-Widerspruch blockiert den Frage-Turn nicht mehr`.

### Task 2 — Abschluss bleibt 503, ohne Rohwert, danach nachholbar

- [ ] T2 `test_konvertierungswiderspruch_im_abschluss_bleibt_ein_503_ohne_rohwert(pool, caplog)`:
  - Erst ein Frage-Turn ohne den Wert, dann `FERTIG` mit dem Wert.
  - Erwartet wird `pytest.raises(ProfilWriteError)`.
  - `dreimal jaehrlich` steht nicht in `caplog.text` (Stufe `ERROR`), `_zeilen()` bleibt `in_erhebung`, und `writer.abschluss_offen(state) == "nachholbar"`.
- [ ] Voller Lauf. Der Test kommt voraussichtlich grün an, denn der Abschluss ist heute schon so. Die Wirkung belegt eine Gegenprobe im Scratchpad-Kopie-Verfahren: Wird der Abschluss im Writer ebenfalls übersprungen, muss T2 rot werden.
- [ ] Commit `test(bc1): Abschluss mit Konvertierungs-Widerspruch bleibt ein 503`.

### Task 3 — Minor (1)/(2) aus Paket (4) und Doku

- [ ] E3: `abschluss_offen` am alten Ort per Edit entfernen → voller Lauf (rot, `AttributeError`) → direkt hinter `reconcile` wieder einfügen → voller Lauf.
- [ ] E4: `from typing import Literal`, Rückgabe-Annotation. Voller Lauf.
- [ ] Kommentar `tests/test_feldtypen.py:184`: „503 in JEDEM Turn, die Sitzung haengt dauerhaft“ wird zu „503 im Abschluss-Turn; bis dahin uebersprungen (Paket Konvertierung im Frage-Turn)“.
- [ ] Doku:
  - Abschlussplan: „Neu 25.10. — aus der Prüfung von Paket (4)“ auf „gebaut“, Minor (1)/(2) als erledigt markieren, Stand-Zeile.
  - `design/Spec-Abschluss-nachholen.md:323ff.`: den Nebenbefund als erledigt vermerken.
  - `SMOKE.md` nur, falls dort ein 503 mitten im Interview beschrieben ist (prüfen).
  - Bauvermerk hier im Kopf.
- [ ] Volle Suite mit DB und ohne DB. Unabhängige Gesamtprüfung; jeder pytest-Aufruf darin mit `-p no:tdd-guard -p no:cacheprovider`. Bericht. Push nur nach OK.
