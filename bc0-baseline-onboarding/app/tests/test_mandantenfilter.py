# -*- coding: utf-8 -*-
"""
Tests der Mandantentrennung (Etappe 4b).

Etappe 4a hat die Tür zugemacht: Ohne Anmeldung kein Zugriff. Damit war die
Anwendung geschlossen, innen aber noch ungeteilt — jeder Angemeldete sah alles.
Diese Etappe zieht die Wand ein.

Geprüft wird das, worauf es ankommt: Ein Benutzer darf einen fremden Mandanten
weder sehen noch ändern, und er darf sich auch keinen neuen anlegen. Der Admin
darf beides.

Die Antwort auf einen fremden Mandanten ist **404 und nicht 403**. Das ist
Absicht: Ein Benutzer soll nicht erfahren, dass ein Mandant existiert, den er
nicht sehen darf — sonst ließe sich durch Ausprobieren feststellen, welche IDs
vergeben sind.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402  — conftest.py hat die Umgebung vorbereitet
from bc0_auth import Rolle  # noqa: E402

PW_ADMIN = "filter-admin-passwort"
PW_ALPHA = "filter-alpha-passwort"
PW_OHNE = "filter-ohne-passwort"


@pytest.fixture(scope="module")
def welt():
    """Zwei Mandanten, drei Benutzer.

    alpha@bc0.test ist Mandant Alpha zugeordnet, ohne@bc0.test keinem.
    """
    client = TestClient(anwendung.app)

    anwendung.AUTH.benutzer_anlegen("f-admin@bc0.test", "Admin", PW_ADMIN, Rolle.ADMIN)
    client.post("/api/auth/login", json={"email": "f-admin@bc0.test", "passwort": PW_ADMIN})

    alpha = client.post("/api/companies", json={"name": "Alpha GmbH", "kps": [0]}).json()["id"]
    beta = client.post("/api/companies", json={"name": "Beta GmbH", "kps": [0]}).json()["id"]

    nutzer_alpha = anwendung.AUTH.benutzer_anlegen(
        "alpha@bc0.test", "Alpha-Nutzer", PW_ALPHA, Rolle.BENUTZER, mandanten=[str(alpha)]
    )
    anwendung.AUTH.benutzer_anlegen("ohne@bc0.test", "Ohne", PW_OHNE, Rolle.BENUTZER)

    client.cookies.clear()
    return {"client": client, "alpha": str(alpha), "beta": str(beta), "nutzer_alpha": nutzer_alpha}


def _als(welt, email, passwort) -> TestClient:
    client = welt["client"]
    client.cookies.clear()
    antwort = client.post("/api/auth/login", json={"email": email, "passwort": passwort})
    assert antwort.status_code == 200, antwort.text
    return client


# --------------------------------------------------------------------------- #
# Sehen
# --------------------------------------------------------------------------- #
def test_benutzer_sieht_nur_seinen_mandanten(welt):
    client = _als(welt, "alpha@bc0.test", PW_ALPHA)
    ids = [str(m["id"]) for m in client.get("/api/companies").json()]
    assert welt["alpha"] in ids
    assert welt["beta"] not in ids


def test_admin_sieht_alle_mandanten(welt):
    client = _als(welt, "f-admin@bc0.test", PW_ADMIN)
    ids = [str(m["id"]) for m in client.get("/api/companies").json()]
    assert welt["alpha"] in ids and welt["beta"] in ids


def test_benutzer_ohne_zuordnung_sieht_nichts(welt):
    """Kein Fehler, sondern eine leere Liste — und damit eine ehrliche Antwort."""
    client = _als(welt, "ohne@bc0.test", PW_OHNE)
    assert client.get("/api/companies").json() == []


# --------------------------------------------------------------------------- #
# Zugriff auf einen fremden Mandanten
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "pfad",
    ["", "/report", "/documents"],
)
def test_fremder_mandant_wird_mit_404_abgewiesen(welt, pfad):
    client = _als(welt, "alpha@bc0.test", PW_ALPHA)
    antwort = client.get("/api/companies/" + welt["beta"] + pfad)
    assert antwort.status_code == 404


def test_eigener_mandant_bleibt_erreichbar(welt):
    client = _als(welt, "alpha@bc0.test", PW_ALPHA)
    assert client.get("/api/companies/" + welt["alpha"]).status_code == 200
    assert client.get("/api/companies/" + welt["alpha"] + "/report").status_code == 200


def test_schreiben_auf_fremden_mandanten_wird_abgewiesen(welt):
    """Der eigentliche Punkt der Etappe: kein Schreibzugriff über die Grenze."""
    client = _als(welt, "alpha@bc0.test", PW_ALPHA)
    antwort = client.put(
        "/api/companies/" + welt["beta"] + "/profile",
        json={"name": "Uebernommen", "geschaeftsmodell": "x", "tech_stack": "y"},
    )
    assert antwort.status_code == 404

    antwort = client.post(
        "/api/companies/" + welt["beta"] + "/process/add", json={"kp_index": 1}
    )
    assert antwort.status_code == 404

    antwort = client.post(
        "/api/companies/" + welt["beta"] + "/rating",
        json={"key": "KP-01.TP-1", "items": {"1": {"stufe": 5, "beleg": "erfunden"}}},
    )
    assert antwort.status_code == 404


def test_schreiben_auf_eigenen_mandanten_geht(welt):
    client = _als(welt, "alpha@bc0.test", PW_ALPHA)
    antwort = client.put(
        "/api/companies/" + welt["alpha"] + "/profile",
        json={"name": "Alpha GmbH", "geschaeftsmodell": "Beratung", "tech_stack": "Python"},
    )
    assert antwort.status_code == 200


# --------------------------------------------------------------------------- #
# Neue Mandanten anlegen
# --------------------------------------------------------------------------- #
def test_benutzer_darf_keinen_mandanten_anlegen(welt):
    """Sonst wäre die Mandantentrennung umgehbar: Wer sich selbst Mandanten
    schafft, braucht keine Zuordnung mehr."""
    client = _als(welt, "alpha@bc0.test", PW_ALPHA)
    assert client.post("/api/companies", json={"name": "Eigenmaechtig", "kps": []}).status_code == 403


def test_benutzer_darf_kein_yaml_importieren(welt):
    client = _als(welt, "alpha@bc0.test", PW_ALPHA)
    antwort = client.post("/api/import_yaml", content="company:\n  name: Schmuggel\n")
    assert antwort.status_code == 403


def test_admin_darf_mandanten_anlegen(welt):
    client = _als(welt, "f-admin@bc0.test", PW_ADMIN)
    assert client.post("/api/companies", json={"name": "Gamma GmbH", "kps": []}).status_code == 200


# --------------------------------------------------------------------------- #
# Wirksamkeit von Änderungen an der Zuordnung
# --------------------------------------------------------------------------- #
def test_entzogene_zuordnung_wirkt_sofort(welt):
    """Ohne Neuanmeldung — der Benutzer wird bei jeder Anfrage frisch geladen."""
    client = _als(welt, "alpha@bc0.test", PW_ALPHA)
    assert client.get("/api/companies/" + welt["alpha"]).status_code == 200

    anwendung.AUTH.benutzer.mandanten_setzen(welt["nutzer_alpha"].benutzer_id, [])
    assert client.get("/api/companies/" + welt["alpha"]).status_code == 404
    assert client.get("/api/companies").json() == []

    # Zustand für andere Tests wiederherstellen
    anwendung.AUTH.benutzer.mandanten_setzen(welt["nutzer_alpha"].benutzer_id, [welt["alpha"]])
    assert client.get("/api/companies/" + welt["alpha"]).status_code == 200
