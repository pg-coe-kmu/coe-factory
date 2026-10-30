"""Pruefwerkzeug Schicht b (Spec Antwortformen, Abschnitt 6) gegen eine Test-KI.

Die Test-KI kennt das gefragte Feld: Extraktion nach (zuletzt gefragtes Feld,
Nachricht). `FakeLLM` indiziert nur nach dem Text und taugt hier nicht, weil
dieselbe Antwort („eine halbe Stunde“) bei zwei Feldern zwei Felder trifft."""
from pathlib import Path

from bc1_core.core import zuletzt_gefragt
from bc1_core.feldtypen import FREITEXT, MINUTEN
from bc1_core.llm import ExtractionCandidate
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.store import InMemoryStateStore
from werkzeuge.antwortpruefung import Erwartung, bewerte, pruefe_nachfragetext, spiele
from werkzeuge.katalog import baue_paket, lade_katalog

KATALOG = lade_katalog(Path(__file__).parent / "daten" / "antwortkatalog.json")
DISCOVERY = baue_paket(KATALOG["kontext"])


class FeldFakeLLM:
    """Test-KI mit Feldbezug: Extraktion nach (zuletzt gefragtes Feld, Nachricht)."""

    def __init__(self, extraktionen, fehler=()):
        self.extraktionen = extraktionen
        self.fehler = list(fehler)  # je `antworte`-Aufruf: True = die KI wirft

    def extract(self, message, package, state):
        return list(self.extraktionen.get((zuletzt_gefragt(state), message), []))

    def antworte(self, kontext):
        if self.fehler and self.fehler.pop(0):
            raise RuntimeError("Aussetzer der Test-KI")
        if kontext.ist_abschluss:
            return "Fertig."
        return kontext.naechste_frage


PAKET = UseCasePackage(
    name="pruefung", schema_version="1", max_rounds=20,
    fields=(
        FieldSpec("a1", "Worum geht es?", typ=FREITEXT),
        FieldSpec("e1", "Wie lange dauert der Durchlauf?", typ=MINUTEN),
        FieldSpec("e2", "Wie lange dauert der Schritt?", typ=MINUTEN),
    ))

HALBE_STUNDE = {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30")],
                ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "30")]}


def test_ablauf_antwortet_je_gefragtem_feld():
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE})
    gefragt = []

    def antworten(feld, versuch):
        gefragt.append((feld, versuch))
        return "eine halbe Stunde"

    lauf = spiele(InMemoryStateStore(), llm, PAKET, antworten, start="Start")

    assert gefragt == [("e1", 0), ("e2", 0)]
    assert [t.status for t in lauf.turns] == ["frage", "frage", "fertig"]


def test_ablauf_zaehlt_die_versuche_je_feld():
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE})
    antworten_je_aufruf = iter(["unbrauchbar", "eine halbe Stunde", "eine halbe Stunde"])
    gefragt = []

    def antworten(feld, versuch):
        gefragt.append((feld, versuch))
        return next(antworten_je_aufruf)

    spiele(InMemoryStateStore(), llm, PAKET, antworten, start="Start")

    assert gefragt == [("e1", 0), ("e1", 1), ("e2", 0)]


def _bewerte(erwartungen, antworten_je_feld, extraktionen=None, paket=PAKET):
    """Spielt PAKET mit den Antworten je Feld (der Reihe nach) und wertet aus."""
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **(HALBE_STUNDE if extraktionen is None else extraktionen)})
    folgen = {feld: iter(texte) for feld, texte in antworten_je_feld.items()}
    lauf = spiele(InMemoryStateStore(), llm, paket,
                  lambda feld, versuch: next(folgen[feld]), start="Start")
    return bewerte(lauf, erwartungen)


def test_bewertung_ok_im_ersten_versuch():
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")]),
         Erwartung("e2", [("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde"], "e2": ["eine halbe Stunde"]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "ok_1"), ("e2", "ok_1")]


def test_gleicher_antworttext_liefert_je_feld_seinen_wert():
    # (Regression) Die Test-KI haengt an (Feld, Text): derselbe Text trifft zwei Felder.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")]),
         Erwartung("e2", [("eine halbe Stunde", "90")])],
        {"e1": ["eine halbe Stunde"], "e2": ["eine halbe Stunde"]},
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30")],
         ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "90")]})

    assert [r.ergebnis for r in ergebnisse] == ["ok_1", "ok_1"]


def test_bewertung_falscher_wert():
    # Ein anderer, gueltiger Wert als erwartet.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")]),
         Erwartung("e2", [("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde"], "e2": ["eine halbe Stunde"]},
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "45")],
         ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "30")]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "falsch"), ("e2", "ok_1")]


def test_bewertung_ok_nach_nachfrage():
    # Erwartet ist eine Nachfrage, danach die gueltige Zweitantwort (Szenario 4).
    ergebnisse = _bewerte(
        [Erwartung("e1", [("unbrauchbar", "Nachfrage"), ("eine halbe Stunde", "30")])],
        {"e1": ["unbrauchbar", "eine halbe Stunde"], "e2": ["eine halbe Stunde"]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "ok_nach_nachfrage")]


def test_bewertung_aufgegeben():
    # Auch die Zweitantwort bringt keinen Wert: das Pflichtfeld endet ohne Wert.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("unbrauchbar", "Nachfrage"), ("auch unbrauchbar", "30")])],
        {"e1": ["unbrauchbar", "auch unbrauchbar"], "e2": ["eine halbe Stunde"]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "aufgegeben")]


def test_bewertung_unerwartete_nachfrage():
    # Erwartet ist ein Wert; die KI kann die Antwort nicht lesen und fragt nach.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("unbrauchbar", "30")])],
        {"e1": ["unbrauchbar", "eine halbe Stunde"], "e2": ["eine halbe Stunde"]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "unerwartete_nachfrage")]


def test_bewertung_sofortige_festlegung_bei_erwarteter_nachfrage_ist_falsch():
    # (Regression) Je Turn, nicht nur der Endwert: der Endwert 30 stimmt, die
    # Festlegung im ersten Versuch war aber nicht erwartet.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "Nachfrage"), ("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde"], "e2": ["eine halbe Stunde"]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "falsch")]


def test_bewertung_x_oder_nachfrage_nimmt_beides_an_aber_keinen_anderen_wert():
    erwartung = [Erwartung("e1", [("eine halbe Stunde", "30 oder Nachfrage"),
                                  ("eine halbe Stunde", "30")])]
    antworten = {"e1": ["eine halbe Stunde", "eine halbe Stunde"],
                 "e2": ["eine halbe Stunde"]}
    anderer_wert = {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "45")],
                    ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "30")]}

    wert = _bewerte(erwartung, antworten)
    nachfrage = _bewerte(erwartung, {"e1": ["unklar", "eine halbe Stunde"],
                                     "e2": ["eine halbe Stunde"]})
    falsch = _bewerte(erwartung, antworten, anderer_wert)

    assert [wert[0].ergebnis, nachfrage[0].ergebnis, falsch[0].ergebnis] == [
        "ok_1", "ok_nach_nachfrage", "falsch"]


def test_bewertung_zweitantwort_mit_anderem_wert_ist_falsch():
    ergebnisse = _bewerte(
        [Erwartung("e1", [("unbrauchbar", "Nachfrage"), ("eine halbe Stunde", "30")])],
        {"e1": ["unbrauchbar", "eine Stunde"], "e2": ["eine halbe Stunde"]},
        {("e1", "eine Stunde"): [ExtractionCandidate("e1", "60")],
         **HALBE_STUNDE})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "falsch")]


def test_bewertung_aenderung_eines_anderen_felds_ist_falsch():
    # Die Antwort auf e1 setzt zugleich e2: e1 hat den erwarteten Wert, ist aber falsch.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde"]},
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30"),
                                       ExtractionCandidate("e2", "30")]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "falsch")]


def test_bewertung_nicht_geprueft():
    # a1 stand in der Startnachricht und wurde nie gefragt; e2 hat im Szenario keine
    # Katalogantwort (Rueckfall-Antwort, keine Erwartung).
    ergebnisse = _bewerte(
        [Erwartung("a1", [("Anfragen", "Anfragen")]),
         Erwartung("e1", [("eine halbe Stunde", "30")]),
         Erwartung("e2", [])],
        {"e1": ["eine halbe Stunde"], "e2": ["eine halbe Stunde"]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [
        ("a1", "nicht_geprueft"), ("e1", "ok_1"), ("e2", "nicht_geprueft")]


def test_bewertung_technischer_abbruch_ist_kein_feldfehler():
    # Die Zweitantwort kam nie an (zweimal Aussetzer): weder ok noch aufgegeben.
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")]},
                      fehler=[False, False, True, True])
    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: ["unbrauchbar", "eine halbe Stunde"][versuch],
                  start="Start")

    ergebnisse = bewerte(lauf, [Erwartung(
        "e1", [("unbrauchbar", "Nachfrage"), ("eine halbe Stunde", "30")])])

    assert lauf.technisch_abgebrochen is True
    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "nicht_geprueft")]


def test_nachfragetext_ja_nein_nennt_ja_und_nein():
    spec = DISCOVERY.field("focus_step_media_break")

    assert pruefe_nachfragetext(spec, "Bitte antworten Sie mit Ja oder Nein.") == []
    assert pruefe_nachfragetext(spec, "Bitte antworten Sie mit Ja.") == [
        "nennt Nein nicht"]


def test_nachfragetext_auswahl_nennt_alle_optionen():
    # Option (Kennung) ODER Name, verglichen ueber den Schluessel aus Spec 3.3
    # (Gross-/Kleinschreibung, Umlaute, Trennzeichen).
    spec = DISCOVERY.field("process_owner_role")

    assert pruefe_nachfragetext(spec, "Meinen Sie R-01, R-02 oder R-03?") == []
    assert pruefe_nachfragetext(
        spec, "Meinen Sie die geschaeftsfuehrung, Vertrieb & Innendienst oder Lager+Versand?") == []
    assert pruefe_nachfragetext(spec, "Meinen Sie R-01 oder Vertrieb & Innendienst?") == [
        "nennt R-03 nicht"]


def test_nachfragetext_skala_nennt_1_und_5():
    # Die Richtung der Kernfrage prueft kein Programm; der Bericht druckt den Text.
    spec = DISCOVERY.field("documentation_status")

    assert pruefe_nachfragetext(spec, "Bitte eine Zahl von 1 (gar nicht) bis 5 (vollstaendig).") == []
    assert pruefe_nachfragetext(spec, "Bitte eine Zahl von 1 bis 4.") == ["nennt 5 nicht"]
    assert pruefe_nachfragetext(spec, "Bitte eine Zahl von 15 bis 50.") == [
        "nennt 1 nicht", "nennt 5 nicht"]


def test_ablauf_wiederholt_bei_fehler_fortsetzbar_einmal():
    # Die KI wirft einmal in `antworte` (Turn 0): dieselbe message_id, danach weiter.
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE}, fehler=[True])

    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: "eine halbe Stunde", start="Start")

    assert lauf.wiederholungen == 1
    assert lauf.technisch_abgebrochen is False
    assert [t.status for t in lauf.turns] == ["frage", "frage", "fertig"]


def test_ablauf_bricht_technisch_ab_nach_zweitem_fehler():
    # Zweiter Aussetzer bei derselben Nachricht: Abbruch, ausdruecklich kein Feldfehler.
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE}, fehler=[False, True, True])

    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: "eine halbe Stunde", start="Start")

    assert lauf.technisch_abgebrochen is True
    assert lauf.wiederholungen == 1
    assert [t.status for t in lauf.turns] == ["frage"]


def test_ablauf_zaehlt_aufrufe():
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE})

    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: "eine halbe Stunde", start="Start")

    assert lauf.aufrufe == {"extract": 3, "antworte": 3}


def test_ablauf_endet_bei_abgebrochen_ohne_identitaet():
    # (Regression) Zweite Runde erreicht das Limit, das identitaetskritische Feld ist offen.
    paket = UseCasePackage(
        name="pruefung_identitaet", schema_version="1", max_rounds=2,
        fields=(FieldSpec("a1", "Worum geht es?", typ=FREITEXT),
                FieldSpec("e1", "Wie lange dauert der Durchlauf?", typ=MINUTEN,
                          identitaetskritisch=True)))
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")]})

    lauf = spiele(InMemoryStateStore(), llm, paket,
                  lambda feld, versuch: "keine Ahnung", start="Start")

    assert [t.status for t in lauf.turns] == ["frage", "abgebrochen_ohne_identitaet"]
    assert lauf.technisch_abgebrochen is False


def test_ablauf_hoechstzahl_turns():
    # Zwei Turns reichen nicht bis „fertig“: Abbruch zaehlt als technisch, nicht als Feldfehler.
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE})

    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: "eine halbe Stunde", start="Start", max_turns=2)

    assert [t.status for t in lauf.turns] == ["frage", "frage"]
    assert lauf.technisch_abgebrochen is True
