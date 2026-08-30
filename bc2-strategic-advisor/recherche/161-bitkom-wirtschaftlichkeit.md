# Bitkom-Wirtschaftlichkeitsmodul — Befunde zu #161

*Recherche 30.08.2026 · BC2 · Quellen: Google Drive `Produkt- & Projektmanagement/Reifegrad/`,
Snapshot v3 im Repo, öffentliche Bitkom-Seite. Grundlage für ein Rechenmodell ohne LLM.*

> **Lesehilfe.** Jede Aussage ist mit einer der drei Marken versehen:
> **[BELEGT]** steht so in einer Primärquelle · **[ABGELEITET]** von mir aus Primärquellen
> gerechnet, Rechenweg angegeben · **[OFFEN]** die Quellen sagen dazu nichts, BC2 muss es setzen.

## Verwendete Quellen

| Kurzname | Datei | Drive-ID |
|---|---|---|
| **Leitfaden 3.0** | `bitkom-leitfaden-reifegradmodell-digitale-geschaeftsprozesse-30-2.pdf`, Stand März 2026 | `1oH3wQiQKg_PJCUoh31hFsMqgNc9Clyff` |
| **Checkliste** | `bitkom-checkliste-reifegradmodell-digitale-prozesse-3-0(2).xlsx` | `1e7vxqj0P6o5r0sVGvkxFbifKNU94jE38` |
| **5-Minuten** | `Bitkom_Reifegrad_in_5_Minuten.md` (17.08.) / `.pdf` (25.08.) — inhaltsgleich geprüft | `17Wk7SmO118vOsxM8w77KFDSh9Cd5ZW73` / `12A3NgcfWqkz_Msaj3wC60AGS8hMTFLlI` |
| **NoroAI-Mappen** | `NoroAI_Bitkom_KP01…KP04.xlsx`, `…Crosssection_KP02-KP04.xlsx` | KP02 = `1EX5KwVTsZ6vFziD_AzAvKf68myT2i8jA` u. a. |
| **BC0-ROI** | `BC0_ROI_Grundlagen_und_Datenluecken.md`, 11.08.2026 | `1uIQrJjHw5goKwQkALeQqEXQU2PVG15vw` |
| **Snapshot v3** | `bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json` | im Repo |

Seitenzahlen beziehen sich auf die Textfassung des Leitfaden-PDF; Kapitelnummern sind belastbarer
als Seitenzahlen und daher zusätzlich genannt.

### Korrektur zum Kommentar an #161

`BC0_ROI_Grundlagen_und_Datenluecken` **existiert im Drive** — als `.md` (11./12.08.2026,
`1uIQrJjHw5goKwQkALeQqEXQU2PVG15vw`) und als `.pdf` vom 25.08. (`17YRuv-P_kvAajn_yDa9n2qhdQbCVcaS4`),
beide im Ordner `1Q14f38szesGfsbv6hWvbbIFiFIp-A32q`, nicht im Ordner `BitKom_Leitfaden`. Das Papier
ist für die Fragen 2 und 4 die wichtigste Einzelquelle und war im Kommentar als fehlend vermerkt.

Nicht gefunden und damit weiterhin offen: **`Voraussetzungen_Prozessautomatisierung.md`** und eine
**Vorgängerfassung 2.0** des Leitfadens. Die Drive-Suche liefert unter „Prozessautomatisierung" nur
`prozessautomatisierung.json` / `.schema.json` vom Juni — andere Artefakte, keine Ersatzquelle.

---

## 1. Nutzwertanalyse nach Bitkom: Kriterien, Gewichtung, Skala, Rangfolge

**Fundstelle:** Leitfaden 3.0, Kap. 3.4 „Wirtschaftlichkeitsbetrachtung", Abschnitt 1
„Qualitative Bewertung (Nutzwertbetrachtung)", S. 45–46.

Bitkom nennt das Ganze **WiBe-Modul**. Es zerfällt in zwei Teile: *quantitativ* =
Kapitalwertbetrachtung (→ Frage 2), *qualitativ* = Nutzwertbetrachtung (hier).

### Das Verfahren in drei Schritten **[BELEGT]**

1. Die **aus dem Reifegradmodell 3.0 abgeleiteten qualitativen Kriterien** werden in *zukünftige
   Prozessanforderungen* überführt, funktional wie nicht-funktional. Bitkom stellt dafür eine
   „beispielhafte Anforderungsliste" bereit, die „initial überprüft und an die spezifischen
   Prozess- und Organisationsbedarfe angepasst werden muss".
2. Bewertet werden **die potenziellen IT-Lösungen bzw. Lösungsanbieter** entlang dieser
   Anforderungen. Erfüllungsstufe je Anforderung, dreistufig vordefiniert:
   **„erfüllt" / „teilweise erfüllt" / „nicht erfüllt"**. Zusätzlich wird je Anforderung
   festgelegt, ob sie **Muss-Kriterium** ist.
3. Zusammenführung nach dem **Prinzip der einfachen Punktbewertung (Scoring-Modell)**. Wörtlich:
   „Dabei werden alle Kriterien **gleichwertig** betrachtet. Die Erfüllungsstufen sind mit festen
   Punktwerten hinterlegt, die automatisch summiert werden." Die Lösung mit dem höchsten
   Gesamtwert gewinnt; Muss-Kriterien wirken als K.-o.-Filter.

### Gewichtung: Bitkom hat sie ausdrücklich **nicht** implementiert **[BELEGT]**

Der Leitfaden ist an dieser Stelle ungewöhnlich offen (S. 46, „Hinweis zur Methodik"):

> „Die klassische Nutzwertanalyse sieht vor, dass jede Anforderung zusätzlich eine Gewichtung
> erhält, die mit der Erfüllungsstufe multipliziert wird. […] **Im aktuellen WiBe-Modul ist diese
> Gewichtung nicht implementiert.** Sie kann jedoch in einem nachgelagerten Schritt ergänzt werden."

Und weiter: die einfache Punktebewertung „berücksichtigt jedoch nicht die unterschiedliche
Bedeutung einzelner Anforderungen".

Damit ist die Teilfrage „welche Gewichtung?" beantwortet: **gar keine.** Wer gewichten will, tut
das als eigene Erweiterung — Bitkom erlaubt es ausdrücklich, liefert aber weder Gewichte noch ein
Verfahren, sie zu bestimmen. **[OFFEN]** für BC2.

### Der Haken, der für BC2 zählt

Bitkoms Nutzwertbetrachtung bewertet **IT-Lösungen gegeneinander**, nicht Automatisierungs­potenziale.
Das Bewertungsobjekt ist der Anbieter bzw. die Lösung, das Ziel ist eine Auswahlentscheidung. BC2
will aber **Potenziale priorisieren** — ein anderes Objekt und eine andere Frage.

Die Methode (Anforderungsliste, dreistufige Erfüllung, Muss-Kriterien, Punktsumme) lässt sich auf
Potenziale übertragen, aber das ist eine **Zweckentfremdung, keine Anwendung**. Sie gehört als
solche gekennzeichnet, sonst entsteht der Eindruck, Bitkom habe eine Potenzialpriorisierung
vorgesehen. Hat es nicht. **[OFFEN]** — BC2-Setzung.

### Was in unserem Material fehlt

Die **konkreten Punktwerte** hinter „erfüllt / teilweise erfüllt / nicht erfüllt" nennt der
Leitfaden nicht („sind mit festen Punktwerten hinterlegt" — welche, steht nicht da). Sie stecken in
der WiBe-Excel-Datei, die Bitkom auf der Projektwebseite separat anbietet. **Diese Datei liegt nicht
im Drive-Ordner `BitKom_Leitfaden`** — dort sind nur Leitfaden und Reifegrad-Checkliste.

*Nicht aus dem Projektmaterial:* Laut der öffentlichen Bitkom-Themenseite
([bitkom.org/Digital-Office/Reifegradmodell-Digitale-Prozesse](https://www.bitkom.org/Digital-Office/Reifegradmodell-Digitale-Prozesse))
werden Checkliste, Management-Cockpit-Vorlage und WiBe als Downloads gebündelt; der Bezug kann eine
Registrierung erfordern. Ob die WiBe-Datei die Punktwerte offenlegt, habe ich **nicht verifiziert** —
ich habe sie nicht heruntergeladen. **[OFFEN]**

Naheliegend und in Scoring-Modellen üblich wäre 2 / 1 / 0 oder 1 / 0,5 / 0. Das ist eine
**Vermutung, kein Befund** — wenn BC2 so rechnet, ist es eine Projektsetzung.

### Nebenbefund: die echte Bitkom-Gewichtung sitzt woanders **[BELEGT]**

Unabhängig vom WiBe-Modul kennt das Reifegradmodell 3.0 sehr wohl einen Gewichtungshebel — die
**Relevanzanpassung je Dimension**, „von 0 bis 100 Prozent in **20er-Schritten**" (Leitfaden Kap. 2.2,
S. 22). Sie beeinflusst die Berechnung des Reifegrads. Relevanz 0 ist explizit vorgesehen, um eine
Dimension ganz auszublenden (Kap. „Einordnung", S. 28).

**In den NoroAI-Mappen steht diese Relevanz durchgängig auf 100 %** — geprüft über alle sechs
Ergebnisblätter der KP-02-Mappe. Der Hebel existiert, ist aber im Projektdatenbestand neutral
gestellt. Wenn BC2 gewichten will, ist das der von Bitkom vorgesehene Ort — und er wirkt auf den
Reifegrad, nicht auf die Nutzwertanalyse.

---

## 2. Kapitalwertbetrachtung: Zinssatz, Nutzungsdauer — und ob das hier trägt

**Fundstelle:** Leitfaden 3.0, Kap. 3.4, Abschnitt 2 „Quantitative Bewertung
(Kapitalwertbetrachtung)", S. 46–47.

### Was Bitkom zum Verfahren sagt **[BELEGT]**

Sämtliche zahlungswirksamen Kosten und Nutzen über einen „definierten Betrachtungszeitraum" werden
erfasst und „mittels eines **festgelegten Kalkulationszinssatzes** auf einen gemeinsamen
Bezugszeitpunkt, das sogenannte **Basisjahr**, abgezinst (Diskontierungsfaktor)".

```
Kapitalwert = Σ (abgezinste Nutzen) − Σ (abgezinste Kosten)
```

Positiver Kapitalwert = wirtschaftlich vorteilhaft, negativer = nicht zu empfehlen.

Kostenseite (S. 35): Einmal- und laufende Aufwände, „z. B. Einführungskosten, Personalaufwände,
Betriebskosten". Nutzenseite: „Ist- und Soll-Nutzenaspekte (z. B. Zeitersparnis, Fehlervermeidung,
Servicequalität, strategische Wirkung)".

### Zinssatz und Nutzungsdauer: **beide nicht genannt** **[BELEGT — als Negativbefund]**

Ich habe den vollständigen Leitfadentext (1 983 Zeilen) nach `Zins`, `Kalkulationszins`,
`Nutzungsdauer`, `Betrachtungszeitraum`, `Basisjahr`, `Amortis`, `Barwert`, `Rendite` durchsucht.
**Keine einzige Zahl.** Die Formulierungen sind durchgehend passiv — „*eines festgelegten*
Kalkulationszinssatzes", „*einen definierten* Betrachtungszeitraum". Beides ist vom Anwender zu
setzen.

Damit ist die Teilfrage beantwortet: **Bitkom gibt weder Zinssatz noch Nutzungsdauer vor.**
Jede Zahl, die BC2 einsetzt, ist eine Projektsetzung. **[OFFEN]**

*Nicht aus dem Projektmaterial:* Der Leitfaden verweist darauf, dass sich das Modul „methodisch an
dem WiBe-Standard […], wie er in vielen Behörden und öffentlichen Programmen (z. B. OZG,
Registermodernisierung, EfA-Finanzierung) etabliert ist" orientiert (S. 35). Das ist das
WiBe-Konzept des Bundes; dort wird der Kalkulationszinssatz üblicherweise aus den vom BMF
veröffentlichten Sätzen für Wirtschaftlichkeitsuntersuchungen nach § 7 BHO abgeleitet. **Ich habe
das nicht am Primärdokument verifiziert** und nenne bewusst keine Zahl. Wer sie braucht, muss die
BMF-Veröffentlichung ziehen und datieren.

### Bitkoms eigene Grenzziehung **[BELEGT]**

Der Leitfaden relativiert das Modul deutlich (S. 46 f.):

- „Es ersetzt **kein vollständiges WiBe-Gutachten**, sondern bietet eine standardisierte,
  niedrigschwellige **Vorstufe**."
- „Grenzen bestehen insbesondere darin, dass das Modul **keine vollständige betriebswirtschaftliche
  Amortisationsrechnung liefert**."
- „Dabei verfolgt das WiBe-Modul **nicht das Ziel einer vollständigen betriebswirtschaftlichen
  Amortisationsrechnung**, sondern stellt ein pragmatisches Werkzeug zur Verfügung" (S. 35).

Der letzte Satz ist wichtig und wird leicht falsch gelesen: Bitkom sagt nicht, Amortisationsrechnung
sei zu einfach — Bitkom sagt, das eigene Modul leiste sie *nicht*.

### Empfehlung: Amortisation, nicht Kapitalwert

**Ich empfehle, den Kapitalwert nicht zur Leitkennzahl zu machen.** Drei Gründe, in absteigender
Härte:

1. **Der Kapitalwert braucht genau die Größe, die im Projekt frei erfunden ist.** BC0 hält
   fest (ROI-Papier, Abschnitt 4): Entwicklung, Einführung, Schulung, Lizenzen, Betrieb, Wartung,
   LLM-/API-Kosten — „**Kein einziger dieser Werte steht in einem der beiden Datenmodelle.**"
   Der Kapitalwert diskontiert also eine erfundene Zahl über einen gesetzten Zeitraum mit einem
   gesetzten Zins. Das Ergebnis sieht präziser aus, als es ist — drei Setzungen erzeugen eine
   Nachkommastelle, die nichts trägt.
2. **Die Diskontierung ändert bei den hier plausiblen Größenordnungen die Rangfolge nicht.** Sie
   skaliert alle Vorhaben mit demselben Faktor; sie diskriminiert nur dort, wo sich die
   *zeitlichen Profile* der Zahlungsströme unterscheiden. Solange BC2 für alle Potenziale dasselbe
   Profil unterstellt — und mangels Daten wird es das —, ist die Abzinsung reine Zierde.
3. **BC0 empfiehlt dasselbe** (ROI-Papier, Abschnitt 6.1): „Bei mehrjähriger Betrachtung wäre ein
   Kapitalwert mit Diskontierung methodisch sauberer. Für den Projektrahmen dürfte die
   **Amortisationsdauer** die nützlichste Zahl sein — sie ist die verständlichste und macht
   Größenordnungen sofort vergleichbar."

Die von BC0 vorgeschlagene Rechnung (ROI-Papier 6.1) kommt ohne Zins und Nutzungsdauer aus:

```
Einsparung pro Jahr   = Kosten IST − Kosten SOLL − laufende Kosten
Amortisationsdauer    = Investition / Einsparung pro Jahr
ROI über n Jahre      = (Einsparung × n − Investition) / Investition
```

**Vorschlag für BC2:** Amortisationsdauer als Leitkennzahl, mit offengelegter Investitionsannahme
und als Bandbreite. Den Kapitalwert optional als Nebenrechnung mitführen, damit die Bitkom-Anbindung
formal gewahrt bleibt — mit ausgewiesenem Zins und Zeitraum als sichtbare Setzungen, nicht als
Modellwahrheit. So bleibt das Ticketziel „legt seine Annahmen offen" erfüllt, ohne Scheingenauigkeit.

### Zwei Fallen bei der Rangfolge, die BC0 benennt **[BELEGT]**

Aus ROI-Papier 6.2, für ein Rechenmodell unmittelbar relevant:

- **Nach absoluter Einsparung ordnen, nicht nach ROI in Prozent.** Sonst schlägt ein Vorhaben mit
  800 € Investition und 400 % ROI eines mit 40 000 € Jahreseinsparung. „Prozent ist eine schöne Zahl
  und eine schlechte Rangfolge."
- **Gemeinsame Kosten nicht mehrfach zählen.** Brauchen fünf Potenziale dieselbe Plattform, ist die
  Investition einmal da; eine Rechnung „je Prozess" zählt sie fünfmal und verwirft womöglich alle fünf.

Beides ist im Modell zu berücksichtigen, sonst rechnet es reproduzierbar falsch.

---

## 3. Die nichtlineare Skala — wie man Reifegrad in Nutzen übersetzt

Das ist die folgenreichste Frage, und hier gibt es sowohl einen **Widerspruch in den Bitkom-Quellen**
als auch eine **saubere Lösung**.

### 3.1 Zwei Bitkom-Skalen, die sich widersprechen **[BELEGT]**

Der **Leitfaden 3.0**, Tabelle 3 „Skalenwertetabelle" (Kap. 2.1, S. 19), definiert:

| Stufe | Einschätzung in Prozent | Bandbreite |
|---|---|---|
| 1 | 0 | 0 pp (Punktwert) |
| 2 | > 0 % – 40 % | 40 pp |
| 3 | > 40 % – 50 % | 10 pp |
| 4 | > 50 % – 95 % | **45 pp** |
| 5 | > 95 % | 5 pp |

Die **Checkliste** (`Bewertung, Checkliste`, Spaltenköpfe) definiert dagegen:

| Stufe | Einschätzung in Prozent | Bandbreite |
|---|---|---|
| 1 | 0 – 10 % | 10 pp |
| 2 | > 10 % – 40 % | 30 pp |
| 3 | > 40 % – 60 % | 20 pp |
| 4 | > 60 % – 90 % | 30 pp |
| 5 | > 90 % | 10 pp |

**Das sind zwei verschiedene Skalen in derselben Modellversion 3.0.** Die Checklisten-Skala ist
symmetrisch und nahezu linear; die Leitfaden-Skala ist stark asymmetrisch.

**Entscheidend:** Die **ausgefüllten NoroAI-Mappen tragen die Checklisten-Skala**, nicht die des
Leitfadens — verifiziert über die Spaltenbeschriftungen in `NoroAI_Bitkom_KP02.xlsx`
(`Bewertung 1 … (0-10%)`, `Bewertung 3 … (>40% - 60%)`, `Bewertung 4 … (>60 - 90%)`). Das Instrument,
mit dem die 690 Bewertungen in der Datenbank tatsächlich erhoben wurden, verwendet also die
**andere** Skala als die, auf die sich die BC2-Invariante in `bc2-strategic-advisor/CLAUDE.md` und
der BC0-Einseiter berufen.

> **Das ist für BC2 zu entscheiden, bevor gerechnet wird.** Beide Skalen sind Bitkom-Material. Die
> Wahl verschiebt den ausgewiesenen Erfüllungsgrad um mehrere Prozentpunkte (Zahlen in 3.4).
> Ich habe keine Quelle gefunden, die den Widerspruch auflöst. **[OFFEN]**

Eine Anmerkung zur Herkunft: Das Vorwortblatt der Checkliste sagt, das Modell „basiert auf den
öffentlich verfügbaren Dokumenten zum Reifegradmodell Digitale Prozesse 3.0 des Bitkom". Ob die
Datei im Drive das Original von Bitkom ist oder eine nachgebaute Fassung, lässt sich daraus **nicht
sicher entscheiden**. Falls nachgebaut, wäre die Leitfaden-Skala die maßgebliche und die
Checklisten-Skala ein Übertragungsfehler, der sich in alle NoroAI-Erhebungen fortgepflanzt hat.
Das zu klären ist wichtiger als jede Feinheit der Rechenformel. **[OFFEN]**

### 3.2 Präzisierung der BC0-Warnung **[ABGELEITET]**

Der BC0-Einseiter sagt: „Der Sprung von 3 auf 4 ist der größte im ganzen Modell — er überspannt
45 Prozentpunkte, während zwischen 2 und 3 nur zehn liegen."

Das vermischt zwei verschiedene Größen. Sauber getrennt (Leitfaden-Skala):

- **Bandbreite der Stufe 4** = 45 pp (50–95 %). Das ist die Zahl, die BC0 nennt. Sie ist die
  *Unschärfe innerhalb* der Stufe, nicht der Abstand zur Nachbarstufe.
- **Abstand zwischen den Bandmitten** 3 → 4 = 72,5 − 45 = **27,5 pp**. Die Abstände insgesamt:
  1→2: 20 pp · 2→3: 25 pp · **3→4: 27,5 pp** · 4→5: 25 pp.

Die Schlussfolgerung „3→4 ist der größte Sprung" hält unter **beiden** Lesarten — aber mit
verschiedenen Zahlen, und nur die zweite ist der „Sprung". Für das Rechenmodell ist die
Unterscheidung wesentlich: die 45 pp gehen in die **Intervallbreite** ein, die 27,5 pp in den
**Punktwert**.

Und: die Abstände zwischen den Bandmitten sind mit 20 / 25 / 27,5 / 25 pp **deutlich gleichmäßiger,
als die Bandbreiten vermuten lassen**. Der eigentliche Schaden einer linearen Umrechnung ist
deshalb geringer als befürchtet — der eigentliche Befund liegt woanders, nämlich in der Unschärfe.

### 3.3 Warum die Warnung trotzdem greift: die Datenlage **[ABGELEITET]**

Verteilung aller 690 NoroAI-Bewertungen (Snapshot v3, gezählt):

| Stufe | Anzahl | Anteil | Bandbreite (Leitfaden) |
|---|---|---|---|
| 1 | 10 | 1,4 % | 0 pp |
| 2 | 76 | 11,0 % | 40 pp |
| 3 | 205 | 29,7 % | 10 pp |
| **4** | **361** | **52,3 %** | **45 pp** |
| 5 | 38 | 5,5 % | 5 pp |

**Über die Hälfte aller Bewertungen liegt auf genau der Stufe mit dem breitesten Band.** Das ist der
Grund, warum die Nichtlinearität hier praktisch beißt und nicht bloß theoretisch: Der Modalwert des
Datenbestands ist zugleich die unschärfste Aussage, die das Modell kennt. Eine „4" heißt
„irgendetwas zwischen 50 % und 95 %" — das ist fast der halbe Wertebereich.

### 3.4 Das korrekte Übersetzungsverfahren **[ABGELEITET]**

**Regel: nicht den aggregierten Reifegrad übersetzen, sondern jede Einzelbewertung — und dann
aggregieren.**

```
je Item:   Stufe s  →  Band [lo(s), hi(s)]        aus der Skalentabelle
Aggregat:  [ Mittelwert aller lo , Mittelwert aller hi ]
Punktwert: Mitte des Aggregatintervalls
```

Der Mittelwert ist in beiden Argumenten monoton, deshalb ist die komponentenweise Mittelung des
Intervalls zulässig. Ergebnis für die sechs erhobenen Kernprozesse (Snapshot v3, Leitfaden-Skala):

| KP | Reifegrad | **Erfüllungsgrad korrekt** | Punktwert | naiv linear | Fehler linear |
|---|---|---|---|---|---|
| KP-01 | 3,19 | 37,6 – 64,2 % | 50,9 % | 54,7 % | +3,8 pp |
| KP-02 | 3,70 | 47,7 – 80,9 % | 64,3 % | 67,5 % | +3,2 pp |
| KP-03 | 3,77 | 50,7 – 81,0 % | 65,9 % | 69,2 % | +3,3 pp |
| KP-04 | 3,88 | 50,3 – 87,9 % | 69,1 % | 72,0 % | +2,9 pp |
| KP-05 | 3,20 | 41,0 – 60,2 % | 50,6 % | 55,0 % | +4,4 pp |
| KP-06 | 2,25 | 11,3 – 41,5 % | 26,4 % | 31,2 % | +4,8 pp |

*„naiv linear" = `(Reifegrad − 1) / 4 × 100` — die Umrechnung, vor der BC0 warnt.*

**Drei Ergebnisse:**

1. **Die lineare Umrechnung überschätzt systematisch**, um 2,9 bis 4,8 Prozentpunkte. Bei KP-06 sind
   das 31,2 statt 26,4 % — ein relativer Fehler von 18 %. Der Fehler ist einseitig, also kein
   Rauschen, sondern ein Bias. **BC0s Warnung ist bestätigt**, wenn auch aus einem anderen Grund als
   im Einseiter genannt (nicht der Sprung 3→4, sondern die Asymmetrie der Bänder insgesamt).
2. **Der Punktwert lässt sich billig approximieren.** Lineare Interpolation zwischen den *Bandmitten*
   (0 / 20 / 45 / 72,5 / 97,5) statt zwischen den Stufenzahlen reproduziert die korrekte Intervallmitte
   auf **≤ 0,8 pp** genau — geprüft für alle sechs Kernprozesse. Wer den Punktwert direkt aus dem
   aggregierten Reifegrad braucht, kann das so tun. **Das Intervall aber nicht** — es entsteht nur
   aus der Aggregation der Einzelbänder.
3. **Das Intervall ist 25 bis 38 Prozentpunkte breit.** Jede Nutzenaussage, die aus dem Reifegrad
   einen Punktwert macht, täuscht eine Genauigkeit vor, die die Skala nicht hergibt.

### 3.5 Die unbequeme Folge: der Reifegrad rangiert, aber er trennt nicht **[ABGELEITET]**

Die Rangfolge KP-06 < KP-01 ≈ KP-05 < KP-02 < KP-03 < KP-04 ist **unter allen drei
Umrechnungsverfahren identisch** — korrekte Bandaggregation, Bandmitten-Interpolation, naiv linear.
Auch der Wechsel auf die Checklisten-Skala ändert sie nicht, mit **einer** Ausnahme: KP-01 und KP-05
tauschen die Plätze (Leitfaden 50,9 / 50,6 — Checkliste 54,6 / 55,0). Beide liegen mit 0,3 bzw.
0,4 pp Abstand ohnehin im Rauschen; deshalb oben das „≈". Das ist genau BC0s Stabilitätskriterium
(ROI-Papier 3): „Eine Rangfolge, die bei jeder Annahme dieselbe bleibt, ist belastbar" — und
zugleich ein Beleg dafür, dass sie bei eng beieinanderliegenden Werten eben *nicht* stabil ist.

**Aber die Intervalle überlappen fast vollständig.** KP-02 liegt bei 47,7–80,9 %, KP-04 bei
50,3–87,9 % — die Obergrenze von KP-02 (80,9) liegt weit über der Untergrenze von KP-04 (50,3).
Der Reifegradunterschied zwischen den drei BC0-sauberen Prozessen (3,70 / 3,77 / 3,88) ist
**kleiner als die Unschärfe der Skala**.

Für BC2 heißt das konkret:

- Der Reifegrad taugt als **Ordnungsmerkmal** — die Reihenfolge ist stabil.
- Er taugt **nicht** als Beleg dafür, dass KP-04 „besser" sei als KP-02. Der Abstand ist nicht
  signifikant.
- Eine Aussage wie „KP-04 hat 4 Prozentpunkte mehr Automatisierungspotenzial" ist **nicht gedeckt**.

Das ist keine Schwäche der Rechnung, sondern eine Eigenschaft des Messinstruments — und genau die
Art Aussage, die ein Modell offenlegen soll, statt sie wegzurunden.

### 3.6 Was der Leitfaden zur Übersetzung sagt: **nichts** **[BELEGT — Negativbefund]**

Suche über den vollständigen Leitfadentext nach `linear`, `Interpolat`, `Prozentwert`, `Bandbreit`,
`Intervall`: **kein einziger Treffer** im Zusammenhang mit der Umrechnung von Reifegrad in Nutzen.

Der Leitfaden sagt sogar das Gegenteil einer Übersetzungsvorschrift (Kap. 2.2, S. 22 und
Limitierung 4, S. 26):

> „Wie bei allen Methoden der Prozessanalyse liefert das Modell **keine automatisierten
> Handlungsempfehlungen**. Es beschreibt den Status quo – nicht die Lösung."

> „Das Reifegradmodell identifiziert Reifegradunterschiede und Handlungsfelder, **gibt aber keine
> konkreten Handlungsempfehlungen oder Maßnahmen vor**."

Der Reifegrad ist bei Bitkom die **Machbarkeitsachse**, nicht die Nutzenachse — so liest ihn auch
BC0 (ROI-Papier 6.2: „Der Bitkom-Reifegrad je Teilprozess sagt, ob ein Prozess überhaupt
automatisierungsreif ist. Aus ROI und Reifegrad wird eine Portfolio-Matrix statt einer Liste.").

**Empfehlung:** Reifegrad **nicht** in eine Nutzengröße umrechnen, sondern als zweite Achse führen.
Der Nutzen kommt aus Menge × Zeit × Kostensatz × Automatisierungsgrad (BC0-Papier, Blöcke 1–3); der
Reifegrad sagt, ob das Vorhaben trägt. Wenn dennoch eine Erfüllungsgrad-Aussage gebraucht wird — für
die Präsentation etwa —, dann nach dem Verfahren aus 3.4 und **immer als Intervall**.

---

## 4. Bandbreiten und Güte-Flags

### 4.1 Eine etablierte Konvention gibt es nicht **[BELEGT — Negativbefund]**

Die gesuchte Kopplung „Güte-Flag → Intervallbreite" steht **weder im Leitfaden noch in der
Checkliste noch im BC0-Material**. Der Leitfaden kennt zum Umgang mit Unsicherheit genau einen Satz
(Kap. 3.4, S. 47):

> „**Unsicherheiten in der quantitativen Bewertung sollten durch Risikoaufschläge/-abschläge oder
> Sensitivitätsanalysen adressiert werden.**"

Das legitimiert den *Mechanismus* — Zu- und Abschläge, Szenarienrechnung — nennt aber **keine
Beträge, keine Prozentsätze und keine Zuordnung zu Gütestufen**. Ergänzend fordert derselbe
Abschnitt: „Die sorgfältige Dokumentation der Bewertungen und der zugrunde liegenden Annahmen ist
essenziell, um die Nachvollziehbarkeit und Transparenz der Ergebnisse sicherzustellen."

**Antwort auf die Frage: Nein, es gibt keine etablierte Konvention. Das ist eine Projektsetzung, die
BC2 selbst treffen muss.** Bitkom deckt, *dass* mit Bandbreiten gearbeitet wird, nicht *wie breit*.

### 4.2 Die Güte-Flags aus dem Ticket existieren so nicht **[BELEGT]**

Das Ticket nennt `belegt` / `geschaetzt` / `geraten`. Im tatsächlichen Datenbestand finde ich diese
Trias nicht:

- **Snapshot v3, 690 Bewertungen:** Feld `quelle` trägt nur `baseline` (570) und `manuell` (120).
  Das ist die **Erhebungsherkunft**, keine Güteaussage. Die Zeichenketten `belegt`, `geschaetzt`,
  `geraten` kommen im Snapshot **nicht vor**.
- **`gate_pruefpunkt_werte` ist leer** (#159, gemessen 30.08.) — die erhoffte Quelle für Güte-Flags
  existiert noch nicht.
- **`beleg` ist zu 100 % gefüllt** (Snapshot: 0 leere Belege von 690, `beleg_quote: 100`). Die
  Belegpflicht ist hart erzwungen — aber sie ist **binär**: jede Bewertung hat einen Beleg, also
  unterscheidet das Feld nichts. Als Güteachse ist es unbrauchbar, solange es keine Bewertung der
  Belegqualität gibt.

Stattdessen kennt BC0 **zwei andere, feinere Vokabulare** (ROI-Papier 2.2 und 5.5):

| Größe | Feld | Werte |
|---|---|---|
| Zeitangabe | `focus_step_duration_source` | `gemessen` / `geschaetzt` / `aus_system` |
| Zeitangabe | `focus_step_duration_confidence_pct` | **0–100, numerisch** |
| Kostensatz | `rollen_kostensaetze.quelle` | `erhoben` / `branchenreferenz` / `geschaetzt` |

BC0 begründet das ausdrücklich: „Ein ROI aus gemessenen Zeiten ist etwas anderes als einer aus
geschätzten mit 40 % Sicherheit. Ohne diese Angabe sieht eine Schätzung aus wie eine Messung."

**Der wichtigste Fund hier:** `focus_step_duration_confidence_pct` ist eine **numerische** Größe
0–100. Sie ist einer dreistufigen Flagge deutlich überlegen, weil sie die Intervallbreite direkt
liefert, ohne eine willkürliche Stufen-zu-Breite-Tabelle zu brauchen. Wenn BC1 dieses Feld füllt,
sollte BC2 darauf aufsetzen statt auf `belegt/geschaetzt/geraten`.

**Achtung, Abweichung Papier ↔ Datenbank:** Das ROI-Papier empfiehlt für NoroAI
`quelle = 'branchenreferenz'` (Abschnitt 5.5: „Für NoroAI […] kommen ausschließlich
Branchenreferenzwerte in Frage"). Gemessen wurde am 30.08. jedoch durchgängig `geschaetzt` (#159,
K1–K5, 40–140 EUR/h). Maßgeblich ist die Datenbank — aber die Abweichung heißt, dass die Kostensätze
schwächer belegt sind, als das Papier vorsah.

### 4.3 Was BC0 zu Bandbreiten empfiehlt **[BELEGT]**

ROI-Papier, Abschnitt 3:

> „**Empfehlung:** Mit einer Bandbreite rechnen (**vorsichtig / realistisch / optimistisch**) statt
> mit einem Punktwert, und die Bandbreite ausweisen. Eine Rangfolge, die bei jeder Annahme dieselbe
> bleibt, ist belastbar; eine, die kippt, ist es nicht."

Und zur Ursache (Abschnitt 3): „**Der Automatisierungsgrad ist der empfindlichste Wert der gesamten
Rechnung.** Wer 100 % ansetzt, weil ‚der Schritt wird automatisiert', rechnet sich systematisch
reich — in der Praxis bleiben Prüfung, Ausnahmefälle und Nacharbeit."

Ebenso (Abschnitt 5.3) zum Vollkostenfaktor: „In Summe liegt der Vollkostensatz typischerweise beim
**1,7- bis 2,2-fachen** des reinen Bruttostundenlohns. **Welcher Faktor angesetzt wird, ist eine
Festlegung und muss dokumentiert sein** — sonst ist der ROI nicht reproduzierbar."

Das ist die einzige konkrete Bandbreite im gesamten Projektmaterial — und sie betrifft den
Kostensatz, nicht den Reifegrad.

### 4.4 Vorschlag für BC2 — als Setzung gekennzeichnet **[OFFEN]**

Da keine Konvention existiert, muss BC2 eine treffen. Ich schlage vor, sie an das zu binden, was
**belegt** ist, statt eine Stufen-zu-Breite-Tabelle zu erfinden:

**Drei Quellen von Unschärfe, drei verschiedene Behandlungen:**

1. **Reifegrad-Achse — Breite kommt aus der Skala selbst, keine Setzung nötig.**
   Das Intervall entsteht aus den Bandgrenzen der Skalentabelle (Verfahren 3.4). Das ist der
   sauberste Teil des Modells: **belegt, nicht gesetzt**, weil Bitkom die Bänder definiert.
2. **Numerische Güte, wo vorhanden — `confidence_pct` direkt verwenden.**
   Wo BC1 eine Sicherheit in Prozent liefert, ist die Halbbreite daraus ableitbar, ohne eine Stufe
   zwischenzuschalten. Auch das ist überwiegend belegt.
3. **Alles Übrige — Szenarien statt Intervallbreiten.**
   Für Investition, laufende Kosten und Automatisierungsgrad gibt es keine Datengrundlage
   (BC0: „fehlt überall"). Hier ist BC0s Dreier-Szenario vorsichtig / realistisch / optimistisch
   ehrlicher als ein gerechnetes Intervall, weil es die Annahme sichtbar macht, statt sie in eine
   Breite zu verstecken. Das entspricht Bitkoms „Sensitivitätsanalysen".

**Das Abnahmekriterium ist nicht die Breite, sondern die Stabilität.** BC0s Satz ist der brauchbarste
Maßstab im ganzen Material: Ein Ergebnis ist belastbar, wenn die *Rangfolge* über alle drei Szenarien
gleich bleibt. Das lässt sich deterministisch prüfen, braucht kein LLM und macht die Frage
„wie breit ist breit genug?" gegenstandslos — die Breite muss nur groß genug sein, um die Rangfolge
zu testen.

Was ich **ausdrücklich nicht** empfehle: eine Tabelle der Form „`belegt` → ±10 %, `geschaetzt` →
±25 %, `geraten` → ±50 %". Solche Zahlen sehen fundiert aus, sind es aber nicht, und sie sind
unprüfbar. Wenn BC2 sie dennoch braucht, gehören sie als frei gewählt gekennzeichnet — nicht als
Konvention ausgegeben.

---

## 5. Die Schwelle 3,5

**BC0s Aussage stimmt. Die Schwelle 3,5 ist eine Projektsetzung, keine Bitkom-Vorgabe.** **[BELEGT]**

Geprüft auf drei Wegen:

1. **Volltextsuche** im Leitfaden 3.0 nach `3,5`: fünf Treffer, **alle** in Beispieltabellen als
   errechneter Kriteriums- oder Dimensionswert (cross-sectionale Tabelle 4, Verprobungsbeispiele
   Kap. 4). **Kein einziger Treffer als Schwelle, Grenzwert oder Entscheidungskriterium.**
2. **Volltextsuche** nach `Schwelle`, `Grenzwert`, `Mindestreifegrad`: `Grenzwert` und
   `Mindestreifegrad` kommen nicht vor. `Schwelle` kommt zweimal vor (Kap. 4, Verprobung EASY
   SOFTWARE) — beide Male **rein beschreibend** („an der Schwelle zwischen teilweise digital und
   überwiegend digital"), nie als Entscheidungskriterium. Keine Fundstelle legt einen
   Reifegrad-Schwellenwert für Automatisierungseignung fest.
3. **Inhaltlich:** Der Leitfaden schließt so etwas sogar aus. Limitierung 4 (S. 26): das Modell
   „gibt aber keine konkreten Handlungsempfehlungen oder Maßnahmen vor. Die Interpretation der
   Ergebnisse und die Ableitung geeigneter Schritte bleiben **vollständig bei den Anwenderinnen und
   Anwendern**." Und Kap. 2.2 (S. 22): „Es beschreibt den Status quo – nicht die Lösung."
   Eine Schwelle „ab hier lohnt sich Automatisierung" wäre genau die Handlungsempfehlung, die Bitkom
   verweigert.

Der BC0-Einseiter formuliert es korrekt und deckungsgleich mit dem Leitfaden: „Unsere Schwelle von
3,5 ist deshalb eine Projektsetzung, keine Bitkom-Vorgabe. Wir sehen einen Prozess erst ab einem
Reifegrad von 3,5 im Fokus-Schritt als tragfähigen Automatisierungskandidaten an. Das ist begründet
und dokumentiert, aber es ist unsere Festlegung."

### Drei Beobachtungen, die BC2 kennen sollte

**Die Schwelle wirkt bereits.** In #159 ist KP-01 (Reifegrad 3,19) mit der BC0-Sperre
„reifegrad zu niedrig" belegt. Die Setzung ist also nicht theoretisch, sie schließt Prozesse aus.

**Der Gesamtreifegrad von NoroAI liegt bei 3,49** (Snapshot v3, `reifegrad.gesamt`) — einen
Hundertstelpunkt unter der Schwelle. Das ist wohl Zufall, macht aber sichtbar, wie scharf eine
gesetzte Grenze schneidet, wenn die Messwerte dicht darum liegen.

**Und die Schwelle ist unschärfer als der Abstand, den sie zieht.** Nach 3.5 liegt die Unschärfe
eines aggregierten Reifegrads bei 25–38 Prozentpunkten Erfüllungsgrad. Ein Prozess bei 3,49 und
einer bei 3,51 sind nicht unterscheidbar. Wenn BC2 die Schwelle übernimmt, sollte sie als
**weiche Grenze mit Begründungspflicht** wirken, nicht als harter Filter — oder zumindest die
Grenzfälle sichtbar machen, statt sie stillschweigend zu verwerfen.

Ob 3,5 der richtige Wert ist, lässt sich aus dem Material **nicht beantworten**. Eine Herleitung der
Zahl habe ich nirgends gefunden — weder im Einseiter noch im ROI-Papier. **[OFFEN]**

---

## Was ich nicht klären konnte

| Punkt | Warum |
|---|---|
| **Welche der beiden Bitkom-Skalen gilt** (Leitfaden vs. Checkliste) | Beide sind 3.0-Material und widersprechen sich. Keine auflösende Quelle gefunden. **Größtes offenes Risiko** — verschiebt jeden Erfüllungsgrad. |
| **Punktwerte der WiBe-Erfüllungsstufen** | Der Leitfaden sagt „feste Punktwerte", nennt sie nicht. Die WiBe-Excel liegt nicht im Drive; ich habe sie nicht von bitkom.org bezogen. |
| **Kalkulationszinssatz und Nutzungsdauer** | Bitkom nennt beides nicht. Der Verweis auf den WiBe-Standard des Bundes ist eine Spur, die ich nicht am Primärdokument (BMF) verifiziert habe. |
| **Herleitung der Schwelle 3,5** | Nirgends begründet, nur als gesetzt bezeichnet. |
| **Ob die Drive-Checkliste das Bitkom-Original ist** | Ihr Vorwort sagt „basiert auf den öffentlich verfügbaren Dokumenten" — das kann Original oder Nachbau heißen. Entscheidend für den Skalenwiderspruch. |
| **`Voraussetzungen_Prozessautomatisierung.md`, Leitfaden 2.0** | Im Drive nicht auffindbar (Suche über Titel). Bestätigt den Kommentar an #161. |
| **Güte-Flags `belegt/geschaetzt/geraten`** | Existieren im Datenbestand nicht. `gate_pruefpunkt_werte` leer (#159), Snapshot kennt nur `baseline`/`manuell`. Offen, ob sie noch entstehen (#166). |
| **Relevanzgewichtung ≠ 100 %** | Rechenformel für Gewichte ≠ 100 % nicht verifizierbar — in allen NoroAI-Mappen stehen 100 %. Dass Relevanz 0 eine Dimension ausblendet, ist belegt; die genaue Formel nicht. |

---

## Kurzfassung für das Rechenmodell

1. **Reifegrad nicht in Nutzen umrechnen.** Er ist die Machbarkeitsachse (Bitkom wie BC0). Nutzen
   entsteht aus Menge × Zeit × Kostensatz × Automatisierungsgrad.
2. **Wenn doch ein Erfüllungsgrad gebraucht wird:** je Item das Band nachschlagen, dann die Bänder
   mitteln — nie den aggregierten Reifegrad linear strecken. Ergebnis immer als Intervall.
3. **Leitkennzahl Amortisationsdauer, nicht Kapitalwert.** Der Kapitalwert diskontiert eine
   erfundene Investitionshöhe und täuscht Präzision vor. Bitkom selbst nennt sein Modul eine
   „niedrigschwellige Vorstufe", die „keine vollständige betriebswirtschaftliche
   Amortisationsrechnung" leistet.
4. **Nutzwertanalyse ungewichtet** wie bei Bitkom — oder gewichtet als ausgewiesene Erweiterung.
   Muss-Kriterien als K.-o.-Filter. Bewertungsobjekt umzudeuten (Lösung → Potenzial) ist zulässig,
   aber zu kennzeichnen.
5. **Bandbreiten:** aus der Skala, wo sie die Skala hergibt; aus `confidence_pct`, wo BC1 liefert;
   sonst drei Szenarien. Abnahmekriterium ist die **Stabilität der Rangfolge**, nicht die Breite.
6. **Rangfolge nach absoluter Einsparung**, nicht nach Prozent-ROI; gemeinsame Investitionen nicht
   mehrfach zählen.

Alle sechs Punkte sind deterministisch in Python rechenbar. Kein Schritt braucht ein LLM.
