
- **Pipeline-Engine** = n8n.

- **LLM** = Mistral (EU-Anbieter).

- **Eingangs-Storage** = ein Ablage-Ort wo BC2 ihre Konzept-Dateien hinlegt, damit unsere Pipeline sie abholen kann. Aktuell: Google Drive Ordner. Alternative: ein GitHub-Ordner (evtl. besser, weil BC2 dort sowieso arbeitet).

- **Ausgangs-Storage** = ein Ablage-Ort wo unsere fertigen tickets.json landen, damit BC4 sie abholen kann. Aktuell: Google Drive Ordner. Alternative: ein GitHub-Ordner (evtl. besser fürs Abholen durch BC4, weil BC4 dort den Code commitet).

- **Schema-Registry** = ein Ort wo die "Bauanleitungen" für die JSON-Dateien liegen (welche Felder sind Pflicht, welche optional). Wie ein Regelheft. Heute: GitHub-Repository.

- **Secrets-Tresor** = sicherer Speicher für Passwörter und API-Schlüssel, damit sie nicht im Code rumliegen. Heute: n8n-Credentials (eingebaut).

- **Lieferungs-Archiv** = eine Tabelle die festhält welche Lieferung wann von wem freigegeben wurde. Für die Audit-Spur (Nachweis-Pflicht: wer hat wann was entschieden?).

- **Approval-UI** = ein Webformular wo ein Mensch klickt "freigegeben" bevor die Lieferung an BC4 geht.

(optional) **Ticket-Dokumentation** = pro Story/Ticket eine eigene lesbare Seite. Die wichtigsten Infos (Beschreibung, Akzeptanzkriterien, Abhängigkeiten, Herkunft) haben wir bereits in tickets.json — ein Extra-Tool wäre nur für Diskussion, Status-Updates, Kommentare nötig. Optionen falls gewünscht:
  - **GitHub Issues** = 1 Story = 1 Issue, mit Kommentaren, Status-Labels. Vorteil: GitHub ist schon entschieden, kein Extra-Tool.
  - **PostgreSQL** = klassische Datenbank, jede Story = eine Zeile. Lässt sich mit Lieferungs-Archiv kombinieren, braucht aber Frontend.

- (optional) **Vektor-Datenbank** =  um Compliance-Profile von einem KMU zum nächsten wiederzuverwenden (ähnliche Branche wie KMU X, gleiche Pflichten).



## Nur Gedanken eventuell für andere Bcs

- **PII-Filter** 
- **Audit-Log** 
- **Identity Provider** (= zentraler Login-Service) 


3. **Compliance-Stories als BC3-Output oder Plattform-Aufgabe?** (PII, Audit, Crypto)
4. **BC4-Übergabe-Format:** json oder md?

---

*Stand: 26.06.2026 ·  Diskussions-Entwurf*
