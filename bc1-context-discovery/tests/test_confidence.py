from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_core.package import TOY_PROZESS, FieldSpec, UseCasePackage
from bc1_core.confidence import confidence_check

def _state_with(**felder):
    st = SessionState(session_id="s1", schema_version="0.1")
    for name, status in felder.items():
        st.values[name] = FieldValue(value="x", status=status)
    return st

def test_empty_state_all_required_open():
    res = confidence_check(SessionState("s1", "0.1"), TOY_PROZESS)
    assert res.completeness == 0.0
    assert res.offene_pflichtfelder == ["prozess_name", "ausloeser", "haeufigkeit"]

def test_completeness_counts_only_gueltig():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.UNGUELTIG,
                     haeufigkeit=FieldStatus.GUELTIG)
    res = confidence_check(st, TOY_PROZESS)
    assert res.completeness == 2 / 3
    assert res.offene_pflichtfelder == ["ausloeser"]

# UNKLAR ist weder erfüllt noch erledigt: zählt nicht in die Vollständigkeit
# und bleibt ein offenes Pflichtfeld (Invariante „erklärbare Status").
def test_unklar_zaehlt_nicht_als_erfuellt_und_bleibt_offen():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.UNKLAR,
                     haeufigkeit=FieldStatus.GUELTIG)
    res = confidence_check(st, TOY_PROZESS)
    assert res.completeness == 2 / 3
    assert res.offene_pflichtfelder == ["ausloeser"]
    assert res.ungeloeste_felder == []

def test_ungeloest_is_not_open_but_listed():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.GUELTIG,
                     haeufigkeit=FieldStatus.UNGELOEST)
    res = confidence_check(st, TOY_PROZESS)
    assert res.offene_pflichtfelder == []
    assert res.ungeloeste_felder == ["haeufigkeit"]

# Ohne Pflichtfelder ist die gezählte Vollständigkeit per Definition 1.0
# (0/0 darf nicht crashen und nicht 0.0 melden).
def test_paket_ohne_pflichtfelder_ist_vollstaendig():
    nur_optional = UseCasePackage(
        name="nur_optional",
        schema_version="0.1",
        fields=(FieldSpec("notiz", "Sonstiges?", required=False),),
    )
    res = confidence_check(SessionState("s1", "0.1"), nur_optional)
    assert res.completeness == 1.0
    assert res.offene_pflichtfelder == []

# statuses ist das vollständige Mapping ALLER Paketfelder (auch optionaler),
# fehlende Einträge defaulten auf FEHLT — Task 8 gibt es 1:1 nach außen.
def test_statuses_umfasst_alle_paketfelder_mit_fehlt_default():
    res = confidence_check(SessionState("s1", "0.1"), TOY_PROZESS)
    assert res.statuses == {
        "prozess_name": FieldStatus.FEHLT,
        "ausloeser": FieldStatus.FEHLT,
        "haeufigkeit": FieldStatus.FEHLT,
        "notiz": FieldStatus.FEHLT,
    }

def test_optionales_feld_kann_ungeloest_sein():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.GUELTIG,
                     haeufigkeit=FieldStatus.GUELTIG,
                     notiz=FieldStatus.UNGELOEST)
    res = confidence_check(st, TOY_PROZESS)
    assert res.completeness == 1.0
    assert res.ungeloeste_felder == ["notiz"]

# state.values-Einträge ohne Paket-Gegenstück (z. B. nach Paket-Wechsel)
# werden bewusst still ignoriert — Review-Entscheidung Task 4, plan-gemäß.
def test_unbekannte_state_eintraege_werden_ignoriert():
    st = _state_with(prozess_name=FieldStatus.GUELTIG,
                     ausloeser=FieldStatus.GUELTIG,
                     haeufigkeit=FieldStatus.GUELTIG)
    st.values["altes_feld"] = FieldValue(value="x", status=FieldStatus.UNGELOEST)
    res = confidence_check(st, TOY_PROZESS)
    assert "altes_feld" not in res.statuses
    assert res.ungeloeste_felder == []
    assert res.completeness == 1.0
