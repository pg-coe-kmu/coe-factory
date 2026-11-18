# BC3 – Engineering Architect

**Team:** Svetlana, Sabrina
**Phase:** 3 – Planung

## Zweck
Übersetzer zwischen Business-Strategie und technischer Umsetzung. Erstellt die logische Struktur der Lösung.

## Messages
- **Consumed:** Freigegebenes Automatisierungskonzept (aus BC2)
- **Produced:** Ticket-Set (`ticket_set.json`), Compliance-Befund (`compliance-audit.json`), Technisches Blueprint (`architecture.md`, `blueprint.json`). Die offenen Punkte (`offene-punkte.json`) bleiben bei BC3. API-Spezifikationen entfallen (Pflicht am 15.10.2026 gestrichen).

## Arbeitspakete
- **AP 3.1** Epic & Story Slicer (Prompt-Chains): umgesetzt in BC3-20 (Stories), BC3-30 (Compliance) und BC3-40 (Tickets bauen und prüfen)
- **AP 3.2** Ticketing-System-Integration (GitHub Issues API): nicht umgesetzt, die Übergabe an BC4 läuft als Dateien per Pull Request
- **AP 3.3** System-Blueprint Generator: umgesetzt in BC3-50, der API-Teil ist abgeschaltet

## Schnittstellen
- **Input von BC2:** `/contracts/bc2-to-bc3/`, BC3-01 holt neue, an Gate 1 freigegebene Konzepte selbst ab
- **Output an BC4:** die vier Dateien in `/contracts/bc3-to-bc4/<projekt>/<lieferung>/`, per Pull Request nach der Freigabe an Gate 2

## Stand 18.11.2026
- Der Slicer läuft in n8n als feste Kette kleiner Workflows (BC3-00 bis BC3-80). KI nur in drei Schritten, Modelle von Mistral mit fester Version.
- Ein Mensch gibt an Gate 2 frei, bessert nach oder lehnt ab. „Nachbessern“ startet einen neuen Lauf mit dem Kommentar, höchstens dreimal. Die Gate-2-Seite kommt per Telegram-Link.
- Vertrag BC3 → BC4 3.6: Die IDs von BC2 (Mandant, Paket, Priorisierung, Potenzial je Epic) stehen im Ticket-Set und in `bc3.lieferungen`. Messverfahren übernimmt BC3 von BC2, fehlende sind als „offen“ markiert.
- Nur Lieferungen aus echten Läufen kommen an BC4. BC3 führt den Pull Request erst nach grüner Prüfung zusammen. Ordner: `del-` gültig, `test-del-` Testlauf, `veraltet-del-` alter Stand.
- Erste Lieferung nach 3.6: `contracts/bc3-to-bc4/kp-06/del-kp-06-2026-11-18-201545/` (UC1, PR #402). Erste echte Lieferung überhaupt am 23.10.2026 (KP-05, PR #337).
- Offen: Rückweg zu BC2, ID je Akzeptanzkriterium, Rückkanal von BC4. Einzelheiten und alle Änderungen seit 23.10.: [ablauf-slicer.md](ablauf-slicer.md).

## Dateien in diesem Ordner
- [ablauf-slicer.md](ablauf-slicer.md): Ablauf eines Laufs, Schritt für Schritt
- [nachweis-pruefstand-reproduzierbarkeit.md](nachweis-pruefstand-reproduzierbarkeit.md): Prüfstand (Precision, Recall, F1) und Reproduzierbarkeit
- [pruefstand/risikoklasse-faelle.json](pruefstand/risikoklasse-faelle.json): 16 erfundene Testfälle für den Prüfstand
- [workflows/](workflows/README.md): die n8n-Workflows des Slicers, bereinigt exportiert, mit Zugängen und Platzhaltern (Export vom 23.10.2026, ein neuer Export mit dem Stand 18.11. folgt)
- [bc3-architektur-bausteine.md](bc3-architektur-bausteine.md): Bausteine der Architektur (Entwurf vom 26.06.2026, mit Stand 23.10.2026)
- `bc2-anforderung/`, `pseudonymisierung/`, `simulation/`: Beispiele, Vorarbeiten und simulierte Konzepte
