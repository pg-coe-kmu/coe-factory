"""
Der Trigger-Endpunkt gegen die Zusagen aus #190.

Jeder Test prüft **eine** Zeile der Entscheidungstabelle. Wer sie ändert, sieht
hier, was daran hing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from eingang import Paket

VERTRAG = (
    Path(__file__).resolve().parents[3] / "contracts" / "bc0-to-bc2" / "trigger.schema.json"
)


# ---------------------------------------------------------------- Zusage: 202


def test_gueltiges_paket_wird_mit_202_quittiert(client, kopf, paket):
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 202, a.text
    assert a.json() == {"paket_id": "PKT-2026-0007", "status": "angenommen"}


def test_paket_landet_roh_in_der_ablage(client, kopf, paket, buch):
    paket["ein_feld_das_bc2_nicht_kennt"] = {"beliebig": [1, 2, 3]}
    client.post("/api/bc0/uebergabe", json=paket, headers=kopf)

    abgelegt = buch.abgelegt["PKT-2026-0007"]
    assert abgelegt.company_id == "NOROAI"
    assert abgelegt.quelle == "push"
    # Tolerant: das unbekannte Feld wird nicht abgeschnitten, sondern aufgehoben.
    assert abgelegt.nutzlast["ein_feld_das_bc2_nicht_kennt"] == {"beliebig": [1, 2, 3]}


def test_unbekannte_felder_fuehren_nicht_zu_400(client, kopf, paket):
    """Der Endpunkt ist tolerant — BC0 darf ergaenzen, ohne zu fragen."""
    paket["bc1_profil_stand"] = "v7"
    paket["voellig_neu"] = "egal"
    assert client.post("/api/bc0/uebergabe", json=paket, headers=kopf).status_code == 202


# --------------------------------------------------------- Zusage: Idempotenz


def test_doppelanstoss_ist_harmlos(client, kopf, paket, buch):
    erste = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    zweite = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)

    assert erste.json()["status"] == "angenommen"
    # Wieder 202, kein 409: das zwaenge BC0 zu einer Sonderbehandlung fuer einen
    # Fall, der keiner ist.
    assert zweite.status_code == 202
    assert zweite.json()["status"] == "bereits_angenommen"
    assert len(buch.abgelegt) == 1


def test_zweiter_anstoss_ueberschreibt_nichts(client, kopf, paket, buch):
    client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    veraendert = dict(paket, company_id="EIN-ANDERER", teilprozesse=["KP-99.TP-9"])
    client.post("/api/bc0/uebergabe", json=veraendert, headers=kopf)

    # Was zuerst kam, bleibt stehen. Das Eingangsprotokoll ist ein Protokoll.
    assert buch.abgelegt["PKT-2026-0007"].company_id == "NOROAI"


# ------------------------------------------------------------ Zusage: 400/401


@pytest.mark.parametrize("fehlend", ["paket_id", "company_id", "uebergeben_am", "teilprozesse"])
def test_fehlendes_pflichtfeld_gibt_400_mit_klartext(client, kopf, paket, fehlend):
    del paket[fehlend]
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 400
    # Der Klartext nennt das Feld beim Namen — wer den 400 bekommt, soll nicht
    # raten muessen.
    assert fehlend in a.json()["fehler"]


def test_leere_teilprozessliste_gibt_400(client, kopf, paket):
    paket["teilprozesse"] = []
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 400
    assert "teilprozesse" in a.json()["fehler"]


def test_unbrauchbarer_zeitstempel_gibt_400(client, kopf, paket):
    paket["uebergeben_am"] = "gestern nachmittag"
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 400
    assert "uebergeben_am" in a.json()["fehler"]


def test_zeitstempel_mit_z_wird_angenommen(client, kopf, paket):
    """Python vor 3.11 stolpert ueber das abschliessende Z — der Endpunkt nicht."""
    paket["uebergeben_am"] = "2026-09-10T12:32:11Z"
    assert client.post("/api/bc0/uebergabe", json=paket, headers=kopf).status_code == 202


def test_kein_schluessel_gibt_401(client, paket):
    a = client.post("/api/bc0/uebergabe", json=paket)
    assert a.status_code == 401


def test_falscher_schluessel_gibt_401(client, paket):
    a = client.post(
        "/api/bc0/uebergabe", json=paket, headers={"Authorization": "Bearer falsch"}
    )
    assert a.status_code == 401


def test_ohne_schluessel_wird_nichts_abgelegt(client, paket, buch):
    """Die Pruefung steht vor der Ablage, nicht daneben."""
    client.post("/api/bc0/uebergabe", json=paket)
    assert buch.abgelegt == {}


def test_schluessel_im_falschen_header_zaehlt_nicht(client, paket, token):
    a = client.post("/api/bc0/uebergabe", json=paket, headers={"X-API-Key": token})
    assert a.status_code == 401


# -------------------------------------------------------------- Zusage: 503


def test_ablage_nicht_erreichbar_gibt_503(client, kopf, paket, buch):
    """503 und nicht 500 — nur beim ersten lohnt BC0 ein neuer Versuch."""
    buch.antwortet = False
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 503


# ------------------------------------------------------- Nachhol-Abgleich


def _offenes_paket(pid: str) -> Paket:
    return Paket(
        paket_id=pid,
        company_id="NOROAI",
        uebergeben_am=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
        nutzlast={"paket_id": pid, "company_id": "NOROAI", "teilprozesse": ["KP-02.TP-1"]},
        quelle="nachgeholt",
    )


def test_abgleich_holt_nach_was_der_push_nicht_brachte(client, kopf, buch):
    buch.offen = [_offenes_paket("PKT-A"), _offenes_paket("PKT-B")]

    a = client.post("/api/intern/abgleich", headers=kopf)
    assert a.status_code == 200
    assert a.json()["nachgeholt"] == 2
    assert set(buch.abgelegt) == {"PKT-A", "PKT-B"}
    assert buch.abgelegt["PKT-A"].quelle == "nachgeholt"


def test_abgleich_holt_nichts_doppelt(client, kopf, paket, buch):
    client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    buch.offen = [_offenes_paket("PKT-2026-0007")]  # dasselbe Paket noch einmal

    a = client.post("/api/intern/abgleich", headers=kopf)
    assert a.json()["nachgeholt"] == 0
    # Der Push-Eintrag bleibt Push — er wird nicht als nachgeholt umgeschrieben.
    assert buch.abgelegt["PKT-2026-0007"].quelle == "push"


def test_abgleich_braucht_den_schluessel(client, buch):
    buch.offen = [_offenes_paket("PKT-A")]
    assert client.post("/api/intern/abgleich").status_code == 401
    assert buch.abgelegt == {}


def test_start_holt_offene_pakete_nach(kopf):
    """Was eintraf, waehrend BC2 aus war, ist nach dem Start da."""
    from fastapi.testclient import TestClient

    from app import erzeuge_app
    from eingang import SpeicherEingangsbuch

    b = SpeicherEingangsbuch(offen=[_offenes_paket("PKT-WAEHREND-AUS")])
    with TestClient(erzeuge_app(b)):
        pass
    assert "PKT-WAEHREND-AUS" in b.abgelegt


def test_start_laeuft_auch_wenn_die_datenbank_schweigt():
    """Der Push ist der Hauptweg — ein gescheiterter Abgleich darf ihn nicht verhindern."""
    from fastapi.testclient import TestClient

    from app import erzeuge_app
    from eingang import SpeicherEingangsbuch

    b = SpeicherEingangsbuch(antwortet=False)
    with TestClient(erzeuge_app(b)) as c:
        assert c.get("/health").status_code == 200


# ------------------------------------------------------------------ Sonstiges


def test_health_braucht_keinen_schluessel(client):
    a = client.get("/health")
    assert a.status_code == 200
    assert a.json() == {"status": "ok"}


def test_health_verraet_nichts_ueber_die_datenbank(client, buch):
    """Sonst waere der Zustand der gemeinsamen Datenbank ohne Anmeldung ablesbar."""
    buch.antwortet = False
    a = client.get("/health")
    assert a.status_code == 200
    assert "datenbank" not in a.text.lower()


def test_bereitschaft_meldet_die_datenbank_nur_mit_schluessel(client, kopf, buch):
    assert client.get("/api/intern/bereit").status_code == 401

    assert client.get("/api/intern/bereit", headers=kopf).status_code == 200
    buch.antwortet = False
    assert client.get("/api/intern/bereit", headers=kopf).status_code == 503


# --------------------------------------------------- Vertrag und Wirklichkeit


def test_die_beispiele_im_vertrag_werden_auch_angenommen(client, kopf):
    """Was im Schema als Beispiel steht, muss durch den echten Endpunkt gehen.

    Sonst haette BC0 ein Papier, das der Dienst nicht einloest — genau die
    Sorte Widerspruch, an der diese Karte schon dreimal haengengeblieben ist.
    """
    schema = json.loads(VERTRAG.read_text(encoding="utf-8"))
    for i, beispiel in enumerate(schema["examples"]):
        a = client.post("/api/bc0/uebergabe", json=beispiel, headers=kopf)
        assert a.status_code == 202, f"Beispiel {i} abgewiesen: {a.text}"


def test_die_beispiele_im_vertrag_passen_zum_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(VERTRAG.read_text(encoding="utf-8"))
    for i, beispiel in enumerate(schema["examples"]):
        jsonschema.validate(beispiel, schema)


def test_pflichtfelder_stimmen_mit_dem_vertrag_ueberein():
    """Code und Schema duerfen nicht auseinanderlaufen."""
    from app import PFLICHTFELDER

    schema = json.loads(VERTRAG.read_text(encoding="utf-8"))
    assert set(PFLICHTFELDER) == set(schema["required"])
