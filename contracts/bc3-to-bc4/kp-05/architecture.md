# Bauplan — kp-05

**Lieferung:** `del-kp-05-2026-10-11-185943`  
**Konzept:** `5d82f848-fdbc-40a9-9169-c03c0893b077`  
**Erzeugt am:** 2026-10-11 durch den BC3-Slicer

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
    e0KIgesttzteWi["KI-gestützte Wissenssuche im Google-Dri…<br/>4 Stories"]
  end
  subgraph Ausgang
    s2Qdrant["Qdrant"]
    s4Ollama["Ollama"]
    s5PostgreSQL16["PostgreSQL 16"]
  end
  subgraph "Lesend und schreibend"
    s1n8n["n8n"]
  end
  s0NextcloudHub --> e0KIgesttzteWi
  e0KIgesttzteWi --> s1n8n
  e0KIgesttzteWi --> s2Qdrant
  s3PaddleOCR --> e0KIgesttzteWi
  e0KIgesttzteWi --> s4Ollama
  e0KIgesttzteWi --> s5PostgreSQL16
  s6Authentik --> e0KIgesttzteWi
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

### KI-gestützte Wissenssuche im Google-Drive-Bestand

`ep-b460-4f9d-bb2b-f789f03f5de5`  
**Ziel:** Automatisierte und quellenbasierte Antwortgenerierung auf Nutzerfragen aus Google Drive.  
**Kategorien:** it:backend, it:integration

| Story | Titel | Akzeptanzkriterien |
|---|---|---|
| 1 | Durchführung der Indizierung der Drive-Dokumente | 1 |
| 2 | Frageverarbeitung und Antwortgenerierung | 2 |
| 3 | Zugriffsrechtespiegelung | 1 |
| 4 | Widersprüchliche Dokumentversionen erkennen | 1 |

---

1 Epics · 4 Stories · 7 Komponenten
