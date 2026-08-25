from pathlib import Path

import pytest

from tests.db_fixture import DSN, MANDANT_A, frische_db, spiele_ddl_ein, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

VERTRAGSTABELLEN = ("prozessprofil", "profil_rollen", "profil_write_status")


def _tabellen(conn) -> set[str]:
    return {z[0] for z in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'bc1'").fetchall()}


def _draft_anlegen(conn) -> None:
    conn.execute(
        "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, profil_version, "
        "process_id, status, erhebung_id, paket_version, profil) "
        "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-01', "
        "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))


def test_fall_1_leere_db_legt_alle_vertragsobjekte_an():
    frische_db(DSN)                                   # spielt die DDL bereits ein
    with verbindung(DSN, None) as conn:
        assert set(VERTRAGSTABELLEN) <= _tabellen(conn)


def test_fall_2_zweiter_lauf_ist_ein_no_op_und_laesst_daten_stehen():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        _draft_anlegen(conn)
        conn.commit()
    spiele_ddl_ein(DSN)                               # zweiter Lauf, identischer Bestand
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 1


def test_fall_3_teilbestand_bricht_ab_ohne_etwas_zu_aendern():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("DROP TABLE bc1.profil_write_status")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Teilbestand" in str(fehler.value)
    with verbindung(DSN, None) as conn:
        assert "profil_write_status" not in _tabellen(conn)   # NICHTS angelegt


def test_fall_3_abweichende_spalte_bricht_ab_ohne_etwas_zu_aendern():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("ALTER TABLE bc1.prozessprofil ADD COLUMN fremd integer")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Sollsignatur" in str(fehler.value)
    assert "fremd" in str(fehler.value)                       # Diff nennt den Grund
    with verbindung(DSN, None) as conn:
        spalten = {z[0] for z in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'bc1' AND table_name = 'prozessprofil'").fetchall()}
    assert "fremd" in spalten                                 # unveraendert stehen geblieben


def _katalog_stempel():
    """Fingerabdruck der Katalogzeilen, die unsere Anlage schreibt.

    Bewusst praezise formuliert (Codex N10-I7): das ist NICHT "jeder denkbare
    Rewrite". Erfasst sind pg_class, pg_proc, pg_trigger, pg_description und die
    Tabellen-ACL — nicht pg_attribute, nicht pg_policy, nicht Rollenmitglied-
    schaften und nicht pg_temp. Fuer den No-op-Nachweis reicht das: die Statements
    in Abschnitt 2/3 schreiben genau in diese Kataloge. Die weitergehende Drift
    faengt die Sollsignatur ab, nicht dieser Stempel.
    """
    with verbindung(DSN, None) as conn:
        return conn.execute(
            "SELECT (SELECT array_agg(p.xmin::text ORDER BY p.proname) "
            "          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "         WHERE n.nspname = 'bc1'), "
            "       (SELECT array_agg(t.xmin::text ORDER BY t.tgname) "
            "          FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "          JOIN pg_namespace n ON n.oid = c.relnamespace "
            "         WHERE n.nspname = 'bc1' AND NOT t.tgisinternal), "
            "       (SELECT array_agg(c.relacl::text ORDER BY c.relname) "
            "          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "         WHERE n.nspname = 'bc1' AND c.relkind = 'r'), "
            "       (SELECT array_agg(c.xmin::text ORDER BY c.relname) "
            "          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "         WHERE n.nspname = 'bc1'), "
            "       (SELECT array_agg(d.xmin::text ORDER BY d.objoid, d.objsubid) "
            "          FROM pg_description d JOIN pg_class c ON c.oid = d.objoid "
            "          JOIN pg_namespace n ON n.oid = c.relnamespace "
            "         WHERE n.nspname = 'bc1')").fetchone()


def test_fall_2_ruehrt_den_katalog_nicht_an():
    # Der eigentliche No-op-Nachweis (Codex R1-C1, erweitert R2-N-I1): CREATE OR
    # REPLACE, GRANT/REVOKE und COMMENT wuerden Katalogzeilen neu schreiben —
    # xmin von pg_class/pg_proc/pg_trigger/pg_description verriete es. Der
    # Nachweis ergaenzt den Kontrollfluss, er ersetzt ihn nicht.
    frische_db(DSN)
    vorher = _katalog_stempel()
    spiele_ddl_ein(DSN)
    assert _katalog_stempel() == vorher


def test_fall_3_nur_triggerfunktionen_ohne_tabellen_bricht_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("DROP TABLE bc1.profil_write_status, bc1.profil_rollen, "
                     "bc1.prozessprofil CASCADE")     # Funktionen bleiben stehen
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Teilbestand" in str(fehler.value)
    with verbindung(DSN, None) as conn:
        assert not set(VERTRAGSTABELLEN) & _tabellen(conn)     # nichts angelegt


@pytest.mark.parametrize("eingriff, spur", [
    ("ALTER TABLE bc1.prozessprofil DROP CONSTRAINT prozessprofil_confidence_bereich",
     "prozessprofil_confidence_bereich"),
    ("DROP INDEX bc1.prozessprofil_hoechstens_ein_draft",
     "prozessprofil_hoechstens_ein_draft"),
    ("CREATE OR REPLACE FUNCTION bc1.tf_freeze_profil() RETURNS trigger "
     "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$",
     "funktion|tf_freeze_profil"),
    ("GRANT SELECT ON bc1.profil_write_status TO bc2_role",
     "bc2_role"),
    ("REVOKE EXECUTE ON FUNCTION bc1.tf_freeze_profil() FROM PUBLIC",
     "funktion_acl|tf_freeze_profil"),
])
def test_fall_3_erkennt_jede_semantische_abweichung(eingriff, spur):
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute(eingriff)
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Sollsignatur" in str(fehler.value)
    assert spur in str(fehler.value)


def test_einspielen_als_falscher_eigentuemer_wird_abgewiesen():
    # Betriebsrisiko, beim Bauen gemessen (25.08.): Abschnitt 0 prueft nur, OB die
    # einspielende Rolle im Schema bc1 anlegen darf — ein Superuser darf das auch.
    # Ohne SET ROLE wuerden die Tabellen postgres gehoeren; die Sollsignatur haelt
    # aber Eigentuemer UND ACL fest, die Nachpruefung schlaegt also an und rollt
    # alles zurueck. Dieser Test haelt genau das fest.
    import psycopg
    frische_db(DSN, mit_ddl=False)
    ddl = (Path(__file__).parents[1] / "bc1_service" / "db" / "prozessprofil.sql"
           ).read_text(encoding="utf-8")
    with pytest.raises(Exception) as fehler:
        with psycopg.connect(DSN) as conn:          # bewusst OHNE SET ROLE
            conn.execute(ddl)
            conn.commit()
    assert "Nachpruefung fehlgeschlagen" in str(fehler.value)
    assert "postgres" in str(fehler.value)
    with verbindung(DSN, None) as conn:
        assert not _tabellen(conn)                  # vollstaendiger Rollback


def test_spaltenrecht_an_fremde_rolle_wird_erkannt():
    # Codex N10-C1: Spaltenrechte liegen in pg_attribute.attacl, nicht in
    # pg_class.relacl. Ein GRANT auf EINE Spalte umging Signatur UND Rechte-Test.
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute("GRANT SELECT (profil) ON bc1.prozessprofil TO bc2_role")
        conn.commit()
    with verbindung(DSN, None) as conn:
        assert conn.execute(
            "SELECT has_column_privilege('bc2_role', 'bc1.prozessprofil', "
            "'profil', 'SELECT')").fetchone()[0], "Vorbedingung: das Recht wirkt"
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Sollsignatur" in str(fehler.value)
    assert "bc2_role" in str(fehler.value)


def test_mitgliedschaft_in_bc1_role_wird_erkannt():
    # Codex N10-C2: GRANT bc1_role TO <beliebige Rolle> gibt volle Rechte, ohne
    # dass sich eine Tabellen-ACL aendert. Eine feste Rollenliste sieht das nicht.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("DROP ROLE IF EXISTS fremde_rolle")
        conn.execute("CREATE ROLE fremde_rolle NOLOGIN")
        conn.execute("GRANT bc1_role TO fremde_rolle")
        conn.commit()
    try:
        with pytest.raises(Exception) as fehler:
            spiele_ddl_ein(DSN)
        assert "Sollsignatur" in str(fehler.value)
        assert "fremde_rolle" in str(fehler.value)
    finally:
        with verbindung(DSN, None) as conn:
            conn.execute("DROP ROLE IF EXISTS fremde_rolle")
            conn.commit()


def test_deaktivierter_interner_fk_trigger_wird_erkannt():
    # Codex N10-I3: tgisinternal wird ausgeschlossen — ein deaktivierter RI-Trigger
    # laesst die Constraint-Definition unveraendert, der FK wird aber nicht mehr
    # erzwungen. profil_write_status hat NUR interne Trigger, isoliert den Fall also.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("ALTER TABLE bc1.profil_write_status DISABLE TRIGGER ALL")
        conn.commit()
    with pytest.raises(Exception) as fehler:
        spiele_ddl_ein(DSN)
    assert "Sollsignatur" in str(fehler.value)


def test_zweiter_lauf_in_derselben_session_ist_ein_no_op():
    # Codex N10-I4: die TEMP VIEW kennt kein ON COMMIT DROP und ueberlebt den
    # Commit. Ein zweiter Lauf in DERSELBEN Session lief deshalb auf
    # "relation bc1_ist_signatur already exists". Die Fixture verdeckte das,
    # weil sie je Lauf eine neue Verbindung oeffnet.
    import psycopg
    frische_db(DSN, mit_ddl=False)
    ddl = (Path(__file__).parents[1] / "bc1_service" / "db" / "prozessprofil.sql"
           ).read_text(encoding="utf-8")
    with psycopg.connect(DSN) as conn:
        conn.execute("SET ROLE bc1_role")
        conn.execute(ddl)
        conn.commit()
        conn.execute(ddl)          # zweiter Lauf, SELBE Session
        conn.commit()
    with verbindung(DSN, None) as conn:
        assert set(VERTRAGSTABELLEN) <= _tabellen(conn)


def test_bc1_role_darf_alles_auf_den_drei_tabellen():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        for tabelle in VERTRAGSTABELLEN:
            for recht in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert conn.execute(
                    "SELECT has_table_privilege('bc1_role', %s, %s)",
                    (f"bc1.{tabelle}", recht)).fetchone()[0], f"{tabelle}/{recht}"


def test_fremde_bc_rollen_lesen_nichts_auch_nicht_ueber_bc_leser():
    # R14-I1: BC0s DEFAULT PRIVILEGES haetten bc_leser SELECT gegeben; die
    # Positivkontrolle in test_db_fixture.py beweist, dass der Automatismus wirkt.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        for rolle in ("bc_leser", "bc2_role", "bc3_role", "bc4_role"):
            for tabelle in VERTRAGSTABELLEN:
                assert not conn.execute(
                    "SELECT has_table_privilege(%s, %s, 'SELECT')",
                    (rolle, f"bc1.{tabelle}")).fetchone()[0], f"{rolle} sieht {tabelle}"
