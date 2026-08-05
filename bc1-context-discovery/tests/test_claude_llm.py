import json
import os

import pytest

from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.core import process_turn
from bc1_core.types import FieldValue, SessionState
from bc1_service.claude_llm import ClaudeLLM


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Antwort:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [_Block(text)]
        self.stop_reason = stop_reason


class _StubMessages:
    def __init__(self, antworten: list) -> None:
        self._antworten = list(antworten)
        self.aufrufe: list[dict] = []

    def create(self, **kwargs):
        self.aufrufe.append(kwargs)
        return self._antworten.pop(0)


class _StubClient:
    def __init__(self, antworten: list) -> None:
        self.messages = _StubMessages(antworten)


def _extraktions_json(*paare: tuple[str, str]) -> str:
    return json.dumps(
        {"extraktionen": [{"feld": f, "wert": w} for f, w in paare]}
    )


def test_extract_liefert_kandidaten_und_filtert_unbekannte_felder():
    stub = _StubClient([_Antwort(_extraktions_json(
        ("prozess_name", "Urlaubsantrag"),
        ("erfundenes_feld", "x"),
        ("ausloeser", "   "),
    ))])
    llm = ClaudeLLM(client=stub)
    kandidaten = llm.extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    assert [(k.field_name, k.value) for k in kandidaten] == [
        ("prozess_name", "Urlaubsantrag")
    ]


def test_extract_nutzt_structured_outputs_mit_json_schema():
    stub = _StubClient([_Antwort(_extraktions_json())])
    ClaudeLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    aufruf = stub.messages.aufrufe[0]
    assert aufruf["output_config"]["format"]["type"] == "json_schema"


def test_refusal_wirft_statt_leise_zu_scheitern():
    stub = _StubClient([_Antwort("", stop_reason="refusal")])
    with pytest.raises(RuntimeError):
        ClaudeLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))


def test_phrase_liefert_frage_und_markiert_nachfragen():
    stub = _StubClient([_Antwort("  Wie oft kommt der Prozess vor?  ")])
    state = SessionState("s1", "0.1")
    state.values["haeufigkeit"] = FieldValue(attempts=1)
    frage = ClaudeLLM(client=stub).phrase(TOY_PROZESS.field("haeufigkeit"), state)
    assert frage == "Wie oft kommt der Prozess vor?"
    assert "Nachfrage" in stub.messages.aufrufe[0]["messages"][0]["content"]


def test_protocol_konformitaet_ein_turn_durch_process_turn():
    stub = _StubClient([
        _Antwort(_extraktions_json(("prozess_name", "Urlaubsantrag"))),
        _Antwort("Was löst den Prozess aus?"),
    ])
    antwort = process_turn(
        InMemoryStateStore(), ClaudeLLM(client=stub), TOY_PROZESS,
        "s1", "m1", "Der Prozess heißt Urlaubsantrag",
    )
    assert antwort["status"] == "frage"
    assert antwort["payload"]["feld"] == "ausloeser"
    assert antwort["payload"]["naechste_frage"] == "Was löst den Prozess aus?"


@pytest.mark.skipif(
    not os.environ.get("BC1_ECHT_LLM"),
    reason="Echt-API-Stichprobe nur mit BC1_ECHT_LLM=1 (Kosten!)",
)
def test_echt_api_stichprobe_extraktion():
    llm = ClaudeLLM()
    kandidaten = llm.extract(
        "Der Prozess heißt Urlaubsantrag und läuft etwa 50 mal pro Jahr.",
        TOY_PROZESS,
        SessionState("s1", "0.1"),
    )
    felder = {k.field_name for k in kandidaten}
    assert "prozess_name" in felder
