"""Schicht a — Antwortkatalog ohne KI (Spec Antwortformen, Abschnitt 5).

Je Eintrag zwei Wege, kein Weg liefert einen anderen gueltigen Wert als erwartet:
(1) direkt: Kurzform -> Normalisierer -> Pruefer, erwartet `fest`;
(2) die KI reicht woertlich durch: Normalisierer -> Pruefer auf dem Rohtext,
    erwartet `fest` oder (bei nackten Zahlen) den `vertrag`-Wert.
"Nachfrage" heisst: ungueltig oder keine Kurzform.
"""
from pathlib import Path

import pytest

from werkzeuge.katalog import baue_paket, lade_katalog, weg_direkt, weg_woertlich

KATALOG = lade_katalog(Path(__file__).parent / "daten" / "antwortkatalog.json")
PAKET = baue_paket(KATALOG["kontext"])


def test_katalog_baut_das_paket_mit_dem_testkontext():
    # Kontext-Zweig (1.2+ctx-...), nicht das kontextfreie Paket
    assert PAKET.schema_version.startswith("1.2+ctx-")
    # genau ein Eigner-Vorschlag (KP-01 -> R-01) geht in die Frage nach B3 ein
    assert "Laut BC0 ist das Geschäftsführung (R-01)." in PAKET.field("process_owner_role").question
    assert PAKET.field("focus_step_systems").typ.validator("S-01") is True


def test_katalog_variante_ohne_eigner_stellt_b3_ohne_vorschlag():
    paket = baue_paket(KATALOG["kontext"], "ohne_eigner")
    assert "Laut BC0" not in paket.field("process_owner_role").question
    assert "Laut BC0" in PAKET.field("process_owner_role").question


def test_katalog_kontext_nennt_kernprozesse_und_teilprozesse():
    assert "KP-01 = Auftrag-Abwicklung" in PAKET.field("process_id").question
    assert "KP-02.TP-1 = Lieferanten-Bewertung" in PAKET.field("focus_step").question


def _wert_von(angabe):
    """Der konkrete Wert einer `fest`/`ki`-Angabe; None bei reiner Nachfrage."""
    if angabe == "Nachfrage":
        return None
    return angabe.removesuffix(" oder Nachfrage")


def test_katalog_schema():
    # genau diese Schluessel; `variante` ist optional und kennt nur "ohne_eigner"
    pflicht = {"feld", "antwort", "fest", "ki", "vertrag"}
    for eintrag in KATALOG["eintraege"]:
        name = f"{eintrag['feld']}-{eintrag['antwort']}"
        assert pflicht <= set(eintrag) <= pflicht | {"variante"}, name
        assert eintrag.get("variante", "ohne_eigner") == "ohne_eigner", name
        spec = PAKET.field(eintrag["feld"])
        assert spec is not None, name
        assert isinstance(eintrag["antwort"], str) and eintrag["antwort"], name
        for schluessel in ("fest", "ki"):
            angabe = eintrag[schluessel]
            assert isinstance(angabe, str) and angabe, name
            wert = _wert_von(angabe)
            # Grenzform immer mit dem konkreten Wert, nie "Grenzfall" allein
            assert wert is None or " oder " not in wert, name
            # ein konkreter Wert ist fuer das Feld wirklich gueltig
            assert wert is None or spec.typ.validator(spec.typ.normalisiere(wert)), name
        # der Festweg kennt keine Grenzfaelle
        assert "oder" not in eintrag["fest"].replace("Nachfrage", ""), name
        vertrag = eintrag["vertrag"]
        assert vertrag is None or (
            isinstance(vertrag, str) and spec.typ.validator(spec.typ.normalisiere(vertrag))), name


SKALA_PFLICHT = ["4", "4.", "4 von 5", "vier", "eher gut", "Ja"]
DAUER_PFLICHT = [
    "40 Stunden", "40", "ca. 2 Std.", "eine halbe Stunde", "anderthalb Stunden",
    "1 Stunde und zehn Minuten", "nicht 3 Stunden", "unter 1 Stunde", "2 Tage",
    "2–3 Stunden", "so 45 Minuten"]
PFLICHT = {
    "request_goal": ["zeit_sparen", "Zeit sparen", "Fehler senken", "weniger Fehler",
                     "Zeit sparen und Fehler senken"],
    "scope_focus": ["ganzer Prozess", "den ganzen Prozess", "ein einzelner Schritt",
                    "einzelner Schritt", "Beides"],
    "process_owner_role": [
        "Geschäftsführung", "geschaeftsfuehrung", "Vertrieb & Innendienst", "Lager+Versand",
        "die Geschäftsführung", "Geschäftsführung (R-01)", "R-01 = Geschäftsführung",
        "R-02 = Geschäftsführung", "Ja, stimmt"],
    "process_id": ["Auftrag-Abwicklung", "Einkauf & Beschaffung", "Einkauf und Beschaffung",
                   "KP-01 = Auftrag-Abwicklung", "Auftrag"],
    "input_format": ["E-Mail", "Email", "per Mail", "PDF", "als PDF", "PDF per Mail"],
    "frequency_per_year": [
        "2 pro Monat", "2x die Woche", "2/Woche", "300", "wöchentlich", "einmal pro Woche",
        "jeden 2. Monat", "täglich", "2-3x pro Woche", "2x", "pro Monat 30",
        "so 30 im Monat", "20 Leads pro Woche", "etwa 20 Anfragen pro Monat",
        "jede Woche 2", "2 mal in der Woche", "2 mal", "zweimal", "2-mal"],
    "executions_per_run": ["1", "ca. 3 Fälle", "5 Leads", "immer 1", "fünf", "5 bis 10",
                           "5 pro Woche"],
    "total_duration_minutes": DAUER_PFLICHT + [
        "30 Minuten pro Lead", "mehr als 2 Stunden", "meistens 20 Minuten",
        "2 Stunden bei uns", "ca. 40"],
    "focus_step": [
        "KP-01.TP-1", "Anfrage erfassen", "Lieferanten-Bewertung", "anfrage erfassen.",
        "Anfrage erfassen?", "KP-01.TP-9", "erfassen", "der zweite Schritt", "die Prüfung",
        "KP-01.TP-1 = Anfrage erfassen", "KP-01.TP-1 = Angebot prüfen"],
    "focus_step_duration_minutes": DAUER_PFLICHT + ["3 Stunden", "30 Minuten pro Fall"],
    "focus_step_duration_source": ["gemessen", "geschätzt", "aus dem System", "aus System",
                                   "nur geschätzt"],
    "focus_step_duration_confidence_pct": [
        "70", "ca. 70 %", "70 Prozent", "70,5 %", "zu 70 Prozent sicher", "ziemlich sicher"],
    "focus_step_media_break": [
        "Ja", "nein.", "Ja?", "Ja, eigentlich nicht", "Ja, aber selten", "Ja Systeme wechseln",
        "nö", "Zwischen Systemen wechseln", "Ja, müssen wir", "Ja, keine Ahnung",
        "teilweise", "eher ja"],
    "documentation_status": SKALA_PFLICHT + ["gar nicht"],
    "standardization_level": SKALA_PFLICHT + ["immer gleich"],
    "data_availability_score": SKALA_PFLICHT,
    "stability_score": SKALA_PFLICHT,
    "pii_involved": [
        "Ja", "nein.", "Ja?", "Ja, eigentlich nicht", "nö", "Ja, Namen und Mailadressen",
        "Nein, nur Namen und Mailadressen", "Zwischen Systemen wechseln",
        "Ja, keine Ahnung"],
}


def test_katalog_deckt_alle_festen_pflichtfelder():
    vorhanden = {(e["feld"], e["antwort"]) for e in KATALOG["eintraege"]}
    fehlend = [(feld, antwort) for feld, antworten in PFLICHT.items()
               for antwort in antworten if (feld, antwort) not in vorhanden]
    assert fehlend == []


@pytest.mark.parametrize(
    "eintrag", KATALOG["eintraege"],
    ids=[f"{e['feld']}-{e['antwort']}" for e in KATALOG["eintraege"]])
def test_katalog_kein_weg_liefert_falschen_wert(eintrag):
    spec = baue_paket(KATALOG["kontext"], eintrag.get("variante")).field(eintrag["feld"])
    assert spec is not None, eintrag["feld"]
    assert weg_direkt(spec, eintrag["antwort"]) == eintrag["fest"]
    erlaubt = {eintrag["fest"]}
    if eintrag["vertrag"] is not None:
        erlaubt.add(eintrag["vertrag"])
    assert weg_woertlich(spec, eintrag["antwort"]) in erlaubt


def test_katalog_nackte_zahlen_nur_ueber_den_normalisierer():
    # Ruling 8: D1 "300" = pro Jahr, E1/E2 "40" = Minuten; die Kurzform nimmt keine nackte Zahl
    nackt = [e for e in KATALOG["eintraege"] if e["vertrag"] is not None]
    assert {(e["feld"], e["antwort"], e["vertrag"]) for e in nackt} == {
        ("frequency_per_year", "300", "300"), ("total_duration_minutes", "40", "40"),
        ("focus_step_duration_minutes", "40", "40")}
    for e in nackt:
        spec = PAKET.field(e["feld"])
        assert weg_woertlich(spec, e["antwort"]) == e["vertrag"]


def test_katalog_nackte_zahl_gilt_fest_und_zusatzformen_bleiben_nachfrage():
    # Spec 2 „Fester Schutz“: die Kurzform nimmt die nackte Zahl an (Vertragsbedeutung);
    # „2x“, „2 mal“, „zweimal“, „2-mal“ (D1) und „ca. 40“ (E1) bleiben Nachfrage, auch mit KI.
    nackt = [e for e in KATALOG["eintraege"] if e["vertrag"] is not None]
    for e in nackt:
        assert (e["fest"], e["ki"]) == (e["vertrag"], e["vertrag"])
        assert weg_direkt(PAKET.field(e["feld"]), e["antwort"]) == e["vertrag"]
    zusatz = {(e["feld"], e["antwort"]): e for e in KATALOG["eintraege"]}
    for feld, antwort in [("frequency_per_year", a) for a in ("2x", "2 mal", "zweimal", "2-mal")] \
            + [("total_duration_minutes", "ca. 40")]:
        assert (zusatz[(feld, antwort)]["fest"], zusatz[(feld, antwort)]["ki"]) \
            == ("Nachfrage", "Nachfrage"), antwort


@pytest.mark.parametrize(
    "eintrag", KATALOG["eintraege"],
    ids=[f"{e['feld']}-{e['antwort']}" for e in KATALOG["eintraege"]])
def test_katalog_normalisierer_umfasst_kurzform(eintrag):
    # Invariante (Spec 3.4): Hat die Kurzform k einen gueltigen Wert, liefert der
    # Normalisierer auf dem Rohtext genau diesen; ist normalisiere(k) ungueltig,
    # bleibt auch der Rohtext ungueltig.
    spec = PAKET.field(eintrag["feld"])
    kurz = spec.typ.kurzform(eintrag["antwort"]) if spec.typ.kurzform else None
    if kurz is None:
        return
    aus_kurz = spec.typ.normalisiere(kurz)
    aus_roh = spec.typ.normalisiere(eintrag["antwort"])
    if spec.typ.validator(aus_kurz):
        assert aus_roh == aus_kurz
    else:
        assert not spec.typ.validator(aus_roh)
