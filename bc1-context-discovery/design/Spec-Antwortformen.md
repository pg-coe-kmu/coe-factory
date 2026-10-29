# Spec: Natürliche Antworten richtig erfassen — nichts erfinden, KI kennt Frage und Antwortform, zwei Prüfschichten

> Stand 29.10.2026, **Entwurf 2**. Anlass: Generalprobe 2 auf BC0s Server (Testanfrage A-2026-08, KP-02.TP-2, 29.10.): 25 von 26 Pflichtfeldern.
> - **Quellen:** gespeicherte Sitzung und Profil (nur lesend gemessen), BC1-Log vom Server, Code auf `main` @ `4ead3de`, Proben an Kurzformen/Normalisierern/Prüfern.
> - **Vorgänger:** `design/Spec-Extraktion-gestellte-Frage.md` (Kurzantworten, gemergt mit #367).
> - **Geprüft:** Entwurf 1 von Codex (1 Critical, 8 Important, 2 Minor), agy (3 C, 6 I, 4 M) und einem unabhängigen Claude-Prüfer (1 C, 9 I, 6 M) — einhellig „so nicht bauen“. Entwurf 2 baut die Befunde ein (Abschnitt 10).
> - **Termin:** Vorführung Dienstag 03.11.2026. Plan und Rückfallebene in Abschnitt 9.
> - **Nächster Schritt:** Zweitmeinungen zu Entwurf 2 (Codex, agy, Claude-Prüfer), dann Abnahme durch die BC1-Projektleitung.

---

## Big Picture

**Was passiert ist.** Die Kurzantworten aus #367 funktionieren live (zehn nackte Antworten landeten beim ersten Mal ohne KI im richtigen Feld). Zwei natürliche Antworten scheiterten: „Lead qualifizieren“ (Name statt Kennung) und „Ja Systeme wechseln“ (Ja mit Zusatz); die Nachfrage machte aus der Ja/Nein-Frage eine Frage mit drei Möglichkeiten.

**Was die Prüfung von Entwurf 1 zusätzlich gezeigt hat.**
- **Die Extraktions-KI kennt die gerade gestellte Frage nicht und soll Werte „wörtlich“ übernehmen** (`prompts.py`: „Werte wörtlich bzw. minimal normalisiert“). Die erlaubten Werte standen bei E5 sogar im Fragetext („KP-02.TP-2 = Lead qualifizieren“) — die KI hat trotzdem den Namen geliefert.
- **Still falsche, aber gültige Werte sind heute schon möglich**, wenn die KI einen Satz wörtlich weiterreicht, weil die Normalisierer eine Zahl aus dem Satz lesen: „jeden 2. Monat“ → 24 pro Jahr (richtig 6), „1 Stunde und zehn Minuten“ → 60 Minuten, „nicht 3 Stunden“ → 180, „Ja?“ → ja. Ein falscher Wert ist schlimmer als ein leeres Feld: niemand bemerkt ihn.
- **Viele natürliche Antworten scheitern** in mindestens 15 von 18 Feldern mit festem Typ: „Zeit sparen“, „einzelner Schritt“, „E-Mail“, „geschätzt“, „wöchentlich“, „eine halbe Stunde“, „5 Leads“, „4 von 5“, „nö“ …
- **Die Nachfrage-Regel „nenne in der Frage enthaltene Optionen vollständig“** hat das „oder“ einer Ja/Nein-Frage zu Antwortoptionen gemacht.
- Eine einfache Ja/Nein-Regel „beginnt mit Ja → ja“ (Entwurf 1) wäre gefährlich: „Ja, eigentlich nicht“, „Ja, keine Ahnung“ würden „ja“.

**Grundsatz dieses Pakets: nichts erfinden.** Eindeutige Antworten werden richtig erfasst — gleich, ob kurz, mit Namen, mit Umlaut oder als Satz. Unsichere, eingeschränkte, widersprüchliche oder mehrdeutige Antworten führen zu einer **verständlichen Nachfrage**, nie zu einem geratenen Wert.

**Was wir ändern.**
1. **Die Extraktions-KI kennt die gerade gestellte Frage und die erlaubte Antwortform jedes Felds** (z. B. „ja oder nein“, „Kennung KP-02.TP-2 (= Lead qualifizieren)“, „Zahl pro Woche/Monat/Jahr“, „Dauer in Minuten oder Stunden“) und liefert Werte in dieser Form; eindeutige Umformungen sind erwünscht („wöchentlich“ → „1 pro Woche“, „eine halbe Stunde“ → „30 Minuten“), Unsicheres lässt sie weg.
2. **Feste Regeln im Code, nur wo sie sicher sind:** ein einheitlicher Vergleich für alle Auswahlfelder (Groß/Klein, Umlaut, Unterstrich/Bindestrich/Leerraum), dazu Anzeigenamen (Teilprozess, Rolle, Kernprozess) und wenige Synonyme („E-Mail“ → mail). **„?“ heißt: keine Festlegung.** **Die Normalisierer lesen keine Zahlen mehr aus ganzen Sätzen** — sie nehmen nur noch die eindeutigen Formen an.
3. **Die Nachfrage bekommt die Antwortform fest aus dem Feldtyp** und bittet ausdrücklich darum („Bitte mit Ja oder Nein antworten“), mit derselben Bedeutung von Ja/Nein, derselben Skalenrichtung, denselben Optionen.
4. **Zwei Prüfschichten:** (a) ein **Antwortkatalog** natürlicher Antworten als normaler Test ohne KI (läuft immer, kostet nichts); (b) ein **Prüfwerkzeug mit echter KI**, das ganze Gespräche mit diesem Katalog durchspielt, Nachfragen absichtlich auslöst und ihren Wortlaut prüft — fester Schritt vor jeder Generalprobe.

**Was nicht.** Keine Änderung an Fragetexten, Paketfassung, Datenbank oder BC2-Vertrag; gespeichert werden weiter Kennungen und „ja“/„nein“. Keine eigene Sprachlogik für Zahlwörter oder Wort-Häufigkeiten im Code (das macht die KI mit Antwortform; feste Regeln kommen nur dazu, wo das Prüfwerkzeug Lücken zeigt).

**Erfolg (Abnahme).**
1. Antwortkatalog (Schicht a) grün: jede Katalogantwort führt auf dem festen Weg zum erwarteten Wert **oder** ausdrücklich zu „Nachfrage erwartet“; **kein Eintrag erzeugt einen falschen gültigen Wert**.
2. Prüfwerkzeug (Schicht b) gegen die echte KI, je Szenario zwei Läufe: keine Antwort mit falschem Wert, kein aufgegebenes Pflichtfeld, jede natürliche Antwort im ersten Versuch richtig außer „Nachfrage erwartet“, Nachfragetexte bestehen die Prüfregeln (Abschnitt 6).
3. Generalprobe 3 über BC0s App mit natürlichen Antworten: 26/26, kein falscher Wert.

---

## Technischer Teil

### 1. Antwortform je Feldtyp (`bc1_core/feldtypen.py`)

`Feldtyp` erhält ein Merkmal **`antwortform: str`** (Text für KI-Prompts, deutsch, ohne Feldnamen). Vorgabe für die bestehenden Typen:

| Typ | Antwortform |
|---|---|
| JA_NEIN | „ja oder nein“ |
| SKALA_1_5 | „eine Ziffer von 1 bis 5“ |
| ANZAHL | „eine Zahl (Anzahl)“ |
| ZAHL (Häufigkeit) | „Zahl pro Woche, pro Monat oder pro Jahr, z. B. ‚2 pro Monat‘“ |
| MINUTEN | „Dauer als Zahl mit ‚Minuten‘ oder ‚Stunden‘, z. B. ‚90 Minuten‘“ |
| PROZENT_0_100 / PROZENT_GANZ_0_100 | „Zahl von 0 bis 100“ / „ganze Zahl von 0 bis 100“ |
| AUSWAHL | „genau eine von: “ + Optionen, je mit Anzeigename, falls vorhanden („KP-02.TP-2 (= Lead qualifizieren)“) |
| FREITEXT / LISTE / Systemtyp | „Text“ / „Liste, durch Kommas getrennt“ / „Liste; bekannte Systeme mit Kennung S-NN“ |

Die Antwortform ist reine Beschreibung; Prüfer und gespeicherte Werte ändern sich dadurch nicht.

### 2. Extraktion kennt Frage und Antwortform (`bc1_service/prompts.py`, drei Adapter)

- **Ein gemeinsamer Helfer** `extraktions_nutzer_prompt(message, package, state)` in `prompts.py` (Muster: `gespraech_nutzer_prompt`, schon von allen Adaptern geteilt). Gemini-, Claude- und Ollama-Adapter rufen ihn statt der eigenen Zeile `"- {f.name}: {f.question}"`. **Kein Protokollwechsel:** `extract(message, package, state)` bekommt den Zustand schon; der Helfer bestimmt das gefragte Feld mit `zuletzt_gefragt(state)`.
- **Inhalt:** (a) „Gerade gestellte Frage: <Feldname> — <Fragetext> (Antwortform: …)“, falls vorhanden; (b) die Feldliste mit je Fragetext und Antwortform; (c) die Nachricht.
- **`SYSTEM_EXTRAKTION` neu, sinngemäß:** „Die Nachricht beantwortet in erster Linie die gerade gestellte Frage; andere Felder nur, wenn die Nachricht sie ausdrücklich belegt. Liefere jeden Wert **in der Antwortform des Felds**: bei Auswahl die Kennung (nicht den Namen), bei Ja/Nein ‚ja‘ oder ‚nein‘, Zahlen mit der genannten Einheit bzw. dem Zeitraum. Eindeutige Umformungen sind erwünscht (‚wöchentlich‘ → ‚1 pro Woche‘, ‚eine halbe Stunde‘ → ‚30 Minuten‘, ‚jeden 2. Monat‘ → ‚6 pro Jahr‘). **Lass ein Feld weg**, wenn die Angabe unsicher, eingeschränkt, widersprüchlich, eine Spanne, eine Gegenfrage oder nur mit einer Annahme umrechenbar ist (z. B. ‚vielleicht‘, ‚weiß nicht‘, ‚Ja, eigentlich nicht‘, ‚2–3 Stunden‘, ‚täglich‘, ‚2 Tage‘, ‚eher gut‘). Nichts erfinden.“ Der PII-Hinweis bleibt.
- **Bewusst als Nachfrage** (nicht von der KI umzurechnen): „täglich/pro Tag“ (Arbeits- oder Kalendertage?), Dauern in Tagen/Wochen (Arbeits- oder Durchlaufzeit? Vertrag mit BC2: Jahresminuten = D1 × E1), Spannen, „teilweise/manchmal/eher ja“, qualitative Skalenwörter („eher gut“). Entscheidung 8.1.

### 3. Feste Regeln im Code

**3.1 „?“ heißt keine Festlegung.** `_entferne_rand` entfernt kein „?“ mehr; steht irgendwo ein „?“, bleibt der Wert in Ja/Nein- und Auswahl-Normalisierern unverändert (ungültig → Nachfrage). Heute wird „Ja?“ zu „ja“ und „KP-03.TP-1?“ auf dem KI-Weg gültig — das ändert sich bewusst.

**3.2 Ja/Nein:** Normalisierer und Kurzform bleiben bei genau „ja“/„nein“ (mit Rändern wie heute, ohne „?“). **Keine Präfixregel.** „Ja, …“-Sätze wandelt die KI mit Fragebezug um oder lässt sie weg.

**3.3 Auswahl: einheitlicher Vergleich, Namen, Synonyme.** `AUSWAHL(*optionen, namen=None, synonyme=None)`:
- **Vergleichsschlüssel** für Eingabe, Optionen, Namen und Synonyme gleichermaßen: Unicode NFC, `casefold()`, ä/ö/ü/ß ↔ ae/oe/ue/ss, „_“, „-“ und Leerraum zu einem Leerzeichen, Ränder wie `_entferne_rand` (ohne „?“).
- **Treffer:** Schlüssel gleich einer Option → Option; gleich dem Schlüssel **genau eines** Namens oder Synonyms → zugehörige Option. Mehrdeutige Schlüssel (zwei Optionen) und leere Namen werden nicht übersetzt; eine Kennung gewinnt vor einem gleichlautenden Namen.
- **Normalisierer und Kurzform** nutzen denselben Abgleich (Kurzform weiter eng: ganze Nachricht, höchstens ein „.“/„!“ am Ende).
- **Prüfer unverändert** (gültig nur die Optionen); gespeichert wird immer die Kennung bzw. Option.
- **Woher:** `discovery_paket.py` übergibt B3 `kontext.rollen`, B4 `kontext.prozesse`, E5 `kontext.teilprozesse` als Namen. Synonyme nur für feste Auswahlfelder und nur, wo der Schlüssel nicht reicht: C3 mail ← „E-Mail“, „Email“; A3 ganzer_prozess ← „den ganzen Prozess“, einzelner_schritt ← „ein einzelner Schritt“; E3 aus_system ← „aus dem System“. („Zeit sparen“, „einzelner Schritt“, „geschätzt“, „aus System“ löst schon der Schlüssel.)
- **Paket-Fingerprint:** Namen wirken jetzt auf die Eingabe-Auslegung. Der Fingerprint (`_ctx_fingerprint`) nimmt deshalb auch die Namen auf; damit ändert sich die Kontext-Kennung in `schema_version` (Teil nach `+ctx-`), nicht die Paketfassung 1.2. Folge: Sitzungen, die vor dem Update begonnen wurden, laufen in den bestehenden Paket-Schutz — vor dem Update ohnehin per Messung ausgeschlossen. Entscheidung 8.4.

**3.4 Normalisierer lesen keine Zahlen mehr aus Sätzen.** Zahl-, Dauer-, Anzahl-, Prozent- und Skalen-Normalisierer nehmen nur noch die **ganze Eingabe** in den eindeutigen Formen an (dieselben Formen wie die Kurzformen aus #367, plus nackte Zahl, wo der Typ sie heute schon meint). Alles andere bleibt unverändert (ungültig → Nachfrage). Damit fallen weg: „jeden 2. Monat“ → 24, „1 Stunde und zehn Minuten“ → 60, „nicht 3 Stunden“ → 180, „30 Minuten pro Lead“ → 30.
- **Invariante „Normalisierer ⊇ Kurzform“:** was die Kurzform annimmt, nimmt auch der Normalisierer an, mit demselben Ergebnis (heute verletzt: `SKALA_1_5.normalisiere("4.")` ungültig, Prozent „70 Prozent“ auf dem KI-Weg ungültig).
- Totalität bleibt (wirft nie). Gespeicherte Form unverändert.

### 4. Nachfrage mit Antwortform (`bc1_core/gespraech.py`, `bc1_service/prompts.py`)

- `TurnKontext` erhält `antwortform: str | None` des gefragten Felds (aus `spec.typ.antwortform`).
- Nachfrage-Text an die Gesprächs-KI, sinngemäß: „Frage nach **demselben Gegenstand** wie die Kernfrage. Antwortform: <…>. **Bitte ausdrücklich um eine Antwort in dieser Form** (bei Ja/Nein: ‚mit Ja oder Nein‘). Ja und Nein bedeuten dasselbe wie in der Kernfrage (nicht umkehren, nicht verneinen). Bei einer Skala bleiben Richtung und Endpunkte. Nenne nur Optionen, die die Antwortform vorgibt — ein ‚oder‘ in einer Ja/Nein-Frage ist keine Auswahl.“ Die Regel „nenne in der Frage enthaltene Optionen vollständig“ wird dadurch ersetzt. Zweck erklären, Beispiel, „Feld darf offen bleiben“ bleiben.

### 5. Schicht a — Antwortkatalog als Test ohne KI

- **Katalog** als Daten im Repo (eine Datei, von Test und Werkzeug gemeinsam genutzt): je Pflichtfeld mit festem Typ (A2, A3, B3, B4, C3, D1, D4, E1, E5, E2, E3, E4, F3, G1, G2, G4, G5, I1) natürliche Antworten mit Erwartung: **Wert** oder **„Nachfrage erwartet“**. Pflichtinhalt: die Beispiele aus den drei Prüfberichten (Tabellen „26 Felder × natürliche Antworten“), darunter die gefährlichen Fälle („jeden 2. Monat“, „nicht 3 Stunden“, „Ja, eigentlich nicht“, „Ja?“), Namen mit Bindestrich/„+“/„&“/Umlaut, Synonyme.
- **Prüft zwei Wege:** (1) direkt: Kurzform → Normalisierer → Prüfer; (2) „KI reicht wörtlich durch“: Normalisierer → Prüfer auf dem Rohtext. Auf **keinem** Weg darf ein falscher gültiger Wert entstehen; „Nachfrage erwartet“ heißt: ungültig oder keine Kurzform.
- Plus Eigenschaftstest „Normalisierer ⊇ Kurzform“ über alle Katalogeinträge.
- Was nur die KI lösen kann („wöchentlich“, „eine halbe Stunde“), ist im Katalog für Schicht b markiert und in Schicht a als „auf festem Weg: Nachfrage“ geführt.

### 6. Schicht b — Prüfwerkzeug mit echter KI

- **Ort:** `bc1-context-discovery/werkzeuge/` (nicht im Image, nicht in der Suite, nicht in der CI). Architektur-Invariante „Tests gegen Fake-LLM, kein Netz in Tests“ unberührt: Das Werkzeug ist kein Test; es ruft nur `process_turn` (mit `InMemoryStateStore`, `baue_discovery_paket(kontext=…)`, KI-Adapter hinter dem LLM-Client) und befüllt nie selbst den Zustand. Seine eigene Ablauf- und Auswertelogik ist mit der Test-KI in der Suite getestet.
- **Modell** wie auf dem Server (`gemini-3.8-flash`, Adapter über `BC1_LLM` wählbar), bezahlter Tarif (Projektleitung 29.10.).
- **Testkontext:** generisch, aber realistisch (Namen mit Bindestrich, „+“, „&“, Umlaut; mehrere Teilprozesse; Rollen; Kernprozesse; Systeme).
- **Szenarien, je unabhängig gestartet:**
  1. **Grundlauf** — kurze Startnachricht (nur A1/A2/A3/B1), sodass B3, B4, E5 und die übrigen Felder einzeln gefragt werden; Antworten mit Kennungen und Kurzformen.
  2. **Natürlich** — dieselbe Struktur, Antworten aus dem Katalog in natürlicher Form (Namen, Umlaute, „wöchentlich“, „eine halbe Stunde“, „5 Leads“, „4 von 5“, „Ja, müssen wir“, „nö“ …).
  3. **Nachfragen** — für je ein Ja/Nein-, Auswahl- und Skalenfeld zuerst eine unbrauchbare Antwort („Wie meinen Sie das?“), dann die richtige; der Nachfragetext wird geprüft: Ja/Nein nennt „Ja“ und „Nein“; Auswahl nennt alle Optionen; Skala nennt 1 und 5 und die Richtung der Kernfrage; ausgegeben zum Lesen.
  4. **Nachfrage erwartet** — „täglich“, „2–3 Stunden“, „2 Tage“, „eher gut“, „Ja, keine Ahnung“, „Ja?“: erwartet ist eine Nachfrage, **kein** Wert.
- **Laufvertrag:** Schleife solange Status „frage“; Antwort je **gefragtem Feld** (`payload["feld"]`) aus dem Szenario; `fehler_fortsetzbar` → einmal dieselbe Nachricht wiederholen, dann Abbruch „technisch nicht abgeschlossen“ (kein Feldfehler); Höchstzahl an Turns; Aufrufzähler.
- **Bericht je Feld:** gesendete Antworten, Zahl der Nachfragen, Endwert, erwartet, Ergebnis (✓ im 1. Versuch · ✓ nach erwarteter Nachfrage · ✗ falscher Wert/aufgegeben/unerwartete Nachfrage · „nicht geprüft“); Nachfragetexte; Modell, Code-Stand, Szenario. Ein Wert für ein **anderes** Feld, der sich durch die Antwort ändert, ist ✗.
- **Umgang mit ✗:** nie den Katalog still anpassen. Entweder Code/Prompt ändern (mit Test) oder den Eintrag mit Begründung auf „Nachfrage erwartet“ setzen (Entscheidung der Projektleitung bei Bedeutungsfragen).

### 7. Tests (Test zuerst, gegen die Test-KI)

1. Antwortform je Typ (Tabelle Abschnitt 1).
2. Extraktions-Prompt: enthält gefragtes Feld mit Frage und Antwortform; Feldliste mit Antwortformen; neue Regeln; alle drei Adapter nutzen den Helfer (Muster bestehender Adapter-Tests).
3. „?“-Regel; Ja/Nein exakt.
4. Auswahl: Schlüssel (Groß/Klein, Umlaut, „_“/„-“/Leerraum, NFC), Namen, Synonyme, Mehrdeutigkeit, leere Namen, Kennung vor Name, ohne Namen wie heute; Prüfer unverändert; B3/B4/E5 im Paket; Fingerprint mit Namen.
5. Normalisierer streng: die gefährlichen Fälle werden ungültig; die eindeutigen Formen bleiben; Invariante ⊇ Kurzform.
6. Nachfrage-Prompt mit Antwortform; alte Optionen-Regel ersetzt (bestehenden Test anpassen).
7. Katalogtest (Schicht a).
8. Nachspiel Generalprobe 2 mit Test-KI: „Lead qualifizieren“ (Kurzform jetzt direkt) und „Ja Systeme wechseln“ (Test-KI liefert „ja“ wie mit dem neuen Prompt erwartet; liefert sie wörtlich, bleibt es ungültig → Nachfrage, kein falscher Wert).
9. Werkzeug: Ablauf und Auswertung mit Test-KI (Feldzuordnung, Nachfrage-Szenario, „nicht geprüft“, Abbruch bei Fehler).
10. Bestehende Tests, die sich bewusst ändern, im Plan ausweisen (u. a. `test_extractor.py` „Erfassen“ wird Kurzform; `test_feldtypen.py` „geschätzt“; Normalisierer-Tests mit Sätzen; `test_prompts.py` Optionen-Regel).

### 8. Entscheidungen für die BC1-Projektleitung

1. **Grundsatz „nichts erfinden“** (Empfehlung): „täglich“, Dauern in Tagen/Wochen, Spannen, „teilweise/eher ja“, qualitative Skalenwörter führen zur Nachfrage.
2. **KI kennt Frage und Antwortform jetzt** (Empfehlung) — die eigentliche Ursache; ein gemeinsamer Helfer für alle drei Adapter.
3. **Normalisierer streng** (Empfehlung) — keine Zahl mehr aus Sätzen; was die KI nicht in die Antwortform bringt, wird nachgefragt statt falsch gespeichert.
4. **Namen im Fingerprint** (Empfehlung) — sicher gegen Umbenennung zwischen zwei Turns; Folge: neue Kontext-Kennung nach dem Update (vorher messen).
5. **Fester Code nur für Schlüssel, Namen, wenige Synonyme und „?“** (Empfehlung); Zahlwörter, „wöchentlich“, „4 von 5“, „nö“ löst die KI mit Antwortform; feste Regeln nur nachziehen, wo das Prüfwerkzeug Lücken zeigt.
6. **Prüfwerkzeug: vier Szenarien, je zwei Läufe, gleiches Modell wie der Server** (Empfehlung); fester Schritt vor jeder Generalprobe und vor jedem Update, das Dialog oder Extraktion berührt (in BETRIEB.md und Abschlussplan).
7. **Generalprobe 3 an KP-03.TP-1** mit natürlichen Antworten (Empfehlung), nach Merge, Update mit Ansage an BC0 und Werkzeug-Abnahme.

### 9. Plan bis Dienstag und Rückfallebene

- **Do 29.10. abends:** Entwurf 2, Zweitmeinungen. **Fr 30.10.:** Abnahme der Spec, Implementierungsplan (geprüft), Bau Teil 1 (Abschnitte 1–4, Katalogtest). **Sa 31.10.:** Bau Teil 2 (Werkzeug), Gesamtprüfung, Werkzeug-Läufe gegen die echte KI, Nachbesserung. **So 01.11.:** PR, Merge nach OK, Tag, Update mit Ansage, Generalprobe 3. **Mo 02.11.:** Puffer, UC1-Testanfrage KP-06.TP-2 für die Vorführung.
- **Rückfallebene**, falls bis Montag 12 Uhr nicht alles abgenommen ist: Vorführung mit dem heutigen Stand (`bc1-kurzantworten-2026-10-29`) und einer Antwortliste mit Kennungen und kurzen Antworten — ehrlich angesagt als bekannte Grenze; das Paket folgt danach. Kein halbfertiger Stand auf dem Server.

### 10. Was aus der Prüfung von Entwurf 1 wurde

| Befund (Prüfer) | Entwurf 2 |
|---|---|
| Ja/Nein-Präfixregel erzeugt falsche Werte (alle drei, Critical) | gestrichen; KI mit Fragebezug, Normalisierer exakt (3.2) |
| „Ja?“ wird heute „ja“; „?“ uneinheitlich (alle drei) | „?“ = keine Festlegung (3.1) |
| Extraktion kennt die Frage nicht; Anweisung „wörtlich“ ist die Ursache (alle drei) | Abschnitt 2 |
| Viele natürliche Antworten scheitern (alle drei, Critical Claude) | Antwortform + KI-Umformung (2), Schlüssel/Namen/Synonyme (3.3), Katalog (5), Werkzeug (6) |
| Still falsche Werte aus Sätzen („jeden 2. Monat“ → 24 …) (Codex) | Normalisierer streng (3.4) |
| Normalisierer ⊉ Kurzform („4.“, „70 Prozent“) (Claude) | Invariante (3.4, 5) |
| Optionen-Regel erklärt die Dreifach-Nachfrage; Polarität fehlt (alle drei) | Abschnitt 4 |
| Namen wirken auf die Auslegung → Fingerprint (Codex) | 3.3, Entscheidung 4 |
| Namensregel zu eng (Bindestrich, Umlaut, Leerraum, Aliase) (Claude, Codex) | Schlüssel + Synonyme (3.3) |
| Werkzeug: Varianten werden nicht geprüft, Nachfrage nicht gemessen, Laufvertrag, Kontingent, glatter Testkontext (alle drei) | Szenarien, Laufvertrag, Bericht, Testkontext (6); Tarif bezahlt |
| Billige deterministische Schicht fehlt (Claude) | Schicht a (5) |
| Abschnitt 5 nicht ehrlich genug: Risiken waren bekannt und auf „live messen“ vertagt; es gibt echte KI-Stichproben (`tests/test_gemini_echt.py`) (Claude, Codex) | Abschnitt 11 |
| „geschätzt … erledigt“ zu stark (Claude, Codex) | Schlüssel löst es fest (3.3) |

### 11. Warum unsere Prüfungen das nicht gefunden haben (für den Abschlussplan)

- **Die normalen Tests laufen gegen eine Test-KI**; es gibt nur kleine echte KI-Stichproben (`tests/test_gemini_echt.py` u. a.), kein ganzes Gespräch mit natürlichen Antworten.
- **Die Testantworten wurden passend zu dem gewählt, was BC1 kann** — in beiden Generalproben-Antwortlisten und in den Nachspiel-Tests (dort füllt die Test-KI elf Felder aus einer kurzen Startnachricht).
- **Bekannte Risiken wurden auf „live messen“ vertagt** statt vorher geprüft: Namen statt Kennung (Abschlussplan (g), seit 24.10.), umformulierte Nachfrage (Messpunkt), „Ja, aber selten“ ausdrücklich keine Kurzform (#367). Die Generalprobe war damit das Messinstrument.
- **Die Prüfungen prüften gegen eine zu enge Spec.** Der Weg über die KI mit ganzen Sätzen lag außerhalb.
- **Folge:** Schicht a und b (Abschnitte 5, 6) sind fester Bestandteil; Antwortlisten für Generalproben enthalten absichtlich natürliche Antworten; neue Specs, die Dialog oder Extraktion berühren, nennen ausdrücklich, welche natürlichen Antworten sie abdecken.

### 12. Roadmap (Abschlussplan, je mit Ziel und nächstem Schritt)

- (1) „KI kennt die gestellte Frage“: mit diesem Paket umgesetzt (Abschnitt 2); Messung über Schicht b.
- Messpunkt „Nachfrage formuliert frei um“: eingetreten in Generalprobe 2 → Abschnitt 4; gemessen in Schicht b Szenario 3.
- (g) Namen statt Kennung bei B3/B4/E5: erledigt (3.3). „Ja, stimmt“ auf den BC0-Vorschlag bei B3: KI mit Fragebezug, gemessen in Schicht b; fehlt es dort, fester Fall im nächsten Paket.
- (6) Umlaut bei E3: erledigt (3.3).
- (7) Ausrollen und zweite Generalprobe: erledigt (25/26). Neuer Punkt **Generalprobe 3** (Abschnitt 8.7).
- Neu: **Prüfwerkzeug als fester Schritt** vor Generalprobe und Update (BETRIEB.md).
