"""
BC2 · Die Präsentation (#257, Format und Weg entschieden in #244).

PPTX über ``python-pptx``, aus Code **gezeichnet** — nicht das alte Template
befüllt: ``python-pptx`` kann keine Folien duplizieren, und ein Lauf trägt rund
zehn Potenziale gegen sechs Kacheln im Template.

Zwei Teile, getrennt wie in ``modell/`` (#238):

- :mod:`~praesentation.folien` — die **reine Funktion**: Konzepte +
  Priorisierung → ``Presentation`` im Speicher. Mit
  :mod:`~praesentation.formulierung` (wie Zahlen auf die Folie kommen) und
  :mod:`~praesentation.zeichnen` (Palette und Formen aus dem KIsult-Schnitt).
- :mod:`~praesentation.ablage` — der **dünne Aufrufer**: zu Bytes machen und
  in ``lieferungen/<company>-<paket_id>-f<n>/praesentation.pptx`` ablegen.

Kürzester Weg::

    from praesentation import baue_praesentation, als_bytes

    prs = baue_praesentation(konzepte, priorisierung)   # wirft vor der Freigabe
    daten = als_bytes(prs)
"""

from .ablage import DATEINAME, als_bytes, lege_ab, lieferordner, mandantenkuerzel
from .folien import KeineFreigabe, baue_praesentation

__all__ = [
    "DATEINAME",
    "KeineFreigabe",
    "als_bytes",
    "baue_praesentation",
    "lege_ab",
    "lieferordner",
    "mandantenkuerzel",
]
