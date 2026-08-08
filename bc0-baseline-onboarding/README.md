# BC0 — Baseline & Onboarding

**Bounded Context 0** · Verantwortung: Simeon Ehmer · Stand: 07.08.2026

BC0 erhebt die Ausgangslage eines Mandanten und vergibt die IDs, an denen alle nachgelagerten Bounded Contexts hängen. Ohne BC0 gibt es keine Baseline — und ohne Baseline keinen Anker für BC1 bis BC4.

---

## Aktueller Stand

Die Anwendung läuft produktiv gegen PostgreSQL (Supabase, Region eu-west-1). Referenzmandant ist die **NoroAI Consulting GmbH**, ein virtuelles Unternehmen.

| | |
|---|---|
| Mandanten | 1 (NoroAI, virtuelles Referenzunternehmen) |
| Kernprozesse | 10 |
| Teilprozesse | 50 |
| Item-Bewertungen | **600** (4 KP × 5 TP × 30 Items) |
| Reifegrad gesamt | **Ø 3.63** |
| Beleg-Quote | **100 %** — jede Bewertung trägt einen Beleg |
| Schema | **v1.1.1** (`app/schema_v1.1.1.sql`) |
| Backend | FastAPI + PostgreSQL, PWA-Oberfläche |

Bewertungsgrundlage ist das **Bitkom-Reifegradmodell für digitale Geschäftsprozesse 3.0**: 5 Dimensionen × 15 Kriterien × 30 Items, Skala 1–5, je Teilprozess.

---

## Stabile IDs — der Vertrag

Alle Bounded Contexts hängen sich an diese IDs. Sie werden **ausschließlich von BC0 vergeben**, **nie geändert** und **nie wiederverwendet**.

| Ebene | Format | Beispiel |
|---|---|---|
| Kernprozess | `KP-XX` | `KP-02` |
| Teilprozess | `KP-XX.TP-Y` | `KP-02.TP-3` |
| Item-Bewertung | `KP-XX.TP-Y.I-NN` | `KP-02.TP-3.I-07` |

**Der Teilprozessteil ist einstellig.** Verbindlich nach ADR-002 vom 12.07.2026. In der Produktivdatenbank sind alle 600 Bewertungen in diesem Format, ohne Abweichung (geprüft 07.08.2026).

> **Achtung bei älteren Dokumenten:** In Artefakten aus der Erhebungsphase kursieren abweichende Schreibweisen (`KP-XX.TP-YY-Z`, `KP-XX.TP-YY`). Sie sind überholt. Wer gegen ein Muster mit zweistelligem Teilprozessteil validiert, weist gültige BC0-IDs ab. Maßgeblich ist ausschließlich das Format oben.

---

## Aufbau

```
bc0-baseline-onboarding/
├── README.md              dieses Dokument
└── app/                   Anwendung und Datenmodell
    ├── app.py             FastAPI-Anwendung, 17 Endpunkte
    ├── schema_v1.1.1.sql  aktuelles Schema (verbindlich)
    ├── schema_v1.1.sql    Vertragsstand ADR-002, historisch
    ├── static/            PWA (Oberfläche, Service Worker, Manifest)
    ├── snapshots/         Baseline-Snapshot + JSON-Schema
    ├── migrate_sqlite_to_pg.py   Migration SQLite → PostgreSQL
    ├── seed_noroai.py     Referenzdaten einspielen
    ├── export_snapshot.py Snapshot je Mandant erzeugen
    ├── gen_mandant_template.py   Erfassungsvorlage erzeugen
    ├── MIGRATION.md       Migrationsanleitung
    ├── DEPLOY.md          Deployment
    └── BACKUP.md          Backup und Wiederherstellung
```

---

## Datenmodell

Zehn Tabellen und sechs Views. Die wichtigsten:

| Tabelle | Inhalt |
|---|---|
| `companies` | Mandanten (UUID, Branche, Größe, Status) |
| `company_profile` | Unternehmensprofil, volles Profil als JSONB |
| `ref_prozesse` | Kernprozesse je Mandant, `process_id` = `KP-XX` |
| `ref_teilprozesse` | Teilprozesse, `sub_process_id` = `KP-XX.TP-Y`, dazu Tools, Medienbrüche, Schnittstellen |
| `ref_items` | die 30 Bitkom-Items (mandantenübergreifend) |
| `bitkom_bewertungen` | die Bewertungen, **Beleg ist Pflicht** (`NOT NULL` + `CHECK`) |
| `beleg_dokumente` | hochgeladene Belegdateien je Prozess oder Teilprozess |
| `bewertung_belege` | Verknüpfung Bewertung ↔ Dokument (angelegt, noch nicht befüllt) |
| `audit_log` | Änderungsprotokoll (angelegt, noch nicht befüllt) |

Views `v_reifegrad_tp`, `v_reifegrad_kp_dim`, `v_reifegrad_kp`, `v_reifegrad_company`, `v_prozessautomatisierung`, `v_crossfunktional` liefern die Auswertungen rein rechnerisch — sie enthalten keine gespeicherten Aggregate.

**Beleg-Pflicht ist hart erzwungen.** Eine Bewertung ohne Beleg lässt sich nicht speichern; die Datenbank weist sie ab. Das ist Absicht: Reifegradaussagen ohne Nachweis sind wertlos.

---

## Zugriff für BC1 bis BC4

**Über die Datenbank.** Lesend uneingeschränkt. Eigene DB-Rolle je Bounded Context, eigenes Schema für BC-eigene Arbeitsdaten. Schreibzugriff auf BC0-Tabellen ist derzeit nicht vorgesehen — das Schreibmodell steht mit ADR-003 zur Abstimmung.

**Über den Snapshot.** `app/snapshots/NoroAI_Consulting_GmbH_baseline_v1.json` ist ein eingefrorener, vollständiger Stand mit JSON-Schema (`snapshot_schema.json`). Nützlich für Entwicklung ohne Datenbankzugang und als datierter Stand.

> **Für lesende Komponenten:** Das Datenmodell wächst additiv — es kommen Felder dazu. Konsumenten sollten unbekannte Felder **ignorieren**, nicht mit einem Fehler abbrechen. Ein Schema mit `"additionalProperties": false` auf oberster Ebene weist bei jeder Erweiterung den kompletten Snapshot ab.

---

## Anwendung lokal starten

```bash
cd app
pip install -r requirements.txt
cp .env.example .env          # DATABASE_URL eintragen, oder leer lassen für SQLite
python -m uvicorn app:app --reload
```

Ohne `DATABASE_URL` läuft die Anwendung gegen eine lokale SQLite-Datei — praktisch zum Ausprobieren. Mit gesetzter `DATABASE_URL` gegen PostgreSQL. Welches Backend aktiv ist, zeigt `GET /api/meta` im Feld `backend`.

**Referenzdaten einspielen:**

```bash
python seed_noroai.py        # NoroAI-Baseline inkl. 600 Bewertungen
```

**Neuen Mandanten anlegen:**

```bash
python gen_mandant_template.py    # erzeugt mandant_vorlage.yaml
# ausfüllen, dann über POST /api/import_yaml einspielen
```

Deployment mit Docker Compose und Caddy: siehe `app/DEPLOY.md`. Backup und Wiederherstellung: `app/BACKUP.md`.

---

## Architekturentscheidungen

| | Inhalt | Status |
|---|---|---|
| **ADR-001** | PostgreSQL als Projektstandard, Ausprägung Supabase | angenommen 12.07.2026 |
| **ADR-002** | DB-Schema v1.1 ist verbindliche Vorgabe für alle BCs, stabile IDs als Vertrag | angenommen 12.07.2026 |
| **ADR-003** | SSoT-Schreibmodell: alle BCs schreiben additiv in die gemeinsame Datenbank | **Vorschlag**, Abstimmung 10.08.2026 |

---

## Was BC0 geliefert hat

- **Reifegradbericht NoroAI v1** — 600 Item-Bewertungen, Prozessautomatisierungs-Matrix, cross-funktionale Matrix, Spinnennetz-Profile
- **Unternehmensprofil NoroAI v6.0** — inklusive 4 Kernprozesse mit je 5 Teilprozessen
- **Datenmodell** — PostgreSQL-Schema, gegen den Parser validiert, produktiv im Einsatz
- **Anwendung** — Erfassung, Auswertung und Belegablage über eine installierbare PWA
- **Baseline-Snapshot** — versionierter Datenvertrag samt JSON-Schema
- **Datenfluss-Matrix** — 226 Aspekte über alle Bounded Contexts

## Was noch aussteht

- Belegablage auf Objektspeicher umstellen, OCR und Volltextsuche
- Änderungsprotokoll anschließen (`audit_log` ist angelegt, wird noch nicht befüllt)
- Benutzerverwaltung mit Rollentrennung
- Entitäten-Register: stabile IDs auch für Personen, Unternehmen, Tools und Systeme
- Re-Erhebung der Kernprozesse 5 bis 10 mit spezifischen Teilprozessen
