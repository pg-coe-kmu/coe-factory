from __future__ import annotations
from dataclasses import dataclass
from bc1_core.types import Ergebnis, FieldStatus, FieldValue, SessionState
from bc1_core.package import UseCasePackage
from bc1_core.confidence import ConfidenceResult

MAX_ATTEMPTS_PER_FIELD = 2
MAX_ROUNDS = 20

# Wire-Werte für FieldValue.grund (Spec B4) — Vertrag Richtung BC2.
GRUND_NACHFRAGE_LIMIT = "nachfrage_limit_erreicht"
GRUND_RUNDEN_LIMIT = "runden_limit_erreicht"
# Grund im Abbruch-Payload (Spec K0, Wire-Vertrag).
GRUND_IDENTITAET_UNGEKLAERT = "identitaet_ungeklaert"


@dataclass
class Decision:
    ergebnis: Ergebnis
    next_field: str | None = None


def _offene_identitaet(state: SessionState, package: UseCasePackage) -> str | None:
    """Erstes identitaetskritisches Pflichtfeld ohne gueltigen Wert."""
    for spec in package.required_fields():
        if not spec.identitaetskritisch:
            continue
        fv = state.values.get(spec.name)
        if fv is None or fv.status is not FieldStatus.GUELTIG:
            return spec.name
    return None


def decide_next(state: SessionState, package: UseCasePackage,
                conf: ConfidenceResult) -> Decision:
    identitaetsfelder = {s.name for s in package.required_fields()
                         if s.identitaetskritisch}
    offene_identitaet = _offene_identitaet(state, package)

    # Cap-Politik: ueber dem Limit -> als ungeloest markieren. Identitaets-
    # kritische Felder sind ausgenommen (Spec K0) — sie werden nie aufgegeben.
    for name in conf.offene_pflichtfelder:
        if name in identitaetsfelder:
            continue
        fv = state.values.get(name)
        if fv is not None and fv.attempts >= MAX_ATTEMPTS_PER_FIELD:
            fv.status = FieldStatus.UNGELOEST
            fv.grund = GRUND_NACHFRAGE_LIMIT

    offen = [n for n in conf.offene_pflichtfelder
             if state.values.get(n) is None
             or state.values[n].status is not FieldStatus.UNGELOEST]

    # Fail-safe: ein identitaetskritisches Feld darf nie aus der Frageliste
    # fallen — auch nicht in Alt-Sessions, in denen es schon ungeloest wurde.
    if offene_identitaet is not None and offene_identitaet not in offen:
        offen.insert(0, offene_identitaet)

    if state.rounds >= package.max_rounds:
        if offene_identitaet is not None:
            # Definiertes Ende statt Endlosschleife (Spec K0): kein Profil,
            # kein 503, klare Ansage. Die uebrigen Felder werden NICHT mehr
            # aufgegeben — es entsteht ohnehin kein Profil.
            return Decision(Ergebnis.ABGEBROCHEN_OHNE_IDENTITAET,
                            next_field=offene_identitaet)
        for name in offen:
            fv = state.values.get(name)
            if fv is None:
                fv = FieldValue()
                state.values[name] = fv
            fv.status = FieldStatus.UNGELOEST
            fv.grund = GRUND_RUNDEN_LIMIT
        return Decision(Ergebnis.FERTIG)

    if not offen:
        return Decision(Ergebnis.FERTIG)

    target = offen[0]
    fv = state.values.get(target)
    if fv is None:
        fv = FieldValue()
        state.values[target] = fv
    fv.attempts += 1
    return Decision(Ergebnis.WEITER, next_field=target)
