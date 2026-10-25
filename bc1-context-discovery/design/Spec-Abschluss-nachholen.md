# Entscheidungsvorlage — Abschluss nachholen (Paket (4))

> **Status:** **Entschieden 25.10.2026 (BC1-Projektleitung): B2 in enger Form plus H** — enge Form,
> Wortlaut wie vorgeschlagen, Regel R4-I1 wird ersetzt. Unabhängig geprüft (Bau-Sicht und
> Gegenprüfung, drei Runden, Befunde eingearbeitet). Gebaut wird nach eigenem Plan mit TDD.
> **Bezug:** Abschlussplan „Neu 23.10.“ (2) und C4 „Outbox/Reconciler“; `bc1_service/n8n/SMOKE.md`,
> Abschnitt „Betrieb: wenn das Schreiben des Profils klemmt“; Spec DB-Profil-Fundament, Regel R4-I1.

---

## Big Picture

### Das Problem

Am Ende eines Interviews speichert BC1 das fertige Prozessprofil. Gelingt das nicht, antwortet der
Dienst mit 503 und dem Text „… Bitte senden Sie Ihre letzte Nachricht in einem Moment noch einmal.“
Das ist Absicht: Lieber keine Abschlussantwort als eine, deren Profil nicht in der Datenbank steht.

Im Chat führt dieser Rat in eine Sackgasse. Der n8n-Chat gibt jeder gesendeten Nachricht eine neue
Kennung. Der Dienst sieht die Sitzung schon als abgeschlossen an und weist die neue Nachricht mit 409
ab: „Dieses Interview ist bereits abgeschlossen.“ Die Person hat die Zusammenfassung nie gesehen, und
das Profil bleibt ungeschrieben, bis jemand aus dem Betrieb es von Hand nachholt (mit der alten
Kennung aus dem Protokoll, per curl). Gemessen und in `SMOKE.md` beschrieben.

### Was heute passiert

1. Letzte Antwort der Person → der Kern erkennt „alle Pflichtfelder da“, setzt die Sitzung auf
   `fertig` und speichert die Abschlussantwort.
2. Der Profil-Writer soll das Profil einfrieren — und scheitert → **503**, die Antwort wird nicht
   ausgeliefert.
3. Die Person sendet erneut (neue Kennung) → **409 „bereits abgeschlossen“** — eine falsche Aussage,
   denn das Profil fehlt.
4. BC0 kann Gate 0 nicht entscheiden. Nur eine `ERROR`-Zeile im Protokoll zeigt es.

### Woran das Speichern scheitert — ehrlich eingeordnet

Die **meisten Ursachen sind dauerhaft**: Am häufigsten belegt ein fremder Entwurf denselben
Teilprozess (`SMOKE.md`); dazu kommen ein belegtes Ziel beim Umbinden, Werte, die nicht in die Spalten
passen, eine Rolle oder ein Teilprozess, den es bei BC0 nicht mehr gibt. Dann hilft kein Neusenden,
sondern nur ein Eingriff des Betriebs. **Von selbst heilt nur eine kurze Störung** genau zwischen dem
Speichern der Sitzung und dem Einfrieren des Profils — ein schmales Zeitfenster. Das bestimmt, was
jede Option leisten kann.

### Die Optionen auf einen Blick

| | Option | Was die Person nach dem 503 beim Neusenden sieht | Aufwand | Einschätzung |
|---|---|---|---|---|
| **A** | So lassen, Betrieb holt von Hand nach | 409 „abgeschlossen“ (falsch) | — | vertretbar, aber unehrlich |
| **H** | Ehrlicher Text, solange das Profil aussteht | „abgeschlossen, aber noch nicht gespeichert“ | S | beseitigt die falsche Aussage, holt nichts nach |
| **B1** | Nachholen, Antwort bleibt 409 | 409 „abgeschlossen“ | S | wie B2, nur schlechtere Antwort → nein |
| **B2** | Nachholen und den Abschluss ausliefern — **eng:** nur bei offenem eigenen Entwurf auf dem eigenen Schritt | in diesem Fall: die Zusammenfassung (bei kurzer Störung sofort, sonst nach dem Eingriff); in allen anderen Fällen wie A | S | heilt den Teil, der heilen kann |
| **B2 + H** | **beides** | Zusammenfassung, wo nachholbar; sonst der ehrliche Text | S | **Empfehlung** |
| **B3** | Jede neue Nachricht an eine fertige Sitzung bekommt den Abschluss | auch später immer wieder die Zusammenfassung | S | ändert das Normalverhalten → eher nein |
| **C** | Sitzung erst nach erfolgreichem Speichern abschließen | normal weiter | L | Umbau des Kerns → nein |
| **D** | n8n schickt beim Neusenden dieselbe Kennung | wie B2 | — | im Chat nicht machbar (Annahme, s. u.) → nein |
| **E** | Nachholen im Hintergrund, regelmäßig | wie A bzw. H | M–L | gehört zu B3 Teil 2 |
| **F** | Speichern im selben Aufruf kurz wiederholen | seltener ein 503 | S | nur kurze Störungen; später |
| **G** | Nachholen beim Start des Dienstes | wie A bzw. H | S–M | günstige Vorstufe von E; später |

### Empfehlung: B2 in enger Form, ergänzt um H

**Nachholen, wo es sicher geht (B2 eng).** Kommt eine neue Nachricht an eine Sitzung, die `fertig` ist,
deren **eigener Entwurf noch offen ist und auf dem Schritt liegt, den die Sitzung festgestellt hat**,
und deren Paket sich nicht geändert hat, holt der Dienst das Einfrieren nach und liefert die
gespeicherte Abschlussantwort aus — genau das, was der Betrieb heute von Hand tut.

**Ehrlich antworten, wo es nicht geht (H).** Steht das Profil aus, ist aber nicht sicher nachholbar
(kein eigener Entwurf, Entwurf auf einem anderen Schritt, Paket geändert), antwortet der Dienst nicht
mehr „bereits abgeschlossen“, sondern mit einem eigenen Text, dass das Ergebnis noch nicht gespeichert
ist (Wortlaut: Entscheidung 3).

**Was das bringt:**
- Die falsche Aussage „abgeschlossen“ verschwindet in **allen** Fällen, in denen das Profil fehlt (H).
- Eine kurze Störung beim Einfrieren heilt von selbst, sobald die Person erneut sendet (B2).
- Ist der eigene Entwurf noch offen, reicht nach einem Eingriff des Betriebs, dass die Person erneut
  sendet — kein curl mit der alten Kennung (B2).
- Klein: eine Lese-Methode und eine Weiche an einer Stelle; Kern und Writer können das Nachholen schon.
  Keine Datenbankänderung, kein Vertragsthema mit BC2; die Regel „Profil nur ausliefern, wenn es
  eingefroren ist“ bleibt unangetastet.
- Die enge Form kann kein jüngeres Profil überholen: Ihr Entwurf belegt genau den Schritt, auf dem sie
  einfriert, und dort kann solange kein anderes Interview einfrieren.

**Was sich im häufigsten Fall ändert — und was nicht:** Blockiert ein fremder Entwurf, sieht die Person
künftig den ehrlichen Text statt „abgeschlossen“. Nachgeholt wird dort **nicht** automatisch: Der
Betrieb räumt auf und holt wie heute von Hand nach.

**Was B2 + H nicht löst:**
- **Dauerhafte Ursachen bei offenem eigenen Entwurf** (Teilprozess stillgelegt, Wert passt nicht): Die
  Person bekommt bei jedem Neusenden wieder den 503 „in einem Moment noch einmal“, bis der Betrieb
  eingreift — wahr, für die Person aber eine Sackgasse.
- **Die Person geht weg.** Dann holt niemand nach. Es bleiben die `ERROR`-Zeile und die Messung M3 vor
  jedem Neustart. Lückenlos erst mit G oder E.
- **Der Text der neuen Nachricht wird nicht gelesen.** Eine Korrektur statt einer Wiederholung ändert
  nichts an der gespeicherten Zusammenfassung.
- **Die Ursache selbst** — die Sitzung ist schon `fertig`, bevor das Profil steht (C4 K-K) — bleibt.

**Ehrlich zum Nutzen:** Er ist begrenzt; die meisten Fälle brauchen den Betrieb weiterhin. Der größte
Gewinn ist, dass die Person nicht mehr belogen wird (H). B2 kommt für die kurzen Störungen dazu, die im
Betrieb mit einer entfernten Datenbank zu erwarten, bisher aber nicht gemessen sind. Wer nur das
Nötigste will, wählt **H allein**; wer gar nichts bauen will, **A**.

### Entscheidungen (BC1-Projektleitung, 25.10.2026)

*Alle vier wie empfohlen entschieden: B2 eng + H, enge Form, Wortlaut wie vorgeschlagen, R4-I1 wird
ersetzt. Die Punkte bleiben zur Nachvollziehbarkeit stehen.*

1. **Welche Option?** Empfehlung **B2 eng + H**. Alternativen: **H allein** (ehrlich, ohne
   Selbstheilung) oder **A**.
2. **Bei B2: enge oder weite Form?** Empfehlung **eng**. Die weite Form würde auch ohne eigenen Entwurf
   bzw. mit Umbinden auf einen anderen Schritt nachholen. Damit deckt sie den fremden Entwurf ab, legt
   aber auch einen vom Betrieb **absichtlich gelöschten** Entwurf wieder an und kann umbinden, nachdem
   ein anderes Interview den Zielschritt eingefroren hat. Die Datenbank vergibt die Fassungsnummer neu
   (höchste + 1): Ein verspätetes, älteres Interview würde zur jüngsten Fassung des Teilprozesses und
   damit maßgeblich für Gate 0. Laut BC0 (Mitteilung 25.10., v3.16–v3.18) macht ein neues BC1-Profil
   eine bestehende Freigabe veraltet. „Gelöscht“ von „nie angelegt“ zu unterscheiden, ginge nur mit
   einer Datenbankänderung.
3. **Wortlaut des neuen Texts (H).** Vorschlag: „Ihr Interview ist abgeschlossen, das Ergebnis konnte
   aber noch nicht gespeichert werden. Bitte wenden Sie sich an Ihre Ansprechperson.“ Er verspricht
   kein Nachholen, weil das nur der Betrieb leisten kann. Wer im öffentlichen Chat „Ihre
   Ansprechperson“ ist, ist dieselbe offene Frage wie Abschlussplan „Neu 23.10.“ (8) — beim Durchstich
   bzw. in der Live-Bewertung prüfen.
4. **Spec-Änderung:** B2 hebt Regel **R4-I1** der Spec DB-Profil-Fundament auf („neue `message_id`s weist
   das bestehende 409-Gate weiterhin ab (kein Reconcile-Anspruch)“) und ersetzt sie durch die Regel aus
   Abschnitt 4. Ein Go für B2 schließt diese Änderung ein; der Plan zieht den Text nach. (H allein
   berührt R4-I1 nicht: Es bleibt beim 409, nur mit anderem Schlüssel und Text.)

---

## Technischer Teil

### 1. Ist-Stand im Code (gelesen auf `main` @ `3fe21c1`)

| Stelle | Was dort passiert |
|---|---|
| `bc1_service/api.py:251–256` | Terminal-Gate: Sitzung in `TERMINALE_STATUS` und `message_id` unbekannt → 409 `session_abgeschlossen`, **bevor** der Kern läuft. Bekannte Kennungen gehen an den Kern. |
| `bc1_core/core.py:112–123`, `56–79` | Nach Mandanten- und Anfrage-Schutz der Paket-Schutz (`116–117`: `schema_version` ungleich **oder** `paket_name` weder `None` noch gleich); Ausnahme nur für den Recovery-Replay mit bekannter Kennung **und** mitgesendeter alter `schema_version`. |
| `bc1_core/core.py:125–129` | Bekannte, beantwortete Kennung → gespeicherte Antwort (Replay). |
| `bc1_core/core.py:145–149` | **Neue Kennung an eine terminale Sitzung → `state.antworten[letzte Kennung]`, ohne zu speichern** (kein `raw_log`, kein LLM, Text ungenutzt). Kommentar: „aktives Zurückweisen ist Sache der Transportschicht (P2)“. Test: `tests/test_core.py:208`. |
| `bc1_service/api.py:274–306` | Nach dem Kern: erneut laden, Mandanten- und Anfrage-Schutz, `writer.reconcile`, bei `ProfilWriteError` 503, sonst Overlay aus der DB, Gate bei BC0 im Hintergrund, `chat_text`. |
| `bc1_service/api.py:207–215` | Jede andere Ausnahme → 500 `interner_fehler`. |
| `bc1_service/profil_writer.py:351–429` | `reconcile` ist wiederholbar und läuft in **einer** Transaktion: Profil eingefroren → gespeichertes Profil (`421–423`); Entwurf auf anderem Schritt → Umbinden (`405–411`, `489–506`: alten Entwurf löschen, auf dem Ziel neu anlegen); Entwurf `in_erhebung` → erneute Prüfung der Interviewbarkeit (`428`), dann einfrieren; kein Entwurf → anlegen (scheitert bei fremdem Entwurf). |
| `bc1_service/profil_writer.py:438–447` | `_bindung`: Bindung der Sitzung mit `focus_step_id` und Profilstatus. |
| `bc1_service/db/prozessprofil.sql` | `profil_write_status` hängt per `ON DELETE CASCADE` am Profil (gelöschter Entwurf ⇒ Bindung weg); höchstens ein `in_erhebung`-Entwurf je Schritt (`:686–688`); Fassungsnummer vergibt ein Trigger (höchste + 1, `:775–778`); Status nur `in_erhebung`/`fertig`; maßgeblich für Gate 0 ist die jüngste `fertig`-Zeile. |
| `bc1_service/main.py:52–56` | Getrennte Pools für Sitzungen und Profile (Profil-Pool `max_size=5`). |
| `bc1_service/n8n/bc1-chat-workflow.json` | HTTP-Knoten mit `neverError`, **ohne** Wiederholung; zeigt `chat_text ?? detail`. |
| `bc1_core/types.py:22–24` | `TERMINALE_STATUS = (FERTIG, ABGEBROCHEN_OHNE_IDENTITAET)`. |

Heutiges Verhalten, in Tests festgehalten: `tests/test_api.py:713` (409 trägt `chat_text`), `:784`
(der 503-Text verspricht nicht, dass Neusenden alles rettet), `tests/test_api_profil.py:855` (503, dann
Nachholen mit **derselben** Kennung), `tests/test_protokoll.py:78/224` (Protokollzeile 409).

Normative Texte, die B2 berührt: Spec DB-Profil-Fundament, **R4-I1** (lokal,
`docs/superpowers/specs/2026-08-23-bc1-db-profil-fundament-design.md:340–343`) — „kein
Reconcile-Anspruch“ für neue Kennungen; `design/Design-Spec.md:95` — „fertige Session antwortet
idempotent; Reject-Semantik → Transportschicht“ (verträgt sich mit B2 und H).

### 2. Ursachen eines 503 im Abschluss-Turn

| Ursache | Dauer | eigener Entwurf auf eigenem Schritt offen? | B2 eng | B2 weit | H |
|---|---|---|---|---|---|
| Kurze Störung beim Einfrieren (Profil-Pool, Netz) | vorübergehend | meist ja | ✓ beim Neusenden | ✓ | Text, falls nein |
| Fremder Entwurf belegt den Schritt (K5, häufigster Fall) | bis zum Eingriff | **nein** | — (von Hand) | ✓ nach dem Eingriff | ✓ Text |
| Ziel beim Umbinden belegt (`profil_writer.py:405–411`) | bis zum Eingriff | **nein** (Entwurf liegt auf dem alten Schritt) | — (von Hand) | ✓, kann überholen | ✓ Text |
| Teilprozess stillgelegt / Bewertung verworfen (`:428`, beim Anlegen `:510`) | dauerhaft | meist | 503-Schleife | 503-Schleife | Text, falls nein |
| Wert passt nicht in die Spalte (`:203–211`) | dauerhaft | meist | 503-Schleife | 503-Schleife | Text, falls nein |
| FK/CHECK verletzt, z. B. `process_owner_rolle_id` (`:217`) | bis BC0-Daten passen | meist | ✓ danach | ✓ | Text, falls nein |
| Abschluss-Schutz verletzt, Einfrieren trifft ≠ 1 Zeile | Fehler im Code | ja | 503-Schleife | 503-Schleife | — |

„Meist“: Wird der Schritt erst im Abschluss-Turn gültig, entsteht der Entwurf erst dort und wird beim
Fehler mit zurückgerollt. Scheitert schon das Speichern der **Sitzung**, ist sie nicht `fertig` (500
`interner_fehler`) — kein Fall für dieses Paket.

### 3. Optionen im Detail

**A — so lassen.** Kein Code, Betriebsweg in `SMOKE.md`. Die Person liest nach dem Neusenden
„abgeschlossen“, obwohl nichts gespeichert ist; das Profil kann unbemerkt fehlen, bis jemand die
`ERROR`-Zeile sieht.

**H — ehrlicher Text.** Im Terminal-Gate für `fertig`-Sitzungen mit ausstehendem Profil 409 mit eigenem
Schlüssel (etwa `abschluss_ausstehend`) und eigenem `chat_text` statt `session_abgeschlossen`. Braucht
dieselbe Lese-Methode wie B2. Ändert nichts am Speichern.

**B1 — nachholen, aber 409 antworten.** Gleicher Eingriff wie B2. Die Person sieht nie die
Zusammenfassung; scheitert das Nachholen, wäre 409 eine Unwahrheit und 503 ein Bruch mit
„abgeschlossen“ → nein.

**B2 — nachholen und den Abschluss ausliefern.** Enge Form siehe Abschnitt 4. Die weite Form verzichtet
auf „eigener Entwurf offen, auf dem eigenen Schritt“ (siehe Entscheidung 2).

**B3 — die Abweisung für `fertig` ganz aufheben.** Spart die Lese-Methode, ändert aber das
Normalverhalten: Wer später in einen fertigen Chat schreibt, bekommt die Zusammenfassung statt des
Hinweises auf ein neues Interview. Jede solche Nachricht baut zuerst den Profilinhalt neu (BC0-Lesezugriffe,
erneute Befund-Warnungen, `profil_writer.py:385–396` vor `421`) und stößt das Gate bei BC0 an → eher nein.

**C — terminal erst nach erfolgreichem Speichern.** Neuer Zwischenzustand im Kern, der Kern müsste vom
Writer erfahren. Kehrt die Reihenfolge Kern → Writer um und berührt Idempotenz und Recovery an vielen
Stellen. Beseitigt die Ursache, ist aber groß und riskant → nein. Die Ursache bleibt in C4 nachgehalten.

**D — dieselbe Kennung beim Neusenden.** Unser Workflow bildet die Kennung aus der Ausführung
(`exec-<id>`); jedes Senden ist eine neue Ausführung. *Annahme, nicht in der Primärdoku geprüft:* Der
Chat-Trigger liefert keine stabile Nachrichten-Kennung, aus der man sie bilden könnte. Eine Kennung aus
Sitzung + Text wäre gefährlich: Zwei gleiche Antworten („ja“) in verschiedenen Turns bekämen dieselbe
Kennung, die zweite würde still mit der alten Antwort beantwortet → nein.

**E — Nachholen im Hintergrund.** Ein regelmäßiger Lauf sucht Sitzungen, die nach der engen Regel
nachholbar sind (eine Teilmenge der Bedingung M3), und gleicht sie ab. Deckt auch „Person ist weggegangen“ ab. Braucht einen Zeitgeber und
bei mehreren Workern Abstimmung → B3 Teil 2.

**F — im selben Aufruf wiederholen.** Zwei, drei Versuche mit kurzer Pause, bevor der 503 kommt. Hilft
nur bei kurzen Störungen, verlängert die Antwort unter dem Sitzungs-Lock und gegen das n8n-Zeitlimit.
Variante: Wiederholung im n8n-Knoten innerhalb derselben Ausführung (gleiche Kennung) — wie sich das mit
`neverError` verträgt, ist in der n8n-Doku zu prüfen. Ohne Dauerbetrieb gibt es keine Messung, wie oft
kurze Störungen vorkommen → später.

**G — Nachholen beim Start.** Beim Start des Dienstes (wo B4 schon das Gate nachzieht) für jede Sitzung,
die nach der engen Regel nachholbar ist, den Abgleich nachholen. Kein Zeitgeber, keine Abstimmung
zwischen Workern; schließt „Person weg“ bei jedem Neustart **ohne** Paketwechsel. Mit Paketwechsel ist
es nicht sicher (der Writer baut den Inhalt mit dem neuen Paket), und genau dort verlangt die
Vorbedingung vor dem Neustart ohnehin M3 = 0 → später, sobald der Dienst im Dauerbetrieb läuft.

### 4. B2 (enge Form) + H im Detail

**Regel.** Im Terminal-Gate (`api.py:251`) gilt für eine **neue** `message_id`:

| Sitzung | Bedingung | Antwort |
|---|---|---|
| `abgebrochen_ohne_identitaet` | — | 409 `session_abgeschlossen` — unverändert |
| `fertig` | kein Writer, oder Writer schreibt nicht (Paket ohne Identität) | 409 `session_abgeschlossen` — unverändert |
| `fertig` | Profil eingefroren | 409 `session_abgeschlossen` — unverändert |
| `fertig` | **eigener Entwurf `in_erhebung` auf dem Fokus-Schritt der Sitzung** und der Paket-Schutz des Kerns ließe die Sitzung durch | **B2:** weiter zum Kern → Abschlussantwort → `reconcile` → 200 mit Overlay oder 503 |
| `fertig` | sonst Profil ausstehend: kein eigener Entwurf, Entwurf auf anderem Schritt, oder Paket geändert | **H:** 409 mit eigenem Schlüssel und Text |
| `fertig` | Lese-Methode scheitert | 503 `profil_write_fehlgeschlagen` |

**Paket-Bedingung.** Im Gate muss dieselbe Prüfung gelten wie im Kern (`core.py:116–117`, einschließlich
`paket_name is None`). Im Code eine gemeinsame Prüfung, keine zweite Formulierung.

**Ablauf beim Nachholen.** Die neue Nachricht geht an `process_turn`; der Kern liefert über
`core.py:145–149` die gespeicherte Abschlussantwort und speichert nichts. Danach läuft der bestehende
Block `api.py:274–306` unverändert: Schutzprüfungen, `reconcile`, 503 bei Fehler, Overlay, Gate im
Hintergrund (nur bei Erfolg), `chat_text`. Spec K3.3 („`fertig` nur ausliefern, wenn im selben Abgleich
eingefroren“) gilt ohne Ausnahme.

**Neue Lese-Methode im Writer.** Sie bekommt den Sitzungszustand und meldet einen von vier Ständen:
*kein Profil* (Writer schreibt nicht), *eingefroren*, *nachholbar* (Bindung `in_erhebung` und deren
`focus_step_id` = gültiger Fokus-Schritt der Sitzung), *ausstehend* (alles andere: keine Bindung,
Entwurf auf anderem Schritt). Nur lesend. Ein Fehler (realistisch: Wartezeit im Profil-Pool, fehlende
Rechte) wird als `ProfilWriteError` gemeldet und im Gate **ausdrücklich** in 503 übersetzt — sonst würde
er über `api.py:207–215` zu 500. Ist die Datenbank ganz weg, scheitert schon das Laden der Sitzung
(`api.py:226`) → 500, wie heute. Namen und Form sind Sache des Plans.

**Bewusste Abweichungen und Grenzen.**
- **Idempotenz je Kennung:** Dieselbe neue Kennung ergibt erst 200, danach 409 (der Kern merkt sie sich
  nicht). Erreichbar nur per curl, der Workflow wiederholt nicht. Hingenommen.
- **Text der neuen Nachricht** wird nicht gelesen (Korrektur → alte Zusammenfassung).
- **Kein liegengebliebener Entwurf** nach einem gescheiterten Nachholen: `_abgleich` läuft in einer
  Transaktion. Folgt aus dem Pool-Verhalten, ist aber nicht gemessen → Test im Plan.
- **Spätes Einfrieren:** Kommt die Person erst nach Tagen wieder, friert das Profil dann ein und das Gate
  wird angestoßen. Die Interview-Inhalte sind dieselben wie damals; was gegen BC0 geprüft wird (Sweep der
  Systeme, Eigner-Vergleich, Kernprozess-Prüfung, Interviewbarkeit, `profil_writer.py:385–396` und `428`),
  gilt für den Stand bei BC0 zum Zeitpunkt des Einfrierens. Das Overlay zeigt diesen Stand.

**Was gleich bleibt.** Mandanten- und Anfrage-Schutz zuerst; beide terminalen Zustände im Gate
(`types.py:22`); die vorhandenen Texte in `FEHLER_TEXTE`; keine Änderung an Datenbank, Vertrag oder
Paketfassung; der n8n-Workflow (er zeigt den neuen `chat_text` ohne Änderung).

**Protokoll.** Turn-Zeile wie gewohnt (`http=200 status=fertig`, `503`, bzw. `409` mit dem neuen
Schlüssel). Dazu eine `INFO`-Zeile `abschluss_nachgeholt session=… message=…` (nur Kennungen).
Bei H ist die Turn-Zeile nur `INFO` (`ERROR` erst ab 500, `api.py:217–218`); ob „die Person war wieder
da, das Profil steht weiter aus“ eine eigene `WARNING`-Zeile bekommt, ist zu klären. *Beides Vorschlag,
Entscheidung beim Plan.*

**Aufwand.** S: Lese-Methode samt Fehlerübersetzung, Weiche im Gate mit gemeinsamer Paket-Prüfung, ein
neuer Text, die Fake-Writer in den Tests ergänzen (`tests/test_api.py:548`, `:754`;
`tests/test_protokoll.py:232` haben nur `reconcile`), rund 14 Tests, Doku.

### 5. Testideen (für den Plan)

1. Kurze Störung beim Einfrieren (eigener Entwurf offen), dann **neue** Kennung → 200 `fertig`, Profil
   eingefroren, Overlay aus der DB, `chat_text` = Abschlusstext (Container-Test).
2. Eigener Entwurf offen, Teilprozess inzwischen stillgelegt → wieder 503; kein neuer Entwurf, Sitzung
   unverändert.
3. Nach einem gescheiterten Nachholen steht kein zusätzlicher Entwurf (Rollback).
4. Bei 503 wird das Gate bei BC0 **nicht** angestoßen; bei Erfolg genau einmal.
5. Profil schon eingefroren, neue Kennung → 409 `session_abgeschlossen`.
6. Kein eigener Entwurf (fremder Entwurf hatte blockiert, oder Entwurf gelöscht) → H, nichts wird angelegt.
7. Eigener Entwurf auf altem Schritt (Umbinden gescheitert), Ziel inzwischen frei bzw. dort eingefroren →
   H, kein Umbinden, keine neue Fassung.
8. `abgebrochen_ohne_identitaet` bzw. ohne Writer / Paket ohne Identität → 409 `session_abgeschlossen`,
   Lese-Methode nicht gefragt.
9. Fremder Mandant bzw. fremde Anfrage → weiterhin `mandant_konflikt`/`anfrage_konflikt`.
10. Paket geändert (auch mit `paket_name` = `None` an der Sitzung, wie im Kern) → H, kein `paket_konflikt`.
11. Lese-Methode scheitert → 503, nicht 409 und nicht 500.
12. Text der neuen Nachricht erscheint weder in `raw_log` noch im Protokoll; dieselbe neue Kennung nach
    Erfolg noch einmal → 409 `session_abgeschlossen`.
13. Der neue Text hält die Regeln für `FEHLER_TEXTE` ein (kein Schlüssel, kein `_`, kein `{`).
14. Protokollzeile zeigt den neuen Schlüssel bei H.

### 6. Doku, die mit dem Bau mitgeht

`SMOKE.md` (Absatz „Im Chat reicht Neusenden nicht immer“ neu fassen; im K5-Rezept ergänzen, dass ein
gelöschter Entwurf einer `fertig`-Sitzung nicht nachgeholt wird und die Person den neuen Text sieht) ·
Modul-Kopf `api.py` · Kommentar `core.py:146–148` · Kommentar `types.py:22–23` · README Betriebsprotokoll
(neuer Schlüssel, ggf. Zeile `abschluss_nachgeholt`) · Testkommentar `tests/test_api.py:784` · Spec
DB-Profil-Fundament R4-I1 (lokal) · Abschlussplan „Neu 23.10.“ (2) und C4.

### 7. Nachgehalten, je mit Ziel

- **G — Nachholen beim Start** (schließt „Person weg“ bei Neustarts ohne Paketwechsel). Ziel: B3 Teil 2,
  sobald der Dienst im Dauerbetrieb läuft; Auslöser vorher: erster Fall „Person weg nach 503“.
- **E — Nachholen im Hintergrund.** Ziel: B3 Teil 2 bzw. C4, Auslöser: mehr als ein Worker oder G reicht
  nicht.
- **F — Wiederholung im Aufruf oder im n8n-Knoten.** Auslöser: vorübergehende 503 im Betrieb gemessen;
  dann die n8n-Doku zu Wiederholung und `neverError` lesen.
- **Anderer Text für die 503-Schleife bei dauerhaften Ursachen** (statt „in einem Moment noch einmal“).
  Ziel: Live-Bewertung (Paket (6)) bzw. der erste dauerhafte 503 im Betrieb — dann die Ursachen zählen
  und den Text entscheiden.
- **Weite Form von B2.** Nur, wenn K5-Fälle häufig werden; vorher mit BC0 klären, ob ein spät
  eingefrorenes Profil eine schon erteilte Freigabe veralten lassen darf.
- **Ursache „Sitzung `fertig` vor dem 503“** (C4 K-K, Codex A7 I1) bleibt in C4.
- **Nebenbefund der Prüfung (vorbestehend, nicht Teil dieses Pakets):** Ein Konvertierungs-Widerspruch
  (`profil_writer.py:203–211`) wirft `ProfilWriteError` auch in Turns mitten im Interview, und `reconcile`
  reicht ihn unabhängig vom Status weiter (`:356–359`) → 503 mitten im Interview, entgegen dem Kommentar
  `:368`. Ziel: beim Bau dieses Pakets klären (gleiche Datei), sonst C4.
