# Bauplan — kp-05

**Lieferung:** `del-kp-05-2026-10-14-090557`  
**Konzept:** `5d82f848-fdbc-40a9-9169-c03c0893b077`  
**Erzeugt am:** 2026-10-14 durch den BC3-Slicer

> Automatisch erzeugt aus dem Ticket-Set. Nicht von Hand ändern —
> Änderungen gehen beim nächsten Lauf verloren.

## Überblick

```mermaid
flowchart LR
  subgraph Eingang
    s0NextcloudHub["Nextcloud Hub"]
    s3PaddleOCR["PaddleOCR"]
    s6Authentik["Authentik"]
  end
  subgraph Verarbeitung
    e0Automatisier["Automatisierte KI-gestützte Wissenssuche<br/>10 Stories"]
  end
  subgraph Ausgang
    s2Qdrant["Qdrant"]
    s4Ollama["Ollama"]
    s5PostgreSQL16["PostgreSQL 16"]
  end
  subgraph "Lesend und schreibend"
    s1n8n["n8n"]
  end
  s0NextcloudHub --> e0Automatisier
  e0Automatisier --> s1n8n
  e0Automatisier --> s2Qdrant
  s3PaddleOCR --> e0Automatisier
  e0Automatisier --> s4Ollama
  e0Automatisier --> s5PostgreSQL16
  s6Authentik --> e0Automatisier
```

## Komponenten

| Komponente | Rolle | Anbindung | Use Case |
|---|---|---|---|
| Nextcloud Hub | Quelle | API | KI-gestützte Wissenssuche im Goog… |
| PaddleOCR | Quelle | API | KI-gestützte Wissenssuche im Goog… |
| Authentik | Quelle | API | KI-gestützte Wissenssuche im Goog… |
| n8n | Quelle+Ziel | API | KI-gestützte Wissenssuche im Goog… |
| Qdrant | Ziel | API | KI-gestützte Wissenssuche im Goog… |
| Ollama | Ziel | API | KI-gestützte Wissenssuche im Goog… |
| PostgreSQL 16 | Ziel | DB | KI-gestützte Wissenssuche im Goog… |

## Empfohlener Stack

- Qdrant (self-hosted, Hetzner) — Vector-DB für semantische Indizierung und gefilterte Abfragen
- Ollama mit Mistral oder Qwen — lokales LLM für Embedding-Generierung und Antwortvorschläge (EU, OSS, kein Datenabfluss)
- PaddleOCR — Texterkennung für nicht-native Dokumente
- n8n (self-hosted, Hetzner) — Orchestrierung der Indizierungspipeline, Webhook-Anbindung und Scheduler
- PostgreSQL 16 — persistente Ablage von Chunk-Metadaten, Quellenverweisen und Anfrage-Protokollen
- Authentik (self-hosted, IONOS) — Identitätsprüfung und Berechtigungsgruppen für die Zugriffsrechtespiegelung
- Nextcloud Hub (self-hosted, Hetzner) — primäre Dokumentenquelle; API-Zugriff auf Ordnerstruktur und Dateimetadaten
- Anthropic Claude API (EU-Region, nur mit gültigem AVV) — optionaler Fallback für komplexe Antwortgenerierung, wenn lokal betriebene Modelle dokumentiert nicht ausreichen

## Epics und Stories

### Automatisierte KI-gestützte Wissenssuche

`ep-35ec-f2fb-68d5-6d6dddfa6fa7`  
**Ziel:** Automatisierung der Wissenssuche im Google-Drive-Bestand durch eine KI-gestützte Anwendung.  
**Kategorien:** it:backend, it:integration

| Story | Titel | Akzeptanzkriterien |
|---|---|---|
| 1 | Indizierung der freigegebenen Dokumente | 2 |
| 2 | Zugriffsrechtespiegelung | 2 |
| 3 | Generierung von Antwortvorschlägen | 2 |
| 4 | Fehler- und Eingabemanagement | 2 |
| 5 | Protokollierung und Statusvergabe | 2 |
| 6 | Einhaltung der EU-First- und Open-Source-First-Maxime | 1 |
| 7 | Teilantwort bei unvollständiger Beleglage | 1 |
| 8 | Belegtreue der Quellenangaben | 1 |
| 9 | Transparenzhinweis in der UI | 1 |
| 10 | Zugriffsrechtespiegelung | 1 |

---

1 Epics · 10 Stories · 7 Komponenten
