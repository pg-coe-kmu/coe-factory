"""
Tests: die Lieferung aus Schema ``bc2`` ziehen (#306, entschieden in #305).

Die Strecke ist die des Betriebs, bis auf die Datenbank: ein echter Lauf
(Erkennung → Bewertung → Rechnung → Ausarbeitung, mit Doppelgänger-Modell)
wird abgelegt und freigegeben, ``lieferung.lieferungen`` setzt ihn zusammen,
und ``tools/lieferung_ziehen.py`` schreibt ihn in einen Lieferordner. Zwischen
beiden liegt — wie über ``ssh`` — eine JSON-Rundreise.

Abnahme aus dem Ticket: schemagültig, ein zweiter Zug ändert nichts, ein
manipulierter Ordner bricht ab.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ablage import AblegendeLaufquelle, SpeicherErgebnisbuch
from gate1 import Gate1Entscheidung, NichtFreigegeben, SpeicherGate1Buch, jetzt
from lieferung import lieferungen, mandantenkuerzel

from test_ausarbeitung import (
    NOROAI,
    _JeKonzept,
    _erkannt_zwei,
    _gut_zwei,
    _laufquelle,
    _validator,
    _zwei_kernprozesse,
)

WERKZEUG = Path(__file__).resolve().parents[2] / "tools" / "lieferung_ziehen.py"


def _werkzeug():
    spec = importlib.util.spec_from_file_location("lieferung_ziehen", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul  # sonst findet @dataclass sein Modul nicht
    spec.loader.exec_module(modul)
    return modul


ziehen = _werkzeug()


def _echter_lauf(*, freigeben: str | None = "approved", heraus: int = 0):
    """Ein ausgearbeiteter Lauf über zwei Kernprozesse, abgelegt und entschieden."""
    innen = _laufquelle(_JeKonzept(_erkannt_zwei(), _gut_zwei()), _zwei_kernprozesse(),
                        ("KP-06.TP-1", "KP-06.TP-2", "KP-07.TP-1"))
    ergebnisse = SpeicherErgebnisbuch()
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    ansicht = AblegendeLaufquelle(innen, ergebnisse).ansicht("PKT-301")
    if freigeben:
        ids = ansicht.potenzial_ids()
        gate1.merken(Gate1Entscheidung(
            paket_id="PKT-301", company_id=NOROAI, status=freigeben,
            fassung=ansicht.kopf.fassung,
            approved_potenzial_ids=tuple(ids[heraus:]) if freigeben == "approved" else (),
            nicht_freigegeben=tuple(
                NichtFreigegeben(pid, "Kommt in dieser Runde nicht mit.") for pid in ids[:heraus]
            ),
            kommentar="Abgelehnt im Test." if freigeben == "rejected" else "",
            entscheider="Sergio",
            entschieden_am=jetzt(),
        ))
    return ergebnisse, gate1


def _ueber_ssh(ergebnisse, gate1) -> dict:
    """Was ``python -m lieferung`` ausgibt, nach der Rundreise durch JSON."""
    return json.loads(json.dumps(
        {"lieferungen": [l.als_json() for l in lieferungen(ergebnisse, gate1)]},
        ensure_ascii=False,
    ))


# ---------------------------------------------------------------------------
# Welche Läufe geliefert sind
# ---------------------------------------------------------------------------


def test_ein_freigegebener_echter_lauf_ist_geliefert():
    ergebnisse, gate1 = _echter_lauf()
    (l,) = lieferungen(ergebnisse, gate1)
    assert l.ordner == "noroai-PKT-301-f1"
    assert l.priorisierung["gate1"]["status"] == "approved"
    assert [k["konzept_id"] for k in l.konzepte] == l.priorisierung["konzept_ids"]
    # Das Modellurteil ist ein Hinweis (#305): es reist mit, sperrt aber nichts.
    assert any("#299" in h for h in l.hinweise)


@pytest.mark.parametrize("status", [None, "rejected"])
def test_offen_oder_abgelehnt_ist_nichts_geliefert(status):
    ergebnisse, gate1 = _echter_lauf(freigeben=status)
    assert lieferungen(ergebnisse, gate1) == []


def test_ein_freigegebener_lauf_mit_sperrgrund_ist_nicht_geliefert():
    ergebnisse, gate1 = _echter_lauf()
    ergebnisse.zeilen["PKT-301"][-1].sperrgrund = "Nicht nachrechenbar."
    assert lieferungen(ergebnisse, gate1) == []


def test_das_mandantenkuerzel():
    assert mandantenkuerzel("NoroAI Consulting GmbH", "7c2d5ee9-x") == "noroai"
    assert mandantenkuerzel(None, "7C2D5EE9-2a9a") == "7c2d5ee9"
    assert mandantenkuerzel("  ", "7c2d5ee9-2a9a") == "7c2d5ee9"


# ---------------------------------------------------------------------------
# In den Lieferordner ziehen
# ---------------------------------------------------------------------------


def test_der_gezogene_ordner_ist_schemagueltig(tmp_path):
    ergebnisse, gate1 = _echter_lauf(heraus=1)
    abgleich, _ = ziehen.ziehe(_ueber_ssh(ergebnisse, gate1), tmp_path)

    assert abgleich.neu == ["noroai-PKT-301-f1"] and not abgleich.abweichend
    ordner = tmp_path / "noroai-PKT-301-f1"
    assert sorted(d.name for d in ordner.iterdir()) == [
        "NACHRICHT_AN_BC3.md", "konzept_KP-06.json", "konzept_KP-07.json",
        "prozesspriorisierung.json",
    ]
    prio = json.loads((ordner / "prozesspriorisierung.json").read_text(encoding="utf-8"))
    _validator("priorisierung.schema.json").validate(prio)
    assert prio["gate1"]["nicht_freigegeben"][0]["begruendung"]
    pruefer = _validator("konzept.schema.json")
    for datei in ordner.glob("konzept_*.json"):
        pruefer.validate(json.loads(datei.read_text(encoding="utf-8")))
    # Keine Präsentation: sie geht an den Mandanten (#305, Punkt 4).
    assert not list(ordner.glob("*.pptx"))


def test_die_schluessel_stehen_in_der_reihenfolge_des_schemas(tmp_path):
    """Postgres ``jsonb`` vergisst die Reihenfolge — die Datei darf es nicht zeigen."""
    roh = _ueber_ssh(*_echter_lauf())
    l = roh["lieferungen"][0]
    l["priorisierung"] = dict(sorted(l["priorisierung"].items(), key=lambda kv: (len(kv[0]), kv[0])))
    ziehen.ziehe(roh, tmp_path)

    text = (tmp_path / l["ordner"] / "prozesspriorisierung.json").read_text(encoding="utf-8")
    schluessel = list(json.loads(text))
    assert schluessel[:3] == ["priorisierung_id", "schema_version", "company_id"]
    assert schluessel[-1] == "gate1"
    assert text.endswith("}\n") and "\\u00" not in text


def test_ein_zweiter_zug_aendert_nichts(tmp_path):
    roh = _ueber_ssh(*_echter_lauf())
    ziehen.ziehe(roh, tmp_path)
    vorher = {d: d.read_bytes() for d in (tmp_path / "noroai-PKT-301-f1").iterdir()}

    abgleich, _ = ziehen.ziehe(roh, tmp_path)

    assert abgleich.neu == [] and abgleich.gleich == ["noroai-PKT-301-f1"]
    assert {d: d.read_bytes() for d in (tmp_path / "noroai-PKT-301-f1").iterdir()} == vorher


def test_ein_veraenderter_ordner_bricht_ab_und_nichts_wird_geschrieben(tmp_path, capsys):
    roh = _ueber_ssh(*_echter_lauf())
    ziehen.ziehe(roh, tmp_path)
    prio = tmp_path / "noroai-PKT-301-f1" / "prozesspriorisierung.json"
    prio.write_text(prio.read_text(encoding="utf-8").replace('"fassung": 1', '"fassung": 9'),
                    encoding="utf-8")
    # Dazu ein zweiter, neuer Lauf — er darf beim Abbruch nicht halb entstehen.
    zweiter = json.loads(json.dumps(roh["lieferungen"][0]))
    zweiter["ordner"] = "noroai-PKT-302-f1"
    roh["lieferungen"].append(zweiter)
    datei = tmp_path / "roh.json"
    datei.write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")

    code = ziehen.main(["--aus", str(datei), "--ziel", str(tmp_path)])

    assert code == 1
    assert "ABWEICHUNG  noroai-PKT-301-f1" in capsys.readouterr().out
    assert not (tmp_path / "noroai-PKT-302-f1").exists()


def test_pruefen_schreibt_nichts(tmp_path):
    roh = _ueber_ssh(*_echter_lauf())
    abgleich, _ = ziehen.ziehe(roh, tmp_path, pruefen=True)
    assert abgleich.neu == ["noroai-PKT-301-f1"]
    assert not any(tmp_path.iterdir())


def test_die_nachricht_traegt_freigabe_reihenfolge_und_hinweise(tmp_path):
    ergebnisse, gate1 = _echter_lauf(heraus=1)
    roh = _ueber_ssh(ergebnisse, gate1)
    text = ziehen.nachricht(roh["lieferungen"][0])

    assert text.startswith("# Lieferung an BC3 — noroai-PKT-301-f1\n")
    assert "durch Sergio" in text
    assert "nicht freigegeben: Kommt in dieser Runde nicht mit." in text
    assert "## Hinweise" in text and "#299" in text
    # Byte-gleich heißt auch: kein Zeitpunkt des Ziehens.
    assert ziehen.nachricht(roh["lieferungen"][0]) == text


def test_ordne_folgt_ref_und_anyof():
    wurzel = {
        "$defs": {"spanne": {"type": "object", "properties": {"min": {}, "max": {}}}},
        "properties": {
            "a": {"$ref": "#/$defs/spanne"},
            "b": {"anyOf": [{"type": "null"}, {"$ref": "#/$defs/spanne"}]},
            "c": {"type": "array", "items": {"$ref": "#/$defs/spanne"}},
        },
    }
    daten = {"z": 1, "c": [{"max": 2, "min": 1}], "b": {"max": 2, "min": 1}, "a": {"max": 2, "min": 1}}
    geordnet = ziehen.ordne(daten, wurzel, wurzel)
    assert list(geordnet) == ["a", "b", "c", "z"]
    assert list(geordnet["a"]) == list(geordnet["b"]) == list(geordnet["c"][0]) == ["min", "max"]
