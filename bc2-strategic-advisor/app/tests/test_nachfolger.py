"""Tests für die Kette über Pakete hinweg (Vertrag v3.1, #291, ADR-009 · BC2).

Zwei Dinge:

1. **Die Vertragsform** — gegen die echten Schemadateien, nicht gegen einen Nachbau:
   `ersetzt_potenzial_ids` an jedem Potenzial einer 3.1 und an keinem einer 3.0,
   höchstens ein Eintrag; `gestrichene_potenziale` in der Priorisierung genau bei 3.1.
2. **Die Kettenregel** aus `tools/kette.py`, die `validate.py` auf jede Lieferung anwendet:
   1:1, Vorgänger und Gestrichenes nur aus früheren freigegebenen Lieferungen, gleicher
   Kernprozess, gleiche Lösungsklasse.
"""

from __future__ import annotations

import copy
import json
import sys
import uuid
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[3]
VERTRAEGE = WURZEL / "contracts" / "bc2-to-bc3"
BEISPIELE = WURZEL / "contracts" / "examples"
sys.path.insert(0, str(WURZEL / "bc2-strategic-advisor" / "tools"))

from kette import gelieferte_potenziale, kettenbefunde  # noqa: E402


def _lies(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def _fehler(schema_datei: str, daten: dict) -> list:
    jsonschema = pytest.importorskip("jsonschema")
    v = jsonschema.Draft202012Validator(_lies(VERTRAEGE / schema_datei))
    return list(v.iter_errors(daten))


def _konzept_31() -> dict:
    return _lies(BEISPIELE / "mock_automatisierungskonzept_KP-05.json")


def _prio_31() -> dict:
    return _lies(BEISPIELE / "mock_prozesspriorisierung.json")


# --- 1. Vertragsform ---------------------------------------------------------


def test_die_fixtures_sind_v3_1_und_tragen_eine_leere_kette():
    k, p = _konzept_31(), _prio_31()
    assert k["schema_version"] == p["schema_version"] == "3.1"
    assert all(pot["ersetzt_potenzial_ids"] == [] for pot in k["potenziale"])
    assert p["gestrichene_potenziale"] == []
    assert not _fehler("konzept.schema.json", k)
    assert not _fehler("priorisierung.schema.json", p)


def test_ein_potenzial_einer_v3_1_ohne_vorgaengerfeld_ist_ungueltig():
    """Pflicht ab 3.1 — sonst hieße ein fehlendes Feld „neu“ oder „nicht gebaut“, ununterscheidbar."""
    k = _konzept_31()
    del k["potenziale"][0]["ersetzt_potenzial_ids"]
    assert _fehler("konzept.schema.json", k)


def test_ein_vorgaengerfeld_in_einer_v3_0_ist_ungueltig():
    k = _konzept_31()
    k["schema_version"] = "3.0"
    assert _fehler("konzept.schema.json", k)
    for pot in k["potenziale"]:
        del pot["ersetzt_potenzial_ids"]
    assert not _fehler("konzept.schema.json", k)


def test_mehr_als_ein_vorgaenger_ist_ungueltig():
    """Nur 1:1 (ADR-009 · BC2 §2.4) — die Liste ist Form, nicht Erlaubnis."""
    k = _konzept_31()
    k["potenziale"][0]["ersetzt_potenzial_ids"] = [str(uuid.uuid4()), str(uuid.uuid4())]
    assert _fehler("konzept.schema.json", k)


def test_die_streichliste_ist_pflicht_genau_bei_v3_1():
    p = _prio_31()
    del p["gestrichene_potenziale"]
    assert _fehler("priorisierung.schema.json", p)

    p = _prio_31()
    p["schema_version"] = "3.0"
    del p["ausgangslage"]
    assert _fehler("priorisierung.schema.json", p)
    del p["gestrichene_potenziale"]
    assert not _fehler("priorisierung.schema.json", p)


def test_ein_gestrichenes_potenzial_braucht_eine_begruendung():
    p = _prio_31()
    p["gestrichene_potenziale"] = [{"potenzial_id": str(uuid.uuid4()), "kp_id": "KP-05"}]
    assert _fehler("priorisierung.schema.json", p)
    p["gestrichene_potenziale"][0]["begruendung"] = "Die Nacherhebung zeigt: der Medienbruch ist behoben."
    assert not _fehler("priorisierung.schema.json", p)


def test_die_uebergebene_simulierte_lieferung_bleibt_gueltig():
    """3.0 bleibt 3.0 — eine übergebene Lieferung wird nicht nachgezogen (ADR-007 · BC2 §2.4)."""
    ordner = VERTRAEGE / "lieferungen" / "noroai-SIM-UC3-2026-09-21-f1"
    for datei in ordner.glob("konzept_*.json"):
        assert not _fehler("konzept.schema.json", _lies(datei))
    assert not _fehler("priorisierung.schema.json", _lies(ordner / "prozesspriorisierung.json"))


# --- 2. Kettenregel ------------------------------------------------------------


def _lauf(paket_id: str, status: str = "approved"):
    """Ein Lauf aus der KP-05-Fixture, mit eigenen Kennungen und eigenem Paket."""
    k = copy.deepcopy(_konzept_31())
    k["paket_id"] = paket_id
    for pot in k["potenziale"]:
        pot["potenzial_id"] = str(uuid.uuid4())
    p = copy.deepcopy(_prio_31())
    p["paket_id"] = paket_id
    p["gate1"]["status"] = status
    return k, p


@pytest.fixture()
def frueher():
    """Ein freigegebener Lauf aus einem früheren Paket, der schon bei BC3 liegt."""
    return _lauf("PAKET-ALT")


@pytest.fixture()
def neu():
    return _lauf("PAKET-NEU", status="pending")


def _befunde(neu, *gelieferte):
    k, p = neu
    return kettenbefunde([k], p, gelieferte_potenziale([([g[0]], g[1]) for g in gelieferte]))


def test_ein_nachfolger_aus_einem_frueheren_paket_haelt(frueher, neu):
    alt = frueher[0]["potenziale"][0]
    neu[0]["potenziale"][0]["ersetzt_potenzial_ids"] = [alt["potenzial_id"]]
    assert _befunde(neu, frueher) == []


def test_ein_vorgaenger_aus_einem_abgelehnten_lauf_zaehlt_nicht(neu):
    """BC3 hat eine abgelehnte Fassung nie gesehen (ADR-009 · BC2 §2.2)."""
    abgelehnt = _lauf("PAKET-ALT", status="rejected")
    neu[0]["potenziale"][0]["ersetzt_potenzial_ids"] = [abgelehnt[0]["potenziale"][0]["potenzial_id"]]
    assert any("keiner freigegebenen" in b for b in _befunde(neu, abgelehnt))


def test_zwei_nachfolger_fuer_einen_vorgaenger_sind_ein_verstoss(frueher, neu):
    """Eine Teilung führte bei BC3 zweimal auf dieselbe älteste Kennung."""
    if len(neu[0]["potenziale"]) < 2:
        neu[0]["potenziale"].append(copy.deepcopy(neu[0]["potenziale"][0]))
        neu[0]["potenziale"][1]["potenzial_id"] = str(uuid.uuid4())
    alt = frueher[0]["potenziale"][0]["potenzial_id"]
    neu[0]["potenziale"][0]["ersetzt_potenzial_ids"] = [alt]
    neu[0]["potenziale"][1]["ersetzt_potenzial_ids"] = [alt]
    assert any("zwei Nachfolger" in b for b in _befunde(neu, frueher))


def test_eine_andere_loesungsklasse_ist_kein_nachfolger(frueher, neu):
    """Ändert sich die Lösung, ist es ein neues Potenzial (ADR-009 · BC2 §2.1)."""
    alt = frueher[0]["potenziale"][0]
    andere = "Assistenz" if alt["automatisierungsgrad"]["klasse"] != "Assistenz" else "Integration"
    neu[0]["potenziale"][0]["automatisierungsgrad"]["klasse"] = andere
    neu[0]["potenziale"][0]["ersetzt_potenzial_ids"] = [alt["potenzial_id"]]
    assert any("Loesungsklasse" in b for b in _befunde(neu, frueher))


def test_ein_vorgaenger_aus_demselben_paket_ist_ein_verstoss(neu):
    """Innerhalb eines Pakets verkettet ersetzt_konzept_id (ADR-008 · BC2 §2.1)."""
    gleiches = _lauf("PAKET-NEU")
    neu[0]["potenziale"][0]["ersetzt_potenzial_ids"] = [gleiches[0]["potenziale"][0]["potenzial_id"]]
    assert any("demselben Paket" in b for b in _befunde(neu, gleiches))


def test_gestrichen_und_fortgeschrieben_zugleich_ist_ein_verstoss(frueher, neu):
    alt = frueher[0]["potenziale"][0]["potenzial_id"]
    neu[0]["potenziale"][0]["ersetzt_potenzial_ids"] = [alt]
    neu[1]["gestrichene_potenziale"] = [
        {"potenzial_id": alt, "kp_id": "KP-05", "begruendung": "fällt nach der Nacherhebung weg"}
    ]
    assert any("zugleich fortgeschrieben" in b for b in _befunde(neu, frueher))


def test_eine_streichung_aus_einem_frueheren_paket_haelt(frueher, neu):
    alt = frueher[0]["potenziale"][0]["potenzial_id"]
    neu[1]["gestrichene_potenziale"] = [
        {"potenzial_id": alt, "kp_id": "KP-05", "begruendung": "fällt nach der Nacherhebung weg"}
    ]
    assert _befunde(neu, frueher) == []


def test_eine_uneinheitliche_fassung_im_lauf_faellt_auf(neu):
    neu[0]["schema_version"] = "3.0"
    assert any("uneinheitliche schema_version" in b for b in _befunde(neu))
