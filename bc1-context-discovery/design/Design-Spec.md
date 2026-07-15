# BC1 — Interactive Context Discovery · MVP-Design (Spec)

> **Status:** Entwurf (lokal) · **Stand:** 2026-06-23 · **Scope:** MVP-Kern
> **Bauweise:** Hybrid (n8n-Hülle + Code-Kern) · **Arbeitspakete:** #48–#53
> **Generik:** fall-unabhängig bis die Use Cases feststehen; danach lokale Spezialisierung über ein Use-Case-Paket.
> **Hinweis:** Dies ist die *technische Ebene* unter der bestehenden Konzept-Ebene des Teams. Die Konzept-Übersicht wird hier nicht wiederholt.

---

## Teil A — Big Picture

**Was BC1 macht.** BC1 verwandelt die unstrukturierte Schilderung eines Process Owners in ein **strukturiertes Prozessprofil (JSON)** plus einen **Vollständigkeits-/Confidence-Bericht** und eine **menschenlesbare Doku**. Das Ergebnis geht über ein menschliches Prüf-Tor (**Gate 0**) an BC2.

**MVP-Schnitt.** Der erste lauffähige Prototyp ist bewusst schlank: ein **Text-Chat-Interviewer**, der gezielt nachfragt und am Ende ein sauberes JSON-Profil liefert. Voice/OCR, PII-Filter, Doku-Generator und das Mapping auf eine Baseline sind **spätere, eigenständig andockbare Schichten** (in der Roadmap, Teil B8).

**Bauweise (Hybrid).** Zwei Teile mit klaren Aufgaben:
- **n8n = Hülle/Verrohrung:** nimmt Chat-Nachrichten an, ruft den Kern, schickt Antworten zurück. Bewusst „dumm".
- **Code-Kern = das Gehirn:** führt das Gespräch, zieht Fakten heraus, prüft was fehlt, entscheidet die nächste Frage. Liegt in **testbarem Code**.

**Der Ablauf in einem Satz.** Nach jeder Antwort prüft der Kern „was habe ich, was fehlt?" und stellt die nächste passende Frage — bis das Profil vollständig genug ist; dann geht es an Gate 0.

**Fünf Leitprinzipien:**
1. **Nie still scheitern** — jede Lücke wird markiert, nichts geht verloren.
2. **Keine erfundenen Zahlen** — Vollständigkeit wird gezählt, nicht geschätzt; pro Feld gibt es erklärbare Status statt ausgedachter Prozente.
3. **Der Mensch an Gate 0 ist das Sicherheitsnetz** — der MVP muss ehrlich sein, was er nicht erfassen konnte, nicht perfekt.
4. **Generisch bis die Use Cases feststehen**, dann lokal spezialisieren.
5. **Kein Over-Engineering** — nur der MVP-Kern; alles andere nachgehalten.

---

## Teil B — Technischer Teil

### B1. Architektur & Bauweise

- **Genau ein deployter Kern-Dienst.** Die sechs Module (B2) sind *interne* Code-Grenzen, **keine** eigenen Services.
- **Reihenfolge:** zuerst den Code-Kern über einen minimalen Chat-/HTTP-Client beweisen, **dann** n8n davorschalten. n8n-Integration nicht vor bewiesenem Kernverhalten.
- **Eine Schnittstelle n8n ↔ Kern**, eine **versionierte** Antwort mit explizitem Status:
  - **Request:** `{ session_id, message_id, message, schema_version? }` (das optionale `schema_version` prüft die **Transportschicht** gegen das deployte Paket; der Kern bindet die Session beim ersten Turn an die Paket-Version und lehnt Wechsel ab)
  - **Response:** `{ status, payload }` mit `status ∈ { "frage", "fertig", "fehler_fortsetzbar" }`
    - `"frage"` → `payload = { naechste_frage, feld }`
    - `"fertig"` → `payload = { felder, vollstaendigkeit, ungeloeste_felder[], schema_version }`
      (`felder` = das Profil: je Paketfeld `{ wert, status, quelle, grund, kandidaten[{wert, quelle}] }`;
      finale Formalisierung gehört nach `contracts/bc1-to-bc2/`, gemeinsam mit BC2 + Platform)
    - `"fehler_fortsetzbar"` → `payload = { grund }`
- **Idempotenz über `message_id`** (nicht nur `session_id`): bereits verarbeitete Nachrichten werden nicht doppelt angewandt (schützt vor n8n-/HTTP-Retries).
- **Persistenz gehört dem Kern.** Laden → Ändern → Speichern ist **eine atomare Operation** mit **State-Versionierung (optimistic locking)**; veraltete Updates werden abgewiesen/erneut gespielt. **n8n schreibt nie selbst den Zustand** — es transportiert nur.

### B2. Komponenten (je eine Verantwortung)

| Modul | Verantwortung | LLM? |
|---|---|---|
| **State-Store** | Besitzt Persistenz **und** Nebenläufigkeit: atomares Laden/Ändern/Speichern mit Versionsfeld. Hält je Session: erfasste Felder (mit Quelle + Status), Gesprächslog, Retry-Zähler, `schema_version`, Session-Status. | nein |
| **Extractor** | Nachricht + Stand → Feld-**Kandidaten**, jeder mit Quelle (`message_id`). | ja |
| **Confidence-Check** | Reine Logik: je Pflichtfeld ein **erklärbarer Status** `fehlt / gueltig / ungueltig / unklar / ungeloest`. Zusätzlich **deterministische Vollständigkeit** = erfüllte Pflichtfelder / Pflichtfelder gesamt. | nein |
| **Dialog-Manager** | Besitzt **Priorisierung, Retry-Caps, Fragenauswahl, Fertig-Entscheidung**. Nutzt das LLM nur zum **Formulieren** der Frage. | ja (nur Formulierung) |
| **Schema + Use-Case-Paket** | Deklarative Plug-Stelle (B6). | nein |
| **LLM-Client** | Adapter, versteckt den Anbieter; austauschbar. Liefert strukturierte Extraktion; **die Zustandsübergänge steuert deterministischer Code**, nicht das LLM. | — |

**Merge-Regel (Extractor → State):** Neue Werte werden als **Kandidaten** geführt. Ein bereits bestätigter (= **gültiger**) Wert wird **nicht still überschrieben**; bei Abweichung entsteht ein markierter Konflikt (B4). Präzisierungen: (1) Ein **ungültiger** Wert gilt nicht als bestätigt — eine validierte Korrektur **ersetzt** ihn, der alte Wert bleibt als Kandidat erhalten (Entscheidung 12.07.2026). (2) Ein **unklarer** Konflikt ist per **exakter Klärung** auflösbar: erneute Nennung des Werts bestätigt ihn, exakte Nennung eines Kandidaten wählt diesen (Tausch; nichts geht verloren; Entscheidung 15.07.2026).

### B3. Datenfluss & State-Machine

**Session-Status (State-Machine):** `AKTIV → WARTET_AUF_ANTWORT → … → FERTIG | FEHLER_FORTSETZBAR`. Nur definierte Übergänge sind erlaubt.

**Eine Runde:**
1. n8n ruft den Kern mit `{ session_id, message_id, message }`.
2. **Rohnachricht zuerst speichern** — *vor* dem LLM-Aufruf (sonst widerspricht es „nie Daten verlieren").
3. **Idempotenz-Check** auf `message_id` (schon verarbeitet → überspringen).
4. **State laden** (atomar, versioniert).
5. **Extractor** → Kandidaten (mit Quelle).
6. **Merge** in den State nach Merge-Regel (Konflikte markieren, nicht überschreiben).
7. **Confidence-Check** → Status je Pflichtfeld + Vollständigkeit.
8. **Dialog-Manager** → nächste Lücke wählen (Caps beachten) und Frage formulieren **oder** „fertig".
9. **State speichern** (atomar, Versions-Check).
10. **Eine versionierte Antwort** zurück. n8n sendet die Frage (→ Schleife) **oder** übergibt `profil + vollstaendigkeit + ungeloeste_felder` an Gate 0.

**Wichtig:** Fragenauswahl ist **datengetrieben** (welches Pflichtfeld fehlt), kein starres Skript. Der State lebt in der DB, **nicht** im LLM-Kontext → Gespräche sind pausier-/fortsetzbar. Der **Output trägt explizit den Vollständigkeits-Status + die Liste ungelöster Felder + `schema_version`**, damit BC2 unvollständige Daten nicht für vollständig hält.

### B4. Fehlerfälle

**Leitregel:** nie still scheitern · nie Daten verlieren · Mensch an Gate 0 ist Sicherheitsnetz · ehrlich über Lücken.

- **Endlos-Schleife verhindern:** max. **K Nachfragen pro Feld** (z. B. 2) + **Runden-Limit** je Anfrage → danach Feld `ungeloest` + Grund. „Fertig" = alle Pflichtfelder `gueltig` **oder** Rest als `ungeloest` markiert.
- **Vage Antwort:** einmal gezielter nachfragen, sonst Status herabsetzen + Notiz, weiter.
- **Widerspruch:** MVP nur **exakte Gleich-Feld-Konflikte** (keine semantische Erkennung — das wäre versteckte LLM-Komplexität). Alten + neuen Kandidaten mit `message_id` behalten, Nutzer klären lassen, **nie still überschreiben**.
- **LLM-Aussetzer/Timeout:** **eng begrenzte** Retries mit Backoff (damit der Chat-Request nicht in n8n-/Client-Timeouts läuft); sonst State speichern und `fehler_fortsetzbar` zurückgeben.
- **Kaputtes Extraktions-JSON:** gegen Schema validieren; einmal strenger nachfordern; sonst Rohantwort im `raw_log` behalten, betroffene Felder bleiben `fehlt`, **nicht abstürzen**. (Behandlung im LLM-Adapter, P2 — kein eigener Feldstatus. Präzisiert 14.07.2026: hier stand ein Marker `nicht_extrahiert`, den das bewusste 5-Status-Modell nicht kennt.)
- **Bewusst NICHT im MVP (YAGNI → Roadmap):** automatische Widerspruchsauflösung, selbstkorrigierende Extraktion, Off-Topic-Erkennung, numerische Per-Feld-Confidence · LLM-**Retries/Backoff** + Logging verschluckter Validator-Fehler (→ echter LLM-Client; `fehler_fortsetzbar`-Minimalvertrag ist implementiert) · **Thread-Sicherheit des In-Memory-Stores** (MVP läuft sequenziell; Nebenläufigkeit → persistenter StateStore) · Bereinigung der **Wert/Kandidaten-Überlappung** bei UNGUELTIG-Korrektur-Zyklen (kosmetisch, im Test dokumentiert) · aktives **Zurückweisen** von Nachrichten nach Gate 0 (fertige Session antwortet idempotent; Reject-Semantik → Transportschicht).

### B5. Test-Strategie

- **Fake-LLM** mit aufgezeichneten Extraktions-Fällen → der Kern ist testbar **ohne** echte API-Aufrufe und ohne den Umweg über n8n.
- **Reine-Logik-Module** (Confidence-Check, Dialog-Manager-Policy, State-Store-Übergänge, Merge-Regel) → Unit-Tests mit hoher Abdeckung, kein LLM.
- **Extractor** → gegen aufgezeichnete Transkript-Fixtures (Fake-LLM liefert feste strukturierte Ausgabe).
- **Naht-Test (Generik):** zwei **bewusst unterschiedliche** Spielzeug-Use-Case-Pakete durchspielen. Muss der Kern dafür auf einen Use-Case-Namen verzweigen, ist die Abstraktion undicht (B6).
- **Robustheit:** Idempotenz (gleiche `message_id` erneut) und Fortsetzbarkeit (Resume nach `FEHLER_FORTSETZBAR`).

### B6. Generik-Naht: das Use-Case-Paket

Die Plug-Stelle ist **mehr als Schema + Fragetexte**. Sie ist ein **deklaratives Use-Case-Paket**:
- Zielfelder + Typen
- Pflicht-Bedingungen + Validatoren
- Feld-Abhängigkeiten
- Abschlussregeln (wann ist „fertig")
- Retry-Policy
- Frage-Leitfaden

**Ehrliche Grenze:** Das Versprechen ist **nicht** „der Kern wird nie angefasst". Realistisch: **stabile Orchestrierung + Erweiterungs-Schnittstellen**. Für fragebogen-ähnliche Use Cases bleibt Spezialisierung lokal; **echt neue Interaktionsmuster** können Kern-Änderungen erfordern. Der Naht-Test (B5) deckt Lecks früh auf.

### B7. Observability (minimal)

Correlation-ID, Session-ID, Message-ID, Latenz, Retries, Validierungsfehler. **Keine unnötigen Rohdaten loggen** — besonders, weil der PII-Filter erst eine spätere Schicht ist.

### B8. Abgrenzung & Roadmap (der eine Plan)

**Liegt NICHT bei BC1:** DB-Tabellen/Infra/Audit/Verschlüsselung → Platform · Konzept-Übersicht → bestehende Team-Ebene · Vektor-Suche/Embeddings → nicht genutzt · F1 → Offline-Gütemaß, kein Laufzeit-Gate.

**Nachgehalten (lückenlos), je mit Ziel:**
| Thema | Ziel / nächster Schritt | Bezug |
|---|---|---|
| Use Cases definiert | Use-Case-Paket(e) befüllen (B6) | Team-Entscheidung |
| Voice-to-Text + OCR | Eingangs-Schicht vor dem Extractor | #49 |
| PII-Filter | Pre-LLM-Schicht; dann Logging schärfen | #50 |
| Doku-Generator | Profil → menschenlesbare Doku | #52 |
| Baseline-Mapper | Zuordnung zur Baseline (direkte KI-Klassifikation) | #53 |
| BC1→BC2-Vertrag | Schema + Mock final in `contracts/bc1-to-bc2/` (gemeinsam mit BC2 + Platform) | — |
| LLM-Anbieter | EU- vs. Cloud-Entscheidung; bis dahin hinter LLM-Client offen | — |
| Confidence-Semantik | finaler Abgleich mit BC2 (Status + Vollständigkeit; F1 offline) | #95 |

---

*Design-Spec, lokal · zweistufig (Teil A / Teil B) · generisch bis zur Use-Case-Definition · kein Upload ohne ausdrückliche Freigabe.*
