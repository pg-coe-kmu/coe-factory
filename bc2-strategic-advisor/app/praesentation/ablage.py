"""
BC2 · Der dünne Aufrufer: die gezeichnete Präsentation ablegen (#257).

Der Foliensatz entsteht im Speicher (:func:`praesentation.baue_praesentation`);
hier wird er zu Bytes und — falls es den Ort gibt — in den Lieferordner
geschrieben. **Ein Erzeugungsvorgang, zwei Empfänger** (#244): der Endpunkt
liefert dieselben Bytes aus, die er ablegt, damit Download und Ablage nicht
auseinanderlaufen können.

**Die Präsentation ist kein Vertragsgegenstand.** Sie liegt neben Konzepten und
Priorisierung, weil ADR-006 verlangt, dass eine Lieferung ohne Datenbank prüfbar
ist; aber ``validate.py`` fasst sie nicht an, und ihr Fehlen bricht keine
Lieferung.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from pptx import Presentation

__all__ = ["DATEINAME", "als_bytes", "lege_ab", "lieferordner", "mandantenkuerzel"]

#: Ohne ``f<n>``: die Fassung steht im Ordnernamen und auf der Titelfolie. Im
#: Dateinamen würde sie beim Kopieren der Datei widersprüchlich (#244).
DATEINAME = "praesentation.pptx"


def als_bytes(prs: Presentation) -> bytes:
    puffer = io.BytesIO()
    prs.save(puffer)
    return puffer.getvalue()


def mandantenkuerzel(name: str | None, company_id: str) -> str:
    """Der ``<company>``-Teil des Ordnernamens aus ADR-007 (2.2).

    ADR-007 legt ``<company>-<paket_id>-f<n>`` fest, aber nicht, woraus
    ``<company>`` entsteht; die einzige vorhandene Lieferung nennt NoroAI
    ``noroai``. Hier: das erste Wort des Mandantennamens, klein, nur Buchstaben
    und Ziffern — und ohne Namen die ersten acht Zeichen der ``company_id``,
    statt einen Namen zu raten. **Annahme aus #257**, rückbaubar an dieser
    einen Stelle.
    """
    teile = (name or "").split()
    if teile:
        erstes = re.sub(r"[^a-z0-9]", "", teile[0].lower())
        if erstes:
            return erstes
    return company_id[:8].lower()


def lieferordner(basis: Path, kuerzel: str, paket_id: str, fassung: int) -> Path:
    """``<basis>/<company>-<paket_id>-f<n>`` — derselbe Schnitt wie für Konzepte und Priorisierung."""
    return Path(basis) / f"{kuerzel}-{paket_id}-f{fassung}"


def lege_ab(daten: bytes, ordner: Path) -> Path:
    """Schreibt die Präsentation in den Lieferordner und gibt den Pfad zurück.

    Der Ordner wird angelegt, die **Basis** nicht: fehlt sie, ist das kein
    Grund, sie irgendwo zu erfinden — der Aufrufer entscheidet, ob er ohne
    Ablage ausliefert.
    """
    ordner = Path(ordner)
    if not ordner.parent.is_dir():
        raise FileNotFoundError(f"Lieferungen-Verzeichnis fehlt: {ordner.parent}")
    ordner.mkdir(exist_ok=True)
    ziel = ordner / DATEINAME
    ziel.write_bytes(daten)
    return ziel
