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
                 ("KP-02.TP-1", "Bestellen A")]
    gemeinsam = {tp for tp, _ in a}
    assert gemeinsam <= {tp for tp, _ in b}                  # IDs kollidieren...
    assert dict(a) != dict(b)                                # ...die Inhalte nicht
    assert {tp for tp, _ in b} - gemeinsam == {"KP-02.TP-2"}  # B-exklusiv


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
