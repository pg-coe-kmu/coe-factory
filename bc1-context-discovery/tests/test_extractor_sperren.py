"""Feste Sperren gegen Regelverstöße der KI (Spec-Antwortformen Abschnitt 2).

Ein KI-Kandidat wird verworfen, wenn er der Originalnachricht widerspricht:
(a) Identitätsbezug, (b) Zeitraum/Einheit, (c) Fragebezug.
"""
from bc1_core.extractor import extract_and_merge
from bc1_core.feldtypen import AUSWAHL, MINUTEN, ZAHL
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import SessionState


class _KI(FakeLLM):
    """Liefert eine feste Kandidatenliste."""
    def __init__(self, kandidaten):
        super().__init__()
        self._kandidaten = kandidaten

    def extract(self, message, package, state):
        return list(self._kandidaten)


_TEILPROZESS = FieldSpec(
    "teilprozess", "Welcher Teilprozess?",
    typ=AUSWAHL("KP-01.TP-1", "KP-01.TP-2",
                namen={"KP-01.TP-1": "Anfrage erfassen",
                       "KP-01.TP-2": "Angebot prüfen"}),
    identitaetskritisch=True)


def _spiele(paket, nachricht, kandidaten, gefragt=None):
    state = SessionState("s1", "0.1")
    extract_and_merge(state, nachricht, "m1", paket, _KI(kandidaten),
                      gefragt=gefragt)
    return state


def _paket_identitaet():
    return UseCasePackage(name="sperre_a", schema_version="0.1",
                          fields=(_TEILPROZESS,))


def test_identitaet_nennt_die_nachricht_den_namen_wird_der_wert_angenommen():
    # (Regression) „Anfrage erfassen“ ist der Name von KP-01.TP-1.
    state = _spiele(_paket_identitaet(), "Wir meinen die Anfrage erfassen",
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert state.values["teilprozess"].value == "KP-01.TP-1"


def test_identitaet_kennung_im_satz_wird_angenommen():
    # (Regression)
    state = _spiele(_paket_identitaet(), "Es geht um KP-01.TP-1, bitte.",
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert state.values["teilprozess"].value == "KP-01.TP-1"


def test_identitaet_kennung_und_name_einer_anderen_option_wird_verworfen():
    state = _spiele(_paket_identitaet(), "KP-01.TP-1 = Angebot prüfen",
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert "teilprozess" not in state.values


def test_identitaet_name_mit_fragezeichen_wird_verworfen():
    state = _spiele(_paket_identitaet(), "Anfrage erfassen?",
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert "teilprozess" not in state.values


def _paket_wert(typ):
    return UseCasePackage(name="sperre_b", schema_version="0.1",
                          fields=(FieldSpec("wert", "Wie viel?", typ=typ),))


def test_zeitraum_ohne_nennung_in_der_nachricht_wird_verworfen():
    # „2x“ ist keine Zeitangabe: „2 pro Jahr“ wäre erfunden.
    state = _spiele(_paket_wert(ZAHL), "2x",
                    [ExtractionCandidate("wert", "2 pro Jahr")])
    assert "wert" not in state.values


def test_einheit_ohne_nennung_in_der_nachricht_wird_verworfen():
    # „ca. 40“ nennt keine Einheit: „40 Minuten“ wäre erfunden.
    state = _spiele(_paket_wert(MINUTEN), "ca. 40",
                    [ExtractionCandidate("wert", "40 Minuten")])
    assert "wert" not in state.values


def test_einheit_halbe_stunde_in_der_nachricht_erlaubt_den_ki_wert():
    # (Regression)
    state = _spiele(_paket_wert(MINUTEN), "eine halbe Stunde",
                    [ExtractionCandidate("wert", "30 Minuten")])
    assert state.values["wert"].value == "30"


def test_zeitraum_jeden_zweiten_monat_erlaubt_sechs_pro_jahr():
    # (Regression) Der Zeitraum in der Nachricht (Monat) und im Wert (Jahr) dürfen sich
    # unterscheiden — es zählt, dass die Nachricht überhaupt einen Zeitraum nennt.
    state = _spiele(_paket_wert(ZAHL), "jeden 2. Monat",
                    [ExtractionCandidate("wert", "6 pro Jahr")])
    assert state.values["wert"].value == "6"


def test_zeitraum_20_leads_pro_woche_ergibt_1040():
    # (Regression)
    state = _spiele(_paket_wert(ZAHL), "20 Leads pro Woche",
                    [ExtractionCandidate("wert", "20 pro Woche")])
    assert state.values["wert"].value == "1040"


def test_zeitraum_wochentlich_in_der_nachricht_erlaubt_den_ki_wert():
    state = _spiele(_paket_wert(ZAHL), "wöchentlich",
                    [ExtractionCandidate("wert", "1 pro Woche")])
    assert state.values["wert"].value == "52"


def test_identitaet_ordinalzahl_ohne_kennung_oder_namen_wird_verworfen():
    state = _spiele(_paket_identitaet(), "der zweite Schritt",
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert "teilprozess" not in state.values
