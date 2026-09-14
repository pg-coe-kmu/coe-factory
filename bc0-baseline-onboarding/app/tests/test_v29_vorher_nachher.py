# -*- coding: utf-8 -*-
"""Schema v2.9 — Vorher / Nachher: der Stand nach einer Erhebung.

Simeon (04.09.2026): "Werden die Items geaendert, aendert sich auch der
Reifegrad je Prozess. Und immer auf aktuellem Stand — wie machen wir eine
Vor-/Nachher-Betrachtung?"

Vier Aussagen:
  1. `?bis=E-…` rechnet den Bericht auf den Stand NACH dieser Erhebung — die
     Nacherhebung danach ist darin nicht enthalten. Ohne Parameter wie bisher.
  2. Der Vergleich nennt je Teilprozess vorher, nachher, Differenz und die
     geaenderten Items; nicht nacherhobene Teilprozesse bleiben unveraendert.
  3. "fest" heisst: diese und alle frueheren Erhebungen sind nicht mehr offen.
  4. Verworfene sind keine Grenze; vorher muss vor nachher liegen.
"""
import os, sys, datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "_v29.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "v29-admin-passwort"
HEUTE = datetime.date.today()
E1 = "E-%04d-%02d" % (HEUTE.year, HEUTE.month)
E2 = E1 + "-2"
E3 = E1 + "-3"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("v29-admin@bc0.test", "V29-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "v29-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    """Ersterhebung E1: zwei Teilprozesse voll bewertet (alles 3), abgeschlossen.
    Nacherhebung E2: in TP-1 drei Items auf 5, ein Item bleibt 3 (unveraendert
    gespeichert), TP-2 nicht angefasst. Abgeschlossen. Dann E3 offen mit einem Item."""
    cid = str(client.post("/api/companies", json={"name": "Vorher Nachher AG", "kps": [1]}).json()["id"])
    kp = sorted(client.get("/api/companies/" + cid).json()["processes"].keys())[0]
    drei = {str(n): {"stufe": 3, "beleg": "Beleg %d" % n} for n in range(1, 31)}
    for tp in (kp + ".TP-1", kp + ".TP-2"):
        assert client.post("/api/companies/" + cid + "/rating", json={"key": tp, "items": drei}).status_code == 200
    assert client.post("/api/companies/" + cid + "/erhebungen", json={"aktion": "abschliessen"}).status_code == 200
    r = client.post("/api/companies/" + cid + "/rating", json={"key": kp + ".TP-1", "items": {
        "1": {"stufe": 5, "beleg": "besser"}, "2": {"stufe": 5, "beleg": "besser"},
        "3": {"stufe": 5, "beleg": "besser"}, "4": {"stufe": 3, "beleg": "gleich"}}})
    assert r.status_code == 200 and r.json()["erhebung_id"] == E2
    assert client.post("/api/companies/" + cid + "/erhebungen", json={"aktion": "abschliessen"}).status_code == 200
    r = client.post("/api/companies/" + cid + "/rating", json={"key": kp + ".TP-2", "items": {
        "7": {"stufe": 1, "beleg": "schlechter"}}})
    assert r.status_code == 200 and r.json()["erhebung_id"] == E3
    return cid


def _kp(client, cid):
    return sorted(client.get("/api/companies/" + cid).json()["processes"].keys())[0]


# --------------------------------------------------------------------------- #
# 1. Der Bericht zum Stand nach einer Erhebung
# --------------------------------------------------------------------------- #
def test_bericht_ohne_parameter_ist_der_aktuelle_stand(client, mandant):
    rep = client.get("/api/companies/" + mandant + "/report").json()
    assert rep["bis"] is None
    assert sorted(e["erhebung_id"] for e in rep["erhebungen"]) == [E1, E2, E3]
    tp1 = [t for t in rep["tp_rows"] if t["sub_process_id"].endswith(".TP-1")][0]
    # 27 x 3 + 3 x 5 = 96 / 30 = 3.2
    assert tp1["avg"] == 3.2


def test_bericht_nach_erster_erhebung_kennt_die_nacherhebung_nicht(client, mandant):
    rep = client.get("/api/companies/" + mandant + "/report?bis=" + E1).json()
    assert rep["bis"]["erhebung_id"] == E1 and rep["bis"]["fest"] is True
    assert [e["erhebung_id"] for e in rep["erhebungen"]] == [E1], "Herkunft nennt nur E1"
    for t in rep["tp_rows"]:
        assert t["avg"] == 3.0
    assert rep["gesamt"] == 3.0


def test_bericht_nach_zweiter_erhebung_ist_die_zusammensetzung(client, mandant):
    rep = client.get("/api/companies/" + mandant + "/report?bis=" + E2).json()
    assert rep["bis"]["fest"] is True
    assert sorted(e["erhebung_id"] for e in rep["erhebungen"]) == [E1, E2]
    tp1 = [t for t in rep["tp_rows"] if t["sub_process_id"].endswith(".TP-1")][0]
    tp2 = [t for t in rep["tp_rows"] if t["sub_process_id"].endswith(".TP-2")][0]
    assert tp1["avg"] == 3.2 and tp2["avg"] == 3.0, "TP-2 wurde nicht nacherhoben und bleibt"


def test_stand_nach_offener_erhebung_ist_nicht_fest(client, mandant):
    rep = client.get("/api/companies/" + mandant + "/report?bis=" + E3).json()
    assert rep["bis"]["fest"] is False
    d = client.get("/api/companies/" + mandant + "/erhebungen").json()
    fest = {e["erhebung_id"]: e["fest"] for e in d["erhebungen"]}
    rang = {e["erhebung_id"]: e["rang"] for e in d["erhebungen"]}
    assert fest == {E1: True, E2: True, E3: False}
    assert rang == {E1: 1, E2: 2, E3: 3}


def test_unbekannte_und_verworfene_grenze(client, mandant):
    r = client.get("/api/companies/" + mandant + "/report?bis=E-2020-01")
    assert r.status_code == 400 and "Unbekannte Erhebung" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# 2. Der Vergleich
# --------------------------------------------------------------------------- #
def test_vergleich_e1_gegen_e2(client, mandant):
    v = client.get("/api/companies/" + mandant + "/report/vergleich?von=" + E1 + "&bis=" + E2).json()
    assert v["von"]["erhebung_id"] == E1 and v["bis"]["erhebung_id"] == E2 and v["fest"] is True
    assert v["n_geaendert"] == 3 and v["n_neu_bewertet"] == 0
    tp1 = [t for t in v["teilprozesse"] if t["sub_process_id"].endswith(".TP-1")][0]
    tp2 = [t for t in v["teilprozesse"] if t["sub_process_id"].endswith(".TP-2")][0]
    assert (tp1["vorher"], tp1["nachher"], tp1["delta"], tp1["geaendert"]) == (3.0, 3.2, 0.2, 3)
    assert (tp2["vorher"], tp2["nachher"], tp2["delta"], tp2["geaendert"]) == (3.0, 3.0, 0.0, 0)
    # Item 4 wurde in E2 mit demselben Wert gespeichert — keine Aenderung.
    assert sorted(i["item_nr"] for i in v["items"]) == [1, 2, 3]
    assert all(i["alt"] == 3 and i["neu"] == 5 and i["erhebung_neu"] == E2 for i in v["items"])
    # Gesamt: 60 Items, 3 davon von 3 auf 5 -> 3.0 -> 3.1
    assert (v["gesamt"]["vorher"], v["gesamt"]["nachher"], v["gesamt"]["delta"]) == (3.0, 3.1, 0.1)
    assert len(v["dimensionen"]) == 5


def test_vergleich_gegen_offene_erhebung_warnt_und_zaehlt_verschlechterung(client, mandant):
    v = client.get("/api/companies/" + mandant + "/report/vergleich?von=" + E2 + "&bis=" + E3).json()
    assert v["fest"] is False, "E3 ist offen — der Vergleich kann sich noch aendern"
    tp2 = [t for t in v["teilprozesse"] if t["sub_process_id"].endswith(".TP-2")][0]
    assert tp2["delta"] < 0 and tp2["geaendert"] == 1
    assert v["items"][0]["alt"] == 3 and v["items"][0]["neu"] == 1


def test_erstmals_bewertet_hat_kein_vorher_und_kein_delta(client, mandant):
    """Befund NoroAI 04.09.: drei Teilprozesse waren in der Ersterhebung nicht bewertet.
    Dann ist vorher None und delta None — nicht 0 und +3,2 (das taeuschte eine
    Verbesserung vor). Hier: TP-3 wird erst in einer vierten Erhebung bewertet."""
    kp = _kp(client, mandant)
    assert client.post("/api/companies/" + mandant + "/erhebungen", json={"aktion": "abschliessen"}).status_code == 200
    r = client.post("/api/companies/" + mandant + "/rating", json={"key": kp + ".TP-3", "items": {
        "1": {"stufe": 4, "beleg": "erstmals"}}})
    assert r.status_code == 200 and r.json()["erhebung_id"] == E1 + "-4"
    v = client.get("/api/companies/" + mandant + "/report/vergleich?von=" + E3 + "&bis=" + E1 + "-4").json()
    tp3 = [t for t in v["teilprozesse"] if t["sub_process_id"].endswith(".TP-3")][0]
    assert tp3["vorher"] is None and tp3["delta"] is None and tp3["nachher"] == 4.0
    assert tp3["geaendert"] == 0 and tp3["neu_bewertet"] == 1
    assert v["n_geaendert"] == 0 and v["n_neu_bewertet"] == 1


def test_vorher_muss_vor_nachher_liegen(client, mandant):
    r = client.get("/api/companies/" + mandant + "/report/vergleich?von=" + E2 + "&bis=" + E1)
    assert r.status_code == 400 and "vor" in r.json()["detail"]
    r = client.get("/api/companies/" + mandant + "/report/vergleich?von=" + E1 + "&bis=" + E1)
    assert r.status_code == 400
    r = client.get("/api/companies/" + mandant + "/report/vergleich?bis=" + E1)
    assert r.status_code == 400 and "von" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# 3. Bauteile
# --------------------------------------------------------------------------- #
def test_sel_bew_ohne_grenze_ist_wortgleich_mit_sel_bew():
    assert anwendung._sel_bew() == anwendung.SEL_BEW


def test_grenze_wird_nach_form_geprueft():
    with pytest.raises(ValueError):
        anwendung._bew_aktuell("company_id", ("2026-09-04'; DROP TABLE x; --", "E-2026-09"))
    with pytest.raises(ValueError):
        anwendung._bew_aktuell("company_id", ("2026-09-04", "E-2026-09' OR 1=1"))


def test_bericht_reiter_hat_stand_und_vergleich():
    hier = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(hier, "static", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert 'id="rbStand"' in html and "rbVergleich" in html and "report/vergleich" in html
    assert "prompt(" not in html.split("function rbStandLeiste")[1].split("async function renderRB")[0]
