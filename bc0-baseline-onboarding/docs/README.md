# BC0 — Dokumentation und Entscheidungen

Fachpapiere von BC0, die bisher nur im Projektordner `PG KI-CoE-KMU` lagen. Sie stehen hier,
weil das Repository der verbindliche Ort für das ist, was gilt — Code, Schema, Verträge,
Entscheidungen. Drive bleibt für das, was an Menschen geht, die kein Repository benutzen:
Präsentationen, Briefe, PDF-Fassungen.

## `datenbank/`

| Datei | Inhalt |
|---|---|
| `BC0_Datenbank_Dokumentation_v1.3.md` | Tabellen, Sichten, Rollen und API-Endpunkte zum Schemastand v1.3 |
| `BC0_Datenbank_Dokumentation_Nachtrag_v2.1-v2.9.md` | Fortschreibung über die Schemastände v2.1 bis v2.9 |
| `BC0_DB_Ablaufanalyse_03-09-2026.md` | Ablaufanalyse vom 03.09.2026 |

Die Schemadateien selbst liegen unter [`../app/`](../app/) (`schema_v*.sql`).

## `entscheidungen/`

| Datei | Stand |
|---|---|
| `BC0_ADR-003_SSoT_Schreibmodell.md` | **angenommen 10.08.2026** |
| `BC0_Entscheidung_DB_SSoT.md` | Vorlauf zu ADR-003 |
| `BC0_Entscheidung_Hosting_v1.md` | Hosting-Entscheidung |

**ADR-004** liegt unter [`../app/ADR-004_Entitaeten_Identitaet.md`](../app/ADR-004_Entitaeten_Identitaet.md)
— angenommen 12.08.2026.

**ADR-005 (BC0) — „Ergebnispflicht und Herkunftsnachweis", angenommen am 01.09.2026 — fehlt hier
noch.** Die Nummer 5 ist im Repository auch an
[`bc2-strategic-advisor/docs/adr/ADR-005_Analyselauf_ist_das_Paket.md`](../../bc2-strategic-advisor/docs/adr/ADR-005_Analyselauf_ist_das_Paket.md)
vergeben. Das Register in [`../README.md`](../README.md) weist beide Beschlüsse aus und benennt die
Ursache; die Nummernvergabe selbst entscheidet
[#220](https://github.com/pg-coe-kmu/coe-factory/issues/220). Das Papier kommt hinzu, sobald
feststeht, unter welcher Nummer — ein Einchecken vorher würde die Doppelung im Repository
festschreiben.
