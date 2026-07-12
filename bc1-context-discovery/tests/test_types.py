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
