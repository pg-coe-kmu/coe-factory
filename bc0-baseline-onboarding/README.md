# BC0 — Baseline & Onboarding

**Bounded Context 0** · Verantwortung: Simeon Ehmer · Stand: 12.08.2026

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
| Schema | **v1.3** — Grundmodell `app/schema_v1.1.1.sql`, Nachträge `app/schema_v1.2_*.sql` und `app/schema_v1.3_*.sql` |
| Backend | FastAPI + PostgreSQL, PWA-Oberfläche |
| Betrieb | **https://bc0.perspektivwechsel.ai** — Docker Compose hinter Caddy, TLS automatisch |
| Zugangsschutz | **Anmeldepflicht seit 11.08.2026.** Serverseitige Sitzungen, Rollentrennung Benutzer/Admin, Mandantenfilter in jedem Endpunkt |
| Tests | **89** |

Bewertungsgrundlage ist das **Bitkom-Reifegradmodell für digitale Geschäftsprozesse 3.0**: 5 Dimensionen × 15 Kriterien × 30 Items, Skala 1–5, je Teilprozess.

---

## Stabile IDs — der Vertrag

Alle Bounded Contexts hängen sich an diese IDs. Sie werden **ausschließlich von BC0 vergeben**, **nie geändert** und **nie wiederverwendet**.

| Ebene | Format | Beispiel |
|---|---|---|
| Kernprozess | `KP-XX` | `KP-02` |
| Teilprozess | `KP-XX.TP-Y` | `KP-02.TP-3` |
| Item-Bewertung | `KP-XX.TP-Y.I-NN` | `KP-02.TP-3.I-07` |
| Rolle | `R-NN` | `R-02` |
| Person | `P-NN` | `P-01` |
| System beim Mandanten | `S-NN` | `S-03` |
| System im Produktkatalog | `SYS-<Kat>-<Kurz>` | `SYS-CRM-ESPO` |
| Medienbruch | `MB-NNN` | `MB-001` |

Die fünf zuletzt genannten sind seit **ADR-004** vom 12.08.2026 vergeben (`app/ADR-004_Entitaeten_Identitaet.md`). Personen und Systeme lagen vorher als Freitext in `ref_prozesse.owner_name` und `ref_teilprozesse.tools` — beide Felder mussten eine n:m-Beziehung in einen einzelnen Text pressen und sind maschinell nicht auflösbar. Sie bestehen übergangsweise weiter und werden nach Prüfung der Migration entfernt.

**Der Teilprozessteil ist einstellig.** Verbindlich nach ADR-002 vom 12.07.2026. In der Produktivdatenbank sind alle 600 Bewertungen in diesem Format, ohne Abweichung (geprüft 07.08.2026).

> **Achtung bei älteren Dokumenten:** In Artefakten aus der Erhebungsphase kursieren abweichende Schreibweisen (`KP-XX.TP-YY-Z`, `KP-XX.TP-YY`). Sie sind überholt. Wer gegen ein Muster mit zweistelligem Teilprozessteil validiert, weist gültige BC0-IDs ab. Maßgeblich ist ausschließlich das Format oben.

---

## Aufbau

```
bc0-baseline-onboarding/
├── README.md              dieses Dokument
└── app/                   Anwendung und Datenmodell
    ├── app.py             FastAPI-Anwendung, 30 Endpunkte
    ├── bc0_auth/          Anmeldung und Benutzerverwaltung (Paket)
    ├── tests/             89 Tests
    ├── schema_v1.1.1.sql  Grundmodell
    ├── schema_v1.2_*.sql  Benutzerverwaltung · Stammdaten und Gate
    ├── schema_v1.3_*.sql  Personen- und Systemregister (ADR-004)
    ├── migration_v1.3_*.sql  Überführung der alten Freitextfelder
    ├── schema_v1.1.sql    Vertragsstand ADR-002, historisch
    ├── AUTH.md            Betriebsanleitung der Anmeldung
    ├── ROLLEN.md          DB-Rollen und Rechte
    ├── ADR-004_Entitaeten_Identitaet.md
    ├── benutzer_verwalten.py     Benutzer auf der Kommandozeile
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

**23 Tabellen und 14 Views.** Die vollständige Beschreibung — jede Spalte, jede Werteliste, Rechtelage und HTTP-Schnittstelle — liegt außerhalb dieses Repositories im Projektordner (`10_DB_Dokumentation/BC0_Datenbank_Dokumentation_v1.3.md`), weil sie Zugangswege benennt. Die wichtigsten Tabellen:

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
| `mandant_rollen`, `rollen_kostensaetze` | Rollen mit Kostenklasse `K1`–`K5`, Vollkostensätze mit Quelle und Gültigkeit |
| `ref_personen`, `prozess_personen` | Personenregister und Zuordnung zum Prozess mit Funktion |
| `ref_systeme_katalog`, `mandant_systeme`, `teilprozess_systeme` | Produktkatalog, Systeme des Mandanten, Zuordnung |
| `medienbrueche` | Übergänge zwischen Systemen ohne durchgehende Datenverbindung |
| `gate_ereignisse` | Freigabeprotokoll des HitL-Gates, append-only |
| `app_benutzer`, `app_benutzer_mandanten`, `app_sitzungen` | Anmeldung und Mandantenzuweisung |

Views `v_reifegrad_tp`, `v_reifegrad_kp_dim`, `v_reifegrad_kp`, `v_reifegrad_company`, `v_prozessautomatisierung`, `v_crossfunktional` liefern die Auswertungen rein rechnerisch — sie enthalten keine gespeicherten Aggregate.

**Beleg-Pflicht ist hart erzwungen.** Eine Bewertung ohne Beleg lässt sich nicht speichern; die Datenbank weist sie ab. Das ist Absicht: Reifegradaussagen ohne Nachweis sind wertlos.

---

## Zugriff für BC1 bis BC4

**Über die Datenbank.** Eigene DB-Rolle je Bounded Context, eigenes Schema für BC-eigene Arbeitsdaten. Das Schreibmodell steht mit **ADR-003, angenommen am 10.08.2026**: BC0 hält die Baseline, alle anderen lesen und schreiben in ihre eigenen Schemata. Es gibt keinen Nachrichtenkanal zurück nach BC0 — wer etwas mitteilen will, schreibt es in die Datenbank, und BC0 liest es dort.

**Personenbezogene Daten laufen über Sichten, nicht über Tabellen.** Nach ADR-004 R5 stehen Klarnamen an genau einer Stelle (`ref_personen.name`), und die ist für lesende Kontexte gesperrt. Statt `ref_prozesse` bitte **`v_prozesse_lesen`** verwenden: dieselben Spalten ohne `owner_name` und `owner_role`, dafür `eigner_ids` und `sponsor_ids` als Array von `person_id`. Dazu `v_prozess_personen_lesen` mit Funktion, Rolle und Kostenklasse — ohne Namen.

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
| **ADR-003** | SSoT-Schreibmodell: alle BCs schreiben additiv in die gemeinsame Datenbank | **angenommen 10.08.2026** |
| **ADR-004** | Identität der Entitäten: IDs fachlich und lesbar, serverseitig vergeben, nie wiederverwendet, gesperrt statt gelöscht, Klarnamen an genau einer Stelle | **angenommen 12.08.2026** |

---

## Was BC0 geliefert hat

- **Reifegradbericht NoroAI v1** — 600 Item-Bewertungen, Prozessautomatisierungs-Matrix, cross-funktionale Matrix, Spinnennetz-Profile
- **Unternehmensprofil NoroAI v6.0** — inklusive 4 Kernprozesse mit je 5 Teilprozessen
- **Datenmodell** — PostgreSQL-Schema, gegen den Parser validiert, produktiv im Einsatz
- **Anwendung** — Erfassung, Auswertung und Belegablage über eine installierbare PWA
- **Baseline-Snapshot** — versionierter Datenvertrag samt JSON-Schema
- **Datenfluss-Matrix** — 226 Aspekte über alle Bounded Contexts

## Was noch aussteht

- **Erhebungen als eigene Entität** (`ref_erhebungen`, Schema v1.3 Teil C). Eine Bewertung weiß heute nur, *wann* sie entstand, nicht *zu welcher Erhebung* sie gehört — eine Nacherhebung überschriebe den bisherigen Stand, und eine Gate-Freigabe wäre nicht reproduzierbar
- **Entzug des Leserechts auf `ref_prozesse`** (`schema_v1.3_teil_a2_rechte_umstellung.sql`), sobald die lesenden Kontexte auf `v_prozesse_lesen` umgestellt haben
- Änderungsprotokoll anschließen (`audit_log` ist angelegt, wird noch nicht befüllt)
- Freigabe-Dashboard des HitL-Gates — die Datenbankseite steht, es fehlt das Statusfeld aus BC1
- Belegablage auf Objektspeicher umstellen, OCR und Volltextsuche
- Re-Erhebung der Kernprozesse 5 bis 10 mit spezifischen Teilprozessen
- `input_text` und `output_text` nachtragen — bei allen zehn Prozessen leer
