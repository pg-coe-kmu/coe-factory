import json

from bc1_core.types import FieldStatus, SessionStatus, FieldValue, SessionState

def test_fieldvalue_defaults_to_fehlt():
    fv = FieldValue()
    assert fv.value is None
    assert fv.status is FieldStatus.FEHLT
    assert fv.attempts == 0

def test_sessionstate_starts_active_version_zero():
    st = SessionState(session_id="s1", schema_version="0.1")
    assert st.status is SessionStatus.AKTIV
    assert st.version == 0
    assert st.values == {}
    assert st.processed_message_ids == set()

# Die String-Werte sind der JSON-Draht-Vertrag BC1→BC2 (Design-Spec) —
# eine Änderung hier bricht den Konsumenten, nicht nur diese Tests.
def test_fieldstatus_wire_werte():
    assert FieldStatus.FEHLT.value == "fehlt"
    assert FieldStatus.GUELTIG.value == "gueltig"
    assert FieldStatus.UNGUELTIG.value == "ungueltig"
    assert FieldStatus.UNKLAR.value == "unklar"
    assert FieldStatus.UNGELOEST.value == "ungeloest"

def test_sessionstatus_wire_werte():
    assert SessionStatus.AKTIV.value == "aktiv"
    assert SessionStatus.WARTET.value == "wartet_auf_antwort"
    assert SessionStatus.FERTIG.value == "fertig"
    assert SessionStatus.FEHLER.value == "fehler_fortsetzbar"

def test_status_enums_serialisieren_und_rehydrieren_als_wire_string():
    assert json.dumps(FieldStatus.GUELTIG) == '"gueltig"'
    assert json.dumps(SessionStatus.WARTET) == '"wartet_auf_antwort"'
    assert FieldStatus("gueltig") is FieldStatus.GUELTIG
    assert SessionStatus("fertig") is SessionStatus.FERTIG
