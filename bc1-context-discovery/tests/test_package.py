from bc1_core.package import UseCasePackage, FieldSpec, TOY_PROZESS

def test_required_fields_excludes_optional_and_keeps_order():
    namen = [f.name for f in TOY_PROZESS.required_fields()]
    assert namen == ["prozess_name", "ausloeser", "haeufigkeit"]

def test_field_lookup():
    assert TOY_PROZESS.field("ausloeser").question != ""
    assert TOY_PROZESS.field("gibt_es_nicht") is None

def test_validator_runs():
    h = TOY_PROZESS.field("haeufigkeit")
    assert h.validator("100 mal") is True
    assert h.validator("oft") is False
