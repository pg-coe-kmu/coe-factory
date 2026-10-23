# Nachweis Prüfstand und Reproduzierbarkeit

Stand 22.10.2026. Belege zu den Kennzahlen Precision, Recall, F1 und zur Wiederholbarkeit des BC3-Slicers.

## Kurz

- **Prüfstand:** BC3-83 läuft monatlich und schickt 16 erfundene Fälle mit feststehender Risikoklasse durch die Compliance-Prüfung BC3-30. Vier Läufe: je 16 von 16 Klassen richtig, Macro-F1 1,0, Fundstelle 10 bis 11 von 12.
- **Reproduzierbarkeit:** Vier Läufe mit demselben UC1-Konzept, festem Modell (`mistral-large-2512`), Temperatur 0, Seed 42. Einstufung, Ampel und Pflichten bleiben gleich, der Schnitt der Stories schwankt (16 bis 21 Stories).
- **Aussage:** Das Compliance-Urteil ist wiederholbar, der Story-Schnitt nicht wörtlich. Deshalb prüfen Regeln (Abdeckung, Gegenprobe, Gate-2-Prüfpunkte) jeden Lauf, und ein Mensch entscheidet an Gate 2.
- **Grenzen:** Die 16 Fälle sind eigene, eindeutig formulierte Fälle, kein unabhängiger Datensatz. Gemessen wird BC3-30 ohne Regel R2. Grenzfälle sind nicht abgedeckt.

## Prüfstand Risikoklasse

Testfälle: [pruefstand/risikoklasse-faelle.json](pruefstand/risikoklasse-faelle.json) (3 verboten, 7 Hochrisiko über Anhang III Nr. 2 bis 5, 2 Fallen ohne Hochrisiko, 2 begrenzt, 2 minimal). Soll-Werte aus dem Wortlaut von Art. 5, Art. 50 und Anhang III KI-VO, von BC3 geprüft am 22.10.2026.

| Kennzahl | Lauf 1927 | Lauf 1961 | Lauf 1995 | Lauf 2028 |
|---|---|---|---|---|
| Klasse richtig | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 |
| Precision / Recall / F1 je Klasse (verboten, hoch, begrenzt, minimal) | je 1,0 | je 1,0 | je 1,0 | je 1,0 |
| Macro-F1 | 1,0 | 1,0 | 1,0 | 1,0 |
| Hochrisiko oder verboten: Precision / Recall / F1 | 1,0 / 1,0 / 1,0 | 1,0 / 1,0 / 1,0 | 1,0 / 1,0 / 1,0 | 1,0 / 1,0 / 1,0 |
| Fundstelle getroffen | 11 / 12 | 11 / 12 | 10 / 12 (zusätzlich H5: Nr. 3 b statt a) | 11 / 12 |
| Dauer | rund 7 Minuten | rund 14 Minuten (Fall M1 hing bei Mistral) | rund 5 Minuten | rund 6 Minuten |

Fehltreffer in allen vier Läufen: U2 (Mieter-Punktzahl) richtig als verboten eingestuft, aber Art. 5 Abs. 1 Buchst. c nicht genannt. Die Meldung „Einstufung strittig“ bei allen H-Fällen kommt nur vom Prüfstand: Ohne Regel R2 findet die Gegenprobe keinen Bereich aus Anhang III.

## Reproduzierbarkeit UC1

Konzept: `bc3-engineering-architect/simulation/noroai-SIM-UC1-2026-10-22-f1/konzept_KP-06.json` (KP-06.TP-2, simuliert). Alle Läufe im Modus `test`.

| | 1813 | 1847 | 1880 | 1903 |
|---|---|---|---|---|
| Klasse, Ampel | minimal, grün | minimal, grün | minimal, grün | minimal, grün |
| Anhang III | keiner | keiner | keiner | keiner |
| Pflichten | 6 | 6 | 7 | 7 |
| Epics (Stories je Epic) | 2 (10, 6) | 2 (9, 7) | 2 (11, 7) | 2 (14, 7) |
| Stories mit offenem Messverfahren | 9 | 7 | 8 | 8 |
| Gate-2-Prüfpunkte offen | Kriterien | Kriterien | Kriterien, Grundlagen | Kriterien, Grundlagen |
| Abdeckung aller A- und K-Nummern | vollständig | vollständig | vollständig | vollständig |

- **1880 und 1903 sind das Vergleichspaar** (gleiche Fassung von BC3-20, 30, 40): identische sieben Pflichten mit denselben Adressaten (4 an BC4, 2 an die Organisation, 1 an die Plattform). Die Stories unterscheiden sich in Zahl (18 und 21) und Wortlaut, nicht im abgedeckten Inhalt.
- Zwischen 1813/1847 und 1880/1903 wurden BC3-20 und BC3-50 geändert, die Zahl der Entscheidungspunkte im Bauplan ist deshalb nicht vergleichbar.
- Der Schnitt schwankt trotz Seed: Mistral hält den Seed nicht wörtlich, das Compliance-Urteil bleibt gleich.

Seit dem 23.10.2026 erkennt BC3-40 doppelte Compliance-Stories und hängt sie nicht an. Die Zahlen oben stammen von vorher. Neue Zahlen kommen mit dem Kettentest vom 26.10.2026.
