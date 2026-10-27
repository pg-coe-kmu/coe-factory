"""Schritt 1 (27.10.2026): Zugangsschlüssel vor allen Endpunkten.

Plan: design/Plan-Zugang-und-Anfragepruefung.md (Z1–Z7). BC0s Backend schickt den
Schlüssel im Header X-BC1-Zugang; ohne ihn antwortet der Dienst 401 ohne Inhalt.
"""
import logging

from fastapi.testclient import TestClient

from bc1_core.llm import FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_service.api import create_app

MANDANT = "11111111-1111-1111-1111-111111111111"
ZUGANG = "z" * 43


def _client(zugang=ZUGANG) -> TestClient:
    return TestClient(create_app(InMemoryStateStore(), FakeLLM(), TOY_PROZESS,
                                 company_id=MANDANT, zugang=zugang))


def test_ohne_header_antwortet_der_dienst_401_ohne_inhalt():
    antwort = _client().get("/gesundheit")
    assert antwort.status_code == 401
    assert antwort.content == b""


def test_richtiger_schluessel_laesst_durch():
    antwort = _client().get("/gesundheit", headers={"X-BC1-Zugang": ZUGANG})
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "ok"


def test_richtiger_schluessel_laesst_auch_turn_durch():
    antwort = _client().post("/turn", headers={"X-BC1-Zugang": ZUGANG}, json={
        "session_id": "s1", "message_id": "m1", "message": "Hallo",
        "anfrage_id": "A-2026-01", "company_id": MANDANT})
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "frage"


def test_falscher_schluessel_antwortet_401():
    antwort = _client().get("/gesundheit", headers={"X-BC1-Zugang": "y" * 43})
    assert antwort.status_code == 401
    assert antwort.content == b""


def test_fremde_zeichen_im_schluessel_geben_401_statt_500():
    # Starlette dekodiert Header als latin-1; compare_digest auf str nähme nur ASCII an
    # und würfe sonst einen TypeError (= 500). Darum der Vergleich auf Bytes.
    antwort = _client().get("/gesundheit", headers={"X-BC1-Zugang": b"\xe4" * 43})
    assert antwort.status_code == 401


def test_auch_die_doku_endpunkte_brauchen_den_schluessel():
    client = _client()
    for pfad in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(pfad).status_code == 401, pfad


def test_ohne_schluessel_am_dienst_prueft_niemand():
    # Nur Test-Verdrahtung (Plan Z6): main.py übergibt den Schlüssel immer.
    assert _client(zugang=None).get("/gesundheit").status_code == 200


def test_abgewiesener_zugriff_steht_im_protokoll_ohne_den_gesendeten_wert(caplog):
    caplog.set_level(logging.WARNING, logger="bc1.api")
    falsch = "geraten-" + "q" * 40
    _client().get("/gesundheit", headers={"X-BC1-Zugang": falsch})
    _client().post("/turn", json={})
    zeilen = [r.getMessage() for r in caplog.records if r.name == "bc1.api"]
    assert zeilen == ["zugang_verweigert pfad=/gesundheit grund=falsch",
                      "zugang_verweigert pfad=/turn grund=fehlt"]
    assert all(falsch not in z and ZUGANG not in z for z in zeilen)


def test_pfad_im_protokoll_kann_keine_zeile_faelschen(caplog):
    # Den Pfad wählt der Aufrufer: ein Zeilenumbruch fälschte sonst eine zweite Zeile.
    caplog.set_level(logging.WARNING, logger="bc1.api")
    _client().get("/a%0Azugang_verweigert pfad=/x grund=fehlt")
    zeilen = [r.getMessage() for r in caplog.records if r.name == "bc1.api"]
    assert len(zeilen) == 1
    assert "\n" not in zeilen[0] and " pfad=/x" not in zeilen[0]
