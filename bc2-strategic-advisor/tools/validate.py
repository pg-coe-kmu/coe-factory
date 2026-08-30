"""contracts-validate: prueft Mocks und Lieferungen gegen die v2-Schemas (Draft 2020-12)."""
import json, sys, pathlib
from jsonschema import Draft202012Validator

BASE = pathlib.Path(__file__).resolve().parents[2]
LIEFERUNG = "contracts/bc2-to-bc3/lieferungen/2026-08-30-vorlaeufig"
PAIRS = [
    ("contracts/bc2-to-bc3/konzept.schema.json", "contracts/examples/mock_automatisierungskonzept.json"),
    ("contracts/bc2-to-bc3/priorisierung.schema.json", "contracts/examples/mock_prozesspriorisierung.json"),
    ("contracts/bc2-to-bc3/konzept.schema.json", f"{LIEFERUNG}/konzept_KP-02.json"),
    ("contracts/bc2-to-bc3/konzept.schema.json", f"{LIEFERUNG}/konzept_KP-03.json"),
    ("contracts/bc2-to-bc3/konzept.schema.json", f"{LIEFERUNG}/konzept_KP-04.json"),
    ("contracts/bc2-to-bc3/priorisierung.schema.json", f"{LIEFERUNG}/prozesspriorisierung.json"),
]

ok = True
for schema_path, mock_path in PAIRS:
    schema = json.loads((BASE / schema_path).read_text(encoding="utf-8"))
    data = json.loads((BASE / mock_path).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        ok = False
        print(f"FAIL  {mock_path} gegen {schema_path}:")
        for e in errors:
            loc = "/".join(str(p) for p in e.path)
            print(f"   - [{loc}] {e.message}")
    else:
        # zusaetzliche fachliche Konsistenzchecks
        print(f"OK    {mock_path} -> {schema_path}")

# Zusatz-Check: Reihenfolge in gesamtempfehlung == Ranking der Priorisierung
konzept = json.loads((BASE / "contracts/examples/mock_automatisierungskonzept.json").read_text(encoding="utf-8"))
prio = json.loads((BASE / "contracts/examples/mock_prozesspriorisierung.json").read_text(encoding="utf-8"))
reihenfolge = konzept["gesamtempfehlung"]["reihenfolge_potenzial_ids"]
prio_order = [e["potenzial_id"] for e in sorted(prio["eintraege"], key=lambda e: e["rang"])]
if reihenfolge == prio_order:
    print("OK    Reihenfolge(gesamtempfehlung) == Ranking(priorisierung)")
else:
    ok = False
    print("FAIL  Reihenfolge weicht ab:", reihenfolge, "!=", prio_order)

# Zusatz-Check: alle potenzial_ids der Priorisierung existieren im Konzept
konz_ids = {p["potenzial_id"] for p in konzept["potenziale"]}
prio_ids = {e["potenzial_id"] for e in prio["eintraege"]}
if prio_ids <= konz_ids:
    print("OK    Priorisierung referenziert nur existierende Potenziale")
else:
    ok = False
    print("FAIL  Priorisierung referenziert unbekannte Potenziale:", prio_ids - konz_ids)

# ---------------------------------------------------------------------------
# Lieferung 2026-08-30 (vorlaeufig, Issue #168): drei Konzepte + eine
# Priorisierung ueber alle drei. Andere Struktur als der Mock, daher eigene Checks.
# ---------------------------------------------------------------------------
lief_konzepte = [
    json.loads((BASE / f"{LIEFERUNG}/konzept_{kp}.json").read_text(encoding="utf-8"))
    for kp in ("KP-02", "KP-03", "KP-04")
]
lief_prio = json.loads((BASE / f"{LIEFERUNG}/prozesspriorisierung.json").read_text(encoding="utf-8"))

# Jedes Konzept empfiehlt genau seine eigenen Potenziale.
for k in lief_konzepte:
    eigene = [p["potenzial_id"] for p in k["potenziale"]]
    if k["gesamtempfehlung"]["reihenfolge_potenzial_ids"] == eigene:
        print(f"OK    {k['kontext']['kp_id']}: Reihenfolge == eigene Potenziale")
    else:
        ok = False
        print(f"FAIL  {k['kontext']['kp_id']}: Reihenfolge verweist nicht auf die eigenen Potenziale")

# Die Priorisierung referenziert nur Potenziale, die es in den Konzepten gibt.
lief_konz_ids = {p["potenzial_id"] for k in lief_konzepte for p in k["potenziale"]}
lief_prio_ids = {e["potenzial_id"] for e in lief_prio["eintraege"]}
if lief_prio_ids <= lief_konz_ids:
    print("OK    Lieferung: Priorisierung referenziert nur existierende Potenziale")
else:
    ok = False
    print("FAIL  Lieferung: unbekannte Potenziale:", lief_prio_ids - lief_konz_ids)

# Alle Potenziale der Konzepte tauchen auch in der Priorisierung auf.
if lief_konz_ids <= lief_prio_ids:
    print("OK    Lieferung: alle Potenziale sind priorisiert")
else:
    ok = False
    print("FAIL  Lieferung: nicht priorisierte Potenziale:", lief_konz_ids - lief_prio_ids)

# Rang folgt dem Score absteigend, Tie-Break hoehere Einsparung.
erwartet = [
    e["potenzial_id"]
    for e in sorted(lief_prio["eintraege"], key=lambda e: (-e["score"], -e["einsparung_eur_jahr"]))
]
tatsaechlich = [e["potenzial_id"] for e in sorted(lief_prio["eintraege"], key=lambda e: e["rang"])]
if erwartet == tatsaechlich:
    print("OK    Lieferung: Rangfolge entspricht Score (Tie-Break Einsparung)")
else:
    ok = False
    print("FAIL  Lieferung: Rangfolge widerspricht dem Score")

# Vorlaeufigkeits-Kennzeichnung -- der eigentliche Zweck von #168.
MARKER = "[VORLAEUFIG]"
for k in lief_konzepte:
    kp = k["kontext"]["kp_id"]
    for p in k["potenziale"]:
        if not p["titel"].startswith(MARKER):
            ok = False
            print(f"FAIL  {kp}/{p['potenzial_id']}: Titel traegt den Marker {MARKER} nicht")
        if p["value"]["value_quelle"] != "default":
            ok = False
            print(f"FAIL  {kp}/{p['potenzial_id']}: value_quelle ist nicht 'default'")
        if not p["value"].get("annahmen") or "VORLAEUFIG" not in p["value"]["annahmen"][0]:
            ok = False
            print(f"FAIL  {kp}/{p['potenzial_id']}: erste Annahme ist keine Vorlaeufigkeits-Warnung")
    if k["gate1"]["status"] != "pending":
        ok = False
        print(f"FAIL  {kp}: gate1.status ist nicht 'pending'")
    if MARKER not in k["gate1"].get("kommentar", ""):
        ok = False
        print(f"FAIL  {kp}: gate1.kommentar warnt nicht vor der Freigabe")
    if not k["kontext"]["prozess_kurzbeschreibung"].startswith(MARKER):
        ok = False
        print(f"FAIL  {kp}: prozess_kurzbeschreibung traegt den Marker nicht")
for e in lief_prio["eintraege"]:
    if not e["titel"].startswith(MARKER):
        ok = False
        print(f"FAIL  Priorisierung/{e['potenzial_id']}: Titel traegt den Marker nicht")
print(f"OK    Lieferung: Vorlaeufigkeits-Kennzeichnung vollstaendig ({MARKER})"
      if ok else "FAIL  Lieferung: Kennzeichnung unvollstaendig")

sys.exit(0 if ok else 1)
