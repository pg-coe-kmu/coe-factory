"""
BC2 · Strukturierte Ausgabe an der Modellnaht (#319).

Je Schritt ein Antwortschema neben der Anweisung; :class:`SdkModell` gibt es als
``output_config`` an die API, :class:`CliModell` als ``--json-schema`` an die CLI.

Was hier geprüft wird, kann kein echter Aufruf zeigen, ohne zu kosten:

- dass die Schemas in die Grenzen der API passen — sonst antwortet sie mit 400,
  und das erst im Betrieb;
- dass Schema und Ausgabeteil der Anweisung dieselbe Form beschreiben — die
  Anweisung bleibt, weil die CLI nicht beschränkt dekodiert und weil das Modell
  die Felder dort erklärt bekommt;
- dass die Antworten, mit denen die übrigen Tests die Kette fahren, schemagültig
  sind — sonst prüften sie eine Form, die im Betrieb nicht mehr ankommt;
- dass jeder Schritt sein Schema mitgibt und beide Wege es richtig weiterreichen.

Ob die API die Schemas annimmt, zeigt erst ein echter Lauf.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import types

import pytest
from jsonschema import Draft202012Validator

from ausarbeitung import arbeite_aus
from ausarbeitung.anweisung import ANTWORTSCHEMA as AUSARBEITUNG
from ausarbeitung.anweisung import ANWEISUNG as AUSARBEITUNG_ANWEISUNG
from bewertung import bewerte
from bewertung.anweisung import ANTWORTSCHEMA as BEWERTUNG
from bewertung.anweisung import ANWEISUNG as BEWERTUNG_ANWEISUNG
from erkennung import CliModell, Doppelgaenger, SdkModell, erkenne
from erkennung.anweisung import ANWEISUNG as ERKENNUNG_ANWEISUNG
from erkennung.anweisung import VORGAENGER, antwortschema
from test_ausarbeitung import _gerechnet
from test_bewertung import _ausgearbeitet, _bestand, _erkannt, _gut, _kennungen

SCHEMAS = {
    "erkennung": antwortschema(),
    "erkennung mit vorgaengern": antwortschema(mit_vorgaenger=True),
    "bewertung": BEWERTUNG,
    "ausarbeitung": AUSARBEITUNG,
}

#: Was die API an einem Antwortschema nicht annimmt (structured-outputs, Stand
#: 10.10.2026). ``pattern`` ginge, aber ohne Wortgrenzen — das Rechenverbot
#: bleibt darum in Python.
VERBOTEN = {
    "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "multipleOf", "maxItems", "uniqueItems", "patternProperties",
}


def _knoten(schema: dict, pfad: str = "$"):
    yield pfad, schema
    for name, unter in (schema.get("properties") or {}).items():
        yield from _knoten(unter, f"{pfad}.{name}")
    if isinstance(schema.get("items"), dict):
        yield from _knoten(schema["items"], f"{pfad}[]")
    for i, unter in enumerate(schema.get("anyOf") or []):
        yield from _knoten(unter, f"{pfad}|{i}")


def _ist_union(schema: dict) -> bool:
    return isinstance(schema.get("type"), list) or "anyOf" in schema or (
        None in (schema.get("enum") or []) and len(schema["enum"]) > 1
    )


# ======================================================================
# Die Grenzen der API
# ======================================================================


@pytest.mark.parametrize("name", SCHEMAS)
def test_das_schema_passt_in_die_grenzen_der_api(name):
    schema = SCHEMAS[name]
    Draft202012Validator.check_schema(schema)
    verstoesse, optional, unionen = [], 0, 0
    for pfad, k in _knoten(schema):
        if VERBOTEN & set(k):
            verstoesse.append(f"{pfad}: {sorted(VERBOTEN & set(k))}")
        if "$ref" in k or "$defs" in k:
            verstoesse.append(f"{pfad}: keine Verweise — Rekursion nimmt die API nicht")
        if k.get("minItems", 0) not in (0, 1):
            verstoesse.append(f"{pfad}: minItems nur 0 oder 1")
        if k.get("type") == "object":
            if k.get("additionalProperties") is not False:
                verstoesse.append(f"{pfad}: additionalProperties muss false sein")
            optional += len(set(k["properties"]) - set(k.get("required", [])))
        unionen += _ist_union(k)
    assert not verstoesse
    assert optional <= 24, f"{optional} optionale Felder, die API nimmt höchstens 24"
    assert unionen <= 16, f"{unionen} Union-Typen, die API nimmt höchstens 16"


@pytest.mark.parametrize("name", SCHEMAS)
def test_jedes_feld_ist_pflicht(name):
    """Optionale Felder rücken in der Ausgabe nach hinten und zählen gegen die
    24 — was fehlen darf, steht als ``null`` da."""
    for pfad, k in _knoten(SCHEMAS[name]):
        if k.get("type") == "object":
            assert k["required"] == list(k["properties"]), pfad


# ======================================================================
# Schema und Anweisung beschreiben dieselbe Form
# ======================================================================


def _beispiel(anweisung: str) -> dict:
    """Das JSON-Beispiel aus dem Ausgabeteil einer Anweisung."""
    teil = anweisung.split("## Ausgabe", 1)[1]
    return json.loads(teil[teil.index("{"): teil.rindex("}") + 1])


def _form(wert):
    """Nur die Schlüssel, rekursiv — die Werte im Beispiel sind Platzhalter.

    Eine leere Liste im Beispiel (``abhaengigkeiten``) sagt nichts über ihre
    Einträge; sie wird als ``...`` geführt und passt zu jeder Liste.
    """
    if isinstance(wert, dict):
        return {k: _form(v) for k, v in wert.items()}
    if wert == []:
        return ...
    if isinstance(wert, list) and isinstance(wert[0], dict):
        return [_form(wert[0])]
    return None


def _passt(schema_form, beispiel_form) -> bool:
    if beispiel_form is ...:
        return isinstance(schema_form, list) or schema_form is None
    if isinstance(beispiel_form, dict):
        return (
            isinstance(schema_form, dict)
            and list(schema_form) == list(beispiel_form)
            and all(_passt(schema_form[k], v) for k, v in beispiel_form.items())
        )
    if isinstance(beispiel_form, list):
        return isinstance(schema_form, list) and _passt(schema_form[0], beispiel_form[0])
    return schema_form == beispiel_form


def _form_des_schemas(schema: dict):
    if schema.get("type") == "object":
        return {k: _form_des_schemas(v) for k, v in schema["properties"].items()}
    if schema.get("type") == "array" and schema["items"].get("type") == "object":
        return [_form_des_schemas(schema["items"])]
    return None


@pytest.mark.parametrize(
    "anweisung, schema",
    [
        (ERKENNUNG_ANWEISUNG, antwortschema()),
        (BEWERTUNG_ANWEISUNG, BEWERTUNG),
        (AUSARBEITUNG_ANWEISUNG, AUSARBEITUNG),
    ],
    ids=["erkennung", "bewertung", "ausarbeitung"],
)
def test_schema_und_anweisung_nennen_dieselben_felder(anweisung, schema):
    # Auch die Reihenfolge: die API gibt Pflichtfelder in Schema-Reihenfolge aus.
    assert _passt(_form_des_schemas(schema), _form(_beispiel(anweisung)))


def test_die_vorgaenger_stehen_im_schema_wie_in_der_anweisung():
    zeile = re.search(r"\{\"kandidat\".*?\}", VORGAENGER).group(0)
    vorgaenger = antwortschema(mit_vorgaenger=True)["properties"]["vorgaenger"]
    assert list(vorgaenger["items"]["properties"]) == list(json.loads(zeile))


# ======================================================================
# Die Antworten der übrigen Tests kämen so auch über die API
# ======================================================================


@pytest.mark.parametrize(
    "schema, antwort",
    [
        (antwortschema(), _erkannt()),
        (BEWERTUNG, _gut()),
        (AUSARBEITUNG, _ausgearbeitet("P1", "P2", abhaengig={"P2": "P1"})),
    ],
    ids=["erkennung", "bewertung", "ausarbeitung"],
)
def test_die_testantworten_sind_schemagueltig(schema, antwort):
    fehler = sorted(Draft202012Validator(schema).iter_errors(antwort), key=str)
    assert not fehler, [f"{list(f.path)}: {f.message}" for f in fehler]


@pytest.mark.parametrize(
    "schema, antwort",
    [
        (antwortschema(), {**_erkannt(), "potenziale": [
            {**_erkannt()["potenziale"][0], "loesungsklasse": "Dokumentenverarbeitung"}
        ]}),
        (BEWERTUNG, {"bewertungen": [{**_gut()["bewertungen"][0], "nutzwert": {
            **_gut()["bewertungen"][0]["nutzwert"],
            "qualitaet": {"wert": 11, "begruendung": "zu hoch"},
        }}]}),
        (AUSARBEITUNG, {**_ausgearbeitet("P1"), "anmerkung": "ein Feld zu viel"}),
    ],
    ids=["klasse ausserhalb des vertrags", "note ueber zehn", "fremdes feld"],
)
def test_das_schema_haelt_was_der_waechter_sonst_mahnte(schema, antwort):
    assert list(Draft202012Validator(schema).iter_errors(antwort))


# ======================================================================
# Jeder Schritt gibt sein Schema mit
# ======================================================================


def test_erkennung_und_bewertung_geben_ihr_schema_mit():
    bestand = _bestand()
    modell = Doppelgaenger([_erkannt(), _gut()])
    erkennung = erkenne(bestand, modell)
    bewerte(erkennung, bestand, modell, urteile=1, kennung=_kennungen())
    assert modell.schemas == [antwortschema(), BEWERTUNG]


def test_die_ausarbeitung_gibt_ihr_schema_mit():
    bestand, erkennung, bewertung, lauf, ansicht = _gerechnet()
    modell = Doppelgaenger([_ausgearbeitet("P1", "P2")])
    arbeite_aus(lauf, ansicht.potenziale, erkennung, bewertung.kennungen, bestand, modell)
    assert modell.schemas == [AUSARBEITUNG]


def test_eine_wiederholung_fragt_mit_demselben_schema():
    falsch = {**_erkannt(), "potenziale": [
        {**_erkannt()["potenziale"][0], "ausgangslage": "Dauert 540 Stunden im Jahr."}
    ]}
    modell = Doppelgaenger([falsch, _erkannt()])
    erkenne(_bestand(), modell)
    assert modell.schemas == [antwortschema(), antwortschema()]


# ======================================================================
# Die beiden Wege reichen es weiter
# ======================================================================


class _Klient:
    """Steht für ``anthropic.Anthropic`` und merkt sich den Aufruf."""

    aufrufe: list[dict] = []
    antwort = None

    def __init__(self, api_key: str) -> None:
        self.messages = self

    def create(self, **kwargs):
        _Klient.aufrufe.append(kwargs)
        return _Klient.antwort


def _sdk_antwort(text: str, stop_reason: str = "end_turn"):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=types.SimpleNamespace(input_tokens=10, output_tokens=20),
    )


@pytest.fixture
def anthropic_attrappe(monkeypatch):
    _Klient.aufrufe = []
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Klient))
    return _Klient


def test_sdk_gibt_das_schema_als_output_config_weiter(anthropic_attrappe):
    anthropic_attrappe.antwort = _sdk_antwort(json.dumps(_gut()))
    antwort = SdkModell(schluessel="test").frage("Frage", schema=BEWERTUNG)
    assert anthropic_attrappe.aufrufe[0]["output_config"] == {
        "format": {"type": "json_schema", "schema": BEWERTUNG}
    }
    assert antwort.ergebnis == _gut()


def test_sdk_ohne_schema_fragt_wie_bisher(anthropic_attrappe):
    anthropic_attrappe.antwort = _sdk_antwort("```json\n" + json.dumps(_gut()) + "\n```")
    antwort = SdkModell(schluessel="test").frage("Frage")
    assert "output_config" not in anthropic_attrappe.aufrufe[0]
    assert antwort.ergebnis == _gut()


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
def test_sdk_abbruch_und_ablehnung_bleiben_eigene_fehler(anthropic_attrappe, stop_reason):
    # Auch ein lesbarer Rest gilt nicht: hier garantiert das Schema nichts.
    anthropic_attrappe.antwort = _sdk_antwort(json.dumps(_gut()), stop_reason)
    antwort = SdkModell(schluessel="test").frage("Frage", schema=BEWERTUNG)
    assert antwort.ergebnis is None
    assert f"stop_reason={stop_reason}" in antwort.lesefehler


def _cli(monkeypatch, huelle: dict, returncode: int = 0) -> list:
    befehle = []

    def lauf(befehl, **_):
        befehle.append(befehl)
        return subprocess.CompletedProcess(befehl, returncode, json.dumps(huelle), "")

    monkeypatch.setattr(subprocess, "run", lauf)
    return befehle


def test_cli_gibt_das_schema_mit_und_liest_structured_output(monkeypatch):
    befehle = _cli(monkeypatch, {
        "type": "result", "subtype": "success", "is_error": False,
        "result": "egal", "structured_output": _gut(),
    })
    antwort = CliModell().frage("Frage", schema=BEWERTUNG)
    befehl = befehle[0]
    assert befehl[befehl.index("--output-format") + 1] == "json"
    assert json.loads(befehl[befehl.index("--json-schema") + 1]) == BEWERTUNG
    assert befehl[-1] == "Frage"
    assert antwort.ergebnis == _gut()


@pytest.mark.parametrize(
    "huelle, returncode, erwartet",
    [
        ({"subtype": "error_max_structured_output_retries", "is_error": True}, 1,
         "error_max_structured_output_retries"),
        ({"subtype": "success", "is_error": False, "result": "{}"}, 0,
         "ohne structured_output"),
    ],
    ids=["aufgegeben", "erfolg ohne ergebnis"],
)
def test_cli_ohne_schemagueltiges_ergebnis_ist_ein_lesefehler(
    monkeypatch, huelle, returncode, erwartet
):
    _cli(monkeypatch, huelle, returncode)
    antwort = CliModell().frage("Frage", schema=BEWERTUNG)
    assert antwort.ergebnis is None
    assert erwartet in antwort.lesefehler
