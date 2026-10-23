# Simulationen für Tests des BC3-Slicers

Hier liegen simulierte Konzepte, mit denen BC3 den Slicer probt, solange es für einen Use Case noch kein Konzept von BC2 gibt. Sie liegen bewusst nicht unter `contracts/bc2-to-bc3/lieferungen/`: BC3-01 startet sie nie von selbst, nur der Handstart mit Pfad.

| Ordner | Was | erzeugt mit |
|---|---|---|
| `noroai-SIM-UC1-2026-10-22-f1/` | UC1 Reisebuchung (KP-06.TP-2), zwei Potenziale, Konzept v3.1, Priorisierung v3.0 | `gen_sim_uc1.py` |

**Kennzeichnung:** `[SIMULIERT]` im Titel, Warnblock am Anfang der Beschreibung, `value_quelle` = `annahme`, Gate 1 `pending` mit Freigabesperre. Nicht für Entscheidungen, Angebote oder Gate-1-Freigaben verwenden.

**Woher die Inhalte kommen:** Texte aus BC3s Vorlage `bc2-anforderung/beispiel_uc1_reisebuchung.json` (31.08.2026), Zahlen mit BC2s Rechenkern (`bc2-strategic-advisor/app/modell/`, ADR-006), wie bei BC2s UC3-Simulation (`gen_lieferung_sim_uc3.py`, #168). Häufigkeit, Dauer und Stundensatz stehen wörtlich in der Vorlage und werden gegen `ist_kosten_eur_jahr` nachgerechnet.

**Neu erzeugen** (aus dem Repo-Wurzelverzeichnis):

```
python bc3-engineering-architect/simulation/gen_sim_uc1.py
```

Beide Dateien sind gegen `contracts/bc2-to-bc3/konzept.schema.json` und `priorisierung.schema.json` gültig (geprüft 22.10.2026).
