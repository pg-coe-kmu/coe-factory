# -*- coding: utf-8 -*-
"""
Erzeugt eine ausfuellfertige YAML-Importvorlage fuer EINEN neuen Mandanten.
Struktur passt 1:1 zum Importer (POST /api/import_yaml):
  company / profile / unternehmensdaten / prozesse[ -> teilprozesse[ -> bewertungen{1..30} ] ]

Geruest: 10 Kernprozesse x 5 Teilprozesse x 30 Bitkom-Items.
Leere Items (stufe: ~) werden beim Import uebersprungen -> nur Ausgefuelltes zaehlt.

Aufruf (im Ordner BC0_App):
    python gen_mandant_template.py                 # -> mandant_vorlage.yaml
    python gen_mandant_template.py "Acme GmbH"     # Firmenname vorbelegen
    python gen_mandant_template.py "Acme GmbH" out.yaml
"""
import sys

# 30 Items -> (Dimension, Kriterium) als Kommentar-Label
ITEM_LABEL = {
 1:("1) Technologie","Technologiebasis – eingehende Infos digital"),
 2:("1) Technologie","Technologiebasis – ausgehende Infos digital"),
 3:("1) Technologie","Tools im Prozess – Software-Modellierung"),
 4:("1) Technologie","Tools im Prozess – Automatisierungsgrad"),
 5:("1) Technologie","Systemintegration – Integration der Tools"),
 6:("1) Technologie","Systemintegration – keine Medienbrueche"),
 7:("2) Prozessdaten","Datenerhebung – digitale Erhebung"),
 8:("2) Prozessdaten","Datenerhebung – automatische Erhebung"),
 9:("2) Prozessdaten","Datenbereitstellung – Berichtswesen"),
 10:("2) Prozessdaten","Datenbereitstellung – einfache Nutzung"),
 11:("2) Prozessdaten","Datenverwendung – Schnittstelle/Abruf"),
 12:("2) Prozessdaten","Datenverwendung – Prozessverbesserung"),
 13:("3) Prozessqualitaet","Beschreibung – Umfang Standards"),
 14:("3) Prozessqualitaet","Beschreibung – Detailgrad Standards"),
 15:("3) Prozessqualitaet","Ausfuehrung – Status einsehbar"),
 16:("3) Prozessqualitaet","Ausfuehrung – Stabilitaet bei Last"),
 17:("3) Prozessqualitaet","Compliance – Kontrollen/Pruefinstanzen"),
 18:("3) Prozessqualitaet","Compliance – regulatorische Anforderungen"),
 19:("4) Kund:innen","Zentrierung – Beduerfnis-Dokumentation"),
 20:("4) Kund:innen","Zentrierung – zugeschnittene Angebote"),
 21:("4) Kund:innen","Nutzen – Status fuer Kund:innen einsehbar"),
 22:("4) Kund:innen","Nutzen – erkennbarer Nutzen"),
 23:("4) Kund:innen","Partizipation – Beteiligungsformate"),
 24:("4) Kund:innen","Partizipation – wirksame Massnahmen"),
 25:("5) Skills & Kultur","Digital Skills – Kompetenzen der MA"),
 26:("5) Skills & Kultur","Digital Skills – Verfuegbarkeit"),
 27:("5) Skills & Kultur","Digital Leadership – Fuehrung denkt digital"),
 28:("5) Skills & Kultur","Digital Leadership – Anreize"),
 29:("5) Skills & Kultur","Digital Mindset – digitale Kultur"),
 30:("5) Skills & Kultur","Digital Mindset – konsequente Anwendung"),
}

KP = [
 ("KP-01","Strategieprozess","Steuerungsprozess"),
 ("KP-02","Vertrieb & Lead-Management","Kerngeschäftsprozess"),
 ("KP-03","Kunden-Onboarding","Kerngeschäftsprozess"),
 ("KP-04","Engagement-/Auftragssteuerung","Kerngeschäftsprozess"),
 ("KP-05","Wissensmanagement","Unterstützungsprozess"),
 ("KP-06","HR / Personal","Unterstützungsprozess"),
 ("KP-07","Buchhaltung","Unterstützungsprozess"),
 ("KP-08","IT-Operations","Unterstützungsprozess"),
 ("KP-09","Qualitaetssicherung","Unterstützungsprozess"),
 ("KP-10","Compliance & Datenschutz","Unterstützungsprozess"),
]

def render(firmenname):
    L = []
    a = L.append
    a("# ============================================================")
    a("# BC0 Onboarding – Mandanten-Importvorlage")
    a("# Ausfuellen und im Tool ueber 'Aus YAML importieren' hochladen.")
    a("# Hinweise:")
    a("#  - stufe: 1..5 eintragen, Beleg ist Pflicht (sonst wird die Zeile ignoriert).")
    a("#  - Leere Items (stufe: ~) werden beim Import uebersprungen – einfach offen lassen.")
    a("#  - Nicht benoetigte Kernprozesse/Teilprozesse koennen ganz geloescht werden.")
    a("# ============================================================")
    a("")
    a("company:")
    a("  name: %s" % firmenname)
    a("  branche: \"\"")
    a("  rechtsform: \"\"")
    a("  mitarbeitende: ")
    a("  region: \"\"")
    a("")
    a("profile:")
    a("  geschaeftsmodell: \"\"")
    a("  tech_stack: \"\"")
    a("")
    a("# --- Volles Unternehmensprofil (frei strukturiert) -> Reiter 'Unternehmensdaten' ---")
    a("unternehmensdaten:")
    a("  vision: \"\"")
    a("  mission: \"\"")
    a("  strategische_initiativen: []")
    a("  roadmap:")
    a("    horizont_12_monate: \"\"")
    a("    horizont_24_monate: \"\"")
    a("    horizont_36_monate: \"\"")
    a("  tech_stack:")
    a("    anzahl_tools: ")
    a("    tools: []")
    a("  team: []")
    a("  finanzen: {}")
    a("")
    a("prozesse:")
    for pid, name, kat in KP:
        a("  - process_id: %s" % pid)
        a("    process_name: %s" % name)
        a("    kategorie: %s" % kat)
        a("    owner_name: \"\"")
        a("    owner_role: \"\"")
        a("    trigger: \"\"")
        a("    input: \"\"")
        a("    output: \"\"")
        a("    teilprozesse:")
        for step in range(1, 6):
            a("      - step: %d" % step)
            a("        name: Teilprozess %d" % step)
            a("        notation: \"\"")
            a("        bewertungen:")
            cur_dim = None
            for nr in range(1, 31):
                dim, krit = ITEM_LABEL[nr]
                if dim != cur_dim:
                    a("          # %s" % dim)
                    cur_dim = dim
                a("          %d: { stufe: ~, beleg: \"\" }   # %s" % (nr, krit))
        a("")
    return "\n".join(L) + "\n"

if __name__ == "__main__":
    firma = sys.argv[1] if len(sys.argv) > 1 else "Neuer Mandant GmbH"
    out = sys.argv[2] if len(sys.argv) > 2 else "mandant_vorlage.yaml"
    open(out, "w", encoding="utf-8").write(render(firma))
    print("OK: Vorlage geschrieben -> %s" % out)
