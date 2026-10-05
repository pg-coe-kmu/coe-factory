# -*- coding: utf-8 -*-
"""
Dokumentpflicht je Teilprozess — v3.12 (05.10.2026, Vorgang 917).

Entscheidung Simeon: Die Text-Belegpflicht je Item bleibt. Zusaetzlich MUSS je
Teilprozess mindestens ein Dokument hochgeladen sein. Speichern bleibt ohne
Dokument moeglich ("Zwischenspeicherung"), aber:

  1. Self-Rating ohne Dokument: 200, Antwort meldet zwischenstand=True und den Hinweis.
  2. Self-Rating ohne Text-Beleg: weiterhin 400 (ADR-005, unveraendert).
  3. Mit Dokument am Teilprozess: zwischenstand=False.
  4. Es zaehlt NUR ein Dokument genau am Teilprozess — am Kernprozess oder am
     Mandanten belegt keinen Teilprozess. Verworfene zaehlen nicht.
  5. Gate 0 sperrt ohne Dokument (dritte Vorbedingung, Hindernisart "dokument")
     und gibt frei, sobald eines da ist.
  6. Der Bericht rechnet weiter mit, sagt aber "Nicht belegt!" und nennt die
     Teilprozesse; dok_quote zaehlt Teilprozesse mit Dokument.
  7. YAML-Import: Stufe ohne Beleg -> 400, und es wird NICHTS angelegt (Befund N6).
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as A  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "dokumentpflicht-admin-pw"
ITEMS = {str(n): {"stufe": 2, "beleg": "Beleg %d" % n} for n in range(1, 31)}


@pytest.fixture(scope="module")
def client():
    A.AUTH.benutzer_anlegen("dok@bc0.test", "Dok-Admin", PW, Rolle.ADMIN)
    c = TestClient(A.app)
    c.post("/api/auth/login", json={"email": "dok@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    cid = str(client.post("/api/companies", json={"name": "Dok GmbH", "kps": [1]}).json()["id"])
    client.put("/api/companies/%s/entitaeten" % cid, json={"personen": [{"name": "Ida", "funktion": "Leitung"}]})
    p = client.get("/api/companies/%s/entitaeten" % cid).json()["personen"][0]["person_id"]
    kp = _kp(client, cid)
    client.put("/api/companies/%s/entitaeten" % cid, json={"zuordnungen": [{"process_id": kp, "person_id": p, "funktion": "eigner"}]})
    return cid


def _kp(client, cid):
    return sorted(client.get("/api/companies/" + cid).json()["processes"].keys())[0]


def _hoch(client, cid, ref):
    r = client.post("/api/companies/%s/documents" % cid, data={"ref_id": ref},
                    files={"file": ("nachweis.txt", b"Nachweis " + ref.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    return r.json()


def _rating(client, cid, sid, items=ITEMS):
    return client.post("/api/companies/%s/rating" % cid, json={"key": sid, "items": items})


def _gate(client, cid, sid):
    return [t for t in client.get("/api/companies/%s/gate" % cid).json()["teilprozesse"] if t["sub_process_id"] == sid][0]


def test_speichern_ohne_dokument_ist_zwischenstand(client, mandant):
    sid = _kp(client, mandant) + ".TP-1"
    r = _rating(client, mandant, sid)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["saved"] == 30 and j["zwischenstand"] is True and j["belegt"] is False and j["dokumente"] == 0
    assert "Zwischenstand" in j["hinweis"] and "Dokument" in j["hinweis"]


def test_text_beleg_je_item_bleibt_pflicht(client, mandant):
    sid = _kp(client, mandant) + ".TP-1"
    r = _rating(client, mandant, sid, {"3": {"stufe": 2, "beleg": "   "}})
    assert r.status_code == 400 and "3" in r.json()["detail"]


def test_dokument_am_kernprozess_oder_mandant_belegt_keinen_teilprozess(client, mandant):
    kp = _kp(client, mandant)
    _hoch(client, mandant, kp); _hoch(client, mandant, "MANDANT")
    assert _rating(client, mandant, kp + ".TP-1").json()["zwischenstand"] is True
    z = _gate(client, mandant, kp + ".TP-1")
    assert z["dokument_vorhanden"] is False and z["bogen_ausfuellbar"] is False
    assert "Kein Dokument" in z["am_zug_grund"]


def test_gate0_sperrt_ohne_dokument_mit_eigener_hindernisart(client, mandant):
    kp = _kp(client, mandant)
    h = [x for x in client.get("/api/companies/%s/gate" % mandant).json()["hindernisse"] if x["art"] == "dokument"]
    assert h and h[0]["process_id"] == kp and "Nicht belegt" in h[0]["text"]
    # Eine Freigabe wird mit der Liste der fehlenden Vorbedingungen abgewiesen.
    r = client.post("/api/companies/%s/gate/%s" % (mandant, kp + ".TP-1"), json={"ereignis": "freigegeben"})
    assert r.status_code == 400 and "kein Dokument hochgeladen" in r.json()["detail"], r.text


def test_mit_dokument_am_teilprozess_ist_er_belegt(client, mandant):
    sid = _kp(client, mandant) + ".TP-1"
    _hoch(client, mandant, sid)
    j = _rating(client, mandant, sid).json()
    assert j["zwischenstand"] is False and j["dokumente"] == 1 and j["hinweis"] is None
    z = _gate(client, mandant, sid)
    assert z["dokument_vorhanden"] is True and z["bogen_ausfuellbar"] is True


def test_verworfenes_dokument_zaehlt_nicht(client, mandant):
    sid = _kp(client, mandant) + ".TP-2"
    d = _hoch(client, mandant, sid)
    doc_id = d.get("doc_id") or d.get("id")
    c = A.db(); c.execute("UPDATE beleg_dokumente SET status='verworfen' WHERE doc_id=?", (doc_id,)); c.commit(); c.close()
    assert _rating(client, mandant, sid).json()["zwischenstand"] is True


def test_bericht_rechnet_und_sagt_nicht_belegt(client, mandant):
    kp = _kp(client, mandant)
    rep = client.get("/api/companies/%s/report" % mandant).json()
    tps = {t["sub_process_id"]: t for t in rep["tp_rows"]}
    assert tps[kp + ".TP-1"]["belegt"] is True and tps[kp + ".TP-2"]["belegt"] is False
    assert tps[kp + ".TP-2"]["avg"] == 2.0, "nicht belegte Teilprozesse werden mitgerechnet"
    assert rep["nicht_belegt"] == [kp + ".TP-2"] and rep["dok_quote"] == 50
    assert any(s.startswith("Nicht belegt!") and kp + ".TP-2" in s for s in rep["befund"]["kurzfassung"])


def test_yaml_ohne_beleg_wird_abgewiesen_und_legt_nichts_an(client):
    vorher = len(client.get("/api/companies").json())
    yaml = ("company: {name: Ohne Beleg AG}\nprozesse:\n  - process_id: KP-01\n    process_name: Test\n"
            "    teilprozesse:\n      - step: 1\n        name: T1\n        bewertungen:\n"
            "          1: {stufe: 2, beleg: \"ok\"}\n          2: {stufe: 3, beleg: \"\"}\n")
    r = client.post("/api/import_yaml", content=yaml.encode())
    assert r.status_code == 400 and "KP-01.TP-1 I-02" in r.json()["detail"]
    assert len(client.get("/api/companies").json()) == vorher, "nichts angelegt"


def test_yaml_mit_belegen_geht_weiter(client):
    yaml = ("company: {name: Mit Beleg AG}\nprozesse:\n  - process_id: KP-01\n    process_name: Test\n"
            "    teilprozesse:\n      - step: 1\n        name: T1\n        bewertungen:\n"
            "          1: {stufe: 2, beleg: \"Arbeitsanweisung 2025\"}\n          2: {stufe: ~, beleg: \"\"}\n")
    r = client.post("/api/import_yaml", content=yaml.encode())
    assert r.status_code == 200 and r.json()["bewertungen"] == 1
