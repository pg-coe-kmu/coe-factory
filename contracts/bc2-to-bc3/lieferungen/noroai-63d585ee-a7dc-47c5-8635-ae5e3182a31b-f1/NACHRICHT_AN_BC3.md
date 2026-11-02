# Lieferung an BC3 — noroai-63d585ee-a7dc-47c5-8635-ae5e3182a31b-f1

> Maschinell erzeugt von `bc2-strategic-advisor/tools/lieferung_ziehen.py` aus Schema
> `bc2` (ADR-007 · BC2, Nachtrag #305). Nicht von Hand ändern: der nächste Zug bricht
> dann ab, weil eine Lieferung sich nach der Übergabe nicht mehr ändert.

| | |
|---|---|
| Mandant | NoroAI Consulting GmbH (`7c2d5ee9-2a9a-5990-810f-502ea2b2012d`) |
| Paket | `63d585ee-a7dc-47c5-8635-ae5e3182a31b`, übergeben am 2026-11-02T17:06:50.510382+00:00 |
| Fassung | f1 |
| Gate 1 | freigegeben am 2026-11-02T17:17:05.067662+00:00 |
| Vertrag | 3.1 |

## Konzepte in finaler Reihenfolge

1. **KP-06 — Personal** · `konzept_KP-06.json`
   - Reiseanfrage-Daten aus E-Mail extrahieren · PRIO 2 · Score 30
   - Buchungsstatus-Abfrage automatisieren · PRIO 2 · Score 20
   - Stornierungsauslösung und Bestätigung automatisieren · PRIO 2 · Score 20
   - Angebotserstellung mit Recherche-Assistent unterstützen · PRIO 3 · Score 16

## Hinweise

- BC1s Profile sind LIVE gelesen, nicht auf stand_zum(uebergeben_am): Schema bc1 liegt ausserhalb von BC0s Historisierung. Es gilt die juengste profil_version mit status='fertig'.
- Schnitt und Bewertung sind Modellurteile: ein Neulauf desselben Pakets schneidet und bewertet neu, nicht zwingend gleich. Die Bewertung ist der Median aus drei Urteilen (#299).
