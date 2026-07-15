from bc1_core.types import Candidate, FieldStatus, FieldValue, SessionState
from bc1_core.package import TOY_PROZESS, FieldSpec, UseCasePackage
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.extractor import extract_and_merge

def test_new_value_is_stored_with_source_and_validated():
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("prozess_name", "Freigabe"),
                         ExtractionCandidate("haeufigkeit", "oft")]})
    extract_and_merge(st, "m", "msg-1", TOY_PROZESS, llm)
    assert st.values["prozess_name"].value == "Freigabe"
    assert st.values["prozess_name"].status is FieldStatus.GUELTIG
    assert st.values["prozess_name"].source_message_id == "msg-1"
    assert st.values["haeufigkeit"].status is FieldStatus.UNGUELTIG  # kein Digit

def test_unknown_field_is_ignored():
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("gibt_es_nicht", "x")]})
    extract_and_merge(st, "m", "msg-1", TOY_PROZESS, llm)
    assert "gibt_es_nicht" not in st.values

def test_same_value_again_is_noop():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"
    assert fv.status is FieldStatus.GUELTIG
    assert fv.candidates == []
    assert fv.source_message_id == "msg-1"  # Quelle bleibt die erste Nachricht

def test_conflict_does_not_overwrite_and_marks_unklar():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"                # nicht überschrieben
    assert fv.candidates == [Candidate("Bestellung", "msg-2")]
    assert fv.status is FieldStatus.UNKLAR

# Ersetzt den alten Duplikat-Test: seit der Klärungs-Regel löst die erneute
# Nennung des KANDIDATEN den Konflikt — Dedup greift bei einem dritten Wert,
# der mehrfach genannt wird, ohne je bestätigt zu werden.
def test_unbestaetigter_mehrfachwert_wird_nicht_doppelt_kandidat():
    st = SessionState("s1", "0.1")
    werte = [("a", "Freigabe"), ("b", "Bestellung"), ("c", "Einkauf"),
             ("d", "Einkauf")]
    for msg, wert in werte:
        llm = FakeLLM({msg: [ExtractionCandidate("prozess_name", wert)]})
        extract_and_merge(st, msg, f"msg-{msg}", TOY_PROZESS, llm)
    fv = st.values["prozess_name"]
    # "Einkauf" wurde als Kandidat erneut genannt -> Klärung per Tausch;
    # dabei entsteht KEIN Duplikat, jeder Wert existiert genau einmal.
    assert fv.value == "Einkauf"
    assert fv.status is FieldStatus.GUELTIG
    assert fv.candidates == [Candidate("Bestellung", "msg-b"),
                             Candidate("Freigabe", "msg-a")]

def test_third_differing_value_accumulates_from_unklar_state():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    assert st.values["prozess_name"].status is FieldStatus.UNKLAR
    llm3 = FakeLLM({"c": [ExtractionCandidate("prozess_name", "Einkauf")]})
    extract_and_merge(st, "c", "msg-3", TOY_PROZESS, llm3)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"                # weiterhin nicht überschrieben
    assert fv.candidates == [Candidate("Bestellung", "msg-2"),
                             Candidate("Einkauf", "msg-3")]
    assert fv.status is FieldStatus.UNKLAR

def test_invalid_value_is_replaced_by_valid_correction():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("haeufigkeit", "oft")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    assert st.values["haeufigkeit"].status is FieldStatus.UNGUELTIG
    llm2 = FakeLLM({"b": [ExtractionCandidate("haeufigkeit", "5 mal pro Woche")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["haeufigkeit"]
    assert fv.value == "5 mal pro Woche"         # Korrektur ersetzt UNGUELTIG
    assert fv.status is FieldStatus.GUELTIG
    # alter Wert geht nicht verloren — samt der Quelle, aus der er stammte
    assert fv.candidates == [Candidate("oft", "msg-1")]
    assert fv.source_message_id == "msg-2"

# Design-Spec B2/B4: Kandidaten tragen ihre Quelle (message_id) —
# „Alten + neuen Kandidaten mit message_id behalten".
def test_konflikt_kandidat_traegt_quelle():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    assert st.values["prozess_name"].candidates == [Candidate("Bestellung", "msg-2")]

# Naht zu Task 7: decide_next legt beim Nachfragen FieldValue() an (value=None,
# attempts gezählt). Die Antwort muss das Feld füllen, OHNE den Nachfrage-
# Zähler zu verlieren — sonst verschiebt sich die Cap-Politik.
def test_antwort_auf_nachfrage_fuellt_feld_und_erhaelt_attempts():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(attempts=1)   # wie von decide_next angelegt
    llm = FakeLLM({"m": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "m", "msg-2", TOY_PROZESS, llm)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"
    assert fv.status is FieldStatus.GUELTIG
    assert fv.source_message_id == "msg-2"
    assert fv.attempts == 1

# GEWOLLT (Gesamt-Review 15.07.): ein vom Dialog aufgegebenes Feld (UNGELOEST,
# value=None, grund gesetzt) wird durch eine spätere validierte Extraktion
# wiederbelebt — echte späte Info schlägt „ungelöst", der grund erlischt.
def test_spaete_extraktion_belebt_aufgegebenes_feld_wieder():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(status=FieldStatus.UNGELOEST,
                                           attempts=2,
                                           grund="nachfrage_limit_erreicht")
    llm = FakeLLM({"m": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "m", "msg-9", TOY_PROZESS, llm)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"
    assert fv.status is FieldStatus.GUELTIG
    assert fv.grund is None                     # Grund gilt nur für UNGELOEST
    assert fv.attempts == 2                     # Zähler-Historie bleibt

# Zwei Kandidaten fürs gleiche Feld in EINER Nachricht: sequenzieller Merge —
# der erste füllt, der zweite erzeugt den Konflikt. Widersprüchliche Angaben
# in einer Nachricht landen so als UNKLAR beim Dialog zur Klärung.
def test_zwei_kandidaten_fuers_gleiche_feld_in_einer_nachricht():
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("prozess_name", "Freigabe"),
                         ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "m", "msg-1", TOY_PROZESS, llm)
    fv = st.values["prozess_name"]
    assert fv.value == "Freigabe"
    assert fv.status is FieldStatus.UNKLAR
    assert fv.candidates == [Candidate("Bestellung", "msg-1")]

# Spec B4 „Nutzer klären lassen": die exakte Re-Bestätigung des Werts löst
# einen UNKLAR-Konflikt auf — sonst wäre UNKLAR eine Sackgasse und ehrliche
# Antworten liefen ins Nachfrage-Limit.
def test_re_bestaetigung_des_werts_loest_unklar_konflikt():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    assert st.values["prozess_name"].status is FieldStatus.UNKLAR
    llm3 = FakeLLM({"c": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "c", "msg-3", TOY_PROZESS, llm3)   # Klärung
    fv = st.values["prozess_name"]
    assert fv.status is FieldStatus.GUELTIG
    assert fv.value == "Freigabe"
    assert fv.candidates == [Candidate("Bestellung", "msg-2")]  # Historie bleibt

def test_bestaetigung_des_kandidaten_loest_unklar_konflikt_per_tausch():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("prozess_name", "Freigabe")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    llm3 = FakeLLM({"c": [ExtractionCandidate("prozess_name", "Bestellung")]})
    extract_and_merge(st, "c", "msg-3", TOY_PROZESS, llm3)   # Klärung: Kandidat
    fv = st.values["prozess_name"]
    assert fv.status is FieldStatus.GUELTIG
    assert fv.value == "Bestellung"
    assert fv.source_message_id == "msg-3"                  # Klärungs-Nachricht
    assert fv.candidates == [Candidate("Freigabe", "msg-1")]  # alter Wert bleibt

# Korrektur-Zyklus UNGUELTIG→UNGUELTIG→…: der Dedup-Guard verhindert, dass
# ein schon bekannter Wert beim erneuten Verdrängen doppelt in die Kandidaten
# wandert. (Bekannte Eigenheit: der AKTUELLE Wert kann zugleich als Kandidat
# aus einem früheren Zyklus vorliegen — nachgehalten als Roadmap-Notiz.)
def test_korrektur_zyklus_erzeugt_keine_kandidaten_duplikate():
    st = SessionState("s1", "0.1")
    for msg, wert in [("a", "oft"), ("b", "selten"), ("c", "oft"), ("d", "nie")]:
        llm = FakeLLM({msg: [ExtractionCandidate("haeufigkeit", wert)]})
        extract_and_merge(st, msg, f"msg-{msg}", TOY_PROZESS, llm)
    fv = st.values["haeufigkeit"]
    assert fv.value == "nie"
    assert fv.status is FieldStatus.UNGUELTIG
    # "oft" nur einmal, mit der Quelle des ERSTEN Vorkommens (msg-a)
    assert fv.candidates == [Candidate("oft", "msg-a"),
                             Candidate("selten", "msg-b")]

# Ein werfender Validator (z. B. int() auf "fuenfhundert") darf nie den Turn
# crashen — mit Raw-First-Save (Task 8) wäre die Nachricht sonst dauerhaft
# verloren. Policy: Validator-Fehler = Wert UNGUELTIG.
def test_werfender_validator_macht_wert_ungueltig_statt_crash():
    paket = UseCasePackage(
        name="p", schema_version="0.1",
        fields=(FieldSpec("betrag", "Wie hoch?",
                          validator=lambda v: int(v) > 0),),
    )
    st = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("betrag", "fuenfhundert")]})
    extract_and_merge(st, "m", "msg-1", paket, llm)
    assert st.values["betrag"].status is FieldStatus.UNGUELTIG
    assert st.values["betrag"].value == "fuenfhundert"

def test_invalid_value_replaced_by_another_invalid_stays_ungueltig():
    st = SessionState("s1", "0.1")
    llm1 = FakeLLM({"a": [ExtractionCandidate("haeufigkeit", "oft")]})
    extract_and_merge(st, "a", "msg-1", TOY_PROZESS, llm1)
    llm2 = FakeLLM({"b": [ExtractionCandidate("haeufigkeit", "selten")]})
    extract_and_merge(st, "b", "msg-2", TOY_PROZESS, llm2)
    fv = st.values["haeufigkeit"]
    assert fv.value == "selten"
    assert fv.status is FieldStatus.UNGUELTIG
    assert fv.candidates == [Candidate("oft", "msg-1")]
