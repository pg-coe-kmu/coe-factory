"""
Tests: die Ergebnisakte (#378, entschieden in #376, ADR-007 · BC2 Nachtrag 13.11.2026).

Drei Fragen:

1. **Byte-gleich.** Die Dateien an BC3 entstehen seit #378 im Dienst statt im
   Werkzeug. Die Lieferung ``cc7f4d1b`` (f1) liegt schon im Repo; was der Dienst
   aus demselben Lauf einfriert, muss Byte für Byte dieselben Dateien ergeben —
   sonst bräche das nachträgliche Einfrieren beim Ausrollen ab (Punkt 6).
2. **Beides oder nichts.** Freigabe und Akte liegen zusammen oder gar nicht, im
   Doppelgänger wie in der Datenbank (die prüft ``test_vertrag_postgres.py``).
3. **Nachtragen.** Ein vor bc2.4 freigegebener Lauf wird einmal, mit Vermerk,
   nachträglich eingefroren.
"""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from datetime import datetime
from pathlib import Path

import pytest

import ergebnisakte
from ablage import AbgelegterLauf, AblegendeLaufquelle, Laufbeleg, SpeicherErgebnisbuch
from ergebnisakte import (
    AkteFehlt,
    AkteUngueltig,
    NachtragNichtMoeglich,
    akte_einfrieren,
    einfrieren,
    nachricht,
    nachtragen,
    ordne,
    stoff_aus_ablage,
)
from gate1 import Gate1Entscheidung, NichtFreigegeben, SpeicherGate1Buch, jetzt
from lieferung import lieferung_aus

from conftest import akte_zur_freigabe
from test_ausarbeitung import NOROAI, _JeKonzept, _erkannt_zwei, _gut_zwei, _laufquelle, _zwei_kernprozesse
from test_lieferung import ziehen

LIEFERUNGEN = Path(__file__).resolve().parents[3] / "contracts" / "bc2-to-bc3" / "lieferungen"
CC7F = LIEFERUNGEN / "noroai-cc7f4d1b-4c71-4cfa-92c3-46a395080e4b-f1"


# ---------------------------------------------------------------------------
# 1. Byte-gleich zur Lieferung cc7f4d1b (f1)
# ---------------------------------------------------------------------------


def _wie_jsonb(daten):
    """Die Schlüsselfolge, in der Postgres ``jsonb`` zurückgibt: kurz vor lang,
    dann nach Bytes. So kommt das Dokument aus ``bc2.lauf`` an."""
    if isinstance(daten, dict):
        return {k: _wie_jsonb(daten[k])
                for k in sorted(daten, key=lambda k: (len(k.encode()), k.encode()))}
    if isinstance(daten, list):
        return [_wie_jsonb(x) for x in daten]
    return daten


def _entscheidung_aus(block: dict, prio: dict) -> Gate1Entscheidung:
    return Gate1Entscheidung(
        paket_id=prio["paket_id"],
        company_id=prio["company_id"],
        status=block["status"],
        fassung=prio["fassung"],
        approved_potenzial_ids=tuple(block.get("approved_potenzial_ids", [])),
        nicht_freigegeben=tuple(
            NichtFreigegeben(n["potenzial_id"], n["begruendung"])
            for n in block.get("nicht_freigegeben", [])
        ),
        finale_reihenfolge_potenzial_ids=tuple(block.get("finale_reihenfolge_potenzial_ids", [])),
        finale_prozessreihenfolge_kp_ids=tuple(block.get("finale_prozessreihenfolge_kp_ids", [])),
        abweichungsbegruendung=block.get("abweichungsbegruendung", ""),
        entscheider=block.get("entscheider", ""),
        kommentar=block.get("kommentar", ""),
        entschieden_am=datetime.fromisoformat(block["entschieden_am"]),
    )


def _cc7f_wie_in_bc2() -> tuple[AbgelegterLauf, Gate1Entscheidung]:
    """Der Lauf, wie er in Schema ``bc2`` liegt — zurückgebaut aus dem Lieferordner.

    Dokument und Konzepte stehen dort wörtlich (nur der ``gate1``-Block kam beim
    Ziehen dazu), die Hinweise und der Klartextname des Kernprozesses in der
    Nachricht. Die Schlüssel kommen in ``jsonb``-Folge an, wie aus der Datenbank.
    """
    prio = json.loads((CC7F / "prozesspriorisierung.json").read_text(encoding="utf-8"))
    block = prio.pop("gate1")
    konzepte = [json.loads(d.read_text(encoding="utf-8")) for d in sorted(CC7F.glob("konzept_*.json"))]
    text = (CC7F / "NACHRICHT_AN_BC3.md").read_text(encoding="utf-8")
    hinweise = tuple(z[2:] for z in text.split("## Hinweise\n\n", 1)[1].splitlines() if z.startswith("- "))
    entscheidung = _entscheidung_aus(block, prio)
    assert entscheidung.als_vertrag() == block, "die Entscheidung muss denselben Block ergeben"
    lauf = AbgelegterLauf(
        beleg=Laufbeleg(
            priorisierung_id=prio["priorisierung_id"], company_id=prio["company_id"],
            paket_id=prio["paket_id"], uebergeben_am=datetime.fromisoformat(prio["uebergeben_am"]),
            fassung=prio["fassung"], zustand="abgeschlossen",
        ),
        dokument=_wie_jsonb(prio),
        konzepte=[_wie_jsonb(k) for k in konzepte],
        kp_namen={"KP-06": "Personal"},  # bc2.konzept.kp_name; die Nachricht nennt ihn
        hinweise=hinweise,
        gate1_status="approved",
    )
    return lauf, entscheidung


def test_die_dateien_an_bc3_sind_byte_gleich_zur_lieferung_cc7f4d1b():
    """Abnahme aus #378: der Dienst ergibt dieselben Bytes wie das bisherige Werkzeug."""
    lauf, entscheidung = _cc7f_wie_in_bc2()
    akte = einfrieren(stoff_aus_ablage(lauf), entscheidung, praesentation=b"PK\x03\x04")

    assert akte.ordner == CC7F.name
    assert sorted(d.name for d in akte.fuer("bc3")) == sorted(d.name for d in CC7F.iterdir())
    for d in akte.fuer("bc3"):
        assert d.inhalt == (CC7F / d.name).read_bytes(), d.name


def test_das_werkzeug_findet_cc7f4d1b_unveraendert(tmp_path):
    """Derselbe Weg wie beim Ausrollen: eingefroren, über ``python -m lieferung``
    ausgegeben, gegen den Lieferordner gehalten — und nichts weicht ab."""
    shutil.copytree(CC7F, tmp_path / CC7F.name)
    lauf, entscheidung = _cc7f_wie_in_bc2()
    akte = einfrieren(stoff_aus_ablage(lauf), entscheidung, praesentation=b"PK\x03\x04")
    roh = json.loads(json.dumps({"lieferungen": [lieferung_aus(akte).als_json()]}))

    abgleich, _ = ziehen.ziehe(roh, tmp_path)

    assert abgleich.gleich == [CC7F.name] and not abgleich.neu and not abgleich.abweichend


# ---------------------------------------------------------------------------
# Was in der Akte liegt
# ---------------------------------------------------------------------------


def _gerechnet(*, sperrgrund: str | None = None):
    innen = _laufquelle(_JeKonzept(_erkannt_zwei(), _gut_zwei()), _zwei_kernprozesse(),
                        ("KP-06.TP-1", "KP-06.TP-2", "KP-07.TP-1"))
    ergebnisse = SpeicherErgebnisbuch()
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    quelle = AblegendeLaufquelle(innen, ergebnisse)
    quelle.rechnen("PKT-301", neu=False)
    if sperrgrund:
        ergebnisse.zeilen["PKT-301"][-1].sperrgrund = sperrgrund
    return quelle, ergebnisse, gate1, quelle.ansicht("PKT-301")


def _freigabe(ansicht, *, status: str = "approved", heraus: int = 0) -> Gate1Entscheidung:
    ids = ansicht.potenzial_ids()
    return Gate1Entscheidung(
        paket_id="PKT-301", company_id=NOROAI, status=status, fassung=ansicht.kopf.fassung,
        approved_potenzial_ids=tuple(ids[heraus:]) if status == "approved" else (),
        nicht_freigegeben=tuple(NichtFreigegeben(p, "Kommt in dieser Runde nicht mit.")
                                for p in ids[:heraus]),
        kommentar="" if status == "approved" else "Abgelehnt im Test.",
        entscheider="Sergio", entschieden_am=jetzt(),
    )


def test_ein_lieferbarer_lauf_hat_vier_dateien_an_zwei_empfaenger():
    _, _, gate1, ansicht = _gerechnet()
    akte = akte_zur_freigabe(gate1, ansicht, _freigabe(ansicht))

    assert {(d.name, d.empfaenger) for d in akte.dateien} == {
        ("prozesspriorisierung.json", "bc3"), ("konzept_KP-06.json", "bc3"),
        ("konzept_KP-07.json", "bc3"), ("NACHRICHT_AN_BC3.md", "bc3"),
        ("praesentation.pptx", "mandant"),
    }
    assert akte.lieferbar and akte.ordner == "noroai-PKT-301-f1"
    assert akte.praesentation[:2] == b"PK"
    for d in akte.dateien:
        assert d.pruefsumme == hashlib.sha256(d.inhalt).hexdigest()
    prio = json.loads(akte.datei("prozesspriorisierung.json").inhalt)
    assert prio["gate1"]["entscheider"] == "Sergio"


def test_der_gate1_block_steht_so_da_wie_aus_der_datenbank():
    """Die Oberfläche schickt die Kennungen in ihrer Folge, ``lesen`` gibt sie nach
    Rang zurück. Eingefroren wird die zweite Form, in UTC — sonst ergäbe das
    nachträgliche Einfrieren andere Bytes als das beim Freigeben."""
    from dataclasses import replace
    from datetime import timedelta, timezone

    _, _, gate1, ansicht = _gerechnet()
    ids = ansicht.potenzial_ids()
    e = replace(
        _freigabe(ansicht, heraus=1),
        approved_potenzial_ids=tuple(reversed(ids[1:])),
        finale_reihenfolge_potenzial_ids=tuple(reversed(ids)),
        abweichungsbegruendung="Umgekehrt im Test.",
        entschieden_am=datetime(2026, 11, 13, 12, 0, tzinfo=timezone(timedelta(hours=1))),
    )
    block = json.loads(akte_zur_freigabe(gate1, ansicht, e).datei("prozesspriorisierung.json").inhalt)["gate1"]

    rang = {p: i for i, p in enumerate(reversed(ids))}
    assert block["approved_potenzial_ids"] == sorted(ids[1:], key=rang.get)
    assert block["entschieden_am"] == "2026-11-13T11:00:00+00:00"
    assert block["finale_reihenfolge_potenzial_ids"] == list(reversed(ids))


def test_ein_lauf_mit_sperrgrund_hat_eine_akte_aber_keine_lieferung():
    """Nachtrag 13.11., Punkt 2: freigegeben, eingefroren, nicht geliefert."""
    _, _, gate1, ansicht = _gerechnet(sperrgrund="Nicht nachrechenbar (Testfall).")
    akte = akte_zur_freigabe(gate1, ansicht, _freigabe(ansicht))

    assert [(d.name, d.empfaenger) for d in akte.dateien] == [("praesentation.pptx", "mandant")]
    assert not akte.lieferbar and lieferung_aus(akte) is None


def test_die_akte_wird_aus_dem_abgelegten_dokument_gebaut_nicht_aus_der_ansicht():
    """Ausgeliefert wird das Dokument, nie eine Rekonstruktion (ADR-008 · BC2, 2.2):
    ``priorisierung_id`` und ``erzeugt_am`` kennt nur das abgelegte."""
    _, ergebnisse, gate1, ansicht = _gerechnet()
    akte = akte_zur_freigabe(gate1, ansicht, _freigabe(ansicht))
    prio = json.loads(akte.datei("prozesspriorisierung.json").inhalt)
    abgelegt = ergebnisse.letzter("PKT-301").dokument

    assert prio["priorisierung_id"] == abgelegt["priorisierung_id"]
    assert prio["erzeugt_am"] == abgelegt["erzeugt_am"]
    assert {k: v for k, v in prio.items() if k != "gate1"} == abgelegt


@pytest.mark.parametrize("kaputt", ["bc3_mit_sperrgrund", "ohne_praesentation", "zur_ablehnung"])
def test_die_pruefung_haelt_was_die_datenbank_haelt(kaputt):
    from dataclasses import replace

    _, _, gate1, ansicht = _gerechnet()
    e = _freigabe(ansicht)
    akte = akte_zur_freigabe(gate1, ansicht, e)
    if kaputt == "bc3_mit_sperrgrund":
        akte, wogegen = replace(akte, sperrgrund="Gesperrt."), e
    elif kaputt == "ohne_praesentation":
        akte, wogegen = replace(akte, dateien=akte.fuer("bc3")), e
    else:
        akte, wogegen = akte, _freigabe(ansicht, status="rejected")
    with pytest.raises(AkteUngueltig):
        ergebnisakte.pruefe(akte, wogegen)


def test_ohne_vertragsschemas_entsteht_keine_akte(monkeypatch, tmp_path):
    """Im Image fehlten sie anfangs (Bau-Kontext ``app/``): dann scheitert das Einfrieren laut."""
    monkeypatch.setenv("BC2_VERTRAG", str(tmp_path))
    _, _, gate1, ansicht = _gerechnet()
    with pytest.raises(FileNotFoundError, match="BC2_VERTRAG"):
        akte_zur_freigabe(gate1, ansicht, _freigabe(ansicht))


# ---------------------------------------------------------------------------
# 2. Beides oder nichts — im Doppelgänger
# ---------------------------------------------------------------------------


def test_eine_freigabe_ohne_akte_gilt_nicht():
    _, _, gate1, ansicht = _gerechnet()
    with pytest.raises(AkteFehlt):
        gate1.merken(_freigabe(ansicht))
    assert gate1.lesen("PKT-301") is None and gate1.akte("PKT-301") is None


def test_scheitert_die_akte_liegt_auch_die_freigabe_nicht():
    _, ergebnisse, gate1, ansicht = _gerechnet()
    e = _freigabe(ansicht)
    akte = akte_zur_freigabe(gate1, ansicht, e)
    gate1.akten_antworten = False
    with pytest.raises(RuntimeError):
        gate1.merken(e, akte=akte)
    assert gate1.lesen("PKT-301") is None
    assert ergebnisse.letzter("PKT-301").gate1_status == "pending"

    gate1.akten_antworten = True
    gate1.merken(e, akte=akte)
    assert gate1.lesen("PKT-301").status == "approved"
    assert gate1.akte("PKT-301").eingefroren_am is not None


def test_eine_ablehnung_hat_keine_akte():
    _, _, gate1, ansicht = _gerechnet()
    gate1.merken(_freigabe(ansicht, status="rejected"))
    assert gate1.akte("PKT-301") is None


def test_ein_gesperrter_link_liefert_nichts():
    _, _, gate1, ansicht = _gerechnet()
    e = _freigabe(ansicht)
    gate1.merken(e, akte=akte_zur_freigabe(gate1, ansicht, e))
    token = gate1.akte("PKT-301").link_token

    assert gate1.praesentation_zum_token(token)[:2] == b"PK"
    assert gate1.sperren(token) is True
    assert gate1.praesentation_zum_token(token) is None
    assert gate1.sperren(token) is False
    # Die Bytes bleiben in der Akte; nur der Link gilt nicht mehr.
    assert gate1.akte("PKT-301").praesentation[:2] == b"PK"
    assert gate1.akte("PKT-301").als_uebersicht()["link"] is None


def test_das_token_ist_zufaellig_und_lang_genug():
    a, b = ergebnisakte.neues_token(), ergebnisakte.neues_token()
    assert a != b and len(a) >= 32 and ergebnisakte.TOKEN_FORM.fullmatch(a)


# ---------------------------------------------------------------------------
# 3. Nachträglich einfrieren (#378, Punkt 6)
# ---------------------------------------------------------------------------


def _vor_bc2_4_freigegeben():
    """Ein Lauf, freigegeben, als es die Akte noch nicht gab — am Doppelgänger
    vorbei gesetzt, wie ``cc7f4d1b`` (f1) in der Datenbank liegt."""
    quelle, ergebnisse, gate1, ansicht = _gerechnet()
    e = _freigabe(ansicht, heraus=1)
    gate1.abgelegt[("PKT-301", 1)] = e
    ergebnisse.abschliessen("PKT-301", 1, "approved")
    return quelle, ergebnisse, gate1, ansicht, e


def test_nachtragen_friert_mit_vermerk_ein():
    _, ergebnisse, gate1, ansicht, e = _vor_bc2_4_freigegeben()
    assert gate1.akte("PKT-301") is None

    akte = nachtragen(ergebnisse, gate1, "PKT-301", vermerk="Nachgetragen beim Ausrollen von #378.")

    assert gate1.akte("PKT-301") is not None
    assert gate1.akte("PKT-301").vermerk == "Nachgetragen beim Ausrollen von #378."
    # Dieselben Dateien an BC3, die die Freigabe damals geschrieben hätte.
    frisch = akte_zur_freigabe(gate1, ansicht, e)
    assert {d.name: d.inhalt for d in akte.fuer("bc3")} == {
        d.name: d.inhalt for d in frisch.fuer("bc3")
    }


def test_nachtragen_trocken_schreibt_nichts():
    _, ergebnisse, gate1, _, _ = _vor_bc2_4_freigegeben()
    akte = nachtragen(ergebnisse, gate1, "PKT-301", vermerk="Nur ansehen.", trocken=True)
    assert akte.fuer("bc3") and gate1.akte("PKT-301") is None


def test_nachtragen_gibt_es_nur_einmal_und_nur_fuer_eine_freigabe():
    _, ergebnisse, gate1, _, _ = _vor_bc2_4_freigegeben()
    nachtragen(ergebnisse, gate1, "PKT-301", vermerk="Erstes Mal.")
    with pytest.raises(NachtragNichtMoeglich, match="schon eine Ergebnisakte"):
        nachtragen(ergebnisse, gate1, "PKT-301", vermerk="Zweites Mal.")

    _, ergebnisse, gate1, _ = _gerechnet()
    with pytest.raises(NachtragNichtMoeglich, match="nicht freigegeben"):
        nachtragen(ergebnisse, gate1, "PKT-301", vermerk="Noch offen.")
    with pytest.raises(NachtragNichtMoeglich, match="kein gerechneter Lauf"):
        nachtragen(ergebnisse, gate1, "PKT-999", vermerk="Gibt es nicht.")


def test_nachtragen_braucht_einen_vermerk():
    _, ergebnisse, gate1, _, _ = _vor_bc2_4_freigegeben()
    with pytest.raises(NachtragNichtMoeglich, match="Vermerk"):
        nachtragen(ergebnisse, gate1, "PKT-301", vermerk="  ")


# ---------------------------------------------------------------------------
# Ordnen und Nachricht (aus tools/lieferung_ziehen.py umgezogen)
# ---------------------------------------------------------------------------


def test_die_schluessel_stehen_in_der_reihenfolge_des_schemas():
    """Postgres ``jsonb`` vergisst die Reihenfolge — die Datei darf es nicht zeigen."""
    _, ergebnisse, gate1, ansicht = _gerechnet()
    zeile = ergebnisse.zeilen["PKT-301"][-1]
    zeile.dokument = _wie_jsonb(zeile.dokument)
    zeile.konzepte = [_wie_jsonb(k) for k in zeile.konzepte]
    akte = akte_zur_freigabe(gate1, ansicht, _freigabe(ansicht))

    text = akte.datei("prozesspriorisierung.json").inhalt.decode("utf-8")
    schluessel = list(json.loads(text))
    assert schluessel[:3] == ["priorisierung_id", "schema_version", "company_id"]
    assert schluessel[-1] == "gate1"
    assert text.endswith("}\n") and "\\u00" not in text
    konzept = list(json.loads(akte.datei("konzept_KP-06.json").inhalt))
    assert konzept[:2] == ["konzept_id", "ersetzt_konzept_id"]


def test_die_nachricht_traegt_freigabe_reihenfolge_und_hinweise():
    _, _, gate1, ansicht = _gerechnet()
    e = _freigabe(ansicht, heraus=1)
    akte = akte_zur_freigabe(gate1, ansicht, e)
    text = akte.datei("NACHRICHT_AN_BC3.md").inhalt.decode("utf-8")

    assert text.startswith("# Lieferung an BC3 — noroai-PKT-301-f1\n")
    assert "durch Sergio" in text
    assert "nicht freigegeben: Kommt in dieser Runde nicht mit." in text
    assert "## Hinweise" in text and "#299" in text
    # Wiederholbar heißt auch: kein Zeitpunkt des Einfrierens.
    zweite = akte_zur_freigabe(gate1, ansicht, e)
    assert zweite.datei("NACHRICHT_AN_BC3.md").inhalt.decode("utf-8") == text


def test_ordne_folgt_ref_und_anyof():
    wurzel = {
        "$defs": {"spanne": {"type": "object", "properties": {"min": {}, "max": {}}}},
        "properties": {
            "a": {"$ref": "#/$defs/spanne"},
            "b": {"anyOf": [{"type": "null"}, {"$ref": "#/$defs/spanne"}]},
            "c": {"type": "array", "items": {"$ref": "#/$defs/spanne"}},
        },
    }
    daten = {"z": 1, "c": [{"max": 2, "min": 1}], "b": {"max": 2, "min": 1}, "a": {"max": 2, "min": 1}}
    geordnet = ordne(daten, wurzel, wurzel)
    assert list(geordnet) == ["a", "b", "c", "z"]
    assert list(geordnet["a"]) == list(geordnet["b"]) == list(geordnet["c"][0]) == ["min", "max"]


def test_ordnen_haengt_nicht_an_der_eingangsfolge():
    """Gleich, in welcher Folge die Schlüssel ankommen — die Datei ist dieselbe."""
    lauf, entscheidung = _cc7f_wie_in_bc2()
    prio, konzept = ergebnisakte.vertragsschemas()
    dok = dict(lauf.dokument)
    schluessel = list(dok)
    random.Random(378).shuffle(schluessel)
    gemischt = {k: dok[k] for k in schluessel}
    assert ergebnisakte.als_text(ordne(gemischt, prio, prio)) == ergebnisakte.als_text(
        ordne(lauf.dokument, prio, prio)
    )


def test_nachricht_ist_die_alte_nachricht():
    """Der Kopf nennt weiter das Werkzeug: gelieferter Wortlaut (siehe ``nachricht``)."""
    lauf, entscheidung = _cc7f_wie_in_bc2()
    lieferung = {
        "ordner": CC7F.name,
        "priorisierung": {**lauf.dokument, "gate1": entscheidung.als_vertrag()},
        "konzepte": lauf.konzepte, "hinweise": list(lauf.hinweise),
        "kp_namen": lauf.kp_namen, "verwiesen": {},
    }
    assert nachricht(lieferung) == (CC7F / "NACHRICHT_AN_BC3.md").read_text(encoding="utf-8")
