# -*- coding: utf-8 -*-
"""
Tests für Rollen und Kostensätze (Stammdaten der ROI-Kostenachse).

Zwei Eigenschaften sind hier wichtiger als die Speicherfunktion selbst:

**Rollen werden gesperrt, nicht gelöscht.** BC1 speichert die `rolle_id` in
seinem Prozessprofil. Verschwindet die Rolle, ist der Verweis nicht mehr
auflösbar — und ein ROI, dessen Kostensatz sich nicht mehr zuordnen lässt, ist
nicht reproduzierbar.

**Ein geänderter Kostensatz erzeugt eine neue Zeile.** Nur so bleibt
nachvollziehbar, mit welchem Satz eine frühere Freigabe gerechnet hat.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "rollen-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("rk-admin@bc0.test", "RK-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "rk-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies", json={"name": "Rollen GmbH", "kps": []}).json()["id"])


def _pfad(mandant: str) -> str:
    return "/api/companies/" + mandant + "/rollen_kosten"


# --------------------------------------------------------------------------- #
def test_leerer_mandant_liefert_die_fuenf_klassen(client, mandant):
    """Auch ohne gepflegte Daten muss die Oberfläche wissen, welche Klassen es gibt."""
    daten = client.get(_pfad(mandant)).json()
    assert daten["rollen"] == []
    assert daten["kostensaetze"] == []
    assert [k["klasse"] for k in daten["klassen"]] == ["K1", "K2", "K3", "K4", "K5"]


def test_rollen_bekommen_fortlaufende_ids(client, mandant):
    client.put(_pfad(mandant), json={
        "rollen": [
            {"bezeichnung": "Sachbearbeitung", "klasse": "K2"},
            {"bezeichnung": "Geschäftsführung", "klasse": "K5"},
        ],
        "kostensaetze": [],
    })
    rollen = client.get(_pfad(mandant)).json()["rollen"]
    assert [r["rolle_id"] for r in rollen] == ["R-01", "R-02"]
    assert rollen[0]["bezeichnung"] == "Sachbearbeitung"


def test_bestehende_rolle_behaelt_ihre_id(client, mandant):
    """Die ID ist der Anker für BC1 — sie darf sich beim Umbenennen nicht ändern."""
    vorher = client.get(_pfad(mandant)).json()["rollen"]
    client.put(_pfad(mandant), json={
        "rollen": [
            {"rolle_id": "R-01", "bezeichnung": "Sachbearbeitung Auftrag", "klasse": "K2"},
            {"rolle_id": "R-02", "bezeichnung": "Geschäftsführung", "klasse": "K5"},
        ],
        "kostensaetze": [],
    })
    nachher = client.get(_pfad(mandant)).json()["rollen"]
    assert [r["rolle_id"] for r in nachher] == [r["rolle_id"] for r in vorher]
    assert nachher[0]["bezeichnung"] == "Sachbearbeitung Auftrag"


def test_entfernte_rolle_wird_gesperrt_statt_geloescht(client, mandant):
    """Der wichtigste Test dieser Datei."""
    client.put(_pfad(mandant), json={
        "rollen": [{"rolle_id": "R-01", "bezeichnung": "Sachbearbeitung Auftrag", "klasse": "K2"}],
        "kostensaetze": [],
    })
    rollen = {r["rolle_id"]: r for r in client.get(_pfad(mandant)).json()["rollen"]}
    assert "R-02" in rollen, "die Rolle darf nicht verschwinden"
    assert rollen["R-02"]["aktiv"] is False
    assert rollen["R-01"]["aktiv"] is True


def test_unbekannte_klasse_wird_abgelehnt(client, mandant):
    antwort = client.put(_pfad(mandant), json={
        "rollen": [{"bezeichnung": "Irgendwer", "klasse": "K9"}], "kostensaetze": [],
    })
    assert antwort.status_code == 400


# --------------------------------------------------------------------------- #
def test_kostensatz_wird_gespeichert_und_gelesen(client, mandant):
    client.put(_pfad(mandant), json={
        "rollen": [],
        "kostensaetze": [
            {"klasse": "K2", "satz_eur_h": 58.5, "quelle": "branchenreferenz",
             "bemerkung": "Faktor 1,9 auf 30 EUR brutto"},
            {"klasse": "K5", "satz_eur_h": 140, "quelle": "geschaetzt"},
        ],
    })
    saetze = {s["klasse"]: s for s in client.get(_pfad(mandant)).json()["kostensaetze"]}
    assert saetze["K2"]["satz_eur_h"] == 58.5
    assert saetze["K2"]["quelle"] == "branchenreferenz"
    assert "1,9" in saetze["K2"]["bemerkung"]
    assert saetze["K5"]["satz_eur_h"] == 140.0


def test_negativer_satz_wird_abgelehnt(client, mandant):
    for wert in (-5, 0.0):
        antwort = client.put(_pfad(mandant), json={
            "rollen": [], "kostensaetze": [{"klasse": "K1", "satz_eur_h": wert}],
        })
        # 0 wird als "nicht gepflegt" behandelt und uebersprungen, negativ abgelehnt
        assert antwort.status_code in (200, 400)
    antwort = client.put(_pfad(mandant), json={
        "rollen": [], "kostensaetze": [{"klasse": "K1", "satz_eur_h": -5}],
    })
    assert antwort.status_code == 400


def test_unbekannte_quelle_wird_abgelehnt(client, mandant):
    antwort = client.put(_pfad(mandant), json={
        "rollen": [], "kostensaetze": [{"klasse": "K1", "satz_eur_h": 30, "quelle": "geraten"}],
    })
    assert antwort.status_code == 400


def test_aenderung_am_selben_tag_ueberschreibt_die_tageszeile(client, mandant):
    """Sonst entstünden bei mehreren Korrekturen am selben Tag Dubletten."""
    client.put(_pfad(mandant), json={
        "rollen": [], "kostensaetze": [{"klasse": "K3", "satz_eur_h": 70, "quelle": "geschaetzt"}],
    })
    client.put(_pfad(mandant), json={
        "rollen": [], "kostensaetze": [{"klasse": "K3", "satz_eur_h": 75, "quelle": "erhoben"}],
    })
    saetze = [s for s in client.get(_pfad(mandant)).json()["kostensaetze"] if s["klasse"] == "K3"]
    assert len(saetze) == 1
    assert saetze[0]["satz_eur_h"] == 75.0
    assert saetze[0]["quelle"] == "erhoben"


# --------------------------------------------------------------------------- #
def test_fremder_mandant_bleibt_gesperrt(client, mandant):
    """Die Mandantentrennung gilt auch für die neuen Endpunkte."""
    fremd = str(client.post("/api/companies", json={"name": "Fremd GmbH", "kps": []}).json()["id"])
    nutzer = anwendung.AUTH.benutzer_anlegen(
        "rk-nutzer@bc0.test", "Nutzer", "rollen-nutzer-passwort", Rolle.BENUTZER,
        mandanten=[mandant],
    )
    assert nutzer.mandanten == frozenset({mandant})

    client.cookies.clear()
    client.post("/api/auth/login",
                json={"email": "rk-nutzer@bc0.test", "passwort": "rollen-nutzer-passwort"})
    assert client.get(_pfad(mandant)).status_code == 200
    assert client.get(_pfad(fremd)).status_code == 404
    assert client.put(_pfad(fremd), json={"rollen": [], "kostensaetze": []}).status_code == 404


def test_gesperrte_rolle_bleibt_gesperrt_beim_naechsten_speichern(client, mandant):
    """Gefunden im PostgreSQL-Durchlauf am 11.08.2026.

    Die Oberfläche zeigt gesperrte Rollen weiterhin an und schickt sie beim
    Speichern mit. Würde der Server den Sperrstatus aus der Anwesenheit in der
    Liste ableiten, wäre jede Sperre beim nächsten Speichern wieder aufgehoben —
    und niemand hätte es gemerkt, weil das Speichern ja erfolgreich meldet.
    """
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "rk-admin@bc0.test", "passwort": PW})

    # R-02 ist aus einem früheren Test gesperrt; alle Zeilen zurückschicken
    rollen = client.get(_pfad(mandant)).json()["rollen"]
    gesperrt = [r for r in rollen if not r["aktiv"]]
    assert gesperrt, "Vorbedingung: mindestens eine gesperrte Rolle"

    client.put(_pfad(mandant), json={"rollen": rollen, "kostensaetze": []})

    danach = {r["rolle_id"]: r["aktiv"] for r in client.get(_pfad(mandant)).json()["rollen"]}
    for r in gesperrt:
        assert danach[r["rolle_id"]] is False, "die Sperre wurde aufgehoben"


def test_gesperrte_rolle_laesst_sich_wieder_freigeben(client, mandant):
    """Die Sperre ist keine Sackgasse — ein Häkchen genügt."""
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "rk-admin@bc0.test", "passwort": PW})
    rollen = client.get(_pfad(mandant)).json()["rollen"]
    ziel = next(r for r in rollen if not r["aktiv"])
    for r in rollen:
        if r["rolle_id"] == ziel["rolle_id"]:
            r["aktiv"] = True
    client.put(_pfad(mandant), json={"rollen": rollen, "kostensaetze": []})
    danach = {r["rolle_id"]: r["aktiv"] for r in client.get(_pfad(mandant)).json()["rollen"]}
    assert danach[ziel["rolle_id"]] is True


def test_beschreibung_wird_gespeichert_und_gelesen(client, mandant):
    """Die Beschreibung je Kernprozess ist Richards Wunsch aus der ADR-003-Rückmeldung:
    Der Interview-Bot muss erklären können, was ein Prozess umfasst, ohne zu erfinden."""
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "rk-admin@bc0.test", "passwort": PW})
    m = str(client.post("/api/companies", json={"name": "Beschreibung GmbH", "kps": [1]}).json()["id"])

    text = "Umfasst die Steuerung laufender Aufträge von der Annahme bis zur Abnahme."
    antwort = client.put("/api/companies/" + m + "/process",
                         json={"process_id": "KP-02", "beschreibung": text, "tps": []})
    assert antwort.status_code == 200

    prozesse = client.get("/api/companies/" + m).json()["processes"]
    assert prozesse["KP-02"]["beschreibung"] == text
