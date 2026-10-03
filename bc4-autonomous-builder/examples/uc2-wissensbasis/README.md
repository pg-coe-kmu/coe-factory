# UC2 Aurelia – Referenzprototyp mit 14 Dokumenten

Stand: 03.10.2026. Funktionsfähiger Referenzprototyp für die universitäre Projektarbeit. Alle Inhalte in `knowledge/` sind fiktiv. Die bisherigen Live-Prüfungen sind begleitete Entwicklungstests; eine unabhängige Vollabnahme aller Dokumentinhalte liegt nicht vor. Der isolierte Konflikttest sowie der Aktualisierungstest mit anschließendem Wiederholungslauf sind inzwischen erfolgreich abgeschlossen.

## Ablauf

1. Der manuell gestartete Indexierungsworkflow liest 14 ausdrücklich ausgewählte Markdown-Dokumente aus `pg-coe-kmu/coe-factory`, Branch `main`, Verzeichnis `bc4-autonomous-builder/examples/uc2-wissensbasis/knowledge/`.
2. GitHub-Dateien werden aus einem festgehaltenen Commit gelesen. Abschnitte werden in maximal 1.200 Zeichen einschließlich Titel-/Abschnittspräfix aufgeteilt; bei Aufteilung innerhalb eines Abschnitts überlappen 150 Zeichen. Zwischen Abschnitten gibt es keine Überlappung.
3. OpenAI `text-embedding-3-small` erzeugt 1.536-dimensionale Vektoren. Supabase speichert Dokumente und Chunks. Ein Dokument wird atomar ersetzt; der Gesamtimport aller Dokumente ist keine gemeinsame Transaktion. Unveränderte Dateien mit passender Indexkonfiguration werden übersprungen.
4. Der Fragenworkflow nutzt den n8n-Testchat ohne Gesprächsgedächtnis. Er sucht bis zu zwölf Chunks per Cosinusähnlichkeit ab 0,20. Dieser Schwellenwert ist vorläufig und kein Wahrheitsmaß.
5. `gpt-4.1-mini-2025-04-14` beantwortet Teilfragen mit strukturierten Belegen. Der Workflow prüft Quellen-IDs und wörtliche Zitate und leitet den Status aus den Teilbewertungen ab. Die semantische Richtigkeit und Vollständigkeit der Modellbewertung ist damit nicht garantiert.
6. Fragen, Antworten, Quellenmetadaten, Versionen und Status werden in `uc2_query_runs` protokolliert. Ein Logging-Ausfall lässt die Antwort verfügbar, erscheint aber als Warnhinweis. Die gespeicherte `duration_ms` endet vor dem Speicherversuch und ist keine vollständige End-to-End-Latenz.

## Dateien und Versionen

- `workflows/UC2_Indexierung_14_Dokumente.json`: Bereinigter aktueller Nutzerexport, 18 Knoten; veraltete Drei-Dokumente-Beschriftungen korrigiert.
- `workflows/UC2_Fragenbeantwortung_14_Dokumente_v2_4.json`: Bereinigter aktueller Nutzerexport, 22 Knoten.
- Workflow `uc2-qa-v2.4-14docs`, Prompt `uc2-prompt-v2.2`, Schema `uc2_grounded_answer_v2_2`, Validator `uc2-validator-v2.4`.
- `database/001` bis `007`: Basistabellen, Indexierungs-/Suchfunktionen, Protokollierung und rückrollbare Selbsttests.
- `tests/ABSCHLUSSTESTS.md`: Nachweise der abgeschlossenen Prüfungen und bekannte Grenzen.
- `tests/UC2_TEST_Quellenkonflikt.json`: isolierter, erfolgreich live ausgeführter Konflikttest mit synthetischen Daten.

Die älteren Etappe-1- und v2-Dateien sind historische Entwicklungsstände. Für den dokumentierten 14-Dokumente-Stand gelten die zwei oben genannten Dateien. Dieses Update enthält keine neue Kopie des bereits vorhandenen `knowledge/`-Ordners.

## Einrichtung

Zielumgebung des Nutzers: n8n Cloud 2.41.4 und separates Supabase-Testprojekt mit pgvector 0.8.0 im Schema `extensions`.

Bei einer **neuen** Datenbank zunächst pgvector im Schema `extensions` bereitstellen, danach SQL 001 bis 007 in Reihenfolge prüfen/ausführen. SQL 001 legt Tabellen an und ist nicht zur erneuten Ausführung gegen die bereits eingerichtete Datenbank gedacht. SQL 003, 005 und 007 sind rückrollbare Selbsttests. Im vorhandenen Projekt wurden diese Einrichtungsschritte bereits durchgeführt; für einen Workflow-Neuimport ist keine erneute Datenbankanlage nötig.

JSON-Dateien jeweils in einen leeren n8n-Workflow importieren. Im jeweiligen Konfigurationsknoten den Platzhalter `https://DEIN-PROJEKT.supabase.co` ersetzen. Credential-Verweise, Instanzmetadaten und gepinnte Daten wurden aus den Exporten entfernt. Credential-Zuordnung:

- Indexierung: GitHub in `GitHub Commit`, `GitHub Inventar`, `GitHub Dokument`; Supabase in `Supabase Indexstand`, `Supabase atomar speichern`; OpenAI in `OpenAI Embeddings`.
- Fragen: OpenAI in `Frage einbetten`, `Antwort formulieren`; Supabase in `Wissen suchen`, `Testprotokoll speichern`.
- Supabase-Credential muss die für die RPCs freigegebene `service_role` nutzen. Diese Zugangsdaten verbleiben serverseitig in n8n. GitHub-HTTP-Credential muss `api.github.com` erlauben.

Zuerst Indexierung vollständig starten, danach Fragen im Testchat stellen. Die Exporte sind unveröffentlicht. Zugangsdaten gehören nicht in Code oder Repository.

## Bestätigter Bestand und Grenzen

14 Dokumente, 76 Chunks: 3 vorhandene Dokumente/19 Chunks plus 11 neue Dokumente/57 Chunks. Ein anschließender unveränderter Lauf übersprang alle 14 Dokumente und schrieb keine Chunks.

Keine automatische Löschsynchronisation, keine automatischen Wiederholungen, keine eigene Chatoberfläche und keine produktive Benutzer-/Mandantentrennung. Die service_role-gestützte Suche ist für die separate Testumgebung vorgesehen. Die Inhaltsabdeckung aller 14 Dokumente, adversariale Quelleninhalte und das Auffinden realer Konflikte im Retrieval sind nicht umfassend abgenommen. Ein manipulierter Nutzerprompt ist kein Nachweis gegen beliebige Quellenmanipulationen.

Die vereinbarte begleitete Abschlussprüfung des Referenzprototyps ist abgeschlossen; dies ist keine Produktionsfreigabe. Einzelne Prüfungen und ihre Nachweisgrenzen stehen in `tests/ABSCHLUSSTESTS.md`.

## Finaler Wissensstand

AUR-10 wurde auf Version 1.1 / Stand 2026-10-03 aktualisiert. GitHub-Commit: f893524e8bd84b305ff50c4259053d57da2a7fbb; Blob: 0679171353c22bd789228a8f46dfb99cad27b9d4. Fünf Chunks und ein Revisionsmarker UC2-20261003-A wurden vom Nutzer bestätigt. Die anderen Dokumente wurden bei diesem Lauf übersprungen und behalten ihre zuvor indexierten Commit-Verweise. Die Quelle in der getesteten Antwort zeigt den neuen AUR-10-Commit. Der finale unveränderte Wiederholungslauf wurde vom Nutzer bestätigt.

Das Paket ergänzt das bestehende Repository und ersetzt dessen README. Der bereits vorhandene knowledge-Ordner einschließlich AUR-10 Version 1.1 wird nicht überschrieben. Alte Workflows bleiben als historische Artefakte erhalten; maßgeblich sind die oben benannten 14-Dokumente-Exporte.
