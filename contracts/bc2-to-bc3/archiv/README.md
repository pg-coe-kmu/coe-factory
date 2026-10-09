# Archiv — abgelöste Vertragsfassungen

Hier liegen die Schemas, gegen die **bereits übergebene** Lieferungen geschnitten wurden.
Sie werden nicht mehr gepflegt und nicht mehr weiterentwickelt — sie sind nur noch da, damit
eine Lieferung prüfbar bleibt, die zu ihrer Zeit gültig war.

| Datei | Gültig für | Abgelöst |
|---|---|---|
| `konzept.schema-v2.0.json` | `lieferungen/2026-08-30-vorlaeufig/konzept_KP-0*.json` | v3.0, 20.09.2026 ([#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)) |
| `priorisierung.schema-v2.0.json` | `lieferungen/2026-08-30-vorlaeufig/prozesspriorisierung.json` | v3.0, 20.09.2026 ([#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)) |

**Warum die alte Lieferung nicht nachgezogen wurde.** [ADR-007 · BC2](../../../bc2-strategic-advisor/docs/adr/ADR-007_Rueckrichtung_BC2_zu_BC3.md)
§ 2.3/2.4: ein übergebenes Konzept wird nie ungültig, es **veraltet**. Nicht neu rechnen — das
zerstört, worauf eine übergebene Lieferung sich beruft; nicht nur markieren — ein Potenzial kann bei
anderen Zahlen anders *geschnitten* sein. Eine Neuberechnung entsteht als **neue Fassung** aus einem
neuen Ruf von BC0, nicht durch Überschreiben der alten.

Die Übergangslieferung vom 30.08.2026 trägt zudem durchgehend frei gesetzte Zahlen
(`value_quelle: "default"`, Marker `[VORLAEUFIG]`). Sie auf v3.0 zu heben hieße, Pflichtfelder zu
füllen, die niemand erhoben hat — genau die Scheingenauigkeit, gegen die v3.0 die Bandbreiten
eingeführt hat.

`validate.py` prüft die Lieferung weiterhin, nur gegen diese Dateien statt gegen die aktuellen.
