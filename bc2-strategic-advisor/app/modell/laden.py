"""
BC2 · Einen Messsatz in Modell-Eingänge lesen.

Ein Messsatz ist eine JSON-Datei unter ``bc2-strategic-advisor/kalibrierung/``:
``company_id``, ``paket_id`` und eine Liste von Potenzialen in genau den Feldern
von :class:`~modell.rechnen.Potenzialeingang`.

**Warum das im Modell liegt und nicht beim Werkzeug.** Die Funktion kennt die
Modelltypen und sonst nichts — sie gehört dorthin, wo diese Typen definiert
sind. Sie stand bis zum Bau der Oberfläche (#243) in
``tools/kalibrierung.py``; dort wäre sie ein zweites Mal entstanden, sobald ein
zweiter Aufrufer sie braucht. Genau das trat ein: die Oberfläche zeigt einen
Lauf, und solange der Erkennungsschritt nicht gebaut ist (Schnitt entschieden in
#194, Bau #248), ist ein Messsatz die einzige Quelle dafür.

**Was ein Messsatz nicht ist: ein Lauf aus der Datenbank.** Die Zahlen sind
erhoben oder erfunden, aber sie sind nicht auf ``stand_zum(uebergeben_am)``
gelesen. Wer daraus eine Lieferung an BC3 erzeugte, lieferte einen Stand, den
niemand nachrechnen kann. Die Datei trägt dafür ein Feld ``warnung``, und wer
sie liest, reicht es weiter.
"""

from __future__ import annotations

import json
from pathlib import Path

from .rechnen import Nutzwert, Nutzwertkategorie, Potenzialeingang

__all__ = ["Messsatz", "lies_messsatz", "lies_eingaenge"]


class Messsatz:
    """Ein gelesener Messsatz: Kennungen, Eingänge und die Warnung der Datei."""

    def __init__(
        self,
        company_id: str,
        paket_id: str,
        eingaenge: list[Potenzialeingang],
        warnung: str | None = None,
    ) -> None:
        self.company_id = company_id
        self.paket_id = paket_id
        self.eingaenge = eingaenge
        self.warnung = warnung


def lies_messsatz(pfad: Path | str) -> Messsatz:
    """Liest eine Messsatz-Datei."""
    pfad = Path(pfad)
    roh = json.loads(pfad.read_text(encoding="utf-8"))

    eingaenge = []
    for p in roh["potenziale"]:
        # Kopie, damit die Datei mehrfach gelesen werden kann: die
        # Vorgängerfassung in tools/kalibrierung.py arbeitete mit ``pop`` auf
        # dem geladenen Wörterbuch. Beim einmaligen Aufruf eines Skripts
        # gleichgültig, beim Dienst nicht — der liest denselben Satz je Anfrage.
        felder = dict(p)
        nw = felder.pop("nutzwert")
        felder["nutzwert"] = Nutzwert(
            **{
                schluessel: Nutzwertkategorie(eintrag["wert"], eintrag["begruendung"])
                for schluessel, eintrag in nw.items()
            }
        )
        for schluessel in ("betroffene_teilprozess_ids", "reifeskalen"):
            if felder.get(schluessel) is not None:
                felder[schluessel] = tuple(felder[schluessel])
        eingaenge.append(Potenzialeingang(**felder))

    return Messsatz(roh["company_id"], roh["paket_id"], eingaenge, roh.get("warnung"))


def lies_eingaenge(
    pfad: Path | str,
) -> tuple[str, str, list[Potenzialeingang], str | None]:
    """Die Form, die ``tools/kalibrierung.py`` erwartet."""
    satz = lies_messsatz(pfad)
    return satz.company_id, satz.paket_id, satz.eingaenge, satz.warnung
