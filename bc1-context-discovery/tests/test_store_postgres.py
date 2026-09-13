import pytest

from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung
from tests.store_contract import StoreVertrag, _fetter_state

pytestmark = pytest.mark.skipif(
    not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt (lokales Test-Postgres nötig)"
)

# Wie im Betrieb (EINSPIELEN.md, Abschnitt 6): der Store verbindet als bc1_role.
# Im Container haengt die Rolle als libpq-Option an der DSN — die README-DSN traegt
# keine Query-Parameter, deshalb reicht '?'. Am 13.09. gemessen: psycopg.connect
# und ConnectionPool liefern damit current_user = bc1_role.
ROLLEN_DSN = f"{DSN}?options=-c%20role%3Dbc1_role" if DSN else None


class TestPostgresStore(StoreVertrag):
    @pytest.fixture
    def store(self):
        from bc1_service.postgres_store import PostgresStateStore

        frische_db(DSN)                  # Geruest + prozessprofil.sql + sessions.sql
        s = PostgresStateStore(ROLLEN_DSN)
        yield s
        s.close()

    def test_company_id_steht_typisiert_in_der_spalte(self, store):
        store.save(_fetter_state("s1"))
        with verbindung(DSN) as conn:
            zeile = conn.execute(
                "SELECT company_id::text, version FROM bc1.sessions "
                " WHERE session_id = 's1'").fetchone()
        assert zeile == (MANDANT_A, 1)

    def test_session_ohne_mandant_wird_von_der_datenbank_abgewiesen(self, store):
        # Der Kern setzt company_id beim ersten Turn (core.py); die Datenbank haelt
        # das als NOT NULL fest — keine mandantenlose Sitzung, auch nicht aus Versehen.
        import psycopg

        st = _fetter_state("ohne")
        st.company_id = None
        with pytest.raises(psycopg.errors.NotNullViolation):
            store.save(st)


def test_start_ohne_tabelle_bricht_mit_hinweis_auf_die_einspiel_datei_ab():
    # Echter Fehlpfad am Container, nicht nur der Stub in test_postgres_init.py:
    # Geruest ohne unsere DDL — Schema bc1 existiert, bc1.sessions nicht.
    from bc1_service.postgres_store import PostgresStateStore

    frische_db(DSN, mit_ddl=False)
    with pytest.raises(RuntimeError, match="sessions.sql"):
        PostgresStateStore(ROLLEN_DSN)
