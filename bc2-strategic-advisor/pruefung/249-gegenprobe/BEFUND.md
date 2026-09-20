# Gegenprobe zu #249 — gilt die Feldauflösung aus #194 an der laufenden Datenbank?

**Gemessen am 21.09.2026** gegen die laufende Postgres (Supabase, Session-Pooler 5432),
Rolle `bc2_role`, ausgeführt im Betriebscontainer auf `bc2.02da.de` — die Zugangsdaten
haben den Server nicht verlassen (ADR-003).

**Vergleichsmaßstab:** BC0s Snapshot v3 vom 27.08.2026, gemessen in #194 durch
`packen.py:aufloesung_messen()`. Die dortigen Zahlen wurden vor der Gegenprobe
reproduziert und stimmen mit dem Ticketkopf überein.

> **Kurz:** Die Feldauflösung gilt unverändert — jede einzelne Zahl. Die Belegtext-Wiederholung
> gilt ebenfalls. **Ein Befund fällt:** die „27 Teilprozesse mit `avg: 0`" sind ein
> Artefakt des Snapshot-Exports, nicht der Datenbank. **Und zwei Funde kamen dazu,
> die keiner der drei Fragen galten** — die echten Pakete sind winzig, und der
> BC1-Vertrag bricht an der laufenden Datenbank.

---

## 1 · Feldauflösung — **bestätigt, jede Zahl**

Bei wie vielen der zehn Kernprozesse ist ein Feld über *alle* Teilprozesse wortgleich:

| Feld | Snapshot v3 (#194) | **laufende DB** | mit `aktiv`-Filter |
|---|---|---|---|
| `tools` | 10 von 10 | **10 von 10** | 10 von 10 |
| `medienbrueche` | 10 von 10 | **10 von 10** | 10 von 10 |
| `api` | 10 von 10 | **10 von 10** | 10 von 10 |
| `schnittstellen` | 7 von 10 | **7 von 10** | 7 von 10 |
| `notation` | 4 von 10 | **4 von 10** | 4 von 10 |
| `sub_process_name` | 0 von 10 | **0 von 10** | 0 von 10 |

Keine Abweichung. NoroAI hat weiterhin 10 Kernprozesse zu je 5 Teilprozessen (50),
**alle aktiv** — der Filter, den `v_bewertung_aktuell` seit Schema v3.4 anlegt, ändert
hier nichts, weil nichts deaktiviert ist. Kein Kernprozess ist ein entarteter Fall:
die Wiederholung wird überall über mindestens zwei Geschwister gemessen.

**Der Snapshot war in diesem Punkt also kein veralteter Stand, sondern ein zutreffender.**

## 2 · Belegtexte — **bestätigt, und schärfer als im Ticket**

Gelesen über `v_bewertung_aktuell`, nicht über `bitkom_bewertungen` — der Unterschied,
den #249 ausdrücklich verlangt. Er ändert nichts:

| Kernprozess | bewertete TP | Items | mit identischem Beleg |
|---|---|---|---|
| KP-01 | 5 | 30 | **30** |
| KP-02 | 5 | 30 | **30** |
| KP-03 | 5 | 30 | **30** |
| KP-04 | 5 | 30 | **30** |
| KP-05 | 1 | 30 | 30 *(ein TP, trivial)* |
| KP-06 | 2 | 30 | **30** |

Bei allen fünf Kernprozessen mit mehr als einem bewerteten Teilprozess tragen **alle
30 Bitkom-Items über sämtliche Teilprozesse denselben Belegtext**.

Der #194-Befund „die Stufen unterscheiden sich, die Begründung nicht" lässt sich jetzt
beziffern. Bei KP-01 tragen **18 von 30 Items verschiedene Stufen bei identischem Beleg**:

```
Item 4 · Stufen  TP-1: 1 | TP-2: 2 | TP-3: 2 | TP-4: 2 | TP-5: 2
         Beleg für alle fünf: „Menschenzentrierter Klausur-Prozess"

Item 7 · Stufen  TP-1: 2 | TP-2: 3 | TP-3: 3 | TP-4: 2 | TP-5: 2
         Beleg für alle fünf: „Klausur-Protokolle als strukturierte Logs"
```

Eine 1 und eine 2 stützen sich auf denselben Satz. Für BC2 heißt das: **der Beleg trägt
keine teilprozess-eigene Information** und darf einem Modellaufruf nicht als solche
angeboten werden — genau die Verwechslung, an der Schnitt A in #194 zerbrach.

## 3 · „27 Teilprozesse mit `avg: 0`" — **widerlegt für den Leseweg, den BC2 benutzt**

| | Snapshot v3 | laufende DB |
|---|---|---|
| Teilprozesse ohne jede Bewertung | 27 von 50 | **27 von 50** ✅ |
| davon in der Automatisierungssicht mit 0 geführt | **27** | **0** ❌ |

Die Lücke selbst ist unverändert: 27 der 50 Teilprozesse tragen keine einzige Bewertung.
**Aber sie erscheinen in `v_prozessautomatisierung` gar nicht.** Die View hat genau
23 Zeilen — die 23 bewerteten Teilprozesse — und keine einzige Zeile mit einer 0:

```sql
 SELECT company_id, sub_process_id, "left"(sub_process_id::text, 5) AS process_id,
        round(avg(stufe) FILTER (WHERE item_nr = ANY (ARRAY[1, 2])), 2) AS technologiebasis,
        ...
   FROM v_bewertung_aktuell b
  GROUP BY company_id, sub_process_id;
```

Ein `GROUP BY` über die Bewertungen kann einen unbewerteten Teilprozess nicht erzeugen.
Die Nullen entstehen **erst im Snapshot-Export**, der die Matrix über alle Teilprozesse
aufspannt und Fehlendes auffüllt.

**Folge für die Auflage an #248.** Sie lautete: die Oberflächen-Regel aus #167
(*„fehlende Daten: Etikett statt Zahl, nie eine 0"*) müsse schon beim **Lesen** greifen.
Für den Produktionsweg — direkt gegen Postgres, wie in #158 festgelegt — ist das
gegenstandslos: dort gibt es die Null nicht. **Für die Test-Fixture gilt sie weiter,
und dort wiegt sie schwerer**: wer gegen den Snapshot testet, prüft sein Leseverhalten
gegen eine Datenlage, die im Betrieb nicht vorkommt. Ein Test, der die 0 korrekt als
Lücke behandelt, belegt nichts über den echten Weg; einer, der an ihr scheitert, meldet
einen Fehler, den es nicht gibt.

## 4 · BC1s Profile — **drei statt einem, aber die Frage war falsch gestellt**

`bc1.prozessprofil` trägt 6 Zeilen, daraus nach der vertraglichen Leseregel
(jüngste `profil_version` mit `status='fertig'`) **drei gültige Profile**:

| Fokus-Schritt | Version | `frequency_per_year` | `focus_step_duration_minutes` | Herkunft |
|---|---|---|---|---|
| KP-05.TP-1 | v2 | 260 | 25 | `geschaetzt` |
| KP-06.TP-1 | v2 | 40 | 60 | `geschaetzt` |
| KP-06.TP-2 | v2 | 180 | 90 | `geschaetzt` |

In #194 war KP-06.TP-2 „der einzige mit einem BC1-Profil" — es sind jetzt drei.
**Alle drei tragen `geschaetzt`**, also die breiteste Bandbreite nach ADR-006 (±40 %).

Die Ticketfrage lautete, *wie viele der freigegebenen Teilprozesse eines echten Pakets
ein Profil tragen*. Die Antwort ist **1 von 1 — und damit keine Antwort**, weil die
Grundgesamtheit eins ist. Warum, steht im nächsten Abschnitt.

---

## Zwei Funde außerhalb der drei Fragen

### A · Die echten Pakete sind winzig — #194 hat mit einem 16er-Paket gemessen

Alle jemals geschnürten Pakete, über beide Mandanten:

| übergeben am | Mandant | Teilprozesse | Kernprozesse |
|---|---|---|---|
| 2026-09-04 05:12 | Übungsmandant (Demo) | 2 | 1 |
| 2026-09-18 07:55 | NoroAI Consulting GmbH | **1** | 1 |
| 2026-09-18 08:05 | NoroAI Consulting GmbH | **1** | 1 |

Gate 0 hat bei NoroAI **genau einen** Teilprozess freigegeben (KP-05.TP-1).

Der Prototyp aus #194 lief auf einem **frei gewählten** Paket von 16 Teilprozessen über
vier Kernprozesse — zulässig und im LIESMICH offengelegt, weil der Snapshot keine Pakete
kennt. Gegen die Wirklichkeit gehalten heißt das:

- **Die Entscheidung für Schnitt C bleibt richtig, ist heute aber nicht messbar.**
  Bei einem Kernprozess je Paket fallen B und C zusammen; bei einem Teilprozess fallen
  A, B und C zusammen. An keinem real existierenden Paket lassen sich die drei Schnitte
  unterscheiden.
- **Auflage 1 aus #194 ist vorerst gegenstandslos.** Die Nutzlast-Obergrenze und das
  Ausweichen auf Schnitt B waren gegen 80.431 Zeichen bemessen; ein Ein-Teilprozess-Paket
  liegt bei rund einem Fünfzigstel. Die Auflage bleibt richtig, ihre Dringlichkeit
  für #248 ist es nicht.
- **Der Befund gegen Schnitt A hält unabhängig davon** — dass Doppelzählung eine Aussage
  über ein Paar ist und in Schnitt A kein Aufruf beide Hälften sieht, ist strukturell
  und hängt an keiner Paketgröße. Das hatte #249 richtig vorausgesehen.

**Was daraus folgt, ist eine Frage an BC0, keine an BC2:** ob Pakete dauerhaft so klein
bleiben (dann ist die prozessübergreifende Priorisierung aus dem Ziel der Karte heute
ohne Gegenstand, weil ein Paket nie mehrere Kernprozesse trägt) oder ob das der
Aufbaustand ist. **Nicht aus dem Bestand zu erschließen** — es wäre derselbe Fehlschluss,
den die Karte dreimal verzeichnet.

### B · Der Vertrag `contracts/bc1-to-bc2/lesen.sql` bricht an der laufenden Datenbank

```
VERTRAG BRICHT: UndefinedColumn
column p.step_frequency_per_year does not exist
```

`lesen.sql` liest 20 typisierte Spalten. `bc1.prozessprofil` hat **19** — `step_frequency_per_year`
ist nicht darunter. Die Abfrage scheitert beim Parsen, also **vollständig**: BC2 bekommt
heute über den eigenen Vertragsweg *kein einziges* BC1-Profil.

Die Ursache ist dokumentiert, nur an drei Stellen verteilt:

1. **BC1 führt das Feld als JSON-Feld, nicht als Spalte.** Im Implementierungsplan steht
   D3 `step_frequency_per_year` unter den *„passiv miterfassten E-Feldern"*.
2. **BC1 hat die Schema-Ergänzung an eine Bedingung geknüpft.** Abschlussplan A1:
   *„D3 `step_frequency_per_year` ist ungebunden; BC2 entscheidet binden oder ignorieren.
   **Falls binden: Schema-Ergänzung**, der Writer bleibt (Feld liegt nur im JSON)."*
3. **BC2 hat am 20.09.2026 entschieden zu binden** (`contracts/bc1-to-bc2/README.md`,
   Invariante I8) — **die Schema-Ergänzung ist nicht erfolgt.** Die Bindung wurde
   einseitig vollzogen.

Und selbst mit Spalte trüge sie nichts: das Feld ist **in keiner der sechs Profilzeilen
befüllt**, auch nicht im JSONB (`profil ? 'step_frequency_per_year'` ist überall `false`).
Invariante I8 — *„ist das Feld gesetzt, hat es Vorrang für den Fokus-Schritt"* — ist damit
heute nicht nur unerfüllbar, sondern ihr Leseweg ist der Grund, warum gar nichts gelesen wird.

**Das ist genau die Gegenprobe, die #184 offen ließ:** *„Nicht belegt: geschnitten wurde
gegen BC1s Code, nicht gegen die laufende Datenbank — eine Gegenprobe steht aus."*
Sie ist jetzt gemacht und fällt negativ aus.

---

## Was offen bleibt

**Frage 3 des Tickets ist nicht beantwortet** und war es auch nicht zu beantworten:
ob die Wiederholung der Kernprozess-Texte bei BC0 **Erhebungsstand oder Modellentscheidung**
ist, entscheidet, ob BC2 dauerhaft damit rechnen muss. Das Ticket verlangt ausdrücklich,
es **bei Simeon zu bestätigen und nicht aus dem Bestand zu erschließen** — sonst wäre es
der vierte Fall der Fehlerform, die die Karte dreimal verzeichnet (#163, #186, #165).
Die Messung hier zeigt nur, *dass* die Wiederholung besteht, nicht *warum*.

## Grenzen dieser Messung

- **Ein Mandant trägt die Aussage.** Der Übungsmandant ist ausdrücklich als Testdaten
  gekennzeichnet und wurde nur für die Paketübersicht herangezogen.
- **Die Paket-Aussage ruht auf drei Paketen**, zwei davon vom selben Tag und mit demselben
  Inhalt. Sie belegt den Stand, nicht die Absicht — siehe Fund A.
- **Nur gelesen.** Die Sitzung lief `readonly`; kein INSERT, kein UPDATE, kein DDL.

## Nachvollziehen

```bash
# im Betriebscontainer auf bc2.02da.de, wo DATABASE_URL bereits gesetzt ist
docker cp messen.py app-app-1:/tmp/ && docker exec app-app-1 python /tmp/messen.py
docker cp vertiefen.py app-app-1:/tmp/ && docker exec app-app-1 python /tmp/vertiefen.py
```

**Die Rohausgabe liegt bewusst nicht im Repo.** Sie trägt Teilprozess- und Paket-IDs,
Belegtexte und BC1-Werte des Mandanten, und sie ist mit den beiden Skripten jederzeit
neu zu erzeugen — anders als bei #194, wo die Modellantworten nicht reproduzierbar waren
und deshalb als Primärquelle mitgingen. Was aus ihr trägt, steht oben in diesem Befund.
