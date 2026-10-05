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
