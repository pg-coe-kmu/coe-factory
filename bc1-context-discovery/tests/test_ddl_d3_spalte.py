"""Spalte step_frequency_per_year (Frage D3) in bc1.prozessprofil — #255.

BC2 hat D3 am 20.09.2026 gebunden (Vertrag 1.2, Invariante I8); lesen.sql fragt die
Spalte ab. Bis dahin lag der Wert nur im Profil-JSON. Zwei Einspiel-Wege:
frische DB (prozessprofil.sql legt mit Spalte an) und Bestand (prozessprofil_d3.sql
migriert, danach ist prozessprofil.sql wieder Fall 2).
"""
import pytest
from psycopg.types.json import Jsonb

from tests.db_fixture import (DSN, MANDANT_A, frische_db, spiele_d3_ein, spiele_ddl_ein,
                              spiele_migration_und_ddl_ein, verbindung)

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

FINGERPRINT = "1.1+ctx-0000000000000000"

# Der Wertebereichs-CHECK, wie er VOR #255 in der Supabase liegt (prozessprofil.sql
# bis Commit 136003e) — damit stellt der Test den Bestand vor der Migration nach.
CHECK_ALT = (
    "CHECK ((frequency_per_year IS NULL OR (frequency_per_year >= 0 "
    "AND frequency_per_year < 'Infinity'::numeric)) "
    "AND (executions_per_run IS NULL OR (executions_per_run >= 0 "
    "AND executions_per_run < 'Infinity'::numeric)) "
    "AND (total_duration_minutes IS NULL OR (total_duration_minutes >= 0 "
    "AND total_duration_minutes < 'Infinity'::numeric)) "
    "AND (focus_step_duration_minutes IS NULL OR (focus_step_duration_minutes >= 0 "
    "AND focus_step_duration_minutes < 'Infinity'::numeric)))")


def _altzustand_herstellen(dsn: str) -> None:
    """Frische DB, dann zurueck auf den Stand vor #255: ohne Spalte, mit altem CHECK.

    Als Superuser, weil es den Bestand nachstellt — nicht den Einspielweg."""
    frische_db(dsn)
    with verbindung(dsn, None) as conn:
        # DROP COLUMN nimmt den CHECK, der die Spalte nennt, automatisch mit.
        conn.execute("ALTER TABLE bc1.prozessprofil DROP COLUMN step_frequency_per_year")
        conn.execute("ALTER TABLE bc1.prozessprofil "
                     f"ADD CONSTRAINT prozessprofil_zahlen_wertebereich {CHECK_ALT}")
        conn.commit()


def _spalte(conn, name: str) -> tuple[str, str] | None:
    """(Datentyp, Nullability) der Spalte oder None, wenn es sie nicht gibt."""
    return conn.execute(
        "SELECT data_type, is_nullable FROM information_schema.columns "
        " WHERE table_schema = 'bc1' AND table_name = 'prozessprofil' "
        "   AND column_name = %s", (name,)).fetchone()


def _profil_einfuegen(conn, step_frequency) -> None:
    conn.execute(
        "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, profil_version, "
        "process_id, status, erhebung_id, paket_version, profil, step_frequency_per_year) "
        "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-01', %s, '{}', %s)",
        (MANDANT_A, FINGERPRINT, step_frequency))


def test_frische_db_hat_die_spalte_numeric_und_nullable():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        assert _spalte(conn, "step_frequency_per_year") == ("numeric", "YES")


def test_wertebereich_weist_nan_infinity_und_negativ_ab():
    frische_db(DSN)
    for wert in ("NaN", "Infinity", "-1"):
        with verbindung(DSN) as conn:
            with pytest.raises(Exception) as fehler:
                _profil_einfuegen(conn, wert)
            assert "prozessprofil_zahlen_wertebereich" in str(fehler.value)


def test_wertebereich_nimmt_null_und_nicht_negative_zahlen():
    frische_db(DSN)
    for wert in (None, "0", "12"):
        with verbindung(DSN) as conn:
            _profil_einfuegen(conn, wert)
            conn.rollback()


def test_migration_zieht_den_bestand_nach_und_prozessprofil_sql_ist_danach_fall_2():
    _altzustand_herstellen(DSN)
    spiele_d3_ein(DSN)                                # M1: Spalte + CHECK nachziehen
    with verbindung(DSN, None) as conn:
        assert _spalte(conn, "step_frequency_per_year") == ("numeric", "YES")
    spiele_ddl_ein(DSN)                               # neue Sollsignatur: Fall 2, kein Abbruch
    with verbindung(DSN) as conn:
        with pytest.raises(Exception) as fehler:      # und der neue CHECK greift
            _profil_einfuegen(conn, "-1")
        assert "prozessprofil_zahlen_wertebereich" in str(fehler.value)


def test_migration_ist_beim_zweiten_lauf_ein_no_op_und_laesst_daten_stehen():
    _altzustand_herstellen(DSN)
    spiele_d3_ein(DSN)                                # M1
    with verbindung(DSN) as conn:
        _profil_einfuegen(conn, "12")
        conn.commit()
    spiele_d3_ein(DSN)                                # M2: nichts zu tun, kein Abbruch
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT step_frequency_per_year FROM bc1.prozessprofil"
                            ).fetchone()[0] == 12


def test_migration_auf_leerer_db_ist_no_op_und_prozessprofil_sql_legt_danach_mit_spalte_an():
    frische_db(DSN, mit_ddl=False)                    # Geruest ohne bc1-Tabellen
    spiele_d3_ein(DSN)                                # M0: nichts da, nichts zu tun
    with verbindung(DSN, None) as conn:
        assert conn.execute("SELECT to_regclass('bc1.prozessprofil')").fetchone()[0] is None
    spiele_ddl_ein(DSN)                               # Fall 1
    with verbindung(DSN, None) as conn:
        assert _spalte(conn, "step_frequency_per_year") == ("numeric", "YES")


def _altzeile_einfuegen(conn, d3_status: str, d3_wert) -> None:
    """Profilzeile im ALTEN Schema (ohne Spalte), D3 nur im JSON — wie der Bestand."""
    conn.execute(
        "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, profil_version, "
        "process_id, status, erhebung_id, paket_version, profil, frequency_per_year) "
        "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-01', %s, %s, 11)",
        (MANDANT_A, FINGERPRINT,
         Jsonb({"felder": {"step_frequency_per_year":
                           {"status": d3_status, "wert": d3_wert}}})))


def test_migration_bricht_ab_wenn_der_bestand_gueltige_json_d3_werte_traegt():
    # Codex-Review 22.09. (Important 1): ADD COLUMN liesse die Spalte NULL, obwohl im
    # JSON ein gueltiger Wert steht — bei fertigen Zeilen dauerhaft (Freeze). Die
    # Uebernahme ist zu entscheiden, nicht stillschweigend zu ueberspringen.
    _altzustand_herstellen(DSN)
    with verbindung(DSN) as conn:
        _altzeile_einfuegen(conn, "gueltig", "66")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_d3_ein(DSN)
    assert "JSON" in str(fehler.value)
    with verbindung(DSN, None) as conn:                # nichts geaendert
        assert _spalte(conn, "step_frequency_per_year") is None


def test_migration_laesst_bestandszeilen_ohne_json_d3_unveraendert():
    # Wie der Live-Bestand: D3 im JSON als 'fehlt'. Migration laeuft, bisherige Werte
    # bleiben, die neue Spalte ist NULL (Codex-Review 22.09., Minor 4).
    _altzustand_herstellen(DSN)
    with verbindung(DSN) as conn:
        _altzeile_einfuegen(conn, "fehlt", None)
        conn.commit()
    spiele_d3_ein(DSN)                                # M1
    with verbindung(DSN) as conn:
        assert conn.execute(
            "SELECT frequency_per_year, step_frequency_per_year, "
            "       profil->'felder'->'step_frequency_per_year'->>'status' "
            "  FROM bc1.prozessprofil").fetchone() == (11, None, "fehlt")


def test_fall_3_von_prozessprofil_sql_rollt_die_migration_in_derselben_transaktion_zurueck():
    # Codex-Review 22.09. (Important 2): die volle Signaturpruefung kommt erst aus
    # prozessprofil.sql. Laufen beide Dateien in EINER Transaktion (Betrieb: psql -1 mit
    # zwei -f), nimmt ein Fall 3 die schon ausgefuehrte Migration wieder mit.
    _altzustand_herstellen(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("DROP TABLE bc1.profil_write_status")   # Teilbestand => Fall 3
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_migration_und_ddl_ein(DSN)
    assert "Fall 3" in str(fehler.value)
    with verbindung(DSN, None) as conn:
        assert _spalte(conn, "step_frequency_per_year") is None


def test_migration_bricht_bei_unerwartetem_bestand_ab_ohne_zu_aendern():
    # Spalte vorhanden, aber CHECK in alter Fassung: weder M1 noch M2 — nichts erraten.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("ALTER TABLE bc1.prozessprofil "
                     "DROP CONSTRAINT prozessprofil_zahlen_wertebereich")
        conn.execute("ALTER TABLE bc1.prozessprofil "
                     f"ADD CONSTRAINT prozessprofil_zahlen_wertebereich {CHECK_ALT}")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_d3_ein(DSN)
    assert "M3" in str(fehler.value)
    with verbindung(DSN) as conn:                     # alter CHECK steht unveraendert
        _profil_einfuegen(conn, "-1")
        conn.rollback()
