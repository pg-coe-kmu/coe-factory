# [ADR-003 · Vorschlag] SSoT-Schreibmodell: alle BCs schreiben additiv in die gemeinsame Datenbank

*Ersteller: Simeon Ehmer (BC0) · Stand 07.08.2026 · Repo: `pg-coe-kmu/coe-factory` · Label: `adr`*

> **Zum Einstellen als GitHub-Issue.** Titel: `[ADR-003 · Vorschlag] SSoT-Schreibmodell: alle BCs schreiben additiv in die gemeinsame Datenbank`

---

**Status:** **Vorschlag.** Vorgabe aus BC0, eingebracht am 07.08.2026, zur Abstimmung im Team-Meeting am 10.08.2026. Bis zur Annahme durch das Team gilt ADR-002 unverändert weiter.

**Betrifft:** ADR-002 in genau einem Punkt — die Konsequenz „Konsumenten (BC1–BC4) hängen sich an die stabilen IDs, nicht an interne Spalten." Alles Übrige aus ADR-002 bliebe unverändert gültig.

---

## Leitgedanke

Prof. Dorka gibt für die Projektarbeit **Reproduzierbarkeit, Transparenz und Nachvollziehbarkeit** vor. Dieser Vorschlag leitet das Datenmodell aus dieser Vorgabe ab, nicht aus technischer Bequemlichkeit. Jede der folgenden Regeln beantwortet eine der drei Fragen:

| Anforderung | Frage, die beantwortet werden muss |
|---|---|
| **Reproduzierbarkeit** | Lässt sich ein Ergebnis von damals mit den Daten von damals erneut herleiten? |
| **Transparenz** | Ist sichtbar, welcher Bounded Context welchen Wert beigetragen hat? |
| **Nachvollziehbarkeit** | Ist zu jedem Wert belegt, woher er stammt und wann er entstand? |

Ein Datenmodell, das eine dieser drei Fragen offen lässt, erfüllt die Vorgabe nicht — unabhängig davon, wie gut es technisch funktioniert.

## Kontext

ADR-001 und ADR-002 vom 12.07.2026 gehen von einem Übergabemodell aus: BC0 liefert eine eingefrorene Baseline als Snapshot plus API-Contract, die nachgelagerten BCs entwickeln dagegen und bleiben von BC0s interner Struktur entkoppelt. Die Entscheidungsvorlage vom 21.06.2026 formuliert es ausdrücklich: „BC1 ist über den stabilen Vertrag bereits entkoppelt und arbeitsfähig."

Seither hat sich die Lage in zwei Punkten geändert.

**Erstens ist die Datenbank produktiv.** Seit dem 06.08.2026 läuft BC0 auf einer gemeinsamen, serverfähigen PostgreSQL-Instanz (Supabase, eu-west-1) mit erreichbarer Anwendung. Der ursprüngliche Grund für die Entkopplung über eine Datei — es gab keinen gemeinsamen Server — ist entfallen.

**Zweitens bauen die Bounded Contexts fachlich aufeinander auf, sie liefern nicht nacheinander ab.** Die Kette lautet:

```
BC0   Grundlagenerfassung und ID-Vergabe           legt die Zeile an
BC1   Anreicherung, Häufigkeiten, Interviewdaten    ergänzt unter derselben ID
BC2   ROI-Berechnung auf BC0- und BC1-Daten         ergänzt unter derselben ID
BC3   Architektur- und Lösungsentwurf               ergänzt unter derselben ID
BC4   Umsetzung                                     ergänzt unter derselben ID
```

Jede Stufe braucht alles Vorherige. Ein eigener Snapshot je Stufe hieße: fünf Dateiversionen, fünf Übergabetermine und bei jeder Rückfrage die Suche danach, welcher Stand wo galt. Genau das widerspricht der Vorgabe.

### Entkopplung ist ein Entwicklungsmodus, kein Betriebsmodell

Das ist der Kern der Sache, und er wird leicht übersehen.

**In der Entwicklung ist Entkopplung sinnvoll und soll erhalten bleiben.** Fünf Teams arbeiten parallel, niemand soll auf den anderen warten. Wer gegen einen Snapshot oder eine lokale Datenbank entwickelt, kommt voran, ohne dass die gemeinsame Instanz steht. Das war der richtige Weg für die vergangenen Wochen und bleibt es für Tests.

**Im Echtbetrieb gibt es keine Entkopplung.** Dort läuft die Kette **sequentiell**: Ein Mandant wird erfasst (BC0), dann im Interview angereichert (BC1), dann wird der ROI berechnet (BC2), dann die Lösung entworfen (BC3), dann umgesetzt (BC4). Jeder Schritt setzt auf dem Ergebnis des vorherigen auf — an derselben Zeile, unter derselben ID, in derselben Datenbank. Ein Snapshot dazwischen wäre kein Schutz, sondern eine Bruchstelle: Er müsste nach jedem Schritt neu erzeugt, weitergereicht und versioniert werden, und nach fünf Stufen wüsste niemand mehr, welcher Stand welchem Mandanten entspricht.

**Ausgelegt wird für den Echtbetrieb, nicht für die Entwicklungsphase.** Ein Datenmodell, das nur in der Entwicklung trägt, ist keines. Die Entkopplung bleibt als Entwicklungswerkzeug bestehen — der Snapshot verschwindet nicht — aber sie ist nicht das Zielbild.

**Zum Stand zwischen BC0 und BC1:** Die gemeinsame Datenbank ist dort bereits faktische Richtung — PR #130 bringt BC1 einen `PostgresStateStore` mit eigenem Schema `bc1` und der Aussage „Supabase ist nur ein DSN-Tausch". Für BC2 bis BC4 ist dieser Vorschlag noch nicht besprochen.

## Vorschlag

**Die PostgreSQL-Datenbank ist Single Source of Truth. Alle Bounded Contexts arbeiten direkt auf ihr — lesend uneingeschränkt, schreibend ausschließlich additiv.**

### Regel 1 — BC0-Daten werden nie überschrieben

Jeder BC schreibt ausschließlich in eigene, neue Spalten oder eigene Tabellen. Der Wert von BC0 bleibt unverändert stehen, daneben steht der Wert von BC1.

*Erfüllt Transparenz:* Beide Werte sind gleichzeitig sichtbar, der Beitrag jedes BC ist an der Spalte ablesbar.
*Erfüllt Reproduzierbarkeit:* Die Baseline, auf der eine spätere Berechnung beruhte, ist noch da.

### Regel 2 — Alle IDs kommen aus BC0 und werden von allen mitgeführt

**Die ID-Vergabe liegt vollständig bei BC0 — für Prozesse wie für Entitäten.**

**Prozess-IDs** nach ADR-002: `KP-XX` · `KP-XX.TP-Y` · `KP-XX.TP-Y.I-NN`.

**Entitäts-IDs** für jede benannte Entität — Person, Unternehmen, Tool, System, Rolle. Auch sie werden ausschließlich von BC0 vergeben (Entitäten-Register, Schema v1.2, → #149). Der Klarname bleibt in der Datenbank; nach außen und an Sprachmodelle geht ausschließlich die ID.

Alle IDs werden **nie geändert** und **nie wiederverwendet**.

**Jeder Bounded Context führt diese IDs in allen seinen Daten mit** — in jeder Spalte, jeder Tabelle, jedem Artefakt, jedem Export. Nicht als Kopie eines Namens, sondern als Fremdschlüssel auf die BC0-Zeile.

*Warum die Entitäts-IDs sinnvollerweise bei BC0 liegen und nicht bei dem, der sie zuerst braucht:*

Vorweg zur Einordnung: Keiner der folgenden Punkte ist ohne zentrale ID **unmöglich**. Alle sind mit mehr Aufwand und geringerer Verlässlichkeit auch anders lösbar. Der Vorschlag ist also eine Abwägung von Aufwand und Sicherheit, keine technische Notwendigkeit.

**Die PII-Prüfung in BC3 wird damit erheblich einfacher und verlässlicher.** Pseudonymisierung ginge auch ohne zentrales Register — etwa über deterministisches Hashing der Namen oder Entitätserkennung im Text. Mit einer gemeinsamen ID entfällt dieser Aufwand: Der Klarname bleibt intern, außen läuft die ID, und die Zuordnung ist eine Tabelle statt eines Verfahrens. Ohne gemeinsame ID müssten alle fünf Bounded Contexts dasselbe Verfahren identisch umsetzen und identisch gepflegt halten. Weicht einer ab, entstehen für dieselbe Person zwei Kennungen — und es fällt niemandem auf.

**Selektion und Auswertung werden überhaupt erst praktikabel.** Fragen wie „welche Prozesse berührt diese Person", „in wie vielen Teilprozessen steckt dieses Tool" oder „welche Systeme hängen an diesem Prozess" lassen sich über eine stabile ID direkt beantworten. Über Klarnamen scheitert es an Schreibvarianten — *Müller*, *Mueller*, *M. Müller* sind für eine Datenbank drei verschiedene Personen. Man kann das mit Textabgleich und Normalisierung auffangen, aber jedes Ergebnis bleibt eine Schätzung.

**Löschanfragen werden beantwortbar statt aufwendig.** Verlangt jemand nach DSGVO Auskunft oder Löschung, muss über alle fünf Bounded Contexts hinweg auffindbar sein, wo diese Person vorkommt. Mit einer durchgängigen Entitäts-ID ist das eine Abfrage mit belastbarem Ergebnis. Ohne sie ist es eine Textsuche über fünf Datenbestände — machbar, aber ohne Gewähr auf Vollständigkeit. Genau diese Gewähr wird bei einer Auskunft aber verlangt.

*Erfüllt alle drei Anforderungen zugleich:* Die ID ist das einzige, was einen Wert aus BC3 mit der Erhebung aus BC0 verbindet. Ohne durchgängig mitgeführte ID ist eine ROI-Zahl aus BC2 nicht mehr auf den Prozess zurückführbar, aus dem sie stammt — und damit weder nachvollziehbar noch reproduzierbar. Deshalb ist das Mitführen keine Empfehlung, sondern Bedingung.

### Regel 3 — Zwei Ablageformen unter derselben ID

Einzelwerte kommen in eigene Spalten je BC mit Präfix (`bc1_*`, `bc2_*`, …). Artefakte — mehrteilige, versionierte Ergebnisse — kommen in eigene Tabellen mit Fremdschlüssel auf die BC0-ID, etwa `bc1_prozessprofil` oder `bc4_prozessentwurf`, dort mit Version und Bezug auf den zugrunde liegenden Bewertungsstand.

*Erfüllt Reproduzierbarkeit:* Ein Artefakt trägt, auf welchem Stand es beruht. Ändert sich die Baseline später, bleibt nachvollziehbar, womit gerechnet wurde.

### Regel 4 — Der Transportweg ist frei, die Regeln nicht

Ob ein BC direkt gegen die Datenbank schreibt oder über eine eigene Schnittstelle, ist ihm überlassen; ebenso, wo er zwischenspeichert. Verbindlich sind Zielstruktur, Pflichtfelder und Rechte — und diese werden **in der Datenbank** durchgesetzt (`NOT NULL`, `CHECK`, `GRANT`, Trigger), nicht im Weg dorthin.

*Begründung:* Nur so gilt dieselbe Regel für beide Wege. Stünden die Regeln in einer Schnittstelle, wäre der direkte Weg ein Loch daneben.

## Konsequenzen, falls angenommen

**Das Schema würde zur Schnittstelle zwischen den BCs.** Es wäre nicht mehr eine interne Angelegenheit von BC0, sondern der Vertrag selbst. Daraus folgte: Änderungen nur additiv, Versionierung verbindlich, Ankündigungsregel für Erweiterungen, definiertes Verfahren für Breaking Changes. *Das dient der Nachvollziehbarkeit — wer wissen will, was gilt, liest eine Datei statt vier Dokumente.*

**Der API-Contract v1 verlöre seine entkoppelnde Funktion.** Er bliebe gültig als Beschreibung des Lesepfads und der ID-Formate, wäre aber nicht mehr die Grenze, hinter der BC0s Struktur verborgen bleibt.

**Der Snapshot bliebe, mit geänderter Rolle.** Weiterhin nützlich als eingefrorener Stand für Präsentationen und für Entwicklung ohne DB-Zugang — *und gerade für Reproduzierbarkeit wertvoll, weil er einen datierten Stand konserviert.* Er wäre nicht mehr der Übergabemechanismus.

**Rechte müssten technisch erzwungen werden, nicht vereinbart.** Vor dem ersten schreibenden Zugriff eines zweiten BC: eigene DB-Rolle je BC, eigenes Schema für BC-eigene Arbeitsdaten, Leserecht auf die Baseline, spaltenbezogene `GRANT UPDATE` für Anreicherungen. Eine Absprache genügt nicht — ein Fehler in einem BC darf BC0-Werte physisch nicht überschreiben können. → #148, plus DB-Zugang BC1 als vorgezogener Leseteil.

**Herkunftsnachweis würde Pflicht statt Kür.** Bei vier schreibenden Bounded Contexts ist ohne Provenance je Wert nicht mehr feststellbar, woher eine Angabe stammt. Unter ADR-002 war das ein geplanter v1.2-Baustein; unter diesem Vorschlag ist es Voraussetzung. *Das ist die Anforderung Nachvollziehbarkeit in ihrer direktesten Form.* → #142, Frist 21.08.2026.

**Änderungshistorie ebenso.** Reproduzierbarkeit heißt, einen früheren Stand rekonstruieren zu können, nicht nur den aktuellen zu sehen. Append-only Historie mit Zeitstempel und Urheber, generisch statt spaltenweise, damit jede künftig ergänzte Spalte automatisch mitprotokolliert wird. → R9 in #148.

**Für BC1 konkret:** Das Ergebnis eines Interviews gehörte unter der BC0-ID in die gemeinsame Datenbank, nicht in einen Payload an eine Transportschicht. Die Zielstruktur gäbe BC0 vor. Der Interviewverlauf selbst (Sitzungen, Message-IDs, Wiederaufsetzen) bliebe BC1s Sache und gehörte in dessen eigenes Schema. Ein Vertrag `contracts/bc1-to-bc2/` *würde* damit gegenstandslos — beide läsen dieselben Daten.

**Ein Konsument, der bei unbekannten Feldern abbricht, wäre mit diesem Modell unverträglich.** Additive Erweiterung heißt, dass Felder dazukommen. Lesende Komponenten müssten unbekannte Felder ignorieren statt zu scheitern (`additionalProperties` nicht auf `false`). Betrifft aktuell `bc1_service/snapshot_schema.json`.

## Alternativen

**Beim Snapshot-/Contract-Modell bleiben.** Maximale Entkopplung, aber jede Stufe braucht eine eigene Freeze-Version, und die Zusammenführung von BC0- und BC1-Daten fände außerhalb der Datenbank statt. Vor allem: Es löst ein Entwicklungsproblem und schafft ein Betriebsproblem — im Echtbetrieb läuft die Kette sequentiell, dort ist ein Freeze je Stufe eine Bruchstelle statt eines Schutzes (siehe Kontext).

Der Einwand liegt nahe, dass die Prozess-ID doch genau dafür da ist. Sie ist es — aber eine ID verbindet nur dann zuverlässig, wenn jemand die Verbindung **durchsetzt**. In einer Datenbank tut das der Fremdschlüssel: Ein Datensatz, der auf eine nicht existierende ID zeigt, wird abgewiesen. Beim Zusammenführen zweier Dateien gibt es diese Instanz nicht. Ein Join über nicht passende IDs liefert dort kein Fehlersignal, sondern ein leeres Ergebnis — und das sieht aus wie „keine Daten vorhanden", nicht wie „Fehler".

Das ist kein theoretisches Risiko. Am 07.08.2026 zeigte die Prüfung der ID-Formate genau diesen Fall: Die Mockdaten in `06_Mockdata_BC1_to_BC2/` führen `KP-01.TP-01`, die Datenbank führt `KP-01.TP-1`. Wer beides über die Teilprozess-ID verbindet, erhält null Treffer, ohne Fehlermeldung. Der Fehler lag seit Wochen unbemerkt in den Übergabedaten.

**Schreibzugriff nur über eine BC0-API.** BC0 wäre alleiniger Schreiber und könnte jede Regel selbst prüfen. Nachteil: BC0 würde zum Engpass für vier Teams — und dieselben Regeln lassen sich in der Datenbank durchsetzen, wo sie dann für jeden Weg gelten, auch für eine API.

**Je BC eine eigene Datenbank mit Synchronisation.** Maximale Autonomie. Nachteil: Synchronisation zwischen fünf Datenbanken ist aufwendiger als das Problem, das sie löst, und die Frage „welcher Stand gilt" stellte sich dadurch erst recht.

## Was aus ADR-002 unverändert gälte

- `BC0_Onboarding_DB_Schema_v1.1.sql` ist verbindlich für alle BCs — durch diesen Vorschlag sogar verbindlicher, weil das Schema dann der Vertrag wäre. Aktueller Stand: **v1.1.1** vom 07.08.2026 (Nachtrag `beleg_dokumente`, `bewertung_belege`).
- Stabile IDs `KP-XX` · `KP-XX.TP-Y` · `KP-XX.TP-Y.I-NN` als gemeinsamer Anker.
- Beleg-Pflicht hart über `NOT NULL` + `CHECK`.
- Mandantenfähigkeit über `company_id`, Row-Level-Security empfohlen.
- Änderungen nur additiv und versioniert.

## Zu klären

- Abstimmung im Team-Meeting am 10.08.2026
- Zielstruktur für `bc1_prozessprofil` — BC0 gäbe sie vor
- Entitäten-Register: Reichweite (nur Personen und Unternehmen, oder auch Tools und Systeme) — #149
- LLM-Grenze: Wenn nach außen nur IDs gehen sollen, muss der Filter vor dem LLM-Zugriff sitzen, nicht in den einzelnen Adaptern — #150
- Enrichment-/Provenance-Layer: zentral in BC0 oder je BC — #142, Frist 21.08.2026
- Skalierung des Spaltenmodells beobachten: bei spürbarer Spaltenzahl JSONB je BC oder Attributtabelle prüfen (beide erhalten die Spaltenhoheit)
