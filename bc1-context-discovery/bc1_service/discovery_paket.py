"""Das Discovery-Paket — reine Daten nach dem BC0-Fragenkatalog (Blöcke A–J).

Feldnamen schema-nah englisch (Zielfelder des Katalogs): der Gate-0-Payload
ist damit BC2-nah benannt. Muss-Felder (M) werden aktiv gefragt, E-Felder
passiv miterfasst (required=False). Dokumentierte Katalog-Abweichungen
(Spec P3): B3/H1/H2 nennen „Auswahl“ ohne Optionsliste. B3 ist im Kontext-Zweig
(1.2) eine Auswahl aus den aktiven Rollen des Mandanten, im kontextfreien Zweig
(1.0) Freitext; H1/H2 sind FREITEXT, bis der Katalog Optionen nachliefert ·
E5 auf Pflicht hochgestuft (der flache
Fokus-Schnitt hängt daran) · D4 als executions_per_run (Katalog-Zielfeld
heißt executions_per_year, die Frage erfasst Fälle pro Durchlauf — Name
folgt der Frage). Flach + Fokus-Schritt: die focus_step_*-Felder
gelten für den in focus_step benannten Schritt.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from bc1_core.feldtypen import (
    ANZAHL,
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
from bc1_service.paket_feldtypen import PROZENT_GANZ_0_100, baue_system_typ

SCHEMA_VERSION = "1.0"
# Neue Basisversion, weil sich die BEDEUTUNG aendert: focus_step ist jetzt eine
# validierte Teilprozess-ID, focus_step_systems prueft gegen mandant_systeme
# (Spec K2 — nur mit BC0-Kontext erreichbar, s. Bc0Kontext unten).
SCHEMA_VERSION_CTX = "1.2"
MAX_ROUNDS_DISCOVERY = 60   # 26 Pflichtfelder × 2 Versuche + Puffer


@dataclass(frozen=True)
class Bc0Kontext:
    """Alles, was beim Dienststart einmalig aus BC0 geladen wird (Spec K2)."""
    company_id: str
    # (TP-ID, Schrittname) — nur BEWERTETE (Rev. 11, s. start.lade_kontext). Zu einem
    # unbewerteten Teilprozess entsteht kein Profil; die Menge geht in den Fingerprint ein.
    teilprozesse: tuple[tuple[str, str], ...]
    system_ids: tuple[str, ...]
    # B5: die Anfrage, zu der interviewt wird. None nur in kontextfreien Tests —
    # main.py setzt sie immer (BC1_ANFRAGE_ID ist Pflicht).
    anfrage_id: str | None = None
    # (Rollen-ID, Bezeichnung) — nur aktive Rollen des Mandanten. ID und Bezeichnung
    # gehen in den Fingerprint ein.
    rollen: tuple[tuple[str, str], ...] = ()
    # (Kernprozess-ID, Rollen-ID oder None) — Kernprozesse der Anfrage-TPs, nach
    # Prozess-ID sortiert. None = keine Eigner-Rolle ableitbar. Nicht im Fingerprint.
    eigner: tuple[tuple[str, str | None], ...] = ()
    # (Kernprozess-ID, Name) — alle aktiven Kernprozesse des Mandanten beim Laden, nach
    # Prozess-ID sortiert. IDs und Namen gehen in den Fingerabdruck ein.
    prozesse: tuple[tuple[str, str], ...] = ()


def _eigner_vorschlag(kontext: Bc0Kontext) -> list[str]:
    """Rollen-ID, die der B3-Fragetext als Eigner-Vorschlag nennt (genau ein Kernprozess
    mit aktiver Rolle), sonst leer."""
    if len(kontext.eigner) == 1 and dict(kontext.rollen).get(kontext.eigner[0][1]) is not None:
        return [kontext.eigner[0][1]]
    return []


def _ctx_fingerprint(kontext: Bc0Kontext) -> str:
    # Kanonisch, strukturiert, sortiert (Spec K2, R5-M7): gleiche Grundlagen =>
    # gleicher Wert, unabhaengig von Query-Reihenfolge. Rollen, Kernprozesse und
    # Teilprozesse gehen als (ID, Name)-Paare ein: die Namen wirken auf die
    # Auslegung der Eingabe (Spec Antwortformen 3.3), eine Umbenennung in BC0
    # aendert also die Paket-Identitaet — gewollt. Vom Eigner geht nur der Vorschlag ein,
    # den der B3-Fragetext nennt (Rollen-ID oder leer): er ist antwortrelevant, ein
    # Eignerwechsel zwischen zwei Turns ist ein Paketkonflikt (Gesamtpruefung Befund 2).
    # Die Anfrage ist Teil der Paketidentitaet. Den Schutz gegen eine fremde Anfrage
    # traegt aber `pruefe_anfrage` (core) — der Recovery-Replay darf einen
    # abweichenden ctx-Hash passieren.
    roh = json.dumps(
        {"anfrage": kontext.anfrage_id,
         "company_id": kontext.company_id.lower(),
         "eigner": _eigner_vorschlag(kontext),
         "kp": sorted(kontext.prozesse),
         "rollen": sorted(kontext.rollen),
         "snn": sorted(kontext.system_ids),
         "tp": sorted(kontext.teilprozesse)},
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(roh.encode()).hexdigest()[:16]


def baue_discovery_paket(*, kontext: Bc0Kontext | None = None) -> UseCasePackage:
    """kontext: einmalig beim Dienststart geladene BC0-Anbindung (Spec K2) —
    schaltet B4 auf die Kernprozess-Auswahl, focus_step auf eine geprüfte
    Teilprozess-Auswahl (identitätskritisch) und focus_step_systems auf die
    Mandanten-Systemmenge um. Ohne Kontext bleibt das Etappe-0-Verhalten
    (Freitext, schema_version 1.0) unverändert."""
    if kontext is not None:
        # B4 kommt im Kontext-Zweig aus den beim Start geladenen Kernprozessen.
        if kontext.prozesse:
            b4_typ = AUSWAHL(*(pid for pid, _ in kontext.prozesse),
                             namen=dict(kontext.prozesse))
            b4_frage = ("Zu welchem Ihrer Kernprozesse gehört das? ("
                        + ", ".join(f"{pid} = {name}" for pid, name in kontext.prozesse)
                        + ")")
        else:
            b4_typ = FREITEXT
            b4_frage = "Zu welchem Ihrer Kernprozesse gehört das?"
        # E5 wird zur geprüften Teilprozess-Auswahl; ohne BC0-Anbindung gibt es
        # keine Prozess-Identität, die man erzwingen könnte (identitaetskritisch
        # haengt deshalb bewusst am Kontext, nicht an einer Konstante).
        e5_typ = AUSWAHL(*(tp for tp, _ in kontext.teilprozesse),
                         namen=dict(kontext.teilprozesse))
        e5_frage = ("Welcher Schritt kostet am meisten Zeit oder nervt am "
                    "meisten? ("
                    + ", ".join(f"{tp} = {name}" for tp, name in kontext.teilprozesse)
                    + ")")
        b3_typ = AUSWAHL(*(rid for rid, _ in kontext.rollen), namen=dict(kontext.rollen))
        b3_frage = ("Welche Rolle ist für diesen Prozess verantwortlich? "
                    "Bitte nennen Sie die Rolle ("
                    + ", ".join(f"{rid} = {bez}" for rid, bez in kontext.rollen)
                    + ").")
        for rolle_id in _eigner_vorschlag(kontext):
            b3_frage += f" Laut BC0 ist das {dict(kontext.rollen)[rolle_id]} ({rolle_id})."
        f2_typ = baue_system_typ(frozenset(kontext.system_ids))
        # E4 ganzzahlig NUR im Kontext-Zweig (Codex R2-N-I4): geschrieben wird
        # ausschliesslich mit BC0-Kontext, und der Zweig traegt mit 1.1+ctx-
        # ohnehin eine neue Version. Der kontextfreie Zweig bleibt bei
        # PROZENT_0_100 — sonst aendert sich Semantik unter unveraenderter 1.0.
        e4_typ = PROZENT_GANZ_0_100
        d4_typ = ANZAHL
        e2_frage = "Wie lange dauert ein einzelner Lauf dieses Schritts im Schnitt?"
        # Semver-Build-Metadata-Semantik (+-Suffix, von Konsumenten beim
        # Versionsvergleich ignorierbar): der Fingerprint macht Teilprozess-
        # Liste, System-Menge, Mandant UND KP-Liste Teil der Paket-Identität,
        # damit der bestehende Paket-Guard (core.py, PaketKonfliktError) bei
        # jeder dieser Grundlagen-Änderungen zwischen zwei Turns derselben
        # Session greift.
        schema_version = (f"{SCHEMA_VERSION_CTX}+ctx-"
                          f"{_ctx_fingerprint(kontext)}")
    else:
        e5_typ, f2_typ, e4_typ = FREITEXT, LISTE, PROZENT_0_100
        d4_typ = ZAHL
        e2_frage = "Wie lange dauert dieser Schritt im Schnitt?"
        b3_typ = FREITEXT
        b3_frage = "Welche Rolle ist für diesen Prozess verantwortlich?"
        e5_frage = ("Welcher Schritt kostet am meisten Zeit oder nervt am "
                    "meisten?")
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
                      typ=AUSWAHL("ganzer_prozess", "einzelner_schritt", synonyme={
                          "ganzer_prozess": ("den ganzen Prozess",),
                          "einzelner_schritt": ("ein einzelner Schritt",)})),
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
            FieldSpec("process_owner_role", b3_frage, typ=b3_typ),               # B3 (Katalog: Auswahl ohne Optionsliste; 1.2 aus aktiven Rollen, 1.0 Freitext)
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
                      typ=AUSWAHL("digital", "papier", "pdf", "mail",
                                  synonyme={"mail": ("E-Mail", "Email")})),
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
                      "typischerweise pro Durchlauf?", typ=d4_typ),
            # --- Block E — Zeit / Aufwand (Fokus-Schritt) ---
            FieldSpec("total_duration_minutes",                                  # E1
                      "Wie lange dauert ein kompletter Durchlauf im Schnitt?",
                      typ=MINUTEN),
            FieldSpec("focus_step", e5_frage, typ=e5_typ,                        # E5 (⚠️ auf M hochgestuft — Fokus-Schnitt)
                      identitaetskritisch=kontext is not None),
            FieldSpec("focus_step_duration_minutes", e2_frage,                   # E2
                      typ=MINUTEN),
            FieldSpec("focus_step_duration_source",                              # E3
                      "Ist diese Zeitangabe gemessen, geschaetzt oder "
                      "aus_system?",
                      typ=AUSWAHL("gemessen", "geschaetzt", "aus_system",
                                  synonyme={"aus_system": ("aus dem System",)})),
            FieldSpec("focus_step_duration_confidence_pct",                      # E4
                      "Wie sicher ist diese Zeitangabe (0–100 %)?",
                      typ=e4_typ),
            # --- Block F — Fokus-Schritt: Rollen & Systeme ---
            FieldSpec("focus_step_roles",                                        # F1
                      "Welche Rollen oder Abteilungen sind an diesem Schritt "
                      "beteiligt?", typ=LISTE),
            FieldSpec("focus_step_systems",                                      # F2
                      "Welche IT-Systeme oder Tools nutzen Sie in diesem "
                      "Schritt?", typ=f2_typ),
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
