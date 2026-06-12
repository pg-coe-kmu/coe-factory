# BC3 → BC4 — Bemerkungen

an BC4-Team,

das hier ist unser Liefer-Ordner an euch. Ihr findet hier Mock-Dateien zum Bauen gegen, ein JSON-Schema zur Validierung und pro Projekt einen Unterordner mit dem konkreten Ticket-Set.

## Wer wir sind

**BC3 — Engineering Architect:** Wir übersetzen das BC2-Automatisierungskonzept in Tickets, die ihr parsen und bauen könnt.

## Was hier liegt

```
contracts/bc3-to-bc4/
├── README.md             diese Datei
├── tickets.schema.json   JSON Schema 2020-12 — validiert die tickets.json
└── <projekt>/            ein Unterordner pro Projekt-Setting
    ├── tickets.json          die Hauptlieferung — Stories mit Akzeptanzkriterien
    ├── architecture.md       Bauplan mit Mermaid-Diagramm + Komponenten
    ├── api/openapi.yaml      OpenAPI 3.0 — Endpunkte je Story
    ├── compliance-audit.json Compliance-Vorprüfung (nicht für eure Pipeline — noch unsicher, wer es generiert)
    └── README.md             Einstieg in das Projekt
```

Aktuell drin:
- **mock** für Beispiel Aurelia Krankenkasse: Antragsbearbeitung Krankentagegeld

## Was BC4 braucht (und was nicht)

**Für eure Codegen-Pipeline:** `tickets.json` + `architecture.md` + `api/openapi.yaml`.

**Was ihr ignorieren könnt:** `compliance-audit.json` — das ist Audit-Material. Wir haben es im gleichen Ordner abgelegt, damit es Audit-mäßig zur Lieferung gehört, aber für eure Pipeline ist es irrelevant. Wo die Compliance-Prüfung am Ende stattfindet (bei uns, bei BC1/BC2, im Plattform-Team) ist noch zu klären.

## Wie tickets.json aufgebaut ist

Maximal reduziert — nur was ihr zum Bauen wirklich braucht.

**Eine Lieferung enthält:**
- Identität: `lieferung_id`, `schema_version`, `projekt_kurzname`
- Bezug zur BC2-Quelle: `konzept_ref` (Audit-Spur)
- `epics[]` — pro BC2-Use-Case ein Epic
- `gate2` — Status der menschlichen Freigabe vor Build

**Pro Epic:**
- `epic_id` (UUID, Format `ep-...`)
- `titel`, `ziel`
- `kategorien[]` — für euer Worker-Routing (z.B. `it:backend`, `it:ai-pipeline`)
- `stories[]`

**Pro Story:**
- `story_id` (UUID, Format `st-...-<n>`)
- `titel`, `beschreibung` (Als-Möchte-Damit)
- `akzeptanzkriterien[]` mit Messverfahren
- `abhaengigkeiten[]` (Verweise auf andere Story-IDs)

Konkretes Beispiel: schaut in `mock/tickets.json`.

## Validierung

Bevor wir liefern, validieren wir gegen das Schema. Ihr könnt das auch nochmal:

```bash
jsonschema -i aurelia/tickets.json tickets.schema.json
```

Wenn das grün ist, ist die Datei strukturell sauber.

## Compliance — wo das herkommt

Compliance-Vorprüfung passiert in unserer Pipeline **vor** der Story-Generierung. Ergebnis liegt in `compliance-audit.json`. Wenn dort eine Pflicht steht (z.B. „HitL-Prüfschritt bei Konfidenz <0,8"), wird daraus eine eigene Story im tickets.json. Ihr seht die Story wie jede andere — ihr müsst nicht prüfen, ob sie aus Compliance entstanden ist.

Bei Hochrisiko-KI (AI-Act Anhang III, z.B. Aurelia) pausiert unsere Pipeline vor der Lieferung, bis DSB freigibt. Das heißt: was bei euch ankommt, ist immer schon Compliance-gegengezeichnet.

*Wichtig: das ist noch nicht final entschieden. Einige Compliance-Aufgaben (PII-Filter, Audit-Log, Löschungs-Cron) gehören vermutlich vor BC3 — in BC1 oder ins Plattform-Team. Wir klären das mit Sergio + Mehdi.*

## Mock-Phase vs. später

Aktuell sind alle Dateien **händisch befüllt** als Mock. Damit könnt ihr eure n8n-Pipeline parallel bauen.

Ab M3 läuft unsere BC3-Pipeline selbst — Eingabe ist BC2-Output, Ausgabe sind diese Dateien automatisch. Format bleibt identisch.

## Sergios Vorgabe vom 16.05. — was wir einhalten, was wir abweichen

Im Projektplan (Abschnitt 3.2 BC3 → BC4) stand:

> *Ticket-Set: `ticket_id`, `typ` (epic/story/task), `titel`, `beschreibung`, `akzeptanzkriterien[]`, `api_spec_ref`, `security_requirements[]`, `aufwand_schaetzung`, `abhaengigkeiten[]`.*
> *Tickets per GitLab-API als Issues + `ticket_set.json`. Blueprint: Mermaid-C4 + JSON-Komponentenliste. API-Specs als OpenAPI 3.0 YAML. Freigabe nach Gate 2 (Security-by-Design-Check + Technical Approval).*

**Wir halten ein:**
- Schema-validiertes JSON-Ticket-Set
- Akzeptanzkriterien pro Story (mit Messverfahren ergänzt)
- Abhängigkeiten als ID-Verweise
- Blueprint als Mermaid (in `architecture.md`)
- API-Specs als OpenAPI 3.0 YAML (`api/openapi.yaml`)
- Gate 2 (`gate2.status` in tickets.json)

**Wir weichen ab:**
- **Felder `typ` + `aufwand_schaetzung` raus** — BC4 braucht beides nicht zum Bauen; sind PM-Felder, kein Codegen-Input
- **Statt einem `ticket_id`** trennen wir in `epic_id` + `story_id` (klare Hierarchie)
- **`security_requirements[]` raus** — Sicherheits-Anforderungen sind in `compliance-audit.json` als Pflichten dokumentiert und werden ggf. zu eigenen Stories


## Issues und Änderungswünsche

- Format-Konflikt oder Schema-Wunsch → ferne ein Issue mit Label `contract` oder WhattsApp :)
- Konkrete Fragen zur Mock-Lieferung → einfach Issue.

---

*Stand 12.06.2026 · Sabrina + Svetlana*
