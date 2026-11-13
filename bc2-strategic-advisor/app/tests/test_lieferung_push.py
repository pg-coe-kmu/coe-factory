"""
Tests: die Lieferung ohne Handgriff (#388, entschieden in #383).

Eine GitHub Action zieht nach Zeitplan über einen eigenen, nur lesenden
Endpunkt (Nachtrag zu ADR-007 · BC2 §2.2 vom 13.11.2026). Geprüft wird hier
die Seite des Dienstes — Schlüssel, Filter, Form — und das Werkzeug mit der
Quelle ``--von-url`` gegen einen echten, lokal gestarteten Dienst. Der Workflow
selbst läuft nur auf GitHub.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import erzeuge_app
from eingang import SpeicherEingangsbuch
from laeufe import MesssatzLaufquelle
from test_lieferung import _echter_lauf, _ueber_ssh, ziehen

from conftest import MESSSAETZE

SCHLUESSEL = "liefer-schluessel-nicht-echt"
PFAD = "/api/lieferungen"


def _dienst(gate1):
    return erzeuge_app(SpeicherEingangsbuch(), laufquelle=MesssatzLaufquelle(MESSSAETZE),
                       gate1_buch=gate1)


@pytest.fixture
def geliefert():
    """Ein freigegebener, lieferbarer Lauf mit eingefrorener Akte."""
    _, gate1 = _echter_lauf()
    return gate1


def _hole(gate1, kopf: dict | None = None):
    with TestClient(_dienst(gate1)) as c:
        return c.get(PFAD, headers=kopf or {})


def _bearer(wert: str) -> dict:
    return {"Authorization": f"Bearer {wert}"}


# ---------------------------------------------------------------------------
# Der Endpunkt
# ---------------------------------------------------------------------------


def test_ohne_gesetzten_schluessel_gibt_es_den_endpunkt_nicht(geliefert, monkeypatch):
    """Abgeschaltet, nicht offen: ein leerer Schlüssel darf nie passen."""
    monkeypatch.delenv("BC2_LIEFERUNG_TOKEN", raising=False)
    assert _hole(geliefert, _bearer("")).status_code == 404


@pytest.mark.parametrize("kopf", [None, _bearer("falsch"), _bearer("test-schluessel-nicht-echt")])
def test_ohne_den_eigenen_schluessel_401(geliefert, monkeypatch, kopf):
    """Auch der Schlüssel der Oberfläche öffnet ihn nicht — und umgekehrt (#383, Punkt 1)."""
    monkeypatch.setenv("BC2_LIEFERUNG_TOKEN", SCHLUESSEL)
    assert _hole(geliefert, kopf).status_code == 401


def test_der_lieferschluessel_oeffnet_die_oberflaeche_nicht(geliefert, monkeypatch):
    monkeypatch.setenv("BC2_LIEFERUNG_TOKEN", SCHLUESSEL)
    with TestClient(_dienst(geliefert)) as c:
        assert c.get("/api/oberflaeche/laeufe", headers=_bearer(SCHLUESSEL)).status_code == 401


def test_der_endpunkt_liefert_was_python_m_lieferung_liefert(geliefert, monkeypatch):
    monkeypatch.setenv("BC2_LIEFERUNG_TOKEN", SCHLUESSEL)
    antwort = _hole(geliefert, _bearer(SCHLUESSEL))
    assert antwort.status_code == 200
    assert antwort.headers["cache-control"] == "no-store"
    assert antwort.json() == _ueber_ssh(geliefert)
    (l,) = antwort.json()["lieferungen"]
    assert sorted(d["name"] for d in l["dateien"]) == [
        "NACHRICHT_AN_BC3.md", "konzept_KP-06.json", "konzept_KP-07.json",
        "prozesspriorisierung.json",
    ]


@pytest.mark.parametrize("lauf", [
    dict(freigeben=None), dict(freigeben="rejected"), dict(sperrgrund="Nicht nachrechenbar."),
])
def test_nicht_lieferbares_steht_nicht_drin(monkeypatch, lauf):
    """Offen, abgelehnt oder mit Sperrgrund: keine Lieferung — und keine Präsentation."""
    monkeypatch.setenv("BC2_LIEFERUNG_TOKEN", SCHLUESSEL)
    _, gate1 = _echter_lauf(**lauf)
    assert _hole(gate1, _bearer(SCHLUESSEL)).json() == {"lieferungen": []}


def test_die_praesentation_geht_nicht_mit(geliefert, monkeypatch):
    """Sie ist Datei der Akte mit Empfänger ``mandant``, nicht Teil der Lieferung."""
    monkeypatch.setenv("BC2_LIEFERUNG_TOKEN", SCHLUESSEL)
    namen = [d["name"] for l in _hole(geliefert, _bearer(SCHLUESSEL)).json()["lieferungen"]
             for d in l["dateien"]]
    assert not [n for n in namen if n.endswith(".pptx")]


# ---------------------------------------------------------------------------
# Das Werkzeug mit --von-url, gegen einen laufenden Dienst
# ---------------------------------------------------------------------------


def _freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _laufend(anwendung):
    import uvicorn

    port = _freier_port()
    server = uvicorn.Server(uvicorn.Config(anwendung, host="127.0.0.1", port=port,
                                           log_level="warning"))
    faden = threading.Thread(target=server.run, daemon=True)
    faden.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "Der Dienst ist nicht angelaufen."
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        faden.join(timeout=5)


def test_von_url_schreibt_ab_und_ein_zweiter_zug_aendert_nichts(geliefert, monkeypatch, tmp_path,
                                                                capsys):
    monkeypatch.setenv("BC2_LIEFERUNG_TOKEN", SCHLUESSEL)
    with _laufend(_dienst(geliefert)) as basis:
        assert ziehen.main(["--von-url", basis, "--ziel", str(tmp_path)]) == 0
        assert "neu  noroai-PKT-301-f1" in capsys.readouterr().out
        assert (tmp_path / "noroai-PKT-301-f1" / "prozesspriorisierung.json").exists()

        assert ziehen.main(["--von-url", basis, "--ziel", str(tmp_path)]) == 0
        assert "Nichts Neues." in capsys.readouterr().out


def test_von_url_mit_falschem_schluessel_bricht_ab_ohne_zu_schreiben(geliefert, monkeypatch,
                                                                     tmp_path, capsys):
    # Dienst und Werkzeug teilen hier einen Prozess und damit die Umgebung: der
    # Dienst behält seinen Schlüssel, das Werkzeug schickt einen anderen.
    import lieferung
    monkeypatch.setattr(lieferung, "_lieferschluessel", lambda: SCHLUESSEL)
    monkeypatch.setenv("BC2_LIEFERUNG_TOKEN", "falsch")
    with _laufend(_dienst(geliefert)) as basis:
        assert ziehen.main(["--von-url", basis, "--ziel", str(tmp_path)]) == 1
    assert "401" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_von_url_ohne_schluessel_in_der_umgebung_bricht_ab(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("BC2_LIEFERUNG_TOKEN", raising=False)
    assert ziehen.main(["--von-url", "http://127.0.0.1:9", "--ziel", str(tmp_path)]) == 1
    assert "BC2_LIEFERUNG_TOKEN" in capsys.readouterr().err
