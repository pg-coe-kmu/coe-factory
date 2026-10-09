"""
Tests der Ablage (#290, ADR-008 · BC2) — gegen die Doppelgänger.

Was hier grün ist, ist **Semantik**, keine Garantie: Fassungsvergabe, ein
offener Lauf je Paket und die Endgültigkeit von Gate 1 setzt in Betrieb die
Datenbank durch. Das prüft ``test_vertrag_postgres.py`` von Hand gegen sie.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from ablage import (
    AblegendeLaufquelle,
    NeulaufNichtErlaubt,
    SpeicherErgebnisbuch,
    dokumente_aus_ansicht,
    potenzialzeilen,
)
from gate1 import (
    Gate1Entscheidung,
    Gate1Konflikt,
    NichtFreigegeben,
    SpeicherGate1Buch,
    jetzt,
    zeilen_aus,
)
from laeufe import MesssatzLaufquelle

from conftest import MESSSAETZE


class ZaehlendeQuelle:
    """Die Messsatzquelle, die mitzählt, wie oft gerechnet wurde."""

    def __init__(self, scheitert: bool = False) -> None:
        self._innen = MesssatzLaufquelle(MESSSAETZE)
        self.gerechnet = 0
        self.scheitert = scheitert

    def uebersicht(self, company_id=None):
        return self._innen.uebersicht(company_id)

    def ansicht(self, paket_id):
        self.gerechnet += 1
        ansicht = self._innen.ansicht(paket_id)
        if self.scheitert and ansicht is not None:
            # Ein Potenzial ohne Teilprozesse lässt die Projektion scheitern —
            # das Ergebnis darf dann **gar nicht** liegen, nicht halb.
            kaputt = [dict(e) for e in ansicht.eintraege]
            del kaputt[0]["betroffene_teilprozess_ids"]
            return replace(ansicht, eintraege=kaputt)
        return ansicht


@pytest.fixture
def ergebnisse() -> SpeicherErgebnisbuch:
    return SpeicherErgebnisbuch()


@pytest.fixture
def innen() -> ZaehlendeQuelle:
    return ZaehlendeQuelle()


@pytest.fixture
def quelle(innen, ergebnisse) -> AblegendeLaufquelle:
    return AblegendeLaufquelle(innen, ergebnisse)


@pytest.fixture
def paket_id(innen) -> str:
    return innen.uebersicht()[0].paket_id


def entscheiden(gate1, ansicht, status: str, **weiteres) -> Gate1Entscheidung:
    e = Gate1Entscheidung(
        paket_id=ansicht.kopf.paket_id,
        company_id=ansicht.kopf.company_id,
        status=status,
        fassung=ansicht.kopf.fassung,
        approved_potenzial_ids=tuple(ansicht.potenzial_ids()) if status == "approved" else (),
        kommentar="Taugt nicht." if status == "rejected" else "",
        entschieden_am=jetzt(),
        **weiteres,
    )
    gate1.merken(e)
    return e


# ---------------------------------------------------------------------------
# Ablegen und Zeigen
# ---------------------------------------------------------------------------


def test_gerechnet_wird_einmal_danach_gilt_das_abgelegte(quelle, innen, paket_id):
    erste = quelle.ansicht(paket_id)
    zweite = quelle.ansicht(paket_id)

    assert innen.gerechnet == 1
    assert erste == zweite
    assert erste.kopf.fassung == 1


def test_die_ansicht_traegt_die_echten_kennungen(quelle, ergebnisse, paket_id):
    """Die Platzhalter aus ``aus_lauf`` werden beim Ablegen durch UUIDs ersetzt —
    überall, auch in den Verweisen der Einträge."""
    ansicht = quelle.ansicht(paket_id)
    abgelegt = ergebnisse.letzter(paket_id)

    konzept_ids = set(abgelegt.dokument["konzept_ids"])
    assert {k["konzept_id"] for k in abgelegt.konzepte} == konzept_ids
    for kid in konzept_ids:
        uuid.UUID(kid)
    assert {e["konzept_id"] for e in ansicht.eintraege} <= konzept_ids
    assert {r["konzept_id"] for r in ansicht.prozess_raenge} == konzept_ids
    uuid.UUID(abgelegt.dokument["priorisierung_id"])


def test_gezeigt_wird_genau_das_abgelegte_dokument(quelle, ergebnisse, paket_id):
    ansicht = quelle.ansicht(paket_id)
    dok = ergebnisse.letzter(paket_id).dokument

    assert ansicht.eintraege == dok["eintraege"]
    assert ansicht.prozess_raenge == dok["prozess_raenge"]
    assert ansicht.score_formel == dok["score_formel"]
    # Das Dokument trägt keinen gate1-Block — der liegt zerlegt daneben.
    assert "gate1" not in dok


def test_die_warnung_des_messsatzes_reist_mit(quelle, innen, paket_id):
    """Ein Messsatz ist nicht nachrechenbar; das darf beim Ablegen nicht verloren gehen."""
    vorher = innen.uebersicht()[0].warnung
    assert vorher
    assert quelle.ansicht(paket_id).kopf.warnung == vorher


def test_jedes_potenzial_steht_in_genau_einem_konzept(quelle, ergebnisse, paket_id):
    quelle.ansicht(paket_id)
    abgelegt = ergebnisse.letzter(paket_id)

    zeilen = potenzialzeilen(abgelegt.dokument, abgelegt.konzepte)
    in_konzepten = [p["potenzial_id"] for k in abgelegt.konzepte for p in k["potenziale"]]
    assert sorted(in_konzepten) == sorted(z["potenzial_id"] for z in zeilen)
    assert len(in_konzepten) == len(set(in_konzepten))


def test_ein_gescheiterter_lauf_ist_keine_fassung(ergebnisse, paket_id):
    """Technischer Fehler → Zustand ``fehler``; der Neuversuch läuft unter
    **derselben** Fassung (ADR-008 · BC2, 2.1)."""
    kaputt = AblegendeLaufquelle(ZaehlendeQuelle(scheitert=True), ergebnisse)
    with pytest.raises(KeyError):
        kaputt.ansicht(paket_id)

    gescheitert = ergebnisse.letzter(paket_id)
    assert gescheitert.beleg.zustand == "fehler"
    assert gescheitert.dokument is None

    heil = AblegendeLaufquelle(ZaehlendeQuelle(), ergebnisse)
    ansicht = heil.ansicht(paket_id)
    assert ansicht.kopf.fassung == 1
    assert ergebnisse.letzter(paket_id).beleg.priorisierung_id == gescheitert.beleg.priorisierung_id


def test_unbekanntes_paket_legt_nichts_an(quelle, ergebnisse):
    assert quelle.ansicht("GIBT-ES-NICHT") is None
    assert ergebnisse.letzter("GIBT-ES-NICHT") is None


# ---------------------------------------------------------------------------
# Fassungen
# ---------------------------------------------------------------------------


def test_kein_neulauf_solange_gate1_offen(quelle, paket_id):
    quelle.ansicht(paket_id)
    with pytest.raises(NeulaufNichtErlaubt, match="offen"):
        quelle.neu_rechnen(paket_id)


def test_kein_neulauf_nach_freigabe(quelle, ergebnisse, paket_id):
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    entscheiden(gate1, quelle.ansicht(paket_id), "approved")

    with pytest.raises(NeulaufNichtErlaubt, match="freigegeben"):
        quelle.neu_rechnen(paket_id)


def test_nach_reject_entsteht_die_naechste_fassung(quelle, ergebnisse, paket_id):
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    f1 = quelle.ansicht(paket_id)
    f1_konzepte = {k["kontext"]["kp_id"]: k["konzept_id"]
                   for k in ergebnisse.letzter(paket_id).konzepte}
    entscheiden(gate1, f1, "rejected")

    f2 = quelle.neu_rechnen(paket_id)

    assert f2.kopf.fassung == 2
    assert f2.kopf.gate1_status == "pending"
    f2_abgelegt = ergebnisse.letzter(paket_id)
    # Neue Kennung je Fassung, verkettet über die kp_id (ADR-007 · BC2, 2.5).
    for k in f2_abgelegt.konzepte:
        kp = k["kontext"]["kp_id"]
        assert k["konzept_id"] != f1_konzepte[kp]
        assert k["ersetzt_konzept_id"] == f1_konzepte[kp]
    # Die alte Fassung bleibt abrufbar.
    assert [z.beleg.fassung for z in ergebnisse.zeilen[paket_id]] == [1, 2]
    assert ergebnisse.zeilen[paket_id][0].dokument is not None


def test_die_erste_fassung_ersetzt_nichts(quelle, ergebnisse, paket_id):
    quelle.ansicht(paket_id)
    assert all(k["ersetzt_konzept_id"] is None for k in ergebnisse.letzter(paket_id).konzepte)


def test_gate1_haengt_an_der_fassung(quelle, ergebnisse, paket_id):
    """Die neue Fassung hat ihr eigenes Gate 1; das der alten bleibt stehen."""
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    entscheiden(gate1, quelle.ansicht(paket_id), "rejected")
    f2 = quelle.neu_rechnen(paket_id)

    assert gate1.lesen(paket_id, 1).status == "rejected"
    assert gate1.lesen(paket_id, 2) is None
    entscheiden(gate1, f2, "approved")
    assert gate1.lesen(paket_id, 2).status == "approved"


# ---------------------------------------------------------------------------
# Gate 1: Endgültigkeit und Zerlegung
# ---------------------------------------------------------------------------


def test_gate1_ist_nach_abschluss_endgueltig(quelle, ergebnisse, paket_id):
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    ansicht = quelle.ansicht(paket_id)
    entscheiden(gate1, ansicht, "approved")

    with pytest.raises(Gate1Konflikt) as fehler:
        entscheiden(gate1, ansicht, "rejected")
    assert fehler.value.bisher == "approved"
    assert gate1.lesen(paket_id).status == "approved"


def test_ein_entwurf_bleibt_ueberschreibbar(quelle, ergebnisse, paket_id):
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    ansicht = quelle.ansicht(paket_id)
    entscheiden(gate1, ansicht, "pending")
    entscheiden(gate1, ansicht, "approved")
    assert gate1.lesen(paket_id).status == "approved"
    # Ein Entwurf schliesst den Lauf nicht ab, die Freigabe schon.
    assert ergebnisse.letzter(paket_id).beleg.zustand == "abgeschlossen"


def test_zeilen_aus_traegt_die_reihenfolge_als_rang():
    """Die Reihenfolgen liegen als Rang, nicht als Liste (ADR-008 · BC2, 2.3)."""
    e = Gate1Entscheidung(
        paket_id="P",
        company_id="C",
        status="approved",
        approved_potenzial_ids=("A", "C"),
        nicht_freigegeben=(NichtFreigegeben("B", "Zu teuer."),),
        finale_reihenfolge_potenzial_ids=("C", "A", "B"),
        finale_prozessreihenfolge_kp_ids=("KP-2", "KP-1"),
    )
    potenziale, prozesse = zeilen_aus(e)

    nach_id = {z["potenzial_id"]: z for z in potenziale}
    assert nach_id["C"] == {"potenzial_id": "C", "freigegeben": True,
                            "begruendung": None, "finaler_rang": 1}
    assert nach_id["B"]["freigegeben"] is False
    assert nach_id["B"]["begruendung"] == "Zu teuer."
    assert nach_id["B"]["finaler_rang"] == 3
    assert prozesse == [{"kp_id": "KP-2", "finaler_rang": 1},
                        {"kp_id": "KP-1", "finaler_rang": 2}]


def test_ohne_gesetzte_folge_bleibt_der_rang_leer():
    """Leer heisst im Vertrag „es gilt der gerechnete Rang“ — eine Zahl hiesse etwas anderes."""
    e = Gate1Entscheidung(paket_id="P", company_id="C", status="approved",
                          approved_potenzial_ids=("A", "B"))
    potenziale, prozesse = zeilen_aus(e)
    assert all(z["finaler_rang"] is None for z in potenziale)
    assert prozesse == []


def test_dokumente_verketten_nur_ueber_dieselbe_kp_id(quelle, ergebnisse, paket_id):
    ansicht = quelle.ansicht(paket_id)
    abgelegt = ergebnisse.letzter(paket_id)
    vorige = [{**abgelegt.konzepte[0], "kontext": {"kp_id": "KP-ANDERS"}}]

    _, konzepte = dokumente_aus_ansicht(ansicht, abgelegt.beleg, vorige_konzepte=vorige)
    assert all(k["ersetzt_konzept_id"] is None for k in konzepte)


# ---------------------------------------------------------------------------
# Über die Oberfläche
# ---------------------------------------------------------------------------


@pytest.fixture
def ablage_client(buch, quelle, ergebnisse):
    from fastapi.testclient import TestClient

    from app import erzeuge_app

    with TestClient(
        erzeuge_app(buch, laufquelle=quelle,
                    gate1_buch=SpeicherGate1Buch(ergebnisse=ergebnisse))
    ) as c:
        yield c


def _freigeben(lauf: dict) -> dict:
    return {"status": "approved", "entscheider": "Test",
            "approved_potenzial_ids": [e["potenzial_id"] for e in lauf["eintraege"]],
            "fassung": lauf["kopf"]["fassung"]}


def test_neu_rechnen_nur_nach_reject(ablage_client, kopf, paket_id):
    basis = f"/api/oberflaeche/laeufe/{paket_id}"
    lauf = ablage_client.get(basis, headers=kopf).json()

    assert ablage_client.post(f"{basis}/neu", headers=kopf).status_code == 409

    abgelehnt = ablage_client.post(
        f"{basis}/gate1", headers=kopf,
        json={"status": "rejected", "kommentar": "Schnitt zu grob.", "fassung": 1},
    )
    assert abgelehnt.status_code == 200

    neu = ablage_client.post(f"{basis}/neu", headers=kopf)
    assert neu.status_code == 201
    assert neu.json()["kopf"]["fassung"] == 2
    assert neu.json()["gate1"] == {"status": "pending"}

    # Und die Seite zeigt ab jetzt Fassung 2, offen.
    erneut = ablage_client.get(basis, headers=kopf).json()
    assert erneut["kopf"]["fassung"] == 2
    assert erneut["gate1"]["status"] == "pending"
    zeile = next(z for z in ablage_client.get("/api/oberflaeche/laeufe", headers=kopf)
                 .json()["laeufe"] if z["paket_id"] == paket_id)
    assert (zeile["fassung"], zeile["gate1_status"]) == (2, "pending")
    assert lauf["kopf"]["fassung"] == 1


def test_eine_entscheidung_ueber_eine_alte_fassung_ist_ein_konflikt(
    ablage_client, kopf, paket_id
):
    basis = f"/api/oberflaeche/laeufe/{paket_id}"
    f1 = ablage_client.get(basis, headers=kopf).json()
    ablage_client.post(f"{basis}/gate1", headers=kopf,
                       json={"status": "rejected", "kommentar": "Schnitt zu grob."})
    ablage_client.post(f"{basis}/neu", headers=kopf)

    veraltet = ablage_client.post(f"{basis}/gate1", headers=kopf, json=_freigeben(f1))
    assert veraltet.status_code == 409
    assert "Fassung 2" in veraltet.json()["fehler"]


def test_nach_freigabe_kein_neulauf_ueber_die_oberflaeche(ablage_client, kopf, paket_id):
    basis = f"/api/oberflaeche/laeufe/{paket_id}"
    lauf = ablage_client.get(basis, headers=kopf).json()
    assert ablage_client.post(f"{basis}/gate1", headers=kopf,
                              json=_freigeben(lauf)).status_code == 200

    abgewiesen = ablage_client.post(f"{basis}/neu", headers=kopf)
    assert abgewiesen.status_code == 409
    assert "neues Paket" in abgewiesen.json()["fehler"]


def test_zustand_meldet_den_neulauf(ablage_client, kopf):
    assert ablage_client.get("/api/oberflaeche/zustand", headers=kopf).json()["neulauf"] is True


def test_ohne_ablage_gibt_es_keinen_neulauf(client, kopf, paket_id):
    """Die nackte Messsatzquelle kennt keine Fassungen."""
    antwort = client.post(f"/api/oberflaeche/laeufe/{paket_id}/neu", headers=kopf)
    assert antwort.status_code == 501


# ---------------------------------------------------------------------------
# Auflage ADR-009 · BC2 §4.3 — Vorgänger-Kandidaten brechen ab
# ---------------------------------------------------------------------------


def _zwei_pakete(innen, *, zweite_company: str | None = None):
    """Zwei Pakete über dieselben Teilprozesse — der Normalfall nach einer Nacherhebung."""
    from laeufe import SpeicherLaufquelle

    vorlage = innen.ansicht(innen.uebersicht()[0].paket_id)
    a = replace(vorlage, kopf=replace(vorlage.kopf, paket_id="PAKET-A"))
    b = replace(vorlage, kopf=replace(
        vorlage.kopf, paket_id="PAKET-B", company_id=zweite_company or vorlage.kopf.company_id
    ))
    return SpeicherLaufquelle([a, b])


def test_ein_lauf_mit_vorgaenger_kandidaten_bricht_ab(innen, ergebnisse):
    from ablage import NachfolgerOffen

    quelle = AblegendeLaufquelle(_zwei_pakete(innen), ergebnisse)
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    entscheiden(gate1, quelle.ansicht("PAKET-A"), "approved")

    with pytest.raises(NachfolgerOffen) as fehler:
        quelle.ansicht("PAKET-B")
    assert {k["paket_id"] for k in fehler.value.kandidaten} == {"PAKET-A"}
    assert "#295" in str(fehler.value)
    # Kein stilles []: der Lauf liegt als gescheitert da, ohne Ergebnis.
    b = ergebnisse.letzter("PAKET-B")
    assert b.beleg.zustand == "fehler"
    assert b.dokument is None


def test_abgelehnte_fassungen_sind_keine_kandidaten(innen, ergebnisse):
    quelle = AblegendeLaufquelle(_zwei_pakete(innen), ergebnisse)
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    entscheiden(gate1, quelle.ansicht("PAKET-A"), "rejected")

    assert quelle.ansicht("PAKET-B").kopf.fassung == 1


def test_offene_laeufe_sind_keine_kandidaten(innen, ergebnisse):
    quelle = AblegendeLaufquelle(_zwei_pakete(innen), ergebnisse)
    quelle.ansicht("PAKET-A")
    assert quelle.ansicht("PAKET-B") is not None


def test_kandidaten_gelten_nur_im_selben_mandanten(innen, ergebnisse):
    quelle = AblegendeLaufquelle(_zwei_pakete(innen, zweite_company="ANDERER"), ergebnisse)
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    entscheiden(gate1, quelle.ansicht("PAKET-A"), "approved")

    assert quelle.ansicht("PAKET-B") is not None


def test_der_abbruch_kommt_als_409_an(innen, ergebnisse, buch, kopf):
    from fastapi.testclient import TestClient

    from app import erzeuge_app

    quelle = AblegendeLaufquelle(_zwei_pakete(innen), ergebnisse)
    gate1 = SpeicherGate1Buch(ergebnisse=ergebnisse)
    entscheiden(gate1, quelle.ansicht("PAKET-A"), "approved")

    with TestClient(erzeuge_app(buch, laufquelle=quelle, gate1_buch=gate1)) as c:
        antwort = c.get("/api/oberflaeche/laeufe/PAKET-B", headers=kopf)
    assert antwort.status_code == 409
    assert antwort.json()["kandidaten"]


# ---------------------------------------------------------------------------
# Vertrag v3.1 durch die Ablage (#254, ADR-009 · BC2 §2.7)
# ---------------------------------------------------------------------------


def test_ausgangslage_und_vertragskonzepte_gehen_durch_die_ablage(innen, ergebnisse):
    """Trägt die Quelle Ausgangslage und Vertragskonzepte (#288), liegt v3.1."""
    from laeufe import SpeicherLaufquelle

    vorlage = innen.ansicht(innen.uebersicht()[0].paket_id)
    erstes = vorlage.eintraege[0]
    ausgangslage = {"unternehmen": {"name": "NoroAI Consulting"}}
    vertrag = [{
        "konzept_id": "platzhalter",
        "kontext": {"kp_id": erstes["kp_id"], "prozess_kurzbeschreibung": "Kurz."},
        "potenziale": [{"potenzial_id": erstes["potenzial_id"], "beschreibung": "Vom LLM."}],
    }]
    quelle = AblegendeLaufquelle(
        SpeicherLaufquelle([replace(vorlage, ausgangslage=ausgangslage, konzepte=vertrag)]),
        ergebnisse,
    )

    ansicht = quelle.ansicht(vorlage.kopf.paket_id)
    dok = ergebnisse.letzter(vorlage.kopf.paket_id).dokument

    assert dok["schema_version"] == "3.1"
    assert dok["ausgangslage"] == ausgangslage
    assert dok["gestrichene_potenziale"] == []
    assert ansicht.ausgangslage == ausgangslage

    konzept = next(k for k in ansicht.konzepte if k["kontext"]["kp_id"] == erstes["kp_id"])
    assert konzept["konzept_id"] != "platzhalter"
    assert konzept["kontext"]["prozess_kurzbeschreibung"] == "Kurz."
    pot = next(p for p in konzept["potenziale"] if p["potenzial_id"] == erstes["potenzial_id"])
    # Beide Hälften: das Urteil des LLM und die Rechnung.
    assert pot["beschreibung"] == "Vom LLM."
    assert "potenzialrang" in pot
    assert all(p["ersetzt_potenzial_ids"] == [] for k in ansicht.konzepte for p in k["potenziale"])


def test_ein_messsatz_bleibt_bei_3_0(quelle, ergebnisse, paket_id):
    """Ohne Ausgangslage kein 3.1 — und damit auch keine erfundene leere Kette."""
    ansicht = quelle.ansicht(paket_id)
    dok = ergebnisse.letzter(paket_id).dokument

    assert dok["schema_version"] == "3.0"
    assert "gestrichene_potenziale" not in dok
    assert all("ersetzt_potenzial_ids" not in p
               for k in ansicht.konzepte for p in k["potenziale"])
    assert all(z["ersetzt_potenzial_ids"] is None
               for z in potenzialzeilen(dok, ergebnisse.letzter(paket_id).konzepte))
