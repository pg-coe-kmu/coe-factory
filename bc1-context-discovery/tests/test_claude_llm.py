import json
import os

import pytest

from bc1_core.gespraech import TurnKontext
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.core import process_turn
from bc1_core.types import SessionState
from bc1_service.claude_llm import ClaudeLLM
from bc1_service.prompts import SYSTEM_GESPRAECH


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


# Extraktion und Umformulierung sind triviale Aufgaben. Ohne explizites
# effort denkt das Standardmodell per Default lange und frisst das
# max_tokens-Budget auf, statt zu antworten (-> stop_reason max_tokens).
def test_effort_low_wird_gesetzt():
    stub = _StubClient([_Antwort(_extraktions_json())])
    ClaudeLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    assert stub.messages.aufrufe[0]["output_config"]["effort"] == "low"

    stub_antworte = _StubClient([_Antwort("Wie oft?")])
    kontext = TurnKontext(nutzer_nachricht="msg", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    ClaudeLLM(client=stub_antworte).antworte(kontext)
    assert stub_antworte.messages.aufrufe[0]["output_config"]["effort"] == "low"


# Abgeschnittene Antworten sind kaputte Antworten: bei extract wäre das JSON
# unvollständig (json.loads würde mit einer irreführenden Meldung scheitern).
# Muss laut werden — process_turn macht daraus den fehler_fortsetzbar-Vertrag.
def test_max_tokens_truncation_wirft():
    stub = _StubClient([_Antwort("{\"extrakt", stop_reason="max_tokens")])
    with pytest.raises(RuntimeError):
        ClaudeLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))


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


def test_modell_override_aus_umgebung(monkeypatch):
    monkeypatch.setenv("BC1_CLAUDE_MODELL", "test-modell")
    stub = _StubClient([_Antwort(_extraktions_json())])
    ClaudeLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    assert stub.messages.aufrufe[0]["model"] == "test-modell"


def test_antworte_nur_whitespace_wirft():
    stub = _StubClient([_Antwort("   ")])
    kontext = TurnKontext(nutzer_nachricht="msg", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    with pytest.raises(RuntimeError, match="ohne Inhalt"):
        ClaudeLLM(client=stub).antworte(kontext)


def test_antworte_nutzt_gespraechsprompt_und_strippt():
    stub = _StubClient([_Antwort("  Notiert. Wie oft?  ")])
    kontext = TurnKontext(nutzer_nachricht="msg", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    text = ClaudeLLM(client=stub).antworte(kontext)
    assert text == "Notiert. Wie oft?"
    aufruf = stub.messages.aufrufe[0]
    assert aufruf["system"] == SYSTEM_GESPRAECH
    assert "Wie oft?" in aufruf["messages"][0]["content"]
    assert aufruf["output_config"]["effort"] == "low"


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
