"""Konstruktor-Verhalten des PostgresStateStore — ohne echte Datenbank.

Der Pool wird per Stub eingesetzt (monkeypatch), damit der Fehlerpfad der
Schema-Anlage ohne laufendes Postgres pruefbar ist.
"""
from contextlib import contextmanager

import pytest

from bc1_service import postgres_store


class _StubVerbindung:
    def execute(self, *args, **kwargs):
        raise RuntimeError("Schema-Anlage fehlgeschlagen (z. B. keine Rechte)")


class _StubPool:
    def __init__(self) -> None:
        self.geschlossen = False

    @contextmanager
    def connection(self):
        yield _StubVerbindung()

    def close(self) -> None:
        self.geschlossen = True


# Scheitert die Schema-Anlage, darf der bereits geoeffnete Pool nicht als
# Leiche zurueckbleiben: seine Hintergrund-Threads und Verbindungen wuerden
# sonst bis zum Prozessende weiterlaufen.
def test_pool_wird_bei_init_fehler_geschlossen(monkeypatch):
    pools: list[_StubPool] = []

    def _fabrik(*args, **kwargs) -> _StubPool:
        pool = _StubPool()
        pools.append(pool)
        return pool

    monkeypatch.setattr(postgres_store, "ConnectionPool", _fabrik)
    with pytest.raises(RuntimeError):
        postgres_store.PostgresStateStore("postgresql://egal/egal")
    assert pools and pools[0].geschlossen


# Fehlt die Pflicht-Variable, soll der Dienst mit einer lesbaren Meldung
# stehenbleiben — nicht mit einem nackten KeyError beim Import.
def test_main_ohne_dsn_meldet_die_fehlende_variable(monkeypatch):
    import importlib

    monkeypatch.delenv("BC1_DB_DSN", raising=False)
    with pytest.raises(RuntimeError, match="BC1_DB_DSN"):
        importlib.import_module("bc1_service.main")
