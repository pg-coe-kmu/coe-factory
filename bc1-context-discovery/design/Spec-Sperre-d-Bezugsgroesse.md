# Spec: Sperre (d) — fremde Bezugsgröße bei Häufigkeit und Dauer

> Entwurf 2, 09.11.2026 (nach unabhängiger Prüfung: 0 Critical, 3 Important, 6 Minor, alle
> eingearbeitet). Ergänzt `Spec-Antwortformen.md`, Abschnitt 2, „Feste Sperren“ (a)–(c).
> Herkunft: `Abschlussplan-BC1.md`, Kleinpunkte „Neu 09.11.“ (1). **Wartet auf Abnahme.**

## Big Picture

**Das Problem.** Auf die Frage „Wie lange dauert ein einzelner Lauf dieses Schritts?“ antwortet
jemand „30 Minuten pro Fall“. Ob ein Lauf genau einen Fall bearbeitet, steht nicht fest. Die KI
macht trotzdem „30 Minuten“ daraus, und BC1 übernimmt den Wert still als 30 Minuten je Lauf. So
geschehen im Prüfwerkzeug am 30.10. (Szenario 4). Die Prompt-Regel „andere Bezugsgröße:
weglassen“ hält die KI nicht zuverlässig auf. Sperre (b) greift nicht, weil die Nachricht die
Einheit „Minuten“ nennt.

**Die Regel.** Steht in der Nachricht „pro“ oder „je“, dem keine zur Frage passende Bezugsgröße
folgt, nimmt BC1 den KI-Wert für Häufigkeit oder Dauer nicht an und fragt nach. Passend ist bei
der Häufigkeit ein Zeitraum (Woche, Monat, Jahr), bei der Dauer ein Lauf („Lauf“, „Durchlauf“,
„Prozessdurchlauf“).

**Was sich für die Person ändert.** In seltenen Fällen eine Nachfrage mehr. Wiederholt sie dann
ihren Satz statt einer kurzen Antwort, bleibt das Feld nach zwei Nachfragen offen (`NULL` für
BC2, wie heute schon bei unbekannten Perioden). Kurze Antworten wie „2 mal pro Woche“ oder
„30 Minuten“ laufen wie bisher ohne KI und sind nicht betroffen.

**Was die Regel nicht kann.** Sie verhindert, dass BC1 einen solchen KI-Wert still übernimmt.
Antwortet die Person auf die Nachfrage „30 Minuten“, meint aber weiter „pro Fall“, gilt der
Wert; das kann keine Regel erkennen. Formulierungen ohne „pro“ oder „je“ („jeder Fall dauert
30 Minuten“, „jeweils 30 Minuten“, „30 min/Fall“) schützt weiter nur der Prompt.

## Entscheidungen (zur Abnahme)

| # | Frage | Empfehlung | Warum |
|---|---|---|---|
| E1 | Gilt die Sperre bei der Dauer auch für Zeiträume („2 Stunden pro Woche“)? | **Ja.** Bei der Dauer passt nur der Lauf. | „2 Stunden pro Woche“ ist eine Summe je Woche, keine Dauer je Lauf. Ohne die Sperre würde daraus still 120 Minuten je Lauf. |
| E2 | Ein Satz mit zwei Angaben („Einmal pro Woche, ein Durchlauf dauert 3 Stunden“) verliert den KI-Wert der Dauer; „2 mal pro Woche, pro Durchlauf etwa 20 Fälle“ den der Häufigkeit. Hinnehmen oder genauer zuordnen? | **Hinnehmen.** | Die Regel wirkt wie (b) auf die ganze Nachricht. Eine Zuordnung „welches ‚pro‘ gehört zu welcher Zahl“ wäre neue, fehleranfällige Logik. Kosten: eine Nachfrage, im schlechtesten Fall ein offenes Feld; nie ein falscher Wert. Gemessen wird das über neue Katalogeinträge (unten). |
| E3 | „/“ als Bezug („30 min/Fall“)? | **Nicht jetzt.** Ziel: kein falscher Wert aus „min/…“. Nächster Schritt: Katalogeintrag „30 min/Fall“ (KI: Nachfrage); zeigt Szenario 4 einen Durchrutscher, eine Sperre an der Einheit („min/…“, „Std./…“, „h/…“) bauen. | Bisher nicht beobachtet. Ein freies „/“ stünde auch in Systemlisten („Outlook/SAP“); eine Form an der Einheit hätte diesen Fehlalarm nicht, ist aber ohne Anlass Vorrat. |
| E4 | Der Vertrag mit BC2 beschreibt heute das Gegenteil: „‚90 Minuten pro Fall‘ → `90`“ und „Zusätze zur Bezugsgröße verworfen“ (`contracts/bc1-to-bc2/README.md`), „von BC1 nicht geprüft“ (`prozessprofil.schema.json`, Beschreibung von `total_duration_minutes`). | **Die Texte im selben PR ändern (Fassung 1.5, nur Text), Hinweis an BC2 in #286 vor dem Ausrollen.** Nicht auf BC2s Antwort warten. | Die Normalisierung ist Vertragsbestandteil und wird nicht ohne Hinweis an BC2 geändert. Für BC2 wird es strenger, nicht anders: statt eines still übernommenen Werts im seltenen Fall `NULL`. Struktur, Typen und `lesen.sql` bleiben. Hängt am Roadmap-Punkt „BC2-Texte angleichen“ (Kleinpunkte „Neu 30.10.“ (4)). |

## Technischer Teil

**Ort.** `bc1_core/extractor.py`, `extract_and_merge`, im KI-Zweig (`wert_roh is None`) direkt
nach Sperre (b), mit `continue` wie dort. Die Kurzform bleibt unberührt: Ihre Grammatik nimmt
„30 Minuten pro Fall“ schon heute nicht an (Spec-Antwortformen 3.4).

**Woran die Sperre hängt.** Wie (b) an einem Merkmal des Feldtyps, nie am Feldnamen: neues Feld
`Feldtyp.fremder_bezug: Callable[[str], bool] | None` (Muster: `nennt_einheit`). Gesetzt nur bei
`ZAHL` und `MINUTEN`; alle anderen Typen bleiben `None`.

**Erkennen: Negativform, wiederverwendet.** Wie das frühere `_PRO_MUSTER` (Codex Fix-Welle 5,
bis `82e10ce^` in `bc1_core/feldtypen.py`): jedes ganze Wort „pro“ oder „je“ im
Vergleichsschlüssel der Nachricht, dem **nicht** Leerraum und eine passende Form folgen, sperrt.
So sperren auch ein zweites Vorkommen, Satzzeichen direkt danach („pro (einzelnem) Fall“,
„pro „Fall““) und „je“ vor einer Zahl.
- `ZAHL`: `(?<![a-z])(?:pro|je)(?!\s+(?:woche|wochen|monat|monate|monaten|jahr|jahre|jahren)(?![a-z]))(?![a-z])` — dieselben ganzen Wortformen wie Sperre (b) (`_ZEITRAUM_MUSTER`), also „Wochentag“ und „Wochenende“ nicht.
- `MINUTEN`: `(?<![a-z])(?:pro|je)(?!\s+[a-z]*lauf(?![a-z]))(?![a-z])` — ein Wort, das auf „lauf“ endet („Lauf“, „Durchlauf“, „Prozessdurchlauf“, „Zahlungslauf“), „Laufzettel“ nicht.

**Beispiele (werden Tests; Gegenprobe mit dem Muster oben gelaufen).**

| Nachricht | Feldtyp | KI-Kandidat | Ergebnis |
|---|---|---|---|
| „30 Minuten pro Fall“ | MINUTEN | „30 Minuten“ | verworfen |
| „30 Minuten pro (einzelnem) Fall“ | MINUTEN | „30 Minuten“ | verworfen |
| „je Vorgang etwa eine halbe Stunde“ | MINUTEN | „30 Minuten“ | verworfen |
| „2 Stunden pro Woche“ | MINUTEN | „2 Stunden“ | verworfen (E1) |
| „drei Fälle, je 30 Minuten“ | MINUTEN | „30 Minuten“ | verworfen |
| „90 Minuten pro Durchlauf“ | MINUTEN | „90 Minuten“ | angenommen |
| „pro Prozessdurchlauf etwa 90 Minuten“ | MINUTEN | „90 Minuten“ | angenommen |
| „pro Laufzettel 5 Minuten“ | MINUTEN | „5 Minuten“ | verworfen |
| „20 Leads pro Woche“ | ZAHL | „20 pro Woche“ | angenommen (Bestandstest) |
| „5 pro Lead im Monat“ | ZAHL | „5 pro Monat“ | verworfen |
| „2 pro Wochentag“ | ZAHL | „10 pro Woche“ | verworfen |
| „je nach Saison 2 mal im Monat“ | ZAHL | „2 pro Monat“ | verworfen (Einschränkung; die Prompt-Regel sagt dort schon „weglassen“) |
| „2 mal pro Woche, je Lauf 30 Minuten“ | ZAHL / MINUTEN | beide | beide verworfen (E2) |
| „Prozess läuft wöchentlich“ | ZAHL | „1 pro Woche“ | angenommen (kein „pro/je“) |

**Bewusst hingenommen (je eine Nachfrage):** Wörter aus der Frage zwischen „pro“ und „Lauf“
(„pro komplettem Durchlauf“, „pro einzelnem Lauf“), „pro Ausführung“, „pro Durchgang“,
„je nach …“, „je mehr … desto“. Eine Zulassung von Zwischenwörtern brächte neue Lücken.

**Bekannte Grenze.** Im kontextfreien Zweig (Fassung 1.0, nur Demo und Tests) ist D4 vom Typ
`ZAHL` und fragt „pro Durchlauf“; dort passen die Formen nicht zur Frage. Harmlos: Der
Normalisierer lehnt den Wert ohnehin ab, und der Betrieb lädt immer den BC0-Kontext.

**Folgen.**
- Paket-Fingerabdruck und `schema_version` bleiben (der Fingerabdruck enthält nur den Kontext).
  Vor dem Update trotzdem messen (`betrieb/BETRIEB.md`, Abschnitt 4).
- Antwortkatalog `tests/daten/antwortkatalog.json`: „30 Minuten pro Lead“ und „30 Minuten pro
  Fall“ stehen dort schon als „KI: Nachfrage“; die Sperre setzt das im Code durch. Neu als
  „KI: Nachfrage“ für Szenario 4: zwei Kombi-Antworten aus E2 und „30 min/Fall“ (E3).
  `test_antwortkatalog.py` ruft `extract_and_merge` nicht auf; die Sperre selbst prüfen
  Einheitstests in `tests/test_extractor_sperren.py` und Szenario 4.
- Der ZAHL-Teil ist vorbeugend; beobachtet ist nur der Dauer-Fall.
- Prompt: unverändert (die Regel steht dort schon).
- Vertrag (E4): `contracts/bc1-to-bc2/README.md` und die Beschreibung in
  `prozessprofil.schema.json`, Fassung 1.5; Entwurf des Hinweises an BC2 liegt lokal vor,
  Versand nur mit OK.
- Prüfwerkzeug nach dem Bau: Szenario 4 zweimal (`betrieb/BETRIEB.md`, Abschnitt 8). Dabei
  prüfen, ob die Nachfrage zu E1/E2 „Lauf“ bzw. „Durchlauf“ nennt.
- Ausrollen nur mit Ansage an BC0 und vor der Probe zur Endpräsentation, nicht danach
  (24-Stunden-Ruhe).

**Nicht Teil dieser Spec.** „/“ als Bezug (E3); Formulierungen ohne „pro“/„je“; zwei erlaubte
Zeiträume in einer Nachricht („pro Woche … pro Monat“), die die KI zu einem sauberen Wert
macht (früher lehnte das der Normalisierer ab, heute schützt nur der Prompt); eine Zuordnung
je Zahl (E2).
