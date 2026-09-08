"""Anhang A (Rev. 12): die drei Use-Case-Testprofile sind aus dem Repo reproduzierbar."""
import pytest
from psycopg_pool import ConnectionPool

from bc1_core.store import InMemoryStateStore
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket
from bc1_service.use_case_testprofile import (FAELLE, fuehre_interview, main,
                                              schreibe_testprofile)
from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung

NORO = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"
KONTEXT = Bc0Kontext(NORO, (("KP-05.TP-1", "Wissenstransfer"),
                            ("KP-06.TP-1", "Consulting-Matching"),
                            ("KP-06.TP-2", "Reise- und Einsatzplanung")),
                     tuple(f"S-0{i}" for i in range(1, 7)))


def _antworten():
    paket = baue_discovery_paket(kontext=KONTEXT)
    return [(fall, fuehre_interview(InMemoryStateStore(), paket, fall, company_id=NORO))
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


def test_zweiter_lauf_erzeugt_keine_zweite_version(pool):
    # Kriterium 4: dieselben session_id/message_id -> Replay-Weiche + Draft-Bindung,
    # keine neue Version, kein offener Draft.
    schreibe_testprofile(pool, MANDANT_A)
    schreibe_testprofile(pool, MANDANT_A)
    assert _zeilen("SELECT focus_step_id, count(*) FROM bc1.prozessprofil "
                   "GROUP BY 1 ORDER BY 1") == [("KP-05.TP-1", 1), ("KP-06.TP-1", 1),
                                                ("KP-06.TP-2", 1)]
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE status = 'in_erhebung'") == [(0,)]


# --- CLI-Einstieg: ohne --echt wird nichts geschrieben

def _darf_nicht_schreiben(*_a, **_k):
    raise AssertionError("Trockenlauf darf schreibe_testprofile nicht aufrufen")


def test_main_ohne_echt_schreibt_nicht(monkeypatch, capsys):
    monkeypatch.setenv("BC1_DB_DSN", "postgresql://unbenutzt")
    monkeypatch.setattr("bc1_service.use_case_testprofile.schreibe_testprofile",
                        _darf_nicht_schreiben)
    assert main(["--company-id", MANDANT_A]) == 0
    assert "TROCKENLAUF" in capsys.readouterr().out
