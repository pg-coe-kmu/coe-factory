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
    ('id="addKpB"',           "Kernprozess hinzufuegen"),
    ('data-addtp=',           "Teilprozess hinzufuegen"),
    ('id="logoutLink"',       "Abmelden"),
])
def test_bedienstelle_ist_vorhanden(huelle, marke, wozu):
    assert marke in huelle, "Bedienstelle fehlt: %s (%s)" % (marke, wozu)


# --------------------------------------------------------------------------
# Die zweite Anwendung (01.09.2026)
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anfrage_huelle() -> str:
    """Die ausgelieferte Anfrage-Anwendung unter /anfrage/."""
    c = TestClient(anwendung.app)
    antwort = c.get("/anfrage/")
    assert antwort.status_code == 200
    return antwort.text


def test_anfrage_pwa_wird_ausgeliefert(anfrage_huelle):
    """Beide Schreibweisen muessen gehen — mit und ohne Schraegstrich.

    Wer den Pfad von Hand eintippt, laesst den letzten Schrich weg. Ein 404
    an dieser Stelle waere der erste Eindruck der Anwendung.
    """
    c = TestClient(anwendung.app)
    assert c.get("/anfrage").status_code == 200
    assert "Anfrage an das CoE" in anfrage_huelle


def test_anfrage_pwa_traegt_das_formular(anfrage_huelle):
    """Was von BC0 hierher gewandert ist."""
    for marke in ('id="text"', 'id="ziel"', 'id="ausl"', 'id="umf"',
                  'id="kp"', 'id="per"', 'id="senden"'):
        assert marke in anfrage_huelle, "Feld fehlt: %s" % marke


def test_anfrage_pwa_erlaubt_weiss_ich_nicht(anfrage_huelle):
    """Der Kern der Entscheidung vom 28.08. muss auch hier gelten."""
    assert "weiß ich nicht" in anfrage_huelle


def test_anfrage_pwa_ist_eine_eigene_anwendung(anfrage_huelle):
    """Eigenes Manifest, eigener Service Worker, eigener Geltungsbereich.

    Ohne diese drei waere es kein zweites Programm, sondern eine weitere
    Seite von BC0 — und die Trennung faende nur im Pfad statt.
    """
    c = TestClient(anwendung.app)

    m = c.get("/anfrage/manifest.json")
    assert m.status_code == 200
    daten = m.json()
    assert daten["scope"] == "/anfrage/"
    assert daten["start_url"] == "/anfrage/"
    assert daten["short_name"] != "BC0"

    sw = c.get("/anfrage/sw.js")
    assert sw.status_code == 200
    assert sw.headers.get("cache-control") == "no-cache"
    # Ein eigener Cache-Name: Sonst loeschte der eine Worker beim Aktivieren
    # die Ablage des anderen — beide raeumen alles weg, was nicht ihr Name ist.
    assert "coe-anfrage-v" in sw.text
    assert "bc0-pwa-v" not in sw.text
    assert 'navigator.serviceWorker.register(\'/anfrage/sw.js\')' in anfrage_huelle


def test_bc0_fuehrt_in_die_anfrage_anwendung_und_hat_kein_zweites_formular(huelle):
    """Ein Eingang, nicht zwei.

    Bis zum 01.09. stand das Formular in BEIDEN Anwendungen. Zwei Eingaenge
    fuer dieselbe Sache sind genau der Fehler, den die Trennung behebt —
    deshalb ist es in BC0 verschwunden und nicht nur ausgeblendet.
    """
    assert "'/anfrage/'" in huelle, "Die Kachel fuehrt nicht in die zweite Anwendung"
    for weg in ('id="anfSend"', 'id="anfText"', 'id="anfZiel"', 'id="anfUmf"'):
        assert weg not in huelle, "Formularrest in BC0: %s" % weg
    # Die Liste bleibt — sie ist die Verwaltungssicht.
    assert 'id="anfListe"' in huelle


def test_die_beiden_worker_raeumen_sich_nicht_gegenseitig_aus():
    """Zwei Service Worker auf demselben Ursprung, zwei Ablagen.

    ``caches.keys()`` liefert die Ablagen des GANZEN Ursprungs, nicht nur die
    eigenen. Ein Worker, der beim Aktivieren alles loescht, was nicht seinen
    Namen traegt, raeumt damit die Ablage der anderen Anwendung ab — und die
    andere beim naechsten Aktivieren diese hier. Gefunden am 01.09.2026 beim
    Bau der zweiten Anwendung, bevor es jemandem auffallen konnte.
    """
    c = TestClient(anwendung.app)
    bc0 = c.get("/sw.js").text
    anf = c.get("/anfrage/sw.js").text
    assert 'startsWith("bc0-pwa-")' in bc0
    assert 'startsWith("coe-anfrage-")' in anf


# ---------------------------------------------------------------------------
# Nachgeruestet am 02.09.2026
# ---------------------------------------------------------------------------

def test_cache_name_haengt_an_der_huelle():
    """Aendert sich die Huelle, muss jemand ueber den Cache-Namen entscheiden.

    **Der Anlass, und er ist eine eigene Unterlassung.** Am 01.09.2026 wurde
    die Huelle von BC0 geaendert — das Anfrageformular kam heraus, die Kachel
    fuehrt seitdem nach ``/anfrage/``. Der Cache-Name blieb dabei auf
    ``bc0-pwa-v4`` stehen, obwohl im Kopf von ``sw.js`` seit dem 28.08. die
    Regel steht: *„Der Name wird bei jeder Aenderung an der Shell erhoeht."*

    Aufgefallen ist es erst am 02.09. beim Ausrollen, beim Vergleich der
    Dateigroessen mit dem Serverstand. **Kein Test hat es gesehen**, und das
    war kein Zufall: Die vorhandenen Pruefungen fragen nach dem *Praefix*
    (``bc0-pwa-``), nicht nach der *Nummer*. Ein Praefix aendert sich nie.

    **Was es gekostet haette:** Die Huelle laeuft network-first, online waere
    also nichts passiert. Offline haette die Anwendung weiter die alte
    Startseite ausgeliefert — mit einem Formular, das auf einen Weg zeigt,
    den es nicht mehr gibt. Kein Ausfall. Eine Falle.

    **Was dieser Test tut:** Er koppelt beides. Im Service Worker steht die
    Pruefsumme seiner Huelle. Aendert jemand die Huelle, ohne den Service
    Worker anzufassen, schlaegt der Test fehl. Er sagt nicht, dass der Name
    erhoeht werden *muss* — er erzwingt die Entscheidung. Es gibt Aenderungen
    an der Huelle, die keinen neuen Namen brauchen; es gibt keine, bei der
    man die Frage nicht stellen sollte.
    """
    import hashlib
    import re

    hier = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paare = [("static/index.html", "static/sw.js"),
             ("static/anfrage/index.html", "static/anfrage/sw.js")]

    for huelle_rel, sw_rel in paare:
        huelle_pfad = os.path.join(hier, *huelle_rel.split("/"))
        sw_pfad = os.path.join(hier, *sw_rel.split("/"))

        with open(huelle_pfad, "rb") as f:
            ist = hashlib.sha256(f.read()).hexdigest()[:8]

        with open(sw_pfad, encoding="utf-8") as f:
            sw_text = f.read()

        treffer = re.search(r"/\* HUELLE ([0-9a-f]{8}) ", sw_text)
        assert treffer, (
            "%s nennt keine Huellen-Pruefsumme. Erwartet eine Zeile "
            "'/* HUELLE %s — ...'" % (sw_rel, ist))

        assert treffer.group(1) == ist, (
            "\n\n  Die Huelle %s hat sich geaendert.\n"
            "  %s nennt %s, tatsaechlich ist es %s.\n\n"
            "  Jetzt ist zu entscheiden: Muss CACHE erhoeht werden?\n"
            "    JA  — wenn Aussehen oder Bedienung sich geaendert haben.\n"
            "          Dann CACHE erhoehen UND die Pruefsumme nachtragen.\n"
            "    NEIN— wenn nur ein Kommentar oder eine Kleinigkeit ohne\n"
            "          Wirkung geaendert wurde. Dann nur die Pruefsumme.\n\n"
            "  Genau diese Frage ist am 01.09.2026 nicht gestellt worden.\n"
            % (huelle_rel, sw_rel, treffer.group(1), ist))
