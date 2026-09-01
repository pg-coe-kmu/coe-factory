"""FastAPI-Transportschicht um process_turn.

Zustandslos gegenüber der Fachlogik: Persistenz macht der Kern (Architektur-
Invariante). Hier liegen nur die laut Design-Spec an die Transportschicht
delegierten Pflichten: Mandanten-Guard vor jeder anderen Prüfung,
schema_version-Check im Request und aktives Zurückweisen neuer Nachrichten
an Sessions in einem Endzustand (fertig oder abgebrochen ohne Identität —
Gate 0).
"""
from __future__ import annotations

import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from bc1_core.core import (MandantKonfliktError, PaketKonfliktError,
                           darf_recovery_replay, ist_terminal, process_turn,
                           pruefe_mandant)
from bc1_core.llm import LLMClient
from bc1_core.package import UseCasePackage
from bc1_core.store import StaleStateError, StateStore

# Fester, LLM-freier Wortlaut (Spec K0): keine Halluzinationsflaeche im
# Terminalzustand, und der Text bleibt ueber Neustarts identisch.
ABBRUCH_TEXT = ("Wir konnten den Prozess-Schritt nicht eindeutig zuordnen. "
                "Bitte starten Sie neu und wählen Sie einen Schritt aus der Liste.")


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
    lifespan=None,
    *,
    company_id: str,
) -> FastAPI:
    # lifespan: Aufhaenger fuers Hoch-/Herunterfahren (main.py schliesst dort
    # den Store). Die Factory kennt den Inhalt nicht — nur den Durchreicher.
    app = FastAPI(title="BC1 Context Discovery", version="0.2.0",
                  lifespan=lifespan)

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
        with _session_lock(req.session_id):
            state = store.load(req.session_id)
            if state is not None:
                # Reihenfolge ist normativ (R12-I1): Mandanten-Guard VOR der
                # Schema-Ausnahme, vor der Replay-Auslieferung, vor dem
                # Terminal-Gate. Diese Pruefung kennt keine Ausnahme.
                try:
                    pruefe_mandant(state, company_id)
                except MandantKonfliktError:
                    raise HTTPException(status_code=409, detail="mandant_konflikt")

            recovery = state is not None and darf_recovery_replay(
                state, package, req.message_id, req.schema_version)

            if (req.schema_version is not None
                    and req.schema_version != package.schema_version
                    and not recovery):
                raise HTTPException(status_code=409,
                                    detail="schema_version_passt_nicht")

            if (state is not None and ist_terminal(state)
                    and req.message_id not in state.processed_message_ids):
                # Nur WIRKLICH neue Nachrichten werden abgewiesen. Bereits
                # bekannte (auch unbeantwortete) gehen an den Kern — er ist die
                # eine Stelle, die Idempotenz und Crash-Resume entscheidet.
                raise HTTPException(status_code=409, detail="session_abgeschlossen")

            try:
                antwort = process_turn(store, llm, package, req.session_id,
                                       req.message_id, req.message,
                                       company_id=company_id,
                                       mitgesendete_version=req.schema_version)
            except PaketKonfliktError:  # Paket-/Versions-Guard des Kerns
                raise HTTPException(status_code=409, detail="paket_konflikt")
            except MandantKonfliktError:
                raise HTTPException(status_code=409, detail="mandant_konflikt")
            except StaleStateError:
                # Verlorener Schreib-Wettlauf: fachlich ein Konflikt, kein
                # Serverfehler. Der Client darf die Nachricht wiederholen.
                raise HTTPException(status_code=409, detail="gleichzeitige_anfrage")
            antwort["chat_text"] = _chat_text(antwort)
            return antwort

    return app


def _fortschrittszeile(p: dict) -> str:
    # Vor diesem Branch persistierte Payloads (Legacy-Replay alter
    # message_ids) kennen die Zähler-Keys noch nicht — tolerant rendern
    # statt KeyError/500 beim Idempotenz-Replay.
    if "pflicht_erfasst" not in p or "pflicht_gesamt" not in p:
        return ""
    return (f"\n\n✓ {p['pflicht_erfasst']} von {p['pflicht_gesamt']} "
            "Pflichtfeldern erfasst")


def _chat_text(antwort: dict) -> str:
    if antwort["status"] == "abgebrochen_ohne_identitaet":
        return ABBRUCH_TEXT           # bewusst ohne Fortschrittszeile: fester Text
    if antwort["status"] == "frage":
        p = antwort["payload"]
        return (p.get("naechste_frage") or "") + _fortschrittszeile(p)
    if antwort["status"] == "fertig":
        p = antwort["payload"]
        return ((p.get("abschluss_text")
                 or "Danke! Das Interview ist abgeschlossen.")
                + _fortschrittszeile(p))
    return ("Da ist gerade etwas schiefgegangen — "
            "bitte schick deine Nachricht einfach noch einmal.")
