# BC3 — Engineering Architect

**Team:** Sabrina, Svetlana
**Phase:** 3 — Logische Strukturierung der Lösung (zwischen Business-Strategie und technischer Umsetzung)
**Schema-Version:** 3.3
**Stand:** 07.06.2026

## Zweck

BC3 übersetzt das von BC2 gelieferte Automatisierungskonzept in **eine kanonische Lieferung an BC4** mit integriertem Compliance-Profil. Compliance ist konstruktiv: AI-Act- und DSGVO-Pflichten erzeugen eigene Stories (HitL, PII-Filter, Audit, Löschung), nicht nur Tags.

## Messages

- **Consumed:** Freigegebenes Automatisierungskonzept (aus BC2, `gate1 = approved`)
  - `konzept.json` (Multi-Use-Case)
  - `priorisierung.json` (Ranked List)
  - `roi_report.md` (Aggregat, optional)
- **Produced:** Drei Dateien je Projekt-Setting unter `contracts/bc3-to-bc4/<projekt>/`:
  - `tickets.json` — PRIMÄR, enthält Epics + Stories + compliance_profile + pflichten
  - `architecture.md` — Mermaid-Bauplan + Komponenten
  - `README.md` — Einstieg für BC4

## Arbeitspakete (v3.3)

| AP | Name | Pipeline-Phase |
|---|---|---|
| AP 3.1 | Schnittstellen-Contract (`tickets.schema.json` v3.3 + Aurelia-Mock) | — (Foundation) |
| AP 3.2 | Compliance-Auswertung (Pattern-Match → pflichten[] + ai_act_klasse) | Phase 2 |
| AP 3.3 | Slicer (UC-Stories + Compliance-Stories, regelbasiert M2 / LLM ab M3) | Phase 3 + 4 |
| AP 3.4 | Architecture-Generator (Mermaid aus betroffene_systeme) | Phase 6 |
| AP 3.5 | Verifikation (jede Pflicht in mind. einer Story abgedeckt) | Phase 5 |
| AP 3.6 | Hochrisiko-Eskalation (DSB-Pre-Check bei ai_act_klasse=high) | Phase 5b |
| AP 3.7 | Output-Writer (tickets.json + architecture.md + README.md) | Phase 6 |
| AP 3.8 | End-to-End-Probelauf BC2 → BC3 → BC4 (Aurelia) | M3 |
| AP 3.9 | Ergebnis-Präsentation BC3 | M4 |

## Schnittstellen

- **Input von BC2:** `/contracts/bc2-to-bc3/` (Schema `konzept.schema.json` v1.0)
- **Output an BC4:** `/contracts/bc3-to-bc4/<projekt>/` (Schema `tickets.schema.json` v3.3)

## Pipeline-Prinzipien

1. **Eine kanonische Datei** — `tickets.json` mit integriertem `compliance_profile`
2. **Drei Dateien** an BC4 (statt früher sieben)
3. **Pipeline vollautomatisch** — Mensch nur an `gate2` + `klaerung-an-bc2` + Hochrisiko-Eskalation
4. **Compliance ist konstruktiv** — Pflichten erzeugen eigene Stories
5. **Verifikation** Phase 5: jede `pflichten[].id` in mind. einer Story `erfuellt_pflichten[]`
6. **Hochrisiko-Pre-Check** Phase 5b: bei `ai_act_klasse = "high"` DSB-Freigabe vor Output

## Referenz-Beispiel

Erstes konkretes Projekt-Setting: **Aurelia Krankenkasse** (Antragsbearbeitung Krankentagegeld, KP-07).

→ Liegt unter `contracts/bc3-to-bc4/aurelia/`:
- `tickets.json` — 1 Epic, 7 Stories (3 UC + 4 Compliance), 6 Pflichten
- `architecture.md` — OCR-Pipeline + Compliance-Komponenten
- `README.md` — BC4-Einstieg

Basis: BC2-Mock `bc2-strategic-advisor/Mock/mock_automatisierungskonzept.json` UC-1.

## Meilensteine

| ME | Datum | Inhalt |
|---|---|---|
| Foundation BC3 | 13.06.2026 | Schema + Aurelia-Mock im Repo |
| M2 | 28.06.2026 | Walking-Skeleton regelbasiert lauffähig |
| M3 | 19.07.2026 | LLM-Slicer + Vektor-DB; Live BC2 → BC3 → BC4 |
| M4 | 02.08.2026 | Semester-1-Abnahme |

## Kontakt

- Issues: [coe-factory/issues](https://github.com/pg-coe-kmu/coe-factory/issues), Label `contract` für Schnittstellen-Änderungen
- Aktive Issues: #38 (Ticket-Format), #39 (Blueprint-Übergabe)
