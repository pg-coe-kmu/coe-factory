"""FastAPI-Transportschicht um process_turn.

Zustandslos gegenüber der Fachlogik: Persistenz macht der Kern (Architektur-
Invariante). Hier liegen nur die laut Design-Spec an die Transportschicht
delegierten Pflichten: schema_version-Check im Request und aktives
Zurückweisen neuer Nachrichten an fertige Sessions (Gate 0).
"""
from __future__ import annotations

import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from bc1_core.core import PaketKonfliktError, process_turn
from bc1_core.llm import LLMClient
from bc1_core.package import UseCasePackage
from bc1_core.store import StaleStateError, StateStore
from bc1_core.types import SessionStatus


class TurnRequest(BaseModel):
    # Leere IDs sind keine gültigen Schlüssel (Session-Bindung, Idempotenz).
    session_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    message: str
    schema_version: str | None = None


def create_app(
    store: StateStore,
    llm: LLMClient,
    package: UseCasePackage,
    snapshot=None,
) -> FastAPI:
    app = FastAPI(title="BC1 Context Discovery", version="0.2.0")

    # Ein Lock je Session: /turn liest den State (Gate) und lässt ihn vom Kern
    # fortschreiben — zwei gleichzeitige Turns derselben Session würden sonst
    # auf demselben Stand rechnen und einer den Versions-Wettlauf verlieren.
    # Gilt für den EIN-Prozess-Betrieb (uvicorn, ein Worker). Mehrere Prozesse
    # brauchen einen Turn-Claim im Store — nachgehalten als Roadmap-Anker;
    # bis dahin ist der StaleStateError->409-Pfad unten das Sicherheitsnetz.
    session_locks: dict[str, threading.Lock] = {}
    register_lock = threading.Lock()

    def _session_lock(session_id: str) -> threading.Lock:
        with register_lock:
            return session_locks.setdefault(session_id, threading.Lock())

    @app.get("/gesundheit")
    def gesundheit() -> dict:
        return {
            "status": "ok",
            "paket": package.name,
            "schema_version": package.schema_version,
        }

    @app.get("/prozesse")
    def prozesse() -> dict:
        if snapshot is None:
            raise HTTPException(status_code=404, detail="kein_snapshot_konfiguriert")
        return {"prozesse": snapshot.prozess_liste()}

    @app.post("/turn")
    def turn(req: TurnRequest) -> dict:
        if (req.schema_version is not None
                and req.schema_version != package.schema_version):
            raise HTTPException(status_code=409, detail="schema_version_passt_nicht")
        with _session_lock(req.session_id):
            state = store.load(req.session_id)
            if (state is not None
                    and state.status is SessionStatus.FERTIG
                    and req.message_id not in state.processed_message_ids):
                # Nur WIRKLICH neue Nachrichten werden abgewiesen. Bereits
                # bekannte (auch unbeantwortete) gehen an den Kern — er ist die
                # eine Stelle, die Idempotenz und Crash-Resume entscheidet.
                raise HTTPException(
                    status_code=409, detail="session_abgeschlossen")
            try:
                antwort = process_turn(
                    store, llm, package,
                    req.session_id, req.message_id, req.message,
                )
            except PaketKonfliktError:  # Paket-/Versions-Guard des Kerns
                raise HTTPException(status_code=409, detail="paket_konflikt")
            except StaleStateError:
                # Verlorener Schreib-Wettlauf: fachlich ein Konflikt, kein
                # Serverfehler. Der Client darf die Nachricht wiederholen.
                raise HTTPException(
                    status_code=409, detail="gleichzeitige_anfrage")
            antwort["chat_text"] = _chat_text(antwort)
            return antwort

    return app


def _chat_text(antwort: dict) -> str:
    if antwort["status"] == "frage":
        return antwort["payload"]["naechste_frage"] or ""
    if antwort["status"] == "fertig":
        v = antwort["payload"]["vollstaendigkeit"]
        return f"Danke! Das Interview ist abgeschlossen (Vollständigkeit: {v:.0%})."
    return ("Da ist gerade etwas schiefgegangen — "
            "bitte schick deine Nachricht einfach noch einmal.")
