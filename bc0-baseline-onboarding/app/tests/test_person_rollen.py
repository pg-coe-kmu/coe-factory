# -*- coding: utf-8 -*-
"""
Weitere Rollen je Person — Schema v3.9 (29.09.2026, Vorgang 911).

ref_personen.rolle_id bleibt die Hauptrolle; weitere Rollen stehen in
person_rollen und laufen ueber denselben Endpunkt PUT /entitaeten.

Geprueft wird:
  1. GET liefert je Person ``weitere_rollen`` (leer, solange nichts gesetzt ist).
  2. PUT mit ``weitere_rollen`` ersetzt die Liste dieser Person.
  3. OHNE den Schluessel bleibt der Bestand stehen — die alte Oberflaeche
     schickt ihn nie und darf nichts loeschen.
  4. Die Hauptrolle wird nicht doppelt gefuehrt, Doppelte fallen weg.
  5. Eine unbekannte Rolle wird mit 400 abgewiesen, und dann wird NICHTS
     geschrieben — auch nicht die Personendaten desselben Aufrufs.
  6. Die Hauptrolle (und damit owner_rolle_id) bleibt unberuehrt.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "person-rollen-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("personrollen@bc0.test", "PR-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "personrollen@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    cid = str(client.post("/api/companies", json={"name": "Rollen GmbH", "kps": [1]}).json()["id"])
    r = client.put("/api/companies/%s/rollen_kosten" % cid, json={"rollen": [
        {"bezeichnung": "Teamleitung", "klasse": "K4", "aktiv": True},
        {"bezeichnung": "Sachbearbeitung", "klasse": "K2", "aktiv": True},
        {"bezeichnung": "Datenschutz", "klasse": "K3", "aktiv": True}]})
    assert r.status_code == 200, r.text
    return cid


def _personen(client, mandant):
    return {p["person_id"]: p for p in client.get("/api/companies/%s/entitaeten" % mandant).json()["personen"]}


def _rollen_ids(client, mandant):
    return [r["rolle_id"] for r in client.get("/api/companies/%s/entitaeten" % mandant).json()["rollen"]]


def _put(client, mandant, **person):
    p = {"person_id": "P-01", "name": "Test Person", "funktion": "Logistik", "aktiv": True}
    p.update(person)
    return client.put("/api/companies/%s/entitaeten" % mandant, json={"personen": [p]})


def test_anfangs_keine_weiteren_rollen(client, mandant):
    r1, r2, r3 = _rollen_ids(client, mandant)
    assert _put(client, mandant, person_id="", rolle_id=r1).status_code == 200
    assert _personen(client, mandant)["P-01"]["weitere_rollen"] == []


def test_weitere_rollen_setzen_und_ersetzen(client, mandant):
    r1, r2, r3 = _rollen_ids(client, mandant)
    assert _put(client, mandant, rolle_id=r1, weitere_rollen=[r2, r3]).status_code == 200
    assert _personen(client, mandant)["P-01"]["weitere_rollen"] == sorted([r2, r3])
    assert _put(client, mandant, rolle_id=r1, weitere_rollen=[r3]).status_code == 200
    assert _personen(client, mandant)["P-01"]["weitere_rollen"] == [r3]


def test_ohne_schluessel_bleibt_der_bestand(client, mandant):
    r1, r2, r3 = _rollen_ids(client, mandant)
    _put(client, mandant, rolle_id=r1, weitere_rollen=[r2])
    assert _put(client, mandant, rolle_id=r1).status_code == 200          # alte Oberflaeche
    assert _personen(client, mandant)["P-01"]["weitere_rollen"] == [r2]


def test_hauptrolle_und_doppelte_fallen_weg(client, mandant):
    r1, r2, r3 = _rollen_ids(client, mandant)
    assert _put(client, mandant, rolle_id=r1, weitere_rollen=[r1, r2, r2, ""]).status_code == 200
    p = _personen(client, mandant)["P-01"]
    assert p["rolle_id"] == r1
    assert p["weitere_rollen"] == [r2]


def test_unbekannte_rolle_schreibt_nichts(client, mandant):
    r1, r2, r3 = _rollen_ids(client, mandant)
    _put(client, mandant, rolle_id=r1, weitere_rollen=[r2], funktion="Vorher")
    r = _put(client, mandant, rolle_id=r1, weitere_rollen=["R-99"], funktion="Nachher")
    assert r.status_code == 400
    p = _personen(client, mandant)["P-01"]
    assert p["weitere_rollen"] == [r2]
    assert p["funktion"] == "Vorher", "ein abgewiesener Aufruf darf auch die Person nicht aendern"


def test_keine_liste_wird_abgewiesen(client, mandant):
    r1, r2, r3 = _rollen_ids(client, mandant)
    assert _put(client, mandant, rolle_id=r1, weitere_rollen="R-02").status_code == 400


def test_hauptrolle_bleibt_quelle_der_eignerrolle(client, mandant):
    """Die Hauptrolle ist unveraendert ein eigenes Feld — weitere Rollen verdraengen sie nicht."""
    r1, r2, r3 = _rollen_ids(client, mandant)
    _put(client, mandant, rolle_id=r2, weitere_rollen=[r1, r3])
    p = _personen(client, mandant)["P-01"]
    assert p["rolle_id"] == r2
    assert p["weitere_rollen"] == sorted([r1, r3])
