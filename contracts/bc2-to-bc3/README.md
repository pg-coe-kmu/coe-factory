# Contract BC2 → BC3 · Automatisierungskonzept

**Owner:** BC2 (Sergio) · **Consumer:** BC3 · Änderungen brauchen Review beider Seiten.

| Datei | Liefergegenstand | Version |
|---|---|---|
| `konzept.schema.json` | L2-01 Automatisierungskonzept, je **Kernprozess** | **3.0** |
| `priorisierung.schema.json` | L2-02 Priorisierung, je **Analyselauf** | **3.0** |
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

Prüft die Fixtures gegen v3.0 und die alte Lieferung gegen die archivierten v2-Schemas, dann die
fachliche Konsistenz: dass sich das Rechenmodell aus ADR-006 · BC2 nachrechnen lässt (Nutzwert,
Impact, Score, Kategorie, Prioritätsgruppe), dass Konzepte und Priorisierung eines Laufs sich
nicht widersprechen, dass der Prozessrang dem jeweils besten Potenzial folgt und dass die beiden
Textformen eingehalten sind. Exit 0 = grün.

`bc2-strategic-advisor/tools/migriere_bc3_vorlage.py` erzeugt die Fixtures neu. Der frühere
`gen_mocks.py` ist nach `bc2-strategic-advisor/tools/archiv/gen_mocks_v2.py` eingefroren.

> **Die CI fasst diesen Ordner nicht an.** `.github/workflows/vertraege-pruefen.yml` läuft bei
> jeder Änderung unter `contracts/**`, prüft aber **ausschließlich** `contracts/bc3-to-bc4`. Ohne
> Erweiterung ist der PR-Weg aus ADR-007 · BC2 ein Verfahren ohne Netz, und eine schema-ungültige
> Lieferung, die BC3 bereits gezogen hat, holt niemand zurück. `validate.py` läuft bis dahin von
> Hand.
