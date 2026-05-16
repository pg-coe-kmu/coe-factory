# Contracts

**Owner:** Platform-Team + jeweils angrenzende BCs

## Zweck
Zentrale Sammlung aller Schnittstellen zwischen den Bounded Contexts. Jede Datei hier ist ein **JSON-Schema** + Beispieldaten und definiert den Vertrag zwischen zwei BCs.

**Wichtig:** Änderungen an Contracts erfordern Reviews der beiden angrenzenden Teams (siehe CODEOWNERS).

## Struktur
- `bc1-to-bc2/` – Strukturiertes Prozessprofil + Confidence Report
- `bc2-to-bc3/` – Freigegebenes Automatisierungskonzept
- `bc3-to-bc4/` – Blueprint + Ticket-Set + API-Specs
- `examples/` – Mockdaten je Schnittstelle (für Parallelentwicklung der BCs)
