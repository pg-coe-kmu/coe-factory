# Spec: Natürliche Antworten richtig erfassen — nichts erfinden, KI kennt Frage und Antwortform, zwei Prüfschichten

> Stand 30.10.2026, **Entwurf 3, gebaut auf Zweig `bc1-antwortformen`** (nicht gemergt). Anlass: Generalprobe 2 auf BC0s Server (Testanfrage A-2026-08, KP-02.TP-2, 29.10.): 25 von 26 Pflichtfeldern.
> - **Quellen:** gespeicherte Sitzung und Profil (nur lesend gemessen), BC1-Log vom Server, Code auf `main` @ `4ead3de`, Proben an Kurzformen/Normalisierern/Prüfern.
> - **Vorgänger:** `design/Spec-Extraktion-gestellte-Frage.md` (Kurzantworten, gemergt mit #367).
> - **Geprüft:** Entwurf 1 von Codex (1 Critical, 8 Important, 2 Minor), agy (3 C, 6 I, 4 M) und einem unabhängigen Claude-Prüfer (1 C, 9 I, 6 M) — einhellig „so nicht bauen“ (Abschnitt 10). Entwurf 2 von agy (1 C, 5 I, 3 M) und einem Claude-Prüfer (0 C, 5 I, 11 M, „Bau freigeben mit fünf Auflagen“); Entwurf 3 baut beide ein (Abschnitt 13).
> - **Abnahme:** Entwurf 2 mit allen Empfehlungen (Abschnitt 8) von der BC1-Projektleitung abgenommen; die Empfehlungen der Prüfer zu Entwurf 2 gelten als angenommen (Abschnitt 13).
> - **Termin:** Vorführung Dienstag 03.11.2026. Plan und Rückfallebene in Abschnitt 9.
> - **Nachprüfung Entwurf 3** (agy): baufertig, 0 C, 1 I, 3 M — eingearbeitet (Identitätsbezug im Prompt markieren, Abschnitt 2; Systemtyp ohne Nachfrage-Antwortform, 4; Grammatik um „/“ und Form der Invariante, 3.4; Testliste, 7.10).
> - **Nächster Schritt:** Läufe des Prüfwerkzeugs (Abschnitt 6), Gesamtprüfung, dann Merge.

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
2. Prüfwerkzeug (Schicht b) gegen die echte KI — Szenarien 1, 3 und 4 je zwei Läufe, Szenario 2 als Variantenreihe mit mindestens drei Läufen: keine Antwort mit falschem Wert (auch kein anderer gültiger Wert als erwartet), kein aufgegebenes Pflichtfeld, jede natürliche Antwort im ersten Versuch richtig außer „Nachfrage erwartet“ und Grenzfällen, Nachfragetexte bestehen die Prüfregeln (Abschnitt 6).
3. Generalprobe 3 über BC0s App mit natürlichen Antworten: 26/26, kein falscher Wert.

---

## Technischer Teil

### 1. Antwortform je Feldtyp (`bc1_core/feldtypen.py`)

`Feldtyp` erhält ein Merkmal **`antwortform: str`** (Text für KI-Prompts, deutsch, ohne Feldnamen). Vorgabe für die bestehenden Typen:

| Typ | Antwortform |
|---|---|
| JA_NEIN | „ja oder nein“ |
| SKALA_1_5 | „eine Ziffer von 1 bis 5“ |
| ANZAHL | „nur eine Zahl, ohne Einheit, z. B. ‚5‘“ |
| ZAHL (Häufigkeit) | „Zahl pro Woche, pro Monat oder pro Jahr, z. B. ‚2 pro Monat‘“ |
| MINUTEN | „Dauer als Zahl mit ‚Minuten‘ oder ‚Stunden‘, z. B. ‚90 Minuten‘“ |
| PROZENT_0_100 / PROZENT_GANZ_0_100 | „Zahl von 0 bis 100“ / „ganze Zahl von 0 bis 100“ |
| AUSWAHL | „genau eine von: “ + Optionen, je mit Anzeigename, falls vorhanden („KP-02.TP-2 (= Lead qualifizieren)“) |
| FREITEXT / LISTE / Systemtyp | „Text“ / „Liste, durch Kommas getrennt“ / „Liste der genannten Systeme, durch Kommas getrennt; Kennungen S-NN nur, wenn die Nachricht sie nennt“ |

Die Antwortform ist reine Beschreibung; Prüfer und gespeicherte Werte ändern sich dadurch nicht.
- **Pflichtmerkmal ohne Vorgabe** (`field(kw_only=True)`): kein Typ erbt still eine falsche Beschreibung; alle Konstruktoren in `feldtypen.py` und `paket_feldtypen.py` setzen es.
- **Systemtyp:** Der Kontext kennt keine Systemnamen; eine Antwortform „bekannte Systeme mit Kennung“ würde erfundene, gültige S-NN-Kennungen einladen.
- **Bekannte Grenze:** Im kontextfreien Zweig ist D4 ein ZAHL-Feld; die Antwortform passt dort nicht genau. Hingenommen, im Plan vermerkt.

### 2. Extraktion kennt Frage und Antwortform (`bc1_service/prompts.py`, drei Adapter)

- **Ein gemeinsamer Helfer** `extraktions_nutzer_prompt(message, package, state)` in `prompts.py` (Muster: `gespraech_nutzer_prompt`, schon von allen Adaptern geteilt). Gemini-, Claude- und Ollama-Adapter rufen ihn statt der eigenen Zeile `"- {f.name}: {f.question}"`. **Kein Protokollwechsel:** `extract(message, package, state)` bekommt den Zustand schon; der Helfer bestimmt das gefragte Feld mit `zuletzt_gefragt(state)`.
- **Inhalt:** (a) „Gerade gestellte Frage: <Feldname> — <Fragetext> (Antwortform: …)“, falls vorhanden; (b) die Feldliste mit je Fragetext und Antwortform; (c) die Nachricht. Felder mit `spec.identitaetskritisch` tragen in (a) und (b) den Zusatz „Identitätsbezug“ — genau der Begriff, den `SYSTEM_EXTRAKTION` aufgreift; sonst wüsste die KI nicht, für welches Feld die Identitätsregel gilt.
- **`SYSTEM_EXTRAKTION` neu, sinngemäß:** „Die Nachricht beantwortet in erster Linie die gerade gestellte Frage; andere Felder nur, wenn die Nachricht sie ausdrücklich belegt. Liefere jeden Wert **in der Antwortform des Felds**: bei Auswahl die Kennung (nicht den Namen), bei Ja/Nein ‚ja‘ oder ‚nein‘, bei Häufigkeit und Dauer mit Zeitraum bzw. Einheit, bei Anzahl, Skala und Prozent nur die Zahl. **Freitext und Listen: wörtlich bzw. minimal normalisiert, Platzhalter unverändert.** Eindeutige Umformungen sind erwünscht (‚wöchentlich‘ → ‚1 pro Woche‘, ‚eine halbe Stunde‘ → ‚30 Minuten‘, ‚jeden 2. Monat‘ → ‚6 pro Jahr‘). **Ergänze nie eine Einheit oder einen Zeitraum, den die Nachricht nicht nennt.** **Felder mit Identitätsbezug nur, wenn die Nachricht die Kennung oder den Namen eindeutig nennt** — keine Teilnamen, Ordinalzahlen oder Umschreibungen. **Lass ein Feld weg**, wenn die Angabe unsicher, eingeschränkt, widersprüchlich, eine Spanne oder eine Gegenfrage ist, ein ‚?‘ enthält, sich auf eine andere Bezugsgröße bezieht als die Frage, mehrere Optionen nennt, wo eine verlangt ist, oder nur mit einer Annahme umrechenbar ist (z. B. ‚vielleicht‘, ‚weiß nicht‘, ‚Ja, eigentlich nicht‘, ‚KP-03.TP-1?‘, ‚2–3 Stunden‘, ‚täglich‘, ‚2 Tage‘, ‚30 Minuten pro Lead‘, ‚eher gut‘, ‚Ja‘ auf eine Skalenfrage). Nichts erfinden.“ Der PII-Hinweis bleibt.
- **Warum Freitext wörtlich bleibt:** BC2 bindet Rollen, Systeme und offene Anmerkungen als Text (`contracts/bc1-to-bc2/README.md`); die Umformungsregel gilt nur für Felder mit festem Typ.
- **Warum die Identitätsregel:** E5 legt fest, welcher Teilprozess beschrieben wird (`spec.identitaetskritisch`), und ist mit „fertig“ endgültig. Eine KI-Umformung von „die Qualifizierung“, „der zweite Schritt“ oder „Lead“ auf eine bestehende, aber falsche Kennung wäre gültig und falsch. Die Regel wird generisch über `spec.identitaetskritisch` in den Prompt geschrieben (nicht über Feldnamen). Eine feste Sperre im Code steht auf der Roadmap (Abschnitt 12).
- **Nackte Zahl:** Die KI ergänzt nie Einheit oder Zeitraum; die Normalisierer behalten die heutige Vertragsbedeutung einer nackten Zahl (Abschnitt 3.4). **Fester Schutz (nach Schicht b, ersetzt die Präzisierung von Haltepunkt B):** Bei Häufigkeit und Dauer gilt eine nackte Zahl nur, wenn die Person **genau diese Zahl** schreibt — dann nimmt sie die Kurzform direkt an, ohne KI, mit der Vertragsbedeutung (D1 pro Jahr, E1/E2 Minuten, „ohne Rückfrage“, `contracts/bc1-to-bc2/README.md`). Ein KI-Kandidat für diese Typen, der nur eine Zahl ohne Zeitraum bzw. Einheit ist, wird verworfen (→ Nachfrage); der Prompt sagt „ohne Zeitraum bzw. Einheit: weglassen“. Anlass: Mit der Regel „nackte Zahl unverändert zurückgeben“ machte die echte KI aus „2x“ die Zahl „2“, gespeichert als 2 pro Jahr — ein stiller Falsch-Wert (Szenario 4). Ein Prompt allein schützt nicht; der Code muss es.
- **Feste Sperren gegen Regelverstöße der KI** (aus der Roadmap vorgezogen nach der Gesamtprüfung, Entscheidung der BC1-Projektleitung 30.10.). Ein KI-Kandidat wird verworfen (→ Nachfrage), wenn er der Originalnachricht widerspricht:
  - **(a) Identitätsbezug:** Für ein Feld mit `spec.identitaetskritisch` gilt ein KI-Wert nur, wenn die Nachricht (über den Vergleichsschlüssel aus 3.3) die Kennung dieser Option oder genau einen ihrer Namen enthält, kein „?“ enthält und nicht zugleich Kennung oder Namen einer anderen Option nennt.
  - **(b) Zeitraum und Einheit:** Für Häufigkeit und Dauer gilt ein KI-Wert mit Zeitraum bzw. Einheit nur, wenn die Nachricht selbst einen Zeitraum (Wortstämme Woche, Monat, Jahr — auch „wöchentlich“, „monatlich“, „jährlich“) bzw. eine Zeiteinheit (Minute, Stunde — auch „halbe Stunde“, „Std“, „min“, „h“) nennt. So wird „2x“ nie „2 pro Jahr“ und „ca. 40“ nie „40 Minuten“.
  - **(c) Fragebezug:** Liefert die KI für das gerade gefragte Feld keinen gültigen Wert, werden ihre Kandidaten für andere Felder in diesem Turn verworfen. Eine Antwort, die nicht in die Form der gestellten Frage passt, wird nachgefragt, nicht einem anderen Feld zugeordnet (Anlass: „5 pro Woche“ auf die Fallzahl-Frage änderte die Häufigkeit).
- **Tests mit `state=None`:** Adapter-Tests, die heute `state=None` übergeben, werden auf einen echten `SessionState` umgestellt (bewusste Änderung, Abschnitt 7).
- **Bewusst als Nachfrage** (nicht von der KI umzurechnen): „täglich/pro Tag“ (Arbeits- oder Kalendertage?), Dauern in Tagen/Wochen (Arbeits- oder Durchlaufzeit? Vertrag mit BC2: Jahresminuten = D1 × E1), Spannen, „teilweise/manchmal/eher ja“, qualitative Skalenwörter („eher gut“). Entscheidung 8.1.

### 3. Feste Regeln im Code

**3.1 „?“ heißt keine Festlegung.** `_entferne_rand` entfernt kein „?“ mehr; steht irgendwo ein „?“, bleibt der Wert in Ja/Nein- und Auswahl-Normalisierern unverändert (ungültig → Nachfrage). Heute wird „Ja?“ zu „ja“ und „KP-03.TP-1?“ auf dem KI-Weg gültig — das ändert sich bewusst.

**3.2 Ja/Nein:** Normalisierer und Kurzform bleiben bei genau „ja“/„nein“ (mit Rändern wie heute, ohne „?“). **Keine Präfixregel.** „Ja, …“-Sätze wandelt die KI mit Fragebezug um oder lässt sie weg.

**3.3 Auswahl: einheitlicher Vergleich, Namen, Synonyme.** `AUSWAHL(*optionen, namen=None, synonyme=None)`:
- **Vergleichsschlüssel** für Eingabe, Optionen, Namen und Synonyme gleichermaßen: Unicode NFC, `casefold()`, ä/ö/ü/ß ↔ ae/oe/ue/ss, „_“, „-“ und Leerraum zu einem Leerzeichen, Ränder wie `_entferne_rand` (ohne „?“).
- **Treffer:** Schlüssel gleich einer Option → Option; gleich dem Schlüssel **genau eines** Namens oder Synonyms → zugehörige Option. Mehrdeutige Schlüssel (zwei Optionen) und leere Namen werden nicht übersetzt; eine Kennung gewinnt vor einem gleichlautenden Namen.
- **Normalisierer und Kurzform** nutzen denselben Abgleich. Die Kurzform bleibt eng: zuerst die engen Ränder am Rohtext prüfen (ganze Nachricht, höchstens ein „.“/„!“ am Ende), erst dann den Schlüssel bilden — so bleibt etwa „geschaetzt..“ ohne Kurzform.
- **Paarformen** („KP-02.TP-2 = Lead qualifizieren“, „Geschäftsführung (R-06)“, „die Geschäftsführung“) löst der feste Weg nicht; sie stehen im Katalog als „fest: Nachfrage, KI: Wert“. Feste Paarformen erst, wenn Schicht b eine Lücke zeigt.
- **Prüfer unverändert** (gültig nur die Optionen); gespeichert wird immer die Kennung bzw. Option.
- **Woher:** `discovery_paket.py` übergibt B3 `kontext.rollen`, B4 `kontext.prozesse`, E5 `kontext.teilprozesse` als Namen. Synonyme nur für feste Auswahlfelder und nur, wo der Schlüssel nicht reicht: C3 mail ← „E-Mail“, „Email“; A3 ganzer_prozess ← „den ganzen Prozess“, einzelner_schritt ← „ein einzelner Schritt“; E3 aus_system ← „aus dem System“. („Zeit sparen“, „einzelner Schritt“, „geschätzt“, „aus System“ löst schon der Schlüssel.)
- **Paket-Fingerprint:** Namen wirken jetzt auf die Eingabe-Auslegung. Der Fingerprint (`_ctx_fingerprint`) nimmt deshalb auch die Namen auf; damit ändert sich die Kontext-Kennung in `schema_version` (Teil nach `+ctx-`), nicht die Paketfassung 1.2. Folge: Sitzungen, die vor dem Update begonnen wurden, laufen in den bestehenden Paket-Schutz — vor dem Update ohnehin per Messung ausgeschlossen. Entscheidung 8.4.
  - **Dauerfolge:** Benennt BC0 einen Teilprozess, eine Rolle oder einen Kernprozess um und startet BC1 danach neu, laufen dort schon begonnene Sitzungen in 409 `paket_konflikt` — gewollt (Schutz vor veralteter Auslegung).
  - Bestandstests mit festen Hashes (`test_discovery_paket.py`) und die zugehörigen Kommentare in `discovery_paket.py` werden bewusst angepasst.

**3.4 Normalisierer lesen keine Zahlen mehr aus Sätzen — nur zusammen mit Abschnitt 2.** Zahl-, Dauer-, Anzahl-, Prozent- und Skalen-Normalisierer nehmen nur noch die **ganze Eingabe** in einer geschlossenen Grammatik an: die Kurzformen aus #367 (mit Näherungswort, Einheit bzw. Zeitraum, höchstens „.“/„!“ am Ende) plus nackte Zahl, wo der Typ sie heute schon meint (Vertrag: D1 „300“ = pro Jahr, E1 „40“ = Minuten). Alles andere bleibt unverändert (ungültig → Nachfrage). Seit Schicht b: Die nackte Zahl bei Häufigkeit/Dauer nimmt auch die Kurzform an (die Person schrieb genau diese Zahl); vom KI-Weg wird sie für diese Typen nie übernommen (Abschnitt 2, „Fester Schutz“).
- **Häufigkeit, erweitert um heute gültige eindeutige Verbindungen:** `<Zahl> [x|mal]` gefolgt von einer Wortverbindung mit Leerraum davor und danach (`pro`, `im`, `je`, `in der`, `die`, `den`, `das`) oder von „/“ mit optionalem Leerraum, dann `Woche|Monat|Jahr` — also auch „2x die Woche“, „2/Woche“, „2 mal in der Woche“; Wortverschmelzungen wie „2imMonat“ bleiben ungültig. Kurzform und Normalisierer gleich.
- **Fallen bewusst weg (heute still falsch):** „jeden 2. Monat“ → 24, „1 Stunde und zehn Minuten“ → 60, „nicht 3 Stunden“ → 180, „unter 1 Stunde“ → 60, „mehr als 2 Stunden“ → 120, „30 Minuten pro Lead“ → 30.
- **Werden auf dem festen Weg zur Nachfrage, die KI bringt sie in die Antwortform** (Katalog „fest: Nachfrage, KI: Wert“): „20 Leads pro Woche“, „etwa 20 Anfragen pro Monat“, „jede Woche 2“, „so 30 im Monat“, „pro Monat 30“, „so 45 Minuten“, „meistens 20 Minuten“, „2 Stunden bei uns“. Reicht die KI wörtlich durch, entsteht eine Nachfrage, kein falscher Wert. Bei einem schon gültigen Feld kann ein wörtlich durchgereichter Satz das Feld auf „unklar“ setzen; das löst sich durch Wiederholung und wird in Schicht b gemessen.
- **3.4 nie ohne Abschnitt 2** (gleicher Merge, gleiches Update): ohne Fragebezug und Antwortform würden die strengen Normalisierer viele heute gültige Antworten zur Nachfrage machen.
- **Invariante „Normalisierer ⊇ Kurzform“:** was die Kurzform annimmt, nimmt auch der Normalisierer an, mit demselben Ergebnis — geprüft als `normalisiere(x) == normalisiere(kurzform(x))`, denn die Kurzform liefert eine Zwischenform („2 pro Woche“, die erst der Normalisierer zu „104“ macht); lehnt der Prüfer die Zwischenform ab (z. B. „150 %“ → „150“), bleibt auch der Rohtext ungültig — Prüfer werden dafür nie gelockert (heute verletzt: `SKALA_1_5.normalisiere("4.")` ungültig, Prozent „70 Prozent“ auf dem KI-Weg ungültig).
- Totalität bleibt (wirft nie). Gespeicherte Form unverändert.
- **Bewusst geänderte Bestandstests:** in `test_feldtypen.py` „5 pro Woche pro Woche“ (heute 260) und „30 pro Monat [Person A]“ (heute 360, damals als gewollt notiert) — beide künftig ungültig. BC2-Texte mit Satzbeispielen (`contracts/bc1-to-bc2/README.md` „90 Minuten pro Fall“, `prozessprofil.schema.json`) bleiben heute unverändert → Roadmap (Abschnitt 12).

### 4. Nachfrage mit Antwortform (`bc1_core/gespraech.py`, `bc1_service/prompts.py`)

- `TurnKontext` erhält als letztes Feld `antwortform: str | None = None` des gefragten Felds: gesetzt aus `spec.typ.antwortform` nur für Felder mit festem Typ (= Typ mit Kurzform); bei Freitext, Liste und Systemtyp `None` — dann bleibt der Nachfrage-Text ohne Antwortform-Satz (eine Bitte „als Text“ wäre nutzlos, und die Systemtyp-Antwortform ist eine Anweisung an die Extraktion, nicht an die Befragten).
- Nachfrage-Text an die Gesprächs-KI, sinngemäß: „Frage nach **demselben Gegenstand** wie die Kernfrage. Antwortform: <…>. **Bitte ausdrücklich um eine Antwort in dieser Form** (bei Ja/Nein: ‚mit Ja oder Nein‘). Ja und Nein bedeuten dasselbe wie in der Kernfrage (nicht umkehren, nicht verneinen). Bei einer Skala bleiben Richtung und Endpunkte. Nenne nur Optionen, die die Antwortform vorgibt — ein ‚oder‘ in einer Ja/Nein-Frage ist keine Auswahl.“ Die Regel „nenne in der Frage enthaltene Optionen vollständig“ wird dadurch ersetzt. Zweck erklären, Beispiel, „Feld darf offen bleiben“ bleiben.

### 5. Schicht a — Antwortkatalog als Test ohne KI

- **Katalog** als reine Daten im Repo (`tests/daten/antwortkatalog.json`, von Test und Werkzeug gemeinsam genutzt): je Pflichtfeld mit festem Typ (A2, A3, B3, B4, C3, D1, D4, E1, E5, E2, E3, E4, F3, G1, G2, G4, G5, I1) natürliche Antworten. Pflichtinhalt: die Beispiele aus den Prüfberichten (Tabellen „26 Felder × natürliche Antworten“), darunter die gefährlichen Fälle („jeden 2. Monat“, „nicht 3 Stunden“, „Ja, eigentlich nicht“, „Ja?“), Namen mit Bindestrich/„+“/„&“/Umlaut, Synonyme, Paarformen, die Satzformen aus 3.4. Nur generische Namen (Repo öffentlich).
- **Eintrag:** `{feld, antwort, fest, ki, vertrag}`.
  - `fest`: erwarteter Wert auf dem festen Weg oder „Nachfrage“.
  - `ki`: erwarteter Wert mit KI (Schicht b), „Nachfrage“ oder **Grenzfall** „Wert X oder Nachfrage“.
  - `vertrag`: der Wert ist die Vertragsbedeutung einer nackten Zahl (D1 „300“ = pro Jahr, E1 „40“ = Minuten).
- **Grenzfälle und Skalenwörter:** „Ja, aber selten“, „Zwischen Systemen wechseln“ (F3) sind Grenzfälle. Skalen-Endpunkte, die die Frage selbst definiert („gar nicht“ = 1 bei G1, „immer gleich“ = 5 bei G2), gelten als Wert; andere qualitative Wörter, Mehrfachnennung bei Einzelauswahl und „Ja“ auf eine Skalenfrage → Nachfrage.
- **Prüft zwei Wege:** (1) direkt: Kurzform → Normalisierer → Prüfer; (2) „KI reicht wörtlich durch“: Normalisierer → Prüfer auf dem Rohtext. **Kein Weg liefert einen anderen gültigen Wert als erwartet**; Weg 2 darf den `vertrag`-Wert liefern. „Nachfrage“ heißt: ungültig oder keine Kurzform.
- Plus Eigenschaftstest „Normalisierer ⊇ Kurzform“ über alle Katalogeinträge.
- Was nur die KI lösen kann („wöchentlich“, „eine halbe Stunde“), ist im Katalog für Schicht b markiert und in Schicht a als „auf festem Weg: Nachfrage“ geführt.

### 6. Schicht b — Prüfwerkzeug mit echter KI

- **Ort:** `bc1-context-discovery/werkzeuge/` (nicht im Image, nicht in der Suite, nicht in der CI). Architektur-Invariante „Tests gegen Fake-LLM, kein Netz in Tests“ unberührt: Das Werkzeug ist kein Test; es ruft nur `process_turn` (mit `InMemoryStateStore`, `baue_discovery_paket(kontext=…)`, KI-Adapter hinter dem LLM-Client) und befüllt nie selbst den Zustand. Seine eigene Ablauf- und Auswertelogik ist mit der Test-KI in der Suite getestet.
- **Modell** wie auf dem Server (`gemini-3.8-flash`, Adapter über `BC1_LLM` wählbar), bezahlter Tarif (Projektleitung 29.10.).
- **Testkontext:** generisch, aber realistisch (Namen mit Bindestrich, „+“, „&“, Umlaut; mehrere Teilprozesse; Rollen mit genau einem Eigner; Kernprozesse; Systeme).
- **Szenarien, je unabhängig gestartet** (Bau- und Laufreihenfolge: zuerst 3 und 4, dann 1, dann 2):
  1. **Grundlauf** — kurze Startnachricht (nur A1/A2/A3/B1), sodass B3, B4, E5 und die übrigen Felder einzeln gefragt werden; Antworten mit Kennungen und Kurzformen.
  2. **Natürlich, als Variantenreihe** — dieselbe Struktur, Antworten aus dem Katalog in natürlicher Form (Namen, Umlaute, „wöchentlich“, „eine halbe Stunde“, „5 Leads“, „4 von 5“, „Ja, müssen wir“, „nö“ …). Je Lauf erreicht pro Feld nur eine natürliche Antwort die KI (höchstens zwei Versuche je Feld); deshalb nimmt Lauf k je Feld die k-te Antwort, mindestens drei Läufe.
  3. **Nachfragen** — für je ein Ja/Nein-, Auswahl- und Skalenfeld zuerst eine unbrauchbare Antwort („Wie meinen Sie das?“), dann die richtige; der Nachfragetext wird geprüft: Ja/Nein nennt „Ja“ und „Nein“; Auswahl nennt alle Optionen (Abgleich über den Vergleichsschlüssel aus 3.3); Skala nennt 1 und 5 und die Richtung der Kernfrage. Die Nachfragetexte stehen wörtlich im Bericht; der Ausführende bewertet sie schriftlich (Polarität, Richtung, Optionen) und markiert sie für die Projektleitung als offen.
  4. **Nachfrage erwartet** — „täglich“, „2–3 Stunden“, „2 Tage“, „eher gut“, „Ja, keine Ahnung“, „Ja?“, dazu E5 mit Teilname, Ordinalzahl oder Umschreibung: erwartet ist eine Nachfrage, **kein** Wert; **danach eine gültige Zweitantwort**, damit kein Pflichtfeld aufgegeben wird (Ergebnis „✓ nach erwarteter Nachfrage“).
- **Laufvertrag:** Schleife solange Status „frage“; Antwort je **gefragtem Feld** (`payload["feld"]`) aus dem Szenario; `fehler_fortsetzbar` → einmal dieselbe Nachricht wiederholen, dann Abbruch „technisch nicht abgeschlossen“ (kein Feldfehler); Höchstzahl an Turns; Aufrufzähler.
- **Bericht je Feld:** gesendete Antworten, Zahl der Nachfragen, Endwert, erwartet, Ergebnis (✓ im 1. Versuch · ✓ nach erwarteter Nachfrage · ✗ falscher Wert/aufgegeben/unerwartete Nachfrage · „nicht geprüft“); Nachfragetexte; Modell, Code-Stand, Szenario. Ein Wert für ein **anderes** Feld, der sich durch die Antwort ändert, ist ✗.
- **Umgang mit ✗:** nie den Katalog still anpassen. Entweder Code/Prompt ändern (mit Test) oder den Eintrag mit Begründung auf „Nachfrage erwartet“ setzen (Entscheidung der Projektleitung bei Bedeutungsfragen). Ohne Projektleitung: Code/Prompt nur bei eindeutigem Fehler und mit Test ändern; Bedeutungsfragen als „offen für die Projektleitung“ in den Bericht.

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
10. Bestehende Tests, die sich bewusst ändern, im Plan einzeln ausweisen: `test_feldtypen.py` (Normalisierer-Sätze aus 3.4; „geschätzt“ wird Kurzform „geschaetzt“, „geschaetzt..“ bleibt ohne), `test_extractor.py` („Erfassen“ wird Kurzform), `test_discovery_paket.py` (zwei feste Fingerprint-Hashes und zwei Umbenennungs-Tests, die heute „Name ändert die Kennung nicht“ festhalten), `test_prompts.py` (Optionen-Regel; `TurnKontext`-Konstruktion), `test_gemini_llm.py` und `test_gemini_echt.py` (`state=None`). Unberührt bleiben die Testdaten-, Demo- und Nachspiel-Tests sowie der Test „Ja auf die Eigner-Frage bleibt ungültig“.

### 8. Entscheidungen für die BC1-Projektleitung

1. **Grundsatz „nichts erfinden“** (Empfehlung): „täglich“, Dauern in Tagen/Wochen, Spannen, „teilweise/eher ja“, qualitative Skalenwörter führen zur Nachfrage.
2. **KI kennt Frage und Antwortform jetzt** (Empfehlung) — die eigentliche Ursache; ein gemeinsamer Helfer für alle drei Adapter.
3. **Normalisierer streng** (Empfehlung) — keine Zahl mehr aus Sätzen; was die KI nicht in die Antwortform bringt, wird nachgefragt statt falsch gespeichert.
4. **Namen im Fingerprint** (Empfehlung) — sicher gegen Umbenennung zwischen zwei Turns; Folge: neue Kontext-Kennung nach dem Update (vorher messen).
5. **Fester Code nur für Schlüssel, Namen, wenige Synonyme und „?“** (Empfehlung); Zahlwörter, „wöchentlich“, „4 von 5“, „nö“ löst die KI mit Antwortform; feste Regeln nur nachziehen, wo das Prüfwerkzeug Lücken zeigt.
6. **Prüfwerkzeug: vier Szenarien (1, 3, 4 je zwei Läufe; 2 als Variantenreihe mit mindestens drei Läufen, seit Entwurf 3), gleiches Modell wie der Server** (Empfehlung); fester Schritt vor jeder Generalprobe und vor jedem Update, das Dialog oder Extraktion berührt (in BETRIEB.md und Abschlussplan).
7. **Generalprobe 3 an KP-03.TP-1** mit natürlichen Antworten (Empfehlung), nach Merge, Update mit Ansage an BC0 und Werkzeug-Abnahme.

### 9. Plan bis Dienstag und Rückfallebene

- **Bau-Reihenfolge mit Haltepunkten** (je Schritt ein Commit, Suite grün):
  1. Abschnitt 1 (Antwortform).
  2. 3.1 „?“ und 3.3 Schlüssel/Namen/Synonyme mit Fingerprint und den zugehörigen Katalogeinträgen → **Haltepunkt A**: rein fest, sicher und für sich wertvoll („Lead qualifizieren“, „Zeit sparen“, „geschätzt“, „E-Mail“ ohne KI).
  3. Abschnitte 2 und 4 (Prompt mit Fragebezug, Identitätsregel, Nachfrage).
  4. 3.4 strenge Normalisierer — erst nach Schritt 3 → **Haltepunkt B**: Code vollständig; nicht ausrollen ohne Schicht b; nie 3.4 ohne 2. Zweitmeinung über den Diff an dieser Stelle.
  5. Katalogtest (Schicht a, Schema aus Abschnitt 5).
  6. Werkzeug (Schicht b): zuerst Szenarien 3 und 4, dann 1, dann 2.
  7. Läufe gegen die echte KI, Bericht, Gesamtprüfung.
- **Zeitplan:** Do 29.10. Entwurf 3; Fr 30.10. Implementierungsplan (geprüft), Bau bis Haltepunkt A; Sa 31.10. bis Haltepunkt B, Katalogtest, Werkzeug; So 01.11. Läufe, Gesamtprüfung, PR, Merge, Tag, Update mit Ansage, Generalprobe 3; Mo 02.11. Puffer, UC1-Testanfrage KP-06.TP-2 für die Vorführung.
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
- **Feste Sperre für E5 im Code:** mit diesem Paket umgesetzt (Abschnitt 2, „Feste Sperren“ (a)), zusammen mit den Sperren für Zeitraum/Einheit (b) und Fragebezug (c).
- Neu: **Feste Regeln nachziehen** (Entscheidung 8.5) für Lücken, die Schicht b zeigt (z. B. Paarformen, Zahlwörter). Ziel: nach den ersten Läufen. Nächster Schritt: Lückenliste aus dem Bericht.
- Neu: **BC2-Texte angleichen** — Satzbeispiele in `contracts/bc1-to-bc2/README.md` („90 Minuten pro Fall“) und `prozessprofil.schema.json` passen nicht mehr zur strengen Auslegung; dazu die Vertragsbedeutung der nackten Zahl. Ziel: mit BC2 klären (#286). Nächster Schritt: Kommentar in #286 nach dem Merge.
- Neu: **Ollama-Kontextlänge prüfen** — der Extraktions-Prompt wächst (heute rund 4.600 Zeichen); `num_ctx` in der Primärdoku nachlesen. Kein Server-Pfad. Ziel: vor dem nächsten Ollama-Einsatz.

### 13. Was aus der Prüfung von Entwurf 2 wurde

| Befund (Prüfer) | Entwurf 3 |
|---|---|
| Antwortform/Prompt widerspricht Prüfer: „Zahlen mit Einheit“ macht „5 Leads“ ungültig (D4); Systemtyp lädt zu erfundenen S-NN ein (agy, Critical) | ANZAHL „nur eine Zahl, ohne Einheit“; Systemtyp „nur genannte Kennungen“ (1); Prompt „bei Anzahl, Skala, Prozent nur die Zahl“ (2) |
| Strenge Normalisierer machen heute gültige Satzformen zur Nachfrage (agy, Claude) | heute gültige eindeutige Häufigkeitsformen in die Grammatik (3.4); übrige Satzformen „fest: Nachfrage, KI: Wert“; 3.4 nur zusammen mit 2 |
| „wörtlich“ für Freitext/Listen muss bleiben (Claude) | Abschnitt 2 |
| E5 identitätskritisch: KI-Umformung kann eine falsche, gültige Kennung liefern (Claude) | Identitätsregel im Prompt über `spec.identitaetskritisch` (2), Katalog und Szenario 4; feste Sperre → Roadmap (12) |
| KI-Umformung umgeht „?“-Schutz und Bezugsgröße (agy) | Weglass-Liste: „?“, andere Bezugsgröße, Mehrfachnennung, „Ja“ auf Skala (2) |
| Szenario 4 ohne gültige Zweitantwort widerspricht der Abnahme (agy) | Zweitantwort (6) |
| Je Lauf erreicht pro Feld nur eine natürliche Antwort die KI (Claude) | Szenario 2 als Variantenreihe, ≥ 3 Läufe (6, Abnahme 2) |
| Katalog-Schema unklar; nackte Zahl und Grenzfälle fehlen (Claude) | Schema `{feld, antwort, fest, ki, vertrag}`, Grenzfall-Klasse, Skalen-Endpunkte (5) |
| Paarformen „KP-02.TP-2 = Lead qualifizieren“, „Geschäftsführung (R-06)“ (agy, Claude) | Katalog „fest: Nachfrage, KI: Wert“; feste Paarformen nur bei Lücke (3.3, 12) |
| `antwortform` mit Vorgabe beschreibt Typen falsch; `TurnKontext`-Vorgabe; Bitte „als Text“ bei Freitext-Nachfrage (agy, Claude) | Pflichtmerkmal `kw_only` (1); `antwortform` letztes Feld, `None` bei freien Typen (4) |
| Tests mit `state=None`, feste Fingerprint-Hashes brechen (agy, Claude) | als bewusste Änderungen ausgewiesen (2, 3.3, 7.10) |
| Ränder der Kurzform widersprüchlich („geschaetzt..“) (Claude) | erst Ränder am Rohtext, dann Schlüssel (3.3) |
| Fingerprint-Dauerfolge bei Umbenennung (Claude) | 3.3 |
| Roadmap-Einträge fehlen (Claude) | Abschnitt 12 |
| Reihenfolge und Haltepunkte fehlen (Claude) | Abschnitt 9 |
