from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import TOY_PROZESS, UseCasePackage, FieldSpec
from bc1_core.confidence import confidence_check
from bc1_core.dialog import (GRUND_NACHFRAGE_LIMIT, GRUND_RUNDEN_LIMIT,
                             MAX_ATTEMPTS_PER_FIELD, MAX_ROUNDS,
                             Decision, decide_next)

# Die grund-Werte sind Wire-Vertrag Richtung BC2 — wie die Enum-Werte.
def test_grund_konstanten_sind_wire_vertrag():
    assert GRUND_NACHFRAGE_LIMIT == "nachfrage_limit_erreicht"
    assert GRUND_RUNDEN_LIMIT == "runden_limit_erreicht"

def test_asks_first_open_field_and_counts_attempt():
    st = SessionState("s1", "0.1")
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf)
    assert d.done is False
    assert d.next_field == "prozess_name"
    assert st.values["prozess_name"].attempts == 1

def test_done_when_no_open_required_fields():
    st = SessionState("s1", "0.1")
    for n in ("prozess_name", "ausloeser", "haeufigkeit"):
        st.values[n] = FieldValue(value="x", status=FieldStatus.GUELTIG)
    conf = confidence_check(st, TOY_PROZESS)
    assert decide_next(st, TOY_PROZESS, conf) == Decision(done=True)

def test_field_over_attempt_cap_becomes_ungeloest():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(status=FieldStatus.FEHLT,
                                           attempts=MAX_ATTEMPTS_PER_FIELD)
    st.values["ausloeser"] = FieldValue(value="x", status=FieldStatus.GUELTIG)
    st.values["haeufigkeit"] = FieldValue(value="3", status=FieldStatus.GUELTIG)
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf)
    assert st.values["prozess_name"].status is FieldStatus.UNGELOEST
    assert d.done is True

# Die Cap-Politik gilt nur für OFFENE Pflichtfelder — ein gültiges Feld
# mit hohem Zähler (z. B. nach Korrekturen) darf nie auf UNGELOEST kippen.
def test_gueltiges_feld_am_cap_bleibt_gueltig():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(value="x", status=FieldStatus.GUELTIG,
                                           attempts=MAX_ATTEMPTS_PER_FIELD)
    conf = confidence_check(st, TOY_PROZESS)
    decide_next(st, TOY_PROZESS, conf)
    assert st.values["prozess_name"].status is FieldStatus.GUELTIG

def test_mehrere_gecappte_felder_werden_alle_ungeloest():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(status=FieldStatus.FEHLT,
                                           attempts=MAX_ATTEMPTS_PER_FIELD)
    st.values["ausloeser"] = FieldValue(status=FieldStatus.FEHLT,
                                        attempts=MAX_ATTEMPTS_PER_FIELD)
    st.values["haeufigkeit"] = FieldValue(value="3", status=FieldStatus.GUELTIG)
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf)
    assert st.values["prozess_name"].status is FieldStatus.UNGELOEST
    assert st.values["ausloeser"].status is FieldStatus.UNGELOEST
    assert d == Decision(done=True)

# Design-Spec Z. 81: „danach Feld ungeloest + Grund" — Gate 0 soll wissen,
# WARUM ein Feld offen blieb.
def test_gecapptes_feld_traegt_grund():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(status=FieldStatus.FEHLT,
                                           attempts=MAX_ATTEMPTS_PER_FIELD)
    conf = confidence_check(st, TOY_PROZESS)
    decide_next(st, TOY_PROZESS, conf)
    fv = st.values["prozess_name"]
    assert fv.status is FieldStatus.UNGELOEST
    assert fv.grund == "nachfrage_limit_erreicht"

def test_gecapptes_feld_wird_uebersprungen_naechstes_offenes_gefragt():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(status=FieldStatus.FEHLT,
                                           attempts=MAX_ATTEMPTS_PER_FIELD)
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf)
    assert st.values["prozess_name"].status is FieldStatus.UNGELOEST
    assert d.done is False
    assert d.next_field == "ausloeser"           # nächstes offenes, nicht das gecappte

# Spec Z. 81: AUCH das Runden-Limit führt zu „ungeloest + Grund" — sonst
# verschwänden nie-gefragte Pflichtfelder spurlos aus dem Gate-0-Payload.
def test_runden_limit_markiert_alle_offenen_pflichtfelder_ungeloest():
    st = SessionState("s1", "0.1")
    st.values["prozess_name"] = FieldValue(value="x", status=FieldStatus.GUELTIG)
    st.rounds = MAX_ROUNDS
    conf = confidence_check(st, TOY_PROZESS)
    d = decide_next(st, TOY_PROZESS, conf)
    assert d == Decision(done=True)
    for name in ("ausloeser", "haeufigkeit"):    # inkl. nie angefragtem Feld
        fv = st.values[name]
        assert fv.status is FieldStatus.UNGELOEST
        assert fv.grund == "runden_limit_erreicht"

def test_done_at_round_limit_even_with_open_fields():
    st = SessionState("s1", "0.1")
    st.rounds = MAX_ROUNDS
    conf = confidence_check(st, TOY_PROZESS)
    assert decide_next(st, TOY_PROZESS, conf) == Decision(done=True)
    assert all(fv.attempts == 0 for fv in st.values.values())

def test_paket_max_rounds_uebersteuert_die_konstante():
    paket = UseCasePackage(
        name="lang", schema_version="0.1",
        fields=(FieldSpec("f1", "?"),),
        max_rounds=25,
    )
    state = SessionState("s1", "0.1")
    state.rounds = 20   # alte Grenze erreicht — Paket erlaubt mehr
    conf = confidence_check(state, paket)
    d = decide_next(state, paket, conf)
    assert d.done is False
    assert d.next_field == "f1"

def test_paket_max_rounds_kappt_wie_bisher():
    paket = UseCasePackage(
        name="kurz", schema_version="0.1",
        fields=(FieldSpec("f1", "?"),),
        max_rounds=3,
    )
    state = SessionState("s1", "0.1")
    state.rounds = 3
    conf = confidence_check(state, paket)
    d = decide_next(state, paket, conf)
    assert d.done is True
    assert state.values["f1"].status is FieldStatus.UNGELOEST
    assert state.values["f1"].grund == GRUND_RUNDEN_LIMIT
