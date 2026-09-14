import json
import os

import pytest

from bc1_core.core import process_turn
from bc1_core.gespraech import TurnKontext
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.types import SessionState
from bc1_service.ollama_llm import OllamaLLM
from bc1_service.prompts import SYSTEM_GESPRAECH

MANDANT = "11111111-1111-1111-1111-111111111111"


class _Nachricht:
    def __init__(self, content: str) -> None:
        self.content = content


class _Antwort:
    def __init__(self, content: str, done_reason: str = "stop") -> None:
        self.message = _Nachricht(content)
        self.done_reason = done_reason


class _StubClient:
    """Zeichnet chat()-Aufrufe auf — Muster wie _StubClient in test_claude_llm.py."""

    def __init__(self, antworten: list) -> None:
        self._antworten = list(antworten)
        self.aufrufe: list[dict] = []

    def chat(self, **kwargs):
        self.aufrufe.append(kwargs)
        return self._antworten.pop(0)


class _KaputterClient:
    def chat(self, **kwargs):
        # Die ollama-Lib wirft bei nicht erreichbarem Server den builtin
        # ConnectionError (sie übersetzt httpx.ConnectError intern selbst).
        raise ConnectionError(
            "Failed to connect to Ollama. Please check that Ollama is "
            "downloaded, running and accessible."
        )


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
    llm = OllamaLLM(client=stub)
    kandidaten = llm.extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    assert [(k.field_name, k.value) for k in kandidaten] == [
        ("prozess_name", "Urlaubsantrag")
    ]


# Leere Modell-Antwort (z. B. wenn ein via BC1_OLLAMA_MODELL gesetztes
# Reasoning-Modell nur thinking füllt) muss laut werden — Analogie zu
# ClaudeLLMs "LLM-Antwort ohne Textblock"-Guard.
def test_leere_antwort_wirft():
    stub = _StubClient([_Antwort("")])
    with pytest.raises(RuntimeError):
        OllamaLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))


# Codex-Zweitmeinung 07.08.: nur-Whitespace passiert den rohen Guard und
# wird erst in antworte() zu "" gestrippt — eine leere Antwort ginge an den
# Nutzer und würde idempotent zementiert. Muss laut werden.
def test_nur_whitespace_antwort_wirft():
    stub = _StubClient([_Antwort("  \n")])
    kontext = TurnKontext(nutzer_nachricht="msg", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    with pytest.raises(RuntimeError):
        OllamaLLM(client=stub).antworte(kontext)


# Constrained Decoding + Determinismus sind der Kern des Adapters: das Schema
# erzwingt valides JSON, temperature 0 macht Dev-Läufe reproduzierbar, und
# stream=False pinnt den Nicht-Streaming-Modus (Python-Lib-Default; der REST-Default wäre Streaming).
def test_extract_nutzt_schema_temperature_null_und_kein_streaming():
    stub = _StubClient([_Antwort(_extraktions_json())])
    OllamaLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    aufruf = stub.aufrufe[0]
    assert aufruf["format"]["required"] == ["extraktionen"]
    assert aufruf["stream"] is False
    assert aufruf["options"]["temperature"] == 0
    assert aufruf["options"]["num_predict"] == 4096


# Abgeschnittene Antworten sind kaputte Antworten (halbes JSON) — muss laut
# werden, statt dass json.loads mit irreführender Meldung scheitert.
def test_abgeschnittene_antwort_wirft():
    stub = _StubClient([_Antwort("{\"extrakt", done_reason="length")])
    with pytest.raises(RuntimeError):
        OllamaLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))


# DER typische Dev-Stolperer: Ollama läuft nicht. Der nackte httpx-Fehler
# ist kryptisch — die Meldung muss den Fix nennen.
def test_verbindungsfehler_nennt_ollama_serve():
    with pytest.raises(RuntimeError, match="ollama serve"):
        OllamaLLM(client=_KaputterClient()).extract(
            "...", TOY_PROZESS, SessionState("s1", "0.1")
        )


def test_modell_override_aus_umgebung(monkeypatch):
    monkeypatch.setenv("BC1_OLLAMA_MODELL", "test-modell")
    stub = _StubClient([_Antwort(_extraktions_json())])
    OllamaLLM(client=stub).extract("...", TOY_PROZESS, SessionState("s1", "0.1"))
    assert stub.aufrufe[0]["model"] == "test-modell"


def test_protocol_konformitaet_ein_turn_durch_process_turn():
    stub = _StubClient([
        _Antwort(_extraktions_json(("prozess_name", "Urlaubsantrag"))),
        _Antwort("Was löst den Prozess aus?"),
    ])
    antwort = process_turn(
        InMemoryStateStore(), OllamaLLM(client=stub), TOY_PROZESS,
        "s1", "m1", "Der Prozess heißt Urlaubsantrag",
        company_id=MANDANT,
    )
    assert antwort["status"] == "frage"
    assert antwort["payload"]["feld"] == "ausloeser"
    assert antwort["payload"]["naechste_frage"] == "Was löst den Prozess aus?"


def test_antworte_nutzt_gespraechsprompt_und_strippt():
    stub = _StubClient([_Antwort("  Notiert. Wie oft?  ")])
    kontext = TurnKontext(nutzer_nachricht="msg", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    text = OllamaLLM(client=stub).antworte(kontext)
    assert text == "Notiert. Wie oft?"
    assert stub.aufrufe[0]["messages"][0]["content"] == SYSTEM_GESPRAECH
    assert "Wie oft?" in stub.aufrufe[0]["messages"][1]["content"]


@pytest.mark.skipif(
    os.environ.get("BC1_ECHT_LLM") != "1",
    reason="Echt-Stichprobe nur mit BC1_ECHT_LLM=1 (lokal, aber langsam)",
)
def test_echt_ollama_stichprobe_extraktion():
    llm = OllamaLLM()
    try:
        kandidaten = llm.extract(
            "Der Prozess heißt Urlaubsantrag und läuft etwa 50 mal pro Jahr.",
            TOY_PROZESS,
            SessionState("s1", "0.1"),
        )
    except RuntimeError as fehler:
        if "ollama serve" in str(fehler):
            pytest.skip("Ollama läuft nicht")
        raise
    felder = {k.field_name for k in kandidaten}
    assert "prozess_name" in felder
