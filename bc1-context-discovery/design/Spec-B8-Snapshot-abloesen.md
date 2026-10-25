# Spec B8 — Snapshot-Modus ablösen, `GET /prozesse` streichen

> Stand 24.10.2026, Entwurf 2, abgenommen 24.10.2026 (einschließlich 9.2–9.10).
> - **Bau:** gebaut am 24.10.2026, auf `main` seit 25.10.2026 (#342, Squash-Merge des Zweigs `bc1-b8-snapshot-abloesen`). **Messung n8n ↔ Dienst bei Bindung an 127.0.0.1: bestanden am 24.10.2026 (colima)**, Ergebnis in Abschnitt 5.
> - **Auftrag:** Go der BC1-Projektleitung am 24.10. für B8 („Snapshot-Modus ablösen und GET /prozesse absichern. Erst Plan, dann bauen").
> - **Entscheidung der BC1-Projektleitung (24.10.):** Der Endpunkt wird gestrichen statt abgesichert, wenn ihn wirklich niemand braucht, auch kein anderer BC. Die Prüfung dazu steht in Abschnitt 7; ihr Ergebnis: Niemand ruft ihn auf.
> - **Geprüft:** Builder-Check und Zweitmeinung Codex (beide 24.10.). Alle Befunde sind eingearbeitet oder begründet zurückgestellt (Abschnitt 10).
> - **Quellen:** Abschlussplan B8 und B3 (d); Kleinpunkt „Snapshot-Modus filtert `aktiv` nicht" (Codex A7); Spec B4 Abschnitt „Nicht in B4"; P2-Plan, Roadmap-Anker „`/prozesse`-Auth"; Issue #265; Messung (4a) vom 24.10.
> - **Nächster Schritt nach Abnahme:** Implementierungsplan.

## Big Picture

**Worum es geht.** Die Frage nach dem Kernprozess (B4) bekommt ihre Auswahlliste heute aus einer Datei: dem BC0-Snapshot vom Sommer, einer eingefrorenen Kopie. Was BC0 danach ändert, etwa ein neuer Kernprozess, fehlt darin. Die Datei ist optional, und im Betrieb ist sie nicht gesetzt. Deshalb ist B4 dort ein Freitextfeld. Zusätzlich gibt der Dienst die Liste über den Endpunkt `GET /prozesse` an jeden aus, der ihn erreicht, ohne Prüfung.

**Was sich ändert (Klartext).**

1. **Die Auswahl kommt aus der Datenbank.** Beim Start liest der Dienst die aktiven Kernprozesse des Mandanten aus BC0s Sicht `v_prozesse_lesen`, so wie er schon Teilprozesse, Systeme und Rollen liest. B4 ist damit eine Auswahl aus dem Stand **beim Start**. Ändert BC0 während eines laufenden Dienstes etwas, wirkt es erst nach dem nächsten Neustart, wie bei allen anderen Startdaten.
2. **Die Datei verschwindet.** Die Variable `BC1_SNAPSHOT_PFAD`, das Lesemodul und das Snapshot-Schema entfallen.
3. **`GET /prozesse` wird gestrichen.** Niemand ruft ihn auf: Der n8n-Chat nutzt nur `/turn`, und in keinem anderen BC findet sich ein Aufruf (Abschnitt 7, von Codex unabhängig bestätigt). Ein Endpunkt ohne Nutzer muss nicht abgesichert werden, sondern kann weg.
4. **Das Testprofil-Werkzeug folgt denselben Regeln.** Es baut sein Paket aus demselben Startkontext wie der Dienst. Bei gleichem Datenstand haben Dienst und Werkzeug dasselbe Paket.
5. **Der Docker-Start lauscht nur noch auf dem eigenen Rechner.** Das README startet den Container heute mit `-p 8000:8000`. Docker veröffentlicht den Port damit auf allen Adressen des Rechners, und der Dienst kann je nach Docker-Umgebung aus dem lokalen Netz erreichbar sein. Neu: `-p 127.0.0.1:8000:8000`. Dass n8n im Container den Dienst so weiter erreicht, ist am 24.10. gemessen (Abschnitt 5).

**Was B8 nicht löst — ehrlich gesagt.** Der Dienst hat **überhaupt keine Zugangsprüfung**. Offen sind alle Endpunkte (`/turn`, `/gesundheit`, `/docs`, `/redoc`, `/openapi.json`) und der n8n-Chat: Sein Chat-Trigger ist öffentlich, ohne Anmeldung, und reicht jede Nachricht an `/turn` weiter. Eine Sitzung ist an Mandant und Anfrage gebunden, aber wer aufruft, prüft niemand. Geschützt ist der Dienst nur dadurch, dass niemand anderes ihn erreicht. Das gilt nur, wenn er richtig gestartet wird: uvicorn direkt (lauscht standardmäßig nur auf dem eigenen Rechner) oder der Container mit der Bindung aus Punkt 5. B8 macht das zur ausdrücklichen Betriebsvoraussetzung im README. Die eigentliche Zugangsprüfung kommt mit Ziel in den Abschlussplan: vor dem ersten Betrieb auf einem Rechner, den andere erreichen (Abschnitt 6).

**Wer etwas davon merkt.**
- **Befragte Personen:** B4 nennt die Kernprozesse mit ID und Namen. Passt eine Antwort auf keinen davon, fragt das Interview nach. Passt sie zweimal nicht, gibt es das Feld auf; B4 ist bewusst nicht identitätskritisch. Das war mit Datei schon so.
- **BC0:** Der Befund `kp_tp_diskrepanz` (die befragte Person ordnet den Schritt einem anderen Kernprozess zu als BC0) entsteht jetzt verlässlich. Bisher entstand er im Betrieb nur, wenn die Freitext-Antwort genau eine Prozess-ID wie `KP-05` war; „KP-05 Logistik" zählte nicht. BC0 nennt BC1 außerdem noch als Leser des Snapshots (`export_snapshot.py`, ADR-003). BC1 teilt BC0 mit, dass es den Snapshot nicht mehr liest (Abschnitt 6).
- **BC2:** Die **Vertragsstruktur bleibt unverändert**. Die Spalte `process_id` stammt weiter aus dem Teilprozess. Der im Vertrag beschriebene B4-Abgleich (`kp_tp_diskrepanz`) bleibt und bekommt häufiger kanonische IDs. Neu möglich ist, dass `process_id` nach zwei unpassenden Antworten in `ungeloeste_felder` steht und `vollstaendigkeit` dadurch sinkt. Der Vertrag sieht das für jedes nicht identitätskritische Pflichtfeld schon vor; mit Freitext kam es bei B4 nur praktisch nicht vor. BC2 erfährt es im nächsten Stand in #286.
- **Andere BCs:** sonst nichts (Abschnitt 7).

**Vorbedingung der Auslieferung.** Die Paketkennung (`1.2+ctx-…`) ändert sich, weil die Kernprozess-Liste in ihren Fingerabdruck eingeht. Eine offene Sitzung ließe sich danach nicht fortsetzen. Deshalb gilt:
- **Unmittelbar vor dem Neustart** wird immer neu gemessen (`messung-4a-c1a.sql`, Blöcke M1 bis M3; das Skript liegt nur lokal, weil es die Mandantenkennung enthält). Die drei Kriterien:
  - **M1:** keine Sitzung im Status `aktiv`, `wartet_auf_antwort` oder `fehler_fortsetzbar` (`fertig` und `abgebrochen_ohne_identitaet` sind in Ordnung, wenn M3 leer ist);
  - **M2:** kein Draft `in_erhebung`;
  - **M3:** kein ausstehender Abschluss.
- Zwischen Messung und Neustart läuft weder der alte Dienst noch das Testprofil-Werkzeug. Ein laufender Dienst prüft den Anfragestatus nur beim Start und nimmt danach weiter neue Sitzungen an.
- Gibt es Offenes, wird es mit dem alten Stand abgeschlossen oder nach K5 verworfen, dann erneut gemessen.
- Dasselbe gilt für einen Rückfall auf den alten Stand.

**Bewusst nicht in B8:**
- **Zugangsprüfung des Dienstes** (alle Endpunkte: `/turn`, `/gesundheit`, `/docs`, `/redoc`, `/openapi.json`) **und des n8n-Chats** → Abschlussplan, Ziel B3 Teil 2 (Abschnitt 6).
- **B4 mit Vorschlag aus BC0** (wie bei B3 „Laut BC0 ist das …") oder B4 ganz aus dem Teilprozess ableiten → neue Funktion bzw. Feldänderung, nicht Teil des Ersatzes.
- **Die Warnzeile `kp_tp_diskrepanz` wiederholt sich je Turn**, weil der Writer bei jedem Abgleich schreibt. Mit B8 kommt das öfter vor. Dasselbe Muster beim Eigner ist schon zurückgestellt (Abschlussplan „Neu 24.10." (4e)); beide bekommen dasselbe Ziel: B7 Teil 2.
- **Paketfassung erhöhen:** bleibt 1.2. B4 war unter 1.2 schon eine Auswahl, wenn eine Datei gesetzt war. Der Fingerabdruck unterscheidet die Stände (Entscheidung 9.4).

## Technischer Teil

### 1. Lesepfad und Startkontext (`bc0_lesepfade.py`, `discovery_paket.py`, `start.py`)

- **Neu:** `bc0_lesepfade.kernprozesse(conn, company_id) -> list[tuple[str, str]]`:
  ```sql
  SELECT process_id, process_name FROM v_prozesse_lesen
   WHERE company_id = %s ORDER BY process_id
  ```
  Der Mandantenfilter ist Pflicht; die Sicht filtert `aktiv` selbst (wie in `_AKTIVER_KERNPROZESS` schon genutzt). `bc1_role` hat das Leserecht (Messung 24.10., M4; im Gerüst über `bc_leser`).
- **`Bc0Kontext`** bekommt am Ende das Feld `prozesse: tuple[tuple[str, str], ...] = ()`. `lade_kontext` füllt es. „Aktiv" heißt: aktiv beim Laden des Kontexts.
- **Kein eigener Abbruch für eine leere Liste.** Im echten Start kann sie nicht leer sein: Der Start verlangt interviewbare Teilprozesse mit aktivem Kernprozess und bricht sonst schon vorher ab (`MELDUNG_KEINE_TEILPROZESSE`). Ein zusätzlicher Abbruch wäre nicht testbar. Die Startabfragen laufen nacheinander und nicht in einer gemeinsamen Lesesicht. Kernprozesse sind bei BC0 seit dem 23.09. nicht mehr stilllegbar; den verbleibenden theoretischen Wettlauf nimmt B8 hin (9.9).
- **Warum im Kontext und nicht in `main.py`:** Dienst und Testprofil-Werkzeug bauen ihr Paket beide aus `lade_kontext`. Läge die Liste nur in `main.py`, hätten sie verschiedene Pakete (B4 Freitext gegen Auswahl, andere Kennung).

### 2. Paket (`discovery_paket.py`, `paket_wahl.py`)

- Im Kontext-Zweig kommen B4-Typ, Fragetext und Fingerabdruck aus **derselben** Liste `kontext.prozesse`. Typ und Frage sind wie bisher mit Datei: `AUSWAHL` der IDs, Frage mit „ID = Name". Die IDs gehen in den Kontext-Fingerabdruck ein, die Namen nicht. Die übrigen Bestandteile des Fingerabdrucks und seine kanonische JSON-Form bleiben gleich.
- **Kennungen bleiben vergleichbar:** Bei leerer Liste (Tests mit Minimalkontext) bleibt die bisherige Kennung erhalten, und B4 bleibt dort Freitext. Bei gleichen KP-IDs und sonst gleichem Kontext ist die Kennung dieselbe wie bisher mit Datei.
- **Der Parameter `prozesse` entfällt** in `baue_discovery_paket` und `waehle_paket`. Mit ihm entfällt die kontextfreie Variante `1.0+kp-…`: Sie war nur mit Datei und ohne Kontext erreichbar, und ohne Kontext startet der Dienst seit B5 nicht. Der kontextfreie Zweig bleibt bei 1.0 mit B4 als Freitext.
- **Tests dieser Variante werden nicht einfach verschoben, sondern für den Kontext-Zweig neu belegt:**
  - Fingerabdruck über IDs;
  - 16 Hex-Zeichen, direkt geprüft (die alten Kollisionsbeispiele gelten für eine andere Eingabeform und beweisen hier nichts);
  - Umbenennung und Reihenfolge ändern die Kennung nicht;
  - Paket-Guard nach Abschnitt 3.

### 3. Paket-Guard: drei Wege, getrennt belegt

Eine geänderte Kernprozess-Liste wirkt je nach Lage verschieden. Der Plan testet jeden Weg einzeln:

1. **Offene Sitzung, Turn ohne Versionsangabe:** `paket_konflikt` (Paket-Guard im Kern).
2. **Turn mit abweichender Versionsangabe:** `schema_version_passt_nicht` (schon in `api.py`).
3. **Wiederholung eines letzten Turns** (bekannte Nachrichten-ID, Sitzung `fertig`, gleicher Paketname und gleiche Basisfassung): Sie darf einen geänderten Fingerabdruck passieren (Recovery, `core.py`). Gespeicherte Feldstatus werden dabei nicht neu gegen die neue Liste geprüft. Deshalb bleibt „kein ausstehender Abschluss" Vorbedingung der Auslieferung.

Mandanten- und Anfrage-Prüfung bleiben unverändert streng.

### 4. Dienst (`main.py`, `api.py`)

- `main.py` liest `BC1_SNAPSHOT_PFAD` nicht mehr. Ist die Variable noch gesetzt, passiert nichts (9.7). API und Writer bekommen weiter dasselbe Paketobjekt.
- `create_app` verliert den Parameter `snapshot` und die Route `GET /prozesse`. Ein Aufruf bekommt FastAPIs Standard-404; die Route fehlt auch in der OpenAPI-Beschreibung. Aufrufer übergeben `lifespan` danach per Name.
- **P3-Zusage bleibt:** Unbekannte Fehlerschlüssel gehen unverändert und ohne `chat_text` durch. Der Test dafür nutzte `kein_snapshot_konfiguriert`, den einzigen Schlüssel ohne Text. Er bekommt eine Test-Route, die eine `HTTPException` mit unbekanntem Schlüssel wirft; eine bloß unbekannte URL prüft den eigenen Handler nicht.

### 5. Betrieb und Abhängigkeiten

- **Entfällt:** `bc1_service/snapshot.py`, `bc1_service/snapshot_schema.json`, `tests/test_snapshot.py`.
- **`jsonschema`** wird in BC1 nur von `snapshot.py` genutzt. Es wandert aus den Laufzeit-Abhängigkeiten in die `dev`-Gruppe: `pyproject.toml` **und** `uv.lock` gemeinsam, ohne andere Pakete anzuheben. Das Image installiert aus `uv.lock` (`--frozen`), eine Änderung nur an `pyproject.toml` reicht also nicht. Abnahme in zwei Teilen:
  1. **Entwicklerumgebung:** `jsonschema` ist da, BC2s `tools/validate.py` läuft mit dem BC1-venv, und `pytest -v` zeigt weiter das Plugin `tdd-guard-pytest`.
  2. **Dienst:** `uv export --frozen --no-dev --group service` enthält kein `jsonschema`.

  In CI installiert der Vertrags-Workflow `jsonschema` selbst; er läuft bei BC1-Änderungen nicht zwingend und ist deshalb kein Nachweis.
- **`.dockerignore`:** Die Ausnahme `!bc1_service/snapshot_schema.json` entfällt. Die Regel `**/*snapshot*.json` bleibt als Schutz, denn BC0-Snapshots mit Mandantendaten können lokal herumliegen. Sie greift nur über den Dateinamen; der eigentliche Schutz bleibt, dass das Dockerfile nur `bc1_core/` und `bc1_service/` kopiert.
- **Netz (README):**
  - Der Container startet mit `-p 127.0.0.1:8000:8000`. Ebenso der Test-Postgres im README (`-p 127.0.0.1:55432:5432`), denn derselbe Fehler steht dort mit dem Passwort `test`.
  - Im Container lauscht uvicorn weiter auf `0.0.0.0`, sonst funktioniert die Portweiterleitung nicht.
  - **Messergebnis (24.10.2026, macOS, Docker Engine in colima; in Containern löst `host.docker.internal` auf das Host-Gateway von lima auf):**
    1. Das BC1-Image wurde gebaut und mit `-p 127.0.0.1:8000:8000` gegen die Test-DB gestartet; Docker meldet die Bindung `127.0.0.1:8000`.
    2. Vom eigenen Rechner antwortet `/gesundheit` mit `200 ok`.
    3. Aus dem n8n-Image (ohne `--add-host`, wie in SMOKE) antwortet `http://host.docker.internal:8000/gesundheit` mit `ok`.
    4. `/prozesse` liefert `404 Not Found`.
    5. Ein Wegwerf-Postgres mit `-p 127.0.0.1:55499:5432` ist aus einem Container über `host.docker.internal:55499` erreichbar.
    6. **Nicht gemessen:** dass der Dienst aus dem lokalen Netz jetzt unerreichbar ist (Gegenprobe nicht freigegeben); die README-Aussage stützt sich auf Dockers dokumentiertes Verhalten.
    7. **Nicht gemessen:** Linux mit Docker Engine. Dort gibt es `host.docker.internal` nur mit `--add-host=host.docker.internal:host-gateway`, es zeigt auf die Bridge-Adresse, und ein an `127.0.0.1` veröffentlichter Port ist von dort vermutlich nicht erreichbar.
  - Ist das nicht der Fall (Punkt 7: Linux), wird der Weg über ein gemeinsames Docker-Netz ohne veröffentlichten Port beschrieben. Die Wahl kommt dann vor die BC1-Projektleitung.

### 6. Doku, Roadmap, Meldungen

- **README:** Variable und Absatz zum Snapshot entfernen; Netz wie in Abschnitt 5; ein Satz zur Betriebsvoraussetzung „nur auf dem eigenen Rechner oder im internen Docker-Netz erreichbar, bis es eine Zugangsprüfung gibt". **`main.py`-Kopf** und **Dockerfile**-Kommentar ebenso.
- **SMOKE.md:** Die ausführbare Demo-Verdrahtung (`demo_fake.py`, Import von `lade_snapshot`, `create_app(…, snapshot)`) und die Anleitungsschritte (Snapshot setzen, `curl /prozesse`) werden auf den neuen Stand gebracht. Protokolle vergangener Läufe bleiben als Geschichte stehen.
- **Kommentare** in `profil_writer.py` und `tests/test_profil_bau.py`, die sagen „ohne Snapshot ist B4 Freitext", werden auf den neuen Stand gebracht. Alte Implementierungspläne bleiben als historische Stände unverändert.
- **Abschlussplan:**
  - B8 erledigt; B3 (d) erledigt durch Streichen; Kleinpunkt „Snapshot filtert `aktiv` nicht" erledigt (seit 23.09. ohnehin gegenstandslos).
  - **Neuer Roadmap-Punkt unter B3 Teil 2:** „Zugangsprüfung des Dienstes — alle Endpunkte (`/turn`, `/gesundheit`, `/docs`, `/redoc`, `/openapi.json`) und der n8n-Chat (Chat-Trigger öffentlich, ohne Anmeldung) sind offen, geschützt nur über das Netz (README- und SMOKE-Bindung an 127.0.0.1 seit B8). Ziel: vor dem ersten Betrieb auf einem Rechner, den andere erreichen, zusammen mit dem n8n-Chat auf fester Adresse."
  - (4e) wird um `kp_tp_diskrepanz` ergänzt.
- **Meldungen** werden lokal entworfen und erst nach OK der BC1-Projektleitung gepostet:
  - **#265:** Haken „`/prozesse` nur mit Zugangsprüfung" mit Verweis auf B8 als entfallen.
  - **BC0 (#206):** BC1 liest den Snapshot nicht mehr. Der Hinweis in ADR-003 auf `bc1_service/snapshot_schema.json` ist damit gegenstandslos; ob BC0 ihn anpasst, entscheidet BC0.
  - **BC2 (#286):** ein Satz zu `ungeloeste_felder` (Big Picture).
- **Unverändert:** Vertrag `contracts/bc1-to-bc2/`, DDL und Signaturen, Gerüst-Rechte (`v_prozesse_lesen` ist im Gerüst da).

### 7. Prüfung „braucht jemand `GET /prozesse`?" (24.10.2026)

| Wo gesucht | Ergebnis |
|---|---|
| n8n-Chat von BC1 (`bc1-chat-workflow.json`) | einzige URL: `…:8000/turn` |
| `origin/main`, alle Verzeichnisse außer BC1, nach `/prozesse` | ein Treffer: eine YAML-Fehlermeldung in BC0 (`company:/profile:/prozesse:`), kein Aufruf |
| alle 87 Remote-Zweige, außer BC1, nach `/prozesse` | nur dieselbe YAML-Meldung in BC0-Ständen |
| `origin/main` nach Aufrufen des BC1-Dienstes (URL, Port, Variablen) | nur BC0- und BC2-eigene Proxys auf ihren eigenen Port 8000, BC4 auf Ollama/Qdrant |
| n8n-Workflows von BC3 und BC4 | keine Anfrage an BC1 |
| Doku anderer BCs zu „Endpunkt/API" und BC1 | nur BC0s Endpunkte **für** BC1 (die Richtung BC1 → BC0) |
| GitHub-Issues und PRs (`"GET /prozesse"`, `kein_snapshot_konfiguriert`, `BC1_SNAPSHOT_PFAD`) | nur BC1-eigene: #130, #265, #268, #269, #328 |
| Codex, unabhängig (Arbeitsbaum, `origin/main`, 87 Zweige) | kein Aufruf; keine fremden Aufrufer von `baue_discovery_paket`, `waehle_paket`, `bc1_service.snapshot` oder der Variable |

Grenze: Eine Repo-Suche beweist nicht, dass es keinen unversionierten Aufrufer gibt. Bekannt ist keiner.

### 8. Testmatrix (Vorgabe für den Plan)

| Bereich | Was belegt wird |
|---|---|
| Lesepfad (DB) | zwei Mandanten mit gleichen IDs und anderen Namen; aktiv/stillgelegt; Sortierung; Zugriff als `bc1_role` |
| Auswahlumfang | B4 erlaubt aktive Kernprozesse außerhalb der Anfrage, auch solche ohne bewertete Teilprozesse; E5 bleibt auf die interviewbaren Teilprozesse der Anfrage begrenzt |
| Start | der echte Startkontext enthält die Kernprozesse |
| Fingerabdruck | ID dazu oder weg ändert ihn; Umbenennung und Reihenfolge nicht; 16 Hex-Zeichen; die übrigen Bestandteile wirken weiter; leere Liste = bisherige Kennung |
| Paket-Guard | die drei Wege aus Abschnitt 3 |
| Werkzeug | Fixture mit Kernprozessen; gleiche Kennung und gleiche B4-Prüfung wie der Dienst bei gleichem Kontext |
| Befund | andere kanonische ID → Befund; gleiche ID, unpassende Antwort oder ungelöstes B4 → kein Befund; Spalte bleibt aus dem Teilprozess |
| API | `/prozesse` fehlt, auch in OpenAPI; eigener unbekannter Schlüssel ohne `chat_text` |
| Verdrahtung | keine Snapshot-Abhängigkeit mehr; alte Variable wirkungslos; API und Writer mit demselben Paket |
| Abhängigkeiten | die beiden Abnahmen aus Abschnitt 5 |

Mit anzupassen sind auch die Aufrufer in `tests/test_paket_wahl.py`, `tests/test_discovery_paket.py` (auch der Fall mit Liste **und** Kontext), das `create_app`-Double in `tests/test_api_profil.py` und `tests/test_demo_durchlaeufe.py`.

### 9. Entscheidungen

| # | Entscheidung | Wer |
|---|---|---|
| 9.1 | `GET /prozesse` streichen statt absichern (Prüfung in Abschnitt 7) | BC1-Projektleitung, 24.10. |
| 9.2 | Auswahl = **alle** aktiven Kernprozesse des Mandanten, nicht nur die der Anfrage. B4 ist eine Selbsteinschätzung der befragten Person. Mit der mandantenweiten Liste kann sie den Schritt auch einem Kernprozess **außerhalb** der Anfrage zuordnen, und genau das hält der Befund fest. E5 bleibt auf die Anfrage begrenzt. | Claude (Bauentscheidung) |
| 9.3 | Liste im `Bc0Kontext`, nicht in `main.py` (Abschnitt 1) | Claude |
| 9.4 | Paketfassung bleibt 1.2 (Big Picture, „Bewusst nicht") | Claude |
| 9.5 | Parameter `prozesse` und Variante `1.0+kp-…` entfallen; ihre Eigenschaften werden im Kontext-Zweig neu belegt | Claude |
| 9.6 | `jsonschema` in die `dev`-Gruppe statt ganz entfernen (lokale Vertragsprüfung) | Claude |
| 9.7 | Kein Warnhinweis, wenn `BC1_SNAPSHOT_PFAD` noch gesetzt ist | Claude |
| 9.8 | README bindet Dienst und Test-Postgres an `127.0.0.1`; Messung mit n8n im Bau | Claude |
| 9.9 | Kein eigener Abbruch für eine leere Kernprozess-Liste (Abschnitt 1) | Claude |
| 9.10 | Wiederholte Warnzeile → B7 Teil 2 wie (4e) | Claude |

### 10. Befunde der Prüfungen und ihr Verbleib

| Befund | Schwere | Verbleib |
|---|---|---|
| Codex I1: Docker veröffentlicht auf allen Adressen, „von außen nicht erreichbar" war unbelegt | Important | Big Picture Punkt 5 und „nicht lösen", Abschnitte 5 und 6 |
| Codex I2: Messung vom 24.10. sichert die Auslieferung nicht dauerhaft | Important | Vorbedingung: immer unmittelbar vor dem Neustart messen, Ruhe bis zum Wechsel |
| Codex I3: „aktuell und aktiv" gilt nur beim Laden | Important | Big Picture Punkt 1, Abschnitt 1, 9.9 |
| Codex I4: `uv.lock` fehlte, keine getrennte Abnahme | Important | Abschnitt 5 |
| Codex M1: weitere Aufrufer und Test-Doubles | Minor | Abschnitt 8 |
| Codex M2: Vertrag beschreibt den B4-Abgleich; BC0-ADR nennt das Schema | Minor | „Wer merkt" BC2/BC0, Abschnitt 6 |
| Codex M3: drei Guard-Wege, Recovery-Ausnahme | Minor | Abschnitt 3 |
| Codex M4 / Builder 5: Befund nur bei genauer ID, B4 kann ungelöst bleiben | Minor | „Wer merkt", Abschnitt 8 |
| Codex M5 / Builder: Begründung unterstellte einen Anfrage-Kernprozess | Minor | 9.2 neu begründet |
| Builder 1: Folge für `vollstaendigkeit`/`ungeloeste_felder` | wichtig | „Wer merkt" BC2, Meldung in #286 |
| Builder 2: Warnzeile je Turn | gering | 9.10, Abschlussplan (4e) |
| Builder 3: BC0 nennt BC1 als Snapshot-Leser | gering | Meldung an BC0 (Abschnitt 6) |
| Builder 4: „stillgelegte Prozesse in der Datei" überholt | gering | Big Picture neu begründet |
