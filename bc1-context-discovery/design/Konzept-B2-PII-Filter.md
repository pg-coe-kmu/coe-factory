# B2 — PII-Filter vor LLM und Datenbank: Konzept

> Stand 14.09.2026, mit Nachträgen aus dem Plan-Review (Codex, 14.09.). Entscheidungen Richard 14.09.2026 (Chat, nach Bestandsaufnahme). Bezug: Issue #50, Abschlussplan Stufe B Paket B2, Design-Spec B7/B8. Der Implementierungsplan folgt als eigene Datei; dieses Dokument ist das *Warum* und das *Was*.

## Big Picture

**Ziel.** Kein personenbezogener Klartext verlässt den Code-Kern — weder zum LLM-Anbieter noch in die Datenbank. Der Filter ist ein reiner Textschritt im Kern, unmittelbar bevor eine Nachricht zum ersten Mal gespeichert wird. Ein Original gibt es danach nicht mehr.

**Warum jetzt.** Seit B1 liegt der komplette Interview-Rohtext in `bc1.sessions` (`raw_log`, jeder Turn wörtlich; dazu Profilwerte und LLM-Antworten). Die Supabase ist mandantenübergreifend geteilt, und Issue #50 verlangt: kein PII-Klartext in der Datenbank. Nach dem Abschlussplan geht nichts in eine gehostete Umgebung (B3), bevor dieses Konzept steht.

**Die drei Entscheidungen (Richard, 14.09.2026):**

1. **Filter am Eingang, kein Original.** Alternativen waren ein Mapping-Tresor (Platzhalter → Klartext, getrennt gespeichert) und ein Filter nur vor dem LLM bei erhaltenem Rohtext in `sessions`. Beides verworfen: der Tresor hätte keinen Konsumenten (BC2 arbeitet mit Rollen, niemand will rückersetzen) und wäre eine zweite zu schützende PII-Ablage; der Rohtext in `sessions` widerspricht #50. Svetlanas Referenz in `bc3-engineering-architect/pseudonymisierung/` kommt ebenfalls ohne Rückweg aus.
2. **Erkennung deterministisch, ohne neue Abhängigkeit.** Muster für E-Mail, Telefon, IBAN, Adresse; Namen nur mit Hinweiswort. Kein NER-Modell im ersten Schnitt.
3. **Keine Namensliste aus BC0.** War als Option vorgesehen und ist verworfen: BC0 sperrt Klarnamen für lesende Kontexte (ADR-004 R5, `bc0-baseline-onboarding/README.md` „Zugriff für BC1 bis BC4"), und live hat `bc1_role` auf `ref_personen` kein Recht (gemessen 12.09., `struktur_bc0.log`). BC1 liest keine Namen — BC0 wird darüber informiert.

**Was erkannt wird (erste Stufe).**

| Klasse | Wie | Platzhalter |
|---|---|---|
| E-Mail | Muster, auch Unicode-Domains (Referenz bc3, erweitert) | `[E-Mail A]` |
| Telefon | Muster: Präfix `+` oder `0`, geklammerte Vorwahl `(0)`, 7–14 weitere Ziffern, bis drei Trennzeichen; nicht inmitten von Dezimalzahlen, Datums- und Uhrzeitformen ausgeschlossen (Referenz bc3, erweitert nach Plan-Review) | `[Telefon A]` |
| IBAN | Muster: Ländercode, Prüfziffern, Vierergruppen; Groß-/Kleinschreibung und geschützte Leerzeichen; Folgetext bleibt anhand der Soll-Länge je Land erhalten (Referenz bc3, erweitert nach Plan-Review) | `[IBAN A]` |
| Adresse | Straße/Allee/Gasse mit Hausnummer (auch Bereiche „12-14"), optional PLZ + Ort dahinter (nach Komma oder „in", Ort ein- oder zweiteilig); Weg/Platz/Ring/Damm/Ufer **nur** als volle Adresse mit PLZ + Ort („Arbeitsplatz 3" ist eine Prozessangabe); Prozessbegriffe mit Straßenwort („Fertigungsstraße 3") sind ausgenommen. Kein alleinstehendes PLZ + Ort: fünfstellige Mengen („12000 Rechnungen") wären Fehltreffer (Plan-Review 14.09.) | `[Adresse A]` |
| Name mit Hinweiswort | Anrede (Herr, Herrn, Frau, Hr., Fr.), Titel (Dr., Prof., mit Zusätzen wie „med."), Kollege/Kollegin (kein Plural), Selbstvorstellung („ich heiße", „mein Name ist") — danach ein bis drei **Buchstabenwörter** mit großem Anfangsbuchstaben (lateinische Schrift inkl. Akzente), Partikel wie „von"/„van der" erlaubt, Titel auch zusammengesetzt („Dr.-Ing.") (Kennungen wie `S-03`, `KP-06.TP-2` gehören nie zum Namen). Das Hinweiswort bleibt stehen, Titel und Name werden ersetzt: „Frau Dr. Musterfrau prüft" → „Frau [Person A] prüft". Kennungen folgen der Textreihenfolge | `[Person A]` |

**Was der Nutzer merkt.** Der Interviewer bestätigt mit dem Platzhalter, das Profil trägt ihn. Für ein Prozessprofil sind Rollen relevant, nicht Personen — kein fachlicher Verlust. Die Systemprompts sagen dem LLM, dass eckige Klammern Platzhalter für entfernte Angaben sind: wörtlich übernehmen, nie auflösen, nie raten.

**Was bewusst nicht drin ist — je mit Auslöser (Prinzip 4):**

| Vertagt | Warum | Auslöser / nächster Schritt |
|---|---|---|
| Nackte Nachnamen ohne Hinweiswort („Müller prüft das") | Im Deutschen sind alle Substantive großgeschrieben; ein Muster ohne Hinweiswort trifft Rollen und Systeme. Braucht NER (spaCy/Presidio): schwere Abhängigkeit, Hosting (B3) offen, nicht deterministisch testbar | NER, wenn das Testset oder echte Läufe eine relevante Fehlrate zeigen (Messgröße: Anteil ungefilterter Namen in einer Stichprobe echter Turns) |
| „Ich bin X" als Hinweiswort | „ich bin Sachbearbeiter" würde eine Rolle löschen — genau das, was das Profil braucht | Nur mit NER |
| Kartennummern, Geburtsdaten | In Prozess-Interviews nicht zu erwarten; ein Datum ist eher ein Prozessdatum | Erster Treffer in echten Läufen |
| Konsistenz der Platzhalter über Turns hinweg | Braucht ein gespeichertes Mapping oder ein geheimes Hashverfahren; Extraktion sieht nur den aktuellen Turn | Wenn Profile durch verschiedene Platzhalter für dieselbe Person unlesbar werden |
| Rückersetzung im Chat-Text | Kein Konsument; ein Rückweg wäre eine zweite PII-Stelle | Nie, solange niemand den Klarnamen im Gespräch braucht |
| Migration vorhandener Sitzungen | Live liegen nur die drei Testprofile ohne echte Namen (Repo-Konvention) | Entfällt |
| B7-Logging (Correlation-ID, Latenz, Zähler ohne Inhalt) | Eigenes Paket, setzt auf diesem Filter auf | Nach B2, laut Abschlussplan |
| Ein Wert, der nur aus einem Platzhalter besteht (Owner-Rolle = `[Person A]`), als ungültig behandeln und nachfragen | Sinnvoll, aber nicht Teil des Filters; Feldtyp-Frage | Wenn es in Testläufen auftritt (C2-Nähe) |

**Eine Grenze außerhalb von BC1, ehrlich benannt.** n8n speichert Ausführungsdaten inklusive Chat-Eingabe in seinem eigenen Protokoll, bevor unser Dienst die Nachricht sieht. Das kann BC1 nicht filtern. Hosting-/Konfigurationsthema für B3 (Ausführungsdaten in n8n nicht speichern oder kurz aufbewahren).

**Abweichung von Issue #50.** Das Kriterium „Mapping liegt in separatem Speicher" wird nicht umgesetzt (Entscheidung 1). Wird beim PR im Issue begründet kommentiert.

**Messung (KPI `pii_erkennung`).** Ein Testset deutscher Interviewsätze mit erwarteter Ausgabe, erfundene Namen wie „Mustermann" (die Repo-Konvention „keine Namen" meint reale Personen). Gemessen wird je Klasse die Trefferquote (gefundene / vorhandene PII-Stellen) und die Fehltrefferquote auf den PII-freien Sätzen der drei Demo-Durchläufe (Ziel: null). Die Zahlen stehen im README und werden von einem Test als untere Schranke gehalten.

## Technischer Teil

### T1. Modul und Vertrag

- `bc1_core/pii.py`, nur Standardbibliothek (`re`). Eine öffentliche Funktion:

  ```python
  def ersetze_pii(text: str) -> str
  ```

- **Total:** wirft nie; leere Eingabe ergibt leere Ausgabe.
- **Deterministisch:** gleiche Eingabe, gleiche Ausgabe (Replay- und Idempotenz-Pfade des Kerns bleiben stabil).
- **Idempotent:** `ersetze_pii(ersetze_pii(x)) == ersetze_pii(x)`; bereits gesetzte Platzhalter werden nicht erneut ersetzt.
- Buchstaben je Klasse und Turn in Reihenfolge des Auftretens (A, B, …, Z, AA, AB, …); derselbe Wert (nach `strip`, Vergleich ohne Groß-/Kleinschreibung) im selben Turn ergibt denselben Platzhalter.
- Kein Rückgabewert außer dem Text (YAGNI). Zähler je Klasse für B7-Logging kommen, wenn B7 sie braucht.

### T2. Einhängung im Kern

- `bc1_core/core.py`, `process_turn`: `message = ersetze_pii(message)` **unmittelbar vor** `state.raw_log.append(...)` im Zweig für neue Nachrichten. Damit gilt der Filter für API (`/turn`), CLI (`run_scripted`) und Testprofil-Skripte gleichermaßen — ein Punkt, im Kern, wo auch die Persistenz liegt (Architektur-Invariante „Persistenz im Code-Kern").
- Der Crash-Resume-Pfad (`message = state.raw_log[-1][1]`) spielt den gefilterten Log-Text ab (für Turns, die unter B2 geloggt wurden; ältere Klartext-Einträge gibt es live nicht — nur Testprofile). Die Idempotenz je `message_id` ist unberührt.
- Auch die Anbieter-**Ausgaben** werden gefiltert (Code-Review 14.09.): Extraktionswerte vor der Normalisierung, der Antworttext vor dem Speichern — der Anbieter sieht nur Platzhalter, kann aber Klartext halluzinieren.
- Beide Anbieter-Pfade sehen nur gefilterten Text: `llm.extract(message, …)` bekommt den gefilterten Turn; `TurnKontext` (`nutzer_nachricht`, `neu_erfasst`, `profil_uebersicht`) entsteht aus gefilterten Werten.
- Transport (`api.py`) ändert sich nicht.

### T3. Muster, Reihenfolge und Grenzen

Reihenfolge von spezifisch nach allgemein, damit „Frau Dr. Erika Musterfrau" **ein** Platzhalter wird:

1. Kennungen bereits vorhandener Platzhalter als belegt vormerken (`\[(Person|E-Mail|Telefon|IBAN|Adresse) [A-Z]+\]`) — kein Muster trifft den Wortlaut eines Platzhalters, eine Segmentierung ist nicht nötig,
2. E-Mail, 3. IBAN, 4. Telefon, 5. Adresse (Straße + Hausnummer, optional PLZ + Ort; Weg/Platz nur mit PLZ + Ort), 6. Name mit Hinweiswort und Titel in **einem** Muster (Kennungen in Textreihenfolge).

Details, die der Plan als Tests festhält:
- Telefon: nur mit Präfix `+` oder führender `0`; „180 Fälle pro Jahr", „3 pro Woche", „45 Minuten" bleiben unberührt. Datumsformen (`2026-09-14`, `14.09.2026`) sind ausgeschlossen.
- Name: Hinweiswort + `(Dr\.|Prof\.)?` + ein bis drei Wörter mit großem Anfangsbuchstaben (inkl. Umlaute, Bindestrich) — drei, damit bei „Anna Maria Muster“ kein Nachname stehen bleibt (Übererkennung ist der akzeptierte Fehler, s. u.). Ein kleingeschriebenes Folgewort beendet den Namen („Herr Muster prüft" → nur „Muster"). „Frau des Kunden", „Kollegen aus dem Vertrieb" treffen nicht (Folgewort klein).
- Bekannte Fehltreffer, bewusst akzeptiert: „Dr. Oetker" (Firma) wird `[Person A]`; „Kollegin Buchhaltung" (ungewöhnliches Deutsch) und „Fr. Vormittag" ebenso; „Herrn Musters Freigabe" ersetzt beide Wörter. Übererkennung kostet Information, Untererkennung kostet Datenschutz — die Waage kippt zur Übererkennung. Bekannte Lücken neben nackten Nachnamen: Straßen ohne Straßenwort („Am Alten Markt 3").
- Platzhalter enthalten keine Ziffern, Kommas, Zeilenumbrüche: alleinstehend und in Text-/Listenfeldern passieren sie `LISTE` (trennt nur an `,`/`\n`), `_entferne_rand` (strippt keine Klammern) und die S-NN-Regel (`\bS-[0-9]{2}\b`) unverändert; in Zahlenfeldern gewinnt die Zahl (`ZAHL("30 pro Monat [Person A]")` → `"360"`), das ist gewollt (geprüft 14.09. in `feldtypen.py`, `paket_feldtypen.py`; Plan-Review M3).

### T4. Prompts

`bc1_service/prompts.py`: `SYSTEM_EXTRAKTION` und `SYSTEM_GESPRAECH` bekommen je einen Satz: *„Ausdrücke in eckigen Klammern wie [Person A] sind Platzhalter für entfernte personenbezogene Angaben. Übernimm sie wörtlich; löse sie nie auf und rate nicht, wer gemeint ist."* Alle drei Adapter nutzen diese Konstanten, also eine Änderung an einem Ort.

### T5. Tests (TDD, tdd-guard)

- `tests/test_pii.py`: je Klasse Positiv- und Negativfälle; Reihenfolge/Verschmelzung („Frau Dr. Erika Musterfrau" → ein Platzhalter); Buchstabenvergabe und Wiederverwendung im Turn; Determinismus; Idempotenz; leere Eingabe; keine Ausnahme bei beliebigem Text.
- `tests/test_core.py` (Ergänzung): nach einem Turn mit PII steht im `raw_log` nur der gefilterte Text, und der `FakeLLM` erhält den gefilterten Text (Skript auf gefilterten Text geschlüsselt).
- `tests/test_feldtypen.py` (Ergänzung): Round-Trip der Platzhalter durch `FREITEXT`, `LISTE`, `baue_system_typ`.
- KPI: `tests/pii_testset.py` (Sätze + erwartete Ausgabe, erfundene Namen) und ein Test, der je Klasse die Trefferquote misst und die im README dokumentierte Schranke hält; Fehltreffer auf den Demo-Sätzen aus `test_demo_durchlaeufe.py` = 0.
- Kein Netz, kein Modell: alles gegen Fake-LLM und Standardbibliothek. Bestehende Testskripte enthalten keine PII-Muster (gemessen 14.09.), bleiben also unverändert.

### T6. Doku und Nachhalten

- README-Abschnitt „PII-Filter": Klassen, Strategie (maskieren, kein Mapping), Lücken mit Auslöser, KPI-Zahlen, n8n-Grenze.
- `design/Abschlussplan-BC1.md`: B2-Zeile auf Stand; die vertagten Punkte oben in die Kleinpunkte, sofern nicht schon dort.
- BC0 informieren: BC1 liest keine Personennamen; das direkte SELECT-Recht von `bc1_role` auf `prozess_personen` ist für BC1 unnötig.
- Issue #50: Kommentar zur Abweichung (kein Mapping-Tresor) beim PR.

### T7. Aufwand und Schnitt

S–M. Ein Branch `bc1-b2-pii-konzept` (ab dem Bau-Zweig, bis PR #201 gemergt ist), ein PR. Ausgangslage Suite 502 passed / 4 skipped. Nicht Teil dieses Pakets: B7-Logging, NER, Rückersetzung, Migration.
