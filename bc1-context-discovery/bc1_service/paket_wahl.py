"""Wählt das Use-Case-Paket anhand von BC1_PAKET (Default: discovery)."""
from __future__ import annotations

from collections.abc import Mapping

from bc1_core.package import TOY_PROZESS, UseCasePackage
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket


def waehle_paket(
    umgebung: Mapping[str, str],
    *,
    kontext: Bc0Kontext | None = None,
) -> UseCasePackage:
    wahl = umgebung.get("BC1_PAKET", "discovery")
    if wahl == "discovery":
        return baue_discovery_paket(kontext=kontext)
    if wahl == "toy":
        return TOY_PROZESS
    raise RuntimeError(
        f"BC1_PAKET='{wahl}' ist unbekannt — erlaubt sind 'discovery' "
        "(Default) oder 'toy' (Mini-Testpaket)."
    )
