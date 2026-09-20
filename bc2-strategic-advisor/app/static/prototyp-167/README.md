# PROTOTYP zu [#167](https://github.com/pg-coe-kmu/coe-factory/issues/167) — Frontend-Schnitt BC2

**Wegwerfcode.** Er beantwortet eine Frage und wird danach weggeworfen; was gewinnt, wird neu
geschrieben. Dieser Zweig (`prototyp/167-frontend-schnitt`) geht **nicht** nach `main`.

## Ansehen

`index.html` im Browser öffnen — Doppelklick genügt, kein Server, kein Bauschritt.

    open index.html

Zwischen den Fassungen schalten: die Pille unten, die Pfeiltasten **←/→**, oder
`?variant=A|B|C|D` in der Adresse. **D ist die Voreinstellung.**

| | Fassung | Die Seite ist … | Kann umsortieren |
|---|---|---|---|
| **D** | **Mischung** *(aus der Rückmeldung vom 20.09.2026)* | die Liste, nach Kernprozess geklappt | **ja, per Ziehen**, zwei Ebenen |
| **A** | Rangliste | die Reihenfolge | nein |
| **B** | Portfolio | die Matrix | nein |
| **C** | Freigabe-Assistent | der Entscheidungsweg | **ja**, mit Pflichtbegründung |

### Fassung D im Einzelnen

Sie nimmt aus jeder der drei etwas: die **Gliederung nach Kernprozess** aus C, aber als Akkordeon
über einer Liste in der **Dichte von A**; Bs **Matrix** sitzt hinter einem Knopf statt auf einer
eigenen Seite.

- **Ziehen auf zwei Ebenen** — eine Zeile innerhalb ihres Kernprozesses (am Griff `⠿`), oder der
  ganze Kernprozess über seinen Kopf. Die geltende Reihenfolge ist die Verkettung. Ein Potenzial
  in einen fremden Prozess zu ziehen ist gesperrt: das wäre Umhängen, keine Reihenfolgefrage.
- **Der Vorschlag ist vorbelegt** — alles freigegeben. Begründet wird die *Abweichung*, nicht die
  Zustimmung.
- **Jede Nicht-Freigabe braucht eine Begründung.** Fehlt eine, bleibt Gate 1 gesperrt.
- **Gespeichert** wird im Browser (`localStorage`, Schlüssel `PROTOTYP-167-wegwerfen`, an die
  `paket_id` gebunden) — Freigaben, Begründungen und Reihenfolge überleben das Neuladen.
  „Entscheidung verwerfen" setzt zurück. *Im Betrieb gehört das an den Lauf (Schema `bc2`) und in
  die Lieferung;* **im Vertrag gibt es für die Ablehnungsbegründung heute kein Feld** — offene
  Auflage an [#187](https://github.com/pg-coe-kmu/coe-factory/issues/187).
- **Grenze:** Ziehen ist Maus-Bedienung. Auf einem Tablet bräuchte es zusätzlich ↑/↓ wie in C.

Jede Fassung trägt oben den Kasten **„Was diese Fassung behauptet"** — dort steht, wie sie die
acht Fragen des Tickets beantwortet. Die Unterschiede sind strukturell, nicht farblich.

## Daten

Die Daten stehen **in `index.html` eingebettet**, zwischen den Marken `DATEN-ANFANG` und
`DATEN-ENDE`. Nicht von Hand ändern, sondern neu erzeugen:

    python3 daten_bauen.py

*(Eingebettet und nicht als eigene `daten.js` daneben: Safari behandelt jede `file://`-Datei als
eigene Herkunft und lädt eine benachbarte `.js` nicht — die Seite blieb weiß.)*

Die Werte sind **erfunden, aber nach [ADR-006](../../../docs/adr/ADR-006_Value_und_Priorisierungsmodell.md)
gerechnet** — Bandbreiten je Herkunft der Dauer, Eckenrechnung, Impact aus monetärem Teil-Score und
Nutzwert, `score = impact × (11 − komplexitaet)`, Kategorien und Prioritätsgruppen. Ein Prototyp,
der über seine eigene Arithmetik lügt, taugt nicht als Entscheidungsgrundlage.

Der Satz ist so geschnitten, dass die Ausnahmefälle vorkommen, an denen sich die Oberfläche
beweisen muss:

- **P-04** hat keine erhobene Dauer → **keine Value-Zahl** (nicht eine sehr breite).
- **P-08** hat keine Reifeskalen → Umsetzungskomplexität **geurteilt** statt gemessen.
- **P-07** weicht von BC1s `automation_potential_estimate_pct` ab → Plausibilitätsprobe schlägt an.
- **P-09** reißt zusammen mit den übrigen die **Plausibilitätsschranke** des Laufs (7.992 h > 7.040 h).
- Drei Läufe im Kopf: einer offen, einer freigegeben, einer vom **Übungsmandanten** — letzterer
  zeigt, warum jede Abfrage nach `company_id` filtert.

Keine Datenbank. In A/B/C lebt jede Freigabe nur im Arbeitsspeicher; **D speichert** — siehe oben,
weil die Begründung einer Nicht-Freigabe die eine Angabe ist, die nirgends sonst herkommt.

## Technik — Punkt 8 des Tickets

Eine HTML-Datei, kein Rahmenwerk, kein Bauschritt. Genau so liegt **BC0s PWA** im Repo
(`bc0-baseline-onboarding/app/static/index.html`, 2.903 Zeilen, von FastAPI über `StaticFiles`
ausgeliefert). Der Prototyp ist damit selbst das Argument: für diesen Umfang braucht BC2 kein
eigenes Frontend-Projekt. Wenn die Fassung steht, wird sie unter `bc2-strategic-advisor/app/static/`
montiert wie bei BC0.
