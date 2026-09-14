import pytest

from bc1_service.start import (
    MELDUNG_KEINE_BEWERTUNG,
    MELDUNG_KEINE_TEILPROZESSE,
    lade_kontext,
    lies_company_id,
)
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


def test_bc0_wortlaut_der_startmeldungen_ist_festgenagelt():
    # Der erste Satz stammt WOERTLICH von BC0 (Antwort 10, 02.09.) und ist abgestimmt.
    # Ein Vergleich nur gegen die Konstante wuerde eine Umformulierung nicht bemerken:
    # beide Seiten aenderten sich mit. Deshalb hier das Literal — wer den Text aendert,
    # muss diesen Test bewusst mitaendern, statt ihn aus Versehen zu verlieren.
    # (Gemessen im Review 02.09.: mit Substring-Assertions blieb die Suite gruen,
    # nachdem beide Meldungen durch einen voellig anderen Satz ersetzt worden waren.)
    assert MELDUNG_KEINE_TEILPROZESSE == (
        "Für diesen Mandanten sind noch keine Teilprozesse erfasst. Das Interview kann "
        "erst geführt werden, wenn die Prozessstruktur steht.")
    assert MELDUNG_KEINE_BEWERTUNG == (
        "Für diesen Mandanten ist noch kein Teilprozess bewertet. Das Interview kann erst "
        "geführt werden, wenn mindestens ein Teilprozess im Self-Rating bewertet ist.")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_mandant_ohne_teilprozesse_startet_nicht_mit_bc0_wortlaut():
    # BC0-Antwort 10 (02.09.): der Zustand ist regulaer (Mandant -> Kernprozesse ->
    # Teilprozesse) — nicht starten, mit dem von BC0 vorgeschlagenen Wortlaut.
    frische_db(DSN)
    leer = "33333333-3333-3333-3333-333333333333"
    with verbindung(DSN, None) as conn:
        conn.execute("INSERT INTO companies (company_id, name) VALUES (%s, 'Demo C')", (leer,))
        conn.commit()
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, leer)
    assert str(fehler.value) == MELDUNG_KEINE_TEILPROZESSE


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_mandant_mit_teilprozessen_aber_ohne_bewertung_startet_nicht():
    # Nach dem Filter kann die Auswahl leer sein, obwohl Teilprozesse existieren —
    # dann waere BC0s Wortlaut ("keine Teilprozesse erfasst") sachlich falsch.
    frische_db(DSN)
    ohne = "44444444-4444-4444-4444-444444444444"
    with verbindung(DSN, None) as conn:
        conn.execute("INSERT INTO companies (company_id, name) VALUES (%s, 'Demo D')", (ohne,))
        conn.execute("INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) "
                     "VALUES (%s, 'KP-01', 'Auftrag D', 'Kerngeschäftsprozess')", (ohne,))
        conn.execute("INSERT INTO ref_teilprozesse (company_id, sub_process_id, process_id, "
                     "step_no, sub_process_name) VALUES (%s, 'KP-01.TP-1', 'KP-01', 1, 'Erfassen D')",
                     (ohne,))
        conn.commit()
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, ohne)
    assert str(fehler.value) == MELDUNG_KEINE_BEWERTUNG
