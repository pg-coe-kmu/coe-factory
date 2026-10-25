"""B7 Teil 2 (#266): Betriebsprotokoll des Kerns — nur Kennungen, Feldnamen, Klassen, Zahlen."""
import logging
import re
import time

import pytest

from bc1_core.confidence import confidence_check
from bc1_core.core import process_turn
from bc1_core.dialog import decide_next
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_core.protokoll import aktuelle_korrelation
from bc1_core.store import InMemoryStateStore
from bc1_core.types import FieldStatus, FieldValue, SessionState

MANDANT = "11111111-1111-1111-1111-111111111111"
KI_ZEILE = re.compile(
    r"^ki_aufruf korrelation=- art=(?P<art>extraktion|antwort) ergebnis=ok dauer_ms=\d+$")


def _kern(caplog) -> list:
    return [r for r in caplog.records if r.name == "bc1.kern"]


def test_ki_aufrufe_werden_mit_dauer_protokolliert(caplog):
    caplog.set_level(logging.INFO, logger="bc1.kern")
    process_turn(InMemoryStateStore(), FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo",
                 company_id=MANDANT)
    zeilen = _kern(caplog)
    treffer = [KI_ZEILE.match(r.getMessage()) for r in zeilen]
    assert all(treffer), [r.getMessage() for r in zeilen]
    assert [t["art"] for t in treffer] == ["extraktion", "antwort"]
    assert all(r.levelno == logging.INFO for r in zeilen)


class _LangsameExtraktion(FakeLLM):
    def extract(self, message, package, state):
        time.sleep(0.02)
        return super().extract(message, package, state)


def test_ki_dauer_misst_den_aufruf(caplog):
    # Gesamtprüfung M2: die Zeile muss die echte Dauer tragen, nicht nur eine Zahl.
    caplog.set_level(logging.INFO, logger="bc1.kern")
    process_turn(InMemoryStateStore(), _LangsameExtraktion(), TOY_PROZESS, "s1", "m1",
                 "hallo", company_id=MANDANT)
    extraktion = KI_ZEILE.match(_kern(caplog)[0].getMessage())
    assert extraktion["art"] == "extraktion"
    assert int(re.search(r"dauer_ms=(\d+)", extraktion.string)[1]) >= 20


GEHEIM = "Geheimwort Nordlicht 4711"


class _AntwortFaelltAus(FakeLLM):
    def antworte(self, kontext):
        raise RuntimeError(GEHEIM)


def test_ki_fehler_wird_mit_klasse_und_ohne_text_protokolliert(caplog):
    caplog.set_level(logging.DEBUG)
    antwort = process_turn(InMemoryStateStore(), _AntwortFaelltAus(), TOY_PROZESS, "s1",
                           "m1", "hallo", company_id=MANDANT)
    assert antwort["status"] == "fehler_fortsetzbar"
    warnungen = [(r.levelno, r.getMessage()) for r in _kern(caplog)
                 if r.levelno >= logging.WARNING]
    assert len(warnungen) == 2, warnungen
    assert re.fullmatch(r"ki_aufruf korrelation=- art=antwort ergebnis=fehler dauer_ms=\d+",
                        warnungen[0][1])
    assert warnungen[1][1] == "verarbeitung_fehlgeschlagen korrelation=- klasse=RuntimeError"
    assert all(stufe == logging.WARNING for stufe, _ in warnungen)
    assert not any(GEHEIM in r.getMessage() for r in caplog.records)


@pytest.fixture
def korrelation():
    # Wie /turn sie setzt; so prüft jeder Test, dass die Zeile die Kennung liest.
    token = aktuelle_korrelation.set("k-1")
    yield "k-1"
    aktuelle_korrelation.reset(token)


def _zeilen(caplog, ereignis: str) -> list[str]:
    return [r.getMessage() for r in _kern(caplog) if r.getMessage().startswith(ereignis + " ")]


def test_ungueltiger_wert_wird_ohne_wert_protokolliert(korrelation, caplog):
    caplog.set_level(logging.DEBUG)
    # Der Validator von TOY verlangt für die Häufigkeit eine Ziffer.
    llm = FakeLLM({"x": [ExtractionCandidate("haeufigkeit", "Geheimwort Polarstern")]})
    process_turn(InMemoryStateStore(), llm, TOY_PROZESS, "s1", "m1", "x",
                 company_id=MANDANT)
    assert _zeilen(caplog, "validierung") == [
        "validierung korrelation=k-1 feld=haeufigkeit ergebnis=ungueltig"]
    assert not any("Polarstern" in r.getMessage() for r in caplog.records)


def test_widerspruch_wird_als_unklar_protokolliert(korrelation, caplog):
    caplog.set_level(logging.INFO, logger="bc1.kern")
    llm = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")],
                   "b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    store = InMemoryStateStore()
    for mid, text in (("m1", "a"), ("m2", "b")):
        process_turn(store, llm, TOY_PROZESS, "s1", mid, text, company_id=MANDANT)
    # Über beide Turns: der gültige erste Wert erzeugt keine Zeile.
    assert _zeilen(caplog, "validierung") == [
        "validierung korrelation=k-1 feld=prozess_name ergebnis=unklar"]


def test_feld_am_nachfrage_limit_wird_einmal_protokolliert(korrelation, caplog):
    caplog.set_level(logging.INFO, logger="bc1.kern")
    state = SessionState("s1", TOY_PROZESS.schema_version)
    state.values["prozess_name"] = FieldValue(value="Freigabe", status=FieldStatus.GUELTIG)
    state.values["ausloeser"] = FieldValue(value="Antrag", status=FieldStatus.GUELTIG)
    state.values["haeufigkeit"] = FieldValue(value="oft", status=FieldStatus.UNGUELTIG,
                                             attempts=2)
    # Zweimal: ein aufgegebenes Feld besucht die Cap-Schleife nicht erneut.
    for _ in range(2):
        decide_next(state, TOY_PROZESS, confidence_check(state, TOY_PROZESS))
    assert _zeilen(caplog, "feld_ungeloest") == [
        "feld_ungeloest korrelation=k-1 feld=haeufigkeit grund=nachfrage_limit_erreicht"]


def test_runden_limit_protokolliert_jedes_aufgegebene_feld(korrelation, caplog):
    caplog.set_level(logging.INFO, logger="bc1.kern")
    state = SessionState("s1", TOY_PROZESS.schema_version)
    state.rounds = TOY_PROZESS.max_rounds
    state.values["prozess_name"] = FieldValue(value="Freigabe", status=FieldStatus.GUELTIG)
    decide_next(state, TOY_PROZESS, confidence_check(state, TOY_PROZESS))
    assert _zeilen(caplog, "feld_ungeloest") == [
        "feld_ungeloest korrelation=k-1 feld=ausloeser grund=runden_limit_erreicht",
        "feld_ungeloest korrelation=k-1 feld=haeufigkeit grund=runden_limit_erreicht"]
