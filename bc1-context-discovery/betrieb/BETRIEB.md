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
- **Jeder abgeschlossene Lauf verbraucht eine Anfrage samt Teilprozess.** Danach steht die Anfrage am Gate, und ein zweites Profil am selben Teilprozess ließe BC0s Freigabe veralten. Je Lauf also eine neue Testanfrage zu einem Teilprozess, den BC0 nennt.
- **Nur Testdaten.** Für echte Personen fehlen noch die Datenschutz-Punkte: Hinweis in der App, Löschen, Aufbewahrungsfrist, Vertrag mit dem KI-Anbieter.

**Begrüßungstext** (zeigt BC0s Chat-Ansicht als erste Zeile; BC1 antwortet erst auf die erste Nachricht):

> Guten Tag! Ich stelle Ihnen einige Fragen zu dem Ablauf, um den es in Ihrer Anfrage geht.
> Am besten beantworten Sie sie in einem Zug. Bitte nennen Sie keine Namen, E-Mail-Adressen oder
> Telefonnummern von Personen. Wenn Sie bereit sind, schreiben Sie einfach eine erste Nachricht.

## Teil 2 — Technik

### 1. Einrichten (einmalig)

1. **Checkout auf festem Tag**, getrennt von BC0s Code, z. B. `git clone --branch <tag> https://github.com/pg-coe-kmu/coe-factory.git /opt/bc1/coe-factory`. Dann zieht BC0s übliches `docker compose up -d --build` nie ungeprüft einen neuen BC1-Stand mit.
2. **`.env.bc1`** aus `env.bc1.vorlage` anlegen und füllen; die Datei liegt nur auf dem Server. In **BC0s `.env`** kommen `BC1_ZUGANG` und `BC1_COMPANY_ID`. Den Schlüssel auf dem Server erzeugen: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. Er muss mindestens 32 Zeichen lang sein, nur ASCII, ohne Leerzeichen; sonst bricht BC1 den Start ab.
3. **Erst dann den Compose-Eintrag** aus `compose-bc1.yml` übernehmen (Dienst `bc1`, bei `app` die drei Zeilen). Fehlen Checkout oder `.env.bc1`, scheitert sonst vermutlich das ganze `docker compose up`.
4. **Zugang zu BC0 prüfen**, nur lesend: `docker compose run --rm bc1 /app/.venv/bin/python -m bc1_service.bc0_meldungen --probe` (Exit 0 = bereit).
5. **Vor dem Start messen** (Abschnitt 3), dann `docker compose up -d bc1` und im Log auf die Zeile `dienst gestartet paket=… schema_version=… mandant=…` warten.

### 2. Ablauf je Testlauf

1. **Anfrage anlegen** — in BC0s Oberfläche mit dem BC1-Dienstkonto oder über die Schnittstelle (unten). Im Originaltext steht „Testanfrage“; Kernprozess und Teilprozess sind die, die BC0 genannt hat.
2. **Mit OK von BC0 auf `zugeordnet` setzen** — dafür gibt es in BC0s Oberfläche keinen Knopf, nur die Schnittstelle (unten).
3. **`BC1_ANFRAGE_ID`** in `.env.bc1` auf die neue Nummer setzen.
4. **Messen** (Abschnitt 3).
5. **Neu starten:** `docker compose up -d bc1`, im Log die Zeile `dienst gestartet` prüfen.
6. **Gespräch** in BC0s App unter „Meine Anfragen“.
7. **Gate 0** bei BC0; danach geht das Paket an BC2.

**Schnittstelle von BC0** (Feldnamen aus BC0s `app.py`; so noch nicht live erprobt). Das Passwort geht über `printf` (Shell-Befehl, erscheint nicht in der Prozessliste) an `curl`; enthält es ein `"` oder `\`, stattdessen die Oberfläche nehmen:

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

```bash
psql "$BC1_DB_DSN" -v mandant=<uuid> -v anfrage=A-JJJJ-NN -f betrieb/vor-dem-start.sql
```

Nur lesend, als `bc1_role`. Erwartet:
- M0: `bc1_role`.
- M1: keine Sitzung `aktiv`, `wartet_auf_antwort` oder `fehler_fortsetzbar`.
- M2: kein Entwurf `in_erhebung`.
- M3: kein ausstehender Abschluss.
- M4: kein fehlendes Leserecht.
- M5: die Anfrage steht auf `zugeordnet` und hat mindestens einen Teilprozess.

Steht in M1 oder M2 etwas, das niemand mehr fortsetzt: nach [`../bc1_service/n8n/SMOKE.md`](../bc1_service/n8n/SMOKE.md), Abschnitt „K5“, verwerfen. Sonst erst abschließen lassen. Grund: Mit jeder Anfrage wechselt die Paketkennung, und eine offene Sitzung liefe danach ins Leere.

### 4. Update und Neustart

- **Neuer Stand:** im Checkout den Tag wechseln (`git fetch --tags && git checkout <tag>`), messen (Abschnitt 3), `docker compose up -d --build bc1`. Jedes Update stimmen BC0 und BC1 vorher kurz ab. `GET /gesundheit` (mit Header) nennt `paket` und `schema_version`.
- **Nach einem Neustart des Servers** startet `bc1` nicht von selbst (`restart: "on-failure:3"`, siehe Kommentar in `compose-bc1.yml`). Einmal `docker compose up -d bc1` ausführen und den Start im Log prüfen. Dasselbe gilt, wenn der ganze Stack hochfährt, bevor Caddy bereit ist: Die drei Wiederholungen folgen zu schnell aufeinander, um das abzufangen.

### 5. Log lesen

`docker compose logs bc1 --since 1h`. Nachrichtentexte, Werte und Profildaten stehen nie im Log. Die wichtigsten Zeilen:

| Zeile | Bedeutung |
|---|---|
| `bc1.dienst dienst gestartet paket=… mandant=…` | Start erfolgreich |
| `bc1.dienst turn … http=200 status=frage` | normaler Turn |
| `bc1.dienst turn … http=409 status=anfrage_passt_nicht` | BC0 hat eine andere Anfrage oder einen anderen Mandanten geschickt |
| `bc1.api zugang_verweigert pfad=… grund=fehlt\|falsch` | Header fehlt oder falscher Schlüssel (Konfiguration bei BC0 prüfen) |
| `bc1.kern ki_aufruf … ergebnis=fehler` | KI nicht erreichbar oder Guthaben leer; die Person bekommt `fehler_fortsetzbar` |
| `RuntimeError: …` beim Start | regulärer Startabbruch; der Satz sagt, was fehlt (Tabellen in `SMOKE.md`, „Aufbau“) |

Alle Zeilen erklärt die README, Abschnitt „Betriebsprotokoll“.

### 6. Häufige Fehlerbilder

| Symptom | Ursache | Tun |
|---|---|---|
| BC0 bekommt keine Verbindung zu `bc1` | Container läuft nicht, z. B. nach einem Startabbruch | `docker compose ps bc1`, Log lesen, Ursache beheben, `up -d bc1` |
| Start bricht ab mit „steht auf 'am_gate'“ | Die eingestellte Anfrage ist schon fertig interviewt | neuen Testlauf vorbereiten (Abschnitt 2) |
| Start bricht ab mit „BC1_ZUGANG …“ | Schlüssel fehlt, ist zu kurz oder enthält fremde Zeichen | BC0s `.env` prüfen |
| jede Anfrage 401 | BC0 schickt den Header nicht oder einen anderen Wert | `BC1_ZUGANG` bei `app` und `bc1` gleich? |
| 409 `anfrage_passt_nicht` | Die App bietet eine Anfrage an, die BC1 gerade nicht bedient | erwartet bei anderen Anfragen; sonst `BC1_ANFRAGE_ID` prüfen |
| `fehler_fortsetzbar` im Chat | KI-Aufruf gescheitert | Guthaben im KI-Konto und Log `ki_aufruf` prüfen; die Person sendet dieselbe Nachricht erneut |

### 7. Rückfall: Vorführung vom eigenen Rechner

Läuft der Einbau nicht, zeigt man dieselbe Fachstrecke lokal: Dienst gegen Supabase mit der vorbereiteten Anfrage, Chat über n8n auf `localhost` (README und `SMOKE.md`). **Vorher `bc1` auf dem Server stoppen** (`docker compose stop bc1`): Zwei Dienste auf derselben Datenbank sind nicht vorgesehen.

### Geprüft (27.10.2026, lokal mit colima)

- **Image und Netz:** Image aus diesem Stand gebaut, im internen Docker-Netz ohne veröffentlichten Port gestartet, gegen die Test-DB.
- **Aus einem zweiten Container im selben Netz:**
  - `/gesundheit` und `/docs` ohne Schlüssel: 401, `/gesundheit` mit Schlüssel: 200.
  - `/turn` mit fremder Anfrage: 409 `anfrage_passt_nicht`.
  - `/turn` mit Schlüssel: 200 (`frage`, zwei KI-Aufrufe über `gemini-3.8-flash`, 4,5 s).
- **Vom eigenen Rechner:** keine Verbindung.
- **Ohne `BC1_ZUGANG`:** vier Startversuche mit klarer Meldung, danach bleibt der Container aus.
- **`vor-dem-start.sql`:** fehlerfrei als `bc1_role` gegen die Test-DB.
- **Nicht geprüft:**
  - `docker compose` selbst. Es fehlt lokal; der Eintrag ist als YAML geprüft, das Verhalten mit reinem Docker nachgestellt.
  - Die BC0-Schnittstellenaufrufe in Abschnitt 2.
  - Der Lauf auf BC0s Server.
