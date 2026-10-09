"""
Tests des Ausarbeitungsschritts (#301, ADR-010 · BC2).

**Was diese Tests nicht zeigen.** Kein Test hier ruft ein Modell — dieselbe
Grenze wie in ``test_erkennung.py`` und ``test_bewertung.py``. Ob ein Modell
gute Texte schreibt und das Rechenverbot hält, zeigt nur der von Hand gefahrene
Aufruf (``tools/ausarbeitung_messen.py``), protokolliert im Ticket. Geprüft wird
die Kette **um** das Modell: was es sieht, was der Wächter verwirft, was Python
einsetzt und beiträgt — und dass der abgelegte Lauf schemagültig ist.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from ablage import AblegendeLaufquelle, SpeicherErgebnisbuch
from ausarbeitung import Erwartung, arbeite_aus, baue_nutzlast, pruefe_ausarbeitung, setze_ein
from bewertung import bewerte
from erkennung import Doppelgaenger, Kernprozess, Teilprozess, erkenne
from erkennung.bestand import tech_stack_aus_profil
from erkennung.modellruf import Antwort, schaele_json
from gate1 import Gate1Entscheidung, SpeicherGate1Buch, jetzt
from laeufe import LaufAngehalten, PaketLaufquelle, Paketeintrag, SpeicherPaketverzeichnis, aus_lauf
from modell import rechne_lauf
from test_bewertung import NOROAI, STAND, _ausgearbeitet, _bestand, _erkannt, _gut, _kennungen

VERTRAEGE = Path(__file__).resolve().parents[3] / "contracts" / "bc2-to-bc3"


# --------------------------------------------------------------------- Hilfen


def _validator(name: str):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((VERTRAEGE / name).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def _zwei_kernprozesse():
    """``_bestand()`` plus KP-07 mit einem Teilprozess, der Werkzeuge nennt."""
    b = _bestand()
    kp07 = Kernprozess(
        kernprozess_id="KP-07",
        name="Rechnungsstellung",
        teilprozesse=(
            Teilprozess(
                "KP-07.TP-1", "KP-07", "Rechnung schreiben", schritt_nr=1,
                ablauf="Rechnung in der Buchhaltung anlegen.",
                werkzeuge="Lexware, Outlook", bitkom=b.kernprozesse[0].teilprozesse[0].bitkom,
            ),
        ),
    )
    return replace(b, kernprozesse=(*b.kernprozesse, kp07))


def _erkannt_zwei() -> dict:
    e = _erkannt()
    p3 = dict(e["potenziale"][0], id="P3", kernprozess_id="KP-07",
              titel="Rechnung aus Zeiten erzeugen", beruehrte_teilprozesse=["KP-07.TP-1"],
              loesungsklasse="Textgenerierung")
    e["potenziale"].append(p3)
    return e


def _gut_zwei() -> dict:
    g = _gut()
    g["bewertungen"].append(dict(
        g["bewertungen"][0], id="P3", angesetzt_min_pct=35, angesetzt_max_pct=45,
        komplexitaet_ueberschrieben=5,
        komplexitaet_begruendung="Fuer die Rechnungsstellung liegen keine Skalen vor."))
    return g


def _nutzlast_aus(frage: str) -> dict:
    teil = frage.split("## Die Nutzlast")[1]
    return json.loads(re.search(r"```json\n(.*)\n```", teil, re.S).group(1))


def _lexware(kp: str, antwort: dict) -> dict:
    """KP-07 nennt Lexware und Outlook — „Projekttool“ steht dort nicht."""
    if kp == "KP-07":
        for p in antwort["potenziale"]:
            p["betroffene_systeme"][0]["name"] = "Lexware"
    return antwort


class _JeKonzept:
    """Ein Modellruf, der Erkennung und Bewertung aus einer Liste beantwortet
    und jede Ausarbeitung aus der Frage baut — die Konzepte laufen parallel,
    eine feste Reihenfolge gibt es dort nicht."""

    def __init__(self, *antworten, aendere=None) -> None:
        self.antworten = list(antworten)
        self.aendere = aendere or _lexware
        self.fragen: list[str] = []

    def frage(self, text: str) -> Antwort:
        self.fragen.append(text)
        if "## Die Nutzlast" in text:
            n = _nutzlast_aus(text)
            nummern = [p["id"] for p in n["potenziale"]]
            antwort = self.aendere(n["kernprozess"]["id"], _ausgearbeitet(*nummern))
        else:
            antwort = self.antworten.pop(0)
        roh = json.dumps(antwort, ensure_ascii=False)
        return Antwort(roh=roh, ergebnis=schaele_json(roh), modell="je-konzept")


def _gerechnet(bestand=None, erkannt=None, gut=None):
    """Erkennung, Bewertung und Rechnung — alles bis vor die Ausarbeitung."""
    bestand = bestand or _bestand()
    erkennung = erkenne(bestand, Doppelgaenger([erkannt or _erkannt()]))
    bewertung = bewerte(erkennung, bestand, Doppelgaenger([gut or _gut()]), urteile=1,
                        kennung=_kennungen())
    lauf = rechne_lauf(NOROAI, bestand.paket_id, bewertung.eingaenge)
    ansicht = aus_lauf(lauf, list(bewertung.eingaenge), uebergeben_am=STAND)
    return bestand, erkennung, bewertung, lauf, ansicht


def _erwartung(**ueber) -> Erwartung:
    vorgabe = dict(nummern=("P1", "P2"), alle_nummern=frozenset({"P1", "P2"}), systeme={})
    vorgabe.update(ueber)
    return Erwartung(**vorgabe)


# ======================================================================
# Was das Modell sieht
# ======================================================================


def test_die_nutzlast_traegt_keine_zahl_aus_der_rechnung():
    """#194: das Rechenverbot brach dort, wo Zahlen in der Nutzlast standen."""
    bestand, erkennung, bewertung, lauf, ansicht = _gerechnet()
    erkannt = {p.potenzial_id: p for p in erkennung.potenziale}
    nummer = {pid: nr for nr, pid in bewertung.kennungen.items()}
    stuecke = [(erkannt[nummer[p.potenzial_id]], ansicht.potenziale[p.potenzial_id])
               for p in lauf.potenziale]

    nutzlast = baue_nutzlast(bestand.mandant, bestand.kernprozesse[0], stuecke, [])

    schluessel: set[str] = set()
    zahlen: list = []

    def sammle(w, k=None):
        if isinstance(w, dict):
            for kk, v in w.items():
                schluessel.add(kk)
                sammle(v, kk)
        elif isinstance(w, list):
            for v in w:
                sammle(v, k)
        elif isinstance(w, (int, float)) and not isinstance(w, bool):
            zahlen.append(k)

    sammle(nutzlast)
    assert zahlen == ["potenzialrang", "potenzialrang"], "nur der Rang ist eine Zahl"
    assert not schluessel & {"value", "manueller_aufwand_heute", "automatisierungsgrad",
                             "impact", "prioritaet_score", "aufwand_schaetzung_pt", "wert"}
    (p1, *_) = nutzlast["potenziale"]
    assert p1["lage_im_korridor"] and set(p1["nutzwert_begruendungen"]) == {
        "qualitaet", "durchlaufzeit", "fehlerreduktion", "mitarbeiterzufriedenheit", "compliance"}
    assert nutzlast["tech_stack"] == "nicht erhoben"


# ======================================================================
# Der Wächter
# ======================================================================


def test_der_waechter_laesst_eine_saubere_antwort_durch():
    assert pruefe_ausarbeitung(_ausgearbeitet("P1", "P2"), _erwartung()) == ()


def _mit(pfad: str, wert):
    def aendern(a):
        ziel = a
        teile = pfad.split(".")
        for t in teile[:-1]:
            ziel = ziel[int(t)] if t.isdigit() else ziel[t]
        ziel[teile[-1]] = wert
        return a
    return aendern


@pytest.mark.parametrize(
    "aenderung, erwartet",
    [
        (_mit("potenziale.0.beschreibung", "Spart rund 40 Stunden. " * 20), "Zahl mit Einheit"),
        (_mit("potenziale.0.to_be_vision", "Spart {einsparung} Euro. " * 20), "unbekannter Platzhalter"),
        (_mit("kontext.prozess_kurzbeschreibung", "Erreicht {grad_min} Prozent."), "nicht erlaubt"),
        (_mit("gesamtempfehlung_begruendung", "Erst {grad_max}."), "nicht erlaubt"),
        (_mit("kontext.hauptschmerzpunkte.0.haeufigkeit", "in 30 % der Faelle"), "Zahl mit Einheit"),
        (_mit("kontext.prozess_kurzbeschreibung", "x" * 281), "280"),
        (_mit("potenziale.0.beschreibung", "Zu kurz."), "kürzer als 300"),
        (_mit("potenziale.0.user_story", "Die Zeiten sollen automatisch abgerechnet werden."),
         "SOPHIST"),
        (_mit("potenziale.0.akzeptanzkriterien.0.kriterium",
              "Die Zeiten werden zuverlaessig abgerechnet."), "Given/When/Then"),
        (_mit("potenziale.0.akzeptanzkriterien", []), "mindestens ein Kriterium"),
        (_mit("potenziale.0.betroffene_systeme.0.rolle", "Senke"), "rolle"),
        (_mit("potenziale.0.betroffene_systeme.0.integration", "Webhook"), "integration"),
        (_mit("potenziale.0.risiken.0.auswirkung", "mittel"), "low, med, high"),
        (_mit("potenziale.0.tech_stack_empfehlung", []), "mindestens 1"),
        (_mit("potenziale.0.abhaengigkeiten", [{"potenzial": "P1", "grund": "x"}]),
         "nicht von sich selbst"),
        (_mit("potenziale.0.abhaengigkeiten", [{"potenzial": "P9", "grund": "x"}]),
         "kein Potenzial dieses Laufs"),
        (_mit("potenziale.1.id", "P1"), "P2 fehlt"),
        (lambda a: (a["potenziale"].append(dict(a["potenziale"][0], id="P7")), a)[1],
         "gehört nicht zu diesem Konzept"),
    ],
)
def test_der_waechter_verwirft(aenderung, erwartet):
    antwort = aenderung(_ausgearbeitet("P1", "P2"))
    gruende = pruefe_ausarbeitung(antwort, _erwartung())
    assert any(erwartet in g for g in gruende), gruende


def test_ein_system_muss_im_bestand_oder_im_tech_stack_stehen():
    antwort = _ausgearbeitet("P1", "P2")
    erwartung = _erwartung(systeme={"P1": "lexware, outlook", "P2": "projekttool"})
    (grund,) = pruefe_ausarbeitung(antwort, erwartung)
    assert "potenziale[P1].betroffene_systeme[0].name" in grund and "Projekttool" in grund


def test_ein_system_aus_dem_ablauf_zaehlt_auch_mit_bindestrichen():
    """Gemessen am 09.10.2026: KP-05 führt keine Werkzeuge, der Ablauf sagt
    „durchsuchen Google-Drive-Ordner“ — das ist das tatsächliche Quellsystem."""
    bestand = _bestand()
    kp = bestand.kernprozesse[0]
    tp1 = replace(kp.teilprozesse[0],
                  ablauf="Mitarbeitende durchsuchen Google-Drive-Ordner manuell.")
    kp = replace(kp, teilprozesse=(tp1, *kp.teilprozesse[1:]))
    bestand = replace(bestand, kernprozesse=(kp,))
    _, erkennung, bewertung, lauf, ansicht = _gerechnet(bestand)

    def drive(a):
        # Nur P2 berührt TP-1; P1 liegt allein auf TP-2, und dort steht kein Drive.
        p2 = next(p for p in a["potenziale"] if p["id"] == "P2")
        p2["betroffene_systeme"] = [{"name": "Google Drive", "rolle": "Quelle", "integration": "API"}]
        return a

    a = arbeite_aus(lauf, ansicht.potenziale, erkennung, bewertung.kennungen, bestand,
                    Doppelgaenger([drive(_ausgearbeitet("P1", "P2"))]))
    (aufruf,) = a.aufrufe
    assert aufruf.versuche == 1, aufruf.verworfen


def test_ohne_genannte_systeme_wird_nicht_geprueft():
    """Sonst hinge der Lauf an einer Datenlücke fest, die das Modell nicht schließen kann."""
    assert pruefe_ausarbeitung(_ausgearbeitet("P1", "P2"), _erwartung(systeme={"P1": None})) == ()


def test_kein_json_ist_ein_verstoss():
    assert pruefe_ausarbeitung(None, _erwartung()) == ("Die Antwort enthält kein JSON-Objekt.",)


# ======================================================================
# Was Python einsetzt und beiträgt
# ======================================================================


def test_platzhalter_bekommen_die_gerechnete_zahl_in_deutscher_schreibweise():
    text = {"k": ["mindestens {grad_min} %, hoechstens {grad_max} %"]}
    assert setze_ein(text, {"grad_min": 65.0, "grad_max": 67.5}) == {
        "k": ["mindestens 65 %, hoechstens 67,5 %"]}


def test_die_konzepte_tragen_texte_und_maschinelle_felder():
    bestand, erkennung, bewertung, lauf, ansicht = _gerechnet()
    a = arbeite_aus(lauf, ansicht.potenziale, erkennung, bewertung.kennungen, bestand,
                    Doppelgaenger([_ausgearbeitet("P1", "P2", abhaengig={"P2": "P1"})]))

    (konzept,) = a.konzepte
    rang = sorted(lauf.potenziale, key=lambda p: p.potenzialrang)
    assert konzept["gesamtempfehlung"]["reihenfolge_potenzial_ids"] == [p.potenzial_id for p in rang]
    assert konzept["gelesen_am"] == STAND.isoformat()
    assert konzept["kontext"]["unternehmen"] == "NoroAI Consulting GmbH"

    je_titel = {p["titel"]: p for p in konzept["potenziale"]}
    p1, p2 = je_titel["Potenzial P1"], je_titel["Potenzial P2"]
    # Die gerechnete Hälfte bleibt, die Texte kommen dazu.
    assert p1["prioritaet_score"] == ansicht.potenziale[p1["potenzial_id"]]["prioritaet_score"]
    # Der Platzhalter trägt die gerechnete Untergrenze, nicht eine Zahl des Modells.
    unten = p1["automatisierungsgrad"]["angesetzt_min_pct"]
    assert f"mindestens {unten:g} % ohne Nacharbeit" in p1["akzeptanzkriterien_geschaeftlich"][0]["kriterium"]
    # Teilprozesse heißen im Vertrag „Prozessschritte“.
    assert p2["betroffene_prozessschritte"] == ["Einsatzplanung", "Zeiterfassung abrechnen"]
    assert p1["querschnitte"]["reifegrad"].startswith("Bitkom-Stufe im Mittel 3 von 5")
    (abh,) = p2["querschnitte"]["abhaengigkeiten"]
    assert abh.startswith(f"{p1['potenzial_id']} (Potenzial P1): ")
    # Nur das Gerechnete wandert mit — hier das BC1-Profil von TP-2.
    assert {w.get("betrifft_teilprozess_id") for w in konzept["eingangswerte"]} - {None} == {
        "KP-06.TP-2"}

    assert a.ausgangslage["herausforderungen"] == [{
        "beschreibung": "Doppelerfassung", "auswirkung": "Fehler in der Rechnung",
        "haeufigkeit": "woechentlich", "kp_ids": ["KP-06"]}]
    assert a.ausgangslage["unternehmen"]["name"] == "NoroAI Consulting GmbH"
    assert "kernaussage" not in a.ausgangslage  # entfällt vorerst (#301, Q5)


def test_je_konzept_ein_aufruf_in_der_reihenfolge_der_prozessraenge():
    bestand, erkennung, bewertung, lauf, ansicht = _gerechnet(
        _zwei_kernprozesse(), _erkannt_zwei(), _gut_zwei())
    modell = _JeKonzept()

    a = arbeite_aus(lauf, ansicht.potenziale, erkennung, bewertung.kennungen, bestand, modell)

    assert [k["kontext"]["kp_id"] for k in a.konzepte] == [r.kp_id for r in lauf.prozess_raenge]
    assert len(modell.fragen) == 2 and len(a.aufrufe) == 2
    # Jeder Aufruf sieht die Potenziale des anderen Konzepts — für Abhängigkeiten.
    for frage in modell.fragen:
        n = _nutzlast_aus(frage)
        eigene = {p["id"] for p in n["potenziale"]}
        uebrige = {p["id"] for p in n["uebrige_potenziale_des_laufs"]}
        assert eigene | uebrige == {"P1", "P2", "P3"} and not eigene & uebrige
    assert {k["kontext"]["kp_id"]: len(k["potenziale"]) for k in a.konzepte} == {"KP-06": 2, "KP-07": 1}
    # Zwei Konzepte mit demselben Schmerzpunkt: eine Herausforderung, zwei Kernprozesse.
    (h,) = a.ausgangslage["herausforderungen"]
    assert sorted(h["kp_ids"]) == ["KP-06", "KP-07"]


def test_die_systempruefung_greift_wo_der_bestand_systeme_nennt():
    """KP-07 nennt Lexware und Outlook — „Projekttool“ steht dort nicht."""
    bestand, erkennung, bewertung, lauf, ansicht = _gerechnet(
        _zwei_kernprozesse(), _erkannt_zwei(), _gut_zwei())
    unveraendert = _JeKonzept(aendere=lambda kp, a: a)

    from ausarbeitung import AusarbeitungAbgebrochen
    with pytest.raises(AusarbeitungAbgebrochen, match="Projekttool"):
        arbeite_aus(lauf, ansicht.potenziale, erkennung, bewertung.kennungen, bestand,
                    unveraendert)

    a = arbeite_aus(lauf, ansicht.potenziale, erkennung, bewertung.kennungen, bestand,
                    _JeKonzept(aendere=_lexware))
    assert a.konzepte


def test_eine_wiederholung_mit_benanntem_verstoss_dann_durch():
    bestand, erkennung, bewertung, lauf, ansicht = _gerechnet()
    schlecht = _mit("potenziale.0.beschreibung", "Spart 40 Stunden. " * 20)(_ausgearbeitet("P1", "P2"))
    modell = Doppelgaenger([schlecht, _ausgearbeitet("P1", "P2")])

    a = arbeite_aus(lauf, ansicht.potenziale, erkennung, bewertung.kennungen, bestand, modell)

    assert "dieser Aufruf ist eine Wiederholung" in modell.fragen[1]
    assert "Zahl mit Einheit" in modell.fragen[1]
    (aufruf,) = a.aufrufe
    assert aufruf.versuche == 2 and aufruf.verworfen


# ======================================================================
# Der Anschluss: PaketLaufquelle und Ablage
# ======================================================================


class _Quelle:
    def __init__(self, bestand=None) -> None:
        self._bestand = bestand or _bestand()

    def lies_paket(self, company_id, paket_id, uebergeben_am, teilprozess_ids):
        return replace(self._bestand, paket_id=paket_id)


def _laufquelle(modell, bestand=None, tps=("KP-06.TP-1", "KP-06.TP-2")):
    eintrag = Paketeintrag("PKT-301", NOROAI, STAND, tps)
    return PaketLaufquelle(SpeicherPaketverzeichnis([eintrag]), _Quelle(bestand), modell, urteile=1)


def test_bricht_die_wiederholung_auch_haelt_der_lauf_an():
    schlecht = _mit("potenziale.0.user_story", "Zeiten automatisch abrechnen, bitte.")(
        _ausgearbeitet("P1", "P2"))
    laeufe = _laufquelle(Doppelgaenger([_erkannt(), _gut(), schlecht, copy.deepcopy(schlecht)]))

    with pytest.raises(LaufAngehalten, match="Ausarbeitung von KP-06 angehalten.*SOPHIST"):
        laeufe.ansicht("PKT-301")


def test_ohne_ausarbeitung_bleibt_der_lauf_ohne_texte():
    laeufe = PaketLaufquelle(
        SpeicherPaketverzeichnis([Paketeintrag("PKT-301", NOROAI, STAND, ("KP-06.TP-2",))]),
        _Quelle(), Doppelgaenger([_erkannt(), _gut()]), urteile=1, ausarbeiten=False)
    ansicht = laeufe.ansicht("PKT-301")
    assert ansicht.konzepte is None and ansicht.ausgangslage is None


def test_der_abgelegte_lauf_ist_ein_schemagueltiger_vertrag_3_1():
    """Der Kern des Tickets: der echte Weg legt einen Vertrag ab, der an BC3 gehen kann."""
    modell = _JeKonzept(_erkannt_zwei(), _gut_zwei())
    innen = _laufquelle(modell, _zwei_kernprozesse(),
                        ("KP-06.TP-1", "KP-06.TP-2", "KP-07.TP-1"))
    ergebnisse = SpeicherErgebnisbuch()
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    laeufe = AblegendeLaufquelle(innen, ergebnisse)

    ansicht = laeufe.ansicht("PKT-301")
    entscheidung = Gate1Entscheidung(
        paket_id="PKT-301", company_id=NOROAI, status="approved", fassung=ansicht.kopf.fassung,
        approved_potenzial_ids=tuple(ansicht.potenzial_ids()), kommentar="",
        entschieden_am=jetzt(),
    )
    gate1.merken(entscheidung)

    abgelegt = ergebnisse.letzter("PKT-301")
    priorisierung = {**abgelegt.dokument, "gate1": entscheidung.als_vertrag()}
    assert priorisierung["schema_version"] == "3.1"
    _validator("priorisierung.schema.json").validate(priorisierung)
    pruefer = _validator("konzept.schema.json")
    assert len(abgelegt.konzepte) == 2
    for konzept in abgelegt.konzepte:
        assert konzept["schema_version"] == "3.1"
        pruefer.validate(konzept)
    # Die Detail-Schublade zeigt die Texte (Q8: sehen ja, ändern nein).
    for pot in laeufe.ansicht("PKT-301").potenziale.values():
        assert pot["beschreibung"] and pot["user_story"].startswith("Als ")


# ======================================================================
# Der Tech-Stack aus dem Unternehmensprofil
# ======================================================================


def test_der_tech_stack_kommt_aus_dem_unterabschnitt_des_profils():
    profil = {
        "1. Steckbrief": "…",
        "6. Tech-Stack & IT-Architektur intern": {
            "Inhalt": "EU-First, Open-Source-First.",
            "6.2 Tech-Stack (Standard-Toolbox)": "| Workflow | n8n |",
            "6.5 Cybersicherheit": "Wazuh",
        },
    }
    assert tech_stack_aus_profil(profil) == "### 6.2 Tech-Stack (Standard-Toolbox)\n| Workflow | n8n |"


def test_ohne_unterabschnitt_gilt_der_ganze_abschnitt_und_ohne_abschnitt_nichts():
    ganz = {"7. Tech-Stack": {"Inhalt": "n8n und Postgres", "Leer": " "}}
    assert tech_stack_aus_profil(ganz) == "### Inhalt\nn8n und Postgres"
    assert tech_stack_aus_profil({"1. Steckbrief": "x"}) is None
    assert tech_stack_aus_profil(None) is None
