# BC2 -- ROI-/Value-Report (Mock)

**Prozess:** Antragsbearbeitung Krankentagegeld (KP-07) · **Stand:** 2026-06-27T12:00:00Z

**Berechnungsmodell (deterministisch, kein LLM):**

- Jahresvolumen: 13.800 Vorgaenge (300/Woche x 46 Wochen)
- Vollkostensatz: 50 EUR/h · Umsetzungs-Tagessatz: 800 EUR
- ist_kosten = betroffene_faelle x minuten_heute / 60 x stundensatz
- einsparung = ist_kosten x einsparungsgrad · investition = aufwand_pt x tagessatz
- amortisation_monate = investition / (einsparung / 12)

| Rang | Potenzial | Ist-Kosten/Jahr | Einsparung/Jahr | Ersparnis | Investition | Amortisation | Score | Kategorie |
|---|---|---|---|---|---|---|---|---|
| 1 | Bescheid-Generator mit Textbausteinen und Vorlagen | 69.000 EUR | 51.750 EUR | 75 % | 12.000 EUR | 2.8 Mon. | 100.0 | Quick Win |
| 2 | Automatisierte Antragserfassung via OCR + LLM-Feldextraktion | 57.500 EUR | 40.250 EUR | 70 % | 20.000 EUR | 6.0 Mon. | 56.2 | Quick Win |
| 3 | Gefuehrter Rueckfrage-Workflow bei unvollstaendigen Antraegen | 27.600 EUR | 16.560 EUR | 60 % | 24.000 EUR | 17.4 Mon. | 37.5 | Strategisch |

**Summe Einsparung/Jahr:** 108.560 EUR · **Summe Investition (Richtwert):** 56.000 EUR

> Hinweis: Werte sind Richtwerte auf Basis der BC1-Angaben und dokumentierter Annahmen. Die qualitative Bewertung (Impact/Komplexitaet) stammt aus der LLM-Potenzialerkennung, die Zahlen aus der deterministischen Berechnung.