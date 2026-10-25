# -*- coding: utf-8 -*-
"""v3.20 — Gate 0 liest das BC1-Profil der gewaehlten Anfrage (25.10.2026).

Rueckfrage BC1 (Richard, 25.10.), Punkt 3: ``_bc1_anreicherung`` und
``gate_entscheiden`` nahmen die juengste fertige Fassung JE TEILPROZESS. Liegen
zwei Anfragen auf demselben Teilprozess, trug die Freigabe die falsche Fassung.
Dazu die lesbare Meldung zur Platzhalter-Sperre (v3.19b).
"""
import pytest
from fastapi import HTTPException

import app as A


def _p(version, anfrage):
    return {"focus_step_id": "KP-05.TP-1", "profil_version": version, "anfrage_id": anfrage}


PROFILE = [_p(5, "A-2026-07"), _p(3, "A-2026-05"), _p(1, None)]   # juengste zuerst


def test_ohne_filter_gilt_die_juengste():
    assert A._bc1_profil_waehlen(PROFILE)["profil_version"] == 5


def test_ohne_anfrage_gilt_die_juengste():
    assert A._bc1_profil_waehlen(PROFILE, None)["profil_version"] == 5


def test_mit_anfrage_gilt_ihre_fassung():
    assert A._bc1_profil_waehlen(PROFILE, "A-2026-05")["profil_version"] == 3
    assert A._bc1_profil_waehlen(PROFILE, "A-2026-07")["profil_version"] == 5


def test_anfrage_ohne_eigenes_profil_nimmt_nur_eines_ohne_anfrage():
    assert A._bc1_profil_waehlen(PROFILE, "A-2026-02")["profil_version"] == 1


def test_nie_das_profil_einer_anderen_anfrage():
    nur_fremde = [_p(5, "A-2026-07"), _p(3, "A-2026-05")]
    assert A._bc1_profil_waehlen(nur_fremde, "A-2026-02") is None


def test_juengste_fassung_der_anfrage():
    zwei = [_p(4, "A-2026-05"), _p(3, "A-2026-05")]
    assert A._bc1_profil_waehlen(zwei, "A-2026-05")["profil_version"] == 4


def test_leer():
    assert A._bc1_profil_waehlen([], "A-2026-05") is None


@pytest.mark.parametrize("name", ["", "  ", None, "Teilprozess 3", "teilprozess  12", " Teilprozess 1 "])
def test_platzhalter_erkannt(name):
    assert A._tp_unbenannt(name)


@pytest.mark.parametrize("name", ["Reisekosten", "Teilprozess Einkauf", "Teilprozess 3a", "TP 3"])
def test_echte_namen(name):
    assert not A._tp_unbenannt(name)


class _C:
    def __init__(self, name):
        self.name = name

    def execute(self, sql, args):
        class R:
            def __init__(s, n):
                s.n = n

            def fetchone(s):
                return None if s.n is False else {"sub_process_name": s.n}
        return R(self.name)


def test_meldung_bei_platzhalter():
    with pytest.raises(HTTPException) as e:
        A._tp_benannt_pruefen(_C("Teilprozess 2"), "cid", "KP-05.TP-2")
    assert e.value.status_code == 400
    assert "noch nicht benannt" in e.value.detail and "KP-05.TP-2" in e.value.detail


def test_keine_meldung_bei_namen_ohne_tp_oder_unbekannt():
    A._tp_benannt_pruefen(_C("Reisekosten"), "cid", "KP-05.TP-1")
    A._tp_benannt_pruefen(_C("Teilprozess 2"), "cid", None)
    A._tp_benannt_pruefen(_C(False), "cid", "KP-09.TP-9")   # unbekannt: meldet die Pruefung davor


# --- Ueber die Schnittstelle --------------------------------------------------
from fastapi.testclient import TestClient   # noqa: E402
from bc0_auth import Rolle                  # noqa: E402

PW = "v320-admin-passwort"


@pytest.fixture(scope="module")
def client():
    A.AUTH.benutzer_anlegen("v320-admin@bc0.test", "V320-Admin", PW, Rolle.ADMIN)
    c = TestClient(A.app)
    c.post("/api/auth/login", json={"email": "v320-admin@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client):
    return str(client.post("/api/companies", json={"name": "Platzhalter GmbH", "kps": [0]}).json()["id"])


def test_api_platzhalter_wird_lesbar_abgewiesen(client, mandant):
    r = client.post("/api/companies/%s/anfragen" % mandant, json={
        "originaltext": "Platzhalter.", "process_id": "KP-01", "sub_process_id": "KP-01.TP-1"})
    assert r.status_code == 400
    assert "noch nicht benannt" in r.json()["detail"]


def test_api_kernprozess_ohne_teilprozess_geht(client, mandant):
    r = client.post("/api/companies/%s/anfragen" % mandant, json={
        "originaltext": "Ganzer Kernprozess.", "process_id": "KP-01"})
    assert r.status_code == 200, r.text


def test_api_nach_benennen_geht(client, mandant):
    c = A.db()
    c.execute("UPDATE ref_teilprozesse SET sub_process_name='Reisebuchung' "
              "WHERE company_id=? AND sub_process_id='KP-01.TP-1'", (mandant,))
    c.commit()
    c.close()
    r = client.post("/api/companies/%s/anfragen" % mandant, json={
        "originaltext": "Benannt.", "process_id": "KP-01", "sub_process_id": "KP-01.TP-1"})
    assert r.status_code == 200, r.text


def test_api_bogen_nennt_gewaehlte_anfrage(client, mandant):
    r = client.get("/api/companies/%s/gate/KP-01.TP-1?anfrage_id=A-2026-01" % mandant)
    assert r.status_code == 200, r.text
    assert r.json()["anfrage_gewaehlt"] == "A-2026-01"
    r = client.get("/api/companies/%s/gate/KP-01.TP-1" % mandant)
    assert r.json()["anfrage_gewaehlt"] is None


# --- v3.20.1: Pruefpunkt "Rollen mit Zeitanteil" abgeschaltet ----------------

def _profil_ohne_rollen():
    return {"focus_step_duration_minutes": 90.0, "frequency_per_year": 12.0,
            "executions_per_run": 1.0, "rollen_anzahl": 0}


def test_abgeschalteter_pruefpunkt_fehlt_nicht():
    aktive = {"dauer", "haeufigkeit", "menge", "kosten"}
    assert A._bc1_fehlende_angaben(_profil_ohne_rollen(), aktive) == []


def test_ohne_katalog_zaehlen_alle_vier():
    assert A._bc1_fehlende_angaben(_profil_ohne_rollen()) == ["Rollen mit Zeitanteil"]


def test_aktiver_pruefpunkt_wird_weiter_verlangt():
    z = _profil_ohne_rollen(); z["executions_per_run"] = None
    assert A._bc1_fehlende_angaben(z, {"dauer", "haeufigkeit", "menge"}) == ["Menge"]


def test_wortlaut_anderes_profil():
    g = A._gate_veraltet_grund({"stand": "freigegeben", "bc1_profil_stand": "3"},
                               {"profil_version": 2}, None)
    assert g.startswith("anderes BC1-Profil (Fassung 2)")
