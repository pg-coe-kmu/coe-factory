# -*- coding: utf-8 -*-
"""
Tests für das Entitäten-Register (ADR-004): Personen, Systeme, Zuordnungen.

Vier Eigenschaften sind hier wichtiger als das Speichern selbst:

**IDs werden nie wiederverwendet.** Wird P-03 gesperrt, bleibt P-03 belegt. Ein
zählerbasierter Ansatz würde die Nummer erneut vergeben, und ein alter Verweis
aus BC1 zeigte danach auf eine andere Person als bei seiner Entstehung.

**Der Name darf leer sein.** „externer Steuerberater" ist ein realer Beteiligter
ohne erhobenen Namen. Ohne ID ginge der Verweis aus dem Prozess verloren.

**Jeder Block ist einzeln optional.** Ein PUT nur mit `personen` darf Systeme
und Zuordnungen nicht anfassen — sonst löscht ein Teilformular still, was es gar
nicht anzeigt.

**Eine abgewiesene Zuordnung darf die Tabelle nicht leeren.** Geprüft wird vor
dem Löschen, nicht danach.

Seit dem 18.08.2026 (Schema v1.5) kommt eine fünfte dazu: **Die dienstlichen
Kontaktdaten verlassen BC0 nicht.** Sie stehen nach ADR-004 R5 an derselben
Stelle wie der Klarname, und keine der pseudonymisierten Sichten gibt sie aus.
"""

from __future__ import annotations

import glob
import os
import re
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "entitaeten-admin-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("ent-admin@bc0.test", "Ent-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "ent-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    m = str(client.post("/api/companies", json={"name": "Entitäten GmbH", "kps": [1, 2]}).json()["id"])
    # Eine Rolle, damit die Kostenklassen-Zuordnung geprüft werden kann.
    client.put("/api/companies/" + m + "/rollen_kosten", json={
        "rollen": [{"bezeichnung": "Geschäftsführung", "klasse": "K5"}], "kostensaetze": []})
    return m


def _pfad(mandant: str) -> str:
    return "/api/companies/" + mandant + "/entitaeten"


def _hole(client, mandant):
    return client.get(_pfad(mandant)).json()


# --------------------------------------------------------------------------- #
# Personen
# --------------------------------------------------------------------------- #
def test_leerer_mandant_liefert_die_auswahllisten(client, mandant):
    """Die Oberfläche darf keine zweite Werteliste führen müssen."""
    d = _hole(client, mandant)
    assert d["personen"] == []
    assert d["systeme"] == []
    assert [b["wert"] for b in d["beteiligungen"]] == \
        ["eigner", "sponsor", "mitwirkend", "vertretung"]
    # Welche Kernprozess-Nummern das Anlegen vergibt, haengt am Katalog —
    # deshalb wird die Menge geprueft und nicht auf feste IDs gewettet.
    assert len(d["prozesse"]) == 2
    assert all(p["process_id"].startswith("KP-") for p in d["prozesse"])
    assert d["rollen"] and d["rollen"][0]["klasse"] == "K5"


def test_personen_bekommen_fortlaufende_ids(client, mandant):
    client.put(_pfad(mandant), json={"personen": [
        {"name": "Sergio Morazán Irias", "funktion": "MD"},
        {"name": "Zakaria Samih", "funktion": "Lead DevOps"},
    ]})
    personen = _hole(client, mandant)["personen"]
    assert [p["person_id"] for p in personen] == ["P-01", "P-02"]
    assert personen[0]["name"] == "Sergio Morazán Irias"


def test_person_ohne_namen_ist_erlaubt(client, mandant):
    """„externer Steuerberater" hat keinen erhobenen Namen, aber eine Rolle im Prozess."""
    d = _hole(client, mandant)
    d["personen"].append({"funktion": "externer Steuerberater", "extern": True,
                          "organisation": "Kanzlei N.N."})
    client.put(_pfad(mandant), json={"personen": d["personen"]})
    neu = {p["person_id"]: p for p in _hole(client, mandant)["personen"]}["P-03"]
    assert neu["name"] is None
    assert neu["funktion"] == "externer Steuerberater"
    assert neu["extern"] is True


def test_person_ohne_namen_und_ohne_funktion_wird_uebergangen(client, mandant):
    vorher = len(_hole(client, mandant)["personen"])
    d = _hole(client, mandant)
    d["personen"].append({"name": "   ", "funktion": ""})
    client.put(_pfad(mandant), json={"personen": d["personen"]})
    assert len(_hole(client, mandant)["personen"]) == vorher


def test_bestehende_person_behaelt_ihre_id(client, mandant):
    """Die ID ist der Anker für BC1 — Umbenennen darf sie nicht ändern."""
    d = _hole(client, mandant)
    d["personen"][0]["name"] = "Sergio Morazán Irias (GF)"
    client.put(_pfad(mandant), json={"personen": d["personen"]})
    nachher = _hole(client, mandant)["personen"]
    assert nachher[0]["person_id"] == "P-01"
    assert nachher[0]["name"] == "Sergio Morazán Irias (GF)"


def test_entfernte_person_wird_gesperrt_statt_geloescht(client, mandant):
    d = _hole(client, mandant)
    ohne_p02 = [p for p in d["personen"] if p["person_id"] != "P-02"]
    client.put(_pfad(mandant), json={"personen": ohne_p02})
    personen = {p["person_id"]: p for p in _hole(client, mandant)["personen"]}
    assert "P-02" in personen, "die Person darf nicht verschwinden"
    assert personen["P-02"]["aktiv"] is False


def test_gesperrte_person_bleibt_gesperrt_beim_naechsten_speichern(client, mandant):
    """Derselbe Fehler war am 11.08. bei den Rollen erst im PostgreSQL-Lauf aufgefallen:
    Die Oberfläche schickt gesperrte Zeilen mit, und wenn der Server den Status aus
    der Anwesenheit in der Liste ableitet, ist jede Sperre beim nächsten Speichern weg."""
    d = _hole(client, mandant)
    gesperrt = [p["person_id"] for p in d["personen"] if not p["aktiv"]]
    assert gesperrt, "Vorbedingung: mindestens eine gesperrte Person"
    client.put(_pfad(mandant), json={"personen": d["personen"]})
    danach = {p["person_id"]: p["aktiv"] for p in _hole(client, mandant)["personen"]}
    for pid in gesperrt:
        assert danach[pid] is False, "die Sperre wurde aufgehoben"


def test_gesperrte_person_gibt_ihre_id_nicht_frei(client, mandant):
    """ADR-004 R3. Der wichtigste Test dieser Datei.

    P-02 ist gesperrt. Eine neue Person darf trotzdem nicht P-02 bekommen —
    sonst zeigte ein alter Verweis aus BC1 auf einen anderen Menschen.
    """
    d = _hole(client, mandant)
    hoechste = max(int(p["person_id"].split("-")[1]) for p in d["personen"])
    d["personen"].append({"name": "Neu Zugang"})
    client.put(_pfad(mandant), json={"personen": d["personen"]})
    ids = [p["person_id"] for p in _hole(client, mandant)["personen"]]
    assert "P-%02d" % (hoechste + 1) in ids
    assert len(ids) == len(set(ids)), "IDs sind doppelt vergeben"


def test_unbekannte_rolle_wird_abgelehnt(client, mandant):
    antwort = client.put(_pfad(mandant), json={
        "personen": [{"name": "Wer", "rolle_id": "R-99"}]})
    assert antwort.status_code == 400


# --------------------------------------------------------------------------- #
# Systeme
# --------------------------------------------------------------------------- #
def test_system_ohne_katalogbezug_ist_erlaubt(client, mandant):
    """„Strategie-Cockpit" benennt eine Gattung, kein Produkt."""
    client.put(_pfad(mandant), json={"systeme": [
        {"bezeichnung": "Strategie-Cockpit", "einsatz": "Zielverfolgung"},
    ]})
    systeme = _hole(client, mandant)["systeme"]
    assert systeme[0]["system_id"] == "S-01"
    assert systeme[0]["katalog_id"] is None


def test_katalog_ist_vorbelegt_und_verwendbar(client, mandant):
    """Der Katalog ist global wie die 30 Bitkom-Items und steht ohne Pflege bereit.
    Sonst müsste jeder Mandant „EspoCRM" neu erfinden — und genau die Schreibweisen
    würden später auseinanderlaufen."""
    katalog = {k["katalog_id"]: k for k in _hole(client, mandant)["katalog"]}
    assert "SYS-CRM-ESPO" in katalog
    assert katalog["SYS-CRM-ESPO"]["kategorie"] == "crm"

    systeme = _hole(client, mandant)["systeme"]
    systeme.append({"bezeichnung": "Espo", "katalog_id": "SYS-CRM-ESPO"})
    assert client.put(_pfad(mandant), json={"systeme": systeme}).status_code == 200
    neu = [s for s in _hole(client, mandant)["systeme"] if s["bezeichnung"] == "Espo"]
    assert neu and neu[0]["katalog_id"] == "SYS-CRM-ESPO"


def test_unbekanntes_katalogprodukt_wird_abgelehnt(client, mandant):
    antwort = client.put(_pfad(mandant), json={
        "systeme": [{"bezeichnung": "Irgendwas", "katalog_id": "SYS-XX-NIX"}]})
    assert antwort.status_code == 400


def test_entferntes_system_wird_gesperrt_statt_geloescht(client, mandant):
    client.put(_pfad(mandant), json={"systeme": []})
    systeme = {s["system_id"]: s for s in _hole(client, mandant)["systeme"]}
    assert "S-01" in systeme
    assert systeme["S-01"]["aktiv"] is False


# --------------------------------------------------------------------------- #
# Blockweise Unabhängigkeit
# --------------------------------------------------------------------------- #
def test_teilformular_loescht_nicht_was_es_nicht_anzeigt(client, mandant):
    """Ein PUT nur mit `personen` darf Systeme nicht sperren."""
    client.put(_pfad(mandant), json={"systeme": [
        {"system_id": "S-01", "bezeichnung": "Strategie-Cockpit", "aktiv": True}]})
    assert _hole(client, mandant)["systeme"][0]["aktiv"] is True

    d = _hole(client, mandant)
    client.put(_pfad(mandant), json={"personen": d["personen"]})   # ohne "systeme"

    assert _hole(client, mandant)["systeme"][0]["aktiv"] is True, \
        "der Systemblock wurde angefasst, obwohl er nicht mitgeschickt wurde"


# --------------------------------------------------------------------------- #
# Zuordnungen
# --------------------------------------------------------------------------- #
def test_mehrere_eigner_und_doppelrolle_sind_moeglich(client, mandant):
    """Genau das ließ sich in owner_name nicht abbilden:
    „Ozan Kiraz / Mehdi Louali" (zwei Eigner) und
    „Engagement Manager · Sponsor: Sergio" (Eigner und Sponsor nebeneinander)."""
    kp_a, kp_b = [p["process_id"] for p in _hole(client, mandant)["prozesse"]]
    antwort = client.put(_pfad(mandant), json={"zuordnungen": [
        {"process_id": kp_a, "person_id": "P-01", "funktion": "eigner"},
        {"process_id": kp_a, "person_id": "P-01", "funktion": "sponsor"},
        {"process_id": kp_b, "person_id": "P-01", "funktion": "eigner"},
        {"process_id": kp_b, "person_id": "P-03", "funktion": "mitwirkend"},
    ]})
    assert antwort.status_code == 200
    z = _hole(client, mandant)["zuordnungen"]
    assert len(z) == 4
    erster = sorted(x["funktion"] for x in z if x["process_id"] == kp_a)
    assert erster == ["eigner", "sponsor"]


def test_unbekannte_beteiligung_wird_abgelehnt(client, mandant):
    kp_a = _hole(client, mandant)["prozesse"][0]["process_id"]
    antwort = client.put(_pfad(mandant), json={"zuordnungen": [
        {"process_id": kp_a, "person_id": "P-01", "funktion": "chef"}]})
    assert antwort.status_code == 400


def test_abgewiesene_zuordnung_leert_die_tabelle_nicht(client, mandant):
    """Erst prüfen, dann löschen. Sonst stünde die Tabelle nach einem
    abgewiesenen Eintrag leer da — und das Speichern hätte einen Fehler
    gemeldet, während die Daten schon weg sind."""
    vorher = _hole(client, mandant)["zuordnungen"]
    assert vorher, "Vorbedingung: es gibt Zuordnungen"

    kp_a = vorher[0]["process_id"]
    antwort = client.put(_pfad(mandant), json={"zuordnungen": [
        {"process_id": kp_a, "person_id": "P-01", "funktion": "eigner"},
        {"process_id": "KP-99", "person_id": "P-01", "funktion": "eigner"},   # falsch
    ]})
    assert antwort.status_code == 400
    assert _hole(client, mandant)["zuordnungen"] == vorher


def test_unbekannte_person_in_der_zuordnung_wird_abgelehnt(client, mandant):
    kp_a = _hole(client, mandant)["prozesse"][0]["process_id"]
    antwort = client.put(_pfad(mandant), json={"zuordnungen": [
        {"process_id": kp_a, "person_id": "P-77", "funktion": "eigner"}]})
    assert antwort.status_code == 400


# --------------------------------------------------------------------------- #
# Dienstliche Kontaktdaten (Entscheidung vom 17.08.2026, Schema v1.5)
#
# Wer im Interview eine Rückfrage hat, fand bisher keinen Weg zur Person: Der
# Prozess kennt eine person_id, das Register einen Namen — und damit endete die
# Spur. Erfasst wird ausschließlich das Dienstliche.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def kontakt_mandant(client) -> str:
    """Eigener Mandant: Die Tests oben verändern den Personenbestand fortlaufend."""
    return str(client.post("/api/companies",
                           json={"name": "Kontakt GmbH", "kps": [1]}).json()["id"])


def test_kontaktdaten_werden_gespeichert_und_gelesen(client, kontakt_mandant):
    client.put(_pfad(kontakt_mandant), json={"personen": [
        {"name": "Ida Eigner", "funktion": "Vertriebsleitung",
         "email": "i.eigner@noroai.example", "telefon": "+49 30 123456-17"}]})
    person = _hole(client, kontakt_mandant)["personen"][0]
    assert person["email"] == "i.eigner@noroai.example"
    assert person["telefon"] == "+49 30 123456-17"


def test_kontaktdaten_duerfen_leer_bleiben(client, kontakt_mandant):
    """Wie beim Namen: Nicht erhoben ist ein zulässiger Zustand.

    Ein Pflichtfeld erzeugte hier nur Erfindungen — „externer Steuerberater" hat
    oft keine Nummer im Haus.
    """
    d = _hole(client, kontakt_mandant)
    d["personen"].append({"funktion": "externer Steuerberater", "extern": True})
    antwort = client.put(_pfad(kontakt_mandant), json={"personen": d["personen"]})
    assert antwort.status_code == 200, antwort.text
    neu = _hole(client, kontakt_mandant)["personen"][1]
    assert neu["email"] is None and neu["telefon"] is None


def test_telefonnummer_hat_keinen_formatzwang(client, kontakt_mandant):
    """Durchwahl, Landesvorwahl und Mobilnummer stehen im Haus in mehreren
    Schreibweisen — keine davon ist falsch."""
    d = _hole(client, kontakt_mandant)
    d["personen"][1]["telefon"] = "Zentrale, App. 4"
    assert client.put(_pfad(kontakt_mandant), json={"personen": d["personen"]}).status_code == 200
    assert _hole(client, kontakt_mandant)["personen"][1]["telefon"] == "Zentrale, App. 4"


def test_email_ohne_klammeraffen_wird_abgewiesen(client, kontakt_mandant):
    """Die einzige Prüfung, und sie greift nur bei gefülltem Feld: Ein Tippfehler
    im Verteiler fällt sonst erst auf, wenn die Rückfrage nicht ankommt."""
    d = _hole(client, kontakt_mandant)
    d["personen"][0]["email"] = "i.eigner.noroai.example"
    antwort = client.put(_pfad(kontakt_mandant), json={"personen": d["personen"]})
    assert antwort.status_code == 400
    assert "i.eigner.noroai.example" in antwort.json()["detail"]
    assert _hole(client, kontakt_mandant)["personen"][0]["email"] == "i.eigner@noroai.example"


# --------------------------------------------------------------------------- #
# Die Zusicherung, an der die ganze Änderung hängt (ADR-004 R5)
# --------------------------------------------------------------------------- #
#: Zeichenketten, die in keiner Lesesicht auf ref_personen vorkommen dürfen.
KONTAKTSPALTEN = ("email", "telefon")

_VIEW = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(\w+)\s+AS(.*?);", re.S | re.I)


def _schemaskripte():
    verzeichnis = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pfade = glob.glob(os.path.join(verzeichnis, "*.sql"))
    # Das Gate-Schema liegt neben dem Anwendungsverzeichnis, nicht darin.
    pfade += glob.glob(os.path.join(os.path.dirname(verzeichnis), "gate0", "*.sql"))
    return sorted(pfade)


def _sichten(pfad):
    """(Name, Rumpf) je CREATE VIEW. Kommentarzeilen fallen weg — ein Wort wie
    „email" in einer Erläuterung darf den Test nicht auslösen."""
    text = open(pfad, encoding="utf-8").read()
    ohne_kommentar = "\n".join(z.split("--")[0] for z in text.splitlines())
    return [(t.group(1), t.group(2)) for t in _VIEW.finditer(ohne_kommentar)]


def test_keine_sicht_gibt_kontaktdaten_aus():
    """Die pseudonymisierten Sichten dürfen sich nicht durch neue Spalten erweitern.

    Geprüft wird der Quelltext der Schemaskripte und nicht die laufende
    Datenbank: Im Entwicklungsmodus läuft SQLite, das diese Sichten gar nicht
    kennt — der Fehler entstünde aber schon beim Schreiben des Skripts. Ein
    `SELECT *` auf ref_personen wäre genau die stille Erweiterung, gegen die
    ADR-004 R5 steht; deshalb wird auch danach gesucht und nicht nur nach den
    beiden Spaltennamen.
    """
    geprueft = []
    for pfad in _schemaskripte():
        for name, rumpf in _sichten(pfad):
            if "ref_personen" not in rumpf:
                continue
            geprueft.append(name)
            klein = rumpf.lower()
            for spalte in KONTAKTSPALTEN:
                assert spalte not in klein, \
                    "%s (%s) gibt %s aus" % (name, os.path.basename(pfad), spalte)
            assert not re.search(r"select\s+\*", rumpf, re.I), \
                "%s liest ref_personen mit SELECT * und waechst still mit" % name
            assert not re.search(r"\w+\.\*", rumpf), \
                "%s liest eine Tabelle mit alias.* und waechst still mit" % name
    assert "v_prozess_personen_lesen" in geprueft, \
        "die Sicht, auf die es ankommt, wurde gar nicht gefunden"


# --------------------------------------------------------------------------- #
# Mandantentrennung
# --------------------------------------------------------------------------- #
def test_fremder_mandant_bleibt_gesperrt(client, mandant):
    fremd = str(client.post("/api/companies", json={"name": "Fremd AG", "kps": []}).json()["id"])
    anwendung.AUTH.benutzer_anlegen("ent-nutzer@bc0.test", "Nutzer", "ent-nutzer-passwort",
                                    Rolle.BENUTZER, mandanten=[mandant])
    client.cookies.clear()
    client.post("/api/auth/login",
                json={"email": "ent-nutzer@bc0.test", "passwort": "ent-nutzer-passwort"})
    assert client.get(_pfad(mandant)).status_code == 200
    assert client.get(_pfad(fremd)).status_code == 404
    assert client.put(_pfad(fremd), json={"personen": []}).status_code == 404


def test_anmeldung_ist_pflicht(mandant):
    """Ohne Sitzung kein Zugriff — Klarnamen stehen in diesem Endpunkt."""
    anonym = TestClient(anwendung.app)
    assert anonym.get(_pfad(mandant)).status_code == 401
