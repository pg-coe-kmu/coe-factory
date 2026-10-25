"""B7 Teil 2 (#266): Betriebsprotokoll des Kerns — nur Kennungen, Feldnamen, Klassen, Zahlen."""
import logging
import re

from bc1_core.core import process_turn
from bc1_core.llm import FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore

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
