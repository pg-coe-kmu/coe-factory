from bc1_core.types import SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.llm import FakeLLM, ExtractionCandidate

def test_fake_extract_returns_scripted_candidates():
    fake = FakeLLM({"Bestellfreigabe, monatlich":
                    [ExtractionCandidate("prozess_name", "Bestellfreigabe")]})
    out = fake.extract("Bestellfreigabe, monatlich", TOY_PROZESS, SessionState("s1", "0.1"))
    assert out == [ExtractionCandidate("prozess_name", "Bestellfreigabe")]

def test_fake_extract_unknown_message_is_empty():
    assert FakeLLM().extract("hä?", TOY_PROZESS, SessionState("s1", "0.1")) == []

def test_fake_phrase_uses_field_question():
    fake = FakeLLM()
    assert fake.phrase(TOY_PROZESS.field("ausloeser"), SessionState("s1", "0.1")) \
        == "Was löst den Prozess aus?"
