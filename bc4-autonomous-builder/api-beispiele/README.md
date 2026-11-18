# API-Beispiele für den Generator

Echte Anfrage- und Antwortformen der externen APIs, die ein Prototyp aufruft. Der Generator gibt sie dem Modell im Bauauftrag mit (Abschnitt „API-BEISPIELE“), damit die gebauten Workflows die Felder richtig lesen, statt sie zu raten.

| Datei | API | Stand | Quelle |
|---|---|---|---|
| `travel-mock-api.json` | Reise-Mock-API `https://bc04-travel-mock-api.onrender.com` (Suche Flug/Hotel/Mietwagen, Reservierung, Buchung prüfen, Storno) | 15.11.2026 | Quelltext `pg-coe-kmu/travel-mock-api` (master `a8a766b`), Felder gegen `/v3/api-docs` der laufenden API geprüft: 28 Objekttypen, 0 Abweichungen |

## Regeln
- Eine Datei je API. Je Liste höchstens zwei Einträge. Die ganze Datei bleibt unter 12 000 Zeichen, weil der Generator sie dort abschneidet.
- Schlüssel: `"METHODE /pfad?parameter"`. Darunter steht `anfrage` (bei POST) und `antwort`, für Fehlerfälle `antwort_404`, `antwort_409` usw.
- `_hinweise` enthält Regeln, die sich aus den Beispielen allein nicht ablesen lassen, zum Beispiel wie die API Preise rechnet oder wie Fehler aussehen.
- Werte sind Beispiele. Keine echten Kunden- oder Zugangsdaten.

## Nutzung
- **Ab Generator v4.9.1:** In den Projektannahmen die Zeile `API-Beispiele: travel-mock-api` eintragen. Der Generator liest dann diese Datei, egal in welchem Lieferungsordner das Ticket liegt.
- **v4.9:** Der Generator liest nur `api-beispiele.json` im Lieferungsordner, also eine Kopie unter `contracts/bc3-to-bc4/<projekt>/api-beispiele.json`.
