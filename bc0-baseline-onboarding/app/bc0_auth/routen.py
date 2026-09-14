# -*- coding: utf-8 -*-
"""
HTTP-Schnittstelle der Benutzerverwaltung.

Alle Endpunkte liegen unter ``/api/auth``. Sie zerfallen in zwei Gruppen:

* **Für jeden Angemeldeten** — anmelden, abmelden, eigenes Konto ansehen,
  eigenes Passwort ändern.
* **Nur für Admins** — Benutzer auflisten, anlegen, ändern, sperren, fremdes
  Passwort zurücksetzen.

Was hier bewusst *nicht* passiert
---------------------------------
Kein Endpunkt gibt jemals einen Passwort-Hash heraus, und keiner nimmt eine
Rollenangabe vom Aufrufer für sich selbst entgegen. Wer sein eigenes Konto
bearbeitet, kann Namen und Passwort ändern — Rolle und Mandantenzuordnung nur
ein Admin. Andernfalls könnte sich jeder Benutzer selbst zum Admin machen.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import passwoerter
from .abhaengigkeiten import (
    COOKIE_NAME,
    admin,
    angemeldeter_benutzer,
    hole_dienst,
    optionaler_benutzer,
    sitzungsschluessel_aus,
)
from .modelle import AnmeldeFehler, Benutzer, Rolle, ZuVieleVersuche

_log = logging.getLogger("bc0.auth")

router = APIRouter(prefix="/api/auth", tags=["Benutzerverwaltung"])

#: Das Sitzungs-Cookie wird nur über HTTPS gesendet. Für die lokale Entwicklung
#: ohne TLS lässt sich das mit BC0_COOKIE_UNSICHER=1 abschalten — im Betrieb
#: niemals setzen. Die Vorbelegung ist bewusst die sichere.
COOKIE_NUR_HTTPS = os.environ.get("BC0_COOKIE_UNSICHER", "").strip() not in ("1", "true", "ja")


# --------------------------------------------------------------------------- #
# Ein- und Ausgabemodelle
# --------------------------------------------------------------------------- #
class AnmeldeDaten(BaseModel):
    """Rumpf von ``POST /api/auth/login``.

    Kein Feld hat eine Vorbelegung: Beide Angaben sind Pflicht, und ein
    fehlendes Feld soll als 422 auffallen und nicht als leere Zeichenkette
    durch die Passwortprüfung laufen.
    """

    email: str
    passwort: str


class PasswortDaten(BaseModel):
    """Rumpf des Passwortwechsels.

    Bewusst **ohne** Feld für das alte Passwort: Der Wechsel setzt eine gültige
    Sitzung voraus, und der Endpunkt ändert ausschließlich das eigene Konto.
    Ein Admin setzt fremde Passwörter über ``PUT /benutzer/{id}``.

    Die Mindestlänge prüft nicht dieses Modell, sondern
    :func:`bc0_auth.passwoerter.pruefe_mindestanforderungen` — damit dieselbe
    Regel für alle Wege gilt, auf denen ein Passwort entsteht.
    """

    neues_passwort: str


class BenutzerAnlegen(BaseModel):
    """Rumpf von ``POST /api/auth/benutzer`` (Admin).

    ``rolle`` ist mit :data:`Rolle.BENUTZER` vorbelegt. Das ist eine
    Sicherheitsentscheidung: Wer das Feld vergisst, legt ein gewöhnliches Konto
    an und keinen Administrator. Der Text wird über ``Rolle.aus_text``
    aufgelöst, die unbekannte Werte abweist statt sie stillschweigend zu
    ersetzen (Test ``test_auth.py`` Nr. 7).

    ``mandanten`` ist standardmäßig leer — ein neues Konto sieht zunächst
    nichts. Auch das ist die sichere Vorbelegung.
    """

    email: str
    name: str
    passwort: str
    rolle: str = Rolle.BENUTZER.value
    mandanten: List[str] = []


class BenutzerAendern(BaseModel):
    """Rumpf von ``PUT /api/auth/benutzer/{id}`` (Admin).

    Alle Felder sind ``Optional`` und mit ``None`` vorbelegt, weil dies ein
    **Teilformular** ist: Ein PUT, das nur ``aktiv`` schickt, darf die
    Mandantenzuordnung nicht leeren. ``None`` heißt „nicht mitgeschickt",
    nicht „auf leer setzen". Der Unterschied ist der Grund, warum hier nicht
    einfach die Vorbelegungen aus :class:`BenutzerAnlegen` stehen — dieselbe
    Fehlerklasse ist im Entitätenregister als Test festgehalten
    (``test_entitaeten.py`` Nr. 14).
    """

    name: Optional[str] = None
    rolle: Optional[str] = None
    mandanten: Optional[List[str]] = None
    aktiv: Optional[bool] = None


def _als_antwort(benutzer: Benutzer) -> dict:
    """Formt die nach außen sichtbare Darstellung eines Benutzers.

    Diese Funktion ist der einzige Weg, auf dem Benutzerdaten die Anwendung
    verlassen. Neue Felder in :class:`Benutzer` erscheinen dadurch nicht
    versehentlich in der API — sie müssen hier ausdrücklich aufgenommen werden.
    """
    return {
        "benutzer_id": benutzer.benutzer_id,
        "email": benutzer.email,
        "name": benutzer.name,
        "rolle": benutzer.rolle.value,
        "ist_admin": benutzer.ist_admin,
        "mandanten": sorted(benutzer.mandanten),
        "aktiv": benutzer.aktiv,
    }


# --------------------------------------------------------------------------- #
# Anmeldung
# --------------------------------------------------------------------------- #
@router.get("/status")
def status(benutzer: Optional[Benutzer] = Depends(optionaler_benutzer)) -> dict:
    """Auskunft für die Oberfläche — ohne Anmeldung erreichbar.

    Liefert, ob jemand angemeldet ist und ob überhaupt schon ein Konto existiert.
    Letzteres braucht die Oberfläche, um beim Erststart einen verständlichen
    Hinweis statt einer wirkungslosen Anmeldemaske zu zeigen.
    """
    dienst = hole_dienst()
    return {
        "angemeldet": benutzer is not None,
        "benutzer": _als_antwort(benutzer) if benutzer else None,
        "eingerichtet": dienst.ist_eingerichtet(),
    }


def _herkunft(request: Request) -> Optional[str]:
    """Die IP-Adresse des Aufrufers, wie die Anwendung sie sieht.

    ``request.client.host`` ist seit dem Ausrollen von ``--proxy-headers`` am
    02.09.2026 die **echte** Adresse des Benutzers: uvicorn setzt sie aus
    ``X-Forwarded-For``, das Caddy mitschickt. Vorher stand hier Caddys eigene
    Adresse, und ein Zaehler je IP haette alle Benutzer als einen gezaehlt.

    Es wird **kein** Header selbst gelesen. Wer ``X-Forwarded-For`` hier von
    Hand auswertete, liesse sich die Adresse vom Aufrufer diktieren — und die
    Bremse waere mit einer erfundenen Zeile im Kopf zu umgehen. Die Auswertung
    gehoert an die eine Stelle, an der die Vertrauensgrenze steht: uvicorn.
    """
    return request.client.host if request.client else None


@router.post("/login")
def anmelden(daten: AnmeldeDaten, request: Request, antwort: Response) -> dict:
    """Meldet einen Benutzer an und setzt das Sitzungs-Cookie.

    Der Sitzungsschlüssel wird ausschließlich im Cookie übertragen und **nicht**
    im Antwortkörper. So kann ihn kein Skript in der Seite auslesen.

    Zwei verschiedene Absagen
    -------------------------
    **401** heisst „Adresse oder Passwort falsch" und sagt bewusst nicht, was
    von beidem — sonst waere die Anmeldemaske ein Verzeichnis der vorhandenen
    Konten. **429** heisst „zu viele Versuche" und sagt es ausdruecklich, samt
    Wartezeit: Dieser Fall verraet nichts ueber Konten, weil der Versuch
    gezaehlt wird und nicht das Konto — und wer nicht erfaehrt, dass er
    gesperrt ist, haelt die Anwendung fuer kaputt.

    ``Retry-After`` ist die Standardform dieser Auskunft (RFC 9110); die
    Wartezeit steht zusaetzlich im Text, weil sie sonst nur im Kopf der
    Antwort stuende und in der Oberflaeche niemand sie saehe.
    """
    dienst = hole_dienst()
    try:
        benutzer, schluessel, sitzung = dienst.anmelden(
            daten.email, daten.passwort, herkunft=_herkunft(request))
    except ZuVieleVersuche as gesperrt:
        minuten = max(1, round(gesperrt.rest_sekunden / 60))
        raise HTTPException(
            status_code=429,
            detail="Zu viele fehlgeschlagene Anmeldeversuche. "
                   "Bitte in %d Minute%s erneut versuchen."
                   % (minuten, "n" if minuten != 1 else ""),
            headers={"Retry-After": str(gesperrt.rest_sekunden)},
        )
    except AnmeldeFehler:
        # Einheitliche Meldung — siehe modelle.AnmeldeFehler.
        raise HTTPException(status_code=401, detail="E-Mail-Adresse oder Passwort ist falsch.")

    antwort.set_cookie(
        key=COOKIE_NAME,
        value=schluessel,
        httponly=True,
        secure=COOKIE_NUR_HTTPS,
        samesite="lax",
        max_age=int(dienst.sitzungsdauer.total_seconds()),
        path="/",
    )
    return {"ok": True, "benutzer": _als_antwort(benutzer)}


@router.post("/logout")
def abmelden(request: Request, antwort: Response) -> dict:
    """Beendet die Sitzung serverseitig und löscht das Cookie.

    Beides ist nötig: Ein gelöschtes Cookie allein würde einen abgegriffenen
    Schlüssel weiter gültig lassen.
    """
    hole_dienst().abmelden(sitzungsschluessel_aus(request))
    antwort.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def eigenes_konto(benutzer: Benutzer = Depends(angemeldeter_benutzer)) -> dict:
    """Gibt das eigene Konto zurück — Grundlage für die Rollenwahl der Oberfläche."""
    return _als_antwort(benutzer)


@router.post("/me/passwort")
def eigenes_passwort_aendern(
    daten: PasswortDaten, benutzer: Benutzer = Depends(angemeldeter_benutzer)
) -> dict:
    """Ändert das eigene Passwort.

    Alle offenen Sitzungen werden dabei beendet — auch die aufrufende. Der
    Benutzer muss sich anschließend neu anmelden. Siehe
    :meth:`AuthDienst.passwort_aendern`.
    """
    try:
        hole_dienst().passwort_aendern(benutzer.benutzer_id, daten.neues_passwort)
    except passwoerter.PasswortFehler as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    return {"ok": True, "hinweis": "Bitte neu anmelden."}


# --------------------------------------------------------------------------- #
# Benutzerpflege (nur Admin)
# --------------------------------------------------------------------------- #
@router.get("/benutzer")
def benutzer_auflisten(_: Benutzer = Depends(admin)) -> List[dict]:
    """Listet alle Konten auf. Admins vorbehalten.

    Der Rückgabeweg führt zwingend über :func:`_als_antwort`; der Passwort-Hash
    verlässt die Anwendung damit an keiner Stelle (Test ``test_app_zugriff.py``
    Nr. 9). Der Parameter heißt ``_``, weil der handelnde Admin hier nicht
    gebraucht wird — ``Depends(admin)`` steht ausschließlich als Rechteprüfung.
    """
    return [_als_antwort(b) for b in hole_dienst().alle_benutzer()]


@router.post("/benutzer")
def benutzer_anlegen(daten: BenutzerAnlegen, handelnder: Benutzer = Depends(admin)) -> dict:
    """Legt ein Konto an. Admins vorbehalten.

    Zwei Fehlerklassen werden getrennt gefangen und beide zu 400:
    :class:`~bc0_auth.passwoerter.PasswortFehler` für ein zu kurzes Passwort und
    ``ValueError`` für eine bereits vergebene Adresse oder eine unbekannte
    Rolle. Wichtig ist, was **nicht** passiert: Die Meldung wird unverändert
    durchgereicht, damit in der Oberfläche „mindestens 12 Zeichen" steht und
    nicht „Fehler".

    Der handelnde Admin wird protokolliert. Das ist derzeit die einzige Form
    von Nachvollziehbarkeit im System — ein Änderungsprotokoll in der Datenbank
    fehlt noch (Etappe 4c, siehe Sicherheitskonzept 3.4). Ein Protokolleintrag
    in der Containerausgabe überlebt einen Neustart nicht.
    """
    try:
        neuer = hole_dienst().benutzer_anlegen(
            email=daten.email,
            name=daten.name,
            passwort=daten.passwort,
            rolle=Rolle.aus_text(daten.rolle),
            mandanten=daten.mandanten,
        )
    except passwoerter.PasswortFehler as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    except ValueError as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    _log.info("%s hat den Benutzer %s angelegt", handelnder.email, neuer.email)
    return _als_antwort(neuer)


@router.put("/benutzer/{benutzer_id}")
def benutzer_aendern(
    benutzer_id: str, daten: BenutzerAendern, handelnder: Benutzer = Depends(admin)
) -> dict:
    """Ändert Rolle, Mandantenzuordnung oder Sperrstatus eines Benutzers.

    Ein Admin kann sich nicht selbst herabstufen oder sperren. Das ist kein
    Misstrauen, sondern verhindert den Zustand, in dem kein Admin mehr existiert
    und die Anwendung nur noch über die Kommandozeile zu retten wäre.
    """
    dienst = hole_dienst()
    ziel = dienst.benutzer.finde_per_id(benutzer_id)
    if ziel is None:
        raise HTTPException(status_code=404, detail="Benutzer unbekannt.")

    selbst = ziel.benutzer_id == handelnder.benutzer_id
    if selbst and daten.rolle is not None and Rolle.aus_text(daten.rolle) is not Rolle.ADMIN:
        raise HTTPException(status_code=400, detail="Die eigene Admin-Rolle kann nicht entzogen werden.")
    if selbst and daten.aktiv is False:
        raise HTTPException(status_code=400, detail="Das eigene Konto kann nicht gesperrt werden.")

    if daten.name is not None:
        dienst.benutzer.name_setzen(benutzer_id, daten.name)
    if daten.rolle is not None:
        dienst.benutzer.rolle_setzen(benutzer_id, Rolle.aus_text(daten.rolle))
    if daten.mandanten is not None:
        dienst.benutzer.mandanten_setzen(benutzer_id, daten.mandanten)
    if daten.aktiv is not None:
        if daten.aktiv:
            dienst.benutzer_entsperren(benutzer_id)
        else:
            dienst.benutzer_sperren(benutzer_id)

    _log.info("%s hat den Benutzer %s geändert", handelnder.email, ziel.email)
    return _als_antwort(dienst.benutzer.finde_per_id(benutzer_id))


@router.post("/benutzer/{benutzer_id}/passwort")
def fremdes_passwort_setzen(
    benutzer_id: str, daten: PasswortDaten, handelnder: Benutzer = Depends(admin)
) -> dict:
    """Setzt das Passwort eines anderen Benutzers zurück.

    Für den Fall, dass jemand sein Passwort vergessen hat. Ein
    Selbstbedienungs-Weg per E-Mail ist bewusst nicht vorgesehen: Er bräuchte
    einen Mailversand und wäre bei dieser Nutzerzahl mehr Angriffsfläche als
    Nutzen.
    """
    dienst = hole_dienst()
    if dienst.benutzer.finde_per_id(benutzer_id) is None:
        raise HTTPException(status_code=404, detail="Benutzer unbekannt.")
    try:
        dienst.passwort_aendern(benutzer_id, daten.neues_passwort)
    except passwoerter.PasswortFehler as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    _log.info("%s hat das Passwort von %s zurückgesetzt", handelnder.email, benutzer_id)
    return {"ok": True}
