# Spalte-zu-Feld-Tabelle — was BC1 fragt und was daraus wird

> **Aus dem Code erzeugt** am 08.09.2026 (Paket `discovery`, Basis-Schema `1.1`, Writer `bc1_service/profil_writer.py`). Nicht von Hand pflegen — Generator liegt neben den Betriebs-Skripten, Aufruf im Kopf des Generators.
>
> Erledigt zugleich BC0s ADR-005 §8 Punkt 96 (jeder Kontext meldet seine Herkunftsspalten) und ist der Eingang fuer den Vertrag `contracts/bc1-to-bc2/prozessprofil.schema.json`.

## Big Picture

Das Interview stellt **43 Fragen**: **26 Pflichtfragen** (M) — ohne sie wird das Profil nicht `fertig` — und **17 Ergaenzungsfragen** (E), die passiv miterfasst werden. **Alle 43 Antworten landen im Profil-JSON** (`bc1.prozessprofil.profil`, unter `felder.<name>.wert` mit Status und Herkunft). **9 davon speisen zusaetzlich typisierte Spalten**, mit denen BC2 direkt rechnen kann. Der Rest ist fuer BC2 Kontext, nicht Rechengroesse.

**Die vier Groessen aus BC2s Ticket #184:**

| BC2 braucht | Spalte | Frage | Stand |
|---|---|---|---|
| `haeufigkeit` | `frequency_per_year` | D1 — auf Jahr normalisiert (30 pro Monat → 360) | ✅ typisiert |
| `menge` | `executions_per_run` | D4 — Faelle je Durchlauf | ✅ typisiert |
| `dauer` | `total_duration_minutes` + `focus_step_duration_minutes` | E1 (Prozess), E2 (Fokus-Schritt) — in Minuten | ✅ typisiert |
| Guete zur Dauer | `focus_step_duration_confidence_pct` + `focus_step_duration_source` | E4 (0–100, ganzzahlig), E3 (gemessen/geschaetzt/aus_system) | ✅ typisiert |
| `rollen` | — | F1 `focus_step_roles` ist eine **Freitext-Liste im JSON**; `profil_rollen` bleibt in Etappe 1 leer, `process_owner_rolle_id` NULL | ⚠️ Etappe 2 (Abschlussplan C1) |

## Technischer Teil

### 1. Spalten von `bc1.prozessprofil` und ihre Herkunft

| Spalte | Typ | Herkunft |
|---|---|---|
| `company_id` | uuid | Writer-Konfiguration (`BC1_COMPANY_ID`) — nie aus dem Interview |
| `focus_step_id` | text | Feld `focus_step` (E5), nur `gueltig` — die Identitaet des Profils |
| `process_id` | text | **abgeleitet**: Praefix der TP-ID; Feld `process_id` (B4) dient nur dem Abgleich (`befunde.kp_tp_diskrepanz`) |
| `profil_version` | integer | vergibt der `BEFORE INSERT`-Trigger |
| `status` | text | `in_erhebung` → `fertig` (Freeze, final) |
| `process_owner_rolle_id` | text | **immer NULL in Etappe 1**; B3 `process_owner_role` bleibt Freitext im JSON |
| `upstream_process_id` | text | Feld `upstream_process` (H1), nur kanonisch `KP-NN`, in der Baseline, != eigener KP; sonst NULL |
| `downstream_process_id` | text | Feld `downstream_process` (H2), wie upstream |
| `frequency_per_year` | numeric | Feld `frequency_per_year` (D1), Decimal, nur `gueltig` |
| `executions_per_run` | numeric | Feld `executions_per_run` (D4), Decimal, nur `gueltig` |
| `total_duration_minutes` | numeric | Feld `total_duration_minutes` (E1), Decimal, nur `gueltig` |
| `focus_step_duration_minutes` | numeric | Feld `focus_step_duration_minutes` (E2), Decimal, nur `gueltig` |
| `focus_step_duration_confidence_pct` | integer | Feld `focus_step_duration_confidence_pct` (E4), int, nur `gueltig` |
| `focus_step_duration_source` | text | Feld `focus_step_duration_source` (E3), AUSWAHL-normalisiert |
| `erhebung_id` | text | Lookup: juengste nicht verworfene Bewertung des Teilprozesses (`v_bewertung_aktuell` × `ref_erhebungen.stand`) |
| `paket_version` | text | `schema_version` des Pakets inkl. Kontext-Fingerprint (`1.1+ctx-…`) |
| `profil` | jsonb | alle Felder mit Status/Herkunft, `vollstaendigkeit`, `pflicht_erfasst/gesamt`, `ungeloeste_felder`, `befunde` |

**Regel:** Nur `status == gueltig` wird in eine Spalte konvertiert; jeder andere Status ergibt SQL `NULL`, der Rohwert bleibt im JSON.

### 2. Alle Fragen des Interviews

| Katalog | Feld | M/E | Typ | Speist Spalte | Frage |
|---|---|---|---|---|---|
| A1 | `request_intent` | M | freitext | — | Was möchten Sie konkret automatisieren oder verbessern? |
| A2 | `request_goal` | M | auswahl | — | Welches Ergebnis erwarten Sie vor allem — zeit_sparen, fehler_senken oder skalieren? |
| A3 | `scope_focus` | M | auswahl | — | Geht es um einen ganzer_prozess oder einen einzelner_schritt? |
| A4 | `pain_level` | E | skala_1_5 | — | Wie hoch ist der Leidensdruck heute (1–5)? |
| B1 | `process_name` | M | freitext | — | Um welchen Prozess geht es — wie würden Sie ihn nennen? |
| B2 | `process_category` | E | auswahl | — | Ist das eher steuerung, kerngeschaeft oder unterstuetzung? |
| B3 | `process_owner_role` | M | freitext | — | Welche Rolle ist für diesen Prozess verantwortlich? |
| B4 | `process_id` | M | freitext | — | Zu welchem Ihrer Kernprozesse gehört das? |
| B5 | `process_steps` | M | liste | — | Welche Einzelschritte hat der Prozess, von Anfang bis Ende? |
| C1 | `trigger_text` | M | freitext | — | Was löst den Prozess aus? |
| C2 | `input_text` | M | freitext | — | Welche Eingangsdaten oder Dokumente brauchen Sie zum Start? |
| C3 | `input_format` | M | auswahl | — | In welchem Format kommen die Eingangsdaten an — digital, papier, pdf oder mail? |
| C4 | `output_text` | M | freitext | — | Was ist das Endergebnis bzw. der Output des Prozesses? |
| C5 | `output_format` | E | auswahl | — | In welchem Format geht der Output raus — system, dokument oder mail? |
| D1 | `frequency_per_year` | M | zahl | `frequency_per_year` | Wie oft läuft der gesamte Prozess (pro Woche, Monat oder Jahr)? |
| D2 | `seasonal_peaks` | E | ja_nein | — | Gibt es saisonale Schwankungen oder Lastspitzen? |
| D3 | `step_frequency_per_year` | E | zahl | — | Wie oft läuft dieser einzelne Schritt, falls abweichend? |
| D4 | `executions_per_run` | M | zahl | `executions_per_run` | Wie viele Fälle oder Vorgänge bearbeiten Sie typischerweise pro Durchlauf? |
| E1 | `total_duration_minutes` | M | minuten | `total_duration_minutes` | Wie lange dauert ein kompletter Durchlauf im Schnitt? |
| E5 | `focus_step` | M | auswahl | `focus_step_id` | Welcher Schritt kostet am meisten Zeit oder nervt am meisten? (Auswahl aus den bewerteten Teilprozessen des Mandanten) |
| E2 | `focus_step_duration_minutes` | M | minuten | `focus_step_duration_minutes` | Wie lange dauert dieser Schritt im Schnitt? |
| E3 | `focus_step_duration_source` | M | auswahl | `focus_step_duration_source` | Ist diese Zeitangabe gemessen, geschaetzt oder aus_system? |
| E4 | `focus_step_duration_confidence_pct` | M | prozent_ganz_0_100 | `focus_step_duration_confidence_pct` | Wie sicher ist diese Zeitangabe (0–100 %)? |
| F1 | `focus_step_roles` | M | liste | — | Welche Rollen oder Abteilungen sind an diesem Schritt beteiligt? |
| F2 | `focus_step_systems` | M | systeme | — | Welche IT-Systeme oder Tools nutzen Sie in diesem Schritt? (Auswahl aus den Systemen des Mandanten, S-NN) |
| F3 | `focus_step_media_break` | M | ja_nein | — | Müssen Sie zwischen Systemen wechseln oder Daten manuell übertragen? |
| F4 | `systems_integrated` | E | ja_nein | — | Sind diese Systeme über Schnittstellen verbunden? |
| F5 | `digital_logging` | E | ja_nein | — | Werden Zwischenstände digital protokolliert oder archiviert? |
| G1 | `documentation_status` | M | skala_1_5 | — | Ist der Ablauf dokumentiert (1 = gar nicht, 5 = vollständig)? |
| G2 | `standardization_level` | M | skala_1_5 | — | Läuft der Prozess immer gleich (5) oder gibt es viele Sonderfälle (1)? |
| G3 | `variant_share_pct` | E | prozent_0_100 | — | Wie viel Prozent der Fälle sind Ausnahmen? |
| G4 | `data_availability_score` | M | skala_1_5 | — | Liegen die nötigen Daten strukturiert und digital vor (1–5)? |
| G5 | `stability_score` | M | skala_1_5 | — | Wie stabil läuft der Prozess bei hoher Last (1–5)? |
| G6 | `rule_based_score` | E | skala_1_5 | — | Folgt der Prozess klaren Regeln (1–5)? |
| G7 | `acceptance_score` | E | skala_1_5 | — | Wie offen sind die Beteiligten für Automatisierung (1–5)? |
| G8 | `automation_potential_estimate_pct` | E | prozent_0_100 | — | Wie hoch schätzen Sie das Automatisierungs-Potenzial (0–100 %)? |
| H1 | `upstream_process` | E | freitext | `upstream_process_id` | Welcher Prozess kommt davor und liefert Ihnen etwas? |
| H2 | `downstream_process` | E | freitext | `downstream_process_id` | Welcher Prozess kommt danach und braucht Ihr Ergebnis? |
| H3 | `interface_data` | E | freitext | — | Welche Daten werden an diesen Schnittstellen übergeben? |
| I1 | `pii_involved` | M | ja_nein | — | Werden in diesem Prozess personenbezogene Daten verarbeitet? |
| I2 | `approval_steps` | E | ja_nein | — | Gibt es Kontroll- oder Freigabeschritte (Vier-Augen, Genehmigung)? |
| I3 | `error_hotspots` | E | freitext | — | Wo passieren heute typischerweise Fehler oder Nacharbeit? |
| J2 | `open_remarks` | E | freitext | — | Gibt es etwas Wichtiges, das noch nicht zur Sprache kam? |

**Nicht gefragt, bewusst:** die 30 Bitkom-Items (bleiben im Self-Rating von BC0) · Rollen als Auswahl und Zeitanteil je Rolle (Etappe 2) · Kanten-Art (Etappe 2, BC0-Endpunkt folgt).
