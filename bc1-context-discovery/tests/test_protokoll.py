"""P5 (#271): Betriebsprotokoll Teil 1 — genau eine Zeile je /turn, ohne Gespraechsinhalte."""
import logging
import re

import pytest
from fastapi.testclient import TestClient

from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore, KorrupterStateError, StaleStateError
from bc1_service.api import FEHLER_TEXTE, _protokollwert, create_app
from bc1_service.profil_writer import ProfilWriteError

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
    # Schritt 1: Anfrage und Mandant gehen immer mit (Pflichtfelder).
    return client.post("/turn", headers=headers or {}, json={
        "session_id": session, "message_id": mid, "message": text,
        "anfrage_id": "A-2026-01", "company_id": MANDANT})


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


def test_409_schreibt_eine_zeile_mit_dem_grund_als_status(caplog):
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
    assert treffer["http"] == "409" and treffer["status"] == "session_abgeschlossen"
    assert treffer["message"] == "m4"


# Schritt 1: auch die abgewiesene fremde Anfrage hat genau ihre eine Turn-Zeile.
def test_fremde_anfrage_schreibt_eine_zeile_mit_anfrage_passt_nicht(caplog):
    client = TestClient(create_app(InMemoryStateStore(), _llm(), TOY_PROZESS,
                                   company_id=MANDANT, anfrage_id="A-2026-02"),
                        raise_server_exceptions=False)
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    assert _turn(client, "m1", GEHEIM).status_code == 409
    zeilen = _zeilen(caplog)
    assert len(zeilen) == 1
    treffer = ZEILE.match(zeilen[0].getMessage())
    assert treffer["http"] == "409" and treffer["status"] == "anfrage_passt_nicht"


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


# B7 Teil 2 (#266): ein Logger-Baum — der Betrieb stellt nur `bc1` ein, nicht zwei Bäume.
def test_alle_bc1_logger_haengen_am_baum_bc1():
    from bc1_service import api, bc0_meldungen, profil_writer
    assert (api.log.name, bc0_meldungen.log.name, profil_writer.log.name) == (
        "bc1.api", "bc1.bc0", "bc1.writer")


class _AntwortFaelltAus(FakeLLM):
    def antworte(self, kontext):
        raise RuntimeError("Ausfall")


# Jede Kernzeile eines Turns trägt dessen Kennung — auch auf dem Fehlerpfad.
@pytest.mark.parametrize("llm_faellt_aus", [False, True])
def test_korrelation_erreicht_den_kern(caplog, llm_faellt_aus):
    caplog.set_level(logging.INFO, logger="bc1.kern")
    llm = _AntwortFaelltAus() if llm_faellt_aus else _llm()
    client = TestClient(create_app(InMemoryStateStore(), llm, TOY_PROZESS,
                                   company_id=MANDANT))
    _turn(client, "m1", GEHEIM, headers={"X-Correlation-ID": "k-4711"})
    zeilen = [r.getMessage() for r in caplog.records if r.name == "bc1.kern"]
    assert len(zeilen) >= 2, zeilen
    assert all("korrelation=k-4711" in zeile for zeile in zeilen), zeilen


# Starlettes ServerErrorMiddleware wirft jede Ausnahme nach dem 500 erneut, uvicorn
# schreibt dann den Traceback — dessen Text kann Inhalte tragen. raise_server_exceptions
# bleibt deshalb hier an: nichts darf bis zum Server durchdringen.
def test_unerwartete_ausnahme_erreicht_den_server_nicht():
    client = TestClient(create_app(_ExplodierenderStore(), _llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    antwort = _turn(client, "m1", GEHEIM)
    assert antwort.status_code == 500
    assert antwort.json() == {"detail": "interner_fehler",
                              "chat_text": FEHLER_TEXTE["interner_fehler"]}
    assert antwort.headers["X-Correlation-ID"]


def test_unerwartete_ausnahme_wird_mit_klasse_protokolliert(caplog):
    caplog.set_level(logging.INFO, logger="bc1.api")
    client = TestClient(create_app(_ExplodierenderStore(), _llm(), TOY_PROZESS,
                                   company_id=MANDANT))
    antwort = _turn(client, "m1", GEHEIM)
    eintraege = [r for r in caplog.records if r.name == "bc1.api"]
    assert [r.getMessage() for r in eintraege] == [
        f"unerwartete_ausnahme korrelation={antwort.headers['X-Correlation-ID']} "
        "klasse=RuntimeError"]
    assert eintraege[0].levelno == logging.ERROR
    assert eintraege[0].exc_info is None


# B7 Teil 2 (E11): ohne den Grund waere ein verlorener Schreibwettlauf nicht von einer
# abgeschlossenen Sitzung oder einem fremden Mandanten zu unterscheiden.
def test_abgewiesener_turn_nennt_den_grund_im_status(caplog):
    client = _client()
    _turn(client, "m1", GEHEIM)
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    _turn(client, "m3", "Etwa 100 mal pro Jahr")
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    _turn(client, "m4", "noch etwas")
    treffer = ZEILE.match(_zeilen(caplog)[0].getMessage())
    assert treffer["http"] == "409" and treffer["status"] == "session_abgeschlossen"


class _KonfliktStore(InMemoryStateStore):
    def save(self, state):
        raise StaleStateError("verlorener Schreibwettlauf")


class _ScheiternderWriter:
    def reconcile(self, stand, antwort):
        raise ProfilWriteError("Abschluss nicht gespeichert")


# Gesamtprüfung M1: der Grund je Fehlerart — gerade der Store-Konflikt war der Anlass
# für E11 (sonst nicht von anderen 409 zu unterscheiden).
@pytest.mark.parametrize("store, writer, http, status", [
    (_KonfliktStore(), None, "409", "gleichzeitige_anfrage"),
    (_BeschaedigterStore(), None, "500", "sitzung_beschaedigt"),
    (InMemoryStateStore(), _ScheiternderWriter(), "503", "profil_write_fehlgeschlagen"),
])
def test_turn_zeile_nennt_den_grund_je_fehlerart(caplog, store, writer, http, status):
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    client = TestClient(create_app(store, _llm(), TOY_PROZESS, company_id=MANDANT,
                                   writer=writer), raise_server_exceptions=False)
    _turn(client, "m1", GEHEIM)
    treffer = ZEILE.match(_zeilen(caplog)[0].getMessage())
    assert (treffer["http"], treffer["status"]) == (http, status)


def test_unerwartete_ausnahme_steht_als_interner_fehler_in_der_turn_zeile(caplog):
    caplog.set_level(logging.INFO, logger="bc1.dienst")
    _turn(_client(store=_ExplodierenderStore()), "m1", GEHEIM)
    treffer = ZEILE.match(_zeilen(caplog)[0].getMessage())
    assert treffer["http"] == "500" and treffer["status"] == "interner_fehler"
