"""Die geteilten Prompt-Konstanten sind ein Wire-Vertrag zwischen den
LLM-Adaptern und dem Extractor — beide Adapter importieren aus prompts.py,
damit nichts driftet."""
from bc1_core.package import TOY_PROZESS
from bc1_core.types import FieldValue, SessionState
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_FRAGE,
    frage_nutzer_prompt,
)


def test_extraktions_schema_ist_der_wire_vertrag():
    eintrag = EXTRAKTIONS_SCHEMA["properties"]["extraktionen"]["items"]
    assert eintrag["required"] == ["feld", "wert"]
    assert eintrag["additionalProperties"] is False
    assert EXTRAKTIONS_SCHEMA["required"] == ["extraktionen"]


def test_system_prompts_sind_die_bekannten_deutschen_prompts():
    assert "extrahierst" in SYSTEM_EXTRAKTION
    assert "Interview" in SYSTEM_FRAGE


def test_frage_prompt_markiert_nachfragen_ab_zweitem_versuch():
    state = SessionState("s1", "0.1")
    # attempts zählt der Dialog VOR dem phrase-Aufruf hoch: 1 = Erstfrage,
    # ab 2 ist es wirklich eine Nachfrage.
    state.values["haeufigkeit"] = FieldValue(attempts=2)
    prompt = frage_nutzer_prompt(TOY_PROZESS.field("haeufigkeit"), state)
    assert "Nachfrage" in prompt
    assert "haeufigkeit" in prompt


def test_frage_prompt_erstfrage_ohne_nachfrage_hinweis():
    state = SessionState("s1", "0.1")
    state.values["haeufigkeit"] = FieldValue(attempts=1)
    prompt = frage_nutzer_prompt(TOY_PROZESS.field("haeufigkeit"), state)
    assert "Nachfrage" not in prompt
