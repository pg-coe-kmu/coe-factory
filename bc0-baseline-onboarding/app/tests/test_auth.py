# -*- coding: utf-8 -*-
"""
Tests der Benutzerverwaltung.

Ausführen:
    cd BC0_App_PWA
    python -m pytest tests/ -v

Die Tests laufen gegen eine flüchtige SQLite-Datei und starten weder die
Anwendung noch eine Datenbankverbindung nach außen. Möglich ist das, weil die
Repositories ihre Verbindungsfabrik im Konstruktor entgegennehmen — genau dafür
ist sie so gebaut.

Geprüft werden nicht nur die Gutfälle. Der größere Teil sind die Fälle, die
*scheitern müssen*: falsches Passwort, gesperrtes Konto, abgelaufene Sitzung,
fremder Mandant. Ein Rechtemodell, das nur im Gutfall geprüft wurde, ist eine
Vermutung.
"""

from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bc0_auth import AnmeldeFehler, AuthDienst, Benutzer, Rolle  # noqa: E402
from bc0_auth import passwoerter  # noqa: E402


# --------------------------------------------------------------------------- #
# Testverbindung
# --------------------------------------------------------------------------- #
class _TestVerbindung:
    """Bildet die Verbindungsschnittstelle aus ``app.py`` nach.

    Erwartet werden ``execute(sql, params)`` mit ``?``-Platzhaltern, ``commit()``
    und ``close()`` sowie Zeilen, die sich wie ein Mapping ansprechen lassen.
    """

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


@pytest.fixture()
def dienst(tmp_path) -> AuthDienst:
    """Ein frisch eingerichteter AuthDienst auf einer leeren Datenbank."""
    pfad = str(tmp_path / "test.db")
    auth = AuthDienst(lambda: _TestVerbindung(pfad), ist_postgres=False)
    auth.einrichten()
    return auth


MANDANT_A = "11111111-1111-1111-1111-111111111111"
MANDANT_B = "22222222-2222-2222-2222-222222222222"
PASSWORT = "ein-hinreichend-langes-passwort"


# --------------------------------------------------------------------------- #
# Passwörter
# --------------------------------------------------------------------------- #
def test_hash_laesst_sich_pruefen():
    hash_text = passwoerter.hash_erzeugen(PASSWORT)
    assert passwoerter.hash_pruefen(PASSWORT, hash_text)


def test_falsches_passwort_wird_abgelehnt():
    hash_text = passwoerter.hash_erzeugen(PASSWORT)
    assert not passwoerter.hash_pruefen(PASSWORT + "x", hash_text)
    assert not passwoerter.hash_pruefen("", hash_text)


def test_gleiches_passwort_ergibt_verschiedene_hashes():
    """Das Salz muss je Passwort neu gezogen werden.

    Wären zwei Hashes desselben Passworts gleich, ließe sich aus der Tabelle
    ablesen, welche Benutzer dasselbe Passwort verwenden.
    """
    assert passwoerter.hash_erzeugen(PASSWORT) != passwoerter.hash_erzeugen(PASSWORT)


def test_beschaedigter_hash_fuehrt_nicht_zur_ausnahme():
    for kaputt in ("", "unsinn", "pbkdf2_sha256$abc$def", "md5$1$a$b"):
        assert passwoerter.hash_pruefen(PASSWORT, kaputt) is False


def test_zu_kurzes_passwort_wird_abgelehnt():
    with pytest.raises(passwoerter.PasswortFehler):
        passwoerter.hash_erzeugen("kurz")
    with pytest.raises(passwoerter.PasswortFehler):
        passwoerter.hash_erzeugen("   ")


def test_veralteter_kostenparameter_wird_erkannt():
    alt = passwoerter.hash_erzeugen(PASSWORT, durchlaeufe=1000)
    assert passwoerter.muss_neu_gehasht_werden(alt)
    assert not passwoerter.muss_neu_gehasht_werden(passwoerter.hash_erzeugen(PASSWORT))


# --------------------------------------------------------------------------- #
# Fachliche Regeln
# --------------------------------------------------------------------------- #
def test_unbekannte_rolle_wird_nicht_stillschweigend_ersetzt():
    with pytest.raises(ValueError):
        Rolle.aus_text("superadmin")


def test_admin_sieht_alle_mandanten():
    admin = Benutzer("1", "a@b.de", "A", Rolle.ADMIN, frozenset())
    assert admin.darf_mandanten_sehen(MANDANT_A)
    assert admin.darf_mandanten_sehen("beliebig")
    assert admin.darf_loeschen()
    assert admin.darf_freigeben()


def test_benutzer_sieht_nur_seinen_mandanten():
    benutzer = Benutzer("2", "b@b.de", "B", Rolle.BENUTZER, frozenset({MANDANT_A}))
    assert benutzer.darf_mandanten_sehen(MANDANT_A)
    assert not benutzer.darf_mandanten_sehen(MANDANT_B)


def test_benutzer_darf_nicht_loeschen_und_nicht_freigeben():
    benutzer = Benutzer("2", "b@b.de", "B", Rolle.BENUTZER, frozenset({MANDANT_A}))
    assert not benutzer.darf_loeschen()
    assert not benutzer.darf_freigeben()


# --------------------------------------------------------------------------- #
# Anlegen
# --------------------------------------------------------------------------- #
def test_neue_datenbank_ist_nicht_eingerichtet(dienst):
    assert dienst.ist_eingerichtet() is False


def test_benutzer_anlegen_und_wiederfinden(dienst):
    dienst.benutzer_anlegen("Chef@Firma.DE", "Chefin", PASSWORT, Rolle.ADMIN)
    assert dienst.ist_eingerichtet() is True
    treffer = dienst.benutzer.finde_per_email("chef@firma.de")
    assert treffer is not None
    assert treffer[0].name == "Chefin"
    assert treffer[0].ist_admin


def test_email_wird_unabhaengig_von_grossschreibung_gefunden(dienst):
    dienst.benutzer_anlegen("Max.Muster@Firma.DE", "Max", PASSWORT, Rolle.BENUTZER)
    assert dienst.benutzer.finde_per_email("MAX.MUSTER@firma.de") is not None


def test_doppelte_adresse_wird_abgelehnt(dienst):
    dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.BENUTZER)
    with pytest.raises(ValueError):
        dienst.benutzer_anlegen("a@b.de", "Doppelt", PASSWORT, Rolle.ADMIN)


def test_mandantenzuordnung_wird_gespeichert(dienst):
    angelegt = dienst.benutzer_anlegen(
        "m@b.de", "M", PASSWORT, Rolle.BENUTZER, mandanten=[MANDANT_A]
    )
    assert angelegt.mandanten == frozenset({MANDANT_A})
    dienst.benutzer.mandanten_setzen(angelegt.benutzer_id, [MANDANT_B])
    assert dienst.benutzer.finde_per_id(angelegt.benutzer_id).mandanten == frozenset({MANDANT_B})


# --------------------------------------------------------------------------- #
# Anmeldung
# --------------------------------------------------------------------------- #
def test_anmeldung_mit_richtigen_daten(dienst):
    dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.ADMIN)
    benutzer, schluessel, sitzung = dienst.anmelden("a@b.de", PASSWORT)
    assert benutzer.email == "a@b.de"
    assert schluessel
    assert not sitzung.ist_abgelaufen()


def test_anmeldung_mit_falschem_passwort(dienst):
    dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.ADMIN)
    with pytest.raises(AnmeldeFehler):
        dienst.anmelden("a@b.de", "falsch-aber-lang-genug")


def test_anmeldung_mit_unbekannter_adresse(dienst):
    with pytest.raises(AnmeldeFehler):
        dienst.anmelden("niemand@nirgends.de", PASSWORT)


def test_gesperrtes_konto_kann_sich_nicht_anmelden(dienst):
    angelegt = dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.BENUTZER)
    dienst.benutzer_sperren(angelegt.benutzer_id)
    with pytest.raises(AnmeldeFehler):
        dienst.anmelden("a@b.de", PASSWORT)


# --------------------------------------------------------------------------- #
# Sitzungen
# --------------------------------------------------------------------------- #
def test_sitzung_loest_den_benutzer_auf(dienst):
    dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.ADMIN)
    _, schluessel, _ = dienst.anmelden("a@b.de", PASSWORT)
    aufgeloest = dienst.benutzer_zu_sitzung(schluessel)
    assert aufgeloest is not None and aufgeloest.email == "a@b.de"


def test_unbekannter_schluessel_loest_nichts_auf(dienst):
    assert dienst.benutzer_zu_sitzung("frei-erfunden") is None
    assert dienst.benutzer_zu_sitzung(None) is None
    assert dienst.benutzer_zu_sitzung("") is None


def test_schluessel_steht_nicht_im_klartext_in_der_datenbank(dienst, tmp_path):
    """Der wichtigste Test dieser Datei.

    Ein Backup der Datenbank darf niemandem erlauben, eine offene Sitzung zu
    übernehmen. Gespeichert wird deshalb nur der SHA-256-Abdruck.
    """
    dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.ADMIN)
    _, schluessel, _ = dienst.anmelden("a@b.de", PASSWORT)
    verbindung = dienst.sitzungen._oeffnen()
    try:
        gespeichert = verbindung.execute(
            "SELECT schluessel_abdruck FROM app_sitzungen"
        ).fetchone()["schluessel_abdruck"]
    finally:
        verbindung.close()
    assert gespeichert != schluessel
    assert gespeichert == passwoerter.schluessel_abdruck(schluessel)


def test_abmelden_macht_die_sitzung_ungueltig(dienst):
    dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.ADMIN)
    _, schluessel, _ = dienst.anmelden("a@b.de", PASSWORT)
    dienst.abmelden(schluessel)
    assert dienst.benutzer_zu_sitzung(schluessel) is None


def test_abgelaufene_sitzung_wird_abgewiesen(tmp_path):
    pfad = str(tmp_path / "ablauf.db")
    auth = AuthDienst(
        lambda: _TestVerbindung(pfad),
        ist_postgres=False,
        sitzungsdauer=_dt.timedelta(seconds=-1),  # bereits abgelaufen
    )
    auth.einrichten()
    auth.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.ADMIN)
    _, schluessel, sitzung = auth.anmelden("a@b.de", PASSWORT)
    assert sitzung.ist_abgelaufen()
    assert auth.benutzer_zu_sitzung(schluessel) is None


def test_passwortwechsel_beendet_alle_sitzungen(dienst):
    angelegt = dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.ADMIN)
    _, schluessel_eins, _ = dienst.anmelden("a@b.de", PASSWORT)
    _, schluessel_zwei, _ = dienst.anmelden("a@b.de", PASSWORT)
    dienst.passwort_aendern(angelegt.benutzer_id, "ein-neues-langes-passwort")
    assert dienst.benutzer_zu_sitzung(schluessel_eins) is None
    assert dienst.benutzer_zu_sitzung(schluessel_zwei) is None
    # Mit dem neuen Passwort geht es wieder.
    assert dienst.anmelden("a@b.de", "ein-neues-langes-passwort")[0].email == "a@b.de"


def test_sperren_beendet_laufende_sitzung(dienst):
    """Eine Sperre wirkt sofort, nicht erst bei der nächsten Anmeldung."""
    angelegt = dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.BENUTZER)
    _, schluessel, _ = dienst.anmelden("a@b.de", PASSWORT)
    assert dienst.benutzer_zu_sitzung(schluessel) is not None
    dienst.benutzer_sperren(angelegt.benutzer_id)
    assert dienst.benutzer_zu_sitzung(schluessel) is None


def test_rollenwechsel_wirkt_ohne_neuanmeldung(dienst):
    """Der Benutzer wird je Anfrage neu geladen — eine Höherstufung wirkt sofort."""
    angelegt = dienst.benutzer_anlegen("a@b.de", "A", PASSWORT, Rolle.BENUTZER)
    _, schluessel, _ = dienst.anmelden("a@b.de", PASSWORT)
    assert not dienst.benutzer_zu_sitzung(schluessel).ist_admin
    dienst.benutzer.rolle_setzen(angelegt.benutzer_id, Rolle.ADMIN)
    assert dienst.benutzer_zu_sitzung(schluessel).ist_admin
