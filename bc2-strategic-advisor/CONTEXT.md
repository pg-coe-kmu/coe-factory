# BC2 — Strategic Advisor

Der Kontext zwischen Gate 0 und Gate 1: er liest den freigegebenen Prozessbestand einer Firma,
findet darin Automatisierungspotenziale, bewertet und ordnet sie und übergibt das Ergebnis an BC3.

Dieses Dokument ist ein **Glossar** — es legt fest, was die Wörter bedeuten und wer sie setzt.
Rechenregeln stehen nicht hier (die entscheidet [#166](https://github.com/pg-coe-kmu/coe-factory/issues/166)),
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
Datenstand ergibt dasselbe Ergebnis.
_Avoid_: Durchlauf, Analyse, Job

**Ausgangslage**:
Die Beschreibung dessen, was heute geschieht — Prozessverlauf, beteiligte Systeme, Schmerzpunkte.
Wird je Kernprozess aus dem Datenstand des Pakets geschrieben, nicht als eigenes Artefakt geführt.
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

**Schmerzpunkt**:
Eine benannte Schwierigkeit im heutigen Ablauf — Wartezeit, Medienbruch, Doppelerfassung. Motiviert
Potenziale, schneidet sie aber nicht.
_Avoid_: Pain Point, Problem, Engpass

**Lösungsansatz**:
Der vorgeschlagene Weg, ein Potenzial umzusetzen. Hängt am Potenzial und ist nicht das Potenzial:
dasselbe Potenzial kann verschieden gelöst werden.
_Avoid_: Muster, Pattern, empfohlenes Muster

### Wie BC2 bewertet

**Manueller Aufwand heute**:
Wie viel Handarbeit der heutige Ablauf je Jahr kostet. Eine **gemessene** Größe aus **Dauer und
Häufigkeit** — kein Urteil. Die **Fallzahl geht nicht als Faktor ein**: die Dauer eines
Prozessdurchlaufs deckt seine Fälle schon ab. *(Präzisiert am 10.09.2026, #184. Die
Vorgängerfassung nannte „Dauer, Häufigkeit und Menge" und legte damit ein Produkt aus dreien nahe —
gerechnet ergäbe das für die Reisebuchung das Dreifache der Gesamtkapazität des Mandanten.)*
_Avoid_: Ist-Aufwand, Handaufwand

**Value**:
Die **monetäre** Nutzenaussage eines Potenzials in Euro pro Jahr — Einsparung gegen Investition.
Entweder gerechnet oder als Annahme gekennzeichnet, nie beides stillschweigend.
_Avoid_: ROI, Wirtschaftlichkeit, Business Value

**Nutzwert**:
Der **nicht-monetäre** Nutzen eines Potenzials — Qualität, Durchlaufzeit, Mitarbeiterzufriedenheit,
Zukunftssicherheit. Die einzige Urteilsgröße auf der Nutzenseite.
_Avoid_: Soft Benefits, qualitativer Nutzen

**Impact**:
Die **Mehrwert-Achse** der Priorisierung, ordinal von 1 bis 10. Fasst Value und Nutzwert zu einer
Zahl zusammen und ist deshalb **gerechnet**, nicht geurteilt.
_Avoid_: Mehrwert, Nutzen, Wirkung

**Umsetzungskomplexität**:
Die **Aufwands-Achse** der Priorisierung, ordinal von 1 bis 10. Die einzige geurteilte Achse — es
gibt keine Messung dafür.
_Avoid_: Aufwand, Schwierigkeit, Komplexität (unqualifiziert)

**Prioritätsscore**:
Die Zahl, die Impact und Umsetzungskomplexität zu einer Rangfolge verrechnet. Ein **Vorschlag**, den
der Mensch am Gate 1 überschreiben darf.
_Avoid_: Priorität, Ranking-Wert, Punktzahl

**Kategorie**:
Das **Etikett** eines Potenzials im Quadranten aus Impact und Umsetzungskomplexität. Sagt nichts über
die Reihenfolge und darf mehrfach vorkommen — mehrere Potenziale eines Laufs können „Quick Win" sein.
_Avoid_: Low Hanging Fruit, Priorität, Klasse

**Prioritätsgruppe**:
Der **Rangblock**, in dem ein Potenzial umgesetzt werden soll (PRIO 1, 2, 3). Trägt die Reihenfolge;
jedes Potenzial steht in genau einer.
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
