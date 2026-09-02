import pytest

from bc1_service import bc0_lesepfade
from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")


@pytest.fixture(scope="module", autouse=True)
def db():
    frische_db(DSN)


def test_mandant_existiert_nur_fuer_bekannte_uuid():
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.mandant_existiert(conn, MANDANT_A) is True
        assert bc0_lesepfade.mandant_existiert(
            conn, "99999999-9999-9999-9999-999999999999") is False


def test_teilprozesse_liefern_nur_den_eigenen_mandanten():
    with verbindung(DSN) as conn:
        a = bc0_lesepfade.teilprozesse(conn, MANDANT_A)
        b = bc0_lesepfade.teilprozesse(conn, MANDANT_B)
    assert a == [("KP-01.TP-1", "Erfassen A"), ("KP-01.TP-2", "Pruefen A"),
                 ("KP-01.TP-3", "Archivieren A"), ("KP-02.TP-1", "Bestellen A")]
    gemeinsam = {tp for tp, _ in a}
    assert gemeinsam <= {tp for tp, _ in b}                  # IDs kollidieren...
    assert dict(a) != dict(b)                                # ...die Inhalte nicht
    assert {tp for tp, _ in b} - gemeinsam == {"KP-02.TP-2"}  # B-exklusiv


def test_bewertete_teilprozesse_filtern_mandant_und_verworfene_erhebungen():
    # Rev. 11: interviewbar ist nur, was mindestens eine AKTUELLE Bewertung hat.
    # KP-01.TP-3 ist bei A ausschliesslich in der verworfenen E-2026-03 bewertet —
    # fuer v_bewertung_aktuell also unbewertet. B hat dieselben IDs, aber nur
    # KP-01.TP-1 bewertet: ein fehlender company_id-Filter faellt sofort auf.
    with verbindung(DSN) as conn:
        alle_a = bc0_lesepfade.teilprozesse(conn, MANDANT_A)
        a = bc0_lesepfade.bewertete_teilprozesse(conn, MANDANT_A)
        b = bc0_lesepfade.bewertete_teilprozesse(conn, MANDANT_B)
    # Ohne diese Zeilen bewiese der Test die Verworfen-Logik nicht: fehlte KP-01.TP-3
    # in der Fixture oder seine Bewertung, waere er gruen, ohne dass je eine verworfene
    # Erhebung im Spiel war. Die Rohtabelle ist fuer bc1_role gesperrt, deshalb als
    # Eigentuemer gelesen — reine Fixture-Zusicherung, kein Produktivpfad.
    assert ("KP-01.TP-3", "Archivieren A") in alle_a
    with verbindung(DSN, None) as conn:
        status = conn.execute(
            "SELECT e.status FROM bitkom_bewertungen b "
            "  JOIN ref_erhebungen e ON e.company_id = b.company_id "
            "                       AND e.erhebung_id = b.erhebung_id "
            " WHERE b.company_id = %s AND b.sub_process_id = 'KP-01.TP-3'",
            (MANDANT_A,)).fetchall()
    assert [z[0] for z in status] == ["verworfen"]
    assert a == [("KP-01.TP-1", "Erfassen A"), ("KP-01.TP-2", "Pruefen A"),
                 ("KP-02.TP-1", "Bestellen A")]
    assert b == [("KP-01.TP-1", "Erfassen B")]


def test_system_ids_sind_mandantengetrennt():
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.system_ids(conn, MANDANT_A) == ["S-01", "S-02"]
        assert bc0_lesepfade.system_ids(conn, MANDANT_B) == ["S-01", "S-03"]


def test_kp_existenz_laeuft_ueber_die_sicht_und_filtert_den_mandanten():
    # KP-03 gibt es NUR bei Mandant B — ein fehlender company_id-Filter faellt
    # nur mit so einer ID auf (ein nirgends existierendes 'KP-99' beweist nichts).
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_A, "KP-01") is True
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_B, "KP-03") is True
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_A, "KP-03") is False
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_A, "KP-99") is False
