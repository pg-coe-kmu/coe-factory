# -*- coding: utf-8 -*-
"""
Anbindung der Benutzerverwaltung an FastAPI.

Dieses Modul stellt die ``Depends``-Funktionen bereit, mit denen ein Endpunkt
seine Anforderung an den Aufrufer ausdrückt::

    @app.get("/api/companies")
    def companies(benutzer: Benutzer = Depends(angemeldeter_benutzer)):
        ...

    @app.delete("/api/companies/{cid}")
    def delete_company(cid: str, benutzer: Benutzer = Depends(admin)):
        ...

Der Vorteil gegenüber einer Prüfung im Rumpf jeder Funktion: Die Anforderung steht
in der Signatur und damit auch in der automatisch erzeugten API-Dokumentation.
Wer den Endpunkt liest, sieht sofort, wer ihn aufrufen darf.

Warum ein Cookie und kein Bearer-Token
--------------------------------------
Die Oberfläche ist eine PWA, die im selben Ursprung wie die API läuft. Ein
``HttpOnly``-Cookie ist dort die sicherere Wahl: Es ist für JavaScript nicht
lesbar, ein eingeschleustes Skript kann es also nicht auslesen und
weiterschicken. Ein im ``localStorage`` abgelegtes Token wäre genau das.

Der Preis ist die Anfälligkeit für websiteübergreifende Anfragen (CSRF). Dagegen
steht ``SameSite=Lax``: Der Browser sendet das Cookie dann nicht bei
schreibenden Anfragen von fremden Seiten mit.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request

from .dienst import AuthDienst
from .modelle import Benutzer

#: Name des Sitzungs-Cookies.
COOKIE_NAME = "bc0_sitzung"

# Der Dienst wird beim Start der Anwendung einmal gesetzt (siehe app.py). Ein
# Modul-globaler Halter ist hier angemessen: Es gibt genau eine Anwendung mit
# genau einer Datenbankanbindung, und die Alternative — den Dienst durch jede
# Signatur zu reichen — würde nur Rauschen erzeugen.
_dienst: Optional[AuthDienst] = None


def dienst_setzen(dienst: AuthDienst) -> None:
    """Hinterlegt den zu verwendenden :class:`AuthDienst`."""
    global _dienst
    _dienst = dienst


def hole_dienst() -> AuthDienst:
    """Liefert den hinterlegten Dienst.

    Raises:
        RuntimeError: wenn die Anwendung ``dienst_setzen`` nicht aufgerufen hat.
            Das ist ein Programmierfehler und soll laut scheitern, nicht still
            zu einem offenen Zugang führen.
    """
    if _dienst is None:
        raise RuntimeError(
            "AuthDienst ist nicht gesetzt — bc0_auth.abhaengigkeiten.dienst_setzen() "
            "muss beim Start der Anwendung aufgerufen werden."
        )
    return _dienst


def sitzungsschluessel_aus(request: Request) -> Optional[str]:
    """Liest den Sitzungsschlüssel aus dem Cookie der Anfrage."""
    return request.cookies.get(COOKIE_NAME)


def optionaler_benutzer(request: Request) -> Optional[Benutzer]:
    """Liefert den angemeldeten Benutzer oder ``None``.

    Für Endpunkte, die auch ohne Anmeldung antworten sollen — etwa die Auskunft,
    ob überhaupt schon ein Konto eingerichtet ist.
    """
    return hole_dienst().benutzer_zu_sitzung(sitzungsschluessel_aus(request))


def angemeldeter_benutzer(request: Request) -> Benutzer:
    """Erzwingt eine gültige Anmeldung.

    Raises:
        HTTPException: 401, wenn keine gültige Sitzung vorliegt.
    """
    benutzer = optionaler_benutzer(request)
    if benutzer is None:
        raise HTTPException(status_code=401, detail="Nicht angemeldet.")
    return benutzer


def admin(benutzer: Benutzer = Depends(angemeldeter_benutzer)) -> Benutzer:
    """Erzwingt die Admin-Rolle.

    Raises:
        HTTPException: 403, wenn der Angemeldete kein Admin ist.

    Der Unterschied zu 401 ist beabsichtigt: 401 heißt „melde dich an", 403 heißt
    „du bist angemeldet, darfst das aber nicht". Die Oberfläche kann daran
    unterscheiden, ob sie zum Anmeldedialog führt oder einen Hinweis zeigt.
    """
    if not benutzer.ist_admin:
        raise HTTPException(status_code=403, detail="Diese Aktion ist Administratoren vorbehalten.")
    return benutzer


def pruefe_mandant(benutzer: Benutzer, mandant_id: str) -> None:
    """Prüft den Zugriff auf einen bestimmten Mandanten.

    Wird in jedem Endpunkt aufgerufen, der eine ``company_id`` entgegennimmt.

    Die Antwort ist bewusst **404 und nicht 403**: Ein Benutzer soll nicht
    erfahren, dass ein Mandant existiert, den er nicht sehen darf. Mit 403 ließe
    sich durch Ausprobieren feststellen, welche IDs vergeben sind.

    Raises:
        HTTPException: 404, wenn der Mandant für diesen Benutzer nicht sichtbar ist.
    """
    if not benutzer.darf_mandanten_sehen(str(mandant_id)):
        raise HTTPException(status_code=404, detail="Mandant unbekannt.")
