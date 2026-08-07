"""Read-only-Zugriff auf den BC0-Baseline-Snapshot über stabile IDs.

Vertrag: BC0-Handover v1.0 vom 16.06. — Snapshot-Datei heute, Live-API
mit identischer Struktur später; BC1 liest nur, Rückgaben laufen über den
Anreicherungs-Pfad (nicht Teil dieses Moduls).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

_SCHEMA_PFAD = Path(__file__).with_name("snapshot_schema.json")


class SnapshotFehler(ValueError):
    pass


class Snapshot:
    def __init__(self, daten: dict) -> None:
        self._daten = daten
        self._prozesse = {
            p["process_id"]: p for p in daten["stammdaten"]["prozesse"]
        }
        self._teilprozesse = {
            tp["sub_process_id"]: tp
            for p in daten["stammdaten"]["prozesse"]
            for tp in p["teilprozesse"]
        }

    def prozess_ids(self) -> list[str]:
        return list(self._prozesse)

    def prozess(self, process_id: str) -> dict | None:
        return self._prozesse.get(process_id)

    def teilprozess(self, sub_process_id: str) -> dict | None:
        return self._teilprozesse.get(sub_process_id)

    def prozess_liste(self) -> list[dict]:
        return [
            {"process_id": p["process_id"], "process_name": p["process_name"]}
            for p in self._daten["stammdaten"]["prozesse"]
        ]


def lade_snapshot(pfad: str | Path) -> Snapshot:
    daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA_PFAD.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(daten, schema)
    except jsonschema.ValidationError as fehler:
        raise SnapshotFehler(
            f"Snapshot verletzt das BC0-Schema: {fehler.message}"
        ) from fehler
    return Snapshot(daten)
