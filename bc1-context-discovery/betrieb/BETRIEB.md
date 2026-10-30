# BC1 auf BC0s Server — Betriebsanleitung

> Stand 27.10.2026. Dateien in diesem Ordner: `compose-bc1.yml` (Compose-Eintrag),
> `env.bc1.vorlage` (Umgebung, ohne Werte), `vor-dem-start.sql` (Prüfung vor jedem Start).
> Zugangsschlüssel und Anfrage-Prüfung: [`../design/Plan-Zugang-und-Anfragepruefung.md`](../design/Plan-Zugang-und-Anfragepruefung.md).

## Teil 1 — Überblick

**Was läuft wo.** BC1 läuft als Container `bc1` im Docker Compose von BC0, ohne eigenen Port
nach außen. Die Person spricht nur mit BC0s Anfrage-App. BC0s Backend reicht jede Chat-Nachricht
an `http://bc1:8000/turn` weiter, mit dem Zugangsschlüssel im Header `X-BC1-Zugang` sowie Anfrage
und Mandant im Aufruf. BC1 liest und schreibt in der gemeinsamen Datenbank (Supabase, als
`bc1_role`), meldet BC0 über dessen öffentliche Adresse `im_interview` und zieht nach dem
Abschluss das Gate nach. Für die Gesprächsführung ruft es Gemini auf.

**Grenzen dieses Stands.**
- BC1 bedient **eine Anfrage zur Zeit** (`BC1_ANFRAGE_ID`). Eine andere Anfrage bekommt 409 `anfrage_passt_nicht`. „Anfrage je Gespräch“ folgt als eigener Schritt.
- **Jeder abgeschlossene Lauf verbraucht eine Anfrage samt Teilprozess.** Danach steht die Anfrage am Gate, und ein zweites Profil am selben Teilprozess ließe BC0s Freigabe veralten. Je Lauf also eine neue Testanfrage zu einem Teilprozess, den BC0 nennt und der noch kein BC1-Profil hat.
- **Nur Testdaten.** Für echte Personen fehlen noch die Datenschutz-Punkte: Hinweis in der App, Löschen, Aufbewahrungsfrist, Vertrag mit dem KI-Anbieter.

**Begrüßungstext** (zeigt BC0s Chat-Ansicht als erste Zeile; BC1 antwortet erst auf die erste Nachricht):

> Guten Tag! Ich stelle Ihnen einige Fragen zu dem Ablauf, um den es in Ihrer Anfrage geht.
> Am besten beantworten Sie sie in einem Zug. Bitte nennen Sie keine Namen, E-Mail-Adressen oder
> Telefonnummern von Personen. Wenn Sie bereit sind, schreiben Sie einfach eine erste Nachricht.

## Teil 2 — Technik

**Alle `docker compose`-Befehle für BC1 mit `--no-deps`.** Sonst startet Compose BC0s Container
mit oder erzeugt sie neu, wenn deren Konfiguration noch nicht ausgerollt ist. Die drei Zeilen bei
`app` rollt BC0 selbst aus (`docker compose up -d app`).

### 1. Einrichten (einmalig)

1. **Checkout auf festem Tag**, getrennt von BC0s Code, z. B. `git clone --branch <tag> https://github.com/pg-coe-kmu/coe-factory.git /opt/bc1/coe-factory`. Dann zieht BC0s übliches `docker compose up -d --build` nie ungeprüft einen neuen BC1-Stand mit.
2. **`.env.bc1`** aus `env.bc1.vorlage` anlegen und füllen. Die Datei liegt nur auf dem Server, Geheimnisse stehen in einfachen Anführungszeichen. In **BC0s `.env`** kommen `BC1_ZUGANG` und `BC1_COMPANY_ID`; beide Dienste lesen sie von dort. Den Schlüssel auf dem Server erzeugen: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. Er braucht mindestens 32 Zeichen, nur ASCII, ohne Leerzeichen; sonst bricht BC1 den Start ab.
3. **Erst dann den Compose-Eintrag** aus `compose-bc1.yml` übernehmen (Dienst `bc1`, bei `app` die drei Zeilen). Fehlen Checkout oder `.env.bc1`, scheitert sonst vermutlich das ganze `docker compose up`. Den absoluten Build-Pfad meldet Compose als nicht portabel; das ist hier gewollt.
4. **Zugang zu BC0 prüfen**, nur lesend: `docker compose run --rm --no-deps bc1 /app/.venv/bin/python -m bc1_service.bc0_meldungen --probe` (Exit 0 = bereit). Die Probe braucht `BC1_COMPANY_ID` und die drei BC0-Variablen, keine Datenbank.
5. **Vor dem Start messen** (Abschnitt 3), dann `docker compose up -d --no-deps bc1` und im Log auf die Zeile `dienst gestartet paket=… schema_version=… mandant=…` warten.

### 2. Ablauf je Testlauf

1. **Anfrage anlegen** — in BC0s Oberfläche mit dem BC1-Dienstkonto oder über die Schnittstelle (unten). Im Originaltext steht „Testanfrage“; Kernprozess und Teilprozess sind die, die BC0 genannt hat.
2. **Mit OK von BC0 auf `zugeordnet` setzen** — dafür gibt es in BC0s Oberfläche keinen Knopf, nur die Schnittstelle (unten).
3. **Abschluss der vorigen Anfrage prüfen:** Meldet die Messung (Abschnitt 3) M3-Zeilen, diese **jetzt** nachholen (`SMOKE.md`, „Betrieb: wenn das Schreiben des Profils klemmt“). Der Turn von Hand braucht noch die alte Anfrage, nach dem Wechsel käme 409.
4. **`BC1_ANFRAGE_ID`** in `.env.bc1` auf die neue Nummer setzen.
5. **Messen** (Abschnitt 3), mit der neuen Anfrage.
6. **Neu starten:** `docker compose up -d --no-deps bc1`, im Log die Zeile `dienst gestartet` prüfen.
7. **Gespräch** in BC0s App unter „Meine Anfragen“.
8. **Gate 0** bei BC0; danach geht das Paket an BC2.

**Werte in die Shell holen** (für die Schnittstelle und die Messung). Die Werte stehen in `.env.bc1` bzw. in der eigenen Zugangsdatei. `.env.bc1` ist im Compose-Format und lässt sich nicht verlässlich per `source` laden. Deshalb von Hand eingeben, ohne Echo:

```bash
read -r  BC1_BC0_KONTO_EMAIL;    export BC1_BC0_KONTO_EMAIL
read -rs BC1_BC0_KONTO_PASSWORT; export BC1_BC0_KONTO_PASSWORT
read -rs BC1_DB_DSN;             export BC1_DB_DSN          # Session-Pooler, als bc1_role
# danach: unset BC1_BC0_KONTO_EMAIL BC1_BC0_KONTO_PASSWORT BC1_DB_DSN
```

Ein leerer Wert führt bei BC0 zu 401, und jeder Fehlversuch zählt bei BC0s Anmeldebremse.

**Schnittstelle von BC0** (Feldnamen aus BC0s `app.py`; so noch nicht live erprobt). Das Passwort geht über `printf` (Shell-Befehl, erscheint nicht in der Prozessliste) an `curl`. Enthält es ein `"` oder `\`, stattdessen die Oberfläche nehmen:

```bash
B=https://bc0.perspektivwechsel.ai; C=<mandant-uuid>; J=$(mktemp)
printf '{"email":"%s","passwort":"%s"}' "$BC1_BC0_KONTO_EMAIL" "$BC1_BC0_KONTO_PASSWORT" \
  | curl -sS -c "$J" -H 'Content-Type: application/json' --data @- "$B/api/auth/login" -o /dev/null -w '%{http_code}\n'
# anlegen (Antwort nennt die neue anfrage_id, Status eingegangen)
curl -sS -b "$J" -H 'Content-Type: application/json' \
  -d '{"originaltext":"Testanfrage für einen BC1-Durchlauf, kein echtes Anliegen.","process_id":"KP-NN","sub_process_id":"KP-NN.TP-N"}' \
  "$B/api/companies/$C/anfragen"
# zuordnen (nach OK von BC0)
curl -sS -b "$J" -X PUT -H 'Content-Type: application/json' -d '{"status":"zugeordnet"}' \
  "$B/api/companies/$C/anfragen/A-JJJJ-NN/status"
rm -f "$J"
```

### 3. Vor jedem Start messen

Vom eigenen Rechner im Ordner `bc1-context-discovery/` (mit `psql`; der Container hat keins):

```bash
psql "$BC1_DB_DSN" -v mandant=<uuid> -v anfrage=A-JJJJ-NN -f betrieb/vor-dem-start.sql
```

Nur lesend, als `bc1_role`. Erwartet:
- M0: `bc1_role`.
- M1: keine Sitzung `aktiv`, `wartet_auf_antwort` oder `fehler_fortsetzbar`.
- M2: kein Entwurf `in_erhebung`.
- M3: kein ausstehender Abschluss.
- M4: kein fehlendes Leserecht.
- M5: die Anfrage steht auf `zugeordnet` (beim Update einer laufenden Anfrage auch `im_interview`) und hat mindestens einen Teilprozess.
- M6: kein BC1-Profil an ihren Teilprozessen.

Was bei Treffern zu tun ist:
- **M1** lockert die frühere Regel „keine Sitzung“ bewusst. Erst klären, ob noch jemand mitten im Gespräch ist, und das Gespräch abschließen lassen. Eine offene Sitzung einer früheren Anfrage lässt sich nach dem Wechsel nicht mehr fortsetzen (409); das kann man bewusst hinnehmen.
- **M2:** Ein offener Entwurf blockiert seinen Teilprozess. Nach [`../bc1_service/n8n/SMOKE.md`](../bc1_service/n8n/SMOKE.md), Abschnitt „K5“, verwerfen.
- **M3:** vor dem Wechsel nachholen (Abschnitt 2, Schritt 3).
- **M6:** anderen Teilprozess bei BC0 erfragen.

### 4. Update und Neustart

- **Neuer Stand:** im Checkout den Tag wechseln (`git fetch --tags && git checkout <tag>`), messen (Abschnitt 3), `docker compose up -d --no-deps --build bc1`. Jedes Update stimmen BC0 und BC1 vorher kurz ab. `GET /gesundheit` (mit Header) nennt `paket` und `schema_version`.
- **Nach einem Neustart des Servers** startet `bc1` nicht von selbst (`restart: "on-failure:3"`, siehe Kommentar in `compose-bc1.yml`). Einmal `docker compose up -d --no-deps bc1` ausführen und den Start im Log prüfen. Dasselbe gilt, wenn der ganze Stack hochfährt, bevor Caddy bereit ist: Die drei Wiederholungen folgen zu schnell aufeinander, um das abzufangen.

### 5. Log lesen

`docker compose logs bc1 --since 1h`. Nachrichtentexte, Werte und Profildaten stehen nie im Log. Die wichtigsten Zeilen:

| Zeile | Bedeutung |
|---|---|
| `bc1.dienst dienst gestartet paket=… mandant=…` | Start erfolgreich |
| `bc1.dienst turn … http=200 status=frage` | normaler Turn |
| `bc1.dienst turn … http=409 status=anfrage_passt_nicht` | BC0 hat eine andere Anfrage oder einen anderen Mandanten geschickt |
| `bc1.api zugang_verweigert pfad=… grund=fehlt\|falsch` | Header fehlt oder falscher Schlüssel (Konfiguration bei BC0 prüfen) |
| `bc1.kern ki_aufruf … ergebnis=fehler` | KI nicht erreichbar oder Guthaben leer; die Person bekommt `fehler_fortsetzbar` |
| `RuntimeError: …` oder `Bc0MeldungFehler: …` beim Start | regulärer Startabbruch; der Satz sagt, was fehlt (Tabellen in `SMOKE.md`, „Aufbau“) |

Alle Zeilen erklärt die README, Abschnitt „Betriebsprotokoll“.

### 6. Häufige Fehlerbilder

| Symptom | Ursache | Tun |
|---|---|---|
| BC0 bekommt keine Verbindung zu `bc1` | Container läuft nicht, z. B. nach einem Startabbruch | `docker compose ps bc1`, Log lesen, Ursache beheben, `up -d --no-deps bc1` |
| Start bricht ab mit „steht auf 'am_gate'“ | Die eingestellte Anfrage ist schon fertig interviewt | neuen Testlauf vorbereiten (Abschnitt 2) |
| Start bricht ab mit „BC1_ZUGANG …“ | Schlüssel fehlt, ist zu kurz oder enthält fremde Zeichen | BC0s `.env` prüfen |
| Start bricht ab mit „BC0 unter … ist nicht erreichbar“ | Caddy oder BC0 war beim Start noch nicht bereit | `docker compose up -d --no-deps bc1` |
| jede Anfrage 401 | BC0 schickt den Header nicht oder einen anderen Wert | Liest `app` `BC1_ZUGANG` aus derselben `.env`? |
| 409 `anfrage_passt_nicht` | Die App bietet eine Anfrage an, die BC1 gerade nicht bedient | erwartet bei anderen Anfragen; sonst `BC1_ANFRAGE_ID` prüfen |
| `fehler_fortsetzbar` im Chat | KI-Aufruf gescheitert | Guthaben im KI-Konto und Log `ki_aufruf` prüfen; die Person sendet dieselbe Nachricht erneut |

### 7. Rückfall: Vorführung vom eigenen Rechner

Läuft der Einbau nicht, zeigt man dieselbe Fachstrecke lokal: Dienst gegen Supabase mit der vorbereiteten Anfrage, Chat über n8n auf `localhost` (README und `SMOKE.md`). **Vorher `bc1` auf dem Server stoppen** (`docker compose stop bc1`): Zwei Dienste auf derselben Datenbank sind nicht vorgesehen.

### 8. Prüfwerkzeug vor Generalprobe und vor jedem Update, das Dialog oder Extraktion berührt

Fester Schritt, vom eigenen Rechner im Ordner `bc1-context-discovery/` (nicht auf dem Server, nicht im Image):

```bash
BC1_LLM=gemini GEMINI_API_KEY=… .venv/bin/python -m werkzeuge.pruefe_antworten --szenario <1|2|3|4> [--lauf K] --ausgabe <Datei außerhalb des Repos>
```

- **Schlüssel** nur aus der Umgebung der Sitzung, nie in Repo, Chat oder Log. **Berichte** nie ins Repo (die Ausgabedatei liegt außerhalb).
- **Abnahme:** Spec `design/Spec-Antwortformen.md`, „Erfolg 2“ (Szenarien 1, 3, 4 je zwei Läufe, Szenario 2 mindestens drei Läufe; kein falscher Wert, kein aufgegebenes Pflichtfeld).
- **Nach dem Update dieses Pakets ändert sich die Kontext-Kennung** (`+ctx-…` in `schema_version`), weil die Namen im Fingerabdruck stehen. Vorher messen (Abschnitt 3), dass keine Sitzung offen ist.

### Geprüft (27.10.2026, lokal mit colima)

- **Image und Netz:** Image aus diesem Stand gebaut, im internen Docker-Netz ohne veröffentlichten Port gestartet, gegen die Test-DB.
- **Aus einem zweiten Container im selben Netz:**
  - `/gesundheit` und `/docs` ohne Schlüssel: 401, `/gesundheit` mit Schlüssel: 200.
  - `/turn` mit fremder Anfrage: 409 `anfrage_passt_nicht`.
  - `/turn` mit Schlüssel: 200 (`frage`, zwei KI-Aufrufe über `gemini-3.8-flash`, 4,5 s).
- **Vom eigenen Rechner:** keine Verbindung.
- **Ohne `BC1_ZUGANG`:** vier Startversuche mit klarer Meldung, danach bleibt der Container aus.
- **`vor-dem-start.sql`:** als `bc1_role` gegen die Test-DB fehlerfrei. M6 meldet ein über den echten Schreibweg angelegtes Profil.
- **Nicht geprüft:**
  - `docker compose` selbst. Es fehlt lokal; der Eintrag ist als YAML geprüft, das Verhalten mit reinem Docker nachgestellt.
  - Die BC0-Schnittstellenaufrufe in Abschnitt 2. Die Feldnamen hat eine unabhängige Prüfung gegen BC0s Code bestätigt.
  - Der Lauf auf BC0s Server.
