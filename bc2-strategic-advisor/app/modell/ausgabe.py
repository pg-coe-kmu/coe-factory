"""
BC2 · Vom Rechenergebnis in die Form des Vertrags v3.0.

Eigenes Modul, damit ``rechnen.py`` rein bleibt: der Kern kennt keine
JSON-Form, und die Abbildung kennt keine Rechnung. Ändert BC3 den Vertrag,
ändert sich diese Datei — nicht das Modell.

**Was hier entsteht, ist ein halbes Potenzial.** Der Vertrag verlangt je
Potenzial auch ``beschreibung``, ``to_be_vision``, ``user_story``,
``akzeptanzkriterien_geschaeftlich``, ``fachliche_anforderungen``,
``betroffene_prozessschritte``, ``betroffene_systeme``, ``potenzielle_loesung``,
``voraussetzungen`` und ``querschnitte`` — alles Text, den das **LLM** schreibt
und dieser Kern nicht kennt. ``als_konzept_potenzial`` liefert die Felder, die
BC2 *rechnet*; der Rest wird darübergelegt (``| texte``). Der Schnitt läuft
damit genau dort, wo ADR-006 2.0 ihn zieht: Rechnen tut Python, Urteilen das LLM.
"""

from __future__ import annotations

from datetime import datetime

from .rechnen import Lauf, Nutzwert, Potenzial, Spanne, runde

__all__ = [
    "als_konzept_potenzial",
    "als_eingangswerte",
    "als_prozess_raenge",
    "als_eintraege",
]


def _spanne(s: Spanne | None, stellen: int = 0) -> dict[str, float] | None:
    return None if s is None else s.als_dict(stellen)


def _nutzwert(n: Nutzwert, mittel: float) -> dict:
    def k(kat):
        return {"wert": kat.wert, "begruendung": kat.begruendung}

    return {
        "qualitaet": k(n.qualitaet),
        "durchlaufzeit": k(n.durchlaufzeit),
        "fehlerreduktion": k(n.fehlerreduktion),
        "mitarbeiterzufriedenheit": k(n.mitarbeiterzufriedenheit),
        "compliance": k(n.compliance),
        "mittel": runde(mittel, 1),
    }


def als_konzept_potenzial(pot: Potenzial, nutzwert: Nutzwert) -> dict:
    """Die gerechneten Felder eines Potenzials in Vertragsform (v3.0).

    ``nutzwert`` wird gereicht statt am ``Potenzial`` mitgeführt: der Kern
    braucht daraus nur das Mittel, die fünf Begründungssätze gehören zum
    Urteil des LLM und nicht ins Rechenergebnis.
    """
    value: dict = {"value_quelle": pot.value.value_quelle}
    if pot.value.value_quelle == "keine":
        value["grund"] = pot.value.grund
    else:
        value.update(
            {
                "ist_kosten_eur_jahr": _spanne(pot.value.ist_kosten_eur_jahr),
                "einsparung_eur_jahr": _spanne(pot.value.einsparung_eur_jahr),
                "ersparnis_prozent": _spanne(pot.value.ersparnis_prozent, 1),
                "investition_eur_richtwert": runde(pot.value.investition_eur_richtwert or 0),
                "amortisation_monate": _spanne(pot.value.amortisation_monate, 1),
            }
        )
    if pot.value.annahmen:
        value["annahmen"] = list(pot.value.annahmen)

    grad = pot.automatisierungsgrad
    ausgabe: dict = {
        "potenzial_id": pot.potenzial_id,
        "titel": pot.titel,
        "potenzialrang": pot.potenzialrang,
        "prioritaetsgruppe": pot.prioritaetsgruppe,
        "betroffene_teilprozess_ids": list(pot.betroffene_teilprozess_ids),
        "manueller_aufwand_heute": {
            # Ein Punktwert, kein Band: der Vertrag fuehrt ihn als gemessene
            # Jahresstundenzahl. Die Unsicherheit steht in 'herkunft' und wirkt
            # ueber die Bandbreite in 'value'.
            "stunden_jahr": runde(pot.jahresstunden_zentral or 0, 1),
            "herkunft": pot.aufwand_herkunft,
            "konfidenz_pct": pot.konfidenz_pct,
        },
        "automatisierungsgrad": {
            "klasse": grad.klasse,
            "angesetzt_min_pct": runde(grad.angesetzt.min * 100, 1),
            "angesetzt_max_pct": runde(grad.angesetzt.max * 100, 1),
            "begruendung": grad.begruendung,
            "bc1_schaetzung_pct": grad.bc1_schaetzung_pct,
        },
        "nutzwert": _nutzwert(nutzwert, pot.nutzwert),
        "impact": pot.impact,
        "impact_monetaer": pot.impact_monetaer,
        "umsetzungskomplexitaet": pot.umsetzungskomplexitaet,
        "komplexitaet_herkunft": pot.komplexitaet_herkunft,
        "value": value,
        "prioritaet_score": pot.prioritaet_score,
        "kategorie": pot.kategorie,
    }
    if pot.komplexitaet_begruendung:
        ausgabe["komplexitaet_begruendung"] = pot.komplexitaet_begruendung
    if pot.aufwand_schaetzung_pt is not None:
        ausgabe["aufwand_schaetzung_pt"] = pot.aufwand_schaetzung_pt
    if pot.hinweise:
        ausgabe["hinweise"] = [{"art": h.art, "text": h.text} for h in pot.hinweise]
    return ausgabe


def als_eingangswerte(pot: Potenzial, gelesen_am: datetime) -> list[dict]:
    """Die Herkunftsnachweise eines Potenzials, gestempelt mit dem Lesezeitpunkt.

    Die Differenz zwischen ``gelesen_am`` und ``uebergeben_am`` zeigt, wie viel
    sich zwischen Freigabe und Rechnung bewegt haben kann (ADR-006, 2.9).
    """
    stempel = gelesen_am.isoformat()
    zeilen = []
    for q in pot.eingangswerte:
        zeile: dict = {
            "groesse": q.groesse,
            "wert": q.wert,
            "herkunft_tabelle": q.herkunft_tabelle,
            "herkunft_spalte": q.herkunft_spalte,
            "gelesen_am": stempel,
        }
        if q.einheit is not None:
            zeile["einheit"] = q.einheit
        if q.herkunft_id is not None:
            zeile["herkunft_id"] = q.herkunft_id
        if q.betrifft_teilprozess_id is not None:
            zeile["betrifft_teilprozess_id"] = q.betrifft_teilprozess_id
        if q.kennzeichnung is not None:
            zeile["kennzeichnung"] = q.kennzeichnung
        zeilen.append(zeile)
    return zeilen


def als_prozess_raenge(lauf: Lauf, konzept_ids: dict[str, str]) -> list[dict]:
    """Die Prozessreihenfolge für ``priorisierung.schema.json``.

    ``konzept_ids`` bildet ``kp_id`` auf die ``konzept_id`` ab. Der Rechenkern
    kennt sie nicht und soll sie nicht kennen: ein Konzept entsteht je
    Kernprozess beim Ausliefern, und jede Fassung bekommt eine **neue** Kennung
    (ADR-007 · BC2, 2.5). Wer sie im Modell führte, verdrahtete die
    Fassungslogik in die Rechnung.
    """
    anzahl = {r.kp_id: 0 for r in lauf.prozess_raenge}
    for pot in lauf.potenziale:
        anzahl[pot.kp_id] = anzahl.get(pot.kp_id, 0) + 1

    return [
        {
            "prozessrang": r.rang,
            "kp_id": r.kp_id,
            "konzept_id": konzept_ids[r.kp_id],
            "bestes_potenzial_id": r.bestes_potenzial_id,
            "bester_score": r.bester_score,
            "anzahl_potenziale": anzahl[r.kp_id],
        }
        for r in lauf.prozess_raenge
    ]


def als_eintraege(lauf: Lauf, konzept_ids: dict[str, str]) -> list[dict]:
    """Die Potenzialliste für ``priorisierung.schema.json``, in Rangfolge."""
    eintraege = []
    for pot in lauf.potenziale:
        eintrag: dict = {
            "potenzialrang": pot.potenzialrang,
            "prioritaetsgruppe": pot.prioritaetsgruppe,
            "potenzial_id": pot.potenzial_id,
            "konzept_id": konzept_ids[pot.kp_id],
            "titel": pot.titel,
            "kp_id": pot.kp_id,
            "betroffene_teilprozess_ids": list(pot.betroffene_teilprozess_ids),
            "kategorie": pot.kategorie,
            "impact": pot.impact,
            "impact_monetaer": pot.impact_monetaer,
            "nutzwert_mittel": runde(pot.nutzwert, 1),
            "umsetzungskomplexitaet": pot.umsetzungskomplexitaet,
            "komplexitaet_herkunft": pot.komplexitaet_herkunft,
            "score": pot.prioritaet_score,
        }
        if pot.aufwand_schaetzung_pt is not None:
            eintrag["aufwand_pt"] = pot.aufwand_schaetzung_pt
        if pot.value.value_quelle != "keine":
            eintrag["einsparung_eur_jahr"] = _spanne(pot.value.einsparung_eur_jahr)
            eintrag["investition_eur_richtwert"] = runde(
                pot.value.investition_eur_richtwert or 0
            )
            eintrag["amortisation_monate"] = _spanne(pot.value.amortisation_monate, 1)
        eintraege.append(eintrag)
    return eintraege
