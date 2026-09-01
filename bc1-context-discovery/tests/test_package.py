from dataclasses import FrozenInstanceError

import pytest

from bc1_core.package import UseCasePackage, FieldSpec, TOY_PROZESS
from bc1_core.feldtypen import FREITEXT

def test_required_fields_excludes_optional_and_keeps_order():
    namen = [f.name for f in TOY_PROZESS.required_fields()]
    assert namen == ["prozess_name", "ausloeser", "haeufigkeit"]

def test_field_lookup():
    assert TOY_PROZESS.field("ausloeser").question != ""
    assert TOY_PROZESS.field("gibt_es_nicht") is None

def test_field_lookup_liefert_genau_das_angefragte_feld():
    for spec in TOY_PROZESS.fields:
        assert TOY_PROZESS.field(spec.name) is spec

def test_validator_runs():
    h = TOY_PROZESS.field("haeufigkeit")
    assert h.validator("100 mal") is True
    assert h.validator("oft") is False

# TOY_PROZESS ist eine geteilte Modul-Instanz — wäre sie veränderlich,
# könnte ein Test den Zustand aller folgenden Tests vergiften (belegt im Audit).
def test_paket_und_feldspecs_sind_unveraenderlich():
    with pytest.raises(FrozenInstanceError):
        TOY_PROZESS.field("notiz").required = True
    with pytest.raises(FrozenInstanceError):
        TOY_PROZESS.name = "anders"
    assert isinstance(TOY_PROZESS.fields, tuple)

# Audit-Befund: field() nimmt still den ersten Treffer — bei doppelten
# Feldnamen liefe der Validator des zweiten Specs nie (falsches GUELTIG).
def test_doppelte_feldnamen_werden_bei_konstruktion_abgelehnt():
    with pytest.raises(ValueError):
        UseCasePackage(
            name="p",
            schema_version="0.1",
            fields=(
                FieldSpec("betrag", "Wie hoch?"),
                FieldSpec("betrag", "Wie hoch genau?",
                          validator=lambda v: v.isdigit()),
            ),
        )

# Review-Befund: identitaetskritisch wirkt nur ueber required_fields() —
# auf einem optionalen Feld waere die Flagge ein stiller No-op (kein Fail-safe,
# kein Abbruch, Session laeuft ins Runden-Limit ohne geklaerte Identitaet).
def test_identitaetskritisch_ohne_required_wird_bei_konstruktion_abgelehnt():
    with pytest.raises(ValueError):
        UseCasePackage(
            name="p",
            schema_version="0.1",
            fields=(
                FieldSpec("tp_id", "Welcher Schritt?",
                          required=False, identitaetskritisch=True),
            ),
        )

def test_identitaetskritisch_mit_required_baut_problemlos():
    paket = UseCasePackage(
        name="p",
        schema_version="0.1",
        fields=(
            FieldSpec("tp_id", "Welcher Schritt?",
                      required=True, identitaetskritisch=True),
        ),
    )
    assert paket.field("tp_id").identitaetskritisch is True

def test_fieldspec_typ_default_ist_freitext():
    spec = FieldSpec("f", "?")
    assert spec.typ is FREITEXT

def test_package_max_rounds_default_ist_20():
    assert TOY_PROZESS.max_rounds == 20
