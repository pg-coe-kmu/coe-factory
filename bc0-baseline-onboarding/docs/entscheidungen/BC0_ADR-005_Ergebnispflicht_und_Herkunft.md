# ADR-005 — Ergebnispflicht und Herkunftsnachweis

**Status:** ✅ **ANGENOMMEN** — R1, R2 und R3 gelten für alle Bounded Contexts.
Festgehalten am 01.09.2026 (siehe Nachtrag am Ende).
**Autor:** Simeon Ehmer · Bounded Context 0 (Baseline und Reifegrad)
**Datum:** 17.08.2026
**Ersetzt nicht, sondern ergänzt:** ADR-003 (SSoT-Schreibmodell), ADR-004 (Identität der Entitäten)
**Zugehöriges Arbeitspaket:** [#142](https://github.com/pg-coe-kmu/coe-factory/issues/142), Frist 21.08.2026


---

> ## ⚠️ Nummernkonflikt — und er geht auf unser Konto
>
> **Die Nummer 005 ist im Projekt zweimal vergeben.** Dieses Papier trägt sie seit dem 17.08.2026.
> BC2 hat sie am 10.09.2026 für „Der Analyselauf ist das Paket, nicht der Mandant" gezogen
> ([`bc2-strategic-advisor/docs/adr/ADR-005_Analyselauf_ist_das_Paket.md`](../../../bc2-strategic-advisor/docs/adr/ADR-005_Analyselauf_ist_das_Paket.md)).
> **Beide Beschlüsse gelten. Wer „ADR-005" schreibt, muss seitdem den Bounded Context dazusagen.**
>
> **Der Fehler liegt bei BC0 — und es war nicht die Wahl der Nummer.** Dieses Papier wurde am
> 01.09.2026 vom Team angenommen und danach **drei Wochen lang nicht ins Repository eingecheckt**;
> es lag ausschließlich im Projektordner von BC0. Wer im Repository nach der nächsten freien
> ADR-Nummer sah, fand ADR-004 als höchste. **Die 5 sah frei aus, weil unser Papier nirgends
> stand.** BC2 hat sie in gutem Glauben gezogen.
>
> **Die Doppelvergabe ist die Folge einer fehlenden Ablage, nicht einer falschen Wahl** — und damit
> ein Verstoß gegen genau das, was dieses Papier unter **R1** fordert: was erarbeitet ist, liegt am
> vereinbarten Ort und nicht im eigenen Werkzeug. Die Regel hat als Erstes ihren eigenen Autor
> eingeholt.
>
> **Keines der beiden Papiere wird umbenannt.** Umbenennen wäre teuer — „ADR-005" steht in rund 30
> Dateien des Repositories, darunter Schema, Tests und drei Design-Papiere von BC1. Beide Beschlüsse
> sind stattdessen im ADR-Register mit Warnhinweis ausgewiesen ([`../../README.md`](../../README.md),
> eingetragen von BC2 mit [#197](https://github.com/pg-coe-kmu/coe-factory/pull/197)). Wie die
> Nummernvergabe künftig läuft, entscheidet
> [#220](https://github.com/pg-coe-kmu/coe-factory/issues/220).
>
> *Eingecheckt am 21.09.2026 — verspätet.*

---

## Leitgedanke: die Vorgabe, aus der sich alles ableitet

Prof. Dorka gibt für die Projektarbeit **Reproduzierbarkeit, Transparenz und Nachvollziehbarkeit** vor. ADR-003 hat das Datenmodell ausdrücklich aus dieser Vorgabe abgeleitet und nicht aus technischer Bequemlichkeit. Dieses Papier führt dieselbe Linie fort — jede der drei Regeln beantwortet eine der drei Fragen:

| Anforderung | Frage, die beantwortet werden muss | beantwortet durch |
|---|---|---|
| **Reproduzierbarkeit** | Lässt sich ein Ergebnis von damals mit den Daten von damals erneut herleiten? | R1 — was nicht abgelegt ist, lässt sich nicht herleiten |
| **Transparenz** | Ist sichtbar, welcher Bounded Context welchen Wert beigetragen hat? | R2, erste Angabe — und R3, denn ein Eingriff ohne Spur macht sie unsichtbar |
| **Nachvollziehbarkeit** | Ist zu jedem Wert belegt, woher er stammt und wann er entstand? | R2, dritte und vierte Angabe |

> Ein Datenmodell, das eine dieser drei Fragen offen lässt, erfüllt die Vorgabe nicht — unabhängig davon, wie gut es technisch funktioniert.
> *(Leitsatz aus ADR-003, vom Team am 10.08.2026 angenommen)*

Die Governance-Phase des Projekts nennt die Anforderung auch ausdrücklich beim Namen. Aus dem KickOff vom 18.04.2026, Phase „Rollout & Governance": *„CI/CD für Bots/Modelle, Monitoring, Audit Logs, DSGVO Check."* Ein Audit-Log ohne Herkunftsangabe protokolliert, dass etwas geschah — nicht, worauf es beruhte.

### Dieser Vorschlag ist keine neue Forderung

ADR-003 hat die Konsequenz bereits gezogen und benannt:

> „Herkunftsnachweis würde Pflicht statt Kür. Bei vier schreibenden Bounded Contexts ist ohne Provenance je Wert nicht mehr feststellbar, woher eine Angabe stammt. Unter ADR-002 war das ein geplanter v1.2-Baustein; unter diesem Vorschlag ist es Voraussetzung. **Das ist die Anforderung Nachvollziehbarkeit in ihrer direktesten Form.** → #142"

Das Team hat ADR-003 am 10.08.2026 **einschließlich dieser Konsequenz** angenommen. Zur Debatte steht hier also nicht mehr das Ob, sondern die Ausgestaltung: welche Angaben, in welcher Form, mit welcher Verbindlichkeit. Wer den Vorschlag ablehnt, lehnt nicht eine neue Idee ab, sondern nimmt eine bereits beschlossene Voraussetzung zurück — was zulässig ist, aber ausdrücklich geschehen sollte.

## 1. Ausgangslage

Am 10. August hat das Team **ADR-003** angenommen: Die PostgreSQL-Datenbank ist Single Source of Truth. Alle Bounded Contexts lesen alles, schreiben additiv in ihr eigenes Schema, überschreiben nie BC0-Daten, und führen die von BC0 vergebenen IDs mit. Es gibt keinen Nachrichtenkanal zurück — **die Datenbank ist der Kanal**.

Seitdem ist die technische Seite fertig: Vier Datenbankrollen mit eigenem Schema (`bc1_role` bis `bc4_role`), die Zugänge sind am 12. und 17. August verteilt — BC1 Richard, BC2 Sergio, BC3 Sabrina, BC4 Mehdi. Das Entitätenregister aus ADR-004 steht produktiv, die Datenbankdokumentation liegt in Google Drive und im Repository.

**Was ADR-003 nicht regelt, ist zweierlei:** ob überhaupt geschrieben wird, und woher ein geschriebener Wert stammt.

---

## 2. Das Problem in einem Beispiel

BC1 trägt für einen Teilprozess ein: **Dauer 20 Minuten**. Die Datenbank weiß, dass `bc1_role` geschrieben hat. Woher die 20 kommen, weiß sie nicht:

- aus dem Interview mit dem Prozesseigner, der gesagt hat „so zwanzig Minuten"
- aus einem Auszug des Ticketsystems, gemessen über drei Monate
- aus einer Modellschätzung, die aus „dauert nicht lang" eine Zahl gemacht hat

In allen drei Fällen steht dieselbe Rolle dahinter. Für BC2, das damit eine Wirtschaftlichkeit rechnet, ist der Unterschied **alles** — im ersten Fall eine Näherung, im zweiten eine Messung, im dritten eine Vermutung mit Nachkommastelle.

Die Datenbankrolle beantwortet, **welches System** geschrieben hat. Sie beantwortet nicht, **worauf der Wert beruht**.

> **Der zweite Teil des Problems ist banaler und größer:** Ein Ergebnis, das gar nicht erst in die Datenbank geschrieben wird, hat auch keine Herkunft. Ein BC3-Prozessentwurf, der nur im Entwurfswerkzeug liegt, ist für die Kette verloren — ohne dass jemand gegen ADR-003 verstoßen hätte, denn ADR-003 sagt nur, *wie* geschrieben wird, nicht *dass*.

---

## 3. Entscheidung

Drei Regeln, aufeinander aufbauend.

### R1 — Ergebnispflicht

**Was ein Bounded Context erarbeitet, steht in PostgreSQL.** Nicht im eigenen Werkzeug, nicht in einer Datei, nicht im Chatverlauf.

**Ein Ergebnis ist**, worauf ein anderer Kontext aufbaut oder was in eine Empfehlung eingeht. Das rohe Interviewprotokoll ist kein Ergebnis — die daraus abgeleiteten Werte sind es. Ein Zwischenstand einer laufenden Bearbeitung ist keiner; das Resultat schon.

Diese Abgrenzung ist bewusst eng gehalten: Eine Ablagepflicht für Arbeitsmaterial würde niemand einhalten, und eine Regel, an die sich keiner hält, ist schlechter als keine.

### R2 — Herkunft je Wert

Zu jedem geschriebenen Ergebnis gehören **vier Angaben**:

| Angabe | beantwortet |
|---|---|
| **wer** | welche Rolle oder Person hat geschrieben |
| **wann** | Zeitstempel |
| **woher** | worauf beruht der Wert — Interview, Systemauszug, Dokument, Modellvorschlag |
| **wie belastbar** | Messung, begründete Schätzung, Vermutung — beziehungsweise der jeweils passende Reifebegriff |

Die **Spalten sind verbindlich, die Werteliste der vierten ist es nicht.** „belegt / geschätzt / geraten" passt für Zahlen aus BC0 und BC1; für einen BC3-Prozessentwurf wäre „Skizze / geprüft / abgenommen" sinnvoller. Jeder Kontext legt seine Werteliste selbst fest — mit **einer Mindestanforderung**:

> **Es muss erkennbar sein, ob ein Mensch den Wert geprüft hat oder eine Maschine ihn vorgeschlagen hat.**

Das ist die Unterscheidung, die bei der Beleg-Ingestion Stufe 3 ([#140](https://github.com/pg-coe-kmu/coe-factory/issues/140)) den Ausschlag gibt: Dort ordnet ein Sprachmodell Belege automatisch zu, und die Datenbankrolle wäre dieselbe wie bei einer Zuordnung von Hand.

### R3 — Kein Eingriff ohne Spur

**Änderungen am Datenbestand laufen über die Anwendungen und Schnittstellen, nicht über die Konsole.** Ein Wert, den jemand von Hand mit `psql` setzt, trägt keine Herkunft — und macht damit alles wertlos, was R2 leistet. Wer von Hand eingreifen muss, weil ein Fehler anders nicht zu beheben ist, hält das fest.

Das ist keine Misstrauensregel, sondern eine Rechenregel: Bei vier schreibenden Kontexten genügt **ein** stiller Eingriff, damit niemand mehr sagen kann, ob ein Wert nachvollziehbar ist.

---

## 4. Was das *nicht* heißt

**Niemand bekommt vorgeschrieben, wie er arbeitet.** BC0 sagt nicht, wie Richard sein Interview führt, wie Sergio rechnet, wie Sabrina entwirft oder wie Mehdi baut. Geregelt wird ausschließlich, **wie das Ergebnis abgelegt wird**.

Es ist dasselbe Prinzip wie bei den Prozess-IDs: Was jemand mit `KP-02.TP-4` macht, ist seine Sache — dass alle dieselbe Kennung verwenden, ist gemeinsame Sache, sonst passt nichts zusammen.

**BC0 bekommt keine Sonderrolle und betreibt keinen Dienst.** Jeder schreibt weiter ausschließlich in sein eigenes Schema. Gemeinsam ist nur das Format.

---

## 5. Warum BC0 das vorschlägt

Nicht aus Zuständigkeit, sondern weil BC0 es hat. Der Herkunftsnachweis läuft dort seit Wochen produktiv:

| Wo | Was es festhält |
|---|---|
| `bitkom_bewertungen.bewerter`, `.bewertet_am` | wer, wann |
| `bitkom_bewertungen.quelle`, `.beleg` | worauf gestützt — **erzwungen**, eine Bewertung ohne Begründung nimmt die Datenbank nicht an |
| `bewertung_belege` → `beleg_dokumente` | welches Dokument trägt welche Bewertung |
| `ref_erhebungen`, `erhebung_id` im Primärschlüssel | zu welchem Messzeitpunkt gehört der Wert |
| `gate_pruefpunkt_werte.guete` | wie belastbar — belegt, geschätzt, geraten, entfällt |
| `gate_ereignisse.erhebung_id`, `.bc1_profil_stand` | auf welchem Datenstand wurde freigegeben |

**Nachweis, dass es trägt:** 600 Bewertungen, Belegquote 100 %, über zwei Schemastände hinweg migriert, ohne dass ein Wert seine Herkunft verloren hätte.

Die vierte Angabe — die Belastbarkeit — ist die jüngste und in unserem Zusammenhang die wichtigste. Klassische Herkunftsführung sagt, *woher* ein Wert kommt. Für eine Wirtschaftlichkeitsrechnung ist entscheidender, *wie belastbar* er ist: Eine gemessene und eine geratene Dauer haben dieselbe Herkunft und völlig unterschiedliches Gewicht.

---

## 6. Was jeder Kontext konkret tun müsste

| Kontext | Aufwand |
|---|---|
| **BC0** — Simeon | keiner, läuft. Stellt das Format und ein Beispiel bereit |
| **BC1** — Richard | vier Spalten in den Tabellen des Schemas `bc1`. Der Confidence-Report deckt das Meiste schon ab; `duration_confidence_pct` (30/70/95) ist bereits die Belastbarkeitsangabe und braucht nur einen festen Ort |
| **BC2** — Sergio | schreibt Ergebnisse, keine Erhebungen. Für ihn zählt vor allem die Leserichtung: Er *bekommt* die Belastbarkeit von BC0 und BC1 und entscheidet daraufhin, ob er einen Punktwert oder eine Bandbreite rechnet |
| **BC3** — Sabrina | vier Spalten je Artefakttabelle. Eigene Werteliste für die Belastbarkeit, Vorschlag: Entwurfsstand |
| **BC4** — Mehdi | dito, plus die Angabe, welcher Teil generiert und welcher geprüft wurde — bei automatisiert erzeugten Artefakten ist genau das die Frage |

---

## 7. Die Gegenposition

Sie ist ernst zu nehmen: **Jeder führt Herkunft, wie er will.**

Dafür spricht: keine Abstimmung nötig, jeder kommt sofort weiter, niemand wird durch die Formatänderungen der anderen gebunden. Bei vier Beteiligten mit unterschiedlichem Reifegrad ist das kein schwaches Argument.

Dagegen spricht die Frage, die am Ende der Kette gestellt wird: **„Worauf beruht diese Empfehlung?"** Sie geht von der BC2-Rechnung über die BC1-Angaben bis zur BC0-Bewertung zurück. Mit vier Formaten ist das Handarbeit, und in einer Prüfungssituation wird aus der Nachvollziehbarkeit eine Behauptung.

Die Projektvorgabe lautet Reproduzierbarkeit, Transparenz und Nachvollziehbarkeit. ADR-003 wurde genau damit begründet. R1 bis R3 sind die Fortsetzung derselben Linie — ohne sie bleibt ADR-003 auf halbem Weg stehen.

---

## 8. Zu entscheiden

| | |
|---|---|
| **Frage** | Gelten R1, R2 und R3 für alle Bounded Contexts? |
| **Wenn ja** | Jeder Kontext legt bis zum **01.09.2026** seine vier Spalten und seine Werteliste fest und meldet sie zurück. BC0 trägt sie in die Datenbankdokumentation ein. |
| **Wenn nein** | [#142](https://github.com/pg-coe-kmu/coe-factory/issues/142) wird als „bewusst nicht geregelt" geschlossen, mit Begründung. Dann sollte in der Abschlussdokumentation stehen, dass die Herkunft über Kontextgrenzen hinweg nicht durchgängig nachvollziehbar ist. |
| **Offen bleibt in jedem Fall** | die zentrale LLM-Grenze ([#150](https://github.com/pg-coe-kmu/coe-factory/issues/150)). R2 verlangt, dass Modellvorschläge als solche erkennbar sind — durchsetzbar ist das nur, wenn klar ist, wo Modelle überhaupt aufgerufen werden. |

---

*Simeon Ehmer · BC0 Baseline und Reifegrad · PG KI-CoE-KMU · 17.08.2026*

---

## Nachtrag 01.09.2026 — angenommen

**R1, R2 und R3 gelten für alle Bounded Contexts.**

**Angenommen von den im Team-Meeting Anwesenden.** Die nicht Erschienenen waren unentschuldigt und
tragen die Entscheidung mit. Festgehalten am 01.09.2026 durch Simeon Ehmer (BC0).

Damit ist [#142](https://github.com/pg-coe-kmu/coe-factory/issues/142) entschieden — das
Arbeitspaket lief seit dem 06.08. und hatte den 21.08. als Frist.

### Was daraus jetzt folgt

Abschnitt 8 nennt die Folge für den Fall „ja", und sie tritt ein:

> **Jeder Kontext legt seine vier Spalten und seine Werteliste fest und meldet sie zurück.
> BC0 trägt sie in die Datenbankdokumentation ein.**

| Kontext | was zu melden ist |
|---|---|
| **BC0** — Simeon | nichts zu tun, läuft. Stellt Format und Beispiel |
| **BC1** — Richard | vier Spalten in den Tabellen des Schemas `bc1`. `duration_confidence_pct` (30/70/95) ist die Belastbarkeitsangabe und braucht nur einen festen Ort |
| **BC2** — Sergio | schreibt Ergebnisse, keine Erhebungen. Für ihn zählt die Leserichtung: Er *bekommt* die Belastbarkeit und entscheidet daraufhin, ob er einen Punktwert oder eine Bandbreite rechnet |
| **BC3** — Sabrina | vier Spalten je Artefakttabelle, eigene Werteliste (Vorschlag: Entwurfsstand) |
| **BC4** — Mehdi | dito, plus die Angabe, **welcher Teil generiert und welcher geprüft** wurde |

**Die Mindestanforderung aus R2 bleibt der harte Kern:**

> Es muss erkennbar sein, ob ein Mensch den Wert geprüft hat oder eine Maschine ihn
> vorgeschlagen hat.

### Der eine Punkt, der offen bleibt — und er ist dringlicher geworden

Abschnitt 8 hält fest, dass die zentrale LLM-Grenze
([#150](https://github.com/pg-coe-kmu/coe-factory/issues/150)) „in jedem Fall offen bleibt".
**Am 01.09.2026 ist sie keine offene Frage mehr, sondern eine laufende Entwicklung:** Im
Repository stehen die Zweige `bc1-gemini-adapter` und `bc1-ollama-adapter`.

Das berührt R2 unmittelbar. Die Mindestanforderung ist nur durchsetzbar, wenn feststeht, **wo**
Modelle aufgerufen werden. Werden sie in jedem Kontext einzeln angebunden, bleibt R2 eine
Vereinbarung; läuft der Zugang zentral, ist sie erzwingbar.

**R2 ist beschlossen, seine Durchsetzbarkeit ist es nicht.** #150 gehört deshalb auf den 07.09.

### Wie BC0 es hält — als Beleg, nicht als Forderung

R1 bis R3 sind für BC0 kein Vorhaben, sondern der Bestand. Zwei Beispiele vom 27. und 28.08.:

- **`zuordnung_quelle` an `ref_anfragen`** unterscheidet vier Herkünfte, darunter ausdrücklich
  `vorschlag_bc0` (regelbasiert, ohne Modell) und `vorschlag_bc1` (semantisch, mit Modell).
  **Getrennt genau deshalb, weil bei einer Fehlzuordnung sonst nicht erkennbar wäre, ob die Regel
  zu grob war oder das Modell danebenlag** — zwei Ursachen, zwei Reparaturen. Das ist R2, auf einen
  einzelnen Wert angewandt.
- **`ck_anfrage_bezug_paarweise`** erzwingt, dass ein Prozessbezug **und** seine Herkunftsangabe
  nur gemeinsam existieren. Ein Bezug ohne Herkunft ist nach R2 nicht verwendbar — die Datenbank
  lässt ihn deshalb gar nicht erst entstehen.

**Das ist zugleich die Antwort auf den Einwand, R2 sei teuer.** Es sind vier Spalten und die
Bereitschaft, eine Maschinenzuordnung als solche zu kennzeichnen.
