#!/usr/bin/env python3
"""BC2 · Den Erkennungsschritt an einem echten Modellaufruf messen.

**Wozu das Werkzeug da ist.** Die Tests in ``app/tests/test_erkennung.py``
laufen gegen einen Doppelgänger und rufen nie ein Modell. Sie zeigen, dass die
Kette um das Modell herum hält — nicht, dass je ein echter Aufruf durchging.
Genau diese Lücke hat die Karte #158 an [#205] teuer bezahlt: 48 grüne Tests
belegten nicht, dass BC0s Ruf je ankam, weil sie mit ihrem eigenen Schlüssel
signierten. Was ein einseitiger Test grundsätzlich nicht erreicht, ist die Naht
zu einem fremden System.

Dieses Werkzeug fährt sie von Hand.

Aufruf::

    python3 bc2-strategic-advisor/tools/erkennung_messen.py            # Prototyp-Paket (16 TP)
    python3 bc2-strategic-advisor/tools/erkennung_messen.py --alle     # ganzer Bestand (50 TP)
    python3 bc2-strategic-advisor/tools/erkennung_messen.py --trocken  # nur packen, nicht fragen

Aus dem Wurzelverzeichnis des Repos aufrufen. Ohne ``--sdk`` läuft es über die
Claude-CLI, damit kein ``ANTHROPIC_API_KEY`` nötig ist; im Betrieb ist das SDK
der Weg (siehe ``app/erkennung/modellruf.py``).

Die Quelle ist BC0s Snapshot vom 27.08.2026 — er kennt keine Pakete, das
Prototyp-Paket ist frei gewählt und deckt die unangenehmen Fälle ab (KP-02/03
dicht bewertet, KP-05 fast nur Platzhalter, KP-06.TP-2 mit BC1-Profil). Eine
Messung hier ist **keine** Aussage über den Livestand; die gehört zu [#249].

[#205]: https://github.com/pg-coe-kmu/coe-factory/issues/205
[#249]: https://github.com/pg-coe-kmu/coe-factory/issues/249
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

from erkennung import (  # noqa: E402
    CliModell,
    ErkennungAbgebrochen,
    SdkModell,
    SnapshotBestand,
    erkenne,
    packe,
)

SNAPSHOT = WURZEL / "bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json"
NOROAI = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"

PROTOTYP_PAKET = [
    "KP-02.TP-1", "KP-02.TP-2", "KP-02.TP-3", "KP-02.TP-4", "KP-02.TP-5",
    "KP-03.TP-1", "KP-03.TP-2", "KP-03.TP-3", "KP-03.TP-4", "KP-03.TP-5",
    "KP-05.TP-1", "KP-05.TP-2", "KP-05.TP-3", "KP-05.TP-4", "KP-05.TP-5",
    "KP-06.TP-2",
]


def alle_teilprozesse() -> list[str]:
    d = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return [
        t["sub_process_id"]
        for p in d["stammdaten"]["prozesse"]
        for t in p["teilprozesse"]
    ]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--alle", action="store_true", help="ganzer Bestand statt Prototyp-Paket")
    p.add_argument("--trocken", action="store_true", help="nur packen, kein Modellaufruf")
    p.add_argument("--sdk", action="store_true", help="ueber ANTHROPIC_API_KEY statt CLI")
    p.add_argument("--grenze", type=int, default=None, help="Obergrenze in Zeichen erzwingen")
    p.add_argument("--ziel", type=Path, default=None, help="Ergebnis als JSON ablegen")
    a = p.parse_args()

    tps = alle_teilprozesse() if a.alle else PROTOTYP_PAKET
    quelle = SnapshotBestand(SNAPSHOT)
    bestand = quelle.lies_paket(
        NOROAI, "MESSUNG-248", datetime.now(timezone.utc), tps
    )

    ohne = [t.teilprozess_id for t in bestand.teilprozesse if not t.bewertet]
    print(f"Bestand: {len(bestand.teilprozess_ids)} Teilprozesse in "
          f"{len(bestand.kernprozesse)} Kernprozessen")
    print(f"  ohne Bewertungen (Auflage 4, kein Nullwert): {len(ohne)}"
          + (f" — {', '.join(ohne)}" if ohne else ""))
    print(f"  schneidbar: {len(bestand.schneidbare_ids)}")

    kwargs = {"grenze": a.grenze} if a.grenze else {}
    aufrufe = packe(bestand, **kwargs)
    for auf in aufrufe:
        print(f"  Aufruf {auf.name}: Schnitt {auf.schnitt}, {auf.zeichen} Zeichen, "
              f"{len(auf.teilprozess_ids)} Teilprozesse")

    if a.trocken:
        return 0

    modell = SdkModell() if a.sdk else CliModell()
    t0 = time.time()
    try:
        e = erkenne(bestand, modell, **kwargs)
    except ErkennungAbgebrochen as fehler:
        print(f"\nANGEHALTEN nach {time.time() - t0:.0f}s: {fehler}")
        return 1

    print(f"\n{len(e.potenziale)} Potenziale in {time.time() - t0:.0f}s")
    for pot in e.potenziale:
        print(f"  {pot.potenzial_id:10s} {pot.kernprozess_id}  "
              f"[{pot.klasse}]  {pot.titel}")
        print(f"             beruehrt: {', '.join(pot.beruehrte_teilprozess_ids)}")
    if e.nicht_geschnitten:
        print(f"\nnicht geschnitten ({len(e.nicht_geschnitten)}):")
        for n in e.nicht_geschnitten:
            print(f"  {n.teilprozess_id}: {n.grund}")

    b = e.pruefung
    print(f"\nNachkontrolle: {'sauber' if b.sauber else 'VERSTOSS'}")
    print(f"  unbedeckt: {list(b.unbedeckt) or '—'}")
    print(f"  mehrfach belegt: {[t for t, _ in b.mehrfach] or '—'}")
    print(f"  Ueberschneidungen: {len(b.ueberschneidungen)}")
    print(f"  Zahlen im Text: {list(b.zahlen_im_text) or '—'}")
    print(f"  unbekannte Klasse: {list(b.unbekannte_klasse) or '—'}")
    print(f"  Paare fuer Gate 1: {len(e.paare)}")
    for prot in e.aufrufe:
        print(f"  Aufruf {prot.name}: {prot.versuche} Versuch(e), Modell {prot.modell}"
              + (f", verworfen: {prot.verworfen}" if prot.verworfen else ""))
    for h in e.hinweise:
        print(f"  Hinweis: {h}")

    if a.ziel:
        a.ziel.write_text(
            json.dumps(
                {
                    "paket_id": e.paket_id,
                    "modell": [pr.modell for pr in e.aufrufe],
                    "potenziale": [vars(x) for x in e.potenziale],
                    "nicht_geschnitten": [vars(x) for x in e.nicht_geschnitten],
                    "aufrufe": [vars(x) for x in e.aufrufe],
                    "hinweise": list(e.hinweise),
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"\ngeschrieben: {a.ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
