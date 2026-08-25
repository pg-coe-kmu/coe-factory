# BC1 DB-Anbindung Etappe 1 — Profil-Fundament: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BC1 schreibt sein Prozessprofil als versionierte, eingefrorene Zeile nach
`bc1.prozessprofil` — mit validierter Teilprozess-Identität, Mandanten-Guard und
DB-durchgesetzten Freeze-/Versionsregeln, damit BC0s Gate-0-Dashboard echte Daten sieht.

**Architecture:** Vier Bausteine, streng getrennt. (1) **DDL** (`bc1_service/db/prozessprofil.sql`)
— Vertragstabellen, Trigger, Rechte, atomare Einspiel-Dreifallregel; die Datenbank
erzwingt Version, Freeze und Eindeutigkeit, der Writer verlässt sich darauf.
(2) **Kern-Erweiterung K0** — `FieldSpec.identitaetskritisch` + dritter Ausgang
`abgebrochen_ohne_identitaet` (generisch, kein BC1-Sonderfall) plus ein neues
`SessionState`-Feld `company_id` als ausnahmsloser Mandanten-Guard. (3) **Paket-Schicht**
— statische Teilprozess-Auswahl und paketlokaler S-NN-Feldtyp, beide beim Dienststart
aus BC0 geladen, beide im Paket-Fingerprint `1.1+ctx-<16hex>`. (4) **Profil-Writer**
(`bc1_service/profil_writer.py`) — Reconcile-Modell: gleicht am Ende jedes zugelassenen
Turns Soll und Ist ab, bindet Session→Profil atomar über `bc1.profil_write_status`,
friert beim Abschluss ein und liefert der API das DB→Wire-Overlay.

**Tech Stack:** Python 3.12 · PostgreSQL 16/17 (Test-Container, später Supabase) ·
psycopg 3 + psycopg_pool · FastAPI · pytest (Container-Tests über `BC1_TEST_DB_DSN`).

> **Stand: Rev. 9 — Bau-Befund aus Task 3 eingearbeitet (siehe Changelog Rev. 9).**
> Rev. 8 war von Codex freigegeben (Runde 8: READY, 0 Findings); der Befund kam
> erst beim Ausführen am Container zutage, nicht beim Lesen.
> Verlauf: R1 NO (7C/6I/1M) · R2 NO (3C/6I/1M) · R3 WITH FIXES (0C/2I/2M) ·
> R4 WITH FIXES (0C/2I/1M) · R5 WITH FIXES (0C/2I) · R6 WITH FIXES (1C — am Container
> widerlegt, von Codex an PG-Doku und RI-Quellcode bestätigt) · R7 WITH FIXES (0C/1I) ·
> **R8 READY**. Abnahmeumfang: Tasks 1–12 und Task 16 Steps 1–2 sind ohne Rückfrage
> ausführbar, K0–K5 und die darauf entfallenden Erfolgskriterien vollständig gedeckt.
> Changelogs am Ende.
>
> ⛔ **Ausführbar sind heute Tasks 1–12 sowie Task 16, Steps 1–2** (Betriebsdoku).
> Task 16, Step 3 ist die Gesamtverifikation — sie setzt Tasks 13–15 voraus.
> Tasks 13–15 hängen an Klärpunkt
> **K-A** (`erhebung_id`-Regel, Bündel-Frage #1 an Simeon) — ohne diese Antwort kann
> der Writer nicht fertiggestellt werden. Das ist keine Lücke des Plans, sondern die
> externe Abhängigkeit, die die Spec selbst benennt.

**Spec:** `docs/superpowers/specs/2026-08-23-bc1-db-profil-fundament-design.md`
(Rev. 15, freigegeben 25.08. nach 15 Codex-Runden — im Projekt-Root über dem Clone).
Der Plan argumentiert aus der Spec; beide zusammen lesen. **Die Spec ist bindend: bei
Widerspruch zwischen Plan und Spec gewinnt die Spec — Abweichung melden, nicht
stillschweigend auflösen.**

**Grundlagen-Dokumente (nicht neu verhandeln):** Brief BC1→BC0 vom 22.08.
(`Entwurf-Antwort-BC1-an-BC0-Checkliste.md`, Abschnitte 2 + 3 = Spaltentabellen,
Statusfeld, Freeze-Regeln) · BC0-Antwort vom 23.08. (`Simeon/`, Abschnitt 1) ·
BC0-Schema `origin/main:bc0-baseline-onboarding/app/schema_v1.*.sql` + `ROLLEN.md`.

---

## Global Constraints

- **Branch:** `bc1-db-profil-fundament`, abgezweigt von `bc1-gemini-adapter` @ `058a77e`
  (= Stand PR #157, 18 Commits). Kette wie gehabt (#129 → #130 → #151 → #157 → dieser).
  Task 1 legt den Branch an und committet diesen Plan.
- **TDD, ohne Ausnahme.** Der tdd-guard bewacht `*.py` unter `coe-factory/` und wird NIE
  umgangen. Bei einem Block: Skill `tdd-guard` aufrufen, nicht improvisieren.
- **pytest IMMER aus `bc1-context-discovery/` und IMMER mit Test-DB:**
  ```
  BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest
  ```
  Container starten, falls er nicht läuft (Docker über colima — `colima start`):
  ```
  docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16
  ```
  Ohne DSN skippen die Container-Tests **still** — dieser Plan baut fast nur
  Container-Tests. Ein grüner Lauf ohne DSN beweist NICHTS.
- **Suite-Basis: 245 passed, 4 skipped, 0 Warnings** (Stand 058a77e, Momentaufnahme).
  Erwartete Zahlen in den Tasks sind Momentaufnahmen — reale Zahlen laufen lassen,
  berichten, Abweichungen explizit benennen.
- **Ein Commit je RED→GREEN-Paar.** Conventional Commits, Scope `bc1`, Sprache deutsch
  (Code-Kommentare, Docstrings, Commit-Messages).
- **Zwei Mandanten in JEDER DB-Fixture.** Alle BC0-Lookups laufen zwingend über
  `WHERE company_id = %s`; jeder Lesepfad bekommt einen Test, der beweist, dass er den
  fremden Mandanten NICHT sieht (Spec R5-I5). IDs wie `KP-01.TP-1` oder `S-01`
  wiederholen sich über Mandanten hinweg — ein vergessener Filter ist ein Datenleck,
  kein Schönheitsfehler.
- **Kein Deploy in die Supabase in diesem Plan.** Die DDL ist ein voll testbares Gerüst
  (Test-Container ja, Produktion nein). Eingespielt wird erst, wenn K-C (Zahlen-
  Wertebereiche mit BC2) entschieden ist; das GRANT-Signal an BC0 geht erst mit dem
  Deploy (Spec K1, Deploy-Gate).
- **Betriebsgrenze:** bis zur PII-Schicht (#150) ausschließlich Demo-/Testdaten, kein
  Echtmandant (Brief Abschnitt 3).
- **Numerics über `Decimal`, nie `float`.** `psycopg` liefert `numeric` als `Decimal`;
  jede Konvertierung im Writer geht über `Decimal(str(...))`.
- **Wire-Werte sind lowercase** (bestehender Vertrag): `gueltig`, `ungeloest`,
  `abgebrochen_ohne_identitaet`, `mandant_konflikt`.

### Ehrliche Präzisierungen zur Spec (vor dem Bau lesen)

Drei Stellen, an denen die Spec das *Was* festlegt und dieser Plan das *Wie* ergänzt.
Keine davon ändert eine Zusage; alle drei sind bewusst hier aufgeschrieben, damit sie
im Review sichtbar sind:

1. **`process_turn` bekommt einen Parameter `company_id` (keyword-only, ohne Default).**
   Die Spec verlangt den Mandanten-Guard „nach jedem `store.load()` als ERSTES" — also
   im Kern. Der Kern liest keine Umgebungsvariablen (Architektur-Invariante), folglich
   muss der Wert hineingereicht werden. Das ist eine dritte, rein **mechanische**
   Kern-Berührung neben den beiden fachlichen (K0-Guard, State-Feld) und wird als solche
   berichtet — kein Default `None`, damit es keinen stillen zweiten Betriebsmodus gibt.
2. **Die API lädt den State nach dem Turn erneut** (`store.load`), um dem Writer den
   Stand NACH dem Turn zu geben. Der Kern-Vertrag (Rückgabe = Antwort-Dict) bleibt damit
   unverändert; Preis ist ein zusätzlicher SELECT pro Turn. Bewusst so: Alternative wäre
   eine geänderte Kern-Rückgabe — teurer für den Vertrag als für die Datenbank.
3. **`bc1_service/bc0_lesepfade.py` sind freie Funktionen mit `conn` als erstem
   Parameter** (keine Klasse). Grund: Der S-NN-Sweep und der `erhebung_id`-Lookup müssen
   laut Spec in DERSELBEN Transaktion laufen wie der Write — mit einem Verbindungs-
   Parameter ist das die natürliche Form; beim Dienststart öffnet der Aufrufer eine
   kurze eigene Verbindung.

---

## File Structure

**Neu:**

| Datei | Verantwortung | Task |
|---|---|---|
| `bc1_service/db/prozessprofil.sql` | Die eine DDL — Vertragstabellen, Trigger, Indizes, Rechte, Dreifallregel. Test-Container und (später) Supabase spielen dieselbe Datei ein. | 3, 4 |
| `tests/db/bc0_geruest.sql` | Minimales, schema-identisches BC0-Gerüst für Tests (aus `schema_v1.*` abgeleitet), inkl. Rollen + DEFAULT PRIVILEGES. | 2 |
| `tests/db_fixture.py` | Fixture-Helfer: Gerüst + DDL einspielen, zwei Mandanten anlegen, aufräumen. | 2 |
| `tests/test_ddl_trigger.py` | Trigger-/Index-Verträge am Container. | 3 |
| `tests/test_ddl_einspielen.py` | Dreifallregel + Rechte/ACL-Vererbung. | 4 |
| `bc1_service/bc0_lesepfade.py` | Die fünf BC0-Lookups, alle mandantengefiltert. | 8, 13 |
| `tests/test_bc0_lesepfade.py` | Lesepfade inkl. Zweit-Mandanten-Negativtests. | 8, 13 |
| `bc1_service/paket_feldtypen.py` | Paketlokaler S-NN-Feldtyp (kanonisierende Normalisierung + komponierter Validator). | 9 |
| `tests/test_paket_feldtypen.py` | Feldtyp-Verträge. | 9 |
| `bc1_service/profil_writer.py` | Profil-Bau (Mapping, Sweep) + Reconcile (Bindung, INSERT, Rebind, Freeze, Postcondition). | 11, 12, 14 |
| `tests/test_profil_bau.py` | Reine Bau-/Mapping-/Sweep-Tests, ohne DB. | 11, 12 |
| `tests/test_profil_writer.py` | Reconcile am Container (Durchstich, 503, Rebind, Konflikt, Idempotenz). | 14, 15 |

**Geändert:**

| Datei | Änderung | Task |
|---|---|---|
| `bc1_core/types.py` | `SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET` · `Ergebnis`-Enum · `SessionState.company_id` | 5 |
| `bc1_core/package.py` | `FieldSpec.identitaetskritisch: bool = False` | 5 |
| `bc1_core/dialog.py` | `Decision.ergebnis` statt `done`; Completion-Guard-Semantik | 5 |
| `bc1_core/serialize.py` | `company_id` schreiben + rückwärtskompatibel lesen | 5 |
| `bc1_core/core.py` | Mandanten-Guard, company_id-Bindung, dritter Ausgang (LLM-frei), Terminal-Weiche, Recovery-Ausnahme | 6 |
| `bc1_service/api.py` | `company_id`-Pflichtparameter, 409 `mandant_konflikt`, Terminal-Gate beide Zustände, schema_version-Guard mit Recovery-Ausnahme, Abbruch-Text, Writer-Aufruf + Overlay + 503 | 7, 15 |
| `bc1_service/discovery_paket.py` | `Bc0Kontext`, TP-Auswahl, `identitaetskritisch`, S-NN-Typ, Fingerprint `1.1+ctx-` | 10 |
| `bc1_service/paket_wahl.py` | Kontext durchreichen | 10 |
| `bc1_service/main.py` | `BC1_COMPANY_ID` Pflicht + UUID- und Existenzprüfung, Kontext laden, Pool + Writer verdrahten | 10, 15 |
| `bc1_service/n8n/SMOKE.md` | Startvariablen, Einspiel-Anleitung, K5-Betriebsrezept | 16 |
| `tests/test_core.py`, `tests/test_api.py`, `tests/test_dialog.py`, `tests/test_serialize.py`, `tests/test_discovery_paket.py`, `tests/test_seam.py` | Anpassung an neue Signaturen | 5–7, 10 |

---

## Reihenfolge

```
Phase A (DB-Fundament)      Task 1 → 2 → 3 → 4
Phase B (Kern K0 + Guard)   Task 5 → 6 → 7
Phase C (Paket + Lesepfade) Task 8 → 9 → 10
Phase D (Writer)            Task 11 → 12 → [K-A-Gate] → 13 → 14 → 15
Phase E (Betrieb)           Task 16
```

Strikt sequenziell. Phase A und Phase B sind technisch unabhängig voneinander (DDL
berührt keinen Python-Kern) — wer parallelisiert, muss trotzdem beide vor Phase D
abschließen. Phase C braucht Phase A (Lesepfade testen gegen das Gerüst) und Phase B
(`identitaetskritisch` muss existieren).

**Blockiert:** Task 13 (`erhebung_id`-Regel) hängt an Klärpunkt **K-A** (Bündel-Frage #1
an Simeon) — und Task 14 (Reconcile) hängt an Task 13, weil der Writer die Funktion beim
Anlegen JEDER Profilzeile ruft. **Phase D endet damit real nach Task 12, solange K-A
offen ist** (Codex R1-C6). Tasks 1–12 und die Doku aus Task 16 sind ohne Antwort baubar;
ob Task 13/14 gegen die vorläufige Regel vorgezogen werden, entscheidet Richard.

---

# Phase A — DB-Fundament

## Task 1: Branch, Plan-Commit, Basis verifizieren

**Files:**
- Create: `bc1-context-discovery/design/Implementierungsplan-DB-Profil-Fundament.md` (diese Datei)

**Interfaces:**
- Consumes: —
- Produces: Branch `bc1-db-profil-fundament` mit diesem Plan als erstem Commit.

- [x] **Step 1: Branch anlegen** — ERLEDIGT 25.08.: `bc1-db-profil-fundament` auf
      `058a77e` gepinnt, Hash verifiziert.

```bash
cd coe-factory
git fetch origin
git checkout -b bc1-db-profil-fundament 058a77e
git log -1 --format=%H          # MUSS 058a77e... sein, sonst stoppen
```

Der Branch wird **direkt auf `058a77e` gepinnt** — ein `pull --ff-only` auf
`bc1-gemini-adapter` könnte den Ausgangsstand stillschweigend verschieben.

- [x] **Step 2: Test-Container hochfahren und Basis messen** — ERLEDIGT 25.08.:
      `245 passed, 4 skipped` — exakt die erwartete Basis. Die 4 Skips sind
      Echt-API-Stichproben (Claude/Gemini/Ollama, brauchen `BC1_ECHT_LLM=1`),
      **keine still übersprungenen Container-Tests** — mit `-rs` nachgeprüft.

```bash
docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16
```

Dann aus `bc1-context-discovery/`:

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q
```

Erwartet: `245 passed, 4 skipped` (Momentaufnahme — reale Zahl notieren und berichten).
**Weicht die Zahl ab, erst klären, dann bauen.** Läuft der Container nicht, ist die
Zahl wertlos (Container-Tests skippen still).

- [x] **Step 3: PostgreSQL-Version festhalten** — ERLEDIGT 25.08.:
      `PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on aarch64-unknown-linux-gnu`.
      16 ≥ 14, also `CREATE OR REPLACE TRIGGER` und `pg_advisory_xact_lock` nutzbar.

```bash
docker exec bc1-test-pg psql -U postgres -c "select version()"
```

Der Plan nutzt `CREATE OR REPLACE TRIGGER` (ab PG 14) und `pg_advisory_xact_lock`.
Ist der Container älter als 14, neu aufsetzen — nicht umbauen.

- [x] **Step 4: Commit** — ERLEDIGT 25.08. als `bc57daa` (nicht gepusht: Push ins
      geteilte Repo braucht Richards ausdrückliches OK).

**Task 1 ist vollständig abgeschlossen (25.08.).** Alle vier Steps abgehakt, Basis und
PG-Version gemessen. Task 2 kann starten.

---

## Task 2: BC0-Test-Gerüst mit zwei Mandanten

**Warum zuerst:** Ohne ein schema-identisches BC0-Gerüst lässt sich weder ein
Fremdschlüssel anlegen noch ein Mandantenfilter widerlegen. Das Gerüst ist aus
`origin/main:bc0-baseline-onboarding/app/schema_v1.*.sql` **abgeleitet** — nicht neu
erfunden: Spalten, Typen, CHECK-Muster und Sichten werden übernommen.

**Files:**
- Create: `tests/db/bc0_geruest.sql`
- Create: `tests/db_fixture.py`
- Create: `tests/test_db_fixture.py`

**Interfaces:**
- Consumes: BC0-Schema-Dateien auf `origin/main` (nur als Vorlage, kein Import).
- Produces:
  - `tests/db_fixture.py`: `MANDANT_A: str`, `MANDANT_B: str`,
    `DSN: str | None` (aus `BC1_TEST_DB_DSN`),
    `frische_db(dsn: str, *, mit_ddl: bool = True) -> None`,
    `spiele_ddl_ein(dsn: str) -> None`,
    `verbindung(dsn: str, rolle: str | None = None)` (Contextmanager, `SET ROLE`).

- [x] **Step 1: Gerüst-SQL schreiben** (`tests/db/bc0_geruest.sql`) — ERLEDIGT 25.08.

Struktur + Rollen + Rechte, KEINE Testdaten (die setzt Python).

```sql
-- BC0-Gerüst für BC1-Tests. Abgeleitet aus schema_v1.1 / v1.2 / v1.3 (Teile A, B, C).
-- Wird als postgres (Superuser) eingespielt.
--
-- Anspruch, präzise (Codex R4-C3): Enthalten sind nur die Objekte, die BC1
-- berührt — für diese aber DEFINITIONSGLEICH: Spaltennamen, Typen, CHECK-Muster,
-- Schlüssel und Sichtdefinitionen wie in BC0. Nicht berührte Zusatzspalten
-- (z. B. ref_teilprozesse.medienbrueche/schnittstellen/api, mandant_rollen.hinweis,
-- weitere companies-Spalten) fehlen bewusst: Unser SQL nennt sie nie, sie können
-- also keinen falschen Grünstand erzeugen — anders als ein abweichender
-- Spaltenname, der genau das täte (deshalb sub_process_name statt step_name).
-- Wächst der Lesepfad in Etappe 2, wächst das Gerüst mit.

-- ---------- Rollen (idempotent; ROLLEN.md-Modell) ----------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
        CREATE ROLE bc_leser NOLOGIN;
    END IF;
    FOR i IN 1..4 LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc' || i || '_role') THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', 'bc' || i || '_role');
        END IF;
        EXECUTE format('GRANT bc_leser TO %I', 'bc' || i || '_role');
    END LOOP;
END $$;

-- ---------- Typen (wortgleich aus schema_v1.1) ----------
CREATE TYPE process_category AS ENUM
    ('Steuerungsprozess', 'Kerngeschäftsprozess', 'Unterstützungsprozess');
CREATE TYPE beleg_source AS ENUM
    ('chat', 'doc', 'xlsx', 'interview', 'manuell', 'baseline', 'yaml');

-- ---------- BC0-Stammdaten ----------
CREATE TABLE companies (
    company_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL
);

CREATE TABLE ref_prozesse (
    company_id   uuid             NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    process_id   varchar(8)       NOT NULL CHECK (process_id ~ '^KP-[0-9]{2}$'),
    process_name text             NOT NULL,
    kategorie    process_category NOT NULL,
    beschreibung text,                       -- ALTER aus schema_v1.2
    owner_name   text,
    owner_role   text,
    trigger_text text,
    input_text   text,
    output_text  text,
    created_at   timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, process_id)
);

CREATE TABLE ref_teilprozesse (
    company_id       uuid        NOT NULL,
    sub_process_id   varchar(16) NOT NULL CHECK (sub_process_id ~ '^KP-[0-9]{2}\.TP-[0-9]+$'),
    process_id       varchar(8)  NOT NULL,
    step_no          integer     NOT NULL CHECK (step_no BETWEEN 1 AND 5),
    sub_process_name text        NOT NULL,
    notation         text,
    tools            text,
    PRIMARY KEY (company_id, sub_process_id),
    FOREIGN KEY (company_id, process_id)
        REFERENCES ref_prozesse(company_id, process_id) ON DELETE CASCADE,
    UNIQUE (company_id, process_id, step_no)
);

CREATE TABLE mandant_rollen (
    company_id  uuid NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    rolle_id    text NOT NULL,
    bezeichnung text NOT NULL,
    klasse      text NOT NULL CHECK (klasse IN ('K1','K2','K3','K4','K5')),
    aktiv       boolean NOT NULL DEFAULT true,
    PRIMARY KEY (company_id, rolle_id)
);

CREATE TABLE mandant_systeme (
    company_id  uuid NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    system_id   text NOT NULL CHECK (system_id ~ '^S-[0-9]{2}$'),
    bezeichnung text NOT NULL,
    PRIMARY KEY (company_id, system_id)
);

CREATE TABLE ref_erhebungen (
    company_id  uuid NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    erhebung_id text NOT NULL CHECK (erhebung_id ~ '^E-[0-9]{4}-[0-9]{2}$'),
    bezeichnung text NOT NULL,
    stand       date NOT NULL,
    status      text NOT NULL CHECK (status IN ('offen','abgeschlossen','verworfen')),
    PRIMARY KEY (company_id, erhebung_id)
);

CREATE TABLE ref_items (
    item_nr   integer PRIMARY KEY CHECK (item_nr BETWEEN 1 AND 30),
    dimension text NOT NULL,
    kriterium text NOT NULL,
    frage     text NOT NULL
);

CREATE TABLE bitkom_bewertungen (
    company_id     uuid         NOT NULL,
    erhebung_id    text         NOT NULL,
    id             varchar(28)  NOT NULL
                   CHECK (id ~ '^KP-[0-9]{2}\.TP-[0-9]+\.I-[0-9]{2}$'),
    sub_process_id varchar(16)  NOT NULL,
    item_nr        integer      NOT NULL REFERENCES ref_items(item_nr),
    stufe          integer      NOT NULL CHECK (stufe BETWEEN 1 AND 5),
    beleg          text         NOT NULL CHECK (length(btrim(beleg)) > 0),
    quelle         beleg_source NOT NULL DEFAULT 'manuell',
    bewerter       text,
    bewertet_am    timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, erhebung_id, id),
    FOREIGN KEY (company_id, sub_process_id)
        REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id, erhebung_id)
        REFERENCES ref_erhebungen(company_id, erhebung_id) ON DELETE CASCADE,
    UNIQUE (company_id, erhebung_id, sub_process_id, item_nr)
);

CREATE TABLE prozess_personen (
    company_id uuid NOT NULL,
    process_id varchar(8) NOT NULL,
    person_id  text NOT NULL,
    funktion   text NOT NULL
        CHECK (funktion IN ('eigner','sponsor','mitwirkend','vertretung')),
    PRIMARY KEY (company_id, process_id, person_id, funktion),
    FOREIGN KEY (company_id, process_id)
        REFERENCES ref_prozesse(company_id, process_id) ON DELETE CASCADE
);

-- ---------- Sichten (wortgleich aus schema_v1.3 übernommen) ----------
CREATE OR REPLACE VIEW v_bewertung_aktuell AS
SELECT company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg,
       quelle, bewerter, bewertet_am
  FROM (SELECT b.company_id, b.erhebung_id, b.id, b.sub_process_id, b.item_nr,
               b.stufe, b.beleg, b.quelle, b.bewerter, b.bewertet_am,
               row_number() OVER (PARTITION BY b.company_id, b.sub_process_id, b.item_nr
                                  ORDER BY e.stand DESC, e.erhebung_id DESC) AS rang
          FROM bitkom_bewertungen b
          JOIN ref_erhebungen e
            ON e.company_id = b.company_id AND e.erhebung_id = b.erhebung_id
         WHERE e.status <> 'verworfen') t
 WHERE rang = 1;

CREATE OR REPLACE VIEW v_prozesse_lesen AS
SELECT p.company_id, p.process_id, p.process_name, p.beschreibung,
       p.trigger_text, p.input_text, p.output_text, p.created_at,
       (SELECT array_agg(pp.person_id ORDER BY pp.person_id)
          FROM prozess_personen pp
         WHERE pp.company_id = p.company_id AND pp.process_id = p.process_id
           AND pp.funktion = 'eigner')  AS eigner_ids,
       (SELECT array_agg(pp.person_id ORDER BY pp.person_id)
          FROM prozess_personen pp
         WHERE pp.company_id = p.company_id AND pp.process_id = p.process_id
           AND pp.funktion = 'sponsor') AS sponsor_ids
  FROM ref_prozesse p;

-- ---------- Schema bc1 + Rechte wie in BC0s ROLLEN.md ----------
CREATE SCHEMA IF NOT EXISTS bc1 AUTHORIZATION bc1_role;
GRANT USAGE, CREATE ON SCHEMA bc1 TO bc1_role;
GRANT USAGE ON SCHEMA bc1 TO bc_leser;
GRANT USAGE ON SCHEMA public TO bc1_role, bc_leser;

-- Der Stolperstein aus R14-I1: BC0 vergibt SELECT auf JEDE neue Tabelle von bc1_role
-- automatisch an bc_leser. Ohne diese Zeile testet die ACL-Prüfung ins Leere.
ALTER DEFAULT PRIVILEGES FOR ROLE bc1_role IN SCHEMA bc1 GRANT SELECT ON TABLES TO bc_leser;

-- Rechte, die BC1 laut Spec K1 (Einspiel-Voraussetzungen I9) bekommt:
GRANT REFERENCES ON companies, ref_prozesse, ref_teilprozesse, mandant_rollen,
                    ref_erhebungen TO bc1_role;
GRANT SELECT ON v_bewertung_aktuell, mandant_systeme, ref_teilprozesse, companies,
                v_prozesse_lesen TO bc1_role;

-- BEWUSST NICHT: SELECT auf ref_prozesse (BC0 hat das Recht entzogen, R14-I2).
-- Ein Test beweist, dass der direkte Lesezugriff scheitert und v_prozesse_lesen trägt.
--
-- ABWEICHUNG, bewusst und geprueft (25.08., Abgleich gegen origin/main): BC0s
-- prozess_personen traegt zusaetzlich einen FK auf ref_personen(company_id, person_id).
-- Den hat das Geruest nicht, weil ref_personen fehlt — das Geruest ist an dieser
-- Stelle also LAXER als BC0. Folgenlos, solange BC1 prozess_personen nur mittelbar
-- ueber v_prozesse_lesen liest und nie beschreibt. Schreibt BC1 dort je hinein,
-- muss ref_personen ins Geruest.
```

- [x] **Step 2: Fixture-Modul schreiben** (`tests/db_fixture.py`) — ERLEDIGT 25.08.

```python
"""Fixture-Helfer für alle DB-Tests: BC0-Gerüst + unsere DDL + zwei Mandanten.

Zwei Mandanten sind Pflicht (Spec R5-I5): BC0-IDs wie 'KP-01.TP-1' oder 'S-01'
wiederholen sich über Mandanten hinweg — ein vergessener company_id-Filter fällt
nur mit einem zweiten Mandanten auf.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg

DSN = os.environ.get("BC1_TEST_DB_DSN")

MANDANT_A = "11111111-1111-1111-1111-111111111111"
MANDANT_B = "22222222-2222-2222-2222-222222222222"

_GERUEST = Path(__file__).parent / "db" / "bc0_geruest.sql"
_DDL = Path(__file__).parents[1] / "bc1_service" / "db" / "prozessprofil.sql"


def frische_db(dsn: str, *, mit_ddl: bool = True) -> None:
    """Setzt public + bc1 zurueck, baut das Geruest, spielt (optional) unsere DDL ein.

    ACHTUNG: raeumt auch bc1.sessions weg — einen PostgresStateStore erst NACH
    diesem Aufruf anlegen (sein Konstruktor legt die Tabelle wieder an).
    """
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS bc1 CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(_GERUEST.read_text(encoding="utf-8"))
        _testdaten(conn)
    if mit_ddl:
        spiele_ddl_ein(dsn)


def spiele_ddl_ein(dsn: str) -> None:
    """Spielt prozessprofil.sql genau wie im Betrieb ein: EINE Transaktion, als bc1_role."""
    with psycopg.connect(dsn) as conn:          # autocommit=False => eine Transaktion
        conn.execute("SET ROLE bc1_role")
        conn.execute(_DDL.read_text(encoding="utf-8"))
        conn.commit()


@contextmanager
def verbindung(dsn: str, rolle: str | None = "bc1_role"):
    """Verbindung mit optionalem SET ROLE (None = postgres/Superuser)."""
    with psycopg.connect(dsn) as conn:
        if rolle:
            conn.execute(f"SET ROLE {rolle}")
        yield conn


def _testdaten(conn) -> None:
    for mandant, kuerzel in ((MANDANT_A, "A"), (MANDANT_B, "B")):
        conn.execute("INSERT INTO companies (company_id, name) VALUES (%s, %s)",
                     (mandant, f"Demo {kuerzel}"))
        conn.execute(
            "INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) "
            "VALUES (%s, 'KP-01', %s, 'Kerngeschäftsprozess'), "
            "       (%s, 'KP-02', %s, 'Unterstützungsprozess')",
            (mandant, f"Auftrag {kuerzel}", mandant, f"Einkauf {kuerzel}"))
        # Namen bewusst mandantenspezifisch: gleiche IDs, verschiedene Inhalte —
        # nur so faellt ein fehlender company_id-Filter im Test auf.
        conn.execute(
            "INSERT INTO ref_teilprozesse "
            "(company_id, sub_process_id, process_id, step_no, sub_process_name) VALUES "
            "(%s, 'KP-01.TP-1', 'KP-01', 1, %s), "
            "(%s, 'KP-01.TP-2', 'KP-01', 2, %s), "
            "(%s, 'KP-02.TP-1', 'KP-02', 1, %s)",
            (mandant, f"Erfassen {kuerzel}", mandant, f"Pruefen {kuerzel}",
             mandant, f"Bestellen {kuerzel}"))
        conn.execute(
            "INSERT INTO mandant_rollen (company_id, rolle_id, bezeichnung, klasse) "
            "VALUES (%s, 'R-01', 'Sachbearbeitung', 'K2')", (mandant,))
    # Nur bei Mandant B: damit lassen sich Verbund-FK und Mandantenfilter gezielt
    # verletzen — eine ID, die es beim anderen Mandanten NICHT gibt.
    conn.execute(
        "INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) "
        "VALUES (%s, 'KP-03', 'Nur bei B', 'Steuerungsprozess')", (MANDANT_B,))
    conn.execute(
        "INSERT INTO ref_teilprozesse "
        "(company_id, sub_process_id, process_id, step_no, sub_process_name) "
        "VALUES (%s, 'KP-02.TP-2', 'KP-02', 2, 'Nur bei B')", (MANDANT_B,))
    # Systeme: S-01 gibt es in BEIDEN Mandanten (verschiedene Bedeutung),
    # S-02 nur in A, S-03 nur in B — genau der Fall, den ein fehlender Filter frisst.
    conn.execute("INSERT INTO mandant_systeme (company_id, system_id, bezeichnung) "
                 "VALUES (%s, 'S-01', 'SAP A'), (%s, 'S-02', 'DATEV A')",
                 (MANDANT_A, MANDANT_A))
    conn.execute("INSERT INTO mandant_systeme (company_id, system_id, bezeichnung) "
                 "VALUES (%s, 'S-01', 'Navision B'), (%s, 'S-03', 'Lexware B')",
                 (MANDANT_B, MANDANT_B))
    conn.execute(
        "INSERT INTO ref_items (item_nr, dimension, kriterium, frage) VALUES "
        "(1, '1) Technologie', 'Systemunterstuetzung', 'Wie digital laeuft der Schritt?'), "
        "(2, '2) Daten', 'Datenqualitaet', 'Wie strukturiert liegen die Daten vor?')")
    conn.execute(
        "INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, stand, status) "
        "VALUES (%s, 'E-2026-01', 'Erst', '2026-01-15', 'abgeschlossen'), "
        "       (%s, 'E-2026-02', 'Nach',  '2026-06-01', 'abgeschlossen')",
        (MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, stand, status) "
        "VALUES (%s, 'E-2026-09', 'B-Erhebung', '2026-03-01', 'abgeschlossen')",
        (MANDANT_B,))
    # A: KP-01.TP-1 wurde in E-2026-01 bewertet und in E-2026-02 teilweise nacherhoben
    # (genau die 1.2-Logik: je Item die juengste nicht verworfene Erhebung).
    # id folgt BC0s Muster '^KP-\d{2}\.TP-\d+\.I-\d{2}$'; beleg ist Pflicht.
    # A: Item 1 wurde in E-2026-02 nacherhoben, Item 2 steht noch auf E-2026-01 —
    # genau die 1.2-Logik "je Einzelbewertung die juengste nicht verworfene".
    conn.execute(
        "INSERT INTO bitkom_bewertungen "
        "(company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg, "
        " bewertet_am) VALUES "
        "(%s, 'E-2026-01', 'KP-01.TP-1.I-01', 'KP-01.TP-1', 1, 2, 'Erstaufnahme', "
        " '2026-01-15'), "
        "(%s, 'E-2026-01', 'KP-01.TP-1.I-02', 'KP-01.TP-1', 2, 3, 'Erstaufnahme', "
        " '2026-01-15')",
        (MANDANT_A, MANDANT_A))
    conn.execute(
        "UPDATE bitkom_bewertungen SET erhebung_id = 'E-2026-02', "
        "       stufe = 4, beleg = 'Nacherhebung', bewertet_am = '2026-06-01' "
        " WHERE company_id = %s AND id = 'KP-01.TP-1.I-01'", (MANDANT_A,))
    # B: gleicher Teilprozess-Schluessel, andere Erhebung — Kollisionsfalle.
    conn.execute(
        "INSERT INTO bitkom_bewertungen "
        "(company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg) VALUES "
        "(%s, 'E-2026-09', 'KP-01.TP-1.I-01', 'KP-01.TP-1', 1, 5, 'B-Aufnahme')",
        (MANDANT_B,))
```

- [x] **Step 3: Failing test schreiben** (`tests/test_db_fixture.py`) — ERLEDIGT 25.08.

Die DDL gibt es noch nicht — deshalb baut dieser Test das Gerüst OHNE sie
(`mit_ddl=False`) und prüft nur BC0-Seite und Rechte.

```python
import pytest

from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")


def test_geruest_hat_beide_mandanten_mit_kollidierenden_ids():
    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, "bc1_role") as conn:
        treffer = conn.execute(
            "SELECT company_id, sub_process_name FROM ref_teilprozesse "
            "WHERE sub_process_id = 'KP-01.TP-1'").fetchall()
    assert {str(z[0]) for z in treffer} == {MANDANT_A, MANDANT_B}
    assert {z[1] for z in treffer} == {"Erfassen A", "Erfassen B"}   # Inhalte trennbar


def test_bc1_role_liest_ref_prozesse_nicht_direkt_aber_ueber_die_sicht():
    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, "bc1_role") as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("SELECT 1 FROM ref_prozesse").fetchone()
        assert "permission denied" in str(fehler.value).lower()
    with verbindung(DSN, "bc1_role") as conn:
        zeilen = conn.execute(
            "SELECT process_id FROM v_prozesse_lesen WHERE company_id = %s ORDER BY 1",
            (MANDANT_A,)).fetchall()
    assert [z[0] for z in zeilen] == ["KP-01", "KP-02"]


def test_default_privileges_reproduzieren_den_bc_leser_automatismus():
    # Positivkontrolle fuer R14-I1: ohne explizites REVOKE bekommt bc_leser
    # SELECT auf JEDE neue Tabelle von bc1_role. Faellt dieser Test aus, ist der
    # spaetere ACL-Test (Task 4) wertlos, weil er nichts mehr beweisen kann.
    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, "bc1_role") as conn:
        conn.execute("CREATE TABLE bc1.leck_probe (x int)")
        conn.commit()
    with verbindung(DSN, None) as conn:
        darf = conn.execute(
            "SELECT has_table_privilege('bc_leser', 'bc1.leck_probe', 'SELECT')"
        ).fetchone()[0]
    assert darf is True
```

- [x] **Step 4: Tests laufen lassen (RED)** — ERLEDIGT 25.08.: `ModuleNotFoundError:
      No module named 'tests.db_fixture'` (genau der vorhergesagte RED, vor Step 1/2).

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_db_fixture.py -v
```

Erwartet: FAIL — `ModuleNotFoundError: tests.db_fixture` bzw. fehlende SQL-Datei,
je nachdem, welche Datei zuerst entsteht. Erst RED sehen, dann Step 1/2 fertigstellen.

- [x] **Step 5: Tests laufen lassen (GREEN)** — ERLEDIGT 25.08.: 3 passed;
      volle Suite `248 passed, 4 skipped` (Basis 245 + 3 neue, keine Regression).

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_db_fixture.py -v
```

Erwartet: alle Fixture-Tests grün. Danach die volle Suite.

- [x] **Step 6: Commit** — ERLEDIGT 25.08.

```bash
git add bc1-context-discovery/tests/db/bc0_geruest.sql bc1-context-discovery/tests/db_fixture.py bc1-context-discovery/tests/test_db_fixture.py
git commit -m "test(bc1): BC0-Testgeruest mit zwei Mandanten + Rollenmodell"
```

---

## Task 3: DDL — Vertragstabellen, Trigger, Indizes

**Files:**
- Create: `bc1_service/db/prozessprofil.sql` (Abschnitte 0 und 2; Abschnitte 1, 3, 4 kommen in Task 4)
- Create: `tests/test_ddl_trigger.py`

**Interfaces:**
- Consumes: `tests/db_fixture.py` (Task 2).
- Produces: Schema-Objekte `bc1.prozessprofil`, `bc1.profil_rollen`,
  `bc1.profil_write_status` samt Triggern — der Writer (Phase D) verlässt sich auf:
  - `profil_version` vergibt die DB (`INSERT ... RETURNING profil_version`),
  - höchstens eine `in_erhebung`-Zeile je `(company_id, focus_step_id)`,
  - `fertig`-Zeilen sind gegen UPDATE/DELETE gesperrt (Kaskade ausgenommen).

**Wichtig:** Die Datei enthält **kein** `BEGIN`/`COMMIT`. Sie wird als EINE Transaktion
eingespielt (`psql -1` bzw. psycopg ohne autocommit) — eigene Transaktionsbefehle würden
die Atomarität der Dreifallregel (Task 4) zerstören.

- [x] **Step 1: Failing tests schreiben** (`tests/test_ddl_trigger.py`) — ERLEDIGT 25.08.
      (zwei Tests kamen beim Bauen dazu, siehe Changelog Rev. 9)

```python
import threading

import pytest

from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

FINGERPRINT = "1.1+ctx-0000000000000000"


@pytest.fixture
def db():
    frische_db(DSN)
    return DSN


def _insert(conn, mandant=MANDANT_A, tp="KP-01.TP-1", status="in_erhebung",
            erhebung="E-2026-01", **spalten):
    namen = ["company_id", "focus_step_id", "profil_version", "process_id", "status",
             "erhebung_id", "paket_version", "profil", *spalten]
    werte = [mandant, tp, 1, tp[:5], status, erhebung, FINGERPRINT, "{}",
             *spalten.values()]
    platz = ", ".join(["%s"] * len(namen))
    return conn.execute(
        f"INSERT INTO bc1.prozessprofil ({', '.join(namen)}) VALUES ({platz}) "
        "RETURNING profil_version", werte).fetchone()[0]


def test_version_wird_von_der_db_vergeben_und_zaehlt_hoch(db):
    with verbindung(db) as conn:
        assert _insert(conn) == 1
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig' "
                     "WHERE focus_step_id = 'KP-01.TP-1'")
        assert _insert(conn) == 2          # uebergebene 1 wird ueberschrieben
        conn.commit()


def test_version_zaehlt_je_fokus_schritt_getrennt(db):
    with verbindung(db) as conn:
        assert _insert(conn, tp="KP-01.TP-1") == 1
        assert _insert(conn, tp="KP-01.TP-2") == 1
        conn.commit()


def test_nur_ein_draft_je_fokus_schritt(db):
    with verbindung(db) as conn:
        _insert(conn)
        with pytest.raises(Exception) as fehler:
            _insert(conn)
        assert "prozessprofil_hoechstens_ein_draft" in str(fehler.value)


def test_fertige_zeile_ist_gegen_update_gesperrt(db):
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("UPDATE bc1.prozessprofil SET profil = '{\"x\":1}'::jsonb")
        assert "eingefroren" in str(fehler.value)


def test_fertige_zeile_ist_gegen_delete_gesperrt_draft_nicht(db):
    with verbindung(db) as conn:
        _insert(conn, tp="KP-01.TP-1", status="fertig")
        _insert(conn, tp="KP-01.TP-2", status="in_erhebung")
        conn.commit()
    with verbindung(db) as conn:
        conn.execute("DELETE FROM bc1.prozessprofil WHERE focus_step_id = 'KP-01.TP-2'")
        conn.commit()                                   # Betriebsweg K5: erlaubt
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("DELETE FROM bc1.prozessprofil WHERE focus_step_id = 'KP-01.TP-1'")
        assert "eingefroren" in str(fehler.value)


def test_mandanten_kaskade_laeuft_durch_die_freeze_trigger(db):
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.commit()
    with verbindung(db, None) as conn:                  # BC0/Admin loescht den Mandanten
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 0


def test_rollen_zeilen_einer_fertigen_version_sind_gesperrt(db):
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, profil_version, "
            "pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')", (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute(
                "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
                "profil_version, pos, rolle_freitext) "
                "VALUES (%s, 'KP-01.TP-1', 1, 2, 'Praktikant')", (MANDANT_A,))
        assert "eingefroren" in str(fehler.value)


def test_rollen_freeze_serialisiert_gegen_parallelen_freeze(db):
    # R4-I7: Rollen-Trigger sperrt die Elternzeile (FOR UPDATE), bevor er den
    # Status liest. Ohne Sperre koennte die Rolle NACH dem Freeze durchrutschen.
    with verbindung(db) as conn:
        _insert(conn)
        conn.commit()
    ergebnisse: dict[str, Exception | None] = {}
    tor = threading.Barrier(2)

    def rolle_einfuegen():
        try:
            with verbindung(db) as conn:
                tor.wait(timeout=5)
                conn.execute(
                    "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
                    "profil_version, pos, rolle_id) "
                    "VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')", (MANDANT_A,))
                conn.commit()
            ergebnisse["rolle"] = None
        except Exception as fehler:                     # noqa: BLE001 — Testbeobachtung
            ergebnisse["rolle"] = fehler

    def freeze():
        try:
            with verbindung(db) as conn:
                conn.execute("SELECT 1 FROM bc1.prozessprofil "
                             "WHERE focus_step_id = 'KP-01.TP-1' FOR UPDATE")
                tor.wait(timeout=5)
                conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
                conn.commit()
            ergebnisse["freeze"] = None
        except Exception as fehler:                     # noqa: BLE001
            ergebnisse["freeze"] = fehler

    faeden = [threading.Thread(target=freeze), threading.Thread(target=rolle_einfuegen)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join(timeout=10)
    assert ergebnisse["freeze"] is None                 # der Freeze gewinnt
    assert ergebnisse["rolle"] is not None              # die Rolle prallt am Freeze ab
    assert "eingefroren" in str(ergebnisse["rolle"])


def test_zahlenspalten_weisen_nan_infinity_und_negativ_ab(db):
    for wert in ("NaN", "Infinity", "-1"):
        with verbindung(db) as conn:
            with pytest.raises(Exception) as fehler:
                _insert(conn, frequency_per_year=wert)
            assert "prozessprofil_zahlen_wertebereich" in str(fehler.value)


def test_fokus_schritt_muss_zum_prozess_gehoeren(db):
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute(
                "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
                "profil_version, process_id, status, erhebung_id, paket_version, profil) "
                "VALUES (%s, 'KP-01.TP-1', 1, 'KP-02', 'in_erhebung', 'E-2026-01', %s, '{}')",
                (MANDANT_A, FINGERPRINT))
        assert "prozessprofil_tp_gehoert_zu_kp" in str(fehler.value)


def test_kein_selbstbezug_bei_upstream(db):
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            _insert(conn, upstream_process_id="KP-01")
        assert "prozessprofil_upstream_kein_selbstbezug" in str(fehler.value)


def test_parallele_inserts_vergeben_verschiedene_versionen(db):
    # R3-I7: der Advisory-Lock im BEFORE-INSERT-Trigger serialisiert zwei
    # gleichzeitige Writer je (Mandant, Fokus-Schritt).
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.commit()
    versionen: list[int] = []
    tor = threading.Barrier(2)

    def einfuegen():
        with verbindung(db) as conn:
            tor.wait(timeout=5)
            versionen.append(_insert(conn, status="fertig"))
            conn.commit()

    faeden = [threading.Thread(target=einfuegen) for _ in range(2)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join(timeout=10)
    assert sorted(versionen) == [2, 3]          # keine Doppelvergabe


def test_kaskade_raeumt_auch_rollenzeilen(db):
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db, None) as conn:
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_teilprozess_eines_fremden_mandanten_wird_abgewiesen(db):
    # KP-02.TP-2 gibt es nur bei Mandant B — der Verbund-FK muss greifen.
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            _insert(conn, mandant=MANDANT_A, tp="KP-02.TP-2")
        assert "prozessprofil_teilprozess_fk" in str(fehler.value)


def test_triggerinduziertes_update_umgeht_den_freeze_nicht(db):
    # Codex R1-C2: die Kaskaden-Ausnahme gilt NUR fuer DELETE. Ein UPDATE aus
    # einem fremden Trigger heraus muss weiterhin am Freeze prallen.
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.execute("CREATE TABLE bc1.ausloeser (x int)")
        conn.execute(
            "CREATE FUNCTION bc1.tf_probe() RETURNS trigger LANGUAGE plpgsql AS "
            "$fn$ BEGIN UPDATE bc1.prozessprofil SET profil = '{\"x\":1}'::jsonb; "
            "RETURN NEW; END $fn$")
        conn.execute("CREATE TRIGGER tr_probe AFTER INSERT ON bc1.ausloeser "
                     "FOR EACH ROW EXECUTE FUNCTION bc1.tf_probe()")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("INSERT INTO bc1.ausloeser VALUES (1)")
        assert "eingefroren" in str(fehler.value)


def test_kaskade_laeuft_auch_unter_echter_rollentrennung(db):
    # R6-N6-C1: BC0 loescht Mandanten mit einem Konto, das auf bc1.* KEINE Rechte
    # hat. Gemessen: die FK-Kaskade laeuft mit den Rechten des Tabellen-
    # eigentuemers (bc1_role), der Rollen-Trigger kann prozessprofil also lesen.
    # Dieser Test haelt das fest — ein Superuser-DELETE wuerde es verdecken.
    with verbindung(db, None) as conn:
        conn.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles "
                     "WHERE rolname = 'bc0_loescher') THEN CREATE ROLE bc0_loescher; "
                     "END IF; END $$")
        conn.execute("GRANT SELECT, DELETE ON companies TO bc0_loescher")
        conn.execute("GRANT USAGE ON SCHEMA public TO bc0_loescher")
        conn.commit()
    with verbindung(db) as conn:
        # Reihenfolge zaehlt (Codex R7-N7-I1): erst Draft, dann Rollenzeile, DANN
        # einfrieren — in eine bereits fertige Version laesst der Rollen-Freeze
        # keine Zeile mehr hinein.
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute(
            "SELECT has_table_privilege('bc0_loescher', 'bc1.prozessprofil', 'SELECT')"
        ).fetchone()[0] is False                       # wirklich rechtelos
    with verbindung(db, "bc0_loescher") as conn:
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_fremdes_delete_auf_rollenzeile_einer_fertigen_version_prallt(db):
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("DELETE FROM bc1.profil_rollen")
        assert "eingefroren" in str(fehler.value)


def test_draft_loeschung_raeumt_die_rollenzeile_mit(db):
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.commit()
    with verbindung(db) as conn:                        # Betriebsweg K5
        conn.execute("DELETE FROM bc1.prozessprofil WHERE status = 'in_erhebung'")
        conn.commit()
    with verbindung(db) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_triggerinduziertes_delete_ohne_kaskade_prallt_am_freeze(db):
    # R5-N5-I2: die Ausnahme verlangt zusaetzlich, dass der companies-Elternsatz
    # schon weg ist. Ein fremdes Trigger-DELETE bei lebendem Mandanten muss also
    # scheitern — sonst waere der Freeze ueber jeden Trigger aushebelbar.
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.execute("CREATE TABLE bc1.ausloeser_del (x int)")
        conn.execute(
            "CREATE FUNCTION bc1.tf_probe_del() RETURNS trigger LANGUAGE plpgsql AS "
            "$fn$ BEGIN DELETE FROM bc1.prozessprofil; RETURN NEW; END $fn$")
        conn.execute("CREATE TRIGGER tr_probe_del AFTER INSERT ON bc1.ausloeser_del "
                     "FOR EACH ROW EXECUTE FUNCTION bc1.tf_probe_del()")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("INSERT INTO bc1.ausloeser_del VALUES (1)")
        assert "eingefroren" in str(fehler.value)


def test_dsgvo_kaskade_raeumt_ein_voll_befuelltes_profil(db):
    # LUECKE DER URSPRUENGLICHEN PLAN-TESTS (am Container gefunden, 25.08.):
    # die bisherigen Kaskaden-Tests liessen process_owner_rolle_id leer und
    # deckten damit nicht ab, was in Etappe 2 der Normalfall ist. Mit gesetztem
    # Rollenbezug UND einer profil_rollen-Zeile blockierte profil_rollen_rolle_fk
    # das DELETE — die DSGVO-Loeschung waere stillschweigend gescheitert.
    # Ursache: profil_rollen wird erst auf Kaskadentiefe 2 geraeumt, die
    # NO-ACTION-Pruefung beim Loeschen von mandant_rollen laeuft auf Tiefe 1.
    with verbindung(db) as conn:
        # ALLE sieben kreuzenden Referenzen gesetzt (Codex N9-I4): Prozess,
        # Teilprozess und Erhebung sind Pflicht, dazu owner_rolle, upstream,
        # downstream und eine profil_rollen-Zeile.
        _insert(conn, process_owner_rolle_id="R-01",
                upstream_process_id="KP-02", downstream_process_id="KP-02")
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db, None) as conn:
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_einzelne_mandant_rolle_bleibt_trotz_deferrable_geschuetzt(db):
    # Die Kur darf die Schutzwirkung nicht kosten: eine einzelne mandant_rollen-
    # Zeile, auf die eine Profilzeile zeigt, muss unloeschbar bleiben. Bei
    # DEFERRABLE INITIALLY DEFERRED schlaegt das erst beim COMMIT zu — deshalb
    # liegt der commit() INNERHALB des raises-Blocks.
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("DELETE FROM mandant_rollen WHERE company_id = %s "
                         "AND rolle_id = 'R-01'", (MANDANT_A,))
            conn.commit()
        assert "profil_rollen_rolle_fk" in str(fehler.value)


def test_unbekannte_rolle_id_wird_weiterhin_abgewiesen(db):
    # Codex N9-I4: die Behauptung "DEFERRED kostet keine Schutzwirkung" war
    # unbelegt. Bei INITIALLY DEFERRED schlaegt der FK erst beim COMMIT zu.
    with verbindung(db) as conn:
        _insert(conn)
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute(
                "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
                "profil_version, pos, rolle_id) "
                "VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-99')", (MANDANT_A,))
            conn.commit()
        assert "profil_rollen_rolle_fk" in str(fehler.value)


def test_kaskadentests_laufen_im_unguenstigsten_fall(db):
    # Diese Zusicherung ist der Grund, warum die Kaskaden-Tests etwas beweisen.
    # Beim DELETE FROM companies stehen die Kaskaden aller direkt referenzierenden
    # Tabellen in EINER Startqueue (Reihenfolge nach Triggername); was sie
    # ausloesen, wird HINTEN angehaengt. Feuert der bc1-Kaskadentrigger ZULETZT,
    # ist das der spaetestmoegliche Zeitpunkt, zu dem bc1-Zeilen verschwinden —
    # also der unguenstigste Fall. Am Container per Vorhersage bestaetigt:
    # bc1 zuletzt => profil_rollen_rolle_fk blockte (vor dem DEFERRABLE-Fix),
    # bc1 zuerst  => lief durch. Kippt diese Reihenfolge, testen die Kaskaden-
    # Tests nur noch den bequemen Fall — dann schlaegt hier Alarm.
    with verbindung(db, None) as conn:
        namen = conn.execute(
            "SELECT c.conrelid::regclass::text "
            "  FROM pg_constraint c JOIN pg_trigger t ON t.tgconstraint = c.oid "
            " WHERE c.confrelid = 'companies'::regclass AND c.contype = 'f' "
            "   AND t.tgrelid = 'companies'::regclass "
            " ORDER BY t.tgname").fetchall()
    assert namen, "keine companies-Kaskadentrigger gefunden"
    assert namen[-1][0] == "bc1.prozessprofil"


def test_fremder_teilprozess_wird_vom_verbund_fk_abgewiesen(db):
    # MANDANT_B hat KP-01.TP-1 ebenfalls — der Verbund-FK muss den Mandanten mitpruefen.
    with verbindung(db) as conn:
        _insert(conn, mandant=MANDANT_B, tp="KP-01.TP-1", erhebung="E-2026-09")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            _insert(conn, mandant=MANDANT_A, tp="KP-01.TP-1", erhebung="E-2026-09")
        assert "prozessprofil_erhebung_fk" in str(fehler.value)
```

- [x] **Step 2: Tests laufen lassen (RED)** — ERLEDIGT 25.08.: 20 errors,
      `FileNotFoundError` in `spiele_ddl_ein` — genau der vorhergesagte RED.

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_ddl_trigger.py -v
```

Erwartet: alle FAIL — `prozessprofil.sql` existiert nicht (`FileNotFoundError` in
`spiele_ddl_ein`).

- [x] **Step 3: DDL schreiben** (`bc1_service/db/prozessprofil.sql`) — ERLEDIGT 25.08.

```sql
-- BC1 Etappe 1 — Profil-Fundament. Zielstruktur nach Brief BC1->BC0 vom 22.08.
-- (Abschnitte 2 + 3) und BC0-Antwort vom 23.08. (Abschnitt 1).
--
-- Einspielen (EINE Transaktion, Rollback bei jedem Fehler):
--     psql -v ON_ERROR_STOP=1 -1 -f prozessprofil.sql
-- Die Datei enthaelt bewusst KEIN BEGIN/COMMIT.
--
-- Aufbau: 0 Voraussetzungen | 1 Vorpruefung (Task 4) | 2 Anlage
--         3 Rechte (Task 4)  | 4 Nachpruefung (Task 4)

-- ============================================================
-- 0. VORAUSSETZUNGEN — lieber eine klare Ansage als "permission denied"
-- ============================================================
DO $$
DECLARE fehlend text[] := '{}';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'bc1') THEN
        RAISE EXCEPTION 'Schema bc1 fehlt. BC0 legt es an (ROLLEN.md, Schritt 5).';
    END IF;
    IF NOT has_schema_privilege(current_user, 'bc1', 'CREATE') THEN
        RAISE EXCEPTION 'Rolle % darf im Schema bc1 nichts anlegen.', current_user;
    END IF;

    SELECT array_agg(t) INTO fehlend FROM unnest(ARRAY[
        'companies', 'ref_prozesse', 'ref_teilprozesse', 'mandant_rollen', 'ref_erhebungen'
    ]) AS t WHERE NOT has_table_privilege(current_user, t, 'REFERENCES');
    IF fehlend IS NOT NULL THEN
        RAISE EXCEPTION 'GRANT REFERENCES fehlt auf: %. Das ist das GRANT-Signal an BC0 '
                        '(Buendel-Frage #3).', array_to_string(fehlend, ', ');
    END IF;

    SELECT array_agg(t) INTO fehlend FROM unnest(ARRAY[
        'v_bewertung_aktuell', 'mandant_systeme', 'ref_teilprozesse', 'companies',
        'v_prozesse_lesen'
    ]) AS t WHERE NOT has_table_privilege(current_user, t, 'SELECT');
    IF fehlend IS NOT NULL THEN
        RAISE EXCEPTION 'GRANT SELECT fehlt auf: %.', array_to_string(fehlend, ', ');
    END IF;
END $$;

-- ============================================================
-- 2. ANLAGE — idempotent; im No-op-Fall aendert hier nichts etwas
-- ============================================================
CREATE TABLE IF NOT EXISTS bc1.prozessprofil (
    company_id                          uuid        NOT NULL,
    focus_step_id                       varchar(16) NOT NULL,
    profil_version                      integer     NOT NULL,
    process_id                          varchar(8)  NOT NULL,
    status                              text        NOT NULL,
    process_owner_rolle_id              text,
    upstream_process_id                 varchar(8),
    downstream_process_id               varchar(8),
    frequency_per_year                  numeric,
    executions_per_run                  numeric,
    total_duration_minutes              numeric,
    focus_step_duration_minutes         numeric,
    focus_step_duration_source          text,
    focus_step_duration_confidence_pct  integer,
    erhebung_id                         text        NOT NULL,
    paket_version                       text        NOT NULL,
    profil                              jsonb       NOT NULL,
    erstellt_am                         timestamptz NOT NULL DEFAULT now(),
    aktualisiert_am                     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT prozessprofil_pkey
        PRIMARY KEY (company_id, focus_step_id, profil_version),
    CONSTRAINT prozessprofil_version_positiv
        CHECK (profil_version >= 1),
    CONSTRAINT prozessprofil_status_werte
        CHECK (status IN ('in_erhebung', 'fertig')),
    CONSTRAINT prozessprofil_focus_step_muster
        CHECK (focus_step_id ~ '^KP-[0-9]{2}\.TP-[0-9]+$'),
    CONSTRAINT prozessprofil_process_muster
        CHECK (process_id ~ '^KP-[0-9]{2}$'),
    CONSTRAINT prozessprofil_tp_gehoert_zu_kp
        CHECK (focus_step_id LIKE process_id || '.%'),
    CONSTRAINT prozessprofil_upstream_kein_selbstbezug
        CHECK (upstream_process_id IS NULL OR upstream_process_id <> process_id),
    CONSTRAINT prozessprofil_downstream_kein_selbstbezug
        CHECK (downstream_process_id IS NULL OR downstream_process_id <> process_id),
    CONSTRAINT prozessprofil_duration_source_werte
        CHECK (focus_step_duration_source IS NULL
               OR focus_step_duration_source IN ('gemessen', 'geschaetzt', 'aus_system')),
    CONSTRAINT prozessprofil_confidence_bereich
        CHECK (focus_step_duration_confidence_pct IS NULL
               OR focus_step_duration_confidence_pct BETWEEN 0 AND 100),
    -- Weiche Zahlenpruefung (Klaerpunkt K-C mit BC2 offen): nicht negativ und
    -- endlich. In PostgreSQLs numeric-Ordnung sortiert NaN UEBER Infinity —
    -- '< Infinity' schliesst NaN damit mit aus; explizit dokumentiert, weil das
    -- gegenlaeufig zu float ist.
    CONSTRAINT prozessprofil_zahlen_wertebereich CHECK (
        (frequency_per_year IS NULL
            OR (frequency_per_year >= 0 AND frequency_per_year < 'Infinity'::numeric))
        AND (executions_per_run IS NULL
            OR (executions_per_run >= 0 AND executions_per_run < 'Infinity'::numeric))
        AND (total_duration_minutes IS NULL
            OR (total_duration_minutes >= 0 AND total_duration_minutes < 'Infinity'::numeric))
        AND (focus_step_duration_minutes IS NULL
            OR (focus_step_duration_minutes >= 0
                AND focus_step_duration_minutes < 'Infinity'::numeric))),

    CONSTRAINT prozessprofil_company_fk FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON DELETE CASCADE,
    CONSTRAINT prozessprofil_teilprozess_fk FOREIGN KEY (company_id, focus_step_id)
        REFERENCES ref_teilprozesse (company_id, sub_process_id),
    CONSTRAINT prozessprofil_prozess_fk FOREIGN KEY (company_id, process_id)
        REFERENCES ref_prozesse (company_id, process_id),
    CONSTRAINT prozessprofil_upstream_fk FOREIGN KEY (company_id, upstream_process_id)
        REFERENCES ref_prozesse (company_id, process_id),
    CONSTRAINT prozessprofil_downstream_fk FOREIGN KEY (company_id, downstream_process_id)
        REFERENCES ref_prozesse (company_id, process_id),
    CONSTRAINT prozessprofil_owner_rolle_fk FOREIGN KEY (company_id, process_owner_rolle_id)
        REFERENCES mandant_rollen (company_id, rolle_id),
    CONSTRAINT prozessprofil_erhebung_fk FOREIGN KEY (company_id, erhebung_id)
        REFERENCES ref_erhebungen (company_id, erhebung_id)
);

COMMENT ON TABLE bc1.prozessprofil IS
    'BC1-Prozessprofil je Fokus-Schritt und Version. Massgeblich fuer Gate 0 ist die '
    'juengste Zeile mit status=fertig (Brief 2.2). Nur bc1_role schreibt.';

-- Hoechstens EIN laufendes Interview je Fokus-Schritt (Brief 2.3, Regel 2).
CREATE UNIQUE INDEX IF NOT EXISTS prozessprofil_hoechstens_ein_draft
    ON bc1.prozessprofil (company_id, focus_step_id)
    WHERE status = 'in_erhebung';

CREATE TABLE IF NOT EXISTS bc1.profil_rollen (
    company_id     uuid        NOT NULL,
    focus_step_id  varchar(16) NOT NULL,
    profil_version integer     NOT NULL,
    pos            smallint    NOT NULL,
    rolle_id       text,
    rolle_freitext text,
    zeitanteil_pct integer,

    CONSTRAINT profil_rollen_pkey
        PRIMARY KEY (company_id, focus_step_id, profil_version, pos),
    CONSTRAINT profil_rollen_pos_positiv CHECK (pos > 0),
    CONSTRAINT profil_rollen_zeitanteil_bereich
        CHECK (zeitanteil_pct IS NULL OR zeitanteil_pct BETWEEN 0 AND 100),
    -- Brief Abschnitt 3 woertlich: "genau eine Quelle je Zeile — rolle_id
    -- gesetzt ODER rolle_freitext nicht-leer (getrimmt), nicht beides".
    -- Ein leerer/Whitespace-Freitext ist KEINE zweite Quelle und macht eine
    -- ID-Zeile deshalb nicht ungueltig (Codex R1-I6).
    CONSTRAINT profil_rollen_genau_eine_quelle CHECK (
        (rolle_id IS NOT NULL) <> (btrim(coalesce(rolle_freitext, '')) <> '')),
    CONSTRAINT profil_rollen_profil_fk
        FOREIGN KEY (company_id, focus_step_id, profil_version)
        REFERENCES bc1.prozessprofil (company_id, focus_step_id, profil_version)
        ON DELETE CASCADE,
    -- DEFERRABLE INITIALLY DEFERRED ist hier PFLICHT, nicht Geschmack — am
    -- Container gemessen (postgres:16, 25.08.): ohne die Verzoegerung blockiert
    -- dieser FK die DSGVO-Loeschkaskade. Grund: bei DELETE FROM companies wird
    -- mandant_rollen auf Kaskadentiefe 1 geraeumt und seine NO-ACTION-Pruefung
    -- sofort ausgewertet, waehrend profil_rollen erst auf Tiefe 2 verschwindet
    -- (companies -> prozessprofil -> profil_rollen). Die Verletzung ist also nur
    -- transient innerhalb der Loeschtransaktion. Gemessen:
    --   NO ACTION                     -> Kaskade BLOCKIERT
    --   DEFERRABLE INITIALLY IMMEDIATE-> Kaskade BLOCKIERT
    --   DEFERRABLE INITIALLY DEFERRED -> Kaskade laeuft, beide Schutzwirkungen bleiben
    -- Die Schutzwirkung kostet das nichts: eine einzelne mandant_rollen-Zeile,
    -- auf die ein Profil zeigt, bleibt unloeschbar (dann eben beim COMMIT), und
    -- eine unbekannte rolle_id wird weiterhin abgewiesen.
    -- FOLGE FUER ETAPPE 2 (Rollen-Writer): FK-Fehler schlagen beim COMMIT zu,
    -- nicht beim INSERT. Wer sie frueher sehen will, setzt nach dem Einfuegen
    -- SET CONSTRAINTS bc1.profil_rollen_rolle_fk IMMEDIATE.
    CONSTRAINT profil_rollen_rolle_fk FOREIGN KEY (company_id, rolle_id)
        REFERENCES mandant_rollen (company_id, rolle_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE UNIQUE INDEX IF NOT EXISTS profil_rollen_rolle_einmalig
    ON bc1.profil_rollen (company_id, focus_step_id, profil_version, rolle_id)
    WHERE rolle_id IS NOT NULL;

COMMENT ON TABLE bc1.profil_rollen IS
    'Rollen am Fokus-Schritt. Struktur ist abgenommen; befuellt wird sie erst in '
    'Etappe 2 (Rollen-Auswahl im Interview).';

-- Interne Session->Profil-Bindung. Gehoert BC1 allein (kein Fremdzugriff, s. Abschnitt 3).
CREATE TABLE IF NOT EXISTS bc1.profil_write_status (
    session_id     text        NOT NULL,
    company_id     uuid        NOT NULL,
    focus_step_id  varchar(16) NOT NULL,
    profil_version integer     NOT NULL,
    erstellt_am    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT profil_write_status_pkey PRIMARY KEY (session_id),
    CONSTRAINT profil_write_status_je_zeile
        UNIQUE (company_id, focus_step_id, profil_version),
    CONSTRAINT profil_write_status_profil_fk
        FOREIGN KEY (company_id, focus_step_id, profil_version)
        REFERENCES bc1.prozessprofil (company_id, focus_step_id, profil_version)
        ON DELETE CASCADE
);

COMMENT ON TABLE bc1.profil_write_status IS
    'Bindung Session -> Profilzeile. Lebt und stirbt mit ihrer Profilzeile (CASCADE). '
    'Interne Tabelle: ausschliesslich bc1_role, ausdruecklich NICHT in der '
    'Fremdschema-Lesematrix (siehe REVOKE in Abschnitt 3).';

-- ---------- Trigger-Funktionen ----------
CREATE OR REPLACE FUNCTION bc1.tf_version_vergeben() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE max_version integer;
BEGIN
    -- Serialisiert zwei gleichzeitige Writer je (Mandant, Fokus-Schritt), bevor
    -- sie dasselbe Maximum lesen koennen (R3-I7). Der Partialindex bleibt als
    -- zweite Verteidigungslinie.
    PERFORM pg_advisory_xact_lock(
        hashtext(NEW.company_id::text || '|' || NEW.focus_step_id));
    SELECT coalesce(max(profil_version), 0) INTO max_version
      FROM bc1.prozessprofil
     WHERE company_id = NEW.company_id AND focus_step_id = NEW.focus_step_id;
    NEW.profil_version := max_version + 1;    -- vergibt die DB, nicht der Writer
    NEW.erstellt_am := now();
    NEW.aktualisiert_am := now();
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION bc1.tf_freeze_profil() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- Definierte Ausnahme, ZWEI Bedingungen (Codex R1-C2 + R5-N5-I2):
    -- (1) verschachteltes DELETE — pg_trigger_depth() benennt aber nur die
    --     Verschachtelung, nicht die Ursache; ohne TG_OP wuerde sonst jedes
    --     triggerinduzierte UPDATE den Freeze umgehen;
    -- (2) der Elternsatz in companies ist bereits weg. Das ist der fehlende
    --     Ursachen-Nachweis: bei der DSGVO-Loeschkaskade ist die companies-Zeile
    --     im selben Statement schon geloescht, bei jedem anderen Trigger-DELETE
    --     steht sie noch. Ein fremdes Trigger-DELETE prallt damit am Freeze ab.
    --     AM CONTAINER GEMESSEN (postgres:16): Kaskade depth=2/eltern=weg,
    --     fremder Trigger depth=2/eltern=da, direkter DELETE depth=1.
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
       AND NOT EXISTS (SELECT 1 FROM companies
                        WHERE company_id = OLD.company_id) THEN
        RETURN OLD;
    END IF;

    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'fertig' THEN
            RAISE EXCEPTION 'bc1.prozessprofil %/% ist eingefroren (DELETE abgewiesen)',
                OLD.focus_step_id, OLD.profil_version USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN OLD;                                   -- Draft loeschen ist erlaubt (K5)
    END IF;

    IF OLD.status = 'fertig' THEN
        RAISE EXCEPTION 'bc1.prozessprofil %/% ist eingefroren (UPDATE abgewiesen)',
            OLD.focus_step_id, OLD.profil_version USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.company_id <> OLD.company_id
       OR NEW.focus_step_id <> OLD.focus_step_id
       OR NEW.profil_version <> OLD.profil_version THEN
        RAISE EXCEPTION 'Identitaet einer Profilzeile ist unveraenderlich'
            USING ERRCODE = 'restrict_violation';
    END IF;
    NEW.aktualisiert_am := now();
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION bc1.tf_freeze_rollen() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_company uuid; v_step varchar(16); v_version integer; eltern_status text;
BEGIN
    -- Wie bei prozessprofil zwei Bedingungen: verschachteltes DELETE UND die
    -- referenzierte Profilzeile ist bereits weg (Kaskade Mandant bzw. Profil).
    -- INSERT/UPDATE aus einem Trigger heraus bleibt gesperrt (R1-C2, R5-N5-I2).
    -- RECHTE-FRAGE GEMESSEN (postgres:16, R6-N6-C1): Bei der FK-Kaskade fuehrt
    -- PostgreSQL die Aktion mit den Rechten des EIGENTUEMERS der referenzierenden
    -- Tabelle aus — der Trigger laeuft also als bc1_role, nicht als BC0s
    -- Loeschkonto. Ein Loeschkonto ohne jedes Recht auf bc1.* hat die Kaskade
    -- vollstaendig durchlaufen (0 Restzeilen); der SELECT hier scheitert nicht.
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
       AND NOT EXISTS (SELECT 1 FROM bc1.prozessprofil
                        WHERE company_id = OLD.company_id
                          AND focus_step_id = OLD.focus_step_id
                          AND profil_version = OLD.profil_version) THEN
        RETURN OLD;
    END IF;

    IF TG_OP = 'DELETE' THEN
        v_company := OLD.company_id; v_step := OLD.focus_step_id;
        v_version := OLD.profil_version;
    ELSE
        v_company := NEW.company_id; v_step := NEW.focus_step_id;
        v_version := NEW.profil_version;
    END IF;

    -- Elternzeile SPERREN, bevor ihr Status gelesen wird (R4-I7): sonst koennte
    -- eine Rollenzeile zwischen Statuspruefung und Freeze durchrutschen.
    SELECT status INTO eltern_status FROM bc1.prozessprofil
     WHERE company_id = v_company AND focus_step_id = v_step
       AND profil_version = v_version
       FOR UPDATE;

    IF eltern_status = 'fertig' THEN
        RAISE EXCEPTION 'bc1.profil_rollen zu %/%: Version ist eingefroren',
            v_step, v_version USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;

-- ---------- Trigger (CREATE OR REPLACE = echter No-op im Fall 2, ab PG 14) ----------
CREATE OR REPLACE TRIGGER tr_version_vergeben
    BEFORE INSERT ON bc1.prozessprofil
    FOR EACH ROW EXECUTE FUNCTION bc1.tf_version_vergeben();

CREATE OR REPLACE TRIGGER tr_freeze_profil
    BEFORE UPDATE OR DELETE ON bc1.prozessprofil
    FOR EACH ROW EXECUTE FUNCTION bc1.tf_freeze_profil();

CREATE OR REPLACE TRIGGER tr_freeze_rollen
    BEFORE INSERT OR UPDATE OR DELETE ON bc1.profil_rollen
    FOR EACH ROW EXECUTE FUNCTION bc1.tf_freeze_rollen();
```

- [x] **Step 4: Tests laufen lassen (GREEN)** — ERLEDIGT 25.08.: 22 passed;
      volle Suite `270 passed, 4 skipped`. **Zwischenstand war 18/2 rot** — der Befund
      zu `profil_rollen_rolle_fk` steht im Changelog Rev. 9.

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_ddl_trigger.py -v
```

Erwartet: alle Trigger-Tests grün.

**Die beiden Bedingungen der Freeze-Ausnahme sind am Container gemessen** (postgres:16,
25.08., nicht angenommen — die Messung stand vor dem Plan-Text):

| Fall | `pg_trigger_depth()` | `companies`-Elternsatz noch sichtbar? | Ergebnis |
|---|---|---|---|
| DSGVO-Löschkaskade | 2 | **nein** | läuft durch ✓ |
| fremdes Trigger-DELETE, Mandant lebt | 2 | ja | prallt am Freeze ✓ |
| direkter `DELETE` auf `fertig` | 1 | ja | prallt am Freeze ✓ |

Die Abfrage im Trigger sieht also die Wirkung des laufenden Statements — genau darauf
stützt sich Bedingung (2). Scheitert ein Kaskaden-Test trotzdem (andere PG-Version),
die Werte mit `RAISE NOTICE 'depth=% eltern=%'` nachmessen und den Befund melden,
**nicht** die Freeze-Regel aufweichen: Kaskade muss durch, direkter und fremder
Trigger-DELETE müssen prallen.

- [x] **Step 5: Commit** — ERLEDIGT 25.08.

```bash
git add bc1-context-discovery/bc1_service/db/prozessprofil.sql bc1-context-discovery/tests/test_ddl_trigger.py
git commit -m "feat(bc1): DDL Profil-Fundament — Vertragstabellen, Version, Freeze-Trigger"
```

---

## Task 4: DDL — Rechte, Sollsignatur, atomare Dreifallregel

**Ziel (Spec K1):** Das Skript läuft in EINER Transaktion und prüft den Ist-Zustand
**vor** jeder Änderung: (1) nichts da ⇒ Anlage · (2) exakt identisch ⇒ No-op ·
(3) Teilbestand oder irgendeine Abweichung ⇒ `RAISE`, Rollback, **keine Änderung**.

**Files:**
- Modify: `bc1_service/db/prozessprofil.sql` (Abschnitte 0b, 1, 3, 4 ergänzen)
- Create: `tests/test_ddl_einspielen.py`

**Interfaces:**
- Consumes: Abschnitt 2 aus Task 3.
- Produces: Einspielbarkeit nach Dreifallregel + normative Rechtelage:
  `bc1_role` = voll auf allen drei Tabellen; `bc_leser` und alle `bcN_role` = **nichts**
  (auch nicht über Vererbung), bis K-B beantwortet ist.

**Rechte-Entscheidung, bewusst eng (Spec K1 wörtlich: „bis dahin nur `bc1_role`"):**
BC0 vergibt über `ALTER DEFAULT PRIVILEGES` automatisch `SELECT` an `bc_leser` auf jede
neue Tabelle von `bc1_role` — auch auf `bc1.prozessprofil`. Wir nehmen das für **alle
drei** Tabellen explizit zurück, nicht nur für die interne. Gründe: (a) die exakte
Lese-Wertemenge ist Bündel-Frage #3 und noch offen, (b) die effektive ACL wird damit
unabhängig davon, ob im Zielsystem DEFAULT PRIVILEGES gesetzt sind — sonst hinge unser
No-op-Fall an einer fremden Einstellung. **Naht für K-B:** Sobald Simeon die Rollen
nennt, kommt genau eine `GRANT SELECT`-Zeile dazu und die Sollsignatur wird neu
generiert. Vor dem Supabase-Deploy ist das ohnehin fällig (Deploy-Gate).

- [ ] **Step 1: Failing tests schreiben** (`tests/test_ddl_einspielen.py`)

```python
import pytest

from tests.db_fixture import DSN, MANDANT_A, frische_db, spiele_ddl_ein, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

VERTRAGSTABELLEN = ("prozessprofil", "profil_rollen", "profil_write_status")


def _tabellen(conn) -> set[str]:
    return {z[0] for z in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'bc1'").fetchall()}


def _draft_anlegen(conn) -> None:
    conn.execute(
        "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, profil_version, "
        "process_id, status, erhebung_id, paket_version, profil) "
        "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-01', "
        "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))


def test_fall_1_leere_db_legt_alle_vertragsobjekte_an():
    frische_db(DSN)                                   # spielt die DDL bereits ein
    with verbindung(DSN, None) as conn:
        assert set(VERTRAGSTABELLEN) <= _tabellen(conn)


def test_fall_2_zweiter_lauf_ist_ein_no_op_und_laesst_daten_stehen():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        _draft_anlegen(conn)
        conn.commit()
    spiele_ddl_ein(DSN)                               # zweiter Lauf, identischer Bestand
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 1


def test_fall_3_teilbestand_bricht_ab_ohne_etwas_zu_aendern():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("DROP TABLE bc1.profil_write_status")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Teilbestand" in str(fehler.value)
    with verbindung(DSN, None) as conn:
        assert "profil_write_status" not in _tabellen(conn)   # NICHTS angelegt


def test_fall_3_abweichende_spalte_bricht_ab_ohne_etwas_zu_aendern():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("ALTER TABLE bc1.prozessprofil ADD COLUMN fremd integer")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Sollsignatur" in str(fehler.value)
    assert "fremd" in str(fehler.value)                       # Diff nennt den Grund
    with verbindung(DSN, None) as conn:
        spalten = {z[0] for z in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'bc1' AND table_name = 'prozessprofil'").fetchall()}
    assert "fremd" in spalten                                 # unveraendert stehen geblieben


def _katalog_stempel():
    """Fingerabdruck des Katalogzustands: aendert sich bei JEDEM Rewrite."""
    with verbindung(DSN, None) as conn:
        return conn.execute(
            "SELECT (SELECT array_agg(p.xmin::text ORDER BY p.proname) "
            "          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "         WHERE n.nspname = 'bc1'), "
            "       (SELECT array_agg(t.xmin::text ORDER BY t.tgname) "
            "          FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "          JOIN pg_namespace n ON n.oid = c.relnamespace "
            "         WHERE n.nspname = 'bc1' AND NOT t.tgisinternal), "
            "       (SELECT array_agg(c.relacl::text ORDER BY c.relname) "
            "          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "         WHERE n.nspname = 'bc1' AND c.relkind = 'r'), "
            "       (SELECT array_agg(c.xmin::text ORDER BY c.relname) "
            "          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "         WHERE n.nspname = 'bc1'), "
            "       (SELECT array_agg(d.xmin::text ORDER BY d.objoid, d.objsubid) "
            "          FROM pg_description d JOIN pg_class c ON c.oid = d.objoid "
            "          JOIN pg_namespace n ON n.oid = c.relnamespace "
            "         WHERE n.nspname = 'bc1')").fetchone()


def test_fall_2_ruehrt_den_katalog_nicht_an():
    # Der eigentliche No-op-Nachweis (Codex R1-C1, erweitert R2-N-I1): CREATE OR
    # REPLACE, GRANT/REVOKE und COMMENT wuerden Katalogzeilen neu schreiben —
    # xmin von pg_class/pg_proc/pg_trigger/pg_description verriete es. Der
    # Nachweis ergaenzt den Kontrollfluss, er ersetzt ihn nicht.
    frische_db(DSN)
    vorher = _katalog_stempel()
    spiele_ddl_ein(DSN)
    assert _katalog_stempel() == vorher


def test_fall_3_nur_triggerfunktionen_ohne_tabellen_bricht_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("DROP TABLE bc1.profil_write_status, bc1.profil_rollen, "
                     "bc1.prozessprofil CASCADE")     # Funktionen bleiben stehen
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Teilbestand" in str(fehler.value)
    with verbindung(DSN, None) as conn:
        assert not set(VERTRAGSTABELLEN) & _tabellen(conn)     # nichts angelegt


@pytest.mark.parametrize("eingriff, spur", [
    ("ALTER TABLE bc1.prozessprofil DROP CONSTRAINT prozessprofil_confidence_bereich",
     "prozessprofil_confidence_bereich"),
    ("DROP INDEX bc1.prozessprofil_hoechstens_ein_draft",
     "prozessprofil_hoechstens_ein_draft"),
    ("CREATE OR REPLACE FUNCTION bc1.tf_freeze_profil() RETURNS trigger "
     "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$",
     "funktion|tf_freeze_profil"),
    ("GRANT SELECT ON bc1.profil_write_status TO bc2_role",
     "bc2_role"),
    ("REVOKE EXECUTE ON FUNCTION bc1.tf_freeze_profil() FROM PUBLIC",
     "funktion_acl|tf_freeze_profil"),
])
def test_fall_3_erkennt_jede_semantische_abweichung(eingriff, spur):
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute(eingriff)
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Sollsignatur" in str(fehler.value)
    assert spur in str(fehler.value)


def test_bc1_role_darf_alles_auf_den_drei_tabellen():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        for tabelle in VERTRAGSTABELLEN:
            for recht in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert conn.execute(
                    "SELECT has_table_privilege('bc1_role', %s, %s)",
                    (f"bc1.{tabelle}", recht)).fetchone()[0], f"{tabelle}/{recht}"


def test_fremde_bc_rollen_lesen_nichts_auch_nicht_ueber_bc_leser():
    # R14-I1: BC0s DEFAULT PRIVILEGES haetten bc_leser SELECT gegeben; die
    # Positivkontrolle in test_db_fixture.py beweist, dass der Automatismus wirkt.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        for rolle in ("bc_leser", "bc2_role", "bc3_role", "bc4_role"):
            for tabelle in VERTRAGSTABELLEN:
                assert not conn.execute(
                    "SELECT has_table_privilege(%s, %s, 'SELECT')",
                    (rolle, f"bc1.{tabelle}")).fetchone()[0], f"{rolle} sieht {tabelle}"
```

- [ ] **Step 2: Tests laufen lassen (RED)**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_ddl_einspielen.py -v
```

Erwartet: `test_fall_2/3/…` FAIL (kein Vorprüfungs-Block, keine Rechte-Sektion);
`test_fall_1` kann bereits PASSEN — Abschnitt 2 legt ja an. Das ist in Ordnung: die
neuen Regeln sind RED, das Bestehende bleibt grün.

- [ ] **Step 3: Abschnitt 0b (Signatur-Definition) in `prozessprofil.sql` einfügen** —
      direkt nach Abschnitt 0, VOR Abschnitt 2

```sql
-- ============================================================
-- 0b. SOLLSIGNATUR — was "identisch" bedeutet (Spec K1, Geltungsbereich: NUR bc1)
-- ============================================================
-- Erfasst alle semantisch wirksamen Definitionen unserer drei Vertragstabellen:
-- Spalten (Typ, Nullability, Default) · Constraints (inkl. CHECK-Ausdruck und
-- FK-Aktionen) · Indizes (inkl. Partialpraedikat) · Trigger (inkl. Definition) ·
-- Trigger-Funktionsrumpf · Eigentuemer · effektive Rechte.
-- Rechte auf BC0-Tabellen sind ausdruecklich NICHT Teil der Signatur — die vergibt
-- BC0; sonst haenge unser No-op-Fall an fremden Aenderungen.
-- Kein vorheriges DROP (Codex R2-N-C3): ein unqualifiziertes
-- 'DROP TABLE IF EXISTS bc1_soll_signatur' koennte eine gleichnamige PERMANENTE
-- Tabelle aus dem Suchpfad loeschen — also eine Aenderung VOR der Pruefung, genau
-- das, was die Dreifallregel verbietet. Lebensdauer: die beiden TEMP-TABELLEN
-- verschwinden mit dem Commit (ON COMMIT DROP), die TEMP VIEW erst mit der
-- Session (Views kennen ON COMMIT DROP nicht) — beide Einspielwege (psql -1 und
-- psycopg) beenden die Session direkt nach dem Commit.
CREATE TEMP TABLE bc1_soll_signatur (zeile text PRIMARY KEY) ON COMMIT DROP;

INSERT INTO pg_temp.bc1_soll_signatur (zeile) VALUES
-- << HIER die generierte Sollsignatur einsetzen (Step 6) >>
    ('platzhalter|wird|in|step6|ersetzt');

CREATE TEMP VIEW bc1_ist_signatur AS
SELECT format('spalte|%s|%s|%s|%s|%s|%s|%s', c.relname, a.attname,
              format_type(a.atttypid, a.atttypmod),
              CASE WHEN a.attnotnull THEN 'notnull' ELSE 'null' END,
              coalesce(pg_get_expr(d.adbin, d.adrelid), ''),
              coalesce(nullif(a.attidentity, ''), '-'),
              coalesce(nullif(a.attgenerated, ''), '-')) AS zeile
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
 WHERE n.nspname = 'bc1'
   AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND a.attnum > 0 AND NOT a.attisdropped
UNION ALL
SELECT format('constraint|%s|%s|%s', c.relname, con.conname,
              pg_get_constraintdef(con.oid))
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1'
   AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
SELECT format('index|%s|%s|%s', tablename, indexname, indexdef)
  FROM pg_indexes
 WHERE schemaname = 'bc1'
   AND tablename IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
SELECT format('trigger|%s|%s|%s|%s', c.relname, t.tgname,
              pg_get_triggerdef(t.oid), t.tgenabled)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1'
   AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND NOT t.tgisinternal
UNION ALL
-- Nicht nur der Rumpf: Sprache, SECURITY-Modus, Volatilitaet und die
-- Funktionskonfiguration gehoeren zur Semantik (Codex R1-I2).
SELECT format('funktion|%s(%s)->%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s',
              p.proname, pg_get_function_identity_arguments(p.oid),
              format_type(p.prorettype, NULL), l.lanname, p.prokind,
              p.prosecdef, p.proleakproof, p.provolatile, p.proisstrict,
              p.proretset, p.proparallel, pg_get_userbyid(p.proowner),
              coalesce(array_to_string(p.proconfig, ','), '-'), md5(p.prosrc))
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  JOIN pg_language l ON l.oid = p.prolang
 WHERE n.nspname = 'bc1'
   AND p.proname IN ('tf_version_vergeben', 'tf_freeze_profil', 'tf_freeze_rollen')
UNION ALL
-- Auch die Funktionsrechte gehoeren zur Signatur: EXECUTE liegt per Default bei
-- PUBLIC (Codex R3-N-I2). Fuer Trigger-Funktionen ist das folgenlos, aber es
-- gehoert sichtbar in die Sollsignatur statt unbemerkt zu driften.
SELECT format('funktion_acl|%s|%s|%s|%s', p.proname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  CROSS JOIN LATERAL aclexplode(
      coalesce(p.proacl, acldefault('f', p.proowner))) AS acl
 WHERE n.nspname = 'bc1'
   AND p.proname IN ('tf_version_vergeben', 'tf_freeze_profil', 'tf_freeze_rollen')
UNION ALL
SELECT format('eigentuemer|%s|%s', c.relname, pg_get_userbyid(c.relowner))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1'
   AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
-- Gesetzte Rechte VOLLSTAENDIG (Codex R1-I2): aclexplode listet JEDEN Grantee,
-- auch unerwartete und PUBLIC — eine feste Rollenliste haette zusaetzliche
-- Empfaenger uebersehen.
SELECT format('acl|%s|%s|%s|%s', c.relname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(
      coalesce(c.relacl, acldefault('r', c.relowner))) AS acl
 WHERE n.nspname = 'bc1'
   AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
-- Zusaetzlich die EFFEKTIVE Sicht (loest Rollenvererbung auf): so faellt auch
-- auf, wenn eine BC-Rolle ueber bc_leser an unsere Tabellen kaeme.
SELECT format('effektiv|%s|%s|%s', c.relname, r.rolname, priv)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace,
       pg_roles r,
       unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) AS priv
 WHERE n.nspname = 'bc1'
   AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND r.rolname IN ('bc1_role', 'bc_leser', 'bc2_role', 'bc3_role', 'bc4_role')
   AND has_table_privilege(r.oid, c.oid, priv);
```

- [ ] **Step 4: Abschnitt 1 (Vorprüfung) einfügen** — nach 0b, VOR Abschnitt 2

```sql
-- ============================================================
-- 1. VORPRUEFUNG — Dreifallregel, VOR jeder Aenderung (Spec K1)
-- ============================================================
CREATE TEMP TABLE bc1_einspiel_modus (modus text NOT NULL) ON COMMIT DROP;

DO $$
DECLARE vorhanden integer; abweichung text;
BEGIN
    -- Existenz ueber ALLE neun Vertragsobjekte, nicht nur die Tabellen
    -- (Codex R1-I2: drei verwaiste Triggerfunktionen bei null Tabellen waeren
    -- sonst als "nichts vorhanden" durchgegangen und still ergaenzt worden).
    SELECT count(*) INTO vorhanden FROM (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND c.relkind = 'r'
           AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
        UNION ALL
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'bc1'
           AND p.proname IN ('tf_version_vergeben', 'tf_freeze_profil',
                             'tf_freeze_rollen')
        UNION ALL
        SELECT 1 FROM pg_trigger t
          JOIN pg_class c ON c.oid = t.tgrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND NOT t.tgisinternal
           AND t.tgname IN ('tr_version_vergeben', 'tr_freeze_profil',
                            'tr_freeze_rollen')) alle;

    IF vorhanden = 0 THEN
        INSERT INTO pg_temp.bc1_einspiel_modus VALUES ('anlegen');
        RAISE NOTICE 'Fall 1: kein Vertragsobjekt vorhanden — vollstaendige Anlage.';
        RETURN;
    END IF;

    IF vorhanden <> 9 THEN
        -- Auch MEHR als neun ist Fall 3 (z. B. ein zusaetzliches Overload,
        -- Codex R2-N-I2) — nicht nur Teilbestand.
        RAISE EXCEPTION 'Fall 3: Teilbestand oder Mehrbestand — % statt 9 '
                        'Vertragsobjekte. Abbruch OHNE Aenderung.', vorhanden;
    END IF;

    SELECT string_agg(zeile, E'\n' ORDER BY zeile) INTO abweichung FROM (
        SELECT format('  - fehlt:  %s', zeile) AS zeile
          FROM (SELECT zeile FROM bc1_soll_signatur
                EXCEPT SELECT zeile FROM bc1_ist_signatur) a
        UNION ALL
        SELECT format('  + zuviel: %s', zeile)
          FROM (SELECT zeile FROM bc1_ist_signatur
                EXCEPT SELECT zeile FROM bc1_soll_signatur) b) diff;

    IF abweichung IS NOT NULL THEN
        RAISE EXCEPTION E'Fall 3: Bestand weicht von der Sollsignatur ab. Abbruch OHNE Aenderung.\n%',
                        abweichung;
    END IF;
    INSERT INTO pg_temp.bc1_einspiel_modus VALUES ('noop');
    RAISE NOTICE 'Fall 2: Bestand ist identisch zur Sollsignatur — No-op.';
END $$;
```

- [ ] **Step 5: Abschnitt 2 in den Einspiel-Guard wickeln (Fall 2 = echter No-op)**

`CREATE TABLE IF NOT EXISTS` ist ein No-op — `CREATE OR REPLACE FUNCTION`,
`CREATE OR REPLACE TRIGGER`, `COMMENT`, `REVOKE` und `GRANT` sind es **nicht**
(Codex R1-C1): sie schreiben den Katalog neu und nehmen dabei Sperren auf die
Tabellen. Im Fall 2 darf nichts davon laufen. Deshalb bekommen die **Abschnitte 2 und 3** eine
Klammer, die nur im Anlage-Fall öffnet (Abschnitt 4 bleibt draußen — er liest nur):

```sql
DO $einspielen$
BEGIN
    IF (SELECT modus FROM pg_temp.bc1_einspiel_modus) <> 'anlegen' THEN
        RAISE NOTICE 'Fall 2: Bestand identisch — es wird NICHTS ausgefuehrt.';
        RETURN;
    END IF;

    EXECUTE $ddl$ CREATE TABLE bc1.prozessprofil ( ... ) $ddl$;
    EXECUTE $ddl$ COMMENT ON TABLE bc1.prozessprofil IS '...' $ddl$;
    EXECUTE $ddl$ CREATE UNIQUE INDEX prozessprofil_hoechstens_ein_draft ... $ddl$;
    -- ... alle weiteren Anlage-Statements aus Step 3 in dieser Form ...
    EXECUTE $ddl$ CREATE FUNCTION bc1.tf_version_vergeben() RETURNS trigger
                  LANGUAGE plpgsql AS $fn$ ... $fn$ $ddl$;
    EXECUTE $ddl$ CREATE TRIGGER tr_version_vergeben BEFORE INSERT
                  ON bc1.prozessprofil FOR EACH ROW
                  EXECUTE FUNCTION bc1.tf_version_vergeben() $ddl$;

    -- Abschnitt 3 (Rechte) — dieselbe Klammer, gleiche Begruendung
    EXECUTE $ddl$ REVOKE ALL ON bc1.prozessprofil, bc1.profil_rollen,
                  bc1.profil_write_status FROM PUBLIC $ddl$;
    ...
END
$einspielen$;
```

Regeln für den Umbau:
- **Drei Quoting-Ebenen, drei Tags:** außen `$einspielen$`, je Statement `$ddl$`,
  Funktionsrümpfe `$fn$` (statt `$$`). Gleiche Tags dürfen sich nicht verschachteln.
- **`IF NOT EXISTS` / `OR REPLACE` entfallen** innerhalb der Klammer: Im Fall 1 ist
  garantiert nichts da, also darf schlicht `CREATE …` stehen. Das ist die schärfere
  Variante — ein unerwarteter Restbestand wird zum Fehler statt zur stillen Ersetzung.
- Die `RAISE NOTICE`-Zeilen bleiben, damit der Betrieb sieht, welcher Fall lief.

- [ ] **Step 6: Abschnitt 3 (Rechte) — INNERHALB des Guards — und Abschnitt 4
      (Nachprüfung, read-only) ans Dateiende**

⚠️ **Abschnitt 3 steht im `DO $einspielen$`-Block aus Step 5** (Codex R2-N-C2): `REVOKE`
und `GRANT` sind mutierende Statements und dürfen im Fall 2 nicht laufen. Der folgende
SQL-Text ist also der **Inhalt** der `EXECUTE $ddl$ … $ddl$`-Zeilen, nicht ein eigener
Abschnitt hinter dem Block. Nur Abschnitt 4 steht außerhalb — er liest ausschließlich.

```sql
-- ============================================================
-- 3. RECHTE — nur bc1_role; alles andere ausdruecklich weg (Spec K1, R14-I1)
-- ============================================================
REVOKE ALL ON bc1.prozessprofil, bc1.profil_rollen, bc1.profil_write_status
    FROM PUBLIC;

-- bc_leser bekommt SELECT ueber BC0s ALTER DEFAULT PRIVILEGES automatisch — ein
-- REVOKE nur von PUBLIC entfernt das NICHT (R14-I1). Deshalb explizit, und fuer
-- ALLE drei Tabellen (die Lese-Wertemenge ist Buendel-Frage #3, K-B).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
        EXECUTE 'REVOKE ALL ON bc1.prozessprofil, bc1.profil_rollen, '
                'bc1.profil_write_status FROM bc_leser';
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON bc1.prozessprofil, bc1.profil_rollen, bc1.profil_write_status TO bc1_role;

-- ============================================================
-- 4. NACHPRUEFUNG — der Bestand MUSS jetzt exakt der Sollsignatur entsprechen
-- ============================================================
DO $$
DECLARE abweichung text;
BEGIN
    IF (SELECT modus FROM pg_temp.bc1_einspiel_modus) <> 'anlegen' THEN
        RETURN;              -- Fall 2: die Vorpruefung hat schon verglichen
    END IF;
    SELECT string_agg(zeile, E'\n' ORDER BY zeile) INTO abweichung FROM (
        SELECT format('  - fehlt:  %s', zeile) AS zeile
          FROM (SELECT zeile FROM bc1_soll_signatur
                EXCEPT SELECT zeile FROM bc1_ist_signatur) a
        UNION ALL
        SELECT format('  + zuviel: %s', zeile)
          FROM (SELECT zeile FROM bc1_ist_signatur
                EXCEPT SELECT zeile FROM bc1_soll_signatur) b) diff;

    IF abweichung IS NOT NULL THEN
        RAISE EXCEPTION E'Nachpruefung fehlgeschlagen — Rollback.\n%', abweichung;
    END IF;
    RAISE NOTICE 'Sollsignatur bestaetigt.';
END $$;
```

- [ ] **Step 7: Sollsignatur EINMALIG generieren und einsetzen**

Die Sollsignatur wird nicht von Hand getippt (`pg_get_constraintdef` formatiert selbst),
sondern aus dem frisch angelegten Bestand erzeugt. Ablauf:

1. Platzhalterzeile in Abschnitt 0b stehen lassen, Datei mit ihr einspielen — die
   Nachprüfung schlägt fehl und **listet den kompletten Ist-Bestand als „+ zuviel"**.
   Bequemer ist der direkte Weg über eine Wegwerf-DB:

```bash
docker exec -i bc1-test-pg psql -U postgres -q <<'SQL'
SELECT format('    (%L),', zeile) FROM bc1_ist_signatur ORDER BY zeile;
SQL
```

   (Der Temp-View und die Modus-Tabelle leben nur in der Einspiel-Session — praktikabel ist deshalb: den
   `CREATE TEMP VIEW`-Block plus das `SELECT` in einer eigenen psql-Session gegen die
   bereits angelegte Test-DB laufen lassen.)

2. Ausgabe in Abschnitt 0b statt der Platzhalterzeile einsetzen, letztes Komma zu
   einem Semikolon machen.
3. `frische_db` + `spiele_ddl_ein` erneut laufen lassen: Fall 1 legt an, Fall 2 meldet
   `NOTICE: Fall 2 … No-op`.

**Betriebsregel (in SMOKE.md aufnehmen, Task 16):** Die Signatur ist an die
PostgreSQL-Version gebunden (Katalogtexte können sich zwischen Hauptversionen
unterscheiden). Bricht das Einspielen im Zielsystem mit reinen Formatierungsdiffs ab,
wird die Signatur **auf der Zielversion neu erzeugt, der Diff gelesen und bewusst
committet** — niemals die Prüfung abgeschaltet.

- [ ] **Step 8: Tests laufen lassen (GREEN)**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_ddl_einspielen.py tests/test_ddl_trigger.py -v
```

Erwartet: alle Tests beider Dateien grün. Danach volle Suite.

- [ ] **Step 9: Commit**

```bash
git add bc1-context-discovery/bc1_service/db/prozessprofil.sql bc1-context-discovery/tests/test_ddl_einspielen.py
git commit -m "feat(bc1): DDL-Rechte, Sollsignatur und atomare Einspiel-Dreifallregel"
```

---

# Phase B — Kern: Completion-Guard (K0) und Mandanten-Guard

> **Preis ehrlich benannt (Spec K0/K3):** Der Kern bekommt zwei fachliche Erweiterungen
> (`FieldSpec.identitaetskritisch` samt drittem Ausgang, `SessionState.company_id`) und
> eine mechanische (Parameter `company_id` an `process_turn`). Beides ist generisch —
> kein Use-Case-Wissen, kein BC1-Sonderfall. Das Toy-Paket bleibt in der
> **Completion-Semantik** unverändert (Flag defaultet auf `False`); Dienst- und
> State-Verhalten ändern sich dagegen auch für Toy (Mandanten-Guard gilt überall).

## Task 5: Typen, Paket-Flag, Dialog-Semantik, Serialisierung

**Files:**
- Modify: `bc1_core/types.py`, `bc1_core/package.py`, `bc1_core/dialog.py`,
  `bc1_core/serialize.py`
- Modify: `tests/test_dialog.py`, `tests/test_serialize.py`, `tests/test_types.py`

**Interfaces:**
- Produces (von Task 6/7 und Phase C/D konsumiert):
  - `bc1_core.types.SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET = "abgebrochen_ohne_identitaet"`
  - `bc1_core.types.Ergebnis` (`WEITER` / `FERTIG` / `ABGEBROCHEN_OHNE_IDENTITAET`)
  - `bc1_core.types.TERMINALE_STATUS: tuple[SessionStatus, ...]`
  - `bc1_core.types.SessionState.company_id: str | None = None`
  - `bc1_core.package.FieldSpec.identitaetskritisch: bool = False`
  - `bc1_core.dialog.Decision(ergebnis: Ergebnis, next_field: str | None = None)`
    (`done` entfällt ersatzlos)
  - `bc1_core.dialog.GRUND_IDENTITAET_UNGEKLAERT = "identitaet_ungeklaert"`

- [ ] **Step 1: Failing tests schreiben** — neue Fälle in `tests/test_dialog.py`

```python
from bc1_core.dialog import GRUND_IDENTITAET_UNGEKLAERT, Decision, decide_next
from bc1_core.types import Ergebnis, FieldStatus, FieldValue, SessionState
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.confidence import confidence_check

IDENT_PAKET = UseCasePackage(
    name="ident_test", schema_version="0.1", max_rounds=3,
    fields=(
        FieldSpec("tp_id", "Welcher Schritt?",
                  validator=lambda v: v == "KP-01.TP-1", identitaetskritisch=True),
        FieldSpec("dauer", "Wie lange?"),
    ),
)


def _state(rounds=0, **werte):
    st = SessionState("s1", "0.1", paket_name="ident_test",
                      company_id="11111111-1111-1111-1111-111111111111")
    st.rounds = rounds
    for name, (wert, status, attempts) in werte.items():
        st.values[name] = FieldValue(value=wert, status=status,
                                     source_message_id="m1", attempts=attempts)
    return st


def test_identitaetskritisches_feld_wird_am_cap_nicht_aufgegeben():
    st = _state(tp_id=(None, FieldStatus.FEHLT, 5), dauer=("10", FieldStatus.GUELTIG, 1))
    d = decide_next(st, IDENT_PAKET, confidence_check(st, IDENT_PAKET))
    assert d.ergebnis is Ergebnis.WEITER
    assert d.next_field == "tp_id"
    assert st.values["tp_id"].status is not FieldStatus.UNGELOEST


def test_nicht_identitaetskritisches_feld_wird_am_cap_weiter_aufgegeben():
    st = _state(tp_id=("KP-01.TP-1", FieldStatus.GUELTIG, 1),
                dauer=(None, FieldStatus.FEHLT, 2))
    d = decide_next(st, IDENT_PAKET, confidence_check(st, IDENT_PAKET))
    assert st.values["dauer"].status is FieldStatus.UNGELOEST
    assert d.ergebnis is Ergebnis.FERTIG


def test_runden_limit_mit_offener_identitaet_bricht_definiert_ab():
    st = _state(rounds=3, tp_id=("Bestellung pruefen", FieldStatus.UNGUELTIG, 2),
                dauer=("10", FieldStatus.GUELTIG, 1))
    d = decide_next(st, IDENT_PAKET, confidence_check(st, IDENT_PAKET))
    assert d == Decision(Ergebnis.ABGEBROCHEN_OHNE_IDENTITAET, next_field="tp_id")


def test_runden_limit_mit_gueltiger_identitaet_wird_normal_fertig():
    st = _state(rounds=3, tp_id=("KP-01.TP-1", FieldStatus.GUELTIG, 1),
                dauer=(None, FieldStatus.FEHLT, 0))
    d = decide_next(st, IDENT_PAKET, confidence_check(st, IDENT_PAKET))
    assert d.ergebnis is Ergebnis.FERTIG
    assert st.values["dauer"].status is FieldStatus.UNGELOEST


def test_ungeloest_markierte_identitaet_kommt_zurueck_in_die_frageliste():
    # Fail-safe fuer Alt-Sessions: vor K0 konnte das Feld ungeloest werden.
    st = _state(rounds=0, tp_id=(None, FieldStatus.UNGELOEST, 2),
                dauer=("10", FieldStatus.GUELTIG, 1))
    d = decide_next(st, IDENT_PAKET, confidence_check(st, IDENT_PAKET))
    assert d.ergebnis is Ergebnis.WEITER
    assert d.next_field == "tp_id"
```

Und in `tests/test_serialize.py`:

```python
def test_company_id_ueberlebt_den_roundtrip():
    st = _beispiel_state()
    st.company_id = "11111111-1111-1111-1111-111111111111"
    assert state_from_dict(state_to_dict(st)).company_id == st.company_id


def test_alt_session_ohne_company_id_laedt_unveraendert():
    daten = state_to_dict(_beispiel_state())
    del daten["company_id"]                     # Stand vor dieser Aenderung
    assert state_from_dict(daten).company_id is None
```

- [ ] **Step 2: Bestandstests auf `ergebnis` umstellen**

`tests/test_dialog.py` prüft heute 8-mal `Decision(done=...)` bzw. `d.done`.
Mechanisch umschreiben: `Decision(done=True)` → `Decision(Ergebnis.FERTIG)` ·
`Decision(done=False, next_field=x)` → `Decision(Ergebnis.WEITER, next_field=x)` ·
`d.done is True` → `d.ergebnis is Ergebnis.FERTIG` · `d.done is False` →
`d.ergebnis is Ergebnis.WEITER`. Die Testnamen mit „done" bleiben, damit der Diff
klein bleibt.

- [ ] **Step 3: Tests laufen lassen (RED)**

```bash
.venv/bin/pytest tests/test_dialog.py tests/test_serialize.py -v
```

Erwartet: `ImportError: cannot import name 'Ergebnis'` bzw.
`TypeError: FieldSpec.__init__() got an unexpected keyword argument 'identitaetskritisch'`.

- [ ] **Step 4: `bc1_core/types.py` erweitern**

```python
class SessionStatus(str, Enum):
    AKTIV = "aktiv"
    WARTET = "wartet_auf_antwort"
    FERTIG = "fertig"
    FEHLER = "fehler_fortsetzbar"
    # Definiertes Ende, wenn die Prozess-Identitaet ungeklaert bleibt (Spec K0).
    # Terminal wie FERTIG — aber ohne Profil und ohne 503.
    ABGEBROCHEN_OHNE_IDENTITAET = "abgebrochen_ohne_identitaet"


# Zustaende, aus denen es keinen Weg zurueck gibt. Replay-Weiche (core) und
# Terminal-Gate (api) pruefen BEIDE, nie nur FERTIG.
TERMINALE_STATUS = (SessionStatus.FERTIG, SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET)


class Ergebnis(str, Enum):
    """Ausgang eines Turns. Ersetzt das frühere Decision.done (nur zwei Ausgänge)."""
    WEITER = "weiter"
    FERTIG = "fertig"
    ABGEBROCHEN_OHNE_IDENTITAET = "abgebrochen_ohne_identitaet"
```

Und in `SessionState` **direkt nach `paket_name`**:

```python
    # Mandanten-Bindung der Session (Spec K3, R11-C1). Wird beim ersten Turn
    # gesetzt und danach bei JEDEM Turn geprueft — der Paket-Fingerprint taugt
    # dafuer nicht, weil der Recovery-Replay ihn passieren darf.
    company_id: str | None = None
```

**Vor dem Einfügen prüfen** (alle bestehenden Aufrufe nutzen ab Position 3 Keywords —
sonst verschiebt das neue Feld eine Positionsangabe):

```bash
grep -rn "SessionState(" bc1_core bc1_service tests
```

- [ ] **Step 5: `bc1_core/package.py` erweitern**

```python
@dataclass(frozen=True)
class FieldSpec:
    name: str
    question: str
    required: bool = True
    validator: Callable[[str], bool] | None = None
    typ: Feldtyp = FREITEXT
    # Ohne gueltigen Wert gibt es kein Profil und keinen Abschluss (Spec K0).
    # Generisch: Pakete ohne solches Feld verhalten sich unveraendert.
    identitaetskritisch: bool = False
```

- [ ] **Step 6: `bc1_core/dialog.py` umbauen**

```python
from bc1_core.types import Ergebnis, FieldStatus, FieldValue, SessionState

GRUND_NACHFRAGE_LIMIT = "nachfrage_limit_erreicht"
GRUND_RUNDEN_LIMIT = "runden_limit_erreicht"
# Grund im Abbruch-Payload (Spec K0, Wire-Vertrag).
GRUND_IDENTITAET_UNGEKLAERT = "identitaet_ungeklaert"


@dataclass
class Decision:
    ergebnis: Ergebnis
    next_field: str | None = None


def _offene_identitaet(state: SessionState, package: UseCasePackage) -> str | None:
    """Erstes identitaetskritisches Pflichtfeld ohne gueltigen Wert."""
    for spec in package.required_fields():
        if not spec.identitaetskritisch:
            continue
        fv = state.values.get(spec.name)
        if fv is None or fv.status is not FieldStatus.GUELTIG:
            return spec.name
    return None


def decide_next(state: SessionState, package: UseCasePackage,
                conf: ConfidenceResult) -> Decision:
    identitaetsfelder = {s.name for s in package.required_fields()
                         if s.identitaetskritisch}
    offene_identitaet = _offene_identitaet(state, package)

    # Cap-Politik: ueber dem Limit -> als ungeloest markieren. Identitaets-
    # kritische Felder sind ausgenommen (Spec K0) — sie werden nie aufgegeben.
    for name in conf.offene_pflichtfelder:
        if name in identitaetsfelder:
            continue
        fv = state.values.get(name)
        if fv is not None and fv.attempts >= MAX_ATTEMPTS_PER_FIELD:
            fv.status = FieldStatus.UNGELOEST
            fv.grund = GRUND_NACHFRAGE_LIMIT

    offen = [n for n in conf.offene_pflichtfelder
             if state.values.get(n) is None
             or state.values[n].status is not FieldStatus.UNGELOEST]

    # Fail-safe: ein identitaetskritisches Feld darf nie aus der Frageliste
    # fallen — auch nicht in Alt-Sessions, in denen es schon ungeloest wurde.
    if offene_identitaet is not None and offene_identitaet not in offen:
        offen.insert(0, offene_identitaet)

    if state.rounds >= package.max_rounds:
        if offene_identitaet is not None:
            # Definiertes Ende statt Endlosschleife (Spec K0): kein Profil,
            # kein 503, klare Ansage. Die uebrigen Felder werden NICHT mehr
            # aufgegeben — es entsteht ohnehin kein Profil.
            return Decision(Ergebnis.ABGEBROCHEN_OHNE_IDENTITAET,
                            next_field=offene_identitaet)
        for name in offen:
            fv = state.values.get(name)
            if fv is None:
                fv = FieldValue()
                state.values[name] = fv
            fv.status = FieldStatus.UNGELOEST
            fv.grund = GRUND_RUNDEN_LIMIT
        return Decision(Ergebnis.FERTIG)

    if not offen:
        return Decision(Ergebnis.FERTIG)

    target = offen[0]
    fv = state.values.get(target)
    if fv is None:
        fv = FieldValue()
        state.values[target] = fv
    fv.attempts += 1
    return Decision(Ergebnis.WEITER, next_field=target)
```

- [ ] **Step 7: `bc1_core/serialize.py` erweitern**

In `state_to_dict` nach `"paket_name"`: `"company_id": state.company_id,`
In `state_from_dict`: `company_id=daten.get("company_id"),`
(`.get`, nicht `[...]` — Alt-Sessions kennen den Schlüssel nicht, R11-C1.)

- [ ] **Step 8: Tests laufen lassen (GREEN)**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q
```

Erwartet: `tests/test_core.py` und `tests/test_api.py` scheitern jetzt (sie nutzen
`decision.done` über `core.py`) — das ist Task 6/7. Alles andere grün.
**Wenn die Suite hier komplett grün ist, ist etwas faul** (dann greift `core.py` gar
nicht auf `done` zu — nachsehen, nicht weitermachen).

- [ ] **Step 9: Commit**

```bash
git add bc1-context-discovery/bc1_core bc1-context-discovery/tests/test_dialog.py bc1-context-discovery/tests/test_serialize.py
git commit -m "feat(bc1): Completion-Guard-Typen — Ergebnis, identitaetskritisch, company_id im State"
```

---

## Task 6: Kern — dritter Ausgang, Mandanten-Guard, Recovery-Ausnahme

**Files:**
- Modify: `bc1_core/core.py`, `bc1_core/cli.py`
- Modify: `tests/test_core.py` (51 Aufrufstellen), `tests/test_seam.py`,
  `tests/test_demo_durchlaeufe.py`, `tests/test_discovery_paket.py`,
  `tests/test_claude_llm.py`, `tests/test_gemini_llm.py`, `tests/test_ollama_llm.py`

**Interfaces:**
- Consumes: alles aus Task 5.
- Produces:
  - `process_turn(store, llm, package, session_id, message_id, message, *, company_id: str) -> dict`
  - `MandantKonfliktError(ValueError)`
  - `pruefe_mandant(state: SessionState, company_id: str) -> None`
  - `ist_terminal(state: SessionState) -> bool`
  - `darf_recovery_replay(state, package, message_id, mitgesendete_version: str | None = None) -> bool`
  - Antwort-Vertrag `{"status": "abgebrochen_ohne_identitaet",
    "payload": {"grund": "identitaet_ungeklaert", "feld": str,
    "pflicht_erfasst": int, "pflicht_gesamt": int}}`

- [ ] **Step 1: Testaufrufe mechanisch umstellen**

`process_turn` bekommt einen Pflichtparameter. Statt 51 Aufrufe einzeln zu ändern, in
`tests/test_core.py` einen Helfer einführen und die Aufrufe umbenennen:

```python
from bc1_core.core import (MandantKonfliktError, PaketKonfliktError, process_turn)

MANDANT = "11111111-1111-1111-1111-111111111111"


def _turn(store, llm, package, session_id, message_id, message,
          company_id=MANDANT, mitgesendete_version=None):
    """Testhelfer: process_turn mit Standard-Mandant."""
    return process_turn(store, llm, package, session_id, message_id, message,
                        company_id=company_id,
                        mitgesendete_version=mitgesendete_version)
```

Dann in derselben Datei alle Aufrufe `process_turn(` → `_turn(` ersetzen (der Import
und die Helfer-Definition bleiben unberührt). Analog in den übrigen Testdateien —
dort sind es 1–2 Stellen, die direkt `company_id=MANDANT` bekommen.

- [ ] **Step 2: Failing tests schreiben** (neu in `tests/test_core.py`)

```python
IDENT_PAKET = UseCasePackage(
    name="ident_test", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa", max_rounds=2,
    fields=(FieldSpec("tp_id", "Welcher Schritt?",
                      validator=lambda v: v == "KP-01.TP-1",
                      identitaetskritisch=True),),
)
MANDANT_B = "22222222-2222-2222-2222-222222222222"


class _WerfendesLLM(FakeLLM):
    def antworte(self, kontext):
        raise RuntimeError("LLM kaputt")


def test_runden_limit_ohne_identitaet_endet_im_abbruch_zustand():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, IDENT_PAKET, "s1", "m1", "keine ahnung")
    r = _turn(store, llm, IDENT_PAKET, "s1", "m2", "immer noch nicht")
    assert r["status"] == "abgebrochen_ohne_identitaet"
    assert r["payload"]["grund"] == "identitaet_ungeklaert"
    assert r["payload"]["feld"] == "tp_id"
    assert store.load("s1").status is SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET


def test_abbruch_kommt_ohne_llm_aus():
    # R8-I2: ein LLM-Ausfall darf den definierten Terminalzustand nicht in
    # fehler_fortsetzbar kippen. Gegenprobe im Frage-Turn: DORT schlaegt der
    # Ausfall wie gehabt durch (der Kern faengt ihn, Codex R2-N-I5).
    store = InMemoryStateStore()
    frage_turn = _turn(store, _WerfendesLLM(), IDENT_PAKET, "s1", "m1", "keine ahnung")
    assert frage_turn["status"] == "fehler_fortsetzbar"

    store2 = InMemoryStateStore()
    _turn(store2, FakeLLM(), IDENT_PAKET, "s1", "m1", "keine ahnung")
    r = _turn(store2, _WerfendesLLM(), IDENT_PAKET, "s1", "m2", "nein")
    assert r["status"] == "abgebrochen_ohne_identitaet"


def test_abbruch_replay_ist_idempotent():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, IDENT_PAKET, "s1", "m1", "a")
    erst = _turn(store, llm, IDENT_PAKET, "s1", "m2", "b")
    assert _turn(store, llm, IDENT_PAKET, "s1", "m2", "b") == erst


def test_mandanten_guard_weist_fremden_mandanten_immer_ab():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, TOY_PROZESS, "s1", "m1", "hallo")
    with pytest.raises(MandantKonfliktError):
        _turn(store, llm, TOY_PROZESS, "s1", "m2", "hallo", company_id=MANDANT_B)
    with pytest.raises(MandantKonfliktError):        # auch der bekannte Replay
        _turn(store, llm, TOY_PROZESS, "s1", "m1", "hallo", company_id=MANDANT_B)


def test_alt_session_ohne_company_id_wird_immer_abgewiesen():
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess"))   # company_id=None
    with pytest.raises(MandantKonfliktError):
        _turn(store, FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")


def test_company_id_liegt_schon_im_ersten_gespeicherten_stand():
    gesehen = []

    class _SpionStore(InMemoryStateStore):
        def save(self, state):
            gesehen.append(state.company_id)
            super().save(state)

    _turn(_SpionStore(), FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")
    assert gesehen and gesehen[0] == MANDANT          # schon beim Roh-Log-Save


def test_recovery_replay_passiert_den_paket_guard_nur_bei_ctx_abweichung():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, IDENT_PAKET, "s1", "m1", "a")
    erst = _turn(store, llm, IDENT_PAKET, "s1", "m2", "b")     # terminal
    alt_version = IDENT_PAKET.schema_version
    anderes_ctx = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    assert _turn(store, llm, anderes_ctx, "s1", "m2", "b",
                 mitgesendete_version=alt_version) == erst

    with pytest.raises(PaketKonfliktError):          # ohne Altversion kein Recovery
        _turn(store, llm, anderes_ctx, "s1", "m2", "b")

    andere_basis = replace(IDENT_PAKET, schema_version="1.2+ctx-bbbbbbbbbbbbbbbb")
    with pytest.raises(PaketKonfliktError):
        _turn(store, llm, andere_basis, "s1", "m2", "b",
              mitgesendete_version=alt_version)

    anderer_name = replace(anderes_ctx, name="fremd")
    with pytest.raises(PaketKonfliktError):
        _turn(store, llm, anderer_name, "s1", "m2", "b",
              mitgesendete_version=alt_version)
```

(`from dataclasses import replace` ergänzen — `UseCasePackage` ist frozen.)

- [ ] **Step 3: Tests laufen lassen (RED)**

```bash
.venv/bin/pytest tests/test_core.py -v
```

Erwartet: `TypeError: process_turn() got an unexpected keyword argument 'company_id'`.

- [ ] **Step 4: `bc1_core/core.py` umbauen**

```python
from bc1_core.types import (Ergebnis, FieldStatus, FieldValue, SessionState,
                            SessionStatus, TERMINALE_STATUS)
from bc1_core.dialog import GRUND_IDENTITAET_UNGEKLAERT, decide_next


class PaketKonfliktError(ValueError):
    """Session ist an ein anderes Paket / eine andere schema_version gebunden."""


class MandantKonfliktError(ValueError):
    """Session gehoert zu einem anderen Mandanten — oder zu gar keinem."""


def ist_terminal(state: SessionState) -> bool:
    return state.status in TERMINALE_STATUS


def pruefe_mandant(state: SessionState, company_id: str) -> None:
    """Ausnahmsloser Mandanten-Guard (Spec K3): laeuft nach JEDEM load als Erstes.

    Auch Alt-Sessions ohne gespeicherte company_id werden abgewiesen — sonst
    koennte nach einem A->B-Neustart eine Antwort aus Mandant A unter B sichtbar
    werden (R12-C1). Lieber ein abgewiesener Alt-Turn als ein Datenleck.
    """
    if state.company_id != company_id:
        raise MandantKonfliktError(
            f"Session {state.session_id} gehoert zu Mandant {state.company_id}, "
            f"der Aufruf kam mit {company_id}")


def _basis(schema_version: str) -> str:
    return schema_version.split("+", 1)[0]


def _ctx(schema_version: str) -> str:
    teile = schema_version.split("+", 1)
    return teile[1] if len(teile) > 1 else ""


def darf_recovery_replay(state: SessionState, package: UseCasePackage,
                         message_id: str,
                         mitgesendete_version: str | None) -> bool:
    """Eng begrenzte Ausnahme fuer den nachholenden Profil-Write (R13-I2).

    Alle VIER Bedingungen muessen gelten: gleicher Paketname, gleiche
    Basisversion, ausschliesslich abweichender ctx-Hash UND eine im Request
    mitgesendete alte schema_version, die zur Session passt. Fehlt die Version,
    gibt es KEIN Recovery (Codex R1-I1: 'None' waere die vierte Bedingung
    stillschweigend uebersprungen). Der Turn aendert per Definition nichts am
    Interview; er holt nur den Write nach. Die Mandanten-Pruefung ist davon
    ausdruecklich AUSGENOMMEN (R11-C1).
    """
    return (mitgesendete_version is not None
            and mitgesendete_version == state.schema_version
            and ist_terminal(state)
            and message_id in state.processed_message_ids
            and state.paket_name == package.name
            and _basis(state.schema_version) == _basis(package.schema_version)
            and _ctx(state.schema_version).startswith("ctx-")
            and _ctx(package.schema_version).startswith("ctx-"))


def process_turn(store: StateStore, llm: LLMClient, package: UseCasePackage,
                 session_id: str, message_id: str, message: str,
                 *, company_id: str,
                 mitgesendete_version: str | None = None) -> dict:
    # mitgesendete_version = die schema_version aus dem Request. Sie ist die
    # vierte Bedingung der Recovery-Ausnahme; Default None => kein Recovery.
    state = store.load(session_id)
    if state is None:
        # Mandanten-Bindung VOR dem ersten dauerhaften Speichern (R12-I1).
        state = SessionState(session_id, package.schema_version,
                             paket_name=package.name, company_id=company_id)
    else:
        pruefe_mandant(state, company_id)          # als ERSTES nach dem load

    if (state.schema_version != package.schema_version
            or state.paket_name not in (None, package.name)):
        if not darf_recovery_replay(state, package, message_id,
                                    mitgesendete_version):
            raise PaketKonfliktError(
                f"Session {session_id} laeuft mit Paket "
                f"{state.paket_name}/{state.schema_version}, Aufruf kam mit "
                f"{package.name}/{package.schema_version}")
```

Danach die drei bestehenden `SessionStatus.FERTIG`-Prüfungen auf `ist_terminal(state)`
umstellen (Replay-Weiche und `elif`-Zweig für neue Nachrichten an fertigen Sessions).

Turn-Ende:

```python
    state.rounds += 1
    try:
        vorher = werte_schnappschuss(state)
        extract_and_merge(state, message, message_id, package, llm)
        conf = confidence_check(state, package)
        decision = decide_next(state, package, conf)
        if decision.ergebnis is not Ergebnis.WEITER:
            conf = confidence_check(state, package)
        if decision.ergebnis is Ergebnis.ABGEBROCHEN_OHNE_IDENTITAET:
            # Kein llm.antworte() (R8-I2) und kein Abschlusskontext: ein
            # LLM-Ausfall darf diesen Terminalzustand nicht kippen.
            antwortetext = None
        else:
            kontext = baue_turn_kontext(message, vorher, state, package, conf,
                                        decision.next_field,
                                        decision.ergebnis is Ergebnis.FERTIG)
            antwortetext = llm.antworte(kontext)
    except Exception:
        state = store.load(session_id)
        pruefe_mandant(state, company_id)      # auch dieser load wird geprueft
        state.status = SessionStatus.FEHLER
        store.save(state)
        return {"status": "fehler_fortsetzbar",
                "payload": {"grund": "verarbeitung_fehlgeschlagen"}}

    pflicht = package.required_fields()
    erfasst = sum(1 for s in pflicht
                  if conf.statuses[s.name] is FieldStatus.GUELTIG)
    if decision.ergebnis is Ergebnis.ABGEBROCHEN_OHNE_IDENTITAET:
        state.status = SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET
        resp = {"status": "abgebrochen_ohne_identitaet",
                "payload": {"grund": GRUND_IDENTITAET_UNGEKLAERT,
                            "feld": decision.next_field,
                            "pflicht_erfasst": erfasst,
                            "pflicht_gesamt": len(pflicht)}}
    elif decision.ergebnis is Ergebnis.FERTIG:
        state.status = SessionStatus.FERTIG
        payload = _profil(state, conf, package)
        payload["abschluss_text"] = antwortetext
        payload["pflicht_erfasst"] = erfasst
        payload["pflicht_gesamt"] = len(pflicht)
        resp = {"status": "fertig", "payload": payload}
    else:
        state.status = SessionStatus.WARTET
        resp = {"status": "frage",
                "payload": {"naechste_frage": antwortetext,
                            "feld": decision.next_field,
                            "pflicht_erfasst": erfasst,
                            "pflicht_gesamt": len(pflicht)}}

    state.antworten[message_id] = resp
    store.save(state)
    return resp
```

- [ ] **Step 5: `bc1_core/cli.py` nachziehen**

`run_scripted()` ruft `process_turn()` heute ohne Mandant auf (Zeile 12) und würde
sonst mit `TypeError` sterben. Der CLI-Treiber ist ein Testwerkzeug — er bekommt einen
expliziten Parameter mit Demo-Vorbelegung:

```python
DEMO_MANDANT = "11111111-1111-1111-1111-111111111111"


def run_scripted(store, llm, package, session_id, nachrichten,
                 company_id: str = DEMO_MANDANT):
    ...
        out.append(process_turn(store, llm, package, session_id, message_id,
                                message, company_id=company_id))
```

`tests/test_seam.py` (nutzt den CLI-Treiber) entsprechend prüfen.

- [ ] **Step 6: Tests laufen lassen (GREEN)**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_core.py tests/test_seam.py -v
```

Erwartet: alle Kern-Tests grün (Bestand + 8 neue). `tests/test_api.py` bleibt rot
(Task 7).

- [ ] **Step 7: Commit**

```bash
git add bc1-context-discovery/bc1_core bc1-context-discovery/tests
git commit -m "feat(bc1): Kern — Abbruch ohne Identitaet, Mandanten-Guard, Recovery-Ausnahme"
```

---

## Task 7: Transportschicht — 409 `mandant_konflikt`, Terminal-Gate, Abbruch-Text

**Files:**
- Modify: `bc1_service/api.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: Task 6.
- Produces:
  - `create_app(store, llm, package, snapshot=None, lifespan=None, *, company_id: str)`
  - HTTP: `409 mandant_konflikt` · `409 session_abgeschlossen` (auch im
    Abbruch-Zustand) · `200` mit festem Abbruch-Text
  - `bc1_service.api.ABBRUCH_TEXT` (fester, LLM-freier Wortlaut)

- [ ] **Step 1: Failing tests schreiben** (`tests/test_api.py`)

```python
MANDANT = "11111111-1111-1111-1111-111111111111"
MANDANT_B = "22222222-2222-2222-2222-222222222222"

IDENT_PAKET = UseCasePackage(
    name="ident_test", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa", max_rounds=2,
    fields=(FieldSpec("tp_id", "Welcher Schritt?",
                      validator=lambda v: v == "KP-01.TP-1",
                      identitaetskritisch=True),),
)


def test_abbruch_liefert_200_mit_festem_text():
    client = TestClient(create_app(InMemoryStateStore(), FakeLLM(), IDENT_PAKET,
                                   company_id=MANDANT))
    _turn(client, "m1", "keine ahnung")
    antwort = _turn(client, "m2", "immer noch nicht")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "abgebrochen_ohne_identitaet"
    assert antwort.json()["chat_text"] == ABBRUCH_TEXT


def test_neue_nachricht_nach_abbruch_wird_abgewiesen():
    client = TestClient(create_app(InMemoryStateStore(), FakeLLM(), IDENT_PAKET,
                                   company_id=MANDANT))
    _turn(client, "m1", "a")
    _turn(client, "m2", "b")
    assert _turn(client, "m3", "c").status_code == 409


def test_abbruch_replay_liefert_dieselbe_antwort():
    client = TestClient(create_app(InMemoryStateStore(), FakeLLM(), IDENT_PAKET,
                                   company_id=MANDANT))
    _turn(client, "m1", "a")
    erst = _turn(client, "m2", "b").json()
    assert _turn(client, "m2", "b").json() == erst


def test_fremder_mandant_bekommt_409_mandant_konflikt():
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess",
                            company_id=MANDANT_B))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    antwort = _turn(client, "m1", "hallo")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "mandant_konflikt"


def test_fremder_mandant_wird_auch_bei_terminaler_session_abgewiesen():
    # Spec K4: A->B muss aktiv UND terminal greifen — ausdruecklich auch ohne
    # bestehende Profil-Bindung (R12-I1).
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess",
                            company_id=MANDANT_B, status=SessionStatus.FERTIG,
                            processed_message_ids={"m1"}, raw_log=[("m1", "hallo")],
                            antworten={"m1": {"status": "fertig", "payload": {}}}))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    for mid in ("m1", "m2"):                       # Replay UND neue Nachricht
        antwort = _turn(client, mid, "hallo")
        assert antwort.status_code == 409
        assert antwort.json()["detail"] == "mandant_konflikt"


def test_alt_session_ohne_company_id_bekommt_409():
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess",
                            status=SessionStatus.FERTIG,
                            processed_message_ids={"m1"}, raw_log=[("m1", "hallo")],
                            antworten={"m1": {"status": "fertig", "payload": {}}}))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    assert _turn(client, "m1", "hallo").status_code == 409


def test_recovery_replay_mit_alter_schema_version_geht_durch():
    store = InMemoryStateStore()
    llm = FakeLLM()
    client_alt = TestClient(create_app(store, llm, IDENT_PAKET, company_id=MANDANT))
    _turn(client_alt, "m1", "a")
    erst = _turn(client_alt, "m2", "b").json()

    neues_paket = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    client_neu = TestClient(create_app(store, llm, neues_paket, company_id=MANDANT))
    antwort = _turn(client_neu, "m2", "b", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == erst["status"]


def test_recovery_replay_mit_falscher_schema_version_bleibt_409():
    store = InMemoryStateStore()
    llm = FakeLLM()
    client_alt = TestClient(create_app(store, llm, IDENT_PAKET, company_id=MANDANT))
    _turn(client_alt, "m1", "a")
    _turn(client_alt, "m2", "b")
    neues_paket = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    client_neu = TestClient(create_app(store, llm, neues_paket, company_id=MANDANT))
    antwort = _turn(client_neu, "m2", "b", schema_version="1.1+ctx-cccccccccccccccc")
    assert antwort.status_code == 409
```

Alle bestehenden `create_app(...)`-Aufrufe in `tests/test_api.py` (3 Stellen) bekommen
`company_id=MANDANT`; die vier direkt gebauten `SessionState(...)` bekommen
`company_id=MANDANT`, sonst greift der Guard.

- [ ] **Step 2: Tests laufen lassen (RED)**

```bash
.venv/bin/pytest tests/test_api.py -v
```

Erwartet: `TypeError: create_app() got an unexpected keyword argument 'company_id'`.

- [ ] **Step 3: `bc1_service/api.py` umbauen**

```python
from bc1_core.core import (MandantKonfliktError, PaketKonfliktError,
                           darf_recovery_replay, ist_terminal, process_turn,
                           pruefe_mandant)

# Fester, LLM-freier Wortlaut (Spec K0): keine Halluzinationsflaeche im
# Terminalzustand, und der Text bleibt ueber Neustarts identisch.
ABBRUCH_TEXT = ("Wir konnten den Prozess-Schritt nicht eindeutig zuordnen. "
                "Bitte starten Sie neu und wählen Sie einen Schritt aus der Liste.")


def create_app(store: StateStore, llm: LLMClient, package: UseCasePackage,
               snapshot=None, lifespan=None, *, company_id: str) -> FastAPI:
    ...

    @app.post("/turn")
    def turn(req: TurnRequest) -> dict:
        with _session_lock(req.session_id):
            state = store.load(req.session_id)
            if state is not None:
                # Reihenfolge ist normativ (R12-I1): Mandanten-Guard VOR der
                # Schema-Ausnahme, vor der Replay-Auslieferung, vor dem
                # Terminal-Gate. Diese Pruefung kennt keine Ausnahme.
                try:
                    pruefe_mandant(state, company_id)
                except MandantKonfliktError:
                    raise HTTPException(status_code=409, detail="mandant_konflikt")

            recovery = state is not None and darf_recovery_replay(
                state, package, req.message_id, req.schema_version)

            if (req.schema_version is not None
                    and req.schema_version != package.schema_version
                    and not recovery):
                raise HTTPException(status_code=409,
                                    detail="schema_version_passt_nicht")

            if (state is not None and ist_terminal(state)
                    and req.message_id not in state.processed_message_ids):
                raise HTTPException(status_code=409, detail="session_abgeschlossen")

            try:
                antwort = process_turn(store, llm, package, req.session_id,
                                       req.message_id, req.message,
                                       company_id=company_id,
                                       mitgesendete_version=req.schema_version)
            except PaketKonfliktError:
                raise HTTPException(status_code=409, detail="paket_konflikt")
            except MandantKonfliktError:
                raise HTTPException(status_code=409, detail="mandant_konflikt")
            except StaleStateError:
                raise HTTPException(status_code=409, detail="gleichzeitige_anfrage")
            antwort["chat_text"] = _chat_text(antwort)
            return antwort
```

`_chat_text` bekommt einen Zweig **vor** dem Fehler-Fallback:

```python
    if antwort["status"] == "abgebrochen_ohne_identitaet":
        return ABBRUCH_TEXT           # bewusst ohne Fortschrittszeile: fester Text
```

- [ ] **Step 4: Tests laufen lassen (GREEN)**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q
```

Erwartet: volle Suite grün (Basis 245 + 3 Fixture + 12 Trigger + 6 Einspielen
+ 5 Dialog/Serialize + 7 Kern + 7 API ≈ 285). Reale Zahl notieren.

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_service/api.py bc1-context-discovery/tests/test_api.py
git commit -m "feat(bc1): Transport — Mandanten-Guard 409, Terminal-Gate, fester Abbruch-Text"
```

---

# Phase C — Paket-Schicht: Teilprozess-Auswahl, S-NN-Feldtyp, Startprüfung

## Task 8: BC0-Lesepfade (alle mandantengefiltert)

**Files:**
- Create: `bc1_service/bc0_lesepfade.py`
- Create: `tests/test_bc0_lesepfade.py`

**Interfaces:**
- Consumes: `tests/db_fixture.py`.
- Produces (freie Funktionen, `conn` zuerst — der Writer braucht sie später in
  SEINER Transaktion):
  - `mandant_existiert(conn, company_id: str) -> bool`
  - `teilprozesse(conn, company_id: str) -> list[tuple[str, str]]` — `(TP-ID, Name)`,
    sortiert nach TP-ID
  - `system_ids(conn, company_id: str) -> list[str]` — sortiert
  - `kp_existiert(conn, company_id: str, process_id: str) -> bool` — über
    `v_prozesse_lesen` (direktes `SELECT` auf `ref_prozesse` ist entzogen, R14-I2)

- [ ] **Step 1: Failing tests schreiben** (`tests/test_bc0_lesepfade.py`)

```python
import pytest

from bc1_service import bc0_lesepfade
from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")


@pytest.fixture(scope="module", autouse=True)
def db():
    frische_db(DSN)


def test_mandant_existiert_nur_fuer_bekannte_uuid():
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.mandant_existiert(conn, MANDANT_A) is True
        assert bc0_lesepfade.mandant_existiert(
            conn, "99999999-9999-9999-9999-999999999999") is False


def test_teilprozesse_liefern_nur_den_eigenen_mandanten():
    with verbindung(DSN) as conn:
        a = bc0_lesepfade.teilprozesse(conn, MANDANT_A)
        b = bc0_lesepfade.teilprozesse(conn, MANDANT_B)
    assert a == [("KP-01.TP-1", "Erfassen A"), ("KP-01.TP-2", "Pruefen A"),
                 ("KP-02.TP-1", "Bestellen A")]
    gemeinsam = {tp for tp, _ in a}
    assert gemeinsam <= {tp for tp, _ in b}                  # IDs kollidieren...
    assert dict(a) != dict(b)                                # ...die Inhalte nicht
    assert {tp for tp, _ in b} - gemeinsam == {"KP-02.TP-2"}  # B-exklusiv


def test_system_ids_sind_mandantengetrennt():
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.system_ids(conn, MANDANT_A) == ["S-01", "S-02"]
        assert bc0_lesepfade.system_ids(conn, MANDANT_B) == ["S-01", "S-03"]


def test_kp_existenz_laeuft_ueber_die_sicht_und_filtert_den_mandanten():
    # KP-03 gibt es NUR bei Mandant B — ein fehlender company_id-Filter faellt
    # nur mit so einer ID auf (ein nirgends existierendes 'KP-99' beweist nichts).
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_A, "KP-01") is True
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_B, "KP-03") is True
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_A, "KP-03") is False
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_A, "KP-99") is False
```

- [ ] **Step 2: RED**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_bc0_lesepfade.py -v
```

Erwartet: `ModuleNotFoundError: bc1_service.bc0_lesepfade`.

- [ ] **Step 3: `bc1_service/bc0_lesepfade.py` schreiben**

```python
"""Lesende Zugriffe auf BC0-Objekte. Genau die fuenf, die Etappe 1 braucht.

Normativ (Spec R5-I5): JEDER Lookup filtert ueber company_id. BC0 nutzt
zusammengesetzte Schluessel — IDs wie 'KP-01.TP-1' oder 'S-01' wiederholen sich
ueber Mandanten hinweg; ein fehlender Filter ist ein Datenleck.

Die Funktionen nehmen die VERBINDUNG als ersten Parameter: der S-NN-Sweep und der
Erhebungs-Lookup muessen in derselben Transaktion laufen wie der Profil-Write.
Kein voller Baseline-Lesepfad — der kommt in Etappe 2 (#148).
"""
from __future__ import annotations


def mandant_existiert(conn, company_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM companies WHERE company_id = %s", (company_id,)
    ).fetchone() is not None


def teilprozesse(conn, company_id: str) -> list[tuple[str, str]]:
    """(TP-ID, Schrittname) des Mandanten — Grundlage der statischen Auswahl (K2)."""
    return [(zeile[0], zeile[1]) for zeile in conn.execute(
        "SELECT sub_process_id, sub_process_name FROM ref_teilprozesse "
        "WHERE company_id = %s ORDER BY sub_process_id", (company_id,)).fetchall()]


def system_ids(conn, company_id: str) -> list[str]:
    """S-NN-Startmenge des Mandanten (Feldtyp-Grundlage und Sweep-Referenz)."""
    return [zeile[0] for zeile in conn.execute(
        "SELECT system_id FROM mandant_systeme "
        "WHERE company_id = %s ORDER BY system_id", (company_id,)).fetchall()]


def kp_existiert(conn, company_id: str, process_id: str) -> bool:
    """Existenzpruefung ueber v_prozesse_lesen — direktes SELECT auf ref_prozesse
    hat BC0 entzogen (R14-I2). Nur Existenz, kein Baseline-Lesepfad."""
    return conn.execute(
        "SELECT 1 FROM v_prozesse_lesen WHERE company_id = %s AND process_id = %s",
        (company_id, process_id)).fetchone() is not None
```

- [ ] **Step 4: GREEN + Commit**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_bc0_lesepfade.py -v
git add bc1-context-discovery/bc1_service/bc0_lesepfade.py bc1-context-discovery/tests/test_bc0_lesepfade.py
git commit -m "feat(bc1): BC0-Lesepfade mit normativem Mandantenfilter"
```

---

## Task 9: Paketlokaler S-NN-Feldtyp

**Warum ein Feldtyp und kein Validator (Spec R5-I2):** Der Extractor normalisiert
ausschließlich über `spec.typ.normalisiere()`. Ein `FieldSpec.validator` liefert nur
`bool` und **kann nicht kanonisieren** — `s-01` bliebe klein geschrieben im Profil
stehen und der Sweep würde es später nicht wiedererkennen.

**Files:**
- Create: `bc1_service/paket_feldtypen.py`
- Create: `tests/test_paket_feldtypen.py`

**Interfaces:**
- Produces:
  - `snn_tokens(text: str) -> list[str]` — kanonische Treffer (`S-01`), auch eingebettet
  - `kanonisiere_snn(text: str) -> str`
  - `entferne_snn(text: str, ids: Iterable[str]) -> str` — deterministische Entfernung
    inkl. Trimmen angrenzender Separatoren/Klammern (vom Sweep in Task 12 genutzt)
  - `baue_system_typ(bekannte_ids: frozenset[str]) -> Feldtyp`
  - `PROZENT_GANZ_0_100: Feldtyp` — Prozent **ohne Nachkommastelle**

**Warum ein zweiter Prozent-Typ (Codex R1-C4):** `focus_step_duration_confidence_pct`
ist laut Brief eine `integer`-Spalte (0–100). Der bestehende `PROZENT_0_100` lässt
aber `70,5` als **gültig** durch. Ein so abgeschlossenes Interview ließe sich nicht
schreiben — und weil die Session dann terminal ist, könnte der Nutzer es auch nicht
mehr korrigieren: Dauer-503. Genau davor warnt der Brief („Validator und Datenbank
müssen dieselbe Regel haben, sonst scheitert ein gültig abgeschlossenes Interview am
Schreiben"). Der Typ zieht die Regel an die Spalte heran: `70,5` wird `ungueltig` und
löst die normale Nachfrage aus.

- [ ] **Step 1: Failing tests schreiben** (`tests/test_paket_feldtypen.py`)

```python
from bc1_service.paket_feldtypen import (PROZENT_GANZ_0_100, baue_system_typ,
                                         entferne_snn, kanonisiere_snn, snn_tokens)

BEKANNT = frozenset({"S-01", "S-02"})


def test_erkennt_eingebettete_und_kleingeschriebene_ids():
    assert snn_tokens("SAP (s-01) und DATEV S-02") == ["S-01", "S-02"]
    assert snn_tokens("MS-01 ist kein Treffer") == []


def test_normalisierung_kanonisiert_und_wendet_listenregel_an():
    typ = baue_system_typ(BEKANNT)
    assert typ.normalisiere("sap (s-01),  datev") == "sap (S-01), datev"


def test_bekannte_id_ist_gueltig_unbekannte_nicht():
    typ = baue_system_typ(BEKANNT)
    assert typ.validator(typ.normalisiere("SAP (s-01)")) is True
    assert typ.validator(typ.normalisiere("Eigenbau (S-99)")) is False


def test_leerwert_scheitert_am_komponierten_listen_validator():
    typ = baue_system_typ(BEKANNT)
    assert typ.validator("") is False
    assert typ.validator("   ") is False


def test_freitext_ohne_id_bleibt_gueltig():
    typ = baue_system_typ(BEKANNT)
    assert typ.validator(typ.normalisiere("SAP, Excel")) is True


def test_prozent_ganz_lehnt_nachkommastellen_ab():
    typ = PROZENT_GANZ_0_100
    assert typ.validator(typ.normalisiere("70 %")) is True
    assert typ.normalisiere("70 %") == "70"
    assert typ.validator(typ.normalisiere("70,5")) is False    # sonst Dauer-503
    assert typ.validator(typ.normalisiere("101")) is False


def test_prozent_ganz_wirft_nie_auch_unnormalisiert():
    # Feldtyp-Vertrag: Validatoren sind total. '70,5' UNNORMALISIERT ist der
    # Stolperstein — PROZENT_0_100 haelt es fuer gueltig, Decimal wirft darauf.
    for roh in ("70,5", "abc", "", "1.234,5", "NaN", "-5", "1e400", "70%%"):
        assert typ_wirft_nicht(PROZENT_GANZ_0_100, roh)


def typ_wirft_nicht(typ, wert) -> bool:
    try:
        typ.validator(wert)
        typ.validator(typ.normalisiere(wert))
        return True
    except Exception:                                   # noqa: BLE001 — Testprobe
        return False


def test_entfernung_ist_deterministisch_und_trimmt_die_reste():
    assert entferne_snn("SAP (S-99)", ["S-99"]) == "SAP"
    assert entferne_snn("S-99", ["S-99"]) == ""
    assert entferne_snn("SAP (S-01), Excel (S-99)", ["S-99"]) == "SAP (S-01), Excel"
    assert entferne_snn("SAP (S-01)", ["S-99"]) == "SAP (S-01)"
```

- [ ] **Step 2: RED**

```bash
.venv/bin/pytest tests/test_paket_feldtypen.py -v
```

- [ ] **Step 3: `bc1_service/paket_feldtypen.py` schreiben**

```python
"""Paketlokale Feldtypen des Discovery-Pakets — Dienst-Ebene, kein Kern-Eingriff.

Feldtypen sind Paket-Bausteine (wie AUSWAHL): der Kern kennt nur das Protokoll
normalisiere/validator, nicht die Bedeutung.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from decimal import Decimal, InvalidOperation

from bc1_core.feldtypen import LISTE, PROZENT_0_100, Feldtyp

# Wortbegrenzt, damit 'MS-01' oder 'S-011' nicht faelschlich als Systemkennung
# gelesen werden. IGNORECASE, weil Nutzer 's-01' schreiben.
_SNN = re.compile(r"\bS-[0-9]{2}\b", re.IGNORECASE)


def snn_tokens(text: str) -> list[str]:
    """Alle Vorkommen in kanonischer Form (S-01), in Textreihenfolge."""
    return [treffer.upper() for treffer in _SNN.findall(text)]


def kanonisiere_snn(text: str) -> str:
    return _SNN.sub(lambda m: m.group(0).upper(), text)


def entferne_snn(text: str, ids: Iterable[str]) -> str:
    """Streicht die genannten Kennungen und raeumt die Reste auf.

    Deterministisch (Spec K3, Sweep): Token raus, danach leere Klammerpaare und
    ueberzaehlige Separatoren/Leerzeichen trimmen. Der Freitext-Name bleibt.
    """
    zu_entfernen = {kennung.upper() for kennung in ids}
    rest = _SNN.sub(
        lambda m: "" if m.group(0).upper() in zu_entfernen else m.group(0), text)
    rest = re.sub(r"\(\s*\)", "", rest)          # leere Klammern
    rest = re.sub(r"\[\s*\]", "", rest)
    rest = re.sub(r"\s{2,}", " ", rest)          # doppelte Leerzeichen
    rest = re.sub(r"\s+([,;])", r"\1", rest)     # Leerzeichen vor Trenner
    rest = re.sub(r"(^|,)\s*([,;])", r"\1", rest)
    return rest.strip(" ,;-").strip()


# Prozent OHNE Nachkommastelle: die Zielspalte ist integer (Brief Abschnitt 3).
# Ein 'gueltiges' 70,5 waere sonst nicht schreibbar und die fertige Session haenge
# dauerhaft im 503 (Codex R1-C4). Normalisierung wie PROZENT_0_100, nur die
# Pruefung ist strenger.
def _ist_ganzer_prozentwert(wert: str) -> bool:
    """TOTAL wie jeder Feldtyp-Validator: wirft nie (Codex R2-N-I3).

    Achtung: PROZENT_0_100.validator('70,5') ist WAHR — ein direktes
    Decimal('70,5') wuerde werfen. Deshalb intern erst normalisieren.
    """
    if not PROZENT_0_100.validator(wert):
        return False
    try:
        zahl = Decimal(PROZENT_0_100.normalisiere(wert))
    except (InvalidOperation, ValueError):
        return False
    return zahl == zahl.to_integral_value()


PROZENT_GANZ_0_100 = Feldtyp(
    name="prozent_ganz_0_100",
    validator=_ist_ganzer_prozentwert,
    normalisiere=PROZENT_0_100.normalisiere,
)


def baue_system_typ(bekannte_ids: frozenset[str]) -> Feldtyp:
    """Listen-Feldtyp, der S-NN kanonisiert UND gegen die Mandanten-Menge prueft."""
    def normalisiere(wert: str) -> str:
        return kanonisiere_snn(LISTE.normalisiere(wert))

    def validator(wert: str) -> bool:
        # Komposition explizit (R5-I2): ohne den LISTE-Validator schluepfte ein
        # Leerstring durch, weil er keine unbekannte ID enthaelt.
        return (LISTE.validator(wert)
                and all(token in bekannte_ids for token in snn_tokens(wert)))

    return Feldtyp(name="systeme", validator=validator, normalisiere=normalisiere)
```

- [ ] **Step 4: GREEN + Commit**

```bash
.venv/bin/pytest tests/test_paket_feldtypen.py -v
git add bc1-context-discovery/bc1_service/paket_feldtypen.py bc1-context-discovery/tests/test_paket_feldtypen.py
git commit -m "feat(bc1): paketlokaler S-NN-Feldtyp mit kanonisierender Normalisierung"
```

---

## Task 10: Discovery-Paket mit BC0-Kontext + Pflicht-Startprüfung

**Files:**
- Modify: `bc1_service/discovery_paket.py`, `bc1_service/paket_wahl.py`,
  `bc1_service/main.py`
- Create: `bc1_service/start.py`, `tests/test_start.py`
- Modify: `tests/test_discovery_paket.py`, `tests/test_paket_wahl.py`

**Interfaces:**
- Consumes: Task 8 (Lesepfade), Task 9 (Feldtyp), Task 5 (`identitaetskritisch`).
- Produces:
  - `bc1_service.discovery_paket.Bc0Kontext(company_id: str,
    teilprozesse: tuple[tuple[str, str], ...], system_ids: tuple[str, ...])`
  - `baue_discovery_paket(prozesse=None, kontext: Bc0Kontext | None = None) -> UseCasePackage`
    — mit Kontext: `schema_version = "1.1+ctx-<16hex>"`, `focus_step` als
    Teilprozess-Auswahl und `identitaetskritisch=True`, `focus_step_systems` mit
    S-NN-Feldtyp
  - `bc1_service.start.lies_company_id(umgebung) -> str`
  - `bc1_service.start.lade_kontext(conn, company_id) -> Bc0Kontext`

- [ ] **Step 1: Failing tests schreiben** (`tests/test_discovery_paket.py` ergänzen)

```python
import re
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket

KONTEXT = Bc0Kontext(
    company_id="11111111-1111-1111-1111-111111111111",
    teilprozesse=(("KP-01.TP-1", "Erfassen"), ("KP-01.TP-2", "Pruefen")),
    system_ids=("S-01", "S-02"))


def _feld(paket, name):
    return paket.field(name)


def test_mit_kontext_traegt_das_paket_den_ctx_fingerprint():
    paket = baue_discovery_paket(kontext=KONTEXT)
    assert re.fullmatch(r"1\.1\+ctx-[0-9a-f]{16}", paket.schema_version)


def test_fokus_schritt_ist_auswahl_und_identitaetskritisch():
    spec = _feld(baue_discovery_paket(kontext=KONTEXT), "focus_step")
    assert spec.identitaetskritisch is True
    assert spec.typ.validator("KP-01.TP-1") is True
    assert spec.typ.validator("Bestellung pruefen") is False
    assert spec.typ.normalisiere("kp-01.tp-2") == "KP-01.TP-2"
    assert "KP-01.TP-1 = Erfassen" in spec.question


def test_systemfeld_prueft_gegen_die_mandanten_menge():
    spec = _feld(baue_discovery_paket(kontext=KONTEXT), "focus_step_systems")
    assert spec.typ.validator(spec.typ.normalisiere("SAP (s-01)")) is True
    assert spec.typ.validator(spec.typ.normalisiere("Eigenbau (S-99)")) is False


def test_fingerprint_reagiert_auf_jede_grundlage_aber_nicht_auf_reihenfolge():
    basis = baue_discovery_paket(kontext=KONTEXT).schema_version
    gedreht = baue_discovery_paket(kontext=Bc0Kontext(
        KONTEXT.company_id, KONTEXT.teilprozesse[::-1], KONTEXT.system_ids[::-1]))
    assert gedreht.schema_version == basis                     # Inhalt zaehlt, nicht Reihenfolge
    for abweichung in (
        Bc0Kontext("22222222-2222-2222-2222-222222222222",
                   KONTEXT.teilprozesse, KONTEXT.system_ids),
        Bc0Kontext(KONTEXT.company_id, KONTEXT.teilprozesse[:1], KONTEXT.system_ids),
        Bc0Kontext(KONTEXT.company_id, KONTEXT.teilprozesse, ("S-01",)),
    ):
        assert baue_discovery_paket(kontext=abweichung).schema_version != basis


def test_kp_liste_bleibt_teil_der_paket_identitaet():
    ohne_kp = baue_discovery_paket(kontext=KONTEXT).schema_version
    mit_kp = baue_discovery_paket([("KP-01", "Auftrag")], kontext=KONTEXT).schema_version
    assert ohne_kp != mit_kp


def test_ohne_kontext_bleibt_alles_wie_bisher():
    paket = baue_discovery_paket()
    assert paket.schema_version == "1.0"
    assert paket.field("focus_step").identitaetskritisch is False


def test_konfidenz_prozent_ist_im_kontext_zweig_ganzzahlig():
    # Sonst waere '70,5' gueltig, aber nicht in die integer-Spalte schreibbar
    # (Codex R1-C4). Nur im Kontext-Zweig — der kontextfreie behaelt Semantik
    # UND Version 1.0 (Codex R2-N-I4).
    mit = baue_discovery_paket(kontext=KONTEXT).field(
        "focus_step_duration_confidence_pct").typ
    assert mit.validator(mit.normalisiere("70")) is True
    assert mit.validator(mit.normalisiere("70,5")) is False

    ohne = baue_discovery_paket().field(
        "focus_step_duration_confidence_pct").typ
    assert ohne.validator(ohne.normalisiere("70,5")) is True    # unveraendert
```

Und `tests/test_start.py`:

```python
import pytest

from bc1_service.start import lade_kontext, lies_company_id
from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung

def test_fehlende_company_id_ist_ein_startfehler():
    with pytest.raises(RuntimeError) as fehler:
        lies_company_id({})
    assert "BC1_COMPANY_ID" in str(fehler.value)


def test_unsinnige_company_id_ist_ein_startfehler():
    with pytest.raises(RuntimeError):
        lies_company_id({"BC1_COMPANY_ID": "mandant-1"})


def test_gueltige_uuid_wird_kleingeschrieben_durchgereicht():
    gross = "AAAAAAAA-1111-1111-1111-111111111111"
    assert lies_company_id({"BC1_COMPANY_ID": gross}) == gross.lower()


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_kontext_kommt_mandantengefiltert_aus_der_db():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        kontext = lade_kontext(conn, MANDANT_A)
    assert [tp for tp, _ in kontext.teilprozesse] == [
        "KP-01.TP-1", "KP-01.TP-2", "KP-02.TP-1"]
    assert kontext.system_ids == ("S-01", "S-02")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_unbekannter_mandant_ist_ein_startfehler():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, "99999999-9999-9999-9999-999999999999")
    assert "existiert nicht" in str(fehler.value)
```

- [ ] **Step 2: RED**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_discovery_paket.py tests/test_start.py -v
```

- [ ] **Step 3: `discovery_paket.py` erweitern**

```python
import json

from bc1_service.paket_feldtypen import PROZENT_GANZ_0_100, baue_system_typ

SCHEMA_VERSION = "1.0"
# Neue Basisversion, weil sich die BEDEUTUNG aendert: focus_step ist jetzt eine
# validierte Teilprozess-ID, focus_step_systems prueft gegen mandant_systeme.
SCHEMA_VERSION_CTX = "1.1"


@dataclass(frozen=True)
class Bc0Kontext:
    """Alles, was beim Dienststart einmalig aus BC0 geladen wird (Spec K2)."""
    company_id: str
    teilprozesse: tuple[tuple[str, str], ...]      # (TP-ID, Schrittname)
    system_ids: tuple[str, ...]


def _ctx_fingerprint(kontext: Bc0Kontext, kp_ids: list[str]) -> str:
    # Kanonisch, strukturiert, sortiert (Spec K2, R5-M7): gleiche Grundlagen =>
    # gleicher Wert, unabhaengig von Query-Reihenfolge.
    roh = json.dumps(
        {"company_id": kontext.company_id.lower(),
         "kp": sorted(kp_ids),
         "snn": sorted(kontext.system_ids),
         "tp": sorted(tp for tp, _ in kontext.teilprozesse)},
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(roh.encode()).hexdigest()[:16]


def baue_discovery_paket(prozesse=None, kontext: Bc0Kontext | None = None):
    ...  # B4-Zweig (KP-Auswahl) bleibt unveraendert
    if kontext is not None:
        e5_typ = AUSWAHL(*(tp for tp, _ in kontext.teilprozesse))
        e5_frage = ("Welcher Schritt kostet am meisten Zeit oder nervt am meisten? ("
                    + ", ".join(f"{tp} = {name}" for tp, name in kontext.teilprozesse)
                    + ")")
        f2_typ = baue_system_typ(frozenset(kontext.system_ids))
        # E4 ganzzahlig NUR im Kontext-Zweig (Codex R2-N-I4): geschrieben wird
        # ausschliesslich mit BC0-Kontext, und der Zweig traegt mit 1.1+ctx-
        # ohnehin eine neue Version. Der kontextfreie Zweig bleibt bei
        # PROZENT_0_100 — sonst aendert sich Semantik unter unveraenderter 1.0.
        e4_typ = PROZENT_GANZ_0_100
        schema_version = (f"{SCHEMA_VERSION_CTX}+ctx-"
                          f"{_ctx_fingerprint(kontext, [pid for pid, _ in (prozesse or [])])}")
    else:
        e5_typ, f2_typ, e4_typ = FREITEXT, LISTE, PROZENT_0_100
        e5_frage = ("Welcher Schritt kostet am meisten Zeit oder nervt am "
                    "meisten?")
        # schema_version bleibt der bestehende 1.0-Zweig
```

**Zusätzlich E4 auf den ganzzahligen Typ umstellen** (Codex R1-C4) — nur im
Kontext-Zweig, siehe `e4_typ` oben:

```python
            FieldSpec("focus_step_duration_confidence_pct",                  # E4
                      "Wie sicher ist diese Zeitangabe (0–100 %)?",
                      typ=e4_typ),
```

Die beiden Feldzeilen werden ersetzt:

```python
            FieldSpec("focus_step", e5_frage, typ=e5_typ,                    # E5
                      identitaetskritisch=kontext is not None),
            ...
            FieldSpec("focus_step_systems",                                  # F2
                      "Welche IT-Systeme oder Tools nutzen Sie in diesem "
                      "Schritt?", typ=f2_typ),
```

**Wichtig:** `identitaetskritisch` hängt bewusst am Kontext. Ohne BC0-Anbindung gibt
es keine Prozess-Identität, die man erzwingen könnte — der Guard würde nur einen
Freitext gegen sich selbst prüfen. Das ist keine Sonderlocke, sondern die ehrliche
Kopplung (und im Betrieb ist der Kontext ohnehin Pflicht, s. `start.py`).

- [ ] **Step 4: `bc1_service/start.py` schreiben**

```python
"""Startprüfungen des Dienstes. BC1_COMPANY_ID ist ab Etappe 1 PFLICHT (R13-I1):
ohne sie gaebe es Sessions ohne Mandanten-Bindung — und damit einen zweiten
Betriebsmodus neben dem ausnahmslosen Mandanten-Guard.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping

from bc1_service import bc0_lesepfade
from bc1_service.discovery_paket import Bc0Kontext


def lies_company_id(umgebung: Mapping[str, str]) -> str:
    roh = umgebung.get("BC1_COMPANY_ID", "").strip()
    if not roh:
        raise RuntimeError(
            "BC1_COMPANY_ID ist nicht gesetzt — der Dienst startet ohne "
            "Mandanten-Bindung nicht. Beispiel: "
            'export BC1_COMPANY_ID="11111111-1111-1111-1111-111111111111"')
    try:
        return str(uuid.UUID(roh))                 # normalisiert auf lowercase
    except ValueError as fehler:
        raise RuntimeError(
            f"BC1_COMPANY_ID='{roh}' ist keine UUID.") from fehler


def lade_kontext(conn, company_id: str) -> Bc0Kontext:
    if not bc0_lesepfade.mandant_existiert(conn, company_id):
        raise RuntimeError(
            f"Mandant {company_id} existiert nicht in companies — "
            "BC1_COMPANY_ID pruefen.")
    return Bc0Kontext(
        company_id=company_id,
        teilprozesse=tuple(bc0_lesepfade.teilprozesse(conn, company_id)),
        system_ids=tuple(bc0_lesepfade.system_ids(conn, company_id)))
```

- [ ] **Step 5: `paket_wahl.py` und `main.py` verdrahten**

```python
def waehle_paket(umgebung, prozesse=None, kontext=None) -> UseCasePackage:
    wahl = umgebung.get("BC1_PAKET", "discovery")
    if wahl == "discovery":
        return baue_discovery_paket(prozesse, kontext)
    ...
```

`main.py` (Docstring um `BC1_COMPANY_ID` als Pflicht ergänzen):

```python
from psycopg_pool import ConnectionPool

from bc1_service import bc0_lesepfade  # noqa: F401 — via start.py genutzt
from bc1_service.start import lade_kontext, lies_company_id

_company_id = lies_company_id(os.environ)

# Zweiter, kleiner Pool fuer die Profil-Seite. Der Session-Store behaelt seinen
# eigenen — kein Umbau am bewaehrten Store.
_profil_pool = ConnectionPool(_dsn, min_size=1, max_size=5, open=True)
with _profil_pool.connection() as _conn:
    _kontext = lade_kontext(_conn, _company_id)

app = create_app(
    _store,
    waehle_llm(os.environ),
    waehle_paket(os.environ, _prozesse, _kontext),
    _snapshot,
    lifespan=_lebenszyklus,
    company_id=_company_id,
)
```

und im Lebenszyklus zusätzlich `_profil_pool.close()`.

- [ ] **Step 6: GREEN**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q
```

Bestehende `test_paket_wahl.py`-Tests müssen weiter grün sein (Kontext ist optional).

- [ ] **Step 7: Commit**

```bash
git add bc1-context-discovery/bc1_service bc1-context-discovery/tests
git commit -m "feat(bc1): Teilprozess-Auswahl, S-NN-Feldtyp und Pflicht-Mandantenstart"
```

---

# Phase D — Profil-Writer

> **Reconcile-Modell (Spec K3):** Kein „Auslöser". Der Writer gleicht am Ende **jedes
> von der API zugelassenen Turns** Soll und Ist ab. Bei terminalen Sessions heißt das:
> nur bei Replays **bekannter** `message_id`s — neue Nachrichten weist das 409-Gate
> vorher ab, dann läuft kein Reconcile.

## Task 11: Profil-Bau — typisierte Spalten und JSON (ohne DB)

**Files:**
- Create: `bc1_service/profil_writer.py` (Bau-Teil)
- Create: `tests/test_profil_bau.py`
- Modify: `bc1_core/core.py` (privates `_profil` → öffentliches `profil_payload`)

**Interfaces:**
- Consumes: `bc1_core.confidence.confidence_check`, `bc1_core.core.profil_payload`.
- Produces:
  - `class ProfilWriteError(RuntimeError)` — im Terminal-Turn ⇒ HTTP 503
  - `Profilinhalt(focus_step_id: str, process_id: str, spalten: dict[str, object], profil: dict)`
  - `baue_profilinhalt(state, package, *, kp_bekannt: Callable[[str], bool]) -> Profilinhalt | None`
    (`None` = keine gültige Fokus-Schritt-ID ⇒ es entsteht kein Profil)

**Vollständige Spalte-zu-Feld-Tabelle (Spec K3, „Der Implementierungsplan trägt sie"):**

| Spalte | Interviewfeld | Regel |
|---|---|---|
| `company_id` | — | `BC1_COMPANY_ID` (Writer-Konfiguration) |
| `focus_step_id` | `focus_step` | nur wenn `gueltig`; sonst entsteht kein Profil |
| `process_id` | — | **abgeleitet**: Präfix der TP-ID (`focus_step_id[:5]`) |
| `profil_version` | — | vergibt der `BEFORE INSERT`-Trigger |
| `status` | — | `in_erhebung` bzw. `fertig` |
| `process_owner_rolle_id` | — | **immer `NULL`** in Etappe 1 (keine Rollen-Auswahl) |
| `upstream_process_id` | `upstream_process` | nur `gueltig` **und** kanonisch `^KP-\d{2}$` **und** in der Baseline vorhanden (`kp_bekannt`) **und** ≠ `process_id`; sonst `NULL` (Freitext bleibt im JSON) |
| `downstream_process_id` | `downstream_process` | wie `upstream_process_id` |
| `frequency_per_year` | `frequency_per_year` | `Decimal(str(...))` |
| `executions_per_run` | `executions_per_run` | `Decimal` |
| `total_duration_minutes` | `total_duration_minutes` | `Decimal` |
| `focus_step_duration_minutes` | `focus_step_duration_minutes` | `Decimal` |
| `focus_step_duration_source` | `focus_step_duration_source` | Text (`AUSWAHL`-normalisiert) |
| `focus_step_duration_confidence_pct` | `focus_step_duration_confidence_pct` | `int`; der Feldtyp `PROZENT_GANZ_0_100` (Task 9) lässt nur ganze Zahlen als `gueltig` durch — Validator und Spaltentyp tragen dieselbe Regel |
| `erhebung_id` | — | Lookup (Task 13) |
| `paket_version` | — | `state.schema_version` |
| `profil` | alle | JSON-Payload inkl. `befunde` |

**Konvertiert wird ausschließlich `status == gueltig`** (I6/R4-I5). Jeder andere Status
(`fehlt`/`ungueltig`/`unklar`/`ungeloest`) ergibt SQL `NULL` — auch wenn ein Roh-`value`
dasteht.

**Konvertierungsfehler — Lesart und ihre Voraussetzung (Codex R1-C4):** Die Spec sagt
„ein Konvertierungsfehler auf einem `gueltig`-Wert ist ein harter Fehler (Befund, kein
stilles NULL)". Dieser Plan setzt das als **`ProfilWriteError`** um (⇒ 503 im
Terminal-Turn) plus strukturiertem Log. Das ist **nur dann vertretbar, wenn kein
regulärer Nutzerwert dort landen kann** — sonst hinge eine fertige Session dauerhaft im
503, ohne Korrekturmöglichkeit. Genau deshalb bekommt E4 in Task 9/10 den ganzzahligen
Prozent-Typ: Danach ist ein Konvertierungsfehler nur noch bei einem echten Widerspruch
zwischen Validator und Spaltentyp möglich — also bei einem Fehler im Code, nicht in der
Eingabe. **Regel für künftige typisierte Spalten:** Erst den Feldtyp an die Spalte
angleichen, dann hart fehlschlagen lassen.

- [ ] **Step 1: Failing tests schreiben** (`tests/test_profil_bau.py`)

```python
from decimal import Decimal

import pytest

from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.feldtypen import AUSWAHL, MINUTEN, PROZENT_0_100, ZAHL
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_service.profil_writer import ProfilWriteError, baue_profilinhalt

PAKET = UseCasePackage(
    name="discovery", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa",
    fields=(
        FieldSpec("focus_step", "Welcher Schritt?", typ=AUSWAHL("KP-01.TP-1"),
                  identitaetskritisch=True),
        FieldSpec("process_id", "Welcher Kernprozess?", typ=AUSWAHL("KP-01", "KP-02")),
        FieldSpec("frequency_per_year", "Wie oft?", typ=ZAHL),
        FieldSpec("total_duration_minutes", "Wie lange?", typ=MINUTEN),
        FieldSpec("focus_step_duration_confidence_pct", "Wie sicher?",
                  typ=PROZENT_0_100),
        FieldSpec("upstream_process", "Was kommt davor?", required=False),
    ),
)


def _state(**werte):
    st = SessionState("s1", PAKET.schema_version, paket_name="discovery",
                      company_id="11111111-1111-1111-1111-111111111111")
    for name, (wert, status) in werte.items():
        st.values[name] = FieldValue(value=wert, status=status,
                                     source_message_id="m1")
    return st


def _bau(state, kp_bekannt=lambda kp: kp in {"KP-01", "KP-02"}):
    return baue_profilinhalt(state, PAKET, kp_bekannt=kp_bekannt)


def test_ohne_gueltige_tp_id_entsteht_kein_profil():
    assert _bau(_state(focus_step=("Bestellung", FieldStatus.UNGUELTIG))) is None


def test_identitaet_kommt_allein_aus_der_tp_id():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         process_id=("KP-02", FieldStatus.GUELTIG)))
    assert inhalt.focus_step_id == "KP-01.TP-1"
    assert inhalt.process_id == "KP-01"                       # Praefix schlaegt Interview
    assert inhalt.profil["befunde"]["kp_tp_diskrepanz"] == {
        "interview_kp": "KP-02", "abgeleiteter_kp": "KP-01"}


def test_ohne_diskrepanz_kein_befund():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         process_id=("KP-01", FieldStatus.GUELTIG)))
    assert "kp_tp_diskrepanz" not in inhalt.profil["befunde"]


def test_nur_gueltige_werte_landen_in_den_spalten():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         frequency_per_year=("120", FieldStatus.GUELTIG),
                         total_duration_minutes=("90", FieldStatus.UNKLAR)))
    assert inhalt.spalten["frequency_per_year"] == Decimal("120")
    assert inhalt.spalten["total_duration_minutes"] is None    # UNKLAR => NULL
    assert inhalt.spalten["process_owner_rolle_id"] is None     # Etappe 1


def test_zahlen_kommen_als_decimal_nie_als_float():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         frequency_per_year=("0.1", FieldStatus.GUELTIG)))
    assert isinstance(inhalt.spalten["frequency_per_year"], Decimal)


def test_upstream_nur_als_bekannte_kanonische_fremde_kp_id():
    def bau(wert, kp_bekannt=lambda kp: kp == "KP-02"):
        return _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                           upstream_process=(wert, FieldStatus.GUELTIG)),
                    kp_bekannt=kp_bekannt)
    assert bau("KP-02").spalten["upstream_process_id"] == "KP-02"
    assert bau("Wareneingang").spalten["upstream_process_id"] is None
    assert bau("KP-09").spalten["upstream_process_id"] is None       # nicht in Baseline
    assert bau("KP-01").spalten["upstream_process_id"] is None       # Selbstbezug


def test_unkonvertierbarer_gueltiger_wert_ist_ein_harter_fehler():
    # Konstruierter Widerspruch Validator<->Spaltentyp (im Discovery-Paket durch
    # PROZENT_GANZ_0_100 ausgeschlossen) — er MUSS laut werden, nicht still NULL.
    state = _state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                   focus_step_duration_confidence_pct=("70.5", FieldStatus.GUELTIG))
    with pytest.raises(ProfilWriteError):
        _bau(state)


def test_regulaeres_interview_kann_diesen_fehler_nicht_ausloesen():
    # Gegenprobe zum Test darueber: mit dem Paket-Feldtyp entsteht '70.5' gar
    # nicht erst als gueltig (Codex R1-C4).
    from bc1_service.paket_feldtypen import PROZENT_GANZ_0_100
    assert PROZENT_GANZ_0_100.validator(
        PROZENT_GANZ_0_100.normalisiere("70,5")) is False


@pytest.mark.parametrize("status", [FieldStatus.FEHLT, FieldStatus.UNGUELTIG,
                                    FieldStatus.UNKLAR, FieldStatus.UNGELOEST])
def test_jeder_nicht_gueltige_status_ergibt_null(status):
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         frequency_per_year=("120", status)))
    assert inhalt.spalten["frequency_per_year"] is None


def test_jede_typisierte_spalte_wird_belegt():
    # Vollstaendigkeitsprobe gegen die Mapping-Tabelle: keine Spalte darf
    # vergessen werden, sonst schreibt der Writer sie stumm nie.
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG)))
    assert set(inhalt.spalten) == {
        "process_owner_rolle_id", "upstream_process_id", "downstream_process_id",
        "frequency_per_year", "executions_per_run", "total_duration_minutes",
        "focus_step_duration_minutes", "focus_step_duration_source",
        "focus_step_duration_confidence_pct"}


def test_json_traegt_den_vollen_payload_inklusive_zaehler():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG)))
    assert set(inhalt.profil) >= {"felder", "vollstaendigkeit", "ungeloeste_felder",
                                  "pflicht_erfasst", "pflicht_gesamt",
                                  "schema_version", "befunde"}
    assert inhalt.profil["schema_version"] == PAKET.schema_version
```

- [ ] **Step 2: RED**

```bash
.venv/bin/pytest tests/test_profil_bau.py -v
```

- [ ] **Step 3: `bc1_core/core.py` — `_profil` öffentlich machen**

Reine Umbenennung `_profil` → `profil_payload` (eine Definition, ein Aufruf). Grund:
Der Writer braucht exakt dieselbe Payload-Form — zwei Quellen für dieselbe Regel wären
der sichere Weg in Divergenz.

- [ ] **Step 4: Bau-Teil von `bc1_service/profil_writer.py` schreiben**

```python
"""Profil-Writer: baut aus dem SessionState die Profilzeile und gleicht sie mit
der Datenbank ab (Reconcile-Modell, Spec K3).

Dieser Teil ist DB-frei und rein: Bau der typisierten Spalten und des JSON.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from bc1_core.confidence import confidence_check
from bc1_core.core import profil_payload
from bc1_core.package import UseCasePackage
from bc1_core.types import FieldStatus, SessionState

log = logging.getLogger(__name__)

KP_MUSTER = re.compile(r"^KP-[0-9]{2}$")

# Spalte -> (Feldname, Konverter). Nur gueltige Werte werden konvertiert.
_ZAHLENSPALTEN = {
    "frequency_per_year": "frequency_per_year",
    "executions_per_run": "executions_per_run",
    "total_duration_minutes": "total_duration_minutes",
    "focus_step_duration_minutes": "focus_step_duration_minutes",
}
_TEXTSPALTEN = {"focus_step_duration_source": "focus_step_duration_source"}
_GANZZAHLSPALTEN = {
    "focus_step_duration_confidence_pct": "focus_step_duration_confidence_pct"}


class ProfilWriteError(RuntimeError):
    """Profil konnte nicht geschrieben werden. Im Terminal-Turn => HTTP 503."""


@dataclass(frozen=True)
class Profilinhalt:
    focus_step_id: str
    process_id: str
    spalten: dict[str, object]
    profil: dict


def _gueltiger_wert(state: SessionState, feld: str) -> str | None:
    fv = state.values.get(feld)
    if fv is None or fv.status is not FieldStatus.GUELTIG:
        return None                       # jeder andere Status => SQL NULL (I6)
    return fv.value


def _dezimal(wert: str, feld: str) -> Decimal:
    try:
        return Decimal(wert)              # nie float — Rundung waere stillschweigend
    except InvalidOperation as fehler:
        raise ProfilWriteError(
            f"Feld {feld}: gueltiger Wert '{wert}' laesst sich nicht als numeric "
            "konvertieren — Validator und Spaltentyp widersprechen sich.") from fehler


def _ganzzahl(wert: str, feld: str) -> int:
    try:
        zahl = Decimal(wert)
        if zahl != zahl.to_integral_value():
            raise InvalidOperation(wert)
        return int(zahl)
    except InvalidOperation as fehler:
        raise ProfilWriteError(
            f"Feld {feld}: gueltiger Wert '{wert}' ist keine ganze Zahl.") from fehler


def _fremde_kp(state: SessionState, feld: str, process_id: str,
               kp_bekannt: Callable[[str], bool]) -> str | None:
    wert = _gueltiger_wert(state, feld)
    if wert is None or not KP_MUSTER.match(wert):
        return None                       # Freitext bleibt im JSON (Brief)
    if wert == process_id:                # DDL-CHECK: kein Selbstbezug
        return None
    return wert if kp_bekannt(wert) else None


def baue_profilinhalt(state: SessionState, package: UseCasePackage, *,
                      kp_bekannt: Callable[[str], bool]) -> Profilinhalt | None:
    focus_step_id = _gueltiger_wert(state, "focus_step")
    if focus_step_id is None:
        return None                       # keine Identitaet => kein Profil (Brief)

    # Identitaet allein aus der TP-ID (R4-C1): der DDL-CHECK
    # 'focus_step_id LIKE process_id||".%"' ist damit per Konstruktion erfuellt.
    process_id = focus_step_id.split(".", 1)[0]

    conf = confidence_check(state, package)
    profil = profil_payload(state, conf, package)
    pflicht = package.required_fields()
    profil["pflicht_erfasst"] = sum(
        1 for s in pflicht if conf.statuses[s.name] is FieldStatus.GUELTIG)
    profil["pflicht_gesamt"] = len(pflicht)
    profil["befunde"] = {}

    interview_kp = _gueltiger_wert(state, "process_id")
    if interview_kp is not None and interview_kp != process_id:
        # Stabiler Befund-Vertrag fuers Gate (R4-C1) — plus strukturiertes Log.
        profil["befunde"]["kp_tp_diskrepanz"] = {
            "interview_kp": interview_kp, "abgeleiteter_kp": process_id}
        log.warning("kp_tp_diskrepanz session=%s interview_kp=%s abgeleitet=%s",
                    state.session_id, interview_kp, process_id)

    spalten: dict[str, object] = {"process_owner_rolle_id": None}   # Etappe 1
    for spalte, feld in _ZAHLENSPALTEN.items():
        wert = _gueltiger_wert(state, feld)
        spalten[spalte] = _dezimal(wert, feld) if wert is not None else None
    for spalte, feld in _GANZZAHLSPALTEN.items():
        wert = _gueltiger_wert(state, feld)
        spalten[spalte] = _ganzzahl(wert, feld) if wert is not None else None
    for spalte, feld in _TEXTSPALTEN.items():
        spalten[spalte] = _gueltiger_wert(state, feld)
    spalten["upstream_process_id"] = _fremde_kp(
        state, "upstream_process", process_id, kp_bekannt)
    spalten["downstream_process_id"] = _fremde_kp(
        state, "downstream_process", process_id, kp_bekannt)

    return Profilinhalt(focus_step_id, process_id, spalten, profil)
```

- [ ] **Step 5: GREEN + Commit**

```bash
.venv/bin/pytest tests/test_profil_bau.py tests/test_core.py -v
git add bc1-context-discovery/bc1_service/profil_writer.py bc1-context-discovery/tests/test_profil_bau.py bc1-context-discovery/bc1_core/core.py
git commit -m "feat(bc1): Profil-Bau — typisierte Spalten, abgeleitete Identitaet, KP/TP-Befund"
```

---

## Task 12: S-NN-Sweep beim Schreiben

**Files:**
- Modify: `bc1_service/profil_writer.py` (Sweep-Teil)
- Modify: `bc1_core/extractor.py` (`_status_for` → öffentliches `status_fuer`)
- Modify: `tests/test_profil_bau.py`

**Interfaces:**
- Produces:
  - `GRUND_SNN_ENTFALLEN = "systemreferenz_beim_schreiben_entfallen"`
  - `wende_sweep_an(profil: dict, package, *, bekannte_systeme: frozenset[str], session_id: str) -> dict`
    — verändert den Payload **in place** und gibt ihn zurück
  - `bc1_core.extractor.status_fuer(spec, wert) -> FieldStatus`

**Normative Übergangstabelle (Spec K3, R7-I1) — jede Zeile bekommt einen Test:**

| Fall nach dem Sweep | Ergebnis im gespeicherten Profil |
|---|---|
| Wert war `gueltig`, ist jetzt leer oder ungültig | Status **`ungeloest`**, `grund = "systemreferenz_beim_schreiben_entfallen"`, Wert `null` |
| Wert war `gueltig`, bleibt gültig (Rest trägt) | unverändert `gueltig`, bereinigter Wert |
| Kandidat wird durch die Entfernung leer | Kandidat **entfällt** |
| Feld war nicht `gueltig` | Status unverändert, nur Token-Entfernung |

**Befund-Domäne (R11-I2):** `befunde.snn_entfernt` entsteht **nur** für Felder, die vor
dem Sweep `gueltig` waren; `feld_status_danach` ist exakt `gueltig` oder `ungeloest`
(lowercase). **Keine rohen IDs im JSON** — die konkrete Kennung geht ausschließlich ins
strukturierte Log (sonst stünde sie wieder im Profil und bräche die eigene
Sweep-Postcondition).

- [ ] **Step 1: Failing tests schreiben** (Ergänzung in `tests/test_profil_bau.py`)

```python
from bc1_service.profil_writer import GRUND_SNN_ENTFALLEN, wende_sweep_an

SYS_PAKET = UseCasePackage(
    name="discovery", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa",
    fields=(
        FieldSpec("focus_step", "Welcher Schritt?", typ=AUSWAHL("KP-01.TP-1"),
                  identitaetskritisch=True),
        FieldSpec("focus_step_systems", "Welche Systeme?",
                  typ=baue_system_typ(frozenset({"S-01"}))),
    ),
)
BEKANNT = frozenset({"S-01"})


def _payload(wert, status, kandidaten=()):
    return {
        "felder": {
            "focus_step": {"wert": "KP-01.TP-1", "status": "gueltig",
                           "quelle": "m1", "grund": None, "kandidaten": []},
            "focus_step_systems": {
                "wert": wert, "status": status, "quelle": "m1", "grund": None,
                "kandidaten": [{"wert": k, "quelle": "m1"} for k in kandidaten]},
        },
        "vollstaendigkeit": 1.0, "ungeloeste_felder": [],
        "pflicht_erfasst": 2, "pflicht_gesamt": 2,
        "schema_version": SYS_PAKET.schema_version, "befunde": {},
    }


def _sweep(payload):
    return wende_sweep_an(payload, SYS_PAKET, bekannte_systeme=BEKANNT,
                          session_id="s1")


def test_gueltig_wird_ungeloest_wenn_nichts_uebrig_bleibt():
    p = _sweep(_payload("S-99", "gueltig"))
    feld = p["felder"]["focus_step_systems"]
    assert feld["status"] == "ungeloest"
    assert feld["grund"] == GRUND_SNN_ENTFALLEN
    assert feld["wert"] is None
    assert p["befunde"]["snn_entfernt"] == [
        {"feld": "focus_step_systems", "anzahl": 1, "feld_status_danach": "ungeloest"}]
    assert "focus_step_systems" in p["ungeloeste_felder"]
    assert p["pflicht_erfasst"] == 1                      # Zaehler nachgezogen


def test_gueltig_bleibt_gueltig_wenn_der_rest_traegt():
    p = _sweep(_payload("SAP (S-99), DATEV (S-01)", "gueltig"))
    feld = p["felder"]["focus_step_systems"]
    assert feld["status"] == "gueltig"
    assert feld["wert"] == "SAP, DATEV (S-01)"
    assert p["befunde"]["snn_entfernt"][0]["feld_status_danach"] == "gueltig"


def test_leer_gewordener_kandidat_entfaellt():
    p = _sweep(_payload("SAP (S-01)", "gueltig", kandidaten=("S-99", "Excel (S-99)")))
    kandidaten = [k["wert"] for k in p["felder"]["focus_step_systems"]["kandidaten"]]
    assert kandidaten == ["Excel"]


def test_nicht_gueltiges_feld_wird_still_bereinigt():
    p = _sweep(_payload("S-99", "ungeloest"))
    feld = p["felder"]["focus_step_systems"]
    assert feld["status"] == "ungeloest"                  # unveraendert
    assert feld["wert"] == ""                             # Token entfernt
    assert p["befunde"] == {}                             # KEIN Nutzer-Hinweis


def test_kein_unbekanntes_token_bleibt_im_json_stehen():
    p = _sweep(_payload("S-99", "gueltig", kandidaten=("Excel (S-98)",)))
    assert "S-99" not in json.dumps(p)
    assert "S-98" not in json.dumps(p)


def test_mehrere_betroffene_felder_bleiben_in_paketreihenfolge():
    p = _payload("S-99", "gueltig")
    p["felder"]["focus_step"]["wert"] = "KP-01.TP-1 (S-98)"     # zweites Feld
    ergebnis = _sweep(p)
    assert [b["feld"] for b in ergebnis["befunde"]["snn_entfernt"]] == [
        "focus_step", "focus_step_systems"]                      # Paketreihenfolge


def test_ohne_systemnennung_passiert_nichts():
    vorher = _payload("SAP, Excel", "gueltig")
    nachher = _sweep(_payload("SAP, Excel", "gueltig"))
    assert nachher == vorher
```

- [ ] **Step 2: RED**, dann

- [ ] **Step 3: `bc1_core/extractor.py` — `_status_for` → `status_fuer`** (öffentlich,
      eine Aufrufstelle mitziehen). Dieselbe Statusregel für Extraktion und Sweep.

- [ ] **Step 4: Sweep in `bc1_service/profil_writer.py`**

```python
from bc1_core.extractor import status_fuer
from bc1_service.paket_feldtypen import entferne_snn, snn_tokens

# Neue stabile Grund-Konstante neben GRUND_NACHFRAGE_LIMIT / GRUND_RUNDEN_LIMIT.
GRUND_SNN_ENTFALLEN = "systemreferenz_beim_schreiben_entfallen"


def _unbekannte(text: str | None, bekannte: frozenset[str]) -> list[str]:
    return [t for t in snn_tokens(text or "") if t not in bekannte]


def wende_sweep_an(profil: dict, package: UseCasePackage, *,
                   bekannte_systeme: frozenset[str], session_id: str) -> dict:
    """Entfernt vor dem Schreiben JEDE nicht zum Mandanten gehoerende S-NN-Kennung.

    Erfuellt BC0-Auflage 1.4 woertlich ("beim Schreiben pruefen"). Der Validator
    schuetzt nur gueltige Werte — der Kern exportiert aber Wert UND Kandidaten
    unabhaengig vom Feldstatus (R5-I3).
    """
    befunde: list[dict] = []
    for spec in package.fields:                       # Paket-Feldreihenfolge
        feld = profil["felder"].get(spec.name)
        if feld is None:
            continue
        entfernt = _unbekannte(feld["wert"], bekannte_systeme)
        for kandidat in feld["kandidaten"]:
            entfernt += _unbekannte(kandidat["wert"], bekannte_systeme)
        if not entfernt:
            continue

        # Rohe IDs NUR ins Log (R11-I1), nie zurueck ins Profil.
        log.warning("snn_entfernt session=%s feld=%s ids=%s",
                    session_id, spec.name, sorted(set(entfernt)))

        war_gueltig = feld["status"] == FieldStatus.GUELTIG.value
        if feld["wert"] is not None:
            feld["wert"] = entferne_snn(feld["wert"], entfernt)
        feld["kandidaten"] = [
            {**k, "wert": entferne_snn(k["wert"], entfernt)}
            for k in feld["kandidaten"]
            if entferne_snn(k["wert"], entfernt)]       # leer => entfaellt

        if not war_gueltig:
            continue                                    # still bereinigt, kein Befund

        # Status neu bestimmen — der Extractor wuesste nichts von der Entfernung.
        neuer_status = (status_fuer(spec, feld["wert"]) if feld["wert"]
                        else FieldStatus.UNGUELTIG)
        if neuer_status is FieldStatus.GUELTIG:
            danach = FieldStatus.GUELTIG.value
        else:
            feld["status"] = FieldStatus.UNGELOEST.value
            feld["grund"] = GRUND_SNN_ENTFALLEN
            feld["wert"] = None
            danach = FieldStatus.UNGELOEST.value
        befunde.append({"feld": spec.name, "anzahl": len(entfernt),
                        "feld_status_danach": danach})

    if befunde:
        profil["befunde"]["snn_entfernt"] = befunde
    _zaehler_neu(profil, package)
    return profil


def _zaehler_neu(profil: dict, package: UseCasePackage) -> None:
    """vollstaendigkeit, pflicht_erfasst und ungeloeste_felder in Paketreihenfolge neu.

    Ohne das haette der Payload eine zu hohe Vollstaendigkeit — der Sweep kann
    ein Pflichtfeld gerade offen gemacht haben.
    """
    pflicht = package.required_fields()
    erfasst = sum(1 for s in pflicht
                  if profil["felder"][s.name]["status"] == FieldStatus.GUELTIG.value)
    profil["pflicht_erfasst"] = erfasst
    profil["pflicht_gesamt"] = len(pflicht)
    profil["vollstaendigkeit"] = erfasst / len(pflicht) if pflicht else 1.0
    profil["ungeloeste_felder"] = [
        s.name for s in package.fields
        if profil["felder"][s.name]["status"] == FieldStatus.UNGELOEST.value]
```

- [ ] **Step 5: GREEN + Commit**

```bash
.venv/bin/pytest tests/test_profil_bau.py -v
git add bc1-context-discovery/bc1_service/profil_writer.py bc1-context-discovery/bc1_core/extractor.py bc1-context-discovery/tests/test_profil_bau.py
git commit -m "feat(bc1): S-NN-Sweep beim Schreiben inkl. normativer Statusuebergaenge"
```

---

## Task 13: `erhebung_id`-Lookup — **BLOCKIERT durch Klärpunkt K-A**

> ⛔ **HARTES GATE — dieser Task steht VOR dem Reconcile-Task (Codex R1-C6):** Der
> Writer ruft `erhebung_id()` beim Anlegen jeder Profilzeile auf; ohne diese Funktion
> kann Task 14 nicht grün werden. Bündel-Frage #1 an Simeon muss beantwortet sein (a: welche
> `erhebung_id`, wenn die aktuellen Bewertungen aus mehreren Erhebungen stammen ·
> b: Teilprozess ganz ohne Bewertung — `NULL`, Platzhalter oder Interview verweigern?).
> Ist die Antwort beim Erreichen dieses Tasks nicht da: **Sofort-Eskalation** (so steht
> es in der Spec) und **stoppen** — Tasks 11 und 12 sind DB-frei und bis dahin gebaut,
> ein fertiger Writer gegen eine unbestätigte Erhebungsregel wäre dagegen genau die
> Abkürzung, die wir nicht nehmen. Ob wir trotzdem mit der vorläufigen Regel
> weiterbauen, entscheidet Richard; die Entscheidung gehört in den Bericht.

**Files:**
- Modify: `bc1_service/bc0_lesepfade.py`
- Modify: `tests/test_bc0_lesepfade.py`

**Interfaces:**
- Produces:
  - `class ErhebungFehltError(RuntimeError)`
  - `erhebung_id(conn, company_id: str, focus_step_id: str) -> str`

**Befund aus dem Rechte-Abgleich (gehört ins Simeon-Bündel):** Wir haben auf
`ref_erhebungen` **nur `REFERENCES`, kein `SELECT`** (Einspiel-Voraussetzungen I9).
Die „jüngste" Erhebung lässt sich deshalb **nicht** über `ref_erhebungen.stand`
bestimmen, sondern nur über die Spalten, die `v_bewertung_aktuell` selbst mitbringt
(`bewertet_am`, `erhebung_id`). Wenn Simeon „jüngste nach `stand`" bestätigt, brauchen
wir zusätzlich `SELECT` auf `ref_erhebungen` — das gehört dann ins GRANT-Signal (K-B).

- [ ] **Step 1: Failing tests schreiben**

```python
def test_erhebung_id_nimmt_die_juengste_aktuelle():
    # Fixture: KP-01.TP-1 hat Item 1 aus E-2026-02 (jueng.) und Item 2 aus E-2026-01.
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-01.TP-1") == "E-2026-02"


def test_erhebung_id_filtert_den_mandanten():
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.erhebung_id(conn, MANDANT_B, "KP-01.TP-1") == "E-2026-09"


def test_teilprozess_ohne_bewertung_meldet_sich_deutlich():
    with verbindung(DSN) as conn:
        with pytest.raises(bc0_lesepfade.ErhebungFehltError):
            bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-02.TP-1")
```

- [ ] **Step 2: RED, dann implementieren**

```python
class ErhebungFehltError(RuntimeError):
    """Zum Teilprozess gibt es keine aktuelle Bewertung (Klaerpunkt K-A, Fall b)."""


def erhebung_id(conn, company_id: str, focus_step_id: str) -> str:
    """VORLAEUFIGE Regel (Klaerpunkt K-A, Buendel-Frage #1 an BC0).

    Die 30 aktuellen Bewertungen eines Teilprozesses koennen laut BC0s 1.2-Logik
    aus MEHREREN Erhebungen stammen (je Item die juengste nicht verworfene).
    Arbeits-Vorschlag bis zur Bestaetigung: die juengste unter den aktuellen.
    'Juengste' ueber bewertet_am — auf ref_erhebungen.stand haben wir kein
    SELECT-Recht (nur REFERENCES).

    Fall b (Teilprozess ohne aktuelle Bewertung): unsere Spalte ist NOT NULL,
    die Sicht liefert null Zeilen => ErhebungFehltError. Der Reconcile legt dann
    in nicht-terminalen Turns kein Profil an; im Terminal-Turn wird daraus ein
    503. Sobald K-A beantwortet ist, aendert sich AUSSCHLIESSLICH diese Funktion.
    """
    zeile = conn.execute(
        "SELECT erhebung_id FROM v_bewertung_aktuell "
        " WHERE company_id = %s AND sub_process_id = %s "
        " ORDER BY bewertet_am DESC, erhebung_id DESC LIMIT 1",
        (company_id, focus_step_id)).fetchone()
    if zeile is None:
        raise ErhebungFehltError(
            f"Teilprozess {focus_step_id} hat keine aktuelle Bewertung — "
            "ohne erhebung_id kann kein Profil entstehen (Klaerpunkt K-A).")
    return zeile[0]
```

`ErhebungFehltError` behandelt Task 14 (Writer): in `_einfuegen` **nicht** fangen — der
generische Fehlerpfad in `reconcile` macht daraus im Terminal-Turn 503 und in
nicht-terminalen Turns einen Log-Eintrag. Der zugehörige Test gehört zu Task 14:

```python
def test_teilprozess_ohne_bewertung_erzeugt_im_terminal_turn_503(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    with pytest.raises(ProfilWriteError):
        writer.reconcile(_state(tp="KP-02.TP-1"), FERTIG)
    assert writer.reconcile(_state(tp="KP-02.TP-1"), FRAGE) is None   # kein Absturz
```

- [ ] **Step 3: GREEN + Commit**

```bash
git commit -m "feat(bc1): erhebung_id-Lookup (vorlaeufige K-A-Regel, eine Naht)"
```

---

## Task 14: Reconcile — Bindung, Draft, Rebind, Freeze, Postcondition

**Files:**
- Modify: `bc1_service/profil_writer.py` (Klasse `ProfilWriter`)
- Create: `tests/test_profil_writer.py`

**Interfaces:**
- Consumes: Tasks 8, 11, 12, **13** (`bc0_lesepfade.erhebung_id`); DDL aus Task 3/4.
- Produces:
  - `ProfilWriter(pool, company_id: str, package: UseCasePackage)`
  - `ProfilWriter.reconcile(state: SessionState, antwort: dict) -> dict | None`
    — Rückgabe = gespeichertes Profil-JSON **nur** bei einer `fertig`-Antwort
    (Overlay-Quelle für die API), sonst `None`; wirft `ProfilWriteError`,
    wenn eine `fertig`-Antwort nicht abgesichert werden kann (⇒ 503).

**Postcondition, hart (Spec K3.3):** Eine `fertig`-Antwort wird **nur** ausgeliefert,
wenn im selben Reconcile eine EIGENE Bindung existiert (nötigenfalls INSERT jetzt) und
genau diese Zeile erfolgreich auf `fertig` gesetzt wurde. Jeder Fehler im Terminal-Turn
— fehlende Bindung, INSERT-Fehler, Fremd-Draft-Konflikt, UPDATE-Fehler — erzeugt 503.
Für `abgebrochen_ohne_identitaet` gilt die Postcondition **ausdrücklich nicht**.

- [ ] **Step 1: Failing tests schreiben** (`tests/test_profil_writer.py`)

```python
import pytest
from psycopg_pool import ConnectionPool

from bc1_core.feldtypen import AUSWAHL
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_service.paket_feldtypen import baue_system_typ
from bc1_service.profil_writer import ProfilWriteError, ProfilWriter
from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

PAKET = UseCasePackage(
    name="discovery", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa",
    fields=(
        FieldSpec("focus_step", "Welcher Schritt?",
                  typ=AUSWAHL("KP-01.TP-1", "KP-01.TP-2", "KP-02.TP-1"),
                  identitaetskritisch=True),
        FieldSpec("focus_step_systems", "Welche Systeme?",
                  typ=baue_system_typ(frozenset({"S-01", "S-02"}))),
    ),
)
FERTIG = {"status": "fertig", "payload": {}}
FRAGE = {"status": "frage", "payload": {}}
ABBRUCH = {"status": "abgebrochen_ohne_identitaet", "payload": {}}


@pytest.fixture
def pool():
    frische_db(DSN)
    p = ConnectionPool(DSN, min_size=1, max_size=4, open=True,
                       kwargs={"options": "-c role=bc1_role"})
    yield p
    p.close()


def _state(session_id="s1", tp="KP-01.TP-1", mandant=MANDANT_A, **felder):
    st = SessionState(session_id, PAKET.schema_version, paket_name="discovery",
                      company_id=mandant)
    st.values["focus_step"] = FieldValue(value=tp, status=FieldStatus.GUELTIG,
                                         source_message_id="m1")
    for name, (wert, status) in felder.items():
        st.values[name] = FieldValue(value=wert, status=status,
                                     source_message_id="m1")
    return st


def _zeilen(spalten="focus_step_id, profil_version, status"):
    with verbindung(DSN) as conn:
        return conn.execute(
            f"SELECT {spalten} FROM bc1.prozessprofil ORDER BY focus_step_id"
        ).fetchall()


def test_erster_turn_legt_draft_und_bindung_an(pool):
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(), FRAGE)
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT session_id, profil_version "
                            "FROM bc1.profil_write_status").fetchall() == [("s1", 1)]


def test_zweiter_turn_legt_keine_zweite_zeile_an(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    writer.reconcile(_state(), FRAGE)
    assert len(_zeilen()) == 1


def test_abschluss_friert_die_eigene_zeile_ein_und_liefert_den_payload(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    payload = writer.reconcile(_state(), FERTIG)
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]
    assert payload["felder"]["focus_step"]["wert"] == "KP-01.TP-1"


def test_abschluss_ohne_vorherigen_draft_legt_ihn_jetzt_an(pool):
    payload = ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(), FERTIG)
    assert payload is not None
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]


def test_replay_nach_committetem_freeze_ist_ein_no_op_erfolg(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FERTIG)
    payload = writer.reconcile(_state(), FERTIG)          # Antwort war verloren
    assert payload is not None                            # Erfolg ohne UPDATE
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]


def test_tp_korrektur_bindet_um_und_raeumt_den_alten_draft(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    writer.reconcile(_state(tp="KP-01.TP-2"), FRAGE)
    assert _zeilen() == [("KP-01.TP-2", 1, "in_erhebung")]


def test_tp_korrektur_ueber_die_kp_grenze_zieht_process_id_nach(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    writer.reconcile(_state(tp="KP-02.TP-1"), FRAGE)
    assert _zeilen("focus_step_id, process_id") == [("KP-02.TP-1", "KP-02")]


def test_rebind_konflikt_laesst_den_alten_draft_stehen(pool):
    # Codex R1-C5: bei einem belegten Ziel darf der alte Draft NICHT verloren
    # gehen — Loeschen und Neuanlage liegen in einem gemeinsamen Savepoint.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="s1", tp="KP-01.TP-1"), FRAGE)
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(
        _state(session_id="fremd", tp="KP-01.TP-2"), FRAGE)
    assert writer.reconcile(_state(session_id="s1", tp="KP-01.TP-2"), FRAGE) is None
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung"),
                         ("KP-01.TP-2", 1, "in_erhebung")]
    with verbindung(DSN) as conn:
        assert conn.execute(
            "SELECT focus_step_id FROM bc1.profil_write_status "
            "WHERE session_id = 's1'").fetchone()[0] == "KP-01.TP-1"


def test_kp_feld_aenderung_loest_keinen_rebind_aus(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    geaendert = _state()
    geaendert.values["process_id"] = FieldValue(
        value="KP-02", status=FieldStatus.GUELTIG, source_message_id="m2")
    writer.reconcile(geaendert, FRAGE)
    assert _zeilen("focus_step_id, process_id") == [("KP-01.TP-1", "KP-01")]


def test_fremder_draft_blockiert_stabil_und_wird_nicht_adoptiert(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="fremd"), FRAGE)
    assert writer.reconcile(_state(session_id="s2"), FRAGE) is None
    assert len(_zeilen()) == 1
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_write_status"
                            ).fetchone()[0] == 1


def test_fremder_draft_im_terminal_turn_erzeugt_503(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="fremd"), FRAGE)
    with pytest.raises(ProfilWriteError):
        writer.reconcile(_state(session_id="s2"), FERTIG)


def test_abbruch_raeumt_den_gebundenen_draft(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    assert writer.reconcile(_state(), ABBRUCH) is None
    assert _zeilen() == []
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_write_status"
                            ).fetchone()[0] == 0            # CASCADE raeumt mit


def test_unklar_allein_loescht_den_draft_noch_nicht(pool):
    # R6-C1: die Klaerung kann den alten Wert bestaetigen — voreiliges Loeschen
    # waere Datenverlust. Erst der Terminalzustand raeumt.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    unklar = _state()
    unklar.values["focus_step"].status = FieldStatus.UNKLAR
    assert writer.reconcile(unklar, FRAGE) is None
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]


def test_gueltig_unklar_abbruch_raeumt_den_draft(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    unklar = _state()
    unklar.values["focus_step"].status = FieldStatus.UNKLAR
    writer.reconcile(unklar, FRAGE)
    assert writer.reconcile(unklar, ABBRUCH) is None
    assert _zeilen() == []


def test_fehlgeschlagenes_aufraeumen_am_draft_liefert_trotzdem_aus(pool, caplog):
    # K5-Fall: das DELETE scheitert, der Draft BLEIBT verwaist stehen, die
    # Antwort geht trotzdem raus (Codex R2-N-I6 — der Freeze-Fall unten kann
    # das nicht zeigen, dort gibt es gar keinen Draft).
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    with verbindung(DSN) as conn:                      # DELETE gezielt blockieren
        conn.execute(
            "CREATE FUNCTION bc1.tf_blockiere() RETURNS trigger LANGUAGE plpgsql "
            "AS $fn$ BEGIN RAISE EXCEPTION 'Aufraeumen blockiert'; END $fn$")
        conn.execute("CREATE TRIGGER tr_blockiere BEFORE DELETE ON bc1.prozessprofil "
                     "FOR EACH ROW EXECUTE FUNCTION bc1.tf_blockiere()")
        conn.commit()
    with caplog.at_level("ERROR"):
        assert writer.reconcile(_state(), ABBRUCH) is None      # KEIN 503
    assert "draft_aufraeumen_fehlgeschlagen" in caplog.text
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]      # Draft bleibt


def test_neustart_nach_committeter_bindung_macht_sauber_weiter(pool):
    # Crash "nach INSERT, vor Antwort": ein FRISCHER Writer (neuer Prozess) muss
    # die Bindung in profil_write_status finden — keine zweite Zeile.
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(), FRAGE)
    payload = ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(), FERTIG)
    assert payload is not None
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]


def test_fehlgeschlagenes_aufraeumen_bei_eingefrorener_zeile(pool, caplog):
    # Realistische Simulation: die gebundene Zeile ist inzwischen eingefroren —
    # der Freeze-Trigger weist das DELETE ab (K5-Fall, verwaister Draft bleibt).
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FERTIG)
    with caplog.at_level("ERROR"):
        assert writer.reconcile(_state(), ABBRUCH) is None   # KEIN 503
    assert "draft_aufraeumen_fehlgeschlagen" in caplog.text  # strukturiert geloggt
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]        # Zeile bleibt stehen


def test_zweites_interview_bekommt_version_zwei(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="s1"), FERTIG)
    writer.reconcile(_state(session_id="s2"), FERTIG)
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig"), ("KP-01.TP-1", 2, "fertig")]


def test_bindung_wird_nur_im_eigenen_mandanten_gefunden(pool):
    # session_id ist globaler Primaerschluessel von profil_write_status — zwei
    # Mandanten koennen sie sich also nie teilen. Geprueft wird deshalb: der
    # Writer von B findet die Bindung von A NICHT und legt seine eigene an.
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(session_id="s-a"), FRAGE)
    ProfilWriter(pool, MANDANT_B, PAKET).reconcile(
        _state(session_id="s-b", mandant=MANDANT_B), FRAGE)
    with verbindung(DSN) as conn:
        paare = conn.execute(
            "SELECT w.session_id, w.company_id FROM bc1.profil_write_status w "
            "ORDER BY w.session_id").fetchall()
    assert [(z[0], str(z[1])) for z in paare] == [
        ("s-a", MANDANT_A), ("s-b", MANDANT_B)]
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(DISTINCT company_id) "
                            "FROM bc1.prozessprofil").fetchone()[0] == 2


def test_paket_ohne_identitaetsfeld_schreibt_nichts(pool):
    ohne = UseCasePackage(name="toy_prozess", schema_version="0.1",
                          fields=(FieldSpec("prozess_name", "Wie heisst er?"),))
    assert ProfilWriter(pool, MANDANT_A, ohne).reconcile(_state(), FERTIG) is None
    assert _zeilen() == []
```

**Zur Fixture:** Der Pool verbindet als `postgres` und setzt per
`options="-c role=bc1_role"` die Rolle für jede Verbindung — so laufen die Tests unter
exakt den Rechten, die im Betrieb gelten (`bc1_role` hat im Container kein LOGIN).

- [ ] **Step 2: RED**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_profil_writer.py -v
```

- [ ] **Step 3: `ProfilWriter` implementieren** (in `bc1_service/profil_writer.py`)

```python
import time
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from bc1_service import bc0_lesepfade

KONFLIKT_LOG_ABSTAND_S = 60.0      # Rate-Limit fuer den stabilen Konflikt-Log


@dataclass(frozen=True)
class Bindung:
    focus_step_id: str
    profil_version: int
    status: str


class ProfilWriter:
    """Gleicht am Ende jedes zugelassenen Turns Soll und Ist ab (Spec K3)."""

    def __init__(self, pool, company_id: str, package: UseCasePackage) -> None:
        self._pool = pool
        self._company_id = company_id
        self._package = package
        # Ohne identitaetskritisches Feld gibt es keine Prozess-Identitaet und
        # damit kein Profil (z. B. Toy-Paket) — der Writer haelt sich raus.
        self._schreibt = any(s.identitaetskritisch
                             for s in package.required_fields())
        self._konflikt_zuletzt: dict[str, float] = {}

    def reconcile(self, state: SessionState, antwort: dict) -> dict | None:
        if not self._schreibt:
            return None
        status = antwort["status"]
        if status == "fehler_fortsetzbar":
            return None
        terminal = status == "fertig"
        try:
            with self._pool.connection() as conn:          # eine Transaktion
                return self._abgleich(conn, state, status, terminal)
        except ProfilWriteError:
            raise
        except Exception as fehler:                        # noqa: BLE001
            if terminal:
                raise ProfilWriteError(
                    f"Profil-Write im Terminal-Turn fehlgeschlagen: {fehler}") from fehler
            # Nicht-terminale Turns blockieren nicht — der naechste reconcilet.
            log.warning("profil_write_uebersprungen session=%s grund=%r",
                        state.session_id, fehler)
            return None

    # ---- innerhalb EINER Transaktion ------------------------------------
    def _abgleich(self, conn, state, status, terminal):
        bindung = self._bindung(conn, state.session_id)

        if status == "abgebrochen_ohne_identitaet":
            if bindung is not None:
                self._draft_aufraeumen(conn, bindung, state.session_id)
            return None

        inhalt = baue_profilinhalt(
            state, self._package,
            kp_bekannt=lambda kp: bc0_lesepfade.kp_existiert(conn, self._company_id, kp))
        if inhalt is None:
            if terminal:
                raise ProfilWriteError(
                    "fertig ohne gueltige Fokus-Schritt-ID (Completion-Guard verletzt)")
            return None

        # Auflage 1.4: schlichtes SELECT in DERSELBEN Transaktion, ohne
        # Sperrklausel (FOR KEY SHARE braucht UPDATE-Recht, R7-C1).
        wende_sweep_an(
            inhalt.profil, self._package,
            bekannte_systeme=frozenset(
                bc0_lesepfade.system_ids(conn, self._company_id)),
            session_id=state.session_id)

        if bindung is not None and bindung.focus_step_id != inhalt.focus_step_id:
            if bindung.status == "fertig":
                raise ProfilWriteError(
                    "gebundene Zeile ist eingefroren, TP-ID weicht ab")
            # Rebind ATOMAR: Loeschen und Neuanlage liegen in EINEM Savepoint.
            # Sonst waere bei einem Zielkonflikt der alte Draft schon geloescht
            # und der Verlust wuerde mitcommittet (Codex R1-C5).
            bindung = self._umbinden(conn, state, inhalt, bindung)
            if bindung is None:
                if terminal:
                    raise ProfilWriteError(
                        "Rebind-Ziel ist von einem fremden Draft belegt")
                return None                                 # alter Draft steht noch
        elif bindung is None:
            bindung = self._draft_anlegen(conn, state, inhalt)
            if bindung is None:                             # fremder Draft
                if terminal:
                    raise ProfilWriteError(
                        "fremder in_erhebung-Draft belegt den Fokus-Schritt")
                return None

        if not terminal:
            return None
        if bindung.status == "fertig":
            # Freeze war committet, die Antwort ging verloren (R4-C2).
            return self._gespeichertes_profil(conn, bindung)
        return self._einfrieren(conn, bindung, inhalt)

    def _bindung(self, conn, session_id: str) -> Bindung | None:
        zeile = conn.execute(
            "SELECT w.focus_step_id, w.profil_version, p.status "
            "  FROM bc1.profil_write_status w "
            "  JOIN bc1.prozessprofil p ON p.company_id = w.company_id "
            "   AND p.focus_step_id = w.focus_step_id "
            "   AND p.profil_version = w.profil_version "
            " WHERE w.session_id = %s AND w.company_id = %s",
            (session_id, self._company_id)).fetchone()
        return Bindung(*zeile) if zeile else None

    def _umbinden(self, conn, state, inhalt, alt: Bindung) -> Bindung | None:
        """Alten Draft loeschen und neu binden — ganz oder gar nicht."""
        try:
            with conn.transaction():                 # ein gemeinsamer Savepoint
                conn.execute(
                    "DELETE FROM bc1.prozessprofil WHERE company_id = %s "
                    "AND focus_step_id = %s AND profil_version = %s",
                    (self._company_id, alt.focus_step_id, alt.profil_version))
                return self._einfuegen(conn, state, inhalt)   # wirft bei Konflikt
        except UniqueViolation:
            # Rollback bis zum Savepoint: alter Draft UND Bindung stehen noch.
            self._konflikt_melden(state.session_id, inhalt.focus_step_id)
            return None

    def _draft_anlegen(self, conn, state, inhalt) -> Bindung | None:
        try:
            # Savepoint: ein Unique-Konflikt darf die umgebende Transaktion
            # nicht abschiessen (der Turn laeuft ja weiter).
            with conn.transaction():
                return self._einfuegen(conn, state, inhalt)
        except UniqueViolation:
            self._konflikt_melden(state.session_id, inhalt.focus_step_id)
            return None

    def _einfuegen(self, conn, state, inhalt) -> Bindung:
        """Profilzeile + Bindung im selben Commit (C2). Wirft bei Fremd-Draft."""
        erhebung = bc0_lesepfade.erhebung_id(
            conn, self._company_id, inhalt.focus_step_id)
        spalten = inhalt.spalten
        namen = ["company_id", "focus_step_id", "profil_version", "process_id",
                 "status", "erhebung_id", "paket_version", "profil", *spalten]
        werte = [self._company_id, inhalt.focus_step_id, 1, inhalt.process_id,
                 "in_erhebung", erhebung, state.schema_version,
                 Jsonb(inhalt.profil), *spalten.values()]
        platzhalter = ", ".join(["%s"] * len(namen))
        version = conn.execute(
            f"INSERT INTO bc1.prozessprofil ({', '.join(namen)}) "
            f"VALUES ({platzhalter}) RETURNING profil_version",
            werte).fetchone()[0]
        conn.execute(
            "INSERT INTO bc1.profil_write_status "
            "(session_id, company_id, focus_step_id, profil_version) "
            "VALUES (%s, %s, %s, %s)",
            (state.session_id, self._company_id, inhalt.focus_step_id, version))
        return Bindung(inhalt.focus_step_id, version, "in_erhebung")

    def _einfrieren(self, conn, bindung, inhalt) -> dict:
        # Spaltennamen stammen aus unserer eigenen Konstante, nicht aus Eingaben.
        zuweisungen = ", ".join(f"{spalte} = %s" for spalte in inhalt.spalten)
        cursor = conn.execute(
            f"UPDATE bc1.prozessprofil SET status = 'fertig', profil = %s, "
            f"{zuweisungen} WHERE company_id = %s AND focus_step_id = %s "
            "AND profil_version = %s AND status = 'in_erhebung'",
            [Jsonb(inhalt.profil), *inhalt.spalten.values(), self._company_id,
             bindung.focus_step_id, bindung.profil_version])
        if cursor.rowcount != 1:
            raise ProfilWriteError(
                f"Freeze traf {cursor.rowcount} Zeilen statt einer")
        return inhalt.profil

    def _gespeichertes_profil(self, conn, bindung) -> dict:
        return conn.execute(
            "SELECT profil FROM bc1.prozessprofil WHERE company_id = %s "
            "AND focus_step_id = %s AND profil_version = %s",
            (self._company_id, bindung.focus_step_id,
             bindung.profil_version)).fetchone()[0]

    def _draft_aufraeumen(self, conn, bindung, session_id: str) -> None:
        try:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM bc1.prozessprofil WHERE company_id = %s "
                    "AND focus_step_id = %s AND profil_version = %s",
                    (self._company_id, bindung.focus_step_id,
                     bindung.profil_version))
        except Exception as fehler:                         # noqa: BLE001
            # Ehrlich (Spec K0): die Antwort geht trotzdem raus — die Session ist
            # fachlich zu Ende. Zurueck bleibt ein verwaister Draft; er ist fuer
            # BC0 nicht gate-relevant, belegt aber den UNIQUE-Slot (Betriebsweg K5).
            log.error("draft_aufraeumen_fehlgeschlagen session=%s schritt=%s grund=%r",
                      session_id, bindung.focus_step_id, fehler)

    def _konflikt_melden(self, session_id: str, focus_step_id: str) -> None:
        # Stabiler Konflikt, rate-limitiert: ohne persistenten Marker waere ein
        # "einmalig"-Versprechen nicht haltbar (Spec K3.2).
        jetzt = time.monotonic()
        schluessel = f"{session_id}|{focus_step_id}"
        if jetzt - self._konflikt_zuletzt.get(schluessel, 0.0) < KONFLIKT_LOG_ABSTAND_S:
            return
        self._konflikt_zuletzt[schluessel] = jetzt
        log.warning("fremder_draft_konflikt session=%s schritt=%s mandant=%s",
                    session_id, focus_step_id, self._company_id)
```

- [ ] **Step 4: GREEN + Commit**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_profil_writer.py -v
git add bc1-context-discovery/bc1_service/profil_writer.py bc1-context-discovery/tests/test_profil_writer.py
git commit -m "feat(bc1): Profil-Writer — atomare Bindung, Rebind, Freeze mit harter Postcondition"
```

---

## Task 15: API-Verdrahtung — Reconcile, DB→Wire-Overlay, Post-Sweep-Hinweise, 503

**Files:**
- Modify: `bc1_service/api.py`, `bc1_service/main.py`
- Create: `tests/test_api_profil.py`

**Interfaces:**
- Consumes: Tasks 7, 14 (Reconcile).
- Produces:
  - `create_app(..., *, company_id: str, writer: ProfilWriter | None = None)`
  - `bc1_service.api.OVERLAY_SCHLUESSEL` — die Payload-Keys, die aus der DB kommen
  - `HINWEIS_UNGELOEST`, `HINWEIS_GUELTIG` (feste, LLM-freie Texte)
  - HTTP `503 profil_write_fehlgeschlagen`

**DB→Wire-Overlay (Spec K3.3, normativ):**

| Payload-Key | Quelle |
|---|---|
| `felder`, `vollstaendigkeit`, `ungeloeste_felder`, `pflicht_erfasst`, `pflicht_gesamt`, `befunde` | **DB** (gespeichertes `prozessprofil.profil`) |
| `abschluss_text`, `schema_version` | Kern-Antwort |
| `chat_text` | erzeugt die API **nach** dem Overlay |

**Geltungsbereich:** Das Overlay greift **nur**, wenn dieser Turn eine `fertig`-Antwort
zurückgibt (Erstabschluss oder Replay der Abschluss-`message_id`). Der Replay einer
älteren Frage-`message_id` bleibt unverändert historisch.

**Post-Sweep-Hinweis (R9-I1/R10-I1/I2):** Der Kern lässt den Abschlusstext formulieren,
BEVOR der Sweep läuft. Hat der Sweep etwas verändert, hängt die API einen festen Zusatz
an — **kein zweiter LLM-Aufruf**. Auslöser ist ausschließlich `befunde.snn_entfernt` im
überlagerten Payload (persistent in der DB) — deshalb ist der Text nach einem Neustart
identisch und kann nicht doppelt angehängt werden.

- [ ] **Step 1: Failing tests schreiben** (`tests/test_api_profil.py`)

```python
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from bc1_core.feldtypen import AUSWAHL
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.store import InMemoryStateStore
from bc1_service.api import (HINWEIS_GUELTIG, HINWEIS_UNGELOEST, create_app)
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket
from bc1_service.profil_writer import ProfilWriter
from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

KONTEXT = Bc0Kontext(
    company_id=MANDANT_A,
    teilprozesse=(("KP-01.TP-1", "Erfassen"), ("KP-01.TP-2", "Pruefen")),
    system_ids=("S-01", "S-02"))

# Alle 26 Pflichtfelder des Discovery-Pakets in einer Nachricht — so ist der
# Durchstich ein Turn und der Test bleibt lesbar.
WERTE = {
    "request_intent": "Angebote schneller rausbringen",
    "request_goal": "zeit_sparen",
    "scope_focus": "einzelner_schritt",
    "process_name": "Angebotserstellung",
    "process_owner_role": "Vertriebsleitung",
    "process_id": "KP-01",
    "process_steps": "Anfrage, Kalkulation, Angebot",
    "trigger_text": "Kundenanfrage per Mail",
    "input_text": "Anfrage mit Mengen",
    "input_format": "mail",
    "output_text": "Angebot als PDF",
    "frequency_per_year": "120",
    "executions_per_run": "3",
    "total_duration_minutes": "90",
    "focus_step": "KP-01.TP-1",
    "focus_step_duration_minutes": "30",
    "focus_step_duration_source": "geschaetzt",
    "focus_step_duration_confidence_pct": "70",
    "focus_step_roles": "Vertrieb, Kalkulation",
    "focus_step_systems": "SAP (s-01)",     # klein: Kanonisierung nachweisen
    "focus_step_media_break": "ja",
    "documentation_status": "3",
    "standardization_level": "4",
    "data_availability_score": "3",
    "stability_score": "4",
    "pii_involved": "ja",
}


def _llm(ohne=(), abweichend=None):
    werte = {**WERTE, **(abweichend or {})}
    erste = [ExtractionCandidate(n, w) for n, w in werte.items() if n not in ohne]
    zweite = [ExtractionCandidate(n, werte[n]) for n in ohne]
    return FakeLLM({"alles": erste, "rest": zweite})


@pytest.fixture
def umgebung():
    frische_db(DSN)
    pool = ConnectionPool(DSN, min_size=1, max_size=4, open=True,
                          kwargs={"options": "-c role=bc1_role"})
    paket = baue_discovery_paket(kontext=KONTEXT)
    yield pool, paket
    pool.close()


def _client(umgebung, ohne=(), abweichend=None):
    pool, paket = umgebung
    return TestClient(create_app(
        InMemoryStateStore(), _llm(ohne, abweichend), paket, company_id=MANDANT_A,
        writer=ProfilWriter(pool, MANDANT_A, paket)))


def _turn(client, mid, text, session="s1", **extra):
    return client.post("/turn", json={"session_id": session, "message_id": mid,
                                      "message": text, **extra})


def test_durchstich_schreibt_genau_eine_eingefrorene_zeile(umgebung):
    antwort = _turn(_client(umgebung), "m1", "alles")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fertig"
    with verbindung(DSN) as conn:
        zeilen = conn.execute(
            "SELECT focus_step_id, process_id, status, erhebung_id, "
            "       frequency_per_year, focus_step_duration_confidence_pct, "
            "       paket_version, profil "
            "  FROM bc1.prozessprofil").fetchall()
    assert len(zeilen) == 1
    zeile = zeilen[0]
    assert zeile[0] == "KP-01.TP-1" and zeile[1] == "KP-01"
    assert zeile[2] == "fertig" and zeile[3] == "E-2026-02"
    assert zeile[4] == 120 and zeile[5] == 70
    assert zeile[6].startswith("1.1+ctx-")
    assert zeile[7]["felder"]["process_name"]["wert"] == "Angebotserstellung"
    # Kanonisierung bis in die DB (Spec K4): 's-01' wird als 'S-01' gespeichert.
    assert zeile[7]["felder"]["focus_step_systems"]["wert"] == "SAP (S-01)"


def test_sweep_macht_das_feld_offen_und_der_payload_folgt_der_db(umgebung):
    # Alleinstehende Kennung: nach der Entfernung bleibt NICHTS uebrig.
    client = _client(umgebung, ohne=("pii_involved",),
                     abweichend={"focus_step_systems": "S-02"})
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:                 # System verschwindet
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    antwort = _turn(client, "m2", "rest").json()
    feld = antwort["payload"]["felder"]["focus_step_systems"]
    assert feld["status"] == "ungeloest"
    assert feld["wert"] is None
    assert "focus_step_systems" in antwort["payload"]["ungeloeste_felder"]
    assert antwort["payload"]["vollstaendigkeit"] < 1.0
    assert HINWEIS_UNGELOEST in antwort["chat_text"]
    with verbindung(DSN) as conn:
        gespeichert = conn.execute("SELECT profil FROM bc1.prozessprofil").fetchone()[0]
    assert gespeichert["vollstaendigkeit"] == antwort["payload"]["vollstaendigkeit"]
    assert "S-02" not in str(gespeichert)


def test_sweep_mit_tragendem_rest_meldet_den_anderen_hinweis(umgebung):
    client = _client(umgebung, ohne=("pii_involved",),
                     abweichend={"focus_step_systems": "SAP (S-02)"})
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    # Wert war "SAP (S-02)" => "SAP" traegt nach der Entfernung weiter.
    antwort = _turn(client, "m2", "rest").json()
    assert antwort["payload"]["felder"]["focus_step_systems"]["status"] == "gueltig"
    assert antwort["payload"]["felder"]["focus_step_systems"]["wert"] == "SAP"
    assert HINWEIS_GUELTIG in antwort["chat_text"]


def test_replay_der_abschlussnachricht_liefert_denselben_hinweis_genau_einmal(umgebung):
    client = _client(umgebung, ohne=("pii_involved",),
                     abweichend={"focus_step_systems": "SAP (S-02)"})
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    erst = _turn(client, "m2", "rest").json()
    nochmal = _turn(client, "m2", "rest").json()
    assert nochmal == erst
    assert nochmal["chat_text"].count(HINWEIS_GUELTIG) == 1


def test_replay_einer_aelteren_frage_bleibt_historisch(umgebung):
    client = _client(umgebung, ohne=("pii_involved",))
    frage = _turn(client, "m1", "alles").json()
    _turn(client, "m2", "rest")
    assert _turn(client, "m1", "alles").json() == frage      # kein Overlay


def test_unbekannte_kennung_ueberlebt_das_nachfrage_limit_nicht(umgebung):
    # Spec K4: S-99 -> Nachfrage-Limit -> Abschluss => kein unbekanntes Token im
    # gespeicherten JSON, auch nicht unter den Kandidaten.
    pool, paket = umgebung
    llm = FakeLLM({
        "alles": [ExtractionCandidate(n, w) for n, w in WERTE.items()
                  if n != "focus_step_systems"],
        "systeme": [ExtractionCandidate("focus_step_systems", "Eigenbau (S-99)")],
        "nochmal": [ExtractionCandidate("focus_step_systems", "Eigenbau2 (S-99)")],
    })
    client = TestClient(create_app(InMemoryStateStore(), llm, paket,
                                   company_id=MANDANT_A,
                                   writer=ProfilWriter(pool, MANDANT_A, paket)))
    _turn(client, "m1", "alles")
    _turn(client, "m2", "systeme")
    antwort = _turn(client, "m3", "nochmal").json()
    assert antwort["status"] == "fertig"
    assert antwort["payload"]["felder"]["focus_step_systems"]["status"] == "ungeloest"
    with verbindung(DSN) as conn:
        gespeichert = conn.execute("SELECT profil FROM bc1.prozessprofil").fetchone()[0]
    assert "S-99" not in str(gespeichert)


def test_sweep_hinweis_ueberlebt_den_neustart_unveraendert(umgebung):
    # R10-I2: Ausloeser ist der persistente Befund in der DB, nicht Laufzeitwissen.
    pool, paket = umgebung
    store = InMemoryStateStore()                       # bleibt ueber den Neustart
    def _app():
        return TestClient(create_app(
            store, _llm(ohne=("pii_involved",),
                        abweichend={"focus_step_systems": "SAP (S-02)"}),
            paket, company_id=MANDANT_A,
            writer=ProfilWriter(pool, MANDANT_A, paket)))
    client = _app()
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    erst = _turn(client, "m2", "rest").json()
    nach_neustart = _turn(_app(), "m2", "rest").json()   # frische App, alter Store
    assert nach_neustart["chat_text"] == erst["chat_text"]
    assert nach_neustart["chat_text"].count(HINWEIS_GUELTIG) == 1


def test_recovery_nach_neustart_mit_geaendertem_ctx_holt_den_write_nach(umgebung):
    # Spec K0-Tabelle: 503 beim Abschluss -> Neustart mit geaenderten
    # Options-Mengen -> derselbe Replay MIT alter schema_version holt den Write nach.
    pool, paket = umgebung
    store = InMemoryStateStore()
    with verbindung(DSN) as conn:                        # fremder Draft blockiert
        conn.execute(
            "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
            "profil_version, process_id, status, erhebung_id, paket_version, profil) "
            "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-02', "
            "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))
        conn.commit()
    client = TestClient(create_app(store, _llm(), paket, company_id=MANDANT_A,
                                   writer=ProfilWriter(pool, MANDANT_A, paket)))
    assert _turn(client, "m1", "alles").status_code == 503
    with verbindung(DSN) as conn:
        conn.execute("DELETE FROM bc1.prozessprofil WHERE status = 'in_erhebung'")
        conn.commit()

    # Neustart mit zusaetzlichem Teilprozess => anderer ctx-Hash
    neuer_kontext = Bc0Kontext(
        MANDANT_A, KONTEXT.teilprozesse + (("KP-02.TP-1", "Bestellen A"),),
        KONTEXT.system_ids)
    neues_paket = baue_discovery_paket(kontext=neuer_kontext)
    assert neues_paket.schema_version != paket.schema_version
    client_neu = TestClient(create_app(
        store, _llm(), neues_paket, company_id=MANDANT_A,
        writer=ProfilWriter(pool, MANDANT_A, neues_paket)))
    antwort = _turn(client_neu, "m1", "alles",
                    schema_version=paket.schema_version)
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fertig"
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchall() == [
            ("fertig",)]


def test_abbruch_mit_blockiertem_aufraeumen_liefert_trotzdem_200(umgebung, caplog):
    # Spec K4 verlangt den Nachweis auf HTTP-Ebene: DELETE-Fehler beim Aufraeumen
    # => 200 + Logeintrag + Draft bleibt (Codex R3-I4). Ein zweifeldriges Paket
    # laesst den Abbruch in zwei Turns erreichen.
    pool, _ = umgebung
    # ZWEI Pflichtfelder: sonst waere die Session schon nach Turn 1 fertig und
    # Turn 2 bekaeme 409 statt des Abbruchs (Codex R4-N4-I1).
    knapp = UseCasePackage(
        name="discovery", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa", max_rounds=2,
        fields=(FieldSpec("focus_step", "Welcher Schritt?",
                          typ=AUSWAHL("KP-01.TP-1", "KP-01.TP-2"),
                          identitaetskritisch=True),
                FieldSpec("dauer", "Wie lange dauert der Schritt?")))
    llm = FakeLLM({
        "schritt": [ExtractionCandidate("focus_step", "KP-01.TP-1")],
        # Zweitnennung eines ANDEREN gueltigen Schritts => Feld wird UNKLAR;
        # am Rundenlimit greift damit der Completion-Guard.
        "wirr": [ExtractionCandidate("focus_step", "KP-01.TP-2")]})
    client = TestClient(create_app(InMemoryStateStore(), llm, knapp,
                                   company_id=MANDANT_A,
                                   writer=ProfilWriter(pool, MANDANT_A, knapp)))
    erst = _turn(client, "m1", "schritt")
    assert erst.json()["status"] == "frage"             # Session laeuft weiter
    with verbindung(DSN) as conn:                        # Draft gebunden?
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchall() == [
            ("in_erhebung",)]
        assert conn.execute("SELECT count(*) FROM bc1.profil_write_status"
                            ).fetchone()[0] == 1
    with verbindung(DSN) as conn:                       # DELETE blockieren
        conn.execute(
            "CREATE FUNCTION bc1.tf_blockiere() RETURNS trigger LANGUAGE plpgsql "
            "AS $fn$ BEGIN RAISE EXCEPTION 'Aufraeumen blockiert'; END $fn$")
        conn.execute("CREATE TRIGGER tr_blockiere BEFORE DELETE ON bc1.prozessprofil "
                     "FOR EACH ROW EXECUTE FUNCTION bc1.tf_blockiere()")
        conn.commit()
    with caplog.at_level("ERROR"):
        antwort = _turn(client, "m2", "wirr")           # macht das Feld unklar => Abbruch
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "abgebrochen_ohne_identitaet"
    assert "draft_aufraeumen_fehlgeschlagen" in caplog.text
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchall() == [
            ("in_erhebung",)]                            # verwaister Draft bleibt


def test_write_fehler_erzeugt_503_und_der_replay_holt_ihn_nach(umgebung):
    pool, paket = umgebung
    client = _client(umgebung)
    with verbindung(DSN) as conn:                            # fremder Draft im Weg
        conn.execute(
            "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
            "profil_version, process_id, status, erhebung_id, paket_version, profil) "
            "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-02', "
            "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))
        conn.commit()
    assert _turn(client, "m1", "alles").status_code == 503
    with verbindung(DSN) as conn:                            # Betriebsweg K5
        conn.execute("DELETE FROM bc1.prozessprofil WHERE status = 'in_erhebung'")
        conn.commit()
    nachgeholt = _turn(client, "m1", "alles")                # derselbe message_id
    assert nachgeholt.status_code == 200
    assert nachgeholt.json()["status"] == "fertig"
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchall() == [
            ("fertig",)]
```

- [ ] **Step 2: RED**, dann

- [ ] **Step 3: `bc1_service/api.py` erweitern**

```python
from bc1_service.profil_writer import ProfilWriteError

# Diese Keys kommen bei einer fertig-Antwort aus der DB, nicht aus dem Kern
# (Spec K3.3): der Sweep kann Werte und Zaehler veraendert haben, nachdem der
# Kern seine Antwort schon persistiert hatte.
OVERLAY_SCHLUESSEL = ("felder", "vollstaendigkeit", "ungeloeste_felder",
                      "pflicht_erfasst", "pflicht_gesamt", "befunde")

HINWEIS_UNGELOEST = (
    "Hinweis: Eine genannte System-Angabe ist im Verzeichnis des Mandanten nicht "
    "(mehr) vorhanden und wurde entfernt; das betroffene Feld gilt damit als offen.")
HINWEIS_GUELTIG = (
    "Hinweis: Eine genannte System-Kennung ist im Verzeichnis des Mandanten nicht "
    "(mehr) vorhanden und wurde aus der Angabe entfernt; die übrige Angabe bleibt "
    "erhalten.")


def create_app(store, llm, package, snapshot=None, lifespan=None, *,
               company_id: str, writer=None) -> FastAPI:
    ...
            # (nach process_turn, innerhalb des Session-Locks)
            if writer is not None:
                stand = store.load(req.session_id)
                # Nach JEDEM load als Erstes (R12-I1) — auch vor dem Reconcile.
                try:
                    pruefe_mandant(stand, company_id)
                except MandantKonfliktError:
                    raise HTTPException(status_code=409, detail="mandant_konflikt")
                try:
                    db_profil = writer.reconcile(stand, antwort)
                except ProfilWriteError:
                    # Terminal-Postcondition (Spec K3.3): die Antwort wird NICHT
                    # ausgeliefert. Der Retry derselben message_id faehrt den
                    # kompletten Reconcile erneut und antwortet erst nach Erfolg.
                    raise HTTPException(status_code=503,
                                        detail="profil_write_fehlgeschlagen")
                if db_profil is not None:
                    antwort["payload"].update(
                        {k: db_profil[k] for k in OVERLAY_SCHLUESSEL
                         if k in db_profil})
            antwort["chat_text"] = _chat_text(antwort)
            return antwort
```

`_chat_text` für `fertig` erweitern:

```python
def _sweep_hinweise(p: dict) -> str:
    """Fester Zusatz aus dem persistenten Befund — deterministisch, kein LLM.

    Quelle ist ausschliesslich der ueberlagerte Payload; dadurch identisch nach
    Neustart und pro Auslieferung genau einmal (R10-I2).
    """
    befunde = (p.get("befunde") or {}).get("snn_entfernt") or []
    texte: list[str] = []
    for befund in befunde:                       # Paket-Feldreihenfolge
        text = (HINWEIS_UNGELOEST if befund["feld_status_danach"] == "ungeloest"
                else HINWEIS_GUELTIG)
        if text not in texte:                    # dedupliziert (R11-I2)
            texte.append(text)
    return "".join("\n\n" + text for text in texte)


# ... in _chat_text, Zweig "fertig":
        return ((p.get("abschluss_text")
                 or "Danke! Das Interview ist abgeschlossen.")
                + _sweep_hinweise(p)
                + _fortschrittszeile(p))
```

- [ ] **Step 4: `bc1_service/main.py` verdrahten**

```python
from bc1_service.profil_writer import ProfilWriter

_paket = waehle_paket(os.environ, _prozesse, _kontext)

app = create_app(
    _store, waehle_llm(os.environ), _paket, _snapshot,
    lifespan=_lebenszyklus,
    company_id=_company_id,
    writer=ProfilWriter(_profil_pool, _company_id, _paket),
)
```

- [ ] **Step 5: GREEN — volle Suite**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q
```

Erwartet: alles grün, 0 Warnings. Reale Zahlen notieren und berichten.

- [ ] **Step 6: Commit**

```bash
git add bc1-context-discovery/bc1_service bc1-context-discovery/tests/test_api_profil.py
git commit -m "feat(bc1): API-Verdrahtung — Reconcile, DB-Overlay, Post-Sweep-Hinweise, 503-Pfad"
```

---

# Phase E — Betrieb und Abschluss

## Task 16: Betriebsdoku, GRANT-Signal-Vorlage, Gesamtverifikation

**Files:**
- Modify: `bc1_service/n8n/SMOKE.md`
- Create: `bc1_service/db/EINSPIELEN.md`

- [ ] **Step 1: `bc1_service/db/EINSPIELEN.md` schreiben**

Inhalt (kurz und konkret):
1. **Voraussetzungen** — die Rechte aus Abschnitt 0 der DDL, wörtlich als Liste
   (`GRANT REFERENCES` auf companies, ref_prozesse, ref_teilprozesse, mandant_rollen,
   ref_erhebungen · `GRANT SELECT` auf v_bewertung_aktuell, mandant_systeme,
   ref_teilprozesse, companies, v_prozesse_lesen) + Hinweis auf `bc1.profil_write_status`
   (interne Tabelle, kein BC0-Prüfbedarf) — das ist zugleich der **Text fürs
   GRANT-Signal an BC0** (Bündel-Frage #3).
2. **Einspielen:** `psql -v ON_ERROR_STOP=1 -1 -f prozessprofil.sql` als `bc1_role`.
3. **Dreifallregel:** was `NOTICE: Fall 1/2` bedeutet und dass ein `Fall 3`-Abbruch
   nichts verändert hat.
4. **Sollsignatur:** wie sie erzeugt wird und die Betriebsregel bei
   PostgreSQL-Versionswechsel (Task 4, Step 6).
5. **Deploy-Gate:** Supabase erst nach K-C (Zahlen-Wertebereiche mit BC2); GRANT-Signal
   geht erst mit dem Deploy raus.
6. **Offene Rechte-Naht K-B:** Solange Simeon die Lese-Rollen nicht genannt hat, liest
   **niemand außer `bc1_role`** die drei Tabellen — inklusive BC0. Das ist bewusst so
   und muss vor dem Deploy geklärt sein.

- [ ] **Step 2: `SMOKE.md` ergänzen**

- Startvariablen: `BC1_COMPANY_ID` ist **Pflicht** (der Dienst startet sonst nicht),
  Beispielzeile mit Demo-UUID.
- **K5-Betriebsrezept** (verwaister/fremder Draft), wörtlich zum Kopieren:

```sql
-- Verwaisten in_erhebung-Draft gezielt loeschen (fertige Zeilen sind gesperrt).
SELECT company_id, focus_step_id, profil_version, erstellt_am
  FROM bc1.prozessprofil WHERE status = 'in_erhebung';

DELETE FROM bc1.prozessprofil
 WHERE company_id = '<UUID>' AND focus_step_id = '<KP-XX.TP-N>'
   AND profil_version = <n> AND status = 'in_erhebung';
-- Danach reconcilet die aktive Session beim naechsten Turn von selbst.
```

- **Startmengen-Ehrlichkeit:** Zwischen Dienststart und Interview neu angelegte
  Teilprozesse oder Systeme kennt der Validator nicht (statische Mengen) — Neustart
  lädt nach; laufende Sessions bekommen dann 409 `paket_konflikt`.
- **503 `profil_write_fehlgeschlagen`:** was es heißt (Antwort wurde bewusst nicht
  ausgeliefert) und dass die Wiederholung derselben `message_id` der richtige Weg ist.
- **Demo-Snippet nachziehen:** Der `create_app(...)`-Aufruf im Fake-Demo-Block der
  SMOKE.md (Toy-Paket) kennt `company_id` noch nicht und würde mit `TypeError`
  scheitern — `company_id=DEMO_MANDANT` ergänzen (Codex R1-I5).

- [ ] **Step 3: Gesamtverifikation — erst NACH Task 15** (Codex R5-N5-I1)

Die folgenden Nachweise brauchen den fertigen Writer; vor der K-A-Antwort sind sie
nicht erbringbar. Steps 1–2 (Betriebsdoku) sind davon unabhängig und können sofort
laufen.

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q -W error
```

Und die fünf Erfolgskriterien der Spec einzeln durchgehen und im Bericht belegen:
1. Suite grün inkl. aller neuen Verträge; Bestandstests unverändert.
2. FakeLLM-Interview mit TP-Auswahl bis `fertig` ⇒ genau eine eingefrorene Zeile mit
   korrekten typisierten Spalten (nur `gueltig`-Werte), `erhebung_id`, JSON.
3. 503-Nachweis: Abschluss-Write-Fehler ⇒ 503; Replay derselben `message_id` holt den
   Write nach und liefert dann die gespeicherte Antwort.
4. Trigger-Nachweise am Container (Freeze, UNIQUE, Versionsfolge, Kaskade).
5. DDL identisch einspielbar in Test-Container (Supabase erst nach dem Deploy-Gate).

- [ ] **Step 4: Commit**

```bash
git add bc1-context-discovery/bc1_service/db/EINSPIELEN.md bc1-context-discovery/bc1_service/n8n/SMOKE.md
git commit -m "docs(bc1): Einspiel-Anleitung, GRANT-Signal-Vorlage und K5-Betriebsrezept"
```

---

# Was dieser Plan NICHT baut (nachgehalten, Spec-Roadmap)

| Punkt | Anker / nächster Schritt |
|---|---|
| Einstiegspunkt `company_id`/Anfrage-Bezug per API (Multi-Tenant) | Etappe 2 |
| Voller Baseline-/Rollen-Lesepfad (#148), Rollen-Auswahl im Interview, Befüllung `bc1.profil_rollen` | Etappe 2 |
| **B6 `process_category`-Umbau** | Etappe 2 (braucht `ref_prozesse`-Lesepfad + `SCHEMA_VERSION`-Erhöhung); Simeon informieren |
| `zeitanteil_pct`-Erhebung | Zeitanteil-Semantik ist Termin-Punkt 3 |
| Strukturierte System-Erfassung (S-NN als echte Auswahl statt Freitext-Prüfung) | Etappe 2 |
| Zwischenstands-Updates des Profil-JSON je Turn | nach Etappe 2 bewerten (YAGNI) |
| Outbox/Reconciler-Prozess | erst falls der 503-Weg operativ nicht reicht |
| `SECURITY DEFINER`-Prüfpfad für die S-NN-Restlücke | nur falls die Restlücke je stört |
| Automatische Auflösung verwaister Drafts | K5 bleibt manuell (YAGNI) |
| Echt-Gegenprobe gegen Supabase (SMOKE, echter Profil-Write auf den Demo-Mandanten) | sobald Projektreferenz + DSN da sind und K-C entschieden ist |

# Offene Klärpunkte (blockieren einzelne Tasks, nicht den Plan)

| # | Frage | An | Blockiert |
|---|---|---|---|
| K-A | `erhebung_id`-Regel (a: mehrere aktuelle Erhebungen · b: Teilprozess ohne Bewertung) | Simeon, Bündel #1 | **Task 13 — und damit 14 + 15** |
| K-B | GRANT-Signal inkl. Lese-Rollen für `bc1.prozessprofil` · **neu: brauchen wir `SELECT` auf `ref_erhebungen`?** (s. Task 13) | Simeon, Bündel #3 | Supabase-Deploy, nicht den Bau |
| K-C | Zahlen-Wertebereiche (0 zulässig? Präzision) | BC2 | finale CHECKs, nicht die DDL-Struktur |
| K-D | Company-UUID im Snapshot-Export | Simeon, Bündel #2 | nur den Snapshot-Abgleich der Startprüfung |

# Changelog Rev. 9 (Bau-Befund Task 3 — am Container gefunden, nicht im Review)

**Gefunden beim Ausfuehren von Task 3, nicht beim Lesen.** Nach 8 Codex-Runden READY —
der Fehler zeigte sich erst, als die DDL wirklich lief. 18 Tests gruen, 2 rot:

    ForeignKeyViolation: update or delete on table "mandant_rollen" violates
    foreign key constraint "profil_rollen_rolle_fk" on table "profil_rollen"

**Tragweite: die DSGVO-Loeschkaskade war blockiert.** `DELETE FROM companies` ist der
Loeschweg K5; er waere in Etappe 2 (sobald `profil_rollen` befuellt wird) hart
gescheitert. Der Plan war in sich widerspruechlich: seine eigenen Tests verlangten die
durchlaufende Kaskade, seine DDL verhinderte sie.

**Ursache, am Container gemessen (postgres:16), nicht angenommen:**
`profil_rollen` wird erst auf Kaskadentiefe 2 geraeumt (companies -> prozessprofil ->
profil_rollen), waehrend `mandant_rollen` schon auf Tiefe 1 verschwindet und seine
NO-ACTION-Pruefung sofort ausgewertet wird. Die Verletzung ist also nur transient
innerhalb der Loeschtransaktion. Reproduziert auch mit nackten Tabellen ohne unsere
Trigger — der Freeze-Mechanismus ist unbeteiligt.

| FK-Modus | DSGVO-Kaskade | einzelne mandant_rolle | unbekannte rolle_id |
|---|---|---|---|
| `NO ACTION` (Rev. 8) | **blockiert** | blockiert | blockiert |
| `DEFERRABLE INITIALLY IMMEDIATE` | **blockiert** | blockiert | blockiert |
| `DEFERRABLE INITIALLY DEFERRED` | laeuft | blockiert | blockiert |

**Fix:** `profil_rollen_rolle_fk` auf `DEFERRABLE INITIALLY DEFERRED`. Beide
Schutzwirkungen bleiben erhalten — die Kur kostet nichts ausser dem Zeitpunkt der
Fehlermeldung. `ON DELETE CASCADE` waere falsch gewesen (wuerde Zeilen aus einem
eingefrorenen Profil entfernen; `tf_freeze_rollen` wuerde es ohnehin als Exception
werfen), `INITIALLY IMMEDIATE` wirkungslos (gemessen).

**Zwei Regressionstests ergaenzt**, weil die Luecke im Testsatz selbst lag:
- `test_dsgvo_kaskade_raeumt_ein_voll_befuelltes_profil` — die bisherigen
  Kaskaden-Tests liessen `process_owner_rolle_id` leer und deckten damit nicht ab,
  was in Etappe 2 der Normalfall ist.
- `test_einzelne_mandant_rolle_bleibt_trotz_deferrable_geschuetzt` — nagelt fest,
  dass die Verzoegerung keine Schutzwirkung kostet.

**Mitgemessen, damit es nicht offen bleibt:** die uebrigen BC1->BC0-Fremdschluessel
(`prozessprofil_owner_rolle_fk` und die anderen) laufen bei der Mandantenloeschung
durch, weil `prozessprofil` direkt an `companies` haengt und damit auf Tiefe 1
verschwindet — dieselbe Tiefen-Logik, nur zu unseren Gunsten. Sie bleiben unveraendert.
Weil "haengt an der Feuerreihenfolge" der eigentliche Verdacht war, wurde das nicht
geglaubt, sondern erschuettert: die companies-referenzierenden Constraints wurden in
vier Varianten neu angelegt (unveraendert · nur der bc1-FK neu · nur mandant_rollen neu ·
alle BC0-FKs neu, sodass der bc1-FK zuerst feuert). **Alle vier laufen durch.** Die
Korrektheit haengt also an der Kaskadentiefe, nicht an der Constraint-Anlagereihenfolge.

## Zweitmeinung: Codex-Runde 9 (Job task-mt8svn65-m0p0mr) — WITH FIXES (1C/3I/2M)

**Adjudiziert, nicht blind uebernommen.** Vorher wurde das Queue-Modell durch
VORHERSAGE validiert (nicht nur nachtraeglich erklaert): Beim `DELETE FROM companies`
stehen die Kaskaden aller direkt referenzierenden Tabellen in EINER Startqueue
(Reihenfolge nach Triggername); was sie ausloesen, wird HINTEN angehaengt. Daraus
folgte die pruefbare Vorhersage, dass `profil_rollen_rolle_fk` auch OHNE DEFERRABLE
durchlaeuft, sobald der bc1-Kaskadentrigger zuerst feuert. **Beide Vorhersagen sind
am Container eingetroffen** (bc1 zuletzt => BLOCK, bc1 zuerst => DURCH).

- **C1 „die uebrigen sechs FKs haengen auch an der Reihenfolge" — NICHT uebernommen,
  mit Begruendung.** Codex' Gegenvorschlag (alle sieben `DEFERRABLE INITIALLY
  IMMEDIATE` plus `SET CONSTRAINTS ... DEFERRED` vor dem Firmen-DELETE) setzt voraus,
  dass WIR das DELETE ausfuehren. Das tut BC0 — wir koennen dort kein `SET CONSTRAINTS`
  erzwingen, also traegt die Variante nicht. Und die sechs Pruefungen *auf*
  `prozessprofil` koennen nach dem validierten Queue-Modell nicht zu frueh feuern: sie
  werden von Kaskaden angehaengt, die selbst in der Startqueue stehen, waehrend
  `prozessprofil` ueber seinen eigenen `ON DELETE CASCADE` bereits in dieser Startqueue
  liegt. Vier verschiedene Constraint-Anlagereihenfolgen wurden gemessen, alle laufen
  durch. Alle sechs auf `INITIALLY DEFERRED` zu stellen wuerde dagegen die
  Fehlerlokalitaet des Writers (Tasks 13-15) verschlechtern: jeder falsche
  `process_id`/`focus_step_id`/`erhebung_id` schluege erst beim COMMIT zu.
  **Statt Uebernahme abgesichert:** `test_kaskadentests_laufen_im_unguenstigsten_fall`
  nagelt fest, dass der bc1-Kaskadentrigger ZULETZT feuert — der spaetestmoegliche
  Zeitpunkt und damit der unguenstigste Fall. Kippt diese Reihenfolge je, schlaegt der
  Test an, statt dass die Kaskaden-Tests unbemerkt nur noch den bequemen Fall pruefen.
  **RICHARD-ENTSCHEIDUNG 25.08.: so lassen, der Reihenfolge-Test sichert ab.**
  Damit ist der Punkt entschieden und wird nicht neu verhandelt. Bewusst getragenes
  Restrisiko: das Queue-Modell ist dokumentiertes PostgreSQL-Verhalten, aber keine
  Standard-Zusage. Frueherkennung liegt bei
  `test_kaskadentests_laufen_im_unguenstigsten_fall` — schlaegt der an, ist diese
  Entscheidung neu zu bewerten, nicht der Test anzupassen.
- **I2 „Kaskadentiefe ist nicht die normative Ursache" — uebernommen.** Praeziser:
  `CASCADE` und `NO ACTION` sind beides RI-Constraint-Trigger; die unmittelbare
  `NO ACTION`-Pruefung kann vor einem noch ausstehenden Loeschast feuern. Die Tiefe
  macht die beobachtete Reihenfolge plausibel, die Garantie liefert die Queue.
- **I3 „migriert bestehende Installationen nicht" — geprueft, bereits gedeckt.**
  `pg_get_constraintdef` gibt `DEFERRABLE INITIALLY DEFERRED` mit aus (am Container
  nachgesehen), die Sollsignatur aus Task 4 enthaelt es also. Ein Altbestand mit
  nicht-aufschiebbarem FK landet damit in **Fall 3** und bricht mit Diff ab, statt
  still den falschen Constraint zu behalten. Kein zusaetzliches `ALTER TABLE` noetig.
- **I4 „Testabdeckung beweist die Eigenschaft nicht" — uebernommen.** Der
  Vollprofil-Test setzt jetzt ALLE sieben kreuzenden Referenzen (inkl. `upstream`/
  `downstream`); dazu zwei neue Tests: `test_unbekannte_rolle_id_wird_weiterhin_
  abgewiesen` (die Behauptung „DEFERRED kostet keine Schutzwirkung" war unbelegt) und
  `test_kaskadentests_laufen_im_unguenstigsten_fall` (s. C1).
  **Offen bleibt Codex' Punkt zum Ausschnitt-Charakter des BC0-Geruests** — weitere
  kreuzende NO-ACTION-FKs oder `BEFORE DELETE`-Trigger in nicht enthaltenen
  BC0-Tabellen kann unser Test nicht ausschliessen. Gehoert vor den Supabase-Deploy
  gegen die echte DB geprueft (nachgehalten bei den Deploy-Voraussetzungen).
- **M5 Writer-Verhalten / M6 `ON DELETE CASCADE` waere falsch** — beide bestaetigen
  die getroffene Wahl; `SET CONSTRAINTS ... IMMEDIATE` ist der richtige Kontrollpunkt
  und steht im DDL-Kommentar.

**Folge fuer Etappe 2 (im DDL-Kommentar vermerkt):** FK-Fehler auf `profil_rollen`
schlagen jetzt beim COMMIT zu, nicht beim INSERT. Wer sie frueher braucht, setzt
`SET CONSTRAINTS bc1.profil_rollen_rolle_fk IMMEDIATE`.

# Changelog Rev. 8 (Codex-Runde 7, Job task-mt88pzcw-kjqjqz — WITH FIXES, 0 Critical)

- **N6-C1 endgültig geklärt:** Codex hat die Container-Messung an der PostgreSQL-16-
  Dokumentation und am RI-Quellcode (`ri_triggers.c`, `RI_PLAN_CASCADE_ONDELETE`)
  gegengeprüft und als **WIDERLEGT** bestätigt: Die Referenzaktion wechselt temporär
  zum Eigentümer der referenzierenden Tabelle. Beide Tabellen gehören `bc1_role`, und
  ein Eigentümerwechsel würde von der Sollsignatur bemerkt.
- **N7-I1 — mein neuer Rollentrennungs-Test hätte nie das DELETE erreicht:** Er legte
  das Profil sofort als `fertig` an und wollte danach eine Rollenzeile einfügen — die
  weist der Rollen-Freeze korrekt ab. Jetzt in der richtigen Reihenfolge: Draft →
  Rollenzeile → einfrieren → löschen. (Task 3)

# Changelog Rev. 7 (Codex-Runde 6, Job task-mt88hkjo-l3cv0j — WITH FIXES, 1 Critical)

**N6-C1 — am Container GEMESSEN und damit widerlegt.** Codex' Befund: `tf_freeze_rollen`
liest `bc1.prozessprofil`; da die Funktion `SECURITY INVOKER` ist und fremde Rollen kein
Recht auf `bc1.*` haben, müsse BC0s DSGVO-Löschung an `permission denied` scheitern —
der Kaskadentest verdecke das, weil er als Superuser löscht. Die Prämisse stimmt nicht:

| Messung (postgres:16) | Ergebnis |
|---|---|
| `bc0_loescher`: `SELECT` auf `bc1.prozessprofil` · `USAGE` auf Schema `bc1` | **false · false** |
| Rollen-Trigger während der Kaskade läuft als | **`bc1_role`** (Eigentümer der referenzierenden Tabelle) |
| Kaskade als dieses rechtelose Konto | **durchgelaufen**, 0 Rest in beiden Tabellen |

PostgreSQL führt FK-Kaskaden mit den Rechten des **Tabelleneigentümers** aus, nicht mit
denen des Löschenden. Zusatzbefund: Wenn der Rollen-Trigger läuft, ist die Profilzeile
bereits weg — die Ausnahme greift also aus zwei unabhängigen Gründen.

**Trotzdem übernommen — Codex' Testvorschläge sind wertvoll**, weil sie genau diese
Annahme festnageln, statt sie zu glauben. Neu in Task 3:
- Kaskade **als eingeschränktes BC0-Löschkonto** (mit Vorab-Assertion, dass das Konto
  wirklich rechtelos ist) — ein Superuser-DELETE könnte den Fall nie zeigen;
- fremdes `DELETE` direkt auf einer Rollenzeile einer `fertig`-Version muss prallen;
- Draft-Löschung räumt die Rollenzeile mit (Betriebsweg K5 bleibt unberührt).

Der Trigger-Kommentar trägt die Messung mit PG-Version — damit ein späterer Leser die
Rechteannahme nicht neu erraten muss.

# Changelog Rev. 6 (Codex-Runde 5, Job task-mt88810p-2kg9vl — WITH FIXES, 0 Critical)

**Important**
1. **N5-I2 — die Freeze-Ausnahme ging doch schärfer, meine „unvermeidbar"-Einschätzung
   war falsch.** Codex' Vorschlag: zusätzlich prüfen, ob der Elternsatz schon weg ist.
   **Am Container gemessen statt geglaubt** (postgres:16): bei der DSGVO-Kaskade ist die
   `companies`-Zeile für die Abfrage im Trigger bereits unsichtbar (`depth=2`,
   `eltern=weg`), bei einem fremden Trigger-DELETE steht sie noch (`depth=2`,
   `eltern=da`), beim direkten DELETE ist `depth=1`. Beide Trigger tragen jetzt die
   zweite Bedingung; ein fremdes Trigger-DELETE prallt damit ab. Neuer Test dafür.
   **Damit ist das letzte bewusst offene Restrisiko geschlossen.** (Task 3)
2. **N5-I1 — Task 16 war zu weit als „vor K-A ausführbar" bezeichnet:** Steps 1–2
   (Betriebsdoku) ja, Step 3 (Gesamtverifikation) braucht die Tasks 13–15. Kopf und
   Task 16 sagen das jetzt getrennt.

**Von Codex bestätigt:** der HTTP-Aufräumtest erreicht den Abbruchpfad jetzt wirklich
(Turn 1 bleibt aktiv, die gültige Zweitnennung setzt `UNKLAR`, am Rundenlimit greift der
Guard) · der Funktions-ACL-Regressionsfall wirkt · der präzisierte Gerüst-Anspruch (C3)
ist für die aktuelle BC1-Oberfläche haltbar — mit dem Merkposten, dass das Gerüst
mitwachsen muss, sobald ein weiterer Lesepfad dazukommt (z. B. `mandant_systeme.aktiv`).

# Changelog Rev. 5 (Codex-Runde 4, Job task-mt87zdub-r3dy2g — WITH FIXES, 0 Critical)

Runde 4 hat alle vier Runde-3-Findings und die erweiterte Funktionssignatur als
VERIFIED bestätigt. Eingearbeitet:

**Important**
1. **N4-I1 — mein neuer HTTP-Aufräumtest wäre nie beim Abbruch angekommen:** Das
   Testpaket hatte nur EIN Pflichtfeld, also war die Session schon nach Turn 1 fertig
   und Turn 2 hätte 409 bekommen statt des Abbruchs. Jetzt zwei Pflichtfelder, mit
   ausdrücklicher Zwischenprüfung nach Turn 1 (`status == "frage"`, Draft
   `in_erhebung`, Bindung vorhanden). (Task 15)
2. **N4-I2 — „nicht ohne Rückfrage ausführbar" (K-A-Gate):** Sachlich richtig, aber
   keine Plan-Lücke — es ist die externe Abhängigkeit, die die Spec selbst benennt.
   **Adjudiziert: nicht durch mich behebbar.** Die Gate-Lage steht jetzt im Kopf des
   Dokuments: Tasks 1–12 und 16 sind heute ausführbar, 13–15 brauchen K-A.

**Minor**
1. Regressionsfall für die neue Funktions-ACL ergänzt (`REVOKE EXECUTE … FROM PUBLIC`
   muss als `funktion_acl|tf_freeze_profil` im Diff auftauchen). (Task 4)

**Adjudizierte TEILWEISE-Punkte (bewusst nicht weiter gefixt):**
- **C3 (Gerüst „reduziert"):** Der Anspruch ist jetzt präzise formuliert statt
  überdehnt — definitionsgleich für alles, was BC1 berührt; nicht berührte
  Zusatzspalten fehlen bewusst. Sie können keinen falschen Grünstand erzeugen, weil
  unser SQL sie nie nennt — anders als ein abweichender Spaltenname, der genau das
  täte (der ursprüngliche C3-Fund). Wächst der Lesepfad in Etappe 2, wächst das
  Gerüst mit.
- **C2 (Freeze-Ausnahme):** Restrisiko damals benannt — **in Rev. 6 geschlossen**,
  s. Changelog Rev. 6. Stand Rev. 5: PostgreSQL bietet keinen
  Kaskaden-Nachweis. Die Mandantenkaskade inkl. `profil_rollen` ist von Codex als
  funktionierend bestätigt.

# Changelog Rev. 4 (Codex-Runde 3, Job task-mt87mce1-g92mgn — WITH FIXES, 0 Critical)

**Erste Runde ohne Critical.** Runde 3 hat alle drei Criticals und sieben der neun
Runde-2-Findings als VERIFIED bestätigt. Eingearbeitet:

**Important**
1. **N3-I1 — mein Fixture-Fix hatte einen Test überholt:** Mandant B bekam den
   B-exklusiven `KP-02.TP-2`, der Teilprozess-Test verlangte aber weiter identische
   ID-Mengen für A und B. Der Test vergleicht jetzt die gemeinsame Menge und erwartet
   die Zusatz-ID bei B ausdrücklich. (Task 8)
2. **N3-I2 — zwei DDL-Tests prüften einen Text, den es nicht mehr gab:** Beim Umbau auf
   „Mehrbestand ist auch Fall 3" war „Teilbestand" aus der Fehlermeldung verschwunden.
   Der Wortlaut trägt das Wort wieder. (Task 4)
3. **Rest aus I4/N-I6:** Der Aufräum-Fehler wird jetzt zusätzlich **über `/turn`**
   nachgewiesen — HTTP 200, Logeintrag und verbleibender `in_erhebung`-Draft in einem
   Test, wie K4 es verlangt. (Task 15)
4. **Rest aus I2/N-I2:** Die Sollsignatur erfasst zusätzlich Funktions-Eigentümer,
   Funktions-ACL (`EXECUTE` liegt per Default bei PUBLIC), `prokind`, `proleakproof`
   und `proretset`. (Task 4)
5. **Rest aus C3:** `v_prozesse_lesen` im Testgerüst führt jetzt auch `sponsor_ids` —
   die Bezeichnung „wortgleich übernommen" stimmt damit wieder. (Task 2)

**Minor**
1. Step 5 sagte „Abschnitte 2 und ebenso 3 und 4", Step 6 legt Abschnitt 4 korrekt
   außerhalb fest — jetzt einheitlich „Abschnitte 2 und 3". (Task 4)
2. Die Lebensdauer der Temp-Objekte ist korrekt beschrieben: die beiden TEMP-Tabellen
   verschwinden mit dem Commit, die TEMP VIEW erst mit der Session (Views kennen kein
   `ON COMMIT DROP`); beide Einspielwege beenden die Session direkt danach. (Task 4)

**Damals offen (in Rev. 6 geschlossen):** Die Freeze-Ausnahme ließ zu diesem Zeitpunkt
jedes verschachtelte `DELETE` durch, nicht nur BC0s Kaskade — PostgreSQL bietet keinen
Kaskaden-Nachweis an. Codex bestätigt, dass die Mandantenkaskade inklusive
`profil_rollen` durchläuft.

# Changelog Rev. 3 (Codex-Runde 2, Job task-mt87eow1-nt75jc — NO, 3C/6I/1M)

Runde 2 hat die 14 Fixes aus Runde 1 nachgeprüft: **8 VERIFIED** (C4, C5, C6, C7, I1,
I3, I5, I6, M1), **5 TEILWEISE** (C2, C3, I2, I4), **1 OFFEN** (C1). Daraus:

**Critical**
1. **N-C1 — das BC0-Gerüst wäre gar nicht gelaufen.** Zwei echte Baufehler in meiner
   Runde-1-Korrektur: `v_prozesse_lesen` liest `p.beschreibung`, die Spalte fehlte
   (sie kommt per `ALTER TABLE` aus `schema_v1.2` — nachgeprüft), und der
   `mandant_rollen`-Insert war aus der Mandantenschleife herausgerutscht
   (`IndentationError`). Beides behoben; zusätzlich gibt es jetzt **KP-03 nur bei
   Mandant B** als saubere Probe für den Mandantenfilter. (Task 2)
2. **N-C2 — Fall 2 war immer noch kein No-op:** Der Rechte-Abschnitt stand hinter dem
   Guard statt darin, `REVOKE`/`GRANT` wären also auch im Identisch-Fall gelaufen.
   Abschnitt 3 liegt jetzt ausdrücklich IM `DO $einspielen$`-Block; außerhalb steht nur
   noch die lesende Nachprüfung. (Task 4, Step 6)
3. **N-C3 — die Vorprüfung hätte fremde Objekte löschen können:** die unqualifizierten
   `DROP … IF EXISTS bc1_soll_signatur/bc1_ist_signatur/bc1_einspiel_modus` treffen über
   den Suchpfad auch gleichnamige **permanente** Objekte — eine Änderung VOR der
   Prüfung, also genau das, was die Dreifallregel verbietet. Die DROPs sind raus; die
   Temp-Objekte tragen `ON COMMIT DROP` und werden `pg_temp`-qualifiziert angesprochen.
   (Task 4)

**Important**
1. No-op-Test vergleicht zusätzlich `pg_class.xmin` und `pg_description.xmin` — und der
   Text sagt jetzt klar, dass der Nachweis den Kontrollfluss ergänzt, nicht ersetzt.
2. Sollsignatur: Funktionsidentität (`pg_get_function_identity_arguments`, Rückgabetyp),
   `proisstrict`/`proparallel`, `acl.is_grantable`; Mehrbestand ist jetzt ebenfalls
   Fall 3 (`vorhanden <> 9` statt `< 9`).
3. **Der neue Prozent-Validator konnte werfen** — `PROZENT_0_100.validator("70,5")` ist
   wahr, `Decimal("70,5")` wirft. Der Test verdeckte das, weil er vorher normalisierte.
   **Diesen Punkt habe ich parallel selbst gefunden und am Interpreter reproduziert.**
   Jetzt eine benannte, try/except-gesicherte Prüffunktion (Feldtyp-Verträge sind total)
   plus Test mit unnormalisierten Werten.
4. E4 wird **nur im Kontext-Zweig** ganzzahlig — der kontextfreie Zweig behält Semantik
   UND Version `1.0`. (Sonst hätte sich Bedeutung unter unveränderter Version geändert.)
5. Der neue LLM-Ausfall-Test erwartete eine Exception, die der Kern fängt; er prüft jetzt
   `fehler_fortsetzbar` im Frage-Turn und den LLM-freien Abbruch im Terminal-Turn.
6. Restliche K4-Lücken: Mandanten-KP-Lookup über einen B-exklusiven KP · Aufräum-Fehler
   **am Draft** injiziert (beweist „Draft bleibt") · Neustart nach committeter Bindung ·
   DB-Nachweis, dass `s-01` als `S-01` gespeichert wird.

**Minor**
1. Fragile Testzahlen im Plan durch „alle grün" ersetzt.

**Von Codex ausdrücklich als tragfähig bestätigt:** die drei Dollar-Quoting-Ebenen
(`$einspielen$`/`$ddl$`/`$fn$`), die Sichtbarkeit von `bc1_ist_signatur` zum
Prüfzeitpunkt, der Savepoint-Zuschnitt in `_umbinden`/`_einfuegen`, der
if/elif-Kontrollfluss und das durchgereichte `mitgesendete_version` (legitimer
ctx-Recovery-Replay bleibt möglich).

**Damals als Restrisiko benannt (in Rev. 6 geschlossen):** Die Freeze-Ausnahme ließ
JEDES verschachtelte `DELETE` durch, nicht nur die BC0-Kaskade. In diesem Schema gibt es
kein anderes Trigger-DELETE; ein Test hält den Zustand fest. Eine schärfere Prüfung
bräuchte einen Kaskaden-Nachweis, den PostgreSQL nicht anbietet.

# Changelog Rev. 2 (Codex-Review-Runde 1, Job task-mt84rugd-jiggxj — NO, 7C/6I/1M)

Alle Findings wurden **erst nachgeprüft, dann übernommen** (u. a. am BC0-Schema auf
`origin/main`, an `bc1_core/feldtypen.py` und am laufenden Interpreter):

**Critical**
1. **Fall 2 war kein No-op** — `CREATE OR REPLACE FUNCTION/TRIGGER`, `COMMENT`,
   `REVOKE`/`GRANT` schreiben den Katalog neu. Abschnitte 2–4 laufen jetzt nur noch im
   Anlage-Fall (Modus-Flag `bc1_einspiel_modus` + Klammer-`DO`-Block); neuer Test
   `test_fall_2_ruehrt_den_katalog_nicht_an` vergleicht `xmin`/ACL vor und nach dem
   zweiten Lauf. (Task 4, Steps 4–6)
2. **`pg_trigger_depth() > 1` war zu breit** — die Ausnahme galt für jede
   Verschachtelung und jede Operation. Jetzt **nur `TG_OP = 'DELETE'`**; neuer Test mit
   einem fremden Trigger, der ein UPDATE auslöst. Restlücke (fremdes Trigger-DELETE)
   ist im Code benannt. (Task 3)
3. **BC0-Gerüst war nicht schema-identisch** — verifiziert: die Spalte heißt
   `sub_process_name` (nicht `step_name`), `bitkom_bewertungen.id` ist `varchar(28)`
   mit Muster-CHECK, `stufe` 1–5, `ref_items` hat `kriterium`/`frage`,
   `prozess_personen.funktion` kennt `mitwirkend`/`vertretung`, `ref_prozesse.kategorie`
   ist ein NOT-NULL-Enum. Gerüst, Testdaten und der TP-Lookup sind angeglichen; die
   Teilprozess-Namen sind jetzt mandantenspezifisch (der Test war intern widersprüchlich).
   (Tasks 2, 8)
4. **`70,5 %` hätte eine fertige Session dauerhaft in 503 gesetzt** — der bestehende
   `PROZENT_0_100` lässt Dezimalstellen zu, die `integer`-Spalte nicht. Neuer
   paketlokaler Feldtyp `PROZENT_GANZ_0_100` für E4 (Validator = Spaltenregel, wie es
   der Brief verlangt). Meine Behauptung „`int(Decimal('70.5'))` schlägt fehl" war
   falsch — sie ist raus. (Tasks 9, 10, 11)
5. **Rebind-Konflikt hätte den eigenen Draft verloren** — Löschen und Neuanlage liegen
   jetzt in EINEM Savepoint (`_umbinden`); neuer Test
   `test_rebind_konflikt_laesst_den_alten_draft_stehen`. (Task 14)
6. **Reihenfolge 13/14 war nicht baubar** — der Writer ruft `erhebung_id()` beim Anlegen
   jeder Zeile. `erhebung_id` ist jetzt **Task 13**, der Reconcile **Task 14**, mit
   hartem K-A-Gate davor: **Phase D endet real nach Task 12, solange K-A offen ist.**
7. **Der zusätzliche State-Reload lief ohne Mandanten-Guard** — `pruefe_mandant()` läuft
   jetzt nach JEDEM `load`, auch im Fehlerzweig des Kerns und vor dem Writer-Aufruf.
   (Tasks 6, 15)

**Important**
1. Recovery-Replay verlangt jetzt die **mitgesendete alte `schema_version`** (`None` ⇒
   kein Recovery); die Request-Version wird bis in den Kern durchgereicht. (Tasks 6, 7)
2. Sollsignatur erweitert: Existenzprüfung über **alle neun** Vertragsobjekte,
   `pg_proc`-Merkmale (Sprache, SECURITY, Volatilität, Konfiguration),
   Identity/Generated bei Spalten, ACL über `aclexplode` (jeder Grantee inkl. PUBLIC)
   **plus** die effektive Sicht. Vier neue Fall-3-Tests. (Task 4)
3. Zwei widersprüchliche Tests korrigiert: `session_id` ist globaler Primärschlüssel
   (Fremdmandanten-Test umgebaut) · der Sweep-Test für `ungeloest` nutzt jetzt eine
   alleinstehende Kennung. (Tasks 14, 15)
4. Fehlende K4-Tests ergänzt: parallele Versionsvergabe · Kaskade mit Rollenzeilen ·
   TP-Verbund-FK über Mandantengrenze · trigger-induziertes UPDATE · A→B aktiv und
   terminal ohne Bindung · `gueltig → unklar` ohne Löschung und mit Abbruch ·
   Aufräum-Fehler mit `caplog` · Rebind-Konflikt · KP-Feld ohne Rebind ·
   `S-99 → Nachfrage-Limit → fertig` · Neustart-Test für den Sweep-Hinweis ·
   503-Recovery nach Neustart mit geändertem ctx · Mapping-Vollständigkeit und alle
   Nicht-`gueltig`-Status. (Tasks 3, 7, 11, 12, 14, 15)
5. `bc1_core/cli.py` und das Demo-Snippet in `SMOKE.md` ziehen die neuen Signaturen
   nach. (Tasks 6, 16)
6. `profil_rollen_genau_eine_quelle` als XOR gegen den getrimmten Freitext — wörtlich
   nach Brief Abschnitt 3. (Task 3)

**Minor**
1. Branch wird direkt auf `058a77e` gepinnt statt über `pull --ff-only`. (Task 1)

**Ohne Befund geblieben** (von Codex ausdrücklich geprüft): der Numeric-CHECK schließt
negative Werte, `±Infinity` und — wegen PostgreSQLs Ordnung — auch `NaN` aus · mehrere
parameterlose Statements in einem psycopg-3-`execute()` · `Jsonb` · `RETURNING` nach
einem BEFORE-Trigger · verschachteltes `conn.transaction()` als Savepoint.

# Selbstprüfung des Plans (durchgeführt)

- **Spec-Abdeckung:** K0 → Tasks 5–7 · K1 → Tasks 3–4 (+ Fixture Task 2) · K2 →
  Tasks 9–10 · K3 → Tasks 11–15 (13 = `erhebung_id`, 14 = Reconcile) · K4 → Tests in
  jedem Task (Trigger-Verträge, Writer-Verträge, Mandantentrennung, Completion-Guard,
  Dreifallregel) · K5 → Task 16.
- **Präzisierungen gegenüber der Spec** stehen oben unter „Ehrliche Präzisierungen"
  (Parameter `company_id` — inzwischen plus `mitgesendete_version` —, State-Reload in
  der API, Lesepfade als freie Funktionen), dazu die **Lesart** zum Konvertierungsfehler
  in Task 11 (jetzt mit Voraussetzung: Feldtyp an die Spalte angleichen) und die
  **Rechte-Entscheidung** in Task 4 (`bc_leser` auch auf `prozessprofil` entzogen).
  Codex hat sie in Runde 1 als vertretbar beurteilt — bis auf die Konvertierungslesart,
  die deshalb ihre Voraussetzung bekommen hat.
- **Ein neuer Befund während des Planens:** Für `erhebung_id` fehlt uns `SELECT` auf
  `ref_erhebungen` — die „jüngste" Erhebung ist deshalb nur über `v_bewertung_aktuell`
  bestimmbar (Task 13). Das schärft Bündel-Frage #1/#3.
- **Typkonsistenz geprüft:** `Ergebnis`/`Decision.ergebnis` (Task 5) → `core.py`
  (Task 6) → `api.py` (Task 7) · `Bc0Kontext` (Task 10) → `ProfilWriter` (Task 14) ·
  `baue_profilinhalt`/`wende_sweep_an` (Tasks 11/12) → `_abgleich` (Task 14) ·
  `OVERLAY_SCHLUESSEL` (Task 15) deckt genau die Keys, die `profil_payload` +
  `_zaehler_neu` + `befunde` erzeugen.
