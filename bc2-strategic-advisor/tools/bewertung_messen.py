#!/usr/bin/env python3
"""BC2 · Den Bewertungsschritt an echten Modellaufrufen messen — mit Stabilitätsprobe.

**Wozu.** ``app/tests/test_bewertung.py`` läuft gegen einen Doppelgänger und
ruft nie ein Modell. Ob ein Modell die Anker trifft, im Korridor bleibt und sich
an das Rechenverbot in den Texten hält, zeigt nur ein echter Aufruf — die Lehre
aus #205 und #248.

**Die Abnahme (ADR-006 · BC2, 6.2; Regel aus #299).** Das Werkzeug erkennt das
Paket **einmal** und bewertet denselben Schnitt *n*-mal (Voreinstellung 10).
Aus den *n* Urteilen werden alle Paare **disjunkter** Gruppen gezogen — je
eines, je drei, je fünf —, jede Gruppe über :func:`bewertung.fuehre_zusammen`
zu einem Median-Urteil zusammengeführt, also mit genau dem Code, der im Betrieb
läuft. Ein Paar **hält**, wenn kein Nutzwert-**Mittel** um mehr als einen Punkt
abweicht (Glossar: „Nutzwert" ist das Mittel). Die Entscheidung:

1. halten mindestens 95 % der Dreierpaare → **Median aus drei**;
2. sonst halten 95 % der Fünferpaare → **Median aus fünf**;
3. sonst ist die Streuung mit Wiederholen nicht zu bezähmen → die **Anker** der
   am stärksten streuenden Kategorien sind zu schärfen (eigenes Ticket).

Kategorien, Gruppenwechsel und der Aufwand werden ausgewiesen, entscheiden aber
nicht (Q2 in #299). Die Erkennung wird bewusst nicht wiederholt: sonst mäße die
Probe die Streuung des Schneidens mit, und die ist in #248 schon gemessen.

Aufruf (aus dem Wurzelverzeichnis des Repos)::

    python3 bc2-strategic-advisor/tools/bewertung_messen.py              # 10 Urteile, CLI
    python3 bc2-strategic-advisor/tools/bewertung_messen.py --n 2        # nur ein Paar
    python3 bc2-strategic-advisor/tools/bewertung_messen.py --sdk        # über die API
    python3 bc2-strategic-advisor/tools/bewertung_messen.py --auswerten /tmp/bewertung-299

Ohne ``--sdk`` über die Claude-CLI, also ohne ``ANTHROPIC_API_KEY``. Die Quelle
ist BC0s Snapshot vom 27.08.2026 — **ohne BC1-Profile**: jede Value-Zahl fällt
damit auf ``keine``, und jede Komplexität ist geurteilt. Für die Stabilität der
Nutzwerte ist das gleichgültig; über Value sagt die Messung nichts.

Jedes Urteil wird **sofort** nach ``--aus`` geschrieben (Voreinstellung
``/tmp/bewertung-299``), **nicht** ins Repo: es trägt Belegtexte des Mandanten.
Mit ``--auswerten`` lässt sich eine abgebrochene oder alte Erhebung neu
auswerten, ohne ein Modell zu fragen.
"""

from __future__ import annotations

import argparse
import itertools
import json
import pickle
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WURZEL / "bc2-strategic-advisor/app"))

from bewertung import (  # noqa: E402
    BewertungAbgebrochen,
    baue_eingaenge,
    bewerte,
    erwartungen,
    fuehre_zusammen,
)
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

#: Die Abbruchgrenze aus ADR-006 · BC2, 6.2: am Nutzwert-Mittel.
GRENZE_PUNKTE = 1.0
#: Wie viele Paare halten müssen, damit eine Gruppengröße trägt (#299, Q5).
GRENZE_ANTEIL = 0.95
KUERZEL = dict(zip(KATEGORIEN, "QDFMC"))


def _bestand():
    stand = datetime(2026, 9, 20, tzinfo=timezone.utc)
    return SnapshotBestand(SNAPSHOT).lies_paket(NOROAI, "MESS-299", stand, PROTOTYP_PAKET)


def _mittel(antwort: dict) -> dict[str, float]:
    return {
        str(b["id"]): sum(b["nutzwert"][k]["wert"] for k in KATEGORIEN) / len(KATEGORIEN)
        for b in antwort["bewertungen"]
    }


def erheben(n: int, modell, aus: Path, parallel: int) -> int:
    aus.mkdir(parents=True, exist_ok=True)
    bestand = _bestand()
    t0 = time.time()
    try:
        erkennung = erkenne(bestand, modell)
    except ErkennungAbgebrochen as e:
        print(f"Erkennung angehalten: {e}", file=sys.stderr)
        return 2
    (aus / "erkennung.pickle").write_bytes(pickle.dumps(erkennung))
    print(f"Erkennung: {len(erkennung.potenziale)} Potenziale in {time.time() - t0:.0f} s")

    def ein_urteil(nr: int):
        t = time.time()
        b = bewerte(erkennung, bestand, modell, urteile=1)
        (aus / f"urteil-{nr:02d}.json").write_text(
            json.dumps(b.urteile[0], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return nr, b, time.time() - t

    abgebrochen = 0
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        auftraege = [pool.submit(ein_urteil, nr) for nr in range(1, n + 1)]
        for f in as_completed(auftraege):
            try:
                nr, b, dauer = f.result()
            except BewertungAbgebrochen as e:
                abgebrochen += 1
                print(f"Ein Urteil angehalten: {e}", file=sys.stderr)
                continue
            print(
                f"Urteil {nr:>2}: {b.aufruf.versuche} Versuch(e), {b.aufruf.zeichen} Zeichen, {dauer:.0f} s"
                + (f" — verworfen: {list(b.aufruf.verworfen)}" if b.aufruf.verworfen else "")
            )
    print(f"Waechter: {abgebrochen} von {n} Urteilen endgueltig angehalten.")
    return auswerten(aus)


def _gruppenpaare(n: int, g: int):
    """Alle ungeordneten Paare disjunkter Gruppen der Größe *g* aus ``range(n)``."""
    for a in itertools.combinations(range(n), g):
        rest = [i for i in range(n) if i not in a]
        for b in itertools.combinations(rest, g):
            if a < b:
                yield a, b


def auswerten(aus: Path) -> int:
    erkennung = pickle.loads((aus / "erkennung.pickle").read_bytes())
    bestand = _bestand()
    erwartet = erwartungen(erkennung, bestand)
    urteile = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(aus.glob("urteil-*.json"))
    ]
    n = len(urteile)
    titel = {p.potenzial_id: p.titel for p in erkennung.potenziale}
    ids = list(erwartet)
    print(f"\n{n} Urteile ueber {len(ids)} Potenziale aus {aus}")

    # --- Streuung der Einzelurteile -------------------------------------------
    print("\nStreuung der Einzelurteile (kleinster–groesster Wert, Median):")
    print(f"  {'Potenzial':<40} " + " ".join(f"{KUERZEL[k]:>7}" for k in KATEGORIEN)
          + f"  {'Mittel':>11}  {'PT':>11}  {'Lage':>9}")
    for pid in ids:
        je = [next(b for b in u["bewertungen"] if b["id"] == pid) for u in urteile]
        zellen = []
        for k in KATEGORIEN:
            w = [b["nutzwert"][k]["wert"] for b in je]
            zellen.append(f"{min(w)}–{max(w)}|{statistics.median_low(w)}")
        m = [_mittel({"bewertungen": [b]})[pid] for b in je]
        pt = [b["aufwand_schaetzung_pt"] for b in je]
        lage = [b["angesetzt_min_pct"] for b in je]
        print(f"  {(pid + ' ' + titel[pid])[:40]:<40} " + " ".join(f"{z:>7}" for z in zellen)
              + f"  {min(m):>4.1f}–{max(m):<4.1f}  {min(pt):>4g}–{max(pt):<5g}  {min(lage):>3g}–{max(lage):<4g}")

    # Gemeinsame Verschiebung je Aufruf: liegt ein Urteil durchweg hoch oder tief?
    print("\nJe Urteil (Mittel ueber alle Potenziale): Nutzwert / Aufwand in PT")
    for i, u in enumerate(urteile, 1):
        m = _mittel(u)
        pt = [b["aufwand_schaetzung_pt"] for b in u["bewertungen"]]
        print(f"  Urteil {i:>2}: {statistics.mean(m.values()):.2f} / {statistics.mean(pt):.1f}")

    # --- Paarprobe ------------------------------------------------------------
    def kennung_fuer(zaehler=itertools.count(1)):
        return lambda: f"K{next(zaehler)}"

    cache: dict[tuple[int, ...], tuple[dict[str, float], dict[str, str]]] = {}

    def gruppe(idx: tuple[int, ...]):
        if idx not in cache:
            z = fuehre_zusammen([urteile[i] for i in idx], erwartet)
            eingaenge, kennungen = baue_eingaenge(erkennung, bestand, z.antwort, kennung_fuer())
            lauf = rechne_lauf(NOROAI, "MESS-299", eingaenge)
            zurueck = {v: k for k, v in kennungen.items()}
            prio = {zurueck[p.potenzial_id]: p.prioritaetsgruppe for p in lauf.potenziale}
            cache[idx] = (_mittel(z.antwort), prio)
        return cache[idx]

    print(f"\nPaarprobe (Grenze: kein Mittel weicht um mehr als {GRENZE_PUNKTE:g} ab; "
          f"traegt ab {GRENZE_ANTEIL:.0%} der Paare):")
    ergebnis: dict[int, float] = {}
    for g in (1, 3, 5):
        if 2 * g > n:
            continue
        paare = list(_gruppenpaare(n, g))
        halten = 0
        gruppenwechsel = 0
        groesste = 0.0
        for a, b in paare:
            ma, pa = gruppe(a)
            mb, pb = gruppe(b)
            d = max(abs(ma[i] - mb[i]) for i in ids)
            groesste = max(groesste, d)
            halten += d <= GRENZE_PUNKTE + 1e-9
            gruppenwechsel += any(pa[i] != pb[i] for i in ids)
        anteil = halten / len(paare)
        ergebnis[g] = anteil
        print(f"  je {g}: {len(paare):>5} Paare, {anteil:6.1%} halten, groesste Abweichung "
              f"{groesste:.1f}, Gruppenwechsel in {gruppenwechsel / len(paare):.1%}")

    if ergebnis.get(3, 0) >= GRENZE_ANTEIL:
        urteil, code = "MEDIAN AUS DREI traegt (Regel 1)", 0
    elif ergebnis.get(5, 0) >= GRENZE_ANTEIL:
        urteil, code = "MEDIAN AUS FUENF traegt (Regel 2)", 0
    elif 3 in ergebnis:
        urteil, code = "Kein Median traegt — Anker schaerfen (Regel 3)", 1
    else:
        urteil, code = "Zu wenige Urteile fuer die Regel (mindestens 6, fuer Regel 2 zehn)", 1
    print(f"\nEntscheidung: {urteil}")
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--n", type=int, default=10, help="wie viele Urteile (Voreinstellung 10)")
    ap.add_argument("--sdk", action="store_true", help="ueber die API statt die CLI")
    ap.add_argument("--aus", default="/tmp/bewertung-299", help="Verzeichnis fuer die Urteile")
    ap.add_argument("--parallel", type=int, default=5, help="gleichzeitige Aufrufe")
    ap.add_argument("--auswerten", metavar="VERZ", help="nur eine vorhandene Erhebung auswerten")
    args = ap.parse_args()

    if args.auswerten:
        return auswerten(Path(args.auswerten))
    modell = SdkModell() if args.sdk else CliModell()
    return erheben(args.n, modell, Path(args.aus), args.parallel)


if __name__ == "__main__":
    raise SystemExit(main())
