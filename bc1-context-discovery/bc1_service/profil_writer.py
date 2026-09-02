"""Profil-Writer: baut aus dem SessionState die Profilzeile und gleicht sie mit
der Datenbank ab (Reconcile-Modell, Spec K3).

Dieser Teil ist DB-frei und rein: Bau der typisierten Spalten und des JSON.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from bc1_core.confidence import confidence_check
from bc1_core.core import profil_payload
from bc1_core.package import UseCasePackage
from bc1_core.types import FieldStatus, SessionState

log = logging.getLogger(__name__)

KP_MUSTER = re.compile(r"^KP-[0-9]{2}$")

# Spalte -> Feldname. Nur gueltige Werte werden konvertiert.
_ZAHLENSPALTEN = {
    "frequency_per_year": "frequency_per_year",
    "executions_per_run": "executions_per_run",
    "total_duration_minutes": "total_duration_minutes",
    "focus_step_duration_minutes": "focus_step_duration_minutes",
}
_TEXTSPALTEN = {"focus_step_duration_source": "focus_step_duration_source"}
_GANZZAHLSPALTEN = {
    "focus_step_duration_confidence_pct": "focus_step_duration_confidence_pct"}


class ProfilWriteError(RuntimeError):
    """Profil konnte nicht geschrieben werden. Im Terminal-Turn => HTTP 503."""


@dataclass(frozen=True)
class Profilinhalt:
    focus_step_id: str
    process_id: str
    spalten: dict[str, object]
    profil: dict


def _gueltiger_wert(state: SessionState, feld: str) -> str | None:
    fv = state.values.get(feld)
    if fv is None or fv.status is not FieldStatus.GUELTIG:
        return None                       # jeder andere Status => SQL NULL (I6)
    return fv.value


def _dezimal(wert: str, feld: str) -> Decimal:
    try:
        return Decimal(wert)              # nie float — Rundung waere stillschweigend
    except InvalidOperation as fehler:
        raise ProfilWriteError(
            f"Feld {feld}: gueltiger Wert '{wert}' laesst sich nicht als numeric "
            "konvertieren — Validator und Spaltentyp widersprechen sich.") from fehler


def _ganzzahl(wert: str, feld: str) -> int:
    try:
        zahl = Decimal(wert)
        if zahl != zahl.to_integral_value():
            raise InvalidOperation(wert)
        return int(zahl)
    except InvalidOperation as fehler:
        raise ProfilWriteError(
            f"Feld {feld}: gueltiger Wert '{wert}' ist keine ganze Zahl.") from fehler


def _fremde_kp(state: SessionState, feld: str, process_id: str,
               kp_bekannt: Callable[[str], bool]) -> str | None:
    wert = _gueltiger_wert(state, feld)
    # fullmatch, nicht match: '$' liesse ein abschliessendes \n durch, der
    # Postgres-CHECK nicht (Review 02.09. an beiden Seiten gemessen).
    if wert is None or not KP_MUSTER.fullmatch(wert):
        return None                       # Freitext bleibt im JSON (Brief)
    if wert == process_id:                # DDL-CHECK: kein Selbstbezug
        return None
    return wert if kp_bekannt(wert) else None


def baue_profilinhalt(state: SessionState, package: UseCasePackage, *,
                      kp_bekannt: Callable[[str], bool]) -> Profilinhalt | None:
    focus_step_id = _gueltiger_wert(state, "focus_step")
    if focus_step_id is None:
        return None                       # keine Identitaet => kein Profil (Brief)

    # Identitaet allein aus der TP-ID (R4-C1): der DDL-CHECK
    # 'focus_step_id LIKE process_id||".%"' ist damit per Konstruktion erfuellt.
    process_id = focus_step_id.split(".", 1)[0]

    conf = confidence_check(state, package)
    profil = profil_payload(state, conf, package)
    pflicht = package.required_fields()
    profil["pflicht_erfasst"] = sum(
        1 for s in pflicht if conf.statuses[s.name] is FieldStatus.GUELTIG)
    profil["pflicht_gesamt"] = len(pflicht)
    profil["befunde"] = {}

    # Nur eine kanonische KP-ID kann der abgeleiteten widersprechen. Ohne BC0-Snapshot
    # ist das Feld FREITEXT (main.py: BC1_SNAPSHOT_PFAD ist optional) — dann waere jede
    # normale Antwort ein Befund und das Log schriebe bei jeder Sitzung rohen
    # Nutzertext mit. Abweichung vom Plan (Rev. 11), begruendet im Review 02.09.
    interview_kp = _gueltiger_wert(state, "process_id")
    if (interview_kp is not None and KP_MUSTER.fullmatch(interview_kp)
            and interview_kp != process_id):
        # Stabiler Befund-Vertrag fuers Gate (R4-C1) — plus strukturiertes Log.
        profil["befunde"]["kp_tp_diskrepanz"] = {
            "interview_kp": interview_kp, "abgeleiteter_kp": process_id}
        log.warning("kp_tp_diskrepanz session=%s interview_kp=%s abgeleitet=%s",
                    state.session_id, interview_kp, process_id)

    spalten: dict[str, object] = {"process_owner_rolle_id": None}   # Etappe 1
    for spalte, feld, konverter, ziel in (
            [(s, f, _dezimal, "numeric") for s, f in _ZAHLENSPALTEN.items()]
            + [(s, f, _ganzzahl, "integer") for s, f in _GANZZAHLSPALTEN.items()]):
        wert = _gueltiger_wert(state, feld)
        if wert is None:
            spalten[spalte] = None
            continue
        try:
            spalten[spalte] = konverter(wert, feld)
        except ProfilWriteError:
            # Der Fehler wird spaeter als generischer 503 ausgeliefert — ohne diesen
            # Eintrag waere nicht feststellbar, welche Sitzung an welchem Feld haengt.
            # Der Rohwert bleibt bewusst draussen: er ist Nutzertext.
            log.error("profil_konvertierung_widerspruch session=%s feld=%s ziel=%s",
                      state.session_id, feld, ziel)
            raise
    for spalte, feld in _TEXTSPALTEN.items():
        spalten[spalte] = _gueltiger_wert(state, feld)
    spalten["upstream_process_id"] = _fremde_kp(
        state, "upstream_process", process_id, kp_bekannt)
    spalten["downstream_process_id"] = _fremde_kp(
        state, "downstream_process", process_id, kp_bekannt)

    return Profilinhalt(focus_step_id, process_id, spalten, profil)
