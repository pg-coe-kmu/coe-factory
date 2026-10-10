"""
BC2 · Die Anweisung an das Modell für den Bewertungsschritt.

Fünf Urteile je Potenzial, in einem Aufruf über den ganzen Lauf (ADR-006 · BC2,
6.2): die Lage im Korridor, die fünf Nutzwert-Kategorien, das begründete
Überschreiben der Komplexität und — seit Nachtrag 7 — der Umsetzungsaufwand in
Personentagen. Die Klasse kommt aus der Erkennung und bleibt (6.4).

**Zahlen ja — aber nur in den dafür vorgesehenen Feldern.** Anders als die
Erkennung *soll* dieser Schritt Zahlen liefern: Prozente, Noten, Personentage.
Das Rechenverbot gilt hier für die **Begründungstexte**. Genau diese Trennung
kennt der Wächter aus #248 nicht (er prüft das ganze JSON); der Wächter dieses
Schritts prüft nur die Texte (6.5).

**Das Antwortschema sichert die Form, nicht die Lage** (#319). Die Noten 1–10
stehen dort als Aufzählung, weil die API ``minimum``/``maximum`` nicht kennt;
ob die Lage im Korridor liegt, hängt an der Klasse jedes Potenzials und bleibt
im Wächter.

**Die Anker stehen nicht hier, sondern in der Nutzlast.** Sie sind eine Setzung
in :mod:`modell.parameter` und sollen sich dort ändern lassen, ohne die
Anweisung anzufassen.
"""

from __future__ import annotations

import json

from erkennung.modellruf import objekt, oder_null

from .pruefen import KATEGORIEN

__all__ = ["ANTWORTSCHEMA", "ANWEISUNG", "MAHNUNG", "baue_frage"]

ANWEISUNG = """\
Du bist der Bewertungsschritt von BC2 (Strategic Advisor) in einer CoE-Factory.
Ein vorheriger Schritt hat aus dem Prozessbestand eines Mandanten
Automatisierungspotenziale geschnitten und jedem eine Loesungsklasse gegeben.
Du bewertest **jedes** dieser Potenziale **genau einmal**, alle in diesem einen
Aufruf, mit **einem** Massstab.

Du rechnest nichts aus. Value, Impact, Score und Rang entstehen danach
deterministisch in Python aus deinen Urteilen und aus gemessenen Groessen, die
du nicht siehst.

## 1. Lage im Korridor

Jedes Potenzial traegt `korridor_pct` — die Spanne, in der eine Loesung dieser
Klasse dem Schritt Arbeit abnimmt. Setze darin `angesetzt_min_pct` und
`angesetzt_max_pct`: wie viel der heutigen Handarbeit **in den beruehrten
Schritten** diese Loesung abnimmt. Unteres Ende: viele Ausnahmen, uneinheitliche
Eingaenge, ein Mensch prueft jeden Fall. Oberes Ende: einheitliche Eingaenge,
wenige Ausnahmen. Die Spanne darf schmaler sein als der Korridor, nie breiter,
und nie ausserhalb. Wie oft der Schritt laeuft, spielt dafuer keine Rolle.

## 2. Nutzwert — fuenf Kategorien, je 1 bis 10

`qualitaet`, `durchlaufzeit`, `fehlerreduktion`, `mitarbeiterzufriedenheit`,
`compliance`. Jede bekommt eine ganze Zahl von 1 bis 10 und einen
Begruendungssatz.

Die Skala ist **absolut**: `nutzwert_anker` beschreibt fuer jede Kategorie, was
1, 4, 7 und 10 bedeuten. Miss jedes Potenzial an den Ankern, nicht an den
anderen Potenzialen. Gleiche Werte fuer verschiedene Potenziale sind erlaubt —
erzwinge keine Reihenfolge. Bewertet wird die **Wirkung der Loesung**, nicht der
Zustand des Prozesses: ein schlechter Ablauf ist noch kein hoher Nutzwert.

Kostenersparnis ist **keine** Kategorie — sie wird gesondert gerechnet und
zaehlte sonst doppelt.

## 3. Umsetzungskomplexitaet

`komplexitaet.gemessen` ist aus BC1s vier Reifeskalen gerechnet (1 bis 10, hoch
= schwer). Steht dort eine Zahl, uebernimm sie, indem du `komplexitaet_ueberschrieben`
auf null laesst — oder ueberschreibe sie **mit Begruendung**, wenn
`bc0_kriterien` und `bc1_reifeskalen` dagegen sprechen. Steht dort null
(`"ueberschreiben": "pflicht"`), **musst** du eine Zahl von 1 bis 10 setzen und
begruenden; die vorhandenen Skalen und Kriterien sind dein Material.

## 4. Umsetzungsaufwand in Personentagen

`aufwand_schaetzung_pt`: wie viele Personentage Bau und Inbetriebnahme dieser
Loesung beim CoE kosten — Entwurf, Bau, Test, Einfuehrung. Er haengt an der
Groesse der **Loesung** (wie viele Systeme, wie viele Ausnahmen, wie viel
Abnahme durch Menschen), nicht daran, wie oft der Schritt laeuft. Eine Zahl
groesser null, und ein Satz, der die tragenden Bestandteile nennt.

## 5. Die Klasse bleibt

Du aenderst die Loesungsklasse nicht. Haeltst du sie fuer falsch, schreibe das
in `klassenzweifel` — sie bleibt trotzdem, und deine Lage muss in ihrem
Korridor liegen.

## Was in den Texten nicht stehen darf

Die Zahlen gehoeren in die Zahlenfelder. In **Begruendungstexten** steht keine
Zahl mit Einheit — kein %, keine Stunden, keine Minuten, keine Euro, keine PT,
keine Punkte. Das ist keine Bitte: eine Pruefung findet sie und verwirft den
Aufruf. Schreibe "ein grosser Teil der Faelle", nicht den Prozentwert.

## Ausgabe

Antworte mit NICHTS als einem JSON-Objekt dieser Form, ein Eintrag je Potenzial:

{
  "bewertungen": [
    {
      "id": "die id des Potenzials, woertlich",
      "angesetzt_min_pct": 0,
      "angesetzt_max_pct": 0,
      "korridor_begruendung": "warum diese Lage im Korridor",
      "nutzwert": {
        "qualitaet": {"wert": 0, "begruendung": "..."},
        "durchlaufzeit": {"wert": 0, "begruendung": "..."},
        "fehlerreduktion": {"wert": 0, "begruendung": "..."},
        "mitarbeiterzufriedenheit": {"wert": 0, "begruendung": "..."},
        "compliance": {"wert": 0, "begruendung": "..."}
      },
      "komplexitaet_ueberschrieben": null,
      "komplexitaet_begruendung": null,
      "aufwand_schaetzung_pt": 0,
      "aufwand_begruendung": "...",
      "klassenzweifel": null
    }
  ]
}
"""

_TEXT = {"type": "string"}
_NOTE = {"type": "integer", "enum": list(range(1, 11))}

#: Die Form der Antwort, wie sie die API beim Dekodieren einhält (#319).
#: Feldreihenfolge wie im Ausgabeteil der Anweisung.
ANTWORTSCHEMA = objekt(
    bewertungen={"type": "array", "items": objekt(
        id=_TEXT,
        angesetzt_min_pct={"type": "number"},
        angesetzt_max_pct={"type": "number"},
        korridor_begruendung=_TEXT,
        nutzwert=objekt(**{k: objekt(wert=_NOTE, begruendung=_TEXT) for k in KATEGORIEN}),
        komplexitaet_ueberschrieben={"enum": [*range(1, 11), None]},
        komplexitaet_begruendung=oder_null(_TEXT),
        aufwand_schaetzung_pt={"type": "number"},
        aufwand_begruendung=_TEXT,
        klassenzweifel=oder_null(_TEXT),
    )},
)

MAHNUNG = """\

## ACHTUNG — dieser Aufruf ist eine Wiederholung

Dein vorheriger Versuch wurde von der Pruefung verworfen:

{gruende}

Liefere die Bewertung noch einmal und behebe genau das. Aendere die uebrigen
Urteile nicht aus anderen Gruenden.
"""


def baue_frage(nutzlast: dict, gruende: list[str] | None = None) -> str:
    """Setzt Anweisung, etwaige Mahnung und Nutzlast zu einer Frage zusammen."""
    text = ANWEISUNG
    if gruende:
        text += MAHNUNG.format(gruende="\n".join(f"- {g}" for g in gruende))
    return (
        text
        + "\n\n## Die Potenziale und ihr Bestand\n\n```json\n"
        + json.dumps(nutzlast, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
