# UC1-Test-Tickets (26.10.2026)

Test-Tickets für UC1 Reisebuchung (KP-06.TP-2) im Format der BC3-Lieferung an BC4 (Vertrag 3.5). **Von Hand erzeugt, ohne n8n-Slicer.**

Seit 29.10.2026 liegen die Dateien direkt hier statt im Unterordner `del-uc1-reisebuchung-2026-10-26-test/`, damit der BC4-Generator sie findet. Sie ersetzen die Lieferung `del-uc1-reisebuchung-2026-09-06-104439` (in der Git-Historie).

> **Ohne Gewähr.** Diese Tickets sind anhand von Zakarias Workflow erstellt, nicht auf dem normalen Weg. Normal schneidet BC3 die Tickets aus dem Konzept, das BC2 liefert (`contracts/bc2-to-bc3/lieferungen/`), mit Prüfung an Gate 2. Für UC1 gibt es noch kein Konzept von BC2. Es gibt deshalb keine Garantie, dass die Tickets vollständig sind oder dem entsprechen, was BC2 und der Slicer später liefern. Kommt ein UC1-Konzept von BC2, ersetzt die reguläre Lieferung diese Dateien.

- **Inhalt:** nur, was Zakarias Prototyp `UC1_PROTOTYPE_FULL_DATA_V3` (22.10.2026) tut: ein Eingang, vier Wege (Suche mit Angeboten, Reservierung, Buchung prüfen, Stornierung).
- **Messverfahren** sind Vorschläge von BC3, der Workflow enthält keine. Wo keiner passt, steht „offen“.
- **Datenschutz und KI-Verordnung:** Hinweise von BC3 nur in `compliance-audit.json`, nicht als Story.
- **Konzept-Bezug:** BC3s simuliertes UC1-Konzept (`bc3-engineering-architect/simulation/noroai-SIM-UC1-2026-10-22-f1/`), weil es von BC2 kein UC1-Konzept gibt.
- Gate 2 steht auf `pending`, niemand hat freigegeben.
- **Zweck:** BC4 leitet daraus Anforderungen an BC0 und BC1 ab (Absprache nach dem Kettentest am 26.10.2026, Treffen BC4 am 28.10.).

| Datei | Inhalt |
|---|---|
| `ticket_set.json` | 3 Epics, 12 Stories, gegen `contracts/bc3-to-bc4/tickets.schema.json` geprüft |
| `compliance-audit.json` | Vorprüfung (limited, Ampel gelb), 5 Pflichten nach Adressat |
| `blueprint.json` | Komponenten, Datenflüsse, menschliche Entscheidungspunkte |
| `architecture.md` | Bauplan zum Lesen, Hinweise von BC3, offene Punkte |
