# BC3 → BC4: der Liefer-Ordner

An das BC4-Team,

hier liegen die Lieferungen von BC3. Ein Unterordner je Projekt, darin ein Ordner je Lieferung, dazu das JSON-Schema,
gegen das ihr die Tickets validieren könnt.

## Wer wir sind

**BC3, Engineering Architect.** Wir übersetzen das Automatisierungskonzept von BC2 in
Tickets, die ihr parsen und bauen könnt.

## Was hier liegt

```
contracts/bc3-to-bc4/
├── README.md               diese Datei
├── tickets.schema.json     JSON Schema 2020-12, validiert die ticket_set.json
├── mock/                   Beispiel Aurelia Krankenkasse, erfundene Daten
└── <projekt>/              ein Ordner je Projekt (Kernprozess, z. B. kp-05)
    └── <lieferung_id>/         ein Ordner je Lieferung, z. B. del-kp-05-2026-10-23-081500
        ├── ticket_set.json         die Hauptlieferung: Epics mit Stories
        ├── blueprint.json          Bauplan als JSON: Komponenten, Datenflüsse, Entscheidungspunkte
        ├── architecture.md         derselbe Bauplan als Text, mit Mermaid-Diagramm
        └── compliance-audit.json   Compliance-Vorprüfung, Audit-Material
```

Seit 23.10.2026 bekommt jede Lieferung einen eigenen Ordner, damit sich Lieferungen zum
selben Kernprozess nicht überschreiben. Die aktuelle Lieferung ist die mit der jüngsten
`lieferung_id` (Datum und Uhrzeit stehen im Namen). Dateien direkt unter `<projekt>/` stammen
aus der Zeit davor.

### Gültige, Test- und veraltete Lieferungen

Nur Ordner, die mit `del-` beginnen, sind gültige Lieferungen. Alles andere bitte nicht
als Ergebnis werten.

| Präfix | Bedeutung |
|---|---|
| `del-` | gültige Lieferung aus einem echten Lauf |
| `test-del-` | Testlauf mit Übungsmandant oder Simulation, nur zum Ausprobieren |
| `veraltet-del-` | echter Lauf, aber alter Stand, durch eine neuere Lieferung ersetzt, nicht mehr maßgeblich |

Stand 19.11.2026:

| Projekt | Ordner | Art |
|---|---|---|
| kp-06 | `del-kp-06-2026-11-19-104358` | **gültig**, UC1 (Reisebuchung), Vertrag 3.7 mit Kennung je Kriterium von BC2 |
| kp-05 | `del-kp-05-2026-11-19-105004` | **gültig**, UC2 (Wissenssuche), Vertrag 3.7 mit Kennung je Kriterium von BC2 |
| kp-01 | `test-del-kp-01-2026-11-13-130559` | Übungsmandant |
| kp-01 | `test-del-kp-01-2026-11-18-183750` | Übungsmandant (Vertrag 3.6) |
| kp-06 | `test-del-kp-06-2026-11-15-210539` | Simulation |
| kp-05 | `veraltet-del-kp-05-2026-10-26-185111` | alter Stand |
| kp-06 | `veraltet-del-kp-06-2026-10-31-090033`, `-11-02-172536`, `-11-03-184824` | alter Stand |
| kp-06 | `veraltet-del-kp-06-2026-11-18-201545` | ersetzt durch `del-kp-06-2026-11-19-094806` |
| kp-06 | `veraltet-del-kp-06-2026-11-19-094806` | ersetzt durch `del-kp-06-2026-11-19-104358` |

Maßgeblich für UC1 ist `del-kp-06-2026-11-19-104358`, für UC2 `del-kp-05-2026-11-19-105004`
(erstes gültiges Ticket für UC2). Beide nach Vertrag 3.7: Jedes Akzeptanzkriterium von BC2 steht
wörtlich im Ticket-Set und trägt seine Kennung `bc2_kriterium_id` (UC1: 6, UC2: 4). Die Stories von
UC1 sind gegenüber dem Morgen des 19.11. neu geschnitten (19 Stories, 29 Kriterien), bitte neu
generieren. In `compliance-audit.json` von UC1 steht bei p9 Artikel 12 der KI-Verordnung, der nur
für Hochrisiko-Systeme gilt; die Pflicht ist dort als `freiwillig` vermerkt, das System ist als
begrenztes Risiko eingestuft.

## Was BC4 braucht, und was nicht

**Für eure Pipeline:** `ticket_set.json`, `blueprint.json`.

**Zum Nachschlagen für Menschen:** `architecture.md`, derselbe Inhalt wie `blueprint.json`,
aber lesbar und mit Diagramm.

**Was ihr ignorieren könnt:** `compliance-audit.json`. Das ist Audit-Material für die
Datenschutzbetrachtung. Es liegt hier, damit die Lieferung vollständig nachvollziehbar ist,
für eure Codegen-Pipeline ist es ohne Belang.

## Wie eine Lieferung ankommt

BC3 liefert **nicht** durch einen Commit auf `main`, sondern als Pull Request:

1. Der BC3-Slicer erzeugt die fünf Dateien.
2. An **Gate 2** gibt ein Mensch frei. Ohne Freigabe verlässt nichts den Vorschau-Bereich.
3. Die Freigabe legt den Zweig `lieferung/<lieferung_id>` an, committet die Dateien nach
   `contracts/bc3-to-bc4/<projekt>/<lieferung_id>/` und öffnet einen Pull Request.
4. BC3 führt den Pull Request selbst zusammen. Ihr holt die Lieferung aus `main`.

Freigeben heißt bei uns: ein Mensch hat an Gate 2 entschieden. Eine zweite Abnahme durch
BC4 vor dem Zusammenführen gibt es nicht. Passt etwas nicht, meldet euch bei BC3.

Im Text des Pull Requests stehen Kernprozess, Umfang, Herkunft der Zahlen, wer an Gate 2
freigegeben hat und alle Befunde aus dem Lauf.

## Wie `ticket_set.json` aufgebaut ist

Maximal reduziert, nur was ihr zum Bauen braucht.

**Eine Lieferung:**

- Identität: `lieferung_id`, `schema_version`, `projekt_kurzname`
- Bezug zur BC2-Quelle: `konzept_ref` mit `kp_id` (Pflicht), `teilprozess_ids`,
  `source_file` und `value_quelle`
- `epics[]`: je BC2-Potenzial ein Epic
- `gate2`: Status der menschlichen Freigabe

**Je Epic:** `epic_id` (`ep-…`), `titel`, `ziel`, `kategorien[]` für euer Worker-Routing,
`stories[]`, optional `teilprozess_ids[]`.

**Je Story:** `story_id` (`st-…-<n>`), `titel`, `beschreibung`, `akzeptanzkriterien[]` mit
Messverfahren, `abhaengigkeiten[]`.

### `value_quelle`, bitte beachten

Steht dort `annahme`, beruhen die Zahlen im zugrunde liegenden Konzept auf Annahmen und
nicht auf einer Erhebung. Die Lieferung ist dann als Formatvorlage brauchbar, nicht als
Grundlage für eine Wirtschaftlichkeitsaussage.

### `kp_id`, die Kernprozesskennung

Seit dem 24.08.2026 verbindlich. Die Kennung aus der BC0-Baseline läuft durch alle
Artefakte mit, sonst lässt sich eine Lieferung später nicht mehr ihrem Prozess zuordnen und
landet nicht in der Datenbank.

## Prüfen

```bash
python -m pip install jsonschema
python -c "import json,jsonschema,sys; \
  s=json.load(open('contracts/bc3-to-bc4/tickets.schema.json')); \
  d=json.load(open(sys.argv[1])); jsonschema.Draft202012Validator(s).validate(d); \
  print('gültig')" contracts/bc3-to-bc4/<projekt>/<lieferung_id>/ticket_set.json
```

Bei jedem Pull Request auf `contracts/**` läuft dieselbe Prüfung automatisch, siehe
`.github/workflows/vertraege-pruefen.yml`. Ihr seht also grün oder rot, bevor ihr lest.

## Was sich am 19.11.2026 geändert hat (v3.7)

| Vorher | Jetzt | Warum |
|---|---|---|
| Kriterium nur mit `text` und `messverfahren` | bei Kriterien von BC2 zusätzlich `bc2_kriterium_id`, z. B. `bc2:b7e0b991/969094be/1` | Soll-Ist-Vergleich: BC4 kann einen Messwert so einem Kriterium von BC2 zuordnen, ohne Textvergleich (Übergabe-Befund BC0, 19.11.2026) |

Die Kennung folgt der Konvention von BC0: `bc2:<Priorisierung>/<Potenzial>/<Nr.>`, je die ersten 8 Zeichen der UUID, Nr. = Reihenfolge in `akzeptanzkriterien_geschaeftlich` des Potenzials. BC2 vergibt selbst keine ID. Das Feld ist optional, eigene Kriterien von BC3 haben keins. `schema_version` darf `3.5`, `3.6` oder `3.7` sein, ältere Lieferungen bleiben gültig. Für eure Pipeline ändert sich nichts, `text` und `messverfahren` bleiben wie bisher.

## Was sich am 18.11.2026 geändert hat (v3.6)

| Vorher | Jetzt | Warum |
|---|---|---|
| nur `konzept_id` und `kp_id` in `konzept_ref` | dazu `company_id`, `paket_id`, `priorisierung_id` und, wenn BC2 sie liefert, `anfrage_id` | Soll-Ist-Vergleich: Ohne diese IDs lässt sich kein Ergebnis von BC4 der Vorgabe von BC2 zuordnen (Befund BC0, 17.11.2026) |
| Potenzial nur im Compliance-Audit | `potenzial_id` je Epic in `ticket_set.json` | ein Potenzial von BC2 ergibt ein Epic, BC4 kann so jedes Ergebnis zurückführen |
| `value_quelle` ohne `keine` | `keine` erlaubt | wie im Vertrag BC2 → BC3; die Lieferung `kp-01` vom 16.11. war deshalb rot |

Alle neuen Felder sind optional. `schema_version` darf `3.5` oder `3.6` sein, ältere Lieferungen bleiben gültig.

## Was sich am 03.09.2026 geändert hat

| Vorher | Jetzt | Warum |
|---|---|---|
| `tickets.json` | `ticket_set.json` | seit Juli angekündigt, nie umgesetzt |
| gab es nicht | `blueprint.json` | BC4 braucht den Bauplan als JSON, nicht als Markdown |
| Schema v3.4 | **v3.5** | `kp_id` hatte in v3.4 keinen Platz, `additionalProperties` steht überall auf `false` |
| Ablage im Google Drive | Pull Request in dieses Repo | eine Adresse, Versionsgeschichte in git, Freigabe über CODEOWNERS |

Der Google-Drive-Ordner `Output BC3` wird noch zwei Läufe lang parallel beschrieben, damit
nichts abreißt. Danach gilt nur noch dieser Ordner.

## Compliance: wo das herkommt

Die Compliance-Vorprüfung passiert in unserer Pipeline **vor** der Story-Erzeugung. Das
Ergebnis liegt in `compliance-audit.json`. Steht dort eine Pflicht, etwa „menschlicher
Prüfschritt bei Konfidenz unter 0,8", wird daraus eine eigene Story im `ticket_set.json`.
Ihr seht sie wie jede andere und müsst nicht prüfen, woher sie kommt.

Bei Hochrisiko-KI nach Anhang III der EU-KI-Verordnung hält unsere Kette vor der Lieferung
an, bis ein Mensch an Gate 2 freigibt. Was bei euch ankommt, ist also immer schon
gegengezeichnet.

*Weiterhin offen: einige Compliance-Aufgaben, nämlich PII-Filter, Audit-Log und Löschungs-Cron,
gehören vermutlich vor BC3, also in BC1 oder ins Plattform-Team. Das ist seit Juni nicht
entschieden.*

## Sergios Vorgabe vom 16.05.: was wir einhalten, was wir abweichen

Im Projektplan, Abschnitt 3.2 BC3 → BC4, stand:

> *Ticket-Set: `ticket_id`, `typ` (epic/story/task), `titel`, `beschreibung`,
> `akzeptanzkriterien[]`, `api_spec_ref`, `security_requirements[]`, `aufwand_schaetzung`,
> `abhaengigkeiten[]`.*
> *Tickets per GitLab-API als Issues + `ticket_set.json`. Blueprint: Mermaid-C4 +
> JSON-Komponentenliste. API-Specs als OpenAPI 3.0 YAML. Freigabe nach Gate 2
> (Security-by-Design-Check + Technical Approval).*

**Wir halten ein:**

- schema-validiertes JSON-Ticket-Set
- Akzeptanzkriterien je Story, um das Messverfahren ergänzt
- Abhängigkeiten als ID-Verweise
- Blueprint als Mermaid in `architecture.md`, seit v3.5 zusätzlich als `blueprint.json`
- API-Spezifikation als OpenAPI 3.0: seit 22.10.2026 abgeschaltet, BC4 baut n8n-Workflows und liest sie nicht
- Gate 2 als `gate2.status` im Ticket-Set

**Wir weichen ab:**

- **`typ` und `aufwand_schaetzung` raus.** BC4 braucht beides nicht zum Bauen, das sind
  Projektmanagement-Felder, kein Eingang für die Codegenerierung
- **statt einem `ticket_id`** trennen wir in `epic_id` und `story_id`, damit die Hierarchie
  sichtbar ist
- **`security_requirements[]` raus.** Sicherheitsanforderungen stehen als Pflichten in
  `compliance-audit.json` und werden bei Bedarf zu eigenen Stories
- **GitLab-API raus.** Das Projekt ist seit ADR-0001 auf GitHub. Tickets als Issues sind
  vorbereitet (BC3-90), stehen aber auf Trockenlauf; die Lieferform bleibt die Datei

## Fragen

Format-Konflikt oder Schema-Wunsch: Issue mit Label `contract`. Konkrete Fragen zu einer
Lieferung: direkt in deren Pull Request.

---

*Stand 03.09.2026 · Sabrina und Svetlana · erste Fassung 12.06.2026*
