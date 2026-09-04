# -*- coding: utf-8 -*-
"""
Tests für Erhebungen (Schema v1.3 Teil C).

Der Umbau hat einen Zweck: **Eine Nacherhebung darf den bisherigen Stand nicht
überschreiben.** Ohne Erhebungsbezug erzeugt die Re-Erhebung eines Prozesses
dieselben Item-Schlüssel wie beim ersten Mal — der alte Wert wäre spurlos weg,
und eine Gate-Freigabe, die sich auf ihn bezog, nicht mehr nachvollziehbar.

Zwei Eigenschaften sind hier wichtiger als das Anlegen selbst:

**Der aktuelle Stand wird je Einzelbewertung bestimmt, nicht je Mandant.** Wird
nur ein Teil der Prozesse nacherhoben, behalten die übrigen ihre alten Werte. Ein
Filter auf „jüngste Erhebung des Mandanten" ließe sie verschwinden — genau der
Fehler, der beim Durchspielen am 13.08.2026 auffiel.

**Eine verworfene Erhebung wird übergangen.** Ein Fehlversuch darf den Stand
nicht verfälschen, aber auch nicht gelöscht werden müssen.
"""

from __future__ import annotations

import datetime
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "erhebung-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("erh-admin@bc0.test", "Erh-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "erh-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies",
                           json={"name": "Erhebung GmbH", "kps": [1, 2]}).json()["id"])


def _tp(client, mandant: str) -> tuple[str, str]:
    """Zwei Teilprozesse aus zwei verschiedenen Kernprozessen."""
    daten = client.get("/api/companies/" + mandant).json()
    kps = sorted(daten["processes"].keys())
    return kps[0] + ".TP-1", kps[1] + ".TP-1"


def _bewerte(client, mandant: str, sub_process_id: str, stufe: int):
    items = {str(n): {"stufe": stufe, "beleg": "Beleg %d" % n} for n in range(1, 31)}
    return client.post("/api/companies/" + mandant + "/rating",
                       json={"key": sub_process_id, "items": items})


def _stufen(client, mandant: str, sub_process_id: str) -> list[int]:
    ratings = client.get("/api/companies/" + mandant).json()["ratings"]
    return sorted({v["stufe"] for v in ratings.get(sub_process_id, {}).values()})


# --------------------------------------------------------------------------- #
def test_erste_bewertung_erzeugt_eine_erhebung(client, mandant):
    """Niemand soll vor der ersten Bewertung an einen Messzeitpunkt denken müssen —
    aber jede Bewertung muss an einem hängen."""
    assert client.get("/api/companies/" + mandant + "/erhebungen").json()["erhebungen"] == []

    erste, _ = _tp(client, mandant)
    assert _bewerte(client, mandant, erste, 3).status_code == 200

    daten = client.get("/api/companies/" + mandant + "/erhebungen").json()
    assert len(daten["erhebungen"]) == 1
    e = daten["erhebungen"][0]
    assert e["erhebung_id"].startswith("E-")
    assert e["status"] == "offen"
    assert e["bewertungen"] == 30
    assert daten["massgeblich"] == e["erhebung_id"]


def test_mandant_meldet_die_geltende_erhebung(client, mandant):
    """Die Oberfläche muss anzeigen können, in welchen Messzeitpunkt geschrieben wird."""
    erh = client.get("/api/companies/" + mandant).json()["erhebung"]
    assert erh and erh["status"] == "offen"


def test_zweite_bewertung_landet_in_derselben_erhebung(client, mandant):
    _, zweite = _tp(client, mandant)
    _bewerte(client, mandant, zweite, 4)
    daten = client.get("/api/companies/" + mandant + "/erhebungen").json()
    assert len(daten["erhebungen"]) == 1, "es darf keine zweite Erhebung entstehen"
    assert daten["erhebungen"][0]["bewertungen"] == 60


def test_erhebung_abschliessen(client, mandant):
    antwort = client.post("/api/companies/" + mandant + "/erhebungen",
                          json={"aktion": "abschliessen"})
    assert antwort.status_code == 200
    assert client.get("/api/companies/" + mandant + "/erhebungen") \
        .json()["erhebungen"][0]["status"] == "abgeschlossen"


def test_zweite_erhebung_im_selben_monat_bekommt_eine_nummer(client, mandant):
    """Bis v2.7: 400, weil `E-JJJJ-MM` nur eine Erhebung je Monat kannte. Seit v2.8
    heisst die zweite `E-JJJJ-MM-2` — alt bleibt, neu kommt dazu (wie beim Paket)."""
    heute = datetime.date.today()
    antwort = client.post("/api/companies/" + mandant + "/erhebungen",
                          json={"aktion": "neu", "bezeichnung": "Zweiter Anlauf"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["erhebung_id"] == "E-%04d-%02d-2" % (heute.year, heute.month)
    daten = client.get("/api/companies/" + mandant + "/erhebungen").json()
    assert daten["offen"] == antwort.json()["erhebung_id"]
    assert daten["erhebungen"][0]["bezeichnung"] == "Zweiter Anlauf"
    # Aufraeumen fuer die folgenden Tests: die Nummer 2 wird verworfen, die Zaehlung
    # geht trotzdem weiter — eine Kennung wird nie ein zweites Mal vergeben.
    assert client.post("/api/companies/" + mandant + "/erhebungen",
                       json={"aktion": "verwerfen"}).status_code == 200
    assert client.get("/api/companies/" + mandant + "/erhebungen").json()["naechste"] \
        == "E-%04d-%02d-3" % (heute.year, heute.month)


def test_unbekannte_aktion_wird_abgelehnt(client, mandant):
    assert client.post("/api/companies/" + mandant + "/erhebungen",
                       json={"aktion": "loeschen"}).status_code == 400


# --------------------------------------------------------------------------- #
# Der eigentliche Zweck des Umbaus
# --------------------------------------------------------------------------- #
def _erhebung_von_hand(mandant: str, erhebung_id: str, stand: str, status: str = "abgeschlossen"):
    """Eine Erhebung mit abweichendem Monat anlegen.

    Über die Schnittstelle geht das nicht — sie kennt nur den laufenden Monat.
    Für den Test einer Nacherhebung brauchen wir aber zwei verschiedene Stände.
    """
    c = anwendung.db()
    try:
        c.execute("INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) "
                  "VALUES(?,?,?,?,?)",
                  (mandant, erhebung_id, "Nacherhebung " + erhebung_id, stand, status))
        c.commit()
    finally:
        c.close()


def _bewertung_von_hand(mandant: str, erhebung_id: str, sub_process_id: str, stufe: int):
    c = anwendung.db()
    try:
        for nr in range(1, 31):
            rid = "%s.I-%02d" % (sub_process_id, nr)
            spalten = "company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,bewertet_am"
            werte = [mandant, erhebung_id, rid, sub_process_id, nr, stufe, "Nacherhebung",
                     anwendung.now()]
            if not anwendung.PG:
                spalten = spalten.replace("sub_process_id,item_nr",
                                          "sub_process_id,process_id,item_nr")
                werte.insert(4, sub_process_id.split(".")[0])
            c.execute("INSERT INTO bitkom_bewertungen(" + spalten + ") VALUES("
                      + ",".join(["?"] * len(werte)) + ")", tuple(werte))
        c.commit()
    finally:
        c.close()


def test_nacherhebung_ueberschreibt_nur_die_nacherhobenen(client, mandant):
    """**Der wichtigste Test dieser Datei.**

    Zwei Teilprozesse sind mit 3 und 4 bewertet. Eine Nacherhebung berührt nur
    den ersten und setzt ihn auf 5. Danach muss der erste 5 zeigen und der zweite
    **weiterhin 4** — nicht verschwinden, nicht auf den neuen Wert springen.
    """
    erste, zweite = _tp(client, mandant)
    assert _stufen(client, mandant, erste) == [3]
    assert _stufen(client, mandant, zweite) == [4]

    _erhebung_von_hand(mandant, "E-2099-12", "2099-12-01")
    _bewertung_von_hand(mandant, "E-2099-12", erste, 5)

    assert _stufen(client, mandant, erste) == [5], "die Nacherhebung hat nicht gegriffen"
    assert _stufen(client, mandant, zweite) == [4], \
        "der nicht nacherhobene Teilprozess hat seinen Stand verloren"


def test_alte_bewertung_bleibt_erhalten(client, mandant):
    """Der alte Wert ist nicht überschrieben, sondern liegt unter seiner Erhebung."""
    erste, _ = _tp(client, mandant)
    c = anwendung.db()
    try:
        zeilen = c.execute(
            "SELECT erhebung_id, stufe FROM bitkom_bewertungen WHERE " + anwendung.W_CO +
            " AND sub_process_id=? AND item_nr=1 ORDER BY erhebung_id", (mandant, erste)).fetchall()
    finally:
        c.close()
    stufen = {r["erhebung_id"]: r["stufe"] for r in zeilen}
    assert len(stufen) == 2, "es muessen beide Erhebungen vorliegen"
    assert 3 in stufen.values() and 5 in stufen.values()


def test_verworfene_erhebung_wird_uebergangen(client, mandant):
    """Ein Fehlversuch darf den Stand nicht verfälschen — und nicht gelöscht
    werden müssen, weil Verweise darauf zeigen können."""
    erste, _ = _tp(client, mandant)
    _erhebung_von_hand(mandant, "E-2099-11", "2099-11-01", status="offen")
    _bewertung_von_hand(mandant, "E-2099-11", erste, 1)
    # Sie ist jünger als E-2026-xx, aber älter als E-2099-12 — greift also nicht.
    assert _stufen(client, mandant, erste) == [5]

    # Jetzt eine, die jünger ist als alles andere, und dann verworfen wird.
    c = anwendung.db()
    try:
        c.execute("INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) "
                  "VALUES(?,?,?,?,?)", (mandant, "E-2100-01", "Fehlversuch", "2100-01-01", "offen"))
        c.commit()
    finally:
        c.close()
    _bewertung_von_hand(mandant, "E-2100-01", erste, 2)
    assert _stufen(client, mandant, erste) == [2], "Vorbedingung: der Fehlversuch greift"

    c = anwendung.db()
    try:
        c.execute("UPDATE ref_erhebungen SET status='verworfen' WHERE " + anwendung.W_CO +
                  " AND erhebung_id=?", (mandant, "E-2100-01"))
        c.commit()
    finally:
        c.close()
    assert _stufen(client, mandant, erste) == [5], \
        "die verworfene Erhebung wird weiterhin mitgezaehlt"


def test_bericht_rechnet_auf_dem_massgeblichen_stand(client, mandant):
    """Der Reifegradbericht darf nicht über zwei Erhebungen hinweg mitteln."""
    bericht = client.get("/api/companies/" + mandant + "/report").json()
    assert bericht["n_bewertungen"] == 60, \
        "der Bericht zaehlt Zeilen aus mehreren Erhebungen doppelt"


# --------------------------------------------------------------------------- #
def test_fremder_mandant_bleibt_gesperrt(client, mandant):
    fremd = str(client.post("/api/companies", json={"name": "Fremd KG", "kps": []}).json()["id"])
    anwendung.AUTH.benutzer_anlegen("erh-nutzer@bc0.test", "Nutzer", "erh-nutzer-passwort",
                                    Rolle.BENUTZER, mandanten=[mandant])
    client.cookies.clear()
    client.post("/api/auth/login",
                json={"email": "erh-nutzer@bc0.test", "passwort": "erh-nutzer-passwort"})
    assert client.get("/api/companies/" + mandant + "/erhebungen").status_code == 200
    assert client.get("/api/companies/" + fremd + "/erhebungen").status_code == 404
    # v2.8: Abschliessen/Beginnen ist BC0 (Admin) vorbehalten — ein Benutzer
    # scheitert schon an der Rolle (403), bevor der Mandant geprueft wird.
    assert client.post("/api/companies/" + fremd + "/erhebungen",
                       json={"aktion": "abschliessen"}).status_code == 403
    assert client.post("/api/companies/" + mandant + "/erhebungen",
                       json={"aktion": "abschliessen"}).status_code == 403
