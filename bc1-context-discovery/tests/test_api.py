import logging
import threading
from contextlib import asynccontextmanager
from dataclasses import replace

from fastapi.testclient import TestClient

from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import FieldSpec, TOY_PROZESS, UseCasePackage
from bc1_core.store import InMemoryStateStore, StaleStateError
from bc1_core.types import SessionState, SessionStatus
from bc1_service.api import (ABBRUCH_TEXT, MELDUNG_GATE_FEHLGESCHLAGEN,
                             OVERLAY_SCHLUESSEL, _sweep_hinweise, create_app)
from bc1_service.bc0_meldungen import Bc0MeldungFehler

MANDANT = "11111111-1111-1111-1111-111111111111"
MANDANT_B = "22222222-2222-2222-2222-222222222222"

IDENT_PAKET = UseCasePackage(
    name="ident_test", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa", max_rounds=2,
    fields=(FieldSpec("tp_id", "Welcher Schritt?",
                      validator=lambda v: v == "KP-01.TP-1",
                      identitaetskritisch=True),),
)


def _fake_llm() -> FakeLLM:
    return FakeLLM({
        "Der Prozess heißt Urlaubsantrag": [
            ExtractionCandidate("prozess_name", "Urlaubsantrag")
        ],
        "Ausgelöst durch einen Antrag": [
            ExtractionCandidate("ausloeser", "Antrag")
        ],
        "Etwa 100 mal pro Jahr": [
            ExtractionCandidate("haeufigkeit", "100 mal pro Jahr")
        ],
    })


class ExplodierendesLLM(FakeLLM):
    def extract(self, message, package, state):
        raise RuntimeError("LLM kaputt")


def _client(llm=None, store=None) -> TestClient:
    return TestClient(create_app(store or InMemoryStateStore(),
                                 llm or _fake_llm(), TOY_PROZESS,
                                 company_id=MANDANT))


def _turn(client, mid, text, session="s1", **extra):
    return client.post("/turn", json={
        "session_id": session, "message_id": mid, "message": text, **extra
    })


def test_gesundheit():
    antwort = _client().get("/gesundheit")
    assert antwort.status_code == 200
    assert antwort.json()["paket"] == "toy_prozess"


def test_interview_bis_fertig_mit_chat_text():
    client = _client()
    a1 = _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    assert a1.status_code == 200
    assert a1.json()["status"] == "frage"
    assert a1.json()["chat_text"].startswith(a1.json()["payload"]["naechste_frage"])
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    a3 = _turn(client, "m3", "Etwa 100 mal pro Jahr")
    assert a3.json()["status"] == "fertig"
    assert a3.json()["payload"]["vollstaendigkeit"] == 1.0
    assert "Zusammenfassung" in a3.json()["chat_text"]
    assert "✓ " in a3.json()["chat_text"]


def test_chat_text_traegt_fortschrittszeile():
    client = _client()
    antwort = _turn(client, "m1", "Der Prozess heißt Urlaubsantrag",
                    session="s-fortschritt")
    daten = antwort.json()
    p = daten["payload"]
    erwartet = (f"✓ {p['pflicht_erfasst']} von {p['pflicht_gesamt']} "
                "Pflichtfeldern erfasst")
    assert daten["chat_text"].endswith(erwartet)
    assert daten["chat_text"].startswith(p["naechste_frage"])


def test_gleiche_message_id_ist_idempotent():
    client = _client()
    a1 = _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    a2 = _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    assert a2.status_code == 200
    assert a2.json() == a1.json()


def test_schema_version_mismatch_gibt_409():
    antwort = _turn(_client(), "m1", "egal", schema_version="99.9")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "schema_version_passt_nicht"


def test_fertige_session_weist_neue_nachricht_aktiv_ab():
    client = _client()
    _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    alt = _turn(client, "m3", "Etwa 100 mal pro Jahr")
    neu = _turn(client, "m4", "noch etwas!")
    assert neu.status_code == 409
    assert neu.json()["detail"] == "session_abgeschlossen"
    # Replay einer bekannten message_id bleibt idempotent erlaubt:
    replay = _turn(client, "m3", "Etwa 100 mal pro Jahr")
    assert replay.status_code == 200
    assert replay.json()["status"] == "fertig"
    assert replay.json()["payload"] == alt.json()["payload"]


def test_llm_ausfall_gibt_vertragsantwort_mit_status_200():
    antwort = _turn(_client(llm=ExplodierendesLLM()), "m1", "Hallo")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fehler_fortsetzbar"
    assert antwort.json()["chat_text"]  # Nutzer bekommt eine Chat-Erklärung


def test_paket_guard_gibt_409_mit_stabilem_detail():
    store = InMemoryStateStore()
    store.save(SessionState("s9", "9.9", paket_name="fremdes_paket",
                            company_id=MANDANT))
    antwort = _turn(_client(store=store), "m1", "Hallo", session="s9")
    assert antwort.status_code == 409
    # Stabiler Schlüssel statt Exception-Text: der Chat bekommt keine
    # Interna zu sehen, n8n kann darauf verzweigen.
    assert antwort.json()["detail"] == "paket_konflikt"


def test_prozesse_ohne_snapshot_404():
    assert _client().get("/prozesse").status_code == 404


class _StaleBeimErstenSave(InMemoryStateStore):
    """Simuliert einen verlorenen Schreib-Wettlauf (z. B. zweiter Prozess)."""

    def __init__(self) -> None:
        super().__init__()
        self._saves = 0

    def save(self, state):
        self._saves += 1
        if self._saves == 1:
            raise StaleStateError("fremder Schreibzugriff kam zuerst")
        super().save(state)


# Sicherheitsnetz: das Prozess-Lock deckt nur den Ein-Prozess-Betrieb —
# ein verlorener CAS-Wettlauf ist ein Konflikt, kein 500er.
def test_stale_konflikt_gibt_409():
    antwort = _turn(_client(store=_StaleBeimErstenSave()), "m1", "Hallo")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "gleichzeitige_anfrage"


# Gate-Kriterium ist "kennt die Session diese message_id?", nicht "gibt es
# schon eine Antwort dazu?": ein bekannter, unbeantworteter Turn (Crash
# zwischen den Saves) muss an den Kern durch — der liefert idempotent, was er
# hat, statt den Retry mit 409 abzuweisen.
def test_bekannter_unbeantworteter_turn_passiert_das_gate():
    store = InMemoryStateStore()
    store.save(SessionState(
        "s1", "0.1", paket_name="toy_prozess", status=SessionStatus.FERTIG,
        processed_message_ids={"mx"}, raw_log=[("mx", "hallo")],
        company_id=MANDANT,
    ))
    antwort = _turn(_client(store=store), "mx", "hallo")
    assert antwort.status_code == 200
    # Doppel-Crash-Fall: es existiert keine Antwort -> Vertrags-Fallback.
    assert antwort.json()["status"] == "fehler_fortsetzbar"


class _BarrierenLLM(FakeLLM):
    """Hält jeden Turn im LLM-Aufruf fest, bis ein zweiter dort ankommt.

    Ohne Serialisierung stehen damit garantiert beide Turns gleichzeitig
    zwischen Roh- und Final-Save — einer verliert den Versions-Wettlauf.
    Mit Serialisierung kommt der zweite nie an: die Barriere läuft in ihren
    Timeout, bricht, und beide Turns laufen nacheinander durch.
    """

    def __init__(self) -> None:
        super().__init__()
        self.barriere = threading.Barrier(2, timeout=0.5)

    def extract(self, message, package, state):
        try:
            self.barriere.wait()
        except threading.BrokenBarrierError:
            pass
        return super().extract(message, package, state)


def test_nebenlaeufige_turns_derselben_session_serialisiert():
    store = InMemoryStateStore()
    app = create_app(store, _BarrierenLLM(), TOY_PROZESS, company_id=MANDANT)
    ergebnisse: dict[str, object] = {}

    def sende(mid: str) -> None:
        try:
            ergebnisse[mid] = TestClient(app).post("/turn", json={
                "session_id": "s1", "message_id": mid, "message": "hallo",
            }).status_code
        except Exception as fehler:   # ohne Lock: StaleStateError aus dem Kern
            ergebnisse[mid] = repr(fehler)

    threads = [threading.Thread(target=sende, args=(m,)) for m in ("ma", "mb")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert ergebnisse == {"ma": 200, "mb": 200}
    st = store.load("s1")
    assert st.rounds == 2
    assert st.processed_message_ids == {"ma", "mb"}


# Leere IDs sind keine gültigen Schlüssel (Session-Bindung, Idempotenz) —
# sie dürfen gar nicht erst in den Kern laufen.
def test_leere_message_id_wird_abgewiesen():
    assert _turn(_client(), "", "Hallo").status_code == 422


# Die Produktions-Verdrahtung braucht einen Aufhaenger fuers Herunterfahren
# (Store schliessen) — die Factory reicht ihn nur durch.
def test_lifespan_wird_durchgereicht():
    zustand = {"laeuft": False}

    @asynccontextmanager
    async def _lifespan(app):
        zustand["laeuft"] = True
        yield
        zustand["laeuft"] = False

    app = create_app(InMemoryStateStore(), _fake_llm(), TOY_PROZESS,
                     lifespan=_lifespan, company_id=MANDANT)
    with TestClient(app):
        assert zustand["laeuft"]
    assert not zustand["laeuft"]


# Vor diesem Branch persistierte "frage"-Antworten kennen die Zähler-Keys
# (pflicht_erfasst/pflicht_gesamt) noch nicht. Ein Replay ihrer message_id
# darf nicht mit KeyError/500 scheitern (Legacy-Upgrade-Pfad).
def test_replay_legacy_frage_antwort_ohne_zaehler_liefert_chat_text_ohne_fortschritt():
    store = InMemoryStateStore()
    store.save(SessionState(
        "s1", "0.1", paket_name="toy_prozess", status=SessionStatus.WARTET,
        processed_message_ids={"m1"}, raw_log=[("m1", "hallo")],
        antworten={"m1": {"status": "frage", "payload": {
            "naechste_frage": "Wie heißt der Prozess?", "feld": "prozess_name",
        }}},
        company_id=MANDANT,
    ))
    antwort = _turn(_client(store=store), "m1", "hallo")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["chat_text"] == "Wie heißt der Prozess?"
    assert "✓" not in daten["chat_text"]


# Vor diesem Branch persistierte "fertig"-Antworten kennen weder abschluss_text
# noch die Zähler-Keys. Replay darf nicht mit KeyError/500 scheitern — der
# bestehende Fallback-Dankestext greift (bislang unerreichbarer Code).
def test_replay_legacy_fertig_antwort_ohne_abschluss_text_liefert_fallback():
    store = InMemoryStateStore()
    store.save(SessionState(
        "s1", "0.1", paket_name="toy_prozess", status=SessionStatus.FERTIG,
        processed_message_ids={"m1"}, raw_log=[("m1", "hallo")],
        antworten={"m1": {"status": "fertig", "payload": {
            "felder": {}, "vollstaendigkeit": 1.0, "ungeloeste_felder": [],
            "schema_version": "0.1",
        }}},
        company_id=MANDANT,
    ))
    antwort = _turn(_client(store=store), "m1", "hallo")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["chat_text"] == "Danke! Das Interview ist abgeschlossen."
    assert "✓" not in daten["chat_text"]


def test_abbruch_liefert_200_mit_festem_text():
    client = TestClient(create_app(InMemoryStateStore(), FakeLLM(), IDENT_PAKET,
                                   company_id=MANDANT))
    _turn(client, "m1", "keine ahnung")
    antwort = _turn(client, "m2", "immer noch nicht")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "abgebrochen_ohne_identitaet"
    assert antwort.json()["chat_text"] == ABBRUCH_TEXT


def test_neue_nachricht_nach_abbruch_wird_abgewiesen():
    client = TestClient(create_app(InMemoryStateStore(), FakeLLM(), IDENT_PAKET,
                                   company_id=MANDANT))
    _turn(client, "m1", "a")
    _turn(client, "m2", "b")
    assert _turn(client, "m3", "c").status_code == 409


def test_abbruch_replay_liefert_dieselbe_antwort():
    client = TestClient(create_app(InMemoryStateStore(), FakeLLM(), IDENT_PAKET,
                                   company_id=MANDANT))
    _turn(client, "m1", "a")
    erst = _turn(client, "m2", "b").json()
    assert _turn(client, "m2", "b").json() == erst


def test_fremder_mandant_bekommt_409_mandant_konflikt():
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess",
                            company_id=MANDANT_B))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    antwort = _turn(client, "m1", "hallo")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "mandant_konflikt"


def test_fremder_mandant_hat_vorrang_vor_schema_pruefung():
    # Pinnt die Reihenfolge (R12-I1): laeuft der Schema-Check vor dem
    # Mandanten-Guard, bekaeme ein fremder Mandant hier "schema_version_passt_
    # nicht" statt "mandant_konflikt" — ein schwaecheres Orakel.
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess",
                            company_id=MANDANT_B))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    antwort = _turn(client, "m1", "hallo", schema_version="99.9")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "mandant_konflikt"


def test_fremder_mandant_wird_auch_bei_terminaler_session_abgewiesen():
    # Spec K4: A->B muss aktiv UND terminal greifen — ausdruecklich auch ohne
    # bestehende Profil-Bindung (R12-I1).
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess",
                            company_id=MANDANT_B, status=SessionStatus.FERTIG,
                            processed_message_ids={"m1"}, raw_log=[("m1", "hallo")],
                            antworten={"m1": {"status": "fertig", "payload": {}}}))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    for mid in ("m1", "m2"):                       # Replay UND neue Nachricht
        antwort = _turn(client, mid, "hallo")
        assert antwort.status_code == 409
        assert antwort.json()["detail"] == "mandant_konflikt"


def test_alt_session_ohne_company_id_bekommt_409():
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess",
                            status=SessionStatus.FERTIG,
                            processed_message_ids={"m1"}, raw_log=[("m1", "hallo")],
                            antworten={"m1": {"status": "fertig", "payload": {}}}))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    assert _turn(client, "m1", "hallo").status_code == 409


ANFRAGE = "A-2026-01"


def test_fremde_anfrage_bekommt_409_anfrage_konflikt():
    store = InMemoryStateStore()
    alt = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                company_id=MANDANT, anfrage_id=ANFRAGE))
    assert _turn(alt, "m1", "Der Prozess heißt Urlaubsantrag").status_code == 200
    neu = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                company_id=MANDANT, anfrage_id="A-2026-02"))
    antwort = _turn(neu, "m2", "Ausgelöst durch einen Antrag")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"


def test_dieselbe_anfrage_setzt_die_sitzung_ueber_mehrere_turns_fort():
    # Pinnt, dass der Dienst die Anfrage beim ersten Turn in die Sitzung schreibt
    # (sonst wiese der Guard schon den zweiten Turn derselben Anfrage ab).
    store = InMemoryStateStore()
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT, anfrage_id=ANFRAGE))
    assert _turn(client, "m1", "Der Prozess heißt Urlaubsantrag").status_code == 200
    assert _turn(client, "m2", "Ausgelöst durch einen Antrag").status_code == 200
    assert store.load("s1").anfrage_id == ANFRAGE


class _StoreMitAnfrageWechselImKern(InMemoryStateStore):
    """Der zweite load MIT Zustand (der des Kerns, nach dem Gate der API) liefert
    eine fremde Anfrage — nur so ist der Kern-Guard hinter dem API-Guard messbar."""

    def __init__(self) -> None:
        super().__init__()
        self.geladen = 0

    def load(self, session_id: str):
        state = super().load(session_id)
        if state is None:
            return None
        self.geladen += 1
        if self.geladen == 2:
            state.anfrage_id = "A-FREMD"
        return state


def test_anfrage_konflikt_des_kerns_wird_zu_409_anfrage_konflikt():
    store = _StoreMitAnfrageWechselImKern()
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT, anfrage_id=ANFRAGE))
    assert _turn(client, "m1", "Der Prozess heißt Urlaubsantrag").status_code == 200
    antwort = _turn(client, "m2", "Ausgelöst durch einen Antrag")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"


def test_alt_sitzung_ohne_anfrage_wird_abgewiesen():
    store = InMemoryStateStore()
    store.save(SessionState("s1", TOY_PROZESS.schema_version, paket_name=TOY_PROZESS.name,
                            company_id=MANDANT))
    client = TestClient(create_app(store, _fake_llm(), TOY_PROZESS,
                                   company_id=MANDANT, anfrage_id=ANFRAGE))
    antwort = _turn(client, "m1", "hallo")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"


def test_recovery_replay_wechselt_nie_die_anfrage():
    # Der Paket-Guard laesst einen abweichenden ctx-Hash beim terminalen Replay
    # passieren (darf_recovery_replay) — der Anfrage-Guard darf das NICHT.
    store = InMemoryStateStore()
    llm = FakeLLM()
    alt = TestClient(create_app(store, llm, IDENT_PAKET, company_id=MANDANT,
                                anfrage_id=ANFRAGE))
    _turn(alt, "m1", "a")
    _turn(alt, "m2", "b")
    neues_paket = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    neu = TestClient(create_app(store, llm, neues_paket, company_id=MANDANT,
                                anfrage_id="A-2026-02"))
    antwort = _turn(neu, "m2", "b", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"


def test_recovery_replay_mit_alter_schema_version_geht_durch():
    store = InMemoryStateStore()
    llm = FakeLLM()
    client_alt = TestClient(create_app(store, llm, IDENT_PAKET, company_id=MANDANT))
    _turn(client_alt, "m1", "a")
    erst = _turn(client_alt, "m2", "b").json()

    neues_paket = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    client_neu = TestClient(create_app(store, llm, neues_paket, company_id=MANDANT))
    antwort = _turn(client_neu, "m2", "b", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == erst["status"]


def test_recovery_replay_mit_falscher_schema_version_bleibt_409():
    store = InMemoryStateStore()
    llm = FakeLLM()
    client_alt = TestClient(create_app(store, llm, IDENT_PAKET, company_id=MANDANT))
    _turn(client_alt, "m1", "a")
    _turn(client_alt, "m2", "b")
    neues_paket = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    client_neu = TestClient(create_app(store, llm, neues_paket, company_id=MANDANT))
    antwort = _turn(client_neu, "m2", "b", schema_version="1.1+ctx-cccccccccccccccc")
    assert antwort.status_code == 409


# Die Post-Sweep-Hinweise haengen an EINEM Feld des gespeicherten Profils. Diese
# Faelle brauchen keine Datenbank — deshalb hier und nicht in test_api_profil.py,
# das ohne BC1_TEST_DB_DSN komplett skippt (Codex-Review 03.09.).
def test_unbekannter_befund_status_erzeugt_keinen_hinweis():
    # Der Writer schreibt heute nur 'gueltig' oder 'ungeloest'. Kommt je ein
    # dritter Status dazu, waere ein zugeordneter Text eine falsche Aussage
    # gegenueber dem Nutzer — dann lieber gar kein Hinweis.
    payload = {"befunde": {"snn_entfernt": [
        {"feld": "focus_step_systems", "anzahl": 1, "feld_status_danach": "neu"}]}}
    assert _sweep_hinweise(payload) == ""


def test_overlay_laesst_die_kern_eigenen_schluessel_unangetastet():
    # Spec K3.3 zieht die Grenze: abschluss_text und schema_version kommen aus
    # der Kern-Antwort, nie aus der DB. Ein zusaetzlich eingeschleuster
    # Schluessel waere durch keinen Verhaltenstest zu fangen (beide Werte sind
    # in Kern und DB gleich, Codex-Review 03.09.) — daher als Vertrag gepinnt.
    assert "schema_version" not in OVERLAY_SCHLUESSEL
    assert "abschluss_text" not in OVERLAY_SCHLUESSEL


class _WriterOhneDb:
    """Der Gate-Anstoss haengt nur an 'Writer verdrahtet + fertig' — die DB-Seite
    prueft test_api_profil.py."""

    def reconcile(self, state, antwort):
        return None


class _GateMelder:
    def __init__(self, fehler=None):
        self.aufrufe = 0
        self.anfragen: list[str] = []
        self._fehler = fehler

    def ziehe_gate_nach(self, anfrage_id):
        self.aufrufe += 1
        self.anfragen.append(anfrage_id)
        if self._fehler is not None:
            raise self._fehler
        return [ANFRAGE]


def _gate_client(melder, writer=_WriterOhneDb()):
    return TestClient(create_app(InMemoryStateStore(), _fake_llm(), TOY_PROZESS,
                                 company_id=MANDANT, anfrage_id=ANFRAGE,
                                 writer=writer, melder=melder))


def _bis_fertig(client):
    _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    return _turn(client, "m3", "Etwa 100 mal pro Jahr")


def test_fertig_mit_writer_zieht_das_gate_genau_einmal_nach():
    melder = _GateMelder()
    antwort = _bis_fertig(_gate_client(melder))
    assert antwort.json()["status"] == "fertig"
    assert melder.aufrufe == 1


def test_gate_im_hintergrund_reicht_die_eigene_anfrage_durch():
    melder = _GateMelder()
    _bis_fertig(_gate_client(melder))
    assert melder.anfragen == [ANFRAGE]


def test_gate_wird_erst_nach_der_antwort_angestossen():
    # Der Chat wartet nie auf BC0 (Spec B4, Abschnitt 4). Der TestClient laesst
    # Hintergrundaufgaben vor post() laufen und zeigt die Reihenfolge deshalb nicht —
    # der letzte Turn geht hier direkt gegen die ASGI-Schnittstelle.
    import asyncio
    import json

    ereignisse: list[str] = []

    class _ReihenfolgeMelder:
        def ziehe_gate_nach(self, anfrage_id):
            ereignisse.append("gate")
            return []

    app = create_app(InMemoryStateStore(), _fake_llm(), TOY_PROZESS,
                     company_id=MANDANT, anfrage_id=ANFRAGE,
                     writer=_WriterOhneDb(), melder=_ReihenfolgeMelder())
    client = TestClient(app)
    _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    rumpf = json.dumps({"session_id": "s1", "message_id": "m3",
                        "message": "Etwa 100 mal pro Jahr"}).encode()
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "POST", "path": "/turn", "raw_path": b"/turn",
             "query_string": b"", "root_path": "", "scheme": "http",
             "server": ("testserver", 80), "client": ("testclient", 5),
             "headers": [(b"content-type", b"application/json"),
                         (b"content-length", str(len(rumpf)).encode())]}

    async def empfangen():
        return {"type": "http.request", "body": rumpf, "more_body": False}

    async def senden(nachricht):
        if nachricht["type"] == "http.response.body" and not nachricht.get("more_body"):
            ereignisse.append("antwort_gesendet")

    asyncio.run(app(scope, empfangen, senden))
    assert ereignisse == ["antwort_gesendet", "gate"]


def test_zwischenstand_zieht_das_gate_nicht_nach():
    melder = _GateMelder()
    _turn(_gate_client(melder), "m1", "Der Prozess heißt Urlaubsantrag")
    assert melder.aufrufe == 0


def test_ohne_writer_wird_nichts_eingefroren_und_nichts_nachgezogen():
    melder = _GateMelder()
    _bis_fertig(_gate_client(melder, writer=None))
    assert melder.aufrufe == 0


def _api_log(caplog):
    return [r for r in caplog.records if r.name == "bc1_service.api"]


def test_ohne_melder_kein_aufruf_und_keine_logzeile(caplog):
    with caplog.at_level(logging.INFO, logger="bc1_service.api"):
        antwort = _bis_fertig(_gate_client(None))
    assert antwort.json()["status"] == "fertig"
    assert _api_log(caplog) == []


def test_gescheitertes_gate_laesst_die_antwort_unberuehrt_und_warnt(caplog):
    melder = _GateMelder(Bc0MeldungFehler("BC0 antwortet auf 'Gate nachziehen' mit 500: x"))
    with caplog.at_level(logging.WARNING, logger="bc1_service.api"):
        antwort = _bis_fertig(_gate_client(melder))
    assert antwort.status_code == 200 and antwort.json()["status"] == "fertig"
    assert [r.getMessage() for r in _api_log(caplog)] == [MELDUNG_GATE_FEHLGESCHLAGEN.format(
        grund="BC0 antwortet auf 'Gate nachziehen' mit 500: x",
        anfrage_id=ANFRAGE, company_id=MANDANT)]


def test_unerwartete_ausnahme_im_hintergrund_nennt_nur_die_klasse(caplog):
    melder = _GateMelder(AttributeError("interna mit geheimnis"))
    with caplog.at_level(logging.WARNING, logger="bc1_service.api"):
        antwort = _bis_fertig(_gate_client(melder))
    assert antwort.status_code == 200
    eintraege = _api_log(caplog)
    assert len(eintraege) == 1
    assert "AttributeError" in eintraege[0].getMessage()
    assert "geheimnis" not in eintraege[0].getMessage()


def test_replay_des_abschlusses_zieht_erneut_nach():
    melder = _GateMelder()
    client = _gate_client(melder)
    _bis_fertig(client)
    assert _turn(client, "m3", "Etwa 100 mal pro Jahr").status_code == 200
    assert melder.aufrufe == 2


def test_nachgezogenes_gate_wird_mit_den_gesetzten_anfragen_geloggt(caplog):
    with caplog.at_level(logging.INFO, logger="bc1_service.api"):
        _bis_fertig(_gate_client(_GateMelder()))
    assert [r.getMessage() for r in _api_log(caplog)] == [
        f"Gate bei BC0 nachgezogen (Anfrage {ANFRAGE}): auf am_gate gesetzt: {ANFRAGE}"]


def test_nachgezogenes_gate_ohne_gesetzte_anfrage_sagt_keine(caplog):
    class _NichtsZuTun(_GateMelder):
        def ziehe_gate_nach(self, anfrage_id):
            return []

    with caplog.at_level(logging.INFO, logger="bc1_service.api"):
        _bis_fertig(_gate_client(_NichtsZuTun()))
    assert [r.getMessage() for r in _api_log(caplog)] == [
        f"Gate bei BC0 nachgezogen (Anfrage {ANFRAGE}): auf am_gate gesetzt: keine"]
