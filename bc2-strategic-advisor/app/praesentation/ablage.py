"""
BC2 · Der dünne Aufrufer: die gezeichnete Präsentation zu Bytes machen (#257).

Der Foliensatz entsteht im Speicher (:func:`praesentation.baue_praesentation`);
hier wird er zu Bytes für den Download.

**Die Präsentation ist kein Teil der Lieferung.** Sie geht an den Mandanten,
nicht an BC3, und liegt darum nicht im Lieferordner (ADR-007 · BC2, Nachtrag
#305, Punkt 4) — bis dahin legte der Dienst sie dort ab (#257).
"""

from __future__ import annotations

import io

from pptx import Presentation

__all__ = ["DATEINAME", "als_bytes"]

#: Ohne ``f<n>``: die Fassung steht auf der Titelfolie. Im Dateinamen würde sie
#: beim Kopieren der Datei widersprüchlich (#244).
DATEINAME = "praesentation.pptx"


def als_bytes(prs: Presentation) -> bytes:
    puffer = io.BytesIO()
    prs.save(puffer)
    return puffer.getvalue()
