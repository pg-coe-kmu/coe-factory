# -*- coding: utf-8 -*-
"""
Tests der Anmeldebremse (ToDo-Punkt 71, 02.09.2026).

Ausfuehren:
    python -m pytest tests/test_anmeldebremse.py -v

WAS HIER GEPRUEFT WIRD — UND WARUM GERADE DAS
  Eine Bremse laesst sich leicht so bauen, dass sie im Gutfall funktioniert
  und in genau den Faellen versagt, fuer die sie da ist. Die Tests unten
  zielen deshalb auf die Umgehungswege:

    * ein Passwort gegen viele Konten  -> faengt der IP-Zaehler
    * ein Konto von vielen Adressen    -> faengt der E-Mail-Zaehler
    * Adresse existiert nicht          -> wird trotzdem gezaehlt
    * Konto ist ohnehin gesperrt       -> wird trotzdem gezaehlt
    * richtiges Passwort waehrend der Sperre -> kommt nicht durch

  Dazu die beiden Eigenschaften, die keine Sicherheitsfragen sind, sondern
  Bedienbarkeit: Die Sperre loest sich von allein, und eine erfolgreiche
  Anmeldung raeumt die Tippfehler davor weg.

WARUM `time.sleep` ABGESCHALTET IST
  Die Verzoegerung ist Absicht und im Test nur Wartezeit: Zehn Fehlversuche
  kosten 1+2+4+8+8+8 = 31 Sekunden. Die Kurve wird deshalb **rechnerisch**
  geprueft (`wartezeit`, eine reine Funktion ohne Uhr und ohne Datenbank), und
  der Ablauf laeuft ohne echtes Warten. Geprueft wird trotzdem, DASS verzoegert
  wurde — die Ersatzfunktion schreibt jeden Aufruf mit.
"""

from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bc0_auth import AnmeldeFehler, AuthDienst, Rolle, ZuVieleVersuche  # noqa: E402
from bc0_auth import dienst as dienst_modul  # noqa: E402


class _TestVerbindung:
    """Bildet die Verbindungsschnittstelle aus ``app.py`` nach (wie test_auth.py)."""

    def __init__(self, pfad: str):
        self.c = sqlite3.connect(pfad)
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql, params=()):
        return self.c.execute(sql, params)

    def commit(self):
        self.c.commit()

    def close(self):
        self.c.close()


PASSWORT = "ein-hinreichend-langes-passwort"
FALSCH = "das-ist-nicht-das-passwort"


@pytest.fixture()
def gewartet(monkeypatch):
    """Schaltet das echte Warten ab und schreibt die Wartezeiten mit."""
    protokoll = []

    def _statt_sleep(sekunden):
        protokoll.append(sekunden)

    monkeypatch.setattr(dienst_modul.time, "sleep", _statt_sleep)
    return protokoll


@pytest.fixture()
def billige_hashes(monkeypatch):
    """Setzt den Kostenparameter des Passwort-Hashs herab.

    Im Betrieb sind es 600.000 Durchlaeufe — rund **1,1 Sekunden je Pruefung**
    auf diesem Rechner, und genau so soll es sein. Diese Tests brauchen aber
    zehn Fehlversuche je Fall; bei voller Kostenstufe liefe die Datei ueber
    zwei Minuten und wuerde deshalb bald niemand mehr ausfuehren.

    **Geprueft wird hier die Bremse, nicht der Hash.** Dessen Kosten haben
    ihren eigenen Ort: ``test_auth.py`` und ``passwoerter.py``. Der Parameter
    ist dort ausdruecklich als „nur fuer Tests herabsetzen" vermerkt.

    Herabgesetzt werden muss an zwei Stellen — die zweite ist leicht zu
    uebersehen: ``_BLINDHASH`` wird beim Import einmal erzeugt und bei jeder
    **unbekannten** Adresse geprueft. Ohne ihn bliebe genau der Testfall
    langsam, der die meisten Fehlversuche braucht.
    """
    from bc0_auth import passwoerter

    # Die **urspruengliche** Funktion zuerst festhalten. `dienst_modul.passwoerter`
    # IST das Modul `passwoerter` — ein Ersatz, der ueber den Modulnamen wieder
    # `hash_erzeugen` ruft, ruft sich selbst. Beim ersten Lauf am 02.09.2026
    # endete das in 15 `RecursionError` statt in 15 gruenen Tests.
    echt = passwoerter.hash_erzeugen

    monkeypatch.setattr(
        dienst_modul.passwoerter, "hash_erzeugen",
        lambda passwort, durchlaeufe=1000: echt(passwort, durchlaeufe))
    monkeypatch.setattr(
        dienst_modul, "_BLINDHASH", echt("nur-fuer-den-zeitausgleich-2026", 1000))


@pytest.fixture()
def dienst(tmp_path, gewartet, billige_hashes) -> AuthDienst:
    """Ein AuthDienst mit einem angelegten Konto."""
    pfad = str(tmp_path / "test.db")
    auth = AuthDienst(lambda: _TestVerbindung(pfad), ist_postgres=False)
    auth.einrichten()
    auth.benutzer_anlegen(email="a@b.de", name="A", passwort=PASSWORT, rolle=Rolle.BENUTZER)
    return auth


def _fehlversuche(auth, anzahl, email="a@b.de", herkunft="10.0.0.1"):
    """Erzeugt ``anzahl`` Fehlversuche und gibt die letzte Ausnahme zurueck."""
    letzte = None
    for _ in range(anzahl):
        try:
            auth.anmelden(email, FALSCH, herkunft=herkunft)
        except AnmeldeFehler as fehler:
            letzte = fehler
    return letzte


# --------------------------------------------------------------------------- #
# 1 — Die Kurve, ohne Uhr und ohne Datenbank
# --------------------------------------------------------------------------- #
def test_wartezeit_beginnt_erst_ab_der_schwelle():
    """Die ersten vier Fehlversuche fuehlen sich normal an.

    Vertippen ist der Normalfall, Angriff der Ausnahmefall. Eine Bremse, die
    schon beim zweiten Versuch spuerbar ist, erzieht Benutzer dazu, das
    Passwort aufzuschreiben.
    """
    for n in range(0, dienst_modul.VERZOEGERUNG_AB):
        assert dienst_modul.wartezeit(n) == 0.0


def test_wartezeit_verdoppelt_sich_und_ist_gedeckelt():
    assert dienst_modul.wartezeit(5) == 1.0
    assert dienst_modul.wartezeit(6) == 2.0
    assert dienst_modul.wartezeit(7) == 4.0
    assert dienst_modul.wartezeit(8) == 8.0
    # Der Deckel ist keine Kosmetik: Die Anmelderoute laeuft in FastAPIs
    # endlichem Threadpool. Ohne Grenze waere die Bremse ein Weg, ihn zu fuellen.
    assert dienst_modul.wartezeit(9) == dienst_modul.VERZOEGERUNG_MAX.total_seconds()
    assert dienst_modul.wartezeit(50) == dienst_modul.VERZOEGERUNG_MAX.total_seconds()


# --------------------------------------------------------------------------- #
# 2 — Verzoegern und Sperren
# --------------------------------------------------------------------------- #
def test_die_ersten_versuche_werden_nicht_verzoegert(dienst, gewartet):
    _fehlversuche(dienst, dienst_modul.VERZOEGERUNG_AB - 1)
    assert gewartet == []


def test_ab_der_schwelle_wird_verzoegert(dienst, gewartet):
    _fehlversuche(dienst, dienst_modul.VERZOEGERUNG_AB + 1)
    assert gewartet, "ab dem fuenften Fehlversuch muss verzoegert werden"
    assert gewartet[0] == 1.0


def test_der_zehnte_fehlversuch_setzt_die_sperre_der_elfte_spuert_sie(dienst):
    """Die Sperre gilt ab dem Versuch **nach** dem zehnten — mit Absicht.

    Der zehnte Versuch war ein echter Versuch, und er war falsch; darauf ist
    „Adresse oder Passwort falsch" die zutreffende Antwort. Ihn stattdessen
    mit „gesperrt" zu beantworten, hiesse einem Benutzer zu verschweigen, dass
    er sich gerade vertippt hat.
    """
    letzte = _fehlversuche(dienst, dienst_modul.SPERRE_AB)
    assert not isinstance(letzte, ZuVieleVersuche)

    with pytest.raises(ZuVieleVersuche) as gefangen:
        dienst.anmelden("a@b.de", FALSCH, herkunft="10.0.0.1")
    assert gefangen.value.rest_sekunden > 0


def test_richtiges_passwort_kommt_waehrend_der_sperre_nicht_durch(dienst):
    """Der eigentliche Zweck: Die Sperre steht **vor** der Passwortpruefung.

    Laege sie dahinter, waere sie nur eine andere Fehlermeldung — der Aufwand,
    den ein Angreifer erzeugt, entstuende weiter.
    """
    _fehlversuche(dienst, dienst_modul.SPERRE_AB)
    with pytest.raises(ZuVieleVersuche):
        dienst.anmelden("a@b.de", PASSWORT, herkunft="10.0.0.1")


def test_zuvieleversuche_ist_ein_anmeldefehler():
    """Bestehende Behandlungen duerfen durch die Bremse nicht loechrig werden.

    Wer irgendwo ``except AnmeldeFehler`` geschrieben hat, faengt den neuen
    Fall mit — er faellt nicht ungefangen durch.
    """
    assert issubclass(ZuVieleVersuche, AnmeldeFehler)


# --------------------------------------------------------------------------- #
# 3 — Die beiden Zaehler
# --------------------------------------------------------------------------- #
def test_ein_passwort_gegen_viele_konten_faengt_der_ip_zaehler(dienst):
    """Neun verschiedene Adressen, eine Herkunft — kein E-Mail-Zaehler kaeme je an.

    Ohne den IP-Zaehler waere dies der offene Weg: EIN Passwort gegen alle
    zwoelf Uebungskonten, und jeder einzelne Zaehler bliebe bei eins.
    """
    for i in range(dienst_modul.SPERRE_AB):
        _fehlversuche(dienst, 1, email="konto%d@b.de" % i, herkunft="10.0.0.9")
    with pytest.raises(ZuVieleVersuche):
        dienst.anmelden("noch-eine@b.de", FALSCH, herkunft="10.0.0.9")


def test_ein_konto_von_vielen_adressen_faengt_der_email_zaehler(dienst):
    """Neun Herkuenfte, eine Adresse — der E-Mail-Zaehler haelt trotzdem."""
    for i in range(dienst_modul.SPERRE_AB):
        _fehlversuche(dienst, 1, email="a@b.de", herkunft="10.0.%d.1" % i)
    with pytest.raises(ZuVieleVersuche):
        dienst.anmelden("a@b.de", FALSCH, herkunft="10.0.99.1")


def test_ohne_herkunft_zaehlt_nur_die_email(dienst):
    """Ein Aufruf ohne IP darf keinen Sammelzaehler bilden.

    Ein Platzhalter wie ``unbekannt`` waere schaedlich: Alle Aufrufe ohne IP
    teilten sich einen Zaehler und sperrten sich gegenseitig aus.
    """
    _fehlversuche(dienst, dienst_modul.SPERRE_AB - 1, email="x@b.de", herkunft=None)
    # Eine andere Adresse ohne Herkunft ist davon unberuehrt.
    with pytest.raises(AnmeldeFehler) as gefangen:
        dienst.anmelden("y@b.de", FALSCH, herkunft=None)
    assert not isinstance(gefangen.value, ZuVieleVersuche)


# --------------------------------------------------------------------------- #
# 4 — Was trotzdem mitgezaehlt wird
# --------------------------------------------------------------------------- #
def test_unbekannte_adresse_wird_genauso_gesperrt(dienst):
    """Aus der Sperre darf sich nicht ablesen lassen, ob es die Adresse gibt.

    Gezaehlt wird der Versuch, nicht das Konto. Deshalb ist die Sperrmeldung
    auch kein Verrat und darf sich zu erkennen geben.
    """
    _fehlversuche(dienst, dienst_modul.SPERRE_AB, email="gibt-es-nicht@b.de")
    with pytest.raises(ZuVieleVersuche):
        dienst.anmelden("gibt-es-nicht@b.de", FALSCH, herkunft="10.0.0.1")


def test_gesperrtes_konto_wird_mitgezaehlt(dienst):
    """Sonst waere ein deaktiviertes Konto der eine Weg mit unbegrenzten Versuchen."""
    dienst.benutzer_anlegen(email="tot@b.de", name="T", passwort=PASSWORT, rolle=Rolle.BENUTZER)
    konto = dienst.benutzer.finde_per_email("tot@b.de")[0]
    dienst.benutzer_sperren(konto.benutzer_id)
    _fehlversuche(dienst, dienst_modul.SPERRE_AB, email="tot@b.de")
    with pytest.raises(ZuVieleVersuche):
        dienst.anmelden("tot@b.de", PASSWORT, herkunft="10.0.0.1")


# --------------------------------------------------------------------------- #
# 5 — Wieder freikommen
# --------------------------------------------------------------------------- #
def test_die_sperre_loest_sich_von_allein(dienst, monkeypatch):
    """Kein Mensch muss entsperren — entschieden am 02.09.2026.

    Statt fuenfzehn Minuten zu warten, wird die Uhr des Dienstes vorgestellt:
    Die Sperre wird mit einer Sperrdauer von 0 gesetzt und ist damit sofort
    abgelaufen. Geprueft wird die Regel „laeuft ab", nicht die Zahl 15.
    """
    _fehlversuche(dienst, dienst_modul.SPERRE_AB)
    with pytest.raises(ZuVieleVersuche):
        dienst.anmelden("a@b.de", PASSWORT, herkunft="10.0.0.1")

    # Sperre auf „gerade abgelaufen" setzen — wie nach Ablauf der Frist.
    verbindung = dienst.versuche._oeffnen()
    vergangen = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(seconds=1)).isoformat()
    verbindung.execute("UPDATE app_anmeldeversuche SET gesperrt_bis=?", (vergangen,))
    verbindung.commit()
    verbindung.close()

    benutzer, schluessel, _ = dienst.anmelden("a@b.de", PASSWORT, herkunft="10.0.0.1")
    assert benutzer.email == "a@b.de" and schluessel


def test_nach_der_sperre_wird_bei_null_begonnen(dienst):
    """Sonst waere die naechste Sperre schon beim ersten weiteren Fehlversuch da.

    Aus der befristeten Sperre waere dann eine dauerhafte geworden — genau
    das, was am 02.09. ausdruecklich nicht gewollt war.
    """
    _fehlversuche(dienst, dienst_modul.SPERRE_AB)
    abdruck = dienst.versuche.abdruck("email", "a@b.de")
    zaehler, gesperrt_bis = dienst.versuche.stand(abdruck)
    assert gesperrt_bis is not None
    assert zaehler == 0


def test_erfolgreiche_anmeldung_raeumt_die_tippfehler_weg(dienst):
    """Wer das Passwort kennt, soll nicht wegen der Versuche davor auffliegen."""
    _fehlversuche(dienst, dienst_modul.SPERRE_AB - 1)
    dienst.anmelden("a@b.de", PASSWORT, herkunft="10.0.0.1")
    for art, wert in (("email", "a@b.de"), ("ip", "10.0.0.1")):
        zaehler, gesperrt_bis = dienst.versuche.stand(dienst.versuche.abdruck(art, wert))
        assert (zaehler, gesperrt_bis) == (0, None), art


def test_alter_fehlversuch_zaehlt_nicht_mehr_mit(dienst):
    """Das gleitende Fenster — sonst summierten sich Tippfehler ueber Monate."""
    _fehlversuche(dienst, dienst_modul.SPERRE_AB - 1)
    alt = (_dt.datetime.now(_dt.timezone.utc)
           - dienst_modul.ZAEHLFENSTER - _dt.timedelta(minutes=1)).isoformat()
    verbindung = dienst.versuche._oeffnen()
    verbindung.execute("UPDATE app_anmeldeversuche SET letzter_am=?", (alt,))
    verbindung.commit()
    verbindung.close()

    # Der naechste Fehlversuch beginnt wieder bei 1 und sperrt nicht.
    with pytest.raises(AnmeldeFehler) as gefangen:
        dienst.anmelden("a@b.de", FALSCH, herkunft="10.0.0.1")
    assert not isinstance(gefangen.value, ZuVieleVersuche)


# --------------------------------------------------------------------------- #
# 6 — Was in der Tabelle steht
# --------------------------------------------------------------------------- #
def test_die_adresse_steht_nicht_im_klartext_in_der_tabelle(dienst):
    """Der Zaehler entsteht auch fuer Adressen, die es nicht gibt.

    Wer die Anmeldemaske mit fremden Adressen befuellt, wuerde sonst dafuer
    sorgen, dass BC0 genau diese Adressen ablegt — personenbezogene Daten von
    Menschen, die mit dem Projekt nichts zu tun haben.
    """
    _fehlversuche(dienst, 2, email="fremde.person@example.org", herkunft="203.0.113.7")
    verbindung = dienst.versuche._oeffnen()
    zeilen = verbindung.execute("SELECT * FROM app_anmeldeversuche").fetchall()
    verbindung.close()
    alles = " ".join(str(dict(z)) for z in zeilen)
    assert zeilen, "es muss gezaehlt worden sein"
    assert "fremde.person@example.org" not in alles
    assert "203.0.113.7" not in alles
    # Wer zu einer bekannten Adresse nachsehen will, bildet ihren Abdruck.
    assert dienst.versuche.abdruck("email", "fremde.person@example.org") in alles


def test_abdruck_ist_unabhaengig_von_der_schreibweise(dienst):
    """Sonst waeren ``A@b.de`` und ``a@b.de`` zwei Zaehler — und keiner erreichte die Schwelle."""
    assert (dienst.versuche.abdruck("email", "A@B.de  ")
            == dienst.versuche.abdruck("email", "a@b.de"))


# --------------------------------------------------------------------------- #
# 7 — Der Weg nach draussen: was der Browser sieht
# --------------------------------------------------------------------------- #
# Die Tests oben pruefen die Regel. Dieser prueft ihre **Uebersetzung nach
# HTTP** — und die ist eine eigene Entscheidung: 401 sagt bewusst nicht, was
# falsch war, 429 sagt es ausdruecklich. Ein Benutzer, der nicht erfaehrt, dass
# er gesperrt ist, haelt die Anwendung fuer kaputt und ruft an.


@pytest.fixture()
def bremse_frei():
    """Raeumt die Zaehler vor UND nach dem Test.

    Notwendig, nicht kosmetisch: Der Testclient meldet sich immer von derselben
    Herkunft (``testclient``). Bliebe hier eine IP-Sperre stehen, waere sie beim
    naechsten Testmodul noch da — und ``test_app_zugriff.py`` laeuft nach
    diesem, weil pytest die Dateien alphabetisch abarbeitet. Der Fehler saehe
    dann so aus, als sei die Anmeldung kaputt.
    """
    import app as anwendung

    def leeren():
        verbindung = anwendung.AUTH.versuche._oeffnen()
        verbindung.execute("DELETE FROM app_anmeldeversuche")
        verbindung.commit()
        verbindung.close()

    leeren()
    yield
    leeren()


def test_route_antwortet_mit_429_und_retry_after(bremse_frei, monkeypatch):
    """Geprueft wird die Uebersetzung nach HTTP, nicht die Schwelle.

    Die Schwellen stehen in den Tests weiter oben. Hier werden sie
    herabgesetzt, damit dieser Test nicht zehn Passwortpruefungen zu je 1,1
    Sekunden braucht, um eine Statuszahl zu pruefen.
    """
    from fastapi.testclient import TestClient

    import app as anwendung

    monkeypatch.setattr(dienst_modul, "SPERRE_AB", 3)
    monkeypatch.setattr(dienst_modul, "VERZOEGERUNG_AB", 99)  # keine Wartezeit im Test

    client = TestClient(anwendung.app)
    for _ in range(3):
        antwort = client.post("/api/auth/login",
                              json={"email": "bremse@bc0.test", "passwort": FALSCH})
        assert antwort.status_code == 401, "der Fehlversuch selbst bleibt eine 401"

    gesperrt = client.post("/api/auth/login",
                           json={"email": "bremse@bc0.test", "passwort": FALSCH})
    assert gesperrt.status_code == 429
    assert "Retry-After" in gesperrt.headers
    assert int(gesperrt.headers["Retry-After"]) > 0
    # Die Wartezeit steht auch im Text — im Kopf allein saehe sie in der
    # Oberflaeche niemand.
    assert "Minute" in gesperrt.json()["detail"]
