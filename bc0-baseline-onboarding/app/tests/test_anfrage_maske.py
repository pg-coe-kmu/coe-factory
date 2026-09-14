# -*- coding: utf-8 -*-
"""
Tests für die Anfragemaske (28.08.2026).

Der Anlass ist ein Fehler, den kein bestehender Test gefunden hätte:
`schema_v2.1` hat am 27.08. `process_id` und `zuordnung_quelle` auf NOT NULL
gesetzt, der Endpunkt `POST …/anfragen` schrieb beide Spalten aber nicht. In
der Produktivdatenbank war das Anlegen einer Anfrage damit zwei Tage lang
unmöglich — **stillschweigend**, weil niemand den Knopf drückte.

Die Testsammlung konnte es nicht sehen: Sie läuft auf SQLite, und dort stand
die Pflicht nicht. Deshalb prüfen die Tests hier nicht nur das Verhalten des
Endpunkts, sondern **auch, dass die SQLite-Tabelle dieselben Spalten und
dieselben Bedingungen trägt wie die Postgres-Tabelle**. Ein Test, der auf einer
anderen Tabelle läuft als der Betrieb, sichert nichts.

Die fachliche Regel, die hier geprüft wird, ist die Entscheidung vom 28.08.
(Schema v2.3):

    Eine Anfrage darf OHNE Prozessbezug **entstehen** — „weiß ich nicht" ist
    erlaubt und ausdrücklich besser als ein geratener Prozess.
    Sie darf ohne Bezug nicht **weiterlaufen**.

Aus „ohne Prozess keine Anfrage" wird damit „ohne Prozess kein Fortschritt".
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "anfrage-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("anfrage-admin@bc0.test", "Anfrage-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "anfrage-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies",
                           json={"name": "Anfrage GmbH", "kps": [0, 1]}).json()["id"])


# --------------------------------------------------------------------------
# Der Regelfall und der Fall, um den es geht
# --------------------------------------------------------------------------

def test_anfrage_mit_prozessbezug(client, mandant):
    """Der vollständige Weg: Anliegen, Ziel, Auslöser, Umfang, Prozess, Schritt."""
    r = client.post("/api/companies/%s/anfragen" % mandant, json={
        "originaltext": "Die Reisebuchung laeuft ueber drei Mails und eine Excel-Liste.",
        "erhofftes_ziel": "Nicht mehr am Wochenende abrechnen.",
        "ausloeser": "Die Kollegin geht Ende September.",
        "umfang_geschaetzt": "etwa zwoelf Leute, jeden Monatsanfang",
        "process_id": "KP-01",
        "sub_process_id": "KP-01.TP-1",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["process_id"] == "KP-01"
    # Herkunft wird gesetzt, nicht erwartet: Wer ueber die Maske kommt, hat den
    # Prozess selbst gewaehlt. Ohne sie schluege ck_anfrage_bezug_paarweise zu.
    assert d["zuordnung_quelle"] == "anfrage"
    assert d["status"] == "eingegangen"


def test_anfrage_ohne_prozessbezug_wird_angenommen(client, mandant):
    """„Weiß ich nicht" ist erlaubt — das ist der Kern der Entscheidung vom 28.08.

    Ein Fachbereichsmensch kennt `KP-06.TP-2` nicht. Zwänge ihn die Maske zur
    Auswahl, klickte er auf gut Glück — und BC1 führte ein vollständiges
    Interview auf dem falschen Prozess. Das fällt erst am Gate auf, und dann ist
    die Arbeit getan.
    """
    r = client.post("/api/companies/%s/anfragen" % mandant,
                    json={"originaltext": "Irgendetwas mit den Rechnungen dauert zu lange."})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["process_id"] is None
    assert d["zuordnung_quelle"] is None
    assert d["status"] == "eingegangen"


def test_eingang_weg_faellt_auf_pwa(client, mandant):
    """Der einzige Hinweis darauf, ob eine Anfrage aus der Maske stammt."""
    client.post("/api/companies/%s/anfragen" % mandant,
                json={"originaltext": "Ohne Angabe des Weges."})
    zeilen = client.get("/api/companies/%s/anfragen" % mandant).json()["anfragen"]
    assert zeilen[0]["eingang_weg"] == "pwa"


def test_originaltext_ist_pflicht(client, mandant):
    r = client.post("/api/companies/%s/anfragen" % mandant, json={"originaltext": "   "})
    assert r.status_code == 400
    assert "Originaltext" in r.json()["detail"]


# --------------------------------------------------------------------------
# Die Grenzen — jede mit 400 und einem lesbaren Satz, nie mit 500
# --------------------------------------------------------------------------

def test_unbekannter_kernprozess(client, mandant):
    r = client.post("/api/companies/%s/anfragen" % mandant,
                    json={"originaltext": "x", "process_id": "KP-99"})
    assert r.status_code == 400
    assert "KP-99" in r.json()["detail"]


def test_teilprozess_aus_fremdem_kernprozess(client, mandant):
    """`KP-02.TP-1` unter `KP-01` ist kein Bezug, sondern ein Tippfehler."""
    r = client.post("/api/companies/%s/anfragen" % mandant,
                    json={"originaltext": "x", "process_id": "KP-01",
                          "sub_process_id": "KP-02.TP-1"})
    assert r.status_code == 400
    assert "gehoert nicht" in r.json()["detail"]


def test_teilprozess_ohne_kernprozess(client, mandant):
    r = client.post("/api/companies/%s/anfragen" % mandant,
                    json={"originaltext": "x", "sub_process_id": "KP-01.TP-1"})
    assert r.status_code == 400


def test_unbekannte_zuordnungsquelle(client, mandant):
    r = client.post("/api/companies/%s/anfragen" % mandant,
                    json={"originaltext": "x", "process_id": "KP-01",
                          "zuordnung_quelle": "geraten"})
    assert r.status_code == 400
    assert "geraten" in r.json()["detail"]


def test_quelle_ohne_bezug_wird_abgewiesen(client, mandant):
    """Eine Herkunftsangabe ohne Bezug beschreibt nichts (ck_anfrage_bezug_paarweise)."""
    r = client.post("/api/companies/%s/anfragen" % mandant,
                    json={"originaltext": "x", "zuordnung_quelle": "anfrage"})
    assert r.status_code == 400


# --------------------------------------------------------------------------
# Die Lesesicht
# --------------------------------------------------------------------------

def test_liste_liefert_die_neuen_felder(client, mandant):
    """Ohne Status ist die Anfrage ein Eintrag ohne Leben."""
    zeilen = client.get("/api/companies/%s/anfragen" % mandant).json()["anfragen"]
    assert zeilen, "es wurde mindestens eine Anfrage angelegt"
    for feld in ("status", "process_id", "sub_process_id", "zuordnung_quelle",
                 "erhofftes_ziel", "ausloeser", "umfang_geschaetzt"):
        assert feld in zeilen[0], "Feld %s fehlt in der Liste" % feld


def test_meta_nennt_quellen_und_status(client):
    m = client.get("/api/meta").json()
    assert m["zuordnung_quellen"] == ["anfrage", "vorschlag_bc0", "vorschlag_bc1", "interview"]
    assert m["anfrage_status"][0] == "eingegangen"
    # Gate 0 steht ZWISCHEN Interview und ROI-Rechnung, nicht dahinter.
    assert m["anfrage_status"].index("am_gate") < m["anfrage_status"].index("bewertet")


# --------------------------------------------------------------------------
# Die Tabelle, auf der die Tests laufen, muss die des Betriebs sein
# --------------------------------------------------------------------------

def test_sqlite_tabelle_traegt_dieselben_spalten():
    """Der Test, der den Fehler vom 27.08. gefunden haette.

    Er prueft nicht Verhalten, sondern eine Voraussetzung: dass die
    SQLite-Tabelle dieselben Spalten kennt wie die Postgres-Tabelle. Waere das
    am 27.08. geprueft worden, waere aufgefallen, dass `process_id` in der
    einen Pflicht ist und in der anderen nicht existiert.
    """
    for ddl in (anwendung.GATE0_DDL_SQLITE, anwendung.GATE0_DDL_PG):
        # Der Abschnitt bis zur naechsten CREATE-Anweisung. Bewusst per split
        # und nicht per Regex auf die schliessende Klammer: Die beiden DDLs
        # setzen sie unterschiedlich (");" gegen "));"), und ein Test, der an
        # einem Leerzeichen scheitert, wird beim naechsten Mal geloescht statt
        # gelesen.
        block = ddl.split("CREATE TABLE IF NOT EXISTS ref_anfragen", 1)[1]
        # Am Zeilenanfang, sonst schneidet ein Kommentar, der das Wort
        # enthaelt, den Block mitten entzwei.
        block = block.split("\nCREATE TABLE", 1)[0]
        for spalte in ("process_id", "sub_process_id", "zuordnung_quelle", "status",
                       "status_seit", "erhofftes_ziel", "ausloeser", "umfang_geschaetzt"):
            assert spalte in block, "%s fehlt in einer der beiden DDLs" % spalte
        # Und die Regel selbst, in beiden Backends gleich formuliert.
        assert "process_id IS NOT NULL OR status = 'eingegangen'" in block
