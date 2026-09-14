# -*- coding: utf-8 -*-
"""Erzeugt das ID-Verzeichnis der drei Use Cases aus denselben Listen wie das SQL.

Zweck: Das Verzeichnis darf nicht von Hand gepflegt werden. Wer die Stufen in
gen.py aendert, laesst beides neu erzeugen — sonst behauptet das Papier etwas
anderes als die Datenbank.
"""
import io

DIM = [("Technologie", "Technologiebasis Technologiebasis Tools-im-Prozess Tools-im-Prozess "
        "Systemintegration Systemintegration"),
       ("Prozessdaten", "Datenerhebung Datenerhebung Datenbereitstellung Datenbereitstellung "
        "Datenverwendung Datenverwendung"),
       ("Prozessqualität", "Beschreibung Beschreibung Ausführung Ausführung Compliance Compliance"),
       ("Kundinnen und Kunden", "Zentrierung Zentrierung Nutzen Nutzen Partizipation Partizipation"),
       ("Skills und Kultur", "Digital-Skills Digital-Skills Digital-Leadership Digital-Leadership "
        "Digital-Mindset Digital-Mindset")]

W = {"Technologie": [4, 4, 3, 4, 3, 3], "Prozessdaten": [3, 4, 3, 3, 4, 3],
     "Prozessqualität": [3, 3, 3, 3, 3, 3], "Kundinnen und Kunden": [3, 3, 3, 4, 3, 3],
     "Skills und Kultur": [3, 4, 3, 3, 3, 2]}
O = {"Technologie": [3, 3, 3, 3, 3, 2], "Prozessdaten": [2, 3, 2, 3, 2, 2],
     "Prozessqualität": [3, 2, 3, 2, 3, 2], "Kundinnen und Kunden": [3, 3, 2, 3, 3, 2],
     "Skills und Kultur": [2, 2, 3, 2, 2, 2]}
R = {"Technologie": [3, 2, 2, 3, 2, 2], "Prozessdaten": [2, 2, 2, 2, 2, 1],
     "Prozessqualität": [2, 2, 2, 2, 2, 2], "Kundinnen und Kunden": [2, 2, 2, 2, 2, 2],
     "Skills und Kultur": [2, 2, 2, 2, 2, 1]}

FALL = [
 dict(nr=1, titel="Reisebuchung", anfrage="A-2026-01", kp="KP-06", kpname="Personal",
      tp="KP-06.TP-2", tpname="Reise- und Einsatzplanung", stufen=R, rg="2,00",
      ablauf="Reiseanfrage per Mail oder Formular → Verfügbarkeit wird geprüft → Angebot manuell "
             "erstellt → Bestätigung per Mail → Buchung manuell vorgenommen"),
 dict(nr=2, titel="Interne Wissensbasis (RAG)", anfrage="A-2026-02", kp="KP-05",
      kpname="Wissensmanagement", tp="KP-05.TP-1", tpname="Wissenstransfer", stufen=W, rg="3,20",
      ablauf="Frage entsteht → Mitarbeitende durchsuchen Google-Drive-Ordner manuell → Dokumente "
             "einzeln öffnen und lesen → Antwort zusammentragen → mündlich oder per Mail weitergeben"),
 dict(nr=3, titel="Consultant Placement (HR)", anfrage="A-2026-03", kp="KP-06", kpname="Personal",
      tp="KP-06.TP-1", tpname="Neueinstellung und Onboarding", stufen=O, rg="2,50",
      ablauf="Lebenslauf geht unstrukturiert ein → manuell abgelegt → Projektausschreibung wird "
             "gelesen → Lebensläufe manuell gesichtet → Skills mit Anforderungen abgeglichen → "
             "Personalvorschlag zusammengestellt → per Mail an das Team"),
]

t = []
A = t.append
A("# Was zu den drei Use Cases in der Datenbank steht\n")
A("**BC0 · Simeon Ehmer · 24.08.2026 · Mandant NoroAI Consulting GmbH**\n")
A("Jede Zeile, die am 24.08.2026 geschrieben wurde, mit ihrer ID. Erzeugt aus denselben "
  "Listen wie das Einspielskript — das Papier kann der Datenbank nicht widersprechen.\n")
A("**Alles darin sind Testdaten.** Kein Wert ist erhoben oder gemessen. Jede Bewertung trägt das "
  "in ihrem Belegtext; wiederfinden lässt sich der ganze Satz mit\n")
A("```sql\nSELECT * FROM bitkom_bewertungen WHERE erhebung_id = 'E-2026-08';\n```\n")
A("---\n")
A("## Gemeinsame Einträge\n")
A("| Objekt | ID | Inhalt |")
A("|---|---|---|")
A('| Erhebung | **`E-2026-08`** | „Use-Case-Definition der Projektgruppe (Testdaten)“, Stand 24.08.2026, Status `offen`, Methode `gesetzt` |')
A("| Eigner | **`P-07`** | zugeordnet als `eigner` zu `KP-05` und `KP-06`. Bei `KP-05` neben den vorhandenen `P-04` und `P-05` |")
A("")
A("Nicht angelegt: Systeme · Medienbrüche · Belege · BC1-Angaben · Gate-Entscheidungen.\n")

for f in FALL:
    A("---\n")
    A("## Use Case %d — %s\n" % (f["nr"], f["titel"]))
    A("| Objekt | ID | Inhalt |")
    A("|---|---|---|")
    A("| Anfrage | **`%s`** | Originaltext der Use-Case-Beschreibung · `eingang_am` 24.08.2026 · "
      "`eingang_weg` \u201eTestdaten\u201c · `steller_id` `P-07` · Prozessbezug im Hinweisfeld |" % f["anfrage"])
    A("| Kernprozess | `%s` | %s — bestand bereits, unverändert |" % (f["kp"], f["kpname"]))
    A("| Teilprozess | **`%s`** | **%s** \u2014 vorher \u201eTeilprozess %s\u201c, jetzt benannt |"
      % (f["tp"], f["tpname"], f["tp"][-1]))
    A("| Ist-Ablauf | in `%s.notation` | %s |" % (f["tp"], f["ablauf"]))
    A("| Bewertungen | **`%s.I-01`** bis **`%s.I-30`** | 30 Zeilen in `E-2026-08`, Reifegrad **%s** |"
      % (f["tp"], f["tp"], f["rg"]))
    A("")
    A("**Die 30 Bewertungen im Einzelnen**\n")
    A("| ID | Item | Dimension | Kriterium | Stufe |")
    A("|---|---:|---|---|---:|")
    nr = 1
    for dimname, krits in DIM:
        kl = krits.split()
        for i, stufe in enumerate(f["stufen"][dimname]):
            A("| `%s.I-%02d` | %d | %s | %s | **%d** |"
              % (f["tp"], nr, nr, dimname, kl[i].replace("-", " "), stufe))
            nr += 1
    A("")
    A("**Je Dimension**\n")
    A("| Dimension | Summe | Ø |")
    A("|---|---:|---:|")
    for dimname, _ in DIM:
        v = f["stufen"][dimname]
        A("| %s | %d | %.2f |" % (dimname, sum(v), sum(v) / 6.0))
    ges = sum(sum(f["stufen"][d]) for d, _ in DIM)
    A("| **Gesamt** | **%d** | **%.2f** |" % (ges, ges / 30.0))
    A("")

A("---\n")
A("## Wieder entfernen\n")
A("```sql")
A("DELETE FROM bitkom_bewertungen WHERE erhebung_id = 'E-2026-08';")
A("DELETE FROM ref_erhebungen     WHERE erhebung_id = 'E-2026-08';")
A("DELETE FROM ref_anfragen       WHERE anfrage_id IN ('A-2026-01','A-2026-02','A-2026-03');")
A("```\n")
A("Die Teilprozessnamen und die Eignerzuordnung bleiben dabei stehen. Die vorherigen Namen "
  "lauteten `Teilprozess 1` und `Teilprozess 2`.\n")

io.open("BC0_UseCases_DB_Verzeichnis.md", "w", encoding="utf-8").write("\n".join(t))
print("geschrieben, %d Zeilen" % len(t))
