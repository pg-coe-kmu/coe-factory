"""Anhang A (Rev. 12): die drei Use-Case-Testprofile sind aus dem Repo reproduzierbar."""
import dataclasses

import pytest
from psycopg_pool import ConnectionPool

from bc1_core.store import InMemoryStateStore
from bc1_service.bc0_meldungen import Bc0MeldungFehler
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket
from bc1_service.paket_wahl import waehle_paket
from bc1_service.profil_writer import ProfilWriteError, ProfilWriter
from bc1_service.start import lade_kontext
from bc1_service.use_case_testprofile import (FAELLE, KENNZEICHEN, Vorpruefung,
                                              fuehre_interview, main, pruefe_anfragen,
                                              schreibe_testprofile)
from tests.db_fixture import DSN, MANDANT_A, MANDANT_B, frische_db, verbindung

# Offline reicht der synthetische Fixture-Mandant — die echte Mandantenkennung
# gehoert in den Aufruf der CLI, nicht ins Repo.
KONTEXT = Bc0Kontext(MANDANT_A, (("KP-05.TP-1", "Wissenstransfer"),
                            ("KP-06.TP-1", "Consulting-Matching"),
                            ("KP-06.TP-2", "Reise- und Einsatzplanung")),
                     tuple(f"S-0{i}" for i in range(1, 7)),
                     rollen=(("R-05", "Logistik"),),
                     eigner=(("KP-05", "R-05"), ("KP-06", "R-05")))


def _antworten():
    paket = baue_discovery_paket(kontext=KONTEXT)
    return [(fall, fuehre_interview(InMemoryStateStore(), paket, fall, company_id=MANDANT_A,
                                    anfrage_id=ANFRAGEN[fall.fokus_tp]))
            for fall in FAELLE]


KONTEXT_KP = dataclasses.replace(KONTEXT, prozesse=(("KP-05", "Wissen"), ("KP-06", "Personal")))


def test_jeder_fall_endet_mit_kernprozess_auswahl_fertig_und_b4_gueltig():
    paket = baue_discovery_paket(kontext=KONTEXT_KP)
    for fall in FAELLE:
        antwort = fuehre_interview(InMemoryStateStore(), paket, fall, company_id=MANDANT_A,
                                   anfrage_id=ANFRAGEN[fall.fokus_tp])
        assert antwort["status"] == "fertig", fall.session_id
        assert antwort["payload"]["vollstaendigkeit"] == 1.0, fall.session_id
        assert antwort["payload"]["felder"]["process_id"]["status"] == "gueltig", fall.session_id


def test_jeder_fall_endet_fertig_und_vollstaendig():
    for fall, antwort in _antworten():
        assert antwort["status"] == "fertig", fall.session_id
        assert antwort["payload"]["vollstaendigkeit"] == 1.0, fall.session_id


def test_kennzeichnung_ist_gueltig_und_beginnt_mit_testdaten():
    for fall, antwort in _antworten():
        feld = antwort["payload"]["felder"]["open_remarks"]
        assert feld["status"] == "gueltig", fall.session_id
        assert feld["wert"].startswith("Testdaten"), fall.session_id


def test_kennzeichnung_steht_in_derselben_nachricht_wie_ein_pflichtfeld():
    # Lehre vom 08.09.: mit dem letzten Pflichtfeld wird der Kern terminal —
    # eine Kennzeichnung in einer spaeteren Nachricht bleibt 'fehlt'.
    paket = baue_discovery_paket(kontext=KONTEXT)
    pflicht = {s.name for s in paket.required_fields()}
    for fall in FAELLE:
        traeger = [felder for _, felder in fall.nachrichten
                   if any(name == "open_remarks" for name, _ in felder)]
        assert len(traeger) == 1, fall.session_id
        assert pflicht & {name for name, _ in traeger[0]}, (
            f"{fall.session_id}: open_remarks ohne Pflichtfeld in derselben Nachricht")


def test_fokusschritt_nachricht_nennt_die_kennung_des_fokus():
    # Feste Sperre (a): der KI-Wert fuer focus_step gilt nur, wenn die Nachricht die
    # Kennung nennt — das Skript spielt eine Person, die sie nennt.
    for fall in FAELLE:
        traeger = [text for text, felder in fall.nachrichten
                   if any(name == "focus_step" for name, _ in felder)]
        assert len(traeger) == 1, fall.session_id
        assert fall.fokus_tp in traeger[0], fall.session_id


def test_version_3_werte():
    assert "Version 3" in KENNZEICHEN
    for fall in FAELLE:
        werte = {name: wert for _, felder in fall.nachrichten for name, wert in felder}
        assert werte["executions_per_run"] == "1", fall.session_id
        assert fall.session_id.endswith("-v3"), fall.session_id
        assert "Version 3" in werte["open_remarks"], fall.session_id


def test_fokus_tp_stimmt_mit_dem_skript_ueberein():
    # fokus_tp ist Metadatum UND steht als focus_step im Skript — beides muss zusammenpassen.
    for fall in FAELLE:
        werte = {name: wert for _, felder in fall.nachrichten for name, wert in felder}
        assert werte["focus_step"] == fall.fokus_tp, fall.session_id


# --- gegen die Datenbank: Gerüst kennt nur KP-01/KP-02, die drei Fokus-TPs kommen hier dazu

def _noro_geruest(conn) -> None:
    conn.execute(
        "INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) VALUES "
        "(%s, 'KP-05', 'Wissen', 'Kerngeschäftsprozess'), "
        "(%s, 'KP-06', 'Personal', 'Unterstützungsprozess')", (MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO ref_teilprozesse "
        "(company_id, sub_process_id, process_id, step_no, sub_process_name) VALUES "
        "(%s, 'KP-05.TP-1', 'KP-05', 1, 'Wissenstransfer'), "
        "(%s, 'KP-06.TP-1', 'KP-06', 1, 'Consulting-Matching'), "
        "(%s, 'KP-06.TP-2', 'KP-06', 2, 'Reise- und Einsatzplanung')",
        (MANDANT_A, MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO mandant_systeme (company_id, system_id, bezeichnung) VALUES "
        "(%s, 'S-03', 'Wiki'), (%s, 'S-04', 'Ablage'), (%s, 'S-05', 'CRM'), (%s, 'S-06', 'Skills')",
        (MANDANT_A, MANDANT_A, MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO bitkom_bewertungen "
        "(company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg, bewertet_am) VALUES "
        "(%s, 'E-2026-01', 'KP-05.TP-1.I-01', 'KP-05.TP-1', 1, 3, 'Testdaten', '2026-01-15'), "
        "(%s, 'E-2026-01', 'KP-06.TP-1.I-01', 'KP-06.TP-1', 1, 2, 'Testdaten', '2026-01-15'), "
        "(%s, 'E-2026-01', 'KP-06.TP-2.I-01', 'KP-06.TP-2', 1, 2, 'Testdaten', '2026-01-15')",
        (MANDANT_A, MANDANT_A, MANDANT_A))
    # C1a: B3 ist eine Auswahl der aktiven Rollen; R-05 ist die Rolle, die die
    # Skripte nennen, Person P-05 ist Eigner beider Kernprozesse.
    conn.execute(
        "INSERT INTO mandant_rollen (company_id, rolle_id, bezeichnung, klasse) "
        "VALUES (%s, 'R-05', 'Logistik', 'K2')", (MANDANT_A,))
    conn.execute(
        "INSERT INTO ref_personen (company_id, person_id, funktion, rolle_id) "
        "VALUES (%s, 'P-05', 'Logistikleitung', 'R-05')", (MANDANT_A,))
    conn.execute(
        "INSERT INTO prozess_personen (company_id, process_id, person_id, funktion) VALUES "
        "(%s, 'KP-05', 'P-05', 'eigner'), (%s, 'KP-06', 'P-05', 'eigner')",
        (MANDANT_A, MANDANT_A))
    # B5: der Start haengt an der Anfrage. Die Basis-Anfragen von Mandant A (aus dem
    # Geruest) tragen dieselben IDs A-2026-01..03 wie die Faelle — erst raeumen.
    # (anfrage_prozesse faellt per ON DELETE CASCADE mit.)
    conn.execute("DELETE FROM ref_anfragen WHERE company_id = %s", (MANDANT_A,))
    for fall in FAELLE:
        kp = fall.fokus_tp.split(".")[0]
        conn.execute(
            "INSERT INTO ref_anfragen (company_id, anfrage_id, eingang_am, process_id, "
            "sub_process_id, zuordnung_quelle, status) "
            "VALUES (%s, %s, '2026-09-01', %s, %s, 'anfrage', 'zugeordnet')",
            (MANDANT_A, ANFRAGEN[fall.fokus_tp], kp, fall.fokus_tp))
        conn.execute(
            "INSERT INTO anfrage_prozesse (company_id, anfrage_id, process_id, "
            "sub_process_id, rolle, zuordnung_quelle) "
            "VALUES (%s, %s, %s, %s, 'haupt', 'anfrage')",
            (MANDANT_A, ANFRAGEN[fall.fokus_tp], kp, fall.fokus_tp))


@pytest.fixture
def pool():
    if not DSN:
        pytest.skip("BC1_TEST_DB_DSN nicht gesetzt — DB-Tests uebersprungen")
    frische_db(DSN)
    with verbindung(DSN, rolle=None) as conn:
        _noro_geruest(conn)
    p = ConnectionPool(DSN, min_size=1, max_size=4, open=True,
                       kwargs={"options": "-c role=bc1_role"})
    yield p
    p.close()


def _zeilen(sql):
    with verbindung(DSN) as conn:
        return conn.execute(sql).fetchall()


# Seit Version 3 kommen die Anfragen als Parameter (--anfrage TP=A-JJJJ-NN); das
# Geruest legt diese drei Anfragen an.
ANFRAGEN = {"KP-06.TP-2": "A-2026-01", "KP-05.TP-1": "A-2026-02", "KP-06.TP-1": "A-2026-03"}


def test_fehlende_anfrage_wird_gemeldet(pool):
    ohne = {tp: a for tp, a in ANFRAGEN.items() if tp != "KP-05.TP-1"}
    with pytest.raises(RuntimeError) as fehler:
        schreibe_testprofile(pool, MANDANT_A, ohne)
    assert "Für KP-05.TP-1 fehlt --anfrage KP-05.TP-1=A-JJJJ-NN." in str(fehler.value)
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(0,)]


class _Melder:
    """Ersatz-Melder: zeichnet die Aufrufe auf."""

    def __init__(self, scheitern=()):
        self.aufrufe = []
        self.scheitern = set(scheitern)

    def pruefe_konto(self):
        self.aufrufe.append(("pruefe_konto",))

    def melde_interview_laeuft(self, anfrage_id):
        self.aufrufe.append(("laeuft", anfrage_id))

    def ziehe_gate_nach(self, anfrage_id):
        # Was BC0 taete: das Gate sieht nur Profile, die in der DB schon fertig sind.
        status = _zeilen("SELECT status FROM bc1.prozessprofil "
                         f"WHERE anfrage_id = '{anfrage_id}'")
        self.aufrufe.append(("gate", anfrage_id, status))
        if anfrage_id in self.scheitern:
            raise Bc0MeldungFehler("BC0 nicht erreichbar")
        with verbindung(DSN, rolle=None) as conn:      # wie BC0: Anfrage steht am Gate
            conn.execute("UPDATE ref_anfragen SET status = 'am_gate' "
                         "WHERE company_id = %s AND anfrage_id = %s", (MANDANT_A, anfrage_id))
        return [anfrage_id]


def test_melder_reihenfolge(pool):
    melder = _Melder()
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN, melder)
    assert melder.aufrufe == [
        ("pruefe_konto",),
        ("laeuft", "A-2026-01"), ("laeuft", "A-2026-02"), ("laeuft", "A-2026-03"),
        ("gate", "A-2026-01", [("fertig",)]), ("gate", "A-2026-02", [("fertig",)]),
        ("gate", "A-2026-03", [("fertig",)])]


def test_kontofehler_bricht_vor_dem_schreiben_ab(pool):
    # (Regression) Spec §7: ein Fehler beim Melden bricht vor dem Schreiben ab.
    class _KeinKonto(_Melder):
        def pruefe_konto(self):
            super().pruefe_konto()
            raise Bc0MeldungFehler("Konto nicht erreichbar")

    melder = _KeinKonto()
    with pytest.raises(Bc0MeldungFehler):
        schreibe_testprofile(pool, MANDANT_A, ANFRAGEN, melder)
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(0,)]
    assert melder.aufrufe == [("pruefe_konto",)]


def test_meldefehler_bricht_vor_dem_schreiben_ab(pool):
    # (Regression) Der erste Interview-Beginn scheitert: nichts geschrieben, kein Gate.
    class _KeinBeginn(_Melder):
        def melde_interview_laeuft(self, anfrage_id):
            super().melde_interview_laeuft(anfrage_id)
            raise Bc0MeldungFehler("BC0 nicht erreichbar")

    melder = _KeinBeginn()
    with pytest.raises(Bc0MeldungFehler):
        schreibe_testprofile(pool, MANDANT_A, ANFRAGEN, melder)
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(0,)]
    assert [a[0] for a in melder.aufrufe] == ["pruefe_konto", "laeuft"]


def test_erst_pruefen_dann_schreiben(pool):
    with verbindung(DSN, rolle=None) as conn:
        conn.execute("UPDATE ref_anfragen SET status = 'eingegangen' "
                     "WHERE company_id = %s AND anfrage_id = 'A-2026-02'", (MANDANT_A,))
    melder = _Melder()
    with pytest.raises(RuntimeError) as fehler:
        schreibe_testprofile(pool, MANDANT_A, ANFRAGEN, melder)
    assert "A-2026-02" in str(fehler.value)
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(0,)]
    assert melder.aufrufe == []


def test_falsch_zugeordnete_anfrage_wird_vor_dem_schreiben_erkannt(pool):
    # A-2026-01 ist interviewbar, umfasst aber nur KP-06.TP-2.
    falsch = {**ANFRAGEN, "KP-05.TP-1": "A-2026-01"}
    melder = _Melder()
    with pytest.raises(RuntimeError) as fehler:
        schreibe_testprofile(pool, MANDANT_A, falsch, melder)
    assert "Die Anfrage A-2026-01 umfasst KP-05.TP-1 nicht." in str(fehler.value)
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(0,)]
    assert melder.aufrufe == []


def test_inaktive_eigner_rolle_wird_vor_dem_schreiben_erkannt(pool):
    # R-05 ist die Rolle, die alle drei Skripte fuer B3 waehlen. Ist sie beim Mandanten
    # stillgelegt (R-01/R-02 bleiben aktiv), scheiterte B3 sonst erst nach dem Einfrieren.
    with verbindung(DSN, rolle=None) as conn:
        conn.execute("UPDATE mandant_rollen SET aktiv = false "
                     "WHERE company_id = %s AND rolle_id = 'R-05'", (MANDANT_A,))
    melder = _Melder()
    with pytest.raises(RuntimeError) as fehler:
        schreibe_testprofile(pool, MANDANT_A, ANFRAGEN, melder)
    assert "R-05" in str(fehler.value)
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(0,)]
    assert melder.aufrufe == []


def test_andere_anfrage_fuer_geschriebenen_fall_wird_abgelehnt(pool):
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    with verbindung(DSN, rolle=None) as conn:
        conn.execute(
            "INSERT INTO ref_anfragen (company_id, anfrage_id, eingang_am, process_id, "
            "sub_process_id, zuordnung_quelle, status) "
            "VALUES (%s, 'A-2026-04', '2026-09-02', 'KP-05', 'KP-05.TP-1', 'anfrage', "
            "'zugeordnet')", (MANDANT_A,))
        conn.execute(
            "INSERT INTO anfrage_prozesse (company_id, anfrage_id, process_id, "
            "sub_process_id, rolle, zuordnung_quelle) "
            "VALUES (%s, 'A-2026-04', 'KP-05', 'KP-05.TP-1', 'haupt', 'anfrage')",
            (MANDANT_A,))
    with pytest.raises(RuntimeError) as fehler:
        schreibe_testprofile(pool, MANDANT_A, {**ANFRAGEN, "KP-05.TP-1": "A-2026-04"})
    assert ("uc2-wissensbasis-testdaten-v3 ist schon zu A-2026-02 geschrieben; "
            "für A-2026-04 braucht es eine neue Sitzungsnummer.") in str(fehler.value)
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(3,)]


def test_fremder_gate_fehler_wird_nur_mit_klassennamen_gemeldet(pool, capsys):
    # Wie _gate_im_hintergrund: nur Bc0MeldungFehler traegt eine eigene Meldung,
    # jede andere Ausnahme nennt nur ihre Klasse (kein Geheimnis in der Ausgabe).
    class _Unfall(_Melder):
        def ziehe_gate_nach(self, anfrage_id):
            raise ValueError("geheim-token")

    ergebnis = schreibe_testprofile(pool, MANDANT_A, ANFRAGEN, _Unfall())
    assert [e["status"] for e in ergebnis] == ["fertig"] * 3
    fehlerausgabe = capsys.readouterr().err
    assert "ValueError" in fehlerausgabe
    assert "geheim-token" not in fehlerausgabe


def test_ohne_melder_wird_nichts_gemeldet(pool):
    ergebnis = schreibe_testprofile(pool, MANDANT_A, ANFRAGEN, melder=None)
    assert [e["status"] for e in ergebnis] == ["fertig"] * 3
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE status = 'fertig'") == [(3,)]


def test_vorpruefung_bereit(pool):
    assert pruefe_anfragen(pool, MANDANT_A, ANFRAGEN) == Vorpruefung((), frozenset())


def test_schreibe_legt_drei_fertige_gekennzeichnete_zeilen_an(pool):
    ergebnis = schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    assert [e["status"] for e in ergebnis] == ["fertig"] * 3
    zeilen = _zeilen("SELECT focus_step_id, status, erhebung_id "
                     "FROM bc1.prozessprofil ORDER BY 1")
    assert zeilen == [("KP-05.TP-1", "fertig", "E-2026-01"),
                      ("KP-06.TP-1", "fertig", "E-2026-01"),
                      ("KP-06.TP-2", "fertig", "E-2026-01")]
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE profil->'felder'->'open_remarks'->>'wert' LIKE 'Testdaten%'") == [(3,)]


def test_testprofile_tragen_ihre_anfrage(pool):
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    with verbindung(DSN) as conn:
        zeilen = dict(conn.execute(
            "SELECT focus_step_id, anfrage_id FROM bc1.prozessprofil "
            "WHERE company_id = %s", (MANDANT_A,)).fetchall())
    assert zeilen == ANFRAGEN


# Unabhaengige Erwartung (NICHT aus FAELLE abgeleitet): die Spaltenwerte der
# Version 3. Frequenzen und Dauern wie am 08.09.2026 gemessen, Menge je Durchlauf 1.
# Aendert jemand einen Rohwert im Modul, sagt dieser Test es.
SPALTEN_V3 = {
    #  focus_step_id : (haeufigkeit, menge, dauer_ges, dauer_fokus, guete, herkunft)
    "KP-05.TP-1": (260, 1, 45, 25, 50, "geschaetzt"),
    "KP-06.TP-1": (40, 1, 120, 60, 70, "geschaetzt"),
    "KP-06.TP-2": (180, 1, 180, 90, 60, "geschaetzt"),
}
KENNZEICHEN_V3 = ("Testdaten Use-Case-Definition 24.08., nicht erhoben, Version 3. "
                  "Quelle: Projektgruppe CoE-Factory.")


def test_gespeicherte_spalten_und_kennzeichnung_sind_die_werte_von_version_3(pool):
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    zeilen = _zeilen(
        "SELECT focus_step_id, frequency_per_year, executions_per_run, "
        "       total_duration_minutes, focus_step_duration_minutes, "
        "       focus_step_duration_confidence_pct, focus_step_duration_source, "
        "       profil->'felder'->'open_remarks'->>'wert' "
        "FROM bc1.prozessprofil ORDER BY 1")
    assert {z[0]: tuple(z[1:7]) for z in zeilen} == SPALTEN_V3
    assert {z[7] for z in zeilen} == {KENNZEICHEN_V3}


def test_testprofile_tragen_die_eigner_rolle_ohne_abweichung(pool):
    # Das Geruest macht R-05 zum BC0-Eigner von KP-05 und KP-06; die Faelle waehlen
    # R-05. Spalte gesetzt, kein Befund — sonst triggert jeder Testlauf die Warnung.
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    zeilen = _zeilen("SELECT focus_step_id, process_owner_rolle_id, profil->'befunde' "
                     "FROM bc1.prozessprofil ORDER BY 1")
    assert len(zeilen) == 3
    for _, rolle, befunde in zeilen:
        assert rolle == "R-05"
        assert "eigner_rolle_abweichung" not in befunde


def test_zweiter_lauf_erzeugt_keine_zweite_version(pool):
    # Kriterium 4: dieselben session_id/message_id -> keine neue Version, kein offener
    # Draft. Traeger ist die Vorpruefung: ein schon fertig zur selben Anfrage gebundener
    # Fall gilt als erledigt und erreicht den Writer nicht noch einmal (der Store ist je
    # Lauf frisch, die Replay-Weiche des Kerns greift hier nicht).
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    assert _zeilen("SELECT focus_step_id, count(*) FROM bc1.prozessprofil "
                   "GROUP BY 1 ORDER BY 1") == [("KP-05.TP-1", 1), ("KP-06.TP-1", 1),
                                                ("KP-06.TP-2", 1)]
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE status = 'in_erhebung'") == [(0,)]


def test_neue_session_id_erzeugt_version_2(pool, monkeypatch):
    # Kriterium 4, zweite Haelfte: 'fertig' ist final — der einzige Korrekturweg
    # ist ein Lauf mit NEUER session_id, der eine neue Version anlegt.
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    neu = tuple(dataclasses.replace(f, session_id=f.session_id + "-v3") for f in FAELLE)
    monkeypatch.setattr("bc1_service.use_case_testprofile.FAELLE", neu)
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    assert _zeilen("SELECT focus_step_id, profil_version, status FROM bc1.prozessprofil "
                   "ORDER BY 1, 2") == [
        ("KP-05.TP-1", 1, "fertig"), ("KP-05.TP-1", 2, "fertig"),
        ("KP-06.TP-1", 1, "fertig"), ("KP-06.TP-1", 2, "fertig"),
        ("KP-06.TP-2", 1, "fertig"), ("KP-06.TP-2", 2, "fertig")]


def test_wiederholung_meldet_den_gespeicherten_stand_nicht_den_neuen_kern(pool):
    # Wie api.py: liefert der Writer das gespeicherte (eingefrorene) Profil, gilt
    # DAS — nicht, was der Kern in diesem Lauf frisch extrahiert hat.
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    with pool.connection() as conn:
        kontext = lade_kontext(conn, MANDANT_A, ANFRAGEN[FAELLE[0].fokus_tp])
    paket = baue_discovery_paket(kontext=kontext)
    fall = FAELLE[0]
    nachrichten = tuple(
        (text, tuple(("focus_step_duration_minutes", "900 Minuten")
                     if name == "focus_step_duration_minutes" else (name, wert)
                     for name, wert in felder))
        for text, felder in fall.nachrichten)
    antwort = fuehre_interview(InMemoryStateStore(), paket,
                               dataclasses.replace(fall, nachrichten=nachrichten),
                               company_id=MANDANT_A, anfrage_id=ANFRAGEN[fall.fokus_tp],
                               writer=ProfilWriter(pool, MANDANT_A, paket))
    assert antwort["payload"]["felder"]["focus_step_duration_minutes"]["wert"] == "90"


# --- CLI-Einstieg: ohne --echt wird nichts geschrieben

def _darf_nicht_schreiben(*_a, **_k):
    raise AssertionError("Trockenlauf darf schreibe_testprofile nicht aufrufen")


def test_main_ohne_echt_schreibt_nicht(monkeypatch, capsys):
    monkeypatch.setenv("BC1_DB_DSN", "postgresql://unbenutzt")
    monkeypatch.setattr("bc1_service.use_case_testprofile.schreibe_testprofile",
                        _darf_nicht_schreiben)
    assert main(["--company-id", MANDANT_A]) == 0
    assert "TROCKENLAUF" in capsys.readouterr().out


ANFRAGE_ARGS = [arg for tp, a in ANFRAGEN.items() for arg in ("--anfrage", f"{tp}={a}")]


def test_main_ohne_echt_erzeugt_keinen_melder(monkeypatch, capsys):
    def _darf_nicht_bauen(*_a, **_k):
        raise AssertionError("Trockenlauf darf keinen Melder bauen")

    monkeypatch.setattr("bc1_service.use_case_testprofile.baue_melder", _darf_nicht_bauen)
    assert main(["--company-id", MANDANT_A, *ANFRAGE_ARGS]) == 0
    assert "TROCKENLAUF" in capsys.readouterr().out


def test_main_anfrage_ohne_gleichheitszeichen_bricht_sauber_ab(capsys):
    with pytest.raises(SystemExit) as ende:
        main(["--company-id", MANDANT_A, "--anfrage", "A-2026-01"])
    assert ende.value.code == 2
    assert "TP=A-JJJJ-NN" in capsys.readouterr().err


def test_main_echt_schreibt_drei_faelle_und_meldet_ok(pool, monkeypatch, capsys):
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_BC0_MELDUNGEN", "aus")
    assert main(["--company-id", MANDANT_A, "--echt", *ANFRAGE_ARGS]) == 0
    assert capsys.readouterr().out.count("OK ") == 3
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE status = 'fertig'") == [(3,)]


def test_main_echt_ohne_dsn_bricht_mit_klarer_meldung_ab(monkeypatch, capsys):
    monkeypatch.delenv("BC1_DB_DSN", raising=False)
    assert main(["--company-id", MANDANT_A, "--echt"]) == 1
    assert "BC1_DB_DSN" in capsys.readouterr().err


def test_main_gibt_fremde_ausnahmen_ohne_detail_aus(pool, monkeypatch, capsys):
    # ProfilWriteError traegt die DB-Ausnahme samt DETAIL (Profilinhalt) im Text:
    # ausgegeben werden nur Klasse und erste Zeile, kein Traceback.
    def _scheitert(*_a, **_k):
        raise ProfilWriteError("Profil-Write im Terminal-Turn fehlgeschlagen: FEHLER x\n"
                               "DETAIL: Failing row contains (geheim)")

    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_BC0_MELDUNGEN", "aus")
    monkeypatch.setattr("bc1_service.use_case_testprofile.schreibe_testprofile", _scheitert)
    assert main(["--company-id", MANDANT_A, "--echt", *ANFRAGE_ARGS]) == 1
    fehlerausgabe = capsys.readouterr().err
    assert "ProfilWriteError" in fehlerausgabe
    assert "Profil-Write im Terminal-Turn fehlgeschlagen: FEHLER x" in fehlerausgabe
    assert "geheim" not in fehlerausgabe
    assert "Traceback" not in fehlerausgabe


def test_main_gibt_alle_vorpruefungsmeldungen_vollstaendig_aus(pool, monkeypatch, capsys):
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_BC0_MELDUNGEN", "aus")
    assert main(["--company-id", MANDANT_A, "--echt",
                 "--anfrage", "KP-06.TP-2=A-2026-01"]) == 1
    fehlerausgabe = capsys.readouterr().err
    assert "Für KP-05.TP-1 fehlt --anfrage KP-05.TP-1=A-JJJJ-NN." in fehlerausgabe
    assert "Für KP-06.TP-1 fehlt --anfrage KP-06.TP-1=A-JJJJ-NN." in fehlerausgabe
    assert "RuntimeError" not in fehlerausgabe


def test_zweiter_lauf_holt_gescheitertes_gate_nach(pool, monkeypatch, capsys):
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_BC0_MELDUNGEN", "aus")
    args = ["--company-id", MANDANT_A, "--echt", *ANFRAGE_ARGS]
    erster = _Melder(scheitern={"A-2026-02"})
    monkeypatch.setattr("bc1_service.use_case_testprofile.baue_melder",
                        lambda umgebung, company_id: erster)
    assert main(args) == 0
    assert "A-2026-02" in capsys.readouterr().err

    zweiter = _Melder()
    monkeypatch.setattr("bc1_service.use_case_testprofile.baue_melder",
                        lambda umgebung, company_id: zweiter)
    assert main(args) == 0
    assert capsys.readouterr().out.count("bereits geschrieben") == 3
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(3,)]
    assert [a[:2] for a in zweiter.aufrufe if a[0] == "laeuft"] == []
    assert [a[1] for a in zweiter.aufrufe if a[0] == "gate"] == [
        "A-2026-01", "A-2026-02", "A-2026-03"]


def test_main_echt_ohne_bereite_anfrage_exit_1_ohne_traceback(pool, monkeypatch, capsys):
    # Mandant B hat zwar A-2026-01 (dieselbe ID wie A), aber nicht deren Teilprozesse:
    # die Pruefung meldet es auf stderr, statt halbe Profile zu schreiben.
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_BC0_MELDUNGEN", "aus")
    assert main(["--company-id", MANDANT_B, "--echt", *ANFRAGE_ARGS]) == 1
    assert "A-2026-01" in capsys.readouterr().err
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil") == [(0,)]


def test_main_echt_meldet_fehler_wenn_ein_fall_nicht_fertig_wird(pool, monkeypatch, capsys):
    # Mandant B scheitert schon in der Vorpruefung (seine Anfrage hat die Fokus-TPs nicht,
    # s. test_main_echt_ohne_bereite_anfrage_exit_1_ohne_traceback). Den FEHLER-Pfad
    # erreicht man mit einem Fall, dessen Interview nach der zweiten Nachricht endet: nicht fertig ->
    # Exit 1, FEHLER-Zeile, und der Writer hat nichts eingefroren.
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_BC0_MELDUNGEN", "aus")
    abgebrochen = dataclasses.replace(FAELLE[0], nachrichten=FAELLE[0].nachrichten[:2])
    monkeypatch.setattr("bc1_service.use_case_testprofile.FAELLE", (abgebrochen,))
    assert main(["--company-id", MANDANT_A, "--echt", *ANFRAGE_ARGS]) == 1
    assert capsys.readouterr().out.count("FEHLER") == 1
    assert _zeilen("SELECT count(*) FROM bc1.prozessprofil "
                   "WHERE status = 'fertig'") == [(0,)]


def test_werkzeug_schreibt_mit_derselben_paketkennung_wie_der_dienst(pool):
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    for fall in FAELLE:
        with pool.connection() as conn:
            kontext = lade_kontext(conn, MANDANT_A, ANFRAGEN[fall.fokus_tp])
        assert kontext.prozesse                               # Liste kommt aus der DB
        dienst = waehle_paket({}, kontext=kontext)            # Weg des Dienstes
        with verbindung(DSN) as conn:
            zeile = conn.execute(
                "SELECT paket_version, profil->'felder'->'process_id'->>'status', "
                "       profil->'befunde' ? 'kp_tp_diskrepanz' "
                "  FROM bc1.prozessprofil WHERE focus_step_id = %s",
                (fall.fokus_tp,)).fetchall()
        assert zeile == [(dienst.schema_version, "gueltig", False)]
