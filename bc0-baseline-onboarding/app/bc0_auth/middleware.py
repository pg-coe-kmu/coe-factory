# -*- coding: utf-8 -*-
"""
Anmeldepflicht als Netz unter der gesamten API.

Warum eine Middleware und nicht ``Depends`` an jedem Endpunkt
-------------------------------------------------------------
``app.py`` hat siebzehn Endpunkte, und es kommen welche dazu. Würde der Schutz
allein an ``Depends`` hängen, wäre ein neuer Endpunkt so lange offen, bis jemand
daran denkt — der Fehler wäre still und von außen nicht sichtbar.

Diese Middleware dreht die Vorgabe um: **Alles unter** ``/api/`` **verlangt eine
Anmeldung**, es sei denn, der Pfad steht ausdrücklich in :data:`OFFENE_PFADE`.
Eine vergessene Absicherung führt damit nicht zu einem offenen Endpunkt, sondern
zu einem, der 401 meldet — ein Fehler, der sofort auffällt.

``Depends(angemeldeter_benutzer)`` bleibt trotzdem sinnvoll und wird weiter
verwendet: dort, wo der Endpunkt den Benutzer im Rumpf braucht (Mandantenfilter,
Admin-Prüfung). Die Middleware ist der Boden, ``Depends`` ist die Fachlogik.

Was bewusst offen bleibt
------------------------
Die PWA-Hülle selbst — ``/``, ``/sw.js``, ``/manifest.json``, ``/static/…``. Sie
enthält keine Mandantendaten, sondern nur die Oberfläche, die anschließend die
Anmeldemaske zeigt. Wäre sie geschützt, gäbe es keine Seite, auf der man sich
anmelden könnte.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .abhaengigkeiten import hole_dienst, sitzungsschluessel_aus

#: Pfade unterhalb von ``/api/``, die ohne Anmeldung erreichbar sein müssen.
#: Bewusst kurz gehalten und einzeln begründet:
#:   /api/auth/login   — sonst könnte sich niemand anmelden
#:   /api/auth/logout  — muss auch mit abgelaufener Sitzung aufrufbar sein
#:   /api/auth/status  — die Oberfläche fragt damit ab, ob jemand angemeldet ist
OFFENE_PFADE = frozenset(
    {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/status",
    }
)

#: Präfix, ab dem die Anmeldepflicht greift.
GESCHUETZTES_PRAEFIX = "/api/"


class AnmeldepflichtMiddleware(BaseHTTPMiddleware):
    """Weist Anfragen an die API ohne gültige Sitzung mit 401 ab.

    Der aufgelöste Benutzer wird unter ``request.state.benutzer`` abgelegt.
    Nachgelagerte ``Depends``-Funktionen greifen darauf zurück, statt ihn ein
    zweites Mal aus der Datenbank zu lesen.
    """

    async def dispatch(self, request, call_next):
        """Entscheidet je Anfrage: durchlassen oder mit 401 abweisen.

        Die Reihenfolge der beiden Bedingungen ist wesentlich. Geprüft wird
        zuerst, ob der Pfad überhaupt geschützt ist, und erst dann, ob eine
        Sitzung besteht. Die Vorgabe für alles unter ``/api/`` ist „gesperrt";
        ein Pfad wird nur durch den ausdrücklichen Eintrag in
        :data:`OFFENE_PFADE` frei.

        Auch auf offenen Pfaden wird die Sitzung aufgelöst und unter
        ``request.state.benutzer`` abgelegt — ``/api/auth/status`` braucht den
        Benutzer, ohne ihn zu verlangen.

        Die 401-Antwort trägt ``Cache-Control: no-store``. Ohne diesen Kopf
        könnte ein Zwischenspeicher die Abweisung festhalten und sie nach einer
        erfolgreichen Anmeldung erneut ausliefern.
        """
        pfad = request.url.path

        if not pfad.startswith(GESCHUETZTES_PRAEFIX) or pfad in OFFENE_PFADE:
            # Kein API-Pfad oder ausdrücklich offen — trotzdem den Benutzer
            # auflösen, falls eine Sitzung besteht. Endpunkte wie /api/auth/status
            # können ihn dann verwenden.
            request.state.benutzer = _sicher_aufloesen(request)
            AKTUELLER_BENUTZER.set(request.state.benutzer)
            return await call_next(request)

        benutzer = _sicher_aufloesen(request)
        if benutzer is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Nicht angemeldet."},
                headers={"Cache-Control": "no-store"},
            )

        request.state.benutzer = benutzer
        AKTUELLER_BENUTZER.set(benutzer)
        return await call_next(request)


import contextvars

#: Der Benutzer der laufenden Anfrage — fuer die Aenderungshistorie (R9, v2.6).
#: Die Datenbankverbindung liest ihn und setzt `bc0.benutzer`; der Trigger
#: trg_historie() traegt ihn als `actor` ein. Ohne Anmeldung bleibt er None,
#: und die Historie zeigt den Datenbankbenutzer.
AKTUELLER_BENUTZER = contextvars.ContextVar("bc0_aktueller_benutzer", default=None)


def _sicher_aufloesen(request):
    """Löst die Sitzung auf und schluckt dabei keine Fehler stillschweigend.

    Ein Datenbankfehler beim Auflösen darf nicht dazu führen, dass die Anfrage
    als „angemeldet" durchgeht. Er führt hier zu ``None`` und damit zu 401 —
    im Zweifel abweisen, nicht durchlassen.
    """
    try:
        return hole_dienst().benutzer_zu_sitzung(sitzungsschluessel_aus(request))
    except Exception:  # noqa: BLE001 — bewusst breit: jeder Fehler bedeutet „nicht angemeldet"
        import logging

        logging.getLogger("bc0.auth").exception("Sitzung konnte nicht aufgelöst werden")
        return None
