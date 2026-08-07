import json
import os

import httpx
import pytest

from bc1_core.package import TOY_PROZESS
from bc1_core.types import SessionState
from bc1_service.ollama_llm import OllamaLLM


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
        raise httpx.ConnectError("All connection attempts failed")


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


# Constrained Decoding + Determinismus sind der Kern des Adapters: das Schema
# erzwingt valides JSON, temperature 0 macht Dev-Läufe reproduzierbar, und
# stream=False ist Pflicht (REST-Default wäre streaming).
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
