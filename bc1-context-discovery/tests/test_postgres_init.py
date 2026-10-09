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


class _StubCursorOhneTabelle:
    def fetchone(self):
        return ("fehlt",)


class _StubVerbindungOhneTabelle:
    def execute(self, *args, **kwargs):
        return _StubCursorOhneTabelle()


class _StubPoolOhneTabelle(_StubPool):
    @contextmanager
    def connection(self):
        yield _StubVerbindungOhneTabelle()


# Seit B1 legt der Store die Tabelle nicht mehr an. Fehlt sie, soll der Dienst mit
# einem Hinweis auf die Einspiel-Datei stehenbleiben — und den Pool schliessen.
def test_fehlende_tabelle_meldet_die_einspiel_datei_und_schliesst_den_pool(monkeypatch):
    pools: list[_StubPoolOhneTabelle] = []

    def _fabrik(*args, **kwargs) -> _StubPoolOhneTabelle:
        pool = _StubPoolOhneTabelle()
        pools.append(pool)
        return pool

    monkeypatch.setattr(postgres_store, "ConnectionPool", _fabrik)
    with pytest.raises(RuntimeError, match="sessions.sql"):
        postgres_store.PostgresStateStore("postgresql://egal/egal")
    assert pools and pools[0].geschlossen


class _StubCursorOhneRechte:
    def fetchone(self):
        return ("keine_rechte",)


class _StubVerbindungOhneRechte:
    def execute(self, *args, **kwargs):
        return _StubCursorOhneRechte()


class _StubPoolOhneRechte(_StubPool):
    @contextmanager
    def connection(self):
        yield _StubVerbindungOhneRechte()


# Review 13.09., Befund 4: die Tabelle kann existieren, waehrend der DSN-Rolle jedes
# Recht darauf fehlt (to_regclass braucht keine Rechte). Dann darf der Dienst nicht
# starten und erst beim ersten Turn scheitern — Startpruefung mit lesbarer Meldung.
def test_fehlende_rechte_meldet_die_rolle_und_schliesst_den_pool(monkeypatch):
    pools: list[_StubPoolOhneRechte] = []

    def _fabrik(*args, **kwargs) -> _StubPoolOhneRechte:
        pool = _StubPoolOhneRechte()
        pools.append(pool)
        return pool

    monkeypatch.setattr(postgres_store, "ConnectionPool", _fabrik)
    with pytest.raises(RuntimeError, match="Rechte"):
        postgres_store.PostgresStateStore("postgresql://egal/egal")
    assert pools and pools[0].geschlossen


# Fehlt die Pflicht-Variable, soll der Dienst mit einer lesbaren Meldung
# stehenbleiben — nicht mit einem nackten KeyError beim Import.
def test_main_ohne_dsn_meldet_die_fehlende_variable(monkeypatch):
    import importlib

    monkeypatch.delenv("BC1_DB_DSN", raising=False)
    with pytest.raises(RuntimeError, match="BC1_DB_DSN"):
        importlib.import_module("bc1_service.main")


# Fehlt die Mandanten-ID, soll der Dienst ebenso mit einer lesbaren Meldung
# stehenbleiben — sonst liefe der Dienst ohne Mandanten-Bindung an, und jede
# Session würde stillschweigend mandantenlos gespeichert.
def test_main_ohne_company_id_meldet_die_fehlende_variable(monkeypatch):
    import importlib

    monkeypatch.setenv("BC1_DB_DSN", "postgresql://egal/egal")
    monkeypatch.delenv("BC1_COMPANY_ID", raising=False)
    with pytest.raises(RuntimeError, match="BC1_COMPANY_ID"):
        importlib.import_module("bc1_service.main")


# B5: ohne Anfrage gibt es keine Teilprozess-Auswahl — der Dienst bleibt stehen.
def test_main_ohne_anfrage_id_meldet_die_fehlende_variable(monkeypatch):
    import importlib
    import sys

    monkeypatch.setenv("BC1_DB_DSN", "postgresql://egal/egal")
    monkeypatch.setenv("BC1_COMPANY_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.delenv("BC1_ANFRAGE_ID", raising=False)
    monkeypatch.delitem(sys.modules, "bc1_service.main", raising=False)
    with pytest.raises(RuntimeError, match="BC1_ANFRAGE_ID"):
        importlib.import_module("bc1_service.main")


# B4: ohne BC0-Zugang (und ohne bewusstes 'aus') startet der Dienst nicht — und zwar
# bevor eine Datenbankverbindung entsteht (die DSN hier ist absichtlich unerreichbar).
def test_main_ohne_bc0_zugang_meldet_die_fehlenden_variablen(monkeypatch):
    import importlib
    import sys

    monkeypatch.setenv("BC1_DB_DSN", "postgresql://egal/egal")
    monkeypatch.setenv("BC1_COMPANY_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("BC1_ANFRAGE_ID", "A-2026-01")
    for name in ("BC1_BC0_MELDUNGEN", "BC1_BC0_URL", "BC1_BC0_KONTO_EMAIL",
                 "BC1_BC0_KONTO_PASSWORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delitem(sys.modules, "bc1_service.main", raising=False)
    with pytest.raises(RuntimeError, match="BC0-Zugang unvollständig"):
        importlib.import_module("bc1_service.main")
