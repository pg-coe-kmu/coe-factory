import dataclasses
import json

import pytest

from bc1_core.serialize import state_from_dict, state_to_dict
from bc1_core.types import (
    Candidate,
    FieldStatus,
    FieldValue,
    SessionState,
    SessionStatus,
)


def _voller_state() -> SessionState:
    return SessionState(
        session_id="s1",
        schema_version="0.1",
        paket_name="toy_prozess",
        status=SessionStatus.WARTET,
        version=3,
        rounds=2,
        values={
            "prozess_name": FieldValue(
                value="Urlaubsantrag",
                status=FieldStatus.GUELTIG,
                source_message_id="m1",
                candidates=[Candidate("Urlaub", "m0")],
                attempts=1,
            ),
            "haeufigkeit": FieldValue(
                status=FieldStatus.UNGELOEST,
                attempts=2,
                grund="nachfrage_limit_erreicht",
            ),
        },
        processed_message_ids={"m0", "m1"},
        raw_log=[("m0", "erste Nachricht"), ("m1", "zweite Nachricht")],
        antworten={
            "m1": {
                "status": "frage",
                "payload": {"naechste_frage": "Wie oft?", "feld": "haeufigkeit"},
            }
        },
    )


def test_roundtrip_ueber_echtes_json():
    original = _voller_state()
    wieder = state_from_dict(json.loads(json.dumps(state_to_dict(original))))
    assert wieder == original


def test_raw_log_wird_re_getupelt_und_set_wiederhergestellt():
    wieder = state_from_dict(json.loads(json.dumps(state_to_dict(_voller_state()))))
    assert all(isinstance(eintrag, tuple) for eintrag in wieder.raw_log)
    assert isinstance(wieder.processed_message_ids, set)


def test_enums_landen_als_wire_strings_im_dict():
    daten = state_to_dict(_voller_state())
    assert daten["status"] == "wartet_auf_antwort"
    assert daten["values"]["prozess_name"]["status"] == "gueltig"


def test_wert_ohne_quelle_wird_abgelehnt():
    daten = state_to_dict(_voller_state())
    daten["values"]["prozess_name"]["source_message_id"] = None
    with pytest.raises(ValueError):
        state_from_dict(daten)


# Leerstring ist keine Quelle: der Ledger-Eintrag waere nicht mehr auf eine
# Nachricht zurueckfuehrbar — genauso kaputt wie eine fehlende Quelle.
def test_wert_mit_leerer_quelle_wird_abgelehnt():
    daten = state_to_dict(_voller_state())
    daten["values"]["prozess_name"]["source_message_id"] = ""
    with pytest.raises(ValueError):
        state_from_dict(daten)


def test_kandidat_ohne_quelle_wird_abgelehnt():
    daten = state_to_dict(_voller_state())
    daten["values"]["prozess_name"]["candidates"][0]["source_message_id"] = None
    with pytest.raises(ValueError):
        state_from_dict(daten)


# Waechter gegen stille Datenverluste: ein neues SessionState-Feld muss hier
# auffallen, nicht erst als fehlender Wert im persistenten Store.
def test_serialisierung_deckt_alle_sessionstate_felder():
    daten = state_to_dict(_voller_state())
    assert set(daten.keys()) == {f.name for f in dataclasses.fields(SessionState)}


def test_unbekannter_statuswert_wird_abgelehnt():
    daten = state_to_dict(_voller_state())
    daten["status"] = "kaputt"
    with pytest.raises(ValueError):
        state_from_dict(daten)
