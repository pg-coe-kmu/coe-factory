# ADR-009 · BC2 — Potenziale über Pakete hinweg verknüpfen: Nachfolger und Streichliste

**Status:** Entwurf · 09.10.2026
**Bezug:** [#291](https://github.com/pg-coe-kmu/coe-factory/issues/291) · Anlass: [#242](https://github.com/pg-coe-kmu/coe-factory/issues/242), Punkt 3 (Svetlana, BC3) · Karte [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158)
**Baut auf:** ADR-007 · BC2 §2.4 (ein Konzept veraltet, es wird nicht ersetzt) · ADR-008 · BC2 §2.1/§2.2 (Fassung nur innerhalb eines Pakets, Ergebnis unveränderlich) · ADR-002 (stabile IDs als Vertrag)
**Erledigt:** ADR-008 · BC2 §4 Punkt 2
**Nummer:** Die Vergabe läuft über Bounded Contexts hinweg ([#220](https://github.com/pg-coe-kmu/coe-factory/issues/220)).
Deshalb durchgängig **ADR-009 · BC2** schreiben.

---

## 1. Kontext

BC3 berechnet `epic_id` und `story_id` aus einer Prüfsumme über `konzept_id` und `potenzial_id`.
Beide Kennungen sind je Rechnung neu: „eine Kennung, ein Inhalt“ (ADR-007 · BC2). Zwischen Fassungen
eines Pakets trifft das BC3 nicht, denn BC3 sieht je Paket genau eine Fassung (ADR-008 · BC2 §2.1).
Es trifft BC3 **über Pakete hinweg**. Nach einer Nacherhebung schnürt BC0 ein neues Paket, alle
Kennungen sind neu, und BC4 legt lauter neue Tickets an, statt die bestehenden fortzuschreiben. Ein
Potenzial, das in der neuen Rechnung wegfällt, sieht heute niemand. BC4 baut womöglich daran
weiter.

BC3 schlägt `ersetzt_potenzial_ids` je Potenzial vor, leer bei einem neuen. BC3 folgt der Kette
zurück und rechnet mit der **ältesten** Kennung.

**Der Befund, der den Schnitt bestimmt:** Ein neues Paket trägt nur die **neu freigegebenen**
Teilprozesse. `v_uebergabe_kandidaten` sammelt jede Freigabe ein, die noch in keinem Paket steckt
(BC0 `schema_v2.6_historie_und_paket.sql`: „die Nachzügler“). Wird nach einer Nacherhebung nur
KP-05.TP-2 neu freigegeben, kommt ein Paket mit genau diesem Teilprozess. Die Überlappung mit einem
früheren Paket ist damit der **Normalfall**, kein Randfall.

## 2. Entscheidung

### 2.1 Ein Nachfolger ist dasselbe Vorhaben, neu bewertet

Ein **Nachfolger** ist ein Potenzial aus einem späteren Paket, das dasselbe Vorhaben ist wie ein
schon geliefertes, nur auf neuem Datenstand. Für BC4 heißt das: das bestehende Ticket wird
fortgeschrieben. Ähnlich zu klingen genügt nicht. Ändert sich die Lösung, ist es ein neues Potenzial,
und das alte ist gestrichen. Prüfbar wird das an der **Lösungsklasse**: Weicht sie ab, ist es kein
Nachfolger. Teilprozesse dürfen sich verschieben.

### 2.2 Der Anker ist der Teilprozess, nicht der Kernprozess

**Kandidaten** für einen Vorgänger sind alle Potenziale aus `approved`-Läufen früherer Pakete, deren
`betroffene_teilprozess_ids` sich mit den Teilprozessen des neuen Pakets überschneiden, jeweils aus
dem jüngsten `approved`-Lauf, der diesen Teilprozess enthielt.

- **Abgelehnte Fassungen zählen nicht.** BC3 hat sie nie gesehen.
- **An Gate 1 nicht freigegebene Potenziale zählen mit.** Sie stehen markiert in der gelieferten
  Datei (ADR-007 · BC2). Ob BC3 daraus Epics gebaut hat, weiß BC2 nicht. Daraus nicht auf BC3s
  Verhalten zu schließen ist die Lehre aus #163, #165 und #186.
- **Was das neue Paket nicht berührt, ist kein Kandidat** und gilt unverändert weiter.

### 2.3 Drei Ausgänge je Kandidat

| Ausgang | Bedeutung | Im Vertrag |
|---|---|---|
| **fortgeschrieben** | ein neues Potenzial ist sein Nachfolger | `ersetzt_potenzial_ids` des Nachfolgers |
| **gestrichen** | das Vorhaben fällt weg, mit Begründung | `gestrichene_potenziale[]` der Priorisierung |
| **unverändert** | aus diesem Paket nicht zu beurteilen, gilt weiter wie geliefert | nichts: keiner zeigt darauf, und es steht nicht auf der Streichliste |

„Unverändert“ ist **nur zulässig, wenn der Kandidat auch Teilprozesse außerhalb des Pakets
berührt**. Ein Kandidat, der ganz im Paket liegt, wurde vollständig neu gesehen, und für ihn ist zu
entscheiden. Ohne den dritten Ausgang würde jede Teilnacherhebung ein Potenzial streichen, dessen
andere Hälfte gar nicht neu gerechnet wurde.

### 2.4 Nur 1:1

Jedes neue Potenzial hat **höchstens einen** Vorgänger, jedes alte **höchstens einen** Nachfolger.
Bei einer Teilung zeigten zwei neue Potenziale auf dasselbe alte. BC3 rechnete dann für beide aus
der ältesten Kennung dieselbe `epic_id`, und bei BC4 kollidierten sie. Bei einer Zusammenlegung
wäre offen, welche Kennung „die älteste“ ist. Wird geteilt oder zusammengelegt, gelten die neuen
Potenziale als neu und die alten als gestrichen. Das passt zu 2.1: Ein geteiltes Vorhaben ist nicht
mehr dasselbe.

Der Feldname bleibt **`ersetzt_potenzial_ids`**, eine Liste, wie BC3 ihn vorgeschlagen hat und
Schema `bc2` ihn vorhält. Im Vertrag gilt `maxItems: 1`. Später auf n:m zu lockern bricht nichts.

### 2.5 Python bestimmt die Kandidaten, das Modell ordnet zu, Python prüft, der Mensch gibt frei

1. **Python** liest die Kandidaten aus `bc2.potenzial` der `approved`-Läufe (2.2).
2. **Das Modell** bekommt sie im Paketaufruf der Erkennung, **nur qualitativ**: Titel, Beschreibung,
   Lösungsklasse, Teilprozesse, keine Zahlen. Das Rechenverbot brach in #194 genau dort, wo Zahlen
   in der Nutzlast standen. Je Kandidat liefert das Modell einen Ausgang aus 2.3, bei „gestrichen“
   mit Begründung.
3. **Python prüft nach:** nur Kandidaten als Vorgänger, gleiche Lösungsklasse, 1:1, „unverändert“
   nur bei Teilprozessen außerhalb des Pakets, jeder Kandidat genau ein Ausgang.
4. **Der Mensch bestätigt mit der Freigabe.** Eine falsche Kette ist ein Ablehnungsgrund, und die
   Begründung geht als Hinweis in die nächste Fassung (ADR-008 · BC2 §2.1). Gate 1 bekommt
   **keinen** eigenen Editierweg für die Kette.

### 2.6 `ersetzt_konzept_id` bleibt auf ein Paket beschränkt

ADR-008 · BC2 §2.1 wird **nicht** geöffnet. Ein Konzept über KP-05.TP-2 ersetzt kein Konzept über
TP-1 bis TP-3. Es überschneidet sich nur mit ihm. Die Fortschreibung über Pakete hinweg lebt
**ausschließlich auf Potenzialebene**. ADR-007 · BC2 §2.4 gilt weiter: Ein Konzept veraltet.

### 2.7 Vertrag: in v3.1, Pflicht ab 3.1

| Schema | Feld | Form |
|---|---|---|
| `konzept.schema.json` | `potenziale[].ersetzt_potenzial_ids` | Liste aus UUIDs, `maxItems: 1`, `[]` bei einem neuen Potenzial |
| `priorisierung.schema.json` | `gestrichene_potenziale[]` | `{potenzial_id, kp_id, begruendung}`, `[]` wenn nichts gestrichen ist |

Beide sind ab `schema_version` 3.1 Pflicht und fehlen in 3.0, nach demselben Muster wie die
Ausgangslage in [PR #287](https://github.com/pg-coe-kmu/coe-factory/pull/287). Mitgenommen wird
die Änderung in **dieselbe v3.1**: #287 ist vorab gemergt, BC3s Bestätigung steht aber noch aus,
und so bestätigt BC3 einmal statt zweimal. Damit springt auch `konzept.schema.json` auf 3.1.

## 3. Warum nicht anders

**Warum nicht die Kernprozess-Ebene als Anker.** Dann wären alle Potenziale des zuletzt gelieferten
Konzepts Kandidaten. Bei einer Teilnacherhebung sähe alles, was nur TP-1 oder TP-3 berührt, aus
wie gestrichen, und BC4 würde genau das abbauen, was die Kette schützen soll.

**Warum die Streichliste nicht implizit.** „Gestrichen ist, worauf keiner zeigt“ setzt voraus,
dass BC3 die Kandidatenmenge aus 2.2 selbst nachbaut. Sonst hält BC3 jedes Potenzial außerhalb des
Pakets für gestrichen. BC2 kennt die Menge ohnehin.

**Warum die Streichliste nicht im Konzept.** `potenziale` hat `minItems: 1`. Bleibt bei einem
Kernprozess nur Gestrichenes, entsteht kein Konzept, das die Streichung tragen könnte. Die
Priorisierung ist das eine Ereignis je Lauf (ADR-007 · BC2).

**Warum keine deterministische Regel allein.** „Gleicher Teilprozess plus gleiche Lösungsklasse“
ist mehrdeutig, sobald ein Teilprozess zwei Potenziale derselben Klasse trägt. Ob zwei Potenziale
dasselbe Vorhaben sind, ist ein Urteil. Die Regel bleibt als Nachprüfung, nicht als Zuordnung.

**Warum kein Editierweg an Gate 1.** Das Ergebnis ist nach dem Schreiben unveränderlich, und
ausgeliefert wird das gespeicherte Dokument (ADR-008 · BC2 §2.2). Eine Kette, die erst an Gate 1
entstünde, müsste beim Ausliefern hineingemischt werden. Damit wäre die Stelle offen, an der das
Ausgelieferte vom Abgelegten abweicht.

**Warum nicht die `potenzial_id` stabil halten.** Das war BC3s erste Frage. Sie bleibt nicht gleich,
weil jede Rechnung neu schneidet. Eine alte Kennung wiederzuverwenden hieße, dass eine Kennung zwei
Inhalte trägt, und widerspricht ADR-007 · BC2.

## 4. Folgen

1. **Vertrag** in [PR #297](https://github.com/pg-coe-kmu/coe-factory/pull/297): beide Schemas auf
   3.1, README mit „Was BC3 tun muss“, Kettenregel in `tools/kette.py` für `validate.py`, Fixtures.
   Geht mit #287 zusammen zur Bestätigung an BC3 (#242).
2. **Bau** in [#295](https://github.com/pg-coe-kmu/coe-factory/issues/295), blockiert durch den Bau von Schema `bc2` (#290): Kandidaten
   lesen, Kandidaten in die Erkennungsnutzlast, Nachprüfung, Gestrichenes und Ketten in der
   Gate-1-Ansicht, `bc2.potenzial.ersetzt_potenzial_ids` schreiben.
3. **Bis dahin ist `[]` richtig**, denn es gibt noch keinen echten `approved`-Lauf. **Auflage an
   #290:** Findet ein Lauf Kandidaten nach 2.2, solange die Verknüpfung nicht gebaut ist, bricht er
   ab, statt still `[]` zu liefern. Voraussichtlich wird das zum ersten Mal bei der
   KP-05-Nacherhebung (#143) relevant.
4. **BC3** folgt der Kette zur ältesten Kennung und entscheidet selbst, was BC4 mit einem
   gestrichenen Potenzial tut.

---

## Nachtrag 1 · Beim Bau (#295, 09.10.2026)

Gebaut in `app/nachfolge.py` (Kandidat, Ausgang, Nachprüfung), `app/erkennung/` (Nutzlast,
Anweisung, Wächter), `app/ablage.py` (Kandidaten, Prüfung vor dem Ablegen, Vertrag) und der
Gate-1-Ansicht. Vier Punkte, die der Entwurf offen ließ oder anders sagte:

1. **Kandidat ist, was gilt, nicht was zuletzt den Teilprozess enthielt.** §2.2 sagt „jeweils aus
   dem jüngsten `approved`-Lauf, der diesen Teilprozess enthielt“. Das lässt sich so nicht bauen,
   weil Schema `bc2` die Teilprozesse eines Pakets nicht kennt, nur die seiner Potenziale. Wörtlich
   genommen wäre es auch falsch: Schreibt Paket B ein Potenzial aus A über TP-1 fort, und Paket C
   bringt TP-2, dann ist der jüngste Lauf mit TP-2 noch A, und das schon fortgeschriebene Potenzial
   bekäme einen zweiten Nachfolger (§2.4). Gebaut ist darum: **Kandidat ist jedes Potenzial eines
   freigegebenen Laufs, das einen Teilprozess des Pakets berührt und das kein freigegebener Lauf
   seither fortgeschrieben oder gestrichen hat.** Das ist, was bei BC3 gerade gilt.
2. **Die Ablage legt den Lauf an, bevor sie rechnet.** Die Kandidaten gehen in den Paketaufruf der
   Erkennung (§2.5), müssen also vor der Rechnung feststehen. Dafür trägt `Laufkopf` jetzt die
   Teilprozesse des **Pakets** (`teilprozess_ids`). Damit ist auch die Lücke der Sperre aus §4.3
   geschlossen: bis hierher suchte sie nur über die Teilprozesse der geschnittenen Potenziale, und
   ein Paket, das einen gelieferten Teilprozess neu brachte, ohne diesmal etwas aus ihm zu schneiden,
   lief durch.
3. **Die Sperre aus §4.3 bleibt an zwei Stellen.** Sie hält einen Lauf mit Kandidaten an, wenn seine
   Quelle sie nicht beurteilt (Messsatz) oder wenn er ohne Ausgangslage kommt, also als Vertrag 3.0,
   der für die Kette keine Felder hat. **Das zweite trifft heute den echten Weg:**
   `PaketLaufquelle` setzt noch keine Vertragskonzepte und keine Ausgangslage zusammen. Ein Paket
   über schon gelieferte Teilprozesse läuft dort erst durch, wenn das gebaut ist.
4. **„Unverändert“ wird nicht abgelegt.** Der Ausgang steht nicht im Vertrag (§2.3), und Schema
   `bc2` setzt ein Ergebnis nie aus etwas anderem als den Vertragsdokumenten zusammen
   (ADR-008 · BC2, 2.2). Die Gate-1-Ansicht zeigt darum Vorgänger und Streichliste, aber nicht, was
   als unverändert gemeldet wurde. Geprüft wird es trotzdem, im Wächter und vor dem Ablegen.

Die Anweisung für die Kandidaten wird **nur angehängt, wenn es welche gibt**. Ein Lauf ohne
Kandidaten bekommt dieselbe Frage wie vorher, damit die Messungen zu #299 nicht über eine geänderte
Frage laufen.

**Offene Grenze:** Zwei Pakete, die gleichzeitig offen sind und denselben Kandidaten fortschreiben,
werden einzeln richtig geprüft. Werden beide freigegeben, hat der Kandidat zwei Nachfolger. Ob das
vorkommen kann, hängt daran, wie BC0 Pakete schnürt; geprüft ist es nicht. Eine Sperre dagegen
gehörte an die Freigabe, nicht an die Rechnung.

