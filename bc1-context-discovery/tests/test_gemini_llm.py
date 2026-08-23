"""GeminiLLM: Konfiguration, Guards, Key-Hygiene — Stubs, kein Netz."""
import json
import traceback

import pytest
from google.genai import errors, types

from bc1_core.core import process_turn
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.store import InMemoryStateStore
from bc1_service.gemini_llm import KEY_FEHLT, GeminiLLM
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_GESPRAECH,
)

PAKET = UseCasePackage(
    name="gemini_test", schema_version="0.1",
    fields=(FieldSpec("zweck", "Was ist der Zweck?"),))


class _Kandidat:
    def __init__(self, finish):
        self.finish_reason = finish


class _Antwort:
    def __init__(self, text, finish=types.FinishReason.STOP, kandidaten=True):
        self.text = text
        self.candidates = [_Kandidat(finish)] if kandidaten else []


class _Models:
    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.aufrufe = []

    def generate_content(self, **kwargs):
        self.aufrufe.append(kwargs)
        ergebnis = self._antworten.pop(0)
        if isinstance(ergebnis, Exception):
            raise ergebnis
        return ergebnis


class _StubClient:
    def __init__(self, antworten):
        self.models = _Models(antworten)


def _llm(antworten, modell=None):
    return GeminiLLM(client=_StubClient(antworten), modell=modell)


def test_extract_reicht_prompts_schema_und_konfig_durch():
    stub = _StubClient([_Antwort('{"extraktionen": [{"feld": "zweck", "wert": " X "}]}')])
    ergebnis = GeminiLLM(client=stub).extract("Nachricht", PAKET, None)
    aufruf = stub.models.aufrufe[0]
    konfig = aufruf["config"]
    # Default-Pin gemini-3.7-flash: gemini-2.5-flash liefert fuer Neukonten
    # 404 "no longer available to new users" (live verifiziert 23.08.);
    # 3er-Familie => temperature entfaellt.
    assert aufruf["model"] == "gemini-3.7-flash"
    assert konfig.system_instruction == SYSTEM_EXTRAKTION
    assert konfig.response_mime_type == "application/json"
    assert konfig.response_json_schema is EXTRAKTIONS_SCHEMA
    assert konfig.temperature is None
    assert konfig.max_output_tokens == 4096
    assert "Was ist der Zweck?" in aufruf["contents"]
    assert "Nachricht" in aufruf["contents"]
    assert [(k.field_name, k.value) for k in ergebnis] == [("zweck", "X")]


def test_extract_filtert_unbekannte_felder_und_leere_werte():
    stub = _StubClient([_Antwort(json.dumps({"extraktionen": [
        {"feld": "zweck", "wert": "A"},
        {"feld": "fremd", "wert": "B"},
        {"feld": "zweck", "wert": "   "},
    ]}))])
    ergebnis = GeminiLLM(client=stub).extract("m", PAKET, None)
    assert [(k.field_name, k.value) for k in ergebnis] == [("zweck", "A")]


def test_antworte_nutzt_gespraechs_prompts_und_strippt():
    from bc1_core.gespraech import TurnKontext
    stub = _StubClient([_Antwort("  Hallo! Wie oft läuft es?  ")])
    kontext = TurnKontext(nutzer_nachricht="m", neu_erfasst=(),
                          naechste_frage="Wie oft?", ist_nachfrage=False,
                          ist_abschluss=False)
    text = GeminiLLM(client=stub).antworte(kontext)
    konfig = stub.models.aufrufe[0]["config"]
    assert konfig.system_instruction == SYSTEM_GESPRAECH
    assert konfig.response_mime_type is None
    assert text == "Hallo! Wie oft läuft es?"


def test_thinking_budget_null_fuer_25_familie():
    stub = _StubClient([_Antwort("ok")])
    _llm_mit_stub = GeminiLLM(client=stub, modell="gemini-2.5-flash")
    from bc1_core.gespraech import TurnKontext
    _llm_mit_stub.antworte(TurnKontext("m", (), "F?", False, False))
    tk = stub.models.aufrufe[0]["config"].thinking_config
    assert tk.thinking_budget == 0


def test_25_familie_behaelt_temperature_null():
    # Determinismus-Pin: die 2.5-Familie sendet weiterhin temperature=0
    # (nur die 3er-Generation laesst temperature weg).
    stub = _StubClient([_Antwort("ok")])
    from bc1_core.gespraech import TurnKontext
    GeminiLLM(client=stub, modell="gemini-2.5-flash").antworte(
        TurnKontext("m", (), "F?", False, False))
    assert stub.models.aufrufe[0]["config"].temperature == 0


def test_thinking_level_low_fuer_3er_strich_praefix():
    # Legacy-Schreibweise "gemini-3-…": gleiche 3er-Generation, gleiche
    # Konfig wie die Punkt-Schreibweise (LOW; MINIMAL lehnt die API ab —
    # ersetzt den frueheren MINIMAL-Pin, API-Doku-Stand 23.08.).
    stub = _StubClient([_Antwort("ok")])
    from bc1_core.gespraech import TurnKontext
    GeminiLLM(client=stub, modell="gemini-3-flash").antworte(
        TurnKontext("m", (), "F?", False, False))
    tk = stub.models.aufrufe[0]["config"].thinking_config
    assert tk.thinking_level == types.ThinkingLevel.LOW


def test_3_punkt_familie_level_low_ohne_temperature():
    # API-Doku 3.7 (23.08.): MINIMAL "returns an error" (nur low|medium|high),
    # Migrationsanleitung verlangt "Strip temperature" fuer die 3er-Generation.
    stub = _StubClient([_Antwort("ok")])
    from bc1_core.gespraech import TurnKontext
    GeminiLLM(client=stub, modell="gemini-3.7-flash").antworte(
        TurnKontext("m", (), "F?", False, False))
    konfig = stub.models.aufrufe[0]["config"]
    assert konfig.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert konfig.temperature is None


def test_unbekannte_modellfamilie_wirft_klaren_fehler():
    with pytest.raises(RuntimeError, match="keine gepinnte Thinking-Konfiguration"):
        _llm([], modell="gemma-7b")


def test_ohne_key_und_ohne_client_wirft_festen_text(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as fehler:
        GeminiLLM()
    assert str(fehler.value) == KEY_FEHLT


def test_stub_client_braucht_keinen_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _llm([])  # kein Raise: Key-Prüfung nur ohne injizierten Client


def test_nur_whitespace_key_wirft_festen_text(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    with pytest.raises(RuntimeError) as fehler:
        GeminiLLM()
    assert str(fehler.value) == KEY_FEHLT


def test_echter_client_pinnt_timeout_und_keine_retries(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SENTINEL-TESTKEY-123")
    erfasst = {}

    def fake_client(**kwargs):
        erfasst.update(kwargs)
        return _StubClient([])

    import bc1_service.gemini_llm as modul
    monkeypatch.setattr(modul.genai, "Client", fake_client)
    GeminiLLM()
    ho = erfasst["http_options"]
    # SDK-Doku: timeout in MILLISEKUNDEN; attempts inkl. Erstversuch.
    assert ho.timeout == 30_000
    assert ho.retry_options.attempts == 1


def test_echter_client_bekommt_api_key_explizit(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SENTINEL-TESTKEY-123")
    erfasst = {}

    def fake_client(**kwargs):
        erfasst.update(kwargs)
        return _StubClient([])

    import bc1_service.gemini_llm as modul
    monkeypatch.setattr(modul.genai, "Client", fake_client)
    GeminiLLM()
    assert erfasst["api_key"] == "SENTINEL-TESTKEY-123"


def test_429_neutrale_diagnose_genau_ein_aufruf_kein_sentinel(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SENTINEL-TESTKEY-123")
    stub = _StubClient([errors.ClientError(429, {"error": {"message": "quota"}})])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(RuntimeError) as fehler:
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))
    assert "Kontingent/Rate-Limit" in str(fehler.value)
    assert "SENTINEL-TESTKEY-123" not in str(fehler.value)
    assert len(stub.models.aufrufe) == 1


def test_429_sentinel_nicht_in_exception_kette():
    stub = _StubClient([
        errors.ClientError(429, {"error": {"message": "SENTINEL-CHAIN-XYZ"}})
    ])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(RuntimeError) as fehler:
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))
    volltext = "".join(traceback.format_exception(
        type(fehler.value), fehler.value, fehler.value.__traceback__))
    assert "SENTINEL-CHAIN-XYZ" not in volltext


def test_andere_client_fehler_fliegen_unveraendert():
    stub = _StubClient([errors.ClientError(400, {})])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(errors.ClientError):
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))


def test_abgeschnitten_wirft():
    stub = _StubClient([_Antwort("halb", finish=types.FinishReason.MAX_TOKENS)])
    with pytest.raises(RuntimeError, match="abgeschnitten"):
        GeminiLLM(client=stub).extract("m", PAKET, None)


def test_safety_ende_wirft():
    stub = _StubClient([_Antwort("x", finish=types.FinishReason.SAFETY)])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(RuntimeError, match="nicht normal geendet"):
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))


def test_ohne_kandidaten_wirft():
    stub = _StubClient([_Antwort("x", kandidaten=False)])
    with pytest.raises(RuntimeError, match="ohne Kandidaten"):
        GeminiLLM(client=stub).extract("m", PAKET, None)


def test_prompt_sicherheitsblockade_wirft_eigenen_fehler():
    antwort = types.GenerateContentResponse(
        prompt_feedback=types.GenerateContentResponsePromptFeedback(
            block_reason=types.BlockedReason.SAFETY
        )
    )
    stub = _StubClient([antwort])
    with pytest.raises(RuntimeError, match="Prompt-Sicherheitsfilter"):
        GeminiLLM(client=stub).extract("m", PAKET, None)


def test_nur_whitespace_wirft():
    stub = _StubClient([_Antwort("   ")])
    from bc1_core.gespraech import TurnKontext
    with pytest.raises(RuntimeError, match="ohne Inhalt"):
        GeminiLLM(client=stub).antworte(TurnKontext("m", (), "F?", False, False))


def test_protokoll_konformitaet_ein_turn_durch_process_turn():
    stub = _StubClient([
        _Antwort('{"extraktionen": [{"feld": "zweck", "wert": "Automatisieren"}]}'),
        _Antwort("Notiert: Automatisieren. Fertig!"),
    ])
    antwort = process_turn(InMemoryStateStore(), GeminiLLM(client=stub),
                           PAKET, "s-gemini", "m1", "Wir wollen automatisieren")
    assert antwort["status"] == "fertig"
    assert "Automatisieren" in antwort["payload"]["abschluss_text"]
