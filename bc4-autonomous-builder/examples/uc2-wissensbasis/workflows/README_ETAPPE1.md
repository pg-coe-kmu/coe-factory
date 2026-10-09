# UC2: gesicherter Stand der ersten Etappe

Aus den vom Nutzer bereitgestellten Cloudexporten, 02.10.2026. Kein neuer Funktionsstand. GitHub-Ziel: `bc4-autonomous-builder/examples/uc2-wissensbasis/workflows/`.

- `UC2_Indexierung_Etappe1.json`: 18 Knoten, Auswahl AUR-01, AUR-02 und AUR-05.
- `UC2_Fragenbeantwortung_Etappe1.json`: 13 Knoten, Antwortschema v1.4, Antwortprüfung v1.1.
- `manifest.json`: SHA-256 der beiden bereinigten Exporte.

Entfernt: Kontoverknüpfungen, Instanz-/Workflow-Metadaten, angeheftete Daten und Tags. Projektadresse durch Platzhalter ersetzt, vorhandene Webhook-Kennung neu erzeugt, Aktivierung aus. Knotenparameter ansonsten unverändert, Verbindungen identisch zu den Nutzerexporten. Originaldateien nicht verändert. Nach Import müssen Supabase-Adresse und vorhandene Credentials erneut zugeordnet werden. Die laufenden Cloudworkflows nicht durch diese bereinigte Sicherung ersetzen.

Nachgewiesen durch Nutzerläufe: 3 Dokumente und 19 Chunks in Supabase, Überspringen unveränderter Dokumente; korrekte Personen-/Mitarbeiterantworten; erweiterte Prozessfrage mit AUR-02/AUR-05; Teilantwort und vollständige Enthaltung. Neuester Stand v1.4 zeigt Prozessantwort, kombinierte Personen-/Mitarbeiter-/Terminfrage und separate Enthaltung. Nicht alle ursprünglichen Einzeltests wurden auf demselben Stand separat wiederholt.

Die Sicherung ist ein funktionierender Zwischenstand, keine vollständige UC2-Abnahme. Offen: bessere Fehlerdiagnose, Versions-/Retrievalprotokolle, belegte Konfliktanzeige, dauerhafte Testnachweise, Vollbestand mit 14 Dokumenten, Update-/Löschtests, unabhängige Evaluation sowie BC3-/BC4-Ableitung.

Voraussetzungen: n8n Cloud (Nutzerstand 2.41.4), Supabase-Schema SQL 001/002/004 aus dem UC2-Arbeitsbestand, passender OpenAI-Zugang und GitHub-Wissensbestand. Dieses Paket enthält nur die Workflowsicherung; SQL-Dateien müssen vor einer vollständigen Reproduktion zusätzlich im Repository versioniert werden. `prompt_version` im gesicherten Export ist historisch unvollständig; Schema v1.4 und Validator v1.1 sowie diese Dateien gemeinsam als Stand verwenden.
