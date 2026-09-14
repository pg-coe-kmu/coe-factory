# -*- coding: utf-8 -*-
"""
Tests der Beleg-Ingestion Stufe 2 — Extraktionsweg und Volltextsuche (#139).

Grundlage: `13_Konzepte_Architektur/BC0_OCR_Konzept_Stufe2.md` vom 18.08.2026.

WAS HIER GEPRUEFT WIRD — UND WARUM GERADE DAS
  Der Kern von Stufe 2 ist **eine Weiche**, keine Zeichenerkennung: Wo Text
  als Text vorliegt, wird er verlustfrei ausgelesen; nur Pixel brauchen OCR.

  Das Konzept begruendet es scharf: *„Direktes Auslesen ist hundertprozentig
  genau. OCR hat immer eine Fehlerquote, auch das beste Modell bei sauberem
  Scan — aus einer 3 wird gelegentlich eine 8, aus ‚rn' ein ‚m'. Fuer einen
  Beleg, der eine Reifegradbewertung stuetzt, ist der Unterschied wesentlich.
  Wo direkt ausgelesen werden kann, darf niemals OCR laufen."*

  Die Tests zielen deshalb auf beide Seiten der Weiche — und auf den Fall
  dazwischen, der am ehesten schiefgeht: ein PDF, das nur eine Kopfzeile
  ueber einem Scan traegt und dadurch fast wie ein Textdokument aussieht.
"""

from __future__ import annotations

import io
import os
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as anwendung  # noqa: E402
from app import (  # noqa: E402
    TEXTEBENE_ZEICHEN_JE_SEITE, _belastbarkeit, _fundstelle, text_holen,
)
from bc0_auth import Rolle  # noqa: E402

PW = "stufe2-admin-passwort"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx(text) -> bytes:
    """Baut eine minimale .docx — eine ZIP-Datei mit `word/document.xml`."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("word/document.xml",
                   '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
                   + "".join("<w:p><w:r><w:t>%s</w:t></w:r></w:p>" % zeile
                             for zeile in text.split("\n"))
                   + "</w:body></w:document>")
    return puffer.getvalue()


# --------------------------------------------------------------------------- #
# 1 — Die Weiche
# --------------------------------------------------------------------------- #
def test_office_wird_verlustfrei_ausgelesen(tmp_path):
    """Der Regelfall, und der haeufigste: ein Word-Dokument.

    Ausgelesen wird ueber `zipfile` und `re` — kein Fremdpaket, kein OCR.
    """
    pfad = tmp_path / "handbuch.docx"
    pfad.write_bytes(_docx("Rechnungen werden in DATEV erfasst"))
    text, guete, verfahren = text_holen(str(pfad), DOCX)
    assert verfahren == "office"
    assert guete == 1.000, "verlustfrei heisst 1.000 — das ist keine Schoenfaerbung"
    assert "DATEV" in text


def test_absatzenden_werden_zu_leerzeichen(tmp_path):
    """Sonst klebt das letzte Wort eines Absatzes am ersten des naechsten.

    Beide waeren dann unauffindbar — und zwar unbemerkt, weil der Text
    vorhanden aussieht.
    """
    pfad = tmp_path / "zwei.docx"
    pfad.write_bytes(_docx("Erster Absatz\nZweiter Absatz"))
    text, _, _ = text_holen(str(pfad), DOCX)
    assert "AbsatzZweiter" not in text
    assert "Absatz Zweiter" in text


def test_reiner_text_wird_gelesen(tmp_path):
    pfad = tmp_path / "notiz.txt"
    pfad.write_text("Der CRM-Auszug vom Mai liegt bei.", encoding="utf-8")
    text, guete, verfahren = text_holen(str(pfad), "text/plain")
    assert (verfahren, guete) == ("text", 1.000)
    assert "CRM-Auszug" in text


def test_ein_bild_ergibt_nichts(tmp_path):
    """Ein JPEG ist Arbeitsvorrat fuer den Worker aus Schritt 5 — kein Fehler.

    Wichtig ist, dass hier **nichts** zurueckkommt: Ein halb ausgelesener Scan
    waere schlechter als keiner, weil er belastbar aussieht.
    """
    pfad = tmp_path / "whiteboard.jpg"
    pfad.write_bytes(b"\xff\xd8\xff\xe0not-really-a-jpeg")
    assert text_holen(str(pfad), "image/jpeg") == (None, None, None)


def test_unbekannter_typ_ergibt_nichts(tmp_path):
    pfad = tmp_path / "irgendwas.bin"
    pfad.write_bytes(b"\x00\x01\x02")
    assert text_holen(str(pfad), "application/octet-stream") == (None, None, None)


def test_beschaedigte_office_datei_wirft_nicht(tmp_path):
    """Eine kaputte ZIP-Datei darf das Hochladen nicht scheitern lassen.

    Die Datei liegt zu diesem Zeitpunkt bereits im Volume. **Ein Beleg ohne
    Text ist brauchbar, ein verlorener Beleg nicht.**
    """
    pfad = tmp_path / "kaputt.docx"
    pfad.write_bytes(b"das ist keine zip-datei")
    assert text_holen(str(pfad), DOCX) == (None, None, None)


def test_die_schwelle_ist_je_seite_gerechnet():
    """100 Zeichen je Seite, nicht 100 insgesamt.

    Ein zwanzigseitiger Scan mit Kopfzeile traegt sonst genug Zeichen, um als
    Textdokument durchzugehen — und dann bliebe der Inhalt fuer immer
    unsichtbar, weil ihn niemand mehr zur Erkennung schickt.
    """
    assert TEXTEBENE_ZEICHEN_JE_SEITE == 100


# --------------------------------------------------------------------------- #
# 2 — Die Auskunft ueber die Belastbarkeit
# --------------------------------------------------------------------------- #
def test_belastbarkeit_im_wortlaut_der_sicht():
    """Die Wortlaute muessen mit `v_beleg_lesen` (Schema v1.6) uebereinstimmen.

    Sonst nennt dieselbe Datei in der Suche etwas anderes als im Bericht.
    """
    assert _belastbarkeit(None, None) == "kein Text"
    assert _belastbarkeit("x", 1.000) == "verlustfrei ausgelesen"
    assert _belastbarkeit("x", 0.87) == "erkannt"
    assert _belastbarkeit("x", 0.42) == "erkannt, unsicher — bitte pruefen"


def test_fundstelle_zeigt_das_umfeld():
    text = "Vorne steht Beiwerk. " * 20 + "Rechnungen gehen an DATEV. " + "Hinten auch. " * 20
    stelle = _fundstelle(text, "DATEV")
    assert "DATEV" in stelle
    assert len(stelle) < len(text), "die Fundstelle ist ein Ausschnitt, kein Abzug"


def test_fundstelle_ohne_text_ist_leer():
    assert _fundstelle(None, "x") is None
    assert _fundstelle("etwas", "") is None


# --------------------------------------------------------------------------- #
# 3 — Der Weg durch die Anwendung
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def client():
    anwendung.AUTH.benutzer_anlegen("stufe2@bc0.test", "Stufe2-Admin", PW, Rolle.ADMIN)
    c = TestClient(anwendung.app)
    c.post("/api/auth/login", json={"email": "stufe2@bc0.test", "passwort": PW})
    return c


@pytest.fixture(scope="module")
def mandant(client) -> str:
    return str(client.post("/api/companies",
                           json={"name": "Beleg GmbH", "kps": [1]}).json()["id"])


def _hochladen(client, mandant, name, inhalt, mime, ref_id="KP-02"):
    r = client.post("/api/companies/%s/documents" % mandant,
                    data={"ref_id": ref_id},
                    files={"file": (name, inhalt, mime)})
    assert r.status_code == 200, r.text
    return r.json()


def test_beim_hochladen_wird_der_text_nachgetragen(client, mandant):
    """Nicht im Hintergrund — der Extraktionsweg braucht Millisekunden.

    Ein Hintergrundlauf waere hier nur eine Stelle mehr, an der etwas unbemerkt
    scheitert. Er gehoert zu Schritt 5, wo eine Seite Erkennung Sekunden kostet.
    """
    _hochladen(client, mandant, "prozessdoku.docx",
               _docx("Der Freigabelauf erfolgt per Mail an die Buchhaltung"), DOCX)
    treffer = client.get("/api/companies/%s/documents/suche?q=Freigabelauf" % mandant).json()
    assert treffer["treffer"], "der Text muss beim Hochladen entstanden sein"
    assert treffer["treffer"][0]["erkannt_durch"] == "office"
    assert treffer["treffer"][0]["belastbarkeit"] == "verlustfrei ausgelesen"


def test_die_suche_nennt_die_fundstelle(client, mandant):
    _hochladen(client, mandant, "crm.txt",
               b"Der CRM-Auszug vom Mai zeigt 1.240 offene Vorgaenge.", "text/plain")
    d = client.get("/api/companies/%s/documents/suche?q=CRM-Auszug" % mandant).json()
    assert d["treffer"]
    assert "CRM-Auszug" in d["treffer"][0]["fundstelle"]


def test_ein_bild_wird_ueber_den_dateinamen_gefunden(client, mandant):
    """Und es ist als textlos gekennzeichnet.

    **Die erste Erwartung war falsch, nicht der Code.** Ich hatte geprueft,
    dass ein Bild gar nicht erscheint. Der Dateiname wird aber absichtlich
    mitdurchsucht — in PostgreSQL sogar mit dem **hoeheren** Gewicht A, weil er
    meist bewusst vergeben wurde, waehrend der Belegtext auch Beiwerk enthaelt
    (Schema v1.6, Kommentar an `such_vektor`).

    Das ist auch fachlich richtig: Ein Scan namens `CRM-Auszug_Mai.pdf` soll
    auffindbar sein, bevor ihn jemand durch die Erkennung geschickt hat.
    **Entscheidend ist, dass man ihm ansieht, woran man ist** — deshalb
    `belastbarkeit = "kein Text"` und keine Fundstelle.
    """
    _hochladen(client, mandant, "scan.jpg", b"\xff\xd8\xffnicht-lesbar", "image/jpeg")
    d = client.get("/api/companies/%s/documents/suche?q=scan" % mandant).json()
    bild = [x for x in d["treffer"] if x["filename"] == "scan.jpg"]
    assert bild, "ueber den Dateinamen muss es auffindbar sein"
    assert bild[0]["belastbarkeit"] == "kein Text"
    assert bild[0]["fundstelle"] is None
    assert bild[0]["erkannt_durch"] is None


def test_ohne_text_wird_gezaehlt(client, mandant):
    """**Ohne Text kein INHALTS-Treffer — und das muss sichtbar sein.**

    Sonst haelt man ein unvollstaendiges Ergebnis fuer ein vollstaendiges: Der
    gesuchte Satz koennte in einem Scan stehen, den niemand ausgelesen hat.
    """
    d = client.get("/api/companies/%s/documents/suche?q=Freigabelauf" % mandant).json()
    assert d["ohne_text"] >= 1, "die Zahl der textlosen Belege gehoert in die Antwort"
    assert all(x["filename"] != "scan.jpg" for x in d["treffer"]), \
        "ohne Text und ohne Namenstreffer taucht ein Beleg nicht auf"


def test_leere_suche_ist_kein_fehler(client, mandant):
    d = client.get("/api/companies/%s/documents/suche?q=" % mandant).json()
    assert d["treffer"] == []
    assert "verfahren" in d, "das Verfahren wird immer genannt, auch ohne Treffer"


def test_die_suche_bleibt_beim_mandanten(client, mandant):
    """Ein Belegtext ist Fliesstext und kann Namen enthalten, die keine ID tragen.

    Er darf deshalb unter keinen Umstaenden ueber die Mandantengrenze gehen.
    """
    fremd = str(client.post("/api/companies",
                            json={"name": "Fremd GmbH", "kps": [1]}).json()["id"])
    _hochladen(client, mandant, "geheim.txt", b"Zauberwort Kaskadenrichter", "text/plain")
    d = client.get("/api/companies/%s/documents/suche?q=Kaskadenrichter" % fremd).json()
    assert d["treffer"] == []


def test_suche_ist_ohne_anmeldung_gesperrt(mandant):
    r = TestClient(anwendung.app).get(
        "/api/companies/%s/documents/suche?q=x" % mandant)
    assert r.status_code == 401


# --------------------------------------------------------------------------- #
# 4 — Ein Prozentzeichen, das die Anwendung umwarf
# --------------------------------------------------------------------------- #
def test_kein_prozentzeichen_in_den_ddl_texten():
    """Am 03.09.2026 hat EIN Zeichen in einem KOMMENTAR den Server lahmgelegt.

    Die DDL-Texte gehen durch ``cur.execute(sql, params)``. psycopg2 liest das
    Prozentzeichen als Platzhalter und bricht mit ``IndexError: tuple index out
    of range`` ab — **auch wenn keine Parameter uebergeben werden**. Der
    Container ging in eine Neustartschleife, die Anwendung war nicht erreichbar.

    Der Satz, der es ausloeste, war eine Erlaeuterung: *„ein zu 87 Prozent
    erkannter Scan"*. Er hatte fachlich recht und stand an der richtigen Stelle.

    **In SQLite faellt es nicht auf** — dort geht der Text unveraendert durch.
    Deshalb war die Testsammlung gruen, waehrend der Server abstuerzte. Genau
    diese Luecke schliesst dieser Test.

    Beim Berichtigen stand das Zeichen dann im Warnhinweis selbst und haette es
    ein zweites Mal getan.
    """
    import re

    quelle = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "app.py"), encoding="utf-8").read()
    schuldig = [m.group(1) for m in
                re.finditer(r'([A-Z0-9_]+_DDL(?:_PG|_SQLITE)?) = """(.*?)"""', quelle, re.S)
                if "%" in m.group(2)]
    assert not schuldig, (
        "Prozentzeichen in %s — psycopg2 liest es als Platzhalter. "
        "Auch in Kommentaren nicht zulaessig." % ", ".join(schuldig))
