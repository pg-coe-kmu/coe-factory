# BC3 → BC4: der Liefer-Ordner

An das BC4-Team,

hier liegen die Lieferungen von BC3. Ein Unterordner je Projekt, dazu das JSON-Schema,
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
└── <projekt>/              eine echte Lieferung, ein Ordner je Projekt
    ├── ticket_set.json         die Hauptlieferung: Epics mit Stories
    ├── blueprint.json          Bauplan als JSON: Komponenten, Datenflüsse, Entscheidungspunkte
    ├── architecture.md         derselbe Bauplan als Text, mit Mermaid-Diagramm
    ├── api/openapi.yaml         die Endpunkte, die die Stories voraussetzen
    └── compliance-audit.json   Compliance-Vorprüfung, Audit-Material
```

## Was BC4 braucht, und was nicht

**Für eure Pipeline:** `ticket_set.json`, `blueprint.json`, `api/openapi.yaml`.

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
   `contracts/bc3-to-bc4/<projekt>/` und öffnet einen Pull Request.
4. CODEOWNERS fragt `team-bc3` und `team-bc4` um Freigabe.

**Der Merge ist eure Abnahme.** Solange ihr nicht merged, gilt die Lieferung als nicht
angekommen. Und man sieht das, statt dass irgendwo stillschweigend eine alte Datei
weiterbenutzt wird.

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
  print('gültig')" contracts/bc3-to-bc4/<projekt>/ticket_set.json
```

Bei jedem Pull Request auf `contracts/**` läuft dieselbe Prüfung automatisch, siehe
`.github/workflows/vertraege-pruefen.yml`. Ihr seht also grün oder rot, bevor ihr lest.

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
- API-Spezifikation als OpenAPI 3.0 in `api/openapi.yaml`
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
