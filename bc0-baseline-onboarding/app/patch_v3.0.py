# -*- coding: utf-8 -*-
"""Patch v3.0 fuer app.py — 07.09.2026. Setzt patch_v2.9.py und schema_v3.0 voraus.

Wer hat die Anfrage gestellt, und wann geht sie ans Gate.

  1. `POST …/anfragen` schreibt `angelegt_von` = benutzer.benutzer_id mit.
     Die Anmeldung wurde bisher geprueft und dann vergessen; die Zeile trug
     nicht, wer sie abgeschickt hat. Befund vom 07.09.2026 am Quelltext.
  2. `GET …/anfragen` liefert je Anfrage `steller` aus `v_anfrage_steller`:
     `person_id`, `herkunft` (formular | konto | unbekannt) und `name`.
     Das ist die Angabe, die BC1 fuer Ansprache und Herkunft braucht
     (Richard, 03.09., Abschnitt 5).
  3. `POST …/anfragen/gate_nachziehen` ruft `anfrage_am_gate_nachziehen()`.
     Setzt Anfragen auf `am_gate`, sobald ALLE ihre Teilprozesse ein fertiges
     BC1-Profil tragen. Damit muss BC1 den Status nicht selbst setzen.
     Ohne `bc1.prozessprofil` ohne Wirkung — die Funktion sagt es.

Nur PostgreSQL: `v_anfrage_steller` und die Funktion gibt es im SQLite-Betrieb
nicht. Beide Stellen fallen dort auf das bisherige Verhalten zurueck.
"""
import io, sys

def lies(p):  return io.open(p, encoding="utf-8").read()
def schreib(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def ersetze(s, alt, neu, name):
    if s.count(alt) != 1:
        sys.exit("Anker nicht (eindeutig) gefunden: " + name)
    return s.replace(alt, neu, 1)

s = lies("app.py")

# ---------------------------------------------------------------- 1. angelegt_von
s = ersetze(s,
    '''        c.execute("INSERT INTO ref_anfragen(company_id,anfrage_id,originaltext,eingang_am,"
                  "eingang_weg,steller_id,hinweis,angelegt_am,"
                  "process_id,sub_process_id,zuordnung_quelle,"
                  "status,status_seit,erhofftes_ziel,ausloeser,umfang_geschaetzt) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, anfrage_id, originaltext, eingang_am or _heute(),
                   (b.get("eingang_weg") or "").strip() or "pwa", steller_id,''',
    '''        # v3.0: Wer die Maske abgeschickt hat, steht jetzt in der Zeile. Bis
        # hierher wurde die Anmeldung geprueft und dann vergessen — die Anfrage
        # trug ihren Absender nicht. `steller_id` bleibt daneben: sie sagt, WER
        # GEMEINT ist (auch wenn ein Dritter die Maske bedient hat).
        c.execute("INSERT INTO ref_anfragen(company_id,anfrage_id,originaltext,eingang_am,"
                  "eingang_weg,steller_id,hinweis,angelegt_am,"
                  "process_id,sub_process_id,zuordnung_quelle,"
                  "status,status_seit,erhofftes_ziel,ausloeser,umfang_geschaetzt,"
                  "angelegt_von) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, anfrage_id, originaltext, eingang_am or _heute(),
                   (b.get("eingang_weg") or "").strip() or "pwa", steller_id,''',
    "insert anfrage spalten")

s = ersetze(s,
    '''                   (b.get("erhofftes_ziel") or "").strip() or None,
                   (b.get("ausloeser") or "").strip() or None,
                   (b.get("umfang_geschaetzt") or "").strip() or None))''',
    '''                   (b.get("erhofftes_ziel") or "").strip() or None,
                   (b.get("ausloeser") or "").strip() or None,
                   (b.get("umfang_geschaetzt") or "").strip() or None,
                   benutzer.benutzer_id))''',
    "insert anfrage werte")

# ---------------------------------------------------------------- 2. steller lesen
s = ersetze(s,
    '''        bezuege = _bezuege_lesen(c, cid)                       # v2.7
    finally:
        c.close()
    for z in zeilen:
        z["bezuege"] = bezuege.get(z["anfrage_id"], [])
    return {"anfragen": zeilen}''',
    '''        bezuege = _bezuege_lesen(c, cid)                       # v2.7
        steller = {}                                           # v3.0
        if PG:
            # v_anfrage_steller loest auf, wer hinter der Anfrage steht:
            # ausdruecklich gesetzte steller_id, sonst die Person des Kontos.
            # `herkunft` sagt, worauf die P-ID beruht — geraten wird nichts.
            for r in c.execute(
                    "SELECT anfrage_id, person_id, herkunft, person_name, person_funktion"
                    " FROM v_anfrage_steller WHERE " + W_CO, (cid,)).fetchall():
                steller[r["anfrage_id"]] = {
                    "person_id": r["person_id"], "herkunft": r["herkunft"],
                    "name": r["person_name"], "funktion": r["person_funktion"]}
    finally:
        c.close()
    for z in zeilen:
        z["bezuege"] = bezuege.get(z["anfrage_id"], [])
        z["steller"] = steller.get(z["anfrage_id"],
                                   {"person_id": None, "herkunft": "unbekannt",
                                    "name": None, "funktion": None})
    return {"anfragen": zeilen}''',
    "anfragen steller")

# ---------------------------------------------------------------- 3. gate nachziehen
s = ersetze(s,
    '''@app.put("/api/companies/{cid}/anfragen/{anfrage_id}/status")''',
    '''@app.post("/api/companies/{cid}/anfragen/gate_nachziehen")
def anfrage_gate_nachziehen(cid: str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Zieht Anfragen auf ``am_gate`` nach, deren BC1-Profile fertig sind.

    **Wofuer.** ``am_gate`` stand seit v2.2 in der Wertemenge — und **keine
    Zeile Code setzte ihn.** Befund vom 07.09.2026. Simeon: *„Wenn er
    abgeschlossen hat, sollte es automatisch ins Gate 0 zur Freigabe HitL
    gehen."* Damit erledigt sich zugleich Richards Frage vom 03.09., ob BC1
    den Status selbst setzen darf: Er muss nicht.

    **Die Regel** steht in der Datenbank, nicht hier: ``am_gate`` erst, wenn
    **alle** Teilprozesse der Anfrage ein fertiges BC1-Profil tragen —
    dieselbe Vollstaendigkeitsregel wie bei der Uebergabe (v2.7). Ein
    Gate-Bogen auf einem Ausschnitt waere derselbe Fehler wie ein ROI auf
    einem Ausschnitt. Kein Ruecksprung: nur aus ``zugeordnet`` und
    ``im_interview`` heraus.

    Solange BC1 nicht eingespielt hat, gibt es ``bc1.prozessprofil`` nicht;
    die Funktion laeuft dann, tut nichts und sagt es im Hinweis.

    Returns:
        Je betrachteter Anfrage: alter Status, neuer Status, Hinweis.
    """
    pruefe_mandant(benutzer, cid)
    _nur_pg("Das Nachziehen auf am_gate")
    c = db()
    try:
        _gate_mandant(c, cid)
        zeilen = [dict(r) for r in c.execute(
            "SELECT anfrage_id, status_alt, status_neu, hinweis"
            " FROM anfrage_am_gate_nachziehen(?) ORDER BY anfrage_id", (cid,)).fetchall()]
        c.commit()
    finally:
        c.close()
    return {"geprueft": len(zeilen),
            "gesetzt": [z["anfrage_id"] for z in zeilen if z["status_neu"] == "am_gate"
                        and z["status_alt"] != "am_gate"],
            "anfragen": zeilen}


@app.put("/api/companies/{cid}/anfragen/{anfrage_id}/status")''',
    "endpunkt gate_nachziehen")

schreib("app.py", s)
print("app.py: gepatcht (v3.0)")
