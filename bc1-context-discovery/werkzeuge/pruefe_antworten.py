"""Kommandozeile des Pruefwerkzeugs (Schicht b): duenne Verdrahtung, kein Test der KI.

Aufruf (aus bc1-context-discovery/):
    python -m werkzeuge.pruefe_antworten --szenario {1,2,3,4} [--lauf K] --ausgabe <Datei>
"""
import argparse
import os
import subprocess
from dataclasses import replace
from pathlib import Path

from bc1_core.store import InMemoryStateStore
from werkzeuge.antwortpruefung import bericht, bewerte, spiele
from werkzeuge.katalog import baue_paket, lade_katalog
from werkzeuge.szenarien import anzahl_laeufe, baue_szenario

REPO = Path(__file__).resolve().parents[2]   # coe-factory
KATALOG = Path(__file__).resolve().parents[1] / "tests" / "daten" / "antwortkatalog.json"


def ermittle_code_stand(verzeichnis):
    """Kurz-SHA von HEAD; mit "+dirty", wenn `verzeichnis` Aenderungen gegen HEAD hat."""
    stand = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                           text=True, cwd=verzeichnis).stdout.strip()
    offen = subprocess.run(["git", "status", "--porcelain", "--", "."], capture_output=True,
                           text=True, cwd=verzeichnis).stdout.strip()
    return stand + "+dirty" if stand and offen else stand


def main(argv=None, umgebung=None, waehle=None):
    parser = argparse.ArgumentParser(prog="python -m werkzeuge.pruefe_antworten")
    parser.add_argument("--szenario", type=int, choices=(1, 2, 3, 4), required=True)
    parser.add_argument("--lauf", type=int, help="nur diesen Lauf spielen (Standard: alle)")
    parser.add_argument("--ausgabe", type=Path, required=True)
    args = parser.parse_args(argv)
    if REPO in args.ausgabe.resolve().parents:
        parser.error("Berichte gehören nie ins Repo — bitte außerhalb ablegen "
                     "(z. B. im AutoCoE-Wurzelordner)")
    katalog = lade_katalog(KATALOG)
    anzahl = anzahl_laeufe(katalog, args.szenario)
    if args.lauf is not None and not 1 <= args.lauf <= anzahl:
        parser.error(f"--lauf muss zwischen 1 und {anzahl} liegen")
    if umgebung is None:
        umgebung = os.environ
    if waehle is None:
        from bc1_service.llm_wahl import waehle_llm as waehle   # erst beim echten Lauf
    llm = waehle(umgebung)
    ergebnisse, laeufe, pflicht = [], [], []
    for nummer in [args.lauf] if args.lauf else range(1, anzahl + 1):
        szenario = baue_szenario(katalog, args.szenario, nummer)
        paket = baue_paket(katalog["kontext"], szenario.variante)
        lauf = spiele(InMemoryStateStore(), llm, paket, szenario.antworten,
                      start=szenario.start)
        ergebnisse += [replace(r, lauf=nummer)
                       for r in bewerte(lauf, szenario.erwartungen, paket,
                                        start_felder=szenario.start_felder)]
        laeufe.append((nummer, lauf))
        pflicht += szenario.pflicht
    modell = umgebung.get("BC1_LLM", "claude")
    if modell == "gemini":
        modell = umgebung.get("BC1_GEMINI_MODELL")
        if not modell:
            # Nur hier laden: --help und die anderen Adapter brauchen die Gemini-Lib nie.
            from bc1_service.gemini_llm import STANDARD_MODELL
            modell = STANDARD_MODELL
    stand = ermittle_code_stand(Path(__file__).parents[1])
    text = bericht(ergebnisse, modell=modell, code_stand=stand or "unbekannt",
                   szenario=f"Szenario {args.szenario}", pflicht=pflicht, laeufe=laeufe,
                   teillauf=args.lauf if len(laeufe) < anzahl else None)
    args.ausgabe.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
