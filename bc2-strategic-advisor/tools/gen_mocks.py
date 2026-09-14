"""
Erzeugt die v2-Mock-Artefakte fuer BC2 aus dem BC1-Prozessprofil (Krankentagegeld).
Die Value-/ROI-Berechnung ist DETERMINISTISCH (kein LLM) -- dient zugleich als
Referenzimplementierung fuer AP 2.3 (ROI-/Value-Calculator).
"""
import json, uuid, datetime, pathlib

BASE = pathlib.Path(__file__).resolve().parents[2]
NOW = "2026-06-27T12:00:00Z"

# --- deterministische Kalkulations-Defaults (dokumentiert in mock_roi_report.md) ---
ARBEITSWOCHEN_JAHR = 46          # ~6 Wochen Ausfall/Urlaub/Feiertage
STUNDENSATZ_EUR = 50.0           # kalkulatorischer Vollkostensatz Sachbearbeitung
TAGESSATZ_EUR = 800.0            # externer Umsetzungs-Tagessatz (Investitions-Richtwert)
VOLUMEN_WOCHE = 300              # aus BC1: ~300 Antraege/Woche
JAHRESVOLUMEN = VOLUMEN_WOCHE * ARBEITSWOCHEN_JAHR   # 13.800

IMPACT_W = {"gering": 25, "mittel": 50, "hoch": 75, "sehr hoch": 100}
KOMPLEX_W = {"gering": 25, "mittel": 50, "hoch": 75, "sehr hoch": 100}


def berechne_value(faelle_jahr, minuten_heute_pro_fall, einsparungsgrad, aufwand_pt):
    """Deterministische Value-Berechnung. Rueckgabe: value-Objekt (Schema-konform)."""
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
        "value_quelle": "berechnet",
        "annahmen": [
            f"Jahresvolumen {JAHRESVOLUMEN} Vorgaenge ({VOLUMEN_WOCHE}/Woche x {ARBEITSWOCHEN_JAHR} Wochen)",
            f"Vollkostensatz {STUNDENSATZ_EUR:.0f} EUR/h",
            f"Umsetzungs-Tagessatz {TAGESSATZ_EUR:.0f} EUR",
            f"betroffene Faelle/Jahr: {faelle_jahr}",
            f"manuelle Zeit heute: {minuten_heute_pro_fall} Min/Fall",
            f"angenommener Einsparungsgrad: {int(einsparungsgrad*100)} %",
        ],
    }


def score(impact, komplex):
    """Komplexitaet x Impact. Quick Wins (hoher Impact, geringe Komplexitaet) -> hoher Score."""
    return round(IMPACT_W[impact] * (125 - KOMPLEX_W[komplex]) / 100.0, 2)


# --- feste UUIDs, damit Mocks reproduzierbar/diff-stabil sind ---
KONZEPT_ID = "3f9a1c22-0001-4a10-9c00-000000000001"
PROFIL_REF = "mock_prozessprofil"     # v1: Key/Dateiname statt UUID
P1 = "aa000000-0000-4000-8000-000000000001"  # OCR+LLM Antragserfassung
P2 = "aa000000-0000-4000-8000-000000000002"  # Rueckfrage-Workflow
P3 = "aa000000-0000-4000-8000-000000000003"  # Bescheid-Generator

# ---------------------------------------------------------------------------
# Potenzial 1 -- Automatisierte Antragserfassung (OCR + LLM-Feldextraktion)
# ---------------------------------------------------------------------------
p1_value = berechne_value(faelle_jahr=JAHRESVOLUMEN, minuten_heute_pro_fall=5,
                          einsparungsgrad=0.70, aufwand_pt=25)
p1 = {
    "potenzial_id": P1,
    "titel": "Automatisierte Antragserfassung via OCR + LLM-Feldextraktion",
    "rang": 2,
    "beschreibung": (
        "Im Schritt \"Antrag erfassen\" digitalisiert die Sachbearbeitung heute jeden eingehenden "
        "Krankentagegeld-Antrag manuell in SAP. Papier-Antraege werden zunaechst am Dokumentenscanner "
        "eingescannt, PDF-Antraege liegen bereits digital vor; anschliessend werden die relevanten "
        "Felder (Versichertennummer, Zeitraum, Diagnose-Bezug, Bankverbindung) von Hand in die "
        "SAP-Maske uebertragen. Das betrifft **alle** rund 13.800 Vorgaenge pro Jahr und kostet je "
        "Fall etwa fuenf Minuten reine Erfassungszeit. Zwei Automatisierungshindernisse sind bekannt: "
        "Papier-Antraege muessen gescannt werden, und die OCR-Qualitaet schwankt.\n\n"
        "**Was automatisiert wird:** Ein OCR-Service liest das gescannte oder hochgeladene Dokument, "
        "ein nachgelagertes LLM extrahiert die Felder strukturiert, prueft sie auf Plausibilitaet "
        "(z. B. gueltiges Datum, vorhandene Versichertennummer) und schreibt sie ueber die SAP-API in "
        "den Antragsdatensatz. Nur bei niedriger Extraktions-Konfidenz wird der Fall der "
        "Sachbearbeitung zur manuellen Nacherfassung vorgelegt (Human-in-the-Loop).\n\n"
        "**Prozessschritt:** \"Antrag erfassen\" (erster Schritt). **Ergebnis:** ein vollstaendig "
        "erfasster, strukturierter Antrag in SAP inklusive Konfidenz-Flag. **Datenfluesse:** "
        "Dokument (Scan/PDF) -> OCR -> LLM-Extraktion -> Validierung -> SAP-API. **Akteure:** "
        "Sachbearbeitung (nur noch Ausnahmefaelle), System (Regelfall). **Vorbedingungen:** "
        "SAP-API-Schreibzugriff, ein OCR-Modell, DSGVO-Freigabe fuer die Dokumentenverarbeitung. "
        "**Sonderfaelle/Ausnahmen:** unleserliche Scans, unbekannte Formulartypen und Antraege mit "
        "widerspruechlichen Angaben werden nicht automatisch gebucht, sondern eskaliert. Damit sinkt "
        "der manuelle Erfassungsaufwand deutlich, ohne die fachliche Kontrolle aufzugeben."
    ),
    "betroffene_prozessschritte": ["Antrag erfassen"],
    "betroffene_systeme": [
        {"name": "Dokumentenscanner", "rolle": "Quelle", "integration": "OCR"},
        {"name": "SAP", "rolle": "Ziel", "integration": "API"},
    ],
    "manueller_aufwand_heute": "mittel",
    "impact": "hoch",
    "umsetzungskomplexitaet": "mittel",
    "value": p1_value,
    "aufwand_schaetzung_pt": 25,
    "prioritaet_score": score("hoch", "mittel"),
    "kategorie": "Quick Win",
    "potenzielle_loesung": {
        "ansatz": (
            "OCR-Extraktion des Antragsdokuments, LLM-gestuetzte Feldextraktion und Plausibilitaets"
            "pruefung, Rueckschreiben der strukturierten Felder via SAP-API. Konfidenzschwelle steuert "
            "den Human-in-the-Loop: unsichere Faelle gehen an die Sachbearbeitung."
        ),
        "tech_stack_empfehlung": ["OCR-Service", "Claude (Sonnet 4.6)", "n8n", "SAP-API", "PostgreSQL"],
        "to_be_kurz": "Antraege werden automatisch erfasst; Menschen bearbeiten nur noch Ausnahmen.",
    },
    "voraussetzungen": ["SAP-API-Schreibzugriff", "OCR-Modell verfuegbar", "DSGVO-Freigabe Dokumentenverarbeitung"],
    "risiken": [
        {"beschreibung": "OCR-Qualitaet bei schlechten Scans zu niedrig", "wahrscheinlichkeit": "med",
         "auswirkung": "med", "gegenmassnahme": "Konfidenzschwelle + manueller Fallback"},
    ],
}

# ---------------------------------------------------------------------------
# Potenzial 2 -- Rueckfrage-Workflow (strukturierte Nachforderung + Bot)
# ---------------------------------------------------------------------------
FAELLE_RUECKFRAGE = int(round(JAHRESVOLUMEN * 0.30))   # 30 % der Faelle
p2_value = berechne_value(faelle_jahr=FAELLE_RUECKFRAGE, minuten_heute_pro_fall=8,
                          einsparungsgrad=0.60, aufwand_pt=30)
p2 = {
    "potenzial_id": P2,
    "titel": "Gefuehrter Rueckfrage-Workflow bei unvollstaendigen Antraegen",
    "rang": 3,
    "beschreibung": (
        "Rund 30 % aller Antraege sind unvollstaendig und loesen eine Rueckfrage an die Versicherten "
        "aus -- der laut BC1 groesste Zeitfresser des Prozesses. Heute formuliert die Sachbearbeitung "
        "die Rueckfrage manuell in Outlook, es entsteht ein Medienbruch zwischen Mail und SAP, und die "
        "Antwortzeit der Versicherten ist nicht kontrollierbar (Wartezeit +1 bis 3 Tage, faktisch oft "
        "laenger). Pro Rueckfrage fallen ueber Formulierung, Wiedervorlage und Nachverfolgung rund "
        "acht Minuten aktive Bearbeitungszeit an; das betrifft etwa 4.140 Faelle pro Jahr.\n\n"
        "**Was automatisiert wird:** Sobald die sachliche Pruefung eine definierte Luecke erkennt "
        "(z. B. fehlende Bescheinigung), erzeugt das System eine strukturierte, vollstaendige "
        "Nachforderung mit klarer Angabe der fehlenden Unterlagen und einem Ruecklauf-Link/Formular. "
        "Erinnerungen laufen automatisch, der Ruecklauf wird ohne manuelle Uebertragung dem SAP-Vorgang "
        "zugeordnet. **Prozessschritt:** \"Rueckfrage an Versicherten\". **Ergebnis:** vollstaendiger "
        "Antrag oder dokumentierte Nichtreaktion nach definierter Frist. **Datenfluesse:** "
        "SAP-Lueckenbefund -> Nachforderungsvorlage -> Versand (E-Mail/Portal) -> Ruecklauf -> "
        "automatische Zuordnung zum SAP-Vorgang. **Akteure:** Sachbearbeitung (nur Freigabe/Ausnahmen), "
        "Versicherte (extern), System. **Vorbedingungen:** definierte Luecken-Kategorien, "
        "Outlook-/Portal-Anbindung, Vorlagenkatalog. **Sonderfaelle:** mehrfache Rueckfragen, "
        "Teil-Rueckmeldungen und Fristablauf werden geregelt. Die eigentliche Kundenantwortzeit bleibt "
        "unbeeinflussbar -- deshalb ist die Einsparung auf den internen Aufwand begrenzt."
    ),
    "betroffene_prozessschritte": ["Sachliche Pruefung", "Rueckfrage an Versicherten (bei Luecken)"],
    "betroffene_systeme": [
        {"name": "SAP", "rolle": "Quelle+Ziel", "integration": "API"},
        {"name": "Outlook", "rolle": "Quelle+Ziel", "integration": "Email"},
    ],
    "manueller_aufwand_heute": "hoch",
    "impact": "hoch",
    "umsetzungskomplexitaet": "hoch",
    "value": p2_value,
    "aufwand_schaetzung_pt": 30,
    "prioritaet_score": score("hoch", "hoch"),
    "kategorie": "Strategisch",
    "potenzielle_loesung": {
        "ansatz": (
            "Regelbasierte Luecken-Erkennung in der Pruefung, generierte strukturierte Nachforderung, "
            "automatischer Versand mit Erinnerungen und medienbruchfreie Rueckordnung zum SAP-Vorgang. "
            "LLM formuliert die Nachforderung verstaendlich, Regeln steuern den Ablauf."
        ),
        "tech_stack_empfehlung": ["n8n", "Claude (Sonnet 4.6)", "SAP-API", "Outlook/Graph-API", "PostgreSQL"],
        "to_be_kurz": "Nachforderungen laufen strukturiert und medienbruchfrei; Wiedervorlage automatisch.",
    },
    "voraussetzungen": ["Outlook-/Graph-Anbindung", "SAP-API-Zugang", "definierter Luecken-Katalog"],
    "risiken": [
        {"beschreibung": "Medienbruch Mail<->SAP schwer aufzuloesen", "wahrscheinlichkeit": "med",
         "auswirkung": "high", "gegenmassnahme": "eindeutige Vorgangs-IDs im Betreff + Rueckordnungslogik"},
        {"beschreibung": "Kundenantwortzeit bleibt unkontrollierbar", "wahrscheinlichkeit": "high",
         "auswirkung": "med", "gegenmassnahme": "automatische Eskalation nach Frist"},
    ],
}

# ---------------------------------------------------------------------------
# Potenzial 3 -- Bescheid-Generator mit Templates
# ---------------------------------------------------------------------------
p3_value = berechne_value(faelle_jahr=JAHRESVOLUMEN, minuten_heute_pro_fall=6,
                          einsparungsgrad=0.75, aufwand_pt=15)
p3 = {
    "potenzial_id": P3,
    "titel": "Bescheid-Generator mit Textbausteinen und Vorlagen",
    "rang": 1,
    "beschreibung": (
        "Im letzten Schritt \"Bescheid versenden\" wird heute **jeder** Bescheid manuell formuliert -- "
        "es gibt keine Templates. Das verlangsamt die Endphase und fuehrt zu uneinheitlichen "
        "Formulierungen; zusaetzlich fehlt eine Postversand-Schnittstelle. Betroffen sind alle rund "
        "13.800 Vorgaenge pro Jahr mit geschaetzt sechs Minuten Formulierungs- und Pruefaufwand je "
        "Bescheid.\n\n"
        "**Was automatisiert wird:** Auf Basis von Pruefergebnis (Genehmigung/Ablehnung), "
        "Auszahlungsdaten und Ablehnungsgruenden erzeugt ein Template-Generator den vollstaendigen "
        "Bescheidtext aus versionierten, rechtssicher freigegebenen Textbausteinen. Die Sachbearbeitung "
        "prueft nur noch und gibt frei; der Versand wird ueber eine definierte Schnittstelle "
        "angestossen. **Prozessschritt:** \"Bescheid versenden\" (und Uebergabe aus \"Auszahlung "
        "anstossen / Ablehnung erstellen\"). **Ergebnis:** einheitlicher, korrekter Bescheid in "
        "Sekunden statt Minuten. **Datenfluesse:** SAP-Vorgangsdaten -> Template-Engine -> Bescheid-"
        "PDF -> Freigabe -> Versand. **Akteure:** Sachbearbeitung (Freigabe), System (Erzeugung). "
        "**Vorbedingungen:** freigegebener, versionierter Textbaustein-Katalog; Zugriff auf die "
        "Vorgangsdaten in SAP. **Sonderfaelle:** individuelle Begruendungen bei komplexen Ablehnungen "
        "bleiben editierbar. Wegen geringer Komplexitaet, hoher Fallzahl und niedriger Investition ist "
        "dies das wirtschaftlichste Potenzial des Prozesses."
    ),
    "betroffene_prozessschritte": ["Auszahlung anstossen / Ablehnung erstellen", "Bescheid versenden"],
    "betroffene_systeme": [
        {"name": "SAP", "rolle": "Quelle", "integration": "API"},
        {"name": "Outlook + Postversand", "rolle": "Ziel", "integration": "Datei"},
    ],
    "manueller_aufwand_heute": "hoch",
    "impact": "sehr hoch",
    "umsetzungskomplexitaet": "gering",
    "value": p3_value,
    "aufwand_schaetzung_pt": 15,
    "prioritaet_score": score("sehr hoch", "gering"),
    "kategorie": "Quick Win",
    "potenzielle_loesung": {
        "ansatz": (
            "Versionierter Textbaustein-Katalog + Template-Engine, gespeist aus SAP-Vorgangsdaten. "
            "LLM formuliert nur individuelle Begruendungen; Standardbescheide entstehen regelbasiert. "
            "Sachbearbeitung gibt frei, Versand ueber definierte Schnittstelle."
        ),
        "tech_stack_empfehlung": ["Template-Engine", "Claude (Sonnet 4.6)", "SAP-API", "PostgreSQL"],
        "to_be_kurz": "Bescheide entstehen einheitlich per Vorlage; Mensch prueft und gibt frei.",
    },
    "voraussetzungen": ["freigegebener Textbaustein-Katalog", "SAP-Vorgangsdaten-Zugriff"],
    "risiken": [
        {"beschreibung": "Rechtssichere Formulierungen muessen fachlich freigegeben werden",
         "wahrscheinlichkeit": "med", "auswirkung": "med",
         "gegenmassnahme": "Freigabe-Workflow fuer Textbausteine, Versionierung"},
    ],
}

potenziale = [p1, p2, p3]

# Ranking nach Score (desc) fuer gesamtempfehlung + Priorisierung
ranked = sorted(potenziale, key=lambda p: p["prioritaet_score"], reverse=True)
reihenfolge = [p["potenzial_id"] for p in ranked]

konzept = {
    "konzept_id": KONZEPT_ID,
    "schema_version": "2.0",
    "prozessprofil_ref": PROFIL_REF,
    "erzeugt_am": NOW,
    "erzeugt_von": "bc2-advisor@v2.0 (mock)",
    "kontext": {
        "prozess_kurzbeschreibung": "Versicherte reichen Antraege auf Krankentagegeld ein; das Team prueft und bewilligt (Aurelia Krankenkasse).",
        "kp_id": "KP-07",
        "unternehmen": "Aurelia Krankenkasse, Abteilung Leistung",
        "betroffene_systeme_landschaft": ["SAP", "Outlook", "Excel", "Dokumentenscanner"],
        "hauptschmerzpunkte": [
            {"beschreibung": "Rueckfrage-Schleifen bei unvollstaendigen Antraegen",
             "haeufigkeit": "30 % der Faelle", "auswirkung": "+1-3 Tage Wartezeit, Hauptzeitfresser"},
            {"beschreibung": "Excel-Liste 'Offene Antraege' veraltet oft",
             "haeufigkeit": "woechentlich", "auswirkung": "ca. 1 Antrag/Woche geht verloren und muss rekonstruiert werden"},
            {"beschreibung": "Bescheide manuell formuliert (keine Templates)",
             "haeufigkeit": "jeder Bescheid", "auswirkung": "verlangsamt Endphase, uneinheitliche Formulierungen"},
        ],
    },
    "potenziale": potenziale,
    "gesamtempfehlung": {
        "reihenfolge_potenzial_ids": reihenfolge,
        "begruendung": (
            "Empfohlen wird, mit dem **Bescheid-Generator** zu starten: hoechster Score (geringe "
            "Komplexitaet, sehr hoher Impact, Amortisation < 3 Monate). Danach die **OCR-/LLM-"
            "Antragserfassung** als zweiter Quick Win. Der **Rueckfrage-Workflow** folgt zuletzt: hoher "
            "Nutzen, aber hoehere Komplexitaet (Medienbruch, Kundeninteraktion, DSGVO) und laengere "
            "Amortisation -- als strategisches Potenzial bewusst nach den Quick Wins."
        ),
    },
    "gate1": {"status": "pending"},
}

# --- Priorisierung (potenzial-zentriert, ueber alle Konzepte) ---
priorisierung = {
    "priorisierung_id": "bb000000-0000-4000-8000-000000000001",
    "schema_version": "2.0",
    "erzeugt_am": NOW,
    "score_formel": (
        "score = impact_gewicht x (125 - komplexitaet_gewicht) / 100, mit "
        "Gewichten gering=25, mittel=50, hoch=75, sehr hoch=100. "
        "Geringe Umsetzungskomplexitaet erhoeht den Score, hoher Impact ebenso -> Quick Wins zuerst."
    ),
    "eintraege": [
        {
            "rang": i + 1,
            "potenzial_id": p["potenzial_id"],
            "konzept_id": KONZEPT_ID,
            "titel": p["titel"],
            "kp_id": "KP-07",
            "kategorie": p["kategorie"],
            "impact": p["impact"],
            "umsetzungskomplexitaet": p["umsetzungskomplexitaet"],
            "score": p["prioritaet_score"],
            "aufwand_pt": p["aufwand_schaetzung_pt"],
            "einsparung_eur_jahr": p["value"]["einsparung_eur_jahr"],
            "investition_eur_richtwert": p["value"]["investition_eur_richtwert"],
            "amortisation_monate": p["value"]["amortisation_monate"],
        }
        for i, p in enumerate(ranked)
    ],
}

# set rang inside konzept-potenziale consistent with ranking
rang_map = {p["potenzial_id"]: i + 1 for i, p in enumerate(ranked)}
for p in potenziale:
    p["rang"] = rang_map[p["potenzial_id"]]

(BASE / "contracts" / "examples" / "mock_automatisierungskonzept.json").write_text(
    json.dumps(konzept, ensure_ascii=False, indent=2), encoding="utf-8")
(BASE / "contracts" / "examples" / "mock_prozesspriorisierung.json").write_text(
    json.dumps(priorisierung, ensure_ascii=False, indent=2), encoding="utf-8")

# --- ROI-Report (menschenlesbar) ---
def eur(x): return f"{x:,.0f} EUR".replace(",", ".")
lines = []
lines.append("# BC2 -- ROI-/Value-Report (Mock)\n")
lines.append(f"**Prozess:** Antragsbearbeitung Krankentagegeld (KP-07) · **Stand:** {NOW}\n")
lines.append("**Berechnungsmodell (deterministisch, kein LLM):**\n")
lines.append(f"- Jahresvolumen: {JAHRESVOLUMEN:,} Vorgaenge ({VOLUMEN_WOCHE}/Woche x {ARBEITSWOCHEN_JAHR} Wochen)".replace(",", "."))
lines.append(f"- Vollkostensatz: {STUNDENSATZ_EUR:.0f} EUR/h · Umsetzungs-Tagessatz: {TAGESSATZ_EUR:.0f} EUR")
lines.append("- ist_kosten = betroffene_faelle x minuten_heute / 60 x stundensatz")
lines.append("- einsparung = ist_kosten x einsparungsgrad · investition = aufwand_pt x tagessatz")
lines.append("- amortisation_monate = investition / (einsparung / 12)\n")
lines.append("| Rang | Potenzial | Ist-Kosten/Jahr | Einsparung/Jahr | Ersparnis | Investition | Amortisation | Score | Kategorie |")
lines.append("|---|---|---|---|---|---|---|---|---|")
for i, p in enumerate(ranked):
    v = p["value"]
    lines.append(
        f"| {i+1} | {p['titel']} | {eur(v['ist_kosten_eur_jahr'])} | {eur(v['einsparung_eur_jahr'])} | "
        f"{v['ersparnis_prozent']:.0f} % | {eur(v['investition_eur_richtwert'])} | "
        f"{v['amortisation_monate']:.1f} Mon. | {p['prioritaet_score']:.1f} | {p['kategorie']} |")
summe_einsp = sum(p["value"]["einsparung_eur_jahr"] for p in ranked)
summe_inv = sum(p["value"]["investition_eur_richtwert"] for p in ranked)
lines.append(f"\n**Summe Einsparung/Jahr:** {eur(summe_einsp)} · **Summe Investition (Richtwert):** {eur(summe_inv)}\n")
lines.append("> Hinweis: Werte sind Richtwerte auf Basis der BC1-Angaben und dokumentierter Annahmen. "
             "Die qualitative Bewertung (Impact/Komplexitaet) stammt aus der LLM-Potenzialerkennung, "
             "die Zahlen aus der deterministischen Berechnung.")
(BASE / "contracts" / "examples" / "mock_roi_report.md").write_text("\n".join(lines), encoding="utf-8")

print("Mocks erzeugt.")
print("Ranking:", [(p['titel'][:30], p['prioritaet_score']) for p in ranked])
print("Summe Einsparung/Jahr:", eur(summe_einsp))
