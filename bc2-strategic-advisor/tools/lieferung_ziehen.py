#!/usr/bin/env python3
"""
BC2 · Die Lieferung an BC3 aus Schema ``bc2`` in den Lieferordner abschreiben (#306, #378).

Die Datenbank ist der eine Ort, der Lieferordner ihre Abbildung (ADR-007 · BC2,
Nachtrag #305). **Seit #378 setzt dieses Werkzeug nichts mehr zusammen**
(Nachtrag vom 13.11.2026): der Dienst friert beim Freigeben die Ergebnisakte
ein, mit den fertigen Dateien an BC3, und hier werden die ``bc3``-Dateien der
lieferbaren Akten nur abgeschrieben — Byte für Byte. Den PR öffnet seit #388
die Action ``bc2-lieferung-ziehen.yml`` nach Zeitplan; von Hand geht es weiter.

Aus dem Repo-Wurzelverzeichnis::

    python3 bc2-strategic-advisor/tools/lieferung_ziehen.py            # über ssh bc2
    python3 bc2-strategic-advisor/tools/lieferung_ziehen.py --pruefen  # nur ansehen
    python3 bc2-strategic-advisor/tools/lieferung_ziehen.py --aus lieferungen.json
    BC2_LIEFERUNG_TOKEN=… python3 bc2-strategic-advisor/tools/lieferung_ziehen.py \
        --von-url https://bc2.02da.de

Ohne ``--aus`` und ``--von-url`` ruft es ``ssh bc2 docker exec app-app-1 python
-m lieferung``; das liest im Betriebscontainer mit einer ``readonly``-Sitzung,
die ``DATABASE_URL`` verlässt den Server nicht (ADR-003). ``--von-url`` holt
dieselbe Ausgabe über ``GET /api/lieferungen``, mit dem eigenen, nur lesenden
Schlüssel aus der Umgebung (#388) — so zieht die Action, ohne ssh.

**Keine Markierung „geliefert“** (Nachtrag #305, Punkt 3). Jeder Zug schreibt
alle lieferbaren Akten ab und hält sie gegen den Arbeitsbaum. Liegt ein Ordner
schon da und weicht ab, **bricht es ab, bevor es irgendetwas schreibt**, und
zeigt den Unterschied. Was übergeben ist, ändert sich nicht. Dazu prüft es die
Prüfsumme jeder Datei: was unterwegs verdorben ist, wird nicht geschrieben.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
LIEFERUNGEN = BASE / "contracts" / "bc2-to-bc3" / "lieferungen"

SSH_AUFRUF = ["ssh", "bc2", "docker", "exec", "app-app-1", "python", "-m", "lieferung"]


class QuelleNichtLesbar(RuntimeError):
    """Der Endpunkt hat nicht geliefert — Schlüssel, Netz oder Dienst."""


def von_url(basis: str) -> str:
    """Die Ausgabe von ``python -m lieferung`` über ``GET /api/lieferungen`` (#388)."""
    schluessel = (os.environ.get("BC2_LIEFERUNG_TOKEN") or "").strip()
    if not schluessel:
        raise QuelleNichtLesbar("BC2_LIEFERUNG_TOKEN ist nicht gesetzt")
    anfrage = urllib.request.Request(
        basis.rstrip("/") + "/api/lieferungen",
        headers={"Authorization": f"Bearer {schluessel}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=60) as antwort:
            return antwort.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise QuelleNichtLesbar(f"{e.code} von {anfrage.full_url}") from None
    except urllib.error.URLError as e:
        raise QuelleNichtLesbar(f"{anfrage.full_url} nicht erreichbar: {e.reason}") from None


class PruefsummeFalsch(ValueError):
    """Eine Datei kam anders an, als die Akte sie trägt."""


def dateien(eintrag: dict) -> dict[str, bytes]:
    """Name → Inhalt einer Lieferung aus ``python -m lieferung``, nach Prüfsumme geprüft."""
    ergebnis = {}
    for d in eintrag["dateien"]:
        inhalt = base64.b64decode(d["inhalt_b64"], validate=True)
        if hashlib.sha256(inhalt).hexdigest() != d["sha256"]:
            raise PruefsummeFalsch(f"{eintrag['ordner']}/{d['name']}: Pruefsumme stimmt nicht")
        if "/" in d["name"] or d["name"].startswith("."):
            raise ValueError(f"{eintrag['ordner']}: {d['name']!r} ist kein Dateiname")
        ergebnis[d["name"]] = inhalt
    return dict(sorted(ergebnis.items()))


def _zeilen(inhalt: bytes) -> list[str]:
    return inhalt.decode("utf-8", errors="replace").splitlines(keepends=True)


@dataclass
class Abgleich:
    neu: list[str]
    gleich: list[str]
    #: Ordner → Unterschiede als Text. Nicht leer heißt: nichts schreiben.
    abweichend: dict[str, str]


def abgleichen(soll: dict[str, dict[str, bytes]], basis: Path) -> Abgleich:
    neu, gleich, abweichend = [], [], {}
    for ordner, inhalt in soll.items():
        pfad = basis / ordner
        if not pfad.exists():
            neu.append(ordner)
            continue
        vorhanden = {d.name: d.read_bytes() for d in pfad.iterdir() if d.is_file()}
        unterschied = []
        for name in sorted(set(vorhanden) | set(inhalt)):
            alt, frisch = vorhanden.get(name, b""), inhalt.get(name, b"")
            if alt != frisch:
                zeilen = list(difflib.unified_diff(
                    _zeilen(alt), _zeilen(frisch),
                    f"liegt/{ordner}/{name}", f"kaeme/{ordner}/{name}",
                ))
                # Gleicher Text, andere Bytes (etwa ein Binärinhalt): trotzdem eine Abweichung.
                unterschied += zeilen or [f"(die Bytes von {name} weichen ab)\n"]
        if unterschied:
            abweichend[ordner] = "".join(unterschied)
        else:
            gleich.append(ordner)
    return Abgleich(neu, gleich, abweichend)


def schreiben(soll: dict[str, dict[str, bytes]], ordner: list[str], basis: Path) -> None:
    for name in ordner:
        pfad = basis / name
        pfad.mkdir(parents=True)
        for datei, inhalt in soll[name].items():
            (pfad / datei).write_bytes(inhalt)


def ziehe(
    roh: dict, basis: Path = LIEFERUNGEN, *, pruefen: bool = False
) -> tuple[Abgleich, dict[str, dict[str, bytes]]]:
    soll = {l["ordner"]: dateien(l) for l in roh["lieferungen"]}
    abgleich = abgleichen(soll, basis)
    # Erst alles prüfen, dann schreiben: ein Abbruch hinterlässt keinen halben Zug.
    if not pruefen and not abgleich.abweichend:
        schreiben(soll, abgleich.neu, basis)
    return abgleich, soll


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    quelle = parser.add_mutually_exclusive_group()
    quelle.add_argument("--aus", type=Path,
                        help="Ausgabe von `python -m lieferung` aus einer Datei statt über ssh")
    quelle.add_argument("--von-url", metavar="BASIS",
                        help="über GET <BASIS>/api/lieferungen, Schlüssel aus BC2_LIEFERUNG_TOKEN")
    parser.add_argument("--ziel", type=Path, default=LIEFERUNGEN,
                        help="Lieferungen-Verzeichnis (Vorgabe: contracts/bc2-to-bc3/lieferungen)")
    parser.add_argument("--pruefen", action="store_true",
                        help="nur abgleichen, nichts schreiben")
    args = parser.parse_args(argv)

    if args.aus:
        text = args.aus.read_text(encoding="utf-8")
    elif args.von_url:
        try:
            text = von_url(args.von_url)
        except QuelleNichtLesbar as e:
            print(f"Abgebrochen, nichts geschrieben: {e}", file=sys.stderr)
            return 1
    else:
        text = subprocess.run(SSH_AUFRUF, check=True, capture_output=True, text=True).stdout
    try:
        abgleich, _ = ziehe(json.loads(text), args.ziel, pruefen=args.pruefen)
    except PruefsummeFalsch as e:
        print(f"Abgebrochen, nichts geschrieben: {e}", file=sys.stderr)
        return 1

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
