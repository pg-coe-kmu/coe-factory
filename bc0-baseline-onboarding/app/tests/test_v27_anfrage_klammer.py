# -*- coding: utf-8 -*-
"""Schema v2.7 — die Anfrage als Klammer: n:m-Prozessbezug, Status `uebergeben`.

SQLite-Seite. Die Vollstaendigkeitspruefung der Uebergabe (v_anfrage_uebergabe_stand,
gate_paket_schnueren) laeuft nur auf PostgreSQL und ist in
``pruefung_v2.7_anfrage_klammer.sql`` belegt.
"""
import os, sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "_v27.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "v27-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("v27-admin@bc0.test", "V27-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "v27-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies", json={"name": "Klammer GmbH", "kps": [1, 2]}).json()["id"])


def _kps(client, cid):
    return sorted(client.get("/api/companies/" + cid).json()["processes"].keys())


def test_status_kennt_uebergeben_zwischen_gate_und_bewertung():
    s = anwendung.ANFRAGE_STATUS
    assert s.index("am_gate") < s.index("uebergeben") < s.index("bewertet")


def test_anfrage_mit_bezug_legt_hauptbezug_an(client, mandant):
    kp = _kps(client, mandant)[0]
    r = client.post("/api/companies/" + mandant + "/anfragen", json={
        "originaltext": "Der ganze Ablauf ist zu langsam.", "process_id": kp,
        "zuordnung_quelle": "anfrage"})
    assert r.status_code == 200, r.text
    a = [x for x in client.get("/api/companies/" + mandant + "/anfragen").json()["anfragen"]
         if x["anfrage_id"] == r.json()["anfrage_id"]][0]
    assert a["bezuege"] == [{"process_id": kp, "sub_process_id": None, "rolle": "haupt",
                             "zuordnung_quelle": "anfrage"}]


def test_bezuege_liste_ersetzt_und_spiegelt_den_hauptbezug(client, mandant):
    kp1, kp2 = _kps(client, mandant)[:2]
    aid = client.post("/api/companies/" + mandant + "/anfragen",
                      json={"originaltext": "Angebot bis Rechnung."}).json()["anfrage_id"]
    r = client.put("/api/companies/" + mandant + "/anfragen/" + aid + "/zuordnung", json={"bezuege": [
        {"process_id": kp1, "sub_process_id": kp1 + ".TP-2", "rolle": "haupt", "zuordnung_quelle": "interview"},
        {"process_id": kp2, "rolle": "beteiligt", "zuordnung_quelle": "interview"},
        {"process_id": kp2, "sub_process_id": kp2 + ".TP-1", "zuordnung_quelle": "vorschlag_bc0"}]})
    assert r.status_code == 200, r.text
    assert r.json()["process_id"] == kp1 and r.json()["sub_process_id"] == kp1 + ".TP-2"
    assert len(r.json()["bezuege"]) == 3
    assert r.json()["bezuege"][0]["rolle"] == "haupt", "der Hauptbezug steht vorn"
    a = [x for x in client.get("/api/companies/" + mandant + "/anfragen").json()["anfragen"]
         if x["anfrage_id"] == aid][0]
    assert a["process_id"] == kp1 and a["zuordnung_quelle"] == "interview", "ref_anfragen ist gespiegelt"
    # Ersetzen: eine kuerzere Liste, ohne rolle -> erster wird haupt
    r = client.put("/api/companies/" + mandant + "/anfragen/" + aid + "/zuordnung", json={"bezuege": [
        {"process_id": kp2, "zuordnung_quelle": "interview"}]})
    assert r.status_code == 200 and r.json()["bezuege"][0]["rolle"] == "haupt"
    assert r.json()["process_id"] == kp2


@pytest.mark.parametrize("bezuege,erwartet", [
    ([], "Mindestens ein Bezug"),
    ([{"process_id": "$1", "rolle": "haupt", "zuordnung_quelle": "anfrage"},
      {"process_id": "$2", "rolle": "haupt", "zuordnung_quelle": "anfrage"}], "Genau ein Hauptbezug"),
    ([{"process_id": "$1", "sub_process_id": "$2.TP-1", "zuordnung_quelle": "anfrage"}], "gehoert nicht zu"),
    ([{"process_id": "$1", "zuordnung_quelle": "geraten"}], "Unbekannte Zuordnungsquelle"),
    ([{"process_id": "$1", "zuordnung_quelle": "anfrage"},
      {"process_id": "$1", "zuordnung_quelle": "anfrage"}], "doppelt"),
    ([{"process_id": "KP-99", "zuordnung_quelle": "anfrage"}], "Unbekannter Kernprozess"),
])
def test_bezuege_werden_geprueft(client, mandant, bezuege, erwartet):
    kp1, kp2 = _kps(client, mandant)[:2]
    bezuege = [{k: (v.replace("$1", kp1).replace("$2", kp2) if isinstance(v, str) else v)
                for k, v in b.items()} for b in bezuege]
    aid = client.post("/api/companies/" + mandant + "/anfragen",
                      json={"originaltext": "Pruefung " + erwartet}).json()["anfrage_id"]
    r = client.put("/api/companies/" + mandant + "/anfragen/" + aid + "/zuordnung", json={"bezuege": bezuege})
    assert r.status_code == 400, r.text
    assert erwartet in r.json()["detail"]


def test_einzelform_setzt_hauptbezug_und_laesst_beteiligte(client, mandant):
    kp1, kp2 = _kps(client, mandant)[:2]
    aid = client.post("/api/companies/" + mandant + "/anfragen",
                      json={"originaltext": "Einzelform."}).json()["anfrage_id"]
    client.put("/api/companies/" + mandant + "/anfragen/" + aid + "/zuordnung", json={"bezuege": [
        {"process_id": kp1, "zuordnung_quelle": "anfrage"},
        {"process_id": kp2, "rolle": "beteiligt", "zuordnung_quelle": "interview"}]})
    r = client.put("/api/companies/" + mandant + "/anfragen/" + aid + "/zuordnung",
                   json={"process_id": kp1, "sub_process_id": kp1 + ".TP-1", "zuordnung_quelle": "interview"})
    assert r.status_code == 200, r.text
    a = [x for x in client.get("/api/companies/" + mandant + "/anfragen").json()["anfragen"]
         if x["anfrage_id"] == aid][0]
    rollen = {(b["process_id"], b["sub_process_id"]): b["rolle"] for b in a["bezuege"]}
    assert rollen[(kp1, kp1 + ".TP-1")] == "haupt"
    assert rollen[(kp2, None)] == "beteiligt", "Beteiligte bleiben stehen"
    assert len(a["bezuege"]) == 2


def test_status_uebergeben_ist_setzbar_und_kein_ruecksprung(client, mandant):
    kp = _kps(client, mandant)[0]
    aid = client.post("/api/companies/" + mandant + "/anfragen",
                      json={"originaltext": "Status.", "process_id": kp,
                            "zuordnung_quelle": "anfrage"}).json()["anfrage_id"]
    for st in ("zugeordnet", "im_interview", "am_gate", "uebergeben"):
        assert client.put("/api/companies/" + mandant + "/anfragen/" + aid + "/status",
                          json={"status": st}).status_code == 200, st
    r = client.put("/api/companies/" + mandant + "/anfragen/" + aid + "/status", json={"status": "am_gate"})
    assert r.status_code == 400 and "Rueckschritt" in r.json()["detail"]
    assert client.put("/api/companies/" + mandant + "/anfragen/" + aid + "/status",
                      json={"status": "bewertet"}).status_code == 200


def test_uebergabe_im_sqlite_modus_bleibt_501(client, mandant):
    r = client.post("/api/companies/" + mandant + "/uebergabe", json={"anfrage_id": "A-2026-01"})
    assert r.status_code == 501
