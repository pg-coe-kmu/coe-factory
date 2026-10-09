"""
BC2 · Der Ausarbeitungsschritt (#301, ADR-010 · BC2).

Aus einem **gerechneten** Lauf werden lieferbare Konzepte: die Texte, die BC3
zu Tickets schneidet und der Mandant in der Präsentation liest — Beschreibung,
Soll-Vision, User Story, Akzeptanzkriterien, Kontext —, zusammengesetzt mit dem,
was Python maschinell beiträgt, und die Ausgangslage des Laufs dazu. Damit legt
der echte Weg einen schemagültigen Vertrag 3.1 ab.

Vier Teile, dieselbe Bauform wie :mod:`erkennung` und :mod:`bewertung`:

- :mod:`~ausarbeitung.nutzlast` — was das Modell je Konzept sieht. Keine Zahl
  aus der Rechnung.
- :mod:`~ausarbeitung.anweisung` — die Anweisung, mit den zwei Platzhaltern.
- :mod:`~ausarbeitung.pruefen` — der Wächter: Pflichtfelder, Schablonen,
  Systeme aus dem Bestand, Rechenverbot.
- :mod:`~ausarbeitung.ausarbeiten` — der Ablauf, ein Aufruf je Konzept,
  parallel, mit einer Wiederholung; dazu das Zusammensetzen.

Kürzester Weg::

    from ausarbeitung import arbeite_aus

    ausarbeitung = arbeite_aus(lauf, ansicht.potenziale, erkennung,
                               bewertung.kennungen, bestand, modell)
"""

from .anweisung import ANWEISUNG, PLATZHALTER, baue_frage
from .ausarbeiten import Ausarbeitung, AusarbeitungAbgebrochen, arbeite_aus, setze_ein
from .nutzlast import baue_nutzlast
from .pruefen import Erwartung, pruefe_ausarbeitung

__all__ = [
    "ANWEISUNG",
    "PLATZHALTER",
    "Ausarbeitung",
    "AusarbeitungAbgebrochen",
    "Erwartung",
    "arbeite_aus",
    "baue_frage",
    "baue_nutzlast",
    "pruefe_ausarbeitung",
    "setze_ein",
]
