# UC2 Aurelia – Wissensbasis für den Referenzprototyp

Dieser Bestand enthält 14 fiktive Wissensdokumente, die ersten Testfälle und das Basisschema für die separate UC2-Supabase-Testumgebung. Der vollständige RAG-Workflow ist noch nicht implementiert oder validiert. Die Inhalte beschreiben kein reales Unternehmen.

## Verzeichnisse

- `knowledge/`: ausschließlich die 14 Wissensdokumente für die Indexierung.
- `tests/`: Auswahl der ersten drei Dokumente und vorbereitete Sollantworten; niemals mit indexieren.
- `database/`: Basistabellen für den UC2-Prototyp. Das SQL ist keine Migration für die gemeinsame CoE-Factory-Datenbank und darf dort nicht ungeprüft ausgeführt werden.

## Erster Durchlauf

`tests/etappe1_manifest.json` wählt AUR-01 (Unternehmensprofil), AUR-02 (Ansprechpartner) und AUR-05 (Reklamationsprozess). Die Pfade im Manifest sind relativ zu diesem UC2-Verzeichnis. Für einen GitHub-API-Aufruf muss `bc4-autonomous-builder/examples/uc2-wissensbasis/` vorangestellt werden.

Die fachliche Kennung `document_id` im Markdown und Testmanifest entspricht `document_code` im Datenbankschema. Die Datenbankspalte `document_id` ist eine interne UUID.

Der Indexierungsworkflow soll den gewählten Branch zunächst auf einen Commit auflösen und Inventar sowie Dateiinhalte aus diesem Stand lesen. Für Antworten werden Links auf die tatsächlich indexierte Commit-Version erzeugt. Testfragen, README und SQL gehören nicht zum Suchbestand.

## Stand und nächste Schritte

- 14 Dokumente, Pflichtmetadaten, eindeutige Kennungen und interne Verweise lokal geprüft.
- Vier fachliche Ersttests und eine Wiederholungsprüfung vorbereitet; noch nicht ausgeführt.
- Tabellen `uc2_documents` und `uc2_chunks` mit RLS wurden laut Nutzer-Screenshot in der separaten Supabase-Testumgebung angelegt; pgvector 0.8.0 im Schema extensions.
- Startkonfiguration der Tabellen: `text-embedding-3-small`, 1536 Dimensionen. Der konkrete Modellaufruf wurde noch nicht getestet.
- Suchfunktion, atomarer Dokumentaustausch, Laufprotokolle und n8n-Workflows folgen.

Bestehende UC2-Verträge unter `contracts/bc3-to-bc4/uc2-wissensbasis/` und Generator-Workflows werden mit diesem Paket nicht geändert. Zuerst wird die Referenz validiert, anschließend werden Anforderungen und Ticket-Verarbeitung damit abgeglichen.

Zugangsdaten werden ausschließlich in n8n-Credentials hinterlegt und sind nicht Bestandteil dieses Pakets.
