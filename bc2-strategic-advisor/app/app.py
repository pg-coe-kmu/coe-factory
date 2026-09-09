"""
BC2 Strategic Advisor — Trigger-Endpunkt.

Nimmt den Paket-Anstoß von BC0 entgegen (Karte #158, Ticket #190), quittiert
sofort mit ``202`` und legt die rohe Nutzlast in ``bc2.eingang`` ab. **Gerechnet
wird hier nichts** — der Endpunkt ist Briefkasten, nicht Sachbearbeiter. Genau
das ist der Grund für ``202`` statt ``200``: zum Antwortzeitpunkt ist noch
nichts passiert, und ``202`` sagt das.

Zwei Wege führen herein (entschieden am 09.09.2026, #190):

1. **Push** — BC0 ruft ``POST /api/bc0/uebergabe`` auf.
2. **Nachholen** — BC2 gleicht selbst gegen ``public.v_uebergabe_offen`` ab,
   beim Start und auf Knopfdruck. Damit hängt BC2s Lauf nicht an BC0s
   Push-Implementierung, und BC0 braucht keine Wiederholungslogik.
   **Kein Dauer-Polling** — die Festlegung aus #165 bleibt.

Die Idempotenz setzt die **Datenbank** durch, nicht dieser Code: ``paket_id``
ist Primärschlüssel von ``bc2.eingang``. Der zweite Aufruf mit derselben ID
läuft ins ``ON CONFLICT DO NOTHING`` und wird als ``bereits_angenommen``
quittiert.

Vertrag: ``contracts/bc0-to-bc2/``.
"""

from __future__ import annotations

import hmac
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from eingang import Eingangsbuch, Paket, PostgresEingangsbuch

log = logging.getLogger("bc2.trigger")

PFLICHTFELDER = ("paket_id", "company_id", "uebergeben_am", "teilprozesse")


# ----------------------------------------------------------------------------
# Schlüssel
# ----------------------------------------------------------------------------


def _erwarteter_schluessel() -> str:
    return (os.environ.get("BC2_TRIGGER_TOKEN") or "").strip()


def _schluessel_stimmt(request: Request) -> bool:
    """Prüft ``Authorization: Bearer <token>``.

    ``Authorization`` und nicht ``X-API-Key``: den ersten Header maskieren
    Zugriffsprotokolle üblicherweise von sich aus, den zweiten nicht.

    ``hmac.compare_digest`` statt ``==``: der Vergleich läuft in gleichbleibender
    Zeit und verrät damit nicht über die Antwortdauer, wie viele Zeichen schon
    stimmen.
    """
    erwartet = _erwarteter_schluessel()
    if not erwartet:
        return False
    kopf = request.headers.get("authorization") or ""
    if not kopf.lower().startswith("bearer "):
        return False
    return hmac.compare_digest(kopf[7:].strip(), erwartet)


# ----------------------------------------------------------------------------
# Prüfung der Nutzlast
# ----------------------------------------------------------------------------


def pruefe_nutzlast(daten: Any) -> tuple[Paket | None, str | None]:
    """Prüft die Nutzlast gegen ``contracts/bc0-to-bc2/trigger.schema.json``.

    Gibt ``(Paket, None)`` oder ``(None, "Klartext, was fehlt")`` zurück. Der
    Klartext geht so an BC0 — wer einen ``400`` bekommt, soll nicht raten
    müssen.

    Geprüft werden **nur die Pflichtfelder**. Unbekannte Felder sind erlaubt und
    werden roh mitprotokolliert: der Endpunkt ist tolerant (#190), damit BC0
    ergänzen kann, ohne sich mit BC2 abzustimmen.
    """
    if not isinstance(daten, dict):
        return None, "Rumpf muss ein JSON-Objekt sein."

    fehlend = [f for f in PFLICHTFELDER if daten.get(f) in (None, "", [])]
    if fehlend:
        return None, f"Pflichtfeld(er) fehlen oder sind leer: {', '.join(fehlend)}."

    paket_id = daten["paket_id"]
    company_id = daten["company_id"]
    if not isinstance(paket_id, str) or not isinstance(company_id, str):
        return None, "paket_id und company_id muessen Zeichenketten sein."

    teilprozesse = daten["teilprozesse"]
    if not isinstance(teilprozesse, list) or not all(
        isinstance(t, str) and t for t in teilprozesse
    ):
        return None, "teilprozesse muss eine nicht-leere Liste von Zeichenketten sein."

    roh = daten["uebergeben_am"]
    if not isinstance(roh, str):
        return None, "uebergeben_am muss eine ISO-8601-Zeichenkette sein."
    try:
        # Python vor 3.11 versteht das abschliessende Z nicht.
        uebergeben_am = datetime.fromisoformat(roh.replace("Z", "+00:00"))
    except ValueError:
        return None, f"uebergeben_am ist kein ISO-8601-Zeitstempel: {roh!r}."

    return (
        Paket(
            paket_id=paket_id,
            company_id=company_id,
            uebergeben_am=uebergeben_am,
            nutzlast=daten,  # roh, samt unbekannter Felder
            quelle="push",
        ),
        None,
    )


# ----------------------------------------------------------------------------
# Anwendung
# ----------------------------------------------------------------------------


def _abgleichen(buch: Eingangsbuch) -> list[str]:
    """Holt nach, was der Push nicht gebracht hat. Gibt die neuen Paket-IDs."""
    neu: list[str] = []
    for paket in buch.offene_pakete_von_bc0():
        if buch.eintragen(paket):
            neu.append(paket.paket_id)
    return neu


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    # Ohne Schlüssel steht der Endpunkt offen. Dann lieber gar nicht starten —
    # ein Dienst, der Pakete von jedem annimmt, ist schlimmer als keiner.
    if not _erwarteter_schluessel():
        raise RuntimeError(
            "BC2_TRIGGER_TOKEN ist nicht gesetzt. Ohne Schluessel startet der "
            "Endpunkt nicht (#190). Erzeugen mit: python -c \"import secrets; "
            "print(secrets.token_urlsafe(32))\" und in die .env legen."
        )

    if app.state.buch is None:
        app.state.buch = PostgresEingangsbuch()

    # Nachholen beim Start: Pakete, die eintrafen, waehrend BC2 aus war.
    # Scheitert das, laeuft der Dienst trotzdem an — der Push ist der Hauptweg,
    # und ein Abgleich laesst sich jederzeit anstossen.
    try:
        neu = _abgleichen(app.state.buch)
        if neu:
            log.info("Beim Start nachgeholt: %s", ", ".join(neu))
    except Exception as e:  # noqa: BLE001
        log.warning("Abgleich beim Start fehlgeschlagen (Dienst laeuft): %s", e)

    yield


def erzeuge_app(buch: Eingangsbuch | None = None) -> FastAPI:
    """Baut die Anwendung. ``buch`` wird in den Tests untergeschoben."""
    app = FastAPI(
        title="BC2 Strategic Advisor — Trigger",
        description="Nimmt Paket-Anstoesse von BC0 entgegen (#190).",
        lifespan=lebenszyklus,
    )
    app.state.buch = buch

    @app.get("/health")
    def health() -> dict[str, str]:
        """Lebenszeichen ohne Schlüssel — für Caddy und die Erreichbarkeitsprobe.

        Sagt bewusst **nichts** über die Datenbank: sonst wäre der Zustand der
        gemeinsamen Datenbank ohne Anmeldung ablesbar. Dafür gibt es
        ``/api/intern/bereit``.
        """
        return {"status": "ok"}

    @app.get("/api/intern/bereit")
    def bereit(request: Request):
        """Bereitschaft samt Datenbank — nur mit Schlüssel."""
        if not _schluessel_stimmt(request):
            return JSONResponse(
                {"fehler": "Schluessel fehlt oder stimmt nicht."}, status_code=401
            )
        db_ok = app.state.buch.erreichbar()
        return JSONResponse(
            {"status": "bereit" if db_ok else "datenbank nicht erreichbar",
             "datenbank": db_ok},
            status_code=200 if db_ok else 503,
        )

    @app.post("/api/bc0/uebergabe")
    async def uebergabe(request: Request):
        """Der Endpunkt, auf den BC0 seit dem 09.09.2026 wartet."""
        if not _schluessel_stimmt(request):
            return JSONResponse(
                {"fehler": "Schluessel fehlt oder stimmt nicht."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            daten = await request.json()
        except Exception:  # noqa: BLE001
            return JSONResponse({"fehler": "Rumpf ist kein gueltiges JSON."}, status_code=400)

        paket, fehler = pruefe_nutzlast(daten)
        if fehler:
            return JSONResponse({"fehler": fehler}, status_code=400)
        assert paket is not None

        try:
            neu = app.state.buch.eintragen(paket)
        except Exception as e:  # noqa: BLE001
            # 503 und nicht 500: hier lohnt ein Wiederholungsversuch, und genau
            # das soll BC0 an der Antwort erkennen koennen.
            log.error("Ablage fehlgeschlagen fuer %s: %s", paket.paket_id, e)
            return JSONResponse(
                {"fehler": "Ablage nicht erreichbar. Spaeter erneut versuchen."},
                status_code=503,
            )

        log.info(
            "Paket %s (%s, %d Teilprozesse) %s",
            paket.paket_id,
            paket.company_id,
            len(paket.nutzlast.get("teilprozesse", [])),
            "angenommen" if neu else "lag bereits",
        )
        return JSONResponse(
            {
                "paket_id": paket.paket_id,
                "status": "angenommen" if neu else "bereits_angenommen",
            },
            status_code=202,
        )

    @app.post("/api/intern/abgleich")
    def abgleich(request: Request):
        """Nachhol-Abgleich auf Knopfdruck.

        Der Rückfallweg gegen ``v_uebergabe_offen``. Damit hängt BC2 nicht an
        BC0s Push, und niemand braucht Wiederholungslogik.
        """
        if not _schluessel_stimmt(request):
            return JSONResponse(
                {"fehler": "Schluessel fehlt oder stimmt nicht."}, status_code=401
            )
        try:
            neu = _abgleichen(app.state.buch)
        except Exception as e:  # noqa: BLE001
            log.error("Abgleich fehlgeschlagen: %s", e)
            return JSONResponse(
                {"fehler": "Datenbank nicht erreichbar."}, status_code=503
            )
        return JSONResponse({"nachgeholt": len(neu), "paket_ids": neu})

    return app


app = erzeuge_app()
