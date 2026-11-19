# BC3 – n8n-Workflows des Slicers

Stand 19.11.2026 abends: veröffentlichte Fassung aus n8n, bereinigt exportiert. Neu exportiert sind nur Workflows, die sich seit dem letzten Export geändert haben (19.11. abends: BC3-00, BC3-20, BC3-40, BC3-81). Die übrigen Dateien sind unverändert und stimmen mit der Fassung in n8n überein. Ablauf eines Laufs: [../ablauf-slicer.md](../ablauf-slicer.md).

## Änderungen am 19.11.2026 abends

Vertrag BC3 → BC4 3.7 (PR #411) und Gate 2:

- **BC3-20** (`f5d81ecf`): „Umschlag ergänzen“ setzt an jedes Akzeptanzkriterium von BC2 die Kennung `bc2_kriterium_id` (`bc2:<Priorisierung>/<Potenzial>/<Nr.>`, je 8 Zeichen der UUID, Nr. in der Reihenfolge von BC2). Ein Story-Kriterium trägt höchstens eine Kennung. Fehlt `priorisierung_id` oder die Potenzial-ID, gibt es keine Kennung und einen Befund im Laufprotokoll.
- **BC3-40** (`2bbf2d39`): Vertrag 3.7. „Compliance bereitstellen“ nimmt den geprüften Befund von BC3-30 statt der Rohantwort, damit der Vermerk `freiwillig` bei Hochrisiko-Artikeln im Compliance-Audit ankommt. „Lieferung prüfen“ erlaubt `bc2_kriterium_id` nur bei 3.7 und prüft das Muster; fehlen Kennungen, ist das ein weicher Befund.
- **BC3-00** (`f13b030b`): „Gate 2 vorbereiten“ hat den Prüfpunkt „Kriterien von BC2 vollständig“: stehen alle Kriterien von BC2 wörtlich und mit Kennung im Ticket-Set? Beim Prüfpunkt „Rechtsgrundlage“ sagt „Was hilft“ zuerst, wenn die Pflicht schon als freiwillig vermerkt ist.
- **BC3-81** (`c7126fde`): Der Satz oben auf der Seite verweist auf die Stichprobe der Akzeptanzkriterien in Bereich 5.

## Änderungen am 19.11.2026

Übergabe-Befund von BC0 vom 19.11. (UC1):

- **BC3-20** (`c4a65b75`): „Umschlag ergänzen“ setzt jedes Akzeptanzkriterium von BC2 wörtlich ins Ticket, mit dem Messverfahren von BC2 und in der Formulierung von BC2 („Gegeben …, wenn …, dann …“). Fehlt in der abdeckenden Story ein passendes Kriterium, wird es angehängt. Der Prompt des Story-Architekten verlangt die wörtliche Übernahme, eigene Kriterien bleiben Given/When/Then.
- **BC3-40** (`87f22da0`): Das Compliance-Audit nennt Stories mit derselben Kennung wie `ticket_set.json` (`abgedeckt_durch`, `stelle` und die Befunde aus BC3-20), vorher mit der Zwischenkennung aus BC3-20.

## Änderungen am 18.11.2026

- **BC3-00** (`a4282226`): Rückweg an Gate 2. „Nachbessern“ startet über „Neu starten?“ und „BC3-00 neu starten“ einen neuen Lauf mit demselben Konzept und dem Kommentar, höchstens dreimal (Eingänge `gate2_kommentar`, `vorlauf`, `runde`, `liefermodus`). Liefermodus `test` für Simulation, Übungsmandant und Start von Hand ohne `liefermodus`, der Neustart behält den Modus. Die Gate-2-Nachricht geht zusätzlich an Legal (eigener Telegram-Baustein).
- **BC3-20** (`212ecebc`): „Kriterien reparieren“ und „Ergänzung bereinigen“ übernehmen das Messverfahren von BC2 wörtlich, wo es eines gibt, sonst „offen“. „Modus setzen“ gibt den Gate-2-Kommentar an den Story-Architekten.
- **BC3-30** (`a1105411`): „Modus setzen“ gibt den Gate-2-Kommentar an den Compliance-Agenten. „Einstufung gegenprüfen“ vermerkt Pflichten aus Art. 9, 12–15 und 17 KI-VO bei einer Risikoklasse unter `high` als `freiwillig: true` mit Hinweis, gelöscht wird nichts.
- **BC3-40** (`bcb5d19c`): Vertrag BC3 → BC4 3.6. „Tickets und Audit bauen“ schreibt die IDs von BC2 in `konzept_ref` und `potenzial_id` je Epic, „Lieferung prüfen“ prüft nach Schema 3.6.
- **BC3-80** (`a04bbec4`): Schreibt `ticket_set`, `compliance_audit`, `blueprint`, `priorisierung_id`, `konzept_id`, `potenzial_ids` und `status` in `bc3.lieferungen` und setzt ältere gültige Zeilen desselben Pakets und Kernprozesses auf veraltet. Nach dem Pull Request wartet BC3-80 auf die Prüfung „Schema und Vollständigkeit“ und führt nur bei grün zusammen, sonst bleibt der Pull Request offen und der Befund steht in `fehler`.
- **BC3-83** (`2648bf7d`): neu im Repo. Misst einmal im Monat Precision, Recall und F1 der Risikoklasse von BC3-30 an den 16 Fällen aus [../pruefstand/risikoklasse-faelle.json](../pruefstand/risikoklasse-faelle.json), Ergebnis in der Tabelle `pruefstand`. Nachweis: [../nachweis-pruefstand-reproduzierbarkeit.md](../nachweis-pruefstand-reproduzierbarkeit.md).

## Was bereinigt ist

- Keine Zugangsdaten, keine Credential-IDs. An den Bausteinen steht nur der Name des Zugangs (Tabelle unten).
- Keine Pin-Daten, keine Testdaten, kein gespeicherter Zustand, keine Besitzer- und Instanzangaben. Ausnahme: BC3-83 enthält im Code die 16 erfundenen Prüffälle, dieselben wie in [../pruefstand/risikoklasse-faelle.json](../pruefstand/risikoklasse-faelle.json).
- Instanz-Adresse, Webhook-Pfade, Telegram-Chats und Drive-Ordner sind Platzhalter.
- Die Workflow-IDs der Unterworkflows und des Error Workflows sind die der Originalinstanz. Nach einem Import neu wählen (Tabelle unten).

## Workflows

| Nr. | Datei | Aufgabe | ID in der Originalinstanz | Fassung | Export |
|---|---|---|---|---|---|
| BC3-00 | [bc3-00-orchestrator.json](bc3-00-orchestrator.json) | Steuert einen Lauf, hält an Gate 2 an, schreibt den Abschluss | `Mi0FNs8k9wCMgHQu` | `f13b030b` | 19.11. |
| BC3-01 | [bc3-01-neue-lieferung-suchen.json](bc3-01-neue-lieferung-suchen.json) | Sucht alle 15 Minuten neue Konzepte von BC2 und startet BC3-00 | `ffLq7cRw96M8YHck` | `5fb15f01` | 23.10. |
| BC3-10 | [bc3-10-konzept-einlesen.json](bc3-10-konzept-einlesen.json) | Liest das Konzept und prüft den Eingang | `L0kJaQpzehSf6LKY` | `a2f5105e` | 25.10. |
| BC3-11 | [bc3-11-datei-aus-github-holen.json](bc3-11-datei-aus-github-holen.json) | Holt eine Datei aus `coe-factory` | `ehcA304UI8tpGUIQ` | `4c577604` | 23.10. |
| BC3-15 | [bc3-15-plan-festlegen.json](bc3-15-plan-festlegen.json) | Legt mit festen Regeln fest, welche Stufe in welchem Modus läuft, ein KI-Ratgeber meldet Lücken | `V9FJSchlZhzjIw8R` | `b5cccc36` | 23.10. |
| BC3-20 | [bc3-20-stories-schneiden.json](bc3-20-stories-schneiden.json) | Schneidet Epics und Stories (KI) | `dYZc5Z0JGsd03ZMS` | `f5d81ecf` | 19.11. |
| BC3-30 | [bc3-30-compliance-pruefen.json](bc3-30-compliance-pruefen.json) | Prüft die Epics gegen EU AI Act und DSGVO, setzt Ampel und Risikoklasse (KI) | `4MH1nHOhouKuDtP9` | `a1105411` | 18.11. |
| BC3-40 | [bc3-40-tickets-bauen-und-pruefen.json](bc3-40-tickets-bauen-und-pruefen.json) | Baut `tickets.json` und `compliance-audit.json` und prüft beides gegen den Vertrag mit BC4 | `rc7L7WfB4HOwZuN5` | `2bbf2d39` | 19.11. |
| BC3-50 | [bc3-50-architektur.json](bc3-50-architektur.json) | Erzeugt `architecture.md` und `blueprint.json` aus den Tickets, API-Teil abgeschaltet | `ScGYz1bQxqryE9Iy` | `29c7a4dc` | 23.10. |
| BC3-70 | [bc3-70-ausliefern.json](bc3-70-ausliefern.json) | Legt die Lieferung zur Ansicht in Google Drive ab und sammelt die offenen Punkte | `bHwGl0vFoE8v2O00` | `143d92f0` | 23.10. |
| BC3-80 | [bc3-80-gate-2-freigabe.json](bc3-80-gate-2-freigabe.json) | Setzt die Entscheidung an Gate 2 um (Pull Request, Team-Datenbank) | `btNCECvEp5neQ2h4` | `a04bbec4` | 18.11. |
| BC3-81 | [bc3-81-gate-2-seite.json](bc3-81-gate-2-seite.json) | Gate-2-Seite zum Entscheiden (Webhook) | `eKr8CANKYO4OyM27` | `c7126fde` | 19.11. |
| BC3-82 | [bc3-82-uebersicht.json](bc3-82-uebersicht.json) | Übersicht über Läufe, Fehler und Lieferungen (Webhook mit Passwort) | `1I8HbQb1g6SCRipA` | `561f065d` | 25.10. |
| BC3-83 | [bc3-83-pruefstand.json](bc3-83-pruefstand.json) | Prüfstand: misst einmal im Monat, wie gut BC3-30 die Risikoklasse trifft (16 erfundene Fälle), schreibt in `pruefstand` | `m6uKYlxaLRoKshhv` | `2648bf7d` | 18.11. |
| BC3-90 | [bc3-90-live-demo.json](bc3-90-live-demo.json) | Live-Demo für Präsentationen: Seite mit Passwort, zeigt einen Lauf Schritt für Schritt bis zur Entscheidung an Gate 2. „Jetzt prüfen“ ruft BC3-01 auf und startet neue, an Gate 1 freigegebene Lieferungen von BC2 im Modus `echt` (nach Freigabe Pull Request an BC4), ohne neue Lieferung nur eine Meldung. „Testfall“ startet das simulierte UC1 im Modus `test` | `YkJfiOq1fJwAqVQD` | `5234c493` | 31.10. |
| BC3-91 | [bc3-91-laufprotokoll.json](bc3-91-laufprotokoll.json) | Schreibt den Stand eines Laufs in `laeufe` | `lJEmDjgpCHVBybUO` | `88ef8092` | 25.10. |
| BC3-99 | [bc3-99-fehlerprotokoll.json](bc3-99-fehlerprotokoll.json) | Error Workflow aller BC3-Workflows, schreibt in `fehler` | `D03E5Rn1DDKDZGbL` | `cb04a573` | 23.10. |

## Zugänge

In n8n vor dem Import anlegen, Werte nicht ins Repo.

| Name im Export | Art | Genutzt in |
|---|---|---|
| Postgres BC3 | Postgres (Supabase `bc3-slicer`) | BC3-00, 01, 80, 81, 82, 83, 90, 91, 99 |
| Postgres Team-Datenbank | Postgres (Team-Datenbank, Schema `bc3`) | BC3-80 |
| GitHub coe-factory | GitHub API, nur dieses Repo | BC3-80 |
| PG n8n uni | Mistral Cloud | BC3-15 |
| Mistral PG (OpenAI-Schnittstelle) | OpenAI API mit Mistral-Adresse | BC3-20, 30 |
| PG | Telegram API (Bot) | BC3-00 (zwei Bausteine: Betrieb und Legal) |
| vs drive | Google Drive OAuth2 | BC3-70 |
| BC3 Übersicht Betrieb, BC3 Übersicht Legal | Basic Auth, je eine Adresse | BC3-82, BC3-90 |

## Platzhalter

| Platzhalter | Wo | Was eintragen |
|---|---|---|
| `__N8N_ADRESSE__` | BC3-00 „Lauf einstellen“ und Link zur Ausführung | Adresse der eigenen n8n-Instanz |
| `__PFAD_GATE2__` | BC3-81 Webhooks, BC3-00, BC3-82 | Pfad der Gate-2-Seite |
| `__PFAD_UEBERSICHT__`, `__PFAD_UEBERSICHT_LEGAL__` | BC3-82 Webhooks, Code und Notiz | Pfade der Übersicht |
| `__TELEGRAM_CHAT_ID__`, `__TELEGRAM_CHAT_ID_LEGAL__` | BC3-00 „Lauf einstellen“ | Chats für die Gate-2-Nachricht (Betrieb und Legal) |
| `__DRIVE_ORDNER_VORSCHAU__` | BC3-00 „Lauf einstellen“, BC3-90 Seite | Drive-Ordner `_vorschau` |
| `__PFAD_LIVE__`, `__PFAD_LIVE_LEGAL__`, `__PFAD_LIVE_START__`, `__PFAD_LIVE_STAND__` | BC3-90 Webhooks und Seite, BC3-82 „Link zur Live-Demo“ | Pfade der Live-Demo: Seite (mit Passwort, je eine Adresse für Betrieb und Legal), Start und Stand (prüfen einen Schlüssel, den die Seite beim Ausliefern bekommt) |
| `__PFAD_PRAESENTATION__`, `__PFAD_PRAESENTATION_LEGAL__` | BC3-82 „Link zur Live-Demo“ | Pfade der Präsentation (BC3-94, nicht im Repo, weil Vortragsmaterial) |

## Import

Reihenfolge: BC3-99, 91, 11, dann 10, 15, 20, 30, 40, 50, 70, 80, danach 00, 01, 81, 82, 83, 90. Danach in jedem Workflow den Error Workflow (BC3-99) und an jedem Baustein *Execute Workflow* den aufgerufenen Workflow neu wählen (die IDs oben helfen bei der Zuordnung).
