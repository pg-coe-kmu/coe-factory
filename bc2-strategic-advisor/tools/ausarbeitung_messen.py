#!/usr/bin/env python3
"""BC2 · Den Ausarbeitungsschritt an echten Modellaufrufen messen (#301).

**Wozu.** ``app/tests/test_ausarbeitung.py`` läuft gegen Doppelgänger und ruft
nie ein Modell. Ob ein Modell Texte schreibt, die der Wächter durchlässt — das
Rechenverbot hält, die Schablonen trifft, nur Systeme aus dem Bestand nennt —,
und ob der Vertrag am Ende schemagültig ist, zeigt nur ein echter Aufruf: die
Lehre aus #205 und #248.

**Was gemessen wird.** Je Konzept: Versuche, verworfene Gründe, Dauer, Länge der
Frage. Danach wird der ganze Lauf gegen ``konzept.schema.json`` geprüft, so wie
ihn die Ablage (``ablage.dokumente_aus_ansicht``) mit Kopf zusammensetzt.

**Woher Erkennung und Bewertung kommen.** Mit ``--von`` aus einer Erhebung von
``bewertung_messen.py`` (``erkennung.pickle`` und die ersten drei Urteile, je
Feld der Median — genau wie im Betrieb); dann kostet die Messung nur die
Ausarbeitungsaufrufe. Ohne ``--von`` wird erkannt und dreimal bewertet.

Aufruf (aus dem Wurzelverzeichnis des Repos)::

    python3 bc2-strategic-advisor/tools/ausarbeitung_messen.py --von /tmp/bewertung-299
    python3 bc2-strategic-advisor/tools/ausarbeitung_messen.py          # alles frisch, CLI

Ohne ``--sdk`` über die Claude-CLI, also ohne ``ANTHROPIC_API_KEY``. Quelle ist
BC0s Snapshot vom 27.08.2026, ohne BC1-Profile. Die Antworten und das Ergebnis
gehen nach ``--aus`` (Voreinstellung ``/tmp/ausarbeitung-301``), **nicht** ins
Repo: sie tragen Belegtexte des Mandanten.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WURZEL / "bc2-strategic-advisor/app"))
sys.path.insert(0, str(WURZEL / "bc2-strategic-advisor/tools"))

from ablage import Laufbeleg, dokumente_aus_ansicht  # noqa: E402
from ausarbeitung import AusarbeitungAbgebrochen, arbeite_aus  # noqa: E402
from bewertung import baue_eingaenge, bewerte, erwartungen, fuehre_zusammen  # noqa: E402
from bewertung_messen import NOROAI, _bestand  # noqa: E402
from erkennung import CliModell, SdkModell, erkenne  # noqa: E402
from laeufe import aus_lauf  # noqa: E402
from modell import rechne_lauf  # noqa: E402

VERTRAEGE = WURZEL / "contracts" / "bc2-to-bc3"


class _Protokollierend:
    """Reicht jede Frage durch und legt die Antwort ab, sobald sie da ist."""

    def __init__(self, innen, aus: Path) -> None:
        self.innen = innen
        self.aus = aus
        self.zaehler = 0

    def frage(self, text: str, schema: dict | None = None):
        self.zaehler += 1
        nr = self.zaehler
        t = time.time()
        antwort = self.innen.frage(text, schema)
        (self.aus / f"antwort-{nr:02d}.txt").write_text(antwort.roh, encoding="utf-8")
        print(f"  Aufruf {nr:>2}: {time.time() - t:.0f} s, {len(text)} Zeichen Frage, "
              f"{len(antwort.roh)} Zeichen Antwort", flush=True)
        return antwort


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--von", type=Path, help="Erhebung von bewertung_messen.py wiederverwenden")
    ap.add_argument("--aus", type=Path, default=Path("/tmp/ausarbeitung-301"))
    ap.add_argument("--sdk", action="store_true", help="über die API statt die CLI")
    args = ap.parse_args()
    args.aus.mkdir(parents=True, exist_ok=True)

    modell = _Protokollierend(SdkModell() if args.sdk else CliModell(), args.aus)
    bestand = _bestand()
    print(f"Tech-Stack aus dem Profil: {len(bestand.mandant.tech_stack or '')} Zeichen")

    if args.von:
        erkennung = pickle.loads((args.von / "erkennung.pickle").read_bytes())
        urteile = [json.loads(p.read_text(encoding="utf-8"))
                   for p in sorted(args.von.glob("urteil-*.json"))[:3]]
        zusammen = fuehre_zusammen(urteile, erwartungen(erkennung, bestand))
        eingaenge, kennungen = baue_eingaenge(erkennung, bestand, zusammen.antwort)
        print(f"Erkennung und {len(urteile)} Urteile aus {args.von}")
    else:
        erkennung = erkenne(bestand, modell)
        bewertung = bewerte(erkennung, bestand, modell)
        eingaenge, kennungen = bewertung.eingaenge, bewertung.kennungen

    lauf = rechne_lauf(NOROAI, bestand.paket_id, eingaenge)
    ansicht = aus_lauf(lauf, list(eingaenge), uebergeben_am=bestand.uebergeben_am)
    print(f"{len(lauf.potenziale)} Potenziale in {len(lauf.prozess_raenge)} Konzepten: "
          + ", ".join(r.kp_id for r in lauf.prozess_raenge))

    t0 = time.time()
    try:
        a = arbeite_aus(lauf, ansicht.potenziale, erkennung, kennungen, bestand, modell)
    except AusarbeitungAbgebrochen as e:
        print(f"\nANGEHALTEN nach {time.time() - t0:.0f} s: {e}", file=sys.stderr)
        return 2
    print(f"\nAusarbeitung in {time.time() - t0:.0f} s")
    for aufruf in a.aufrufe:
        print(f"  {aufruf.name}: {aufruf.versuche} Versuch(e), {aufruf.zeichen} Zeichen"
              + (f"\n    verworfen: {list(aufruf.verworfen)}" if aufruf.verworfen else ""))

    # Wie die Ablage den Lauf zusammensetzt — mit Kopf und Fassung.
    from dataclasses import replace
    ansicht = replace(ansicht, konzepte=list(a.konzepte), ausgangslage=a.ausgangslage)
    beleg = Laufbeleg(
        priorisierung_id=str(uuid.uuid4()), company_id=NOROAI, paket_id=bestand.paket_id,
        uebergeben_am=bestand.uebergeben_am, fassung=1, zustand="laeuft",
    )
    from nachfolge import Nachfolge
    ansicht = replace(ansicht, nachfolge=Nachfolge())
    dokument, konzepte = dokumente_aus_ansicht(ansicht, beleg, erzeugt_am=datetime.now(timezone.utc))
    (args.aus / "konzepte.json").write_text(
        json.dumps(konzepte, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.aus / "priorisierung.json").write_text(
        json.dumps(dokument, ensure_ascii=False, indent=2), encoding="utf-8")

    import jsonschema
    pruefer = jsonschema.Draft202012Validator(
        json.loads((VERTRAEGE / "konzept.schema.json").read_text(encoding="utf-8")),
        format_checker=jsonschema.FormatChecker(),
    )
    fehler = [f"{k['kontext']['kp_id']}: {f.message[:200]}"
              for k in konzepte for f in pruefer.iter_errors(k)]
    print(f"\nSchema: {len(konzepte)} Konzepte, {len(fehler)} Verstoesse")
    for f in fehler:
        print("  " + f)
    print(f"Ergebnis in {args.aus}")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
