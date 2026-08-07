# -*- coding: utf-8 -*-
"""
BC0 Onboarding-App — FastAPI · SQLite (lokal) ODER PostgreSQL/Supabase (DATABASE_URL) · Stand 10.07.2026

Backend-Wahl:
  - Env-Variable DATABASE_URL gesetzt -> PostgreSQL, Schema v1.1 (verbindliche Projekt-Vorgabe)
  - sonst                             -> SQLite (bc0.db wie bisher; Pfad per BC0_DB überschreibbar)

Eine .env neben app.py wird automatisch geladen (DATABASE_URL=postgresql://...).

Start:  pip install -r requirements.txt
        uvicorn app:app --reload --port 8000
        Browser: http://localhost:8000
"""
import sqlite3, os, datetime, json, uuid, re, urllib.request, urllib.error

HERE = os.path.dirname(__file__)

def _load_env():
    p = os.path.join(HERE, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
_load_env()

DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
PG = bool(DATABASE_URL)
if PG:
    import psycopg2, psycopg2.extras

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

DB = os.environ.get("BC0_DB", os.path.join(HERE, "bc0.db"))
SCHEMA_SQL = os.path.join(HERE, "schema_v1.1.sql")

# ---- Beleg-Dokumente: Storage (Stufe 1) ----
# Default: lokales Verzeichnis ./belege — optional Supabase Storage (EU), wenn
# SUPABASE_URL + SUPABASE_SERVICE_KEY gesetzt sind (Bucket: SUPABASE_BUCKET, Default 'belege').
BELEGE_DIR = os.environ.get("BELEGE_DIR", os.path.join(HERE, "belege"))
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = (os.environ.get("SUPABASE_SERVICE_KEY") or "").strip()
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "belege")
SB_STORAGE = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)
MAX_DOC_MB = int(os.environ.get("MAX_DOC_MB", "15"))
REF_RE = re.compile(r"^KP-\d{2}(\.TP-\d+)?$")

def _sb(method, path, data=None, ctype=None, extra=None):
    req = urllib.request.Request(SUPABASE_URL + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + SUPABASE_SERVICE_KEY)
    req.add_header("apikey", SUPABASE_SERVICE_KEY)
    if ctype: req.add_header("Content-Type", ctype)
    for k, v in (extra or {}).items(): req.add_header(k, v)
    return urllib.request.urlopen(req, timeout=30)

def _sb_ensure_bucket():
    body = json.dumps({"id": SUPABASE_BUCKET, "name": SUPABASE_BUCKET, "public": False}).encode()
    try: _sb("POST", "/storage/v1/bucket", body, "application/json")
    except urllib.error.HTTPError: pass  # existiert bereits

def store_file(key, data, mime):
    if SB_STORAGE:
        p = "/storage/v1/object/%s/%s" % (SUPABASE_BUCKET, key)
        try:
            _sb("POST", p, data, mime or "application/octet-stream", {"x-upsert": "true"})
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                _sb_ensure_bucket()
                _sb("POST", p, data, mime or "application/octet-stream", {"x-upsert": "true"})
            else: raise
        return
    path = os.path.join(BELEGE_DIR, *key.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f: f.write(data)

def load_file(key):
    if SB_STORAGE:
        return _sb("GET", "/storage/v1/object/%s/%s" % (SUPABASE_BUCKET, key)).read()
    path = os.path.join(BELEGE_DIR, *key.split("/"))
    if not os.path.exists(path): raise FileNotFoundError(key)
    return open(path, "rb").read()

def delete_file(key):
    try:
        if SB_STORAGE:
            _sb("DELETE", "/storage/v1/object/%s/%s" % (SUPABASE_BUCKET, key))
        else:
            os.remove(os.path.join(BELEGE_DIR, *key.split("/")))
    except Exception:
        pass  # Datei weg = Ziel erreicht

DOC_DDL_PG = """
DO $$ BEGIN
  CREATE TYPE doc_status AS ENUM ('hochgeladen','ocr_fertig','vorgeschlagen','bestaetigt','verworfen');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE TABLE IF NOT EXISTS beleg_dokumente (
  doc_id UUID PRIMARY KEY,
  company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  ref_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  mime_type TEXT,
  seiten INTEGER,
  ocr_text TEXT,
  ocr_confidence NUMERIC(4,3),
  extrakt JSONB,
  status doc_status NOT NULL DEFAULT 'hochgeladen',
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_belegdoc_company_ref ON beleg_dokumente(company_id, ref_id);
CREATE TABLE IF NOT EXISTS bewertung_belege (
  company_id UUID NOT NULL,
  bewertung_id VARCHAR(28) NOT NULL,
  doc_id UUID NOT NULL REFERENCES beleg_dokumente(doc_id) ON DELETE CASCADE,
  zitat TEXT, seite INTEGER,
  PRIMARY KEY (company_id, bewertung_id, doc_id),
  FOREIGN KEY (company_id, bewertung_id) REFERENCES bitkom_bewertungen(company_id, id) ON DELETE CASCADE
);
"""
DOC_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS beleg_dokumente(
  doc_id TEXT PRIMARY KEY, company_id INTEGER NOT NULL, ref_id TEXT NOT NULL,
  filename TEXT NOT NULL, storage_key TEXT NOT NULL, mime_type TEXT, seiten INTEGER,
  ocr_text TEXT, ocr_confidence REAL, extrakt TEXT,
  status TEXT NOT NULL DEFAULT 'hochgeladen', uploaded_at TEXT,
  FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS idx_belegdoc_company_ref ON beleg_dokumente(company_id, ref_id);
CREATE TABLE IF NOT EXISTS bewertung_belege(
  company_id INTEGER NOT NULL, bewertung_id TEXT NOT NULL, doc_id TEXT NOT NULL,
  zitat TEXT, seite INTEGER,
  PRIMARY KEY(company_id,bewertung_id,doc_id));
"""

# ---- 30 Bitkom-Items (statisch) ----
ITEMS = [
 (1,"1) Technologie","Technologiebasis","Inwieweit sind alle eingehenden Informationen für den Prozess vollständig digital verfügbar?"),
 (2,"1) Technologie","Technologiebasis","Inwieweit sind alle ausgehenden Informationen für den Prozess vollständig digital verfügbar?"),
 (3,"1) Technologie","Tools im Prozess","Wie stark wird eine Software-Lösung zur Modellierung und Unterstützung des Prozesses eingesetzt?"),
 (4,"1) Technologie","Tools im Prozess","Wie vollständig ist der Geschäftsprozess durch eine Software-Lösung automatisiert?"),
 (5,"1) Technologie","Systemintegration","In welchem Maß sind die im Prozess verwendeten Software-Lösungen integriert?"),
 (6,"1) Technologie","Systemintegration","Inwieweit läuft der Prozess ohne unnötige Medienbrüche ab?"),
 (7,"2) Prozessdaten","Datenerhebung","In welchem Umfang werden Prozessdurchläufe (z. B. Logdaten) digital erhoben?"),
 (8,"2) Prozessdaten","Datenerhebung","Wie vollständig werden Prozessdurchläufe automatisch erhoben?"),
 (9,"2) Prozessdaten","Datenbereitstellung","Wie vollständig werden Daten für das Berichtswesen bereitgestellt?"),
 (10,"2) Prozessdaten","Datenbereitstellung","Inwieweit ist die Darstellung von Daten einfach und nutzbar?"),
 (11,"2) Prozessdaten","Datenverwendung","In welchem Maß können Daten durch eine Schnittstelle für die weitere Verwendung abgerufen werden?"),
 (12,"2) Prozessdaten","Datenverwendung","Inwieweit werden Daten als Grundlage zur Verbesserung des Prozesses verwendet?"),
 (13,"3) Prozessqualität","Beschreibung","In welchem Umfang ist der aktuelle Prozess mithilfe von Standards beschrieben?"),
 (14,"3) Prozessqualität","Beschreibung","Wie detailliert ist der Prozess mithilfe von Standards beschrieben?"),
 (15,"3) Prozessqualität","Ausführung","In welchem Maße ist der Status des Prozesses jederzeit einsehbar?"),
 (16,"3) Prozessqualität","Ausführung","Wie stabil sind die Prozessdurchläufe auch bei Lastspitzen?"),
 (17,"3) Prozessqualität","Compliance","Inwieweit beinhaltet der Prozess wirksame Kontrollen und Prüfinstanzen?"),
 (18,"3) Prozessqualität","Compliance","In welchem Maß erfüllt der Prozess die regulatorischen Anforderungen?"),
 (19,"4) Kundinnen und Kunden","Zentrierung","Inwieweit berücksichtigt der Prozess die kontinuierliche Dokumentation der Kund:innen-Bedürfnisse?"),
 (20,"4) Kundinnen und Kunden","Zentrierung","Inwieweit sieht der Prozess zugeschnittene Produkt- bzw. Service-Angebote vor?"),
 (21,"4) Kundinnen und Kunden","Nutzen","In welchem Maß ist der Status des Prozesses jederzeit von Kund:innen einsehbar?"),
 (22,"4) Kundinnen und Kunden","Nutzen","Wie gut erkennen die Kund:innen den Nutzen des Prozesses?"),
 (23,"4) Kundinnen und Kunden","Partizipation","Wie stark sieht der Prozess verbindliche Beteiligungsformate vor?"),
 (24,"4) Kundinnen und Kunden","Partizipation","In welchem Umfang werden wirksame Maßnahmen umgesetzt?"),
 (25,"5) Skills und Kultur","Digital Skills","In welchem Maße verfügen die Mitarbeitenden über digitale Kompetenzen?"),
 (26,"5) Skills und Kultur","Digital Skills","Inwieweit steht digitale Kompetenz zur Verfügung?"),
 (27,"5) Skills und Kultur","Digital Leadership","In welchem Maße denken die Führungskräfte digital?"),
 (28,"5) Skills und Kultur","Digital Leadership","Wie stark werden Anreize für digitales Denken geschaffen?"),
 (29,"5) Skills und Kultur","Digital Mindset","In welchem Umfang wirken die Mitarbeitenden in einer digitalen Kultur?"),
 (30,"5) Skills und Kultur","Digital Mindset","Wie konsequent werden digitale Ansätze in der Organisation verwendet?"),
]
DIMS = ["1) Technologie","2) Prozessdaten","3) Prozessqualität","4) Kundinnen und Kunden","5) Skills und Kultur"]
KP_TEMPLATE = ["Strategieprozess","Vertrieb & Lead-Management","Kunden-Onboarding","Engagement-/Auftragssteuerung",
 "Wissensmanagement","HR / Personal","Buchhaltung","IT-Operations","Qualitätssicherung","Compliance & Datenschutz"]
PA_CRIT = [("Technologiebasis",[1,2]),("Tools im Prozess",[3,4]),("Systemintegration",[5,6]),
           ("Prozessbeschreibung",[13,14]),("Ausführung",[15,16]),("Compliance",[17,18])]
CF_CRIT = [("Technologiebasis",[1,2]),("Tools im Prozess",[3,4]),("Systemintegration",[5,6]),
           ("Prozessbeschreibung",[7,8]),("Ausführung",[9,10]),("Compliance",[11,12])]
def _build_krit15():
    seen=[]; m={}
    for nr,dim,krit,frage in ITEMS:
        if krit not in m: m[krit]=[]; seen.append(krit)
        m[krit].append(nr)
    return [(k,m[k]) for k in seen]
KRIT15 = _build_krit15()
ITEMS12 = [1,2,3,4,5,6,13,14,15,16,17,18]
KATEGORIEN = ("Steuerungsprozess","Kerngeschäftsprozess","Unterstützungsprozess")

def kpid(i): return "KP-%02d" % (i+1)
def now(): return datetime.datetime.utcnow().isoformat()

def _kat(v, default="Unterstützungsprozess"):
    """Kategorie auf kanonische ENUM-Werte (mit Umlaut, Schema v1.1 [3]) normalisieren."""
    v = (v or "").strip()
    if v in KATEGORIEN: return v
    m = {"Kerngeschaeftsprozess":"Kerngeschäftsprozess","Unterstuetzungsprozess":"Unterstützungsprozess"}
    return m.get(v, default)

# ---------------- DB-Layer (SQLite / PostgreSQL) ----------------
class _Cx:
    """Einheitliche Schnittstelle: execute(sql, params) mit '?'-Platzhaltern, Rows als Mapping."""
    def __init__(self):
        if PG:
            self.c = psycopg2.connect(DATABASE_URL)
        else:
            self.c = sqlite3.connect(DB)
            self.c.row_factory = sqlite3.Row
            self.c.execute("PRAGMA foreign_keys=ON")
    def execute(self, sql, params=()):
        if PG:
            cur = self.c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql.replace("?", "%s"), params)
            return cur
        return self.c.execute(sql, params)
    def executemany(self, sql, seq):
        if PG:
            cur = self.c.cursor()
            cur.executemany(sql.replace("?", "%s"), seq)
            return cur
        return self.c.executemany(sql, seq)
    def commit(self): self.c.commit()
    def close(self): self.c.close()

def db(): return _Cx()

# Mode-spezifische SELECTs/WHEREs (PG: Schema v1.1 mit UUID/ENUM -> auf App-Sicht aliasen)
if PG:
    SEL_CO   = ("SELECT company_id::text AS id,name,branche,rechtsform,mitarbeitende AS ma,region,"
                "status::text AS status,created_at::text AS created_at FROM companies")
    KEY_CO   = "company_id::text=?"   # companies
    W_CO     = "company_id::text=?"   # Fachtabellen
    SEL_PROF = ("SELECT company_id::text AS company_id,geschaeftsmodell,tech_stack,"
                "profile_json::text AS profile_json FROM company_profile")
    SEL_PROC = ("SELECT company_id::text AS company_id,process_id,process_name,kategorie::text AS kategorie,"
                "owner_name,owner_role,trigger_text,input_text,output_text FROM ref_prozesse")
    SEL_TP   = ("SELECT company_id::text AS company_id,sub_process_id,process_id,step_no,sub_process_name,"
                "notation,tools,medienbrueche,schnittstellen,api FROM ref_teilprozesse")
    SEL_BEW  = ("SELECT company_id::text AS company_id,id,sub_process_id,left(sub_process_id,5) AS process_id,"
                "item_nr,stufe,beleg,quelle::text AS quelle,bewertet_am::text AS bewertet_am FROM bitkom_bewertungen")
    SEL_DOC  = ("SELECT doc_id::text AS doc_id,company_id::text AS company_id,ref_id,filename,storage_key,"
                "mime_type,seiten,ocr_confidence,status::text AS status,uploaded_at::text AS uploaded_at FROM beleg_dokumente")
else:
    SEL_CO   = "SELECT * FROM companies";        KEY_CO = "id=?";        W_CO = "company_id=?"
    SEL_PROF = "SELECT * FROM company_profile"
    SEL_PROC = "SELECT * FROM ref_prozesse"
    SEL_TP   = "SELECT * FROM ref_teilprozesse"
    SEL_BEW  = "SELECT * FROM bitkom_bewertungen"
    SEL_DOC  = ("SELECT doc_id,company_id,ref_id,filename,storage_key,mime_type,seiten,"
                "ocr_confidence,status,uploaded_at FROM beleg_dokumente")

def init_db():
    c = db()
    if PG:
        ok = c.execute("SELECT to_regclass('public.companies') IS NOT NULL AS ok").fetchone()["ok"]
        if not ok:
            # Schema v1.1 automatisch einspielen (liegt als schema_v1.1.sql bei)
            if not os.path.exists(SCHEMA_SQL):
                raise RuntimeError("Ziel-DB leer und schema_v1.1.sql fehlt — Schema v1.1 zuerst einspielen (siehe MIGRATION.md).")
            sql = open(SCHEMA_SQL, encoding="utf-8").read()
            try:
                c.execute(sql)
            except Exception:
                c.c.rollback()
                # Fallback: pgcrypto ggf. nicht verfügbar; gen_random_uuid() ist ab PG13 eingebaut
                c.execute(sql.replace('CREATE EXTENSION IF NOT EXISTS "pgcrypto";', ""))
        c.executemany("INSERT INTO ref_items(item_nr,dimension,kriterium,frage) VALUES(?,?,?,?) ON CONFLICT (item_nr) DO NOTHING", ITEMS)
        c.execute(DOC_DDL_PG)
        c.commit(); c.close(); return
    c.c.executescript("""
    CREATE TABLE IF NOT EXISTS companies(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, branche TEXT, rechtsform TEXT,
      ma INTEGER, region TEXT, status TEXT DEFAULT 'neu', created_at TEXT);
    CREATE TABLE IF NOT EXISTS company_profile(
      company_id INTEGER PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
      geschaeftsmodell TEXT, tech_stack TEXT);
    CREATE TABLE IF NOT EXISTS ref_items(item_nr INTEGER PRIMARY KEY, dimension TEXT, kriterium TEXT, frage TEXT);
    CREATE TABLE IF NOT EXISTS ref_prozesse(
      company_id INTEGER, process_id TEXT, process_name TEXT, kategorie TEXT,
      owner_name TEXT, owner_role TEXT, trigger_text TEXT, input_text TEXT, output_text TEXT,
      PRIMARY KEY(company_id,process_id),
      FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS ref_teilprozesse(
      company_id INTEGER, sub_process_id TEXT, process_id TEXT, step_no INTEGER,
      sub_process_name TEXT, notation TEXT,
      tools TEXT, medienbrueche TEXT, schnittstellen TEXT, api TEXT,
      PRIMARY KEY(company_id,sub_process_id),
      FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS bitkom_bewertungen(
      company_id INTEGER, id TEXT, sub_process_id TEXT, process_id TEXT, item_nr INTEGER,
      stufe INTEGER CHECK(stufe BETWEEN 1 AND 5), beleg TEXT NOT NULL, quelle TEXT DEFAULT 'manuell',
      bewertet_am TEXT,
      PRIMARY KEY(company_id,id),
      FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE);
    """)
    if not c.execute("SELECT COUNT(*) n FROM ref_items").fetchone()["n"]:
        c.executemany("INSERT INTO ref_items VALUES(?,?,?,?)", ITEMS)
    try: c.execute("ALTER TABLE company_profile ADD COLUMN profile_json TEXT")
    except Exception: pass
    for col in ("tools", "medienbrueche", "schnittstellen", "api"):
        try: c.execute("ALTER TABLE ref_teilprozesse ADD COLUMN %s TEXT" % col)
        except Exception: pass
    c.c.executescript(DOC_DDL_SQLITE)
    c.commit(); c.close()

app = FastAPI(title="BC0 Onboarding")
init_db()

# ---------------- API ----------------
@app.get("/api/meta")
def meta():
    c=db(); items=[dict(r) for r in c.execute("SELECT * FROM ref_items ORDER BY item_nr").fetchall()]; c.close()
    return {"items":items,"dims":DIMS,"kp_template":KP_TEMPLATE,
            "pa_crit":PA_CRIT,"cf_crit":CF_CRIT,
            "backend":"postgres" if PG else "sqlite"}

def company_progress(c, cid):
    kps=c.execute("SELECT COUNT(*) n FROM ref_prozesse WHERE "+W_CO, (cid,)).fetchone()["n"]
    total=kps*5*30
    rated=c.execute("SELECT COUNT(*) n FROM bitkom_bewertungen WHERE "+W_CO, (cid,)).fetchone()["n"]
    avg=c.execute("SELECT AVG(stufe) a FROM bitkom_bewertungen WHERE "+W_CO, (cid,)).fetchone()["a"]
    return (round(rated/total*100) if total else 0, round(float(avg),2) if avg else 0, kps)

@app.get("/api/companies")
def companies():
    c=db(); out=[]
    order = " ORDER BY created_at DESC" if PG else " ORDER BY id DESC"
    for r in c.execute(SEL_CO+order).fetchall():
        p,a,kps=company_progress(c,r["id"])
        d=dict(r); d.update(progress=p, avg=a, kp_count=kps); out.append(d)
    c.close(); return out

@app.post("/api/companies")
async def create_company(req: Request):
    b=await req.json(); c=db()
    name=b.get("name","").strip() or "Unbenannt"
    if PG:
        cid=c.execute("INSERT INTO companies(name,branche,rechtsform,mitarbeitende,region,status) VALUES(?,?,?,?,?,?) RETURNING company_id::text AS id",
            (name, b.get("branche"), b.get("rechtsform"), b.get("ma") or None, b.get("region"), "laeuft")).fetchone()["id"]
    else:
        cur=c.execute("INSERT INTO companies(name,branche,rechtsform,ma,region,status,created_at) VALUES(?,?,?,?,?,?,?)",
            (name, b.get("branche"), b.get("rechtsform"), b.get("ma") or None, b.get("region"), "laeuft", now()))
        cid=cur.lastrowid
    c.execute("INSERT INTO company_profile(company_id,geschaeftsmodell,tech_stack) VALUES(?,?,?)",(cid,"",""))
    for i in b.get("kps",[]):
        c.execute("INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie) VALUES(?,?,?,?)",
            (cid,kpid(i),KP_TEMPLATE[i],"Steuerungsprozess" if i==0 else ("Kerngeschäftsprozess" if i<4 else "Unterstützungsprozess")))
        for n in range(1,6):
            c.execute("INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation) VALUES(?,?,?,?,?,?)",
                (cid,"%s.TP-%d"%(kpid(i),n),kpid(i),n,"Teilprozess %d"%n,""))
    c.commit(); c.close(); return {"id":cid}

@app.get("/api/companies/{cid}")
def get_company(cid:str):
    c=db(); co=c.execute(SEL_CO+" WHERE "+KEY_CO, (cid,)).fetchone()
    if not co: c.close(); raise HTTPException(404,"unbekannt")
    prof=c.execute(SEL_PROF+" WHERE "+W_CO, (cid,)).fetchone()
    procs={}
    for r in c.execute(SEL_PROC+" WHERE "+W_CO+" ORDER BY process_id", (cid,)).fetchall():
        d=dict(r); d["tps"]=[]; procs[r["process_id"]]=d
    for r in c.execute(SEL_TP+" WHERE "+W_CO+" ORDER BY process_id,step_no", (cid,)).fetchall():
        if r["process_id"] in procs: procs[r["process_id"]]["tps"].append(dict(r))
    ratings={}
    for r in c.execute(SEL_BEW+" WHERE "+W_CO, (cid,)).fetchall():
        ratings.setdefault(r["sub_process_id"],{})[r["item_nr"]]={"stufe":r["stufe"],"beleg":r["beleg"],"quelle":r["quelle"]}
    c.close()
    return {"company":dict(co),"profile":dict(prof) if prof else {},"processes":procs,"ratings":ratings}

@app.put("/api/companies/{cid}/profile")
async def save_profile(cid:str, req:Request):
    b=await req.json(); c=db()
    if PG:
        c.execute("UPDATE companies SET name=COALESCE(?,name),branche=?,rechtsform=?,mitarbeitende=?,region=? WHERE "+KEY_CO,
            (b.get("name"),b.get("branche"),b.get("rechtsform"),b.get("ma") or None,b.get("region"),cid))
    else:
        c.execute("UPDATE companies SET name=COALESCE(?,name),branche=?,rechtsform=?,ma=?,region=? WHERE id=?",
            (b.get("name"),b.get("branche"),b.get("rechtsform"),b.get("ma") or None,b.get("region"),cid))
    c.execute("UPDATE company_profile SET geschaeftsmodell=?,tech_stack=? WHERE "+W_CO,
        (b.get("geschaeftsmodell"),b.get("tech_stack"),cid))
    c.commit(); c.close(); return {"ok":True}

@app.put("/api/companies/{cid}/process")
async def save_process(cid:str, req:Request):
    b=await req.json(); pid=b["process_id"]; c=db()
    kat=_kat(b.get("kategorie")) if PG else b.get("kategorie")
    c.execute("""UPDATE ref_prozesse SET owner_name=?,owner_role=?,kategorie=?,trigger_text=?,input_text=?,output_text=?
                 WHERE """+W_CO+" AND process_id=?",
        (b.get("owner_name"),b.get("owner_role"),kat,b.get("trigger_text"),
         b.get("input_text"),b.get("output_text"),cid,pid))
    for n,tp in enumerate(b.get("tps",[]),start=1):
        c.execute("""UPDATE ref_teilprozesse SET sub_process_name=?,notation=?,tools=?,medienbrueche=?,schnittstellen=?,api=?
                     WHERE """+W_CO+" AND sub_process_id=?",
            (tp.get("name"),tp.get("notation"),tp.get("tools"),tp.get("medienbrueche"),
             tp.get("schnittstellen"),tp.get("api"),cid,"%s.TP-%d"%(pid,n)))
    c.commit(); c.close(); return {"ok":True}

@app.post("/api/companies/{cid}/process/add")
async def add_process(cid:str, req:Request):
    b=await req.json(); i=int(b["kp_index"]); pid=kpid(i); c=db()
    c.execute("INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie) VALUES(?,?,?,?) ON CONFLICT(company_id,process_id) DO NOTHING",
        (cid,pid,KP_TEMPLATE[i],"Steuerungsprozess" if i==0 else ("Kerngeschäftsprozess" if i<4 else "Unterstützungsprozess")))
    for n in range(1,6):
        c.execute("INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation) VALUES(?,?,?,?,?,?) ON CONFLICT(company_id,sub_process_id) DO NOTHING",
            (cid,"%s.TP-%d"%(pid,n),pid,n,"Teilprozess %d"%n,""))
    c.commit(); c.close(); return {"ok":True,"process_id":pid}

@app.post("/api/companies/{cid}/rating")
async def save_rating(cid:str, req:Request):
    b=await req.json(); key=b["key"]; items=b.get("items",{})
    missing=[k for k,v in items.items() if v.get("stufe") and not (v.get("beleg") or "").strip()]
    if missing:
        raise HTTPException(400, "Beleg fehlt für Item(s): "+", ".join(missing))
    pid=key.split(".")[0]; c=db()
    for nr,v in items.items():
        if not v.get("stufe"): continue
        rid="%s.I-%02d"%(key,int(nr))
        if PG:
            c.execute("""INSERT INTO bitkom_bewertungen(company_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am)
                         VALUES(?,?,?,?,?,?,?,?)
                         ON CONFLICT(company_id,id) DO UPDATE SET stufe=excluded.stufe,beleg=excluded.beleg,quelle=excluded.quelle,bewertet_am=excluded.bewertet_am""",
                (cid,rid,key,int(nr),int(v["stufe"]),v.get("beleg","").strip(),v.get("quelle","manuell"),now()))
        else:
            c.execute("""INSERT INTO bitkom_bewertungen(company_id,id,sub_process_id,process_id,item_nr,stufe,beleg,quelle,bewertet_am)
                         VALUES(?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(company_id,id) DO UPDATE SET stufe=excluded.stufe,beleg=excluded.beleg,quelle=excluded.quelle,bewertet_am=excluded.bewertet_am""",
                (cid,rid,key,pid,int(nr),int(v["stufe"]),v.get("beleg","").strip(),v.get("quelle","manuell"),now()))
    c.execute("UPDATE companies SET status='laeuft' WHERE "+KEY_CO+" AND status='neu'", (cid,))
    c.commit(); c.close(); return {"ok":True,"saved":len([1 for v in items.values() if v.get('stufe')])}

def _avg(rows):
    rows=[r for r in rows if r is not None]
    return round(sum(rows)/len(rows),2) if rows else 0

@app.get("/api/companies/{cid}/report")
def report(cid:str):
    c=db()
    co=c.execute(SEL_CO+" WHERE "+KEY_CO, (cid,)).fetchone()
    if not co: c.close(); raise HTTPException(404)
    dim_of={r["item_nr"]:r["dimension"] for r in c.execute("SELECT item_nr,dimension FROM ref_items").fetchall()}
    bew=[dict(r) for r in c.execute(SEL_BEW+" WHERE "+W_CO, (cid,)).fetchall()]
    procs=[dict(r) for r in c.execute(SEL_PROC+" WHERE "+W_CO+" ORDER BY process_id", (cid,)).fetchall()]
    # Dimension-Ø (Spider 5)
    dim_avg={d:_avg([b["stufe"] for b in bew if dim_of.get(b["item_nr"])==d]) for d in DIMS}
    gesamt=_avg([b["stufe"] for b in bew])
    bok=sum(1 for b in bew if (b["beleg"] or "").strip()); btot=len(bew)
    # per KP × Dimension + KP-Ø
    kp_rows=[]
    for p in procs:
        pid=p["process_id"]; bp=[b for b in bew if b["process_id"]==pid]
        row={"process_id":pid,"process_name":p["process_name"],
             "dims":{d:_avg([b["stufe"] for b in bp if dim_of.get(b["item_nr"])==d]) for d in DIMS},
             "krit15":{k:_avg([b["stufe"] for b in bp if b["item_nr"] in its]) for k,its in KRIT15},
             "avg":_avg([b["stufe"] for b in bp])}
        kp_rows.append(row)
    # Prozessautomatisierungs-Matrix (intern, je TP)
    auto={}
    for p in procs:
        pid=p["process_id"]; rows=[]
        tps=c.execute(SEL_TP+" WHERE "+W_CO+" AND process_id=? ORDER BY step_no",(cid,pid)).fetchall()
        for tp in tps:
            sid=tp["sub_process_id"]; bt=[b for b in bew if b["sub_process_id"]==sid]
            crit={name:_avg([b["stufe"] for b in bt if b["item_nr"] in its]) for name,its in PA_CRIT}
            rows.append({"tp":tp["sub_process_name"],"sub_process_id":sid,"krit":crit,
                         "avg":_avg([v for v in crit.values() if v])})
        auto[pid]={"process_name":p["process_name"],"rows":rows}
    # Cross-funktionale Matrix (je KP)
    cross=[]
    for p in procs:
        pid=p["process_id"]; bp=[b for b in bew if b["process_id"]==pid]
        crit={name:_avg([b["stufe"] for b in bp if b["item_nr"] in its]) for name,its in CF_CRIT}
        cross.append({"process_id":pid,"owner":p["owner_name"],"io":(p["input_text"] or "?")+" → "+(p["output_text"] or "?"),
                      "krit":crit,"avg":_avg([v for v in crit.values() if v])})
    # Spider 6 (Automatisierungs-Reife, company-weit, PA-Kriterien)
    spider6={name:_avg([b["stufe"] for b in bew if b["item_nr"] in its]) for name,its in PA_CRIT}
    krit15_overall={k:_avg([b["stufe"] for b in bew if b["item_nr"] in its]) for k,its in KRIT15}
    items12_overall={("I-%02d"%n):_avg([b["stufe"] for b in bew if b["item_nr"]==n]) for n in ITEMS12}
    c.close()
    return {"company":dict(co),"gesamt":gesamt,"beleg_quote":(round(bok/btot*100) if btot else 0),
            "n_bewertungen":btot,"dim_avg":dim_avg,"kp_rows":kp_rows,
            "auto":auto,"cross":cross,"spider6":spider6,
            "krit15_labels":[k for k,_ in KRIT15],"krit15_overall":krit15_overall,
            "items12":["I-%02d"%n for n in ITEMS12],"items12_overall":items12_overall,
            "pa_crit":[x[0] for x in PA_CRIT],"cf_crit":[x[0] for x in CF_CRIT],"dims":DIMS}

@app.post("/api/import_yaml")
async def import_yaml(req: Request):
    raw = await req.body()
    try:
        import yaml as _y
    except Exception:
        raise HTTPException(500, "PyYAML nicht installiert: pip install pyyaml")
    try:
        data = _y.safe_load(raw.decode("utf-8"))
    except Exception as e:
        raise HTTPException(400, "YAML-Fehler: %s" % e)
    if not isinstance(data, dict):
        raise HTTPException(400, "YAML-Wurzel muss ein Objekt sein (company:/profile:/prozesse:).")
    co = data.get("company", {}) or {}
    c = db()
    if PG:
        cid = c.execute("INSERT INTO companies(name,branche,rechtsform,mitarbeitende,region,status) VALUES(?,?,?,?,?,?) RETURNING company_id::text AS id",
            (co.get("name", "Importiert"), co.get("branche"), co.get("rechtsform"),
             co.get("mitarbeitende") or co.get("ma"), co.get("region"), "laeuft")).fetchone()["id"]
    else:
        cur = c.execute("INSERT INTO companies(name,branche,rechtsform,ma,region,status,created_at) VALUES(?,?,?,?,?,?,?)",
            (co.get("name", "Importiert"), co.get("branche"), co.get("rechtsform"),
             co.get("mitarbeitende") or co.get("ma"), co.get("region"), "laeuft", now()))
        cid = cur.lastrowid
    pr = data.get("profile", {}) or {}
    full = data.get("unternehmensdaten") or data.get("profil_full") or pr or {}
    c.execute("INSERT INTO company_profile(company_id,geschaeftsmodell,tech_stack,profile_json) VALUES(?,?,?,?)",
        (cid, pr.get("geschaeftsmodell", ""), pr.get("tech_stack", ""), json.dumps(full, ensure_ascii=False)))
    np_ = 0; nb = 0
    for p in (data.get("prozesse", []) or []):
        pid = p["process_id"]
        kat = _kat(p.get("kategorie")) if PG else p.get("kategorie", "")
        c.execute("INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie,owner_name,owner_role,trigger_text,input_text,output_text) VALUES(?,?,?,?,?,?,?,?,?)",
            (cid, pid, p.get("process_name", pid), kat, p.get("owner_name"),
             p.get("owner_role"), p.get("trigger"), p.get("input"), p.get("output")))
        np_ += 1
        for tp in (p.get("teilprozesse", []) or []):
            step = int(tp.get("step")); sid = "%s.TP-%d" % (pid, step)
            c.execute("""INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation,tools,medienbrueche,schnittstellen,api) VALUES(?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(company_id,sub_process_id) DO UPDATE SET sub_process_name=excluded.sub_process_name,notation=excluded.notation,tools=excluded.tools,medienbrueche=excluded.medienbrueche,schnittstellen=excluded.schnittstellen,api=excluded.api""",
                (cid, sid, pid, step, tp.get("name", "Teilprozess %d" % step), tp.get("notation", ""),
                 tp.get("tools"), tp.get("medienbrueche"), tp.get("schnittstellen"), tp.get("api")))
            for nr, b in (tp.get("bewertungen", {}) or {}).items():
                if not b or not b.get("stufe"): continue
                nr = int(nr); beleg = (b.get("beleg") or "").strip() or "Aus YAML übernommen"
                rid = "%s.I-%02d" % (sid, nr)
                if PG:
                    c.execute("""INSERT INTO bitkom_bewertungen(company_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES(?,?,?,?,?,?,?,?)
                                 ON CONFLICT(company_id,id) DO UPDATE SET stufe=excluded.stufe,beleg=excluded.beleg,quelle=excluded.quelle,bewertet_am=excluded.bewertet_am""",
                        (cid, rid, sid, nr, int(b["stufe"]), beleg, "yaml", now()))
                else:
                    c.execute("""INSERT INTO bitkom_bewertungen(company_id,id,sub_process_id,process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES(?,?,?,?,?,?,?,?,?)
                                 ON CONFLICT(company_id,id) DO UPDATE SET stufe=excluded.stufe,beleg=excluded.beleg,quelle=excluded.quelle,bewertet_am=excluded.bewertet_am""",
                        (cid, rid, sid, pid, nr, int(b["stufe"]), beleg, "yaml", now()))
                nb += 1
    c.commit(); c.close()
    return {"ok": True, "id": cid, "prozesse": np_, "bewertungen": nb}

# ---------------- Beleg-Dokumente (Stufe 1: Upload & Ablage) ----------------
def _doc_public(d):
    d = dict(d); d.pop("storage_key", None); return d

@app.post("/api/companies/{cid}/documents")
async def upload_document(cid: str, ref_id: str = Form(...), file: UploadFile = File(...)):
    if not REF_RE.match(ref_id or ""):
        raise HTTPException(400, "ref_id muss 'KP-XX' oder 'KP-XX.TP-Y' sein")
    c = db()
    if not c.execute(SEL_CO + " WHERE " + KEY_CO, (cid,)).fetchone():
        c.close(); raise HTTPException(404, "Mandant unbekannt")
    data = await file.read()
    if not data:
        c.close(); raise HTTPException(400, "Leere Datei")
    if len(data) > MAX_DOC_MB * 1024 * 1024:
        c.close(); raise HTTPException(413, "Datei groesser als %d MB" % MAX_DOC_MB)
    doc_id = str(uuid.uuid4())
    safe = re.sub(r"[^\w.\-äöüÄÖÜß ]", "_", file.filename or "datei")[:120] or "datei"
    key = "%s/%s/%s_%s" % (cid, ref_id, doc_id[:8], safe)
    try:
        store_file(key, data, file.content_type)
    except Exception as e:
        c.close(); raise HTTPException(502, "Storage-Fehler: %s" % e)
    c.execute("INSERT INTO beleg_dokumente(doc_id,company_id,ref_id,filename,storage_key,mime_type,status,uploaded_at) VALUES(?,?,?,?,?,?,?,?)",
        (doc_id, cid, ref_id, safe, key, file.content_type, "hochgeladen", now()))
    c.commit()
    d = dict(c.execute(SEL_DOC + " WHERE doc_id" + ("::text" if PG else "") + "=?", (doc_id,)).fetchone())
    c.close()
    return _doc_public(d)

@app.get("/api/companies/{cid}/documents")
def list_documents(cid: str, ref_id: str = None):
    c = db()
    q = SEL_DOC + " WHERE " + W_CO; params = [cid]
    if ref_id:
        q += " AND ref_id=?"; params.append(ref_id)
    q += " ORDER BY uploaded_at DESC"
    rows = [_doc_public(r) for r in c.execute(q, tuple(params)).fetchall()]
    c.close(); return rows

@app.get("/api/companies/{cid}/documents/{doc_id}/file")
def get_document_file(cid: str, doc_id: str):
    c = db()
    r = c.execute(SEL_DOC + " WHERE " + W_CO + " AND doc_id" + ("::text" if PG else "") + "=?", (cid, doc_id)).fetchone()
    c.close()
    if not r: raise HTTPException(404, "Dokument unbekannt")
    try:
        data = load_file(r["storage_key"])
    except Exception:
        raise HTTPException(404, "Datei nicht im Storage")
    return Response(content=data, media_type=r["mime_type"] or "application/octet-stream",
                    headers={"Content-Disposition": 'inline; filename="%s"' % r["filename"]})

@app.delete("/api/companies/{cid}/documents/{doc_id}")
def delete_document(cid: str, doc_id: str):
    c = db()
    r = c.execute(SEL_DOC + " WHERE " + W_CO + " AND doc_id" + ("::text" if PG else "") + "=?", (cid, doc_id)).fetchone()
    if not r: c.close(); raise HTTPException(404, "Dokument unbekannt")
    delete_file(r["storage_key"])
    c.execute("DELETE FROM beleg_dokumente WHERE " + W_CO + " AND doc_id" + ("::text" if PG else "") + "=?", (cid, doc_id))
    c.commit(); c.close(); return {"ok": True}

# ---------------- Static frontend ----------------
@app.get("/")
def index(): return FileResponse(os.path.join(HERE,"static","index.html"))

@app.get("/sw.js")
def sw():
    # Service Worker auf Root-Pfad -> Scope "/" (PWA)
    return FileResponse(os.path.join(HERE, "static", "sw.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})

@app.get("/manifest.json")
def manifest():
    return FileResponse(os.path.join(HERE, "static", "manifest.json"), media_type="application/manifest+json")
app.mount("/static", StaticFiles(directory=os.path.join(HERE,"static")), name="static")
