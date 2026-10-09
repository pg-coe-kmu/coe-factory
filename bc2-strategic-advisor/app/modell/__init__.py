"""
BC2 · Das Value- und Priorisierungsmodell (ADR-006 · BC2, Bau in #238).

Drei Teile, bewusst getrennt:

- ``parameter`` — die **Setzungen**, darunter die beiden unter
  Kalibrierungsvorbehalt (Euro-Schwellen, Score-Bänder). Getrennt, damit sie am
  ersten echten Lauf verschoben werden können, ohne den Kern anzufassen.
- ``rechnen`` — der **Rechenkern**. Eine reine Funktion: liest nichts, schreibt
  nichts, ruft kein LLM. Gleiche Eingänge, gleiche Zahlen.
- ``ausgabe`` — die Abbildung in den **Vertrag v3.0**. Ändert BC3 den Vertrag,
  ändert sich nur diese Datei.

Was **nicht** hier liegt: das Lesen aus der gemeinsamen Datenbank auf
``stand_zum(uebergeben_am)`` und das Erkennen, welche Potenziale ein Paket
trägt. Das gehört zu #194.

Kürzester Weg::

    from modell import Potenzialeingang, rechne_lauf

    lauf = rechne_lauf("<company_id>", "<paket_id>", [eingang, ...])
    for pot in lauf.potenziale:          # bereits nach Rang sortiert
        print(pot.potenzialrang, pot.prioritaetsgruppe, pot.titel)
"""

from .parameter import STANDARD, Klasse, Parameter
from .rechnen import (
    Automatisierungsgrad,
    Hinweis,
    Lauf,
    Nutzwert,
    Nutzwertkategorie,
    Potenzial,
    Potenzialeingang,
    Prozessrang,
    Quellwert,
    Spanne,
    Value,
    rechne_lauf,
    runde,
)

__all__ = [
    "STANDARD",
    "Automatisierungsgrad",
    "Hinweis",
    "Klasse",
    "Lauf",
    "Nutzwert",
    "Nutzwertkategorie",
    "Parameter",
    "Potenzial",
    "Potenzialeingang",
    "Prozessrang",
    "Quellwert",
    "Spanne",
    "Value",
    "rechne_lauf",
    "runde",
]
