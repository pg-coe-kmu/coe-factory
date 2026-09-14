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
