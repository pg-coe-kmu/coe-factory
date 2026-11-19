# Bauplan — kp-06

**Lieferung:** `del-kp-06-2026-11-19-094806`  
**Konzept:** `4d53e481-b332-43c7-b191-63869059afd8`  
**Erzeugt am:** 2026-11-19 durch den BC3-Slicer

> Automatisch erzeugt aus dem Ticket-Set. Nicht von Hand ändern —
> Änderungen gehen beim nächsten Lauf verloren.

## Überblick

```mermaid
flowchart LR
  subgraph Eingang
    s0EMailTelefon["E-Mail / Telefon"]
    s5Angebotslist["Angebotsliste"]
  end
  subgraph Verarbeitung
    e0Automatisier["Automatisierte Extraktion von Reiseanfr…<br/>9 Stories"]
    e1Automatisier["Automatisierte Medienbruch-Integration …<br/>8 Stories"]
  end
  subgraph Ausgang
    s1Erfassungsbo["Erfassungsbogen"]
    s2n8n["n8n"]
    s3NocoDB["NocoDB"]
    s4Ollama["Ollama"]
    s7Vorgangslist["Vorgangsliste"]
    s8PostgreSQL16["PostgreSQL 16"]
  end
  subgraph "Lesend und schreibend"
    s6Anbieterport["Anbieterportal"]
  end
  s0EMailTelefon --> e0Automatisier
  s0EMailTelefon --> e1Automatisier
  e0Automatisier --> s1Erfassungsbo
  e0Automatisier --> s2n8n
  e1Automatisier --> s2n8n
  e0Automatisier --> s3NocoDB
  e1Automatisier --> s3NocoDB
  e0Automatisier --> s4Ollama
  s5Angebotslist --> e1Automatisier
  e1Automatisier --> s6Anbieterport
  s6Anbieterport --> e1Automatisier
  e1Automatisier --> s7Vorgangslist
  e1Automatisier --> s8PostgreSQL16
```

Die Epics stehen in der Reihenfolge der Umsetzungsempfehlung von BC2. Das ist kein Ablauf.

## Komponenten

| Komponente | Rolle | Anbindung | Use Case |
|---|---|---|---|
| E-Mail / Telefon | Quelle | Email | Reiseanfrage-Extraktion aus E-Mai…, Medienbruch-Integration zwischen … |
| Angebotsliste | Quelle | Manuell | Medienbruch-Integration zwischen … |
| Anbieterportal | Quelle+Ziel | API | Medienbruch-Integration zwischen … |
| Erfassungsbogen | Ziel | Manuell | Reiseanfrage-Extraktion aus E-Mai… |
| n8n | Ziel | API | Reiseanfrage-Extraktion aus E-Mai…, Medienbruch-Integration zwischen … |
| NocoDB | Ziel | API | Reiseanfrage-Extraktion aus E-Mai…, Medienbruch-Integration zwischen … |
| Ollama | Ziel | API | Reiseanfrage-Extraktion aus E-Mai… |
| Vorgangsliste | Ziel | DB | Medienbruch-Integration zwischen … |
| PostgreSQL 16 | Ziel | DB | Medienbruch-Integration zwischen … |

## Tech-Stack laut Konzept (BC2)

- n8n (self-hosted, Hetzner) — Workflow-Orchestrierung und E-Mail-Trigger
- Ollama mit Mistral oder Qwen — lokales LLM für Feldextraktion und Rückfrage-Generierung
- NocoDB (self-hosted, IONOS) — strukturierter Erfassungsbogen und Datenhaltung
- PostgreSQL 16 — persistente Protokollierung der Extraktionsergebnisse und Freigaben
- Anthropic Claude (EU-Region, optional, nur mit AVV) — Fallback für komplexe oder mehrdeutige E-Mails
- n8n (self-hosted, Hetzner) — Workflow-Orchestrierung und Anbieteranbindung
- NocoDB (self-hosted, IONOS) — Vorgangsliste und Angebotsliste als strukturierte Datenbasis
- PostgreSQL 16 — Protokollierung aller Aktionen und Rohantworten
- K3s — Container-Betrieb des RPA-Fallback-Dienstes (Playwright)
- Ollama mit Mistral oder Qwen — optionale Klassifikation von Freitext-Portalantworten
- GitLab CI (self-hosted) — Versionierung und Deployment der Workflow-Konfigurationen

## Epics und Stories

### Automatisierte Extraktion von Reiseanfragen aus E-Mails in strukturierten Erfassungsbogen

`ep-5df5-0da1-9841-5793dbd06895`  
**Ziel:** Automatisierung des ersten Schritts im Reisebuchungsprozess durch KI-gestützte Extraktion von Reisedaten aus E-Mails und strukturierte Ablage im Erfassungsbogen.  
**Kategorien:** it:backend, it:integration, it:ai-pipeline

| Story | Titel | Akzeptanzkriterien |
|---|---|---|
| 1 | Pflichtfeldschema für Erfassungsbogen dokumentieren und ver… | 1 |
| 2 | E-Mail-Postfach für Extraktionsdienst zugänglich machen | 1 |
| 3 | Extraktion von Reisedaten aus E-Mails implementieren | 3 |
| 4 | Lückenerkennung und Rückfrage-Entwurf generieren | 2 |
| 5 | Unsichere Extraktionsergebnisse kennzeichnen | 1 |
| 6 | Revisionssichere Protokollierung der Extraktionsergebnisse | 1 |
| 7 | Ausnahmebehandlung für nicht automatisierbare Anfragen | 1 |
| 8 | Transparenzhinweis für KI-gestützte Verarbeitung in E-Mails… | 1 |
| 9 | Pseudonymisierung von E-Mail-Adressen und Telefonnummern vo… | 1 |

### Automatisierte Medienbruch-Integration zwischen Angebotsliste, Anbieterportalen und Vorgangsliste

`ep-26d9-5ed3-1682-ce59de66b523`  
**Ziel:** Eine Integrationsschicht verbindet die interne Vorgangsliste mit Anbieterportalen, um Reservierungsnummern, Buchungsstatus und Stornierungen automatisch zu synchronisieren und Kundenbenachrichtigungen vorzubereiten.  
**Kategorien:** it:backend, it:integration

| Story | Titel | Akzeptanzkriterien |
|---|---|---|
| 1 | Strukturierte Datenbasis in NocoDB sicherstellen | 1 |
| 2 | Anbieterzugriffswege prüfen und dokumentieren | 1 |
| 3 | Automatisierte Reservierung beim Anbieter anlegen | 2 |
| 4 | Buchungsstatus automatisch abrufen und aufbereiten | 2 |
| 5 | Stornierungsaufruf beim Anbieter auslösen und Ergebnis vera… | 3 |
| 6 | Benachrichtigungsentwürfe für Kunden erstellen und zur Frei… | 1 |
| 7 | Hybriden Prozess für nicht-automatisierbare Anbieter unters… | 1 |
| 8 | Anbieterindividuelle Konfiguration der Integrationsschicht … | 1 |

---

2 Epics · 17 Stories · 9 Komponenten
