"""
Hebt BC3s Formatvorlage vom 31.08.2026 auf den Vertrag v3.0 -- als Fixture, nicht als Lieferung.

ZWECK. Ticket #187 verlangt, dass BC3s drei Beispielkonzepte gegen das neue Schema validieren.
Woertlich koennen sie das nicht: sie tragen schema_version '2.1-bc3', fuehren gate1 im Konzept
(seit ADR-007 BC2 gehoert er in die Priorisierung) und kennen keins der Rechenfelder aus
ADR-006 BC2. Dieses Skript zeigt stattdessen, was die Frage eigentlich meint -- dass BC3s
INHALT in v3.0 hineinpasst -- indem es ihn deterministisch hinueberhebt.

BC3s Dateien in `bc3-engineering-architect/` werden NICHT angefasst. Sie gehoeren einem anderen
Kontext, und dreimal ist in dieser Karte schon aus einem fremden Artefakt auf die Absicht dahinter
geschlossen worden (#163, #186, #165). Gelesen wird, geschrieben nicht.

ZWEI FUNDE, die erst das Hinueberheben zeigt:

  1. uc1 (Reisebuchung) und uc3 (Consultant Placement) tragen BEIDE kp_id 'KP-06', nur
     verschiedene Teilprozesse (TP-2 und TP-1). Ein Konzept deckt in v3.0 genau EINEN Kernprozess
     ab (ADR-005 BC2), also werden aus drei Beispielen ZWEI Konzepte. BC3s drei Dateien sind drei
     Use Cases, keine drei Konzepte.
  2. Weder `user_story` noch `messverfahren` kommen in der Vorlage vor. Beide verantwortet BC2
     (#186, bestaetigt 09.09.2026) -- die Vorlage konnte sie gar nicht haben.

WAS HERGELEITET IST UND WAS UEBERNOMMEN. Uebernommen wird jeder Text: Beschreibung, to_be_vision,
fachliche Anforderungen, Akzeptanzkriterien, Systeme, Schritte, Voraussetzungen, Risiken,
Loesungsansatz. Hergeleitet werden die Zahlen -- nach ADR-006 BC2, aus den Groessen, die BC3s
Annahmen nennen. Jede Herleitung steht unten bei ihrer Funktion und reist als Annahme mit.

Aufruf aus dem Repo-Wurzelverzeichnis:
    python3 bc2-strategic-advisor/tools/migriere_bc3_vorlage.py
"""
import json
import math
import pathlib
import re
import uuid

BASE = pathlib.Path(__file__).resolve().parents[2]
QUELLE = BASE / "bc3-engineering-architect/bc2-anforderung"
ZIEL = BASE / "contracts/examples"

# --- Fixture-Rahmen -------------------------------------------------------------------------
# NoroAI aus bc2-strategic-advisor/CLAUDE.md. Die paket_id ist eine Fixture-Kennung: BC3s Vorlage
# entstand vor dem ersten Gate-0-Paket, es gibt also keine echte.
COMPANY_ID = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"
PAKET_ID = "FIXTURE-BC3-VORLAGE-2026-08-31"
UEBERGEBEN_AM = "2026-08-31T00:00:00+02:00"
GELESEN_AM = "2026-09-20T00:00:00+02:00"
ERZEUGT_AM = "2026-09-20T00:00:00+02:00"
NS = uuid.UUID("11111111-2222-4333-8444-555555555555")

ERZEUGT_VON = (
    "migriere_bc3_vorlage.py -- Fixture aus BC3s Formatvorlage vom 31.08.2026, "
    "KEINE BC2-Lieferung. Texte uebernommen, Zahlen nach ADR-006 BC2 hergeleitet."
)

# --- ADR-006 BC2 ----------------------------------------------------------------------------
MISCHSATZ_EUR_H = 43.0        # NoroAI-Profil Kap. 9.2: 750.000 EUR / 2.200 PT (#172)
BAUSATZ_EUR_PT = 800.0        # Marktkonditionen beim CoE, bewusst ein anderer Satz
BANDBREITE = {"gemessen": 0.10, "aus_system": 0.15, "geschaetzt": 0.40}
KORRIDOR = {
    "Regelwerk/Weiterleitung": (70, 90),
    "Integration": (60, 85),
    "Extraktion": (50, 75),
    "Textgenerierung": (30, 50),
    "Assistenz": (10, 30),
}
# BC3s vier Stufen auf 1-10. Die Mitte jeder Stufe, damit kein Rand bevorzugt wird.
STUFE_ZU_ZEHN = {"gering": 3, "mittel": 5, "hoch": 7, "sehr hoch": 9}


def kfm(x):
    """Kaufmaennisch runden (halbe Werte aufwaerts).

    Nicht Pythons round(): das rundet halbe Werte zur geraden Zahl, und ADR-006 BC2 meint mit
    "round" die gewohnte Regel. Bei den heutigen Zahlen faellt der Unterschied nicht an -- er
    faellt genau dann an, wenn jemand spaeter eine Schwelle verschiebt, und dann still.
    """
    return int(math.floor(x + 0.5))


def klasse_aus_text(titel, ansatz):
    """Loesungsansatz-Klasse aus dem Text der Vorlage.

    In der echten Lieferung verortet das LLM; hier entscheiden feste Stichworte in fester
    Reihenfolge, damit der Lauf reproduzierbar bleibt. Die erste Regel, die greift, gewinnt.
    """
    t = f"{titel} {ansatz}".lower()
    regeln = [
        ("Extraktion", ("extrahier", "extraktion", "erfassen", "lebenslauf", "ocr", "feldextraktion")),
        ("Integration", ("indexier", "integration", "abgleich", "medienbruch", "synchron", "api-")),
        ("Textgenerierung", ("beantworten", "antwort", "angebot", "entwurf", "generier", "formulier")),
        ("Regelwerk/Weiterleitung", ("weiterleit", "freigabe", "regelwerk", "buchung", "status")),
        ("Assistenz", ("vorschlag", "empfehl", "assistenz", "unterstuetz")),
    ]
    for klasse, stichworte in regeln:
        if any(s in t for s in stichworte):
            return klasse
    return "Assistenz"


def stundensatz_aus_annahmen(annahmen):
    """BC3s eigener Vollkostensatz, damit aus ihren Ist-Kosten die Jahresstunden ruecklesbar sind."""
    for a in annahmen:
        treffer = re.search(r"Vollkostensatz\s+([\d.,]+)\s*EUR/h", a)
        if treffer:
            return float(treffer.group(1).replace(",", "."))
    return 60.0


def spanne(mitte, breite):
    return {"min": round(mitte * (1 - breite), 2), "max": round(mitte * (1 + breite), 2)}


def impact_monetaer(einsparung_eur):
    """Absolute Euro-Schwellen, logarithmisch zwischen 1.000 und 50.000 EUR/Jahr (ADR-006 2.5)."""
    if einsparung_eur <= 0:
        return None
    roh = 1 + 9 * (math.log10(einsparung_eur) - 3) / (math.log10(50000) - 3)
    return max(1, min(10, kfm(roh)))


def nutzwert(potenzial, basis):
    """Fuenf Kategorien 1-10 mit je einem Begruendungssatz, ungewichtetes Mittel.

    In der echten Lieferung urteilt das LLM. Hier wird aus BC3s ordinalem `impact` eine Basis
    gebildet und an zwei Stellen nachgeschaerft, wo die Vorlage den Grund selbst nennt: ein
    DSGVO-Risiko hebt Compliance, ein Medienbruch hebt die Fehlerreduktion. Beides ist als
    Herleitung ausgewiesen, nicht als Urteil.
    """
    risikotext = " ".join(r["beschreibung"] + " " + r.get("gegenmassnahme", "") for r in potenzial.get("risiken", []))
    alles = (potenzial["beschreibung"] + " " + potenzial["to_be_vision"] + " " + risikotext).lower()

    compliance_grund = any(w in alles for w in ("dsgvo", "personenbezogen", "aufbewahrung", "protokoll"))
    fehler_grund = any(w in alles for w in ("medienbruch", "von hand", "manuell uebertrag", "excel"))

    werte = {
        "qualitaet": (
            basis,
            f"Aus BC3s ordinalem impact '{potenzial['impact']}' hergeleitet; die Vorlage nennt keine eigene Qualitaetsaussage.",
        ),
        "durchlaufzeit": (
            min(10, basis + 1),
            "Die to_be_vision der Vorlage beziffert durchgaengig eine kuerzere Bearbeitung als heute.",
        ),
        "fehlerreduktion": (
            min(10, basis + 1) if fehler_grund else basis,
            "Die Vorlage nennt einen Medienbruch oder eine Handuebertragung als Fehlerquelle."
            if fehler_grund
            else "Kein eigener Fehlerhinweis in der Vorlage; auf der Basis belassen.",
        ),
        "mitarbeiterzufriedenheit": (
            basis,
            "Ohne eigene Aussage in der Vorlage auf der Basis belassen.",
        ),
        "compliance": (
            min(10, basis + 2) if compliance_grund else max(1, basis - 2),
            "Die Vorlage fuehrt ein DSGVO- oder Aufbewahrungsthema ausdruecklich."
            if compliance_grund
            else "Die Vorlage nennt kein Compliance-Thema; bewusst abgesenkt statt unter 'Qualitaet' verschwinden zu lassen.",
        ),
    }
    ergebnis = {k: {"wert": w, "begruendung": b} for k, (w, b) in werte.items()}
    ergebnis["mittel"] = round(sum(v["wert"] for v in ergebnis.values()) / 5, 1)
    return ergebnis


def messverfahren_zu(kriterium):
    """`messverfahren` fuellt BC2 (#186, 09.09.2026) -- BC3s Vorlage hat dafuer kein Feld.

    Abgeleitet aus dem, was das Kriterium selbst pruefbar macht.
    """
    k = kriterium.lower()
    if any(w in k for w in ("binnen", "minuten", "stunden", "sekunden")):
        return "Zeitstempelvergleich im Vorgangsprotokoll ueber eine Stichprobe von 50 Vorgaengen."
    if "protokoll" in k:
        return "Protokollauszug je Vorgang, gegen die geforderten Felder geprueft."
    if any(w in k for w in ("markiert", "status", "zugewiesen", "bleibt")):
        return "Statusfeld im Vorgang, Stichprobe von 50 Vorgaengen."
    if any(w in k for w in ("quelle", "angabe", "enthaelt", "liegt")):
        return "Inhaltliche Stichprobe von 50 Vorgaengen gegen die geforderten Angaben."
    return "Stichprobe von 50 Vorgaengen, je gegen das Kriterium geprueft."


def user_story(potenzial, kp_id):
    """SOPHIST-Schablone. Die Vorlage fuehrt keine -- BC2 verantwortet sie (#186).

    Der Nutzen wird als "damit gilt: <Satz>" angehaengt statt direkt nach "damit". Grund ist
    Grammatik, nicht Geschmack: "damit" ist eine unterordnende Konjunktion und verlangt das Verb
    am Satzende -- BC3s to_be_kurz sind aber fertige Hauptsaetze. Sie umzustellen hiesse, ihren
    Wortlaut zu veraendern; so bleiben sie unangetastet.
    """
    nutzen = potenzial["potenzielle_loesung"].get("to_be_kurz", "").strip()
    if not nutzen:
        nutzen = potenzial["to_be_vision"].split(".")[0].strip() + "."
    return (
        f"Als bearbeitende Person im Kernprozess {kp_id} moechte ich den Schritt "
        f"„{potenzial['titel']}“ automatisiert ausfuehren, damit gilt: {nutzen}"
    )


def hebe_potenzial(p, kp_id, quelle_datei):
    stundensatz = stundensatz_aus_annahmen(p["value"].get("annahmen", []))
    stunden_jahr = round(p["value"]["ist_kosten_eur_jahr"] / stundensatz, 1)

    # BC3s Annahmen sagen durchgaengig "Annahme, nicht erhoben" / "nicht gemessen".
    herkunft = "geschaetzt"
    breite = BANDBREITE[herkunft]

    klasse = klasse_aus_text(p["titel"], p["potenzielle_loesung"]["ansatz"])
    grad_min, grad_max = KORRIDOR[klasse]

    ist_mitte = stunden_jahr * MISCHSATZ_EUR_H
    # Eckenrechnung: unteres Ende der Dauer x unteres Ende des Korridors, oberes x oberes.
    ist = spanne(ist_mitte, breite)
    einsparung = {
        "min": round(ist["min"] * grad_min / 100, 2),
        "max": round(ist["max"] * grad_max / 100, 2),
    }
    investition = round(p["aufwand_schaetzung_pt"] * BAUSATZ_EUR_PT, 2)
    amort = {
        "min": round(investition / (einsparung["max"] / 12), 1) if einsparung["max"] else 0.0,
        "max": round(investition / (einsparung["min"] / 12), 1) if einsparung["min"] else 0.0,
    }

    basis = STUFE_ZU_ZEHN[p["impact"]]
    nw = nutzwert(p, basis)
    einsparung_mitte = (einsparung["min"] + einsparung["max"]) / 2
    im = impact_monetaer(einsparung_mitte)
    impact = kfm(((im if im is not None else nw["mittel"]) + nw["mittel"]) / 2)
    komplexitaet = STUFE_ZU_ZEHN[p["umsetzungskomplexitaet"]]
    score = impact * (11 - komplexitaet)

    if impact >= 6:
        kategorie = "Quick Win" if komplexitaet <= 5 else "Strategisch"
    else:
        kategorie = "Optional" if komplexitaet <= 5 else "Zurueckgestellt"
    gruppe = "PRIO 1" if score >= 50 else ("PRIO 2" if score >= 20 else "PRIO 3")

    hinweise = [
        {
            "art": "mischsatz_untertreibt",
            "text": (
                f"BC3s Vorlage rechnet mit {stundensatz:.0f} EUR/h, v3.0 mit dem Mischsatz "
                f"{MISCHSATZ_EUR_H:.0f} EUR/h (#172). Die absoluten Betraege liegen damit niedriger "
                "als in der Vorlage; fuer die Rangfolge ist ein konstanter Faktor gleichwertig."
            ),
        },
        {
            "art": "testdaten",
            "text": (
                f"Fixture aus {quelle_datei} (BC3s Vorlage vom 31.08.2026). Die Zahlen sind gesetzt, "
                "nicht erhoben -- Gate 0 war fuer diesen Teilprozess nicht durchlaufen."
            ),
        },
    ]

    return {
        "potenzial_id": p["potenzial_id"],
        "titel": p["titel"],
        "potenzialrang": 0,  # wird nach dem Sortieren ueber den ganzen Lauf gesetzt
        "prioritaetsgruppe": gruppe,
        "beschreibung": p["beschreibung"],
        "to_be_vision": p["to_be_vision"],
        "user_story": user_story(p, kp_id),
        "akzeptanzkriterien_geschaeftlich": [
            {"kriterium": k, "messverfahren": messverfahren_zu(k)}
            for k in p["akzeptanzkriterien_geschaeftlich"]
        ],
        "fachliche_anforderungen": p["fachliche_anforderungen"],
        "betroffene_teilprozess_ids": p["betroffene_teilprozess_ids"],
        "betroffene_prozessschritte": p["betroffene_prozessschritte"],
        "betroffene_systeme": p["betroffene_systeme"],
        "manueller_aufwand_heute": {
            "stunden_jahr": stunden_jahr,
            "herkunft": herkunft,
            "konfidenz_pct": None,
        },
        "automatisierungsgrad": {
            "klasse": klasse,
            "angesetzt_min_pct": grad_min,
            "angesetzt_max_pct": grad_max,
            "begruendung": (
                f"Klasse '{klasse}' aus dem Loesungsansatz der Vorlage abgeleitet. Der Korridor wird "
                "ungeschmaelert uebernommen, weil keine LLM-Verortung vorliegt -- in der echten "
                "Lieferung engt das LLM ihn ein und begruendet die Lage."
            ),
            "bc1_schaetzung_pct": None,
        },
        "nutzwert": nw,
        "impact": impact,
        "impact_monetaer": im,
        "umsetzungskomplexitaet": komplexitaet,
        "komplexitaet_herkunft": "geurteilt",
        "komplexitaet_begruendung": (
            f"BC3s ordinale Stufe '{p['umsetzungskomplexitaet']}' auf die Stufenmitte {komplexitaet} "
            "abgebildet. BC1s vier Skalen am Fokus-Schritt liegen fuer diese Fixture nicht vor, "
            "die Herkunft ist deshalb 'geurteilt' statt 'gemessen'."
        ),
        "value": {
            "value_quelle": "annahme",
            "ist_kosten_eur_jahr": ist,
            "einsparung_eur_jahr": einsparung,
            "ersparnis_prozent": {"min": float(grad_min), "max": float(grad_max)},
            "investition_eur_richtwert": investition,
            "amortisation_monate": amort,
            "annahmen": [
                "FIXTURE -- hergeleitet aus BC3s Formatvorlage vom 31.08.2026, keine BC2-Lieferung.",
                f"Jahresstunden {stunden_jahr} aus BC3s ist_kosten_eur_jahr / {stundensatz:.0f} EUR/h zurueckgerechnet.",
                f"Mischsatz {MISCHSATZ_EUR_H:.0f} EUR/h (NoroAI-Profil Kap. 9.2, #172).",
                f"Bausatz {BAUSATZ_EUR_PT:.0f} EUR/PT -- Setzung, bewusst ein anderer Satz als die Einsparungsseite.",
                f"Automatisierungsgrad {grad_min}-{grad_max} % aus dem Korridor der Klasse '{klasse}' (ADR-006 BC2, 2.2).",
                f"Bandbreite +/-{int(breite * 100)} % aus der Herkunft '{herkunft}' (ADR-006 BC2, 2.3).",
            ],
        },
        "aufwand_schaetzung_pt": p["aufwand_schaetzung_pt"],
        "prioritaet_score": score,
        "kategorie": kategorie,
        "querschnitte": {
            "zukunftssicherheit": (
                "Nicht aus BC3s Vorlage uebernehmbar -- sie fuehrt keinen Querschnitt. Fuer die echte "
                "Lieferung urteilt das LLM; hier als Luecke ausgewiesen, statt sie zu erfinden."
            ),
            "abhaengigkeiten": [],
        },
        "potenzielle_loesung": p["potenzielle_loesung"],
        "voraussetzungen": p["voraussetzungen"],
        "risiken": p.get("risiken", []),
        "hinweise": hinweise,
    }


def main():
    dateien = sorted(QUELLE.glob("beispiel_*.json"))
    roh = [(f.name, json.loads(f.read_text(encoding="utf-8"))) for f in dateien]

    # Fund 1: nach Kernprozess gruppieren, nicht nach Datei. uc1 und uc3 sind beide KP-06.
    nach_kp = {}
    for name, d in roh:
        nach_kp.setdefault(d["kontext"]["kp_id"], []).append((name, d))

    konzepte = []
    for kp_id in sorted(nach_kp):
        teile = nach_kp[kp_id]
        konzept_id = str(uuid.uuid5(NS, f"{PAKET_ID}/{kp_id}/f1"))
        potenziale = [
            hebe_potenzial(p, kp_id, name) for name, d in teile for p in d["potenziale"]
        ]
        potenziale.sort(key=lambda p: (-p["prioritaet_score"], -p["value"]["einsparung_eur_jahr"]["max"]))

        erste = teile[0][1]
        quellen = ", ".join(name for name, _ in teile)
        kurz = erste["kontext"]["prozess_kurzbeschreibung"]
        if len(teile) > 1:
            kurz = f"{kp_id}: zwei Use Cases derselben Kernprozess-Zuordnung ({quellen})."
        systeme = sorted({s for _, d in teile for s in d["kontext"].get("betroffene_systeme_landschaft", [])})
        schmerz = [s for _, d in teile for s in d["kontext"]["hauptschmerzpunkte"]]

        konzepte.append(
            {
                "konzept_id": konzept_id,
                "ersetzt_konzept_id": None,
                "schema_version": "3.0",
                "company_id": COMPANY_ID,
                "paket_id": PAKET_ID,
                "uebergeben_am": UEBERGEBEN_AM,
                "gelesen_am": GELESEN_AM,
                "fassung": 1,
                "erzeugt_am": ERZEUGT_AM,
                "erzeugt_von": ERZEUGT_VON,
                "kontext": {
                    "prozess_kurzbeschreibung": kurz[:280],
                    "kp_id": kp_id,
                    "unternehmen": erste["kontext"].get("unternehmen", "NoroAI Consulting GmbH"),
                    "betroffene_systeme_landschaft": systeme,
                    "hauptschmerzpunkte": schmerz,
                },
                "potenziale": potenziale,
                "gesamtempfehlung": {
                    "reihenfolge_potenzial_ids": [p["potenzial_id"] for p in potenziale],
                    "begruendung": (
                        "Reihenfolge strikt nach Score. Fachliche Abhaengigkeiten stehen seit v3.0 in "
                        "potenziale[].querschnitte.abhaengigkeiten und nicht mehr hier im Freitext -- "
                        "BC3s Vorlage musste sie mangels Feld noch hierher schreiben."
                    ),
                },
                "eingangswerte": [
                    {
                        "groesse": "ist_kosten_eur_jahr",
                        "wert": p["value"]["ist_kosten_eur_jahr"]["max"],
                        "einheit": "EUR/Jahr",
                        "herkunft_tabelle": "bc3-engineering-architect/bc2-anforderung",
                        "herkunft_spalte": "potenziale[].value.ist_kosten_eur_jahr",
                        "herkunft_id": p["potenzial_id"],
                        "betrifft_teilprozess_id": p["betroffene_teilprozess_ids"][0],
                        "gelesen_am": GELESEN_AM,
                        "kennzeichnung": "Vorlage BC3 vom 31.08.2026 -- Annahme, nicht erhoben.",
                    }
                    for p in potenziale
                ],
            }
        )

    # Potenzialrang ueber den GANZEN Lauf, strikt nach Score.
    alle = [(k, p) for k in konzepte for p in k["potenziale"]]
    alle.sort(key=lambda kp: (-kp[1]["prioritaet_score"], -kp[1]["value"]["einsparung_eur_jahr"]["max"]))
    for i, (_, p) in enumerate(alle, start=1):
        p["potenzialrang"] = i

    eintraege = [
        {
            "potenzialrang": p["potenzialrang"],
            "prioritaetsgruppe": p["prioritaetsgruppe"],
            "potenzial_id": p["potenzial_id"],
            "konzept_id": k["konzept_id"],
            "titel": p["titel"],
            "kp_id": k["kontext"]["kp_id"],
            "betroffene_teilprozess_ids": p["betroffene_teilprozess_ids"],
            "kategorie": p["kategorie"],
            "impact": p["impact"],
            "impact_monetaer": p["impact_monetaer"],
            "nutzwert_mittel": p["nutzwert"]["mittel"],
            "umsetzungskomplexitaet": p["umsetzungskomplexitaet"],
            "komplexitaet_herkunft": p["komplexitaet_herkunft"],
            "score": p["prioritaet_score"],
            "aufwand_pt": p["aufwand_schaetzung_pt"],
            "einsparung_eur_jahr": p["value"]["einsparung_eur_jahr"],
            "investition_eur_richtwert": p["value"]["investition_eur_richtwert"],
            "amortisation_monate": p["value"]["amortisation_monate"],
        }
        for k, p in alle
    ]

    # Prozessrang: der Rang des BESTEN Potenzials des Kernprozesses (ADR-006 BC2, 2.7).
    bestes = {}
    for k, p in alle:
        kp = k["kontext"]["kp_id"]
        if kp not in bestes:
            bestes[kp] = (k, p, 0)
        kk, pp, n = bestes[kp]
        bestes[kp] = (kk, pp, n + 1)
    prozess_raenge = sorted(bestes.values(), key=lambda t: t[1]["potenzialrang"])
    prozess_raenge = [
        {
            "prozessrang": i,
            "kp_id": k["kontext"]["kp_id"],
            "konzept_id": k["konzept_id"],
            "bestes_potenzial_id": p["potenzial_id"],
            "bester_score": p["prioritaet_score"],
            "anzahl_potenziale": n,
            "begruendung": (
                f"Bestes Potenzial auf Rang {p['potenzialrang']} des Laufs. Der Prozessrang folgt dem "
                "besten Potenzial, nicht der Summe oder dem Mittel -- angefangen wird mit dem, was sich "
                "zuerst lohnt."
            ),
        }
        for i, (k, p, n) in enumerate(prozess_raenge, start=1)
    ]

    priorisierung = {
        "priorisierung_id": str(uuid.uuid5(NS, f"{PAKET_ID}/priorisierung/f1")),
        "schema_version": "3.0",
        "company_id": COMPANY_ID,
        "paket_id": PAKET_ID,
        "uebergeben_am": UEBERGEBEN_AM,
        "gelesen_am": GELESEN_AM,
        "fassung": 1,
        "erzeugt_am": ERZEUGT_AM,
        "score_formel": (
            "score = impact x (11 - umsetzungskomplexitaet), Bereich 1...100. "
            "impact = round((impact_monetaer + nutzwert) / 2); impact_monetaer aus absoluten "
            "Euro-Schwellen, logarithmisch zwischen 1.000 EUR/Jahr (1) und 50.000 EUR/Jahr (10). "
            "umsetzungskomplexitaet hier aus BC3s ordinaler Stufe, nicht aus BC1s vier Skalen. "
            "Die lineare Umkehrung ist bewusst gesetzt (ADR-006 BC2, 2.7)."
        ),
        "konzept_ids": [k["konzept_id"] for k in konzepte],
        "eintraege": eintraege,
        "prozess_raenge": prozess_raenge,
        "gate1": {
            "status": "pending",
            "kommentar": (
                "FIXTURE aus BC3s Formatvorlage vom 31.08.2026 -- keine BC2-Lieferung und nicht zur "
                "Freigabe bestimmt. Alle Zahlen sind hergeleitet (value_quelle 'annahme')."
            ),
        },
    }

    # Dateinamen: das Konzept auf Prozessrang 1 behaelt den historischen Namen
    # `mock_automatisierungskonzept.json`. BC3s README zeigt auf genau diesen Pfad
    # (bc3-engineering-architect/bc2-anforderung/README.md Z. 17) -- ihn umzubenennen hiesse,
    # einen fremden Verweis ins Leere laufen zu lassen. Die weiteren Konzepte haengen ihre
    # kp_id an.
    erster_kp = prozess_raenge[0]["kp_id"]
    ZIEL.mkdir(parents=True, exist_ok=True)
    for k in konzepte:
        kp = k["kontext"]["kp_id"]
        name = (
            "mock_automatisierungskonzept.json"
            if kp == erster_kp
            else f"mock_automatisierungskonzept_{kp}.json"
        )
        ziel = ZIEL / name
        ziel.write_text(json.dumps(k, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"geschrieben  {ziel.relative_to(BASE)}  ({kp}, {len(k['potenziale'])} Potenziale)")

    ziel = ZIEL / "mock_prozesspriorisierung.json"
    ziel.write_text(json.dumps(priorisierung, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"geschrieben  {ziel.relative_to(BASE)}  ({len(eintraege)} Eintraege, {len(prozess_raenge)} Prozesse)")

    schreibe_report(priorisierung, konzepte)
    print(f"\nHinweis: aus {len(roh)} Vorlagendateien wurden {len(konzepte)} Konzepte -- "
          "uc1 und uc3 tragen beide KP-06.")


def schreibe_report(priorisierung, konzepte):
    """Menschenlesbarer Value-Report. Fuehrt die Spannen als Spannen, nicht als Mittelwerte --
    ein Punktwert im Bericht waere genau die Scheingenauigkeit, gegen die v3.0 sie eingefuehrt hat.
    """
    def eur(x):
        return f"{x:,.0f} EUR".replace(",", ".")

    z = ["# BC2 -- Value-Report (Fixture aus BC3s Formatvorlage)\n"]
    z.append(
        f"**Lauf:** `{priorisierung['paket_id']}`, Fassung {priorisierung['fassung']} · "
        f"**Mandant:** NoroAI · **Stand:** {priorisierung['erzeugt_am']}\n"
    )
    z.append(
        "> **Keine BC2-Lieferung.** Hergeleitet aus BC3s Formatvorlage vom 31.08.2026, um zu zeigen, "
        "dass ihr Inhalt in den Vertrag v3.0 passt. Alle Zahlen tragen `value_quelle: \"annahme\"`.\n"
    )
    z.append("**Rechenmodell (ADR-006 · BC2, deterministisch, kein LLM):**\n")
    z.append(f"- Jahresstunden x {MISCHSATZ_EUR_H:.0f} EUR/h (Mischsatz) = Ist-Kosten")
    z.append("- Ist-Kosten x Automatisierungsgrad = Einsparung, als **Eckenrechnung** ueber beide Spannen")
    z.append(f"- Aufwand PT x {BAUSATZ_EUR_PT:.0f} EUR/PT (Bausatz) = Investition -- bewusst ein anderer Satz")
    z.append("- `score = impact x (11 - umsetzungskomplexitaet)`, `impact = round((impact_monetaer + nutzwert) / 2)`\n")

    z.append("| Rang | PRIO | KP | Potenzial | Ist-Kosten/Jahr | Einsparung/Jahr | Investition | Amortisation | Score | Kategorie |")
    z.append("|---|---|---|---|---|---|---|---|---|---|")
    konz = {k["konzept_id"]: k for k in konzepte}
    for e in priorisierung["eintraege"]:
        p = next(x for x in konz[e["konzept_id"]]["potenziale"] if x["potenzial_id"] == e["potenzial_id"])
        v = p["value"]
        z.append(
            f"| {e['potenzialrang']} | {e['prioritaetsgruppe']} | {e['kp_id']} | {e['titel']} | "
            f"{eur(v['ist_kosten_eur_jahr']['min'])} – {eur(v['ist_kosten_eur_jahr']['max'])} | "
            f"{eur(v['einsparung_eur_jahr']['min'])} – {eur(v['einsparung_eur_jahr']['max'])} | "
            f"{eur(v['investition_eur_richtwert'])} | "
            f"{v['amortisation_monate']['min']:.0f} – {v['amortisation_monate']['max']:.0f} Mon. | "
            f"{e['score']} | {e['kategorie']} |"
        )

    z.append("\n**Prozessrang** (der Rang des besten Potenzials, nicht Summe oder Mittel):\n")
    z.append("| Rang | KP | bester Score | Potenziale |")
    z.append("|---|---|---|---|")
    for pr in priorisierung["prozess_raenge"]:
        z.append(f"| {pr['prozessrang']} | {pr['kp_id']} | {pr['bester_score']} | {pr['anzahl_potenziale']} |")

    gruppen = {}
    for e in priorisierung["eintraege"]:
        gruppen[e["prioritaetsgruppe"]] = gruppen.get(e["prioritaetsgruppe"], 0) + 1
    z.append(
        "\n> **Kalibrierungsvorbehalt (#238).** Verteilung auf die Prioritaetsgruppen in diesem Lauf: "
        + ", ".join(f"{g} = {n}" for g, n in sorted(gruppen.items()))
        + ". Die Score-Baender sind gesetzt, nicht geprueft -- der Befund aus #167, dass mit "
        "plausiblen NoroAI-Groessen fast alles in einer Gruppe landet, reproduziert sich hier."
    )
    ziel = ZIEL / "mock_roi_report.md"
    ziel.write_text("\n".join(z) + "\n", encoding="utf-8")
    print(f"geschrieben  {ziel.relative_to(BASE)}")


if __name__ == "__main__":
    main()
