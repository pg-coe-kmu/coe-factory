from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.confidence import confidence_check

def _state_with(**felder):
    st = SessionState(session_id="s1", schema_version="0.1")
    for name, status in felder.items():
        st.values[name] = FieldValue(value="x", status=status)
    return st

def test_empty_state_all_required_open():
    res = confidence_check(SessionState("s1", "0.1"), TOY_PROZESS)
    assert res.completeness == 0.0
    assert res.offene_pflichtfelder == ["prozess_name", "ausloeser", "haeufigkeit"]

def test_completeness_counts_only_gueltig():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.UNGUELTIG,
                     haeufigkeit=FieldStatus.GUELTIG)
    res = confidence_check(st, TOY_PROZESS)
    assert res.completeness == 2 / 3
    assert res.offene_pflichtfelder == ["ausloeser"]

def test_ungeloest_is_not_open_but_listed():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.GUELTIG,
                     haeufigkeit=FieldStatus.UNGELOEST)
    res = confidence_check(st, TOY_PROZESS)
    assert res.offene_pflichtfelder == []
    assert res.ungeloeste_felder == ["haeufigkeit"]
