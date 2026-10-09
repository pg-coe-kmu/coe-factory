# Contract BC2 → BC3 · Automatisierungskonzept

**Owner:** BC2 (Sergio) · **Consumer:** BC3 · Änderungen brauchen Review beider Seiten.

| Datei | Liefergegenstand | Version |
|---|---|---|
| `konzept.schema.json` | L2-01 Automatisierungskonzept, je **Kernprozess** | **3.1** (nimmt 3.0 weiter an) |
| `priorisierung.schema.json` | L2-02 Priorisierung, je **Analyselauf** | **3.1** (nimmt 3.0 weiter an) |
| [`archiv/`](archiv/) | eingefrorene v2.0-Fassung für die Lieferung vom 30.08.2026 | 2.0 |

Fixtures liegen in [`../examples/`](../examples/): `mock_automatisierungskonzept.json` (KP-06),
`mock_automatisierungskonzept_KP-05.json`, `mock_prozesspriorisierung.json` und der
menschenlesbare `mock_roi_report.md`. Sie tragen seit v3.0 **echten NoroAI-Inhalt** aus BC3s
Formatvorlage vom 31.08.2026 statt des früheren erfundenen Krankentagegeld-Falls; der alte Stand
liegt in [`../examples/archiv-v2/`](../examples/archiv-v2/).

## Die Übergabeeinheit ist der Lauf, nicht das Konzept

Ein **Analyselauf** ist `(company_id, paket_id)` — das Paket, das BC0 nach der Gate-0-Freigabe
schnürt (ADR-005 · BC2). Übergeben wird er als Ganzes: **eine Priorisierung und ihre *n* Konzepte,
ein Ereignis.** Ein einzeln freigegebenes Konzept hätte keine Reihenfolge, und BC3 bekäme Epics
ohne den Rang, der sie sortiert.

Daraus folgt der Zuschnitt: **ein Konzept deckt genau einen Kernprozess ab**, gelesen und bewertet
wird auf Teilprozess-Ebene. Der Kernprozess ist das Präfix der Teilprozess-ID, keine eigene
Erhebung.

## Lieferungen

Echte Lieferungen liegen unter [`lieferungen/`](lieferungen/), getrennt von den Fixtures.
Künftige Lieferungen heißen `<company>-<paket_id>-f<n>/` und kommen **per Pull Request**, nicht
direkt auf `main` — das Datum trägt keine Identität (zwei Läufe am selben Tag sind möglich), die
`paket_id` schon. Details: [ADR-007 · BC2](../../bc2-strategic-advisor/docs/adr/ADR-007_Rueckrichtung_BC2_zu_BC3.md).

| Lieferung | Stand | Vertrag | Art |
| --- | --- | --- | --- |
| [`2026-08-30-vorlaeufig/`](lieferungen/2026-08-30-vorlaeufig/) | 30.08.2026 | **v2.0** (eingefroren) | ⚠️ **vorläufig** — echte Prozesse (KP-02/03/04), gesetzte Value-Zahlen |
| [`noroai-SIM-UC3-2026-09-21-f1/`](lieferungen/noroai-SIM-UC3-2026-09-21-f1/) | 21.09.2026 | v3.0 | ⚠️ **simuliert** — Rückfallebene zum Durchstich in KW 40 ([#206](https://github.com/pg-coe-kmu/coe-factory/issues/206)), Zuschnitt UC3 |

Die simulierte Lieferung ist die **erste im Ordnerschnitt nach ADR-007** und die erste, die mit
`app/modell/` gerechnet wurde — also eine Probe des Weges, den der echte Lauf gehen soll. Ihre
Zahlen sind gesetzt (`value_quelle: "annahme"`), und das steht in Titel, Beschreibung, Paket-ID
und Ordnernamen.

Die alte Lieferung wird **nicht** auf v3.0 nachgezogen: ein übergebenes Konzept wird nie ungültig,
es veraltet. Neu rechnen zerstört, worauf eine übergebene Lieferung sich beruft; nur markieren
reicht nicht, weil ein Potenzial bei anderen Zahlen anders *geschnitten* sein kann. Eine
Neuberechnung entsteht als **neue Fassung**. Siehe [`archiv/README.md`](archiv/README.md).

## Dieser Pfad ist die Endlage

Die Dateien lagen bis zum 30.08.2026 außerhalb des Repos und davor in zwei weiteren,
divergierenden Kopien. Sie liegen jetzt hier und werden **nicht noch einmal verschoben** — BC3
hatte am 20.08. darum gebeten. Aufgeräumt in
[#162](https://github.com/pg-coe-kmu/coe-factory/issues/162).

## Was sich von v3.0 auf v3.1 geändert hat

**Additiv, drei Felder in zwei Schemas**: die Ausgangslage
([#254](https://github.com/pg-coe-kmu/coe-factory/issues/254), entschieden in
[#244](https://github.com/pg-coe-kmu/coe-factory/issues/244)) und die Kette über Pakete hinweg
([#291](https://github.com/pg-coe-kmu/coe-factory/issues/291), [ADR-009 · BC2](../../bc2-strategic-advisor/docs/adr/ADR-009_Nachfolger_ueber_Pakete.md),
auf BC3s eigenen Vorschlag an [#242](https://github.com/pg-coe-kmu/coe-factory/issues/242)).
⚠️ **Von BC3 noch nicht bestätigt.**

| Was | v3.0 | v3.1 | Warum |
|---|---|---|---|
| `ausgangslage` in der Priorisierung | — | `unternehmen{name, branche, mitarbeitende, region, geschaeftsmodell}`, `herausforderungen[]{beschreibung, auswirkung, haeufigkeit?, kp_ids[]}`, `kernaussage?` | Teil 1 der Präsentation hatte im Vertrag keinen Ort. Erzeugte der Foliengenerator sie selbst, trüge die Präsentation eigene Information — unversioniert und nie bei BC3 |
| `potenziale[].ersetzt_potenzial_ids` im Konzept | — | Liste aus UUIDs, höchstens **ein** Eintrag, `[]` bei einem neuen Potenzial | Der Vorgänger aus einer früher **gelieferten** Lieferung eines **anderen** Pakets. Ohne ihn sind nach einer Nacherhebung alle Kennungen neu, und BC4 legt neue Tickets an, statt fortzuschreiben |
| `gestrichene_potenziale[]` in der Priorisierung | — | `{potenzial_id, kp_id, begruendung}`, `[]` wenn nichts gestrichen ist | Was dieser Lauf neu gesehen hat und als Vorhaben wegfällt — ausdrücklich, weil BC3 sonst nicht unterscheiden kann zwischen „gestrichen“ und „gar nicht neu gerechnet“ |
| `schema_version` | `const "3.0"` | `"3.0"` oder `"3.1"`, **in beiden Schemas** | Eine 3.0-Datei bleibt gültig; eine 3.1 **trägt** die neuen Felder, eine 3.0 **trägt sie nicht** — die Nummer sagt, ob sie da sind. In einem Lauf tragen alle Dateien dieselbe Nummer |

- **`unternehmen` ist maschinell**, kein LLM: aus `public.companies` und `public.company_profile`
  auf `stand_zum(uebergeben_am)`. Alle fünf Schlüssel sind Pflicht, jeder Wert darf `null` sein —
  eine fehlende Angabe ist `null`, nie `0` und nie `""`.
- **`herausforderungen` erfinden nichts:** es sind die `kontext.hauptschmerzpunkte` aller Konzepte,
  wörtlich gleiche zusammengeführt (mit allen ihren `kp_ids`), ähnliche getrennt gelassen.
  `validate.py` prüft, dass beide Mengen übereinstimmen.
- **`kernaussage` ist optional** — sie entsteht beim Paketaufruf des Erkennungsschritts
  ([#248](https://github.com/pg-coe-kmu/coe-factory/issues/248)), und die Präsentation soll ohne sie
  erzeugt werden können.
- **Nicht übernommen:** Positionierung, Marktumfeld und strategische Ziele aus dem
  Unternehmensprofil v6.0. Fließtext ohne Datengrundlage im Paket; ihn zu verdichten hieße, im Lauf
  Aussagen zu erzeugen, die niemand prüfen kann.
- **Die Kette lebt nur auf Potenzialebene.** Ein neues Paket trägt nur die **neu freigegebenen**
  Teilprozesse (BC0s `v_uebergabe_kandidaten`), ein Konzept über KP-05.TP-2 ersetzt also kein
  Konzept über TP-1 bis TP-3. `ersetzt_konzept_id` verkettet weiter nur Fassungen **desselben**
  Pakets. Ein Vorgänger kommt nur aus einer **freigegebenen** Lieferung (abgelehnte Fassungen hat BC3
  nie gesehen) und nur, wenn er einen Teilprozess des neuen Pakets berührt.
- **Nur 1:1.** Ein Vorgänger hat höchstens einen Nachfolger. Bei einer Teilung rechnete BC3 zwei
  Potenziale auf dieselbe älteste Kennung. Was sich teilt oder zusammenlegt, ist neu, und das Alte
  steht auf der Streichliste.
- **Worauf keiner zeigt und was nicht auf der Streichliste steht, gilt unverändert** — es lag
  außerhalb des Pakets oder war aus ihm allein nicht zu beurteilen.
- **Bis der Bau steht ([#295](https://github.com/pg-coe-kmu/coe-factory/issues/295)), sind beide
  Felder leer** — zu Recht, denn einen freigegebenen echten Lauf gibt es noch nicht. Kommt ein
  Teilprozess zum zweiten Mal, bevor die Verknüpfung gebaut ist, liefert BC2 nicht still `[]`,
  sondern bricht ab (#290).

**Was BC3 tun muss:** Wer gegen eine eigene Kopie des v3.0-Schemas prüft, lehnt eine v3.1 ab
(`additionalProperties: false`, `const "3.0"`). Die Kopie ist zu ersetzen. Lesecode, der
`ausgangslage` nicht kennt, kann es ignorieren. **Für die Ticketkennungen:** der Kette über
`ersetzt_potenzial_ids` zurück folgen und mit der **ältesten** `potenzial_id` rechnen (Svetlanas
Vorschlag an #242). Was mit einem gestrichenen Potenzial bei BC4 geschieht, entscheidet BC3.

## Was sich von v2.0 auf v3.0 geändert hat

Zehn angesammelte Änderungen, in **einem** Zug geschnitten
([#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)) — jeder brechende Release kostet BC3
eine Anpassung.

### Brechend

| Was | v2.0 | v3.0 | Warum |
|---|---|---|---|
| Herkunft des Laufs | `prozessprofil_ref` (ein String, drei Bedeutungen) | `company_id` + `paket_id` + `uebergeben_am` | Zwei Mandanten liegen in derselben Datenbank, und die Datenbank trennt sie nicht (#164) |
| Skala Impact / Komplexität | vier Stufen `gering`…`sehr hoch` | **1–10** | Von BC3 am 06.09.2026 bestätigt (#186 F1); die vier Stufen in BC3s Vorlage waren Ist-Stand, keine Gegenposition |
| Aufwand heute | Urteils-Enum | `{ stunden_jahr, herkunft }` | Das Glossar führt ihn als **gemessene** Größe aus Dauer und Häufigkeit, kein Urteil — das Enum widersprach dem |
| Gate 1 | im Konzept, je Kernprozess | in der **Priorisierung**, je Lauf | Entschieden wurde an einer Stelle, protokolliert an einer anderen (ADR-007 · BC2) |
| Value-Größen | Punktwerte | **Spannen** (`{min, max}`) | Bandbreite je Herkunft der Dauer (ADR-006 · BC2) |
| Vierte Kategorie | `Long Bet` | `Zurueckgestellt` | Eine Wette verspricht einen Gewinn, den die Zahlen dort gerade nicht zeigen |
| `rang` | Rang **innerhalb** des Konzepts | `potenzialrang`, über den **ganzen Lauf** | Rangiert wird über die Prozesse hinweg — das ist der Kern dessen, was BC2 liefert |

### Neu

**Aus BC3s Vorlage übernommen** (die Form stand fest, sie war abzuschreiben, nicht zu entwerfen):
`akzeptanzkriterien_geschaeftlich` (Given/When/Then), `fachliche_anforderungen`, ausführliches
`to_be_vision`, `betroffene_teilprozess_ids` (Auflage BC0 vom 24.08.), und `value_quelle` um
`annahme` erweitert.

**Aus dem Value-Modell** (ADR-006 · BC2): `nutzwert` (fünf Kategorien mit Begründung),
`impact_monetaer`, `automatisierungsgrad` (Klasse + Korridor), `komplexitaet_herkunft`,
`prioritaetsgruppe`, `querschnitte` (Zukunftssicherheit, Reifegrad, Umsatzpotenzial,
Abhängigkeiten), `eingangswerte` und `hinweise`.

**Aus der Rückrichtung** (ADR-007 · BC2): `ersetzt_konzept_id`, `fassung`, und in `gate1` die
`finale_reihenfolge_potenzial_ids` samt `abweichungsbegruendung` sowie `nicht_freigegeben[]` mit
Begründung je Potenzial.

**Neu als eigenes Ergebnis:** `prozess_raenge[]` in der Priorisierung. Bisher wurde nach
Potenzialen rangiert; gefragt war aber, welcher **Prozess** zuerst automatisiert wird.

### Die beiden Formen nicht verwechseln

- `user_story` → **SOPHIST**: „Als … möchte … damit …"
- `akzeptanzkriterien_geschaeftlich[].kriterium` → **Given/When/Then**: „Gegeben …, wenn …, dann …"
- `akzeptanzkriterien_geschaeftlich[].messverfahren` → **füllt BC2**

Diese Frage ist viermal beantwortet worden (#160 GWT → #186 SOPHIST → Meeting 07.09. GWT →
Rückfrage 09.09. GWT). Die letzte Antwort erfolgte **in Kenntnis der vorherigen** und gilt.

### Was bewusst gleich geblieben ist

`aufwand_schaetzung_pt` und `risiken` **bleiben** — von BC3 am 06.09.2026 ausdrücklich bestätigt
(#186 F3), obwohl `tickets.schema.json` v3.5 für beide kein Zielfeld hat. Die **Risiken bleiben
dreistufig** (`low`/`med`/`high`): eine Matrix 1–10 × 1–10 suggeriert Genauigkeit, die es dort
nicht gibt. Die Skalenänderung betrifft Impact und Komplexität, nicht die Risiken.

## Prüfen

```bash
python3 -m pip install jsonschema
python3 bc2-strategic-advisor/tools/validate.py   # aus dem Repo-Wurzelverzeichnis
```

Prüft die Fixtures gegen v3.1 und die alte Lieferung gegen die archivierten v2-Schemas, dann die
fachliche Konsistenz: dass sich das Rechenmodell aus ADR-006 · BC2 nachrechnen lässt (Nutzwert,
Impact, Score, Kategorie, Prioritätsgruppe), dass Konzepte und Priorisierung eines Laufs sich
nicht widersprechen, dass der Prozessrang dem jeweils besten Potenzial folgt, dass die beiden
Textformen eingehalten sind und dass die Ausgangslage nur zusammenführt, was in den Konzepten steht.
Exit 0 = grün.

`bc2-strategic-advisor/tools/migriere_bc3_vorlage.py` erzeugt die Fixtures neu. Der frühere
`gen_mocks.py` ist nach `bc2-strategic-advisor/tools/archiv/gen_mocks_v2.py` eingefroren.

Gefunden wird **jeder** Ordner unter `lieferungen/`, nicht eine feste Liste: was dort liegt und
nicht die eingefrorene v2-Lieferung ist, läuft gegen das aktuelle Schema (nimmt 3.0 und 3.1) —
Schema, ein Lauf je Ordner, Konzepte und Priorisierung decken dieselben Potenziale, Rangfolge wie
im Rechenkern, Ordnername `<company>-<paket_id>-f<n>`, bei 3.1 die Ausgangslage (genau die
Schmerzpunkte der Konzepte, nichts dazu) und die Kette (`tools/kette.py`: 1:1, Vorgänger und
Gestrichenes aus einer früheren **freigegebenen** Lieferung im Repo, gleicher Kernprozess, gleiche
Lösungsklasse, nichts zugleich fortgeschrieben und gestrichen), und bei `paket_id` `SIM-…` die
Simulations-Kennzeichnung.

**Die CI prüft das bei jedem PR, der die Lieferstrecke berührt** (#253): Job **„BC2 → BC3
Lieferungen"** in `.github/workflows/vertraege-pruefen.yml` startet `validate.py`, sobald sich
etwas unter `contracts/bc2-to-bc3/`, `contracts/bc1-to-bc2/`, `contracts/examples/`, an
`validate.py`, an `kette.py` oder am Workflow selbst ändert. Der Job hat ein eigenes Ergebnis, getrennt von der
BC3→BC4-Prüfung im selben Workflow — ein Rot dort sagt nichts über BC2 und umgekehrt.
