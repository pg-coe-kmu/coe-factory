"""Spalte step_frequency_per_year (Frage D3) in bc1.prozessprofil — #255.

BC2 hat D3 am 20.09.2026 gebunden (Vertrag 1.2, Invariante I8); lesen.sql fragt die
Spalte ab. Bis dahin lag der Wert nur im Profil-JSON. Zwei Einspiel-Wege:
frische DB (prozessprofil.sql legt mit Spalte an) und Bestand (prozessprofil_d3.sql
migriert, danach ist prozessprofil.sql wieder Fall 2).
"""
import pytest

from tests.db_fixture import DSN, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")


def _spalte(conn, name: str) -> tuple[str, str] | None:
    """(Datentyp, Nullability) der Spalte oder None, wenn es sie nicht gibt."""
    return conn.execute(
        "SELECT data_type, is_nullable FROM information_schema.columns "
        " WHERE table_schema = 'bc1' AND table_name = 'prozessprofil' "
        "   AND column_name = %s", (name,)).fetchone()


def test_frische_db_hat_die_spalte_numeric_und_nullable():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        assert _spalte(conn, "step_frequency_per_year") == ("numeric", "YES")
