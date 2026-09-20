// ERZEUGT von daten_bauen.py — nicht von Hand ändern. PROTOTYP zu #167.
window.PROTOTYP_DATEN = {
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
   "teilprozesse": [
    "KP-04.TP-3",
    "KP-03.TP-2",
    "KP-06.TP-1",
    "KP-06.TP-4",
    "KP-02.TP-1",
    "KP-06.TP-2",
    "KP-03.TP-4",
    "KP-04.TP-5",
    "KP-04.TP-2",
    "KP-02.TP-3",
    "KP-06.TP-5"
   ],
   "konzepte": [
    {
     "kp_id": "KP-04",
     "name": "Projektdurchführung",
     "reifegrad": 3.52,
     "ausgangslage": "Projekte laufen über Jira und eine eigene Zeiterfassung. Statusberichte und Retrospektiven werden je Projektleitung unterschiedlich geführt.",
     "systeme": [
      "Jira",
      "Zeiterfassung (eigenentwickelt)",
      "Confluence",
      "Excel"
     ],
     "schmerzpunkte": [
      "Statusberichte kosten wöchentlich Zeit und sehen überall anders aus",
      "Erkenntnisse aus Retrospektiven versanden"
     ],
     "potenzial_ids": [
      "P-10",
      "P-06",
      "P-05"
     ],
     "bester_rang": 1,
     "prozessrang": 1
    },
    {
     "kp_id": "KP-03",
     "name": "Kunden-Onboarding",
     "reifegrad": 3.77,
     "ausgangslage": "Neukunden werden anhand einer Checkliste in Excel aufgenommen. AVV und DSGVO-Unterlagen werden versendet, unterschrieben zurückerwartet und abgelegt — teils auf Papier.",
     "systeme": [
      "Excel",
      "Outlook",
      "DocuSign (punktuell)",
      "Netzlaufwerk"
     ],
     "schmerzpunkte": [
      "Dokumentierter Medienbruch: AVV-Unterzeichnung kann Papier sein",
      "Fristen werden nicht systematisch nachgehalten"
     ],
     "potenzial_ids": [
      "P-04",
      "P-03"
     ],
     "bester_rang": 2,
     "prozessrang": 2
    },
    {
     "kp_id": "KP-06",
     "name": "Ressourcen- & Einsatzplanung",
     "reifegrad": 3.1,
     "ausgangslage": "Einsätze, Reisen und Verfügbarkeiten werden in einer Tabelle geplant und per Absprache abgeglichen. Belege werden gesammelt und monatlich erfasst.",
     "systeme": [
      "Excel",
      "Outlook-Kalender",
      "Reiseportale",
      "DATEV (nachgelagert)"
     ],
     "schmerzpunkte": [
      "Konflikte fallen erst am Einsatztag auf",
      "Belegerfassung staut sich zum Monatsende"
     ],
     "potenzial_ids": [
      "P-09",
      "P-08",
      "P-07",
      "P-11"
     ],
     "bester_rang": 3,
     "prozessrang": 3
    },
    {
     "kp_id": "KP-02",
     "name": "Vertrieb & Akquise",
     "reifegrad": 3.41,
     "ausgangslage": "Anfragen erreichen NoroAI per E-Mail und über das Kontaktformular und werden von Hand ins CRM übertragen. Angebote entstehen aus früheren Angeboten durch Kopieren.",
     "systeme": [
      "Outlook",
      "HubSpot",
      "Word",
      "Netzlaufwerk"
     ],
     "schmerzpunkte": [
      "Doppelerfassung zwischen Postfach und CRM",
      "Angebotsqualität hängt an der Person"
     ],
     "potenzial_ids": [
      "P-01",
      "P-02"
     ],
     "bester_rang": 5,
     "prozessrang": 4
    }
   ],
   "potenziale": [
    {
     "id": "P-10",
     "kp_id": "KP-04",
     "tp_id": "KP-04.TP-3",
     "titel": "Rechnungsstellung aus Zeiterfassung und Projektvertrag erzeugen",
     "loesungsansatz": "Aus Zeiterfassung und Projektvertrag den Rechnungsentwurf erzeugen und zur Freigabe vorlegen.",
     "klasse": "Regelwerk / Weiterleitung",
     "korridor_pct": [
      70,
      90
     ],
     "lage_im_korridor": "oberes Drittel",
     "lage_begruendung": "Der Ablauf ist vollständig geregelt: Stunden × Satz nach Vertrag. Nur Sonderabsprachen brauchen einen Menschen.",
     "aufwand_pt": 5,
     "herkunft_dauer": "gemessen",
     "konfidenz_pct": null,
     "nutzwert_kategorien": {
      "Qualität": 6,
      "Durchlaufzeit": 7,
      "Fehlerreduktion": 8,
      "Mitarbeiterzufriedenheit": 6,
      "Compliance / Rechtssicherheit": 6
     },
     "querschnitt": {
      "Zukunftssicherheit": "hoch — der Ablauf ändert sich nicht",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,52 von 5",
      "Umsatzpotenzial": "kürzere Zahlungsziele denkbar, nicht bezifferbar"
     },
     "datenluecken": [],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 480,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-04.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 35,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-04.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "gemessen",
       "einheit": "—",
       "bezug": "KP-04.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 5,
       "einheit": "1–5",
       "bezug": "KP-04.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 5,
       "einheit": "1–5",
       "bezug": "KP-04.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-04.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-04.TP-3"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 6.6,
     "reife": 4.5,
     "komplexitaet": 2,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (5/5/4/4) = 4.50; komplexitaet = round(11 − 2 × 4.50).",
     "value": {
      "jahresstunden_mitte": 280.0,
      "jahresstunden_spanne": [
       252.0,
       308.0
      ],
      "ist_kosten_mitte": 12040,
      "einsparung_spanne": [
       7585,
       11920
      ],
      "einsparung_mitte": 9752,
      "investition": 4000,
      "amortisation_monate": 4.9,
      "breite_pct": 10
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−10 %) × unteres Ende des Korridors (70 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 6,
     "impact": 6,
     "impact_herleitung": "round((6 + 6.6) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 54,
     "kategorie": "Quick Win",
     "gruppe": "PRIO 1",
     "score_herleitung": "6 × (11 − 2) = 54",
     "user_story": "Als Mitarbeitende im Prozess „Projektdurchführung\" möchte ich rechnungsstellung aus Zeiterfassung und Projektvertrag erzeugen, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Projektdurchführung\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-04.TP-3 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 1
    },
    {
     "id": "P-04",
     "kp_id": "KP-03",
     "tp_id": "KP-03.TP-2",
     "titel": "Onboarding-Checkliste und Fristen automatisch nachhalten",
     "loesungsansatz": "Checkliste je Neukunde erzeugen, Fristen überwachen, Erinnerungen versenden.",
     "klasse": "Regelwerk / Weiterleitung",
     "korridor_pct": [
      70,
      90
     ],
     "lage_im_korridor": "oberes Drittel",
     "lage_begruendung": "Reine Fristenlogik, keine Textdeutung.",
     "aufwand_pt": 3,
     "herkunft_dauer": null,
     "konfidenz_pct": null,
     "nutzwert_kategorien": {
      "Qualität": 5,
      "Durchlaufzeit": 7,
      "Fehlerreduktion": 6,
      "Mitarbeiterzufriedenheit": 6,
      "Compliance / Rechtssicherheit": 7
     },
     "querschnitt": {
      "Zukunftssicherheit": "hoch",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,77 von 5",
      "Umsatzpotenzial": "keines"
     },
     "datenluecken": [
      "Keine Dauer erhoben (`focus_step_duration_source` ist NULL) — deshalb **keine** Value-Zahl, nicht eine sehr breite."
     ],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 40,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-03.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": null,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-03.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-03.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-03.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-03.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-03.TP-2"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 legt nicht fest, wie `impact` entsteht, wenn es keine Value-Zahl gibt. Der Prototyp nimmt den Nutzwert allein; `impact_monetaer = 1` wäre die Alternative und ergäbe hier 3 statt 6 — ein Unterschied von zwei Prioritätsgruppen."
     ],
     "nutzwert": 6.2,
     "reife": 3.25,
     "komplexitaet": 4,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (3/4/3/3) = 3.25; komplexitaet = round(11 − 2 × 3.25).",
     "value": null,
     "value_hinweis": "Keine Value-Zahl: die Dauer ist nicht erhoben. Eine Spanne von ±100 % wäre keine Aussage mehr (ADR-006, 2.3).",
     "impact_monetaer": null,
     "impact": 6,
     "impact_herleitung": "Nur Nutzwert (6.2) — der monetäre Teil-Score entfällt.",
     "score": 42,
     "kategorie": "Quick Win",
     "gruppe": "PRIO 2",
     "score_herleitung": "6 × (11 − 4) = 42",
     "user_story": "Als Mitarbeitende im Prozess „Kunden-Onboarding\" möchte ich onboarding-Checkliste und Fristen automatisch nachhalten, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Kunden-Onboarding\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-03.TP-2 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 2
    },
    {
     "id": "P-09",
     "kp_id": "KP-06",
     "tp_id": "KP-06.TP-1",
     "titel": "Reiseanfragen aus Portalen übernehmen",
     "loesungsansatz": "Anfragen aus den Portalen einlesen und als Vorgang anlegen.",
     "klasse": "Integration",
     "korridor_pct": [
      60,
      85
     ],
     "lage_im_korridor": "Mitte",
     "lage_begruendung": "Schnittstelle je Portal, danach mechanisch.",
     "aufwand_pt": 10,
     "herkunft_dauer": "geschaetzt",
     "konfidenz_pct": 40,
     "nutzwert_kategorien": {
      "Qualität": 6,
      "Durchlaufzeit": 7,
      "Fehlerreduktion": 6,
      "Mitarbeiterzufriedenheit": 6,
      "Compliance / Rechtssicherheit": 2
     },
     "querschnitt": {
      "Zukunftssicherheit": "mittel — hängt an fremden Schnittstellen",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,10 von 5",
      "Umsatzpotenzial": "abhängig von der offenen Lesart des Prozesses"
     },
     "datenluecken": [
      "Dauer geschätzt bei 40 % Konfidenz.",
      "Frequenz 2.600/Jahr bei zehn Mitarbeitenden — trägt die Plausibilitätsschranke des Laufs."
     ],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 2600,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-06.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 150,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-06.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "geschaetzt",
       "einheit": "—",
       "bezug": "KP-06.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_confidence_pct",
       "wert": 40,
       "einheit": "%",
       "bezug": "KP-06.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-06.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-1"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 5.4,
     "reife": 2.25,
     "komplexitaet": 6,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (2/2/3/2) = 2.25; komplexitaet = round(11 − 2 × 2.25).",
     "value": {
      "jahresstunden_mitte": 6500.0,
      "jahresstunden_spanne": [
       3900.0,
       9100.0
      ],
      "ist_kosten_mitte": 279500,
      "einsparung_spanne": [
       100620,
       332605
      ],
      "einsparung_mitte": 216612,
      "investition": 8000,
      "amortisation_monate": 0.4,
      "breite_pct": 40
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−40 %) × unteres Ende des Korridors (60 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 10,
     "impact": 8,
     "impact_herleitung": "round((10 + 5.4) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 40,
     "kategorie": "Strategisch",
     "gruppe": "PRIO 2",
     "score_herleitung": "8 × (11 − 6) = 40",
     "user_story": "Als Mitarbeitende im Prozess „Ressourcen- & Einsatzplanung\" möchte ich reiseanfragen aus Portalen übernehmen, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Ressourcen- & Einsatzplanung\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-06.TP-1 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 3
    },
    {
     "id": "P-08",
     "kp_id": "KP-06",
     "tp_id": "KP-06.TP-4",
     "titel": "Spesen- und Belegerfassung aus Fotos",
     "loesungsansatz": "Foto hochladen, Felder extrahieren, Buchungsvorschlag erzeugen; Freigabe durch die Buchhaltung.",
     "klasse": "Extraktion",
     "korridor_pct": [
      50,
      75
     ],
     "lage_im_korridor": "Mitte",
     "lage_begruendung": "Belege sind vielgestaltig, die Felder aber wenige und feste.",
     "aufwand_pt": 8,
     "herkunft_dauer": "geschaetzt",
     "konfidenz_pct": 70,
     "nutzwert_kategorien": {
      "Qualität": 5,
      "Durchlaufzeit": 6,
      "Fehlerreduktion": 8,
      "Mitarbeiterzufriedenheit": 7,
      "Compliance / Rechtssicherheit": 4
     },
     "querschnitt": {
      "Zukunftssicherheit": "hoch",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,10 von 5",
      "Umsatzpotenzial": "keines"
     },
     "datenluecken": [
      "Reifeskalen fehlen — Umsetzungskomplexität ist **geurteilt**, nicht gemessen."
     ],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 1300,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-06.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 12,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-06.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "geschaetzt",
       "einheit": "—",
       "bezug": "KP-06.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_confidence_pct",
       "wert": 70,
       "einheit": "%",
       "bezug": "KP-06.TP-4"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 6.0,
     "reife": null,
     "komplexitaet": 5,
     "komplexitaet_herkunft": "geurteilt",
     "komplexitaet_begruendung": "BC1 liefert für diesen Teilprozess keine Reifeskalen; geurteilt anhand von BC0s Technologiebasis und Toolstand.",
     "value": {
      "jahresstunden_mitte": 260.0,
      "jahresstunden_spanne": [
       156.0,
       364.0
      ],
      "ist_kosten_mitte": 11180,
      "einsparung_spanne": [
       3354,
       11739
      ],
      "einsparung_mitte": 7546,
      "investition": 6400,
      "amortisation_monate": 10.2,
      "breite_pct": 40
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−40 %) × unteres Ende des Korridors (50 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 6,
     "impact": 6,
     "impact_herleitung": "round((6 + 6.0) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 36,
     "kategorie": "Quick Win",
     "gruppe": "PRIO 2",
     "score_herleitung": "6 × (11 − 5) = 36",
     "user_story": "Als Mitarbeitende im Prozess „Ressourcen- & Einsatzplanung\" möchte ich spesen- und Belegerfassung aus Fotos, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Ressourcen- & Einsatzplanung\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-06.TP-4 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 4
    },
    {
     "id": "P-01",
     "kp_id": "KP-02",
     "tp_id": "KP-02.TP-1",
     "titel": "Lead-Erfassung und -Qualifizierung aus E-Mail-Anfragen ins CRM",
     "loesungsansatz": "Eingangspostfach wird gelesen, Felder extrahiert, Lead im CRM angelegt; Zweifelsfälle landen in einer Prüfliste.",
     "klasse": "Extraktion",
     "korridor_pct": [
      50,
      75
     ],
     "lage_im_korridor": "Mitte",
     "lage_begruendung": "Anfragen kommen in freier Form; Firmenname und Bedarf sind meist eindeutig, die Budgetangabe fast nie.",
     "aufwand_pt": 4,
     "herkunft_dauer": "geschaetzt",
     "konfidenz_pct": 60,
     "nutzwert_kategorien": {
      "Qualität": 7,
      "Durchlaufzeit": 8,
      "Fehlerreduktion": 7,
      "Mitarbeiterzufriedenheit": 6,
      "Compliance / Rechtssicherheit": 3
     },
     "querschnitt": {
      "Zukunftssicherheit": "hoch — das Muster trägt auch für Partneranfragen",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,41 von 5",
      "Umsatzpotenzial": "schnellere Reaktion auf Anfragen, nicht bezifferbar"
     },
     "datenluecken": [],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 180,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-02.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 25,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-02.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "geschaetzt",
       "einheit": "—",
       "bezug": "KP-02.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_confidence_pct",
       "wert": 60,
       "einheit": "%",
       "bezug": "KP-02.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-02.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-02.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-02.TP-1"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-02.TP-1"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 6.2,
     "reife": 3.75,
     "komplexitaet": 4,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (4/4/3/4) = 3.75; komplexitaet = round(11 − 2 × 3.75).",
     "value": {
      "jahresstunden_mitte": 75.0,
      "jahresstunden_spanne": [
       45.0,
       105.0
      ],
      "ist_kosten_mitte": 3225,
      "einsparung_spanne": [
       968,
       3386
      ],
      "einsparung_mitte": 2177,
      "investition": 3200,
      "amortisation_monate": 17.6,
      "breite_pct": 40
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−40 %) × unteres Ende des Korridors (50 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 3,
     "impact": 5,
     "impact_herleitung": "round((3 + 6.2) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 35,
     "kategorie": "Optional",
     "gruppe": "PRIO 2",
     "score_herleitung": "5 × (11 − 4) = 35",
     "user_story": "Als Mitarbeitende im Prozess „Vertrieb & Akquise\" möchte ich lead-Erfassung und -Qualifizierung aus E-Mail-Anfragen ins CRM, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Vertrieb & Akquise\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-02.TP-1 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 5
    },
    {
     "id": "P-07",
     "kp_id": "KP-06",
     "tp_id": "KP-06.TP-2",
     "titel": "Reise- und Einsatzplanung: Verfügbarkeiten und Buchungen abgleichen",
     "loesungsansatz": "Verfügbarkeiten, Einsatzorte und Buchungen in einer Sicht zusammenführen und Konflikte vorab melden.",
     "klasse": "Integration",
     "korridor_pct": [
      60,
      85
     ],
     "lage_im_korridor": "Mitte",
     "lage_begruendung": "Der Abgleich ist mechanisch; die Zusage an den Kunden und die Rücksicht auf persönliche Umstände nicht.",
     "aufwand_pt": 12,
     "herkunft_dauer": "geschaetzt",
     "konfidenz_pct": 60,
     "nutzwert_kategorien": {
      "Qualität": 7,
      "Durchlaufzeit": 9,
      "Fehlerreduktion": 6,
      "Mitarbeiterzufriedenheit": 8,
      "Compliance / Rechtssicherheit": 3
     },
     "querschnitt": {
      "Zukunftssicherheit": "hoch — trägt beide Lesarten des Prozesses",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,10 von 5",
      "Umsatzpotenzial": "mehr abrechenbare Tage denkbar, nicht bezifferbar"
     },
     "datenluecken": [
      "**Fachliche Lesart offen** (Nebel der Karte): interne Einsatzplanung für zehn Mitarbeitende oder Reisebuchung für Kunden — Fallzahl und Systeme unterscheiden sich um Größenordnungen.",
      "BC1 schätzt den Automatisierungsgrad auf 30 %, der Korridor der Klasse „Integration\" liegt bei 60–85 %. Abweichung — Plausibilitätsprobe schlägt an (ADR-006, 2.2)."
     ],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 180,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-06.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 180,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-06.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "geschaetzt",
       "einheit": "—",
       "bezug": "KP-06.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_confidence_pct",
       "wert": 60,
       "einheit": "%",
       "bezug": "KP-06.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-06.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.automation_potential_estimate_pct",
       "wert": 30,
       "einheit": "%",
       "bezug": "KP-06.TP-2 (Plausibilitätsprobe, kein Vorrang)"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": 30,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 6.6,
     "reife": 2.25,
     "komplexitaet": 6,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (2/2/2/3) = 2.25; komplexitaet = round(11 − 2 × 2.25).",
     "value": {
      "jahresstunden_mitte": 540.0,
      "jahresstunden_spanne": [
       324.0,
       756.0
      ],
      "ist_kosten_mitte": 23220,
      "einsparung_spanne": [
       8359,
       27632
      ],
      "einsparung_mitte": 17995,
      "investition": 9600,
      "amortisation_monate": 6.4,
      "breite_pct": 40
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−40 %) × unteres Ende des Korridors (60 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 8,
     "impact": 7,
     "impact_herleitung": "round((8 + 6.6) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 35,
     "kategorie": "Strategisch",
     "gruppe": "PRIO 2",
     "score_herleitung": "7 × (11 − 6) = 35",
     "user_story": "Als Mitarbeitende im Prozess „Ressourcen- & Einsatzplanung\" möchte ich reise- und Einsatzplanung: Verfügbarkeiten und Buchungen abgleichen, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Ressourcen- & Einsatzplanung\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-06.TP-2 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 6
    },
    {
     "id": "P-03",
     "kp_id": "KP-03",
     "tp_id": "KP-03.TP-4",
     "titel": "AVV- und DSGVO-Abwicklung im Onboarding medienbruchfrei machen",
     "loesungsansatz": "AVV aus Vorlage erzeugen, elektronisch zeichnen lassen, Fristen und Nachweise revisionssicher ablegen.",
     "klasse": "Integration",
     "korridor_pct": [
      60,
      85
     ],
     "lage_im_korridor": "Mitte",
     "lage_begruendung": "Der dokumentierte Medienbruch (Unterschrift auf Papier) lässt sich vollständig schließen; die inhaltliche Prüfung bleibt beim Menschen.",
     "aufwand_pt": 5,
     "herkunft_dauer": "gemessen",
     "konfidenz_pct": null,
     "nutzwert_kategorien": {
      "Qualität": 6,
      "Durchlaufzeit": 6,
      "Fehlerreduktion": 7,
      "Mitarbeiterzufriedenheit": 4,
      "Compliance / Rechtssicherheit": 10
     },
     "querschnitt": {
      "Zukunftssicherheit": "hoch — Nachweispflicht bleibt",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,77 von 5",
      "Umsatzpotenzial": "keines"
     },
     "datenluecken": [],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 40,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-03.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 70,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-03.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "gemessen",
       "einheit": "—",
       "bezug": "KP-03.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-03.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-03.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-03.TP-4"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-03.TP-4"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 6.6,
     "reife": 3.75,
     "komplexitaet": 4,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (4/4/4/3) = 3.75; komplexitaet = round(11 − 2 × 3.75).",
     "value": {
      "jahresstunden_mitte": 46.7,
      "jahresstunden_spanne": [
       42.0,
       51.3
      ],
      "ist_kosten_mitte": 2007,
      "einsparung_spanne": [
       1084,
       1876
      ],
      "einsparung_mitte": 1480,
      "investition": 4000,
      "amortisation_monate": 32.4,
      "breite_pct": 10
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−10 %) × unteres Ende des Korridors (60 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 2,
     "impact": 4,
     "impact_herleitung": "round((2 + 6.6) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 28,
     "kategorie": "Optional",
     "gruppe": "PRIO 2",
     "score_herleitung": "4 × (11 − 4) = 28",
     "user_story": "Als Mitarbeitende im Prozess „Kunden-Onboarding\" möchte ich aVV- und DSGVO-Abwicklung im Onboarding medienbruchfrei machen, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Kunden-Onboarding\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-03.TP-4 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 7
    },
    {
     "id": "P-06",
     "kp_id": "KP-04",
     "tp_id": "KP-04.TP-5",
     "titel": "Projektstatusbericht aus Zeiterfassung und Tickets zusammenstellen",
     "loesungsansatz": "Bericht je Projekt und Woche erzeugen, Abweichungen markieren, Versand nach Freigabe durch die Projektleitung.",
     "klasse": "Integration",
     "korridor_pct": [
      60,
      85
     ],
     "lage_im_korridor": "Mitte",
     "lage_begruendung": "Zwei Systeme verbinden und rechnen; der Kommentar an den Kunden bleibt Handarbeit.",
     "aufwand_pt": 7,
     "herkunft_dauer": "aus_system",
     "konfidenz_pct": null,
     "nutzwert_kategorien": {
      "Qualität": 6,
      "Durchlaufzeit": 8,
      "Fehlerreduktion": 6,
      "Mitarbeiterzufriedenheit": 7,
      "Compliance / Rechtssicherheit": 2
     },
     "querschnitt": {
      "Zukunftssicherheit": "hoch",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,52 von 5",
      "Umsatzpotenzial": "keines"
     },
     "datenluecken": [],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 260,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-04.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 20,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-04.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "aus_system",
       "einheit": "—",
       "bezug": "KP-04.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-04.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-04.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-04.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-04.TP-5"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 5.8,
     "reife": 3.75,
     "komplexitaet": 4,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (3/4/4/4) = 3.75; komplexitaet = round(11 − 2 × 3.75).",
     "value": {
      "jahresstunden_mitte": 86.7,
      "jahresstunden_spanne": [
       73.7,
       99.7
      ],
      "ist_kosten_mitte": 3727,
      "einsparung_spanne": [
       1901,
       3643
      ],
      "einsparung_mitte": 2772,
      "investition": 5600,
      "amortisation_monate": 24.2,
      "breite_pct": 15
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−15 %) × unteres Ende des Korridors (60 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 3,
     "impact": 4,
     "impact_herleitung": "round((3 + 5.8) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 28,
     "kategorie": "Optional",
     "gruppe": "PRIO 2",
     "score_herleitung": "4 × (11 − 4) = 28",
     "user_story": "Als Mitarbeitende im Prozess „Projektdurchführung\" möchte ich projektstatusbericht aus Zeiterfassung und Tickets zusammenstellen, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Projektdurchführung\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-04.TP-5 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 8
    },
    {
     "id": "P-05",
     "kp_id": "KP-04",
     "tp_id": "KP-04.TP-2",
     "titel": "Sprint-Retrospektive und Lessons Learned automatisch verdichten",
     "loesungsansatz": "Aus Tickets, Zeiterfassung und Notizen eine Vorlage für die Retrospektive bauen; das Team ergänzt und beschließt.",
     "klasse": "Textgenerierung",
     "korridor_pct": [
      30,
      50
     ],
     "lage_im_korridor": "Mitte",
     "lage_begruendung": "Verdichten geht, das Bewerten der Erkenntnisse bleibt beim Team.",
     "aufwand_pt": 6,
     "herkunft_dauer": "geschaetzt",
     "konfidenz_pct": 50,
     "nutzwert_kategorien": {
      "Qualität": 7,
      "Durchlaufzeit": 5,
      "Fehlerreduktion": 4,
      "Mitarbeiterzufriedenheit": 8,
      "Compliance / Rechtssicherheit": 2
     },
     "querschnitt": {
      "Zukunftssicherheit": "mittel",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,52 von 5",
      "Umsatzpotenzial": "keines"
     },
     "datenluecken": [
      "Dauer geschätzt bei 50 % Konfidenz — die niedrigste im Paket."
     ],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 26,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-04.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 120,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-04.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "geschaetzt",
       "einheit": "—",
       "bezug": "KP-04.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_confidence_pct",
       "wert": 50,
       "einheit": "%",
       "bezug": "KP-04.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-04.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-04.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-04.TP-2"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 4,
       "einheit": "1–5",
       "bezug": "KP-04.TP-2"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 5.2,
     "reife": 3.5,
     "komplexitaet": 4,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (4/3/3/4) = 3.50; komplexitaet = round(11 − 2 × 3.50).",
     "value": {
      "jahresstunden_mitte": 52.0,
      "jahresstunden_spanne": [
       31.2,
       72.8
      ],
      "ist_kosten_mitte": 2236,
      "einsparung_spanne": [
       402,
       1565
      ],
      "einsparung_mitte": 984,
      "investition": 4800,
      "amortisation_monate": 58.5,
      "breite_pct": 40
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−40 %) × unteres Ende des Korridors (30 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 1,
     "impact": 3,
     "impact_herleitung": "round((1 + 5.2) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 21,
     "kategorie": "Optional",
     "gruppe": "PRIO 2",
     "score_herleitung": "3 × (11 − 4) = 21",
     "user_story": "Als Mitarbeitende im Prozess „Projektdurchführung\" möchte ich sprint-Retrospektive und Lessons Learned automatisch verdichten, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Projektdurchführung\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-04.TP-2 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 9
    },
    {
     "id": "P-02",
     "kp_id": "KP-02",
     "tp_id": "KP-02.TP-3",
     "titel": "Angebotsentwurf aus Anfrage und Referenzprojekten erzeugen",
     "loesungsansatz": "Aus Anfrage und drei ähnlichsten Referenzprojekten einen Angebotsentwurf bauen, den die Beratung überarbeitet.",
     "klasse": "Textgenerierung",
     "korridor_pct": [
      30,
      50
     ],
     "lage_im_korridor": "unteres Drittel",
     "lage_begruendung": "Der Entwurf spart das Schreiben, nicht das Kalkulieren und nicht die Abstimmung mit dem Kunden.",
     "aufwand_pt": 9,
     "herkunft_dauer": "aus_system",
     "konfidenz_pct": null,
     "nutzwert_kategorien": {
      "Qualität": 6,
      "Durchlaufzeit": 7,
      "Fehlerreduktion": 5,
      "Mitarbeiterzufriedenheit": 7,
      "Compliance / Rechtssicherheit": 2
     },
     "querschnitt": {
      "Zukunftssicherheit": "mittel — hängt an der Pflege der Referenzsammlung",
      "Abhängigkeiten": "setzt P-01 voraus (Anfrage strukturiert im CRM)",
      "Reifegrad des Prozesses": "3,41 von 5",
      "Umsatzpotenzial": "höhere Angebotsquote denkbar, nicht erhoben"
     },
     "datenluecken": [
      "Referenzprojekte liegen unstrukturiert als Dateien, nicht in der Datenbank."
     ],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 90,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-02.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 95,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-02.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "aus_system",
       "einheit": "—",
       "bezug": "KP-02.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-02.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-02.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-02.TP-3"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 3,
       "einheit": "1–5",
       "bezug": "KP-02.TP-3"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 5.4,
     "reife": 2.75,
     "komplexitaet": 6,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (3/3/2/3) = 2.75; komplexitaet = round(11 − 2 × 2.75).",
     "value": {
      "jahresstunden_mitte": 142.5,
      "jahresstunden_spanne": [
       121.1,
       163.9
      ],
      "ist_kosten_mitte": 6128,
      "einsparung_spanne": [
       1563,
       3523
      ],
      "einsparung_mitte": 2543,
      "investition": 7200,
      "amortisation_monate": 34.0,
      "breite_pct": 15
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−15 %) × unteres Ende des Korridors (30 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 3,
     "impact": 4,
     "impact_herleitung": "round((3 + 5.4) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 20,
     "kategorie": "Zurückgestellt",
     "gruppe": "PRIO 2",
     "score_herleitung": "4 × (11 − 6) = 20",
     "user_story": "Als Mitarbeitende im Prozess „Vertrieb & Akquise\" möchte ich angebotsentwurf aus Anfrage und Referenzprojekten erzeugen, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Vertrieb & Akquise\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-02.TP-3 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 10
    },
    {
     "id": "P-11",
     "kp_id": "KP-06",
     "tp_id": "KP-06.TP-5",
     "titel": "Fahrtenbuch-Nachweise auf Vollständigkeit prüfen",
     "loesungsansatz": "Vorschlagsliste unvollständiger Nachweise erzeugen; Prüfung bleibt manuell.",
     "klasse": "Assistenz",
     "korridor_pct": [
      10,
      30
     ],
     "lage_im_korridor": "Mitte",
     "lage_begruendung": "Jeder Fall wird vom Menschen entschieden; die Lösung schlägt nur vor.",
     "aufwand_pt": 6,
     "herkunft_dauer": "geschaetzt",
     "konfidenz_pct": 50,
     "nutzwert_kategorien": {
      "Qualität": 4,
      "Durchlaufzeit": 3,
      "Fehlerreduktion": 4,
      "Mitarbeiterzufriedenheit": 3,
      "Compliance / Rechtssicherheit": 5
     },
     "querschnitt": {
      "Zukunftssicherheit": "niedrig — entfällt bei Umstellung auf Poolfahrzeuge",
      "Abhängigkeiten": "keine",
      "Reifegrad des Prozesses": "3,10 von 5",
      "Umsatzpotenzial": "keines"
     },
     "datenluecken": [
      "Zwölf Fälle im Jahr — die Bandbreite ist breiter als der Betrag selbst."
     ],
     "herkunftsnachweise": [
      {
       "quelle": "bc1.prozessprofil.frequency_per_year",
       "wert": 12,
       "einheit": "Durchläufe/Jahr",
       "bezug": "KP-06.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.total_duration_minutes",
       "wert": 45,
       "einheit": "Minuten/Durchlauf",
       "bezug": "KP-06.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_source",
       "wert": "geschaetzt",
       "einheit": "—",
       "bezug": "KP-06.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.focus_step_duration_confidence_pct",
       "wert": 50,
       "einheit": "%",
       "bezug": "KP-06.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.documentation_status",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.standardization_level",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.data_availability_score",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-5"
      },
      {
       "quelle": "bc1.prozessprofil.stability_score",
       "wert": 2,
       "einheit": "1–5",
       "bezug": "KP-06.TP-5"
      },
      {
       "quelle": "Setzung ADR-006 · Mischsatz",
       "wert": 43.0,
       "einheit": "EUR/h",
       "bezug": "NoroAI-Profil Kap. 9.2"
      },
      {
       "quelle": "Setzung ADR-006 · Bausatz",
       "wert": 800.0,
       "einheit": "EUR/PT",
       "bezug": "Marktkondition CoE"
      }
     ],
     "bc1_automationsgrad_pct": null,
     "offene_modellfragen": [
      "ADR-006 nennt für `impact_monetaer` absolute Euro-Schwellen, sagt aber nicht, welcher Punkt der Einsparungsspanne eingesetzt wird. Der Prototyp nimmt die Mitte; das untere Ende wäre die vorsichtigere Lesart."
     ],
     "nutzwert": 3.8,
     "reife": 2.0,
     "komplexitaet": 7,
     "komplexitaet_herkunft": "gemessen",
     "komplexitaet_begruendung": "Mittel aus BC1s vier Skalen (2/2/2/2) = 2.00; komplexitaet = round(11 − 2 × 2.00).",
     "value": {
      "jahresstunden_mitte": 9.0,
      "jahresstunden_spanne": [
       5.4,
       12.6
      ],
      "ist_kosten_mitte": 387,
      "einsparung_spanne": [
       23,
       163
      ],
      "einsparung_mitte": 93,
      "investition": 4800,
      "amortisation_monate": 620.2,
      "breite_pct": 40
     },
     "value_hinweis": "Eckenrechnung: unteres Ende der Dauer (−40 %) × unteres Ende des Korridors (10 %), oberes × oberes. Bewusst pessimistisch — sie unterstellt, dass beide Fehler gleichsinnig auftreten.",
     "impact_monetaer": 1,
     "impact": 2,
     "impact_herleitung": "round((1 + 3.8) / 2) — monetärer Teil-Score aus der Mitte der Einsparungsspanne.",
     "score": 8,
     "kategorie": "Zurückgestellt",
     "gruppe": "PRIO 3",
     "score_herleitung": "2 × (11 − 7) = 8",
     "user_story": "Als Mitarbeitende im Prozess „Ressourcen- & Einsatzplanung\" möchte ich fahrtenbuch-Nachweise auf Vollständigkeit prüfen, damit die Handarbeit entfällt und der Ablauf nachvollziehbar bleibt.",
     "akzeptanzkriterien": [
      {
       "text": "**Gegeben** der Ablauf „Ressourcen- & Einsatzplanung\" läuft wie heute, **wenn** die Lösung in Betrieb ist, **dann** entfällt der manuelle Schritt in KP-06.TP-5 für den Regelfall.",
       "messverfahren": "Stichprobe von 20 Durchläufen nach Inbetriebnahme; der Regelfall gilt als getroffen, wenn kein manueller Eingriff nötig war."
      },
      {
       "text": "**Gegeben** ein Zweifelsfall, **wenn** die Lösung ihn nicht eindeutig entscheiden kann, **dann** wird er einem Menschen zur Entscheidung vorgelegt und nicht stillschweigend geraten.",
       "messverfahren": "Prüfliste ist vorhanden und wird bei bewusst unklarer Eingabe befüllt."
      }
     ],
     "rang": 11
    }
   ],
   "schranke": {
    "jahresstunden_gesamt": 7991.9,
    "warnschwelle_h": 7040.0,
    "harte_grenze_h": 17600.0,
    "gerissen": true,
    "text": "Die gerechneten Jahresstunden des Laufs (7.992 h) übersteigen die interne Kapazität von 7.040 h (880 PT). BC2 rechnet durch und weist nichts zurück — die Prüfung ist formal, nicht fachlich. Die Plausibilität liegt bei BC0/BC1."
   }
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
   "teilprozesse": [
    "KP-02.TP-1",
    "KP-02.TP-3"
   ],
   "konzepte": [],
   "potenziale": [],
   "schranke": null
  },
  {
   "paket_id": "a4d09e15-6c3b-4f88-b210-5e9a7d2c4801",
   "paket_kurz": "a4d09e15",
   "company_id": "1a0f8b34-77c2-4e51-9d86-0b3f5c81ea62",
   "mandant": "Übungsmandant (zweite Firma in derselben Datenbank)",
   "uebergeben_am": "2026-09-04T08:31:00Z",
   "gelesen_am": null,
   "zustand": "offen",
   "fassung": 1,
   "teilprozesse": [
    "KP-01.TP-1"
   ],
   "konzepte": [],
   "potenziale": [],
   "schranke": null
  }
 ]
};
