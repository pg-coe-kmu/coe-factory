"""Meldungen von BC1 an BC0 (B4): 'Interview laeuft' und 'Gate nachziehen'.

BC1 meldet sich dafuer mit dem Anwendungskonto an (POST /api/auth/login, Cookie
bc0_sitzung). Je Meldung eine frische Anmeldung: eine BC0-Sitzung gilt 8 Stunden,
zwischen Start und Abschluss koennen Stunden liegen.

Sicherheit: Das Passwort steht in keiner Meldung, keinem Log, keinem repr. Ausnahmen
von httpx werden nie verkettet und nie geloggt — sie tragen die Anfrage samt Rumpf,
beim Login also das Passwort (gemessen 06.10.2026: e.request.content).
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from bc1_service.start import lies_company_id

log = logging.getLogger(__name__)

ZEITLIMIT_SEKUNDEN = 10

_PFLICHT = ("BC1_BC0_URL", "BC1_BC0_KONTO_EMAIL", "BC1_BC0_KONTO_PASSWORT")
_ERLAUBTE_HTTP_HOSTS = ("localhost", "127.0.0.1")   # lokales BC0, sonst nur https

# Wortlaut aus der Spec B4, Abschnitt 5 — in Tests festgenagelt.
MELDUNG_ZUGANG_UNVOLLSTAENDIG = (
    "BC0-Zugang unvollständig: {namen} fehlt. Ohne Zugang meldet BC1 weder "
    "'im_interview' noch das Gate. Entweder setzen oder bewusst BC1_BC0_MELDUNGEN=aus.")
MELDUNG_SCHALTER_UNBEKANNT = (
    "BC1_BC0_MELDUNGEN='{wert}' ist unbekannt. Erlaubt ist nur 'aus' — oder die "
    "Variable weglassen.")
MELDUNG_KEIN_HTTPS = (
    "BC1_BC0_URL='{url}' ist keine https-Adresse. Das Passwort geht nur verschlüsselt "
    "über das Netz (Ausnahme: localhost).")
MELDUNG_AUS = (
    "Meldungen an BC0 sind ausgeschaltet (BC1_BC0_MELDUNGEN=aus) — 'im_interview' und "
    "das Gate setzt BC0 von Hand.")

MELDUNG_ANMELDUNG_ABGELEHNT = (
    "BC0 lehnt die Anmeldung ab (E-Mail oder Passwort falsch). BC1_BC0_KONTO_EMAIL "
    "und BC1_BC0_KONTO_PASSWORT prüfen.")
MELDUNG_GESPERRT = (
    "BC0 sperrt die Anmeldung nach zu vielen Fehlversuchen noch {minuten} Minute(n). "
    "Erst den Zugang prüfen, dann warten.")
MELDUNG_SITZUNG_NICHT_ANGENOMMEN = (
    "BC0 nimmt die Anmeldung bei '{aktion}' nicht an (401), obwohl sie geklappt hat. "
    "Bei einem lokalen BC0 ohne https muss dort BC0_COOKIE_UNSICHER=1 gesetzt sein.")
MELDUNG_KEIN_SCHREIBRECHT = (
    "BC0 verweigert '{aktion}' (403): {detail} Das Anwendungskonto braucht "
    "Schreibrecht (Rolle 'benutzer' oder 'admin').")
MELDUNG_MANDANT_UNBEKANNT = (
    "BC0 kennt den Mandanten {company_id} für dieses Anwendungskonto nicht (404). "
    "Das Konto braucht den Mandanten zugewiesen.")
MELDUNG_ANTWORT = "BC0 antwortet auf '{aktion}' mit {code}: {detail}"
MELDUNG_NICHT_ERREICHBAR = (
    "BC0 unter {url} ist nicht erreichbar ({art}). Läuft BC0, stimmt BC1_BC0_URL?")
MELDUNG_KONTO_OHNE_SCHREIBRECHT = (
    "Das BC0-Anwendungskonto darf nicht schreiben (Rolle '{rolle}'). Es braucht die Rolle "
    "'benutzer' oder 'admin'.")
MELDUNG_KONTO_OHNE_MANDANT = (
    "Das BC0-Anwendungskonto sieht den Mandanten {company_id} nicht. Das Konto braucht den "
    "Mandanten zugewiesen.")

_ANMELDUNG = "Anmeldung"
_MANDANT_UNBEKANNT_DETAIL = "Mandant unbekannt."   # bc0_auth.abhaengigkeiten.pruefe_mandant


@dataclass(frozen=True)
class Bc0Zugang:
    url: str
    email: str
    passwort: str = field(repr=False)


def lies_bc0_zugang(umgebung: Mapping[str, str]) -> Bc0Zugang | None:
    schalter = umgebung.get("BC1_BC0_MELDUNGEN", "").strip()
    if schalter:
        if schalter == "aus":
            return None
        raise RuntimeError(MELDUNG_SCHALTER_UNBEKANNT.format(wert=schalter))
    fehlend = [name for name in _PFLICHT if not umgebung.get(name, "").strip()]
    if fehlend:
        raise RuntimeError(MELDUNG_ZUGANG_UNVOLLSTAENDIG.format(namen=", ".join(fehlend)))
    url_roh = umgebung["BC1_BC0_URL"].strip()
    teile = urlsplit(url_roh)
    sicher = teile.scheme == "https" or (
        teile.scheme == "http" and teile.hostname in _ERLAUBTE_HTTP_HOSTS)
    if not (sicher and teile.hostname):
        raise RuntimeError(MELDUNG_KEIN_HTTPS.format(url=url_roh))
    # Das Passwort wird NICHT beschnitten — Leerzeichen koennen dazugehoeren.
    return Bc0Zugang(url=url_roh.rstrip("/"), email=umgebung["BC1_BC0_KONTO_EMAIL"].strip(),
                     passwort=umgebung["BC1_BC0_KONTO_PASSWORT"])


class Bc0MeldungFehler(RuntimeError):
    """Eine Meldung an BC0 ist gescheitert; der Text ist fuer Menschen gedacht."""


def _detail(antwort: httpx.Response, *, geheim: str | None = None) -> str:
    """BC0s detail-Text; ohne JSON (Proxy-Seite) der Antworttext. Auf 200 Zeichen.

    Mit `geheim` (beim Login: das Passwort) nur BC0s eigener str-detail, nie der rohe
    Antworttext — BC0 kann den Rumpf samt Passwort zuruecksenden (FastAPI-422: "input")."""
    try:
        daten = antwort.json()
    except ValueError:
        daten = None
    detail = daten.get("detail") if isinstance(daten, dict) else None
    if not isinstance(detail, str):
        if geheim is not None:
            return ""
        detail = antwort.text
    if geheim is not None and geheim in detail:     # VOR dem Kuerzen: sonst bliebe ein Anfang stehen
        return ""
    return detail[:200]


def _minuten(antwort: httpx.Response) -> int:
    """Wie BC0 selbst: max(1, round(Sekunden / 60)); unlesbar oder fehlend = 1."""
    try:
        sekunden = int(antwort.headers.get("Retry-After", ""))
    except ValueError:
        return 1
    return max(1, round(sekunden / 60))


def _konto_bereit(konto: dict, company_id: str) -> tuple[bool, bool]:
    """(darf schreiben, sieht den Mandanten) — wie BC0s darf_schreiben/darf_mandanten_sehen:
    Admin sieht alle Mandanten. "mandanten": null gilt als leer."""
    schreiben = konto.get("darf_schreiben") is True
    mandant = konto.get("ist_admin") is True or company_id in (konto.get("mandanten") or [])
    return schreiben, mandant


class Bc0Melder:
    """Je Meldung: frischer Client -> Login -> Aufruf -> schliessen."""

    def __init__(self, zugang: Bc0Zugang, company_id: str, *,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._zugang = zugang
        self._company_id = company_id
        self._transport = transport             # nur Tests (httpx.MockTransport)

    def melde_interview_laeuft(self, anfrage_id: str) -> None:
        self._melden("Status im_interview", "PUT",
                     f"/api/companies/{self._company_id}/anfragen/{anfrage_id}/status",
                     {"status": "im_interview"})

    def ziehe_gate_nach(self) -> list[str]:
        daten = self._melden(
            "Gate nachziehen", "POST",
            f"/api/companies/{self._company_id}/anfragen/gate_nachziehen")
        return list(daten.get("gesetzt") or [])          # auch bei "gesetzt": null

    def lies_konto(self) -> dict:
        return self._melden("Konto lesen", "GET", "/api/auth/me")

    def pruefe_konto(self) -> None:
        """Start-Pruefung (Ergaenzung 08.10.): Anmeldung + eigenes Konto lesen, aendert nichts."""
        konto = self.lies_konto()
        schreiben, mandant = _konto_bereit(konto, self._company_id)
        if not schreiben:
            raise Bc0MeldungFehler(MELDUNG_KONTO_OHNE_SCHREIBRECHT.format(rolle=konto.get("rolle")))
        if not mandant:
            raise Bc0MeldungFehler(MELDUNG_KONTO_OHNE_MANDANT.format(company_id=self._company_id))

    def _melden(self, aktion: str, methode: str, pfad: str, rumpf: dict | None = None) -> dict:
        art = None
        try:
            with httpx.Client(base_url=self._zugang.url, timeout=ZEITLIMIT_SEKUNDEN,
                              transport=self._transport) as client:
                self._pruefe(client.post("/api/auth/login", json={
                    "email": self._zugang.email, "passwort": self._zugang.passwort}),
                    _ANMELDUNG)
                antwort = client.request(methode, pfad, json=rumpf)
                self._pruefe(antwort, aktion)
                return self._json(antwort, aktion)
        except httpx.RequestError as fehler:
            art = type(fehler).__name__
        # Bewusst AUSSERHALB des except-Blocks: so haengt die httpx-Ausnahme (mit dem
        # Login-Rumpf) weder als __cause__ noch als __context__ an der BC1-Ausnahme.
        raise Bc0MeldungFehler(MELDUNG_NICHT_ERREICHBAR.format(url=self._zugang.url, art=art))

    @staticmethod
    def _json(antwort: httpx.Response, aktion: str) -> dict:
        try:
            daten = antwort.json()
        except ValueError:
            daten = None
        if not isinstance(daten, dict):
            raise Bc0MeldungFehler(MELDUNG_ANTWORT.format(
                aktion=aktion, code=antwort.status_code, detail=antwort.text[:200]))
        return daten

    def _pruefe(self, antwort: httpx.Response, aktion: str) -> None:
        code = antwort.status_code
        if 200 <= code < 300:
            return
        geheim = self._zugang.passwort if aktion == _ANMELDUNG else None
        detail = _detail(antwort, geheim=geheim)
        if aktion == _ANMELDUNG and code == 401:
            raise Bc0MeldungFehler(MELDUNG_ANMELDUNG_ABGELEHNT)
        if aktion == _ANMELDUNG and code == 429:
            raise Bc0MeldungFehler(MELDUNG_GESPERRT.format(minuten=_minuten(antwort)))
        if code == 401:
            raise Bc0MeldungFehler(MELDUNG_SITZUNG_NICHT_ANGENOMMEN.format(aktion=aktion))
        if code == 403:
            raise Bc0MeldungFehler(MELDUNG_KEIN_SCHREIBRECHT.format(aktion=aktion, detail=detail))
        if code == 404 and detail == _MANDANT_UNBEKANNT_DETAIL:
            raise Bc0MeldungFehler(MELDUNG_MANDANT_UNBEKANNT.format(company_id=self._company_id))
        raise Bc0MeldungFehler(MELDUNG_ANTWORT.format(aktion=aktion, code=code, detail=detail))


def baue_melder(umgebung: Mapping[str, str], company_id: str) -> Bc0Melder | None:
    """None = Meldungen bewusst aus; dann steht es einmal deutlich im Log."""
    zugang = lies_bc0_zugang(umgebung)
    if zugang is None:
        log.warning(MELDUNG_AUS)
        return None
    return Bc0Melder(zugang, company_id)


def probe(umgebung: Mapping[str, str], *, transport=None, ausgabe=print) -> int:
    """Live-Probe (nur lesend): darf das Konto schreiben, sieht es den Mandanten?

    Mandant sichtbar wie bei BC0 (darf_mandanten_sehen): Admin sieht alle, sonst
    nur die zugewiesenen. Aendert nichts bei BC0."""
    try:
        company_id = lies_company_id(umgebung)
        zugang = lies_bc0_zugang(umgebung)
    except RuntimeError as fehler:
        ausgabe(str(fehler))
        return 2
    if zugang is None:
        ausgabe("BC1_BC0_MELDUNGEN=aus — nichts zu prüfen.")
        return 2
    try:
        konto = Bc0Melder(zugang, company_id, transport=transport).lies_konto()
    except Bc0MeldungFehler as fehler:
        ausgabe(str(fehler))
        return 1
    schreiben, mandant = _konto_bereit(konto, company_id)
    ausgabe(f"Rolle: {konto.get('rolle')}")
    ausgabe(f"Schreibrecht: {'ja' if schreiben else 'nein'}")
    ausgabe(f"Mandant {company_id} sichtbar: {'ja' if mandant else 'nein'}")
    return 0 if schreiben and mandant else 1


if __name__ == "__main__":
    if sys.argv[1:] != ["--probe"]:
        print("Aufruf: python -m bc1_service.bc0_meldungen --probe")
        sys.exit(2)
    sys.exit(probe(os.environ))
