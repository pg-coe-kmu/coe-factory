# BC0: Migration SQLite → Supabase-PostgreSQL (Schema v1.1)

Stand: 10.07.2026 · getestet End-to-End gegen lokales PostgreSQL (Report SQLite ≙ Report Postgres, 600 Bewertungen, Ø 3.63, Beleg-Quote 100 %).

## Prinzip

Die App wählt das Backend über die Umgebungsvariable `DATABASE_URL`:

| DATABASE_URL | Backend | Schema |
|---|---|---|
| gesetzt | PostgreSQL/Supabase | **Schema v1.1** (Projekt-Vorgabe: UUID, ENUMs, Views, Trigger) |
| leer / nicht gesetzt | SQLite `bc0.db` | internes App-Schema (unverändert, lokaler Fallback) |

Eine `.env` neben `app.py` wird automatisch geladen. Der lokale SQLite-Betrieb bleibt vollständig funktionsfähig.

## Schritte (einmalig)

1. **Supabase-Projekt anlegen** (Region Frankfurt/eu-central-1, Passwort sichern).
2. **Connection-String holen:** Dashboard → Connect → *Session Pooler*. Beispiel:
   `postgresql://postgres.PROJEKTREF:[PASSWORT]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require`
3. **`.env` anlegen** (Vorlage: `.env.example`):
   ```
   DATABASE_URL=postgresql://postgres.PROJEKTREF:[PASSWORT]@...:5432/postgres?sslmode=require
   ```
4. **Abhängigkeiten:** `pip install -r requirements.txt` (neu: `psycopg2-binary`).
5. **Migration ausführen:**
   ```
   python3 migrate_sqlite_to_pg.py                  # alle Mandanten aus bc0.db
   python3 migrate_sqlite_to_pg.py --only NoroAI    # nur NoroAI
   python3 migrate_sqlite_to_pg.py --dry-run        # nur anzeigen
   ```
   Das Skript spielt **Schema v1.1 automatisch ein** (aus `schema_v1.1.sql`), wenn die Ziel-DB leer ist,
   und verifiziert am Ende Zeilenzahlen + Reifegrad über die View `v_reifegrad_company`.
   Es ist **idempotent** (deterministische UUIDs via uuid5, Upserts) — mehrfach ausführbar.
6. **App starten:** `uvicorn app:app --port 8000` → `/api/meta` zeigt `"backend": "postgres"`.

## Mapping App ↔ Schema v1.1

| App (SQLite) | Schema v1.1 (Postgres) |
|---|---|
| `companies.id` (INTEGER) | `companies.company_id` (UUID) |
| `companies.ma` | `companies.mitarbeitende` |
| `bitkom_bewertungen.process_id` (Spalte) | abgeleitet: `left(sub_process_id,5)` |
| `quelle`/`kategorie`/`status` (TEXT) | ENUMs `beleg_source`/`process_category`/`onboarding_status` |
| `company_profile.profile_json` (TEXT) | `JSONB` |

Beleg-Pflicht ist in Postgres **hart** (CHECK); leere Belege werden bei Migration durch `"(migriert ohne Beleg)"` ersetzt (aktuell: 0 Fälle).

## Beleg-Dokumente (Stufe 1 — seit 10.07.2026)

Upload von Dateien (PDF/Bilder) je KP/TP im Self-Rating-Reiter der PWA (mobil direkt per Kamera).
Endpoints: `POST/GET /api/companies/{cid}/documents`, `GET …/{doc_id}/file`, `DELETE …/{doc_id}`.
Tabellen `beleg_dokumente` + `bewertung_belege` werden beim App-Start automatisch angelegt (SQLite und Postgres, idempotent).

Datei-Ablage: ohne weitere Konfiguration lokal unter `./belege/` (`BELEGE_DIR`).
Mit `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in der `.env` landen Dateien im **Supabase Storage**
(Bucket `belege`, wird automatisch angelegt). Max. Dateigröße: `MAX_DOC_MB` (Default 15).
OCR/LLM-Zuordnung sind Stufe 2/3 (siehe `../BC0_Beleg_Ingestion_OCR_Konzept_v1.md`); die Status-Spalte ist dafür vorbereitet.

## Hinweise / bekannte Grenzen

- `export_snapshot.py` und `seed_noroai.py` arbeiten weiterhin direkt auf SQLite (`bc0.db`). Snapshot-Export
  aus Postgres ist ein Folgeschritt (sinnvoll zusammen mit der geplanten Baseline-Snapshot-API).
- RLS: Schema v1.1 dokumentiert die empfohlene Tenant-Policy (Abschnitt 7); die App verbindet als
  DB-Owner — Policies greifen erst mit eigener Rolle (Folgeschritt fürs Deployment).
- PWA-Installation braucht HTTPS (Caddy-Deployment-Paket liegt bei) oder `localhost`.
