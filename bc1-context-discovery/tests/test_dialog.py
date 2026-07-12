from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.confidence import confidence_check
from bc1_core.llm import FakeLLM
from bc1_core.dialog import decide_next, Decision, MAX_ATTEMPTS_PER_FIELD, MAX_ROUNDS

def test_asks_first_open_field_and_counts_attempt():
    st = SessionState("s1", "0.1")
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf, FakeLLM())
    assert d.done is False
    assert d.next_field == "prozess_name"
    assert d.question == "Wie heißt der Prozess?"
    assert st.values["prozess_name"].attempts == 1

def test_done_when_no_open_required_fields():
    st = SessionState("s1", "0.1")
    for n in ("prozess_name", "ausloeser", "haeufigkeit"):
        st.values[n] = FieldValue(value="x", status=FieldStatus.GUELTIG)
    conf = confidence_check(st, TOY_PROZESS)
    assert decide_next(st, TOY_PROZESS, conf, FakeLLM()) == Decision(done=True)

def test_field_over_attempt_cap_becomes_ungeloest():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(status=FieldStatus.FEHLT,
                                           attempts=MAX_ATTEMPTS_PER_FIELD)
    st.values["ausloeser"] = FieldValue(value="x", status=FieldStatus.GUELTIG)
    st.values["haeufigkeit"] = FieldValue(value="3", status=FieldStatus.GUELTIG)
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf, FakeLLM())
    assert st.values["prozess_name"].status is FieldStatus.UNGELOEST
    assert d.done is True

def test_done_at_round_limit_even_with_open_fields():
    st = SessionState("s1", "0.1")
    st.rounds = MAX_ROUNDS
    conf = confidence_check(st, TOY_PROZESS)
    assert decide_next(st, TOY_PROZESS, conf, FakeLLM()) == Decision(done=True)
    assert all(fv.attempts == 0 for fv in st.values.values())
