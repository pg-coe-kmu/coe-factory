"""sessions.sql — zweite Einspiel-Einheit (B1): Dreifallregel, Rechte, Kaskade, Wertebereich.

Alles hier laeuft gegen das Geruest MIT aktivem bc_leser-Automatismus
(ALTER DEFAULT PRIVILEGES in bc0_geruest.sql) — nur ein ausdrueckliches REVOKE
haelt bc_leser von der Tabelle fern (Positivkontrolle: test_db_fixture.py).
"""
import re
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.db_fixture import (DSN, MANDANT_A, MANDANT_B, frische_db, spiele_ddl_ein,
                              spiele_sessions_ein, verbindung)

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

_DB = Path(__file__).parents[1] / "bc1_service" / "db"
ALLE_RECHTE = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _tabellen(conn) -> set[str]:
    return {z[0] for z in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'bc1'").fetchall()}


_WIE_SPALTE = object()


def _session_anlegen(conn, session_id="s1", mandant=MANDANT_A, version=1,
                     state_mandant=_WIE_SPALTE) -> None:
    # Der Zustand traegt den Mandanten auch im JSON (so schreibt ihn der Store);
    # state_mandant erlaubt, JSON und Spalte gezielt auseinanderlaufen zu lassen
    # (None => JSON-null).
    im_json = mandant if state_mandant is _WIE_SPALTE else state_mandant
    conn.execute(
        "INSERT INTO bc1.sessions (session_id, company_id, version, state) "
        "VALUES (%s, %s, %s, %s)",
        (session_id, mandant, version, Jsonb({"company_id": im_json})))


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


def test_set_mitgliedschaft_in_bc1_role_wird_von_sessions_sql_selbst_erkannt():
    # Review 13.09., Befund 3: sessions.sql verliess sich fuer Mitgliedschafts-Kanten
    # auf den vorgeschalteten prozessprofil.sql-Lauf. Eine SET-Mitgliedschaft ohne
    # INHERIT ist fuer has_table_privilege unsichtbar, gibt per SET ROLE aber vollen
    # Zugriff auf bc1.sessions — die Datei muss das selbst sehen.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("DROP ROLE IF EXISTS angreifer")
        conn.execute("CREATE ROLE angreifer NOLOGIN")
        conn.execute("GRANT bc1_role TO angreifer WITH INHERIT FALSE, SET TRUE")
        conn.commit()
    try:
        with verbindung(DSN, None) as conn:      # Vorbedingung: unsichtbar fuer die Effektiv-Sicht
            assert not conn.execute(
                "SELECT has_table_privilege('angreifer', 'bc1.sessions', 'SELECT')"
            ).fetchone()[0], "Vorbedingung: kein vererbtes Recht"
        with pytest.raises(Exception) as fehler:
            spiele_sessions_ein(DSN)
        assert "Sollsignatur" in str(fehler.value) and "angreifer" in str(fehler.value)
    finally:
        with verbindung(DSN, None) as conn:
            conn.execute("REVOKE bc1_role FROM angreifer")
            conn.execute("DROP ROLE IF EXISTS angreifer")
            conn.commit()


def test_deaktivierter_kaskaden_trigger_auf_companies_wird_erkannt():
    # Review 13.09., Befund 7: die Loeschkaskade companies -> sessions haengt am
    # RI-Trigger RI_FKey_cascade_del, der auf COMPANIES sitzt, nicht auf sessions.
    # Wird er deaktiviert, bleibt die Constraint-Definition unveraendert, die DSGVO-
    # Loeschung liefe aber ins Leere. Die Signatur muss beide FK-Seiten kennen.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        name = conn.execute(
            "SELECT t.tgname FROM pg_trigger t "
            "  JOIN pg_constraint c ON c.oid = t.tgconstraint "
            "  JOIN pg_proc p ON p.oid = t.tgfoid "
            " WHERE c.conname = 'sessions_company_fk' AND p.proname = 'RI_FKey_cascade_del'"
        ).fetchone()[0]
        conn.execute(f'ALTER TABLE companies DISABLE TRIGGER "{name}"')
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_sessions_ein(DSN)
    assert "Sollsignatur" in str(fehler.value) and "RI_FKey_cascade_del" in str(fehler.value)


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


@pytest.mark.parametrize("state_mandant", [MANDANT_B, None])
def test_json_mandant_muss_zur_spalte_passen(state_mandant):
    # Review 13.09., Befund 5: der Store schreibt den Mandanten in die Spalte UND ins
    # JSON; die Loeschkaskade folgt der Spalte, der Kern liest das JSON. Beides muss
    # dasselbe sagen — auch bei UPDATEs, die nur das JSON tauschen. Ein JSON ohne
    # Mandant (None => 'company_id': null) ist ebenso ungueltig.
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(psycopg.errors.IntegrityError):
            _session_anlegen(conn, mandant=MANDANT_A, state_mandant=state_mandant)


def _umgebungsrollen(datei: str) -> set[str]:
    ddl = (_DB / datei).read_text(encoding="utf-8")
    block = ddl.split("umgebungsrollen (rolname) VALUES", 1)[1].split(";", 1)[0]
    return set(re.findall(r"\('([^']+)'\)", block))


def test_ausnahmeliste_ist_identisch_mit_prozessprofil_sql():
    # Die drei Namen sind in der Ziel-Supabase gemessen (EINSPIELEN.md, Abschnitt 5).
    # Beide Dateien tragen die Liste — driften sie, bricht eine von beiden live ab.
    assert _umgebungsrollen("sessions.sql") == _umgebungsrollen("prozessprofil.sql") \
        == {"postgres", "supabase_read_only_user", "supabase_etl_admin"}
