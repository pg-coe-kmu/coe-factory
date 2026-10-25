# BC1 — Interactive Context Discovery

**Team:** Richard, Philipp
**Phase:** 1 — Discovery

## Zweck
Übersetzt unstrukturierte Eingaben (im MVP: Text-Chat; später Sprache/Dokumente/Bilder) in ein strukturiertes **Prozessprofil (JSON)** + **Confidence-/Vollständigkeits-Status** + **Prozessdoku** und übergibt am **Gate 0** an BC2. BC1 liefert das vollständige Prozessbild; die Auswahl konkreter Use Cases passiert außerhalb von BC1.

## Messages
- **Consumed:** Chat (MVP) · später Sprache, Dokumente, Bilder · Baseline (read-only)
- **Produced:** Prozessprofil (JSON), Confidence-Report, Prozessdoku → `contracts/bc1-to-bc2/`

## Bauweise
**Hybrid:** n8n-Hülle (Verrohrung) + Code-Kern (Gehirn). **MVP-first:** schlanker Text-Interview→JSON-Kern zuerst; weitere Schichten docken an, ohne den Kern zu ändern.

## Struktur
- `architektur/` — Systemarchitektur (technische Ebene, Überblick)
- `design/` — Design-Spec (das *Warum*) + Implementierungsplan (die *Anleitung pro Arbeitspaket*, inkl. Code/Tests)
- `bc1_core/` — Code-Kern: Dialog, Extraktion, Confidence, PII-Filter, Store-Vertrag
- `bc1_service/` — Dienst-Schicht: FastAPI, Postgres-Store, BC0-Lesepfade, LLM-Adapter; darin `db/` (Einspiel-Dateien) und `n8n/` (Chat-Hülle)
- `tests/` — Tests (`pytest`), Datenbank-Tests nur mit `BC1_TEST_DB_DSN`

## Wie man hier mitarbeitet
Die offenen Pakete stehen im [Abschlussplan](design/Abschlussplan-BC1.md). Jedes Paket bekommt ein GitHub-Issue (Label `bc1`) mit Ziel, Dateien und Akzeptanzkriterien. **Ein Issue = ein Branch ab `main` = ein kleiner PR** (Squash-Merge). Die Arbeitsregeln stehen in [`CLAUDE.md`](CLAUDE.md): Test zuerst, `pytest` aus `bc1-context-discovery/`.

## Arbeitspakete
[#48 KI-Interviewer](https://github.com/pg-coe-kmu/coe-factory/issues/48) — MVP-Kern gebaut ([PR #129](https://github.com/pg-coe-kmu/coe-factory/pull/129), DoD-Stand im Issue) · [#49 Voice/OCR](https://github.com/pg-coe-kmu/coe-factory/issues/49) — Stufe C · [#50 PII-Filter](https://github.com/pg-coe-kmu/coe-factory/issues/50) — gebaut (B2, PII-Filter) · [#51 JSON-Compiler](https://github.com/pg-coe-kmu/coe-factory/issues/51) — abgedeckt durch [#123](https://github.com/pg-coe-kmu/coe-factory/issues/123) · [#52 Doku-Generator](https://github.com/pg-coe-kmu/coe-factory/issues/52) — Stufe C · [#53 Mapper & Verifier](https://github.com/pg-coe-kmu/coe-factory/issues/53) — Stufe C

Was offen ist, steht im Abschlussplan.

## Schnittstellen
- **Input von BC0:** Baseline-Lookup (KP/TP/Reifegrad)
- **Output an BC2:** `contracts/bc1-to-bc2/` (Schema + Mock; gemeinsam mit BC2 + Platform)
- **Eigner-Rolle (seit C1a):** `process_owner_rolle_id` ist nicht mehr immer leer. Sie wird aus der im Interview gewählten Rolle (Frage B3, Auswahl aus `mandant_rollen`) gefüllt, aber nur bei gültigem B3-Wert, sonst `NULL`. Weicht die Wahl von BC0s Eigner-Rolle ab, steht im Profil ein Befund `eigner_rolle_abweichung`; BC1 ändert bei BC0 nichts. Der Start bricht ab, wenn für den Mandanten keine aktive Rolle erfasst ist (Meldung `MELDUNG_KEINE_ROLLEN`).

## PII-Filter

Jede Nachricht wird im Kern gefiltert, **bevor** sie gespeichert oder an einen
LLM-Anbieter gegeben wird (`bc1_core/pii.py`, Einhängung in `process_turn`).
Ein Original gibt es danach nicht — weder in `bc1.sessions` noch im Profil. Auch die
Anbieter-Ausgaben (Extraktionswerte, Antworttext) laufen durch den Filter.
Strategie: **maskieren**, kein Mapping-Tresor (kein Konsument für eine Rückersetzung).

| Klasse | Erkennung | Platzhalter | Quote Testset (Offline-Wert, kein Betriebsbestand) |
|---|---|---|---|
| E-Mail | Muster, auch Unicode-Domains und -Endungen (Punycode) | `[E-Mail A]` | 100 % |
| Telefon | Muster: `+`/`0`-Präfix, `(0)`, geklammerte Vorwahl, 7–14 Ziffern, Trenner inkl. geschützter Leerzeichen; Datums-, Uhrzeit- und Dezimalformen ausgenommen | `[Telefon A]` | 100 % |
| IBAN | Muster für bekannte Ländercodes, Groß-/Kleinschreibung, geschützte Leerzeichen, Soll-Länge je Land (Folgewort bleibt) | `[IBAN A]` | 100 % |
| Adresse | Straße/Allee/Gasse mit Hausnummer, optional PLZ + Ort; Weg/Platz nur mit PLZ + Ort; Prozessbegriffe („Fertigungsstraße 3") ausgenommen | `[Adresse A]` | 100 % |
| Name mit Hinweiswort | Anrede (Herr/Herrn/Frau/Hr./Fr.), Titel (Dr./Prof./Dipl., „Dr.-Ing.", Zusätze wie „med."), Partikel („von", „van der"), Kollege/Kollegin, „ich heiße", „mein Name ist"; Hinweiswort bleibt stehen | `[Person A]` | 100 % |
| Name ohne Hinweiswort | **nicht erkannt** (dokumentierte Lücke, braucht NER) | — | 0 % |

Quote = erkannte PII-Stellen / vorhandene Stellen im Testset (`tests/pii_testset.py`,
eine Stelle je Fall); `tests/test_pii_kpi.py` hält diese Tabelle gegen die Messung.
Fehltreffer auf den PII-freien Interviewsätzen des Testsets: 0. Kennungen laufen
je Klasse und Turn (A, B, …, AA) in Textreihenfolge; gleicher Wert im selben Turn
→ gleicher Platzhalter; über Turns hinweg keine Konsistenz.

Bekannte Grenzen: nackte Nachnamen („Mustermann prüft"), „ich bin X", Kartennummern,
Straßen ohne Straßenwort („Am Alten Markt 3"). Übererkennung ist akzeptiert („Dr. Oetker",
„Fr. Vormittag" werden `[Person A]`). NER folgt erst bei gemessenem Bedarf. Außerhalb
von BC1: n8n speichert Ausführungsdaten mit der Chat-Eingabe, bevor der Dienst sie
sieht — Hosting-Thema (B3). Konzept: `design/Konzept-B2-PII-Filter.md`.

## Use-Case-Testprofile (Version 3)

Die drei Testfälle (Anhang A der DB-Profil-Planung) lassen sich über den regulären Schreibweg neu erzeugen. Version 3 trägt `executions_per_run` = 1, eine Eigner-Rolle (B3) und eine `anfrage_id`. Die Anfragen kommen als Parameter, je Fokus-Teilprozess eine:

```bash
uv run python -m bc1_service.use_case_testprofile --company-id <uuid> \
  --anfrage KP-06.TP-2=A-… --anfrage KP-05.TP-1=A-… --anfrage KP-06.TP-1=A-… [--echt]
```

- **Ohne `--echt`** ein Trockenlauf: nichts wird geschrieben, BC0 wird nicht benachrichtigt.
- **Mit `--echt`** braucht jeder Fall seine `--anfrage TP=A-…` und `BC1_DB_DSN` (als `bc1_role`). Das Werkzeug prüft **zuerst alle** Anfragen (vorhanden, interviewbar, umfasst den Teilprozess, Sitzungsnummer nicht an eine andere Anfrage gebunden, Eigner-Rolle der Skripte beim Mandanten aktiv); bei einem Mangel gibt es eine Meldung, es wird nichts gemeldet und nichts geschrieben.
- **BC0 wird benachrichtigt wie vom Dienst:** Kontoprüfung, „Interview läuft“ nur aus `zugeordnet`, nach dem Schreiben das Gate. Die drei BC0-Variablen wie beim Dienst (`BC1_BC0_URL`, `BC1_BC0_KONTO_EMAIL`, `BC1_BC0_KONTO_PASSWORT`); `BC1_BC0_MELDUNGEN=aus` schaltet die Meldungen ab (nur lokal ohne BC0).
- **Wiederholbar:** Ein zweiter Lauf mit denselben Parametern überspringt, was schon zur selben Anfrage geschrieben ist („bereits geschrieben“), und holt einen gescheiterten Gate-Aufruf nach (ein Fehler dabei ist nur eine Warnzeile).

## Betriebsprotokoll

Der Dienst schreibt je `/turn` genau eine Zeile über den Logger `bc1.dienst` — auch bei 409/503/500
(Level INFO, bei HTTP 5xx — 503 und 500 — ERROR), dazu beim Start `dienst gestartet paket=… schema_version=… mandant=…`:

```
turn korrelation=<id> session=<session_id> message=<message_id> http=<200|409|503|500> status=<…> dauer_ms=<int>
```

`status` ist bei HTTP 200 der fachliche Status (`frage`, `fertig`, `abgebrochen_ohne_identitaet`,
`fehler_fortsetzbar`), bei einer abgewiesenen Anfrage der Fehlerschlüssel aus `detail` (z. B.
`session_abgeschlossen`, `gleichzeitige_anfrage`, `profil_write_fehlgeschlagen`, `sitzung_beschaedigt`,
`interner_fehler`). Die Correlation-ID kommt aus dem Header `X-Correlation-ID` (z. B. von n8n) oder wird
erzeugt und als `X-Correlation-ID` zurückgegeben. Seit B7 Teil 2 steht sie auch in den Zeilen, die Kern
und KI-Adapter während des Turns schreiben:

| Logger | Zeile | Stufe |
|---|---|---|
| `bc1.kern` | `ki_aufruf korrelation=<id> art=<extraktion\|antwort> ergebnis=<ok\|fehler> dauer_ms=<int>` | INFO, bei `fehler` WARNING |
| `bc1.kern` | `verarbeitung_fehlgeschlagen korrelation=<id> klasse=<Ausnahmeklasse>` | WARNING |
| `bc1.kern` | `validierung korrelation=<id> feld=<Feldname> ergebnis=<ungueltig\|unklar>` | INFO |
| `bc1.kern` | `feld_ungeloest korrelation=<id> feld=<Feldname> grund=<nachfrage_limit_erreicht\|runden_limit_erreicht>` | INFO |
| `bc1.ki` | `ki_wiederholung korrelation=<id> anbieter=claude versuch=<n>` (nur Claude; Gemini und Ollama wiederholen nicht) | WARNING |
| `bc1.api` | `unerwartete_ausnahme korrelation=<id> klasse=<Ausnahmeklasse>` | ERROR |
| `bc1.writer` | `profil_write_fehlgeschlagen session=<id> grund=<Klasse: erste Meldungszeile>` | ERROR |

Außerhalb eines Turns (CLI, Testprofil-Werkzeug) steht `korrelation=-`. Die Kern-Zeilen entstehen je
Verarbeitungsversuch: Scheitert die KI und schickt der Client die Nachricht erneut, stehen sie für den
neuen Versuch noch einmal da. Eine *unerwartete* Ausnahme in `/turn` beantwortet der Dienst selbst mit
500 `interner_fehler` und einem festen Chat-Text; sie erreicht uvicorn nicht, es entsteht kein Traceback.

**Nie im Protokoll:** Nachrichtentext, extrahierte Werte, Profildaten, Fragen, Chat-Texte, Ausnahmetexte
und Tracebacks — nur IDs, Feldnamen, Status, Klassennamen und Zahlen. Einzige Ausnahme: Der Profil-Writer
nennt bei Datenbankfehlern Klasse und erste Meldungszeile (Tabelle, Constraint), nie die DETAIL-Zeile.
Seine Befund-Warnungen (`kp_tp_diskrepanz`, `eigner_rolle_abweichung`, `snn_entfernt`) kommen nur im
Abschluss-Turn (ein Replay oder der erneute Versuch nach einem 503 meldet erneut). Die Befunde selbst
stehen im Profil; die entfernten Systemkennungen stehen bewusst nur in der Zeile `snn_entfernt` (und
weiter im Sitzungszustand, den der Sweep nicht ändert). Alle eigenen Logger hängen unter `bc1` (`bc1.dienst`,
`bc1.api`, `bc1.kern`, `bc1.ki`, `bc1.writer`, `bc1.bc0`). Das Protokoll geht auf die Standardausgabe des
Prozesses; im Container `docker logs <container>`.

Bewusst ohne eigene Zeilen (Entscheidung 25.10., `design/Plan-B7-Teil-2-Betriebsprotokoll.md`, A1–A3): der
Datenbank-Store — seine Fehler erscheinen als Grund in der Turn-Zeile, als `sitzung_beschaedigt` oder als
`unerwartete_ausnahme`; ein Startabbruch — er erscheint als Python-Traceback mit der festen Startmeldung,
beim Start gibt es noch keine Gesprächsinhalte. Writer- und Gate-Zeilen nennen die Sitzung bzw. die
Anfrage statt der Correlation-ID; mit nur einem Prozess ist der Turn darüber eindeutig.

Auf derselben Ausgabe stehen auch fremde Logger: `httpx` je ausgehender Anfrage (Methode, Adresse,
Status — kein Inhalt) und das Anthropic-SDK (`anthropic._base_client`, auf INFO „Retrying request …").
**Achtung:** Auf DEBUG protokolliert das Anthropic-SDK die Anfrage samt Nachrichten — „nie Inhalte" gilt
ab INFO, und der Dienst läuft auf INFO. Anfragen, die schon an der Body-Prüfung scheitern (422),
erscheinen nur im Zugriffslog von uvicorn. Dazu gehören seit der Härtung (25.10.) Sitzungs- und
Nachrichtenkennungen, die nicht zu `[A-Za-z0-9_-]{1,64}` passen — Sitzungskennungen stünden sonst roh im
Protokoll. n8n schickt eine UUID und `exec-<Nummer>`, beide passen.

## Setup und Start

Voraussetzungen: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Docker (für die Test-Datenbank), `psql`.

```bash
uv sync                                                            # .venv anlegen
docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:17
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q -W error
```

Dienst starten (Pflicht: `BC1_DB_DSN` als `bc1_role`, `BC1_COMPANY_ID`, `BC1_ANFRAGE_ID` — seit B5 die BC0-Anfrage, zu der interviewt wird, Form `A-JJJJ-NN`; seit B4 der BC0-Zugang (`BC1_BC0_URL`, `BC1_BC0_KONTO_EMAIL`, `BC1_BC0_KONTO_PASSWORT`; die Adresse ohne `@` — Zugangsdaten in der Adresse lehnt der Start ab, sie stünden sonst in jeder Protokollzeile) — lokal ohne echtes BC0 bewusst `BC1_BC0_MELDUNGEN=aus`; LLM-Wahl über `BC1_LLM` = `claude` | `ollama` | `gemini`, Key des Anbieters aus der Umgebung):

```bash
export BC1_DB_DSN="postgresql://…"        # Datenbank mit eingespielter DDL, siehe unten
export BC1_COMPANY_ID="<uuid des Mandanten>"
export BC1_ANFRAGE_ID="A-2026-03"         # Pflicht seit B5; Beispielwert
export BC1_BC0_MELDUNGEN=aus               # lokal ohne BC0; im Betrieb stattdessen:
# export BC1_BC0_URL="https://bc0.perspektivwechsel.ai"
# export BC1_BC0_KONTO_EMAIL="$BC0_APP_KONTO_EMAIL"      # aus der lokalen Zugangsdatei
# export BC1_BC0_KONTO_PASSWORT="$BC0_APP_KONTO_PASSWORT"
export BC1_LLM=ollama                      # lokal, ohne API-Key
.venv/bin/uvicorn bc1_service.main:app --port 8000
```

**Als Container:** Das Image enthält nur die Gruppe `service` aus `uv.lock` und den Code (`bc1_core/`, `bc1_service/`), keine Tests und keine Zugangsdaten; der Prozess läuft als eigener Benutzer, nicht als root. Datenbank und Tabellen müssen vorher da sein ([`bc1_service/db/EINSPIELEN.md`](bc1_service/db/EINSPIELEN.md)); alle Werte kommen per `-e` zur Laufzeit:

```bash
docker build -t bc1 bc1-context-discovery
docker run --rm -p 127.0.0.1:8000:8000 \
  -e BC1_DB_DSN="postgresql://…" -e BC1_COMPANY_ID="<uuid des Mandanten>" \
  -e BC1_ANFRAGE_ID="A-2026-03" -e BC1_LLM=claude -e ANTHROPIC_API_KEY \
  -e BC1_BC0_MELDUNGEN=aus \
  bc1
```

`BC1_BC0_MELDUNGEN=aus` nur für einen lokalen Versuch ohne BC0 — im Betrieb stattdessen die drei BC0-Variablen wie oben. Eine Datenbank auf dem eigenen Rechner erreicht der Container unter `host.docker.internal` statt `localhost`.

**Betriebsvoraussetzung (Pflicht):** Der Dienst hat keine Zugangsprüfung. Offen sind alle seine Endpunkte (`/turn`, `/gesundheit`, dazu FastAPIs `/docs`, `/redoc` und `/openapi.json`) und der n8n-Chat: Sein Chat-Trigger ist öffentlich, ohne Anmeldung, und reicht jede Nachricht an `/turn` weiter — wer den n8n-Port erreicht, kann Interviews führen. Beides darf nur auf dem eigenen Rechner oder im internen Docker-Netz erreichbar sein, bis es eine Zugangsprüfung gibt — darum `-p 127.0.0.1:8000:8000` hier und `-p 127.0.0.1:5678:5678` für n8n in [`SMOKE.md`](bc1_service/n8n/SMOKE.md).

**Messergebnis (24.10.2026, macOS, Docker Engine in colima):** Mit `-p 127.0.0.1:8000:8000` antwortet `/gesundheit` vom eigenen Rechner mit `200 ok`, und aus dem n8n-Image (ohne `--add-host`) antwortet `http://host.docker.internal:8000/gesundheit` ebenfalls mit `ok`; `/prozesse` liefert `404`. Ein an `127.0.0.1` veröffentlichter Test-Postgres ist aus einem Container über `host.docker.internal` erreichbar. **Nicht gemessen:** dass der Dienst aus dem lokalen Netz unerreichbar ist (die Aussage stützt sich auf Dockers dokumentiertes Verhalten), und Linux mit Docker Engine — dort gibt es `host.docker.internal` nur mit `--add-host=host.docker.internal:host-gateway`, es zeigt auf die Bridge-Adresse, und ein an `127.0.0.1` veröffentlichter Port ist von dort vermutlich nicht erreichbar. In so einer Umgebung gilt der Weg über ein gemeinsames Docker-Netz ohne veröffentlichten Port.

**Was der Dienst bei BC0 tut (seit B4):** Beim Start prüft er immer den Zugang (Anmeldung + eigenes Konto, ändert nichts) und bricht bei einem Mangel ab — auch bei einer Anfrage, die schon auf `im_interview` steht. Danach zieht er das Gate für die eigene Anfrage nach, noch bevor er aus der Datenbank liest (holt einen früher gescheiterten Gate-Aufruf nach; steht die Anfrage danach schon auf `am_gate`, endet der Start mit „steht auf 'am_gate'“). Dann meldet er der Anfrage `im_interview` — nur aus `zugeordnet`, ein Neustart überschreibt BC0s Stand also nicht. Nach jedem Abschluss eines Interviews zieht er das Gate bei BC0 nach, im Hintergrund; die Chat-Antwort hängt nicht davon ab. Alle Gate-Aufrufe tragen `?anfrage_id=` — BC0 prüft seit v3.13 nur diese Anfrage. Scheitert das, steht eine WARNING mit Handlungsanweisung im Log (die Anfrage bei BC0 von Hand nachziehen) — das Profil ist dann trotzdem gespeichert. Alles läuft über ein BC0-Anwendungskonto mit Schreibrecht (Rolle `benutzer` oder `admin`), das den Mandanten sieht (zugewiesen; `admin` sieht alle); das Passwort steht nur in der Umgebung, in keiner Meldung und in keinem Log. Ob das Konto bereit ist, zeigt die Live-Probe — sie ändert bei BC0 nichts (Anmeldung, dann nur Lesen des eigenen Kontos) und braucht `BC1_COMPANY_ID` und die drei BC0-Variablen, keine Datenbank:

```bash
uv run python -m bc1_service.bc0_meldungen --probe
```

Ausgabe: Rolle, Schreibrecht ja/nein, Mandant sichtbar ja/nein. Exit 0 = bereit; 1 = nicht bereit, oder Anmeldung bzw. Aufruf bei BC0 scheitern (die Meldung sagt warum); 2 = Konfiguration fehlt oder ungültig, oder `BC1_BC0_MELDUNGEN=aus` (dann gibt es nichts zu prüfen).

Der Dienst startet nur, wenn der Mandant bewertete Teilprozesse hat und die Anfrage interviewbar ist (Stand `zugeordnet`/`im_interview`, alle ihre Teilprozesse bewertet) — die regulären Startabbrüche (seit B4 auch die der BC0-Meldungen) und der Chat-Aufbau stehen in [`bc1_service/n8n/SMOKE.md`](bc1_service/n8n/SMOKE.md). Die Datenbanktabellen kommen aus [`bc1_service/db/prozessprofil.sql`](bc1_service/db/prozessprofil.sql); wie man sie einspielt und was die Dreifallregel bedeutet, steht in [`bc1_service/db/EINSPIELEN.md`](bc1_service/db/EINSPIELEN.md). Was das Interview fragt und in welche Spalte es fließt: [`design/Spalte-zu-Feld-Tabelle.md`](design/Spalte-zu-Feld-Tabelle.md). Was noch fehlt: [`design/Abschlussplan-BC1.md`](design/Abschlussplan-BC1.md).
