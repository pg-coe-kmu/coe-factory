"""Startprüfungen des Dienstes. BC1_COMPANY_ID ist ab Etappe 1 PFLICHT (R13-I1):
ohne sie gaebe es Sessions ohne Mandanten-Bindung — und damit einen zweiten
Betriebsmodus neben dem ausnahmslosen Mandanten-Guard.

Der Dienst bietet nur bewertete Teilprozesse an (Rev. 11); die Auswahl geht in den
ctx-Fingerprint ein — ein nach dem Start neu bewerteter Teilprozess ist erst nach
Neustart waehlbar, laufende Sessions bekommen dann 409 `paket_konflikt`.

Seit B5 (05.10.2026) ist BC1_ANFRAGE_ID ebenfalls Pflicht: angeboten werden nur die
Teilprozesse dieser Anfrage. Seit B4 prüft der Start zuerst immer den BC0-Zugang und
meldet BC0 dann 'im_interview' — nur aus 'zugeordnet'.
"""
from __future__ import annotations

import re
import uuid
from collections.abc import Mapping

from bc1_service import bc0_lesepfade
from bc1_service.discovery_paket import Bc0Kontext

INTERVIEWBARE_STATUS = ("zugeordnet", "im_interview")   # = anfrage_am_gate_nachziehen()
_ANFRAGE_MUSTER = re.compile(r"A-[0-9]{4}-[0-9]{2}")   # BC0 ck auf ref_anfragen (v1.4)

# Wortlaut von BC0 (Antwort 10, 02.09.) — nicht umformulieren, er ist mit BC0 abgestimmt.
MELDUNG_KEINE_TEILPROZESSE = (
    "Für diesen Mandanten sind noch keine Teilprozesse erfasst. Das Interview kann "
    "erst geführt werden, wenn die Prozessstruktur steht.")
# Zweite Stufe (Rev. 11): Struktur da, aber nichts bewertet — BC0s Satz waere hier falsch.
MELDUNG_KEINE_BEWERTUNG = (
    "Für diesen Mandanten ist noch kein Teilprozess bewertet. Das Interview kann erst "
    "geführt werden, wenn mindestens ein Teilprozess im Self-Rating bewertet ist.")
# B5: Meldungen zur Anfrage (str.format-Vorlagen).
MELDUNG_ANFRAGE_UNBEKANNT = (
    "Die Anfrage {anfrage_id} gibt es bei diesem Mandanten nicht. "
    "BC1_ANFRAGE_ID prüfen.")
MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW = (
    "Die Anfrage {anfrage_id} steht auf '{status}'. Interviewt wird nur eine Anfrage "
    "im Stand 'zugeordnet' oder 'im_interview'.")
MELDUNG_ANFRAGE_OHNE_TEILPROZESSE = (
    "Die Anfrage {anfrage_id} ist keinem Teilprozess zugeordnet. Das Interview kann "
    "erst geführt werden, wenn BC0 die Anfrage zugeordnet hat.")
MELDUNG_TEILPROZESSE_NICHT_BEREIT = (
    "Zur Anfrage {anfrage_id} sind diese Teilprozesse nicht bewertet oder stillgelegt: "
    "{liste}. BC0 übergibt eine Anfrage nur vollständig — das Interview startet "
    "erst, wenn alle bewertet und aktiv sind.")


def lies_company_id(umgebung: Mapping[str, str]) -> str:
    roh = umgebung.get("BC1_COMPANY_ID", "").strip()
    if not roh:
        raise RuntimeError(
            "BC1_COMPANY_ID ist nicht gesetzt — der Dienst startet ohne "
            "Mandanten-Bindung nicht. Beispiel: "
            'export BC1_COMPANY_ID="11111111-1111-1111-1111-111111111111"')
    try:
        return str(uuid.UUID(roh))                 # normalisiert auf lowercase
    except ValueError as fehler:
        raise RuntimeError(
            f"BC1_COMPANY_ID='{roh}' ist keine UUID.") from fehler


def lies_anfrage_id(umgebung: Mapping[str, str]) -> str:
    roh = umgebung.get("BC1_ANFRAGE_ID", "").strip()
    if not roh:
        raise RuntimeError(
            "BC1_ANFRAGE_ID ist nicht gesetzt — BC1 interviewt nur zu einer Anfrage "
            'von BC0. Beispiel: export BC1_ANFRAGE_ID="A-2026-03"')
    if not _ANFRAGE_MUSTER.fullmatch(roh):
        raise RuntimeError(f"BC1_ANFRAGE_ID='{roh}' hat nicht die Form A-JJJJ-NN.")
    return roh


def lade_kontext(conn, company_id: str, anfrage_id: str) -> Bc0Kontext:
    if not bc0_lesepfade.mandant_existiert(conn, company_id):
        raise RuntimeError(
            f"Mandant {company_id} existiert nicht in companies — "
            "BC1_COMPANY_ID pruefen.")
    if not bc0_lesepfade.teilprozesse(conn, company_id):
        raise RuntimeError(MELDUNG_KEINE_TEILPROZESSE)
    bewertete = dict(bc0_lesepfade.bewertete_teilprozesse(conn, company_id))
    if not bewertete:
        raise RuntimeError(MELDUNG_KEINE_BEWERTUNG)
    status = bc0_lesepfade.anfrage_status(conn, company_id, anfrage_id)
    if status is None:
        raise RuntimeError(MELDUNG_ANFRAGE_UNBEKANNT.format(anfrage_id=anfrage_id))
    if status not in INTERVIEWBARE_STATUS:
        raise RuntimeError(MELDUNG_ANFRAGE_NICHT_IM_INTERVIEW.format(
            anfrage_id=anfrage_id, status=status))
    soll = bc0_lesepfade.anfrage_teilprozesse(conn, company_id, anfrage_id)
    if not soll:
        raise RuntimeError(MELDUNG_ANFRAGE_OHNE_TEILPROZESSE.format(anfrage_id=anfrage_id))
    # Regel 7 (BC0): uebergeben wird eine Anfrage nur vollstaendig. Ein TP ohne
    # Bewertung oder stillgelegt blockiert sie dauerhaft — das sagt der Start, nicht
    # das dritte Interview.
    fehlend = [tp for tp in soll if tp not in bewertete]
    if fehlend:
        raise RuntimeError(MELDUNG_TEILPROZESSE_NICHT_BEREIT.format(
            anfrage_id=anfrage_id, liste=", ".join(fehlend)))
    return Bc0Kontext(
        company_id=company_id,
        teilprozesse=tuple((tp, bewertete[tp]) for tp in soll),
        system_ids=tuple(bc0_lesepfade.system_ids(conn, company_id)),
        anfrage_id=anfrage_id)


def melde_interview_beginn(melder, anfrage_id: str, status: str | None) -> None:
    """B4: Zuerst immer den Zugang pruefen (Ergaenzung 08.10.: sonst fiele ein falscher
    Zugang bei 'im_interview' erst nach dem Interview auf), dann BC0 melden, dass interviewt
    wird — nur aus 'zugeordnet'; bei 'im_interview' nicht erneut, sonst ueberschriebe jeder
    Neustart BC0s status_seit. melder None = Meldungen bewusst aus (BC1_BC0_MELDUNGEN=aus).
    Ein Bc0MeldungFehler bricht den Start ab.

    melder: bc0_meldungen.Bc0Melder oder Ersatz mit pruefe_konto() und
    melde_interview_laeuft(anfrage_id) — bewusst ohne Import (start.py bleibt frei von der
    HTTP-Seite)."""
    if melder is None:
        return
    melder.pruefe_konto()
    if status == "zugeordnet":
        melder.melde_interview_laeuft(anfrage_id)
