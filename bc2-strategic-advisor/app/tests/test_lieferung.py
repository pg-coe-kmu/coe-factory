"""
Tests: die Lieferung aus Schema ``bc2`` ziehen (#306, seit #378 aus der Ergebnisakte).

Die Strecke ist die des Betriebs, bis auf die Datenbank: ein echter Lauf
(Erkennung → Bewertung → Rechnung → Ausarbeitung, mit Doppelgänger-Modell)
wird abgelegt und freigegeben, die Freigabe friert die Ergebnisakte ein,
``lieferung.lieferungen`` gibt die ``bc3``-Dateien der lieferbaren Akten aus,
und ``tools/lieferung_ziehen.py`` schreibt sie in einen Lieferordner ab.
Zwischen beiden liegt — wie über ``ssh`` — eine JSON-Rundreise.

Abnahme aus #306: schemagültig, ein zweiter Zug ändert nichts, ein
manipulierter Ordner bricht ab. Aus #378: abgeschrieben wird Byte für Byte, was
die Akte trägt, und eine verdorbene Datei wird nicht geschrieben.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ablage import AblegendeLaufquelle, SpeicherErgebnisbuch
from gate1 import Gate1Entscheidung, NichtFreigegeben, SpeicherGate1Buch, jetzt
from lieferung import lieferungen, mandantenkuerzel

from conftest import akte_zur_freigabe
from test_ausarbeitung import (
    NOROAI,
    _JeKonzept,
    _erkannt_zwei,
    _gut_zwei,
    _laufquelle,
    _validator,
    _zwei_kernprozesse,
)

WERKZEUG = Path(__file__).resolve().parents[2] / "tools" / "lieferung_ziehen.py"


def _werkzeug():
    spec = importlib.util.spec_from_file_location("lieferung_ziehen", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul  # sonst findet @dataclass sein Modul nicht
    spec.loader.exec_module(modul)
    return modul


ziehen = _werkzeug()


def _echter_lauf(*, freigeben: str | None = "approved", heraus: int = 0, kommentar: str = "",
                 sperrgrund: str | None = None):
    """Ein ausgearbeiteter Lauf über zwei Kernprozesse, abgelegt und entschieden."""
    innen = _laufquelle(_JeKonzept(_erkannt_zwei(), _gut_zwei()), _zwei_kernprozesse(),
                        ("KP-06.TP-1", "KP-06.TP-2", "KP-07.TP-1"))
    ergebnisse = SpeicherErgebnisbuch()
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    quelle = AblegendeLaufquelle(innen, ergebnisse)
    quelle.rechnen("PKT-301", neu=False)
    if sperrgrund:
        ergebnisse.zeilen["PKT-301"][-1].sperrgrund = sperrgrund
    ansicht = quelle.ansicht("PKT-301")
    if freigeben:
        ids = ansicht.potenzial_ids()
        e = Gate1Entscheidung(
            paket_id="PKT-301", company_id=NOROAI, status=freigeben,
            fassung=ansicht.kopf.fassung,
            approved_potenzial_ids=tuple(ids[heraus:]) if freigeben == "approved" else (),
            nicht_freigegeben=tuple(
                NichtFreigegeben(pid, "Kommt in dieser Runde nicht mit.") for pid in ids[:heraus]
            ),
            kommentar=kommentar or ("Abgelehnt im Test." if freigeben == "rejected" else ""),
            entscheider="Sergio",
            entschieden_am=jetzt(),
        )
        gate1.merken(e, akte=akte_zur_freigabe(gate1, ansicht, e)
                     if freigeben == "approved" else None)
    return ergebnisse, gate1


def _ueber_ssh(gate1) -> dict:
    """Was ``python -m lieferung`` ausgibt, nach der Rundreise durch JSON."""
    return json.loads(json.dumps(
        {"lieferungen": [l.als_json() for l in lieferungen(gate1)]}, ensure_ascii=False,
    ))


# ---------------------------------------------------------------------------
# Welche Läufe geliefert sind
# ---------------------------------------------------------------------------


def test_ein_freigegebener_echter_lauf_ist_geliefert():
    _, gate1 = _echter_lauf()
    (l,) = lieferungen(gate1)
    assert l.ordner == "noroai-PKT-301-f1"
    assert sorted(l.dateien) == [
        "NACHRICHT_AN_BC3.md", "konzept_KP-06.json", "konzept_KP-07.json",
        "prozesspriorisierung.json",
    ]
    prio = json.loads(l.dateien["prozesspriorisierung.json"])
    assert prio["gate1"]["status"] == "approved"
    # Das Modellurteil ist ein Hinweis (#305): es reist mit, sperrt aber nichts.
    assert "#299" in l.dateien["NACHRICHT_AN_BC3.md"].decode("utf-8")


def test_geliefert_wird_genau_was_die_akte_traegt():
    """Eine Stelle, an der die Lieferdatei entsteht (Nachtrag 13.11., Punkt 2)."""
    _, gate1 = _echter_lauf()
    (l,) = lieferungen(gate1)
    akte = gate1.akte("PKT-301")
    assert l.dateien == {d.name: d.inhalt for d in akte.fuer("bc3")}


@pytest.mark.parametrize("status", [None, "rejected"])
def test_offen_oder_abgelehnt_ist_nichts_geliefert(status):
    _, gate1 = _echter_lauf(freigeben=status)
    assert lieferungen(gate1) == []


def test_ein_freigegebener_lauf_mit_sperrgrund_hat_eine_akte_aber_ist_nicht_geliefert():
    _, gate1 = _echter_lauf(sperrgrund="Nicht nachrechenbar.")
    assert gate1.akte("PKT-301") is not None
    assert lieferungen(gate1) == []


def test_das_mandantenkuerzel():
    assert mandantenkuerzel("NoroAI Consulting GmbH", "7c2d5ee9-x") == "noroai"
    assert mandantenkuerzel(None, "7C2D5EE9-2a9a") == "7c2d5ee9"
    assert mandantenkuerzel("  ", "7c2d5ee9-2a9a") == "7c2d5ee9"


# ---------------------------------------------------------------------------
# In den Lieferordner abschreiben
# ---------------------------------------------------------------------------


def test_der_gezogene_ordner_ist_schemagueltig(tmp_path):
    _, gate1 = _echter_lauf(heraus=1)
    abgleich, _ = ziehen.ziehe(_ueber_ssh(gate1), tmp_path)

    assert abgleich.neu == ["noroai-PKT-301-f1"] and not abgleich.abweichend
    ordner = tmp_path / "noroai-PKT-301-f1"
    assert sorted(d.name for d in ordner.iterdir()) == [
        "NACHRICHT_AN_BC3.md", "konzept_KP-06.json", "konzept_KP-07.json",
        "prozesspriorisierung.json",
    ]
    prio = json.loads((ordner / "prozesspriorisierung.json").read_text(encoding="utf-8"))
    _validator("priorisierung.schema.json").validate(prio)
    assert prio["gate1"]["nicht_freigegeben"][0]["begruendung"]
    pruefer = _validator("konzept.schema.json")
    for datei in ordner.glob("konzept_*.json"):
        pruefer.validate(json.loads(datei.read_text(encoding="utf-8")))
    # Keine Präsentation: sie geht an den Mandanten (#305, Punkt 4).
    assert not list(ordner.glob("*.pptx"))


def test_abgeschrieben_wird_byte_fuer_byte(tmp_path):
    _, gate1 = _echter_lauf()
    ziehen.ziehe(_ueber_ssh(gate1), tmp_path)
    for d in gate1.akte("PKT-301").fuer("bc3"):
        assert (tmp_path / "noroai-PKT-301-f1" / d.name).read_bytes() == d.inhalt


def test_der_kommentar_zur_freigabe_steht_im_gezogenen_gate1_block(tmp_path):
    """Der Kommentar reist im ``gate1``-Block mit (#377, entschieden in #376)."""
    _, gate1 = _echter_lauf(kommentar="Mit dem Fachbereich abgestimmt.")
    ziehen.ziehe(_ueber_ssh(gate1), tmp_path)

    prio = json.loads(
        (tmp_path / "noroai-PKT-301-f1" / "prozesspriorisierung.json").read_text(encoding="utf-8")
    )
    _validator("priorisierung.schema.json").validate(prio)
    assert prio["gate1"]["kommentar"] == "Mit dem Fachbereich abgestimmt."


def test_ein_zweiter_zug_aendert_nichts(tmp_path):
    roh = _ueber_ssh(_echter_lauf()[1])
    ziehen.ziehe(roh, tmp_path)
    vorher = {d: d.read_bytes() for d in (tmp_path / "noroai-PKT-301-f1").iterdir()}

    abgleich, _ = ziehen.ziehe(roh, tmp_path)

    assert abgleich.neu == [] and abgleich.gleich == ["noroai-PKT-301-f1"]
    assert {d: d.read_bytes() for d in (tmp_path / "noroai-PKT-301-f1").iterdir()} == vorher


def test_ein_veraenderter_ordner_bricht_ab_und_nichts_wird_geschrieben(tmp_path, capsys):
    roh = _ueber_ssh(_echter_lauf()[1])
    ziehen.ziehe(roh, tmp_path)
    prio = tmp_path / "noroai-PKT-301-f1" / "prozesspriorisierung.json"
    prio.write_text(prio.read_text(encoding="utf-8").replace('"fassung": 1', '"fassung": 9'),
                    encoding="utf-8")
    # Dazu ein zweiter, neuer Lauf — er darf beim Abbruch nicht halb entstehen.
    zweiter = json.loads(json.dumps(roh["lieferungen"][0]))
    zweiter["ordner"] = "noroai-PKT-302-f1"
    roh["lieferungen"].append(zweiter)
    datei = tmp_path / "roh.json"
    datei.write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")

    code = ziehen.main(["--aus", str(datei), "--ziel", str(tmp_path)])

    assert code == 1
    assert "ABWEICHUNG  noroai-PKT-301-f1" in capsys.readouterr().out
    assert not (tmp_path / "noroai-PKT-302-f1").exists()


def test_eine_verdorbene_datei_wird_nicht_geschrieben(tmp_path, capsys):
    """Die Prüfsumme reist mit; stimmt sie nicht, bricht der ganze Zug ab."""
    roh = _ueber_ssh(_echter_lauf()[1])
    d = roh["lieferungen"][0]["dateien"][0]
    d["inhalt_b64"] = base64.b64encode(base64.b64decode(d["inhalt_b64"]) + b" ").decode()
    datei = tmp_path / "roh.json"
    datei.write_text(json.dumps(roh), encoding="utf-8")

    assert ziehen.main(["--aus", str(datei), "--ziel", str(tmp_path)]) == 1
    assert "Pruefsumme" in capsys.readouterr().err
    assert not (tmp_path / "noroai-PKT-301-f1").exists()


def test_pruefen_schreibt_nichts(tmp_path):
    roh = _ueber_ssh(_echter_lauf()[1])
    abgleich, _ = ziehen.ziehe(roh, tmp_path, pruefen=True)
    assert abgleich.neu == ["noroai-PKT-301-f1"]
    assert not any(tmp_path.iterdir())


def test_das_werkzeug_setzt_nichts_mehr_zusammen():
    """Ordnen und Nachricht sind in den Dienst gezogen (#378, Punkt 3)."""
    text = WERKZEUG.read_text(encoding="utf-8")
    assert "def ordne" not in text and "def nachricht" not in text
    assert "schema.json" not in text
