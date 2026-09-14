# -*- coding: utf-8 -*-
"""Schema v2.6 — Einfrieren statt Sperren: die App-Seite.

Was hier geprueft wird, laeuft im SQLite-Modus. Die Datenbankseite (Trigger,
Historie, stand_zum, Paket) laeuft nur auf PostgreSQL und ist in
``pruefung_v2.6_historie_und_paket.sql`` mit Erwartungswerten belegt.

Drei Aussagen:
  1. Eine abgeschlossene Erhebung nimmt keine Bewertung mehr an — die App sagt
     es mit 400 und einem Satz, bevor der Datenbank-Trigger es mit einem
     Constraint-Fehler sagen muesste.
  2. Der Widerruf einer Freigabe ist ein neues Ereignis, mit Grund, und danach
     ist der Teilprozess wieder entscheidbar.
  3. Die PostgreSQL-only-Endpunkte antworten im SQLite-Modus mit 501 und
     sagen, warum — statt mit einem Tabellenfehler.
"""
import os, sys, datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "_v26.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "v26-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("v26-admin@bc0.test", "V26-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "v26-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    cid = str(client.post("/api/companies", json={"name": "Frost GmbH", "kps": [1]}).json()["id"])
    client.put("/api/companies/" + cid + "/entitaeten", json={
        "personen": [{"name": "Ida Eigner", "funktion": "Leitung"}], "zuordnungen": []})
    person = client.get("/api/companies/" + cid + "/entitaeten").json()["personen"][0]["person_id"]
    kp = sorted(client.get("/api/companies/" + cid).json()["processes"].keys())[0]
    client.put("/api/companies/" + cid + "/entitaeten", json={"zuordnungen": [
        {"process_id": kp, "person_id": person, "funktion": "eigner"}]})
    items = {str(n): {"stufe": 3, "beleg": "Beleg %d" % n} for n in range(1, 31)}
    assert client.post("/api/companies/" + cid + "/rating",
                       json={"key": kp + ".TP-1", "items": items}).status_code == 200
    return cid


def _tp(client, cid):
    return sorted(client.get("/api/companies/" + cid).json()["processes"].keys())[0] + ".TP-1"


def _punkte():
    punkte = []
    for name, _b, _e, _q, guete_noetig, _p, aktiv, _r in anwendung.GATE_PRUEFPUNKTE:
        if aktiv:
            punkte.append({"pruefpunkt": name, "vorhanden_pct": 100,
                           "guete": "belegt" if guete_noetig else None,
                           "bestaetigt": True, "anmerkung": None})
    return punkte


# --------------------------------------------------------------------------- #
# 1. Abgeschlossen heisst abgeschlossen
# --------------------------------------------------------------------------- #
def test_abgeschlossene_erhebung_nimmt_keine_bewertung_mehr_an(client, mandant):
    """Bis v2.7 antwortete die App hier mit 400 (E-JJJJ-MM: eine Erhebung je Monat).
    Seit v2.8 gilt die Regel des Pakets: Die abgeschlossene Erhebung nimmt nichts
    mehr an — die Bewertung geht in eine NEUE (E-JJJJ-MM-2). Alt bleibt, neu kommt dazu."""
    tp = _tp(client, mandant)
    assert client.post("/api/companies/" + mandant + "/erhebungen",
                       json={"aktion": "abschliessen"}).status_code == 200
    antwort = client.post("/api/companies/" + mandant + "/rating",
                          json={"key": tp, "items": {"1": {"stufe": 5, "beleg": "neu"}}})
    assert antwort.status_code == 200, antwort.text
    heute = datetime.date.today()
    assert antwort.json()["erhebung_id"] == "E-%04d-%02d-2" % (heute.year, heute.month)
    # Die alte Erhebung steht unveraendert — nichts wurde ueberschrieben.
    daten = client.get("/api/companies/" + mandant + "/erhebungen").json()
    alt = [e for e in daten["erhebungen"] if e["erhebung_id"] == "E-%04d-%02d" % (heute.year, heute.month)][0]
    assert alt["status"] == "abgeschlossen" and alt["bewertungen"] == 30


def test_freigabe_beginnt_keine_erhebung(client, mandant):
    """Das Gate liest den massgeblichen Stand; es legt keine Erhebung an."""
    tp = _tp(client, mandant)
    vorher = len(client.get("/api/companies/" + mandant + "/erhebungen").json()["erhebungen"])
    antwort = client.post("/api/companies/" + mandant + "/gate/" + tp, json={
        "ereignis": "freigegeben", "kette_bestaetigt": True, "punkte": _punkte()})
    assert antwort.status_code == 200, antwort.text
    heute = datetime.date.today()
    # massgeblich ist die juengste nicht verworfene — seit dem Test davor die Nacherhebung -2
    assert antwort.json()["erhebung_id"] == "E-%04d-%02d-2" % (heute.year, heute.month)
    nachher = len(client.get("/api/companies/" + mandant + "/erhebungen").json()["erhebungen"])
    assert nachher == vorher, "eine Freigabe darf keine Erhebung anlegen"


# --------------------------------------------------------------------------- #
# 2. Widerruf
# --------------------------------------------------------------------------- #
def test_widerruf_braucht_einen_grund(client, mandant):
    tp = _tp(client, mandant)
    antwort = client.post("/api/companies/" + mandant + "/gate/" + tp + "/widerrufen", json={})
    assert antwort.status_code == 400
    assert "Grund" in antwort.json()["detail"]


def test_widerruf_ist_ein_neues_ereignis_und_macht_wieder_entscheidbar(client, mandant):
    tp = _tp(client, mandant)
    antwort = client.post("/api/companies/" + mandant + "/gate/" + tp + "/widerrufen",
                          json={"grund": "Nacherhebung hat den Reifegrad halbiert."})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["stand"] == "widerrufen"
    bogen = client.get("/api/companies/" + mandant + "/gate/" + tp).json()
    assert bogen["letzter_stand"]["stand"] == "widerrufen"
    assert bogen["letzter_stand"]["grund"].startswith("Nacherhebung")
    zeile = [t for t in client.get("/api/companies/" + mandant + "/gate").json()["teilprozesse"]
             if t["sub_process_id"] == tp][0]
    assert zeile["am_zug"] != "entschieden", "nach dem Widerruf steht der Teilprozess wieder an"


def test_widerruf_ohne_freigabe_scheitert(client, mandant):
    tp = _tp(client, mandant)
    antwort = client.post("/api/companies/" + mandant + "/gate/" + tp + "/widerrufen",
                          json={"grund": "zweimal geht nicht"})
    assert antwort.status_code == 400
    assert "nicht freigegeben" in antwort.json()["detail"]


# --------------------------------------------------------------------------- #
# 3. PostgreSQL-only, ehrlich benannt
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("pfad,methode", [
    ("/uebergabe", "GET"), ("/uebergabe", "POST"), ("/uebergabe/veraltet", "GET"),
    ("/stand?datum=2026-09-04T09:00:00%2B02:00", "GET"), ("/historie", "GET")])
def test_pg_endpunkte_sagen_im_sqlite_modus_501(client, mandant, pfad, methode):
    antwort = client.request(methode, "/api/companies/" + mandant + pfad,
                             json={} if methode == "POST" else None)
    assert antwort.status_code == 501, antwort.text
    assert "PostgreSQL" in antwort.json()["detail"]


def test_uebergabe_ist_admins_vorbehalten(client, mandant):
    anwendung.AUTH.benutzer_anlegen("v26-nutzer@bc0.test", "V26-Nutzer", PW, Rolle.BENUTZER,
                                    mandanten=[mandant])
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "v26-nutzer@bc0.test", "passwort": PW})
    assert c.get("/api/companies/" + mandant + "/uebergabe").status_code == 403
    assert c.post("/api/companies/" + mandant + "/uebergabe", json={}).status_code == 403
    tp = _tp(client, mandant)
    assert c.post("/api/companies/" + mandant + "/gate/" + tp + "/widerrufen",
                  json={"grund": "x"}).status_code == 403
