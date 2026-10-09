"""BC1-Profilzeile -> ``Bc1Profil``: gelesen wie der Vertrag sie liefert (#255).

Die Zeile ist die echte aus ``contracts/examples/beispiel_bc1_prozessprofil.json``
(BC1, KP-06.TP-2, Version 2). Gemessen am 09.10.2026 als ``bc2_role`` an der
laufenden Datenbank: die Interviewfelder liegen unter ``profil.felder.<name>``
(Invariante I6), auf der obersten Ebene steht keines davon. Die erste Fassung von
``_bc1_aus_zeile`` las sie oben und bekam darum in allen drei Profilen nichts —
weder die vier Reifeskalen noch die Testdaten-Kennzeichnung (I7).
"""
from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

from erkennung.bestand import _SQL_BC1, _bc1_aus_zeile

BEISPIEL = (
    Path(__file__).resolve().parents[3] / "contracts" / "examples" / "beispiel_bc1_prozessprofil.json"
)


def _zeile() -> dict:
    return json.loads(BEISPIEL.read_text(encoding="utf-8"))


def test_reifeskalen_kommen_aus_profil_felder():
    p = _bc1_aus_zeile(_zeile())
    assert p.documentation_status == 2
    assert p.reifeskalen is not None
    assert all(isinstance(s, int) and 1 <= s <= 5 for s in p.reifeskalen)


def test_testdaten_kennzeichnung_kommt_aus_open_remarks():
    p = _bc1_aus_zeile(_zeile())
    assert p.kennzeichnung is not None
    assert p.kennzeichnung.startswith("Testdaten ")


def test_ohne_testdaten_praefix_keine_kennzeichnung():
    z = _zeile()
    z["profil"]["felder"]["open_remarks"]["wert"] = "Erhoben im Interview am 01.10."
    assert _bc1_aus_zeile(z).kennzeichnung is None


def test_nur_gueltige_felder_tragen_einen_wert():
    z = _zeile()
    z["profil"]["felder"]["stability_score"]["status"] = "ungeloest"
    p = _bc1_aus_zeile(z)
    assert p.stability_score is None
    assert p.reifeskalen is None  # nur vollständig oder gar nicht


def test_step_frequency_kommt_aus_der_spalte():
    z = _zeile()
    z["step_frequency_per_year"] = Decimal("12")
    assert _bc1_aus_zeile(z).step_frequency_per_year == Decimal("12")
    # Ein gültiger JSON-Wert ohne Spalte zählt nicht: in die Spalte fließt nur,
    # was BC1 als gültig übernommen hat (I6), und die Spalte ist der Vertrag (I8).
    z2 = copy.deepcopy(_zeile())
    z2["profil"]["felder"]["step_frequency_per_year"] = {"wert": "12", "status": "gueltig"}
    assert _bc1_aus_zeile(z2).step_frequency_per_year is None


def test_unlesbarer_wert_wird_none_statt_absturz():
    z = _zeile()
    z["profil"]["felder"]["documentation_status"]["wert"] = "zwei"
    assert _bc1_aus_zeile(z).documentation_status is None


def test_leseregel_liest_step_frequency_als_spalte():
    assert "p.step_frequency_per_year" in _SQL_BC1
