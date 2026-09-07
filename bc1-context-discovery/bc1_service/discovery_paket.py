"""Das Discovery-Paket — reine Daten nach dem BC0-Fragenkatalog (Blöcke A–J).

Feldnamen schema-nah englisch (Zielfelder des Katalogs): der Gate-0-Payload
ist damit BC2-nah benannt. Muss-Felder (M) werden aktiv gefragt, E-Felder
passiv miterfasst (required=False). Dokumentierte Katalog-Abweichungen
(Spec P3): B3/H1/H2 nennen „Auswahl“ ohne Optionsliste → FREITEXT bis der
Katalog Optionen nachliefert · E5 auf Pflicht hochgestuft (der flache
Fokus-Schnitt hängt daran) · D4 als executions_per_run (Katalog-Zielfeld
heißt executions_per_year, die Frage erfasst Fälle pro Durchlauf — Name
folgt der Frage). Flach + Fokus-Schritt: die focus_step_*-Felder
gelten für den in focus_step benannten Schritt.
"""
from __future__ import annotations

import hashlib

from bc1_core.feldtypen import (
    AUSWAHL,
    FREITEXT,
    JA_NEIN,
    LISTE,
    MINUTEN,
    PROZENT_0_100,
    SKALA_1_5,
    ZAHL,
)
from bc1_core.package import FieldSpec, UseCasePackage

SCHEMA_VERSION = "1.0"
MAX_ROUNDS_DISCOVERY = 60   # 26 Pflichtfelder × 2 Versuche + Puffer


def baue_discovery_paket(
    prozesse: list[tuple[str, str]] | None = None,
) -> UseCasePackage:
    """prozesse: (ID, Name)-Paare aus dem BC0-Snapshot für B4; None → Freitext."""
    if prozesse:
        b4_typ = AUSWAHL(*(pid for pid, _ in prozesse))
        b4_frage = ("Zu welchem Ihrer Kernprozesse gehört das? ("
                    + ", ".join(f"{pid} = {name}" for pid, name in prozesse) + ")")
        # Semver-Build-Metadata-Semantik (+-Suffix, von Konsumenten beim
        # Versionsvergleich ignorierbar): der Fingerprint macht den Snapshot-
        # Inhalt Teil der Paket-Identität, damit der bestehende Paket-Guard
        # (core.py, PaketKonfliktError) bei einem Snapshot-Wechsel zwischen
        # zwei Turns derselben Session greift — sonst validierte eine
        # fortgesetzte Session gegen einen anderen Options-Satz als den, mit
        # dem sie gestartet wurde. sorted(): paketrelevant ist der Options-
        # INHALT (welche IDs gültig sind), nicht seine Reihenfolge — eine
        # reine Umsortierung (z. B. andere Snapshot-Query-Reihenfolge) ändert
        # die Validator-Semantik nicht und soll die Identität nicht unnötig
        # churnen lassen.
        # Verifikations-Critical (Codex-Residuum, Fix-Welle 5): 8 Hex-Zeichen
        # (32 Bit) sind kollisionsanfällig — Codex hat real zwei verschiedene
        # Prozess-IDs mit identischem 8-Hex-Fingerprint gebruteforced; der
        # Paket-Guard griff dann bei einem Snapshot-Wechsel NICHT. 16 Hex
        # (64 Bit) statt 8.
        fp = hashlib.sha256(
            repr(sorted(pid for pid, _ in prozesse)).encode()
        ).hexdigest()[:16]
        schema_version = f"{SCHEMA_VERSION}+kp-{fp}"
    else:
        b4_typ = FREITEXT
        b4_frage = "Zu welchem Ihrer Kernprozesse gehört das?"
        schema_version = SCHEMA_VERSION

    return UseCasePackage(
        name="discovery",
        schema_version=schema_version,
        max_rounds=MAX_ROUNDS_DISCOVERY,
        fields=(
            # --- Block A — Anfrage-Rahmen & Ziel ---
            FieldSpec("request_intent",                                          # A1
                      "Was möchten Sie konkret automatisieren oder verbessern?"),
            FieldSpec("request_goal",                                            # A2
                      "Welches Ergebnis erwarten Sie vor allem — zeit_sparen, "
                      "fehler_senken oder skalieren?",
                      typ=AUSWAHL("zeit_sparen", "fehler_senken", "skalieren")),
            FieldSpec("scope_focus",                                             # A3
                      "Geht es um einen ganzer_prozess oder einen "
                      "einzelner_schritt?",
                      typ=AUSWAHL("ganzer_prozess", "einzelner_schritt")),
            FieldSpec("pain_level",                                              # A4 (E)
                      "Wie hoch ist der Leidensdruck heute (1–5)?",
                      required=False, typ=SKALA_1_5),
            # --- Block B — Prozess-Identität & Einordnung ---
            FieldSpec("process_name",                                            # B1
                      "Um welchen Prozess geht es — wie würden Sie ihn nennen?"),
            FieldSpec("process_category",                                        # B2 (E)
                      "Ist das eher steuerung, kerngeschaeft oder "
                      "unterstuetzung?",
                      required=False,
                      typ=AUSWAHL("steuerung", "kerngeschaeft", "unterstuetzung")),
            FieldSpec("process_owner_role",                                      # B3 (⚠️ Katalog: Auswahl ohne Optionsliste)
                      "Welche Rolle ist für diesen Prozess verantwortlich?"),
            FieldSpec("process_id", b4_frage, typ=b4_typ),                       # B4
            FieldSpec("process_steps",                                           # B5
                      "Welche Einzelschritte hat der Prozess, von Anfang bis "
                      "Ende?", typ=LISTE),
            # --- Block C — Auslöser · Input · Output ---
            FieldSpec("trigger_text", "Was löst den Prozess aus?"),              # C1
            FieldSpec("input_text",                                              # C2
                      "Welche Eingangsdaten oder Dokumente brauchen Sie zum "
                      "Start?"),
            FieldSpec("input_format",                                            # C3
                      "In welchem Format kommen die Eingangsdaten an — "
                      "digital, papier, pdf oder mail?",
                      typ=AUSWAHL("digital", "papier", "pdf", "mail")),
            FieldSpec("output_text",                                             # C4
                      "Was ist das Endergebnis bzw. der Output des Prozesses?"),
            FieldSpec("output_format",                                           # C5 (E)
                      "In welchem Format geht der Output raus — system, "
                      "dokument oder mail?",
                      required=False, typ=AUSWAHL("system", "dokument", "mail")),
            # --- Block D — Mengengerüst & Häufigkeit ---
            FieldSpec("frequency_per_year",                                      # D1
                      "Wie oft läuft der gesamte Prozess (pro Woche, Monat "
                      "oder Jahr)?", typ=ZAHL),
            FieldSpec("seasonal_peaks",                                          # D2 (E)
                      "Gibt es saisonale Schwankungen oder Lastspitzen?",
                      required=False, typ=JA_NEIN),
            FieldSpec("step_frequency_per_year",                                 # D3 (E)
                      "Wie oft läuft dieser einzelne Schritt, falls "
                      "abweichend?", required=False, typ=ZAHL),
            FieldSpec("executions_per_run",                                      # D4 (⚠️ Katalog-Befund: Zielfeld-Name vs. Frage)
                      "Wie viele Fälle oder Vorgänge bearbeiten Sie "
                      "typischerweise pro Durchlauf?", typ=ZAHL),
            # --- Block E — Zeit / Aufwand (Fokus-Schritt) ---
            FieldSpec("total_duration_minutes",                                  # E1
                      "Wie lange dauert ein kompletter Durchlauf im Schnitt?",
                      typ=MINUTEN),
            FieldSpec("focus_step",                                              # E5 (⚠️ auf M hochgestuft — Fokus-Schnitt)
                      "Welcher Schritt kostet am meisten Zeit oder nervt am "
                      "meisten?"),
            FieldSpec("focus_step_duration_minutes",                             # E2
                      "Wie lange dauert dieser Schritt im Schnitt?",
                      typ=MINUTEN),
            FieldSpec("focus_step_duration_source",                              # E3
                      "Ist diese Zeitangabe gemessen, geschaetzt oder "
                      "aus_system?",
                      typ=AUSWAHL("gemessen", "geschaetzt", "aus_system")),
            FieldSpec("focus_step_duration_confidence_pct",                      # E4
                      "Wie sicher ist diese Zeitangabe (0–100 %)?",
                      typ=PROZENT_0_100),
            # --- Block F — Fokus-Schritt: Rollen & Systeme ---
            FieldSpec("focus_step_roles",                                        # F1
                      "Welche Rollen oder Abteilungen sind an diesem Schritt "
                      "beteiligt?", typ=LISTE),
            FieldSpec("focus_step_systems",                                      # F2
                      "Welche IT-Systeme oder Tools nutzen Sie in diesem "
                      "Schritt?", typ=LISTE),
            FieldSpec("focus_step_media_break",                                  # F3
                      "Müssen Sie zwischen Systemen wechseln oder Daten "
                      "manuell übertragen?", typ=JA_NEIN),
            FieldSpec("systems_integrated",                                      # F4 (E)
                      "Sind diese Systeme über Schnittstellen verbunden?",
                      required=False, typ=JA_NEIN),
            FieldSpec("digital_logging",                                         # F5 (E)
                      "Werden Zwischenstände digital protokolliert oder "
                      "archiviert?", required=False, typ=JA_NEIN),
            # --- Block G — Automatisierungs-Voraussetzungen ---
            FieldSpec("documentation_status",                                    # G1
                      "Ist der Ablauf dokumentiert (1 = gar nicht, "
                      "5 = vollständig)?", typ=SKALA_1_5),
            FieldSpec("standardization_level",                                   # G2
                      "Läuft der Prozess immer gleich (5) oder gibt es viele "
                      "Sonderfälle (1)?", typ=SKALA_1_5),
            FieldSpec("variant_share_pct",                                       # G3 (E)
                      "Wie viel Prozent der Fälle sind Ausnahmen?",
                      required=False, typ=PROZENT_0_100),
            FieldSpec("data_availability_score",                                 # G4
                      "Liegen die nötigen Daten strukturiert und digital vor "
                      "(1–5)?", typ=SKALA_1_5),
            FieldSpec("stability_score",                                         # G5
                      "Wie stabil läuft der Prozess bei hoher Last (1–5)?",
                      typ=SKALA_1_5),
            FieldSpec("rule_based_score",                                        # G6 (E)
                      "Folgt der Prozess klaren Regeln (1–5)?",
                      required=False, typ=SKALA_1_5),
            FieldSpec("acceptance_score",                                        # G7 (E)
                      "Wie offen sind die Beteiligten für Automatisierung "
                      "(1–5)?", required=False, typ=SKALA_1_5),
            FieldSpec("automation_potential_estimate_pct",                       # G8 (E)
                      "Wie hoch schätzen Sie das Automatisierungs-Potenzial "
                      "(0–100 %)?", required=False, typ=PROZENT_0_100),
            # --- Block H — Schnittstellen (E, ⚠️ Katalog nennt Auswahl ohne Optionen) ---
            FieldSpec("upstream_process",                                        # H1
                      "Welcher Prozess kommt davor und liefert Ihnen etwas?",
                      required=False),
            FieldSpec("downstream_process",                                      # H2
                      "Welcher Prozess kommt danach und braucht Ihr Ergebnis?",
                      required=False),
            FieldSpec("interface_data",                                          # H3 (E)
                      "Welche Daten werden an diesen Schnittstellen "
                      "übergeben?", required=False),
            # --- Block I — Daten, Qualität & Compliance ---
            FieldSpec("pii_involved",                                            # I1
                      "Werden in diesem Prozess personenbezogene Daten "
                      "verarbeitet?", typ=JA_NEIN),
            FieldSpec("approval_steps",                                          # I2 (E)
                      "Gibt es Kontroll- oder Freigabeschritte (Vier-Augen, "
                      "Genehmigung)?", required=False, typ=JA_NEIN),
            FieldSpec("error_hotspots",                                          # I3 (E)
                      "Wo passieren heute typischerweise Fehler oder "
                      "Nacharbeit?", required=False),
            # --- Block J — Abschluss (J1 Spiegelung + J3 Source: siehe Spec-Roadmap) ---
            FieldSpec("open_remarks",                                            # J2 (E)
                      "Gibt es etwas Wichtiges, das noch nicht zur Sprache "
                      "kam?", required=False),
        ),
    )
