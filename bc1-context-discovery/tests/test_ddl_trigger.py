import threading

import pytest

from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

FINGERPRINT = "1.1+ctx-0000000000000000"


@pytest.fixture
def db():
    frische_db(DSN)
    return DSN


def _insert(conn, mandant=MANDANT_A, tp="KP-01.TP-1", status="in_erhebung",
            erhebung="E-2026-01", **spalten):
    namen = ["company_id", "focus_step_id", "profil_version", "process_id", "status",
             "erhebung_id", "paket_version", "profil", *spalten]
    werte = [mandant, tp, 1, tp[:5], status, erhebung, FINGERPRINT, "{}",
             *spalten.values()]
    platz = ", ".join(["%s"] * len(namen))
    return conn.execute(
        f"INSERT INTO bc1.prozessprofil ({', '.join(namen)}) VALUES ({platz}) "
        "RETURNING profil_version", werte).fetchone()[0]


def test_version_wird_von_der_db_vergeben_und_zaehlt_hoch(db):
    with verbindung(db) as conn:
        assert _insert(conn) == 1
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig' "
                     "WHERE focus_step_id = 'KP-01.TP-1'")
        assert _insert(conn) == 2          # uebergebene 1 wird ueberschrieben
        conn.commit()


def test_version_zaehlt_je_fokus_schritt_getrennt(db):
    with verbindung(db) as conn:
        assert _insert(conn, tp="KP-01.TP-1") == 1
        assert _insert(conn, tp="KP-01.TP-2") == 1
        conn.commit()


def test_nur_ein_draft_je_fokus_schritt(db):
    with verbindung(db) as conn:
        _insert(conn)
        with pytest.raises(Exception) as fehler:
            _insert(conn)
        assert "prozessprofil_hoechstens_ein_draft" in str(fehler.value)


def test_fertige_zeile_ist_gegen_update_gesperrt(db):
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("UPDATE bc1.prozessprofil SET profil = '{\"x\":1}'::jsonb")
        assert "eingefroren" in str(fehler.value)


def test_fertige_zeile_ist_gegen_delete_gesperrt_draft_nicht(db):
    with verbindung(db) as conn:
        _insert(conn, tp="KP-01.TP-1", status="fertig")
        _insert(conn, tp="KP-01.TP-2", status="in_erhebung")
        conn.commit()
    with verbindung(db) as conn:
        conn.execute("DELETE FROM bc1.prozessprofil WHERE focus_step_id = 'KP-01.TP-2'")
        conn.commit()                                   # Betriebsweg K5: erlaubt
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("DELETE FROM bc1.prozessprofil WHERE focus_step_id = 'KP-01.TP-1'")
        assert "eingefroren" in str(fehler.value)


def test_mandanten_kaskade_laeuft_durch_die_freeze_trigger(db):
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.commit()
    with verbindung(db, None) as conn:                  # BC0/Admin loescht den Mandanten
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 0


def test_rollen_zeilen_einer_fertigen_version_sind_gesperrt(db):
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, profil_version, "
            "pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')", (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute(
                "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
                "profil_version, pos, rolle_freitext) "
                "VALUES (%s, 'KP-01.TP-1', 1, 2, 'Praktikant')", (MANDANT_A,))
        assert "eingefroren" in str(fehler.value)


def test_rollen_freeze_serialisiert_gegen_parallelen_freeze(db):
    # R4-I7: Rollen-Trigger sperrt die Elternzeile (FOR UPDATE), bevor er den
    # Status liest. Ohne Sperre koennte die Rolle NACH dem Freeze durchrutschen.
    with verbindung(db) as conn:
        _insert(conn)
        conn.commit()
    ergebnisse: dict[str, Exception | None] = {}
    tor = threading.Barrier(2)

    def rolle_einfuegen():
        try:
            with verbindung(db) as conn:
                tor.wait(timeout=5)
                conn.execute(
                    "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
                    "profil_version, pos, rolle_id) "
                    "VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')", (MANDANT_A,))
                conn.commit()
            ergebnisse["rolle"] = None
        except Exception as fehler:                     # noqa: BLE001 — Testbeobachtung
            ergebnisse["rolle"] = fehler

    def freeze():
        try:
            with verbindung(db) as conn:
                conn.execute("SELECT 1 FROM bc1.prozessprofil "
                             "WHERE focus_step_id = 'KP-01.TP-1' FOR UPDATE")
                tor.wait(timeout=5)
                conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
                conn.commit()
            ergebnisse["freeze"] = None
        except Exception as fehler:                     # noqa: BLE001
            ergebnisse["freeze"] = fehler

    faeden = [threading.Thread(target=freeze), threading.Thread(target=rolle_einfuegen)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join(timeout=10)
    assert ergebnisse["freeze"] is None                 # der Freeze gewinnt
    assert ergebnisse["rolle"] is not None              # die Rolle prallt am Freeze ab
    assert "eingefroren" in str(ergebnisse["rolle"])


def test_zahlenspalten_weisen_nan_infinity_und_negativ_ab(db):
    for wert in ("NaN", "Infinity", "-1"):
        with verbindung(db) as conn:
            with pytest.raises(Exception) as fehler:
                _insert(conn, frequency_per_year=wert)
            assert "prozessprofil_zahlen_wertebereich" in str(fehler.value)


def test_fokus_schritt_muss_zum_prozess_gehoeren(db):
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute(
                "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
                "profil_version, process_id, status, erhebung_id, paket_version, profil) "
                "VALUES (%s, 'KP-01.TP-1', 1, 'KP-02', 'in_erhebung', 'E-2026-01', %s, '{}')",
                (MANDANT_A, FINGERPRINT))
        assert "prozessprofil_tp_gehoert_zu_kp" in str(fehler.value)


def test_kein_selbstbezug_bei_upstream(db):
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            _insert(conn, upstream_process_id="KP-01")
        assert "prozessprofil_upstream_kein_selbstbezug" in str(fehler.value)


def test_parallele_inserts_vergeben_verschiedene_versionen(db):
    # R3-I7: der Advisory-Lock im BEFORE-INSERT-Trigger serialisiert zwei
    # gleichzeitige Writer je (Mandant, Fokus-Schritt).
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.commit()
    versionen: list[int] = []
    tor = threading.Barrier(2)

    def einfuegen():
        with verbindung(db) as conn:
            tor.wait(timeout=5)
            versionen.append(_insert(conn, status="fertig"))
            conn.commit()

    faeden = [threading.Thread(target=einfuegen) for _ in range(2)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join(timeout=10)
    assert sorted(versionen) == [2, 3]          # keine Doppelvergabe


def test_kaskade_raeumt_auch_rollenzeilen(db):
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db, None) as conn:
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_teilprozess_eines_fremden_mandanten_wird_abgewiesen(db):
    # KP-02.TP-2 gibt es nur bei Mandant B — der Verbund-FK muss greifen.
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            _insert(conn, mandant=MANDANT_A, tp="KP-02.TP-2")
        assert "prozessprofil_teilprozess_fk" in str(fehler.value)


def test_triggerinduziertes_update_umgeht_den_freeze_nicht(db):
    # Codex R1-C2: die Kaskaden-Ausnahme gilt NUR fuer DELETE. Ein UPDATE aus
    # einem fremden Trigger heraus muss weiterhin am Freeze prallen.
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.execute("CREATE TABLE bc1.ausloeser (x int)")
        conn.execute(
            "CREATE FUNCTION bc1.tf_probe() RETURNS trigger LANGUAGE plpgsql AS "
            "$fn$ BEGIN UPDATE bc1.prozessprofil SET profil = '{\"x\":1}'::jsonb; "
            "RETURN NEW; END $fn$")
        conn.execute("CREATE TRIGGER tr_probe AFTER INSERT ON bc1.ausloeser "
                     "FOR EACH ROW EXECUTE FUNCTION bc1.tf_probe()")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("INSERT INTO bc1.ausloeser VALUES (1)")
        assert "eingefroren" in str(fehler.value)


def test_kaskade_laeuft_auch_unter_echter_rollentrennung(db):
    # R6-N6-C1: BC0 loescht Mandanten mit einem Konto, das auf bc1.* KEINE Rechte
    # hat. Gemessen: die FK-Kaskade laeuft mit den Rechten des Tabellen-
    # eigentuemers (bc1_role), der Rollen-Trigger kann prozessprofil also lesen.
    # Dieser Test haelt das fest — ein Superuser-DELETE wuerde es verdecken.
    with verbindung(db, None) as conn:
        conn.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles "
                     "WHERE rolname = 'bc0_loescher') THEN CREATE ROLE bc0_loescher; "
                     "END IF; END $$")
        conn.execute("GRANT SELECT, DELETE ON companies TO bc0_loescher")
        conn.execute("GRANT USAGE ON SCHEMA public TO bc0_loescher")
        conn.commit()
    with verbindung(db) as conn:
        # Reihenfolge zaehlt (Codex R7-N7-I1): erst Draft, dann Rollenzeile, DANN
        # einfrieren — in eine bereits fertige Version laesst der Rollen-Freeze
        # keine Zeile mehr hinein.
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute(
            "SELECT has_table_privilege('bc0_loescher', 'bc1.prozessprofil', 'SELECT')"
        ).fetchone()[0] is False                       # wirklich rechtelos
    with verbindung(db, "bc0_loescher") as conn:
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_fremdes_delete_auf_rollenzeile_einer_fertigen_version_prallt(db):
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("DELETE FROM bc1.profil_rollen")
        assert "eingefroren" in str(fehler.value)


def test_draft_loeschung_raeumt_die_rollenzeile_mit(db):
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.commit()
    with verbindung(db) as conn:                        # Betriebsweg K5
        conn.execute("DELETE FROM bc1.prozessprofil WHERE status = 'in_erhebung'")
        conn.commit()
    with verbindung(db) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_triggerinduziertes_delete_ohne_kaskade_prallt_am_freeze(db):
    # R5-N5-I2: die Ausnahme verlangt zusaetzlich, dass der companies-Elternsatz
    # schon weg ist. Ein fremdes Trigger-DELETE bei lebendem Mandanten muss also
    # scheitern — sonst waere der Freeze ueber jeden Trigger aushebelbar.
    with verbindung(db) as conn:
        _insert(conn, status="fertig")
        conn.execute("CREATE TABLE bc1.ausloeser_del (x int)")
        conn.execute(
            "CREATE FUNCTION bc1.tf_probe_del() RETURNS trigger LANGUAGE plpgsql AS "
            "$fn$ BEGIN DELETE FROM bc1.prozessprofil; RETURN NEW; END $fn$")
        conn.execute("CREATE TRIGGER tr_probe_del AFTER INSERT ON bc1.ausloeser_del "
                     "FOR EACH ROW EXECUTE FUNCTION bc1.tf_probe_del()")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("INSERT INTO bc1.ausloeser_del VALUES (1)")
        assert "eingefroren" in str(fehler.value)


def test_dsgvo_kaskade_raeumt_ein_voll_befuelltes_profil(db):
    # LUECKE DER URSPRUENGLICHEN PLAN-TESTS (am Container gefunden, 25.08.):
    # die bisherigen Kaskaden-Tests liessen process_owner_rolle_id leer und
    # deckten damit nicht ab, was in Etappe 2 der Normalfall ist. Mit gesetztem
    # Rollenbezug UND einer profil_rollen-Zeile blockierte profil_rollen_rolle_fk
    # das DELETE — die DSGVO-Loeschung waere stillschweigend gescheitert.
    # Ursache: profil_rollen wird erst auf Kaskadentiefe 2 geraeumt, die
    # NO-ACTION-Pruefung beim Loeschen von mandant_rollen laeuft auf Tiefe 1.
    with verbindung(db) as conn:
        # ALLE sieben kreuzenden Referenzen gesetzt (Codex N9-I4): Prozess,
        # Teilprozess und Erhebung sind Pflicht, dazu owner_rolle, upstream,
        # downstream und eine profil_rollen-Zeile.
        _insert(conn, process_owner_rolle_id="R-01",
                upstream_process_id="KP-02", downstream_process_id="KP-02")
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.execute("UPDATE bc1.prozessprofil SET status = 'fertig'")
        conn.commit()
    with verbindung(db, None) as conn:
        conn.execute("DELETE FROM companies WHERE company_id = %s", (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM bc1.profil_rollen").fetchone()[0] == 0


def test_einzelne_mandant_rolle_bleibt_trotz_deferrable_geschuetzt(db):
    # Die Kur darf die Schutzwirkung nicht kosten: eine einzelne mandant_rollen-
    # Zeile, auf die eine Profilzeile zeigt, muss unloeschbar bleiben. Bei
    # DEFERRABLE INITIALLY DEFERRED schlaegt das erst beim COMMIT zu — deshalb
    # liegt der commit() INNERHALB des raises-Blocks.
    with verbindung(db) as conn:
        _insert(conn)
        conn.execute(
            "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
            "profil_version, pos, rolle_id) VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-01')",
            (MANDANT_A,))
        conn.commit()
    with verbindung(db, None) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute("DELETE FROM mandant_rollen WHERE company_id = %s "
                         "AND rolle_id = 'R-01'", (MANDANT_A,))
            conn.commit()
        assert "profil_rollen_rolle_fk" in str(fehler.value)


def test_unbekannte_rolle_id_wird_weiterhin_abgewiesen(db):
    # Codex N9-I4: die Behauptung "DEFERRED kostet keine Schutzwirkung" war
    # unbelegt. Bei INITIALLY DEFERRED schlaegt der FK erst beim COMMIT zu.
    with verbindung(db) as conn:
        _insert(conn)
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            conn.execute(
                "INSERT INTO bc1.profil_rollen (company_id, focus_step_id, "
                "profil_version, pos, rolle_id) "
                "VALUES (%s, 'KP-01.TP-1', 1, 1, 'R-99')", (MANDANT_A,))
            conn.commit()
        assert "profil_rollen_rolle_fk" in str(fehler.value)


def test_kaskadentests_laufen_im_unguenstigsten_fall(db):
    # Diese Zusicherung ist der Grund, warum die Kaskaden-Tests etwas beweisen.
    # Beim DELETE FROM companies stehen die Kaskaden aller direkt referenzierenden
    # Tabellen in EINER Startqueue (Reihenfolge nach Triggername); was sie
    # ausloesen, wird HINTEN angehaengt. Feuert der bc1-Kaskadentrigger ZULETZT,
    # ist das der spaetestmoegliche Zeitpunkt, zu dem bc1-Zeilen verschwinden —
    # also der unguenstigste Fall. Am Container per Vorhersage bestaetigt:
    # bc1 zuletzt => profil_rollen_rolle_fk blockte (vor dem DEFERRABLE-Fix),
    # bc1 zuerst  => lief durch. Kippt diese Reihenfolge, testen die Kaskaden-
    # Tests nur noch den bequemen Fall — dann schlaegt hier Alarm.
    with verbindung(db, None) as conn:
        namen = conn.execute(
            "SELECT c.conrelid::regclass::text "
            "  FROM pg_constraint c JOIN pg_trigger t ON t.tgconstraint = c.oid "
            " WHERE c.confrelid = 'companies'::regclass AND c.contype = 'f' "
            "   AND t.tgrelid = 'companies'::regclass "
            " ORDER BY t.tgname").fetchall()
    assert namen, "keine companies-Kaskadentrigger gefunden"
    assert namen[-1][0] == "bc1.prozessprofil"


def test_fremder_teilprozess_wird_vom_verbund_fk_abgewiesen(db):
    # MANDANT_B hat KP-01.TP-1 ebenfalls — der Verbund-FK muss den Mandanten mitpruefen.
    with verbindung(db) as conn:
        _insert(conn, mandant=MANDANT_B, tp="KP-01.TP-1", erhebung="E-2026-09")
        conn.commit()
    with verbindung(db) as conn:
        with pytest.raises(Exception) as fehler:
            _insert(conn, mandant=MANDANT_A, tp="KP-01.TP-1", erhebung="E-2026-09")
        assert "prozessprofil_erhebung_fk" in str(fehler.value)
