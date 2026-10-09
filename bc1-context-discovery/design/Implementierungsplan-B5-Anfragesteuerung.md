# B5 Anfragesteuerung — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BC1 interviewt nur noch zu einer BC0-Anfrage (`BC1_ANFRAGE_ID`, Pflicht), bietet nur deren Teilprozesse an und schreibt die Anfragenummer in `bc1.prozessprofil.anfrage_id`.

**Architecture:** Die Anfrage wird wie der Mandant beim Dienststart eingestellt und fließt in den `Bc0Kontext` (Auswahl + Fingerabdruck). Die Sitzung trägt `anfrage_id` im JSON-Zustand; ein eigener Anfrage-Guard (wie der Mandanten-Guard) läuft vor dem Recovery-Replay. Die Datenbank bekommt eine nullable Spalte mit Format-CHECK über eine Umstellungseinheit nach dem Muster von `prozessprofil_d3.sql`.

**Tech Stack:** Python 3.11, FastAPI, psycopg 3 / psycopg_pool, pytest, PostgreSQL 17 (Test-Container), uv.

**Spec:** `bc1-context-discovery/design/Spec-B5-Anfragesteuerung.md` (abgenommen 05.10.2026, nach agy-Zweitmeinung überarbeitet).

## Global Constraints

- Arbeitsverzeichnis für alle Befehle: `coe-factory/bc1-context-discovery/`; Zweig `bc1-b5-anfragesteuerung`.
- Tests: `uv run pytest …`; DB-Tests brauchen `BC1_TEST_DB_DSN` (lokaler PG-17-Container), sonst skippen sie.
- **TDD-Guard aktiv, NIE umgehen.** Bei einem Block das Skill `tdd-guard` aufrufen; jeden neu gelösten Block dort in die Lessons-Tabelle eintragen.
- **Ein neuer Test je Edit** (Guard-Regel „Multiple test addition“): Die Testblöcke eines Steps einzeln einfügen, jeweils RED laufen lassen, dann die Implementierung für genau diesen RED. Die Code-Blöcke unten zeigen den Endstand eines Steps, nicht einen einzigen Edit.
- **Bestandsaufrufer mitziehen:** Jede Signaturänderung wird in allen Aufrufern im selben Task nachgezogen — gefunden per `git grep -n '<name>('` über `bc1_core bc1_service tests`.
- `BC1_ANFRAGE_ID` ist Pflicht, Format `^A-[0-9]{4}-[0-9]{2}$` (BC0-CHECK `ref_anfragen.anfrage_id`, v1.4).
- Interviewbar nur Status `zugeordnet` oder `im_interview`.
- Kein Fremdschlüssel auf `ref_anfragen`; kein Status-Recheck vor dem Freeze; keine Spalte in `bc1.sessions`; `sessions.sql` bleibt unverändert; C4 (b) NICHT in B5.
- Lesen aus BC0 nur über Sichten, immer mit `company_id`-Filter.
- Deutsche Anführungszeichen („ “) nie in Python-String-Literale; Meldungstexte mit `'…'`.
- Kein Push, kein PR, kein Posten auf GitHub ohne OK der BC1-Projektleitung. Live-Skripte (`lauf.sh`) startet die BC1-Projektleitung.
- Commit-Nachrichten enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Alt-Sitzung aus der Zeit vor B5** im Store (kein `anfrage_id` im JSON) trifft auf einen B5-Dienst → erwartet 409 `anfrage_konflikt`, nie ein stilles Weiterlaufen. *Test in Task 4.*
2. **Gleiche Anfragenummer bei einem anderen Mandanten** (IDs wiederholen sich mandantenübergreifend) → Start mit Mandant A darf die Anfrage von B nicht finden („unbekannt“). *Test in Task 3.*
3. **Kernprozess-Bezug mit teils stillgelegtem Teilprozess** → stillgelegter TP erscheint nicht in der Auswahl; **direkt zugeordneter, stillgelegter TP** → Startabbruch mit diesem TP in der Liste. *Tests in Task 3.*
4. **`BC1_ANFRAGE_ID` mit Kleinbuchstaben oder Leerzeichen** (`a-2026-03`, ` A-2026-03 `) → Kleinbuchstaben werden abgewiesen (BC0-Muster ist case-sensitiv), Leerzeichen am Rand werden entfernt. *Test in Task 3.*
5. **Wiederholter Abschluss (Recovery-Replay) in einer Instanz mit anderer Anfrage** → 409 `anfrage_konflikt`, obwohl der ctx-Hash-Unterschied den Paket-Guard passieren darf. *Test in Task 4.*

---

## Dateistruktur

| Datei | Änderung | Verantwortung |
|---|---|---|
| `tests/db/bc0_geruest.sql` | ändern | BC0-Anfrageobjekte (Ausschnitt) + zwei Sichten wortgleich |
| `tests/db_fixture.py` | ändern | Testanfragen; Einspielreihenfolge mit `prozessprofil_b5.sql` |
| `bc1_service/bc0_lesepfade.py` | ändern | `anfrage_status`, `anfrage_teilprozesse` |
| `bc1_service/start.py` | ändern | `lies_anfrage_id`, `lade_kontext(…, anfrage_id)`, Meldungen |
| `bc1_service/discovery_paket.py` | ändern | `Bc0Kontext.anfrage_id`, Fingerabdruck |
| `bc1_service/main.py` | ändern | Verdrahtung `BC1_ANFRAGE_ID` |
| `bc1_core/types.py`, `bc1_core/serialize.py` | ändern | `SessionState.anfrage_id` + Rundlauf |
| `bc1_core/core.py` | ändern | `AnfrageKonfliktError`, `pruefe_anfrage`, `process_turn(…, anfrage_id)` |
| `bc1_service/api.py` | ändern | Guard vor Replay, 409 `anfrage_konflikt` |
| `bc1_service/db/prozessprofil_b5.sql` | **neu** | Umstellungseinheit M0–M3 |
| `bc1_service/db/prozessprofil.sql` | ändern | Spalte + CHECK, Rechte-Vorprüfung, Sollsignatur |
| `bc1_service/profil_writer.py` | ändern | `anfrage_id` beim Anlegen schreiben |
| `bc1_service/db/EINSPIELEN.md`, `bc1_service/n8n/SMOKE.md`, `README.md` | ändern | Betrieb |
| `tests/test_*.py` | erweitern; neu `tests/test_ddl_b5_spalte.py` | Nachweise |
| `.superpowers/sdd/Implementierungsplan-DB-Profil-Fundament/struktur_bc0.sql`, `lauf.sh` | ändern (lokal, nicht im Repo-Tracking prüfen) | Live-Messung und Live-Lauf |

---

### Task 0: Live-Struktur der Anfrage-Sichten messen (vor jedem Code)

**Files:**
- Modify: `coe-factory/.superpowers/sdd/Implementierungsplan-DB-Profil-Fundament/struktur_bc0.sql`

**Interfaces:** Produces: Messausgabe (live vs. Repo) als Grundlage für Task 1. Weicht live von den Repo-Dateien ab → **anhalten, der BC1-Projektleitung melden, nicht anpassen.**

- [ ] **Step 1: Messblock ergänzen** — am Ende von `struktur_bc0.sql` anhängen:

```sql
-- B5 (05.10.2026): Anfrage-Objekte, die BC1 ab B5 liest
SELECT 'sicht|' || c.relname || '|' || md5(pg_get_viewdef(c.oid, true))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relname IN ('v_anfrage_prozessbezug', 'v_anfrage_teilprozesse')
 ORDER BY 1;
SELECT 'sichtspalte|' || table_name || '|' || column_name || '|' || data_type
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name IN ('v_anfrage_prozessbezug', 'v_anfrage_teilprozesse')
 ORDER BY table_name, ordinal_position;
SELECT 'recht|' || t || '|' || has_table_privilege('bc1_role', t, 'SELECT')
  FROM unnest(ARRAY['v_anfrage_prozessbezug', 'v_anfrage_teilprozesse']) AS t ORDER BY 1;
SELECT 'check|' || conname || '|' || pg_get_constraintdef(oid)
  FROM pg_constraint WHERE conname IN ('ck_anfrage_status') ORDER BY 1;
```

- [ ] **Step 2: Die BC1-Projektleitung startet die Messung** (Claude liest `ZUGAENGE-LOKAL.env` nie):

```bash
./lauf.sh sql struktur_bc0.sql
```

- [ ] **Step 3: Gegen Container vergleichen** — dasselbe Skript gegen den Test-Container laufen lassen, nachdem Task 1 das Gerüst erweitert hat; Mengen-Diff der `sicht|`/`sichtspalte|`/`recht|`-Zeilen muss leer sein (wie bei A7). Ergebnis in den Zwischenbericht.

---

### Task 1: Gerüst und Testdaten um die Anfrage erweitern

**Files:**
- Modify: `tests/db/bc0_geruest.sql` (nach `v_systeme_lesen`, vor „Schema bc1 + Rechte“)
- Modify: `tests/db_fixture.py` (`_testdaten`, Konstanten)
- Test: `tests/test_db_fixture.py`

**Interfaces:**
- Produces: Tabellen `ref_anfragen` (Ausschnitt), `anfrage_prozesse`, `gate_paket_inhalt` (Stummel), Sichten `v_gate_freigabe_aktuell` (Stummel), `v_anfrage_prozessbezug`, `v_anfrage_teilprozesse`; Fixture-Konstanten `ANFRAGE_A = "A-2026-01"` (Mandant A, `zugeordnet`, Haupt-TP KP-01.TP-1 + beteiligt KP-01.TP-2), `ANFRAGE_A_KERNPROZESS = "A-2026-02"` (A, `im_interview`, Kernprozess KP-01 ohne TP), `ANFRAGE_A_EINGEGANGEN = "A-2026-03"` (A, `eingegangen`, kein Bezug), `ANFRAGE_A_UNBEWERTET = "A-2026-04"` (A, `zugeordnet`, TP KP-01.TP-3 = nur verworfen bewertet), `ANFRAGE_A_OHNE_TP = "A-2026-05"` (A, `zugeordnet`, `process_id` KP-02 gesetzt, aber **keine** Zeile in `anfrage_prozesse` — Altbestand vor v2.7), `ANFRAGE_B = "A-2026-01"` existiert auch bei Mandant B (gleiche ID!, `zugeordnet`, KP-02.TP-2).

- [ ] **Step 1: Failing test** — in `tests/test_db_fixture.py` ergänzen:

```python
@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_anfrage_sichten_sind_fuer_bc1_role_lesbar_und_mandantengetrennt():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        a = conn.execute(
            "SELECT sub_process_id FROM v_anfrage_teilprozesse "
            "WHERE company_id = %s AND anfrage_id = %s ORDER BY 1",
            (MANDANT_A, ANFRAGE_A)).fetchall()
        b = conn.execute(
            "SELECT sub_process_id FROM v_anfrage_teilprozesse "
            "WHERE company_id = %s AND anfrage_id = %s ORDER BY 1",
            (MANDANT_B, ANFRAGE_B)).fetchall()
        status = conn.execute(
            "SELECT status FROM v_anfrage_prozessbezug "
            "WHERE company_id = %s AND anfrage_id = %s",
            (MANDANT_A, ANFRAGE_A_EINGEGANGEN)).fetchone()
    assert a == [("KP-01.TP-1",), ("KP-01.TP-2",)]
    assert b == [("KP-02.TP-2",)]
    assert status == ("eingegangen",)


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_kernprozess_bezug_loest_nur_aktive_teilprozesse_auf():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("UPDATE ref_teilprozesse SET aktiv = false "
                     "WHERE company_id = %s AND sub_process_id = 'KP-01.TP-3'", (MANDANT_A,))
        conn.commit()
    with verbindung(DSN) as conn:
        tps = conn.execute(
            "SELECT sub_process_id FROM v_anfrage_teilprozesse "
            "WHERE company_id = %s AND anfrage_id = %s ORDER BY 1",
            (MANDANT_A, ANFRAGE_A_KERNPROZESS)).fetchall()
    assert tps == [("KP-01.TP-1",), ("KP-01.TP-2",)]
```

Imports oben ergänzen: `from tests.db_fixture import ANFRAGE_A, ANFRAGE_A_EINGEGANGEN, ANFRAGE_A_KERNPROZESS, ANFRAGE_B` (zur bestehenden Importzeile).

- [ ] **Step 2: Lauf, erwartet FAIL** — `uv run pytest tests/test_db_fixture.py -k anfrage -v` → ImportError `ANFRAGE_A`.

- [ ] **Step 3: Gerüst erweitern** — in `tests/db/bc0_geruest.sql` nach `v_systeme_lesen` einfügen:

```sql
-- ---------- Anfrage (B5, 05.10.2026) — Ausschnitt; Sichten wortgleich ----------
-- ref_anfragen: nur die Spalten, die v_anfrage_prozessbezug/_teilprozesse brauchen.
-- originaltext, steller_id u. a. fehlen bewusst — BC1 liest sie nicht.
CREATE TABLE ref_anfragen (
    company_id       uuid NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    anfrage_id       text NOT NULL CHECK (anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}$'),
    eingang_am       date NOT NULL,
    process_id       text,
    sub_process_id   text,
    zuordnung_quelle text,
    status           text NOT NULL DEFAULT 'eingegangen',
    PRIMARY KEY (company_id, anfrage_id),
    CONSTRAINT ck_anfrage_status
      CHECK (status IN ('eingegangen','zugeordnet','im_interview','am_gate','uebergeben',
                        'bewertet','beauftragt','erledigt','abgelehnt'))
);

-- v2.7 Z. 57-84 (ohne Trigger ap_haupt_spiegeln/historie — das Gerüst pflegt
-- ref_anfragen.process_id in den Testdaten selbst konsistent).
CREATE TABLE anfrage_prozesse (
  bezug_id         BIGSERIAL PRIMARY KEY,
  company_id       UUID        NOT NULL,
  anfrage_id       TEXT        NOT NULL,
  process_id       VARCHAR(8)  NOT NULL,
  sub_process_id   VARCHAR(16),
  rolle            TEXT        NOT NULL DEFAULT 'beteiligt'
                   CHECK (rolle IN ('haupt','beteiligt')),
  zuordnung_quelle TEXT        NOT NULL
                   CHECK (zuordnung_quelle IN ('anfrage','vorschlag_bc0','vorschlag_bc1','interview')),
  angelegt_am      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_ap_anfrage FOREIGN KEY (company_id, anfrage_id)
    REFERENCES ref_anfragen (company_id, anfrage_id) ON DELETE CASCADE,
  CONSTRAINT fk_ap_prozess FOREIGN KEY (company_id, process_id)
    REFERENCES ref_prozesse (company_id, process_id) ON DELETE CASCADE,
  CONSTRAINT fk_ap_teilprozess FOREIGN KEY (company_id, sub_process_id)
    REFERENCES ref_teilprozesse (company_id, sub_process_id) ON DELETE CASCADE,
  CONSTRAINT ck_ap_tp_gehoert_kp CHECK (sub_process_id IS NULL OR sub_process_id LIKE process_id || '.%')
);

-- Stummel: v_anfrage_teilprozesse liest Freigabe und Paketinhalt. Im Gerüst leer —
-- BC1 nutzt freigegeben/im_paket nicht; die Typen folgen v1.4/v2.6.
CREATE TABLE gate_paket_inhalt (
  company_id           uuid   NOT NULL,
  paket_id             uuid   NOT NULL,
  sub_process_id       text   NOT NULL,
  freigabe_ereignis_id bigint NOT NULL,
  anfrage_id           text,
  PRIMARY KEY (company_id, paket_id, sub_process_id)
);
CREATE VIEW v_gate_freigabe_aktuell AS
SELECT NULL::uuid AS company_id, NULL::text AS sub_process_id, NULL::text AS stand,
       NULL::bigint AS ereignis_id, NULL::timestamptz AS entschieden_am
 WHERE false;

-- v2.3 Z. 143-153, wortgleich
CREATE OR REPLACE VIEW v_anfrage_prozessbezug AS
SELECT company_id,
       anfrage_id,
       process_id,
       sub_process_id,
       zuordnung_quelle,
       eingang_am,
       status
  FROM ref_anfragen;

-- v2.7 Z. 129-154, wortgleich
CREATE OR REPLACE VIEW v_anfrage_teilprozesse AS
WITH bezuege AS (
  SELECT p.company_id, p.anfrage_id, p.process_id, p.rolle, p.zuordnung_quelle,
         coalesce(p.sub_process_id, t.sub_process_id) AS sub_process_id,
         (p.sub_process_id IS NULL) AS aus_kernprozess
    FROM anfrage_prozesse p
    LEFT JOIN ref_teilprozesse t
      ON p.sub_process_id IS NULL
     AND t.company_id = p.company_id AND t.process_id = p.process_id AND t.aktiv
)
SELECT DISTINCT ON (b.company_id, b.anfrage_id, b.sub_process_id)
       b.company_id, b.anfrage_id, b.process_id, b.sub_process_id, b.rolle,
       b.zuordnung_quelle, b.aus_kernprozess,
       (f.stand = 'freigegeben')                       AS freigegeben,
       f.ereignis_id                                   AS freigabe_ereignis_id,
       f.entschieden_am,
       EXISTS (SELECT 1 FROM gate_paket_inhalt i
                WHERE i.company_id = b.company_id AND i.anfrage_id = b.anfrage_id
                  AND i.sub_process_id = b.sub_process_id
                  AND i.freigabe_ereignis_id = f.ereignis_id) AS im_paket
  FROM bezuege b
  LEFT JOIN v_gate_freigabe_aktuell f
    ON f.company_id = b.company_id AND f.sub_process_id = b.sub_process_id
 WHERE b.sub_process_id IS NOT NULL
 ORDER BY b.company_id, b.anfrage_id, b.sub_process_id,
          (b.rolle = 'haupt') DESC, b.aus_kernprozess;
```

Und im Rechteblock ergänzen:

```sql
GRANT SELECT ON v_anfrage_prozessbezug TO bc_leser;                     -- v2.3 Z. 153
GRANT SELECT ON v_anfrage_teilprozesse TO bc_leser;                     -- v2.7 Z. 323
```

Vor dem Commit: beide Sichtentexte mit `diff` gegen `../bc0-baseline-onboarding/app/schema_v2.3_anfrage_ohne_prozessbezug.sql:143-153` und `schema_v2.7_anfrage_prozesse_und_uebergabe.sql:129-154` prüfen (wortgleich).

- [ ] **Step 4: Testdaten** — in `tests/db_fixture.py` Konstanten oben ergänzen:

```python
# B5: Anfragen. ANFRAGE_B hat BEWUSST dieselbe ID wie ANFRAGE_A — BC0-IDs wiederholen
# sich ueber Mandanten; ein fehlender company_id-Filter faellt nur so auf.
ANFRAGE_A = "A-2026-01"
ANFRAGE_A_KERNPROZESS = "A-2026-02"
ANFRAGE_A_EINGEGANGEN = "A-2026-03"
ANFRAGE_A_UNBEWERTET = "A-2026-04"
ANFRAGE_A_OHNE_TP = "A-2026-05"
ANFRAGE_B = "A-2026-01"
```

und am Ende von `_testdaten` (nach den Bewertungen):

```python
    conn.execute(
        "INSERT INTO ref_anfragen (company_id, anfrage_id, eingang_am, process_id, "
        "sub_process_id, zuordnung_quelle, status) VALUES "
        "(%s, %s, '2026-09-01', 'KP-01', 'KP-01.TP-1', 'anfrage', 'zugeordnet'), "
        "(%s, %s, '2026-09-02', 'KP-01', NULL, 'anfrage', 'im_interview'), "
        "(%s, %s, '2026-09-03', NULL, NULL, NULL, 'eingegangen'), "
        "(%s, %s, '2026-09-04', 'KP-01', 'KP-01.TP-3', 'anfrage', 'zugeordnet'), "
        "(%s, %s, '2026-09-05', 'KP-02', NULL, 'anfrage', 'zugeordnet'), "
        "(%s, %s, '2026-09-05', 'KP-02', 'KP-02.TP-2', 'anfrage', 'zugeordnet')",
        (MANDANT_A, ANFRAGE_A, MANDANT_A, ANFRAGE_A_KERNPROZESS,
         MANDANT_A, ANFRAGE_A_EINGEGANGEN, MANDANT_A, ANFRAGE_A_UNBEWERTET,
         MANDANT_A, ANFRAGE_A_OHNE_TP, MANDANT_B, ANFRAGE_B))
    conn.execute(
        "INSERT INTO anfrage_prozesse (company_id, anfrage_id, process_id, sub_process_id, "
        "rolle, zuordnung_quelle) VALUES "
        "(%s, %s, 'KP-01', 'KP-01.TP-1', 'haupt', 'anfrage'), "
        "(%s, %s, 'KP-01', 'KP-01.TP-2', 'beteiligt', 'anfrage'), "
        "(%s, %s, 'KP-01', NULL, 'haupt', 'anfrage'), "
        "(%s, %s, 'KP-01', 'KP-01.TP-3', 'haupt', 'anfrage'), "
        "(%s, %s, 'KP-02', 'KP-02.TP-2', 'haupt', 'anfrage')",
        (MANDANT_A, ANFRAGE_A, MANDANT_A, ANFRAGE_A, MANDANT_A, ANFRAGE_A_KERNPROZESS,
         MANDANT_A, ANFRAGE_A_UNBEWERTET, MANDANT_B, ANFRAGE_B))
```

- [ ] **Step 5: Lauf, erwartet PASS** — `uv run pytest tests/test_db_fixture.py -v`; danach volle DB-Suite `uv run pytest -q` (das Gerüst darf nichts Bestehendes brechen).

- [ ] **Step 6: Task 0 Step 3 ausführen** (Container-Messung, Diff gegen Live).

- [ ] **Step 7: Commit**

```bash
git add tests/db/bc0_geruest.sql tests/db_fixture.py tests/test_db_fixture.py
git commit -m "BC1 B5: Gerüst um Anfrage-Sichten (v2.3/v2.7 wortgleich) und Testanfragen erweitert

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Lesepfade für Status und Teilprozesse der Anfrage

**Files:**
- Modify: `bc1_service/bc0_lesepfade.py` (ans Ende)
- Test: `tests/test_bc0_lesepfade.py`

**Interfaces:**
- Consumes: Task 1 (Sichten, Testdaten).
- Produces: `anfrage_status(conn, company_id: str, anfrage_id: str) -> str | None`; `anfrage_teilprozesse(conn, company_id: str, anfrage_id: str) -> list[str]` (sortiert, ohne Namen).

- [ ] **Step 1: Failing tests**

```python
def test_anfrage_status_ist_mandantengefiltert():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.anfrage_status(conn, MANDANT_A, ANFRAGE_A_EINGEGANGEN) == "eingegangen"
        # A-2026-03 gibt es nur bei A — bei B ist sie unbekannt.
        assert bc0_lesepfade.anfrage_status(conn, MANDANT_B, ANFRAGE_A_EINGEGANGEN) is None


def test_anfrage_teilprozesse_kommen_aus_der_anfrage_und_nicht_vom_nachbarmandanten():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.anfrage_teilprozesse(conn, MANDANT_A, ANFRAGE_A) == [
            "KP-01.TP-1", "KP-01.TP-2"]
        assert bc0_lesepfade.anfrage_teilprozesse(conn, MANDANT_B, ANFRAGE_B) == ["KP-02.TP-2"]
```

(Import `ANFRAGE_A, ANFRAGE_A_EINGEGANGEN, ANFRAGE_B, MANDANT_B` aus `tests.db_fixture` ergänzen; die Datei hat bereits `pytestmark` für DSN.)

- [ ] **Step 2: Lauf, erwartet FAIL** — `uv run pytest tests/test_bc0_lesepfade.py -k anfrage -v` → `AttributeError: anfrage_status`.

- [ ] **Step 3: Implementierung** — ans Ende von `bc0_lesepfade.py`:

```python
def anfrage_status(conn, company_id: str, anfrage_id: str) -> str | None:
    """Status der Anfrage (B5) — None, wenn es sie bei DIESEM Mandanten nicht gibt.
    Anfrage-IDs wiederholen sich ueber Mandanten (A-JJJJ-NN je Mandant)."""
    zeile = conn.execute(
        "SELECT status FROM v_anfrage_prozessbezug "
        " WHERE company_id = %s AND anfrage_id = %s", (company_id, anfrage_id)).fetchone()
    return zeile[0] if zeile else None


def anfrage_teilprozesse(conn, company_id: str, anfrage_id: str) -> list[str]:
    """Teilprozess-IDs der Anfrage (B5). Die Sicht loest einen Kernprozess-Bezug in
    seine AKTIVEN Teilprozesse auf; einen direkt zugeordneten TP liefert sie auch
    stillgelegt — den Abgleich mit dem Lesepfad macht start.lade_kontext."""
    return [zeile[0] for zeile in conn.execute(
        "SELECT sub_process_id FROM v_anfrage_teilprozesse "
        " WHERE company_id = %s AND anfrage_id = %s ORDER BY sub_process_id",
        (company_id, anfrage_id)).fetchall()]
```

Docstring der Modulkopfzeile „die sechs, die Etappe 1 braucht“ → „die Lesepfade, die der Dienst braucht (Etappe 1 + B5)“.

- [ ] **Step 4: Lauf, erwartet PASS** — `uv run pytest tests/test_bc0_lesepfade.py -v`.

- [ ] **Step 5: Commit** — `git commit -m "BC1 B5: Lesepfade anfrage_status und anfrage_teilprozesse …"` (mit Co-Authored-By).

---

### Task 3: Start mit Anfrage — Pflicht, Prüfungen, Auswahl, Fingerabdruck

**Files:**
- Modify: `bc1_service/start.py`, `bc1_service/discovery_paket.py:40-62`, `bc1_service/main.py`
- Test: `tests/test_start.py`, `tests/test_discovery_paket.py`

**Interfaces:**
- Consumes: Task 2.
- Produces: `lies_anfrage_id(umgebung: Mapping[str, str]) -> str`; `lade_kontext(conn, company_id: str, anfrage_id: str) -> Bc0Kontext`; `Bc0Kontext.anfrage_id: str | None = None` (letztes Feld, Default nur für kontextfreie Tests); Konstanten `INTERVIEWBARE_STATUS`, `MELDUNG_ANFRAGE_UNBEKANNT`, `MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW`, `MELDUNG_ANFRAGE_OHNE_TEILPROZESSE`, `MELDUNG_TEILPROZESSE_NICHT_BEREIT` (alle `str.format`-Vorlagen).

- [ ] **Step 1: Failing tests** — in `tests/test_start.py` (Importe ergänzen: `lies_anfrage_id`, die vier Meldungen, `ANFRAGE_*`, `MANDANT_B`):

```python
def test_fehlende_anfrage_id_ist_ein_startfehler():
    with pytest.raises(RuntimeError) as fehler:
        lies_anfrage_id({})
    assert "BC1_ANFRAGE_ID" in str(fehler.value)


@pytest.mark.parametrize("roh", ["a-2026-03", "A-26-03", "A-2026-3", "Anfrage 3"])
def test_anfrage_id_in_falscher_form_ist_ein_startfehler(roh):
    with pytest.raises(RuntimeError) as fehler:
        lies_anfrage_id({"BC1_ANFRAGE_ID": roh})
    assert "A-JJJJ-NN" in str(fehler.value)


def test_anfrage_id_wird_von_raendern_befreit():
    assert lies_anfrage_id({"BC1_ANFRAGE_ID": "  A-2026-03 "}) == "A-2026-03"


def test_wortlaut_der_anfrage_meldungen_ist_festgenagelt():
    assert MELDUNG_ANFRAGE_UNBEKANNT.format(anfrage_id="A-2026-09") == (
        "Die Anfrage A-2026-09 gibt es bei diesem Mandanten nicht. "
        "BC1_ANFRAGE_ID prüfen.")
    assert MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW.format(
        anfrage_id="A-2026-09", status="am_gate") == (
        "Die Anfrage A-2026-09 steht auf 'am_gate'. Interviewt wird nur eine Anfrage "
        "im Stand 'zugeordnet' oder 'im_interview'.")
    assert MELDUNG_ANFRAGE_OHNE_TEILPROZESSE.format(anfrage_id="A-2026-09") == (
        "Die Anfrage A-2026-09 ist keinem Teilprozess zugeordnet. Das Interview kann "
        "erst geführt werden, wenn BC0 die Anfrage zugeordnet hat.")
    assert MELDUNG_TEILPROZESSE_NICHT_BEREIT.format(
        anfrage_id="A-2026-09", liste="KP-01.TP-3") == (
        "Zur Anfrage A-2026-09 sind diese Teilprozesse nicht bewertet oder stillgelegt: "
        "KP-01.TP-3. BC0 übergibt eine Anfrage nur vollständig — das Interview startet "
        "erst, wenn alle bewertet und aktiv sind.")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_auswahl_sind_genau_die_teilprozesse_der_anfrage_mit_namen():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        kontext = lade_kontext(conn, MANDANT_A, ANFRAGE_A)
    assert kontext.teilprozesse == (("KP-01.TP-1", "Erfassen A"), ("KP-01.TP-2", "Pruefen A"))
    assert kontext.anfrage_id == ANFRAGE_A


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_unbekannte_anfrage_und_fremde_anfrage_brechen_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, "A-2026-99")
        assert str(fehler.value) == MELDUNG_ANFRAGE_UNBEKANNT.format(anfrage_id="A-2026-99")
        # A-2026-03 gibt es nur bei A — Mandant B darf sie nicht finden.
        with pytest.raises(RuntimeError):
            lade_kontext(conn, MANDANT_B, ANFRAGE_A_EINGEGANGEN)


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_anfrage_im_falschen_stand_bricht_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A_EINGEGANGEN)
    assert str(fehler.value) == MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW.format(
        anfrage_id=ANFRAGE_A_EINGEGANGEN, status="eingegangen")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_unbewerteter_teilprozess_der_anfrage_bricht_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A_UNBEWERTET)
    assert str(fehler.value) == MELDUNG_TEILPROZESSE_NICHT_BEREIT.format(
        anfrage_id=ANFRAGE_A_UNBEWERTET, liste="KP-01.TP-3")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_stillgelegter_direkt_zugeordneter_teilprozess_bricht_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("UPDATE ref_teilprozesse SET aktiv = false "
                     "WHERE company_id = %s AND sub_process_id = 'KP-01.TP-2'", (MANDANT_A,))
        conn.commit()
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A)
    assert str(fehler.value) == MELDUNG_TEILPROZESSE_NICHT_BEREIT.format(
        anfrage_id=ANFRAGE_A, liste="KP-01.TP-2")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_anfrage_ohne_teilprozesse_bricht_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A_OHNE_TP)
    assert str(fehler.value) == MELDUNG_ANFRAGE_OHNE_TEILPROZESSE.format(
        anfrage_id=ANFRAGE_A_OHNE_TP)


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_kernprozess_bezug_ohne_bewertung_aller_tps_bricht_ab():
    # A-2026-02 = ganzer KP-01 -> TP-1, TP-2, TP-3; TP-3 ist nur verworfen bewertet.
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A_KERNPROZESS)
    assert "KP-01.TP-3" in str(fehler.value)
```

**Alle vier** bestehenden Aufrufe in `test_start.py` um `ANFRAGE_A` erweitern: Z. 32 `lade_kontext(conn, MANDANT_A, ANFRAGE_A)`, Z. 43 `lade_kontext(conn, "99999999-9999-9999-9999-999999999999", ANFRAGE_A)`, Z. 73 `(conn, leer, ANFRAGE_A)`, Z. 93 `(conn, ohne, ANFRAGE_A)` (agy F2: `pytest.raises(RuntimeError)` fängt den `TypeError` sonst nicht). `test_kontext_kommt_mandantengefiltert_aus_der_db` erwartet danach `["KP-01.TP-1", "KP-01.TP-2"]` (Anfrage statt Mandantenliste) — die Erwartung bewusst anpassen und im Kommentar begründen.

`tests/test_postgres_init.py` — neben `test_main_ohne_company_id_meldet_die_fehlende_variable` (Z. 125) den Zwilling nach demselben Muster:

```python
def test_main_ohne_anfrage_id_meldet_die_fehlende_variable(monkeypatch):
    monkeypatch.setenv("BC1_DB_DSN", "postgresql://x@localhost/y")
    monkeypatch.setenv("BC1_COMPANY_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.delenv("BC1_ANFRAGE_ID", raising=False)
    monkeypatch.delitem(sys.modules, "bc1_service.main", raising=False)
    with pytest.raises(RuntimeError) as fehler:
        importlib.import_module("bc1_service.main")
    assert "BC1_ANFRAGE_ID" in str(fehler.value)
```

(Imports/DSN-Wert wie im Zwilling Z. 125–132 übernehmen, falls dort abweichend.)

`tests/test_api_profil.py` Z. 373–377 (`test_main_verdrahtet_writer_…`): `monkeypatch.setenv("BC1_ANFRAGE_ID", ANFRAGE_A)` ergänzen und `assert gesehen["anfrage_id"] == ANFRAGE_A` (agy F3; `ANFRAGE_A` aus `tests.db_fixture` importieren).

In `tests/test_discovery_paket.py` ergänzen:

```python
def test_fingerabdruck_reagiert_auf_die_anfrage():
    basis = Bc0Kontext(company_id="11111111-1111-1111-1111-111111111111",
                       teilprozesse=(("KP-01.TP-1", "Erfassen"),), system_ids=("S-01",),
                       anfrage_id="A-2026-01")
    andere = replace(basis, anfrage_id="A-2026-02")
    assert (baue_discovery_paket(kontext=basis).schema_version
            != baue_discovery_paket(kontext=andere).schema_version)
```

(`from dataclasses import replace` ergänzen, falls nicht vorhanden.)

- [ ] **Step 2: Lauf, erwartet FAIL** — `uv run pytest tests/test_start.py tests/test_discovery_paket.py -v` → ImportError `lies_anfrage_id`.

- [ ] **Step 3: `discovery_paket.py`** — `Bc0Kontext` um das letzte Feld ergänzen und den Fingerabdruck erweitern:

```python
    system_ids: tuple[str, ...]
    # B5: die Anfrage, zu der interviewt wird. None nur in kontextfreien Tests —
    # main.py setzt sie immer (BC1_ANFRAGE_ID ist Pflicht).
    anfrage_id: str | None = None
```

```python
    roh = json.dumps(
        {"anfrage": kontext.anfrage_id,
         "company_id": kontext.company_id.lower(),
         "kp": sorted(kp_ids),
         "snn": sorted(kontext.system_ids),
         "tp": sorted(tp for tp, _ in kontext.teilprozesse)},
        sort_keys=True, separators=(",", ":"))
```

Kommentar am Fingerabdruck ergänzen: „Die Anfrage ist Teil der Paketidentität. Den Schutz gegen eine fremde Anfrage trägt aber `pruefe_anfrage` (core) — der Recovery-Replay darf einen abweichenden ctx-Hash passieren.“

- [ ] **Step 4: `start.py`** — Imports `import re`; Konstanten und Funktionen:

```python
INTERVIEWBARE_STATUS = ("zugeordnet", "im_interview")   # = anfrage_am_gate_nachziehen()
_ANFRAGE_MUSTER = re.compile(r"A-[0-9]{4}-[0-9]{2}")   # BC0 ck auf ref_anfragen (v1.4)

MELDUNG_ANFRAGE_UNBEKANNT = (
    "Die Anfrage {anfrage_id} gibt es bei diesem Mandanten nicht. "
    "BC1_ANFRAGE_ID prüfen.")
MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW = (
    "Die Anfrage {anfrage_id} steht auf '{status}'. Interviewt wird nur eine Anfrage "
    "im Stand 'zugeordnet' oder 'im_interview'.")
MELDUNG_ANFRAGE_OHNE_TEILPROZESSE = (
    "Die Anfrage {anfrage_id} ist keinem Teilprozess zugeordnet. Das Interview kann "
    "erst geführt werden, wenn BC0 die Anfrage zugeordnet hat.")
MELDUNG_TEILPROZESSE_NICHT_BEREIT = (
    "Zur Anfrage {anfrage_id} sind diese Teilprozesse nicht bewertet oder stillgelegt: "
    "{liste}. BC0 übergibt eine Anfrage nur vollständig — das Interview startet "
    "erst, wenn alle bewertet und aktiv sind.")


def lies_anfrage_id(umgebung: Mapping[str, str]) -> str:
    roh = umgebung.get("BC1_ANFRAGE_ID", "").strip()
    if not roh:
        raise RuntimeError(
            "BC1_ANFRAGE_ID ist nicht gesetzt — BC1 interviewt nur zu einer Anfrage "
            'von BC0. Beispiel: export BC1_ANFRAGE_ID="A-2026-03"')
    if not _ANFRAGE_MUSTER.fullmatch(roh):
        raise RuntimeError(f"BC1_ANFRAGE_ID='{roh}' hat nicht die Form A-JJJJ-NN.")
    return roh


def lade_kontext(conn, company_id: str, anfrage_id: str) -> Bc0Kontext:
    if not bc0_lesepfade.mandant_existiert(conn, company_id):
        raise RuntimeError(
            f"Mandant {company_id} existiert nicht in companies — "
            "BC1_COMPANY_ID pruefen.")
    if not bc0_lesepfade.teilprozesse(conn, company_id):
        raise RuntimeError(MELDUNG_KEINE_TEILPROZESSE)
    bewertete = dict(bc0_lesepfade.bewertete_teilprozesse(conn, company_id))
    if not bewertete:
        raise RuntimeError(MELDUNG_KEINE_BEWERTUNG)
    status = bc0_lesepfade.anfrage_status(conn, company_id, anfrage_id)
    if status is None:
        raise RuntimeError(MELDUNG_ANFRAGE_UNBEKANNT.format(anfrage_id=anfrage_id))
    if status not in INTERVIEWBARE_STATUS:
        raise RuntimeError(MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW.format(
            anfrage_id=anfrage_id, status=status))
    soll = bc0_lesepfade.anfrage_teilprozesse(conn, company_id, anfrage_id)
    if not soll:
        raise RuntimeError(MELDUNG_ANFRAGE_OHNE_TEILPROZESSE.format(anfrage_id=anfrage_id))
    # Regel 7 (BC0): uebergeben wird eine Anfrage nur vollstaendig. Ein TP ohne
    # Bewertung oder stillgelegt blockiert sie dauerhaft — das sagt der Start, nicht
    # das dritte Interview.
    fehlend = [tp for tp in soll if tp not in bewertete]
    if fehlend:
        raise RuntimeError(MELDUNG_TEILPROZESSE_NICHT_BEREIT.format(
            anfrage_id=anfrage_id, liste=", ".join(fehlend)))
    return Bc0Kontext(
        company_id=company_id,
        teilprozesse=tuple((tp, bewertete[tp]) for tp in soll),
        system_ids=tuple(bc0_lesepfade.system_ids(conn, company_id)),
        anfrage_id=anfrage_id)
```

Modul-Docstring ergänzen: „Seit B5 (05.10.2026) ist BC1_ANFRAGE_ID ebenfalls Pflicht: angeboten werden nur die Teilprozesse dieser Anfrage.“

- [ ] **Step 5: `main.py`** — Import `lies_anfrage_id`; nach `_company_id = …` die Zeile `_anfrage_id = lies_anfrage_id(os.environ)`; `lade_kontext(_conn, _company_id, _anfrage_id)`; `create_app(…, anfrage_id=_anfrage_id, …)` (Parameter entsteht in Task 4 — bis dahin den Aufruf in Task 4 Step 6 nachziehen). Docstring: „Pflicht: BC1_DB_DSN, BC1_COMPANY_ID, BC1_ANFRAGE_ID.“

- [ ] **Step 5b: Use-Case-Testprofile auf die Anfrage umstellen** (agy F1 — Werkzeug + 7 DB-Tests brechen sonst). Jeder `Fall` trägt schon `anfrage_id` (`use_case_testprofile.py:46-54`, bisher nur dokumentarisch). `schreibe_testprofile` lädt Kontext, Paket und Writer **je Fall**:

```python
def schreibe_testprofile(pool, company_id: str) -> list[dict]:
    """Schreibt alle Faelle ueber den regulaeren Writer-Pfad; Session-Store
    bewusst In-Memory — kein ungeprueftes bc1.sessions in der Ziel-DB.
    Seit B5 je Fall mit dessen Anfrage: Auswahl, Fingerabdruck und Writer haengen an ihr."""
    ergebnis = []
    for fall in FAELLE:
        with pool.connection() as conn:
            kontext = lade_kontext(conn, company_id, fall.anfrage_id)
        paket = baue_discovery_paket(kontext=kontext)
        writer = ProfilWriter(pool, company_id, paket)
        antwort = fuehre_interview(InMemoryStateStore(), paket, fall,
                                   company_id=company_id, writer=writer)
        ergebnis.append({"session_id": fall.session_id, "status": antwort["status"],
                         "vollstaendigkeit": antwort["payload"].get("vollstaendigkeit")})
    return ergebnis
```

Docstring von `Fall`: „anfrage_id ist seit B5 die Anfrage, zu der der Fall interviewt wird (BC1_ANFRAGE_ID-Äquivalent).“ In `tests/test_use_case_testprofile.py`: `_noro_geruest` legt die Anfragen der Fälle an — **vorher** die Basis-Anfragen von Mandant A löschen, weil `A-2026-01..03` sonst mit den Fixture-Anfragen aus Task 1 kollidieren (dieselben IDs, andere TPs):

```python
    conn.execute("DELETE FROM ref_anfragen WHERE company_id = %s", (MANDANT_A,))
    for fall in FAELLE:
        kp = fall.fokus_tp.split(".")[0]
        conn.execute(
            "INSERT INTO ref_anfragen (company_id, anfrage_id, eingang_am, process_id, "
            "sub_process_id, zuordnung_quelle, status) "
            "VALUES (%s, %s, '2026-09-01', %s, %s, 'anfrage', 'zugeordnet')",
            (MANDANT_A, fall.anfrage_id, kp, fall.fokus_tp))
        conn.execute(
            "INSERT INTO anfrage_prozesse (company_id, anfrage_id, process_id, "
            "sub_process_id, rolle, zuordnung_quelle) "
            "VALUES (%s, %s, %s, %s, 'haupt', 'anfrage')",
            (MANDANT_A, fall.anfrage_id, kp, fall.fokus_tp))
```

(`FAELLE` aus `bc1_service.use_case_testprofile` importieren.) Z. 176 `lade_kontext(conn, MANDANT_A)` → `lade_kontext(conn, MANDANT_A, FAELLE[0].anfrage_id)` und die Erwartung an die Auswahl auf den einen TP dieser Anfrage anpassen. Hinweis in den Zwischenbericht: Der Live-Lauf des Werkzeugs (`--echt`) braucht ab B5 die drei Anfragen bei BC0 im Stand `zugeordnet`/`im_interview`.

- [ ] **Step 6: Lauf, erwartet PASS** — `uv run pytest tests/test_start.py tests/test_discovery_paket.py tests/test_paket_wahl.py tests/test_use_case_testprofile.py tests/test_postgres_init.py tests/test_api_profil.py -v`; dann volle Suite. Fällt ein Test mit wörtlich gepinntem ctx-Hash: Erwartung bewusst neu setzen und im Commit nennen.

- [ ] **Step 7: Commit** — `"BC1 B5: Start nur mit Anfrage — Pflicht, Statusprüfung, Auswahl aus der Anfrage, Anfrage im Fingerabdruck"`.

---

### Task 4: Sitzung an die Anfrage binden — Guard vor dem Replay

**Files:**
- Modify: `bc1_core/types.py`, `bc1_core/serialize.py`, `bc1_core/core.py`, `bc1_service/api.py`, `bc1_service/main.py`
- Test: `tests/test_core.py`, `tests/test_api.py`, `tests/test_store_postgres.py` (Rundlauf)

**Interfaces:**
- Consumes: Task 3 (`main.py` reicht `_anfrage_id` durch).
- Produces: `SessionState.anfrage_id: str | None = None`; `class AnfrageKonfliktError(ValueError)`; `pruefe_anfrage(state: SessionState, anfrage_id: str) -> None`; `process_turn(…, *, company_id: str, anfrage_id: str | None = None, mitgesendete_version=None)`; `create_app(…, *, company_id: str, anfrage_id: str | None = None, writer=None)`; HTTP 409 `detail="anfrage_konflikt"`.

- [ ] **Step 1: Failing tests** — `tests/test_api.py`:

```python
ANFRAGE = "A-2026-01"


def test_fremde_anfrage_bekommt_409_anfrage_konflikt():
    store = InMemoryStateStore()
    alt = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                company_id=MANDANT, anfrage_id=ANFRAGE))
    assert _turn(alt, "m1", "Der Prozess heißt Urlaubsantrag").status_code == 200
    neu = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                company_id=MANDANT, anfrage_id="A-2026-02"))
    antwort = _turn(neu, "m2", "Ausgelöst durch einen Antrag")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"


def test_alt_sitzung_ohne_anfrage_wird_abgewiesen():
    store = InMemoryStateStore()
    store.save(SessionState("s1", TOY_PROZESS.schema_version, paket_name=TOY_PROZESS.name,
                            company_id=MANDANT))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT, anfrage_id=ANFRAGE))
    antwort = _turn(client, "m1", "hallo")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"


def test_recovery_replay_wechselt_nie_die_anfrage():
    # Der Paket-Guard laesst einen abweichenden ctx-Hash beim terminalen Replay
    # passieren (darf_recovery_replay) — der Anfrage-Guard darf das NICHT.
    store = InMemoryStateStore()
    llm = FakeLLM()
    alt = TestClient(create_app(store, llm, IDENT_PAKET, company_id=MANDANT,
                                anfrage_id=ANFRAGE))
    _turn(alt, "m1", "a")
    _turn(alt, "m2", "b")
    neues_paket = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    neu = TestClient(create_app(store, llm, neues_paket, company_id=MANDANT,
                                anfrage_id="A-2026-02"))
    antwort = _turn(neu, "m2", "b", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"
```

`tests/test_core.py`:

```python
def test_neue_sitzung_traegt_die_anfrage_und_fremde_anfrage_scheitert():
    store = InMemoryStateStore()
    process_turn(store, FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo",
                 company_id=MANDANT, anfrage_id="A-2026-01")
    assert store.load("s1").anfrage_id == "A-2026-01"
    with pytest.raises(AnfrageKonfliktError):
        process_turn(store, FakeLLM(), TOY_PROZESS, "s1", "m2", "weiter",
                     company_id=MANDANT, anfrage_id="A-2026-02")
```

(`MANDANT`-Konstante und Importe wie in den bestehenden Mandanten-Tests von `test_core.py` verwenden; `AnfrageKonfliktError` aus `bc1_core.core` importieren.)

`tests/test_store_postgres.py` — im bestehenden Rundlauf-Test einen State mit `anfrage_id="A-2026-01"` speichern und laden; Assertion `geladen.anfrage_id == "A-2026-01"`. Falls es dort keinen Rundlauf-Test mit Feldvergleich gibt, neuen Test nach dem Muster des vorhandenen `save/load`-Tests anlegen.

- [ ] **Step 2: Drei getrennte TDD-Zyklen statt eines Laufs** (agy F5 — sonst blockiert der Guard die Edits an `types.py`/`serialize.py` als „Premature implementation“):
  1. **Zustand:** nur den Rundlauf-Test (`test_store_postgres.py`) einfügen → `uv run pytest tests/test_store_postgres.py -k anfrage -v` → RED (`TypeError: unexpected keyword 'anfrage_id'` bzw. Attribut fehlt) → Step 3 + Step 4 → GREEN.
  2. **Kern:** nur `test_neue_sitzung_traegt_die_anfrage_und_fremde_anfrage_scheitert` einfügen → `uv run pytest tests/test_core.py -k anfrage -v` → RED → Step 5 → GREEN.
  3. **API:** die drei `test_api.py`-Tests einzeln einfügen, je RED (`TypeError: create_app() got an unexpected keyword argument 'anfrage_id'`, danach 200 statt 409) → Step 6 → GREEN.

- [ ] **Step 3: `types.py`** — nach `company_id`:

```python
    # Anfrage-Bindung (B5): beim ersten Turn gesetzt, danach bei JEDEM Turn
    # geprueft (pruefe_anfrage) — wie company_id, aus demselben Grund.
    anfrage_id: str | None = None
```

- [ ] **Step 4: `serialize.py`** — `"anfrage_id": state.anfrage_id,` nach `company_id` in `state_to_dict`; `anfrage_id=daten.get("anfrage_id"),` in `state_from_dict` (`.get`: Alt-Zustände ohne Schlüssel bleiben lesbar und werden vom Guard abgewiesen).

- [ ] **Step 5: `core.py`**

```python
class AnfrageKonfliktError(ValueError):
    """Session gehoert zu einer anderen Anfrage — oder zu gar keiner (B5)."""


def pruefe_anfrage(state: SessionState, anfrage_id: str) -> None:
    """Anfrage-Guard (B5), gleiche Strenge wie pruefe_mandant: keine Ausnahme, auch
    nicht fuer den Recovery-Replay; Alt-Sessions ohne anfrage_id werden abgewiesen."""
    if state.anfrage_id != anfrage_id:
        raise AnfrageKonfliktError(
            f"Session {state.session_id} gehoert zu Anfrage {state.anfrage_id}, "
            f"der Dienst laeuft mit {anfrage_id}")
```

`process_turn`: Signatur `*, company_id: str, anfrage_id: str | None = None, mitgesendete_version: str | None = None`. Neuer State: `SessionState(…, company_id=company_id, anfrage_id=anfrage_id)`. Im `else`-Zweig nach `pruefe_mandant(state, company_id)`:

```python
        if anfrage_id is not None:
            pruefe_anfrage(state, anfrage_id)
```

- [ ] **Step 6: `api.py`** — Import `AnfrageKonfliktError, pruefe_anfrage`; `create_app(…, *, company_id: str, anfrage_id: str | None = None, writer: …)` mit Kommentar „None nur in Tests ohne BC0-Kontext; main.py setzt immer (BC1_ANFRAGE_ID Pflicht)“. Nach BEIDEN Mandanten-Guards (vor `darf_recovery_replay` und vor `writer.reconcile`):

```python
                if anfrage_id is not None:
                    try:
                        pruefe_anfrage(state, anfrage_id)
                    except AnfrageKonfliktError:
                        raise HTTPException(status_code=409, detail="anfrage_konflikt")
```

(im zweiten Block `stand` statt `state`). `process_turn(…, company_id=company_id, anfrage_id=anfrage_id, …)` und im `except`-Block `except AnfrageKonfliktError: raise HTTPException(status_code=409, detail="anfrage_konflikt")`. Modul-Docstring: „Mandanten- und Anfrage-Guard vor jeder anderen Prüfung“. `main.py`: `create_app(…, company_id=_company_id, anfrage_id=_anfrage_id, …)`.

- [ ] **Step 7: Lauf, erwartet PASS** — `uv run pytest tests/test_api.py tests/test_core.py tests/test_store_postgres.py -v`; dann volle Suite.

- [ ] **Step 8: Commit** — `"BC1 B5: Sitzung an die Anfrage gebunden — Anfrage-Guard vor dem Recovery-Replay (agy C1)"`.

---

### Task 5: Datenbank — Spalte `anfrage_id`, Umstellungseinheit, Sollsignatur

**Files:**
- Create: `bc1_service/db/prozessprofil_b5.sql`
- Modify: `bc1_service/db/prozessprofil.sql` (Abschnitt 0, `CREATE TABLE`, Abschnitt 0b Sollsignatur), `tests/db_fixture.py`
- Test: `tests/test_ddl_b5_spalte.py` (neu), `tests/test_ddl_einspielen.py`, `tests/test_ddl_sessions.py`

**Interfaces:**
- Consumes: Task 1 (Sichten für die Rechte-Vorprüfung).
- Produces: Spalte `bc1.prozessprofil.anfrage_id text NULL`, CHECK `prozessprofil_anfrage_format`; `tests.db_fixture.spiele_b5_ein(dsn)`; `spiele_migration_und_ddl_ein` spielt d3 → b5 → prozessprofil in EINER Transaktion.

- [ ] **Step 1: Failing tests** — `tests/test_ddl_b5_spalte.py`:

```python
"""Spalte anfrage_id in bc1.prozessprofil — B5 (05.10.2026).

Zwei Einspielwege wie bei D3: frische DB (prozessprofil.sql legt mit Spalte an) und
Bestand (prozessprofil_b5.sql migriert, danach meldet prozessprofil.sql Fall 2).
"""
import pytest

from tests.db_fixture import (DSN, MANDANT_A, frische_db, spiele_b5_ein,
                              spiele_migration_und_ddl_ein, verbindung)

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")


def _spalte(conn):
    return conn.execute(
        "SELECT data_type, is_nullable FROM information_schema.columns "
        " WHERE table_schema = 'bc1' AND table_name = 'prozessprofil' "
        "   AND column_name = 'anfrage_id'").fetchone()


def _einfuegen(conn, anfrage_id):
    conn.execute(
        "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, profil_version, "
        "process_id, status, erhebung_id, paket_version, profil, anfrage_id) "
        "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-01', "
        "'1.1+ctx-0000000000000000', '{}', %s)", (MANDANT_A, anfrage_id))


def _altzustand(dsn):
    """Bestand vor B5: ohne Spalte (DROP COLUMN nimmt den CHECK mit)."""
    frische_db(dsn)
    with verbindung(dsn, None) as conn:
        conn.execute("ALTER TABLE bc1.prozessprofil DROP COLUMN anfrage_id")
        conn.commit()


def test_frische_db_hat_die_spalte_text_und_nullable():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        assert _spalte(conn) == ("text", "YES")


@pytest.mark.parametrize("falsch", ["a-2026-01", "A-26-01", "A-2026-1", ""])
def test_format_check_weist_falsche_nummern_ab(falsch):
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(Exception) as fehler:
            _einfuegen(conn, falsch)
        assert "prozessprofil_anfrage_format" in str(fehler.value)


@pytest.mark.parametrize("richtig", [None, "A-2026-01"])
def test_format_check_nimmt_null_und_richtige_nummern(richtig):
    frische_db(DSN)
    with verbindung(DSN) as conn:
        _einfuegen(conn, richtig)
        conn.rollback()


def test_m1_migriert_den_bestand_und_danach_ist_prozessprofil_fall_2():
    _altzustand(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute(
            "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, profil_version, "
            "process_id, status, erhebung_id, paket_version, profil) VALUES "
            "(%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-01', 'x', '{}')",
            (MANDANT_A,))
        conn.commit()
    spiele_migration_und_ddl_ein(DSN)        # d3 (M2) -> b5 (M1) -> prozessprofil (Fall 2)
    with verbindung(DSN, None) as conn:
        assert _spalte(conn) == ("text", "YES")
        assert conn.execute("SELECT anfrage_id FROM bc1.prozessprofil").fetchall() == [(None,)]


def test_m2_ist_ein_noop():
    frische_db(DSN)
    spiele_b5_ein(DSN)                         # zweiter Lauf auf migriertem Stand
    spiele_migration_und_ddl_ein(DSN)


def test_m3_bricht_ohne_aenderung_ab():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:        # Spalte da, CHECK fehlt -> M3
        conn.execute("ALTER TABLE bc1.prozessprofil "
                     "DROP CONSTRAINT prozessprofil_anfrage_format")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_b5_ein(DSN)
    assert "M3" in str(fehler.value)
```

`tests/test_ddl_einspielen.py` ergänzen:

```python
def test_vorpruefung_meldet_fehlende_anfrage_sicht():
    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, None) as conn:
        conn.execute("REVOKE SELECT ON v_anfrage_teilprozesse FROM bc_leser")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "v_anfrage_teilprozesse" in str(fehler.value)
```

- [ ] **Step 2: Lauf, erwartet FAIL** — `uv run pytest tests/test_ddl_b5_spalte.py tests/test_ddl_einspielen.py -k "b5 or anfrage" -v` → ImportError `spiele_b5_ein`.

- [ ] **Step 3: `prozessprofil.sql` — Tabelle und Vorprüfung**
  - In `CREATE TABLE` nach `paket_version` (vor `profil`):

```sql
        -- B5 (05.10.2026): die BC0-Anfrage, zu der interviewt wurde. NULL nur fuer
        -- Bestand vor B5 (eingefroren, keine Nachzuordnung). Kein FK auf ref_anfragen
        -- (Entscheidung BC1 05.10.: kein REFERENCES-Recht, Freeze-Konflikt).
        anfrage_id                          text,
```

  - Constraint nach `prozessprofil_confidence_bereich`:

```sql
        CONSTRAINT prozessprofil_anfrage_format
            CHECK (anfrage_id IS NULL OR anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}$'),
```

  - Abschnitt 0 (SELECT-Vorprüfung) Array ergänzen um `'v_anfrage_prozessbezug', 'v_anfrage_teilprozesse'`; Kommentar „B5: Start liest die Anfrage“.

- [ ] **Step 4: Constraint-Text gegenmessen** — der in Step 5 eingetragene Soll-Text ist die erwartete PG-Ausgabe; gegen den Container (PG 17) verifizieren:

```bash
uv run python -c "import psycopg,os;c=psycopg.connect(os.environ['BC1_TEST_DB_DSN']);c.execute(\"CREATE TEMP TABLE t(anfrage_id text, CONSTRAINT k CHECK (anfrage_id IS NULL OR anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}\$'))\");print(c.execute(\"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='k'\").fetchone()[0])"
```

Erwartet: `CHECK (((anfrage_id IS NULL) OR (anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}$'::text)))`. Weicht die Ausgabe ab, gilt die gemessene Ausgabe — `check_soll` in Step 5 entsprechend ersetzen (der M1-Test aus Step 1 fällt sonst mit „Nachpruefung fehlgeschlagen“).

- [ ] **Step 5: `prozessprofil_b5.sql` anlegen** (Kopf und Struktur wie `prozessprofil_d3.sql`):

```sql
-- BC1 — Bestand nachziehen: Spalte anfrage_id in bc1.prozessprofil (B5, 05.10.2026).
-- BC1 interviewt nur noch zu einer BC0-Anfrage; das Profil traegt deren Nummer.
--
-- Warum eine eigene Datei: wie prozessprofil_d3.sql — ein Bestand OHNE die Spalte waere
-- gegen die neue Sollsignatur Fall 3. Danach meldet prozessprofil.sql wieder Fall 2
-- (Test: tests/test_ddl_b5_spalte.py).
--
-- Einspielen (EINE Transaktion), NACH prozessprofil_d3.sql und VOR prozessprofil.sql:
--     psql -v ON_ERROR_STOP=1 -1 -f prozessprofil_d3.sql -f prozessprofil_b5.sql -f prozessprofil.sql
-- Kein BEGIN/COMMIT. Auf einer frischen DB ein No-op.
--
-- Vierfallregel:
--   M0  Tabelle fehlt                 -> No-op; prozessprofil.sql legt mit Spalte an
--   M1  Spalte fehlt, CHECK fehlt     -> Spalte + CHECK anlegen, nachpruefen
--   M2  Spalte da,    CHECK = Soll    -> No-op
--   M3  alles andere                  -> Abbruch OHNE Aenderung
-- Keine Datenvorbedingung: die Spalte ist neu und leer; Bestandszeilen bleiben NULL.

SET LOCAL search_path = public, pg_temp;
SELECT pg_advisory_xact_lock(hashtext('bc1.prozessprofil.einspielen'));

DO $$
DECLARE
    -- Woertlich die Ausgabe von pg_get_constraintdef auf PG 17 (Step 4 gemessen).
    check_soll constant text := 'CHECK (((anfrage_id IS NULL) OR (anfrage_id ~ ''^A-[0-9]{4}-[0-9]{2}$''::text)))';
    tabelle_da boolean;
    spalte_da  boolean;
    check_ist  text;
BEGIN
    SELECT to_regclass('bc1.prozessprofil') IS NOT NULL INTO tabelle_da;
    IF NOT tabelle_da THEN
        RAISE NOTICE 'M0: bc1.prozessprofil fehlt — nichts zu migrieren.';
        RETURN;
    END IF;
    SELECT EXISTS (
        SELECT 1 FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
           AND a.attname = 'anfrage_id' AND NOT a.attisdropped) INTO spalte_da;
    SELECT pg_get_constraintdef(con.oid) INTO check_ist
      FROM pg_constraint con
      JOIN pg_class c ON c.oid = con.conrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
       AND con.conname = 'prozessprofil_anfrage_format';

    IF spalte_da AND check_ist = check_soll THEN
        RAISE NOTICE 'M2: Spalte und CHECK bereits auf Stand B5 — No-op.';
        RETURN;
    END IF;
    IF NOT spalte_da AND check_ist IS NULL THEN
        RAISE NOTICE 'M1: Bestand ohne Spalte — anfrage_id anlegen.';
        ALTER TABLE bc1.prozessprofil ADD COLUMN anfrage_id text;
        ALTER TABLE bc1.prozessprofil ADD CONSTRAINT prozessprofil_anfrage_format
            CHECK (anfrage_id IS NULL OR anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}$');
        SELECT pg_get_constraintdef(con.oid) INTO check_ist
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
           AND con.conname = 'prozessprofil_anfrage_format';
        IF check_ist IS DISTINCT FROM check_soll THEN
            RAISE EXCEPTION E'M1: Nachpruefung fehlgeschlagen — CHECK weicht ab. Rollback.\n  ist:  %\n  soll: %',
                            check_ist, check_soll;
        END IF;
        RAISE NOTICE 'M1: erledigt — prozessprofil.sql muss jetzt Fall 2 melden.';
        RETURN;
    END IF;
    RAISE EXCEPTION E'M3: unerwarteter Bestand — Spalte vorhanden: %, CHECK: %. Abbruch OHNE Aenderung.',
                    spalte_da, coalesce(check_ist, '<fehlt>');
END $$;
```

Spaltenposition: `ADD COLUMN` hängt hinten an, die frische DB hat die Spalte vor `profil`. Unkritisch — die `spalte|`-Zeilen der Sollsignatur tragen keine Ordinalposition (`prozessprofil.sql:267`, bei D3 genauso bewiesen).

- [ ] **Step 6: `db_fixture.py`** — `_DDL_B5 = … / "prozessprofil_b5.sql"`; neue Funktion

```python
def spiele_b5_ein(dsn: str) -> None:
    """prozessprofil_b5.sql — Migrations-Einheit B5, laeuft nach d3, vor prozessprofil.sql."""
    spiele_datei_ein(dsn, _DDL_B5)
```

und in `spiele_migration_und_ddl_ein` zwischen d3 und prozessprofil: `conn.execute(_DDL_B5.read_text(encoding="utf-8"))`; Docstrings „d3 → b5 → prozessprofil“.

- [ ] **Step 7: Sollsignatur neu erzeugen** — zuerst in `prozessprofil.sql` den alten Block zwischen `INSERT INTO pg_temp.bc1_soll_signatur (zeile) VALUES` und dessen abschließendem `;` durch genau diese eine Zeile ersetzen (der Generator verlangt sie, `signatur_erzeugen.py:84-86`, agy F4):

```sql
    ('platzhalter|wird|in|step7|ersetzt');
```

Dann:

```bash
uv run python tests/db/signatur_erzeugen.py bc1_service/db/prozessprofil.sql
```

Danach `git diff bc1_service/db/prozessprofil.sql` lesen: erwartet sind nur neue `spalte|prozessprofil|anfrage_id|…`- und `constraint|…|prozessprofil_anfrage_format|…`-Zeilen plus geänderte Zeilenzahl im Kommentar (177 → neu). Jede andere Zeilenänderung → anhalten und verstehen.

- [ ] **Step 8: Lauf, erwartet PASS** — `uv run pytest tests/test_ddl_b5_spalte.py tests/test_ddl_d3_spalte.py tests/test_ddl_einspielen.py tests/test_ddl_sessions.py tests/test_signatur_erzeugen.py -v`; `test_ddl_sessions` muss weiter „sessions.sql Fall 2“ und „prozessprofil.sql bleibt No-op“ zeigen. Dann volle Suite.

- [ ] **Step 9: Commit** — `"BC1 B5: Spalte anfrage_id in bc1.prozessprofil + Umstellungseinheit prozessprofil_b5.sql (M0–M3), Sollsignatur neu"`.

---

### Task 6: Writer schreibt die Anfrage ins Profil

**Files:**
- Modify: `bc1_service/profil_writer.py:475-485` (`_einfuegen`)
- Test: `tests/test_profil_writer.py`, `tests/test_api_profil.py`

**Interfaces:**
- Consumes: Task 4 (`state.anfrage_id`), Task 5 (Spalte).
- Produces: Profilzeilen tragen `anfrage_id = state.anfrage_id`; `_umbinden` übernimmt ihn über `_einfuegen` unverändert.

- [ ] **Step 1: Failing test** — in `tests/test_profil_writer.py` nach dem Muster des bestehenden Draft-Anlege-Tests (gleiche Fixtures/Helfer der Datei verwenden), den State mit `anfrage_id="A-2026-01"` bauen und nach `reconcile` prüfen:

```python
    with verbindung(DSN) as conn:
        assert conn.execute(
            "SELECT anfrage_id FROM bc1.prozessprofil WHERE company_id = %s",
            (MANDANT_A,)).fetchall() == [("A-2026-01",)]
```

In `tests/test_api_profil.py` den Aufruf in der Hilfsfunktion `_client` auf `create_app(…, anfrage_id=ANFRAGE_A)` und die Modulkonstante `KONTEXT = Bc0Kontext(…, anfrage_id=ANFRAGE_A)` umstellen und im Durchstich-Test (fertig) zusätzlich `anfrage_id` der fertigen Zeile prüfen (`== ANFRAGE_A`). Außerdem den Umbinden-Test: nach TP-Wechsel trägt die neue Zeile weiter `ANFRAGE_A`.

- [ ] **Step 2: Lauf, erwartet FAIL** — `uv run pytest tests/test_profil_writer.py tests/test_api_profil.py -k anfrage -v` → `[(None,)] != [('A-2026-01',)]`.

- [ ] **Step 3: Implementierung** — in `_einfuegen`:

```python
        namen = ["company_id", "focus_step_id", "profil_version", "process_id",
                 "status", "erhebung_id", "paket_version", "anfrage_id", "profil", *spalten]
        werte = [self._company_id, inhalt.focus_step_id, 1, inhalt.process_id,
                 "in_erhebung", erhebung, state.schema_version, state.anfrage_id,
                 Jsonb(inhalt.profil), *spalten.values()]
```

Kommentar: „anfrage_id aus der SITZUNG (B5) — der Anfrage-Guard in api.py stellt sicher, dass sie zur Instanz passt.“ Kein Status-Recheck in `_abgleich` (Spec Big Picture 3).

Zusätzlich `use_case_testprofile.fuehre_interview`: `process_turn(…, company_id=company_id, anfrage_id=fall.anfrage_id)`; dazu in `tests/test_use_case_testprofile.py` ein Test (eigener Edit, vorher RED), der nach `schreibe_testprofile` je Fall `anfrage_id` der Profilzeile prüft:

```python
def test_testprofile_tragen_ihre_anfrage(pool):
    schreibe_testprofile(pool, MANDANT_A)
    with verbindung(DSN) as conn:
        zeilen = dict(conn.execute(
            "SELECT focus_step_id, anfrage_id FROM bc1.prozessprofil "
            "WHERE company_id = %s", (MANDANT_A,)).fetchall())
    assert zeilen == {f.fokus_tp: f.anfrage_id for f in FAELLE}
```

- [ ] **Step 4: Lauf, erwartet PASS** — Ziel-Tests, dann volle Suite.

- [ ] **Step 5: Commit** — `"BC1 B5: Writer schreibt anfrage_id aus der Sitzung ins Profil"`.

---

### Task 7: Betrieb — Doku und Live-Lauf vorbereiten

**Files:**
- Modify: `bc1_service/db/EINSPIELEN.md` (§2 Reihenfolge, neuer Abschnitt „B5 live“), `bc1_service/n8n/SMOKE.md` (Startvariablen, neue Startabbrüche), `README.md` (Pflichtvariablen)
- Modify (lokal, SDD): `.superpowers/sdd/Implementierungsplan-DB-Profil-Fundament/lauf.sh` (Unterbefehl `b5`), neu `einspielen-nachpruefung-b5.sql`

**Interfaces:** Produces: `./lauf.sh b5` = Vorprüfung (Fall erkennen) → `psql -1 -f prozessprofil_d3.sql -f prozessprofil_b5.sql -f prozessprofil.sql` → `sessions.sql` → Nachprüfung.

- [ ] **Step 1: EINSPIELEN.md §2** — Befehl ersetzen durch:

```
psql -v ON_ERROR_STOP=1 -1 -f prozessprofil_d3.sql -f prozessprofil_b5.sql -f prozessprofil.sql && psql -v ON_ERROR_STOP=1 -1 -f sessions.sql
```

und einen Abschnitt „B5 — Spalte anfrage_id (Bestand)“ mit erwarteten Meldungen: d3 `M2`, b5 `M1`, prozessprofil `Fall 2`, sessions `Fall 2`.

- [ ] **Step 2: Nachprüfung** — `einspielen-nachpruefung-b5.sql`:

```sql
SELECT 'spalte|' || data_type || '|' || is_nullable FROM information_schema.columns
 WHERE table_schema = 'bc1' AND table_name = 'prozessprofil' AND column_name = 'anfrage_id';
SELECT 'bestand_ohne_anfrage|' || count(*) FROM bc1.prozessprofil WHERE anfrage_id IS NULL;
SELECT 'bestand_gesamt|' || count(*) FROM bc1.prozessprofil;
```

Erwartet: `spalte|text|YES`, `bestand_ohne_anfrage` = `bestand_gesamt`. Danach `lesen_gegenprobe.py` wie bei D3 (Ausgabe `lesen.sql` wörtlich unverändert).

- [ ] **Step 3: `lauf.sh b5`** — Zweig analog `d3` anlegen (gleiche Variablen, gleiche Logdatei-Konvention `einspielen-b5.log`). Claude schreibt das Skript; **Die BC1-Projektleitung führt es aus.**

- [ ] **Step 4: SMOKE.md / README** — `BC1_ANFRAGE_ID` als Pflicht, Beispielwert `A-2026-03`, die vier neuen Startabbrüche mit Wortlaut-Verweis auf `start.py`; Hinweis „Für den Durchstich einen Teilprozess wählen, zu dem es noch kein fertiges BC1-Profil gibt (BC0s Gate-Funktion verknüpft noch nicht über anfrage_id).“

- [ ] **Step 5: Commit** (nur Repo-Dateien; SDD-Ordner ist lokal) — `"BC1 B5: Einspielen, Smoke und README auf BC1_ANFRAGE_ID und prozessprofil_b5.sql"`.

---

### Task 8: Abschluss — volle Suite, Zweitmeinung, Plan, Entwürfe

**Files:**
- Modify: `bc1-context-discovery/design/Abschlussplan-BC1.md`
- Create (lokal, Projektwurzel, NICHT im Repo): `Entwurf-Kommentar-Issue-226-B5.md`, `Entwurf-Kommentar-Issue-206-Stand.md`; Modify: `Sammelliste an BC0 (lokal)` (Runde 2)

- [ ] **Step 1: Volle Suite mit Container** — `uv run pytest -q`; Ergebnis (passed/skipped) wörtlich in den Zwischenbericht. Kein „grün“ ohne diese Ausgabe.

- [ ] **Step 2: Zweitmeinung (Pflicht, Datenmodell)** — Codex-Review über `git diff main...bc1-b5-anfragesteuerung`; Befunde nach Schwere adjudizieren (Critical/Important fixen, Minor fixen oder mit Ziel vertagen), jeden Fix mit Test verifizieren, Ergebnis der BC1-Projektleitung vorlegen.

- [ ] **Step 3: Abschlussplan** — B5 auf „gebaut (Live-Einspielen offen)“; Rückstellungen aus der Spec-Tabelle als eigene Zeilen/Kleinpunkte mit Ziel (Variante B → B3 Teil 2; Status setzen + `gate_nachziehen` → B4; C4 (b) → eigenes Paket direkt nach B5; vorbestehender Erhebungs-Recheck-Hänger → B3 Teil 1; Fragesteller → nach C1a; Anliegen-Kontext → nach #226; 409-`chat_text` → P3); offene Punkte aus der BC0-Antwort vom 23.09. (R-07 entfällt, P-07/#R1 geschlossen); BC0 v3.8–v3.11 geprüft (Spec-Abschnitt). Commit.

- [ ] **Step 4: Entwürfe (nicht posten)** — #226: Felderliste (Anliegen-Text ohne Personenbezug, `status`; Rückmeldung über die Sicht, BC1 liest beim Start) + Klärpunkte (Sperren `eigner_benannt`/`items_bewertet` sichtbar?; interviewbare Status bestätigt?). #206: KW 40 verfehlt, B5 gebaut, B4 folgt, neuer Terminvorschlag (BC1-Projektleitung). Sammelliste Runde 2: Gate-Funktion über `anfrage_id`; Kopplung (FK) gewünscht?; `ref_anfragen.originaltext` für `bc_leser` lesbar; `ki_*` (v3.11) über Default-Rechte lesbar.

- [ ] **Step 5: Zwischenbericht an die BC1-Projektleitung und auf Go warten** — Inhalt: Suite-Ergebnis, Review-Adjudikation, was öffentlich würde (Vertraulichkeits-Check des Diffs), Push/PR nur nach OK; danach Live-Lauf durch die BC1-Projektleitung (`./lauf.sh b5`).
