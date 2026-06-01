# BC0 — Vorarbeit / Preparatory Work
 
**Team:** Simeon (Lead) **Phase:** 0 — Vorbereitung (Baseline-Aufbau)
 
---
 
## Zweck
 
KI-vorbereitende Befüllung der **SSoT-Baseline** vor dem ersten BC1-Lauf: Self-Rating nach Bitkom, Unternehmensprofil NoroAI, Prozesslandkarte, Reifegrad pro Prozess, Spinnennetz-Profile. Ohne BC0 keine Baseline — und ohne Baseline kein BC1.
 
---
 
## Messages
 
- **Consumed:** Bitkom-Excel-Checklist · NoroAI v5.1-Profil · KP-Stammdaten · Process-Owner-Inputs
- **Produced:** Baseline-Datensatz in der SSoT · Reifegradbericht (Pflichtartefakt) · Mock-Pakete für BC2
---
 
## Arbeitspakete
 
- **AP 0.1** Dokumentation + Methodik (Bitkom-Kurzfassung · Spinnennetz-Spec · Unternehmensprofil · Prozessfragen)
- **AP 0.2** Self-Rating + Reifegradfeststellung (4 Excels · 600 Items · Prozessautomatisierungs-Matrix · Cross-funktionale Matrix · Reifegradbericht v1)
- **AP 0.3** Brief + Architektur (BC0-Brief · BC1-Architektur v6)
- **AP 0.4** Schnittstelle BC2 + Mocks (BC2-Übergabetermin · Mock-Daten BC1→BC2 · Automatisierungs-Fragen für BC1)
- **AP 0.5** Repo + Präsentationen (README · GitHub-AP-Pflege · 1. Präsentation · DB-Schema-Spec · 2. Präsentation)
- **AP 0.6** DB-Pipeline (PostgreSQL-Schema · Excel→DB · YAML-Master · YAML→DB · Smoke-Test)
- **AP 0.7** Übergabe (Reifegradbericht v2 DB-aggregiert · Handover an Richard · Status-Review)
---
 
## Schnittstellen
 
- **Output an BC1:** Baseline-Datensatz in SSoT (Unternehmensprofil · Prozesslandkarte · Reifegrad · Spinnennetz) — Read-API / SQL-Views (siehe `/contracts/bc0-to-bc1/`)
- **Output an BC2 (indirekt über BC1):** Mock-Pakete als Schnittstellen-Vorlagen (siehe `/contracts/examples/`)
---
