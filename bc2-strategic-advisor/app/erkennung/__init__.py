"""
BC2 · Der Erkennungsschritt (#194 entschieden, #248 gebaut).

Aus dem freigegebenen Datenstand eines Pakets werden **Potenziale**: ein
Modellaufruf über das ganze Paket (Schnitt C), qualitativ geurteilt, in Python
deterministisch nachkontrolliert.

Fünf Teile, bewusst getrennt:

- :mod:`~erkennung.bestand` — die **Leseseite**. Protokoll ``Bestandsquelle``,
  dahinter Postgres (``stand_zum(uebergeben_am)``) und BC0s Snapshot.
- :mod:`~erkennung.nutzlast` — was das Modell zu sehen bekommt. Entdoppelt den
  Kernprozess-Text und fällt über der Grenze auf Schnitt B zurück.
- :mod:`~erkennung.anweisung` — die Anweisung. Trägt den Trenntest, die fünf
  Lösungsklassen des Vertrags und das Rechenverbot.
- :mod:`~erkennung.modellruf` — die **Naht zum Modell**. SDK (Betrieb), CLI
  (Werkbank), Doppelgänger (Tests).
- :mod:`~erkennung.pruefen` — die deterministische Nachkontrolle, portiert aus
  dem Prototyp zu #194.

Was **nicht** hier liegt: Value, Nutzwert und Priorisierung (:mod:`modell`,
ADR-006 · BC2) sowie die drei noch offenen Urteilsstellen des LLM — siehe
:mod:`~erkennung.erkennen`.

Kürzester Weg::

    from erkennung import SnapshotBestand, CliModell, erkenne

    quelle = SnapshotBestand(pfad)
    bestand = quelle.lies_paket(company_id, paket_id, uebergeben_am, teilprozesse)
    ergebnis = erkenne(bestand, CliModell())

    for p in ergebnis.potenziale:
        print(p.kernprozess_id, p.klasse, p.titel)
"""

from .anweisung import ANWEISUNG, baue_frage
from .bestand import (
    Bc1Profil,
    Bestandsquelle,
    Bewertung,
    HistorieZuAlt,
    Kernprozess,
    Mandant,
    Paketbestand,
    PostgresBestand,
    SnapshotBestand,
    Teilprozess,
)
from .erkennen import (
    Aufrufprotokoll,
    Erkennung,
    ErkennungAbgebrochen,
    ErkanntesPotenzial,
    NichtGeschnitten,
    erkenne,
)
from .modellruf import Antwort, CliModell, Doppelgaenger, Modellruf, SdkModell
from .nutzlast import GRENZE_ZEICHEN, Aufruf, packe
from .pruefen import Paar, Pruefbericht, paare_im_kernprozess, pruefe_schnitt

__all__ = [
    "ANWEISUNG",
    "Antwort",
    "Aufruf",
    "Aufrufprotokoll",
    "Bc1Profil",
    "Bestandsquelle",
    "Bewertung",
    "CliModell",
    "Doppelgaenger",
    "Erkennung",
    "ErkennungAbgebrochen",
    "ErkanntesPotenzial",
    "GRENZE_ZEICHEN",
    "HistorieZuAlt",
    "Kernprozess",
    "Mandant",
    "Modellruf",
    "NichtGeschnitten",
    "Paar",
    "Paketbestand",
    "PostgresBestand",
    "Pruefbericht",
    "SdkModell",
    "SnapshotBestand",
    "Teilprozess",
    "baue_frage",
    "erkenne",
    "paare_im_kernprozess",
    "packe",
    "pruefe_schnitt",
]
