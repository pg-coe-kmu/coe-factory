from bc1_core.types import FieldStatus, SessionState
from bc1_core.package import TOY_PROZESS, FieldSpec, UseCasePackage
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

def test_duplicate_conflict_value_is_not_added_twice():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    llm3 = FakeLLM({"c": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "c", "msg-3", TOY_PROZESS, llm3)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"                # weiterhin nicht überschrieben
    assert fv.candidates == ["Bestellung"]       # Dedup: kein Duplikat
    assert fv.status is FieldStatus.UNKLAR

def test_third_differing_value_accumulates_from_unklar_state():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    assert st.values["prozess_name"].status is FieldStatus.UNKLAR
    llm3 = FakeLLM({"c": [ExtractionCandidate("prozess_name", "Einkauf")]})
    extract_and_merge(st, "c", "msg-3", TOY_PROZESS, llm3)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"                # weiterhin nicht überschrieben
    assert fv.candidates == ["Bestellung", "Einkauf"]
    assert fv.status is FieldStatus.UNKLAR

def test_invalid_value_is_replaced_by_valid_correction():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("haeufigkeit", "oft")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    assert st.values["haeufigkeit"].status is FieldStatus.UNGUELTIG
    llm2 = FakeLLM({"b": [ExtractionCandidate("haeufigkeit", "5 mal pro Woche")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["haeufigkeit"]
    assert fv.value == "5 mal pro Woche"         # Korrektur ersetzt UNGUELTIG
    assert fv.status is FieldStatus.GUELTIG
    assert "oft" in fv.candidates                # alter Wert geht nicht verloren
    assert fv.source_message_id == "msg-2"

# Ein werfender Validator (z. B. int() auf "fuenfhundert") darf nie den Turn
# crashen — mit Raw-First-Save (Task 8) wäre die Nachricht sonst dauerhaft
# verloren. Policy: Validator-Fehler = Wert UNGUELTIG.
def test_werfender_validator_macht_wert_ungueltig_statt_crash():
    paket = UseCasePackage(
        name="p", schema_version="0.1",
        fields=(FieldSpec("betrag", "Wie hoch?",
                          validator=lambda v: int(v) > 0),),
    )
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("betrag", "fuenfhundert")]})
    extract_and_merge(st, "m", "msg-1", paket, llm)
    assert st.values["betrag"].status is FieldStatus.UNGUELTIG
    assert st.values["betrag"].value == "fuenfhundert"

def test_invalid_value_replaced_by_another_invalid_stays_ungueltig():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("haeufigkeit", "oft")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("haeufigkeit", "selten")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["haeufigkeit"]
    assert fv.value == "selten"
    assert fv.status is FieldStatus.UNGUELTIG
    assert "oft" in fv.candidates
