# Abschlussplan BC1 — was bis „fertig" noch fehlt

> **Masterplan, kein Code-Plan.** Er hält lückenlos nach, was in BC1 noch offen ist, in
> welcher Reihenfolge es sinnvoll ist und welche Entscheidung wo hängt. Für jedes Paket
> entsteht — nach explizitem Go — ein eigener Implementierungsplan mit TDD-Schritten,
> so wie bisher (`Implementierungsplan-*.md`). Dieser Plan ersetzt die verstreuten
> Roadmap-Anker der sieben Einzelpläne; sie bleiben als Herkunft verlinkt.
>
> **Stand:** 22.09.2026 (B6 Spalte D3 gebaut, #255; Vertrag 1.2 auf `main`). Davor 12.09.2026 (A1: Vertrag Fassung 1.1 als PR #199; A5 entblockt; C1a/C4 ergänzt). **Spec:** `Design-Spec.md` (MVP-Schnitt, Teil B8 Roadmap) und
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
| **A1** | **Vertrag BC1→BC2** | `contracts/bc1-to-bc2/prozessprofil.schema.json` mit Beispiel — Typen und Einheiten der vier Größen, TP-ID als Anker, `erhebung_id`-Lesart (Klärpunkt **K-L**: die Sicht ist itemweise aktuell, wir speichern eine ID); **Einheit von `menge`** klären — in den Testprofilen steht `executions_per_run` (Fälle je Durchlauf) gleich der Jahreshäufigkeit (Review Rev. 12, 08.09.) **Stand 12.09.:** BC2 hat Fassung 1.0 gegen unsere Zeilen geschnitten (#195, 10.09.); Prüfung gegen den Bau mit unabhängiger Zweitmeinung → Typen/Enums/JSON-Form/`lesen.sql` halten, aber drei Zusagen in unserem Namen stimmten nicht (v. a. „nie NULL bei fertig") → **Fassung 1.1 als PR #199** | PR #199 mergen lassen; BC2-Antwort zu D3 (`step_frequency_per_year`) einarbeiten; die zwei Bau-Zusagen aus 1.1 (D4-Zähltyp, E2-Text) liegen in C1a | BC2 (Merge, D3) | S |
| **A2** | **GitHub-Stand = Realität** | Die Arbeitspakete spiegeln den Bau: #120–#126 sind über PR #129 erledigt → schließen; #48 DoD an die Hybrid-Architektur angleichen (kein Tool-Call, kein Aurelia-Mock, Schema-Validierung → A1); #49/#50/#52/#53 als Stufe B/C einordnen; README um Setup + Start ergänzen (heute nur Struktur) | Richard schließt/kommentiert; README-Absatz aus `SMOKE.md` ableiten | — | S |
| **A3** | **Spalte-zu-Feld-Tabelle + Einseiter** | Als eigenes Artefakt an BC0 (erledigt dort ADR-005 §8 Punkt 96) und für das Team: „Was BC1 fragt und was daraus wird" (26 Pflichtfragen → Spalte) | Aus Task 11 des DB-Profil-Plans extrahieren, in `design/` ablegen | — | S |
| **A4** | **Testdaten reproduzierbar (Rev. 12)** | Das Testdaten-Skript vom 08.09. liegt außerhalb des Repos. Als TDD-Task ins Repo: Test, der die drei Läufe gegen das Gerüst fährt und `fertig` + Kennzeichnung prüft. **Lehre einbauen:** Kennzeichnungsfelder in dieselbe Nachricht wie das letzte Pflichtfeld — der Kern ist danach terminal | Implementierungsplan Rev. 12 schreiben | — | S |
| **A5** | **Auswirkungsprüfung v2.5–v3.1, Schritt D** | **GEMESSEN 12.09.** — `design/Auswirkungspruefung-BC0-v2.5-v3.1.md`: Sichten wortgleich, alle Spalten/Constraints da, **nichts bricht**. Zwei Änderungen nachziehen: `aktiv`-Stilllegung filtern (→ C2), Gerüst-CHECK `erhebung_id` an v2.8 angleichen (→ A5b). Default-Privileg für `bc1` live weg; Gerüst-Simulation als Positivkontrolle behalten, Kommentare in `bc0_geruest.sql:166` und `test_db_fixture.py:50` korrigieren (→ A5b) | **A5b ERLEDIGT 12.09.:** Gerüst-CHECK auf v2.8-Muster, `mandant_rollen`-GRANT, ADP-Kommentare korrigiert (Entscheidung Richard: Positivkontrolle bleibt) — zwei Tests (`test_db_fixture.py`), Suite 465 grün | — | S |
| **A6** | **Dorka-Termin 22.09.** | 2 Folien / 10 Minuten, maximale Transparenz inkl. Minuspunkten — Material ist dieser Plan | Entwurf im Gruppentermin der Vorwoche | Richard | S |

### Stufe B — betriebsfähig

| # | Paket | Ziel | Nächster Schritt | Hängt an | Aufwand |
|---|---|---|---|---|---|
| **B1** | **`bc1.sessions` ins Fundament** | Bis 13.09. legte `PostgresStateStore` die Tabelle selbst an (`CREATE TABLE IF NOT EXISTS`, außerhalb der Sollsignatur, ohne `REVOKE`). **Stand 13.09. — GEBAUT** (`design/Implementierungsplan-B1-Sessions-Fundament.md`, Branch `bc1-b1-sessions-fundament`): eigene Einspiel-Einheit **`sessions.sql`** statt Einbau in `prozessprofil.sql` (Entscheidung Richard: die Dreifallregel kennt nur alles/nichts, live stehen die neun Objekte; Test belegt, dass beide Dateien nach der jeweils anderen Fall 2 bleiben) · Signatur 32 Zeilen, `bc_leser`/`bc2`–`bc4` ohne jedes Recht (gegen den Gerüst-Automatismus gemessen) · **Schlüssel `session_id` allein** (Entscheidung Richard; wie `profil_write_status` und der Store-Vertrag), `company_id` Pflichtspalte mit `ON DELETE CASCADE` (Rohtext stirbt mit dem Mandanten) · Store legt nichts mehr an, Startprüfung mit Verweis auf die Anleitung · Vertragssuite als `bc1_role` · Signatur-Generator ins Repo (`tests/db/signatur_erzeugen.py`). **Befund nebenbei:** der alte Store hätte als `bc1_role` live nie starten können (`CREATE SCHEMA` braucht `CREATE` auf der Datenbank). Zweitmeinung Codex 13.09.: 10 Befunde, alle Critical/Important gefixt und am Container nachgemessen (Signatur 40 Zeilen, Suite 502 grün, Adjudikation im Plan). **LIVE EINGESPIELT 13.09.** (`EINSPIELEN.md` §10): alte Datei Fall 2, `sessions.sql` Fall 1 + Sollsignatur bestätigt + Fall 2, Nachprüfung sauber. **PR #200 gemergt 14.09.** (`0be3144`) — **B1 abgeschlossen**, auf `main` seit 14.09. (#201, `c6b1054`) | — | — | erledigt |
| **B2** | **PII-Filter (#50)** | **GEBAUT 14.09.** (Konzept `design/Konzept-B2-PII-Filter.md`, Plan Fassung 2 `design/Implementierungsplan-B2-PII-Filter.md`): Filter `bc1_core/pii.py` im Kern **vor dem ersten Speichern** — kein Original mehr, weder in `sessions` noch beim Anbieter · Muster für E-Mail/Telefon/IBAN/Adresse + Namen mit Hinweiswort (Anrede, Titel, Kollege/in, Selbstvorstellung), deterministisch, idempotent, nur Standardbibliothek · **kein Mapping-Tresor** (Abweichung von #50: kein Konsument) · **keine Namensliste aus BC0** (ADR-004 R5, live kein Recht auf `ref_personen`) · Systemprompts erklären die Platzhalter · Kennzahl `pii_erkennung` wird gegen die README-Tabelle gehalten (100 % je Muster-Klasse, 0 % nackte Nachnamen = dokumentierte Lücke), 0 Fehltreffer auf 45 PII-freien Sätzen · Zweitmeinung Codex **vor** dem Bau (Plan-Review, 3 Critical/6 Important/3 Minor, alle eingearbeitet) und **nach** dem Bau (Code-Review, 2 Critical/8 Important/3 Minor, alle gefixt — u. a. Anbieter-Ausgaben werden jetzt ebenfalls gefiltert; Adjudikation im Plan) · Suite **535 passed / 4 skipped**. Danach **B7-Logging** darauf aufsetzen **PR #202 gemergt 14.09.** (`2b65af7`), Kommentar in #50 gepostet, auf `main` seit 14.09. (#201, `c6b1054`) | BC0 informieren (BC1 liest keine Namen) — Richard | Richard | erledigt bis auf BC0-Info |
| **B3** | **Deployment** | Dockerfile + `uv lock` (Dependencies sind ungepinnt) + Hosting; **Turn-Claim in der DB** (`SELECT … FOR UPDATE` auf der Session-Zeile — das Transport-Lock greift nur innerhalb eines Prozesses); `/prozesse`-Auth (heute offen); Korrupt-Row-Behandlung (`KorrupterStateError` statt rohem `KeyError`); menschliche Fehlertexte im Chat statt `paket_konflikt` | Hosting-Entscheidung der Gruppe einholen; bis dahin `uvicorn` lokal | Gruppe | M |
| **B4** | **Dienst-Anmeldung an BC0 + Endpunkte** | Anwendungskonto (Rolle `admin`, `POST /api/auth/login`, HttpOnly-Cookie — Klärpunkt K-E beantwortet) im Dienst mitführen; dann `PUT …/zuordnung` (`zuordnung_quelle='interview'`) und `PUT …/status` (`im_interview`) aufrufen. `am_gate` setzt BC0 selbst | Konto von BC0 erhalten (Adresse ist gemeldet); Client mit Cookie-Jar; Test gegen Fake-BC0 | BC0 | M |
| **B5** | **`anfrage_id` beim Interview-Start** | Session an die Anfrage binden (BC0s ADR-006: jeder BC führt `KP-XX.TP-Y` und `(company_id, anfrage_id)`); Interviewpartner über `v_anfrage_steller` (Leserecht erbeten) | Wartet auf ADR-006; dann Vorbelegung A1/A2 aus `ref_anfragen` | BC0 | S |
| **B6** | **Spalte `step_frequency_per_year` (#255)** | BC2 hat D3 am 20.09. gebunden (Vertrag 1.2, Invariante I8); `lesen.sql` fragt die Spalte ab und brach am Bestand — BC2 las über den Vertragsweg **nichts** (#249/#255). Simeon 21.09.: „Richard baut die Spalte." **GEBAUT 22.09.** (Branch `bc1-d3-spalte`): Spalte numeric im Wertebereichs-CHECK + Sollsignatur neu (177 Zeilen) · Migrations-Einheit `prozessprofil_d3.sql` (M0–M3, mit `prozessprofil.sql` in EINER Transaktion, Nachweis = Fall 2; Vorbedingung: kein gültiger JSON-D3-Wert im Bestand) · Writer liest D3 · Fixture in Betriebsreihenfolge · `EINSPIELEN.md` §2/§11. **Codex-Zweitmeinung 22.09.: 0 Critical, 2 Important (beide gefixt + Test: JSON-D3-Vorbedingung; Fall-3-Rollback in einer Transaktion), 5 Minor (2 gefixt: Bestandszeilen-Test, Doku; 3 vertagt → Kleinpunkte).** `lesen.sql` wörtlich im Container gegen das neue Schema gemessen (parst, liefert die Spalte). **LIVE EINGESPIELT 22.09.** (`EINSPIELEN.md` §11: Vorprüfung Fall 3 → M1 + Fall 2 → M2 + Fall 2 → `sessions.sql` Fall 2 → Nachprüfung A–D, `lesen.sql` liefert 3 Profile mit 20 Spalten). | Kommentar in #255, BC2 um `bc2_role`-Gegenprobe bitten → PR nach `main` | Richard (Live-Lauf), Termin vor Durchstich KW 40 (#206) | S |

### Stufe C — Spec-vollständig (selektiv)

| # | Paket | Ziel | Nächster Schritt | Hängt an | Aufwand |
|---|---|---|---|---|---|
| **C1** | **Rollen-Lesepfad + `profil_rollen`** | Rollen als **Auswahl** aus `mandant_rollen` statt Freitext; `profil_rollen` befüllen; `process_owner_rolle_id` setzen; **`zeitanteil_pct` erheben** — das ist der `fte_anteil`, den BC2 in #184 will und den heute niemand liefert. Vorher: Eigner/Sponsor 1:n (`v_prozesse_lesen`) gegen die eine Spalte prüfen. **C1a (vorgezogen, ein Lauf = Version 3 der Testprofile):** Owner-Auswahl aus `mandant_rollen` (`bc1_role` liest sie, gemessen 12.09.: 6 Zeilen) → `process_owner_rolle_id` setzen · **D4 auf reinen Zähl-Typ** ohne Perioden-Normalisierer (Vertrag 1.1) · **E2-Fragetext „je Durchlauf"** (Vertrag 1.1) · Testprofile korrigieren: `executions_per_run` fachlich (=1), D1/E1 je KP konsistent (heute widersprechen sich `KP-06.TP-1` und `TP-2`) — die Zusage „Version 3" steht öffentlich in #195. **C1b:** `profil_rollen` + `zeitanteil_pct` — erst wenn BC0/BC2 klären, ob `fte_anteil` gebraucht wird | C1a: Simeons Antwort zu Owner 1:n vs. 1:1 (Sammelliste) abwarten, dann Implementierungsplan | BC0-Rechtekonzept #148 (Spaltenhoheit, teils umgesetzt); C1b: BC0/BC2 | M |
| **C2** | **Etappe-2-Fragen** | Nachfass-Paket für Lücken (Klartext, keine Skalen) · Kanten-Art „Was fließt zwischen den beiden?" (BC0-Endpunkt kommt) · strukturierte System-Erfassung (S-NN als Auswahl) · **`aktiv` auswerten:** stillgelegte Prozesse/Teilprozesse/Systeme (`aktiv=false`, BC0 v2.2) sind weder interviewbar noch als S-NN gültig — heute ungefiltert (A5, 12.09.); **BC0 zieht den Filter in die Sichten (Simeon 14.09.) — C2 wartet darauf** · B6 `process_category`-Umbau (braucht `ref_prozesse`-Lesepfad + `SCHEMA_VERSION`-Erhöhung, BC0 informieren) | Je Punkt ein kleines Paket; Reihenfolge nach Bedarf der Use Cases | — | M |
| **C3** | **Spätere Schichten** | Doku-Generator (#52: Prozessdoku aus dem Profil) · Baseline-Mapper (#53: Abgleich mit BC0-Reifegrad) · Voice/OCR (#49: Eingangsschicht vor dem Extractor) | Erst wenn Stufe B steht und das Team den Bedarf bestätigt — jede Schicht dockt am Kern an, ohne ihn zu ändern | Team | L |
| **C4** | **Härtung, bewusst vertagt** | **K-K:** der Freeze prüft die Erhebung nicht nach (Draft angelegt → Erhebungen verworfen → Zeile `fertig` mit verworfener ID; gemessen) · **K-M:** Eingaben < 0,0001 werden zurückgewiesen (`str(float)` → Exponent) — fachlich irrelevant · Outbox/Reconciler nur, falls der 503-Weg operativ nicht reicht · `SECURITY DEFINER`-Prüfpfad für die S-NN-Restlücke · automatische Auflösung verwaister Drafts (K5 bleibt manuell) · **Rechengrößen unaufgebbar?** Heute wird ein Profil nach zwei Nachfragen auch ohne D1/D4/E1/E2 `fertig` (Spalte NULL, `ungeloeste_felder` sagt welche) — Vertrag 1.1 sagt das ehrlich, BC2 hält NULL aus; die vier `identitaetskritisch` zu machen wäre eine Spec-Entscheidung, die Interviews bei sturen Antworten blockiert · **strukturierter Testdaten-Marker** statt Präfix-Konvention `Testdaten ` in `open_remarks` (Review 12.09.) | Nur auf konkreten Anlass | — | S je Punkt |

### Nachgehaltene Kleinpunkte (aus allen Plänen, damit nichts verloren geht)

- Wert/Kandidaten-Überlappung bei UNGUELTIG-Korrektur-Zyklen — kosmetisch, im Test gepinnt (MVP-Kern).
- Prompt-Feinschliff der Adapter (Feldtypen, Mehrsprachigkeit, Beispiele) — wenn echte Pakete stabil sind (P2).
- Zwischenstands-Updates des Profil-JSON je Turn — nach Etappe 2 bewerten, YAGNI (DB-Profil).
- **Dauerregel:** kein Fremdschlüssel von `bc1.*` auf `prozess_personen`/`ref_personen` — BC0 schreibt sie mandantenweit neu (DB-Profil).
- **Dauerregel (15.09., zugesichert an BC0):** `bc1_role` braucht **SELECT auf `public.companies`** — der Freeze-Trigger liest die Tabelle bei BC0s Löschkaskade (`DELETE FROM companies`) mit den Rechten von `bc1_role`; ohne das Recht bricht BC0s DSGVO-Löschung. Gemessen 12.09.: das SELECT kommt über `bc_leser` (Mitgliedschaft), direkt hat `bc1_role` nur `REFERENCES`. Kein BC1-Artefakt darf diesen Weg voraussetzungslos kappen; BC0 sagt vor dem Aufräumen der direkten Grants (Etappe 4c), welcher Weg bleibt. Suite: `test_kaskade_laeuft_auch_unter_echter_rollentrennung`, `test_kaskade_raeumt_die_sitzung_auch_unter_rechtelosem_loeschkonto`.
- Bitkom-30-Items im Chat — **entfällt endgültig** (Team-Beschluss, von BC0 angenommen); Bewertung bleibt im Self-Rating.
- Die Produktfrage „wer bewertet die übrigen Teilprozesse" liegt außerhalb des Projekts (Roadmap-Anker für ein Produkt).
- **D3 `step_frequency_per_year`** — **gebunden** (BC2, 20.09., Vertrag 1.2, Invariante I8). Die Bedingung „falls binden: Schema-Ergänzung" ist mit **B6** eingelöst (Spalte + Migration, 22.09.); der Writer liest das Feld jetzt in die Spalte.
- **Aus dem Codex-Review zu B6 (22.09.) vertagt, je mit Ziel:** (1) Signatur-Determinismus — `pg_get_constraintdef`-Text hängt von `quote_all_identifiers` ab; alle drei Einspiel-Einheiten setzen nur `search_path`. Ziel **C4** (Signatur-Härtung): `SET LOCAL quote_all_identifiers = off` in allen Einheiten gleichzeitig, nicht nur in einer. (2) Durchgehender Writer-Test für D3 (normalisierter Wert → INSERT → Abschluss → Freeze weist UPDATE ab); Auslöser: **C1a/Version 3**, sobald D3 im Interview tatsächlich gesetzt wird — heute läuft D3 denselben generischen Pfad wie `frequency_per_year`. (3) Vertragsartefakte `contracts/bc1-to-bc2/`: D3 fehlt in `required`, Beispiel-Export ohne den Schlüssel, README Z. 62 „17 Felder" (sind 18) und „BC1 musste nichts ändern" (Z. 233 + Schema-Beschreibung) sind überholt — **mit BC2 in #255 klären**, gemeinsame Datei, kein Alleingang.
- **Merge nach `main`:** unser Bau liegt nur auf `bc1-db-profil-fundament`; BC2 hat gegen Branch + DB-Zeilen geschnitten. **Gemessen 14.09. — kein Kleinpunkt:** merge-base ist der 26.06., 102 BC1-Dateien unterscheiden sich, 37 Konflikte (36 add/add in BC1 + `.gitignore`); `main` hat für BC1 nichts, was nicht schon in unserer Historie liegt (je Konfliktdatei belegt: main-Blob = früherer eigener Stand, `git log --find-object`). **Erledigt 14.09.:** `origin/main` in den Bau-Zweig gemergt — überall die BC1-Fassung, `.gitignore` vereinigt, BC1 byteidentisch, Suite 502/4. **Erledigt 14.09.:** PR #201 per **Squash** gemergt (`c6b1054`) — das Ruleset `protect-main` verlangt lineare Historie (Repo-Konvention); die Bau-Historie bleibt auf dem getaggten Bau-Zweig `bc1-bau-2026-09-14` erreichbar. Ab jetzt Feature-Zweige ab `main`.
- **Default-Privileg auf `public`:** jede neue BC0-Tabelle ist automatisch für `bc1_role` und `bc_leser` lesbar (gemessen 12.09.) — BC0 fragen, ob gewollt (Sammelliste); für uns kein Handlungsbedarf.
- **Signatur-Sicht liegt jetzt zweimal im Repo** (`prozessprofil.sql` 0b, `sessions.sql` 0b, seit B1 13.09.) — bewusst, solange nur zwei Einheiten eine Sollsignatur tragen; `prozessprofil_d3.sql` (B6) hat keine (sie vergleicht nur Spalte + CHECK, die volle Prüfung macht `prozessprofil.sql` in derselben Transaktion). **Bei einer dritten Signatur** wird die Sicht in einen Generator gezogen, nicht vorher (YAGNI). `sessions.sql` prüft die `mitglied|`-Kanten seit dem Review 13.09. selbst; Funktionen prüft nur `prozessprofil.sql`.
- **Aus der Zweitmeinung zu B1 (Codex, 13.09.) deferiert, Ziel C4:** (a) **Inventarprüfung fremder Objekte in `bc1`** — eine View oder `SECURITY DEFINER`-Funktion, die auf `bc1.prozessprofil`/`bc1.sessions` zeigt, sieht keine der beiden Signaturen (bekannt seit 03.09., von Codex erneut benannt); Auslöser: Deployment in eine gehostete Umgebung (B3). (b) **`prozessprofil.sql` signiert die RI-Trigger der referenzierten Seite nicht** (`sessions.sql` tut es seit 13.09.); nachziehen bei der nächsten ohnehin nötigen Signatur-Neuerzeugung von `prozessprofil.sql` — nicht vorher, die Datei bleibt byteidentisch. (c) **Generator-Parser kürzt mehrzeilige Signaturwerte still** — heute gibt es keine (Katalogtexte sind einzeilig); beheben, sobald eine Signaturart mehrzeilig wird.
- **Alte Generator-Kopie außerhalb des Repos** (`AutoCoE_Projekt/signatur-erzeugen.py`) ist seit B1 durch `tests/db/signatur_erzeugen.py` ersetzt — löschen (Richard, seine Datei).
- **Aus B2 (14.09.) vertagt, je mit Auslöser:** NER für nackte Nachnamen (Auslöser: gemessene Fehlrate in echten Turns; das Testset hält die Lückenklasse bei 0 %) · Platzhalter als alleiniger Feldwert (z. B. Owner-Rolle = `[Person A]`) als ungültig behandeln und nachfragen (C2-Nähe; Auslöser: Auftreten in Testläufen) · n8n speichert Ausführungsdaten mit der Chat-Eingabe, bevor der Dienst filtert (B3/Hosting: Ausführungsdaten nicht speichern oder kurz aufbewahren) · Straßen ohne Straßenwort („Am Alten Markt 3") und Kartennummern (Auslöser: erster Treffer in echten Läufen) · Konsistenz der Platzhalter über Turns (Auslöser: Profile werden dadurch unlesbar).
- **Befunde BC0 zu PR #201 (Simeon, 14.09., kein Einwand, ADR-003 eingehalten):** (1) Sechs FKs ohne `ON DELETE` machen `process_id`/`sub_process_id`/`erhebung_id`/`rolle_id` in BC0 faktisch unveränderlich — Umbenennen/Löschen in der Prozesslandkarte verbietet jetzt die Datenbank; BC0 nimmt „Stilllegung statt Löschen" ins ADR. Für uns: Kontext, nichts zu bauen. (2) BC0s DSGVO-Löschkaskade (`DELETE FROM companies` → `bc1.sessions`/`bc1.prozessprofil`) hängt am Freeze-Trigger, der `public.companies` **als `bc1_role`** liest — **BC0 bittet um ausdrückliche Zusicherung, dass `bc1_role` das SELECT auf `public.companies` behält.** **Dauerregel seit 15.09. (Brief an BC0), eigener Punkt oben;** Hinweis in `EINSPIELEN.md` §1 steht. Container-Test, der die Kaskade ohne das Recht laut scheitern sieht: vertagt nach C4, Auslöser nächste Änderung an `sessions.sql`/`prozessprofil.sql`. (3) `aktiv`-Filter gehört in BC0s Sichten (`v_prozesse_lesen`, `v_bewertung_aktuell`); BC0 zieht ihn dorthin — **C2 wartet darauf** und entscheidet dann, ob der eigene Filter zusätzlich nötig ist. (4) Default-Privilegien in `public`: BC0 entscheidet diese Woche, Antwort im PR-Thread. Nebenbei: BC0 v3.2 (`b0786ce`) ändert nur den Ruf an BC2 — A5-Prüfung bleibt gültig. **Merge von #201:** Ruleset `protect-main` verlangt lineare Historie (Squash/Rebase); Merge-Commit nur mit Ausnahme durch einen Org-Owner.
- **Normalisierung ist jetzt Vertragsbestandteil** (Vertrag 1.1, Abschnitt „Normalisierung der Zahlen"): Perioden-/Einheitenlogik in `feldtypen.py` nicht mehr ohne BC2-Hinweis ändern.

### Entscheidungen, die den Plan bewegen

| Entscheidung | Optionen | Empfehlung | Wer |
|---|---|---|---|
| **Zielstufe** | A · B · C | **B bis November**, C1 vorgezogen | Richard mit Team |
| **Reihenfolge Stufe B** | B1→B2→B3 oder B3 zuerst („erst mal deployen") | **B1→B2→B3** — nie Rohtext ohne PII-Konzept in eine gehostete Umgebung | Richard |
| **Hosting** | Gruppen-Server · Cloud · lokal bleiben | offen — Team-Frage, blockiert B3 | Gruppe |
| **Sitzungsschlüssel** | `session_id` allein · `(company_id, session_id)` | **`session_id` allein — so entschieden 13.09. (B1):** passt zu `profil_write_status` und `StateStore.load(session_id)`; `company_id` ist Pflichtspalte mit Kaskade. Ehrlich: n8n vergibt die ID heute schon clientseitig; solange ein Dienst je Mandant läuft, kollidiert nichts. Verbundschlüssel bleibt Roadmap-Anker (DB-Profil-Plan, Nachtrag 08.09.) mit Auslöser „zweite Dienstinstanz auf derselben Datenbank" | Richard ✔ |
| **Stufe C: was davon** | alle vier Schichten · nur Rollen + Doku-Generator | nach Use-Case-Bedarf; Voice/OCR zuletzt | Team |
| **Rechengrößen unaufgebbar** | aufgebbar lassen (heute) · `identitaetskritisch` | **aufgebbar lassen** — BC2 hält NULL aus, Vertrag 1.1 sagt es ehrlich; **so entschieden 12.09.** | Richard |
| **`executions_per_run`-Korrektur** | Version 3 sofort · mit C1a in einem Lauf | **mit C1a** — ein Lauf, alle Korrekturen; Version 3 ist in #195 ohne Datum zugesagt | Richard |

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
