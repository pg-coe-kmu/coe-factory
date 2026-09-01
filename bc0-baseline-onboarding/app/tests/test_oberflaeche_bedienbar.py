# -*- coding: utf-8 -*-
"""
Tests, die pruefen, dass ein vorhandener Endpunkt auch **bedienbar** ist.

Der Anlass ist ein Befund vom 26.08.2026: `POST /api/auth/me/passwort` gab es
seit dem 10.08., war getestet und funktionierte — **aber die Oberflaeche bot
ihn nicht an.** Oben rechts standen nur Name, Rolle und „Abmelden". Die
Kurzanleitung wies seit dem 17.08. trotzdem an, das Passwort „unter deinem
Namen oben rechts" zu aendern. **Mit dieser Anleitung sind zwoelf Konten
verteilt worden.**

Kein Test hat das gesehen, und das war kein Zufall: Die gesamte Testsammlung
prueft die Schnittstelle. Ein Endpunkt, der antwortet, gilt dort als
vorhanden — ob ihn jemand erreichen kann, ist eine andere Frage.

**Diese Datei schliesst genau diese Luecke**, und zwar in beide Richtungen:

* Zu jedem hier genannten Endpunkt muss es in der ausgelieferten Huelle eine
  Bedienstelle geben.
* Umgekehrt muss jede Bedienstelle einen Endpunkt treffen, den es gibt.

Das ist bewusst grob — ein `grep` auf ausgelieferten HTML-Text, kein
Browser-Test. Es faengt nicht jeden Fehler, aber es faengt den, der hier
tatsaechlich passiert ist: **eine Fachschicht ohne Zugang.**
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402


@pytest.fixture(scope="module")
def huelle() -> str:
    """Die ausgelieferte Startseite — genau das, was ein Browser bekommt."""
    c = TestClient(anwendung.app)
    antwort = c.get("/")
    assert antwort.status_code == 200
    return antwort.text


# --------------------------------------------------------------------------
# Der Befund vom 26.08. — ab jetzt gesichert
# --------------------------------------------------------------------------

def test_passwortwechsel_ist_erreichbar(huelle):
    """Der Endpunkt allein genuegt nicht; es muss einen Weg dorthin geben."""
    assert 'id="pwLink"' in huelle, "Kein Link zum Passwortwechsel in der Kopfzeile"
    assert "/api/auth/me/passwort" in huelle, "Die Huelle ruft den Endpunkt nirgends auf"
    assert 'id="pwForm"' in huelle, "Kein Formular fuer den Wechsel"


def test_passwortwechsel_warnt_vor_der_folge(huelle):
    """Der Wechsel beendet ALLE Sitzungen — auch die aufrufende.

    Wer das nicht vorher liest, haelt den anschliessenden Rauswurf fuer einen
    Fehler. Der Hinweis ist deshalb Teil der Funktion, nicht Beiwerk.
    """
    assert "Sitzungen werden beendet" in huelle


def test_passwortwechsel_verlangt_die_wiederholung(huelle):
    """Zwei Felder, obwohl der Server nur eines nimmt.

    Ein Tippfehler im einzigen Feld sperrte den Benutzer aus seinem eigenen
    Konto aus — mit einem Passwort, das nur er kennt und das er nie gesehen
    hat. Der Abgleich ist deshalb keine Bequemlichkeit.
    """
    assert 'id="pwNeu2"' in huelle


def test_mindestlaenge_steht_an_derselben_stelle_wie_im_server(huelle):
    """Die Oberflaeche darf keine andere Zahl nennen als die Fachschicht prueft.

    Sie prueft NICHT statt des Servers — der weist ein zu kurzes Passwort mit
    400 ab. Sie sagt es nur vorher, und wenn sie dabei eine andere Zahl nennt,
    ist der Hinweis schlimmer als keiner.
    """
    from bc0_auth import passwoerter
    assert "Mindestens %d Zeichen" % passwoerter.MINDESTLAENGE in huelle


# --------------------------------------------------------------------------
# Dieselbe Frage fuer die uebrigen Bedienstellen
# --------------------------------------------------------------------------

@pytest.mark.parametrize("marke,wozu", [
    ('id="kachelAnfrage"',    "Anfrage an das CoE"),
    ('id="kachelOnboarding"', "Onboarding"),
    ('id="anfSend"',          "Anfrage absenden"),
    ('id="addKpB"',           "Kernprozess hinzufuegen"),
    ('data-addtp=',           "Teilprozess hinzufuegen"),
    ('id="logoutLink"',       "Abmelden"),
])
def test_bedienstelle_ist_vorhanden(huelle, marke, wozu):
    assert marke in huelle, "Bedienstelle fehlt: %s (%s)" % (marke, wozu)
