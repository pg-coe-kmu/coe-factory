# -*- coding: utf-8 -*-
"""
Zugriffstests gegen die laufende Anwendung.

Während ``test_auth.py`` die Bausteine einzeln prüft, geht es hier um die Frage,
die am Ende zählt: **Kommt jemand ohne Anmeldung an die Daten?**

Die Tests sprechen die vollständige Anwendung über den FastAPI-Testclient an,
also mit Middleware, Router und Cookie-Behandlung. Grundlage ist eine leere
SQLite-Datei in einem temporären Verzeichnis (siehe ``conftest.py``).
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402  — conftest.py hat die Umgebung vorbereitet
from bc0_auth import Rolle  # noqa: E402

PASSWORT_ADMIN = "admin-passwort-2026"
PASSWORT_NUTZER = "nutzer-passwort-2026"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Ein Testclient mit einem Admin und einem einfachen Benutzer."""
    anwendung.AUTH.benutzer_anlegen("admin@bc0.test", "Admin", PASSWORT_ADMIN, Rolle.ADMIN)
    anwendung.AUTH.benutzer_anlegen("nutzer@bc0.test", "Nutzer", PASSWORT_NUTZER, Rolle.BENUTZER)
    return TestClient(anwendung.app)


def _anmelden(client: TestClient, email: str, passwort: str) -> TestClient:
    antwort = client.post("/api/auth/login", json={"email": email, "passwort": passwort})
    assert antwort.status_code == 200, antwort.text
    return client


# --------------------------------------------------------------------------- #
# Ohne Anmeldung
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "pfad",
    [
        "/api/meta",
        "/api/companies",
        "/api/auth/me",
        "/api/auth/benutzer",
    ],
)
def test_api_ist_ohne_anmeldung_gesperrt(client, pfad):
    """Der Kern der Etappe 4a: kein Datenzugriff ohne Sitzung."""
    client.cookies.clear()
    assert client.get(pfad).status_code == 401


def test_schreibender_zugriff_ist_ohne_anmeldung_gesperrt(client):
    """Bis zum 10.08.2026 war genau das möglich — von jedem, ohne Anmeldung."""
    client.cookies.clear()
    antwort = client.post("/api/companies", json={"name": "Fremdeintrag", "kps": []})
    assert antwort.status_code == 401


def test_unbekannter_api_pfad_ist_ebenfalls_gesperrt(client):
    """Die Sperre gilt für das gesamte Präfix, nicht für eine Liste von Endpunkten.

    Damit ist auch ein künftiger, noch nicht geschriebener Endpunkt geschützt.
    """
    client.cookies.clear()
    assert client.get("/api/irgendetwas-neues").status_code == 401


def test_oberflaeche_bleibt_erreichbar(client):
    """Die PWA-Hülle muss ausgeliefert werden — sonst gäbe es keine Anmeldemaske."""
    client.cookies.clear()
    for pfad in ("/", "/manifest.json", "/sw.js"):
        assert client.get(pfad).status_code == 200


def test_status_gibt_ohne_anmeldung_auskunft(client):
    client.cookies.clear()
    daten = client.get("/api/auth/status").json()
    assert daten["angemeldet"] is False
    assert daten["eingerichtet"] is True
    assert daten["benutzer"] is None


def test_falsche_zugangsdaten(client):
    client.cookies.clear()
    antwort = client.post(
        "/api/auth/login", json={"email": "admin@bc0.test", "passwort": "falsch-aber-lang"}
    )
    assert antwort.status_code == 401


# --------------------------------------------------------------------------- #
# Mit Anmeldung
# --------------------------------------------------------------------------- #
def test_anmeldung_oeffnet_die_api(client):
    client.cookies.clear()
    _anmelden(client, "admin@bc0.test", PASSWORT_ADMIN)
    assert client.get("/api/meta").status_code == 200
    assert client.get("/api/companies").status_code == 200


def test_sitzungsschluessel_steht_nicht_in_der_antwort(client):
    """Der Schlüssel gehört ins HttpOnly-Cookie, nicht in den Antwortkörper.

    Stünde er im JSON, könnte ihn ein Skript in der Seite auslesen — und der
    Schutz durch HttpOnly wäre wirkungslos.
    """
    client.cookies.clear()
    antwort = client.post(
        "/api/auth/login", json={"email": "admin@bc0.test", "passwort": PASSWORT_ADMIN}
    )
    inhalt = antwort.json()
    assert "bc0_sitzung" in antwort.cookies or "bc0_sitzung" in client.cookies
    assert "schluessel" not in antwort.text.lower()
    assert "passwort" not in str(inhalt).lower()


def test_eigenes_konto_wird_ohne_hash_ausgeliefert(client):
    client.cookies.clear()
    _anmelden(client, "nutzer@bc0.test", PASSWORT_NUTZER)
    daten = client.get("/api/auth/me").json()
    assert daten["email"] == "nutzer@bc0.test"
    assert daten["ist_admin"] is False
    assert "passwort_hash" not in daten


def test_benutzerverwaltung_ist_admins_vorbehalten(client):
    client.cookies.clear()
    _anmelden(client, "nutzer@bc0.test", PASSWORT_NUTZER)
    assert client.get("/api/auth/benutzer").status_code == 403
    assert client.post(
        "/api/auth/benutzer",
        json={"email": "neu@bc0.test", "name": "Neu", "passwort": "langes-passwort-123"},
    ).status_code == 403


def test_admin_darf_benutzer_verwalten(client):
    client.cookies.clear()
    _anmelden(client, "admin@bc0.test", PASSWORT_ADMIN)
    assert client.get("/api/auth/benutzer").status_code == 200


def test_admin_kann_sich_nicht_selbst_herabstufen(client):
    """Sonst könnte der letzte Admin die Anwendung führungslos machen."""
    client.cookies.clear()
    _anmelden(client, "admin@bc0.test", PASSWORT_ADMIN)
    ich = client.get("/api/auth/me").json()
    antwort = client.put("/api/auth/benutzer/" + ich["benutzer_id"], json={"rolle": "benutzer"})
    assert antwort.status_code == 400


def test_abmelden_beendet_den_zugang(client):
    client.cookies.clear()
    _anmelden(client, "admin@bc0.test", PASSWORT_ADMIN)
    assert client.get("/api/meta").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/meta").status_code == 401
