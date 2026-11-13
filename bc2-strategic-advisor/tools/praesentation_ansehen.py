#!/usr/bin/env python3
"""
BC2 · Einen Foliensatz zum Hinsehen rendern, vor einer Freigabe (#380).

Die Präsentation entsteht aus Code; ob sie *aussieht*, sagt kein Test. Dieses
Werkzeug macht aus einer ``.pptx`` — oder aus einem Lieferordner, aus dem es
die Präsentation erst zeichnet — eine PDF und je Folie ein PNG, gerendert mit
LibreOffice (``soffice --headless``), die PNGs mit ``pdftoppm``, falls da.

Aus dem Repo-Wurzelverzeichnis::

    python3 bc2-strategic-advisor/tools/praesentation_ansehen.py praesentation.pptx
    python3 bc2-strategic-advisor/tools/praesentation_ansehen.py \\
        contracts/bc2-to-bc3/lieferungen/noroai-cc7f4d1b-…-f1

Den Lieferordner zu zeichnen braucht ``python-pptx`` und die Umgebung des
Dienstes (Python 3.11+), also z. B. ``/tmp/bc2v13/bin/python``.

**Die Ausgaben gehören nicht ins Repo**: sie tragen Mandantendaten. Sie landen
darum standardmäßig im Temp-Verzeichnis (``…/bc2-praesentation/<name>/``), und
ein Ziel innerhalb des Repos lehnt das Werkzeug ab.

**LibreOffice ist nicht PowerPoint.** Es schrumpft überlaufenden Text
(``normAutofit``) sofort, PowerPoint erst beim Bearbeiten — ein sauberes Bild
hier heißt nicht, dass PowerPoint dasselbe zeigt. Gegen den Überlauf hält der
Test in ``app/tests/test_praesentation.py``, nicht dieses Bild.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "bc2-strategic-advisor" / "app"
PRIO_DATEI = "prozesspriorisierung.json"


def _zeichne_aus_lieferung(ordner: Path, ziel: Path) -> Path:
    """Zeichnet die Präsentation aus ``prozesspriorisierung.json`` und ``konzept_*.json``."""
    sys.path.insert(0, str(APP))
    from praesentation import als_bytes, baue_praesentation

    prio = json.loads((ordner / PRIO_DATEI).read_text(encoding="utf-8"))
    konzepte = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(ordner.glob("konzept_*.json"))]
    datei = ziel / "praesentation.pptx"
    datei.write_bytes(als_bytes(baue_praesentation(konzepte, prio)))
    return datei


def _im_repo(pfad: Path) -> bool:
    try:
        pfad.resolve().relative_to(REPO)
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("quelle", type=Path, help="eine .pptx oder ein Lieferordner")
    ap.add_argument("--nach", type=Path, help="Ausgabeordner (Standard: Temp-Verzeichnis)")
    ap.add_argument("--aufloesung", type=int, default=80, help="PNG in dpi (Standard 80)")
    args = ap.parse_args(argv)

    quelle = args.quelle
    if not quelle.exists():
        ap.error(f"{quelle} gibt es nicht.")
    name = quelle.stem if quelle.is_file() else quelle.name
    ziel = args.nach or Path(tempfile.gettempdir()) / "bc2-praesentation" / name
    if _im_repo(ziel):
        ap.error(f"{ziel} liegt im Repo. Die Ausgaben tragen Mandantendaten und gehören nicht hinein.")
    soffice = shutil.which("soffice")
    if not soffice:
        ap.error("soffice fehlt — LibreOffice installieren (z. B. brew install --cask libreoffice).")
    ziel.mkdir(parents=True, exist_ok=True)

    pptx = quelle if quelle.is_file() else _zeichne_aus_lieferung(quelle, ziel)
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(ziel), str(pptx)],
        check=True, capture_output=True,
    )
    pdf = ziel / f"{pptx.stem}.pdf"
    print(f"PDF:  {pdf}")

    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        for alt in ziel.glob("folie-*.png"):
            alt.unlink()
        subprocess.run([pdftoppm, "-png", "-r", str(args.aufloesung), str(pdf), str(ziel / "folie")],
                       check=True)
        print(f"PNG:  {len(list(ziel.glob('folie-*.png')))} Folien in {ziel}")
    else:
        print("PNG:  pdftoppm fehlt (poppler) — nur die PDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
