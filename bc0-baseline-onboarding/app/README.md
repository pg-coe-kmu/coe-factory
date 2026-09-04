# BC0 Onboarding-Tool (lokal lauffähig)

Erfassung der BC0-Baseline (Mandanten, Unternehmensprofil, Prozesse/Teilprozesse,
Bitkom-Self-Rating mit Beleg-Pflicht) **und** rechnerische Reifegrad-Feststellung
(Reifegradbericht, Prozessautomatisierungs-Matrix, Cross-funktionale Matrix,
5-Dimensionen- und 6-Kriterien-Spinnennetz).

**Stack:** FastAPI + SQLite + statisches HTML-Frontend. Mandantenfähig (company_id).
Autor: Simeon Ehmer · NoroAI · BC0.

---

## Schnellstart (lokal)

Voraussetzung: **Python 3.10+**.

```bash
cd BC0_App
pip install -r requirements.txt
python -m uvicorn app:app --port 8000
```

Dann im Browser öffnen: **http://localhost:8000**

> Hinweis: `python -m uvicorn` benutzen (nicht nur `uvicorn`), falls das CLI nicht im PATH liegt.
> Windows: ggf. `py -m uvicorn app:app --port 8000`.

Die Datenbank wird beim ersten Start automatisch als **`bc0.db`** (SQLite) neben `app.py` angelegt
und mit den 30 Bitkom-Items befüllt. Belege/Dateien: in dieser lokalen Variante als Feld;
Datei-Upload (MinIO) ist für die Server-Variante vorgesehen.

DB-Pfad überschreibbar: Umgebungsvariable `BC0_DB` setzen.

---

## Bedienung

1. **+ Neuer Mandant** → 3-Schritte-Onboarding (Firmendaten, Kernprozesse, Anlegen).
2. Im Mandanten-Arbeitsbereich:
   - **Unternehmensprofil** erfassen,
   - **Prozesse & Teilprozesse** (Owner, Rolle, Trigger/Input/Output, 5 TP je KP),
   - **Self-Rating** (30 Items je Teilprozess, Stufe 1–5, **Beleg Pflicht** — Speichern blockiert sonst),
   - **Bewertungen** (Grid),
   - **Reifegradbericht** (Ø je Dimension/KP, beide Spinnennetze, beide Matrizen, „Drucken/PDF").

---

## Datensicherung / Reset

- **Sicherung:** Datei `bc0.db` kopieren.
- **Reset:** `bc0.db` löschen → wird neu (leer) erzeugt.

---

## Später auf einen Server

1. **Gleicher Code:** Ordner `BC0_App` auf den Server kopieren, dort `pip install -r requirements.txt`
   und `python -m uvicorn app:app --host 0.0.0.0 --port 8000` (hinter Reverse-Proxy/HTTPS).
2. **Daten mitnehmen:** `bc0.db` mitkopieren.
3. **Umstieg auf PostgreSQL** (Zielstack): Das relationale Schema liegt in
   `../BC0_Onboarding_DB_Schema.sql`. SQLite→Postgres ist eine kleine Anpassung der
   DB-Anbindung in `app.py` (gleiche Tabellen/Spalten). Migration der Daten via Export/Import.

---

## API (Kurzreferenz)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/meta` | 30 Items, Dimensionen, KP-Vorlage, Kriterien |
| GET/POST | `/api/companies` | Mandanten lesen / anlegen |
| GET | `/api/companies/{id}` | Mandant inkl. Profil/Prozesse/Bewertungen |
| PUT | `/api/companies/{id}/profile` | Profil speichern |
| PUT | `/api/companies/{id}/process` | Prozess-Stammdaten + Teilprozesse |
| POST | `/api/companies/{id}/process/add` | Kernprozess hinzufügen |
| POST | `/api/companies/{id}/rating` | Self-Rating speichern (Beleg-Pflicht) |
| GET | `/api/companies/{id}/report` | Reifegrad + Matrizen + Spinnennetz-Daten |
| GET | `/api/companies/{id}/report?bis=E-…` | derselbe Bericht auf den **Stand nach einer Erhebung** (v2.9) |
| GET | `/api/companies/{id}/report/vergleich?von=&bis=` | **Vorher / Nachher** je Teilprozess, Dimension, Item (v2.9) |
| GET/POST | `/api/companies/{id}/erhebungen` | Erhebungen lesen (`offen`, `naechste`, `rang`, `fest`) · abschließen / neu / verwerfen (Admin, v2.8) |
| GET/POST | `/api/companies/{id}/uebergabe` | Paket an BC2 — je Anfrage nur vollständig oder Portfolio-Liste (Admin, v2.6/v2.7) |
| GET | `/api/companies/{id}/uebergabe/veraltet` | was sich seit Freigabe / Paket bewegt hat (v2.6) |
| POST | `/api/companies/{id}/gate/{tp}/widerrufen` | Freigabe widerrufen, Grund Pflicht (v2.6) |
| GET | `/api/companies/{id}/stand?datum=` | Reifegrad je Teilprozess zum Zeitpunkt, aus der Historie (v2.6) |
| GET | `/api/companies/{id}/historie` | Änderungshistorie des Mandanten (v2.6) |
| PUT | `/api/companies/{id}/anfragen/{a}/zuordnung` | Prozessbezüge einer Anfrage, `bezuege` n:m (v2.7) |

*Stand: 13.06.2026, Endpunkte ergänzt 04.09.2026 (Schema v2.6–v2.9) · BC0-interne Wahl (jedes BC entscheidet seine DB selbst). Maßgeblich ist der Quelltext; die Datenbankseite steht in `schema_v*.sql` und in der Datenbankdokumentation (Nachtrag v2.1–v2.9).*

---

## PWA (Stand 10.07.2026)

Diese Variante ist eine installierbare Progressive Web App auf Basis der aktuellen `BC0_App` (inkl. TP-Felder Tools/Medienbrüche/Schnittstellen/API).

- `static/manifest.json` — Scope `/`, standalone, Icons 192/512 (inkl. maskable)
- `static/sw.js` (v2) — Registrierung unter `/sw.js` (Root-Scope via app.py):
  - `/api/...` wird **nie** gecacht (immer live)
  - App-Shell: network-first mit Offline-Fallback aus dem Cache
  - Icons/Assets: cache-first
- Installation erfordert HTTPS (Deployment-Paket mit Caddy liegt bei) oder `localhost`.
- Offline: UI lädt aus dem Cache; Speichern/Bewerten braucht Verbindung (bewusst, Beleg-Pflicht serverseitig).
