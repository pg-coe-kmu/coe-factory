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
