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


def test_tp_korrektur_bindet_um_und_raeumt_den_alten_draft(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    writer.reconcile(_state(tp="KP-01.TP-2"), FRAGE)
    assert _zeilen() == [("KP-01.TP-2", 1, "in_erhebung")]


def test_tp_korrektur_ueber_die_kp_grenze_zieht_process_id_nach(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    writer.reconcile(_state(tp="KP-02.TP-1"), FRAGE)
    assert _zeilen("focus_step_id, process_id") == [("KP-02.TP-1", "KP-02")]


def test_rebind_konflikt_laesst_den_alten_draft_stehen(pool):
    # Codex R1-C5: bei einem belegten Ziel darf der alte Draft NICHT verloren
    # gehen — Loeschen und Neuanlage liegen in einem gemeinsamen Savepoint.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="s1", tp="KP-01.TP-1"), FRAGE)
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(
        _state(session_id="fremd", tp="KP-01.TP-2"), FRAGE)
    assert writer.reconcile(_state(session_id="s1", tp="KP-01.TP-2"), FRAGE) is None
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung"),
                         ("KP-01.TP-2", 1, "in_erhebung")]
    with verbindung(DSN) as conn:
        assert conn.execute(
            "SELECT focus_step_id FROM bc1.profil_write_status "
            "WHERE session_id = 's1'").fetchone()[0] == "KP-01.TP-1"


def test_kp_feld_aenderung_loest_keinen_rebind_aus(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    geaendert = _state()
    geaendert.values["process_id"] = FieldValue(
        value="KP-02", status=FieldStatus.GUELTIG, source_message_id="m2")
    writer.reconcile(geaendert, FRAGE)
    assert _zeilen("focus_step_id, process_id") == [("KP-01.TP-1", "KP-01")]


def test_fremder_draft_blockiert_stabil_und_wird_nicht_adoptiert(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="fremd"), FRAGE)
    assert writer.reconcile(_state(session_id="s2"), FRAGE) is None
    assert len(_zeilen()) == 1
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_write_status"
                            ).fetchone()[0] == 1


def test_fremder_draft_im_terminal_turn_erzeugt_503(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="fremd"), FRAGE)
    with pytest.raises(ProfilWriteError):
        writer.reconcile(_state(session_id="s2"), FERTIG)


def test_abbruch_raeumt_den_gebundenen_draft(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    assert writer.reconcile(_state(), ABBRUCH) is None
    assert _zeilen() == []
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_write_status"
                            ).fetchone()[0] == 0            # CASCADE raeumt mit


def test_unklar_allein_loescht_den_draft_noch_nicht(pool):
    # R6-C1: die Klaerung kann den alten Wert bestaetigen — voreiliges Loeschen
    # waere Datenverlust. Erst der Terminalzustand raeumt.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    unklar = _state()
    unklar.values["focus_step"].status = FieldStatus.UNKLAR
    assert writer.reconcile(unklar, FRAGE) is None
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]


def test_gueltig_unklar_abbruch_raeumt_den_draft(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    unklar = _state()
    unklar.values["focus_step"].status = FieldStatus.UNKLAR
    writer.reconcile(unklar, FRAGE)
    assert writer.reconcile(unklar, ABBRUCH) is None
    assert _zeilen() == []


def test_bewertung_nach_sitzungsstart_verworfen_erzeugt_im_terminal_turn_503(pool):
    # Wettlauf: der State traegt einen Teilprozess, der zur Laufzeit keine aktuelle
    # Bewertung (mehr) hat. Seit Task 10b ist das im Regelbetrieb nicht mehr waehlbar;
    # ErhebungFehltError wird NICHT gefangen, der generische Fehlerpfad macht daraus
    # im Terminal-Turn einen 503 und in nicht-terminalen Turns einen Log-Eintrag.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    with pytest.raises(ProfilWriteError):
        writer.reconcile(_state(tp="KP-01.TP-3"), FERTIG)
    assert writer.reconcile(_state(tp="KP-01.TP-3"), FRAGE) is None   # kein Absturz


def test_paket_ohne_identitaetsfeld_schreibt_nichts(pool):
    ohne = UseCasePackage(name="toy_prozess", schema_version="0.1",
                          fields=(FieldSpec("prozess_name", "Wie heisst er?"),))
    assert ProfilWriter(pool, MANDANT_A, ohne).reconcile(_state(), FERTIG) is None
    assert _zeilen() == []


def test_bindung_wird_nur_im_eigenen_mandanten_gefunden(pool):
    # session_id ist globaler Primaerschluessel von profil_write_status — zwei
    # Mandanten koennen sie sich also nie teilen. Geprueft wird deshalb: der
    # Writer von B findet die Bindung von A NICHT und legt seine eigene an.
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(session_id="s-a"), FRAGE)
    ProfilWriter(pool, MANDANT_B, PAKET).reconcile(
        _state(session_id="s-b", mandant=MANDANT_B), FRAGE)
    with verbindung(DSN) as conn:
        paare = conn.execute(
            "SELECT w.session_id, w.company_id FROM bc1.profil_write_status w "
            "ORDER BY w.session_id").fetchall()
    assert [(z[0], str(z[1])) for z in paare] == [
        ("s-a", MANDANT_A), ("s-b", MANDANT_B)]
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(DISTINCT company_id) "
                            "FROM bc1.prozessprofil").fetchone()[0] == 2


def test_zweites_interview_bekommt_version_zwei(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="s1"), FERTIG)
    writer.reconcile(_state(session_id="s2"), FERTIG)
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig"), ("KP-01.TP-1", 2, "fertig")]


def test_neustart_nach_committeter_bindung_macht_sauber_weiter(pool):
    # Crash "nach INSERT, vor Antwort": ein FRISCHER Writer (neuer Prozess) muss
    # die Bindung in profil_write_status finden — keine zweite Zeile.
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(), FRAGE)
    payload = ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(), FERTIG)
    assert payload is not None
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]


def test_fehlgeschlagenes_aufraeumen_am_draft_liefert_trotzdem_aus(pool, caplog):
    # K5-Fall: das DELETE scheitert, der Draft BLEIBT verwaist stehen, die
    # Antwort geht trotzdem raus (Codex R2-N-I6 — der Freeze-Fall unten kann
    # das nicht zeigen, dort gibt es gar keinen Draft).
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    with verbindung(DSN, None) as conn:                # DELETE gezielt blockieren
        conn.execute(
            "CREATE FUNCTION bc1.tf_blockiere() RETURNS trigger LANGUAGE plpgsql "
            "AS $fn$ BEGIN RAISE EXCEPTION 'Aufraeumen blockiert'; END $fn$")
        conn.execute("CREATE TRIGGER tr_blockiere BEFORE DELETE ON bc1.prozessprofil "
                     "FOR EACH ROW EXECUTE FUNCTION bc1.tf_blockiere()")
        conn.commit()
    with caplog.at_level("ERROR"):
        assert writer.reconcile(_state(), ABBRUCH) is None      # KEIN 503
    assert "draft_aufraeumen_fehlgeschlagen" in caplog.text
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]      # Draft bleibt


def test_fehlgeschlagenes_aufraeumen_bei_eingefrorener_zeile(pool, caplog):
    # Realistische Simulation: die gebundene Zeile ist inzwischen eingefroren —
    # der Freeze-Trigger weist das DELETE ab (K5-Fall, verwaister Draft bleibt).
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FERTIG)
    with caplog.at_level("ERROR"):
        assert writer.reconcile(_state(), ABBRUCH) is None   # KEIN 503
    assert "draft_aufraeumen_fehlgeschlagen" in caplog.text  # strukturiert geloggt
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]        # Zeile bleibt stehen


def test_replay_nach_committetem_freeze_ist_ein_no_op_erfolg(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FERTIG)
    payload = writer.reconcile(_state(), FERTIG)          # Antwort war verloren
    assert payload is not None                            # Erfolg ohne UPDATE
    assert _zeilen() == [("KP-01.TP-1", 1, "fertig")]
