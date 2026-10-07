"""B4: Meldungen an BC0 — Zugang, Melder, Fehlersätze, Live-Probe.

Kein Netz: BC0 wird mit httpx.MockTransport nachgebaut (Endpunkte und Antworten wie
bc0_auth/routen.py und app.py v3.12, nachgelesen 06.10.2026).
"""
import json
import logging

import httpx
import pytest

from bc1_service.bc0_meldungen import (
    MELDUNG_ANMELDUNG_ABGELEHNT,
    MELDUNG_ANTWORT,
    MELDUNG_AUS,
    MELDUNG_GESPERRT,
    MELDUNG_KEIN_HTTPS,
    MELDUNG_KEIN_SCHREIBRECHT,
    MELDUNG_MANDANT_UNBEKANNT,
    MELDUNG_NICHT_ERREICHBAR,
    MELDUNG_SCHALTER_UNBEKANNT,
    MELDUNG_SITZUNG_NICHT_ANGENOMMEN,
    MELDUNG_ZUGANG_UNVOLLSTAENDIG,
    ZEITLIMIT_SEKUNDEN,
    Bc0MeldungFehler,
    Bc0Melder,
    Bc0Zugang,
    baue_melder,
    lies_bc0_zugang,
    probe,
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


ANFRAGE = "A-2026-01"


def _eigene(caplog, logger="bc1_service.bc0_meldungen"):
    return [r.getMessage() for r in caplog.records if r.name == logger]


def test_baue_melder_beim_aus_liefert_none_und_warnt(caplog):
    with caplog.at_level(logging.WARNING, logger="bc1_service.bc0_meldungen"):
        assert baue_melder({"BC1_BC0_MELDUNGEN": "aus"}, MANDANT) is None
    assert _eigene(caplog) == [MELDUNG_AUS]


def test_baue_melder_mit_zugang_liefert_einen_melder_ohne_warnung(caplog):
    with caplog.at_level(logging.WARNING, logger="bc1_service.bc0_meldungen"):
        assert isinstance(baue_melder(VOLL, MANDANT), Bc0Melder)
    assert _eigene(caplog) == []


def test_baue_melder_reicht_konfigurationsfehler_durch():
    with pytest.raises(RuntimeError, match="BC0-Zugang unvollständig"):
        baue_melder({}, MANDANT)


COOKIE = "bc0_sitzung=schluessel-1; HttpOnly; Secure; Path=/; SameSite=lax"


class FakeBc0:
    """BC0 im Kleinen: Login setzt das Cookie, die Fachaufrufe verlangen es.

    `login` / `aktion` ersetzen die Antwort des jeweiligen Schritts (Funktion
    request -> Response, darf auch eine httpx-Ausnahme werfen)."""

    def __init__(self, *, login=None, aktion=None, konto=None):
        self.anfragen: list[httpx.Request] = []
        self._login = login
        self._aktion = aktion
        self.konto = konto or {"rolle": "benutzer", "ist_admin": False,
                               "darf_schreiben": True, "mandanten": [MANDANT]}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.anfragen.append(request)
        if request.url.path == "/api/auth/login":
            if self._login is not None:
                return self._login(request)
            return httpx.Response(200, json={"ok": True}, headers={"set-cookie": COOKIE})
        if self._aktion is not None:
            return self._aktion(request)
        if request.headers.get("cookie") != "bc0_sitzung=schluessel-1":
            return httpx.Response(401, json={"detail": "Nicht angemeldet."})
        if request.url.path.endswith("/gate_nachziehen"):
            return httpx.Response(200, json={"geprueft": 2, "gesetzt": [ANFRAGE],
                                             "anfragen": []})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"ok": True, "anfrage_id": ANFRAGE,
                                             "status_alt": "zugeordnet",
                                             "status": "im_interview"})
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=self.konto)
        return httpx.Response(404, json={"detail": "Not Found"})


def _melder(bc0, url="https://bc0.example.org"):
    zugang = lies_bc0_zugang({**VOLL, "BC1_BC0_URL": url})
    return Bc0Melder(zugang, MANDANT, transport=httpx.MockTransport(bc0))


def test_anmeldung_schickt_email_und_passwort_unveraendert():
    bc0 = FakeBc0()
    _melder(bc0).melde_interview_laeuft(ANFRAGE)
    login = bc0.anfragen[0]
    assert login.method == "POST" and login.url.path == "/api/auth/login"
    assert json.loads(login.content) == {"email": "dienst@example.org", "passwort": PASSWORT}


def test_interview_laeuft_setzt_den_status_mit_cookie():
    bc0 = FakeBc0()
    _melder(bc0).melde_interview_laeuft(ANFRAGE)
    status = bc0.anfragen[1]
    assert status.method == "PUT"
    assert status.url.path == f"/api/companies/{MANDANT}/anfragen/{ANFRAGE}/status"
    assert json.loads(status.content) == {"status": "im_interview"}
    assert status.headers["cookie"] == "bc0_sitzung=schluessel-1"


def test_gate_nachziehen_liefert_die_gesetzten_anfragen():
    bc0 = FakeBc0()
    assert _melder(bc0).ziehe_gate_nach() == [ANFRAGE]
    gate = bc0.anfragen[1]
    assert gate.method == "POST"
    assert gate.url.path == f"/api/companies/{MANDANT}/anfragen/gate_nachziehen"


def test_gate_ohne_gesetzte_anfragen_auch_bei_null():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(
        200, json={"geprueft": 0, "gesetzt": None, "anfragen": []}))
    assert _melder(bc0).ziehe_gate_nach() == []


def test_gate_antwort_ohne_gesetzt_gilt_als_leer():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(200, json={"geprueft": 0}))
    assert _melder(bc0).ziehe_gate_nach() == []


def test_konto_lesen_liefert_die_antwort_von_auth_me():
    bc0 = FakeBc0()
    assert _melder(bc0).lies_konto() == bc0.konto
    konto = bc0.anfragen[1]
    assert konto.method == "GET" and konto.url.path == "/api/auth/me"


def test_jede_meldung_meldet_sich_frisch_an():
    bc0 = FakeBc0()
    melder = _melder(bc0)
    melder.melde_interview_laeuft(ANFRAGE)
    melder.ziehe_gate_nach()
    pfade = [a.url.path for a in bc0.anfragen]
    assert pfade.count("/api/auth/login") == 2


def test_zeitlimit_ist_zehn_sekunden():
    bc0 = FakeBc0()
    _melder(bc0).ziehe_gate_nach()
    assert ZEITLIMIT_SEKUNDEN == 10
    assert bc0.anfragen[0].extensions["timeout"] == {
        "connect": 10, "read": 10, "write": 10, "pool": 10}


def _ohne_passwort(ausgabe: str) -> None:
    # repr() verdoppelt den Backslash im Passwort, JSON maskiert zusaetzlich das Anfuehrungs-
    # zeichen: neben dem Rohwert auch diese Formen pruefen, sonst waere die Pruefung gegen
    # eine repr- oder JSON-Ausgabe (BC0 schickt den Rumpf als JSON zurueck) falsch-gruen.
    formen = (PASSWORT, repr(PASSWORT)[1:-1],
              json.dumps(PASSWORT)[1:-1], json.dumps(PASSWORT, ensure_ascii=False)[1:-1])
    for form in formen:
        assert form.strip() not in ausgabe


def _fehler(bc0, aufruf="gate", url="https://bc0.example.org") -> Bc0MeldungFehler:
    melder = _melder(bc0, url)
    with pytest.raises(Bc0MeldungFehler) as fehler:
        if aufruf == "gate":
            melder.ziehe_gate_nach()
        else:
            melder.melde_interview_laeuft(ANFRAGE)
    _ohne_passwort(str(fehler.value))
    _ohne_passwort(repr(fehler.value))
    return fehler.value


def test_falsches_passwort():
    bc0 = FakeBc0(login=lambda r: httpx.Response(
        401, json={"detail": "E-Mail-Adresse oder Passwort ist falsch."}))
    assert str(_fehler(bc0)) == MELDUNG_ANMELDUNG_ABGELEHNT


def test_anmeldung_422_gibt_den_zurueckgeschickten_rumpf_nicht_weiter():
    # FastAPI-Standard-422 traegt den Rumpf als "input" — beim Login samt Passwort.
    bc0 = FakeBc0(login=lambda r: httpx.Response(422, json={"detail": [{
        "type": "missing", "loc": ["body", "x"], "msg": "Field required",
        "input": json.loads(r.content)}]}))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Anmeldung", code=422, detail="")


def test_anmeldung_str_detail_mit_abgeschnittenem_passwort_wird_verworfen():
    # Das Kuerzen auf 200 Zeichen darf nur den Anfang des Passworts stehen lassen.
    bc0 = FakeBc0(login=lambda r: httpx.Response(400, json={
        "detail": "x" * 195 + json.loads(r.content)["passwort"]}))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Anmeldung", code=400, detail="")


def test_anmeldung_ohne_json_gibt_keinen_antworttext_weiter():
    bc0 = FakeBc0(login=lambda r: httpx.Response(
        502, text="Gateway: " + json.loads(r.content)["passwort"]))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Anmeldung", code=502, detail="")


def test_anmeldung_str_detail_mit_dem_passwort_wird_verworfen():
    bc0 = FakeBc0(login=lambda r: httpx.Response(400, json={
        "detail": "Ungueltig: " + json.loads(r.content)["passwort"]}))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Anmeldung", code=400, detail="")


@pytest.mark.parametrize("kopf, minuten", [("600", 10), ("20", 1), (None, 1), ("bald", 1)])
def test_gesperrte_anmeldung_nennt_die_wartezeit(kopf, minuten):
    headers = {"Retry-After": kopf} if kopf is not None else {}
    bc0 = FakeBc0(login=lambda r: httpx.Response(
        429, json={"detail": "Zu viele fehlgeschlagene Anmeldeversuche."}, headers=headers))
    assert str(_fehler(bc0)) == MELDUNG_GESPERRT.format(minuten=minuten)


def test_429_beim_fachaufruf_ist_keine_anmeldesperre():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(429, json={"detail": "Zu viele Anfragen."}))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Gate nachziehen", code=429, detail="Zu viele Anfragen.")


@pytest.mark.parametrize("aufruf, aktion", [
    ("status", "Status im_interview"), ("gate", "Gate nachziehen")])
def test_lokales_bc0_ohne_https_nimmt_das_sichere_cookie_nicht_zurueck(aufruf, aktion):
    # Gemessen 06.10.: httpx schickt ein Secure-Cookie nicht ueber http://localhost.
    bc0 = FakeBc0()
    fehler = _fehler(bc0, aufruf=aufruf, url="http://localhost:8000")
    assert str(fehler) == MELDUNG_SITZUNG_NICHT_ANGENOMMEN.format(aktion=aktion)


def test_kein_schreibrecht():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(
        403, json={"detail": "Nur lesender Zugang."}))
    assert str(_fehler(bc0)) == MELDUNG_KEIN_SCHREIBRECHT.format(
        aktion="Gate nachziehen", detail="Nur lesender Zugang.")


def test_mandant_nicht_zugewiesen_kommt_als_404():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(404, json={"detail": "Mandant unbekannt."}))
    assert str(_fehler(bc0, aufruf="status")) == MELDUNG_MANDANT_UNBEKANNT.format(
        company_id=MANDANT)


@pytest.mark.parametrize("code, detail", [
    (404, "Unbekannte Anfrage: A-2026-01"),
    (400, "Rueckschritt von 'am_gate' auf 'im_interview' ist nicht vorgesehen."),
    (500, "Interner Fehler"),
])
def test_andere_absagen_nennen_code_und_detail(code, detail):
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(code, json={"detail": detail}))
    assert str(_fehler(bc0, aufruf="status")) == MELDUNG_ANTWORT.format(
        aktion="Status im_interview", code=code, detail=detail)


def test_antwort_ohne_json_nennt_den_gekuerzten_text():
    seite = "<html>" + "x" * 500 + "</html>"
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(502, text=seite))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Gate nachziehen", code=502, detail=seite[:200])


def test_erfolg_ohne_json_ist_ebenfalls_ein_fehler():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(200, text="<html>Wartung</html>"))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Gate nachziehen", code=200, detail="<html>Wartung</html>")


@pytest.mark.parametrize("code, text", [
    (200, "[1, 2]"),                                   # Erfolg, aber kein JSON-Objekt
    (422, '{"detail": [{"msg": "Feld fehlt"}]}'),      # FastAPI-Validierung: detail ist eine Liste
    (500, '{"fehler": "x"}'),                          # Objekt ohne detail
    (500, '["x"]'),                                    # kein JSON-Objekt
])
def test_json_ohne_detail_text_nennt_den_antworttext(code, text):
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(
        code, content=text, headers={"content-type": "application/json"}))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Gate nachziehen", code=code, detail=text)


def test_weiterleitung_wird_nicht_befolgt():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(
        302, headers={"location": "https://anderswo.example.org/"}))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Gate nachziehen", code=302, detail="")
    assert len(bc0.anfragen) == 2                      # Login + Aufruf, kein Folgen


def _wirft(ausnahme_klasse):
    def antwort(request):
        raise ausnahme_klasse("kaputt", request=request)
    return antwort


@pytest.mark.parametrize("klasse", [httpx.ConnectError, httpx.ReadTimeout])
def test_nicht_erreichbar_beim_login_ohne_verkettung(klasse):
    fehler = _fehler(FakeBc0(login=_wirft(klasse)))
    assert str(fehler) == MELDUNG_NICHT_ERREICHBAR.format(
        url="https://bc0.example.org", art=klasse.__name__)
    # Die httpx-Ausnahme traegt den Login-Rumpf mit dem Passwort — sie darf an der
    # BC1-Ausnahme nicht haengen, weder als Ursache noch als Kontext.
    assert fehler.__cause__ is None and fehler.__context__ is None


def test_nicht_erreichbar_beim_fachaufruf():
    fehler = _fehler(FakeBc0(aktion=_wirft(httpx.ConnectError)))
    assert str(fehler) == MELDUNG_NICHT_ERREICHBAR.format(
        url="https://bc0.example.org", art="ConnectError")


def _probe(konto=None, login=None, umgebung=None):
    zeilen: list[str] = []
    bc0 = FakeBc0(konto=konto, login=login)
    code = probe(umgebung or {**VOLL, "BC1_COMPANY_ID": MANDANT},
                 transport=httpx.MockTransport(bc0), ausgabe=zeilen.append)
    return code, zeilen, bc0


def test_probe_benutzer_mit_mandant_ist_bereit_und_aendert_nichts():
    code, zeilen, bc0 = _probe()
    assert code == 0
    assert zeilen == ["Rolle: benutzer", "Schreibrecht: ja",
                      f"Mandant {MANDANT} sichtbar: ja"]
    assert [a.method for a in bc0.anfragen] == ["POST", "GET"]   # Login + /me, sonst nichts


def test_probe_admin_ohne_mandantenliste_sieht_den_mandanten():
    code, zeilen, _ = _probe(konto={"rolle": "admin", "ist_admin": True,
                                    "darf_schreiben": True, "mandanten": []})
    assert code == 0 and zeilen[2] == f"Mandant {MANDANT} sichtbar: ja"


def test_probe_leser_ist_nicht_bereit():
    code, zeilen, _ = _probe(konto={"rolle": "leser", "ist_admin": False,
                                    "darf_schreiben": False, "mandanten": [MANDANT]})
    assert code == 1 and zeilen[1] == "Schreibrecht: nein"


def test_probe_benutzer_ohne_mandant_ist_nicht_bereit():
    code, zeilen, _ = _probe(konto={"rolle": "benutzer", "ist_admin": False,
                                    "darf_schreiben": True, "mandanten": []})
    assert code == 1 and zeilen[2] == f"Mandant {MANDANT} sichtbar: nein"


def test_probe_mit_falschem_passwort_meldet_den_satz():
    code, zeilen, _ = _probe(login=lambda r: httpx.Response(401, json={"detail": "x"}))
    assert code == 1 and zeilen == [MELDUNG_ANMELDUNG_ABGELEHNT]


def test_probe_ohne_mandant_oder_mit_aus_ist_ein_konfigurationsfehler():
    code, zeilen, _ = _probe(umgebung=dict(VOLL))
    assert code == 2 and "BC1_COMPANY_ID" in zeilen[0]
    code, zeilen, _ = _probe(umgebung={"BC1_BC0_MELDUNGEN": "aus", "BC1_COMPANY_ID": MANDANT})
    assert code == 2 and zeilen == ["BC1_BC0_MELDUNGEN=aus — nichts zu prüfen."]
