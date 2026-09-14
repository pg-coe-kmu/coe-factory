"""PII-Filter (B2): personenbezogene Angaben werden VOR dem ersten Speichern
durch Platzhalter ersetzt. Erfundene Namen/Adressen/Nummern (Repo-Konvention);
was erkannt wird und was bewusst nicht: design/Konzept-B2-PII-Filter.md."""
from bc1_core.pii import ersetze_pii


def test_email_wird_platzhalter():
    assert (ersetze_pii("Rückfragen an erika.musterfrau@example.org bitte.")
            == "Rückfragen an [E-Mail A] bitte.")


def test_kennungen_je_wert_gleicher_wert_gleiche_kennung():
    assert (ersetze_pii("Kontakt max@example.org, info@example.org, Max@example.org")
            == "Kontakt [E-Mail A], [E-Mail B], [E-Mail A]")


def test_kennungen_laufen_ueber_z_hinaus():
    ergebnis = ersetze_pii(" ".join(f"m{i}@example.org" for i in range(27)))
    assert "[E-Mail Z]" in ergebnis
    assert ergebnis.endswith("[E-Mail AA]")


def test_iban_wird_platzhalter_folgewort_bleibt():
    assert (ersetze_pii("Konto DE89 3704 0044 0532 0130 00 verwenden.")
            == "Konto [IBAN A] verwenden.")
    assert ersetze_pii("de89370400440532013000") == "[IBAN A]"
    assert ersetze_pii("DE89 3704 0044 0532 0130 00") == "[IBAN A]"
    assert ersetze_pii("AT61 1904 3002 3457 3201 SAP") == "[IBAN A] SAP"


def test_telefon_wird_platzhalter():
    assert (ersetze_pii("Erreichbar unter +49 30 1234567 oder 0151 12345678.")
            == "Erreichbar unter [Telefon A] oder [Telefon B].")
    assert ersetze_pii("Büro 030/1234567 oder 030 / 1234567") == "Büro [Telefon A] oder [Telefon B]"
    assert ersetze_pii("+49 (0)30 1234567") == "[Telefon A]"


def test_mengen_daten_dezimalzahlen_bleiben_stehen():
    for text in ("180 Fälle pro Jahr", "3 pro Woche", "45 Minuten", "60%", "80 %",
                 "am 14.09.2026", "seit 2026-09-14", "Termin 01-02-2026",
                 "Termin 01/02/2026 09:30", "Termin am Freitag um 09:30",
                 "0,01234567 %", "12000 Rechnungen im Jahr", "Rechnung Nr. 4711"):
        assert ersetze_pii(text) == text


def test_adresse_mit_strasse_wird_platzhalter():
    assert ersetze_pii("Sitz: Musterstraße 12, 10115 Berlin.") == "Sitz: [Adresse A]."
    assert ersetze_pii("Musterstraße 12-14, 10115 Berlin") == "[Adresse A]"
    assert ersetze_pii("Musterstraße 12, 01234 Bad Beispielstadt") == "[Adresse A]"
    assert ersetze_pii("Hauptstr. 5 in 10115 Berlin") == "[Adresse A]"
    assert ersetze_pii("Karl-Marx-Straße 1") == "[Adresse A]"


def test_weg_und_platz_nur_als_volle_adresse():
    assert ersetze_pii("Marktplatz 5, 10115 Berlin") == "[Adresse A]"
    for text in ("Der Arbeitsplatz 3 nutzt S-03.", "System Datenweg 3 verarbeitet 60%.",
                 "Büro am Marktplatz 5", "Beispielweg 3a"):
        assert ersetze_pii(text) == text


def test_anrede_verraet_den_namen_hinweiswort_bleibt():
    assert (ersetze_pii("Herr Mustermann prüft die Rechnung.")
            == "Herr [Person A] prüft die Rechnung.")
    assert (ersetze_pii("mit Herrn Beispiel und Frau Musterfrau")
            == "mit Herrn [Person A] und Frau [Person B]")
    assert (ersetze_pii("Bitte an Hr. Mustermann und Fr. Musterfrau.")
            == "Bitte an Hr. [Person A] und Fr. [Person B].")


def test_titel_und_mehrteilige_namen_werden_ein_platzhalter():
    assert ersetze_pii("Frau Dr. Erika Musterfrau leitet das.") == "Frau [Person A] leitet das."
    assert ersetze_pii("Frau Dr. med. Muster prüft") == "Frau [Person A] prüft"
    assert ersetze_pii("Kollegin Anna Maria Muster übernimmt.") == "Kollegin [Person A] übernimmt."
    assert ersetze_pii("Herr Müller-Lüdenscheid kommt.") == "Herr [Person A] kommt."


def test_titel_ohne_anrede_und_kennungen_in_textreihenfolge():
    assert ersetze_pii("Prof. Dr. Mustermann entscheidet.") == "[Person A] entscheidet."
    assert (ersetze_pii("Dr. Muster prüft und Frau Beispiel genehmigt.")
            == "[Person A] prüft und Frau [Person B] genehmigt.")


def test_selbstvorstellung_kollege_und_kennungen_neben_namen():
    assert ersetze_pii("Mein Name ist Max Mustermann.") == "Mein Name ist [Person A]."
    assert ersetze_pii("Ich heiße Erika Musterfrau.") == "Ich heiße [Person A]."
    assert ersetze_pii("Kollege Muster übernimmt.") == "Kollege [Person A] übernimmt."
    assert ersetze_pii("Frau Muster S-03 prüft.") == "Frau [Person A] S-03 prüft."
    assert ersetze_pii("Frau Muster KP-06.TP-2 prüft.") == "Frau [Person A] KP-06.TP-2 prüft."


def test_kein_treffer_ohne_hinweiswort_und_bei_kleingeschriebenem_folgewort():
    for text in ("Mustermann prüft das.", "die Frau des Kunden ruft an",
                 "Kollegen aus dem Vertrieb", "Kollegen Sachbearbeitung Vertrieb prüfen.",
                 "ich bin Sachbearbeiter", "Herr der Lage",
                 "Anfrage eines Kollegen oder Kunden"):
        assert ersetze_pii(text) == text


def test_vorhandene_platzhalter_bleiben_und_kollidieren_nicht():
    assert ersetze_pii("Frau [Person A] und Herr Muster") == "Frau [Person A] und Herr [Person B]"


def test_idempotent_und_deterministisch():
    text = "Herr Muster (muster@example.org, 0151 12345678), Musterstraße 1"
    einmal = ersetze_pii(text)
    assert einmal == "Herr [Person A] ([E-Mail A], [Telefon A]), [Adresse A]"
    assert ersetze_pii(einmal) == einmal
    assert ersetze_pii(text) == einmal


def test_leer_und_beliebiger_text_ohne_ausnahme():
    assert ersetze_pii("") == ""
    for text in ("[", "]]", "@", "+", "Dr.", "Herr ", "\n\t", "S-03, S-04",
                 "0" * 40, "[Person ]", "[Person A", "DE00"):
        assert isinstance(ersetze_pii(text), str)   # darf nie werfen


# --- Zweitmeinung 2 (Codex, Code-Review 14.09.) ------------------------------

def test_geschuetztes_leerzeichen_in_iban_per_chr160():
    # Review 2, Important 8: das Zeichen steht NICHT im Quelltext (chr(160)),
    # damit eine stille Editor-Normalisierung im Modul hier sofort rot wird.
    geschuetzt = chr(160).join(["DE89", "3704", "0044", "0532", "0130", "00"])
    assert ersetze_pii(geschuetzt) == "[IBAN A]"
    assert ersetze_pii("Konto " + geschuetzt + " nutzen") == "Konto [IBAN A] nutzen"


def test_email_mit_unicode_oder_punycode_endung():
    # Review 2, Important 5
    assert ersetze_pii("Rückfragen an muster@example.рф.") == "Rückfragen an [E-Mail A]."
    assert ersetze_pii("muster@example.xn--p1ai") == "[E-Mail A]"
    assert ersetze_pii("muster@büro.example.org") == "[E-Mail A]"


def test_telefon_mit_geschuetztem_leerzeichen_und_klammervorwahl_datumsfolgen_bleiben():
    # Review 2, Important 3 + 6
    geschuetzt = chr(160)
    assert ersetze_pii("Kontakt +49 (0)30" + geschuetzt + "1234567") == "Kontakt [Telefon A]"
    assert ersetze_pii("Telefon: (030) 1234567") == "Telefon: [Telefon A]"
    for text in ("Seit 01-02-2026 30 Fälle täglich.", "Termin 01/02/2026 - 03/02/2026",
                 "Termin 01/02/2026 09:30", "Termin 01-02-2026"):
        assert ersetze_pii(text) == text


def test_namen_mit_akzenten_partikeln_und_zusammengesetzten_titeln():
    # Review 2, Critical 2
    assert ersetze_pii("Herr René Muster genehmigt.") == "Herr [Person A] genehmigt."
    assert ersetze_pii("Herr van Muster prüft.") == "Herr [Person A] prüft."
    assert ersetze_pii("Frau Anna von Muster kommt.") == "Frau [Person A] kommt."
    assert ersetze_pii("Frau van der Muster kommt.") == "Frau [Person A] kommt."
    assert ersetze_pii("Dr.-Ing. Mustermann entscheidet.") == "[Person A] entscheidet."
    assert ersetze_pii("Herr der Lage") == "Herr der Lage"      # "der" allein ist kein Partikel

def test_zwei_ibans_nebeneinander_werden_beide_im_ersten_lauf_ersetzt():
    # Review 2, Critical 1: der Regex lief in die zweite IBAN hinein, die
    # Soll-Laengen-Kuerzung gab den Rest ungeprueft zurueck (nur beim ZWEITEN
    # Aufruf ersetzt = Idempotenz verletzt).
    text = "AT61 1904 3002 3457 3201 GB82 WEST 1234 5698 7654 32"
    assert ersetze_pii(text) == "[IBAN A] [IBAN B]"


def test_iban_nur_bekannte_laender_beliebige_und_geschuetzte_leerzeichen():
    # Review 2, Important 4 + 8. Das geschuetzte Leerzeichen kommt hier als
    # Escape, damit eine stille Editor-Normalisierung im Modul sofort rot wird.
    assert ersetze_pii("Ticket AB12 3456 7890 wurde heute bearbeitet.") == "Ticket AB12 3456 7890 wurde heute bearbeitet."
    assert ersetze_pii("DE89  3704  0044  0532  0130  00") == "[IBAN A]"
    assert ersetze_pii("DE89 3704 0044 0532 0130 00") == "[IBAN A]"
