import pytest
from psycopg_pool import ConnectionPool

from bc1_core.feldtypen import AUSWAHL
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_service import bc0_lesepfade
from bc1_service.paket_feldtypen import baue_system_typ
from bc1_service.profil_writer import (
    GRUND_SNN_ENTFALLEN,
    Bindung,
    ProfilWriteError,
    ProfilWriter,
)
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
        # Ohne dieses Feld war die kp_existiert-Verdrahtung des Writers nicht
        # pruefbar: _payload_wert findet nur, was im Paket steht (Review 03.09.,
        # per Mutation belegt — die Assertion lief vorher ins Leere).
        FieldSpec("upstream_process", "Was kommt davor?", required=False),
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


def test_fremder_draft_wird_einmal_gemeldet_und_nicht_bei_jedem_turn(pool, caplog):
    # Spec K3.2: der Konflikt ist STABIL — er besteht in jedem Folgeturn weiter.
    # Ohne Ratenbegrenzung schriebe jeder Turn dieselbe Zeile ins Log.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="fremd"), FRAGE)
    with caplog.at_level("WARNING"):
        for _ in range(3):
            writer.reconcile(_state(session_id="s2"), FRAGE)
    assert caplog.text.count("fremder_draft_konflikt") == 1


def test_der_fehlerlog_traegt_keinen_payload_inhalt(pool, caplog):
    # Review 03.09.: grund=%r trug Postgres' DETAIL-Zeile ins Log, und die enthaelt
    # einen Ausschnitt der eingefuegten Zeile — inklusive Profil-JSON. Dass darin
    # heute kein Nutzertext steht, war Zufall der JSON-Schluesselordnung. Nach K-I
    # wird sowas nicht mit "passt schon" abgehakt.
    with verbindung(DSN, None) as conn:                # CHECK-Verletzung erzwingen
        conn.execute("ALTER TABLE bc1.prozessprofil "
                     "ADD CONSTRAINT tmp_immer_falsch CHECK (false) NOT VALID")
        conn.commit()
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    with caplog.at_level("WARNING"):
        assert writer.reconcile(_state(), FRAGE) is None
    assert "profil_write_uebersprungen" in caplog.text     # gemeldet wird trotzdem
    assert "Failing row contains" not in caplog.text
    assert "felder" not in caplog.text


def test_erste_konfliktmeldung_kommt_auch_direkt_nach_dem_systemstart(pool, caplog,
                                                                     monkeypatch):
    # Der Vergleich lief gegen den Default 0.0. Liegt time.monotonic() noch unter
    # dem Abstand — also kurz nach dem Systemstart —, galt der allererste Konflikt
    # als "schon gemeldet" und verschwand (Codex-Review 03.09., gemessen).
    monkeypatch.setattr("bc1_service.profil_writer.time.monotonic", lambda: 30.0)
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="fremd"), FRAGE)
    with caplog.at_level("WARNING"):
        writer.reconcile(_state(session_id="s2"), FRAGE)
    assert "fremder_draft_konflikt" in caplog.text


def test_auch_der_rebind_konflikt_wird_gemeldet(pool, caplog):
    # Zwei Pfade koennen an einem belegten Ziel scheitern — Neuanlage und Rebind.
    # Ohne diesen Test meldet nur einer von beiden, und der Rebind-Konflikt bliebe
    # im Betrieb unsichtbar.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="s1", tp="KP-01.TP-1"), FRAGE)
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(
        _state(session_id="fremd", tp="KP-01.TP-2"), FRAGE)
    with caplog.at_level("WARNING"):
        writer.reconcile(_state(session_id="s1", tp="KP-01.TP-2"), FRAGE)
    assert "fremder_draft_konflikt" in caplog.text
    assert "schritt=KP-01.TP-2" in caplog.text


def test_fehler_fortsetzbar_schreibt_nichts(pool):
    # Der Turn ist fachlich nicht zustandegekommen — es gibt nichts abzugleichen,
    # und ein Draft aus einem frueheren Turn bleibt unangetastet.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    assert writer.reconcile(_state(), {"status": "fehler_fortsetzbar",
                                       "payload": {}}) is None
    assert _zeilen() == []


def test_rebind_konflikt_im_terminal_turn_erzeugt_503(pool):
    # Ohne eigene Bindung auf dem neuen Fokus-Schritt darf keine fertig-Antwort
    # rausgehen (Postcondition K3.3). Der Meldungstext ist mitgeprueft: sonst
    # traegt der generische Fehlerpfad einen AttributeError nach aussen, und im
    # Log stuende nicht, WAS blockiert hat.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(session_id="s1", tp="KP-01.TP-1"), FRAGE)
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(
        _state(session_id="fremd", tp="KP-01.TP-2"), FRAGE)
    with pytest.raises(ProfilWriteError, match="Rebind-Ziel"):
        writer.reconcile(_state(session_id="s1", tp="KP-01.TP-2"), FERTIG)
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung"),
                         ("KP-01.TP-2", 1, "in_erhebung")]


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
    # Ohne diese Zeile war der Test auch mit einem Writer gruen, der gar nichts
    # tut — "aufgeraeumt" und "nie angelegt" sahen gleich aus (Review 03.09.).
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]
    assert writer.reconcile(_state(), ABBRUCH) is None
    assert _zeilen() == []
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.profil_write_status"
                            ).fetchone()[0] == 0            # CASCADE raeumt mit


def test_abbruch_raeumt_auch_wenn_der_profilbau_scheitert(pool, monkeypatch):
    # Review 03.09.: Der Abbruch braucht den Profilinhalt gar nicht — er muss VOR
    # dem Bau behandelt werden. Lief der Bau zuerst, riss jeder Fehler darin (hier
    # stellvertretend der BC0-Systemlookup) das Aufraeumen mit: der Draft blieb
    # verwaist stehen und belegte den UNIQUE-Slot des Fokus-Schritts.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]      # Draft steht wirklich
    monkeypatch.setattr(
        bc0_lesepfade, "system_ids",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("BC0-Systemlookup kaputt")))
    assert writer.reconcile(_state(), ABBRUCH) is None
    assert _zeilen() == []


def test_unklar_allein_loescht_den_draft_noch_nicht(pool):
    # R6-C1: die Klaerung kann den alten Wert bestaetigen — voreiliges Loeschen
    # waere Datenverlust. Erst der Terminalzustand raeumt.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    unklar = _state()
    unklar.values["focus_step"].status = FieldStatus.UNKLAR
    assert writer.reconcile(unklar, FRAGE) is None
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]


def test_vom_sweep_entfernte_identitaet_meldet_sauber_statt_abzustuerzen(pool):
    # Seit der Sweep vor der Ableitung laeuft, kann er die Identitaet selbst
    # treffen: der Payload traegt danach None, und die Ableitung lief in einen
    # AttributeError (Review 03.09. gemessen). Mit dem echten Discovery-Paket
    # unerreichbar — BC0s TP-IDs enthalten keine S-NN-Kennung —, aber der
    # Sweep-Docstring fordert genau hier einen Guard.
    ident_ist_system = UseCasePackage(
        name="discovery", schema_version="1.1+ctx-cccccccccccccccc",
        fields=(FieldSpec("focus_step", "Welcher Schritt?",
                          typ=baue_system_typ(frozenset({"S-01", "S-02"})),
                          identitaetskritisch=True),))
    writer = ProfilWriter(pool, MANDANT_A, ident_ist_system)
    with pytest.raises(ProfilWriteError, match="Completion-Guard"):
        writer.reconcile(_state(tp="S-99"), FERTIG)
    assert writer.reconcile(_state(tp="S-99"), FRAGE) is None
    assert _zeilen() == []


def test_bc0_verdrahtung_filtert_den_mandanten(pool):
    # Review 03.09.: Kein Test setzte je focus_step_systems oder upstream_process —
    # die beiden BC0-Zulieferungen des Writers waren voellig ungedeckt. Ein
    # Aufruf ohne company_id (oder mit den Systemen ALLER Mandanten) fiel nirgends
    # auf, ausgerechnet an der Stelle, die BC0-Auflage 1.4 erfuellen soll.
    # S-03 gehoert nur B, KP-03 gibt es nur bei B.
    zustand = _state(focus_step_systems=("S-03", FieldStatus.GUELTIG),
                     upstream_process=("KP-03", FieldStatus.GUELTIG))
    payload = ProfilWriter(pool, MANDANT_A, PAKET).reconcile(zustand, FERTIG)

    systeme = payload["felder"]["focus_step_systems"]
    assert systeme["wert"] is None                       # S-03 weggesweept
    assert systeme["grund"] == GRUND_SNN_ENTFALLEN
    with verbindung(DSN) as conn:
        assert conn.execute(
            "SELECT upstream_process_id FROM bc1.prozessprofil "
            "WHERE company_id = %s", (MANDANT_A,)).fetchone()[0] is None


def test_replay_liefert_das_gespeicherte_profil_nicht_das_frisch_gebaute(pool):
    # Der Replay-Test nebenan prueft nur "nicht None" — eine Implementierung, die
    # inhalt.profil zurueckgibt statt der DB-Zeile, bliebe unentdeckt (Review
    # 03.09.). Deshalb traegt der Replay-Turn einen ZUSAETZLICHEN Feldwert: der
    # frisch gebaute Payload haette ihn, der eingefrorene nicht. Massgeblich ist
    # der eingefrorene — spaetere Eingaben duerfen ein fertiges Profil nicht mehr
    # veraendern.
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    erster = writer.reconcile(_state(), FERTIG)
    assert erster["felder"]["focus_step_systems"]["wert"] is None

    spaeter = _state(focus_step_systems=("S-01", FieldStatus.GUELTIG))
    payload = writer.reconcile(spaeter, FERTIG)
    assert payload["felder"]["focus_step_systems"]["wert"] is None


def test_freeze_der_keine_zeile_trifft_ist_ein_503(pool, monkeypatch):
    # Wettlauf: zwischen Bindungssuche und Freeze friert jemand anderes die Zeile
    # ein. Der Freeze trifft dann 0 Zeilen. Ohne den rowcount-Wachter ginge der
    # Payload trotzdem raus — genau der K3.3-Bruch (Review 03.09., dort im echten
    # Wettlauf gemessen; hier deterministisch ueber einen veralteten Bindungsstand).
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FERTIG)                    # Zeile steht auf 'fertig'
    veraltet = Bindung("KP-01.TP-1", 1, "in_erhebung")    # Stand von VOR dem Freeze
    monkeypatch.setattr(ProfilWriter, "_bindung",
                        lambda self, conn, session_id: veraltet)
    with pytest.raises(ProfilWriteError, match="Freeze traf 0 Zeilen"):
        writer.reconcile(_state(session_id="s2"), FERTIG)


def test_fertig_ohne_gueltige_identitaet_ist_ein_503(pool):
    # Der Completion-Guard war ungetestet: eine Implementierung, die hier None
    # zurueckgibt statt zu werfen, liess alle Tests gruen (Review 03.09.).
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    unklar = _state()
    unklar.values["focus_step"].status = FieldStatus.UNKLAR
    with pytest.raises(ProfilWriteError, match="Completion-Guard"):
        writer.reconcile(unklar, FERTIG)
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]   # Draft unangetastet


def test_gueltig_unklar_abbruch_raeumt_den_draft(pool):
    writer = ProfilWriter(pool, MANDANT_A, PAKET)
    writer.reconcile(_state(), FRAGE)
    unklar = _state()
    unklar.values["focus_step"].status = FieldStatus.UNKLAR
    writer.reconcile(unklar, FRAGE)
    assert _zeilen() == [("KP-01.TP-1", 1, "in_erhebung")]   # steht wirklich noch
    assert writer.reconcile(unklar, ABBRUCH) is None
    assert _zeilen() == []


def test_bewertung_nach_sitzungsstart_verworfen_erzeugt_im_terminal_turn_503(pool):
    # Der State traegt einen Teilprozess ohne aktuelle Bewertung. ErhebungFehltError
    # wird NICHT gefangen: der generische Fehlerpfad macht daraus im Terminal-Turn
    # einen 503 und sonst einen Log-Eintrag.
    # ABGEDECKT ist damit nur der Fall OHNE bestehenden Draft — dort laeuft der
    # Erhebungs-Lookup beim Einfuegen. Steht der Draft schon (Regelbetrieb ab
    # Turn 1), greift der Schutz NICHT: der Freeze prueft die Erhebung nicht nach,
    # das Profil wird auf eine inzwischen verworfene Erhebung eingefroren. Im
    # Review 03.09. gemessen, nachgehalten als Klaerpunkt K-K.
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
    # Review 03.09.: Die alte Fassung nahm zwei VERSCHIEDENE session_ids — damit
    # konnte die Bindungssuche die fremde Zeile ohnehin nie finden, der Test war
    # wirkungslos. Scharf wird es erst so: A haelt die (global vergebene) Sitzung
    # 's1'. B bekommt einen Abbruch-Turn mit derselben ID, hat aber selbst einen
    # Draft aus einer ANDEREN Sitzung. Ohne company_id in der Bindungssuche findet
    # B die Bindung von A, und A's Sitzungszustand entscheidet, welche Zeile von B
    # geloescht wird.
    ProfilWriter(pool, MANDANT_A, PAKET).reconcile(_state(session_id="s1"), FRAGE)
    ProfilWriter(pool, MANDANT_B, PAKET).reconcile(
        _state(session_id="andere", mandant=MANDANT_B), FRAGE)
    vorher = _zeilen("company_id, focus_step_id")
    assert len(vorher) == 2

    ProfilWriter(pool, MANDANT_B, PAKET).reconcile(
        _state(session_id="s1", mandant=MANDANT_B), ABBRUCH)
    assert _zeilen("company_id, focus_step_id") == vorher     # nichts angefasst


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
