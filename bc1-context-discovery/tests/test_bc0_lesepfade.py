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


def test_erhebung_id_nimmt_die_juengste_aktuelle_nach_erhebungsstand():
    # A/KP-01.TP-1: Item 1 aus E-2026-02 (stand 2026-06-01), Item 2 aus E-2026-01
    # (stand 2026-01-15) — aber Item 2 wurde am 2026-08-01 KORRIGIERT, sein bewertet_am
    # ist juenger als alles in E-2026-02. Massgeblich ist der Erhebungs-STAND, wie in
    # v_bewertung_aktuell selbst: E-2026-02, nicht E-2026-01.
    # Dieser Test haelt zugleich die Mandantenbedingung IM JOIN: B hat eine eigene
    # E-2026-01 mit spaeterem Stand (2026-12-01). Faellt company_id aus der
    # JOIN-Bedingung, hebt Bs Stand As Verlierer-Erhebung auf Platz 1.
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-01.TP-1") == "E-2026-02"


def test_erhebung_id_filtert_den_mandanten_und_bricht_gleichstand_nach_id():
    # B/KP-01.TP-1: Item 1 aus E-2026-09, Item 2 aus E-2026-10 — BEIDE mit Stand
    # 2026-03-01. Gleichstand im Stand entscheidet erhebung_id DESC, wie in der Sicht
    # (Rev. 11a). Und: dieselbe TP-ID wie bei A, andere Antwort — Mandantenfilter.
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.erhebung_id(conn, MANDANT_B, "KP-01.TP-1") == "E-2026-10"


def test_erhebung_id_rankt_nach_stand_und_nicht_nach_der_id():
    # A/KP-02.TP-1: Item 1 aus E-2026-01 (stand 2026-01-15), Item 2 aus E-2026-05
    # (stand 2025-11-01). E-2026-05 hat die GROESSERE ID, aber den AELTEREN Stand.
    # Die einzige Stelle, an der beide Reihenfolgen auseinanderfallen — ohne sie
    # bestuende auch eine Implementierung, die ref_erhebungen gar nicht erst
    # verbindet und nur nach v.erhebung_id sortiert.
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-02.TP-1") == "E-2026-01"


def test_offene_erhebung_gilt_als_aktuell():
    # A/KP-01.TP-2: Item 1 aus E-2026-02 (abgeschlossen, stand 2026-06-01), Item 2 aus
    # E-2026-04 (OFFEN, stand 2026-09-01). v_bewertung_aktuell schliesst nur
    # 'verworfen' aus — eine laufende Erhebung ist aktuell und gewinnt hier nach Stand.
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-01.TP-2") == "E-2026-04"


def test_teilprozess_ohne_aktuelle_bewertung_meldet_sich_deutlich():
    # KP-01.TP-3 ist bei A nur in der VERWORFENEN Erhebung E-2026-03 bewertet — fuer die
    # Sicht also unbewertet. Seit Task 10b bietet der Dienst so einen Teilprozess nicht
    # mehr an; der Fehler bleibt als zweite Verteidigungslinie fuer den Wettlauf
    # "Bewertung nach Sitzungsstart verworfen".
    with verbindung(DSN) as conn:
        with pytest.raises(bc0_lesepfade.ErhebungFehltError):
            bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-01.TP-3")
