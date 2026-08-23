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

SCHEMA_VERSION = "1.2"
# 1.1: Teilprozess-Felder tools/medienbrueche/schnittstellen/api ergaenzt
# 1.2: owner_name/owner_role entfallen, dafuer eigner_ids/sponsor_ids (22.08.2026).
#      BREAKING fuer Leser, die owner_name erwarten — BC1 hat die Umstellung am
#      22.08. bereits vollzogen und liest die neuen Felder.
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "snapshots")


def slug(s):
    keep = "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")
    while "__" in keep:
        keep = keep.replace("__", "_")
    return keep


def _admin_kontext():
    """Ein Benutzer-Objekt mit Adminrechten fuer den Exportlauf.

    Das Skript laeuft auf dem Server, von Hand, durch jemanden, der ohnehin
    Zugriff auf die Datenbank hat — es ist kein Weg an der Anmeldung vorbei,
    sondern der Ersatz fuer sie in einem Vorgang ohne HTTP-Anfrage.

    Bewusst OHNE Mandantenzuordnung: Ein Admin sieht nach
    `darf_mandanten_sehen()` ohnehin alle, und eine erfundene Zuordnung waere
    eine zweite Wahrheit.
    """
    from bc0_auth import Benutzer, Rolle
    return Benutzer(benutzer_id="export", email="export@bc0.local",
                    name="Snapshot-Export", rolle=Rolle.ADMIN)


def _eigner_und_sponsoren(cid):
    """Personen-IDs je Kernprozess, getrennt nach Eigner und Sponsor.

    Liest `prozess_personen` unmittelbar aus der Datenbank statt aus
    `get_company()` — der Endpunkt liefert die Zuordnungen nicht mit, und ihn
    dafuer zu erweitern hiesse, die Oberflaeche fuer einen Exportzweck zu
    aendern.

    Sortiert, damit zwei Ausfuehrungen auf demselben Datenstand denselben
    Snapshot ergeben — dieselbe Zusicherung wie beim Reifegradbericht.

    Returns:
        dict: ``{process_id: {"eigner": [...], "sponsor": [...]}}``.
        Fehlt die Tabelle (SQLite-Entwicklungsmodus vor Schema v1.3), kommt ein
        leeres Woerterbuch zurueck und der Export laeuft ohne die IDs weiter —
        er soll nicht daran scheitern, dass das Register noch nicht steht.
    """
    zu = {}
    c = A.db()
    try:
        w = "company_id::text=?" if A.PG else "company_id=?"
        for r in c.execute(
                "SELECT process_id, person_id, funktion FROM prozess_personen "
                "WHERE " + w + " ORDER BY process_id, person_id", (cid,)).fetchall():
            eintrag = zu.setdefault(r["process_id"], {"eigner": [], "sponsor": []})
            if r["funktion"] in eintrag:
                eintrag[r["funktion"]].append(r["person_id"])
    except Exception:
        zu = {}
    finally:
        c.close()
    return zu


def build_snapshot(cid, version):
    """Baut das Snapshot-Bundle exakt aus den App-Funktionen (= API-Antworten)."""
    # Seit Etappe 4b (11.08.2026) verlangen get_company() und report() einen
    # angemeldeten Benutzer (Depends). Direkt aufgerufen bekaemen sie das
    # Depends-Objekt statt eines Benutzers und liefen in einen AttributeError.
    # Das Skript lief deshalb seit dem 11.08. nicht mehr — aufgefallen erst
    # beim Umbau am 22.08. Der Exportlauf ist ein Administratorvorgang, also
    # wird hier ein Admin-Kontext gebaut, kein Schutz umgangen.
    admin = _admin_kontext()

    base = A.get_company(cid, admin)   # {company, profile, processes, ratings}
    rep = A.report(cid, admin)         # aggregierter Reifegrad inkl. Matrizen/Spider
    meta = A.meta()                    # items(30) + dims

    beteiligung = _eigner_und_sponsoren(cid)

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
            # KEINE Klarnamen im Snapshot (ADR-004 R5, geaendert am 22.08.2026).
            #
            # Bis hierher standen an dieser Stelle owner_name und owner_role.
            # Der Rechteentzug aus schema_v1.3_teil_a2 schliesst den Lesepfad
            # ueber die Datenbank — dieser Export war der zweite Weg, und
            # ausgerechnet den benutzt BC1 heute. Aufgefallen ist es durch
            # Richards Rueckmeldung vom 22.08.: "Die Klarnamen fliessen derzeit
            # auch ueber deinen Snapshot-Export."
            #
            # Ersatz sind die Entitaets-IDs aus ref_personen (P-NN). Wer den
            # Klarnamen braucht, fragt in BC0 nach — das ist der Zweck der
            # Pseudonymisierung, nicht ihr Nebeneffekt.
            "eigner_ids": beteiligung.get(p.get("process_id"), {}).get("eigner", []),
            "sponsor_ids": beteiligung.get(p.get("process_id"), {}).get("sponsor", []),
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
    # Die Spalte heisst in PostgreSQL `company_id` (UUID) und in SQLite `id`.
    # Statt das hier ein zweites Mal zu entscheiden, wird die Abfrage aus app.py
    # uebernommen: `A.SEL_CO` liefert in beiden Dialekten eine Spalte `id`.
    # Vorher stand hier `SELECT id,name FROM companies` — das lief nur gegen
    # SQLite und brach gegen PostgreSQL mit `column "id" does not exist`
    # (gefunden am 23.08.2026 beim ersten Lauf gegen die produktive Datenbank).
    if name:
        rows = c.execute(A.SEL_CO + " WHERE name=?", (name,)).fetchall()
    else:
        rows = c.execute(A.SEL_CO + " ORDER BY name").fetchall()
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
