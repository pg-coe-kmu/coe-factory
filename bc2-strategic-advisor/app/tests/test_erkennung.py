"""
Tests des Erkennungsschritts (#248, Entscheidung in #194).

**Was diese Tests nicht zeigen.** Kein Test hier ruft ein Modell. Dass sich ein
Modell an das Rechenverbot hält, ist damit *nicht* gezeigt — in #194 hielt es
sich in 2 von 21 Aufrufen nicht daran, und genau dafür gibt es den Wächter.
Geprüft wird die Kette **um** das Modell herum: Lesen, Packen, Wächter,
Wiederholung, Abbildung. Die Lehre aus #205 gilt auch hier: ein grüner Lauf
gegen einen Doppelgänger beweist nichts über die Naht zu einem fremden System.
Der echte Aufruf ist von Hand gefahren und im Ticket protokolliert.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from erkennung import (
    Bewertung,
    Doppelgaenger,
    ErkennungAbgebrochen,
    Kernprozess,
    Mandant,
    Paketbestand,
    SnapshotBestand,
    Teilprozess,
    erkenne,
    paare_im_kernprozess,
    packe,
    pruefe_schnitt,
)
from erkennung.pruefen import erlaubte_klassen

SNAPSHOT = (
    Path(__file__).resolve().parents[3]
    / "bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json"
)
NOROAI = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"
STAND = datetime(2026, 9, 20, tzinfo=timezone.utc)

#: Das Paket aus dem Prototyp zu #194 — geschnitten auf die unangenehmen Fälle:
#: KP-02/KP-03 dicht bewertet, KP-05 fast nur Platzhalter, KP-06.TP-2 einzeln.
PROTOTYP_PAKET = [
    "KP-02.TP-1", "KP-02.TP-2", "KP-02.TP-3", "KP-02.TP-4", "KP-02.TP-5",
    "KP-03.TP-1", "KP-03.TP-2", "KP-03.TP-3", "KP-03.TP-4", "KP-03.TP-5",
    "KP-05.TP-1", "KP-05.TP-2", "KP-05.TP-3", "KP-05.TP-4", "KP-05.TP-5",
    "KP-06.TP-2",
]


@pytest.fixture(scope="module")
def quelle() -> SnapshotBestand:
    return SnapshotBestand(SNAPSHOT)


@pytest.fixture
def bestand(quelle):
    return quelle.lies_paket(NOROAI, "PKT-TEST", STAND, PROTOTYP_PAKET)


def baue_bestand(*teilprozesse: Teilprozess, kp_id: str = "KP-01") -> Paketbestand:
    """Ein Bestand von Hand, für die Fälle, die der Snapshot nicht hergibt."""
    return Paketbestand(
        mandant=Mandant(company_id=NOROAI, name="NoroAI"),
        paket_id="PKT-HAND",
        uebergeben_am=STAND,
        gelesen_am=STAND,
        kernprozesse=(Kernprozess(kernprozess_id=kp_id, name="Test", teilprozesse=teilprozesse),),
    )


def tp(nr: int, **kw) -> Teilprozess:
    kw.setdefault("name", f"Schritt {nr}")
    return Teilprozess(
        teilprozess_id=f"KP-01.TP-{nr}", kernprozess_id="KP-01", schritt_nr=nr, **kw
    )


def bew(item: int, stufe: int = 3, beleg: str = "Beleg") -> Bewertung:
    return Bewertung(item_nr=item, kriterium=f"K{item}", frage=f"F{item}", stufe=stufe, beleg=beleg)


def potenzial(pid: str, kp: str, tps: list[str], **kw) -> dict:
    d = {
        "id": pid,
        "kernprozess_id": kp,
        "titel": f"Potenzial {pid}",
        "beruehrte_teilprozesse": tps,
        "ausgangslage": "Heute von Hand.",
        "schmerzpunkte": ["Doppelerfassung"],
        "loesungsansatz": "Anbinden.",
        "loesungsklasse": "Integration",
        "trenntest_begruendung": "Eigenstaendig baubar, kein Doppelzaehlen.",
        "unsicherheit": None,
    }
    d.update(kw)
    return d


# ---------------------------------------------------------------------------
# Leseseite — Auflage 4: die 0 ist keine Zahl, sondern eine Lücke
# ---------------------------------------------------------------------------


def test_unbewerteter_teilprozess_traegt_keine_null(bestand):
    """27 von 50 Teilprozessen tragen null Bewertungen und stehen trotzdem mit
    ``avg: 0`` in der Matrix. Wer das als Zahl liest, hält den unerhobenen
    Teilprozess für den am schlechtesten automatisierbaren im Bestand."""
    ohne = {t.teilprozess_id: t for t in bestand.teilprozesse if not t.bewertet}
    assert "KP-05.TP-3" in ohne
    t = ohne["KP-05.TP-3"]
    assert t.bitkom == ()
    assert not t.schneidbar

    inhalt = packe(bestand)[0].inhalt
    block = next(
        b
        for kp in inhalt["kernprozesse"]
        for b in kp["teilprozesse"]
        if b["teilprozess_id"] == "KP-05.TP-3"
    )
    assert block["bewertungen"] == "nicht erhoben"
    assert "0" not in json.dumps(block.get("bewertungen"))


def test_platzhalter_wird_erkannt_aber_nicht_weggelassen(bestand):
    """Platzhalter werden **gemeldet, nicht geschnitten** — und schon gar nicht
    stillschweigend aus einem Paket entfernt, das sie freigegeben hat."""
    namen = {t.teilprozess_id: t for t in bestand.teilprozesse}
    assert namen["KP-05.TP-3"].ist_platzhalter
    assert not namen["KP-05.TP-1"].ist_platzhalter
    assert set(bestand.teilprozess_ids) == set(PROTOTYP_PAKET)
    assert "KP-05.TP-3" not in bestand.schneidbare_ids


def test_snapshot_gesteht_sein_datum_ein(bestand):
    assert any("27.08.2026" in h for h in bestand.hinweise)


def test_fehlender_teilprozess_wird_gemeldet(quelle):
    b = quelle.lies_paket(NOROAI, "PKT", STAND, ["KP-02.TP-1", "KP-99.TP-9"])
    assert any("KP-99.TP-9" in h for h in b.hinweise)


# ---------------------------------------------------------------------------
# Nutzlast — Auflage 2: Kernprozess-Text einmal stellen, bedingt
# ---------------------------------------------------------------------------


def test_wortgleiche_felder_wandern_an_den_kernprozess():
    b = baue_bestand(
        tp(1, werkzeuge="CRM, Mail", bitkom=(bew(1),)),
        tp(2, werkzeuge="CRM, Mail", bitkom=(bew(1),)),
    )
    kp = packe(b)[0].inhalt["kernprozesse"][0]
    assert kp["gilt_fuer_alle_teilprozesse"]["werkzeuge"] == "CRM, Mail"
    assert all("werkzeuge" not in t for t in kp["teilprozesse"])


def test_unterschiedliche_felder_bleiben_beim_teilprozess():
    """Nicht blind heben: der Befund »bei 10 von 10 wortgleich« stammt vom
    Snapshot vom 27.08. und wird erst in #249 am Livestand gegengeprüft."""
    b = baue_bestand(
        tp(1, werkzeuge="CRM", bitkom=(bew(1),)),
        tp(2, werkzeuge="Excel", bitkom=(bew(1),)),
    )
    kp = packe(b)[0].inhalt["kernprozesse"][0]
    assert "werkzeuge" not in kp.get("gilt_fuer_alle_teilprozesse", {})
    assert [t["werkzeuge"] for t in kp["teilprozesse"]] == ["CRM", "Excel"]


def test_belege_werden_nur_gehoben_wenn_alle_items_wortgleich():
    gleich = baue_bestand(
        tp(1, bitkom=(bew(1, 4, "derselbe Satz"), bew(2, 2, "zweiter Satz"))),
        tp(2, bitkom=(bew(1, 3, "derselbe Satz"), bew(2, 5, "zweiter Satz"))),
    )
    kp = packe(gleich)[0].inhalt["kernprozesse"][0]
    assert kp["bitkom_belege"]["1"] == "derselbe Satz"
    assert all("beleg" not in e for t in kp["teilprozesse"] for e in t["bitkom"])
    # Die Stufen unterscheiden sich weiterhin — genau darum geht es.
    assert [e["stufe"] for t in kp["teilprozesse"] for e in t["bitkom"]] == [4, 2, 3, 5]

    verschieden = baue_bestand(
        tp(1, bitkom=(bew(1, 4, "Satz A"),)),
        tp(2, bitkom=(bew(1, 3, "Satz B"),)),
    )
    kp2 = packe(verschieden)[0].inhalt["kernprozesse"][0]
    assert "bitkom_belege" not in kp2
    assert kp2["teilprozesse"][0]["bitkom"][0]["beleg"] == "Satz A"


def test_einzelner_teilprozess_wird_nicht_entdoppelt():
    """Bei einem einzigen Teilprozess ist »gilt für alle« eine Umschreibung für
    »gilt für diesen einen« — das kostet Platz und sagt nichts."""
    b = baue_bestand(tp(1, werkzeuge="CRM", bitkom=(bew(1),)))
    kp = packe(b)[0].inhalt["kernprozesse"][0]
    assert "gilt_fuer_alle_teilprozesse" not in kp
    assert kp["teilprozesse"][0]["werkzeuge"] == "CRM"


def test_itemkatalog_steht_einmal_im_rahmen(bestand):
    """30 Items mal 50 Teilprozessen wäre derselbe Text 1500-mal."""
    inhalt = packe(bestand)[0].inhalt
    nummern = [i["item"] for i in inhalt["rahmen"]["bitkom_items"]]
    assert len(nummern) == len(set(nummern))
    assert all("kriterium" not in e for kp in inhalt["kernprozesse"]
               for t in kp["teilprozesse"] for e in t.get("bitkom", []))


def test_entdoppelt_ist_der_ganze_bestand_kleiner_als_das_prototyp_paket(quelle, bestand):
    """Der Messbefund, der Auflage 1 auf den Kopf stellt.

    Der Ticketkopf rechnete für ein Paket über alle 50 Teilprozesse mit dem
    Dreifachen von 80.431 Zeichen. Entdoppelt ist der **ganze** Bestand kleiner
    als der Prototyp-Aufruf über 16."""
    alle = [
        t.teilprozess_id
        for p in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["stammdaten"]["prozesse"]
        for t in [type("T", (), {"teilprozess_id": x["sub_process_id"]}) for x in p["teilprozesse"]]
    ]
    ganz = quelle.lies_paket(NOROAI, "PKT-ALLE", STAND, alle)
    assert len(ganz.teilprozess_ids) == 50

    gross = packe(ganz)[0]
    assert gross.schnitt == "C"
    assert gross.zeichen < 80_431
    # Und er bleibt weit unter der Grenze: sie greift heute nicht.
    assert gross.zeichen < 120_000


# ---------------------------------------------------------------------------
# Nutzlast — Auflage 1: die Obergrenze
# ---------------------------------------------------------------------------


def test_unter_der_grenze_genau_ein_aufruf(bestand):
    aufrufe = packe(bestand)
    assert len(aufrufe) == 1
    assert aufrufe[0].schnitt == "C"
    assert set(aufrufe[0].teilprozess_ids) == set(PROTOTYP_PAKET)


def test_ueber_der_grenze_rueckfall_auf_schnitt_b(bestand):
    aufrufe = packe(bestand, grenze=1_000)
    assert len(aufrufe) == 4
    assert {a.schnitt for a in aufrufe} == {"B"}
    assert [a.name for a in aufrufe] == ["KP-02", "KP-03", "KP-05", "KP-06"]
    # Jeder Aufruf ist nur fuer seine eigenen Teilprozesse zustaendig — sonst
    # meldete die Deckungspruefung die der anderen als unbedeckt.
    assert set(aufrufe[3].teilprozess_ids) == {"KP-06.TP-2"}
    assert sum(len(a.teilprozess_ids) for a in aufrufe) == 16
    assert "hinweis_zum_schnitt" in aufrufe[0].inhalt["rahmen"]


def test_leeres_paket_ergibt_keinen_aufruf():
    leer = Paketbestand(
        mandant=Mandant(company_id=NOROAI),
        paket_id="PKT-LEER",
        uebergeben_am=STAND,
        gelesen_am=STAND,
    )
    assert packe(leer) == ()


# ---------------------------------------------------------------------------
# Die Nachkontrolle
# ---------------------------------------------------------------------------


def test_sauberer_satz_ist_sauber():
    bericht = pruefe_schnitt(
        [potenzial("P1", "KP-01", ["KP-01.TP-1", "KP-01.TP-2"])],
        ["KP-01.TP-1", "KP-01.TP-2"],
    )
    assert bericht.sauber
    assert bericht.verstoesse == ()
    assert bericht.anzahl == 1


@pytest.mark.parametrize(
    "text",
    ["spart 540 Stunden", "23.220 EUR im Jahr", "rund 40 % weniger", "etwa 5 PT Aufwand"],
)
def test_zahl_mit_einheit_haelt_den_lauf_an(text):
    """Der Verstoß, der in 2 von 21 Aufrufen auftrat — genau dort, wo Zahlen in
    der Nutzlast standen (BC1s 540 h / 23.220 € bei KP-06.TP-2)."""
    bericht = pruefe_schnitt(
        [potenzial("P1", "KP-01", ["KP-01.TP-1"], loesungsansatz=text)], ["KP-01.TP-1"]
    )
    assert bericht.zahlen_im_text == ("P1",)
    assert not bericht.sauber


@pytest.mark.parametrize(
    "text",
    ["Item 6 ist niedrig", "betrifft KP-02.TP-5", "Stufe 3 laut Beleg", "P1 und P2"],
)
def test_zahl_ohne_einheit_ist_kein_verstoss(text):
    """Die Regel hängt an der Einheit, nicht an der Ziffer — sonst wäre jede
    Teilprozess-ID ein Verstoß."""
    bericht = pruefe_schnitt(
        [potenzial("P1", "KP-01", ["KP-01.TP-1"], ausgangslage=text)], ["KP-01.TP-1"]
    )
    assert bericht.zahlen_im_text == ()
    assert bericht.sauber


def test_potenzial_ueber_zwei_kernprozesse_ist_vertragsbruch():
    bericht = pruefe_schnitt(
        [potenzial("P1", "KP-01", ["KP-01.TP-1", "KP-02.TP-1"])],
        ["KP-01.TP-1", "KP-02.TP-1"],
    )
    assert bericht.ueber_kernprozess == ("P1",)
    assert not bericht.sauber


def test_klassen_des_prototyps_faellt_der_vertrag_durch():
    """Regressionstest auf den Fund beim Bau: **10 von 10** Potenzialen des
    Prototyps zu #194 trugen eine Klasse, die ``konzept.schema.json`` nicht
    kennt und für die ``modell.parameter`` keinen Korridor hat."""
    aus_dem_prototyp = ["regelwerk", "dokumentenverarbeitung", "dialog", "assistenz"]
    bericht = pruefe_schnitt(
        [
            potenzial(f"P{i}", "KP-01", ["KP-01.TP-1"], loesungsklasse=k)
            for i, k in enumerate(aus_dem_prototyp)
        ],
        ["KP-01.TP-1"],
    )
    assert len(bericht.unbekannte_klasse) == 4
    assert not bericht.sauber
    # „Integration" fehlte im Prototyp-Prompt ganz — ausgerechnet die Klasse,
    # die Medienbrueche schliesst, also NoroAIs Hauptbefund.
    assert "Integration" in erlaubte_klassen()
    assert "Integration" not in aus_dem_prototyp


def test_gemeldeter_teilprozess_gilt_nicht_als_unbedeckt():
    """Die Regel aus #194: nicht schneiden, sondern melden."""
    offen = pruefe_schnitt([], ["KP-01.TP-1"])
    assert offen.unbedeckt == ("KP-01.TP-1",)

    gemeldet = pruefe_schnitt(
        [], ["KP-01.TP-1"], [{"teilprozess_id": "KP-01.TP-1", "grund": "Platzhalter"}]
    )
    assert gemeldet.unbedeckt == ()
    assert gemeldet.sauber


def test_mehrfachbelegung_ist_kein_verstoss():
    """Ein Teilprozess kann mehrere Potenziale tragen (CONTEXT.md) — das ist
    ein Zeiger fürs Auge, kein Fehler."""
    bericht = pruefe_schnitt(
        [
            potenzial("P1", "KP-01", ["KP-01.TP-1"]),
            potenzial("P2", "KP-01", ["KP-01.TP-1"]),
        ],
        ["KP-01.TP-1"],
    )
    assert bericht.mehrfach == (("KP-01.TP-1", ("P1", "P2")),)
    assert len(bericht.ueberschneidungen) == 1
    assert bericht.sauber


def test_fremder_teilprozess_wird_gemeldet():
    bericht = pruefe_schnitt(
        [potenzial("P1", "KP-01", ["KP-09.TP-9"])], ["KP-01.TP-1"]
    )
    assert bericht.fremd == (("P1", "KP-09.TP-9"),)


def test_pruefung_ist_blind_gegen_doppelgaenger_ohne_gemeinsamen_teilprozess():
    """Der Befund, der Schnitt A erledigt hat — hier als Test festgehalten.

    Fünf Kopien desselben Sachverhalts, jede auf ihrem eigenen Teilprozess:
    die mechanische Prüfung meldet **null** Überschneidungen. Doppelzählung ist
    eine Aussage über ein Paar, und dort sieht kein Aufruf je beide Hälften.
    Das ist kein Mangel der Prüfung, sondern der Grund für Schnitt C."""
    kopien = [
        potenzial(f"P{i}", "KP-01", [f"KP-01.TP-{i}"], titel="E-Mail ins CRM uebernehmen")
        for i in range(1, 6)
    ]
    bericht = pruefe_schnitt(kopien, [f"KP-01.TP-{i}" for i in range(1, 6)])
    assert bericht.ueberschneidungen == ()
    assert bericht.sauber
    # Sichtbar wird es erst fuer den Menschen — als Paare im selben Kernprozess.
    assert len(paare_im_kernprozess(kopien)) == 10


def test_paare_nur_innerhalb_eines_kernprozesses():
    paare = paare_im_kernprozess(
        [
            potenzial("P1", "KP-01", ["KP-01.TP-1"]),
            potenzial("P2", "KP-01", ["KP-01.TP-1", "KP-01.TP-2"]),
            potenzial("P3", "KP-02", ["KP-02.TP-1"]),
        ]
    )
    assert len(paare) == 1
    assert (paare[0].a, paare[0].b) == ("P1", "P2")
    assert paare[0].gemeinsame_teilprozesse == ("KP-01.TP-1",)


# ---------------------------------------------------------------------------
# Der Ablauf und der Wächter
# ---------------------------------------------------------------------------


def antwort(*potenziale: dict, nicht: list[dict] | None = None) -> dict:
    return {"potenziale": list(potenziale), "nicht_geschnitten": nicht or []}


def test_glueckspfad(bestand):
    modell = Doppelgaenger(
        [
            antwort(
                potenzial("P1", "KP-02", ["KP-02.TP-1", "KP-02.TP-2"]),
                nicht=[{"teilprozess_id": t, "grund": "Platzhalter"} for t in PROTOTYP_PAKET[:1]],
            )
        ]
    )
    ergebnis = erkenne(bestand, modell)
    assert [p.potenzial_id for p in ergebnis.potenziale] == ["P1"]
    assert ergebnis.potenziale[0].klasse == "Integration"
    assert ergebnis.aufrufe[0].versuche == 1
    assert ergebnis.aufrufe[0].schnitt == "C"
    assert ergebnis.company_id == NOROAI
    assert ergebnis.kernprozess_ids == ("KP-02",)


def test_waechter_wiederholt_einmal_und_nennt_den_grund(bestand):
    """Auflage 3: das Rechenverbot braucht einen Wächter, keine Bitte."""
    modell = Doppelgaenger(
        [
            antwort(potenzial("P1", "KP-02", ["KP-02.TP-1"], loesungsansatz="spart 540 Stunden")),
            antwort(potenzial("P1", "KP-02", ["KP-02.TP-1"])),
        ]
    )
    ergebnis = erkenne(bestand, modell)

    assert len(ergebnis.potenziale) == 1
    prot = ergebnis.aufrufe[0]
    assert prot.versuche == 2
    assert any("Rechenverbot" in g for g in prot.verworfen)
    # Die Mahnung reist wirklich mit — sonst wiederholte das Modell den Fehler.
    assert "Wiederholung" not in modell.fragen[0]
    assert "Wiederholung" in modell.fragen[1]
    assert "Rechenverbot" in modell.fragen[1]


def test_zweimal_gebrochen_haelt_den_lauf_an(bestand):
    """Ein still verworfenes Potenzial wäre ein Loch im Paket, das niemand
    sieht — also bricht der Lauf ab, statt weniger zu liefern."""
    kaputt = antwort(
        potenzial("P1", "KP-02", ["KP-02.TP-1"], loesungsansatz="spart 23.220 EUR")
    )
    modell = Doppelgaenger([kaputt, kaputt])
    with pytest.raises(ErkennungAbgebrochen) as fehler:
        erkenne(bestand, modell)
    assert "Rechenverbot" in str(fehler.value)
    assert fehler.value.aufruf == "PKT-TEST"
    assert fehler.value.roh


def test_ohne_wiederholung_bricht_sofort_ab(bestand):
    modell = Doppelgaenger(
        [antwort(potenzial("P1", "KP-02", ["KP-02.TP-1"], titel="spart 5 PT"))]
    )
    with pytest.raises(ErkennungAbgebrochen):
        erkenne(bestand, modell, wiederholungen=0)
    assert modell.fragen and len(modell.fragen) == 1


def test_unlesbare_antwort_wird_wiederholt(bestand):
    modell = Doppelgaenger(
        ["Tut mir leid, dazu kann ich nichts sagen.", antwort(potenzial("P1", "KP-02", ["KP-02.TP-1"]))]
    )
    ergebnis = erkenne(bestand, modell)
    assert len(ergebnis.potenziale) == 1
    assert ergebnis.aufrufe[0].versuche == 2
    assert any("JSON" in g for g in ergebnis.aufrufe[0].verworfen)


def test_schnitt_b_stellt_den_aufrufnamen_voran(bestand):
    """Jeder Aufruf zählt bei ``P1`` wieder von vorn — zwei Potenziale mit
    derselben Kennung wären in der Lieferung nicht auseinanderzuhalten."""
    modell = Doppelgaenger(
        [
            antwort(potenzial("P1", "KP-02", ["KP-02.TP-1"])),
            antwort(potenzial("P1", "KP-03", ["KP-03.TP-1"])),
            antwort(nicht=[{"teilprozess_id": f"KP-05.TP-{i}", "grund": "Platzhalter"}
                           for i in range(1, 6)]),
            antwort(potenzial("P1", "KP-06", ["KP-06.TP-2"])),
        ]
    )
    ergebnis = erkenne(bestand, modell, grenze=1_000)
    assert [p.potenzial_id for p in ergebnis.potenziale] == [
        "KP-02/P1", "KP-03/P1", "KP-06/P1"
    ]
    assert len(ergebnis.aufrufe) == 4
    assert any("Schnitt B" in h for h in ergebnis.hinweise)


def test_gesamtpruefung_sieht_die_luecke_ueber_alle_aufrufe(bestand):
    """Unter Schnitt B ist die Gesamtprüfung die einzige Stelle, an der
    kernprozessübergreifende Deckung überhaupt noch sichtbar wird."""
    modell = Doppelgaenger([antwort(potenzial("P1", "KP-02", ["KP-02.TP-1"]))])
    ergebnis = erkenne(bestand, modell)
    assert "KP-03.TP-1" in ergebnis.pruefung.unbedeckt
    assert any("weder geschnitten noch gemeldet" in h for h in ergebnis.hinweise)
    # Eine Luecke ist ein Befund, kein Verstoss — der Lauf lebt.
    assert ergebnis.pruefung.sauber


def test_hinweise_des_bestands_reisen_mit(bestand):
    modell = Doppelgaenger([antwort(potenzial("P1", "KP-02", ["KP-02.TP-1"]))])
    ergebnis = erkenne(bestand, modell)
    assert any("27.08.2026" in h for h in ergebnis.hinweise)
