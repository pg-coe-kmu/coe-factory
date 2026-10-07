"""Meldungen von BC1 an BC0 (B4): 'Interview laeuft' und 'Gate nachziehen'.

BC1 meldet sich dafuer mit dem Anwendungskonto an (POST /api/auth/login, Cookie
bc0_sitzung). Je Meldung eine frische Anmeldung: eine BC0-Sitzung gilt 8 Stunden,
zwischen Start und Abschluss koennen Stunden liegen.

Sicherheit: Das Passwort steht in keiner Meldung, keinem Log, keinem repr. Ausnahmen
von httpx werden nie verkettet und nie geloggt — sie tragen die Anfrage samt Rumpf,
beim Login also das Passwort (gemessen 06.10.2026: e.request.content).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

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
