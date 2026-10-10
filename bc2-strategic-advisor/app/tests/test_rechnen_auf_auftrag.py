"""
Tests: Ansehen rechnet nicht — gerechnet wird auf Auftrag, im Hintergrund.

Gefunden am ersten echten Lauf (10.10.2026): die Oberfläche öffnete nach der
Anmeldung den obersten Lauf von selbst, und das ``GET`` rechnete jedes neue
Paket — Modellaufrufe und ein Lauf in der gemeinsamen Datenbank, ohne dass es
jemand entschieden hatte. Wer gleichzeitig dasselbe Paket ansah, rechnete ein
zweites Mal.

Die Quelle hier ist teuer (``teuer = True``) wie ``PaketLaufquelle``, rechnet
aber aus dem Messsatz — und zählt, wie oft.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from ablage import AblegendeLaufquelle, SpeicherErgebnisbuch
from gate1 import SpeicherGate1Buch
from laeufe import LaufAngehalten, MesssatzLaufquelle

from conftest import MESSSAETZE
from test_oberflaeche import alle_freigeben, sende


class TeuereQuelle:
    """Wie ``PaketLaufquelle``: teuer, zählt die Rechnungen, kann warten oder scheitern."""

    teuer = True

    def __init__(self) -> None:
        self._innen = MesssatzLaufquelle(MESSSAETZE)
        self.gerechnet = 0
        self.tor = threading.Event()
        self.tor.set()
        self.scheitert = False

    def uebersicht(self, company_id=None):
        return [replace(k, sperrgrund=None) for k in self._innen.uebersicht(company_id)]

    def ansicht(self, paket_id, kandidaten=()):
        self.gerechnet += 1
        self.tor.wait(5)
        if self.scheitert:
            raise LaufAngehalten("Ausarbeitung angehalten: Die Antwort enthält kein JSON-Objekt.")
        a = self._innen.ansicht(paket_id, kandidaten)
        return replace(a, kopf=replace(a.kopf, sperrgrund=None))


@pytest.fixture
def teuer():
    return TeuereQuelle()


@pytest.fixture
def stapel(teuer, buch):
    ergebnisse = SpeicherErgebnisbuch()
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    quelle = AblegendeLaufquelle(teuer, ergebnisse)
    from app import erzeuge_app

    with TestClient(erzeuge_app(buch, laufquelle=quelle, gate1_buch=gate1)) as c:
        yield c, teuer, ergebnisse


def _paket(c, kopf) -> str:
    return c.get("/api/oberflaeche/laeufe", headers=kopf).json()["laeufe"][0]["paket_id"]


def _warte_bis_gerechnet(c, kopf, paket_id, grenze_s=10) -> dict:
    ende = time.monotonic() + grenze_s
    while time.monotonic() < ende:
        lauf = c.get(f"/api/oberflaeche/laeufe/{paket_id}", headers=kopf).json()
        if lauf.get("gerechnet") or (lauf.get("zustand") == "fehler" and not lauf.get("laeuft")):
            return lauf
        time.sleep(0.05)
    raise AssertionError("Der Lauf wurde nicht fertig.")


def test_ansehen_rechnet_nicht(stapel, kopf):
    c, teuer, _ = stapel
    liste = c.get("/api/oberflaeche/laeufe", headers=kopf).json()["laeufe"]
    assert liste[0]["zustand"] == "ungerechnet" and liste[0]["laeuft"] is False

    lauf = c.get(f"/api/oberflaeche/laeufe/{liste[0]['paket_id']}", headers=kopf).json()

    assert lauf["gerechnet"] is False and lauf["zustand"] == "ungerechnet"
    assert teuer.gerechnet == 0


def test_rechnen_auf_auftrag_im_hintergrund(stapel, kopf):
    c, teuer, _ = stapel
    pid = _paket(c, kopf)

    antwort = c.post(f"/api/oberflaeche/laeufe/{pid}/rechnen", headers=kopf)
    assert antwort.status_code == 202 and antwort.json()["gestartet"] is True

    lauf = _warte_bis_gerechnet(c, kopf, pid)
    assert lauf["gerechnet"] is True and lauf["eintraege"]
    assert lauf["kopf"]["zustand"] == "offen"
    assert teuer.gerechnet == 1
    # Ein zweiter Auftrag rechnet nicht noch einmal.
    assert c.post(f"/api/oberflaeche/laeufe/{pid}/rechnen", headers=kopf).status_code == 409
    assert teuer.gerechnet == 1


def test_zwei_auftraege_gleichzeitig_rechnen_einmal(stapel, kopf):
    c, teuer, _ = stapel
    pid = _paket(c, kopf)
    teuer.tor.clear()  # die erste Rechnung hängt, bis das Tor aufgeht

    erste = c.post(f"/api/oberflaeche/laeufe/{pid}/rechnen", headers=kopf).json()
    zweite = c.post(f"/api/oberflaeche/laeufe/{pid}/rechnen", headers=kopf).json()
    waehrend = c.get(f"/api/oberflaeche/laeufe/{pid}", headers=kopf).json()
    teuer.tor.set()

    assert erste["gestartet"] is True and zweite["gestartet"] is False
    assert waehrend["gerechnet"] is False and waehrend["laeuft"] is True
    _warte_bis_gerechnet(c, kopf, pid)
    assert teuer.gerechnet == 1


def test_ein_gescheiterter_lauf_zeigt_seinen_grund_und_laesst_sich_neu_anstossen(stapel, kopf):
    c, teuer, ergebnisse = stapel
    pid = _paket(c, kopf)
    teuer.scheitert = True
    c.post(f"/api/oberflaeche/laeufe/{pid}/rechnen", headers=kopf)

    lauf = _warte_bis_gerechnet(c, kopf, pid)
    assert lauf["gerechnet"] is False and lauf["zustand"] == "fehler"
    assert "kein JSON-Objekt" in lauf["fehler"]
    # Nochmal ansehen rechnet nicht still neu.
    c.get(f"/api/oberflaeche/laeufe/{pid}", headers=kopf)
    assert teuer.gerechnet == 1

    teuer.scheitert = False
    assert c.post(f"/api/oberflaeche/laeufe/{pid}/rechnen", headers=kopf).status_code == 202
    lauf = _warte_bis_gerechnet(c, kopf, pid)
    assert lauf["gerechnet"] is True and lauf["kopf"]["fassung"] == 1  # Neuversuch, keine Fassung


def test_neu_rechnen_nach_reject_laeuft_im_hintergrund(stapel, kopf):
    c, teuer, _ = stapel
    pid = _paket(c, kopf)
    c.post(f"/api/oberflaeche/laeufe/{pid}/rechnen", headers=kopf)
    lauf = _warte_bis_gerechnet(c, kopf, pid)

    # Vor der Entscheidung: keine neue Fassung — und der Grund kommt an.
    vorher = c.post(f"/api/oberflaeche/laeufe/{pid}/neu", headers=kopf)
    assert vorher.status_code == 409 and "erst an Gate 1" in vorher.json()["fehler"]

    sende(c, kopf, pid, {"status": "rejected", "entscheider": "Test", "kommentar": "Nochmal."})
    antwort = c.post(f"/api/oberflaeche/laeufe/{pid}/neu", headers=kopf)
    assert antwort.status_code == 202

    neu = _warte_bis_gerechnet(c, kopf, pid)
    assert neu["kopf"]["fassung"] == 2 and neu["gate1"]["status"] == "pending"
    assert teuer.gerechnet == 2


def test_eine_billige_quelle_rechnet_beim_ansehen_wie_bisher(client, kopf):
    """Messsatz und Vorschau kosten nichts — dort bleibt Öffnen gleich Rechnen."""
    pid = client.get("/api/oberflaeche/laeufe", headers=kopf).json()["laeufe"][0]["paket_id"]
    lauf = client.get(f"/api/oberflaeche/laeufe/{pid}", headers=kopf).json()
    assert lauf["gerechnet"] is True and lauf["eintraege"]
    assert sende(client, kopf, pid, alle_freigeben(lauf)).status_code == 200
