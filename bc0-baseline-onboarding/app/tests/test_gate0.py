# -*- coding: utf-8 -*-
"""
Tests für den Gate-0-Freigabebogen (Schema v1.4).

Drei Eigenschaften sind hier wichtiger als das Speichern selbst:

**Der Bogen ist Administratoren vorbehalten.** Die Freigabe löst BC2 aus und
betrifft das ganze Unternehmen; sie ist keine Pflegehandlung. Ein normaler
Benutzer scheitert deshalb auf *jedem* der Endpunkte — auch auf den lesenden.

**Eine Freigabe ohne Güte wird abgewiesen.** „100 % vorhanden" heißt nur, dass
ein Wert dasteht, nicht dass er stimmt. Ginge eine Freigabe ohne Güteangabe
durch, rechnete BC2 einen Punktwert, ohne je zu erfahren, worauf er beruht —
genau die Scheingenauigkeit, die das Gate abfangen soll.

**Eine Zurückweisung ohne Maßnahme wird abgewiesen.** „Nein" ohne Antwort auf die
Frage „was passiert jetzt?" ist eine Sackgasse.

Dazu die Zusicherung, ohne die eine Freigabe nicht reproduzierbar wäre: Im
Ereignis steht die Erhebung, auf die sie sich bezieht — als kopierter Wert.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW_ADMIN = "gate-admin-passwort"
PW_NUTZER = "gate-nutzer-passwort"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("gate-admin@bc0.test", "Gate-Admin", PW_ADMIN, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "gate-admin@bc0.test", "passwort": PW_ADMIN})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    """Ein Mandant, dessen erster Teilprozess alle Vorbedingungen erfüllt."""
    cid = str(client.post("/api/companies",
                          json={"name": "Gate GmbH", "kps": [1]}).json()["id"])
    # Eigner und Ansprechpartner — beides Vorbedingung, beides am Kernprozess.
    client.put("/api/companies/" + cid + "/entitaeten", json={
        "personen": [{"name": "Ida Eigner", "funktion": "Vertriebsleitung"},
                     {"name": "Ole Auskunft", "funktion": "Sachbearbeitung"}],
        "zuordnungen": []})
    personen = client.get("/api/companies/" + cid + "/entitaeten").json()["personen"]
    pid = _erster_kp(client, cid)
    client.put("/api/companies/" + cid + "/entitaeten", json={"zuordnungen": [
        {"process_id": pid, "person_id": personen[0]["person_id"], "funktion": "eigner"},
        {"process_id": pid, "person_id": personen[1]["person_id"], "funktion": "mitwirkend"}]})
    # 30 bewertete Items auf TP-1 — die dritte Vorbedingung.
    items = {str(n): {"stufe": 4, "beleg": "Beleg %d" % n} for n in range(1, 31)}
    client.post("/api/companies/" + cid + "/rating",
                json={"key": pid + ".TP-1", "items": items})
    return cid


@pytest.fixture(scope="module")
def nutzer_client(client, mandant) -> TestClient:
    """Ein normaler Benutzer *mit* Zugriff auf den Mandanten.

    Der Zugriff ist wesentlich: Scheiterte er schon an der Mandantentrennung,
    bewiese der Test nichts über die Admin-Beschränkung.
    """
    anwendung.AUTH.benutzer_anlegen("gate-nutzer@bc0.test", "Gate-Nutzer", PW_NUTZER,
                                    Rolle.BENUTZER, mandanten=[mandant])
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "gate-nutzer@bc0.test", "passwort": PW_NUTZER})
    return c


def _erster_kp(client, cid: str) -> str:
    return sorted(client.get("/api/companies/" + cid).json()["processes"].keys())[0]


def _tp(client, cid: str) -> str:
    return _erster_kp(client, cid) + ".TP-1"


def _punkte(guete_dauer="belegt"):
    """Ein vollständig ausgefüllter Prüfbogen; die Güte der Dauer ist einstellbar."""
    punkte = []
    for name, bezeichnung, erl, quelle, guete_noetig, pflicht, aktiv, reihe in anwendung.GATE_PRUEFPUNKTE:
        if not aktiv:
            continue
        guete = (guete_dauer if name == "dauer" else ("belegt" if guete_noetig else None))
        punkte.append({"pruefpunkt": name, "vorhanden_pct": 100, "guete": guete,
                       "bestaetigt": True, "anmerkung": None})
    return punkte


# --------------------------------------------------------------------------- #
# Die zentrale Anforderung: nur Administratoren
# --------------------------------------------------------------------------- #
def test_benutzer_scheitert_auf_allen_gate_endpunkten(nutzer_client, mandant, client):
    """Ein normaler Benutzer darf den Bogen nicht einmal lesen.

    403 und nicht 404: Der Mandant ist ihm zugeordnet, er kennt ihn. Was ihm
    fehlt, ist die Rolle.
    """
    tp = _tp(client, mandant)
    basis = "/api/companies/" + mandant
    assert nutzer_client.get(basis + "/gate").status_code == 403
    assert nutzer_client.get(basis + "/gate/" + tp).status_code == 403
    assert nutzer_client.post(basis + "/gate/" + tp,
                              json={"ereignis": "freigegeben", "kette_bestaetigt": True,
                                    "punkte": _punkte()}).status_code == 403
    assert nutzer_client.get(basis + "/anfragen").status_code == 403
    assert nutzer_client.post(basis + "/anfragen",
                              json={"originaltext": "Geht da was mit KI?"}).status_code == 403


def test_benutzer_sieht_die_freigabe_nicht_in_der_liste(nutzer_client, mandant):
    """Auch nach einer Freigabe bleibt der Bogen für ihn verschlossen."""
    assert nutzer_client.get("/api/companies/" + mandant + "/gate").status_code == 403


# --------------------------------------------------------------------------- #
def test_admin_bekommt_die_liste(client, mandant):
    antwort = client.get("/api/companies/" + mandant + "/gate")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert len(daten["teilprozesse"]) == 5, "ein Kernprozess hat fuenf Teilprozesse"
    erster = [t for t in daten["teilprozesse"] if t["sub_process_id"] == _tp(client, mandant)][0]
    assert erster["eigner_benannt"] and erster["ansprechpartner_benannt"]
    assert erster["items_bewertet"] == 30 and erster["vollstaendig_bewertet"]
    assert erster["reifegrad"] == 4.0 and erster["ueber_schwelle"]
    assert erster["bogen_ausfuellbar"]
    assert erster["stand"] is None, "noch ist nichts entschieden"


def test_bogen_zeigt_pruefpunkte_und_kette(client, mandant):
    bogen = client.get("/api/companies/" + mandant + "/gate/" + _tp(client, mandant)).json()
    namen = [p["pruefpunkt"] for p in bogen["pruefpunkte"]]
    assert namen[0] == "dauer", "Reihenfolge kommt aus dem Katalog"
    assert "zulaessigkeit" not in namen, "nicht aktive Pruefpunkte erscheinen nicht"
    assert bogen["kette"] == {"liefert_an": [], "empfaengt_von": []}


def test_teilprozess_ohne_vorbedingungen_ist_gesperrt(client, mandant):
    """TP-2 ist nicht bewertet — der Bogen ist nicht auszufüllen, und eine
    Freigabe wird auch dann abgewiesen, wenn jemand den Endpunkt direkt aufruft."""
    tp2 = _erster_kp(client, mandant) + ".TP-2"
    bogen = client.get("/api/companies/" + mandant + "/gate/" + tp2).json()
    assert bogen["bogen_ausfuellbar"] is False
    antwort = client.post("/api/companies/" + mandant + "/gate/" + tp2,
                          json={"ereignis": "freigegeben", "kette_bestaetigt": True,
                                "punkte": _punkte()})
    assert antwort.status_code == 400
    assert "Items" in antwort.json()["detail"]


# --------------------------------------------------------------------------- #
# Die beiden Regeln, die der Server durchsetzt
# --------------------------------------------------------------------------- #
def test_freigabe_ohne_guete_bei_dauer_scheitert(client, mandant):
    """Die Dauer geht in die Rechnung ein. Ohne Güte weiß BC2 nicht, ob sie
    gemessen oder geraten ist — und rechnet trotzdem einen Punktwert."""
    antwort = client.post("/api/companies/" + mandant + "/gate/" + _tp(client, mandant),
                          json={"ereignis": "freigegeben", "kette_bestaetigt": True,
                                "punkte": _punkte(guete_dauer=None)})
    assert antwort.status_code == 400
    assert "dauer" in antwort.json()["detail"]
    assert "Guete" in antwort.json()["detail"]


def test_zurueckweisung_ohne_massnahme_scheitert(client, mandant):
    antwort = client.post("/api/companies/" + mandant + "/gate/" + _tp(client, mandant),
                          json={"ereignis": "zurueckgewiesen", "kette_bestaetigt": True,
                                "grund": "Zeitanteil einer Rolle offen", "punkte": []})
    assert antwort.status_code == 400
    assert "Massnahme" in antwort.json()["detail"]


def test_zurueckweisung_ohne_grund_scheitert(client, mandant):
    antwort = client.post("/api/companies/" + mandant + "/gate/" + _tp(client, mandant),
                          json={"ereignis": "zurueckgewiesen", "kette_bestaetigt": True,
                                "massnahme": "P-04 eintragen", "punkte": []})
    assert antwort.status_code == 400
    assert "Begruendung" in antwort.json()["detail"]


def test_unbekannter_pruefpunkt_scheitert(client, mandant):
    antwort = client.post("/api/companies/" + mandant + "/gate/" + _tp(client, mandant),
                          json={"ereignis": "zurueckgewiesen", "kette_bestaetigt": True,
                                "grund": "unklar", "massnahme": "nachfassen",
                                "punkte": [{"pruefpunkt": "wetterlage", "bestaetigt": True}]})
    assert antwort.status_code == 400
    assert "wetterlage" in antwort.json()["detail"]


def test_zurueckweisung_darf_abbrechen(client, mandant):
    """Eine Zurückweisung braucht **keine** vollständige Güte — wer abbricht,
    muss nicht erst jeden Punkt bewerten."""
    antwort = client.post("/api/companies/" + mandant + "/gate/" + _tp(client, mandant),
                          json={"ereignis": "zurueckgewiesen", "kette_bestaetigt": False,
                                "kette_ergaenzung": "KP-07 liefert zu, steht nicht drin",
                                "grund": "Kein Ansprechpartner im Interview erreichbar",
                                "massnahme": "Ansprechpartner benennen, KW 34 nachfassen",
                                "punkte": [{"pruefpunkt": "dauer", "vorhanden_pct": 100,
                                            "guete": None, "bestaetigt": False,
                                            "anmerkung": "keine Messung"}]})
    assert antwort.status_code == 200, antwort.text
    liste = client.get("/api/companies/" + mandant + "/gate").json()["teilprozesse"]
    zeile = [t for t in liste if t["sub_process_id"] == _tp(client, mandant)][0]
    assert zeile["stand"] == "zurueckgewiesen"
    assert zeile["hinweis_an_bc2"] == "nicht freigegeben"


# --------------------------------------------------------------------------- #
def test_freigabe_wird_geschrieben_und_erscheint_im_naechsten_get(client, mandant):
    tp = _tp(client, mandant)
    anfrage = client.post("/api/companies/" + mandant + "/anfragen", json={
        "originaltext": "Wir verlieren zu viel Zeit beim Angebotschreiben. Geht da was mit KI?",
        "eingang_weg": "Mail"})
    assert anfrage.status_code == 200
    antwort = client.post("/api/companies/" + mandant + "/gate/" + tp, json={
        "ereignis": "freigegeben", "anfrage_id": anfrage.json()["anfrage_id"],
        "kette_bestaetigt": True, "punkte": _punkte(guete_dauer="geschaetzt")})
    assert antwort.status_code == 200, antwort.text

    liste = client.get("/api/companies/" + mandant + "/gate").json()["teilprozesse"]
    zeile = [t for t in liste if t["sub_process_id"] == tp][0]
    assert zeile["stand"] == "freigegeben"
    assert zeile["entschieden_am"]
    assert zeile["hinweis_an_bc2"].startswith("Bandbreite empfohlen"), \
        "die Guete der Dauer muss an BC2 mitwandern"

    bogen = client.get("/api/companies/" + mandant + "/gate/" + tp).json()
    stand = bogen["letzter_stand"]
    assert stand["stand"] == "freigegeben"
    assert stand["anfrage_id"] == anfrage.json()["anfrage_id"]
    assert stand["kette_bestaetigt"] is True
    gueten = {p["pruefpunkt"]: p["guete"] for p in stand["punkte"]}
    assert gueten["dauer"] == "geschaetzt" and gueten["haeufigkeit"] == "belegt"
    assert gueten["prozessbeschreibung"] is None, "ohne Guetepflicht bleibt das Feld leer"


def test_erhebung_ist_im_ereignis_gesetzt(client, mandant):
    """Ohne den festgehaltenen Datenstand wäre die Freigabe nicht reproduzierbar.

    Der Wert ist **kopiert**, nicht verwiesen: Ein Verweis wanderte mit, und die
    Freigabe behauptete rückwirkend, etwas geprüft zu haben, das es damals nicht
    gab.
    """
    massgeblich = client.get("/api/companies/" + mandant + "/erhebungen").json()["massgeblich"]
    c = anwendung.db()
    try:
        zeile = c.execute(
            "SELECT erhebung_id, benutzer_id, objekt_typ, gate FROM gate_ereignisse WHERE "
            + anwendung.W_CO + " AND ereignis='freigegeben' ORDER BY ereignis_id DESC LIMIT 1",
            (mandant,)).fetchone()
    finally:
        c.close()
    assert zeile is not None, "die Freigabe wurde nicht geschrieben"
    assert zeile["erhebung_id"] == massgeblich
    assert zeile["benutzer_id"], "wer entschieden hat, kommt aus der Anmeldung"
    assert zeile["objekt_typ"] == "teilprozess" and zeile["gate"] == "bc0-bc2"


def test_widerruf_ueber_zweite_entscheidung(client, mandant):
    """Nichts wird überschrieben — der aktuelle Stand ist die jüngste Zeile."""
    tp = _tp(client, mandant)
    client.post("/api/companies/" + mandant + "/gate/" + tp, json={
        "ereignis": "zurueckgewiesen", "kette_bestaetigt": True,
        "grund": "Nachtrag aus BC1 widerspricht der Dauer",
        "massnahme": "Dauer im Interview erneut aufnehmen", "punkte": []})
    liste = client.get("/api/companies/" + mandant + "/gate").json()["teilprozesse"]
    assert [t for t in liste if t["sub_process_id"] == tp][0]["stand"] == "zurueckgewiesen"
    c = anwendung.db()
    try:
        n = c.execute("SELECT COUNT(*) AS n FROM gate_ereignisse WHERE " + anwendung.W_CO +
                      " AND objekt_id=?", (mandant, tp)).fetchone()["n"]
    finally:
        c.close()
    assert n >= 3, "die frueheren Entscheidungen bleiben stehen"


# --------------------------------------------------------------------------- #
def test_anfragen_werden_fortlaufend_nummeriert(client, mandant):
    vorher = client.get("/api/companies/" + mandant + "/anfragen").json()["anfragen"]
    neu = client.post("/api/companies/" + mandant + "/anfragen",
                      json={"originaltext": "Zweite Frage aus dem Fachbereich."}).json()
    nachher = client.get("/api/companies/" + mandant + "/anfragen").json()["anfragen"]
    assert len(nachher) == len(vorher) + 1
    assert neu["anfrage_id"].startswith("A-")
    nummern = sorted(int(a["anfrage_id"].split("-")[2]) for a in nachher)
    assert nummern == list(range(1, len(nachher) + 1))
    assert nachher[0]["originaltext"] == "Zweite Frage aus dem Fachbereich."


def test_anfrage_ohne_originaltext_scheitert(client, mandant):
    antwort = client.post("/api/companies/" + mandant + "/anfragen", json={"originaltext": "  "})
    assert antwort.status_code == 400


# --------------------------------------------------------------------------- #
def test_fremder_mandant_liefert_404(client, mandant):
    """Ein Admin darf alle Mandanten sehen — aber keine, die es nicht gibt.

    Ein normaler Benutzer kommt an diesen Endpunkten gar nicht erst vorbei; für
    ihn ist die Antwort 403, siehe oben.
    """
    fremd = "00000000-0000-0000-0000-000000000000" if anwendung.PG else "987654"
    assert client.get("/api/companies/" + fremd + "/gate").status_code == 404
    assert client.get("/api/companies/" + fremd + "/gate/KP-02.TP-1").status_code == 404
    assert client.post("/api/companies/" + fremd + "/gate/KP-02.TP-1",
                       json={"ereignis": "zurueckgewiesen", "grund": "x", "massnahme": "y",
                             "kette_bestaetigt": True, "punkte": []}).status_code == 404
    assert client.get("/api/companies/" + fremd + "/anfragen").status_code == 404
    assert client.post("/api/companies/" + fremd + "/anfragen",
                       json={"originaltext": "Frage"}).status_code == 404


def test_teilprozess_eines_fremden_mandanten_liefert_404(client, mandant):
    """Die Teilprozess-ID allein öffnet nichts — sie muss zum Mandanten gehören."""
    anderer = str(client.post("/api/companies",
                              json={"name": "Andere KG", "kps": [5]}).json()["id"])
    fremder_tp = _tp(client, anderer)
    assert client.get("/api/companies/" + mandant + "/gate/" + fremder_tp).status_code == 404


# --------------------------------------------------------------------------- #
# „Was ist jetzt zu tun?" — am_zug, Hindernisse, Sortierung
#
# Die Liste beantwortete bisher nur „was gibt es?". Fünfzig gleich aussehende
# Zeilen, alle „noch nicht entschieden", sagen niemandem, wo anzusetzen ist. Die
# folgenden Tests sichern die drei Aussagen, aus denen die Antwort besteht:
# der Zustand je Teilprozess, die *gruppierten* Hindernisse und die Reihenfolge.
# --------------------------------------------------------------------------- #
def _liste(client, cid):
    return client.get("/api/companies/" + cid + "/gate").json()


def _zeile(client, cid, sid):
    return [t for t in _liste(client, cid)["teilprozesse"] if t["sub_process_id"] == sid][0]


def _bewerte(client, cid, sid, n=30):
    items = {str(i): {"stufe": 4, "beleg": "Beleg %d" % i} for i in range(1, n + 1)}
    antwort = client.post("/api/companies/" + cid + "/rating", json={"key": sid, "items": items})
    assert antwort.status_code == 200, antwort.text


@pytest.fixture(scope="module")
def zustand_mandant(client) -> str:
    """Zwei Kernprozesse. KP-01 hat einen Eigner, aber *keinen* Ansprechpartner.

    Der eigene Mandant ist Absicht: Die Tests weiter oben verändern ihren Stand
    fortlaufend (Freigabe, Widerruf). Ein Zustandstest, der darauf aufsetzte,
    prüfte am Ende die Reihenfolge der Testdatei und nicht die Ableitung.
    """
    cid = str(client.post("/api/companies",
                          json={"name": "Am-Zug GmbH", "kps": [0, 1]}).json()["id"])
    kp = _erster_kp(client, cid)
    # Beide Personen gibt es von Anfang an — zugeordnet ist zunaechst nur der
    # Eigner. Sonst prueften die Tests unten das Anlegen mit und nicht die
    # Ableitung des Zustands.
    client.put("/api/companies/" + cid + "/entitaeten", json={
        "personen": [{"name": "Ida Eigner", "funktion": "Vertriebsleitung"},
                     {"name": "Ole Auskunft", "funktion": "Sachbearbeitung"}],
        "zuordnungen": []})
    personen = client.get("/api/companies/" + cid + "/entitaeten").json()["personen"]
    client.put("/api/companies/" + cid + "/entitaeten", json={"zuordnungen": [
        {"process_id": kp, "person_id": personen[0]["person_id"], "funktion": "eigner"}]})
    _bewerte(client, cid, kp + ".TP-1")
    _bewerte(client, cid, kp + ".TP-2")
    return cid


def test_am_zug_ohne_ansprechpartner_ist_bc0_pflege(client, zustand_mandant):
    """Eigner da, 30 Items bewertet — es fehlt allein der Ansprechpartner.

    Der Zustand muss `bc0_pflege` sein und nicht `wartet_bc1`: Was BC0 selbst
    nachtragen kann, steht vor dem, worauf BC0 nur warten kann.
    """
    kp = _erster_kp(client, zustand_mandant)
    zeile = _zeile(client, zustand_mandant, kp + ".TP-1")
    assert zeile["eigner_benannt"] and zeile["items_bewertet"] == 30
    assert zeile["ansprechpartner_benannt"] is False
    assert zeile["am_zug"] == "bc0_pflege"
    assert zeile["am_zug_grund"] == "Ansprechpartner fehlt"


def test_nach_dem_nachtragen_wartet_der_teilprozess_auf_bc1(client, zustand_mandant):
    """Sind die Vorbedingungen erfüllt, wandert der Zustand weiter — nicht auf
    `entscheiden`, denn die BC1-Angaben gibt es noch nicht."""
    kp = _erster_kp(client, zustand_mandant)
    personen = client.get("/api/companies/" + zustand_mandant + "/entitaeten").json()["personen"]
    client.put("/api/companies/" + zustand_mandant + "/entitaeten", json={"zuordnungen": [
        {"process_id": kp, "person_id": personen[0]["person_id"], "funktion": "eigner"},
        {"process_id": kp, "person_id": personen[1]["person_id"], "funktion": "mitwirkend"}]})
    zeile = _zeile(client, zustand_mandant, kp + ".TP-1")
    assert zeile["bogen_ausfuellbar"], "wartet_bc1 sperrt nichts — der Bogen bleibt offen"
    assert zeile["am_zug"] == "wartet_bc1"
    assert zeile["am_zug_grund"].startswith("Anreicherung fehlt:")


def test_nach_der_entscheidung_ist_der_teilprozess_entschieden(client, zustand_mandant):
    """Eine Freigabe ist trotz `wartet_bc1` möglich — der Zustand steuert nur die
    Einsortierung, nicht die Erlaubnis."""
    kp = _erster_kp(client, zustand_mandant)
    tp = kp + ".TP-1"
    antwort = client.post("/api/companies/" + zustand_mandant + "/gate/" + tp, json={
        "ereignis": "freigegeben", "kette_bestaetigt": True,
        "punkte": _punkte(guete_dauer="entfaellt")})
    assert antwort.status_code == 200, antwort.text
    zeile = _zeile(client, zustand_mandant, tp)
    assert zeile["am_zug"] == "entschieden"
    assert zeile["am_zug_grund"] == "Entschieden: freigegeben"


def test_hindernisse_sind_je_kernprozess_gruppiert(client):
    """Zehn Kernprozesse, nichts gepflegt: **zehn** Einträge je Art, nicht fünfzig.

    Eigner und Ansprechpartner hängen am Kernprozess und werden an seine fünf
    Teilprozesse vererbt. Je Teilprozess aufgeführt stünde derselbe Satz fünfzig
    Mal — eine Liste, die niemand liest.
    """
    cid = str(client.post("/api/companies",
                          json={"name": "Leer AG", "kps": list(range(10))}).json()["id"])
    daten = _liste(client, cid)
    assert len(daten["teilprozesse"]) == 50
    hindernisse = daten["hindernisse"]
    assert all(t["am_zug"] == "bc0_pflege" for t in daten["teilprozesse"])
    je_art = {}
    for h in hindernisse:
        je_art.setdefault(h["art"], []).append(h)
    assert sorted(je_art) == ["ansprechpartner", "bewertung", "eigner"]
    for art, eintraege in je_art.items():
        assert len(eintraege) == 10, "%s: je Kernprozess ein Eintrag, nicht je Teilprozess" % art
        assert {e["process_id"] for e in eintraege} == \
            {"KP-%02d" % n for n in range(1, 11)}
        assert all(e["betroffen"] == 5 for e in eintraege)
    assert len(hindernisse) == 30, "zehn Prozesse mal drei Arten — nicht 150"
    assert hindernisse[0]["process_id"] == "KP-01" and hindernisse[0]["art"] == "eigner"
    assert hindernisse[0]["process_name"], "der Name gehoert dazu, sonst ist die ID stumm"


def test_hindernisse_zaehlen_entschiedenes_nicht_mehr_mit(client, zustand_mandant):
    """Der freigegebene Teilprozess aus KP-01 taucht in den Hindernissen nicht auf.

    Er wartet auf nichts mehr; ein Nachtrag an ihm änderte die Entscheidung nicht.
    """
    kp = _erster_kp(client, zustand_mandant)
    daten = _liste(client, zustand_mandant)
    bewertung = [h for h in daten["hindernisse"]
                 if h["process_id"] == kp and h["art"] == "bewertung"]
    assert len(bewertung) == 1
    assert bewertung[0]["betroffen"] == 3, "TP-1 ist entschieden, TP-2 bewertet — bleiben drei"
    assert not [h for h in daten["hindernisse"]
                if h["process_id"] == kp and h["art"] in ("eigner", "ansprechpartner")]


def test_die_liste_ist_nach_am_zug_sortiert(client, zustand_mandant):
    """Was zu tun ist, steht oben: entscheiden, bc0_pflege, wartet_bc1,
    entschieden — und darin nach Teilprozess-ID."""
    zeilen = _liste(client, zustand_mandant)["teilprozesse"]
    ordnung = list(anwendung.GATE_AM_ZUG)
    assert ordnung == ["entscheiden", "bc0_pflege", "wartet_bc1", "entschieden"]
    schluessel = [(ordnung.index(z["am_zug"]), z["sub_process_id"]) for z in zeilen]
    assert schluessel == sorted(schluessel), "die Reihenfolge kommt aus dem Backend"
    zustaende = [z["am_zug"] for z in zeilen]
    assert zustaende[0] == "bc0_pflege", "entscheidungsreif ist derzeit nichts"
    assert zustaende[-1] == "entschieden"
    assert zustaende.count("wartet_bc1") == 1


def test_entscheiden_ist_ohne_bc1_nicht_erreichbar(client, zustand_mandant):
    """Solange `_bc1_angaben` nichts liefert, gibt es keinen entscheidungsreifen
    Teilprozess. Das ist der Projektstand, kein Mangel — und deshalb ein Test:
    Wird BC1 angeschlossen, muss diese Zusicherung bewusst fallen."""
    assert anwendung._bc1_angaben(None, zustand_mandant, "KP-01.TP-1") is None
    zeilen = _liste(client, zustand_mandant)["teilprozesse"]
    assert not [z for z in zeilen if z["am_zug"] == "entscheiden"]
