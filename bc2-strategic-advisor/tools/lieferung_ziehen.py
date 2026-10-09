#!/usr/bin/env python3
"""
BC2 · Die Lieferung an BC3 aus Schema ``bc2`` in den Lieferordner ziehen (#306).

Die Datenbank ist der eine Ort, der Lieferordner ihre Abbildung (ADR-007 · BC2,
Nachtrag #305). Der Dienst schreibt keine Lieferdateien; dieses Werkzeug holt,
was geliefert ist, und schreibt es in den Arbeitsbaum. Den PR öffnet ein Mensch,
``validate.py`` prüft ihn in der CI (#253).

Aus dem Repo-Wurzelverzeichnis::

    python3 bc2-strategic-advisor/tools/lieferung_ziehen.py            # über ssh bc2
    python3 bc2-strategic-advisor/tools/lieferung_ziehen.py --pruefen  # nur ansehen
    python3 bc2-strategic-advisor/tools/lieferung_ziehen.py --aus lieferungen.json

Ohne ``--aus`` ruft es ``ssh bc2 docker exec app-app-1 python -m lieferung``; das
liest im Betriebscontainer mit einer ``readonly``-Sitzung, die ``DATABASE_URL``
verlässt den Server nicht (ADR-003).

**Keine Markierung „geliefert“** (Nachtrag #305, Punkt 3). Das Werkzeug erzeugt
jeden gelieferten Lauf neu, byte-gleich: Schlüssel in der Reihenfolge des
Vertragsschemas, zwei Leerzeichen Einzug, UTF-8, Zeilenende am Schluss. Liegt
ein Ordner schon da und käme jetzt anders heraus, **bricht es ab, bevor es
irgendetwas schreibt**, und zeigt den Unterschied. Was übergeben ist, ändert
sich nicht — und eine Codeänderung, die die Vertragsform still verschiebt,
fällt hier zuerst auf.
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
VERTRAG = BASE / "contracts" / "bc2-to-bc3"
LIEFERUNGEN = VERTRAG / "lieferungen"
KONZEPT_SCHEMA = VERTRAG / "konzept.schema.json"
PRIO_SCHEMA = VERTRAG / "priorisierung.schema.json"

PRIO_DATEI = "prozesspriorisierung.json"
NACHRICHT_DATEI = "NACHRICHT_AN_BC3.md"

SSH_AUFRUF = ["ssh", "bc2", "docker", "exec", "app-app-1", "python", "-m", "lieferung"]


# ---------------------------------------------------------------------------
# Byte-gleich: Schlüssel nach dem Schema ordnen
# ---------------------------------------------------------------------------


def _aufloesen(knoten: dict, wurzel: dict) -> dict:
    """Folgt ``$ref`` und wählt aus ``anyOf``/``oneOf``/``allOf`` den Zweig, der
    eine Gestalt hat — für die Reihenfolge genügt das, geprüft wird anderswo."""
    while "$ref" in knoten:
        teile = knoten["$ref"].lstrip("#/").split("/")
        ziel = wurzel
        for t in teile:
            ziel = ziel[t]
        knoten = ziel
    if "properties" in knoten or "items" in knoten:
        return knoten
    for schluessel in ("anyOf", "oneOf", "allOf"):
        for zweig in knoten.get(schluessel, []):
            zweig = _aufloesen(zweig, wurzel)
            if "properties" in zweig or "items" in zweig:
                return zweig
    return knoten


def ordne(daten, knoten: dict | None, wurzel: dict):
    """Ordnet die Schlüssel wie im Schema; Unbekanntes alphabetisch dahinter.

    Nötig, weil Postgres ``jsonb`` die Reihenfolge nicht bewahrt — es gibt die
    Schlüssel kurz vor lang zurück. Byte-gleich wäre auch das, lesbar nicht.
    """
    knoten = _aufloesen(knoten or {}, wurzel)
    if isinstance(daten, dict):
        eigenschaften = knoten.get("properties", {})
        reihe = [k for k in eigenschaften if k in daten]
        reihe += sorted(k for k in daten if k not in eigenschaften)
        return {k: ordne(daten[k], eigenschaften.get(k), wurzel) for k in reihe}
    if isinstance(daten, list):
        items = knoten.get("items")
        return [ordne(x, items if isinstance(items, dict) else None, wurzel) for x in daten]
    return daten


def als_text(daten) -> str:
    return json.dumps(daten, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Die Nachricht an BC3
# ---------------------------------------------------------------------------


def _reihenfolge(gesetzt: list[str], gerechnet: list[str]) -> list[str]:
    return list(gesetzt) if gesetzt else list(gerechnet)


def nachricht(lieferung: dict) -> str:
    """Kurz und ohne Zeitpunkt des Ziehens — sonst wäre der zweite Zug nicht byte-gleich."""
    p = lieferung["priorisierung"]
    g = p["gate1"]
    kp_namen = lieferung.get("kp_namen") or {}
    verwiesen = lieferung.get("verwiesen") or {}
    konzepte = {k["kontext"]["kp_id"]: k for k in lieferung["konzepte"]}
    mandant = ((p.get("ausgangslage") or {}).get("unternehmen") or {}).get("name")

    eintraege = {e["potenzial_id"]: e for e in p["eintraege"]}
    potenzialfolge = _reihenfolge(
        g.get("finale_reihenfolge_potenzial_ids") or [],
        [e["potenzial_id"] for e in sorted(p["eintraege"], key=lambda e: e["potenzialrang"])],
    )
    prozessfolge = _reihenfolge(
        g.get("finale_prozessreihenfolge_kp_ids") or [],
        [r["kp_id"] for r in sorted(p["prozess_raenge"], key=lambda r: r["prozessrang"])],
    )
    nicht = {n["potenzial_id"]: n["begruendung"] for n in g.get("nicht_freigegeben") or []}

    def verweis(pid: str) -> str:
        v = verwiesen.get(pid) or {}
        titel = v.get("titel") or "unbekannt"
        herkunft = f", Paket {v['paket_id']}" if v.get("paket_id") else ""
        return f"{titel} (`{pid}`{herkunft})"

    freigabe = f"freigegeben am {g.get('entschieden_am', 'unbekannt')}"
    if g.get("entscheider"):
        freigabe += f" durch {g['entscheider']}"

    z = [
        f"# Lieferung an BC3 — {lieferung['ordner']}",
        "",
        "> Maschinell erzeugt von `bc2-strategic-advisor/tools/lieferung_ziehen.py` aus Schema",
        "> `bc2` (ADR-007 · BC2, Nachtrag #305). Nicht von Hand ändern: der nächste Zug bricht",
        "> dann ab, weil eine Lieferung sich nach der Übergabe nicht mehr ändert.",
        "",
        "| | |",
        "|---|---|",
        f"| Mandant | {mandant or '—'} (`{p['company_id']}`) |",
        f"| Paket | `{p['paket_id']}`, übergeben am {p['uebergeben_am']} |",
        f"| Fassung | f{p['fassung']} |",
        f"| Gate 1 | {freigabe} |",
        f"| Vertrag | {p['schema_version']} |",
        "",
        "## Konzepte in finaler Reihenfolge",
        "",
    ]
    for i, kp in enumerate(prozessfolge, 1):
        k = konzepte[kp]
        name = kp_namen.get(kp)
        z.append(f"{i}. **{kp}{' — ' + name if name else ''}** · `konzept_{kp}.json`")
        if k.get("ersetzt_konzept_id"):
            z.append(f"   - ersetzt Konzept `{k['ersetzt_konzept_id']}` aus der vorigen Fassung")
        alte = {p_["potenzial_id"]: p_.get("ersetzt_potenzial_ids") or [] for p_ in k["potenziale"]}
        for pid in potenzialfolge:
            e = eintraege[pid]
            if e["kp_id"] != kp:
                continue
            if pid in nicht:
                z.append(f"   - ~~{e['titel']}~~ — nicht freigegeben: {nicht[pid]}")
            else:
                z.append(f"   - {e['titel']} · {e['prioritaetsgruppe']} · Score {e['score']}")
            for alt in alte.get(pid, []):
                z.append(f"     - schreibt fort: {verweis(alt)}")
    gestrichen = p.get("gestrichene_potenziale") or []
    if gestrichen:
        z += ["", "## Gestrichen", ""]
        z += [f"- {verweis(s['potenzial_id'])}: {s['begruendung']}" for s in gestrichen]
    if g.get("abweichungsbegruendung"):
        z += ["", "## Abweichung vom gerechneten Rang", "", g["abweichungsbegruendung"]]
    hinweise = lieferung.get("hinweise") or []
    if hinweise:
        z += ["", "## Hinweise", ""]
        z += [f"- {h}" for h in hinweise]
    return "\n".join(z) + "\n"


# ---------------------------------------------------------------------------
# Dateien und Abgleich
# ---------------------------------------------------------------------------


def dateien(lieferung: dict, prio_schema: dict, konzept_schema: dict) -> dict[str, str]:
    """Name → Inhalt aller Dateien eines Lieferordners."""
    ergebnis = {PRIO_DATEI: als_text(ordne(lieferung["priorisierung"], prio_schema, prio_schema))}
    for k in lieferung["konzepte"]:
        name = f"konzept_{k['kontext']['kp_id']}.json"
        ergebnis[name] = als_text(ordne(k, konzept_schema, konzept_schema))
    ergebnis[NACHRICHT_DATEI] = nachricht(lieferung)
    return dict(sorted(ergebnis.items()))


@dataclass
class Abgleich:
    neu: list[str]
    gleich: list[str]
    #: Ordner → Unterschiede als Text. Nicht leer heißt: nichts schreiben.
    abweichend: dict[str, str]


def abgleichen(soll: dict[str, dict[str, str]], basis: Path) -> Abgleich:
    neu, gleich, abweichend = [], [], {}
    for ordner, inhalt in soll.items():
        pfad = basis / ordner
        if not pfad.exists():
            neu.append(ordner)
            continue
        vorhanden = {d.name: d.read_text(encoding="utf-8") for d in pfad.iterdir() if d.is_file()}
        unterschied = []
        for name in sorted(set(vorhanden) | set(inhalt)):
            alt, frisch = vorhanden.get(name, ""), inhalt.get(name, "")
            if alt != frisch:
                unterschied += difflib.unified_diff(
                    alt.splitlines(keepends=True), frisch.splitlines(keepends=True),
                    f"liegt/{ordner}/{name}", f"kaeme/{ordner}/{name}",
                )
        if unterschied:
            abweichend[ordner] = "".join(unterschied)
        else:
            gleich.append(ordner)
    return Abgleich(neu, gleich, abweichend)


def schreiben(soll: dict[str, dict[str, str]], ordner: list[str], basis: Path) -> None:
    for name in ordner:
        pfad = basis / name
        pfad.mkdir(parents=True)
        for datei, text in soll[name].items():
            (pfad / datei).write_text(text, encoding="utf-8")


def ziehe(
    roh: dict, basis: Path = LIEFERUNGEN, *, pruefen: bool = False
) -> tuple[Abgleich, dict[str, dict[str, str]]]:
    prio_schema = json.loads(PRIO_SCHEMA.read_text(encoding="utf-8"))
    konzept_schema = json.loads(KONZEPT_SCHEMA.read_text(encoding="utf-8"))
    soll = {
        l["ordner"]: dateien(l, prio_schema, konzept_schema) for l in roh["lieferungen"]
    }
    abgleich = abgleichen(soll, basis)
    # Erst alles prüfen, dann schreiben: ein Abbruch hinterlässt keinen halben Zug.
    if not pruefen and not abgleich.abweichend:
        schreiben(soll, abgleich.neu, basis)
    return abgleich, soll


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--aus", type=Path,
                        help="Ausgabe von `python -m lieferung` aus einer Datei statt über ssh")
    parser.add_argument("--ziel", type=Path, default=LIEFERUNGEN,
                        help="Lieferungen-Verzeichnis (Vorgabe: contracts/bc2-to-bc3/lieferungen)")
    parser.add_argument("--pruefen", action="store_true",
                        help="nur abgleichen, nichts schreiben")
    args = parser.parse_args(argv)

    if args.aus:
        text = args.aus.read_text(encoding="utf-8")
    else:
        text = subprocess.run(SSH_AUFRUF, check=True, capture_output=True, text=True).stdout
    abgleich, _ = ziehe(json.loads(text), args.ziel, pruefen=args.pruefen)

    for o in abgleich.gleich:
        print(f"unverändert  {o}")
    for o in abgleich.neu:
        print(f"{'neu (nicht geschrieben)' if args.pruefen or abgleich.abweichend else 'neu'}  {o}")
    if abgleich.abweichend:
        for o, diff in abgleich.abweichend.items():
            print(f"\nABWEICHUNG  {o} — eine übergebene Lieferung ändert sich nicht:\n{diff}")
        print("Abgebrochen, nichts geschrieben.", file=sys.stderr)
        return 1
    if not abgleich.neu:
        print("Nichts Neues.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
