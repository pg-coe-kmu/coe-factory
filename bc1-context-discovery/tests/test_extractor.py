import logging

import pytest

from bc1_core.types import Candidate, FieldStatus, FieldValue, SessionState
from bc1_core.package import TOY_PROZESS, FieldSpec, UseCasePackage
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.extractor import extract_and_merge
from bc1_core.feldtypen import AUSWAHL, MINUTEN, PROZENT_0_100, SKALA_1_5, ZAHL
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket
from bc1_service.paket_feldtypen import PROZENT_GANZ_0_100


class _ZaehlerKI(FakeLLM):
    """Zählt die extract-Aufrufe; liefert eine einstellbare Kandidatenliste."""
    def __init__(self, kandidaten=None):
        super().__init__()
        self.aufrufe = 0
        self._kandidaten = kandidaten or []

    def extract(self, message, package, state):
        self.aufrufe += 1
        return list(self._kandidaten)


@pytest.mark.parametrize("typ, eingabe, erwartet", [
    (PROZENT_0_100, "ca. 70 %", "70"),
    (SKALA_1_5, "4.", "4"),
    (MINUTEN, "1,5h", "90"),
    (ZAHL, "2mal im Monat", "24"),
])
def test_kurzantwort_ohne_ki(typ, eingabe, erwartet):
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("wert", "Wie viel?", typ=typ),),
    )
    state = SessionState("s1", "0.1")
    ki = _ZaehlerKI()
    extract_and_merge(state, eingabe, "m1", paket, ki,
                      gefragt=paket.field("wert"))
    fv = state.values["wert"]
    assert fv.value == erwartet
    assert fv.status is FieldStatus.GUELTIG
    assert fv.source_message_id == "m1"
    assert ki.aufrufe == 0


def test_kurzantwort_ungueltiger_wert():
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("wert", "Wie viel Prozent?", typ=PROZENT_0_100),),
    )
    state = SessionState("s1", "0.1")
    ki = _ZaehlerKI()
    extract_and_merge(state, "150 %", "m1", paket, ki,
                      gefragt=paket.field("wert"))
    assert state.values["wert"].status is FieldStatus.UNGUELTIG
    assert ki.aufrufe == 0


def test_kurzantwort_ganzzahl_prozent_mit_komma():
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("wert", "Wie viel Prozent?",
                          typ=PROZENT_GANZ_0_100),),
    )
    state = SessionState("s1", "0.1")
    ki = _ZaehlerKI()
    extract_and_merge(state, "70,5 %", "m1", paket, ki,
                      gefragt=paket.field("wert"))
    assert state.values["wert"].status is FieldStatus.UNGUELTIG
    assert ki.aufrufe == 0


def test_lange_antwort_geht_an_die_ki():
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("schrittdauer", "Wie lange dauert der Schritt?",
                          typ=MINUTEN),
                FieldSpec("gesamtdauer", "Wie lange dauert alles?",
                          typ=MINUTEN)),
    )
    state = SessionState("s1", "0.1")
    ki = _ZaehlerKI([ExtractionCandidate("gesamtdauer", "3 Stunden")])
    extract_and_merge(state, "Der Prozess dauert 3 Stunden.", "m1", paket, ki,
                      gefragt=paket.field("schrittdauer"))
    assert state.values["gesamtdauer"].value == "180"
    assert "schrittdauer" not in state.values
    assert ki.aufrufe == 1


@pytest.mark.parametrize("gefragt_name", [None, "notiz"])
def test_ohne_kurzform_ruft_die_ki(gefragt_name):
    # (a) nichts gefragt, (b) gefragtes Feld ohne Kurzform (FREITEXT)
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("notiz", "Was noch?"),
                FieldSpec("note", "Wie gut?", typ=SKALA_1_5)),
    )
    state = SessionState("s1", "0.1")
    ki = _ZaehlerKI()
    gefragt = paket.field(gefragt_name) if gefragt_name else None
    extract_and_merge(state, "4", "m1", paket, ki, gefragt=gefragt)
    assert ki.aufrufe == 1
    assert state.values == {}


def test_kurzantwort_bestaetigt_kandidaten():
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("dauer", "Wie lange?", typ=MINUTEN),),
    )
    state = SessionState("s1", "0.1")
    state.values["dauer"] = FieldValue(
        "2400", FieldStatus.UNKLAR, "m1", attempts=1,
        candidates=[Candidate("180", "m2")])
    extract_and_merge(state, "3 Stunden", "m3", paket, _ZaehlerKI(),
                      gefragt=paket.field("dauer"))
    fv = state.values["dauer"]
    assert fv.value == "180"
    assert fv.source_message_id == "m3"
    assert fv.candidates == [Candidate("2400", "m1")]
    assert fv.status is FieldStatus.GUELTIG
    assert fv.attempts == 1


def test_kurzantwort_bestaetigt_bisherigen_wert():
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("dauer", "Wie lange?", typ=MINUTEN),),
    )
    state = SessionState("s1", "0.1")
    state.values["dauer"] = FieldValue(
        "2400", FieldStatus.UNKLAR, "m1", attempts=1,
        candidates=[Candidate("180", "m2")])
    extract_and_merge(state, "40 Stunden", "m3", paket, _ZaehlerKI(),
                      gefragt=paket.field("dauer"))
    fv = state.values["dauer"]
    assert fv.value == "2400"
    assert fv.source_message_id == "m1"
    assert fv.status is FieldStatus.GUELTIG


def test_kurzantwort_dritter_wert_bleibt_unklar():
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("dauer", "Wie lange?", typ=MINUTEN),),
    )
    state = SessionState("s1", "0.1")
    state.values["dauer"] = FieldValue(
        "2400", FieldStatus.UNKLAR, "m1", attempts=1,
        candidates=[Candidate("180", "m2")])
    extract_and_merge(state, "5 Stunden", "m3", paket, _ZaehlerKI(),
                      gefragt=paket.field("dauer"))
    fv = state.values["dauer"]
    assert fv.status is FieldStatus.UNKLAR
    assert Candidate("300", "m3") in fv.candidates


def test_kurzantwort_korrigiert_ungueltig():
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("dauer", "Wie lange?", typ=MINUTEN),),
    )
    state = SessionState("s1", "0.1")
    state.values["dauer"] = FieldValue("viel", FieldStatus.UNGUELTIG, "m1")
    extract_and_merge(state, "3 Stunden", "m2", paket, _ZaehlerKI(),
                      gefragt=paket.field("dauer"))
    fv = state.values["dauer"]
    assert fv.value == "180"
    assert fv.status is FieldStatus.GUELTIG
    assert fv.candidates == [Candidate("viel", "m1")]


def test_kurzantwort_protokolliert_nur_feldname(caplog):
    paket = UseCasePackage(
        name="kurz_test", schema_version="0.1",
        fields=(FieldSpec("quelle", "Geschätzt oder gemessen?",
                          typ=AUSWAHL("geschaetzt", "gemessen")),),
    )
    state = SessionState("s1", "0.1")
    with caplog.at_level(logging.INFO, logger="bc1.kern"):
        extract_and_merge(state, "geschaetzt", "m1", paket, _ZaehlerKI(),
                          gefragt=paket.field("quelle"))
    zeilen = [r.getMessage() for r in caplog.records if r.name == "bc1.kern"]
    direkt = [z for z in zeilen if z.startswith("kurzantwort_direkt")]
    assert len(direkt) == 1
    assert direkt[0].endswith("feld=quelle")
    assert "korrelation=" in direkt[0]
    assert not any("geschaetzt" in z for z in zeilen)
    assert not any("ki_aufruf" in z and "art=extraktion" in z for z in zeilen)


def test_focus_step_kurzantwort():
    kontext = Bc0Kontext(
        company_id="11111111-1111-1111-1111-111111111111",
        teilprozesse=(("KP-01.TP-1", "Erfassen"), ("KP-01.TP-2", "Pruefen")),
        system_ids=("S-01", "S-02"))
    paket = baue_discovery_paket(kontext=kontext)
    gefragt = paket.field("focus_step")
    state = SessionState("s1", paket.schema_version)
    ki = _ZaehlerKI()
    extract_and_merge(state, "KP-01.TP-1", "m1", paket, ki, gefragt=gefragt)
    assert state.values["focus_step"].value == "KP-01.TP-1"
    assert state.values["focus_step"].status is FieldStatus.GUELTIG
    assert ki.aufrufe == 0
    # Teilprozessname loest die Kurzform direkt auf (Spec 3.3): kein KI-Aufruf
    direkt_ki = _ZaehlerKI()
    direkt_state = SessionState("s3", paket.schema_version)
    extract_and_merge(direkt_state, "Erfassen", "m1", paket, direkt_ki, gefragt=gefragt)
    assert direkt_state.values["focus_step"].value == "KP-01.TP-1"
    assert direkt_ki.aufrufe == 0
    for text in ("KP-01.TP-9", "KP-01.TP-1?"):
        frische_ki = _ZaehlerKI()
        extract_and_merge(SessionState("s2", paket.schema_version), text,
                          "m1", paket, frische_ki, gefragt=gefragt)
        assert frische_ki.aufrufe == 1, text

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

def test_typ_normalisiert_vor_validierung_und_speichert_normalisiert():
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("dauer", "Wie lange?", typ=MINUTEN),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({"2 Stunden": [ExtractionCandidate("dauer", "2 Stunden")]})
    extract_and_merge(state, "2 Stunden", "m1", paket, llm)
    assert state.values["dauer"].value == "120"
    assert state.values["dauer"].status is FieldStatus.GUELTIG


def test_typ_ungueltiger_wert_bleibt_unnormalisiert_und_ungueltig():
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("menge", "Wie oft?", typ=ZAHL),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("menge", "5 pro Tag")]})
    extract_and_merge(state, "m", "m1", paket, llm)
    assert state.values["menge"].value == "5 pro Tag"
    assert state.values["menge"].status is FieldStatus.UNGUELTIG


def test_expliziter_validator_gewinnt_ueber_typ():
    # Rückwärtskompatibilität: Felder wie TOY haeufigkeit behalten Verhalten.
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("f", "?", validator=lambda v: v == "spezial", typ=ZAHL),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("f", "spezial")]})
    extract_and_merge(state, "m", "m1", paket, llm)
    assert state.values["f"].status is FieldStatus.GUELTIG


def test_unklar_wird_ueber_normalisierten_kandidaten_match_aufgeloest():
    # Konflikt-Kandidat "1200" wird über NORMALISIERTE Gleichheit bestätigt:
    # "100 pro Monat" normalisiert ebenfalls zu "1200" — kein exakter
    # String-Match auf den Rohwert nötig (Gesamt-Review F3).
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("menge", "Wie oft?", typ=ZAHL),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({
        "600 pro Jahr": [ExtractionCandidate("menge", "600 pro Jahr")],
        "1200 pro Jahr": [ExtractionCandidate("menge", "1200 pro Jahr")],
        "100 pro Monat": [ExtractionCandidate("menge", "100 pro Monat")],
    })
    extract_and_merge(state, "600 pro Jahr", "m1", paket, llm)
    extract_and_merge(state, "1200 pro Jahr", "m2", paket, llm)
    assert state.values["menge"].status is FieldStatus.UNKLAR
    extract_and_merge(state, "100 pro Monat", "m3", paket, llm)
    fv = state.values["menge"]
    assert fv.value == "1200"
    assert fv.status is FieldStatus.GUELTIG
    assert fv.candidates == [Candidate("600", "m1")]


def test_klaerung_erkennt_normalisierte_gleichheit():
    # "50 pro Monat" und "600" sind nach Normalisierung DERSELBE Wert —
    # die Wiederholung darf keinen Konflikt (UNKLAR) erzeugen.
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("menge", "Wie oft?", typ=ZAHL),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({
        "50 pro Monat": [ExtractionCandidate("menge", "50 pro Monat")],
        "600 pro Jahr": [ExtractionCandidate("menge", "600 pro Jahr")],
    })
    extract_and_merge(state, "50 pro Monat", "m1", paket, llm)
    extract_and_merge(state, "600 pro Jahr", "m2", paket, llm)
    assert state.values["menge"].value == "600"
    assert state.values["menge"].status is FieldStatus.GUELTIG
    assert state.values["menge"].candidates == []
