"""
BC2 · Die Nutzlast des Bewertungsschritts — was das Modell sieht, und was nicht.

ADR-006 · BC2, 6.3: die geschnittenen Potenziale, die entdoppelte Nutzlast der
**berührten** Teilprozesse, je Potenzial der **Korridor** seiner Klasse und die
**gemessene Komplexität** samt BC1s vier Skalen und BC0s sechs Kriterien als
Material zum Überschreiben.

**Keine Jahresstunden, keine Euro, keine Dauern.** Keine der Urteilsstellen
braucht sie — die Lage im Korridor fragt, wie viel die Lösung *vom Schritt*
abnimmt, nicht wie oft er läuft —, und das Rechenverbot brach in #194 genau dort,
wo Zahlen in der Nutzlast standen. Anders als die Erkennung (``bc1_gemessen``)
trägt diese Nutzlast BC1s Häufigkeiten und Dauern deshalb **gar nicht**; ein Test
hält das fest.

Der Aufwand in Personentagen (Nachtrag 7) braucht sie ebensowenig: er hängt an
der Größe der **Lösung**, nicht an der Häufigkeit des Schritts.

Hier liegt auch die Übersetzung von BC1s Profil in eine
:class:`modell.Schrittmessung` — sie ist die Naht zwischen Leseseite und
Rechenkern, und der Bewertungsschritt ist der Ort, an dem beide zusammenkommen.
"""

from __future__ import annotations

from typing import Any

from erkennung.bestand import Paketbestand, Teilprozess
from erkennung.erkennen import Erkennung, ErkanntesPotenzial
from erkennung.nutzlast import HEBBARE_FELDER
from modell import Parameter, Schrittmessung, gemessene_komplexitaet, runde

__all__ = ["baue_nutzlast", "messungen_je_teilprozess"]

_SKALEN = (
    "documentation_status",
    "standardization_level",
    "data_availability_score",
    "stability_score",
)


def _zahl(wert: Any) -> float | None:
    """psycopg2 liefert ``Decimal``; der Rechenkern rechnet in ``float``."""
    return None if wert is None else float(wert)


def messungen_je_teilprozess(bestand: Paketbestand) -> dict[str, Schrittmessung]:
    """BC1s Profile des Pakets als Messungen je Teilprozess.

    Ein Teilprozess ohne Profil fehlt im Ergebnis — er bekommt **keine leere
    Messung**. Der Rechenkern liest das Fehlen als „kein BC1-Profil" und weist
    dann keine Value-Zahl aus; eine leere Messung sähe aus wie eine erhobene
    Lücke.
    """
    messungen: dict[str, Schrittmessung] = {}
    for tp in bestand.teilprozesse:
        p = tp.bc1_profil
        if p is None:
            continue
        messungen[tp.teilprozess_id] = Schrittmessung(
            teilprozess_id=tp.teilprozess_id,
            frequency_per_year=_zahl(p.frequency_per_year),
            step_frequency_per_year=_zahl(p.step_frequency_per_year),
            focus_step_duration_minutes=_zahl(p.focus_step_duration_minutes),
            focus_step_duration_source=p.focus_step_duration_source,  # type: ignore[arg-type]
            focus_step_duration_confidence_pct=_zahl(p.focus_step_duration_confidence_pct),
            reifeskalen=p.reifeskalen,
            automation_potential_estimate_pct=_zahl(p.automation_potential_estimate_pct),
            erhebung_id=p.erhebung_id,
            kennzeichnung=p.kennzeichnung,
        )
    return messungen


def _kriterien(tp: Teilprozess) -> dict[str, float]:
    """BC0s Kriterien je Teilprozess: das Mittel der Stufen je Kriterium.

    Dieselbe Verdichtung wie ``v_prozessautomatisierung``. Material zum
    Überschreiben der Komplexität, **kein Rechenterm** (ADR-006, 2.6). Ein
    unbewerteter Teilprozess trägt keine — und keine Nullen (Auflage 4, #248).
    """
    je: dict[str, list[int]] = {}
    for b in tp.bitkom:
        je.setdefault(b.kriterium or f"Item {b.item_nr}", []).append(b.stufe)
    return {k: runde(sum(v) / len(v), 1) for k, v in je.items()}


def _tp_block(
    tp: Teilprozess, gehoben: set[str], messung: Schrittmessung | None
) -> dict[str, Any]:
    block: dict[str, Any] = {"teilprozess_id": tp.teilprozess_id, "name": tp.name}
    if tp.ablauf:
        block["ablauf"] = tp.ablauf
    for feld in HEBBARE_FELDER:
        wert = getattr(tp, feld)
        if feld not in gehoben and wert:
            block[feld] = wert
    kriterien = _kriterien(tp)
    block["bc0_kriterien"] = kriterien or "nicht erhoben"
    if messung is not None and messung.reifeskalen is not None:
        block["bc1_reifeskalen"] = dict(zip(_SKALEN, messung.reifeskalen))
    else:
        block["bc1_reifeskalen"] = "nicht erhoben"
    return block


def _potenzial_block(
    p: ErkanntesPotenzial,
    messungen: dict[str, Schrittmessung],
    parameter: Parameter,
) -> dict[str, Any]:
    lo, hi = parameter.korridore[p.klasse]
    gemessen = gemessene_komplexitaet(
        p.beruehrte_teilprozess_ids,
        tuple(messungen[t] for t in p.beruehrte_teilprozess_ids if t in messungen),
    )
    block: dict[str, Any] = {
        "id": p.potenzial_id,
        "kernprozess_id": p.kernprozess_id,
        "titel": p.titel,
        "beruehrte_teilprozesse": list(p.beruehrte_teilprozess_ids),
        "ausgangslage": p.ausgangslage,
        "schmerzpunkte": list(p.schmerzpunkte),
        "loesungsansatz": p.loesungsansatz,
        "loesungsklasse": p.klasse,
        "korridor_pct": {"min": runde(lo * 100), "max": runde(hi * 100)},
    }
    if p.unsicherheit:
        block["unsicherheit_aus_der_erkennung"] = p.unsicherheit
    if gemessen is None:
        block["komplexitaet"] = {
            "gemessen": None,
            "ueberschreiben": "pflicht",
            "grund": "Nicht jedem beruehrten Teilprozess liegen BC1s vier Skalen vor.",
        }
    else:
        wert, herleitung = gemessen
        block["komplexitaet"] = {
            "gemessen": wert,
            "herleitung": herleitung,
            "ueberschreiben": "erlaubt, nur begruendet",
        }
    return block


def baue_nutzlast(
    erkennung: Erkennung,
    bestand: Paketbestand,
    parameter: Parameter,
    messungen: dict[str, Schrittmessung] | None = None,
) -> dict[str, Any]:
    """Die Nutzlast für **einen** Aufruf über alle Potenziale des Laufs (6.2)."""
    if messungen is None:
        messungen = messungen_je_teilprozess(bestand)
    beruehrt = {t for p in erkennung.potenziale for t in p.beruehrte_teilprozess_ids}

    kernprozesse: list[dict[str, Any]] = []
    for kp in bestand.kernprozesse:
        tps = [t for t in kp.teilprozesse if t.teilprozess_id in beruehrt]
        if not tps:
            continue
        block: dict[str, Any] = {"kernprozess_id": kp.kernprozess_id, "name": kp.name}
        for schluessel, wert in (
            ("ausloeser", kp.ausloeser),
            ("eingang", kp.eingang),
            ("ausgang", kp.ausgang),
        ):
            if wert:
                block[schluessel] = wert
        # Dieselbe bedingte Entdopplung wie in der Erkennung: gehoben wird nur,
        # was unter den beruehrten Geschwistern tatsaechlich uebereinstimmt.
        gehoben: dict[str, str] = {}
        for feld in HEBBARE_FELDER:
            werte = {getattr(t, feld) or "" for t in tps}
            if len(werte) == 1 and len(tps) > 1 and (einziger := werte.pop()):
                gehoben[feld] = einziger
        if gehoben:
            block["gilt_fuer_alle_teilprozesse"] = gehoben
        block["teilprozesse"] = [
            _tp_block(t, set(gehoben), messungen.get(t.teilprozess_id)) for t in tps
        ]
        kernprozesse.append(block)

    m = bestand.mandant
    rahmen: dict[str, Any] = {"company_id": bestand.company_id, "paket_id": bestand.paket_id}
    for schluessel, wert in (("mandant", m.name), ("branche", m.branche)):
        if wert:
            rahmen[schluessel] = wert

    return {
        "rahmen": rahmen,
        "nutzwert_anker": {
            kat: {str(stufe): text for stufe, text in sorted(anker.items())}
            for kat, anker in parameter.nutzwert_anker.items()
        },
        "kernprozesse": kernprozesse,
        "potenziale": [
            _potenzial_block(p, messungen, parameter) for p in erkennung.potenziale
        ],
    }
