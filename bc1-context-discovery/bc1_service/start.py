"""Startprüfungen des Dienstes. BC1_COMPANY_ID ist ab Etappe 1 PFLICHT (R13-I1):
ohne sie gaebe es Sessions ohne Mandanten-Bindung — und damit einen zweiten
Betriebsmodus neben dem ausnahmslosen Mandanten-Guard.

Der Dienst bietet nur bewertete Teilprozesse an (Rev. 11); die Auswahl geht in den
ctx-Fingerprint ein — ein nach dem Start neu bewerteter Teilprozess ist erst nach
Neustart waehlbar, laufende Sessions bekommen dann 409 `paket_konflikt`.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping

from bc1_service import bc0_lesepfade
from bc1_service.discovery_paket import Bc0Kontext


# Wortlaut von BC0 (Antwort 10, 02.09.) — nicht umformulieren, er ist mit BC0 abgestimmt.
MELDUNG_KEINE_TEILPROZESSE = (
    "Für diesen Mandanten sind noch keine Teilprozesse erfasst. Das Interview kann "
    "erst geführt werden, wenn die Prozessstruktur steht.")
# Zweite Stufe (Rev. 11): Struktur da, aber nichts bewertet — BC0s Satz waere hier falsch.
MELDUNG_KEINE_BEWERTUNG = (
    "Für diesen Mandanten ist noch kein Teilprozess bewertet. Das Interview kann erst "
    "geführt werden, wenn mindestens ein Teilprozess im Self-Rating bewertet ist.")


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


def lade_kontext(conn, company_id: str) -> Bc0Kontext:
    if not bc0_lesepfade.mandant_existiert(conn, company_id):
        raise RuntimeError(
            f"Mandant {company_id} existiert nicht in companies — "
            "BC1_COMPANY_ID pruefen.")
    if not bc0_lesepfade.teilprozesse(conn, company_id):
        raise RuntimeError(MELDUNG_KEINE_TEILPROZESSE)
    bewertete = bc0_lesepfade.bewertete_teilprozesse(conn, company_id)
    if not bewertete:
        raise RuntimeError(MELDUNG_KEINE_BEWERTUNG)
    return Bc0Kontext(
        company_id=company_id,
        teilprozesse=tuple(bewertete),
        system_ids=tuple(bc0_lesepfade.system_ids(conn, company_id)))
