"""
Erzeugt das SIMULIERTE UC1-Konzept (Reisebuchung) fuer Tests des BC3-Slicers (A3, Kettentest 26.10.2026).

Warum: Fuer UC1 gibt es noch kein Konzept von BC2. Das echte entsteht erst im Kettentest, wenn
Zakarias Anforderungen durch BC1 und BC2 gelaufen sind. Bis dahin probt BC3 den Weg mit dieser
Simulation, im eigenen Ordner, nicht unter contracts/bc2-to-bc3/lieferungen/. BC3-01 startet sie
deshalb nie von selbst, nur der Handstart mit Pfad.

Wie: Dasselbe Vorgehen wie BC2s gen_lieferung_sim_uc3.py (#168). Texte aus BC3s eigener Vorlage
beispiel_uc1_reisebuchung.json (#176), Zahlen mit BC2s Rechenkern (app/modell/) nach ADR-006,
Format v3.1. BC2s Dateien werden nur gelesen. Nichts ist neu ausgedacht: Haeufigkeit, Dauer und
Stundensatz stehen woertlich in den Annahmen der Vorlage und werden gegen ist_kosten_eur_jahr
nachgerechnet.

Kennzeichnung: [SIMULIERT] im Titel, Warnblock am Anfang der Beschreibung, value_quelle "annahme",
gate1 "pending" mit Freigabesperre.

Aufruf aus dem Repo-Wurzelverzeichnis:
    python bc3-engineering-architect/simulation/gen_sim_uc1.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import uuid
from datetime import datetime

BASE = pathlib.Path(__file__).resolve().parents[2]
BC2_TOOLS = BASE / "bc2-strategic-advisor" / "tools"
sys.path.insert(0, str(BASE / "bc2-strategic-advisor" / "app"))
sys.path.insert(0, str(BC2_TOOLS))

from migriere_bc3_vorlage import (  # noqa: E402
    STUFE_ZU_ZEHN,
    klasse_aus_text,
    messverfahren_zu,
    nutzwert as nutzwert_dict,
    user_story,
)
from modell import (  # noqa: E402
    Nutzwert,
    Nutzwertkategorie,
    Potenzialeingang,
    Schrittmessung,
    rechne_lauf,
)
from modell.ausgabe import (  # noqa: E402
    als_eingangswerte,
    als_eintraege,
    als_konzept_potenzial,
    als_prozess_raenge,
)

QUELLE = BASE / "bc3-engineering-architect/bc2-anforderung/beispiel_uc1_reisebuchung.json"

# NoroAI wie in der UC3-Simulation. Simuliert ist das Paket, nicht der Mandant.
COMPANY_ID = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"
COMPANY_SLUG = "noroai"
PAKET_ID = "SIM-UC1-2026-10-22"
FASSUNG = 1
UEBERGEBEN_AM = "2026-10-22T00:00:00+02:00"
GELESEN_AM = "2026-10-22T00:00:00+02:00"
ERZEUGT_AM = "2026-10-22T00:00:00+02:00"
ZIEL = BASE / f"bc3-engineering-architect/simulation/{COMPANY_SLUG}-{PAKET_ID}-f{FASSUNG}"

# Eigener Namensraum fuer BC3s Simulationen, damit die Kennungen nicht mit BC2s kollidieren
NS = uuid.UUID("3c1b9d52-7e4a-4f0b-8a61-2d5e9f3b7c13")

MARKER = "[SIMULIERT]"

WARNUNG = (
    "SIMULIERT -- KEINE BEWERTUNG. Haeufigkeit und Dauer sind Annahmen aus BC3s Vorlage vom "
    "31.08.2026, nicht erhobene Groessen; Gate 0 ist fuer KP-06.TP-2 nicht durchlaufen. "
    "Dieses Konzept dient nur dazu, den BC3-Slicer vor dem Kettentest zu proben. Nicht fuer "
    "Entscheidungen, Angebote oder Gate-1-Freigaben verwenden."
)

ERZEUGT_VON = (
    "gen_sim_uc1.py (BC3) -- SIMULIERTES UC1-Konzept fuer Tests des Slicers. Texte aus BC3s "
    "Vorlage vom 31.08.2026, Zahlen mit BC2s app/modell/ nach ADR-006 gerechnet, Eingaenge gesetzt."
)


def _zahl(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def groessen_aus_annahmen(potenzial: dict) -> tuple[float, float, float]:
    """Haeufigkeit (1/Jahr), Dauer (min) und Stundensatz aus den Annahmen der Vorlage, mit Gegenprobe."""
    frequenz = dauer = satz = None
    for a in potenzial["value"].get("annahmen", []):
        if frequenz is None and (t := re.search(r"Jahresvolumen\s+([\d.,]+)", a)):
            frequenz = _zahl(t.group(1))
        if dauer is None and (t := re.search(r"([\d.,]+)\s*Min\s*/", a)):
            dauer = _zahl(t.group(1))
        if satz is None and (t := re.search(r"Vollkostensatz\s+([\d.,]+)\s*EUR/h", a)):
            satz = _zahl(t.group(1))

    fehlend = [n for n, w in (("Haeufigkeit", frequenz), ("Dauer", dauer), ("Stundensatz", satz)) if w is None]
    if fehlend:
        raise SystemExit(f"{potenzial['titel']!r}: {', '.join(fehlend)} nicht in den Annahmen gefunden")

    nachgerechnet = frequenz * dauer / 60 * satz
    erwartet = potenzial["value"]["ist_kosten_eur_jahr"]
    if abs(nachgerechnet - erwartet) > 1.0:
        raise SystemExit(
            f"{potenzial['titel']!r}: {frequenz:g} x {dauer:g} min x {satz:g} EUR/h = "
            f"{nachgerechnet:,.0f} EUR/Jahr, die Vorlage nennt {erwartet:,.0f}"
        )
    return frequenz, dauer, satz


def als_nutzwert(potenzial: dict) -> Nutzwert:
    roh = nutzwert_dict(potenzial, STUFE_ZU_ZEHN[potenzial["impact"]])
    mach = lambda k: Nutzwertkategorie(roh[k]["wert"], roh[k]["begruendung"])  # noqa: E731
    return Nutzwert(
        mach("qualitaet"),
        mach("durchlaufzeit"),
        mach("fehlerreduktion"),
        mach("mitarbeiterzufriedenheit"),
        mach("compliance"),
    )


def als_eingang(potenzial: dict, kp_id: str) -> Potenzialeingang:
    frequenz, dauer, satz = groessen_aus_annahmen(potenzial)
    klasse = klasse_aus_text(potenzial["titel"], potenzial["potenzielle_loesung"]["ansatz"])
    tp = potenzial["betroffene_teilprozess_ids"][0]
    kennzeichnung = (
        f"Testdaten aus BC3s Vorlage vom 31.08.2026 ({QUELLE.name}) -- Annahme, nicht "
        f"erhoben. BC3 rechnete mit {satz:.0f} EUR/h, BC2s Kern mit dem Mischsatz 43 EUR/h (#172)."
    )
    return Potenzialeingang(
        potenzial_id=str(uuid.uuid5(NS, f"{PAKET_ID}:{potenzial['potenzial_id']}")),
        titel=f"{MARKER} {potenzial['titel']}",
        kp_id=kp_id,
        betroffene_teilprozess_ids=tuple(potenzial["betroffene_teilprozess_ids"]),
        klasse=klasse,
        automatisierungsgrad_begruendung=(
            f"Klasse {klasse!r} aus dem Loesungsansatz der Vorlage abgeleitet, Korridor "
            "ungeschmaelert, weil keine LLM-Verortung vorliegt."
        ),
        nutzwert=als_nutzwert(potenzial),
        messungen=(
            Schrittmessung(
                teilprozess_id=tp,
                frequency_per_year=frequenz,
                focus_step_duration_minutes=dauer,
                focus_step_duration_source="geschaetzt",
                reifeskalen=None,
                erhebung_id=potenzial["potenzial_id"],
                kennzeichnung=kennzeichnung,
            ),
        ),
        komplexitaet_ueberschrieben=STUFE_ZU_ZEHN[potenzial["umsetzungskomplexitaet"]],
        komplexitaet_begruendung=(
            f"BC3s ordinale Stufe {potenzial['umsetzungskomplexitaet']!r} auf die Stufenmitte "
            f"{STUFE_ZU_ZEHN[potenzial['umsetzungskomplexitaet']]} abgebildet. BC1s vier Skalen "
            f"liegen fuer {tp} nicht vor."
        ),
        aufwand_schaetzung_pt=float(potenzial["aufwand_schaetzung_pt"]),
        groessen_gesetzt=True,
    )


def texte(potenzial: dict, kp_id: str) -> dict:
    return {
        "beschreibung": f"{WARNUNG}\n\n{potenzial['beschreibung']}",
        "to_be_vision": potenzial["to_be_vision"],
        "user_story": user_story(potenzial, kp_id),
        "akzeptanzkriterien_geschaeftlich": [
            {"kriterium": k, "messverfahren": messverfahren_zu(k)}
            for k in potenzial["akzeptanzkriterien_geschaeftlich"]
        ],
        "fachliche_anforderungen": potenzial["fachliche_anforderungen"],
        "betroffene_prozessschritte": potenzial["betroffene_prozessschritte"],
        "betroffene_systeme": potenzial["betroffene_systeme"],
        "potenzielle_loesung": potenzial["potenzielle_loesung"],
        "voraussetzungen": potenzial["voraussetzungen"],
        "risiken": potenzial.get("risiken", []),
        "querschnitte": {
            "zukunftssicherheit": (
                "Nicht aus BC3s Vorlage uebernehmbar -- sie fuehrt keinen Querschnitt. "
                "Als Luecke ausgewiesen, nicht erfunden."
            ),
            "abhaengigkeiten": [],
        },
        # v3.1: jedes Potenzial traegt das Feld, eine Simulation ersetzt nichts
        "ersetzt_potenzial_ids": [],
    }


def main() -> None:
    vorlage = json.loads(QUELLE.read_text(encoding="utf-8"))
    kp_id = vorlage["kontext"]["kp_id"]

    eingaenge = [als_eingang(p, kp_id) for p in vorlage["potenziale"]]
    lauf = rechne_lauf(COMPANY_ID, PAKET_ID, eingaenge)

    konzept_id = str(uuid.uuid5(NS, f"{PAKET_ID}:konzept:{kp_id}:f{FASSUNG}"))
    konzept_ids = {kp_id: konzept_id}
    nach_herkunft = {e.messungen[0].erhebung_id: e for e in eingaenge}
    gelesen = datetime.fromisoformat(GELESEN_AM)

    potenziale = []
    eingangswerte = []
    for pot in lauf.potenziale:
        quelle = next(p for p in vorlage["potenziale"] if nach_herkunft[p["potenzial_id"]].potenzial_id == pot.potenzial_id)
        eingang = nach_herkunft[quelle["potenzial_id"]]
        potenziale.append(als_konzept_potenzial(pot, eingang.nutzwert) | texte(quelle, kp_id))
        eingangswerte.extend(als_eingangswerte(pot, gelesen))

    # Reihenfolge wie in BC3s Vorlage: die Angebotserstellung setzt geprueft Optionen voraus
    neue_id = {p["potenzial_id"]: nach_herkunft[p["potenzial_id"]].potenzial_id for p in vorlage["potenziale"]}
    reihenfolge = [neue_id[i] for i in vorlage["gesamtempfehlung"]["reihenfolge_potenzial_ids"]]

    konzept = {
        "konzept_id": konzept_id,
        "schema_version": "3.1",
        "company_id": COMPANY_ID,
        "paket_id": PAKET_ID,
        "uebergeben_am": UEBERGEBEN_AM,
        "gelesen_am": GELESEN_AM,
        "fassung": FASSUNG,
        "erzeugt_am": ERZEUGT_AM,
        "erzeugt_von": ERZEUGT_VON,
        "kontext": {
            "prozess_kurzbeschreibung": (
                f"{MARKER} KP-06.TP-2 (UC1, Reisebuchung): Reiseanfragen kommen per Mail oder "
                "Formular, Verfuegbarkeit wird in mehreren Portalen geprueft, Angebot und Buchung "
                "laufen von Hand. Zahlen sind Annahmen aus BC3s Vorlage."
            ),
            "kp_id": kp_id,
            "unternehmen": vorlage["kontext"]["unternehmen"],
            "betroffene_systeme_landschaft": vorlage["kontext"]["betroffene_systeme_landschaft"],
            "hauptschmerzpunkte": vorlage["kontext"]["hauptschmerzpunkte"],
        },
        "potenziale": potenziale,
        "gesamtempfehlung": {
            "reihenfolge_potenzial_ids": reihenfolge,
            "begruendung": vorlage["gesamtempfehlung"]["begruendung"],
        },
        "eingangswerte": eingangswerte,
    }

    priorisierung = {
        "priorisierung_id": str(uuid.uuid5(NS, f"{PAKET_ID}:prio:f{FASSUNG}")),
        # 3.0 wie in BC2s UC3-Simulation: 3.1 verlangt ausgangslage, die BC3s Vorlage nicht hat
        "schema_version": "3.0",
        "company_id": COMPANY_ID,
        "paket_id": PAKET_ID,
        "uebergeben_am": UEBERGEBEN_AM,
        "gelesen_am": GELESEN_AM,
        "fassung": FASSUNG,
        "erzeugt_am": ERZEUGT_AM,
        "score_formel": (
            "score = impact x (11 - umsetzungskomplexitaet), Bereich 1...100, gerechnet mit BC2s "
            "app/modell/. umsetzungskomplexitaet GEURTEILT aus BC3s ordinaler Stufe -- BC1s vier "
            "Skalen liegen fuer KP-06.TP-2 nicht vor."
        ),
        "konzept_ids": [konzept_id],
        "eintraege": als_eintraege(lauf, konzept_ids),
        "prozess_raenge": als_prozess_raenge(lauf, konzept_ids),
        "gate1": {
            "status": "pending",
            "kommentar": (
                "FREIGABESPERRE. Simuliertes UC1-Konzept von BC3 fuer Tests des Slicers: "
                "Haeufigkeit und Dauer sind Annahmen aus BC3s Vorlage vom 31.08.2026, Gate 0 ist "
                "fuer KP-06.TP-2 nicht durchlaufen. Darf nicht freigegeben werden. Das echte "
                "UC1-Konzept entsteht im Kettentest am 26.10.2026."
            ),
        },
    }

    ZIEL.mkdir(parents=True, exist_ok=True)
    schreibe(ZIEL / f"konzept_{kp_id}.json", konzept)
    schreibe(ZIEL / "prozesspriorisierung.json", priorisierung)
    print(f"geschrieben: {ZIEL.relative_to(BASE)}")
    for e in priorisierung["eintraege"]:
        print(f"  {e['potenzialrang']}. {e['prioritaetsgruppe']:7s} Score {e['score']:3.0f}  {e['titel']}")
    for h in lauf.hinweise:
        print(f"  Hinweis ({h.art}): {h.text}")


def schreibe(pfad: pathlib.Path, inhalt: dict) -> None:
    pfad.write_text(json.dumps(inhalt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
