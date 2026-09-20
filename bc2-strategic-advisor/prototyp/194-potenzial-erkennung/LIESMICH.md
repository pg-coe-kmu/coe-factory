# Prototyp zu #194 — wie aus einem Paket Potenziale werden

> **Wegwerfcode.** Keine Tests, keine Fehlerbehandlung, keine Abstraktionen. Er wird nicht
> befördert. Er liegt auf diesem Zweig als **Primärquelle** der Entscheidung, nicht als Vorlage
> für den Bau. Was aus ihm in den echten Code wandert, steht unten unter „Was liftbar ist".

## Die Frage

Seit [#164](https://github.com/pg-coe-kmu/coe-factory/issues/164) steht, **was** ein Potenzial ist.
Offen war, **wie BC2 sie findet** — vor allem, in welchem Schnitt das Modell gerufen wird: je
Teilprozess, je Kernprozess oder je Paket.

## Ansehen

`prototyp-194.html` doppelklicken. Eine Datei, alles inline, kein Server, kein Schlüssel.

## Nachbauen

```bash
python3 bauen.py       # Nutzlasten je Schnitt aus BC0s Snapshot v3
python3 schneiden.py   # 21 Modellaufrufe (A: 16, B: 4, C: 1), ~45 min
python3 packen.py      # alles in prototyp-194.html
```

Die Läufe sind abgelegt (`schnitt-A/B/C.json`) und werden nicht wiederholt; wer neu schneiden
will, löscht die Dateien. Jeder Aufruf ist eine eigene Sitzung ohne Gedächtnis an die anderen —
sonst wäre der Vergleich zwischen den Schnitten wertlos.

## Das Paket

Frei gewählt, weil der Snapshot keine Pakete kennt (er ist vom 27.08.2026, Gate 0 wird erst seit
dem 18.09. benutzt). 16 Teilprozesse, geschnitten auf die unangenehmen Fälle:

| | warum drin |
|---|---|
| KP-02, 5 TP | fünf verschiedene Stufenmuster — der dichteste Fall |
| KP-03, 5 TP | dito, dazu ein echter Medienbruch im Text |
| KP-05, 5 TP | nur TP-1 ist bewertet, TP-2…5 sind Platzhalter — der entartete Fall |
| KP-06.TP-2, 1 TP | der einzige mit einem BC1-Profil |

## Grenzen dieses Prototyps

- **Datenstand 27.08.2026.** Der Snapshot ist älter als BC1s erste Lieferung (08.09.) und älter
  als die erste Gate-0-Freigabe (18.09.). Die Messungen zur Auflösung der Teilprozess-Felder
  sind **an der laufenden Datenbank gegenzuprüfen**, bevor sie als Dauerbefund gelten — die Karte
  verzeichnet drei Fälle, in denen aus einem Artefakt auf die Absicht geschlossen wurde und es
  falsch war.
- **Ein BC1-Wert ist nicht aus dem Snapshot**, sondern aus der Messung in
  [#166](https://github.com/pg-coe-kmu/coe-factory/issues/166) (540 Jahresstunden für KP-06.TP-2).
  Im Code als solcher gekennzeichnet.
- **Ein Lauf je Schnitt.** Streuung zwischen Wiederholungen ist nicht gemessen. Die Befunde sind
  deshalb qualitativ — „fünfmal derselbe Sachverhalt" ist robust, „18 gegen 12 gegen 10
  Potenziale" ist es nur der Größenordnung nach.
- **Modell:** Claude Sonnet. Ob Opus anders schneidet, ist nicht geprüft.

## Was liftbar ist

Alles in `vorlage.html` unterhalb von `// Der liftbare Teil` — rein, ohne DOM:

- `pruefeSchnitt(potenziale, teilprozesseImPaket)` — die deterministische Nachkontrolle über der
  Modellantwort: unbedeckte Teilprozesse, Mehrfachbelegung, Paare unter Doppelzählungsverdacht,
  Potenziale über zwei Kernprozesse (Vertragsbruch), **Zahlen im Text trotz Verbots**.
- `paareImKernprozess(potenziale)` — die Vorlage für das Menschenurteil am Gate 1.

Die Seite ruft nur hinein, nie umgekehrt.
