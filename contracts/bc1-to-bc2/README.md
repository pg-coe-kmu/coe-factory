# BC1 → BC2 · Prozessprofil

Was BC1 in die gemeinsame Datenbank geschrieben haben muss, bevor BC2 rechnet — und
wie BC2 es liest. Entschieden in
[#184](https://github.com/pg-coe-kmu/coe-factory/issues/184).

> **Dieser Vertrag ist gegen die Wirklichkeit geschnitten, nicht gegen einen Entwurf.**
> BC1 hat am 08.09.2026 drei Profile für NoroAI nach `bc1.prozessprofil` geschrieben
> (`KP-06.TP-2`, `KP-05.TP-1`, `KP-06.TP-1`, je `status='fertig'`). Der Vertrag
> beschreibt diese Zeilen, keine Wunschform. Wo er mehr fordert als heute geliefert
> wird, steht das unten ausdrücklich als offener Punkt.
>
> **Er beschreibt nicht die Tabelle.** Die gehört BC1, ihr Schema liegt in der
> Datenbank und wird hier nicht dupliziert (ADR-002). Beschrieben ist die
> **Leseprojektion**: das Objekt, das BC2 aus einer Zeile baut. Einig werden müssen
> sich beide Seiten über Feldnamen, Einheiten und Nullbarkeit — nicht über
> Postgres-Typen.

## Dateien

| Datei | Was drinsteht |
|---|---|
| `prozessprofil.schema.json` | Die Leseprojektion als JSON Schema (Draft 2020-12) |
| `lesen.sql` | Die Leseregel — **Vertragsbestandteil**, siehe Invariante I5 |
| `../examples/beispiel_bc1_prozessprofil.json` | `KP-06.TP-2`, nachgebaut aus der Zeile vom 08.09.2026 |

Geprüft wird das Paar von `bc2-strategic-advisor/tools/validate.py`.

## Feldnamen bleiben englisch

BC1s Spalten heißen `frequency_per_year`, nicht `haeufigkeit_pro_jahr`. Das ist Absicht:
es sind BC1s Daten, und jeder umbenannte Feldname erzeugt eine Übersetzungstabelle, die
zwei Teams im Kopf mitführen müssen — ein Befund wie „`executions_per_run` ist gleich
`frequency_per_year` gesetzt" wäre zwischen den Teams nicht mehr aussprechbar. Übersetzt
wird an BC2s **innerer** Grenze, wo aus einem Profil ein Potenzial wird, nicht hier.

## Was der Vertrag bindet

**Die neun typisierten Spalten** — `frequency_per_year`, `executions_per_run`,
`total_duration_minutes`, `focus_step_duration_minutes`, `focus_step_duration_source`,
`focus_step_duration_confidence_pct`, `upstream_process_id`, `downstream_process_id`,
`process_owner_rolle_id` — plus die Identität (`company_id`, `focus_step_id`,
`profil_version`, `process_id`, `status`, `erhebung_id`, `paket_version`).

**Dazu acht namentlich benannte Felder aus dem Profil-JSON:** `documentation_status`,
`standardization_level`, `data_availability_score`, `stability_score` (je Skala 1–5),
`focus_step_roles`, `focus_step_systems`, `focus_step_media_break`, `open_remarks`.

Warum diese acht: die vier Skalen tragen die **Umsetzungskomplexität** aus BC2s
Score-Formel, `focus_step_media_break` ist die einzige Medienbruch-Angabe, der BC2
trauen kann (`v_gate_prozessstand.tp_mit_medienbruch` zählt nur nicht-leeren Freitext,
[#163](https://github.com/pg-coe-kmu/coe-factory/issues/163)), und `open_remarks` trägt
heute die Testdaten-Kennzeichnung. Dass sie bisher nur zufällig da waren, wäre die
teuerste Lücke gewesen — die vier Prüfpunkte aus `ref_gate_pruefpunkte` allein tragen
die Priorisierung nicht.

**Dazu zwei Kopf-Angaben des Profil-JSON:** `ungeloeste_felder` und `vollstaendigkeit`.
Sie sagen, ob und welche Pflichtfelder das Interview aufgegeben hat — und damit, warum
eine Rechengröße `NULL` ist (siehe „Was BC1 zusagt").

**Alles Übrige aus dem Profil-JSON ist unverbindlicher Kontext** und darf sich ohne
Rücksprache ändern. BC1 stellt 43 Fragen; BC2 rechnet auf 17 Feldern plus zwei Kopf-Angaben.

## Invarianten

**I1 · Dauern gelten je Prozessdurchlauf.** `total_duration_minutes` und
`focus_step_duration_minutes` sind Minuten **je Prozessdurchlauf**, einschließlich der darin bearbeiteten `executions_per_run` Fälle. Frage E1 lautet „Wie
lange dauert ein kompletter Durchlauf im Schnitt?", Frage E2 „Wie lange dauert dieser
Schritt im Schnitt?".

    Jahresminuten = frequency_per_year × total_duration_minutes

**Die Bezugsgröße ist eine Annahme aus dem Fragetext, keine Prüfung.** BC1 speichert den
normalisierten Zahlenwert; ein Zusatz wie „pro Fall" oder „je Mitarbeiter" geht dabei
verloren („90 Minuten pro Fall" → `90`). E2 nennt im Fragetext gar keine Bezugsgröße.
BC1 schärft E2 mit der nächsten Paket-Revision; bis dahin gilt: je Durchlauf, ungeprüft.

**`frequency_per_year` und `total_duration_minutes` beschreiben den Prozess, wie ihn der
Befragte in `process_name` gerahmt hat** — D1 und E1 fragen nach „dem gesamten Prozess",
gespeichert wird die Antwort auf der Zeile des Fokus-Schritts. Zwei Profile desselben
Kernprozesses können sich darin widersprechen; die drei Zeilen vom 08.09.2026 tun es
(KP-06: 40 × 120 min in `KP-06.TP-1`, 180 × 180 min in `KP-06.TP-2`). BC2 rechnet
**je Profilzeile** und summiert nicht je Kernprozess.

**I2 · `executions_per_run` ist kein Multiplikator der Dauer.** Es ist die Fallschwere
je Prozessdurchlauf, Kontext für die Bewertung — nicht ein Faktor der Jahresminuten. Wer
`f × e × Dauer` rechnet, erhält für die Reisebuchung 48.600 Stunden im Jahr: das
Dreifache der Gesamtkapazität einer Firma mit zehn Mitarbeitenden, für **einen** Schritt.
Richtig sind 270 Stunden.

**I3 · Plausibilitätsschranke.** Übersteigen die Jahresminuten eines Prozesses die
Kapazität des Mandanten, rechnet BC2 nicht weiter, sondern meldet. Eine Zahl, die
niemand leisten kann, ist keine Wertaussage.

**I4 · `erhebung_id` ist Herkunftsanker, keine Stand-Garantie.** BC1 speichert die
Erhebung mit dem jüngsten Stand **zu dem Zeitpunkt, an dem die Profilzeile angelegt
wird** — nicht die, aus der alle aktuellen Bewertungen stammen;
`v_bewertung_aktuell` ist itemweise aktuell. **BC2 sagt zu, die Bitkom-Bewertungen über
`v_bewertung_aktuell` zu holen und nie über diese ID** (Klärpunkt **K-L**, von BC1 in
`bc0_lesepfade.py` an BC2 gestellt und hiermit beantwortet). BC2s Zeitanker ist
`uebergeben_am` gegen die Historisierung seit Schema v2.6, nicht dieses Feld.

**I5 · Die Leseregel gehört zum Vertrag.** Es liegen **mehrere Versionen je
Teilprozess** vor, weil `fertig` bei BC1 final ist und BC1 deshalb nachlegt statt zu
korrigieren. Es gilt die jüngste `profil_version` mit `status='fertig'` — siehe
`lesen.sql`. Das ist die einzige Stelle, an der BC2 stillschweigend die falsche Zeile
lesen könnte. Und: **Nachlegen gewinnt immer** — eine jüngere fertige Version verdrängt die
ältere auch dann, wenn ihr Rechengrößen fehlen. Es gilt die gelieferte Zeile, nicht die
beste.

**I6 · Im Profil-JSON ist jeder Wert eine Zeichenkette.** `felder.<name>.wert` ist
`string` oder `null` — auch bei Zahlen und 1-bis-5-Skalen. Nur die typisierten Spalten
tragen Zahlen. Nur Felder mit `status='gueltig'` sind überhaupt in eine Spalte geflossen;
jeder andere Status ergibt dort SQL `NULL`, während im JSON der **normalisierte** Wert
stehen bleibt, sofern je einer erfasst wurde (`wert` kann auch `null` sein). Den Rohtext
der Antwort speichert BC1 nirgends.

**I7 · Testdaten werden durchgereicht, nicht abgewiesen.** Beginnt `open_remarks` mit
dem Präfix `Testdaten ` (das Wort, dann ein Leerzeichen — so in BC1s
`use_case_testprofile.py` festgeschrieben), rechnet BC2 normal weiter und trägt
die Kennzeichnung als **Herkunft** an den mitgeführten Eingangswert
([#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)). In der erzeugten
Präsentation muss sichtbar sein, dass die Zahl gesetzt und nicht erhoben war.

## Normalisierung der Zahlen

Was BC1 aus einer Antwort macht, bevor sie in die Spalte kommt — gemessen am Bau
(`bc1_core/feldtypen.py`), nicht am Wunsch:

| Antwort auf D1 (`frequency_per_year`) | Spalte | Warum |
|---|---|---|
| `30 pro Monat` · `2 pro Woche` | `360` · `104` | Woche/Monat/Jahr werden auf das Jahr gerechnet |
| `30` | `30` | nackte Zahl gilt als **pro Jahr**, ohne Rückfrage |
| `30 monatlich` · `3 pro Tag` · `30 pro Quartal` | Nachfrage | unbekannte Periode wird nicht geraten; nach zwei Nachfragen `ungeloest` → `NULL` |

Dauern (E1, E2): `3 Stunden` → `180`, `90 min` → `90`; die Einheit wird auf Minuten
gerechnet, Zusätze zur Bezugsgröße verworfen (siehe I1). Die Konfidenz (E4) ist ganzzahlig.

**D4 (`executions_per_run`) nutzt heute denselben Normalisierer wie D1** — „5 pro Woche"
würde zu `260` „Fällen je Durchlauf". Für eine Fallzahl je Durchlauf ist das sinnlos; BC1
stellt D4 mit der nächsten Paket-Revision auf einen reinen Zähl-Typ um.

## Güte

BC1 liefert **zwei** Güteangaben, beide nur zur Fokus-Schritt-Dauer:
`focus_step_duration_source` (`gemessen` / `geschaetzt` / `aus_system`) und
`focus_step_duration_confidence_pct` (0–100).

**Die Herkunft ist die Achse, die Konfidenz verfeinert sie.** Simeons Belegpflicht vom
07.09.2026 („kein Prozess ohne Dokumentation") trifft die Herkunft, nicht eine
Konfidenzzahl. Wie breit die Bandbreite je Herkunft wird, setzt
[#166](https://github.com/pg-coe-kmu/coe-factory/issues/166); hier wird nur die Quelle
benannt.

**Die drei übrigen Rechengrößen tragen keine Güteangabe.** BC2 fordert das nicht nach:
eine vierfache Konfidenz wäre genauso geschätzt und würde BC1s Abschluss der Etappe 1
blockieren. BC2 führt die Unsicherheit für sie selbst — dieselbe Lage wie über den
Bitkom-Bestand ([#161](https://github.com/pg-coe-kmu/coe-factory/issues/161)).

## Was BC1 zusagt — und was BC2 aushält

**Zusage:** Alle vier Rechengrößen sind Pflichtfragen, und BC1 fragt jede höchstens
zweimal nach. **Bleibt eine danach ungeklärt, wird das Profil trotzdem `fertig`.** Das
Feld steht dann im Profil-JSON mit `status='ungeloest'` und einem `grund`
(`nachfrage_limit_erreicht` oder `runden_limit_erreicht`), sein Name steht in
`profil.ungeloeste_felder`, und die typisierte Spalte ist `NULL`. Nur die Identität
(`focus_step_id`) ist unaufgebbar. `profil.vollstaendigkeit` ist der Anteil erfasster
Pflichtfelder (0–1). Ein `fertig` mit `NULL`-Rechengrößen ist also kein Fehler, sondern
ein abgebrochenes Nachfragen — die Datenbank erzwingt keinen CHECK, und BC1 verspricht
keinen. In den drei Zeilen vom 08.09.2026 ist `vollstaendigkeit` 1.0 und
`ungeloeste_felder` leer.

**Verhalten:** BC2 verlässt sich nicht darauf. Ist ein Wert `NULL`, rechnet BC2
**qualitativ weiter** — Erkennen, Beschreiben, ordinale Priorisierung — und vermerkt die
Lücke am Potenzial. Verloren geht allein die monetäre Wertaussage, nicht der Lauf
([#163](https://github.com/pg-coe-kmu/coe-factory/issues/163)). Eine Zeile abzuweisen
würde BC1 blockieren, ohne dass BC2 etwas gewinnt.

## Was BC1 heute nicht liefert

**Rollen.** `bc1.profil_rollen` ist strukturell abgenommen (inklusive `zeitanteil_pct`)
und **leer**; `process_owner_rolle_id` ist immer `NULL`. Beteiligte stehen als Freitext
in `focus_step_roles` („Office Management, Consultants"). Daraus eine `rolle_id`
abzuleiten wäre geraten — BC2 tut es nicht. Befüllt wird die Tabelle mit BC1s
Rollen-Lesepfad (Abschlussplan BC1, Paket C1); die Rollen-Stammdaten liegen bei BC0.

**Zeitanteile.** `zeitanteil_pct` erhebt heute niemand — die Frage gehört zu BC1s
Etappe 2. Damit fehlt der Eingang für die Kapazitätsachse
([#172](https://github.com/pg-coe-kmu/coe-factory/issues/172), Option D). **BC2
verdrahtet diese Achse nicht, bis sie trägt.**

Beides steht als Struktur im Schema, damit die Form verbindlich ist, sobald sie befüllt
wird. Ein Termin ist nicht Teil dieses Vertrags.

## Offene Punkte

1. **`executions_per_run` gleich `frequency_per_year` — bestätigt als Eingabeartefakt**
   (BC1 in #195, 12.09.2026; alle drei Zeilen gemessen, Spalte wie JSON). BC1 legt
   korrigierte Testprofile als Version 3 nach; bis dahin trägt I2. Erledigt ist damit auch
   die Frage nach `focus_step_media_break`: in der Datenbank steht `ja`/`nein`,
   normalisiert — in allen sechs Zeilen gemessen.
2. **An BC2: `step_frequency_per_year` (Frage D3, optional).** „Wie oft läuft dieser
   einzelne Schritt, falls abweichend?" Ist das Feld `gueltig`, läuft der Fokus-Schritt
   nicht `frequency_per_year`-mal, sondern so oft — und `frequency_per_year ×
   focus_step_duration_minutes` wäre falsch. Heute ist D3 ungebunden, BC2 sieht es nicht.
   BC2 entscheidet: binden (dann ins Schema, mit Vorrang vor `frequency_per_year` für den
   Fokus-Schritt) oder ausdrücklich ignorieren (dann hier festhalten).

**K-K wird hingenommen.** Dass eine *offene* Erhebung als aktuell gilt und BC0 sie später
verwerfen kann, ohne dass der Fremdschlüssel es merkt, ist für BC2 folgenlos: der Anstoß
kommt seit [#165](https://github.com/pg-coe-kmu/coe-factory/issues/165) erst nach der
Gate-0-Freigabe. BC1 muss dafür nichts ändern.

## Stand

**Fassung 1.1 — Vorschlag von BC1, 12.09.2026.** Nach Prüfung gegen den Bau (Branch
`bc1-db-profil-fundament`) und die echte Zeile `KP-06.TP-2` Version 2 (gegen das Schema
validiert, 0 Fehler): die Zusage „nie `NULL` bei `fertig`" durch die `ungeloest`-Regel
ersetzt und `ungeloeste_felder`/`vollstaendigkeit` gebunden · Bezugsgröße als ungeprüfte
Annahme benannt · Prozess-Größen auf Teilprozess-Zeilen erklärt · Normalisierung
festgehalten · `focus_step_systems` als Freitext-Liste · Kennzeichnungs-Präfix exakt ·
Beispiel durch den echten Export ersetzt · offene Punkte 1–2 geschlossen, D3 an BC2.
Typen, Enums, JSON-Form und `lesen.sql` haben der Prüfung standgehalten.

**Fassung 1.0, 10.09.2026.** Von BC2 geschnitten und auf `main` gelegt; BC1 hat den
Vertrag im eigenen Abschlussplan (Stufe A, Paket A1) bestellt und die Eingänge geliefert
(Spalte-zu-Feld-Tabelle vom 08.09.2026). Änderungswünsche von BC1 oder Platform gehen als
Issue oder PR gegen diese Dateien — der Vertrag ist ein Vorschlag von BC2, kein Diktat,
und ist im Zweifel BC1s Bau nachzuziehen, nicht umgekehrt.
