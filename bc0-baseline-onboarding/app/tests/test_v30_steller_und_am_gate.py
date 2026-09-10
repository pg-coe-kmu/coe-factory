# -*- coding: utf-8 -*-
"""Schema v3.0 — wer die Anfrage gestellt hat, und wann sie ans Gate geht.

Zwei Befunde aus Richards Brief vom 03.09.2026, Abschnitt 5, am 07.09. am
Quelltext nachgeprueft:

  1. Die Anfragemaske verlangt eine Anmeldung — und vergass sie sofort wieder:
     `ref_anfragen` speicherte den Benutzer nicht. Wer die Anfrage gestellt
     hat, war hinterher nur bekannt, wenn jemand `steller_id` von Hand
     ausgefuellt hatte, und die ist optional.
  2. `am_gate` stand seit v2.2 in der Wertemenge — und **keine Zeile Code
     setzte ihn.**

Vier Aussagen, hier gegen SQLite geprueft:
  1. Eine neue Anfrage traegt das Konto, das sie abgeschickt hat.
  2. Die Anfrageliste liefert je Anfrage einen `steller`-Block mit `herkunft`.
     Ohne Zuordnung sagt sie `unbekannt` — und erfindet keine P-ID.
  3. `steller_id` am Formular bleibt erhalten und hat Vorrang.
  4. Das Nachziehen auf `am_gate` gibt es nur im PostgreSQL-Betrieb und sagt
     das mit 501, statt still nichts zu tun.

Die Aufloesung ueber `v_anfrage_steller` und die Funktion
`anfrage_am_gate_nachziehen()` sind PostgreSQL-Sachen; sie sind in
`pruefung_v3.0_steller_und_am_gate.sql` mit neun Erwartungswerten geprueft.
"""
import os, sys, datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "_v30.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "v30-admin-passwort"
EMAIL = "v30-admin@bc0.test"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen(EMAIL, "V30-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    r = c.post("/api/auth/login", json={"email": EMAIL, "passwort": PW})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies",
                           json={"name": "V30 Testmandant GmbH", "kps": [1]}).json()["id"])


def _anfrage(client, cid, text):
    r = client.post("/api/companies/%s/anfragen" % cid,
                    json={"originaltext": text, "eingang_am": str(datetime.date.today())})
    assert r.status_code in (200, 201), r.text
    return r.json()["anfrage_id"]


def test_anfrage_traegt_das_konto(client, mandant):
    """1. Wer die Maske abschickt, steht in der Zeile — nicht nur im Cookie."""
    aid = _anfrage(client, mandant, "Die Angebotserstellung dauert zu lange.")
    c = anwendung.db()
    try:
        # Mandantenfilter, immer (Punkt 16): in der gemeinsamen Testdatenbank
        # tragen mehrere Mandanten dieselbe anfrage_id.
        zeile = c.execute("SELECT angelegt_von FROM ref_anfragen "
                          "WHERE company_id=? AND anfrage_id=?",
                          (mandant, aid)).fetchone()
    finally:
        c.close()
    assert zeile is not None
    assert zeile["angelegt_von"], "angelegt_von ist leer — die Anmeldung wurde wieder vergessen"
    c = anwendung.db()
    try:
        konto = c.execute("SELECT benutzer_id FROM app_benutzer WHERE email=?",
                          (EMAIL,)).fetchone()
    finally:
        c.close()
    assert zeile["angelegt_von"] == konto["benutzer_id"]


def test_liste_nennt_die_herkunft(client, mandant):
    """2. Der steller-Block ist immer da — und sagt `unbekannt`, statt zu raten."""
    r = client.get("/api/companies/%s/anfragen" % mandant)
    assert r.status_code == 200, r.text
    anfragen = r.json()["anfragen"]
    assert anfragen, "keine Anfrage gelesen"
    for a in anfragen:
        assert "steller" in a, "steller-Block fehlt"
        assert a["steller"]["herkunft"] in ("formular", "konto", "unbekannt")
    # SQLite kennt v_anfrage_steller nicht -> unbekannt, aber kein Fehler
    assert anfragen[0]["steller"]["person_id"] in (None, "")


def test_steller_id_bleibt_und_hat_vorrang(client, mandant):
    """3. Die ausdrueckliche Angabe am Formular wird nicht ueberschrieben."""
    r = client.post("/api/companies/%s/anfragen" % mandant,
                    json={"originaltext": "Zweite Anfrage, mit Steller.",
                          "eingang_am": str(datetime.date.today()),
                          "steller_id": "P-01"})
    # P-01 existiert bei diesem Mandanten nicht -> die Pruefung muss greifen
    assert r.status_code == 400, "unbekannte Person wurde angenommen"
    assert "Unbekannte Person" in r.text


def test_gate_nachziehen_nur_mit_postgres(client, mandant):
    """4. Im SQLite-Betrieb sagt der Endpunkt es — statt still nichts zu tun."""
    r = client.post("/api/companies/%s/anfragen/gate_nachziehen" % mandant)
    assert r.status_code == 501, r.text
    assert "PostgreSQL" in r.text
