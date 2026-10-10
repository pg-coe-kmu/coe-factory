"""
Die Oberfläche im echten Browser (#243).

**Warum es diese Datei gibt.** ``test_oberflaeche.py`` prüft die API und war
vollständig grün, während die Seite einen Fehler trug, den nur ein Browser
zeigt: der Freigabeknopf blieb gesperrt, obwohl die Begründung dastand. Ursache
war die Regel ``wurdeUmsortiert()`` im JavaScript — die Gliederung nach
Kernprozess weicht von sich aus vom gerechneten Rang ab (Befund 2 aus #167), und
die Seite hielt das für einen Eingriff des Menschen.

Das ist **dieselbe Lücke wie bei #190/#205**: ein einseitiger Test erreicht die
Naht zwischen zwei Seiten nicht. Dort war es die Naht zwischen BC0 und BC2, hier
die zwischen JavaScript und API. Grüne API-Tests belegen nicht, dass die Seite
bedienbar ist.

Gefahren wird hinter einem Schalter, weil Playwright einen Browser mitbringt und
in der Vorschleife nicht überall bezahlbar ist::

    /tmp/bc2v13/bin/pip install playwright && playwright install chromium
    BC2_BROWSERTEST=1 python -m pytest tests/test_oberflaeche_browser.py -q

Ohne den Schalter überspringen die Tests — sichtbar, nicht stillschweigend.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BC2_BROWSERTEST") != "1",
    reason="Browsertest laeuft nur mit BC2_BROWSERTEST=1 (braucht Playwright + Chromium).",
)

playwright_modul = pytest.importorskip("playwright.sync_api", reason="playwright fehlt")
sync_playwright = playwright_modul.sync_playwright

MESSSAETZE = Path(__file__).resolve().parent.parent.parent / "kalibrierung"
SCHLUESSEL = "browsertest-schluessel"


def _freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _starte(anwendung):
    import uvicorn

    port = _freier_port()
    server = uvicorn.Server(
        uvicorn.Config(anwendung, host="127.0.0.1", port=port, log_level="error")
    )
    faden = threading.Thread(target=server.run, daemon=True)
    faden.start()

    frist = time.time() + 15
    while not server.started and time.time() < frist:
        time.sleep(0.05)
    assert server.started, "Der Dienst ist nicht angelaufen."

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    faden.join(timeout=10)


@pytest.fixture(scope="module")
def dienst():
    """Startet den Dienst in einem Nebenläufer — mit Speicher-Ablagen."""
    from app import erzeuge_app
    from eingang import SpeicherEingangsbuch
    from gate1 import SpeicherGate1Buch
    from laeufe import MesssatzLaufquelle

    with _starte(erzeuge_app(
        SpeicherEingangsbuch(),
        laufquelle=MesssatzLaufquelle(MESSSAETZE),
        gate1_buch=SpeicherGate1Buch(),
    )) as url:
        yield url


@pytest.fixture
def dienst_mit_ablage():
    """Ein eigener Dienst mit dem Ablage-Stapel aus #290 — Fassungen, Endgültigkeit.

    Eigener Dienst, nicht der des Moduls: dort hat ein früherer Test den Lauf
    freigegeben, und nach ``approved`` gibt es keine neue Fassung.
    """
    from ablage import AblegendeLaufquelle, SpeicherErgebnisbuch
    from app import erzeuge_app
    from eingang import SpeicherEingangsbuch
    from gate1 import SpeicherGate1Buch
    from laeufe import MesssatzLaufquelle

    ergebnisse = SpeicherErgebnisbuch()
    with _starte(erzeuge_app(
        SpeicherEingangsbuch(),
        laufquelle=AblegendeLaufquelle(MesssatzLaufquelle(MESSSAETZE), ergebnisse),
        gate1_buch=SpeicherGate1Buch(ergebnisse=ergebnisse),
    )) as url:
        yield url


@pytest.fixture
def seite(dienst):
    with _angemeldet(dienst) as blatt:
        yield blatt


@pytest.fixture
def seite_mit_ablage(dienst_mit_ablage):
    with _angemeldet(dienst_mit_ablage) as blatt:
        yield blatt


@contextmanager
def _angemeldet(url, warte_auf: str = ".kpblock"):
    """Eine angemeldete Seite, mit scharfem Blick auf Konsolenfehler.

    Ein Fehler im JavaScript macht die Seite nicht kaputt genug, um aufzufallen
    — ein halb gezeichneter Zustand sieht aus wie ein Zustand. Deshalb wird
    jeder Konsolenfehler gesammelt und am Ende zum Testfehler.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        blatt = browser.new_page(viewport={"width": 1500, "height": 1000})
        fehler: list[str] = []
        blatt.on("pageerror", lambda e: fehler.append(f"Seitenfehler: {e}"))

        def _konsole(meldung):
            if meldung.type != "error":
                return
            # „Failed to load resource" ist die Meldung des Browsers über einen
            # HTTP-Status, kein Skriptfehler. Ein abgewiesener 422 ist hier ein
            # **erwarteter** Fall — die Seite soll ihn anzeigen, und genau das
            # prüft `test_der_serverfehler_wird_angezeigt…`. Würde er als
            # Browserfehler zählen, schlüge der Test an seinem eigenen Vorsatz
            # fehl.
            if "Failed to load resource" in meldung.text:
                return
            fehler.append(f"Konsole: {meldung.text}")

        blatt.on("console", _konsole)

        blatt.goto(url, wait_until="networkidle")
        blatt.fill("#schluesselfeld", SCHLUESSEL)
        blatt.click("#anmelden")
        blatt.wait_for_selector(warte_auf, timeout=10_000)

        yield blatt

        browser.close()
        assert not fehler, "Fehler im Browser: " + " | ".join(fehler)


@pytest.fixture(autouse=True)
def _schluessel(monkeypatch):
    monkeypatch.setenv("BC2_TRIGGER_TOKEN", SCHLUESSEL)


# ---------------------------------------------------------------------------


def test_die_liste_wird_gezeichnet(seite):
    """Akkordeon je Kernprozess, eine Zeile je Potenzial."""
    assert seite.locator(".kpblock").count() >= 1
    assert seite.locator(".dzeile").count() >= 1


def test_der_vorschlag_ist_vorbelegt_und_braucht_keine_begruendung(seite):
    """**Der Fehler, den die API-Tests nicht fanden.**

    Beim ersten Laden ist alles freigegeben, nichts umsortiert — Gate 1 muss
    offen stehen. Die Vorgängerfassung verlangte hier eine
    Abweichungsbegründung, weil sie die Gliederung nach Kernprozess für einen
    Eingriff hielt.
    """
    assert seite.evaluate("() => Z.freigegeben.size") == seite.locator(".dzeile").count()
    assert seite.evaluate("() => wurdeUmsortiert()") is False
    assert seite.locator('[data-tat="approved"]').is_disabled() is False


def test_nicht_freigabe_sperrt_gate_1_bis_die_begruendung_steht(seite):
    knopf = seite.locator('[data-tat="approved"]')

    seite.locator("input[data-frei]").first.uncheck()
    seite.wait_for_selector(".grundfeld.fehlt")
    assert knopf.is_disabled(), "Ohne Begruendung darf Gate 1 nicht aufgehen."

    seite.locator("textarea[data-ablehnung]").first.fill(
        "Haengt an einer Schnittstelle, die erst im naechsten Quartal steht."
    )
    seite.wait_for_timeout(200)
    assert not knopf.is_disabled(), "Mit Begruendung muss Gate 1 aufgehen."


def test_umsortieren_verlangt_eine_begruendung(seite):
    knopf = seite.locator('[data-tat="approved"]')
    assert not knopf.is_disabled()

    # ↑/↓ statt Ziehen: das ist die Auflage aus #167 (Ziehen ist Maus-Bedienung).
    seite.locator("[data-kprunter]").first.click()
    seite.wait_for_timeout(300)

    assert seite.evaluate("() => wurdeUmsortiert()") is True
    assert seite.locator("textarea[data-abweichung]").count() == 1
    assert knopf.is_disabled(), "Eine unbegruendete Abweichung darf Gate 1 nicht aufmachen."

    seite.locator("textarea[data-abweichung]").fill(
        "Der Abrechnungsprozess bindet Personal im Quartalsschluss."
    )
    seite.wait_for_timeout(200)
    assert not knopf.is_disabled()


def test_zurueckschieben_ist_keine_abweichung(seite):
    """Wer etwas verschiebt und wieder zurückschiebt, schuldet keine Begründung."""
    seite.locator("[data-kprunter]").first.click()
    seite.wait_for_timeout(200)
    assert seite.evaluate("() => wurdeUmsortiert()") is True

    seite.locator("[data-kphoch]").nth(1).click()
    seite.wait_for_timeout(200)
    assert seite.evaluate("() => wurdeUmsortiert()") is False


def test_quer_ueber_prozessgrenzen_wird_nicht_sortiert(seite):
    """Die ↑/↓ eines Potenzials enden an seinem Kernprozess.

    Ein Potenzial in einen anderen Kernprozess zu schieben wäre **Umhängen**,
    und das ist am Gate 1 nicht vorgesehen — das Konzept geht je Kernprozess
    an BC3.
    """
    zuordnung_vorher = seite.evaluate(
        "() => Object.fromEntries(Z.ansicht.eintraege.map(e => [e.potenzial_id, e.kp_id]))"
    )
    # Das erste Potenzial des ersten Blocks kann nicht weiter nach oben.
    erstes = seite.locator(".kpblock").first.locator("[data-hoch]").first
    assert erstes.is_disabled()

    # Das letzte kann nicht weiter nach unten — auch nicht in den naechsten Block.
    letztes = seite.locator(".kpblock").first.locator("[data-runter]").last
    assert letztes.is_disabled()

    zuordnung_nachher = seite.evaluate(
        "() => Object.fromEntries(Z.ansicht.eintraege.map(e => [e.potenzial_id, e.kp_id]))"
    )
    assert zuordnung_vorher == zuordnung_nachher


def test_fehlende_value_zahl_zeigt_ein_etikett_und_keine_null(seite):
    """#167 Frage 6 — in der gezeichneten Seite, nicht nur im JSON."""
    hat_fall = seite.evaluate(
        "() => Z.ansicht.eintraege.some(e => !e.einsparung_eur_jahr)"
    )
    if not hat_fall:
        pytest.skip("Der Messsatz traegt keinen Fall ohne Value-Zahl.")

    assert seite.locator(".dzeile .wert .tag.fehlt").count() >= 1
    text = seite.locator(".dzeile .wert .tag.fehlt").first.inner_text()
    assert "keine Value-Zahl" in text
    assert "0 €" not in seite.locator(".kpinhalt").first.inner_text()


def test_die_matrix_verdeckt_keinen_punkt(seite):
    """Fund 4 aus #167: gleiche Koordinaten dürfen sich nicht überlagern."""
    seite.locator('[data-sicht="matrix"]').click()
    seite.wait_for_selector(".matrixkarte svg")

    anzahl = seite.locator(".punkt").count()
    assert anzahl == seite.evaluate("() => Z.ansicht.eintraege.length")

    mittelpunkte = seite.evaluate(
        """() => [...document.querySelectorAll('.punkt circle')]
                 .map(c => c.getAttribute('cx') + ':' + c.getAttribute('cy'))"""
    )
    assert len(set(mittelpunkte)) == len(mittelpunkte), "Zwei Punkte liegen uebereinander."


def test_die_schublade_zeigt_das_detail(seite):
    seite.locator(".dzeile .titel").first.click()
    seite.wait_for_selector(".schublade")
    text = seite.locator(".schublade").inner_text()
    for ueberschrift in ("Aufwand heute", "Automatisierungsgrad", "Nutzwert", "Die beiden Achsen"):
        assert ueberschrift in text
    # Ein Messsatz hat keinen Ausarbeitungsschritt — die Lücke wird angesagt (#301).
    assert "Die Texte liegen nicht vor" in text


def test_der_ganze_weg_bis_zur_freigabe(seite):
    """Freigeben, neu laden, und der Stand steht wieder da."""
    seite.fill("input[data-entscheider]", "S. Morazan")
    seite.locator('[data-tat="approved"]').click()
    seite.wait_for_selector("#meldung .hinweis", timeout=5000)
    assert "freigegeben" in seite.locator("#meldung").inner_text()

    seite.reload(wait_until="networkidle")
    seite.wait_for_selector(".kpblock", timeout=10_000)
    assert seite.evaluate("() => Z.gate1.status") == "approved"
    assert "freigegeben" in seite.locator(".laufkopf").inner_text()


def test_der_serverfehler_wird_angezeigt_und_nicht_verschluckt(seite):
    """Weist der Server ab, muss die Seite den Mangel zeigen.

    Sonst hielte der Mensch eine abgewiesene Entscheidung für gespeichert —
    der teuerste denkbare Fehler an dieser Stelle.
    """
    # Eine Entscheidung am Server vorbei bauen, die er ablehnen muss.
    seite.evaluate(
        """() => {
            Z.freigegeben.clear();
            Z.ansicht.eintraege.forEach(e => Z.ablehnungsgrund[e.potenzial_id] =
                'Kommt in dieser Runde nicht mit.');
            zeichne();
        }"""
    )
    seite.evaluate("() => entscheiden('approved')")
    seite.wait_for_selector("#meldung .hinweis.warn", timeout=5000)
    assert "nicht zulässig" in seite.locator("#meldung").inner_text()


def test_nach_der_freigabe_laesst_sich_die_praesentation_herunterladen(seite_mit_ablage):
    """Der Knopf erscheint erst nach der Freigabe und liefert eine echte PPTX (#257).

    Eigener Dienst: im Moduldienst hat ein früherer Test den Lauf schon
    freigegeben, und seit #290 ist das endgültig — eine zweite Freigabe wäre
    ein 409, kein neuer Anfang.
    """
    seite = seite_mit_ablage
    assert seite.locator("[data-praesentation]").count() == 0
    seite.fill("input[data-entscheider]", "S. Morazan")
    seite.locator('[data-tat="approved"]').click()
    seite.wait_for_selector("[data-praesentation]", timeout=5000)
    # Ein Messsatz trägt einen Sperrgrund: freigeben ja, liefern nein (#305).
    assert "freigegeben, nicht lieferbar" in seite.locator(".fussleiste").inner_text()

    with seite.expect_download(timeout=10_000) as laden:
        seite.locator("[data-praesentation]").click()
    download = laden.value
    assert download.suggested_filename == "praesentation.pptx"
    assert Path(download.path()).read_bytes()[:2] == b"PK"
    seite.wait_for_selector("#meldung .hinweis", timeout=5000)
    assert "liegt nicht im Lieferordner" in seite.locator("#meldung").inner_text()


def test_nach_reject_rechnet_der_knopf_die_naechste_fassung(seite_mit_ablage):
    """Reject → „neu rechnen“ → Fassung 2, Gate 1 wieder offen (ADR-008 · BC2, 2.1).

    Und davor: nach der Entscheidung bietet die Seite keine Knöpfe mehr an,
    die der Server mit 409 abwiese.
    """
    seite = seite_mit_ablage
    seite.on("dialog", lambda d: d.accept("Der Schnitt ist zu grob."))
    seite.locator('[data-tat="rejected"]').click()
    seite.wait_for_selector("[data-neu]", timeout=5000)

    assert seite.locator('[data-tat="approved"]').count() == 0
    assert "endgültig" in seite.locator(".fussleiste").inner_text()

    seite.locator("[data-neu]").click()
    seite.wait_for_function("() => Z.ansicht && Z.ansicht.kopf.fassung === 2", timeout=5000)
    assert seite.evaluate("() => Z.gate1.status") == "pending"
    assert seite.locator('[data-tat="approved"]').count() == 1
    assert "Fassung 2" in seite.locator("#meldung").inner_text()


@pytest.fixture
def seite_mit_kette():
    """Zwei Pakete über dieselben Teilprozesse, das erste freigegeben (#295).

    Das zweite liegt später und steht darum oben in der Auswahl. Der Dienst
    schneidet und verkettet es selbst — auf Auftrag, denn seit dem 10.10.2026
    rechnet Öffnen nicht mehr.
    """
    from datetime import timedelta

    from app import erzeuge_app
    from eingang import SpeicherEingangsbuch
    from laeufe import Paketeintrag
    from test_verknuepfung import NOROAI, STAND, TP1, TP2, _freigeben, _kette, _strecke

    laeufe, _, gate1, _ = _strecke(
        *_kette(),
        pakete=[Paketeintrag("PKT-A", NOROAI, STAND, (TP1, TP2)),
                Paketeintrag("PKT-B", NOROAI, STAND + timedelta(days=1), (TP2,))],
    )
    _freigeben(gate1, laeufe.rechnen("PKT-A", neu=False))
    laeufe.rechnen("PKT-B", neu=False)
    with _starte(erzeuge_app(SpeicherEingangsbuch(), laufquelle=laeufe, gate1_buch=gate1)) as url:
        with _angemeldet(url) as blatt:
            yield blatt


def test_vorgaenger_und_streichliste_stehen_am_gate_1(seite_mit_kette):
    """Die Kette ist Anzeige, kein Editierweg (ADR-009 · BC2 §2.5) — aber sie
    muss zu sehen sein, sonst gibt der Mensch frei, was er nicht gesehen hat."""
    seite = seite_mit_kette
    assert seite.evaluate("() => Z.paket_id") == "PKT-B"

    streichliste = seite.locator("[data-streichliste]")
    assert "Potenzial P2" in streichliste.inner_text()
    assert "Die Einsatzplanung laeuft inzwischen im Projekttool." in streichliste.inner_text()

    marke = seite.locator("[data-vorgaenger]")
    assert marke.count() == 1 and "Potenzial P1" in marke.inner_text()

    seite.locator(".dzeile .titel").first.click()
    seite.wait_for_selector(".schublade")
    text = seite.locator(".schublade").inner_text()
    assert "Fortgeschrieben" in text
    # Der echte Weg trägt die Texte des Ausarbeitungsschritts (#301) — sichtbar,
    # mit eingesetztem Automatisierungsgrad statt Platzhalter.
    assert "Als Projektleitung moechte ich" in text and "Akzeptanzkriterien" in text
    assert "{grad_min}" not in text and "ohne Nacharbeit abgerechnet" in text


@pytest.fixture
def seite_teuer():
    """Ein Dienst mit teurer Quelle wie im Betrieb — Rechnen kostet Modellaufrufe."""
    from ablage import AblegendeLaufquelle, SpeicherErgebnisbuch
    from app import erzeuge_app
    from eingang import SpeicherEingangsbuch
    from gate1 import SpeicherGate1Buch

    from test_rechnen_auf_auftrag import TeuereQuelle

    teuer = TeuereQuelle()
    ergebnisse = SpeicherErgebnisbuch()
    with _starte(erzeuge_app(
        SpeicherEingangsbuch(),
        laufquelle=AblegendeLaufquelle(teuer, ergebnisse),
        gate1_buch=SpeicherGate1Buch(ergebnisse=ergebnisse),
    )) as url, _angemeldet(url, warte_auf="[data-rechnen]") as blatt:
        yield blatt, teuer


def test_anmelden_rechnet_nichts_gerechnet_wird_auf_knopfdruck(seite_teuer):
    """Erster echter Lauf (10.10.2026): die Anmeldung öffnete den obersten Lauf und
    rechnete ihn. Jetzt steht er mit seinem Stand da, und gerechnet wird erst auf
    Knopfdruck — die Seite fragt danach selbst nach, bis er da ist."""
    seite, teuer = seite_teuer
    seite.wait_for_selector("[data-rechnen]", timeout=5000)
    assert teuer.gerechnet == 0
    assert "nicht gerechnet" in seite.locator("#laufwahl").inner_text()
    assert "kostet Modellaufrufe" in seite.locator("#buehne").inner_text()

    seite.locator("[data-rechnen]").click()
    seite.wait_for_selector("#buehne h1", timeout=15000)  # „Priorisierung“: der Lauf ist da
    assert teuer.gerechnet == 1
    assert "Potenziale" in seite.locator("#laufwahl").inner_text()


def test_enter_im_schluesselfeld_meldet_an(dienst):
    """Wer den Schlüssel einfügt und Enter drückt, ist angemeldet (10.10.2026)."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        blatt = browser.new_page()
        blatt.goto(dienst, wait_until="networkidle")
        blatt.fill("#schluesselfeld", SCHLUESSEL)
        blatt.press("#schluesselfeld", "Enter")
        blatt.wait_for_selector(".kpblock", timeout=10_000)
        browser.close()


def test_die_seite_laeuft_unter_einem_praefix_mit_eigenem_schluesselfach(monkeypatch):
    """So hängt Caddy die Vorschau unter /vorschau/ ein (Präfix abgeschnitten).
    Die API-Rufe sind relativ und landen beim eingehängten Dienst; der Schlüssel
    liegt in einem eigenen Fach — die Vorschau liest den der echten Seite nie."""
    from starlette.applications import Starlette
    from starlette.routing import Mount

    from app import erzeuge_app
    from eingang import SpeicherEingangsbuch
    from gate1 import SpeicherGate1Buch
    from laeufe import MesssatzLaufquelle

    monkeypatch.setenv("BC2_VORSCHAU", "1")
    innen = erzeuge_app(SpeicherEingangsbuch(), laufquelle=MesssatzLaufquelle(MESSSAETZE),
                        gate1_buch=SpeicherGate1Buch())
    with _starte(Starlette(routes=[Mount("/vorschau", app=innen)])) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            blatt = browser.new_page()
            blatt.goto(url + "/vorschau/", wait_until="networkidle")
            assert blatt.locator(".vorschau-marke").is_visible()
            blatt.fill("#schluesselfeld", SCHLUESSEL)
            blatt.press("#schluesselfeld", "Enter")
            blatt.wait_for_selector(".kpblock", timeout=10_000)
            faecher = blatt.evaluate("() => Object.keys(sessionStorage)")
            browser.close()
    assert faecher == ["bc2-gate1-schluessel:/vorschau/"]
