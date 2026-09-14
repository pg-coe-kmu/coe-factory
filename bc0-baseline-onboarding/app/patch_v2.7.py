# -*- coding: utf-8 -*-
"""Patch v2.7 fuer app.py — 04.09.2026. Setzt patch_v2.6.py voraus.

  1. Status `uebergeben` zwischen am_gate und bewertet.
  2. anfrage_prozesse in beiden DDL-Bloecken (frische Installation, SQLite-Tests).
  3. Zuordnung n:m: PUT …/zuordnung nimmt `bezuege` (Liste) oder die alte
     Einzelform; POST …/anfragen legt den Hauptbezug auch in anfrage_prozesse an;
     GET …/anfragen liefert `bezuege` je Anfrage.
  4. Uebergabe je Anfrage (vollstaendig) oder als Portfolio mit Liste;
     GET …/uebergabe liefert je Anfrage soll/freigegeben/fehlend/uebergabefaehig.
"""
import io, sys

def lies(p):  return io.open(p, encoding="utf-8").read()
def schreib(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def ersetze(s, alt, neu, name):
    if s.count(alt) != 1:
        sys.exit("Anker nicht (eindeutig) gefunden: " + name)
    return s.replace(alt, neu, 1)

s = lies("app.py")
if "v2.7" in s:
    print("app.py: bereits gepatcht (v2.7)"); sys.exit(0)
if "_erhebung_massgeblich" not in s:
    sys.exit("patch_v2.6.py zuerst.")

# 1. Status
s = ersetze(s,
    'ANFRAGE_STATUS = ("eingegangen","zugeordnet","im_interview","am_gate",\n                  "bewertet","beauftragt","erledigt","abgelehnt")',
    'ANFRAGE_STATUS = ("eingegangen","zugeordnet","im_interview","am_gate","uebergeben",\n'
    '                  "bewertet","beauftragt","erledigt","abgelehnt")   # uebergeben: v2.7',
    "ANFRAGE_STATUS")

# 2. DDL — PG (nur Tabelle und Indizes; Trigger/Sichten kommen aus dem Schema-Skript)
s = ersetze(s,
    "CREATE TABLE IF NOT EXISTS ref_gate_pruefpunkte (\n  pruefpunkt     TEXT        PRIMARY KEY CHECK (pruefpunkt ~ '^[a-z_]{3,30}$'),",
    """CREATE TABLE IF NOT EXISTS anfrage_prozesse (
  bezug_id         BIGSERIAL PRIMARY KEY,
  company_id       UUID        NOT NULL,
  anfrage_id       TEXT        NOT NULL,
  process_id       VARCHAR(8)  NOT NULL,
  sub_process_id   VARCHAR(16),
  rolle            TEXT        NOT NULL DEFAULT 'beteiligt' CHECK (rolle IN ('haupt','beteiligt')),
  zuordnung_quelle TEXT        NOT NULL
                   CHECK (zuordnung_quelle IN ('anfrage','vorschlag_bc0','vorschlag_bc1','interview')),
  angelegt_am      TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (company_id, anfrage_id) REFERENCES ref_anfragen (company_id, anfrage_id) ON DELETE CASCADE,
  CHECK (sub_process_id IS NULL OR substr(sub_process_id, 1, length(process_id) + 1) = process_id || '.')
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ap_bezug
  ON anfrage_prozesse (company_id, anfrage_id, process_id, coalesce(sub_process_id, ''));
CREATE UNIQUE INDEX IF NOT EXISTS ux_ap_haupt
  ON anfrage_prozesse (company_id, anfrage_id) WHERE rolle = 'haupt';
CREATE TABLE IF NOT EXISTS ref_gate_pruefpunkte (
  pruefpunkt     TEXT        PRIMARY KEY CHECK (pruefpunkt ~ '^[a-z_]{3,30}$'),""",
    "DDL PG anfrage_prozesse")

# 2. DDL — SQLite
s = ersetze(s,
    "CREATE TABLE IF NOT EXISTS ref_gate_pruefpunkte(\n  pruefpunkt TEXT PRIMARY KEY, bezeichnung TEXT NOT NULL, erlaeuterung TEXT,",
    """CREATE TABLE IF NOT EXISTS anfrage_prozesse(
  bezug_id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id INTEGER NOT NULL, anfrage_id TEXT NOT NULL,
  process_id TEXT NOT NULL, sub_process_id TEXT,
  rolle TEXT NOT NULL DEFAULT 'beteiligt' CHECK (rolle IN ('haupt','beteiligt')),
  zuordnung_quelle TEXT NOT NULL, angelegt_am TEXT,
  CHECK (sub_process_id IS NULL OR substr(sub_process_id, 1, length(process_id) + 1) = process_id || '.'));
CREATE UNIQUE INDEX IF NOT EXISTS ux_ap_bezug
  ON anfrage_prozesse (company_id, anfrage_id, process_id, coalesce(sub_process_id, ''));
CREATE UNIQUE INDEX IF NOT EXISTS ux_ap_haupt
  ON anfrage_prozesse (company_id, anfrage_id) WHERE rolle = 'haupt';
CREATE TABLE IF NOT EXISTS ref_gate_pruefpunkte(
  pruefpunkt TEXT PRIMARY KEY, bezeichnung TEXT NOT NULL, erlaeuterung TEXT,""",
    "DDL SQLite anfrage_prozesse")

# 3a. Hilfsfunktion: Bezuege schreiben — vor den Anfrage-Endpunkten
HELFER = r'''
# ---------------- v2.7: Prozessbezuege n:m (anfrage_prozesse) ----------------
def _bezuege_lesen(c, cid, anfrage_id=None):
    """Die Bezuege je Anfrage, aus anfrage_prozesse. {anfrage_id: [ {...}, ... ]}"""
    sql = ("SELECT anfrage_id, process_id, sub_process_id, rolle, zuordnung_quelle "
           "FROM anfrage_prozesse WHERE " + W_CO)
    werte = [cid]
    if anfrage_id:
        sql += " AND anfrage_id=?"; werte.append(anfrage_id)
    sql += " ORDER BY anfrage_id, (rolle='haupt') DESC, process_id, sub_process_id"
    ergebnis = {}
    for r in c.execute(sql, tuple(werte)).fetchall():
        ergebnis.setdefault(r["anfrage_id"], []).append(
            {"process_id": r["process_id"], "sub_process_id": r["sub_process_id"],
             "rolle": r["rolle"], "zuordnung_quelle": r["zuordnung_quelle"]})
    return ergebnis


def _bezuege_schreiben(c, cid, anfrage_id, bezuege):
    """Ersetzt die Bezuege einer Anfrage. Genau ein Hauptbezug; er spiegelt sich in
    ref_anfragen (im PostgreSQL-Betrieb tut das auch der Trigger — doppelt haelt
    besser, und im SQLite-Modus gibt es den Trigger nicht).

    Prueft jeden Bezug gegen die Landkarte und sagt bei Fehlern, welcher.
    Gibt den Hauptbezug zurueck.
    """
    if not bezuege:
        raise HTTPException(400, "Mindestens ein Bezug ist noetig.")
    haupt = [b for b in bezuege if b.get("rolle") == "haupt"]
    if len(haupt) > 1:
        raise HTTPException(400, "Genau ein Hauptbezug je Anfrage — es sind %d." % len(haupt))
    if not haupt:
        bezuege[0]["rolle"] = "haupt"
    gesehen = set()
    for b in bezuege:
        pid = (b.get("process_id") or "").strip()
        sid = (b.get("sub_process_id") or "").strip() or None
        quelle = (b.get("zuordnung_quelle") or "").strip()
        if not pid:
            raise HTTPException(400, "Ein Bezug ohne Kernprozess ist keiner.")
        if quelle not in ZUORDNUNG_QUELLEN:
            raise HTTPException(400, "Unbekannte Zuordnungsquelle: %s" % (quelle or "(leer)"))
        if not c.execute("SELECT 1 AS da FROM ref_prozesse WHERE " + W_CO + " AND process_id=?",
                         (cid, pid)).fetchone():
            raise HTTPException(400, "Unbekannter Kernprozess: %s" % pid)
        if sid and not c.execute("SELECT 1 AS da FROM ref_teilprozesse WHERE " + W_CO +
                                 " AND sub_process_id=? AND process_id=?", (cid, sid, pid)).fetchone():
            raise HTTPException(400, "%s gehoert nicht zu %s." % (sid, pid))
        if (pid, sid) in gesehen:
            raise HTTPException(400, "Bezug doppelt: %s %s" % (pid, sid or ""))
        gesehen.add((pid, sid))
        b["process_id"], b["sub_process_id"], b["zuordnung_quelle"] = pid, sid, quelle
        b["rolle"] = "haupt" if b.get("rolle") == "haupt" else "beteiligt"
    c.execute("DELETE FROM anfrage_prozesse WHERE " + W_CO + " AND anfrage_id=?", (cid, anfrage_id))
    for b in bezuege:
        c.execute("INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,"
                  "rolle,zuordnung_quelle,angelegt_am) VALUES(?,?,?,?,?,?,?)",
                  (cid, anfrage_id, b["process_id"], b["sub_process_id"], b["rolle"],
                   b["zuordnung_quelle"], _jetzt()))
    h = [b for b in bezuege if b["rolle"] == "haupt"][0]
    c.execute("UPDATE ref_anfragen SET process_id=?,sub_process_id=?,zuordnung_quelle=? "
              "WHERE " + W_CO + " AND anfrage_id=?",
              (h["process_id"], h["sub_process_id"], h["zuordnung_quelle"], cid, anfrage_id))
    return h


'''
s = ersetze(s, '@app.get("/api/companies/{cid}/anfragen")\ndef anfragen(', HELFER + '@app.get("/api/companies/{cid}/anfragen")\ndef anfragen(', "Helfer einfuegen")

# 3b. GET anfragen: bezuege mitliefern
s = ersetze(s,
    '''            " FROM ref_anfragen WHERE " + W_CO +
            " ORDER BY anfrage_id DESC", (cid,)).fetchall()]
    finally:
        c.close()
    return {"anfragen": zeilen}''',
    '''            " FROM ref_anfragen WHERE " + W_CO +
            " ORDER BY anfrage_id DESC", (cid,)).fetchall()]
        bezuege = _bezuege_lesen(c, cid)                       # v2.7
    finally:
        c.close()
    for z in zeilen:
        z["bezuege"] = bezuege.get(z["anfrage_id"], [])
    return {"anfragen": zeilen}''', "GET anfragen bezuege")

# 3c. POST anfragen: Hauptbezug auch nach anfrage_prozesse
s = ersetze(s,
    '''                   (b.get("umfang_geschaetzt") or "").strip() or None))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "anfrage_id": anfrage_id, "status": "eingegangen",
            "process_id": process_id, "zuordnung_quelle": quelle}''',
    '''                   (b.get("umfang_geschaetzt") or "").strip() or None))
        if process_id:                                          # v2.7: Hauptbezug n:m
            c.execute("INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,"
                      "rolle,zuordnung_quelle,angelegt_am) VALUES(?,?,?,?,?,?,?)",
                      (cid, anfrage_id, process_id, sub_process_id, "haupt", quelle, _jetzt()))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "anfrage_id": anfrage_id, "status": "eingegangen",
            "process_id": process_id, "zuordnung_quelle": quelle}''', "POST anfragen haupt")

# 3d. PUT zuordnung: bezuege-Liste oder Einzelform
s = ersetze(s,
    '''    pruefe_mandant(benutzer, cid)
    b = await req.json()
    process_id = (b.get("process_id") or "").strip() or None
    sub_process_id = (b.get("sub_process_id") or "").strip() or None
    quelle = (b.get("zuordnung_quelle") or "").strip() or None

    if not process_id:
        raise HTTPException(400, "Ohne Kernprozess ist es keine Zuordnung.")''',
    '''    pruefe_mandant(benutzer, cid)
    b = await req.json()
    # v2.7: eine Anfrage betrifft x Kernprozesse und y Teilprozesse. Kommt eine
    # Liste `bezuege`, ersetzt sie alle Bezuege der Anfrage (genau ein Hauptbezug).
    # Die alte Einzelform setzt den Hauptbezug und laesst Beteiligte stehen.
    if isinstance(b.get("bezuege"), list):
        c = db()
        try:
            _gate_mandant(c, cid)
            if not c.execute("SELECT 1 AS da FROM ref_anfragen WHERE " + W_CO +
                             " AND anfrage_id=?", (cid, anfrage_id)).fetchone():
                raise HTTPException(404, "Unbekannte Anfrage: %s" % anfrage_id)
            haupt = _bezuege_schreiben(c, cid, anfrage_id, [dict(x) for x in b["bezuege"]])
            c.commit()
            zeile = c.execute("SELECT status FROM ref_anfragen WHERE " + W_CO +
                              " AND anfrage_id=?", (cid, anfrage_id)).fetchone()
            bezuege = _bezuege_lesen(c, cid, anfrage_id).get(anfrage_id, [])
        finally:
            c.close()
        return {"ok": True, "anfrage_id": anfrage_id, "process_id": haupt["process_id"],
                "sub_process_id": haupt["sub_process_id"], "zuordnung_quelle": haupt["zuordnung_quelle"],
                "bezuege": bezuege, "status": zeile["status"] if zeile else None}
    process_id = (b.get("process_id") or "").strip() or None
    sub_process_id = (b.get("sub_process_id") or "").strip() or None
    quelle = (b.get("zuordnung_quelle") or "").strip() or None

    if not process_id:
        raise HTTPException(400, "Ohne Kernprozess ist es keine Zuordnung.")''', "PUT zuordnung bezuege")

s = ersetze(s,
    '''        c.execute("UPDATE ref_anfragen SET process_id=?,sub_process_id=?,zuordnung_quelle=? "
                  "WHERE " + W_CO + " AND anfrage_id=?",
                  (process_id, sub_process_id, quelle, cid, anfrage_id))
        c.commit()
        zeile = c.execute("SELECT status FROM ref_anfragen WHERE " + W_CO +
                          " AND anfrage_id=?", (cid, anfrage_id)).fetchone()''',
    '''        c.execute("UPDATE ref_anfragen SET process_id=?,sub_process_id=?,zuordnung_quelle=? "
                  "WHERE " + W_CO + " AND anfrage_id=?",
                  (process_id, sub_process_id, quelle, cid, anfrage_id))
        # v2.7: der Hauptbezug in anfrage_prozesse; Beteiligte bleiben stehen.
        c.execute("DELETE FROM anfrage_prozesse WHERE " + W_CO + " AND anfrage_id=? AND rolle='haupt'",
                  (cid, anfrage_id))
        c.execute("DELETE FROM anfrage_prozesse WHERE " + W_CO + " AND anfrage_id=? AND process_id=? "
                  "AND coalesce(sub_process_id,'')=coalesce(?,'')", (cid, anfrage_id, process_id, sub_process_id))
        c.execute("INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,"
                  "rolle,zuordnung_quelle,angelegt_am) VALUES(?,?,?,?,?,?,?)",
                  (cid, anfrage_id, process_id, sub_process_id, "haupt", quelle, _jetzt()))
        c.commit()
        zeile = c.execute("SELECT status FROM ref_anfragen WHERE " + W_CO +
                          " AND anfrage_id=?", (cid, anfrage_id)).fetchone()''', "PUT zuordnung haupt n:m")

# 4a. GET uebergabe: Anfragen mit Sollstand
s = ersetze(s,
    '''    finally:
        c.close()
    return {"kandidaten": kandidaten, "pakete": list(pakete.values())}''',
    '''        anfragen = [dict(r) for r in c.execute(                    # v2.7
            "SELECT anfrage_id, status, soll, freigegeben, fehlend, vollstaendig, uebergabefaehig, "
            "letztes_paket_id::text AS letztes_paket_id, letzte_uebergabe_am::text AS letzte_uebergabe_am "
            "FROM v_anfrage_uebergabe_stand WHERE company_id=? AND status NOT IN ('erledigt','abgelehnt') "
            "ORDER BY anfrage_id", (cid,)).fetchall()]
    finally:
        c.close()
    for a in anfragen:
        a["soll"] = int(a["soll"]); a["freigegeben"] = int(a["freigegeben"])
        a["fehlend"] = list(a["fehlend"] or [])
        a["vollstaendig"] = bool(a["vollstaendig"]); a["uebergabefaehig"] = bool(a["uebergabefaehig"])
    # Portfolio-Kandidaten: freigegeben, in keinem Paket, ohne Anfrage.
    portfolio = [k for k in kandidaten if not k["anfrage_id"]]
    return {"anfragen": anfragen, "kandidaten": kandidaten, "portfolio": portfolio,
            "pakete": list(pakete.values())}''', "GET uebergabe anfragen")

# 4b. POST uebergabe: je Anfrage oder Portfolio-Liste
s = ersetze(s,
    '''    b = await req.json() if req.headers.get("content-length", "0") not in ("0", "") else {}
    hinweis = (b.get("hinweis") or "").strip() or None
    c = db()
    try:
        _gate_mandant(c, cid)
        try:
            paket = c.execute("SELECT gate_paket_schnueren(?, ?, ?)::text AS paket_id",
                              (cid, benutzer.benutzer_id, hinweis)).fetchone()["paket_id"]''',
    '''    b = await req.json() if req.headers.get("content-length", "0") not in ("0", "") else {}
    hinweis = (b.get("hinweis") or "").strip() or None
    anfrage_id = (b.get("anfrage_id") or "").strip() or None
    teilprozesse = [str(x).strip() for x in (b.get("teilprozesse") or []) if str(x).strip()]
    if not anfrage_id and not teilprozesse:
        raise HTTPException(400, "Entweder eine Anfrage (vollstaendig) oder eine ausdrueckliche "
                                 "Liste von Teilprozessen (Portfolio-Weg).")
    if anfrage_id and teilprozesse:
        raise HTTPException(400, "Entweder Anfrage oder Liste — nicht beides.")
    c = db()
    try:
        _gate_mandant(c, cid)
        try:
            # v2.7: je Anfrage nur vollstaendig; Portfolio mit Liste.
            paket = c.execute("SELECT gate_paket_schnueren(?, ?, ?, ?, ?)::text AS paket_id",
                              (cid, benutzer.benutzer_id, hinweis, anfrage_id,
                               teilprozesse or None)).fetchone()["paket_id"]''', "POST uebergabe")

schreib("app.py", s)
print("app.py: gepatcht (v2.7)")
