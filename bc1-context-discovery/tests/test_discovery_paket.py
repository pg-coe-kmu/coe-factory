"""Integrität des Discovery-Pakets gegen die Spec-Feldliste (P3)."""
import pytest

from bc1_core.core import PaketKonfliktError, process_turn
from bc1_core.llm import FakeLLM
from bc1_core.store import InMemoryStateStore
from bc1_service.discovery_paket import (
    MAX_ROUNDS_DISCOVERY,
    SCHEMA_VERSION,
    baue_discovery_paket,
)

MANDANT = "11111111-1111-1111-1111-111111111111"

MUSS_FELDER = [
    "request_intent", "request_goal", "scope_focus",
    "process_name", "process_owner_role", "process_id", "process_steps",
    "trigger_text", "input_text", "input_format", "output_text",
    "frequency_per_year", "executions_per_run",
    "total_duration_minutes", "focus_step", "focus_step_duration_minutes",
    "focus_step_duration_source", "focus_step_duration_confidence_pct",
    "focus_step_roles", "focus_step_systems", "focus_step_media_break",
    "documentation_status", "standardization_level",
    "data_availability_score", "stability_score", "pii_involved",
]

PASSIVE_FELDER = [
    "pain_level", "process_category", "output_format", "seasonal_peaks",
    "step_frequency_per_year", "systems_integrated", "digital_logging",
    "variant_share_pct", "rule_based_score", "acceptance_score",
    "automation_potential_estimate_pct", "upstream_process",
    "downstream_process", "interface_data", "approval_steps",
    "error_hotspots", "open_remarks",
]


def test_alle_muss_felder_der_spec_sind_required():
    paket = baue_discovery_paket()
    for name in MUSS_FELDER:
        spec = paket.field(name)
        assert spec is not None, f"Muss-Feld fehlt: {name}"
        assert spec.required, f"Muss-Feld nicht required: {name}"
    assert len([f for f in paket.fields if f.required]) == len(MUSS_FELDER)


def test_alle_passiven_felder_sind_optional():
    paket = baue_discovery_paket()
    for name in PASSIVE_FELDER:
        spec = paket.field(name)
        assert spec is not None, f"Passives Feld fehlt: {name}"
        assert not spec.required, f"Passives Feld faelschlich required: {name}"
    assert len(paket.fields) == len(MUSS_FELDER) + len(PASSIVE_FELDER)


def test_paket_metadaten():
    paket = baue_discovery_paket()
    assert paket.name == "discovery"
    assert paket.schema_version == SCHEMA_VERSION == "1.0"
    assert paket.max_rounds == MAX_ROUNDS_DISCOVERY == 60
    # Ohne Snapshot (None oder leere Liste) bleibt die Version unverändert —
    # der Fingerprint kommt erst mit echten Prozessen ins Spiel.
    assert baue_discovery_paket([]).schema_version == "1.0"


def test_b4_mit_snapshot_wird_auswahl_ueber_die_ids():
    paket = baue_discovery_paket([("KP-01", "Angebotserstellung"), ("KP-02", "Onboarding")])
    spec = paket.field("process_id")
    assert spec.typ.validator("KP-01") is True
    assert spec.typ.validator("KP-99") is False
    assert spec.typ.normalisiere("kp-02") == "KP-02"
    assert "KP-01 = Angebotserstellung" in spec.question


def test_b4_ohne_snapshot_ist_freitext():
    spec = baue_discovery_paket(None).field("process_id")
    assert spec.typ.validator("irgendein Prozess") is True


def test_b4_snapshot_fingerprint_in_schema_version():
    # Codex-Repro: B4-Optionen kommen aus dem mutierbaren BC0-Snapshot, die
    # Paket-Identität (schema_version) muss den Snapshot-Inhalt spiegeln,
    # sonst validiert eine fortgesetzte Session gegen einen anderen
    # Options-Satz als den, mit dem sie gestartet wurde.
    mit_kp01 = baue_discovery_paket([("KP-01", "X")])
    assert mit_kp01.schema_version.startswith("1.0+kp-")
    # Verifikations-Critical (Codex-Residuum, Fix-Welle 5): 8 Hex-Zeichen
    # (32 Bit) sind kollisionsanfällig — Codex hat real zwei unterschiedliche
    # Prozess-IDs mit identischem 8-Hex-Fingerprint gefunden (siehe unten),
    # der Paket-Guard griff dann NICHT. Fix: 16 Hex-Zeichen (64 Bit).
    assert len(mit_kp01.schema_version.split("+kp-", 1)[1]) == 16

    gleich = baue_discovery_paket([("KP-01", "X")])
    assert gleich.schema_version == mit_kp01.schema_version

    anders = baue_discovery_paket([("KP-02", "Y")])
    assert anders.schema_version != mit_kp01.schema_version

    # Codex-Kollisions-Repro: unter dem alten 8-Hex-Fingerprint lieferten
    # diese beiden unterschiedlichen Prozess-IDs denselben Wert (1.0+kp-
    # a1036665) — eine mit KP-60702 gestartete Session hätte unbemerkt mit
    # KP-71431 fortgesetzt werden können. Mit 16 Hex müssen sie sich
    # unterscheiden.
    kollision_a = baue_discovery_paket([("KP-60702", "X")])
    kollision_b = baue_discovery_paket([("KP-71431", "X")])
    assert kollision_a.schema_version != kollision_b.schema_version


def test_b4_fingerprint_haengt_nur_von_den_prozess_ids_ab():
    # Verifikations-Minor: der Kommentar in baue_discovery_paket() sagt
    # "paketrelevant ist der Options-INHALT (welche IDs gültig sind)" — die
    # Implementierung hashte aber sorted(prozesse), also (ID, Name)-Paare.
    # Damit invalidierte eine reine Prozess-UMBENENNUNG im Snapshot (gleiche
    # IDs, andere Namen) laufende Sessions, obwohl der Validator nur von den
    # IDs abhängt. Fix: nur die sortierten IDs fließen in den Fingerprint.
    mit_namen_a = baue_discovery_paket([("KP-01", "Angebotserstellung")])
    mit_namen_b = baue_discovery_paket([("KP-01", "Angebotserledigung")])
    assert mit_namen_a.schema_version == mit_namen_b.schema_version


def test_b4_snapshot_wechsel_wird_vom_bestehenden_paket_guard_abgelehnt():
    # End-to-End: der Fingerprint allein bewirkt nichts — erst zusammen mit
    # dem bestehenden Paket-Guard (core.py, PaketKonfliktError) greift er:
    # eine Session, die mit Snapshot A gestartet wurde, darf nicht mit
    # Snapshot B fortgesetzt werden (Codex-Repro).
    paket_a = baue_discovery_paket([("KP-01", "X")])
    paket_b = baue_discovery_paket([("KP-02", "Y")])
    store = InMemoryStateStore()
    process_turn(store, FakeLLM(), paket_a, "s1", "m1", "hallo", company_id=MANDANT)
    with pytest.raises(PaketKonfliktError):
        process_turn(store, FakeLLM(), paket_b, "s1", "m2", "hallo", company_id=MANDANT)


def test_b4_leere_snapshot_liste_ist_ebenfalls_freitext():
    # Leere Liste fällt über Truthiness auf FREITEXT zurück wie None (Gesamt-
    # Review F5) — bisher nur implizit korrekt, hier als Vertrag gepinnt.
    spec = baue_discovery_paket([]).field("process_id")
    assert spec.typ.validator("irgendein Prozess") is True


ERWARTETE_TYPEN = {
    "request_intent": "freitext",
    "request_goal": "auswahl(zeit_sparen, fehler_senken, skalieren)",
    "scope_focus": "auswahl(ganzer_prozess, einzelner_schritt)",
    "pain_level": "skala_1_5",
    "process_name": "freitext",
    "process_category": "auswahl(steuerung, kerngeschaeft, unterstuetzung)",
    "process_owner_role": "freitext",
    "process_id": "freitext",
    "process_steps": "liste",
    "trigger_text": "freitext",
    "input_text": "freitext",
    "input_format": "auswahl(digital, papier, pdf, mail)",
    "output_text": "freitext",
    "output_format": "auswahl(system, dokument, mail)",
    "frequency_per_year": "zahl",
    "seasonal_peaks": "ja_nein",
    "step_frequency_per_year": "zahl",
    "executions_per_run": "zahl",
    "total_duration_minutes": "minuten",
    "focus_step": "freitext",
    "focus_step_duration_minutes": "minuten",
    "focus_step_duration_source": "auswahl(gemessen, geschaetzt, aus_system)",
    "focus_step_duration_confidence_pct": "prozent_0_100",
    "focus_step_roles": "liste",
    "focus_step_systems": "liste",
    "focus_step_media_break": "ja_nein",
    "systems_integrated": "ja_nein",
    "digital_logging": "ja_nein",
    "documentation_status": "skala_1_5",
    "standardization_level": "skala_1_5",
    "variant_share_pct": "prozent_0_100",
    "data_availability_score": "skala_1_5",
    "stability_score": "skala_1_5",
    "rule_based_score": "skala_1_5",
    "acceptance_score": "skala_1_5",
    "automation_potential_estimate_pct": "prozent_0_100",
    "upstream_process": "freitext",
    "downstream_process": "freitext",
    "interface_data": "freitext",
    "pii_involved": "ja_nein",
    "approval_steps": "ja_nein",
    "error_hotspots": "freitext",
    "open_remarks": "freitext",
}


def test_alle_43_felder_haben_den_erwarteten_typ():
    # Vollständige Typ-Tabelle statt Stichprobe (Gesamt-Review F4) — ein
    # Options-Tausch (z. B. C3/C5) würde hier auffallen, da der volle
    # AUSWAHL-Name inkl. Optionen geprüft wird.
    paket = baue_discovery_paket()
    assert set(ERWARTETE_TYPEN) == set(MUSS_FELDER) | set(PASSIVE_FELDER)
    assert len(ERWARTETE_TYPEN) == 43
    for name, typ_name in ERWARTETE_TYPEN.items():
        assert paket.field(name).typ.name == typ_name, name


def test_typ_stichproben_gegen_die_spec_tabelle():
    paket = baue_discovery_paket()
    assert paket.field("frequency_per_year").typ.normalisiere("50 pro Monat") == "600"
    assert paket.field("total_duration_minutes").typ.normalisiere("2 Stunden") == "120"
    assert paket.field("pii_involved").typ.normalisiere("Ja.") == "ja"
    assert paket.field("request_goal").typ.validator("zeit_sparen") is True
    assert paket.field("request_goal").typ.validator("abkuerzen") is False
    assert paket.field("documentation_status").typ.validator("6") is False
