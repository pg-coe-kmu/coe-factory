"""Testset für die Kennzahl pii_erkennung (Issue #50).

POSITIV: (Klasse, Eingabe, Erwartet) mit GENAU EINER PII-Stelle je Fall — die
Quote je Klasse = erkannte Stellen / vorhandene Stellen. Erfundene Namen,
Beispiel-Domains, die dokumentierte Beispiel-IBAN, erfundene Nummern. Die Klasse
"Name ohne Hinweiswort" ist die dokumentierte Lücke aus dem Konzept (heute 0 %);
ändert sich ihre Quote, muss die README-Tabelle mit.
NEGATIV: Interviewsätze ohne PII (alle Skript-Sätze der Demo-Durchläufe +
Grenzfälle), müssen unverändert bleiben (Fehltreffer = 0)."""
POSITIV = [
    ("E-Mail", "Rückfragen an erika.musterfrau@example.org.", "Rückfragen an [E-Mail A]."),
    ("E-Mail", "Sammelpostfach: rechnungen@example.com", "Sammelpostfach: [E-Mail A]"),
    ("E-Mail", "Kontakt max+test@sub.example.org bitte", "Kontakt [E-Mail A] bitte"),
    ("E-Mail", "Postfach muster@büro.example.org", "Postfach [E-Mail A]"),
    ("Telefon", "Erreichbar unter +49 30 1234567.", "Erreichbar unter [Telefon A]."),
    ("Telefon", "Handy 0151 12345678", "Handy [Telefon A]"),
    ("Telefon", "Büro 030 / 1234567", "Büro [Telefon A]"),
    ("Telefon", "Zentrale +49 (0)30 1234567", "Zentrale [Telefon A]"),
    ("Telefon", "Tel. +43 1 234 56 78", "Tel. [Telefon A]"),
    ("IBAN", "Überweisung auf DE89 3704 0044 0532 0130 00.", "Überweisung auf [IBAN A]."),
    ("IBAN", "IBAN de89370400440532013000 ohne Leerzeichen", "IBAN [IBAN A] ohne Leerzeichen"),
    ("IBAN", "Konto AT61 1904 3002 3457 3201 SAP", "Konto [IBAN A] SAP"),
    ("Adresse", "Lieferung an Musterstraße 12, 10115 Berlin.", "Lieferung an [Adresse A]."),
    ("Adresse", "Sitz Musterstraße 12-14, 01234 Bad Beispielstadt", "Sitz [Adresse A]"),
    ("Adresse", "Hauptstr. 5 in 10115 Berlin", "[Adresse A]"),
    ("Adresse", "Karl-Marx-Straße 1", "[Adresse A]"),
    ("Adresse", "Marktplatz 5, 10115 Berlin", "[Adresse A]"),
    ("Name mit Hinweiswort", "Herr Mustermann prüft die Rechnung.", "Herr [Person A] prüft die Rechnung."),
    ("Name mit Hinweiswort", "Frau Dr. Erika Musterfrau gibt frei.", "Frau [Person A] gibt frei."),
    ("Name mit Hinweiswort", "Frau Dr. med. Muster prüft.", "Frau [Person A] prüft."),
    ("Name mit Hinweiswort", "Kollegin Musterfrau übernimmt.", "Kollegin [Person A] übernimmt."),
    ("Name mit Hinweiswort", "Kollege Mustermann prüft.", "Kollege [Person A] prüft."),
    ("Name mit Hinweiswort", "Mein Name ist Max Mustermann.", "Mein Name ist [Person A]."),
    ("Name mit Hinweiswort", "Ich heiße Erika Musterfrau.", "Ich heiße [Person A]."),
    ("Name mit Hinweiswort", "Prof. Dr. Mustermann entscheidet.", "[Person A] entscheidet."),
    ("Name mit Hinweiswort", "Bitte an Hr. Mustermann.", "Bitte an Hr. [Person A]."),
    ("Name mit Hinweiswort", "Bitte an Fr. Musterfrau.", "Bitte an Fr. [Person A]."),
    ("Name mit Hinweiswort", "Herr Müller-Lüdenscheid kommt.", "Herr [Person A] kommt."),
    ("Name mit Hinweiswort", "Frau Muster S-03 prüft.", "Frau [Person A] S-03 prüft."),
    ("E-Mail", "Rückfragen an muster@example.рф.", "Rückfragen an [E-Mail A]."),
    ("Telefon", "Telefon: (030) 1234567", "Telefon: [Telefon A]"),
    ("IBAN", "CH93 0076 2011 6238 5295 7 Excel", "[IBAN A] Excel"),
    ("Adresse", "Sitz: Musterweg 3,12345 Musterstadt", "Sitz: [Adresse A]"),
    ("Name mit Hinweiswort", "Herr René Muster genehmigt.", "Herr [Person A] genehmigt."),
    ("Name ohne Hinweiswort", "Mustermann prüft das.", "[Person A] prüft das."),
    ("Name ohne Hinweiswort", "Das macht Erika Musterfrau.", "Das macht [Person A]."),
    ("Name ohne Hinweiswort", "Freigabe durch Mustermann.", "Freigabe durch [Person A]."),
]

NEGATIV = [
    # Alle Skript-Sätze der drei Demo-Durchläufe (test_demo_durchlaeufe.py)
    "Wir wollen die Reisebuchung automatisieren — es geht um den ganzen Prozess, Ziel ist Zeit sparen.",
    "Wir wollen Antworten aus unserer Wissensbasis automatisieren — es geht um den ganzen Prozess, Ziel ist Zeit sparen.",
    "Wir wollen das Consultant-Staffing beschleunigen — es geht um den ganzen Prozess, Ziel ist Zeit sparen.",
    "Verantwortlich und Ablauf.", "Auslöser, Eingang und Ergebnis.", "Mengen und Dauer.",
    "Der anstrengendste Schritt.", "Beteiligte und Systeme.", "Voraussetzungen.",
    # Werte der Demo-Durchläufe
    "Office Management, Mitarbeiter", "Mail, Buchungsportal, Excel", "Fachexperten, Support",
    "Sharepoint, Mail, Wiki", "Staffing, Vertrieb", "CRM, Skill-Datenbank, Excel",
    "Mitarbeiter plant eine Dienstreise", "Anfrage eines Kollegen oder Kunden",
    "Kundenanfrage nach einem Consultant",
    "Anfrage erfassen, Profile suchen, Matching, Vorschlag versenden",
    "30 pro Monat", "20 pro Woche", "300 pro Jahr", "3 Stunden", "45 Minuten", "60%", "80 %",
    # Grenzfälle: Mengen, Daten, Kennungen, Rollen, Prozessangaben, kleingeschriebene Folgewörter
    "180 Fälle pro Jahr", "12000 Rechnungen im Jahr", "Rechnung Nr. 4711 vom 14.09.2026",
    "seit 2026-09-14", "Termin 01-02-2026", "Termin 01/02/2026 09:30", "Termin am Freitag um 09:30",
    "0,01234567 %", "S-03, S-04", "KP-06.TP-2", "Frau des Kunden ruft an", "Kollegen aus dem Vertrieb",
    "Kollegen Sachbearbeitung Vertrieb prüfen.", "ich bin Sachbearbeiter in der Buchhaltung",
    "Herr der Lage", "Der Arbeitsplatz 3 nutzt S-03.", "System Datenweg 3 verarbeitet 60%.",
    "Büro am Marktplatz 5", "Arbeitsschritt 3 dauert 20 Minuten",
    # Aus der Zweitmeinung 2 (Codex, 14.09.)
    "Die Fertigungsstraße 3 verarbeitet 80 %.", "Seit 01-02-2026 30 Fälle täglich.",
    "Termin 01/02/2026 - 03/02/2026", "Ticket AB12 3456 7890 wurde heute bearbeitet.",
]
