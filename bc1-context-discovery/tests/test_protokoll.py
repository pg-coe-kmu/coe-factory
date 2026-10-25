"""P5 (#271): Betriebsprotokoll Teil 1 — genau eine Zeile je /turn, ohne Gespraechsinhalte."""
import logging
import re

from fastapi.testclient import TestClient

from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore, KorrupterStateError
from bc1_service.api import _protokollwert, create_app

MANDANT = "11111111-1111-1111-1111-111111111111"
GEHEIM = "Geheimwort Nordlicht 4711"
ZEILE = re.compile(
    r"^turn korrelation=(?P<korrelation>\S+) session=(?P<session>\S+) "
    r"message=(?P<message>\S+) http=(?P<http>\d{3}) status=(?P<status>\S+) "
    r"dauer_ms=(?P<dauer>\d+)$")


def _llm() -> FakeLLM:
    return FakeLLM({
        GEHEIM: [ExtractionCandidate("prozess_name", "Nordlicht-Prozess")],
        "Ausgelöst durch einen Antrag": [ExtractionCandidate("ausloeser", "Antrag")],
        "Etwa 100 mal pro Jahr": [ExtractionCandidate("haeufigkeit", "100 mal pro Jahr")],
    })


def _client(store=None) -> TestClient:
    return TestClient(create_app(store or InMemoryStateStore(), _llm(), TOY_PROZESS,
                                 company_id=MANDANT), raise_server_exceptions=False)


def _turn(client, mid, text, session="s1", headers=None):
    return client.post("/turn", headers=headers or {}, json={
        "session_id": session, "message_id": mid, "message": text})


def _zeilen(caplog) -> list:
    return [r for r in caplog.records if r.name == "bc1.dienst"]


def test_erfolgreicher_turn_schreibt_genau_eine_zeile(caplog):
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    antwort = _turn(_client(), "m1", GEHEIM)
    assert antwort.status_code == 200
    zeilen = _zeilen(caplog)
    assert len(zeilen) == 1
    treffer = ZEILE.match(zeilen[0].getMessage())
    assert treffer, zeilen[0].getMessage()
    assert treffer["session"] == "s1" and treffer["message"] == "m1"
    assert treffer["http"] == "200" and treffer["status"] == "frage"
    assert zeilen[0].levelno == logging.INFO


def test_protokoll_enthaelt_weder_nachricht_noch_wert_noch_frage(caplog):
    caplog.set_level(logging.DEBUG)
    antwort = _turn(_client(), "m1", GEHEIM).json()
    frage = antwort["payload"]["naechste_frage"]
    protokoll = "\n".join(r.getMessage() for r in caplog.records)
    for verboten in (GEHEIM, "Nordlicht", "4711", "Nordlicht-Prozess", frage,
                     antwort["chat_text"]):
        assert verboten not in protokoll


def test_409_schreibt_eine_zeile_mit_strich_als_status(caplog):
    client = _client()
    _turn(client, "m1", GEHEIM)
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    _turn(client, "m3", "Etwa 100 mal pro Jahr")
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    antwort = _turn(client, "m4", "noch etwas")
    assert antwort.status_code == 409
    zeilen = _zeilen(caplog)
    assert len(zeilen) == 1
    treffer = ZEILE.match(zeilen[0].getMessage())
    assert treffer["http"] == "409" and treffer["status"] == "-"
    assert treffer["message"] == "m4"


def test_mitgeschickte_korrelation_steht_in_zeile_und_antwort(caplog):
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    antwort = _turn(_client(), "m1", GEHEIM, headers={"X-Correlation-ID": "abc"})
    assert antwort.headers["X-Correlation-ID"] == "abc"
    assert ZEILE.match(_zeilen(caplog)[0].getMessage())["korrelation"] == "abc"


def test_ohne_korrelation_wird_eine_erzeugt_und_zurueckgegeben(caplog):
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    antwort = _turn(_client(), "m1", GEHEIM)
    erzeugt = antwort.headers["X-Correlation-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", erzeugt)
    assert ZEILE.match(_zeilen(caplog)[0].getMessage())["korrelation"] == erzeugt


def test_korrelation_kommt_auch_bei_einem_fehler_zurueck():
    client = _client()
    for mid, text in (("m1", GEHEIM), ("m2", "Ausgelöst durch einen Antrag"),
                      ("m3", "Etwa 100 mal pro Jahr")):
        _turn(client, mid, text)
    antwort = _turn(client, "m4", "noch etwas", headers={"X-Correlation-ID": "xyz"})
    assert antwort.status_code == 409
    assert antwort.headers["X-Correlation-ID"] == "xyz"


def test_unlesbare_korrelation_wird_ersetzt(caplog):
    # Das Format ist key=value je Zeile: ein Leerzeichen oder Zeilenumbruch im
    # Header koennte sonst Felder oder ganze Zeilen faelschen.
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    antwort = _turn(_client(), "m1", GEHEIM,
                    headers={"X-Correlation-ID": "abc http=200 status=fertig"})
    erzeugt = antwort.headers["X-Correlation-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", erzeugt)
    assert ZEILE.match(_zeilen(caplog)[0].getMessage())["korrelation"] == erzeugt


class _BeschaedigterStore(InMemoryStateStore):
    def load(self, session_id):
        raise KorrupterStateError(f"Sitzung {session_id}: nicht lesbar (KeyError)")


def test_500_wird_als_error_protokolliert(caplog):
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    antwort = _turn(_client(store=_BeschaedigterStore()), "m1", GEHEIM)
    assert antwort.status_code == 500
    zeilen = _zeilen(caplog)
    assert len(zeilen) == 1
    assert ZEILE.match(zeilen[0].getMessage())["http"] == "500"
    assert zeilen[0].levelno == logging.ERROR


class _ExplodierenderStore(InMemoryStateStore):
    def load(self, session_id):
        raise RuntimeError("unerwartet " + GEHEIM)


def test_unerwartete_ausnahme_gibt_eine_error_zeile_ohne_inhalt(caplog):
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    antwort = _turn(_client(store=_ExplodierenderStore()), "m1", GEHEIM)
    assert antwort.status_code == 500
    zeilen = _zeilen(caplog)
    assert len(zeilen) == 1
    assert ZEILE.match(zeilen[0].getMessage())["http"] == "500"
    assert zeilen[0].levelno == logging.ERROR
    assert zeilen[0].exc_info is None                 # kein Traceback mit Inhalten


def test_fremd_gewaehlte_ids_koennen_keine_felder_faelschen(caplog):
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    _turn(_client(), "m1 http=200", GEHEIM, session="x status=fertig\nturn")
    # Seit der Härtung (25.10.) scheitert so eine Anfrage am Kennungsmuster (422,
    # test_api) und erzeugt gar keine Dienstzeile mehr.
    assert _zeilen(caplog) == []


# Die Maskierung bleibt als Verteidigung in der Tiefe, falls das Kennungsmuster je fällt;
# über /turn ist sie seit der Härtung nicht mehr zu erreichen, deshalb direkt geprüft.
def test_protokollwert_maskiert_fremde_zeichen():
    assert _protokollwert("x status=fertig\nturn") == "x?status?fertig?turn"
