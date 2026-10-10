"""
BC2 · Die Anweisung an das Modell für den Ausarbeitungsschritt (#301).

Gleiche Bauform wie Erkennung und Bewertung: Anweisung, etwaige Mahnung,
Nutzlast als JSON. Zwei Dinge sind hier neu und beide in ADR-010 · BC2
begründet.

**Platzhalter statt Zahlen.** Ein Akzeptanzkriterium will eine Zielgröße, und
genau die wäre die Zahl mit Einheit, die der Wächter verwirft — und sie stünde
neben dem gerechneten Automatisierungsgrad und könnte ihm widersprechen. Das
Modell schreibt darum ``{grad_min}`` und ``{grad_max}``; Python setzt die
gerechnete Zahl ein. Mehr Platzhalter gibt es nicht: Euro und Stunden gehören in
``value``, ein Kriterium „spart so und so viel“ ist kein Abnahmekriterium.

**Das Antwortschema sichert nur die Form** (#319): Pflichtfelder,
Aufzählungen, mindestens ein Eintrag, wo der Vertrag einen verlangt. Mindestlängen,
Platzhalter, SOPHIST/GWT und die gebundenen Systeme kann es nicht ausdrücken —
dafür bleibt der Wächter.

**Die Systeme sind gebunden.** ``betroffene_systeme`` darf nur nennen, was der
Bestand nennt — dieselbe Regel wie beim Schnitt, wo der Wächter die
Teilprozesse nachprüft. ``rolle`` und ``integration`` sind Aufzählungen des
Vertrags und stehen deshalb wörtlich hier.
"""

from __future__ import annotations

import json

from erkennung.modellruf import objekt, oder_null

__all__ = [
    "ANTWORTSCHEMA", "ANWEISUNG", "INTEGRATIONEN", "MAHNUNG", "PLATZHALTER", "ROLLEN",
    "STUFEN", "baue_frage",
]

#: Die einzigen Platzhalter, die Python einsetzt (ADR-010 · BC2, 2.4).
PLATZHALTER = ("grad_min", "grad_max")

#: Die Aufzählungen aus ``konzept.schema.json`` v3.1. Hier und nicht im Wächter,
#: weil Anweisung, Antwortschema und Wächter sie alle drei brauchen und der
#: Wächter ohnehin von hier liest.
ROLLEN = ("Quelle", "Ziel", "Quelle+Ziel")
INTEGRATIONEN = ("API", "RPA", "Datei", "DB", "Email", "OCR", "Manuell")
STUFEN = ("low", "med", "high")

ANWEISUNG = """\
Du bist der Ausarbeitungsschritt von BC2 (Strategic Advisor) in einer
CoE-Factory. Die Potenziale eines Kernprozesses sind schon geschnitten, bewertet
und gerechnet. Du arbeitest sie zu einem **Konzept** aus, das an ein Team geht,
das daraus Tickets schneidet und baut — und das dem Mandanten vorgelegt wird.

Du aenderst nichts am Schnitt, an der Loesungsklasse, am Rang oder an der
Bewertung. Du schreibst die Texte dazu.

## Was du NICHT tust

Du rechnest nicht und nennst keine Zahl mit Einheit: keine Euro, keine Stunden,
keine Minuten, kein %, keine PT, keine Punkte. Eine Pruefung findet jede solche
Zahl in jedem Textfeld und verwirft den Aufruf. Schreibe "ein grosser Teil der
Faelle", "woechentlich", "spuerbar schneller" — nicht den Wert. Auch Werte aus
dem Bestand oder dem Tech-Stack zitierst du nicht.

**Die einzige Ausnahme sind zwei Platzhalter**, die nur in den Texten eines
Potenzials stehen duerfen (nicht im Kontext, nicht in der Gesamtempfehlung):

- `{grad_min}` und `{grad_max}` — der untere und obere Automatisierungsgrad
  dieses Potenzials, als Zahl ohne Einheit. Schreibe das `%` dahinter selbst:
  "... dann werden mindestens {grad_min} % der Anfragen ohne Nacharbeit
  zugeordnet". Python setzt die gerechnete Zahl ein.

Jeder andere Ausdruck in geschweiften Klammern wird verworfen. Fuer Kriterien
ohne Bezug zum Automatisierungsgrad (etwa Compliance) nennst du die Messgroesse
und die Richtung ("... sinkt gegenueber der Ausgangsmessung"), keinen Zielwert.

## Je Konzept

- `prozess_kurzbeschreibung` — der Kernprozess in einem Satz, hoechstens 280
  Zeichen.
- `hauptschmerzpunkte` — die Schmerzpunkte des Kernprozesses, je mit
  `beschreibung` und `auswirkung`, optional `haeufigkeit` (in Worten). Dein
  Material sind die `schmerzpunkte` der Potenziale; fasse gleiche zusammen,
  erfinde keine neuen.
- `gesamtempfehlung_begruendung` — warum die Potenziale dieses Konzepts in der
  Reihenfolge ihres `potenzialrang` umgesetzt werden sollten, oder wo eine
  fachliche Abhaengigkeit dagegen spricht. Die Reihenfolge selbst setzt Python.

## Je Potenzial — fuer JEDES Potenzial der Nutzlast genau ein Eintrag

- `beschreibung` — Markdown, ausfuehrlich, mindestens 300 Zeichen. Pflichtinhalt:
  (a) was wird automatisiert, (b) in welchen Teilprozessen, (c) mit welchem
  Ergebnis, (d) Datenfluesse, (e) beteiligte Rollen, (f) Vorbedingungen,
  (g) Sonderfaelle und Ausnahmen.
- `to_be_vision` — der Soll-Zustand, ausfuehrlich, mindestens 300 Zeichen.
- `to_be_kurz` — derselbe Soll-Zustand in ein bis zwei Saetzen.
- `user_story` — SOPHIST-Schablone, ein Satz: "Als <Rolle> moechte ich <Ziel>,
  damit <Nutzen>."
- `akzeptanzkriterien` — mindestens eines, je mit
  `kriterium` in **Given/When/Then** als ein Satz: "Gegeben <Ausgangslage>, wenn
  <Ereignis>, dann <erwartetes Ergebnis>." und
  `messverfahren`: woran geprueft wird, ob es erfuellt ist (z. B.
  "Zeitstempel im Vorgangsprotokoll", "Stichprobe von Vorgaengen").
- `fachliche_anforderungen` — mindestens ein Satz: was fachlich gelten muss.
- `betroffene_systeme` — mindestens eines, zuerst die Systeme, mit denen der
  Ablauf heute arbeitet. `name` **nur** ein System, das im Bestand (`werkzeuge`,
  `schnittstellen`, `api`, `medienbrueche`, `ablauf` der Teilprozesse) oder im
  `tech_stack` genannt ist, in dessen Schreibweise.
  `rolle` woertlich eines von `Quelle`, `Ziel`, `Quelle+Ziel`; `integration`
  woertlich eines von `API`, `RPA`, `Datei`, `DB`, `Email`, `OCR`, `Manuell`.
- `loesungsansatz` — Markdown, wie die Automatisierung technisch aussehen
  koennte. Ausgangspunkt ist der `loesungsansatz` der Nutzlast; vertiefe ihn,
  aendere ihn nicht.
- `tech_stack_empfehlung` — mindestens ein Werkzeug. Bevorzuge, was der
  `tech_stack` des Mandanten schon fuehrt, und beachte seine Vorgaben (etwa
  EU- oder Open-Source-Pflicht). Ist er "nicht erhoben", empfiehl nur, was zu den
  genannten Werkzeugen passt.
- `voraussetzungen` — was fachlich oder technisch vorher gelten muss (darf leer
  sein).
- `risiken` — je mit `beschreibung`, `wahrscheinlichkeit` und `auswirkung`
  (woertlich `low`, `med` oder `high`), optional `gegenmassnahme`.
- `zukunftssicherheit` — ein Satz: traegt die Loesung, wenn sich Systeme oder
  Mengen aendern?
- `abhaengigkeiten` — fachliche Abhaengigkeiten zu anderen Potenzialen dieses
  Laufs, je `{"potenzial": "<id>", "grund": "..."}`. Erlaubt sind die ids dieses
  Konzepts und die unter `uebrige_potenziale_des_laufs`, nicht die eigene. Leer,
  wenn es keine gibt.

## Ausgabe

Antworte mit NICHTS als einem JSON-Objekt dieser Form:

{
  "kontext": {
    "prozess_kurzbeschreibung": "...",
    "hauptschmerzpunkte": [
      {"beschreibung": "...", "auswirkung": "...", "haeufigkeit": null}
    ]
  },
  "potenziale": [
    {
      "id": "die id des Potenzials, woertlich",
      "beschreibung": "...",
      "to_be_vision": "...",
      "to_be_kurz": "...",
      "user_story": "Als ... moechte ich ..., damit ...",
      "akzeptanzkriterien": [
        {"kriterium": "Gegeben ..., wenn ..., dann ...", "messverfahren": "..."}
      ],
      "fachliche_anforderungen": ["..."],
      "betroffene_systeme": [{"name": "...", "rolle": "Quelle", "integration": "API"}],
      "loesungsansatz": "...",
      "tech_stack_empfehlung": ["..."],
      "voraussetzungen": ["..."],
      "risiken": [
        {"beschreibung": "...", "wahrscheinlichkeit": "med", "auswirkung": "low",
         "gegenmassnahme": "..."}
      ],
      "zukunftssicherheit": "...",
      "abhaengigkeiten": []
    }
  ],
  "gesamtempfehlung_begruendung": "..."
}
"""

_TEXT = {"type": "string"}
_TEXTE = {"type": "array", "items": _TEXT}
_STUFE = {"type": "string", "enum": list(STUFEN)}

#: Die Form der Antwort, wie sie die API beim Dekodieren einhält (#319).
ANTWORTSCHEMA = objekt(
    kontext=objekt(
        prozess_kurzbeschreibung=_TEXT,
        hauptschmerzpunkte={"type": "array", "minItems": 1, "items": objekt(
            beschreibung=_TEXT, auswirkung=_TEXT, haeufigkeit=oder_null(_TEXT),
        )},
    ),
    potenziale={"type": "array", "items": objekt(
        id=_TEXT,
        beschreibung=_TEXT,
        to_be_vision=_TEXT,
        to_be_kurz=_TEXT,
        user_story=_TEXT,
        akzeptanzkriterien={"type": "array", "minItems": 1, "items": objekt(
            kriterium=_TEXT, messverfahren=_TEXT,
        )},
        fachliche_anforderungen={**_TEXTE, "minItems": 1},
        betroffene_systeme={"type": "array", "minItems": 1, "items": objekt(
            name=_TEXT,
            rolle={"type": "string", "enum": list(ROLLEN)},
            integration={"type": "string", "enum": list(INTEGRATIONEN)},
        )},
        loesungsansatz=_TEXT,
        tech_stack_empfehlung={**_TEXTE, "minItems": 1},
        voraussetzungen=_TEXTE,
        risiken={"type": "array", "items": objekt(
            beschreibung=_TEXT,
            wahrscheinlichkeit=_STUFE,
            auswirkung=_STUFE,
            gegenmassnahme=oder_null(_TEXT),
        )},
        zukunftssicherheit=_TEXT,
        abhaengigkeiten={"type": "array", "items": objekt(potenzial=_TEXT, grund=_TEXT)},
    )},
    gesamtempfehlung_begruendung=_TEXT,
)

MAHNUNG = """\

## ACHTUNG — dieser Aufruf ist eine Wiederholung

Dein vorheriger Versuch wurde von der Pruefung verworfen:

{gruende}

Liefere dieselbe Ausarbeitung noch einmal und behebe genau das.
"""


def baue_frage(nutzlast: dict, gruende: list[str] | None = None) -> str:
    """Setzt Anweisung, etwaige Mahnung und Nutzlast zu einer Frage zusammen."""
    text = ANWEISUNG
    if gruende:
        text += MAHNUNG.format(gruende="\n".join(f"- {g}" for g in gruende))
    return (
        text
        + "\n\n## Die Nutzlast\n\n```json\n"
        + json.dumps(nutzlast, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
