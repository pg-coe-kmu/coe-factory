"""
Erzeugt die SIMULIERTE UC3-Lieferung an BC3 -- die Rueckfallebene zum Durchstich (Issue #168).

ZWECK. Der erste echte Lauf ueber die ganze Strecke ist fuer KW 40 angesetzt (#206). Er steht
unter Vorbehalt: BC0 meldet am 20.09.2026 einen Fehler in Gate 0s manueller Freigabe und einen
Datenbank-Umbau mit offener Dauer. Rutscht der Durchstich, hat BC3 nichts, wogegen es schneidet --
und das ist der Zustand, aus dem #168 ueberhaupt entstanden ist. Diese Lieferung ist die
Rueckfallebene: dieselbe Form wie eine echte, mit erkennbar gesetzten Zahlen.

Der dritte Business Case (UC3, Consultant Placement) ist der Zuschnitt, um den Svetlana am
07.09.2026 gebeten hat -- um zu pruefen, ob erzeugte Daten den Workflow sauber durchlaufen.

WAS SIE VON DER LIEFERUNG VOM 30.08.2026 UNTERSCHEIDET. Jene lieferte *echte* Prozesse
(KP-02/03/04 aus BC0s Snapshot) mit gesetzten Zahlen und ist auf v2.0 eingefroren (ADR-007 BC2,
2.4). Diese hier ist eine *Probe des Weges*: v3.0, Ordnerschnitt nach ADR-007, gerechnet mit dem
Kern, der auch im Ernstfall rechnet.

DREI ENTSCHEIDUNGEN, DIE HIER STECKEN

  1. **Gerechnet wird mit ``app/modell/``, nicht mit einer zweiten Rechnung.** `migriere_bc3_vorlage.py`
     baut die ADR-006-Arithmetik selbst nach -- fuer eine Fixture vertretbar. Eine Rueckfallebene,
     die anders rechnet als der Ernstfall, probt aber den falschen Weg. Nebenbei ist dies der
     erste Lauf, der ``rechnen`` -> ``ausgabe`` -> Vertrag durchgaengig belastet.

  2. **Geteilt werden die Urteils-Ableitungen, nicht die Arithmetik.** `klasse_aus_text`,
     `nutzwert`, `user_story` und `messverfahren_zu` kommen aus `migriere_bc3_vorlage` -- dieselbe
     Vorlage, dieselben Regeln. Zwei Kopien derselben Urteilsregel driften auseinander, ohne dass
     es jemand bemerkt.

  3. **Haeufigkeit und Dauer stammen aus BC3s eigenen Annahmen**, nicht aus BC2s Fantasie: die
     Vorlage nennt sie woertlich ("600 Lebenslaeufe im Jahr", "20 Min/Lebenslauf"). Der Parser
     rechnet gegen BC3s `ist_kosten_eur_jahr` zurueck und bricht ab, wenn es nicht aufgeht --
     die Lesart ist damit widerlegbar und nicht geraten.

BC3s DATEIEN WERDEN NICHT ANGEFASST. Gelesen wird, geschrieben nicht -- dreimal ist in dieser
Karte aus einem fremden Artefakt auf die Absicht dahinter geschlossen worden (#163, #186, #165).

WIE DIE SIMULATION SICHTBAR BLEIBT. Gestaffelt danach, was das Kopieren in BC3s Tickets und von
dort in BC4s Code ueberlebt:

  Traeger                                  ueberlebt Kopieren?
  ---------------------------------------  -------------------
  `[SIMULIERT]` im Titel                   ja -- Titel wandern woertlich weiter
  Warnblock am Anfang der `beschreibung`   ja
  `value_quelle = "annahme"`               nein, nur maschinenlesbar
  `value.annahmen[0]`                      nein
  `gate1.kommentar` (Freigabesperre)       nein

`value_quelle = "annahme"` ist dabei keine Notloesung, sondern die schemakonforme Wahrheit --
der Wert kam in v3.0 wegen genau dieses Tickets in den Vertrag. Der Rechenkern konnte ihn bis
heute nicht vergeben; dass er es jetzt kann (``Potenzialeingang.groessen_gesetzt``), ist der
zweite Fund dieses Tickets.

Aufruf aus dem Repo-Wurzelverzeichnis:
    python3 bc2-strategic-advisor/tools/gen_lieferung_sim_uc3.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import uuid
from datetime import datetime

BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "bc2-strategic-advisor" / "app"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

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
    rechne_lauf,
)
from modell.ausgabe import (  # noqa: E402
    als_eingangswerte,
    als_eintraege,
    als_konzept_potenzial,
    als_prozess_raenge,
)

QUELLE = BASE / "bc3-engineering-architect/bc2-anforderung/beispiel_uc3_consultant_placement.json"

# --- Rahmen des Laufs ------------------------------------------------------------------------
# NoroAI, wie in den Fixtures (#187). Die company_id ist echt -- simuliert ist das Paket, nicht
# der Mandant.
COMPANY_ID = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"
COMPANY_SLUG = "noroai"
# Die paket_id sagt im Namen, was sie ist. Es gibt kein Gate-0-Paket fuer UC3: Gate 0 ist bisher
# fuer KP-05.TP-1 durchlaufen, nicht fuer KP-06.TP-1. Ein Ordner, dem man die Simulation erst im
# Inneren ansieht, waere genau die Falle, gegen die dieses Ticket arbeitet.
PAKET_ID = "SIM-UC3-2026-09-21"
FASSUNG = 1
# Feste Zeitstempel -- halten die Ausgabe diff-stabil (wie gen_uebergangslieferung.py).
UEBERGEBEN_AM = "2026-09-21T00:00:00+02:00"
GELESEN_AM = "2026-09-21T00:00:00+02:00"
ERZEUGT_AM = "2026-09-21T00:00:00+02:00"
ZIEL = BASE / f"contracts/bc2-to-bc3/lieferungen/{COMPANY_SLUG}-{PAKET_ID}-f{FASSUNG}"

# Eigener Namensraum, damit die Kennungen dieses Laufs deterministisch und zugleich
# unverwechselbar BC2s sind. BC3s Original-ID reist als `herkunft_id` in den Eingangswerten mit.
NS = uuid.UUID("6f1e9c44-8f1a-4d2e-9a77-1c9b2f0a5e31")

MARKER = "[SIMULIERT]"

WARNUNG = (
    "SIMULIERT -- KEINE BEWERTUNG. Haeufigkeit und Dauer sind aus BC3s Formatvorlage vom "
    "31.08.2026 uebernommene Annahmen, nicht erhobene Groessen; Gate 0 ist fuer KP-06.TP-1 "
    "nicht durchlaufen. Diese Lieferung ist die Rueckfallebene zum Durchstich in KW 40 (#206) "
    "und dient dazu, den Weg zu proben. Nicht fuer Entscheidungen, Angebote oder "
    "Gate-1-Freigaben verwenden."
)

ERZEUGT_VON = (
    "gen_lieferung_sim_uc3.py -- SIMULIERTE Rueckfall-Lieferung (#168). Texte aus BC3s Vorlage "
    "vom 31.08.2026, Zahlen mit app/modell/ nach ADR-006 BC2 gerechnet, Eingaenge gesetzt."
)


# --- BC3s Annahmen lesen ----------------------------------------------------------------------


def _zahl(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def groessen_aus_annahmen(potenzial: dict) -> tuple[float, float, float]:
    """Haeufigkeit (1/Jahr), Dauer (min) und BC3s Stundensatz aus den Annahmen der Vorlage.

    BC3 nennt beide Groessen woertlich. Sie herauszulesen ist ehrlicher, als sie neu zu erfinden
    -- und pruefbar: Haeufigkeit x Dauer / 60 x Stundensatz muss BC3s `ist_kosten_eur_jahr`
    ergeben. Tut es das nicht, ist die Lesart falsch, und dann soll dieser Lauf abbrechen statt
    still danebenzuliegen.
    """
    annahmen = potenzial["value"].get("annahmen", [])
    frequenz = dauer = satz = None

    for a in annahmen:
        if frequenz is None and (t := re.search(r"([\d.,]+)\s+\S+\s+im\s+Jahr", a)):
            frequenz = _zahl(t.group(1))
        if dauer is None and (t := re.search(r"([\d.,]+)\s*Min\s*/", a)):
            dauer = _zahl(t.group(1))
        if satz is None and (t := re.search(r"Vollkostensatz\s+([\d.,]+)\s*EUR/h", a)):
            satz = _zahl(t.group(1))

    fehlend = [n for n, w in (("Haeufigkeit", frequenz), ("Dauer", dauer), ("Stundensatz", satz)) if w is None]
    if fehlend:
        raise SystemExit(
            f"{potenzial['titel']!r}: {', '.join(fehlend)} nicht in BC3s Annahmen gefunden. "
            "Die Vorlage hat sich geaendert -- den Parser nachziehen, nicht die Zahl setzen."
        )

    # Die Gegenprobe. Sie macht die Lesart widerlegbar.
    nachgerechnet = frequenz * dauer / 60 * satz
    erwartet = potenzial["value"]["ist_kosten_eur_jahr"]
    if abs(nachgerechnet - erwartet) > 1.0:
        raise SystemExit(
            f"{potenzial['titel']!r}: {frequenz:g} x {dauer:g} min x {satz:g} EUR/h = "
            f"{nachgerechnet:,.0f} EUR/Jahr, BC3 nennt aber {erwartet:,.0f}. Die Groessen sind "
            "falsch gelesen -- hier abgebrochen, statt mit stillen Zahlen weiterzurechnen."
        )
    return frequenz, dauer, satz


def als_nutzwert(potenzial: dict) -> Nutzwert:
    """Die fuenf Kategorien aus `migriere_bc3_vorlage` in die Form des Rechenkerns."""
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

    return Potenzialeingang(
        potenzial_id=str(uuid.uuid5(NS, f"{PAKET_ID}:{potenzial['potenzial_id']}")),
        titel=f"{MARKER} {potenzial['titel']}",
        kp_id=kp_id,
        betroffene_teilprozess_ids=tuple(potenzial["betroffene_teilprozess_ids"]),
        klasse=klasse,
        automatisierungsgrad_begruendung=(
            f"Klasse {klasse!r} aus dem Loesungsansatz der Vorlage abgeleitet. Der Korridor wird "
            "ungeschmaelert uebernommen, weil keine LLM-Verortung vorliegt -- im echten Lauf engt "
            "das LLM ihn ein und begruendet die Lage."
        ),
        nutzwert=als_nutzwert(potenzial),
        frequency_per_year=frequenz,
        total_duration_minutes=dauer,
        # BC3 schreibt durchgaengig "Annahme, nicht erhoben" / "nicht gemessen".
        focus_step_duration_source="geschaetzt",
        # BC1s vier Skalen liegen fuer KP-06.TP-1 nicht vor -- ohne sie urteilt das Modell, und
        # die Herkunft der Komplexitaet faellt von 'gemessen' auf 'geurteilt'. Genau die Stelle,
        # an der ein echter Lauf besser waere als dieser.
        reifeskalen=None,
        komplexitaet_ueberschrieben=STUFE_ZU_ZEHN[potenzial["umsetzungskomplexitaet"]],
        komplexitaet_begruendung=(
            f"BC3s ordinale Stufe {potenzial['umsetzungskomplexitaet']!r} auf die Stufenmitte "
            f"{STUFE_ZU_ZEHN[potenzial['umsetzungskomplexitaet']]} abgebildet. BC1s vier Skalen am "
            "Fokus-Schritt liegen fuer KP-06.TP-1 nicht vor."
        ),
        aufwand_schaetzung_pt=float(potenzial["aufwand_schaetzung_pt"]),
        erhebung_id=potenzial["potenzial_id"],
        # Der Kern haengt seinen `testdaten`-Hinweis an, wenn die Kennzeichnung mit "Testdaten"
        # beginnt (#184). Das Praefix ist hier keine Formalie, sondern zutreffend.
        kennzeichnung=(
            f"Testdaten aus BC3s Vorlage vom 31.08.2026 ({QUELLE.name}) -- Annahme, nicht "
            f"erhoben. BC3 rechnete mit {satz:.0f} EUR/h, BC2 mit dem Mischsatz 43 EUR/h (#172); "
            "die absoluten Betraege liegen damit niedriger, die Rangfolge bleibt gleich."
        ),
        groessen_gesetzt=True,
    )


# --- Texte ueberlagern ------------------------------------------------------------------------


def texte(potenzial: dict, kp_id: str) -> dict:
    """Was das LLM im echten Lauf schreibt und hier aus BC3s Vorlage kommt.

    ``als_konzept_potenzial`` liefert bewusst nur ein halbes Potenzial -- die gerechneten Felder.
    Der Text wird darueber gelegt; der Schnitt laeuft dort, wo ADR-006 2.0 ihn zieht.
    """
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
                "Nicht aus BC3s Vorlage uebernehmbar -- sie fuehrt keinen Querschnitt. Im echten "
                "Lauf urteilt das LLM; hier als Luecke ausgewiesen, statt sie zu erfinden."
            ),
            "abhaengigkeiten": [],
        },
    }


def main() -> None:
    vorlage = json.loads(QUELLE.read_text(encoding="utf-8"))
    kp_id = vorlage["kontext"]["kp_id"]

    eingaenge = [als_eingang(p, kp_id) for p in vorlage["potenziale"]]
    lauf = rechne_lauf(COMPANY_ID, PAKET_ID, eingaenge)

    konzept_id = str(uuid.uuid5(NS, f"{PAKET_ID}:konzept:{kp_id}:f{FASSUNG}"))
    konzept_ids = {kp_id: konzept_id}
    nach_herkunft = {e.erhebung_id: e for e in eingaenge}
    gelesen = datetime.fromisoformat(GELESEN_AM)

    potenziale = []
    eingangswerte = []
    for pot in lauf.potenziale:
        quelle = next(p for p in vorlage["potenziale"] if nach_herkunft[p["potenzial_id"]].potenzial_id == pot.potenzial_id)
        eingang = nach_herkunft[quelle["potenzial_id"]]
        potenziale.append(als_konzept_potenzial(pot, eingang.nutzwert) | texte(quelle, kp_id))
        eingangswerte.extend(als_eingangswerte(pot, gelesen))

    konzept = {
        "konzept_id": konzept_id,
        "schema_version": "3.0",
        "company_id": COMPANY_ID,
        "paket_id": PAKET_ID,
        "uebergeben_am": UEBERGEBEN_AM,
        "gelesen_am": GELESEN_AM,
        "fassung": FASSUNG,
        "erzeugt_am": ERZEUGT_AM,
        "erzeugt_von": ERZEUGT_VON,
        "kontext": {
            # maxLength 280 im Vertrag -- BC3s Fassung ist laenger und wird gekuerzt, nicht
            # umgeschrieben.
            "prozess_kurzbeschreibung": (
                f"{MARKER} KP-06.TP-1 (UC3, Consultant Placement): Lebenslaeufe gehen "
                "unstrukturiert ein; fuer eine Ausschreibung werden sie von Hand gesichtet und "
                "abgeglichen. Zahlen sind Annahmen aus BC3s Vorlage."
            ),
            "kp_id": kp_id,
            "unternehmen": vorlage["kontext"]["unternehmen"],
            "betroffene_systeme_landschaft": vorlage["kontext"]["betroffene_systeme_landschaft"],
            "hauptschmerzpunkte": vorlage["kontext"]["hauptschmerzpunkte"],
        },
        "potenziale": potenziale,
        "gesamtempfehlung": {
            "reihenfolge_potenzial_ids": [p["potenzial_id"] for p in potenziale],
            "begruendung": (
                "Reihenfolge strikt nach Score (ADR-006 BC2, 2.7). BC3s Vorlage begruendet die "
                "eigene Reihenfolge fachlich -- der Abgleich setzt strukturierte Profile voraus; "
                "diese Abhaengigkeit steht seit v3.0 in potenziale[].querschnitte und geht nicht "
                "in den Score ein."
            ),
        },
        "eingangswerte": eingangswerte,
    }

    priorisierung = {
        "priorisierung_id": str(uuid.uuid5(NS, f"{PAKET_ID}:prio:f{FASSUNG}")),
        "schema_version": "3.0",
        "company_id": COMPANY_ID,
        "paket_id": PAKET_ID,
        "uebergeben_am": UEBERGEBEN_AM,
        "gelesen_am": GELESEN_AM,
        "fassung": FASSUNG,
        "erzeugt_am": ERZEUGT_AM,
        "score_formel": (
            "score = impact x (11 - umsetzungskomplexitaet), Bereich 1...100. "
            "impact = round((impact_monetaer + nutzwert) / 2); impact_monetaer aus der Mitte der "
            "Eingaenge ueber absolute Euro-Schwellen (1.000...50.000 EUR/Jahr, logarithmisch). "
            "umsetzungskomplexitaet hier GEURTEILT aus BC3s ordinaler Stufe -- BC1s vier Skalen "
            "liegen fuer KP-06.TP-1 nicht vor."
        ),
        "konzept_ids": [konzept_id],
        "eintraege": als_eintraege(lauf, konzept_ids),
        "prozess_raenge": als_prozess_raenge(lauf, konzept_ids),
        "gate1": {
            "status": "pending",
            "kommentar": (
                "FREIGABESPERRE. Simulierte Rueckfall-Lieferung (#168): Haeufigkeit und Dauer sind "
                "Annahmen aus BC3s Vorlage vom 31.08.2026, Gate 0 ist fuer KP-06.TP-1 nicht "
                "durchlaufen, die Umsetzungskomplexitaet ist geurteilt statt gemessen. Diese "
                "Priorisierung darf nicht freigegeben werden. Der echte Lauf entsteht im "
                "Durchstich KW 40 (#206) und ersetzt sie als neue Fassung."
            ),
        },
    }

    ZIEL.mkdir(parents=True, exist_ok=True)
    schreibe(ZIEL / f"konzept_{kp_id}.json", konzept)
    schreibe(ZIEL / "prozesspriorisierung.json", priorisierung)
    print(f"geschrieben: {ZIEL.relative_to(BASE)}")
    for e in priorisierung["eintraege"]:
        print(f"  {e['potenzialrang']}. {e['prioritaetsgruppe']:7s} Score {e['score']:3.0f}  {e['titel']}")
    if lauf.hinweise:
        for h in lauf.hinweise:
            print(f"  Hinweis ({h.art}): {h.text}")


def schreibe(pfad: pathlib.Path, inhalt: dict) -> None:
    pfad.write_text(json.dumps(inhalt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
