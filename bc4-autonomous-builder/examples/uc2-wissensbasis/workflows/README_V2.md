# UC2 Fragenbeantwortung v2

Bereinigter Nutzerexport vom 03.10.2026. Enthält Protokollkorrektur first(0,0). Laufzeitverhalten und Verbindungen des Exports erhalten. Credential-Verweise und Instanzmetadaten entfernt, Supabase-Host durch Platzhalter ersetzt, Webhook-ID erneuert. Kein erneuter Import in die bereits funktionierende Instanz nötig.

Neuinstallation: Voraussetzung sind bestehende UC2-Tabellen, Suchfunktion (SQL 001–005) und drei indexierte Dokumente AUR-01/02/05. Danach SQL 006 und Selbsttest 007 ausführen. Workflow in einen leeren n8n-Workflow importieren. Host in Frage und Konfiguration einsetzen. OpenAI-Credential in Frage einbetten und Antwort formulieren wählen; Supabase-Credential in Wissen suchen und Testprotokoll speichern wählen. Im Testchat testen.

Dieses Paket ist ein v2-Update, kein vollständiges Neuinstallationspaket. Bestehende Etappe-1-Dateien bleiben erhalten. Live-Testnachweis und offene Prüfungen: ../tests/2026-10-03_v2_Livetests.md.
