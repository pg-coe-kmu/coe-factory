"""API-Verdrahtung: Reconcile im Turn, DB->Wire-Overlay, Post-Sweep-Hinweise, 503.

Der Durchstich laeuft ueber HTTP: was hier gemessen wird, ist das Verhalten des
Dienstes, nicht das des Writers (den prueft test_profil_writer.py isoliert).
"""
import dataclasses

import pytest
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from bc1_core.feldtypen import AUSWAHL
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.store import InMemoryStateStore
from bc1_service.api import FEHLER_TEXTE, HINWEIS_GUELTIG, HINWEIS_UNGELOEST, create_app
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket
from bc1_service.profil_writer import ProfilWriter
from tests.db_fixture import ANFRAGE_A, DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

ZUGANG = "z" * 43                     # Länge wie secrets.token_urlsafe(32)

KONTEXT = Bc0Kontext(
    company_id=MANDANT_A,
    teilprozesse=(("KP-01.TP-1", "Erfassen"), ("KP-01.TP-2", "Pruefen")),
    system_ids=("S-01", "S-02"), anfrage_id=ANFRAGE_A,
    rollen=(("R-01", "Sachbearbeitung"),))

# Alle 26 Pflichtfelder des Discovery-Pakets in einer Nachricht — so ist der
# Durchstich ein Turn und der Test bleibt lesbar.
WERTE = {
    "request_intent": "Angebote schneller rausbringen",
    "request_goal": "zeit_sparen",
    "scope_focus": "einzelner_schritt",
    "process_name": "Angebotserstellung",
    "process_owner_role": "R-01",
    "process_id": "KP-01",
    "process_steps": "Anfrage, Kalkulation, Angebot",
    "trigger_text": "Kundenanfrage per Mail",
    "input_text": "Anfrage mit Mengen",
    "input_format": "mail",
    "output_text": "Angebot als PDF",
    "frequency_per_year": "120",
    "executions_per_run": "3",
    "total_duration_minutes": "90",
    "focus_step": "KP-01.TP-1",
    "focus_step_duration_minutes": "30",
    "focus_step_duration_source": "geschaetzt",
    "focus_step_duration_confidence_pct": "70",
    "focus_step_roles": "Vertrieb, Kalkulation",
    "focus_step_systems": "SAP (s-01)",     # klein: Kanonisierung nachweisen
    "focus_step_media_break": "ja",
    "documentation_status": "3",
    "standardization_level": "4",
    "data_availability_score": "3",
    "stability_score": "4",
    "pii_involved": "ja",
}


def _llm(ohne=(), abweichend=None):
    werte = {**WERTE, **(abweichend or {})}
    erste = [ExtractionCandidate(n, w) for n, w in werte.items() if n not in ohne]
    zweite = [ExtractionCandidate(n, werte[n]) for n in ohne]
    return FakeLLM({"alles": erste, "rest": zweite})


@pytest.fixture
def umgebung():
    frische_db(DSN)
    pool = ConnectionPool(DSN, min_size=1, max_size=4, open=True,
                          kwargs={"options": "-c role=bc1_role"})
    paket = baue_discovery_paket(kontext=KONTEXT)
    yield pool, paket
    pool.close()


def _client(umgebung, ohne=(), abweichend=None):
    pool, paket = umgebung
    return TestClient(create_app(
        InMemoryStateStore(), _llm(ohne, abweichend), paket, company_id=MANDANT_A,
        anfrage_id=ANFRAGE_A, writer=ProfilWriter(pool, MANDANT_A, paket)))


def _turn(client, mid, text, session="s1", **extra):
    # Schritt 1: Anfrage und Mandant gehen immer mit (Pflichtfelder).
    return client.post("/turn", json={"session_id": session, "message_id": mid,
                                      "message": text, "anfrage_id": ANFRAGE_A,
                                      "company_id": MANDANT_A, **extra})


def test_durchstich_schreibt_genau_eine_eingefrorene_zeile(umgebung):
    antwort = _turn(_client(umgebung), "m1", "alles")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fertig"
    with verbindung(DSN) as conn:
        zeilen = conn.execute(
            "SELECT focus_step_id, process_id, status, erhebung_id, "
            "       frequency_per_year, focus_step_duration_confidence_pct, "
            "       paket_version, profil, anfrage_id "
            "  FROM bc1.prozessprofil").fetchall()
    assert len(zeilen) == 1
    zeile = zeilen[0]
    assert zeile[8] == ANFRAGE_A
    assert zeile[0] == "KP-01.TP-1" and zeile[1] == "KP-01"
    assert zeile[2] == "fertig" and zeile[3] == "E-2026-02"
    assert zeile[4] == 120 and zeile[5] == 70
    assert zeile[6].startswith("1.2+ctx-")
    assert zeile[7]["felder"]["process_name"]["wert"] == "Angebotserstellung"
    # Kanonisierung bis in die DB (Spec K4): 's-01' wird als 'S-01' gespeichert.
    assert zeile[7]["felder"]["focus_step_systems"]["wert"] == "SAP (S-01)"


def test_sweep_macht_das_feld_offen_und_der_payload_folgt_der_db(umgebung):
    # Alleinstehende Kennung: nach der Entfernung bleibt NICHTS uebrig.
    client = _client(umgebung, ohne=("pii_involved",),
                     abweichend={"focus_step_systems": "S-02"})
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:                 # System verschwindet
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    antwort = _turn(client, "m2", "rest").json()
    feld = antwort["payload"]["felder"]["focus_step_systems"]
    assert feld["status"] == "ungeloest"
    assert feld["wert"] is None
    assert "focus_step_systems" in antwort["payload"]["ungeloeste_felder"]
    assert antwort["payload"]["vollstaendigkeit"] < 1.0
    assert HINWEIS_UNGELOEST in antwort["chat_text"]
    with verbindung(DSN) as conn:
        gespeichert = conn.execute("SELECT profil FROM bc1.prozessprofil").fetchone()[0]
    assert gespeichert["vollstaendigkeit"] == antwort["payload"]["vollstaendigkeit"]
    assert "S-02" not in str(gespeichert)


def test_befunde_und_zaehler_kommen_ebenfalls_aus_der_db(umgebung):
    # Nicht im Plan, aber noetig: ohne diese beiden Schluessel im Overlay bliebe
    # der Befund (Quelle des Post-Sweep-Hinweises) unbelegt und die
    # Fortschrittszeile meldete "26 von 26", obwohl der Sweep ein Pflichtfeld
    # gerade offen gemacht hat — genau so gemessen (03.09.).
    client = _client(umgebung, ohne=("pii_involved",),
                     abweichend={"focus_step_systems": "S-02"})
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    antwort = _turn(client, "m2", "rest").json()
    with verbindung(DSN) as conn:
        gespeichert = conn.execute("SELECT profil FROM bc1.prozessprofil").fetchone()[0]
    assert antwort["payload"]["befunde"] == gespeichert["befunde"]
    assert antwort["payload"]["befunde"]["snn_entfernt"][0]["feld"] == (
        "focus_step_systems")
    assert antwort["payload"]["pflicht_erfasst"] == 25
    assert antwort["payload"]["pflicht_gesamt"] == 26
    assert "✓ 25 von 26 Pflichtfeldern erfasst" in antwort["chat_text"]


def test_sweep_mit_tragendem_rest_meldet_den_anderen_hinweis(umgebung):
    client = _client(umgebung, ohne=("pii_involved",),
                     abweichend={"focus_step_systems": "SAP (S-02)"})
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    # Wert war "SAP (S-02)" => "SAP" traegt nach der Entfernung weiter.
    antwort = _turn(client, "m2", "rest").json()
    assert antwort["payload"]["felder"]["focus_step_systems"]["status"] == "gueltig"
    assert antwort["payload"]["felder"]["focus_step_systems"]["wert"] == "SAP"
    assert HINWEIS_GUELTIG in antwort["chat_text"]


def test_mehrere_befunde_liefern_beide_hinweise_je_einmal(umgebung):
    # Nicht im Plan, aber der Fall, der beide Regeln zugleich traegt: der Sweep
    # laeuft ueber ALLE Felder. Drei Befunde, zwei davon mit gleichem Ausgang
    # => beide Texte muessen erscheinen, der wiederholte aber nur einmal (R11-I2).
    client = _client(umgebung, ohne=("pii_involved",), abweichend={
        "focus_step_systems": "S-02",                       # -> ungeloest
        "process_steps": "Anfrage (S-02), Kalkulation",     # -> gueltig
        "trigger_text": "Kundenanfrage per Mail (S-02)"})   # -> gueltig
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    antwort = _turn(client, "m2", "rest").json()
    befunde = antwort["payload"]["befunde"]["snn_entfernt"]
    assert sorted(b["feld"] for b in befunde) == [
        "focus_step_systems", "process_steps", "trigger_text"]
    assert antwort["chat_text"].count(HINWEIS_UNGELOEST) == 1
    assert antwort["chat_text"].count(HINWEIS_GUELTIG) == 1


def test_chat_text_setzt_sich_in_fester_reihenfolge_zusammen(umgebung):
    # Ohne diesen Test ueberleben drei Mutationen an der reinen Nutzersicht:
    # Hinweis hinter die Fortschrittszeile schieben, Hinweis-Reihenfolge
    # umdrehen, die Absatz-Trenner weglassen (Review 03.09., je gemessen).
    client = _client(umgebung, ohne=("pii_involved",), abweichend={
        "focus_step_systems": "S-02",                       # F2 -> ungeloest
        "process_steps": "Anfrage (S-02), Kalkulation",     # B5 -> gueltig
        "trigger_text": "Kundenanfrage per Mail (S-02)"})   # C1 -> gueltig
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    antwort = _turn(client, "m2", "rest").json()
    p = antwort["payload"]
    # Paket-Feldreihenfolge: B5/C1 (gueltig) vor F2 (ungeloest).
    assert antwort["chat_text"] == (
        p["abschluss_text"]
        + "\n\n" + HINWEIS_GUELTIG
        + "\n\n" + HINWEIS_UNGELOEST
        + f"\n\n✓ {p['pflicht_erfasst']} von {p['pflicht_gesamt']} "
          "Pflichtfeldern erfasst")


def test_replay_der_abschlussnachricht_liefert_denselben_hinweis_genau_einmal(umgebung):
    client = _client(umgebung, ohne=("pii_involved",),
                     abweichend={"focus_step_systems": "SAP (S-02)"})
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    erst = _turn(client, "m2", "rest").json()
    nochmal = _turn(client, "m2", "rest").json()
    assert nochmal == erst
    assert nochmal["chat_text"].count(HINWEIS_GUELTIG) == 1


def test_replay_einer_aelteren_frage_bleibt_historisch(umgebung):
    client = _client(umgebung, ohne=("pii_involved",))
    frage = _turn(client, "m1", "alles").json()
    _turn(client, "m2", "rest")
    assert _turn(client, "m1", "alles").json() == frage      # kein Overlay


def test_unbekannte_kennung_ueberlebt_das_nachfrage_limit_nicht(umgebung):
    # Spec K4: S-99 -> Nachfrage-Limit -> Abschluss => kein unbekanntes Token im
    # gespeicherten JSON, auch nicht unter den Kandidaten.
    pool, paket = umgebung
    llm = FakeLLM({
        "alles": [ExtractionCandidate(n, w) for n, w in WERTE.items()
                  if n != "focus_step_systems"],
        "systeme": [ExtractionCandidate("focus_step_systems", "Eigenbau (S-99)")],
        "nochmal": [ExtractionCandidate("focus_step_systems", "Eigenbau2 (S-99)")],
    })
    client = TestClient(create_app(InMemoryStateStore(), llm, paket,
                                   company_id=MANDANT_A,
                                   writer=ProfilWriter(pool, MANDANT_A, paket)))
    _turn(client, "m1", "alles")
    _turn(client, "m2", "systeme")
    antwort = _turn(client, "m3", "nochmal").json()
    assert antwort["status"] == "fertig"
    assert antwort["payload"]["felder"]["focus_step_systems"]["status"] == "ungeloest"
    with verbindung(DSN) as conn:
        gespeichert = conn.execute("SELECT profil FROM bc1.prozessprofil").fetchone()[0]
    assert "S-99" not in str(gespeichert)


def test_sweep_hinweis_ueberlebt_den_neustart_unveraendert(umgebung):
    # R10-I2: Ausloeser ist der persistente Befund in der DB, nicht Laufzeitwissen.
    pool, paket = umgebung
    store = InMemoryStateStore()                       # bleibt ueber den Neustart

    def _app():
        return TestClient(create_app(
            store, _llm(ohne=("pii_involved",),
                        abweichend={"focus_step_systems": "SAP (S-02)"}),
            paket, company_id=MANDANT_A,
            writer=ProfilWriter(pool, MANDANT_A, paket)))

    client = _app()
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    erst = _turn(client, "m2", "rest").json()
    nach_neustart = _turn(_app(), "m2", "rest").json()   # frische App, alter Store
    assert nach_neustart["chat_text"] == erst["chat_text"]
    assert nach_neustart["chat_text"].count(HINWEIS_GUELTIG) == 1


def test_recovery_nach_neustart_mit_geaendertem_ctx_holt_den_write_nach(umgebung):
    # Spec K0-Tabelle: 503 beim Abschluss -> Neustart mit geaenderten
    # Options-Mengen -> derselbe Replay MIT alter schema_version holt den Write nach.
    pool, paket = umgebung
    store = InMemoryStateStore()
    with verbindung(DSN) as conn:                        # fremder Draft blockiert
        conn.execute(
            "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
            "profil_version, process_id, status, erhebung_id, paket_version, profil) "
            "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-02', "
            "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))
        conn.commit()
    client = TestClient(create_app(store, _llm(), paket, company_id=MANDANT_A,
                                   writer=ProfilWriter(pool, MANDANT_A, paket)))
    assert _turn(client, "m1", "alles").status_code == 503
    with verbindung(DSN) as conn:
        conn.execute("DELETE FROM bc1.prozessprofil WHERE status = 'in_erhebung'")
        conn.commit()

    # Neustart mit zusaetzlichem BEWERTETEN Teilprozess => anderer ctx-Hash (Rev. 11)
    neuer_kontext = Bc0Kontext(
        MANDANT_A, KONTEXT.teilprozesse + (("KP-02.TP-1", "Bestellen A"),),
        KONTEXT.system_ids)
    neues_paket = baue_discovery_paket(kontext=neuer_kontext)
    assert neues_paket.schema_version != paket.schema_version
    client_neu = TestClient(create_app(
        store, _llm(), neues_paket, company_id=MANDANT_A,
        writer=ProfilWriter(pool, MANDANT_A, neues_paket)))
    antwort = _turn(client_neu, "m1", "alles",
                    schema_version=paket.schema_version)
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fertig"
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchall() == [
            ("fertig",)]


def test_recovery_mit_inzwischen_stillgelegter_rolle(umgebung):
    # Review Focus 5: Der Abschluss scheitert (fremder Draft), danach legt BC0 die
    # gewaehlte Rolle still und der Neustart-Kontext kennt sie nicht mehr (anderer
    # Fingerabdruck). Der Replay mit der alten schema_version holt den Write trotzdem
    # nach: gespeichert wird, was der Nutzer gewaehlt hat.
    pool, paket = umgebung
    store = InMemoryStateStore()
    with verbindung(DSN) as conn:                        # fremder Draft blockiert
        conn.execute(
            "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
            "profil_version, process_id, status, erhebung_id, paket_version, profil) "
            "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-02', "
            "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))
        conn.commit()
    client = TestClient(create_app(store, _llm(), paket, company_id=MANDANT_A,
                                   anfrage_id=ANFRAGE_A,
                                   writer=ProfilWriter(pool, MANDANT_A, paket)))
    assert _turn(client, "m1", "alles").status_code == 503
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM bc1.prozessprofil WHERE status = 'in_erhebung'")
        conn.execute("UPDATE mandant_rollen SET aktiv = false "
                     " WHERE company_id = %s AND rolle_id = 'R-01'", (MANDANT_A,))
        conn.commit()

    neuer_kontext = dataclasses.replace(KONTEXT, rollen=(("R-02", "Einkauf A"),))
    neues_paket = baue_discovery_paket(kontext=neuer_kontext)
    assert neues_paket.schema_version != paket.schema_version
    client_neu = TestClient(create_app(
        store, _llm(), neues_paket, company_id=MANDANT_A, anfrage_id=ANFRAGE_A,
        writer=ProfilWriter(pool, MANDANT_A, neues_paket)))
    antwort = _turn(client_neu, "m1", "alles", schema_version=paket.schema_version)
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fertig"
    with verbindung(DSN) as conn:
        zeile = conn.execute(
            "SELECT status, process_owner_rolle_id, "
            "       profil->'felder'->'process_owner_role', anfrage_id "
            "  FROM bc1.prozessprofil").fetchall()
    assert len(zeile) == 1
    status, spalte, feld, anfrage = zeile[0]
    assert (status, spalte, anfrage) == ("fertig", "R-01", ANFRAGE_A)
    assert feld["status"] == "gueltig" and feld["wert"] == "R-01"


class _StoreMitFremdemNachladen(InMemoryStateStore):
    """Liefert beim ZWEITEN load des Turns einen fremden Mandanten.

    Der Nachlade-Vorgang der API ist die einzige Stelle, an der ein Zustand ohne
    erneute Pruefung zum Writer gehen koennte; der Writer schreibt mit SEINER
    company_id und wuerde fremde Interviewinhalte unter dem eigenen Mandanten
    ablegen. Nur mit einem gestoerten Store ist dieser Guard messbar.
    """

    def __init__(self) -> None:
        super().__init__()
        self.geladen = 0

    def load(self, session_id: str):
        # Gezaehlt werden nur Ladevorgaenge MIT Zustand: im ersten Turn sind die
        # beiden ersten Aufrufe (Gate der API, Start des Kerns) noch leer, der
        # erste nicht-leere ist genau das Nachladen vor dem Reconcile.
        state = super().load(session_id)
        if state is None:
            return None
        self.geladen += 1
        if self.geladen == 1:
            state.company_id = MANDANT_B
        return state


def test_fremder_mandant_beim_nachladen_wird_abgewiesen_statt_geschrieben(umgebung):
    pool, paket = umgebung
    client = TestClient(create_app(
        _StoreMitFremdemNachladen(), _llm(), paket, company_id=MANDANT_A,
        writer=ProfilWriter(pool, MANDANT_A, paket)))
    antwort = _turn(client, "m1", "alles")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "mandant_konflikt"
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil"
                            ).fetchone()[0] == 0


class _StoreMitFremderAnfrageBeimNachladen(_StoreMitFremdemNachladen):
    """Wie oben, nur kippt die Anfrage statt des Mandanten (B5)."""

    def load(self, session_id: str):
        state = InMemoryStateStore.load(self, session_id)
        if state is None:
            return None
        self.geladen += 1
        if self.geladen == 1:
            state.anfrage_id = "A-FREMD"
        return state


def test_fremde_anfrage_beim_nachladen_wird_abgewiesen_statt_geschrieben(umgebung):
    pool, paket = umgebung
    client = TestClient(create_app(
        _StoreMitFremderAnfrageBeimNachladen(), _llm(), paket,
        company_id=MANDANT_A, anfrage_id=ANFRAGE_A,
        writer=ProfilWriter(pool, MANDANT_A, paket)))
    antwort = _turn(client, "m1", "alles")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil"
                            ).fetchone()[0] == 0


@pytest.fixture
def main_laden(umgebung, monkeypatch):
    # Laedt bc1_service.main frisch hinter einem strengen create_app-Double (B8:
    # store, llm, package positional, alles Weitere benannt) und raeumt danach auf,
    # auch wenn der Test scheitert. Fabrik statt Import in der Fixture: ein Test
    # kann vor dem Laden noch die Umgebung aendern.
    import importlib
    import sys

    from bc1_service import api as api_modul

    gesehen: dict = {}

    def _stub_create_app(store, llm, package, **kw):
        gesehen.update(kw, package=package)
        return "app"

    monkeypatch.setattr(api_modul, "create_app", _stub_create_app)
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_COMPANY_ID", MANDANT_A)
    monkeypatch.setenv("BC1_ANFRAGE_ID", ANFRAGE_A)
    monkeypatch.setenv("BC1_LLM", "ollama")     # kein API-Key noetig
    monkeypatch.setenv("BC1_BC0_MELDUNGEN", "aus")
    monkeypatch.setenv("BC1_ZUGANG", ZUGANG)
    geladen: list = []

    def _laden():
        # Genau ein Aufruf je Test: beim zweiten merkte sich monkeypatch das erste
        # Modul und stellte es beim Rueckbau mit geschlossenen Pools wieder her.
        assert not geladen, "main_laden() nur einmal je Test aufrufen"
        monkeypatch.delitem(sys.modules, "bc1_service.main", raising=False)
        geladen.append(importlib.import_module("bc1_service.main"))
        return geladen[-1], gesehen

    yield _laden
    for main in geladen:
        main._store.close()
        main._profil_pool.close()
    sys.modules.pop("bc1_service.main", None)


def test_main_verdrahtet_den_profil_writer(main_laden):
    # Ohne diesen Test bliebe die Produktions-Verdrahtung ungeschuetzt: faellt
    # das writer-Argument in main.py weg, bleibt die ganze Suite gruen — und der
    # Dienst schriebe im Betrieb kein einziges Profil (Lehre aus dem T14-Review).
    main, gesehen = main_laden()
    assert gesehen["company_id"] == MANDANT_A
    assert gesehen["anfrage_id"] == ANFRAGE_A
    # Schritt 1 (27.10.): ohne diese Zeile liefe der Dienst im Betrieb ohne Zugangsprüfung.
    assert gesehen["zugang"] == ZUGANG
    assert isinstance(gesehen["writer"], ProfilWriter)
    # Dasselbe Paket-Objekt fuer Kern und Writer: zwei getrennte Bauten
    # koennten auseinanderlaufen (Reihenfolge der BC0-Mengen).
    assert gesehen["writer"]._package is gesehen["package"]
    # B4: BC1_BC0_MELDUNGEN=aus -> kein Melder (die Uebergabe an create_app prueft Task 5).
    assert main._melder is None
    assert gesehen["melder"] is None


def test_main_baut_b4_aus_den_kernprozessen_des_mandanten(main_laden):
    _, gesehen = main_laden()
    paket = gesehen["package"]
    b4 = paket.field("process_id").typ
    assert b4.validator("KP-02") is True and b4.validator("KP-03") is False
    e5 = paket.field("focus_step").typ          # E5 bleibt auf ANFRAGE_A begrenzt
    assert e5.validator("KP-01.TP-1") is True and e5.validator("KP-02.TP-1") is False


def test_main_uebergibt_create_app_keine_weiteren_positionsargumente(main_laden):
    # Strenges Double (B8): store, llm, package sind die einzigen Positionsargumente;
    # alles Weitere (lifespan, company_id, ...) geht benannt. Das Double der
    # Fixture main_laden ist streng; dieser Test haelt die Regel ausdruecklich fest.
    _, gesehen = main_laden()
    assert gesehen["lifespan"] is not None


def test_main_startet_trotz_alter_snapshot_variable(main_laden, monkeypatch):
    # B8: BC1_SNAPSHOT_PFAD ist abgeloest; eine uebrig gebliebene Variable in
    # einer alten Umgebung darf den Start weder brechen noch etwas laden.
    monkeypatch.setenv("BC1_SNAPSHOT_PFAD", "/gibt/es/nicht.json")
    _, gesehen = main_laden()
    assert gesehen["lifespan"] is not None


class _StartMelder:
    def __init__(self):
        self.gemeldet: list[str] = []
        self.gate: list[str] = []
        self.geprueft = 0

    def pruefe_konto(self):
        self.geprueft += 1

    def ziehe_gate_nach(self, anfrage_id):
        self.gate.append(anfrage_id)

    def melde_interview_laeuft(self, anfrage_id):
        self.gemeldet.append(anfrage_id)


def _main_mit_melder(monkeypatch, anfrage_id, melder, gesehen=None):
    import importlib
    import sys

    from bc1_service import api as api_modul
    from bc1_service import bc0_meldungen

    def _stub_create_app(*a, **kw):
        if gesehen is not None:
            gesehen.update(kw)
        return "app"

    monkeypatch.setattr(api_modul, "create_app", _stub_create_app)
    monkeypatch.setattr(bc0_meldungen, "baue_melder", lambda umgebung, cid: melder)
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_COMPANY_ID", MANDANT_A)
    monkeypatch.setenv("BC1_ANFRAGE_ID", anfrage_id)
    monkeypatch.setenv("BC1_ZUGANG", ZUGANG)
    monkeypatch.setenv("BC1_LLM", "ollama")
    monkeypatch.delitem(sys.modules, "bc1_service.main", raising=False)
    return importlib.import_module("bc1_service.main")


def test_main_meldet_eine_zugeordnete_anfrage_beim_start(umgebung, monkeypatch):
    import sys

    melder = _StartMelder()
    main = _main_mit_melder(monkeypatch, ANFRAGE_A, melder)        # Fixture: 'zugeordnet'
    try:
        assert melder.gemeldet == [ANFRAGE_A]
        assert main._melder is melder
    finally:
        main._store.close()
        main._profil_pool.close()
        sys.modules.pop("bc1_service.main", None)


def test_main_zieht_beim_start_das_gate_fuer_die_eigene_anfrage_nach(umgebung, monkeypatch):
    import sys

    melder = _StartMelder()
    main = _main_mit_melder(monkeypatch, ANFRAGE_A, melder)
    try:
        assert melder.gate == [ANFRAGE_A]
        assert melder.gemeldet == [ANFRAGE_A]
    finally:
        main._store.close()
        main._profil_pool.close()
        sys.modules.pop("bc1_service.main", None)


def test_main_bricht_ab_wenn_das_gate_die_anfrage_schon_abschliesst(umgebung, monkeypatch):
    class _GateSchliesstAb(_StartMelder):
        def ziehe_gate_nach(self, anfrage_id):
            super().ziehe_gate_nach(anfrage_id)
            # So wirkt BC0, wenn alle Teilprozesse der Anfrage fertig sind (v3.13).
            with verbindung(DSN, None) as conn:
                conn.execute("UPDATE ref_anfragen SET status = 'am_gate' "
                             "WHERE company_id = %s AND anfrage_id = %s", (MANDANT_A, anfrage_id))
                conn.commit()

    melder = _GateSchliesstAb()
    with pytest.raises(RuntimeError, match="steht auf 'am_gate'"):
        _main_mit_melder(monkeypatch, ANFRAGE_A, melder)
    assert melder.gemeldet == []


def test_main_meldet_eine_anfrage_im_interview_nicht_erneut(umgebung, monkeypatch):
    import sys

    # ANFRAGE_A (startfaehig: alle TPs bewertet) auf 'im_interview' stellen — die
    # Fixture-Anfrage im Stand 'im_interview' (A-2026-02, ganzer KP-01) bricht schon an
    # der B5-Pruefung ab (KP-01.TP-3 unbewertet, test_start.py).
    with verbindung(DSN, None) as conn:
        conn.execute("UPDATE ref_anfragen SET status = 'im_interview' "
                     "WHERE company_id = %s AND anfrage_id = %s", (MANDANT_A, ANFRAGE_A))
        conn.commit()
    melder = _StartMelder()
    main = _main_mit_melder(monkeypatch, ANFRAGE_A, melder)
    try:
        assert melder.gemeldet == []
    finally:
        main._store.close()
        main._profil_pool.close()
        sys.modules.pop("bc1_service.main", None)


def test_main_bricht_bei_im_interview_ab_wenn_die_kontopruefung_scheitert(umgebung, monkeypatch):
    from bc1_service.bc0_meldungen import Bc0MeldungFehler

    with verbindung(DSN, None) as conn:
        conn.execute("UPDATE ref_anfragen SET status = 'im_interview' "
                     "WHERE company_id = %s AND anfrage_id = %s", (MANDANT_A, ANFRAGE_A))
        conn.commit()

    class _KontoKaputt(_StartMelder):
        def pruefe_konto(self):
            super().pruefe_konto()          # zaehlt den Aufruf, dann der Mangel
            raise Bc0MeldungFehler("Das BC0-Anwendungskonto darf nicht schreiben (Rolle 'leser').")

    melder = _KontoKaputt()
    with pytest.raises(Bc0MeldungFehler, match="darf nicht schreiben"):
        _main_mit_melder(monkeypatch, ANFRAGE_A, melder)
    assert melder.geprueft == 1
    assert melder.gemeldet == []


def test_main_schliesst_die_pools_wenn_die_meldung_scheitert(umgebung, monkeypatch):
    from bc1_service.bc0_meldungen import Bc0MeldungFehler

    geschlossen: list[str] = []
    original = ConnectionPool.close

    def _close(self, *a, **kw):
        geschlossen.append("pool")
        return original(self, *a, **kw)

    class _Kaputt(_StartMelder):
        def melde_interview_laeuft(self, anfrage_id):
            raise Bc0MeldungFehler("BC0 unter https://x ist nicht erreichbar (ConnectError).")

    monkeypatch.setattr(ConnectionPool, "close", _close)
    with pytest.raises(Bc0MeldungFehler, match="nicht erreichbar"):
        _main_mit_melder(monkeypatch, ANFRAGE_A, _Kaputt())
    assert len(geschlossen) >= 2          # Session-Store-Pool + Profil-Pool


def test_main_schliesst_die_pools_wenn_das_gate_beim_start_scheitert(umgebung, monkeypatch):
    from bc1_service.bc0_meldungen import Bc0MeldungFehler

    geschlossen: list[str] = []
    original = ConnectionPool.close

    def _close(self, *a, **kw):
        geschlossen.append("pool")
        return original(self, *a, **kw)

    class _GateKaputt(_StartMelder):
        def ziehe_gate_nach(self, anfrage_id):
            raise Bc0MeldungFehler("BC0 antwortet auf 'Gate nachziehen' mit 500: x")

    monkeypatch.setattr(ConnectionPool, "close", _close)
    with pytest.raises(Bc0MeldungFehler, match="Gate nachziehen"):
        _main_mit_melder(monkeypatch, ANFRAGE_A, _GateKaputt())
    assert len(geschlossen) >= 2


def test_main_reicht_den_melder_an_die_app_durch(umgebung, monkeypatch):
    import sys

    melder = _StartMelder()
    gesehen: dict = {}
    main = _main_mit_melder(monkeypatch, ANFRAGE_A, melder, gesehen)
    try:
        assert gesehen["melder"] is melder
    finally:
        main._store.close()
        main._profil_pool.close()
        sys.modules.pop("bc1_service.main", None)


def test_abbruch_mit_blockiertem_aufraeumen_liefert_trotzdem_200(umgebung, caplog):
    # Spec K4 verlangt den Nachweis auf HTTP-Ebene: DELETE-Fehler beim Aufraeumen
    # => 200 + Logeintrag + Draft bleibt (Codex R3-I4). Ein zweifeldriges Paket
    # laesst den Abbruch in zwei Turns erreichen.
    pool, _ = umgebung
    # ZWEI Pflichtfelder: sonst waere die Session schon nach Turn 1 fertig und
    # Turn 2 bekaeme 409 statt des Abbruchs (Codex R4-N4-I1).
    knapp = UseCasePackage(
        name="discovery", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa", max_rounds=2,
        fields=(FieldSpec("focus_step", "Welcher Schritt?",
                          typ=AUSWAHL("KP-01.TP-1", "KP-01.TP-2"),
                          identitaetskritisch=True),
                FieldSpec("dauer", "Wie lange dauert der Schritt?")))
    llm = FakeLLM({
        "schritt": [ExtractionCandidate("focus_step", "KP-01.TP-1")],
        # Zweitnennung eines ANDEREN gueltigen Schritts => Feld wird UNKLAR;
        # am Rundenlimit greift damit der Completion-Guard.
        "wirr": [ExtractionCandidate("focus_step", "KP-01.TP-2")]})
    client = TestClient(create_app(InMemoryStateStore(), llm, knapp,
                                   company_id=MANDANT_A,
                                   writer=ProfilWriter(pool, MANDANT_A, knapp)))
    erst = _turn(client, "m1", "schritt")
    assert erst.json()["status"] == "frage"             # Session laeuft weiter
    with verbindung(DSN) as conn:                        # Draft gebunden?
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchall() == [
            ("in_erhebung",)]
        assert conn.execute("SELECT count(*) FROM bc1.profil_write_status"
                            ).fetchone()[0] == 1
    with verbindung(DSN) as conn:                       # DELETE blockieren
        conn.execute(
            "CREATE FUNCTION bc1.tf_blockiere() RETURNS trigger LANGUAGE plpgsql "
            "AS $fn$ BEGIN RAISE EXCEPTION 'Aufraeumen blockiert'; END $fn$")
        conn.execute("CREATE TRIGGER tr_blockiere BEFORE DELETE ON bc1.prozessprofil "
                     "FOR EACH ROW EXECUTE FUNCTION bc1.tf_blockiere()")
        conn.commit()
    with caplog.at_level("ERROR"):
        antwort = _turn(client, "m2", "wirr")           # macht das Feld unklar => Abbruch
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "abgebrochen_ohne_identitaet"
    assert "draft_aufraeumen_fehlgeschlagen" in caplog.text
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchall() == [
            ("in_erhebung",)]                            # verwaister Draft bleibt


def test_der_sweep_hinweis_kostet_keinen_zweiten_llm_aufruf(umgebung):
    # Normativ (R9-I1/R10-I1): der Zusatz ist fester Text. Bisher war das nur
    # am Ergebnis sichtbar, nicht als Aufruf-Vertrag — ein spaeteres "lass den
    # Abschluss neu formulieren" waere unbemerkt durchgegangen (Codex 03.09.).
    pool, paket = umgebung

    class _ZaehlendesLLM(FakeLLM):
        aufrufe = 0

        def antworte(self, kontext):
            type(self).aufrufe += 1
            return super().antworte(kontext)

    llm = _ZaehlendesLLM(_llm(ohne=("pii_involved",), abweichend={
        "focus_step_systems": "SAP (S-02)"})._extractions)
    client = TestClient(create_app(InMemoryStateStore(), llm, paket,
                                   company_id=MANDANT_A,
                                   writer=ProfilWriter(pool, MANDANT_A, paket)))
    _turn(client, "m1", "alles")
    with verbindung(DSN, None) as conn:
        conn.execute("DELETE FROM mandant_systeme WHERE company_id = %s "
                     "AND system_id = 'S-02'", (MANDANT_A,))
        conn.commit()
    antwort = _turn(client, "m2", "rest").json()
    assert HINWEIS_GUELTIG in antwort["chat_text"]       # Hinweis ist da ...
    assert _ZaehlendesLLM.aufrufe == 2                   # ... und kostete nichts
    _turn(client, "m2", "rest")                          # Replay: gar kein Aufruf
    assert _ZaehlendesLLM.aufrufe == 2


def test_llm_ausfall_bleibt_fortsetzbar_auch_mit_verdrahtetem_writer(umgebung):
    # Der Writer haelt sich bei diesem Status heraus (test_profil_writer.py) —
    # ueber /turn war der Pfad aber nie gefahren. Kippt er, machte die API aus
    # einem fortsetzbaren LLM-Aussetzer still einen 503 (Review 03.09.).
    pool, paket = umgebung

    class _KaputtesLLM(FakeLLM):
        def extract(self, message, package, state):
            raise RuntimeError("LLM kaputt")

    client = TestClient(create_app(InMemoryStateStore(), _KaputtesLLM(), paket,
                                   company_id=MANDANT_A,
                                   writer=ProfilWriter(pool, MANDANT_A, paket)))
    antwort = _turn(client, "m1", "alles")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fehler_fortsetzbar"
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM bc1.prozessprofil"
                            ).fetchone()[0] == 0


def test_503_traegt_den_stabilen_detail_string(umgebung):
    # Der Detail-String ist Schnittstelle (Plan "Produces": 503
    # profil_write_fehlgeschlagen), nicht Prosa — bisher pinnte ihn nichts,
    # ein stiller Rename waere unbemerkt geblieben (Review 03.09.).
    client = _client(umgebung)
    with verbindung(DSN) as conn:                            # fremder Draft im Weg
        conn.execute(
            "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
            "profil_version, process_id, status, erhebung_id, paket_version, profil) "
            "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-02', "
            "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))
        conn.commit()
    antwort = _turn(client, "m1", "alles")
    assert antwort.status_code == 503
    assert antwort.json()["detail"] == "profil_write_fehlgeschlagen"
    assert antwort.json()["chat_text"] == FEHLER_TEXTE["profil_write_fehlgeschlagen"]


def test_write_fehler_erzeugt_503_und_der_replay_holt_ihn_nach(umgebung):
    client = _client(umgebung)
    with verbindung(DSN) as conn:                            # fremder Draft im Weg
        conn.execute(
            "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
            "profil_version, process_id, status, erhebung_id, paket_version, profil) "
            "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-02', "
            "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))
        conn.commit()
    assert _turn(client, "m1", "alles").status_code == 503
    with verbindung(DSN) as conn:                            # Betriebsweg K5
        conn.execute("DELETE FROM bc1.prozessprofil WHERE status = 'in_erhebung'")
        conn.commit()
    nachgeholt = _turn(client, "m1", "alles")                # derselbe message_id
    assert nachgeholt.status_code == 200
    assert nachgeholt.json()["status"] == "fertig"
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchall() == [
            ("fertig",)]


class _GateZaehler:
    def __init__(self):
        self.aufrufe = 0
        self.anfragen: list[str] = []

    def ziehe_gate_nach(self, anfrage_id):
        self.aufrufe += 1
        self.anfragen.append(anfrage_id)
        return [ANFRAGE_A]


def test_eingefrorenes_profil_stoesst_das_gate_einmal_an(umgebung):
    pool, paket = umgebung
    melder = _GateZaehler()
    client = TestClient(create_app(
        InMemoryStateStore(), _llm(), paket, company_id=MANDANT_A, anfrage_id=ANFRAGE_A,
        writer=ProfilWriter(pool, MANDANT_A, paket), melder=melder))
    antwort = _turn(client, "m1", "alles")
    assert antwort.json()["status"] == "fertig"
    assert melder.aufrufe == 1
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchone()[0] == "fertig"


def test_eingefrorenes_profil_zieht_das_gate_fuer_die_eigene_anfrage_nach(umgebung):
    pool, paket = umgebung
    melder = _GateZaehler()
    client = TestClient(create_app(
        InMemoryStateStore(), _llm(), paket, company_id=MANDANT_A, anfrage_id=ANFRAGE_A,
        writer=ProfilWriter(pool, MANDANT_A, paket), melder=melder))
    _turn(client, "m1", "alles")
    assert melder.anfragen == [ANFRAGE_A]


# --- Paket (4): Abschluss nachholen (B2 eng + H, design/Spec-Abschluss-nachholen.md) ---
# Gegen den echten Writer: ein Fake hinter der API waere fuer den tdd-guard nicht
# treibbar (die API faengt jede Ausnahme), und echtes Verhalten ist ohnehin der
# bessere Beleg (Ledger, Ruling Task 3).

ABSCHLUSS_AUSSTEHEND_TEXT = (
    "Ihr Interview ist abgeschlossen, das Ergebnis konnte aber noch nicht "
    "gespeichert werden. Bitte wenden Sie sich an Ihre Ansprechperson.")


def _fremder_entwurf():
    with verbindung(DSN) as conn:
        conn.execute(
            "INSERT INTO bc1.prozessprofil (company_id, focus_step_id, "
            "profil_version, process_id, status, erhebung_id, paket_version, profil) "
            "VALUES (%s, 'KP-01.TP-1', 1, 'KP-01', 'in_erhebung', 'E-2026-02', "
            "'1.1+ctx-0000000000000000', '{}')", (MANDANT_A,))
        conn.commit()


def test_fremder_entwurf_gibt_beim_neusenden_abschluss_ausstehend(umgebung):
    client = _client(umgebung)
    _fremder_entwurf()
    assert _turn(client, "m1", "alles").status_code == 503
    antwort = _turn(client, "m2", "nochmal")
    assert antwort.status_code == 409
    assert antwort.json() == {"detail": "abschluss_ausstehend",
                              "chat_text": ABSCHLUSS_AUSSTEHEND_TEXT}
    with verbindung(DSN) as conn:                     # nichts angelegt, nichts umgebunden
        assert conn.execute("SELECT focus_step_id, profil_version, status "
                            "FROM bc1.prozessprofil").fetchall() == [
            ("KP-01.TP-1", 1, "in_erhebung")]


def test_abgebrochene_sitzung_fragt_den_writer_nicht():
    # Ein Writer auf nie geoeffnetem Pool: Wird er gefragt, gibt es PoolClosed und
    # damit nie 409. Abgebrochen ohne Identitaet hat kein Profil — nichts steht aus.
    ident = UseCasePackage(
        name="ident_test", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa", max_rounds=2,
        fields=(FieldSpec("tp_id", "Welcher Schritt?",
                          validator=lambda v: v == "KP-01.TP-1",
                          identitaetskritisch=True),))
    client = TestClient(create_app(
        InMemoryStateStore(), FakeLLM(), ident, company_id=MANDANT_A,
        writer=ProfilWriter(ConnectionPool(DSN, open=False), MANDANT_A, ident)))
    _turn(client, "m1", "a")
    assert _turn(client, "m2", "b").json()["status"] == "abgebrochen_ohne_identitaet"
    antwort = _turn(client, "m3", "noch etwas")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "session_abgeschlossen"


def _profilstatus():
    with verbindung(DSN) as conn:
        return conn.execute("SELECT status FROM bc1.prozessprofil").fetchall()


def test_kurze_stoerung_wird_beim_neusenden_nachgeholt(umgebung):
    # Die Stoerung kommt NACH dem UPDATE (_EinmalGestoerterWriter): der Rueckroll
    # wird gemessen, nicht nur ein Fehler vor dem Schreiben.
    pool, paket = umgebung
    store, melder = InMemoryStateStore(), _GateZaehler()
    client = TestClient(create_app(
        store, _llm(ohne=("pii_involved",)), paket, company_id=MANDANT_A,
        anfrage_id=ANFRAGE_A, writer=_EinmalGestoerterWriter(pool, MANDANT_A, paket),
        melder=melder))
    assert _turn(client, "m1", "alles").json()["status"] == "frage"
    assert _turn(client, "m2", "rest").status_code == 503
    assert _profilstatus() == [("in_erhebung",)] and melder.aufrufe == 0
    log_vorher = len(store.load("s1").raw_log)

    antwort = _turn(client, "m3", "nochmal")                 # neue Kennung
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "fertig"
    payload = antwort.json()["payload"]
    assert antwort.json()["chat_text"].startswith(payload["abschluss_text"])
    with verbindung(DSN) as conn:
        db_profil = conn.execute("SELECT profil FROM bc1.prozessprofil").fetchone()[0]
    assert payload["befunde"] == db_profil["befunde"] != {}  # Overlay aus der DB
    assert _profilstatus() == [("fertig",)] and melder.aufrufe == 1
    gespeichert = store.load("s1")                           # neue Nachricht nie gespeichert
    assert len(gespeichert.raw_log) == log_vorher
    assert "m3" not in gespeichert.processed_message_ids

    assert _turn(client, "m3", "nochmal").json()["detail"] == "session_abgeschlossen"
    assert _turn(client, "m4", "danke").json()["detail"] == "session_abgeschlossen"
    assert _profilstatus() == [("fertig",)] and melder.aufrufe == 1


def _stilllegen(tp="KP-01.TP-1"):
    with verbindung(DSN, None) as conn:                     # BC0-Tabelle: nicht als bc1_role
        conn.execute("UPDATE ref_teilprozesse SET aktiv = false "
                     " WHERE company_id = %s AND sub_process_id = %s", (MANDANT_A, tp))
        conn.commit()


def test_nachholbar_aber_paket_geaendert_gibt_abschluss_ausstehend(umgebung):
    # Neustart mit anderem ctx-Hash zwischen Abschluss und Neusenden: Der Kern
    # wuerde paket_konflikt melden. Das Gate prueft dieselbe Regel vorher (paket_passt).
    pool, paket = umgebung
    store = InMemoryStateStore()
    client = TestClient(create_app(
        store, _llm(ohne=("pii_involved",)), paket, company_id=MANDANT_A,
        anfrage_id=ANFRAGE_A, writer=ProfilWriter(pool, MANDANT_A, paket)))
    _turn(client, "m1", "alles")                             # eigener Entwurf steht
    _stilllegen()
    assert _turn(client, "m2", "rest").status_code == 503    # Abschluss scheitert

    neues_paket = baue_discovery_paket(kontext=dataclasses.replace(
        KONTEXT, teilprozesse=KONTEXT.teilprozesse + (("KP-02.TP-1", "Bestellen A"),)))
    assert neues_paket.schema_version != paket.schema_version
    client_neu = TestClient(create_app(
        store, _llm(), neues_paket, company_id=MANDANT_A, anfrage_id=ANFRAGE_A,
        writer=ProfilWriter(pool, MANDANT_A, neues_paket)))
    antwort = _turn(client_neu, "m3", "nochmal")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "abschluss_ausstehend"


def test_lesefehler_im_gate_gibt_503(umgebung):
    # Kann der Abschlussstand nicht gelesen werden, ist offen, ob das Profil fehlt:
    # 503 wie beim Schreiben — ein 409 verschwiege es, ein 500 waere kein Konflikt.
    _, paket = umgebung
    client = TestClient(create_app(
        InMemoryStateStore(), _llm(), paket, company_id=MANDANT_A, anfrage_id=ANFRAGE_A,
        writer=ProfilWriter(ConnectionPool(DSN, open=False), MANDANT_A, paket)))
    assert _turn(client, "m1", "alles").status_code == 503
    antwort = _turn(client, "m2", "nochmal")
    assert antwort.status_code == 503
    assert antwort.json()["detail"] == "profil_write_fehlgeschlagen"


class _EinmalGestoerterWriter(ProfilWriter):
    """Erstes Einfrieren scheitert NACH dem UPDATE (kurze Stoerung), danach normal."""
    gestoert = False

    def _einfrieren(self, conn, bindung, inhalt):
        profil = super()._einfrieren(conn, bindung, inhalt)
        if not self.gestoert:
            self.gestoert = True
            raise RuntimeError("kurze Stoerung")
        return profil


def test_nachgeholter_abschluss_wird_protokolliert(umgebung, caplog):
    pool, paket = umgebung
    client = TestClient(create_app(
        InMemoryStateStore(), _llm(ohne=("pii_involved",)), paket, company_id=MANDANT_A,
        anfrage_id=ANFRAGE_A, writer=_EinmalGestoerterWriter(pool, MANDANT_A, paket)))
    _turn(client, "m1", "alles")
    _turn(client, "m2", "rest")                               # 503
    with caplog.at_level("INFO", logger="bc1.api"):
        assert _turn(client, "m3", "nochmal").status_code == 200
    zeilen = [r.getMessage() for r in caplog.records
              if r.name == "bc1.api" and r.getMessage().startswith("abschluss_")]
    assert zeilen == ["abschluss_nachgeholt session=s1 message=m3"]


def test_abschluss_ausstehend_protokolliert_keinen_text(umgebung, caplog):
    # Der Betrieb braucht das Signal und die Kennung des Abschluss-Turns, um von
    # Hand nachzuholen — den Text der Nachricht nie (B7).
    client = _client(umgebung)
    _fremder_entwurf()
    _turn(client, "m1", "alles")                              # 503
    with caplog.at_level("INFO"):
        _turn(client, "m2", "Nordlicht-4711 bitte nochmal")
    warnungen = [r for r in caplog.records
                 if r.name == "bc1.api" and r.levelname == "WARNING"]
    assert [r.getMessage() for r in warnungen] == [
        "abschluss_ausstehend session=s1 message=m2 abschluss=m1"]
    assert any("http=409 status=abschluss_ausstehend" in r.getMessage()
               for r in caplog.records if r.name == "bc1.dienst")
    assert all("Nordlicht" not in r.getMessage() for r in caplog.records)


def test_stillgelegter_teilprozess_bleibt_bei_503_ohne_neuen_entwurf(umgebung):
    # Dauerhafte Ursache bei offenem eigenen Entwurf: Nachholen scheitert jedes Mal
    # gleich (503-Schleife), ohne etwas anzulegen oder die Sitzung zu veraendern.
    pool, paket = umgebung
    store = InMemoryStateStore()
    client = TestClient(create_app(
        store, _llm(ohne=("pii_involved",)), paket, company_id=MANDANT_A,
        anfrage_id=ANFRAGE_A, writer=ProfilWriter(pool, MANDANT_A, paket)))
    _turn(client, "m1", "alles")
    _stilllegen()
    assert _turn(client, "m2", "rest").status_code == 503
    log_vorher = len(store.load("s1").raw_log)
    assert _turn(client, "m3", "nochmal").status_code == 503
    gespeichert = store.load("s1")
    assert len(gespeichert.raw_log) == log_vorher
    assert "m3" not in gespeichert.processed_message_ids
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT focus_step_id, profil_version, status "
                            "FROM bc1.prozessprofil").fetchall() == [
            ("KP-01.TP-1", 1, "in_erhebung")]


def test_fremde_anfrage_fragt_den_writer_nicht(umgebung):
    # Anfrage-Schutz vor dem Gate: Ein Dienst fuer eine andere Anfrage darf den
    # Abschlussstand gar nicht erst lesen (Writer auf nie geoeffnetem Pool: 503).
    _, paket = umgebung
    store = InMemoryStateStore()
    client = TestClient(create_app(
        store, _llm(), paket, company_id=MANDANT_A, anfrage_id=ANFRAGE_A,
        writer=ProfilWriter(ConnectionPool(DSN, open=False), MANDANT_A, paket)))
    assert _turn(client, "m1", "alles").status_code == 503     # fertig, Profil fehlt
    fremd = TestClient(create_app(
        store, _llm(), paket, company_id=MANDANT_A, anfrage_id="A-2026-99",
        writer=ProfilWriter(ConnectionPool(DSN, open=False), MANDANT_A, paket)))
    antwort = _turn(fremd, "m2", "nochmal", anfrage_id="A-2026-99")
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "anfrage_konflikt"
