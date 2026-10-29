"""Abnahmetest: Nachspiel der Generalprobe (Kurzantworten landen im gefragten Feld)."""
from bc1_core.core import process_turn
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.store import InMemoryStateStore
from bc1_core.types import FieldStatus, SessionStatus
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket

MANDANT = "11111111-1111-1111-1111-111111111111"

# Lokal nachgebaut (nach dem Muster von KONTEXT in test_discovery_paket.py);
# Rollen sind Pflicht, sonst ist B3 eine AUSWAHL() ohne Optionen und nie gültig.
KONTEXT = Bc0Kontext(
    company_id=MANDANT,
    teilprozesse=(("KP-01.TP-1", "Erfassen"), ("KP-01.TP-2", "Pruefen")),
    system_ids=("S-01", "S-02"),
    rollen=(("R-01", "Leitung"), ("R-02", "Fachbereich")),
    prozesse=(("KP-01", "Auftrag"), ("KP-02", "Einkauf")))

START = "Wir moechten das regelmaessige Erfassen von Vorgaengen vereinfachen."

# Die elf Pflichtfelder, die schon die Startnachricht liefert.
START_FELDER = {
    "request_intent": "Erfassen von Vorgaengen vereinfachen",
    "request_goal": "zeit_sparen",
    "scope_focus": "einzelner_schritt",
    "process_name": "Vorgangsbearbeitung",
    "process_owner_role": "R-01",
    "process_id": "KP-01",
    "process_steps": "Erfassen, Pruefen",
    "trigger_text": "Eingang einer Anfrage",
    "input_text": "Formular mit Stammdaten",
    "input_format": "digital",
    "output_text": "Bearbeiteter Vorgang",
}

ROLLEN_TEXT = "Leitung und Fachbereich sind beteiligt"

# (gefragtes Feld, Antworttext, erwarteter Wert) in der Reihenfolge des Pakets.
KURZ_TURNS = [
    ("frequency_per_year", "2 pro Monat", "24"),
    ("executions_per_run", "1", "1"),
    ("total_duration_minutes", "40 Stunden", "2400"),
    ("focus_step", "KP-01.TP-1", "KP-01.TP-1"),
    ("focus_step_duration_minutes", "3 Stunden", "180"),
    ("focus_step_duration_source", "geschaetzt", "geschaetzt"),
    ("focus_step_duration_confidence_pct", "70", "70"),
    ("focus_step_roles", ROLLEN_TEXT, "Leitung, Fachbereich"),
    ("focus_step_systems", "S-01, S-02", "S-01, S-02"),
    ("focus_step_media_break", "ja", "ja"),
    ("documentation_status", "2", "2"),
    ("standardization_level", "4", "4"),
    ("data_availability_score", "3", "3"),
    ("stability_score", "4", "4"),
    ("pii_involved", "Ja", "ja"),
]


def test_nachspiel_kurzantworten_fuellen_alle_pflichtfelder():
    paket = baue_discovery_paket(kontext=KONTEXT)
    llm = FakeLLM({
        START: [ExtractionCandidate(name, wert)
                for name, wert in START_FELDER.items()],
        ROLLEN_TEXT: [ExtractionCandidate("focus_step_roles",
                                          "Leitung, Fachbereich")],
        "S-01, S-02": [ExtractionCandidate("focus_step_systems", "S-01, S-02")],
    })
    store = InMemoryStateStore()

    antwort = process_turn(store, llm, paket, "s1", "m-start", START,
                           company_id=MANDANT)
    assert antwort["status"] == "frage"
    assert antwort["payload"]["feld"] == "frequency_per_year"

    for nr, (feld, text, _erwartet) in enumerate(KURZ_TURNS):
        assert antwort["payload"]["feld"] == feld
        antwort = process_turn(store, llm, paket, "s1", f"m-{nr}", text,
                               company_id=MANDANT)

    assert antwort["status"] == "fertig"
    assert antwort["payload"]["pflicht_erfasst"] == 26
    state = store.load("s1")
    assert state.status is SessionStatus.FERTIG

    for name, wert in START_FELDER.items():
        feld = state.values[name]
        assert (feld.status, feld.value) == (FieldStatus.GUELTIG, wert), name
        assert feld.source_message_id == "m-start", name
    for nr, (name, _text, erwartet) in enumerate(KURZ_TURNS):
        feld = state.values[name]
        assert (feld.status, feld.value) == (FieldStatus.GUELTIG, erwartet), name
        assert feld.source_message_id == f"m-{nr}", name
