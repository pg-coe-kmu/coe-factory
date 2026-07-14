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

def test_cap_fertig_payload_traegt_grund_je_aufgegebenem_feld():
    store = InMemoryStateStore()
    r = None
    for i in range(7):
        r = process_turn(store, FakeLLM(), TOY_PROZESS, "s1", f"m{i}", "…")
    felder = r["payload"]["felder"]
    assert felder["prozess_name"]["grund"] == "nachfrage_limit_erreicht"
    assert felder["haeufigkeit"]["grund"] == "nachfrage_limit_erreicht"

# Crash ZWISCHEN Raw-Save und Final-Save (z. B. LLM-Absturz): Die Nachricht
# ist geloggt, aber unbeantwortet. Ein Replay (n8n-Retry) muss den Turn
# FORTSETZEN — nicht die Antwort der Vorgänger-Nachricht liefern (Spec B3:
# Idempotenz schützt vor Retries; Leitregel: nie Daten verlieren).
def test_replay_nach_crash_zwischen_den_saves_setzt_turn_fort():
    class CrashtBeimZweitenSave(InMemoryStateStore):
        def __init__(self):
            super().__init__()
            self.scharf = False
            self._saves_seit_scharf = 0
        def save(self, state):
            if self.scharf:
                self._saves_seit_scharf += 1
                if self._saves_seit_scharf == 2:   # = Final-Save des Turns
                    raise RuntimeError("simulierter Absturz vor dem Final-Save")
            super().save(state)

    store = CrashtBeimZweitenSave()
    llm = FakeLLM({"zwei": [ExtractionCandidate("prozess_name", "Freigabe")]})
    process_turn(store, llm, TOY_PROZESS, "s1", "m1", "eins")
    store.scharf = True
    try:
        process_turn(store, llm, TOY_PROZESS, "s1", "m2", "zwei")
    except RuntimeError:
        pass                                    # Turn m2 blieb unbeantwortet
    store.scharf = False
    r = process_turn(store, llm, TOY_PROZESS, "s1", "m2", "zwei")   # Retry
    assert r["payload"]["feld"] == "ausloeser"  # m2 wurde verarbeitet, nicht m1-Antwort
    st = store.load("s1")
    assert st.raw_log == [("m1", "eins"), ("m2", "zwei")]   # nicht doppelt geloggt
    assert st.values["prozess_name"].value == "Freigabe"

# Raw-First (Spec B3): die Rohnachricht wird VOR jedem LLM-Aufruf gesichert —
# stürzt das LLM ab, ist nichts verloren (Leitregel „nie Daten verlieren").
def test_rohnachricht_ueberlebt_llm_absturz():
    class ExplodierendesLLM(FakeLLM):
        def extract(self, message, package, state):
            raise RuntimeError("LLM weg")

    store = InMemoryStateStore()
    try:
        process_turn(store, ExplodierendesLLM(), TOY_PROZESS, "s1", "m1", "wichtig")
    except RuntimeError:
        pass
    assert store.load("s1").raw_log == [("m1", "wichtig")]
