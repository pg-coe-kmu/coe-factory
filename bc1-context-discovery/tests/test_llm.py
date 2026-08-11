from bc1_core.types import SessionState
from bc1_core.package import TOY_PROZESS
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.gespraech import Erfassung, TurnKontext

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

def test_fake_antworte_enthaelt_werte_und_kernfrage_woertlich():
    kontext = TurnKontext(
        nutzer_nachricht="msg",
        neu_erfasst=(Erfassung("Wie oft?", "600"), Erfassung("Zweck?", "Sparen")),
        naechste_frage="Wie lange dauert es?",
        ist_nachfrage=False, ist_abschluss=False)
    text = FakeLLM().antworte(kontext)
    assert "600" in text and "Sparen" in text
    assert "Wie lange dauert es?" in text


def test_fake_antworte_abschluss_mit_uebersicht_und_offenem():
    kontext = TurnKontext(
        nutzer_nachricht="msg", neu_erfasst=(),
        naechste_frage=None, ist_nachfrage=False, ist_abschluss=True,
        profil_uebersicht=(Erfassung("Wie oft?", "600"),),
        offene_fragen=("Wer ist verantwortlich?",))
    text = FakeLLM().antworte(kontext)
    assert "600" in text
    assert "Wer ist verantwortlich?" in text
