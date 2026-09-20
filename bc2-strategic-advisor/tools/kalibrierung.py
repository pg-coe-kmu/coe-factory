#!/usr/bin/env python3
"""
BC2 · Kalibrierungswerkzeug für Score-Bänder und Euro-Schwellen.

ADR-006 · BC2 legt sich selbst eine Kalibrierung auf (2.5, 2.7): die Bänder
(PRIO 1 ab 50, PRIO 2 ab 20) und die Euro-Schwellen (1.000 / 50.000 €/Jahr)
sind **gesetzt, nicht geprüft**. Dieses Werkzeug prüft sie — an einem echten
Satz Potenziale, nicht am Gefühl.

Aufruf aus dem Repo-Wurzelverzeichnis::

    python3 bc2-strategic-advisor/tools/kalibrierung.py \\
        bc2-strategic-advisor/kalibrierung/prototyp-167.json

**Wozu.** Eine Prioritätsgruppe, in der fast alles liegt, sagt nichts. Gemessen
am 20.09.2026 (#238) an den elf Potenzialen des Prototyps aus #167 landeten
**neun in PRIO 2**. Das ist der Befund, der die Bänder unter Vorbehalt gestellt
hat — und zugleich der Grund, sie noch **nicht** zu verschieben: jene elf sind
erfunden. Festgezurrt wird am ersten echten Lauf (#206, KW 40), und dann mit
diesem Werkzeug.

**Was es nicht kann.** Es sagt nicht, welche Bänder richtig sind. Es zeigt, wie
sich die Verteilung verschiebt, und macht damit sichtbar, was eine Setzung
kostet. Die Entscheidung bleibt beim Menschen und gehört ins ADR.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Der Rechenkern liegt unter app/; von tools/ aus eine Ebene hoch und hinein.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from modell import (  # noqa: E402
    Nutzwert,
    Nutzwertkategorie,
    Parameter,
    Potenzialeingang,
    rechne_lauf,
)

GRUPPEN = ("PRIO 1", "PRIO 2", "PRIO 3")


def lies_eingaenge(pfad: Path) -> tuple[str, str, list[Potenzialeingang], str | None]:
    """Liest eine Eingangsdatei. Gibt (company_id, paket_id, Eingänge, Warnung)."""
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    eingaenge = []
    for p in roh["potenziale"]:
        nw = p.pop("nutzwert")
        p["nutzwert"] = Nutzwert(
            **{
                schluessel: Nutzwertkategorie(eintrag["wert"], eintrag["begruendung"])
                for schluessel, eintrag in nw.items()
            }
        )
        for schluessel in ("betroffene_teilprozess_ids", "reifeskalen"):
            if p.get(schluessel) is not None:
                p[schluessel] = tuple(p[schluessel])
        eingaenge.append(Potenzialeingang(**p))
    return roh["company_id"], roh["paket_id"], eingaenge, roh.get("warnung")


def verteilung(lauf) -> dict[str, int]:
    zaehler = dict.fromkeys(GRUPPEN, 0)
    for pot in lauf.potenziale:
        zaehler[pot.prioritaetsgruppe] += 1
    return zaehler


def _zeile(kopf: str, z: dict[str, int], gesamt: int) -> str:
    anteil = 100 * max(z.values()) / gesamt if gesamt else 0
    fett = "  <== eine Gruppe traegt {:.0f} %".format(anteil) if anteil >= 70 else ""
    return (
        f"  {kopf:<26} "
        + " · ".join(f"{g} {z[g]:>2}" for g in GRUPPEN)
        + fett
    )


def bericht(company_id: str, paket_id: str, eingaenge, warnung: str | None) -> None:
    standard = rechne_lauf(company_id, paket_id, eingaenge)
    gesamt = len(standard.potenziale)
    p = standard.parameter

    print("=" * 84)
    print(f"KALIBRIERUNG · Lauf ({company_id}, {paket_id}) · {gesamt} Potenziale")
    print("=" * 84)
    if warnung:
        print(f"\n  ⚠  {warnung}\n")

    print("Scores in Rangfolge:")
    for pot in standard.potenziale:
        balken = "#" * max(1, round(pot.prioritaet_score / 2))
        monetaer = "—" if pot.impact_monetaer is None else str(pot.impact_monetaer)
        print(
            f"  {pot.potenzialrang:>2}. {pot.prioritaet_score:>3}  {pot.prioritaetsgruppe}  "
            f"I{pot.impact:>2} (mon {monetaer:>2} / nutz {pot.nutzwert:>4.1f})  "
            f"K{pot.umsetzungskomplexitaet:>2}  {balken:<40} {pot.titel[:34]}"
        )

    scores = [pot.prioritaet_score for pot in standard.potenziale]
    print(f"\nScore-Spanne: {min(scores)} … {max(scores)}")

    print(f"\nBaender heute (PRIO 1 ab {p.band_prio1:.0f}, PRIO 2 ab {p.band_prio2:.0f}):")
    print(_zeile("Voreinstellung", verteilung(standard), gesamt))

    print("\nWas andere Grenzen ergaeben — gleiche Rangfolge, nur anderer Schnitt:")
    for b1, b2 in ((50, 20), (45, 20), (40, 20), (36, 18), (35, 15), (30, 15)):
        lauf = rechne_lauf(
            company_id, paket_id, eingaenge, Parameter(band_prio1=float(b1), band_prio2=float(b2))
        )
        print(_zeile(f"PRIO 1 ab {b1}, PRIO 2 ab {b2}", verteilung(lauf), gesamt))

    print("\nWas die Euro-Obergrenze bewirkt (impact_monetaer erreicht dort die 10):")
    for oben in (50_000, 30_000, 20_000, 10_000):
        lauf = rechne_lauf(
            company_id, paket_id, eingaenge, Parameter(euro_schwelle_oben=float(oben))
        )
        werte = [x.impact_monetaer for x in lauf.potenziale if x.impact_monetaer is not None]
        spanne = f"monetaer {min(werte)}–{max(werte)}" if werte else "keine Value-Zahl"
        print(_zeile(f"Obergrenze {oben:>6,} EUR", verteilung(lauf), gesamt) + f"   {spanne}")

    # ── Der Befund, der beim Messen am 20.09.2026 alle ueberrascht hat ───────
    print(
        "\nHinweis zum Lesen dieser Tabelle: verschiebt die Euro-Obergrenze die\n"
        "Verteilung kaum, liegt der Deckel nicht bei ihr, sondern bei der\n"
        "Komplexitaet — komplexitaet = round(11 - 2 x reife) kommt bei\n"
        "realistischer Prozessreife nicht unter 4, und score = impact x (11 - K)\n"
        "ist damit auf etwa impact x 7 gedeckelt. Wer dann nur die Baender\n"
        "verschiebt, behandelt das Symptom (#238)."
    )

    verteilt = verteilung(standard)
    if gesamt and max(verteilt.values()) / gesamt >= 0.7:
        traeger = max(verteilt, key=lambda g: verteilt[g])
        print(
            f"\n⚠  BEFUND: {verteilt[traeger]} von {gesamt} Potenzialen liegen in "
            f"{traeger}.\n   Eine Gruppe, in der fast alles liegt, trennt nicht — die "
            "Kalibrierung steht aus\n   (ADR-006 BC2, 2.7; Auflage an #238)."
        )


def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Prueft die Score-Baender und Euro-Schwellen an einem Satz Potenziale.",
    )
    zerleger.add_argument("eingaenge", type=Path, help="JSON-Datei mit den Potenzialeingaengen")
    args = zerleger.parse_args(argv)

    if not args.eingaenge.exists():
        print(f"Datei nicht gefunden: {args.eingaenge}", file=sys.stderr)
        return 2

    bericht(*lies_eingaenge(args.eingaenge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
