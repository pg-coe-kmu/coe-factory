"""Die geteilten Prompt-Konstanten sind ein Wire-Vertrag zwischen den
LLM-Adaptern und dem Extractor — beide Adapter importieren aus prompts.py,
damit nichts driftet."""
from bc1_core.gespraech import Erfassung, TurnKontext
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    SYSTEM_EXTRAKTION,
    SYSTEM_GESPRAECH,
    gespraech_nutzer_prompt,
)


def test_extraktions_schema_ist_der_wire_vertrag():
    eintrag = EXTRAKTIONS_SCHEMA["properties"]["extraktionen"]["items"]
    assert eintrag["required"] == ["feld", "wert"]
    assert eintrag["additionalProperties"] is False
    assert EXTRAKTIONS_SCHEMA["required"] == ["extraktionen"]


def test_system_prompts_sind_die_bekannten_deutschen_prompts():
    assert "extrahierst" in SYSTEM_EXTRAKTION


def _kontext(**kwargs) -> TurnKontext:
    basis = dict(nutzer_nachricht="msg", neu_erfasst=(),
                 naechste_frage="Wie oft läuft der Prozess?",
                 ist_nachfrage=False, ist_abschluss=False)
    basis.update(kwargs)
    return TurnKontext(**basis)


def test_system_gespraech_pinnt_die_kernregeln():
    assert "NUR die gelieferten Werte" in SYSTEM_GESPRAECH
    assert "NIE technische Feldnamen" in SYSTEM_GESPRAECH
    # Entscheidung 6 (10.08.): Beispiele nur bei Rück-/Nachfragen,
    # Erstfragen bleiben beispielfrei (Anker-Effekt).
    assert "in Erstfragen nie ein Beispiel" in SYSTEM_GESPRAECH


def test_erstfrage_wird_woertlich_verlangt():
    prompt = gespraech_nutzer_prompt(_kontext(
        neu_erfasst=(Erfassung("Zweck?", "Sparen"),)))
    assert "wörtlich" in prompt
    assert "Wie oft läuft der Prozess?" in prompt
    assert "Zweck? → Sparen" in prompt


def test_nachfrage_verlangt_optionen_und_zweck():
    prompt = gespraech_nutzer_prompt(_kontext(ist_nachfrage=True))
    assert "NACHFRAGE" in prompt
    assert "Optionen vollständig" in prompt
    assert "offen bleiben darf" in prompt
    assert "neutralen Beispiel" in prompt


def test_abschluss_prompt_traegt_uebersicht_und_offenes():
    prompt = gespraech_nutzer_prompt(_kontext(
        naechste_frage=None, ist_abschluss=True,
        profil_uebersicht=(Erfassung("Wie oft?", "600"),),
        offene_fragen=("Wer ist verantwortlich?",)))
    assert "Wie oft? → 600" in prompt
    assert "Wer ist verantwortlich?" in prompt
