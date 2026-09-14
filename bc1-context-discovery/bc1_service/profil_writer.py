"""Profil-Writer: baut aus dem SessionState die Profilzeile und gleicht sie mit
der Datenbank ab (Reconcile-Modell, Spec K3).

Zwei Haelften: `baue_profilinhalt` und `wende_sweep_an` sind DB-frei und rein
(Bau der typisierten Spalten und des JSON); `ProfilWriter` darunter fuehrt den
Abgleich in einer eigenen Transaktion aus.
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from bc1_core.confidence import confidence_check
from bc1_core.core import profil_payload
from bc1_core.package import UseCasePackage
from bc1_core.types import FieldStatus, SessionState
from bc1_core.extractor import status_fuer
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from bc1_service import bc0_lesepfade
from bc1_service.paket_feldtypen import entferne_snn, snn_tokens

log = logging.getLogger(__name__)

KP_MUSTER = re.compile(r"^KP-[0-9]{2}$")

# Neue stabile Grund-Konstante neben GRUND_NACHFRAGE_LIMIT / GRUND_RUNDEN_LIMIT.
GRUND_SNN_ENTFALLEN = "systemreferenz_beim_schreiben_entfallen"

KONFLIKT_LOG_ABSTAND_S = 60.0      # Rate-Limit fuer den stabilen Konflikt-Log

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


def _fehlergrund(fehler: Exception) -> str:
    """Fehlerkennung fuers Log — ohne Nutzdaten.

    Postgres haengt an einen Constraint-Fehler eine DETAIL-Zeile mit einem
    Ausschnitt der betroffenen Zeile. Bei uns steht dort das Profil-JSON und
    damit Nutzertext. Deshalb nur Klasse und erste Meldungszeile: die benennt
    Tabelle und Constraint und reicht zur Diagnose (R11-I1, wie beim S-NN-Log).
    """
    return f"{type(fehler).__name__}: {str(fehler).split(chr(10), 1)[0]}"


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


def _fremde_kp(profil: dict, feld: str, process_id: str,
               kp_bekannt: Callable[[str], bool]) -> str | None:
    wert = _payload_wert(profil, feld)
    # fullmatch, nicht match: '$' liesse ein abschliessendes \n durch, der
    # Postgres-CHECK nicht (Review 02.09. an beiden Seiten gemessen).
    if wert is None or not KP_MUSTER.fullmatch(wert):
        return None                       # Freitext bleibt im JSON (Brief)
    if wert == process_id:                # DDL-CHECK: kein Selbstbezug
        return None
    return wert if kp_bekannt(wert) else None


def _payload_wert(profil: dict, feld: str) -> str | None:
    """Wie _gueltiger_wert, aber auf dem BEREINIGTEN Payload (Reihenfolge-Invariante).

    Fehlt das Feld im Paket, gibt es auch keinen Payload-Eintrag — dann NULL, wie
    bisher bei einem nicht gueltigen Status. Fuer BC2 aendert das nichts: was nicht
    im Paket steht, wird ohnehin nicht exportiert.
    """
    eintrag = profil["felder"].get(feld)
    if eintrag is None or eintrag["status"] != FieldStatus.GUELTIG.value:
        return None
    return eintrag["wert"]


def baue_profilinhalt(state: SessionState, package: UseCasePackage, *,
                      kp_bekannt: Callable[[str], bool],
                      bekannte_systeme: frozenset[str]) -> Profilinhalt | None:
    """Payload bauen, bereinigen, DANN ableiten — in dieser Reihenfolge.

    Invariante (Entscheidung Richard 02.09., Option a): **Spalten werden nie aus
    ungesweepten Werten abgeleitet.** Lief der Sweep erst hinterher auf dem JSON,
    entstanden zwei Wahrheiten — `upstream_process = "KP-02 (S-99)"` ist als
    Freitext gueltig, die Spalte blieb mangels fullmatch NULL, und der Sweep machte
    im JSON `KP-02` daraus. `bekannte_systeme` ist deshalb ein Pflichtparameter:
    ein Aufrufer soll die Reihenfolge gar nicht erst drehen koennen.
    """
    if _gueltiger_wert(state, "focus_step") is None:
        return None                       # keine Identitaet => kein Profil (Brief)

    conf = confidence_check(state, package)
    profil = profil_payload(state, conf, package)
    pflicht = package.required_fields()
    profil["pflicht_erfasst"] = sum(
        1 for s in pflicht if conf.statuses[s.name] is FieldStatus.GUELTIG)
    profil["pflicht_gesamt"] = len(pflicht)
    profil["befunde"] = {}

    # BC0-Auflage 1.4 ("beim Schreiben pruefen") — und ab hier gilt: alles, was
    # abgeleitet wird, kommt aus dem bereinigten Payload.
    wende_sweep_an(profil, package, bekannte_systeme=bekannte_systeme,
                   session_id=state.session_id)

    focus_step_id = _payload_wert(profil, "focus_step")
    if focus_step_id is None:
        # Der Sweep hat die Identitaet selbst getroffen. Mit BC0s TP-IDs
        # unerreichbar (kein S-NN darin), aber genau der Guard, den der
        # Docstring von wende_sweep_an fordert — ohne ihn liefe die Ableitung
        # unten in einen AttributeError statt in den Completion-Guard.
        return None
    # Identitaet allein aus der TP-ID (R4-C1): der DDL-CHECK
    # 'focus_step_id LIKE process_id||".%"' ist damit per Konstruktion erfuellt.
    process_id = focus_step_id.split(".", 1)[0]

    # Nur eine kanonische KP-ID kann der abgeleiteten widersprechen. Ohne BC0-Snapshot
    # ist das Feld FREITEXT (main.py: BC1_SNAPSHOT_PFAD ist optional) — dann waere jede
    # normale Antwort ein Befund und das Log schriebe bei jeder Sitzung rohen
    # Nutzertext mit. Abweichung vom Plan (Rev. 11), begruendet im Review 02.09.
    interview_kp = _payload_wert(profil, "process_id")
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
        wert = _payload_wert(profil, feld)
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
        spalten[spalte] = _payload_wert(profil, feld)
    spalten["upstream_process_id"] = _fremde_kp(
        profil, "upstream_process", process_id, kp_bekannt)
    spalten["downstream_process_id"] = _fremde_kp(
        profil, "downstream_process", process_id, kp_bekannt)

    return Profilinhalt(focus_step_id, process_id, spalten, profil)


def _unbekannte(text: str | None, bekannte: frozenset[str]) -> list[str]:
    return [t for t in snn_tokens(text or "") if t not in bekannte]


def _zaehler_neu(profil: dict, package: UseCasePackage) -> None:
    """vollstaendigkeit, pflicht_erfasst und ungeloeste_felder in Paketreihenfolge neu.

    Ohne das haette der Payload eine zu hohe Vollstaendigkeit — der Sweep kann
    ein Pflichtfeld gerade offen gemacht haben.
    """
    pflicht = package.required_fields()
    erfasst = sum(1 for s in pflicht
                  if profil["felder"][s.name]["status"] == FieldStatus.GUELTIG.value)
    profil["pflicht_erfasst"] = erfasst
    profil["pflicht_gesamt"] = len(pflicht)
    profil["vollstaendigkeit"] = erfasst / len(pflicht) if pflicht else 1.0
    profil["ungeloeste_felder"] = [
        s.name for s in package.fields
        if profil["felder"][s.name]["status"] == FieldStatus.UNGELOEST.value]


def wende_sweep_an(profil: dict, package: UseCasePackage, *,
                   bekannte_systeme: frozenset[str], session_id: str) -> dict:
    """Entfernt vor dem Schreiben JEDE nicht zum Mandanten gehoerende S-NN-Kennung.

    Erfuellt BC0-Auflage 1.4 woertlich ("beim Schreiben pruefen"). Der Validator
    schuetzt nur gueltige Werte — der Kern exportiert aber Wert UND Kandidaten
    unabhaengig vom Feldstatus (R5-I3).

    Umfang und Vertrag (im Review 02.09. einzeln nachgemessen, hier festgeschrieben,
    damit nichts davon stillschweigend gilt):
    * Geprueft werden `wert` und `kandidaten[].wert` — also die fachlichen Inhalte.
      `quelle` und `grund` bleiben unangetastet: sie tragen per Vertrag keine
      Nutzereingabe (`grund` sind Konstanten, `quelle` ist die message_id des
      Clients). Sie zu bereinigen wuerde Herkunftsangaben verfaelschen, und ein
      Abbruch waere schaerfer als noetig — die Kennungs-Regex trifft wegen der
      Wortgrenze auch mitten in technischen IDs.
    * `anzahl` im Befund zaehlt VORKOMMEN, nicht verschiedene Kennungen; das Log
      fuehrt die Kennungen entdoppelt. Beide Zahlen koennen daher abweichen.
    * Bei `GRUND_SNN_ENTFALLEN` entfaellt der Wert, `quelle` bleibt aber auf der
      urspruenglichen Nennung stehen — anders als bei `ungeloest` aus dem Dialog,
      das den Wert behaelt.
    * Erwartet einen Payload aus `baue_profilinhalt` (das `befunde` bereits anlegt).
    * `identitaetskritisch` kennt der Sweep nicht. Heute unerreichbar, weil die
      TP-IDs aus BC0 dem Muster `KP-NN.TP-N` folgen und daher nie eine S-NN-Kennung
      enthalten koennen; faellt diese Annahme, braucht es hier einen Guard.
    """
    befunde: list[dict] = []
    for spec in package.fields:                       # Paket-Feldreihenfolge
        # Direkter Zugriff, kein .get(): der Payload stammt aus profil_payload, das
        # ueber dieselben package.fields iteriert — ein fehlendes Feld waere ein
        # Widerspruch, der laut scheitern soll. Ein .get() hier waere falsch
        # beruhigend, weil _zaehler_neu zwei Zeilen spaeter ohnehin direkt zugreift
        # (Review 02.09.: dort gemessen als KeyError).
        feld = profil["felder"][spec.name]
        war_gueltig = feld["status"] == FieldStatus.GUELTIG.value
        entfernt: list[str] = []
        # Schleife, kein Einmalscan: entferne_snn raeumt leere Klammern weg, dabei
        # koennen Nachbarn zu einer NEUEN Kennung zusammenruecken ('S-[S-98]42' ->
        # 'S-42'). Terminiert, weil jede Runde mindestens ein Token loescht und der
        # Text damit echt kuerzer wird (Review 02.09., gemessen).
        while True:
            runde = _unbekannte(feld["wert"], bekannte_systeme)
            for kandidat in feld["kandidaten"]:
                runde += _unbekannte(kandidat["wert"], bekannte_systeme)
            if not runde:
                break
            entfernt += runde
            if feld["wert"] is not None:
                feld["wert"] = entferne_snn(feld["wert"], runde)
            feld["kandidaten"] = [
                {**k, "wert": entferne_snn(k["wert"], runde)}
                for k in feld["kandidaten"]
                if entferne_snn(k["wert"], runde)]      # leer => entfaellt
        if not entfernt:
            continue

        # Rohe IDs NUR ins Log (R11-I1), nie zurueck ins Profil.
        log.warning("snn_entfernt session=%s feld=%s ids=%s",
                    session_id, spec.name, sorted(set(entfernt)))

        if not war_gueltig:
            continue                                    # still bereinigt, kein Befund

        # Status neu bestimmen — der Extractor wuesste nichts von der Entfernung.
        neuer_status = (status_fuer(spec, feld["wert"]) if feld["wert"]
                        else FieldStatus.UNGUELTIG)
        if neuer_status is FieldStatus.GUELTIG:
            danach = FieldStatus.GUELTIG.value
        else:
            feld["status"] = FieldStatus.UNGELOEST.value
            feld["grund"] = GRUND_SNN_ENTFALLEN
            feld["wert"] = None
            danach = FieldStatus.UNGELOEST.value
        befunde.append({"feld": spec.name, "anzahl": len(entfernt),
                        "feld_status_danach": danach})

    if befunde:
        profil["befunde"]["snn_entfernt"] = befunde
    _zaehler_neu(profil, package)
    return profil


@dataclass(frozen=True)
class Bindung:
    focus_step_id: str
    profil_version: int
    status: str


class ProfilWriter:
    """Gleicht am Ende jedes zugelassenen Turns Soll und Ist ab (Spec K3)."""

    def __init__(self, pool, company_id: str, package: UseCasePackage) -> None:
        self._pool = pool
        self._company_id = company_id
        self._package = package
        # Ohne identitaetskritisches Feld gibt es keine Prozess-Identitaet und
        # damit kein Profil (z. B. Toy-Paket) — der Writer haelt sich raus.
        self._schreibt = any(s.identitaetskritisch
                             for s in package.required_fields())
        self._konflikt_zuletzt: dict[str, float] = {}

    def reconcile(self, state: SessionState, antwort: dict) -> dict | None:
        if not self._schreibt:
            return None
        if antwort["status"] == "fehler_fortsetzbar":
            return None                # kein zustandegekommener Turn, nichts abzugleichen
        try:
            return self._abgleich(state, antwort)
        except ProfilWriteError:
            raise
        except Exception as fehler:                        # noqa: BLE001
            if antwort["status"] == "fertig":
                raise ProfilWriteError(
                    f"Profil-Write im Terminal-Turn fehlgeschlagen: {fehler}"
                ) from fehler
            # Nicht-terminale Turns blockieren nicht — der naechste reconcilet.
            log.warning("profil_write_uebersprungen session=%s grund=%s",
                        state.session_id, _fehlergrund(fehler))
            return None

    # ---- innerhalb EINER Transaktion ------------------------------------
    def _abgleich(self, state: SessionState, antwort: dict) -> dict | None:
        with self._pool.connection() as conn:          # eine Transaktion
            bindung = self._bindung(conn, state.session_id)
            # Der Abbruch braucht den Profilinhalt nicht — und er wird VOR dem Bau
            # behandelt: sonst reisst jeder Fehler beim Bau das Aufraeumen mit, und
            # ein ProfilWriteError von dort wuerde den Abbruch zum 503 machen. Fuer
            # abgebrochen_ohne_identitaet gilt die Postcondition ausdruecklich nicht.
            if antwort["status"] == "abgebrochen_ohne_identitaet":
                if bindung is not None:
                    self._draft_aufraeumen(conn, bindung, state.session_id)
                return None
            inhalt = baue_profilinhalt(
                state, self._package,
                kp_bekannt=lambda kp: bc0_lesepfade.kp_existiert(
                    conn, self._company_id, kp),
                bekannte_systeme=frozenset(
                    bc0_lesepfade.system_ids(conn, self._company_id)))
            if inhalt is None:
                # Keine gueltige Identitaet in diesem Turn. Der Draft bleibt
                # stehen: eine Klaerung kann den alten Wert bestaetigen (R6-C1).
                if antwort["status"] == "fertig":
                    raise ProfilWriteError(
                        "fertig ohne gueltige Fokus-Schritt-ID "
                        "(Completion-Guard verletzt)")
                return None
            if bindung is not None and bindung.focus_step_id != inhalt.focus_step_id:
                bindung = self._umbinden(conn, state, inhalt, bindung)
                if bindung is None:
                    if antwort["status"] == "fertig":
                        raise ProfilWriteError(
                            "Rebind-Ziel ist von einem fremden Draft belegt")
                    return None                     # alter Draft steht noch
            elif bindung is None:
                bindung = self._draft_anlegen(conn, state, inhalt)
                if bindung is None:                     # fremder Draft
                    if antwort["status"] == "fertig":
                        raise ProfilWriteError(
                            "fremder in_erhebung-Draft belegt den Fokus-Schritt")
                    return None
            if antwort["status"] != "fertig":
                return None
            if bindung.status == "fertig":
                # Freeze war committet, die Antwort ging verloren (R4-C2).
                return self._gespeichertes_profil(conn, bindung)
            return self._einfrieren(conn, bindung, inhalt)

    def _gespeichertes_profil(self, conn, bindung) -> dict:
        return conn.execute(
            "SELECT profil FROM bc1.prozessprofil WHERE company_id = %s "
            "AND focus_step_id = %s AND profil_version = %s",
            (self._company_id, bindung.focus_step_id,
             bindung.profil_version)).fetchone()[0]

    def _bindung(self, conn, session_id: str) -> Bindung | None:
        zeile = conn.execute(
            "SELECT w.focus_step_id, w.profil_version, p.status "
            "  FROM bc1.profil_write_status w "
            "  JOIN bc1.prozessprofil p ON p.company_id = w.company_id "
            "   AND p.focus_step_id = w.focus_step_id "
            "   AND p.profil_version = w.profil_version "
            " WHERE w.session_id = %s AND w.company_id = %s",
            (session_id, self._company_id)).fetchone()
        return Bindung(*zeile) if zeile else None

    def _draft_aufraeumen(self, conn, bindung, session_id: str) -> None:
        try:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM bc1.prozessprofil WHERE company_id = %s "
                    "AND focus_step_id = %s AND profil_version = %s",
                    (self._company_id, bindung.focus_step_id,
                     bindung.profil_version))
        except Exception as fehler:                         # noqa: BLE001
            # Ehrlich (Spec K0): die Antwort geht trotzdem raus — die Session ist
            # fachlich zu Ende. Zurueck bleibt ein verwaister Draft; er ist fuer
            # BC0 nicht gate-relevant, belegt aber den UNIQUE-Slot (Betriebsweg K5).
            log.error("draft_aufraeumen_fehlgeschlagen session=%s schritt=%s grund=%r",
                      session_id, bindung.focus_step_id, fehler)

    def _draft_anlegen(self, conn, state, inhalt) -> Bindung | None:
        try:
            # Savepoint: ein Unique-Konflikt darf die umgebende Transaktion
            # nicht abschiessen (der Turn laeuft ja weiter).
            with conn.transaction():
                return self._einfuegen(conn, state, inhalt)
        except UniqueViolation:
            self._konflikt_melden(state.session_id, inhalt.focus_step_id)
            return None

    def _konflikt_melden(self, session_id: str, focus_step_id: str) -> None:
        # Stabiler Konflikt, rate-limitiert: er besteht in JEDEM Folgeturn weiter,
        # ohne Begrenzung schriebe jeder Turn dieselbe Zeile (Spec K3.2).
        jetzt = time.monotonic()
        schluessel = f"{session_id}|{focus_step_id}"
        # None statt 0.0 als Default: time.monotonic() startet je nach System nahe
        # null, ein Vergleich gegen 0.0 haette den ERSTEN Konflikt kurz nach dem
        # Systemstart als "schon gemeldet" verschluckt.
        zuletzt = self._konflikt_zuletzt.get(schluessel)
        if zuletzt is not None and jetzt - zuletzt < KONFLIKT_LOG_ABSTAND_S:
            return
        self._konflikt_zuletzt[schluessel] = jetzt
        log.warning("fremder_draft_konflikt session=%s schritt=%s mandant=%s",
                    session_id, focus_step_id, self._company_id)

    def _umbinden(self, conn, state, inhalt, alt: Bindung) -> Bindung | None:
        """Alten Draft loeschen und neu binden — ganz oder gar nicht.

        Loeschen und Neuanlage liegen in EINEM Savepoint: sonst waere bei einem
        Zielkonflikt der alte Draft schon geloescht und der Verlust wuerde
        mitcommittet (Codex R1-C5).
        """
        try:
            with conn.transaction():             # ein gemeinsamer Savepoint
                conn.execute(
                    "DELETE FROM bc1.prozessprofil WHERE company_id = %s "
                    "AND focus_step_id = %s AND profil_version = %s",
                    (self._company_id, alt.focus_step_id, alt.profil_version))
                return self._einfuegen(conn, state, inhalt)
        except UniqueViolation:
            # Rollback bis zum Savepoint: alter Draft UND Bindung stehen noch.
            self._konflikt_melden(state.session_id, inhalt.focus_step_id)
            return None

    def _einfuegen(self, conn, state, inhalt) -> Bindung:
        """Profilzeile + Bindung im selben Commit (C2)."""
        erhebung = bc0_lesepfade.erhebung_id(
            conn, self._company_id, inhalt.focus_step_id)
        spalten = inhalt.spalten
        namen = ["company_id", "focus_step_id", "profil_version", "process_id",
                 "status", "erhebung_id", "paket_version", "profil", *spalten]
        werte = [self._company_id, inhalt.focus_step_id, 1, inhalt.process_id,
                 "in_erhebung", erhebung, state.schema_version,
                 Jsonb(inhalt.profil), *spalten.values()]
        platzhalter = ", ".join(["%s"] * len(namen))
        version = conn.execute(
            f"INSERT INTO bc1.prozessprofil ({', '.join(namen)}) "
            f"VALUES ({platzhalter}) RETURNING profil_version",
            werte).fetchone()[0]
        conn.execute(
            "INSERT INTO bc1.profil_write_status "
            "(session_id, company_id, focus_step_id, profil_version) "
            "VALUES (%s, %s, %s, %s)",
            (state.session_id, self._company_id, inhalt.focus_step_id, version))
        return Bindung(inhalt.focus_step_id, version, "in_erhebung")

    def _einfrieren(self, conn, bindung, inhalt) -> dict:
        # Spaltennamen stammen aus unserer eigenen Konstante, nicht aus Eingaben.
        zuweisungen = ", ".join(f"{spalte} = %s" for spalte in inhalt.spalten)
        cursor = conn.execute(
            f"UPDATE bc1.prozessprofil SET status = 'fertig', profil = %s, "
            f"{zuweisungen} WHERE company_id = %s AND focus_step_id = %s "
            "AND profil_version = %s AND status = 'in_erhebung'",
            [Jsonb(inhalt.profil), *inhalt.spalten.values(), self._company_id,
             bindung.focus_step_id, bindung.profil_version])
        if cursor.rowcount != 1:
            raise ProfilWriteError(
                f"Freeze traf {cursor.rowcount} Zeilen statt einer")
        return inhalt.profil
