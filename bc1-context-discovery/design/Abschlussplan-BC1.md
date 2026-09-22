# Abschlussplan BC1 — was bis „fertig" noch fehlt

> **Masterplan, kein Code-Plan.** Er hält lückenlos nach, was in BC1 noch offen ist, in
> welcher Reihenfolge es sinnvoll ist und welche Entscheidung wo hängt. Für jedes Paket
> entsteht — nach explizitem Go — ein eigener Implementierungsplan mit TDD-Schritten,
> so wie bisher (`Implementierungsplan-*.md`). Dieser Plan ersetzt die verstreuten
> Roadmap-Anker der sieben Einzelpläne; sie bleiben als Herkunft verlinkt.
>
> **Stand:** 22.09.2026 abends (Stufe A abgeschlossen bis auf GitHub-Kosmetik; B6 und A7 auf
> `main`; Arbeitsteilung Richard/Philipp; kritischer Pfad Durchstich KW 40, #206; BC0-Papier „Vom Anliegen zum Paket" eingearbeitet → B5). Davor
> 22.09. morgens (B6), 12.09. (A1 Fassung 1.1, A5). **Spec:** `Design-Spec.md` (MVP-Schnitt,
> Teil B8 Roadmap) und `../architektur/BC1_Systemarchitektur.md` (spätere Schichten
> #49/#50/#52/#53).

**Ziel:** Ein gemeinsames Verständnis, was „fertig" für BC1 bedeutet — in drei Stufen —
und ein Pfad dorthin, bei dem nichts Aufgeschobenes verloren geht.

**Rahmen (gilt für jedes Paket):** pro GitHub-Issue ein explizites Go · TDD mit
tdd-guard, nie umgangen · generisch bleiben, Use-Case-Spezifika ins Paket · kein Push ins
öffentliche Repo ohne Vertraulichkeits-Check · DSGVO ist Pflicht und wird in Stufe B scharf
· kein LLM-Anbieter vorgegeben (drei Adapter existieren) · Sprache Deutsch.

---

## Big Picture

### Wo BC1 heute steht (verifiziert, nicht behauptet)

Etappe 1 ist **fertig und im Ziel belegt**: Der Text-Chat-Interviewer führt ein Gespräch,
extrahiert, fragt nach, liefert ein typisiertes Profil und schreibt es über den regulären
Weg in `bc1.prozessprofil`. Die DDL ist seit dem 08.09. in der Supabase, drei Use-Case-Profile
stehen in der Datenbank, BC2 liest sie über den Vertragsweg. Seit dem 22.09. zusätzlich:
der Vertrag mit BC2 liegt in **Fassung 1.2** auf `main` (D3 gebunden), die Spalte
`step_frequency_per_year` ist **live** (B6, PR #263), und BC1 liest BC0 nur noch über dessen
`aktiv`-Sichten (A7, PR #264). Suite: 552 Tests grün.

**Was fehlt, ist nicht der Chatbot — es ist der Betrieb drumherum und die Anbindung an BC0s
Anfrage.** Nichts davon ist neu: alles stand als Roadmap-Anker in den Einzelplänen. Hier
ist es an einem Ort.

### Drei Stufen von „fertig" — die Zielwahl ist eine Entscheidung

| Stufe | Bedeutet | Wofür es reicht |
|---|---|---|
| **A — Etappe 1 abgeschlossen** | Vertrag mit BC2 steht, Testdaten reproduzierbar im Repo, GitHub-Stand stimmt mit der Realität überein, Doku vollständig | Gate-0-Nachweis, Übergabe an BC2 — **erreicht 22.09.** (Rest: A2-Kosmetik) |
| **B — betriebsfähig** | Der Dienst läuft außerhalb eines Entwickler-Laptops, an BC0s Anfrage gebunden, mit echten Nutzern, DSGVO-konform: Sessions-Tabelle signiert, PII-Filter, Deployment, Auth, Betriebsprotokoll | Echter Einsatz beim Mandanten |
| **C — Spec-vollständig** | Die späteren Schichten aus der Systemarchitektur: Rollen, Doku-Generator, Baseline-Mapper, Voice/OCR, Etappe-2-Fragen | Die volle BC1-Vision |

**Empfehlung:** Stufe A ist erreicht. Stufe B bis zum Novemberziel der Gruppe; aus C nur
**C1a** vorgezogen (Version 3 der Testprofile, in #195 öffentlich zugesagt). Was Stufe B
jetzt treibt, ist nicht die Reihenfolge B1–B7, sondern der **Durchstich in KW 40**.

### Kritischer Pfad bis KW 40 — der Durchstich (#206)

BC0 spielt in KW 40 die Strecke **Anfrage (BC0) → Interview (BC1) → Gate 0 (BC0) → BC2**
einmal mit echten Daten durch, „ohne Eingriff von Hand". Damit BC1 seinen Teil so liefert,
fehlen genau zwei Pakete:

1. **B5 — Anfragesteuerung** (bereit, hängt an niemandem): ohne Anfragebezug ist ein
   Profil keinem Auftrag eindeutig zuzuordnen (Simeon in #206), und BC0s Papier vom 21.09.
   (#256) legt fest, dass BC1 **ausschließlich anfragegesteuert** ist — die Interview-Auswahl
   kommt also aus der Anfrage (`v_anfrage_teilprozesse`), nicht aus der Mandantenliste; je
   Teilprozess der Anfrage eine Sitzung, alle mit derselben `anfrage_id`.
2. **B4 — Dienst-Anmeldung an BC0 + Endpunkte** (wartet auf das Passwort des
   Anwendungskontos, erbeten im Brief vom 22.09.): setzt Zuordnung und Status
   `im_interview` selbst. **Rückfall, falls das Passwort nicht rechtzeitig kommt:** BC0
   setzt Zuordnung und Status im Durchstich von Hand — ein benannter Handeingriff, kein
   Scheitern.

Zwei Punkte liegen bei BC0 und müssen **vor** dem Termin geklärt sein, sonst scheitert der
Durchstich per Definition am Gate:

- #206 verlangt „Rollen mit Zeitanteil" von BC1. BC2 hat diese Achse am 20.09. abgewählt
  (#172, Vertrag 1.2), BC1 baut sie nicht (C1b entfällt). Im Brief 22.09. gebeten, die
  Gate-0-Prüfpunkte „Rollen mit Zeitanteil" und „Menge" zu streichen oder auf `entfaellt`
  zu setzen.
- Kaskadiert BC0 die Stilllegung eines Kernprozesses auf seine Teilprozesse? (A7; bis zur
  Antwort gilt bei uns die strengere Lesart: nur Teilprozesse aktiver Kernprozesse.)

Danach **C1a** mit Version 3 der Testprofile — der Lauf, der alle Korrekturen bündelt.

### Arbeitsteilung ab 23.09. — Richard baut die großen Pakete, Philipp die kleinen

Philipp übernimmt abgegrenzte Pakete, die **in einer Arbeitssitzung abschließbar** sind und
weder Datenmodell noch Verträge noch die Live-Datenbank berühren. Jedes bekommt ein eigenes
GitHub-Issue mit vollem Kontext (Ziel, Dateien, Akzeptanzkriterien, Befehle, Grenzen);
Richard prüft den PR vor dem Merge (CODEOWNERS `team-bc1`). Reihenfolge P1 → P5; P1 ist
bewusst ein Doku-Paket zum Ankommen.

| # | Paket | Gehört zu | Art | Aufwand |
|---|---|---|---|---|
| **P1** | README + `CLAUDE.md` auf den Stand nach dem MVP-Kern bringen (Mitarbeit, Arbeitspakete, Struktur) · README-Zusage aus #233: PII-Quoten sind Offline-Wert aus dem Testset, kein Betriebsbestand | A2 | Doku | S |
| **P2** | Dockerfile + `.dockerignore` für den Dienst (kein root-Betrieb, `uv.lock`), README-Absatz | B3 Teil 1 | Konfiguration | S |
| **P3** | Verständliche Fehlertexte im Chat statt roher Schlüssel: `chat_text` neben dem stabilen `detail` | B3 Teil 1 | Code, TDD | S |
| **P4** | Beschädigte Sitzungszeile: `KorrupterStateError` statt rohem `KeyError`/500 | B3 Teil 1 | Code, TDD | S |
| **P5** | Betriebsprotokoll Teil 1: eine Zeile je Turn im Dienst, Correlation-ID, ohne Gesprächsinhalte | B7 Teil 1 | Code, TDD | S–M |

Bei Richard bleiben: B5, B4, C1a, B7 Teil 2 (Kern, Adapter, Store), die Kern-Teile von B3
(Zugangsprüfung, Turn-Claim) — alles, was Live-Datenbank, Signaturen oder Vertrag berührt.

### Reihenfolge und warum

1. **B5 zuerst** — bereit, ohne Fremdabhängigkeit, Voraussetzung für den Durchstich.
2. **B4, sobald das Passwort da ist** — bis dahin gilt der Rückfall „von Hand" (oben).
3. **C1a mit Version 3** — ein Lauf, alle Testprofil-Korrekturen (KW 40 mit BC0).
4. **P1–P5 laufen parallel** (Philipp). B7 Teil 2 und B3 Teil 2 folgen, wenn Hosting
   entschieden ist.
5. **C nach Bedarf**; C3 erst nach Stufe B.

---

## Technischer Teil

Aufwand ist eine **Schätzung in Arbeitssitzungen** (S = 1, M = 2–3, L = mehr oder
unklar) und wird beim jeweiligen Implementierungsplan präzisiert.

### Stufe A — Etappe 1 abschließen (erreicht; Rest ist Kosmetik)

| # | Paket | Stand | Offen | Aufwand |
|---|---|---|---|---|
| **A1** | **Vertrag BC1→BC2** | **Erledigt.** Fassung 1.0 von BC2 gegen unsere Zeilen geschnitten (#195, 10.09.); Prüfung mit Zweitmeinung → Fassung 1.1 (PR #199, drei Zusagen in unserem Namen zurückgenommen, v. a. „nie NULL bei fertig"); Fassung 1.2 auf `main` seit 20.09. (PR #236): D3 gebunden (I8), C1b abgewählt. Klärpunkt K-L beantwortet (Herkunftsanker), K-K hingenommen, `menge`-Einheit = Fälle je Durchlauf (I2) | Vertragsartefakte nach B6 nachziehen (D3 in `required`, Beispiel, README-Zahlen) — **mit BC2**, siehe Kleinpunkte; Version 3 der Testprofile → C1a | — |
| **A2** | **GitHub-Stand = Realität** | **Weitgehend erledigt:** #120–#126 über PR #129 geschlossen; DoD-Abgleich als Kommentar in #48 (08.09.); #49/#52/#53 als Post-MVP-Schicht kommentiert; README-Setup seit 08.09. | #48 als Übersicht schließen oder stehen lassen und #51 schließen (durch #123 abgedeckt) — **Richard**; README „Wie man hier mitarbeitet"/„Arbeitspakete"/„Struktur" und `CLAUDE.md` „Erst lesen" zeigen noch auf den erledigten MVP-Schnitt → **P1** | S |
| **A3** | **Spalte-zu-Feld-Tabelle** | **Erledigt 14.09.** — `design/Spalte-zu-Feld-Tabelle.md`, aus der README verlinkt (PR #201) | — | — |
| **A4** | **Testdaten reproduzierbar (Rev. 12)** | **Erledigt 14.09.** — `bc1_service/use_case_testprofile.py` (drei Fälle als Daten, regulärer Schreibweg, `--echt`) + `tests/test_use_case_testprofile.py` (13 Tests: `fertig`, Kennzeichnung in derselben Nachricht wie das letzte Pflichtfeld, zweiter Lauf ohne neue Version, neue `session_id` = Version 2) | Version 3 → C1a | — |
| **A5** | **Auswirkungsprüfung v2.5–v3.1** | **Erledigt 12.09.** — `design/Auswirkungspruefung-BC0-v2.5-v3.1.md`, nichts bricht; A5b (Gerüst-CHECK v2.8, `mandant_rollen`-GRANT) gebaut | — | — |
| **A6** | **Dorka-Termin 22.09.** | Folien geliefert (2 Folien + Erklärung, 16.09.), Termin am 22.09. | Ergebnis des Termins ist nicht Teil dieses Plans; Hosting-Entscheidung siehe unten | — |
| **A7** | **Auswirkungsprüfung v3.2–v3.7 + Gerüst v3.4** | **Erledigt 22.09.** (PR #264, `d40c6ac`) — `design/Auswirkungspruefung-BC0-v3.2-v3.7.md`: vier Sichten live wortgleich, Eigner-Index identisch, nichts bricht. Gerüst nachgezogen (`aktiv`, `ref_personen`, `ux_prozess_eigner_eindeutig`, `v_teilprozesse_lesen`/`v_systeme_lesen`, `owner_rolle_id`); Lesepfad nur noch über Sichten (4 Tests); v3.5-Entzug `prozess_personen`/`ref_personen` gemessen (#216). Codex 22.09.: 0 Critical, 2 Important gefixt (Freeze prüft Interviewbarkeit erneut; stillgelegter Kernprozess sperrt seine Teilprozesse), Minor → Kleinpunkte | Kaskaden-Frage an BC0 im Brief 22.09. gestellt; bis zur Antwort strengere Lesart | — |

### Stufe B — betriebsfähig

| # | Paket | Ziel | Nächster Schritt | Hängt an | Aufwand |
|---|---|---|---|---|---|
| **B1** | **`bc1.sessions` ins Fundament** | **Erledigt 14.09.** — eigene signierte Einspiel-Einheit `sessions.sql` (Entscheidung Richard: nicht in `prozessprofil.sql`), Schlüssel `session_id` allein, `company_id` Pflicht mit `ON DELETE CASCADE`, Store legt nichts mehr an, Generator `tests/db/signatur_erzeugen.py` im Repo; live eingespielt 13.09. (`EINSPIELEN.md` §10); Codex 13.09.: 10 Befunde, alle gefixt. Plan: `design/Implementierungsplan-B1-Sessions-Fundament.md` | — | — | — |
| **B2** | **PII-Filter (#50)** | **Erledigt 14.09.** — `bc1_core/pii.py` vor dem ersten Speichern, kein Original mehr; Muster E-Mail/Telefon/IBAN/Adresse/Name mit Hinweiswort, kein Mapping-Tresor, keine Namensliste aus BC0; Kennzahl `pii_erkennung` gegen die README-Tabelle; Codex vor und nach dem Bau, alles eingearbeitet. BC0 informiert (Brief 15.09., #216 bestätigt 22.09.). Konzept + Plan in `design/` | Vertagtes (NER, Platzhalter als Feldwert, n8n-Ausführungsdaten) → Kleinpunkte | — | — |
| **B3** | **Deployment** | Der Dienst läuft außerhalb eines Entwickler-Laptops. **Teil 1, hosting-unabhängig:** (a) Dockerfile + `.dockerignore`, kein root-Betrieb (BC0-Lehre #210), `uv.lock` liegt seit 14.09. → **P2** · (b) verständliche deutsche Fehlertexte im Chat — heute zeigt n8n bei 409/503 den rohen Schlüssel (`session_abgeschlossen`, `paket_konflikt`, …, Ausdruck `chat_text ?? detail`) → `chat_text` neben dem stabilen `detail` → **P3** · (c) beschädigte Sitzungszeile — `state_from_dict` wirft heute `KeyError`, der Dienst antwortet 500 ohne Aussage → `KorrupterStateError`, klare Antwort → **P4** · (d) Zugangsprüfung für `GET /prozesse` — heute offen; der Endpunkt liest den Snapshot, der mit B4 durch den DB-Lesepfad ersetzt wird → **mit B4** (Richard) · (e) Turn-Claim in der DB — **herabgestuft:** der Store schreibt per Compare-and-Swap, ein verlorener Wettlauf ist 409 `gleichzeitige_anfrage`, der Client wiederholt; mit einem Worker reicht das, ein Claim wäre Komfort. Auslöser: mehr als ein Worker. **Teil 2, nach Hosting-Entscheidung:** Betrieb auf dem gewählten Server, Umgebungsvariablen, n8n-Chat auf feste Adresse, Aufbewahrung der n8n-Ausführungsdaten (aus B2) | Sammel-Issue anlegen (Entwurf liegt seit 16.09.; Folie 22.09.: „wird angelegt"), P2–P4 als Teil-Issues; Hosting-Entscheidung der Gruppe einholen | Gruppe (Teil 2) | Teil 1: S je Punkt · Teil 2: M |
| **B4** | **Dienst-Anmeldung an BC0 + Endpunkte** | **Kritischer Pfad #206.** Anwendungskonto (Name: Simeons Brief 18.09.; Rolle **`benutzer`** — alle vier Endpunkte hängen an `angemeldeter_benutzer`, `admin` ist nicht nötig; `POST /api/auth/login`, HttpOnly-Cookie) im Dienst mitführen; dann `PUT …/zuordnung` (`zuordnung_quelle='interview'`) und `PUT …/status` (`im_interview`) aufrufen. `am_gate` setzt BC0 selbst. Rückfall ohne Passwort: BC0 setzt beides im Durchstich von Hand | Passwort des Anwendungskontos (Brief 22.09.) → Client mit Cookie-Jar; Test gegen Fake-BC0; Snapshot-Modus (`BC1_SNAPSHOT_PFAD`) durch den DB-Lesepfad ablösen; dabei `/prozesse`-Zugangsprüfung (B3 d) | Konto und Adresse (`https://bc0.perspektivwechsel.ai`) bekannt; **fehlt nur das Passwort** | M |
| **B5** | **Anfragesteuerung: `anfrage_id` und Teilprozess-Auswahl aus der Anfrage** | **Kritischer Pfad #206.** BC0s Papier „Vom Anliegen zum Paket" (21.09., #256) setzt fest: **BC1 ist ausschließlich anfragegesteuert** (unser Brief 22.09. sagt dasselbe: Weg 2 nein). Heute bietet der Dienst alle bewerteten Teilprozesse des Mandanten an — Übergangsmodus. Ziel: (1) Interview-Auswahl aus **`v_anfrage_teilprozesse`** (`bc_leser` seit v2.7; löst `sub_process_id NULL` in alle aktiven Teilprozesse des Kernprozesses auf, trägt `freigegeben`/`im_paket`) statt aus der Mandantenliste; mehrere Teilprozesse je Anfrage = je Teilprozess eine Sitzung mit **derselben `anfrage_id`**; BC0 schnürt erst, wenn alle Teilprozesse der Anfrage freigegeben sind (Regel 7, `v_anfrage_uebergabe_stand.vollstaendig`) · (2) `anfrage_id` in `bc1.sessions` und `bc1.prozessprofil` mitführen — **neue Spalte = Sollsignatur neu + Migrationseinheit wie B6**, dabei C4 (b) einlösen (RI-Trigger signieren) · (3) Interviewpartner über `v_anfrage_steller` (GRANT seit v3.4), Vorbelegung A1/A2. **Klärpunkte an BC0 (mit #226 zusammen):** Sperren `eigner_benannt`/`items_bewertet` sind Gate-Vorbedingungen — soll BC1 nur entscheidungsreife Teilprozesse anbieten, und woran liest es das? Anfragen mit welchem `status` sind interviewbar (`zugeordnet`, `im_interview`)? Dazu #226: BC0 fragt, **welche Felder BC1 vom Anliegen braucht** → Anliegen-Text ohne Personenbezug, `status`; Rückmeldung über die Sicht, BC1 liest beim Start und je Turn | **Nächstes Go.** Implementierungsplan; Gerüst um `v_anfrage_teilprozesse`, `v_anfrage_uebergabe_stand`, `v_anfrage_prozessbezug`, `v_anfrage_steller` erweitern; Felderliste + Klärpunkte in #226 kommentieren (nach OK) | bereit — Sichten liegen; Klärpunkte blockieren den Bau nicht, nur die Feinheiten | M |
| **B6** | **Spalte `step_frequency_per_year` (#255)** | **Erledigt 22.09.** (PR #263, live) — Spalte numeric im Wertebereichs-CHECK, Sollsignatur 177 Zeilen, Migrationseinheit `prozessprofil_d3.sql` (M0–M3, eine Transaktion mit `prozessprofil.sql`), Writer liest D3, `EINSPIELEN.md` §2/§11 mit Messwerten; `lesen.sql` liefert 3 Profile mit 20 Spalten. Codex 22.09.: 0 Critical, 2 Important gefixt, 3 Minor → Kleinpunkte | BC2 um `bc2_role`-Gegenprobe gebeten (#255) | BC2 | — |
| **B7** | **Betriebsprotokoll (Logging)** | Design-Spec B7 „Observability (minimal)": aus dem Protokoll ist nachvollziehbar, welche Sitzung wann lief, wie lange ein Turn und ein KI-Aufruf dauerte, ob wiederholt wurde und wo eine Validierung scheiterte — **ohne Gesprächsinhalte, extrahierte Werte oder Profildaten**. Heute loggt nur `profil_writer.py`. **Teil 1 (Dienst):** Correlation-ID je Anfrage, eine Zeile je `/turn` mit Sitzungs-/Nachrichten-ID, HTTP-Status, fachlichem Status, Dauer; Test belegt, dass der Nachrichtentext nicht im Protokoll steht → **P5**. **Teil 2 (Kern, Adapter, Store):** Latenz und Wiederholungen je KI-Aufruf, Validierungsfehler je Feld (Feldname, nie der Wert), Start- und Abbruchgründe, Correlation-ID durchgereicht → Richard | Sammel-Issue anlegen (Entwurf liegt), P5 als Teil-Issue; Teil 2 nach P5 | — | Teil 1: S–M · Teil 2: M |

### Stufe C — Spec-vollständig (selektiv)

| # | Paket | Ziel | Nächster Schritt | Hängt an | Aufwand |
|---|---|---|---|---|---|
| **C1** | **Rollen-Lesepfad + `profil_rollen`** | Rollen als **Auswahl** aus `mandant_rollen` statt Freitext; `process_owner_rolle_id` setzen. Eigner ist seit v3.4 **genau einer** (`ux_prozess_eigner_eindeutig`), `owner_rolle_id` steht in `v_prozesse_lesen` (Gerüst seit A7) — Vorbelegung daraus, Abweichung im Profil melden, nicht ändern (Simeon 18.09.). **C1a (vorgezogen, ein Lauf = Version 3 der Testprofile):** Owner-Auswahl aus `mandant_rollen` (`bc1_role` liest sie, gemessen 12.09.) → `process_owner_rolle_id` · **D4 auf reinen Zähl-Typ** ohne Perioden-Normalisierer (Vertrag 1.1) · **E2-Fragetext „je Durchlauf"** (Vertrag 1.1) · Testprofile korrigieren: `executions_per_run` fachlich (=1), D1/E1 je KP konsistent — Zusage „Version 3" steht öffentlich in #195 · durchgehender Writer-Test für D3 (Codex B6). **C1b: entfällt** — BC2 hat am 20.09. entschieden (#172, #195, Vertrag 1.2): Mischsatz 43 €/h, keine Rollenliste, kein Zeitanteil; Wiederaufnahme nur bei Neuentscheidung von BC2. Offen bei BC0: Gate-0-Prüfpunkt „Rollen mit Zeitanteil" hat keinen Abnehmer mehr (Brief 22.09., **blockiert #206 fachlich**) | Nach B5/B4: Implementierungsplan C1a; Version 3 in KW 40 mit BC0 (im Durchstich mitnehmen) | BC0 (Gate-0-Prüfpunkte) | M |
| **C2** | **Etappe-2-Fragen** | Nachfass-Paket für Lücken (Klartext, keine Skalen) · Kanten-Art „Was fließt zwischen den beiden?" (**BC0-Endpunkt existiert seit v2.4:** `POST /api/companies/{cid}/prozesskanten`, Arten `daten/freigabe/material/information`, Rolle `benutzer` genügt — Simeon 18.09.) · strukturierte System-Erfassung (S-NN als Auswahl) · ~~`aktiv` auswerten~~ **erledigt mit A7** · B6 `process_category`-Umbau (braucht `ref_prozesse`-Lesepfad + `SCHEMA_VERSION`-Erhöhung, BC0 informieren) | Je Punkt ein kleines Paket; Reihenfolge nach Bedarf der Use Cases | — | M |
| **C3** | **Spätere Schichten** | Doku-Generator (#52: Prozessdoku aus dem Profil) · Baseline-Mapper (#53: Abgleich mit BC0-Reifegrad) · Voice/OCR (#49: Eingangsschicht vor dem Extractor; BC0 denkt in #204 über Anfragen mit Anhängen nach — dort andocken, nicht parallel bauen) | Erst wenn Stufe B steht und das Team den Bedarf bestätigt — jede Schicht dockt am Kern an, ohne ihn zu ändern | Team | L |
| **C4** | **Härtung, bewusst vertagt** | **K-K:** der Freeze prüft die Erhebung nicht nach (Draft angelegt → Erhebungen verworfen → Zeile `fertig` mit verworfener ID; gemessen) — **seit A7 prüft der Freeze erneut die Interviewbarkeit** (stillgelegt / keine aktuelle Bewertung → 503, Test); offen bleibt die gespeicherte `erhebung_id` selbst und dass der Session-Zustand vor dem 503 schon `fertig` ist (Codex A7, I1) · **K-M:** Eingaben < 0,0001 werden zurückgewiesen (`str(float)` → Exponent) — fachlich irrelevant · Outbox/Reconciler nur, falls der 503-Weg operativ nicht reicht · `SECURITY DEFINER`-Prüfpfad für die S-NN-Restlücke · automatische Auflösung verwaister Drafts (K5 bleibt manuell) · **Rechengrößen unaufgebbar?** — entschieden 12.09.: aufgebbar lassen, BC2 hält NULL aus · **strukturierter Testdaten-Marker** statt Präfix-Konvention `Testdaten ` in `open_remarks` (Review 12.09.) · Signatur-Härtung und Inventarprüfung (siehe Kleinpunkte) | Nur auf konkreten Anlass | — | S je Punkt |

### Nachgehaltene Kleinpunkte (aus allen Plänen, damit nichts verloren geht)

- **Neu 22.09. — README-Zusage aus #233:** die PII-Quoten in der README-Tabelle als „Offline-Wert, Testset, kein Betriebsbestand" kennzeichnen → **P1**.
- **Neu 22.09. — #226 (BC0):** Sicht auf das Anliegen + Rückmeldeweg bei Statuswechsel; BC0 wartet auf unsere Felderliste → **B5**.
- **Neu 22.09. — Ticket-Entwürfe Logging/Deployment** (Folie 22.09.: „werden angelegt") werden als Sammel-Issues zu **B3** und **B7** angelegt; Philipps Pakete P2–P5 hängen darunter.
- **Neu 22.09. — zwei offene Fragen an BC0 aus dem Brief 22.09.:** Gate-0-Prüfpunkte „Rollen mit Zeitanteil"/„Menge" ohne Abnehmer (blockiert #206 fachlich) · Kaskade der Stilllegung KP → TP (A7; bis dahin strengere Lesart im Lesepfad).
- **Neu 22.09. — BC0-Papier „Vom Anliegen zum Paket" (Simeon, 21.09., Antwort auf #256), was uns bindet:** Regel 4 „Das Interview vertieft, es erhebt nicht neu — BC1 liefert Dauer, Häufigkeit, Menge und Rollen auf BC0s IDs zurück" (so gebaut: TP-ID als Anker, S-NN als Auswahl) · Regel 7 „Übergeben wird eine Anfrage nur vollständig" → B5 (mehrere Teilprozesse je Anfrage) · Abschnitt 2.2: die Prüfpunkte `dauer`, `haeufigkeit`, `menge`, `rollen` haben Quelle BC1 und **Güte-Pflicht** bei Freigabe (`belegt`/`geschaetzt`/`geraten`/`entfaellt`); unser #233-Vorschlag bildet nur `dauer` ab (`focus_step_duration_source`) — für `haeufigkeit`/`menge` gibt es bei uns keine Quelle, die Güte setzt heute der Mensch am Gate. **Falls BC0 eine Quelle je Größe von BC1 will, ist das eine Vertragsänderung mit BC2 und eine Spec-Entscheidung (Richard), kein Nebenbei** — offen, mit #226/#233 klären · `rollen` und `menge` bleiben der bekannte Widerspruch zu BC2 (Brief 22.09.) · Abschnitt 2.5: das Gate-Ereignis **kopiert** `erhebung_id` und `bc1_profil_stand` statt zu verweisen — passt zu unserem Freeze (`fertig` ist final; Korrektur = neue Version) · Abschnitt 4/5: „Weg 2 — BC1 interviewt ohne Anfrage" ist im Brief 22.09. mit **nein** beantwortet; Paketgröße = Aufbaustand, keine Absicht (Simeon in #256).
- Wert/Kandidaten-Überlappung bei UNGUELTIG-Korrektur-Zyklen — kosmetisch, im Test gepinnt (MVP-Kern).
- Prompt-Feinschliff der Adapter (Feldtypen, Mehrsprachigkeit, Beispiele) — wenn echte Pakete stabil sind (P2-Plan).
- Zwischenstands-Updates des Profil-JSON je Turn — nach Etappe 2 bewerten, YAGNI (DB-Profil).
- **Dauerregel:** kein Fremdschlüssel von `bc1.*` auf `prozess_personen`/`ref_personen` — BC0 schreibt sie mandantenweit neu (DB-Profil).
- **Dauerregel (15.09., zugesichert an BC0):** `bc1_role` braucht **SELECT auf `public.companies`** — der Freeze-Trigger liest die Tabelle bei BC0s Löschkaskade (`DELETE FROM companies`) mit den Rechten von `bc1_role`; ohne das Recht bricht BC0s DSGVO-Löschung. Gemessen 12.09.: das SELECT kommt über `bc_leser` (Mitgliedschaft), direkt hat `bc1_role` nur `REFERENCES`. Kein BC1-Artefakt darf diesen Weg voraussetzungslos kappen; BC0 sagt vor dem Aufräumen der direkten Grants (Etappe 4c, #215), welcher Weg bleibt. Suite: `test_kaskade_laeuft_auch_unter_echter_rollentrennung`, `test_kaskade_raeumt_die_sitzung_auch_unter_rechtelosem_loeschkonto`. Container-Test, der die Kaskade **ohne** das Recht laut scheitern sieht: vertagt nach C4, Auslöser nächste Änderung an `sessions.sql`/`prozessprofil.sql` (also B5).
- Bitkom-30-Items im Chat — **entfällt endgültig** (Team-Beschluss, von BC0 angenommen); Bewertung bleibt im Self-Rating.
- Die Produktfrage „wer bewertet die übrigen Teilprozesse" liegt außerhalb des Projekts (Roadmap-Anker für ein Produkt).
- **D3 `step_frequency_per_year`** — gebunden (BC2, 20.09., I8), Spalte + Migration mit **B6** eingelöst (22.09.); der Writer liest das Feld in die Spalte.
- **Aus dem Codex-Review zu B6 (22.09.) vertagt, je mit Ziel:** (1) Signatur-Determinismus — `pg_get_constraintdef`-Text hängt von `quote_all_identifiers` ab; alle drei Einspiel-Einheiten setzen nur `search_path`. Ziel **C4** (Signatur-Härtung): `SET LOCAL quote_all_identifiers = off` in allen Einheiten gleichzeitig, nicht nur in einer. (2) Durchgehender Writer-Test für D3 (normalisierter Wert → INSERT → Abschluss → Freeze weist UPDATE ab); Auslöser: **C1a/Version 3**, sobald D3 im Interview tatsächlich gesetzt wird. (3) Vertragsartefakte `contracts/bc1-to-bc2/`: D3 fehlt in `required`, Beispiel-Export ohne den Schlüssel, README „17 Felder" (sind 18) und „BC1 musste nichts ändern" sind überholt — **mit BC2 in #255 klären**, gemeinsame Datei, kein Alleingang.
- **Repo-Konvention seit 14.09.:** Feature-Zweige ab `main`, Squash-Merge (Ruleset `protect-main` verlangt lineare Historie); die Bau-Historie bis 14.09. liegt auf dem Tag `bc1-bau-2026-09-14`.
- **Default-Privileg auf `public`:** jede neue BC0-Tabelle ist automatisch für `bc1_role` und `bc_leser` lesbar (gemessen 12.09., 22.09. unverändert) — **BC0 hat entschieden (#201/#214, 22.09.):** Fall behoben (v3.6, fünf Betriebstabellen entzogen), Mechanismus bleibt bis zum Umzug der Betriebstabellen nach `bc0_betrieb` (#262, Soll 09.10.). Für uns kein Handlungsbedarf.
- **Snapshot-Modus (`BC1_SNAPSHOT_PFAD`) filtert `aktiv` nicht** (Codex A7, Minor): Kernprozess-Auswahl kommt dann aus der Datei, ohne Abgleich mit `v_prozesse_lesen`. Dokumentierte Ausnahme; Ziel **B4**: Snapshot durch den DB-Lesepfad ablösen.
- **Signatur-Sicht liegt zweimal im Repo** (`prozessprofil.sql`, `sessions.sql`) — bewusst, solange nur zwei Einheiten eine Sollsignatur tragen; `prozessprofil_d3.sql` hat keine. **Bei einer dritten Signatur** wird die Sicht in einen Generator gezogen, nicht vorher (YAGNI).
- **Aus der Zweitmeinung zu B1 (Codex, 13.09.) deferiert, Ziel C4:** (a) **Inventarprüfung fremder Objekte in `bc1`** — eine View oder `SECURITY DEFINER`-Funktion auf `bc1.prozessprofil`/`bc1.sessions` sieht keine der beiden Signaturen; Auslöser: Deployment in eine gehostete Umgebung (B3 Teil 2). (b) **`prozessprofil.sql` signiert die RI-Trigger der referenzierten Seite nicht** (`sessions.sql` tut es); nachziehen bei der nächsten Signatur-Neuerzeugung von `prozessprofil.sql` — **das ist B5**, falls dort eine Spalte hinzukommt. (c) **Generator-Parser kürzt mehrzeilige Signaturwerte still** — heute gibt es keine; beheben, sobald eine Signaturart mehrzeilig wird.
- **Alte Generator-Kopie außerhalb des Repos** (`AutoCoE_Projekt/signatur-erzeugen.py`) ist seit B1 durch `tests/db/signatur_erzeugen.py` ersetzt — löschen (Richard, seine Datei).
- **Aus B2 (14.09.) vertagt, je mit Auslöser:** NER für nackte Nachnamen (Auslöser: gemessene Fehlrate in echten Turns) · Platzhalter als alleiniger Feldwert (z. B. Owner-Rolle = `[Person A]`) als ungültig behandeln und nachfragen (C2-Nähe; Auslöser: Auftreten in Testläufen) · n8n speichert Ausführungsdaten mit der Chat-Eingabe, bevor der Dienst filtert (B3 Teil 2: Ausführungsdaten nicht speichern oder kurz aufbewahren) · Straßen ohne Straßenwort („Am Alten Markt 3") und Kartennummern (Auslöser: erster Treffer in echten Läufen) · Konsistenz der Platzhalter über Turns (Auslöser: Profile werden dadurch unlesbar).
- **Befunde BC0 zu PR #201 (Simeon, 14.09., kein Einwand, ADR-003 eingehalten):** (1) Sechs FKs ohne `ON DELETE` machen `process_id`/`sub_process_id`/`erhebung_id`/`rolle_id` in BC0 faktisch unveränderlich — BC0 nimmt „Stilllegung statt Löschen" ins ADR (#218). Für uns: Kontext, nichts zu bauen. (2) Löschkaskade → Dauerregel oben (#215). (3) `aktiv`-Filter in BC0s Sichten — **erledigt (v3.4, A7)**; eigener Zusatzfilter: nur der aktive Elternprozess. (4) Default-Privilegien — **beantwortet 22.09.**, siehe oben.
- **Normalisierung ist Vertragsbestandteil** (Vertrag 1.1, Abschnitt „Normalisierung der Zahlen"): Perioden-/Einheitenlogik in `feldtypen.py` nicht mehr ohne BC2-Hinweis ändern.

### Entscheidungen, die den Plan bewegen

| Entscheidung | Optionen | Empfehlung | Wer |
|---|---|---|---|
| **Zielstufe** | A · B · C | **B bis November**, C1a vorgezogen — A erreicht 22.09. | Richard mit Team |
| **Nächstes Go** | B5 · B7 · C1a | **B5** — kritischer Pfad #206, bereit, ohne Blocker; B7 läuft über P5 parallel an | Richard |
| **Arbeitsteilung** | alles bei Richard · Philipp übernimmt kleine Pakete | **P1–P5 an Philipp** (klein, abgegrenzt, ohne Datenmodell/Vertrag/Live-DB, eigenes Issue mit vollem Kontext, Review vor Merge) — **so entschieden 22.09.** | Richard ✔ |
| **Durchstich KW 40 ohne B4** | Termin verschieben · BC0 setzt Zuordnung/Status von Hand | **von Hand als benannter Rückfall** — der Durchstich prüft die Strecke, nicht unsere Anmeldung; B4 folgt, sobald das Passwort da ist | Richard mit Simeon |
| **Hosting** | Gruppen-Server · Cloud · lokal bleiben | offen — Entscheidungspunkt war der 22.09.; Ergebnis hier nachtragen; blockiert nur B3 Teil 2 | Gruppe |
| **Reihenfolge Stufe B** | B1→B2→B3 oder B3 zuerst | **B1→B2 erledigt**; B3 Teil 1 parallel über P2–P4, Teil 2 nach Hosting | Richard ✔ |
| **Sitzungsschlüssel** | `session_id` allein · `(company_id, session_id)` | **`session_id` allein — so entschieden 13.09. (B1)**; Verbundschlüssel bleibt Roadmap-Anker mit Auslöser „zweite Dienstinstanz auf derselben Datenbank" | Richard ✔ |
| **Stufe C: was davon** | alle vier Schichten · nur Rollen + Doku-Generator | nach Use-Case-Bedarf; Voice/OCR zuletzt und an #204 andocken | Team |
| **Rechengrößen unaufgebbar** | aufgebbar lassen · `identitaetskritisch` | **aufgebbar lassen — so entschieden 12.09.** | Richard ✔ |
| **`executions_per_run`-Korrektur** | Version 3 sofort · mit C1a in einem Lauf | **mit C1a** — ein Lauf, alle Korrekturen; Version 3 ist in #195 zugesagt | Richard ✔ |

### Was dieser Plan ausdrücklich nicht ist

Kein Code-Plan. Jedes Paket bekommt nach Go seinen eigenen Implementierungsplan mit
Tests, Dateien und Commit-Grenzen — in der Tiefe, die die bisherigen Pläne haben. Wer hier
Code-Schritte sucht, sucht am falschen Ort; wer wissen will, **was noch fehlt und warum in
dieser Reihenfolge**, ist richtig.

---

## Selbstprüfung (vom Autor)

- **Spec-Abdeckung:** Design-Spec B7 (Observability) → B7 · B8 (Roadmap) → A1, C3 ·
  Systemarchitektur „spätere Schichten" #49/#50/#52/#53 → B2, C3 · P2-Roadmap-Anker
  (Deployment, Turn-Claim, Auth, Lockfile, Korrupt-Row, Fehlertexte, Logging) → B3, B7 ·
  MVP-Kern-Anker (Vertrag) → A1 · DB-Profil „NICHT baut" → A4, B1, B4, B5, C1, C2, C4,
  Kleinpunkte · Klärpunkte K-K/K-L/K-M → C4, A1, C4 · #48-DoD → A2 · BC0-Tickets #206, #226,
  #215, #218, #204 → B4/B5, B5, Kleinpunkte, Kleinpunkte, C3.
- **Arbeitsteilung:** jedes P-Paket hat ein Ziel-Paket (A2, B3, B7) — nichts Neues ohne Anker.
- **Offen benannt:** Aufwände sind Schätzungen; Hosting ist die eine Entscheidung von
  außen (blockiert B3 Teil 2); der Durchstich hängt an zwei BC0-Antworten und einem
  Passwort; C3 ist bewusst grob, weil der Bedarf nicht feststeht.
- **Vertraulichkeit:** enthält keine Zugänge (der Kontoname steht nur in Simeons Brief),
  keine internen Absprachen, keine personenbezogenen Daten; Mandant NoroAI ist bereits
  öffentlich dokumentiert.
