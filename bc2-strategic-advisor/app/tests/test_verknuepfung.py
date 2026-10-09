"""
Tests der Verknüpfung über Pakete hinweg (#295, ADR-009 · BC2).

Vier Teile, in der Reihenfolge des Baus:

1. **Die Sperre greift über die Paketliste.** Bis #295 suchte die Ablage
   Vorgänger nur über die Teilprozesse der *geschnittenen* Potenziale. Ein
   Paket, das einen gelieferten Teilprozess neu brachte und diesmal nichts aus
   ihm schnitt, lief durch, und das alte Potenzial galt still als unverändert.
2. **Die Nachprüfung** (``nachfolge.pruefe_ausgaenge``) — §2.3 bis §2.5.
3. **Die Erkennung** sieht die Kandidaten nur qualitativ, und nur wenn es
   welche gibt; ihr Wächter prüft die Zuordnung mit.
4. **Der Abnahmefall des Tickets**: ein zweites Paket über einen schon
   gelieferten Teilprozess erzeugt eine Lieferung, deren Kette die Regel aus
   ``tools/kette.py`` (also ``validate.py``) besteht, und ein gestrichenes
   Potenzial steht mit Begründung in der Priorisierung.

**Was diese Tests nicht zeigen.** Kein Test hier ruft ein Modell, und keiner
läuft gegen Postgres. Die SQL-Seite prüft ``test_vertrag_postgres.py``.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ablage import (
    AblegendeLaufquelle,
    KetteUngueltig,
    NachfolgerOffen,
    SpeicherErgebnisbuch,
    potenzialzeilen,
)
from app import erzeuge_app
from erkennung import Doppelgaenger, packe
from erkennung.anweisung import VORGAENGER, baue_frage
from erkennung.modellruf import Antwort, schaele_json
from gate1 import Gate1Entscheidung, SpeicherGate1Buch, jetzt
from laeufe import (
    PaketLaufquelle,
    Paketeintrag,
    SpeicherLaufquelle,
    SpeicherPaketverzeichnis,
)
from nachfolge import Ausgang, Kandidat, Nachfolge, pruefe_ausgaenge

from conftest import MESSSAETZE
from test_bewertung import NOROAI, STAND, _ausgearbeitet, _bestand, _bewertung, _erkannt, _gut

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from kette import gelieferte_potenziale, kettenbefunde  # noqa: E402

TP1, TP2 = "KP-06.TP-1", "KP-06.TP-2"


def _freigeben(gate1: SpeicherGate1Buch, ansicht, status: str = "approved"):
    e = Gate1Entscheidung(
        paket_id=ansicht.kopf.paket_id,
        company_id=ansicht.kopf.company_id,
        status=status,
        fassung=ansicht.kopf.fassung,
        approved_potenzial_ids=tuple(ansicht.potenzial_ids()) if status == "approved" else (),
        kommentar="" if status == "approved" else "Taugt nicht.",
        entschieden_am=jetzt(),
    )
    gate1.merken(e)
    return e


def _kandidat(pid="ALT-1", tps=(TP2,), klasse="Integration", kp="KP-06") -> Kandidat:
    return Kandidat(
        potenzial_id=pid, paket_id="PKT-A", kp_id=kp, titel=f"Titel {pid}",
        klasse=klasse, teilprozess_ids=tuple(tps),
    )


# ======================================================================
# 1. Die Sperre greift über die Paketliste
# ======================================================================


def _messsatz_vorlage():
    """Ein Messsatzlauf **ohne Sperrgrund**, als käme er aus dem echten Weg: nur
    ein gelieferter Lauf stellt Kandidaten (#305)."""
    from laeufe import MesssatzLaufquelle

    q = MesssatzLaufquelle(MESSSAETZE)
    a = q.ansicht(q.uebersicht()[0].paket_id)
    return replace(a, kopf=replace(a.kopf, sperrgrund=None))


def test_ein_neu_gebrachter_teilprozess_ohne_potenzial_ist_trotzdem_neu_gesehen():
    """Paket B schneidet nichts, bringt aber die Teilprozesse von A — das ist
    genau die Lücke, die die Karte am 09.10.2026 an #295 vermerkt hat."""
    vorlage = _messsatz_vorlage()
    a = replace(vorlage, kopf=replace(vorlage.kopf, paket_id="PAKET-A"))
    b = replace(
        vorlage,
        kopf=replace(vorlage.kopf, paket_id="PAKET-B"),
        eintraege=[],
        prozess_raenge=[],
        potenziale={},
    )
    assert b.kopf.teilprozess_ids, "der Kopf trägt die Paketliste"
    ergebnisse = SpeicherErgebnisbuch()
    quelle = AblegendeLaufquelle(SpeicherLaufquelle([a, b]), ergebnisse)
    _freigeben(SpeicherGate1Buch(ergebnisse=ergebnisse), quelle.ansicht("PAKET-A"))

    with pytest.raises(NachfolgerOffen):
        quelle.ansicht("PAKET-B")
    assert ergebnisse.letzter("PAKET-B").beleg.zustand == "fehler"


def test_die_paketquelle_traegt_die_paketliste_in_den_kopf():
    verzeichnis = SpeicherPaketverzeichnis([Paketeintrag("PKT-A", NOROAI, STAND, (TP1, TP2))])
    quelle = PaketLaufquelle(verzeichnis, _Quelle(), Doppelgaenger([]), urteile=1)
    assert quelle.uebersicht()[0].teilprozess_ids == (TP1, TP2)


# ======================================================================
# 2. Die Nachprüfung (ADR-009 · BC2 §2.3–§2.5)
# ======================================================================

NEU = {"P1": {"klasse": "Integration", "kp_id": "KP-06"},
       "P2": {"klasse": "Assistenz", "kp_id": "KP-06"}}


def test_eine_saubere_zuordnung_haelt():
    kandidaten = [_kandidat("A1"), _kandidat("A2", tps=(TP1, TP2), klasse="Assistenz")]
    ausgaenge = [Ausgang("A1", "fortgeschrieben", "P1"),
                 Ausgang("A2", "gestrichen", begruendung="Faellt weg.")]
    assert pruefe_ausgaenge(kandidaten, ausgaenge, NEU, [TP1, TP2]) == []


@pytest.mark.parametrize(
    "ausgaenge, erwartet",
    [
        ([], "hat keinen Ausgang"),
        ([Ausgang("A1", "fortgeschrieben", "P1"), Ausgang("A1", "gestrichen", begruendung="x")],
         "2 Ausgaenge statt einem"),
        ([Ausgang("A1", "vielleicht")], "gibt es nicht"),
        ([Ausgang("A1", "fortgeschrieben", "P9")], "kein Potenzial dieses Laufs"),
        ([Ausgang("A1", "fortgeschrieben", "P2")], "Loesungsklasse"),
        ([Ausgang("A1", "gestrichen")], "ohne Begruendung"),
        ([Ausgang("A1", "unveraendert")], "ganz in diesem Paket"),
        ([Ausgang("A1", "gestrichen", begruendung="x"), Ausgang("FREMD", "gestrichen", begruendung="x")],
         "kein Kandidat"),
    ],
)
def test_die_nachpruefung_verwirft(ausgaenge, erwartet):
    befunde = pruefe_ausgaenge([_kandidat("A1")], ausgaenge, NEU, [TP2])
    assert any(erwartet in b for b in befunde), befunde


def test_nur_eins_zu_eins():
    kandidaten = [_kandidat("A1"), _kandidat("A2")]
    ausgaenge = [Ausgang("A1", "fortgeschrieben", "P1"), Ausgang("A2", "fortgeschrieben", "P1")]
    assert any("zwei Kandidaten" in b for b in pruefe_ausgaenge(kandidaten, ausgaenge, NEU, [TP2]))


def test_ein_nachfolger_bleibt_im_kernprozess():
    neu = {"P1": {"klasse": "Integration", "kp_id": "KP-05"}}
    befunde = pruefe_ausgaenge([_kandidat("A1")], [Ausgang("A1", "fortgeschrieben", "P1")], neu, [TP2])
    assert any("liegt in KP-05" in b for b in befunde)


def test_unveraendert_nur_mit_teilprozessen_ausserhalb_des_pakets():
    """§2.3: sonst striche jede Teilnacherhebung, was sie gar nicht neu gerechnet hat."""
    halb = _kandidat("A1", tps=(TP1, TP2))
    assert pruefe_ausgaenge([halb], [Ausgang("A1", "unveraendert")], NEU, [TP2]) == []


def test_die_streichliste_traegt_kernprozess_und_begruendung():
    n = Nachfolge(
        kandidaten=(_kandidat("A1"),),
        ausgaenge=(Ausgang("A1", "gestrichen", begruendung="  Der Medienbruch ist behoben. "),),
    )
    assert n.gestrichen() == [
        {"potenzial_id": "A1", "kp_id": "KP-06", "begruendung": "Der Medienbruch ist behoben."}
    ]


# ======================================================================
# 3. Die Erkennung
# ======================================================================


def test_ohne_kandidaten_bleibt_die_frage_wie_sie_war():
    """Die Stabilitätsmessungen zu #299 laufen ohne Kandidaten — die Frage
    darf sich für sie durch #295 um kein Zeichen ändern."""
    (aufruf,) = packe(_bestand())
    assert "vorgaenger_kandidaten" not in aufruf.inhalt
    assert VORGAENGER not in baue_frage(aufruf.inhalt)


def test_die_kandidaten_stehen_ohne_zahl_und_mit_kurznamen_in_der_nutzlast():
    k = replace(_kandidat(str(uuid.uuid4()), tps=(TP2, "KP-06.TP-9")),
                titel="Zeiterfassung anbinden", beschreibung="Beschrieb.")
    (aufruf,) = packe(_bestand(), kandidaten=(k,))

    (block,) = aufruf.inhalt["vorgaenger_kandidaten"]
    assert block == {
        "id": "V1",
        "kernprozess_id": "KP-06",
        "titel": k.titel,
        "beschreibung": "Beschrieb.",
        "loesungsklasse": "Integration",
        "beruehrte_teilprozesse": [TP2, "KP-06.TP-9"],
        "ausserhalb_dieses_pakets": ["KP-06.TP-9"],
    }
    assert k.potenzial_id not in json.dumps(aufruf.inhalt)
    assert VORGAENGER in baue_frage(aufruf.inhalt)


def test_unter_schnitt_b_sieht_jeder_aufruf_nur_die_kandidaten_seines_kernprozesses():
    from erkennung import Kernprozess, Teilprozess

    zwei = replace(
        _bestand(),
        kernprozesse=(
            *_bestand().kernprozesse,
            Kernprozess("KP-05", "Vertrieb",
                        teilprozesse=(Teilprozess("KP-05.TP-1", "KP-05", "Lead"),)),
        ),
    )
    k5 = _kandidat("A5", tps=("KP-05.TP-1",), kp="KP-05")
    k6 = _kandidat("A6")
    aufrufe = packe(zwei, grenze=10, kandidaten=(k5, k6))

    gesehen = {a.name: [v for v, _ in a.kandidaten] for a in aufrufe}
    assert gesehen == {"KP-06": ["V2"], "KP-05": ["V1"]}


class _Antwortend:
    """Ein Modellruf, der seine Antwort aus der Frage baut.

    Nötig, weil die Kurznamen ``V1`` … erst in der Frage feststehen: welcher
    Kandidat welchen trägt, hängt an der Reihenfolge der Kennungen.
    """

    def __init__(self, *antworten) -> None:
        self.antworten = list(antworten)
        self.fragen: list[str] = []

    def frage(self, text: str) -> Antwort:
        self.fragen.append(text)
        naechste = self.antworten.pop(0)
        if callable(naechste):
            naechste = naechste(_kurznamen(text))
        roh = json.dumps(naechste, ensure_ascii=False)
        return Antwort(roh=roh, ergebnis=schaele_json(roh), modell="antwortend")


def _kurznamen(frage: str) -> dict[str, str]:
    """Titel → Kurzname, aus dem Bestand in der Frage."""
    teil = frage.split("## Der Bestand")[1]
    nutzlast = json.loads(re.search(r"```json\n(.*)\n```", teil, re.S).group(1))
    return {k["titel"]: k["id"] for k in nutzlast.get("vorgaenger_kandidaten", [])}


def test_der_waechter_mahnt_eine_falsche_zuordnung_und_nimmt_die_richtige():
    from erkennung import erkenne

    a1 = _kandidat(str(uuid.uuid4()))
    erkannt = {"potenziale": _erkannt()["potenziale"][:1], "nicht_geschnitten": []}

    def falsch(kurz):
        return {**erkannt, "vorgaenger": [{"kandidat": kurz[a1.titel], "ausgang": "unveraendert"}]}

    def richtig(kurz):
        return {**erkannt, "vorgaenger": [
            {"kandidat": kurz[a1.titel], "ausgang": "fortgeschrieben", "nachfolger": "P1"}
        ]}

    modell = _Antwortend(falsch, richtig)
    bestand = replace(
        _bestand(),
        kernprozesse=(replace(_bestand().kernprozesse[0],
                              teilprozesse=_bestand().kernprozesse[0].teilprozesse[1:]),),
    )
    ergebnis = erkenne(bestand, modell, kandidaten=(a1,))

    assert "V1 als unveraendert gemeldet" in modell.fragen[1]
    assert ergebnis.nachfolge.ausgaenge == (Ausgang(a1.potenzial_id, "fortgeschrieben", "P1"),)
    assert ergebnis.aufrufe[0].versuche == 2


def test_die_begruendung_einer_streichung_faellt_unter_das_rechenverbot():
    from erkennung import ErkennungAbgebrochen, erkenne

    a1 = _kandidat(str(uuid.uuid4()))
    erkannt = {"potenziale": _erkannt()["potenziale"][:1], "nicht_geschnitten": []}

    def mit_zahl(kurz):
        return {**erkannt, "vorgaenger": [{"kandidat": kurz[a1.titel], "ausgang": "gestrichen",
                                           "begruendung": "Spart nur 40 Stunden."}]}

    with pytest.raises(ErkennungAbgebrochen, match="Rechenverbot"):
        erkenne(_bestand(), _Antwortend(mit_zahl, mit_zahl), kandidaten=(a1,))


# ======================================================================
# 4. Der Abnahmefall: zweites Paket, gültige Kette, Streichliste
# ======================================================================


class _Quelle:
    """Liest ``_bestand()``, beschränkt auf die Teilprozesse des Pakets."""

    def lies_paket(self, company_id, paket_id, uebergeben_am, teilprozess_ids):
        b = _bestand()
        kp = b.kernprozesse[0]
        return replace(
            b,
            paket_id=paket_id,
            uebergeben_am=uebergeben_am,
            kernprozesse=(replace(kp, teilprozesse=tuple(
                t for t in kp.teilprozesse if t.teilprozess_id in teilprozess_ids
            )),),
        )


def _strecke(*antworten, pakete=None):
    pakete = pakete or [
        Paketeintrag("PKT-A", NOROAI, STAND, (TP1, TP2)),
        Paketeintrag("PKT-B", NOROAI, STAND, (TP2,)),
    ]
    modell = _Antwortend(*antworten)
    innen = PaketLaufquelle(SpeicherPaketverzeichnis(pakete), _Quelle(), modell, urteile=1)
    ergebnisse = SpeicherErgebnisbuch()
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    return AblegendeLaufquelle(innen, ergebnisse), ergebnisse, gate1, modell


def _b_erkannt(kurz: dict[str, str]) -> dict:
    """Paket B über TP-2: ein Potenzial, das P1 aus A fortschreibt; A.P2 fällt weg."""
    p = dict(_erkannt()["potenziale"][0], titel="Zeiten automatisch abrechnen")
    return {
        "potenziale": [p],
        "nicht_geschnitten": [],
        "vorgaenger": [
            {"kandidat": kurz["Potenzial P1"], "ausgang": "fortgeschrieben", "nachfolger": "P1"},
            {"kandidat": kurz["Potenzial P2"], "ausgang": "gestrichen",
             "begruendung": "Die Einsatzplanung laeuft inzwischen im Projekttool."},
        ],
    }


def _b_bewertet() -> dict:
    return {"bewertungen": [_bewertung("P1")]}


def _kette() -> list:
    """Paket A und Paket B, je Erkennung, Bewertung und Ausarbeitung (#301)."""
    return [_erkannt(), _gut(), _ausgearbeitet("P1", "P2"),
            _b_erkannt, _b_bewertet(), _ausgearbeitet("P1")]


def test_das_zweite_paket_liefert_eine_gueltige_kette_und_eine_streichliste():
    laeufe, ergebnisse, gate1, modell = _strecke(*_kette())

    a = laeufe.ansicht("PKT-A")
    ea = _freigeben(gate1, a)
    alt = {p["titel"]: p["potenzial_id"] for p in a.potenziale.values()}

    b = laeufe.ansicht("PKT-B")
    eb = _freigeben(gate1, b)

    # Die Kandidaten standen in der Erkennungsfrage von B, ohne ihre UUID.
    frage_b = modell.fragen[3]
    assert "vorgaenger_kandidaten" in frage_b
    assert not any(pid in frage_b for pid in alt.values())

    dok = ergebnisse.letzter("PKT-B").dokument
    assert dok["schema_version"] == "3.1"
    # Die Hinweise kommen aus der Rechnung, nicht aus dem Kopf der Übersicht —
    # seit die Ablage vor dem Rechnen anlegt, liegen beide nebeneinander.
    hinweise = " ".join(b.kopf.hinweise)
    assert "#299" in hinweise and "Noch nicht gerechnet" not in hinweise
    assert b.kopf.lieferbar
    (neu,) = [p for k in b.konzepte for p in k["potenziale"]]
    assert neu["ersetzt_potenzial_ids"] == [alt["Potenzial P1"]]
    assert dok["gestrichene_potenziale"] == [{
        "potenzial_id": alt["Potenzial P2"],
        "kp_id": "KP-06",
        "begruendung": "Die Einsatzplanung laeuft inzwischen im Projekttool.",
    }]
    (zeile,) = potenzialzeilen(dok, ergebnisse.letzter("PKT-B").konzepte)
    assert zeile["ersetzt_potenzial_ids"] == [alt["Potenzial P1"]]

    # Die Lieferung, wie sie an BC3 ginge — geprüft mit der Regel aus validate.py.
    konzepte_a, prio_a = a.als_vertrag(ea.als_vertrag())
    konzepte_b, prio_b = b.als_vertrag(eb.als_vertrag())
    assert prio_b["gestrichene_potenziale"] == dok["gestrichene_potenziale"]
    geliefert = gelieferte_potenziale([(konzepte_a, prio_a)])
    assert kettenbefunde(konzepte_b, prio_b, geliefert) == []


def test_was_fortgeschrieben_oder_gestrichen_ist_ist_kein_kandidat_mehr():
    laeufe, ergebnisse, gate1, _ = _strecke(*_kette())
    _freigeben(gate1, laeufe.ansicht("PKT-A"))
    b = laeufe.ansicht("PKT-B")

    vorher = ergebnisse.kandidaten(NOROAI, "PKT-C", [TP1, TP2])
    assert {k.paket_id for k in vorher} == {"PKT-A"}, "B ist noch nicht freigegeben"

    _freigeben(gate1, b)
    nachher = ergebnisse.kandidaten(NOROAI, "PKT-C", [TP1, TP2])
    # A.P1 ist fortgeschrieben, A.P2 gestrichen — gültig ist allein B.P1.
    assert [k.paket_id for k in nachher] == ["PKT-B"]
    assert nachher[0].titel == "Zeiten automatisch abrechnen"
    assert nachher[0].klasse == "Integration"


def test_die_gate1_ansicht_zeigt_vorgaenger_und_streichliste(buch, kopf):
    laeufe, ergebnisse, gate1, _ = _strecke(*_kette())
    _freigeben(gate1, laeufe.ansicht("PKT-A"))

    with TestClient(erzeuge_app(buch, laufquelle=laeufe, gate1_buch=gate1)) as c:
        lauf = c.get("/api/oberflaeche/laeufe/PKT-B", headers=kopf).json()

    (gestrichen,) = lauf["gestrichene_potenziale"]
    assert gestrichen["begruendung"].startswith("Die Einsatzplanung")
    (pot,) = lauf["potenziale"].values()
    (alt,) = pot["ersetzt_potenzial_ids"]
    assert lauf["verwiesen"][alt] == {"titel": "Potenzial P1", "paket_id": "PKT-A", "kp_id": "KP-06"}
    assert lauf["verwiesen"][gestrichen["potenzial_id"]]["titel"] == "Potenzial P2"


def test_ohne_ausgangslage_bleibt_die_sperre():
    """Eine Quelle ohne Ausarbeitung trägt keine Ausgangslage, also keinen
    Vertrag 3.1 — und 3.0 hat für die Kette keine Felder. Dann lieber anhalten
    als ``[]``. *(Bis #301 war das der echte Weg selbst.)*"""
    pakete = [Paketeintrag("PKT-A", NOROAI, STAND, (TP1, TP2)),
              Paketeintrag("PKT-B", NOROAI, STAND, (TP2,))]
    modell = _Antwortend(_erkannt(), _gut(), _b_erkannt, _b_bewertet())
    innen = PaketLaufquelle(
        SpeicherPaketverzeichnis(pakete), _Quelle(), modell, urteile=1, ausarbeiten=False
    )
    ergebnisse = SpeicherErgebnisbuch()
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    laeufe = AblegendeLaufquelle(innen, ergebnisse)
    _freigeben(gate1, laeufe.ansicht("PKT-A"))
    # Ohne Ausarbeitung trüge A selbst einen Sperrgrund und wäre nie geliefert
    # (#305) — hier zählt nur B. A steht darum, als wäre es geliefert worden.
    ergebnisse.zeilen["PKT-A"][-1].sperrgrund = None

    with pytest.raises(NachfolgerOffen, match="Vertrag 3.1"):
        laeufe.ansicht("PKT-B")


def test_eine_kette_an_der_nachpruefung_vorbei_wird_nicht_abgelegt():
    """Die Ablage prüft selbst, statt der Quelle zu glauben."""
    vorlage = _messsatz_vorlage()
    a = replace(vorlage, kopf=replace(vorlage.kopf, paket_id="PAKET-A"),
                ausgangslage={"unternehmen": {}})
    ergebnisse = SpeicherErgebnisbuch()
    quelle_a = AblegendeLaufquelle(SpeicherLaufquelle([a]), ergebnisse)
    _freigeben(SpeicherGate1Buch(ergebnisse=ergebnisse), quelle_a.ansicht("PAKET-A"))

    # B behauptet, nichts sei zu tun — es gibt aber Kandidaten.
    b = replace(a, kopf=replace(a.kopf, paket_id="PAKET-B"), nachfolge=Nachfolge())
    quelle_b = AblegendeLaufquelle(SpeicherLaufquelle([b]), ergebnisse)
    with pytest.raises(KetteUngueltig, match="hat keinen Ausgang"):
        quelle_b.ansicht("PAKET-B")
    assert ergebnisse.letzter("PAKET-B").beleg.zustand == "fehler"
