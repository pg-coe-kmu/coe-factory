# Contract BC2 → BC3 · Automatisierungskonzept

**Owner:** BC2 (Sergio) · **Consumer:** BC3 · Änderungen brauchen Review beider Seiten.

| Datei | Liefergegenstand | Version |
|---|---|---|
| `konzept.schema.json` | L2-01 Automatisierungskonzept | **2.0** |
| `priorisierung.schema.json` | L2-02 Prozesspriorisierung | **2.0** |

Beispieldaten liegen in [`../examples/`](../examples/):
`mock_automatisierungskonzept.json`, `mock_prozesspriorisierung.json`,
`mock_roi_report.md` und das Eingangsprofil `mock_prozessprofil.json`.

## Lieferungen

Echte Lieferungen an BC3 liegen unter [`lieferungen/`](lieferungen/) — getrennt von den
Mocks, die reine Schema-Fixtures sind.

| Lieferung | Stand | Art |
| --- | --- | --- |
| [`2026-08-30-vorlaeufig/`](lieferungen/2026-08-30-vorlaeufig/) | 30.08.2026 | ⚠️ **vorläufig** — echte Prozesse (KP-02/03/04), gesetzte Value-Zahlen |

Die vorläufige Lieferung entblockt BC3 und BC4, solange das Value-Modell
([#166](https://github.com/pg-coe-kmu/coe-factory/issues/166)) und die Akzeptanzkriterien
([#160](https://github.com/pg-coe-kmu/coe-factory/issues/160)) offen sind. Erzeugt für
[#168](https://github.com/pg-coe-kmu/coe-factory/issues/168); **nicht Gate-1-freigabefähig.**
Details und die Trennung „echt vs. gesetzt" stehen in ihrer
[README](lieferungen/2026-08-30-vorlaeufig/README.md).

## Dieser Pfad ist die Endlage

Die Dateien lagen bis zum 30.08.2026 außerhalb des Repos unter `Projektgruppe/BC2/Lösung/`
und davor in zwei weiteren, divergierenden Kopien. Sie liegen jetzt hier und werden **nicht
noch einmal verschoben** — BC3 hatte am 20.08. darum gebeten, den Pfad nicht wiederholt
nachziehen zu müssen. Aufgeräumt in
[#162](https://github.com/pg-coe-kmu/coe-factory/issues/162).

## Was sich von v1.0 auf v2.0 geändert hat

v1 ordnete **vorgegebene Automatisierungsmuster** zu (`use_cases[]` mit `empfohlenes_muster`
als Enum, gestützt auf einen Qdrant-Musterkatalog). Das ist verworfen. v2 **erkennt Potenziale
offen** aus dem Prozess und **berechnet** deren Value: `potenziale[]`, dazu neu je Potenzial
`impact`, `umsetzungskomplexitaet`, `value{}`, `kategorie` und `potenzielle_loesung`
(frei formuliert statt Enum).

Umbenennungen, die BC3 betreffen — von BC3 am 20.08. abgenommen („Die ID können wir ändern"):

| v1.0 | v2.0 |
|---|---|
| `use_cases[]` | `potenziale[]` |
| `use_case_id` | `potenzial_id` |
| `gesamtempfehlung.reihenfolge_use_case_ids` | `…reihenfolge_potenzial_ids` |
| `gate1.approved_use_case_ids` | `gate1.approved_potenzial_ids` |
| `roi{}` | `value{}` (zusätzlich `investition_eur_richtwert`, `annahmen[]`) |
| `ersparnis_eur_jahr` | `einsparung_eur_jahr` |

`prozessprofil_ref` ist bewusst `string` statt `format: uuid`, damit derselbe Vertrag für
Datei-, REST- und DB-Herkunft gilt.

## Offener Punkt: Akzeptanzkriterien fehlen

v1 trug je Use Case `akzeptanzkriterien_geschaeftlich`, `fachliche_anforderungen` und ein
ausführliches `to_be_vision`. **v2 hat diese drei nicht mehr** — geblieben ist nur
`potenzielle_loesung.to_be_kurz` („1–2 Sätze"). BC3 hat am 20.08. widersprochen:

> „es fehlen Felder wie Akzeptanzkriterien, das bräuchten wir auf jeden Fall"

Die Felder kommen zurück; wie genau, entscheidet
[#160 — Was BC3 von BC2 erwartet](https://github.com/pg-coe-kmu/coe-factory/issues/160).
Bis dahin ist v2.0 als Ausgangspunkt gültig, aber nicht endgültig.

## Prüfen

```bash
python3 -m pip install jsonschema
python3 bc2-strategic-advisor/tools/validate.py   # aus dem Repo-Wurzelverzeichnis
```

Prüft beide Mocks gegen ihre Schemas und zusätzlich, dass
`gesamtempfehlung.reihenfolge_potenzial_ids` mit dem Ranking der Priorisierung übereinstimmt
und keine unbekannten Potenziale referenziert werden. Exit 0 = grün.

`bc2-strategic-advisor/tools/gen_mocks.py` erzeugt die Mocks neu; die Value-/ROI-Rechnung darin
ist deterministisch (kein LLM) und dient als Referenzimplementierung.

> **Fachlicher Vorbehalt zu den Mocks:** `mock_prozessprofil.json` beschreibt
> „Antragsbearbeitung Krankentagegeld, KP-07, Aurelia Krankenkasse". Das ist **frei erfunden** —
> real ist KP-07 die Buchhaltung, und der Referenzmandant NoroAI ist eine KI-Beratung. Die Mocks
> sind **Schema-Fixtures**, keine fachliche Vorlage. Fachliche Grundlage ist die gemeinsame
> Datenbank ([#159](https://github.com/pg-coe-kmu/coe-factory/issues/159)).
