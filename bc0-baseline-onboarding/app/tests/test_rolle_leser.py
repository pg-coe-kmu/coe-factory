# -*- coding: utf-8 -*-
"""
Die Rolle „leser" — Vorgang #211, ab 22.09.2026.

Die Rolle hat nur dann einen Wert, wenn **beide** Seiten stimmen: Sie muss
lesen dürfen, und sie darf nicht schreiben können. Eine Rolle, die nur im
Gutfall geprüft wurde, ist eine Vermutung — dieselbe Begründung wie in
``test_auth.py``.

Die wichtigste Prüfung ist **Nr. 1**: Sie zählt die schreibenden Endpunkte der
Anwendung ab und verlangt für jeden einen Schutz. Sie schlägt damit auch dann
fehl, wenn jemand nächstes Jahr einen neuen ``POST`` ergänzt und die
Abhängigkeit vergisst — ohne dass diese Datei angefasst werden müsste.

Ausführen::

    cd bc0-baseline-onboarding/app
    python -m pytest tests/test_rolle_leser.py -v
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402  — conftest.py hat die Umgebung vorbereitet
from bc0_auth import Benutzer, Rolle  # noqa: E402
from bc0_auth.abhaengigkeiten import beleg_zugriff, schreibender_benutzer  # noqa: E402

PASSWORT_ADMIN = "admin-passwort-2026"
PASSWORT_LESER = "leser-passwort-2026"
PASSWORT_NUTZER = "nutzer-passwort-2026"

#: Pfade, die schreiben, aber keinen Mandanten betreffen und deshalb in Nr. 1
#: gesondert behandelt werden. Beide sind bereits ``Depends(admin)``.
OHNE_MANDANT = {"/api/companies", "/api/import_yaml"}


# --------------------------------------------------------------------------- #
# Vorbereitung
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def umgebung():
    """Ein Mandant, ein Admin, ein Benutzer und ein Leser auf demselben Mandanten."""
    anwendung.AUTH.benutzer_anlegen("admin-l@bc0.test", "Admin", PASSWORT_ADMIN, Rolle.ADMIN)
    client = TestClient(anwendung.app)
    client.post("/api/auth/login", json={"email": "admin-l@bc0.test", "passwort": PASSWORT_ADMIN})
    antwort = client.post("/api/companies", json={"name": "Leser GmbH"})
    assert antwort.status_code == 200, antwort.text
    cid = str(antwort.json()["id"])
    client.post("/api/auth/logout")

    anwendung.AUTH.benutzer_anlegen(
        "leser@bc0.test", "Leserin", PASSWORT_LESER, Rolle.LESER, mandanten=[cid]
    )
    anwendung.AUTH.benutzer_anlegen(
        "nutzer-l@bc0.test", "Nutzer", PASSWORT_NUTZER, Rolle.BENUTZER, mandanten=[cid]
    )
    # Eigenes Konto fuer Nr. 6: Ein Passwortwechsel beendet ALLE Sitzungen des
    # Kontos. Liefe er auf leser@bc0.test, waeren die folgenden Tests abgemeldet.
    anwendung.AUTH.benutzer_anlegen(
        "leser-pw@bc0.test", "Leser PW", PASSWORT_LESER, Rolle.LESER, mandanten=[cid]
    )
    return {"cid": cid}


@pytest.fixture()
def als_leser(umgebung):
    c = TestClient(anwendung.app)
    antwort = c.post("/api/auth/login", json={"email": "leser@bc0.test", "passwort": PASSWORT_LESER})
    assert antwort.status_code == 200, antwort.text
    return c


@pytest.fixture()
def als_benutzer(umgebung):
    c = TestClient(anwendung.app)
    antwort = c.post(
        "/api/auth/login", json={"email": "nutzer-l@bc0.test", "passwort": PASSWORT_NUTZER}
    )
    assert antwort.status_code == 200, antwort.text
    return c


# --------------------------------------------------------------------------- #
# 1. Vollständigkeit — die Prüfung, die künftige Lücken findet
# --------------------------------------------------------------------------- #
def test_01_jeder_schreibende_endpunkt_ist_geschuetzt():
    """Kein ``POST``/``PUT``/``PATCH``/``DELETE`` ohne Schreib- oder Admin-Recht.

    Gezählt wird nicht an einer gepflegten Liste, sondern am Routenbaum der
    Anwendung selbst. Wer einen schreibenden Endpunkt ergänzt und die
    Abhängigkeit vergisst, bringt diesen Test zu Fall — und liest im Fehlertext
    den Pfad, den er vergessen hat.
    """
    from bc0_auth.abhaengigkeiten import admin as admin_abh

    erlaubt = {schreibender_benutzer, admin_abh}
    offen = []
    for route in anwendung.app.routes:
        methoden = getattr(route, "methods", set()) or set()
        if not (methoden & {"POST", "PUT", "PATCH", "DELETE"}):
            continue
        pfad = getattr(route, "path", "")
        if not pfad.startswith("/api/") or pfad.startswith("/api/auth/"):
            continue
        waechter = {
            d.call for d in getattr(route.dependant, "dependencies", []) if d.call is not None
        }
        # Die Abhängigkeit steht in der Signatur und taucht damit als
        # Parameter-Abhängigkeit auf; beides wird eingesammelt.
        for p in getattr(route.dependant, "dependencies", []):
            waechter.add(p.call)
        if not (waechter & erlaubt):
            offen.append("%s %s" % (sorted(methoden), pfad))
    assert not offen, "Schreibende Endpunkte ohne Schutz:\n  " + "\n  ".join(offen)


# --------------------------------------------------------------------------- #
# 2. Die Rolle selbst
# --------------------------------------------------------------------------- #
def test_02_rolle_ist_dreistufig():
    assert [r.value for r in Rolle] == ["benutzer", "admin", "leser"]
    assert Rolle.aus_text("leser") is Rolle.LESER
    with pytest.raises(ValueError):
        Rolle.aus_text("gast")


def test_03_rechte_am_modell():
    leser = Benutzer("id-l", "l@x", "L", Rolle.LESER, frozenset({"m1"}))
    nutzer = Benutzer("id-b", "b@x", "B", Rolle.BENUTZER, frozenset({"m1"}))
    admin = Benutzer("id-a", "a@x", "A", Rolle.ADMIN)

    assert leser.ist_leser and not nutzer.ist_leser and not admin.ist_leser
    assert not leser.darf_schreiben
    assert nutzer.darf_schreiben and admin.darf_schreiben
    assert not leser.darf_belege_oeffnen
    assert nutzer.darf_belege_oeffnen and admin.darf_belege_oeffnen
    # Ein Leser ist kein Admin — Löschen und Freigeben bleiben verschlossen.
    assert not leser.ist_admin and not leser.darf_loeschen() and not leser.darf_freigeben()


def test_04_mandantentrennung_gilt_wie_beim_benutzer():
    """Festlegung vom 22.09.2026: einem Mandanten zugeordnet, wie ein Benutzer."""
    leser = Benutzer("id-l", "l@x", "L", Rolle.LESER, frozenset({"m1"}))
    assert leser.darf_mandanten_sehen("m1")
    assert not leser.darf_mandanten_sehen("m2")


# --------------------------------------------------------------------------- #
# 3. Darf lesen
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "pfad",
    [
        "/api/companies",
        "/api/companies/{cid}",
        "/api/companies/{cid}/report",
        "/api/companies/{cid}/ki_readiness",
        "/api/companies/{cid}/prozessdok",
        "/api/companies/{cid}/documents",
        "/api/companies/{cid}/erhebungen",
        "/api/companies/{cid}/rollen_kosten",
        "/api/companies/{cid}/entitaeten",
        "/api/companies/{cid}/historie",
        "/api/companies/{cid}/anfragen",
    ],
)
def test_05_leser_darf_lesen(als_leser, umgebung, pfad):
    """Geprüft wird das Recht, nicht die Verfügbarkeit.

    Drei dieser Endpunkte antworten unter SQLite mit **501** — ``historie``
    verlangt PostgreSQL, ``ki_readiness`` und ``prozessdok`` verlangen Schema
    v1.9/v2.0. Das ist die Antwort der Anwendung an *jeden* Aufrufer und hat
    mit der Rolle nichts zu tun. Die Behauptung dieses Tests lautet deshalb:
    **Der Leser wird nicht wegen fehlender Rechte abgewiesen** — also weder 401
    noch 403. Auf 200 festzunageln hieße, die Testumgebung zu prüfen statt das
    Rechtemodell.
    """
    antwort = als_leser.get(pfad.replace("{cid}", umgebung["cid"]))
    assert antwort.status_code not in (401, 403), "%s -> %s %s" % (
        pfad,
        antwort.status_code,
        antwort.text,
    )


def test_06_leser_darf_eigenes_passwort_aendern(umgebung):
    """Bewusst erlaubt: Sonst hinge der Zugang am Erstpasswort des Admins.

    Der Wechsel beendet alle Sitzungen des Kontos — auch die aufrufende. Die
    Gegenprobe ist deshalb die **neue Anmeldung** mit dem neuen Passwort und
    nicht ein zweiter Aufruf mit der alten Sitzung.
    """
    c = TestClient(anwendung.app)
    antwort = c.post(
        "/api/auth/login", json={"email": "leser-pw@bc0.test", "passwort": PASSWORT_LESER}
    )
    assert antwort.status_code == 200, antwort.text
    antwort = c.post("/api/auth/me/passwort", json={"neues_passwort": "leser-passwort-neu-2026"})
    assert antwort.status_code == 200, antwort.text
    neu = TestClient(anwendung.app)
    antwort = neu.post(
        "/api/auth/login",
        json={"email": "leser-pw@bc0.test", "passwort": "leser-passwort-neu-2026"},
    )
    assert antwort.status_code == 200, antwort.text


def test_07_eigenes_konto_meldet_die_rolle(als_leser):
    daten = als_leser.get("/api/auth/me").json()
    assert daten["rolle"] == "leser"
    assert daten["ist_admin"] is False
    assert daten["darf_schreiben"] is False
    assert daten["darf_belege_oeffnen"] is False


# --------------------------------------------------------------------------- #
# 4. Darf nicht schreiben
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "methode,pfad,nutzlast",
    [
        ("PUT", "/api/companies/{cid}/profile", {"name": "Umbenannt"}),
        ("PUT", "/api/companies/{cid}/process", {"process_id": "KP-01"}),
        ("POST", "/api/companies/{cid}/process/add", {"name": "Neuer Prozess"}),
        ("POST", "/api/companies/{cid}/rating", {"sub_process_id": "KP-01.TP-1"}),
        ("PUT", "/api/companies/{cid}/ki_readiness", {"dimensionen": []}),
        ("PUT", "/api/companies/{cid}/rollen_kosten", {"rollen": [], "kostensaetze": []}),
        ("PUT", "/api/companies/{cid}/entitaeten", {"personen": [], "systeme": []}),
        ("POST", "/api/companies/{cid}/anfragen", {"titel": "Versuch"}),
        ("POST", "/api/companies/{cid}/prozesskanten", {"von": "KP-01", "nach": "KP-02"}),
    ],
)
def test_08_leser_darf_nicht_schreiben(als_leser, umgebung, methode, pfad, nutzlast):
    """403 und nicht 422.

    Die Rechteprüfung läuft als Abhängigkeit **vor** der Auswertung des Rumpfs.
    Ein unvollständiger Testkörper darf das Ergebnis deshalb nicht verfälschen —
    käme 422 zurück, wäre die Reihenfolge falsch und ein wohlgeformter Aufruf
    würde durchgehen.
    """
    antwort = als_leser.request(methode, pfad.replace("{cid}", umgebung["cid"]), json=nutzlast)
    assert antwort.status_code == 403, "%s %s -> %s %s" % (
        methode,
        pfad,
        antwort.status_code,
        antwort.text,
    )
    assert "nur lesen" in antwort.json().get("detail", "").lower()


def test_09_derselbe_aufruf_gelingt_dem_benutzer(als_benutzer, umgebung):
    """Gegenprobe: Der Endpunkt ist nicht etwa für alle kaputt."""
    antwort = als_benutzer.put(
        "/api/companies/%s/profile" % umgebung["cid"], json={"name": "Leser GmbH"}
    )
    assert antwort.status_code == 200, antwort.text


def test_10_leser_darf_keine_belege_loeschen(als_leser, umgebung):
    antwort = als_leser.delete(
        "/api/companies/%s/documents/00000000-0000-0000-0000-000000000000" % umgebung["cid"]
    )
    assert antwort.status_code == 403, antwort.text


# --------------------------------------------------------------------------- #
# 5. Darf keine Belege öffnen, keinen Gate-0-Bogen sehen
# --------------------------------------------------------------------------- #
def test_11_leser_darf_beleg_nicht_oeffnen(als_leser, umgebung):
    """403 vor 404 — die Rechteprüfung greift, bevor die Datei gesucht wird.

    Wichtig für die Aussage des Tests: Käme 404, ließe sich daraus nicht
    ablesen, ob das Recht gefehlt hat oder nur die Datei.
    """
    antwort = als_leser.get(
        "/api/companies/%s/documents/00000000-0000-0000-0000-000000000000/file"
        % umgebung["cid"]
    )
    assert antwort.status_code == 403, antwort.text


def test_12_leser_darf_belegtexte_nicht_durchsuchen(als_leser, umgebung):
    antwort = als_leser.get("/api/companies/%s/documents/suche?q=vertrag" % umgebung["cid"])
    assert antwort.status_code == 403, antwort.text


def test_13_belegliste_bleibt_sichtbar(als_leser, umgebung):
    """Die Grenze verläuft zwischen Metadaten und Inhalt — und nicht davor."""
    antwort = als_leser.get("/api/companies/%s/documents" % umgebung["cid"])
    assert antwort.status_code == 200, antwort.text


@pytest.mark.parametrize(
    "pfad",
    [
        "/api/companies/{cid}/gate",
        "/api/companies/{cid}/gate/KP-01.TP-1",
        "/api/companies/{cid}/uebergabe",
    ],
)
def test_14_leser_sieht_den_gate_bogen_nicht(als_leser, umgebung, pfad):
    antwort = als_leser.get(pfad.replace("{cid}", umgebung["cid"]))
    assert antwort.status_code == 403, "%s -> %s" % (pfad, antwort.status_code)


def test_15_leser_darf_nicht_entscheiden(als_leser, umgebung):
    antwort = als_leser.post(
        "/api/companies/%s/gate/KP-01.TP-1" % umgebung["cid"], json={"ereignis": "freigegeben"}
    )
    assert antwort.status_code == 403, antwort.text


# --------------------------------------------------------------------------- #
# 6. Mandantentrennung gilt weiter
# --------------------------------------------------------------------------- #
def test_16_fremder_mandant_bleibt_unsichtbar(als_leser):
    """404 und nicht 403 — der Leser soll nicht erfahren, dass es den Mandanten gibt.

    Dieselbe Begründung wie in ``pruefe_mandant``; sie gilt für die neue Rolle
    unverändert.
    """
    antwort = als_leser.get("/api/companies/11111111-1111-1111-1111-111111111111")
    assert antwort.status_code == 404, antwort.text


# --------------------------------------------------------------------------- #
# 7. Die Benutzerverwaltung bleibt dem Admin
# --------------------------------------------------------------------------- #
def test_17_leser_darf_keine_konten_sehen(als_leser):
    assert als_leser.get("/api/auth/benutzer").status_code == 403


def test_18_leser_darf_sich_nicht_selbst_befoerdern(als_leser, umgebung):
    """Der Weg über die Benutzerverwaltung ist versperrt — er ist Admin-Sache."""
    eigen = als_leser.get("/api/auth/me").json()["benutzer_id"]
    antwort = als_leser.put("/api/auth/benutzer/%s" % eigen, json={"rolle": "admin"})
    assert antwort.status_code == 403, antwort.text
    assert als_leser.get("/api/auth/me").json()["rolle"] == "leser"
