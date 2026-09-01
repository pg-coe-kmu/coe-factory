import json
from dataclasses import replace

import pytest

from bc1_core.types import SessionState, SessionStatus
from bc1_core.package import TOY_PROZESS, FieldSpec, UseCasePackage
from bc1_core.dialog import MAX_ROUNDS
from bc1_core.store import InMemoryStateStore
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.core import (MandantKonfliktError, PaketKonfliktError,
                           process_turn)

MANDANT = "11111111-1111-1111-1111-111111111111"


def _turn(store, llm, package, session_id, message_id, message,
          company_id=MANDANT, mitgesendete_version=None):
    """Testhelfer: process_turn mit Standard-Mandant."""
    return process_turn(store, llm, package, session_id, message_id, message,
                        company_id=company_id,
                        mitgesendete_version=mitgesendete_version)

def test_first_turn_asks_first_open_field():
    store = InMemoryStateStore()
    r = _turn(store, FakeLLM(), TOY_PROZESS, "s1", "msg-1", "hallo")
    assert r["status"] == "frage"
    assert r["payload"]["feld"] == "prozess_name"
    st = store.load("s1")
    assert st.raw_log == [("msg-1", "hallo")]   # roh geloggt
    assert st.status is SessionStatus.WARTET
    assert st.rounds == 1

def test_idempotent_replay_returns_same_response_without_double_log():
    store = InMemoryStateStore()
    llm = FakeLLM({"hallo": [ExtractionCandidate("prozess_name", "Freigabe")]})
    first = _turn(store, llm, TOY_PROZESS, "s1", "msg-1", "hallo")
    again = _turn(store, llm, TOY_PROZESS, "s1", "msg-1", "hallo")
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
    _turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    _turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
    r = _turn(store, llm, TOY_PROZESS, "s1", "m3", "c")
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
    _turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    r = _turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
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
        r = _turn(store, FakeLLM(), TOY_PROZESS, "s1", f"m{i}", "…")
    assert r["status"] == "fertig"
    assert r["payload"]["ungeloeste_felder"] == \
        ["prozess_name", "ausloeser", "haeufigkeit"]
    assert r["payload"]["vollstaendigkeit"] == 0.0
    assert r["payload"]["felder"]["haeufigkeit"]["status"] == "ungeloest"

def test_cap_fertig_payload_traegt_grund_je_aufgegebenem_feld():
    store = InMemoryStateStore()
    r = None
    for i in range(7):
        r = _turn(store, FakeLLM(), TOY_PROZESS, "s1", f"m{i}", "…")
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
    _turn(store, llm, TOY_PROZESS, "s1", "m1", "eins")
    store.scharf = True
    try:
        _turn(store, llm, TOY_PROZESS, "s1", "m2", "zwei")
    except RuntimeError:
        pass                                    # Turn m2 blieb unbeantwortet
    store.scharf = False
    r = _turn(store, llm, TOY_PROZESS, "s1", "m2", "zwei")   # Retry
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
    r = _turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
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
        r = _turn(store, FakeLLM(), gross, "s1", f"m{i}", "…")
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
    r1 = _turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    r2 = _turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
    wieder = _turn(store, llm, TOY_PROZESS, "s1", "m1", "a")  # später Retry
    assert wieder == r1
    assert wieder != r2

# Eine ALTE, längst beantwortete Nachricht wird wiederholt, während die
# letzte Nachricht unbeantwortet ist (Crash-Zustand). Sie darf NICHT neu
# verarbeitet werden — und bekommt ihre eigene gespeicherte Antwort.
def test_alte_nachricht_waehrend_offenem_turn_wird_nicht_neu_verarbeitet():
    store = CrashtBeimZweitenSave()
    llm = FakeLLM({"zwei": [ExtractionCandidate("prozess_name", "Freigabe")]})
    r1 = _turn(store, llm, TOY_PROZESS, "s1", "m1", "eins")
    store.scharf = True
    try:
        _turn(store, llm, TOY_PROZESS, "s1", "m2", "zwei")
    except RuntimeError:
        pass
    store.scharf = False
    vorher = store.load("s1")
    r = _turn(store, llm, TOY_PROZESS, "s1", "m1", "eins")   # altes Replay
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
    fertig = _turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    assert fertig["status"] == "fertig"
    vorher = store.load("s1")
    r = _turn(store, llm, TOY_PROZESS, "s1", "m2", "b")
    assert r == fertig                              # idempotenter Abschluss
    nachher = store.load("s1")
    assert nachher.status is SessionStatus.FERTIG
    assert nachher.values["prozess_name"].value == "Freigabe"   # kein UNKLAR
    assert nachher.raw_log == vorher.raw_log
    assert nachher.rounds == vorher.rounds

# Eine Session ist an ihre schema_version gebunden — ein Turn mit einem
# anderen Paket darf nie still vermischt werden (Gate 0 bekäme sonst ein
# Profil mit falscher Schema-Angabe).
def test_paketwechsel_in_laufender_session_wird_abgelehnt():
    anderes = UseCasePackage(
        name="anderes", schema_version="9.9",
        fields=(FieldSpec("lieferant", "Wer?"),),
    )
    store = InMemoryStateStore()
    _turn(store, FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")
    with pytest.raises(ValueError):
        _turn(store, FakeLLM(), anderes, "s1", "m2", "hallo")

def test_paketwechsel_wird_auch_bei_gleicher_schema_version_abgelehnt():
    anderes = UseCasePackage(
        name="anderes", schema_version="0.1",   # gleiche Version wie TOY!
        fields=(FieldSpec("lieferant", "Wer?"),),
    )
    store = InMemoryStateStore()
    _turn(store, FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")
    with pytest.raises(ValueError):
        _turn(store, FakeLLM(), anderes, "s1", "m2", "hallo")

# Der Paket-Guard wirft eine EIGENE Exception-Klasse (Subklasse von
# ValueError): die Transportschicht muss ihn von beliebigen ValueErrors
# aus der Verarbeitung unterscheiden können, ohne auf Text zu prüfen.
def test_paket_guard_wirft_paketkonfliktfehler():
    anderes = UseCasePackage(
        name="anderes", schema_version="0.1",
        fields=(FieldSpec("lieferant", "Wer?"),),
    )
    store = InMemoryStateStore()
    _turn(store, FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")
    with pytest.raises(PaketKonfliktError):
        _turn(store, FakeLLM(), anderes, "s1", "m2", "hallo")


def test_zwei_sessions_bleiben_getrennt_auch_bei_gleicher_message_id():
    store = InMemoryStateStore()
    llm = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    _turn(store, llm, TOY_PROZESS, "s1", "m1", "a")
    r2 = _turn(store, llm, TOY_PROZESS, "s2", "m1", "hallo")
    assert store.load("s1").values["prozess_name"].value == "Freigabe"
    # s2 startet frisch: kein Wert aus s1, keine Idempotenz-Kollision über m1
    assert store.load("s2").values["prozess_name"].value is None
    assert r2 == {"status": "frage",
                  "payload": {"naechste_frage": "Wie heißt der Prozess?",
                              "feld": "prozess_name",
                              "pflicht_erfasst": 0,
                              "pflicht_gesamt": 3}}

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
        _turn(store, llm, TOY_PROZESS, "s1", "m1", "kaputt")   # crasht
    except RuntimeError:
        pass
    store.scharf = False
    fertig = _turn(store, llm, TOY_PROZESS, "s1", "m2", "alles")
    assert fertig["status"] == "fertig"
    r = _turn(store, llm, TOY_PROZESS, "s1", "m1", "kaputt")   # Replay
    assert r == fertig                                # keine Neuverarbeitung
    st = store.load("s1")
    assert st.status is SessionStatus.FERTIG
    assert st.values["prozess_name"].value == "Freigabe"   # kein Konflikt

def test_ueberholter_crash_turn_wird_auch_bei_laufender_session_nicht_fortgesetzt():
    store = CrashtBeimZweitenSave()
    llm = FakeLLM({"kaputt": [ExtractionCandidate("prozess_name", "Falsch")],
                   "ok": [ExtractionCandidate("prozess_name", "Freigabe")]})
    store.scharf = True
    try:
        _turn(store, llm, TOY_PROZESS, "s1", "m1", "kaputt")   # crasht
    except RuntimeError:
        pass
    store.scharf = False
    r2 = _turn(store, llm, TOY_PROZESS, "s1", "m2", "ok")      # überholt m1
    vorher = store.load("s1")
    r = _turn(store, llm, TOY_PROZESS, "s1", "m1", "kaputt")   # Replay m1
    assert r == r2                                  # letzte bekannte Antwort
    nachher = store.load("s1")
    assert nachher.values["prozess_name"].value == "Freigabe"   # kein "Falsch"
    assert nachher.rounds == vorher.rounds

# Doppel-Crash: BEIDE Turns blieben unbeantwortet — das Replay der
# überholten Nachricht bekommt eine Vertragsantwort (fehler_fortsetzbar),
# niemals None (process_turn -> dict).
def test_ueberholtes_replay_ohne_jede_antwort_liefert_vertragsantwort():
    class CrashtBeiFinalSaves(InMemoryStateStore):
        def __init__(self):
            super().__init__()
            self._n = 0
        def save(self, state):
            self._n += 1
            if self._n in (2, 4):               # Final-Saves von m1 und m2
                raise RuntimeError("Absturz vor dem Final-Save")
            super().save(state)

    store = CrashtBeiFinalSaves()
    llm = FakeLLM()
    for mid in ("m1", "m2"):
        try:
            _turn(store, llm, TOY_PROZESS, "s1", mid, "hallo")
        except RuntimeError:
            pass
    r = _turn(store, llm, TOY_PROZESS, "s1", "m1", "hallo")   # überholt
    assert r == {"status": "fehler_fortsetzbar",
                 "payload": {"grund": "turn_unbeantwortet"}}

# Beim Crash-Resume zählt der GELOGGTE Text — nicht ein womöglich
# abweichender Retry-Body (sonst widersprächen sich raw_log und Verarbeitung).
def test_crash_resume_verarbeitet_den_geloggten_text():
    store = CrashtBeimZweitenSave()
    llm = FakeLLM({"orig": [ExtractionCandidate("prozess_name", "Freigabe")],
                   "anders": [ExtractionCandidate("prozess_name", "Falsch")]})
    store.scharf = True
    try:
        _turn(store, llm, TOY_PROZESS, "s1", "m1", "orig")   # crasht
    except RuntimeError:
        pass
    store.scharf = False
    _turn(store, llm, TOY_PROZESS, "s1", "m1", "anders")     # Retry
    st = store.load("s1")
    assert st.values["prozess_name"].value == "Freigabe"    # aus "orig"
    assert st.raw_log == [("m1", "orig")]

class ExplodierendesLLM(FakeLLM):
    def extract(self, message, package, state):
        raise RuntimeError("LLM weg")

# Spec B4: LLM-Aussetzer → State speichern und fehler_fortsetzbar zurückgeben
# (statt roher Exception). Raw-First (B3): die Rohnachricht ist da bereits
# gesichert — nichts geht verloren, der Retry kann fortsetzen.
def test_llm_absturz_liefert_fehler_fortsetzbar_statt_exception():
    store = InMemoryStateStore()
    r = _turn(store, ExplodierendesLLM(), TOY_PROZESS, "s1", "m1", "wichtig")
    assert r == {"status": "fehler_fortsetzbar",
                 "payload": {"grund": "verarbeitung_fehlgeschlagen"}}
    st = store.load("s1")
    assert st.status is SessionStatus.FEHLER
    assert st.raw_log == [("m1", "wichtig")]    # Raw-First: nichts verloren
    assert "m1" not in st.antworten             # unbeantwortet → Retry setzt fort

# Ein LLM-Ausfall darf keine unsichtbare Nachfrage verbrauchen: der
# Fehlerpfad persistiert NUR den FEHLER-Marker, nicht den halb
# verarbeiteten Turn (rounds/attempts). Der Retry zählt dann genau einmal.
def test_llm_ausfall_verbraucht_keine_nachfrage():
    class PhrasenAusfallLLM(FakeLLM):
        def antworte(self, kontext):
            raise RuntimeError("LLM weg")

    store = InMemoryStateStore()
    _turn(store, PhrasenAusfallLLM(), TOY_PROZESS, "s1", "m1", "hallo")
    st = store.load("s1")
    assert st.status is SessionStatus.FEHLER
    assert st.rounds == 0                       # keine halbe Runde persistiert
    assert all(fv.attempts == 0 for fv in st.values.values())
    r = _turn(store, FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")  # Retry
    assert r["status"] == "frage"
    st = store.load("s1")
    assert st.rounds == 1                       # genau EINE Runde gezählt
    assert st.values["prozess_name"].attempts == 1

# Spec B94 „Fortsetzbarkeit": nach FEHLER_FORTSETZBAR setzt der Retry mit
# funktionierendem LLM den Turn normal fort.
def test_retry_nach_fehler_fortsetzbar_setzt_turn_fort():
    store = InMemoryStateStore()
    kaputt = ExplodierendesLLM({"wichtig": [ExtractionCandidate("prozess_name", "Freigabe")]})
    _turn(store, kaputt, TOY_PROZESS, "s1", "m1", "wichtig")
    heil = FakeLLM({"wichtig": [ExtractionCandidate("prozess_name", "Freigabe")]})
    r = _turn(store, heil, TOY_PROZESS, "s1", "m1", "wichtig")   # Retry
    assert r["status"] == "frage"
    st = store.load("s1")
    assert st.status is SessionStatus.WARTET
    assert st.values["prozess_name"].value == "Freigabe"
    assert st.raw_log == [("m1", "wichtig")]    # nicht doppelt geloggt


def test_frage_traegt_gespraechstext_mit_bestaetigung_und_kernfrage():
    store = InMemoryStateStore()
    llm = FakeLLM({"Der Prozess heißt Urlaubsantrag":
                   [ExtractionCandidate("prozess_name", "Urlaubsantrag")]})
    resp = _turn(store, llm, TOY_PROZESS, "s-gespraech", "m1",
                        "Der Prozess heißt Urlaubsantrag")
    p = resp["payload"]
    # Fake-Komposition: Bestätigung der echten Werte + nächste Kernfrage wörtlich.
    assert "Urlaubsantrag" in p["naechste_frage"]
    assert TOY_PROZESS.field(p["feld"]).question in p["naechste_frage"]
    assert p["pflicht_erfasst"] == 1
    assert p["pflicht_gesamt"] == len(TOY_PROZESS.required_fields())


def test_abschluss_traegt_zusammenfassung_und_zaehler():
    store = InMemoryStateStore()
    llm = FakeLLM({
        "A": [ExtractionCandidate("prozess_name", "Urlaubsantrag")],
        "B": [ExtractionCandidate("ausloeser", "Antrag")],
        "C": [ExtractionCandidate("haeufigkeit", "100 mal pro Jahr")]})
    _turn(store, llm, TOY_PROZESS, "s-abschluss", "m1", "A")
    _turn(store, llm, TOY_PROZESS, "s-abschluss", "m2", "B")
    resp = _turn(store, llm, TOY_PROZESS, "s-abschluss", "m3", "C")
    assert resp["status"] == "fertig"
    p = resp["payload"]
    assert "Urlaubsantrag" in p["abschluss_text"]
    assert p["pflicht_erfasst"] == p["pflicht_gesamt"]


def test_gespraechstext_kommt_aus_llm_antworte_nicht_aus_dem_paket():
    # Invariante „LLM nur hinter dem LLM-Client" — ersetzt den bisherigen
    # phrase-Beweis aus test_dialog.py auf der neuen Naht.
    class EigeneWorte(FakeLLM):
        def antworte(self, kontext):
            return "GANZ EIGENE FORMULIERUNG"

    store = InMemoryStateStore()
    resp = _turn(store, EigeneWorte(), TOY_PROZESS, "s-inv", "m1", "Hallo")
    assert resp["payload"]["naechste_frage"] == "GANZ EIGENE FORMULIERUNG"


IDENT_PAKET = UseCasePackage(
    name="ident_test", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa", max_rounds=2,
    fields=(FieldSpec("tp_id", "Welcher Schritt?",
                      validator=lambda v: v == "KP-01.TP-1",
                      identitaetskritisch=True),),
)


def test_runden_limit_ohne_identitaet_endet_im_abbruch_zustand():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, IDENT_PAKET, "s1", "m1", "keine ahnung")
    r = _turn(store, llm, IDENT_PAKET, "s1", "m2", "immer noch nicht")
    assert r["status"] == "abgebrochen_ohne_identitaet"
    assert r["payload"]["grund"] == "identitaet_ungeklaert"
    assert r["payload"]["feld"] == "tp_id"
    assert store.load("s1").status is SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET


class _WerfendesLLM(FakeLLM):
    def antworte(self, kontext):
        raise RuntimeError("LLM kaputt")


def test_abbruch_kommt_ohne_llm_aus():
    # R8-I2: ein LLM-Ausfall darf den definierten Terminalzustand nicht in
    # fehler_fortsetzbar kippen. Gegenprobe im Frage-Turn: DORT schlaegt der
    # Ausfall wie gehabt durch (der Kern faengt ihn, Codex R2-N-I5).
    store = InMemoryStateStore()
    frage_turn = _turn(store, _WerfendesLLM(), IDENT_PAKET, "s1", "m1", "keine ahnung")
    assert frage_turn["status"] == "fehler_fortsetzbar"

    store2 = InMemoryStateStore()
    _turn(store2, FakeLLM(), IDENT_PAKET, "s1", "m1", "keine ahnung")
    r = _turn(store2, _WerfendesLLM(), IDENT_PAKET, "s1", "m2", "nein")
    assert r["status"] == "abgebrochen_ohne_identitaet"


def test_abbruch_replay_ist_idempotent():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, IDENT_PAKET, "s1", "m1", "a")
    erst = _turn(store, llm, IDENT_PAKET, "s1", "m2", "b")
    assert _turn(store, llm, IDENT_PAKET, "s1", "m2", "b") == erst


MANDANT_B = "22222222-2222-2222-2222-222222222222"


def test_mandanten_guard_weist_fremden_mandanten_immer_ab():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, TOY_PROZESS, "s1", "m1", "hallo")
    with pytest.raises(MandantKonfliktError):
        _turn(store, llm, TOY_PROZESS, "s1", "m2", "hallo", company_id=MANDANT_B)
    with pytest.raises(MandantKonfliktError):        # auch der bekannte Replay
        _turn(store, llm, TOY_PROZESS, "s1", "m1", "hallo", company_id=MANDANT_B)


def test_alt_session_ohne_company_id_wird_immer_abgewiesen():
    store = InMemoryStateStore()
    store.save(SessionState("s1", "0.1", paket_name="toy_prozess"))   # company_id=None
    with pytest.raises(MandantKonfliktError):
        _turn(store, FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")


def test_company_id_liegt_schon_im_ersten_gespeicherten_stand():
    gesehen = []

    class _SpionStore(InMemoryStateStore):
        def save(self, state):
            gesehen.append(state.company_id)
            super().save(state)

    _turn(_SpionStore(), FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")
    assert gesehen and gesehen[0] == MANDANT          # schon beim Roh-Log-Save


def test_recovery_replay_passiert_den_paket_guard_nur_bei_ctx_abweichung():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, IDENT_PAKET, "s1", "m1", "a")
    erst = _turn(store, llm, IDENT_PAKET, "s1", "m2", "b")     # terminal
    alt_version = IDENT_PAKET.schema_version
    anderes_ctx = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    assert _turn(store, llm, anderes_ctx, "s1", "m2", "b",
                 mitgesendete_version=alt_version) == erst

    with pytest.raises(PaketKonfliktError):          # ohne Altversion kein Recovery
        _turn(store, llm, anderes_ctx, "s1", "m2", "b")

    andere_basis = replace(IDENT_PAKET, schema_version="1.2+ctx-bbbbbbbbbbbbbbbb")
    with pytest.raises(PaketKonfliktError):
        _turn(store, llm, andere_basis, "s1", "m2", "b",
              mitgesendete_version=alt_version)

    anderer_name = replace(anderes_ctx, name="fremd")
    with pytest.raises(PaketKonfliktError):
        _turn(store, llm, anderer_name, "s1", "m2", "b",
              mitgesendete_version=alt_version)


# Direkter Unit-Test der produzierten Schnittstelle (Plan-Vertrag): sichert die
# Extraktion aus process_turn in eine eigenstaendige, importierbare Funktion ab.
def test_darf_recovery_replay_direkt():
    from bc1_core.core import darf_recovery_replay

    state = SessionState("s1", "1.1+ctx-aaaaaaaaaaaaaaaa", paket_name="ident_test",
                         status=SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET,
                         processed_message_ids={"m2"})
    anderes_ctx = replace(IDENT_PAKET, schema_version="1.1+ctx-bbbbbbbbbbbbbbbb")
    assert darf_recovery_replay(state, anderes_ctx, "m2",
                                "1.1+ctx-aaaaaaaaaaaaaaaa") is True
    assert darf_recovery_replay(state, anderes_ctx, "m2", None) is False


# Terminal-Gate (Spec B3) gilt fuer BEIDE Terminalzustaende, nicht nur FERTIG:
# eine neue, nie gesehene Nachricht darf eine abgebrochene Session nicht
# wieder oeffnen.
def test_abgebrochene_session_wird_nicht_wieder_geoeffnet():
    store = InMemoryStateStore()
    llm = FakeLLM()
    _turn(store, llm, IDENT_PAKET, "s1", "m1", "a")
    abgebrochen = _turn(store, llm, IDENT_PAKET, "s1", "m2", "b")
    assert abgebrochen["status"] == "abgebrochen_ohne_identitaet"
    r = _turn(store, llm, IDENT_PAKET, "s1", "m3", "c")   # neue Nachricht
    assert r == abgebrochen
    st = store.load("s1")
    assert st.raw_log == [("m1", "a"), ("m2", "b")]   # m3 nicht mitprotokolliert


# R11-C1/K3: der Mandanten-Guard laeuft nach JEDEM load, auch dem erneuten
# load im Fehlerpfad — nicht nur beim ersten load des Turns.
def test_except_pfad_prueft_mandant_beim_erneuten_load():
    class _MandantWechselStore(InMemoryStateStore):
        def __init__(self):
            super().__init__()
            self._loads = 0

        def load(self, session_id):
            self._loads += 1
            st = super().load(session_id)
            if self._loads == 3 and st is not None:
                st.company_id = MANDANT_B   # aendert sich zwischen den beiden loads
            return st

    store = _MandantWechselStore()
    _turn(store, FakeLLM(), TOY_PROZESS, "s1", "m1", "hallo")
    with pytest.raises(MandantKonfliktError):
        _turn(store, ExplodierendesLLM(), TOY_PROZESS, "s1", "m2", "kaputt")
