"""Feste Sperren gegen Regelverstöße der KI (Spec-Antwortformen Abschnitt 2).

Ein KI-Kandidat wird verworfen, wenn er der Originalnachricht widerspricht:
(a) Identitätsbezug, (b) Zeitraum/Einheit, (c) Fragebezug, (d) fremde Bezugsgröße
(Spec-Sperre-d-Bezugsgroesse.md).
"""
import pytest

from bc1_core.extractor import extract_and_merge
from bc1_core.feldtypen import ANZAHL, AUSWAHL, LISTE, MINUTEN, ZAHL
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


def test_identitaet_verneinte_option_wird_verworfen():
    # Fix-Welle 4 V1: Die Nachricht nennt den Namen, schliesst die Option aber aus.
    state = _spiele(_paket_identitaet(),
                    "Nicht Anfrage erfassen, sondern den zweiten Schritt",
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert "teilprozess" not in state.values


@pytest.mark.parametrize("nachricht", [
    "Vielleicht Anfrage erfassen",
    "Eventuell Anfrage erfassen",
    "Evtl. Anfrage erfassen",
    "Wahrscheinlich Anfrage erfassen",
    "Vermutlich Anfrage erfassen",
    "Anfrage erfassen oder Angebot prüfen",
    "Keine Anfrage erfassen",
    "Nein, Anfrage erfassen",
    "Anfrage erfassen, sondern etwas anderes",
    "Ich bin unsicher: Anfrage erfassen",
    "Ich weiss nicht, Anfrage erfassen",
    "Ich weiß nicht, Anfrage erfassen",
])
def test_identitaet_unsichere_oder_verneinte_nennung_wird_verworfen(nachricht):
    # Fix-Welle 4 V1: Vorkommen ist keine Festlegung.
    state = _spiele(_paket_identitaet(), nachricht,
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert "teilprozess" not in state.values


def test_identitaet_name_ohne_vergleichsschluessel_zaehlt_nicht_als_nennung():
    # Fix-Welle 4 V2: Der Name „...“ hat einen leeren Schluessel und passte sonst ueberall.
    paket = UseCasePackage(
        name="sperre_a_leer", schema_version="0.1",
        fields=(FieldSpec("teilprozess", "Welcher Teilprozess?",
                          typ=AUSWAHL("KP-01.TP-1", "KP-01.TP-2",
                                      namen={"KP-01.TP-1": "...",
                                             "KP-01.TP-2": "Angebot prüfen"}),
                          identitaetskritisch=True),))
    state = _spiele(paket, "der zweite Schritt, bitte",
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert "teilprozess" not in state.values


def _paket_fragebezug():
    return UseCasePackage(
        name="sperre_c", schema_version="0.1",
        fields=(FieldSpec("haeufigkeit", "Wie oft?", typ=ZAHL),
                FieldSpec("faelle", "Wie viele Fälle je Durchlauf?", typ=ANZAHL)))


def test_fragebezug_ohne_gueltigen_wert_fuers_gefragte_feld_verwirft_andere_felder():
    # „5 pro Woche“ auf die Fallzahl-Frage darf nicht die Häufigkeit ändern.
    paket = _paket_fragebezug()
    state = _spiele(paket, "5 pro Woche",
                    [ExtractionCandidate("haeufigkeit", "5 pro Woche")],
                    gefragt=paket.field("faelle"))
    assert "haeufigkeit" not in state.values


def test_fragebezug_mit_gueltigem_wert_fuers_gefragte_feld_gelten_alle_kandidaten():
    # (Regression) Beantwortet die KI die gestellte Frage, wirken auch ihre anderen Felder.
    paket = _paket_fragebezug()
    state = _spiele(paket, "5 Fälle, und das 5 pro Woche",
                    [ExtractionCandidate("haeufigkeit", "5 pro Woche"),
                     ExtractionCandidate("faelle", "5")],
                    gefragt=paket.field("faelle"))
    assert state.values["faelle"].value == "5"
    assert state.values["haeufigkeit"].value == "260"


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


def test_einheit_wortteil_stundung_ist_keine_einheit():
    # Fix-Welle 4 V3: „Stundung“ enthält „stund“, nennt aber keine Zeiteinheit.
    state = _spiele(_paket_wert(MINUTEN),
                    "Die Bearbeitung der Stundung dauert ca. 40",
                    [ExtractionCandidate("wert", "40 Minuten")])
    assert "wert" not in state.values


def test_einheit_viertelstunde_in_der_nachricht_erlaubt_den_ki_wert():
    state = _spiele(_paket_wert(MINUTEN), "eine Viertelstunde",
                    [ExtractionCandidate("wert", "15 Minuten")])
    assert state.values["wert"].value == "15"


def test_zeitraum_wortteil_mittwoch_ist_kein_zeitraum():
    # Fix-Welle 4 V3: „Mittwoch“ enthält „woch“, nennt aber keinen Zeitraum.
    state = _spiele(_paket_wert(ZAHL), "2x am Mittwoch",
                    [ExtractionCandidate("wert", "2 pro Jahr")])
    assert "wert" not in state.values


def test_einheit_kuerzel_direkt_an_der_zahl_erlaubt_den_ki_wert():
    # (Regression) V3: „1,5h“ und „45min“ nennen die Einheit direkt an der Zahl.
    state = _spiele(_paket_wert(MINUTEN), "1,5h",
                    [ExtractionCandidate("wert", "90 Minuten")])
    assert state.values["wert"].value == "90"
    state = _spiele(_paket_wert(MINUTEN), "45min",
                    [ExtractionCandidate("wert", "45 Minuten")])
    assert state.values["wert"].value == "45"


def test_identitaet_ordinalzahl_ohne_kennung_oder_namen_wird_verworfen():
    state = _spiele(_paket_identitaet(), "der zweite Schritt",
                    [ExtractionCandidate("teilprozess", "KP-01.TP-1")])
    assert "teilprozess" not in state.values


def test_bezug_pro_fall_verwirft_den_ki_wert_fuer_die_dauer():
    # Spec Sperre (d): Ob ein Lauf genau einen Fall bearbeitet, steht nicht fest; „30 Minuten“
    # je Lauf wäre eine Annahme (Prüfwerkzeug 30.10., Szenario 4).
    state = _spiele(_paket_wert(MINUTEN), "30 Minuten pro Fall",
                    [ExtractionCandidate("wert", "30 Minuten")])
    assert "wert" not in state.values


def test_bezug_pro_lead_verwirft_den_ki_wert_fuer_die_haeufigkeit():
    # Sperre (b) lässt ihn durch (die Nachricht nennt „Monat“); 5 je Lead sind keine
    # 5 Durchläufe im Monat.
    state = _spiele(_paket_wert(ZAHL), "5 pro Lead im Monat",
                    [ExtractionCandidate("wert", "5 pro Monat")])
    assert "wert" not in state.values


def _paket_haeufigkeit_dauer():
    return UseCasePackage(
        name="sperre_d", schema_version="0.1",
        fields=(FieldSpec("haeufigkeit", "Wie oft läuft der Prozess?", typ=ZAHL),
                FieldSpec("dauer", "Wie lange dauert ein Lauf?", typ=MINUTEN)))


def test_bezug_zeitraum_und_dauer_in_einer_nachricht_gelten_beide():
    # (Regression) Spec Sperre (d), E1: So schreiben es die Testprofile und Demo-Läufe.
    state = _spiele(_paket_haeufigkeit_dauer(), "15 pro Monat, 3 Stunden",
                    [ExtractionCandidate("haeufigkeit", "15 pro Monat"),
                     ExtractionCandidate("dauer", "3 Stunden")])
    assert state.values["haeufigkeit"].value == "180"
    assert state.values["dauer"].value == "180"


def test_bezug_gilt_fuer_die_ganze_nachricht():
    # Spec Sperre (d), E2 (bewusst hingenommen): keine Zuordnung je Zahl, „je Fall“ kostet
    # auch die Häufigkeit eine Nachfrage.
    state = _spiele(_paket_haeufigkeit_dauer(), "2 mal pro Woche, je Fall 30 Minuten",
                    [ExtractionCandidate("haeufigkeit", "2 pro Woche"),
                     ExtractionCandidate("dauer", "30 Minuten")])
    assert "haeufigkeit" not in state.values
    assert "dauer" not in state.values


def test_bezug_im_gefragten_feld_verwirft_auch_die_anderen_felder():
    # (Regression) Spec Sperre (d), E2 mit Sperre (c): Ist das gesperrte Feld das gefragte,
    # gilt kein anderer KI-Kandidat dieses Turns. Hält die Reihenfolge (d) vor (c) fest.
    paket = UseCasePackage(
        name="sperre_d_c", schema_version="0.1",
        fields=(FieldSpec("dauer", "Wie lange dauert ein Lauf?", typ=MINUTEN),
                FieldSpec("systeme", "Welche Systeme?", typ=LISTE)))
    state = _spiele(paket, "In SAP, 30 Minuten pro Fall",
                    [ExtractionCandidate("dauer", "30 Minuten"),
                     ExtractionCandidate("systeme", "SAP")],
                    gefragt=paket.field("dauer"))
    assert state.values == {}


def test_bezug_laesst_typen_ohne_merkmal_unberuehrt():
    # (Regression) Die Sperre hängt am Typ (`prueft_bezug`), nicht am Wort „pro“: eine
    # Anzahl „pro Lead“ bleibt.
    state = _spiele(_paket_wert(ANZAHL), "5 pro Lead",
                    [ExtractionCandidate("wert", "5")])
    assert state.values["wert"].value == "5"


def test_bezug_kurzform_laeuft_wie_bisher():
    # (Regression) Kurze Antworten gehen ohne KI ins gefragte Feld. Die Kurzform-Grammatik
    # kennt nach „pro“/„je“ nur einen Zeitraum, eine fremde Bezugsgröße erreicht sie nie.
    paket = _paket_haeufigkeit_dauer()
    state = _spiele(paket, "2 mal pro Woche", [],
                    gefragt=paket.field("haeufigkeit"))
    assert state.values["haeufigkeit"].value == "104"
