# -*- coding: utf-8 -*-
"""Schema v3.13 — Gate je Anfrage (08.10.2026).

Befund im Review von PR #280: ``anfrage_am_gate_nachziehen()`` zaehlte ein
fertiges BC1-Profil nur ueber Mandant und Teilprozess. Ein fertiges Profil aus
einer frueheren Anfrage schickte eine neue Anfrage auf demselben Teilprozess ans
Gate, ohne dass fuer sie interviewt wurde.

Die Regel selbst steht in der Datenbank und ist in
``pruefung_v3.13_gate_je_anfrage.sql`` mit sieben Erwartungswerten geprueft.
Hier, gegen SQLite, nur das, was der Endpunkt vor der Datenbank entscheidet:

  1. ``?anfrage_id`` in falscher Form wird mit 400 abgewiesen — vor allem
     anderen, damit kein Freitext bis in die SQL-Funktion gelangt.
  2. In richtiger Form geht der Aufruf bis zur PostgreSQL-Pruefung (501 im
     SQLite-Betrieb) — die Form allein sperrt nichts.
  3. Ohne Parameter bleibt alles wie in v3.0 (501 im SQLite-Betrieb).
"""
import os, sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "_v313.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "v313-admin-passwort"
EMAIL = "v313-admin@bc0.test"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen(EMAIL, "V313-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    r = c.post("/api/auth/login", json={"email": EMAIL, "passwort": PW})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies",
                           json={"name": "V313 Testmandant GmbH", "kps": [1]}).json()["id"])


@pytest.mark.parametrize("falsch", ["A-26-1", "x'; DROP TABLE ref_anfragen;--", "A-2026-007"])
def test_falsche_form_wird_abgewiesen(client, mandant, falsch):
    r = client.post("/api/companies/%s/anfragen/gate_nachziehen" % mandant,
                    params={"anfrage_id": falsch})
    assert r.status_code == 400, r.text
    assert "A-JJJJ-NN" in r.text


def test_richtige_form_geht_bis_zur_pg_pruefung(client, mandant):
    r = client.post("/api/companies/%s/anfragen/gate_nachziehen" % mandant,
                    params={"anfrage_id": "A-2026-01"})
    assert r.status_code == 501, r.text
    assert "PostgreSQL" in r.text


def test_ohne_parameter_wie_bisher(client, mandant):
    r = client.post("/api/companies/%s/anfragen/gate_nachziehen" % mandant)
    assert r.status_code == 501, r.text
