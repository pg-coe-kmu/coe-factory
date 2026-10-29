"""Feldtypen: je Antworttyp EIN Validator + EIN totaler Normalisierer.

Die Normalisierungs-Regeln sind BC2-relevanter Vertrag (Spec-Tabelle P3):
gespeichert wird IMMER der normalisierte Wert.
"""
import pytest

from bc1_core.feldtypen import (
    ANZAHL,
    AUSWAHL,
    FREITEXT,
    Feldtyp,
    JA_NEIN,
    LISTE,
    MINUTEN,
    PROZENT_0_100,
    SKALA_1_5,
    ZAHL,
)
from bc1_service.paket_feldtypen import PROZENT_GANZ_0_100


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


def test_fragezeichen_legt_nichts_fest():
    # Spec 3.1: ein „?“ ist keine Festlegung — Ja/Nein und Auswahl bleiben unveraendert
    # (ungueltig -> Nachfrage). Heute werden „Ja?“ und „KP-03.TP-1?“ gueltig.
    assert JA_NEIN.normalisiere("Ja?") == "Ja?"
    assert JA_NEIN.validator("Ja?") is False
    assert JA_NEIN.normalisiere("ja!?") == "ja!?"
    auswahl = AUSWAHL("KP-03.TP-1")
    assert auswahl.normalisiere("KP-03.TP-1?") == "KP-03.TP-1?"
    assert auswahl.normalisiere("kp-03.tp-1!?") == "kp-03.tp-1!?"


def test_auswahl_schluessel_vergleicht_einheitlich():
    typ = AUSWAHL("zeit_sparen", "geschaetzt")
    for eingabe in ("Zeit sparen", "zeit-sparen", "ZEIT_SPAREN.", "  zeit   sparen "):
        assert typ.normalisiere(eingabe) == "zeit_sparen", eingabe
    # ä als eigenes Zeichen (NFC) und als a + Combining Diaeresis (NFD)
    for eingabe in ("geschätzt", "Geschätzt", "geschätzt"):
        assert typ.normalisiere(eingabe) == "geschaetzt", eingabe
    for eingabe in ("zeit sparen!?", "sparen"):
        assert typ.normalisiere(eingabe) == eingabe, eingabe


def test_auswahl_kurzform_zuerst_raender_dann_schluessel():
    typ = AUSWAHL("geschaetzt", "zeit_sparen")
    assert typ.kurzform("geschätzt") == "geschaetzt"
    assert typ.kurzform("Zeit sparen") == "zeit_sparen"
    assert typ.kurzform(" geschaetzt ") == "geschaetzt"
    assert typ.kurzform("geschaetzt!") == "geschaetzt"
    assert typ.kurzform("geschaetzt..") is None
    assert typ.kurzform("geschaetzt?") is None
    # Kennung und Name gleichlautend: die Kennung gewinnt
    gleich = AUSWAHL("a", "b", namen={"a": "b"})
    assert gleich.kurzform("b") == "b"


def test_auswahl_namen_loesen_auf_die_kennung():
    typ = AUSWAHL("R-01", "R-02", "R-03", "R-04", namen={
        "R-01": "Geschäftsführung", "R-02": "Vertrieb & Innendienst",
        "R-03": "Lager+Versand", "R-04": "Qualität-Prüfung"})
    for eingabe, erwartet in [
        ("Vertrieb & Innendienst", "R-02"), ("vertrieb & innendienst", "R-02"),
        ("Lager+Versand", "R-03"), ("Geschäftsführung", "R-01"),
        ("Geschaeftsfuehrung", "R-01"), ("Qualität Prüfung.", "R-04"),
        ("r-01", "R-01"),
    ]:
        assert typ.normalisiere(eingabe) == erwartet, eingabe
        assert typ.kurzform(eingabe) == erwartet, eingabe
    assert typ.normalisiere("Vertrieb") == "Vertrieb"


def test_auswahl_namen_mehrdeutig_oder_leer():
    typ = AUSWAHL("A", "B", "C", namen={"A": "Gleich", "B": "gleich", "C": ""})
    assert typ.normalisiere("Gleich") == "Gleich"        # trifft zwei Optionen: keine Uebersetzung
    assert typ.kurzform("gleich") is None
    assert typ.normalisiere("") == ""                    # leerer Name wird uebersprungen
    assert typ.kurzform("") is None
    assert typ.normalisiere("c") == "C"                  # Kennungen gehen weiter
    # ohne namen verhaelt sich AUSWAHL wie bisher
    assert AUSWAHL("A", "B").normalisiere("a.") == "A"


def test_auswahl_optionen_mit_gleichem_schluessel_werden_nicht_uebersetzt():
    # Zwei verschiedene Optionen, derselbe Vergleichsschluessel: mehrdeutig, also keine
    # stille Wahl (heute gewinnt die spaetere) — die Eingabe bleibt, ungueltig -> Nachfrage.
    typ = AUSWAHL("a_b", "a-b")
    assert typ.normalisiere("a b") == "a b"
    assert typ.kurzform("a b") is None
    assert typ.validator("a b") is False
    # die exakten Optionen bleiben gueltig
    assert typ.normalisiere("a_b") == "a_b"
    assert typ.normalisiere("a-b") == "a-b"


def test_auswahl_name_darf_keinen_mehrdeutigen_options_schluessel_besetzen():
    # Der Schluessel zweier Optionen bleibt ohne Uebersetzung — auch ein Name
    # mit demselben Schluessel macht ihn nicht eindeutig.
    typ = AUSWAHL("a_b", "a-b", namen={"a_b": "A B"})
    assert typ.normalisiere("a b") == "a b"
    assert typ.normalisiere("A B") == "A B"


def test_auswahl_eingabe_mit_fragezeichen_loest_nie_auf_auch_nicht_ueber_einen_namen():
    # Spec 3.1 gilt auch, wenn ein Name oder Synonym selbst ein „?“ traegt.
    typ = AUSWAHL("a", "b", namen={"a": "Was?"}, synonyme={"b": ("Wie?",)})
    for eingabe in ("Was?", "was?", "Wie?"):
        assert typ.normalisiere(eingabe) == eingabe, eingabe
        assert typ.kurzform(eingabe) is None, eingabe
    assert typ.normalisiere("a") == "a"


def test_auswahl_namen_und_synonyme_fremder_optionen_zaehlen_nicht():
    # Ein Eintrag, dessen Schluessel keine der Optionen ist, kommt nicht in die Tabelle.
    typ = AUSWAHL("a", "b", namen={"zzz": "Fremd"}, synonyme={"yyy": ("Anders",)})
    assert typ.normalisiere("Fremd") == "Fremd"
    assert typ.kurzform("Fremd") is None
    assert typ.normalisiere("Anders") == "Anders"
    assert typ.normalisiere("a") == "a"


def test_auswahl_prueft_nur_optionen():
    # (Regression) Namen werden nur uebersetzt; gueltig bleiben allein die Kennungen.
    typ = AUSWAHL("R-01", namen={"R-01": "Geschäftsführung"})
    assert typ.validator("Geschäftsführung") is False
    assert typ.validator("R-01") is True


def test_auswahl_synonyme():
    typ = AUSWAHL("mail", "pdf", synonyme={"mail": ("E-Mail", "Email")})
    for eingabe in ("E-Mail", "email", "Email.", "e mail"):
        assert typ.normalisiere(eingabe) == "mail", eingabe
        assert typ.kurzform(eingabe) == "mail", eingabe
    assert typ.normalisiere("E-Mail?") == "E-Mail?"
    assert typ.validator("E-Mail") is False
    # ein Synonym, das zwei Optionen traefe, wird verworfen
    zwei = AUSWAHL("a", "b", synonyme={"a": ("x",), "b": ("X",)})
    assert zwei.normalisiere("x") == "x"


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


def test_zahl_und_minuten_lehnen_reine_riesenzahl_ohne_periode_ab():
    # K-J (Task-11-Review, gemessen): Die bestehenden Ueberlauftests tragen ein
    # Periodenwort ("pro Woche", "Stunden") — daran scheitert schon _nur_zahl.
    # Eine REINE Ziffernfolge jenseits des float-Bereichs passiert dagegen das
    # Muster, und inf >= 0 ist wahr: der Wert gilt als gueltig, wird vom
    # Normalisierer (zu Recht, Total-Vertrag) unveraendert durchgereicht, und
    # Decimal() scheitert am stehengebliebenen Komma. Folge im Betrieb:
    # ProfilWriteError -> 503 im Abschluss-Turn; die Frage-Turns davor uebergehen
    # ihn seit 25.10. (Plan Konvertierung im Frage-Turn), das Profil bleibt offen.
    ueberlauf = "9" * 309 + ",25"
    assert ZAHL.validator(ueberlauf) is False
    assert MINUTEN.validator(ueberlauf) is False


def test_zahl_lehnt_ziffernfolge_jenseits_der_spaltenkapazitaet_ab():
    # Zweite gemessene K-J-Variante: diese Zahl IST konvertierbar (Decimal kann
    # sie), aber die numeric-Spalte lehnt sie ab (131072 Vorkommastellen).
    # Sie faellt heute schon durch die Endlichkeitspruefung — der Test haelt
    # fest, dass "gueltig" auch "speicherbar" bedeutet.
    assert ZAHL.validator("1" * 140000) is False


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


def test_zahl_liest_keine_zahl_aus_saetzen():
    # Spec 3.4: nur die ganze Eingabe in der geschlossenen Grammatik zaehlt; ein Satz
    # mit Zahl bleibt unveraendert (ungueltig -> Nachfrage), statt still falsch zu werden.
    for satz in ("jeden 2. Monat", "20 Leads pro Woche", "jede Woche 2", "pro Monat 30",
                 "so 30 im Monat", "etwa 20 Anfragen pro Monat"):
        assert ZAHL.normalisiere(satz) == satz, satz
        assert ZAHL.validator(satz) is False, satz


def test_zahl_eindeutige_formen_bleiben():
    # (Regression) Spec 3.4: was eindeutig und heute gueltig ist, bleibt gueltig.
    for eingabe, erwartet in [
        ("2x die Woche", "104"), ("2/Woche", "104"), ("2 mal in der Woche", "104"),
        ("2 mal im Monat", "24"), ("300", "300"), ("300 im Jahr", "300"),
        ("etwa 4 pro Monat.", "48"),
    ]:
        assert ZAHL.normalisiere(eingabe) == erwartet, eingabe
        assert ZAHL.validator(ZAHL.normalisiere(eingabe)) is True, eingabe


def test_zahl_bewusst_geaenderte_bestandsfaelle_sind_nun_ungueltig():
    # Spec 3.4 (Bestandserwartungen bewusst umgekehrt): frueher "5 pro Woche pro Woche"
    # -> 260 (dieselbe Periode zweimal) und "30 pro Monat [Person A]" -> 360 (Zahl gewinnt
    # neben einem PII-Platzhalter). Die geschlossene Grammatik nimmt beides nicht an.
    for eingabe in ("5 pro Woche pro Woche", "30 pro Monat [Person A]"):
        assert ZAHL.normalisiere(eingabe) == eingabe, eingabe
        assert ZAHL.validator(eingabe) is False, eingabe


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


# --- B2 PII-Filter: Platzhalter passieren die Normalisierer ------------------

def test_pii_platzhalter_passieren_text_und_listenfelder_unveraendert():
    assert FREITEXT.normalisiere("[Person A]") == "[Person A]"
    assert LISTE.normalisiere("[Person A], [Person B]") == "[Person A], [Person B]"
    assert ZAHL.normalisiere("[Telefon A]") == "[Telefon A]"
    assert JA_NEIN.normalisiere("[Person A]") == "[Person A]"


# --- ANZAHL: reine Anzahl, keine Periode -------------------------------------

@pytest.mark.parametrize("eingabe, erwartet", [
    ("0", "0"),
    ("1", "1"),
    ("3", "3"),
    ("2,5", "2.5"),
    ("1.000", "1000"),
    ("3 Fälle", "3"),
    ("1 Fall", "1"),
    ("3 Vorgänge pro Durchlauf", "3"),
    ("etwa 3", "3"),
    ("ca. 3 Fälle", "3"),
    ("im Schnitt 2 Vorgänge je Durchlauf", "2"),
])
def test_anzahl_gueltig(eingabe, erwartet):
    assert ANZAHL.name == "anzahl"
    assert ANZAHL.normalisiere(eingabe) == erwartet
    assert ANZAHL.validator(ANZAHL.normalisiere(eingabe)) is True


@pytest.mark.parametrize("eingabe", [
    "5 pro Woche",
    "15 im Monat",
    "40 im Jahr",
    "5/Monat",
    "5 täglich",
    "3 %",
    "3 Stunden",
    "1 Fall pro Woche",
    "-1",
    "",
    "3 oder 4",
    "9" * 400,
])
def test_anzahl_ungueltig(eingabe):
    assert ANZAHL.validator(ANZAHL.normalisiere(eingabe)) is False


# Abschlussplan „Neu 24.10. — aus C1a" (4b), entschieden 25.10.: „ca" auch ohne Punkt.
@pytest.mark.parametrize("eingabe", ["ca 3", "ca 3 Fälle", "CA 3"])
def test_anzahl_ca_ohne_punkt(eingabe):
    assert ANZAHL.normalisiere(eingabe) == "3"
    assert ANZAHL.validator(ANZAHL.normalisiere(eingabe)) is True


# Ebenso (4b): genau ein Satzzeichen „." oder „!" am Ende; der Dezimalpunkt bleibt Zahl.
@pytest.mark.parametrize("eingabe, erwartet", [
    ("3 Fälle.", "3"),
    ("3.", "3"),
    ("etwa 3.", "3"),
    ("3 Fälle!", "3"),
    ("ca 3 Fälle je Durchlauf.", "3"),
    ("1.000.", "1000"),
    ("2,5.", "2.5"),
])
def test_anzahl_mit_satzzeichen_am_ende(eingabe, erwartet):
    assert ANZAHL.normalisiere(eingabe) == erwartet
    assert ANZAHL.validator(ANZAHL.normalisiere(eingabe)) is True


# Grenze von (4b): ein Fragezeichen drueckt Zweifel aus (Nachfrage ist richtig), mehr als
# ein Zeichen oder ein Komma bleibt unklar, ebenso „ca" ohne Leerzeichen.
@pytest.mark.parametrize("eingabe", ["3?", "3..", "3,", "3 Fälle.!", "ca3"])
def test_anzahl_bleibt_bei_zweifel_und_mehreren_zeichen_ungueltig(eingabe):
    assert ANZAHL.validator(ANZAHL.normalisiere(eingabe)) is False


# Pruefung (4b): das Satzzeichen steht direkt am Wort oder an der Zahl — mit Leerzeichen
# davor bleibt es eine Nachfrage; „ca" nimmt hoechstens einen Punkt.
@pytest.mark.parametrize("eingabe", ["3 .", "3 Fälle .", "3 !", "ca.. 3"])
def test_anzahl_leerzeichen_vor_satzzeichen_und_doppelter_punkt_bleiben_ungueltig(eingabe):
    assert ANZAHL.validator(ANZAHL.normalisiere(eingabe)) is False


# Pruefung (4b): der Dezimalpunkt bleibt Teil der Zahl, erst ein Punkt ohne Ziffer
# dahinter ist das Satzzeichen.
@pytest.mark.parametrize("eingabe", ["2.5", "2.5."])
def test_anzahl_dezimalpunkt_bleibt_teil_der_zahl(eingabe):
    assert ANZAHL.normalisiere(eingabe) == "2.5"
    assert ANZAHL.validator(ANZAHL.normalisiere(eingabe)) is True


# --- kurzform: Kurzantwort ohne KI (Task 1) -----------------------------------

def test_freie_typen_haben_keine_kurzform():
    assert FREITEXT.kurzform is None
    assert LISTE.kurzform is None


@pytest.mark.parametrize("eingabe, erwartet", [
    ("Ja", "ja"), ("nein.", "nein"), ("JA!", "ja"),
    ("Ja, aber selten", None), ("ja?", None), ("jein", None), ("", None),
    ("ja..", None), ("ja,", None), ("Ja !", None),
])
def test_kurzform_ja_nein(eingabe, erwartet):
    assert JA_NEIN.kurzform(eingabe) == erwartet


@pytest.mark.parametrize("eingabe, erwartet", [
    ("4", "4"), ("4.", "4"),
    ("eher 4", None), ("etwa 4", None), ("4 von 5", None), ("6", None),
    ("4?", None), ("4..", None),
])
def test_kurzform_skala(eingabe, erwartet):
    assert SKALA_1_5.kurzform(eingabe) == erwartet


@pytest.mark.parametrize("eingabe, erwartet", [
    ("geschaetzt", "geschaetzt"), ("KP-01.TP-1", "KP-01.TP-1"),
    ("kp-01.tp-1.", "KP-01.TP-1"),
    ("KP-01.TP-1?", None), ("KP-01.TP-9", None), ("Erfassen", None),
    ("geschätzt", "geschaetzt"), ("geschaetzt..", None),
])
def test_kurzform_auswahl(eingabe, erwartet):
    typ = AUSWAHL("geschaetzt", "KP-01.TP-1")
    assert typ.kurzform(eingabe) == erwartet
    assert AUSWAHL().kurzform("") is None
    assert AUSWAHL().kurzform("x") is None


@pytest.mark.parametrize("eingabe, erwartet", [
    ("1", "1"), ("etwa 3 Fälle", "3"), ("ca 3.", "3"),
    ("5 pro Woche", None), ("3?", None), ("ein Fall, manchmal 3", None),
])
def test_kurzform_anzahl(eingabe, erwartet):
    assert ANZAHL.kurzform(eingabe) == erwartet


@pytest.mark.parametrize("wort", [
    "etwa", "ca.", "ca", "circa", "ungefähr", "ungefaehr", "rund",
    "im Schnitt", "durchschnittlich",
])
def test_anzahl_kennt_alle_naeherungswoerter(wort):
    assert ANZAHL.normalisiere(f"{wort} 3") == "3"
    assert ANZAHL.kurzform(f"{wort} 3") == "3"


@pytest.mark.parametrize("eingabe, erwartet", [
    ("70", "70"), ("ca. 70 %", "70"), ("70%", "70"), ("70 Prozent", "70"),
    ("70.", "70"), ("im Schnitt 70 %", "70"),
    ("circa 70", "70"), ("ungefähr 70", "70"), ("ungefaehr 70", "70"),
    ("rund 70", "70"), ("durchschnittlich 70", "70"), ("etwa 70", "70"),
    ("ca 70", "70"),
    ("150 %", "150"), ("70,5 %", "70,5"),
    ("70 bis 80", None), ("70?", None), ("etwa 70 bis 80 %", None),
    ("70 %..", None),
])
def test_kurzform_prozent(eingabe, erwartet):
    assert PROZENT_0_100.kurzform(eingabe) == erwartet


@pytest.mark.parametrize("eingabe, rein, minuten", [
    ("3 Stunden", "3 Stunden", "180"), ("ca 90 Min.", "90 Min", "90"),
    ("45min", "45 min", "45"), ("1,5h", "1,5 h", "90"),
    ("40 Stunden", "40 Stunden", "2400"),
    ("im Schnitt 2 Std.", "2 Std", "120"),
    ("circa 3 Stunden", "3 Stunden", "180"),
    ("ungefähr 3 Stunden", "3 Stunden", "180"),
    ("ungefaehr 3 Stunden", "3 Stunden", "180"),
    ("rund 3 Stunden", "3 Stunden", "180"),
    ("durchschnittlich 3 Stunden", "3 Stunden", "180"),
    ("etwa 3 Stunden", "3 Stunden", "180"),
    ("3", None, None), ("40", None, None), ("90 min..", None, None),
    ("2 Std.!", None, None),
    ("Der Prozess dauert 3 Stunden.", None, None),
    ("nicht 3 Stunden", None, None), ("3 Stunden?", None, None),
    ("1 Stunde 30 Minuten", None, None),
    ("3 Stunden, der Gesamtprozess dauert aber eine Woche", None, None),
])
def test_kurzform_minuten(eingabe, rein, minuten):
    assert MINUTEN.kurzform(eingabe) == rein
    if rein is not None:
        assert MINUTEN.normalisiere(rein) == minuten


@pytest.mark.parametrize("eingabe, rein, jahr", [
    ("2 pro Monat", "2 pro Monat", "24"),
    ("2 mal im Monat", "2 pro Monat", "24"),
    ("2mal im Monat", "2 pro Monat", "24"),
    ("2mal pro Woche", "2 pro Woche", "104"),
    ("2-mal je Jahr", "2 pro Jahr", "2"),
    ("etwa 4 pro Monat", "4 pro Monat", "48"),
    ("ca. 4 pro Monat", "4 pro Monat", "48"),
    ("ca 4 pro Monat", "4 pro Monat", "48"),
    ("circa 4 pro Monat", "4 pro Monat", "48"),
    ("ungefähr 4 pro Monat", "4 pro Monat", "48"),
    ("ungefaehr 4 pro Monat", "4 pro Monat", "48"),
    ("rund 4 pro Monat", "4 pro Monat", "48"),
    ("im Schnitt 4 pro Monat", "4 pro Monat", "48"),
    ("durchschnittlich 4 pro Monat", "4 pro Monat", "48"),
    ("2", None, None), ("2 pro Tag", None, None),
    ("2 mal pro Monat, im Dezember mehr", None, None),
    ("Der Gesamtprozess läuft 2 mal pro Monat", None, None),
    ("2 pro Monat?", None, None), ("2 pro Monat..", None, None),
])
def test_kurzform_haeufigkeit(eingabe, rein, jahr):
    assert ZAHL.kurzform(eingabe) == rein
    if rein is not None:
        assert ZAHL.normalisiere(rein) == jahr


@pytest.mark.parametrize("eingabe, rein, jahr", [
    ("2x pro Monat", "2 pro Monat", "24"),
    ("1x im Jahr", "1 pro Jahr", "1"),
    ("2 x pro Woche", "2 pro Woche", "104"),
    ("2X je Monat", "2 pro Monat", "24"),
    ("etwa 3x im Monat", "3 pro Monat", "36"),
    ("2x pro Monat.", "2 pro Monat", "24"),
    ("2x", None, None), ("2x pro Tag", None, None),
    ("2xx pro Monat", None, None), ("x pro Monat", None, None),
    ("2x pro Monat?", None, None), ("2x pro Monat..", None, None),
    ("0x10 pro Monat", None, None),
])
def test_kurzform_haeufigkeit_mit_x(eingabe, rein, jahr):
    assert ZAHL.kurzform(eingabe) == rein
    if rein is not None:
        assert ZAHL.normalisiere(rein) == jahr


@pytest.mark.parametrize("eingabe, rein, jahr", [
    ("2x die Woche", "2 pro Woche", "104"),
    ("2/Woche", "2 pro Woche", "104"),
    ("2 / Woche", "2 pro Woche", "104"),
    ("2 mal in der Woche", "2 pro Woche", "104"),
    ("2 mal im Monat", "2 pro Monat", "24"),
    ("3 mal den Monat", "3 pro Monat", "36"),
    ("300 im Jahr", "300 pro Jahr", "300"),
    ("etwa 4 pro Monat.", "4 pro Monat", "48"),
    ("2imMonat", None, None), ("2dieWoche", None, None),
    ("2-3x pro Woche", None, None), ("2 pro/Woche", None, None),
])
def test_kurzform_haeufigkeit_erweiterte_verbindungen(eingabe, rein, jahr):
    # Spec 3.4: Kurzform und Normalisierer teilen EINE Grammatik.
    assert ZAHL.kurzform(eingabe) == rein
    if rein is None:
        assert ZAHL.normalisiere(eingabe) == eingabe
    else:
        assert ZAHL.normalisiere(eingabe) == jahr
        assert ZAHL.normalisiere(rein) == jahr


@pytest.mark.parametrize("typ", [
    JA_NEIN, SKALA_1_5, AUSWAHL("a"), ANZAHL, PROZENT_0_100, MINUTEN, ZAHL,
])
@pytest.mark.parametrize("eingabe", [
    "", "\n", "9" * 400, "9" * 400 + " Stunden", "äöü?…", "1.000.000 pro Jahr",
])
def test_kurzformen_sind_total(typ, eingabe):
    ergebnis = typ.kurzform(eingabe)
    assert ergebnis is None or isinstance(ergebnis, str)


# Spec 3.4, Invariante „Normalisierer enthaelt Kurzform“: die Eingaben der Kurzform-Tests oben
# (Rohtext, nicht die Zwischenform).
_AUSWAHL_KURZFORM = AUSWAHL("geschaetzt", "KP-01.TP-1")
_KURZFORM_EINGABEN = [
    (JA_NEIN, e) for e in (
        "Ja", "nein.", "JA!", "Ja, aber selten", "ja?", "jein", "", "ja..", "ja,", "Ja !")
] + [
    (SKALA_1_5, e) for e in ("4", "4.", "eher 4", "etwa 4", "4 von 5", "6", "4?", "4..")
] + [
    (_AUSWAHL_KURZFORM, e) for e in (
        "geschaetzt", "KP-01.TP-1", "kp-01.tp-1.", "KP-01.TP-1?", "KP-01.TP-9",
        "Erfassen", "geschätzt", "geschaetzt..")
] + [
    (ANZAHL, e) for e in (
        "1", "etwa 3 Fälle", "ca 3.", "5 pro Woche", "3?", "ein Fall, manchmal 3")
] + [
    (PROZENT_0_100, e) for e in (
        "70", "ca. 70 %", "70%", "70 Prozent", "70.", "im Schnitt 70 %", "circa 70",
        "ungefähr 70", "ungefaehr 70", "rund 70", "durchschnittlich 70", "etwa 70", "ca 70",
        "150 %", "70,5 %", "70 bis 80", "70?", "etwa 70 bis 80 %", "70 %..")
] + [
    (MINUTEN, e) for e in (
        "3 Stunden", "ca 90 Min.", "45min", "1,5h", "40 Stunden", "im Schnitt 2 Std.",
        "circa 3 Stunden", "ungefähr 3 Stunden", "ungefaehr 3 Stunden", "rund 3 Stunden",
        "durchschnittlich 3 Stunden", "etwa 3 Stunden", "3", "40", "90 min..", "2 Std.!",
        "Der Prozess dauert 3 Stunden.", "nicht 3 Stunden", "3 Stunden?",
        "1 Stunde 30 Minuten", "3 Stunden, der Gesamtprozess dauert aber eine Woche")
] + [
    (ZAHL, e) for e in (
        "2 pro Monat", "2 mal im Monat", "2mal im Monat", "2mal pro Woche", "2-mal je Jahr",
        "etwa 4 pro Monat", "ca. 4 pro Monat", "ca 4 pro Monat", "circa 4 pro Monat",
        "ungefähr 4 pro Monat", "ungefaehr 4 pro Monat", "rund 4 pro Monat",
        "im Schnitt 4 pro Monat", "durchschnittlich 4 pro Monat", "2", "2 pro Tag",
        "2 mal pro Monat, im Dezember mehr", "Der Gesamtprozess läuft 2 mal pro Monat",
        "2 pro Monat?", "2 pro Monat..", "2x pro Monat", "1x im Jahr", "2 x pro Woche",
        "2X je Monat", "etwa 3x im Monat", "2x pro Monat.", "2x", "2x pro Tag",
        "2xx pro Monat", "x pro Monat", "2x pro Monat?", "2x pro Monat..", "0x10 pro Monat")
]


@pytest.mark.parametrize("typ, eingabe", _KURZFORM_EINGABEN)
def test_normalisierer_umfasst_kurzform(typ, eingabe):
    kurz = typ.kurzform(eingabe)
    if kurz is None:
        return
    ergebnis = typ.normalisiere(eingabe)
    zwischen = typ.normalisiere(kurz)
    if typ.validator(zwischen):
        assert typ.validator(ergebnis), (eingabe, ergebnis)
        assert ergebnis == zwischen
    else:
        # z. B. „150 %“ -> „150“: der Pruefer lehnt ab, also bleibt auch der Rohtext ungueltig.
        assert not typ.validator(ergebnis), (eingabe, ergebnis)


def test_antwortform_ja_nein_skala_anzahl():
    assert JA_NEIN.antwortform == "ja oder nein"
    assert SKALA_1_5.antwortform == "eine Ziffer von 1 bis 5"
    assert ANZAHL.antwortform == "nur eine Zahl, ohne Einheit, z. B. ‚5‘"


def test_antwortform_zahl_minuten():
    assert ZAHL.antwortform == (
        "Zahl pro Woche, pro Monat oder pro Jahr, z. B. ‚2 pro Monat‘")
    assert MINUTEN.antwortform == (
        "Dauer als Zahl mit ‚Minuten‘ oder ‚Stunden‘, z. B. ‚90 Minuten‘")


def test_antwortform_prozent():
    assert PROZENT_0_100.antwortform == "Zahl von 0 bis 100"
    assert PROZENT_GANZ_0_100.antwortform == "ganze Zahl von 0 bis 100"


def test_antwortform_auswahl():
    assert AUSWAHL("a", "b").antwortform == "genau eine von: a, b"


def test_antwortform_auswahl_nennt_namen():
    typ = AUSWAHL("KP-01.TP-1", "KP-01.TP-2", namen={"KP-01.TP-1": "Anfrage erfassen"})
    assert typ.antwortform == ("genau eine von: KP-01.TP-1 (= Anfrage erfassen), "
                               "KP-01.TP-2")


def test_antwortform_freie_typen():
    assert FREITEXT.antwortform == "Text"
    assert LISTE.antwortform == "Liste, durch Kommas getrennt"


def test_antwortform_ist_pflichtmerkmal():
    with pytest.raises(TypeError):
        Feldtyp("x", lambda w: True, lambda w: w)
