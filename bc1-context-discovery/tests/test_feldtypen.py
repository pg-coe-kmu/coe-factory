"""Feldtypen: je Antworttyp EIN Validator + EIN totaler Normalisierer.

Die Normalisierungs-Regeln sind BC2-relevanter Vertrag (Spec-Tabelle P3):
gespeichert wird IMMER der normalisierte Wert.
"""
from bc1_core.feldtypen import (
    AUSWAHL,
    FREITEXT,
    JA_NEIN,
    LISTE,
    MINUTEN,
    PROZENT_0_100,
    SKALA_1_5,
    ZAHL,
)


# --- ZAHL: normalisiert auf pro Jahr -----------------------------------------

def test_zahl_woche_und_monat_werden_auf_jahr_normalisiert():
    assert ZAHL.normalisiere("50 pro Monat") == "600"
    assert ZAHL.normalisiere("2 pro Woche") == "104"
    assert ZAHL.normalisiere("300 pro Jahr") == "300"
    assert ZAHL.normalisiere("300") == "300"


def test_zahl_unbekannte_periode_bleibt_unveraendert_und_ist_ungueltig():
    # Total: kein Wurf, unverändert zurück — die Validierung lehnt dann ab.
    assert ZAHL.normalisiere("5 pro Tag") == "5 pro Tag"
    assert ZAHL.validator("5 pro Tag") is False
    assert ZAHL.validator("600") is True
    assert ZAHL.validator("keine Ahnung") is False


# --- MINUTEN -----------------------------------------------------------------

def test_minuten_stunden_werden_umgerechnet():
    assert MINUTEN.normalisiere("2 Stunden") == "120"
    assert MINUTEN.normalisiere("45 Minuten") == "45"
    assert MINUTEN.normalisiere("90") == "90"
    assert MINUTEN.normalisiere("1,5 h") == "90"


def test_minuten_andere_einheiten_ungueltig():
    assert MINUTEN.normalisiere("3 Tage") == "3 Tage"
    assert MINUTEN.validator("3 Tage") is False
    assert MINUTEN.validator("120") is True


# --- SKALA_1_5 / PROZENT_0_100 ----------------------------------------------

def test_skala_akzeptiert_nur_ganze_zahlen_eins_bis_fuenf():
    assert SKALA_1_5.normalisiere(" 3 ") == "3"
    assert SKALA_1_5.validator("3") is True
    assert SKALA_1_5.validator("0") is False
    assert SKALA_1_5.validator("6") is False
    assert SKALA_1_5.validator("3,5") is False


def test_prozent_entfernt_prozentzeichen_und_prueft_bereich():
    assert PROZENT_0_100.normalisiere("70%") == "70"
    assert PROZENT_0_100.normalisiere("70 %") == "70"
    assert PROZENT_0_100.validator("70") is True
    assert PROZENT_0_100.validator("101") is False
    assert PROZENT_0_100.validator("-1") is False


# --- JA_NEIN -----------------------------------------------------------------

def test_ja_nein_case_insensitiv_mit_satzzeichen():
    assert JA_NEIN.normalisiere("Ja.") == "ja"
    assert JA_NEIN.normalisiere("  NEIN! ") == "nein"
    assert JA_NEIN.validator("ja") is True
    assert JA_NEIN.validator("vielleicht") is False
    assert JA_NEIN.normalisiere("vielleicht") == "vielleicht"


# --- LISTE / FREITEXT --------------------------------------------------------

def test_liste_trennt_kommas_und_zeilen_und_trimmt():
    assert LISTE.normalisiere("Prüfen, Buchen ,Ablegen") == "Prüfen, Buchen, Ablegen"
    assert LISTE.normalisiere("Prüfen\nBuchen") == "Prüfen, Buchen"
    assert LISTE.validator("Prüfen, Buchen") is True
    assert LISTE.validator("   ") is False


def test_freitext_verlangt_nur_nicht_leer():
    assert FREITEXT.validator("irgendwas") is True
    assert FREITEXT.validator("  ") is False
    assert FREITEXT.normalisiere("irgendwas") == "irgendwas"


# --- AUSWAHL -----------------------------------------------------------------

def test_auswahl_normalisiert_case_insensitiv_auf_kanonische_option():
    typ = AUSWAHL("zeit_sparen", "fehler_senken", "skalieren")
    assert typ.normalisiere("Zeit_Sparen") == "zeit_sparen"
    assert typ.normalisiere("skalieren.") == "skalieren"
    assert typ.validator("zeit_sparen") is True
    assert typ.validator("abkuerzen") is False
    assert typ.normalisiere("abkuerzen") == "abkuerzen"


def test_ja_nein_und_auswahl_tolerieren_typografische_anfuehrungszeichen():
    assert JA_NEIN.normalisiere('„Ja“') == "ja"
    assert AUSWAHL("zeit_sparen").normalisiere('„zeit_sparen“') == "zeit_sparen"
    # Englische/rechte Anführungszeichen (U+201D) — bisher nicht im Strip-Set.
    assert JA_NEIN.normalisiere('“Ja”') == "ja"
    # Einfache typografische Anführungszeichen (U+2018/U+2019) — dito.
    assert JA_NEIN.normalisiere('‘Ja’') == "ja"


def test_mehr_zahlen_input_bleibt_unveraendert_und_ist_ungueltig():
    # Gesamt-Review I2: bei MEHR als einer Zahl im Text wird NICHT mehr
    # die erste Zahl still normalisiert — der Input bleibt unverändert und
    # fällt in der Validierung durch (bestehende Nachfrage-Mechanik).
    assert ZAHL.normalisiere("3 Jahren, 50 pro Monat") == "3 Jahren, 50 pro Monat"
    assert ZAHL.validator("3 Jahren, 50 pro Monat") is False
    assert MINUTEN.normalisiere("1 Stunde 30 Minuten") == "1 Stunde 30 Minuten"
    assert MINUTEN.validator("1 Stunde 30 Minuten") is False
    assert MINUTEN.normalisiere("30-45 Minuten") == "30-45 Minuten"
    # Positiv-Fälle mit genau EINER Zahl bleiben unverändert funktionsfähig.
    assert ZAHL.normalisiere("50 pro Monat") == "600"
    assert MINUTEN.normalisiere("1,5 h") == "90"


def test_normalisierer_sind_total_und_werfen_nie():
    riesenzahl = "9" * 400
    for typ in (ZAHL, MINUTEN, SKALA_1_5, PROZENT_0_100, JA_NEIN, LISTE, FREITEXT):
        assert isinstance(typ.normalisiere(""), str)
        assert isinstance(typ.normalisiere("совершенно anders 💥"), str)
        # float("9"*400) wird zu inf — int(inf) darf trotzdem nie werfen (OverflowError).
        assert isinstance(typ.normalisiere(riesenzahl), str)
        # Verifikations-Critical: deutsches Tausender+Dezimal-Token ("1.234,5")
        # durfte den naiven float(str.replace(",", ".")) im Prozent-Pfad nicht
        # mehr zum Werfen bringen (ValueError: "1.234.5") — Total-Vertrag.
        assert isinstance(typ.normalisiere("1.234,5"), str)
    assert ZAHL.normalisiere(riesenzahl) == riesenzahl
    assert isinstance(ZAHL.validator(riesenzahl), bool)
    # Fix-Welle 6 (M1): die Validator-Lambdas von ZAHL/MINUTEN parsten bisher
    # roh mit float(w.replace(",", ".")) — bei deutscher Tausendergruppierung
    # mit Dezimalstelle ("1.234,5" -> "1.234.5") wirft float() ValueError. Die
    # Sicherheit hing bisher nur an der Aufrufreihenfolge im Extraktor
    # (normalisieren vor validieren), nicht am Code selbst — jetzt throw-frei
    # pinnen wie die Normalisierer.
    for typ in (ZAHL, MINUTEN):
        for wild in ("1.234,5", "1.234.567,89"):
            assert isinstance(typ.validator(wild), bool)
    assert ZAHL.validator("1.234,5") is True
    assert MINUTEN.validator("1.000.000") is True


def test_zahl_und_minuten_overflow_nach_multiplikation_bleibt_unveraendert():
    # Codex I3: Der Endlichkeits-Guard sitzt bisher nur auf dem Eingabewert.
    # Nach der Perioden-Multiplikation (×52/×60) kann das Ergebnis trotzdem
    # zu inf überlaufen — dann NICHT weiterreichen, sonst wirft _formatiere()
    # bei int(inf) einen OverflowError (Total-Vertrag verletzt).
    riesig_woche = "1" + "0" * 307 + " pro Woche"
    riesig_stunden = "1" + "0" * 307 + " Stunden"
    assert ZAHL.normalisiere(riesig_woche) == riesig_woche
    assert ZAHL.validator(riesig_woche) is False
    assert MINUTEN.normalisiere(riesig_stunden) == riesig_stunden
    assert MINUTEN.validator(riesig_stunden) is False


def test_totalitaet_gilt_auch_fuer_riesenzahl_mit_periode():
    # Ergänzt test_normalisierer_sind_total_und_werfen_nie (Codex I3): dieselbe
    # Riesenzahl, aber MIT Perioden-Suffix — der Überlauf passiert dort erst
    # nach der Multiplikation, nicht schon beim reinen Zahl-Parsing.
    riesenzahl = "9" * 400
    assert ZAHL.normalisiere(riesenzahl + " pro Woche") == riesenzahl + " pro Woche"


def test_zahl_periode_nur_mit_wortgrenze_erkannt():
    # Codex I4: "woche" als Teilstring in "Wochenende" darf NICHT als Periode
    # zählen — nur mit Wortgrenze (\b) matchen.
    assert ZAHL.normalisiere("5 am Wochenende") == "5 am Wochenende"
    assert ZAHL.validator("5 am Wochenende") is False


def test_zahl_pro_mit_unbekanntem_wort_lehnt_ab_trotz_bekannter_periode_im_text():
    # Codex I4: "pro Tag" ist die explizit genannte Periode — dass "Jahr" auch
    # im Text vorkommt, darf das nicht überstimmen.
    assert ZAHL.normalisiere("5 pro Tag im Jahr") == "5 pro Tag im Jahr"
    assert ZAHL.validator("5 pro Tag im Jahr") is False


def test_zahl_periode_ohne_pro_wird_weiterhin_erkannt():
    # Regression: ein Periodenwort ohne "pro" (eigenständige Wortgrenze) bleibt
    # akzeptiert — nur "pro <unbekanntes Wort>" wird abgelehnt.
    assert ZAHL.normalisiere("300 im Jahr") == "300"


def test_zahl_deutsche_tausenderpunkte_werden_nicht_als_dezimalpunkt_gelesen():
    # Codex I4: "1.000" ist deutsche Tausendergruppierung, kein Dezimalpunkt —
    # bisher las float() den Punkt als Dezimaltrenner und "1.000" wurde zu 1.0.
    assert ZAHL.normalisiere("1.000 pro Monat") == "12000"


def test_zahl_deutsche_tausenderpunkte_ohne_periode():
    assert ZAHL.normalisiere("1.000") == "1000"


def test_prozent_komma_und_punkt_normalisieren_auf_denselben_kanonischen_wert():
    # Codex I5: "1,5%" behielt bisher das Komma, "1.5%" den Punkt — gleicher
    # Wert, unterschiedliche Strings, false-UNKLAR downstream. Kanonisch: Punkt.
    assert PROZENT_0_100.normalisiere("1,5%") == "1.5"


def test_prozent_punkt_schreibweise_normalisiert_auf_denselben_wert():
    assert PROZENT_0_100.normalisiere("1.5 %") == "1.5"


def test_minuten_angehaengte_stundeneinheit_wird_erkannt():
    # Codex Minor: "1,5h" (Einheit direkt an die Zahl angehängt, ohne Leerzeichen)
    # fiel bisher durch \bh\b — Digit+Buchstabe bilden keine Wortgrenze.
    assert MINUTEN.normalisiere("1,5h") == "90"


def test_minuten_angehaengte_minuteneinheit_wird_erkannt():
    assert MINUTEN.normalisiere("45min") == "45"


def test_prozent_deutsche_tausenderpunkte_mit_komma_wirft_nicht():
    # Verifikations-Critical: _normalisiere_prozent parste bisher naiv mit
    # float(kern.replace(",", ".")) — bei "1.234,5" wird daraus "1.234.5"
    # (zwei Punkte), float() wirft ValueError. Der Fehler eskaliert durch die
    # Extraktor-Naht (fehler_fortsetzbar) und wiederholt sich bei jedem Replay
    # derselben message_id (Gift-Schleife). Fix: über denselben Token-Parser
    # wie ZAHL/MINUTEN (_zahl_aus_token), nie über rohes float().
    ergebnis = PROZENT_0_100.normalisiere("1.234,5%")
    assert isinstance(ergebnis, str)
    assert PROZENT_0_100.validator(ergebnis) is False
    ergebnis_gross = PROZENT_0_100.normalisiere("999.999,99%")
    assert isinstance(ergebnis_gross, str)
    assert PROZENT_0_100.validator(ergebnis_gross) is False


def test_prozent_und_zahl_tausendergruppe_erfordert_fuehrende_ziffer_ungleich_null():
    # Verifikations-Important (derselbe Root-Cause wie oben): die Tausender-
    # Alternative im Zahl-Token akzeptierte bisher eine führende "0"-Gruppe —
    # "0.999" wurde als Tausendertrennung gelesen (0999 → "999"), dabei ist
    # es die Dezimalzahl 0,999. Und "1.000%" wurde vor der Token-Fix-Kette als
    # 1,0 % (statt 1000 %) fehlgelesen.
    assert ZAHL.normalisiere("0.999") == "0.999"
    prozent = PROZENT_0_100.normalisiere("1.000%")
    assert prozent == "1000"
    assert PROZENT_0_100.validator(prozent) is False


def test_zahl_vier_nachkommastellen_bleibt_eine_zahl():
    # Verifikations-Minor: die Tausender-Alternative konsumierte bisher
    # "1.000" aus "1.0000" und ließ die letzte "0" übrig — findall sah zwei
    # Zahlen im Text und lehnte als "mehr als eine Zahl" ab. Fix: negative
    # Lookahead (?!\d) — die Tausendergruppe darf nicht matchen, wenn direkt
    # eine weitere Ziffer folgt (ein nachfolgendes Komma-Dezimal bleibt ok).
    assert ZAHL.normalisiere("1.0000") == "1"


def test_zahl_pro_prueft_jedes_vorkommen_inkl_interpunktion():
    # Codex-Residuum (Fix-Welle 5): der pro-Guard prüfte bisher nur das ERSTE
    # "pro <Wort>" im Text — ein zweites Vorkommen mit unbekanntem Ziel
    # ("pro Mitarbeiter", "pro Tag") oder Interpunktion direkt nach "pro"
    # ("pro/Tag", kein \s+ dazwischen) wurden stillschweigend ignoriert und
    # lieferten einen falschen, aber validen Wert statt einer Ablehnung.
    assert (ZAHL.normalisiere("5 pro Woche und pro Mitarbeiter")
            == "5 pro Woche und pro Mitarbeiter")
    assert ZAHL.validator("5 pro Woche und pro Mitarbeiter") is False
    assert (ZAHL.normalisiere("5 pro Monat und pro Tag")
            == "5 pro Monat und pro Tag")
    assert ZAHL.validator("5 pro Monat und pro Tag") is False
    assert ZAHL.normalisiere("5 pro/Tag im Jahr") == "5 pro/Tag im Jahr"
    assert ZAHL.validator("5 pro/Tag im Jahr") is False


def test_zahl_zwei_verschiedene_perioden_werden_nicht_still_geraten():
    # Fix-Welle 6 (M2): der pro-Guard lässt "pro Woche" UND "pro Jahr" im
    # selben Text durch (beide sind je für sich bekannte Perioden) — bisher
    # gewann dann stillschweigend die ERSTE per .search() gefundene Periode
    # statt die Mehrdeutigkeit zur Nachfrage zu machen (entgegen der Policy).
    assert (ZAHL.normalisiere("5 pro Woche pro Monat")
            == "5 pro Woche pro Monat")
    assert ZAHL.validator("5 pro Woche pro Monat") is False
    assert (ZAHL.normalisiere("50 pro Woche und pro Jahr")
            == "50 pro Woche und pro Jahr")
    assert ZAHL.validator("50 pro Woche und pro Jahr") is False
    # Regressionen: eindeutige Periode bleibt wie bisher funktionsfähig.
    assert ZAHL.normalisiere("50 pro Monat") == "600"
    assert ZAHL.normalisiere("300 im Jahr") == "300"
    # Dieselbe Periode zweimal ist keine Mehrdeutigkeit (Policy: DISTINCT
    # Perioden > 1 lehnt ab, Wiederholung derselben Periode nicht).
    assert ZAHL.normalisiere("5 pro Woche pro Woche") == "260"
