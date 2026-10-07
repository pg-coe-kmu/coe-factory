"""B4: Meldungen an BC0 — Zugang, Melder, Fehlersätze, Live-Probe.

Kein Netz: BC0 wird mit httpx.MockTransport nachgebaut (Endpunkte und Antworten wie
bc0_auth/routen.py und app.py v3.12, nachgelesen 06.10.2026).
"""
import pytest

from bc1_service.bc0_meldungen import (
    MELDUNG_KEIN_HTTPS,
    MELDUNG_SCHALTER_UNBEKANNT,
    MELDUNG_ZUGANG_UNVOLLSTAENDIG,
    Bc0Zugang,
    lies_bc0_zugang,
)

MANDANT = "11111111-1111-1111-1111-111111111111"
PASSWORT = ' pa"ss\\wört '            # Rand-Leerzeichen und Sonderzeichen: bleibt unverändert
VOLL = {
    "BC1_BC0_URL": "https://bc0.example.org",
    "BC1_BC0_KONTO_EMAIL": "dienst@example.org",
    "BC1_BC0_KONTO_PASSWORT": PASSWORT,
}


def test_vollstaendiger_zugang_wird_gelesen_und_das_passwort_nicht_beschnitten():
    zugang = lies_bc0_zugang(VOLL)
    assert zugang == Bc0Zugang("https://bc0.example.org", "dienst@example.org", PASSWORT)


def test_passwort_steht_nicht_im_repr():
    ausgabe = repr(lies_bc0_zugang(VOLL))
    assert PASSWORT not in ausgabe
    # repr() verdoppelt den Backslash im Passwort: der Rohwert allein fände auch dann nichts,
    # wenn das Passwort im repr stünde — deshalb zusätzlich die maskierte Form prüfen.
    assert repr(PASSWORT) not in ausgabe


@pytest.mark.parametrize("fehlt", sorted(VOLL))
def test_ein_fehlender_name_bricht_ab_und_wird_genannt(fehlt):
    umgebung = {k: v for k, v in VOLL.items() if k != fehlt}
    with pytest.raises(RuntimeError) as fehler:
        lies_bc0_zugang(umgebung)
    assert str(fehler.value) == MELDUNG_ZUGANG_UNVOLLSTAENDIG.format(namen=fehlt)


def test_alle_fehlenden_namen_stehen_in_einer_meldung():
    with pytest.raises(RuntimeError) as fehler:
        lies_bc0_zugang({"BC1_BC0_KONTO_PASSWORT": "   "})   # nur Leerzeichen = fehlt
    assert str(fehler.value) == MELDUNG_ZUGANG_UNVOLLSTAENDIG.format(
        namen="BC1_BC0_URL, BC1_BC0_KONTO_EMAIL, BC1_BC0_KONTO_PASSWORT")


def test_aus_schalter_liefert_none_auch_ohne_zugang():
    assert lies_bc0_zugang({"BC1_BC0_MELDUNGEN": "aus"}) is None


def test_aus_schalter_gewinnt_auch_bei_vollstaendigem_zugang():
    assert lies_bc0_zugang({**VOLL, "BC1_BC0_MELDUNGEN": " aus "}) is None


@pytest.mark.parametrize("wert", ["AUS", "off", "nein", "0"])
def test_unbekannter_schalter_bricht_ab(wert):
    with pytest.raises(RuntimeError) as fehler:
        lies_bc0_zugang({**VOLL, "BC1_BC0_MELDUNGEN": wert})
    assert str(fehler.value) == MELDUNG_SCHALTER_UNBEKANNT.format(wert=wert)


@pytest.mark.parametrize("url", [
    "http://bc0.example.org",
    "http://localhost.example.org",        # Präfix-Falle: kein localhost
    "ftp://bc0.example.org",
    "https://",                             # kein Rechnername
    "bc0.example.org",
])
def test_unsichere_oder_unvollstaendige_adresse_bricht_ab(url):
    with pytest.raises(RuntimeError) as fehler:
        lies_bc0_zugang({**VOLL, "BC1_BC0_URL": url})
    assert str(fehler.value) == MELDUNG_KEIN_HTTPS.format(url=url)


@pytest.mark.parametrize("url, erwartet", [
    ("http://localhost:8000", "http://localhost:8000"),
    ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
    ("https://bc0.example.org/", "https://bc0.example.org"),
    (" https://bc0.example.org ", "https://bc0.example.org"),
])
def test_erlaubte_adressen_werden_ohne_schraegstrich_am_ende_uebernommen(url, erwartet):
    assert lies_bc0_zugang({**VOLL, "BC1_BC0_URL": url}).url == erwartet


def test_email_wird_beschnitten():
    zugang = lies_bc0_zugang({**VOLL, "BC1_BC0_KONTO_EMAIL": " dienst@example.org\n"})
    assert zugang.email == "dienst@example.org"
