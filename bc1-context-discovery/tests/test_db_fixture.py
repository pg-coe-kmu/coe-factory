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
