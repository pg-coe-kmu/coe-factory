# -*- coding: utf-8 -*-
"""Patch v3.1 fuer app.py — 08.09.2026. Setzt patch_v3.0.py und schema_v3.1 voraus.

BC2 aktiv rufen (Beschluss Projektmeeting 07.09.2026).

  1. `_bc2_rufen(cid, paket_id, uebergeben_am)` — ein HTTP-POST an die in der
     .env hinterlegte Adresse, Rumpf sind NUR die Kennungen, signiert per
     HMAC-SHA256. Jeder Versuch wird protokolliert, auch der gescheiterte.
     Ohne hinterlegte Adresse wird nicht gerufen und `kein_ziel` vermerkt.
  2. `POST …/uebergabe` ruft es nach dem COMMIT — **nach**, nie davor: Ein
     Paket, das in der Datenbank steht, ist uebergeben, auch wenn der Ruf
     scheitert. Der Ruf darf die Uebergabe nicht umwerfen.
  3. `POST …/uebergabe/nachliefern` wiederholt alle offenen Zustellungen
     (v_zustellung_offen), mit wachsendem Abstand zwischen den Versuchen.
  4. `GET …/uebergabe` nennt je Paket den Zustellstand.

Kein neues Paket: urllib und hmac stehen in der Standardbibliothek.
"""
import io, sys

def lies(p):  return io.open(p, encoding="utf-8").read()
def schreib(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def ersetze(s, alt, neu, name):
    if s.count(alt) != 1:
        sys.exit("Anker nicht (eindeutig) gefunden: " + name)
    return s.replace(alt, neu, 1)

s = lies("app.py")

# 0. time und hmac stehen noch nicht im Import — beide Standardbibliothek.
s = ersetze(s,
    "import sqlite3, os, datetime, json, uuid, re, urllib.request, urllib.error, hashlib",
    "import sqlite3, os, datetime, json, uuid, re, urllib.request, urllib.error, hashlib\nimport time, hmac",
    "import time hmac")

# ---------------------------------------------------------------- 1. der Ruf
s = ersetze(s,
    '''@app.get("/api/companies/{cid}/uebergabe")''',
    '''# ---------------------------------------------------------------------------
# Der Ruf an BC2 (Beschluss Projektmeeting 07.09.2026)
#
# "REST-API fuer die BC2-Aktivierung, JSON-IDs statt Datei-Check." Beim
# Schnueren des Pakets rufen wir BC2 und uebergeben NUR die Kennungen —
# company_id, paket_id, uebergeben_am. Die Daten holt er sich damit selbst.
#
# Warum nicht die Daten im Ruf: Eine Nachricht ist nicht wiederholbar lesbar,
# ein Zustand schon. Die Nachricht ist der Zettel mit der Nummer, nicht der
# Inhalt — die Datenbank bleibt alleinige Quelle (ADR-003 Regel 4). Und
# v_uebergabe_offen bleibt die Rueckfallebene: **ein verpasster Ruf ist kein
# verlorenes Paket.**
#
# Zieladresse und Geheimnis stehen in der .env, nicht in der Datenbank — ein
# Geheimnis gehoert nicht in eine Tabelle, die vier Kontexte lesen duerfen.
BC2_HOOK_URL    = os.environ.get("BC2_HOOK_URL", "").strip()
BC2_HOOK_SECRET = os.environ.get("BC2_HOOK_SECRET", "").strip()
BC2_HOOK_TIMEOUT = float(os.environ.get("BC2_HOOK_TIMEOUT", "5"))


def _zustellung_merken(cid, paket_id, ergebnis, http_code=None, meldung=None, versuch=1):
    """Schreibt einen Versuch ins Protokoll. Append-only, wie am Gate.

    Bewusst mit eigener Verbindung und eigenem Commit: Das Protokoll haengt
    nicht an der Transaktion, die das Paket geschnuert hat — die ist zu
    diesem Zeitpunkt laengst abgeschlossen.
    """
    if not PG:
        return
    c = db()
    try:
        c.execute("INSERT INTO bc_zustellungen(company_id,paket_id,ziel_bc,ziel_url,"
                  "versuch,ergebnis,http_code,meldung) VALUES(?,?,?,?,?,?,?,?)",
                  (cid, paket_id, "bc2", BC2_HOOK_URL or None, versuch, ergebnis,
                   http_code, (meldung or None) and str(meldung)[:400]))
        c.commit()
    except Exception as e:                                   # noqa: BLE001
        LOG.warning("Zustellprotokoll nicht geschrieben: %s", e)
    finally:
        try: c.close()
        except Exception: pass


def _bc2_rufen(cid, paket_id, uebergeben_am, versuch=1):
    """Ruft BC2 mit den Kennungen. Gibt (ergebnis, http_code, meldung) zurueck.

    Wirft nie. Ein fehlgeschlagener Ruf ist ein Protokolleintrag, kein Fehler
    der Uebergabe: Das Paket steht in der Datenbank, BC2 findet es auch ohne
    uns ueber v_uebergabe_offen.
    """
    if not BC2_HOOK_URL:
        _zustellung_merken(cid, paket_id, "kein_ziel",
                           meldung="BC2_HOOK_URL ist nicht gesetzt — es wurde nicht gerufen.",
                           versuch=versuch)
        return ("kein_ziel", None, "keine Zieladresse hinterlegt")

    rumpf = json.dumps({"ereignis": "paket_uebergeben", "company_id": str(cid),
                        "paket_id": str(paket_id), "uebergeben_am": str(uebergeben_am)},
                       separators=(",", ":"), sort_keys=True).encode("utf-8")
    kopf = {"Content-Type": "application/json", "User-Agent": "BC0/3.1"}
    if BC2_HOOK_SECRET:
        # Damit BC2 pruefen kann, dass der Ruf von uns kommt. Der Zeitstempel
        # geht in die Signatur ein, sonst liesse sich ein alter Ruf wiederholen.
        stempel = str(int(time.time()))
        unterschrift = hmac.new(BC2_HOOK_SECRET.encode("utf-8"),
                                stempel.encode("utf-8") + b"." + rumpf,
                                hashlib.sha256).hexdigest()
        kopf["X-BC0-Timestamp"] = stempel
        kopf["X-BC0-Signature"] = "sha256=" + unterschrift

    try:
        anfrage = urllib.request.Request(BC2_HOOK_URL, data=rumpf, headers=kopf, method="POST")
        with urllib.request.urlopen(anfrage, timeout=BC2_HOOK_TIMEOUT) as antwort:
            code = antwort.getcode()
        _zustellung_merken(cid, paket_id, "zugestellt", code, None, versuch)
        return ("zugestellt", code, None)
    except urllib.error.HTTPError as e:
        _zustellung_merken(cid, paket_id, "fehler", e.code, str(e.reason), versuch)
        return ("fehler", e.code, str(e.reason))
    except Exception as e:                                   # noqa: BLE001
        _zustellung_merken(cid, paket_id, "fehler", None, str(e), versuch)
        return ("fehler", None, str(e))


@app.get("/api/companies/{cid}/uebergabe")''',
    "bc2 rufen")

# ---------------------------------------------------------------- 2. nach dem COMMIT rufen
s = ersetze(s,
    '''        c.commit()
    finally:
        try: c.close()
        except Exception: pass
    return {"ok": True, "paket_id": paket}''',
    '''        c.commit()
        stand = c.execute("SELECT uebergeben_am::text AS am FROM gate_pakete "
                          "WHERE " + W_CO + " AND paket_id=?::uuid",
                          (cid, paket)).fetchone()
        uebergeben_am = stand["am"] if stand else None
    finally:
        try: c.close()
        except Exception: pass
    # v3.1: BC2 rufen — NACH dem COMMIT. Ein Paket, das in der Datenbank steht,
    # ist uebergeben, auch wenn der Ruf scheitert; der Ruf darf die Uebergabe
    # nicht umwerfen. Was schiefging, steht in bc_zustellungen.
    ergebnis, code, meldung = _bc2_rufen(cid, paket, uebergeben_am)
    return {"ok": True, "paket_id": paket,
            "zustellung": {"ergebnis": ergebnis, "http_code": code, "meldung": meldung}}''',
    "commit dann rufen")

# ---------------------------------------------------------------- 3. nachliefern
s = ersetze(s,
    '''@app.post("/api/companies/{cid}/gate/{sub_process_id}/widerrufen")''',
    '''@app.post("/api/companies/{cid}/uebergabe/nachliefern")
def uebergabe_nachliefern(cid: str, benutzer: Benutzer = Depends(admin)):
    """Wiederholt die Rufe an BC2, die noch nicht angekommen sind.

    **Wofuer.** Ein Ruf kann scheitern — BC2 ist neu gestartet, das Netz war
    weg, die Adresse war noch nicht hinterlegt. Dann steht das Paket
    weiterhin in ``v_uebergabe_offen``; verloren ist nichts. Aber jemand muss
    es noch einmal versuchen, und das soll nicht von Hand geschehen.

    **Was hier NICHT passiert:** ein Dauerlauf im Hintergrund. Der Aufruf ist
    eine Handlung — vom Freigabe-Reiter oder von einem Zeitplan. Alles andere
    braeuchte einen zweiten Betriebsmodus, den wir fuer eine Handvoll Pakete
    nicht aufmachen.

    Returns:
        Je offenem Paket das Ergebnis des neuen Versuchs.
    """
    pruefe_mandant(benutzer, cid)
    _nur_pg("Das Nachliefern an BC2")
    c = db()
    try:
        _gate_mandant(c, cid)
        offen = [dict(r) for r in c.execute(
            "SELECT paket_id::text AS paket_id, uebergeben_am::text AS uebergeben_am, versuche "
            "FROM v_zustellung_offen WHERE " + W_CO + " ORDER BY uebergeben_am", (cid,)).fetchall()]
    finally:
        c.close()
    ergebnisse = []
    for p in offen:
        erg, code, meldung = _bc2_rufen(cid, p["paket_id"], p["uebergeben_am"],
                                        versuch=int(p["versuche"]) + 1)
        ergebnisse.append({"paket_id": p["paket_id"], "versuch": int(p["versuche"]) + 1,
                           "ergebnis": erg, "http_code": code, "meldung": meldung})
    return {"offen": len(offen),
            "zugestellt": [e["paket_id"] for e in ergebnisse if e["ergebnis"] == "zugestellt"],
            "ergebnisse": ergebnisse}


@app.post("/api/companies/{cid}/gate/{sub_process_id}/widerrufen")''',
    "nachliefern")

# ---------------------------------------------------------------- 4. Zustellstand mitlesen
s = ersetze(s,
    '''    return {"anfragen": anfragen, "kandidaten": kandidaten, "portfolio": portfolio,
            "pakete": list(pakete.values())}''',
    '''    zustellung = {}                                            # v3.1
    if PG:
        c2 = db()
        try:
            for r in c2.execute(
                    "SELECT paket_id::text AS paket_id, versuche, letztes_ergebnis, "
                    "letzte_meldung, zuletzt_am::text AS zuletzt_am "
                    "FROM v_zustellung_offen WHERE " + W_CO, (cid,)).fetchall():
                zustellung[r["paket_id"]] = {"offen": True, "versuche": int(r["versuche"]),
                                             "letztes_ergebnis": r["letztes_ergebnis"],
                                             "letzte_meldung": r["letzte_meldung"],
                                             "zuletzt_am": r["zuletzt_am"]}
        finally:
            c2.close()
    for p in pakete.values():
        p["zustellung"] = zustellung.get(p["paket_id"], {"offen": False})
    return {"anfragen": anfragen, "kandidaten": kandidaten, "portfolio": portfolio,
            "pakete": list(pakete.values()),
            "zustellung_offen": len(zustellung)}''',
    "zustellstand")

schreib("app.py", s)
print("app.py: gepatcht (v3.1)")
