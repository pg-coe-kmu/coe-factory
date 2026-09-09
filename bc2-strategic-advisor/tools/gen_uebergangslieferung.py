"""
Erzeugt die VORLAEUFIGE Uebergangslieferung an BC3 (Issue #168).

Zweck: BC3 und BC4 entblocken. BC3 kann Tickets gegen *echte* NoroAI-Prozesse
schneiden, ohne auf das fertige Value-Modell (#166) zu warten.

Grundlage sind die realen Prozessdaten aus dem BC0-Snapshot v3
(`bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json`),
nicht der frei erfundene v2-Mock (Krankentagegeld/Aurelia Krankenkasse).

WICHTIG -- was hier echt ist und was nicht:

  ECHT (aus dem Snapshot gelesen)      VORLAEUFIG (hier gesetzt, nicht erhoben)
  ---------------------------------    -----------------------------------------
  Kernprozesse KP-02/03/04             Fallzahlen pro Jahr
  Teilprozesse, Namen, Notation        Bearbeitungszeit pro Fall
  Tools, Medienbrueche, Schnittstellen Einsparungsgrad
  Reifegrad je Kriterium               Umsetzungsaufwand in Personentagen
  Stundensatz K3 (68 EUR/h, geschaetzt)

Die Datenbank fuehrt WEDER Fallzahlen NOCH Bearbeitungszeiten (siehe #159).
Die Value-Rechnung braucht beide. Jede Zahl in `value{}` ist deshalb gesetzt,
nicht gerechnet aus Erhobenem -- unabhaengig davon, ob Mock oder Datenbank die
Quelle ist. Genau deshalb ist die Lieferung als vorlaeufig markiert.

Die Rechnung selbst ist DETERMINISTISCH (kein LLM) -- Invariante aus
`bc2-strategic-advisor/CLAUDE.md`: das LLM bewertet qualitativ, rechnet aber nicht.

Aufruf aus dem Repo-Wurzelverzeichnis:
    python3 bc2-strategic-advisor/tools/gen_uebergangslieferung.py
"""
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[2]
SNAPSHOT = BASE / "bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json"
ZIEL = BASE / "contracts/bc2-to-bc3/lieferungen/2026-08-30-vorlaeufig"

# Fester Zeitstempel -- haelt die Ausgabe diff-stabil (wie gen_mocks.py).
NOW = "2026-08-30T00:00:00Z"
ERZEUGT_VON = "bc2-uebergangslieferung@2026-08-30 -- VORLAEUFIG, keine Bewertung"

# Marker, der die Kopierkette ueberlebt: er steht im Titel, und der Titel
# wandert woertlich in BC3s Tickets und von dort in BC4s Code.
MARKER = "[VORLAEUFIG]"

WARNUNG = (
    "VORLAEUFIG -- KEINE BEWERTUNG. Diese Zahl ist gesetzt, nicht erhoben. "
    "Fallzahl und Bearbeitungszeit fuehrt die gemeinsame Datenbank nicht (Issue #159); "
    "sie sind hier angenommen, um BC3 und BC4 zu entblocken. "
    "Nicht fuer Entscheidungen, Angebote oder Gate-1-Freigaben verwenden."
)

# --- Kalkulations-Annahmen -------------------------------------------------
# STUNDENSATZ ist der einzige Wert mit Beleg in der Datenbank: Kostensatz K3
# aus `rollen_kostensaetze`, gueltig ab 17.08.2026 -- Quelle dort aber
# ausdruecklich `geschaetzt`, nicht `belegt`.
STUNDENSATZ_EUR = 68.0          # K3 aus rollen_kostensaetze (geschaetzt)
STUNDEN_PRO_PT = 8.0
# NoroAI baut intern (n8n, EspoCRM, GitLab liegen vor) -- ein externer
# Tagessatz von 800 EUR bildet die Umsetzung eines 10-Personen-Beratungshauses
# nicht ab. Investition daher auf Basis eigener Personentage.
TAGESSATZ_EUR = STUNDENSATZ_EUR * STUNDEN_PRO_PT   # 544 EUR/PT

IMPACT_W = {"gering": 25, "mittel": 50, "hoch": 75, "sehr hoch": 100}
KOMPLEX_W = {"gering": 25, "mittel": 50, "hoch": 75, "sehr hoch": 100}

# Vorlaeufige IDs tragen ihre Herkunft im Praefix:
# acht fuehrende Nullen == vorlaeufiger Datensatz.
KONZEPT_ID = {
    "KP-02": "00000000-0000-4000-8000-000000000002",
    "KP-03": "00000000-0000-4000-8000-000000000003",
    "KP-04": "00000000-0000-4000-8000-000000000004",
}
POTENZIAL_ID = {
    "KP-02": "00000000-0000-4000-8000-00000000f001",
    "KP-03": "00000000-0000-4000-8000-00000000f002",
    "KP-04": "00000000-0000-4000-8000-00000000f003",
}
PRIORISIERUNG_ID = "00000000-0000-4000-8000-00000000f000"


def berechne_value(faelle_jahr, minuten_heute_pro_fall, einsparungsgrad, aufwand_pt, extra_annahmen):
    """Deterministische Value-Rechnung.

    `value_quelle` ist bewusst 'default', nicht 'berechnet': das Schema
    definiert 'default' als "Eingabedaten waren unvollstaendig, Fallback-Werte
    genutzt (Resilienz R-04)" -- genau der hier vorliegende Fall. Damit ist die
    Vorlaeufigkeit maschinenlesbar, ohne den Vertrag auf v2.1 heben zu muessen.
    """
    stunden_heute = faelle_jahr * minuten_heute_pro_fall / 60.0
    ist_kosten = stunden_heute * STUNDENSATZ_EUR
    einsparung = ist_kosten * einsparungsgrad
    investition = aufwand_pt * TAGESSATZ_EUR
    monatliche_einsparung = einsparung / 12.0
    amortisation = (investition / monatliche_einsparung) if monatliche_einsparung > 0 else 0.0
    return {
        "ist_kosten_eur_jahr": round(ist_kosten, 2),
        "einsparung_eur_jahr": round(einsparung, 2),
        "ersparnis_prozent": round(einsparungsgrad * 100, 1),
        "investition_eur_richtwert": round(investition, 2),
        "amortisation_monate": round(amortisation, 1),
        "value_quelle": "default",
        "annahmen": [
            WARNUNG,
            f"GESETZT -- Fallzahl: {faelle_jahr} Vorgaenge/Jahr ({extra_annahmen['frequenz_begruendung']})",
            f"GESETZT -- manuelle Zeit heute: {minuten_heute_pro_fall} Min/Fall",
            f"GESETZT -- angenommener Einsparungsgrad: {int(einsparungsgrad * 100)} %",
            f"GESETZT -- Umsetzungsaufwand: {aufwand_pt} PT (interne Umsetzung)",
            f"AUS DB, aber 'geschaetzt' -- Stundensatz {STUNDENSATZ_EUR:.0f} EUR/h "
            f"(Kostensatz K3, rollen_kostensaetze, gueltig ab 17.08.2026)",
            f"ABGELEITET -- Tagessatz {TAGESSATZ_EUR:.0f} EUR = {STUNDENSATZ_EUR:.0f} EUR/h x {STUNDEN_PRO_PT:.0f} h",
            "Kein Kernprozess hat Gate 0 durchlaufen (#159) -- diese Rechnung nimmt das vorweg.",
        ],
    }


def score(impact, komplex):
    """Komplexitaet x Impact. Quick Wins (hoher Impact, geringe Komplexitaet) -> hoher Score."""
    return round(IMPACT_W[impact] * (125 - KOMPLEX_W[komplex]) / 100.0, 2)


def lade_prozess(snapshot, kp_id):
    for p in snapshot["stammdaten"]["prozesse"]:
        if p["process_id"] == kp_id:
            return p
    raise KeyError(kp_id)


def reifegrad_zeile(snapshot, kp_id):
    for r in snapshot["reifegrad"]["kp_rows"]:
        if r["process_id"] == kp_id:
            return r
    raise KeyError(kp_id)


def tp_scores(snapshot, kp_id):
    return {r["sub_process_id"]: r for r in snapshot["reifegrad"]["prozessautomatisierung_matrix"][kp_id]["rows"]}


# ---------------------------------------------------------------------------
# Die drei Potenziale. Fachlich verankert an den *gemessen* schwaechsten
# Teilprozessen und den im Snapshot dokumentierten Medienbruechen.
# ---------------------------------------------------------------------------
POTENZIALE = {
    "KP-02": {
        "titel": "Lead-Erfassung und -Qualifizierung aus E-Mail-Anfragen ins CRM",
        "schritte": ["Lead erfassen", "Lead qualifizieren"],
        "tp_ids": ["KP-02.TP-1", "KP-02.TP-2"],
        "impact": "hoch",
        "komplexitaet": "gering",
        "kategorie": "Quick Win",
        "faelle_jahr": 180,
        "minuten": 25,
        "einsparungsgrad": 0.60,
        "aufwand_pt": 4,
        "frequenz_begruendung": "angenommen 15 Leads/Monat bei 10 Mitarbeitenden",
        "systeme": [
            {"name": "E-Mail / LinkedIn-Inbound", "rolle": "Quelle", "integration": "Email"},
            {"name": "EspoCRM", "rolle": "Ziel", "integration": "API"},
            {"name": "n8n", "rolle": "Quelle+Ziel", "integration": "API"},
        ],
        "aufwand_heute": "mittel",
        "ansatz": (
            "n8n greift den Posteingang und den LinkedIn-Inbound ab, ein LLM extrahiert "
            "Firma, Ansprechperson, Anliegen und Quelle strukturiert und legt den Lead ueber "
            "die EspoCRM-API an. Das vorhandene teilautomatische Lead-Scoring wird direkt "
            "angestossen, der Pipeline-Status vorbelegt. Bei unklarer Zuordnung oder fehlender "
            "DSGVO-Rechtsgrundlage bleibt der Lead im Entwurf und geht an den Vertrieb."
        ),
        "stack": ["n8n", "EspoCRM (API)", "Claude (Sonnet 4.6)", "PostgreSQL"],
        "to_be": (
            "Eingehende Anfragen landen ohne Abtippen als qualifizierter Lead im CRM; "
            "der Vertrieb entscheidet nur noch die unklaren Faelle."
        ),
        "voraussetzungen": [
            "EspoCRM-API-Schreibzugriff",
            "Postfach-/Graph-Anbindung fuer den Anfrage-Eingang",
            "DSGVO-Rechtsgrundlage fuer die automatisierte Verarbeitung von Kontaktdaten",
            "Abgrenzung, welche Felder das LLM setzen darf und welche der Mensch",
        ],
        "risiken": [
            {
                "beschreibung": "Fehlklassifizierte Leads verunreinigen die CRM-Pipeline",
                "wahrscheinlichkeit": "med",
                "auswirkung": "med",
                "gegenmassnahme": "Konfidenzschwelle, Entwurfsstatus bis zur Freigabe durch den Vertrieb",
            },
            {
                "beschreibung": "Personenbezogene Daten gehen an ein externes LLM",
                "wahrscheinlichkeit": "high",
                "auswirkung": "high",
                "gegenmassnahme": "PII-Grenze projektweit noch offen (#150) -- vor Umsetzung zu klaeren",
            },
        ],
    },
    "KP-03": {
        "titel": "AVV- und DSGVO-Abwicklung im Onboarding medienbruchfrei machen",
        "schritte": ["AVV + DSGVO klaeren"],
        "tp_ids": ["KP-03.TP-4"],
        "impact": "mittel",
        "komplexitaet": "mittel",
        "kategorie": "Strategisch",
        "faelle_jahr": 12,
        "minuten": 90,
        "einsparungsgrad": 0.50,
        "aufwand_pt": 5,
        "frequenz_begruendung": "angenommen 12 Onboardings/Jahr",
        "systeme": [
            {"name": "AVV-Vorlage (Dokument)", "rolle": "Quelle", "integration": "Datei"},
            {"name": "E-Signatur-Dienst", "rolle": "Quelle+Ziel", "integration": "API"},
            {"name": "EspoCRM", "rolle": "Ziel", "integration": "API"},
            {"name": "NocoDB (VVT)", "rolle": "Ziel", "integration": "API"},
        ],
        "aufwand_heute": "mittel",
        "ansatz": (
            "Die AVV-Vorlage wird aus den Engagement-Daten des CRM vorbefuellt, per "
            "E-Signatur statt auf Papier gezeichnet und der VVT-Eintrag daraus automatisch "
            "erzeugt. Der im Snapshot dokumentierte Medienbruch 'AVV-Unterzeichnung kann "
            "Papier sein' entfaellt; die Nachweiskette Vertrag -> AVV -> VVT wird "
            "durchgaengig maschinell fuehrbar."
        ),
        "stack": ["E-Signatur-Dienst", "n8n", "EspoCRM (API)", "NocoDB"],
        "to_be": (
            "AVV wird digital vorbefuellt und signiert, der VVT-Eintrag entsteht dabei "
            "automatisch statt in einem zweiten, manuellen Schritt."
        ),
        "voraussetzungen": [
            "Auswahl und Beschaffung eines E-Signatur-Dienstes",
            "rechtliche Freigabe der vorbefuellten AVV-Vorlage",
            "VVT-Struktur in NocoDB festgelegt",
        ],
        "risiken": [
            {
                "beschreibung": "Kunde besteht auf Papierunterzeichnung",
                "wahrscheinlichkeit": "med",
                "auswirkung": "low",
                "gegenmassnahme": "Papierweg als dokumentierter Sonderfall erhalten",
            },
            {
                "beschreibung": "Monetaerer Nutzen traegt die Investition rechnerisch nicht",
                "wahrscheinlichkeit": "high",
                "auswirkung": "med",
                "gegenmassnahme": (
                    "Nutzen liegt in Compliance-Sicherheit und Nachweisbarkeit, nicht in "
                    "Zeitersparnis -- ueber Nutzwertanalyse zu bewerten (#166), nicht ueber Amortisation"
                ),
            },
        ],
    },
    "KP-04": {
        "titel": "Sprint-Retrospektive und Lessons Learned automatisch verdichten",
        "schritte": ["Sprint-Retrospektive", "Lessons Learned ableiten"],
        "tp_ids": ["KP-04.TP-3", "KP-04.TP-5"],
        "impact": "mittel",
        "komplexitaet": "mittel",
        "kategorie": "Strategisch",
        "faelle_jahr": 24,
        "minuten": 120,
        "einsparungsgrad": 0.45,
        "aufwand_pt": 6,
        "frequenz_begruendung": "angenommen 24 Sprints/Jahr bei zweiwoechigem Takt",
        "systeme": [
            {"name": "GitLab Issues", "rolle": "Quelle", "integration": "API"},
            {"name": "Grafana Engagement-Dashboard", "rolle": "Quelle", "integration": "API"},
            {"name": "Wissensbasis (KP-05)", "rolle": "Ziel", "integration": "API"},
        ],
        "aufwand_heute": "mittel",
        "ansatz": (
            "Sprint-Daten aus GitLab Issues und dem Grafana-Dashboard werden am Sprint-Ende "
            "eingesammelt; ein LLM verdichtet sie zu einem Retrospektiven-Entwurf mit "
            "Auffaelligkeiten, offenen Punkten und Kandidaten fuer Verbesserungs-Items. "
            "Das Team arbeitet an diesem Entwurf statt am leeren Blatt. Die beschlossenen "
            "Action-Items gehen strukturiert an KP-09, die Lessons Learned an die Wissensbasis "
            "in KP-05 -- heute beides Handarbeit."
        ),
        "stack": ["GitLab API", "Grafana API", "Claude (Sonnet 4.6)", "n8n"],
        "to_be": (
            "Die Retrospektive startet mit einem datengestuetzten Entwurf; Lessons Learned "
            "landen ohne Nacharbeit in der Wissensbasis."
        ),
        "voraussetzungen": [
            "GitLab- und Grafana-API-Zugang",
            "Zielstruktur der Wissensbasis in KP-05 definiert",
            "Einvernehmen im Team, dass ein Entwurf die Retrospektive nicht praejudiziert",
        ],
        "risiken": [
            {
                "beschreibung": "Vorgefertigter Entwurf verengt die Retrospektive",
                "wahrscheinlichkeit": "med",
                "auswirkung": "med",
                "gegenmassnahme": "Entwurf als Materialsammlung kennzeichnen, nicht als Ergebnis",
            },
            {
                "beschreibung": "KP-05 Wissensmanagement ist erst zu 1 von 5 Teilprozessen erhoben (#159)",
                "wahrscheinlichkeit": "high",
                "auswirkung": "med",
                "gegenmassnahme": "Zielstruktur der Wissensbasis vor Umsetzung klaeren",
            },
        ],
    },
}


def baue_beschreibung(kp_id, prozess, spec, tps, value):
    """Beschreibung >= 300 Zeichen, Pflichtinhalt (a)-(g) laut Schema."""
    tp_namen = ", ".join(f"\"{t['name']}\"" for t in prozess["teilprozesse"]
                         if t["sub_process_id"] in spec["tp_ids"])
    tp_werte = "; ".join(
        f"{tps[t]['tp']} (Automatisierungsgrad {tps[t]['avg']}, "
        f"Tools {tps[t]['krit']['Tools im Prozess']}, "
        f"Systemintegration {tps[t]['krit']['Systemintegration']})"
        for t in spec["tp_ids"]
    )
    erster_tp = next(t for t in prozess["teilprozesse"] if t["sub_process_id"] == spec["tp_ids"][0])
    return (
        f"> **{MARKER} Uebergangslieferung, keine Bewertung.** Prozess, Teilprozesse, Tools, "
        f"Medienbrueche und Reifegrade unten sind **echt** (BC0-Snapshot v3 vom 27.08.2026). "
        f"Die Zahlen in `value{{}}` sind **gesetzt, nicht erhoben**: Fallzahl und "
        f"Bearbeitungszeit fuehrt die gemeinsame Datenbank nicht (Issue #159). "
        f"Zweck ist, BC3 und BC4 zu entblocken -- nicht, Wirtschaftlichkeit auszusagen. "
        f"Nicht fuer Entscheidungen, Angebote oder Gate-1-Freigaben verwenden.\n\n"
        f"**Ausgangslage (aus der Baseline, echt).** Im Kernprozess {kp_id} "
        f"\"{prozess['process_name']}\" betrifft dieses Potenzial {tp_namen}. "
        f"Der Snapshot v3 vom 27.08.2026 misst dort: {tp_werte}. "
        f"Als Medienbruch ist dokumentiert: \"{erster_tp['medienbrueche']}\". "
        f"Eingesetzt sind laut Baseline: {erster_tp['tools']}. "
        f"Die Schnittstellenlage ist \"{erster_tp['schnittstellen']}\". "
        f"Ausgeloest wird der Prozess durch: {prozess['trigger']}.\n\n"
        f"**(a) Was automatisiert wird.** {spec['ansatz']}\n\n"
        f"**(b) In welchen Prozessschritten.** {tp_namen} "
        f"(Notation laut Baseline: \"{erster_tp['notation']}\").\n\n"
        f"**(c) Mit welchem Ergebnis.** {spec['to_be']}\n\n"
        f"**(d) Datenfluesse.** "
        + " -> ".join(s["name"] for s in spec["systeme"]) + ". "
        f"Rollen und Integrationsart je System stehen in `betroffene_systeme`.\n\n"
        f"**(e) Beteiligte Akteure/Rollen.** Prozesseigner laut Baseline: "
        f"{', '.join(prozess['eigner_ids']) or 'nicht hinterlegt'}. "
        f"Im Regelfall arbeitet das System, der Mensch entscheidet die Ausnahmen.\n\n"
        f"**(f) Vorbedingungen.** " + "; ".join(spec["voraussetzungen"]) + ".\n\n"
        f"**(g) Sonderfaelle/Ausnahmen.** " + " ".join(
            f"{r['beschreibung']} -- {r['gegenmassnahme']}." for r in spec["risiken"]
        ) + "\n\n"
        f"**Zur Wirtschaftlichkeit -- bitte lesen.** Die Zahlen in `value{{}}` sind "
        f"**gesetzt, nicht erhoben**: die gemeinsame Datenbank fuehrt weder Fallzahlen noch "
        f"Bearbeitungszeiten (#159). Angenommen sind {spec['faelle_jahr']} Vorgaenge/Jahr "
        f"({spec['frequenz_begruendung']}) zu je {spec['minuten']} Minuten. Belegt ist allein "
        f"der Stundensatz -- und auch der ist in der Datenbank als 'geschaetzt' gefuehrt. "
        f"Die Amortisation von {value['amortisation_monate']} Monaten ist daher **keine Aussage "
        f"ueber die Wirtschaftlichkeit**, sondern ein Platzhalter in der richtigen Groessenordnung. "
        f"Der belastbare Stand folgt aus #166; die fehlenden Akzeptanzkriterien aus #160."
    )


def baue_konzept(snapshot, kp_id):
    prozess = lade_prozess(snapshot, kp_id)
    reife = reifegrad_zeile(snapshot, kp_id)
    tps = tp_scores(snapshot, kp_id)
    spec = POTENZIALE[kp_id]

    value = berechne_value(
        faelle_jahr=spec["faelle_jahr"],
        minuten_heute_pro_fall=spec["minuten"],
        einsparungsgrad=spec["einsparungsgrad"],
        aufwand_pt=spec["aufwand_pt"],
        extra_annahmen={"frequenz_begruendung": spec["frequenz_begruendung"]},
    )

    schmerzpunkte = [
        {
            "beschreibung": f"Dokumentierter Medienbruch: {t['medienbrueche']}",
            "haeufigkeit": f"Teilprozess {t['sub_process_id']}",
            "auswirkung": (
                f"Automatisierungsgrad {tps[t['sub_process_id']]['avg']} von 5 "
                f"(Tools {tps[t['sub_process_id']]['krit']['Tools im Prozess']}, "
                f"Systemintegration {tps[t['sub_process_id']]['krit']['Systemintegration']})"
            ),
        }
        for t in prozess["teilprozesse"] if t["sub_process_id"] in spec["tp_ids"]
    ]

    kurz = (f"{MARKER} {prozess['process_name']} ({prozess['kategorie']}, "
            f"Reifegrad {reife['avg']}/5) bei NoroAI Consulting GmbH, 10 Mitarbeitende, KI-Beratung.")
    assert len(kurz) <= 280, len(kurz)

    potenzial = {
        "potenzial_id": POTENZIAL_ID[kp_id],
        "titel": f"{MARKER} {spec['titel']}",
        "rang": 1,
        "beschreibung": baue_beschreibung(kp_id, prozess, spec, tps, value),
        "betroffene_prozessschritte": [
            t["name"] for t in prozess["teilprozesse"] if t["sub_process_id"] in spec["tp_ids"]
        ],
        "betroffene_systeme": spec["systeme"],
        "manueller_aufwand_heute": spec["aufwand_heute"],
        "impact": spec["impact"],
        "umsetzungskomplexitaet": spec["komplexitaet"],
        "value": value,
        "aufwand_schaetzung_pt": spec["aufwand_pt"],
        "prioritaet_score": score(spec["impact"], spec["komplexitaet"]),
        "kategorie": spec["kategorie"],
        "potenzielle_loesung": {
            "ansatz": spec["ansatz"],
            "tech_stack_empfehlung": spec["stack"],
            "to_be_kurz": spec["to_be"],
        },
        "voraussetzungen": spec["voraussetzungen"],
        "risiken": spec["risiken"],
    }

    return {
        "konzept_id": KONZEPT_ID[kp_id],
        "schema_version": "2.0",
        # BC1 liefert derzeit nichts (Schema bc1 ist leer, #163). Die Herkunft
        # ist deshalb ausdruecklich der BC0-Snapshot, nicht ein BC1-Profil.
        "prozessprofil_ref": f"bc0-snapshot:NoroAI_Consulting_GmbH_baseline_v3.json#{kp_id}",
        "erzeugt_am": NOW,
        "erzeugt_von": ERZEUGT_VON,
        "kontext": {
            "prozess_kurzbeschreibung": kurz,
            "kp_id": kp_id,
            "unternehmen": "NoroAI Consulting GmbH (KI-Beratung, 10 Mitarbeitende)",
            "betroffene_systeme_landschaft": ["EspoCRM", "n8n", "GitLab", "Grafana", "NocoDB"],
            "hauptschmerzpunkte": schmerzpunkte,
        },
        "potenziale": [potenzial],
        "gesamtempfehlung": {
            "reihenfolge_potenzial_ids": [POTENZIAL_ID[kp_id]],
            "begruendung": (
                f"{MARKER} Dieses Konzept traegt genau ein Potenzial; eine Reihenfolge "
                f"innerhalb des Konzepts entfaellt. Die Reihenfolge **ueber alle drei "
                f"Kernprozesse hinweg** steht in `prozesspriorisierung.json`. "
                f"Grundlage der Auswahl ist der gemessene Automatisierungsgrad je "
                f"Teilprozess aus dem BC0-Snapshot v3, nicht die Value-Rechnung -- "
                f"diese ist vorlaeufig."
            ),
        },
        "gate1": {
            "status": "pending",
            "kommentar": (
                f"{MARKER} Dieses Konzept darf am Gate 1 NICHT freigegeben werden. "
                f"Es ist eine Uebergangslieferung an BC3 (Issue #168), damit BC3 Tickets "
                f"schneiden und BC4 bauen kann. Die Value-Zahlen sind gesetzt, nicht erhoben. "
                f"Zusaetzlich hat kein Kernprozess Gate 0 durchlaufen (#159). "
                f"Freigabefaehig wird der Stand erst nach #166 (Value-Modell) und #160 "
                f"(Akzeptanzkriterien)."
            ),
        },
    }


def baue_priorisierung(konzepte):
    eintraege = []
    for k in konzepte:
        p = k["potenziale"][0]
        eintraege.append({
            "potenzial_id": p["potenzial_id"],
            "konzept_id": k["konzept_id"],
            "titel": p["titel"],
            "kp_id": k["kontext"]["kp_id"],
            "kategorie": p["kategorie"],
            "impact": p["impact"],
            "umsetzungskomplexitaet": p["umsetzungskomplexitaet"],
            "score": p["prioritaet_score"],
            "aufwand_pt": p["aufwand_schaetzung_pt"],
            "einsparung_eur_jahr": p["value"]["einsparung_eur_jahr"],
            "investition_eur_richtwert": p["value"]["investition_eur_richtwert"],
            "amortisation_monate": p["value"]["amortisation_monate"],
            "bemerkung": (
                f"{MARKER} Value gesetzt, nicht erhoben. Rang folgt dem Score "
                f"(Impact x Komplexitaet); bei Gleichstand entscheidet die hoehere "
                f"angenommene Einsparung. Beides vorlaeufig."
            ),
            "rang": 0,  # wird gleich gesetzt
        })

    # Sortierung: Score absteigend, bei Gleichstand hoehere Einsparung zuerst.
    eintraege.sort(key=lambda e: (-e["score"], -e["einsparung_eur_jahr"]))
    for i, e in enumerate(eintraege, start=1):
        e["rang"] = i

    return {
        "priorisierung_id": PRIORISIERUNG_ID,
        "schema_version": "2.0",
        "erzeugt_am": NOW,
        "score_formel": (
            f"**{MARKER} Vorlaeufig.** `score = impact_gewicht(impact) * "
            f"(125 - komplexitaet_gewicht(umsetzungskomplexitaet)) / 100` mit "
            f"gering=25, mittel=50, hoch=75, sehr hoch=100. Bei Score-Gleichstand "
            f"entscheidet die hoehere angenommene Jahreseinsparung.\n\n"
            f"Die Formel ist aus dem v2-Stand uebernommen und **nicht** das Ergebnis von "
            f"#166 (Value-Modell: Bandbreiten + Nutzwertanalyse). Sie bewertet ausschliesslich "
            f"Impact x Komplexitaet -- die Geldbetraege gehen in den Rang nur als Tie-Break ein. "
            f"Das ist Absicht: die Geldbetraege sind gesetzt, nicht erhoben, und wuerden ein "
            f"Ranking sonst scheingenau machen."
        ),
        "eintraege": eintraege,
    }


def main():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert snapshot["snapshot_version"] == "v3", snapshot["snapshot_version"]
    assert snapshot["mandant"]["id"] == "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"

    ZIEL.mkdir(parents=True, exist_ok=True)

    konzepte = [baue_konzept(snapshot, kp) for kp in ("KP-02", "KP-03", "KP-04")]
    for k in konzepte:
        pfad = ZIEL / f"konzept_{k['kontext']['kp_id']}.json"
        pfad.write_text(json.dumps(k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"geschrieben: {pfad.relative_to(BASE)}")

    prio = baue_priorisierung(konzepte)
    pfad = ZIEL / "prozesspriorisierung.json"
    pfad.write_text(json.dumps(prio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"geschrieben: {pfad.relative_to(BASE)}")

    print("\nRangfolge:")
    for e in prio["eintraege"]:
        print(f"  {e['rang']}. [{e['kp_id']}] score={e['score']:<6} "
              f"einsparung={e['einsparung_eur_jahr']:>9.2f} EUR/a  "
              f"invest={e['investition_eur_richtwert']:>8.2f} EUR  "
              f"amort={e['amortisation_monate']:>5.1f} Mon")


if __name__ == "__main__":
    main()
