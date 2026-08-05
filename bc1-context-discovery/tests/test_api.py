import pytest
from fastapi.testclient import TestClient

from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.types import SessionState
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
    assert a1.json()["chat_text"] == a1.json()["payload"]["naechste_frage"]
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    a3 = _turn(client, "m3", "Etwa 100 mal pro Jahr")
    assert a3.json()["status"] == "fertig"
    assert a3.json()["payload"]["vollstaendigkeit"] == 1.0
    assert "abgeschlossen" in a3.json()["chat_text"]


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


def test_paket_guard_wird_als_409_gemappt():
    store = InMemoryStateStore()
    store.save(SessionState("s9", "9.9", paket_name="fremdes_paket"))
    antwort = _turn(_client(store=store), "m1", "Hallo", session="s9")
    assert antwort.status_code == 409


def test_prozesse_ohne_snapshot_404():
    assert _client().get("/prozesse").status_code == 404
