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

## Betriebsprotokoll

Der Dienst schreibt je `/turn` genau eine Zeile über den Logger `bc1.dienst` — auch bei 409/503/500
(Level INFO, bei HTTP 5xx — 503 und 500 — ERROR), dazu beim Start `dienst gestartet paket=… schema_version=… mandant=…`:

```
turn korrelation=<id> session=<session_id> message=<message_id> http=<200|409|503|500> status=<frage|fertig|abgebrochen_ohne_identitaet|fehler_fortsetzbar|-> dauer_ms=<int>
```

Die Correlation-ID kommt aus dem Header `X-Correlation-ID` (z. B. von n8n) oder wird erzeugt und als
`X-Correlation-ID` zurückgegeben. **Nie in dieser Zeile:** Nachrichtentext, extrahierte Werte, Profildaten,
Fragen oder Chat-Texte — nur IDs, Status und Zahlen. Das Protokoll geht auf die Standardausgabe des
Prozesses; im Container `docker logs <container>`. Kern, KI-Adapter und Store loggen in Teil 2 (B7).

Auf derselben Ausgabe stehen auch andere Logger: `httpx` je ausgehender Anfrage (Methode, Adresse,
Status — kein Inhalt), die Dienst-Schicht selbst (Gate bei BC0, beschädigte Sitzung), der Profil-Writer
und die BC0-Meldungen. Anfragen, die schon an
der Body-Prüfung scheitern (422), erscheinen nur im Zugriffslog von uvicorn. **Bekannte Lücke:** eine
*unerwartete* Ausnahme protokolliert uvicorn mit Traceback („Exception in ASGI application“, stderr) —
der Ausnahmetext kann Inhalte tragen.

## Setup und Start

Voraussetzungen: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Docker (für die Test-Datenbank), `psql`.

```bash
uv sync                                                            # .venv anlegen
docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:17
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q -W error
```

Dienst starten (Pflicht: `BC1_DB_DSN` als `bc1_role`, `BC1_COMPANY_ID`, `BC1_ANFRAGE_ID` — seit B5 die BC0-Anfrage, zu der interviewt wird, Form `A-JJJJ-NN`; seit B4 der BC0-Zugang (`BC1_BC0_URL`, `BC1_BC0_KONTO_EMAIL`, `BC1_BC0_KONTO_PASSWORT`) — lokal ohne echtes BC0 bewusst `BC1_BC0_MELDUNGEN=aus`; LLM-Wahl über `BC1_LLM` = `claude` | `ollama` | `gemini`, Key des Anbieters aus der Umgebung):

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
docker run --rm -p 8000:8000 \
  -e BC1_DB_DSN="postgresql://…" -e BC1_COMPANY_ID="<uuid des Mandanten>" \
  -e BC1_ANFRAGE_ID="A-2026-03" -e BC1_LLM=claude -e ANTHROPIC_API_KEY \
  -e BC1_BC0_MELDUNGEN=aus \
  bc1
```

`BC1_BC0_MELDUNGEN=aus` nur für einen lokalen Versuch ohne BC0 — im Betrieb stattdessen die drei BC0-Variablen wie oben. Ein Snapshot wird gemountet, nie ins Image kopiert (`-v /pfad/snapshot.json:/daten/snapshot.json:ro -e BC1_SNAPSHOT_PFAD=/daten/snapshot.json`). Eine Datenbank auf dem eigenen Rechner erreicht der Container unter `host.docker.internal` statt `localhost`.

**Was der Dienst bei BC0 tut (seit B4):** Beim Start prüft er immer den Zugang (Anmeldung + eigenes Konto, ändert nichts) und bricht bei einem Mangel ab — auch bei einer Anfrage, die schon auf `im_interview` steht. Danach zieht er das Gate für die eigene Anfrage nach, noch bevor er aus der Datenbank liest (holt einen früher gescheiterten Gate-Aufruf nach; steht die Anfrage danach schon auf `am_gate`, endet der Start mit „steht auf 'am_gate'“). Dann meldet er der Anfrage `im_interview` — nur aus `zugeordnet`, ein Neustart überschreibt BC0s Stand also nicht. Nach jedem Abschluss eines Interviews zieht er das Gate bei BC0 nach, im Hintergrund; die Chat-Antwort hängt nicht davon ab. Alle Gate-Aufrufe tragen `?anfrage_id=` — BC0 prüft seit v3.13 nur diese Anfrage. Scheitert das, steht eine WARNING mit Handlungsanweisung im Log (die Anfrage bei BC0 von Hand nachziehen) — das Profil ist dann trotzdem gespeichert. Alles läuft über ein BC0-Anwendungskonto mit Schreibrecht (Rolle `benutzer` oder `admin`), das den Mandanten sieht (zugewiesen; `admin` sieht alle); das Passwort steht nur in der Umgebung, in keiner Meldung und in keinem Log. Ob das Konto bereit ist, zeigt die Live-Probe — sie ändert bei BC0 nichts (Anmeldung, dann nur Lesen des eigenen Kontos) und braucht `BC1_COMPANY_ID` und die drei BC0-Variablen, keine Datenbank:

```bash
uv run python -m bc1_service.bc0_meldungen --probe
```

Ausgabe: Rolle, Schreibrecht ja/nein, Mandant sichtbar ja/nein. Exit 0 = bereit; 1 = nicht bereit, oder Anmeldung bzw. Aufruf bei BC0 scheitern (die Meldung sagt warum); 2 = Konfiguration fehlt oder ungültig, oder `BC1_BC0_MELDUNGEN=aus` (dann gibt es nichts zu prüfen).

Der Dienst startet nur, wenn der Mandant bewertete Teilprozesse hat und die Anfrage interviewbar ist (Stand `zugeordnet`/`im_interview`, alle ihre Teilprozesse bewertet) — die regulären Startabbrüche (seit B4 auch die der BC0-Meldungen) und der Chat-Aufbau stehen in [`bc1_service/n8n/SMOKE.md`](bc1_service/n8n/SMOKE.md). Die Datenbanktabellen kommen aus [`bc1_service/db/prozessprofil.sql`](bc1_service/db/prozessprofil.sql); wie man sie einspielt und was die Dreifallregel bedeutet, steht in [`bc1_service/db/EINSPIELEN.md`](bc1_service/db/EINSPIELEN.md). Was das Interview fragt und in welche Spalte es fließt: [`design/Spalte-zu-Feld-Tabelle.md`](design/Spalte-zu-Feld-Tabelle.md). Was noch fehlt: [`design/Abschlussplan-BC1.md`](design/Abschlussplan-BC1.md).
