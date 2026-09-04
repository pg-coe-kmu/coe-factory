# -*- coding: utf-8 -*-
"""
Tests des regelbasierten Stichwortabgleichs — Trichter 3 (ToDo-Punkt 61).

Ausfuehren:
    python -m pytest tests/test_trichter3.py -v

WAS HIER GEPRUEFT WIRD
  Der Kern ist eine **reine Funktion**: Text hinein, Vorschlaege heraus, keine
  Datenbank und keine Uhr. Das ist kein Zufall der Umsetzung, sondern die
  Bedingung dafuer, dass sich ein Vorschlag streiten laesst — wer ihn fuer
  falsch haelt, kann ihn hier nachstellen.

  Den Anfang macht der Fall, an dem der Punkt haengt: Am 30.08.2026 blieb
  `A-2026-04` („reisekostenabrechnung automatisieren") ohne Prozessbezug,
  waehrend zwei Zeilen darueber `A-2026-01` bereits KP-06.TP-2 „Reise- und
  Einsatzplanung" trug. **Wenn dieser Test faellt, ist der Punkt sinnlos.**

  Danach die andere Haelfte, die schwerer zu bekommen ist: **dass er schweigt,
  wenn er nichts weiss.** Ein Trichter, der immer etwas vorschlaegt, wird nach
  drei Wochen weggeklickt.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import (  # noqa: E402
    HOECHSTENS, MINDESTPUNKTE, passt, vorschlaege_bc0, worte,
)


# --------------------------------------------------------------------------- #
# Die Prozesslandkarte von NoroAI, soweit sie hier gebraucht wird
# --------------------------------------------------------------------------- #
PROZESSE = [
    {"process_id": "KP-06", "process_name": "Personal",
     "trigger_text": "Reiseanfrage per Mail oder Formular, Verfuegbarkeit wird geprueft",
     "beschreibung": "Einsatz und Verfuegbarkeit der Consultants"},
    {"process_id": "KP-02", "process_name": "Angebot und Vertrieb",
     "trigger_text": "Kundenanfrage geht ein, Angebot wird kalkuliert",
     "beschreibung": "Vom Erstkontakt bis zur Unterschrift"},
    {"process_id": "KP-09", "process_name": "Buchhaltung",
     "trigger_text": "Rechnung geht ein und wird geprueft",
     "beschreibung": "Debitoren, Kreditoren, Monatsabschluss"},
]

TEILPROZESSE = [
    {"sub_process_id": "KP-06.TP-2", "process_id": "KP-06",
     "sub_process_name": "Reise- und Einsatzplanung"},
    {"sub_process_id": "KP-06.TP-1", "process_id": "KP-06",
     "sub_process_name": "Neueinstellung und Onboarding"},
    {"sub_process_id": "KP-02.TP-1", "process_id": "KP-02",
     "sub_process_name": "Angebotskalkulation"},
    {"sub_process_id": "KP-09.TP-1", "process_id": "KP-09",
     "sub_process_name": "Eingangsrechnungspruefung"},
]


def _ids(treffer):
    return [t["sub_process_id"] or t["process_id"] for t in treffer]


# --------------------------------------------------------------------------- #
# 1 — Der Fall, an dem der Punkt haengt
# --------------------------------------------------------------------------- #
def test_der_feldversuch_vom_30_08_wird_getroffen():
    """`A-2026-04` haette KP-06.TP-2 vorgeschlagen bekommen.

    Der Wortlaut stammt aus der Datenbank, nicht aus der Erinnerung. Er ist
    der Grund, warum dieser Punkt ueberhaupt in der Liste steht.
    """
    treffer = vorschlaege_bc0("reisekostenabrechnung automatisieren",
                              PROZESSE, TEILPROZESSE)
    assert treffer, "kein Vorschlag — genau das war der Zustand am 30.08."
    assert treffer[0]["sub_process_id"] == "KP-06.TP-2"


def test_der_vorschlag_nennt_das_wort_auf_dem_er_beruht():
    """Ohne sichtbaren Grund liesse sich ein Vorschlag nur glauben.

    Und dann stuende `vorschlag_bc0` in der Herkunftsspalte fuer etwas, das
    niemand geprueft hat — genau die zweite Wahrheit, die ADR-005 ausschliesst.
    """
    treffer = vorschlaege_bc0("reisekostenabrechnung automatisieren",
                              PROZESSE, TEILPROZESSE)
    assert "reisekostenabrechnung" in treffer[0]["treffer"]
    assert "sub_process_name" in treffer[0]["fundstellen"]


def test_auch_die_bereits_zugeordnete_anfrage_wird_getroffen():
    """Gegenprobe am zugeordneten Zwilling: `A-2026-01`.

    Beide Anliegen meinen dieselbe Sache. Traefe nur eines, waere der
    Abgleich zufaellig und nicht regelhaft.
    """
    treffer = vorschlaege_bc0("End-to-End Reisebuchungsprozess automatisieren",
                              PROZESSE, TEILPROZESSE)
    assert treffer[0]["sub_process_id"] == "KP-06.TP-2"


# --------------------------------------------------------------------------- #
# 2 — Dass er schweigt, wenn er nichts weiss
# --------------------------------------------------------------------------- #
def test_ein_anliegen_ohne_bezug_ergibt_keinen_vorschlag():
    """**Die wichtigere Haelfte.**

    Ein Trichter, der immer etwas anbietet, wird nach drei Wochen weggeklickt
    — und dann nuetzt auch der richtige Vorschlag nichts mehr.
    """
    assert vorschlaege_bc0("Der Kaffeeautomat im dritten Stock ist kaputt",
                           PROZESSE, TEILPROZESSE) == []


def test_nur_fuellwoerter_ergeben_keinen_vorschlag():
    """„Wir wollen das automatisieren" sagt nichts ueber einen Prozess aus."""
    assert vorschlaege_bc0("Wir wollen unsere Prozesse automatisieren",
                           PROZESSE, TEILPROZESSE) == []


def test_leerer_text_ergibt_keinen_vorschlag():
    for leer in ("", "   ", None):
        assert vorschlaege_bc0(leer, PROZESSE, TEILPROZESSE) == []


# --------------------------------------------------------------------------- #
# 3 — Die Kompositum-Regel, in beide Richtungen
# --------------------------------------------------------------------------- #
def test_bestimmungswort_am_anfang():
    """``reise`` steckt vorn in ``reisekostenabrechnung``."""
    assert passt("reisekostenabrechnung", "reise")


def test_grundwort_am_ende():
    """``rechnung`` steckt hinten in ``eingangsrechnungspruefung``? Nein —

    aber in ``abrechnung`` schon. Das Deutsche stellt das Grundwort ans Ende,
    und wer nur den Wortanfang prueft, findet die Haelfte der Faelle nicht.
    """
    assert passt("abrechnung", "rechnung")


def test_zu_kurze_staemme_treffen_nicht():
    """Bei vier Zeichen traefe ``rate`` in ``Beratung``.

    Der Wert 5 ist gemessen, nicht geraten: Mit 4 entstanden im Bestand von
    NoroAI drei Fehltreffer, mit 5 keiner.
    """
    assert not passt("beratung", "rate")
    assert not passt("kosten", "oste")


def test_umlaute_und_schreibweise_stoeren_nicht():
    """In den Bogen steht „Rueckfrage" neben „Rückfrage" — je nach Tipper."""
    assert worte("Rückfrage") == worte("Rueckfrage")
    assert worte("PRÜFUNG") == worte("pruefung")


def test_bindestrich_trennt_das_kompositum():
    """„Reise- und Einsatzplanung" muss ``reise`` einzeln hergeben."""
    assert "reise" in worte("Reise- und Einsatzplanung")
    assert "einsatzplanung" in worte("Reise- und Einsatzplanung")


# --------------------------------------------------------------------------- #
# 4 — Reihenfolge, Menge, Wiederholbarkeit
# --------------------------------------------------------------------------- #
def test_zweimal_derselbe_text_ergibt_dasselbe():
    """Dieselbe Zusicherung wie beim Reifegradbericht und beim Snapshot.

    Ohne sie haenge der Vorschlag an der Zeilenreihenfolge der Datenbank —
    und zwei Interviews zum selben Anliegen bekaemen verschiedene Antworten.
    """
    text = "Rechnung pruefen und Angebot kalkulieren"
    a = vorschlaege_bc0(text, PROZESSE, TEILPROZESSE)
    b = vorschlaege_bc0(text, list(reversed(PROZESSE)), list(reversed(TEILPROZESSE)))
    assert _ids(a) == _ids(b)


def test_hoechstens_drei_vorschlaege():
    """Wer fuenf Moeglichkeiten anbietet, hat die Arbeit weitergereicht."""
    text = "Reise Angebot Rechnung Einsatzplanung Onboarding Kalkulation"
    assert len(vorschlaege_bc0(text, PROZESSE, TEILPROZESSE)) <= HOECHSTENS


def test_der_bessere_treffer_steht_oben():
    treffer = vorschlaege_bc0("Angebotskalkulation ueberarbeiten",
                              PROZESSE, TEILPROZESSE)
    assert treffer[0]["sub_process_id"] == "KP-02.TP-1"
    assert treffer[0]["punkte"] >= MINDESTPUNKTE


# --------------------------------------------------------------------------- #
# 5 — Mandanten ohne Teilprozesse
# --------------------------------------------------------------------------- #
def test_ohne_teilprozesse_wird_der_kernprozess_vorgeschlagen():
    """Ein Vorschlag auf Kernprozessebene ist brauchbar.

    Der Fokus-Schritt ist ohnehin Ergebnis des Interviews — ihn hier zu
    verlangen hiesse, die Antwort vor der Frage zu fordern (dieselbe
    Begruendung wie beim Zuordnungs-Endpunkt).
    """
    treffer = vorschlaege_bc0("Reiseanfrage bearbeiten", PROZESSE, [])
    assert treffer
    assert treffer[0]["process_id"] == "KP-06"
    assert treffer[0]["sub_process_id"] is None


# --------------------------------------------------------------------------- #
# 6 — Der Endpunkt: Verdrahtung, Rechte, und dass er nichts schreibt
# --------------------------------------------------------------------------- #
# Die Tests oben pruefen die Regel. Diese pruefen den Weg dorthin: dass der
# Text aus der **Datenbank** kommt und nicht aus dem Aufruf, dass ein fremder
# Mandant nicht durchkommt — und vor allem, dass der Endpunkt die Anfrage
# unangetastet laesst.

from fastapi.testclient import TestClient  # noqa: E402

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "trichter-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("trichter@bc0.test", "Trichter-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "trichter@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    # KP-06 der Vorlage heisst „HR / Personal", KP-07 „Buchhaltung".
    return str(client.post("/api/companies",
                           json={"name": "Trichter GmbH", "kps": [5, 6]}).json()["id"])


def test_endpunkt_liefert_vorschlag_und_begruendung(client, mandant):
    aid = client.post("/api/companies/%s/anfragen" % mandant,
                      json={"originaltext": "Die Personalakte anlegen dauert zu lange"}
                      ).json()["anfrage_id"]
    r = client.get("/api/companies/%s/anfragen/%s/vorschlaege" % (mandant, aid))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["anfrage_id"] == aid
    assert d["grundlage"] == ["originaltext"]
    assert d["vorschlaege"], 'Personalakte muss HR / Personal finden'
    assert "personalakte" in d["vorschlaege"][0]["treffer"]


def test_endpunkt_schreibt_nichts(client, mandant):
    """**Der eigentliche Punkt.**

    Ein Vorschlag, der sich selbst eintraegt, waere eine Erhebung, die
    niemand vorgenommen hat — und in der Herkunftsspalte stuende, sie sei
    geprueft worden.
    """
    aid = client.post("/api/companies/%s/anfragen" % mandant,
                      json={"originaltext": "Die Personalakte anlegen dauert zu lange"}
                      ).json()["anfrage_id"]
    vorher = client.get("/api/companies/%s/anfragen" % mandant).json()
    client.get("/api/companies/%s/anfragen/%s/vorschlaege" % (mandant, aid))
    assert client.get("/api/companies/%s/anfragen" % mandant).json() == vorher


def test_endpunkt_meldet_eine_bereits_bestehende_zuordnung(client, mandant):
    """Damit die Oberflaeche einen gesetzten Bezug nicht stillschweigend uebergeht."""
    aid = client.post("/api/companies/%s/anfragen" % mandant,
                      json={"originaltext": "Personalakte"}).json()["anfrage_id"]
    client.put("/api/companies/%s/anfragen/%s/zuordnung" % (mandant, aid),
               json={"process_id": "KP-06", "zuordnung_quelle": "interview"})
    d = client.get("/api/companies/%s/anfragen/%s/vorschlaege" % (mandant, aid)).json()
    assert d["bereits_zugeordnet"] == "KP-06"


def test_endpunkt_kennt_unbekannte_anfragen_nicht(client, mandant):
    r = client.get("/api/companies/%s/anfragen/A-9999-99/vorschlaege" % mandant)
    assert r.status_code == 404


def test_endpunkt_ist_ohne_anmeldung_gesperrt(mandant):
    """Der Vorschlag nennt Prozessnamen des Mandanten — das ist kein oeffentlicher Text."""
    r = TestClient(anwendung.app).get(
        "/api/companies/%s/anfragen/A-2026-01/vorschlaege" % mandant)
    assert r.status_code == 401
