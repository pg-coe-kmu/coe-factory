"""Tests v3.43 KI-Reifegrad nach SEI.

Modus PG:     DATABASE_URL auf das Testgeruest (SIM-Daten, v3.42, v3.43 eingespielt).
              init_db() wird uebersprungen (Testgeruest ist kein Vollschema).
Modus SQLite: BC0_DB auf eine frische Datei, init_db() laeuft vollstaendig.
"""
import os, sys, types, importlib.util, json

MODUS = os.environ.get("MODUS", "pg")
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
src = open(os.path.join(HIER, "app.py"), encoding="utf-8").read()
if MODUS == "pg":
    assert src.count("\ninit_db()\n") == 1
    src = src.replace("\ninit_db()\n", "\n# init_db() im Test uebersprungen\n")
mod = types.ModuleType("app"); mod.__file__ = os.path.join(HIER, "app.py")
sys.modules["app"] = mod
exec(compile(src, mod.__file__, "exec"), mod.__dict__)
app = mod

from fastapi.testclient import TestClient
from bc0_auth.modelle import Benutzer, Rolle
from bc0_auth import abhaengigkeiten as ab

SIM = "05abe89c-b2a6-4db6-9b22-66b9fb320b1d"
NORO = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"

def benutzer(rolle):
    return Benutzer(benutzer_id="958515eb-a8a6-4b02-a2ac-d4794ad11113", email="t@test.invalid", name="Test",
                    rolle=Rolle(rolle), mandanten=frozenset())

# Anmeldepflicht-Middleware umgehen: Abhaengigkeit direkt setzen
AKT = {"rolle": "admin"}
app.app.dependency_overrides[ab.angemeldeter_benutzer] = lambda: benutzer(AKT["rolle"])
app.app.user_middleware = [m for m in app.app.user_middleware if "Anmeldepflicht" not in str(m.cls)]
app.app.middleware_stack = app.app.build_middleware_stack()
cl = TestClient(app.app)
ok = 0; fehler = []
def pruef(name, bed, info=""):
    global ok
    if bed: ok += 1; print("  ok ", name)
    else: fehler.append(name); print("  FEHLER", name, info)

if MODUS == "pg":
    # Start-DDL der App muss auf der eingespielten v3.43 ohne Fehler laufen (IF NOT EXISTS / ON CONFLICT)
    c = app.db(); c.execute(app.KIA_DDL_PG)
    c.executemany("INSERT INTO kia_dimensionen(dim_nr,name,gruppe) VALUES(?,?,?) ON CONFLICT (dim_nr) DO NOTHING", app.KIA_DIMENSIONEN)
    c.executemany("INSERT INTO kia_bereiche(bereich_id,dim_nr,name,eintrittsstufe,seite,menue) VALUES(?,?,?,?,?,?) ON CONFLICT (bereich_id) DO NOTHING", app.KIA_BEREICHE)
    c.commit(); c.close(); pruef("Start-DDL auf v3.43 laeuft durch", True)
    cid = SIM
else:
    c = app.db(); c.execute("INSERT INTO companies(name) VALUES('Testmandant')"); c.commit()
    cid = str(c.execute("SELECT max(id) AS i FROM companies").fetchone()["i"]); c.close()

print("== GET", MODUS)
r = cl.get("/api/companies/%s/ki_reifegrad_sei" % cid); pruef("GET 200", r.status_code == 200, r.text[:300])
d = r.json()
dims = {x["dim_nr"]: x for x in d["dimensionen"]}
pruef("8 Dimensionen", len(dims) == 8)
pruef("25 Bereiche", sum(len(x["bereiche"]) for x in d["dimensionen"]) == 25)
pruef("4.6.2 Eintrittsstufe 3", [b for b in dims[3]["bereiche"] if b["bereich_id"] == "4.6.2"][0]["eintrittsstufe"] == 3)
pruef("4.10.x sortiert nach 4.9.x", [b["bereich_id"] for b in dims[7]["bereiche"]] == ["4.10.1", "4.10.2", "4.10.3"])

if MODUS == "pg":
    ist = {n: x["ist"] for n, x in dims.items()}
    print("   Ist je Dimension:", ist, " Ziel:", {n: x["ziel"] for n, x in dims.items()})
    # Erwartung aus den Mockdaten (Regel S. 82-87, Tabelle 2):
    # 1 Strategie: 4.4.1=2 (L2 ok); L3 verlangt 4.4.2=1 -> 2
    # 2 Belegschaft: 4.5.1 teilweise -> min(1, max(1,0))=1 -> L2 braucht 4.5.1>=2 -> 1
    # 3 Ablaeufe: 4.6.1=2; L2 ok; L3: 4.6.2 unbewertet -> 2
    # 4 Risiko: 4.7.1=1 -> 1
    # 5 Daten: unbewertet -> 1
    # 6 Engineering: 4.9.1=2, 4.9.2=3 -> L2 ok; L3 braucht 4.9.1>=3 -> 2
    # 7 Betrieb: 4.10.1=2, 4.10.2=2; L3 braucht 4.10.3 (teilweise ->1) -> 2
    # 8 Oekosystem: 4.11.1=2; L3 braucht 4.11.2=2 -> 2
    erw = {1: 2, 2: 1, 3: 2, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2}
    pruef("Ist-Stufen wie erwartet", ist == erw, ist)
    pruef("Ziel 3 ueberall", all(x["ziel"] == 3 for x in dims.values()))
    ns7 = [x["bereich_id"] for x in dims[7]["naechster_schritt"]]
    pruef("Betrieb: naechster Schritt 4.10.1, 4.10.2, 4.10.3", ns7 == ["4.10.1", "4.10.2", "4.10.3"], ns7)
    g = [x for x in dims[7]["naechster_schritt"] if x["bereich_id"] == "4.10.3"][0]["grund"]
    pruef("Grund 4.10.3 = Ziele teilweise erfuellt", g == "Ziele teilweise erfüllt", g)
    m = {k["kennzahl"]: k for b in dims[7]["bereiche"] for k in b["messungen"]}
    mk = m["Erfassungsquote Korrektur (Voraussetzung Drift)"]
    pruef("Korrektur-Erfassung 319/342 = 93,3 %", mk["wert"] == 93.3 and mk["nenner"] == 342, mk)
    mf = m["Läufe mit fester Modellfassung (Datum im Namen)"]; pruef("Feste Fassung 0/342 (mistral, claude ohne Datum)", mf["status"]=="ok" and mf["zaehler"]==0 and mf["nenner"]==342, mf)
    mr = m["Verwendete Modelle im Modellregister"]; pruef("Register 2/2", mr["wert"] == 100.0, mr)
    m6 = {k["kennzahl"]: k for b in dims[6]["bereiche"] for k in b["messungen"]}
    pruef("Kriterien mit Testfall 28/28", m6["Akzeptanzkriterien mit Testfall"]["wert"] == 100.0, m6["Akzeptanzkriterien mit Testfall"])
    tb = m6["Testergebnisse letzter Durchlauf bestanden"]; pruef("letzter Durchlauf 26/28", tb["zaehler"] == 26 and tb["nenner"] == 28, tb)
    m8 = {k["kennzahl"]: k for b in dims[8]["bereiche"] for k in b["messungen"]}
    pruef("Wechselplan 2/2", m8["Modelle mit Abschaltdatum und Wechselplan"]["wert"] == 100.0)
    pruef("Kontext SIM", d["kontext"]["planungshorizont"] == "1_3_jahre")
    r2 = cl.get("/api/companies/%s/ki_reifegrad_sei" % NORO).json()
    r2m = {k["kennzahl"]: k for x in cl.get("/api/companies/%s/ki_reifegrad_sei" % NORO).json()["dimensionen"] for b in x["bereiche"] for k in b["messungen"]}
    pruef("v3.43a NoroAI Kosten ohne Erfassung -> keine Daten", r2m["Kosten je erfolgreichem Lauf"]["status"] == "keine_daten", r2m["Kosten je erfolgreichem Lauf"])
    pruef("NoroAI ohne Bewertung: alles Stufe 1, kein Ziel", all(x["ist"] == 1 and x["ziel"] is None for x in r2["dimensionen"]))
else:
    m = {k["kennzahl"]: k for x in d["dimensionen"] for b in x["bereiche"] for k in b["messungen"]}
    pruef("SQLite: kir_* nicht verfuegbar statt Fehler", m["Akzeptanzkriterien mit Testfall"]["status"] == "nicht_verfuegbar")
    pruef("SQLite: feste Fassung keine Daten (kein Fehler)", m["Läufe mit fester Modellfassung (Datum im Namen)"]["status"] == "keine_daten", m["Läufe mit fester Modellfassung (Datum im Namen)"])
    pruef("SQLite: Laufdaten keine Daten", m["Erfassungsquote Kosten"]["status"] == "keine_daten")

print("== PUT Fehlerfaelle (nichts geschrieben)")
vorher = cl.get("/api/companies/%s/ki_reifegrad_sei" % cid).json()["verlauf"]
gut = {"bereich_id": "4.10.3", "ziele": "erfuellt", "nachweis": "messung", "ind_verantwortung": 3, "ind_planung": 3,
       "ind_ressourcen": 3, "begruendung": "Test"}
for name, body in [
    ("unbekannter Bereich", {"bewertungen": [dict(gut, bereich_id="4.99.9")]}),
    ("Indikator 6", {"bewertungen": [dict(gut, ind_planung=6)]}),
    ("ohne Begruendung", {"bewertungen": [dict(gut, begruendung=" ")]}),
    ("Beleg ohne Angabe", {"bewertungen": [dict(gut, nachweis="beleg")]}),
    ("ziele falsch", {"bewertungen": [dict(gut, ziele="ja")]}),
    ("Zielstufe ohne Begruendung", {"zielstufen": [{"dim_nr": 7, "zielstufe": 3}]}),
    ("Zielstufe 9", {"zielstufen": [{"dim_nr": 7, "zielstufe": 9, "begruendung": "x"}]}),
    ("Kontext falsch", {"kontext": {"regulierung": "egal"}}),
    ("gute Bewertung + falsche Zielstufe", {"bewertungen": [gut], "zielstufen": [{"dim_nr": 0, "zielstufe": 3, "begruendung": "x"}]}),
]:
    r = cl.put("/api/companies/%s/ki_reifegrad_sei" % cid, json=body); pruef("400 " + name, r.status_code == 400, r.status_code)
nachher = cl.get("/api/companies/%s/ki_reifegrad_sei" % cid).json()["verlauf"]
pruef("Bestand unveraendert nach Fehlern", vorher == nachher, (vorher, nachher))

print("== PUT Leser")
AKT["rolle"] = "leser"
r = cl.put("/api/companies/%s/ki_reifegrad_sei" % cid, json={"bewertungen": [gut]}); pruef("Leser 403", r.status_code == 403, r.status_code)
AKT["rolle"] = "admin"

print("== PUT gut: Anhaengen, juengste Zeile gilt")
r = cl.put("/api/companies/%s/ki_reifegrad_sei" % cid, json={"bewertungen": [gut],
           "zielstufen": [{"dim_nr": 7, "zielstufe": 4, "begruendung": "Test Ziel 4"}],
           "kontext": {"umfang": "mandant", "regulierung": "reguliert"}})
pruef("PUT 200", r.status_code == 200, r.text[:200])
d2 = cl.get("/api/companies/%s/ki_reifegrad_sei" % cid).json()
pruef("Verlauf +1 Bewertung, +1 Zielstufe", d2["verlauf"]["bewertungen"] == vorher["bewertungen"] + 1 and d2["verlauf"]["zielstufen"] == vorher["zielstufen"] + 1)
d7 = [x for x in d2["dimensionen"] if x["dim_nr"] == 7][0]
b3 = [b for b in d7["bereiche"] if b["bereich_id"] == "4.10.3"][0]
pruef("4.10.3 jetzt Stufe 3", b3["stufe"] == 3, b3["stufe"])
pruef("Ziel Betrieb 4", d7["ziel"] == 4)
if MODUS == "pg":
    pruef("Betrieb Ist jetzt 2 (4.10.1/4.10.2 nur 2)", d7["ist"] == 2, d7["ist"])
    pruef("bewertet_von = benutzer_id", b3["bewertung"]["bewertet_von"] == "958515eb-a8a6-4b02-a2ac-d4794ad11113")
pruef("Kontext ersetzt", d2["kontext"]["regulierung"] == "reguliert" and d2["kontext"]["planungshorizont"] is None)

print("== Stufenregel (Funktionen)")
f = app._kia_bereichsstufe
pruef("ohne Bewertung None", f(2, None) is None)
pruef("erfuellt min Indikatoren", f(2, {"ziele": "erfuellt", "ind_verantwortung": 4, "ind_planung": 3, "ind_ressourcen": 5}) == 3)
pruef("teilweise gedeckelt auf e-1", f(3, {"ziele": "teilweise", "ind_verantwortung": 5, "ind_planung": 5, "ind_ressourcen": 5}) == 2)
pruef("nein bei e=1 -> 1", f(1, {"ziele": "nein", "ind_verantwortung": 4, "ind_planung": 4, "ind_ressourcen": 4}) == 1)
pruef("zurueckgestellt None", f(2, {"ziele": "zurueckgestellt", "ind_verantwortung": 4, "ind_planung": 4, "ind_ressourcen": 4}) is None)
D = app._kia_dimensionsstufe
pruef("Dimension: zurueckgestellt zaehlt nicht",
      D([{"eintrittsstufe": 2, "stufe": None, "zurueckgestellt": True}, {"eintrittsstufe": 2, "stufe": 3, "zurueckgestellt": False}]) == 3)
pruef("Dimension: Bereich ab 4 bremst Stufe 3 nicht",
      D([{"eintrittsstufe": 2, "stufe": 3, "zurueckgestellt": False}, {"eintrittsstufe": 4, "stufe": None, "zurueckgestellt": False}]) == 3)

print("\nErgebnis %s: %d ok, %d Fehler %s" % (MODUS, ok, len(fehler), fehler))
sys.exit(1 if fehler else 0)
