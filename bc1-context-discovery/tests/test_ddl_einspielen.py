import re
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


def test_bekannte_umgebungsrolle_bricht_das_einspielen_nicht_ab():
    # K-G (Entscheidung Richard, 03.09.): In der Zielumgebung kommen drei fremde
    # Rollen an unsere Tabellen — am 03.09. in der Supabase gemessen: postgres
    # (Mitglied von bc1_role und bc_leser), supabase_read_only_user und
    # supabase_etl_admin (beide ueber pg_read_all_data). Sie sind namentlich
    # ausgenommen, sonst braeche das Einspielen an der Umgebung ab. Dass JEDE
    # andere fremde Rolle weiter auffaellt, pinnt der Test darueber.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("DROP ROLE IF EXISTS supabase_read_only_user")
        conn.execute("CREATE ROLE supabase_read_only_user NOLOGIN")
        conn.execute("GRANT bc1_role TO supabase_read_only_user")
        conn.commit()
    try:
        spiele_ddl_ein(DSN)                      # darf NICHT abbrechen
        with verbindung(DSN, None) as conn:
            assert _tabellen(conn), "Fall 1 haette die Tabellen anlegen muessen"
    finally:
        with verbindung(DSN, None) as conn:
            conn.execute("REVOKE bc1_role FROM supabase_read_only_user")
            conn.execute("DROP ROLE IF EXISTS supabase_read_only_user")
            conn.commit()


def test_set_mitgliedschaft_in_ausgenommener_rolle_wird_erkannt():
    # CRITICAL aus dem Review 03.09., von beiden Reviewern unabhaengig gefunden:
    # Eine Fremdrolle braucht nur SET-Mitgliedschaft (ohne INHERIT) in einer
    # ausgenommenen Umgebungsrolle. has_table_privilege loest nur VERERBBARE
    # Mitgliedschaften auf, sieht sie also nicht — und die mitglied|-Zeile, die
    # den Zwischenschritt gemeldet haette, war fuer genau diese Namen gefiltert.
    # Gemessen: der Angreifer konnte sich anmelden, per 'SET ROLE ...; SET ROLE
    # bc1_role;' lesen UND schreiben, und das Einspielen lief durch.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("DROP ROLE IF EXISTS angreifer")
        conn.execute("DROP ROLE IF EXISTS supabase_read_only_user")
        conn.execute("CREATE ROLE supabase_read_only_user NOLOGIN")
        conn.execute("CREATE ROLE angreifer NOLOGIN")
        conn.execute("GRANT supabase_read_only_user TO angreifer "
                     "WITH INHERIT FALSE, SET TRUE")
        conn.commit()
    try:
        with verbindung(DSN, None) as conn:      # Vorbedingung: unsichtbar fuer die Effektiv-Sicht
            assert not conn.execute(
                "SELECT pg_has_role('angreifer', 'supabase_read_only_user', 'USAGE')"
            ).fetchone()[0], "Vorbedingung: kein vererbtes Recht"
            assert conn.execute(
                "SELECT pg_has_role('angreifer', 'supabase_read_only_user', 'MEMBER')"
            ).fetchone()[0], "Vorbedingung: SET ROLE waere moeglich"
        with pytest.raises(Exception) as fehler:
            spiele_ddl_ein(DSN)
        assert "Sollsignatur" in str(fehler.value)
        assert "angreifer" in str(fehler.value)
    finally:
        with verbindung(DSN, None) as conn:
            conn.execute("REVOKE supabase_read_only_user FROM angreifer")
            conn.execute("DROP ROLE IF EXISTS angreifer")
            conn.execute("DROP ROLE IF EXISTS supabase_read_only_user")
            conn.commit()


def test_ausnahmeliste_enthaelt_genau_die_drei_gemessenen_rollen():
    # I2 aus dem Review: Der INHALT der Ausnahmeliste war durch keinen Test
    # geschuetzt. Gemessen blieben drei Fehlimplementierungen gruen — die Liste
    # per LIKE 'supabase%' aufweichen, sie um fuenf beliebige Namen erweitern,
    # oder die Ausnahme zusaetzlich auf acl| anwenden. Die drei Namen sind am
    # 03.09. in der Ziel-Supabase gemessen (EINSPIELEN.md, Abschnitt 5); wer sie
    # aendert, misst dort neu nach und begruendet den Eintrag in der DDL.
    ddl = (Path(__file__).parents[1] / "bc1_service" / "db" / "prozessprofil.sql"
           ).read_text(encoding="utf-8")
    block = ddl.split("INSERT INTO pg_temp.bc1_umgebungsrollen (rolname) VALUES", 1)[1]
    block = block.split(";", 1)[0]
    namen = set(re.findall(r"\('([^']+)'\)", block))
    assert namen == {"postgres", "supabase_read_only_user", "supabase_etl_admin"}


def test_aehnlich_benannte_fremdrolle_ist_nicht_ausgenommen():
    # I2, zweiter Teil: Der Inhalts-Test oben pinnt die Liste, aber nicht, dass
    # sie auch BENUTZT wird. Gemessen: die Mutation "NOT LIKE 'supabase%'" statt
    # der Namensliste blieb gruen. Eine neue Supabase-Rolle waere damit still
    # ausgenommen. Dieser Test unterscheidet beides.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("DROP ROLE IF EXISTS supabase_neuer_dienst")
        conn.execute("CREATE ROLE supabase_neuer_dienst NOLOGIN")
        conn.execute("GRANT bc1_role TO supabase_neuer_dienst")
        conn.commit()
    try:
        with pytest.raises(Exception) as fehler:
            spiele_ddl_ein(DSN)
        assert "supabase_neuer_dienst" in str(fehler.value)
    finally:
        with verbindung(DSN, None) as conn:
            conn.execute("REVOKE bc1_role FROM supabase_neuer_dienst")
            conn.execute("DROP ROLE IF EXISTS supabase_neuer_dienst")
            conn.commit()


def test_direktes_grant_an_eine_ausgenommene_rolle_bricht_trotzdem_ab():
    # I2: Die Ausnahme darf NUR fuer Mitgliedschaften und effektive Rechte
    # gelten, niemals fuer die ACL selbst — sonst waere ein direktes GRANT an
    # postgres & Co. unsichtbar. Heute korrekt, aber bisher ungeschuetzt: die
    # Mutation "Ausnahme zusaetzlich auf acl| anwenden" blieb im Review gruen.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("DROP ROLE IF EXISTS supabase_etl_admin")
        conn.execute("CREATE ROLE supabase_etl_admin NOLOGIN")
        conn.commit()
    try:
        with verbindung(DSN) as conn:
            conn.execute("GRANT SELECT ON bc1.prozessprofil TO supabase_etl_admin")
            conn.commit()
        with pytest.raises(Exception) as fehler:
            spiele_ddl_ein(DSN)
        assert "acl|prozessprofil|supabase_etl_admin|SELECT" in str(fehler.value)
    finally:
        with verbindung(DSN, None) as conn:
            # Das GRANT haengt an der Rolle und ueberlebt den Rollback des
            # Einspielversuchs — ohne DROP OWNED BY scheitert das DROP ROLE.
            conn.execute("DROP OWNED BY supabase_etl_admin")
            conn.execute("DROP ROLE IF EXISTS supabase_etl_admin")
            conn.commit()


def test_mitgliedschaft_in_pg_maintain_wird_erkannt():
    # I3 aus dem Review 03.09.: PostgreSQL 17 bringt die Systemrolle pg_maintain.
    # Ein GRANT darauf gibt MAINTAIN auf unseren Tabellen (VACUUM, REINDEX,
    # CLUSTER, LOCK), ohne dass sich eine ACL aendert. Die frueher notierte
    # Begruendung "MAINTAIN entsteht nur durch ein direktes GRANT" war damit
    # falsch — belegt durch Messung: has_table_privilege(...,'MAINTAIN') = True,
    # SELECT und UPDATE = False. Kein Datenzugriff, aber ein Recht auf unseren
    # Tabellen, das die Pruefung sehen muss.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("DROP ROLE IF EXISTS wartungs_rolle")
        conn.execute("CREATE ROLE wartungs_rolle NOLOGIN")
        conn.execute("GRANT pg_maintain TO wartungs_rolle")
        conn.commit()
    try:
        with verbindung(DSN, None) as conn:
            assert conn.execute(
                "SELECT has_table_privilege('wartungs_rolle', 'bc1.prozessprofil', "
                "'MAINTAIN')").fetchone()[0], "Vorbedingung: das Recht wirkt wirklich"
        with pytest.raises(Exception) as fehler:
            spiele_ddl_ein(DSN)
        assert "Sollsignatur" in str(fehler.value)
        assert "wartungs_rolle" in str(fehler.value)
    finally:
        with verbindung(DSN, None) as conn:
            conn.execute("REVOKE pg_maintain FROM wartungs_rolle")
            conn.execute("DROP ROLE IF EXISTS wartungs_rolle")
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


def test_bc_leser_liest_die_vertragstabellen_aber_nie_den_write_status():
    # BC0-Antwort 3 (02.09.): Leser von bc1.prozessprofil ist die GRUPPENROLLE
    # bc_leser — BC2, BC3, BC4 lesen ueber ihre Mitgliedschaft, ein spaeterer Entzug
    # wirkt an einer Stelle. profil_rollen gleichgestellt (Rueckfrage an BC0 offen,
    # Rev. 11). profil_write_status bleibt allein bei bc1_role.
    # ACHTUNG bei einer VIERTEN Tabelle: die Namen stehen hier bewusst als Literale
    # (die Rollen sind je Tabelle verschieden, VERTRAGSTABELLEN traegt das nicht mehr).
    # Eine neue Tabelle muss hier UND im REVOKE in prozessprofil.sql nachgetragen
    # werden — sonst oeffnet BC0s ALTER DEFAULT PRIVILEGES sie still fuer bc_leser.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        for rolle in ("bc_leser", "bc2_role", "bc3_role", "bc4_role"):
            for tabelle in ("prozessprofil", "profil_rollen"):
                assert conn.execute(
                    "SELECT has_table_privilege(%s, %s, 'SELECT')",
                    (rolle, f"bc1.{tabelle}")).fetchone()[0], f"{rolle} liest {tabelle} nicht"
                for recht in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                    assert not conn.execute(
                        "SELECT has_table_privilege(%s, %s, %s)",
                        (rolle, f"bc1.{tabelle}", recht)).fetchone()[0], f"{rolle}/{tabelle}/{recht}"
            # ALLE sieben Rechte, nicht nur die vier des Plans: mit der Vierer-Liste
            # blieb der Test bei TRUNCATE/REFERENCES/TRIGGER auf write_status gruen
            # (Review 02.09., am Container mutiert).
            for recht in ("SELECT", "INSERT", "UPDATE", "DELETE",
                          "TRUNCATE", "REFERENCES", "TRIGGER"):
                assert not conn.execute(
                    "SELECT has_table_privilege(%s, 'bc1.profil_write_status', %s)",
                    (rolle, recht)).fetchone()[0], f"{rolle} sieht profil_write_status/{recht}"


def test_bc_leser_kann_die_vertragstabellen_wirklich_lesen():
    # has_table_privilege ignoriert das Schema-USAGE. Ohne "GRANT USAGE ON SCHEMA bc1
    # TO bc_leser" bliebe der Rechte-Test oben gruen, waehrend BC2 real
    # "permission denied for schema bc1" bekaeme (Review 02.09., am Container
    # mutiert nachgewiesen). Deshalb hier der echte Vollzug statt der Behauptung.
    frische_db(DSN)
    with verbindung(DSN, "bc_leser") as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_keine_spaltenrechte_im_schema_bc1():
    # Spaltenrechte leben in pg_attribute.attacl, NICHT in relacl — genau daran
    # scheiterte in Task 4 schon einmal ein Rechte-Test (Codex-Runde 10: ein
    # GRANT SELECT (profil) TO bc2_role blieb unsichtbar). has_table_privilege
    # sieht sie ebenfalls nicht. Deshalb hier direkt am Katalog.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        treffer = conn.execute(
            "SELECT c.relname, a.attname, a.attacl::text "
            "  FROM pg_attribute a "
            "  JOIN pg_class c ON c.oid = a.attrelid "
            "  JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'bc1' AND a.attacl IS NOT NULL").fetchall()
    assert treffer == [], f"Spaltenrechte im Schema bc1: {treffer}"
