import threading
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore, StaleStateError
from bc1_core.types import SessionState, SessionStatus
from bc1_service.api import create_app


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
                                 llm or _fake_llm(), TOY_PROZESS))


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
    store.save(SessionState("s9", "9.9", paket_name="fremdes_paket"))
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
    app = create_app(store, _BarrierenLLM(), TOY_PROZESS)
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
                     lifespan=_lifespan)
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
    ))
    antwort = _turn(_client(store=store), "m1", "hallo")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["chat_text"] == "Danke! Das Interview ist abgeschlossen."
    assert "✓" not in daten["chat_text"]
