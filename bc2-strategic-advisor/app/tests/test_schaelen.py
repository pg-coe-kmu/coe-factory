"""
BC2 · Das Schälen der Modellantwort (#317).

Im ersten echten Betrieb (10.10.2026) scheiterten drei von vier Ausarbeitungen
an „kein JSON-Objekt“, obwohl die Antworten vollständig waren. Zwei Ursachen
ließen sich am alten ``schaele_json`` nachstellen; beide stehen hier als Fall.
"""

from __future__ import annotations

import json
import logging

from erkennung.modellruf import Doppelgaenger, lies_json, schaele_json

_OBJEKT = {
    "kontext": {"prozess_kurzbeschreibung": "Die Klausur wird vorbereitet."},
    "potenziale": [{"id": "P-1", "loesungsansatz": "Ein Workflow."}],
    "gesamtempfehlung_begruendung": "Erst P-1.",
}


def _umzaeunt(objekt: dict) -> str:
    return "```json\n" + json.dumps(objekt, ensure_ascii=False, indent=2) + "\n```"


def test_ein_codeblock_im_inhalt_bricht_das_schaelen_nicht():
    # Der wahrscheinliche Fall aus fd2e…: `loesungsansatz` ist Markdown, und ein
    # technischer Ansatz bringt einen Codeblock mit. Das alte Schälen schnitt am
    # inneren Zaun ab.
    objekt = json.loads(json.dumps(_OBJEKT))
    objekt["potenziale"][0]["loesungsansatz"] = (
        "Ein n8n-Workflow:\n```json\n{\"nodes\": []}\n```\nDanach die Freigabe."
    )
    assert schaele_json(_umzaeunt(objekt)) == objekt


def test_einleitung_und_nachsatz_stoeren_nicht():
    roh = "Hier die Ausarbeitung:\n\n" + _umzaeunt(_OBJEKT) + "\n\nViel Erfolg!"
    assert schaele_json(roh) == _OBJEKT


def test_nackte_antwort_wird_gelesen():
    assert schaele_json(json.dumps(_OBJEKT)) == _OBJEKT


def test_eine_klammer_in_der_einleitung_faellt_auf_den_zaun_zurueck():
    roh = "Ohne {Platzhalter} geschrieben:\n" + _umzaeunt(_OBJEKT)
    assert schaele_json(roh) == _OBJEKT


def test_ein_ungeschuetztes_anfuehrungszeichen_wird_benannt():
    roh = _umzaeunt(_OBJEKT).replace("Ein Workflow.", 'Ein "Workflow".')
    ergebnis, lesefehler = lies_json(roh)
    assert ergebnis is None
    # Stelle und Umfeld, damit Mensch und Modell sehen, was zu ändern ist.
    assert "Zeile" in lesefehler and "Spalte" in lesefehler
    assert "Workflow" in lesefehler
    assert '\\"' in lesefehler  # der Hinweis, wie es richtig wäre


def test_ohne_klammer_sagt_der_lesefehler_das():
    ergebnis, lesefehler = lies_json("Ich kann das nicht ausarbeiten.")
    assert ergebnis is None
    assert "{" in lesefehler


def test_ein_gelesenes_objekt_hat_keinen_lesefehler():
    assert lies_json(_umzaeunt(_OBJEKT)) == (_OBJEKT, None)


def test_die_antwort_traegt_den_lesefehler():
    antwort = Doppelgaenger(antworten=['{"kontext": "kaputt}']).frage("?")
    assert antwort.ergebnis is None
    assert antwort.lesefehler and "Zeile" in antwort.lesefehler


def test_die_rohantwort_geht_vollstaendig_ins_protokoll(caplog):
    from erkennung.modellruf import protokolliere_unlesbar

    roh = "x" * 30_000 + "{kaputt"
    with caplog.at_level(logging.WARNING, logger="bc2.modell"):
        protokolliere_unlesbar("claude-sonnet-4-6", roh, "Zeile 1")
    assert roh in caplog.text
