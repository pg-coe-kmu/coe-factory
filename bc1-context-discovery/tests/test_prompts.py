"""Die geteilten Prompt-Konstanten sind ein Wire-Vertrag zwischen den
LLM-Adaptern und dem Extractor — alle Adapter importieren aus prompts.py,
damit nichts driftet."""
from bc1_core.feldtypen import FREITEXT, JA_NEIN
from bc1_core.gespraech import Erfassung, TurnKontext
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import SessionState
from bc1_service.prompts import (
    EXTRAKTIONS_SCHEMA,
    PII_HINWEIS,
    SYSTEM_EXTRAKTION,
    SYSTEM_GESPRAECH,
    extraktions_nutzer_prompt,
    gespraech_nutzer_prompt,
)


def test_extraktions_schema_ist_der_wire_vertrag():
    eintrag = EXTRAKTIONS_SCHEMA["properties"]["extraktionen"]["items"]
    assert eintrag["required"] == ["feld", "wert"]
    assert eintrag["additionalProperties"] is False
    assert EXTRAKTIONS_SCHEMA["required"] == ["extraktionen"]


def _paket_und_state(identitaetskritisch: bool = False):
    paket = UseCasePackage(
        name="prompt_test", schema_version="0.1",
        fields=(
            FieldSpec("aktiv", "Ist der Prozess aktiv?", typ=JA_NEIN),
            FieldSpec("schritt", "Welcher Teilprozess?", typ=FREITEXT,
                      identitaetskritisch=identitaetskritisch),
        ))
    state = SessionState("s1", "0.1")
    state.raw_log.append(("m1", "Start"))
    state.antworten["m1"] = {"status": "frage", "payload": {"feld": "aktiv"}}
    return paket, state


def test_extraktions_prompt_nennt_gefragte_frage_mit_antwortform():
    paket, state = _paket_und_state()
    prompt = extraktions_nutzer_prompt("Ja", paket, state)
    assert ("Gerade gestellte Frage: aktiv — Ist der Prozess aktiv? "
            "(Antwortform: ja oder nein)") in prompt


def test_extraktions_prompt_ohne_gefragtes_feld():
    paket, _ = _paket_und_state()
    prompt = extraktions_nutzer_prompt("Hallo", paket, SessionState("s1", "0.1"))
    assert "Gerade gestellte Frage" not in prompt


def test_extraktions_prompt_feldliste_hat_antwortformen():
    paket, state = _paket_und_state()
    prompt = extraktions_nutzer_prompt("Ja", paket, state)
    assert "- aktiv: Ist der Prozess aktiv? (Antwortform: ja oder nein)" in prompt
    assert "- schritt: Welcher Teilprozess? (Antwortform: Text)" in prompt


def test_extraktions_prompt_identitaetsregel_generisch():
    paket, state = _paket_und_state(identitaetskritisch=True)
    prompt = extraktions_nutzer_prompt("Ja", paket, state)
    assert ("- schritt: Welcher Teilprozess? "
            "(Antwortform: Text; Identitätsbezug)") in prompt
    assert "(Antwortform: ja oder nein; Identitätsbezug)" not in prompt
    ohne, state_ohne = _paket_und_state(identitaetskritisch=False)
    assert "Identitätsbezug" not in extraktions_nutzer_prompt("Ja", ohne, state_ohne)


def test_extraktions_prompt_gefragte_identitaetsfrage_traegt_den_zusatz():
    paket, state = _paket_und_state(identitaetskritisch=True)
    state.antworten["m1"]["payload"]["feld"] = "schritt"
    prompt = extraktions_nutzer_prompt("Ja", paket, state)
    assert ("Gerade gestellte Frage: schritt — Welcher Teilprozess? "
            "(Antwortform: Text; Identitätsbezug)") in prompt


def test_extraktions_prompt_nachricht_unveraendert():
    paket, state = _paket_und_state()
    prompt = extraktions_nutzer_prompt("Ja, [Person A] macht das.", paket, state)
    assert "Interview-Nachricht:\nJa, [Person A] macht das." in prompt
    assert prompt.endswith(
        "Gib alle Feld-Wert-Paare zurück, die diese Nachricht belegt.")


def test_system_extraktion_regeln():
    s = SYSTEM_EXTRAKTION
    assert "gerade gestellte Frage" in s
    assert "in der Antwortform des Felds" in s
    assert "Freitext und Listen: wörtlich" in s
    assert "Platzhalter unverändert" in s
    assert "Ergänze nie eine Einheit" in s
    assert "Felder mit Identitätsbezug nur, wenn" in s
    assert "Lass ein Feld weg" in s
    assert "‚?‘" in s
    assert PII_HINWEIS in s


def test_system_extraktion_nackte_zahl_unveraendert():
    s = SYSTEM_EXTRAKTION
    assert "nackte Zahl" in s
    assert "unverändert zurück" in s
    assert "ihre Bedeutung legt der Vertrag fest" in s
    # Die Häufigkeits-/Dauer-Regel verlangt keine ergänzte Einheit mehr.
    assert "mit Zeitraum bzw. Einheit, bei Anzahl" not in s
    # Die Weglass-Regel „nur mit einer Annahme umrechenbar“ erfasst sie nicht.
    assert "eine nackte Zahl gehört nicht dazu" in s


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


def test_system_gespraech_verlangt_variierte_einstiege():
    # Klang-Abnahme 23.08.: "Vielen Dank" eroeffnete bei beiden
    # Gemini-Modellen fast jeden Zug (3.6: 3/3, 3.7: 4 Vorkommen in 3 Zuegen).
    assert "Variiere die Satzanfänge" in SYSTEM_GESPRAECH
    assert "höchstens einmal im ganzen Gespräch" in SYSTEM_GESPRAECH


# F2 (opus I1 + deferiertes Finding 5): die Struktur-Regel "genau eine
# Frage" gilt nur, solange das Interview läuft — beim Abschluss ist es
# eine Zusammenfassung ohne Frage.
def test_system_gespraech_begrenzt_die_fragen_regel_auf_den_laufenden_fall():
    assert "OHNE Frage" in SYSTEM_GESPRAECH


def test_erstfrage_wird_woertlich_verlangt():
    prompt = gespraech_nutzer_prompt(_kontext(
        neu_erfasst=(Erfassung("Zweck?", "Sparen"),)))
    assert "wörtlich" in prompt
    assert "Wie oft läuft der Prozess?" in prompt
    assert "Zweck? → Sparen" in prompt


def test_nachfrage_verlangt_optionen_und_zweck():
    prompt = gespraech_nutzer_prompt(_kontext(ist_nachfrage=True))
    assert "NACHFRAGE" in prompt
    assert "Optionen vollständig" not in prompt
    assert "offen bleiben darf" in prompt
    assert "neutralen Beispiel" in prompt


def test_nachfrage_nennt_antwortform_und_bittet_darum():
    prompt = gespraech_nutzer_prompt(_kontext(
        ist_nachfrage=True, antwortform="ja oder nein"))
    assert "Antwortform: ja oder nein" in prompt
    assert "mit Ja oder Nein" in prompt
    assert "dasselbe wie in der Kernfrage" in prompt


def test_nachfrage_ohne_antwortform_hat_keinen_antwortform_satz():
    prompt = gespraech_nutzer_prompt(_kontext(ist_nachfrage=True))
    assert "Antwortform" not in prompt
    assert "mit Ja oder Nein" not in prompt


def test_nachfrage_skala_haelt_richtung():
    prompt = gespraech_nutzer_prompt(_kontext(
        ist_nachfrage=True, antwortform="eine Ziffer von 1 bis 5"))
    assert "Bei einer Skala bleiben Richtung und Endpunkte" in prompt


def test_nachfrage_nennt_nur_optionen_der_antwortform():
    prompt = gespraech_nutzer_prompt(_kontext(
        ist_nachfrage=True, antwortform="ja oder nein"))
    assert ("Nenne nur Optionen, die die Antwortform vorgibt — ein ‚oder‘ in "
            "einer Ja/Nein-Frage ist keine Auswahl") in prompt


def test_abschluss_prompt_traegt_uebersicht_und_offenes():
    prompt = gespraech_nutzer_prompt(_kontext(
        naechste_frage=None, ist_abschluss=True,
        profil_uebersicht=(Erfassung("Wie oft?", "600"),),
        offene_fragen=("Wer ist verantwortlich?",)))
    assert "Wie oft? → 600" in prompt
    assert "Wer ist verantwortlich?" in prompt


# F2 (opus I1): der Abschluss-Prompt darf keine weitere Frage erzwingen —
# das Interview ist beendet, der Nutzer-Prompt muss das explizit sagen.
def test_abschluss_prompt_erzwingt_keine_weitere_frage():
    prompt = gespraech_nutzer_prompt(_kontext(
        naechste_frage=None, ist_abschluss=True))
    assert "KEINE weitere Frage" in prompt


# F5 (opus M4): "unklar oder ungültig" unterstellt eine geprüfte Antwort —
# der Nachfrage-Fall feuert aber auch nach bloßen Rückfragen ohne jeden
# Wert. Ehrliche Formulierung: es liegt schlicht noch kein Wert vor.
def test_nachfrage_prompt_unterstellt_keine_ungueltige_antwort():
    prompt = gespraech_nutzer_prompt(_kontext(ist_nachfrage=True))
    assert "kein verwertbarer Wert vor" in prompt
    assert "unklar oder ungültig" not in prompt


def test_system_prompts_erklaeren_die_pii_platzhalter():
    # B2: der Anbieter sieht nur Platzhalter — wörtlich übernehmen, nie auflösen, nie raten.
    for prompt in (SYSTEM_EXTRAKTION, SYSTEM_GESPRAECH):
        assert "[Person A]" in prompt
        assert "wörtlich" in prompt
        assert "nie auf" in prompt
