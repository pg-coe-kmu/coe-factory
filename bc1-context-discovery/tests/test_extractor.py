from bc1_core.types import FieldStatus, SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.extractor import extract_and_merge

def test_new_value_is_stored_with_source_and_validated():
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("prozess_name", "Freigabe"),
                         ExtractionCandidate("haeufigkeit", "oft")]})
    extract_and_merge(st, "m", "msg-1", TOY_PROZESS, llm)
    assert st.values["prozess_name"].value == "Freigabe"
    assert st.values["prozess_name"].status is FieldStatus.GUELTIG
    assert st.values["prozess_name"].source_message_id == "msg-1"
    assert st.values["haeufigkeit"].status is FieldStatus.UNGUELTIG  # kein Digit

def test_unknown_field_is_ignored():
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("gibt_es_nicht", "x")]})
    extract_and_merge(st, "m", "msg-1", TOY_PROZESS, llm)
    assert "gibt_es_nicht" not in st.values

def test_same_value_again_is_noop():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"
    assert fv.status is FieldStatus.GUELTIG
    assert fv.candidates == []
    assert fv.source_message_id == "msg-1"  # Quelle bleibt die erste Nachricht

def test_conflict_does_not_overwrite_and_marks_unklar():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"                # nicht überschrieben
    assert fv.candidates == ["Bestellung"]
    assert fv.status is FieldStatus.UNKLAR
