# BC3 – n8n-Workflows des Slicers

Stand 23.10.2026: veröffentlichte Fassung aus n8n, bereinigt exportiert. Ablauf eines Laufs: [../ablauf-slicer.md](../ablauf-slicer.md).

## Was bereinigt ist

- Keine Zugangsdaten, keine Credential-IDs. An den Bausteinen steht nur der Name des Zugangs (Tabelle unten).
- Keine Pin-Daten, keine Testdaten, kein gespeicherter Zustand, keine Besitzer- und Instanzangaben.
- Instanz-Adresse, Webhook-Pfade, Telegram-Chat und Drive-Ordner sind Platzhalter.
- Die Workflow-IDs der Unterworkflows und des Error Workflows sind die der Originalinstanz. Nach einem Import neu wählen (Tabelle unten).

## Workflows

| Nr. | Datei | Aufgabe | ID in der Originalinstanz |
|---|---|---|---|
| BC3-00 | [bc3-00-orchestrator.json](bc3-00-orchestrator.json) | Steuert einen Lauf, hält an Gate 2 an, schreibt den Abschluss | `Mi0FNs8k9wCMgHQu` |
| BC3-01 | [bc3-01-neue-lieferung-suchen.json](bc3-01-neue-lieferung-suchen.json) | Sucht alle 15 Minuten neue Konzepte von BC2 und startet BC3-00 | `ffLq7cRw96M8YHck` |
| BC3-10 | [bc3-10-konzept-einlesen.json](bc3-10-konzept-einlesen.json) | Liest das Konzept und prüft den Eingang | `L0kJaQpzehSf6LKY` |
| BC3-11 | [bc3-11-datei-aus-github-holen.json](bc3-11-datei-aus-github-holen.json) | Holt eine Datei aus `coe-factory` | `ehcA304UI8tpGUIQ` |
| BC3-15 | [bc3-15-plan-festlegen.json](bc3-15-plan-festlegen.json) | Legt mit festen Regeln fest, welche Stufe in welchem Modus läuft, ein KI-Ratgeber meldet Lücken | `V9FJSchlZhzjIw8R` |
| BC3-20 | [bc3-20-stories-schneiden.json](bc3-20-stories-schneiden.json) | Schneidet Epics und Stories (KI) | `dYZc5Z0JGsd03ZMS` |
| BC3-30 | [bc3-30-compliance-pruefen.json](bc3-30-compliance-pruefen.json) | Prüft die Epics gegen EU AI Act und DSGVO, setzt Ampel und Risikoklasse (KI) | `4MH1nHOhouKuDtP9` |
| BC3-40 | [bc3-40-tickets-bauen-und-pruefen.json](bc3-40-tickets-bauen-und-pruefen.json) | Baut `tickets.json` und `compliance-audit.json` und prüft beides gegen den Vertrag mit BC4 | `rc7L7WfB4HOwZuN5` |
| BC3-50 | [bc3-50-architektur.json](bc3-50-architektur.json) | Erzeugt `architecture.md` und `blueprint.json` aus den Tickets, API-Teil abgeschaltet | `ScGYz1bQxqryE9Iy` |
| BC3-70 | [bc3-70-ausliefern.json](bc3-70-ausliefern.json) | Legt die Lieferung zur Ansicht in Google Drive ab und sammelt die offenen Punkte | `bHwGl0vFoE8v2O00` |
| BC3-80 | [bc3-80-gate-2-freigabe.json](bc3-80-gate-2-freigabe.json) | Setzt die Entscheidung an Gate 2 um (Pull Request, Team-Datenbank) | `btNCECvEp5neQ2h4` |
| BC3-81 | [bc3-81-gate-2-seite.json](bc3-81-gate-2-seite.json) | Gate-2-Seite zum Entscheiden (Webhook) | `eKr8CANKYO4OyM27` |
| BC3-82 | [bc3-82-uebersicht.json](bc3-82-uebersicht.json) | Übersicht über Läufe, Fehler und Lieferungen (Webhook mit Passwort) | `1I8HbQb1g6SCRipA` |
| BC3-91 | [bc3-91-laufprotokoll.json](bc3-91-laufprotokoll.json) | Schreibt den Stand eines Laufs in `laeufe` | `lJEmDjgpCHVBybUO` |
| BC3-99 | [bc3-99-fehlerprotokoll.json](bc3-99-fehlerprotokoll.json) | Error Workflow aller BC3-Workflows, schreibt in `fehler` | `D03E5Rn1DDKDZGbL` |

## Zugänge

In n8n vor dem Import anlegen, Werte nicht ins Repo.

| Name im Export | Art | Genutzt in |
|---|---|---|
| Postgres BC3 | Postgres (Supabase `bc3-slicer`) | BC3-00, 01, 80, 81, 82, 91, 99 |
| Postgres Team-Datenbank | Postgres (Team-Datenbank, Schema `bc3`) | BC3-80 |
| GitHub coe-factory | GitHub API, nur dieses Repo | BC3-80 |
| PG n8n uni | Mistral Cloud | BC3-15 |
| Mistral PG (OpenAI-Schnittstelle) | OpenAI API mit Mistral-Adresse | BC3-20, 30 |
| PG | Telegram API (Bot) | BC3-00 |
| vs drive | Google Drive OAuth2 | BC3-70 |
| BC3 Übersicht Betrieb, BC3 Übersicht Legal | Basic Auth, je eine Adresse | BC3-82 |

## Platzhalter

| Platzhalter | Wo | Was eintragen |
|---|---|---|
| `__N8N_ADRESSE__` | BC3-00 „Lauf einstellen“ und Link zur Ausführung | Adresse der eigenen n8n-Instanz |
| `__PFAD_GATE2__` | BC3-81 Webhooks, BC3-00, BC3-82 | Pfad der Gate-2-Seite |
| `__PFAD_UEBERSICHT__`, `__PFAD_UEBERSICHT_LEGAL__` | BC3-82 Webhooks, Code und Notiz | Pfade der Übersicht |
| `__TELEGRAM_CHAT_ID__` | BC3-00 „Lauf einstellen“ | Chat für die Gate-2-Nachricht |
| `__DRIVE_ORDNER_VORSCHAU__` | BC3-00 „Lauf einstellen“ | Drive-Ordner `_vorschau` |

## Import

Reihenfolge: BC3-99, 91, 11, dann 10, 15, 20, 30, 40, 50, 70, 80, danach 00, 01, 81, 82. Danach in jedem Workflow den Error Workflow (BC3-99) und an jedem Baustein *Execute Workflow* den aufgerufenen Workflow neu wählen (die IDs oben helfen bei der Zuordnung).
