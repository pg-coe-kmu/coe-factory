"""
BC2 · Die Lieferung an BC3 — die ``bc3``-Dateien der lieferbaren Ergebnisakten.

**Die Datenbank ist der eine Ort, der Lieferordner ihre Abbildung** (ADR-007 ·
BC2, Nachtrag #305). Seit #378 (Nachtrag vom 13.11.2026) heißt das wörtlich:
die Dateien entstehen **einmal**, beim Freigeben, und liegen Byte für Byte in
der Ergebnisakte (``ergebnisakte.py``). Die Lieferung ist der Teil der Akte, der
an BC3 geht — nur bei einem Lauf ohne Sperrgrund.

Die Arbeit bleibt zweigeteilt, weil die beiden Hälften an verschiedenen Orten
leben:

- **hier, im Dienst:** die ``bc3``-Dateien der lieferbaren Akten auslesen. Hier
  liegt der Datenbankzugang (ADR-003: die ``DATABASE_URL`` verlässt den Server
  nicht). Zusammengesetzt wird hier nichts mehr.
- **``tools/lieferung_ziehen.py``, lokal:** sie abschreiben, gegen den
  Arbeitsbaum halten und bei einer Abweichung abbrechen. Den PR öffnet ein Mensch.

Aufruf auf dem VPS, nur lesend::

    docker exec app-app-1 python -m lieferung > lieferungen.json

Die Dateien reisen als Base64 mit ihrer SHA-256, damit das Werkzeug Byte für
Byte abschreibt und prüfen kann, dass unterwegs nichts verloren ging.

**Dieselbe Ausgabe über HTTPS** (#388, Nachtrag zu ADR-007 · BC2 §2.2 vom
13.11.2026): ``GET /api/lieferungen`` liefert sie einer GitHub Action, die nach
Zeitplan zieht. Der Endpunkt hat einen **eigenen** Schlüssel,
``BC2_LIEFERUNG_TOKEN``, nicht den der Oberfläche: mit dem ließe sich Gate 1
entscheiden, und er läge dann als Actions-Secret in GitHub. Dieser hier zeigt
nur, was ohnehin ins Repo kommt. Ist er nicht gesetzt, gibt es den Endpunkt
nicht.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import sys
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ergebnisakte import Ergebnisakte, mandantenkuerzel, ordnername
from gate1 import Gate1Buch

log = logging.getLogger("bc2.lieferung")

__all__ = [
    "Lieferung",
    "erzeuge_router",
    "lieferung_aus",
    "lieferungen",
    "mandantenkuerzel",
    "ordnername",
]


@dataclass(frozen=True)
class Lieferung:
    """Ein gelieferter Lauf: der Ordnername und seine Dateien an BC3."""

    ordner: str
    paket_id: str
    fassung: int
    #: Name → Inhalt, genau die Dateien der Akte mit Empfänger ``bc3``.
    dateien: dict[str, bytes]

    def als_json(self) -> dict:
        return {
            "ordner": self.ordner,
            "paket_id": self.paket_id,
            "fassung": self.fassung,
            "dateien": [
                {
                    "name": name,
                    "sha256": hashlib.sha256(inhalt).hexdigest(),
                    "inhalt_b64": base64.b64encode(inhalt).decode("ascii"),
                }
                for name, inhalt in sorted(self.dateien.items())
            ],
        }


def lieferung_aus(akte: Ergebnisakte) -> Lieferung | None:
    """Die Lieferung dieser Akte — oder ``None``, wenn der Lauf einen Sperrgrund trägt.

    Freigegeben ist jeder Lauf mit Akte; erst ohne Sperrgrund ist die Freigabe
    auch eine Übergabe an BC3 (Nachtrag #305, Punkt 5).
    """
    if not akte.lieferbar:
        return None
    return Lieferung(
        ordner=akte.ordner,
        paket_id=akte.paket_id,
        fassung=akte.fassung,
        dateien={d.name: d.inhalt for d in akte.fuer("bc3")},
    )


def lieferungen(gate1_buch: Gate1Buch) -> list[Lieferung]:
    """Alle gelieferten Läufe, nach ``paket_id``."""
    return [l for a in gate1_buch.lieferbare_akten() if (l := lieferung_aus(a)) is not None]


def als_json(gefunden: list[Lieferung]) -> dict:
    """Die Ausgabe von ``python -m lieferung`` und ``GET /api/lieferungen``."""
    return {"lieferungen": [l.als_json() for l in gefunden]}


def _lieferschluessel() -> str:
    return (os.environ.get("BC2_LIEFERUNG_TOKEN") or "").strip()


def erzeuge_router(gate1_buch: Gate1Buch) -> APIRouter:
    """``GET /api/lieferungen`` — die Lieferungen für die Action (#388).

    Nur lesend, und nur die ``bc3``-Dateien lieferbarer Akten. Ohne gesetzten
    Schlüssel antwortet er wie ein Pfad, den es nicht gibt (404): ein leerer
    Schlüssel darf nie passen, und abgeschaltet soll nicht wie kaputt aussehen.
    Der Vergleich läuft in gleichbleibender Zeit, wie beim Trigger.
    """
    router = APIRouter()

    @router.get("/api/lieferungen", include_in_schema=False)
    def lieferungen_abrufen(request: Request):
        erwartet = _lieferschluessel()
        if not erwartet:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        kopf = request.headers.get("authorization") or ""
        if not (kopf.lower().startswith("bearer ")
                and hmac.compare_digest(kopf[7:].strip(), erwartet)):
            return JSONResponse({"fehler": "Schluessel fehlt oder stimmt nicht."},
                                status_code=401)
        try:
            gefunden = lieferungen(gate1_buch)
        except Exception as e:  # noqa: BLE001 — die Action soll rot werden, nicht raten
            log.error("Lieferungen nicht lesbar: %s", e)
            return JSONResponse({"fehler": "Datenbank nicht erreichbar."}, status_code=503)
        log.info("Lieferungen abgerufen: %d", len(gefunden))
        return JSONResponse(als_json(gefunden), headers={"Cache-Control": "no-store"})

    return router


def main() -> int:
    from gate1 import PostgresGate1Buch

    gefunden = lieferungen(PostgresGate1Buch(nur_lesen=True))
    json.dump(
        als_json(gefunden),
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
