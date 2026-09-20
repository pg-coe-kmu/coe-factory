# Nachricht an BC3 — zum Versenden

> Entwurf zu [#168](https://github.com/pg-coe-kmu/coe-factory/issues/168). **Noch nicht
> versendet.** Sie gehört zusammen mit der Rückfrage aus
> [#242](https://github.com/pg-coe-kmu/coe-factory/issues/242) verschickt — eine Nachricht, nicht
> zwei.

---

Hallo Svetlana,

hier sind die simulierten Daten für den dritten Use Case, um die du am 07.09. gebeten hattest —
plus zwei Dinge, die sich seither geändert haben und die ihr wissen solltet, bevor ihr damit
schneidet.

## 1 · Die Lieferung

```
contracts/bc2-to-bc3/lieferungen/noroai-SIM-UC3-2026-09-21-f1/
├── konzept_KP-06.json          Consultant Placement, KP-06.TP-1, zwei Potenziale
├── prozesspriorisierung.json   Rangfolge + gate1
└── README.md                   ← bitte zuerst lesen
```

Schema-konform gegen **v3.0**, `validate.py` läuft grün. Ihr könnt direkt dagegen entwickeln.

Der Inhalt ist eurer: Beschreibungen, `to_be_vision`, fachliche Anforderungen,
Akzeptanzkriterien und Risiken stammen aus eurer Formatvorlage vom 31.08. Neu von uns sind die
**Zahlen**, die **User Story** in SOPHIST-Form und das **`messverfahren`** je Kriterium — die drei
Dinge, die laut Absprache vom 09.09. BC2 verantwortet.

## 2 · Warum simuliert, und was das für euch heißt

Der Durchstich über die ganze Strecke ist für **KW 40** angesetzt. Er steht unter Vorbehalt:
Simeon meldet einen Fehler in Gate 0s manueller Freigabe und einen Datenbank-Umbau mit offener
Dauer. Diese Lieferung ist die **Rückfallebene**, damit ihr nicht wieder wartet, wenn es rutscht.

Häufigkeit und Dauer sind Annahmen — eure eigenen, aus der Vorlage übernommen (600 Lebensläufe
im Jahr, 20 Min je Lebenslauf; 120 Ausschreibungen, 180 Min je Ausschreibung). Gate 0 ist für
KP-06.TP-1 nicht durchlaufen.

**Was trägt:** der Potenzialschnitt, die Beschreibungen, die Akzeptanzkriterien, die Form.
**Was sich noch dreht:** die Euro-Beträge und möglicherweise die Rangfolge.

Woran ihr es im Artefakt erkennt — bitte beim Übernehmen stehen lassen:

- `[SIMULIERT]` als Präfix in **jedem Titel**
- Warnblock am Anfang **jeder `beschreibung`**
- `value_quelle = "annahme"`, `gate1.status = pending` mit Freigabesperre

## 3 · Zwei Änderungen seit eurer Vorlage

**a) Der Vertrag ist auf v3.0 — und der Schnitt bricht.** Zehn angesammelte Änderungen in einem
Zug ([#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)). Die wichtigsten für euch:

- **`gate1` ist aus dem Konzept in die Priorisierung gewandert.** Entschieden wird über den
  *Lauf*, nicht je Kernprozess.
- **Impact und Komplexität sind Zahlen 1–10**, nicht mehr die vier Stufen — wie ihr am 06.09.
  bestätigt hattet.
- **Value sind Spannen**, keine Punktwerte, plus `value_quelle`.
- `betroffene_teilprozess_ids` ist Pflicht.

Eure drei Beispieldateien vom 31.08. sind übrigens **zwei** Konzepte, nicht drei: uc1 und uc3
tragen beide KP-06, und ein Konzept deckt genau einen Kernprozess ab.

**b) Wir rechnen mit 43 €/h, ihr mit 60 €/h.** Der Mischsatz kommt aus NoroAIs
Unternehmensprofil. Die absoluten Beträge liegen dadurch niedriger als in eurer Vorlage; an der
Rangfolge ändert ein konstanter Faktor nichts.

## 4 · Was ich von euch bräuchte

Steht ausführlich in [#242](https://github.com/pg-coe-kmu/coe-factory/issues/242), kurz:

1. **Zieht ihr** aus dem Repo — und merkt ihr, wenn etwas Neues da ist, oder braucht es einen
   Anstoß von einem Menschen?
2. **Ist der Ordnername in Ordnung?** `<company>-<paket_id>-f<n>`. Er ist nirgends verdrahtet,
   jetzt ist der günstige Moment.
3. **Trägt eine neue `konzept_id` je Fassung bei euch?** Oder hängen eure Epics so an der ID,
   dass ein Fassungswechsel etwas zerreißt? Das ist der Punkt, an dem ich am ehesten falsch
   geraten habe.

Vor KW 40 wäre gut — sonst läuft der erste echte Lauf in eine Konvention, die wir hinterher
wieder umbauen.

Viele Grüße
Sergio
