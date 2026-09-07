"""Demo-Durchläufe der 3 MVP-Use-Cases durch EIN generisches Discovery-Paket.

Jedes Skript: 7 Nachrichten, Mehrfach-Extraktion pro Nachricht, bis fertig.
Die Werte prüfen auch die Normalisierung (BC2-Vertrag): '30 pro Monat'→'360',
'3 Stunden'→'180', '60%'→'60', 'Ja.'→'ja'.
"""
from bc1_core.core import process_turn
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.store import InMemoryStateStore
from bc1_service.discovery_paket import baue_discovery_paket


def _lauf(session_id, nachrichten):
    paket = baue_discovery_paket(None)
    llm = FakeLLM({
        text: [ExtractionCandidate(feld, wert) for feld, wert in felder]
        for text, felder in nachrichten
    })
    store = InMemoryStateStore()
    antwort = None
    for i, (text, _) in enumerate(nachrichten, start=1):
        antwort = process_turn(store, llm, paket, session_id, f"m{i}", text)
    return antwort


def _basis_skript(intent, name, owner, prozess, schritte, trigger, eingang,
                  eingangsformat, ausgang, frequenz, faelle, gesamtdauer,
                  fokus, fokusdauer, quelle, sicherheit, rollen, systeme,
                  medienbruch, doku, standard, daten, stabil, pii):
    return [
        (f"Wir wollen {intent} — es geht um den ganzen Prozess, Ziel ist Zeit sparen.", [
            ("request_intent", intent), ("request_goal", "zeit_sparen"),
            ("scope_focus", "ganzer_prozess"), ("process_name", name)]),
        ("Verantwortlich und Ablauf.", [
            ("process_owner_role", owner), ("process_id", prozess),
            ("process_steps", schritte)]),
        ("Auslöser, Eingang und Ergebnis.", [
            ("trigger_text", trigger), ("input_text", eingang),
            ("input_format", eingangsformat), ("output_text", ausgang)]),
        ("Mengen und Dauer.", [
            ("frequency_per_year", frequenz), ("executions_per_run", faelle),
            ("total_duration_minutes", gesamtdauer)]),
        ("Der anstrengendste Schritt.", [
            ("focus_step", fokus), ("focus_step_duration_minutes", fokusdauer),
            ("focus_step_duration_source", quelle),
            ("focus_step_duration_confidence_pct", sicherheit)]),
        ("Beteiligte und Systeme.", [
            ("focus_step_roles", rollen), ("focus_step_systems", systeme),
            ("focus_step_media_break", medienbruch),
            ("documentation_status", doku)]),
        ("Voraussetzungen.", [
            ("standardization_level", standard),
            ("data_availability_score", daten), ("stability_score", stabil),
            ("pii_involved", pii)]),
    ]


def test_demo_reisebuchung_bis_fertig_mit_normalisierung():
    antwort = _lauf("demo-reise", _basis_skript(
        "die Reisebuchung automatisieren", "Reisebuchung", "Office Management",
        "Geschäftsreisen", "Antrag, Genehmigung, Buchung, Abrechnung",
        "Mitarbeiter plant eine Dienstreise", "Reiseantrag mit Terminen",
        "mail", "gebuchte Reise mit Bestätigungen",
        "30 pro Monat", "360", "3 Stunden",
        "Buchung", "90 Minuten", "geschaetzt", "60%",
        "Office Management, Mitarbeiter", "Mail, Buchungsportal, Excel",
        "Ja.", "2", "3", "2", "4", "ja"))
    assert antwort["status"] == "fertig"
    assert antwort["payload"]["vollstaendigkeit"] == 1.0
    felder = antwort["payload"]["felder"]
    assert felder["frequency_per_year"]["wert"] == "360"        # 30×12
    assert felder["total_duration_minutes"]["wert"] == "180"    # 3 h
    assert felder["focus_step_duration_confidence_pct"]["wert"] == "60"
    assert felder["focus_step_media_break"]["wert"] == "ja"
    assert felder["process_name"]["wert"] == "Reisebuchung"


def test_demo_rag_wissensbasis_bis_fertig():
    antwort = _lauf("demo-rag", _basis_skript(
        "Antworten aus unserer Wissensbasis automatisieren",
        "Wissensanfragen beantworten", "Fachexperte",
        "Wissensmanagement", "Anfrage sichten, Dokumente suchen, Antwort schreiben",
        "Anfrage eines Kollegen oder Kunden", "Anfragetext und Dokumentenablage",
        "digital", "beantwortete Anfrage mit Quellen",
        "20 pro Woche", "1040", "45 Minuten",
        "Dokumente suchen", "25 Minuten", "geschaetzt", "50%",
        "Fachexperten, Support", "Sharepoint, Mail, Wiki",
        "ja", "2", "2", "3", "3", "nein"))
    assert antwort["status"] == "fertig"
    assert antwort["payload"]["vollstaendigkeit"] == 1.0
    assert antwort["payload"]["felder"]["frequency_per_year"]["wert"] == "1040"  # 20×52


def test_demo_consultant_placement_bis_fertig():
    antwort = _lauf("demo-placement", _basis_skript(
        "das Consultant-Staffing beschleunigen", "Consultant Placement",
        "Staffing Manager", "Personaleinsatzplanung",
        "Anfrage erfassen, Profile suchen, Matching, Vorschlag versenden",
        "Kundenanfrage nach einem Consultant", "Anforderungsprofil des Kunden",
        "mail", "Personalvorschlag mit passenden Profilen",
        "300 pro Jahr", "300", "2 Stunden",
        "Profile suchen", "1 Stunden", "aus_system", "80 %",
        "Staffing, Vertrieb", "CRM, Skill-Datenbank, Excel",
        "NEIN!", "3", "4", "4", "3", "ja"))
    assert antwort["status"] == "fertig"
    assert antwort["payload"]["vollstaendigkeit"] == 1.0
    felder = antwort["payload"]["felder"]
    assert felder["focus_step_duration_minutes"]["wert"] == "60"   # 1 h
    assert felder["focus_step_media_break"]["wert"] == "nein"
