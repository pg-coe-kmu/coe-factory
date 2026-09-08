"""Anhang A (Rev. 12): die drei Use-Case-Testprofile sind aus dem Repo reproduzierbar."""
import dataclasses

import pytest
from psycopg_pool import ConnectionPool

from bc1_core.store import InMemoryStateStore
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket
from bc1_service.profil_writer import ProfilWriter
from bc1_service.start import lade_kontext
from bc1_service.use_case_testprofile import (FAELLE, fuehre_interview, main,
                                              schreibe_testprofile)
from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

# Offline reicht der synthetische Fixture-Mandant — die echte Mandantenkennung
# gehoert in den Aufruf der CLI, nicht ins Repo.
KONTEXT = Bc0Kontext(MANDANT_A, (("KP-05.TP-1", "Wissenstransfer"),
                            ("KP-06.TP-1", "Consulting-Matching"),
                            ("KP-06.TP-2", "Reise- und Einsatzplanung")),
                     tuple(f"S-0{i}" for i in range(1, 7)))


def _antworten():
    paket = baue_discovery_paket(kontext=KONTEXT)
    return [(fall, fuehre_interview(InMemoryStateStore(), paket, fall, company_id=MANDANT_A))
            for fall in FAELLE]


def test_jeder_fall_endet_fertig_und_vollstaendig():
    for fall, antwort in _antworten():
        assert antwort["status"] == "fertig", fall.session_id
        assert antwort["payload"]["vollstaendigkeit"] == 1.0, fall.session_id


def test_kennzeichnung_ist_gueltig_und_beginnt_mit_testdaten():
    for fall, antwort in _antworten():
        feld = antwort["payload"]["felder"]["open_remarks"]
        assert feld["status"] == "gueltig", fall.session_id
        assert feld["wert"].startswith("Testdaten"), fall.session_id


def test_kennzeichnung_steht_in_derselben_nachricht_wie_ein_pflichtfeld():
    # Lehre vom 08.09.: mit dem letzten Pflichtfeld wird der Kern terminal —
    # eine Kennzeichnung in einer spaeteren Nachricht bleibt 'fehlt'.
    paket = baue_discovery_paket(kontext=KONTEXT)
    pflicht = {s.name for s in paket.required_fields()}
    for fall in FAELLE:
        traeger = [felder for _, felder in fall.nachrichten
                   if any(name == "open_remarks" for name, _ in felder)]
        assert len(traeger) == 1, fall.session_id
        assert pflicht & {name for name, _ in traeger[0]}, (
            f"{fall.session_id}: open_remarks ohne Pflichtfeld in derselben Nachricht")


def test_fokus_tp_stimmt_mit_dem_skript_ueberein():
    # fokus_tp ist Metadatum UND steht als focus_step im Skript — beides muss zusammenpassen.
    for fall in FAELLE:
        werte = {name: wert for _, felder in fall.nachrichten for name, wert in felder}
        assert werte["focus_step"] == fall.fokus_tp, fall.session_id


# --- gegen die Datenbank: Gerüst kennt nur KP-01/KP-02, die drei Fokus-TPs kommen hier dazu

def _noro_geruest(conn) -> None:
    conn.execute(
        "INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) VALUES "
        "(%s, 'KP-05', 'Wissen', 'Kerngeschäftsprozess'), "
        "(%s, 'KP-06', 'Personal', 'Unterstützungsprozess')", (MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO ref_teilprozesse "
        "(company_id, sub_process_id, process_id, step_no, sub_process_name) VALUES "
        "(%s, 'KP-05.TP-1', 'KP-05', 1, 'Wissenstransfer'), "
        "(%s, 'KP-06.TP-1', 'KP-06', 1, 'Consulting-Matching'), "
        "(%s, 'KP-06.TP-2', 'KP-06', 2, 'Reise- und Einsatzplanung')",
        (MANDANT_A, MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO mandant_systeme (company_id, system_id, bezeichnung) VALUES "
        "(%s, 'S-03', 'Wiki'), (%s, 'S-04', 'Ablage'), (%s, 'S-05', 'CRM'), (%s, 'S-06', 'Skills')",
        (MANDANT_A, MANDANT_A, MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO bitkom_bewertungen "
        "(company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg, bewertet_am) VALUES "
        "(%s, 'E-2026-01', 'KP-05.TP-1.I-01', 'KP-05.TP-1', 1, 3, 'Testdaten', '2026-01-15'), "
        "(%s, 'E-2026-01', 'KP-06.TP-1.I-01', 'KP-06.TP-1', 1, 2, 'Testdaten', '2026-01-15'), "
        "(%s, 'E-2026-01', 'KP-06.TP-2.I-01', 'KP-06.TP-2', 1, 2, 'Testdaten', '2026-01-15')",
        (MANDANT_A, MANDANT_A, MANDANT_A))


@pytest.fixture
def pool():
    if not DSN:
        pytest.skip("BC1_TEST_DB_DSN nicht gesetzt — DB-Tests uebersprungen")
    frische_db(DSN)
    with verbindung(DSN, rolle=None) as conn:
        _noro_geruest(conn)
    p = ConnectionPool(DSN, min_size=1, max_size=4, open=True,
                       kwargs={"options": "-c role=bc1_role"})
    yield p
    p.close()


def _zeilen(sql):
    with verbindung(DSN) as conn:
        return conn.execute(sql).fetchall()


def test_schreibe_legt_drei_fertige_gekennzeichnete_zeilen_an(pool):
    ergebnis = schreibe_testprofile(pool, MANDANT_A)
    assert [e["status"] for e in ergebnis] == ["fertig"] * 3
    zeilen = _zeilen("SELECT focus_step_id, status, erhebung_id "
                     "FROM bc1.prozessprofil ORDER BY 1")
    assert zeilen == [("KP-05.TP-1", "fertig", "E-2026-01"),
                      ("KP-06.TP-1", "fertig", "E-2026-01"),
                      ("KP-06.TP-2", "fertig", "E-2026-01")]
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE profil->'felder'->'open_remarks'->>'wert' LIKE 'Testdaten%'") == [(3,)]


# Unabhaengige Erwartung (NICHT aus FAELLE abgeleitet): die Spaltenwerte, die am
# 08.09.2026 in der Supabase gemessen wurden. Aendert jemand einen Rohwert im Modul,
# widerspricht das Repo dem Ist-Stand — und dieser Test sagt es.
SPALTEN_08_09 = {
    #  focus_step_id : (haeufigkeit, menge, dauer_ges, dauer_fokus, guete, herkunft)
    "KP-05.TP-1": (260, 260, 45, 25, 50, "geschaetzt"),
    "KP-06.TP-1": (40, 40, 120, 60, 70, "geschaetzt"),
    "KP-06.TP-2": (180, 180, 180, 90, 60, "geschaetzt"),
}
KENNZEICHEN_08_09 = ("Testdaten Use-Case-Definition 24.08., nicht erhoben. "
                     "Quelle: Projektgruppe CoE-Factory.")


def test_gespeicherte_spalten_und_kennzeichnung_sind_die_werte_vom_08_09(pool):
    schreibe_testprofile(pool, MANDANT_A)
    zeilen = _zeilen(
        "SELECT focus_step_id, frequency_per_year, executions_per_run, "
        "       total_duration_minutes, focus_step_duration_minutes, "
        "       focus_step_duration_confidence_pct, focus_step_duration_source, "
        "       profil->'felder'->'open_remarks'->>'wert' "
        "FROM bc1.prozessprofil ORDER BY 1")
    assert {z[0]: tuple(z[1:7]) for z in zeilen} == SPALTEN_08_09
    assert {z[7] for z in zeilen} == {KENNZEICHEN_08_09}


def test_zweiter_lauf_erzeugt_keine_zweite_version(pool):
    # Kriterium 4: dieselben session_id/message_id -> keine neue Version, kein offener
    # Draft. Traeger ist die Writer-Bindung (profil_write_status), NICHT die Replay-
    # Weiche des Kerns — der Store ist je Lauf frisch, der Kern rechnet alles neu.
    schreibe_testprofile(pool, MANDANT_A)
    schreibe_testprofile(pool, MANDANT_A)
    assert _zeilen("SELECT focus_step_id, count(*) FROM bc1.prozessprofil "
                   "GROUP BY 1 ORDER BY 1") == [("KP-05.TP-1", 1), ("KP-06.TP-1", 1),
                                                ("KP-06.TP-2", 1)]
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE status = 'in_erhebung'") == [(0,)]


def test_neue_session_id_erzeugt_version_2(pool, monkeypatch):
    # Kriterium 4, zweite Haelfte: 'fertig' ist final — der einzige Korrekturweg
    # ist ein Lauf mit NEUER session_id, der eine neue Version anlegt.
    schreibe_testprofile(pool, MANDANT_A)
    neu = tuple(dataclasses.replace(f, session_id=f.session_id + "-v3") for f in FAELLE)
    monkeypatch.setattr("bc1_service.use_case_testprofile.FAELLE", neu)
    schreibe_testprofile(pool, MANDANT_A)
    assert _zeilen("SELECT focus_step_id, profil_version, status FROM bc1.prozessprofil "
                   "ORDER BY 1, 2") == [
        ("KP-05.TP-1", 1, "fertig"), ("KP-05.TP-1", 2, "fertig"),
        ("KP-06.TP-1", 1, "fertig"), ("KP-06.TP-1", 2, "fertig"),
        ("KP-06.TP-2", 1, "fertig"), ("KP-06.TP-2", 2, "fertig")]


def test_wiederholung_meldet_den_gespeicherten_stand_nicht_den_neuen_kern(pool):
    # Wie api.py: liefert der Writer das gespeicherte (eingefrorene) Profil, gilt
    # DAS — nicht, was der Kern in diesem Lauf frisch extrahiert hat.
    schreibe_testprofile(pool, MANDANT_A)
    with pool.connection() as conn:
        kontext = lade_kontext(conn, MANDANT_A)
    paket = baue_discovery_paket(kontext=kontext)
    fall = FAELLE[0]
    nachrichten = tuple(
        (text, tuple(("focus_step_duration_minutes", "900 Minuten")
                     if name == "focus_step_duration_minutes" else (name, wert)
                     for name, wert in felder))
        for text, felder in fall.nachrichten)
    antwort = fuehre_interview(InMemoryStateStore(), paket,
                               dataclasses.replace(fall, nachrichten=nachrichten),
                               company_id=MANDANT_A,
                               writer=ProfilWriter(pool, MANDANT_A, paket))
    assert antwort["payload"]["felder"]["focus_step_duration_minutes"]["wert"] == "90"


# --- CLI-Einstieg: ohne --echt wird nichts geschrieben

def _darf_nicht_schreiben(*_a, **_k):
    raise AssertionError("Trockenlauf darf schreibe_testprofile nicht aufrufen")


def test_main_ohne_echt_schreibt_nicht(monkeypatch, capsys):
    monkeypatch.setenv("BC1_DB_DSN", "postgresql://unbenutzt")
    monkeypatch.setattr("bc1_service.use_case_testprofile.schreibe_testprofile",
                        _darf_nicht_schreiben)
    assert main(["--company-id", MANDANT_A]) == 0
    assert "TROCKENLAUF" in capsys.readouterr().out


def test_main_echt_schreibt_drei_faelle_und_meldet_ok(pool, monkeypatch, capsys):
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    assert main(["--company-id", MANDANT_A, "--echt"]) == 0
    assert capsys.readouterr().out.count("OK ") == 3
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE status = 'fertig'") == [(3,)]


def test_main_echt_ohne_dsn_bricht_mit_klarer_meldung_ab(monkeypatch, capsys):
    monkeypatch.delenv("BC1_DB_DSN", raising=False)
    assert main(["--company-id", MANDANT_A, "--echt"]) == 1
    assert "BC1_DB_DSN" in capsys.readouterr().err


def test_main_echt_meldet_fehler_wenn_ein_fall_nicht_fertig_wird(pool, monkeypatch, capsys):
    # Mandant B hat die drei Fokus-TPs nicht: der Kern lehnt focus_step ab, kein Fall
    # wird fertig -> Exit 1, FEHLER-Zeilen, und der Writer hat nichts eingefroren.
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    assert main(["--company-id", MANDANT_B, "--echt"]) == 1
    assert capsys.readouterr().out.count("FEHLER") == 3
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE status = 'fertig'") == [(0,)]
