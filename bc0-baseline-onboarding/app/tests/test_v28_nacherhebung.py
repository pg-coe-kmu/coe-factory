# -*- coding: utf-8 -*-
"""Schema v2.8 — Nacherhebung: alt bleibt, neu kommt dazu.

Befund vom Ausrollen v2.6 (04.09.2026): `abgeschlossen` ist eine Sperre, und
`E-JJJJ-MM` erlaubte eine Erhebung je Monat — nach dem Abschluss am 4. war der
Mandant bis zum 1. des Folgemonats nicht mehr bewertbar. Regel seit v2.8 (Simeon):
dieselbe wie beim Paket.

  1. Eine Bewertung nach dem Abschluss legt automatisch die naechste Erhebung an
     (E-JJJJ-MM-2, -3 …); die abgeschlossene bleibt unveraendert.
  2. Was gilt, ist je Item der juengste Wert — eine Nacherhebung mit einem Item
     aendert ein Item, die anderen 29 behalten den Wert der Ersterhebung.
  3. Abschliessen und Beginnen sind Admin-Handlungen; `neu` nur, wenn keine offen ist.
  4. Eine Kennung wird nie ein zweites Mal vergeben (verworfene zaehlen mit).
"""
import os, sys, datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "_v28.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "v28-admin-passwort"
HEUTE = datetime.date.today()
BASIS = "E-%04d-%02d" % (HEUTE.year, HEUTE.month)


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("v28-admin@bc0.test", "V28-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "v28-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    cid = str(client.post("/api/companies", json={"name": "Nachlese GmbH", "kps": [1]}).json()["id"])
    kp = sorted(client.get("/api/companies/" + cid).json()["processes"].keys())[0]
    items = {str(n): {"stufe": 3, "beleg": "Beleg %d" % n} for n in range(1, 31)}
    r = client.post("/api/companies/" + cid + "/rating", json={"key": kp + ".TP-1", "items": items})
    assert r.status_code == 200, r.text
    assert r.json()["erhebung_id"] == BASIS and r.json()["erhebung_neu"] is True
    return cid


def _tp(client, cid):
    return sorted(client.get("/api/companies/" + cid).json()["processes"].keys())[0] + ".TP-1"


def _erhebungen(client, cid):
    return client.get("/api/companies/" + cid + "/erhebungen").json()


def _stufe(client, cid, tp, nr):
    return client.get("/api/companies/" + cid).json()["ratings"][tp][str(nr)]["stufe"]


# --------------------------------------------------------------------------- #
# 1. Nach dem Abschluss: die naechste Bewertung legt die naechste Erhebung an
# --------------------------------------------------------------------------- #
def test_bewertung_nach_abschluss_legt_nacherhebung_an(client, mandant):
    tp = _tp(client, mandant)
    assert client.post("/api/companies/" + mandant + "/erhebungen",
                       json={"aktion": "abschliessen"}).status_code == 200
    d = _erhebungen(client, mandant)
    assert d["offen"] is None and d["naechste"] == BASIS + "-2"

    r = client.post("/api/companies/" + mandant + "/rating",
                    json={"key": tp, "items": {"1": {"stufe": 5, "beleg": "nachgebessert"}}})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "saved": 1, "erhebung_id": BASIS + "-2", "erhebung_neu": True}

    d = _erhebungen(client, mandant)
    assert d["offen"] == BASIS + "-2" and d["massgeblich"] == BASIS + "-2"
    assert d["naechste"] == BASIS + "-3", "die naechste Kennung kommt vom Server, auch bei offener"
    neu = [e for e in d["erhebungen"] if e["erhebung_id"] == BASIS + "-2"][0]
    alt = [e for e in d["erhebungen"] if e["erhebung_id"] == BASIS][0]
    assert neu["status"] == "offen" and neu["bewertungen"] == 1
    assert neu["bezeichnung"].startswith("Nacherhebung")
    assert BASIS in (neu["hinweis"] or ""), "die Nacherhebung nennt, woran sie anschliesst"
    assert alt["status"] == "abgeschlossen" and alt["bewertungen"] == 30, "die alte bleibt, wie sie war"


def test_es_gilt_je_item_der_juengste_wert(client, mandant):
    """Ein nachbewertetes Item traegt den neuen Wert, die anderen 29 den alten."""
    tp = _tp(client, mandant)
    assert _stufe(client, mandant, tp, 1) == 5
    assert _stufe(client, mandant, tp, 2) == 3


def test_zweite_bewertung_geht_in_dieselbe_offene_erhebung(client, mandant):
    tp = _tp(client, mandant)
    r = client.post("/api/companies/" + mandant + "/rating",
                    json={"key": tp, "items": {"2": {"stufe": 4, "beleg": "auch neu"}}})
    assert r.status_code == 200
    assert r.json()["erhebung_id"] == BASIS + "-2" and r.json()["erhebung_neu"] is False
    d = _erhebungen(client, mandant)
    assert [e for e in d["erhebungen"] if e["erhebung_id"] == BASIS + "-2"][0]["bewertungen"] == 2


# --------------------------------------------------------------------------- #
# 2. Kennungen: -2, -3 …, nie doppelt
# --------------------------------------------------------------------------- #
def test_dritte_erhebung_heisst_minus_drei(client, mandant):
    tp = _tp(client, mandant)
    assert client.post("/api/companies/" + mandant + "/erhebungen",
                       json={"aktion": "abschliessen"}).status_code == 200
    r = client.post("/api/companies/" + mandant + "/rating",
                    json={"key": tp, "items": {"3": {"stufe": 2, "beleg": "dritter Anlauf"}}})
    assert r.status_code == 200 and r.json()["erhebung_id"] == BASIS + "-3"


def test_verworfene_kennung_wird_nicht_neu_vergeben(client, mandant):
    assert client.post("/api/companies/" + mandant + "/erhebungen",
                       json={"aktion": "verwerfen"}).status_code == 200
    d = _erhebungen(client, mandant)
    assert d["offen"] is None and d["naechste"] == BASIS + "-4"
    assert d["massgeblich"] == BASIS + "-2", "verworfen zaehlt nicht als massgeblich"


def test_neu_mit_bezeichnung_nur_wenn_keine_offen_ist(client, mandant):
    r = client.post("/api/companies/" + mandant + "/erhebungen",
                    json={"aktion": "neu", "bezeichnung": "Nacherhebung nach Interview"})
    assert r.status_code == 200 and r.json()["erhebung_id"] == BASIS + "-4"
    r2 = client.post("/api/companies/" + mandant + "/erhebungen", json={"aktion": "neu"})
    assert r2.status_code == 400
    assert BASIS + "-4" in r2.json()["detail"] and "abschliessen" in r2.json()["detail"]
    d = _erhebungen(client, mandant)
    assert d["offen"] == BASIS + "-4"
    assert d["erhebungen"][0]["bezeichnung"] == "Nacherhebung nach Interview"


# --------------------------------------------------------------------------- #
# 3. Wer darf: BC0 (Admin)
# --------------------------------------------------------------------------- #
def test_abschliessen_und_beginnen_sind_admins_vorbehalten(client, mandant):
    anwendung.AUTH.benutzer_anlegen("v28-nutzer@bc0.test", "V28-Nutzer", PW, Rolle.BENUTZER,
                                    mandanten=[mandant])
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "v28-nutzer@bc0.test", "passwort": PW})
    assert c.get("/api/companies/" + mandant + "/erhebungen").status_code == 200, "lesen darf jeder"
    for aktion in ("abschliessen", "neu", "verwerfen"):
        assert c.post("/api/companies/" + mandant + "/erhebungen",
                      json={"aktion": aktion}).status_code == 403
    # Bewerten darf der Benutzer weiterhin — auch in eine automatisch angelegte Erhebung.
    tp = _tp(client, mandant)
    r = c.post("/api/companies/" + mandant + "/rating",
               json={"key": tp, "items": {"4": {"stufe": 4, "beleg": "vom Benutzer"}}})
    assert r.status_code == 200 and r.json()["erhebung_id"] == BASIS + "-4"


# --------------------------------------------------------------------------- #
# 4. Die Oberflaeche traegt den Block und den Knopf
# --------------------------------------------------------------------------- #
def test_self_rating_reiter_hat_den_erhebungsblock():
    hier = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(hier, "static", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert 'id="raErh"' in html and "zeichneErhebung" in html
    assert "Erhebung abschließen" in html and "Neue Erhebung beginnen" in html
    block = html.split("async function zeichneErhebung")[1].split("/* Die naechste Kennung sagt der Server")[0]
    assert "prompt(" not in block, "kein Browser-Dialog — der blockiert die Seite"
    assert "d.naechste" in block, "die naechste Kennung kommt vom Server, nicht aus der offenen Kennung gerechnet"
