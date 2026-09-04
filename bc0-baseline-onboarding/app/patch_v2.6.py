# -*- coding: utf-8 -*-
"""Patch v2.6 fuer app.py und bc0_auth/middleware.py — 03./04.09.2026.

Vier Aenderungen, jede einzeln benannt. Laeuft einmal; ein zweiter Lauf
erkennt die vorhandenen Marker und tut nichts. Vorher `git status` — der
Patch arbeitet auf dem Klon-Stand c0dfb06.

  1. Historie kennt den Benutzer: Middleware setzt eine Kontextvariable,
     _Cx setzt je Verbindung `bc0.benutzer` (nur PostgreSQL).
  2. _erhebung_offen() schreibt nur noch in OFFENE Erhebungen; das Gate
     liest den massgeblichen Stand ueber _erhebung_massgeblich().
  3. Neue Endpunkte: Uebergabe (Vorschau, Paket schnueren, Pakete lesen),
     Widerruf einer Freigabe, Stand zum Datum, Historie je Teilprozess,
     v_stand_veraltet.
  4. Wertemenge GATE_EREIGNISSE bleibt; 'widerrufen' entsteht am neuen Endpunkt.
"""
import io, re, sys

def lies(p):  return io.open(p, encoding="utf-8").read()
def schreib(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def ersetze(s, alt, neu, name):
    if alt not in s:
        sys.exit("Anker nicht gefunden: " + name)
    if s.count(alt) != 1:
        sys.exit("Anker nicht eindeutig: " + name)
    return s.replace(alt, neu, 1)

# ---------------------------------------------------------------- middleware
mw = lies("bc0_auth/middleware.py")
if "AKTUELLER_BENUTZER" not in mw:
    mw = ersetze(mw,
        "def _sicher_aufloesen(request):",
        '''import contextvars

#: Der Benutzer der laufenden Anfrage — fuer die Aenderungshistorie (R9, v2.6).
#: Die Datenbankverbindung liest ihn und setzt `bc0.benutzer`; der Trigger
#: trg_historie() traegt ihn als `actor` ein. Ohne Anmeldung bleibt er None,
#: und die Historie zeigt den Datenbankbenutzer.
AKTUELLER_BENUTZER = contextvars.ContextVar("bc0_aktueller_benutzer", default=None)


def _sicher_aufloesen(request):''', "middleware: contextvar")
    mw = ersetze(mw,
        "            request.state.benutzer = _sicher_aufloesen(request)\n            return await call_next(request)",
        "            request.state.benutzer = _sicher_aufloesen(request)\n"
        "            AKTUELLER_BENUTZER.set(request.state.benutzer)\n"
        "            return await call_next(request)", "middleware: offener Pfad")
    mw = ersetze(mw,
        "        request.state.benutzer = benutzer\n        return await call_next(request)",
        "        request.state.benutzer = benutzer\n"
        "        AKTUELLER_BENUTZER.set(benutzer)\n"
        "        return await call_next(request)", "middleware: geschuetzter Pfad")
    schreib("bc0_auth/middleware.py", mw)
    print("middleware.py: Kontextvariable gesetzt")
else:
    print("middleware.py: bereits gepatcht")

# ---------------------------------------------------------------- app.py
s = lies("app.py")
if "v2.6" in s and "_erhebung_massgeblich" in s:
    print("app.py: bereits gepatcht"); sys.exit(0)

# 1. _Cx setzt bc0.benutzer
s = ersetze(s,
    "        if PG:\n            self.c = psycopg2.connect(DATABASE_URL)\n",
    "        if PG:\n            self.c = psycopg2.connect(DATABASE_URL)\n"
    "            # v2.6: Wer schreibt, steht in der Historie (trg_historie liest\n"
    "            # bc0.benutzer). Nur wenn eine Anfrage einen Benutzer hat — Skripte\n"
    "            # und Tests ohne Sitzung erscheinen als Datenbankbenutzer.\n"
    "            try:\n"
    "                from bc0_auth.middleware import AKTUELLER_BENUTZER\n"
    "                b = AKTUELLER_BENUTZER.get(None)\n"
    "            except Exception:  # noqa: BLE001 — ohne Kontext keine Herkunft, kein Abbruch\n"
    "                b = None\n"
    "            if b is not None:\n"
    "                self.c.cursor().execute(\"SELECT set_config('bc0.benutzer', %s, false)\",\n"
    "                                        (str(b.benutzer_id),))\n", "_Cx bc0.benutzer")

# 2. _erhebung_offen: nur offene; _erhebung_massgeblich fuer das Gate
s = ersetze(s,
    '''    zeile = c.execute(
        "SELECT erhebung_id FROM ref_erhebungen WHERE " + W_CO +
        " AND status<>'verworfen' ORDER BY stand DESC, erhebung_id DESC LIMIT 1",
        (cid,)).fetchone()
    if zeile:
        return zeile["erhebung_id"]
    heute = datetime.date.today()
    erhebung_id = "E-%04d-%02d" % (heute.year, heute.month)
    c.execute("INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status,methode) "''',
    '''    # v2.6: Nur eine OFFENE Erhebung nimmt neue Bewertungen an. Vorher wurde die
    # juengste nicht verworfene gewaehlt — auch eine abgeschlossene, und damit war
    # "abgeschlossen" keine Sperre. Seit schema_v2.6 weist die Datenbank das
    # ohnehin ab; hier steht die verstaendliche Antwort davor.
    zeile = c.execute(
        "SELECT erhebung_id FROM ref_erhebungen WHERE " + W_CO +
        " AND status='offen' ORDER BY stand DESC, erhebung_id DESC LIMIT 1",
        (cid,)).fetchone()
    if zeile:
        return zeile["erhebung_id"]
    heute = datetime.date.today()
    erhebung_id = "E-%04d-%02d" % (heute.year, heute.month)
    vorhanden = c.execute("SELECT status FROM ref_erhebungen WHERE " + W_CO +
                          " AND erhebung_id=?", (cid, erhebung_id)).fetchone()
    if vorhanden:
        c.close()
        raise HTTPException(400, "Die Erhebung %s ist %s und nimmt keine Bewertungen mehr an. "
                                 "Eine zweite Erhebung im selben Monat ist nicht darstellbar "
                                 "(Kennung E-JJJJ-MM)." % (erhebung_id, vorhanden["status"]))
    c.execute("INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status,methode) "''',
    "_erhebung_offen")

s = ersetze(s,
    '''@app.get("/api/companies/{cid}/erhebungen")
def erhebungen(cid: str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):''',
    '''def _erhebung_massgeblich(c, cid: str):
    """Die juengste nicht verworfene Erhebung — lesend, ohne Nebenwirkung.

    Fuer das Gate: Eine Freigabe haelt den Stand fest, sie beginnt keine
    Erhebung. (_erhebung_offen legt an; das darf eine Freigabe nicht.) Seit v2.6
    liefert die Historie den vollstaendigen Stand zum Zeitpunkt der Entscheidung;
    diese Kennung ist die Kurzform dazu.
    """
    zeile = c.execute(
        "SELECT erhebung_id FROM ref_erhebungen WHERE " + W_CO +
        " AND status<>'verworfen' ORDER BY stand DESC, erhebung_id DESC LIMIT 1",
        (cid,)).fetchone()
    return zeile["erhebung_id"] if zeile else None


@app.get("/api/companies/{cid}/erhebungen")
def erhebungen(cid: str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):''',
    "_erhebung_massgeblich")

s = ersetze(s,
    '''        erhebung_id = _erhebung_offen(c, cid)
        felder = ("gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,am,anfrage_id,"''',
    '''        erhebung_id = _erhebung_massgeblich(c, cid)
        felder = ("gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,am,anfrage_id,"''',
    "Gate liest massgeblich")

# 3. Neue Endpunkte — vor dem Anfrage-Block
NEU = r'''
# ---------------- v2.6: Uebergabe, Widerruf, Zeitreise (03./04.09.2026) ----------------
# Die Datenbank haelt die Regeln (schema_v2.6_historie_und_paket.sql): Pakete sind
# append-only, die Historie schreibt sich selbst, stand_zum() rechnet zurueck.
# Diese Endpunkte reichen durch und uebersetzen Fehler in lesbare Saetze.
# Alles ausser dem Widerruf braucht PostgreSQL — im SQLite-Modus antworten sie
# mit 501 und sagen es.

def _nur_pg(was):
    if not PG:
        raise HTTPException(501, "%s gibt es nur im PostgreSQL-Betrieb (schema_v2.6)." % was)


def _db_fehler_lesbar(e):
    """Ein Trigger-Fehler aus v2.6 traegt schon den richtigen Satz — durchreichen."""
    text = str(getattr(e, "diag", None) and e.diag.message_primary or e).strip()
    return HTTPException(400, text.split("\n")[0][:400])


@app.get("/api/companies/{cid}/uebergabe")
def uebergabe_lesen(cid: str, benutzer: Benutzer = Depends(admin)):
    """Vorschau und Bestand: Was wuerde ein Paket enthalten, welche Pakete gibt es.

    Keine Sammeluebergabe ohne Blick (Sicherheit 4 vom 11.08.): Die Kandidaten
    stehen hier, bevor der Knopf gedrueckt wird. Nach der ersten Uebergabe ist
    dieselbe Liste die Nachzuegler-Liste.
    """
    pruefe_mandant(benutzer, cid)
    _nur_pg("Die Uebergabe an BC2")
    c = db()
    try:
        _gate_mandant(c, cid)
        kandidaten = [dict(r) for r in c.execute(
            "SELECT sub_process_id, process_id, freigabe_ereignis_id, entschieden_am::text AS entschieden_am, "
            "anfrage_id, bc0_stand, bc1_profil_stand, hinweis_an_bc2 FROM v_uebergabe_kandidaten "
            "WHERE company_id=? ORDER BY sub_process_id", (cid,)).fetchall()]
        pakete = {}
        for r in c.execute(
                "SELECT paket_id::text AS paket_id, uebergeben_am::text AS uebergeben_am, uebergeben_von, "
                "hinweis, sub_process_id, anfrage_id, bc1_profil_stand, hinweis_an_bc2, paket_rang "
                "FROM v_uebergabe_offen WHERE company_id=? ORDER BY uebergeben_am DESC, sub_process_id",
                (cid,)).fetchall():
            p = pakete.setdefault(r["paket_id"], {
                "paket_id": r["paket_id"], "uebergeben_am": r["uebergeben_am"],
                "uebergeben_von": r["uebergeben_von"], "hinweis": r["hinweis"],
                "rang": int(r["paket_rang"]), "teilprozesse": []})
            p["teilprozesse"].append({"sub_process_id": r["sub_process_id"], "anfrage_id": r["anfrage_id"],
                                      "bc1_profil_stand": r["bc1_profil_stand"],
                                      "hinweis_an_bc2": r["hinweis_an_bc2"]})
    finally:
        c.close()
    return {"kandidaten": kandidaten, "pakete": list(pakete.values())}


@app.post("/api/companies/{cid}/uebergabe")
async def uebergabe_schnueren(cid: str, req: Request, benutzer: Benutzer = Depends(admin)):
    """Paket an BC2 uebergeben — eine Transaktion in der Datenbank.

    gate_paket_schnueren() schreibt das Ereignis `uebergeben` am Unternehmen, das
    Paket und seinen Inhalt. Ohne Kandidaten gibt es kein leeres Paket. Das
    Datum am Paket ist der Zeitpunkt, fuer den BC2 mit stand_zum() liest.
    """
    pruefe_mandant(benutzer, cid)
    _nur_pg("Die Uebergabe an BC2")
    b = await req.json() if req.headers.get("content-length", "0") not in ("0", "") else {}
    hinweis = (b.get("hinweis") or "").strip() or None
    c = db()
    try:
        _gate_mandant(c, cid)
        try:
            paket = c.execute("SELECT gate_paket_schnueren(?, ?, ?)::text AS paket_id",
                              (cid, benutzer.benutzer_id, hinweis)).fetchone()["paket_id"]
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 — die Datenbank hat den Satz, wir reichen ihn durch
            c.close()
            raise _db_fehler_lesbar(e)
        c.commit()
    finally:
        try: c.close()
        except Exception: pass
    return {"ok": True, "paket_id": paket}


@app.post("/api/companies/{cid}/gate/{sub_process_id}/widerrufen")
async def gate_widerrufen(cid: str, sub_process_id: str, req: Request,
                          benutzer: Benutzer = Depends(admin)):
    """Eine Freigabe zuruecknehmen — die menschliche Form des Einfrierens.

    Nicht der Prozess wird gesperrt, die Freigabe wird widerrufen: neues
    Ereignis, append-only, Grund Pflicht. Der Teilprozess faellt damit aus
    v_uebergabe_kandidaten heraus und kann neu entschieden werden. Ein bereits
    uebergebenes Paket bleibt unveraendert — BC2 sieht den Widerruf ueber
    v_gate_freigabe_aktuell.
    """
    pruefe_mandant(benutzer, cid)
    b = await req.json()
    grund = (b.get("grund") or "").strip()
    if not grund:
        raise HTTPException(400, "Ein Widerruf braucht einen Grund.")
    c = db()
    try:
        _gate_mandant(c, cid)
        stand = _gate_letzter_stand(c, cid, sub_process_id).get(sub_process_id)
        if not stand or stand["stand"] != "freigegeben":
            c.close()
            raise HTTPException(400, "%s ist nicht freigegeben — nichts zu widerrufen." % sub_process_id)
        felder = "gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,am,anfrage_id,erhebung_id,grund"
        daten = ("bc0-bc2", cid, "teilprozess", sub_process_id, "widerrufen",
                 benutzer.benutzer_id, _jetzt(), stand.get("anfrage_id"), stand.get("erhebung_id"), grund)
        sql = "INSERT INTO gate_ereignisse(" + felder + ") VALUES(" + ",".join(["?"] * 10) + ")"
        if PG:
            ereignis_id = c.execute(sql + " RETURNING ereignis_id", daten).fetchone()["ereignis_id"]
        else:
            ereignis_id = c.execute(sql, daten).lastrowid
        c.commit()
    finally:
        try: c.close()
        except Exception: pass
    return {"ok": True, "ereignis_id": ereignis_id, "stand": "widerrufen"}


@app.get("/api/companies/{cid}/uebergabe/veraltet")
def uebergabe_veraltet(cid: str, benutzer: Benutzer = Depends(admin)):
    """Was sich seit Freigabe bzw. Uebergabe geaendert hat — aus der Historie gezaehlt.

    v_stand_veraltet verbietet nichts. Sie sagt je freigegebenem Teilprozess, ob
    eine Frage ansteht: widerrufen, neu freigeben, oder BC2 rechnet weiter.
    """
    pruefe_mandant(benutzer, cid)
    _nur_pg("Der Abgleich mit der Historie")
    c = db()
    try:
        _gate_mandant(c, cid)
        zeilen = [dict(r) for r in c.execute(
            "SELECT sub_process_id, process_id, freigegeben_am::text AS freigegeben_am, "
            "uebergeben_am::text AS uebergeben_am, paket_id::text AS paket_id, "
            "aenderungen_tp_seit_freigabe, aenderungen_kp_seit_freigabe, aenderungen_tp_seit_paket, "
            "geaenderte_tabellen, stillgelegt, struktur_geaendert FROM v_stand_veraltet "
            "WHERE company_id=? ORDER BY sub_process_id", (cid,)).fetchall()]
    finally:
        c.close()
    for z in zeilen:
        for k in ("aenderungen_tp_seit_freigabe", "aenderungen_kp_seit_freigabe", "aenderungen_tp_seit_paket"):
            z[k] = int(z[k] or 0)
    return {"teilprozesse": zeilen}


@app.get("/api/companies/{cid}/stand")
def stand_zum_datum(cid: str, datum: str, benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Der Reifegrad je Teilprozess, wie er zu einem Zeitpunkt war (Zeitreise, R9).

    `datum` ist ISO-8601 (z. B. 2026-09-04T09:00:00+02:00 oder ein Paketdatum aus
    /uebergabe). Vor Beginn der Historie gibt es keine Antwort — und keine
    geratene; die Datenbank sagt, ab wann sie rekonstruieren kann.
    """
    pruefe_mandant(benutzer, cid)
    _nur_pg("Die Zeitreise")
    c = db()
    try:
        _gate_mandant(c, cid)
        try:
            zeilen = [dict(r) for r in c.execute(
                "SELECT sub_process_id, avg_stufe, n_items FROM reifegrad_tp_zum(?, ?::timestamptz) "
                "ORDER BY sub_process_id", (cid, datum)).fetchall()]
            beginn = c.execute("SELECT historie_beginn()::text AS b").fetchone()["b"]
        except Exception as e:  # noqa: BLE001
            c.close()
            raise _db_fehler_lesbar(e)
    finally:
        try: c.close()
        except Exception: pass
    for z in zeilen:
        z["avg_stufe"] = float(z["avg_stufe"]) if z["avg_stufe"] is not None else None
        z["n_items"] = int(z["n_items"])
    return {"datum": datum, "historie_beginn": beginn, "teilprozesse": zeilen}


@app.get("/api/companies/{cid}/historie")
def historie_lesen(cid: str, tp: str = None, seit: str = None, limit: int = 200,
                   benutzer: Benutzer = Depends(angemeldeter_benutzer)):
    """Die Aenderungshistorie eines Mandanten, optional je Teilprozess und ab Datum.

    Ohne Zeilenbilder — wer die braucht, liest audit_log direkt. Klarnamen
    stehen ohnehin nicht darin (historie_pii_entfernen).
    """
    pruefe_mandant(benutzer, cid)
    _nur_pg("Die Historie")
    limit = max(1, min(int(limit), 1000))
    sql = ("SELECT audit_id, at::text AS at, actor, entity, action, pk::text AS pk, process_id, "
           "sub_process_id FROM v_historie WHERE company_id=? AND action<>'bestand'")
    werte = [cid]
    if tp:
        sql += " AND sub_process_id=?"; werte.append(tp)
    if seit:
        sql += " AND at > ?::timestamptz"; werte.append(seit)
    sql += " ORDER BY at DESC, audit_id DESC LIMIT %d" % limit
    c = db()
    try:
        _gate_mandant(c, cid)
        zeilen = [dict(r) for r in c.execute(sql, tuple(werte)).fetchall()]
    finally:
        c.close()
    return {"eintraege": zeilen}


'''
s = ersetze(s, '@app.get("/api/companies/{cid}/anfragen")\n', NEU + '@app.get("/api/companies/{cid}/anfragen")\n', "neue Endpunkte")
schreib("app.py", s)
print("app.py: gepatcht (v2.6)")
