"""
BC2 · Die Lieferung an BC3 — was aus Schema ``bc2`` in den Lieferordner gehört.

**Die Datenbank ist der eine Ort, der Lieferordner ihre Abbildung** (ADR-007 ·
BC2, Nachtrag #305). Schema ``bc2`` trägt den ganzen Vertrag: das
Priorisierungsdokument, die Konzepte und — zerlegt — die Gate-1-Entscheidung.
Der Dienst schreibt darum keine Lieferdateien; er sagt nur, was geliefert ist.

Die Arbeit ist zweigeteilt, weil die beiden Hälften an verschiedenen Orten
leben:

- **hier, im Dienst:** auswählen und zusammensetzen — freigegebene Läufe ohne
  Sperrgrund, Priorisierung plus ``gate1``, die Konzepte. Hier liegt der
  Datenbankzugang (ADR-003: die ``DATABASE_URL`` verlässt den Server nicht).
- **``tools/lieferung_ziehen.py``, lokal:** in Dateien schreiben. Dort liegen
  die Vertragsschemas, nach denen die Schlüssel geordnet werden, und der
  Arbeitsbaum, aus dem ein Mensch den PR öffnet.

Aufruf auf dem VPS, nur lesend::

    docker exec app-app-1 python -m lieferung > lieferungen.json
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field

from ablage import AbgelegterLauf, Ergebnisbuch
from gate1 import Gate1Buch, Gate1Entscheidung

__all__ = [
    "Lieferung",
    "lieferung_aus",
    "lieferungen",
    "mandantenkuerzel",
    "ordnername",
]


def mandantenkuerzel(name: str | None, company_id: str) -> str:
    """Der ``<company>``-Teil des Ordnernamens aus ADR-007 (2.2).

    ADR-007 legt ``<company>-<paket_id>-f<n>`` fest, aber nicht, woraus
    ``<company>`` entsteht; die erste Lieferung nennt NoroAI ``noroai``. Hier:
    das erste Wort des Mandantennamens, klein, nur Buchstaben und Ziffern —
    und ohne Namen die ersten acht Zeichen der ``company_id``, statt einen
    Namen zu raten. **Annahme aus #257**, rückbaubar an dieser einen Stelle.
    """
    teile = (name or "").split()
    if teile:
        erstes = re.sub(r"[^a-z0-9]", "", teile[0].lower())
        if erstes:
            return erstes
    return company_id[:8].lower()


def ordnername(kuerzel: str, paket_id: str, fassung: int) -> str:
    """``<company>-<paket_id>-f<n>`` (ADR-007 · BC2, 2.2)."""
    return f"{kuerzel}-{paket_id}-f{fassung}"


@dataclass(frozen=True)
class Lieferung:
    """Ein gelieferter Lauf, so wie er in den Ordner gehört — noch nicht als Datei."""

    ordner: str
    #: ``prozesspriorisierung.json``: das abgelegte Dokument plus ``gate1``.
    priorisierung: dict
    #: ``konzept_<KP>.json`` je Konzept, in der Reihenfolge von ``konzept_ids``.
    konzepte: list[dict]
    #: Für die Nachricht an BC3 — nicht für den Vertrag (Nachtrag #305, Punkt 5).
    hinweise: tuple[str, ...] = ()
    kp_namen: dict[str, str] = field(default_factory=dict)
    #: Was hinter den Kennungen von Vorgängern und Gestrichenen steht.
    verwiesen: dict[str, dict] = field(default_factory=dict)

    def als_json(self) -> dict:
        return {
            "ordner": self.ordner,
            "priorisierung": self.priorisierung,
            "konzepte": self.konzepte,
            "hinweise": list(self.hinweise),
            "kp_namen": self.kp_namen,
            "verwiesen": self.verwiesen,
        }


def _verwiesene_ids(priorisierung: dict, konzepte: list[dict]) -> list[str]:
    ids = {
        alt
        for k in konzepte
        for p in k.get("potenziale", [])
        for alt in p.get("ersetzt_potenzial_ids") or []
    } | {g["potenzial_id"] for g in priorisierung.get("gestrichene_potenziale") or []}
    return sorted(ids)


def lieferung_aus(
    lauf: AbgelegterLauf,
    entscheidung: Gate1Entscheidung | None,
    verwiesen: dict[str, dict] | None = None,
) -> Lieferung | None:
    """Die Lieferung dieses Laufs — oder ``None``, wenn er keine hat.

    Keine hat, wer nicht freigegeben ist oder einen Sperrgrund trägt: die
    Freigabe ist die Entscheidung des Menschen, der Sperrgrund ein Merkmal
    des Laufs, und erst beides zusammen ist eine Übergabe an BC3.
    """
    if (
        not lauf.geliefert
        or lauf.dokument is None
        or entscheidung is None
        or entscheidung.status != "approved"
    ):
        return None
    dok = lauf.dokument
    priorisierung = {**dok, "gate1": entscheidung.als_vertrag()}
    name = ((dok.get("ausgangslage") or {}).get("unternehmen") or {}).get("name")
    return Lieferung(
        ordner=ordnername(
            mandantenkuerzel(name, lauf.beleg.company_id),
            lauf.beleg.paket_id,
            lauf.beleg.fassung,
        ),
        priorisierung=priorisierung,
        konzepte=list(lauf.konzepte),
        hinweise=tuple(lauf.hinweise),
        kp_namen=dict(lauf.kp_namen),
        verwiesen=dict(verwiesen or {}),
    )


def lieferungen(buch: Ergebnisbuch, gate1_buch: Gate1Buch) -> list[Lieferung]:
    """Alle gelieferten Läufe, nach ``paket_id``."""
    ergebnis = []
    for paket_id in buch.geliefert():
        lauf = buch.letzter(paket_id)
        if lauf is None or lauf.dokument is None:
            continue
        entscheidung = gate1_buch.lesen(paket_id, lauf.beleg.fassung)
        ids = _verwiesene_ids(lauf.dokument, lauf.konzepte)
        verwiesen = buch.nachschlagen(lauf.beleg.company_id, ids) if ids else {}
        lieferung = lieferung_aus(lauf, entscheidung, verwiesen)
        if lieferung is not None:
            ergebnis.append(lieferung)
    return ergebnis


def main() -> int:
    from ablage import PostgresErgebnisbuch
    from gate1 import PostgresGate1Buch

    gefunden = lieferungen(
        PostgresErgebnisbuch(nur_lesen=True), PostgresGate1Buch(nur_lesen=True)
    )
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
