# Abschlussplan BC1 — was bis „fertig" noch fehlt

> **Masterplan, kein Code-Plan.** Er hält lückenlos nach, was in BC1 noch offen ist, in
> welcher Reihenfolge es sinnvoll ist und welche Entscheidung wo hängt. Für jedes Paket
> entsteht — nach explizitem Go — ein eigener Implementierungsplan mit TDD-Schritten,
> so wie bisher (`Implementierungsplan-*.md`). Dieser Plan ersetzt die verstreuten
> Roadmap-Anker der sieben Einzelpläne; sie bleiben als Herkunft verlinkt.
>
> **Stand:** 08.09.2026. **Spec:** `Design-Spec.md` (MVP-Schnitt, Teil B8 Roadmap) und
> `../architektur/BC1_Systemarchitektur.md` (spätere Schichten #49/#50/#52/#53).

**Ziel:** Ein gemeinsames Verständnis, was „fertig" für BC1 bedeutet — in drei Stufen —
und ein Pfad dorthin, bei dem nichts Aufgeschobenes verloren geht.

**Rahmen (gilt für jedes Paket):** pro GitHub-Issue ein explizites Go · TDD mit
tdd-guard, nie umgangen · generisch bleiben, Use-Case-Spezifika ins Paket · kein Push ins
öffentliche Repo ohne Vertraulichkeits-Check · DSGVO ist Pflicht und wird in Stufe B scharf
· kein LLM-Anbieter vorgegeben (drei Adapter existieren) · Sprache Deutsch.

---

## Big Picture

### Wo BC1 heute steht (verifiziert, nicht behauptet)

Etappe 1 ist **inhaltlich fertig und im Ziel belegt**: Der Text-Chat-Interviewer führt ein
Gespräch, extrahiert, fragt nach, liefert ein typisiertes Profil und schreibt es über den
regulären Weg in `bc1.prozessprofil`. Die DDL ist am 08.09. in die Supabase eingespielt
(Fall 1, Sollsignatur bestätigt, zweiter Lauf Fall 2), das letzte Deploy-Gate ist
gefallen, drei Use-Case-Profile stehen in der Datenbank, BC2 kann sie lesen.

**Was fehlt, ist nicht der Chatbot — es ist der Betrieb drumherum und die DSGVO-Schicht.**
Nichts davon ist neu: alles stand als Roadmap-Anker in den Einzelplänen. Hier ist es
zum ersten Mal an einem Ort.

### Drei Stufen von „fertig" — die Zielwahl ist eine Entscheidung

| Stufe | Bedeutet | Wofür es reicht |
|---|---|---|
| **A — Etappe 1 abgeschlossen** | Vertrag mit BC2 steht, Testdaten reproduzierbar im Repo, GitHub-Stand stimmt mit der Realität überein, Doku vollständig | Gate-0-Nachweis, Dorka-Termin 22.09., Übergabe an BC2 |
| **B — betriebsfähig** | Der Dienst läuft außerhalb eines Entwickler-Laptops, mit echten Nutzern, DSGVO-konform: Sessions-Tabelle signiert, PII-Filter, Deployment, Auth, mehrere Worker | Echter Einsatz beim Mandanten |
| **C — Spec-vollständig** | Die späteren Schichten aus der Systemarchitektur: Rollen, Doku-Generator, Baseline-Mapper, Voice/OCR, Etappe-2-Fragen | Die volle BC1-Vision |

**Empfehlung:** Stufe A **jetzt** (sie ist klein und hängt zu zwei Dritteln an anderen
Teams), Stufe B als Ziel für das Novemberziel der Gruppe, Stufe C **selektiv** nach
Team-Priorität — nicht alles davon braucht das Projekt. Die eine Ausnahme in C, die
früher kommen sollte, ist der **Rollen-Lesepfad (C1)**: Er schließt die einzige Lücke,
die BC2 heute beim Rechnen spürt (`fte_anteil`).

### Reihenfolge und warum

1. **A zuerst**, weil Vertrag (A1) und GitHub-Abgleich (A2) klein sind und alle anderen
   Teams davon abhängen, was sie von uns lesen dürfen.
2. **B1 (Sessions-Tabelle) vor jedem echten Chatbot-Start** gegen die Supabase — sie
   entstünde sonst unsigniert beim ersten Start und trüge Interview-Rohtext.
3. **B2 (PII) vor B3 (Deployment)**, weil Logging und Auth wissen müssen, was sensibel ist.
4. **C1 (Rollen) vor dem Rest von C**, aus dem Grund oben.

---

## Technischer Teil

Aufwand ist eine **Schätzung in Arbeitssitzungen** (S = 1, M = 2–3, L = mehr oder
unklar) und wird beim jeweiligen Implementierungsplan präzisiert.

### Stufe A — Etappe 1 abschließen

| # | Paket | Ziel | Nächster Schritt | Hängt an | Aufwand |
|---|---|---|---|---|---|
| **A1** | **Vertrag BC1→BC2** | `contracts/bc1-to-bc2/prozessprofil.schema.json` mit Beispiel — Typen und Einheiten der vier Größen, TP-ID als Anker, `erhebung_id`-Lesart (Klärpunkt **K-L**: die Sicht ist itemweise aktuell, wir speichern eine ID); **Einheit von `menge`** klären — in den Testprofilen steht `executions_per_run` (Fälle je Durchlauf) gleich der Jahreshäufigkeit (Review Rev. 12, 08.09.) | BC2 schneidet gegen die Zeilen vom 08.09. (#184, v3.0 in #187); BC1 liefert Spalte-zu-Feld-Tabelle + `pruef.sql`-Muster als Eingang | BC2 + Platform (CODEOWNERS) | S |
| **A2** | **GitHub-Stand = Realität** | Die Arbeitspakete spiegeln den Bau: #120–#126 sind über PR #129 erledigt → schließen; #48 DoD an die Hybrid-Architektur angleichen (kein Tool-Call, kein Aurelia-Mock, Schema-Validierung → A1); #49/#50/#52/#53 als Stufe B/C einordnen; README um Setup + Start ergänzen (heute nur Struktur) | Richard schließt/kommentiert; README-Absatz aus `SMOKE.md` ableiten | — | S |
| **A3** | **Spalte-zu-Feld-Tabelle + Einseiter** | Als eigenes Artefakt an BC0 (erledigt dort ADR-005 §8 Punkt 96) und für das Team: „Was BC1 fragt und was daraus wird" (26 Pflichtfragen → Spalte) | Aus Task 11 des DB-Profil-Plans extrahieren, in `design/` ablegen | — | S |
| **A4** | **Testdaten reproduzierbar (Rev. 12)** | Das Testdaten-Skript vom 08.09. liegt außerhalb des Repos. Als TDD-Task ins Repo: Test, der die drei Läufe gegen das Gerüst fährt und `fertig` + Kennzeichnung prüft. **Lehre einbauen:** Kennzeichnungsfelder in dieselbe Nachricht wie das letzte Pflichtfeld — der Kern ist danach terminal | Implementierungsplan Rev. 12 schreiben | — | S |
| **A5** | **Auswirkungsprüfung v2.5–v3.0, Schritt D** | `tests/db/bc0_geruest.sql` gegen den Live-Stand — die gefährlichste Stelle: die Suite bleibt grün, während BC0 wegläuft. Dabei entscheiden: die Gerüst-Simulation des inzwischen entfernten Default-Privilegs behalten (Positivkontrolle) oder angleichen | Braucht BC0s v3.0-Dateien auf `main` (erbeten am 08.09.) | BC0 | S–M |
| **A6** | **Dorka-Termin 22.09.** | 2 Folien / 10 Minuten, maximale Transparenz inkl. Minuspunkten — Material ist dieser Plan | Entwurf im Gruppentermin der Vorwoche | Richard | S |

### Stufe B — betriebsfähig

| # | Paket | Ziel | Nächster Schritt | Hängt an | Aufwand |
|---|---|---|---|---|---|
| **B1** | **`bc1.sessions` ins Fundament** | Heute legt `PostgresStateStore` die Tabelle selbst an (`CREATE TABLE IF NOT EXISTS`, außerhalb der Sollsignatur, ohne `REVOKE`). Ziel: Tabelle in `prozessprofil.sql`, signiert, `bc_leser` ausdrücklich verneint, Test **als `bc1_role`**; der Store legt nichts mehr an. Zugleich entscheiden: Schlüssel `(company_id, session_id)` statt `session_id` allein — relevant, sobald die `session_id` clientseitig vergeben wird | Implementierungsplan; Signatur neu erzeugen; Einspielen als Fall 1 der neuen Tabelle | — | S–M |
| **B2** | **PII-Filter (#50)** | Pre-LLM-Schicht: personenbezogene Angaben erkennen und ersetzen, **bevor** Text an einen Anbieter geht; Ablage der Rohdaten klären (Interview-Rohtext liegt in `sessions`). Danach **B7-Logging** darauf aufsetzen (Correlation-ID, Latenz, Validierungsfehler — keine Rohdaten) | Konzept zuerst: was wird erkannt (Namen, Mail, Telefon, freie Nennungen), womit (Regex zuerst, LLM nur für Restfälle), wo bleibt das Original | — | M |
| **B3** | **Deployment** | Dockerfile + `uv lock` (Dependencies sind ungepinnt) + Hosting; **Turn-Claim in der DB** (`SELECT … FOR UPDATE` auf der Session-Zeile — das Transport-Lock greift nur innerhalb eines Prozesses); `/prozesse`-Auth (heute offen); Korrupt-Row-Behandlung (`KorrupterStateError` statt rohem `KeyError`); menschliche Fehlertexte im Chat statt `paket_konflikt` | Hosting-Entscheidung der Gruppe einholen; bis dahin `uvicorn` lokal | Gruppe | M |
| **B4** | **Dienst-Anmeldung an BC0 + Endpunkte** | Anwendungskonto (Rolle `admin`, `POST /api/auth/login`, HttpOnly-Cookie — Klärpunkt K-E beantwortet) im Dienst mitführen; dann `PUT …/zuordnung` (`zuordnung_quelle='interview'`) und `PUT …/status` (`im_interview`) aufrufen. `am_gate` setzt BC0 selbst | Konto von BC0 erhalten (Adresse ist gemeldet); Client mit Cookie-Jar; Test gegen Fake-BC0 | BC0 | M |
| **B5** | **`anfrage_id` beim Interview-Start** | Session an die Anfrage binden (BC0s ADR-006: jeder BC führt `KP-XX.TP-Y` und `(company_id, anfrage_id)`); Interviewpartner über `v_anfrage_steller` (Leserecht erbeten) | Wartet auf ADR-006; dann Vorbelegung A1/A2 aus `ref_anfragen` | BC0 | S |

### Stufe C — Spec-vollständig (selektiv)

| # | Paket | Ziel | Nächster Schritt | Hängt an | Aufwand |
|---|---|---|---|---|---|
| **C1** | **Rollen-Lesepfad + `profil_rollen`** | Rollen als **Auswahl** aus `mandant_rollen` statt Freitext; `profil_rollen` befüllen; `process_owner_rolle_id` setzen; **`zeitanteil_pct` erheben** — das ist der `fte_anteil`, den BC2 in #184 will und den heute niemand liefert. Vorher: Eigner/Sponsor 1:n (`v_prozesse_lesen`) gegen die eine Spalte prüfen | Lesepfad wie `bc0_lesepfade.py`, Feldtyp `AUSWAHL` aus Kontext (Muster: `focus_step`), Writer-Erweiterung mit Kaskade-Test | BC0-Rechtekonzept #148 (Spaltenhoheit, teils umgesetzt) | M |
| **C2** | **Etappe-2-Fragen** | Nachfass-Paket für Lücken (Klartext, keine Skalen) · Kanten-Art „Was fließt zwischen den beiden?" (BC0-Endpunkt kommt) · strukturierte System-Erfassung (S-NN als Auswahl) · B6 `process_category`-Umbau (braucht `ref_prozesse`-Lesepfad + `SCHEMA_VERSION`-Erhöhung, BC0 informieren) | Je Punkt ein kleines Paket; Reihenfolge nach Bedarf der Use Cases | — | M |
| **C3** | **Spätere Schichten** | Doku-Generator (#52: Prozessdoku aus dem Profil) · Baseline-Mapper (#53: Abgleich mit BC0-Reifegrad) · Voice/OCR (#49: Eingangsschicht vor dem Extractor) | Erst wenn Stufe B steht und das Team den Bedarf bestätigt — jede Schicht dockt am Kern an, ohne ihn zu ändern | Team | L |
| **C4** | **Härtung, bewusst vertagt** | **K-K:** der Freeze prüft die Erhebung nicht nach (Draft angelegt → Erhebungen verworfen → Zeile `fertig` mit verworfener ID; gemessen) · **K-M:** Eingaben < 0,0001 werden zurückgewiesen (`str(float)` → Exponent) — fachlich irrelevant · Outbox/Reconciler nur, falls der 503-Weg operativ nicht reicht · `SECURITY DEFINER`-Prüfpfad für die S-NN-Restlücke · automatische Auflösung verwaister Drafts (K5 bleibt manuell) | Nur auf konkreten Anlass | — | S je Punkt |

### Nachgehaltene Kleinpunkte (aus allen Plänen, damit nichts verloren geht)

- Wert/Kandidaten-Überlappung bei UNGUELTIG-Korrektur-Zyklen — kosmetisch, im Test gepinnt (MVP-Kern).
- Prompt-Feinschliff der Adapter (Feldtypen, Mehrsprachigkeit, Beispiele) — wenn echte Pakete stabil sind (P2).
- Zwischenstands-Updates des Profil-JSON je Turn — nach Etappe 2 bewerten, YAGNI (DB-Profil).
- **Dauerregel:** kein Fremdschlüssel von `bc1.*` auf `prozess_personen`/`ref_personen` — BC0 schreibt sie mandantenweit neu (DB-Profil).
- Bitkom-30-Items im Chat — **entfällt endgültig** (Team-Beschluss, von BC0 angenommen); Bewertung bleibt im Self-Rating.
- Die Produktfrage „wer bewertet die übrigen Teilprozesse" liegt außerhalb des Projekts (Roadmap-Anker für ein Produkt).

### Entscheidungen, die den Plan bewegen

| Entscheidung | Optionen | Empfehlung | Wer |
|---|---|---|---|
| **Zielstufe** | A · B · C | **B bis November**, C1 vorgezogen | Richard mit Team |
| **Reihenfolge Stufe B** | B1→B2→B3 oder B3 zuerst („erst mal deployen") | **B1→B2→B3** — nie Rohtext ohne PII-Konzept in eine gehostete Umgebung | Richard |
| **Hosting** | Gruppen-Server · Cloud · lokal bleiben | offen — Team-Frage, blockiert B3 | Gruppe |
| **Sitzungsschlüssel** | `session_id` allein · `(company_id, session_id)` | mandantenweit, sobald n8n die ID vergibt (B1) | Richard |
| **Stufe C: was davon** | alle vier Schichten · nur Rollen + Doku-Generator | nach Use-Case-Bedarf; Voice/OCR zuletzt | Team |

### Was dieser Plan ausdrücklich nicht ist

Kein Code-Plan. Jedes Paket bekommt nach Go seinen eigenen Implementierungsplan mit
Tests, Dateien und Commit-Grenzen — in der Tiefe, die die bisherigen Pläne haben. Wer hier
Code-Schritte sucht, sucht am falschen Ort; wer wissen will, **was noch fehlt und warum in
dieser Reihenfolge**, ist richtig.

---

## Selbstprüfung (vom Autor)

- **Spec-Abdeckung:** Design-Spec B8 (Roadmap) → A1, C3 · Systemarchitektur „spätere
  Schichten" #49/#50/#52/#53 → B2, C3 · P2-Roadmap-Anker (Deployment, Turn-Claim, Auth,
  Lockfile, Korrupt-Row, Fehlertexte, Logging) → B3, B2 · MVP-Kern-Anker (Vertrag) → A1 ·
  DB-Profil „NICHT baut" (alle 19 Zeilen) → A4, B1, B4, B5, C1, C2, C4, Kleinpunkte ·
  Klärpunkte K-K/K-L/K-M → C4, A1, C4 · #48-DoD → A2.
- **Offen benannt:** Aufwände sind Schätzungen; Hosting ist die eine Entscheidung, die von
  außen kommt und Stufe B blockieren kann; C3 ist bewusst grob, weil der Bedarf nicht feststeht.
- **Vertraulichkeit:** enthält keine Zugänge, keine internen Absprachen, keine
  personenbezogenen Daten; Mandant NoroAI ist bereits öffentlich dokumentiert.
