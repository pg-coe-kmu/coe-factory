"""B7 Teil 2 (#266): Betriebsprotokoll des Kerns.

Nur Kennungen, Feldnamen, feste Schlüsselwörter, Klassennamen und Zahlen — nie
Nachricht, Wert, Frage, Antworttext oder Ausnahmetext.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar

log = logging.getLogger("bc1.kern")

# Die Correlation-ID des laufenden /turn; der Dienst setzt sie, Kern und Adapter lesen
# sie. Ausserhalb eines Turns (CLI, Testprofil-Werkzeug) bleibt es beim Strich.
aktuelle_korrelation: ContextVar[str] = ContextVar("bc1_korrelation", default="-")


@contextmanager
def ki_aufruf(art: str):
    beginn = time.perf_counter()
    try:
        yield
    except Exception:
        # Nur die Tatsache, nie der Ausnahmetext: die Klasse nennt process_turn.
        log.warning("ki_aufruf korrelation=%s art=%s ergebnis=fehler dauer_ms=%d",
                    aktuelle_korrelation.get(), art,
                    round((time.perf_counter() - beginn) * 1000))
        raise
    log.info("ki_aufruf korrelation=%s art=%s ergebnis=ok dauer_ms=%d",
             aktuelle_korrelation.get(), art, round((time.perf_counter() - beginn) * 1000))
