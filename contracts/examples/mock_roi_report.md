# BC2 -- Value-Report (Fixture aus BC3s Formatvorlage)

**Lauf:** `FIXTURE-BC3-VORLAGE-2026-08-31`, Fassung 1 · **Mandant:** NoroAI · **Stand:** 2026-09-20T00:00:00+02:00

> **Keine BC2-Lieferung.** Hergeleitet aus BC3s Formatvorlage vom 31.08.2026, um zu zeigen, dass ihr Inhalt in den Vertrag v3.0 passt. Alle Zahlen tragen `value_quelle: "annahme"`.

**Rechenmodell (ADR-006 · BC2, deterministisch, kein LLM):**

- Jahresstunden x 43 EUR/h (Mischsatz) = Ist-Kosten
- Ist-Kosten x Automatisierungsgrad = Einsparung, als **Eckenrechnung** ueber beide Spannen
- Aufwand PT x 800 EUR/PT (Bausatz) = Investition -- bewusst ein anderer Satz
- `score = impact x (11 - umsetzungskomplexitaet)`, `impact = round((impact_monetaer + nutzwert) / 2)`

| Rang | PRIO | KP | Potenzial | Ist-Kosten/Jahr | Einsparung/Jahr | Investition | Amortisation | Score | Kategorie |
|---|---|---|---|---|---|---|---|---|---|
| 1 | PRIO 1 | KP-06 | Angebot erstellen und Buchung nach Freigabe auslösen | 10.320 EUR – 24.080 EUR | 3.096 EUR – 12.040 EUR | 12.000 EUR | 12 – 46 Mon. | 56 | Quick Win |
| 2 | PRIO 2 | KP-05 | Interne Fragen mit Quellenangabe beantworten | 12.900 EUR – 30.100 EUR | 3.870 EUR – 15.050 EUR | 12.000 EUR | 10 – 37 Mon. | 48 | Quick Win |
| 3 | PRIO 2 | KP-06 | Lebensläufe strukturiert erfassen und Kompetenzprofil aufbauen | 5.160 EUR – 12.040 EUR | 2.580 EUR – 9.030 EUR | 6.400 EUR | 8 – 30 Mon. | 48 | Quick Win |
| 4 | PRIO 2 | KP-06 | Reiseanfrage automatisch erfassen und Verfügbarkeit prüfen | 12.900 EUR – 30.100 EUR | 6.450 EUR – 22.575 EUR | 16.000 EUR | 8 – 30 Mon. | 42 | Quick Win |
| 5 | PRIO 2 | KP-06 | Projektanforderung mit Profilen abgleichen und Vorschlagsliste erzeugen | 9.288 EUR – 21.672 EUR | 5.573 EUR – 18.421 EUR | 14.400 EUR | 9 – 31 Mon. | 32 | Strategisch |
| 6 | PRIO 2 | KP-05 | Wissensquellen automatisch indexieren und aktuell halten | 6.192 EUR – 14.448 EUR | 3.096 EUR – 10.836 EUR | 6.400 EUR | 7 – 25 Mon. | 30 | Optional |

**Prozessrang** (der Rang des besten Potenzials, nicht Summe oder Mittel):

| Rang | KP | bester Score | Potenziale |
|---|---|---|---|
| 1 | KP-06 | 56 | 4 |
| 2 | KP-05 | 48 | 2 |

> **Kalibrierungsvorbehalt (#238).** Verteilung auf die Prioritaetsgruppen in diesem Lauf: PRIO 1 = 1, PRIO 2 = 5. Die Score-Baender sind gesetzt, nicht geprueft -- der Befund aus #167, dass mit plausiblen NoroAI-Groessen fast alles in einer Gruppe landet, reproduziert sich hier.
