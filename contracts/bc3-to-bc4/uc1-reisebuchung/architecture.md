# Bauplan — uc1-reisebuchung

**Lieferung:** `del-uc1-reisebuchung-2026-09-10-173311`  
**Konzept:** `b1000000-0000-4000-8000-0000000000c1`  
**Erzeugt am:** 2026-09-10 durch den BC3-Slicer

> Automatisch erzeugt aus dem Ticket-Set. Nicht von Hand ändern —
> Änderungen gehen beim nächsten Lauf verloren.

## Überblick

```mermaid
flowchart LR
  subgraph Eingang
    s1WebFormularR["Web-Formular Reiseanfrage"]
  end
  subgraph Verarbeitung
    e0Reiseanfrage["Reiseanfrage automatisch erfassen und V…<br/>9 Stories"]
    e1Automatisier["Automatisierte Angebotserstellung und B…<br/>8 Stories"]
  end
  subgraph "Lesend und schreibend"
    s0OutlookPostf["Outlook-Postfach reisen@noroai"]
    s2ReiseAPItrav["Reise-API (travel-mock-api)"]
    s3Vorgangsabla["Vorgangsablage"]
  end
  s0OutlookPostf --> e0Reiseanfrage
  e1Automatisier --> s0OutlookPostf
  s1WebFormularR --> e0Reiseanfrage
  e0Reiseanfrage --> s2ReiseAPItrav
  e1Automatisier --> s2ReiseAPItrav
  e0Reiseanfrage --> s3Vorgangsabla
  e1Automatisier --> s3Vorgangsabla
  e0Reiseanfrage --> e1Automatisier
```

## Komponenten

| Komponente | Rolle | Anbindung | Use Case |
|---|---|---|---|
| Web-Formular Reiseanfrage | Quelle | API | Reiseanfrage automatisch erfassen… |
| Outlook-Postfach reisen@noroai | Quelle, Quelle+Ziel | Email | Reiseanfrage automatisch erfassen…, Angebot erstellen und Buchung nac… |
| Reise-API (travel-mock-api) | Quelle+Ziel, Ziel | API | Reiseanfrage automatisch erfassen…, Angebot erstellen und Buchung nac… |
| Vorgangsablage | Ziel, Quelle+Ziel | DB | Reiseanfrage automatisch erfassen…, Angebot erstellen und Buchung nac… |

## Empfohlener Stack

- n8n
- Mistral Large
- PostgreSQL
- travel-mock-api

## Epics und Stories

### Reiseanfrage automatisch erfassen und Verfügbarkeit prüfen

`ep-7f86-9601-99bb-d235c7490f7d`  
**Ziel:** Automatisierte Erfassung und Verfügbarkeitsprüfung von Reiseanfragen innerhalb von zwei Minuten mit strukturierter Rückmeldung und Protokollierung.  
**Kategorien:** it:backend, it:integration

| Story | Titel | Akzeptanzkriterien |
|---|---|---|
| 1 | Reiseanfragen aus Mail und Web-Formular einheitlich erfassen | 3 |
| 2 | Projekt- oder Kostenstellenzuordnung prüfen | 1 |
| 3 | Budgetrahmen prüfen und Freigabe einholen | 2 |
| 4 | Verfügbarkeit in Buchungsportalen prüfen | 2 |
| 5 | Extraktionskonfidenz prüfen und manuelle Prüfung auslösen | 1 |
| 6 | Eingangsbestätigung und Rückfragen strukturiert versenden | 2 |
| 7 | Vorgangsprotokollierung mit Zeitstempel und IDs | 1 |
| 8 | Aufsichtsführung für Verfügbarkeitsprüfung einbauen | 2 |
| 9 | Transparenzhinweis in Eingangsbestätigung und Angebot einba… | 1 |

### Automatisierte Angebotserstellung und Buchungsauslösung nach Freigabe

`ep-9539-ba84-470c-dc60f3f7c980`  
**Ziel:** Automatisierte Erstellung von Angeboten aus geprüften Optionen, Versand mit eindeutiger Zuordnung, Erfassung der Zusage und Auslösung der Buchung nach menschlicher Freigabe.  
**Kategorien:** it:backend, it:integration

| Story | Titel | Akzeptanzkriterien |
|---|---|---|
| 1 | Angebot aus geprüften Optionen generieren | 2 |
| 2 | Angebot mit Vorgangs-ID versenden und Antwort zuordnen | 2 |
| 3 | Zusage erfassen und Vorgang für Freigabe vorbereiten | 2 |
| 4 | Buchung nach Freigabe auslösen und Buchungsnummern speichern | 2 |
| 5 | Ablauf von Optionen prüfen und aktualisiertes Angebot erzeu… | 1 |
| 6 | Erinnerungen bei ausbleibender Antwort senden und Vorgang s… | 2 |
| 7 | Stornierung als Statuswechsel mit Protokolleintrag erfassen | 1 |
| 8 | Menschliche Freigabe vor Buchungsauslösung einbauen | 2 |

---

2 Epics · 17 Stories · 4 Komponenten
