# -*- coding: utf-8 -*-
"""
Seed: NoroAI aus der BC0-Baseline in die App-DB (SQLite) einspielen.

Liest die echten Baseline-JSONs (10 Kernprozesse, 20 Teilprozesse, 600 Bitkom-Bewertungen,
Unternehmensprofil) und legt daraus den Mandanten "NoroAI Consulting GmbH" an.
IDs werden auf das App-Format normalisiert (KP-XX.TP-{step} / ...I-WW), Kommentare = Belege.

Aufruf (im Ordner BC0_App):
    python seed_noroai.py
Optional anderer Baseline-Pfad:
    python seed_noroai.py "..\\06_Mockdata_BC1_to_BC2\\baseline_json"
"""
import os, sys, json
import app as A   # nutzt dieselbe DB (BC0_DB) + Schema wie die App

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "06_Mockdata_BC1_to_BC2", "baseline_json")

def load(name):
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        sys.exit("Baseline-Datei nicht gefunden: %s\nBitte Pfad als Argument angeben." % p)
    return json.load(open(p, encoding="utf-8"))

def split_owner(s):
    s = (s or "").strip()
    if s.endswith(")") and "(" in s:
        name = s[:s.rfind("(")].strip()
        role = s[s.rfind("(")+1:-1].strip()
        return name, role
    return s, ""

def main():
    rp = load("ref_prozesse.json").get("prozesse", [])
    tp = load("ref_teilprozesse.json").get("teilprozesse", [])
    bw = load("bitkom_bewertungen.json").get("bewertungen", [])
    try:
        prof = load("noroai_profile.json")
    except SystemExit:
        prof = {}
    # v6-Profil (falls vorhanden) -> volles Unternehmensprofil für Reiter "Unternehmensdaten"
    try:
        prof_v6 = load("noroai_profile_v6.json")
    except SystemExit:
        prof_v6 = None
    full_profile = prof_v6 if prof_v6 else prof

    # baseline sub_process_id (TP-01-1) -> (process_id, step_no)
    tpmap = {t["sub_process_id"]: (t["process_id"], t["step_no"]) for t in tp}

    c = A.db()
    # vorhandenen NoroAI-Mandanten entfernen (idempotent)
    old = c.execute("SELECT id FROM companies WHERE name=?", ("NoroAI Consulting GmbH",)).fetchall()
    for r in old:
        c.execute("DELETE FROM companies WHERE id=?", (r["id"],))
    c.commit()

    company = prof.get("company", {}) if isinstance(prof, dict) else {}
    pos = prof.get("positionierung", {}) if isinstance(prof, dict) else {}
    techn = prof.get("tech_stack", {}) if isinstance(prof, dict) else {}
    name = company.get("name", "NoroAI Consulting GmbH")
    region = company.get("region") or company.get("sitz_haupt") or "Hagen"
    team = prof.get("team_und_kultur", {}) if isinstance(prof, dict) else {}
    ma = team.get("anzahl_personen") or 10

    cur = c.execute("INSERT INTO companies(name,branche,rechtsform,ma,region,status,created_at) VALUES(?,?,?,?,?,?,?)",
        (name, "KI-Beratung", company.get("rechtsform", "GmbH"), ma, region, "laeuft", A.now()))
    cid = cur.lastrowid
    gm = pos.get("geschaeftsmodell") or "KI-Beratung mit eigenem, EU-/Open-Source-basiertem Tech-Stack."
    ts = "%s Tools" % (techn.get("anzahl_tools", "")) if techn.get("anzahl_tools") else "EU/Open-Source-Stack"
    c.execute("INSERT INTO company_profile(company_id,geschaeftsmodell,tech_stack,profile_json) VALUES(?,?,?,?)", (cid, gm, ts, json.dumps(full_profile, ensure_ascii=False)))

    # Kernprozesse (alle 10)
    for p in rp:
        on, ro = split_owner(p.get("process_owner"))
        c.execute("""INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie,owner_name,owner_role,trigger_text,input_text,output_text)
                     VALUES(?,?,?,?,?,?,?,?,?)""",
            (cid, p["process_id"], p["process_name"], p.get("kategorie", ""), on, ro, p.get("trigger", ""), "", ""))

    # Teilprozesse: echte (KP01-04) normalisiert + generische für KP05-10
    evaluated = set()
    for t in tp:
        pid = t["process_id"]; step = t["step_no"]; sid = "%s.TP-%d" % (pid, step)
        evaluated.add(pid)
        c.execute("""INSERT OR REPLACE INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation)
                     VALUES(?,?,?,?,?,?)""", (cid, sid, pid, step, t["sub_process_name"], t.get("notation", "")))
    for p in rp:
        pid = p["process_id"]
        if pid in evaluated:
            continue
        for step in range(1, 6):
            c.execute("""INSERT OR IGNORE INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation)
                         VALUES(?,?,?,?,?,?)""", (cid, "%s.TP-%d" % (pid, step), pid, step, "Teilprozess %d" % step, ""))

    # Bewertungen (600) -> normalisierte IDs, Kommentar = Beleg
    n = 0
    tpfields = {}   # app_sid -> {item_nr: kommentar} für abgeleitete TP-Felder
    for b in bw:
        base_sid = b["sub_process_id"]
        if base_sid not in tpmap:
            continue
        pid, step = tpmap[base_sid]
        app_sid = "%s.TP-%d" % (pid, step)
        item = int(b["item_nr"])
        rid = "%s.I-%02d" % (app_sid, item)
        kom = (b.get("kommentar") or "").strip()
        beleg = kom or "Aus BC0-Baseline übernommen"
        if kom:
            tpfields.setdefault(app_sid, {})[item] = kom
        c.execute("""INSERT OR REPLACE INTO bitkom_bewertungen(company_id,id,sub_process_id,process_id,item_nr,stufe,beleg,quelle,bewertet_am)
                     VALUES(?,?,?,?,?,?,?,?,?)""",
            (cid, rid, app_sid, pid, item, int(b["stufe"]), beleg, "baseline", A.now()))
        n += 1

    # Abgeleitete Teilprozess-Felder aus Belegen:
    #   Tools <- Item 3/4 · Medienbrüche <- Item 6 · API bleibt leer
    #   Schnittstellen = konkrete Tool-Verbindungen (Item 5, falls Pfeil) + Prozess-Übergaben aus der Notation
    notmap = {"%s.TP-%d" % (t["process_id"], t["step_no"]): (t.get("notation") or "") for t in tp}
    for sid, it in tpfields.items():
        tools = " · ".join(dict.fromkeys([it[i] for i in (3, 4) if it.get(i)]))
        b5 = it.get(5, "") or ""
        parts = []
        if any(s in b5 for s in ("↔", "→", "->", "<->")):   # nur wenn konkrete Verbindung benannt
            parts.append(b5)
        for seg in notmap.get(sid, "").split("→"):           # Prozess-Übergaben aus der Notation
            seg = seg.strip()
            if "KP-" in seg:
                parts.append(seg)
        schnitt = " · ".join(dict.fromkeys([p for p in parts if p])) or (b5 or None)
        medien = it.get(6, "")
        c.execute("UPDATE ref_teilprozesse SET tools=?,schnittstellen=?,medienbrueche=? WHERE company_id=? AND sub_process_id=?",
            (tools or None, schnitt or None, medien or None, cid, sid))

    c.commit()
    # kleine Bilanz
    avg = c.execute("SELECT ROUND(AVG(stufe),2) a FROM bitkom_bewertungen WHERE company_id=?", (cid,)).fetchone()["a"]
    c.close()
    print("OK: NoroAI angelegt (company_id=%d)" % cid)
    print("   Kernprozesse: %d | Bewertungen: %d | Gesamt-Ø Reifegrad: %s" % (len(rp), n, avg))
    print("   -> Server neu starten (oder Seite neu laden) und Mandant 'NoroAI Consulting GmbH' öffnen.")

if __name__ == "__main__":
    main()
