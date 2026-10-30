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


class _ZaehlendesLLM(FakeLLM):
    def __init__(self, extractions):
        super().__init__(extractions)
        self.nachrichten = []

    def extract(self, message, package, state):
        self.nachrichten.append(message)
        return super().extract(message, package, state)


def _bis_vor(gefragt, llm, store):
    """Spielt Start und Kurzantworten, bis `gefragt` das gefragte Feld ist."""
    paket = baue_discovery_paket(kontext=KONTEXT)
    antwort = process_turn(store, llm, paket, "s1", "m-start", START,
                           company_id=MANDANT)
    for nr, (feld, text, _erwartet) in enumerate(KURZ_TURNS):
        if feld == gefragt:
            break
        antwort = process_turn(store, llm, paket, "s1", f"m-{nr}", text,
                               company_id=MANDANT)
    assert antwort["payload"]["feld"] == gefragt
    return paket


def _skript(extra=()):
    return {
        START: [ExtractionCandidate(name, wert) for name, wert in START_FELDER.items()],
        ROLLEN_TEXT: [ExtractionCandidate("focus_step_roles", "Leitung, Fachbereich")],
        "S-01, S-02": [ExtractionCandidate("focus_step_systems", "S-01, S-02")],
        **dict(extra),
    }


def test_nachspiel_generalprobe2_natuerlich():
    # Spec 7.8: ein Teilprozessname auf die E5-Frage landet ohne KI als Kennung.
    llm = _ZaehlendesLLM(_skript())
    store = InMemoryStateStore()
    paket = _bis_vor("focus_step", llm, store)
    antwort = process_turn(store, llm, paket, "s1", "m-e5", "Erfassen",
                           company_id=MANDANT)
    assert "Erfassen" not in llm.nachrichten
    assert store.load("s1").values["focus_step"].value == "KP-01.TP-1"
    assert antwort["payload"]["feld"] == "focus_step_duration_minutes"

    # F3 „Ja Systeme wechseln“: bringt die KI „ja“, gilt „ja“ ...
    satz = "Ja Systeme wechseln"
    llm = _ZaehlendesLLM(_skript({satz: [ExtractionCandidate("focus_step_media_break", "ja")]}))
    store = InMemoryStateStore()
    paket = _bis_vor("focus_step_media_break", llm, store)
    process_turn(store, llm, paket, "s1", "m-f3", satz, company_id=MANDANT)
    feld = store.load("s1").values["focus_step_media_break"]
    assert (feld.status, feld.value) == (FieldStatus.GUELTIG, "ja")

    # ... reicht sie den Satz woertlich durch, entsteht eine Nachfrage, kein Wert.
    llm = _ZaehlendesLLM(_skript({satz: [ExtractionCandidate("focus_step_media_break", satz)]}))
    store = InMemoryStateStore()
    paket = _bis_vor("focus_step_media_break", llm, store)
    antwort = process_turn(store, llm, paket, "s1", "m-f3", satz, company_id=MANDANT)
    assert antwort["status"] == "frage"
    assert antwort["payload"]["feld"] == "focus_step_media_break"
    assert store.load("s1").values["focus_step_media_break"].status is FieldStatus.UNGUELTIG


def test_nachspiel_nackte_zahl_bei_d1_gilt_ohne_nachfrage():
    # Vertrag: eine nackte Zahl bei D1 gilt als pro Jahr; die KI gibt sie
    # unveraendert zurueck (SYSTEM_EXTRAKTION), der Normalisierer nimmt sie an.
    llm = _ZaehlendesLLM(_skript({"300": [
        ExtractionCandidate("frequency_per_year", "300")]}))
    store = InMemoryStateStore()
    paket = _bis_vor("frequency_per_year", llm, store)
    antwort = process_turn(store, llm, paket, "s1", "m-d1", "300",
                           company_id=MANDANT)
    feld = store.load("s1").values["frequency_per_year"]
    assert (feld.status, feld.value) == (FieldStatus.GUELTIG, "300")
    assert antwort["payload"]["feld"] == "executions_per_run"


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
