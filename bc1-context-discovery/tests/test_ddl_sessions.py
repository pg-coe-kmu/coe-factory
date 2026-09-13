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
