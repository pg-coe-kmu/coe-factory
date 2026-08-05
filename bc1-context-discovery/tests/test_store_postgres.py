import os

import pytest

from tests.store_contract import StoreVertrag

DSN = os.environ.get("BC1_TEST_DB_DSN")

pytestmark = pytest.mark.skipif(
    not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt (lokales Test-Postgres nötig)"
)


class TestPostgresStore(StoreVertrag):
    @pytest.fixture
    def store(self):
        import psycopg

        from bc1_service.postgres_store import PostgresStateStore

        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS bc1.sessions")
        s = PostgresStateStore(DSN)  # legt Schema + Tabelle neu an
        yield s
        s.close()
