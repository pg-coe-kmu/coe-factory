"""
Tests des Bewertungsschritts und seines Anschlusses an die Laufquelle (#288).

**Was diese Tests nicht zeigen.** Kein Test hier ruft ein Modell — dieselbe
Grenze wie in ``test_erkennung.py``. Ob ein Modell die Anker trifft, im Korridor
bleibt und stabil urteilt, zeigt nur der von Hand gefahrene Aufruf
(``tools/bewertung_messen.py``), protokolliert im Ticket. Geprüft wird die Kette
**um** das Modell: was es sieht, was der Wächter verwirft, was daraus in den
Rechenkern geht.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from bewertung import (
    BewertungAbgebrochen,
    Erwartung,
    baue_nutzlast,
    bewerte,
    fuehre_zusammen,
    messungen_je_teilprozess,
    pruefe_bewertung,
)
from erkennung import (
    Bc1Profil,
    Bewertung as BitkomBewertung,
    Doppelgaenger,
    Kernprozess,
    Mandant,
    Paketbestand,
    Teilprozess,
    erkenne,
)
from laeufe import PaketLaufquelle, Paketeintrag, SpeicherPaketverzeichnis
from modell import STANDARD, rechne_lauf

NOROAI = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"
STAND = datetime(2026, 10, 9, tzinfo=timezone.utc)


# --------------------------------------------------------------------- Hilfen


def _profil(tp: str, **ueber) -> Bc1Profil:
    """Ein vollständiges BC1-Profil — Zahlen wie die echte Zeile zu KP-06.TP-2."""
    vorgabe = dict(
        focus_step_id=tp,
        erhebung_id="ERH-0001",
        frequency_per_year=180,
        focus_step_duration_minutes=180,
        total_duration_minutes=999,  # darf nirgends hinwandern (I1, Nachtrag 4)
        focus_step_duration_source="geschaetzt",
        focus_step_duration_confidence_pct=60,
        documentation_status=4,
        standardization_level=4,
        data_availability_score=3,
        stability_score=4,
    )
    vorgabe.update(ueber)
    return Bc1Profil(**vorgabe)


def _bestand() -> Paketbestand:
    """KP-06 mit zwei Teilprozessen: TP-2 voll erhoben, TP-1 ohne BC1-Profil."""
    bitkom = tuple(
        BitkomBewertung(item_nr=i, kriterium=k, frage="F", stufe=s, beleg="B")
        for i, (k, s) in enumerate(
            [("Technologiebasis", 3), ("Technologiebasis", 4), ("Compliance", 2)], start=1
        )
    )
    return Paketbestand(
        mandant=Mandant(company_id=NOROAI, name="NoroAI Consulting GmbH"),
        paket_id="PKT-288",
        uebergeben_am=STAND,
        gelesen_am=STAND,
        kernprozesse=(
            Kernprozess(
                kernprozess_id="KP-06",
                name="Projektdurchfuehrung",
                teilprozesse=(
                    Teilprozess(
                        "KP-06.TP-1", "KP-06", "Einsatzplanung", schritt_nr=1,
                        ablauf="Verfuegbarkeiten per Mail einsammeln.", bitkom=bitkom,
                    ),
                    Teilprozess(
                        "KP-06.TP-2", "KP-06", "Zeiterfassung abrechnen", schritt_nr=2,
                        ablauf="Stunden aus dem Projekttool in die Rechnung tippen.", bitkom=bitkom,
                        bc1_profil=_profil("KP-06.TP-2"),
                    ),
                ),
            ),
        ),
    )


def _erkannt() -> dict:
    """Die Antwort des Erkennungsschritts: P1 auf TP-2, P2 über TP-1 und TP-2."""

    def p(pid, tps, klasse):
        return {
            "id": pid,
            "kernprozess_id": "KP-06",
            "titel": f"Potenzial {pid}",
            "beruehrte_teilprozesse": tps,
            "ausgangslage": "Heute von Hand.",
            "schmerzpunkte": ["Doppelerfassung"],
            "loesungsansatz": "Anbinden.",
            "loesungsklasse": klasse,
            "trenntest_begruendung": "Eigenstaendig baubar, kein Doppelzaehlen.",
            "unsicherheit": None,
        }

    return {
        "potenziale": [
            p("P1", ["KP-06.TP-2"], "Integration"),
            p("P2", ["KP-06.TP-1", "KP-06.TP-2"], "Assistenz"),
        ],
        "nicht_geschnitten": [],
    }


def _nutzwert(wert: int = 6, text: str = "Spuerbar weniger Nacharbeit.") -> dict:
    return {
        k: {"wert": wert, "begruendung": text}
        for k in (
            "qualitaet", "durchlaufzeit", "fehlerreduktion",
            "mitarbeiterzufriedenheit", "compliance",
        )
    }


def _bewertung(pid: str, **ueber) -> dict:
    vorgabe = {
        "id": pid,
        "angesetzt_min_pct": 65,
        "angesetzt_max_pct": 80,
        "korridor_begruendung": "Einheitliche Eingaenge, wenige Ausnahmen.",
        "nutzwert": _nutzwert(),
        "komplexitaet_ueberschrieben": None,
        "komplexitaet_begruendung": None,
        "aufwand_schaetzung_pt": 12,
        "aufwand_begruendung": "Anbindung zweier Systeme, Test und Einfuehrung.",
        "klassenzweifel": None,
    }
    vorgabe.update(ueber)
    return vorgabe


def _gut() -> dict:
    """Eine Antwort, die den Wächter passiert."""
    return {
        "bewertungen": [
            _bewertung("P1"),
            _bewertung(
                "P2",
                angesetzt_min_pct=15,
                angesetzt_max_pct=25,
                komplexitaet_ueberschrieben=6,
                komplexitaet_begruendung="Fuer die Einsatzplanung liegen keine Skalen vor.",
            ),
        ]
    }


def _ausgearbeitet(*nummern: str, abhaengig: dict[str, str] | None = None) -> dict:
    """Eine Antwort des Ausarbeitungsschritts (#301), die den Wächter passiert.

    Ein Konzept, je Nummer ein Potenzial. ``abhaengig`` legt
    ``{nummer: ziel}``-Abhängigkeiten an.
    """
    abhaengig = abhaengig or {}
    lang = (
        "Die Loesung liest die erfassten Zeiten aus dem Projekttool und uebertraegt sie "
        "ohne Abtippen in die Rechnung. Betroffen ist der Teilprozess der Abrechnung; "
        "Daten fliessen vom Projekttool in die Buchhaltung. Beteiligt sind Projektleitung "
        "und Buchhaltung. Vorbedingung ist eine einheitliche Projektnummer. Sonderfaelle "
        "wie Nachtraege und Stornos gehen an einen Menschen."
    )
    return {
        "kontext": {
            "prozess_kurzbeschreibung": "Projekte durchfuehren und die Leistung abrechnen.",
            "hauptschmerzpunkte": [
                {"beschreibung": "Doppelerfassung", "auswirkung": "Fehler in der Rechnung",
                 "haeufigkeit": "woechentlich"},
            ],
        },
        "potenziale": [
            {
                "id": nr,
                "beschreibung": lang,
                "to_be_vision": lang,
                "to_be_kurz": "Zeiten wandern von selbst in die Rechnung.",
                "user_story": "Als Projektleitung moechte ich, dass Zeiten von selbst "
                              "abgerechnet werden, damit keine Doppelerfassung entsteht.",
                "akzeptanzkriterien": [
                    {"kriterium": "Gegeben eine erfasste Zeit, wenn der Monat endet, dann "
                                  "werden mindestens {grad_min} % ohne Nacharbeit abgerechnet.",
                     "messverfahren": "Stichprobe von Rechnungen"},
                ],
                "fachliche_anforderungen": ["Jede Zeit gehoert zu genau einem Projekt."],
                "betroffene_systeme": [
                    {"name": "Projekttool", "rolle": "Quelle", "integration": "API"},
                ],
                "loesungsansatz": "Anbindung des Projekttools an die Buchhaltung ueber die API.",
                "tech_stack_empfehlung": ["n8n"],
                "voraussetzungen": ["Einheitliche Projektnummern"],
                "risiken": [
                    {"beschreibung": "Schnittstelle aendert sich", "wahrscheinlichkeit": "low",
                     "auswirkung": "med", "gegenmassnahme": "Vertragstest"},
                ],
                "zukunftssicherheit": "Traegt auch bei mehr Projekten.",
                "abhaengigkeiten": (
                    [{"potenzial": abhaengig[nr], "grund": "Braucht die Projektnummer."}]
                    if nr in abhaengig else []
                ),
            }
            for nr in nummern
        ],
        "gesamtempfehlung_begruendung": "Erst der Quick Win, dann der Rest.",
    }


def _kennungen():
    zaehler = iter(range(1, 100))
    return lambda: str(uuid.UUID(int=next(zaehler)))


# ======================================================================
# Was das Modell sieht (6.3)
# ======================================================================


def test_die_nutzlast_traegt_keine_stunden_euro_oder_dauern():
    """6.3: keine der Urteilsstellen braucht sie, und dort brach #194.

    Das Profil von TP-2 trägt Häufigkeit und Dauern — sie dürfen in der
    Nutzlast nicht auftauchen, auch nicht als ``bc1_gemessen`` wie in der
    Erkennung.
    """
    bestand = _bestand()
    erkennung = erkenne(bestand, Doppelgaenger([_erkannt()]))
    nutzlast = baue_nutzlast(erkennung, bestand, STANDARD)

    def schluessel(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from schluessel(v)
        elif isinstance(o, list):
            for v in o:
                yield from schluessel(v)

    for k in schluessel(nutzlast):
        for verboten in ("frequency", "duration", "minutes", "bc1_gemessen", "stunden", "eur"):
            assert verboten not in k.lower(), k
    text = json.dumps(nutzlast, ensure_ascii=False)
    assert "999" not in text and "180" not in text


def test_die_nutzlast_traegt_korridor_anker_und_komplexitaet():
    bestand = _bestand()
    erkennung = erkenne(bestand, Doppelgaenger([_erkannt()]))
    n = baue_nutzlast(erkennung, bestand, STANDARD)

    p1, p2 = n["potenziale"]
    assert p1["korridor_pct"] == {"min": 60, "max": 85}  # Integration
    # TP-2: Skalen 4/4/3/4 → Mittel 3,75 → round(3,5) = 4.
    assert p1["komplexitaet"]["gemessen"] == 4
    # P2 berührt TP-1 ohne Profil: ein Maximum über eine Teilmenge wäre ein
    # verkapptes Urteil — Überschreiben ist Pflicht (Nachtrag 5).
    assert p2["komplexitaet"]["gemessen"] is None
    assert p2["komplexitaet"]["ueberschreiben"] == "pflicht"
    assert set(n["nutzwert_anker"]) == set(STANDARD.nutzwert_anker)
    assert set(n["nutzwert_anker"]["compliance"]) == {"1", "4", "7", "10"}

    tps = {t["teilprozess_id"]: t for t in n["kernprozesse"][0]["teilprozesse"]}
    assert tps["KP-06.TP-1"]["bc1_reifeskalen"] == "nicht erhoben"
    assert tps["KP-06.TP-2"]["bc1_reifeskalen"]["data_availability_score"] == 3
    assert tps["KP-06.TP-2"]["bc0_kriterien"] == {"Technologiebasis": 3.5, "Compliance": 2}


def test_ein_teilprozess_ohne_profil_bekommt_keine_leere_messung():
    m = messungen_je_teilprozess(_bestand())
    assert set(m) == {"KP-06.TP-2"}
    assert m["KP-06.TP-2"].focus_step_duration_minutes == 180.0
    assert isinstance(m["KP-06.TP-2"].frequency_per_year, float)


# ======================================================================
# Der Weg in den Rechenkern
# ======================================================================


def test_bewertung_ergibt_vollstaendige_eingaenge_fuer_den_rechenkern():
    bestand = _bestand()
    modell = Doppelgaenger([_erkannt(), _gut()])
    erkennung = erkenne(bestand, modell)
    b = bewerte(erkennung, bestand, modell, urteile=1, kennung=_kennungen())

    assert b.aufruf is not None and b.aufruf.versuche == 1
    assert b.kennungen == {
        "P1": str(uuid.UUID(int=1)),
        "P2": str(uuid.UUID(int=2)),
    }
    p1, p2 = b.eingaenge
    assert p1.klasse == "Integration" and p2.klasse == "Assistenz"  # 6.4
    assert [m.teilprozess_id for m in p1.messungen] == ["KP-06.TP-2"]
    assert [m.teilprozess_id for m in p2.messungen] == ["KP-06.TP-2"]

    lauf = rechne_lauf(NOROAI, "PKT-288", b.eingaenge)
    nach_id = {p.potenzial_id: p for p in lauf.potenziale}
    # P1 ist voll gemessen: 180 × 180 / 60 = 540 h, eine Value-Zahl.
    assert nach_id[p1.potenzial_id].value.value_quelle == "berechnet"
    assert nach_id[p1.potenzial_id].jahresstunden_zentral == pytest.approx(540.0)
    # P2 berührt TP-1 ohne Profil: keine Value-Zahl, keine Teilsumme.
    assert nach_id[p2.potenzial_id].value.value_quelle == "keine"
    assert "KP-06.TP-1" in nach_id[p2.potenzial_id].value.grund
    assert nach_id[p2.potenzial_id].komplexitaet_herkunft == "geurteilt"


def test_ohne_potenzial_wird_nicht_gefragt():
    bestand = _bestand()
    modell = Doppelgaenger([{"potenziale": [], "nicht_geschnitten": [
        {"teilprozess_id": "KP-06.TP-1", "grund": "x"},
        {"teilprozess_id": "KP-06.TP-2", "grund": "x"},
    ]}])
    erkennung = erkenne(bestand, modell)
    b = bewerte(erkennung, bestand, modell)

    assert b.eingaenge == () and b.aufruf is None
    assert len(modell.fragen) == 1  # nur die Erkennung


# ======================================================================
# Der Wächter (6.5)
# ======================================================================


ERWARTET = {
    "P1": Erwartung(korridor_pct=(60.0, 85.0), gemessene_komplexitaet=4),
    "P2": Erwartung(korridor_pct=(10.0, 30.0), gemessene_komplexitaet=None),
}


def test_der_waechter_laesst_eine_saubere_antwort_durch():
    assert pruefe_bewertung(_gut(), ERWARTET) == ()


@pytest.mark.parametrize(
    "aenderung, erwartet",
    [
        ({"angesetzt_min_pct": 50}, "ausserhalb des Korridors"),
        ({"angesetzt_max_pct": 90}, "ausserhalb des Korridors"),
        ({"angesetzt_min_pct": 80, "angesetzt_max_pct": 70}, "ueber angesetzt_max_pct"),
        ({"angesetzt_min_pct": "70"}, "muessen Zahlen sein"),
        ({"nutzwert": _nutzwert(11)}, "keine ganze Zahl von 1 bis 10"),
        ({"nutzwert": _nutzwert(0)}, "keine ganze Zahl von 1 bis 10"),
        ({"nutzwert": {**_nutzwert(), "qualitaet": {"wert": 6.5, "begruendung": "x"}}},
         "keine ganze Zahl"),
        ({"nutzwert": {**_nutzwert(), "qualitaet": {"wert": True, "begruendung": "x"}}},
         "keine ganze Zahl"),
        ({"nutzwert": _nutzwert(6, "")}, "ohne Begruendung"),
        ({"komplexitaet_ueberschrieben": 5}, "ohne Begruendung"),
        ({"komplexitaet_ueberschrieben": 12, "komplexitaet_begruendung": "x"},
         "keine ganze Zahl"),
        ({"aufwand_schaetzung_pt": 0}, "groesser null"),
        ({"aufwand_begruendung": " "}, "aufwand_begruendung fehlt"),
        ({"korridor_begruendung": "Etwa 80 % der Faelle sind einheitlich."}, "Zahl mit Einheit"),
        ({"aufwand_begruendung": "Rund 12 PT fuer die Anbindung."}, "Zahl mit Einheit"),
        ({"nutzwert": _nutzwert(6, "Spart 3 Stunden je Woche.")}, "Zahl mit Einheit"),
    ],
)
def test_der_waechter_verwirft(aenderung, erwartet):
    antwort = _gut()
    antwort["bewertungen"][0].update(aenderung)
    gruende = pruefe_bewertung(antwort, ERWARTET)
    assert any(erwartet in g for g in gruende), gruende


def test_zahlen_in_den_zahlenfeldern_sind_erlaubt():
    """Genau die Trennung, die der Wächter aus #248 nicht kennt."""
    antwort = _gut()
    antwort["bewertungen"][0].update(angesetzt_min_pct=72.5, aufwand_schaetzung_pt=7.5)
    assert pruefe_bewertung(antwort, ERWARTET) == ()


def test_nicht_gemessene_komplexitaet_muss_ueberschrieben_werden():
    antwort = _gut()
    antwort["bewertungen"][1].update(komplexitaet_ueberschrieben=None)
    assert any("Pflicht" in g for g in pruefe_bewertung(antwort, ERWARTET))


def test_jedes_potenzial_genau_einmal():
    fehlt = {"bewertungen": [_bewertung("P1")]}
    assert any("Nicht bewertet: P2" in g for g in pruefe_bewertung(fehlt, ERWARTET))

    doppelt = _gut()
    doppelt["bewertungen"].append(_bewertung("P1"))
    assert any("Mehrfach bewertet: P1" in g for g in pruefe_bewertung(doppelt, ERWARTET))

    fremd = _gut()
    fremd["bewertungen"].append(_bewertung("P9"))
    assert any("P9" in g for g in pruefe_bewertung(fremd, ERWARTET))


def test_kein_json_ist_ein_verstoss():
    assert pruefe_bewertung(None, ERWARTET)
    assert pruefe_bewertung({"etwas": []}, ERWARTET)


def test_eine_wiederholung_mit_benanntem_verstoss_dann_durch():
    bestand = _bestand()
    schlecht = _gut()
    schlecht["bewertungen"][0]["angesetzt_max_pct"] = 95
    modell = Doppelgaenger([_erkannt(), schlecht, _gut()])
    erkennung = erkenne(bestand, modell)

    b = bewerte(erkennung, bestand, modell, urteile=1)

    assert b.aufruf.versuche == 2
    assert any("ausserhalb des Korridors" in v for v in b.aufruf.verworfen)
    # Die Mahnung führt den Verstoß beim Namen mit — sonst wäre die
    # Wiederholung nur ein zweiter Würfelwurf.
    assert "ACHTUNG" in modell.fragen[-1] and "ausserhalb des Korridors" in modell.fragen[-1]


def test_die_mahnung_nennt_die_stelle_an_der_das_json_bricht():
    bestand = _bestand()
    kaputt = json.dumps(_gut(), ensure_ascii=False)[:-1]  # die letzte Klammer fehlt
    modell = Doppelgaenger([_erkannt(), kaputt, _gut()])
    erkennung = erkenne(bestand, modell)

    bewerte(erkennung, bestand, modell, urteile=1)

    assert "ACHTUNG" in modell.fragen[-1] and "Spalte" in modell.fragen[-1]


def test_bricht_die_wiederholung_auch_haelt_der_lauf_an():
    bestand = _bestand()
    schlecht = _gut()
    schlecht["bewertungen"][0]["korridor_begruendung"] = "Bei 90 % der Faelle."
    modell = Doppelgaenger([_erkannt(), schlecht, schlecht])
    erkennung = erkenne(bestand, modell)

    with pytest.raises(BewertungAbgebrochen) as fehler:
        bewerte(erkennung, bestand, modell, urteile=1)
    assert any("Zahl mit Einheit" in g for g in fehler.value.gruende)


# ======================================================================
# Mehrere Urteile, je Feld der Median (#299)
# ======================================================================


def _mit_nutzwert(antwort: dict, pid: str, kategorie: str, wert: int, text: str) -> dict:
    antwort = json.loads(json.dumps(antwort))
    b = next(x for x in antwort["bewertungen"] if x["id"] == pid)
    b["nutzwert"][kategorie] = {"wert": wert, "begruendung": text}
    return antwort


def _mit(antwort: dict, pid: str, **ueber) -> dict:
    antwort = json.loads(json.dumps(antwort))
    next(x for x in antwort["bewertungen"] if x["id"] == pid).update(ueber)
    return antwort


def test_je_kategorie_gilt_der_median_mit_der_begruendung_seines_urteils():
    a = _mit_nutzwert(_gut(), "P1", "durchlaufzeit", 7, "Uebergabe faellt weg.")
    b = _mit_nutzwert(_gut(), "P1", "durchlaufzeit", 4, "Nur ein Teil geht schneller.")
    c = _mit_nutzwert(_gut(), "P1", "durchlaufzeit", 5, "Etwas frueher fertig.")

    z = fuehre_zusammen([a, b, c], ERWARTET)

    p1 = z.antwort["bewertungen"][0]
    assert p1["nutzwert"]["durchlaufzeit"] == {"wert": 5, "begruendung": "Etwas frueher fertig."}
    assert z.streuung["P1"]["durchlaufzeit"] == (4, 7)
    # Was nicht streut, bleibt, wie es war.
    assert p1["nutzwert"]["qualitaet"]["wert"] == 6
    assert z.streuung["P1"]["qualitaet"] == (6, 6)


def test_die_lage_im_korridor_wird_je_grenze_getrennt_gemittelt():
    a = _mit(_gut(), "P1", angesetzt_min_pct=60, angesetzt_max_pct=85)
    b = _mit(_gut(), "P1", angesetzt_min_pct=70, angesetzt_max_pct=75)
    c = _mit(_gut(), "P1", angesetzt_min_pct=65, angesetzt_max_pct=80,
             korridor_begruendung="Die mittlere Lage.")

    p1 = fuehre_zusammen([a, b, c], ERWARTET).antwort["bewertungen"][0]

    assert (p1["angesetzt_min_pct"], p1["angesetzt_max_pct"]) == (65, 80)
    assert p1["korridor_begruendung"] == "Die mittlere Lage."
    assert pruefe_bewertung(fuehre_zusammen([a, b, c], ERWARTET).antwort, ERWARTET) == ()


def test_ein_urteil_ohne_ueberschreiben_zaehlt_mit_dem_gemessenen_wert():
    # P1 ist mit 4 gemessen. Zwei Urteile lassen es stehen, eines nicht.
    ueber = _mit(_gut(), "P1", komplexitaet_ueberschrieben=8, komplexitaet_begruendung="Viele Systeme.")
    p1 = fuehre_zusammen([_gut(), ueber, _gut()], ERWARTET).antwort["bewertungen"][0]
    assert p1["komplexitaet_ueberschrieben"] is None
    assert p1["komplexitaet_begruendung"] is None

    # Zwei überschreiben: der Median ist eines ihrer Urteile, mit Begründung.
    sechs = _mit(_gut(), "P1", komplexitaet_ueberschrieben=6, komplexitaet_begruendung="Zwei Systeme.")
    p1 = fuehre_zusammen([sechs, ueber, _gut()], ERWARTET).antwort["bewertungen"][0]
    assert p1["komplexitaet_ueberschrieben"] == 6
    assert p1["komplexitaet_begruendung"] == "Zwei Systeme."


def test_aufwand_ist_der_median_und_klassenzweifel_braucht_die_mehrheit():
    zweifel = "Eher eine Integration."
    a = _mit(_gut(), "P2", aufwand_schaetzung_pt=9, klassenzweifel=zweifel)
    b = _mit(_gut(), "P2", aufwand_schaetzung_pt=15, aufwand_begruendung="Mehr Abnahme.")
    c = _mit(_gut(), "P2", aufwand_schaetzung_pt=11, aufwand_begruendung="Mittel.")

    z = fuehre_zusammen([a, b, c], ERWARTET)
    p2 = z.antwort["bewertungen"][1]
    assert (p2["aufwand_schaetzung_pt"], p2["aufwand_begruendung"]) == (11, "Mittel.")
    assert z.streuung["P2"]["aufwand_schaetzung_pt"] == (9, 15)
    assert p2["klassenzweifel"] is None  # einer von dreien ist Rauschen

    b = _mit(b, "P2", klassenzweifel=zweifel)
    p2 = fuehre_zusammen([a, b, c], ERWARTET).antwort["bewertungen"][1]
    assert p2["klassenzweifel"] == zweifel


@pytest.mark.parametrize("anzahl", [0, 2, 4])
def test_nur_eine_ungerade_zahl_von_urteilen_hat_einen_median(anzahl):
    with pytest.raises(ValueError):
        fuehre_zusammen([_gut()] * anzahl, ERWARTET)


def test_bewerte_urteilt_n_mal_und_rechnet_mit_dem_median():
    bestand = _bestand()
    urteile = [
        _mit_nutzwert(_gut(), "P1", "compliance", w, f"Urteil {w}.") for w in (3, 9, 5)
    ]
    modell = Doppelgaenger([_erkannt(), *urteile])
    erkennung = erkenne(bestand, modell)

    b = bewerte(erkennung, bestand, modell, urteile=3, gleichzeitig=1)

    assert len(modell.fragen) == 4  # Erkennung und drei Urteile
    assert b.aufruf.versuche == 3 and len(b.urteile) == 3
    assert b.eingaenge[0].nutzwert.compliance.wert == 5
    assert b.eingaenge[0].nutzwert.compliance.begruendung == "Urteil 5."
    assert b.streuung["P1"]["compliance"] == (3, 9)


def test_bricht_eines_der_urteile_haelt_der_ganze_lauf_an():
    bestand = _bestand()
    schlecht = _mit(_gut(), "P1", korridor_begruendung="Bei 90 % der Faelle.")
    modell = Doppelgaenger([_erkannt(), _gut(), schlecht, schlecht])
    erkennung = erkenne(bestand, modell)

    with pytest.raises(BewertungAbgebrochen):
        bewerte(erkennung, bestand, modell, urteile=3, gleichzeitig=1)
    assert len(modell.fragen) == 4  # kein drittes Urteil nach dem Abbruch


def test_ohne_angabe_urteilt_der_lauf_dreimal():
    bestand = _bestand()
    modell = Doppelgaenger([_erkannt(), _gut(), _gut(), _gut()])
    b = bewerte(erkenne(bestand, modell), bestand, modell, gleichzeitig=1)
    assert len(b.urteile) == 3 and b.aufruf.schnitt == "Bewertung, Median aus 3"


def test_die_laufquelle_urteilt_ohne_angabe_wie_der_bewertungsschritt():
    eintrag = Paketeintrag("PKT-299", NOROAI, STAND, ("KP-06.TP-1", "KP-06.TP-2"))
    modell = Doppelgaenger([_erkannt(), _gut(), _gut(), _gut(), _ausgearbeitet("P1", "P2")])
    quelle = PaketLaufquelle(SpeicherPaketverzeichnis([eintrag]), _Quelle(), modell)
    quelle.ansicht("PKT-299")
    assert len(modell.fragen) == 5  # Erkennung, drei Urteile, ein Konzept


def test_eine_gerade_zahl_von_urteilen_wird_nicht_gestellt():
    bestand = _bestand()
    modell = Doppelgaenger([_erkannt()])
    with pytest.raises(ValueError):
        bewerte(erkenne(bestand, modell), bestand, modell, urteile=2)


# ======================================================================
# Der Anschluss: PaketLaufquelle
# ======================================================================


class _Quelle:
    """Eine Bestandsquelle, die immer denselben Bestand liefert."""

    def __init__(self) -> None:
        self.gelesen: list[tuple] = []

    def lies_paket(self, company_id, paket_id, uebergeben_am, teilprozess_ids):
        self.gelesen.append((company_id, paket_id, uebergeben_am, tuple(teilprozess_ids)))
        return _bestand()


def _laufquelle(antworten):
    eintrag = Paketeintrag("PKT-288", NOROAI, STAND, ("KP-06.TP-1", "KP-06.TP-2"))
    quelle = _Quelle()
    modell = Doppelgaenger(list(antworten))
    return PaketLaufquelle(SpeicherPaketverzeichnis([eintrag]), quelle, modell, urteile=1), quelle, modell


def test_die_liste_rechnet_nicht():
    """Ein Lauf kostet mehrere Modellaufrufe; die Liste soll sie nicht bezahlen."""
    laeufe, quelle, modell = _laufquelle([])

    koepfe = laeufe.uebersicht()

    assert [k.paket_id for k in koepfe] == ["PKT-288"]
    assert koepfe[0].anzahl_potenziale == 0 and "Noch nicht gerechnet" in koepfe[0].hinweise[0]
    assert koepfe[0].sperrgrund is None
    assert modell.fragen == [] and quelle.gelesen == []
    assert laeufe.uebersicht(company_id="ein-anderer-mandant") == []


def test_jedes_oeffnen_rechnet_neu():
    """Zustandslos, mit Absicht: ``neu_rechnen`` nach einem Reject braucht einen
    **neuen** Schnitt von der inneren Quelle. Einmal rechnen und dann zeigen ist
    die Aufgabe der ``AblegendeLaufquelle`` (#290)."""
    laeufe, quelle, modell = _laufquelle(
        [_erkannt(), _gut(), _ausgearbeitet("P1", "P2"),
         _erkannt(), _gut(), _ausgearbeitet("P1", "P2")]
    )

    erste = laeufe.ansicht("PKT-288")
    zweite = laeufe.ansicht("PKT-288")

    assert len(modell.fragen) == 6 and len(quelle.gelesen) == 2
    assert quelle.gelesen[0] == (NOROAI, "PKT-288", STAND, ("KP-06.TP-1", "KP-06.TP-2"))
    # Neu geschnitten heißt neue Kennungen (ADR-008 · BC2, 4.2).
    assert set(erste.potenziale).isdisjoint(zweite.potenziale)
    assert len(erste.eintraege) == 2
    assert erste.kp_namen == {"KP-06": "Projektdurchfuehrung"}
    # Das Modellurteil ist ein Hinweis, kein Sperrgrund (#305): der echte Weg ist lieferbar.
    assert "#299" in " ".join(erste.kopf.hinweise)
    assert erste.kopf.sperrgrund is None


def test_die_ablage_rechnet_einmal_und_zeigt_dann_das_abgelegte():
    from ablage import AblegendeLaufquelle, SpeicherErgebnisbuch

    innen, _, modell = _laufquelle([_erkannt(), _gut(), _ausgearbeitet("P1", "P2")])
    laeufe = AblegendeLaufquelle(innen, SpeicherErgebnisbuch())

    erste = laeufe.rechnen("PKT-288", neu=False)
    zweite = laeufe.ansicht("PKT-288")

    assert len(modell.fragen) == 3
    assert erste.potenzial_ids() == zweite.potenzial_ids()
    assert laeufe.uebersicht()[0].anzahl_potenziale == 2


def test_ein_angehaltener_lauf_wird_geworfen_nicht_als_leerer_lauf_abgelegt():
    """Ein leerer Lauf läge als gültiges Ergebnis in Schema ``bc2``. Geworfen,
    liegt er als gescheitert da, ohne Ergebnis und ohne eigene Fassung, und das
    nächste Öffnen rechnet Fassung 1 neu. *(Seit #295 beginnt die Ablage den
    Lauf, bevor sie rechnet: die Vorgänger-Kandidaten müssen vor der Erkennung
    feststehen.)*"""
    from ablage import AblegendeLaufquelle, SpeicherErgebnisbuch
    from laeufe import LaufAngehalten

    schlecht = _gut()
    schlecht["bewertungen"][0]["angesetzt_min_pct"] = 5
    innen, _, modell = _laufquelle(
        [_erkannt(), schlecht, schlecht, _erkannt(), _gut(), _ausgearbeitet("P1", "P2")]
    )
    buch = SpeicherErgebnisbuch()
    laeufe = AblegendeLaufquelle(innen, buch)

    with pytest.raises(LaufAngehalten, match="angehalten"):
        laeufe.rechnen("PKT-288", neu=False)
    gescheitert = buch.letzter("PKT-288")
    assert gescheitert.beleg.zustand == "fehler" and gescheitert.dokument is None

    nochmal = laeufe.rechnen("PKT-288", neu=False)
    assert len(nochmal.eintraege) == 2 and len(modell.fragen) == 6
    assert buch.letzter("PKT-288").beleg.fassung == 1


def test_ein_angehaltener_lauf_kommt_als_409_mit_grund(buch, gate1_buch, kopf):
    from app import erzeuge_app

    schlecht = _gut()
    schlecht["bewertungen"][0]["korridor_begruendung"] = "Bei 90 % der Faelle."
    laeufe, _, _ = _laufquelle([_erkannt(), schlecht, schlecht])
    client = TestClient(erzeuge_app(buch, laufquelle=laeufe, gate1_buch=gate1_buch))

    antwort = client.get("/api/oberflaeche/laeufe/PKT-288", headers=kopf)

    assert antwort.status_code == 409
    assert "Zahl mit Einheit" in antwort.json()["fehler"]


def test_unbekanntes_paket_ist_kein_lauf():
    laeufe, _, modell = _laufquelle([])
    assert laeufe.ansicht("GIBT-ES-NICHT") is None and modell.fragen == []


def test_der_lauf_kommt_ueber_die_oberflaeche_in_vertragsform(buch, gate1_buch, kopf):
    """Die Naht zur Oberfläche, über HTTP — nicht über die Funktion."""
    from app import erzeuge_app

    laeufe, _, _ = _laufquelle([_erkannt(), _gut(), _ausgearbeitet("P1", "P2")])
    client = TestClient(erzeuge_app(buch, laufquelle=laeufe, gate1_buch=gate1_buch))

    antwort = client.get("/api/oberflaeche/laeufe/PKT-288", headers=kopf)

    assert antwort.status_code == 200
    daten = antwort.json()
    assert {e["kp_id"] for e in daten["eintraege"]} == {"KP-06"}
    for pid, pot in daten["potenziale"].items():
        uuid.UUID(pid)  # der Vertrag verlangt eine UUID
        assert pot["automatisierungsgrad"]["klasse"] in STANDARD.korridore
        assert pot["aufwand_schaetzung_pt"] == 12
