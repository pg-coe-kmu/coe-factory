import json

import pytest

from bc1_service.snapshot import Snapshot, SnapshotFehler, lade_snapshot


def _mini_snapshot() -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-08-01T00:00:00Z",
        "mandant": {
            "id": 1,
            "name": "Beispiel GmbH",
            "unternehmensdaten": {},
        },
        "stammdaten": {
            "items": [],
            "dimensionen": [],
            "prozesse": [
                {
                    "process_id": "KP-01",
                    "process_name": "Beispielprozess",
                    "teilprozesse": [
                        {
                            "sub_process_id": "KP-01.TP-1",
                            "step_no": 1,
                            "name": "Erster Schritt",
                        }
                    ],
                }
            ],
        },
        "bewertungen": [],
        "reifegrad": {"gesamt": 0, "dimension_durchschnitt": {}, "kp_rows": []},
    }


def _schreibe(tmp_path, daten: dict):
    pfad = tmp_path / "snapshot.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


def test_laedt_validen_snapshot_und_findet_stabile_ids(tmp_path):
    snap = lade_snapshot(_schreibe(tmp_path, _mini_snapshot()))
    assert snap.prozess_ids() == ["KP-01"]
    assert snap.prozess("KP-01")["process_name"] == "Beispielprozess"
    assert snap.teilprozess("KP-01.TP-1")["step_no"] == 1
    assert snap.prozess("KP-99") is None
    assert snap.prozess_liste() == [
        {"process_id": "KP-01", "process_name": "Beispielprozess"}
    ]


def test_schema_verstoss_wird_abgelehnt(tmp_path):
    kaputt = _mini_snapshot()
    kaputt["stammdaten"]["prozesse"][0]["process_id"] = "P1"  # verletzt Pattern
    with pytest.raises(SnapshotFehler):
        lade_snapshot(_schreibe(tmp_path, kaputt))


def test_fehlender_pflichtblock_wird_abgelehnt(tmp_path):
    kaputt = _mini_snapshot()
    del kaputt["reifegrad"]
    with pytest.raises(SnapshotFehler):
        lade_snapshot(_schreibe(tmp_path, kaputt))
