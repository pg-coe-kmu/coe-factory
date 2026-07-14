import json

from bc1_core.types import SessionStatus
from bc1_core.package import TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.core import process_turn

def test_first_turn_asks_first_open_field():
    store = InMemoryStateStore()
    r = process_turn(store, FakeLLM(), TOY_PROZESS, "s1", "msg-1", "hallo")
    assert r["status"] == "frage"
    assert r["payload"]["feld"] == "prozess_name"
    st = store.load("s1")
    assert st.raw_log == [("msg-1", "hallo")]   # roh geloggt
    assert st.status is SessionStatus.WARTET
    assert st.rounds == 1

def test_idempotent_replay_returns_same_response_without_double_log():
    store = InMemoryStateStore()
    llm = FakeLLM({"hallo": [ExtractionCandidate("prozess_name", "Freigabe")]})
    first = process_turn(store, llm, TOY_PROZESS, "s1", "msg-1", "hallo")
    again = process_turn(store, llm, TOY_PROZESS, "s1", "msg-1", "hallo")
    assert again == first
    st = store.load("s1")
    assert st.raw_log == [("msg-1", "hallo")]   # nicht doppelt
    assert st.rounds == 1                        # Replay zählt keine Runde

def test_full_run_reaches_fertig_with_completeness():
    store = InMemoryStateStore()
    llm = FakeLLM({
        "a": [ExtractionCandidate("prozess_name", "Freigabe")],
        "b": [ExtractionCandidate("ausloeser", "Antrag geht ein")],
        "c": [ExtractionCandidate("haeufigkeit", "100 mal")],
    })
    process_turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    process_turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
    r = process_turn(store, llm, TOY_PROZESS, "s1", "m3", "c")
    assert r["status"] == "fertig"
    assert r["payload"]["vollstaendigkeit"] == 1.0
    assert r["payload"]["schema_version"] == "0.1"
    assert r["payload"]["felder"]["prozess_name"]["wert"] == "Freigabe"
    assert r["payload"]["felder"]["prozess_name"]["status"] == "gueltig"
    assert r["payload"]["ungeloeste_felder"] == []
    assert store.load("s1").status is SessionStatus.FERTIG

# Die Antwort geht als JSON an n8n/HTTP raus — sie muss json.dumps-fähig
# sein, AUCH wenn Kandidaten (Konflikte/Korrekturen) im Profil stehen.
def test_fertig_antwort_mit_kandidaten_ist_json_faehig():
    store = InMemoryStateStore()
    llm = FakeLLM({
        "a": [ExtractionCandidate("prozess_name", "Freigabe"),
              ExtractionCandidate("ausloeser", "Antrag"),
              ExtractionCandidate("haeufigkeit", "oft")],       # ungueltig
        "b": [ExtractionCandidate("haeufigkeit", "5 mal die Woche")],  # Korrektur
    })
    process_turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    r = process_turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
    assert r["status"] == "fertig"
    roundtrip = json.loads(json.dumps(r))
    assert roundtrip == r
    assert roundtrip["payload"]["felder"]["haeufigkeit"]["kandidaten"] == \
        [{"wert": "oft", "quelle": "m1"}]

# Kap-Fertig-Turn: Felder, die decide_next in DIESEM Turn auf UNGELOEST
# cappt, müssen im Payload unter ungeloeste_felder stehen — die Confidence
# von VOR decide_next wäre stale (Gate-0-Payload widerspräche sich selbst).
def test_cap_fertig_payload_enthaelt_frisch_gecappte_felder():
    store = InMemoryStateStore()
    r = None
    for i in range(7):   # 2 Nachfragen je Pflichtfeld, dann gecappt (3 Felder)
        r = process_turn(store, FakeLLM(), TOY_PROZESS, "s1", f"m{i}", "…")
    assert r["status"] == "fertig"
    assert r["payload"]["ungeloeste_felder"] == \
        ["prozess_name", "ausloeser", "haeufigkeit"]
    assert r["payload"]["vollstaendigkeit"] == 0.0
    assert r["payload"]["felder"]["haeufigkeit"]["status"] == "ungeloest"
