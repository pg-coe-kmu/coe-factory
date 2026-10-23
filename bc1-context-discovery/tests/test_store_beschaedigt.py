"""P4 (#270): eine beschaedigte Zeile in bc1.sessions wird zu KorrupterStateError —
ohne Zeileninhalt in der Meldung (der Zustand traegt den Gespraechsverlauf)."""
import pytest
from psycopg.types.json import Jsonb

from bc1_core.serialize import state_to_dict
from bc1_core.store import KorrupterStateError
from bc1_core.types import SessionState
from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")

# Wie in test_store_postgres.py: der Store verbindet als bc1_role.
ROLLEN_DSN = f"{DSN}?options=-c%20role%3Dbc1_role" if DSN else None


def test_beschaedigte_zeile_wird_zu_korrupter_state_error_ohne_inhalt():
    from bc1_service.postgres_store import PostgresStateStore

    frische_db(DSN)
    with verbindung(DSN) as conn:                   # als Superuser, am Store vorbei
        # company_id im JSON verlangt der CHECK sessions_mandant_konsistent;
        # alles andere, was state_from_dict braucht, fehlt.
        conn.execute(
            "INSERT INTO bc1.sessions (session_id, company_id, version, state) "
            "VALUES (%s, %s, 1, %s)",
            ("kaputt-1", MANDANT_A, Jsonb({"company_id": MANDANT_A, "kaputt": True})))
        conn.commit()
    store = PostgresStateStore(ROLLEN_DSN)
    try:
        with pytest.raises(KorrupterStateError) as fehler:
            store.load("kaputt-1")
    finally:
        store.close()
    assert isinstance(fehler.value.__cause__, KeyError)
    assert str(fehler.value) == ("Sitzung kaputt-1: gespeicherter Zustand ist nicht "
                                 "lesbar (KeyError)")


def test_falsch_geformte_werte_werden_ebenfalls_zu_korrupter_state_error():
    # Review: values als Liste statt Objekt -> AttributeError in state_from_dict.
    # Sonst intakte Zeile — eine unvollstaendige scheitert vorher mit KeyError.
    from bc1_service.postgres_store import PostgresStateStore

    zustand = state_to_dict(SessionState("kaputt-2", "0.1", company_id=MANDANT_A))
    zustand["values"] = []
    frische_db(DSN)
    with verbindung(DSN) as conn:
        conn.execute(
            "INSERT INTO bc1.sessions (session_id, company_id, version, state) "
            "VALUES (%s, %s, 1, %s)",
            ("kaputt-2", MANDANT_A, Jsonb(zustand)))
        conn.commit()
    store = PostgresStateStore(ROLLEN_DSN)
    try:
        with pytest.raises(KorrupterStateError) as fehler:
            store.load("kaputt-2")
    finally:
        store.close()
    assert isinstance(fehler.value.__cause__, AttributeError)
