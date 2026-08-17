# -*- coding: utf-8 -*-
"""
BC0 Onboarding-App — FastAPI · SQLite (lokal) ODER PostgreSQL/Supabase (DATABASE_URL) · Stand 10.08.2026

Backend-Wahl:
  - Env-Variable DATABASE_URL gesetzt -> PostgreSQL, Schema v1.1 (verbindliche Projekt-Vorgabe)
  - sonst                             -> SQLite (bc0.db wie bisher; Pfad per BC0_DB überschreibbar)

Eine .env neben app.py wird automatisch geladen (DATABASE_URL=postgresql://...).

ANMELDEPFLICHT (seit 10.08.2026, Etappe 4a)
    Jeder Pfad unter /api/ verlangt eine gültige Sitzung. Ausgenommen sind nur
    /api/auth/login, /api/auth/logout und /api/auth/status. Durchgesetzt wird das
    von bc0_auth.middleware.AnmeldepflichtMiddleware — nicht endpunktweise, damit
    ein neu hinzugefügter Endpunkt nicht versehentlich offen bleibt.

    Es gibt bewusst kein Standardkonto. Der erste Zugang wird auf dem Server
    angelegt:
        python benutzer_verwalten.py anlegen --email … --name "…" --rolle admin
    Solange kein Benutzer existiert, ist die Anwendung für alle gesperrt.
    Siehe AUTH.md.

MANDANTENTRENNUNG (seit 11.08.2026, Etappe 4b)
    Jeder Endpunkt mit einer company_id ruft pruefe_mandant() auf. Ein Benutzer
    sieht und ändert ausschließlich die ihm zugeordneten Mandanten; ein Admin
    alle. Neue Mandanten anlegen — auch per YAML-Import — dürfen nur Admins.

    Ein fremder Mandant wird mit 404 beantwortet, nicht mit 403: Wer ihn nicht
    sehen darf, soll nicht erfahren, dass es ihn gibt.

    Die Regel steht an genau einer Stelle, in Benutzer.darf_mandanten_sehen.
    Auch die Listenfilterung greift darauf zurück statt eine WHERE-Bedingung zu
    formulieren — zwei Formulierungen derselben Regel könnten auseinanderlaufen,
    ohne dass es auffällt.

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

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

DB = os.environ.get("BC0_DB", os.path.join(HERE, "bc0.db"))
SCHEMA_SQL = os.path.join(HERE, "schema_v1.1.1.sql")

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

# ---- Rollen und Kostensaetze (Schema v1.2 Teil 2, seit 11.08.2026) ----
# Kostenachse der ROI-Rechnung: BC2 rechnet Zeit x Menge x Satz; der Satz kommt
# von hier. BC0 liefert das Vokabular (welche Rollen, welche Klasse, was kostet
# die Klasse) — wer wie lange an einem Schritt arbeitet, erhebt BC1.
#
# Kostenklassen (beschlossen 11.08.2026):
#   K1 gewerblich/Assistenz · K2 Sachbearbeitung · K3 Fachkraft/Spezialist
#   K4 Fuehrung/Teamleitung · K5 Geschaeftsfuehrung
#
# Massgeblich ist schema_v1.2_stammdaten_und_gate.sql. Die Anweisungen hier sind
# damit deckungsgleich und dienen dem SQLite-Entwicklungsmodus sowie einer
# PostgreSQL-Datenbank, in der das Schema noch nicht eingespielt wurde.
STAMM_DDL_PG = """
CREATE TABLE IF NOT EXISTS mandant_rollen (
  company_id   UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  rolle_id     TEXT NOT NULL,
  bezeichnung  TEXT NOT NULL,
  klasse       TEXT NOT NULL CHECK (klasse IN ('K1','K2','K3','K4','K5')),
  hinweis      TEXT,
  aktiv        BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (company_id, rolle_id)
);
CREATE TABLE IF NOT EXISTS rollen_kostensaetze (
  company_id   UUID         NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  klasse       TEXT         NOT NULL CHECK (klasse IN ('K1','K2','K3','K4','K5')),
  satz_eur_h   NUMERIC(8,2) NOT NULL CHECK (satz_eur_h > 0),
  quelle       TEXT         NOT NULL CHECK (quelle IN ('erhoben','branchenreferenz','geschaetzt')),
  gueltig_ab   DATE         NOT NULL DEFAULT current_date,
  bemerkung    TEXT,
  PRIMARY KEY (company_id, klasse, gueltig_ab)
);
"""
STAMM_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS mandant_rollen(
  company_id INTEGER NOT NULL, rolle_id TEXT NOT NULL, bezeichnung TEXT NOT NULL,
  klasse TEXT NOT NULL CHECK (klasse IN ('K1','K2','K3','K4','K5')),
  hinweis TEXT, aktiv INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY(company_id, rolle_id));
CREATE TABLE IF NOT EXISTS rollen_kostensaetze(
  company_id INTEGER NOT NULL, klasse TEXT NOT NULL
    CHECK (klasse IN ('K1','K2','K3','K4','K5')),
  satz_eur_h REAL NOT NULL CHECK (satz_eur_h > 0),
  quelle TEXT NOT NULL CHECK (quelle IN ('erhoben','branchenreferenz','geschaetzt')),
  gueltig_ab TEXT NOT NULL, bemerkung TEXT,
  PRIMARY KEY(company_id, klasse, gueltig_ab));
"""

#: Die fünf Kostenklassen. Steht hier, damit die Oberfläche sie über /api/meta
#: bekommt und nicht selbst eine zweite Liste führt.
KOSTENKLASSEN = [
    ("K1", "gewerblich / Assistenz"),
    ("K2", "Sachbearbeitung"),
    ("K3", "Fachkraft / Spezialist"),
    ("K4", "Führung / Teamleitung"),
    ("K5", "Geschäftsführung"),
]
KOSTEN_QUELLEN = ["erhoben", "branchenreferenz", "geschaetzt"]

# ---- Entitaeten-Register (ADR-004, seit 12.08.2026) ----------------------------
# Personen und Systeme waren bis hierher Freitext in fremden Spalten
# (ref_prozesse.owner_name, ref_teilprozesse.tools). Beide Felder mussten eine
# n:m-Beziehung in einen einzelnen Text pressen und haben das mit Trennzeichen
# improvisiert („Ozan Kiraz / Mehdi Louali"). Maschinell nicht aufloesbar.
#
# Massgeblich sind schema_v1.3_teil_a_personen.sql und _teil_b_systeme.sql. Die
# Anweisungen hier sind damit deckungsgleich und dienen dem SQLite-Entwicklungs-
# modus sowie einer PostgreSQL-Datenbank ohne eingespielten Nachtrag.
ENTITAET_DDL_PG = """
CREATE TABLE IF NOT EXISTS ref_personen (
  company_id   UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  person_id    TEXT NOT NULL,
  name         TEXT,
  funktion     TEXT,
  rolle_id     TEXT,
  extern       BOOLEAN NOT NULL DEFAULT FALSE,
  organisation TEXT,
  hinweis      TEXT,
  aktiv        BOOLEAN NOT NULL DEFAULT TRUE,
  angelegt_am  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, person_id)
);
CREATE TABLE IF NOT EXISTS prozess_personen (
  company_id UUID       NOT NULL,
  process_id VARCHAR(8) NOT NULL,
  person_id  TEXT       NOT NULL,
  funktion   TEXT       NOT NULL,
  hinweis    TEXT,
  PRIMARY KEY (company_id, process_id, person_id, funktion)
);
CREATE TABLE IF NOT EXISTS ref_systeme_katalog (
  katalog_id  TEXT PRIMARY KEY,
  bezeichnung TEXT NOT NULL,
  kategorie   TEXT NOT NULL,
  hersteller  TEXT,
  quelloffen  BOOLEAN,
  hinweis     TEXT,
  aktiv       BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS mandant_systeme (
  company_id  UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  system_id   TEXT NOT NULL,
  katalog_id  TEXT,
  bezeichnung TEXT NOT NULL,
  einsatz     TEXT,
  hinweis     TEXT,
  aktiv       BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (company_id, system_id)
);
"""
ENTITAET_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS ref_personen(
  company_id INTEGER NOT NULL, person_id TEXT NOT NULL, name TEXT, funktion TEXT,
  rolle_id TEXT, extern INTEGER NOT NULL DEFAULT 0, organisation TEXT, hinweis TEXT,
  aktiv INTEGER NOT NULL DEFAULT 1, angelegt_am TEXT,
  PRIMARY KEY(company_id, person_id));
CREATE TABLE IF NOT EXISTS prozess_personen(
  company_id INTEGER NOT NULL, process_id TEXT NOT NULL, person_id TEXT NOT NULL,
  funktion TEXT NOT NULL, hinweis TEXT,
  PRIMARY KEY(company_id, process_id, person_id, funktion));
CREATE TABLE IF NOT EXISTS ref_systeme_katalog(
  katalog_id TEXT PRIMARY KEY, bezeichnung TEXT NOT NULL, kategorie TEXT NOT NULL,
  hersteller TEXT, quelloffen INTEGER, hinweis TEXT, aktiv INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS mandant_systeme(
  company_id INTEGER NOT NULL, system_id TEXT NOT NULL, katalog_id TEXT,
  bezeichnung TEXT NOT NULL, einsatz TEXT, hinweis TEXT,
  aktiv INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY(company_id, system_id));
"""

# ---- Erhebungen (ADR-004 Abschnitt 2.5, Schema v1.3 Teil C) --------------------
# Eine Bewertung wusste bis hierher nur, *wann* sie entstand, nicht *zu welcher
# Erhebung* sie gehoert. Eine Nacherhebung haette dieselben Item-Schluessel
# erzeugt und den bisherigen Stand stillschweigend ueberschrieben — womit weder
# eine Gate-Freigabe reproduzierbar noch ein Vorher-Nachher-Vergleich moeglich
# waere.
#
# Massgeblich ist schema_v1.3_teil_c_erhebungen.sql.
ERHEBUNG_DDL_PG = """
CREATE TABLE IF NOT EXISTS ref_erhebungen (
  company_id   UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  erhebung_id  TEXT NOT NULL,
  bezeichnung  TEXT NOT NULL,
  stand        DATE NOT NULL,
  status       TEXT NOT NULL DEFAULT 'offen'
               CHECK (status IN ('offen','abgeschlossen','verworfen')),
  methode      TEXT,
  hinweis      TEXT,
  angelegt_am  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, erhebung_id)
);
"""
ERHEBUNG_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS ref_erhebungen(
  company_id INTEGER NOT NULL, erhebung_id TEXT NOT NULL, bezeichnung TEXT NOT NULL,
  stand TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'offen'
    CHECK (status IN ('offen','abgeschlossen','verworfen')),
  methode TEXT, hinweis TEXT, angelegt_am TEXT,
  PRIMARY KEY(company_id, erhebung_id));
"""

#: Die drei Zustaende einer Erhebung. `verworfen` wird von allen Auswertungen
#: uebergangen — ein Fehlversuch soll den Stand nicht verfaelschen.
ERHEBUNG_STATUS = ["offen", "abgeschlossen", "verworfen"]

# ---- Gate 0: Freigabebogen (Schema v1.4, seit 17.08.2026) ----------------------
# Zwischen BC1 und BC2 sitzt ein Mensch. Der Bogen beantwortet nicht „ist alles
# ausgefuellt" — das kann Software allein —, sondern: darf auf dieser Grundlage
# gerechnet werden? Deshalb traegt jede gepruefte Angabe neben dem Befuellungsgrad
# eine GUETE. Ein Befuellungsgrad sagt, wie viel dasteht, nicht ob es stimmt; ohne
# die Guete verfiele am Gate genau die Information, die BC2 braucht, um zwischen
# Punktwert und Bandbreite zu entscheiden.
#
# Massgeblich ist schema_v1.4_gate0.sql. Die Anweisungen hier sind damit
# deckungsgleich und dienen dem SQLite-Entwicklungsmodus sowie einer PostgreSQL-
# Datenbank, in der der Nachtrag noch nicht eingespielt wurde. gate_ereignisse und
# prozess_schnittstellen stammen aus Schema v1.2 und werden hier vorsorglich
# mitangelegt — ohne sie liefen die ALTER-Anweisungen ins Leere.
#
# Der Fremdschluessel gate_ereignisse.benutzer_id -> app_benutzer fehlt hier
# absichtlich: init_db() laeuft vor AuthDienst.einrichten(), die Tabelle gaebe es
# zu diesem Zeitpunkt noch nicht. Das Schema-Skript setzt ihn.
GATE0_DDL_PG = """
CREATE TABLE IF NOT EXISTS ref_anfragen (
  company_id     UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  anfrage_id     TEXT        NOT NULL CHECK (anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}$'),
  originaltext   TEXT        NOT NULL CHECK (length(btrim(originaltext)) > 0),
  eingang_am     DATE        NOT NULL,
  eingang_weg    TEXT,
  steller_id     TEXT,
  hinweis        TEXT,
  angelegt_am    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, anfrage_id)
);
CREATE TABLE IF NOT EXISTS ref_gate_pruefpunkte (
  pruefpunkt     TEXT        PRIMARY KEY CHECK (pruefpunkt ~ '^[a-z_]{3,30}$'),
  bezeichnung    TEXT        NOT NULL,
  erlaeuterung   TEXT,
  quelle_bc      TEXT        NOT NULL CHECK (quelle_bc IN ('BC0','BC1','BC0/BC1')),
  guete_noetig   BOOLEAN     NOT NULL DEFAULT FALSE,
  pflicht        BOOLEAN     NOT NULL DEFAULT TRUE,
  aktiv          BOOLEAN     NOT NULL DEFAULT TRUE,
  reihenfolge    INTEGER     NOT NULL DEFAULT 100
);
CREATE TABLE IF NOT EXISTS prozess_schnittstellen (
  company_id       UUID       NOT NULL,
  von_process_id   VARCHAR(8) NOT NULL,
  nach_process_id  VARCHAR(8) NOT NULL,
  art              TEXT       NOT NULL
                   CHECK (art IN ('daten','freigabe','material','information')),
  beschreibung     TEXT,
  PRIMARY KEY (company_id, von_process_id, nach_process_id, art)
);
CREATE TABLE IF NOT EXISTS gate_ereignisse (
  ereignis_id  BIGSERIAL   PRIMARY KEY,
  gate         TEXT        NOT NULL,
  company_id   UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  objekt_typ   TEXT        NOT NULL,
  objekt_id    TEXT        NOT NULL,
  ereignis     TEXT        NOT NULL
               CHECK (ereignis IN ('freigegeben','widerrufen','zurueckgewiesen','uebergeben')),
  benutzer_id  TEXT,
  am           TIMESTAMPTZ NOT NULL DEFAULT now(),
  grundlage    JSONB,
  grund        TEXT,
  paket_id     UUID,
  CHECK (ereignis <> 'zurueckgewiesen' OR (grund IS NOT NULL AND length(btrim(grund)) > 0))
);
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS anfrage_id       TEXT;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS erhebung_id      TEXT;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS bc1_profil_stand TEXT;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS kette_bestaetigt BOOLEAN;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS kette_ergaenzung TEXT;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS massnahme        TEXT;
CREATE TABLE IF NOT EXISTS gate_pruefpunkt_werte (
  ereignis_id    BIGINT      NOT NULL REFERENCES gate_ereignisse(ereignis_id) ON DELETE CASCADE,
  pruefpunkt     TEXT        NOT NULL REFERENCES ref_gate_pruefpunkte(pruefpunkt),
  vorhanden_pct  NUMERIC(5,2) CHECK (vorhanden_pct BETWEEN 0 AND 100),
  guete          TEXT        CHECK (guete IN ('belegt','geschaetzt','geraten','entfaellt')),
  bestaetigt     BOOLEAN     NOT NULL,
  anmerkung      TEXT,
  PRIMARY KEY (ereignis_id, pruefpunkt)
);
CREATE INDEX IF NOT EXISTS idx_gate_objekt
  ON gate_ereignisse(gate, company_id, objekt_id, am DESC);
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_gate_massnahme') THEN
    ALTER TABLE gate_ereignisse ADD CONSTRAINT ck_gate_massnahme
      CHECK (ereignis <> 'zurueckgewiesen'
             OR (massnahme IS NOT NULL AND length(btrim(massnahme)) > 0));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_gate_objekt_typ') THEN
    ALTER TABLE gate_ereignisse ADD CONSTRAINT ck_gate_objekt_typ
      CHECK (objekt_typ IN ('prozess','teilprozess'));
  END IF;
END $$;
"""
GATE0_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS ref_anfragen(
  company_id INTEGER NOT NULL, anfrage_id TEXT NOT NULL,
  originaltext TEXT NOT NULL, eingang_am TEXT NOT NULL, eingang_weg TEXT,
  steller_id TEXT, hinweis TEXT, angelegt_am TEXT,
  PRIMARY KEY(company_id, anfrage_id));
CREATE TABLE IF NOT EXISTS ref_gate_pruefpunkte(
  pruefpunkt TEXT PRIMARY KEY, bezeichnung TEXT NOT NULL, erlaeuterung TEXT,
  quelle_bc TEXT NOT NULL CHECK (quelle_bc IN ('BC0','BC1','BC0/BC1')),
  guete_noetig INTEGER NOT NULL DEFAULT 0, pflicht INTEGER NOT NULL DEFAULT 1,
  aktiv INTEGER NOT NULL DEFAULT 1, reihenfolge INTEGER NOT NULL DEFAULT 100);
CREATE TABLE IF NOT EXISTS prozess_schnittstellen(
  company_id INTEGER NOT NULL, von_process_id TEXT NOT NULL, nach_process_id TEXT NOT NULL,
  art TEXT NOT NULL CHECK (art IN ('daten','freigabe','material','information')),
  beschreibung TEXT,
  PRIMARY KEY(company_id, von_process_id, nach_process_id, art));
CREATE TABLE IF NOT EXISTS gate_ereignisse(
  ereignis_id INTEGER PRIMARY KEY AUTOINCREMENT,
  gate TEXT NOT NULL, company_id INTEGER NOT NULL,
  objekt_typ TEXT NOT NULL CHECK (objekt_typ IN ('prozess','teilprozess')),
  objekt_id TEXT NOT NULL,
  ereignis TEXT NOT NULL
    CHECK (ereignis IN ('freigegeben','widerrufen','zurueckgewiesen','uebergeben')),
  benutzer_id TEXT, am TEXT NOT NULL, grundlage TEXT, grund TEXT, paket_id TEXT,
  anfrage_id TEXT, erhebung_id TEXT, bc1_profil_stand TEXT,
  kette_bestaetigt INTEGER, kette_ergaenzung TEXT, massnahme TEXT,
  CHECK (ereignis <> 'zurueckgewiesen' OR (grund IS NOT NULL AND length(trim(grund)) > 0)),
  CHECK (ereignis <> 'zurueckgewiesen'
         OR (massnahme IS NOT NULL AND length(trim(massnahme)) > 0)));
CREATE INDEX IF NOT EXISTS idx_gate_objekt
  ON gate_ereignisse(gate, company_id, objekt_id);
CREATE TABLE IF NOT EXISTS gate_pruefpunkt_werte(
  ereignis_id INTEGER NOT NULL REFERENCES gate_ereignisse(ereignis_id) ON DELETE CASCADE,
  pruefpunkt TEXT NOT NULL REFERENCES ref_gate_pruefpunkte(pruefpunkt),
  vorhanden_pct REAL CHECK (vorhanden_pct BETWEEN 0 AND 100),
  guete TEXT CHECK (guete IN ('belegt','geschaetzt','geraten','entfaellt')),
  bestaetigt INTEGER NOT NULL, anmerkung TEXT,
  PRIMARY KEY(ereignis_id, pruefpunkt));
"""

#: Startbestand des Pruefpunktkatalogs, Wortlaut aus schema_v1.4_gate0.sql.
#: Als Python-Liste und nicht als INSERT im DDL-Text, weil beide Backends
#: denselben Bestand brauchen und Wahrheitswerte in SQLite Zahlen sind — dieselbe
#: Loesung wie bei SYSTEM_KATALOG.
#: Spalten: pruefpunkt, bezeichnung, erlaeuterung, quelle_bc, guete_noetig, pflicht,
#: aktiv, reihenfolge.
GATE_PRUEFPUNKTE = [
    ("dauer", "Dauer je Ausfuehrung",
     "Bearbeitungszeit eines Durchlaufs. Ohne sie gibt es keinen Jahresaufwand und damit keinen ROI.",
     "BC1", True, True, True, 10),
    ("haeufigkeit", "Ausfuehrungen je Zeitraum",
     "Wie oft der Prozess laeuft. Meist aus einem System zaehlbar und damit oft besser belegt als die Dauer.",
     "BC1", True, True, True, 20),
    ("menge", "Menge je Ausfuehrung",
     "Stueckzahl oder Volumen je Durchlauf — Zahl der Positionen, Datensaetze, Dokumente.",
     "BC1", True, True, True, 30),
    ("rollen", "Beteiligte Rollen mit Zeitanteil",
     "Welche Rolle wie lange beteiligt ist. Paare (rolle_id, zeitanteil), nicht Namensliste.",
     "BC1", True, True, True, 40),
    ("kosten", "Kostensatz je beteiligter Rolle",
     "Vollkostensatz aus mandant_rollen und rollen_kostensaetze. Guete unterscheidet "
     "Buchhaltungswert von Branchenreferenz.",
     "BC0", True, True, True, 50),
    ("prozessbeschreibung", "Prozessbeschreibung",
     "Ein bis zwei Saetze, was der Prozess umfasst. Grundlage der Erklaerung durch den BC1-Bot.",
     "BC0", False, True, True, 60),
    ("medienbrueche", "Medienbrueche erfasst",
     "Register aus Schema v1.3 Teil B. Leer kann richtig sein — dann bestaetigt der Mensch die Null.",
     "BC0", False, True, True, 70),
    ("ansprechpartner", "Ansprechpartner bei Rueckfragen",
     "Wer Auskunft geben kann, wenn BC1 oder BC2 nachfragt. Verweis ins Personenregister.",
     "BC0", False, True, True, 80),
    ("zulaessigkeit", "Zulaessigkeit der Automatisierung",
     "Personenbezogene Daten, Mitbestimmung, Vier-Augen-Prinzip, regulatorische Bindung. "
     "VORGESEHEN, NICHT AKTIV — vor dem Scharfschalten ist zu klaeren, wer das beurteilt.",
     "BC0", False, True, False, 90),
]

#: Die vier Guete-Stufen. `entfaellt` ist kein Ausweichwert, sondern die Aussage
#: „trifft auf diesen Prozess nicht zu".
GATE_GUETEN = ["belegt", "geschaetzt", "geraten", "entfaellt"]

#: Was der Bogen schreiben darf. `widerrufen` und `uebergeben` stehen zwar in der
#: Ereignistabelle, entstehen aber nicht an dieser Maske.
GATE_EREIGNISSE = ["freigegeben", "zurueckgewiesen"]

#: Vorbedingung: mindestens 27 der 30 Items bewertet (Schema v1.4, Abschnitt 18).
GATE_ITEMS_MIN = 27

#: Projektsetzung, keine Bitkom-Vorgabe — deshalb Hinweis und keine Sperre.
GATE_SCHWELLE = 3.5

#: Beteiligungsarten, die als Ansprechpartner fuer Rueckfragen zaehlen.
GATE_ANSPRECHPARTNER = ("mitwirkend", "vertretung", "sponsor")

#: Die vier Zustaende von `am_zug`, zugleich die Reihenfolge der Liste: Was jetzt
#: zu tun ist, steht oben; was abgeschlossen ist, unten.
GATE_AM_ZUG = ("entscheiden", "bc0_pflege", "wartet_bc1", "entschieden")

#: Die vier Angaben, die BC1 nachliefern muss. Nur als Wortlaut fuer die
#: Begruendung — die Feldnamen sind noch nicht benannt, siehe _bc1_angaben().
GATE_BC1_FELDER = ("Dauer", "Haeufigkeit", "Menge", "Rollen mit Zeitanteil")

#: Arten von Hindernissen, in der Reihenfolge, in der sie abzuarbeiten sind.
GATE_HINDERNIS_ARTEN = ("eigner", "ansprechpartner", "bewertung")

#: Startbestand des Systemkatalogs. Global wie ITEMS, deshalb im Code und nicht
#: je Mandant. Die ersten vier stammen aus dem NoroAI-Bestand, die uebrigen sind
#: im deutschen Mittelstand haeufig und ersparen dem naechsten Mandanten das
#: Anlegen. Die Liste ist ausdruecklich unvollstaendig und waechst.
SYSTEM_KATALOG = [
    ("SYS-CRM-ESPO",   "EspoCRM",          "crm",             "EspoCRM",       True),
    ("SYS-DEV-GITLAB", "GitLab",           "entwicklung",     "GitLab Inc.",   True),
    ("SYS-AUT-N8N",    "n8n",              "automatisierung", "n8n GmbH",      True),
    ("SYS-BI-GRAFANA", "Grafana",          "bi",              "Grafana Labs",  True),
    ("SYS-OFF-M365",   "Microsoft 365",    "office",          "Microsoft",     False),
    ("SYS-BUC-DATEV",  "DATEV",            "buchhaltung",     "DATEV eG",      False),
    ("SYS-BUC-LEX",    "Lexware",          "buchhaltung",     "Haufe-Lexware", False),
    ("SYS-ERP-SAPB1",  "SAP Business One", "erp",             "SAP",           False),
    ("SYS-KOM-TEAMS",  "Microsoft Teams",  "kommunikation",   "Microsoft",     False),
    ("SYS-DMS-SHARE",  "SharePoint",       "dms",             "Microsoft",     False),
]

#: Art der Beteiligung einer Person an einem Kernprozess. Die Reihenfolge ist die
#: Anzeigereihenfolge in der Oberflaeche.
BETEILIGUNGEN = [
    ("eigner", "Eigner — verantwortlich"),
    ("sponsor", "Sponsor — trägt die Entscheidung"),
    ("mitwirkend", "mitwirkend"),
    ("vertretung", "Vertretung"),
]

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
# Der massgebliche Stand je Einzelbewertung: die juengste nicht verworfene
# Erhebung, die diesen Teilprozess und dieses Item bewertet hat.
#
# Ausdruecklich NICHT die juengste Erhebung des Mandanten. Wird im September nur
# ein Teil der Prozesse nacherhoben, hat die September-Erhebung fuer die uebrigen
# keine Zeilen — ein Filter auf Mandantenebene liesse sie aus dem Bericht
# verschwinden. Der aktuelle Stand ist deshalb eine Zusammensetzung: nacherhobene
# Prozesse mit neuen Werten, unveraenderte mit ihren alten.
#
# Entspricht der View v_bewertung_aktuell in schema_v1.3_teil_c_erhebungen.sql.
# Hier als Unterabfrage, damit auch der SQLite-Entwicklungsmodus sie hat.
def _bew_aktuell(spalten: str) -> str:
    return ("(SELECT " + spalten + " FROM (SELECT bb.*, row_number() OVER ("
            "PARTITION BY bb.company_id, bb.sub_process_id, bb.item_nr "
            "ORDER BY e.stand DESC, e.erhebung_id DESC) AS rang "
            "FROM bitkom_bewertungen bb JOIN ref_erhebungen e "
            "ON e.company_id = bb.company_id AND e.erhebung_id = bb.erhebung_id "
            "WHERE e.status <> 'verworfen') t WHERE rang = 1) AS bitkom_bewertungen")


if PG:
    SEL_CO   = ("SELECT company_id::text AS id,name,branche,rechtsform,mitarbeitende AS ma,region,"
                "status::text AS status,created_at::text AS created_at FROM companies")
    KEY_CO   = "company_id::text=?"   # companies
    W_CO     = "company_id::text=?"   # Fachtabellen
    SEL_PROF = ("SELECT company_id::text AS company_id,geschaeftsmodell,tech_stack,"
                "profile_json::text AS profile_json FROM company_profile")
    SEL_PROC = ("SELECT company_id::text AS company_id,process_id,process_name,kategorie::text AS kategorie,"
                "owner_name,owner_role,trigger_text,input_text,output_text,beschreibung FROM ref_prozesse")
    SEL_TP   = ("SELECT company_id::text AS company_id,sub_process_id,process_id,step_no,sub_process_name,"
                "notation,tools,medienbrueche,schnittstellen,api FROM ref_teilprozesse")
    SEL_BEW  = ("SELECT company_id::text AS company_id,erhebung_id,id,sub_process_id,"
                "left(sub_process_id,5) AS process_id,"
                "item_nr,stufe,beleg,quelle::text AS quelle,bewertet_am::text AS bewertet_am FROM "
                + _bew_aktuell("company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,"
                               "quelle,bewertet_am"))
    SEL_DOC  = ("SELECT doc_id::text AS doc_id,company_id::text AS company_id,ref_id,filename,storage_key,"
                "mime_type,seiten,ocr_confidence,status::text AS status,uploaded_at::text AS uploaded_at FROM beleg_dokumente")
else:
    SEL_CO   = "SELECT * FROM companies";        KEY_CO = "id=?";        W_CO = "company_id=?"
    SEL_PROF = "SELECT * FROM company_profile"
    SEL_PROC = "SELECT * FROM ref_prozesse"
    SEL_TP   = "SELECT * FROM ref_teilprozesse"
    SEL_BEW  = ("SELECT * FROM "
                + _bew_aktuell("company_id,erhebung_id,id,sub_process_id,process_id,item_nr,"
                               "stufe,beleg,quelle,bewertet_am"))
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
        c.execute(STAMM_DDL_PG)
        c.execute(ENTITAET_DDL_PG)
        c.execute(ERHEBUNG_DDL_PG)
        c.execute(GATE0_DDL_PG)
        c.executemany("INSERT INTO ref_gate_pruefpunkte(pruefpunkt,bezeichnung,erlaeuterung,"
                      "quelle_bc,guete_noetig,pflicht,aktiv,reihenfolge) VALUES(?,?,?,?,?,?,?,?) "
                      "ON CONFLICT (pruefpunkt) DO NOTHING", GATE_PRUEFPUNKTE)
        c.executemany("INSERT INTO ref_systeme_katalog(katalog_id,bezeichnung,kategorie,"
                      "hersteller,quelloffen) VALUES(?,?,?,?,?) "
                      "ON CONFLICT (katalog_id) DO NOTHING", SYSTEM_KATALOG)
        # Nachtrag: aktiv-Spalte, falls die Tabelle aus einer frueheren Fassung stammt.
        # Rollen werden gesperrt statt geloescht — BC1 speichert die rolle_id, und ein
        # Verweis auf eine verschwundene Rolle waere nicht mehr aufloesbar.
        c.execute("ALTER TABLE mandant_rollen ADD COLUMN IF NOT EXISTS aktiv BOOLEAN NOT NULL DEFAULT TRUE")
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
      company_id INTEGER, erhebung_id TEXT NOT NULL DEFAULT 'E-0000-00',
      id TEXT, sub_process_id TEXT, process_id TEXT, item_nr INTEGER,
      stufe INTEGER CHECK(stufe BETWEEN 1 AND 5), beleg TEXT NOT NULL, quelle TEXT DEFAULT 'manuell',
      bewertet_am TEXT,
      PRIMARY KEY(company_id,erhebung_id,id),
      FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE);
    """)
    if not c.execute("SELECT COUNT(*) n FROM ref_items").fetchone()["n"]:
        c.executemany("INSERT INTO ref_items VALUES(?,?,?,?)", ITEMS)
    try: c.execute("ALTER TABLE company_profile ADD COLUMN profile_json TEXT")
    except Exception: pass
    for col in ("tools", "medienbrueche", "schnittstellen", "api"):
        try: c.execute("ALTER TABLE ref_teilprozesse ADD COLUMN %s TEXT" % col)
        except Exception: pass
    # Beschreibung je Kernprozess (Schema v1.2 Teil 2): Quelle fuer die Erklaerung
    # durch den BC1-Interview-Bot. In PostgreSQL legt das Schema-Skript sie an.
    try: c.execute("ALTER TABLE ref_prozesse ADD COLUMN beschreibung TEXT")
    except Exception: pass
    c.c.executescript(DOC_DDL_SQLITE)
    c.c.executescript(STAMM_DDL_SQLITE)
    c.c.executescript(ENTITAET_DDL_SQLITE)
    c.c.executescript(ERHEBUNG_DDL_SQLITE)
    c.c.executescript(GATE0_DDL_SQLITE)
    c.executemany("INSERT OR IGNORE INTO ref_systeme_katalog(katalog_id,bezeichnung,"
                  "kategorie,hersteller,quelloffen) VALUES(?,?,?,?,?)",
                  [(a, b, k, h, 1 if q else 0) for a, b, k, h, q in SYSTEM_KATALOG])
    c.executemany("INSERT OR IGNORE INTO ref_gate_pruefpunkte(pruefpunkt,bezeichnung,"
                  "erlaeuterung,quelle_bc,guete_noetig,pflicht,aktiv,reihenfolge) "
                  "VALUES(?,?,?,?,?,?,?,?)",
                  [(p, b, e, q, 1 if g else 0, 1 if pf else 0, 1 if a else 0, r)
                   for p, b, e, q, g, pf, a, r in GATE_PRUEFPUNKTE])
    c.commit(); c.close()

app = FastAPI(title="BC0 Onboarding")
init_db()

# ---------------- Benutzerverwaltung (Etappe 4a, 10.08.2026) ----------------
# Reihenfolge ist wesentlich:
#   1. AuthDienst bauen — er bekommt die Verbindungsfabrik `db` und den
#      Backend-Schalter `PG` übergeben (Konstruktor-Injektion, kein Import-Zyklus).
#   2. `einrichten()` legt app_benutzer, app_benutzer_mandanten und app_sitzungen
#      an, falls sie fehlen. Idempotent.
#   3. `dienst_setzen()` hinterlegt den Dienst für Middleware und Depends.
#   4. Erst danach die Middleware registrieren — sie greift auf den Dienst zu.
from bc0_auth import AuthDienst, Benutzer                            # noqa: E402
from bc0_auth.abhaengigkeiten import (                               # noqa: E402
    admin,
    angemeldeter_benutzer,
    dienst_setzen,
    pruefe_mandant,
)
from bc0_auth.middleware import AnmeldepflichtMiddleware             # noqa: E402
from bc0_auth.routen import router as auth_router                    # noqa: E402

AUTH = AuthDienst(db, PG)
AUTH.einrichten()
dienst_setzen(AUTH)
app.add_middleware(AnmeldepflichtMiddleware)
app.include_router(auth_router)

if not AUTH.ist_eingerichtet():
    import logging as _logging
    _logging.getLogger("bc0.auth").warning(
        "Es ist noch kein Benutzer angelegt — die Anwendung ist damit fuer alle gesperrt. "
        "Ersten Admin anlegen: python benutzer_verwalten.py anlegen "
        '--email <adresse> --name "<Name>" --rolle admin'
    )

# ---------------- API ----------------
@app.get("/api/meta")
def meta():
    c=db(); items=[dict(r) for r in c.execute("SELECT * FROM ref_items ORDER BY item_nr").fetchall()]; c.close()
    return {"items":items,"dims":DIMS,"kp_template":KP_TEMPLATE,
            "pa_crit":PA_CRIT,"cf_crit":CF_CRIT,
            "kostenklassen":[{"klasse":k,"bezeichnung":b} for k,b in KOSTENKLASSEN],
            "kosten_quellen":KOSTEN_QUELLEN,
            "backend":"postgres" if PG else "sqlite"}

def company_progress(c, cid):
    """Erfassungsgrad und Durchschnitt fuer die Mandantenliste.

    Rechnet auf dem MASSGEBLICHEN Stand, nicht auf allen je geschriebenen
    Zeilen. Ohne _bew_aktuell zaehlte eine Nacherhebung doppelt: derselbe
    Teilprozess erschiene mit alter und neuer Bewertung, der Erfassungsgrad
    stiege ueber 100 % und der Durchschnitt mischte zwei Messzeitpunkte.
    Derselbe Fehler, gegen den Schema v1.3 Teil C gebaut wurde — hier war er
    bis zum 17.08.2026 uebersehen.
    """
    kps=c.execute("SELECT COUNT(*) n FROM ref_prozesse WHERE "+W_CO, (cid,)).fetchone()["n"]
    total=kps*5*30
    quelle=_bew_aktuell("company_id, stufe")
    rated=c.execute("SELECT COUNT(*) n FROM "+quelle+" WHERE "+W_CO, (cid,)).fetchone()["n"]
    avg=c.execute("SELECT AVG(stufe) a FROM "+quelle+" WHERE "+W_CO, (cid,)).fetchone()["a"]
    return (round(rated/total*100) if total else 0, round(float(avg),2) if avg else 0, kps)

@app.get("/api/companies")
def companies(benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Mandantenliste — gefiltert auf das, was der Angemeldete sehen darf.

    Der Filter läuft hier in Python und nicht als WHERE-Bedingung. Bei der
    vorliegenden Größenordnung (zweistellige Mandantenzahl) ist der Unterschied
    ohne Belang, und die Regel steht an genau einer Stelle — in
    Benutzer.darf_mandanten_sehen. Eine zweite Formulierung derselben Regel in
    SQL wäre eine Fehlerquelle: Sie könnte auseinanderlaufen, und niemand würde
    es merken, weil beide Wege für sich plausibel aussehen.
    """
    c=db(); out=[]
    order = " ORDER BY created_at DESC" if PG else " ORDER BY id DESC"
    for r in c.execute(SEL_CO+order).fetchall():
        if not benutzer.darf_mandanten_sehen(str(r["id"])):
            continue
        p,a,kps=company_progress(c,r["id"])
        d=dict(r); d.update(progress=p, avg=a, kp_count=kps); out.append(d)
    c.close(); return out

@app.post("/api/companies")
async def create_company(req: Request, _: Benutzer = Depends(admin)):
    """Neuen Mandanten anlegen — Admins vorbehalten.

    Ein Benutzer pflegt sein Unternehmen, er legt keine neuen an. Andernfalls
    könnte er sich selbst Mandanten schaffen, die ihm niemand zugeordnet hat —
    und die Mandantentrennung wäre umgehbar.
    """
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
def get_company(cid:str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
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
    # Welcher Messzeitpunkt gilt? Die Oberflaeche zeigt ihn an, damit niemand
    # unbemerkt in eine abgeschlossene oder in eine neue Erhebung schreibt.
    erh=c.execute("SELECT erhebung_id,bezeichnung,status FROM ref_erhebungen WHERE "+W_CO+
                  " AND status<>'verworfen' ORDER BY stand DESC, erhebung_id DESC LIMIT 1",
                  (cid,)).fetchone()
    c.close()
    return {"company":dict(co),"profile":dict(prof) if prof else {},"processes":procs,
            "ratings":ratings,"erhebung":dict(erh) if erh else None}

@app.put("/api/companies/{cid}/profile")
async def save_profile(cid:str, req:Request, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
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
async def save_process(cid:str, req:Request, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
    b=await req.json(); pid=b["process_id"]; c=db()
    kat=_kat(b.get("kategorie")) if PG else b.get("kategorie")
    c.execute("""UPDATE ref_prozesse SET owner_name=?,owner_role=?,kategorie=?,trigger_text=?,input_text=?,output_text=?,
                 beschreibung=? WHERE """+W_CO+" AND process_id=?",
        (b.get("owner_name"),b.get("owner_role"),kat,b.get("trigger_text"),
         b.get("input_text"),b.get("output_text"),b.get("beschreibung"),cid,pid))
    for n,tp in enumerate(b.get("tps",[]),start=1):
        c.execute("""UPDATE ref_teilprozesse SET sub_process_name=?,notation=?,tools=?,medienbrueche=?,schnittstellen=?,api=?
                     WHERE """+W_CO+" AND sub_process_id=?",
            (tp.get("name"),tp.get("notation"),tp.get("tools"),tp.get("medienbrueche"),
             tp.get("schnittstellen"),tp.get("api"),cid,"%s.TP-%d"%(pid,n)))
    c.commit(); c.close(); return {"ok":True}

@app.post("/api/companies/{cid}/process/add")
async def add_process(cid:str, req:Request, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
    b=await req.json(); i=int(b["kp_index"]); pid=kpid(i); c=db()
    c.execute("INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie) VALUES(?,?,?,?) ON CONFLICT(company_id,process_id) DO NOTHING",
        (cid,pid,KP_TEMPLATE[i],"Steuerungsprozess" if i==0 else ("Kerngeschäftsprozess" if i<4 else "Unterstützungsprozess")))
    for n in range(1,6):
        c.execute("INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation) VALUES(?,?,?,?,?,?) ON CONFLICT(company_id,sub_process_id) DO NOTHING",
            (cid,"%s.TP-%d"%(pid,n),pid,n,"Teilprozess %d"%n,""))
    c.commit(); c.close(); return {"ok":True,"process_id":pid}

@app.post("/api/companies/{cid}/rating")
async def save_rating(cid:str, req:Request, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
    b=await req.json(); key=b["key"]; items=b.get("items",{})
    missing=[k for k,v in items.items() if v.get("stufe") and not (v.get("beleg") or "").strip()]
    if missing:
        raise HTTPException(400, "Beleg fehlt für Item(s): "+", ".join(missing))
    pid=key.split(".")[0]; c=db()
    # In welche Erhebung wird geschrieben? Legt beim ersten Mal eine an.
    eid = _erhebung_offen(c, cid)
    for nr,v in items.items():
        if not v.get("stufe"): continue
        rid="%s.I-%02d"%(key,int(nr))
        if PG:
            c.execute("""INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am)
                         VALUES(?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(company_id,erhebung_id,id) DO UPDATE SET stufe=excluded.stufe,beleg=excluded.beleg,quelle=excluded.quelle,bewertet_am=excluded.bewertet_am""",
                (cid,eid,rid,key,int(nr),int(v["stufe"]),v.get("beleg","").strip(),v.get("quelle","manuell"),now()))
        else:
            c.execute("""INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,process_id,item_nr,stufe,beleg,quelle,bewertet_am)
                         VALUES(?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(company_id,erhebung_id,id) DO UPDATE SET stufe=excluded.stufe,beleg=excluded.beleg,quelle=excluded.quelle,bewertet_am=excluded.bewertet_am""",
                (cid,eid,rid,key,pid,int(nr),int(v["stufe"]),v.get("beleg","").strip(),v.get("quelle","manuell"),now()))
    c.execute("UPDATE companies SET status='laeuft' WHERE "+KEY_CO+" AND status='neu'", (cid,))
    c.commit(); c.close(); return {"ok":True,"saved":len([1 for v in items.values() if v.get('stufe')])}

def _avg(rows):
    rows=[r for r in rows if r is not None]
    return round(sum(rows)/len(rows),2) if rows else 0

@app.get("/api/companies/{cid}/report")
def report(cid:str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
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
async def import_yaml(req: Request, _: Benutzer = Depends(admin)):
    """YAML-Import — Admins vorbehalten.

    Der Import legt einen neuen Mandanten an; es gilt dieselbe Begründung wie
    bei POST /api/companies.
    """
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
    # Der Import erzeugt die Ersterhebung des neuen Mandanten.
    eid = _erhebung_offen(c, cid)
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
                    c.execute("""INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES(?,?,?,?,?,?,?,?,?)
                                 ON CONFLICT(company_id,erhebung_id,id) DO UPDATE SET stufe=excluded.stufe,beleg=excluded.beleg,quelle=excluded.quelle,bewertet_am=excluded.bewertet_am""",
                        (cid, eid, rid, sid, nr, int(b["stufe"]), beleg, "yaml", now()))
                else:
                    c.execute("""INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES(?,?,?,?,?,?,?,?,?,?)
                                 ON CONFLICT(company_id,erhebung_id,id) DO UPDATE SET stufe=excluded.stufe,beleg=excluded.beleg,quelle=excluded.quelle,bewertet_am=excluded.bewertet_am""",
                        (cid, eid, rid, sid, pid, nr, int(b["stufe"]), beleg, "yaml", now()))
                nb += 1
    c.commit(); c.close()
    return {"ok": True, "id": cid, "prozesse": np_, "bewertungen": nb}

# ---------------- Beleg-Dokumente (Stufe 1: Upload & Ablage) ----------------
def _doc_public(d):
    d = dict(d); d.pop("storage_key", None); return d

@app.post("/api/companies/{cid}/documents")
async def upload_document(cid: str, ref_id: str = Form(...), file: UploadFile = File(...),
                          benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
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
def list_documents(cid: str, ref_id: str = None,
                   benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
    c = db()
    q = SEL_DOC + " WHERE " + W_CO; params = [cid]
    if ref_id:
        q += " AND ref_id=?"; params.append(ref_id)
    q += " ORDER BY uploaded_at DESC"
    rows = [_doc_public(r) for r in c.execute(q, tuple(params)).fetchall()]
    c.close(); return rows

@app.get("/api/companies/{cid}/documents/{doc_id}/file")
def get_document_file(cid: str, doc_id: str,
                      benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    pruefe_mandant(benutzer, cid)
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
def delete_document(cid: str, doc_id: str,
                    benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    # Anmerkung: Das Löschen ist hier noch für jeden Angemeldeten mit Zugriff auf
    # den Mandanten möglich. Die Beschränkung auf Admins kommt mit Etappe 4c,
    # zusammen mit dem Änderungsprotokoll — ein Löschrecht ohne Protokoll wäre
    # die schlechtere Hälfte der Lösung.
    pruefe_mandant(benutzer, cid)
    c = db()
    r = c.execute(SEL_DOC + " WHERE " + W_CO + " AND doc_id" + ("::text" if PG else "") + "=?", (cid, doc_id)).fetchone()
    if not r: c.close(); raise HTTPException(404, "Dokument unbekannt")
    delete_file(r["storage_key"])
    c.execute("DELETE FROM beleg_dokumente WHERE " + W_CO + " AND doc_id" + ("::text" if PG else "") + "=?", (cid, doc_id))
    c.commit(); c.close(); return {"ok": True}

# ---------------- Erhebungen (Schema v1.3 Teil C, seit 13.08.2026) ----------------
def _erhebung_offen(c, cid: str) -> str:
    """Die Erhebung, in die neue Bewertungen geschrieben werden.

    Es ist die juengste nicht verworfene. Gibt es noch keine, wird eine fuer den
    laufenden Monat angelegt. Damit muss niemand vor der ersten Bewertung daran
    denken — und trotzdem haengt jede Bewertung an einem Messzeitpunkt. Ohne
    diesen Bezug waere eine Gate-Freigabe nicht reproduzierbar, weil sich der
    Datenstand, auf den sie sich bezog, spaeter nicht mehr herstellen laesst.
    """
    zeile = c.execute(
        "SELECT erhebung_id FROM ref_erhebungen WHERE " + W_CO +
        " AND status<>'verworfen' ORDER BY stand DESC, erhebung_id DESC LIMIT 1",
        (cid,)).fetchone()
    if zeile:
        return zeile["erhebung_id"]
    heute = datetime.date.today()
    erhebung_id = "E-%04d-%02d" % (heute.year, heute.month)
    c.execute("INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status,methode) "
              "VALUES(?,?,?,?,?,?)",
              (cid, erhebung_id, "Erhebung %02d/%04d" % (heute.month, heute.year),
               _heute(), "offen",
               "Self-Rating je Teilprozess, 30 Bitkom-Items, Belegpflicht"))
    return erhebung_id


@app.get("/api/companies/{cid}/erhebungen")
def erhebungen(cid: str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Alle Erhebungen des Mandanten, dazu die Anzahl Bewertungen je Erhebung."""
    pruefe_mandant(benutzer, cid)
    c = db()
    try:
        zeilen = [dict(r) for r in c.execute(
            "SELECT e.erhebung_id, e.bezeichnung, "
            + ("e.stand::text AS stand" if PG else "e.stand") +
            ", e.status, e.methode, e.hinweis, "
            "(SELECT count(*) FROM bitkom_bewertungen b WHERE b.company_id=e.company_id "
            " AND b.erhebung_id=e.erhebung_id) AS bewertungen "
            "FROM ref_erhebungen e WHERE e." + W_CO +
            " ORDER BY e.stand DESC, e.erhebung_id DESC", (cid,)).fetchall()]
    finally:
        c.close()
    massgeblich = zeilen[0]["erhebung_id"] if zeilen else None
    for z in zeilen:
        z["bewertungen"] = int(z["bewertungen"])
    return {"erhebungen": zeilen, "massgeblich": massgeblich, "status_werte": ERHEBUNG_STATUS}


@app.post("/api/companies/{cid}/erhebungen")
async def erhebung_steuern(cid: str, req: Request,
                           benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Erhebung abschliessen oder eine neue beginnen.

    `abschliessen` setzt die offene Erhebung auf `abgeschlossen`. `neu` legt eine
    Erhebung fuer den laufenden Monat an — sie wird dadurch massgeblich, aendert
    aber erst etwas, sobald Bewertungen darin stehen: Der aktuelle Stand wird je
    Teilprozess und Item bestimmt, nicht je Mandant. Ein nicht nacherhobener
    Prozess behaelt also seinen bisherigen Wert.
    """
    pruefe_mandant(benutzer, cid)
    b = await req.json()
    aktion = (b.get("aktion") or "").strip()
    if aktion not in ("abschliessen", "neu", "verwerfen"):
        raise HTTPException(400, "Unbekannte Aktion: %s" % aktion)
    c = db()
    try:
        if aktion == "neu":
            heute = datetime.date.today()
            erhebung_id = "E-%04d-%02d" % (heute.year, heute.month)
            vorhanden = c.execute("SELECT status FROM ref_erhebungen WHERE " + W_CO +
                                  " AND erhebung_id=?", (cid, erhebung_id)).fetchone()
            if vorhanden:
                raise HTTPException(400, "Fuer diesen Monat gibt es bereits die Erhebung %s"
                                         % erhebung_id)
            c.execute("INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,"
                      "status,methode,hinweis) VALUES(?,?,?,?,?,?,?)",
                      (cid, erhebung_id,
                       (b.get("bezeichnung") or "Erhebung %02d/%04d" % (heute.month, heute.year)).strip(),
                       _heute(), "offen",
                       (b.get("methode") or "").strip() or None,
                       (b.get("hinweis") or "").strip() or None))
        else:
            ziel = "abgeschlossen" if aktion == "abschliessen" else "verworfen"
            erhebung_id = (b.get("erhebung_id") or "").strip()
            if not erhebung_id:
                zeile = c.execute("SELECT erhebung_id FROM ref_erhebungen WHERE " + W_CO +
                                  " AND status='offen' ORDER BY stand DESC LIMIT 1",
                                  (cid,)).fetchone()
                if not zeile:
                    raise HTTPException(400, "Es ist keine Erhebung offen")
                erhebung_id = zeile["erhebung_id"]
            c.execute("UPDATE ref_erhebungen SET status=? WHERE " + W_CO + " AND erhebung_id=?",
                      (ziel, cid, erhebung_id))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "erhebung_id": erhebung_id}


# ---------------- Rollen und Kostensaetze (Stammdaten, seit 11.08.2026) ----------------
def _heute():
    """Heutiges Datum im vom Backend erwarteten Typ."""
    heute = datetime.date.today()
    return heute if PG else heute.isoformat()


@app.get("/api/companies/{cid}/rollen_kosten")
def rollen_kosten(cid: str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Rollen des Mandanten und die aktuell gueltigen Kostensaetze je Klasse.

    Von den Kostensaetzen wird nur der jeweils juengste zurueckgegeben, dessen
    Gueltigkeit erreicht ist. Aeltere bleiben in der Tabelle — sie werden
    gebraucht, um eine frueher getroffene Freigabe nachvollziehen zu koennen.
    """
    pruefe_mandant(benutzer, cid)
    c = db()
    try:
        rollen = [dict(r) for r in c.execute(
            "SELECT rolle_id, bezeichnung, klasse, hinweis, aktiv FROM mandant_rollen "
            "WHERE " + W_CO + " ORDER BY rolle_id", (cid,)).fetchall()]
        saetze = [dict(r) for r in c.execute(
            "SELECT klasse, satz_eur_h, quelle, " + ("gueltig_ab::text AS gueltig_ab" if PG else "gueltig_ab") +
            ", bemerkung FROM rollen_kostensaetze WHERE " + W_CO +
            " AND gueltig_ab<=? ORDER BY klasse, gueltig_ab DESC", (cid, _heute())).fetchall()]
    finally:
        c.close()
    # Je Klasse nur den juengsten Satz behalten (die Liste ist absteigend sortiert).
    aktuell, gesehen = [], set()
    for s in saetze:
        if s["klasse"] in gesehen:
            continue
        gesehen.add(s["klasse"])
        s["satz_eur_h"] = float(s["satz_eur_h"])
        aktuell.append(s)
    for r in rollen:
        r["aktiv"] = bool(r["aktiv"]) and str(r["aktiv"]) != "0"
    return {"rollen": rollen,
            "kostensaetze": sorted(aktuell, key=lambda s: s["klasse"]),
            "klassen": [{"klasse": k, "bezeichnung": b} for k, b in KOSTENKLASSEN]}


@app.put("/api/companies/{cid}/rollen_kosten")
async def save_rollen_kosten(cid: str, req: Request,
                             benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Speichert Rollen und Kostensaetze.

    Zwei Eigenheiten, beide mit Absicht:

    **Rollen werden nicht geloescht, sondern auf `aktiv = false` gesetzt.** BC1
    speichert die `rolle_id` in seinem Prozessprofil; ein Verweis auf eine
    verschwundene Rolle waere nicht mehr aufloesbar. Dieselbe Ueberlegung wie bei
    Benutzern, die gesperrt statt geloescht werden.

    **Ein geaenderter Kostensatz erzeugt eine neue Zeile mit `gueltig_ab` heute**,
    statt die alte zu ueberschreiben. Nur so bleibt nachvollziehbar, mit welchem
    Satz eine frueher freigegebene Rechnung gearbeitet hat. Wird derselbe Satz
    mehrfach am selben Tag geaendert, wird die Tageszeile aktualisiert.
    """
    pruefe_mandant(benutzer, cid)
    b = await req.json()
    c = db()
    try:
        # ---- Rollen ----
        vorhanden = {r["rolle_id"] for r in c.execute(
            "SELECT rolle_id FROM mandant_rollen WHERE " + W_CO, (cid,)).fetchall()}
        gesendet = set()
        naechste = max([int(x.split("-")[1]) for x in vorhanden if "-" in x] or [0])

        for eintrag in b.get("rollen", []):
            bezeichnung = (eintrag.get("bezeichnung") or "").strip()
            if not bezeichnung:
                continue
            klasse = (eintrag.get("klasse") or "").strip()
            if klasse not in dict(KOSTENKLASSEN):
                raise HTTPException(400, "Unbekannte Kostenklasse: %s" % klasse)
            # Der Sperrstatus kommt aus der Oberflaeche, er wird nicht aus der
            # Anwesenheit in der Liste abgeleitet. Sonst wuerde jede gesperrte
            # Rolle beim naechsten Speichern wieder aktiv — die Sperre waere
            # nicht zu halten. (Gefunden im PostgreSQL-Durchlauf am 11.08.2026.)
            ist_aktiv = eintrag.get("aktiv", True) is not False
            aktiv_wert = ist_aktiv if PG else (1 if ist_aktiv else 0)
            rolle_id = (eintrag.get("rolle_id") or "").strip()
            if rolle_id and rolle_id in vorhanden:
                c.execute("UPDATE mandant_rollen SET bezeichnung=?, klasse=?, hinweis=?, aktiv=? "
                          "WHERE " + W_CO + " AND rolle_id=?",
                          (bezeichnung, klasse, eintrag.get("hinweis"),
                           aktiv_wert, cid, rolle_id))
            else:
                naechste += 1
                rolle_id = "R-%02d" % naechste
                c.execute("INSERT INTO mandant_rollen(company_id,rolle_id,bezeichnung,klasse,hinweis,aktiv) "
                          "VALUES(?,?,?,?,?,?)",
                          (cid, rolle_id, bezeichnung, klasse, eintrag.get("hinweis"),
                           aktiv_wert))
            gesendet.add(rolle_id)

        # Was gar nicht mitgeschickt wurde, wird gesperrt — nicht geloescht.
        # Das ist das Sicherheitsnetz fuer den Fall, dass eine Zeile in der
        # Oberflaeche entfernt wird.
        for verschwunden in vorhanden - gesendet:
            c.execute("UPDATE mandant_rollen SET aktiv=? WHERE " + W_CO + " AND rolle_id=?",
                      (False if PG else 0, cid, verschwunden))

        # ---- Kostensaetze ----
        for satz in b.get("kostensaetze", []):
            klasse = (satz.get("klasse") or "").strip()
            if klasse not in dict(KOSTENKLASSEN):
                raise HTTPException(400, "Unbekannte Kostenklasse: %s" % klasse)
            if satz.get("satz_eur_h") in (None, "", 0):
                continue
            try:
                wert = float(satz["satz_eur_h"])
            except (TypeError, ValueError):
                raise HTTPException(400, "Kostensatz fuer %s ist keine Zahl" % klasse)
            if wert <= 0:
                raise HTTPException(400, "Kostensatz fuer %s muss groesser als 0 sein" % klasse)
            quelle = (satz.get("quelle") or "geschaetzt").strip()
            if quelle not in KOSTEN_QUELLEN:
                raise HTTPException(400, "Unbekannte Quelle: %s" % quelle)
            c.execute(
                "INSERT INTO rollen_kostensaetze(company_id,klasse,satz_eur_h,quelle,gueltig_ab,bemerkung) "
                "VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(company_id,klasse,gueltig_ab) DO UPDATE SET "
                "satz_eur_h=excluded.satz_eur_h, quelle=excluded.quelle, bemerkung=excluded.bemerkung",
                (cid, klasse, wert, quelle, _heute(), satz.get("bemerkung")))
        c.commit()
    finally:
        c.close()
    return {"ok": True}


# ---------------- Entitaeten-Register: Personen und Systeme (ADR-004) ----------
# Grundregeln, alle vier aus ADR-004:
#   R2  IDs vergibt der Server fortlaufend. Die Oberflaeche schickt bei neuen
#       Objekten KEINE ID mit.
#   R3  IDs werden nie wiederverwendet. Der Zaehler laeuft ueber das Maximum der
#       vorhandenen IDs, nicht ueber die Anzahl — sonst bekaeme nach einer
#       Sperre die naechste Person eine bereits vergebene Nummer.
#   R4  Es wird gesperrt, nicht geloescht.
#   R5  Klarnamen stehen ausschliesslich in ref_personen.name.

def _naechste_nummer(vorhandene, praefix):
    """Hoechste vergebene Nummer + 1, ueber alle IDs der Form 'X-07'.

    Bewusst ueber das Maximum und nicht ueber die Anzahl: Wird P-03 gesperrt,
    bleibt P-03 belegt (ADR-004 R3). Ein zaehlerbasierter Ansatz wuerde die
    Nummer erneut vergeben, und ein alter Verweis aus BC1 zeigte danach auf eine
    andere Person als bei seiner Entstehung.
    """
    nummern = []
    for eintrag in vorhandene:
        teile = str(eintrag).split("-")
        if len(teile) == 2 and teile[0] == praefix and teile[1].isdigit():
            nummern.append(int(teile[1]))
    return max(nummern or [0]) + 1


def _wahr(wert):
    """Wahrheitswert im vom Backend erwarteten Typ."""
    return bool(wert) if PG else (1 if wert else 0)


@app.get("/api/companies/{cid}/entitaeten")
def entitaeten(cid: str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Personen, Systeme und die Zuordnung zu den Kernprozessen.

    Liefert zusaetzlich die Auswahllisten, damit die Oberflaeche keine zweite
    Werteliste fuehren muss: Rollen des Mandanten (fuer die Kostenklasse),
    Systemkatalog, Kernprozesse und die Beteiligungsarten.
    """
    pruefe_mandant(benutzer, cid)
    c = db()
    try:
        personen = [dict(r) for r in c.execute(
            "SELECT person_id, name, funktion, rolle_id, extern, organisation, hinweis, aktiv "
            "FROM ref_personen WHERE " + W_CO + " ORDER BY person_id", (cid,)).fetchall()]
        systeme = [dict(r) for r in c.execute(
            "SELECT system_id, katalog_id, bezeichnung, einsatz, hinweis, aktiv "
            "FROM mandant_systeme WHERE " + W_CO + " ORDER BY system_id", (cid,)).fetchall()]
        zuordnungen = [dict(r) for r in c.execute(
            "SELECT process_id, person_id, funktion FROM prozess_personen "
            "WHERE " + W_CO + " ORDER BY process_id, person_id, funktion", (cid,)).fetchall()]
        rollen = [dict(r) for r in c.execute(
            "SELECT rolle_id, bezeichnung, klasse FROM mandant_rollen "
            "WHERE " + W_CO + " AND aktiv" + ("" if PG else "=1") + " ORDER BY rolle_id",
            (cid,)).fetchall()]
        prozesse = [dict(r) for r in c.execute(
            "SELECT process_id, process_name FROM ref_prozesse WHERE " + W_CO +
            " ORDER BY process_id", (cid,)).fetchall()]
        katalog = [dict(r) for r in c.execute(
            "SELECT katalog_id, bezeichnung, kategorie, hersteller FROM ref_systeme_katalog "
            "ORDER BY kategorie, bezeichnung").fetchall()]
    finally:
        c.close()
    for p in personen:
        p["aktiv"] = bool(p["aktiv"]) and str(p["aktiv"]) != "0"
        p["extern"] = bool(p["extern"]) and str(p["extern"]) != "0"
    for s in systeme:
        s["aktiv"] = bool(s["aktiv"]) and str(s["aktiv"]) != "0"
    return {"personen": personen, "systeme": systeme, "zuordnungen": zuordnungen,
            "rollen": rollen, "prozesse": prozesse, "katalog": katalog,
            "beteiligungen": [{"wert": w, "bezeichnung": b} for w, b in BETEILIGUNGEN]}


@app.put("/api/companies/{cid}/entitaeten")
async def save_entitaeten(cid: str, req: Request,
                          benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Speichert Personen, Systeme und Zuordnungen.

    **Jeder Block ist einzeln optional.** Fehlt der Schluessel im Rumpf, wird der
    Block nicht angefasst. Ein PUT nur mit `personen` laesst Systeme und
    Zuordnungen unberuehrt. Sonst koennte ein Teilformular stillschweigend
    loeschen, was es gar nicht anzeigt.

    **Personen und Systeme werden gesperrt, nicht geloescht** (ADR-004 R4).
    Der Sperrstatus kommt ausdruecklich aus der Oberflaeche und wird nicht aus
    der Anwesenheit in der Liste abgeleitet — derselbe Fehler war am 11.08. bei
    den Rollen erst im PostgreSQL-Durchlauf aufgefallen.

    **Zuordnungen werden dagegen ersetzt.** Sie tragen keine eigene ID, auf die
    von aussen verwiesen wird; sie sind eine Aussage ueber den heutigen Stand.
    Ein `aktiv`-Merkmal waere hier ein Scheinnutzen.
    """
    pruefe_mandant(benutzer, cid)
    b = await req.json()
    erlaubte_beteiligung = dict(BETEILIGUNGEN)
    c = db()
    try:
        # ---- Personen ----
        if "personen" in b:
            vorhanden = {r["person_id"] for r in c.execute(
                "SELECT person_id FROM ref_personen WHERE " + W_CO, (cid,)).fetchall()}
            bekannte_rollen = {r["rolle_id"] for r in c.execute(
                "SELECT rolle_id FROM mandant_rollen WHERE " + W_CO, (cid,)).fetchall()}
            naechste = _naechste_nummer(vorhanden, "P")
            gesendet = set()

            for eintrag in b["personen"]:
                name = (eintrag.get("name") or "").strip() or None
                funktion = (eintrag.get("funktion") or "").strip() or None
                # Mindestens eines von beiden. Unbenannte Externe („externer
                # Steuerberater") bekommen eine ID ueber die Funktion — ohne sie
                # ginge der Verweis aus dem Prozess verloren.
                if not name and not funktion:
                    continue
                rolle_id = (eintrag.get("rolle_id") or "").strip() or None
                if rolle_id and rolle_id not in bekannte_rollen:
                    raise HTTPException(400, "Unbekannte Rolle: %s" % rolle_id)
                ist_aktiv = eintrag.get("aktiv", True) is not False
                person_id = (eintrag.get("person_id") or "").strip()
                werte = (name, funktion, rolle_id, _wahr(eintrag.get("extern")),
                         (eintrag.get("organisation") or "").strip() or None,
                         (eintrag.get("hinweis") or "").strip() or None,
                         _wahr(ist_aktiv))
                if person_id and person_id in vorhanden:
                    c.execute("UPDATE ref_personen SET name=?, funktion=?, rolle_id=?, extern=?, "
                              "organisation=?, hinweis=?, aktiv=? WHERE " + W_CO + " AND person_id=?",
                              werte + (cid, person_id))
                else:
                    person_id = "P-%02d" % naechste
                    naechste += 1
                    c.execute("INSERT INTO ref_personen(name,funktion,rolle_id,extern,organisation,"
                              "hinweis,aktiv,company_id,person_id) VALUES(?,?,?,?,?,?,?,?,?)",
                              werte + (cid, person_id))
                gesendet.add(person_id)

            for verschwunden in vorhanden - gesendet:
                c.execute("UPDATE ref_personen SET aktiv=? WHERE " + W_CO + " AND person_id=?",
                          (_wahr(False), cid, verschwunden))

        # ---- Systeme ----
        if "systeme" in b:
            vorhanden = {r["system_id"] for r in c.execute(
                "SELECT system_id FROM mandant_systeme WHERE " + W_CO, (cid,)).fetchall()}
            katalog = {r["katalog_id"] for r in c.execute(
                "SELECT katalog_id FROM ref_systeme_katalog").fetchall()}
            naechste = _naechste_nummer(vorhanden, "S")
            gesendet = set()

            for eintrag in b["systeme"]:
                bezeichnung = (eintrag.get("bezeichnung") or "").strip()
                if not bezeichnung:
                    continue
                katalog_id = (eintrag.get("katalog_id") or "").strip() or None
                # Der Katalogverweis ist optional. „Strategie-Cockpit" benennt
                # eine Gattung, kein Produkt — solche Eintraege bleiben katalogfrei.
                if katalog_id and katalog_id not in katalog:
                    raise HTTPException(400, "Unbekanntes System im Katalog: %s" % katalog_id)
                ist_aktiv = eintrag.get("aktiv", True) is not False
                werte = (katalog_id, bezeichnung,
                         (eintrag.get("einsatz") or "").strip() or None,
                         (eintrag.get("hinweis") or "").strip() or None,
                         _wahr(ist_aktiv))
                system_id = (eintrag.get("system_id") or "").strip()
                if system_id and system_id in vorhanden:
                    c.execute("UPDATE mandant_systeme SET katalog_id=?, bezeichnung=?, einsatz=?, "
                              "hinweis=?, aktiv=? WHERE " + W_CO + " AND system_id=?",
                              werte + (cid, system_id))
                else:
                    system_id = "S-%02d" % naechste
                    naechste += 1
                    c.execute("INSERT INTO mandant_systeme(katalog_id,bezeichnung,einsatz,hinweis,"
                              "aktiv,company_id,system_id) VALUES(?,?,?,?,?,?,?)",
                              werte + (cid, system_id))
                gesendet.add(system_id)

            for verschwunden in vorhanden - gesendet:
                c.execute("UPDATE mandant_systeme SET aktiv=? WHERE " + W_CO + " AND system_id=?",
                          (_wahr(False), cid, verschwunden))

        # ---- Zuordnung Person <-> Kernprozess ----
        if "zuordnungen" in b:
            bekannte_personen = {r["person_id"] for r in c.execute(
                "SELECT person_id FROM ref_personen WHERE " + W_CO, (cid,)).fetchall()}
            bekannte_prozesse = {r["process_id"] for r in c.execute(
                "SELECT process_id FROM ref_prozesse WHERE " + W_CO, (cid,)).fetchall()}
            neu = []
            for eintrag in b["zuordnungen"]:
                process_id = (eintrag.get("process_id") or "").strip()
                person_id = (eintrag.get("person_id") or "").strip()
                funktion = (eintrag.get("funktion") or "").strip()
                if not (process_id and person_id and funktion):
                    continue
                if process_id not in bekannte_prozesse:
                    raise HTTPException(400, "Unbekannter Prozess: %s" % process_id)
                if person_id not in bekannte_personen:
                    raise HTTPException(400, "Unbekannte Person: %s" % person_id)
                if funktion not in erlaubte_beteiligung:
                    raise HTTPException(400, "Unbekannte Beteiligung: %s" % funktion)
                neu.append((cid, process_id, person_id, funktion))
            # Erst pruefen, dann loeschen. Andernfalls stuende die Tabelle nach
            # einem abgewiesenen Eintrag leer da.
            c.execute("DELETE FROM prozess_personen WHERE " + W_CO, (cid,))
            for zeile in set(neu):
                c.execute("INSERT INTO prozess_personen(company_id,process_id,person_id,funktion) "
                          "VALUES(?,?,?,?)", zeile)
        c.commit()
    finally:
        c.close()
    return {"ok": True}


# ---------------- Gate 0: Freigabebogen (Schema v1.4, seit 17.08.2026) ----------
# ALLES IN DIESEM ABSCHNITT IST ADMINISTRATOREN VORBEHALTEN (Depends(admin)).
# Die Freigabe an BC2 loest den nachgelagerten Kontext aus und betrifft das ganze
# Unternehmen; sie ist keine Pflegehandlung. Benutzer.darf_freigeben sagt dasselbe.
#
# KEIN ZUGRIFF AUF DIE POSTGRESQL-SICHTEN (v_gate_bogen, v_gate_freigabe_aktuell,
# v_gate_vorbedingungen). Sie gibt es im SQLite-Entwicklungsmodus nicht, und eine
# Oberflaeche, die nur gegen ein Backend laeuft, waere im zweiten nicht zu testen.
# Die Abfragen stehen deshalb als portables SQL hier — dasselbe Vorgehen wie bei
# _bew_aktuell(), das die View v_bewertung_aktuell nachbildet.

def _jetzt():
    """Aktueller Zeitpunkt im vom Backend erwarteten Typ."""
    return datetime.datetime.now(datetime.timezone.utc) if PG else now()


def _gate_teilprozesse(c, cid, sub_process_id=None):
    """Teilprozesse des Mandanten mit dem Namen ihres Kernprozesses."""
    sql = ("SELECT t.sub_process_id, t.process_id, t.sub_process_name, p.process_name "
           "FROM ref_teilprozesse t JOIN ref_prozesse p "
           "ON p.company_id=t.company_id AND p.process_id=t.process_id WHERE t." + W_CO)
    werte = [cid]
    if sub_process_id:
        sql += " AND t.sub_process_id=?"; werte.append(sub_process_id)
    return c.execute(sql + " ORDER BY t.process_id, t.step_no", tuple(werte)).fetchall()


def _gate_beteiligungen(c, cid):
    """Je Kernprozess: ist ein Eigner benannt, ist ein Ansprechpartner benannt.

    Beides haengt am Kernprozess und wird an den Teilprozess vererbt. Ein eigener
    Eigner je Teilprozess waere eine Genauigkeit, die es in der Wirklichkeit nicht
    gibt.
    """
    eigner, ansprechpartner = set(), set()
    for r in c.execute("SELECT process_id, funktion FROM prozess_personen WHERE " + W_CO,
                       (cid,)).fetchall():
        if r["funktion"] == "eigner":
            eigner.add(r["process_id"])
        elif r["funktion"] in GATE_ANSPRECHPARTNER:
            ansprechpartner.add(r["process_id"])
    return eigner, ansprechpartner


def _gate_reifegrade(c, cid):
    """Je Teilprozess: Anzahl bewerteter Items und Mittelwert der Stufen.

    Gerechnet wird auf dem massgeblichen Stand (_bew_aktuell), nicht auf allen
    Zeilen — sonst mittelte der Reifegrad ueber mehrere Erhebungen hinweg.
    """
    zeilen = c.execute("SELECT sub_process_id, COUNT(*) AS n_items, AVG(stufe) AS avg_stufe FROM "
                       + _bew_aktuell("company_id,sub_process_id,item_nr,stufe")
                       + " WHERE " + W_CO + " GROUP BY sub_process_id", (cid,)).fetchall()
    return {r["sub_process_id"]: (int(r["n_items"]),
                                  float(r["avg_stufe"]) if r["avg_stufe"] is not None else None)
            for r in zeilen}


def _gate_werte(c, ereignis_ids):
    """Die erfassten Pruefpunkte je Ereignis."""
    if not ereignis_ids:
        return {}
    platz = ",".join(["?"] * len(ereignis_ids))
    ergebnis = {}
    for r in c.execute("SELECT ereignis_id, pruefpunkt, vorhanden_pct, guete, bestaetigt, anmerkung "
                       "FROM gate_pruefpunkt_werte WHERE ereignis_id IN (" + platz + ") "
                       "ORDER BY pruefpunkt", tuple(ereignis_ids)).fetchall():
        eintrag = dict(r)
        eintrag["vorhanden_pct"] = (None if eintrag["vorhanden_pct"] is None
                                    else float(eintrag["vorhanden_pct"]))
        eintrag["bestaetigt"] = bool(eintrag["bestaetigt"])
        ergebnis.setdefault(r["ereignis_id"], []).append(eintrag)
    return ergebnis


def _gate_hinweis(ereignis, werte):
    """Was BC2 aus der Guete folgt — Ableitung, keine Vorschrift.

    Wortgleich mit v_gate_freigabe_aktuell.hinweis_an_bc2, damit beide Wege
    dieselbe Auskunft geben.
    """
    if ereignis != "freigegeben":
        return "nicht freigegeben"
    gueten = {w["guete"] for w in werte}
    if "geraten" in gueten:
        return "Bandbreite rechnen — mindestens eine Angabe ist geraten"
    if "geschaetzt" in gueten:
        return "Bandbreite empfohlen — mindestens eine Angabe ist geschaetzt"
    return "Punktwert vertretbar — alle rechnungsrelevanten Angaben belegt"


def _gate_letzter_stand(c, cid, sub_process_id=None):
    """Je Teilprozess die juengste Entscheidung, samt ihrer Pruefpunkte.

    Eine Freigabe ist ein Ereignis, keine Eigenschaft: Der aktuelle Stand ist die
    juengste Zeile, nichts wird ueberschrieben (ADR-003).
    """
    innen = ("SELECT g.*, row_number() OVER (PARTITION BY g.objekt_id "
             "ORDER BY g.am DESC, g.ereignis_id DESC) AS rang FROM gate_ereignisse g "
             "WHERE g.gate='bc0-bc2' AND g.objekt_typ='teilprozess' AND g." + W_CO)
    werte = [cid]
    if sub_process_id:
        innen += " AND g.objekt_id=?"; werte.append(sub_process_id)
    zeilen = c.execute("SELECT objekt_id, ereignis_id, ereignis, benutzer_id, "
                       + ("am::text AS am" if PG else "am") +
                       ", anfrage_id, erhebung_id, bc1_profil_stand, kette_bestaetigt, "
                       "kette_ergaenzung, grund, massnahme FROM (" + innen + ") t WHERE rang=1",
                       tuple(werte)).fetchall()
    punkte = _gate_werte(c, [r["ereignis_id"] for r in zeilen])
    ergebnis = {}
    for r in zeilen:
        stand = dict(r)
        stand["stand"] = stand.pop("ereignis")
        stand["entschieden_am"] = stand.pop("am")
        stand["kette_bestaetigt"] = (None if stand["kette_bestaetigt"] is None
                                     else bool(stand["kette_bestaetigt"]))
        stand["punkte"] = punkte.get(r["ereignis_id"], [])
        stand["hinweis_an_bc2"] = _gate_hinweis(stand["stand"], stand["punkte"])
        ergebnis[r["objekt_id"]] = stand
    return ergebnis


def _bc1_angaben(c, cid, sub_process_id):
    """Die BC1-Anreicherung zu einem Teilprozess — heute immer None.

    HIER WIRD ANGESCHLOSSEN, sobald Richard die vier Feldnamen (Dauer,
    Haeufigkeit, Menge, Rollen mit Zeitanteil) und die Profil-Version benannt hat.
    Bis dahin gibt es keine lesbare BC1-Quelle; ein geratenes Schema waere eine
    Behauptung ueber fremde Daten und schlimmer als keine Angabe.

    Solange None zurueckkommt, ist `entscheiden` nicht erreichbar. Das ist die
    Wahrheit ueber den Projektstand, kein Mangel dieser Funktion.
    """
    return None


def _gate_luecken(zeile):
    """Die offenen Vorbedingungen einer Bogenzeile als (art, text)-Paare.

    Getrennt von _gate_fehlende_vorbedingungen(): Dort steht der Wortlaut, mit dem
    der Server eine Freigabe abweist — hier der kurze, der in einer Liste mit
    fuenfzig Zeilen noch lesbar ist.
    """
    luecken = []
    if not zeile["eigner_benannt"]:
        luecken.append(("eigner", "Eigner fehlt"))
    if not zeile["ansprechpartner_benannt"]:
        luecken.append(("ansprechpartner", "Ansprechpartner fehlt"))
    if not zeile["vollstaendig_bewertet"]:
        luecken.append(("bewertung", "Bewertung unvollstaendig: %d von %d Items"
                        % (zeile["items_bewertet"], GATE_ITEMS_MIN)))
    return luecken


def _gate_am_zug(zeile, bc1):
    """Wer am Zug ist — vier Werte in fester Pruefreihenfolge, samt Begruendung.

    Die Reihenfolge ist die Aussage: Was entschieden ist, bleibt entschieden, auch
    wenn spaeter eine Vorbedingung wegfaellt. Und was BC0 selbst nachtragen kann,
    steht vor dem, worauf BC0 nur warten kann.

    `wartet_bc1` SPERRT NICHTS. Der Bogen bleibt oeffenbar, sobald die
    Vorbedingungen stimmen, und eine Freigabe bleibt moeglich — der Admin kann die
    BC1-Punkte auf `entfaellt` setzen. Der Zustand steuert allein die
    Einsortierung in der Liste.
    """
    if zeile["stand"] in GATE_EREIGNISSE:
        return "entschieden", "Entschieden: " + zeile["stand"]
    luecken = _gate_luecken(zeile)
    if luecken:
        return "bc0_pflege", ", ".join(t for _art, t in luecken)
    if bc1 is None:
        return "wartet_bc1", "Anreicherung fehlt: " + ", ".join(GATE_BC1_FELDER)
    return "entscheiden", "Vorbedingungen erfuellt, BC1-Angaben liegen vor"


#: Der Wortlaut je Art. Steht am Kernprozess, nicht am Teilprozess — deshalb ohne
#: Zahl im Text; die Zahl der betroffenen Teilprozesse steht daneben.
GATE_HINDERNIS_TEXT = {
    "eigner": "Kein Prozesseigner benannt",
    "ansprechpartner": "Kein Ansprechpartner fuer Rueckfragen benannt",
    "bewertung": "Selbsteinschaetzung unvollstaendig (mindestens %d von 30 Items je "
                 "Teilprozess)" % GATE_ITEMS_MIN,
}


def _gate_hindernisse(zeilen):
    """Die offenen Vorbedingungen, gruppiert nach Kernprozess und Art.

    NICHT je Teilprozess: Eigner und Ansprechpartner haengen am Kernprozess und
    werden an seine fuenf Teilprozesse vererbt. Je Teilprozess aufgefuehrt stuende
    derselbe Satz fuenfzig Mal statt zehn Mal — eine Liste, die niemand liest.

    Gezaehlt wird nur, was auch wirklich blockiert (am_zug='bc0_pflege'). Ein
    entschiedener Teilprozess wartet auf nichts mehr, und ein Nachtrag daran
    aenderte die Entscheidung nicht.
    """
    gruppen = {}
    for z in zeilen:
        if z["am_zug"] != "bc0_pflege":
            continue
        for art, _text in _gate_luecken(z):
            eintrag = gruppen.get((z["process_id"], art))
            if eintrag is None:
                eintrag = gruppen[(z["process_id"], art)] = {
                    "process_id": z["process_id"], "process_name": z["process_name"],
                    "art": art, "text": GATE_HINDERNIS_TEXT[art], "betroffen": 0}
            eintrag["betroffen"] += 1
    return [gruppen[s] for s in sorted(gruppen,
                                       key=lambda s: (s[0], GATE_HINDERNIS_ARTEN.index(s[1])))]


def _gate_bogen(c, cid, sub_process_id=None):
    """Vorbelegung des Bogens je Teilprozess: Vorbedingungen, Reifegrad, Stand."""
    eigner, ansprechpartner = _gate_beteiligungen(c, cid)
    reifegrade = _gate_reifegrade(c, cid)
    staende = _gate_letzter_stand(c, cid, sub_process_id)
    ausgabe = []
    for t in _gate_teilprozesse(c, cid, sub_process_id):
        items, mittel = reifegrade.get(t["sub_process_id"], (0, None))
        hat_eigner = t["process_id"] in eigner
        hat_ansprechpartner = t["process_id"] in ansprechpartner
        vollstaendig = items >= GATE_ITEMS_MIN
        stand = staende.get(t["sub_process_id"])
        zeile = {
            "sub_process_id": t["sub_process_id"], "process_id": t["process_id"],
            "sub_process_name": t["sub_process_name"], "process_name": t["process_name"],
            "eigner_benannt": hat_eigner, "ansprechpartner_benannt": hat_ansprechpartner,
            "items_bewertet": items, "vollstaendig_bewertet": vollstaendig,
            "reifegrad": (None if mittel is None else round(mittel, 2)),
            "ueber_schwelle": (mittel is not None and mittel >= GATE_SCHWELLE),
            "bogen_ausfuellbar": hat_eigner and hat_ansprechpartner and vollstaendig,
            "stand": stand["stand"] if stand else None,
            "entschieden_am": stand["entschieden_am"] if stand else None,
            "hinweis_an_bc2": stand["hinweis_an_bc2"] if stand else None,
        }
        zeile["am_zug"], zeile["am_zug_grund"] = _gate_am_zug(
            zeile, _bc1_angaben(c, cid, t["sub_process_id"]))
        ausgabe.append(zeile)
    return ausgabe


def _gate_mandant(c, cid):
    """Mandant vorhanden? Sonst 404.

    pruefe_mandant() genuegt hier nicht: Ein Admin darf alle Mandanten sehen, also
    auch solche, die es nicht gibt. Die Verbindung schliesst der Aufrufer im
    finally-Zweig.
    """
    if not c.execute(SEL_CO + " WHERE " + KEY_CO, (cid,)).fetchone():
        raise HTTPException(404, "Mandant unbekannt.")


def _gate_fehlende_vorbedingungen(zeile):
    fehlt = []
    if not zeile["eigner_benannt"]:
        fehlt.append("kein Prozesseigner benannt")
    if not zeile["ansprechpartner_benannt"]:
        fehlt.append("kein Ansprechpartner fuer Rueckfragen benannt")
    if not zeile["vollstaendig_bewertet"]:
        fehlt.append("nur %d von 30 Items bewertet (mindestens %d noetig)"
                     % (zeile["items_bewertet"], GATE_ITEMS_MIN))
    return fehlt


@app.get("/api/companies/{cid}/gate")
def gate_liste(cid: str, benutzer: Benutzer = Depends(admin)):
    """Alle Teilprozesse mit Vorbedingungen, Reifegrad, letztem Stand und Zustand.

    Sortiert nach GATE_AM_ZUG: Die Liste beantwortet damit nicht mehr nur „was
    gibt es?", sondern „was ist jetzt zu tun?". Innerhalb eines Zustands nach
    Teilprozess-ID, damit die Reihenfolge zwischen zwei Aufrufen stabil bleibt.
    """
    pruefe_mandant(benutzer, cid)
    c = db()
    try:
        _gate_mandant(c, cid)
        zeilen = _gate_bogen(c, cid)
    finally:
        c.close()
    zeilen.sort(key=lambda z: (GATE_AM_ZUG.index(z["am_zug"]), z["sub_process_id"]))
    return {"teilprozesse": zeilen, "hindernisse": _gate_hindernisse(zeilen),
            "schwelle": GATE_SCHWELLE, "items_min": GATE_ITEMS_MIN}


@app.get("/api/companies/{cid}/gate/{sub_process_id}")
def gate_bogen(cid: str, sub_process_id: str, benutzer: Benutzer = Depends(admin)):
    """Ein Freigabebogen: Vorbedingungen, Prozesskette, Pruefpunkte, letzter Stand.

    Die Prozesskette wird angezeigt, nicht erfasst — sie steht bereits in
    prozess_schnittstellen. Ein drittes Mal erfasst hiesse: beim ersten Widerspruch
    weiss niemand, welche Fassung gilt.
    """
    pruefe_mandant(benutzer, cid)
    c = db()
    try:
        _gate_mandant(c, cid)
        zeilen = _gate_bogen(c, cid, sub_process_id)
        if not zeilen:
            raise HTTPException(404, "Teilprozess unbekannt.")
        bogen = zeilen[0]
        pid = bogen["process_id"]
        liefert_an = [r["nach_process_id"] for r in c.execute(
            "SELECT DISTINCT nach_process_id FROM prozess_schnittstellen WHERE " + W_CO +
            " AND von_process_id=? ORDER BY nach_process_id", (cid, pid)).fetchall()]
        empfaengt_von = [r["von_process_id"] for r in c.execute(
            "SELECT DISTINCT von_process_id FROM prozess_schnittstellen WHERE " + W_CO +
            " AND nach_process_id=? ORDER BY von_process_id", (cid, pid)).fetchall()]
        pruefpunkte = [dict(r) for r in c.execute(
            "SELECT pruefpunkt, bezeichnung, erlaeuterung, quelle_bc, guete_noetig, pflicht, "
            "reihenfolge FROM ref_gate_pruefpunkte WHERE aktiv" + ("" if PG else "=1") +
            " ORDER BY reihenfolge, pruefpunkt").fetchall()]
        stand = _gate_letzter_stand(c, cid, sub_process_id).get(sub_process_id)
        erhebung = c.execute("SELECT erhebung_id, bezeichnung, status FROM ref_erhebungen WHERE "
                             + W_CO + " AND status<>'verworfen' "
                             "ORDER BY stand DESC, erhebung_id DESC LIMIT 1", (cid,)).fetchone()
    finally:
        c.close()
    for p in pruefpunkte:
        p["guete_noetig"] = bool(p["guete_noetig"])
        p["pflicht"] = bool(p["pflicht"])
    bogen["kette"] = {"liefert_an": liefert_an, "empfaengt_von": empfaengt_von}
    bogen["pruefpunkte"] = pruefpunkte
    bogen["letzter_stand"] = stand
    bogen["erhebung"] = dict(erhebung) if erhebung else None
    bogen["gueten"] = GATE_GUETEN
    return bogen


@app.post("/api/companies/{cid}/gate/{sub_process_id}")
async def gate_entscheiden(cid: str, sub_process_id: str, req: Request,
                           benutzer: Benutzer = Depends(admin)):
    """Die Entscheidung schreiben — Ereignis und Pruefpunkte in EINER Transaktion.

    Ein halb geschriebener Pruefbogen haette keinen Beweiswert: Er behauptete eine
    Entscheidung, ohne zu belegen, worauf sie beruht. Deshalb wird erst vollstaendig
    geprueft und dann geschrieben.

    Die Erhebung wird als WERT kopiert, nicht als Verweis gespeichert. Ein Verweis
    wanderte mit — schriebe BC1 danach nach, behauptete die Freigabe rueckwirkend,
    etwas geprueft zu haben, das es damals nicht gab.
    """
    pruefe_mandant(benutzer, cid)
    b = await req.json()
    ereignis = (b.get("ereignis") or "").strip()
    if ereignis not in GATE_EREIGNISSE:
        raise HTTPException(400, "Unbekanntes Ereignis: %s" % (ereignis or "—"))
    grund = (b.get("grund") or "").strip()
    massnahme = (b.get("massnahme") or "").strip()
    if ereignis == "zurueckgewiesen":
        # Beide Pflichtfelder stehen auch als CHECK in der Datenbank. Hier steht
        # die lesbare Meldung — eine Verletzung der Bedingung waere ein 500er.
        if not grund:
            raise HTTPException(400, "Eine Zurueckweisung braucht eine Begruendung.")
        if not massnahme:
            raise HTTPException(400, "Eine Zurueckweisung braucht eine Massnahme: Was passiert jetzt?")
    if ereignis == "freigegeben":
        massnahme = ""   # freigegeben heisst, es ist nichts zu tun

    c = db()
    try:
        _gate_mandant(c, cid)
        zeilen = _gate_bogen(c, cid, sub_process_id)
        if not zeilen:
            raise HTTPException(404, "Teilprozess unbekannt.")
        bogen = zeilen[0]

        katalog = {r["pruefpunkt"]: dict(r) for r in c.execute(
            "SELECT pruefpunkt, guete_noetig, aktiv FROM ref_gate_pruefpunkte").fetchall()}
        gesendet = {}
        for punkt in (b.get("punkte") or []):
            name = (punkt.get("pruefpunkt") or "").strip()
            if name not in katalog:
                raise HTTPException(400, "Unbekannter Pruefpunkt: %s" % (name or "—"))
            if not katalog[name]["aktiv"]:
                raise HTTPException(400, "Pruefpunkt %s ist nicht aktiv und wird nicht bewertet." % name)
            if name in gesendet:
                raise HTTPException(400, "Pruefpunkt %s ist doppelt angegeben." % name)
            guete = (punkt.get("guete") or "").strip() or None
            if guete and guete not in GATE_GUETEN:
                raise HTTPException(400, "Unbekannte Guete bei %s: %s" % (name, guete))
            pct = punkt.get("vorhanden_pct")
            if pct in ("", None):
                pct = None
            else:
                try:
                    pct = float(pct)
                except (TypeError, ValueError):
                    raise HTTPException(400, "Befuellungsgrad bei %s ist keine Zahl" % name)
                if not 0 <= pct <= 100:
                    raise HTTPException(400, "Befuellungsgrad bei %s liegt nicht zwischen 0 und 100" % name)
            gesendet[name] = (pct, guete, _wahr(punkt.get("bestaetigt")),
                              (punkt.get("anmerkung") or "").strip() or None)

        if ereignis == "freigegeben":
            fehlt = _gate_fehlende_vorbedingungen(bogen)
            if fehlt:
                raise HTTPException(400, "Der Bogen ist nicht ausfuellbar: " + "; ".join(fehlt))
            # Guete dort erzwingen, wo der Katalog sie verlangt — und nur bei einer
            # Freigabe. Eine Zurueckweisung darf abbrechen, ohne jeden Punkt zu
            # bewerten. Ein gar nicht gesendeter Punkt traegt ebenfalls keine Guete.
            for name, eintrag in sorted(katalog.items()):
                if not (eintrag["aktiv"] and eintrag["guete_noetig"]):
                    continue
                if not gesendet.get(name, (None, None))[1]:
                    raise HTTPException(400, 'Pruefpunkt "%s" geht in die Rechnung ein und braucht '
                                             "bei einer Freigabe eine Guete "
                                             "(belegt/geschaetzt/geraten/entfaellt)." % name)

        anfrage_id = (b.get("anfrage_id") or "").strip() or None
        if anfrage_id and not c.execute("SELECT 1 AS da FROM ref_anfragen WHERE " + W_CO +
                                        " AND anfrage_id=?", (cid, anfrage_id)).fetchone():
            raise HTTPException(400, "Unbekannte Anfrage: %s" % anfrage_id)

        erhebung_id = _erhebung_offen(c, cid)
        felder = ("gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,am,anfrage_id,"
                  "erhebung_id,kette_bestaetigt,kette_ergaenzung,grund,massnahme")
        daten = ("bc0-bc2", cid, "teilprozess", sub_process_id, ereignis,
                 benutzer.benutzer_id, _jetzt(), anfrage_id, erhebung_id,
                 _wahr(b.get("kette_bestaetigt")),
                 (b.get("kette_ergaenzung") or "").strip() or None,
                 grund or None, massnahme or None)
        sql = "INSERT INTO gate_ereignisse(" + felder + ") VALUES(" + ",".join(["?"] * 13) + ")"
        if PG:
            ereignis_id = c.execute(sql + " RETURNING ereignis_id", daten).fetchone()["ereignis_id"]
        else:
            ereignis_id = c.execute(sql, daten).lastrowid
        for name in sorted(gesendet):
            pct, guete, bestaetigt, anmerkung = gesendet[name]
            c.execute("INSERT INTO gate_pruefpunkt_werte(ereignis_id,pruefpunkt,vorhanden_pct,"
                      "guete,bestaetigt,anmerkung) VALUES(?,?,?,?,?,?)",
                      (ereignis_id, name, pct, guete, bestaetigt, anmerkung))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "ereignis_id": ereignis_id, "erhebung_id": erhebung_id,
            "stand": ereignis}


@app.get("/api/companies/{cid}/anfragen")
def anfragen(cid: str, benutzer: Benutzer = Depends(admin)):
    """Die externen Anfragen an das CoE — der Ausloeser der Kette."""
    pruefe_mandant(benutzer, cid)
    c = db()
    try:
        _gate_mandant(c, cid)
        zeilen = [dict(r) for r in c.execute(
            "SELECT anfrage_id, originaltext, "
            + ("eingang_am::text AS eingang_am" if PG else "eingang_am") +
            ", eingang_weg, steller_id, hinweis FROM ref_anfragen WHERE " + W_CO +
            " ORDER BY anfrage_id DESC", (cid,)).fetchall()]
    finally:
        c.close()
    return {"anfragen": zeilen}


@app.post("/api/companies/{cid}/anfragen")
async def anfrage_anlegen(cid: str, req: Request, benutzer: Benutzer = Depends(admin)):
    """Eine Anfrage aufnehmen.

    Der `originaltext` wird nie veraendert — weder gekuerzt noch umformuliert noch
    zusammengefasst. Eine Zusammenfassung gehoert in `hinweis`. Nur der Wortlaut
    erlaubt am Ende der Kette die Pruefung, ob die Empfehlung von BC2 die gestellte
    Frage ueberhaupt beantwortet.

    Die ID vergibt der Server (ADR-004 R2) und verwendet sie nie wieder (R3): Der
    Zaehler laeuft ueber das Maximum der vergebenen Nummern des Jahres, nicht ueber
    ihre Anzahl.
    """
    pruefe_mandant(benutzer, cid)
    b = await req.json()
    originaltext = (b.get("originaltext") or "").strip()
    if not originaltext:
        raise HTTPException(400, "Der Originaltext der Anfrage fehlt.")
    c = db()
    try:
        _gate_mandant(c, cid)
        steller_id = (b.get("steller_id") or "").strip() or None
        if steller_id and not c.execute("SELECT 1 AS da FROM ref_personen WHERE " + W_CO +
                                        " AND person_id=?", (cid, steller_id)).fetchone():
            raise HTTPException(400, "Unbekannte Person: %s" % steller_id)
        jahr = datetime.date.today().year
        vorhandene = [r["anfrage_id"] for r in c.execute(
            "SELECT anfrage_id FROM ref_anfragen WHERE " + W_CO, (cid,)).fetchall()]
        nummern = [int(x.split("-")[2]) for x in vorhandene
                   if x.startswith("A-%04d-" % jahr) and x.split("-")[2].isdigit()]
        naechste = max(nummern or [0]) + 1
        if naechste > 99:
            raise HTTPException(400, "Fuer %d sind bereits 99 Anfragen vergeben." % jahr)
        anfrage_id = "A-%04d-%02d" % (jahr, naechste)
        eingang_am = (b.get("eingang_am") or "").strip()
        c.execute("INSERT INTO ref_anfragen(company_id,anfrage_id,originaltext,eingang_am,"
                  "eingang_weg,steller_id,hinweis,angelegt_am) VALUES(?,?,?,?,?,?,?,?)",
                  (cid, anfrage_id, originaltext, eingang_am or _heute(),
                   (b.get("eingang_weg") or "").strip() or None, steller_id,
                   (b.get("hinweis") or "").strip() or None, _jetzt()))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "anfrage_id": anfrage_id}


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
