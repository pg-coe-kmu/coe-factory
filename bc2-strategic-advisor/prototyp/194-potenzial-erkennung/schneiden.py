#!/usr/bin/env python3
"""PROTOTYP zu #194 — wegwerfbar, nicht befoerdern.

Laesst dasselbe Paket unter drei Aufruf-Schnitten durch das Modell laufen und
legt die Antworten roh ab. Jeder Aufruf ist eine eigene Sitzung ohne Gedaechtnis
an die anderen -- sonst waere der Vergleich zwischen den Schnitten wertlos.

Aufruf:  python3 schneiden.py [A|B|C ...]
"""
import json
import pathlib
import subprocess
import sys
import time

HIER = pathlib.Path(__file__).parent
MODELL = "sonnet"

ANWEISUNG = """\
Du bist der Erkennungsschritt von BC2 (Strategic Advisor) in einer CoE-Factory.
Du bekommst den freigegebenen Prozessbestand eines Mandanten und sollst daraus
**Automatisierungspotenziale** schneiden.

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
beruehren. Ein Potenzial deckt aber nie zwei Kernprozesse ab.

## Was du NICHT tust

Du rechnest nicht. Keine Euro-Betraege, keine Stunden, keine Punktzahlen, keine
Prozentwerte, keine Impact- oder Komplexitaetsnoten. Diese Zahlen entstehen
spaeter deterministisch in Python. Erfinde sie nicht, auch nicht als Schaetzung.

Du bewertest qualitativ: was geschieht heute, was schmerzt daran, was koennte
eine Maschine uebernehmen, welcher Loesungsweg liegt nahe.

## Wenn die Daten duenn sind

Traegt ein Teilprozess keine Bewertungen oder nur einen Platzhalter-Namen
("Teilprozess 3"), dann erfinde fuer ihn kein Potenzial. Trage ihn stattdessen
unter `nicht_geschnitten` ein, mit dem Grund. Eine 0 in den Kennzahlen bedeutet
"nicht erhoben", nicht "schlecht".

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
      "loesungsklasse": "regelwerk|dokumentenverarbeitung|dialog|entscheidungsunterstuetzung|assistenz",
      "trenntest_begruendung": "warum das von den anderen Potenzialen getrennt ist -- beide Bedingungen benennen",
      "unsicherheit": "woran die Einschaetzung haengt, oder null"
    }
  ],
  "nicht_geschnitten": [
    {"teilprozess_id": "KP-0X.TP-3", "grund": "..."}
  ]
}
"""


def aufrufen(nutzlast: dict) -> str:
    frage = (
        ANWEISUNG
        + "\n\n## Der Bestand\n\n```json\n"
        + json.dumps(nutzlast, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
    p = subprocess.run(
        ["claude", "-p", "--model", MODELL, frage],
        capture_output=True, text=True, timeout=600,
    )
    if p.returncode != 0:
        return json.dumps({"fehler": p.stderr[-2000:]}, ensure_ascii=False)
    return p.stdout


def json_schaelen(roh: str):
    t = roh.strip()
    if "```" in t:
        teile = t.split("```")
        for teil in teile:
            teil = teil.lstrip()
            if teil.startswith("json"):
                teil = teil[4:]
            teil = teil.strip()
            if teil.startswith("{"):
                t = teil
                break
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b == -1:
        return None
    try:
        return json.loads(t[a:b + 1])
    except json.JSONDecodeError:
        return None


def main():
    daten = json.loads((HIER / "nutzlasten.json").read_text(encoding="utf-8"))
    schnitte = [s.upper() for s in sys.argv[1:]] or ["A", "B", "C"]

    for s in schnitte:
        # Eine Datei je Schnitt. Zwei Laeufe parallel in EINE Datei schreiben zu
        # lassen kostete beim ersten Versuch die Ergebnisse von B.
        ziel = HIER / f"schnitt-{s}.json"
        alles = {s: json.loads(ziel.read_text(encoding="utf-8"))[s]} if ziel.exists() else {}
        alles.setdefault(s, [])
        erledigt = {e["aufruf"] for e in alles[s]}
        for nutzlast in daten["nutzlasten"][s]:
            name = nutzlast["aufruf"]
            if name in erledigt:
                print(f"  {s}/{name}: schon da")
                continue
            t0 = time.time()
            roh = aufrufen(nutzlast)
            geschaelt = json_schaelen(roh)
            n = len(geschaelt.get("potenziale", [])) if geschaelt else "?"
            print(f"  {s}/{name}: {n} Potenziale  ({time.time()-t0:.0f}s)")
            alles[s].append({"aufruf": name, "roh": roh, "ergebnis": geschaelt})
            ziel.write_text(json.dumps(alles, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\ngeschrieben: {ziel}")


if __name__ == "__main__":
    main()
