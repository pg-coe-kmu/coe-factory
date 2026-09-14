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
