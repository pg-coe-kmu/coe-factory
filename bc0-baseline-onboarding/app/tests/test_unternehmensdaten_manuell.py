# -*- coding: utf-8 -*-
"""
Unternehmensdaten manuell erfassen und Dokumente zum ganzen Unternehmen (30.09.2026).

Anlass: App V2 (Klon, Vorgang 910). Simeon: Im Onboarding muessen die
Unternehmensdaten auch von Hand eintragbar sein, nicht nur per YAML-Import, und
PDF/Dokumente sollen als Grundlage fuer spaeteres OCR eingelesen werden.

Geprueft wird dreierlei:
  1. ``PUT /profile`` speichert ``profile_json``, wenn es mitkommt — als Objekt
     oder als JSON-Text.
  2. Kommt der Schluessel NICHT mit, bleibt der Bestand stehen. Die alte
     Oberflaeche schickt ihn nie; sie darf nichts loeschen.
  3. ``ref_id="MANDANT"`` ist beim Hochladen erlaubt, alles andere ausserhalb
     von KP-XX / KP-XX.TP-Y bleibt verboten (Pfaddurchstieg).
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "ud-manuell-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("udmanuell@bc0.test", "UD-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "udmanuell@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies", json={"name": "UD GmbH", "kps": [1]}).json()["id"])


def _profil(client, mandant):
    raw = client.get("/api/companies/%s" % mandant).json()["profile"].get("profile_json") or ""
    return json.loads(raw) if raw else {}


def _speichern(client, mandant, **extra):
    body = {"name": "UD GmbH", "branche": "IT", "rechtsform": "GmbH", "ma": 5, "region": "NRW",
            "geschaeftsmodell": "", "tech_stack": ""}
    body.update(extra)
    return client.put("/api/companies/%s/profile" % mandant, json=body)


def test_unternehmensdaten_als_objekt(client, mandant):
    daten = {"1. Steckbrief": "| Attribut | Wert |\n|---|---|\n| Firmierung | UD GmbH |",
             "5. Datenkonzept Intern": {"5.1 Stammdaten-Architektur": "Eine Quelle je Stammdatum."}}
    assert _speichern(client, mandant, profile_json=daten).status_code == 200
    assert _profil(client, mandant) == daten


def test_unternehmensdaten_als_json_text(client, mandant):
    assert _speichern(client, mandant, profile_json=json.dumps({"A": "b"})).status_code == 200
    assert _profil(client, mandant) == {"A": "b"}


def test_ohne_schluessel_bleibt_der_bestand(client, mandant):
    _speichern(client, mandant, profile_json={"Bleibt": "stehen"})
    assert _speichern(client, mandant).status_code == 200          # alte Oberflaeche
    assert _profil(client, mandant) == {"Bleibt": "stehen"}


@pytest.mark.parametrize("falsch", ["[1,2]", "kein json", [1, 2], 5])
def test_nur_ein_objekt_ist_erlaubt(client, mandant, falsch):
    _speichern(client, mandant, profile_json={"Vorher": "x"})
    assert _speichern(client, mandant, profile_json=falsch).status_code == 400
    assert _profil(client, mandant) == {"Vorher": "x"}, "ein Fehler darf nichts schreiben"


def test_dokument_zum_ganzen_unternehmen(client, mandant):
    r = client.post("/api/companies/%s/documents" % mandant, data={"ref_id": "MANDANT"},
                    files={"file": ("steckbrief.txt", "Firmierung UD GmbH".encode(), "text/plain")})
    assert r.status_code == 200, r.text
    liste = client.get("/api/companies/%s/documents?ref_id=MANDANT" % mandant).json()
    namen = [d["filename"] for d in (liste["dokumente"] if isinstance(liste, dict) else liste)]
    assert "steckbrief.txt" in namen


@pytest.mark.parametrize("ref", ["mandant", "MANDANT/../x", "MANDANT.TP-1", "UNTERNEHMEN", ""])
def test_andere_ref_ids_bleiben_verboten(client, mandant, ref):
    r = client.post("/api/companies/%s/documents" % mandant, data={"ref_id": ref},
                    files={"file": ("x.txt", b"x", "text/plain")})
    assert r.status_code in (400, 422)
