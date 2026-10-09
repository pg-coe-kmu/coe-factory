"""
Tests für die Ausgangslage in der Priorisierung (Vertrag v3.1, #254).

Die Präsentation braucht eine Ausgangslage (Teil 1 der KIsult-Vorlage), und im
Vertrag v3.0 hatte sie keinen Ort. Entschieden in #244: sie **entsteht im Lauf
und wandert in die Priorisierung** — sonst trüge die Präsentation eigene
Information, und das schließt das Glossar aus („Kein eigenes Ergebnis").

Geprüft wird, in dieser Reihenfolge:

1. **Die Vertragsform.** ``ausgangslage`` passt in ``priorisierung.schema.json``
   v3.1 — gegen die echte Datei, nicht gegen einen Nachbau.
2. **Rückwärtsverträglichkeit.** Eine v3.0-Priorisierung ohne Ausgangslage
   bleibt gültig, auch die übergebene simulierte Lieferung (#168).
3. **Der maschinelle Teil.** Unternehmen aus dem Mandantensatz, kein LLM; eine
   fehlende Angabe ist ``null``, keine leere Zeichenkette und keine 0;
   Herausforderungen sind die zusammengeführten Schmerzpunkte der Konzepte.
4. **Die Leseseite.** Der Snapshot liefert Region und Geschäftsmodell mit, und
   die Postgres-Abfrage liest den Namen aus der Spalte, die es gibt.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from erkennung import Mandant, SnapshotBestand
from erkennung import bestand as bestand_modul
from modell.ausgabe import als_ausgangslage

VERTRAEGE = Path(__file__).resolve().parents[3] / "contracts" / "bc2-to-bc3"
SIM = VERTRAEGE / "lieferungen" / "noroai-SIM-UC3-2026-09-21-f1"
SNAPSHOT = (
    Path(__file__).resolve().parents[3]
    / "bc0-baseline-onboarding" / "app" / "snapshots" / "NoroAI_Consulting_GmbH_baseline_v3.json"
)
NOROAI = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"


def _schema() -> dict:
    return json.loads((VERTRAEGE / "priorisierung.schema.json").read_text(encoding="utf-8"))


def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    return jsonschema.Draft202012Validator(_schema())


def _mandant(**ueber) -> Mandant:
    vorgabe = dict(
        company_id=NOROAI,
        name="NoroAI Consulting GmbH",
        branche="KI-Beratung",
        mitarbeitende=10,
        region="FH-Suedwestfalen-Region",
        geschaeftsmodell="KI-Beratung mit eigenem Tech-Stack",
    )
    vorgabe.update(ueber)
    return Mandant(**vorgabe)


def _konzept(kp_id: str, *schmerzpunkte: dict) -> dict:
    """Nur der Teil eines Konzepts, aus dem die Herausforderungen entstehen."""
    return {
        "konzept_id": str(uuid.uuid4()),
        "kontext": {
            "kp_id": kp_id,
            "prozess_kurzbeschreibung": f"{kp_id} in kurz.",
            "hauptschmerzpunkte": list(schmerzpunkte),
        },
    }


def _schmerz(beschreibung: str, auswirkung: str = "kostet Zeit", **weiteres) -> dict:
    return {"beschreibung": beschreibung, "auswirkung": auswirkung, **weiteres}


def _priorisierung(**ueber) -> dict:
    """Eine minimale, gültige Priorisierung v3.1."""
    pid, kid = str(uuid.uuid4()), str(uuid.uuid4())
    vorgabe = {
        "priorisierung_id": str(uuid.uuid4()),
        "schema_version": "3.1",
        "company_id": NOROAI,
        "paket_id": "PKT-2026-0007",
        "uebergeben_am": "2026-09-20T14:32:11+00:00",
        "fassung": 1,
        "erzeugt_am": "2026-09-20T15:00:00+00:00",
        "score_formel": "score = impact x (11 - umsetzungskomplexitaet)",
        "konzept_ids": [kid],
        "eintraege": [
            {
                "potenzialrang": 1,
                "prioritaetsgruppe": "PRIO 2",
                "potenzial_id": pid,
                "konzept_id": kid,
                "titel": "Rechnung aus der Zeiterfassung",
                "kp_id": "KP-06",
                "betroffene_teilprozess_ids": ["KP-06.TP-2"],
                "kategorie": "Quick Win",
                "impact": 6,
                "nutzwert_mittel": 6.0,
                "umsetzungskomplexitaet": 5,
                "score": 36,
            }
        ],
        "prozess_raenge": [
            {
                "prozessrang": 1,
                "kp_id": "KP-06",
                "konzept_id": kid,
                "bestes_potenzial_id": pid,
                "bester_score": 36,
            }
        ],
        "gate1": {"status": "pending"},
        "ausgangslage": als_ausgangslage(
            _mandant(), [_konzept("KP-06", _schmerz("Stunden werden abgetippt"))]
        ),
    }
    vorgabe.update(ueber)
    return vorgabe


def _fehler(daten: dict) -> list[str]:
    return [e.message for e in _validator().iter_errors(daten)]


# ======================================================================
# 1. Die Vertragsform
# ======================================================================


def test_eine_priorisierung_v3_1_mit_ausgangslage_passt_in_den_vertrag():
    assert _fehler(_priorisierung()) == []


def test_die_kernaussage_ist_optional():
    """Optional mit Absicht: der Foliengenerator soll ohne #248 lauffähig sein."""
    prio = _priorisierung()
    assert "kernaussage" not in prio["ausgangslage"]
    assert _fehler(prio) == []

    mit = _priorisierung()
    mit["ausgangslage"]["kernaussage"] = "Der größte Hebel liegt im Medienbruch zwischen Mail und CRM."
    assert _fehler(mit) == []


def test_v3_1_ohne_ausgangslage_ist_ungueltig():
    """Die Versionsnummer sagt, ob die Ausgangslage da ist.

    Eine 3.1 ohne Ausgangslage wäre von einer 3.0 nicht zu unterscheiden, die
    sich eine neue Nummer gegeben hat — wer liest, müsste das Feld suchen,
    statt sich auf die Version zu verlassen.
    """
    prio = _priorisierung()
    del prio["ausgangslage"]
    assert _fehler(prio)


def test_eine_ausgangslage_in_einer_v3_0_ist_ungueltig():
    """Umgekehrt: wer 3.0 schreibt, verspricht die Form ohne Ausgangslage."""
    assert _fehler(_priorisierung(schema_version="3.0"))


def test_eine_fehlende_angabe_ist_null_und_bleibt_gueltig():
    prio = _priorisierung(
        ausgangslage=als_ausgangslage(
            _mandant(region=None, mitarbeitende=None, geschaeftsmodell=None),
            [_konzept("KP-06", _schmerz("Stunden werden abgetippt"))],
        )
    )
    assert prio["ausgangslage"]["unternehmen"]["mitarbeitende"] is None
    assert _fehler(prio) == []


def test_eine_null_als_mitarbeiterzahl_ist_kein_vertragsinhalt_fuer_unbekannt():
    """Die 0 ist eine Zahl, kein Etikett für »nicht erhoben« (#167).

    Das Schema lässt sie zu — BC0s eigene Prüfung erlaubt ``>= 0`` —, aber
    ``als_ausgangslage`` erfindet sie nie aus einem fehlenden Wert.
    """
    aus = als_ausgangslage(_mandant(mitarbeitende=None), [_konzept("KP-06", _schmerz("x x x"))])
    assert aus["unternehmen"]["mitarbeitende"] is None


def test_herausforderungen_brauchen_ihre_kernprozesse():
    """Jede Ausgabe führt die Kernprozess-ID mit (Auflage BC0, 17.08.2026)."""
    prio = _priorisierung()
    prio["ausgangslage"]["herausforderungen"][0]["kp_ids"] = []
    assert _fehler(prio)


# ======================================================================
# 2. Rückwärtsverträglichkeit
# ======================================================================


def test_eine_v3_0_priorisierung_ohne_ausgangslage_bleibt_gueltig():
    prio = _priorisierung(schema_version="3.0")
    del prio["ausgangslage"]
    assert _fehler(prio) == []


def test_die_uebergebene_simulierte_lieferung_bleibt_gueltig():
    """Eine übergebene Lieferung wird nie ungültig, sie veraltet (ADR-007, 2.4)."""
    lieferung = json.loads((SIM / "prozesspriorisierung.json").read_text(encoding="utf-8"))
    assert lieferung["schema_version"] == "3.0"
    assert _fehler(lieferung) == []


# ======================================================================
# 3. Der maschinelle Teil
# ======================================================================


def test_das_unternehmen_kommt_maschinell_aus_dem_mandantensatz():
    aus = als_ausgangslage(_mandant(), [_konzept("KP-06", _schmerz("Stunden werden abgetippt"))])
    assert aus["unternehmen"] == {
        "name": "NoroAI Consulting GmbH",
        "branche": "KI-Beratung",
        "mitarbeitende": 10,
        "region": "FH-Suedwestfalen-Region",
        "geschaeftsmodell": "KI-Beratung mit eigenem Tech-Stack",
    }


def test_eine_leere_zeichenkette_ist_eine_luecke():
    """BC0 legt das Profil mit ``geschaeftsmodell = ''`` an (``app.py``,
    Mandant anlegen). Das ist kein Geschäftsmodell, sondern keines."""
    aus = als_ausgangslage(
        _mandant(geschaeftsmodell="", region="   "), [_konzept("KP-06", _schmerz("x x x"))]
    )
    assert aus["unternehmen"]["geschaeftsmodell"] is None
    assert aus["unternehmen"]["region"] is None


def test_herausforderungen_sind_die_schmerzpunkte_der_konzepte_zusammengefuehrt():
    """Derselbe Schmerzpunkt in zwei Kernprozessen ist **eine** Herausforderung.

    Zusammengeführt wird nur, was wörtlich gleich ist — Beschreibung,
    Auswirkung und Häufigkeit. Ähnliches zu verschmelzen wäre ein Urteil, und
    das gehört nicht in den maschinellen Teil.
    """
    doppelt = _schmerz("Daten werden doppelt erfasst", "Fehler und Verzug", haeufigkeit="täglich")
    aus = als_ausgangslage(
        _mandant(),
        [
            _konzept("KP-02", doppelt, _schmerz("Angebote entstehen in Word")),
            _konzept("KP-03", _schmerz("Belege kommen per Post"), dict(doppelt)),
        ],
    )
    assert aus["herausforderungen"] == [
        {
            "beschreibung": "Daten werden doppelt erfasst",
            "auswirkung": "Fehler und Verzug",
            "haeufigkeit": "täglich",
            "kp_ids": ["KP-02", "KP-03"],
        },
        {"beschreibung": "Angebote entstehen in Word", "auswirkung": "kostet Zeit", "kp_ids": ["KP-02"]},
        {"beschreibung": "Belege kommen per Post", "auswirkung": "kostet Zeit", "kp_ids": ["KP-03"]},
    ]


def test_aehnliche_schmerzpunkte_werden_nicht_verschmolzen():
    aus = als_ausgangslage(
        _mandant(),
        [
            _konzept("KP-02", _schmerz("Daten werden doppelt erfasst", "Fehler")),
            _konzept("KP-03", _schmerz("Daten werden doppelt erfasst", "Verzug")),
        ],
    )
    assert len(aus["herausforderungen"]) == 2


def test_die_kernaussage_wird_nur_geschrieben_wenn_sie_da_ist():
    k = [_konzept("KP-06", _schmerz("x x x"))]
    assert "kernaussage" not in als_ausgangslage(_mandant(), k)
    assert "kernaussage" not in als_ausgangslage(_mandant(), k, kernaussage="  ")
    assert als_ausgangslage(_mandant(), k, kernaussage=" Hebel. ")["kernaussage"] == "Hebel."


def test_die_ausgangslage_ist_reproduzierbar():
    k = [_konzept("KP-02", _schmerz("a a a")), _konzept("KP-03", _schmerz("b b b"))]
    assert als_ausgangslage(_mandant(), k) == als_ausgangslage(_mandant(), k)


# ======================================================================
# 4. Die Leseseite
# ======================================================================


def test_der_snapshot_liefert_region_und_geschaeftsmodell():
    bestand = SnapshotBestand(SNAPSHOT).lies_paket(
        NOROAI, "PKT-TEST", datetime(2026, 9, 20, tzinfo=timezone.utc), ["KP-02.TP-1"]
    )
    m = bestand.mandant
    assert m.name == "NoroAI Consulting GmbH"
    assert m.branche == "KI-Beratung"
    assert m.mitarbeitende == 10
    assert m.region == "FH-Suedwestfalen-Region"
    assert m.geschaeftsmodell == "KI-Beratung mit eigenem Tech-Stack"


def test_die_postgres_abfrage_liest_den_namen_aus_der_spalte_die_es_gibt():
    """``companies`` hat die Spalte ``name``, nicht ``company_name``.

    BC0s Schema (``schema_v1.1.1.sql``) und seine Dokumentation (v1.3, § 4)
    kennen nur ``name``; ``company_name`` kommt im ganzen Repo nur in BC2s
    Abfrage vor. ``stand_zum`` liefert das Zeilenbild als JSON, und ``->>`` auf
    einen fehlenden Schlüssel ergibt still ``NULL`` — der Mandantenname wäre in
    jedem Lauf leer gewesen, ohne Fehlermeldung. Gefunden beim Bau von #254.
    """
    sql = bestand_modul._SQL_MANDANT
    assert "'company_name'" not in sql
    assert "->> 'name'" in sql
    # Region und Geschäftsmodell — Letzteres liegt in company_profile, nicht in companies.
    assert "'region'" in sql
    assert "stand_zum('company_profile'" in sql
    assert "'geschaeftsmodell'" in sql
