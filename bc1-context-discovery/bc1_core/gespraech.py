"""Gesprächskontext für die Versprachlichung eines Turns (Spec Gesprächsschicht).

Der Kern befüllt, das LLM gibt nur wieder: alle Inhalte stammen aus dem
echten State. Felder werden gegenüber dem LLM ausschließlich über ihre
Kernfrage identifiziert — technische Feldnamen verlassen den Kern nicht
(Leak-Schutz per Konstruktion).
"""
from __future__ import annotations

from dataclasses import dataclass

from bc1_core.confidence import ConfidenceResult
from bc1_core.package import UseCasePackage
from bc1_core.types import FieldStatus, SessionState


@dataclass(frozen=True)
class Erfassung:
    frage: str   # Kernfrage des Feldes — NICHT der technische Name
    wert: str    # normalisierter Wert aus dem State


@dataclass(frozen=True)
class TurnKontext:
    nutzer_nachricht: str
    neu_erfasst: tuple[Erfassung, ...]
    naechste_frage: str | None          # wörtliche Kernfrage; None beim Abschluss
    ist_nachfrage: bool
    ist_abschluss: bool
    profil_uebersicht: tuple[Erfassung, ...] = ()
    offene_fragen: tuple[str, ...] = ()


def werte_schnappschuss(state: SessionState) -> dict[str, str]:
    """GUELTIGE Werte VOR der Extraktion — Basis der Delta-Berechnung."""
    return {name: fv.value for name, fv in state.values.items()
            if fv.status is FieldStatus.GUELTIG}


def _gueltige(state: SessionState, package: UseCasePackage):
    for spec in package.fields:
        fv = state.values.get(spec.name)
        if fv is not None and fv.status is FieldStatus.GUELTIG:
            yield spec, fv


def baue_turn_kontext(nachricht: str, vorher: dict[str, str],
                      state: SessionState, package: UseCasePackage,
                      conf: ConfidenceResult, ziel_feld: str | None,
                      ist_abschluss: bool) -> TurnKontext:
    """Kontext aus echtem State — in Paket-Reihenfolge, deterministisch."""
    neu = tuple(Erfassung(spec.question, fv.value)
                for spec, fv in _gueltige(state, package)
                if vorher.get(spec.name) != fv.value)

    if ist_abschluss:
        uebersicht = tuple(Erfassung(spec.question, fv.value)
                           for spec, fv in _gueltige(state, package))
        offene = tuple(spec.question for spec in package.required_fields()
                       if conf.statuses[spec.name] is not FieldStatus.GUELTIG)
        return TurnKontext(nachricht, neu, None, ist_nachfrage=False,
                           ist_abschluss=True, profil_uebersicht=uebersicht,
                           offene_fragen=offene)

    ziel = state.values.get(ziel_feld)
    return TurnKontext(nachricht, neu, package.field(ziel_feld).question,
                       ist_nachfrage=ziel is not None and ziel.attempts > 1,
                       ist_abschluss=False)
