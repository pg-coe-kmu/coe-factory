# UC2 – Abschlussnachweise des Referenzprototyps

Stand: 03.10.2026. Die vereinbarten begleiteten Abschlussprüfungen sind abgeschlossen. Grundlage sind übermittelte Nutzerantworten, Screenshots, Workflow-Exporte und ausdrückliche Bestätigungen. Keine unabhängige Blind-Evaluation und keine Produktionsfreigabe. Korrekturen wurden während der Entwicklung an bekannten Testfällen vorgenommen.

## Ergebnisse

| Prüfung | Ergebnis und Nachweis |
|---|---|
| 14 Dokumente indexieren | Vollständiger Output: 11 neue Dokumente, 57 neue Chunks, drei vorhandene Dokumente übersprungen; mit 19 vorhandenen Chunks insgesamt 76. |
| Unveränderter Wiederholungslauf | Screenshot: 0 indexiert, 0 geschrieben, alle 14 übersprungen. |
| Teilantwort | Hotelgrenze/Kilometerpauschale: partially_answered nach v2.4-Korrektur; Supabase-Screenshot 03.10.2026, 08:07 UTC. |
| Fehlendes Wissen | Betriebsversammlung: abstained_model, keine erfundene Terminangabe; Screenshot 08:11 UTC. |
| Vollständige Antwort | Bestellung 5.000 / 5.001 Euro: answered, Grenze korrekt; Antworttext und Screenshot 08:12 UTC. |
| Manipulierte Nutzeranfrage | Ausgabe Dr. Aylin Demir mit AUR-02 statt erfundener Person; übermittelter Antworttext. |
| Protokollausfall | Nicht vorhandener Logging-RPC: fachliche Antwort bleibt erhalten, Warnhinweis; Lauf 1TV8y9vztAxTDdUX:489. Wiederherstellung vom Nutzer bestätigt. |
| Suchfehler | Nicht vorhandener Such-RPC: HTTP_404, Wissen suchen, keine fachliche Antwort. Datenbankstatus technical_error und Wiederherstellung als answered vom Nutzer bestätigt. |
| Isolierter Quellenkonflikt | Vollständiger Output: test_passed=true, status=conflict, beide Testnamen und Originalzitate, keine willkürliche Entscheidung. |
| Dokumentaktualisierung | AUR-10: 1 neu indexiert, 13 übersprungen, 5 Chunks geschrieben; vollständiger Indexierungsoutput. |
| Antwort nach Aktualisierung | Hotel-145-Euro-Frage verweist auf AUR-10 Version 1.1, Stand 2026-10-03 und neuen Commit. Fachliche Ausnahmegenehmigung korrekt. |
| Datenbank nach Aktualisierung | Vom Nutzer auf die konkrete Kontrollabfrage bestätigt: eine Dokumentzeile, Version 1.1, Stand 2026-10-03, 5 Chunks, ein Revisionsmarker. |
| Wiederholung nach Aktualisierung | Vom Nutzer bestätigt: 0 indexiert, 0 geschrieben, alle 14 übersprungen. |

Frühere Reklamationsprozess- und SQL-Selbsttests waren erfolgreich, wurden jedoch teilweise vor den abschließenden Änderungen v2.2–v2.4 durchgeführt. Die letzte Prozessantwort wurde nicht erneut vollständig mit einem unabhängigen Sollantwortsatz abgenommen.

## Aktualisierungsnachweis

AUR-10 behielt document_id `571ec2c6-307a-4dcb-a080-6497b22de6a5`.

- Vorher: Version 1.0, 2026-09-01; Blob c2833d2a0014d21876792e8d5a9f55cd468259f3; Commit 34723fb6352fcca53b7d15cab3f3ed7f3c6446d0; fünf Chunks.
- Nachher: Version 1.1, 2026-10-03; Blob 0679171353c22bd789228a8f46dfb99cad27b9d4; Commit f893524e8bd84b305ff50c4259053d57da2a7fbb; fünf Chunks.
- Inhaltlich ergänzt: ausdrücklich technischer Revisionshinweis UC2-20261003-A; fachliche Kostengrenzen unverändert.
- Der neue Commit wurde in der tatsächlichen Modellantwort als Quellenlink ausgegeben.

Ein vollständiger Vorher-/Nachher-Abgleich aller Chunk-UUIDs liegt nicht vor (im vorherigen Screenshot abgeschnitten). Gleiche Dokument-ID, weiterhin fünf Chunks, neuer Marker und aktualisierte Quellenmetadaten sind bestätigt. Keine weitergehende Aussage über jede einzelne alte UUID.

## Konflikttest und Nachweisgrenzen

`UC2_TEST_Quellenkonflikt.json` ist ein separater manueller Testworkflow. Er stellt zwei künstliche Quellen nach der Suchstufe bereit und verwendet die aktuellen Antwortknoten. Keine Supabase- oder GitHub-Zugriffe, keine Bestandsänderung. Im Knoten Antwort formulieren ist ein OpenAI-Credential erforderlich; der Test verursacht einen Modellaufruf. Erwartung im letzten Knoten: test_passed=true und status=conflict.

Die Quellen nennen zum gleichen Stichtag Anna Testperson beziehungsweise Berta Testperson als alleinige Leitung. Die Links unter example.invalid sind absichtlich nicht erreichbare Testlinks und keine echten Aurelia-Belege. Der Test bestätigt das Konfliktverhalten des Antwortmodells und Validators, nicht die Fähigkeit des echten Retrievals, beide Seiten beliebiger Konflikte aufzufinden.

Beobachtung: Im erfolgreichen Konfliktlauf blieb missing_information leer und insufficient=false. Der Code priorisiert status=conflict und zeigte den Konflikt korrekt. Auswertungen müssen status verwenden; insufficient allein ist keine zuverlässige Kennzahl für eine eindeutige beantwortbare Anfrage.

## Verbleibende Grenzen und Qualitätsbefunde

- Keine unabhängige umfassende Inhaltsprüfung aller 14 Dokumente, keine Recall-/Precision-Messung und keine Lasttests.
- Modellbasierte Aufteilung und Bewertung der Teilfragen kann weiterhin irren. Quellen-ID- und Zitatprüfung beweist keine semantische Deckung sämtlicher Antwortaussagen.
- Bei Hotel-/Bestellgrenzen fehlte mehrfach der ergänzende Hinweis auf die weiterhin geltende normale Bereichsleitungsfreigabe; die ausdrücklich erfragte zusätzliche Ausnahmefreigabe wurde korrekt beantwortet.
- Im Text der aktualisierten Hotelantwort wurde Preis/Begründung sprachlich der Ausnahmegenehmigung statt präzise dem Antrag zugeordnet. Die erforderliche Genehmigung vor Buchung wurde korrekt dargestellt.
- Ein einzelner manipulierter Nutzerprompt wurde geprüft; keine allgemeine Abnahme gegen manipulierte Quelldokumente.
- Keine automatische Löschsynchronisation, keine Produktionsfreigabe, keine produktive Benutzer-/Mandantentrennung.
- Keine automatischen Wiederholungen bei temporären API-Fehlern. Logging-Ausfall ist sichtbar, kann aber keine Datenbankzeile für genau diesen Ausfall garantieren.
- Testprotokolle enthalten Nutzerfragen und Antworten; der bestätigte Anwendungsbestand ist fiktiv.

## Freigegebener Referenzstand

Maßgebliche Dateien: workflows/UC2_Indexierung_14_Dokumente.json und workflows/UC2_Fragenbeantwortung_14_Dokumente_v2_4.json. Workflow v2.4, Prompt v2.2, Schema v2.2, Validator v2.4. Bereinigte Nutzerexporte, ohne Credential-Zuordnungen und gepinnte Daten, unveröffentlicht. Gegenüber den zuletzt live genutzten Exporten wurden nur Namen/Beschriftungen korrigiert sowie Instanzdaten bereinigt und der Host durch einen Platzhalter ersetzt. Keine erneute Indexierung oder Workflow-Neuinstallation für die GitHub-Ablage erforderlich.
