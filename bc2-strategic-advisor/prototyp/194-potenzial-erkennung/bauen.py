#!/usr/bin/env python3
"""PROTOTYP zu #194 — wegwerfbar, nicht befoerdern.

Baut aus BC0s eingefrorenem NoroAI-Snapshot die Nutzlast, die das Modell je
Aufruf-Schnitt zu sehen bekaeme, und schreibt sie als JSON neben dieses Skript.

Drei Schnitte ueber DASSELBE Paket:
    A  ein Aufruf je Teilprozess
    B  ein Aufruf je Kernprozess (alle freigegebenen Teilprozesse zusammen)
    C  ein Aufruf je Paket (alles auf einmal)

Aufruf:  python3 bauen.py
"""
import json
import pathlib
import collections

HIER = pathlib.Path(__file__).parent
WURZEL = HIER.parents[2]
SNAPSHOT = WURZEL / "bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json"

# Das Paket dieses Prototyps. Frei gewaehlt, weil der Snapshot keine Pakete
# kennt (er ist vom 30.08., Gate 0 wird erst seit dem 18.09. benutzt).
# Gewaehlt, damit die unangenehmen Faelle drin sind:
#   KP-02  fuenf Teilprozesse mit fuenf verschiedenen Stufenmustern
#   KP-03  dito, dazu ein echter Medienbruch im Text
#   KP-05  fuenf Teilprozesse mit EINEM Stufenmuster -- der entartete Fall
#   KP-06  nur TP-2, der einzige mit einem BC1-Profil
PAKET = {
    "company_id": "7c2d5ee9-2a9a-5990-810f-502ea2b2012d",
    "paket_id": "PROTOTYP-194",
    "uebergeben_am": "2026-09-20T00:00:00Z",
    "teilprozesse": [
        "KP-02.TP-1", "KP-02.TP-2", "KP-02.TP-3", "KP-02.TP-4", "KP-02.TP-5",
        "KP-03.TP-1", "KP-03.TP-2", "KP-03.TP-3", "KP-03.TP-4", "KP-03.TP-5",
        "KP-05.TP-1", "KP-05.TP-2", "KP-05.TP-3", "KP-05.TP-4", "KP-05.TP-5",
        "KP-06.TP-2",
    ],
}

# Der einzige BC1-Wert, den diese Karte belegt hat (#166, gemessen an BC1s
# echter Zeile). Alles andere traegt BC1 im Snapshot nicht -- der ist aelter
# als BC1s erste Lieferung vom 08.09.2026.
BC1_PROFILE = {
    "KP-06.TP-2": {
        "focus_step_duration_minutes": None,
        "frequency_per_year": None,
        "jahresstunden": 540,
        "ist_kosten_eur": 23220,
        "focus_step_duration_source": "geschaetzt",
        "herkunft": "gemessen in #166 an BC1s echter Profilzeile, nicht aus dem Snapshot",
    }
}


def laden():
    d = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    prozesse = {p["process_id"]: p for p in d["stammdaten"]["prozesse"]}
    items = {i["item_nr"]: i for i in d["stammdaten"]["items"]}
    bew = collections.defaultdict(list)
    for b in d["bewertungen"]:
        bew[b["sub_process_id"]].append(b)
    matrix = {}
    for kp, blk in d["reifegrad"]["prozessautomatisierung_matrix"].items():
        for r in blk["rows"]:
            matrix[r["sub_process_id"]] = r["krit"]
    return d, prozesse, items, bew, matrix


def teilprozess_block(tp_id, prozesse, items, bew, matrix):
    """Alles, was BC2 ueber genau einen Teilprozess weiss."""
    kp_id = tp_id.split(".")[0]
    kp = prozesse[kp_id]
    tp = next(t for t in kp["teilprozesse"] if t["sub_process_id"] == tp_id)
    bewertungen = sorted(bew[tp_id], key=lambda b: b["item_nr"])
    return {
        "teilprozess_id": tp_id,
        "name": tp["name"],
        "schritt_nr": tp.get("step_no"),
        "ablauf": tp.get("notation"),
        "werkzeuge": tp.get("tools"),
        "medienbrueche": tp.get("medienbrueche"),
        "schnittstellen": tp.get("schnittstellen"),
        "api": tp.get("api"),
        "bitkom": [
            {
                "item": b["item_nr"],
                "kriterium": items[b["item_nr"]]["kriterium"],
                "frage": items[b["item_nr"]]["frage"],
                "stufe": b["stufe"],
                "beleg": b["beleg"],
            }
            for b in bewertungen
        ],
        "automatisierungsgrad_je_kriterium": matrix.get(tp_id),
        "bc1_profil": BC1_PROFILE.get(tp_id),
    }


def kernprozess_kopf(kp_id, prozesse):
    kp = prozesse[kp_id]
    return {
        "kernprozess_id": kp_id,
        "name": kp["process_name"],
        "kategorie": kp.get("kategorie"),
        "ausloeser": kp.get("trigger"),
        "eingang": kp.get("input"),
        "ausgang": kp.get("output"),
    }


def main():
    d, prozesse, items, bew, matrix = laden()
    tps = PAKET["teilprozesse"]
    nach_kp = collections.defaultdict(list)
    for tp in tps:
        nach_kp[tp.split(".")[0]].append(tp)

    rahmen = {
        "mandant": d["mandant"]["name"],
        "branche": d["mandant"]["branche"],
        "mitarbeitende": d["mandant"]["mitarbeitende"],
        "company_id": PAKET["company_id"],
        "paket_id": PAKET["paket_id"],
        "uebergeben_am": PAKET["uebergeben_am"],
        "mischsatz_eur_h": 43,
    }

    nutzlasten = {"A": [], "B": [], "C": []}

    # A -- ein Aufruf je Teilprozess
    for tp in tps:
        nutzlasten["A"].append({
            "aufruf": tp,
            "rahmen": rahmen,
            "kernprozess": kernprozess_kopf(tp.split(".")[0], prozesse),
            "teilprozesse": [teilprozess_block(tp, prozesse, items, bew, matrix)],
        })

    # B -- ein Aufruf je Kernprozess
    for kp_id, tp_liste in sorted(nach_kp.items()):
        nutzlasten["B"].append({
            "aufruf": kp_id,
            "rahmen": rahmen,
            "kernprozess": kernprozess_kopf(kp_id, prozesse),
            "teilprozesse": [teilprozess_block(t, prozesse, items, bew, matrix) for t in tp_liste],
        })

    # C -- ein Aufruf je Paket
    nutzlasten["C"].append({
        "aufruf": PAKET["paket_id"],
        "rahmen": rahmen,
        "kernprozesse": [
            {
                **kernprozess_kopf(kp_id, prozesse),
                "teilprozesse": [teilprozess_block(t, prozesse, items, bew, matrix) for t in tp_liste],
            }
            for kp_id, tp_liste in sorted(nach_kp.items())
        ],
    })

    ziel = HIER / "nutzlasten.json"
    ziel.write_text(json.dumps(
        {"paket": PAKET, "rahmen": rahmen, "nutzlasten": nutzlasten},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"geschrieben: {ziel}")
    for schnitt in "ABC":
        n = nutzlasten[schnitt]
        groessen = [len(json.dumps(x, ensure_ascii=False)) for x in n]
        print(f"  Schnitt {schnitt}: {len(n):2d} Aufrufe, "
              f"je {min(groessen):6d}–{max(groessen):6d} Zeichen, "
              f"Summe {sum(groessen):7d}")


if __name__ == "__main__":
    main()
