# ADR-007 — Die Rückrichtung BC2 → BC3: Übergabe, Reject und Fassungen

**Status:** Entwurf · 20.09.2026
**Bezug:** [#188](https://github.com/pg-coe-kmu/coe-factory/issues/188) Rückrichtung BC2 → BC3 · Karte [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158)
**Ergänzt:** [#165](https://github.com/pg-coe-kmu/coe-factory/issues/165), das die Hinrichtung BC0 → BC2 festgelegt hat
**Baut auf:** ADR-005 · BC2 (der Analyselauf ist das Paket), ADR-003 (Schreibmodell), ADR-002 (stabile IDs als Vertrag)

---

## 1. Kontext

Die **Hinrichtung** ist seit dem 09.09.2026 entschieden und läuft nachweislich: BC0 stößt BC2 nach
der Gate-0-Freigabe per REST-Ruf an, die Nutzlast trägt `company_id`, `paket_id` und
`uebergeben_am`. Die **Rückrichtung** kam im Gruppenmeeting vom 07.09.2026 nicht zur Sprache.

Damit standen vier Dinge offen, und drei davon hängen an derselben Frage:

| Offen | Warum es zählt |
|---|---|
| Wie erfährt BC3, dass ein Ergebnis vorliegt? | Die Übergabe ist als **Datei** festgelegt (`konzept_ref.source_file` ist Pflicht) — es gibt keinen Statuskanal, und von Schema `bc2` weiß BC3 nichts. |
| Was geschieht bei Reject an Gate 1? | Der Vertrag kennt `gate1.status = rejected`, aber keine Folge daraus. |
| Was geschieht bei einer Nacherhebung in BC0? | Ein übergebenes Konzept beruft sich auf Zahlen, die sich danach ändern können. |
| Braucht Gate 0 einen Nachbesserungspfad? | Gate 0 läuft bewusst einweg. |

Die vierte Frage ist **auswärts beantwortet** und gehört nicht hierher: Simeon hat am 20.09.2026 in
[#234](https://github.com/pg-coe-kmu/coe-factory/issues/234) festgehalten, dass BC2 nie auf ein
abgelehntes Paket wartet, weil BC2 ohnehin nur bekommt, was BC0 freigegeben hat. Was an Gate 0
danach mit dem zurückgewiesenen Teilprozess geschieht, ist BC0s Zustandsmodell.

Zwei Messbefunde aus dem Vertrag v2.0 setzen den Rahmen:

| Befund | Quelle |
|---|---|
| `gate1` ist Pflichtfeld im **Konzept**, also je Kernprozess | `konzept.schema.json` Z. 15, 297–306 |
| `priorisierung.schema.json` trägt **keinen** Gate-1-Block, kein `company_id`, kein `paket_id` | `priorisierung.schema.json` |

Das widerspricht dem Glossar, das Gate 1 als „Entscheidung des Menschen über die **Priorisierung**
… Abschluss eines Analyselaufs und die Übergabe an BC3" führt. Es wird also an einer Stelle
entschieden und an einer anderen protokolliert.

## 2. Entscheidung

### 2.1 Die Übergabeeinheit ist der Lauf, nicht das einzelne Konzept

Übergeben wird ein **Analyselauf** `(company_id, paket_id)` als Ganzes: eine Priorisierung und ihre
*n* Konzepte, ein Ereignis. `gate1` wandert aus dem Konzept in die **Priorisierung** — eine
brechende Änderung, die in [#187](https://github.com/pg-coe-kmu/coe-factory/issues/187) mit v3.0
geschnitten wird. Das Konzept behält seinen fachlichen Bezug (`kp_id`), aber keinen eigenen
Gate-Status.

Die **Teilfreigabe** bleibt erhalten: `gate1.approved_potenzial_ids` ist weiterhin eine Teilmenge.
Nicht freigegebene Potenziale bleiben im Konzept sichtbar und als nicht freigegeben markiert — sonst
erklärt die Priorisierung ihre eigenen Lücken nicht mehr.

### 2.2 BC3 zieht, BC2 schiebt nicht

BC3 **beobachtet den Lieferordner und zieht selbst** — mündlich von BC3 bestätigt (ca. 06.09.2026;
schriftlich ist es im Tracker nirgends festgehalten, siehe Abschnitt 5).

Ablage: `contracts/bc2-to-bc3/lieferungen/<company>-<paket_id>-f<n>/` im Repo, mit den *n*
Konzepten, der Priorisierung und der Nachricht an BC3 — der Aufbau der Lieferung vom 30.08.2026,
nur maschinell erzeugt und maschinell benannt. **Das Datum trägt keine Identität** (zwei Läufe am
selben Tag sind möglich), die `paket_id` schon. Der Google Drive bleibt Spiegel, nicht Quelle.

Die Lieferung landet **per Pull Request**, nicht direkt auf `main`. Atomarität löst Git ohnehin —
BC3 sieht über `git pull` nie einen halb geschriebenen Ordner. Was der PR zusätzlich bringt, ist
das Netz gegen eine schema-ungültige Lieferung: eine kaputte Lieferung, die BC3 bereits gezogen
hat, holt niemand zurück.

### 2.3 Ein Reject liefert nichts aus und löscht nichts

Bei `gate1.status = rejected` geht **nichts** in den Lieferordner — dieser Ordner ist BC3s Eingang,
und was dort liegt, gilt als übergeben. Der abgelehnte Lauf bleibt mit seiner Begründung stehen.
Ein erneuter Lauf über dasselbe Paket erzeugt eine **neue Fassung**; die alte bleibt abrufbar.

Das ist dasselbe Muster, das [#172](https://github.com/pg-coe-kmu/coe-factory/issues/172) für den
nachgelieferten Rollenwert entschieden hat: **nicht neu rechnen** (das zerstört, worauf eine
übergebene Lieferung sich beruft) und **nicht nur markieren** (ein Potenzial kann bei anderen
Zahlen anders *geschnitten* sein).

**Eine Wiederholungsgrenze gibt es nicht.** Eine Obergrenze hätte keine definierte Folge; die
Fassungsnummer im Pfad leistet, worum es in [#234](https://github.com/pg-coe-kmu/coe-factory/issues/234)
Punkt 4 geht: ein Lauf bei `f4` fällt beim Hinsehen auf.

### 2.4 Ein Konzept wird nie ungültig — es veraltet

BC2 rechnet auf `stand_zum(uebergeben_am)`. Ein übergebenes Konzept bleibt damit **für seinen Stand
reproduzierbar korrekt**, gleichgültig was BC0 danach erhebt.

**BC2 stellt eine Nacherhebung nicht selbst fest** und beobachtet keine fremden Tabellen. Jede
Neuberechnung beginnt mit einem neuen Ruf von BC0 (ADR-003 Regel 4: die Nachricht ist der Zettel,
die Datenbank der Inhalt). Erhebt BC0 nach, schnürt BC0 ein neues Paket; daraus entsteht ein neuer
Lauf und damit eine neue Fassung.

### 2.5 Eine Kennung, ein Inhalt

Jede Fassung bekommt eine **neue `konzept_id`** und ein Feld, das auf die Vorgängerfassung zeigt
(`ersetzt_konzept_id`). BC3 kann damit prüfen, ob das Konzept hinter einem Epic noch das jüngste
ist. Dieselbe Regel trägt den Ordnernamen: ein Pfad, ein Inhalt, unveränderlich.

## 3. Warum nicht anders

**Warum kein REST-Push an BC3 (spiegelbildlich zum Trigger).** BC3 hat keinen Endpunkt gebaut und
keinen zugesagt. Einen zu verlangen wäre die dritte Schnittstelle für dieselbe Kette — und ihn
einseitig in den Vertrag zu schreiben wäre der vierte Fall der Fehlerform, die diese Karte dreimal
verzeichnet: vom Artefakt auf die Absicht des Gegenübers schließen (#163, #186, #165).

**Warum das Konzept nicht einzeln übergeben wird.** Ein einzeln freigegebenes Konzept hat keine
Reihenfolge. Die prozessübergreifende Priorisierung ist der Kern dessen, was BC2 liefert; BC3 bekäme
Epics ohne den Rang, der sie sortiert.

**Warum die `konzept_id` nicht über Fassungen hinweg stabil bleibt.** Eine stabile Kennung hielte
BC3s Referenzen unverändert — um den Preis, dass zwei verschiedene Inhalte dieselbe Kennung tragen.
Dann kann BC3 nicht mehr sagen, welchen Stand es verarbeitet hat, und Idempotenz über die ID ist
nicht mehr möglich. Die Verkettung erreicht dasselbe Ziel, ohne die Regel zu brechen.

**Warum die Fassung im Pfad steht und nicht nur im Dateiinhalt.** Sonst müsste BC3 jede Datei erneut
öffnen, um zu merken, dass sich etwas geändert hat — oder ein Ordner änderte sich unter der Hand,
was der Unveränderlichkeit widerspricht.

## 4. Folgen

1. **Zwei zusätzliche Änderungen an v3.0** ([#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)):
   `gate1` von `konzept.schema.json` nach `priorisierung.schema.json`, und `ersetzt_konzept_id` je
   Konzept.
2. **Die Ablage- und Fassungskonvention ist BC3 noch nicht vorgelegt.** Bestätigt ist nur, dass BC3
   zieht. Ordnerschnitt, Fassungsnummer im Pfad und die neue `konzept_id` je Fassung betreffen BC3
   unmittelbar und sind vor dem Durchstich in KW 40
   ([#206](https://github.com/pg-coe-kmu/coe-factory/issues/206)) zu bestätigen.
3. **Es gibt keinen Rückkanal an BC0.** Lehnt Gate 1 ab, bleibt BC0s Paket im Zustand „übergeben",
   ohne dass je ein Ergebnis folgt — dieselbe Lücke wie an Gate 0, eine Station weiter. Der Weg
   dahin ist Schema `bc2` (BC0 darf lesen), nicht ein Endpunkt bei BC0. Bis dahin erfährt BC0 einen
   Reject **nur über Menschen**, und das ist BC0 zu sagen.
4. **Ein abgelehnter Lauf hat heute keinen Ablageort.** Er lebt nur im Arbeitsstand von BC2. „Die
   alte Fassung bleibt abrufbar" trägt erst, wenn Schema `bc2` steht — der Tabellenentwurf muss
   deshalb auch die **abgelehnten** Läufe tragen, nicht nur die ausgelieferten.
5. **Die Schema-Prüfung in der CI deckt `bc2-to-bc3` nicht ab.** `vertraege-pruefen.yml` läuft bei
   jeder Änderung unter `contracts/**`, prüft aber ausschließlich `contracts/bc3-to-bc4`. Ohne
   Erweiterung ist der PR-Weg aus 2.2 ein Verfahren ohne Netz. Auflage an den Test- und CI-Schnitt.
6. **Gate 0 bleibt einweg**, und das ist für BC2 kein offener Punkt mehr.
