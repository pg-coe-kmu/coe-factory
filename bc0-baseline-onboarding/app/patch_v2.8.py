# -*- coding: utf-8 -*-
"""Patch v2.8 fuer app.py — 04.09.2026. Setzt patch_v2.7.py voraus.

Nacherhebung: mehrere Erhebungen je Monat (Schema v2.8).

  1. `_erhebung_kennung_neu()` — die naechste freie Kennung: E-JJJJ-MM, sonst
     E-JJJJ-MM-2, -3 … (dieselbe Regel wie erhebung_naechste_kennung() im Schema;
     hier auch fuer SQLite).
  2. `_erhebung_offen()` — nach dem Abschluss legt die naechste Bewertung die
     naechste Erhebung an ("Nacherhebung") statt mit 400 abzubrechen. Die
     abgeschlossene bleibt unveraendert: das ist die Sperre.
  3. `POST …/erhebungen` — Admin; `neu` nur, wenn keine offen ist (sonst 400 mit
     Satz), Kennung nach derselben Regel; `abschliessen`/`verwerfen` unveraendert.
  4. `GET …/erhebungen` — liefert `offen` (Kennung oder null) und `naechste`
     (die Kennung, die die naechste Erhebung bekaeme — immer, auch bei offener); `massgeblich`
     uebergeht verworfene (wie _erhebung_massgeblich()).
  5. `POST …/rating` — antwortet zusaetzlich mit `erhebung_id` und
     `erhebung_neu` (true, wenn dieser Aufruf die Erhebung angelegt hat), damit
     die Oberflaeche sagen kann, wohin geschrieben wurde.
"""
import io, sys

def lies(p):  return io.open(p, encoding="utf-8").read()
def schreib(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def ersetze(s, alt, neu, name):
    if s.count(alt) != 1:
        sys.exit("Anker nicht (eindeutig) gefunden: " + name)
    return s.replace(alt, neu, 1)

s = lies("app.py")
if "v2.8" in s:
    print("app.py: bereits gepatcht (v2.8)"); sys.exit(0)
if "_bezuege_schreiben" not in s:
    sys.exit("patch_v2.7.py zuerst.")

# 1 + 2. _erhebung_offen: Nacherhebung statt 400
s = ersetze(s,
    '''    heute = datetime.date.today()
    erhebung_id = "E-%04d-%02d" % (heute.year, heute.month)
    vorhanden = c.execute("SELECT status FROM ref_erhebungen WHERE " + W_CO +
                          " AND erhebung_id=?", (cid, erhebung_id)).fetchone()
    if vorhanden:
        c.close()
        raise HTTPException(400, "Die Erhebung %s ist %s und nimmt keine Bewertungen mehr an. "
                                 "Eine zweite Erhebung im selben Monat ist nicht darstellbar "
                                 "(Kennung E-JJJJ-MM)." % (erhebung_id, vorhanden["status"]))
    c.execute("INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status,methode) "
              "VALUES(?,?,?,?,?,?)",
              (cid, erhebung_id, "Erhebung %02d/%04d" % (heute.month, heute.year),
               _heute(), "offen",
               "Self-Rating je Teilprozess, 30 Bitkom-Items, Belegpflicht"))
    return erhebung_id
''',
    '''    # v2.8: Keine offene Erhebung — die naechste Bewertung legt die naechste an.
    # Nach einem Abschluss ist das eine Nacherhebung (E-JJJJ-MM-2, -3 …); die
    # abgeschlossene bleibt, wie sie war. Das ist die Sperre: nicht "niemand darf
    # bewerten", sondern "das Alte wird nicht ueberschrieben".
    erhebung_id, vorgaenger = _erhebung_kennung_neu(c, cid)
    heute = datetime.date.today()
    if vorgaenger:
        bezeichnung = "Nacherhebung %02d/%04d" % (heute.month, heute.year)
        hinweis = ("Automatisch angelegt: Bewertung nach Abschluss von %s. "
                   "Nur die hier bewerteten Items aendern den Stand." % vorgaenger)
    else:
        bezeichnung, hinweis = "Erhebung %02d/%04d" % (heute.month, heute.year), None
    c.execute("INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status,methode,hinweis) "
              "VALUES(?,?,?,?,?,?,?)",
              (cid, erhebung_id, bezeichnung, _heute(), "offen",
               "Self-Rating je Teilprozess, 30 Bitkom-Items, Belegpflicht", hinweis))
    return erhebung_id


def _erhebung_kennung_neu(c, cid: str):
    """Die naechste freie Erhebungskennung — und die Kennung der juengsten
    vorhandenen Erhebung dieses Monats (oder None).

    Regel (Schema v2.8, erhebung_naechste_kennung()): E-JJJJ-MM fuer die erste
    Erhebung des Monats, danach E-JJJJ-MM-2, -3 … Verworfene zaehlen mit — eine
    Kennung wird nie ein zweites Mal vergeben. Hier in Python, damit SQLite
    dieselbe Regel hat.
    """
    heute = datetime.date.today()
    basis = "E-%04d-%02d" % (heute.year, heute.month)
    zeilen = c.execute("SELECT erhebung_id FROM ref_erhebungen WHERE " + W_CO +
                       " AND (erhebung_id=? OR erhebung_id LIKE ?)",
                       (cid, basis, basis + "-%")).fetchall()
    if not zeilen:
        return basis, None
    hoechste, juengste = 1, basis
    for z in zeilen:
        rest = z["erhebung_id"][len(basis) + 1:]
        n = int(rest) if rest.isdigit() else 1
        if n >= hoechste:
            hoechste, juengste = n, z["erhebung_id"]
    return "%s-%d" % (basis, hoechste + 1), juengste
''', "_erhebung_offen v2.8")

# 4. GET erhebungen: offen + naechste
s = ersetze(s,
    '''    finally:
        c.close()
    massgeblich = zeilen[0]["erhebung_id"] if zeilen else None
    for z in zeilen:
        z["bewertungen"] = int(z["bewertungen"])
    return {"erhebungen": zeilen, "massgeblich": massgeblich, "status_werte": ERHEBUNG_STATUS}
''',
    '''        offen = [z["erhebung_id"] for z in zeilen if z["status"] == "offen"]
        # v2.8: die Kennung, die die naechste Erhebung bekaeme — immer berechnet,
        # auch bei offener; die Oberflaeche rechnet nichts selbst (Monat der
        # Anlage, nicht der offenen Kennung: E-2026-08 offen -> naechste E-2026-09).
        naechste = _erhebung_kennung_neu(c, cid)[0]
    finally:
        c.close()
    # v2.8: massgeblich = juengste NICHT verworfene — wie _erhebung_massgeblich().
    # Vorher stand hier zeilen[0], also auch eine verworfene.
    massgeblich = next((z["erhebung_id"] for z in zeilen if z["status"] != "verworfen"), None)
    for z in zeilen:
        z["bewertungen"] = int(z["bewertungen"])
    return {"erhebungen": zeilen, "massgeblich": massgeblich, "status_werte": ERHEBUNG_STATUS,
            "offen": offen[0] if offen else None, "naechste": naechste}
''', "GET erhebungen v2.8")

# 3. POST erhebungen: Admin, neu nur ohne offene, Kennung nach Regel
s = ersetze(s,
    '''@app.post("/api/companies/{cid}/erhebungen")
async def erhebung_steuern(cid: str, req: Request,
                           benutzer: Benutzer = Depends(angemeldeter_benutzer)):''',
    '''@app.post("/api/companies/{cid}/erhebungen")
async def erhebung_steuern(cid: str, req: Request,
                           benutzer: Benutzer = Depends(admin)):   # v2.8: BC0 entscheidet''',
    "POST erhebungen Kopf")
s = ersetze(s,
    '''        if aktion == "neu":
            heute = datetime.date.today()
            erhebung_id = "E-%04d-%02d" % (heute.year, heute.month)
            vorhanden = c.execute("SELECT status FROM ref_erhebungen WHERE " + W_CO +
                                  " AND erhebung_id=?", (cid, erhebung_id)).fetchone()
            if vorhanden:
                raise HTTPException(400, "Fuer diesen Monat gibt es bereits die Erhebung %s"
                                         % erhebung_id)
            c.execute(''',
    '''        if aktion == "neu":
            heute = datetime.date.today()
            offen = c.execute("SELECT erhebung_id FROM ref_erhebungen WHERE " + W_CO +
                              " AND status='offen' ORDER BY stand DESC, erhebung_id DESC LIMIT 1",
                              (cid,)).fetchone()
            if offen:
                raise HTTPException(400, "Die Erhebung %s ist noch offen — erst abschliessen "
                                         "(oder verwerfen), dann eine neue beginnen. Zwei offene "
                                         "Erhebungen haetten keinen eindeutigen Empfaenger."
                                         % offen["erhebung_id"])
            erhebung_id = _erhebung_kennung_neu(c, cid)[0]   # v2.8: E-JJJJ-MM oder -N
            c.execute(''', "POST erhebungen neu")

# 5. rating: Antwort nennt die Erhebung
s = ersetze(s,
    '''    # In welche Erhebung wird geschrieben? Legt beim ersten Mal eine an.
    eid = _erhebung_offen(c, cid)
''',
    '''    # In welche Erhebung wird geschrieben? Legt beim ersten Mal eine an.
    vorher = c.execute("SELECT erhebung_id FROM ref_erhebungen WHERE " + W_CO +
                       " AND status='offen' LIMIT 1", (cid,)).fetchone()
    eid = _erhebung_offen(c, cid)
    erhebung_neu = vorher is None   # v2.8: dieser Aufruf hat die Erhebung angelegt
''', "rating eid")
s = ersetze(s,
    '''    c.commit(); c.close(); return {"ok":True,"saved":len([1 for v in items.values() if v.get('stufe')])}''',
    '''    c.commit(); c.close()
    return {"ok": True, "saved": len([1 for v in items.values() if v.get('stufe')]),
            "erhebung_id": eid, "erhebung_neu": erhebung_neu}   # v2.8''', "rating return")

schreib("app.py", s)
print("app.py: gepatcht (v2.8)")
