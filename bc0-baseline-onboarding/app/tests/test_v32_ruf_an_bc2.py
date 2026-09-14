# -*- coding: utf-8 -*-
"""Patch v3.2 — zwei Befunde aus BC2s Betrieb am 10.09.2026, an unserem Code.

Der Ruf selbst bleibt unveraendert: HMAC-Signatur, nur die Kennungen im Rumpf.
BC2 hat sich an unsere Form angeglichen (#190) und empfiehlt, sie zu behalten.
Geprueft wird deshalb nur, was v3.2 aendert — und ausdruecklich auch, dass der
Rest gleich geblieben ist:

  1. `_rfc3339()` macht aus PostgreSQLs Textform einen RFC-3339-Zeitstempel:
     `T` statt Leerzeichen, `+02:00` statt `+02`.
  2. Ohne Zeitpunkt wird **nicht** gerufen; frueher ging `"None"` hinaus.
  3. Der Rumpf traegt weiterhin genau vier Felder, die Signatur steht weiterhin
     dran — die Zusagen aus v3.1 gelten unveraendert.
"""
import hashlib, hmac, json, os, sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "_v32.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

import app as anwendung  # noqa: E402

CID = "11111111-1111-1111-1111-111111111111"
PAKET = "22222222-2222-2222-2222-222222222222"
URL = "https://bc2.example/api/bc0/uebergabe"


class _Antwort:
    def __init__(self, code=202): self._code = code
    def getcode(self): return self._code
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _faengt(monkeypatch):
    gefangen = {}

    def _urlopen(anfrage, timeout=None):
        gefangen["url"] = anfrage.full_url
        gefangen["daten"] = anfrage.data
        gefangen["kopf"] = {k.lower(): v for k, v in anfrage.header_items()}
        return _Antwort(202)

    monkeypatch.setattr(anwendung.urllib.request, "urlopen", _urlopen)
    return gefangen


@pytest.mark.parametrize("roh,erwartet", [
    # So schreibt PostgreSQL es wirklich — das ist der Fall aus dem Betrieb.
    ("2026-09-10 14:32:11.123456+02", "2026-09-10T14:32:11.123456+02:00"),
    ("2026-09-10 14:32:11+02",        "2026-09-10T14:32:11+02:00"),
    ("2026-09-10 12:32:11+0000",      "2026-09-10T12:32:11+00:00"),
    # Schon richtig: unveraendert durchreichen, nichts doppelt anfassen.
    ("2026-09-10T14:32:11+02:00",     "2026-09-10T14:32:11+02:00"),
    ("2026-09-10T12:32:11Z",          "2026-09-10T12:32:11Z"),
    # Ohne Zone: keine erfinden.
    ("2026-09-10 14:32:11",           "2026-09-10T14:32:11"),
])
def test_zeitstempel_wird_rfc3339(roh, erwartet):
    """1. `T` statt Leerzeichen, `+02:00` statt `+02`."""
    assert anwendung._rfc3339(roh) == erwartet


@pytest.mark.parametrize("roh", [None, "", "   ", "None"])
def test_kein_zeitpunkt_ist_kein_zeitpunkt(roh):
    """1b. Auch die Zeichenkette `"None"` gilt als fehlend — sie war der Fehler."""
    assert anwendung._rfc3339(roh) is None


def test_unlesbares_wird_durchgereicht():
    """1c. Was wir nicht erkennen, verfaelschen wir nicht."""
    assert anwendung._rfc3339("irgendwann") == "irgendwann"


def test_ohne_zeitpunkt_wird_nicht_gerufen(monkeypatch):
    """2. Frueher ging `"None"` hinaus und BC2 antwortete 400."""
    gefangen = _faengt(monkeypatch)
    monkeypatch.setattr(anwendung, "BC2_HOOK_URL", URL)
    ergebnis, code, meldung = anwendung._bc2_rufen(CID, PAKET, None)
    assert (ergebnis, code) == ("fehler", None)
    assert "uebergeben_am" in meldung
    assert not gefangen, "es darf kein Aufruf hinausgehen"


def test_rumpf_traegt_den_normalisierten_stempel(monkeypatch):
    """2b. Im Rumpf steht die RFC-3339-Form, nicht die von PostgreSQL."""
    gefangen = _faengt(monkeypatch)
    monkeypatch.setattr(anwendung, "BC2_HOOK_URL", URL)
    monkeypatch.setattr(anwendung, "BC2_HOOK_SECRET", "")
    ergebnis, code, _ = anwendung._bc2_rufen(CID, PAKET, "2026-09-14 08:15:00.5+02")
    assert (ergebnis, code) == ("zugestellt", 202)
    rumpf = json.loads(gefangen["daten"].decode("utf-8"))
    assert rumpf["uebergeben_am"] == "2026-09-14T08:15:00.5+02:00"


def test_form_des_rufs_ist_unveraendert(monkeypatch):
    """3. Die Zusagen aus v3.1 gelten weiter — vier Felder, HMAC-Signatur.

    Dieser Test ist die Gegenprobe zum Entwurf, der am 11.09. verworfen wurde:
    kein Bearer, kein `teilprozesse[]`, kein geaenderter Feldsatz.
    """
    gefangen = _faengt(monkeypatch)
    monkeypatch.setattr(anwendung, "BC2_HOOK_URL", URL)
    monkeypatch.setattr(anwendung, "BC2_HOOK_SECRET", "geheim-nur-fuer-bc2")
    anwendung._bc2_rufen(CID, PAKET, "2026-09-14 08:15:00+02")
    rumpf = json.loads(gefangen["daten"].decode("utf-8"))
    assert set(rumpf) == {"ereignis", "company_id", "paket_id", "uebergeben_am"}
    assert "authorization" not in gefangen["kopf"], "kein Bearer — das war der Irrweg"
    stempel = gefangen["kopf"]["x-bc0-timestamp"]
    erwartet = hmac.new(b"geheim-nur-fuer-bc2",
                        stempel.encode("utf-8") + b"." + gefangen["daten"],
                        hashlib.sha256).hexdigest()
    assert gefangen["kopf"]["x-bc0-signature"] == "sha256=" + erwartet
