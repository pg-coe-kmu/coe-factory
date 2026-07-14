import pytest
from bc1_core.types import SessionState
from bc1_core.store import InMemoryStateStore, StaleStateError

def test_load_unknown_returns_none():
    assert InMemoryStateStore().load("x") is None

def test_save_then_load_roundtrip_and_isolation():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1")
    store.save(st)
    loaded = store.load("s1")
    assert loaded.session_id == "s1"
    loaded.rounds = 99          # Änderung an der Kopie
    assert store.load("s1").rounds == 0   # darf den Store nicht berühren

def test_save_isoliert_gegen_spaetere_caller_mutation():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1")
    store.save(st)
    st.rounds = 99              # Änderung am Caller-Objekt NACH dem Save
    assert store.load("s1").rounds == 0   # darf den Store nicht berühren

# Vertrag lt. Plan (Task 3, Produces): save erhöht state.version am Caller-
# Objekt — genau um 1, damit der Caller ohne Neuladen weiterspeichern kann.
def test_save_erhoeht_caller_version_um_genau_eins():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1")
    store.save(st)
    assert st.version == 1
    store.save(st)              # direkt wieder speicherbar, kein Neuladen nötig
    assert st.version == 2
    assert store.load("s1").version == 2

def test_optimistic_locking_rejects_stale_write():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1")
    store.save(st)              # version 0 -> 1
    stale = store.load("s1")    # version 1
    store.save(store.load("s1"))  # jemand anderes speichert: version 1 -> 2
    with pytest.raises(StaleStateError):
        store.save(stale)       # stale hat version 1, gespeichert ist 2

def test_optimistic_locking_rejects_version_ahead_write():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1")
    store.save(st)              # gespeichert: version 1
    ahead = store.load("s1")
    ahead.version = 7           # Caller-Bug: Version läuft dem Store voraus
    with pytest.raises(StaleStateError):
        store.save(ahead)

# Ein Erst-Save mit version != 0 kann nur aus einem Caller-Bug stammen
# (Zustandsobjekte leben nie außerhalb des Prozesses, nur session_ids).
def test_erst_save_mit_versionsstand_wird_abgelehnt():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1", version=5)
    with pytest.raises(StaleStateError):
        store.save(st)
