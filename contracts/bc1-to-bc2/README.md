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

**Alles Übrige aus dem Profil-JSON ist unverbindlicher Kontext** und darf sich ohne
Rücksprache ändern. BC1 stellt 43 Fragen; BC2 rechnet auf 17 Feldern.

## Invarianten

**I1 · Dauern gelten je Prozessdurchlauf.** `total_duration_minutes` und
`focus_step_duration_minutes` sind Minuten **je Prozessdurchlauf**, einschließlich der darin bearbeiteten `executions_per_run` Fälle. Frage E1 lautet
wörtlich „ein kompletter Prozessdurchlauf".

    Jahresminuten = frequency_per_year × total_duration_minutes

**I2 · `executions_per_run` ist kein Multiplikator der Dauer.** Es ist die Fallschwere
je Prozessdurchlauf, Kontext für die Bewertung — nicht ein Faktor der Jahresminuten. Wer
`f × e × Dauer` rechnet, erhält für die Reisebuchung 48.600 Stunden im Jahr: das
Dreifache der Gesamtkapazität einer Firma mit zehn Mitarbeitenden, für **einen** Schritt.
Richtig sind 270 Stunden.

**I3 · Plausibilitätsschranke.** Übersteigen die Jahresminuten eines Prozesses die
Kapazität des Mandanten, rechnet BC2 nicht weiter, sondern meldet. Eine Zahl, die
niemand leisten kann, ist keine Wertaussage.

**I4 · `erhebung_id` ist Herkunftsanker, keine Stand-Garantie.** BC1 speichert die
Erhebung mit dem jüngsten Stand — nicht die, aus der alle aktuellen Bewertungen stammen;
`v_bewertung_aktuell` ist itemweise aktuell. **BC2 sagt zu, die Bitkom-Bewertungen über
`v_bewertung_aktuell` zu holen und nie über diese ID** (Klärpunkt **K-L**, von BC1 in
`bc0_lesepfade.py` an BC2 gestellt und hiermit beantwortet). BC2s Zeitanker ist
`uebergeben_am` gegen die Historisierung seit Schema v2.6, nicht dieses Feld.

**I5 · Die Leseregel gehört zum Vertrag.** Es liegen **mehrere Versionen je
Teilprozess** vor, weil `fertig` bei BC1 final ist und BC1 deshalb nachlegt statt zu
korrigieren. Es gilt die jüngste `profil_version` mit `status='fertig'` — siehe
`lesen.sql`. Das ist die einzige Stelle, an der BC2 stillschweigend die falsche Zeile
lesen könnte.

**I6 · Im Profil-JSON ist jeder Wert eine Zeichenkette.** `felder.<name>.wert` ist
`string` oder `null` — auch bei Zahlen und 1-bis-5-Skalen. Nur die typisierten Spalten
tragen Zahlen. Nur Felder mit `status='gueltig'` sind überhaupt in eine Spalte geflossen;
jeder andere Status ergibt dort SQL `NULL`, während der Rohwert im JSON stehen bleibt.

**I7 · Testdaten werden durchgereicht, nicht abgewiesen.** Beginnt `open_remarks` mit
einer Kennzeichnung wie „Testdaten … nicht erhoben", rechnet BC2 normal weiter und trägt
die Kennzeichnung als **Herkunft** an den mitgeführten Eingangswert
([#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)). In der erzeugten
Präsentation muss sichtbar sein, dass die Zahl gesetzt und nicht erhoben war.

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

## Was BC1 zusagt — und was BC2 trotzdem aushält

**Zusage:** bei `status='fertig'` sind die vier Rechengrößen nicht `NULL`. Alle vier sind
Pflichtfragen; ohne sie wird ein Profil nicht `fertig`. Die Datenbank erzwingt das heute
**nicht** — es gibt keinen CHECK, der sie an den Status bindet.

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

## Offene Punkte an BC1

1. **`executions_per_run` gleich `frequency_per_year`.** In allen drei Zeilen vom
   08.09.2026 stehen dieselben Zahlen (180/180, 260/260, 40/40), obwohl D1 und D4
   verschiedene Größen erfragen. Vermutlich ein Eingabeartefakt der Testdaten — es steht
   aber so in der Datenbank, und I2 hält deshalb ausdrücklich fest, dass BC2 die beiden
   nicht multipliziert.
2. **`focus_step_media_break`** wurde im Interview als „Ja." erfasst. BC2 erwartet den
   normalisierten Wert (`ja` / `nein`); wenn der Rohtext durchschlägt, bitte melden.

**K-K wird hingenommen.** Dass eine *offene* Erhebung als aktuell gilt und BC0 sie später
verwerfen kann, ohne dass der Fremdschlüssel es merkt, ist für BC2 folgenlos: der Anstoß
kommt seit [#165](https://github.com/pg-coe-kmu/coe-factory/issues/165) erst nach der
Gate-0-Freigabe. BC1 muss dafür nichts ändern.

## Stand

**Fassung 1.0, 10.09.2026.** Von BC2 geschnitten und auf `main` gelegt; BC1 hat den
Vertrag im eigenen Abschlussplan (Stufe A, Paket A1) bestellt und die Eingänge geliefert
(Spalte-zu-Feld-Tabelle vom 08.09.2026). Änderungswünsche von BC1 oder Platform gehen als
Issue oder PR gegen diese Dateien — der Vertrag ist ein Vorschlag von BC2, kein Diktat,
und ist im Zweifel BC1s Bau nachzuziehen, nicht umgekehrt.
