#!/usr/bin/env python3
"""
PROTOTYP zu Ticket #167 — Datensatz für den Frontend-Schnitt. **Wegwerfcode.**

Schreibt ``window.PROTOTYP_DATEN`` in ``index.html`` (zwischen die Marken
``DATEN-ANFANG``/``DATEN-ENDE``). Die Zahlen sind **erfunden, aber nach ADR-006
gerechnet** — der Prototyp soll über Bandbreiten, Impact und Score nicht etwas
anderes behaupten als das Modell.

Aufruf aus diesem Verzeichnis::

    python3 daten_bauen.py

Kein Datenbankzugriff, keine Persistenz (Prototyp-Regel 3). Die Eingangsgrößen
stehen unten in ``ROH`` und sind so gewählt, dass alle vier Kategorien, alle drei
Prioritätsgruppen und die drei Ausnahmefälle vorkommen, an denen die Oberfläche
sich beweisen muss: fehlende Dauer (keine Value-Zahl), fehlende Reifeskalen
(geurteilte Komplexität) und eine gerissene Plausibilitätsschranke.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# --- Setzungen aus ADR-006 ---------------------------------------------------

MISCHSATZ_EUR_H = 43.0          # Arbeitszeit des Mandanten (#172)
BAUSATZ_EUR_PT = 800.0          # Bau beim CoE, Marktkondition
KAPAZITAET_WARN_H = 7_040.0     # 880 PT intern
KAPAZITAET_HART_H = 17_600.0    # 2.200 PT brutto

# Korridore des Automatisierungsgrads je Lösungsansatz-Klasse (ADR-006, 2.2)
KORRIDOR = {
    "Regelwerk / Weiterleitung": (0.70, 0.90),
    "Integration": (0.60, 0.85),
    "Extraktion": (0.50, 0.75),
    "Textgenerierung": (0.30, 0.50),
    "Assistenz": (0.10, 0.30),
}

# Bandbreite je Herkunft der Dauer (ADR-006, 2.3). None = keine Value-Zahl.
BREITE = {"gemessen": 0.10, "aus_system": 0.15, "geschaetzt": 0.40, None: None}


def impact_monetaer(einsparung_eur: float) -> int:
    """Absolute Euro-Schwellen, logarithmisch 1.000 € (1) … 50.000 € (10)."""
    if einsparung_eur <= 0:
        return 1
    rohwert = 1 + 9 * (math.log10(einsparung_eur) - 3) / (math.log10(50_000) - 3)
    return max(1, min(10, round(rohwert)))


def kategorie(impact: int, komplexitaet: int) -> str:
    if impact >= 6:
        return "Quick Win" if komplexitaet <= 5 else "Strategisch"
    return "Optional" if komplexitaet <= 5 else "Zurückgestellt"


def prioritaetsgruppe(score: float) -> str:
    if score >= 50:
        return "PRIO 1"
    return "PRIO 2" if score >= 20 else "PRIO 3"


# --- Eingangsgrößen ----------------------------------------------------------
#
# ``dauer_min``/``frequenz`` stehen für BC1s ``total_duration_minutes`` und
# ``frequency_per_year``; ``herkunft`` für ``focus_step_duration_source``.
# ``reife`` sind BC1s vier 1-bis-5-Skalen (documentation_status,
# standardization_level, data_availability_score, stability_score);
# ``reife=None`` heißt: nicht geliefert, das LLM urteilt allein.

ROH = [
    {
        "id": "P-01", "kp": "KP-02", "tp": "KP-02.TP-1",
        "titel": "Lead-Erfassung und -Qualifizierung aus E-Mail-Anfragen ins CRM",
        "frequenz": 180, "dauer_min": 25, "herkunft": "geschaetzt", "konfidenz": 60,
        "klasse": "Extraktion", "lage": "Mitte",
        "lage_begruendung": "Anfragen kommen in freier Form; Firmenname und Bedarf sind meist "
                            "eindeutig, die Budgetangabe fast nie.",
        "aufwand_pt": 4, "reife": [4, 4, 3, 4],
        "nutzwert": {"Qualität": 7, "Durchlaufzeit": 8, "Fehlerreduktion": 7,
                     "Mitarbeiterzufriedenheit": 6, "Compliance / Rechtssicherheit": 3},
        "loesung": "Eingangspostfach wird gelesen, Felder extrahiert, Lead im CRM angelegt; "
                   "Zweifelsfälle landen in einer Prüfliste.",
        "querschnitt": {
            "Zukunftssicherheit": "hoch — das Muster trägt auch für Partneranfragen",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,41 von 5",
            "Umsatzpotenzial": "schnellere Reaktion auf Anfragen, nicht bezifferbar",
        },
        "luecken": [],
    },
    {
        "id": "P-02", "kp": "KP-02", "tp": "KP-02.TP-3",
        "titel": "Angebotsentwurf aus Anfrage und Referenzprojekten erzeugen",
        "frequenz": 90, "dauer_min": 95, "herkunft": "aus_system", "konfidenz": None,
        "klasse": "Textgenerierung", "lage": "unteres Drittel",
        "lage_begruendung": "Der Entwurf spart das Schreiben, nicht das Kalkulieren und nicht "
                            "die Abstimmung mit dem Kunden.",
        "aufwand_pt": 9, "reife": [3, 3, 2, 3],
        "nutzwert": {"Qualität": 6, "Durchlaufzeit": 7, "Fehlerreduktion": 5,
                     "Mitarbeiterzufriedenheit": 7, "Compliance / Rechtssicherheit": 2},
        "loesung": "Aus Anfrage und drei ähnlichsten Referenzprojekten einen Angebotsentwurf "
                   "bauen, den die Beratung überarbeitet.",
        "querschnitt": {
            "Zukunftssicherheit": "mittel — hängt an der Pflege der Referenzsammlung",
            "Abhängigkeiten": "setzt P-01 voraus (Anfrage strukturiert im CRM)",
            "Reifegrad des Prozesses": "3,41 von 5",
            "Umsatzpotenzial": "höhere Angebotsquote denkbar, nicht erhoben",
        },
        "luecken": ["Referenzprojekte liegen unstrukturiert als Dateien, nicht in der Datenbank."],
    },
    {
        "id": "P-03", "kp": "KP-03", "tp": "KP-03.TP-4",
        "titel": "AVV- und DSGVO-Abwicklung im Onboarding medienbruchfrei machen",
        "frequenz": 40, "dauer_min": 70, "herkunft": "gemessen", "konfidenz": None,
        "klasse": "Integration", "lage": "Mitte",
        "lage_begruendung": "Der dokumentierte Medienbruch (Unterschrift auf Papier) lässt sich "
                            "vollständig schließen; die inhaltliche Prüfung bleibt beim Menschen.",
        "aufwand_pt": 5, "reife": [4, 4, 4, 3],
        "nutzwert": {"Qualität": 6, "Durchlaufzeit": 6, "Fehlerreduktion": 7,
                     "Mitarbeiterzufriedenheit": 4, "Compliance / Rechtssicherheit": 10},
        "loesung": "AVV aus Vorlage erzeugen, elektronisch zeichnen lassen, Fristen und Nachweise "
                   "revisionssicher ablegen.",
        "querschnitt": {
            "Zukunftssicherheit": "hoch — Nachweispflicht bleibt",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,77 von 5",
            "Umsatzpotenzial": "keines",
        },
        "luecken": [],
    },
    {
        "id": "P-04", "kp": "KP-03", "tp": "KP-03.TP-2",
        "titel": "Onboarding-Checkliste und Fristen automatisch nachhalten",
        "frequenz": 40, "dauer_min": None, "herkunft": None, "konfidenz": None,
        "klasse": "Regelwerk / Weiterleitung", "lage": "oberes Drittel",
        "lage_begruendung": "Reine Fristenlogik, keine Textdeutung.",
        "aufwand_pt": 3, "reife": [3, 4, 3, 3],
        "nutzwert": {"Qualität": 5, "Durchlaufzeit": 7, "Fehlerreduktion": 6,
                     "Mitarbeiterzufriedenheit": 6, "Compliance / Rechtssicherheit": 7},
        "loesung": "Checkliste je Neukunde erzeugen, Fristen überwachen, Erinnerungen versenden.",
        "querschnitt": {
            "Zukunftssicherheit": "hoch",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,77 von 5",
            "Umsatzpotenzial": "keines",
        },
        "luecken": ["Keine Dauer erhoben (`focus_step_duration_source` ist NULL) — deshalb "
                    "**keine** Value-Zahl, nicht eine sehr breite."],
    },
    {
        "id": "P-05", "kp": "KP-04", "tp": "KP-04.TP-2",
        "titel": "Sprint-Retrospektive und Lessons Learned automatisch verdichten",
        "frequenz": 26, "dauer_min": 120, "herkunft": "geschaetzt", "konfidenz": 50,
        "klasse": "Textgenerierung", "lage": "Mitte",
        "lage_begruendung": "Verdichten geht, das Bewerten der Erkenntnisse bleibt beim Team.",
        "aufwand_pt": 6, "reife": [4, 3, 3, 4],
        "nutzwert": {"Qualität": 7, "Durchlaufzeit": 5, "Fehlerreduktion": 4,
                     "Mitarbeiterzufriedenheit": 8, "Compliance / Rechtssicherheit": 2},
        "loesung": "Aus Tickets, Zeiterfassung und Notizen eine Vorlage für die Retrospektive "
                   "bauen; das Team ergänzt und beschließt.",
        "querschnitt": {
            "Zukunftssicherheit": "mittel",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,52 von 5",
            "Umsatzpotenzial": "keines",
        },
        "luecken": ["Dauer geschätzt bei 50 % Konfidenz — die niedrigste im Paket."],
    },
    {
        "id": "P-06", "kp": "KP-04", "tp": "KP-04.TP-5",
        "titel": "Projektstatusbericht aus Zeiterfassung und Tickets zusammenstellen",
        "frequenz": 260, "dauer_min": 20, "herkunft": "aus_system", "konfidenz": None,
        "klasse": "Integration", "lage": "Mitte",
        "lage_begruendung": "Zwei Systeme verbinden und rechnen; der Kommentar an den Kunden "
                            "bleibt Handarbeit.",
        "aufwand_pt": 7, "reife": [3, 4, 4, 4],
        "nutzwert": {"Qualität": 6, "Durchlaufzeit": 8, "Fehlerreduktion": 6,
                     "Mitarbeiterzufriedenheit": 7, "Compliance / Rechtssicherheit": 2},
        "loesung": "Bericht je Projekt und Woche erzeugen, Abweichungen markieren, Versand nach "
                   "Freigabe durch die Projektleitung.",
        "querschnitt": {
            "Zukunftssicherheit": "hoch",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,52 von 5",
            "Umsatzpotenzial": "keines",
        },
        "luecken": [],
    },
    {
        "id": "P-10", "kp": "KP-04", "tp": "KP-04.TP-3",
        "titel": "Rechnungsstellung aus Zeiterfassung und Projektvertrag erzeugen",
        "frequenz": 480, "dauer_min": 35, "herkunft": "gemessen", "konfidenz": None,
        "klasse": "Regelwerk / Weiterleitung", "lage": "oberes Drittel",
        "lage_begruendung": "Der Ablauf ist vollständig geregelt: Stunden × Satz nach Vertrag. "
                            "Nur Sonderabsprachen brauchen einen Menschen.",
        "aufwand_pt": 5, "reife": [5, 5, 4, 4],
        "nutzwert": {"Qualität": 6, "Durchlaufzeit": 7, "Fehlerreduktion": 8,
                     "Mitarbeiterzufriedenheit": 6, "Compliance / Rechtssicherheit": 6},
        "loesung": "Aus Zeiterfassung und Projektvertrag den Rechnungsentwurf erzeugen und zur "
                   "Freigabe vorlegen.",
        "querschnitt": {
            "Zukunftssicherheit": "hoch — der Ablauf ändert sich nicht",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,52 von 5",
            "Umsatzpotenzial": "kürzere Zahlungsziele denkbar, nicht bezifferbar",
        },
        "luecken": [],
    },
    {
        "id": "P-11", "kp": "KP-06", "tp": "KP-06.TP-5",
        "titel": "Fahrtenbuch-Nachweise auf Vollständigkeit prüfen",
        "frequenz": 12, "dauer_min": 45, "herkunft": "geschaetzt", "konfidenz": 50,
        "klasse": "Assistenz", "lage": "Mitte",
        "lage_begruendung": "Jeder Fall wird vom Menschen entschieden; die Lösung schlägt nur vor.",
        "aufwand_pt": 6, "reife": [2, 2, 2, 2],
        "nutzwert": {"Qualität": 4, "Durchlaufzeit": 3, "Fehlerreduktion": 4,
                     "Mitarbeiterzufriedenheit": 3, "Compliance / Rechtssicherheit": 5},
        "loesung": "Vorschlagsliste unvollständiger Nachweise erzeugen; Prüfung bleibt manuell.",
        "querschnitt": {
            "Zukunftssicherheit": "niedrig — entfällt bei Umstellung auf Poolfahrzeuge",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,10 von 5",
            "Umsatzpotenzial": "keines",
        },
        "luecken": ["Zwölf Fälle im Jahr — die Bandbreite ist breiter als der Betrag selbst."],
    },
    {
        "id": "P-07", "kp": "KP-06", "tp": "KP-06.TP-2",
        "titel": "Reise- und Einsatzplanung: Verfügbarkeiten und Buchungen abgleichen",
        "frequenz": 180, "dauer_min": 180, "herkunft": "geschaetzt", "konfidenz": 60,
        "klasse": "Integration", "lage": "Mitte",
        "lage_begruendung": "Der Abgleich ist mechanisch; die Zusage an den Kunden und die "
                            "Rücksicht auf persönliche Umstände nicht.",
        "aufwand_pt": 12, "reife": [2, 2, 2, 3],
        "nutzwert": {"Qualität": 7, "Durchlaufzeit": 9, "Fehlerreduktion": 6,
                     "Mitarbeiterzufriedenheit": 8, "Compliance / Rechtssicherheit": 3},
        "loesung": "Verfügbarkeiten, Einsatzorte und Buchungen in einer Sicht zusammenführen und "
                   "Konflikte vorab melden.",
        "bc1_automationsgrad_pct": 30,
        "querschnitt": {
            "Zukunftssicherheit": "hoch — trägt beide Lesarten des Prozesses",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,10 von 5",
            "Umsatzpotenzial": "mehr abrechenbare Tage denkbar, nicht bezifferbar",
        },
        "luecken": ["**Fachliche Lesart offen** (Nebel der Karte): interne Einsatzplanung für zehn "
                    "Mitarbeitende oder Reisebuchung für Kunden — Fallzahl und Systeme "
                    "unterscheiden sich um Größenordnungen."],
    },
    {
        "id": "P-08", "kp": "KP-06", "tp": "KP-06.TP-4",
        "titel": "Spesen- und Belegerfassung aus Fotos",
        "frequenz": 1300, "dauer_min": 12, "herkunft": "geschaetzt", "konfidenz": 70,
        "klasse": "Extraktion", "lage": "Mitte",
        "lage_begruendung": "Belege sind vielgestaltig, die Felder aber wenige und feste.",
        "aufwand_pt": 8, "reife": None,
        "komplexitaet_geurteilt": 5,
        "komplexitaet_begruendung": "BC1 liefert für diesen Teilprozess keine Reifeskalen; "
                                    "geurteilt anhand von BC0s Technologiebasis und Toolstand.",
        "nutzwert": {"Qualität": 5, "Durchlaufzeit": 6, "Fehlerreduktion": 8,
                     "Mitarbeiterzufriedenheit": 7, "Compliance / Rechtssicherheit": 4},
        "loesung": "Foto hochladen, Felder extrahieren, Buchungsvorschlag erzeugen; Freigabe durch "
                   "die Buchhaltung.",
        "querschnitt": {
            "Zukunftssicherheit": "hoch",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,10 von 5",
            "Umsatzpotenzial": "keines",
        },
        "luecken": ["Reifeskalen fehlen — Umsetzungskomplexität ist **geurteilt**, nicht gemessen."],
    },
    {
        "id": "P-09", "kp": "KP-06", "tp": "KP-06.TP-1",
        "titel": "Reiseanfragen aus Portalen übernehmen",
        "frequenz": 2600, "dauer_min": 150, "herkunft": "geschaetzt", "konfidenz": 40,
        "klasse": "Integration", "lage": "Mitte",
        "lage_begruendung": "Schnittstelle je Portal, danach mechanisch.",
        "aufwand_pt": 10, "reife": [2, 2, 3, 2],
        "nutzwert": {"Qualität": 6, "Durchlaufzeit": 7, "Fehlerreduktion": 6,
                     "Mitarbeiterzufriedenheit": 6, "Compliance / Rechtssicherheit": 2},
        "loesung": "Anfragen aus den Portalen einlesen und als Vorgang anlegen.",
        "querschnitt": {
            "Zukunftssicherheit": "mittel — hängt an fremden Schnittstellen",
            "Abhängigkeiten": "keine",
            "Reifegrad des Prozesses": "3,10 von 5",
            "Umsatzpotenzial": "abhängig von der offenen Lesart des Prozesses",
        },
        "luecken": ["Dauer geschätzt bei 40 % Konfidenz.",
                    "Frequenz 2.600/Jahr bei zehn Mitarbeitenden — trägt die "
                    "Plausibilitätsschranke des Laufs."],
    },
]

KERNPROZESSE = {
    "KP-02": {
        "name": "Vertrieb & Akquise",
        "reifegrad": 3.41,
        "ausgangslage": "Anfragen erreichen NoroAI per E-Mail und über das Kontaktformular und "
                        "werden von Hand ins CRM übertragen. Angebote entstehen aus früheren "
                        "Angeboten durch Kopieren.",
        "systeme": ["Outlook", "HubSpot", "Word", "Netzlaufwerk"],
        "schmerzpunkte": ["Doppelerfassung zwischen Postfach und CRM",
                          "Angebotsqualität hängt an der Person"],
    },
    "KP-03": {
        "name": "Kunden-Onboarding",
        "reifegrad": 3.77,
        "ausgangslage": "Neukunden werden anhand einer Checkliste in Excel aufgenommen. AVV und "
                        "DSGVO-Unterlagen werden versendet, unterschrieben zurückerwartet und "
                        "abgelegt — teils auf Papier.",
        "systeme": ["Excel", "Outlook", "DocuSign (punktuell)", "Netzlaufwerk"],
        "schmerzpunkte": ["Dokumentierter Medienbruch: AVV-Unterzeichnung kann Papier sein",
                          "Fristen werden nicht systematisch nachgehalten"],
    },
    "KP-04": {
        "name": "Projektdurchführung",
        "reifegrad": 3.52,
        "ausgangslage": "Projekte laufen über Jira und eine eigene Zeiterfassung. Statusberichte "
                        "und Retrospektiven werden je Projektleitung unterschiedlich geführt.",
        "systeme": ["Jira", "Zeiterfassung (eigenentwickelt)", "Confluence", "Excel"],
        "schmerzpunkte": ["Statusberichte kosten wöchentlich Zeit und sehen überall anders aus",
                          "Erkenntnisse aus Retrospektiven versanden"],
    },
    "KP-06": {
        "name": "Ressourcen- & Einsatzplanung",
        "reifegrad": 3.10,
        "ausgangslage": "Einsätze, Reisen und Verfügbarkeiten werden in einer Tabelle geplant und "
                        "per Absprache abgeglichen. Belege werden gesammelt und monatlich erfasst.",
        "systeme": ["Excel", "Outlook-Kalender", "Reiseportale", "DATEV (nachgelagert)"],
        "schmerzpunkte": ["Konflikte fallen erst am Einsatztag auf",
                          "Belegerfassung staut sich zum Monatsende"],
    },
}


def herkunftsnachweise(r: dict) -> list[dict]:
    """Was in die Zahl eingegangen ist — mit Herkunft, Wert, Einheit (ADR-006, 2.9)."""
    nachweise = [
        {"quelle": "bc1.prozessprofil.frequency_per_year", "wert": r["frequenz"],
         "einheit": "Durchläufe/Jahr", "bezug": r["tp"]},
    ]
    if r["dauer_min"] is not None:
        nachweise.append({"quelle": "bc1.prozessprofil.total_duration_minutes",
                          "wert": r["dauer_min"], "einheit": "Minuten/Durchlauf", "bezug": r["tp"]})
        nachweise.append({"quelle": "bc1.prozessprofil.focus_step_duration_source",
                          "wert": r["herkunft"], "einheit": "—", "bezug": r["tp"]})
    else:
        nachweise.append({"quelle": "bc1.prozessprofil.total_duration_minutes",
                          "wert": None, "einheit": "Minuten/Durchlauf", "bezug": r["tp"]})
    if r.get("konfidenz") is not None:
        nachweise.append({"quelle": "bc1.prozessprofil.focus_step_duration_confidence_pct",
                          "wert": r["konfidenz"], "einheit": "%", "bezug": r["tp"]})
    if r.get("reife"):
        for spalte, wert in zip(
            ["documentation_status", "standardization_level",
             "data_availability_score", "stability_score"], r["reife"]
        ):
            nachweise.append({"quelle": f"bc1.prozessprofil.{spalte}", "wert": wert,
                              "einheit": "1–5", "bezug": r["tp"]})
    if r.get("bc1_automationsgrad_pct") is not None:
        nachweise.append({"quelle": "bc1.prozessprofil.automation_potential_estimate_pct",
                          "wert": r["bc1_automationsgrad_pct"], "einheit": "%",
                          "bezug": r["tp"] + " (Plausibilitätsprobe, kein Vorrang)"})
    nachweise.append({"quelle": "Setzung ADR-006 · Mischsatz", "wert": MISCHSATZ_EUR_H,
                      "einheit": "EUR/h", "bezug": "NoroAI-Profil Kap. 9.2"})
    nachweise.append({"quelle": "Setzung ADR-006 · Bausatz", "wert": BAUSATZ_EUR_PT,
                      "einheit": "EUR/PT", "bezug": "Marktkondition CoE"})
    return nachweise


def rechne(r: dict) -> dict:
    """Ein Potenzial nach ADR-006 durchrechnen. Jede Setzung reist mit."""
    p: dict = {
        "id": r["id"], "kp_id": r["kp"], "tp_id": r["tp"], "titel": r["titel"],
        "loesungsansatz": r["loesung"], "klasse": r["klasse"],
        "korridor_pct": [int(KORRIDOR[r["klasse"]][0] * 100), int(KORRIDOR[r["klasse"]][1] * 100)],
        "lage_im_korridor": r["lage"], "lage_begruendung": r["lage_begruendung"],
        "aufwand_pt": r["aufwand_pt"], "herkunft_dauer": r["herkunft"],
        "konfidenz_pct": r.get("konfidenz"),
        "nutzwert_kategorien": r["nutzwert"], "querschnitt": r["querschnitt"],
        "datenluecken": list(r["luecken"]), "herkunftsnachweise": herkunftsnachweise(r),
        "bc1_automationsgrad_pct": r.get("bc1_automationsgrad_pct"),
        "offene_modellfragen": [],
    }

    # --- Nutzwert: ungewichtetes Mittel aus fünf Kategorien, je 1–10 ---
    nutzwert = sum(r["nutzwert"].values()) / len(r["nutzwert"])
    p["nutzwert"] = round(nutzwert, 1)

    # --- Umsetzungskomplexität: gemessen, sonst geurteilt ---
    if r.get("reife"):
        reife = sum(r["reife"]) / len(r["reife"])
        p["reife"] = round(reife, 2)
        p["komplexitaet"] = round(11 - 2 * reife)
        p["komplexitaet_herkunft"] = "gemessen"
        p["komplexitaet_begruendung"] = (
            f"Mittel aus BC1s vier Skalen ({'/'.join(map(str, r['reife']))}) = {reife:.2f}; "
            f"komplexitaet = round(11 − 2 × {reife:.2f})."
        )
    else:
        p["reife"] = None
        p["komplexitaet"] = r["komplexitaet_geurteilt"]
        p["komplexitaet_herkunft"] = "geurteilt"
        p["komplexitaet_begruendung"] = r["komplexitaet_begruendung"]

    # --- Value: Eckenrechnung über Dauer-Bandbreite × Korridor ---
    breite = BREITE[r["herkunft"]]
    if breite is None:
        p["value"] = None
        p["value_hinweis"] = ("Keine Value-Zahl: die Dauer ist nicht erhoben. Eine Spanne von "
                              "±100 % wäre keine Aussage mehr (ADR-006, 2.3).")
        # Offene Modellfrage: ADR-006 setzt impact = Mittel aus zwei Teil-Scores.
        # Fällt der monetäre weg, ist nicht festgelegt, was an seine Stelle tritt.
        p["impact_monetaer"] = None
        p["impact"] = round(nutzwert)
        p["impact_herleitung"] = (f"Nur Nutzwert ({nutzwert:.1f}) — der monetäre Teil-Score "
                                  f"entfällt.")
        p["offene_modellfragen"].append(
            "ADR-006 legt nicht fest, wie `impact` entsteht, wenn es keine Value-Zahl gibt. "
            "Der Prototyp nimmt den Nutzwert allein; `impact_monetaer = 1` wäre die Alternative "
            "und ergäbe hier 3 statt 6 — ein Unterschied von zwei Prioritätsgruppen."
        )
    else:
        dauer_lo, dauer_hi = r["dauer_min"] * (1 - breite), r["dauer_min"] * (1 + breite)
        korr_lo, korr_hi = KORRIDOR[r["klasse"]]
        stunden_lo = r["frequenz"] * dauer_lo / 60
        stunden_hi = r["frequenz"] * dauer_hi / 60
        stunden_mitte = r["frequenz"] * r["dauer_min"] / 60
        einsparung_lo = stunden_lo * MISCHSATZ_EUR_H * korr_lo
        einsparung_hi = stunden_hi * MISCHSATZ_EUR_H * korr_hi
        einsparung_mitte = (einsparung_lo + einsparung_hi) / 2
        investition = r["aufwand_pt"] * BAUSATZ_EUR_PT
        p["value"] = {
            "jahresstunden_mitte": round(stunden_mitte, 1),
            "jahresstunden_spanne": [round(stunden_lo, 1), round(stunden_hi, 1)],
            "ist_kosten_mitte": round(stunden_mitte * MISCHSATZ_EUR_H),
            "einsparung_spanne": [round(einsparung_lo), round(einsparung_hi)],
            "einsparung_mitte": round(einsparung_mitte),
            "investition": round(investition),
            "amortisation_monate": round(investition / (einsparung_mitte / 12), 1),
            "breite_pct": int(breite * 100),
        }
        p["value_hinweis"] = (
            f"Eckenrechnung: unteres Ende der Dauer (−{int(breite*100)} %) × unteres Ende des "
            f"Korridors ({int(korr_lo*100)} %), oberes × oberes. Bewusst pessimistisch — sie "
            f"unterstellt, dass beide Fehler gleichsinnig auftreten."
        )
        p["impact_monetaer"] = impact_monetaer(einsparung_mitte)
        p["impact"] = round((p["impact_monetaer"] + nutzwert) / 2)
        p["impact_herleitung"] = (f"round(({p['impact_monetaer']} + {nutzwert:.1f}) / 2) — "
                                  f"monetärer Teil-Score aus der Mitte der Einsparungsspanne.")
        p["offene_modellfragen"].append(
            "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, "
            "welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; "
            "das untere Ende wäre die vorsichtigere Lesart."
        )
        if r.get("bc1_automationsgrad_pct") is not None:
            if not (korr_lo * 100 <= r["bc1_automationsgrad_pct"] <= korr_hi * 100):
                p["datenluecken"].append(
                    f"BC1 schätzt den Automatisierungsgrad auf {r['bc1_automationsgrad_pct']} %, "
                    f"der Korridor der Klasse „{r['klasse']}\" liegt bei "
                    f"{int(korr_lo*100)}–{int(korr_hi*100)} %. Abweichung — Plausibilitätsprobe "
                    f"schlägt an (ADR-006, 2.2)."
                )

    # --- Score, Kategorie, Gruppe ---
    p["score"] = p["impact"] * (11 - p["komplexitaet"])
    p["kategorie"] = kategorie(p["impact"], p["komplexitaet"])
    p["gruppe"] = prioritaetsgruppe(p["score"])
    p["score_herleitung"] = f"{p['impact']} × (11 − {p['komplexitaet']}) = {p['score']}"

    # --- Vertragsfelder, die BC2 füllt (Feldschnitt vom 09.09.2026) ---
    p["user_story"] = (f"Als Mitarbeitende im Prozess „{KERNPROZESSE[r['kp']]['name']}\" möchte ich "
                       f"{r['titel'][0].lower() + r['titel'][1:]}, damit die Handarbeit entfällt "
                       f"und der Ablauf nachvollziehbar bleibt.")
    p["akzeptanzkriterien"] = [
        {"text": f"**Gegeben** der Ablauf „{KERNPROZESSE[r['kp']]['name']}\" läuft wie heute, "
                 f"**wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in "
                 f"{r['tp']} für den Regelfall.",
         "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt "
                          "als getroffen, wenn kein manueller Eingriff nötig war."},
        {"text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden "
                 "kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht "
                 "stillschweigend geraten.",
         "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."},
    ]
    return p


def baue() -> dict:
    potenziale = [rechne(r) for r in ROH]
    potenziale.sort(key=lambda p: (-p["score"], p["id"]))
    for rang, p in enumerate(potenziale, start=1):
        p["rang"] = rang

    # Prozessrang: der Rang des besten Potenzials (ADR-006, 2.7)
    konzepte = []
    for kp_id, kp in KERNPROZESSE.items():
        eigene = [p for p in potenziale if p["kp_id"] == kp_id]
        konzepte.append({
            "kp_id": kp_id, "name": kp["name"], "reifegrad": kp["reifegrad"],
            "ausgangslage": kp["ausgangslage"], "systeme": kp["systeme"],
            "schmerzpunkte": kp["schmerzpunkte"],
            "potenzial_ids": [p["id"] for p in eigene],
            "bester_rang": min(p["rang"] for p in eigene),
        })
    konzepte.sort(key=lambda k: k["bester_rang"])
    for rang, k in enumerate(konzepte, start=1):
        k["prozessrang"] = rang

    # Plausibilitätsschranke I3 auf Lauf-Ebene
    stunden_gesamt = sum(p["value"]["jahresstunden_mitte"] for p in potenziale if p["value"])
    schranke = {
        "jahresstunden_gesamt": round(stunden_gesamt, 1),
        "warnschwelle_h": KAPAZITAET_WARN_H,
        "harte_grenze_h": KAPAZITAET_HART_H,
        "gerissen": stunden_gesamt > KAPAZITAET_WARN_H,
        "text": None,
    }
    if schranke["gerissen"]:
        # Tausendertrennung deutsch — nur auf den Zahlen, nicht auf dem Satz:
        # ein pauschales replace(",", ".") trifft auch die Satzkommata.
        de = lambda n: f"{n:,.0f}".replace(",", ".")
        schranke["text"] = (
            f"Die gerechneten Jahresstunden des Laufs ({de(stunden_gesamt)} h) übersteigen die "
            f"interne Kapazität von {de(KAPAZITAET_WARN_H)} h (880 PT). BC2 rechnet durch und "
            f"weist nichts zurück — die Prüfung ist formal, nicht fachlich. Die Plausibilität "
            f"liegt bei BC0/BC1."
        )

    return {
        "erzeugt_von": "PROTOTYP #167 · daten_bauen.py — erfundene Werte, nach ADR-006 gerechnet",
        "laeufe": [
            {
                "paket_id": "9f3a1c72-4d18-4b2e-9c05-7a1e3b8c2f41",
                "paket_kurz": "9f3a1c72",
                "company_id": "7c2d5ee9-2a9a-5990-810f-502ea2b2012d",
                "mandant": "NoroAI Consulting GmbH",
                "uebergeben_am": "2026-09-18T09:14:00Z",
                "gelesen_am": "2026-09-18T09:14:37Z",
                "zustand": "offen",
                "fassung": 1,
                "teilprozesse": [p["tp_id"] for p in potenziale],
                "konzepte": konzepte,
                "potenziale": potenziale,
                "schranke": schranke,
            },
            {
                "paket_id": "3c81ba07-9f52-4a10-8d77-2b6e4c1a9de3",
                "paket_kurz": "3c81ba07",
                "company_id": "7c2d5ee9-2a9a-5990-810f-502ea2b2012d",
                "mandant": "NoroAI Consulting GmbH",
                "uebergeben_am": "2026-09-04T11:02:00Z",
                "gelesen_am": "2026-09-04T11:02:19Z",
                "zustand": "freigegeben",
                "fassung": 2,
                "teilprozesse": ["KP-02.TP-1", "KP-02.TP-3"],
                "konzepte": [], "potenziale": [], "schranke": None,
            },
            {
                "paket_id": "a4d09e15-6c3b-4f88-b210-5e9a7d2c4801",
                "paket_kurz": "a4d09e15",
                "company_id": "1a0f8b34-77c2-4e51-9d86-0b3f5c81ea62",
                "mandant": "Übungsmandant (zweite Firma in derselben Datenbank)",
                "uebergeben_am": "2026-09-04T08:31:00Z",
                "gelesen_am": None,
                "zustand": "offen",
                "fassung": 1,
                "teilprozesse": ["KP-01.TP-1"],
                "konzepte": [], "potenziale": [], "schranke": None,
            },
        ],
    }


def schreibe_in_seite(daten: dict, seite: Path) -> None:
    """Die Daten in ``index.html`` einbetten statt daneben zu legen.

    Eine benachbarte ``.js`` lädt Safari von ``file://`` nicht — jede lokale Datei
    gilt dort als eigene Herkunft. Eingebettet ist die Seite selbsttragend und der
    Doppelklick genügt in jedem Browser.
    """
    text = seite.read_text(encoding="utf-8")
    anfang, ende = "/* DATEN-ANFANG */", "/* DATEN-ENDE */"
    i, j = text.index(anfang), text.index(ende)
    block = (anfang + "\nwindow.PROTOTYP_DATEN = "
             + json.dumps(daten, ensure_ascii=False, indent=1)
             # ``</script>`` im Nutztext würde das Skript vorzeitig beenden.
             .replace("</", "<\\/")
             + ";\n")
    seite.write_text(text[:i] + block + text[j:], encoding="utf-8")


if __name__ == "__main__":
    daten = baue()
    ziel = Path(__file__).with_name("index.html")
    schreibe_in_seite(daten, ziel)
    lauf = daten["laeufe"][0]
    print(f"{ziel.name} neu geschrieben — {len(lauf['potenziale'])} Potenziale, "
          f"{len(lauf['konzepte'])} Konzepte.")
    for p in lauf["potenziale"]:
        val = f"{p['value']['einsparung_spanne'][0]:>6}–{p['value']['einsparung_spanne'][1]:<6} EUR" \
              if p["value"] else "  keine Value-Zahl  "
        print(f"  {p['rang']:>2}. {p['id']}  {p['gruppe']}  Score {p['score']:>3}  "
              f"I{p['impact']:>2} K{p['komplexitaet']:>2}  {val}  {p['kategorie']:<14} {p['titel'][:44]}")
    if lauf["schranke"]["gerissen"]:
        print(f"  ⚠ Plausibilitätsschranke: {lauf['schranke']['jahresstunden_gesamt']:.0f} h")
