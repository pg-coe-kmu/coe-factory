# Simulierte Lieferung UC3 — Rückfallebene zum Durchstich

> **Diese Lieferung ist simuliert.** Häufigkeit und Dauer sind Annahmen aus BC3s Formatvorlage
> vom 31.08.2026, nicht erhobene Größen. Gate 0 ist für `KP-06.TP-1` nicht durchlaufen.
> **Nicht für Entscheidungen, Angebote oder eine Gate-1-Freigabe verwenden.**

| | |
|---|---|
| Lauf | `company_id` NoroAI · `paket_id` **`SIM-UC3-2026-09-21`** · Fassung 1 |
| Vertrag | `konzept.schema.json` / `priorisierung.schema.json` **v3.0** |
| Kernprozess | KP-06, Teilprozess TP-1 (Use Case 3, Consultant Placement) |
| Erzeugt von | [`bc2-strategic-advisor/tools/gen_lieferung_sim_uc3.py`](../../../../bc2-strategic-advisor/tools/gen_lieferung_sim_uc3.py) — deterministisch, kein LLM |
| Ticket | [#168](https://github.com/pg-coe-kmu/coe-factory/issues/168) |

## Wozu sie da ist

Der erste echte Lauf über die ganze Strecke ist für **KW 40** angesetzt
([#206](https://github.com/pg-coe-kmu/coe-factory/issues/206)). Er steht unter Vorbehalt: BC0
meldet am 20.09.2026 einen Fehler in Gate 0s manueller Freigabe und einen Datenbank-Umbau mit
offener Dauer. Rutscht der Durchstich, hätte BC3 wieder nichts, wogegen es schneidet — genau der
Zustand, aus dem #168 entstanden ist.

Diese Lieferung ist die Rückfallebene: **dieselbe Form wie eine echte, mit erkennbar gesetzten
Zahlen.** Der Zuschnitt UC3 ist der, um den Svetlana am 07.09.2026 gebeten hat — um zu prüfen, ob
erzeugte Daten den Workflow sauber durchlaufen.

Sie ist zugleich eine **Probe des Weges**: gerechnet wurde mit demselben Kern
(`bc2-strategic-advisor/app/modell/`), der auch im Ernstfall rechnet, und abgelegt im
Ordnerschnitt nach [ADR-007 · BC2](../../../../bc2-strategic-advisor/docs/adr/ADR-007_Rueckrichtung_BC2_zu_BC3.md).

## Was echt ist und was gesetzt

| Echt (aus BC3s Vorlage übernommen) | Gesetzt (angenommen, nicht erhoben) |
|---|---|
| Prozessbeschreibung, Schmerzpunkte, Systeme | Fallzahl pro Jahr (600 Lebensläufe, 120 Ausschreibungen) |
| Potenzialschnitt, `to_be_vision`, fachliche Anforderungen | Bearbeitungszeit je Fall (20 min, 180 min) |
| Akzeptanzkriterien, Voraussetzungen, Risiken | Automatisierungsgrad (Korridor der Klasse, ohne LLM-Verortung) |
| Aufwandsschätzung in Personentagen | Umsetzungskomplexität — **geurteilt**, nicht gemessen |

Die beiden gesetzten Mengengrößen stammen wörtlich aus BC3s eigenen Annahmen; der Generator
rechnet sie gegen BC3s `ist_kosten_eur_jahr` zurück und bricht ab, wenn es nicht aufgeht.

**Zwei Unterschiede zu BC3s Zahlen**, beide gewollt:

1. **Stundensatz.** BC3 rechnet mit 60 €/h, BC2 mit dem Mischsatz **43 €/h** aus dem
   NoroAI-Unternehmensprofil ([#172](https://github.com/pg-coe-kmu/coe-factory/issues/172)). Die
   absoluten Beträge liegen damit niedriger; für die Rangfolge ist ein konstanter Faktor
   gleichwertig, er kürzt sich heraus.
2. **Spannen statt Punktwerten.** v3.0 führt Bandbreiten je Herkunft der Dauer (hier ±40 %, weil
   `geschaetzt`), zusammengesetzt als Eckenrechnung (ADR-006 · BC2, 2.3).

## Das Ergebnis

| Rang | Potenzial | Gruppe | Score | Einsparung €/Jahr | Investition | Amortisation |
|---|---|---|---|---|---|---|
| 1 | Lebensläufe strukturiert erfassen und Kompetenzprofil aufbauen | PRIO 2 | 48 | 2.580 – 9.030 | 6.400 € | 8,5 – 29,8 Mon. |
| 2 | Projektanforderung mit Profilen abgleichen und Vorschlagsliste erzeugen | PRIO 2 | 32 | 5.573 – 18.421 | 14.400 € | 9,4 – 31,0 Mon. |

**Rang 2 spart mehr und liegt trotzdem hinten.** Das ist kein Fehler, sondern die Formel:
`score = impact × (11 − umsetzungskomplexitaet)`. Der Abgleich hat den höheren Impact (8 gegen 6),
aber auch die höhere Komplexität (7 gegen 3). Wer zuerst Wirkung je Aufwand will, fängt mit den
Profilen an — und der Abgleich setzt sie ohnehin voraus.

**Beide in PRIO 2.** Der Kalibrierungsvorbehalt aus ADR-006 reproduziert sich auch hier: PRIO 1
verlangt eine Prozessreife, die es bei NoroAI nicht gibt. Festgezurrt wird am ersten echten Lauf
([#238](https://github.com/pg-coe-kmu/coe-factory/issues/238) → #206), nicht an diesen Zahlen.

## Woran ihr die Simulation im Artefakt erkennt

Gestaffelt danach, was das Kopieren in eure Tickets und von dort in BC4s Code überlebt:

| Träger | Überlebt Kopieren? |
|---|---|
| `[SIMULIERT]` als Präfix in **jedem Titel** | **ja** — bitte beim Übernehmen stehen lassen |
| Warnblock am Anfang **jeder `beschreibung`** | **ja** |
| `value.value_quelle = "annahme"` | nein, nur maschinenlesbar |
| `value.annahmen[0]` = „GESETZT, NICHT ERHOBEN …" | nein |
| `gate1.kommentar` = Freigabesperre | nein |
| `paket_id` und Ordnername tragen `SIM-` | nein |

`validate.py` prüft diese Kennzeichnung mit — sie kann nicht unbemerkt herausfallen.

## Was danach passiert

Der echte Lauf entsteht im Durchstich (#206) und **ersetzt diese Lieferung als neue Fassung**,
mit eigener `paket_id` aus Gate 0. Diese hier bleibt liegen: ein übergebenes Konzept wird nie
ungültig, es veraltet (ADR-007 · BC2, 2.4).

Der Ordnername folgt `<company>-<paket_id>-f<n>`. Ob der Schnitt so passt, ist BC3 in
[#242](https://github.com/pg-coe-kmu/coe-factory/issues/242) vorgelegt und **noch nicht
bestätigt** — er ist nirgends verdrahtet und kann sich ändern.
