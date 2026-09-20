#!/usr/bin/env python3
"""PROTOTYP zu #194 — wegwerfbar, nicht befoerdern.

Giesst Nutzlasten, Schnitte und Messbefunde in EINE doppelklickbare HTML-Datei.
Inline, weil eine Seite von file:// keine Nachbardateien laden darf -- und weil
sie per Mail weitergehen koennen soll.

Aufruf:  python3 packen.py
"""
import json
import pathlib
import collections

HIER = pathlib.Path(__file__).parent
WURZEL = HIER.parents[2]
SNAPSHOT = WURZEL / "bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json"


def aufloesung_messen():
    """Wie viel Eigenes traegt ein Teilprozess gegenueber seinen Geschwistern?"""
    d = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    proz = d["stammdaten"]["prozesse"]
    felder = ["name", "notation", "tools", "medienbrueche", "schnittstellen", "api"]
    ergebnis = {}
    for f in felder:
        identisch = 0
        for p in proz:
            werte = {(t.get(f) or "") for t in p["teilprozesse"]}
            if len(werte) == 1:
                identisch += 1
        ergebnis[f] = identisch

    bew = collections.defaultdict(int)
    for b in d["bewertungen"]:
        bew[b["sub_process_id"]] += 1
    ohne = sum(
        1
        for blk in d["reifegrad"]["prozessautomatisierung_matrix"].values()
        for r in blk["rows"]
        if bew.get(r["sub_process_id"], 0) == 0
    )
    return {
        "felder": ergebnis,
        "identisch_bei_allen": sum(1 for f, n in ergebnis.items() if n == 10),
        "ohne_bewertung": ohne,
    }


MUSTER = {
    "E-Mail-Anfrage ins CRM übernehmen":
        r"(e-?mail|email).{0,40}(crm|erfass)|(crm|erfass).{0,40}(e-?mail|email)",
    "AVV-Unterzeichnung digitalisieren": r"avv",
}


def doppelgaenger(schnitte):
    """Zaehlt, wie oft DERSELBE Sachverhalt als eigenes Potenzial auftaucht.

    Der Punkt: die mechanische Pruefung sieht das NICHT. Jede Kopie nennt nur
    ihren eigenen Teilprozess, es gibt also keine Ueberschneidung zu finden.
    """
    import re
    out = {}
    for s, aufrufe in schnitte.items():
        out[s] = {}
        for name, rx in MUSTER.items():
            treffer = [
                f"{a['aufruf']}/{p['id']}"
                for a in aufrufe
                for p in (a.get("ergebnis") or {}).get("potenziale", [])
                if re.search(rx, p["titel"], re.I)
            ]
            out[s][name] = treffer
    return out


def main():
    nutz = json.loads((HIER / "nutzlasten.json").read_text(encoding="utf-8"))
    schnitte, meta, beispiel = {}, {}, {}

    for s in "ABC":
        datei = HIER / f"schnitt-{s}.json"
        schnitte[s] = json.loads(datei.read_text(encoding="utf-8"))[s] if datei.exists() else []
        n = nutz["nutzlasten"][s]
        groessen = [len(json.dumps(x, ensure_ascii=False)) for x in n]
        meta[s] = {
            "aufrufe": len(n),
            "min": min(groessen), "max": max(groessen), "summe": sum(groessen),
            "gelaufen": len(schnitte[s]),
        }
        # Als Beispielnutzlast den Aufruf nehmen, der die Wiederholung am besten
        # zeigt: bei A und B einen mit mehreren Geschwistern.
        wahl = n[5] if s == "A" else n[1] if s == "B" and len(n) > 1 else n[0]
        beispiel[s] = {"aufruf": wahl["aufruf"], "inhalt": wahl}

    daten = {
        "paket": nutz["paket"],
        "rahmen": nutz["rahmen"],
        "modell": "Claude Sonnet, je Aufruf eine eigene Sitzung",
        "schnitte": schnitte,
        "meta": meta,
        "nutzlastBeispiel": beispiel,
        "aufloesung": aufloesung_messen(),
        "doppelgaenger": doppelgaenger(schnitte),
    }

    vorlage = (HIER / "vorlage.html").read_text(encoding="utf-8")
    roh = json.dumps(daten, ensure_ascii=False)
    # Ein </script> in den Daten wuerde das Skript-Element schliessen.
    roh = roh.replace("</", "<\\/")
    ziel = HIER / "prototyp-194.html"
    ziel.write_text(vorlage.replace("/*DATEN*/", roh), encoding="utf-8")

    print(f"geschrieben: {ziel}  ({ziel.stat().st_size // 1024} KB)")
    for s in "ABC":
        print(f"  Schnitt {s}: {meta[s]['gelaufen']}/{meta[s]['aufrufe']} Aufrufe gelaufen, "
              f"{sum(len((a.get('ergebnis') or {}).get('potenziale', [])) for a in schnitte[s])} Potenziale")


if __name__ == "__main__":
    main()
