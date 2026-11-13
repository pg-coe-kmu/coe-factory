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
schriftlich ist es im Tracker nirgends festgehalten, siehe Abschnitt 4 Punkt 2).

Ablage: `contracts/bc2-to-bc3/lieferungen/<company>-<paket_id>-f<n>/` im Repo, mit den *n*
Konzepten, der Priorisierung und der Nachricht an BC3 — der Aufbau der Lieferung vom 30.08.2026,
nur maschinell erzeugt und maschinell benannt. **Das Datum trägt keine Identität** (zwei Läufe am
selben Tag sind möglich), die `paket_id` schon. Der Google Drive bleibt Spiegel, nicht Quelle.

Die Lieferung landet **per Pull Request**, nicht direkt auf `main`. Atomarität löst Git ohnehin —
BC3 sieht über `git pull` nie einen halb geschriebenen Ordner. Was der PR zusätzlich bringt, ist
das Netz gegen eine schema-ungültige Lieferung: eine kaputte Lieferung, die BC3 bereits gezogen
hat, holt niemand zurück.

> **Nachtrag vom 09.10.2026 ([#305](https://github.com/pg-coe-kmu/coe-factory/issues/305)): wer die
> Lieferung schreibt und wann.** Der echte Weg legte einen gültigen Vertrag 3.1 in Schema `bc2` ab,
> aber nichts davon kam im Lieferordner an — die Konzepte und die Priorisierung schrieb niemand, und
> die Präsentation sperrte sich selbst, weil Sperrgrund und Hinweis in einem Feld lagen.
>
> 1. **Übergeben ist mit der Freigabe, nicht mit dem Download.** Das Glossar sagte es schon
>    („Gate 1 … die Übergabe an BC3“). Hinge die Lieferung am Download der Präsentation, wäre ein
>    freigegebener Lauf, den niemand herunterlädt, nie geliefert.
> 2. **Die Datenbank ist der eine Ort, der Lieferordner ihre Abbildung.** Schema `bc2` trägt den
>    vollständigen Vertrag (Lauf, Konzepte, Gate-1-Entscheidung). Ein Werkzeug
>    (`tools/lieferung_ziehen.py`) liest alle freigegebenen, lieferbaren Läufe über den
>    Betriebscontainer und schreibt die Ordner in den Arbeitsbaum; den PR öffnet ein Mensch, die CI
>    prüft (#253). **Der Dienst schreibt keine Lieferdateien.** Verworfen: der Dienst schreibt in ein
>    eingehängtes Verzeichnis (zwei Ablagen desselben Inhalts) und der Dienst öffnet den PR selbst
>    (ein GitHub-Schlüssel auf dem Server, gegen ADR-003). Der Preis: angekommen ist erst, was
>    gezogen wurde.
> 3. **Keine Markierung „geliefert“.** Das Werkzeug erzeugt byte-gleich neu; `git status` zeigt nur
>    das Neue. Käme ein vorhandener Ordner anders heraus, bricht es mit dem Unterschied ab, statt
>    zu überschreiben — was übergeben ist, ändert sich nicht.
> 4. **Im Ordner liegen** `prozesspriorisierung.json`, `konzept_<KP>.json` je Konzept und eine
>    maschinell erzeugte `NACHRICHT_AN_BC3.md` (Paket, Fassung, Freigabe, Konzepte in finaler
>    Reihenfolge, Vorgänger, Hinweise). **Die Präsentation gehört nicht dazu** — sie geht an den
>    Mandanten, als Download und im Drive. Damit entfällt die Ablage aus
>    [#257](https://github.com/pg-coe-kmu/coe-factory/issues/257) samt `BC2_LIEFERUNGEN`.
> 5. **Sperrgrund und Hinweis sind zwei Dinge.** Ein **Sperrgrund** macht einen Lauf unlieferbar:
>    nicht nachrechenbar (Messsatz, Simulation) oder kein Potenzial geschnitten (schemaungültig,
>    `konzept_ids` braucht einen Eintrag). Ein **Hinweis** steht nur da: Modellurteil,
>    Testdatenstand. Freigeben lässt sich ein Lauf mit Sperrgrund trotzdem — die Freigabe ist die
>    Entscheidung des Menschen, der Sperrgrund ein Merkmal des Laufs; er bleibt dann „freigegeben,
>    nicht lieferbar“. Die Hinweise reisen in der Nachricht und auf der Titelfolie, nicht im
>    Vertrag (keine Änderung an 3.1).
>
> Bau: [Lieferung ziehen bauen](https://github.com/pg-coe-kmu/coe-factory/issues/306).

> **Nachtrag vom 13.11.2026 ([#376](https://github.com/pg-coe-kmu/coe-factory/issues/376)): die
> Ergebnisakte.** BC0 soll die vollständigen Ergebnisse eines freigegebenen Laufs aus Schema `bc2`
> lesen können, so wie sie an BC3 und an den Mandanten gehen, samt Präsentation und Link. Bis
> hierher stand der `gate1`-Block nur in der gezogenen Datei, die Nachricht nur im Repo, und die
> Präsentation entstand bei jedem Klick neu. Damit ändert sich Punkt 4 und ein Teil von Punkt 2.
>
> 1. **Jede Freigabe friert eine Ergebnisakte ein**, auch bei einem Lauf mit Sperrgrund, und zwar
>    in derselben Transaktion wie `approved`. Scheitert das Einfrieren, gilt die Freigabe nicht:
>    „freigegeben, aber ohne Akte“ ist der stille Zwischenzustand, den Punkt 1 abschaffen sollte.
> 2. **Der Dienst erzeugt die fertigen Dateien**: `prozesspriorisierung.json` mit `gate1`,
>    `konzept_<KP>.json` je Konzept, `NACHRICHT_AN_BC3.md` und die Präsentation. Er legt sie Byte
>    für Byte in `bc2` ab, jede mit ihrem Empfänger (`bc3` oder `mandant`). Die Vertragsschemas,
>    nach denen die Schlüssel geordnet werden, kommen dafür ins Image. **Damit gibt es eine Stelle,
>    an der die Lieferdatei entsteht.** `tools/lieferung_ziehen.py` setzt nichts mehr zusammen; es
>    schreibt die `bc3`-Dateien eines lieferbaren Laufs ab. Die Lieferung bleibt der Teil der Akte,
>    der an BC3 geht. Ein Lauf mit Sperrgrund hat eine Akte, aber keine Lieferung.
> 3. **Punkt 4 kehrt sich für die Präsentation um.** Sie bleibt kein Teil der Lieferung, wird aber
>    abgelegt: als Datei der Akte mit Empfänger `mandant`. Nach der Freigabe liefert der Download
>    diese Datei; neu gezeichnet wird nicht mehr. Sonst gäbe es zwei Präsentationen desselben
>    Laufs, die nach einer Codeänderung auseinanderlaufen.
> 4. **Die Akte ist nach dem Schreiben unveränderlich**, wie das Ergebnis eines Laufs (ADR-008 ·
>    BC2, 2.2). Einzige Ausnahme ist die Sperre des Links. **Einen Löschschutz gibt es nicht**: das
>    Löschen über die Kaskade vom Lauf bleibt möglich, wie für den Lauf selbst. Anlass der Frage war,
>    dass BC0 zwei gelieferte Läufe gelöscht hatte
>    ([#379](https://github.com/pg-coe-kmu/coe-factory/issues/379)).
> 5. **Der Link** auf die Präsentation führt zu BC2, mit einem zufälligen Token je Akte und ohne
>    den Schlüssel der Oberfläche. Er gilt unbefristet und lässt sich sperren. Die Bytes liegen
>    zusätzlich in der Datenbank, damit BC0 sie auch selbst ausliefern kann. Wer den Link hat,
>    bekommt Mandantendaten; für den PoC mit einem Mandanten ist das in Kauf genommen.
> 6. **BC0 liest eine Sicht `bc2.v_ergebnisakte`**, nicht die Tabellen. `v_ergebnis_je_paket`
>    zeigt nur die jüngste Fassung je Paket, eine Akte gehört aber zu genau einer Fassung.
>
> Verworfen: nur die Dokumente als `jsonb` ablegen und Ordnen und Nachricht im Werkzeug lassen.
> Dann sähe BC0 nicht, was BC3 bekommt, und die Datei entstünde weiter an zwei Orten.
>
> Bau: [Ergebnisakte bauen](https://github.com/pg-coe-kmu/coe-factory/issues/378), nach den
> beiden Präsentations-Tickets, weil eingefroren endgültig ist.

> **Nachtrag vom 13.11.2026 ([#383](https://github.com/pg-coe-kmu/coe-factory/issues/383)): die
> Lieferung kommt ohne Handgriff ins Repo.** Seit der Ergebnisakte entsteht die Lieferdatei fertig
> im Dienst; übrig blieb der Handgriff aus Punkt 2 des Nachtrags vom 09.10.: Werkzeug fahren,
> committen, PR öffnen. Er fällt weg, ohne dass ein Schlüssel mit Schreibrecht entsteht.
>
> 1. **Eine GitHub Action zieht nach Zeitplan**, alle 30 Minuten und auf Handstart. Sie liest über
>    HTTPS einen eigenen Endpunkt des Dienstes, der **nur die `bc3`-Dateien lieferbarer Akten**
>    zeigt, mit einem **eigenen, nur lesenden Schlüssel** als Actions-Secret. Er verrät nichts, was
>    nicht ohnehin ins Repo käme. Ausdrücklich nicht der Schlüssel der Oberfläche: mit dem ließe
>    sich Gate 1 entscheiden.
> 2. **Zeitplan statt Ereignis.** Ein Anstoß beim Freigeben bräuchte Schreibrecht des Servers auf
>    GitHub (`repository_dispatch`), also genau den Schlüssel, den Punkt 2 vom 09.10. abgelehnt hat.
>    Der Preis ist eine halbe Stunde, dazu die Verspätung des GitHub-Zeitplans; BC3 zieht ohnehin.
> 3. **PR, und die Action mergt selbst**, sobald ihre Prüfung grün ist: dieselbe wie die CI
>    (`tools/validate.py`). Ein PR mit `GITHUB_TOKEN` stößt keinen anderen Workflow an, deshalb
>    prüft sie selbst, vor dem Öffnen. Die menschliche Entscheidung fällt an Gate 1 und ist
>    eingefroren; eine Gegenzeichnung hat BC3 nie verlangt (09.09.2026). Ein zweiter, menschlicher
>    Merge wäre ein Stempel. Der PR bleibt, weil er Nachweis und Signal ist.
> 4. **Das Signal an BC3 gibt CODEOWNERS**: `/contracts/bc2-to-bc3/` fordert `team-bc2` und
>    `team-bc3` automatisch an. Die Action braucht dafür kein Recht. Die PR-Beschreibung ist die
>    `NACHRICHT_AN_BC3.md`.
> 5. **Scheitert der Zug, bleibt alles stehen.** Weicht ein vorhandener Ordner ab oder verletzt eine
>    Datei das Schema, endet der Lauf rot, ohne PR und ohne Überschreiben; GitHub meldet den
>    fehlgeschlagenen Lauf. Was übergeben ist, ändert sich nicht (Punkt 3 vom 09.10.).
> 6. **`tools/lieferung_ziehen.py` bleibt der Kern.** Es bekommt eine zweite Quelle (der Endpunkt
>    statt `ssh bc2`); Abschreiben und Abbruch bei Abweichung bleiben, wie sie sind. Von Hand
>    ziehen geht weiter.
>
> Verworfen: der Dienst öffnet den PR (Schreibschlüssel auf dem Server, wie am 09.10.); ein
> SSH-Schlüssel zum VPS oder die Datenbank-DSN als Actions-Secret (das Geheimnis verließe den
> Server, ADR-003); ein Zeitplan auf Sergios Rechner (hängt an einem Gerät und einer Person).
>
> Voraussetzungen, die nur ein Mensch erfüllt: In den Repo-Einstellungen dürfen Actions PRs
> anlegen. Der Schlüssel steht in der Server-`.env` und als Actions-Secret, eingetragen von
> Sergio, nicht durch den Chat.
>
> Bau: [Lieferung automatisch pushen bauen](https://github.com/pg-coe-kmu/coe-factory/issues/388).

### 2.3 Ein Reject liefert nichts aus und löscht nichts

Bei `gate1.status = rejected` geht **nichts** in den Lieferordner — dieser Ordner ist BC3s Eingang,
und was dort liegt, gilt als übergeben. Der abgelehnte Lauf bleibt mit seiner Begründung stehen.
Ein erneuter Lauf über dasselbe Paket erzeugt eine **neue Fassung**; die alte bleibt abrufbar.

> **Nachgeschärft am 09.10.2026 ([#250](https://github.com/pg-coe-kmu/coe-factory/issues/250),
> ADR-008 · BC2 §2.1):** diesen erneuten Lauf stößt **BC2 selbst** an, an Gate 1 und nur nach
> einem Reject — `bc2.eingang` nimmt dasselbe Paket von BC0 nur einmal an. §2.4 widerspricht dem
> nicht, es meint einen anderen Anlass: eine Nacherhebung ergibt ein **neues Paket**, das wieder
> bei `f1` beginnt. Nach `approved` gibt es keine neue Fassung.

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
   ([#206](https://github.com/pg-coe-kmu/coe-factory/issues/206)) zu bestätigen — vorgelegt mit [#242](https://github.com/pg-coe-kmu/coe-factory/issues/242).
3. **Es gibt keinen Rückkanal an BC0.** Lehnt Gate 1 ab, bleibt BC0s Paket im Zustand „übergeben",
   ohne dass je ein Ergebnis folgt — dieselbe Lücke wie an Gate 0, eine Station weiter. Der Weg
   dahin ist Schema `bc2` (BC0 darf lesen), nicht ein Endpunkt bei BC0. Bis dahin erfährt BC0 einen
   Reject **nur über Menschen**, und das ist BC0 zu sagen — gefragt mit [#241](https://github.com/pg-coe-kmu/coe-factory/issues/241), zusammen mit der Zusage aus 2.4, dass BC0 nach einer Nacherhebung neu schnürt.
4. **Ein abgelehnter Lauf hat heute keinen Ablageort.** *(Entworfen am 09.10.2026 in ADR-008 · BC2,
   [#250](https://github.com/pg-coe-kmu/coe-factory/issues/250); erledigt mit dem Bau.)* Er lebt nur im Arbeitsstand von BC2. „Die
   alte Fassung bleibt abrufbar" trägt erst, wenn Schema `bc2` steht — der Tabellenentwurf muss
   deshalb auch die **abgelehnten** Läufe tragen, nicht nur die ausgelieferten.
5. **Die Schema-Prüfung in der CI deckt `bc2-to-bc3` nicht ab.** `vertraege-pruefen.yml` läuft bei
   jeder Änderung unter `contracts/**`, prüft aber ausschließlich `contracts/bc3-to-bc4`. Ohne
   Erweiterung ist der PR-Weg aus 2.2 ein Verfahren ohne Netz. Auflage an den Test- und CI-Schnitt.
   **Für die Lieferstrecke erledigt mit [#253](https://github.com/pg-coe-kmu/coe-factory/issues/253):**
   eigener Job „BC2 → BC3 Lieferungen" mit eigenem Ergebnis, `validate.py` findet jeden
   Lieferordner selbst. Ob er den Merge *verhindert*, entscheidet erst die Pflicht-Prüfung im
   Ruleset von `main`. BC2s Tests laufen weiterhin in keiner CI.
6. **Gate 0 bleibt einweg**, und das ist für BC2 kein offener Punkt mehr.
