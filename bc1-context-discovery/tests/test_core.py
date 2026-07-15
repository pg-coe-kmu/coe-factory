import json

from bc1_core.types import SessionStatus
from bc1_core.package import TOY_PROZESS, FieldSpec, UseCasePackage
from bc1_core.dialog import MAX_ROUNDS
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

class CrashtBeimZweitenSave(InMemoryStateStore):
    """Fault-Injection: wirft beim zweiten Save nach Scharfschaltung
    (= Final-Save des laufenden Turns)."""
    def __init__(self):
        super().__init__()
        self.scharf = False
        self._saves_seit_scharf = 0

    def save(self, state):
        if self.scharf:
            self._saves_seit_scharf += 1
            if self._saves_seit_scharf == 2:
                raise RuntimeError("simulierter Absturz vor dem Final-Save")
        super().save(state)

# Crash ZWISCHEN Raw-Save und Final-Save (z. B. LLM-Absturz): Die Nachricht
# ist geloggt, aber unbeantwortet. Ein Replay (n8n-Retry) muss den Turn
# FORTSETZEN — nicht die Antwort der Vorgänger-Nachricht liefern (Spec B3:
# Idempotenz schützt vor Retries; Leitregel: nie Daten verlieren).
def test_replay_nach_crash_zwischen_den_saves_setzt_turn_fort():
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

# Gate 0 sieht das GANZE Paket: auch nie berührte (optionale) Felder stehen
# im Profil — mit FEHLT-Default, wie in conf.statuses.
def test_fertig_payload_enthaelt_alle_paketfelder_auch_unberuehrte():
    store = InMemoryStateStore()
    llm = FakeLLM({
        "a": [ExtractionCandidate("prozess_name", "Freigabe"),
              ExtractionCandidate("ausloeser", "Antrag"),
              ExtractionCandidate("haeufigkeit", "5 mal")],
    })
    r = process_turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    assert r["status"] == "fertig"
    felder = r["payload"]["felder"]
    assert set(felder) == {"prozess_name", "ausloeser", "haeufigkeit", "notiz"}
    assert felder["notiz"] == {"wert": None, "status": "fehlt", "quelle": None,
                               "grund": None, "kandidaten": []}

# Runden-Limit-Fertig bei großem Paket: KEIN Pflichtfeld darf spurlos aus
# dem Payload verschwinden — auch nie gefragte nicht (Spec Z. 81 + B3).
def test_runden_limit_fertig_meldet_alle_offenen_pflichtfelder():
    gross = UseCasePackage(
        name="gross", schema_version="0.1",
        fields=tuple(FieldSpec(f"feld_{i:02d}", f"Frage {i}?") for i in range(11)),
    )
    store = InMemoryStateStore()
    r = None
    for i in range(MAX_ROUNDS):
        r = process_turn(store, FakeLLM(), gross, "s1", f"m{i}", "…")
    assert r["status"] == "fertig"
    assert r["payload"]["ungeloeste_felder"] == [f"feld_{i:02d}" for i in range(11)]
    assert r["payload"]["felder"]["feld_10"]["grund"] == "runden_limit_erreicht"
    assert r["payload"]["felder"]["feld_00"]["grund"] == "nachfrage_limit_erreicht"

# Spec Z. 43: Idempotenz gilt PRO message_id — der späte Retry einer älteren
# Nachricht muss IHRE Antwort bekommen, nicht die der neuesten.
def test_replay_einer_aelteren_nachricht_liefert_ihre_eigene_antwort():
    store = InMemoryStateStore()
    llm = FakeLLM({
        "a": [ExtractionCandidate("prozess_name", "Freigabe")],
        "b": [ExtractionCandidate("ausloeser", "Antrag")],
    })
    r1 = process_turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    r2 = process_turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
    wieder = process_turn(store, llm, TOY_PROZESS, "s1", "m1", "a")  # später Retry
    assert wieder == r1
    assert wieder != r2

# Eine ALTE, längst beantwortete Nachricht wird wiederholt, während die
# letzte Nachricht unbeantwortet ist (Crash-Zustand). Sie darf NICHT neu
# verarbeitet werden — und bekommt ihre eigene gespeicherte Antwort.
def test_alte_nachricht_waehrend_offenem_turn_wird_nicht_neu_verarbeitet():
    store = CrashtBeimZweitenSave()
    llm = FakeLLM({"zwei": [ExtractionCandidate("prozess_name", "Freigabe")]})
    r1 = process_turn(store, llm, TOY_PROZESS, "s1", "m1", "eins")
    store.scharf = True
    try:
        process_turn(store, llm, TOY_PROZESS, "s1", "m2", "zwei")
    except RuntimeError:
        pass
    store.scharf = False
    vorher = store.load("s1")
    r = process_turn(store, llm, TOY_PROZESS, "s1", "m1", "eins")   # altes Replay
    assert r == r1                                  # die eigene Antwort von damals
    nachher = store.load("s1")
    assert nachher.rounds == vorher.rounds          # nichts doppelt angewandt
    assert nachher.raw_log == vorher.raw_log

# Spec B3: Die State-Machine kennt keinen Übergang FERTIG → WARTET. Nach
# der Gate-0-Übergabe öffnet keine neue Nachricht die Session wieder —
# sie erhält idempotent das Abschlussergebnis (Zurückweisung: Sache von P2).
def test_fertige_session_wird_nicht_wieder_geoeffnet():
    store = InMemoryStateStore()
    llm = FakeLLM({
        "a": [ExtractionCandidate("prozess_name", "Freigabe"),
              ExtractionCandidate("ausloeser", "Antrag"),
              ExtractionCandidate("haeufigkeit", "5 mal")],
        "b": [ExtractionCandidate("prozess_name", "Anders")],   # Widerspruch
    })
    fertig = process_turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    assert fertig["status"] == "fertig"
    vorher = store.load("s1")
    r = process_turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
    assert r == fertig                              # idempotenter Abschluss
    nachher = store.load("s1")
    assert nachher.status is SessionStatus.FERTIG
    assert nachher.values["prozess_name"].value == "Freigabe"   # kein UNKLAR
    assert nachher.raw_log == vorher.raw_log
    assert nachher.rounds == vorher.rounds

def test_zwei_sessions_bleiben_getrennt_auch_bei_gleicher_message_id():
    store = InMemoryStateStore()
    llm = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    process_turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    r2 = process_turn(store, llm, TOY_PROZESS, "s2", "m1", "hallo")
    assert store.load("s1").values["prozess_name"].value == "Freigabe"
    # s2 startet frisch: kein Wert aus s1, keine Idempotenz-Kollision über m1
    assert store.load("s2").values["prozess_name"].value is None
    assert r2 == {"status": "frage",
                  "payload": {"naechste_frage": "Wie heißt der Prozess?",
                              "feld": "prozess_name"}}

# Ein überholter Crash-Turn (andere Nachrichten kamen dazwischen, Session
# wurde regulär FERTIG) darf beim Replay NICHT fortgesetzt werden — sonst
# würde die abgeschlossene Session wieder geöffnet (Spec B3: kein Übergang
# zurück). Er erhält die letzte bekannte Antwort der Session.
def test_ueberholter_crash_turn_oeffnet_fertige_session_nicht():
    store = CrashtBeimZweitenSave()
    llm = FakeLLM({
        "kaputt": [ExtractionCandidate("prozess_name", "Falsch")],
        "alles": [ExtractionCandidate("prozess_name", "Freigabe"),
                  ExtractionCandidate("ausloeser", "Antrag"),
                  ExtractionCandidate("haeufigkeit", "5 mal")],
    })
    store.scharf = True
    try:
        process_turn(store, llm, TOY_PROZESS, "s1", "m1", "kaputt")   # crasht
    except RuntimeError:
        pass
    store.scharf = False
    fertig = process_turn(store, llm, TOY_PROZESS, "s1", "m2", "alles")
    assert fertig["status"] == "fertig"
    r = process_turn(store, llm, TOY_PROZESS, "s1", "m1", "kaputt")   # Replay
    assert r == fertig                                # keine Neuverarbeitung
    st = store.load("s1")
    assert st.status is SessionStatus.FERTIG
    assert st.values["prozess_name"].value == "Freigabe"   # kein Konflikt

# Beim Crash-Resume zählt der GELOGGTE Text — nicht ein womöglich
# abweichender Retry-Body (sonst widersprächen sich raw_log und Verarbeitung).
def test_crash_resume_verarbeitet_den_geloggten_text():
    store = CrashtBeimZweitenSave()
    llm = FakeLLM({"orig": [ExtractionCandidate("prozess_name", "Freigabe")],
                   "anders": [ExtractionCandidate("prozess_name", "Falsch")]})
    store.scharf = True
    try:
        process_turn(store, llm, TOY_PROZESS, "s1", "m1", "orig")   # crasht
    except RuntimeError:
        pass
    store.scharf = False
    process_turn(store, llm, TOY_PROZESS, "s1", "m1", "anders")     # Retry
    st = store.load("s1")
    assert st.values["prozess_name"].value == "Freigabe"    # aus "orig"
    assert st.raw_log == [("m1", "orig")]

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
