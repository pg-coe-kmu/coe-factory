"""Wiederverwendbare Vertrags-Suite für StateStore-Implementierungen.

Läuft gegen jede Implementierung (InMemory, Postgres, ...). Subklassen
liefern eine `store`-Fixture mit einer frischen, leeren Instanz.
"""
from __future__ import annotations

import threading

import pytest

from bc1_core.store import StaleStateError
from bc1_core.types import (
    Candidate,
    FieldStatus,
    FieldValue,
    SessionState,
    SessionStatus,
)


def _fetter_state(session_id: str = "s1") -> SessionState:
    # Breiter State: verbreitert beim InMemory-Store das Rennfenster
    # (deepcopy zwischen Versions-Check und Schreiben) und prüft beim
    # Postgres-Store nebenbei den vollen Serialisierungs-Roundtrip —
    # deshalb sind ALLE SessionState-Felder befüllt, nicht nur values.
    st = SessionState(
        session_id=session_id,
        schema_version="0.1",
        paket_name="toy_prozess",
        status=SessionStatus.WARTET,
        rounds=2,
        processed_message_ids={"m0", "m1"},
        raw_log=[("m0", "erste Nachricht"), ("m1", "zweite Nachricht")],
        antworten={"m0": {"status": "frage",
                          "payload": {"naechste_frage": "Wie oft?",
                                      "feld": "feld_0"}}},
    )
    for i in range(300):
        st.values[f"feld_{i}"] = FieldValue(
            value=f"wert_{i}",
            status=FieldStatus.GUELTIG,
            source_message_id="m1",
            candidates=[Candidate(f"alt_{i}", "m0")],
        )
    return st


class StoreVertrag:
    def test_load_unbekannter_session_gibt_none(self, store):
        assert store.load("gibt-es-nicht") is None

    def test_roundtrip_erhaelt_den_zustand(self, store):
        original = _fetter_state()
        store.save(original)
        geladen = store.load("s1")
        assert geladen == original
        assert geladen.version == 1

    def test_save_bumpt_caller_version_um_genau_eins(self, store):
        st = SessionState("s1", "0.1")
        store.save(st)
        assert st.version == 1
        store.save(st)  # ohne Neuladen weiterspeichern muss funktionieren
        assert st.version == 2

    def test_erst_save_mit_version_ungleich_null_wird_abgelehnt(self, store):
        st = SessionState("s1", "0.1", version=3)
        with pytest.raises(StaleStateError):
            store.save(st)
        assert st.version == 3  # Fehlerpfad mutiert den Caller nicht

    def test_stale_write_wird_abgelehnt(self, store):
        st = SessionState("s1", "0.1")
        store.save(st)              # gespeichert: Version 1
        veraltet = store.load("s1")
        store.save(st)              # gespeichert: Version 2
        with pytest.raises(StaleStateError):
            store.save(veraltet)    # Version 1 gegen gespeicherte 2

    def test_vorauseilende_version_wird_abgelehnt(self, store):
        st = SessionState("s1", "0.1")
        store.save(st)
        voraus = store.load("s1")
        voraus.version = 99
        with pytest.raises(StaleStateError):
            store.save(voraus)

    def test_load_liefert_isolierte_kopie(self, store):
        store.save(_fetter_state())
        a = store.load("s1")
        a.values["feld_0"].value = "manipuliert"
        assert store.load("s1").values["feld_0"].value == "wert_0"

    def test_save_isoliert_gegen_spaetere_caller_mutation(self, store):
        st = _fetter_state()
        store.save(st)
        st.values["feld_0"].value = "manipuliert"
        assert store.load("s1").values["feld_0"].value == "wert_0"

    def test_zwei_sessions_bleiben_getrennt(self, store):
        # Der Store ist nach session_id partitioniert: ein Schreibvorgang auf
        # s1 darf s2 weder ueberschreiben noch mit ihm vermischt werden.
        s1 = _fetter_state("s1")
        s2 = _fetter_state("s2")
        s2.rounds = 99
        s2.values["feld_0"].value = "nur_in_s2"
        s2.raw_log = [("mx", "nur in s2")]
        store.save(s1)
        store.save(s2)

        geladen1 = store.load("s1")
        geladen2 = store.load("s2")
        assert geladen1.session_id == "s1" and geladen2.session_id == "s2"
        assert geladen1.rounds == 2 and geladen2.rounds == 99
        assert geladen1.values["feld_0"].value == "wert_0"
        assert geladen2.values["feld_0"].value == "nur_in_s2"
        assert geladen1.raw_log == [("m0", "erste Nachricht"),
                                    ("m1", "zweite Nachricht")]
        assert geladen2.raw_log == [("mx", "nur in s2")]

    def test_nebenlaeufige_saves_genau_einer_gewinnt(self, store):
        # Schließt den einzigen adjudiziert-offenen Gesamt-Review-Punkt
        # (Store-Thread-Sicherheit) an der StateStore-Naht.
        for runde in range(100):
            sid = f"race_{runde}"
            store.save(_fetter_state(sid))  # gespeichert: Version 1
            n = 8
            barriere = threading.Barrier(n)
            # list.append ist unter CPython atomar (GIL) — die Zaehler
            # brauchen daher kein eigenes Lock.
            erfolge: list[int] = []
            fehler: list[int] = []

            def schreiber(i: int) -> None:
                st = store.load(sid)
                st.rounds = i
                barriere.wait()
                try:
                    store.save(st)
                    erfolge.append(i)
                except StaleStateError:
                    fehler.append(i)

            threads = [
                threading.Thread(target=schreiber, args=(i,)) for i in range(n)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert len(erfolge) == 1, f"Runde {runde}: {len(erfolge)} Gewinner"
            assert len(fehler) == n - 1
            assert store.load(sid).version == 2
