"""
BC2 · Der Bewertungsschritt (#260 entschieden, #288 gebaut).

Aus den **erkannten** Potenzialen eines Laufs werden vollständige
``modell.Potenzialeingang``: ein Modellaufruf über alle Potenziale (ADR-006 ·
BC2, 6.2), deterministisch bewacht (6.5), dazu BC1s Messungen je berührtem
Teilprozess (Nachtrag 4).

Vier Teile, dieselbe Bauform wie :mod:`erkennung`:

- :mod:`~bewertung.nutzlast` — was das Modell sieht: die Potenziale, die
  berührten Teilprozesse, Korridor und gemessene Komplexität. **Keine** Stunden,
  Euro oder Dauern (6.3).
- :mod:`~bewertung.anweisung` — die Anweisung; die Anker kommen aus
  :mod:`modell.parameter`.
- :mod:`~bewertung.pruefen` — der Wächter.
- :mod:`~bewertung.bewerten` — der Ablauf, mit einer Wiederholung.

Die Naht zum Modell ist dieselbe wie in der Erkennung
(:mod:`erkennung.modellruf`) — SDK im Betrieb, CLI auf der Werkbank,
Doppelgänger in den Tests.

Kürzester Weg::

    from erkennung import SnapshotBestand, CliModell, erkenne
    from bewertung import bewerte
    from modell import rechne_lauf

    bestand = SnapshotBestand(pfad).lies_paket(company_id, paket_id, uebergeben_am, tps)
    modell = CliModell()
    bewertung = bewerte(erkenne(bestand, modell), bestand, modell)
    lauf = rechne_lauf(company_id, paket_id, bewertung.eingaenge)
"""

from .anweisung import ANWEISUNG, baue_frage
from .bewerten import Bewertung, BewertungAbgebrochen, bewerte
from .nutzlast import baue_nutzlast, messungen_je_teilprozess
from .pruefen import Erwartung, pruefe_bewertung

__all__ = [
    "ANWEISUNG",
    "Bewertung",
    "BewertungAbgebrochen",
    "Erwartung",
    "baue_frage",
    "baue_nutzlast",
    "bewerte",
    "messungen_je_teilprozess",
    "pruefe_bewertung",
]
