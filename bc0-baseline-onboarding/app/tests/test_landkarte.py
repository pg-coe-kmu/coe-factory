# -*- coding: utf-8 -*-
"""Die Prozesslandkarte muss wachsen und schrumpfen koennen.

Am 26.08.2026 beim Entwurf des Anfrage-Zugangs gefunden: Die Anwendung konnte
eine Landkarte nicht veraendern. Ein elfter Kernprozess lief in einen
``IndexError`` (HTTP 500), ein sechster Teilprozess war ueber die
Schnittstelle gar nicht erreichbar, und in der Datenbank sperrte
``step_no CHECK BETWEEN 1 AND 5``.

Das ist kein Randfall, sondern die Folge des eigenen Erfolgs: Automatisierung
veraendert die Landschaft, die sie vermessen hat.

Diese Tests halten drei Dinge fest:
  - der elfte Kernprozess geht, und der Mandant benennt ihn selbst,
  - der sechste bis neunte Teilprozess geht,
  - an den Grenzen kommt **400 mit einem lesbaren Satz**, nie ein 500.
"""
import pytest
from fastapi.testclient import TestClient

import app as A
from bc0_auth import Rolle

PW_ADMIN = "landkarte-admin-passwort"


@pytest.fixture(scope="module")
def client():
    A.AUTH.benutzer_anlegen("landkarte-admin@bc0.test", "Landkarte-Admin", PW_ADMIN, Rolle.ADMIN)
    c = TestClient(A.app)
    c.post("/api/auth/login", json={"email": "landkarte-admin@bc0.test", "passwort": PW_ADMIN})
    return c


@pytest.fixture(scope="module")
def leer(client) -> str:
    """Ein Mandant mit genau einem Kernprozess."""
    return str(client.post("/api/companies",
                           json={"name": "Landkarte GmbH", "kps": [0]}).json()["id"])


def _kps(client, cid):
    return sorted(client.get("/api/companies/" + cid).json()["processes"].keys())


# --------------------------------------------------------------------------- #
# Kernprozesse
# --------------------------------------------------------------------------- #
def test_kernprozess_mit_eigenem_namen(client, leer):
    """Der Mandant benennt seinen Prozess selbst — die Vorlage ist ein Vorschlag.

    Bis zum 27.08. kam der Name aus ``KP_TEMPLATE[kp_index]``. Damit hing die
    Identitaet am Index einer Konstante im Quelltext, und ein Haus mit eigener
    Einteilung konnte seine Prozesse nicht benennen.
    """
    r = client.post("/api/companies/" + leer + "/process/add",
                    json={"name": "Ersatzteilversorgung", "kategorie": "Kerngeschäftsprozess"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["process_id"] == "KP-02"          # max + 1
    assert d["process_name"] == "Ersatzteilversorgung"

    proz = client.get("/api/companies/" + leer).json()["processes"]
    assert proz["KP-02"]["process_name"] == "Ersatzteilversorgung"
    # Fuenf Teilprozesse als Startwert, nicht als Grenze.
    assert len(proz["KP-02"]["tps"]) == 5


def test_elfter_kernprozess_geht(client, leer):
    """Der Fall, an dem die Anwendung vorher mit HTTP 500 ausstieg.

    ``KP_TEMPLATE`` hat zehn Eintraege; ``KP_TEMPLATE[10]`` warf einen
    ``IndexError``. Die Datenbank konnte immer bis ``KP-99`` — nur die Vorlage
    nicht.
    """
    for i in range(3, 12):
        r = client.post("/api/companies/" + leer + "/process/add",
                        json={"name": "Eigener Prozess %d" % i,
                              "kategorie": "Unterstützungsprozess"})
        assert r.status_code == 200, r.text
    kps = _kps(client, leer)
    assert "KP-11" in kps
    assert len(kps) == 11


def test_kategorie_wird_geprueft(client, leer):
    """Eine erfundene Kategorie wird abgewiesen, nicht stillschweigend gesetzt."""
    r = client.post("/api/companies/" + leer + "/process/add",
                    json={"name": "Irgendwas", "kategorie": "Wunschprozess"})
    assert r.status_code == 400
    assert "kategorie" in r.json()["detail"].lower()


def test_name_ist_pflicht(client, leer):
    r = client.post("/api/companies/" + leer + "/process/add",
                    json={"kategorie": "Unterstützungsprozess"})
    assert r.status_code == 400


def test_alter_aufruf_mit_kp_index_geht_weiter(client):
    """Rueckwaertsvertraeglichkeit: ein alter Browser-Cache soll keinen Fehler ausloesen."""
    cid = str(client.post("/api/companies", json={"name": "Alt GmbH", "kps": [0]}).json()["id"])
    r = client.post("/api/companies/" + cid + "/process/add", json={"kp_index": 5})
    assert r.status_code == 200, r.text
    assert r.json()["process_name"] == A.KP_TEMPLATE[5]


def test_kp_index_ausserhalb_der_vorlage_gibt_400(client):
    """Frueher ein IndexError und damit 500. Jetzt ein Satz, der die Ursache nennt."""
    cid = str(client.post("/api/companies", json={"name": "Index GmbH", "kps": [0]}).json()["id"])
    r = client.post("/api/companies/" + cid + "/process/add", json={"kp_index": 10})
    assert r.status_code == 400
    assert "name und kategorie" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# Teilprozesse
# --------------------------------------------------------------------------- #
def test_sechster_teilprozess(client):
    """Diesen Weg gab es ueber die Schnittstelle vorher gar nicht.

    ``save_process`` ist UPDATE-only, ``add_process`` legt nur ganze
    Kernprozesse an. Ein sechster Schritt war unerreichbar.
    """
    cid = str(client.post("/api/companies", json={"name": "Sechs GmbH", "kps": [0]}).json()["id"])
    r = client.post("/api/companies/" + cid + "/process/KP-01/subprocess/add",
                    json={"name": "Nachgelagerte Pruefung"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "sub_process_id": "KP-01.TP-6", "step_no": 6}

    subs = client.get("/api/companies/" + cid).json()["processes"]["KP-01"]["tps"]
    assert len(subs) == 6
    assert subs[5]["sub_process_name"] == "Nachgelagerte Pruefung"


def test_zehnter_teilprozess_wird_abgewiesen(client):
    """ADR-002: Der TP-Teil ist einstellig.

    Nicht kosmetisch — bei gemischt ein- und zweistelliger Schreibweise
    sortiert ``TP-10`` vor ``TP-2``, und die Sortierung nach ID ist an vielen
    Stellen die einzige Ordnung. **400 und nicht 500**, mit der Begruendung im
    Text: Wer an eine Grenze stoesst, soll erfahren, dass es eine gibt.
    """
    cid = str(client.post("/api/companies", json={"name": "Neun GmbH", "kps": [0]}).json()["id"])
    for erwartet in range(6, 10):
        r = client.post("/api/companies/" + cid + "/process/KP-01/subprocess/add", json={})
        assert r.status_code == 200, r.text
        assert r.json()["step_no"] == erwartet

    r = client.post("/api/companies/" + cid + "/process/KP-01/subprocess/add", json={})
    assert r.status_code == 400
    assert "ADR-002" in r.json()["detail"]


def test_teilprozess_an_unbekanntem_kernprozess(client, leer):
    r = client.post("/api/companies/" + leer + "/process/KP-77/subprocess/add", json={})
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# Was /api/meta jetzt mitliefert
# --------------------------------------------------------------------------- #
def test_meta_kennzeichnet_die_vorlage_als_vorschlag(client):
    """Damit die Oberflaeche weiss, dass sie daneben einen freien Namen anbieten darf."""
    d = client.get("/api/meta").json()
    assert d["kp_template_ist_vorschlag"] is True
    assert d["max_tp"] == 9
    assert "Kerngeschäftsprozess" in d["kategorien"]
