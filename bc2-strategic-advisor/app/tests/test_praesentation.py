"""
Tests für den Foliengenerator (#257, Format und Weg entschieden in #244).

**Geprüft wird, was auf den Folien steht, nicht dass die Datei entsteht.** Eine
PPTX ist ein ZIP mit Zeitstempeln; ein Bytevergleich taugt nicht. Drei
Prüfungen aus #244, dazu die Darstellungsregeln aus #257:

(a) **kein ``{{``** im ganzen Foliensatz — fängt das Template-Erbe ab;
(b) **Vollzähligkeit** — je freigegebenem Potenzial eine Detailfolie, je
    Kernprozess sein Abschnitt, nichts stillschweigend abgeschnitten;
(c) **die Scheingenauigkeits-Invariante** über alle Textrahmen: kein
    Euro-Betrag ohne Spanne, keine 0 als Ersatz für eine fehlende Größe.

Gelesen wird über alle Textrahmen **und** die Notizen. Die Notizen tragen je
Detail- und Kernprozessfolie die Kennung (``potenzial_id: …``, ``kp_id: …``):
daran zählt (b), statt an Titeln, die sich wiederholen dürfen.

Eingänge: die v3.2-Fixtures aus ``contracts/examples`` (volle Texte samt
Kurztexten für die Folie, zwei Kernprozesse), eine gelieferte 3.1-Lieferung und der Messsatz aus #167 über die Oberflächenquelle (elf
Potenziale in vier Kernprozessen, ohne LLM-Texte — der Weg, den der Knopf heute
geht).
"""

from __future__ import annotations

import copy
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")

from laeufe import MesssatzLaufquelle, aus_lauf  # noqa: E402
from modell import (  # noqa: E402
    Nutzwert,
    Nutzwertkategorie,
    Potenzialeingang,
    Schrittmessung,
    rechne_lauf,
)
from praesentation import (  # noqa: E402
    DATEINAME,
    KeineFreigabe,
    als_bytes,
    baue_praesentation,
)
from praesentation.folien import KACHELN_JE_FOLIE, ZEILEN_KOSTEN  # noqa: E402
from praesentation import formulierung as F  # noqa: E402

WURZEL = Path(__file__).resolve().parents[3]
BEISPIELE = WURZEL / "contracts" / "examples"
MESSSAETZE = WURZEL / "bc2-strategic-advisor" / "kalibrierung"


# ---------------------------------------------------------------------------
# Eingänge
# ---------------------------------------------------------------------------


def _lies(name: str) -> dict:
    return json.loads((BEISPIELE / name).read_text(encoding="utf-8"))


def _freigabe(prio: dict, **gate1) -> dict:
    prio = copy.deepcopy(prio)
    prio["gate1"] = {
        "status": "approved",
        "entscheider": "Sergio (Test)",
        "entschieden_am": "2026-10-09T10:00:00+00:00",
        "approved_potenzial_ids": [e["potenzial_id"] for e in prio["eintraege"]],
        **gate1,
    }
    return prio


@pytest.fixture
def fixture_lauf() -> tuple[list[dict], dict]:
    """Die v3.2-Fixtures: zwei Konzepte (KP-05, KP-06), sechs Potenziale, freigegeben."""
    konzepte = [_lies("mock_automatisierungskonzept.json"),
                _lies("mock_automatisierungskonzept_KP-05.json")]
    return konzepte, _freigabe(_lies("mock_prozesspriorisierung.json"))


@pytest.fixture
def messsatz_lauf() -> tuple[list[dict], dict, str | None]:
    """Der Messsatz aus #167 über die Oberflächenquelle — elf Potenziale, vier Kernprozesse."""
    quelle = MesssatzLaufquelle(MESSSAETZE, uebergeben_am=datetime(2026, 9, 21, tzinfo=timezone.utc))
    ansicht = quelle.ansicht(quelle.uebersicht()[0].paket_id)
    gate1 = {
        "status": "approved",
        "entschieden_am": "2026-10-09T10:00:00+00:00",
        "approved_potenzial_ids": ansicht.potenzial_ids(),
    }
    konzepte, prio = ansicht.als_vertrag(gate1)
    return konzepte, prio, ansicht.kopf.sperrgrund


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------


def _texte_der_folie(folie) -> list[str]:
    return [sp.text_frame.text for sp in folie.shapes if sp.has_text_frame and sp.text_frame.text]


def _notiz(folie) -> str:
    return folie.notes_slide.notes_text_frame.text if folie.has_notes_slide else ""


def _alle_texte(prs) -> list[str]:
    texte = []
    for folie in prs.slides:
        texte.extend(_texte_der_folie(folie))
        if _notiz(folie):
            texte.append(_notiz(folie))
    return texte


def _volltext(prs) -> str:
    return "\n".join(_alle_texte(prs))


def _folien_mit_notiz(prs, praefix: str) -> list[str]:
    werte = []
    for folie in prs.slides:
        for zeile in _notiz(folie).splitlines():
            if zeile.startswith(praefix):
                werte.append(zeile.removeprefix(praefix).strip())
    return werte


def _kopfzeilen(prs) -> list[str]:
    """Alle Textrahmen je Folie, zu einem Text gefügt — darin stehen die Folientitel."""
    return ["\n".join(_texte_der_folie(f)) for f in prs.slides]


# ---------------------------------------------------------------------------
# Die Invariante (c), einmal formuliert und überall angewandt
# ---------------------------------------------------------------------------

_EURO = re.compile(r"(\d[\d.]*(?:,\d+)?)\s*€")
_SPANNE_DAVOR = re.compile(r"\d[\d.]*(?:,\d+)?–$")
_RICHTWERT_DAVOR = re.compile(r"Richtwert $")
_RICHTWERT_DANACH = re.compile(r"\s*aus \d[\d.]*(?:,\d+)? PT Aufwand")
_ERSATZ_NULL = re.compile(r"(?<![\d.,–])0(?:,0+)?\s*(?:€|h/Jahr|h\b|PT\b|Monate)")


def _verstoesse(prs) -> list[str]:
    """Jeder Euro-Betrag ohne Spanne und jede 0 als Ersatz — als Klartext."""
    funde = []
    for text in _alle_texte(prs):
        for m in _EURO.finditer(text):
            davor, danach = text[: m.start(1)], text[m.end():]
            if _SPANNE_DAVOR.search(davor):
                continue  # oberes Ende von „a–b €"
            if _RICHTWERT_DAVOR.search(davor) and _RICHTWERT_DANACH.match(danach):
                continue  # „Richtwert 12.000 € aus 15 PT Aufwand" — die eine benannte Form
            funde.append(f"Euro ohne Spanne: …{text[max(0, m.start() - 30): m.end() + 20]}…")
        for m in _ERSATZ_NULL.finditer(text):
            funde.append(f"0 als Ersatz: …{text[max(0, m.start() - 30): m.end() + 10]}…")
        if text.strip() in {"-", "–", "—", "0", "n/a", "N/A"} or "n/a" in text.lower():
            funde.append(f"Platzhalter statt Grund: {text!r}")
    return funde


def test_die_invariante_selbst_faengt_was_sie_fangen_soll():
    """Ohne diese Gegenprobe wäre ein grüner Test (c) auch ein blinder."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    folie = prs.slides.add_slide(prs.slide_layouts[6])
    for t in ("Einsparung 23.500 €/Jahr", "Aufwand heute: 0 h/Jahr", "n/a",
              "18.000–29.000 €/Jahr (Dauer geschätzt, ±40 %)",
              "Investition: Richtwert 12.000 € aus 15 PT Aufwand"):
        folie.shapes.add_textbox(0, 0, Inches(3), Inches(1)).text_frame.text = t
    funde = _verstoesse(prs)
    assert len(funde) == 3, funde


# ---------------------------------------------------------------------------
# (a) Kein Template-Erbe
# ---------------------------------------------------------------------------


def test_a_kein_platzhalter_im_foliensatz(fixture_lauf, messsatz_lauf):
    for konzepte, prio, *_ in (fixture_lauf, messsatz_lauf):
        assert "{{" not in _volltext(baue_praesentation(konzepte, prio))


# ---------------------------------------------------------------------------
# (b) Vollzähligkeit
# ---------------------------------------------------------------------------


def test_b_je_potenzial_eine_detailfolie_je_kernprozess_ein_abschnitt(fixture_lauf):
    konzepte, prio = fixture_lauf
    prs = baue_praesentation(konzepte, prio)

    detail = _folien_mit_notiz(prs, "potenzial_id:")
    assert sorted(detail) == sorted(e["potenzial_id"] for e in prio["eintraege"])
    assert len(detail) == len(set(detail))

    abschnitte = _folien_mit_notiz(prs, "kp_id:")
    # Jede Detailfolie nennt ihren Kernprozess, dazu je Kernprozess die Abschnittsfolie.
    assert sorted(set(abschnitte)) == sorted(r["kp_id"] for r in prio["prozess_raenge"])


def test_b_ueberlauf_wird_umgebrochen_nie_begrenzt(messsatz_lauf):
    """Elf Potenziale gegen sechs Kacheln: zwei Überblicksfolien, nicht „Top 6"."""
    konzepte, prio, _ = messsatz_lauf
    n = len(prio["eintraege"])
    assert n > KACHELN_JE_FOLIE and n > ZEILEN_KOSTEN, "Der Messsatz prüft den Überlauf nicht mehr."
    prs = baue_praesentation(konzepte, prio)

    assert len(_folien_mit_notiz(prs, "potenzial_id:")) == n
    kopf = "\n".join(_kopfzeilen(prs))
    seiten = -(-n // KACHELN_JE_FOLIE)
    for i in range(1, seiten + 1):
        assert f"Überblick: freigegebene Potenziale ({i} von {seiten})" in kopf
    kosten = -(-n // ZEILEN_KOSTEN)
    assert f"Kosten und Nutzen je Potenzial ({kosten} von {kosten})" in kopf

    text = _volltext(prs)
    for e in prio["eintraege"]:
        # Jeder Titel im Überblick, in der Matrix, auf der Detailfolie und in der Kostentabelle.
        assert text.count(e["titel"]) >= 4, e["titel"]


def test_b_jeder_kernprozess_des_messsatzes_hat_seinen_abschnitt(messsatz_lauf):
    konzepte, prio, _ = messsatz_lauf
    prs = baue_praesentation(konzepte, prio)
    erwartet = [r["kp_id"] for r in sorted(prio["prozess_raenge"], key=lambda r: r["prozessrang"])]
    abschnitte = []
    for folie in prs.slides:
        zeilen = _notiz(folie).splitlines()
        if len(zeilen) == 1 and zeilen[0].startswith("kp_id:"):
            abschnitte.append(zeilen[0].removeprefix("kp_id:").strip())
    assert abschnitte == erwartet


# ---------------------------------------------------------------------------
# (c) Scheingenauigkeit
# ---------------------------------------------------------------------------


def test_c_kein_euro_ohne_spanne_und_keine_0_als_ersatz(fixture_lauf, messsatz_lauf):
    for konzepte, prio, *_ in (fixture_lauf, messsatz_lauf):
        assert _verstoesse(baue_praesentation(konzepte, prio)) == []


def test_c_ohne_wertaussage_steht_der_grund(keine_wertaussage_lauf):
    konzepte, prio = keine_wertaussage_lauf
    prs = baue_praesentation(konzepte, prio)
    text = _volltext(prs)
    assert _verstoesse(prs) == []
    assert "Keine Wertaussage" in text or "Warum keine Wertaussage" in text
    # Der Vertrag trägt hier stunden_jahr: 0 — auf der Folie steht der Grund.
    assert "keine Dauer erhoben" in text


def test_die_herkunft_steht_im_selben_satz_wie_die_spanne(fixture_lauf):
    konzepte, prio = fixture_lauf
    text = _volltext(baue_praesentation(konzepte, prio))
    spannen = re.findall(r"\d[\d.]*–\d[\d.]* €/Jahr \(([^)]*)\)", text)
    assert spannen, "Keine Einsparungsspanne gefunden."
    assert all("Dauer" in h and "±" in h for h in spannen), spannen


# ---------------------------------------------------------------------------
# Die übrigen Darstellungsregeln aus #257
# ---------------------------------------------------------------------------


def test_der_prioritaetsscore_erscheint_nicht(fixture_lauf):
    """Eine 74,5 sieht gemessen aus und ist ein Produkt zweier Urteile (#244)."""
    konzepte, prio = fixture_lauf
    assert "score" not in _volltext(baue_praesentation(konzepte, prio)).lower()


def test_die_titelfolie_traegt_mandant_paket_fassung_und_uebergabe(fixture_lauf):
    konzepte, prio = fixture_lauf
    titel = "\n".join(_texte_der_folie(baue_praesentation(konzepte, prio).slides[0]))
    assert "NoroAI Consulting GmbH" in titel
    assert prio["paket_id"] in titel
    assert f"Fassung {prio['fassung']}" in titel
    assert "übergeben am 31.08.2026" in titel


def test_die_ausgangslage_kommt_aus_dem_vertrag(fixture_lauf):
    konzepte, prio = fixture_lauf
    text = _volltext(baue_praesentation(konzepte, prio))
    u = prio["ausgangslage"]["unternehmen"]
    for wert in (u["branche"], u["region"], u["geschaeftsmodell"], f"Mitarbeitende: {u['mitarbeitende']}"):
        assert str(wert) in text
    for h in prio["ausgangslage"]["herausforderungen"]:
        assert h["beschreibung"] in text
    # Die Kausalketten-Folie ist bewusst entfallen (#244).
    assert "Kausalkette" not in text


def test_ohne_ausgangslage_steht_der_grund_nicht_eine_erfindung(messsatz_lauf):
    konzepte, prio, _ = messsatz_lauf
    assert "ausgangslage" not in prio and prio["schema_version"] == "3.0"
    text = _volltext(baue_praesentation(konzepte, prio))
    assert text.count("in dieser Priorisierung nicht vor") >= 2  # Unternehmen und Herausforderungen


def test_eine_kernaussage_erscheint_wenn_es_sie_gibt(fixture_lauf):
    konzepte, prio = fixture_lauf
    prio["ausgangslage"]["kernaussage"] = "Der größte Hebel liegt im Medienbruch zur Excel-Liste."
    assert "Der größte Hebel liegt im Medienbruch" in _volltext(baue_praesentation(konzepte, prio))


def test_querschnitte_stehen_auf_der_detailfolie(fixture_lauf):
    konzepte, prio = fixture_lauf
    prs = baue_praesentation(konzepte, prio)
    pot = konzepte[0]["potenziale"][0]
    for folie in prs.slides:
        if f"potenzial_id: {pot['potenzial_id']}" in _notiz(folie):
            assert pot["querschnitte"]["zukunftssicherheit"] in "\n".join(_texte_der_folie(folie))
            return
    pytest.fail("Detailfolie nicht gefunden.")


def test_nicht_freigegebene_kommen_nicht_vor_auch_nicht_ihr_grund(fixture_lauf):
    konzepte, prio = fixture_lauf
    raus = prio["eintraege"][-1]
    grund = "Passt nicht in das Budget dieses Jahres — erst nach dem Umzug."
    prio["gate1"]["approved_potenzial_ids"].remove(raus["potenzial_id"])
    prio["gate1"]["nicht_freigegeben"] = [{"potenzial_id": raus["potenzial_id"], "begruendung": grund}]

    prs = baue_praesentation(konzepte, prio)
    text = _volltext(prs)
    assert raus["titel"] not in text
    assert grund not in text
    assert raus["potenzial_id"] not in _folien_mit_notiz(prs, "potenzial_id:")


def test_die_am_gate_gesetzte_reihenfolge_gilt(fixture_lauf):
    konzepte, prio = fixture_lauf
    folge = [e["potenzial_id"] for e in reversed(prio["eintraege"])]
    prio["gate1"]["finale_reihenfolge_potenzial_ids"] = folge
    prio["gate1"]["abweichungsbegruendung"] = "Das Budget erlaubt nur die kleinen zuerst."
    prs = baue_praesentation(konzepte, prio)
    text = _volltext(prs)
    letzter = prio["eintraege"][-1]
    assert f"Rang 1   {letzter['titel']}" in text
    assert "Das Budget erlaubt nur die kleinen zuerst." in text


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_vor_der_freigabe_und_bei_ablehnung_entsteht_keine_praesentation(fixture_lauf, status):
    konzepte, prio = fixture_lauf
    prio["gate1"] = {"status": status, "kommentar": "nicht freigegeben"}
    with pytest.raises(KeineFreigabe):
        baue_praesentation(konzepte, prio)


def test_der_sperrgrund_der_quelle_steht_auf_der_titelfolie(messsatz_lauf):
    konzepte, prio, sperrgrund = messsatz_lauf
    assert sperrgrund, "Der Messsatz trägt keinen Sperrgrund mehr — dann prüft dieser Test nichts."
    titel = "\n".join(_texte_der_folie(
        baue_praesentation(konzepte, prio, sperrgrund=sperrgrund).slides[0]
    ))
    assert sperrgrund in titel


def test_hinweise_stehen_auf_der_titelfolie_ohne_warnzeichen(fixture_lauf):
    """Ein Hinweis hält nichts auf (#305) — er steht da, aber nicht als Warnung."""
    konzepte, prio = fixture_lauf
    hinweis = "Schnitt und Bewertung sind Modellurteile."
    titel = "\n".join(_texte_der_folie(
        baue_praesentation(konzepte, prio, hinweise=[hinweis]).slides[0]
    ))
    assert hinweis in titel and "⚠" not in titel


def test_derselbe_lauf_ergibt_dieselben_folien(fixture_lauf):
    """Reproduzierbar im Inhalt — der Bytevergleich taugt nicht (Zeitstempel im ZIP)."""
    konzepte, prio = fixture_lauf
    assert _alle_texte(baue_praesentation(konzepte, prio)) == _alle_texte(
        baue_praesentation(konzepte, prio))


# ---------------------------------------------------------------------------
# Alle ohne Wertaussage — die offene Frage aus #257
# ---------------------------------------------------------------------------


def _nutzwert() -> Nutzwert:
    k = Nutzwertkategorie(6, "Begruendungssatz fuer den Test.")
    return Nutzwert(k, k, k, k, k)


@pytest.fixture
def keine_wertaussage_lauf() -> tuple[list[dict], dict]:
    """Drei Potenziale, keines mit erhobener Dauer — ``value_quelle: "keine"`` überall."""
    eingaenge = [
        Potenzialeingang(
            potenzial_id=f"00000000-0000-4000-8000-00000000000{i}",
            titel=f"Potenzial ohne Dauer {i}",
            kp_id="KP-02",
            betroffene_teilprozess_ids=(f"KP-02.TP-{i}",),
            klasse="Integration",
            automatisierungsgrad_begruendung="Zwei Systeme verbinden.",
            nutzwert=_nutzwert(),
            # Profil mit Skalen, aber ohne Dauer und Herkunft — darum keine Value-Zahl.
            messungen=(Schrittmessung(teilprozess_id=f"KP-02.TP-{i}", reifeskalen=(3, 3, 3, 3)),),
            aufwand_schaetzung_pt=None if i == 1 else 8.0,
        )
        for i in (1, 2, 3)
    ]
    lauf = rechne_lauf("7c2d5ee9-2a9a-5990-810f-502ea2b2012d", "PKT-OHNE-DAUER", eingaenge)
    ansicht = aus_lauf(lauf, eingaenge, uebergeben_am=datetime(2026, 9, 21, tzinfo=timezone.utc))
    return ansicht.als_vertrag({"status": "approved", "approved_potenzial_ids": ansicht.potenzial_ids()})


def test_sind_alle_ohne_wertaussage_zeigt_teil_3_gruende_statt_leerer_tabellen(keine_wertaussage_lauf):
    konzepte, prio = keine_wertaussage_lauf
    assert all(p["value"]["value_quelle"] == "keine" for k in konzepte for p in k["potenziale"])
    prs = baue_praesentation(konzepte, prio)
    text = _volltext(prs)
    assert "Für keines der 3 Potenziale liegt eine Wertaussage vor" in text
    assert "Warum keine Wertaussage" in text
    assert "Einsparung je Jahr" not in text
    assert "kein Aufwand geschätzt, deshalb kein Richtwert" in text


# ---------------------------------------------------------------------------
# Bytes für den Download
# ---------------------------------------------------------------------------


def test_die_bytes_sind_eine_lesbare_praesentation(fixture_lauf):
    """Abgelegt wird sie nicht mehr (#305) — sie geht als Download an den Mandanten."""
    konzepte, prio = fixture_lauf
    daten = als_bytes(baue_praesentation(konzepte, prio))
    assert DATEINAME == "praesentation.pptx"
    gelesen = pptx.Presentation(io.BytesIO(daten))
    assert len(gelesen.slides) == len(baue_praesentation(konzepte, prio).slides)



# ---------------------------------------------------------------------------
# Kopf der Detailfolie: der Titel läuft nie unter das PRIO-Etikett
# ---------------------------------------------------------------------------


def _titel_und_etikett(folie, titel: str):
    rahmen = [sp for sp in folie.shapes if sp.has_text_frame and sp.text_frame.text.startswith("Rang ")
              and titel in sp.text_frame.text]
    etikett = [sp for sp in folie.shapes if sp.has_text_frame and sp.text_frame.text.startswith("PRIO ")]
    assert len(rahmen) == 1 and len(etikett) == 1
    return rahmen[0], etikett[0]


def _passt(rahmen) -> bool:
    """Steht der Text bei seiner Schriftgröße vollständig im Rahmen?

    Geschätzt wie beim Zeichnen (:func:`praesentation.zeichnen.ueberlaeuft`), mit
    den Breiten der **fetten** Calibri — der Titel ist fett, und genau die zu
    schmal angesetzte Breite ließ ihn in der ersten Fassung unter das Etikett laufen.
    """
    from praesentation.zeichnen import ueberlaeuft

    return not ueberlaeuft(rahmen)


@pytest.mark.parametrize("titel", [
    None,  # der längste Titel des Messsatzes aus #167
    "Lebensläufe strukturiert erfassen, Kompetenzprofile aufbauen und mit Projektanforderungen "
    "abgleichen, damit die Vorschlagsliste für jede Ausschreibung automatisch entsteht",
])
def test_der_titel_der_detailfolie_laeuft_nie_unter_das_etikett(messsatz_lauf, titel):
    konzepte, prio, _ = messsatz_lauf
    prio = copy.deepcopy(prio)
    if titel is None:
        eintrag = max(prio["eintraege"], key=lambda e: len(e["titel"]))
    else:
        eintrag = prio["eintraege"][0]
        eintrag["titel"] = titel
    prs = baue_praesentation(konzepte, prio)
    folie = next(f for f in prs.slides if f"potenzial_id: {eintrag['potenzial_id']}" in _notiz(f))

    rahmen, etikett = _titel_und_etikett(folie, eintrag["titel"])
    assert rahmen.left + rahmen.width <= etikett.left, "Titelrahmen reicht unter das Etikett."
    assert eintrag["titel"] in rahmen.text_frame.text, "Der Titel steht nicht vollständig im Rahmen."
    assert rahmen.text_frame.word_wrap is True
    assert _passt(rahmen), "Der Titel passt bei seiner Schriftgröße nicht in den Rahmen."


# ---------------------------------------------------------------------------
# Kein Überlauf, kein rohes Markdown (#380)
# ---------------------------------------------------------------------------

from collections import Counter  # noqa: E402

from pptx.util import Inches  # noqa: E402

from praesentation.absaetze import Absatz, Lauf, aus_markdown, klartext, teile  # noqa: E402
from praesentation.zeichnen import ueberlaeuft  # noqa: E402

#: Die Lieferung aus dem Befund vom 10.11.2026: ihre Präsentation lief auf den
#: Detailfolien um das 2,5-Fache über und zeigte ``##`` und ``**`` roh.
LIEFERUNG_BEFUND = WURZEL / "contracts" / "bc2-to-bc3" / "lieferungen" / (
    "noroai-cc7f4d1b-4c71-4cfa-92c3-46a395080e4b-f1")


@pytest.fixture
def befund_lauf() -> tuple[list[dict], dict]:
    prio = json.loads((LIEFERUNG_BEFUND / "prozesspriorisierung.json").read_text(encoding="utf-8"))
    konzepte = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(LIEFERUNG_BEFUND.glob("konzept_*.json"))]
    return konzepte, prio


def _ueberlaufende(prs) -> list[str]:
    funde = []
    for n, folie in enumerate(prs.slides, start=1):
        for sp in folie.shapes:
            if sp.has_text_frame and sp.text_frame.text.strip() and ueberlaeuft(sp):
                funde.append(f"Folie {n}: {sp.text_frame.text[:70]!r}")
    return funde


def test_kein_textrahmen_laeuft_ueber(befund_lauf, fixture_lauf, messsatz_lauf, keine_wertaussage_lauf):
    """Der Test gegen Rückfall: jeder Rahmen passt bei seiner gesetzten Größe — geschätzt
    wie beim Zeichnen. PowerPoint schrumpft beim Öffnen nicht; was hier rot wird,
    überdeckt dort, was darunter steht."""
    for konzepte, prio, *_ in (befund_lauf, fixture_lauf, messsatz_lauf, keine_wertaussage_lauf):
        assert _ueberlaufende(baue_praesentation(konzepte, prio)) == []


def test_die_pruefung_auf_ueberlauf_ist_nicht_blind():
    """Gegenprobe: der lange Text aus dem Befund, in den alten Rahmen der Detailfolie
    (6,1 × 2,35 Zoll) bei 8 pt gesetzt — so sah es vorher aus, und das muss rot sein."""
    from pptx import Presentation
    from praesentation.zeichnen import txt

    lang = json.loads((LIEFERUNG_BEFUND / "konzept_KP-06.json").read_text(encoding="utf-8"))
    beschreibung = max((p["beschreibung"] for p in lang["potenziale"]), key=len)
    prs = Presentation()
    folie = prs.slides.add_slide(prs.slide_layouts[6])
    alt = txt(folie, 0, 0, Inches(6.1), Inches(2.35), beschreibung, 11)
    kurz = txt(folie, 0, 0, Inches(6.1), Inches(2.35), "Ein kurzer Satz.", 11)
    assert ueberlaeuft(alt) and not ueberlaeuft(kurz)


def test_kein_markdown_auf_einer_folie(befund_lauf):
    text = _volltext(baue_praesentation(*befund_lauf))
    assert "##" not in text and "**" not in text
    assert not re.search(r"(?m)^\s*#", text), "Eine Zeile beginnt mit #."
    assert "Lösungsansatz: ###" not in text


def _woerter(text: str) -> Counter:
    return Counter(re.findall(r"[\wÄÖÜäöüß€%.,:;()–—→/+-]+", text.replace("*", "").replace("#", "")))


def test_langer_text_geht_auf_fortsetzungsfolien_ohne_dass_etwas_fehlt(befund_lauf):
    """Teilen statt Schrumpfen: alles steht da, in 10 pt, notfalls auf der Fortsetzung."""
    konzepte, prio = befund_lauf
    konzepte = copy.deepcopy(konzepte)
    pot = konzepte[0]["potenziale"][0]
    pot["beschreibung"] = "\n\n".join([pot["beschreibung"]] * 3)  # rund 8.500 Zeichen
    prs = baue_praesentation(konzepte, prio)

    pid = pot["potenzial_id"]
    eigene = [f for f in prs.slides
              if f"potenzial_id: {pid}" in _notiz(f) or f"fortsetzung_von: {pid}" in _notiz(f)]
    assert len(eigene) >= 3, "Der dreifache Text passt nicht auf eine Folie und eine Fortsetzung."
    assert sum(f"fortsetzung_von: {pid}" in _notiz(f) for f in prs.slides) == len(eigene) - 1
    kicker = [t for f in eigene[1:] for t in _texte_der_folie(f) if "FORTSETZUNG" in t]
    assert len(kicker) == len(eigene) - 1
    assert _ueberlaufende(prs) == []

    gezeigt = _woerter("\n".join(t for f in eigene for t in _texte_der_folie(f)))
    # Eine 3.1: Heute fällt auf den langen Text zurück, Soll steht kurz (#382).
    for feld in (pot["beschreibung"], pot["potenzielle_loesung"]["to_be_kurz"],
                 *pot["voraussetzungen"]):
        fehlt = _woerter(klartext(aus_markdown(feld, 10))) - gezeigt
        assert not fehlt, f"Abgeschnitten: {list(fehlt)[:10]}"
    # Die Größe bleibt: geteilt, nicht geschrumpft — Fließtext 10 pt, Abschnittsköpfe 11,5 pt.
    groessen = {r.font.size.pt for f in eigene[1:] for sp in f.shapes
                if sp.has_text_frame and Inches(1.3) <= sp.top < Inches(7.0)
                for p in sp.text_frame.paragraphs for r in p.runs}
    assert groessen == {10.0, 11.5}


def test_eine_detailfolie_ohne_fortsetzung_wenn_der_text_kurz_ist(fixture_lauf):
    konzepte, prio = fixture_lauf
    konzepte = copy.deepcopy(konzepte)
    for k in konzepte:
        for p in k["potenziale"]:
            p["beschreibung"] = "Heute tippt die Sachbearbeitung jede Anfrage ab."
            p["to_be_vision"] = "Künftig liest ein Dienst die Anfrage aus."
    prs = baue_praesentation(konzepte, prio)
    assert not _folien_mit_notiz(prs, "fortsetzung_von:")


def test_voraussetzungen_als_aufzaehlung_nicht_mit_semikolon(befund_lauf):
    text = _volltext(baue_praesentation(*befund_lauf))
    assert ".;" not in text


def test_einzahl_und_mehrzahl(befund_lauf):
    """Ein Kernprozess, ein Konzept: nicht „in 1 Kernprozessen", nicht „1 Konzept(e)"."""
    text = _volltext(baue_praesentation(*befund_lauf))
    assert "in 1 Kernprozess\n" in text or text.count("in 1 Kernprozess") >= 1
    assert "1 Kernprozessen" not in text
    assert "Konzept(e)" not in text and "1 Konzept des Analyselaufs" in text


# --- Markdown und Teilen, für sich ---------------------------------------------


def test_markdown_wird_absatz_aufzaehlung_und_fettung():
    absaetze = aus_markdown(
        "## Titel\n\nText mit **fett** und *kursiv*.\n\n### Rollen\n- **Sachbearbeitung**: prüft\n"
        "1. erstens", 10)
    assert [a.text for a in absaetze] == [
        "Titel", "Text mit fett und kursiv.", "Rollen", "Sachbearbeitung: prüft", "erstens"]
    assert [a.punkt for a in absaetze] == [False, False, False, True, True]
    assert absaetze[0].laeufe == (Lauf("Titel", True),) and absaetze[0].halten
    assert Lauf("fett", True) in absaetze[1].laeufe
    assert absaetze[3].laeufe[0] == Lauf("Sachbearbeitung", True)


def test_teilen_verliert_nichts_und_haelt_ueberschriften():
    text = " ".join(f"Wort{i}" for i in range(600))
    absaetze = [Absatz((Lauf("Kopf", True),), 11, halten=True), Absatz((Lauf(text),), 10)]
    alle, rest = [], absaetze
    while rest:
        drin, rest = teile(rest, 300, 200)
        assert drin, "Eine Fläche blieb leer — das liefe endlos."
        alle.extend(drin)
    assert " ".join(a.text for a in alle[1:]).split() == text.split()
    # Eine Überschrift, nach der nicht mindestens zwei Zeilen passen, wandert mit.
    from praesentation.absaetze import INNEN_HOEHE_PT, ZEILENHOEHE, hoehe_pt

    voll = Absatz((Lauf("Wort " * 150),), 10)
    kopf = Absatz((Lauf("Kopf", True),), 11, halten=True)
    platz = hoehe_pt([voll], 300) + INNEN_HOEHE_PT + 11 * ZEILENHOEHE + 5  # Kopf ja, zwei Zeilen nein
    drin, rest = teile([voll, kopf, Absatz((Lauf("Text " * 40),), 10)], 300, platz)
    assert drin == [voll] and rest[0] is kopf


# --- Die Kurztexte für die Folie (Vertrag 3.2, #382) -------------------------------


def _eigene(prs, pid: str) -> list:
    """Die Detailfolie eines Potenzials und ihre Fortsetzungen, in Folienfolge."""
    return [f for f in prs.slides
            if f"potenzial_id: {pid}" in _notiz(f) or f"fortsetzung_von: {pid}" in _notiz(f)]


def _text_der(folien) -> str:
    return "\n".join(t for f in folien for t in _texte_der_folie(f))


_LINKE_KOEPFE = ("HEUTIGER PROZESS", "AUTOMATISIERUNGSPOTENZIAL")


def test_eine_v3_2_zeigt_beide_kurztexte_ohne_folgefolie_fuer_die_linken_bloecke(fixture_lauf):
    """Die Abnahme aus #382: Heute und Soll passen auf die erste Detailfolie."""
    konzepte, prio = fixture_lauf
    assert prio["schema_version"] == "3.2"
    prs = baue_praesentation(konzepte, prio)
    assert _ueberlaufende(prs) == []

    for pot in (p for k in konzepte for p in k["potenziale"]):
        erste, *fortsetzungen = _eigene(prs, pot["potenzial_id"])
        text = _text_der([erste])
        loesung = pot["potenzielle_loesung"]
        assert pot["heute_kurz"] in text
        assert loesung["to_be_kurz"] in text
        assert f"Werkzeuge: {', '.join(loesung['tech_stack_empfehlung'])}" in text
        assert F.automatisierungsgrad(pot) in text
        # Die langen Texte bleiben für BC3 — auf der Folie stehen sie nicht.
        alles = _text_der([erste, *fortsetzungen])
        assert "Automatisiert wird" not in alles, "die Beschreibung läuft über den Kurztext hinaus"
        assert klartext(aus_markdown(pot["to_be_vision"], 10))[:80] not in alles
        assert "Lösungsansatz" not in alles
        for f in fortsetzungen:
            assert not any(kopf in _text_der([f]) for kopf in _LINKE_KOEPFE), (
                f"{pot['titel']}: Heute oder Soll läuft auf eine Folgefolie")


def test_eine_v3_1_zeigt_heute_lang_und_soll_kurz(befund_lauf):
    """Rückfall je Hälfte: einer 3.1 fehlt heute_kurz, to_be_kurz trägt sie schon."""
    konzepte, prio = befund_lauf
    assert prio["schema_version"] == "3.1"
    prs = baue_praesentation(konzepte, prio)
    assert _ueberlaufende(prs) == []

    for pot in (p for k in konzepte for p in k["potenziale"]):
        assert "heute_kurz" not in pot
        eigene = _eigene(prs, pot["potenzial_id"])
        alles = _text_der(eigene)
        fehlt = _woerter(klartext(aus_markdown(pot["beschreibung"], 10))) - _woerter(alles)
        assert not fehlt, f"Heute ist nicht der lange Text: {list(fehlt)[:10]}"
        loesung = pot["potenzielle_loesung"]
        assert loesung["to_be_kurz"] in alles
        assert f"Werkzeuge: {', '.join(loesung['tech_stack_empfehlung'])}" in alles
        assert klartext(aus_markdown(pot["to_be_vision"], 10))[:80] not in alles
        assert "Lösungsansatz" not in alles


def test_ohne_to_be_kurz_steht_soll_lang_samt_loesungsansatz(befund_lauf):
    """Die andere Hälfte des Rückfalls: eine Datei ohne to_be_kurz (wie jede vor #319)."""
    konzepte, prio = befund_lauf
    konzepte = copy.deepcopy(konzepte)
    pot = konzepte[0]["potenziale"][0]
    del pot["potenzielle_loesung"]["to_be_kurz"]
    prs = baue_praesentation(konzepte, prio)

    alles = _text_der(_eigene(prs, pot["potenzial_id"]))
    gezeigt = _woerter(alles)
    for feld in (pot["to_be_vision"], pot["potenzielle_loesung"]["ansatz"]):
        fehlt = _woerter(klartext(aus_markdown(feld, 10))) - gezeigt
        assert not fehlt, f"Abgeschnitten: {list(fehlt)[:10]}"
    assert "Werkzeuge:" not in alles
    assert _ueberlaufende(prs) == []


def test_zwei_volle_kurztexte_passen_auf_die_erste_folie(fixture_lauf, befund_lauf):
    """Die Grenze des Wächters, ausgeschöpft: je 300 Zeichen Heute und Soll, eine dreifache
    Systemliste und die doppelte Werkzeugliste einer echten Lieferung (dort stehen zu jedem
    Werkzeug Zweck und Betrieb) — die linken Blöcke bleiben trotzdem auf einer Folie."""
    konzepte, prio = fixture_lauf
    konzepte = copy.deepcopy(konzepte)
    satz = "Die Sachbearbeitung prüft jede Anfrage von Hand und überträgt sie in die Liste. "
    voll = (satz * 4)[:299].rstrip() + "."
    echt = max((p["potenzielle_loesung"]["tech_stack_empfehlung"]
                for k in befund_lauf[0] for p in k["potenziale"]),
               key=lambda w: len(", ".join(w)))
    for k in konzepte:
        for p in k["potenziale"]:
            p["heute_kurz"] = voll
            p["potenzielle_loesung"]["to_be_kurz"] = voll
            p["potenzielle_loesung"]["tech_stack_empfehlung"] = echt * 2
            p["betroffene_systeme"] = p["betroffene_systeme"] * 3
    prs = baue_praesentation(konzepte, prio)
    assert _ueberlaufende(prs) == []
    for pot in (p for k in konzepte for p in k["potenziale"]):
        _erste, *fortsetzungen = _eigene(prs, pot["potenzial_id"])
        for f in fortsetzungen:
            assert not any(kopf in _text_der([f]) for kopf in _LINKE_KOEPFE)
