# Spec — Kurzantworten landen im gefragten Feld

> Stand 29.10.2026, Entwurf 3. Anlass: Befund aus der Generalprobe auf BC0s Server (Testanfrage A-2026-07, 29.10.).
> - **Quellen:** gespeicherte Sitzung und Profil der Generalprobe (nur lesend gemessen), BC1-Log vom Server, Spec C1a Abschnitt „Grenzen“ (24.10.: „Extraktor kennt die zuletzt gestellte Frage nicht … vorbestehend“).
> - **Geprüft:** Entwurf 1 von einem unabhängigen Claude-Prüfer (1 Critical, 3 Important, 11 Minor) und von Codex (0 Critical, 4 Important, 3 Minor); beide fanden denselben Kernfehler. Entwurf 2 von agy (1 Critical, 3 Important, 4 Minor; einige Code-Angaben in agys Bericht sind erfunden, die Befunde selbst sind am Code nachgeprüft). Entwurf 3 arbeitet alles ein (Abschnitt 8).
> - **Status:** abgenommen von der BC1-Projektleitung am 29.10.2026, alle drei Entscheidungen in Abschnitt 7 wie empfohlen. Gebaut auf Zweig `bc1-extraktion-gestellte-frage`.
> - **Nachtrag 29.10.2026:** „x“ wie „mal“ (z. B. „2x pro Monat“), Entscheidung der BC1-Projektleitung nach der Gesamtprüfung.
> - **Nächster Schritt:** Gebaut und gesamtgeprüft; Push/PR nach OK der BC1-Projektleitung, dann Ausrollen und zweite Generalprobe.

## Big Picture

**Was passiert ist.** In der Generalprobe hat die befragte Person viele Fragen knapp beantwortet: „1“, „3 Stunden“, „70“, „2“, „4“, „Ja“. BC1 hat diese Antworten keinem Feld zugeordnet, die Frage wiederholt und das Feld nach dem zweiten Versuch aufgegeben.

| Messgröße | Wert |
|---|---|
| Pflichtfelder gültig | 18 von 26 |
| Pflichtfelder aufgegeben („ungelöst“) | 8, alle mit festem Antworttyp (Anzahl, Dauer, Prozent, Skala, Ja/Nein) |
| Vollständigkeit des Profils | 0,69 |
| Falsch gespeicherter Wert | Gesamtdauer 180 statt 2400 Minuten |

Antworten mit eigenem Zusammenhang kamen an, etwa „2 mal pro Monat“ oder „Ja müssen zwischen Systemen wechseln“.

**Ursache.** BC1 lässt eine KI die Werte aus jeder Nachricht ziehen. Diese KI bekommt nur die Liste aller Felder und die Nachricht, nicht die Frage, die BC1 gerade gestellt hat (im Code nachgewiesen). Ein nacktes „4“ gehört so zu keinem bestimmten Feld. Gemessen: Keine der nackten Kurzantworten hat einem Feld einen Wert oder Kandidaten gegeben. Einzige Ausnahme war „3 Stunden“, gemeint als Dauer des Schritts: Die KI ordnete es der Gesamtdauer zu. BC1 fragte die Gesamtdauer deshalb zur Klärung erneut, und die nächste Antwort „3 Stunden“ bestätigte den falschen Wert.

Die Lücke ist seit Spec C1a (24.10.) bekannt, wurde dort nur für die Rollenfrage umgangen und nicht im Abschlussplan nachgehalten.

**Ziel.** Eine Kurzantwort auf die gestellte Frage landet zuverlässig in genau diesem Feld, ohne dass BC1 etwas dazuerfindet. Alles andere wirkt wie bisher: Eine längere Nachricht kann viele Felder auf einmal füllen.

**Lösung.** BC1 merkt sich, welches Feld es zuletzt gefragt hat. Besteht die Antwort **nur** aus einem Wert in der Form, die dieses Feld erwartet, übernimmt BC1 ihn direkt für dieses Feld, ohne KI. Beispiele: „4“ auf eine Frage mit Skala 1–5, „Ja“ auf eine Ja-Nein-Frage, „3 Stunden“ auf eine Dauer, „2 pro Monat“ auf eine Häufigkeit. Jede andere Antwort geht wie bisher an die KI.

Was als „nur der Wert“ gilt, ist je Antworttyp fest und eng beschrieben (Abschnitt 3). Bei Dauer und Häufigkeit gehört die Einheit dazu: Ein nacktes „40“ oder „2“ übernimmt BC1 nicht, weil sonst eine Einheit erfunden wäre. Solche Antworten gehen wie heute an die KI; wer im Gespräch antwortet, sollte Dauer und Häufigkeit deshalb mit Einheit nennen.

**Nicht-Ziele.**
- Die KI selbst über die gestellte Frage informieren. Das bleibt mit Ziel in der Roadmap (Abschnitt 6); der gemessene Befund betrifft nur Kurzantworten mit festem Typ.
- Den Anfragetext aus BC0s Formular „Neue Anfrage“ als Gesprächsbeginn nutzen (Roadmap).
- Den Dialog umbauen (Reihenfolge, zwei Versuche je Feld, Abschluss, Zähler „X von 26“).
- Neue Felder, neue Fragetexte, Datenbank- oder Vertragsänderung.

**Anti-Ziele (Fehlschlag, auch wenn es technisch läuft).**
- Eine Antwort landet still im falschen Feld, wie die Gesamtdauer in der Generalprobe.
- BC1 erfindet etwas, das die Nachricht nicht trägt, etwa eine Einheit.
- Die neue Regel umgeht die bestehenden Regeln für Klärung und Korrektur.
- Eine längere Antwort verliert Werte, weil die neue Regel sie für eine Kurzantwort hält.

**Erfolg.**
- Ein Test spielt das Gespräch der Generalprobe in sauberer Reihenfolge nach (Startnachricht plus 15 Kurzantworten) mit einer Test-KI, die bei Kurzantworten nichts liefert. Je Turn ist das gefragte Feld das erwartete, am Ende sind alle 26 Pflichtfelder gültig mit den erwarteten Werten, darunter Gesamtdauer 2400.
- Eine zweite Generalprobe auf BC0s Server mit Kurzantworten endet mit 26 von 26 und Vollständigkeit 1,0.

## Technischer Teil

### 1. Das zuletzt gefragte Feld (`bc1_core/core.py`)

Neue reine Funktion `zuletzt_gefragt(state) -> str | None`:
- läuft `state.raw_log` rückwärts,
- nimmt den ersten Eintrag, zu dem `state.antworten` eine Antwort hat,
- gibt `payload.get("feld")` zurück, wenn `antwort.get("status") == "frage"`, sonst `None`.

Begründung: `raw_log` ist eine Liste und behält ihre Reihenfolge auch als `jsonb`; `state.antworten` ist ein Dict und tut das nicht. Jede Antwort mit Status `frage` trägt das gefragte Feld bereits (`core.py`, Antwort-Payload `feld`). Die aktuelle Nachricht steht während der Verarbeitung nie in `antworten` und wird deshalb von selbst übersprungen. Kein neues Feld im Sitzungszustand.

Geprüft für alle Pfade von `process_turn` (beide Prüfer bestätigen):
- erster Turn: `None`;
- nach einer Nachfrage: dasselbe Feld;
- nach `fehler_fortsetzbar` (wird nicht in `antworten` gespeichert), mit gleicher oder neuer `message_id`: die Frage davor;
- Fortsetzen nach Absturz (`message = state.raw_log[-1][1]`; Einträge sind Paare aus `message_id` und Text): dasselbe Ergebnis, mit dem geloggten, PII-gefilterten Text;
- Idempotenz-Replay, überholter Turn, Endzustand, Recovery-Replay und Abschluss-Nachholen über das Terminal-Gate (`api.py`): kehren vor der Extraktion zurück, die Funktion wird dort nicht gebraucht.

**Voraussetzung:** Der Client zeigt immer die Antwort auf die zuletzt gesendete Nachricht als aktuelle Frage, nie die gespeicherte Antwort einer älteren Nachricht. So ist es mit BC0 vereinbart (Brief vom 27.10.: bei Störung nur „Erneut senden“ derselben Nachricht).

### 2. Die Regel für Kurzantworten (`bc1_core/extractor.py`)

`extract_and_merge(state, message, message_id, package, llm, *, gefragt: FieldSpec | None = None)`; `process_turn` bestimmt `gefragt` über `zuletzt_gefragt` und `package.field(...)`.

- **Vor** dem Aufruf der KI: Hat der Typ von `gefragt` eine Kurzform (Abschnitt 3) und liefert sie für `message` einen reinen Wert, entsteht genau ein Kandidat `(gefragt.name, reiner_wert)`. Die KI wird für diese Nachricht nicht gefragt.
- Sonst ruft BC1 die KI auf, unverändert wie heute.
- Der Kandidat läuft durch das **bestehende** Zusammenführen: Normalisieren, Klärung bei `unklar`, Korrektur bei `ungueltig`, Konflikt bei abweichendem gültigem Wert. Keine Abkürzung daran vorbei.
- Protokoll: neue Zeile `kurzantwort_direkt korrelation=… feld=…` auf `bc1.kern`, Stufe INFO, nur der Feldname, nie der Wert (B7 Teil 2). Auf solchen Turns fehlt die Zeile `ki_aufruf … art=extraktion`; das ist gewollt. Die Zeile kommt in die Tabelle „Betriebsprotokoll“ der README.
- Die Regel arbeitet auf dem Text, den auch die KI bekäme: nach dem PII-Filter. Eine Telefonnummer ist dort schon `[Telefon A]` und keine Kurzform mehr.

Einfacher als Entwurf 1: Die KI wird nicht erst gefragt und dann verworfen. Das spart den Extraktionsaufruf. Der Turn ruft weiterhin `llm.antworte` auf; scheitert die KI dort, wird der Stand verworfen und der Retry übernimmt die Kurzantwort ohne Extraktion.

### 3. Was als Kurzform gilt (`bc1_core/feldtypen.py`, `bc1_service/paket_feldtypen.py`)

Ein optionales Merkmal `kurzform` am `Feldtyp`: eine Funktion, die für eine Nachricht entweder den **reinen Wert** liefert oder `None`. **Vorgabe: keine Kurzform.** Nur die Typen unten bekommen eine. Ein neuer oder vergessener Typ nimmt damit nie an der Regel teil.

Der reine Wert ist das, was die KI bei einer guten Extraktion liefern würde, etwa „70“ aus „ca. 70 %“ oder „4“ aus „4.“. Er läuft danach durch den bestehenden Normalisierer und Prüfer des Typs. Diese bleiben unverändert. Ohne diesen Schritt würde „ca. 70 %“ als Kurzform erkannt und dann vom bestehenden Prozent-Normalisierer als „ungültig“ abgelehnt (gemessen).

Für alle Kurzformen gilt:
- Die Nachricht besteht, nach Abschneiden von Leerraum, nur aus der beschriebenen Form. Geprüft wird per vollständigem Muster, nicht über die Normalisierer; die ziehen eine Zahl auch aus langen Sätzen.
- Am Ende ist höchstens ein „.“ oder „!“ erlaubt. Der Punkt einer Abkürzung („Min.“, „Std.“) zählt als dieser eine Punkt; „90 min..“ ist keine Kurzform.
- Ein „?“ irgendwo schließt die Kurzform aus.
- Näherungswörter vorn sind erlaubt, dieselbe Liste wie in `_ANZAHL_MUSTER`: etwa, ca. (auch ohne Punkt), circa, ungefähr, ungefaehr, rund, im Schnitt, durchschnittlich. Am besten als eine gemeinsame Konstante.
- Zwischen Zahl und Einheit oder „%“ ist Leerraum erlaubt, aber nicht nötig („45min“, „70%“). Vor dem Wort „Prozent“ steht Leerraum.

| Typ | Kurzform | reiner Wert | Beispiele ja | Beispiele nein |
|---|---|---|---|---|
| `JA_NEIN` | „ja“ oder „nein“, Groß/Klein egal | ja / nein | „Ja“, „nein.“ | „Ja, aber selten“, „ja?“ |
| `SKALA_1_5` | eine Ziffer 1–5 | die Ziffer | „4“, „4.“ | „eher 4“, „4 von 5“ |
| `PROZENT_0_100`, `PROZENT_GANZ_0_100` | wahlweise Näherungswort, Zahl, wahlweise „%“ oder „Prozent“ | die Zahl | „70“, „ca. 70 %“, „70 Prozent“, „70%“ | „70 bis 80“ |
| `ANZAHL` | das bestehende vollständige Muster `_ANZAHL_MUSTER` | das Zahl-Token (Normalisierung folgt) | „1“, „etwa 3 Fälle“ | „5 pro Woche“ |
| `AUSWAHL(...)` | genau eine Option, Groß/Klein egal | die Option | „geschaetzt“, „KP-04.TP-4“ | „KP-04.TP-4?“, „Phasen-Abschluss“ |
| `MINUTEN` | wahlweise Näherungswort, Zahl, **Pflicht-Einheit**: Minute(n), min, Min., Stunde(n), Std., h | Zahl mit Einheit | „3 Stunden“, „ca 90 Min.“, „45min“, „1,5h“ | „3“, „Der Prozess dauert 3 Stunden“, „nicht 3 Stunden“ |
| `ZAHL` (Häufigkeit) | wahlweise Näherungswort, Zahl, wahlweise „mal“ oder „x“ (auch „2mal“, „2-mal“, „2x“), dann „pro“, „im“ oder „je“ und Woche, Monat oder Jahr | Zahl mit Zeitraum | „2 pro Monat“, „2mal im Monat“, „2x pro Monat“ | „2“, „2 mal pro Monat, im Dezember mehr“ |
| `FREITEXT`, `LISTE`, Systemtyp, alle übrigen | keine Kurzform | — | — | — |

Eine Kurzform kann einen Wert liefern, den der Prüfer danach ablehnt, etwa „150 %“ oder bei ganzzahligen Prozent „70,5 %“. Das Feld wird dann wie heute `ungueltig`, und BC1 fragt nach; die KI wird auch dann nicht gefragt.

Das identitätskritische Feld `focus_step` (Auswahl der Teilprozess-IDs) muss nicht ausgenommen werden: Eine genaue ID liefert denselben gültigen Kandidaten wie die KI; ein Name oder eine ID mit „?“ ist keine Kurzform und geht an die KI.

Berührt der Bau `_ZAHL_TOKEN`, gilt die Rückstellung (4)(b) im Abschlussplan.

### 4. Fragetexte bleiben unverändert

Entwurf 2 schlug vor, dass die Dauer-Fragen E1 und E2 die Einheit nennen. Die Fragetexte stehen aber wörtlich im Vertrag mit BC2 (`contracts/bc1-to-bc2/README.md`, `prozessprofil.schema.json`) und in der Spalte-zu-Feld-Tabelle. Eine Änderung wäre eine Vertragsänderung, die mit BC2 abgestimmt werden muss; BC2 antwortet in #286 seit dem 24.10. nicht.

Deshalb jetzt: Fragetexte und Paketfassung bleiben gleich (Entscheidung 7.2). Eine nackte Zahl auf eine Dauer- oder Häufigkeitsfrage geht wie heute an die KI. Liefert sie nichts, fragt BC1 nach; die Nachfrage formuliert die Frage konkreter. Für die Vorführung bekommt die befragte Person den Hinweis, Dauer und Häufigkeit mit Einheit zu nennen. Die Einheit in den Fragetexten bleibt mit Ziel in der Roadmap (Abschnitt 6).

### 5. Tests (Test zuerst, gegen die Test-KI)

1. `zuletzt_gefragt`: erster Turn; nach Frage; nach Nachfrage; nach `fehler_fortsetzbar` mit gleicher und mit neuer `message_id`; Fortsetzen nach Absturz; mehrere unbeantwortete Einträge; neueste gespeicherte Antwort ist keine Frage; nach JSON-Rundreise mit anders sortiertem `antworten`.
2. Kurzform je Typ: alle Ja- und Nein-Beispiele und reinen Werte aus der Tabelle in Abschnitt 3, dazu Fragezeichen, Verneinung, zweite Zahl, Satz mit genau einer Zahl samt Einheit, „90 min..“, alle Näherungswörter.
3. Regel greift: Kurzantwort, die Test-KI wird **nicht** aufgerufen, das Feld ist gültig mit dem erwarteten Wert („ca. 70 %“ → 70, „4.“ → 4, „1,5h“ → 90, „2mal im Monat“ → 24).
4. Regel greift, Wert ungültig: „150 %“ bzw. „70,5 %“ bei ganzzahligen Prozent → Feld `ungueltig`, die Test-KI wird nicht aufgerufen.
5. Regel greift nicht bei längerer Nachricht mit genau einer Zahl samt Einheit: KI wird aufgerufen, ihre Kandidaten bleiben erhalten.
6. Regel greift nicht bei freien Typen und nicht ohne gefragtes Feld (erster Turn, Startnachricht).
7. Zusammenführen über die Regel: bei `unklar` den bisherigen Wert bestätigen, einen Kandidaten bestätigen, einen dritten Wert nennen; bei `ungueltig` korrigieren; Quellen, Kandidaten und Nachfragezähler prüfen.
8. Der Fall der Generalprobe: Schrittdauer gefragt, „3 Stunden“ → Schrittdauer 180, Gesamtdauer unverändert.
9. `focus_step` mit Kontext: genaue ID → gültig über die Regel; Name, unbekannte ID, ID mit „?“ → Weg über die KI.
10. Integration über `process_turn`: Absturz mit verändertem Retry-Body nutzt den geloggten Text; Fehler bei der Antwortformulierung; Replays und Abschluss-Nachholen lösen keine neue Extraktion aus.
11. PII: Eine Telefonnummer („015112345678“) als Antwort auf die **Anzahl**-Frage wird über `process_turn` keine Kurzform (ohne PII-Filter wäre sie eine). Die Protokollzeile `kurzantwort_direkt` trägt nur den Feldnamen, und auf diesem Turn fehlt `ki_aufruf … art=extraktion`.
12. Nachspiel der Generalprobe mit Paket samt BC0-Kontext (Testmandant aus der bestehenden Test-Fixture): Startnachricht (Test-KI liefert ihre Felder), dann die 15 Kurzantworten in sauberer Reihenfolge, Dauern mit Einheit, `focus_step` als ID. Je Turn das erwartete gefragte Feld, am Ende alle 26 Werte; kein Feld trägt eine Kurzantwort als Quelle, die nicht zu ihm gehört.

### 6. Roadmap (im Abschlussplan nachtragen, je mit Ziel und nächstem Schritt)

- **Erledigt durch diese Spec:** Kurzantworten mit festem Typ (aus der Grenze in Spec C1a).
- **KI kennt die gestellte Frage.** Ziel: auch Sätze mit unklarem Bezug („eher so drei Stunden“) und Kurzantworten auf Freitext- und Listenfelder landen im gefragten Feld. Nächster Schritt: nach der Vorführung an den Live-Gesprächen bewerten, ob es nötig ist. Offen dabei: ob ein „Ja“ einen in der Frage vorgeschlagenen Wert übernimmt (Abschlussplan „Neu 24.10. — aus C1a“ (g)).
- **Einheit in den Dauer-Fragen.** Ziel: nackte Zahlen auf Dauer-Fragen werden selten. Nächster Schritt: Fragetexte E1/E2 zusammen mit den Vertragstexten in #286 mit BC2 abstimmen.
- **Anfragetext als Gesprächsbeginn.** Ziel: Was die Person in „Neue Anfrage“ schon beschrieben hat, muss sie im Gespräch nicht wiederholen. Nächster Schritt: mit BC0 klären, ob deren Weiterleitung den Originaltext als ersten Turn schicken kann.
- **Klärungsfrage nennt die Kandidaten.** Ziel: Bei einem Widerspruch („40 oder 3 Stunden?“) sieht die Person beide Werte. Nächster Schritt: nach der Vorführung bewerten.
- **Hinweis, wenn BC1 ein Pflichtfeld aufgibt.** Ziel: kein stilles Weitergehen. Nächster Schritt: nach der Vorführung bewerten.

### 7. Entscheidungen für die BC1-Projektleitung

1. **Nur die feste Regel jetzt, KI-Kontext später** (Empfehlung). Sie behebt den gemessenen Befund vollständig und ohne KI-Abhängigkeit. Der KI-Kontext bringt eine offene Grundsatzfrage mit („Ja auf einen Vorschlag“, Roadmap in Abschnitt 6) und berührt alle drei KI-Adapter.
2. **Dauer und Häufigkeit nur mit Einheit bzw. Zeitraum; Fragetexte und Paketfassung bleiben gleich** (Empfehlung). Die Alternative, die Einheit in die Dauer-Fragen zu schreiben, ändert Vertragstexte mit BC2 und braucht deren Abstimmung.
3. **Zweite Generalprobe an KP-02.TP-2 oder KP-03.TP-1** (beide von BC0 genannt, ohne BC1-Profil), nicht an KP-04.TP-4.

### 8. Prüfung und was daraus wurde

| Befund | Prüfer | Ergebnis |
|---|---|---|
| Regel prüfte nur, ob der Normalisierer einen gültigen Wert findet; bei Dauer und Häufigkeit wird eine Zahl auch aus langen Sätzen gezogen (selbst gemessen) | Claude (Critical), Codex (Important) | eigene, enge Kurzform je Typ (Abschnitt 3) |
| Nackte Zahl bekäme eine erfundene Einheit („40“ → 40 Minuten, „2“ → 2 pro Jahr; selbst gemessen) | Claude, Codex (Important) | Einheit bzw. Zeitraum Pflicht in der Kurzform |
| Ausschlussliste freier Typen ist unsicher | Claude (Important) | Freischaltung je Typ, Vorgabe aus |
| KI-Kontext öffnet die ungeklärte Frage „Ja auf Vorschlag“ | Claude (Important) | KI-Kontext in die Roadmap |
| Frageformulierung kann Einheit oder Bezug ändern | Codex (Important) | Einheit Pflicht in der Kurzform |
| Älterer Replay könnte eine alte Frage wieder anzeigen | Codex (Important) | Voraussetzung benannt (Abschnitt 1) |
| Testliste zu dünn | Claude, Codex | Abschnitt 5 erweitert |
| KI erst fragen, dann verwerfen ist unnötig | Claude, Codex (Minor) | Regel vor dem KI-Aufruf |
| `zuletzt_gefragt` braucht keine `message_id`; robust lesen | Claude (Minor) | übernommen |
| Ursache am Log allein nicht belegt | Claude, Codex (Minor) | Quellen je Nachricht gemessen (Big Picture) |
| Kurzform erkannt, aber bestehender Normalisierer lehnt ab („ca. 70 %“, „70 Prozent“, „70.“, „4.“; selbst gemessen) | agy (Critical) | Kurzform liefert den reinen Wert (Abschnitt 3) |
| Liste der Näherungswörter kürzer als die bestehende | agy (Important) | gleiche Liste, gemeinsame Konstante |
| Leerraum zwischen Zahl und Einheit, Abkürzungspunkt | agy (Important) | Regeln in Abschnitt 3 |
| PII-Test wirkungslos bei Häufigkeit; wirksam bei Anzahl (selbst gemessen) | agy (Important) | Test 11 über die Anzahl-Frage |
| Fragetexte E1/E2 stehen wörtlich im Vertrag mit BC2 (selbst geprüft) | agy (Minor) | Fragetexte bleiben, Roadmap (Abschnitt 4) |
| Neue Logzeile fehlt in der README | agy (Minor) | in Abschnitt 2 aufgenommen |
| Ungültige Kurzantwort nicht getestet | agy (Minor) | Test 4 |
| Spec nennt konkrete Test-IDs und Schrittnamen, Repo öffentlich | Claude (Minor) | Testdaten des Testmandanten, wie in früheren Specs; vor dem Push geprüft |
| agys Angaben zu `choose_next_field`, `state.fields`, Rollen in `raw_log`, Paketfassung 1.3, `baue_extraktions_nachricht` | agy | erfunden, nicht übernommen |
