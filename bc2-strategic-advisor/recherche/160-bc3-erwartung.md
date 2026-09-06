# Was BC3 von BC2 erwartet — und ob `konzept.schema.json` v2.0 das trägt

> **Recherche zu [#160](https://github.com/pg-coe-kmu/coe-factory/issues/160)** · Teil von [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158) · **Stand: 06.09.2026**
> Repo-Stand gemessen im Worktree auf `main`. Schema-Validierungen mit `jsonschema` 4.25.1,
> Draft 2020-12. Issues über `gh issue view --json body,comments` am 06.09.2026 abgerufen.

## Kennzeichnung

| Marke | Bedeutung |
|---|---|
| **[gemessen]** | Von mir aus Repo-Dateien gezählt, validiert oder diffed. Reproduzierbar, Kommando im Anhang. Maßgeblich. |
| **[belegt]** | Steht wörtlich in einer Schema-Datei, einer README oder einem Issue-Kommentar. Fundstelle genannt. |
| **[unsicher]** | Meine Deutung. Nicht durch Messung oder Zitat gedeckt und ausdrücklich als solche markiert. |
| **[nicht belegt]** | Die Quellen schweigen. Nicht erfunden, nicht geraten. |

---

## Kernbefund in vier Sätzen

**BC3 hat #160 bereits beantwortet** — nicht im Ticket, sondern als Artefakt: PR
[#176](https://github.com/pg-coe-kmu/coe-factory/pull/176) vom 31.08.2026 legte
`bc3-engineering-architect/bc2-anforderung/` an, vier Konzeptdateien im Wunschformat, Commit-Text
„Bezug: #160". Der v2-Vertrag **trägt nicht** — er bricht in drei maschinell nachweisbaren Punkten,
und BC3s eigene Vorlage validiert mit fünf Fehlern gegen ihn. Der Widerspruch bei den
Akzeptanzkriterien **löst sich auf**: BC3 will von BC2 **keine SOPHIST-User-Story**, sondern
fachlichen Gehalt in zwei Feldern — in BC3s 116 an BC2 gerichteten Anforderungssätzen kommt SOPHIST
**null Mal** vor, die 47 Akzeptanzkriterien sind **ausnahmslos Given/When/Then**. Der Vertrag muss
**gebrochen und erweitert** werden, aber die Erweiterung ist nicht zu entwerfen — sie liegt fertig
im Repo.

---

## Korrekturen an den Ticket-Prämissen

Vier Annahmen des Tickets treffen den Repo-Stand nicht mehr. Sie zu korrigieren ist keine
Wortklauberei — zwei davon ändern das Ergebnis.

| Ticket sagt | Tatsächlich | Beleg |
|---|---|---|
| `contracts/bc3 - bc4/` | `contracts/bc3-to-bc4/` | `find contracts -type f` |
| `readmi.md`, `mock/READMI.md` | `README.md`, `mock/README.md` | ebenda |
| `tickets.schema.json` **v3.4** | **v3.5** seit 03.09.2026 | `contracts/bc3-to-bc4/tickets.schema.json` Z. 4 + Z. 23 (`"const": "3.5"`) |
| nur `mock/tickets.json` | **drei echte Lieferungen** `uc1`/`uc2`/`uc3` als `ticket_set.json` | `contracts/bc3-to-bc4/uc*/ticket_set.json` |

Die Umbenennung `tickets.json` → `ticket_set.json` steht in `contracts/bc3-to-bc4/README.md` Z. 103
in der Änderungstabelle: *„seit Juli angekündigt, nie umgesetzt"*. **[belegt]**

**Die fünfte und wichtigste Korrektur:** Das Ticket schneidet die Aufgabe als *Rückwärtserschließung*
(„Daraus lässt sich rückwärts lesen, welche Granularität BC3 braucht"). Das war am 30.08. richtig.
Seit dem 31.08.2026 ist es überholt — **BC3 hat seine Erwartung direkt hingeschrieben.** Die
Rückwärtserschließung bleibt als Gegenprobe wertvoll und bestätigt die Direktaussage; sie ist aber
nicht mehr die Hauptarbeit.

---

## Verwendete Quellen

| Kurzname | Datei / Issue | Stand |
|---|---|---|
| **v2.0** | `contracts/bc2-to-bc3/konzept.schema.json` | Version 2.0 |
| **prio v2.0** | `contracts/bc2-to-bc3/priorisierung.schema.json` | Version 2.0 |
| **v3.5** | `contracts/bc3-to-bc4/tickets.schema.json` | Version 3.5, 03.09.2026 |
| **BC3-README** | `contracts/bc3-to-bc4/README.md` | 03.09.2026, Sabrina + Svetlana |
| **Mock-README** | `contracts/bc3-to-bc4/mock/README.md` | 12.06.2026 |
| **Anforderung** | `bc3-engineering-architect/bc2-anforderung/README.md` + 4 JSON | 31.08.2026, PR #176 |
| **Bausteine** | `bc3-engineering-architect/bc3-architektur-bausteine.md` | 26.06.2026, „Diskussions-Entwurf" |
| **Lieferungen** | `contracts/bc3-to-bc4/uc{1,2,3}-*/` je 5 Dateien | 03.–06.09.2026 |
| **Issues** | #8, #9, #11, #89, #100, #103–#108, #110–#112, #115, #116, #118, #158, #160, #168 | 06.09.2026 |

---

## Frage 1 — Was liegt in `contracts/bc3-to-bc4/`, und was braucht BC3 daraus von BC2?

### Bestand **[gemessen]**

```
contracts/bc3-to-bc4/
├── README.md                    Liefer-README an BC4
├── tickets.schema.json          v3.5
├── mock/                        Aurelia, v3.4 — veraltet
│   ├── tickets.json  architecture.md  openapi.yaml  compliance-audit.json  README.md
└── uc{1,2,3}-*/                 drei echte Lieferungen, je fünf Dateien
    ├── ticket_set.json  blueprint.json  architecture.md
    ├── api/openapi.yaml  compliance-audit.json
```

`openapi.yaml` liegt nur bei `uc1` vor; `uc2` und `uc3` haben kein `api/`-Unterverzeichnis
**[gemessen]**. Passend dazu ist #112 „API-Beschreibung automatisch generieren" **offen** und trägt
null Kommentare — die Generierung steht noch nicht.

**Wie weit BC3 ist, lässt sich an einer Zahl ablesen** **[gemessen]**: `gate2.status` steht in allen
drei echten Lieferungen auf **`approved`**. BC3 hat also drei Ticket-Sets menschlich freigegeben und
an BC4 übergeben — auf Grundlage von Konzepten, **die BC3 sich selbst geschrieben hat**, weil BC2
keine geliefert hat. Das ist der Kern der Lage: BC3 ist nicht nur weiter, es hat BC2s Rolle
übergangsweise mitübernommen.

### Was BC3 von BC2 braucht, rückwärts gelesen

Sechs Felder in `konzept_ref` (v3.5 Z. 29–75) sind reine **Durchreichfelder aus BC2**. Vier davon
sind Pflicht:

| Feld in v3.5 | Pflicht | Quelle in v2.0 | Status |
|---|---|---|---|
| `konzept_ref.konzept_id` | ja | `konzept_id` | ✅ vorhanden |
| `konzept_ref.schema_version` | ja | `schema_version` | ✅ vorhanden |
| `konzept_ref.source_file` | ja | — | ⚠️ kein Feld, ergibt sich aus der Übergabeform |
| `konzept_ref.kp_id` | ja | `kontext.kp_id` | ✅ vorhanden, wörtlich benannt |
| `konzept_ref.teilprozess_ids` | nein | — | ❌ **fehlt in v2.0** |
| `konzept_ref.value_quelle` | nein | `potenziale[].value.value_quelle` | ⚠️ **Enum zu eng** |
| `konzept_ref.prozessprofil_ref` | nein | `prozessprofil_ref` | ✅ vorhanden |

Die Herkunft steht wörtlich im Schema. v3.5 Z. 55 zu `kp_id`: *„Der Kernprozess aus der
BC0-Baseline, **übernommen aus `kontext.kp_id` des Konzepts**."* **[belegt]** Und Z. 64 zu
`teilprozess_ids`: *„Sammelt sich aus den Potenzialen."* **[belegt]** — was v2.0 nicht leisten kann,
weil es keine Teilprozess-IDs führt.

### Das schärfste Zitat: BC3s Schema benennt BC2s Lücke namentlich

`tickets.schema.json` v3.5, Z. 152, Beschreibung von `epic.teilprozess_ids`:

> „Freiwillig: BC0 verlangt die Kennung auf Prozess- ODER Teilprozessebene, und `kp_id` in
> `konzept_ref` ist Pflicht. **BC2 liefert Teilprozess-IDs in v2.0 noch nicht.**"

**[belegt]** BC3 hat das Feld also **absichtlich optional gehalten, weil BC2 es nicht liefert.** Das
ist kein Versehen und kein Vorwurf — es ist eine dokumentierte Umgehung eines bekannten Mangels.

### BC3-Ausgabefelder, die sich nur aus BC2-Input befüllen lassen

| BC3-Ausgabe | Speist sich aus | Nachweis |
|---|---|---|
| `epic.titel` | `potenziale[].titel` | 3 von 6 Epic-Titel **wörtlich identisch** **[gemessen]** |
| `epic.ziel` | `to_be_vision` | Kennzahl „innerhalb von zwei Minuten" steht in beiden, s. u. |
| `story.beschreibung` | `fachliche_anforderungen` | Satz-zu-Story-Abbildung, s. Frage 2 |
| `akzeptanzkriterien[].text` | `akzeptanzkriterien_geschaeftlich` | nahezu wörtliche Übernahme, s. Frage 2 |
| `blueprint.komponenten[]` | `betroffene_systeme[]` | `anbindung`-Werte = BC2s `integration`-Enum **[gemessen]** |
| `konzept_ref.*` | Kopfdaten des Konzepts | Tabelle oben |

**`blueprint.json` ist der sauberste Nachweis direkter Weiterverarbeitung** **[gemessen]**:
`komponenten[].anbindung` trägt die Werte `Email`, `API`, `DB`, `Datei` — exakt vier der sieben
Werte aus BC2s `betroffene_systeme[].integration`-Enum (v2.0 Z. 151). Und `komponenten[].rollen`
trägt `Quelle`, `Ziel`, `Quelle+Ziel` — **exakt** BC2s `rolle`-Enum (v2.0 Z. 147). BC2s
Systemliste wandert unverändert in BC3s Bauplan.

Bemerkenswert: `rollen` ist bei BC3 ein **Array**, bei BC2 ein Skalar. Der Grund steht im
Schließkommentar zu **#111** vom 20.07.2026:

> „Ein System kann je Use Case eine andere Rolle haben. Die Buchungsdatenbank wird in UC1
> beschrieben, in UC2 gelesen, in UC3 wieder beschrieben. Eine einzige Rolle je System reicht also
> nicht — sonst zeigen Pfeile in die falsche Richtung."

**[belegt]** Das ist **kein** Bruch für BC2: BC2 führt die Systeme *je Potenzial*, BC3 aggregiert
über die Potenziale. Der Skalar je Potenzial genügt. **[gemessen]** — in `uc1/blueprint.json` trägt
„Outlook-Postfach reisen@noroai" `["Quelle","Quelle+Ziel"]`, zusammengesetzt aus zwei Potenzialen.

### Ein BC3-Pflichtfeld ohne jede BC2-Quelle

`epic.kategorien` (v3.5 Z. 129–137) ist **Pflicht**, `minItems: 1`, Muster
`^(it|fin|gov|sec):[a-z0-9-]+$`, Zweck laut Schema *„Worker-Routing für BC4 auf Epic-Ebene"*.

BC2s `potenziale[].kategorie` ist ein Enum aus `Quick Win`, `Strategisch`, `Optional`, `Long Bet` —
eine **Priorisierungs-Einordnung**, keine fachliche Kategorie. Die beiden Felder heißen fast gleich
und meinen Verschiedenes. **[gemessen]** In allen sechs Epics stehen ausschließlich `it:*`-Werte
(`it:backend`, `it:integration`, `it:ai-pipeline`) — BC3 vergibt sie selbst.

Zuständig ist **#107 „Etiketten (Labels) für Stories"** — **offen, null Kommentare**, AK
*„Etiketten-System festgelegt (it / gov / sec / fin)"* unangehakt. **[belegt]** Der Wert wird also
heute vergeben, ohne dass das System dafür beschlossen wäre.

> **[unsicher]** Ob BC2 hier je etwas beitragen soll, ist offen. `sec:`/`gov:`-Kategorien könnten
> sinnvoll aus `voraussetzungen` („DSGVO-Freigabe …") und `risiken` folgen. Das ist eine
> Vermutung, keine Anforderung von BC3.

---

## Frage 2 — Der Widerspruch bei den Akzeptanzkriterien

Die schärfste Frage des Tickets. Sie ist **entscheidbar**, und zwar gegen die Karten-Festlegung
vom 30.08.

### Was v3.5 formal trennt **[belegt]**

| Feld | Typ | Grenzen | Fundstelle |
|---|---|---|---|
| `story.beschreibung` | String | 20–1500 Zeichen | v3.5 Z. 177–181 |
| `story.akzeptanzkriterien[]` | Array von Objekten | `minItems: 1` | v3.5 Z. 182–203 |
| ↳ `.text` | String | ≥ 10 Zeichen | v3.5 Z. 193–196 |
| ↳ `.messverfahren` | String | ≥ 5 Zeichen | v3.5 Z. 197–200 |

Das Schema selbst schreibt **keine Form** vor — beides sind freie Strings. Die Form ist also nur
empirisch feststellbar.

### Was tatsächlich drinsteht **[gemessen]**

| Lieferung | Stories | `beschreibung` mit „Als …" | Akzeptanzkriterien | davon Given/When/Then |
|---|---|---|---|---|
| `uc1-reisebuchung` | 15 | **15** | 32 | **32** |
| `uc2-wissensbasis` | 13 | **13** | 33 | **33** |
| `uc3-consultant-placement` | 14 | **14** | 29 | **29** |
| `mock/` (Aurelia, Juni) | 4 | **4** | 8 | **0** |
| **Summe echte Lieferungen** | **42** | **42 (100 %)** | **94** | **94 (100 %)** |

**Damit ist die Feldzuordnung beantwortet:** `beschreibung` ist die SOPHIST-Stelle
(„Als … möchte ich … damit …"), `akzeptanzkriterien[].text` ist die Given/When/Then-Stelle. Sie sind
nicht austauschbar.

*Nebenbefund:* Im Aurelia-Mock vom Juni sind 0 von 8 Kriterien Given/When/Then (Form: „Bei
Mail-Eingang im Postfach wird Antrag binnen 60 s in die Eingangs-Queue aufgenommen"). Die
Given/When/Then-Form kam erst mit dem Slicer-Lauf vom 20.07.2026 — genau dem, den #105 meldet.

### Wer die beiden Felder erzeugt: BC3, beide **[belegt]**

Schließkommentar **#105** vom 20.07.2026, @svetlana2305:

> „Anweisung an die KI fuer AK-Vorschlaege steht (Given/When/Then + Messverfahren je Kriterium)"

Schließkommentar **#104** vom 20.07.2026, @svetlana2305:

> „System Prompt steht (Node „Story-Architekt") · Epic-Erkennung und Story-Zerlegung laufen je Use
> Case · Kette laeuft End-to-End: **BC2-Konzept rein, 3 Epics mit 21 Stories raus**"

BC3 erzeugt Stories **und** Akzeptanzkriterien selbst. BC2 liefert den Eingang.

### Was BC3 statt SOPHIST von BC2 will **[gemessen]**

Über alle 9 Potenziale der vier Dateien in `bc3-engineering-architect/bc2-anforderung/`:

| Feld | Sätze gesamt | davon SOPHIST („Als …") | davon Given/When/Then („Gegeben …") |
|---|---|---|---|
| `fachliche_anforderungen` | 69 | **0** | — |
| `akzeptanzkriterien_geschaeftlich` | 47 | **0** | **47 (100 %)** |

**Null von 116 Sätzen ist eine SOPHIST-User-Story.** BC3 fordert von BC2:

- `fachliche_anforderungen` — deklarative Anforderungssätze
  („*Anfragen aus Mail und Web-Formular werden in einem einheitlichen Datensatz zusammengeführt.*")
- `akzeptanzkriterien_geschaeftlich` — Given/When/Then **ohne** `messverfahren`
  („*Gegeben eine Anfrage über dem Budgetrahmen, wenn die Prüfung abgeschlossen ist, dann wird sie
  der Teamleitung zur Freigabe vorgelegt und nicht weiterverarbeitet.*")

Die Rollenverteilung steht wörtlich in `bc3-engineering-architect/bc2-anforderung/README.md` Z. 27:

> „`akzeptanzkriterien_geschaeftlich` — war in v1.0 Pflicht; **BC3 leitet daraus die Kriterien je
> Story ab, BC4 baut dagegen**"

**[belegt]** BC2 liefert die *geschäftliche* Ebene, BC3 leitet die *Story*-Ebene ab und ergänzt das
`messverfahren`.

### Der Beweis der Ableitungskette **[gemessen]**

Ein Kriterium wandert von BC2s Wunschfeld nahezu wörtlich in BC3s Lieferung:

| Ebene | Text |
|---|---|
| BC2 soll liefern (`akzeptanzkriterien_geschaeftlich`, UC1-P1) | „**Gegeben** eine Anfrage über dem Budgetrahmen, **wenn** die Prüfung abgeschlossen ist, **dann** wird sie der Teamleitung zur Freigabe vorgelegt und nicht weiterverarbeitet." |
| BC3 liefert an BC4 (`akzeptanzkriterien[0].text`, Story „Verfügbarkeitsprüfung") | „**Given** eine Anfrage über dem hinterlegten Budgetrahmen, **When** die Prüfung abgeschlossen ist, **Then** wird sie der Teamleitung zur Freigabe vorgelegt und nicht weiterverarbeitet." |
| BC3 ergänzt (`.messverfahren`) | „Prüfung des Vorgangsstatus auf 'Freigabe erforderlich' und Zuweisung an die Teamleitung." |

Dasselbe für `fachliche_anforderungen` → `story.beschreibung`:

| Ebene | Text |
|---|---|
| BC2 soll liefern | „Anfragen aus Mail und Web-Formular werden in einem einheitlichen Datensatz zusammengeführt." |
| BC3 macht daraus | Story „Anfragen aus Mail und Web-Formular einheitlich erfassen" · „**Als** Backoffice-Mitarbeiter **möchte ich**, dass Reiseanfragen aus E-Mails und dem Web-Formular in einem einheitlichen Datensatz zusammengeführt werden, **damit** sie zentral verarbeitet werden können." |

Die SOPHIST-Schablone **entsteht bei BC3**. Sie ist BC3s Ausgabeform, nicht BC2s Eingabeform.

### Antwort auf die drei Teilfragen des Tickets

1. **Bedient BC2s SOPHIST-Lieferung `beschreibung` oder `akzeptanzkriterien[]`?**
   **Weder noch.** Beide Felder erzeugt BC3. BC2 liefert eine Ebene darüber, je Potenzial statt je
   Story.
2. **Will BC3 überhaupt AK von BC2?**
   **Ja, ausdrücklich** — aber als *geschäftliche* Kriterien in Given/When/Then, ohne Messverfahren.
   `bc2-anforderung/README.md` Z. 27 und die #160-Rückmeldung vom 30.08.: *„ohne sie keine Stories
   mit Messverfahren"*.
3. **Oder nur den fachlichen Gehalt?**
   **Beides.** `fachliche_anforderungen` (Gehalt) **und** `akzeptanzkriterien_geschaeftlich`
   (Prüfbarkeit). BC3 fordert sie als **zwei getrennte Felder** — sie erfüllen verschiedene Zwecke.

### Widerspruch W1 — ausdrücklich benannt

Karte #158 hält unter „Bereits entschieden" fest **[belegt]**:

> „**Form der Akzeptanzkriterien entschieden** (30.08.2026, nach BC3s Rückmeldung): **User Story
> nach SOPHIST-Schablone je Potenzial**"

Grundlage war eine Chat-Antwort, im #160-Kommentar vom 30.08.2026 19:05 als *„User Story +
Akzeptanzkriterien nach SOPHIST-Schablone"* protokolliert. **Diese Festlegung wird durch BC3s
eigenes Artefakt vom Folgetag widerlegt.** Der Chat-Satz beschrieb, wie die **fertigen Tickets**
aussehen — nicht, was BC2 liefern soll. Dieselbe Antwort nennt im Übrigen „User Story *und*
Akzeptanzkriterien" als zwei Dinge; in v3.5 sind das `beschreibung` und `akzeptanzkriterien[]`,
also genau die zwei Felder, die BC3 selbst füllt.

**Empfehlung:** Die Karten-Zeile „User Story nach SOPHIST-Schablone je Potenzial" streichen und
durch „`fachliche_anforderungen[]` + `akzeptanzkriterien_geschaeftlich[]` je Potenzial, Given/When/Then,
ohne Messverfahren" ersetzen. **Ohne diese Korrektur baut BC2 ein Feld, das BC3 nicht liest.**

---

## Frage 3 — Die geschlossenen BC3-Issues

Das Ticket nennt sie „die dichteste Quelle, weil sie Abschlusskommentare tragen". Das stimmt für
vier von sechs. Zwei tragen **gar nichts** — und das ist der Befund.

### #9 „[Contract] Schnittstelle BC2 → BC3" — die Abstimmung, die nie stattfand

Erstellt 29.05.2026 von @svetlana2305, **geschlossen 15.06.2026**, Labels `bc2`, `bc3`, `contract`,
`needs-discussion` — **null Kommentare**. **[gemessen]**

Der Body ist ein reines Formular ohne Inhalt:

> **Was soll sich ändern?** „Verbindliches Format für das Automatisierungskonzept, das BC2 an BC3
> übergibt."
> **Migrationsplan:** „schema_version"

**[belegt]** Zwei Beobachtungen:

1. Das Ticket war mit `needs-discussion` gelabelt und wurde **ohne eine einzige Diskussionszeile
   geschlossen**. Die im #160-Ticket als „die einzige dokumentierte Abstimmung" bezeichnete Quelle
   dokumentiert nichts.
2. Das Feld „Betroffene Schnittstelle" trägt **`bc1-to-bc2`** — falsch ausgefüllt, es geht um
   `bc2-to-bc3`. **[gemessen]**

> **Folge:** Es gibt **keine schriftlich abgestimmte Vertragsgrundlage** zwischen BC2 und BC3. v2.0
> ist einseitig, und #9 heilt das nicht. Genau das behauptet #160 als Ausgangslage — es bestätigt
> sich.

### #103 „Vorbereitung prüfen: was liefert BC2 uns" — geschlossen ohne Ergebnis

**Geschlossen, null Kommentare.** Die Akzeptanzkriterien im Body sind **sämtlich unangehakt**
**[gemessen]**:

> - [ ] GitHub-Repo aufgesetzt
> - [ ] BC2-Mock erfolgreich eingelesen (Input-Validierung)
> - [ ] **Lücken-Liste dokumentiert**
> - [ ] **Go/No-Go-Entscheidung schriftlich festgehalten**

**[belegt]** Die Lücken-Liste, die #160 am dringendsten bräuchte, ist ausdrücklich ein
Akzeptanzkriterium dieses Tickets — und wurde nie erstellt. Das Ticket wurde geschlossen, obwohl
seine eigene Definition of Done drei von vier Punkten offen lässt.

> **[unsicher]** Denkbar ist, dass PR #176 vom 31.08.2026 die nachgereichte Lücken-Liste ist. Die
> Datei nennt #160 als Bezug, nicht #103. Ein Zusammenhang ist plausibel, aber nicht belegt.

### #105 „Akzeptanzkriterien definieren + JSON-Schema" — trägt die Kernaussage

Geschlossen 20.07.2026, ein Kommentar. Bereits unter Frage 2 zitiert. Zusätzlich **[belegt]**:

> „Output validiert ohne Fehler: Lauf vom 20.07.2026 gegen das Schema geprueft, VALIDE
> Zusaetzlich geprueft, was das Schema nicht abdeckt: keine toten Story-Verweise, keine Verweise ins
> fremde Epic, keine Zyklen in den Abhaengigkeiten."

Drei Integritätsregeln über das Schema hinaus. `story.abhaengigkeiten[]` ist in v3.5 Pflicht (darf
leer sein) und verweist per Muster auf `st-`-IDs — **BC2 liefert dafür keine Vorlage und muss es
auch nicht**: Abhängigkeiten entstehen erst beim Story-Schnitt.

### #104 „Anweisungen an KI bauen (Prompt Chains)" — die Vollständigkeitsregel

Geschlossen 20.07.2026. Neben dem oben zitierten End-to-End-Lauf **[belegt]**:

> „Der Prompt wurde dabei mehrfach nachgeschaerft. Die urspruengliche Regel „3-5 Stories pro Epic"
> fuehrte dazu, dass Sonderfaelle und nicht-funktionale Anforderungen weggelassen wurden - u.a. fiel
> „Stornierung als Statuswechsel" komplett raus. **Jetzt gilt Vollstaendigkeit vor Anzahl.**"

**Für BC2 unmittelbar relevant:** BC3 lässt die Story-Zahl vom Input bestimmen. Je vollständiger
BC2s `fachliche_anforderungen`, desto vollständiger die Stories. Sonderfälle und nicht-funktionale
Anforderungen sind der Teil, der zuerst verlorengeht — v2.0s `beschreibung` verlangt sie unter
Buchstabe (g) „Sonderfaelle/Ausnahmen" ausdrücklich (v2.0 Z. 128).

### #111 „Architektur-Diagramm automatisch generieren" — deterministisch, ohne LLM

Geschlossen 20.07.2026 **[belegt]**:

> „Bewusst ohne Sprachmodell geloest - Diagramm und Tabelle folgen direkt aus den vorhandenen Daten,
> ein LLM koennte hier nur Fehler hinzufuegen."

**Das ist die härteste Qualitätsanforderung an BC2s `betroffene_systeme`.** Es gibt keine
LLM-Schicht, die Lücken glättet: was BC2 nicht liefert, fehlt im Diagramm. `name`, `rolle`,
`integration` sind in v2.0 alle drei Pflicht (Z. 141) — das passt.

### #89 — BC2s eigenes Contract-Ticket, zum Abgleich

Geschlossen. Akzeptanzkriterium 3 lautet **[belegt]**:

> „Fachliche Beschreibung je Use Case ist ausführlich genug, dass BC3 daraus User Stories und AK
> ableiten kann."

Der Schließkommentar von @Mzumn markiert genau dieses AK als **❌ offen**:

> „**Der offene Rest ist AK 3, und er ist substanziell.** Beim Sprung v1.0 → v2.0 sind drei Felder
> verlorengegangen, die genau diese Anforderung getragen haben."

**[belegt]** BC2 hat den Mangel also selbst protokolliert, bevor BC3 ihn belegt hat. Beide Seiten
kommen unabhängig zum selben Ergebnis.

---

## Frage 4 — Die offenen BC3-Issues

**[gemessen]** Kommentarstand aller im Ticket genannten offenen Issues:

| Issue | Titel | Erstellt | Komm. |
|---|---|---|---|
| #8 | Format mit BC2 abstimmen | 29.05.2026 | 1 (BC2, 06.09.2026) |
| #11 | DSGVO-/Security-Block verbindlich | 29.05.2026 | **0** |
| #100 | Projektplan | 13.06.2026 | **0** |
| #106 | Pipeline einmal durchlaufen lassen | 15.06.2026 | **0** |
| #107 | Etiketten (Labels) für Stories | 15.06.2026 | **0** |
| #108 | Test mit echtem BC2-Konzept | 15.06.2026 | **0** |
| #110 | Anweisungen an KI verfeinern | 15.06.2026 | 1 |
| #112 | API-Beschreibung automatisch generieren | 15.06.2026 | **0** |
| #115 | Übergabe-Prozess fertigstellen | 15.06.2026 | **0** |
| #116 | Übergabe-Kontrakt final | 15.06.2026 | **0** |
| #118 | Architektur BC3-Pipeline klären | 15.06.2026 | 1 |

Neun von elf sind stumm. Die drei mit Inhalt tragen dafür Substanz.

### #110 — der wichtigste offene Fund im ganzen Tracker

Zwischenstand vom 20.07.2026, @svetlana2305 **[belegt]**:

> „**Regel gegen Erfindungen ergaenzt.** Das Modell hatte eine Frist „innerhalb von 2 Minuten" fuer
> die Verfuegbarkeitsabfrage erfunden, die im Konzept nirgends steht. **Jetzt gilt: Zahlen, Fristen
> und Schwellwerte nur aus dem Input.**"

**Das ist eine harte Anforderung an BC2, und sie steht in keinem Vertrag.** Wenn BC3s Modell keine
Zahlen erfinden darf, dann **muss BC2 jede Zahl liefern**, die in einem Akzeptanzkriterium landen
soll: Fristen, Schwellwerte, Mengen, Konfidenzgrenzen. `beschreibung` als Fließtext reicht dafür
nicht verlässlich — sie muss in `fachliche_anforderungen` und `akzeptanzkriterien_geschaeftlich`
maschinennah stehen.

**Die Ironie ist belegbar** **[gemessen]**: Genau die Frist, deren Erfindung BC3 am 20.07.
unterband, steht heute legitim in BC3s Wunschfeld `to_be_vision` —
*„innerhalb von zwei Minuten strukturiert erfasst"* — und von dort in `epic.ziel` der Lieferung:
*„Automatisierte Erfassung und Verfügbarkeitsprüfung von Reiseanfragen innerhalb von zwei Minuten"*.
Der Weg vom Halluzinat zur belegten Vorgabe führt exakt über das Feld, das v2.0 gestrichen hat.

Zwei weitere offene Punkte aus demselben Kommentar **[belegt]**:

> „**„Schema-Pruefung lehnt Verstoesse hart ab" ist NICHT erfuellt.** Im Workflow steckt kein
> Validierungs-Node; ich pruefe den Output bisher ausserhalb der Pipeline. Das gehoert in die CI."
> „Ein Detail geht weiterhin verloren: Die Anforderung „Buchungsnummern fortlaufend je Jahr" wird
> nur als Format JJ-NNNN abgebildet, die jahresweise Sequenz fehlt im Akzeptanzkriterium."

Der zweite Punkt zeigt, dass auch **Geschäftsregeln** beim Story-Schnitt verlorengehen, nicht nur
Zahlen. Ein weiteres Argument für explizite `fachliche_anforderungen`.

### #118 — Architektur, und die Zahl, die nicht mehr stimmt

Kommentar vom 26.06.2026 **[belegt]**:

> „Pipeline läuft End-zu-End — Beispiel-Output (Aurelia: **3 Epics, 19 Stories**)."
> Zwei offene Fragen fürs Plenum: 1. Compliance — welche BC kümmert sich? 2. BC4-Format — JSON oder MD?

Zu den Zahlen siehe Widerspruch W5. Die zweite Plenumsfrage ist inzwischen beantwortet
(`contracts/bc3-to-bc4/README.md`: JSON als `ticket_set.json` **und** `blueprint.json`, Markdown nur
„zum Nachschlagen für Menschen"); die erste ist es nicht — die BC3-README vermerkt am 03.09.2026
noch: *„Das ist seit Juni nicht entschieden."*

### #8 — die Anfrage, die 100 Tage unbeantwortet blieb

**Body-Länge: 0 Zeichen** **[gemessen]**. Keine Labels. Erstellt 29.05.2026 von BC3, adressiert an
BC2. Einzige Aktivität: BC2s Kommentar vom **06.09.2026** — 100 Tage später.

Der leere Body ist selbst ein Befund: BC3 hat den Abstimmungsbedarf angemeldet, ohne ihn zu füllen;
BC2 hat 100 Tage nicht nachgefragt. **Beide Seiten haben denselben Faden fallen lassen.**

### #100 — kein Inhalt, sondern ein Excel-Auswurf

Der Body ist roher HTML-Export aus Microsoft Excel (`mso-*`-Styles, `clip_filelist.xml`)
**[gemessen]**. Verwertbar sind daraus nur die Schrittlisten. Für #160 relevant: Sem 1 enthält
„Vorbereitung prüfen (was liefert BC2 uns)" und „Test mit echtem BC2-Konzept" — beides bis heute
nicht erledigt (#103 leer geschlossen, #108 offen).

Sämtliche Termine dieses Issues sind laut Karte #158 ungültig und hier **nicht** verwertet.

### #108 und #116 — die zwei Tickets, die #160 abschließen müsste

Beide offen, beide ohne Kommentar. #108 „Test mit echtem BC2-Konzept" verlangt *„Echtes BC2-Konzept
durch Pipeline geschickt"* und *„BC4 bestätigt Verwertbarkeit (gate-2)"*. #116 „Übergabe-Kontrakt
final" verlangt *„Kontrakt versioniert im Repo"*.

> **[unsicher]** Solange BC2 kein echtes Konzept liefert, kann #108 nicht schließen. Ob BC3 die drei
> Beispielkonzepte aus PR #176 als Ersatz akzeptiert, ist offen — die Anforderungs-README nennt sie
> ausdrücklich *„Keine BC2-Lieferung und keine Freigabegrundlage"*.

---

## Frage 5 — Reicht die Granularität von `potenziale[]`?

### Die Frage präzise gestellt

Reichen `beschreibung`, `potenzielle_loesung` und `voraussetzungen`, damit BC3 Epics und User
Stories ableiten kann?

**Nein.** Und das ist nicht meine Einschätzung, sondern BC3s: die Anforderungs-README ergänzt genau
deshalb vier Felder, und #110 verbietet dem Modell, das Fehlende zu erfinden.

### Was v2.0 verlangt und was BC3 tatsächlich schreibt **[gemessen]**

v2.0, `potenziale[].beschreibung` (Z. 125–129):

> „Markdown, **Richtwert >= 300 Woerter (maschinell erzwungen: >= 300 Zeichen)**. Pflicht-Inhalt:
> (a) Was wird automatisiert, (b) in welchem/welchen Prozessschritt(en), (c) mit welchem Ergebnis,
> (d) Datenfluesse, (e) beteiligte Akteure/Rollen, (f) Vorbedingungen, (g) Sonderfaelle/Ausnahmen.
> Ziel: BC3 kann daraus User Stories + Akzeptanzkriterien ableiten."

Der Richtwert ist also **nicht** stillschweigend gefallen — er steht wörtlich in v2.0. Was fiel, ist
seine Durchsetzung: **erzwungen werden 300 Zeichen, verlangt sind 300 Wörter.** Ein Faktor von rund
sechs zwischen Anspruch und Prüfung.

BC3s eigene Konzepte, gemessen:

| Datei | Potenziale | `beschreibung` Wörter | Zeichen | `to_be_vision` Wörter |
|---|---|---|---|---|
| `beispiel_uc1_reisebuchung` | 2 | 187 / 177 | 1478 / 1274 | 131 / 120 |
| `beispiel_uc2_wissensbasis` | 2 | 173 / 166 | 1292 / 1223 | 103 / 113 |
| `beispiel_uc3_consultant_placement` | 2 | 150 / 158 | 1190 / 1201 | 116 / 127 |
| `gegenueberstellung_aurelia_bc3` | 3 | 188 / 182 / 151 | 1712 / 1574 / 1377 | 112 / 108 / 100 |

**Kein einziges** erreicht 300 Wörter — alle liegen bei 150–190. Alle erfüllen die 300-**Zeichen**-Regel
mühelos.

### Was das beantwortet

**War das Fallenlassen beabsichtigt?** **[nicht belegt].** Das Dokument
`BC2_Vorbereitungsaufgabe_v1.md` existiert im Repo nicht — weder im Arbeitsverzeichnis noch unter
`bc2-strategic-advisor/`. Ob die Wortzahl bewusst aufgegeben wurde, lässt sich aus den
Repo-Quellen nicht klären.

**Stört es BC3?** **Nein — solange die Struktur da ist.** BC3 setzt Wortzahl durch **Felder**, nicht
durch Länge: 150–190 Wörter Fließtext plus 7–9 `fachliche_anforderungen` plus 5–6
`akzeptanzkriterien_geschaeftlich` plus 100–131 Wörter `to_be_vision`. In Summe deutlich mehr als
300 Wörter, aber **maschinenlesbar gegliedert** statt als Prosa.

> **Das ist die eigentliche Antwort auf Frage 5:** Nicht die Menge des Textes ist die Anforderung,
> sondern seine **Zerlegbarkeit**. Ein 300-Wörter-Absatz nützt einem Story-Schneider weniger als
> neun nummerierte Anforderungssätze. BC3 hat das mit seiner Vorlage praktisch vorgeführt.

**Empfehlung:** Den Richtwert „≥ 300 Wörter" in v3.0 **streichen** und durch `minItems` auf
`fachliche_anforderungen` und `akzeptanzkriterien_geschaeftlich` ersetzen. Die Zeichengrenze von 300
kann bleiben oder auf ~800 steigen (BC3s Minimum liegt bei 1190).

---

## Frage 6 — Übergabeform: Datei, Tabelle oder Ereignis?

### BC3s Antwort: **Datei** **[belegt]**

`bc3-engineering-architect/bc3-architektur-bausteine.md` Z. 6, Stand 26.06.2026:

> „**Eingangs-Storage** = ein Ablage-Ort wo BC2 ihre **Konzept-Dateien** hinlegt, damit unsere
> Pipeline sie **abholen** kann. Aktuell: Google Drive Ordner. Alternative: ein GitHub-Ordner (evtl.
> besser, weil BC2 dort sowieso arbeitet, **Nutzung von Webhook möglich sobald Commit kommt**)."

Drei Aussagen darin:

1. **Datei**, nicht Tabelle, nicht Ereignis-Payload.
2. **Pull** durch BC3, nicht Push durch BC2.
3. Ein **Ereignis** ist vorgesehen, aber nur als *Auslöser* („Webhook sobald Commit kommt") — der
   Inhalt bleibt die Datei.

### Der harte Beleg im Schema **[belegt]**

`konzept_ref.source_file` ist in v3.5 **Pflichtfeld** (Z. 34). **[gemessen]** In allen drei echten
Lieferungen ist es mit einem Dateinamen gefüllt:

| Lieferung | `source_file` |
|---|---|
| uc1 | `konzept_uc1_reisebuchung.json` |
| uc2 | `konzept_uc2_wissensbasis.json` |
| uc3 | `konzept_uc3_consultant_placement.json` |

BC3 kann eine Lieferung **nicht schema-valide erzeugen**, ohne einen Dateinamen für BC2s Konzept zu
nennen. Ein DB-Datensatz hat keinen. Der Dateibezug ist damit nicht Gewohnheit, sondern
**Vertragspflicht**.

### Weiß BC3 von der gemeinsamen Postgres? **Nein.** **[gemessen]**

Volltextsuche über `bc3-engineering-architect/` und `contracts/bc3-to-bc4/README.md` nach
`postgres`, `schema bc2`, `datenbank`:

| Treffer | Kontext | Bezug zur Übergabe? |
|---|---|---|
| `bc3-architektur-bausteine.md` Z. 20 | „PostgreSQL = klassische Datenbank, jede Story = eine Zeile" — **optionale Ticket-Dokumentation bei BC3** | nein |
| 8× in `bc2-anforderung/*.json` | `tech_stack_empfehlung` der **Ziellösung** beim Kunden | nein |
| `bc2-anforderung/README.md` Z. 48 | „Sobald BC2 rechnet, gelten die **Sätze aus der Datenbank**" (Kostensätze) | nein |
| `bc3-to-bc4/README.md` Z. 84 | „sonst … landet nicht in der Datenbank" (zu `kp_id`) | nein |

**Kein einziger Treffer bezieht sich auf die Übergabe BC2 → BC3.** Das Schema `bc2` kommt in BC3s
gesamtem Verzeichnis nicht vor.

> **Widerspruch W6:** Karte #158 legt fest, BC2 schreibe „die Ergebnisse mit Kernprozess-ID zurück
> in Schema `bc2`", und der Trigger sei „Pull, keine Dateiübergabe" (06.09.2026). Das beschreibt
> **BC1 → BC2**. Für **BC2 → BC3** erwartet BC3 weiterhin eine Datei — und **weiß von der
> Postgres-Ablage nichts**. Beides ist vereinbar (BC2 schreibt in die DB *und* legt eine Datei ab),
> aber es ist **nicht abgestimmt**.

### Die gute Nachricht: BC3 ist bereits umgezogen

`contracts/bc3-to-bc4/README.md` Z. 106 nennt für die eigene Ausgangsseite **[belegt]**:

> | Ablage im Google Drive | **Pull Request in dieses Repo** | eine Adresse, Versionsgeschichte in
> git, Freigabe über CODEOWNERS |

Und Z. 41: *„BC3 liefert **nicht** durch einen Commit auf `main`, sondern als Pull Request."* Der
Google-Drive-Ordner wird *„noch zwei Läufe lang parallel beschrieben"*.

**[unsicher]** BC3 hat den Weg für die eigene Ausgangsseite schon gewählt, den BC2 für die
Eingangsseite nur bräuchte zu spiegeln: Datei per PR nach `contracts/`. Dass BC3 das für den Eingang
auch will, ist naheliegend, aber **nicht belegt** — die Bausteine-Datei stammt vom 26.06. und nennt
Google Drive noch als Ist-Zustand.

---

## Frage 7 — Schneidet BC3 ein Potenzial in mehrere Epics?

**Nein. Ein Potenzial wird zu genau einem Epic.** Sechs von sechs. **[gemessen]**

### Die Kardinalitäten im Schema **[belegt]**

| Beziehung | Kardinalität | Fundstelle |
|---|---|---|
| Lieferung → Konzept | **1 : 1** | `konzept_ref` ist ein **Objekt**, kein Array (v3.5 Z. 29) |
| Lieferung → Epics | 1 : n | `epics` Array, `minItems: 1` (v3.5 Z. 77–83) |
| Epic → Stories | 1 : n | `stories` Array, `minItems: 1` (v3.5 Z. 138–144) |
| Story → Abhängigkeiten | 1 : n | `abhaengigkeiten` Array, darf leer sein (v3.5 Z. 204) |

`contracts/bc3-to-bc4/README.md` Z. 65 sagt die fehlende Kante wörtlich **[belegt]**:

> „`epics[]`: **je BC2-Potenzial ein Epic**"

### Der Abgleich Eingang gegen Ausgang **[gemessen]**

Jedes Beispielkonzept aus `bc2-anforderung/` gegen die zugehörige Lieferung in `contracts/bc3-to-bc4/`:

| Lieferung | Potenziale | Epics | Titel identisch | Stories je Epic |
|---|---|---|---|---|
| uc1-reisebuchung | 2 | **2** | 1 von 2 wörtlich | 6, 9 |
| uc2-wissensbasis | 2 | **2** | 1 von 2 wörtlich | 5, 8 |
| uc3-consultant-placement | 2 | **2** | 1 von 2 wörtlich | 7, 7 |

Die je zweiten Titel weichen nur redaktionell ab: *„Angebot erstellen und Buchung nach Freigabe
auslösen"* → *„Automatisierte Angebotserstellung und Buchungsauslösung nach Freigabe"*.
Reihenfolge und Anzahl stimmen exakt.

### Der Aurelia-Mock ist kein Gegenbeispiel

`contracts/examples/mock_automatisierungskonzept.json` hat **3 Potenziale**,
`contracts/bc3-to-bc4/mock/tickets.json` hat **1 Epic** **[gemessen]**. Das sieht nach 3 : 1 aus, ist
aber eine **Teillieferung**: Die `mock/README.md` Z. 41 sagt *„aus BC2 UC-1"*, und der Epic-Titel
*„Automatisierte Antragserfassung via OCR + LLM-Extraktion"* ist der Titel von **Potenzial 1**.
Potenziale 2 und 3 (Rückfrage-Workflow, Bescheid-Generator) wurden schlicht nicht geschnitten.

### Widerspruch W5 — die Epic-Zahlen widersprechen sich

**[gemessen]** Drei verschiedene Angaben zu „uc1":

| Quelle | Datum | Epics | Stories |
|---|---|---|---|
| #104 Schließkommentar | 20.07.2026 | 3 | 21 |
| #118 Kommentar (Aurelia) | 26.06.2026 | 3 | 19 |
| `contracts/bc3-to-bc4/uc1-reisebuchung/ticket_set.json` | 03.09.2026 | **2** | **15** |

Die 3-Epic-Läufe stammen aus dem Google Drive (#160-Kommentar vom 30.08. 19:48 belegt die
Drive-Dateien vom 20.07.). Der Repo-Stand ist **jünger** und gegen ein anderes Eingangskonzept
gefahren. **Maßgeblich ist das Repo** (Karte #158: „maßgeblich ist das Repo").

Damit ist die Vermutung aus dem #160-Kommentar vom 30.08. 19:48 **widerlegt**:

> „Nicht gesichert: „ein Potenzial = ein Epic". … die drei Epics sehen eher nach **Prozessphasen**
> aus (Extraktion → Angebot → Buchung) als nach drei unabhängigen Potenzialen."

Es sind zwei Epics, und sie entsprechen zwei Potenzialen mit denselben Titeln. **Die Epics *sind*
die Prozessphasen — weil BC3 die Potenziale so geschnitten hat.**

### Was das für BC2 heißt

```
1 Prozessprofil → 1 Konzept → 1 BC3-Lieferung
1 Potenzial     → 1 Epic    → 5…9 Stories
```

**BC2s Potenzial-Schnitt ist BC3s Epic-Schnitt.** Es gibt keine Zwischenschicht, die einen zu groben
Schnitt repariert. Praktische Folge, aus BC3s Vorlage abgelesen **[gemessen]**: BC3 setzt **zwei
Potenziale je Teilprozess** an, jedes mit 7–9 `fachliche_anforderungen`, woraus 5–9 Stories werden.

> **[unsicher]** Ob „zwei Potenziale je Teilprozess" eine Regel oder ein Zufall der drei Beispiele
> ist, sagen die Quellen nicht. Als Orientierung für die Schnitttiefe ist es das Beste, was vorliegt.

---

## Frage 8 — Der Vorbefund aus #162, gegengewogen

### Wo BC3 die drei Felder ausdrücklich einfordert **[belegt]**

`bc3-engineering-architect/bc2-anforderung/README.md`, Abschnitt „Was gegenüber v2.0 ergänzt ist":

| Feld | Anmerkung von BC3 |
|---|---|
| `fachliche_anforderungen` | „war in v1.0 Pflicht" |
| `akzeptanzkriterien_geschaeftlich` | „war in v1.0 Pflicht; BC3 leitet daraus die Kriterien je Story ab, BC4 baut dagegen" |
| `to_be_vision` | „war in v1.0 Pflicht **mit ≥ 150 Wörtern**" |
| `betroffene_teilprozess_ids` | „**neu**; Auflage BC0 vom 24.08.2026, die Teilprozess-ID wird durchgereicht" |

> „Zusätzlich sind `aufwand_schaetzung_pt` und `risiken` **wieder Pflicht** — sie sind beim Sprung
> v1.0 → v2.0 von Pflicht auf optional gewechselt."
> „`value.value_quelle` trägt hier den Wert `annahme`. **Er ist im Vertrag v2.0 nicht vorgesehen**;
> die Dateien validieren deshalb nur gegen die erweiterte Fassung."

Die Forderung ist damit **breiter als der Vorbefund aus #162**: nicht drei Felder, sondern
**vier plus zwei Pflicht-Wiederherstellungen plus eine Enum-Erweiterung**.

Zweiter Beleg, unabhängig: die WhatsApp-Rückmeldung vom 20.08.2026, protokolliert im
#160-Kommentar vom 30.08.2026 15:23 **[belegt]**:

> „es fehlen Felder wie **Akzeptanzkriterien**, das bräuchten wir auf jeden Fall"

Dritter Beleg, im #160-Kommentar vom 30.08.2026 19:37 **[belegt]**: *„`fachliche_anforderungen` —
ohne sie keine Stories mit Messverfahren"*, und ausdrücklich: *„Der Rest von v2.0 bleibt. Wir müssen
nicht zurück auf v1."*

### Konsumiert v3.5 diese Felder tatsächlich?

**Nicht als Feld — aber als Inhalt, und das nachweisbar.** v3.5 hat kein Feld namens
`akzeptanzkriterien_geschaeftlich`; die Felder sterben bei BC3 und leben in transformierter Form
weiter. Die Belege stehen unter Frage 2 (nahezu wörtliche Übernahme des Budget-Kriteriums) und
Frage 4 (die Zwei-Minuten-Frist aus `to_be_vision` in `epic.ziel`).

| BC2-Feld (gefordert) | Landet in v3.5 als | Nachweis |
|---|---|---|
| `fachliche_anforderungen[]` | `story.beschreibung` (SOPHIST) + Story-Schnitt | Satz „Anfragen aus Mail und Web-Formular…" → Story 1 |
| `akzeptanzkriterien_geschaeftlich[]` | `story.akzeptanzkriterien[].text` (Given/When/Then) | Budget-Kriterium nahezu wörtlich |
| `to_be_vision` | `epic.ziel` | „innerhalb von zwei Minuten" in beiden |
| `betroffene_teilprozess_ids[]` | `konzept_ref.teilprozess_ids` + `epic.teilprozess_ids` | `["KP-06.TP-2"]` in beiden |
| `aufwand_schaetzung_pt` | — | **[nicht belegt]** — kein Feld in v3.5 |
| `risiken[]` | — | **[nicht belegt]** — kein Feld in v3.5 |

**Zwei Forderungen ohne sichtbare Verwendung:** `aufwand_schaetzung_pt` und `risiken` fordert BC3
zurück auf Pflicht, aber v3.5 hat für beide **kein Zielfeld**. Die BC3-README nennt sogar den Grund
für das eine: *„`typ` und `aufwand_schaetzung` raus. BC4 braucht beides nicht zum Bauen, das sind
Projektmanagement-Felder"* (Z. 148).

> **Offene Frage an Svetlana (F3 unten):** Wofür braucht BC3 `aufwand_schaetzung_pt` und `risiken`
> als Pflicht, wenn die eigene Lieferung sie nicht weiterreicht? Denkbar sind Gate-2-Vorlage oder
> `compliance-audit.json` — **[nicht belegt]**.

---

## Der feldweise Vertragsvergleich: wo bricht die Kette?

### Maschinell nachgewiesen **[gemessen]**

BC3s vier Konzeptdateien gegen `contracts/bc2-to-bc3/konzept.schema.json` v2.0, Draft 2020-12:

```
beispiel_uc1_reisebuchung.json          -> 5 Fehler
beispiel_uc2_wissensbasis.json          -> 5 Fehler
beispiel_uc3_consultant_placement.json  -> 5 Fehler
gegenueberstellung_aurelia_bc3.json     -> 4 Fehler
contracts/examples/mock_automatisierungskonzept.json -> 0 Fehler
```

Die Fehler fallen in **genau drei Klassen**:

| # | Fehler | Ursache in v2.0 | Schwere |
|---|---|---|---|
| **B1** | `/schema_version: '2.0' was expected` | `"const": "2.0"` (Z. 26) | formal, löst sich mit v3.0 |
| **B2** | `/potenziale/N: Additional properties are not allowed ('akzeptanzkriterien_geschaeftlich', 'betroffene_teilprozess_ids', 'fachliche_anforderungen', 'to_be_vision')` | `additionalProperties: false` (Z. 109) | **substanziell** |
| **B3** | `/potenziale/N/value/value_quelle: 'annahme' is not one of ['berechnet','default']` | Enum (Z. 210) | **substanziell** |

**B2 ist der eigentliche Bruch.** Weil `additionalProperties` auf jeder Ebene `false` steht, ist v2.0
**nicht erweiterbar** — BC3 kann die vier Felder nicht beilegen, ohne den Vertrag zu verletzen.
Dieselbe Eigenschaft hat BC3 auf der eigenen Seite zum Versions-Sprung gezwungen; die v3.5-Beschreibung
sagt es wörtlich **[belegt]**: *„In v3.4 hatte sie keinen Platz, weil `additionalProperties` auf allen
Ebenen `false` steht."*

**B3 ist heute schon wirksam:** Alle drei echten BC3-Lieferungen tragen
`konzept_ref.value_quelle = "annahme"` **[gemessen]**. Das ist der von BC2 in #168 zugesagte
Übergangs-Kennwert — v3.5 führt ihn im Enum (Z. 68–72), v2.0 nicht. **BC2 kann den Wert, den BC3
bereits verarbeitet, formal nicht erzeugen.**

### Welches BC3-Pflichtfeld hat in v2.0 keine Quelle?

| BC3-Pflichtfeld (v3.5) | Quelle in v2.0 | Bewertung |
|---|---|---|
| `lieferung_id`, `projekt_kurzname`, `gate2.status` | — | BC3-eigen, unproblematisch |
| `konzept_ref.konzept_id` / `.schema_version` | vorhanden | ✅ |
| `konzept_ref.kp_id` | `kontext.kp_id` | ✅ |
| `konzept_ref.source_file` | **keine** | ⚠️ Übergabeform, s. Frage 6 |
| `epic.epic_id`, `story.story_id` | — | BC3-eigen |
| `epic.titel` | `potenziale[].titel` | ✅ |
| `epic.ziel` (20–600 Z.) | `to_be_kurz` (optional, „1–2 Sätze") | ⚠️ **zu dünn** |
| **`epic.kategorien[]`** | **keine** | ❌ **keine Quelle** — s. Frage 1 |
| `story.beschreibung` | `beschreibung` (Prosa) | ⚠️ **nicht zerlegbar** |
| **`story.akzeptanzkriterien[].text`** | **keine** | ❌ **keine Quelle** — Feld fehlt seit v2 |
| **`story.akzeptanzkriterien[].messverfahren`** | **keine** | ✅ BC3 ergänzt es selbst |
| `story.abhaengigkeiten[]` | — | BC3-eigen, entsteht beim Schnitt |

**Zwei echte Löcher:** `epic.kategorien` (organisatorisch, hängt an #107) und
`akzeptanzkriterien[].text` (fachlich, hängt an den gestrichenen v1-Feldern). Nur das zweite ist
BC2s Aufgabe.

### `priorisierung.schema.json` v2.0 — von BC3 nicht angefasst

**[gemessen]** Die Zeichenkette `priorisierung` kommt in `contracts/bc3-to-bc4/` und
`bc3-engineering-architect/` **nicht vor**; kein Feld aus `eintraege[]` taucht in einem BC3-Artefakt
auf. `konzept_ref` verweist ausschließlich auf das **Konzept**.

> **[unsicher]** BC3 scheint die Priorisierung nicht zu konsumieren. Bestätigt wird das durch die
> #160-Rückmeldung vom 30.08.: *„Prozess-Ranking nötig? **Nein, Potenzial-Ranking reicht**"* — und
> das Potenzial-Ranking steht mit `rang` und `prioritaet_score` schon im Konzept selbst. Ob
> `priorisierung.schema.json` für BC3 überhaupt Vertragsbestandteil ist, ist **[nicht belegt]** und
> gehört gefragt (F5).

---

## Widersprüche — ausdrücklich, ungeglättet

| # | Widerspruch | Quelle A | Quelle B |
|---|---|---|---|
| **W1** | **SOPHIST gegen Given/When/Then.** Karte #158: AK als „User Story nach SOPHIST-Schablone je Potenzial". BC3s Vorlage: 0 von 116 Sätzen SOPHIST, 47 von 47 AK sind Given/When/Then. | #158, 30.08.2026 | `bc2-anforderung/*.json`, 31.08.2026 |
| **W2** | **Skala 1–10 gegen vier Stufen.** #160-Kommentar 30.08. 19:05: „Skala 1–10 (brechend)? **Passt**". BC3s Vorlage vom Folgetag nutzt durchgängig `gering`/`mittel`/`hoch`/`sehr hoch`. | #160, 30.08. | `bc2-anforderung/*.json`, 31.08. **[gemessen]** |
| **W3** | **Versionsstand.** #160 und #158 sprechen durchgängig von `tickets.schema.json` **v3.4**; im Repo liegt **v3.5** mit `"const": "3.5"`. | #160/#158 | `tickets.schema.json` Z. 23 |
| **W4** | **#9 als Abstimmung.** #160 nennt #9 „die einzige dokumentierte Abstimmung". #9 hat **null Kommentare**, Label `needs-discussion`, und nennt als betroffene Schnittstelle fälschlich `bc1-to-bc2`. | #160 | #9 **[gemessen]** |
| **W5** | **Epic-Zahl.** #104 (20.07.): „3 Epics mit 21 Stories". Repo `uc1`: **2 Epics, 15 Stories**. | #104, #118 | `uc1/ticket_set.json` **[gemessen]** |
| **W6** | **Übergabeform.** #158: „Pull, keine Dateiübergabe", Rückschreiben in Schema `bc2`. BC3: „Ablage-Ort wo BC2 ihre Konzept-Dateien hinlegt", `source_file` als Pflichtfeld. BC3 erwähnt Schema `bc2` **nirgends**. | #158, 06.09.2026 | `bc3-architektur-bausteine.md` Z. 6; v3.5 Z. 34 |
| **W7** | **Der Mock ist gegen sein eigenes Schema ungültig.** `mock/tickets.json` erzeugt 3 Fehler gegen v3.5: falsche `schema_version`, fehlende `source_file` und `kp_id`. Die `mock/README.md` nennt selbst „Schema: v3.4". | `mock/tickets.json` | `tickets.schema.json` v3.5 **[gemessen]** |
| **W8** | **`to_be_vision` unterschreitet die eigene Vorgabe.** BC3s README nennt „v1.0 Pflicht mit **≥ 150 Wörtern**"; die eigenen neun Beispiele liegen bei **100–131** Wörtern. | `bc2-anforderung/README.md` Z. 28 | dieselben Dateien **[gemessen]** |
| **W9** | **Verschiedene Prozesse.** BC3 arbeitet an KP-05.TP-1, KP-06.TP-1, KP-06.TP-2. Die Übergangslieferung aus #168 deckt KP-02/03/04. **Keine Überschneidung.** | `bc2-anforderung/README.md` | #168, #160-Kommentar 30.08. 19:48 |

**W2 ist heikler, als es aussieht.** Wenn BC3 am 30.08. „passt" zur Skala 1–10 sagte, am 31.08. aber
eine Vorlage mit dem Vier-Stufen-Enum lieferte, ist unklar, ob die Zustimmung eine Prüfung war oder
eine Höflichkeit. Der Umbau auf 1–10 ist **brechend** und betrifft fünf Felder — er sollte nicht auf
eine Chat-Zeile gestützt werden, der ein widersprechendes Artefakt folgte.

**W9 ist die teuerste.** BC2 hat mit #168 eine Übergangslieferung für KP-02/03/04 geschnitten. BC3
hat drei Konzepte für KP-05/KP-06 geschrieben und daraus bereits vollständige, schema-valide
Lieferungen erzeugt. Beide Seiten haben gearbeitet — **aneinander vorbei.**

---

## Trägt der v2-Vertrag?

**Nein. Er muss gebrochen und erweitert werden — aber die Erweiterung ist bereits entworfen.**

Die Begründung in drei Stufen:

1. **Formal gebrochen** — maschinell nachgewiesen, drei Fehlerklassen (B1–B3). BC3s eigene Vorlage
   validiert nicht gegen v2.0. `additionalProperties: false` macht eine sanfte Erweiterung
   unmöglich.
2. **Fachlich unzureichend** — zwei BC3-Pflichtfelder haben keine Quelle
   (`akzeptanzkriterien[].text`, `epic.kategorien`), zwei weitere eine zu dünne (`epic.ziel` aus
   `to_be_kurz`, `story.beschreibung` aus unzerlegbarer Prosa). #110 verbietet dem Modell, das zu
   überbrücken.
3. **Der Rest trägt** — und das ist die gute Nachricht. BC3 sagt es wörtlich: *„Der Rest von v2.0
   bleibt. Wir müssen nicht zurück auf v1."* Die Umbenennung `use_cases[]` → `potenziale[]`, `value{}`,
   `kategorie`, `betroffene_systeme` (Enum-genau übernommen), `kontext.kp_id`, `gesamtempfehlung`,
   `gate1` sind unstrittig.

### Die minimale Änderungsliste für v3.0, aus BC3s Quellen abgeleitet

| # | Änderung | Belegt durch | Brechend? |
|---|---|---|---|
| 1 | `potenziale[].fachliche_anforderungen[]` — Array von Strings, Pflicht | `bc2-anforderung/README.md` | nein |
| 2 | `potenziale[].akzeptanzkriterien_geschaeftlich[]` — Given/When/Then, **ohne** `messverfahren`, Pflicht | ebenda + Z. 27 | nein |
| 3 | `potenziale[].to_be_vision` — ausführlich, **neben** `to_be_kurz` | ebenda; BC3 führt beide **[gemessen]** | nein |
| 4 | `potenziale[].betroffene_teilprozess_ids[]` — Muster `^KP-(0[1-9]\|10)\.TP-[1-9][0-9]?$` | ebenda; v3.5 Z. 62 | nein |
| 5 | `value.value_quelle` um `annahme` erweitern | v3.5 Z. 68–72; alle 3 Lieferungen **[gemessen]** | nein |
| 6 | `aufwand_schaetzung_pt` und `risiken` auf Pflicht | `bc2-anforderung/README.md` | ja (Pflichtverschärfung) |
| 7 | `schema_version` auf `3.0` | Folge aus 6 + Skala | ja |
| 8 | Richtwert „≥ 300 Wörter" streichen, `minItems` auf 1+2 setzen | s. Frage 5 | nein |

**Die Punkte 1–5 und 8 sind nicht brechend** — sie fügen Felder hinzu und erweitern ein Enum. Wären
sie einzeln zu haben, ginge v2.1. Punkt 6 und die separat beschlossene Skala 1–10 (#158) machen v3.0
daraus.

**Wichtig:** Die Karten-Liste in #158 führt acht Änderungen, die aus **BC2-interner** Sicht
entstanden (`company_id`, `lauf_id`, Skala, finale Reihenfolge). Die Liste hier ist die aus **BC3s**
Sicht. Sie überschneiden sich nur bei Punkt 6 der Karte. **Beide gehören in denselben Schnitt** —
und die BC3-Punkte sind die einzigen, die einen anderen Kontext blockieren.

> **Was BC2 nicht mehr entwerfen muss:** Feldnamen, Datentypen, Satzformen und Beispielinhalte für
> die Punkte 1–5 liegen in `bc3-engineering-architect/bc2-anforderung/` fertig vor. Der Entwurf ist
> von BC3 und damit per Definition konsumierbar. Zu tun bleibt: ins Schema gießen, `minItems`
> festlegen, `gen_mocks.py`/`validate.py` nachziehen — und die **fachliche** Prüfung, um die BC3
> ausdrücklich bittet (`gate1.kommentar`: *„Die Formulierungen darin sind ein Vorschlag von BC3 und
> gehören fachlich von BC2 geprüft."*).

---

## Restfragen — nur Svetlana kann sie beantworten

Sortiert nach Blockadewirkung. F1–F3 blockieren den v3.0-Schnitt.

**F1 · Bestätigt ihr, dass die SOPHIST-Schablone bei euch entsteht und nicht bei uns?**
Belegt ist: eure `beschreibung` ist zu 100 % SOPHIST, eure Wunschfelder zu 0 %. Die Karte vom 30.08.
sagt aber, BC2 liefere SOPHIST je Potenzial. Wenn wir das falsch verstanden haben, bauen wir ein
Feld, das ihr nicht lest. **Ein Satz genügt.**

**F2 · Gilt die Skala 1–10, oder bleiben die vier Stufen?**
Am 30.08. habt ihr „passt" zu 1–10 gesagt; eure Vorlage vom 31.08. nutzt durchgängig
`gering`/`mittel`/`hoch`/`sehr hoch`. Der Umbau ist brechend und betrifft fünf Felder in zwei
Schemas — wir schneiden ihn nicht auf eine Chat-Zeile hin, der ein Gegenbeispiel folgte. (W2)

**F3 · Wofür braucht ihr `aufwand_schaetzung_pt` und `risiken` als Pflicht?**
Eure README fordert beide zurück auf Pflicht, aber `tickets.schema.json` v3.5 hat für keins ein
Zielfeld, und eure BC4-README begründet die Streichung von `aufwand_schaetzung` ausdrücklich. Für
Gate 2? Für `compliance-audit.json`? Davon hängt ab, wie streng wir sie prüfen.

**F4 · Datei oder Datenbank — wie soll das Konzept bei euch ankommen?**
Eure Bausteine (26.06.) nennen einen Ablage-Ort für Konzept-**Dateien**, und `source_file` ist
Pflichtfeld. BC2 schreibt inzwischen zusätzlich in die gemeinsame Postgres, Schema `bc2` — davon
steht bei euch nichts. Reicht euch weiterhin eine Datei per Pull Request nach `contracts/`, so wie
ihr selbst an BC4 liefert? (W6)

**F5 · Lest ihr `priorisierung.schema.json` überhaupt?**
Wir finden in euren Artefakten keinen einzigen Verweis darauf. Wenn ihr nur das Konzept konsumiert,
sparen wir uns die Abstimmung darüber — und `rang`/`prioritaet_score` im Konzept genügen.

**F6 · Welche Prozesse gelten — KP-05/06 oder KP-02/03/04?**
Ihr habt drei Konzepte für KP-05.TP-1, KP-06.TP-1 und KP-06.TP-2 geschrieben. Unsere
Übergangslieferung (#168) deckt KP-02/03/04, die BC0-sauberen. **Es gibt keine Überschneidung.**
Sollen wir auf eure drei umschwenken, obwohl für sie Gate 0 nicht durchlaufen ist? (W9)

**F7 · Wollt ihr die vier Beispielkonzepte als Grundlage von #108 zählen?**
Ihr nennt sie „keine BC2-Lieferung und keine Freigabegrundlage". Wenn wir sie fachlich prüfen und
gegengezeichnet zurückgeben — reicht das für „Test mit echtem BC2-Konzept", oder wollt ihr ein
Konzept aus unserer laufenden Pipeline?

**F8 · Woher kommt `epic.kategorien`, und braucht ihr etwas von uns dafür?**
Pflichtfeld in v3.5, aber #107 („Etiketten-System festgelegt") ist offen. Heute vergebt ihr nur
`it:*`. Sollen `sec:`/`gov:` aus unseren `voraussetzungen` und `risiken` kommen?

**F9 · Reicht euch die Auflösung des Mocks?**
`mock/tickets.json` ist gegen euer eigenes v3.5 ungültig (3 Fehler) und die `mock/README.md` nennt
v3.4. Wollt ihr ihn nachziehen oder löschen? Wir würden sonst weiter gegen einen ungültigen Stand
lesen. (W7)

---

## Was ich ausdrücklich **nicht** geklärt habe

1. **Ob die Wortzahl-Absenkung beabsichtigt war.** `BC2_Vorbereitungsaufgabe_v1.md` liegt nicht im
   Repo. **[nicht belegt]**
2. **Die drei Beispielkonzepte fachlich.** BC3 bittet ausdrücklich um Prüfung
   (*„Entwurf BC3 — fachlich von BC2 zu prüfen"*, `bc2-anforderung/README.md` Z. 44). Das ist
   BC2-Fachfrage, keine Recherche.
3. **Ob `zukunftssicherheit` wirklich entfallen soll.** #160 protokolliert BC3s „Nein — zunächst
   komplett streichen" vom 30.08.; in BC3s Vorlage vom 31.08. fehlt sie folgerichtig. Konsistent,
   aber es ist dieselbe Chat-Quelle wie W1 und W2.
4. **Der Schnitt von v3.0 selbst.** Diese Recherche liefert die BC3-Seite der Änderungsliste. Die
   Zusammenführung mit der BC2-Liste aus #158 und der Zeitpunkt sind Sergios Entscheidung.
5. **BC4s Sicht.** Ob BC4 die Lieferungen tatsächlich *verarbeiten* kann, sagen die Quellen nicht.
   Freigegeben sind sie: `gate2.status` steht in allen drei echten Lieferungen auf **`approved`**
   (nur im Mock auf `pending`) **[gemessen]**. Laut `contracts/bc3-to-bc4/README.md` Z. 49 ist
   jedoch *„der Merge eure Abnahme"* — die Abnahme durch BC4 ist ein anderer Vorgang als Gate 2.

---

## Anhang — verwendete Kommandos

Alle Messungen sind reproduzierbar. Repo-Wurzel als Arbeitsverzeichnis.

```bash
# Bestand und Korrektur der Pfad-Annahmen
find contracts -type f | sort
find bc3-engineering-architect -type f

# Versionsstände
grep -n '"const"' contracts/bc3-to-bc4/tickets.schema.json
grep -rn '2\.1-bc3' .

# Herkunft der BC3-Anforderung
git log -1 --format='%H%n%ad%n%an%n%s%n%b' -- bc3-engineering-architect/bc2-anforderung/README.md

# Issues (Body UND Kommentare — "--comments" allein zeigt nur Kommentare)
gh issue view 9   --repo pg-coe-kmu/coe-factory --json body,comments
gh issue view 103 --repo pg-coe-kmu/coe-factory --json body,comments
for n in 8 11 89 100 104 105 106 107 108 110 111 112 115 116 118 158 160 168; do
  gh issue view $n --repo pg-coe-kmu/coe-factory \
    --json number,title,state,createdAt,body,comments; done
```

```python
# B1–B3: BC3s Vorlage gegen v2.0
import json, glob, jsonschema
s = json.load(open('contracts/bc2-to-bc3/konzept.schema.json'))
v = jsonschema.Draft202012Validator(s)
for f in sorted(glob.glob('bc3-engineering-architect/bc2-anforderung/*.json')):
    print(f, len(list(v.iter_errors(json.load(open(f))))))

# W7: der Mock gegen sein eigenes Schema
s = json.load(open('contracts/bc3-to-bc4/tickets.schema.json'))
v = jsonschema.Draft202012Validator(s)
for f in ['contracts/bc3-to-bc4/mock/tickets.json',
          *glob.glob('contracts/bc3-to-bc4/uc*/ticket_set.json')]:
    print(f, len(list(v.iter_errors(json.load(open(f))))))

# Frage 2: SOPHIST- und Given/When/Then-Anteile
for f in glob.glob('contracts/bc3-to-bc4/uc*/ticket_set.json'):
    d = json.load(open(f))
    st = [s for e in d['epics'] for s in e['stories']]
    ak = [a for s in st for a in s['akzeptanzkriterien']]
    print(f, len(st),
          sum(s['beschreibung'].startswith('Als ') for s in st),
          len(ak),
          sum(a['text'].startswith(('Given', 'Gegeben')) for a in ak))

# Frage 2: null SOPHIST in BC3s Anforderung an BC2
for f in glob.glob('bc3-engineering-architect/bc2-anforderung/*.json'):
    for p in json.load(open(f))['potenziale']:
        assert not any(x.startswith('Als ') for x in p['fachliche_anforderungen'])
        assert all(x.startswith('Gegeben') for x in p['akzeptanzkriterien_geschaeftlich'])

# Frage 7: Potenzial → Epic ist 1:1
for src, dst in [('uc1_reisebuchung', 'uc1-reisebuchung'),
                 ('uc2_wissensbasis', 'uc2-wissensbasis'),
                 ('uc3_consultant_placement', 'uc3-consultant-placement')]:
    k = json.load(open(f'bc3-engineering-architect/bc2-anforderung/beispiel_{src}.json'))
    t = json.load(open(f'contracts/bc3-to-bc4/{dst}/ticket_set.json'))
    print(dst, len(k['potenziale']), len(t['epics']),
          [p['titel'] == e['titel'] for p, e in zip(k['potenziale'], t['epics'])])
```

```bash
# Frage 6: kennt BC3 die gemeinsame Postgres?
grep -rin "postgres\|schema bc2\|datenbank" \
  bc3-engineering-architect/ contracts/bc3-to-bc4/README.md

# Frage 8: konsumiert BC3 die Priorisierung?
grep -rin "priorisierung" bc3-engineering-architect/ contracts/bc3-to-bc4/
```
