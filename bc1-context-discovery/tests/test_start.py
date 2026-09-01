import pytest

from bc1_service.start import lade_kontext, lies_company_id
from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung


def test_fehlende_company_id_ist_ein_startfehler():
    with pytest.raises(RuntimeError) as fehler:
        lies_company_id({})
    assert "BC1_COMPANY_ID" in str(fehler.value)


def test_unsinnige_company_id_ist_ein_startfehler():
    with pytest.raises(RuntimeError):
        lies_company_id({"BC1_COMPANY_ID": "mandant-1"})


def test_gueltige_uuid_wird_kleingeschrieben_durchgereicht():
    gross = "AAAAAAAA-1111-1111-1111-111111111111"
    assert lies_company_id({"BC1_COMPANY_ID": gross}) == gross.lower()


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_kontext_kommt_mandantengefiltert_aus_der_db():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        kontext = lade_kontext(conn, MANDANT_A)
    assert [tp for tp, _ in kontext.teilprozesse] == [
        "KP-01.TP-1", "KP-01.TP-2", "KP-02.TP-1"]
    assert kontext.system_ids == ("S-01", "S-02")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_unbekannter_mandant_ist_ein_startfehler():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, "99999999-9999-9999-9999-999999999999")
    assert "existiert nicht" in str(fehler.value)
