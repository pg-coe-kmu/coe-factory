"""Startprüfungen des Dienstes. BC1_COMPANY_ID ist ab Etappe 1 PFLICHT (R13-I1):
ohne sie gaebe es Sessions ohne Mandanten-Bindung — und damit einen zweiten
Betriebsmodus neben dem ausnahmslosen Mandanten-Guard.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping

from bc1_service import bc0_lesepfade
from bc1_service.discovery_paket import Bc0Kontext


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
    return Bc0Kontext(
        company_id=company_id,
        teilprozesse=tuple(bc0_lesepfade.teilprozesse(conn, company_id)),
        system_ids=tuple(bc0_lesepfade.system_ids(conn, company_id)))
