# ANZAHL: „ca" ohne Punkt und ein Satzzeichen am Ende — Spec und Implementierungsplan

> Stand 25.10.2026, Fassung 1. Go der BC1-Projektleitung am 25.10. („Go für Paket (3) ANZAHL: erst Plan, dann bauen, TDD-Guard nie umgehen.").
> Quelle: Abschlussplan „Neu 24.10. — aus C1a" (4b), entschieden 25.10. von der BC1-Projektleitung: **zulassen**. Ändert die Spec C1a, Abschnitt 3.
> Größe XS: eine Zeile Regex, drei Tests. Spec und Plan stehen deshalb in einem Dokument. Zweitmeinung: eine unabhängige Prüfung nach dem Bau (Plan und Code zusammen), weil die Änderung klein ist, der Wert aber in die Vertragsspalte `executions_per_run` geht.

## Big Picture

Auf die Frage D4 („Wie viele Fälle je Durchlauf?") antworten Menschen oft mit „ca 3" oder „3 Fälle.". Heute ist beides ungültig, und das Interview fragt nach, obwohl die Antwort klar ist. Gemessen am 25.10.:

| Antwort | heute | neu |
|---|---|---|
| `ca 3`, `ca 3 Fälle` | ungültig, Nachfrage | `3` |
| `3 Fälle.`, `3.`, `etwa 3.`, `3 Fälle!` | ungültig, Nachfrage | `3` |
| `ca. 3`, `etwa 3`, `3 Fälle` | `3` | `3` (unverändert) |

**Bleibt ungültig, mit Nachfrage:**
- `3?`: Ein Fragezeichen drückt Zweifel aus, dann ist die Nachfrage richtig.
- `3..`, `3,`, `3 Fälle.!`: mehr als ein Zeichen oder ein Komma.
- `ca3`: kein Leerzeichen nach dem Näherungswort.
- alle Perioden, Einheiten und zweiten Zahlen wie bisher.

**Was sich nicht ändert:**
- Der gespeicherte Wert hat dieselbe Form wie bisher (`3`, `2.5`).
- Der Vertrag BC1→BC2 nennt nur Beispiele (`etwa 3`, `3 Fälle` → `3`), die weiter stimmen. Er bleibt unverändert.
- Andere Feldtypen sind nicht betroffen.

## Entscheidungen (Claude, 25.10.)

| # | Entscheidung | Warum |
|---|---|---|
| E1 | Näherungswort `ca\.?` statt `ca\.` im vorhandenen `_ANZAHL_MUSTER` | Die kleinste Änderung. Das Leerzeichen danach bleibt Pflicht (`\s+`), deshalb bleibt `ca3` ungültig. |
| E2 | Am Ende höchstens **ein** Zeichen aus `.` oder `!` (`[.!]?` vor dem abschließenden `\s*`) | Beide beenden einen Satz. `?` bleibt bewusst draußen, weil es Unsicherheit ausdrückt. Der vorhandene Helfer `_entferne_rand` passt nicht: Er schneidet auf beiden Seiten `.!?,;:` und Anführungszeichen ab, ließe also `3?`, `3,` und `„3"` durch. Das ist mehr, als entschieden ist. |
| E3 | Kein eigener Test für „Punkt nach Tausendergruppe" (`1.000.`) | Der Token-Parser liest `1.000` wie bisher, der Punkt danach ist dann das Satzzeichen. Das deckt T2 mit `1.000.` ab. |

## Global Constraints

- TDD unter dem tdd-guard, nie umgangen. `*.py` unter `coe-factory/` nur mit Edit/Write; Bash nur für pytest, git und Messungen. Ein neuer Test je Edit, jeder Zwischenschritt mit eigenem vollem pytest-Lauf.
- pytest aus `bc1-context-discovery/`: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`. Ausgangsstand auf `main` @ `b35bca5`: 867 bestanden, 4 übersprungen.
- Zweig `bc1-anzahl-naeherung`. Commits auf Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Kein Push ohne OK.

## Review Focus

1. **Dezimalpunkt gegen Satzzeichen:** Bei `2.5` muss der Punkt Teil der Zahl bleiben, bei `3.` ist er das Satzzeichen. Der Token-Parser verlangt nach `.` eine Ziffer. Deshalb ist `3.` Zahl plus Zeichen und `2.5` eine Zahl. Abgedeckt durch die Bestandstests (`2,5`, `1.000`) und T2.
2. **Bestandstests bleiben grün:** Alle bisher gültigen und ungültigen Fälle in `test_feldtypen.py`.

## Tasks

### Task 1 — Näherungswort „ca" ohne Punkt (E1)

Dateien: `bc1_core/feldtypen.py`, `tests/test_feldtypen.py`.

- [ ] T1 `test_anzahl_ca_ohne_punkt(eingabe)`, parametrisiert über `"ca 3"`, `"ca 3 Fälle"`, `"CA 3"`. Erwartet: `ANZAHL.normalisiere(eingabe) == "3"` und gültig.
- [ ] Volle Suite → RED.
- [ ] `ca\.` → `ca\.?` im `_ANZAHL_MUSTER`. Volle Suite → GREEN.
- [ ] Commit `feat(bc1): ANZAHL nimmt „ca" auch ohne Punkt an (C1a (4b))`.

### Task 2 — Ein Satzzeichen am Ende (E2, E3)

- [ ] T2 `test_anzahl_mit_satzzeichen_am_ende(eingabe, erwartet)`, parametrisiert über `("3 Fälle.", "3")`, `("3.", "3")`, `("etwa 3.", "3")`, `("3 Fälle!", "3")`, `("ca 3 Fälle je Durchlauf.", "3")`, `("1.000.", "1000")`, `("2,5.", "2.5")`. Erwartet: normalisiert wie angegeben und gültig.
- [ ] Volle Suite → RED.
- [ ] `[.!]?` vor dem abschließenden `\s*` im `_ANZAHL_MUSTER`. Volle Suite → GREEN.
- [ ] T3 `test_anzahl_bleibt_bei_zweifel_und_mehreren_zeichen_ungueltig(eingabe)`, parametrisiert über `"3?"`, `"3.."`, `"3,"`, `"3 Fälle.!"`, `"ca3"`. Erwartet: ungültig. Der Test ist grün bei Ankunft und braucht deshalb eine Gegenprobe im Scratchpad-Kopie-Verfahren: Mit `[.!?]?` wird `3?` gültig, der Test muss rot werden.
- [ ] Commit `feat(bc1): ANZAHL nimmt ein Satzzeichen am Ende an (C1a (4b))`.

### Task 3 — Spec, Abschlussplan, Prüfung

- [ ] Spec C1a Abschnitt 3: Grammatik und Tabelle nachziehen (`ca` ohne Punkt, ein `.` oder `!` am Ende; `3?` bleibt ungültig), Kopfzeile „Änderung 25.10.".
- [ ] Abschlussplan: „Neu 24.10. — aus C1a" (4b) erledigt, „Nächstes Go" auf (4).
- [ ] Volle Suite mit und ohne DB. Unabhängige Prüfung von Plan und Code (Auftrag: jeder pytest-Aufruf mit `-p no:tdd-guard -p no:cacheprovider`); danach ein regulärer Lauf.
- [ ] Commit `docs(bc1): ANZAHL — Spec C1a und Abschlussplan`.
