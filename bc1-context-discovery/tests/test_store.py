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

def test_optimistic_locking_rejects_stale_write():
    store = InMemoryStateStore()
    st = SessionState(session_id="s1", schema_version="0.1")
    store.save(st)              # version 0 -> 1
    stale = store.load("s1")    # version 1
    store.save(store.load("s1"))  # jemand anderes speichert: version 1 -> 2
    with pytest.raises(StaleStateError):
        store.save(stale)       # stale hat version 1, gespeichert ist 2
