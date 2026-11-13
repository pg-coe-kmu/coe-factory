"""Tests für die Kurztexte der Folie (Vertrag v3.2, #382, ADR-010 · BC2, Nachtrag vom 13.11.2026).

Die Vertragsform, gegen die echten Schemadateien: eine 3.2 trägt ``heute_kurz`` und
``potenzielle_loesung.to_be_kurz`` an jedem Potenzial, je ein bis zwei Sätze Fließtext,
höchstens 300 Zeichen, ohne Markdown und ohne Zeilenumbruch, und weiter
``ersetzt_potenzial_ids``. 3.0 und 3.1 bleiben gültig, und jede gelieferte Lieferung bleibt
es unverändert — ein übergebenes Konzept wird nie ungültig, es veraltet (ADR-007 · BC2, 2.4).

Der Wächter, der die Kurztexte vor dem Ablegen prüft, steht in ``test_ausarbeitung.py``,
die Folie in ``test_praesentation.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[3]
VERTRAEGE = WURZEL / "contracts" / "bc2-to-bc3"
BEISPIELE = WURZEL / "contracts" / "examples"
LIEFERUNGEN = VERTRAEGE / "lieferungen"
#: Die eingefrorene v2-Lieferung läuft gegen die archivierten Schemas (``validate.py``).
EINGEFROREN_V2 = "2026-08-30-vorlaeufig"
sys.path.insert(0, str(WURZEL / "bc2-strategic-advisor" / "tools"))

from kette import kettenbefunde  # noqa: E402


def _lies(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def _fehler(schema_datei: str, daten: dict) -> list:
    jsonschema = pytest.importorskip("jsonschema")
    v = jsonschema.Draft202012Validator(_lies(VERTRAEGE / schema_datei))
    return list(v.iter_errors(daten))


def _konzept() -> dict:
    return _lies(BEISPIELE / "mock_automatisierungskonzept.json")


def _prio() -> dict:
    return _lies(BEISPIELE / "mock_prozesspriorisierung.json")


def _als_31(k: dict) -> dict:
    """Dieselbe Datei als 3.1: ohne ``heute_kurz``, sonst gleich."""
    k["schema_version"] = "3.1"
    for p in k["potenziale"]:
        p.pop("heute_kurz", None)
    return k


# --- Die Beispieldateien -----------------------------------------------------


def test_die_beispieldateien_sind_v3_2_und_tragen_beide_kurztexte():
    konzepte = [_konzept(), _lies(BEISPIELE / "mock_automatisierungskonzept_KP-05.json")]
    prio = _prio()
    assert {k["schema_version"] for k in konzepte} == {prio["schema_version"]} == {"3.2"}
    for k in konzepte:
        assert not _fehler("konzept.schema.json", k)
        for p in k["potenziale"]:
            for text in (p["heute_kurz"], p["potenzielle_loesung"]["to_be_kurz"]):
                assert 0 < len(text) <= 300 and "\n" not in text
    assert not _fehler("priorisierung.schema.json", prio)


def test_der_kurztext_heute_ist_bc3s_eigener_wortlaut():
    """Die Vorlage führt keinen Heute-Kurztext; die Beispieldatei erfindet ihn nicht, sondern
    nimmt die ersten Sätze der Beschreibung, die den heutigen Ablauf schildern."""
    for k in (_konzept(), _lies(BEISPIELE / "mock_automatisierungskonzept_KP-05.json")):
        for p in k["potenziale"]:
            assert p["beschreibung"].startswith(p["heute_kurz"])
            assert "Automatisiert wird" not in p["heute_kurz"]


# --- Was eine 3.2 tragen muss ----------------------------------------------------


@pytest.mark.parametrize("pfad", [("heute_kurz",), ("potenzielle_loesung", "to_be_kurz"),
                                  ("ersetzt_potenzial_ids",)])
def test_eine_v3_2_ohne_pflichtfeld_ist_ungueltig(pfad):
    k = _konzept()
    ziel = k["potenziale"][0]
    for teil in pfad[:-1]:
        ziel = ziel[teil]
    del ziel[pfad[-1]]
    assert _fehler("konzept.schema.json", k)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "x" * 301,
        "Erster Satz.\nZweiter Satz.",
        "## Heute",
        "- Anfragen kommen per Mail.",
        "1. Anfragen kommen per Mail.",
        "Anfragen kommen **per Mail**.",
    ],
    ids=["leer", "nur-leerzeichen", "301-zeichen", "zeilenumbruch", "ueberschrift",
         "aufzaehlung", "nummeriert", "fett"],
)
@pytest.mark.parametrize("feld", ["heute_kurz", "to_be_kurz"])
def test_ein_kurztext_ist_fliesstext_bis_300_zeichen(feld, text):
    k = _konzept()
    p = k["potenziale"][0]
    (p if feld == "heute_kurz" else p["potenzielle_loesung"])[feld] = text
    assert _fehler("konzept.schema.json", k)


def test_genau_300_zeichen_sind_erlaubt():
    k = _konzept()
    k["potenziale"][0]["heute_kurz"] = "x" * 299 + "."
    k["potenziale"][0]["potenzielle_loesung"]["to_be_kurz"] = "C# und n8n tragen den Ablauf. " * 10
    assert not _fehler("konzept.schema.json", k)


# --- 3.0 und 3.1 bleiben gültig ------------------------------------------------


def test_eine_v3_1_braucht_keinen_kurztext_und_traegt_keinen_heute_kurztext():
    k = _als_31(_konzept())
    assert not _fehler("konzept.schema.json", k)
    del k["potenziale"][0]["potenzielle_loesung"]["to_be_kurz"]
    assert not _fehler("konzept.schema.json", k), "to_be_kurz bleibt vor 3.2 optional"
    k["potenziale"][1]["heute_kurz"] = "Heute tippt die Sachbearbeitung jede Anfrage ab."
    assert _fehler("konzept.schema.json", k), "die Nummer sagt, ob das Feld da ist"


def test_vor_3_2_gilt_die_300er_grenze_fuer_to_be_kurz_nicht():
    """Gelieferte 3.1-Dateien wurden ohne die Grenze geschrieben; sie nachträglich zu
    verschärfen, machte eine übergebene Lieferung ungültig."""
    k = _als_31(_konzept())
    k["potenziale"][0]["potenzielle_loesung"]["to_be_kurz"] = "Lang.\n" * 80
    assert not _fehler("konzept.schema.json", k)


def test_jede_gelieferte_lieferung_bleibt_gueltig():
    ordner = sorted(o for o in LIEFERUNGEN.iterdir() if o.is_dir() and o.name != EINGEFROREN_V2)
    assert len(ordner) >= 6
    for o in ordner:
        for datei in o.glob("konzept_*.json"):
            assert not _fehler("konzept.schema.json", _lies(datei)), datei
        assert not _fehler("priorisierung.schema.json", _lies(o / "prozesspriorisierung.json")), o


def test_eine_priorisierung_v3_2_traegt_ausgangslage_und_streichliste_wie_3_1():
    for feld in ("ausgangslage", "gestrichene_potenziale"):
        p = _prio()
        del p[feld]
        assert _fehler("priorisierung.schema.json", p), feld


def test_die_kette_wird_auch_in_einer_v3_2_geprueft():
    """``kette.py`` sah bis #382 nur auf 3.1 — eine 3.2 wäre ungeprüft durchgegangen."""
    k, p = _konzept(), _prio()
    k["potenziale"][0]["ersetzt_potenzial_ids"] = ["00000000-0000-4000-8000-000000000001"]
    befunde = kettenbefunde([k], p, {})
    assert any("steht in keiner freigegebenen Lieferung" in b for b in befunde), befunde
    assert kettenbefunde([_als_31(_konzept())], p, {}) == [
        "uneinheitliche schema_version im Lauf: ['3.1', '3.2']"]
