# Nachricht an BC3 — zum Versenden

> Entwurf für [#168](https://github.com/pg-coe-kmu/coe-factory/issues/168). Eine Nachricht, nicht
> drei: sie trägt die Lieferung **und** die drei seit dem 20.08. offenen Punkte. Vor dem Versenden
> die Repo-URL prüfen (Branch bzw. `main`).

---

Hallo zusammen,

hier ist der fiktive ROI, um den ihr gebeten hattet — mit einer wichtigen Änderung gegenüber dem,
was ihr vermutlich erwartet habt, und drei Dingen, die ich euch noch schulde.

## 1 · Die Lieferung

```
contracts/bc2-to-bc3/lieferungen/2026-08-30-vorlaeufig/
├── konzept_KP-02.json          Vertrieb & Lead-Management
├── konzept_KP-03.json          Kunden-Onboarding
├── konzept_KP-04.json          Engagement-Steuerung
├── prozesspriorisierung.json   Ranking über alle drei
└── README.md                   ← bitte zuerst lesen
```

Schema-konform gegen `konzept.schema.json` / `priorisierung.schema.json` v2.0,
`validate.py` läuft grün. Ihr könnt also direkt dagegen entwickeln.

**Die Änderung:** Ich hätte euch den fertigen Mock schicken können — der beschreibt aber
„Krankentagegeld-Anträge bei der Aurelia Krankenkasse", und das ist **frei erfunden**. Ihr hättet
Tickets für einen Prozess geschnitten, den es bei NoroAI nicht gibt, und die wären beim ersten
Abgleich weggeflogen.

Stattdessen kommen die Prozessdaten aus der echten NoroAI-Baseline: **KP-02, KP-03, KP-04** mit
ihren echten Teilprozessen, Tools, Medienbrüchen und Reifegraden. Die drei sind aus BC0-Sicht die
sauber erhobenen. Das hat einen halben Tag mehr gekostet und ist es wert — **eure Tickets
beschreiben damit existierende Arbeit.**

## 2 · Was daran echt ist und was nicht — bitte einmal genau lesen

| Echt (aus BC0s Baseline-Snapshot v3) | Gesetzt (nirgends erhoben) |
| --- | --- |
| Prozesse, Teilprozesse, Notation, Trigger | Fallzahlen pro Jahr |
| Tools, Medienbrüche, Schnittstellen | Bearbeitungszeit pro Fall |
| Reifegrad je Teilprozess | Einsparungsgrad, Umsetzungsaufwand |
| Stundensatz 68 €/h — in der DB aber selbst als „geschätzt" geführt | **alle Euro-Beträge und Amortisationszeiten** |

Der Grund: Value = Frequenz × Aufwand × Kostensatz. Die gemeinsame Datenbank führt den
**Kostensatz**, aber weder **Fallzahlen** noch **Bearbeitungszeiten**. Die beiden fehlenden Faktoren
muss ich annehmen — daran hätte auch der Mock nichts geändert.

**Konsequenz für euch:** Die Prozess- und Potenzialbeschreibungen tragen. Die **Reihenfolge** kann
sich noch drehen, wenn die echten Zahlen kommen. Wenn ihr Tickets nach Priorität staffelt, plant
bitte damit, dass sich die Rangfolge zwischen KP-03 und KP-04 noch ändert.

**Woran ihr es im Artefakt erkennt** — die Markierung soll den Weg in eure Tickets und in BC4s Code
mitgehen:

- `[VORLAEUFIG]` als Präfix in **jedem Titel** — bitte beim Übernehmen stehen lassen
- Warnblock am Anfang **jeder `beschreibung`**
- `value.value_quelle = "default"` statt `"berechnet"`
- `value.annahmen[0]` = Warntext, danach jede einzelne Annahme
- `gate1.kommentar` = ausdrückliche Freigabesperre
- alle UUIDs beginnen mit **acht Nullen**

Bitte nichts davon für Angebote, Entscheidungen oder eine Gate-1-Freigabe verwenden.

**Ein Befund, der sich mit echten Zahlen nicht umdreht:** NoroAI hat 10 Mitarbeitende, die Volumina
sind entsprechend klein. Die AVV-/DSGVO-Automatisierung (KP-03) landet bei ~53 Monaten
Amortisation — deren Nutzen liegt in Compliance-Sicherheit, nicht in Zeitersparnis. Deshalb ranke
ich nach **Impact × Komplexität** und nutze Euro nur als Tie-Break.

## 3 · Der Vertrag liegt jetzt im Repo — und dieser Pfad bleibt

```
contracts/bc2-to-bc3/
```

Ihr hattet am 20.08. gebeten, den Pfad nicht wiederholt nachziehen zu müssen. Berechtigt — es gab
drei divergierende Kopien. Das ist aufgeräumt: **eine Quelle, und sie wird nicht mehr verschoben.**

Der Ordner `Lösung/` im Google Drive, aus dem ihr bisher gelesen habt, ist damit überholt. Ich
räume ihn noch auf; falls dort kurzzeitig noch der alte Stand liegt: **maßgeblich ist das Repo.**

## 4 · Eure Frage vom 20.08. — ich schulde euch die Antwort

Ihr hattet gefragt, ob `Lösung/` der gültige Stand sei. Der Chat ist danach auf Termine gewechselt
und die Frage blieb liegen. Sorry.

Die Antwort: **inhaltlich ja, aber der Ort hat sich geändert.** Was ihr dort gelesen habt, war der
richtige Vertrag (v2.0) — er liegt jetzt unter `contracts/bc2-to-bc3/`.

## 5 · Die Akzeptanzkriterien kommen zurück

Ihr hattet moniert, dass sie fehlen — zu Recht. Beim Sprung v1 → v2 sind drei Felder verloren
gegangen, die ihr ausdrücklich braucht:

- `akzeptanzkriterien_geschaeftlich`
- `fachliche_anforderungen`
- das ausführliche `to_be_vision` (heute nur noch `to_be_kurz`, 1–2 Sätze)

Das ist ein Fehler auf meiner Seite, kein bewusster Schnitt. Die Felder kommen zurück; wie genau,
entscheide ich in [#160](https://github.com/pg-coe-kmu/coe-factory/issues/160) — **und dabei hätte
ich gern euren Input**, weil ihr die Konsumenten seid.

**Diese Lieferung trägt sie noch nicht.** Die `beschreibung` je Potenzial ist bewusst ausführlich
(Datenflüsse, Akteure, Vorbedingungen, Sonderfälle), damit ihr User Stories ableiten könnt —
aber formale Akzeptanzkriterien müsst ihr vorerst selbst formulieren. Bitte baut nicht darauf,
dass sie schon da wären.

## Kurz gefasst

- ✅ Ihr seid entblockt — schema-konforme Lieferung gegen **echte** NoroAI-Prozesse
- ⚠️ Die Euro-Beträge sind gesetzt, nicht erhoben — Reihenfolge kann sich noch drehen
- 📍 `contracts/bc2-to-bc3/` ist die Endlage, Drive ist überholt
- 🔜 Akzeptanzkriterien folgen über #160 — Input willkommen

Meldet euch, wenn beim Ticketschneiden etwas fehlt oder nicht passt. Lieber jetzt als nach zwanzig
Tickets.

Viele Grüße
Sergio
