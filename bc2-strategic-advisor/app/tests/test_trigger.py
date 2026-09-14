"""
Der Trigger-Endpunkt gegen die Zusagen aus #190.

Jeder Test prüft **eine** Zeile der Entscheidungstabelle. Wer sie ändert, sieht
hier, was daran hing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
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


@pytest.mark.parametrize("fehlend", ["paket_id", "company_id", "uebergeben_am"])
def test_fehlendes_pflichtfeld_gibt_400_mit_klartext(client, kopf, paket, fehlend):
    del paket[fehlend]
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 400
    # Der Klartext nennt das Feld beim Namen — wer den 400 bekommt, soll nicht
    # raten muessen.
    assert fehlend in a.json()["fehler"]


def test_fehlende_teilprozesse_sind_kein_fehler(client, kopf, paket):
    """BC0 schickt den Zuschnitt nicht mit — und muss es auch nicht.

    Die Liste steht in ``v_uebergabe_offen`` und wird über die ``paket_id`` von
    dort gelesen. Sie in der Nachricht zu verlangen hiesse, fremden Zustand zu
    doppeln (ADR-003 Regel 4). Vor dem 10.09.2026 war sie Pflicht — daran waere
    BC0s erster echter Ruf mit ``400`` gescheitert.
    """
    del paket["teilprozesse"]
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 202


def test_leere_teilprozessliste_ist_wie_keine(client, kopf, paket):
    """Eine leere Liste trägt keine Angabe — und wird darum nicht abgewiesen.

    Ein leeres Paket kann BC0 ohnehin nicht schnüren, das verhindert dort eine
    ``check_violation``. Hier deshalb kein zweiter Wächter.
    """
    paket["teilprozesse"] = []
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 202


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


# ------------------------------------------------- BC0s Ruf, wie er ihn baut
#
# Nachgezogen am 10.09.2026 an BC0s Commit 9ddda89 („Ruf an BC2"). Gegen den
# Stand davor waere jeder dieser Rufe gescheitert: 401 mangels Bearer, 400
# mangels teilprozesse, 400 am Postgres-Zeitstempel. Darum stehen sie hier.


def _bc0_ruf(nutzlast: dict, geheimnis: str, stempel: int | None = None):
    """Baut den Ruf **genau** wie BC0 (``bc0-.../app.py:4366-4378``).

    Kompaktes JSON mit sortierten Schlüsseln, Signatur über
    ``stempel + "." + rumpf``. Die Bytes gehen so über die Leitung — wer sie
    neu serialisiert, bekommt eine andere Signatur.
    """
    rumpf = json.dumps(nutzlast, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ts = str(int(time.time()) if stempel is None else stempel)
    unterschrift = hmac.new(
        geheimnis.encode("utf-8"), ts.encode("utf-8") + b"." + rumpf, hashlib.sha256
    ).hexdigest()
    return rumpf, {
        "Content-Type": "application/json",
        "User-Agent": "BC0/3.1",
        "X-BC0-Timestamp": ts,
        "X-BC0-Signature": "sha256=" + unterschrift,
    }


@pytest.fixture
def bc0_nutzlast() -> dict:
    """Was BC0 wirklich schickt: vier Felder, keine Teilprozesse.

    ``uebergeben_am`` in Postgres-Schreibweise — Leerzeichen statt ``T``,
    zweistelliger Zonenversatz. BC0 reicht ``uebergeben_am::text`` durch.
    """
    return {
        "ereignis": "paket_uebergeben",
        "company_id": "7c2d5ee9-2a9a-5990-810f-502ea2b2012d",
        "paket_id": "b1f4c0de-5a2e-4f77-9a31-8c6d1e0b7a44",
        "uebergeben_am": "2026-09-10 14:32:11.123456+02",
    }


def test_bc0s_echter_ruf_wird_angenommen(client, token, bc0_nutzlast, buch):
    """Der Ruf, den BC0 heute baut — Signatur, nur Kennungen, Postgres-Stempel."""
    rumpf, kopf = _bc0_ruf(bc0_nutzlast, token)
    a = client.post("/api/bc0/uebergabe", content=rumpf, headers=kopf)

    assert a.status_code == 202, a.text
    assert a.json()["status"] == "angenommen"
    abgelegt = buch.abgelegt[bc0_nutzlast["paket_id"]]
    # Roh aufgehoben, samt ereignis — das Feld kennt der Vertrag, ausgewertet
    # wird es nicht.
    assert abgelegt.nutzlast == bc0_nutzlast
    assert abgelegt.uebergeben_am.utcoffset().total_seconds() == 2 * 3600


def test_bc0s_doppelanstoss_bleibt_harmlos(client, token, bc0_nutzlast):
    for erwartet in ("angenommen", "bereits_angenommen"):
        rumpf, kopf = _bc0_ruf(bc0_nutzlast, token)
        a = client.post("/api/bc0/uebergabe", content=rumpf, headers=kopf)
        assert a.status_code == 202
        assert a.json()["status"] == erwartet


def test_veraenderter_rumpf_bricht_die_signatur(client, token, bc0_nutzlast):
    """Genau wofür die Signatur da ist: der Rumpf ist mitgeprüft."""
    rumpf, kopf = _bc0_ruf(bc0_nutzlast, token)
    verbogen = rumpf.replace(b"paket_uebergeben", b"paket_zurueckgezogen")
    assert verbogen != rumpf

    a = client.post("/api/bc0/uebergabe", content=verbogen, headers=kopf)
    assert a.status_code == 401


def test_signatur_mit_falschem_geheimnis_gibt_401(client, bc0_nutzlast):
    rumpf, kopf = _bc0_ruf(bc0_nutzlast, "ein-anderes-geheimnis")
    a = client.post("/api/bc0/uebergabe", content=rumpf, headers=kopf)
    assert a.status_code == 401


def test_alter_ruf_gilt_nicht(client, token, bc0_nutzlast):
    """Ein mitgeschnittener Ruf soll sich nicht beliebig lange wiederholen lassen."""
    rumpf, kopf = _bc0_ruf(bc0_nutzlast, token, stempel=int(time.time()) - 3600)
    a = client.post("/api/bc0/uebergabe", content=rumpf, headers=kopf)
    assert a.status_code == 401


def test_signatur_ohne_zeitstempel_gilt_nicht(client, token, bc0_nutzlast):
    rumpf, kopf = _bc0_ruf(bc0_nutzlast, token)
    del kopf["X-BC0-Timestamp"]
    a = client.post("/api/bc0/uebergabe", content=rumpf, headers=kopf)
    assert a.status_code == 401


def test_ohne_signatur_wird_nichts_abgelegt(client, bc0_nutzlast, buch):
    rumpf = json.dumps(bc0_nutzlast).encode("utf-8")
    a = client.post(
        "/api/bc0/uebergabe", content=rumpf, headers={"Content-Type": "application/json"}
    )
    assert a.status_code == 401
    assert buch.abgelegt == {}


# ----------------------------------------------------- Postgres-Zeitstempel


@pytest.mark.parametrize(
    "roh,erwarteter_versatz_h",
    [
        ("2026-09-10 14:32:11.123456+02", 2),   # so schickt BC0 es
        ("2026-09-10 14:32:11+02", 2),          # ohne Bruchsekunden
        ("2026-09-10 14:32:11.12+02", 2),       # gekuerzte Bruchsekunden
        ("2026-09-10 14:32:11+0200", 2),        # Versatz ohne Doppelpunkt
        ("2026-09-10T14:32:11+02:00", 2),       # RFC 3339, unveraendert gueltig
        ("2026-09-10T14:32:11Z", 0),            # Zulu
        ("2026-09-10 12:32:11+00", 0),          # UTC zweistellig
    ],
)
def test_zeitstempel_schreibweisen(roh, erwarteter_versatz_h):
    """Was Postgres ausgibt, muss BC2 lesen — unabhängig von der Python-Version.

    ``fromisoformat`` nimmt Leerzeichen und zweistelligen Versatz erst ab 3.11.
    Der Container läuft auf 3.12, die Prüfung hier auf dem, was gerade da ist —
    darum wird ausdrücklich normalisiert statt auf Nachsicht gehofft.
    """
    from app import iso_normalisieren

    gelesen = datetime.fromisoformat(iso_normalisieren(roh))
    assert gelesen.utcoffset().total_seconds() == erwarteter_versatz_h * 3600


def test_postgres_zeitstempel_kommt_durch_den_endpunkt(client, kopf, paket):
    paket["uebergeben_am"] = "2026-09-10 14:32:11.123456+02"
    a = client.post("/api/bc0/uebergabe", json=paket, headers=kopf)
    assert a.status_code == 202, a.text


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
