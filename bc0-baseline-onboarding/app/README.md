# BC0 — Baseline und Reifegrad

Erfassung der BC0-Baseline (Mandanten, Unternehmensprofil, Prozesse/Teilprozesse,
Bitkom-Self-Rating mit Belegpflicht) **und** rechnerische Reifegrad-Feststellung
(Reifegradbericht, Prozessautomatisierungs-Matrix, Cross-funktionale Matrix,
5-Dimensionen- und 6-Kriterien-Spinnennetz).

**Stack:** FastAPI · **PostgreSQL/Supabase** im Betrieb, SQLite als lokaler Fallback und für Tests ·
statisches HTML-Frontend als installierbare PWA. Mandantenfähig (`company_id`), Rollen `benutzer`/`admin`.
Autor: Simeon Ehmer · Projektgruppe KI-CoE-KMU · Bounded Context 0.

> **Stand: 18.09.2026 · Schema v3.2.** Die Anwendung läuft produktiv hinter Caddy (HTTPS) auf einem
> eigenen Server; die Datenbank liegt bei Supabase in `eu-west-1` (Irland). Maßgeblich ist der
> Quelltext; die Datenbankseite steht in `schema_v*.sql` und in der Datenbankdokumentation.

---

## Betrieb (Server)

Docker Compose mit zwei Diensten: `app` (FastAPI) und `caddy` (Reverse Proxy mit automatischem HTTPS).

```bash
cp .env.example .env      # ausfüllen, siehe unten
docker compose up -d --build
```

Konfiguration ausschließlich über `.env` — siehe `.env.example`. Die wichtigsten Variablen:

| Variable | Wirkung |
|---|---|
| `DATABASE_URL` | Gesetzt → PostgreSQL/Supabase. Leer → SQLite-Fallback auf `/data/bc0.db`. |
| `DOMAIN` | Domain für Caddy; ohne Angabe reines HTTP auf `:80`. |
| `SUPABASE_URL` · `SUPABASE_SERVICE_KEY` · `SUPABASE_BUCKET` | Belegablage in Supabase Storage. Ohne diese Variablen liegen Belege auf dem Volume unter `/data/belege`. |
| `MAX_DOC_MB` | Obergrenze je Belegdatei (Vorgabe 15). |
| `BC2_HOOK_URL` · `BC2_HOOK_SECRET` · `BC2_HOOK_TIMEOUT` | Ruf an BC2 (v3.1/v3.2). Ohne `BC2_HOOK_URL` wird nicht gerufen — das Paket steht trotzdem in der Datenbank, BC2 holt es über `v_uebergabe_offen` nach. |

> **Zwei Regeln, die schon Zeit gekostet haben.** Erstens: Nach dem Push ist nichts ausgerollt —
> Repository und Server sind zwei Dinge. Zweitens: Eine Variable in `.env` ist erst im Container,
> wenn sie in `docker-compose.yml` unter `environment:` durchgereicht wird.
> Geheimnisse gehören in die `.env` des Servers, nicht in die Datenbank und nicht ins Repository.

---

## Schnellstart (lokal)

Voraussetzung: **Python 3.10+**.

```bash
pip install -r requirements.txt
python -m uvicorn app:app --port 8000
```

Dann im Browser öffnen: **http://localhost:8000**

> `python -m uvicorn` benutzen (nicht nur `uvicorn`), falls das CLI nicht im PATH liegt.
> Windows: ggf. `py -m uvicorn app:app --port 8000`.

Ohne `DATABASE_URL` wird die Datenbank beim ersten Start als **`bc0.db`** (SQLite) neben `app.py`
angelegt und mit den 30 Bitkom-Items befüllt; der Pfad ist über `BC0_DB` überschreibbar. Belege
liegen dann lokal unter `./belege`.

**Grenzen des SQLite-Modus:** Sechs Wege brauchen PostgreSQL und antworten sonst mit einem Hinweis
statt mit Daten — Übergabe an BC2, Nachliefern, Historie, Zeitreise (`stand?datum=`), Abgleich mit
der Historie (`uebergabe/veraltet`) und das Nachziehen auf `am_gate`.

---

## Bedienung

1. **+ Neuer Mandant** → 3-Schritte-Onboarding (Firmendaten, Kernprozesse, Anlegen).
2. Im Mandanten-Arbeitsbereich:
   - **Unternehmensprofil** erfassen,
   - **Prozesse & Teilprozesse** (Owner, Rolle, Trigger/Input/Output, Tools, Medienbrüche, Schnittstellen),
   - **Self-Rating** (30 Items je Teilprozess, Stufe 1–5, **Beleg Pflicht** — Speichern blockiert sonst),
   - **Erhebung** (Kennung `E-JJJJ-MM`, abschließen, Nacherhebung `-2`, `-3`, …),
   - **Belege** hochladen (Text aus Office-Dateien und PDFs mit Textebene wird verlustfrei ausgelesen),
   - **Bewertungen** (Grid), **Vorher/Nachher** je Erhebung,
   - **Reifegradbericht** (Ø je Dimension/KP, beide Spinnennetze, beide Matrizen, „Drucken/PDF"),
   - **Gate 0** — Freigabe je Teilprozess, Paket schnüren, an BC2 übergeben, widerrufen.
3. Unter **`/anfrage`** liegt die eigene Einstiegsseite zum Melden eines Anliegens — mit und ohne
   Prozessbezug, ebenfalls installierbar.

---

## Datensicherung / Reset

- **PostgreSQL/Supabase:** nächtliches Backup auf dem Server; Wiederherstellung über `pg_restore`.
  Siehe `DEPLOY.md`.
- **SQLite (lokal):** Sicherung = Datei `bc0.db` kopieren · Reset = `bc0.db` löschen, wird leer neu erzeugt.

---

## API (Kurzreferenz)

**Stammdaten und Bericht**

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/meta` | 30 Items, Dimensionen, KP-Vorlage, Kriterien |
| GET/POST | `/api/companies` | Mandanten lesen / anlegen |
| GET | `/api/companies/{id}` | Mandant inkl. Profil/Prozesse/Bewertungen |
| PUT | `/api/companies/{id}/profile` | Profil speichern |
| PUT | `/api/companies/{id}/process` | Prozess-Stammdaten + Teilprozesse |
| POST | `/api/companies/{id}/process/add` | Kernprozess hinzufügen |
| POST | `/api/companies/{id}/rating` | Self-Rating speichern (Belegpflicht) |
| GET | `/api/companies/{id}/report` | Reifegrad + Matrizen + Spinnennetz-Daten |
| GET | `/api/companies/{id}/report?bis=E-…` | derselbe Bericht auf den **Stand nach einer Erhebung** (v2.9) |
| GET | `/api/companies/{id}/report/vergleich?von=&bis=` | **Vorher / Nachher** je Teilprozess, Dimension, Item (v2.9) |
| GET/PUT | `/api/companies/{id}/entitaeten` | Personen, Systeme, Rollen (`P-NN`, `S-NN`, `R-NN`) |
| GET/PUT | `/api/companies/{id}/rollen_kosten` | Rollenklassen und Kostensätze |
| POST | `/api/companies/{id}/prozesskanten` | Prozesslandkarte, Kanten zwischen Prozessen (v2.4) |

**Erhebung, Belege, Historie**

| Methode | Pfad | Zweck |
|---|---|---|
| GET/POST | `/api/companies/{id}/erhebungen` | Erhebungen lesen (`offen`, `naechste`, `massgeblich`, je Zeile `rang`/`fest`) · abschließen / neu / verwerfen (Admin, v2.8) |
| POST/GET | `/api/companies/{id}/documents` | Beleg hochladen / auflisten; Textextraktion beim Upload |
| GET | `/api/companies/{id}/documents/suche` | Volltextsuche über Belege (Dateiname höchstes Gewicht) |
| GET | `/api/companies/{id}/documents/{doc}/file` | Beleg herunterladen |
| DELETE | `/api/companies/{id}/documents/{doc}` | Beleg löschen |
| GET | `/api/companies/{id}/stand?datum=` | Reifegrad je Teilprozess zum Zeitpunkt, aus der Historie (v2.6) |
| GET | `/api/companies/{id}/historie` | Änderungshistorie des Mandanten (v2.6) |

**Anfrage (Gate-Anker)**

| Methode | Pfad | Zweck |
|---|---|---|
| GET/POST | `/api/companies/{id}/anfragen` | Anfragen lesen / anlegen — Kennung `A-JJJJ-NN`; **`angelegt_von` wird mitgeschrieben (v3.0)** |
| GET | `/api/companies/{id}/anfragen/{a}/vorschlaege` | Prozessvorschläge zur Zuordnung |
| PUT | `/api/companies/{id}/anfragen/{a}/zuordnung` | Prozessbezüge einer Anfrage, `bezuege` n:m (v2.7) |
| PUT | `/api/companies/{id}/anfragen/{a}/status` | Statuslauf der Anfrage |
| POST | `/api/companies/{id}/anfragen/gate_nachziehen` | **Anfragen auf `am_gate` ziehen, deren Teilprozesse vollständig sind (v3.0)** |

**Gate 0 und Übergabe an BC2**

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/companies/{id}/gate` | Freigabestand über alle Teilprozesse |
| GET/POST | `/api/companies/{id}/gate/{tp}` | Prüfbogen lesen / Freigabe erteilen |
| POST | `/api/companies/{id}/gate/{tp}/widerrufen` | Freigabe widerrufen, Grund Pflicht (v2.6) |
| GET/POST | `/api/companies/{id}/uebergabe` | Paket an BC2 — je Anfrage nur vollständig oder Portfolio-Liste (Admin, v2.6/v2.7). **Schnürt das Paket und ruft BC2 nach dem COMMIT (v3.1)** |
| POST | `/api/companies/{id}/uebergabe/nachliefern` | **Wiederholt die Rufe an BC2, die noch offen sind (Admin, v3.1)** |
| GET | `/api/companies/{id}/uebergabe/veraltet` | was sich seit Freigabe / Paket bewegt hat (v2.6) |

---

## Die Schnittstelle zu BC2 (v3.1 / v3.2)

Beim Schnüren eines Pakets ruft BC0 den BC2-Dienst und übergibt **nur Kennungen** —
`company_id`, `paket_id`, `uebergeben_am`. Die Daten holt BC2 mit der `paket_id` selbst.

*Warum nur Kennungen:* Eine Nachricht ist nicht wiederholbar lesbar, ein Zustand schon. Die Nachricht
ist der Zettel mit der Nummer, nicht der Inhalt — die Datenbank bleibt alleinige Quelle
(ADR-003 Regel 4).

| | |
|---|---|
| **Signatur** | HMAC-SHA256 über den Rumpf, Kopfzeilen `X-BC0-Signature` und `X-BC0-Timestamp`. Schlüssel aus `BC2_HOOK_SECRET` (bei BC2 heißt derselbe Wert `BC2_TRIGGER_TOKEN`). |
| **Kennung** | `User-Agent: BC0/3.2` |
| **Zeitstempel** | RFC 3339, normalisiert durch `_rfc3339()` (**v3.2** — PostgreSQL liefert `::text` mit Leerzeichen und zweistelligem Zonenversatz). Ohne `uebergeben_am` wird **gar nicht** gerufen; der Fehlschlag wird protokolliert. |
| **Protokoll** | `bc_zustellungen`, append-only: jeder Versuch steht drin, auch der gescheiterte. Offene Rufe in `v_zustellung_offen`. |
| **Rückfallebene** | `v_uebergabe_offen` — **ein verpasster Ruf ist kein verlorenes Paket.** |

Zieladresse und Geheimnis stehen bewusst **nicht** in der Datenbank, sondern in der `.env` des
Servers — ein Geheimnis gehört nicht in eine Tabelle, die vier Kontexte lesen dürfen.

---

## PWA

Installierbare Progressive Web App, Hülle `bc0-pwa-v12`.

- `static/manifest.json` — Scope `/`, standalone, Icons 192/512 (inkl. maskable)
- `static/sw.js` — Registrierung unter `/sw.js` (Root-Scope über `app.py`):
  - `/api/...` wird **nie** gecacht (immer live)
  - App-Shell: network-first mit Offline-Fallback aus dem Cache
  - Icons/Assets: cache-first
- Installation erfordert HTTPS oder `localhost`.
- Offline: Die Oberfläche lädt aus dem Cache; Speichern und Bewerten brauchen Verbindung —
  bewusst so, weil die Belegpflicht serverseitig geprüft wird.
- Die Anfragemaske unter `/anfrage` hat eigene Einstiegsseite, eigenen Service-Worker-Pfad und
  eigenes Manifest.

---

## Regeln, die für diesen Code gelten

| | |
|---|---|
| **ADR-002** | ID-Formate: `KP-XX` · `KP-XX.TP-Y` · `KP-XX.TP-Y.I-NN` |
| **ADR-003** | Die Datenbank ist Single Source of Truth. Geschrieben wird **additiv** — eigene Spalten mit Präfix oder eigene Tabellen. Niemand ändert fremde Werte. |
| **ADR-004** | Klarnamen stehen an genau einer Stelle (`ref_personen`). Nach außen und an Sprachmodelle geht ausschließlich die ID. |
| **ADR-005** | Herkunftspflicht: Jede Bewertung trägt Quelle und Güte (`belegt` / `geschätzt` / `geraten` / `entfällt`). |
| **R9** | Historie statt Sperre — `audit_log`, `stand_zum()`, `bewertung_aktuell_zum()`. Es darf weitergeschrieben werden; jeder frühere Stand bleibt abrufbar. |

---

## Weiterführende Papiere im Repository

| Datei | Inhalt |
|---|---|
| `ARCHITEKTUR.md` | Aufbau, Schichten, Entscheidungen |
| `AUTH.md` | Anmeldung, Rollen, Sitzungen |
| `ROLLEN.md` | Datenbankrollen `bc1_role`–`bc4_role`, Gruppenrolle `bc_leser` |
| `SICHERHEIT.md` | Sicherheitsbericht mit offen benannten Lücken |
| `TESTABDECKUNG.md` | Was geprüft ist — und was nicht |
| `DEPLOY.md` | Ausrollen, Backup, Wiederherstellung |
| `MIGRATION.md` | Schemawege und Reihenfolge |
| `schema_v*.sql` | Alle Schemastände, rein additiv, v1.1 bis v3.1 |

*Stand: 18.09.2026 · Schema v3.2 · BC0-interne Wahl der Datenbank (jedes BC entscheidet seine
eigene). Maßgeblich ist der Quelltext.*
