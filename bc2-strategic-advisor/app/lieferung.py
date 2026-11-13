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
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from dataclasses import dataclass

from ergebnisakte import Ergebnisakte, mandantenkuerzel, ordnername
from gate1 import Gate1Buch

__all__ = [
    "Lieferung",
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


def main() -> int:
    from gate1 import PostgresGate1Buch

    gefunden = lieferungen(PostgresGate1Buch(nur_lesen=True))
    json.dump(
        {"lieferungen": [l.als_json() for l in gefunden]},
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
