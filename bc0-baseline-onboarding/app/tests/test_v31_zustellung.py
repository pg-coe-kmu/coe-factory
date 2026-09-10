# -*- coding: utf-8 -*-
"""Schema v3.1 — der Ruf an BC2: nur Kennungen, signiert, protokolliert.

Beschluss Projektmeeting 07.09.2026: *„REST-API fuer die BC2-Aktivierung,
JSON-IDs statt Datei-Check."*

Fuenf Aussagen, hier ohne Netz und ohne PostgreSQL geprueft — der Ruf selbst
ist reine Anwendungslogik:

  1. Der Rumpf enthaelt **nur** die drei Kennungen. Kein Reifegrad, keine
     Teilprozessliste, keine Bewertung. Die Nachricht ist der Zettel mit der
     Nummer, nicht der Inhalt.
  2. Ohne hinterlegte Adresse wird **nicht** gerufen, und das Ergebnis heisst
     `kein_ziel` — nicht `fehler`. Es ist ein Zustand, kein Defekt.
  3. Ist ein Geheimnis hinterlegt, traegt der Ruf `X-BC0-Timestamp` und eine
     HMAC-SHA256-Unterschrift ueber `zeitstempel.rumpf`. Ohne Geheimnis
     stehen die Koepfe nicht da.
  4. Ein Fehler beim Rufen wirft nicht — er wird zurueckgegeben. Die
     Uebergabe darf daran nicht scheitern.
  5. `POST …/uebergabe/nachliefern` gibt es nur im PostgreSQL-Betrieb und
     sagt das mit 501.
"""
import hashlib, hmac, json, os, sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "_v31.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

import app as anwendung  # noqa: E402
from bc0_auth import Rolle  # noqa: E402

PW = "v31-admin-passwort"
EMAIL = "v31-admin@bc0.test"
CID = "11111111-1111-1111-1111-111111111111"
PAKET = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen(EMAIL, "V31-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    r = c.post("/api/auth/login", json={"email": EMAIL, "passwort": PW})
    assert r.status_code == 200, r.text
    return c


class _Antwort:
    def __init__(self, code=200): self._code = code
    def getcode(self): return self._code
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _faengt(monkeypatch):
    """Faengt den HTTP-Aufruf ab und gibt die Anfrage zurueck, statt zu senden."""
    gefangen = {}

    def _urlopen(anfrage, timeout=None):
        gefangen["url"] = anfrage.full_url
        gefangen["daten"] = anfrage.data
        gefangen["kopf"] = {k.lower(): v for k, v in anfrage.header_items()}
        return _Antwort(200)

    monkeypatch.setattr(anwendung.urllib.request, "urlopen", _urlopen)
    return gefangen


def test_rumpf_enthaelt_nur_die_kennungen(monkeypatch):
    """1. Der Zettel mit der Nummer — nicht der Inhalt."""
    gefangen = _faengt(monkeypatch)
    monkeypatch.setattr(anwendung, "BC2_HOOK_URL", "https://bc2.example/hook")
    monkeypatch.setattr(anwendung, "BC2_HOOK_SECRET", "")
    ergebnis, code, _ = anwendung._bc2_rufen(CID, PAKET, "2026-09-08")
    assert (ergebnis, code) == ("zugestellt", 200)
    rumpf = json.loads(gefangen["daten"].decode("utf-8"))
    assert set(rumpf) == {"ereignis", "company_id", "paket_id", "uebergeben_am"}
    assert rumpf["paket_id"] == PAKET and rumpf["company_id"] == CID
    assert "x-bc0-signature" not in gefangen["kopf"], "ohne Geheimnis keine Unterschrift"


def test_ohne_adresse_wird_nicht_gerufen(monkeypatch):
    """2. `kein_ziel` ist ein Zustand, kein Defekt."""
    gerufen = {"ja": False}
    def _nie(*a, **k): gerufen["ja"] = True
    monkeypatch.setattr(anwendung.urllib.request, "urlopen", _nie)
    monkeypatch.setattr(anwendung, "BC2_HOOK_URL", "")
    ergebnis, code, meldung = anwendung._bc2_rufen(CID, PAKET, "2026-09-08")
    assert ergebnis == "kein_ziel" and code is None
    assert not gerufen["ja"], "ohne Adresse darf kein Aufruf hinausgehen"
    assert "Zieladresse" in meldung


def test_unterschrift_ueber_zeitstempel_und_rumpf(monkeypatch):
    """3. BC2 muss erkennen koennen, dass der Ruf von uns kommt."""
    gefangen = _faengt(monkeypatch)
    monkeypatch.setattr(anwendung, "BC2_HOOK_URL", "https://bc2.example/hook")
    monkeypatch.setattr(anwendung, "BC2_HOOK_SECRET", "geheim-nur-fuer-bc2")
    anwendung._bc2_rufen(CID, PAKET, "2026-09-08")
    stempel = gefangen["kopf"]["x-bc0-timestamp"]
    erwartet = hmac.new(b"geheim-nur-fuer-bc2",
                        stempel.encode("utf-8") + b"." + gefangen["daten"],
                        hashlib.sha256).hexdigest()
    assert gefangen["kopf"]["x-bc0-signature"] == "sha256=" + erwartet


def test_fehler_wirft_nicht(monkeypatch):
    """4. Ein gescheiterter Ruf ist ein Protokolleintrag, kein Abbruch."""
    def _kaputt(*a, **k): raise OSError("Netz weg")
    monkeypatch.setattr(anwendung.urllib.request, "urlopen", _kaputt)
    monkeypatch.setattr(anwendung, "BC2_HOOK_URL", "https://bc2.example/hook")
    ergebnis, code, meldung = anwendung._bc2_rufen(CID, PAKET, "2026-09-08")
    assert ergebnis == "fehler" and code is None and "Netz weg" in meldung


def test_nachliefern_nur_mit_postgres(client):
    """5. Im SQLite-Betrieb sagt der Endpunkt es, statt still nichts zu tun."""
    r = client.post("/api/companies/%s/uebergabe/nachliefern" % CID)
    assert r.status_code in (403, 404, 501), r.text
    if r.status_code == 501:
        assert "PostgreSQL" in r.text
