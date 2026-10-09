"""
BC2 · Die Anweisung an das Modell für den Erkennungsschritt.

Abgeleitet aus dem Prototyp zu #194, mit **einer inhaltlichen Korrektur**, die
erst beim Bau auffiel.

Die fünf Lösungsklassen
-----------------------

Der Prototyp bot dem Modell ``regelwerk | dokumentenverarbeitung | dialog |
entscheidungsunterstuetzung | assistenz`` an. Der Vertrag v3.0 und ADR-006 · BC2
kennen fünf **andere**: ``Regelwerk/Weiterleitung``, ``Integration``,
``Extraktion``, ``Textgenerierung``, ``Assistenz``. Nachgemessen an
``schnitt-C.json``: **10 von 10** Potenzialen des Prototyps tragen eine Klasse,
die ``konzept.schema.json`` nicht kennt und für die ``modell.parameter`` keinen
Korridor hat.

Drei davon haben keine Entsprechung, sondern nur eine Ähnlichkeit
(``dokumentenverarbeitung`` ≈ ``Extraktion``, ``dialog`` ≈ ``Textgenerierung``)
— das wäre eine Deutung, keine Übersetzung. Und **``Integration`` kam im
Prototyp überhaupt nicht vor**, weil sie im Angebot fehlte: ausgerechnet die
Klasse, die Medienbrüche schließt, also NoroAIs Hauptbefund. Der Prototyp konnte
die Klasse nicht treffen, die seine eigenen Daten nahelegen.

Der Korridor je Klasse steht **nicht** in der Anweisung. Das Modell verortet
später *in* ihm (ADR-006, 2.2, die zweite seiner vier Urteilsstellen); ihn hier
zu nennen hieße, Prozentzahlen in eine Anweisung zu schreiben, die Zahlen
verbietet.

Das Rechenverbot
----------------

Es brach in 2 von 21 Aufrufen — genau dort, wo Zahlen in der Nutzlast standen
(#194). Eine Bitte reicht also nicht, und die Anweisung sagt das jetzt auch:
sie nennt den Wächter beim Namen, damit das Verbot als Prüfung auftritt und
nicht als Höflichkeit.
"""

from __future__ import annotations

__all__ = ["ANWEISUNG", "MAHNUNG", "VORGAENGER", "baue_frage"]

ANWEISUNG = """\
Du bist der Erkennungsschritt von BC2 (Strategic Advisor) in einer CoE-Factory.
Du bekommst den freigegebenen Prozessbestand eines Mandanten und schneidest
daraus **Automatisierungspotenziale**.

## Was ein Potenzial ist

Eine abgrenzbare Automatisierungsmoeglichkeit innerhalb EINES Kernprozesses,
die fuer sich gebaut und in Betrieb genommen werden kann und einen eigenen
Nutzen traegt. Sie nennt die Teilprozesse, die sie beruehrt.

## Der Trenntest — die einzige Schnittregel

Zwei Potenziale liegen vor, wenn sie
  (1) **unabhaengig voneinander in Betrieb gehen koennten** UND
  (2) ihre Nutzenrechnungen sich **nicht doppelt zaehlen**.
Faellt eine der beiden Bedingungen weg, ist es EIN Potenzial.

Weder ein Teilprozess noch ein Schmerzpunkt schneidet Potenziale: ein
Teilprozess kann mehrere tragen, und ein Potenzial kann mehrere Teilprozesse
beruehren. Ein Potenzial deckt aber **nie zwei Kernprozesse** ab.

Du siehst in diesem Aufruf alle Teilprozesse auf einmal. Pruefe den Trenntest
deshalb auch **ueber Kernprozesse hinweg**: taucht derselbe Sachverhalt in zwei
Kernprozessen auf, schneide ihn dort, wo er hingehoert, statt ihn zweimal zu
nennen.

## Was du NICHT tust

Du rechnest nicht. Keine Euro-Betraege, keine Stunden, keine Punktzahlen, keine
Prozentwerte, keine Impact- oder Komplexitaetsnoten. Diese Zahlen entstehen
danach deterministisch in Python.

Das ist keine Bitte: deine Antwort laeuft durch eine Pruefung, die jede Zahl mit
einer Einheit (EUR, Stunden, Minuten, %, PT, Punkte) im Text findet. Findet sie
eine, wird der Aufruf verworfen. Wenn die Nutzlast gemessene Groessen enthaelt
(`bc1_gemessen`), dann sind sie fuer dein **Verstaendnis** da — nenne sie nicht,
zitiere sie nicht, rechne nicht mit ihnen. Schreibe "hoher Bearbeitungsaufwand",
nicht die Stundenzahl.

Du bewertest qualitativ: was geschieht heute, was schmerzt daran, was koennte
eine Maschine uebernehmen, welcher Loesungsweg liegt nahe.

## Die Loesungsklasse

Genau eine der folgenden fuenf, woertlich geschrieben:

- `Regelwerk/Weiterleitung` — deterministische Entscheidung, keine Textdeutung
- `Integration` — zwei Systeme verbinden, Medienbruch schliessen
- `Extraktion` — aus Dokument oder Mail strukturierte Daten ziehen
- `Textgenerierung` — Entwurf, den ein Mensch abnimmt
- `Assistenz` — Vorschlag, Mensch entscheidet jeden Fall

Erfinde keine sechste und schreibe keine andere Schreibweise.

## Wenn die Daten duenn sind

Traegt ein Teilprozess `"bewertungen": "nicht erhoben"` oder einen
Platzhalter-Namen ("Teilprozess 3"), dann erfinde fuer ihn kein Potenzial.
Trage ihn stattdessen unter `nicht_geschnitten` ein, mit dem Grund. "Nicht
erhoben" heisst nicht "schlecht" — es heisst, dass niemand hingesehen hat.

## Ausgabe

Antworte mit NICHTS als einem JSON-Objekt dieser Form:

{
  "potenziale": [
    {
      "id": "P1",
      "kernprozess_id": "KP-0X",
      "titel": "kurz, ohne Fuellwoerter",
      "beruehrte_teilprozesse": ["KP-0X.TP-1"],
      "ausgangslage": "was heute geschieht",
      "schmerzpunkte": ["..."],
      "loesungsansatz": "welcher Weg naheliegt",
      "loesungsklasse": "eine der fuenf oben, woertlich",
      "trenntest_begruendung": "warum das von den anderen getrennt ist — beide Bedingungen benennen",
      "unsicherheit": "woran die Einschaetzung haengt, oder null"
    }
  ],
  "nicht_geschnitten": [
    {"teilprozess_id": "KP-0X.TP-3", "grund": "..."}
  ]
}
"""

#: Nur angehängt, wenn die Nutzlast ``vorgaenger_kandidaten`` trägt (#295,
#: ADR-009 · BC2). Ein Lauf ohne Kandidaten bekommt dieselbe Anweisung wie
#: vorher — gemessen wurde die Erkennung ohne diesen Teil (#248), und die
#: Stabilitätsmessungen zu #299 sollen nicht über eine geänderte Frage laufen.
VORGAENGER = """\

## Schon gelieferte Potenziale (`vorgaenger_kandidaten`)

Zu einigen Teilprozessen dieses Pakets hat der Mandant schon Potenziale aus
einem frueheren Paket bekommen. Sie stehen unter `vorgaenger_kandidaten`. Schneide
das Paket wie immer — nach dem Trenntest, nicht nach diesen Kandidaten. Sage
danach fuer JEDEN Kandidaten genau einen Ausgang:

- `fortgeschrieben` — eines deiner neuen Potenziale ist **dasselbe Vorhaben**,
  nur auf neuem Datenstand. Nenne es unter `nachfolger`. Es muss dieselbe
  Loesungsklasse tragen; aendert sich die Loesung, ist es ein neues Potenzial,
  und der Kandidat ist gestrichen. Hoechstens ein Nachfolger je Kandidat und
  ein Kandidat je Nachfolger: wird ein Vorhaben geteilt oder zusammengelegt,
  sind die neuen Potenziale neu und die alten gestrichen.
- `gestrichen` — das Vorhaben faellt nach dem neuen Datenstand weg. Begruende
  es in `begruendung`; die Begruendung geht an das Team, das daran baut.
- `unveraendert` — aus diesem Paket nicht zu beurteilen. **Nur zulaessig, wenn
  `ausserhalb_dieses_pakets` nicht leer ist**: liegt ein Kandidat ganz in diesem
  Paket, hast du ihn vollstaendig neu gesehen und musst entscheiden.

Aehnlich zu klingen genuegt fuer `fortgeschrieben` nicht. Auch hier gilt das
Rechenverbot.

Ergaenze dein JSON-Objekt um:

  "vorgaenger": [
    {"kandidat": "V1", "ausgang": "fortgeschrieben", "nachfolger": "P2", "begruendung": "..."},
    {"kandidat": "V2", "ausgang": "gestrichen", "nachfolger": null, "begruendung": "..."}
  ]
"""

MAHNUNG = """\

## ACHTUNG — dieser Aufruf ist eine Wiederholung

Dein vorheriger Versuch wurde von der Pruefung verworfen:

{gruende}

Liefere dieselbe Analyse noch einmal und behebe genau das. Aendere den Schnitt
nicht aus anderen Gruenden.
"""


def baue_frage(nutzlast: dict, gruende: list[str] | None = None) -> str:
    """Setzt Anweisung, etwaige Mahnung und Bestand zu einer Frage zusammen."""
    import json

    text = ANWEISUNG
    if nutzlast.get("vorgaenger_kandidaten"):
        text += VORGAENGER
    if gruende:
        text += MAHNUNG.format(gruende="\n".join(f"- {g}" for g in gruende))
    return (
        text
        + "\n\n## Der Bestand\n\n```json\n"
        + json.dumps(nutzlast, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
