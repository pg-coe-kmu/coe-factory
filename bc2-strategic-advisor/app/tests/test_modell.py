"""
Tests für das Value- und Priorisierungsmodell (#238, ADR-006 · BC2).

Geprüft werden vier Dinge, in dieser Reihenfolge der Wichtigkeit:

1. **Die bekannten Fallstricke.** Jeder von ihnen hat schon einmal einen
   falschen Befund erzeugt; sie stehen namentlich im Ticket. Ein Test je
   Fallstrick, mit dem Fund im Docstring — damit niemand ihn »aufräumt«.
2. **Reproduzierbarkeit.** Gleiches Paket, gleiche Zahlen (ADR-006, 2.9). Der
   Rechenkern ist rein; das ist hier prüfbar und nicht erst im Betrieb.
3. **Die Entscheidungen aus #238.** Mitte der Eingänge, Nutzwert allein,
   Bänder als Parameter — jede mit einem Test, der fehlschlägt, wenn sie
   still zurückgedreht wird.
4. **Vertragstreue.** Die Ausgabe passt in ``konzept.schema.json`` v3.0 und
   ``priorisierung.schema.json``. Nicht selbst nachgebaut, sondern gegen die
   echten Schemadateien validiert.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from modell import (
    Nutzwert,
    Nutzwertkategorie,
    Parameter,
    Potenzialeingang,
    rechne_lauf,
    runde,
)
from modell.ausgabe import (
    als_eingangswerte,
    als_eintraege,
    als_konzept_potenzial,
    als_prozess_raenge,
)

VERTRAEGE = Path(__file__).resolve().parents[3] / "contracts" / "bc2-to-bc3"


# --------------------------------------------------------------------- Hilfen


def _nutzwert(*werte: int) -> Nutzwert:
    """Fünf Kategorien aus fünf Zahlen — oder aus einer für alle fünf."""
    if len(werte) == 1:
        werte = werte * 5
    q, d, f, m, c = werte
    mach = lambda w: Nutzwertkategorie(w, "Begruendungssatz fuer den Test.")  # noqa: E731
    return Nutzwert(mach(q), mach(d), mach(f), mach(m), mach(c))


def eingang(**ueber) -> Potenzialeingang:
    """Ein brauchbares Potenzial; einzelne Felder je Test überschrieben."""
    vorgabe = dict(
        potenzial_id=str(uuid.uuid5(uuid.NAMESPACE_URL, ueber.get("titel", "P-STANDARD"))),
        titel="Rechnungsstellung aus der Zeiterfassung",
        kp_id="KP-06",
        betroffene_teilprozess_ids=("KP-06.TP-2",),
        klasse="Integration",
        automatisierungsgrad_begruendung="Zwei Systeme verbinden, kein Textverstehen noetig.",
        nutzwert=_nutzwert(6),
        frequency_per_year=180.0,
        total_duration_minutes=180.0,
        focus_step_duration_source="geschaetzt",
        focus_step_duration_confidence_pct=60.0,
        reifeskalen=(4, 4, 3, 4),
        aufwand_schaetzung_pt=12.0,
        erhebung_id="ERH-0001",
    )
    vorgabe.update(ueber)
    return Potenzialeingang(**vorgabe)


def lauf_mit(*eingaenge, parameter=None):
    p = {"parameter": parameter} if parameter else {}
    return rechne_lauf("7c2d5ee9-2a9a-5990-810f-502ea2b2012d", "PKT-2026-0007", eingaenge, **p)


# ======================================================================
# 1. Die bekannten Fallstricke
# ======================================================================


def test_executions_per_run_ist_kein_multiplikator():
    """Invariante I2 des BC1-Vertrags (#184) — der teuerste Fallstrick.

    Die echte BC1-Zeile fuer KP-06.TP-2 traegt ``frequency_per_year = 180`` und
    ``total_duration_minutes = 180``; ``executions_per_run`` ist in allen drei
    gelieferten Zeilen **gleich** der Frequenz. Richtig gerechnet sind das
    540 h/Jahr und 23.220 EUR Ist-Kosten — die Zahl, die ADR-006 2.5 nennt.
    Wer ``executions_per_run`` multipliziert, erhaelt 97.200 h, ein Vielfaches
    der Gesamtkapazitaet eines Zehn-Personen-Betriebs, fuer EINEN Schritt.

    Die staerkste Form der Zusage steht nicht hier, sondern im Typ:
    ``Potenzialeingang`` kennt das Feld gar nicht.
    """
    pot = lauf_mit(eingang()).potenziale[0]

    assert pot.jahresstunden_zentral == pytest.approx(540.0)
    assert pot.value.ist_kosten_eur_jahr.mitte == pytest.approx(540.0 * 43)
    assert runde(pot.value.ist_kosten_eur_jahr.mitte) == 23_220
    assert "executions_per_run" not in Potenzialeingang.__dataclass_fields__


def test_ohne_herkunft_der_dauer_gibt_es_keine_value_zahl():
    """ADR-006 2.3: bei NULL **gar keine** Zahl statt einer sehr breiten.

    Eine Spanne von ±100 % ist keine Aussage mehr. BC2 rechnet qualitativ
    weiter und vermerkt die Luecke — der Lauf bleibt vollstaendig.
    """
    pot = lauf_mit(eingang(focus_step_duration_source=None)).potenziale[0]

    assert pot.value.value_quelle == "keine"
    assert pot.value.einsparung_eur_jahr is None
    assert pot.value.grund and "NULL" in pot.value.grund
    assert pot.aufwand_herkunft == "unbekannt"
    # Der Lauf faellt nicht aus: Nutzwert, Komplexitaet, Score und Rang stehen.
    assert pot.impact >= 1 and pot.prioritaet_score >= 1


def test_fehlende_reifeskalen_machen_die_komplexitaet_geurteilt():
    """ADR-006 2.6: fehlen BC1s vier Skalen, urteilt das LLM allein.

    Der Vertrag sagt die Skalen bei ``status='fertig'`` zu, die Datenbank
    erzwingt es nicht.
    """
    pot = lauf_mit(
        eingang(
            reifeskalen=None,
            komplexitaet_ueberschrieben=5,
            komplexitaet_begruendung="BC1 liefert fuer diesen Teilprozess keine Reifeskalen.",
        )
    ).potenziale[0]

    assert pot.umsetzungskomplexitaet == 5
    assert pot.komplexitaet_herkunft == "geurteilt"
    assert pot.komplexitaet_begruendung


def test_ueberschreiben_auch_mit_skalen_bleibt_geurteilt():
    """Auch wenn gemessen werden koennte: ueberschrieben heisst 'geurteilt'.

    Der Vertrag sagt es ausdruecklich. Sonst truege ein LLM-Urteil das Etikett
    einer Messung.
    """
    pot = lauf_mit(
        eingang(komplexitaet_ueberschrieben=8, komplexitaet_begruendung="Alt-System ohne API.")
    ).potenziale[0]

    assert pot.umsetzungskomplexitaet == 8
    assert pot.komplexitaet_herkunft == "geurteilt"


def test_ueberschreiben_ohne_begruendung_wird_abgewiesen():
    """ADR-006 2.6 laesst das Ueberschreiben nur **begruendet** zu."""
    with pytest.raises(ValueError, match="Begruendung"):
        eingang(komplexitaet_ueberschrieben=8, komplexitaet_begruendung=None)


def test_kapazitaetsschranke_haengt_an_statt_abzuweisen():
    """Invariante I3 (#172): die Pruefung ist **formal, nicht fachlich**.

    Plausibilitaet liegt bei BC0/BC1. BC2 rechnet durch und haengt einen
    Hinweis an — es weist nichts zurueck.
    """
    # 2.600 Durchlaeufe x 150 min = 6.500 h/Jahr; knapp unter der harten Grenze,
    # deutlich ueber der internen Warnschwelle von 7.040 h liegt erst die Summe.
    pot = lauf_mit(
        eingang(frequency_per_year=2_600.0, total_duration_minutes=200.0)
    ).potenziale[0]

    assert pot.jahresstunden_zentral == pytest.approx(8_666.667, rel=1e-4)
    assert any(h.art == "kapazitaet_ueberschritten" for h in pot.hinweise)
    # Trotz Schranke: die Zahlen stehen, nichts wurde verworfen.
    assert pot.value.value_quelle == "berechnet"
    assert pot.value.einsparung_eur_jahr.min > 0


def test_testdaten_werden_durchgereicht_nicht_abgewiesen():
    """#184: BC1s Kennzeichnung wandert mit, statt den Lauf zu stoppen."""
    pot = lauf_mit(eingang(kennzeichnung="Testdaten aus der Erhebung vom 08.09.")).potenziale[0]

    assert any(h.art == "testdaten" for h in pot.hinweise)
    assert pot.value.value_quelle == "berechnet"
    assert all(q.kennzeichnung for q in pot.eingangswerte if q.herkunft_tabelle == "bc1.prozessprofil")


def test_bc1_schaetzung_ist_nur_probe_kein_vorrang():
    """ADR-006 2.2: falsche Koernung — das Feld haengt am Fokus-Schritt.

    Weicht es vom angesetzten Korridor ab, ist das ein **Signal**, kein
    Korrekturbefehl: die Zahlen bleiben, ein Hinweis kommt dazu.
    """
    ohne = lauf_mit(eingang()).potenziale[0]
    mit = lauf_mit(eingang(automation_potential_estimate_pct=20.0)).potenziale[0]

    assert any(h.art == "bc1_abweichung" for h in mit.hinweise)
    # Der Wert selbst aendert nichts an der Rechnung.
    assert mit.value.einsparung_eur_jahr == ohne.value.einsparung_eur_jahr
    assert mit.prioritaet_score == ohne.prioritaet_score


# ======================================================================
# 2. Reproduzierbarkeit
# ======================================================================


def test_gleiche_eingaenge_gleiche_zahlen():
    """ADR-006 2.9. Die Zusage, auf der die ganze Nachrechenbarkeit ruht."""
    eingaenge = [
        eingang(titel="A", kp_id="KP-02", betroffene_teilprozess_ids=("KP-02.TP-1",)),
        eingang(titel="B", kp_id="KP-03", betroffene_teilprozess_ids=("KP-03.TP-1",)),
    ]
    assert lauf_mit(*eingaenge) == lauf_mit(*eingaenge)


def test_die_reihenfolge_der_eingaenge_aendert_das_ergebnis_nicht():
    """Sonst haenge die Rangfolge daran, in welcher Reihenfolge gelesen wurde."""
    a = eingang(titel="A", kp_id="KP-02", betroffene_teilprozess_ids=("KP-02.TP-1",))
    b = eingang(titel="B", kp_id="KP-03", betroffene_teilprozess_ids=("KP-03.TP-1",))

    vorwaerts = {p.potenzial_id: p.potenzialrang for p in lauf_mit(a, b).potenziale}
    rueckwaerts = {p.potenzial_id: p.potenzialrang for p in lauf_mit(b, a).potenziale}
    assert vorwaerts == rueckwaerts


def test_gleichstand_wird_stabil_aufgeloest():
    """Bei gleichem Score entscheidet die potenzial_id — willkuerlich, aber stabil."""
    a = eingang(titel="A", kp_id="KP-02", betroffene_teilprozess_ids=("KP-02.TP-1",))
    b = eingang(titel="B", kp_id="KP-03", betroffene_teilprozess_ids=("KP-03.TP-1",))
    lauf = lauf_mit(a, b)

    assert lauf.potenziale[0].prioritaet_score == lauf.potenziale[1].prioritaet_score
    assert lauf.potenziale[0].potenzial_id < lauf.potenziale[1].potenzial_id


def test_doppelte_potenzial_id_wird_abgewiesen():
    """Eine Kennung, ein Inhalt (ADR-002)."""
    with pytest.raises(ValueError, match="Doppelte potenzial_id"):
        lauf_mit(eingang(), eingang())


# ======================================================================
# 3. Die Entscheidungen aus #238
# ======================================================================


def test_impact_monetaer_kommt_aus_der_mitte_der_eingaenge():
    """Entscheidung #238, Frage 1 — und sie ist messbar von den Alternativen verschieden.

    ``Integration`` spannt 60–85 %. Die Mitte der Eingaenge ist
    ``stunden x satz x 72,5 %``; die Mitte der **Spanne** liegt darueber, weil
    die Eckenrechnung beide Fehler gleichsinnig multipliziert.
    """
    pot = lauf_mit(eingang()).potenziale[0]
    spanne = pot.value.einsparung_eur_jahr

    erwartet = 540.0 * 43 * 0.725
    assert pot.value.einsparung_zentral_eur == pytest.approx(erwartet)
    # Der zentrale Wert ist NICHT die Mitte der Spanne — sonst waere die
    # Entscheidung wirkungslos.
    assert pot.value.einsparung_zentral_eur < spanne.mitte
    assert spanne.min < pot.value.einsparung_zentral_eur < spanne.max


def test_ohne_value_zahl_traegt_der_nutzwert_den_impact_allein():
    """Entscheidung #238, Frage 2.

    ``impact_monetaer = 1`` waere die Alternative gewesen und behandelte eine
    **fehlende Messung** wie eine gemessene Wertlosigkeit. Gemessen am vollen
    Satz kostete das denselben Prozess fuenf Raenge.
    """
    pot = lauf_mit(eingang(nutzwert=_nutzwert(7, 6, 6, 6, 6), focus_step_duration_source=None)).potenziale[0]

    assert pot.impact_monetaer is None
    assert pot.impact == 6  # round(6.2), nicht round((1 + 6.2) / 2) == 4
    assert "Nutzwert" in pot.impact_herleitung


def test_score_baender_sind_ein_parameter_kein_gemeisselter_wert():
    """Entscheidung #238, Frage 3: kalibrierbar, ohne den Kern anzufassen.

    Festgezurrt wird am ersten echten Lauf (#206) — auf erfundenen
    Prototyp-Zahlen zu kalibrieren hiesse, auf nichts zu kalibrieren.
    """
    e = eingang()
    assert lauf_mit(e).potenziale[0].prioritaetsgruppe == "PRIO 2"

    gerueckt = Parameter(band_prio1=30.0, band_prio2=15.0)
    assert lauf_mit(e, parameter=gerueckt).potenziale[0].prioritaetsgruppe == "PRIO 1"


def test_euro_schwellen_sind_ebenfalls_ein_parameter():
    e = eingang()
    hoch = lauf_mit(e, parameter=Parameter(euro_schwelle_oben=20_000.0)).potenziale[0]
    standard = lauf_mit(e).potenziale[0]
    assert hoch.impact_monetaer >= standard.impact_monetaer


def test_unsinnige_parameter_werden_beim_anlegen_abgewiesen():
    with pytest.raises(ValueError, match="Euro-Schwellen"):
        Parameter(euro_schwelle_unten=60_000.0)
    with pytest.raises(ValueError, match="Score-Baender"):
        Parameter(band_prio1=10.0, band_prio2=50.0)


def test_kaufmaennisch_runden_nicht_zur_geraden_zahl():
    """Ein Pruefer rechnet von Hand nach — und rundet dabei kaufmaennisch.

    Pythons eingebautes ``round`` macht aus 2,5 eine 2. Bei
    ``komplexitaet = round(11 - 2 x reife)`` trifft das real: Reife 3,25 ergibt
    4,5 — kaufmaennisch 5, bankmaessig 4, ein ganzer Score-Schritt.
    """
    assert runde(2.5) == 3
    assert runde(3.5) == 4
    assert round(2.5) == 2  # zum Vergleich: das eingebaute Verhalten

    pot = lauf_mit(eingang(reifeskalen=(3, 3, 3, 4))).potenziale[0]  # Mittel 3,25
    assert pot.umsetzungskomplexitaet == 5


# ======================================================================
# Die Rechnung selbst
# ======================================================================


def test_komplexitaet_aus_den_vier_skalen():
    """``komplexitaet = round(11 - 2 x reife)``, Wertebereich 1-9."""
    pot = lauf_mit(eingang(reifeskalen=(4, 4, 3, 4))).potenziale[0]  # Mittel 3,75
    assert pot.umsetzungskomplexitaet == 4  # round(11 - 7,5) = round(3,5) = 4
    assert pot.komplexitaet_herkunft == "gemessen"
    assert "3.75" in pot.komplexitaet_begruendung

    # Der bekannte Schoenheitsfehler: die 10 wird nie erreicht.
    schlecht = lauf_mit(eingang(reifeskalen=(1, 1, 1, 1))).potenziale[0]
    assert schlecht.umsetzungskomplexitaet == 9


def test_ersparnis_prozent_ist_genau_der_angesetzte_korridor():
    """Eigenschaft der Eckenrechnung: die Stunden kuerzen sich heraus.

    ``einsparung_lo / ist_lo == angesetzt.min`` — und oben ebenso. Faellt dieser
    Test, ist die Eckenrechnung nicht mehr das, was ADR-006 2.3 beschreibt.
    """
    pot = lauf_mit(eingang(klasse="Extraktion")).potenziale[0]  # 50-75 %
    assert pot.value.ersparnis_prozent.min == pytest.approx(50.0)
    assert pot.value.ersparnis_prozent.max == pytest.approx(75.0)


def test_amortisation_dreht_die_spanne_um():
    """Hohe Einsparung heisst **kurze** Amortisation — min und max tauschen."""
    pot = lauf_mit(eingang()).potenziale[0]
    a, e = pot.value.amortisation_monate, pot.value.einsparung_eur_jahr
    investition = pot.value.investition_eur_richtwert

    assert a.min == pytest.approx(investition / (e.max / 12))
    assert a.max == pytest.approx(investition / (e.min / 12))
    assert a.min < a.max


def test_angesetzter_grad_muss_im_korridor_seiner_klasse_liegen():
    """Der Korridor ist die Leitplanke des LLM-Urteils (ADR-006, 2.2).

    Liegt die angesetzte Spanne ausserhalb, ist entweder die Klasse falsch
    gewaehlt oder die Lage falsch begruendet — beides soll auffallen.
    """
    # Innerhalb: das LLM verengt 60-85 % auf 70-80 %.
    pot = lauf_mit(eingang(angesetzt_min_pct=70.0, angesetzt_max_pct=80.0)).potenziale[0]
    assert pot.automatisierungsgrad.angesetzt.min == pytest.approx(0.70)

    with pytest.raises(ValueError, match="ausserhalb des Korridors"):
        lauf_mit(eingang(klasse="Assistenz", angesetzt_min_pct=70.0, angesetzt_max_pct=80.0))

    with pytest.raises(ValueError, match="gehoeren\n?\\s*zusammen|gehoeren zusammen"):
        lauf_mit(eingang(angesetzt_min_pct=70.0))


def test_ohne_angesetzte_spanne_gilt_der_ganze_korridor():
    pot = lauf_mit(eingang(klasse="Textgenerierung")).potenziale[0]  # 30-50 %
    assert pot.automatisierungsgrad.angesetzt == pot.automatisierungsgrad.korridor
    assert pot.automatisierungsgrad.angesetzt.min == pytest.approx(0.30)


def test_kategorie_ist_ein_etikett_keine_reihenfolge():
    """Die vierte Ecke heisst 'Zurueckgestellt', nicht 'Long Bet'."""
    faelle = [
        (_nutzwert(9), (5, 5, 5, 5), "Quick Win"),     # hoher Impact, K=1
        (_nutzwert(9), (1, 1, 1, 1), "Strategisch"),   # hoher Impact, K=9
        (_nutzwert(2), (5, 5, 5, 5), "Optional"),      # kleiner Impact, K=1
        (_nutzwert(2), (1, 1, 1, 1), "Zurueckgestellt"),
    ]
    for nw, reife, erwartet in faelle:
        pot = lauf_mit(eingang(nutzwert=nw, reifeskalen=reife)).potenziale[0]
        assert pot.kategorie == erwartet, f"{nw.mittel=} {reife=} -> {pot.kategorie}"


def test_prozessrang_ist_der_rang_des_besten_potenzials():
    """Nicht Summe, nicht Mittel (ADR-006, 2.7).

    Eine Summe bevorzugte Prozesse mit vielen kleinen Potenzialen; ein Mittel
    bestrafte einen Prozess dafuer, dass er neben seinem Quick Win noch
    schwierige Potenziale hat.
    """
    lauf = lauf_mit(
        # KP-02 traegt ein starkes und ein schwaches Potenzial ...
        eingang(titel="stark", kp_id="KP-02", betroffene_teilprozess_ids=("KP-02.TP-1",),
                nutzwert=_nutzwert(9), reifeskalen=(5, 5, 5, 5)),
        eingang(titel="schwach", kp_id="KP-02", betroffene_teilprozess_ids=("KP-02.TP-2",),
                nutzwert=_nutzwert(2), reifeskalen=(1, 1, 1, 1)),
        # ... KP-03 nur ein mittleres.
        eingang(titel="mittel", kp_id="KP-03", betroffene_teilprozess_ids=("KP-03.TP-1",),
                nutzwert=_nutzwert(6), reifeskalen=(4, 4, 4, 4)),
    )
    raenge = {r.kp_id: r for r in lauf.prozess_raenge}

    assert raenge["KP-02"].rang == 1, "das schwache Potenzial darf KP-02 nicht herunterziehen"
    assert raenge["KP-03"].rang == 2
    bestes = {p.potenzial_id: p for p in lauf.potenziale}[raenge["KP-02"].bestes_potenzial_id]
    assert bestes.titel == "stark"


def test_der_lauf_meldet_die_summe_der_jahresstunden():
    lauf = lauf_mit(
        eingang(titel="A", kp_id="KP-02", betroffene_teilprozess_ids=("KP-02.TP-1",)),
        eingang(titel="B", kp_id="KP-03", betroffene_teilprozess_ids=("KP-03.TP-1",)),
    )
    assert lauf.jahresstunden_gesamt == pytest.approx(1_080.0)
    assert lauf.hinweise == ()  # unter der Warnschwelle


def test_lauf_ohne_potenziale_ist_kein_lauf():
    with pytest.raises(ValueError, match="kein Lauf"):
        lauf_mit()


# ======================================================================
# 4. Vertragstreue — gegen die echten Schemadateien
# ======================================================================


def _schema(name: str) -> dict:
    return json.loads((VERTRAEGE / name).read_text(encoding="utf-8"))


TEXT_300 = (
    "Beschreibungstext fuer den Test, ausreichend lang, damit die vom Vertrag "
    "geforderte Mindestlaenge von 300 Zeichen erreicht wird. Er benennt, was "
    "automatisiert wird, in welchem Prozessschritt, mit welchem Ergebnis, "
    "welche Datenfluesse betroffen sind, welche Rollen beteiligt sind, welche "
    "Vorbedingungen gelten und welche Sonderfaelle auftreten koennen. "
)


def _texte(pot) -> dict:
    """Die Felder, die das **LLM** schreibt — der Kern kennt sie nicht.

    Sie stehen hier als Fuellung, damit gegen das vollstaendige Schema
    validiert werden kann und nicht nur gegen den Ausschnitt.
    """
    return {
        "beschreibung": TEXT_300,
        "to_be_vision": TEXT_300,
        "user_story": "Als Projektleiterin moechte ich die Rechnung automatisch "
                      "erzeugt bekommen, damit ich keine Stunden abtippe.",
        "akzeptanzkriterien_geschaeftlich": [
            {
                "kriterium": "Gegeben eine abgeschlossene Woche, wenn der Lauf startet, "
                             "dann liegt je Projekt ein Rechnungsentwurf vor.",
                "messverfahren": "Stichprobe von 50 Vorgaengen im Vorgangsprotokoll.",
            }
        ],
        "fachliche_anforderungen": ["Die Zeiterfassung ist bis Montag 09:00 Uhr gepflegt."],
        "betroffene_prozessschritte": ["Stunden zusammenstellen", "Rechnung entwerfen"],
        "betroffene_systeme": [
            {"name": "Zeiterfassung", "rolle": "Quelle", "integration": "API"}
        ],
        "querschnitte": {
            "zukunftssicherheit": "Traegt, solange die Zeiterfassung bleibt.",
            "reifegrad": "Bitkom-Reifegrad 3,7 — rangiert, trennt aber nicht.",
        },
        "potenzielle_loesung": {
            "ansatz": "Ein Dienst liest die Zeiten und erzeugt den Entwurf im Rechnungssystem.",
            "tech_stack_empfehlung": ["Python", "REST"],
        },
        "voraussetzungen": ["Zugang zur Zeiterfassungs-API"],
    }


def _konzept(lauf, gelesen_am: datetime) -> dict:
    """Ein vollstaendiges Konzept je Kernprozess — gerechnete Felder plus Texte."""
    kp = lauf.potenziale[0].kp_id
    pots = [p for p in lauf.potenziale if p.kp_id == kp]
    return {
        "konzept_id": str(uuid.uuid4()),
        "ersetzt_konzept_id": None,
        "schema_version": "3.0",
        "company_id": lauf.company_id,
        "paket_id": lauf.paket_id,
        "uebergeben_am": "2026-09-20T14:32:11+00:00",
        "gelesen_am": gelesen_am.isoformat(),
        "fassung": 1,
        "erzeugt_am": gelesen_am.isoformat(),
        "erzeugt_von": "bc2-advisor@v3.0",
        "kontext": {
            "prozess_kurzbeschreibung": "Rechnungsstellung aus der Zeiterfassung.",
            "kp_id": kp,
            "hauptschmerzpunkte": [
                {"beschreibung": "Stunden werden abgetippt.", "auswirkung": "Fehler und Verzug."}
            ],
        },
        "potenziale": [
            als_konzept_potenzial(p, _nutzwert(6)) | _texte(p) for p in pots
        ],
        "gesamtempfehlung": {
            "reihenfolge_potenzial_ids": [p.potenzial_id for p in pots],
            "begruendung": "Nach Score.",
        },
        "eingangswerte": [
            z for p in pots for z in als_eingangswerte(p, gelesen_am)
        ],
    }


def test_die_ausgabe_passt_in_konzept_schema_v3_0():
    """Nicht nachgebaut, sondern gegen die echte Vertragsdatei validiert.

    Genau hier faellt auf, wenn eine Schreibweise abweicht — der Prototyp aus
    #167 schrieb die Klasse als ``Regelwerk / Weiterleitung`` mit Leerzeichen
    und waere am Enum des Vertrags gescheitert.
    """
    jsonschema = pytest.importorskip("jsonschema")

    gelesen_am = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)
    lauf = lauf_mit(eingang())
    jsonschema.Draft202012Validator(_schema("konzept.schema.json")).validate(
        _konzept(lauf, gelesen_am)
    )


def test_auch_ein_potenzial_ohne_value_zahl_passt_in_den_vertrag():
    """Der Fall, den ADR-006 2.3 ausdruecklich offenhaelt — er muss ausliefern koennen."""
    jsonschema = pytest.importorskip("jsonschema")

    gelesen_am = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)
    lauf = lauf_mit(eingang(focus_step_duration_source=None))
    konzept = _konzept(lauf, gelesen_am)

    assert konzept["potenziale"][0]["value"]["value_quelle"] == "keine"
    assert konzept["potenziale"][0]["impact_monetaer"] is None
    jsonschema.Draft202012Validator(_schema("konzept.schema.json")).validate(konzept)


def test_die_priorisierung_passt_in_ihr_schema():
    jsonschema = pytest.importorskip("jsonschema")

    lauf = lauf_mit(
        eingang(titel="A", kp_id="KP-02", betroffene_teilprozess_ids=("KP-02.TP-1",)),
        eingang(titel="B", kp_id="KP-03", betroffene_teilprozess_ids=("KP-03.TP-1",)),
    )
    konzept_ids = {"KP-02": str(uuid.uuid4()), "KP-03": str(uuid.uuid4())}
    priorisierung = {
        "priorisierung_id": str(uuid.uuid4()),
        "schema_version": "3.0",
        "company_id": lauf.company_id,
        "paket_id": lauf.paket_id,
        "uebergeben_am": "2026-09-20T14:32:11+00:00",
        "gelesen_am": "2026-09-20T15:00:00+00:00",
        "fassung": 1,
        "erzeugt_am": "2026-09-20T15:00:00+00:00",
        "score_formel": "score = impact x (11 - umsetzungskomplexitaet)",
        "konzept_ids": sorted(konzept_ids.values()),
        "eintraege": als_eintraege(lauf, konzept_ids),
        "prozess_raenge": als_prozess_raenge(lauf, konzept_ids),
        # 'pending', nicht 'offen': gate1.status ist eines der wenigen Felder des
        # Vertrags mit englischem Enum. Beim ersten Schreiben hier falsch geraten
        # und vom Schema gefangen — genau dafuer validiert dieser Test gegen die
        # echte Vertragsdatei statt gegen einen Nachbau.
        "gate1": {"status": "pending"},
    }
    jsonschema.Draft202012Validator(_schema("priorisierung.schema.json")).validate(priorisierung)


def test_die_eingangswerte_tragen_herkunft_und_lesezeitpunkt():
    """Auflage 2 aus #238: jede Zahl sagt, woher sie kommt.

    Der Grund steht in ADR-006 2.9 — die Lieferung muss **ohne
    Datenbankzugriff** pruefbar sein, als Datei bei BC3 und als Praesentation
    beim Mandanten.
    """
    gelesen_am = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)
    pot = lauf_mit(eingang()).potenziale[0]
    zeilen = als_eingangswerte(pot, gelesen_am)

    nach_groesse = {z["groesse"]: z for z in zeilen}
    assert nach_groesse["total_duration_minutes"]["herkunft_tabelle"] == "bc1.prozessprofil"
    assert nach_groesse["total_duration_minutes"]["herkunft_id"] == "ERH-0001"
    assert nach_groesse["total_duration_minutes"]["betrifft_teilprozess_id"] == "KP-06.TP-2"
    # Auch die Setzungen reisen mit — sonst stuende im Konzept eine Zahl, deren
    # Herkunft nur im ADR nachzulesen waere.
    assert nach_groesse["mischsatz_eur_h"]["wert"] == 43.0
    assert nach_groesse["bausatz_eur_pt"]["herkunft_tabelle"] == "(Setzung)"
    assert all(z["gelesen_am"] == gelesen_am.isoformat() for z in zeilen)
