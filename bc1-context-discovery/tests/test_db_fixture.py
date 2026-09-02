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


def test_bc1_role_liest_bc0_objekte_nur_ueber_bc_leser():
    # Zweite Chat-Nachricht 02.09.: bc1_role liest ueber die Gruppenrolle bc_leser, die
    # direkten Doppel-GRANTs sind weg (in der Supabase am 02.09. nachgesehen). Das
    # Geruest bildet genau das ab. Das ALTER DEFAULT PRIVILEGES bleibt — es existiert
    # in der Supabase, anders als BC0s Antwort 9 behauptet (pg_default_acl, 02.09.).
    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, None) as conn:
        assert conn.execute(
            "SELECT pg_has_role('bc1_role', 'bc_leser', 'USAGE')").fetchone()[0] is True
        for objekt in ("v_bewertung_aktuell", "mandant_systeme", "ref_teilprozesse",
                       "companies", "v_prozesse_lesen", "ref_erhebungen"):
            # Kein DIREKTES SELECT an bc1_role mehr. Achtung: companies,
            # ref_teilprozesse und ref_erhebungen behalten ihr direktes REFERENCES
            # (bc1_role=x in der ACL) — deshalb aclexplode nach Privileg, nicht
            # ein Substring-Test auf 'bc1_role=' (am Container 02.09. so gesehen).
            direkt = conn.execute(
                "SELECT count(*) FROM pg_class c, aclexplode(c.relacl) a "
                " WHERE c.oid = %s::regclass AND a.grantee = 'bc1_role'::regrole "
                "   AND a.privilege_type = 'SELECT'", (objekt,)).fetchone()[0]
            assert direkt == 0, f"{objekt}: direkter SELECT-GRANT an bc1_role"
            assert conn.execute(
                "SELECT has_table_privilege('bc1_role', %s, 'SELECT')",
                (objekt,)).fetchone()[0] is True, f"{objekt}: nicht ueber bc_leser lesbar"
            # Ohne diese Zeile traegt der Testname nicht: bc1_role koennte auch ueber
            # PUBLIC lesen und der Test bliebe gruen (Review 02.09., Mutation MUT-C).
            assert conn.execute(
                "SELECT has_table_privilege('bc_leser', %s, 'SELECT')",
                (objekt,)).fetchone()[0] is True, f"{objekt}: Lesepfad ist nicht bc_leser"


def test_step_no_reicht_bis_neun_und_nicht_weiter():
    # BC0 Schema v2.2 (27.08.): CHECK (step_no BETWEEN 1 AND 9). Das ID-Muster liesse
    # TP-10 zu — die Grenze zieht der CHECK, nicht die Regex.
    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, None) as conn:
        conn.execute(
            "INSERT INTO ref_teilprozesse (company_id, sub_process_id, process_id, "
            "step_no, sub_process_name) VALUES (%s, 'KP-01.TP-9', 'KP-01', 9, 'neun')",
            (MANDANT_A,))
        conn.commit()
    with verbindung(DSN, None) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute(
                "INSERT INTO ref_teilprozesse (company_id, sub_process_id, process_id, "
                "step_no, sub_process_name) VALUES (%s, 'KP-01.TP-10', 'KP-01', 10, 'zehn')",
                (MANDANT_A,))
        assert "step_no" in str(fehler.value)
