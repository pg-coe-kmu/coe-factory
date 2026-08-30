"""contracts-validate: prueft alle Mocks gegen die v2-Schemas (Draft 2020-12)."""
import json, sys, pathlib
from jsonschema import Draft202012Validator

BASE = pathlib.Path(__file__).resolve().parents[2]
PAIRS = [
    ("contracts/bc2-to-bc3/konzept.schema.json", "contracts/examples/mock_automatisierungskonzept.json"),
    ("contracts/bc2-to-bc3/priorisierung.schema.json", "contracts/examples/mock_prozesspriorisierung.json"),
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

sys.exit(0 if ok else 1)
