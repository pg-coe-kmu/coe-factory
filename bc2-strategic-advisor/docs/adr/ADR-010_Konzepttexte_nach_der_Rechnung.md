# ADR-010 · BC2 — Konzepttexte entstehen nach der Rechnung: der Ausarbeitungsschritt

**Status:** Angenommen · 09.10.2026
**Bezug:** [#301](https://github.com/pg-coe-kmu/coe-factory/issues/301) · Karte [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158)
**Baut auf:** ADR-006 · BC2 (Rechenverbot, Urteilsstellen, 6.7 Median aus drei) · ADR-007 · BC2 (Übergabe des Laufs) · ADR-009 · BC2 §2.7 (Kette erst ab Vertrag 3.1) · #194 (ein Aufruf je Paket, Rechenverbot)
**Nummer:** Die Vergabe läuft über Bounded Contexts hinweg ([#220](https://github.com/pg-coe-kmu/coe-factory/issues/220)).
Deshalb durchgängig **ADR-010 · BC2** schreiben.

---

## 1. Kontext

Der echte Weg (`laeufe.PaketLaufquelle`: Paket → Erkennung → Bewertung → Rechenkern) lieferte je
Potenzial nur die **gerechnete Hälfte** (`modell.ausgabe.als_konzept_potenzial`). Was
`konzept.schema.json` darüber hinaus verlangt, schrieb niemand:

- **je Potenzial:** `beschreibung`, `to_be_vision`, `user_story`, `akzeptanzkriterien_geschaeftlich`,
  `fachliche_anforderungen`, `betroffene_prozessschritte`, `betroffene_systeme`,
  `potenzielle_loesung`, `voraussetzungen`, `querschnitte`;
- **je Konzept:** `kontext.prozess_kurzbeschreibung`, `kontext.hauptschmerzpunkte`,
  `gesamtempfehlung`, `eingangswerte`, `gelesen_am`;
- **je Lauf:** `priorisierung.ausgangslage`, die aus den `hauptschmerzpunkte` entsteht.

Damit legte der echte Weg einen Vertrag ab, der nicht schemagültig war. Er konnte nichts an BC3
liefern, und weil die Kette über Pakete Vertrag 3.1 und damit die Ausgangslage braucht
(ADR-009 · BC2 §2.7), hielt jeder Lauf mit Vorgänger-Kandidaten an.

Die Erkennung lieferte schon Material (`ausgangslage`, `schmerzpunkte`, `loesungsansatz` je
Potenzial), die Bewertung Begründungssätze — aber keinen Text in Vertragsform.

## 2. Entscheidung

### 2.1 Ein eigener Schritt, nach dem Rechenkern

Die Texte schreibt ein **dritter Modellschritt**, der **Ausarbeitungsschritt**
(`app/ausarbeitung/`). Die Kette lautet: Erkennung → Bewertung → Rechnung → Ausarbeitung.

Verworfen:

- **Die Erkennung erweitern.** Ein Aufruf und das Material liegt dort. Aber ihre Antwort wüchse auf
  ein Vielfaches (bis zu 20 Potenziale mit je ≥ 300 Zeichen Beschreibung, dazu Vision, Story,
  Kriterien), die gemessene und entschiedene Erkennungsfrage (#194, #248) änderte sich, und ein
  Rechenverbots-Bruch in einem Text verwürfe den ganzen **Schnitt**.
- **Die Bewertung erweitern.** Sie läuft dreimal und nimmt je Feld den Median (ADR-006 · BC2, 6.7).
  Texte haben keinen Median: man schriebe dreimal und würfe zwei Fassungen weg.

Der Grund für die Lage **hinter** dem Rechenkern: die Texte sind Darstellung, kein Urteil, das
rechnet. Sie kennen Rang und Prioritätsgruppe — die Gesamtempfehlung muss die Reihenfolge begründen
können —, bewegen sie aber nicht. Ein Neulauf schreibt andere Sätze, verschiebt keinen Rang; die
Stabilitätsabnahme aus #299 bleibt damit gültig.

### 2.2 Ein Aufruf je Konzept, parallel

Das Konzept ist die Einheit, in der die Texte stehen; `kontext`, `hauptschmerzpunkte` und
`gesamtempfehlung` hängen ohnehin am Konzept. Die Ausgabe bleibt begrenzt, auch wenn ein Paket
viele Kernprozesse trägt, und ein Wächterbruch wiederholt nur ein Konzept. Damit ein Aufruf
Abhängigkeiten **über** Kernprozesse hinweg nennen kann, bekommt er eine knappe Liste der übrigen
Potenziale des Laufs (Nummer, Titel, Kernprozess, Lösungsklasse).

Die optionale **Kernaussage** der Ausgangslage entfällt vorerst: ein eigener Aufruf für einen Satz
lohnt nicht, und die Präsentation kommt ohne sie aus.

### 2.3 Was maschinell entsteht und was Urteil ist

| Feld | Herkunft |
|---|---|
| `betroffene_teilprozess_ids`, `eingangswerte`, `gelesen_am`, `ausgangslage.unternehmen`, `gesamtempfehlung.reihenfolge_potenzial_ids` (Potenzialrang im Konzept), `querschnitte.reifegrad` (Mittel der Bitkom-Stufen der berührten Teilprozesse) | maschinell |
| `betroffene_prozessschritte` | maschinell: die Namen der berührten **Teilprozesse** (siehe 2.7) |
| `querschnitte.abhaengigkeiten` | geurteilt (Ziel und Grund), von Python mit UUID und Titel ausgeschrieben |
| `betroffene_systeme` | geurteilt, maschinell geprüft (2.5) |
| `kontext.hauptschmerzpunkte` | geurteilt — die Erkennung liefert Schmerzpunkte als Sätze, das Schema verlangt dazu eine `auswirkung`. `als_ausgangslage` führt sie danach wörtlich zusammen |
| `beschreibung`, `to_be_vision`, `user_story`, Akzeptanzkriterien, `fachliche_anforderungen`, `potenzielle_loesung` (`ansatz` ausgehend vom Lösungsansatz der Erkennung), `voraussetzungen`, `risiken`, `zukunftssicherheit`, `prozess_kurzbeschreibung`, `gesamtempfehlung.begruendung` | geurteilt |
| `querschnitte.umsatzpotenzial` | weggelassen — ohne Rollenachse (#172) nicht belastbar |

### 2.4 Das Rechenverbot gilt — mit zwei Platzhaltern

Ein Akzeptanzkriterium will eine Zielgröße. Genau die wäre die Zahl mit Einheit, die der Wächter
verwirft, und sie stünde neben dem gerechneten Automatisierungsgrad und könnte ihm widersprechen.
Darum schreibt das Modell **`{grad_min}`** und **`{grad_max}`**, und Python setzt den gerechneten
Grad des Potenzials ein (`65`, `67,5`). Mehr Platzhalter gibt es nicht: Euro und Stunden gehören in
`value`, und „spart so und so viel im Jahr“ ist kein Abnahmekriterium. Wo ein Kriterium keine
gerechnete Entsprechung hat (etwa Compliance), nennt es Messgröße und Richtung, keinen Zielwert.

Platzhalter sind nur in den Texten eines Potenzials erlaubt. Im Kontext und in der
Gesamtempfehlung gibt es keinen Grad, den Python einsetzen könnte — dort ist auch ein erlaubter
Platzhalter ein Verstoß. Jede freie Zahl mit Einheit verwirft den Aufruf wie bisher.

Verworfen: Zahlen frei im Akzeptanzkriterium zulassen. Das bräche die Regel, die nach #194 zwei
von 21 Aufrufen gekostet hat, und erzeugte Zielwerte, die niemand nachrechnen kann.

### 2.5 Der Wächter

Formal, nicht fachlich: jedes Potenzial genau einmal, Pflichtfelder und Mindestlängen des
Vertrags, Story in SOPHIST-Form („Als … möchte ich …, damit …“), Kriterien in Given/When/Then,
Aufzählungen (`rolle`, `integration`, Risikostufen) wörtlich, Abhängigkeiten nur auf Potenziale
des Laufs und nicht auf sich selbst, und das Rechenverbot aus 2.4.

**Ein genanntes System muss im Bestand stehen** — in `werkzeuge`, `schnittstellen`, `api`,
`medienbrueche` oder `ablauf` der berührten Teilprozesse, und nennen die keines, des ganzen
Kernprozesses. **Der Tech-Stack des Mandanten zählt mit**: ein Zielsystem darf eines sein, das der
Mandant schon führt, auch wenn der Prozess es heute nicht berührt. Verglichen wird ohne Leer-,
Binde- und Satzzeichen. Nennt der Bestand gar kein System, wird nicht geprüft; sonst hinge der
Lauf an einer Datenlücke fest, die das Modell nicht schließen kann.

*Zwei Erweiterungen gegenüber dem Gespräch in #301, das nur Werkzeuge und Schnittstellen der
berührten Teilprozesse nannte, beide beim Bau gefunden:* (1) **Tech-Stack** — das Schema verlangt
mindestens ein System, und ein Zielsystem wie `n8n` wäre sonst nie nennbar. (2) **Ablauf** — die
erste echte Messung (09.10.2026) verwarf für KP-05 „Google Drive“. KP-05 führt keine
Werkzeugangaben; das Quellsystem steht nur im Ablauf („durchsuchen Google-Drive-Ordner“). Der
Wächter trieb das Modell damit vom tatsächlichen System weg auf eines aus dem Tech-Stack — die
Prüfung erzeugte genau den Fehler, den sie verhindern soll.

### 2.6 Bricht auch die Wiederholung, hält der Lauf an

Wie bei Erkennung und Bewertung: eine Wiederholung mit benannter Mahnung, dann `LaufAngehalten`.
Ein Lauf ohne Texte ist kein lieferbarer Lauf. Die Alternative — ablegen mit „Texte fehlen“ und
später nur die Texte nachschreiben — bräuchte einen dritten Laufzustand in Schema `bc2` für einen
Fall, den es noch nie gab. Wird das Nachrechnen teuer (jeder Neuversuch kostet Erkennung und drei
Bewertungsurteile), kommt sie als eigenes Ticket.

### 2.7 Gate 1 zeigt die Texte, ändert sie nicht

Die Detail-Schublade zeigt Story, Kriterien, Beschreibung, Vision, Lösung, Systeme, Risiken und
Querschnitte. Bearbeiten lassen sie sich nicht: ein bearbeitetes Konzept stammte nicht mehr allein
vom Modell und bräuchte eine eigene Herkunftsangabe am Text. Sind die Texte falsch, wird der Lauf
mit Begründung abgelehnt und neu gerechnet.

### 2.8 Woher der Tech-Stack kommt

Nicht aus `company_profile.tech_stack` — die Spalte trägt bei NoroAI und beim Übungsmandanten nur
„27 Tools“, eine Zählung (gemessen an der laufenden Datenbank am 09.10.2026). Der Stack steht in
`company_profile.profile_json.profil` unter „6. Tech-Stack & IT-Architektur intern“, als Markdown mit
Unterabschnitten. Gelesen wird der Abschnitt, erkannt am **Titel** (Kapitelnummern wandern mit den
Fassungen des Profils), und davon nur der Unterabschnitt „Tech-Stack“, sofern es ihn gibt — der
übrige Abschnitt trägt Cybersicherheit und SSO samt Personennamen, die eine Werkzeugempfehlung nicht
braucht.

## 3. Folgen

- Der echte Weg legt einen **schemagültigen Vertrag 3.1** ab, und die Kette über Pakete ist im
  echten Weg nicht mehr gesperrt.
- Ein Lauf kostet einen Erkennungsaufruf, drei Bewertungsaufrufe und **je Konzept einen**
  Ausarbeitungsaufruf. Die Ausarbeitung läuft parallel; ihre Dauer ist die des längsten Konzepts.
- Das Glossar kennt den **Ausarbeitungsschritt**. Das Vertragsfeld `betroffene_prozessschritte`
  bleibt — der Vertrag bricht nicht für ein Wort —, ist aber als „Namen der berührten Teilprozesse“
  vermerkt, im Glossar und in der Schemabeschreibung.
- Ob ein Modell die Texte in brauchbarer Güte schreibt, zeigt nur ein echter Lauf; gemessen wird mit
  `tools/ausarbeitung_messen.py`.

## 4. Gemessen (09.10.2026, Sonnet über die CLI)

Prototyp-Paket aus BC0s Snapshot (16 Teilprozesse), Erkennung und Median aus drei Urteilen aus der
Erhebung zu #299 — 7 Potenziale in 4 Konzepten (KP-02, KP-03, KP-05, KP-06).

| Lauf | Wandzeit | Versuche | Verworfen | Schema |
|---|---|---|---|---|
| 1 | 348 s | 1 / 1 / **2** / 1 | KP-05: „Google Drive“ nicht im Bestand | 4 Konzepte, 0 Verstöße |
| 2 (nach 2.5, Ablauf zählt mit) | 319 s | 1 / 1 / 1 / 1 | — | 4 Konzepte, 0 Verstöße |

Das Rechenverbot hielt in allen neun Aufrufen; jeder Aufruf benutzte die Platzhalter, und Python
setzte den gerechneten Grad ein. Ein Aufruf dauert 2½ bis 6 Minuten, das größte Konzept (KP-02, drei
Potenziale) am längsten. Offen bleibt, dass die Systemprüfung **großzügig** ist: „Mail“ oder
„Formular“ bestehen, sobald das Wort im Ablauf steht — sie verhindert erfundene Systeme, nicht
unscharfe.
