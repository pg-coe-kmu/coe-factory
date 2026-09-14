# -*- coding: utf-8 -*-
"""Patch v2.9 fuer app.py — 04.09.2026. Setzt patch_v2.8.py voraus.

Vorher / Nachher: der Stand nach einer Erhebung (Schema v2.9).

  1. `_bew_aktuell(spalten, grenze)` — dieselbe Zusammensetzungsregel, wahlweise
     nur ueber die Erhebungen bis einschliesslich einer Grenze (stand, kennung).
     `_sel_bew(grenze)` baut SEL_BEW damit; ohne Grenze identisch zu SEL_BEW.
  2. `_erhebung_grenze(c, cid, kennung)` — prueft die Kennung (vorhanden, nicht
     verworfen) und sagt, ob der Stand nach ihr FEST ist (sie und alle davor
     nicht mehr offen).
  3. `GET …/report?bis=E-…` — der Bericht, gerechnet auf den Stand nach der
     Erhebung; `bis` im Ergebnis (mit `fest`). Ohne Parameter wie bisher.
  4. `GET …/report/vergleich?von=&bis=` — Vorher gegen Nachher: je Teilprozess,
     je Dimension, gesamt; Liste der geaenderten Items mit altem und neuem Wert.
  5. `GET …/erhebungen` — jede Erhebung traegt `rang` und `fest`.
"""
import io, sys

def lies(p):  return io.open(p, encoding="utf-8").read()
def schreib(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def ersetze(s, alt, neu, name):
    if s.count(alt) != 1:
        sys.exit("Anker nicht (eindeutig) gefunden: " + name)
    return s.replace(alt, neu, 1)

s = lies("app.py")
if "v2.9" in s:
    print("app.py: bereits gepatcht (v2.9)"); sys.exit(0)
if "_erhebung_kennung_neu" not in s:
    sys.exit("patch_v2.8.py zuerst.")

# 1. _bew_aktuell mit Grenze
s = ersetze(s,
    '''def _bew_aktuell(spalten: str) -> str:''',
    '''def _bew_aktuell(spalten: str, grenze=None) -> str:''', "_bew_aktuell Kopf")
s = ersetze(s,
    '''    return ("(SELECT " + spalten + " FROM (SELECT bb.*, row_number() OVER ("
            "PARTITION BY bb.company_id, bb.sub_process_id, bb.item_nr "
            "ORDER BY e.stand DESC, e.erhebung_id DESC) AS rang "
            "FROM bitkom_bewertungen bb JOIN ref_erhebungen e "
            "ON e.company_id = bb.company_id AND e.erhebung_id = bb.erhebung_id "
            "WHERE e.status <> 'verworfen') t WHERE rang = 1) AS bitkom_bewertungen")
''',
    '''    # v2.9: grenze = (stand, erhebung_id) — nur Erhebungen bis einschliesslich
    # dieser (dieselbe Ordnung wie die Fensterfunktion). Der "Stand nach X".
    # Beide Werte kommen aus ref_erhebungen (_erhebung_grenze) und werden hier
    # nach Form geprueft, bevor sie als Literal in den Text gehen — das Fragment
    # steht in Abfragen mit eigenen Parametern, ein Platzhalter mittendrin
    # verschoebe deren Reihenfolge.
    filter_ = ""
    if grenze:
        stand, kennung = grenze
        if not (re.match(r"^\\d{4}-\\d{2}-\\d{2}$", str(stand)) and re.match(r"^E-\\d{4}-\\d{2}(-\\d+)?$", kennung)):
            raise ValueError("Grenze hat nicht die erwartete Form: %r" % (grenze,))
        filter_ = (" AND (e.stand < '%s' OR (e.stand = '%s' AND e.erhebung_id <= '%s'))"
                   % (stand, stand, kennung))
    return ("(SELECT " + spalten + " FROM (SELECT bb.*, row_number() OVER ("
            "PARTITION BY bb.company_id, bb.sub_process_id, bb.item_nr "
            "ORDER BY e.stand DESC, e.erhebung_id DESC) AS rang "
            "FROM bitkom_bewertungen bb JOIN ref_erhebungen e "
            "ON e.company_id = bb.company_id AND e.erhebung_id = bb.erhebung_id "
            "WHERE e.status <> 'verworfen'" + filter_ + ") t WHERE rang = 1) AS bitkom_bewertungen")
''', "_bew_aktuell Rumpf")

# _sel_bew nach dem if/else-Block (vor init_db)
s = ersetze(s,
    '''def init_db():
    """Richtet die Datenbank ein. Wiederholbar, läuft bei jedem Start.''',
    '''def _sel_bew(grenze=None) -> str:
    """SEL_BEW, wahlweise auf den Stand nach einer Erhebung begrenzt (v2.9).
    Ohne Grenze wortgleich mit SEL_BEW — test_v29 prueft das."""
    if PG:
        return ("SELECT company_id::text AS company_id,erhebung_id,id,sub_process_id,"
                "left(sub_process_id,5) AS process_id,"
                "item_nr,stufe,beleg,quelle::text AS quelle,bewertet_am::text AS bewertet_am FROM "
                + _bew_aktuell("company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,"
                               "quelle,bewertet_am", grenze))
    return ("SELECT * FROM "
            + _bew_aktuell("company_id,erhebung_id,id,sub_process_id,process_id,item_nr,"
                           "stufe,beleg,quelle,bewertet_am", grenze))


def _erhebung_grenze(c, cid: str, kennung: str, was: str = "bis"):
    """Die Erhebung als Grenze eines Standes — geprueft, mit `fest` (v2.9).

    fest = diese und alle frueheren Erhebungen sind nicht mehr offen; dann
    kann sich der Stand nach ihr nicht mehr aendern. Verworfene tragen keinen
    Stand und sind keine Grenze.
    """
    kennung = (kennung or "").strip()
    if not kennung:
        raise HTTPException(400, "Parameter %s: eine Erhebungskennung (E-JJJJ-MM oder E-JJJJ-MM-N)." % was)
    zeilen = [dict(r) for r in c.execute(
        "SELECT erhebung_id, bezeichnung, status, " + ("stand::text AS stand" if PG else "stand") +
        " FROM ref_erhebungen WHERE " + W_CO + " ORDER BY stand, erhebung_id", (cid,)).fetchall()]
    treffer = [z for z in zeilen if z["erhebung_id"] == kennung]
    if not treffer:
        raise HTTPException(400, "Unbekannte Erhebung: %s" % kennung)
    z = treffer[0]
    if z["status"] == "verworfen":
        raise HTTPException(400, "Erhebung %s ist verworfen und traegt keinen Stand." % kennung)
    bis_hier = [x for x in zeilen if (x["stand"], x["erhebung_id"]) <= (z["stand"], z["erhebung_id"])]
    z["fest"] = all(x["status"] != "offen" for x in bis_hier)
    z["rang"] = len(bis_hier)
    return z


def init_db():
    """Richtet die Datenbank ein. Wiederholbar, läuft bei jedem Start.''', "_sel_bew/_erhebung_grenze")

# 3. report?bis=
s = ersetze(s,
    '''@app.get("/api/companies/{cid}/report")
def report(cid:str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):''',
    '''@app.get("/api/companies/{cid}/report")
def report(cid:str, bis: str = None, benutzer: Benutzer = Depends(angemeldeter_benutzer)):''',
    "report Kopf")
s = ersetze(s,
    '''    bew=[dict(r) for r in c.execute(SEL_BEW+" WHERE "+W_CO, (cid,)).fetchall()]
    procs=[dict(r) for r in c.execute(SEL_PROC+" WHERE "+W_CO+" ORDER BY process_id", (cid,)).fetchall()]
    # Dimension-Ø (Spider 5)''',
    '''    # v2.9: ?bis=E-… rechnet den Bericht auf den Stand NACH dieser Erhebung —
    # dieselbe Zusammensetzung, nur ueber die Erhebungen bis einschliesslich ihr.
    grenze = None
    if bis:
        try:
            grenze = _erhebung_grenze(c, cid, bis)
        except HTTPException:
            c.close(); raise
    sel = _sel_bew((grenze["stand"], grenze["erhebung_id"])) if grenze else SEL_BEW
    bew=[dict(r) for r in c.execute(sel+" WHERE "+W_CO, (cid,)).fetchall()]
    procs=[dict(r) for r in c.execute(SEL_PROC+" WHERE "+W_CO+" ORDER BY process_id", (cid,)).fetchall()]
    # Dimension-Ø (Spider 5)''', "report bew")
s = ersetze(s,
    '''         "schwelle":SCHWELLE,"erstellt_am":datetime.date.today().isoformat()}
''',
    '''         "schwelle":SCHWELLE,"erstellt_am":datetime.date.today().isoformat(),
         "bis":({"erhebung_id":grenze["erhebung_id"],"bezeichnung":grenze["bezeichnung"],
                 "stand":str(grenze["stand"]),"status":grenze["status"],"fest":bool(grenze["fest"])}
                if grenze else None)}   # v2.9
''', "report bis")

# 4. Vergleich
s = ersetze(s,
    '''    rep["texte"]=texte; rep["textfassung"]=fassung; rep["regelfassung"]=REGELFASSUNG
    rep["befund"]=befund
    return rep
''',
    '''    rep["texte"]=texte; rep["textfassung"]=fassung; rep["regelfassung"]=REGELFASSUNG
    rep["befund"]=befund
    return rep


@app.get("/api/companies/{cid}/report/vergleich")
def report_vergleich(cid: str, von: str = None, bis: str = None,
                     benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Vorher / Nachher (v2.9): der Stand nach `von` gegen den Stand nach `bis`.

    Je Teilprozess und je Dimension Mittelwert vorher, nachher, Differenz; dazu
    die Items, die sich geaendert haben, mit altem und neuem Wert. Ein Item, das
    im Vorher nicht bewertet war, zaehlt als "neu bewertet", nicht als geaendert.
    Dieselbe Rechnung liegt als reifegrad_vergleich() in der Datenbank
    (schema_v2.9) — dort die Regel fuer BC1–BC4, hier fuer den Bericht.
    """
    pruefe_mandant(benutzer, cid)
    c = db()
    try:
        g_von = _erhebung_grenze(c, cid, von, "von")
        g_bis = _erhebung_grenze(c, cid, bis, "bis")
        if (g_von["stand"], g_von["erhebung_id"]) >= (g_bis["stand"], g_bis["erhebung_id"]):
            raise HTTPException(400, "Vorher muss vor Nachher liegen: %s ist nicht vor %s."
                                     % (g_von["erhebung_id"], g_bis["erhebung_id"]))
        dim_of = {r["item_nr"]: r["dimension"] for r in c.execute("SELECT item_nr,dimension FROM ref_items").fetchall()}
        krit_of = {r["item_nr"]: r["kriterium"] for r in c.execute("SELECT item_nr,kriterium FROM ref_items").fetchall()}
        alt = {(r["sub_process_id"], r["item_nr"]): dict(r) for r in c.execute(
            _sel_bew((g_von["stand"], g_von["erhebung_id"])) + " WHERE " + W_CO, (cid,)).fetchall()}
        neu = {(r["sub_process_id"], r["item_nr"]): dict(r) for r in c.execute(
            _sel_bew((g_bis["stand"], g_bis["erhebung_id"])) + " WHERE " + W_CO, (cid,)).fetchall()}
        tps = {r["sub_process_id"]: dict(r) for r in c.execute(
            SEL_TP + " WHERE " + W_CO, (cid,)).fetchall()}
    finally:
        c.close()

    def _d(a, b):
        return round(b - a, 2) if (a is not None and b is not None) else None

    def _m(werte):
        # Kein Wert -> None, nicht 0: "vorher 0, Delta +3,2" taeuschte eine
        # Verbesserung vor, wo erstmals bewertet wurde (Befund NoroAI 04.09.).
        return _avg(werte) if werte else None

    tp_rows = []
    for sid in sorted(tps):
        va = [v["stufe"] for (s_, _n), v in alt.items() if s_ == sid]
        vn = [v["stufe"] for (s_, _n), v in neu.items() if s_ == sid]
        if not va and not vn:
            continue
        ge = sum(1 for k, v in neu.items() if k[0] == sid and k in alt and alt[k]["stufe"] != v["stufe"])
        nb = sum(1 for k in neu if k[0] == sid and k not in alt)
        tp_rows.append({"sub_process_id": sid, "process_id": tps[sid]["process_id"],
                        "name": tps[sid]["sub_process_name"],
                        "vorher": _m(va), "nachher": _m(vn), "delta": _d(_m(va), _m(vn)),
                        "geaendert": ge, "neu_bewertet": nb, "n_vorher": len(va), "n_nachher": len(vn)})
    dims = []
    for d in DIMS:
        va = [v["stufe"] for (_s, n), v in alt.items() if dim_of.get(n) == d]
        vn = [v["stufe"] for (_s, n), v in neu.items() if dim_of.get(n) == d]
        dims.append({"dimension": d, "vorher": _m(va), "nachher": _m(vn), "delta": _d(_m(va), _m(vn))})
    ga, gn = _m([v["stufe"] for v in alt.values()]), _m([v["stufe"] for v in neu.values()])
    items = []
    for k in sorted(neu, key=lambda x: (x[0], x[1])):
        a = alt.get(k)
        if a is None or a["stufe"] != neu[k]["stufe"]:
            items.append({"sub_process_id": k[0], "item_nr": k[1], "kriterium": krit_of.get(k[1]),
                          "alt": a["stufe"] if a else None, "neu": neu[k]["stufe"],
                          "erhebung_alt": a["erhebung_id"] if a else None,
                          "erhebung_neu": neu[k]["erhebung_id"], "beleg_neu": neu[k]["beleg"]})
    grenz = lambda g: {"erhebung_id": g["erhebung_id"], "bezeichnung": g["bezeichnung"],
                       "stand": str(g["stand"]), "status": g["status"], "fest": bool(g["fest"])}
    return {"von": grenz(g_von), "bis": grenz(g_bis), "fest": bool(g_von["fest"] and g_bis["fest"]),
            "gesamt": {"vorher": ga, "nachher": gn, "delta": _d(ga, gn)},
            "dimensionen": dims, "teilprozesse": tp_rows, "items": items,
            "n_geaendert": sum(1 for i in items if i["alt"] is not None),
            "n_neu_bewertet": sum(1 for i in items if i["alt"] is None)}
''', "vergleich")

# 5. GET erhebungen: rang + fest
s = ersetze(s,
    '''        offen = [z["erhebung_id"] for z in zeilen if z["status"] == "offen"]''',
    '''        # v2.9: Reihenfolge und "fest" (Stand nach dieser Erhebung unveraenderlich)
        reihe = sorted(zeilen, key=lambda z: (str(z["stand"]), z["erhebung_id"]))
        noch_offen = False
        for i, z in enumerate(reihe):
            noch_offen = noch_offen or z["status"] == "offen"
            z["rang"] = i + 1
            z["fest"] = (not noch_offen) and z["status"] != "verworfen"
        offen = [z["erhebung_id"] for z in zeilen if z["status"] == "offen"]''', "erhebungen rang/fest")

if "\nimport re\n" not in s and "import re," not in s and ", re\n" not in s and "import re " not in s:
    s = ersetze(s, "import io, sys", "import io, re, sys", "import re") if "import io, sys" in s else s
schreib("app.py", s)
print("app.py: gepatcht (v2.9)")
