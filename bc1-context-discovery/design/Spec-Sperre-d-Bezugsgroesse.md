# Spec: Sperre (d) — fremde Bezugsgröße bei Häufigkeit und Dauer

> Entwurf 3, 09.11.2026. Geprüft: Entwurf 1 von einem Claude-Prüfer (0 Critical, 3 Important,
> 6 Minor), Entwurf 2 von agy (1 Critical, 5 Important, 3 Minor); alles eingearbeitet, siehe
> Abschnitt „Was aus den Prüfungen wurde“. Ergänzt `Spec-Antwortformen.md`, Abschnitt 2,
> „Feste Sperren“ (a)–(c). Herkunft: `Abschlussplan-BC1.md`, Kleinpunkte „Neu 09.11.“ (1).
> Nachprüfung von Entwurf 3 durch agy: baufertig, keine neuen Befunde.
> **Abgenommen 09.11.2026 (BC1-Projektleitung): E1–E4 wie empfohlen. Gebaut 10.11.2026,
> mit E3 und den Entscheidungen vom 10.11.; Stand und Prüfungen siehe Nachträge unten.**

## Big Picture

**Das Problem.** Auf die Frage „Wie lange dauert ein einzelner Lauf dieses Schritts?“ antwortet
jemand „30 Minuten pro Fall“. Ob ein Lauf genau einen Fall bearbeitet, steht nicht fest. Die KI
macht trotzdem „30 Minuten“ daraus, und BC1 übernimmt den Wert still als 30 Minuten je Lauf. So
geschehen im Prüfwerkzeug am 30.10. (Szenario 4). Die Prompt-Regel „andere Bezugsgröße:
weglassen“ hält die KI nicht zuverlässig auf. Sperre (b) greift nicht, weil die Nachricht die
Einheit „Minuten“ nennt.

**Die Regel.** Steht in der Nachricht „pro“ oder „je“, dem weder ein Zeitraum (Woche, Monat,
Jahr) noch ein Lauf („Lauf“, „Durchlauf“, „Prozessdurchlauf“) folgt, nimmt BC1 den KI-Wert für
Häufigkeit oder Dauer nicht an und fragt nach. „30 Minuten pro Fall“, „je Vorgang“, „pro Lead“,
„pro Tag“ sperren; „15 pro Monat, 3 Stunden“ oder „pro Durchlauf 90 Minuten“ nicht.

**Was sich für die Person ändert.** Nur wer eine fremde Bezugsgröße nennt, bekommt eine
Nachfrage. Wiederholt sie dann ihren Satz statt einer kurzen Antwort, bleibt das Feld nach zwei
Nachfragen offen (`NULL` für BC2, wie heute schon bei unbekannten Perioden). Kurze Antworten wie
„2 mal pro Woche“ oder „30 Minuten“ laufen wie bisher ohne KI und sind nicht betroffen.

**Was die Regel nicht kann.** Sie verhindert, dass BC1 einen solchen KI-Wert still übernimmt.
Sie erkennt nicht:
- eine Dauer mit Zeitraum („2 Stunden pro Woche“, „2 Stunden im Monat“): bei einer Dauer-Frage
  eine Summe, keine Dauer je Lauf. Das schützt weiter nur der Prompt (E1);
- Formulierungen ohne „pro“ oder „je“ („für jeden Fall“, „jeder Fall dauert 30 Minuten“,
  „jeweils 30 Minuten“; „30 min/Fall“ seit 10.11. erkannt, siehe Nachtrag „E3 umgesetzt“);
- gezählte Dinge vor dem Zeitraum („20 Leads pro Woche“ ist die Zahl der Leads, nicht
  unbedingt der Durchläufe; im Katalog schon als Grenzfall „1040 oder Nachfrage“ geführt);
- Wörter auf „-lauf“, die keinen Prozesslauf meinen („pro Anlauf“, „pro Rücklauf“).
Antwortet die Person auf die Nachfrage „30 Minuten“, meint aber weiter „pro Fall“, gilt der
Wert; das kann keine Regel erkennen.

## Entscheidungen (zur Abnahme)

| # | Frage | Empfehlung | Warum |
|---|---|---|---|
| E1 | Sperrt die Regel bei der Dauer auch Zeiträume („2 Stunden pro Woche“)? | **Nein** (Entwurf 2 sagte noch Ja). Zeitraum und Lauf sind bei beiden Typen erlaubt. | Mit Ja verlöre jede Nachricht, die Häufigkeit und Dauer zusammen nennt, den Dauerwert: „15 pro Monat, 3 Stunden“. So schreiben es die Testprofile (`bc1_service/use_case_testprofile.py`), die Demo-Läufe und rund 200 Sätze in den Tests, und so antworten Menschen. Der Fall „Dauer mit Zeitraum“ ist nicht beobachtet; er bleibt Restrisiko und wird mit einem Katalogeintrag gemessen. |
| E2 | Die Regel wirkt auf die ganze Nachricht, nicht je Zahl. Hinnehmen? | **Hinnehmen.** | Eine Zuordnung „welches ‚pro‘ gehört zu welcher Zahl“ wäre neue, fehleranfällige Logik. Mit E1 = Nein trifft es nur Nachrichten mit einer fremden Bezugsgröße. Dann gehen alle Häufigkeits- und Dauerwerte der Nachricht verloren; ist das gesperrte Feld das gerade gefragte, verwirft Sperre (c) auch die übrigen Felder des Turns. Kosten: eine Nachfrage, im schlechtesten Fall ein offenes Feld, nie ein falscher Wert. |
| E3 | „/“ als Bezug („30 min/Fall“)? | **Nicht jetzt** (umgesetzt 10.11. nach dem Durchrutscher in Szenario 4, siehe Nachtrag „E3 umgesetzt“). Ziel: kein falscher Wert aus „min/…“. Nächster Schritt: Katalogeintrag „30 min/Fall“ (KI: Nachfrage); zeigt Szenario 4 einen Durchrutscher, eine Sperre an der Einheit („min/…“, „Std./…“, „h/…“) bauen. | Bisher nicht beobachtet. Ein freies „/“ stünde auch in Systemlisten („Outlook/SAP“) und in Häufigkeiten („2/Woche“). |
| E4 | Der Vertrag mit BC2 beschreibt heute das Gegenteil („‚90 Minuten pro Fall‘ → `90`“). | **Die Vertragstexte im selben PR ändern (Fassung 1.5, nur Text, Stellen unten), Hinweis an BC2 in #286 vor dem Ausrollen.** Nicht auf BC2s Antwort warten. | Die Normalisierung ist Vertragsbestandteil und wird nicht ohne Hinweis an BC2 geändert. Für BC2 wird es strenger, nicht anders: statt eines still übernommenen Werts im seltenen Fall `NULL`. Struktur, Typen und `lesen.sql` bleiben. Hängt am Roadmap-Punkt „BC2-Texte angleichen“ (Kleinpunkte „Neu 30.10.“ (4)). |

## Technischer Teil

**Ort.** `bc1_core/extractor.py`, `extract_and_merge`, im KI-Zweig (`wert_roh is None`) direkt
nach Sperre (b), mit `continue` wie dort. Die Kurzform bleibt unberührt: Ihre Grammatik nimmt
„30 Minuten pro Fall“ schon heute nicht an (Spec-Antwortformen 3.4).

**Woran die Sperre hängt.** Wie (b) an einem Merkmal des Feldtyps, nie am Feldnamen: neues Feld
`Feldtyp.prueft_bezug: bool = False` (kw_only). `True` nur bei `ZAHL` und `MINUTEN`. Ein
gemeinsames Muster in `bc1_core/feldtypen.py`, eine Hilfsfunktion `nennt_fremden_bezug(text)`.

**Erkennen: Negativform, wiederverwendet.** Wie das frühere `_PRO_MUSTER` (Codex Fix-Welle 5,
bis `82e10ce^` in `bc1_core/feldtypen.py`) auf dem Vergleichsschlüssel der Nachricht
(`vergleichsschluessel`: kleingeschrieben, ä→ae usw., „-“, „_“ und Leerraum werden ein
Leerzeichen): jedes ganze Wort „pro“ oder „je“, dem **nicht** Leerraum und eine passende Form
folgen, sperrt. So sperren auch ein zweites Vorkommen, Satzzeichen direkt danach („pro
(einzelnem) Fall“, „pro „Fall““) und „je“ vor einer Zahl („drei Fälle, je 30 Minuten“).

```
(?<![a-z])(?:pro|je)(?!\s+(?:(?:woche|wochen|monat|monate|monaten|jahr|jahre|jahren)|[a-z]*lauf)(?![a-z]))(?![a-z])
```

Die Zeitraumformen sind dieselben ganzen Wörter wie in Sperre (b) (`_ZEITRAUM_MUSTER`), also
nicht „Wochentag“ oder „Wochenende“.

**Beispiele (werden Tests; Gegenprobe mit dem Muster gelaufen).** „Sperrt“ heißt: der KI-Wert
für ein Feld vom Typ `ZAHL` oder `MINUTEN` aus dieser Nachricht gilt nicht.

| Nachricht | Muster | Ergebnis im Extraktor |
|---|---|---|
| „30 Minuten pro Fall“ | sperrt | Dauer verworfen |
| „30 Minuten pro (einzelnem) Fall“ | sperrt | Dauer verworfen |
| „je Vorgang etwa eine halbe Stunde“ | sperrt | Dauer verworfen |
| „drei Fälle, je 30 Minuten“ | sperrt | Dauer verworfen |
| „pro Laufzettel 5 Minuten“ | sperrt | Dauer verworfen |
| „5 pro Lead im Monat“ | sperrt | Häufigkeit verworfen |
| „je nach Saison 2 mal im Monat“ | sperrt | Häufigkeit verworfen (Einschränkung; der Prompt sagt dort schon „weglassen“) |
| „2 mal pro Woche, je Fall 30 Minuten“ | sperrt | beide verworfen (E2) |
| „90 Minuten pro Durchlauf“ | frei | Dauer angenommen |
| „pro Prozessdurchlauf etwa 90 Minuten“ | frei | Dauer angenommen |
| „15 pro Monat, 3 Stunden“ | frei | beide angenommen (Testprofile, E1) |
| „2 mal pro Woche, je Lauf 30 Minuten“ | frei | beide angenommen |
| „20 Leads pro Woche“ | frei | Häufigkeit angenommen (Bestandstest; Restrisiko oben) |
| „2 Stunden pro Woche“ | frei | Dauer angenommen (Restrisiko, E1) |
| „Prozess läuft wöchentlich“ | frei | Häufigkeit angenommen (kein „pro/je“) |

**Tests.** Das Muster selbst direkt in `tests/test_feldtypen.py` (`nennt_fremden_bezug`), die
Wirkung im Extraktor in `tests/test_extractor_sperren.py`. Für den Extraktor nur Fälle, die
Sperre (b) nicht schon vorher abweist (z. B. „2 pro Wochentag“ fängt schon (b), weil
„Wochentag“ kein Zeitraumwort ist). Je ein Test, dass Sperre (d) nur auf dem KI-Weg wirkt
(Kurzform „2 mal pro Woche“ bleibt) und dass Typen ohne `prueft_bezug` unberührt bleiben.

**Bewusst hingenommen (je eine Nachfrage):** Wörter zwischen „pro“ und „Lauf“ („pro komplettem
Durchlauf“, „pro einzelnem Lauf“), Bindestrich-Schreibweisen („pro Prozess-Durchlauf“ wird im
Schlüssel zu zwei Wörtern), „pro Ausführung“, „pro Durchgang“, „pro Schritt“ und „je Schritt“
(bei E2 eigentlich richtig, bei E1 falsch; der Feldtyp unterscheidet E1 und E2 nicht),
„je nach …“, „je mehr … desto“, „pro forma“.

**Bekannte Grenze.** Im kontextfreien Zweig (Fassung 1.0, nur Demo und Tests) fragt E2 „Wie
lange dauert dieser Schritt im Schnitt?“ ohne „Lauf“, und D4 ist vom Typ `ZAHL` mit „pro
Durchlauf“. Harmlos: Bei D4 verwerfen schon heute „Fester Schutz“ und Sperre (b) jeden KI-Wert
ohne Zeitraum in der Nachricht; bei E2 kostet „pro Schritt“ eine Nachfrage. Der Betrieb lädt
immer den BC0-Kontext.

**Folgen.**
- Paket-Fingerabdruck und `schema_version` bleiben (der Fingerabdruck enthält nur den Kontext).
  Vor dem Update trotzdem messen (`betrieb/BETRIEB.md`, Abschnitt 4).
- Bestehende Tests, Demo-Läufe und `use_case_testprofile.py` bleiben unverändert grün: Ihre
  Sätze nennen nur Zeiträume („15 pro Monat, 3 Stunden“). Die ganze Suite läuft vor dem Merge.
- Antwortkatalog `tests/daten/antwortkatalog.json`: „30 Minuten pro Lead“ und „30 Minuten pro
  Fall“ stehen dort schon als „KI: Nachfrage“; die Sperre setzt das im Code durch. Neu, je
  „fest: Nachfrage, KI: Nachfrage“: `total_duration_minutes` „2 mal pro Woche, je Fall
  30 Minuten“ (E2), `total_duration_minutes` „30 min/Fall“ (E3), `total_duration_minutes`
  „2 Stunden pro Woche“ (Restrisiko E1, misst den Prompt). Alle drei auch in die Liste `PFLICHT`
  in `tests/test_antwortkatalog.py`. Szenario 4 hat damit mehr Läufe; die Zahl steht nach dem
  Bau im Bericht.
- Prompt: unverändert (die Regel steht dort schon).
- Vertrag (E4), Fassung 1.5, nur Texte:
  - `contracts/bc1-to-bc2/README.md`, Abschnitt zu I1: der Satz „ein Zusatz wie ‚pro Fall‘ …
    geht dabei verloren (‚90 Minuten pro Fall‘ → `90`)“ wird zu „wird nachgefragt“. Der Satz
    „Die Bezugsgröße ist eine Annahme aus dem Fragetext, keine Prüfung“ bleibt im Kern richtig
    (ohne „pro/je“ prüft BC1 nichts) und wird nur ergänzt, nicht umgedreht.
  - ebenda, „Normalisierung der Zahlen“: Tabelle und der Satz „Zusätze zur Bezugsgröße
    verworfen“; dabei die überholte Zeile „`30 monatlich` → Nachfrage“ (seit #368 bringt die
    KI „monatlich“ in die Antwortform) und die Regel „nackte Zahl gilt nur, wenn die Person sie
    selbst schreibt“.
  - `prozessprofil.schema.json`: Beschreibungen von `total_duration_minutes`,
    `focus_step_duration_minutes`, `frequency_per_year` und `step_frequency_per_year`.
  - `README.md`, Abschnitt „Stand“: Eintrag „Fassung 1.5“.
  - Hinweis an BC2 in #286 vor dem Ausrollen.
- Prüfwerkzeug nach dem Bau: Szenario 4 zweimal (`betrieb/BETRIEB.md`, Abschnitt 8). Dabei
  prüfen, ob die Nachfrage zu E1/E2 „Lauf“ bzw. „Durchlauf“ nennt.
- Ausrollen nur mit Ansage an BC0 und vor der Probe zur Endpräsentation, nicht danach
  (24-Stunden-Ruhe).

**Nicht Teil dieser Spec.** „/“ als Bezug (E3; umgesetzt 10.11. für „/“ nach einer Zeiteinheit, siehe Nachtrag); eine Dauer mit Zeitraum (E1); Formulierungen
ohne „pro“/„je“; zwei Zeiträume in einer Nachricht („pro Woche … pro Monat“), die die KI zu einem
sauberen Wert macht (früher lehnte das der Normalisierer ab, heute schützt nur der Prompt); eine
Zuordnung je Zahl (E2).

## Was aus den Prüfungen wurde

- **Claude-Prüfer zu Entwurf 1:** Erkennung über „Wort danach“ ließ Satzzeichen durch, Abgleich
  über den Wortanfang war unscharf → Negativform nach `_PRO_MUSTER` (übernommen). Vertrag nicht
  erwähnt → E4 (übernommen). Kosten von E2 zu niedrig → Kosten ehrlich, Katalogeinträge
  (übernommen). Minor: Restrisiken, „je nach“, D4 im kontextfreien Zweig, E3 mit Ziel (übernommen).
- **agy zu Entwurf 2:** Critical: Mit E1 = Ja verlören die Testprofile, die Demo-Läufe und
  rund 200 Testsätze ihren Dauerwert („15 pro Monat, 3 Stunden“) → E1 auf Nein, Zeitraum und
  Lauf für beide Typen erlaubt (übernommen; Scan aller Test- und Service-Sätze gelaufen).
  Important: Sperre (c) verwirft bei E2 auch die übrigen Felder (in E2 benannt);
  Bindestrich-Schreibweisen, „pro Schritt“ (hingenommen, benannt); Stellenliste E4
  unvollständig (ergänzt); Restrisiken ohne „pro/je“ und mit Zeitraum (benannt). Minor:
  Testaufbau, D4-Begründung, `PFLICHT`-Liste (übernommen).

## Nachtrag: Prüfung des Baus (10.11.2026)

Gebaut wie oben (Muster zeichengleich mit der Spec). Geprüft von agy (keine Befunde) und
einem Claude-Prüfer (0 Critical, 1 Important, 6 Minor). Das Important betraf den
Vertragstext (D3 wird nie nachgefragt, die D4-Nachfrage hängt an der KI) und ist dort
berichtigt, ebenso die Zählung: „nach zwei Nachfragen“ (Big Picture oben) heißt richtig
„nach der Frage und einer Nachfrage“ (`MAX_ATTEMPTS_PER_FIELD = 2`). Zwei Tests (Reihenfolge
vor Sperre (c), „pro“/„je“ am Wortende) und zwei Katalogeinträge („30 monatlich“, „90 Minuten
pro Durchlauf“, beide über die KI) sind dazugekommen.

**Zusätzlich gemessene Grenzen** (Regression gegenüber vorher nur beim zweiten und dritten
Punkt):
- Eine fremde Bezugsgröße **hinter** einem Zeitraum rutscht durch: „5 pro Woche und
  Mitarbeiter“ → 260, „30 Minuten pro Woche und Fall“ → 30. Wie E1 ein Restrisiko.
- Eine **Korrektur** mit fremder Bezugsgröße an einem schon gültigen Feld geht still
  verloren: Dauer gültig 60, dann „Korrektur: 30 Minuten pro Fall“ → bleibt 60, keine
  Klärungsfrage (vor (d): `UNKLAR` mit Klärungsfrage). So verhalten sich auch Sperre (b) und
  der feste Schutz. Ziel und nächster Schritt stehen im Abschlussplan.
- **D3 (`step_frequency_per_year`) ist optional und wird nie nachgefragt.** Sperrt (d) dort,
  ist der Wert weg: „Der Schritt läuft je Fall einmal, also etwa 20 mal pro Woche …“ → D3
  `NULL` (ohne (d): 1040). BC2 liest `NULL` nach I8 als „nicht abweichend“ und rechnet mit
  `frequency_per_year`, also zu niedrig, wenn der Schritt mehrmals je Durchlauf läuft. Für D3
  ist die Sperre damit nicht „strenger, nicht anders“ (E4), sondern anders. Fester Schutz und
  Sperre (b) wirken bei D3 schon heute genauso. Im Vertrag (1.5) offen benannt; (d) gilt für
  D3 weiter (entschieden 10.11., siehe ganz unten).
- `wert_roh is None` in der Bedingung ist durch keinen Test unterscheidbar: keine Eingabe,
  die eine Kurzform annimmt, enthält eine fremde Bezugsgröße. Bewusst wie bei (b) gebaut.

**Zur Entscheidung vorgelegt (Befund 2 der Prüfung; entschieden 10.11., siehe ganz unten):** Die Regel sperrt auch Nachrichten
**ohne** fremde Bezugsgröße, und das ist mehr, als Big Picture und E2 sagen („nur wer eine
fremde Bezugsgröße nennt“):
- „je“ im Sinn von „jeweils“ vor einer Zahl: „2 mal im Monat, je 30 Minuten“ (alle Werte
  verworfen; „jeweils 30 Minuten“ ist frei);
- ein Zeitraum mit Zahl dazwischen: „einmal pro zwei Wochen“, „je 2 Wochen“ (vorher 26
  angenommen; „alle zwei Wochen“ ist frei);
- „Pro“ als Produktname: „Mit Buchhaltung Pro, 2 mal im Monat“.

Kosten je Fall: eine Nachfrage, nie ein falscher Wert. „je + Zahl“ freizugeben würde auch
„drei Fälle, je 30 Minuten“ freigeben. Möglich wären: (A) hinnehmen und hier benennen;
(B) zusätzlich eine Zahl zwischen „pro/je“ und Zeitraum erlauben („pro zwei Wochen“), eine
kleine Musteränderung mit eigenem Test. Für E3 dazu (C): ein „/“, auf das „max“ oder wieder
eine Zeiteinheit folgt („Min/Max“, „Minuten/Stunden“), nicht sperren; „Min/Max“ ist bei
Lager- und Einkaufsprozessen eine übliche Angabe.

**E3 umgesetzt (10.11., Go der BC1-Projektleitung).** Anlass: Prüfwerkzeug Szenario 4 mit
echter KI (Code-Stand `f9548c2`), Lauf 9: „30 min/Fall“ → 30 (die KI ließ „/Fall“ weg; (b)
sieht „min“, (d) kennt kein „/“). Regel, wie E3 sie vorsah: Ein „/“ direkt nach einer
Zeiteinheit (dieselben ganzen Wörter wie in Sperre (b): Minute(n), Stunde(n), Viertelstunde,
min, std, h, auch mit Punkt) zählt wie „pro“. Erlaubt sind danach wieder Zeitraum und Lauf (E1).
Teil von `nennt_fremden_bezug`, kein neues Merkmal. Ein freies „/“ ohne Einheit davor
(„Outlook/SAP“, „2/Woche“) bleibt unberührt.

| Nachricht | Muster |
|---|---|
| „30 min/Fall“, „30 Min. / Fall“, „1,5h/Fall“, „2 Std./Vorgang“, „30 Minuten/Lead“, „2 Std/Tag“ | sperrt |
| „30 min/Woche“, „2 Std./Monat“, „90 min/Durchlauf“, „Outlook/SAP, 30 Minuten“, „2/Woche“, „50 km/h“ | frei |

Grenze wie bei (d): „30 min/Woche“ auf eine Dauer-Frage bleibt ungeprüft (E1). Ein „/“ ohne
Zeiteinheit davor wird nicht geprüft, auch nicht bei einer fremden Bezugsgröße: „5/Lead im
Monat“ → 60 (mit „pro“ gesperrt). Selten und nie schlechter als vor E3.

Geprüft (Claude-Prüfer, 0 Critical, 0 Important, 4 Minor): `_FREMDER_BEZUG_MUSTER` nach dem
Zusammenlegen zeichengleich; Systemlisten, „km/h“, Datumsangaben und Brüche bleiben frei;
Testlücken (weitere Einheiten, Leerraum nach „/“) und Texte (Vertrag, Schema, Spec)
nachgezogen. **Zu weit (entschieden 10.11., siehe ganz unten):** E3 sperrte auch „Min/Max“
(„2 mal pro Woche, dabei prüfen wir die Min/Max-Bestände in SAP“ → D1 und SAP verworfen, beim
gleichen Satz noch einmal D1 `ungeloest`), „24h/7“, abgekürzte Zeiträume („2 Std./Wo.“) und
„Minuten/Stunden“. Kosten wie bei (d): Nachfragen, im schlechtesten Fall `NULL`, nie ein
falscher Wert.

**Zur Entscheidung vorgelegt (D3, Nachprüfung N1; entschieden 10.11., siehe unten):** (A) (d) gilt für D3 wie für D1, so gebaut
und im Vertrag benannt, gleiches Verhalten wie Fester Schutz und (b). (B) (d) nur dort, wo
eine Nachfrage folgen kann, also nur für Pflichtfelder: ein generisches Merkmal der Feldangabe
(`required`), kein Feldname. Dann bliebe ein D3-Wert wie „20 pro Woche“ erhalten, aber auch
ein falsch umgerechneter („3 mal pro Fall, 20 Fälle pro Woche“ → KI „3 pro Woche“ statt
„60 pro Woche“; Sperre (b) lässt ihn durch, weil die Nachricht „Woche“ nennt).

**Entschieden 10.11.2026 (BC1-Projektleitung):**
- **D3: (A).** (d) gilt für D3 wie gebaut; der Vertrag 1.5 benennt die Folge.
- **Zu weite Sperre: (A)** für „je“ im Sinn von „jeweils“, „pro zwei Wochen“ und „Pro“ als
  Produktname: hingenommen, je eine Nachfrage.
- **(C) für E3:** Ein „/“ nach einer Zeiteinheit, auf das „max“ oder wieder eine Zeiteinheit
  folgt, sperrt nicht („Min/Max-Bestände“, „min./max.“, „Min.-/Max.-Bestand“,
  „Minuten/Stunden“, „Std/Min-Abrechnung“). Weiter gesperrt (A): „24h/7“, abgekürzte
  Zeiträume („2 Std./Wo.“). Mit Katalogeintrag „2 mal pro Woche, dabei prüfen wir Min/Max in
  SAP“ (`frequency_per_year`, fest „Nachfrage“, KI 104). Hingenommene Grenze (Kurzprüfung):
  Eine Rate je Zeiteinheit bleibt damit frei („15 Minuten/Stunde“ → 15; mit „pro“ gesperrt),
  weil das Muster eine Rate nicht von einer Alternative („Minuten/Stunden“) unterscheidet.
  Selten, und als Antwort auf „Wie lange dauert ein Durchlauf?“ ungewöhnlich.
