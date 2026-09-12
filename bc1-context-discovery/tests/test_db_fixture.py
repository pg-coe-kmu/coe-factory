import pytest

from bc1_service import bc0_lesepfade
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
    # Geruest bildet genau das ab. Das ALTER DEFAULT PRIVILEGES fuer bc1 hat BC0 am
    # 08.09.2026 live entfernt (K-I); das Geruest simuliert es weiter — bewusst, als
    # Positivkontrolle dafuer, dass unsere DDL auch unter feindlichem Default dicht ist.
    # mandant_rollen: SELECT fuer bc_leser live gemessen 12.09.2026 (A5) — braucht C1a.
    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, None) as conn:
        assert conn.execute(
            "SELECT pg_has_role('bc1_role', 'bc_leser', 'USAGE')").fetchone()[0] is True
        for objekt in ("v_bewertung_aktuell", "mandant_systeme", "ref_teilprozesse",
                       "companies", "v_prozesse_lesen", "ref_erhebungen", "mandant_rollen"):
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


def test_nacherhebungs_ids_wie_bc0_v28_akzeptiert_und_richtig_gereiht():
    # BC0 Schema v2.8 (Nacherhebung): erhebung_id darf ein Suffix tragen —
    # '^E-[0-9]{4}-[0-9]{2}(-[2-9]|-[1-9][0-9]+)?$', live gemessen 12.09.2026 (A5).
    # Das Geruest kannte nur 'E-JJJJ-MM' und war damit strenger als die Realitaet.
    # Zweiter Teil: bei gleichem Stand entscheidet erhebung_id DESC (wie in
    # v_bewertung_aktuell) — 'E-2026-08-2' liegt als Text hinter 'E-2026-08', die
    # Nacherhebung gewinnt also. (Text-Reihenfolge, nicht numerisch: '-10' laege vor
    # '-2'; das ist BC0s Reihung, und wir folgen ihr bewusst.)
    frische_db(DSN, mit_ddl=False)
    with verbindung(DSN, None) as conn:
        conn.execute(
            "INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, stand, status) "
            "VALUES (%s, 'E-2026-08', 'Erhebung', '2026-08-01', 'abgeschlossen'), "
            "       (%s, 'E-2026-08-2', 'Nacherhebung', '2026-08-01', 'offen'), "
            "       (%s, 'E-2026-08-10', 'zehnte Nacherhebung', '2026-08-01', 'offen')",
            (MANDANT_A, MANDANT_A, MANDANT_A))
        conn.execute(
            "INSERT INTO bitkom_bewertungen (company_id, erhebung_id, id, sub_process_id, "
            "item_nr, stufe, beleg, bewertet_am) VALUES "
            "(%s, 'E-2026-08', 'KP-01.TP-3.I-01', 'KP-01.TP-3', 1, 2, 'Erhebung', '2026-08-01'), "
            "(%s, 'E-2026-08-2', 'KP-01.TP-3.I-02', 'KP-01.TP-3', 2, 2, 'Nacherhebung', "
            " '2026-08-01')", (MANDANT_A, MANDANT_A))
        conn.commit()
    for kaputt in ("E-2026-08-1", "E-2026-08-0", "E-2026-08-x"):
        with verbindung(DSN, None) as conn:
            with pytest.raises(Exception) as fehler:
                conn.execute(
                    "INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, "
                    "stand, status) VALUES (%s, %s, 'kaputt', '2026-08-01', 'offen')",
                    (MANDANT_A, kaputt))
            assert "erhebung_id" in str(fehler.value), kaputt
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-01.TP-3") == "E-2026-08-2"
