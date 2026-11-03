# Lieferung an BC3 — noroai-cc7f4d1b-4c71-4cfa-92c3-46a395080e4b-f1

> Maschinell erzeugt von `bc2-strategic-advisor/tools/lieferung_ziehen.py` aus Schema
> `bc2` (ADR-007 · BC2, Nachtrag #305). Nicht von Hand ändern: der nächste Zug bricht
> dann ab, weil eine Lieferung sich nach der Übergabe nicht mehr ändert.

| | |
|---|---|
| Mandant | NoroAI Consulting GmbH (`7c2d5ee9-2a9a-5990-810f-502ea2b2012d`) |
| Paket | `cc7f4d1b-4c71-4cfa-92c3-46a395080e4b`, übergeben am 2026-11-03T18:29:47.606554+00:00 |
| Fassung | f1 |
| Gate 1 | freigegeben am 2026-11-03T18:40:21.339204+00:00 durch Sergio |
| Vertrag | 3.1 |

## Konzepte in finaler Reihenfolge

1. **KP-06 — Personal** · `konzept_KP-06.json`
   - Reiseanfrage-Extraktion aus E-Mail in strukturierten Erfassungsbogen · PRIO 2 · Score 30
   - Medienbruch-Integration zwischen Angebotsliste, Anbieterportalen und Vorgangsliste · PRIO 2 · Score 25

## Hinweise

- BC1s Profile sind LIVE gelesen, nicht auf stand_zum(uebergeben_am): Schema bc1 liegt ausserhalb von BC0s Historisierung. Es gilt die juengste profil_version mit status='fertig'.
- Schnitt und Bewertung sind Modellurteile: ein Neulauf desselben Pakets schneidet und bewertet neu, nicht zwingend gleich. Die Bewertung ist der Median aus drei Urteilen (#299).
