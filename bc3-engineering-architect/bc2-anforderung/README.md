# Beispielkonzepte BC3 — Format für die Übergabe BC2 → BC3

Vier Dateien, die zeigen, in welcher Form BC3 ein Automatisierungskonzept
verarbeiten kann. **Keine BC2-Lieferung und keine Freigabegrundlage.**

Hintergrund und Diskussion: [#160](https://github.com/pg-coe-kmu/coe-factory/issues/160).

## Inhalt

| Datei | Use Case | Kernprozess | Teilprozess |
|---|---|---|---|
| `beispiel_uc1_reisebuchung.json` | UC1 Reise- und Einsatzplanung | KP-06 | KP-06.TP-2 |
| `beispiel_uc2_wissensbasis.json` | UC2 Wissenstransfer (RAG) | KP-05 | KP-05.TP-1 |
| `beispiel_uc3_consultant_placement.json` | UC3 Consultant Placement | KP-06 | KP-06.TP-1 |
| `gegenueberstellung_aurelia_bc3.json` | — | KP-07 | — |

Die vierte Datei ist `contracts/examples/mock_automatisierungskonzept.json` aus
[#170](https://github.com/pg-coe-kmu/coe-factory/pull/170), unverändert bis auf vier
ergänzte Felder. Titel, Zahlen, Reihenfolge und Risiken stammen wörtlich aus dem
Original. Sie zeigt am selben Fall, was BC3 zusätzlich braucht.

## Was gegenüber v2.0 ergänzt ist

| Feld | Anmerkung |
|---|---|
| `fachliche_anforderungen` | war in v1.0 Pflicht |
| `akzeptanzkriterien_geschaeftlich` | war in v1.0 Pflicht; BC3 leitet daraus die Kriterien je Story ab, BC4 baut dagegen |
| `to_be_vision` | war in v1.0 Pflicht mit ≥ 150 Wörtern |
| `betroffene_teilprozess_ids` | neu; Auflage BC0 vom 24.08.2026, die Teilprozess-ID wird durchgereicht |

Zusätzlich sind `aufwand_schaetzung_pt` und `risiken` wieder Pflicht — sie sind beim
Sprung v1.0 → v2.0 von Pflicht auf optional gewechselt.

`value.value_quelle` trägt hier den Wert `annahme`. Er ist im Vertrag v2.0 nicht
vorgesehen; die Dateien validieren deshalb nur gegen die erweiterte Fassung.

## Woher die Angaben stammen

| Teil | Quelle |
|---|---|
| Prozess- und Teilprozess-Kennungen, Namen, Ist-Abläufe | `bc0-baseline-onboarding/app/daten_v1_use_cases_testdaten.sql`, Erhebung `E-2026-08` vom 24.08.2026 |
| Anfragen `A-2026-01` bis `A-2026-03` | dieselbe Quelle |
| Mandant NoroAI Consulting GmbH | BC0-Baseline |
| Schmerzpunkte, Anforderungen, Akzeptanzkriterien, Soll-Zustände | Entwurf BC3 — fachlich von BC2 zu prüfen |
| Alle Euro-Beträge, Fallzahlen, Bearbeitungszeiten | Annahmen, nirgends erhoben |

Der angesetzte Stundensatz von 60 €/h liegt zwischen K2 (55 €) und K3 (68 €) aus
`v_rollen_kostensaetze_aktuell`. Sobald BC2 rechnet, gelten die Sätze aus der Datenbank.

## Einschränkung

Laut `v_gate_prozessstand` stehen die betroffenen Kernprozesse auf:

| Prozess | Bewertete Items | BC0-Sperre |
|---|---|---|
| KP-05 Wissensmanagement | 30 von 150 | `unvollstaendig` |
| KP-06 Personal | 60 von 150 | `unvollstaendig` |

Für keinen der drei Teilprozesse ist Gate 0 durchlaufen. Diese Konzepte sind damit
**Formatvorlage, keine Rechen- oder Freigabegrundlage.**

## Prüfen

```bash
python -m pip install jsonschema
# gegen die erweiterte Fassung, siehe #160
```

Geprüft am 31.08.2026: Schema gültig · alle Kennungen gegen die Projektdatenbank
abgeglichen · Einsparung, Investition, Amortisation und Prioritätswert nachgerechnet ·
alle drei laufen durch den BC3-Slicer und erzeugen eine schemakonforme Lieferung.
