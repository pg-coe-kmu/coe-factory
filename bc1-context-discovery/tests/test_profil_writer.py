import pytest
from psycopg_pool import ConnectionPool

from bc1_core.feldtypen import AUSWAHL
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_service.paket_feldtypen import baue_system_typ
from bc1_service.profil_writer import ProfilWriteError, ProfilWriter
from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

PAKET = UseCasePackage(
    name="discovery", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa",
    fields=(
        FieldSpec("focus_step", "Welcher Schritt?",
                  typ=AUSWAHL("KP-01.TP-1", "KP-01.TP-2", "KP-02.TP-1"),
                  identitaetskritisch=True),
        FieldSpec("focus_step_systems", "Welche Systeme?",
                  typ=baue_system_typ(frozenset({"S-01", "S-02"}))),
    ),
)
FERTIG = {"status": "fertig", "payload": {}}
FRAGE = {"status": "frage", "payload": {}}
ABBRUCH = {"status": "abgebrochen_ohne_identitaet", "payload": {}}


@pytest.fixture
def pool():
    frische_db(DSN)
    p = ConnectionPool(DSN, min_size=1, max_size=4, open=True,
                       kwargs={"options": "-c role=bc1_role"})
    yield p
    p.close()


def _state(session_id="s1", tp="KP-01.TP-1", mandant=MANDANT_A, **felder):
    st = SessionState(session_id, PAKET.schema_version, paket_name="discovery",
                      company_id=mandant)
    st.values["focus_step"] = FieldValue(value=tp, status=FieldStatus.GUELTIG,
                                         source_message_id="m1")
    for name, (wert, status) in felder.items():
        st.values[name] = FieldValue(value=wert, status=status,
                                     source_message_id="m1")
    return st


def _zeilen(spalten="focus_step_id, profil_version, status"):
    with verbindung(DSN) as conn:
        return conn.execute(
            f"SELECT {spalten} FROM bc1.prozessprofil ORDER BY focus_step_id"
        ).fetchall()


def test_erster_turn_legt_draft_und_bindung_an(pool):
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(), FRAGE)
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT session_id, profil_version "
                            "FROM bc1.profil_write_status").fetchall() == [("s1", 1)]


def test_zweiter_turn_legt_keine_zweite_zeile_an(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    writer.reconcile(_state(), FRAGE)
    assert len(_zeilen()) == 1


def test_abschluss_friert_die_eigene_zeile_ein_und_liefert_den_payload(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    payload = writer.reconcile(_state(), FERTIG)
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]
    assert payload["felder"]["focus_step"]["wert"] == "KP-01.TP-1"


def test_abschluss_ohne_vorherigen_draft_legt_ihn_jetzt_an(pool):
    payload = ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(), FERTIG)
    assert payload is not None
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]


def test_replay_nach_committetem_freeze_ist_ein_no_op_erfolg(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FERTIG)
    payload = writer.reconcile(_state(), FERTIG)          # Antwort war verloren
    assert payload is not None                            # Erfolg ohne UPDATE
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]
