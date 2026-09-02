# -*- coding: utf-8 -*-
"""Tests für das, was BC0 an BC1 schuldet: Zuordnung, Status, Kanten.

**Der Anlass.** BC1 braucht Schreibzugriff auf Tabellen in ``public``, und
dort schreibt nach ADR-003 Regel 1 niemand ausser BC0. Der naheliegende
Ausweg — ein ``GRANT UPDATE`` an ``bc1_role`` — wurde am 26.08.2026
ausdruecklich verworfen: *Die Regel ist nur so viel wert, wie sie ohne
Ausnahmen gilt.* Diese drei Endpunkte sind die Gegenleistung dafuer.

**Was hier geprueft wird, ist nicht, ob sie antworten**, sondern ob sie die
Regeln durchsetzen, um derentwillen sie gebaut wurden:

* Ohne Prozessbezug kein Fortschritt (Schema v2.3, Entscheidung vom 28.08.)
* Herkunft ist Pflicht, sobald ein Bezug entsteht (ADR-005 R2)
* Zuordnen und Fortschreiten sind zwei Entscheidungen, nicht eine
* Die Kette laeuft vorwaerts; Berichtigungen sollen sichtbar sein
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "weitergabe-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("weitergabe@bc0.test", "Weitergabe-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "weitergabe@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies",
                           json={"name": "Weitergabe GmbH", "kps": [0, 1, 2]}).json()["id"])


def _anfrage(client, mandant, **felder) -> str:
    """Legt eine Anfrage an und gibt ihre ID zurueck."""
    daten = {"originaltext": "Irgendetwas dauert zu lange."}
    daten.update(felder)
    r = client.post("/api/companies/%s/anfragen" % mandant, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["anfrage_id"]


# ===========================================================================
# Zuordnung
# ===========================================================================

def test_zuordnung_traegt_prozessbezug_nach(client, mandant):
    """Der Regelfall: Eine Anfrage ohne Bezug bekommt ihn aus dem Interview."""
    aid = _anfrage(client, mandant)
    r = client.put("/api/companies/%s/anfragen/%s/zuordnung" % (mandant, aid),
                   json={"process_id": "KP-02", "sub_process_id": "KP-02.TP-1",
                         "zuordnung_quelle": "interview"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["process_id"] == "KP-02"
    assert d["sub_process_id"] == "KP-02.TP-1"
    assert d["zuordnung_quelle"] == "interview"
    # Der Status bleibt, wo er war — zuordnen ist nicht fortschreiten.
    assert d["status"] == "eingegangen"


def test_zuordnung_ohne_herkunft_wird_abgewiesen(client, mandant):
    """ADR-005 R2: Ein Wert ohne Herkunft ist kein Wert.

    Ohne diese Pruefung schluege ``ck_anfrage_bezug_paarweise`` in der
    Datenbank zu — mit einer Meldung, aus der niemand ableiten kann, was zu
    tun ist.
    """
    aid = _anfrage(client, mandant)
    r = client.put("/api/companies/%s/anfragen/%s/zuordnung" % (mandant, aid),
                   json={"process_id": "KP-02"})
    assert r.status_code == 400
    assert "Herkunft" in r.json()["detail"]


def test_zuordnung_prueft_dass_der_teilprozess_zum_kernprozess_gehoert(client, mandant):
    """`KP-01.TP-1` unter `KP-02` ist kein Bezug, sondern ein Fehler.

    Genau diese Sorte Fehlzuordnung stand am 07.08.2026 wochenlang unbemerkt
    in den Mockdaten (`KP-01.TP-01` gegen `KP-01.TP-1`) — ein Join ueber nicht
    passende IDs liefert kein Fehlersignal, sondern ein leeres Ergebnis.
    """
    aid = _anfrage(client, mandant)
    r = client.put("/api/companies/%s/anfragen/%s/zuordnung" % (mandant, aid),
                   json={"process_id": "KP-02", "sub_process_id": "KP-01.TP-1",
                         "zuordnung_quelle": "interview"})
    assert r.status_code == 400
    assert "gehoert nicht" in r.json()["detail"]


def test_zuordnung_weist_unbekannte_herkunft_ab(client, mandant):
    """Die vier Quellen trennen vier Ursachen — eine fuenfte gibt es nicht."""
    aid = _anfrage(client, mandant)
    r = client.put("/api/companies/%s/anfragen/%s/zuordnung" % (mandant, aid),
                   json={"process_id": "KP-02", "zuordnung_quelle": "geraten"})
    assert r.status_code == 400


# ===========================================================================
# Status
# ===========================================================================

def test_status_ohne_prozessbezug_wird_abgewiesen(client, mandant):
    """**Die Regel vom 28.08.: ohne Prozess kein Fortschritt.**

    Die Datenbank haelt das mit ``ck_anfrage_fortschritt_braucht_prozess``
    ohnehin durch. Ein Constraint-Fehler ist aber keine Antwort, mit der ein
    Aufrufer etwas anfangen kann — hier steht ein Satz, der sagt, was zu tun
    ist.
    """
    aid = _anfrage(client, mandant)
    r = client.put("/api/companies/%s/anfragen/%s/status" % (mandant, aid),
                   json={"status": "im_interview"})
    assert r.status_code == 400
    hinweis = r.json()["detail"]
    assert "zuordnen" in hinweis, "Die Meldung sagt nicht, was zu tun ist: %s" % hinweis


def test_status_nach_zuordnung_laeuft(client, mandant):
    """Zugeordnet, dann im Interview — die Kette, um die es geht."""
    aid = _anfrage(client, mandant)
    client.put("/api/companies/%s/anfragen/%s/zuordnung" % (mandant, aid),
               json={"process_id": "KP-03", "zuordnung_quelle": "vorschlag_bc1"})
    r = client.put("/api/companies/%s/anfragen/%s/status" % (mandant, aid),
                   json={"status": "im_interview"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "im_interview"
    assert r.json()["status_alt"] == "eingegangen"


def test_status_kein_rueckschritt(client, mandant):
    """Wer zurueck will, hat eine Berichtigung vor — und die soll sichtbar sein."""
    aid = _anfrage(client, mandant)
    client.put("/api/companies/%s/anfragen/%s/zuordnung" % (mandant, aid),
               json={"process_id": "KP-03", "zuordnung_quelle": "interview"})
    client.put("/api/companies/%s/anfragen/%s/status" % (mandant, aid),
               json={"status": "im_interview"})
    r = client.put("/api/companies/%s/anfragen/%s/status" % (mandant, aid),
                   json={"status": "eingegangen"})
    assert r.status_code == 400
    assert "Rueckschritt" in r.json()["detail"]


def test_abgelehnt_ist_von_ueberall_erreichbar(client, mandant):
    """Ein Anliegen kann jederzeit sein Ende finden — auch mitten im Lauf."""
    aid = _anfrage(client, mandant)
    client.put("/api/companies/%s/anfragen/%s/zuordnung" % (mandant, aid),
               json={"process_id": "KP-03", "zuordnung_quelle": "interview"})
    client.put("/api/companies/%s/anfragen/%s/status" % (mandant, aid),
               json={"status": "am_gate"})
    r = client.put("/api/companies/%s/anfragen/%s/status" % (mandant, aid),
                   json={"status": "abgelehnt"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "abgelehnt"


def test_status_weist_unbekannten_wert_ab(client, mandant):
    """Und die Meldung nennt die erlaubten — sonst raet der Aufrufer."""
    aid = _anfrage(client, mandant)
    r = client.put("/api/companies/%s/anfragen/%s/status" % (mandant, aid),
                   json={"status": "laeuft_irgendwie"})
    assert r.status_code == 400
    assert "eingegangen" in r.json()["detail"]


def test_unbekannte_anfrage_gibt_404(client, mandant):
    """Nicht 400: Der Aufruf ist richtig gebaut, das Ziel gibt es nicht."""
    r = client.put("/api/companies/%s/anfragen/A-1999-99/status" % mandant,
                   json={"status": "abgelehnt"})
    assert r.status_code == 404


# ===========================================================================
# Kanten
# ===========================================================================

def test_kante_wird_angelegt(client, mandant):
    """BC0 erhebt, BC1 ergaenzt — der Weg dafuer."""
    r = client.post("/api/companies/%s/prozesskanten" % mandant,
                    json={"von_process_id": "KP-01", "nach_process_id": "KP-02",
                          "art": "freigabe", "beschreibung": "aus dem Interview"})
    assert r.status_code == 200, r.text
    assert r.json()["neu"] is True


def test_kante_zweimal_anlegen_ist_kein_fehler(client, mandant):
    """Wer zweimal dasselbe meldet, soll keine Fehlermeldung bekommen."""
    daten = {"von_process_id": "KP-02", "nach_process_id": "KP-03", "art": "daten"}
    client.post("/api/companies/%s/prozesskanten" % mandant, json=daten)
    r = client.post("/api/companies/%s/prozesskanten" % mandant, json=daten)
    assert r.status_code == 200, r.text
    assert r.json()["neu"] is False


def test_kante_braucht_eine_art(client, mandant):
    """Die Art steht im Primaerschluessel — ohne sie ist die Kante nicht speicherbar.

    Im Interview ist das ohnehin die bessere Frage: *Was fliesst zwischen den
    beiden?* trennt schaerfer als *was kommt danach?*
    """
    r = client.post("/api/companies/%s/prozesskanten" % mandant,
                    json={"von_process_id": "KP-01", "nach_process_id": "KP-03"})
    assert r.status_code == 400
    assert "Art" in r.json()["detail"]


def test_kante_auf_sich_selbst_wird_abgewiesen(client, mandant):
    """Ein Prozess ist nicht sein eigener Nachfolger — die DB haelt es auch, aber lautlos."""
    r = client.post("/api/companies/%s/prozesskanten" % mandant,
                    json={"von_process_id": "KP-01", "nach_process_id": "KP-01",
                          "art": "daten"})
    assert r.status_code == 400


def test_kante_prueft_beide_prozesse(client, mandant):
    """Ein Fremdschluessel faenge es auch — aber erst beim Schreiben, mit einer
    Meldung, die den Aufrufer nicht weiterbringt."""
    r = client.post("/api/companies/%s/prozesskanten" % mandant,
                    json={"von_process_id": "KP-01", "nach_process_id": "KP-99",
                          "art": "daten"})
    assert r.status_code == 400
    assert "KP-99" in r.json()["detail"]
