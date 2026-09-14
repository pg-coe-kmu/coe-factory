# -*- coding: utf-8 -*-
"""
Migration: bc0.db (SQLite) -> PostgreSQL/Supabase (Schema v1.1)

Aufruf:
    python3 migrate_sqlite_to_pg.py                     # nutzt DATABASE_URL aus .env / Umgebung
    python3 migrate_sqlite_to_pg.py --only "NoroAI"     # nur Mandanten, deren Name "NoroAI" enthält
    python3 migrate_sqlite_to_pg.py --db pfad/bc0.db --dry-run

Eigenschaften:
  - Idempotent: deterministische UUIDs (uuid5) je Mandant, Upserts (ON CONFLICT) — mehrfach ausführbar.
  - Spielt Schema v1.1 (schema_v1.1.sql) automatisch ein, wenn die Ziel-DB leer ist.
  - Mapped App-Schema -> Schema v1.1: id->company_id (UUID), ma->mitarbeitende,
    quelle/kategorie/status -> ENUMs, profile_json -> JSONB.
  - Verifiziert am Ende: Zeilenzahlen + Gesamt-Reifegrad/Beleg-Quote (View v_reifegrad_company).
"""
import argparse, json, os, sqlite3, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))

def load_env():
    p = os.path.join(HERE, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "bc0-onboarding")
def company_uuid(sq_id, name):
    return str(uuid.uuid5(NAMESPACE, "company:%s:%s" % (sq_id, name or "")))

KATEGORIEN = ("Steuerungsprozess", "Kerngeschäftsprozess", "Unterstützungsprozess")
def kat(v):
    v = (v or "").strip()
    if v in KATEGORIEN: return v
    return {"Kerngeschaeftsprozess": "Kerngeschäftsprozess",
            "Unterstuetzungsprozess": "Unterstützungsprozess"}.get(v, "Unterstützungsprozess")

QUELLEN = ("chat", "doc", "xlsx", "interview", "manuell", "baseline", "yaml")
def quelle(v): return v if v in QUELLEN else "manuell"

STATI = ("neu", "laeuft", "abgeschlossen")
def status(v): return v if v in STATI else "neu"

def main():
    ap = argparse.ArgumentParser(description="bc0.db -> PostgreSQL (Schema v1.1)")
    ap.add_argument("--db", default=os.path.join(HERE, "bc0.db"), help="Pfad zur SQLite-DB (Default: bc0.db)")
    ap.add_argument("--url", default=None, help="PostgreSQL-URL (Default: DATABASE_URL aus .env/Umgebung)")
    ap.add_argument("--schema", default=os.path.join(HERE, "schema_v1.1.sql"), help="Schema-SQL (Default: schema_v1.1.sql)")
    ap.add_argument("--only", default=None, help="Nur Mandanten, deren Name diesen Teilstring enthält")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts schreiben")
    a = ap.parse_args()

    load_env()
    url = a.url or (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        sys.exit("FEHLER: keine DATABASE_URL (in .env eintragen oder --url angeben).")
    if not os.path.exists(a.db):
        sys.exit("FEHLER: SQLite-DB nicht gefunden: %s" % a.db)

    import psycopg2, psycopg2.extras
    sq = sqlite3.connect(a.db); sq.row_factory = sqlite3.Row
    pg = psycopg2.connect(url); cur = pg.cursor()

    # ---- Schema sicherstellen ----
    cur.execute("SELECT to_regclass('public.companies') IS NOT NULL")
    if not cur.fetchone()[0]:
        if not os.path.exists(a.schema):
            sys.exit("FEHLER: Ziel-DB leer und Schema-Datei fehlt: %s" % a.schema)
        sql = open(a.schema, encoding="utf-8").read()
        print("Ziel-DB leer -> spiele Schema v1.1 ein ...")
        if not a.dry_run:
            try:
                cur.execute(sql)
            except Exception:
                pg.rollback()  # pgcrypto ggf. nicht verfügbar; gen_random_uuid() ist ab PG13 eingebaut
                cur.execute(sql.replace('CREATE EXTENSION IF NOT EXISTS "pgcrypto";', ""))
            pg.commit()

    # ---- Mandanten wählen ----
    rows = [dict(r) for r in sq.execute("SELECT * FROM companies ORDER BY id")]
    if a.only:
        rows = [r for r in rows if a.only.lower() in (r["name"] or "").lower()]
    if not rows:
        sys.exit("Keine Mandanten gefunden%s." % (" (Filter: %s)" % a.only if a.only else ""))
    idmap = {r["id"]: company_uuid(r["id"], r["name"]) for r in rows}
    ids = tuple(idmap.keys())
    ph = ",".join("?" * len(ids))
    print("Mandanten: " + ", ".join("%s (id %s -> %s)" % (r["name"], r["id"], idmap[r["id"]][:8] + "…") for r in rows))
    if a.dry_run:
        for t in ("company_profile", "ref_prozesse", "ref_teilprozesse", "bitkom_bewertungen"):
            n = sq.execute("SELECT COUNT(*) FROM %s WHERE company_id IN (%s)" % (t, ph), ids).fetchone()[0]
            print("  %s: %d Zeilen würden migriert" % (t, n))
        print("Dry-Run beendet — nichts geschrieben."); return

    # ---- ref_items (statisch) ----
    items = [tuple(r) for r in sq.execute("SELECT item_nr,dimension,kriterium,frage FROM ref_items ORDER BY item_nr")]
    psycopg2.extras.execute_batch(cur,
        "INSERT INTO ref_items(item_nr,dimension,kriterium,frage) VALUES(%s,%s,%s,%s) ON CONFLICT (item_nr) DO NOTHING", items)

    # ---- companies ----
    for r in rows:
        cur.execute("""INSERT INTO companies(company_id,name,branche,rechtsform,mitarbeitende,region,status,created_at)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,COALESCE(%s::timestamptz, now()))
                       ON CONFLICT (company_id) DO UPDATE SET name=excluded.name, branche=excluded.branche,
                         rechtsform=excluded.rechtsform, mitarbeitende=excluded.mitarbeitende,
                         region=excluded.region, status=excluded.status""",
            (idmap[r["id"]], r["name"], r["branche"], r["rechtsform"], r["ma"], r["region"],
             status(r["status"]), r["created_at"]))

    # ---- company_profile ----
    n_prof = 0
    for r in sq.execute("SELECT * FROM company_profile WHERE company_id IN (%s)" % ph, ids):
        pj = None
        raw = r["profile_json"] if "profile_json" in r.keys() else None
        if raw:
            try: pj = json.dumps(json.loads(raw), ensure_ascii=False)
            except Exception: pj = None
        cur.execute("""INSERT INTO company_profile(company_id,geschaeftsmodell,tech_stack,profile_json)
                       VALUES(%s,%s,%s,%s::jsonb)
                       ON CONFLICT (company_id) DO UPDATE SET geschaeftsmodell=excluded.geschaeftsmodell,
                         tech_stack=excluded.tech_stack, profile_json=excluded.profile_json""",
            (idmap[r["company_id"]], r["geschaeftsmodell"], r["tech_stack"], pj))
        n_prof += 1

    # ---- ref_prozesse ----
    n_kp = 0
    for r in sq.execute("SELECT * FROM ref_prozesse WHERE company_id IN (%s)" % ph, ids):
        cur.execute("""INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie,owner_name,owner_role,trigger_text,input_text,output_text)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (company_id,process_id) DO UPDATE SET process_name=excluded.process_name,
                         kategorie=excluded.kategorie, owner_name=excluded.owner_name, owner_role=excluded.owner_role,
                         trigger_text=excluded.trigger_text, input_text=excluded.input_text, output_text=excluded.output_text""",
            (idmap[r["company_id"]], r["process_id"], r["process_name"], kat(r["kategorie"]),
             r["owner_name"], r["owner_role"], r["trigger_text"], r["input_text"], r["output_text"]))
        n_kp += 1

    # ---- ref_teilprozesse ----
    n_tp = 0
    for r in sq.execute("SELECT * FROM ref_teilprozesse WHERE company_id IN (%s)" % ph, ids):
        cur.execute("""INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation,tools,medienbrueche,schnittstellen,api)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (company_id,sub_process_id) DO UPDATE SET sub_process_name=excluded.sub_process_name,
                         notation=excluded.notation, tools=excluded.tools, medienbrueche=excluded.medienbrueche,
                         schnittstellen=excluded.schnittstellen, api=excluded.api""",
            (idmap[r["company_id"]], r["sub_process_id"], r["process_id"], r["step_no"],
             r["sub_process_name"] or ("Teilprozess %s" % r["step_no"]), r["notation"],
             r["tools"], r["medienbrueche"], r["schnittstellen"], r["api"]))
        n_tp += 1

    # ---- bitkom_bewertungen (Beleg-Pflicht: leerer Beleg -> Platzhalter) ----
    n_bew = 0
    for r in sq.execute("SELECT * FROM bitkom_bewertungen WHERE company_id IN (%s)" % ph, ids):
        beleg = (r["beleg"] or "").strip() or "(migriert ohne Beleg)"
        cur.execute("""INSERT INTO bitkom_bewertungen(company_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,COALESCE(%s::timestamptz, now()))
                       ON CONFLICT (company_id,id) DO UPDATE SET stufe=excluded.stufe, beleg=excluded.beleg,
                         quelle=excluded.quelle, bewertet_am=excluded.bewertet_am""",
            (idmap[r["company_id"]], r["id"], r["sub_process_id"], r["item_nr"], r["stufe"],
             beleg, quelle(r["quelle"]), r["bewertet_am"]))
        n_bew += 1

    pg.commit()
    print("Migriert: %d Mandanten, %d Profile, %d KPs, %d TPs, %d Bewertungen." % (len(rows), n_prof, n_kp, n_tp, n_bew))

    # ---- Verifikation ----
    print("\nVerifikation (Ziel-DB):")
    for t in ("companies", "company_profile", "ref_prozesse", "ref_teilprozesse", "bitkom_bewertungen"):
        cur.execute("SELECT COUNT(*) FROM " + t)
        print("  %-20s %6d Zeilen" % (t, cur.fetchone()[0]))
    cur.execute("SELECT name, gesamt_reifegrad, n_bewertungen, beleg_quote_pct FROM v_reifegrad_company ORDER BY name")
    for name, g, n, q in cur.fetchall():
        print("  %-30s Reifegrad %s · %s Bewertungen · Beleg-Quote %s%%" % (name, g, n, q))
    sq.close(); pg.close()

if __name__ == "__main__":
    main()
