from bc1_core.package import UseCasePackage, FieldSpec
from bc1_core.store import InMemoryStateStore
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.core import process_turn

# Zweites, bewusst anderes Paket (anderer Name, andere Felder)
RECHNUNG = UseCasePackage(
    name="rechnungspruefung",
    schema_version="9.9",
    fields=(FieldSpec("lieferant", "Wer ist der Lieferant?"),
            FieldSpec("betrag", "Welcher Betrag?",
                      validator=lambda v: any(c.isdigit() for c in v))),
)

def test_core_handles_a_different_package_unchanged():
    store = InMemoryStateStore()
    llm = FakeLLM({"x": [ExtractionCandidate("lieferant", "ACME"),
                         ExtractionCandidate("betrag", "500 EUR")]})
    r = process_turn(store, llm, RECHNUNG, "s9", "m1", "x")
    # Kern kennt RECHNUNG nicht vorab -> trotzdem korrekt, ohne Sonderlogik
    assert r["status"] == "fertig"
    assert r["payload"]["schema_version"] == "9.9"
    assert r["payload"]["vollstaendigkeit"] == 1.0
    assert set(r["payload"]["felder"]) == {"lieferant", "betrag"}

def test_run_scripted_liefert_eine_antwort_pro_nachricht():
    from bc1_core.cli import run_scripted
    llm = FakeLLM({"x": [ExtractionCandidate("lieferant", "ACME")],
                   "y": [ExtractionCandidate("betrag", "500 EUR")]})
    out = run_scripted(RECHNUNG, llm, [("m1", "x"), ("m2", "y")])
    assert len(out) == 2
    assert out[0]["status"] == "frage"
    assert out[1]["status"] == "fertig"

def test_run_scripted_startet_mit_frischem_zustand():
    from bc1_core.cli import run_scripted
    llm = FakeLLM({"x": [ExtractionCandidate("lieferant", "ACME")],
                   "y": [ExtractionCandidate("betrag", "500 EUR")]})
    run_scripted(RECHNUNG, llm, [("m1", "x")])
    out = run_scripted(RECHNUNG, llm, [("m1", "y")])   # gleiche message_id!
    assert out[0]["payload"]["feld"] == "lieferant"    # kein Zustand aus Lauf 1
