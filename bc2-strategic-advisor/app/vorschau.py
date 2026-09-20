#!/usr/bin/env python3
"""
BC2 · Die Oberfläche ansehen, ohne Datenbank und ohne Zugangsdaten.

    python3 vorschau.py            # http://127.0.0.1:8243, Schlüssel: vorschau
    python3 vorschau.py --port 9000 --schluessel geheim

**Wozu das nötig ist.** ``app:app`` verlangt beim Start eine ``DATABASE_URL``,
weil der Trigger-Endpunkt ohne sie sinnlos wäre — er ist ein Briefkasten für
BC0s Pakete. Die **Oberfläche** braucht davon nichts: ihre Läufe kommen aus den
Messsätzen unter ``kalibrierung/``, ihre Entscheidungen liegen im
Arbeitsspeicher. Ohne diesen Einstieg könnte die Oberfläche nur ansehen, wer
die Zugangsdaten der gemeinsamen Datenbank hat — und das ist bei einer
Oberfläche, über die mit Menschen gesprochen wird, die falsche Hürde. Fassung D
ist genau aus solchen Gesprächen entstanden (#167).

**Was hier läuft, ist nicht der Betrieb.** Kein Postgres, keine dauerhafte
Ablage, ein Schlüssel aus dem Aufruf. Der Betrieb steht in ``DEPLOY.md``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--port", type=int, default=8243)
    zerleger.add_argument("--host", default="127.0.0.1")
    zerleger.add_argument(
        "--schluessel",
        default="vorschau",
        help="Bearer-Schluessel fuer die Oberflaeche (Vorgabe: vorschau)",
    )
    zerleger.add_argument(
        "--messsaetze",
        default=str(HIER.parent / "kalibrierung"),
        help="Verzeichnis mit den Messsatz-Dateien",
    )
    argumente = zerleger.parse_args()

    # Vor dem Import von app.py: der Lebenszyklus verweigert sonst den Start.
    os.environ["BC2_TRIGGER_TOKEN"] = argumente.schluessel
    os.environ.pop("DATABASE_URL", None)

    import uvicorn

    from app import erzeuge_app
    from eingang import SpeicherEingangsbuch
    from gate1 import SpeicherGate1Buch
    from laeufe import MesssatzLaufquelle

    quelle = MesssatzLaufquelle(argumente.messsaetze)
    laeufe = quelle.uebersicht()
    if not laeufe:
        print(f"Keine Messsatz-Datei unter {argumente.messsaetze!r}.", file=sys.stderr)
        return 1

    print(f"  Oberflaeche   http://{argumente.host}:{argumente.port}/")
    print(f"  Schluessel    {argumente.schluessel}")
    print(f"  Laeufe        {', '.join(k.paket_id for k in laeufe)}")
    print("  Ablage        Arbeitsspeicher — die Entscheidung ist beim Beenden weg.\n")

    anwendung = erzeuge_app(
        SpeicherEingangsbuch(), laufquelle=quelle, gate1_buch=SpeicherGate1Buch()
    )
    uvicorn.run(anwendung, host=argumente.host, port=argumente.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
