#!/usr/bin/env python3
"""BC2 · Den Bewertungsschritt an echten Modellaufrufen messen — mit Stabilitätsprobe.

**Wozu.** ``app/tests/test_bewertung.py`` läuft gegen einen Doppelgänger und
ruft nie ein Modell. Ob ein Modell die Anker trifft, im Korridor bleibt und sich
an das Rechenverbot in den Texten hält, zeigt nur ein echter Aufruf — die Lehre
aus #205 und #248.

**Die Abnahme aus #288 (ADR-006 · BC2, 6.2).** Ein Aufruf je Lauf ist nur dann
ein Maßstab, wenn er stabil urteilt. Das Werkzeug erkennt das Paket **einmal**
und bewertet denselben Schnitt **zweimal**; weicht ein Nutzwert um mehr als
einen Punkt ab, ist der Schnitt „ein Aufruf je Lauf" neu zu stellen.

„Nutzwert" ist im Glossar das **Mittel** der fünf Kategorien; das Urteil fällt
darum am Mittel. Die Kategorien werden daneben ausgewiesen — eine Abweichung
dort ist die feinere Probe, und keine der beiden Lesarten soll sich hinter der
anderen verstecken können. Die
Erkennung wird bewusst nicht wiederholt: sonst mäße die Probe die Streuung des
Schneidens mit, und die ist in #248 schon gemessen.

Aufruf (aus dem Wurzelverzeichnis des Repos)::

    python3 bc2-strategic-advisor/tools/bewertung_messen.py              # Prototyp-Paket
    python3 bc2-strategic-advisor/tools/bewertung_messen.py --sdk        # über die API

Ohne ``--sdk`` über die Claude-CLI, also ohne ``ANTHROPIC_API_KEY``. Die Quelle
ist BC0s Snapshot vom 27.08.2026 — **ohne BC1-Profile**: jede Value-Zahl fällt
damit auf ``keine``, und jede Komplexität ist geurteilt. Für die Stabilität der
Nutzwerte ist das gleichgültig; über Value sagt die Messung nichts.

Die Rohantworten schreibt es nach ``--aus`` (Voreinstellung ``/tmp``), **nicht**
ins Repo: sie tragen Belegtexte des Mandanten.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WURZEL / "bc2-strategic-advisor/app"))

from bewertung import BewertungAbgebrochen, bewerte  # noqa: E402
from bewertung.pruefen import KATEGORIEN  # noqa: E402
from erkennung import CliModell, ErkennungAbgebrochen, SdkModell, SnapshotBestand, erkenne  # noqa: E402
from modell import rechne_lauf  # noqa: E402

SNAPSHOT = WURZEL / "bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json"
NOROAI = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"

#: Dasselbe Paket wie in ``erkennung_messen.py`` — damit die Messungen
#: vergleichbar bleiben.
PROTOTYP_PAKET = [
    "KP-02.TP-1", "KP-02.TP-2", "KP-02.TP-3", "KP-02.TP-4", "KP-02.TP-5",
    "KP-03.TP-1", "KP-03.TP-2", "KP-03.TP-3", "KP-03.TP-4", "KP-03.TP-5",
    "KP-05.TP-1", "KP-05.TP-2", "KP-05.TP-3", "KP-05.TP-4", "KP-05.TP-5",
    "KP-06.TP-2",
]

#: Die Abbruchgrenze aus ADR-006 · BC2, 6.2.
GRENZE_PUNKTE = 1


def _je_erkennung(bewertung) -> dict[str, dict]:
    return {str(b["id"]): b for b in (bewertung.antwort or {}).get("bewertungen", [])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sdk", action="store_true", help="ueber die API statt die CLI")
    ap.add_argument("--aus", default="/tmp", help="Verzeichnis fuer die Rohantworten")
    args = ap.parse_args()

    modell = SdkModell() if args.sdk else CliModell()
    stand = datetime(2026, 9, 20, tzinfo=timezone.utc)
    bestand = SnapshotBestand(SNAPSHOT).lies_paket(NOROAI, "MESS-288", stand, PROTOTYP_PAKET)

    t0 = time.time()
    try:
        erkennung = erkenne(bestand, modell)
    except ErkennungAbgebrochen as e:
        print(f"Erkennung angehalten: {e}", file=sys.stderr)
        return 2
    print(f"Erkennung: {len(erkennung.potenziale)} Potenziale in {time.time() - t0:.0f} s")

    laeufe = []
    for nr in (1, 2):
        t0 = time.time()
        try:
            b = bewerte(erkennung, bestand, modell)
        except BewertungAbgebrochen as e:
            print(f"Bewertung {nr} angehalten: {e}", file=sys.stderr)
            Path(args.aus, f"bewertung-288-{nr}-roh.txt").write_text(e.roh, encoding="utf-8")
            return 3
        dauer = time.time() - t0
        print(
            f"Bewertung {nr}: {b.aufruf.versuche} Versuch(e), {b.aufruf.zeichen} Zeichen, "
            f"{dauer:.0f} s" + (f" — verworfen: {list(b.aufruf.verworfen)}" if b.aufruf.verworfen else "")
        )
        laeufe.append(b)

    ziel = Path(args.aus, "bewertung-288.json")
    ziel.write_text(
        json.dumps(
            {
                "erkennung": [p.__dict__ for p in erkennung.potenziale],
                "bewertung_1": laeufe[0].antwort,
                "bewertung_2": laeufe[1].antwort,
            },
            ensure_ascii=False,
            indent=2,
            default=list,
        ),
        encoding="utf-8",
    )

    # --- Stabilität -----------------------------------------------------------
    a, b = _je_erkennung(laeufe[0]), _je_erkennung(laeufe[1])
    titel = {p.potenzial_id: p.titel for p in erkennung.potenziale}
    groesste = 0
    groesste_mittel = 0.0
    ueber_kat = 0
    print("\nStabilitaet (Bewertung 1 → 2):")
    print(f"  {'Potenzial':<44} {'Q':>5} {'D':>5} {'F':>5} {'M':>5} {'C':>5}  {'Mittel':<10} Lage         K       PT")
    for pid in sorted(a):
        x, y = a[pid], b[pid]
        diffs = []
        zellen = []
        for k in KATEGORIEN:
            w1, w2 = x["nutzwert"][k]["wert"], y["nutzwert"][k]["wert"]
            diffs.append(abs(w1 - w2))
            zellen.append(f"{w1}→{w2}")
        groesste = max(groesste, *diffs)
        ueber_kat += sum(1 for d in diffs if d > GRENZE_PUNKTE)
        m1 = sum(x["nutzwert"][k]["wert"] for k in KATEGORIEN) / len(KATEGORIEN)
        m2 = sum(y["nutzwert"][k]["wert"] for k in KATEGORIEN) / len(KATEGORIEN)
        groesste_mittel = max(groesste_mittel, abs(m1 - m2))
        mittel = f"{m1:.1f}→{m2:.1f}"
        lage = f"{x['angesetzt_min_pct']:g}-{x['angesetzt_max_pct']:g}→{y['angesetzt_min_pct']:g}-{y['angesetzt_max_pct']:g}"
        k = f"{x.get('komplexitaet_ueberschrieben')}→{y.get('komplexitaet_ueberschrieben')}"
        pt = f"{x['aufwand_schaetzung_pt']:g}→{y['aufwand_schaetzung_pt']:g}"
        print(f"  {(pid + ' ' + titel[pid])[:44]:<44} " + " ".join(f"{z:>5}" for z in zellen)
              + f"  {mittel:<10} {lage:<12} {k:<7} {pt}")

    stabil = groesste_mittel <= GRENZE_PUNKTE
    urteil = "STABIL" if stabil else "NICHT STABIL — Schnitt neu stellen (6.2)"
    print(f"\nGroesste Abweichung eines Nutzwerts (Mittel): {groesste_mittel:.1f} Punkt(e) → {urteil}")
    print(
        f"Kategorien: groesste Abweichung {groesste} Punkt(e); "
        f"{ueber_kat} von {len(a) * len(KATEGORIEN)} Werten ueber {GRENZE_PUNKTE}"
    )

    # --- Rechenkern -------------------------------------------------------------
    lauf = rechne_lauf(NOROAI, "MESS-288", laeufe[0].eingaenge)
    print("\nLauf aus Bewertung 1:")
    for p in lauf.potenziale:
        print(
            f"  {p.potenzialrang:>2}. {p.prioritaetsgruppe}  Score {p.prioritaet_score:>3}  "
            f"I {p.impact} (nutz {p.nutzwert:.1f})  K {p.umsetzungskomplexitaet} "
            f"[{p.komplexitaet_herkunft}]  PT {p.aufwand_schaetzung_pt:g}  {p.titel[:50]}"
        )
    print(f"\nRohantworten: {ziel}")
    return 0 if stabil else 1


if __name__ == "__main__":
    raise SystemExit(main())
