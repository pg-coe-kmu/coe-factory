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

from .rechnen import Nutzwert, Nutzwertkategorie, Potenzialeingang, Schrittmessung

#: Felder, die bis #288 flach am Potenzial standen. Seit Nachtrag 4 stehen sie
#: je berührtem Teilprozess unter ``messungen`` — eine alte Datei soll laut
#: scheitern, statt still ohne Messung gerechnet zu werden.
_ALTE_FELDER = (
    "frequency_per_year",
    "total_duration_minutes",
    "focus_step_duration_source",
    "focus_step_duration_confidence_pct",
    "reifeskalen",
    "automation_potential_estimate_pct",
    "erhebung_id",
    "kennzeichnung",
)

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
        alt = [f for f in _ALTE_FELDER if f in felder]
        if alt:
            raise ValueError(
                f"{pfad.name}, {felder.get('potenzial_id')}: Felder {alt} stehen am "
                "Potenzial. Seit #288 (ADR-006 · BC2, Nachtrag 4) gehoeren sie je "
                "beruehrtem Teilprozess unter 'messungen'."
            )
        felder["betroffene_teilprozess_ids"] = tuple(felder["betroffene_teilprozess_ids"])
        messungen = []
        for m in felder.pop("messungen", None) or []:
            m = dict(m)
            if m.get("reifeskalen") is not None:
                m["reifeskalen"] = tuple(m["reifeskalen"])
            messungen.append(Schrittmessung(**m))
        felder["messungen"] = tuple(messungen)
        eingaenge.append(Potenzialeingang(**felder))

    return Messsatz(roh["company_id"], roh["paket_id"], eingaenge, roh.get("warnung"))


def lies_eingaenge(
    pfad: Path | str,
) -> tuple[str, str, list[Potenzialeingang], str | None]:
    """Die Form, die ``tools/kalibrierung.py`` erwartet."""
    satz = lies_messsatz(pfad)
    return satz.company_id, satz.paket_id, satz.eingaenge, satz.warnung
