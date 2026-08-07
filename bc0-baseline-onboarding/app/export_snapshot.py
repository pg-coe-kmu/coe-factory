# -*- coding: utf-8 -*-
"""
Snapshot-Export (BC0 -> nachgelagerte BCs).

Erzeugt pro Mandant ein versioniertes, eingefrorenes JSON-Bundle (der "Daten-Vertrag"):
  mandant + stammdaten + bewertungen + reifegrad
Genau diese Struktur liefert später auch die Live-API (/api/v1/.../baseline).

Aufruf (im Ordner BC0_App):
    python export_snapshot.py                         # alle Mandanten -> snapshots/
    python export_snapshot.py "NoroAI Consulting GmbH"
    python export_snapshot.py "NoroAI Consulting GmbH" v1   # Versions-Label
"""
import os, sys, json, datetime
import app as A

SCHEMA_VERSION = "1.1"  # 1.1: Teilprozess-Felder tools/medienbrueche/schnittstellen/api ergänzt
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "snapshots")


def slug(s):
    keep = "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")
    while "__" in keep:
        keep = keep.replace("__", "_")
    return keep


def build_snapshot(cid, version):
    """Baut das Snapshot-Bundle exakt aus den App-Funktionen (= API-Antworten)."""
    base = A.get_company(cid)          # {company, profile, processes, ratings}
    rep = A.report(cid)               # aggregierter Reifegrad inkl. Matrizen/Spider
    meta = A.meta()                   # items(30) + dims

    # Profil/Unternehmensdaten aus profile_json (voll) auspacken
    prof = base.get("profile", {}) or {}
    unternehmensdaten = {}
    if prof.get("profile_json"):
        try:
            unternehmensdaten = json.loads(prof["profile_json"])
        except Exception:
            unternehmensdaten = {}

    # Prozesse + Teilprozesse (Stammdaten, ohne ratings-Dopplung)
    prozesse = []
    for pid, p in sorted(base.get("processes", {}).items()):
        prozesse.append({
            "process_id": p.get("process_id"),
            "process_name": p.get("process_name"),
            "kategorie": p.get("kategorie"),
            "owner_name": p.get("owner_name"),
            "owner_role": p.get("owner_role"),
            "trigger": p.get("trigger_text"),
            "input": p.get("input_text"),
            "output": p.get("output_text"),
            "teilprozesse": [
                {"sub_process_id": t.get("sub_process_id"), "step_no": t.get("step_no"),
                 "name": t.get("sub_process_name"), "notation": t.get("notation"),
                 "tools": t.get("tools"), "medienbrueche": t.get("medienbrueche"),
                 "schnittstellen": t.get("schnittstellen"), "api": t.get("api")}
                for t in p.get("tps", [])
            ],
        })

    # Bewertungen als flache, sortierte Liste (stabile IDs)
    bewertungen = []
    rat = base.get("ratings", {})
    for sid in sorted(rat.keys()):
        for item_nr in sorted(rat[sid].keys()):
            v = rat[sid][item_nr]
            pid = sid.split(".")[0]
            bewertungen.append({
                "id": "%s.I-%02d" % (sid, int(item_nr)),
                "process_id": pid,
                "sub_process_id": sid,
                "item_nr": int(item_nr),
                "stufe": v.get("stufe"),
                "beleg": v.get("beleg"),
                "quelle": v.get("quelle"),
            })

    co = base.get("company", {})
    snap = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_version": version,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "generator": "BC0 Onboarding-Tool",
        "mandant": {
            "id": co.get("id"),
            "name": co.get("name"),
            "branche": co.get("branche"),
            "rechtsform": co.get("rechtsform"),
            "mitarbeitende": co.get("ma"),
            "region": co.get("region"),
            "status": co.get("status"),
            "profil_kurz": {
                "geschaeftsmodell": prof.get("geschaeftsmodell"),
                "tech_stack": prof.get("tech_stack"),
            },
            "unternehmensdaten": unternehmensdaten,
        },
        "stammdaten": {
            "items": meta.get("items"),          # 30 Bitkom-Items (Referenz)
            "dimensionen": meta.get("dims"),     # 5 Dimensionen
            "prozesse": prozesse,                # KP + TP
        },
        "bewertungen": bewertungen,              # 600 Item-Bewertungen
        "reifegrad": {
            "gesamt": rep.get("gesamt"),
            "beleg_quote": rep.get("beleg_quote"),
            "n_bewertungen": rep.get("n_bewertungen"),
            "dimension_durchschnitt": rep.get("dim_avg"),
            "kp_rows": rep.get("kp_rows"),
            "prozessautomatisierung_matrix": rep.get("auto"),
            "crossfunktionale_matrix": rep.get("cross"),
            "spider_6": rep.get("spider6"),
            "krit15_labels": rep.get("krit15_labels"),
            "krit15_overall": rep.get("krit15_overall"),
            "items12": rep.get("items12"),
            "items12_overall": rep.get("items12_overall"),
        },
    }
    return snap


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else None
    version = sys.argv[2] if len(sys.argv) > 2 else "v1"
    os.makedirs(OUT, exist_ok=True)
    c = A.db()
    if name:
        rows = c.execute("SELECT id,name FROM companies WHERE name=?", (name,)).fetchall()
    else:
        rows = c.execute("SELECT id,name FROM companies ORDER BY id").fetchall()
    c.close()
    if not rows:
        sys.exit("Kein Mandant gefunden%s." % (" ('%s')" % name if name else ""))
    for r in rows:
        snap = build_snapshot(r["id"], version)
        fn = os.path.join(OUT, "%s_baseline_%s.json" % (slug(r["name"]), version))
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        print("OK: %s  (Prozesse=%d, Bewertungen=%d, Gesamt-Ø=%s)" % (
            os.path.relpath(fn, HERE), len(snap["stammdaten"]["prozesse"]),
            len(snap["bewertungen"]), snap["reifegrad"]["gesamt"]))


if __name__ == "__main__":
    main()
