# -*- coding: utf-8 -*-
"""
KI-Controlling — Schema v3.11 (04.10.2026, Vorgang 915).

Bausteine 3-6 (Schulungen, Bereichs-Research, Wissensdatenbank, Strategie mit
Meilensteinen) speichert BC0 ueber PUT /ki_controlling. Bausteine 1-2 lesen
ki_laufdaten, die BC4 schreibt; GET verdichtet sie.

Geprueft wird:
  1. Leerer Mandant: alles leer, laufdaten.vorhanden = false.
  2. Jeder Block einzeln optional — ein PUT nur mit "strategie" laesst die
     Schulungen stehen.
  3. Listen ersetzen den Bestand; leere Themen/Titel fallen weg.
  4. Unbekannte Person, falsches Datum, falscher Sachstand -> 400, und dann
     wird NICHTS geschrieben, auch kein anderer Block desselben Aufrufs.
  5. Laufdaten (wie BC4 sie schreibt) werden je Tag/Modell und je Prozess
     verdichtet; Korrekturen und Fehler gezaehlt.
  6. Der Leser darf lesen, nicht schreiben.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "ki-controlling-admin-pw"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("kic@bc0.test", "KIC-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "kic@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    cid = str(client.post("/api/companies", json={"name": "KIC GmbH", "kps": [1]}).json()["id"])
    r = client.put("/api/companies/%s/entitaeten" % cid, json={"personen": [
        {"person_id": "", "name": "Anna", "funktion": "IT", "aktiv": True},
        {"person_id": "", "name": "Ben", "funktion": "HR", "aktiv": True}]})
    assert r.status_code == 200, r.text
    return cid


def _get(client, cid):
    r = client.get("/api/companies/%s/ki_controlling" % cid)
    assert r.status_code == 200, r.text
    return r.json()


def test_leer(client, mandant):
    d = _get(client, mandant)
    assert d["schulungen"] == [] and d["meilensteine"] == []
    assert d["wissensdb"] is None and d["strategie"] is None
    assert d["laufdaten"]["vorhanden"] is False


def test_alle_bloecke_speichern(client, mandant):
    r = client.put("/api/companies/%s/ki_controlling" % mandant, json={
        "schulungen": [{"person_id": "P-01", "thema": "KI-Grundlagen", "termin": "2026-10-15"},
                       {"person_id": "P-02", "thema": "Prompting", "termin": "2026-09-01", "erledigt_am": "2026-09-01"},
                       {"thema": "  "}],
        "research_bereiche": [{"bereich": "Logistik", "person_id": "P-01"}, {"bereich": "Logistik", "person_id": "P-02"}],
        "research_notizen": [{"bereich": "Logistik", "datum": "2026-09-30", "person_id": "P-01", "notiz": "Neue Routenplanung"}],
        "wissensdb": {"vorhanden": "ja", "system": "Confluence", "person_id": "P-02", "aktualisiert_am": "2026-09-20", "takt_tage": 30},
        "strategie": {"sachstand": "beschlossen", "beschreibung": "KI in Logistik", "person_id": "P-01",
                      "beschlossen_am": "2026-07-01", "ueberarbeitet_am": "2026-07-01"},
        "meilensteine": [{"titel": "Pilot", "zieldatum": "2026-12-31"}, {"titel": "Rollout", "zieldatum": "2027-06-30"}]})
    assert r.status_code == 200, r.text
    d = _get(client, mandant)
    assert [s["thema"] for s in d["schulungen"]] == ["Prompting", "KI-Grundlagen"]
    assert d["research_bereiche"] == [{"bereich": "Logistik", "person_id": "P-01"}]
    assert d["research_notizen"][0]["notiz"] == "Neue Routenplanung"
    assert d["wissensdb"]["system"] == "Confluence" and d["wissensdb"]["takt_tage"] == 30
    assert d["strategie"]["sachstand"] == "beschlossen"
    assert [m["titel"] for m in d["meilensteine"]] == ["Pilot", "Rollout"]


def test_bloecke_einzeln_optional(client, mandant):
    before = _get(client, mandant)["schulungen"]
    r = client.put("/api/companies/%s/ki_controlling" % mandant, json={"strategie": {"sachstand": "in_umsetzung"}})
    assert r.status_code == 200
    d = _get(client, mandant)
    assert d["schulungen"] == before
    assert d["strategie"]["sachstand"] == "in_umsetzung"


@pytest.mark.parametrize("falsch", [
    {"schulungen": [{"thema": "X", "person_id": "P-99"}]},
    {"schulungen": [{"thema": "X", "termin": "15.10.2026"}]},
    {"meilensteine": [{"titel": "ohne Datum"}]},
    {"strategie": {"sachstand": "irgendwas"}},
    {"wissensdb": {"vorhanden": "vielleicht"}},
    {"wissensdb": {"vorhanden": "ja", "takt_tage": 0}},
    {"schulungen": "keine Liste"},
])
def test_fehler_schreibt_nichts(client, mandant, falsch):
    vorher = _get(client, mandant)
    body = dict(falsch)
    body["meilensteine"] = body.get("meilensteine", [{"titel": "darf nicht ankommen", "zieldatum": "2030-01-01"}])
    r = client.put("/api/companies/%s/ki_controlling" % mandant, json=body)
    assert r.status_code == 400, r.text
    nachher = _get(client, mandant)
    assert nachher["meilensteine"] == vorher["meilensteine"]
    assert nachher["schulungen"] == vorher["schulungen"]


def test_laufdaten_werden_verdichtet(client, mandant):
    c = anwendung.db()
    zeilen = [("2026-10-01 10:00:00", "KP-01.TP-1", "modell-a", 100, 50, 0.01, "ok", 0),
              ("2026-10-01 11:00:00", "KP-01.TP-1", "modell-a", 200, 50, 0.02, "ok", 1),
              ("2026-10-01 12:00:00", "KP-01.TP-1", "modell-b", 10, 5, 0.001, "fehler", 0),
              ("2026-10-02 09:00:00", "KP-01.TP-1", "modell-a", 300, 0, 0.03, "ok", 0)]
    for z in zeilen:
        c.execute("INSERT INTO ki_laufdaten(company_id,zeitpunkt,sub_process_id,modell,input_tokens,output_tokens,"
                  "kosten_eur,status,korrigiert) VALUES(?,?,?,?,?,?,?,?,?)", (mandant,) + z)
    c.commit(); c.close()
    l = _get(client, mandant)["laufdaten"]
    assert l["vorhanden"] is True
    t = {(z["tag"], z["modell"]): z["token"] for z in l["token_tag_modell"]}
    assert t[("2026-10-01", "modell-a")] == 400 and t[("2026-10-01", "modell-b")] == 15 and t[("2026-10-02", "modell-a")] == 300
    tag1 = [z for z in l["laeufe_tag_prozess"] if z["tag"] == "2026-10-01"][0]
    assert (tag1["laeufe"], tag1["korrigiert"], tag1["fehler"]) == (3, 1, 1)


def test_leser_darf_nicht_schreiben(client, mandant):
    anwendung.AUTH.benutzer_anlegen("kic-leser@bc0.test", "KIC-Leser", PW, Rolle.LESER)
    c2 = TestClient(anwendung.app)
    c2.post("/api/auth/login", json={"email": "kic-leser@bc0.test", "passwort": PW})
    r = c2.put("/api/companies/%s/ki_controlling" % mandant, json={"strategie": {"sachstand": "keine"}})
    assert r.status_code in (401, 403)
