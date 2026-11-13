"""
BC2 · Die Präsentation (#257, Format und Weg entschieden in #244).

PPTX über ``python-pptx``, aus Code **gezeichnet** — nicht das alte Template
befüllt: ``python-pptx`` kann keine Folien duplizieren, und ein Lauf trägt rund
zehn Potenziale gegen sechs Kacheln im Template.

Zwei Teile, getrennt wie in ``modell/`` (#238):

- :mod:`~praesentation.folien` — die **reine Funktion**: Konzepte +
  Priorisierung → ``Presentation`` im Speicher. Mit
  :mod:`~praesentation.formulierung` (wie Zahlen auf die Folie kommen) und
  :mod:`~praesentation.zeichnen` (Palette und Formen aus dem KIsult-Schnitt) und
  :mod:`~praesentation.absaetze` (Markdown in Absätze, teilen statt schrumpfen, #380).
- :mod:`~praesentation.ablage` — der **dünne Aufrufer**: zu Bytes machen für
  den Download. Sie geht an den Mandanten, nicht an BC3 (#305); gezeichnet
  wird sie einmal, beim Freigeben, und liegt in der Ergebnisakte (#378).

Kürzester Weg::

    from praesentation import baue_praesentation, als_bytes

    prs = baue_praesentation(konzepte, priorisierung)   # wirft vor der Freigabe
    daten = als_bytes(prs)
"""

from .ablage import DATEINAME, als_bytes
from .folien import KeineFreigabe, baue_praesentation

__all__ = [
    "DATEINAME",
    "KeineFreigabe",
    "als_bytes",
    "baue_praesentation",
]
