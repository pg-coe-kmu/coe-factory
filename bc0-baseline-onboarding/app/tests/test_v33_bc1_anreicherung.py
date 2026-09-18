# -*- coding: utf-8 -*-
"""v3.3 — Die BC1-Anreicherung am Gate (#P4).

Bis zum 18.09.2026 gab ``_bc1_angaben()`` fest ``None`` zurueck. Das Gate
meldete deshalb "wartet auf BC1", obwohl BC1 seit dem 08.09. drei fertige
Profile in ``bc1.prozessprofil`` liegen hatte. Diese Tests halten fest, was
seither gilt.

Geprueft wird ohne Datenbank: ``_bc1_fehlende_angaben`` und ``_gate_am_zug``
sind reine Funktionen. Der Zugriff auf ``bc1.*`` selbst braucht PostgreSQL und
wird in ``pruefung_v3.3_bc1_anreicherung.sql`` gegen die Produktion geprueft.
"""
import app as A


def _profil(**abw):
    """Eine vollstaendige Profilzeile, wie sie aus bc1.prozessprofil kommt."""
    z = {"focus_step_id": "KP-06.TP-2", "profil_version": 2,
         "erhebung_id": "E-2026-08",
         "frequency_per_year": 180.0, "executions_per_run": 180.0,
         "total_duration_minutes": 180.0, "focus_step_duration_minutes": 90.0,
         "focus_step_duration_source": "geschaetzt",
         "focus_step_duration_confidence_pct": 60,
         "rollen_anzahl": 2}
    z.update(abw)
    return z


def _zeile(**abw):
    """Eine Bogenzeile mit erfuellten Vorbedingungen."""
    z = {"stand": None, "eigner_benannt": True, "vollstaendig_bewertet": True,
         "items_bewertet": 30}
    z.update(abw)
    return z


# --- Was "geliefert" heisst -------------------------------------------------

def test_vollstaendiges_profil_hat_keine_luecke():
    assert A._bc1_fehlende_angaben(_profil()) == []


def test_fehlende_rollen_werden_benannt():
    """Der Fall NoroAI am 18.09.2026: drei Werte da, profil_rollen leer."""
    assert A._bc1_fehlende_angaben(_profil(rollen_anzahl=0)) == ["Rollen mit Zeitanteil"]


def test_namensliste_im_profil_ersetzt_die_rollen_nicht():
    """focus_step_roles steht im JSONB, zaehlt aber nicht: Paare sind verlangt."""
    z = _profil(rollen_anzahl=0)
    z["focus_step_roles"] = "Office Management, Consultants"
    assert "Rollen mit Zeitanteil" in A._bc1_fehlende_angaben(z)


def test_jede_einzelne_angabe_wird_erkannt():
    for spalte, wortlaut in (("focus_step_duration_minutes", "Dauer"),
                             ("frequency_per_year", "Haeufigkeit"),
                             ("executions_per_run", "Menge")):
        assert A._bc1_fehlende_angaben(_profil(**{spalte: None})) == [wortlaut]


def test_reihenfolge_folgt_gate_bc1_felder():
    """Die Begruendung soll lesbar sein — also in der bekannten Reihenfolge."""
    leer = _profil(focus_step_duration_minutes=None, frequency_per_year=None,
                   executions_per_run=None, rollen_anzahl=0)
    assert A._bc1_fehlende_angaben(leer) == list(A.GATE_BC1_FELDER)


# --- Wer am Zug ist ---------------------------------------------------------

def test_ohne_bc1_bleibt_es_beim_alten_wortlaut():
    zustand, grund = A._gate_am_zug(_zeile(), None)
    assert zustand == "wartet_bc1"
    for feld in A.GATE_BC1_FELDER:
        assert feld in grund


def test_vollstaendige_anreicherung_gibt_frei():
    zustand, grund = A._gate_am_zug(_zeile(), {"profil_version": 2, "fehlend": []})
    assert zustand == "entscheiden"
    assert "Fassung 2" in grund


def test_teilstand_nennt_nur_was_fehlt():
    """Der Kern von #P4: nicht mehr pauschal alle vier aufzaehlen."""
    zustand, grund = A._gate_am_zug(
        _zeile(), {"profil_version": 2, "fehlend": ["Rollen mit Zeitanteil"]})
    assert zustand == "wartet_bc1"
    assert "Rollen mit Zeitanteil" in grund
    assert "Haeufigkeit" not in grund
    assert "Fassung 2" in grund


def test_vorbedingungen_gehen_vor_bc1():
    """Was BC0 selbst nachtragen kann, steht vor dem, worauf BC0 nur wartet."""
    zustand, _ = A._gate_am_zug(
        _zeile(eigner_benannt=False, items_bewertet=0, vollstaendig_bewertet=False),
        {"profil_version": 2, "fehlend": []})
    assert zustand == "bc0_pflege"


def test_entschieden_bleibt_entschieden():
    zustand, _ = A._gate_am_zug(_zeile(stand="freigegeben"), None)
    assert zustand == "entschieden"


# --- Rueckfallebene ---------------------------------------------------------

def test_ohne_postgres_kein_zugriff_und_kein_fehler():
    """SQLite kennt bc1.* nicht. Erwartet wird ein leeres Verzeichnis,
    nicht eine Ausnahme — das Gate bleibt ohne BC1 benutzbar."""
    if A.PG:
        return
    assert A._bc1_anreicherung(None, "egal") == {}


def test_feldzuordnung_deckt_alle_vier_felder_ab():
    assert tuple(w for w, _p, _s in A.BC1_FELD_ZU_PRUEFPUNKT) == A.GATE_BC1_FELDER
