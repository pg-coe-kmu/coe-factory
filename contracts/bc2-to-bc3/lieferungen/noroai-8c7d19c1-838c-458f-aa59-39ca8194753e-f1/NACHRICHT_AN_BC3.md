# Lieferung an BC3 — noroai-8c7d19c1-838c-458f-aa59-39ca8194753e-f1

> Maschinell erzeugt von `bc2-strategic-advisor/tools/lieferung_ziehen.py` aus Schema
> `bc2` (ADR-007 · BC2, Nachtrag #305). Nicht von Hand ändern: der nächste Zug bricht
> dann ab, weil eine Lieferung sich nach der Übergabe nicht mehr ändert.

| | |
|---|---|
| Mandant | NoroAI Consulting GmbH (`7c2d5ee9-2a9a-5990-810f-502ea2b2012d`) |
| Paket | `8c7d19c1-838c-458f-aa59-39ca8194753e`, übergeben am 2026-09-18T08:05:19.912797+00:00 |
| Fassung | f1 |
| Gate 1 | freigegeben am 2026-10-10T10:22:59.916446+00:00 |
| Vertrag | 3.1 |

## Konzepte in finaler Reihenfolge

1. **KP-05 — Wissensmanagement** · `konzept_KP-05.json`
   - KI-gestützte Wissenssuche im Google-Drive-Bestand · PRIO 2 · Score 24
     - schreibt fort: KI-gestützte Wissensdatenbank-Suche statt manueller Google-Drive-Recherche (`85191e37-f91a-4b70-8083-e8c890ef8b29`, Paket 880f95f7-0e1e-4866-a206-24f25e624455)

## Hinweise

- BC1s Profile sind LIVE gelesen, nicht auf stand_zum(uebergeben_am): Schema bc1 liegt ausserhalb von BC0s Historisierung. Es gilt die juengste profil_version mit status='fertig'.
- Schnitt und Bewertung sind Modellurteile: ein Neulauf desselben Pakets schneidet und bewertet neu, nicht zwingend gleich. Die Bewertung ist der Median aus drei Urteilen (#299).
