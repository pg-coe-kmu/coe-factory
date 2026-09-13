# B1 — `bc1.sessions` ins signierte Fundament: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) — Tasks einzeln, nach jedem Test ein voller `.venv/bin/pytest -q -W error`-Lauf aus `bc1-context-discovery/` (tdd-guard). `*.py` nur über Edit/Write anlegen, nie per Bash. Bei einem Guard-Block das Skill `tdd-guard` aufrufen, nie umgehen.

**Ziel:** Die Sitzungstabelle `bc1.sessions` (kompletter Interview-Zustand inkl. Nutzer-Rohtext) wird wie die drei Vertragstabellen fest definiert, per Sollsignatur geprüft und ausdrücklich nur für `bc1_role` lesbar; der `PostgresStateStore` legt nichts mehr an, sondern bricht ohne Tabelle mit lesbarer Meldung ab.

**Architektur:** Eine **zweite Einspiel-Einheit** `bc1_service/db/sessions.sql` neben `prozessprofil.sql` — gleiche Dreifallregel (Fall 1 anlegen · Fall 2 No-op · Fall 3 Abbruch ohne Änderung), eigene Sollsignatur, Geltungsbereich genau eine Tabelle. `prozessprofil.sql` bleibt **byteidentisch**; seine Signatur sieht die vierte Tabelle nicht (jede Katalogabfrage dort ist auf die drei Namen eingeschränkt, die Vorprüfung zählt nur die neun benannten Objekte). Der Store verliert `CREATE SCHEMA`/`CREATE TABLE`, prüft beim Start die Existenz der Tabelle und schreibt `company_id` aus dem Zustand in eine typisierte Spalte (Fremdschlüssel auf `companies` mit Löschkaskade — heute überlebt der Rohtext eine Mandantenlöschung). Das Signatur-Werkzeug zieht ins Repo und bekommt die Zieldatei als Argument.

**Tech Stack:** Python 3.11+, pytest (`-W error`), psycopg 3 / psycopg_pool, Test-Container PostgreSQL 17 (`docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:17`, `tests/db_fixture.py`), Ziel Supabase PostgreSQL 17.

**Spec:** `design/Abschlussplan-BC1.md`, Stufe B, Paket B1 + Entscheidungen Richard 13.09.2026 (Chat, nach Bestandsaufnahme):
1. **Eigene Datei `sessions.sql`** statt Einbau in `prozessprofil.sql` — Abweichung vom Abschlussplan, weil die Dreifallregel nur „alles" oder „nichts" kennt: live stehen die neun Vertragsobjekte mit eingefrorenen Daten, ein zehntes Objekt in derselben Datei wäre dort „Fall 3: Teilbestand". **Bedingung Richard:** nichts anderes wird verschlimmbessert, kein anderer BC wird beeinträchtigt → eigener Test (Task 2, `test_prozessprofil_sql_bleibt_nach_sessions_sql_ein_no_op`) und volle Suite grün.
2. **Schlüssel `session_id` allein** (wie `profil_write_status` und der StateStore-Vertrag `load(session_id)`); `company_id` kommt als Pflichtspalte dazu. Der Verbundschlüssel bleibt Roadmap-Anker im DB-Profil-Plan (Nachtrag 08.09., Zeile „Mandantenweiter Sitzungsschlüssel") — Auslöser: zweite Dienstinstanz auf derselben Datenbank. Ehrlich: n8n vergibt die `session_id` heute schon clientseitig (`SMOKE.md`, HTTP-Request-Node); die Kopplung ist fail-closed (409), keine Datenvermischung.
3. **Signatur-Skript ins Repo** (`tests/db/signatur_erzeugen.py`), weil `EINSPIELEN.md` heute auf `../../signatur-erzeugen.py` außerhalb des Repos verweist.

## Global Constraints

- **TDD mit tdd-guard:** Test zuerst, RED messen, dann Implementierung; `*.py` ausschließlich über Edit/Write.
- **Volle Suite** nach jedem Task: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q -W error` aus `bc1-context-discovery/`. Ausgangslage 13.09.: **465 passed / 4 skipped**.
- **`prozessprofil.sql` bleibt unverändert** (Signatur 176 Zeilen, live seit 08.09.). Nachweis: `git diff --stat` des Tasks enthält die Datei nicht.
- **Einspielen im Betrieb als `bc1_role`**, je Datei EINE Transaktion (`psql -v ON_ERROR_STOP=1 -1 -f …`), Reihenfolge erst `prozessprofil.sql`, dann `sessions.sql`.
- **Rechte:** `bc1_role` alles, `bc_leser`/`bc2_role`–`bc4_role`/PUBLIC **nichts** auf `bc1.sessions` — gemessen mit dem Gerüst-Automatismus (`ALTER DEFAULT PRIVILEGES … GRANT SELECT ON TABLES TO bc_leser`, `bc0_geruest.sql:173`), also nur mit ausdrücklichem REVOKE grün.
- **Umgebungsrollen-Liste** (`postgres`, `supabase_read_only_user`, `supabase_etl_admin`) in `sessions.sql` identisch zu `prozessprofil.sql`; ein Test hält beide gleich.
- **Keine Namen** von Personen in Code, Tests, Kommentaren (Repo-Konvention). Sprache Deutsch. Commit-Stil `feat(bc1): …` / `test(bc1): …` / `docs(bc1): …` mit `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- **Kein Push ohne OK von Richard.** Branch `bc1-b1-sessions-fundament` ab `bc1-db-profil-fundament` (die DDL liegt nur dort). Kein Worktree: die tdd-guard-Konfiguration hängt am Hauptcheckout, die Arbeitskopie ist sauber.
- Alle Zahlen und Aussagen in Doku sind **gemessen**, nicht vermutet.

---

## Dateien

- Create: `bc1_service/db/sessions.sql` — zweite Einspiel-Einheit (Voraussetzungen · Sollsignatur · Dreifallregel · Anlage · Rechte · Nachprüfung)
- Create: `tests/db/signatur_erzeugen.py` — Generator (Entwicklungswerkzeug, braucht das Test-Gerüst → liegt bei den Tests, nicht unter `bc1_service/`), Zieldatei als Argument, reine Funktionen + Gesamtlauf testbar
- Create: `tests/test_signatur_erzeugen.py` — Parser + Blockbau
- Create: `tests/test_ddl_sessions.py` — Dreifallregel, Rechte, Kaskade, Wertebereich, Liste, Nichtbeeinflussung
- Modify: `tests/db_fixture.py` — `spiele_datei_ein(dsn, pfad)`, `spiele_sessions_ein(dsn)`, `frische_db` spielt beide Dateien ein, Docstring
- Modify: `bc1_service/postgres_store.py` — kein CREATE, Startprüfung, `company_id`, `aktualisiert_am`
- Modify: `tests/test_store_postgres.py` — Fixture über `frische_db` + Rollen-DSN, zwei Zusatztests
- Modify: `tests/test_postgres_init.py` — Start ohne Tabelle
- Modify: `bc1_service/db/EINSPIELEN.md` — zweite Datei, Skriptpfad, Rechte-Matrix, Live-Lauf
- Modify: `design/Abschlussplan-BC1.md` — B1 Stand
- Außerhalb des Repos (git-ignoriert): `.superpowers/sdd/Implementierungsplan-DB-Profil-Fundament/lauf.sh` Modus `sessions`; neue `einspielen-nachpruefung-sessions.sql` daneben

**Interfaces (Produces):**
- `tests.db_fixture.spiele_datei_ein(dsn: str, pfad: Path) -> None` — eine Datei als `bc1_role` in einer Transaktion
- `tests.db_fixture.spiele_sessions_ein(dsn: str) -> None` — `sessions.sql`
- `tests.db_fixture.spiele_ddl_ein(dsn: str) -> None` — **unverändert** `prozessprofil.sql` (viele Aufrufer)
- `tests.db.signatur_erzeugen.zeilen_aus_fehlertext(text: str) -> tuple[list[str], list[str]]` und `baue_block(zeilen: Iterable[str]) -> str`
- `PostgresStateStore(dsn)` — Signatur unverändert; wirft `RuntimeError` mit `sessions.sql` im Text, wenn `bc1.sessions` fehlt

---

## Reihenfolge

Task 0 (Branch, Plan) → Task 1 (Generator ins Repo, ohne DB-Änderung) → Task 2 (`sessions.sql` + Fixture + DDL-Tests) → Task 3 (Store) → Task 4 (Doku) → Task 5 (Zweitmeinung) → Task 6 (Live-Einspielen, Richard) → Task 7 (Abschluss, Push-Frage).

---

## Task 0: Branch und Plan-Commit

**Files:** dieser Plan.

- [ ] **Step 1:** `git switch -c bc1-b1-sessions-fundament` (ab `bc1-db-profil-fundament` @ `9a73eac`, Arbeitsbaum sauber — prüfen mit `git status --short`).
- [ ] **Step 2:** Container läuft? `docker ps --format '{{.Names}}'` → `bc1-test-pg`; sonst README-Befehl. Suite-Basis messen: `BC1_TEST_DB_DSN=… .venv/bin/pytest -q -W error` → erwartet **465 passed, 4 skipped**.
- [ ] **Step 3:** Commit `docs(bc1): Implementierungsplan B1 — bc1.sessions ins signierte Fundament`.

---

## Task 1: Signatur-Generator ins Repo, Zieldatei als Argument

**Files:**
- Create: `tests/db/signatur_erzeugen.py`
- Create: `tests/test_signatur_erzeugen.py`
- Modify: `tests/db_fixture.py:40-45` (`spiele_datei_ein`)

**Interfaces:**
- Produces: `zeilen_aus_fehlertext`, `baue_block`, CLI `uv run python tests/db/signatur_erzeugen.py <datei.sql>`
- Consumes: `tests.db_fixture.frische_db`, `verbindung`, neu `spiele_datei_ein`

- [ ] **Step 1: Failing Tests schreiben** (`tests/test_signatur_erzeugen.py`)

```python
"""Reine Teile des Signatur-Generators — ohne Datenbank."""
from tests.db.signatur_erzeugen import baue_block, zeilen_aus_fehlertext

FEHLERTEXT = """\
psycopg.errors.RaiseException: Nachpruefung fehlgeschlagen — Rollback.
  - fehlt:  platzhalter|wird|in|step7|ersetzt
  + zuviel: acl|sessions|bc1_role|SELECT|f
  + zuviel: spalte|sessions|session_id|text|notnull||-|-
CONTEXT:  PL/pgSQL function inline_code_block line 17 at RAISE
"""


def test_zeilen_aus_fehlertext_trennt_zuviel_und_fehlt():
    zeilen, fehlt = zeilen_aus_fehlertext(FEHLERTEXT)
    assert zeilen == ["acl|sessions|bc1_role|SELECT|f",
                      "spalte|sessions|session_id|text|notnull||-|-"]
    assert fehlt == ["platzhalter|wird|in|step7|ersetzt"]


def test_baue_block_sortiert_verdoppelt_hochkommas_und_schliesst_mit_semikolon():
    # Unsortierte Eingabe, ein CHECK-Ausdruck mit Hochkomma (muss als '' in die DDL).
    block = baue_block(["spalte|s|b|text|null||-|-",
                        "constraint|s|c|CHECK ((x = 'ja'::text))"])
    assert block == (
        "    ('constraint|s|c|CHECK ((x = ''ja''::text))'),\n"
        "    ('spalte|s|b|text|null||-|-');")
```

- [ ] **Step 2: RED messen** — `.venv/bin/pytest tests/test_signatur_erzeugen.py -q` → `ModuleNotFoundError: tests.db.signatur_erzeugen`.

- [ ] **Step 3: `tests/db_fixture.py` erweitern** (nur die Einspiel-Funktion; `spiele_ddl_ein` behält Name und Verhalten):

```python
def spiele_datei_ein(dsn: str, pfad: Path) -> None:
    """Spielt EINE Einspiel-Datei genau wie im Betrieb ein: EINE Transaktion, als bc1_role."""
    with psycopg.connect(dsn) as conn:          # autocommit=False => eine Transaktion
        conn.execute("SET ROLE bc1_role")
        conn.execute(pfad.read_text(encoding="utf-8"))
        conn.commit()


def spiele_ddl_ein(dsn: str) -> None:
    """prozessprofil.sql — Name bleibt, viele Aufrufer meinen genau diese Datei."""
    spiele_datei_ein(dsn, _DDL)
```

- [ ] **Step 4: Generator schreiben** (`tests/db/signatur_erzeugen.py`; Inhalt aus `../../signatur-erzeugen.py`, umgebaut):

```python
#!/usr/bin/env python
"""Erzeugt die Sollsignatur einer Einspiel-Datei neu (prozessprofil.sql oder sessions.sql).

WANN: nach JEDER Aenderung an der jeweiligen DDL und beim Wechsel der PostgreSQL-
Hauptversion — sonst bricht das eigene Einspielen mit "Fall 3" ab. Den Diff LESEN
und bewusst committen, niemals die Pruefung abschalten.

WIE: Der Signaturblock der Datei wird durch die Platzhalterzeile ersetzt, die Datei
gegen den frischen Test-Container eingespielt; die Nachpruefung schlaegt fehl und
listet den kompletten Ist-Bestand als "+ zuviel" — daraus entsteht der Block. Die
Transaktion rollt zurueck, es bleibt nichts stehen. NIE gegen die Supabase laufen
lassen: frische_db() droppt die Schemata public und bc1.

AUFRUF (aus bc1-context-discovery/, Container postgres:17 muss laufen):
    BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" \\
        uv run python tests/db/signatur_erzeugen.py bc1_service/db/sessions.sql
Ohne Argument: prozessprofil.sql. Danach: volle Suite laufen lassen.

HAUPTVERSION (K-H, 03.09.): Container und Ziel laufen PostgreSQL 17. Gegen 16 erzeugt,
fehlen die 'acl|<tabelle>|bc1_role|MAINTAIN|f'-Zeilen und das Einspielen im Ziel
bricht mit Fall 3 ab — an beiden Versionen gemessen.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

PLATZHALTER = "    ('platzhalter|wird|in|step7|ersetzt');"
PLATZHALTER_ZEILE = "platzhalter|wird|in|step7|ersetzt"
ERLAUBT = ("spalte|", "spalte_acl|", "constraint|", "index|", "trigger|",
           "trigger_intern|", "funktion|", "funktion_acl|", "eigentuemer|",
           "acl|", "mitglied|", "rls|", "policy|", "regel|", "kommentar|",
           "effektiv|", "effektiv_spalte|")
# Rollen sind CLUSTERWEIT und ueberleben frische_db(). Bleibt aus einer Probe eine
# Rolle stehen, landet sie ungefragt in der Sollsignatur (Review 03.09.) — deshalb
# vorher pruefen.
ERWARTETE_ROLLEN = {"bc0_loescher", "bc1_role", "bc2_role", "bc3_role", "bc4_role",
                    "bc_leser"}
STANDARD_DATEI = Path("bc1_service/db/prozessprofil.sql")


def zeilen_aus_fehlertext(text: str) -> tuple[list[str], list[str]]:
    """Liest aus dem Nachpruefungs-Fehler die '+ zuviel'- und '- fehlt'-Zeilen."""
    zeilen = re.findall(r"^\s*\+ zuviel: (.*)$", text, re.M)
    fehlt = re.findall(r"^\s*- fehlt:\s+(.*)$", text, re.M)
    return zeilen, fehlt


def baue_block(zeilen: Iterable[str]) -> str:
    """Sortierter VALUES-Block fuer INSERT INTO … soll_signatur; Hochkommas verdoppelt."""
    return ",\n".join("    ('" + z.replace("'", "''") + "')" for z in sorted(zeilen)) + ";"


def main(argv: list[str]) -> int:
    sys.path.insert(0, ".")
    from tests.db_fixture import DSN, frische_db, spiele_datei_ein, verbindung

    datei = Path(argv[1]) if len(argv) > 1 else STANDARD_DATEI
    if not DSN:
        sys.exit("BC1_TEST_DB_DSN ist nicht gesetzt.")
    quelle = datei.read_text(encoding="utf-8")
    if quelle.count(PLATZHALTER) != 1:
        sys.exit(f"Die Platzhalterzeile fehlt in {datei}. Vor dem Erzeugen den alten "
                 "Signaturblock durch genau diese Zeile ersetzen:\n" + PLATZHALTER)

    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, None) as conn:
        vorhanden = {r[0] for r in conn.execute(
            "SELECT rolname FROM pg_roles WHERE NOT rolsuper "
            "  AND rolname NOT LIKE 'pg\\_%'").fetchall()}
    if vorhanden != ERWARTETE_ROLLEN:
        sys.exit(
            "Der Cluster enthaelt nicht genau die erwarteten Rollen — Abbruch, sonst\n"
            "landen fremde Rollen in der Sollsignatur.\n"
            f"  zuviel: {sorted(vorhanden - ERWARTETE_ROLLEN)}\n"
            f"  fehlt:  {sorted(ERWARTETE_ROLLEN - vorhanden)}\n"
            "Proberollen entfernen (DROP OWNED BY <rolle>; DROP ROLE <rolle>) und\n"
            "erneut starten. Ist die Aenderung gewollt, ERWARTETE_ROLLEN anpassen.")

    try:
        spiele_datei_ein(DSN, datei)
    except Exception as fehler:                   # noqa: BLE001 — der Fehler IST das Ergebnis
        text = str(fehler)
    else:
        sys.exit("Das Einspielen lief durch — der Platzhalter war wohl schon ersetzt.")

    zeilen, fehlt = zeilen_aus_fehlertext(text)
    if not zeilen:
        sys.exit("Keine '+ zuviel'-Zeilen im Fehlertext:\n" + text[:2000])
    if fehlt != [PLATZHALTER_ZEILE]:
        sys.exit(f"Unerwartete 'fehlt'-Zeilen (Signatur unvollstaendig?): {fehlt}")
    fremd = [z for z in zeilen if not z.startswith(ERLAUBT)]
    if fremd:
        sys.exit(f"Unbekannte Signaturarten — ERLAUBT ergaenzen? {fremd[:3]}")

    datei.write_text(quelle.replace(PLATZHALTER, baue_block(zeilen)), encoding="utf-8")
    print(f"Sollsignatur eingesetzt in {datei}: {len(zeilen)} Zeilen")
    for art, n in sorted(Counter(z.split("|")[0] for z in zeilen).items()):
        print(f"    {art:16s} {n}")
    print("\nJetzt die volle Suite laufen lassen.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 5: GREEN messen** — `.venv/bin/pytest tests/test_signatur_erzeugen.py -q` → 2 passed.

- [x] **Step 6: Regression des Umbaus gegen `prozessprofil.sql`** — **als Dauertest umgesetzt** (`test_main_reproduziert_die_committete_sollsignatur_byteidentisch`, 13.09.: 176 Zeilen byteidentisch). Der manuelle Lauf unten ist damit überholt und bleibt nur als Beschreibung stehen:

```bash
S=/private/tmp/claude-501/-Users-rprezer-Desktop-Claude-Projekte-AutoCoE-Projekt/55759f28-fe59-4793-8d8f-8a822856439d/scratchpad
cp bc1_service/db/prozessprofil.sql "$S/prozessprofil.regress.sql"
# Signaturblock (Zeilen zwischen "-- << HIER" und dem abschliessenden ");") durch den Platzhalter ersetzen:
uv run python - "$S/prozessprofil.regress.sql" <<'PY'
import re, sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
neu = re.sub(r"(-- << HIER die generierte Sollsignatur einsetzen \(Step 7\) >>\n)(?:    \('.*\n?)+",
             r"\1    ('platzhalter|wird|in|step7|ersetzt');\n", t)
assert neu != t; open(p, "w", encoding="utf-8").write(neu)
PY
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" \
  uv run python tests/db/signatur_erzeugen.py "$S/prozessprofil.regress.sql"
diff bc1_service/db/prozessprofil.sql "$S/prozessprofil.regress.sql" && echo IDENTISCH
```
Erwartet: `Sollsignatur eingesetzt … 176 Zeilen` und `IDENTISCH`. Weicht es ab: Umbau falsch, nicht die DDL.

- [x] **Step 7:** Volle Suite → **473 passed / 4 skipped** (gemessen 13.09.). Commit `feat(bc1): Signatur-Generator ins Repo, Zieldatei als Argument (B1, Task 1)`.

- [ ] **Step 8 (Richard):** Alte Kopie `AutoCoE_Projekt/signatur-erzeugen.py` (außerhalb des Repos) löschen — Richards Datei, Richards Entscheidung; im Abschlussbericht fragen.

**Verlauf 13.09. (ausgeführt, Abweichungen vom Plan oben — ehrlich):** (1) Der Guard lehnte den Generator unter `bc1_service/db/` zu Recht ab: Dienstcode darf `tests.db_fixture` nicht importieren. Der Generator ist Entwicklungswerkzeug und liegt jetzt in **`tests/db/signatur_erzeugen.py`**; kein `__init__.py` unter `bc1_service/db/`. (2) Statt zwei Tests sind es **acht**, jeder einzeln RED→GREEN gefahren (Guard: ein Test je Schritt, Sicherheitsprüfungen nur mit eigenem Test): Parser, Blockbau, **Byteidentität gegen die committete Signatur** (ersetzt Step 6), Platzhalter fehlt, fremde Cluster-Rolle, unbekannte Signaturart, mehr als der Platzhalter fehlt, keine `zuviel`-Zeilen. Künstliche Einspiel-Dateien (`_kunstdatei`) erzeugen die Fehlertexte gezielt. (3) `spiele_datei_ein` in `db_fixture.py` wie geplant; `spiele_ddl_ein` unverändert im Verhalten.

---

## Task 2: `sessions.sql` — Dreifallregel, Sollsignatur, Anlage, Rechte

**Files:**
- Create: `bc1_service/db/sessions.sql`
- Create: `tests/test_ddl_sessions.py`
- Modify: `tests/db_fixture.py:20-38` (`_DDL_SESSIONS`, `spiele_sessions_ein`, `frische_db`)

**Interfaces:**
- Consumes: `spiele_datei_ein` (Task 1)
- Produces: `spiele_sessions_ein(dsn)`; `frische_db(dsn)` spielt beide Dateien ein; Tabelle `bc1.sessions(session_id text PK, company_id uuid NOT NULL FK companies CASCADE, version integer NOT NULL CHECK ≥ 1, state jsonb NOT NULL, aktualisiert_am timestamptz NOT NULL DEFAULT now())`

- [ ] **Step 1: Fixture erweitern** (`tests/db_fixture.py`)

```python
_GERUEST = Path(__file__).parent / "db" / "bc0_geruest.sql"
_DDL = Path(__file__).parents[1] / "bc1_service" / "db" / "prozessprofil.sql"
_DDL_SESSIONS = Path(__file__).parents[1] / "bc1_service" / "db" / "sessions.sql"


def frische_db(dsn: str, *, mit_ddl: bool = True) -> None:
    """Setzt public + bc1 zurueck, baut das Geruest, spielt (optional) BEIDE DDL-Dateien ein.

    Reihenfolge wie im Betrieb (EINSPIELEN.md): erst prozessprofil.sql, dann sessions.sql,
    jede als bc1_role in einer eigenen Transaktion. bc1.sessions entsteht damit NUR hier —
    der PostgresStateStore legt seit B1 nichts mehr an.
    """
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS bc1 CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(_GERUEST.read_text(encoding="utf-8"))
        _testdaten(conn)
    if mit_ddl:
        spiele_ddl_ein(dsn)
        spiele_sessions_ein(dsn)


def spiele_sessions_ein(dsn: str) -> None:
    """sessions.sql — zweite Einspiel-Einheit (B1)."""
    spiele_datei_ein(dsn, _DDL_SESSIONS)
```

- [ ] **Step 2: Failing Tests schreiben** (`tests/test_ddl_sessions.py`)

```python
"""sessions.sql — zweite Einspiel-Einheit (B1): Dreifallregel, Rechte, Kaskade, Wertebereich.

Alles hier laeuft gegen das Geruest MIT aktivem bc_leser-Automatismus
(ALTER DEFAULT PRIVILEGES in bc0_geruest.sql) — nur ein ausdrueckliches REVOKE
haelt bc_leser von der Tabelle fern (Positivkontrolle: test_db_fixture.py).
"""
import re
from pathlib import Path

import psycopg
import pytest

from tests.db_fixture import (DSN, MANDANT_A, MANDANT_B, frische_db, spiele_ddl_ein,
                              spiele_sessions_ein, verbindung)

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

_DB = Path(__file__).parents[1] / "bc1_service" / "db"
ALLE_RECHTE = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _tabellen(conn) -> set[str]:
    return {z[0] for z in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'bc1'").fetchall()}


def _session_anlegen(conn, session_id="s1", mandant=MANDANT_A, version=1) -> None:
    conn.execute(
        "INSERT INTO bc1.sessions (session_id, company_id, version, state) "
        "VALUES (%s, %s, %s, '{}')", (session_id, mandant, version))


def _anzahl(conn) -> int:
    return conn.execute("SELECT count(*) FROM bc1.sessions").fetchone()[0]


def test_fall_1_legt_die_tabelle_als_bc1_role_an():
    frische_db(DSN)                                   # spielt beide Dateien ein
    with verbindung(DSN, None) as conn:
        assert "sessions" in _tabellen(conn)
        eigentuemer = conn.execute(
            "SELECT tableowner FROM pg_tables "
            " WHERE schemaname = 'bc1' AND tablename = 'sessions'").fetchone()[0]
    assert eigentuemer == "bc1_role"


def test_fall_2_zweiter_lauf_ist_ein_no_op_und_laesst_daten_stehen():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        _session_anlegen(conn)
        conn.commit()
    spiele_sessions_ein(DSN)                          # zweiter Lauf, identischer Bestand
    with verbindung(DSN) as conn:
        assert _anzahl(conn) == 1


def test_fall_3_abweichende_spalte_bricht_ab_ohne_etwas_zu_aendern():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("ALTER TABLE bc1.sessions ADD COLUMN fremd integer")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_sessions_ein(DSN)
    assert "Sollsignatur" in str(fehler.value) and "fremd" in str(fehler.value)
    with verbindung(DSN, None) as conn:               # NICHTS geaendert: Spalte steht noch
        assert conn.execute(
            "SELECT count(*) FROM information_schema.columns "
            " WHERE table_schema = 'bc1' AND table_name = 'sessions' "
            "   AND column_name = 'fremd'").fetchone()[0] == 1


def test_fall_3_fremdes_leserecht_wird_erkannt():
    # Der Fall, um den es bei B1 geht: ein stilles GRANT an einen anderen BC.
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("GRANT SELECT ON bc1.sessions TO bc2_role")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_sessions_ein(DSN)
    assert "Sollsignatur" in str(fehler.value) and "bc2_role" in str(fehler.value)


def test_prozessprofil_sql_bleibt_nach_sessions_sql_ein_no_op():
    # Bedingung Richard (13.09.): die neue Datei darf die alte nicht beeinflussen.
    # Beide Richtungen: prozessprofil.sql sieht die vierte Tabelle nicht (Fall 2),
    # und sessions.sql bleibt nach einem weiteren prozessprofil-Lauf ebenfalls Fall 2.
    frische_db(DSN)
    with verbindung(DSN) as conn:
        _session_anlegen(conn)
        conn.commit()
    spiele_ddl_ein(DSN)                               # prozessprofil.sql erneut: Fall 2
    spiele_sessions_ein(DSN)                          # sessions.sql erneut: Fall 2
    with verbindung(DSN, None) as conn:
        assert _tabellen(conn) == {"prozessprofil", "profil_rollen",
                                   "profil_write_status", "sessions"}
    with verbindung(DSN) as conn:
        assert _anzahl(conn) == 1


def test_bc1_role_darf_alles_und_tut_es_wirklich():
    frische_db(DSN)
    with verbindung(DSN) as conn:                     # echter Vollzug, nicht nur has_table_privilege
        _session_anlegen(conn)
        conn.execute("UPDATE bc1.sessions SET version = 2 WHERE session_id = 's1'")
        assert conn.execute("SELECT version FROM bc1.sessions").fetchone()[0] == 2
        conn.execute("DELETE FROM bc1.sessions WHERE session_id = 's1'")
        assert _anzahl(conn) == 0
        conn.commit()


def test_bc_leser_und_fremde_bcs_haben_kein_einziges_recht():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        for rolle in ("bc_leser", "bc2_role", "bc3_role", "bc4_role"):
            for recht in ALLE_RECHTE:
                assert not conn.execute(
                    "SELECT has_table_privilege(%s, 'bc1.sessions', %s)",
                    (rolle, recht)).fetchone()[0], f"{rolle}/{recht}"
    with verbindung(DSN, "bc_leser") as conn:         # und der echte Versuch scheitert
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM bc1.sessions")


def test_mandanten_kaskade_raeumt_nur_die_eigene_sitzung():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        _session_anlegen(conn, "a1", MANDANT_A)
        _session_anlegen(conn, "b1", MANDANT_B)
        conn.commit()
    with verbindung(DSN, None) as conn:               # BC0/Admin loescht Mandant A
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(DSN) as conn:
        assert [z[0] for z in conn.execute(
            "SELECT session_id FROM bc1.sessions").fetchall()] == ["b1"]


@pytest.mark.parametrize("eingriff", [
    lambda conn: _session_anlegen(conn, version=0),                       # CHECK version >= 1
    lambda conn: conn.execute(                                              # company_id Pflicht
        "INSERT INTO bc1.sessions (session_id, version, state) VALUES ('x', 1, '{}')"),
    lambda conn: _session_anlegen(conn, mandant="99999999-9999-9999-9999-999999999999"),  # FK
])
def test_ungueltige_zeilen_werden_abgewiesen(eingriff):
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(psycopg.errors.IntegrityError):
            eingriff(conn)


def _umgebungsrollen(datei: str) -> set[str]:
    ddl = (_DB / datei).read_text(encoding="utf-8")
    block = ddl.split("umgebungsrollen (rolname) VALUES", 1)[1].split(";", 1)[0]
    return set(re.findall(r"\('([^']+)'\)", block))


def test_ausnahmeliste_ist_identisch_mit_prozessprofil_sql():
    # Die drei Namen sind in der Ziel-Supabase gemessen (EINSPIELEN.md, Abschnitt 5).
    # Beide Dateien tragen die Liste — driften sie, bricht eine von beiden live ab.
    assert _umgebungsrollen("sessions.sql") == _umgebungsrollen("prozessprofil.sql") \
        == {"postgres", "supabase_read_only_user", "supabase_etl_admin"}
```

- [ ] **Step 3: RED messen** — `.venv/bin/pytest tests/test_ddl_sessions.py -q` → alle rot (`FileNotFoundError: … sessions.sql` bzw. `ImportError: spiele_sessions_ein`). Außerdem `tests/test_ddl_einspielen.py` rot? Nein — `frische_db` würde jetzt `sessions.sql` laden und mit `FileNotFoundError` scheitern → **erwartet: die gesamte DB-Suite rot, bis Step 4 steht.** Nur Step 3 → Step 4 direkt hintereinander, kein Commit dazwischen.

- [ ] **Step 4: `sessions.sql` schreiben** — mit Platzhalter-Signatur:

```sql
-- BC1 Etappe 1, Paket B1 — Sitzungszustand des Interviews: bc1.sessions.
-- Zweite Einspiel-Einheit neben prozessprofil.sql: gleiche Dreifallregel, EIGENE
-- Sollsignatur, Geltungsbereich genau diese eine Tabelle. prozessprofil.sql bleibt
-- unveraendert — seine Signatur ist auf die drei Vertragstabellen eingeschraenkt und
-- sieht diese Tabelle nicht (Entscheidung 13.09.2026, Abschlussplan B1).
--
-- Einspielen (EINE Transaktion, Rollback bei jedem Fehler), NACH prozessprofil.sql:
--     psql -v ON_ERROR_STOP=1 -1 -f sessions.sql
-- Die Datei enthaelt bewusst KEIN BEGIN/COMMIT.
--
-- Was hier NICHT geprueft wird und warum: Mitgliedschafts-Kanten ('mitglied|') und
-- Funktionen sind global bzw. gehoeren zu prozessprofil.sql, das im Betrieb immer
-- zuerst laeuft und beides prueft. Ein GRANT bc1_role TO <irgendwer> bricht also
-- dort ab, bevor diese Datei an der Reihe ist.
--
-- Aufbau: 0 Voraussetzungen | 0b Sollsignatur | 1 Vorpruefung | 2 Anlage + 3 Rechte | 4 Nachpruefung

-- ============================================================
-- 0a. DETERMINISMUS UND DEPLOYMENT-SPERRE (wie prozessprofil.sql)
-- ============================================================
SET LOCAL search_path = public, pg_temp;
SELECT pg_advisory_xact_lock(hashtext('bc1.sessions.einspielen'));

-- ============================================================
-- 0. VORAUSSETZUNGEN
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'bc1') THEN
        RAISE EXCEPTION 'Schema bc1 fehlt. BC0 legt es an (ROLLEN.md, Schritt 5).';
    END IF;
    IF NOT has_schema_privilege(current_user, 'bc1', 'CREATE') THEN
        RAISE EXCEPTION 'Rolle % darf im Schema bc1 nichts anlegen.', current_user;
    END IF;
    IF NOT has_table_privilege(current_user, 'companies', 'REFERENCES') THEN
        RAISE EXCEPTION 'GRANT REFERENCES fehlt auf companies (von BC0 am 02.09. erteilt).';
    END IF;
END $$;

-- ============================================================
-- 0b. SOLLSIGNATUR — Geltungsbereich: NUR bc1.sessions
-- ============================================================
-- Erfasst wie prozessprofil.sql: Spalten · Constraints · Indizes · Trigger (eigene
-- UND Aktivierungszustand der internen FK-Trigger) · Eigentuemer · Tabellen- und
-- Spaltenrechte · effektive Rechte ALLER Rollen · RLS, Policies, Regeln · Kommentar.
-- Temp-Objekte tragen den Praefix bc1_sessions_, damit beide Dateien auch in
-- derselben Session nacheinander laufen koennen.
CREATE TEMP TABLE bc1_sessions_soll_signatur (zeile text PRIMARY KEY) ON COMMIT DROP;

-- BEKANNTE UMGEBUNGSROLLEN — WORTGLEICH zu prozessprofil.sql (Klaerpunkt K-G,
-- gemessen 03.09.2026 in der Ziel-Supabase, EINSPIELEN.md Abschnitt 5). Ein Test
-- haelt beide Listen identisch (tests/test_ddl_sessions.py).
CREATE TEMP TABLE bc1_sessions_umgebungsrollen (rolname text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO pg_temp.bc1_sessions_umgebungsrollen (rolname) VALUES
    -- Keine Semikolons in diesen Begruendungen: der Test liest bis zum ersten Semikolon.
    ('postgres'),                 -- Supabase-Administration, dort KEIN Superuser,
                                  -- Mitglied von bc1_role und bc_leser
    ('supabase_read_only_user'),  -- Supabase-Lesekonto, kommt ueber pg_read_all_data
    ('supabase_etl_admin');       -- Supabase-ETL, kommt ueber pg_read_all_data

INSERT INTO pg_temp.bc1_sessions_soll_signatur (zeile) VALUES
-- << HIER die generierte Sollsignatur einsetzen (signatur_erzeugen.py) >>
    ('platzhalter|wird|in|step7|ersetzt');

CREATE OR REPLACE TEMP VIEW bc1_sessions_ist_signatur AS
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
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND a.attnum > 0 AND NOT a.attisdropped
UNION ALL
SELECT format('constraint|%s|%s|%s', c.relname, con.conname,
              pg_get_constraintdef(con.oid))
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
SELECT format('index|%s|%s|%s', tablename, indexname, indexdef)
  FROM pg_indexes
 WHERE schemaname = 'bc1' AND tablename = 'sessions'
UNION ALL
SELECT format('trigger|%s|%s|%s|%s', c.relname, t.tgname,
              pg_get_triggerdef(t.oid), t.tgenabled)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND NOT t.tgisinternal
UNION ALL
-- Interne RI-Trigger: Name traegt OIDs, deshalb Schluessel = Constraint-Name;
-- der AKTIVIERUNGSZUSTAND gehoert in die Signatur (ein deaktivierter RI-Trigger
-- laesst die Constraint-Definition stehen und erzwingt den FK trotzdem nicht).
SELECT format('trigger_intern|%s|%s|%s', c.relname, con.conname, t.tgenabled)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_constraint con ON con.oid = t.tgconstraint
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND t.tgisinternal
UNION ALL
SELECT format('eigentuemer|%s|%s', c.relname, pg_get_userbyid(c.relowner))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
-- Gesetzte Rechte VOLLSTAENDIG: aclexplode listet JEDEN Grantee, auch PUBLIC.
SELECT format('acl|%s|%s|%s|%s', c.relname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(
      coalesce(c.relacl, acldefault('r', c.relowner))) AS acl
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
-- Spaltenrechte liegen in pg_attribute.attacl, nicht in relacl.
SELECT format('spalte_acl|%s|%s|%s|%s|%s', c.relname, a.attname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(a.attacl) AS acl
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND a.attnum > 0 AND NOT a.attisdropped AND a.attacl IS NOT NULL
UNION ALL
SELECT format('rls|%s|%s|%s', c.relname, c.relrowsecurity, c.relforcerowsecurity)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
SELECT format('policy|%s|%s|%s|%s', c.relname, pol.polname, pol.polcmd,
              coalesce(pg_get_expr(pol.polqual, pol.polrelid), '-'))
  FROM pg_policy pol
  JOIN pg_class c ON c.oid = pol.polrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
SELECT format('regel|%s|%s', c.relname, r.rulename)
  FROM pg_rewrite r
  JOIN pg_class c ON c.oid = r.ev_class
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
SELECT format('kommentar|%s|%s', c.relname, md5(d.description))
  FROM pg_description d
  JOIN pg_class c ON c.oid = d.objoid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions' AND d.objsubid = 0
UNION ALL
-- EFFEKTIVE Sicht ueber ALLE Rollen; ausgenommen Superuser, pg_*-Systemrollen und
-- die drei Umgebungsrollen (wie prozessprofil.sql).
SELECT format('effektiv|%s|%s|%s', c.relname, r.rolname, priv)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace,
       pg_roles r,
       unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) AS priv
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND NOT r.rolsuper AND r.rolname NOT LIKE 'pg\_%'
   AND r.rolname NOT IN (SELECT rolname FROM pg_temp.bc1_sessions_umgebungsrollen)
   AND has_table_privilege(r.oid, c.oid, priv)
UNION ALL
SELECT format('effektiv_spalte|%s|%s|%s', c.relname, r.rolname, priv)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace,
       pg_roles r,
       unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']) AS priv
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND NOT r.rolsuper AND r.rolname NOT LIKE 'pg\_%'
   AND r.rolname NOT IN (SELECT rolname FROM pg_temp.bc1_sessions_umgebungsrollen)
   AND has_any_column_privilege(r.oid, c.oid, priv);

-- ============================================================
-- 1. VORPRUEFUNG — Dreifallregel, VOR jeder Aenderung
-- ============================================================
CREATE TEMP TABLE bc1_sessions_einspiel_modus (modus text NOT NULL) ON COMMIT DROP;

DO $$
DECLARE vorhanden integer; abweichung text;
BEGIN
    SELECT count(*) INTO vorhanden
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'bc1' AND c.relname = 'sessions';

    IF vorhanden = 0 THEN
        INSERT INTO pg_temp.bc1_sessions_einspiel_modus VALUES ('anlegen');
        RAISE NOTICE 'Fall 1: bc1.sessions nicht vorhanden — Anlage.';
        RETURN;
    END IF;

    -- Eine Sicht oder Sequenz dieses Namens ist ebenfalls Fall 3, keine Tabelle.
    IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'bc1' AND c.relname = 'sessions' AND c.relkind = 'r') THEN
        RAISE EXCEPTION 'Fall 3: bc1.sessions existiert, ist aber keine Tabelle. Abbruch OHNE Aenderung.';
    END IF;

    SELECT string_agg(zeile, E'\n' ORDER BY zeile) INTO abweichung FROM (
        SELECT format('  - fehlt:  %s', zeile) AS zeile
          FROM (SELECT zeile FROM bc1_sessions_soll_signatur
                EXCEPT SELECT zeile FROM bc1_sessions_ist_signatur) a
        UNION ALL
        SELECT format('  + zuviel: %s', zeile)
          FROM (SELECT zeile FROM bc1_sessions_ist_signatur
                EXCEPT SELECT zeile FROM bc1_sessions_soll_signatur) b) diff;

    IF abweichung IS NOT NULL THEN
        RAISE EXCEPTION E'Fall 3: Bestand weicht von der Sollsignatur ab. Abbruch OHNE Aenderung.\n%',
                        abweichung;
    END IF;
    INSERT INTO pg_temp.bc1_sessions_einspiel_modus VALUES ('noop');
    RAISE NOTICE 'Fall 2: Bestand ist identisch zur Sollsignatur — No-op.';
END $$;

-- ============================================================
-- 2. ANLAGE + 3. RECHTE — NUR im Fall 1
-- ============================================================
-- Nackte CREATEs ohne IF NOT EXISTS: im Fall 1 ist garantiert nichts da, ein
-- unerwarteter Restbestand soll zum Fehler werden statt zur stillen Ersetzung.
DO $einspielen$
BEGIN
    IF (SELECT modus FROM pg_temp.bc1_sessions_einspiel_modus) <> 'anlegen' THEN
        RAISE NOTICE 'Fall 2: Bestand identisch — es wird NICHTS ausgefuehrt.';
        RETURN;
    END IF;

    -- ---------- Abschnitt 2: Anlage ----------
    -- Schluessel session_id allein (wie profil_write_status, wie StateStore.load);
    -- company_id als Pflichtspalte mit Loeschkaskade: der Interview-Rohtext stirbt
    -- mit dem Mandanten (DSGVO). version >= 1 pinnt den Store-Vertrag (erster save
    -- schreibt 1). Kein Trigger: Sitzungen sind veraenderlich, der Store sperrt
    -- optimistisch per Compare-and-Swap auf version.
    EXECUTE $ddl$ CREATE TABLE bc1.sessions (
        session_id      text        NOT NULL,
        company_id      uuid        NOT NULL,
        version         integer     NOT NULL,
        state           jsonb       NOT NULL,
        aktualisiert_am timestamptz NOT NULL DEFAULT now(),

        CONSTRAINT sessions_pkey PRIMARY KEY (session_id),
        CONSTRAINT sessions_version_positiv CHECK (version >= 1),
        CONSTRAINT sessions_company_fk FOREIGN KEY (company_id)
            REFERENCES companies (company_id) ON DELETE CASCADE
    ) $ddl$;

    EXECUTE $ddl$ COMMENT ON TABLE bc1.sessions IS
        'Sitzungszustand des Interviews (Felder, Gespraechslog mit Rohtext, Antworten). '
        'Interne Tabelle: ausschliesslich bc1_role, ausdruecklich NICHT in der '
        'Fremdschema-Lesematrix (REVOKE in Abschnitt 3). Lebt und stirbt mit dem Mandanten.' $ddl$;

    -- ---------- Abschnitt 3: Rechte ----------
    -- bc1_role: alles. bc_leser (Gruppenrolle; BC2, BC3, BC4 lesen darueber): NICHTS —
    -- das REVOKE ist Pflicht, weil Umgebungen mit ALTER DEFAULT PRIVILEGES
    -- (Test-Geruest; die Supabase bis 08.09.) jede neue Tabelle sonst still oeffnen.
    EXECUTE $ddl$ REVOKE ALL ON bc1.sessions FROM PUBLIC $ddl$;
    EXECUTE $ddl$ GRANT SELECT, INSERT, UPDATE, DELETE ON bc1.sessions TO bc1_role $ddl$;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
        EXECUTE $ddl$ REVOKE ALL ON bc1.sessions FROM bc_leser $ddl$;
    END IF;
END
$einspielen$;

-- ============================================================
-- 4. NACHPRUEFUNG — der Bestand MUSS jetzt exakt der Sollsignatur entsprechen
-- ============================================================
DO $$
DECLARE abweichung text;
BEGIN
    IF (SELECT modus FROM pg_temp.bc1_sessions_einspiel_modus) <> 'anlegen' THEN
        RETURN;              -- Fall 2: die Vorpruefung hat schon verglichen
    END IF;
    SELECT string_agg(zeile, E'\n' ORDER BY zeile) INTO abweichung FROM (
        SELECT format('  - fehlt:  %s', zeile) AS zeile
          FROM (SELECT zeile FROM bc1_sessions_soll_signatur
                EXCEPT SELECT zeile FROM bc1_sessions_ist_signatur) a
        UNION ALL
        SELECT format('  + zuviel: %s', zeile)
          FROM (SELECT zeile FROM bc1_sessions_ist_signatur
                EXCEPT SELECT zeile FROM bc1_sessions_soll_signatur) b) diff;

    IF abweichung IS NOT NULL THEN
        RAISE EXCEPTION E'Nachpruefung fehlgeschlagen — Rollback.\n%', abweichung;
    END IF;
    RAISE NOTICE 'Sollsignatur bestaetigt.';
END $$;
```

- [ ] **Step 5: Sollsignatur erzeugen**

```bash
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" \
  uv run python tests/db/signatur_erzeugen.py bc1_service/db/sessions.sql
```
Erwartet: Block mit u. a. `acl|sessions|bc1_role|…` (8 Rechte), **keine** Zeile mit `bc_leser`, `effektiv|sessions|bc1_role|…` (7), `constraint|sessions|sessions_company_fk|…`, `trigger_intern|sessions|sessions_company_fk|O`, `kommentar|sessions|…`, `rls|sessions|f|f`, 5 `spalte|`-Zeilen, `index|sessions|sessions_pkey|…`, `eigentuemer|sessions|bc1_role`. `git diff bc1_service/db/sessions.sql` lesen: jede Zeile erklärbar. Steht eine `bc_leser`-Zeile drin, fehlt das REVOKE — **nicht** die Signatur anpassen.

- [ ] **Step 6: GREEN messen** — `.venv/bin/pytest tests/test_ddl_sessions.py tests/test_ddl_einspielen.py tests/test_db_fixture.py -q` → alles grün (12 neue Testfälle inkl. 3 Parametrisierungen + Bestand). Dann volle Suite: erwartet **485 passed / 4 skipped** (473 nach Task 1 + 12).

- [x] **Step 7:** `git diff --stat` zeigt `prozessprofil.sql` **nicht** (gemessen). Commit `feat(bc1): sessions.sql — bc1.sessions signiert, nur bc1_role, Loeschkaskade (B1, Task 2)`.

**Verlauf 13.09. (ausgeführt):** Signatur **32 Zeilen** (8 `acl|`, 3 `constraint|`, 7 `effektiv|`, 4 `effektiv_spalte|`, 5 `spalte|`, je 1 `eigentuemer|`/`index|`/`kommentar|`/`rls|`/`trigger_intern|`), keine `bc_leser`-Zeile — das REVOKE greift gegen den Gerüst-Automatismus. Suite **485 passed / 4 skipped**. **Ein Bestandstest musste angepasst werden, ehrlich benannt:** `test_ddl_trigger.py::test_kaskadentests_laufen_im_unguenstigsten_fall` verlangte, dass der Kaskadentrigger von `bc1.prozessprofil` auf `companies` als **letzter** feuert; seit `sessions.sql` danach eingespielt wird, feuert `bc1.sessions` als letzter. Die Zusicherung dahinter (jede bc1-Kaskade nach jeder fremden) gilt unverändert — der Test prüft jetzt genau das plus die Einspiel-Reihenfolge der bc1-Tabellen (je FK zwei RI-Trigger, deshalb entdoppelt). Nicht aufgeweicht, sondern präzisiert. Generator-Startblock: `sys.path.insert(0, ".")` nötig, als Skript liegt `tests` nicht neben der Datei.

---

## Task 3: `PostgresStateStore` ohne CREATE, Startprüfung, `company_id`

**Files:**
- Modify: `bc1_service/postgres_store.py` (ganze Datei, 80 Zeilen)
- Modify: `tests/test_store_postgres.py`
- Modify: `tests/test_postgres_init.py` (ein Test dazu)

**Interfaces:**
- Consumes: Tabelle aus Task 2; `frische_db`
- Produces: `PostgresStateStore(dsn)` — wirft `RuntimeError("bc1.sessions fehlt …sessions.sql…")` ohne Tabelle, Pool geschlossen; INSERT schreibt `company_id`; UPDATE setzt `aktualisiert_am = now()`

- [ ] **Step 1: Vertrags-Fixture umstellen** (`tests/test_store_postgres.py`) — Store läuft wie im Betrieb als `bc1_role` gegen die eingespielte Tabelle. Die Rolle hängt als libpq-Option an der DSN (**am 13.09. am Container gemessen:** `psycopg.connect` und `ConnectionPool` liefern `current_user = bc1_role`) — kein Test-Schalter im Store.

```python
import os

import pytest

from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung
from tests.store_contract import StoreVertrag, _fetter_state

pytestmark = pytest.mark.skipif(
    not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt (lokales Test-Postgres nötig)"
)

# Wie im Betrieb (EINSPIELEN.md, Abschnitt 6): der Store verbindet als bc1_role.
# Im Container haengt die Rolle als libpq-Option an der DSN — die README-DSN traegt
# keine Query-Parameter, deshalb reicht '?'.
ROLLEN_DSN = f"{DSN}?options=-c%20role%3Dbc1_role" if DSN else None


class TestPostgresStore(StoreVertrag):
    @pytest.fixture
    def store(self):
        from bc1_service.postgres_store import PostgresStateStore

        frische_db(DSN)                  # Geruest + prozessprofil.sql + sessions.sql
        s = PostgresStateStore(ROLLEN_DSN)
        yield s
        s.close()

    def test_company_id_steht_typisiert_in_der_spalte(self, store):
        store.save(_fetter_state("s1"))
        with verbindung(DSN) as conn:
            zeile = conn.execute(
                "SELECT company_id::text, version FROM bc1.sessions "
                " WHERE session_id = 's1'").fetchone()
        assert zeile == (MANDANT_A, 1)

    def test_session_ohne_mandant_wird_von_der_datenbank_abgewiesen(self, store):
        # Der Kern setzt company_id beim ersten Turn (core.py); die Datenbank haelt
        # das als NOT NULL fest — keine mandantenlose Sitzung, auch nicht aus Versehen.
        import psycopg

        st = _fetter_state("ohne")
        st.company_id = None
        with pytest.raises(psycopg.errors.NotNullViolation):
            store.save(st)


def test_start_ohne_tabelle_bricht_mit_hinweis_auf_die_einspiel_datei_ab():
    # Echter Fehlpfad am Container, nicht nur der Stub in test_postgres_init.py:
    # Geruest ohne unsere DDL — Schema bc1 existiert, bc1.sessions nicht.
    from bc1_service.postgres_store import PostgresStateStore

    frische_db(DSN, mit_ddl=False)
    with pytest.raises(RuntimeError, match="sessions.sql"):
        PostgresStateStore(ROLLEN_DSN)
```

- [ ] **Step 2: Start-ohne-Tabelle-Test** (`tests/test_postgres_init.py`, anhängen)

```python
class _StubCursorOhneTabelle:
    def fetchone(self):
        return (False,)


class _StubVerbindungOhneTabelle:
    def execute(self, *args, **kwargs):
        return _StubCursorOhneTabelle()


class _StubPoolOhneTabelle(_StubPool):
    @contextmanager
    def connection(self):
        yield _StubVerbindungOhneTabelle()


# Seit B1 legt der Store die Tabelle nicht mehr an. Fehlt sie, soll der Dienst mit
# einem Hinweis auf die Einspiel-Datei stehenbleiben — und den Pool schliessen.
def test_fehlende_tabelle_meldet_die_einspiel_datei_und_schliesst_den_pool(monkeypatch):
    pools: list[_StubPoolOhneTabelle] = []

    def _fabrik(*args, **kwargs) -> _StubPoolOhneTabelle:
        pool = _StubPoolOhneTabelle()
        pools.append(pool)
        return pool

    monkeypatch.setattr(postgres_store, "ConnectionPool", _fabrik)
    with pytest.raises(RuntimeError, match="sessions.sql"):
        postgres_store.PostgresStateStore("postgresql://egal/egal")
    assert pools and pools[0].geschlossen
```

- [ ] **Step 3: RED messen** — `.venv/bin/pytest tests/test_store_postgres.py tests/test_postgres_init.py -q`. Erwartet: Vertragssuite rot mit `NotNullViolation` bei `company_id` (der alte INSERT kennt die Spalte nicht; `CREATE TABLE IF NOT EXISTS` ist gegen die bestehende Tabelle ein No-op) und der neue Init-Test rot (kein `RuntimeError`, der Stub-Cursor hat kein `rowcount`… → tatsächliche Meldung notieren).

- [ ] **Step 4: Store umbauen** (`bc1_service/postgres_store.py`, vollständig):

```python
"""Persistenter StateStore auf PostgreSQL (Supabase-Schema `bc1`).

Vertrag identisch zum InMemoryStateStore (siehe tests/store_contract.py).
Optimistisches Locking atomar per Compare-and-Swap-UPDATE — damit ist die
Nebenläufigkeit hier per Konstruktion sicher, nicht per Prozess-Lock.
Nur Standard-Postgres, keine Supabase-Spezialfeatures.

Die Tabelle bc1.sessions legt seit B1 NICHT mehr der Store an, sondern die
signierte Einspiel-Datei bc1_service/db/sessions.sql (EINSPIELEN.md) — als
bc1_role, mit ausdruecklichem REVOKE fuer bc_leser. Fehlt sie, bleibt der
Dienst beim Start stehen, statt eine unsignierte Tabelle zu erzeugen.
"""
from __future__ import annotations

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from bc1_core.serialize import state_from_dict, state_to_dict
from bc1_core.store import StaleStateError, StateStore
from bc1_core.types import SessionState

_TABELLE_VORHANDEN_SQL = "SELECT to_regclass('bc1.sessions') IS NOT NULL"


class PostgresStateStore(StateStore):
    def __init__(self, dsn: str) -> None:
        self._pool = ConnectionPool(dsn, min_size=1, max_size=10, open=True)
        try:
            with self._pool.connection() as conn:
                vorhanden = conn.execute(_TABELLE_VORHANDEN_SQL).fetchone()[0]
            if not vorhanden:
                raise RuntimeError(
                    "bc1.sessions fehlt — der Dienst legt die Tabelle nicht mehr an. "
                    "Einspielen als bc1_role: bc1_service/db/sessions.sql "
                    "(Anleitung: bc1_service/db/EINSPIELEN.md)."
                )
        except Exception:
            # Der Pool ist bereits offen: ohne close() blieben seine
            # Verbindungen und Worker-Threads als Leiche zurueck.
            self._pool.close()
            raise

    def close(self) -> None:
        self._pool.close()

    def load(self, session_id: str) -> SessionState | None:
        with self._pool.connection() as conn:
            zeile = conn.execute(
                "SELECT state FROM bc1.sessions WHERE session_id = %s",
                (session_id,),
            ).fetchone()
        return state_from_dict(zeile[0]) if zeile else None

    def save(self, state: SessionState) -> None:
        neue_version = state.version + 1
        daten = state_to_dict(state)
        daten["version"] = neue_version
        with self._pool.connection() as conn:
            if state.version == 0:
                cursor = conn.execute(
                    "INSERT INTO bc1.sessions (session_id, company_id, version, state) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (session_id) DO NOTHING",
                    (state.session_id, state.company_id, neue_version, Jsonb(daten)),
                )
                if cursor.rowcount == 0:
                    raise StaleStateError(
                        f"stale write for {state.session_id}: "
                        f"Session existiert bereits, got 0"
                    )
            else:
                cursor = conn.execute(
                    "UPDATE bc1.sessions "
                    "SET state = %s, version = %s, aktualisiert_am = now() "
                    "WHERE session_id = %s AND version = %s",
                    (Jsonb(daten), neue_version, state.session_id, state.version),
                )
                if cursor.rowcount == 0:
                    raise StaleStateError(
                        f"stale write for {state.session_id}: "
                        f"gespeicherter Stand weicht ab, got {state.version}"
                    )
        state.version = neue_version
```
Bewusst **nicht** geändert: `company_id` bleibt beim UPDATE unangetastet (der Kern prüft den Mandanten vor jedem Turn, `pruefe_mandant`); kein Python-Guard für `company_id is None` — die Datenbank sagt es (Test Step 1), der Kern setzt es immer.

- [ ] **Step 5: GREEN messen** — `.venv/bin/pytest tests/test_store_postgres.py tests/test_postgres_init.py -q` → 14 + 4 grün (11 Vertrag + 3 neu; 3 Bestand + 1 neu). Der bestehende Test `test_pool_wird_bei_init_fehler_geschlossen` (Stub wirft bei `execute`) bleibt grün. Volle Suite: erwartet **489 passed / 4 skipped**.

- [x] **Step 6:** Docstring in `tests/db_fixture.py` geprüft (Task 2 hat ihn ersetzt). Commit `feat(bc1): PostgresStateStore legt nichts mehr an — Startpruefung, company_id-Spalte (B1, Task 3)`.

**Verlauf 13.09. (ausgeführt, ehrlich):** (1) **Befund:** Als `bc1_role` scheiterte der alte Konstruktor an `CREATE SCHEMA IF NOT EXISTS bc1` mit `permission denied for database` — der Store hätte live (DSN = `bc1_role`) **nie starten können**; die alte Fixture (Superuser) hat das verdeckt. B1 behebt das nebenbei. (2) **Reihenfolge vom Guard erzwungen:** Drei Vertragstests bauen einen nackten `SessionState("s1", "0.1")` ohne Mandant; gegen die Pflichtspalte scheitern sie mit `NotNullViolation`. Der Guard erlaubt keine Änderung roter Bestandstests, und der Store darf den Mandanten nicht optional machen. Deshalb per `git checkout` zurück auf den grünen Stand, in `store_contract.py` den Helfer `_leerer_state()` (mandantengebunden, wie der Kern ihn erzeugt) als **Refactoring bei Grün** eingezogen, dann Task 3 erneut: Fixture → 12 Fixture-Fehler → CREATE raus → 11 `NotNullViolation`/DID-NOT-RAISE → INSERT/UPDATE → nur noch der alte Init-Test rot → Existenzabfrage → neuer Stub-Test rot → `RuntimeError` → Container-Test und NOT-NULL-Test grün bei Ankunft. Suite **489 passed / 4 skipped**. (3) `test_store_postgres.py` importiert `DSN` jetzt aus `db_fixture` statt selbst aus der Umgebung.

---

## Task 4: Betriebsdoku und Abschlussplan

**Files:**
- Modify: `bc1_service/db/EINSPIELEN.md` (Kopf, §2, §4, §7, neuer §10-Platzhalter für den Live-Lauf)
- Modify: `design/Abschlussplan-BC1.md` (Zeile B1)

- [ ] **Step 1: `EINSPIELEN.md`**
  - Titel → „`prozessprofil.sql` und `sessions.sql` einspielen — Anleitung und Rechte-Ist-Stand"; „Fünf Sätze": Satz ergänzen: *„Seit B1 gibt es eine zweite Datei `sessions.sql` für die Sitzungstabelle — gleiche Dreifallregel, eigene Signatur, läuft NACH `prozessprofil.sql`."*
  - §2 Einspielen: zweiter Befehl `psql "$BC1_DB_DSN" -v ON_ERROR_STOP=1 -1 -f bc1_service/db/sessions.sql`, Reihenfolge begründet (Mitgliedschafts-Kanten prüft nur die erste Datei).
  - §4 Sollsignatur: Befehl auf `uv run python tests/db/signatur_erzeugen.py <datei>` umstellen; Satz: Platzhalterzeile je Datei, Generator liegt im Repo.
  - §7 Rechte-Matrix: Zeile `bc1.sessions | alles | **nichts** (ausdrückliches REVOKE)`.
  - §9 bleibt (08.09.); neuer **§10 „Zweiter Lauf: `sessions.sql` — <Datum>"** mit Tabelle Vorprüfung/Lauf 1/Lauf 2/Nachprüfung, zunächst mit dem Vermerk *„offen, wird nach dem Live-Lauf gefüllt (Task 6)"* — kein erfundenes Ergebnis.
  - Anhang „Was sie NICHT abdeckt": Satz ergänzen, dass `sessions.sql` `mitglied|` und Funktionen nicht prüft und warum.
- [ ] **Step 2: `Abschlussplan-BC1.md`**, Zeile B1: Ziel-Spalte ergänzen um *„**Stand 13.09.:** gebaut als eigene Einspiel-Einheit `sessions.sql` (Entscheidung: Dreifallregel kennt nur alles/nichts, live stehen die neun Objekte); Schlüssel `session_id` allein, `company_id` Pflichtspalte mit Kaskade; Store legt nichts mehr an; Suite 489 grün"*; Nächster-Schritt-Spalte: *„Live-Einspielen als Fall 1 (lauf.sh `sessions`), Nachprüfung, EINSPIELEN.md §10"*. Kleinpunkt ergänzen: *„Signatur-Sicht liegt jetzt zweimal (prozessprofil.sql, sessions.sql) — bei einer dritten Einheit in einen Generator ziehen, nicht vorher (YAGNI)."*
- [ ] **Step 3:** Commit `docs(bc1): EINSPIELEN.md zweite Einspiel-Einheit, Abschlussplan B1 (B1, Task 4)`.

---

## Task 5: Unabhängige Zweitmeinung

Tragweite: Datenmodell + Rechte + Signaturmechanik → Pflicht (CLAUDE.md, Reviews).

- [ ] **Step 1:** Review-Agent (frischer Kontext) mit dem Diff `git diff bc1-db-profil-fundament...HEAD` und dieser Datei; Fragen: (1) Kann `sessions.sql` die alte Datei live in Fall 3 treiben? (2) Gibt es einen Weg, wie `bc_leser`/`bc2_role` an `bc1.sessions` kommt, den die Signatur nicht sieht — insbesondere über die weggelassenen `mitglied|`-Zeilen? (3) Verhält sich der Store bei fehlender Tabelle, fehlender Rolle, fehlendem `company_id` korrekt? (4) Verliert die Kaskade Daten, die bleiben müssten? (5) Ist der Generator-Umbau äquivalent (Regressionsschritt Task 1 Step 6)?
- [ ] **Step 2:** Findings nach Schwere adjudizieren: Critical/Important nachmessen und fixen (TDD), Minor begründet fixen oder mit Ziel in den Abschlussplan (Kleinpunkte). Jeder Fix: eigener Commit `fix(bc1): …`.
- [ ] **Step 3:** Volle Suite grün, Stand hier im Plan als Changelog-Absatz festhalten.

---

## Task 6: Live-Einspielen in die Supabase (Richard führt aus, Claude liest Logs)

**Files (git-ignoriert, SDD-Ordner):** `lauf.sh` Modus `sessions`; `einspielen-nachpruefung-sessions.sql`.

- [ ] **Step 1:** `lauf.sh` ergänzen (nach `ein)`):

```bash
  sessions) LOG=$SDD/einspielen-sessions.log
        { echo "--- LAUF 1 ---"
          psql "$DSN" -v ON_ERROR_STOP=1 -1 -f bc1_service/db/sessions.sql 2>&1
          echo "--- LAUF 2 (Idempotenz) ---"
          psql "$DSN" -v ON_ERROR_STOP=1 -1 -f bc1_service/db/sessions.sql 2>&1
        } >"$LOG" ;;
```

- [ ] **Step 2:** `einspielen-nachpruefung-sessions.sql` anlegen:

```sql
\echo === A) Tabellen in bc1 + Eigentuemer (Erwartung: 4, sessions gehoert bc1_role, ACL ohne bc_leser) ===
select c.relname, pg_get_userbyid(c.relowner) as eigentuemer, c.relacl
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = 'bc1' and c.relkind = 'r' order by 1;
\echo === B) Rechte auf bc1.sessions (Erwartung: bc1_role t, alle anderen f) ===
select r.rolname, has_table_privilege(r.oid, 'bc1.sessions', 'SELECT') as sel,
       has_table_privilege(r.oid, 'bc1.sessions', 'INSERT') as ins
  from pg_roles r where r.rolname in ('bc1_role','bc_leser','bc2_role','bc3_role','bc4_role','postgres') order by 1;
\echo === C) Fremdschluessel validiert ===
select conname, convalidated from pg_constraint where conrelid = 'bc1.sessions'::regclass order by 1;
\echo === D) prozessprofil.sql weiterhin Fall 2? (wird durch 'lauf.sh ein' gemessen, LAUF 2 muss 'Fall 2' melden) ===
```

- [ ] **Step 3 (Richard):** Reihenfolge: `bash lauf.sh ein` (muss zweimal „Fall 2" melden — alte Datei unbeeinflusst, Vorbedingung) → `bash lauf.sh sessions` (Erwartung Lauf 1: `Fall 1` + `Sollsignatur bestaetigt.`, Lauf 2: `Fall 2`) → `bash lauf.sh sql einspielen-nachpruefung-sessions.sql`. Vorher die Umgebungsrollen-Abfrage aus EINSPIELEN.md §5 laufen lassen, falls seit 12.09. neue Rollen dazukamen (Stand 12.09.: unverändert).
- [ ] **Step 4 (Claude):** Logs lesen, Ergebnis in `EINSPIELEN.md` §10 eintragen (gemessene NOTICE-Zeilen, Tabelle A–C). Bei Fall 3: Abweichung Zeile für Zeile verstehen, **nie** die Prüfung abschalten; wahrscheinlichste Ursache: neue Rolle in der Supabase → §5-Abfrage.
- [ ] **Step 5:** Commit `docs(bc1): sessions.sql live eingespielt — Fall 1, Nachpruefung (B1, Task 6)`.

---

## Task 7: Abschluss

- [ ] **Step 1:** Volle Suite final messen, Zahl in Abschlussplan/EINSPIELEN eintragen.
- [ ] **Step 2:** Vertraulichkeits-Check vor Push: `git diff bc1-db-profil-fundament...HEAD --stat`; `git grep -n -i -E "passw|secret|supabase\.co|@gmail" -- $(git diff --name-only bc1-db-profil-fundament...HEAD)` → 0 Treffer außer bekannten Variablennamen. Befund Richard vorlegen; **Push nur nach OK**. Ziel-Branch der PR: `bc1-db-profil-fundament` (oder `main`, falls der Merge-Kleinpunkt vorher erledigt ist — Richards Entscheidung).
- [ ] **Step 3:** `SESSION-HANDOFF.md` (lokal) aktualisieren: B1-Stand, offene Richard-Todos (alte Generator-Kopie löschen, Live-Lauf, Push).

---

## Selbstprüfung des Plans (13.09.2026)

- **Spec-Abdeckung:** Tabelle in eigener signierter Datei (Task 2) · `bc_leser` ausdrücklich verneint + Test als `bc1_role` (Task 2, Test 7 mit Automatismus; Task 3 Fixture als `bc1_role`) · Store legt nichts mehr an (Task 3) · Schlüsselentscheidung dokumentiert (Kopf, Roadmap-Anker bleibt) · Nichtbeeinflussung als Test + Live-Vorbedingung (Task 2/6) · Generator im Repo (Task 1) · Doku (Task 4) · Zweitmeinung (Task 5) · Einspielen als Fall 1 (Task 6).
- **Platzhalter:** keine; §10 in EINSPIELEN.md ist bewusst als „offen" markiert, bis gemessen.
- **Typkonsistenz:** `spiele_datei_ein(dsn, pfad)` (Task 1) ↔ Aufruf in `spiele_sessions_ein` und Generator (Task 2/1) · `ROLLEN_DSN` nur in `test_store_postgres.py` · `_fetter_state` aus `store_contract` importiert (existiert, setzt `company_id = MANDANT_A`).
- **Ehrlich offen:** (1) Der Vorprüfungs-`RAISE NOTICE`-Text für Fall 1 weicht bewusst von prozessprofil.sql ab („bc1.sessions nicht vorhanden"); Tests prüfen nur Fall-3-Texte. (2) Die Signatur-Sicht ist dupliziert — nachgehalten als Kleinpunkt. (3) Der Fehlpfad „Tabelle fehlt" wird zweimal gemessen: per Stub (Pool wird geschlossen) und als echter Container-Lauf (`frische_db(mit_ddl=False)` + Store) — beide in Task 3.
