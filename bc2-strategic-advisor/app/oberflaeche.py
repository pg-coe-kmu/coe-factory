"""
BC2 · Die Endpunkte, von denen die Oberfläche lebt (#243, Fassung D aus #167).

Fünf Rufe, mehr braucht die Seite nicht:

======================================================  ====================================
``GET  /api/oberflaeche/zustand``                       Was trägt gerade, und was nicht
``GET  /api/oberflaeche/laeufe``                        Die Liste der Läufe — der Einstieg
``GET  /api/oberflaeche/laeufe/{paket_id}``             Ein Lauf samt Gate-1-Stand
``POST /api/oberflaeche/laeufe/{paket_id}/gate1``       Die Entscheidung
``POST /api/oberflaeche/laeufe/{paket_id}/praesentation``  Der Foliensatz, nur nach Freigabe (#257)
``POST /api/oberflaeche/laeufe/{paket_id}/neu``         Neue Fassung nach Reject (#290)
======================================================  ====================================

**Die Prüfung liegt hier, nicht im Browser.** Fassung D verlangt eine Begründung
für jede Nicht-Freigabe und hält Gate 1 sonst geschlossen. Im Prototyp war das
ein ausgegrauter Knopf — wer die Seite umging, kam daran vorbei. Eine Regel, die
nur die Anzeige kennt, ist keine Regel. ``gate1.pruefe`` läuft deshalb auf dem
Server, und die Oberfläche spiegelt sie nur vor, damit der Mensch nicht bis zum
Absenden warten muss.

**Zur Anmeldung.** BC2 hat keine Nutzerverwaltung, und für #243 eine zu bauen
hiesse, ein zweites Vorhaben in ein Ticket zu legen. Die Oberfläche weist sich
deshalb mit **demselben** ``BC2_TRIGGER_TOKEN`` aus wie BC0 — ein Geheimnis,
kein neues. Daraus folgt aber, dass der Dienst **nicht weiss, wer** entscheidet:
``gate1.entscheider`` ist eine Selbstauskunft, die der Mensch einträgt, keine
Authentifizierung. Das ist für ein Studienprojekt vertretbar und für einen
echten Gate-1-Beschluss nicht; es steht als Befund am Ticket.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from ablage import NeulaufNichtErlaubt
from gate1 import (
    Gate1Buch,
    Gate1Entscheidung,
    Gate1Konflikt,
    LaufUnbekannt,
    NichtFreigegeben,
    jetzt,
    pruefe,
)
from laeufe import Laufquelle
from praesentation import DATEINAME, als_bytes, baue_praesentation

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

log = logging.getLogger("bc2.oberflaeche")

STATIC = Path(__file__).resolve().parent / "static"


def _fehler(text: str, code: int = 400, **weiteres) -> JSONResponse:
    return JSONResponse({"fehler": text, **weiteres}, status_code=code)


def erzeuge_router(
    quelle: Laufquelle,
    buch: Gate1Buch,
    schluessel_stimmt,
    ablage_art: str,
) -> APIRouter:
    """Baut die Routen.

    ``schluessel_stimmt`` wird hereingereicht statt importiert: die Prüfung
    gehört dem Endpunkt-Modul, und dieses Modul soll nicht davon abhängen, wie
    BC0s Signatur aussieht. ``ablage_art`` sagt der Oberfläche, ob ihre
    Entscheidung einen Neustart überlebt.

    Lieferdateien schreibt der Dienst nicht: der Lieferordner ist eine
    Abbildung von Schema ``bc2`` und wird mit ``tools/lieferung_ziehen.py``
    gezogen (ADR-007 · BC2, Nachtrag #305).
    """
    router = APIRouter(prefix="/api/oberflaeche")

    def _wache(request: Request) -> JSONResponse | None:
        if schluessel_stimmt(request):
            return None
        return _fehler("Schluessel fehlt oder stimmt nicht.", 401)

    @router.get("/zustand")
    def zustand(request: Request):
        """Was die Oberfläche über ihre eigene Lage wissen muss.

        Sie sagt dem Menschen an, dass seine Entscheidung im Arbeitsspeicher
        liegt, statt Dauerhaftigkeit vorzutäuschen — dieselbe Regel wie bei
        fehlenden Zahlen (#167, Frage 6): lieber ein Etikett als eine
        Behauptung.
        """
        if (abweisung := _wache(request)) is not None:
            return abweisung
        return JSONResponse(
            {
                "ablage": ablage_art,
                "fluechtig": ablage_art == "arbeitsspeicher",
                "neulauf": hasattr(quelle, "neu_rechnen"),
                "hinweis": (
                    "Die Gate-1-Entscheidung liegt im Arbeitsspeicher des Dienstes "
                    "und ist nach einem Neustart weg — der Dienst laeuft ohne "
                    "Datenbank (DATABASE_URL fehlt)."
                )
                if ablage_art == "arbeitsspeicher"
                else "",
            }
        )

    @router.get("/laeufe")
    def liste(request: Request, company_id: str | None = None):
        """Die Läufe — der Einstieg, keine Profilwahl (#167, Frage 1)."""
        if (abweisung := _wache(request)) is not None:
            return abweisung

        koepfe = quelle.uebersicht(company_id)
        eintraege = []
        for kopf in koepfe:
            entscheidung = buch.lesen(kopf.paket_id, kopf.fassung)
            zeile = kopf.als_json()
            if entscheidung is not None:
                zeile["gate1_status"] = entscheidung.status
            eintraege.append(zeile)
        return JSONResponse({"laeufe": eintraege})

    @router.get("/laeufe/{paket_id}")
    def lauf(request: Request, paket_id: str):
        """Ein Lauf in Vertragsform, dazu der bisherige Gate-1-Stand."""
        if (abweisung := _wache(request)) is not None:
            return abweisung

        ansicht = quelle.ansicht(paket_id)
        if ansicht is None:
            return _fehler(f"Kein Lauf mit paket_id {paket_id!r}.", 404)

        antwort = ansicht.als_json()
        entscheidung = buch.lesen(paket_id, ansicht.kopf.fassung)
        antwort["gate1"] = (
            entscheidung.als_vertrag() if entscheidung is not None else {"status": "pending"}
        )
        return JSONResponse(antwort)

    @router.post("/laeufe/{paket_id}/gate1")
    async def entscheiden(request: Request, paket_id: str):
        """Nimmt die Entscheidung entgegen — **oder weist sie begründet ab**."""
        if (abweisung := _wache(request)) is not None:
            return abweisung

        ansicht = quelle.ansicht(paket_id)
        if ansicht is None:
            return _fehler(f"Kein Lauf mit paket_id {paket_id!r}.", 404)

        try:
            daten = await request.json()
        except Exception:  # noqa: BLE001
            return _fehler("Rumpf ist kein gueltiges JSON.")
        if not isinstance(daten, dict):
            return _fehler("Rumpf muss ein JSON-Objekt sein.")

        try:
            nicht_frei = tuple(
                NichtFreigegeben(
                    potenzial_id=str(n["potenzial_id"]),
                    begruendung=str(n.get("begruendung", "")),
                )
                for n in daten.get("nicht_freigegeben", [])
            )
        except (TypeError, KeyError):
            return _fehler(
                "nicht_freigegeben muss eine Liste aus {potenzial_id, begruendung} sein."
            )

        # Die Oberfläche schickt mit, über welche Fassung sie entschieden hat.
        # Liegt inzwischen eine andere, hat sie auf einem alten Stand gearbeitet
        # — das ist ein Konflikt, keine Entscheidung über die neue Fassung.
        fassung = ansicht.kopf.fassung
        if "fassung" in daten and daten["fassung"] != fassung:
            return _fehler(
                f"Entschieden wurde ueber Fassung {daten['fassung']}, es gilt Fassung "
                f"{fassung}. Bitte neu laden.",
                409,
            )

        entscheidung = Gate1Entscheidung(
            paket_id=paket_id,
            company_id=ansicht.kopf.company_id,
            status=str(daten.get("status", "")),
            fassung=fassung,
            approved_potenzial_ids=tuple(daten.get("approved_potenzial_ids", [])),
            nicht_freigegeben=nicht_frei,
            finale_reihenfolge_potenzial_ids=tuple(
                daten.get("finale_reihenfolge_potenzial_ids", [])
            ),
            finale_prozessreihenfolge_kp_ids=tuple(
                daten.get("finale_prozessreihenfolge_kp_ids", [])
            ),
            abweichungsbegruendung=str(daten.get("abweichungsbegruendung", "")),
            entscheider=str(daten.get("entscheider", "")),
            kommentar=str(daten.get("kommentar", "")),
            entschieden_am=jetzt(),
        )

        maengel = pruefe(
            entscheidung,
            potenzial_ids=ansicht.potenzial_ids(),
            kp_ids=ansicht.kp_ids(),
            gerechnete_reihenfolge=ansicht.potenzial_ids(),
            gerechnete_prozessfolge=ansicht.kp_ids(),
        )
        if maengel:
            # 422 und nicht 400: der Rumpf war wohlgeformt, die Entscheidung
            # aber nicht zulässig. Die Oberfläche unterscheidet daran, ob sie
            # einen Programmierfehler oder eine Rückfrage an den Menschen hat.
            return _fehler(
                "Die Entscheidung ist so nicht zulaessig.", 422, maengel=maengel
            )

        try:
            buch.merken(entscheidung)
        except Gate1Konflikt as e:
            # 409: kein Formfehler, sondern ein anderer war schneller oder die
            # Seite zeigt einen alten Stand. Der geltende Stand kommt mit, damit
            # die Oberfläche ihn anzeigen kann, statt ihn zu überschreiben.
            geltend = buch.lesen(paket_id, fassung)
            return _fehler(
                str(e),
                409,
                gate1=geltend.als_vertrag() if geltend is not None else {"status": e.bisher},
            )
        except LaufUnbekannt:
            return _fehler(f"Zu {paket_id} liegt kein abgelegter Lauf.", 409)
        log.info(
            "Gate 1 fuer %s: %s (%d freigegeben, %d herausgenommen) durch %r",
            paket_id,
            entscheidung.status,
            len(entscheidung.approved_potenzial_ids),
            len(entscheidung.nicht_freigegeben),
            entscheidung.entscheider or "(ohne Angabe)",
        )
        return JSONResponse(
            {"paket_id": paket_id, "fassung": fassung, "gate1": entscheidung.als_vertrag()},
            status_code=200,
        )

    @router.post("/laeufe/{paket_id}/praesentation")
    def praesentation(request: Request, paket_id: str):
        """Zeichnet den Foliensatz des Laufs — **nur nach Freigabe** (#244, #257).

        Die Präsentation geht an den **Mandanten**, nicht an BC3: sie ist
        Download, kein Teil der Lieferung (ADR-007 · BC2, Nachtrag #305,
        Punkt 4). Abgelegt wird sie darum nirgends.

        ``POST`` und nicht ``GET``, wie bisher — der Knopf in der Oberfläche
        ruft es so.
        """
        if (abweisung := _wache(request)) is not None:
            return abweisung

        ansicht = quelle.ansicht(paket_id)
        if ansicht is None:
            return _fehler(f"Kein Lauf mit paket_id {paket_id!r}.", 404)

        entscheidung = buch.lesen(paket_id, ansicht.kopf.fassung)
        if entscheidung is None or entscheidung.status != "approved":
            stand = entscheidung.status if entscheidung is not None else "pending"
            # 409: der Lauf existiert, aber sein Zustand erlaubt es nicht. Vor der
            # Freigabe zeigte die Präsentation eine Reihenfolge, die der Mensch
            # noch überschreiben darf; bei Ablehnung entsteht sie gar nicht
            # (ADR-007, 2.3).
            return _fehler(
                f"Die Praesentation entsteht erst nach der Freigabe am Gate 1 "
                f"(Stand: {stand}).",
                409,
            )

        konzepte, priorisierung = ansicht.als_vertrag(entscheidung.als_vertrag())
        daten = als_bytes(
            baue_praesentation(
                konzepte,
                priorisierung,
                sperrgrund=ansicht.kopf.sperrgrund,
                hinweise=ansicht.kopf.hinweise,
            )
        )
        log.info("Praesentation fuer %s erzeugt (%d Bytes)", paket_id, len(daten))
        return Response(
            daten,
            media_type=PPTX,
            headers={"Content-Disposition": f'attachment; filename="{DATEINAME}"'},
        )

    @router.post("/laeufe/{paket_id}/neu")
    def neu_rechnen(request: Request, paket_id: str):
        """Rechnet die nächste Fassung — **nur nach Reject** (ADR-008 · BC2, 2.1).

        Nach ``approved`` gibt es keine: die Freigabe ist die Übergabe an BC3,
        und neue Daten kommen als neues Paket von BC0. Ob die Bedingung gilt,
        entscheidet die Ablage, nicht diese Route — ein Doppelklick läuft dort
        auf den partiellen Index.
        """
        if (abweisung := _wache(request)) is not None:
            return abweisung
        if not hasattr(quelle, "neu_rechnen"):
            return _fehler("Ohne Ablage gibt es keine Fassungen.", 501)
        try:
            ansicht = quelle.neu_rechnen(paket_id)
        except NeulaufNichtErlaubt as e:
            return _fehler(str(e), 409)
        if ansicht is None:
            return _fehler(f"Kein Lauf mit paket_id {paket_id!r}.", 404)
        log.info("Neue Fassung %d fuer %s", ansicht.kopf.fassung, paket_id)
        antwort = ansicht.als_json()
        antwort["gate1"] = {"status": "pending"}
        return JSONResponse(antwort, status_code=201)

    return router


def erzeuge_seiten_router() -> APIRouter:
    """Liefert die Oberfläche selbst aus.

    Eine Datei, kein Bauschritt, über ``StaticFiles`` — die Technikentscheidung
    aus #167 Frage 8, gemessen an BC0s PWA. Eine eigene Route statt einer
    Einhängung unter ``/static``, damit die Seite unter ``/`` liegt und nicht
    unter einem Pfad, den sich niemand merkt.
    """
    router = APIRouter()
    kopf = {"Content-Security-Policy": seiten_csp((STATIC / "index.html").read_text("utf-8"))}

    @router.get("/", include_in_schema=False)
    def seite():
        return FileResponse(STATIC / "index.html", headers=kopf)

    return router


def seiten_csp(html: str) -> str:
    """Die Content-Security-Policy der Seite — so eng, wie die eine Datei es zulässt.

    Caddy schickt für alles ``default-src 'none'`` (#190: „hier liegt keine
    Oberfläche, nur JSON“) und setzt das seither nur noch, wenn die Anwendung
    keine eigene Policy mitgibt. Die Seite braucht genau dreierlei: ihr
    **eines** Inline-Skript, ihre ``style``-Attribute und ``fetch`` auf den
    eigenen Ursprung. Das Skript wird über seinen Hash erlaubt, nicht über
    ``'unsafe-inline'``; der Hash entsteht hier beim Start aus der Datei, damit
    eine Änderung an ihr nicht an einer zweiten Stelle nachzuziehen ist.

    ``style-src 'unsafe-inline'`` ist der Preis der Ein-Datei-Oberfläche (#167):
    die Seite setzt ``style``-Attribute in erzeugtem HTML, und die deckt kein
    Hash. Ein Stil kann kein Skript ausführen.
    """
    skripte = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"
        for s in skripte
    )
    return (
        f"default-src 'none'; script-src {hashes}; style-src 'unsafe-inline'; "
        "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"
    )
