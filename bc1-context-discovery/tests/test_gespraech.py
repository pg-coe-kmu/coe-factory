"""TurnKontext: der Kern befüllt, das LLM gibt nur wieder (Spec Gesprächsschicht).

Felder werden NUR über ihre Kernfrage identifiziert — technische Feldnamen
dürfen den Kontext nie erreichen (Leak-Schutz per Konstruktion).
"""
from bc1_core.confidence import confidence_check
from bc1_core.gespraech import (
    Erfassung,
    baue_turn_kontext,
    werte_schnappschuss,
)
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import Candidate, FieldStatus, FieldValue, SessionState

PAKET = UseCasePackage(
    name="kontext_test", schema_version="0.1",
    fields=(FieldSpec("zweck", "Was ist der Zweck?"),
            FieldSpec("menge", "Wie viele pro Jahr?"),
            FieldSpec("notiz", "Noch etwas?", required=False)))


def _state(**werte: FieldValue) -> SessionState:
    state = SessionState("s1", "0.1")
    state.values.update(werte)
    return state


def test_neu_erfasst_enthaelt_nur_in_diesem_turn_gueltig_gewordenes():
    state = _state(
        zweck=FieldValue(value="Automatisieren", status=FieldStatus.GUELTIG),
        menge=FieldValue(value="600", status=FieldStatus.UNKLAR,
                         candidates=[Candidate("1200", "m1")]))
    kontext = baue_turn_kontext("msg", {}, state, PAKET,
                                confidence_check(state, PAKET), "menge", False)
    assert kontext.neu_erfasst == (Erfassung("Was ist der Zweck?", "Automatisieren"),)


def test_neu_erfasst_erkennt_wertaenderung_und_ignoriert_unveraendertes():
    state = _state(
        zweck=FieldValue(value="Neu", status=FieldStatus.GUELTIG),
        menge=FieldValue(value="600", status=FieldStatus.GUELTIG))
    vorher = {"zweck": "Alt", "menge": "600"}
    kontext = baue_turn_kontext("msg", vorher, state, PAKET,
                                confidence_check(state, PAKET), "notiz", False)
    assert kontext.neu_erfasst == (Erfassung("Was ist der Zweck?", "Neu"),)


def test_werte_schnappschuss_nur_gueltige():
    state = _state(
        zweck=FieldValue(value="X", status=FieldStatus.GUELTIG),
        menge=FieldValue(value="kaputt", status=FieldStatus.UNGUELTIG))
    assert werte_schnappschuss(state) == {"zweck": "X"}


def test_nachfrage_flag_ab_zweitem_versuch():
    state = _state(menge=FieldValue(attempts=2))
    kontext = baue_turn_kontext("msg", {}, state, PAKET,
                                confidence_check(state, PAKET), "menge", False)
    assert kontext.ist_nachfrage is True
    assert kontext.naechste_frage == "Wie viele pro Jahr?"

    frisch = _state(menge=FieldValue(attempts=1))
    kontext2 = baue_turn_kontext("msg", {}, frisch, PAKET,
                                 confidence_check(frisch, PAKET), "menge", False)
    assert kontext2.ist_nachfrage is False


def test_abschluss_traegt_uebersicht_und_offene_fragen():
    state = _state(
        zweck=FieldValue(value="Automatisieren", status=FieldStatus.GUELTIG),
        menge=FieldValue(value=None, status=FieldStatus.UNGELOEST))
    conf = confidence_check(state, PAKET)
    kontext = baue_turn_kontext("msg", {}, state, PAKET, conf, None, True)
    assert kontext.ist_abschluss is True
    assert kontext.naechste_frage is None
    assert kontext.profil_uebersicht == (
        Erfassung("Was ist der Zweck?", "Automatisieren"),)
    assert kontext.offene_fragen == ("Wie viele pro Jahr?",)


def test_kontext_transportiert_keine_technischen_feldnamen():
    state = _state(zweck=FieldValue(value="X", status=FieldStatus.GUELTIG))
    kontext = baue_turn_kontext("msg", {}, state, PAKET,
                                confidence_check(state, PAKET), "menge", False)
    # Leak-Schutz per Konstruktion: nirgendwo im Kontext taucht ein
    # technischer Feldname auf — nur Kernfragen und Werte.
    assert "zweck" not in repr(kontext)
    assert "menge" not in repr(kontext)
