"""
BC2 · Was der Ausarbeitungsschritt zu sehen bekommt — je Konzept eine Nutzlast.

**Ein Aufruf je Konzept** (ADR-010 · BC2, 2.2): das Konzept ist die Einheit, in
der die Texte stehen, und seine Ausgabe bleibt begrenzt, auch wenn ein Paket
zwanzig Potenziale trägt. Was ein Aufruf so nicht sähe — die Potenziale der
anderen Kernprozesse —, bekommt er als knappe Liste mit, damit
``querschnitte.abhaengigkeiten`` über Kernprozesse hinweg zeigen kann.

**Keine Zahl aus der Rechnung.** Weder Value noch Stunden noch Lage im Korridor
stehen hier als Zahl: der Schritt läuft nach dem Rechenkern, und was er an Zahlen
sähe, schriebe er ab (#194: das Rechenverbot brach genau dort, wo Zahlen in der
Nutzlast standen). Wo ein Kriterium den Automatisierungsgrad braucht, schreibt
das Modell einen Platzhalter, und Python setzt die gerechnete Zahl ein. Rang und
Prioritätsgruppe stehen da — sie tragen keine Einheit und keine Rechnung, und die
Gesamtempfehlung muss die Reihenfolge begründen können.
"""

from __future__ import annotations

from typing import Any

from erkennung.bestand import Kernprozess, Mandant
from erkennung.erkennen import ErkanntesPotenzial

__all__ = ["baue_nutzlast"]

#: Was an Material vom Bewertungsschritt mitkommt: die Sätze, nicht die Werte.
_NUTZWERT = ("qualitaet", "durchlaufzeit", "fehlerreduktion", "mitarbeiterzufriedenheit", "compliance")


def _teilprozess(tp) -> dict[str, Any]:
    eintrag = {"id": tp.teilprozess_id, "name": tp.name}
    for feld, wert in (
        ("ablauf", tp.ablauf),
        ("werkzeuge", tp.werkzeuge),
        ("schnittstellen", tp.schnittstellen),
        ("medienbrueche", tp.medienbrueche),
        ("api", tp.api),
    ):
        if wert and str(wert).strip():
            eintrag[feld] = str(wert).strip()
    return eintrag


def baue_nutzlast(
    mandant: Mandant,
    kernprozess: Kernprozess,
    stuecke: list[tuple[ErkanntesPotenzial, dict]],
    uebrige: list[dict],
) -> dict[str, Any]:
    """Die Nutzlast für **ein** Konzept.

    :param stuecke: je Potenzial des Konzepts, in Rangfolge, das erkannte
        Potenzial und seine gerechnete Hälfte in Vertragsform
        (``modell.ausgabe.als_konzept_potenzial``).
    :param uebrige: die Potenziale der **anderen** Konzepte des Laufs, je
        ``{"id", "titel", "kernprozess_id", "loesungsklasse"}``.
    """
    potenziale = []
    for erkannt, gerechnet in stuecke:
        nutzwert = gerechnet.get("nutzwert") or {}
        potenziale.append(
            {
                "id": erkannt.potenzial_id,
                "titel": erkannt.titel,
                "potenzialrang": gerechnet["potenzialrang"],
                "prioritaetsgruppe": gerechnet["prioritaetsgruppe"],
                "kategorie": gerechnet["kategorie"],
                "loesungsklasse": erkannt.klasse,
                "beruehrte_teilprozesse": list(erkannt.beruehrte_teilprozess_ids),
                "ausgangslage": erkannt.ausgangslage,
                "schmerzpunkte": list(erkannt.schmerzpunkte),
                "loesungsansatz": erkannt.loesungsansatz,
                "trenntest_begruendung": erkannt.trenntest_begruendung,
                "unsicherheit": erkannt.unsicherheit,
                "lage_im_korridor": gerechnet["automatisierungsgrad"]["begruendung"],
                "nutzwert_begruendungen": {
                    k: nutzwert[k]["begruendung"] for k in _NUTZWERT if k in nutzwert
                },
            }
        )

    kopf = {"id": kernprozess.kernprozess_id, "name": kernprozess.name}
    for feld in ("kategorie", "ausloeser", "eingang", "ausgang"):
        wert = getattr(kernprozess, feld)
        if wert and str(wert).strip():
            kopf[feld] = str(wert).strip()
    kopf["teilprozesse"] = [_teilprozess(tp) for tp in kernprozess.teilprozesse]

    return {
        "mandant": {
            k: v
            for k, v in (
                ("name", mandant.name),
                ("branche", mandant.branche),
                ("geschaeftsmodell", mandant.geschaeftsmodell),
            )
            if v and str(v).strip()
        },
        "tech_stack": mandant.tech_stack or "nicht erhoben",
        "kernprozess": kopf,
        "potenziale": potenziale,
        "uebrige_potenziale_des_laufs": uebrige,
    }
