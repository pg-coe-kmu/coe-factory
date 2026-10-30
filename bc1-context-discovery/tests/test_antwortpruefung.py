"""Pruefwerkzeug Schicht b (Spec Antwortformen, Abschnitt 6) gegen eine Test-KI.

Die Test-KI kennt das gefragte Feld: Extraktion nach (zuletzt gefragtes Feld,
Nachricht). `FakeLLM` indiziert nur nach dem Text und taugt hier nicht, weil
dieselbe Antwort („eine halbe Stunde“) bei zwei Feldern zwei Felder trifft."""
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from bc1_core.core import zuletzt_gefragt
from bc1_core.feldtypen import AUSWAHL, FREITEXT, MINUTEN
from bc1_core.llm import ExtractionCandidate
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.store import InMemoryStateStore
from werkzeuge.antwortpruefung import (
    Erwartung, Lauf, Turn, bericht, bewerte, pruefe_nachfragetext, spiele)
from werkzeuge.katalog import baue_paket, lade_katalog
from werkzeuge.pruefe_antworten import ermittle_code_stand, main
from werkzeuge.szenarien import FREIE_ANTWORTEN, abdeckung, anzahl_laeufe, baue_szenario

KATALOG = lade_katalog(Path(__file__).parent / "daten" / "antwortkatalog.json")
DISCOVERY = baue_paket(KATALOG["kontext"])


class FeldFakeLLM:
    """Test-KI mit Feldbezug: Extraktion nach (zuletzt gefragtes Feld, Nachricht)."""

    def __init__(self, extraktionen, fehler=(), nachfragetexte=None):
        self.extraktionen = extraktionen
        self.nachfragetexte = nachfragetexte or {}   # Kernfrage -> Text der Nachfrage
        self.fehler = list(fehler)  # je `antworte`-Aufruf: True = die KI wirft

    def extract(self, message, package, state):
        return list(self.extraktionen.get((zuletzt_gefragt(state), message), []))

    def antworte(self, kontext):
        if self.fehler and self.fehler.pop(0):
            raise RuntimeError("Aussetzer der Test-KI")
        if kontext.ist_abschluss:
            return "Fertig."
        if kontext.ist_nachfrage:
            return self.nachfragetexte.get(kontext.naechste_frage, kontext.naechste_frage)
        return kontext.naechste_frage


PAKET = UseCasePackage(
    name="pruefung", schema_version="1", max_rounds=20,
    fields=(
        FieldSpec("a1", "Worum geht es?", typ=FREITEXT),
        FieldSpec("e1", "Wie lange dauert der Durchlauf?", typ=MINUTEN),
        FieldSpec("e2", "Wie lange dauert der Schritt?", typ=MINUTEN),
    ))

HALBE_STUNDE = {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30 Minuten")],
                ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "30 Minuten")]}


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
    return bewerte(lauf, erwartungen, start_felder=("a1",))


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
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30 Minuten")],
         ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "90 Minuten")]})

    assert [r.ergebnis for r in ergebnisse] == ["ok_1", "ok_1"]


def test_bewertung_haelt_antworten_nachfragen_und_endwert_fest():
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE})
    folgen = {"e1": iter(["unbrauchbar", "eine halbe Stunde"]),
              "e2": iter(["eine halbe Stunde"])}
    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: next(folgen[feld]), start="Start")

    ergebnis = bewerte(lauf, [Erwartung(
        "e1", [("unbrauchbar", "Nachfrage"), ("eine halbe Stunde", "30")])])[0]

    assert ergebnis.gesendet == ["unbrauchbar", "eine halbe Stunde"]
    assert ergebnis.nachfragen == 1
    assert ergebnis.endwert == "30"
    assert ergebnis.erwartet == ["Nachfrage", "30"]


def test_bewertung_haelt_nachfragetexte_woertlich_fest():
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE},
                      nachfragetexte={"Wie lange dauert der Durchlauf?":
                                      "Meinen Sie Minuten oder Stunden?"})
    folgen = {"e1": iter(["unbrauchbar", "eine halbe Stunde"]),
              "e2": iter(["eine halbe Stunde"])}
    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: next(folgen[feld]), start="Start")

    ergebnis = bewerte(lauf, [Erwartung(
        "e1", [("unbrauchbar", "Nachfrage"), ("eine halbe Stunde", "30")])])[0]

    assert ergebnis.nachfragetexte == ["Meinen Sie Minuten oder Stunden?"]


def test_bewertung_falscher_wert():
    # Ein anderer, gueltiger Wert als erwartet.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")]),
         Erwartung("e2", [("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde"], "e2": ["eine halbe Stunde"]},
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "45 Minuten")],
         ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "30 Minuten")]})

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
    anderer_wert = {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "45 Minuten")],
                    ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "30 Minuten")]}

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
        {("e1", "eine Stunde"): [ExtractionCandidate("e1", "60 Minuten")],
         **HALBE_STUNDE})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "falsch")]


def test_bewertung_aenderung_eines_anderen_felds_ist_falsch():
    # Die Antwort auf e1 setzt zugleich e2: e1 hat den erwarteten Wert, ist aber falsch.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde"]},
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30 Minuten"),
                                       ExtractionCandidate("e2", "30 Minuten")]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "falsch")]


def test_bewertung_statuswechsel_bei_gleichem_wert_ist_eine_aenderung():
    # Gesamtprüfung I1 (b): die Antwort auf e2 bringt für e1 einen anderen Wert; e1 behält
    # seinen Wert, wird aber unklar (gültig -> unklar bei gleichem Wert).
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")]),
         Erwartung("e2", [("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde", "eine halbe Stunde"], "e2": ["eine halbe Stunde"]},
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30 Minuten")],
         ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "30 Minuten"),
                                       ExtractionCandidate("e1", "45 Minuten")]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [("e1", "ok_1"), ("e2", "falsch")]
    assert ergebnisse[1].detail == "Antwort änderte auch: e1"


def test_bewertung_statuswechsel_nach_antwort_ohne_erwartung_ist_nebenwirkung():
    # Wie oben, aber e2 hat keine Erwartung (Rückfall-Antwort): eigene ✗-Zeile.
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde", "eine halbe Stunde"], "e2": ["eine halbe Stunde"]},
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30 Minuten")],
         ("e2", "eine halbe Stunde"): [ExtractionCandidate("e2", "30 Minuten"),
                                       ExtractionCandidate("e1", "45 Minuten")]})

    assert [(r.feld, r.ergebnis) for r in ergebnisse] == [
        ("e1", "ok_1"), ("Nebenwirkung: Antwort auf e2", "nebenwirkung")]


def _handlauf(*stationen):
    """Lauf aus (Status, gefragtes Feld, Stand der Felder, gesendete Nachricht)."""
    payload = {"feld": None, "pflicht_erfasst": 1, "pflicht_gesamt": 1}
    return Lauf(turns=[Turn(status, gefragt, werte, {"payload": payload}, nachricht)
                       for status, gefragt, werte, nachricht in stationen],
                aufrufe={"extract": 0, "antworte": 0})


def test_bewertung_haelt_endwert_endstatus_und_soll_je_erwartung_fest():
    # e1 war im 1. Versuch gültig; die zweite Frage an e1 macht es unklar. Das Ergebnis des
    # Felds bleibt „im 1. Versuch“, die Endprüfung sieht Endwert, Endstatus und Soll.
    lauf = _handlauf(("frage", None, {"a1": ("x", "gueltig")}, "Start"),
                     ("frage", "e1", {"a1": ("x", "gueltig"), "e1": ("30", "gueltig")}, "a"),
                     ("fertig", "e1", {"a1": ("x", "gueltig"), "e1": ("30", "unklar")}, "b"))

    ergebnis = bewerte(lauf, [Erwartung("e1", [("eine halbe Stunde", "30")])],
                       start_felder=("a1",))[0]

    assert ergebnis.ergebnis == "ok_1"
    assert (ergebnis.endwert, ergebnis.endstatus, ergebnis.endsoll) == ("30", "unklar", "30")


def test_bericht_endpruefung_abweichender_endwert_ist_nicht_erfuellt_und_wird_gedruckt():
    lauf = _handlauf(("frage", None, {"a1": ("x", "gueltig")}, "Start"),
                     ("frage", "e1", {"a1": ("x", "gueltig"), "e1": ("30", "gueltig")}, "a"),
                     ("fertig", "e1", {"a1": ("x", "gueltig"), "e1": ("30", "unklar")}, "b"))
    ergebnisse = bewerte(lauf, [Erwartung("e1", [("eine halbe Stunde", "30")])],
                         start_felder=("a1",))

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s", laeufe=[(1, lauf)])

    assert "Abnahme NICHT erfüllt: Endwert weicht ab: e1 (Lauf 1)." in text
    assert "| 1 | e1 | 30 | unklar | 30 | ✗ |" in text


def test_bewertung_benennt_das_fremde_feld_im_detail():
    ergebnisse = _bewerte(
        [Erwartung("e1", [("eine halbe Stunde", "30")])],
        {"e1": ["eine halbe Stunde"]},
        {("e1", "eine halbe Stunde"): [ExtractionCandidate("e1", "30 Minuten"),
                                       ExtractionCandidate("e2", "30 Minuten")]})

    assert ergebnisse[0].detail == "Antwort änderte auch: e2"


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


def test_bewertung_ohne_einen_einzigen_turn_ist_nicht_geprueft():
    llm = FeldFakeLLM({}, fehler=[True, True])
    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: "eine halbe Stunde", start="Start")

    ergebnisse = bewerte(lauf, [Erwartung("e1", [("eine halbe Stunde", "30")])])

    assert lauf.turns == []
    assert [(r.feld, r.ergebnis, r.endwert) for r in ergebnisse] == [
        ("e1", "nicht_geprueft", None)]


def test_bewertung_technischer_abbruch_ist_kein_feldfehler():
    # Die Zweitantwort kam nie an (zweimal Aussetzer): weder ok noch aufgegeben.
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")]},
                      fehler=[False, False, True, True])
    lauf = spiele(InMemoryStateStore(), llm, PAKET,
                  lambda feld, versuch: ["unbrauchbar", "eine halbe Stunde"][versuch],
                  start="Start")

    ergebnisse = bewerte(lauf, [Erwartung(
        "e1", [("unbrauchbar", "Nachfrage"), ("eine halbe Stunde", "30")])],
        start_felder=("a1",))

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


def test_nachfragetext_auswahl_vergleicht_ganze_woerter_auch_bei_leerzeichen_in_optionen():
    spec = FieldSpec("x", "Welche?", typ=AUSWAHL("zwei Worte", "a-1", namen={"a-1": "Alpha"}))

    # Name statt Kennung genuegt
    assert pruefe_nachfragetext(spec, "Meinen Sie zwei Worte oder Alpha?") == []
    # nur das erste Wort, und "a-10" ist nicht "a-1"
    assert pruefe_nachfragetext(spec, "Meinen Sie zwei oder a-10?") == [
        "nennt zwei Worte nicht", "nennt a-1 nicht"]


def test_nachfragetext_auswahl_ohne_optionen_daten_ist_ein_verstoss():
    ohne_daten = replace(AUSWAHL("a", "b"), optionen=())
    spec = FieldSpec("x", "Welche?", typ=ohne_daten)

    assert pruefe_nachfragetext(spec, "a oder b?") == ["Optionen nicht ermittelbar"]


def test_nachfragetext_skala_nennt_1_und_5():
    # Die Richtung der Kernfrage prueft kein Programm; der Bericht druckt den Text.
    spec = DISCOVERY.field("documentation_status")

    assert pruefe_nachfragetext(spec, "Bitte eine Zahl von 1 (gar nicht) bis 5 (vollstaendig).") == []
    assert pruefe_nachfragetext(spec, "Bitte eine Zahl von 1 bis 4.") == ["nennt 5 nicht"]
    assert pruefe_nachfragetext(spec, "Bitte eine Zahl von 15 bis 50.") == [
        "nennt 1 nicht", "nennt 5 nicht"]


def _test_ki(szenario):
    """Test-KI fuer die Szenarien: liest nur die Startnachricht und die freien Antworten."""
    start = [ExtractionCandidate("request_intent", FREIE_ANTWORTEN["request_intent"]),
             ExtractionCandidate("process_name", FREIE_ANTWORTEN["process_name"])]
    if "ganzer_prozess" in szenario.start:
        start += [ExtractionCandidate("request_goal", "zeit_sparen"),
                  ExtractionCandidate("scope_focus", "ganzer_prozess")]
    extraktionen = {(None, szenario.start): start}
    for feld, text in FREIE_ANTWORTEN.items():
        extraktionen[(feld, text)] = [ExtractionCandidate(feld, text)]
    # Die Test-KI loest die Faelle mit einem Wert in `ki` (Szenario 2); alle anderen
    # (Nachfrage, "X oder Nachfrage") laesst sie offen.
    # Eine Zahl ohne Zeitraum bzw. Einheit verwirft der Extraktor (Spec 2, „Fester Schutz“):
    # die Test-KI liefert Häufigkeit und Dauer deshalb mit Zeitraum bzw. Einheit.
    zusatz = {"zahl": " pro Jahr", "minuten": " Minuten"}
    for eintrag in KATALOG["eintraege"]:
        if eintrag["fest"] == "Nachfrage" and not eintrag["ki"].endswith("Nachfrage"):
            wert = eintrag["ki"] + zusatz.get(DISCOVERY.field(eintrag["feld"]).typ.name, "")
            extraktionen[(eintrag["feld"], eintrag["antwort"])] = [
                ExtractionCandidate(eintrag["feld"], wert)]
    return FeldFakeLLM(extraktionen)


def _spiele_szenario(nummer, lauf=1):
    szenario = baue_szenario(KATALOG, nummer, lauf)
    gespielt = spiele(InMemoryStateStore(), _test_ki(szenario),
                      baue_paket(KATALOG["kontext"], szenario.variante),
                      szenario.antworten, start=szenario.start)
    return gespielt, bewerte(gespielt, szenario.erwartungen,
                             start_felder=szenario.start_felder)


def test_szenario1_und_3_starten_mit_a1_a2_a3_und_b1():
    for nummer in (1, 3):
        start = baue_szenario(KATALOG, nummer).start
        assert FREIE_ANTWORTEN["request_intent"] in start
        assert FREIE_ANTWORTEN["process_name"] in start
        assert "zeit_sparen" in start and "ganzer_prozess" in start


def test_szenario_antwortet_ohne_erwartung_mit_der_kuerzesten_festen_antwort():
    szenario = baue_szenario(KATALOG, 1)

    assert szenario.antworten("process_owner_role", 0) == "Lager+Versand"
    assert szenario.antworten("process_steps", 0) == FREIE_ANTWORTEN["process_steps"]


def test_szenario_antwortet_bei_nackter_zahl_mit_der_nackten_zahl():
    # Seit dem festen Schutz ist die nackte Zahl eine feste Antwort (D1: pro Jahr).
    szenario = baue_szenario(KATALOG, 1)

    assert szenario.antworten("frequency_per_year", 0) == "300"
    assert szenario.antworten("total_duration_minutes", 0) == "40"


def test_szenario1_grundlauf_mit_test_ki_fertig():
    lauf, ergebnisse = _spiele_szenario(1)

    payload = lauf.turns[-1].antwort["payload"]
    assert lauf.turns[-1].status == "fertig"
    assert (payload["pflicht_erfasst"], payload["pflicht_gesamt"]) == (26, 26)
    assert {r.ergebnis for r in ergebnisse} == {"ok_1"}
    assert len(ergebnisse) == 18 - 2    # 18 Katalogfelder, A2 und A3 stehen im Start


def test_abdeckung_jeder_ki_fall_genau_einmal():
    # KI-Faelle = Katalogeintraege ohne Kurzform (fest = Nachfrage); Kurzformen umgehen die KI.
    ki_faelle = sorted(((e["feld"], e["antwort"], e.get("variante"))
                        for e in KATALOG["eintraege"] if e["fest"] == "Nachfrage"), key=str)
    faelle = abdeckung(KATALOG)

    assert sorted(((f.feld, f.antwort, f.variante) for f in faelle), key=str) == ki_faelle
    # Je Lauf hoechstens ein Fall pro Feld
    assert len({(f.szenario, f.lauf, f.feld) for f in faelle}) == len(faelle)
    # ki = Wert -> Szenario 2; ki = Nachfrage oder "X oder Nachfrage" -> Szenario 4
    ki_je_fall = {(e["feld"], e["antwort"], e.get("variante")): e["ki"]
                  for e in KATALOG["eintraege"]}
    for fall in faelle:
        erwartet = 4 if ki_je_fall[(fall.feld, fall.antwort, fall.variante)].endswith(
            "Nachfrage") else 2
        assert fall.szenario == erwartet


def test_anzahl_laeufe_ist_die_groesste_fallzahl_eines_felds():
    for nummer in (2, 4):
        je_feld = Counter(f.feld for f in abdeckung(KATALOG) if f.szenario == nummer)
        assert anzahl_laeufe(KATALOG, nummer) == max(je_feld.values())
    assert anzahl_laeufe(KATALOG, 1) == anzahl_laeufe(KATALOG, 3) == 1
    # Szenario 2 hat mindestens drei Laeufe, auch bei kleinem Katalog
    assert anzahl_laeufe({"eintraege": []}, 2) == 3


def test_szenario_mit_variante_laeuft_im_paket_der_variante():
    faelle = abdeckung(KATALOG)
    mit_variante = [f for f in faelle if f.variante]
    assert mit_variante    # Der Katalog hat den Eintrag "Ja, stimmt" ohne Eigner

    for fall in mit_variante:
        assert baue_szenario(KATALOG, fall.szenario, fall.lauf).variante == fall.variante
    # Alle anderen Laeufe: Paket wie im Katalog-Kontext
    for fall in faelle:
        if not fall.variante and (fall.szenario, fall.lauf) not in {
                (f.szenario, f.lauf) for f in mit_variante}:
            assert baue_szenario(KATALOG, fall.szenario, fall.lauf).variante is None


def test_szenario_nennt_seine_pflichtfaelle():
    assert baue_szenario(KATALOG, 1).pflicht == []
    assert baue_szenario(KATALOG, 2, 3).pflicht == [
        f for f in abdeckung(KATALOG) if (f.szenario, f.lauf) == (2, 3)]
    assert baue_szenario(KATALOG, 4, 2).pflicht == [
        f for f in abdeckung(KATALOG) if (f.szenario, f.lauf) == (4, 2)]
    sz3 = baue_szenario(KATALOG, 3).pflicht
    assert {f.feld for f in sz3} == {"focus_step_media_break", "process_owner_role",
                                     "focus_step", "documentation_status"}
    assert {(f.antwort, f.szenario, f.lauf) for f in sz3} == {("Wie meinen Sie das?", 3, 1)}


def test_szenario2_waehlt_die_k_te_variante():
    erster = baue_szenario(KATALOG, 2, 1)
    zweiter = baue_szenario(KATALOG, 2, 2)

    # A2 und A3 werden einzeln gefragt: die Startnachricht nennt nur A1 und B1
    assert "zeit_sparen" not in erster.start
    assert FREIE_ANTWORTEN["process_name"] in erster.start


def test_szenario2_d1_beginnt_mit_den_ki_faellen_ohne_nackte_zahl():
    # „300“ ist kein KI-Fall mehr (fest gueltig): Lauf 1 und 2 spielen die Wochenformen.
    erster = baue_szenario(KATALOG, 2, 1)
    zweiter = baue_szenario(KATALOG, 2, 2)

    assert erster.antworten("frequency_per_year", 0) == "wöchentlich"
    assert zweiter.antworten("frequency_per_year", 0) == "einmal pro Woche"
    erwartung = next(e for e in zweiter.erwartungen if e.feld == "frequency_per_year")
    assert erwartung.versuche == [("einmal pro Woche", "52")]


def test_szenario4_nachfrage_dann_zweitantwort():
    # Die Test-KI liefert nichts: erwartet ist eine Nachfrage, danach eine gueltige
    # Zweitantwort (kuerzeste feste Katalogantwort). Felder ohne Fall: nicht geprueft.
    for nummer_lauf in range(1, anzahl_laeufe(KATALOG, 4) + 1):
        lauf, ergebnisse = _spiele_szenario(4, nummer_lauf)

        assert lauf.turns[-1].status == "fertig"
        mit_fall = {f.feld for f in abdeckung(KATALOG)
                    if f.szenario == 4 and f.lauf == nummer_lauf}
        assert {r.feld for r in ergebnisse if r.ergebnis == "ok_nach_nachfrage"} == mit_fall
        assert {r.ergebnis for r in ergebnisse} <= {"ok_nach_nachfrage", "nicht_geprueft"}


def test_szenario2_rueckfall_ist_nicht_geprueft():
    # request_goal hat nur einen Szenario-2-Fall: ab Lauf 2 nimmt der Lauf die kurze
    # feste Antwort als Rueckfall und meldet das Feld nicht geprueft (kein Feldfehler).
    for nummer_lauf in range(1, anzahl_laeufe(KATALOG, 2) + 1):
        lauf, ergebnisse = _spiele_szenario(2, nummer_lauf)
        je_feld = {r.feld: r.ergebnis for r in ergebnisse}

        assert lauf.turns[-1].status == "fertig"
        assert je_feld["request_goal"] == ("ok_1" if nummer_lauf == 1 else "nicht_geprueft")
        assert "falsch" not in je_feld.values()
        mit_fall = {f.feld for f in abdeckung(KATALOG)
                    if f.szenario == 2 and f.lauf == nummer_lauf}
        assert {feld for feld, e in je_feld.items() if e == "ok_1"} == mit_fall


def test_szenario3_prueft_die_nachfragetexte_gegen_die_antwortform():
    szenario = baue_szenario(KATALOG, 3)
    llm = _test_ki(szenario)
    # Die Test-KI nennt bei F3 nur "Ja", bei G1 beide Endpunkte
    llm.nachfragetexte = {
        DISCOVERY.field("focus_step_media_break").question: "Bitte antworten Sie mit Ja.",
        DISCOVERY.field("documentation_status").question: "Bitte 1 bis 5 angeben."}
    lauf = spiele(InMemoryStateStore(), llm, DISCOVERY, szenario.antworten,
                  start=szenario.start)

    ergebnisse = {r.feld: r for r in bewerte(lauf, szenario.erwartungen, DISCOVERY)}

    assert ergebnisse["focus_step_media_break"].nachfragetexte == ["Bitte antworten Sie mit Ja."]
    assert ergebnisse["focus_step_media_break"].verstoesse == ["nennt Nein nicht"]
    assert ergebnisse["documentation_status"].verstoesse == []


def _spiele_mit_zusatz(nummer, zusatz, lauf=1, ersetze=None):
    """Spielt ein Szenario; die Test-KI haengt `zusatz` (Schluessel -> Kandidaten) an
    bzw. ersetzt mit `ersetze` die Kandidaten eines Schluessels."""
    szenario = baue_szenario(KATALOG, nummer, lauf)
    llm = _test_ki(szenario)
    for schluessel, kandidaten in zusatz.items():
        llm.extraktionen.setdefault(schluessel, []).extend(kandidaten)
    llm.extraktionen.update(ersetze or {})
    gespielt = spiele(InMemoryStateStore(), llm,
                      baue_paket(KATALOG["kontext"], szenario.variante),
                      szenario.antworten, start=szenario.start)
    return szenario, gespielt


def test_bewertung_freie_antwort_setzt_ein_fremdes_feld_ist_nebenwirkung():
    # Probe A (Gesamtprüfung I1): die Freitext-Antwort auf process_steps setzt D1 = 52. D1 wird
    # nie gefragt („nicht geprüft“) — die Nebenwirkung steht als eigene ✗-Zeile.
    szenario, gespielt = _spiele_mit_zusatz(3, {
        ("process_steps", FREIE_ANTWORTEN["process_steps"]):
            [ExtractionCandidate("frequency_per_year", "1 pro Woche")]})

    ergebnisse = bewerte(gespielt, szenario.erwartungen, DISCOVERY,
                         start_felder=szenario.start_felder)

    zeile = next(r for r in ergebnisse if r.ergebnis == "nebenwirkung")
    assert zeile.feld == "Nebenwirkung: Antwort auf process_steps"
    assert zeile.detail == "Antwort änderte auch: frequency_per_year"


def test_bewertung_freie_antwort_setzt_e5_ueber_den_namen_ist_nebenwirkung():
    # Probe A2: die Freitext-Antwort nennt „Angebot prüfen“ und setzt E5 auf KP-01.TP-2.
    szenario, gespielt = _spiele_mit_zusatz(1, {
        ("process_steps", FREIE_ANTWORTEN["process_steps"]):
            [ExtractionCandidate("focus_step", "Angebot prüfen")]})

    ergebnisse = bewerte(gespielt, szenario.erwartungen, DISCOVERY,
                         start_felder=szenario.start_felder)

    zeile = next(r for r in ergebnisse if r.ergebnis == "nebenwirkung")
    assert zeile.detail == "Antwort änderte auch: focus_step"
    assert gespielt.turns[-1].werte["focus_step"] == ("KP-01.TP-2", "gueltig")


def test_bewertung_startnachricht_darf_nur_die_vorgesehenen_felder_setzen():
    # Sz1 sieht A1/A2/A3/B1 vor; setzt die Startnachricht zusätzlich E5-nahe Angaben wie
    # process_steps, ist das eine ✗-Zeile (alles andere ist Nebenwirkung).
    start = baue_szenario(KATALOG, 1).start
    szenario, gespielt = _spiele_mit_zusatz(1, {
        (None, start): [ExtractionCandidate("process_steps", "Anfrage erfassen")]})

    ergebnisse = bewerte(gespielt, szenario.erwartungen, DISCOVERY,
                         start_felder=szenario.start_felder)

    zeile = next(r for r in ergebnisse if r.ergebnis == "nebenwirkung")
    assert zeile.feld == "Nebenwirkung: Startnachricht"
    assert zeile.detail == "Antwort änderte auch: process_steps"


def test_bericht_zeigt_die_nebenwirkung_als_x_zeile_mit_ursache():
    szenario, gespielt = _spiele_mit_zusatz(3, {
        ("process_steps", FREIE_ANTWORTEN["process_steps"]):
            [ExtractionCandidate("frequency_per_year", "1 pro Woche")]})
    ergebnisse = bewerte(gespielt, szenario.erwartungen, DISCOVERY,
                         start_felder=szenario.start_felder)

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s")

    assert ("| Nebenwirkung: Antwort auf process_steps | "
            f"{FREIE_ANTWORTEN['process_steps']} | 0 | – |  | "
            "✗ Nebenwirkung (Antwort änderte auch: frequency_per_year) |") in text


def test_bericht_abnahme_nicht_erfuellt_bei_einem_x_trotz_voller_abdeckung():
    # Probe C (Gesamtprüfung I1): ein ✗ „falsch“ in Sz2, die Abdeckung ist voll.
    szenario, gespielt = _spiele_mit_zusatz(2, {}, ersetze={
        ("frequency_per_year", "wöchentlich"):
            [ExtractionCandidate("frequency_per_year", "2 pro Woche")]})
    ergebnisse = bewerte(gespielt, szenario.erwartungen, DISCOVERY,
                         start_felder=szenario.start_felder)

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s",
                   pflicht=szenario.pflicht)

    assert "✗ falsch" in text
    assert "Abnahme NICHT erfüllt: 1 Feld mit ✗." in text
    assert "Abnahme erfüllt" not in text


def test_bericht_probe_b_antwort_bringt_fremden_kandidaten_ist_nicht_erfuellt():
    # Probe B (Gesamtprüfung I1): die F3-Antwort bringt zugleich einen B3-Kandidaten, B3 wird
    # unklar. Früher: „✓ im 1. Versuch“ und „Abnahme erfüllt“.
    szenario, gespielt = _spiele_mit_zusatz(2, {
        ("focus_step_media_break", "Ja Systeme wechseln"):
            [ExtractionCandidate("process_owner_role", "R-02")]})
    ergebnisse = bewerte(gespielt, szenario.erwartungen, DISCOVERY,
                         start_felder=szenario.start_felder)

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s",
                   pflicht=szenario.pflicht, laeufe=[(1, gespielt)])

    je_feld = {r.feld: r for r in ergebnisse}
    assert je_feld["focus_step_media_break"].ergebnis == "falsch"
    assert je_feld["focus_step_media_break"].detail == "Antwort änderte auch: process_owner_role"
    assert "Abnahme NICHT erfüllt" in text
    assert "Abnahme erfüllt" not in text


def test_bericht_urteil_gilt_auch_ohne_pflichtfaelle_wenn_laeufe_bekannt_sind():
    # Szenario 1 hat keine Pflichtfälle; die Abnahme gilt dort an ✗ und Endprüfung.
    lauf, ergebnisse = _spiele_szenario(1)

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s", laeufe=[(1, lauf)])

    assert "## Abnahme\nAbnahme erfüllt" in text
    assert "## Abdeckung" not in text


def test_bericht_endpruefung_lauf_ohne_status_fertig_ist_nicht_erfuellt():
    szenario = baue_szenario(KATALOG, 1)
    gespielt = spiele(InMemoryStateStore(), _test_ki(szenario), DISCOVERY, szenario.antworten,
                      start=szenario.start, max_turns=4)
    ergebnisse = bewerte(gespielt, szenario.erwartungen, DISCOVERY,
                         start_felder=szenario.start_felder)

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s",
                   laeufe=[(1, gespielt)])

    assert "Abnahme NICHT erfüllt: Lauf 1 nicht fertig." in text
    assert "- Lauf 1: Status frage, Pflichtfelder 7 von 26 — nicht fertig" in text


def test_bericht_endpruefung_fertig_mit_aufgegebenem_pflichtfeld_ist_nicht_erfuellt():
    # Status fertig, aber e1 wurde nach den Nachfragen aufgegeben (ungelöst): kein ✗ am Feld
    # (Rückfall-Antwort ohne Erwartung), die Endprüfung muss es trotzdem melden.
    llm = FeldFakeLLM({(None, "Start"): [ExtractionCandidate("a1", "Anfragen")],
                       **HALBE_STUNDE})
    gespielt = spiele(InMemoryStateStore(), llm, PAKET,
                      lambda feld, versuch: "unbrauchbar" if feld == "e1"
                      else "eine halbe Stunde", start="Start")
    ergebnisse = bewerte(gespielt, [Erwartung("e1", [])], start_felder=("a1",))

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s",
                   laeufe=[(1, gespielt)])

    assert gespielt.turns[-1].status == "fertig"
    assert "Abnahme NICHT erfüllt: Lauf 1 Pflichtfelder 2 von 3." in text
    assert "- Lauf 1: Status fertig, Pflichtfelder 2 von 3 — Pflichtfelder fehlen" in text


def test_code_stand_kennzeichnet_einen_unsauberen_arbeitsbaum(tmp_path):
    def git(*argumente):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.org",
             "-c", "commit.gpgsign=false", *argumente],
            cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()

    git("init", "-q")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-qm", "x")
    kurz = git("rev-parse", "--short", "HEAD")

    sauber = ermittle_code_stand(tmp_path)
    (tmp_path / "neu.txt").write_text("neu", encoding="utf-8")
    unsauber = ermittle_code_stand(tmp_path)

    assert (sauber, unsauber) == (kurz, kurz + "+dirty")


def test_bericht_enthaelt_modell_code_stand_szenario():
    _, ergebnisse = _spiele_szenario(1)

    text = bericht(ergebnisse, modell="gemini-test", code_stand="abc1234",
                   szenario="Szenario 1, Grundlauf")

    assert "gemini-test" in text
    assert "abc1234" in text
    assert "Szenario 1, Grundlauf" in text


def test_bericht_zeigt_je_feld_antworten_nachfragen_endwert_erwartung_ergebnis():
    _, ergebnisse = _spiele_szenario(3)

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s")

    zeile = next(z for z in text.splitlines() if z.startswith("| focus_step_media_break "))
    assert [spalte.strip() for spalte in zeile.strip("|").split("|")] == [
        "focus_step_media_break", "Wie meinen Sie das? / Ja", "1", "ja",
        "Nachfrage, ja", "✓ nach erwarteter Nachfrage"]
    ersterversuch = next(z for z in text.splitlines() if z.startswith("| frequency_per_year "))
    assert ersterversuch.endswith("| ✓ im 1. Versuch |")


def test_bericht_druckt_nachfragetexte_woertlich():
    szenario = baue_szenario(KATALOG, 3)
    llm = _test_ki(szenario)
    llm.nachfragetexte = {
        DISCOVERY.field("focus_step_media_break").question: "Bitte antworten Sie mit Ja.",
        DISCOVERY.field("documentation_status").question: "Bitte 1 (gar nicht) bis 5 angeben."}
    lauf = spiele(InMemoryStateStore(), llm, DISCOVERY, szenario.antworten,
                  start=szenario.start)

    text = bericht(bewerte(lauf, szenario.erwartungen, DISCOVERY,
                           start_felder=szenario.start_felder),
                   modell="m", code_stand="c", szenario="s")

    assert "### focus_step_media_break" in text
    assert "> Bitte antworten Sie mit Ja." in text
    assert "Automatische Prüfung: nennt Nein nicht" in text
    assert "> Bitte 1 (gar nicht) bis 5 angeben." in text
    assert "Automatische Prüfung: keine Verstöße" in text


def test_bericht_markiert_offene_bewertung():
    # Polaritaet, Richtung und Optionen eines Nachfragetexts prueft kein Programm.
    _, mit_nachfragen = _spiele_szenario(3)
    _, ohne_nachfragen = _spiele_szenario(1)

    mit = bericht(mit_nachfragen, modell="m", code_stand="c", szenario="s")
    ohne = bericht(ohne_nachfragen, modell="m", code_stand="c", szenario="s")

    assert mit.count("Bewertung durch den Ausführenden (Polarität, Richtung, Optionen): "
                     "offen für die Projektleitung") == 4
    assert "offen für die Projektleitung" not in ohne


def test_bericht_abdeckung_ein_nicht_gelaufener_pflichtfall_heisst_nicht_erfuellt():
    szenario = baue_szenario(KATALOG, 2, 1)
    _, ergebnisse = _spiele_szenario(2, 1)

    voll = bericht(ergebnisse, modell="m", code_stand="c", szenario="s",
                   pflicht=szenario.pflicht)
    lueckenhaft = bericht([r for r in ergebnisse if r.feld != "frequency_per_year"],
                          modell="m", code_stand="c", szenario="s", pflicht=szenario.pflicht)
    anderer_lauf = bericht([replace(r, lauf=2) for r in ergebnisse],
                           modell="m", code_stand="c", szenario="s", pflicht=szenario.pflicht)

    assert "Abnahme erfüllt" in voll
    assert "Abnahme NICHT erfüllt" in lueckenhaft
    assert "Abnahme NICHT erfüllt" in anderer_lauf


def test_bericht_abdeckung_nennt_den_gespielten_fall_je_lauf():
    szenario = baue_szenario(KATALOG, 2, 1)
    _, ergebnisse = _spiele_szenario(2, 1)

    voll = bericht(ergebnisse, modell="m", code_stand="c", szenario="s",
                   pflicht=szenario.pflicht)
    lueckenhaft = bericht([r for r in ergebnisse if r.feld != "frequency_per_year"],
                          modell="m", code_stand="c", szenario="s", pflicht=szenario.pflicht)

    assert "| frequency_per_year | wöchentlich | 2 | 1 | gelaufen |" in voll
    assert "| frequency_per_year | wöchentlich | 2 | 1 | NICHT gelaufen |" in lueckenhaft


def test_bericht_nennt_je_lauf_aufrufe_und_technischen_abbruch():
    fertig, ergebnisse = _spiele_szenario(1)
    llm = FeldFakeLLM({}, fehler=[True, True])
    abgebrochen = spiele(InMemoryStateStore(), llm, PAKET,
                         lambda feld, versuch: "", start="Start")

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s",
                   laeufe=[(1, fertig), (2, abgebrochen)])

    assert (f"- Lauf 1: {len(fertig.turns)} Turns, KI-Aufrufe: "
            f"extract {fertig.aufrufe['extract']}, antworte {fertig.aufrufe['antworte']}, "
            "Wiederholungen nach Fehler 0, abgeschlossen") in text
    assert ("- Lauf 2: 0 Turns, KI-Aufrufe: extract 2, antworte 2, "
            "Wiederholungen nach Fehler 1, technisch NICHT abgeschlossen "
            "(kein Feldfehler)") in text


def test_bericht_fasst_das_ergebnis_vor_der_tabelle_zusammen():
    _, ergebnisse = _spiele_szenario(1)
    _, mit_luecken = _spiele_szenario(2, 2)
    anzahl_ok = sum(1 for r in mit_luecken if r.ergebnis == "ok_1")
    anzahl_offen = sum(1 for r in mit_luecken if r.ergebnis == "nicht_geprueft")

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s")
    luecken = bericht(mit_luecken, modell="m", code_stand="c", szenario="s")

    assert "- Ergebnis: 16 von 16 geprüften Feldern bestanden, 0 nicht geprüft" in text
    assert text.index("- Ergebnis:") < text.index("| Feld |")
    assert (f"- Ergebnis: {anzahl_ok} von {anzahl_ok} geprüften Feldern bestanden, "
            f"{anzahl_offen} nicht geprüft") in luecken


def test_kommandozeile_schreibt_den_bericht_mit_test_ki(tmp_path):
    ziel = tmp_path / "bericht.md"

    code = main(["--szenario", "3", "--ausgabe", str(ziel)],
                umgebung={"BC1_LLM": "gemini", "BC1_GEMINI_MODELL": "modell-x"},
                waehle=lambda umgebung: _test_ki(baue_szenario(KATALOG, 3)))

    text = ziel.read_text(encoding="utf-8")
    assert code == 0
    assert "- Modell: modell-x" in text
    assert re.search(r"- Code-Stand: [0-9a-f]{7,}", text)
    assert "Szenario 3" in text
    assert "Abnahme erfüllt" in text


def test_kommandozeile_druckt_den_code_stand_mit_dirty_kennung(tmp_path, monkeypatch):
    monkeypatch.setattr("werkzeuge.pruefe_antworten.ermittle_code_stand",
                        lambda verzeichnis: "abc1234+dirty")
    ziel = tmp_path / "bericht.md"

    main(["--szenario", "3", "--ausgabe", str(ziel)], umgebung={},
         waehle=lambda umgebung: _test_ki(baue_szenario(KATALOG, 3)))

    assert "- Code-Stand: abc1234+dirty" in ziel.read_text(encoding="utf-8")


def test_kommandozeile_spielt_ohne_lauf_alle_laeufe_und_mit_lauf_nur_einen(tmp_path):
    waehle = lambda umgebung: _test_ki(baue_szenario(KATALOG, 2))
    alle, einer = tmp_path / "alle.md", tmp_path / "einer.md"

    main(["--szenario", "2", "--ausgabe", str(alle)], umgebung={}, waehle=waehle)
    main(["--szenario", "2", "--lauf", "2", "--ausgabe", str(einer)],
         umgebung={}, waehle=waehle)

    text_alle, text_einer = alle.read_text("utf-8"), einer.read_text("utf-8")
    for nummer in range(1, anzahl_laeufe(KATALOG, 2) + 1):
        assert f"- Lauf {nummer}: " in text_alle
    assert "Abnahme erfüllt" in text_alle
    assert "- Lauf 2: " in text_einer and "- Lauf 1: " not in text_einer


def test_kommandozeile_meldet_bei_teillauf_keine_abnahme(tmp_path):
    waehle = lambda umgebung: _test_ki(baue_szenario(KATALOG, 2))
    teil, ganz = tmp_path / "teil.md", tmp_path / "ganz.md"

    main(["--szenario", "2", "--lauf", "2", "--ausgabe", str(teil)], umgebung={}, waehle=waehle)
    main(["--szenario", "3", "--lauf", "1", "--ausgabe", str(ganz)], umgebung={},
         waehle=lambda umgebung: _test_ki(baue_szenario(KATALOG, 3)))

    assert "Teilergebnis: Abdeckung nur für Lauf 2 geprüft" in teil.read_text("utf-8")
    assert "Abnahme erfüllt" not in teil.read_text("utf-8")
    # Szenario 3 hat nur einen Lauf: --lauf 1 ist das ganze Szenario
    assert "Abnahme erfüllt" in ganz.read_text("utf-8")


def test_kommandozeile_legt_berichte_nie_im_repo_ab():
    ziel = Path(__file__).parent / "darf-nicht-entstehen.md"
    aufrufe = []

    with pytest.raises(SystemExit) as ausgang:
        main(["--szenario", "3", "--ausgabe", str(ziel)], umgebung={},
             waehle=lambda umgebung: aufrufe.append(umgebung))

    assert ausgang.value.code == 2
    assert not ziel.exists()
    assert aufrufe == []    # nicht einmal die KI wurde gewaehlt


def test_kommandozeile_waehlt_die_ki_aus_der_umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("BC1_LLM", "gibt-es-nicht")

    with pytest.raises(RuntimeError, match="BC1_LLM='gibt-es-nicht'"):
        main(["--szenario", "3", "--ausgabe", str(tmp_path / "bericht.md")])


def test_modulaufruf_hilfe_braucht_keinen_schluessel():
    umgebung = {schluessel: wert for schluessel, wert in os.environ.items()
                if schluessel not in ("BC1_LLM", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")}

    ergebnis = subprocess.run(
        [sys.executable, "-m", "werkzeuge.pruefe_antworten", "--help"],
        cwd=Path(__file__).parents[1], env=umgebung, capture_output=True, text=True)

    assert ergebnis.returncode == 0
    assert "--szenario" in ergebnis.stdout and "--ausgabe" in ergebnis.stdout


def test_bericht_zeigt_fehlende_werte_als_strich_statt_none():
    # Kein einziger Turn: das Feld hat weder gesendete Antworten noch einen Endwert.
    llm = FeldFakeLLM({}, fehler=[True, True])
    lauf = spiele(InMemoryStateStore(), llm, PAKET, lambda feld, versuch: "", start="Start")
    ergebnisse = bewerte(lauf, [Erwartung("e1", [("eine halbe Stunde", "30")])])

    text = bericht(ergebnisse, modell="m", code_stand="c", szenario="s")

    assert "| e1 |  | 0 | – |" in text
    assert "None" not in text


def test_bericht_teillauf_trifft_keine_abnahme_aussage():
    szenario = baue_szenario(KATALOG, 2, 2)
    _, ergebnisse = _spiele_szenario(2, 2)

    text = bericht([replace(r, lauf=2) for r in ergebnisse], modell="m", code_stand="c",
                   szenario="s", pflicht=szenario.pflicht, teillauf=2)

    assert ("Teilergebnis: Abdeckung nur für Lauf 2 geprüft — "
            "Abnahme hier nicht beurteilbar") in text
    assert "Abnahme erfüllt" not in text and "Abnahme NICHT erfüllt" not in text


def test_bericht_teillauf_nennt_den_gespielten_fall_des_laufs():
    szenario = baue_szenario(KATALOG, 2, 2)
    _, ergebnisse = _spiele_szenario(2, 2)

    text = bericht([replace(r, lauf=2) for r in ergebnisse], modell="m", code_stand="c",
                   szenario="s", pflicht=szenario.pflicht, teillauf=2)

    assert "| frequency_per_year | einmal pro Woche | 2 | 2 | gelaufen |" in text


def test_szenario3_nachfrage_dann_richtige_antwort():
    # Je ein Ja/Nein-, zwei Auswahl- und ein Skalenfeld: erst "Wie meinen Sie das?",
    # dann die richtige Antwort; alle uebrigen Felder gehen im ersten Versuch durch.
    lauf, ergebnisse = _spiele_szenario(3)

    assert lauf.turns[-1].status == "fertig"
    nachgefragt = {r.feld for r in ergebnisse if r.ergebnis == "ok_nach_nachfrage"}
    assert nachgefragt == {"process_owner_role", "focus_step", "focus_step_media_break",
                           "documentation_status"}
    assert {r.ergebnis for r in ergebnisse} == {"ok_1", "ok_nach_nachfrage"}


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
