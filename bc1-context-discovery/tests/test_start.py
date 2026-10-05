import pytest

from bc1_service.start import (
    MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW,
    MELDUNG_ANFRAGE_OHNE_TEILPROZESSE,
    MELDUNG_ANFRAGE_UNBEKANNT,
    MELDUNG_KEINE_BEWERTUNG,
    MELDUNG_KEINE_TEILPROZESSE,
    MELDUNG_TEILPROZESSE_NICHT_BEREIT,
    lade_kontext,
    lies_anfrage_id,
    lies_company_id,
)
from tests.db_fixture import (
    ANFRAGE_A,
    ANFRAGE_A_EINGEGANGEN,
    ANFRAGE_A_KERNPROZESS,
    ANFRAGE_A_OHNE_TP,
    ANFRAGE_A_UNBEWERTET,
    DSN,
    MANDANT_A,
    MANDANT_B,
    frische_db,
    verbindung,
)


def test_fehlende_anfrage_id_ist_ein_startfehler():
    with pytest.raises(RuntimeError) as fehler:
        lies_anfrage_id({})
    assert "BC1_ANFRAGE_ID" in str(fehler.value)


@pytest.mark.parametrize("roh", ["a-2026-03", "A-26-03", "A-2026-3", "Anfrage 3"])
def test_anfrage_id_in_falscher_form_ist_ein_startfehler(roh):
    with pytest.raises(RuntimeError) as fehler:
        lies_anfrage_id({"BC1_ANFRAGE_ID": roh})
    assert "A-JJJJ-NN" in str(fehler.value)


def test_anfrage_id_wird_von_raendern_befreit():
    assert lies_anfrage_id({"BC1_ANFRAGE_ID": "  A-2026-03 "}) == "A-2026-03"


def test_wortlaut_der_anfrage_meldungen_ist_festgenagelt():
    assert MELDUNG_ANFRAGE_UNBEKANNT.format(anfrage_id="A-2026-09") == (
        "Die Anfrage A-2026-09 gibt es bei diesem Mandanten nicht. "
        "BC1_ANFRAGE_ID prüfen.")
    assert MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW.format(
        anfrage_id="A-2026-09", status="am_gate") == (
        "Die Anfrage A-2026-09 steht auf 'am_gate'. Interviewt wird nur eine Anfrage "
        "im Stand 'zugeordnet' oder 'im_interview'.")
    assert MELDUNG_ANFRAGE_OHNE_TEILPROZESSE.format(anfrage_id="A-2026-09") == (
        "Die Anfrage A-2026-09 ist keinem Teilprozess zugeordnet. Das Interview kann "
        "erst geführt werden, wenn BC0 die Anfrage zugeordnet hat.")
    assert MELDUNG_TEILPROZESSE_NICHT_BEREIT.format(
        anfrage_id="A-2026-09", liste="KP-01.TP-3") == (
        "Zur Anfrage A-2026-09 sind diese Teilprozesse nicht bewertet oder stillgelegt: "
        "KP-01.TP-3. BC0 übergibt eine Anfrage nur vollständig — das Interview startet "
        "erst, wenn alle bewertet und aktiv sind.")


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
def test_auswahl_sind_genau_die_teilprozesse_der_anfrage_mit_namen():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        kontext = lade_kontext(conn, MANDANT_A, ANFRAGE_A)
    assert kontext.teilprozesse == (("KP-01.TP-1", "Erfassen A"), ("KP-01.TP-2", "Pruefen A"))
    assert kontext.anfrage_id == ANFRAGE_A


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_unbekannte_anfrage_und_fremde_anfrage_brechen_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, "A-2026-99")
        assert str(fehler.value) == MELDUNG_ANFRAGE_UNBEKANNT.format(anfrage_id="A-2026-99")
        # A-2026-03 gibt es nur bei A — Mandant B darf sie nicht finden.
        with pytest.raises(RuntimeError):
            lade_kontext(conn, MANDANT_B, ANFRAGE_A_EINGEGANGEN)


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_anfrage_im_falschen_stand_bricht_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A_EINGEGANGEN)
    assert str(fehler.value) == MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW.format(
        anfrage_id=ANFRAGE_A_EINGEGANGEN, status="eingegangen")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_unbewerteter_teilprozess_der_anfrage_bricht_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A_UNBEWERTET)
    assert str(fehler.value) == MELDUNG_TEILPROZESSE_NICHT_BEREIT.format(
        anfrage_id=ANFRAGE_A_UNBEWERTET, liste="KP-01.TP-3")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_stillgelegter_direkt_zugeordneter_teilprozess_bricht_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("UPDATE ref_teilprozesse SET aktiv = false "
                     "WHERE company_id = %s AND sub_process_id = 'KP-01.TP-2'", (MANDANT_A,))
        conn.commit()
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A)
    assert str(fehler.value) == MELDUNG_TEILPROZESSE_NICHT_BEREIT.format(
        anfrage_id=ANFRAGE_A, liste="KP-01.TP-2")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_anfrage_ohne_teilprozesse_bricht_den_start_ab():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A_OHNE_TP)
    assert str(fehler.value) == MELDUNG_ANFRAGE_OHNE_TEILPROZESSE.format(
        anfrage_id=ANFRAGE_A_OHNE_TP)


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_kernprozess_bezug_ohne_bewertung_aller_tps_bricht_ab():
    # A-2026-02 = ganzer KP-01 -> TP-1, TP-2, TP-3; TP-3 ist nur verworfen bewertet.
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, MANDANT_A, ANFRAGE_A_KERNPROZESS)
    assert "KP-01.TP-3" in str(fehler.value)


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_kontext_kommt_mandantengefiltert_aus_der_db():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        kontext = lade_kontext(conn, MANDANT_A, ANFRAGE_A)
    # Seit B5 bietet der Start die Teilprozesse der ANFRAGE an, nicht mehr alle
    # bewerteten des Mandanten (vorher: KP-01.TP-1, KP-01.TP-2, KP-02.TP-1).
    assert [tp for tp, _ in kontext.teilprozesse] == ["KP-01.TP-1", "KP-01.TP-2"]
    assert kontext.system_ids == ("S-01", "S-02")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_unbekannter_mandant_ist_ein_startfehler():
    frische_db(DSN)
    with verbindung(DSN) as conn:
        with pytest.raises(RuntimeError) as fehler:
            lade_kontext(conn, "99999999-9999-9999-9999-999999999999", ANFRAGE_A)
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
            lade_kontext(conn, leer, ANFRAGE_A)
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
            lade_kontext(conn, ohne, ANFRAGE_A)
    assert str(fehler.value) == MELDUNG_KEINE_BEWERTUNG
