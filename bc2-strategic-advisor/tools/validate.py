"""contracts-validate: prueft Fixtures und Lieferungen gegen die BC2-Vertraege (Draft 2020-12).

Zwei Vertragsstaende nebeneinander, mit Absicht:

  * **v3.0** -- der aktuelle Vertrag (`contracts/bc2-to-bc3/`). Dagegen laufen die Fixtures in
    `contracts/examples/`.
  * **v2.0** -- eingefroren in `contracts/bc2-to-bc3/archiv/`. Dagegen laeuft nur noch die bereits
    uebergebene Lieferung vom 30.08.2026. Ein uebergebenes Konzept wird nie ungueltig, es veraltet
    (ADR-007 BC2, 2.4); es nachzuziehen zerstoerte, worauf die Lieferung sich beruft.

Jede **andere** Lieferung unter `contracts/bc2-to-bc3/lieferungen/` wird gefunden, nicht
aufgezaehlt, und laeuft gegen v3.0 (Abschnitt 4). Die CI startet dieses Skript bei jeder
Aenderung an der Lieferstrecke (`.github/workflows/vertraege-pruefen.yml`, #253).

Aufruf aus dem Repo-Wurzelverzeichnis:
    python3 bc2-strategic-advisor/tools/validate.py
"""
import json
import math
import pathlib
import sys

from jsonschema import Draft202012Validator

BASE = pathlib.Path(__file__).resolve().parents[2]

KONZEPT_V3 = "contracts/bc2-to-bc3/konzept.schema.json"
PRIO_V3 = "contracts/bc2-to-bc3/priorisierung.schema.json"
KONZEPT_V2 = "contracts/bc2-to-bc3/archiv/konzept.schema-v2.0.json"
PRIO_V2 = "contracts/bc2-to-bc3/archiv/priorisierung.schema-v2.0.json"

FIXTURE_KONZEPTE = [
    "contracts/examples/mock_automatisierungskonzept.json",
    "contracts/examples/mock_automatisierungskonzept_KP-05.json",
]
FIXTURE_PRIO = "contracts/examples/mock_prozesspriorisierung.json"
LIEFERUNG = "contracts/bc2-to-bc3/lieferungen/2026-08-30-vorlaeufig"

PAARE = (
    [(KONZEPT_V3, p) for p in FIXTURE_KONZEPTE]
    + [(PRIO_V3, FIXTURE_PRIO)]
    + [
        # Eingangsseite: BC1s Prozessprofil, geschnitten gegen die Zeilen vom 08.09.2026 (#184).
        ("contracts/bc1-to-bc2/prozessprofil.schema.json", "contracts/examples/beispiel_bc1_prozessprofil.json"),
        # Eingefroren: die uebergebene Lieferung gegen die archivierten v2-Schemas.
        (KONZEPT_V2, f"{LIEFERUNG}/konzept_KP-02.json"),
        (KONZEPT_V2, f"{LIEFERUNG}/konzept_KP-03.json"),
        (KONZEPT_V2, f"{LIEFERUNG}/konzept_KP-04.json"),
        (PRIO_V2, f"{LIEFERUNG}/prozesspriorisierung.json"),
        # Alle anderen Lieferungen findet Abschnitt 4 selbst und prueft sie gegen v3.0.
    ]
)

ok = True


def lies(pfad):
    return json.loads((BASE / pfad).read_text(encoding="utf-8"))


def pruefe(bedingung, gut, schlecht):
    global ok
    if bedingung:
        print(f"OK    {gut}")
    else:
        ok = False
        print(f"FAIL  {schlecht}")


def kfm(x):
    """Kaufmaennisch runden -- dieselbe Regel wie in migriere_bc3_vorlage.py, nicht Pythons round()."""
    return int(math.floor(x + 0.5))


# ---------------------------------------------------------------------------
# 1. Schema-Gueltigkeit
# ---------------------------------------------------------------------------
for schema_pfad, daten_pfad in PAARE:
    schema = lies(schema_pfad)
    daten = lies(daten_pfad)
    fehler = sorted(Draft202012Validator(schema).iter_errors(daten), key=lambda e: list(e.path))
    if fehler:
        ok = False
        print(f"FAIL  {daten_pfad} gegen {schema_pfad}:")
        for e in fehler:
            ort = "/".join(str(p) for p in e.path)
            print(f"   - [{ort}] {e.message}")
    else:
        print(f"OK    {daten_pfad} -> {schema_pfad}")

# ---------------------------------------------------------------------------
# 2. Fixtures v3.0 -- fachliche Konsistenz
#    Die Schema-Pruefung sagt, dass die Felder da sind. Hier wird geprueft, ob sie
#    zueinander passen: das Rechenmodell aus ADR-006 BC2 laesst sich nachrechnen, und die
#    beiden Artefakte eines Laufs widersprechen sich nicht.
# ---------------------------------------------------------------------------
print("\n--- Fixtures v3.0 ---")
konzepte = [lies(p) for p in FIXTURE_KONZEPTE]
prio = lies(FIXTURE_PRIO)
potenziale = {p["potenzial_id"]: (k, p) for k in konzepte for p in k["potenziale"]}

# 2.1 Der Lauf haelt zusammen: ein Mandant, ein Paket, ein Zeitanker, eine Fassung.
lauf_konzept = {(k["company_id"], k["paket_id"], k["uebergeben_am"], k["fassung"]) for k in konzepte}
lauf_prio = (prio["company_id"], prio["paket_id"], prio["uebergeben_am"], prio["fassung"])
pruefe(
    lauf_konzept == {lauf_prio},
    "Lauf: Konzepte und Priorisierung tragen dieselbe (company_id, paket_id, uebergeben_am, fassung)",
    f"Lauf uneinheitlich: Konzepte {lauf_konzept} gegen Priorisierung {lauf_prio}",
)
pruefe(
    set(prio["konzept_ids"]) == {k["konzept_id"] for k in konzepte},
    f"Lauf: die Priorisierung listet genau ihre {len(konzepte)} Konzepte",
    f"Priorisierung listet {prio['konzept_ids']}, vorhanden sind {[k['konzept_id'] for k in konzepte]}",
)

# 2.2 gate1 gehoert seit v3.0 zur Priorisierung, nicht zum Konzept (ADR-007 BC2, 2.1).
pruefe(
    all("gate1" not in k for k in konzepte),
    "gate1: steht nicht mehr im Konzept",
    "gate1 steht noch in einem Konzept -- seit v3.0 gehoert er in die Priorisierung",
)
pruefe("gate1" in prio, "gate1: steht in der Priorisierung", "gate1 fehlt in der Priorisierung")

# 2.3 Ein Konzept deckt genau einen Kernprozess ab, und jedes Potenzial nennt seine Teilprozesse.
for k in konzepte:
    kp = k["kontext"]["kp_id"]
    fremd = [
        tp
        for p in k["potenziale"]
        for tp in p["betroffene_teilprozess_ids"]
        if not tp.startswith(kp + ".")
    ]
    pruefe(
        not fremd,
        f"{kp}: alle Teilprozess-IDs liegen unter dem eigenen Kernprozess",
        f"{kp}: fremde Teilprozess-IDs {fremd} -- der Kernprozess ist das Praefix, keine eigene Erhebung",
    )

# 2.4 Das Rechenmodell aus ADR-006 BC2 laesst sich nachrechnen.
for pid, (k, p) in sorted(potenziale.items()):
    kurz = f"{k['kontext']['kp_id']}/{p['titel'][:34]}"

    mittel = round(sum(p["nutzwert"][c]["wert"] for c in
                       ("qualitaet", "durchlaufzeit", "fehlerreduktion",
                        "mitarbeiterzufriedenheit", "compliance")) / 5, 1)
    pruefe(
        abs(mittel - p["nutzwert"]["mittel"]) < 0.05,
        f"{kurz}: nutzwert.mittel ist das ungewichtete Mittel der fuenf Kategorien",
        f"{kurz}: nutzwert.mittel {p['nutzwert']['mittel']}, gerechnet {mittel}",
    )

    teil = p["impact_monetaer"] if p["impact_monetaer"] is not None else p["nutzwert"]["mittel"]
    erwartet_impact = kfm((teil + p["nutzwert"]["mittel"]) / 2)
    pruefe(
        p["impact"] == erwartet_impact,
        f"{kurz}: impact = round((impact_monetaer + nutzwert) / 2)",
        f"{kurz}: impact {p['impact']}, gerechnet {erwartet_impact}",
    )

    erwartet_score = p["impact"] * (11 - p["umsetzungskomplexitaet"])
    pruefe(
        p["prioritaet_score"] == erwartet_score,
        f"{kurz}: score = impact x (11 - umsetzungskomplexitaet)",
        f"{kurz}: score {p['prioritaet_score']}, gerechnet {erwartet_score}",
    )

    if p["impact"] >= 6:
        erwartet_kat = "Quick Win" if p["umsetzungskomplexitaet"] <= 5 else "Strategisch"
    else:
        erwartet_kat = "Optional" if p["umsetzungskomplexitaet"] <= 5 else "Zurueckgestellt"
    pruefe(
        p["kategorie"] == erwartet_kat,
        f"{kurz}: kategorie folgt dem Quadranten",
        f"{kurz}: kategorie '{p['kategorie']}', erwartet '{erwartet_kat}'",
    )

    s = p["prioritaet_score"]
    erwartet_gruppe = "PRIO 1" if s >= 50 else ("PRIO 2" if s >= 20 else "PRIO 3")
    pruefe(
        p["prioritaetsgruppe"] == erwartet_gruppe,
        f"{kurz}: prioritaetsgruppe folgt den Score-Baendern",
        f"{kurz}: gruppe '{p['prioritaetsgruppe']}' bei Score {s}, erwartet '{erwartet_gruppe}'",
    )

    # Spannen: min <= max, und der Automatisierungsgrad liegt im Korridor seiner Klasse.
    spannen = [f for f in ("ist_kosten_eur_jahr", "einsparung_eur_jahr", "ersparnis_prozent",
                           "amortisation_monate") if f in p["value"]]
    kaputt = [f for f in spannen if p["value"][f]["min"] > p["value"][f]["max"]]
    pruefe(
        not kaputt,
        f"{kurz}: alle Spannen laufen von min nach max",
        f"{kurz}: verdrehte Spannen {kaputt}",
    )
    ag = p["automatisierungsgrad"]
    pruefe(
        ag["angesetzt_min_pct"] <= ag["angesetzt_max_pct"],
        f"{kurz}: Automatisierungsgrad ist eine Spanne, kein Punktwert",
        f"{kurz}: Automatisierungsgrad {ag['angesetzt_min_pct']}-{ag['angesetzt_max_pct']} %",
    )

# 2.5 Konzept und Priorisierung widersprechen sich nicht.
prio_ids = {e["potenzial_id"] for e in prio["eintraege"]}
pruefe(
    prio_ids == set(potenziale),
    f"Priorisierung: alle {len(potenziale)} Potenziale der Konzepte sind genau einmal gelistet",
    f"Priorisierung: fehlend {set(potenziale) - prio_ids}, unbekannt {prio_ids - set(potenziale)}",
)

abweichend = []
for e in prio["eintraege"]:
    _, p = potenziale[e["potenzial_id"]]
    if (e["potenzialrang"], e["score"], e["prioritaetsgruppe"], e["kategorie"]) != (
        p["potenzialrang"], p["prioritaet_score"], p["prioritaetsgruppe"], p["kategorie"]
    ):
        abweichend.append(e["titel"][:34])
pruefe(
    not abweichend,
    "Priorisierung: Rang, Score, Gruppe und Kategorie stimmen mit den Konzepten ueberein",
    f"Priorisierung weicht vom Konzept ab bei: {abweichend}",
)

erwartet = [e["potenzial_id"] for e in sorted(
    prio["eintraege"],
    key=lambda e: (-e["score"], -(e["einsparung_eur_jahr"] or {"max": 0})["max"]),
)]
tatsaechlich = [e["potenzial_id"] for e in sorted(prio["eintraege"], key=lambda e: e["potenzialrang"])]
pruefe(
    erwartet == tatsaechlich,
    "Priorisierung: der Potenzialrang folgt strikt dem Score (Tie-Break Einsparung)",
    "Priorisierung: der Potenzialrang widerspricht dem Score",
)

# 2.6 Der Prozessrang ist der Rang des BESTEN Potenzials (ADR-006 BC2, 2.7).
bester_je_kp = {}
for e in prio["eintraege"]:
    if e["kp_id"] not in bester_je_kp or e["potenzialrang"] < bester_je_kp[e["kp_id"]]["potenzialrang"]:
        bester_je_kp[e["kp_id"]] = e
erwartet_reihenfolge = [kp for kp, _ in sorted(bester_je_kp.items(), key=lambda kv: kv[1]["potenzialrang"])]
tatsaechliche_reihenfolge = [r["kp_id"] for r in sorted(prio["prozess_raenge"], key=lambda r: r["prozessrang"])]
pruefe(
    erwartet_reihenfolge == tatsaechliche_reihenfolge,
    "Prozessrang: folgt dem jeweils besten Potenzial",
    f"Prozessrang {tatsaechliche_reihenfolge}, erwartet {erwartet_reihenfolge}",
)
falsch_bestes = [
    r["kp_id"] for r in prio["prozess_raenge"]
    if r["bestes_potenzial_id"] != bester_je_kp[r["kp_id"]]["potenzial_id"]
]
pruefe(
    not falsch_bestes,
    "Prozessrang: bestes_potenzial_id zeigt auf das hoechstrangige Potenzial des Kernprozesses",
    f"Prozessrang: falsches bestes Potenzial bei {falsch_bestes}",
)

# 2.7 Die Empfehlung eines Konzepts umfasst genau seine eigenen Potenziale.
for k in konzepte:
    eigene = [p["potenzial_id"] for p in sorted(
        k["potenziale"], key=lambda p: p["potenzialrang"])]
    pruefe(
        k["gesamtempfehlung"]["reihenfolge_potenzial_ids"] == eigene,
        f"{k['kontext']['kp_id']}: gesamtempfehlung == eigene Potenziale in Rangfolge",
        f"{k['kontext']['kp_id']}: gesamtempfehlung {k['gesamtempfehlung']['reihenfolge_potenzial_ids']} != {eigene}",
    )

# 2.8 Die Akzeptanzkriterien tragen beide Teile -- Given/When/Then UND messverfahren (#186).
ohne_gwt = [
    p["titel"][:34]
    for _, p in potenziale.values()
    for a in p["akzeptanzkriterien_geschaeftlich"]
    if not a["kriterium"].lower().startswith("gegeben")
]
pruefe(
    not ohne_gwt,
    "Akzeptanzkriterien: durchgaengig Given/When/Then (beginnen mit 'Gegeben')",
    f"Akzeptanzkriterien ohne Given/When/Then bei: {sorted(set(ohne_gwt))}",
)
ohne_story = [p["titel"][:34] for _, p in potenziale.values()
              if not p["user_story"].lower().startswith("als ")]
pruefe(
    not ohne_story,
    "User Stories: durchgaengig SOPHIST ('Als ... moechte ... damit')",
    f"User Stories ohne SOPHIST-Schablone bei: {ohne_story}",
)

# ---------------------------------------------------------------------------
# 3. Lieferung 2026-08-30 (v2.0, eingefroren) -- unveraendert uebernommene Pruefungen.
#    Drei Konzepte + eine Priorisierung ueber alle drei, mit Vorlaeufigkeits-Kennzeichnung (#168).
# ---------------------------------------------------------------------------
print("\n--- Lieferung 2026-08-30 (eingefroren auf v2.0) ---")
lief_konzepte = [lies(f"{LIEFERUNG}/konzept_{kp}.json") for kp in ("KP-02", "KP-03", "KP-04")]
lief_prio = lies(f"{LIEFERUNG}/prozesspriorisierung.json")

for k in lief_konzepte:
    eigene = [p["potenzial_id"] for p in k["potenziale"]]
    pruefe(
        k["gesamtempfehlung"]["reihenfolge_potenzial_ids"] == eigene,
        f"{k['kontext']['kp_id']}: Reihenfolge == eigene Potenziale",
        f"{k['kontext']['kp_id']}: Reihenfolge verweist nicht auf die eigenen Potenziale",
    )

lief_konz_ids = {p["potenzial_id"] for k in lief_konzepte for p in k["potenziale"]}
lief_prio_ids = {e["potenzial_id"] for e in lief_prio["eintraege"]}
pruefe(
    lief_prio_ids == lief_konz_ids,
    "Lieferung: Priorisierung und Konzepte decken dieselben Potenziale ab",
    f"Lieferung: unbekannt {lief_prio_ids - lief_konz_ids}, nicht priorisiert {lief_konz_ids - lief_prio_ids}",
)

erwartet = [e["potenzial_id"] for e in sorted(
    lief_prio["eintraege"], key=lambda e: (-e["score"], -e["einsparung_eur_jahr"]))]
tatsaechlich = [e["potenzial_id"] for e in sorted(lief_prio["eintraege"], key=lambda e: e["rang"])]
pruefe(
    erwartet == tatsaechlich,
    "Lieferung: Rangfolge entspricht dem Score (Tie-Break Einsparung)",
    "Lieferung: Rangfolge widerspricht dem Score",
)

MARKER = "[VORLAEUFIG]"
kennzeichnung_ok = True
for k in lief_konzepte:
    kp = k["kontext"]["kp_id"]
    for p in k["potenziale"]:
        if not p["titel"].startswith(MARKER):
            kennzeichnung_ok = False
            print(f"FAIL  {kp}/{p['potenzial_id']}: Titel traegt den Marker {MARKER} nicht")
        if p["value"]["value_quelle"] != "default":
            kennzeichnung_ok = False
            print(f"FAIL  {kp}/{p['potenzial_id']}: value_quelle ist nicht 'default'")
        if not p["value"].get("annahmen") or "VORLAEUFIG" not in p["value"]["annahmen"][0]:
            kennzeichnung_ok = False
            print(f"FAIL  {kp}/{p['potenzial_id']}: erste Annahme ist keine Vorlaeufigkeits-Warnung")
    if k["gate1"]["status"] != "pending":
        kennzeichnung_ok = False
        print(f"FAIL  {kp}: gate1.status ist nicht 'pending'")
    if MARKER not in k["gate1"].get("kommentar", ""):
        kennzeichnung_ok = False
        print(f"FAIL  {kp}: gate1.kommentar warnt nicht vor der Freigabe")
    if not k["kontext"]["prozess_kurzbeschreibung"].startswith(MARKER):
        kennzeichnung_ok = False
        print(f"FAIL  {kp}: prozess_kurzbeschreibung traegt den Marker nicht")
for e in lief_prio["eintraege"]:
    if not e["titel"].startswith(MARKER):
        kennzeichnung_ok = False
        print(f"FAIL  Priorisierung/{e['potenzial_id']}: Titel traegt den Marker nicht")
pruefe(
    kennzeichnung_ok,
    f"Lieferung: Vorlaeufigkeits-Kennzeichnung vollstaendig ({MARKER})",
    "Lieferung: Kennzeichnung unvollstaendig",
)

# ---------------------------------------------------------------------------
# 4. Lieferungen v3.0 -- JEDER Ordner unter lieferungen/, nicht eine feste Liste (#253).
#    Bis #253 stand hier genau ein Ordner, fest eingetragen. Eine neue Lieferung per PR waere
#    damit gruen gewesen, ohne je geprueft worden zu sein -- das Netz aus ADR-007 BC2, 2.2
#    haette genau die Faelle durchgelassen, fuer die es da ist. Jetzt gilt: was unter
#    lieferungen/ liegt und nicht die eingefrorene v2-Lieferung ist, laeuft gegen v3.0.
#    Ein neuer Vertragsstand faellt damit rot auf (schema_version ist const), bis er hier
#    eingetragen ist -- gewollt.
# ---------------------------------------------------------------------------
LIEFERUNGEN = BASE / "contracts/bc2-to-bc3/lieferungen"
#: Ordner, die oben gegen die archivierten v2-Schemas laufen und hier nicht noch einmal.
EINGEFROREN_V2 = {pathlib.Path(LIEFERUNG).name}


def lies_sicher(datei, ordner_name):
    """Liest JSON; ein Lesefehler ist ein Befund, kein Absturz des ganzen Laufs."""
    global ok
    try:
        return json.loads(datei.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 -- jeder Lesefehler ist ein FAIL dieser Lieferung
        ok = False
        print(f"FAIL  {ordner_name}/{datei.name}: kein gueltiges JSON ({e})")
        return None


def schema_gueltig(schema_pfad, daten, anzeige):
    global ok
    fehler = sorted(Draft202012Validator(lies(schema_pfad)).iter_errors(daten),
                    key=lambda e: list(e.path))
    if fehler:
        ok = False
        print(f"FAIL  {anzeige} gegen {schema_pfad}:")
        for e in fehler:
            print(f"   - [{'/'.join(str(p) for p in e.path)}] {e.message}")
        return False
    print(f"OK    {anzeige} -> {schema_pfad}")
    return True


def pruefe_kennzeichnung_sim(name, konzepte, prio):
    """Eine simulierte Lieferung (paket_id beginnt mit SIM-) muss sich als solche zu erkennen geben.

    Ohne Marker ist sie von einer echten nicht mehr zu unterscheiden -- genau darum ging es in #168.
    """
    marker = "[SIMULIERT]"
    sim_ok = True
    for k in konzepte:
        kp = k["kontext"]["kp_id"]
        for p in k["potenziale"]:
            if not p["titel"].startswith(marker):
                sim_ok = False
                print(f"FAIL  {name}/{kp}/{p['potenzial_id']}: Titel traegt den Marker {marker} nicht")
            if p["value"]["value_quelle"] != "annahme":
                sim_ok = False
                print(f"FAIL  {name}/{kp}/{p['potenzial_id']}: value_quelle ist nicht 'annahme'")
            if not p["value"].get("annahmen") or not p["value"]["annahmen"][0].startswith("GESETZT"):
                sim_ok = False
                print(f"FAIL  {name}/{kp}/{p['potenzial_id']}: erste Annahme ist keine Herkunftswarnung")
            if not p["beschreibung"].startswith("SIMULIERT"):
                sim_ok = False
                print(f"FAIL  {name}/{kp}/{p['potenzial_id']}: beschreibung beginnt ohne Warnblock")
        if not k["kontext"]["prozess_kurzbeschreibung"].startswith(marker):
            sim_ok = False
            print(f"FAIL  {name}/{kp}: prozess_kurzbeschreibung traegt den Marker nicht")
    if prio["gate1"]["status"] != "pending":
        sim_ok = False
        print(f"FAIL  {name}: gate1.status ist nicht 'pending'")
    if "FREIGABESPERRE" not in prio["gate1"].get("kommentar", ""):
        sim_ok = False
        print(f"FAIL  {name}: gate1.kommentar warnt nicht vor der Freigabe")
    for e in prio["eintraege"]:
        if not e["titel"].startswith(marker):
            sim_ok = False
            print(f"FAIL  {name}/Priorisierung/{e['potenzial_id']}: Titel traegt den Marker nicht")
    pruefe(
        sim_ok,
        f"{name}: Simulation vollstaendig gekennzeichnet ({marker})",
        f"{name}: Simulation unvollstaendig gekennzeichnet",
    )


def pruefe_lieferung_v3(ordner):
    """Eine Lieferung nach ADR-007 BC2: n Konzepte, eine Priorisierung, ein Lauf."""
    global ok
    name = ordner.name
    rel = ordner.relative_to(BASE).as_posix()
    print(f"\n--- Lieferung {name} (v3.0) ---")

    konzept_dateien = sorted(ordner.glob("konzept_*.json"))
    prio_datei = ordner / "prozesspriorisierung.json"
    if not konzept_dateien or not prio_datei.exists():
        ok = False
        fehlt = [x for x, da in (("konzept_*.json", bool(konzept_dateien)),
                                 ("prozesspriorisierung.json", prio_datei.exists())) if not da]
        print(f"FAIL  {name}: es fehlt {', '.join(fehlt)} -- eine Lieferung ist eine "
              f"Priorisierung und ihre Konzepte (ADR-007 BC2, 2.1)")
        return

    # 4.1 Schema. Erst wenn alles schema-gueltig ist, lohnt der fachliche Teil -- vorher
    #     wuerde er an fehlenden Feldern abstuerzen statt einen Befund zu melden.
    konzepte, alles_gueltig = [], True
    for datei in konzept_dateien:
        daten = lies_sicher(datei, name)
        gueltig = daten is not None and schema_gueltig(KONZEPT_V3, daten, f"{rel}/{datei.name}")
        alles_gueltig &= gueltig
        konzepte.append(daten)
    prio = lies_sicher(prio_datei, name)
    alles_gueltig &= prio is not None and schema_gueltig(PRIO_V3, prio, f"{rel}/{prio_datei.name}")
    if not alles_gueltig:
        print(f"      {name}: nicht schema-gueltig -- fachliche Pruefung uebersprungen")
        return

    # 4.2 Der Lauf haelt zusammen: ein Mandant, ein Paket, ein Zeitanker, eine Fassung.
    def lauf(d):
        return (d["company_id"], d["paket_id"], d["uebergeben_am"], d["fassung"])

    laeufe = {lauf(k) for k in konzepte} | {lauf(prio)}
    pruefe(
        len(laeufe) == 1,
        f"{name}: Konzepte und Priorisierung tragen denselben Lauf",
        f"{name}: Lauf uneinheitlich -- {sorted(laeufe)}",
    )
    pruefe(
        sorted(prio["konzept_ids"]) == sorted(k["konzept_id"] for k in konzepte),
        f"{name}: die Priorisierung listet genau ihre {len(konzepte)} Konzept(e)",
        f"{name}: Priorisierung listet {prio['konzept_ids']}, vorhanden sind "
        f"{[k['konzept_id'] for k in konzepte]}",
    )
    pruefe(
        all("gate1" not in k for k in konzepte),
        f"{name}: gate1 steht nicht im Konzept",
        f"{name}: gate1 steht im Konzept -- seit v3.0 gehoert er in die Priorisierung",
    )

    # 4.3 Konzepte und Priorisierung decken dieselben Potenziale ab, jedes genau einmal.
    konz_ids = [p["potenzial_id"] for k in konzepte for p in k["potenziale"]]
    prio_ids = [e["potenzial_id"] for e in prio["eintraege"]]
    pruefe(
        sorted(konz_ids) == sorted(prio_ids) and len(set(prio_ids)) == len(prio_ids),
        f"{name}: Priorisierung und Konzepte decken dieselben {len(konz_ids)} Potenziale ab",
        f"{name}: Konzepte fuehren {sorted(konz_ids)}, Priorisierung {sorted(prio_ids)}",
    )

    # 4.4 Die Rangfolge ist die des Rechenkerns: Score absteigend, dann potenzial_id
    #     (app/modell/rechnen.py). Die Fixtures brechen den Gleichstand anders -- sie stammen
    #     aus BC3s Vorlage, nicht aus dem Kern.
    erwartet = [e["potenzial_id"] for e in sorted(
        prio["eintraege"], key=lambda e: (-e["score"], e["potenzial_id"]))]
    tatsaechlich = [e["potenzial_id"] for e in sorted(
        prio["eintraege"], key=lambda e: e["potenzialrang"])]
    pruefe(
        erwartet == tatsaechlich,
        f"{name}: Rangfolge entspricht dem Score",
        f"{name}: Rangfolge widerspricht dem Score",
    )
    for k in konzepte:
        eigene = [p["potenzial_id"] for p in sorted(k["potenziale"], key=lambda p: p["potenzialrang"])]
        pruefe(
            k["gesamtempfehlung"]["reihenfolge_potenzial_ids"] == eigene,
            f"{name}/{k['kontext']['kp_id']}: gesamtempfehlung == eigene Potenziale in Rangfolge",
            f"{name}/{k['kontext']['kp_id']}: gesamtempfehlung weicht von der Rangfolge ab",
        )

    # 4.5 Der Ordnername sagt, was drin ist: <company>-<paket_id>-f<n> (ADR-007 BC2, 2.2/2.5).
    #     Faellt die paket_id oder die Fassung aus dem Namen, zeigt ein `git pull` bei BC3 eine
    #     Lieferung, der man von aussen nicht mehr ansieht, welcher Lauf sie ist.
    endung = f"-{prio['paket_id']}-f{prio['fassung']}"
    pruefe(
        name.endswith(endung),
        f"{name}: Ordnername traegt paket_id und Fassung ('...{endung}')",
        f"{name}: Ordnername passt nicht zu paket_id und Fassung -- erwartet '<company>{endung}'",
    )

    # 4.6 Eine simulierte Lieferung muss als solche erkennbar bleiben (#168).
    if prio["paket_id"].startswith("SIM-"):
        pruefe_kennzeichnung_sim(name, konzepte, prio)


v3_ordner = sorted(o for o in LIEFERUNGEN.iterdir() if o.is_dir() and o.name not in EINGEFROREN_V2)
for o in v3_ordner:
    pruefe_lieferung_v3(o)
print(f"\n{len(v3_ordner)} Lieferung(en) gegen v3.0 geprueft: "
      f"{', '.join(o.name for o in v3_ordner) or '(keine)'}")

print("\nGESAMT: " + ("gruen" if ok else "ROT -- siehe FAIL-Zeilen oben"))
sys.exit(0 if ok else 1)
