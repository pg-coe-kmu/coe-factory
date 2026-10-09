# BC2 — Strategic Advisor

Der Kontext zwischen Gate 0 und Gate 1: er liest den freigegebenen Prozessbestand einer Firma,
findet darin Automatisierungspotenziale, bewertet und ordnet sie und übergibt das Ergebnis an BC3.

Dieses Dokument ist ein **Glossar** — es legt fest, was die Wörter bedeuten und wer sie setzt.
Rechenregeln stehen nicht hier (die stehen in
[ADR-006 · BC2](docs/adr/ADR-006_Value_und_Priorisierungsmodell.md), entschieden in
[#166](https://github.com/pg-coe-kmu/coe-factory/issues/166)),
Feldnamen und Schemastände auch nicht (die stehen im Vertrag unter `contracts/bc2-to-bc3/`).

## Language

### Was BC2 bekommt

**Mandant**:
Die Firma, deren Prozesse betrachtet werden. Trennt die Daten mehrerer Firmen in derselben Datenbank
voneinander; jede Aussage von BC2 gilt für genau einen Mandanten.
_Avoid_: Kunde, Company, Unternehmen

**Anfrage**:
Ein von außen an das CoE herangetragener Auftrag, etwas zu automatisieren. Trägt eine ID der Form
`A-JJJJ-NN` und berührt einen oder mehrere Teilprozesse, von denen einer der Hauptbezug ist.
_Avoid_: Use Case, UC, Auftrag

**Kernprozess**:
Ein fachlich abgeschlossener Prozess des Mandanten, von BC0 erhoben. Trägt eine ID der Form `KP-XX`.
_Avoid_: Hauptprozess, Prozess (unqualifiziert)

**Teilprozess**:
Ein Abschnitt eines Kernprozesses und die kleinste Einheit, für die BC0 erhebt und für die Gate 0
entscheidet. Trägt eine ID der Form `KP-XX.TP-Y`.
_Avoid_: Prozessschritt, Subprozess

> **`betroffene_prozessschritte` im Vertrag** trägt die **Namen** der berührten Teilprozesse. Das
> Feld benutzt das gemiedene Wort und bleibt trotzdem — ein Vertrag bricht nicht für ein Wort.
> Gemeint ist der Teilprozess. *(#301)*

**Fokus-Schritt**:
BC1s Wort für den Teilprozess, zu dem es ein Profil erhebt — dieselbe ID, eine andere Perspektive.
Was BC1 je Schritt misst (Dauer, Häufigkeit, Reifeskalen), gehört zu genau einem Teilprozess; ein
Potenzial über mehrere Teilprozesse hat darum mehrere Fokus-Schritte.
_Avoid_: Schritt (unqualifiziert), Prozessschritt

**Prozessdurchlauf**:
Eine Ausführung eines Kernprozesses beim Mandanten, von seinem Auslöser bis zu seinem Ergebnis.
Die Bezugsgröße aller Zeit- und Mengenangaben von BC1: `frequency_per_year` zählt Prozessdurchläufe
je Jahr, `total_duration_minutes` misst die Minuten **eines** Prozessdurchlaufs. Hat mit dem
Analyselauf nichts zu tun — der eine geschieht beim Mandanten, der andere bei BC2.
_Avoid_: Durchlauf (unqualifiziert), Lauf, Run, Vorgang

**Fall**:
Ein einzelner Vorgang, der innerhalb **eines** Prozessdurchlaufs bearbeitet wird; BC1 zählt sie als
`executions_per_run`. Beschreibt, wie schwer ein Durchlauf wiegt — **nicht**, wie oft er stattfindet.
Die Dauer eines Prozessdurchlaufs deckt seine Fälle bereits ab, Fälle multiplizieren sie also nicht
(siehe `contracts/bc1-to-bc2/README.md`, I1/I2).
_Avoid_: Menge, Vorgang, Transaktion, Item

**Paket**:
Die Menge freigegebener Teilprozesse, die BC0 nach Gate 0 zusammenschnürt und in einem Zug an BC2
übergibt. Trägt eine ID und einen Übergabezeitpunkt; ein Nachzügler ist ein neues Paket, kein
verändertes.
_Avoid_: Batch, Lieferung, Charge

**Analyselauf**:
Eine Bearbeitung genau eines Pakets durch BC2, von der Annahme des Anstoßes bis zum fertigen
Ergebnis. Die Einheit, auf die sich Reproduzierbarkeit bezieht: derselbe Lauf auf demselben
Datenstand ergibt dasselbe Ergebnis. Ein Paket kann mehrere Analyseläufe haben — jeder ist eine
**Fassung**.
_Avoid_: Durchlauf, Analyse, Job

**Fassung**:
Die laufende Nummer eines Analyselaufs über **dasselbe** Paket. Eine neue Fassung entsteht nur,
wenn Gate 1 die vorige abgelehnt hat, und BC2 stößt sie selbst an; die abgelehnte bleibt
abrufbar. Ein neues Paket beginnt wieder bei der ersten Fassung — neue Daten sind ein neues Paket,
keine neue Fassung. Ein technischer Fehlschlag ist keine Fassung.
_Avoid_: Version, Revision, Iteration

**Ausgangslage**:
Die Beschreibung dessen, was heute geschieht — Prozessverlauf, beteiligte Systeme, Schmerzpunkte.
Wird je Kernprozess aus dem Datenstand des Pakets geschrieben, nicht als eigenes Artefakt geführt.
Für den ganzen **Analyselauf** fasst die Priorisierung sie zusammen (seit Vertrag v3.1, #254): die
Angaben zum Mandanten aus seinem Mandantensatz, die Schmerzpunkte aller Konzepte als
**Herausforderungen** zusammengeführt und eine optionale Kernaussage. Sie ist Teil 1 der
Präsentation — und steht deshalb im Vertrag, damit die Präsentation sie nicht erfinden muss.
_Avoid_: Prozessprofil, Ist-Aufnahme, Baseline

> **`Prozessprofil` ist kein Wort von BC2.** Es bezeichnet BC1s Erhebungsergebnis je Teilprozess und
> wird für nichts anderes verwendet — insbesondere nicht für die Vereinigung aus BC0-Baseline und
> BC1-Profil, auf der BC2 arbeitet. Die hat keinen Namen, weil sie nie als Artefakt entsteht.

### Was BC2 findet

**Potenzial**:
Eine abgrenzbare Automatisierungsmöglichkeit innerhalb eines Kernprozesses, die für sich gebaut und
in Betrieb genommen werden kann und einen eigenen Nutzen trägt. Nennt die Teilprozesse, die sie
berührt.
_Avoid_: Automatisierungsfall, Maßnahme, Use Case

> **Der Trenntest.** Zwei Potenziale liegen vor, wenn sie **unabhängig voneinander in Betrieb gehen
> könnten** *und* ihre Nutzenrechnungen sich **nicht doppelt zählen**. Fällt eine der beiden
> Bedingungen weg, ist es **ein** Potenzial. Weder ein Teilprozess noch ein Schmerzpunkt schneidet
> Potenziale: ein Teilprozess kann mehrere tragen, und ein Potenzial kann mehrere Teilprozesse
> berühren.

**Nachfolger**:
Ein Potenzial aus einem späteren Paket, das **dasselbe Vorhaben** ist wie ein schon geliefertes
Potenzial, nur neu bewertet auf neuem Datenstand. Ähnlich zu klingen genügt nicht: Ändert sich
die Lösung, ist es ein neues Potenzial. Vorgänger kommen nur aus gelieferten Läufen und nur dann,
wenn sie einen Teilprozess des neuen Pakets berühren. Was das neue Paket nicht berührt, gilt
unverändert weiter. *(#291)* Wer so in Frage kommt, ist ein **Kandidat**, und nur solange er
**gilt**: ein schon fortgeschriebenes oder gestrichenes Potenzial ist keiner mehr. *(#295)*
_Avoid_: Nachfolgefassung, Version, ähnliches Potenzial

**Schmerzpunkt**:
Eine benannte Schwierigkeit im heutigen Ablauf — Wartezeit, Medienbruch, Doppelerfassung. Motiviert
Potenziale, schneidet sie aber nicht. Über alle Konzepte eines Laufs zusammengeführt heißt er in der
Ausgangslage **Herausforderung** — dasselbe Ding auf Laufebene, kein neues Urteil.
_Avoid_: Pain Point, Problem, Engpass

**Lösungsansatz**:
Der vorgeschlagene Weg, ein Potenzial umzusetzen. Hängt am Potenzial und ist nicht das Potenzial:
dasselbe Potenzial kann verschieden gelöst werden.
_Avoid_: Muster, Pattern, empfohlenes Muster

**Lösungsklasse**:
Eine von **fünf** festen Einordnungen des Lösungsansatzes — `Regelwerk/Weiterleitung`,
`Integration`, `Extraktion`, `Textgenerierung`, `Assistenz`. Sie ist kein Etikett, sondern trägt
den **Automatisierungsgrad**: an ihr hängt der Korridor, in dem verortet wird (ADR-006 · BC2).
Geschrieben wird sie **wörtlich so** wie hier — die Namen stehen im Vertrag als Aufzählung, und
eine sechste oder eine andere Schreibweise hat keinen Korridor.
_Avoid_: Lösungsansatz-Klasse, Automatisierungsklasse, Kategorie, Muster

> **Drei Namen, eine Sache — und einer davon ist gefährlich.** Der Vertrag führt sie als
> `automatisierungsgrad.klasse`, ADR-006 als „Lösungsansatz-Klasse", der Erkennungsschritt als
> `loesungsklasse`. Das ist hinnehmbar, solange die **Werte** dieselben sind. Sie waren es nicht:
> der Prototyp zu #194 bot dem Modell fünf ganz andere an, und **10 von 10** seiner Potenziale
> trugen damit eine Klasse, die der Vertrag nicht kennt (Fund in #248). `Integration` fehlte ihm
> ganz — ausgerechnet die Klasse für Medienbrüche, also NoroAIs Hauptbefund.

**Nicht geschnitten**:
Ein freigegebener Teilprozess, aus dem **bewusst kein** Potenzial entstand — weil er keine
Bewertungen trägt oder nur einen Platzhalter-Namen. Er wird **gemeldet, nicht weggelassen**: ein
Paket hat ihn freigegeben, und sein lautloses Verschwinden wäre von einem Versäumnis nicht zu
unterscheiden. Eine fehlende Bewertung ist eine **Lücke, keine Null** — wer sie als Zahl liest,
hält den unerhobenen Teilprozess für den am schlechtesten automatisierbaren im Bestand.
_Avoid_: übersprungen, ignoriert, leer, unbewertet

### Wie BC2 bewertet

**Bewertungsschritt**:
Der Abschnitt eines Analyselaufs, in dem das LLM die **geschnittenen** Potenziale beurteilt — Lage im
Korridor, Nutzwert, begründetes Überschreiben der Umsetzungskomplexität und seit #288 der
**Umsetzungsaufwand**. Folgt dem
**Erkennungsschritt**, der die Potenziale schneidet und ihre Lösungsklasse setzt, und ändert an
diesem Schnitt nichts; nach der Rechnung folgt der **Ausarbeitungsschritt**. Er urteilt jeden Lauf **mehrfach** — ein **Urteil** ist eine vollständige
Bewertung aller Potenziale in einem Aufruf —, und je Größe gilt der **Median** der Urteile
*(seit #299)*: ein einzelnes Urteil trägt eine eigene Verschiebung, die in der Rangfolge landet.
_Avoid_: Bewertung (unqualifiziert — so heißen BC0s Bitkom-Einstufungen), Scoring, Rating

**Manueller Aufwand heute**:
Wie viel Handarbeit der heutige Ablauf je Jahr kostet. Eine **gemessene** Größe aus **Dauer und
Häufigkeit** — kein Urteil. Bei einem Potenzial ist es die Handarbeit **der Fokus-Schritte, die es
berührt**, nicht die des ganzen Kernprozesses. Die **Fallzahl geht nicht als Faktor ein**: die Dauer eines
Prozessdurchlaufs deckt seine Fälle schon ab. *(Präzisiert am 10.09.2026, #184. Die
Vorgängerfassung nannte „Dauer, Häufigkeit und Menge" und legte damit ein Produkt aus dreien nahe —
gerechnet ergäbe das für die Reisebuchung das Dreifache der Gesamtkapazität des Mandanten.)*
_Avoid_: Ist-Aufwand, Handaufwand

**Value**:
Die **monetäre** Nutzenaussage eines Potenzials in Euro pro Jahr — Einsparung gegen Investition.
Entweder gerechnet oder als Annahme gekennzeichnet, nie beides stillschweigend.
_Avoid_: ROI, Wirtschaftlichkeit, Business Value

**Nutzwert**:
Der **nicht-monetäre** Nutzen eines Potenzials — Qualität, Durchlaufzeit, Fehlerreduktion,
Mitarbeiterzufriedenheit und Compliance/Rechtssicherheit. Die einzige Urteilsgröße auf der
Nutzenseite. **Kostenreduktion gehört nicht dazu** — sie ist der `value`; sie hier mitzuzählen
zählte sie über `impact` doppelt. *(Korrigiert am 11.09.2026: die Ursprungsfassung zählte
**Zukunftssicherheit** mit auf und machte sie damit über `impact` zum Formelterm — die Karte hat am
30.08.2026 ausdrücklich das Gegenteil entschieden. Sie ist ein Querschnitt. Am 20.09.2026 um
Compliance/Rechtssicherheit ergänzt, #166: sie ist bei NoroAI der eigentliche Grund für KP-03 und
verschwand unter „Qualität".)*
_Avoid_: Soft Benefits, qualitativer Nutzen

**Querschnitt**:
Ein Gesichtspunkt, der ein Potenzial betrifft, aber **bewusst in keine Rechnung eingeht** —
Zukunftssicherheit, Abhängigkeiten zu anderen Potenzialen, der **Reifegrad** und das
**Umsatzpotenzial**. Wird dem Entscheider am Gate 1 angezeigt, nicht verrechnet: überschreiben kann
er nur, was er sieht. *(Ergänzt am 20.09.2026, #166. Das Umsatzpotenzial ist monetär und trotzdem
Querschnitt: es ist keine Einsparung, und um es zu rechnen müsste BC2 wissen, wessen Zeit frei wird
— die Rollenachse wird nach #172 nicht erhoben.)*
_Avoid_: Achse, Kriterium, Faktor

**Impact**:
Die **Mehrwert-Achse** der Priorisierung, ordinal von 1 bis 10. Fasst Value und Nutzwert zu einer
Zahl zusammen und ist deshalb **gerechnet**, nicht geurteilt.
_Avoid_: Mehrwert, Nutzen, Wirkung

**Umsetzungskomplexität**:
Die **Aufwands-Achse** der Priorisierung, ordinal von 1 bis 10. **Gemessen** aus BC1s vier Skalen am
Fokus-Schritt, vom LLM begründet überschreibbar; fehlen die Skalen, wird sie geurteilt. Ob sie
gemessen oder geurteilt ist, reist als Herkunft mit. *(Korrigiert am 20.09.2026, #166: die
Vorgängerfassung nannte sie „die einzige geurteilte Achse — es gibt keine Messung dafür". Der
BC1-Vertrag vom 10.09.2026 bindet zehn Tage später genau vier gemessene 1-bis-5-Skalen an diese
Achse, und BC0 misst sechs weitere in `v_prozessautomatisierung`. Die Zeile war schon beim
Schreiben überholt.)*
_Avoid_: Aufwand, Schwierigkeit, Komplexität (unqualifiziert)

**Umsetzungsaufwand**:
Die **Personentage**, die Bau und Inbetriebnahme einer Lösung beim CoE kosten — Basis der
Investition im **Value**. **Geurteilt** im Bewertungsschritt, mit Begründung, die als Annahme
mitreist (ADR-006 · BC2, Nachtrag 7, #288). Nicht die **Umsetzungskomplexität**: die ist eine
Ordinalachse aus der Prozessreife und geht in den Score ein; der Aufwand misst die Größe der Lösung
und wirkt nur über die Amortisation, die reiner Ausweis ist.
_Avoid_: Komplexität, Bauaufwand (unqualifiziert), Investition (die ist der Aufwand mal Bausatz)

**Prioritätsscore**:
Die Zahl, die Impact und Umsetzungskomplexität zu einer Rangfolge verrechnet. Ein **Vorschlag**, den
der Mensch am Gate 1 überschreiben darf.
_Avoid_: Priorität, Ranking-Wert, Punktzahl

**Kategorie**:
Das **Etikett** eines Potenzials im Quadranten aus Impact und Umsetzungskomplexität — Quick Win,
Strategisch, Optional, Zurückgestellt. Sagt nichts über die Reihenfolge und darf mehrfach vorkommen
— mehrere Potenziale eines Laufs können „Quick Win" sein. *(Die vierte Ecke hieß bis zum 20.09.2026
„Long Bet"; eine Wette verspricht einen Gewinn, den geringer Mehrwert bei hohem Aufwand gerade nicht
zeigt.)*
_Avoid_: Low Hanging Fruit, Long Bet, Priorität, Klasse

**Prioritätsgruppe**:
Der **Rangblock**, in dem ein Potenzial umgesetzt werden soll (PRIO 1, 2, 3). Ein **Schnitt durch den
Potenzialrang** entlang fester Score-Bänder; jedes Potenzial steht in genau einer. *(Präzisiert am
20.09.2026, #166: die Vorgängerfassung sagte „trägt die Reihenfolge" und widersprach damit
`Potenzialrang`, der sich „die primäre Rangfolge" nennt. Die Reihenfolge trägt der Rang, die Gruppe
fasst zusammen. Nicht nach `Kategorie` geschnitten — Kategoriegruppen wären im Rang nicht
zusammenhängend.)*
_Avoid_: Welle, Stufe, Kategorie

**Potenzialrang**:
Die Stellung eines Potenzials in der Reihenfolge über den ganzen Analyselauf. Die primäre Rangfolge,
weil das Potenzial die baubare Einheit ist.
_Avoid_: Rang (unqualifiziert)

**Prozessrang**:
Die Stellung eines Kernprozesses in der Reihenfolge, **abgeleitet** aus den Rängen seiner Potenziale.
Beantwortet, welcher Prozess zuerst angefasst werden soll.
_Avoid_: Prozesspriorität

### Was BC2 ausliefert

**Ausarbeitungsschritt**:
Der Abschnitt eines Analyselaufs, in dem das LLM die **gerechneten** Potenziale zu Konzepten
ausarbeitet — Beschreibung, Soll-Vision, User Story, Akzeptanzkriterien, Kontext und
Schmerzpunkte. Folgt der Rechnung und ändert an Schnitt, Bewertung und Rang nichts: er kennt den
Rang, bewegt ihn aber nicht. Ein Aufruf je **Konzept**. *(Seit #301, ADR-010 · BC2.)*
_Avoid_: Formulierung (so heißt die Zahlendarstellung der Präsentation), Textgenerierung (eine
Lösungsklasse), Texterzeugung

**Konzept**:
Das Ergebnis für **einen Kernprozess**: seine Ausgangslage und seine bewerteten Potenziale. Ein
Analyselauf erzeugt so viele Konzepte, wie sein Paket Kernprozesse berührt.
_Avoid_: Automatisierungskonzept, Bericht, Analyse

**Priorisierung**:
Das Ergebnis für **den Analyselauf**: die Reihenfolge über alle Potenziale aller Konzepte, samt
Prozessrang. Hält die Konzepte eines Laufs zusammen.
_Avoid_: Ranking, Roadmap, Reihenfolge

**Präsentation**:
Die menschenlesbare **Darstellung** von Konzepten und Priorisierung als herunterladbares Dokument.
Kein eigenes Ergebnis — sie trägt keine Information, die nicht in den beiden anderen steht.
_Avoid_: Report, Foliensatz, Ergebnisdokument

**Gate 1**:
Die Entscheidung des Menschen über die Priorisierung: freigeben, ablehnen oder die vorgeschlagene
Reihenfolge überschreiben. Der Abschluss eines Analyselaufs und die Übergabe an BC3.
_Avoid_: Freigabe, Approval
