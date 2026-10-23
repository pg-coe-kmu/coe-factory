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

## Stand 23.10.2026
- Der Slicer läuft in n8n als feste Kette kleiner Workflows (BC3-00 bis BC3-80). KI nur in drei Schritten, Modelle von Mistral mit fester Version.
- Ein Mensch gibt an Gate 2 frei, nachbessern oder ablehnen ist möglich, Begründung Pflicht bei Nein. Die Gate-2-Seite kommt per Telegram-Link.
- Erste echte Lieferung an BC4 am 23.10.2026: KP-05, PR #337, Zeile in `bc3.lieferungen`.
- Offen: Rückweg zu BC2 für Nachbesserungen und fehlende Messverfahren.

## Dateien in diesem Ordner
- [ablauf-slicer.md](ablauf-slicer.md): Ablauf eines Laufs, Schritt für Schritt
- [nachweis-pruefstand-reproduzierbarkeit.md](nachweis-pruefstand-reproduzierbarkeit.md): Prüfstand (Precision, Recall, F1) und Reproduzierbarkeit
- [pruefstand/risikoklasse-faelle.json](pruefstand/risikoklasse-faelle.json): 16 erfundene Testfälle für den Prüfstand
- [workflows/](workflows/README.md): die 15 n8n-Workflows des Slicers, bereinigt exportiert, mit Zugängen und Platzhaltern
- [bc3-architektur-bausteine.md](bc3-architektur-bausteine.md): Bausteine der Architektur (Entwurf vom 26.06.2026, mit Stand 23.10.2026)
- `bc2-anforderung/`, `pseudonymisierung/`, `simulation/`: Beispiele, Vorarbeiten und simulierte Konzepte
