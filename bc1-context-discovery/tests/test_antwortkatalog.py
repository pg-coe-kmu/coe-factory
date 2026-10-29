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


def test_katalog_kontext_nennt_kernprozesse_und_teilprozesse():
    assert "KP-01 = Auftrag-Abwicklung" in PAKET.field("process_id").question
    assert "KP-02.TP-1 = Lieferanten-Bewertung" in PAKET.field("focus_step").question


@pytest.mark.parametrize(
    "eintrag", KATALOG["eintraege"],
    ids=[f"{e['feld']}-{e['antwort']}" for e in KATALOG["eintraege"]])
def test_katalog_beide_wege(eintrag):
    spec = PAKET.field(eintrag["feld"])
    assert spec is not None, eintrag["feld"]
    assert weg_direkt(spec, eintrag["antwort"]) == eintrag["fest"]
    erlaubt = {eintrag["fest"]}
    if eintrag["vertrag"] is not None:
        erlaubt.add(eintrag["vertrag"])
    assert weg_woertlich(spec, eintrag["antwort"]) in erlaubt
