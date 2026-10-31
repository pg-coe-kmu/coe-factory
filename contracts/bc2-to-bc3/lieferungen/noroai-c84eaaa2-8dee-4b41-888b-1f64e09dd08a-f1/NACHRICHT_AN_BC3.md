# Lieferung an BC3 — noroai-c84eaaa2-8dee-4b41-888b-1f64e09dd08a-f1

> Maschinell erzeugt von `bc2-strategic-advisor/tools/lieferung_ziehen.py` aus Schema
> `bc2` (ADR-007 · BC2, Nachtrag #305). Nicht von Hand ändern: der nächste Zug bricht
> dann ab, weil eine Lieferung sich nach der Übergabe nicht mehr ändert.

| | |
|---|---|
| Mandant | NoroAI Consulting GmbH (`7c2d5ee9-2a9a-5990-810f-502ea2b2012d`) |
| Paket | `c84eaaa2-8dee-4b41-888b-1f64e09dd08a`, übergeben am 2026-10-31T08:20:32.104750+00:00 |
| Fassung | f1 |
| Gate 1 | freigegeben am 2026-10-31T08:49:10.300974+00:00 |
| Vertrag | 3.1 |

## Konzepte in finaler Reihenfolge

1. **KP-06 — Personal** · `konzept_KP-06.json`
   - Reisestornierung automatisiert ausführen und bestätigen · PRIO 2 · Score 20

## Hinweise

- BC1s Profile sind LIVE gelesen, nicht auf stand_zum(uebergeben_am): Schema bc1 liegt ausserhalb von BC0s Historisierung. Es gilt die juengste profil_version mit status='fertig'.
- Schnitt und Bewertung sind Modellurteile: ein Neulauf desselben Pakets schneidet und bewertet neu, nicht zwingend gleich. Die Bewertung ist der Median aus drei Urteilen (#299).
