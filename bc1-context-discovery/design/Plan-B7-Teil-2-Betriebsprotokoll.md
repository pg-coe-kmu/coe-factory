# B7 Teil 2 — Betriebsprotokoll in Kern, KI-Adapter und Writer: Spec und Implementierungsplan

> Stand 25.10.2026, Fassung 2. Go der BC1-Projektleitung am 25.10. („Danach Go für B7 Teil 2. Erst Plan, dann bauen, TDD-Guard nie umgehen.").
> Quellen: Sammel-Issue #266 (Teil 2, Definition of Done), Design-Spec B7 „Observability (minimal)", Abschlussplan Zeile B7 und die Rückstellungen mit Ziel B7 Teil 2 („Neu 23.10." (6), „Neu 24.10. — aus C1a" (4e), Befund M8 aus `Plan-Haertung-vor-dem-Betrieb.md`).
> Größe M: acht Tasks, je ein bis vier TDD-Zyklen. Spec und Plan stehen in einem Dokument, wie beim Härtungspaket.
> **Geprüft:** unabhängiger Prüfer (25.10.), „bereit mit Korrekturen", 0 Critical, 4 Important, 9 Minor. Alle Behauptungen zu SDK, Starlette, anyio und psycopg hat er an der Quelle bestätigt und gemessen. Alles eingearbeitet (Abschnitt „Befundverbleib").
> **Offen vor dem Bau:** Bestätigung von A1–A3 durch die BC1-Projektleitung.
> Ausführung: Claude selbst im Hauptstrang, `*.py` nur per Edit/Write; danach eine unabhängige Gesamtprüfung.

## Big Picture

Seit P5 schreibt der Dienst je Nachricht eine Zeile: wer, wann, welcher Status, wie lange. **Was im Inneren eines Turns passiert, sieht man heute nicht.** Scheitert die KI, wird daraus still „fehler_fortsetzbar", ohne dass irgendwo steht, warum. Wie lange die KI gebraucht hat, ob das SDK wiederholt hat und an welchem Feld eine Antwort abgelehnt wurde, steht nirgends. Nach diesem Paket gilt:

1. **KI-Aufrufe:** Je Aufruf eine Zeile mit Art (Extraktion oder Antwort), Ergebnis und Dauer. Wiederholt das Claude-SDK einen Aufruf, steht das mit Versuchsnummer im Protokoll. Scheitert ein Turn, steht die Fehlerklasse da (z. B. `APITimeoutError`), nie der Fehlertext.
2. **Validierung:** Wird eine Antwort für ein Feld abgelehnt oder widerspricht sie einer früheren, steht der **Feldname** im Protokoll, nie der Wert. Gibt das Interview ein Feld auf (Nachfrage- oder Rundenlimit), steht Feld und Grund da.
3. **Eine Kennung durch alles:** Die Correlation-ID aus P5 steht auch in diesen neuen Zeilen. So findet man zu einer Turn-Zeile alles, was in diesem Turn passiert ist.
4. **Warum ein Turn abgewiesen wurde:** Die Turn-Zeile nennt bei 409/500/503 statt `-` den Grund (z. B. `status=gleichzeitige_anfrage`). Scheitert das Speichern des Profils beim Abschluss, steht der Datenbankgrund (Klasse und erste Zeile) im Protokoll.
5. **Lücken geschlossen, die der Prüfer der Härtung gefunden hat:** Eine unerwartete Ausnahme erzeugt keinen Traceback mehr (der Text konnte Inhalte tragen). Der Writer trägt keine Datenbank-DETAIL-Zeile mehr in seiner Fehlermeldung. Eine kaputte BC0-Adresse kann beim Start nicht mehr Teile der Adresse ausgeben.
6. **Weniger Rauschen:** Die Befund-Warnungen des Writers (Eigner weicht ab, KP passt nicht zum TP, Systemkennung entfernt) kommen einmal beim Abschluss statt in jedem Turn. Der BC0-Eigner wird nur gelesen, wenn das Interview eine gültige Rolle hat.

**Was sich für Nutzer ändert:** nur der Text bei einem unerwarteten Fehler. Bisher kam „Internal Server Error" ohne `chat_text`, jetzt kommt ein fester Satz. Vertrag BC1→BC2, Datenbank, BC0 und n8n bleiben unberührt.

**Nie im Protokoll** (gilt für jede neue Zeile): Nachrichtentext, extrahierte Werte, Fragen, Antworttexte, Ausnahmetexte, Tracebacks. Nur Kennungen, Feldnamen, feste Schlüsselwörter, Klassennamen und Zahlen. Ausnahme wie bisher: der Writer nennt bei Datenbankfehlern Klasse und erste Meldungszeile (`_fehlergrund`), die Tabelle und Constraint benennt, nie die DETAIL-Zeile.

## Neue und geänderte Zeilen (normativ)

| Logger | Zeile | Stufe |
|---|---|---|
| `bc1.kern` | `ki_aufruf korrelation=<id> art=<extraktion\|antwort> ergebnis=<ok\|fehler> dauer_ms=<int>` | INFO, bei `fehler` WARNING |
| `bc1.kern` | `verarbeitung_fehlgeschlagen korrelation=<id> klasse=<Ausnahmeklasse>` | WARNING |
| `bc1.kern` | `validierung korrelation=<id> feld=<Feldname> ergebnis=<ungueltig\|unklar>` | INFO |
| `bc1.kern` | `feld_ungeloest korrelation=<id> feld=<Feldname> grund=<nachfrage_limit_erreicht\|runden_limit_erreicht>` | INFO |
| `bc1.ki` | `ki_wiederholung korrelation=<id> anbieter=claude versuch=<n>` (n ≥ 2) | WARNING |
| `bc1.api` | `unerwartete_ausnahme korrelation=<id> klasse=<Ausnahmeklasse>` | ERROR |
| `bc1.writer` | `profil_write_fehlgeschlagen session=<id> grund=<Klasse: erste Meldungszeile>` | ERROR |
| `bc1.dienst` (geändert) | Turn-Zeile wie P5; `status=` trägt bei einer abgewiesenen Anfrage den Fehlerschlüssel (`session_abgeschlossen`, `gleichzeitige_anfrage`, `profil_write_fehlgeschlagen`, `interner_fehler` …) statt `-` | wie P5 |

Außerhalb eines `/turn` (CLI, Testprofil-Werkzeug, Tests ohne Dienst) steht `korrelation=-`. Die neuen Kern-Zeilen entstehen **je Verarbeitungsversuch**: Wird ein Turn nach einem KI-Ausfall als `fehler_fortsetzbar` zurückgerollt, schreibt der Wiederholungsversuch sie erneut (ebenso beim Crash-Resume).

## Entscheidungen (Claude, 25.10.)

| # | Entscheidung | Warum |
|---|---|---|
| E1 | Korrelation als `ContextVar` `aktuelle_korrelation` (Vorgabe `"-"`) in einem neuen Modul `bc1_core/protokoll.py`. Der Dienst setzt sie in `/turn`, Kern und Adapter lesen sie. Kein `reset`. | Der Kern darf nicht vom Dienst abhängen, und kein Aufruf braucht einen neuen Parameter. Ein `reset` ist unnötig: anyio führt jeden synchronen Endpunkt in einer eigenen Kopie des Kontexts aus (`copy_context()`/`context.run`, anyio `_backends/_asyncio.py`; vom Prüfer zusätzlich gemessen: kein Übertrag zwischen zwei Anfragen). |
| E2 | Die Dauer misst der **Kern** um `llm.extract` (`extractor.py`) und `llm.antworte` (`core.py`), mit einem Kontextmanager `ki_aufruf(art)`. Nicht jeder Adapter einzeln. | Eine Stelle für alle drei Adapter; das LLM bleibt austauschbar (Projektregel). |
| E3 | Wiederholungen sieht nur der Claude-Adapter, über die **öffentliche Middleware des SDK**: `anthropic.Anthropic(..., middleware=[_wiederholung_protokollieren])`. Die Middleware läuft im Wiederholungskreis des SDK einmal je Versuch, im aufrufenden Thread, und kennt `APIRequest.retries_taken` (anthropic 0.121.0, `_middleware.py`, `_request.py`; exportiert in `anthropic/__init__.py`). Gemini (`HttpRetryOptions(attempts=1)`) und Ollama wiederholen nie; dort gibt es nichts zu protokollieren. | Keine eigene Wiederholungsschleife, das SDK macht Backoff und `retry-after` schon (Prinzip „Bewährtes nutzen"). Die SDK-eigene INFO-Zeile „Retrying request to … in … seconds" (`anthropic._base_client`) trägt keine Korrelation. `pyproject.toml` bleibt ohne Versionsgrenze, wie die übrigen Dienst-Abhängigkeiten dort: `uv.lock` pinnt 0.121.0, das Image baut mit `uv sync --frozen`, und ein älteres SDK ohne `middleware` scheiterte beim Start laut (`TypeError`). |
| E4 | Ausnahmen erscheinen in Kern-, Adapter- und Dienstzeilen nur als `type(fehler).__name__`, nie mit Text, `exc_info` oder Traceback. | Ausnahmetexte können Inhalte tragen, etwa JSON-Ausschnitte aus `json.loads`, Werte aus einem `KeyError` oder den Nutzerwert in `ProfilWriteError` aus `_dezimal`/`_ganzzahl`. **Folge:** Die eigenen Fehler der Adapter (Ablehnung, abgeschnitten, leer) erscheinen alle als `RuntimeError`. Unterscheiden ließe sich das über eine eigene Ausnahmeklasse mit fester Kennung; zurückgestellt mit Ziel (Abschnitt „Zurückgestellt"). |
| E5 | `validierung` wird im **Extraktor** geschrieben, je Kandidat, nach dem das Feld `ungueltig` oder `unklar` ist. Nicht in `status_fuer`. `feld_ungeloest` schreibt `decide_next` an den beiden Stellen, die ein Feld aufgeben, ohne weitere Bedingung. | `status_fuer` ruft auch der Sweep des Writers auf (`profil_writer.py` ~307); dort entstünden falsche Validierungszeilen. Eine Übergangsprüfung braucht `decide_next` nicht: Beide Schleifen besuchen nur Felder aus `offene_pflichtfelder` bzw. `offen`, und dort fehlen aufgegebene Felder (`confidence.py`, vom Prüfer gemessen). |
| E6 | Unerwartete Ausnahme in `/turn`: Der Endpunkt fängt sie selbst, schreibt `unerwartete_ausnahme`, antwortet 500 mit `detail="interner_fehler"` und festem `chat_text`. | Ein `exception_handler(Exception)` reicht nicht. Starlettes `ServerErrorMiddleware` wirft die Ausnahme nach jedem 500-Handler erneut („We always continue to raise the exception", starlette 1.6.0, `middleware/errors.py`), danach schreibt uvicorn den Traceback. Eine `HTTPException` geht dagegen über die `ExceptionMiddleware` und wird nicht erneut geworfen. |
| E7 | Writer: `baue_profilinhalt` und `wende_sweep_an` bekommen `protokollieren: bool = True` (nur Schlüsselwort). Der Writer übergibt `antwort["status"] == "fertig"`. Die Befunde stehen weiter im Profil-JSON, sooft es geschrieben wird (Anlegen, Umbinden, Einfrieren); nur die WARNING-Zeilen `kp_tp_diskrepanz`, `eigner_rolle_abweichung` und `snn_entfernt` kommen einmal im Abschluss-Turn. Der BC0-Eigner wird nur gelesen, wenn `process_owner_role` einen gültigen Wert hat. | Rückstellung (4e). `snn_entfernt` hat dasselbe Muster (der State behält die Kennung, jeder Turn sweept neu) und kommt deshalb dazu, mit eigenem Test. Vorgabe `True`: Wer den Parameter vergisst, bekommt Rauschen, aber kein Schweigen. Wird ein schon eingefrorenes Profil wiederholt abgefragt (Replay), entstehen die Zeilen erneut — selten, hingenommen. |
| E8 | `ProfilWriteError` im Terminal-Turn trägt `_fehlergrund(fehler)` statt `str(fehler)`. Dazu schreibt der terminale Zweig von `reconcile` vor dem `raise` die Zeile `profil_write_fehlgeschlagen` mit `_fehlergrund(fehler)`, als Gegenstück zu `profil_write_uebersprungen` im nicht-terminalen Zweig. | Befund M8 der Härtungsprüfung. Heute scheitert der Abschluss mit 503, und kein Protokoll nennt den Datenbankgrund (Prüfer I4, gemessen an einer FK-Verletzung). Nur der `except Exception`-Zweig schreibt die Zeile; ein `ProfilWriteError` aus dem Inneren wird nie als Text protokolliert (E4). |
| E9 | `lies_bc0_zugang`: `urlsplit` und `.port` in `try`, ein `ValueError` wird zu `RuntimeError(MELDUNG_URL_UNLESBAR) from None`, und zwar **vor** der https-Prüfung. | Gemessen: `urlsplit("https://u＠host")` wirft `ValueError` mit `netloc` im Text; `https://host:geheim` geht durch `urlsplit` durch, `.port` wirft mit `'geheim'`, httpx später mit `InvalidURL: Invalid port: 'geheim'`. `from None`, weil die verkettete Ausnahme sonst im Traceback stünde. Die https-Meldung wiederholt die Adresse (`http://host:geheim` gäbe heute „geheim" darin aus), deshalb kommt diese Prüfung vorher. |
| E10 | Ein Logger-Baum: `bc1_service.api` → `bc1.api`, `bc1_service.profil_writer` → `bc1.writer`, `bc1_service.bc0_meldungen` → `bc1.bc0`; neu `bc1.kern`, `bc1.ki`; `bc1.dienst` bleibt. | #266 verlangt „ein Logger-Baum (`bc1.*`)". B3 Teil 2 setzt dann nur `bc1` auf INFO statt zweier Bäume. |
| E11 | Turn-Zeile: Bei einer `HTTPException` trägt `status=` deren `detail` (unsere festen Schlüssel aus `api.py`) statt `-`. | Ohne das ist ein verlorener Schreibwettlauf im Store (`gleichzeitige_anfrage`) im Protokoll nicht von `session_abgeschlossen` oder `mandant_konflikt` zu unterscheiden (Prüfer I3), und ein 503 nicht von einem 500. Kostet eine Zeile; ändert den P5-Zeilenvertrag (README) und einen P5-Test. Teil von A1, zur Bestätigung. |

### Abweichungen und Vertragsänderung — zur Bestätigung durch die BC1-Projektleitung

- **A1 Store ohne eigene Zeilen, dafür der Grund in der Turn-Zeile (E11).** #266 nennt den Datenbank-Store. Store-Fehler sind Ausnahmen, die die Dienstschicht ohnehin behandelt: eine beschädigte Zeile → `sitzung_beschaedigt` (eigene Zeile, schon heute); ein verlorener Schreibwettlauf → 409 `gleichzeitige_anfrage`; alles andere → `unerwartete_ausnahme` (E6). Heute steht der 409-Grund **nicht** in der Turn-Zeile (`status=-`); mit E11 steht er dort. Die Dauer des Stores steckt in `dauer_ms` der Turn-Zeile. Eigene Store-Zeilen wären dann doppelt. **Ohne E11** wäre ein Store-Konflikt bis B3 Teil 2 im Protokoll nicht erkennbar. **Empfehlung:** E11 mitnehmen.
- **A2 „Start- und Abbruchgründe des Dienstes".** Der Start steht seit P5 im Protokoll (`dienst gestartet paket=… schema_version=… mandant=…`). Bricht der Start ab, bleibt es beim Python-Traceback mit der festen, für Menschen geschriebenen Meldung aus `start.py`/`main.py`. Beim Start gibt es noch keine Gesprächsinhalte, und mit E9 auch keine Adressteile. Eine Zeile `dienst_start_abgebrochen` passte in das vorhandene `except` von `main.py`. Sie deckte aber nur den Teil ab dem Pool ab, nicht die Konfigurationsfehler davor (DSN, Mandant, Melder). Außerdem bräuchte sie einen Test, der `main` importiert, und der zieht die offene Fixture-Schuld „Neu 24.10. — aus B8" (1) nach sich. Bricht ein Turn zur Laufzeit ab, steht das in `unerwartete_ausnahme` (E6). Wie ein Interview endet, zeigen der Status der Turn-Zeile und `feld_ungeloest`. **Empfehlung:** keine eigene Startabbruch-Zeile.
- **A3 Writer- und Prosazeilen ohne Correlation-ID.** #266 verlangt „ein Format, eine Correlation-ID". Die sieben Writer-Zeilen behalten `session=` ohne Kennung. Sie laufen innerhalb des Turns, und eine Sitzung hat nie zwei Turns zugleich (Sitzungs-Lock in `api.py`, ein Prozess): Sitzung und Zeit bestimmen den Turn eindeutig. Die Prosazeilen in `bc1.api` (`sitzung_beschaedigt: …`, Gate-Zeilen) bleiben, wie sie sind; die Gate-Zeilen laufen nach der Antwort im Hintergrund und nennen die Anfrage. **Empfehlung:** so lassen; das Umbauen brächte keine neue Information. Mit mehreren Workern (B3 Teil 2) neu bewerten.

## Global Constraints

- TDD unter dem tdd-guard, nie umgangen. `*.py` unter `coe-factory/` **nur mit Edit/Write**; Bash nur für pytest, git und Messungen. Ein neuer Test je Edit (ein parametrisierter Test zählt als einer). Jeder Zwischenschritt mit eigenem **vollem** pytest-Lauf. Die Reihenfolgeregeln aus dem Skill `tdd-guard` gelten: Importfehler → nur Stub; Name erst benutzen, dann definieren (`NameError` als RED, auch für Logger); im roten Schritt nicht umbauen; Bestandstests erst Aufruf, dann Erwartung.
- pytest aus `bc1-context-discovery/`: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`. Ausgangsstand auf `main` @ `a27c23f`: 837 bestanden, 4 übersprungen.
- Zeilen exakt wie in der Tabelle oben. Ausnahmen nur als `type(fehler).__name__` (Writer: `_fehlergrund`). `dauer_ms` wie P5: `round((time.perf_counter() - beginn) * 1000)`.
- Neue Wortlaute: `MELDUNG_URL_UNLESBAR = ("BC1_BC0_URL ist keine lesbare Adresse (Rechnername oder Port). Die Adresse wird hier bewusst nicht wiederholt — sie könnte Zugangsdaten enthalten.")` in `bc1_service/bc0_meldungen.py`. `FEHLER_TEXTE["interner_fehler"] = ("Da ist auf unserer Seite etwas schiefgegangen. Bitte senden Sie Ihre Nachricht in einem Moment noch einmal.")` in `bc1_service/api.py`.
- Zweig `bc1-b7-teil-2`. Commits auf Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Kein Push ohne OK.

## Review Focus

1. **Reihenfolge der `except` in `/turn`:** 409 und 503 sind `HTTPException` und dürfen nicht im neuen allgemeinen Fänger landen. Abgedeckt durch die Bestandstests zu 409/503 in `test_api.py`/`test_protokoll.py` und T5.3.
2. **Vertrag „fehler_fortsetzbar" bleibt:** `ki_aufruf` wirft jede Ausnahme unverändert weiter, nur protokolliert. Abgedeckt durch die Bestandstests in `test_core.py` (LLM-Ausfall) und T2.2.
3. **Korrelation in jeder neuen Zeile, auch auf dem Fehlerpfad:** T2.3 (parametrisiert: normaler Turn, KI-Ausfall), Task 3 mit gesetzter Kennung, T4.1 mit dem echten SDK und `httpx.MockTransport`, ohne Netz.
4. **Kein Inhalt aus dem Kern:** Ein ungültiger Wert und ein Ausnahmetext mit Geheimwort dürfen in keiner Zeile stehen. Abgedeckt durch T2.2 und T3.1.
5. **Bestehende Rauschunterdrückung:** `fremder_draft_konflikt` (einmal je Sitzung, `_konflikt_zuletzt`) bleibt unberührt; die Bestandstests in `test_profil_writer.py` müssen grün bleiben.

## Tasks

### Task 1 — Ein Logger-Baum `bc1.*` (E10)

Dateien: `bc1_service/api.py`, `bc1_service/profil_writer.py`, `bc1_service/bc0_meldungen.py`, `tests/test_protokoll.py`, `tests/test_api.py`, `tests/test_bc0_meldungen.py`.

- [ ] T1.1 in `tests/test_protokoll.py`: `test_alle_bc1_logger_haengen_am_baum_bc1` — importiert `api`, `bc0_meldungen`, `profil_writer` aus `bc1_service` und prüft `(api.log.name, bc0_meldungen.log.name, profil_writer.log.name) == ("bc1.api", "bc1.bc0", "bc1.writer")`.
- [ ] Volle Suite → RED (Assertion).
- [ ] Die drei `getLogger(__name__)` auf die festen Namen umstellen (ein Edit je Datei, Lauf dazwischen).
- [ ] Volle Suite: rot werden die Bestandstests, die nach dem alten Namen filtern — in `tests/test_api.py` die Gate-Tests (4) und `test_beschaedigte_sitzung_wird_ohne_zeileninhalt_als_fehler_geloggt` (über `_api_log`), in `tests/test_bc0_meldungen.py` `test_baue_melder_beim_aus_liefert_none_und_warnt` (über `_eigene`). Dort `_api_log`, `_eigene` und deren `caplog.at_level(..., logger=…)` auf `bc1.api` bzw. `bc1.bc0` umstellen → GREEN.
- [ ] Zwei Tests werden **nicht** rot, prüften nach dem Umbenennen aber nichts mehr: `test_ohne_melder_kein_aufruf_und_keine_logzeile` (`test_api.py` ~651) und `test_baue_melder_mit_zugang_liefert_einen_melder_ohne_warnung` (`test_bc0_meldungen.py` ~147). Ihre `at_level`-Namen ebenfalls umstellen (Umbenennung bei Grün) → volle Suite.
- [ ] Commit `refactor(bc1): ein Logger-Baum bc1.* (B7 Teil 2)`.

### Task 2 — Korrelation und KI-Dauer im Kern (E1, E2, E4)

Dateien: neu `bc1_core/protokoll.py`, `bc1_core/extractor.py`, `bc1_core/core.py`, `bc1_service/api.py`; Tests neu `tests/test_protokoll_kern.py`, dazu `tests/test_protokoll.py`.

**Liefert:** `aktuelle_korrelation: ContextVar[str]` (Name `"bc1_korrelation"`, Vorgabe `"-"`) und `ki_aufruf(art: str)` (Kontextmanager, `contextlib.contextmanager`) in `bc1_core/protokoll.py`; Logger `logging.getLogger("bc1.kern")`.

- [ ] T2.1 neu `tests/test_protokoll_kern.py`: `test_ki_aufrufe_werden_mit_dauer_protokolliert` — ein Turn mit `FakeLLM` über `process_turn` (TOY_PROZESS, InMemoryStateStore, Mandant wie in `test_core.py`), `caplog.set_level(logging.INFO, logger="bc1.kern")`. Erwartet: genau zwei Zeilen, die auf `^ki_aufruf korrelation=- art=(extraktion|antwort) ergebnis=ok dauer_ms=\d+$` passen, Arten in der Reihenfolge `["extraktion", "antwort"]`, beide INFO.
- [ ] Volle Suite → RED (keine Zeilen).
- [ ] Aufrufer zuerst: in `extract_and_merge` `with ki_aufruf("extraktion"):` um `llm.extract(...)`, Import aus `bc1_core.protokoll` → Lauf (ImportError) → `bc1_core/protokoll.py` nur mit einem Stub `ki_aufruf`, der `yield` macht → Lauf (Assertion-RED) → Messung und INFO-Zeile in `ki_aufruf` (Logger erst benutzen, dann definieren, je mit Lauf) → dasselbe für `llm.antworte` in `core.py` (`with ki_aufruf("antwort"): text = llm.antworte(kontext)`, dann `ersetze_pii(text)`) → GREEN. In T2.1 und T2.2 darf `korrelation=-` noch als Literal stehen; die `ContextVar` treibt erst T2.3.
- [ ] T2.2 `test_ki_fehler_wird_mit_klasse_und_ohne_text_protokolliert` — `FakeLLM`-Unterklasse, deren `antworte` `RuntimeError(GEHEIM)` wirft (`GEHEIM = "Geheimwort Nordlicht 4711"`). Erwartet: Antwort `fehler_fortsetzbar`; eine WARNING-Zeile `ki_aufruf korrelation=- art=antwort ergebnis=fehler dauer_ms=<int>` und eine WARNING-Zeile `verarbeitung_fehlgeschlagen korrelation=- klasse=RuntimeError`; `GEHEIM` in keiner Meldung aller Logger (`caplog.set_level(logging.DEBUG)`).
- [ ] RED → `ki_aufruf` schreibt bei Ausnahme die WARNING-Zeile und wirft weiter (`raise`) → Lauf → `except Exception as fehler:` in `process_turn` schreibt `verarbeitung_fehlgeschlagen` vor dem Neuladen → GREEN.
- [ ] T2.3 in `tests/test_protokoll.py`: `test_korrelation_erreicht_den_kern(llm_faellt_aus)`, parametrisiert über `False`/`True` — `/turn` mit Header `X-Correlation-ID: k-4711`; bei `True` ein `FakeLLM`, dessen `antworte` wirft. `caplog.set_level(logging.INFO, logger="bc1.kern")`. Erwartet: mindestens zwei `bc1.kern`-Zeilen, **alle** enthalten `korrelation=k-4711` (bei `True` also auch `ki_aufruf … ergebnis=fehler` und `verarbeitung_fehlgeschlagen`).
- [ ] RED → Guard-Schritte: in `turn()` direkt nach `korrelation = _korrelation(...)` `aktuelle_korrelation.set(korrelation)` mit Import → Lauf (ImportError) → `aktuelle_korrelation` in `protokoll.py` → Lauf (Assertion-RED, die Zeilen tragen noch `-`) → `ki_aufruf` liest `aktuelle_korrelation.get()` → Lauf → `verarbeitung_fehlgeschlagen` ebenso → GREEN.
- [ ] Commit `feat(bc1): KI-Aufrufe mit Dauer und Korrelation protokollieren (B7 Teil 2)`.

### Task 3 — Validierung je Feld (E5)

Dateien: `bc1_core/extractor.py`, `bc1_core/dialog.py`; Test `tests/test_protokoll_kern.py`.

In dieser Datei setzt eine Fixture `korrelation` die Kennung für den Test: `token = aktuelle_korrelation.set("k-1")`, `yield`, `aktuelle_korrelation.reset(token)`. Sie kommt mit T3.1. Alle Task-3-Tests nutzen sie und erwarten `korrelation=k-1`.

- [ ] T3.1 `test_ungueltiger_wert_wird_ohne_wert_protokolliert(korrelation, caplog)` — `FakeLLM({"x": [ExtractionCandidate("haeufigkeit", "Geheimwort Polarstern")]})` (der Validator von TOY verlangt eine Ziffer). Erwartet: Zeile `validierung korrelation=k-1 feld=haeufigkeit ergebnis=ungueltig` (INFO), `"Polarstern"` in keiner Meldung.
- [ ] RED → am Ende des Schleifenrumpfs in `extract_and_merge`: Status des Felds lesen, bei `UNGUELTIG` die Zeile mit `ergebnis=ungueltig` → GREEN. (Logger `bc1.kern` im Modul: erst benutzen, dann definieren.)
- [ ] T3.2 `test_widerspruch_wird_als_unklar_protokolliert(korrelation, caplog)` — zwei Turns: `prozess_name` „Freigabe", dann „Bestellung". Erwartet: die **vollständige** Liste der `validierung`-Zeilen über beide Turns ist `["validierung korrelation=k-1 feld=prozess_name ergebnis=unklar"]` (ein gültiger Wert erzeugt keine Zeile).
- [ ] RED → Bedingung auf `UNGUELTIG`/`UNKLAR` erweitern, `ergebnis` aus `status.value` → GREEN.
- [ ] T3.3 `test_feld_am_nachfrage_limit_wird_einmal_protokolliert(korrelation, caplog)` — direkt über `decide_next`: State mit `haeufigkeit` `UNGUELTIG`, `attempts=2`, `prozess_name` und `ausloeser` gültig; zweimal `decide_next(state, TOY_PROZESS, confidence_check(state, TOY_PROZESS))`. Erwartet: genau eine Zeile `feld_ungeloest korrelation=k-1 feld=haeufigkeit grund=nachfrage_limit_erreicht`.
- [ ] RED → Zeile in der Cap-Schleife von `decide_next`, ohne weitere Bedingung (E5) → GREEN.
- [ ] T3.4 `test_runden_limit_protokolliert_jedes_aufgegebene_feld(korrelation, caplog)` — State mit `rounds` auf dem Rundenlimit (wie `test_dialog.py` es aufbaut), nur `prozess_name` gültig. Erwartet: genau die Zeilen `feld_ungeloest korrelation=k-1 feld=ausloeser grund=runden_limit_erreicht` und `… feld=haeufigkeit …`, in Paketreihenfolge.
- [ ] RED → Zeile in der Rundenlimit-Schleife → GREEN.
- [ ] Commit `feat(bc1): Validierung und aufgegebene Felder je Feld protokollieren (B7 Teil 2)`.

### Task 4 — Wiederholungen im Claude-Adapter (E3)

Dateien: `bc1_service/claude_llm.py`; Test `tests/test_claude_llm.py`.

**Liefert:** `_wiederholung_protokollieren(anfrage, weiter)` auf Modulebene in `claude_llm.py`: schreibt bei `anfrage.retries_taken >= 1` die `ki_wiederholung`-Zeile (`versuch = retries_taken + 1`, Logger `bc1.ki`) und gibt `weiter(anfrage)` zurück.

- [ ] T4.1 `test_wiederholung_wird_mit_versuch_und_korrelation_protokolliert` — echter Client ohne Netz: `anthropic.Anthropic(api_key="test", base_url="http://anthropic.test", http_client=httpx.Client(transport=httpx.MockTransport(antwort)), max_retries=1, middleware=[_wiederholung_protokollieren])`. `antwort` liefert beim ersten Aufruf 529 mit Header `retry-after-ms: 1` und Rumpf `{"type": "error", "error": {"type": "overloaded_error", "message": "x"}}`, beim zweiten 200 mit einer minimalen Message (`id`, `type: message`, `role: assistant`, `model`, `content: [{"type": "text", "text": "ok"}]`, `stop_reason: end_turn`, `stop_sequence: null`, `usage: {input_tokens: 1, output_tokens: 1}`). Korrelation im Test per `aktuelle_korrelation.set("k-1")` setzen und im `finally` zurücksetzen. Aufruf `client.messages.create(model="m", max_tokens=10, messages=[{"role": "user", "content": "hallo"}])`. Erwartet: `bc1.ki`-Meldungen `== ["ki_wiederholung korrelation=k-1 anbieter=claude versuch=2"]`, Stufe WARNING, zwei Anfragen beim Transport. (Vom Prüfer unter `-W error` simuliert: läuft.)
- [ ] Volle Suite → RED (ImportError) → Funktion als Durchreicher (`return weiter(anfrage)`) → Lauf (Assertion-RED) → Zeile ergänzen (Logger erst benutzen, dann definieren) → GREEN.
- [ ] T4.2 `test_standard_client_meldet_wiederholungen` — `monkeypatch.setattr(claude_llm.anthropic, "Anthropic", aufzeichner)`; `ClaudeLLM()`. Erwartet: Aufruf mit `timeout=30.0, max_retries=1, middleware=[_wiederholung_protokollieren]`.
- [ ] RED → `middleware=[_wiederholung_protokollieren]` im Konstruktor → GREEN.
- [ ] Commit `feat(bc1): SDK-Wiederholungen des Claude-Adapters protokollieren (B7 Teil 2)`.

### Task 5 — Unerwartete Ausnahme ohne Traceback, Grund in der Turn-Zeile (E6, E11)

Dateien: `bc1_service/api.py`; Test `tests/test_protokoll.py`.

- [ ] T5.1 `test_unerwartete_ausnahme_erreicht_den_server_nicht` — `TestClient(create_app(_ExplodierenderStore(), _llm(), TOY_PROZESS, company_id=MANDANT))` **mit** `raise_server_exceptions=True` (Vorgabe). Erwartet: `_turn(...)` wirft nicht; Status 500; `json() == {"detail": "interner_fehler", "chat_text": FEHLER_TEXTE["interner_fehler"]}`; Header `X-Correlation-ID` vorhanden.
- [ ] Volle Suite → RED (Error: die Ausnahme dringt bis zum TestClient). Minimal: in `turn()` nach `except HTTPException` ein `except Exception:` mit `raise HTTPException(status_code=500, detail="interner_fehler", headers={"X-Correlation-ID": korrelation}) from None` (`http` steht schon auf 500) → Lauf → Assertion-RED (`chat_text` fehlt) → Eintrag in `FEHLER_TEXTE` → GREEN.
- [ ] T5.2 `test_unerwartete_ausnahme_wird_mit_klasse_protokolliert` — gleicher Aufbau, `caplog.set_level(logging.INFO, logger="bc1.api")`. Erwartet: `bc1.api`-Meldungen `== [f"unerwartete_ausnahme korrelation={antwort.headers['X-Correlation-ID']} klasse=RuntimeError"]`, ERROR, `exc_info is None`, `GEHEIM` nicht enthalten.
- [ ] RED → `log.error(...)` im Fänger → GREEN.
- [ ] T5.3 `test_abgewiesener_turn_nennt_den_grund_im_status` — wie `test_409_schreibt_eine_zeile_mit_strich_als_status` (drei Turns bis `fertig`, dann `m4`). Erwartet: `http == "409"` und `status == "session_abgeschlossen"`.
- [ ] RED → im `except HTTPException` `status = fehler.detail` → Lauf: rot ist dann `test_409_schreibt_eine_zeile_mit_strich_als_status` an `status == "-"` → nur diese Erwartung auf `"session_abgeschlossen"` ändern → GREEN → bei Grün den Testnamen auf `test_409_schreibt_eine_zeile_mit_dem_grund_als_status` ändern → Lauf. Die `HTTPException` aus dem Fänger von T5.1 läuft nicht durch das benachbarte `except HTTPException`; ihr Status kommt deshalb mit eigenem Test T5.4.
- [ ] T5.4 `test_unerwartete_ausnahme_steht_als_interner_fehler_in_der_turn_zeile` — `_ExplodierenderStore`, `caplog.set_level(logging.INFO, logger="bc1.dienst")`. Erwartet: eine Turn-Zeile mit `http=500` und `status=interner_fehler`. RED → `status = "interner_fehler"` im Fänger → GREEN.
- [ ] Commit `fix(bc1): unerwartete Ausnahme ohne Traceback, Grund in der Turn-Zeile (B7 Teil 2)`.

### Task 6 — Writer: Befunde einmal, Eigner nur bei gültiger Rolle, Abschlussfehler protokolliert (E7, E8)

Dateien: `bc1_service/profil_writer.py`; Tests `tests/test_profil_bau.py` (ohne DB), `tests/test_profil_writer.py` (DB).

- [ ] T6.1 (`test_profil_bau.py`) `test_eigner_wird_ohne_gueltige_rolle_nicht_gelesen` — `process_owner_role` `UNGUELTIG` (wie im Nachbartest), `bc0_eigner=lambda kp: pytest.fail("BC0-Eigner gelesen")`. Erwartet: kein Fehlschlag, kein Befund `eigner_rolle_abweichung`.
- [ ] RED → `bc0_rolle = bc0_eigner(process_id) if interview_rolle is not None else None` → GREEN.
- [ ] T6.2 (`test_profil_bau.py`) `test_ohne_protokollieren_keine_eigner_warnung` — wie `test_eigner_abweichung_ergibt_befund_und_warnung`, aber `protokollieren=False`. Erwartet: Befund vorhanden, keine Meldung mit `eigner_rolle_abweichung`.
- [ ] RED (`TypeError`) → nur der Parameter `*, …, protokollieren: bool = True` → Lauf (Assertion-RED) → Warnung unter `if protokollieren:` → GREEN.
- [ ] T6.3 `test_ohne_protokollieren_keine_kp_warnung` — wie `test_identitaet_kommt_allein_aus_der_tp_id` mit `protokollieren=False`: Befund `kp_tp_diskrepanz` vorhanden, keine Meldung. RED → `if protokollieren:` → GREEN.
- [ ] T6.4 `test_ohne_protokollieren_keine_snn_zeile` — nach dem Muster von `test_entfernte_kennung_landet_im_log`, aber über `baue_profilinhalt(..., protokollieren=False)` mit einer unbekannten Kennung im Systemfeld. Erwartet: keine `snn_entfernt`-Meldung, die Kennung trotzdem aus dem Profil entfernt. RED → Aufrufer `wende_sweep_an(..., protokollieren=protokollieren)` → Lauf (`TypeError`) → Parameter `protokollieren: bool = True` in `wende_sweep_an` → Lauf → Zeile unter `if protokollieren:` → GREEN.
- [ ] T6.5 (`test_profil_writer.py`, DB) `test_befund_warnung_nur_im_abschluss_turn(pool, caplog)` — `EIGNER_PAKET`, Rolle R-01 gegen BC0-Eigner R-02 (wie `test_interview_mit_abweichung_endet_fertig_mit_spalte_und_befund`); `reconcile` mit `FRAGE`, `FRAGE`, `FERTIG` unter `caplog.at_level("WARNING")`. Erwartet: genau eine Meldung mit `eigner_rolle_abweichung`.
- [ ] RED → im Writer `protokollieren=antwort["status"] == "fertig"` an `baue_profilinhalt` → GREEN.
- [ ] T6.6 (`test_profil_writer.py`, DB) `test_profil_write_fehler_nennt_nur_die_erste_zeile(pool)` — Aufbau wie `test_geloeschte_rolle_bricht_erst_den_abschluss` (FK-Verletzung). Erwartet: `ProfilWriteError`, in `str(fehler.value)` weder `"\n"` noch `"DETAIL"`. (Vom Prüfer gemessen: heute rot, psycopg 3.3.4 trägt `\nDETAIL:` in `str()`.)
- [ ] RED → `f"Profil-Write im Terminal-Turn fehlgeschlagen: {_fehlergrund(fehler)}"` → GREEN.
- [ ] T6.7 (`test_profil_writer.py`, DB) `test_abschlussfehler_wird_ohne_detail_protokolliert(pool, caplog)` — derselbe Aufbau, `caplog.at_level("ERROR")`. Erwartet: genau eine Meldung, die mit `profil_write_fehlgeschlagen session=s1 grund=ForeignKeyViolation: ` beginnt, ohne `"DETAIL"`.
- [ ] RED → im terminalen Zweig von `reconcile` vor dem `raise` `log.error("profil_write_fehlgeschlagen session=%s grund=%s", state.session_id, _fehlergrund(fehler))` → GREEN.
- [ ] Commit `fix(bc1): Writer-Befunde nur beim Abschluss melden, Abschlussfehler ohne DETAIL protokollieren (B7 Teil 2)`.

### Task 7 — Kaputte `BC1_BC0_URL` ohne Adresse melden (E9)

Dateien: `bc1_service/bc0_meldungen.py`; Test `tests/test_bc0_meldungen.py`.

- [ ] T7.1 `test_unlesbare_adresse_bricht_ab_ohne_sie_zu_wiederholen(url)` plus Import von `MELDUNG_URL_UNLESBAR` (zwei Edits: erst Testfunktion, dann Import), parametrisiert über `"https://bc1＠bc0.example.org"` (Vollbreite-＠), `"https://bc0.example.org:geheim"`, `"http://bc0.example.org:geheim"` (sichert die Reihenfolge vor der https-Prüfung), `"https://[bc0.example.org"`. Erwartet: `RuntimeError`, `str(...) == MELDUNG_URL_UNLESBAR`, `__cause__ is None`, `__suppress_context__ is True`.
- [ ] Volle Suite → RED (Import) → nur die Konstante → Lauf (heute: `ValueError` bzw. „DID NOT RAISE" für `https://…:geheim`, `MELDUNG_KEIN_HTTPS` mit „geheim" für `http://…:geheim`) → `try`/`except ValueError` um `urlsplit` und `teile.port`, vor der https-Prüfung → GREEN.
- [ ] Commit `fix(bc1): unlesbare BC1_BC0_URL ohne Adressteile melden (B7 Teil 2)`.

### Task 8 — Doku, Gegenproben, Gesamtprüfung

- [ ] README „Betriebsprotokoll": die Tabelle der neuen Zeilen; der Logger-Baum `bc1.*`; `status=` der Turn-Zeile mit Fehlerschlüssel (E11); „Bekannte Lücke" ersetzen durch `interner_fehler`; der Satz „Kern, KI-Adapter und Store loggen in Teil 2" ersetzt durch den Stand samt A1–A3; „je Verarbeitungsversuch, nicht je gespeichertem Zustand"; Ausnahmen nur als Klasse (E4); Hinweis, dass das Anthropic-SDK auf DEBUG die Anfrage samt Nachrichten protokolliert (`anthropic._base_client`) — „nie Inhalte" gilt ab INFO, der Dienst läuft auf INFO.
- [ ] Abschlussplan: B7-Zeile (Teil 2 erledigt), „Neu 23.10." (6) (uvicorn-Traceback, `ProfilWriteError`, kaputte Adresse erledigt), „Neu 24.10. — aus C1a" (4e) erledigt; den B3-Teil-2-Punkt „Logger-Stufe" erweitern: `bc1` auf INFO **und** `anthropic`/`httpx` höchstens INFO; die Rückstellungen unten mit Ziel eintragen; „Nächstes Go" auf (3) ANZAHL.
- [ ] Gegenproben für jeden Test, der grün bei Ankunft war (geplant ist keiner; Liste beim Bauen führen): Kopie-Verfahren im Scratchpad (Skill `tdd-guard`), die erzeugende Zeile entfernen, der Test muss rot werden.
- [ ] Volle Suite mit und ohne DB. Gesamtprüfung durch einen unabhängigen Prüfer (Auftrag: jeder pytest-Aufruf mit `-p no:tdd-guard -p no:cacheprovider`); danach vor dem nächsten bewachten Edit ein regulärer Lauf.
- [ ] Commit `docs(bc1): B7 Teil 2 — README und Abschlussplan`.

## Zurückgestellt (mit Ziel)

| Punkt | Ziel / Auslöser |
|---|---|
| Eigene Fehler der Adapter (Ablehnung, abgeschnitten, leer, Kontingent) unterscheidbar machen: eigene Ausnahmeklasse mit fester Kennung, die der Kern ausgeben darf (E4) | Live-Bewertung im echten Chat (Paket 6 der Reihenfolge): wenn dort `klasse=RuntimeError` die Diagnose behindert |
| Korrelation in Writer-, Gate- und Prosazeilen (A3) | B3 Teil 2, sobald mehr als ein Worker läuft |
| `bc1` auf INFO, `anthropic`/`httpx` höchstens INFO | B3 Teil 2 (fremde Logging-Konfiguration entsteht erst auf dem Server) |
| Eigene Startabbruch-Zeile (A2), falls doch gewünscht | mit der Fixture-Schuld „Neu 24.10. — aus B8" (1), Paket (5) Test-Aufräumen |

## Befundverbleib (Prüfung 25.10.)

| Befund | Schwere | Verbleib |
|---|---|---|
| I1 Korrelation auf dem Fehlerpfad und in Task 3 ungetestet; Guard-Schritte zu T2.3 fehlten | Important | eingearbeitet (T2.3 parametrisiert, Fixture `korrelation` in Task 3, Guard-Schritte ausgeschrieben) |
| I2 Übergangsprüfung in `decide_next` ist toter Code, Begründung in E5 falsch | Important | eingearbeitet (E5 berichtigt, T3.3 als Regressionstest, Zeile ohne Bedingung) |
| I3 A1 behauptete den 409-Grund in der Turn-Zeile | Important | eingearbeitet (A1 berichtigt, E11 neu, T5.3/T5.4; zur Bestätigung) |
| I4 Abschlussfehler des Writers wird nirgends protokolliert | Important | eingearbeitet (E8 erweitert, T6.7) |
| M1 Guard-Schnitt (Stub zuerst, Logger benutzen vor definieren, `http = 500` überflüssig) | Minor | eingearbeitet (Global Constraints, T2.1, T5.1) |
| M2 Reihenfolge vor der https-Prüfung ungesichert; Ablauf „falsche Meldung" ungenau | Minor | eingearbeitet (vierter Fall `http://…:geheim`, Ablauf berichtigt) |
| M3 E11 (alt) war Abweichung von #266, nicht nur Entscheidung | Minor | eingearbeitet (jetzt A3, zur Bestätigung) |
| M4 Begründung zu A2 übertrieben | Minor | eingearbeitet (A2 berichtigt: Kosten sind Testschuld und Teilabdeckung) |
| M5 Anthropic-SDK protokolliert auf DEBUG Inhalte | Minor | eingearbeitet (README in Task 8, B3-Teil-2-Punkt erweitert) |
| M6 Liste der Bestandstests: zwei würden still nichts mehr prüfen | Minor | eingearbeitet (Task 1) |
| M7 T3.2 sicherte nicht ab, dass gültige Werte keine Zeile erzeugen | Minor | eingearbeitet (vollständige Liste) |
| M8 Zeilen entstehen je Verarbeitungsversuch | Minor | eingearbeitet (Zeilentabelle, README) |
| M9 Wortlaut E7 („in jedem Turn") und E3 („wie alle Abhängigkeiten") | Minor | eingearbeitet |
