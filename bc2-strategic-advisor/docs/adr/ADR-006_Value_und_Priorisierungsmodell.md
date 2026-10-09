# ADR-006 · BC2 — Das Value- und Priorisierungsmodell

**Status:** Angenommen · 20.09.2026 — mit drei Nachträgen aus dem Bau (§5), drei aus dem
Bewertungsschritt (09.10.2026, [#260](https://github.com/pg-coe-kmu/coe-factory/issues/260), §6) und
einem aus seinem Bau (09.10.2026, [#288](https://github.com/pg-coe-kmu/coe-factory/issues/288), §6.6)
**Bezug:** [#166](https://github.com/pg-coe-kmu/coe-factory/issues/166) · Bau [#238](https://github.com/pg-coe-kmu/coe-factory/issues/238) · Karte [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158)
**Baut auf:** ADR-005 · BC2 (der Analyselauf ist das Paket) · ADR-003 (Schreibmodell) · ADR-002 (stabile IDs)
**Nummer:** Die Vergabe läuft über Bounded Contexts hinweg und ist seit [#220](https://github.com/pg-coe-kmu/coe-factory/issues/220)
als kollisionsanfällig bekannt. Deshalb durchgängig **ADR-006 · BC2** schreiben, nie „ADR-006" allein.

---

## 1. Kontext

Am 30.08.2026 hat die Karte die **Richtung** des Value-Modells festgelegt: Bandbreiten statt
Punktwerten, Nutzwertanalyse für das Nicht-Monetäre. Beide Begründungen haben sich danach als
brüchig erwiesen ([#161](https://github.com/pg-coe-kmu/coe-factory/issues/161)): die Güte-Flags,
auf denen die Bandbreiten aufsetzen sollten, existieren im Bestand nicht, und Bitkoms
Nutzwertanalyse ist für IT-Lösungen gedacht, ohne Gewichtung, nicht für Potenziale. Die
Entscheidung blieb, ihre Herleitung war neu zu treffen.

Der Stand, von dem dieses ADR ausgeht, ist damit: **die Rechenstruktur existierte, die Herkunft
ihrer Faktoren nicht.** Die Übergangslieferung vom 30.08.2026 rechnete ein vollständiges Modell mit
frei gesetzten Zahlen — 45/50/60 % Ersparnis, 544 €/PT Investition — und sagte das auch in jeder
Annahme dazu.

Inzwischen ist die Datenlage eine andere:

- **BC1 liefert Frequenz und Dauer** vertraglich gebunden ([#184](https://github.com/pg-coe-kmu/coe-factory/issues/184)).
- **Der Kostenansatz steht:** Mischsatz 43 €/h ([#172](https://github.com/pg-coe-kmu/coe-factory/issues/172)).
- **Die Bitkom-Skala steht:** Checkliste, nicht Leitfaden ([#171](https://github.com/pg-coe-kmu/coe-factory/issues/171)).
- **Die Rechnung ist ein Vorschlag**, den der Mensch am Gate 1 überschreiben darf (30.08.2026).

Offen war, wie aus diesen Eingängen eine Zahl wird.

---

## 2. Entscheidung

### 2.0 Grundsatz

**Rechnen tut Python, nicht das LLM.** Das LLM urteilt an genau vier Stellen — Lösungsansatz-Klasse,
Lage im Korridor, die fünf Nutzwert-Kategorien und das begründete Überschreiben der
Umsetzungskomplexität. Alles Übrige ist deterministisch. **Jede Setzung reist mit dem Ergebnis mit.**

**Nachtrag 7 (#288): es sind fünf.** Der Umsetzungsaufwand in Personentagen
(`aufwand_schaetzung_pt`) ist die fünfte Urteilsstelle — begründet in §6.6.

### 2.1 Value — die monetäre Seite

```
Jahresstunden  = frequency_per_year × total_duration_minutes / 60
Ist-Kosten     = Jahresstunden × 43 €/h
Einsparung     = Ist-Kosten × Automatisierungsgrad
Investition    = aufwand_schaetzung_pt × 800 €/PT
Amortisation   = Investition / (Einsparung / 12)
```

**`executions_per_run` ist kein Faktor** (Invariante I2 des BC1-Vertrags). Wer ihn multipliziert,
erhält für die Reisebuchung das Dreifache der Gesamtkapazität des Mandanten.

**Nachtrag 4 (#260): die Jahresstunden sind die der berührten Schritte, nicht die des ganzen
Prozesses.** Die erste Zeile oben ist damit ersetzt durch

```
Jahresstunden  = Σ über die berührten Teilprozesse:
                 (step_frequency_per_year ?? frequency_per_year) × focus_step_duration_minutes / 60
```

`frequency_per_year × total_duration_minutes` beschreibt laut BC1-Vertrag (I1) den **ganzen
Prozess, wie ihn der Befragte gerahmt hat** — gespeichert auf der Zeile des Fokus-Schritts, und
zwei Profile desselben Kernprozesses widersprechen sich darin (KP-06: 40 × 120 min in TP-1,
180 × 180 min in TP-2). Ein Potenzial, das einen Schritt berührt, beanspruchte damit die Dauer des
ganzen Prozesses; eines über zwei Teilprozesse hätte zwei widersprüchliche Ganz-Prozess-Zahlen, und
summiert zählten sie doppelt. Eine Lösung nimmt die Arbeit eines **Schritts** ab. Je Schritt
summiert zählt nichts doppelt, weil die Teilprozesse verschiedene Schritte sind. `step_frequency_per_year`
hat Vorrang, wo gesetzt (I8).

- **Herkunft** ist die **schwächste** der berührten Teilprozesse (`geschaetzt` vor `aus_system` vor
  `gemessen`); einmal `geschaetzt` macht die Breite ±40 %. Die Eingangswerte reisen **je
  Teilprozess** mit.
- **Fehlt einem berührten Teilprozess das Profil oder eine der beiden Größen, gibt es keine
  Value-Zahl** — wie bei `NULL` in 2.3, der Nutzwert trägt den Impact allein (Nachtrag 2), und ein
  Hinweis nennt die fehlenden Teilprozesse. Eine Teilsumme sähe vollständig aus und läge
  systematisch zu niedrig: der Schluss vom Artefakt auf die Absicht, diesmal mit Zahlen.

**Zwei verschiedene Sätze, mit Absicht.** Die Einsparungsseite rechnet mit dem Mischsatz von
43 €/h (341 €/PT) — das ist die Arbeitszeit des Mandanten. Die Investitionsseite rechnet mit einem
**Bausatz von 800 €/PT**, weil der Bau beim CoE anfällt und zu Marktkonditionen stattfindet, nicht
zu NoroAIs Selbstkostensatz. Derselbe Satz auf beiden Seiten würde sich in der Amortisation
herauskürzen und sie damit **systematisch zu günstig** ausweisen. Der Bausatz ist eine **Setzung**
und wird als solche ausgewiesen.

**Die Amortisation ist reiner Ausweis.** Sie wirkt nicht auf die Rangfolge. Eine Schranke — etwa
„jenseits von 36 Monaten in die letzte Gruppe" — wäre eine zweite, versteckte Schwelle neben dem
Score und träfe bei NoroAI gerade die Potenziale mit dem belegtesten Nutzen (KP-03, Compliance,
rechnerisch über 50 Monate). Sie gehört sichtbar ins Konzept und soll über den Menschen wirken,
nicht über die Formel.

### 2.2 Der Automatisierungsgrad

Der größte Hebel des Modells, und er wird von niemandem geliefert. BC2 setzt ihn über einen
**Korridor je Lösungsansatz-Klasse**; das LLM verortet das Potenzial darin und begründet die Lage.

| Klasse | Korridor | Was sie kennzeichnet |
|---|---|---|
| Regelwerk / Weiterleitung | 70–90 % | deterministische Entscheidung, keine Textdeutung |
| Integration | 60–85 % | zwei Systeme verbinden, Medienbruch schließen |
| Extraktion | 50–75 % | aus Dokument oder Mail strukturierte Daten ziehen |
| Textgenerierung | 30–50 % | Entwurf, den ein Mensch abnimmt |
| Assistenz | 10–30 % | Vorschlag, Mensch entscheidet jeden Fall |

Der Grad geht **nie als Punktwert** ins Ergebnis, sondern immer als Spanne.

**BC1s `automation_potential_estimate_pct` hat keinen Vorrang** — nicht aus Autoritätsgründen,
sondern wegen der **Körnung**: das Feld hängt am Fokus-Schritt, der Automatisierungsgrad gehört zum
Lösungsansatz. Ein Teilprozess kann nach dem Trenntest mehrere Potenziale mit verschiedenen Lösungen
tragen; das Feld könnte für alle nur eine Zahl liefern. Es beantwortet zudem eine andere Frage
(„wie automatisierbar hält der Prozessverantwortliche das") als BC2 stellt („wie viel nimmt *diese*
Lösung ab"). Ist es gefüllt, liest BC2 es als **Plausibilitätsprobe** und hängt bei großer Abweichung
einen Hinweis ans Potenzial — eine Abweichung ist das Signal, an dem ein falsch gesetzter Korridor
auffällt.

Das Feld wird bei BC1 **nicht nachgefordert**: es würde BC1s Etappe 1 aufhalten, und der Korridor trägt.

### 2.3 Bandbreiten

**Breite je Herkunft der Dauer** (`focus_step_duration_source`):

| Herkunft | Breite |
|---|---|
| `gemessen` | ± 10 % |
| `aus_system` | ± 15 % |
| `geschaetzt` | ± 40 % |
| `NULL` | **keine Value-Zahl** |

Der große Abstand nach oben ist Absicht: das einzige echte Beispiel trägt `geschaetzt` bei 60 %
Konfidenz und stammt aus einer Use-Case-Definition, nicht aus einer Erhebung. Bei `NULL` wird
**gar keine** Zahl ausgewiesen statt einer sehr breiten — eine Spanne von ±100 % ist keine Aussage
mehr; BC2 rechnet dann qualitativ weiter und vermerkt die Lücke.

**`focus_step_duration_confidence_pct` verfeinert die Breite nicht.** Die Konfidenzzahl ist selbst
geschätzt; aus einer geschätzten Prozentzahl eine feinere Bandbreite zu rechnen erfände die
Genauigkeit, die die Bandbreite gerade eingestehen soll. Sie wird als Herkunftsangabe mitgeführt.

**Zusammensetzung: Eckenrechnung.** Unteres Ende der Dauer × unteres Ende des Korridors, oberes ×
oberes. Sie ist in zwei Zeilen nachvollziehbar und für einen Prüfer im Konzept nachrechenbar. Sie
ist **bewusst pessimistisch** — sie unterstellt, dass beide Fehler gleichsinnig auftreten; das
gehört als Annahme ins Ergebnis. Monte-Carlo wurde verworfen: es verlangt Verteilungsannahmen, die
niemand erhoben hat.

**Plausibilitätsschranke** (I3): Übersteigen die Jahresminuten die Kapazität des Mandanten —
880 PT / 7.040 h intern als Warnschwelle, 2.200 PT / 17.600 h brutto als harte Grenze — hängt BC2
einen Hinweis an und weist nichts zurück. Die Prüfung ist formal, nicht fachlich.

### 2.4 Nutzwert — die nicht-monetäre Seite

Fünf Kategorien, je **1–10**, vom LLM geurteilt mit je einem Begründungssatz, **ungewichtetes
Mittel**:

1. Qualität
2. Durchlaufzeit
3. Fehlerreduktion
4. Mitarbeiterzufriedenheit
5. **Compliance / Rechtssicherheit**

Die fünfte ist gegenüber dem Glossarstand ergänzt: sie ist bei NoroAI der eigentliche Grund für
KP-03 (AVV/DSGVO), und unter „Qualität" verschwindet sie — ohne sie fiele das Potenzial durch,
dessen Nutzen am besten belegt ist.

**Ungewichtet** aus demselben Grund, aus dem Bitkom es ist: eine Gewichtung wäre reine Setzung und
ließe sich gegenüber einem Prüfer nicht begründen.

**Nachtrag 6 (#260): der Nutzwert trägt keine Spanne — aber feste Anker.** Er ist ein Urteil auf
einer Ordinalskala; eine Spanne darum wäre dieselbe erfundene Genauigkeit, die 2.3 bei
`confidence_pct` verwirft. Es reisen die Herkunft `geurteilt` und ein Begründungssatz je Kategorie;
dass ein Impact ganz geurteilt ist, zeigt schon `impact_monetaer: null`. Damit die Skala **absolut**
ist und nicht nur so heißt, setzt BC2 je Kategorie **Anker für 1, 4, 7 und 10** — eine Setzung
neben Korridoren und Euro-Schwellen in `app/modell/parameter.py`, offengelegt und am ersten echten
Lauf mitzuprüfen.

**Nicht aus den Bitkom-Bewertungen abgeleitet.** Die hängen am **Teilprozess**, der Nutzwert gehört
zum **Potenzial**, und ein Teilprozess trägt mehrere Potenziale. Eine Ableitung gäbe allen
Potenzialen eines Teilprozesses denselben Nutzwert und ebnete genau die Unterscheidung ein, für die
die Größe da ist.

### 2.5 Impact — die Zusammenführung

```
impact = round( (impact_monetaer + nutzwert) / 2 )
```

Beide Teil-Scores werden **mitgeführt**, nicht nur ihr Mittel.

`impact_monetaer` entsteht aus **absoluten Euro-Schwellen**, logarithmisch zwischen 1.000 €/Jahr
(Score 1) und 50.000 €/Jahr (Score 10), darunter und darüber gekappt:

```
impact_monetaer = clamp(1, 10, round(1 + 9 × (log₁₀(E) − 3) / (log₁₀(50000) − 3)))
```

**Absolut, nicht relativ zum Lauf.** Bei relativer Normierung änderte sich der Impact eines
Potenzials, sobald ein anderes Paket geschnitten wird — und das Konzept geht je Kernprozess an BC3:
derselbe Prozess bekäme in zwei Lieferungen verschiedene Zahlen, ohne dass sich an ihm etwas
geändert hätte.

**Gleichgewichtet**, weil keine Seite den Vorrang beanspruchen kann: bei NoroAI trägt die
Monetärrechnung für die Mehrzahl der Potenziale nicht (Amortisation über 50 bzw. 27 Monate,
[#168](https://github.com/pg-coe-kmu/coe-factory/issues/168)), dort ist der Nutzwert der tragende
Teil. Den Nutzwert auf eine Korrektur von ±2 zu beschränken würde die Rangfolge verzerren.

**Die Schwellen sind vorläufig und am ersten echten Lauf zu kalibrieren.** Die einzige echte
BC1-Zeile ergibt für KP-06.TP-2 bereits 540 h/Jahr, also 23.220 € Ist-Kosten — eine Größenordnung
über den Annahmen der Übergangslieferung. Die Obergrenze muss unter NoroAIs Gesamtpersonalkosten
bleiben (7.040 h × 43 €/h = 302.720 €/Jahr); eine Skala, deren Spitze darüber liegt, könnte nie
erreicht werden.

**Nachtrag 1 (#238): welcher Punkt der Einsparungsspanne in `E` eingesetzt wird.** Die Einsparung
ist eine **Spanne**, die Formel braucht eine Zahl — dieses ADR ließ offen, welche. Eingesetzt wird
die **Mitte der Eingänge**: Dauer-Mitte × Korridor-Mitte, also
`stunden_zentral × 43 €/h × (korridor_min + korridor_max) / 2`.

Nicht die Mitte der *Spanne*: `(lo·lo + hi·hi) / 2` liegt systematisch **über** der zentralen
Schätzung, weil die Eckenrechnung beide Fehler gleichsinnig multipliziert — sie erbt den
Pessimismus als Überhöhung. Und nicht das untere Ende: das zählt die Pessimismus-Annahme ein
zweites Mal und drückte an einem Satz von elf Potenzialen **4 von 10** auf den Bodenwert 1, womit
der monetäre Teil-Score seine Trennschärfe verlöre — in einem Modell, dessen Problem ohnehin
mangelnde Trennschärfe ist (siehe §5).

**Nachtrag 2 (#238): was aus `impact` wird, wenn es keine Value-Zahl gibt.** Der **Nutzwert trägt
den Impact allein** (`impact = round(nutzwert)`), und `impact_monetaer` wird `null`.

`impact_monetaer = 1` wäre die Alternative gewesen und behandelte eine **fehlende Messung** wie
eine gemessene Wertlosigkeit — der Schluss vom Artefakt auf die Absicht, den die Karte dreimal als
Fehler verzeichnet ([#163](https://github.com/pg-coe-kmu/coe-factory/issues/163),
[#186](https://github.com/pg-coe-kmu/coe-factory/issues/186),
[#165](https://github.com/pg-coe-kmu/coe-factory/issues/165)). Er ist hier derselbe: BC1s
Erhebungsstand sagt nichts über den Wert des Prozesses. Dieses ADR hat den analogen Fall in 2.3
bereits so entschieden — bei `NULL` gar keine Zahl statt einer erfundenen —, und die Regel gilt
für den Teil-Score genauso.

**Der Preis ist benannt:** ein rein geurteiltes Potenzial kann ein gemessenes überholen, weil der
Nutzwert dann die einzige Eingabe ist. Sichtbar bleibt es über `impact_monetaer: null` im Vertrag;
am Gate 1 entscheidet ohnehin der Mensch, und überschreiben kann er nur, was er sieht. Eine
Deckelung geurteilter Potenziale (»nie PRIO 1«) wurde verworfen: das wäre eine zweite versteckte
Schwelle neben dem Score — genau das, was 2.1 für die Amortisation ausdrücklich ablehnt.

### 2.6 Umsetzungskomplexität — gemessen, nicht geurteilt

```
reife         = Mittel( documentation_status, standardization_level,
                        data_availability_score, stability_score )     # je 1–5
komplexitaet  = round(11 − 2 × reife)                                  # Bereich 1–9
```

Das LLM darf den Wert **begründet überschreiben**; BC0s sechs Kriterien aus
`v_prozessautomatisierung` (Technologiebasis, Tools, Systemintegration, Prozessbeschreibung,
Ausführung, Compliance) sind dafür das Begründungsmaterial — **kein zweiter Rechenterm**. Zehn
Zahlen aus zwei verschiedenen Körnungen zu mitteln erzeugte Scheingenauigkeit: BC1s vier hängen am
Fokus-Schritt, BC0s sechs am Teilprozess, und ein Potenzial kann mehrere Teilprozesse berühren.

**Fehlen die vier Skalen** — der Vertrag sagt sie bei `status='fertig'` zu, die Datenbank erzwingt
es nicht —, urteilt das LLM allein, und die Herkunft wird als `geurteilt` statt `gemessen`
mitgeführt. Der Lauf bleibt vollständig.

**Bekannter Schönheitsfehler:** die Formel erreicht die 10 nie, der Wertebereich ist 1–9. Jede
Streckung wäre willkürlicher als die Lücke.

**Nachtrag 5 (#260): mehrere Teilprozesse — das Maximum.** Die vier Skalen hängen am Fokus-Schritt,
also je Teilprozess; ein Potenzial braucht eine Komplexität. Gerechnet wird sie **je berührtem
Teilprozess** nach der Formel oben, und es gilt die **höchste**: der am schwersten umsetzbare Teil
bestimmt den Aufwand, ein Mittel glättete ihn weg. **Fehlen einem berührten Teilprozess die Skalen,
ist die Komplexität nicht gemessen** — das LLM urteilt (Herkunft `geurteilt`), die vorhandenen
Skalen sind Begründungsmaterial wie BC0s sechs Kriterien. Ein Maximum über eine Teilmenge wäre ein
Urteil, das sich als Messung ausgibt. Der Preis ist bekannt: die Komplexität deckelt den Score
ohnehin (§5.2), das Maximum verschärft das. Das gehört in die Kalibrierung, nicht in die Formel.

### 2.7 Score, Kategorie, Gruppe, Rang

```
score = impact × (11 − komplexitaet)        # 1 … 100
```

**Kategorie** — Etikett im Quadranten, sagt nichts über die Reihenfolge, darf mehrfach vorkommen:

| | Komplexität ≤ 5 | Komplexität ≥ 6 |
|---|---|---|
| **Impact ≥ 6** | Quick Win | Strategisch |
| **Impact ≤ 5** | Optional | Zurückgestellt |

Die vierte Ecke heißt **„Zurückgestellt"**, nicht „Long Bet": eine Wette verspricht einen Gewinn,
den die Zahlen dort gerade nicht zeigen.

**Prioritätsgruppe** — Score-Bänder, ebenfalls am ersten Lauf zu prüfen:

| Gruppe | Score |
|---|---|
| PRIO 1 — jetzt | ≥ 50 |
| PRIO 2 — danach | 20 – 49 |
| PRIO 3 — optional | < 20 |

**Nachtrag 3 (#238): die Bänder sind ein Parameter, kein Wert im Code.** Sie stehen samt den
Euro-Schwellen in `app/modell/parameter.py` und werden am ersten echten Lauf
([#206](https://github.com/pg-coe-kmu/coe-factory/issues/206), KW 40) mit
`tools/kalibrierung.py` festgezurrt. Die Werte oben bleiben bis dahin die Voreinstellung — sie
jetzt zu verschieben hieße, auf **erfundenen** Zahlen zu kalibrieren; der einzige vollständige
Satz, der vorliegt, sind die elf Wegwerf-Potenziale des Prototyps aus
[#167](https://github.com/pg-coe-kmu/coe-factory/issues/167). Was sie belegen, ist der
Kalibrierungs**bedarf**, nicht eine neue Grenze. Der Befund selbst steht in §5.

**Nicht nach Kategorie gruppiert.** Kategoriegruppen wären im Rang nicht zusammenhängend: ein
Strategisches mit Impact 10 und Komplexität 6 erreicht Score 50, ein Quick Win mit Impact 6 und
Komplexität 5 nur 36 — ein PRIO-2-Potenzial stünde über einem PRIO-1-Potenzial. Score-Bänder sind
zusammenhängend und über Läufe hinweg vergleichbar, anders als feste Anteile, bei denen dieselbe
Zahl je nach Paketgröße in verschiedenen Gruppen landet.

**Potenzialrang:** strikt nach Score über den ganzen Analyselauf.
**Prozessrang:** der Rang seines **besten** Potenzials. Die Frage lautet „welchen Prozess fasse ich
zuerst an", und angefangen wird mit dem, was sich zuerst lohnt. Eine Summe bevorzugte Prozesse mit
vielen kleinen Potenzialen, ein Mittel bestrafte einen Prozess dafür, dass er neben seinem Quick Win
noch schwierige Potenziale hat.

### 2.8 Was bewusst **nicht** in die Rechnung eingeht

| Größe | Behandlung | Grund |
|---|---|---|
| **Reifegrad** | Querschnitt | Er rangiert, aber er **trennt nicht** — die Intervalle von KP-02/03/04 überlappen fast vollständig (#161). BC0 empfiehlt, aus einer Stufe keinen Prozentwert zurückzurechnen. Die Merkregel „Sprung 3→4 ist der größte" ist mit #171 gefallen. |
| **Schwelle 3,5** | entfällt | Gate 0 filtert bereits, BC2 bekommt nur Freigegebenes. Eine zweite Schwelle aus einer Projektsetzung wiese einen Prozess ab, den ein Mensch gerade freigegeben hat. |
| **Zukunftssicherheit** | Querschnitt | Entschieden am 30.08.2026. |
| **Umsatzpotenzial** | Querschnitt | Es ist monetär und **keine Einsparung** — das Modell kann es bis heute nicht ausdrücken. Um es zu rechnen, müsste BC2 wissen, *wessen* Zeit frei wird; die Rollenachse wird nach #172 nicht erhoben, und aus `focus_step_roles` eine `rolle_id` abzuleiten verbietet der BC1-Vertrag. Eine Schätzung wäre eine Setzung auf eine Setzung, ohne belegbaren Korridor. |
| **Kostenreduktion als Nutzwert** | ausgeschlossen | Sie **ist** der `value`. Sie zusätzlich in den Nutzwert zu nehmen zählte sie über den Impact doppelt. |
| **Tools** | keine Rechengröße | Simeons Auflage vom 07.09.2026 zielt auf einen Soll-Ist-Vergleich **nach** dem Bau. Im Gruppentermin war zudem Konsens, dass der PoC die Tool-Landschaft nicht final verändern soll. Bleibt Auflage für das Rückschreiben. |

### 2.9 Reproduzierbarkeit und Nachvollziehbarkeit — zwei Dinge

**Reproduzierbarkeit:** gerechnet wird auf `stand_zum(uebergeben_am)`. Die Historisierung existiert
seit Schema v2.6 vom 04.09.2026, und die Lesegruppe hat EXECUTE darauf
([#217](https://github.com/pg-coe-kmu/coe-factory/issues/217)). Gleiches Paket, gleicher Stand,
gleiche Zahlen — ein erneuter Lauf kann keine alten oder neuen Werte einmischen.

**Nachvollziehbarkeit:** die Eingangswerte werden trotzdem ins Konzept mitgeschrieben — mit Herkunft
(Tabelle, Spalte, ID), Wert, Einheit und Lesezeitpunkt neben `uebergeben_am`. Nicht der ganze
Bestand, nur das Gerechnete. Der Grund hat sich verschoben: eine Lieferung geht als Datei an BC3 und
als Präsentation an den Mandanten, und beide müssen **ohne Datenbankzugriff** prüfbar sein. Die
ursprüngliche Begründung vom 09.09.2026 („BC2 rechnet live") ist am 10.09. weggefallen.

Ein eigener Snapshot je Lauf bleibt verworfen (dupliziert fremdes Schema, ADR-002).

---

## 3. Alternativen, die verworfen wurden

- **Automatisierungsgrad aus `v_prozessautomatisierung` ableiten.** Die sechs Kriterien messen, wie
  digital der Prozess **heute** ist, nicht wie viel eine **Lösung** abnimmt — der Schluss vom
  Artefakt auf die Absicht, den die Karte dreimal als Fehler verzeichnet.
- **Ein Satz für Einsparung und Investition.** Kürzt sich in der Amortisation heraus und macht sie
  systematisch zu günstig — genau die Größe, auf die ein Prüfer schaut.
- **Bandbreite aus `confidence_pct` rechnen.** Feinere Zahl aus einer geschätzten Zahl.
- **Monte-Carlo über die Eingänge.** Verteilungsannahmen, die niemand erhoben hat.
- **Impact relativ zum stärksten Potenzial des Laufs.** Macht dieselbe Lieferung von der
  Paketgröße abhängig.
- **Nutzwert aus den Bitkom-Dimensionen.** Falsche Körnung — ebnet Potenziale innerhalb eines
  Teilprozesses ein.
- **Alle zehn Messungen zur Komplexität mitteln.** Mischt zwei Körnungen.
- **PRIO-Gruppen nach Kategorie.** Im Rang nicht zusammenhängend.
- **Amortisationsschranke auf die Rangfolge.** Zweite versteckte Schwelle, trifft gerade die
  belegtesten Potenziale.

---

## 4. Folgen

**Gut:**

- Jede Zahl hat eine benannte Herkunft: gemessen, gesetzt oder geurteilt.
- Die Rechnung ist deterministisch und ohne LLM nachvollziehbar.
- Zwei Läufe desselben Pakets liefern dasselbe Ergebnis.
- Der Vorschlagscharakter bleibt erhalten: der Mensch am Gate 1 sieht auch, was **nicht** gerechnet
  wurde (die Querschnitte).

**Teuer:**

- **Drei Setzungen tragen das Modell** — Bausatz 800 €/PT, die fünf Korridore, die Euro-Schwellen.
  Keine davon ist erhoben. Alle drei sind offengelegt, und die letzte wird kalibriert.
- **Die Kalibrierung steht aus.** Euro-Schwellen und Score-Bänder sind gesetzt, nicht geprüft; erst
  der erste echte Lauf zeigt, ob sie trennen.
- **Der Mischsatz untertreibt bei absoluten Beträgen** (bekannt aus #172) — für die Rangfolge
  gleichwertig, für den Investitionsrahmen zu niedrig.
- **Der Wertebereich der Komplexität ist 1–9**, nicht 1–10.

**Vertragliche Folgen** (Schnitt in [#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)):
Feld für die Querschnitte (Reifegrad, Zukunftssicherheit, Umsatzpotenzial), die beiden Teil-Scores
neben dem Impact, die Herkunft der Komplexität (`gemessen` / `geurteilt`), die Prioritätsgruppe und
die Bandbreiten als Spanne statt als Punktwert.

---

## 5. Nachtrag aus dem Bau — 20.09.2026 ([#238](https://github.com/pg-coe-kmu/coe-factory/issues/238))

Drei Lücken hat erst das Bauen sichtbar gemacht; sie sind oben an Ort und Stelle als **Nachtrag 1–3**
entschieden. Hier steht der Messbefund, der dazu geführt hat — und eine Korrektur an der Diagnose,
die das Ticket selbst noch trug.

### 5.1 Die Gruppen trennen nicht

Über die elf Potenziale des Prototyps aus #167 gerechnet:

| Bandgrenzen | PRIO 1 | PRIO 2 | PRIO 3 |
|---|---|---|---|
| **≥ 50 / 20–49 / < 20** (dieses ADR) | 1 | **9** | 1 |
| ≥ 40 / 20–39 / < 20 | 1 | **9** | 1 |
| ≥ 36 / 18–35 / < 18 | 3 | 7 | 1 |
| ≥ 30 / 15–29 / < 15 | 5 | 5 | 1 |

Score-Spanne im Satz: **8 … 54**. Eine Gruppe, in der 82 % aller Potenziale liegen, sagt dem
Entscheider am Gate 1 nichts.

### 5.2 Der vermutete Hebel ist der falsche

Naheliegend wäre, die **Euro-Obergrenze** zu senken: 50.000 €/Jahr erreicht ein Mandant dieser
Größe kaum, also müsste `impact_monetaer` systematisch zu klein ausfallen. **Gemessen stimmt das
nicht.** Von 50.000 € auf 10.000 € herunter ändert sich die Verteilung über die Prioritätsgruppen
um **null** — das Runden auf ganze Score-Stufen schluckt den Unterschied.

Der Deckel sitzt bei der **Umsetzungskomplexität**. `komplexitaet = round(11 − 2 × reife)` kommt
bei realistischer Prozessreife (3,5–3,75) nicht unter 4, also ist `score = impact × (11 − k)` auf
etwa `impact × 7` gedeckelt; und der Impact kommt selten über 6, weil der Nutzwert bei ~6,6 endet.
PRIO 1 (≥ 50) verlangt damit entweder eine Prozessreife, die es bei NoroAI nicht gibt, oder eine
fünfstellige Einsparung.

**Die Formel bleibt dennoch unangetastet.** Sie jetzt zu ändern wäre eine neue Modellentscheidung
mitten im Bau, und der Befund ruht auf erfundenen Zahlen. Er gehört in die Kalibrierung am ersten
echten Lauf — mit der Warnung, dass ein Verschieben der Bänder allein das Symptom behandelt.

### 5.3 Zwei Korrekturen an der Diagnose des Tickets

- **»Zwei Prioritätsgruppen Unterschied«** bei fehlender Value-Zahl (#167, Punkt 2) **reproduziert
  sich am vollen Satz nicht.** Das betroffene Potenzial wandert von Rang 2 auf Rang 7, bleibt aber
  in beiden Lesarten PRIO 2. Der Sprung stammte aus dem engeren Einzelbeispiel. Entschieden wurde
  Nachtrag 2 darum nicht wegen seiner Größe, sondern wegen seiner Richtung.
- **Frage 1 wiegt leichter als angenommen.** Über alle drei Lesarten hinweg ist die
  Gruppenverteilung identisch; es gibt 3 Rangänderungen unter 11. Ausschlaggebend war nicht die
  Rangfolge, sondern dass das untere Ende den monetären Teil-Score auf den Bodenwert zusammendrückt.

### 5.4 Zwei Festlegungen, die der Bau erzwungen hat

- **Kaufmännisch runden, nicht zur geraden Zahl.** Dieses ADR schreibt nur »round«. Pythons
  eingebautes `round` rundet zur geraden Zahl (`round(2.5) == 2`), und bei
  `komplexitaet = round(11 − 2 × reife)` trifft das real: eine Reife von 3,25 ergibt 4,5 —
  kaufmännisch 5, bankmäßig 4, ein ganzer Score-Schritt. Weil 2.9 verlangt, dass ein Prüfer die
  Zahlen **von Hand** nachrechnen kann, und von Hand niemand zur geraden Zahl rundet, gilt
  kaufmännisches Runden.
- **Der Korridor ist Leitplanke, nicht Wert.** Der Vertrag führt `angesetzt_min_pct` /
  `angesetzt_max_pct` je Potenzial; wäre dort immer der Korridor der Klasse eingetragen, wären die
  Felder überflüssig. Das LLM setzt also eine Spanne an, und der Rechenkern prüft, dass sie
  **innerhalb** des Korridors ihrer Klasse liegt — wer ihn überschreitet, hat die Klasse falsch
  gewählt, und das soll auffallen statt stillschweigend zu gelten. Ohne Angabe gilt der volle
  Korridor.

---

## 6. Nachtrag — der Bewertungsschritt · 09.10.2026 ([#260](https://github.com/pg-coe-kmu/coe-factory/issues/260))

2.0 lässt das LLM an vier Stellen urteilen. Der Erkennungsschritt
([#248](https://github.com/pg-coe-kmu/coe-factory/issues/248)) deckt **eine** ab, die Lösungsklasse.
Die übrigen drei — Lage im Korridor, die fünf Nutzwert-Kategorien, das begründete Überschreiben
der Komplexität — urteilt ein eigener **Bewertungsschritt**. Er sieht das *geschnittene* Potenzial
und läuft deshalb nach der Erkennung, nie vorher. Die Aggregation über mehrere Teilprozesse steht
oben an Ort und Stelle (Nachtrag 4 und 5), die Unsicherheit des Nutzwerts ebenso (Nachtrag 6).

### 6.1 Ein eigener Aufruf, nicht ein Anhang an die Erkennung

Für den Anhang sprach nur, dass der Kontext schon geladen ist — entdoppelt rund 46.500 Zeichen, ein
kleiner Preis. Dagegen: der Wächter aus #248 prüft das **ganze JSON** eines Potenzials auf Zahlen mit
Einheit, also hielte jede Korridor-Begründung mit `%` den Erkennungslauf an; eine Wiederholung würfelte
den ganzen **Schnitt** neu statt nur die Bewertung; und beide wären nicht mehr getrennt prüfbar.

### 6.2 Ein Aufruf je Lauf

Die Sorge des Tickets war, dass ein Aufruf über alle Potenziale **vergleichend** urteilt, die Skala
aber absolut ist (2.5). Sie kehrt sich um: #194 ist an Doppelzählung beim **Schneiden** gescheitert,
nicht an einem Urteil. Ein Aufruf je Potenzial kalibriert sich jedes Mal neu, und diese Streuung
landet als Rauschen in der Rangfolge — der Größe, an der BC2 gemessen wird. Ein Aufruf je Lauf ist
**ein** Urteiler mit **einem** Maßstab. Gegen das Vergleichen stehen die Anker (Nachtrag 6) und die
Regel „gleiche Werte sind erlaubt, keine Reihenfolge erzwingen".

**Abnahme im Bau: eine Stabilitätsmessung** — dasselbe Paket zweimal bewerten. Weicht ein Nutzwert
um mehr als einen Punkt ab, ist dieser Schnitt neu zu stellen.

⚠ **Gescheitert am 09.10.2026 ([#288](https://github.com/pg-coe-kmu/coe-factory/issues/288)).**
Ein Paket, einmal erkannt, zweimal bewertet (7 Potenziale, Sonnet über die CLI): das Nutzwert-Mittel
weicht bei 2 von 7 um 1,2 Punkte ab, die Kategorien bei 9 von 35 Werten um mehr als einen Punkt
(höchstens 3); ein Potenzial wechselt die Prioritätsgruppe. Lage im Korridor und Komplexität blieben
stabil. Der Schnitt ist damit neu zu stellen — in
[#299](https://github.com/pg-coe-kmu/coe-factory/issues/299). Bis dahin gilt dieser Abschnitt als
gebaut, aber nicht abgenommen.

### 6.3 Was der Aufruf sieht

Die geschnittenen Potenziale (Titel, Ausgangslage, Schmerzpunkte, Lösungsansatz, Klasse), die
entdoppelte Nutzlast der berührten Teilprozesse, den **Korridor** der Klasse und die **gemessene
Komplexität** samt den vier Skalen und BC0s sechs Kriterien als Material zum Überschreiben.
**Keine** Jahresstunden, keine Euro, keine Dauern: keine der drei Urteilsstellen braucht sie — die
Lage im Korridor fragt, wie viel die Lösung *vom Schritt* abnimmt, nicht wie oft er läuft —, und das
Rechenverbot brach in #194 genau dort, wo Zahlen in der Nutzlast standen.

### 6.4 Die Klasse ist fest

Der Bewertungsschritt **ändert die Lösungsklasse nicht**. Sie ist Teil des Schnitts, den der Mensch
am Gate 1 sieht; ein zweiter Schritt, der still umsetzt, wäre eine zweite Wahrheit über dasselbe
Potenzial. Passt die Lage nicht in den Korridor, ist das ein Verstoß (6.5). Zweifel an der Klasse
reist als **Hinweis** ans Potenzial.

### 6.5 Der Wächter

Wie in der Erkennung: **einmal wiederholen** mit benanntem Verstoß, dann **bricht der Lauf ab**.
Geprüft wird deterministisch, **vor** dem Rechenkern (der heute erst mit `ValueError` aussteigt):

- `angesetzt_min_pct` / `angesetzt_max_pct` liegen im Korridor der Klasse;
- jeder Nutzwert ist eine ganze Zahl 1–10 und trägt eine Begründung;
- ein Überschreiben der Komplexität nur mit Begründung — **Pflicht**, wo sie nicht gemessen ist
  (Nachtrag 5);
- jedes erkannte Potenzial ist **genau einmal** bewertet;
- **keine Zahl mit Einheit in Begründungstexten** — die strukturierten Felder sind ausgenommen. Genau
  diese Trennung kennt der Wächter aus #248 nicht.

### 6.6 Nachtrag 7 — der Umsetzungsaufwand · 09.10.2026 ([#288](https://github.com/pg-coe-kmu/coe-factory/issues/288))

**Der Fund.** 2.1 rechnet `Investition = aufwand_schaetzung_pt × 800 €/PT`, aber weder 2.0 noch
#260 sagten, **wer** den Aufwand liefert. Bis #288 trugen ihn nur von Hand geschriebene Messsätze
und BC3s Beispiele. Im Rechenkern hängt an ihm mehr als die Amortisation: der Vertrag verlangt
die fünf Value-Größen nur **zusammen**, also fiel ohne Aufwand auch `impact_monetaer` weg — jeder
echte Lauf hätte eine rein geurteilte Rangfolge geliefert, ohne dass es eine Entscheidung dafür gab.

**Entscheidung (Sergio, 09.10.2026): der Bewertungsschritt urteilt ihn**, als fünfte Stelle im
selben Aufruf — eine Zahl größer null in einem Zahlenfeld, dazu ein Begründungssatz, der als
Annahme in `value.annahmen` mitreist.

- **Warum das Modell.** Der Aufwand hängt an der Größe der **Lösung** — wie viele Systeme, wie
  viele Ausnahmen, wie viel Abnahme durch Menschen —, und den Lösungsansatz sieht nur das Modell.
  Die Umsetzungskomplexität misst **Prozessreife**, nicht Lösungsgröße; ein Aufwand je
  Komplexitätsstufe wäre eine Setzung auf eine Messung von etwas anderem gewesen.
- **Verworfen:** eine Tabelle PT je Komplexität (s. o.); den Aufwand offen lassen (jeder Lauf ohne
  Euro-Seite); `impact_monetaer` von der Investition entkoppeln (verlangt eine Vertragsänderung
  und berührt die laufende Fassung v3.1).
- **Was es nicht ändert.** Die Amortisation bleibt reiner Ausweis (2.1) — der geurteilte Aufwand
  wirkt nicht auf die Rangfolge. Er sieht wie die anderen Urteile **keine** Stunden, Euro oder
  Dauern (6.3): wie oft ein Schritt läuft, macht die Lösung nicht größer.
- **Der Preis.** Eine geurteilte Zahl in einer Euro-Rechnung. Sichtbar bleibt das über die Annahme
  am Potenzial; kalibriert wird sie wie Korridor und Anker am ersten echten Lauf (#206).
