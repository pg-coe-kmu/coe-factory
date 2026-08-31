# Aurelia — Architektur-Blueprint UC-1

Diese Datei beschreibt, wie Aurelia technisch zusammengebaut wird. Lesepublikum: BC4 zum Bauen, BC1/Platform für Schnittstellen, alle anderen zur Übersicht.

Bezug: `tickets.json` (Epic `ep-1111-...`), aus BC2 UC-1 (konzept_id `8a3d2f1c-...`)

## Kontext

Aurelia Krankenkasse, Antragsbearbeitung Krankentagegeld (KP-07). UC-1 „Automatisierte Antragserfassung via OCR + LLM-Extraktion" ersetzt Schritt 1 „Antrag erfassen" — heute ~5 Min manuell durch Sachbearbeitung.

- **AI-Act-Klasse:** high (Details in `compliance-audit.json`)
- **Compliance-Stories:** 1 (Story 4 HitL-Prüfschritt)
- **Speicherdauer:** 10 Jahre nach § 28f SGB IV (Plattform-Standard, Löschungs-Cron)

## Datenfluss UC-1

```mermaid
flowchart LR
    A[E-Mail-Postfach IMAP] --> B[Eingangs-Adapter]
    P[Online-Portal] --> B
    S[Dokumentenscanner] --> B
    B --> H{Idempotenz-Check}
    H -- doppelt --> X[Abweisen + Audit-Log]
    H -- neu --> O[OCR-Service Docling]
    O --> F[PII-Filter Plattform-Standard]
    F --> L[LLM-Extraktor via n8n + MCP]
    L --> K{Konfidenz aller Pflichtfelder >= 0.8?}
    K -- ja --> M[SAP-REST-Adapter]
    K -- nein --> Q[HitL-Queue Sachbearbeitung]
    Q -- freigegeben --> M
    Q -- korrigiert --> M
    Q -- verworfen --> X
    M --> SAP[(SAP S/4HANA)]
    M --> N[Eingangsbestätigung Portal/Mail]
    M --> AL[(Audit-Log Plattform-Standard)]
```

## Komponenten (UC-spezifisch — als Stories abgebildet)

| Komponente | Rolle | Technologie | Story |
|---|---|---|---|
| Eingangs-Adapter | drei Kanäle einlesen | n8n-Trigger (IMAP, HTTP, File-Watch) | Story 1 (`st-...-1`) |
| Idempotenz-Check | Duplikate abweisen | Postgres-Index auf Hash + Antragsnummer | Story 1 |
| OCR-Service | PDF zu strukturiertem Text | Docling | Story 2 (`st-...-2`) |
| LLM-Extraktor | Feld-Extraktion mit Konfidenz | LLM via n8n + MCP — Anbieterwahl unter AI-Act-Anforderung (siehe unten) | Story 2 |
| SAP-REST-Adapter | API-Schreiben ins SAP | SAP S/4HANA REST API über Service-User | Story 3 (`st-...-3`) |
| HitL-Queue | Sachbearbeiter-Interface | n8n + Web-UI | Story 4 (`st-...-4`, Compliance) |

## Querschnitts-Komponenten (KEINE eigenen Stories — gelten für alle Use-Cases)

Diese Komponenten sind Pipeline-Infrastruktur und werden zentral gebaut/betrieben:

| Komponente | Zweck | Pflicht | Owner-Team (vorläufig) |
|---|---|---|---|
| **PII-Filter (Pre-LLM)** | Pseudonymisierung vor Claude-Call | p2 [DSGVO Art. 25] | BC1 (AP 1.2 spaCy/LLM) |
| **Audit-Log (Append-only)** | Verarbeitungs-Historie unveränderbar | p3 [DSGVO Art. 30] | Platform-Team (AP 5.2) |
| **Löschungs-Cron** | Aufbewahrungsfrist durchsetzen | p4 [DSGVO Art. 17 + § 28f SGB IV] | Platform-Team |
| **TLS 1.3 + AES-256** | Verschlüsselung in Transit + at Rest | p5 [DSGVO Art. 32] | Platform-Team |

→ BC4 muss diese Standards in der eigenen Logik einhalten (z.B. Verschlüsselung beim SAP-Write nutzen), bekommt aber keine eigenen Tickets dafür. Konfiguration kommt von BC1 + Platform. Owner-Zuordnung noch mit Sergio + Mehdi zu bestätigen.

## Betroffene Externe Systeme

| System | Rolle | Integration |
|---|---|---|
| E-Mail-Server (IMAP) | Quelle | n8n IMAP-Trigger, Service-Account |
| Online-Portal | Quelle | REST-API mit OAuth2 |
| Dokumentenscanner | Quelle | Datei-Watch im SMB-Share |
| SAP S/4HANA | Ziel | REST-API mit Service-User, eigene Rolle |
| LLM-Backend | Verarbeitung | n8n-Outbound + MCP, Vault-managed Key, nur pseudonymisierte Daten — Anbieter siehe Hinweis |

### LLM-Anbieter-Hinweis (AI-Act-Anforderung)

Aurelia ist **Hochrisiko-KI** (AI-Act Anhang III 5(a)). Daraus folgen Pflichten an die Anbieterauswahl (Art. 25/28 — Verantwortlichkeiten in der Wertschöpfungskette):

- **Anthropic/Claude direkt geht nicht** ohne weitere Prüfung — US-Anbieter, AI-Act-Konformitätsbewertung offen, Drittlandtransfer kritisch trotz DPA.
- **Optionen die zu prüfen sind:**
  - **Ollama lokal** (Llama, Mistral oder ähnlich) — vollständig im VPN, keine externen Calls. Qualitätsverlust ggü. Claude muss abgewogen werden.
  - **EU-konformer Cloud-LLM** (Mistral, Aleph Alpha) mit nachgewiesener AI-Act-Compliance.
  - **MCP als Protokoll-Layer** bleibt nutzbar — ist Modell-agnostisch, nicht an Anthropic gebunden.
- **Entscheidung offen** — mit Mehdi (Platform) und Sabrina (Compliance) zu klären, vor M2-Build.

## Konfigurierbare Parameter

| Parameter | Default | Begründung |
|---|---|---|
| Konfidenz-Threshold | 0.8 | BC2-Vorgabe in `fachliche_beschreibung` |
| HitL-Eskalations-Frist | 24 h | tbd im Compliance-Review |
| Löschungs-Cron-Lauf | täglich 02:00 | Plattform-Standard |
| Antragsvolumen-Annahme | ~300/Woche | BC2-Mock |

## Risiken (operativ)

| Risiko | Wahrscheinlichkeit | Auswirkung | Maßnahme |
|---|---|---|---|
| OCR-Qualität bei Handschrift unzureichend | mittel | mittel | HitL-Queue (Story 4) + Trainingsdaten je Antragsart |
| SAP-API-Zugang verzögert | mittel | hoch | Mock-Adapter in S2-S3, produktive Anbindung erst S5 |
| LLM-Output strukturell inkonsistent | mittel | hoch | Strukturierte Prompts mit Schema + Validierung |
| AI-Act-Konformitätsbewertung verzögert | hoch | hoch | Parallele Vorbereitung mit DSB |

## Worker-Routing für BC4

Das Aurelia-Epic hat `kategorien: ["it:backend", "it:integration", "it:ai-pipeline"]`. Alle 4 Stories gehen an dieselben Worker — kein Story-spezifisches Routing.

Konsequenz: ein Mixed-Worker-Setup, das Backend (SAP-Adapter, Idempotenz-Check) + AI-Pipeline (OCR + LLM) + Integration (n8n-Trigger) bedient.

---

*Stand 12.06.2026 · Sabrina + Svetlana*
