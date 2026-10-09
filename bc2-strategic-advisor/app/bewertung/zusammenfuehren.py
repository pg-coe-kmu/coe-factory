"""
BC2 · Mehrere Urteile über denselben Lauf zu einem zusammenführen (#299).

Ein Aufruf je Lauf urteilt nicht stabil genug für eine Rangfolge (ADR-006 ·
BC2, 6.2, gescheitert in #288). Der Schnitt bleibt **ein Aufruf je Lauf** —
ein Urteiler, ein Maßstab —, wird aber *n*-mal gestellt, und je Feld gilt der
**Median**. Temperatur 0 ist bewusst kein Ersatz: sie friert eine Ziehung ein,
statt sie zu glätten, und die Nachfolger von Sonnet 4.6 lehnen sie ab.

Die Regeln (Q7 in #299):

- **Nutzwert, Aufwand:** Median je Feld. Die Begründung kommt aus dem ersten
  Urteil, dessen Wert der Median ist — Zahl und Satz gehören zusammen.
- **Lage im Korridor:** Median von Unter- und Obergrenze **getrennt**. Weil
  jedes einzelne Urteil im Korridor liegt und min ≤ max hält, tut es der Median
  auch. Die Begründung kommt aus dem Urteil, das der Mediangrenze am nächsten
  liegt.
- **Komplexität:** ein Urteil ohne Überschreiben zählt mit dem gemessenen Wert.
  Landet der Median dort, gilt sie als **nicht** überschrieben.
- **Klassenzweifel:** reist nur mit, wenn ihn die **Mehrheit** äußert —
  ein einzelner wäre Rauschen am Gate 1.

*n* muss ungerade sein: der Median ist dann ein Element der Urteile, also eine
ganze Zahl, wo der Wächter eine verlangt. Die Streuung (kleinster und größter
Wert) geht ins Protokoll, nicht in den Vertrag.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from .pruefen import KATEGORIEN, Erwartung

__all__ = ["Zusammenfuehrung", "fuehre_zusammen"]


@dataclass(frozen=True)
class Zusammenfuehrung:
    #: Dieselbe Form wie eine einzelne Antwort: ``{"bewertungen": [...]}``.
    antwort: dict[str, Any]
    #: Potenzial → Feld → (kleinster, größter) Wert über alle Urteile.
    streuung: dict[str, dict[str, tuple[float, float]]]


def _erstes(urteile: list[dict], passt) -> dict:
    return next(u for u in urteile if passt(u))


def _fuehre_eines_zusammen(urteile: list[dict], erwartung: Erwartung) -> tuple[dict, dict]:
    pid = urteile[0]["id"]
    streuung: dict[str, tuple[float, float]] = {}

    nutzwert = {}
    for k in KATEGORIEN:
        werte = [u["nutzwert"][k]["wert"] for u in urteile]
        m = median(werte)
        streuung[k] = (min(werte), max(werte))
        quelle = _erstes(urteile, lambda u: u["nutzwert"][k]["wert"] == m)
        nutzwert[k] = {"wert": m, "begruendung": quelle["nutzwert"][k]["begruendung"]}

    lo = median(u["angesetzt_min_pct"] for u in urteile)
    hi = median(u["angesetzt_max_pct"] for u in urteile)
    lage = min(
        urteile,
        key=lambda u: abs(u["angesetzt_min_pct"] - lo) + abs(u["angesetzt_max_pct"] - hi),
    )
    streuung["angesetzt_min_pct"] = (
        min(u["angesetzt_min_pct"] for u in urteile),
        max(u["angesetzt_min_pct"] for u in urteile),
    )
    streuung["angesetzt_max_pct"] = (
        min(u["angesetzt_max_pct"] for u in urteile),
        max(u["angesetzt_max_pct"] for u in urteile),
    )

    def wirksam(u: dict) -> int:
        k = u.get("komplexitaet_ueberschrieben")
        return erwartung.gemessene_komplexitaet if k is None else k

    komplexitaeten = [wirksam(u) for u in urteile]
    k_median = median(komplexitaeten)
    streuung["komplexitaet"] = (min(komplexitaeten), max(komplexitaeten))
    if k_median == erwartung.gemessene_komplexitaet:
        k_ueber, k_text = None, None
    else:
        quelle = _erstes(urteile, lambda u: u.get("komplexitaet_ueberschrieben") == k_median)
        k_ueber, k_text = k_median, quelle.get("komplexitaet_begruendung")

    aufwaende = [u["aufwand_schaetzung_pt"] for u in urteile]
    pt = median(aufwaende)
    streuung["aufwand_schaetzung_pt"] = (min(aufwaende), max(aufwaende))
    pt_quelle = _erstes(urteile, lambda u: u["aufwand_schaetzung_pt"] == pt)

    zweifel = [u for u in urteile if (u.get("klassenzweifel") or "").strip()]
    klassenzweifel = zweifel[0]["klassenzweifel"] if len(zweifel) * 2 > len(urteile) else None

    return (
        {
            "id": pid,
            "angesetzt_min_pct": lo,
            "angesetzt_max_pct": hi,
            "korridor_begruendung": lage["korridor_begruendung"],
            "nutzwert": nutzwert,
            "komplexitaet_ueberschrieben": k_ueber,
            "komplexitaet_begruendung": k_text,
            "aufwand_schaetzung_pt": pt,
            "aufwand_begruendung": pt_quelle.get("aufwand_begruendung"),
            "klassenzweifel": klassenzweifel,
        },
        streuung,
    )


def fuehre_zusammen(
    antworten: list[dict[str, Any]], erwartet: dict[str, Erwartung]
) -> Zusammenfuehrung:
    """Führt *n* vom Wächter geprüfte Antworten zu einer zusammen.

    :param antworten: geprüfte Antworten in der Form ``{"bewertungen": [...]}``.
    :param erwartet: je Erkennungsnummer, was der Wächter weiß — hier gebraucht
        für die gemessene Komplexität.
    :raises ValueError: bei gerader oder leerer Anzahl.
    """
    if not antworten or len(antworten) % 2 == 0:
        raise ValueError(
            f"Zusammengefuehrt wird eine ungerade Zahl von Urteilen, nicht {len(antworten)}: "
            "nur dann ist der Median eines von ihnen."
        )
    je_antwort = [{str(b["id"]): b for b in a["bewertungen"]} for a in antworten]
    bewertungen = []
    streuung = {}
    for pid in erwartet:
        eintrag, s = _fuehre_eines_zusammen([j[pid] for j in je_antwort], erwartet[pid])
        bewertungen.append(eintrag)
        streuung[pid] = s
    return Zusammenfuehrung(antwort={"bewertungen": bewertungen}, streuung=streuung)
