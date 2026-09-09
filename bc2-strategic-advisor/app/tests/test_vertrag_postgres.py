"""
Vertragstest gegen die **echte** gemeinsame Datenbank.

Läuft nicht in der Vorschleife. Nur von Hand, mit gesetztem Flag:

    BC2_ECHTE_DB=1 DATABASE_URL="postgresql://…" python -m pytest tests/test_vertrag_postgres.py -v

**Warum es diesen Test gibt.** Die Trigger-Tests laufen gegen
``SpeicherEingangsbuch``, einen Doppelgänger. Der ahmt die Semantik nach, aber
die **Garantien** gibt nur Postgres:

- Dass ``paket_id`` Primärschlüssel ist und damit die Idempotenz durchsetzt —
  die Entscheidung aus #190 lautet ausdrücklich »die Datenbank setzt sie durch,
  nicht der Code«. Ein grüner Speichertest beweist das nicht.
- Dass BC2 die Rechte hat, die ADR-003 zusagt: lesen auf ``public``, schreiben
  ausschließlich in ``bc2``.
- Dass ``public.v_uebergabe_offen`` die Spalten trägt, die ``_SQL_OFFEN``
  erwartet. Das Schema gehört BC0, nicht BC2 — es kann sich ändern, ohne dass
  jemand BC2 fragt. Genau dafür ist dieser Test da.

Der Test räumt hinter sich auf: er schreibt Pakete mit dem Präfix ``TEST-`` und
löscht sie am Ende wieder.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BC2_ECHTE_DB") != "1",
    reason="Braucht die echte Datenbank. Mit BC2_ECHTE_DB=1 aktivieren.",
)


@pytest.fixture
def buch():
    from eingang import PostgresEingangsbuch

    if not (os.environ.get("DATABASE_URL") or "").strip():
        pytest.fail("BC2_ECHTE_DB=1 gesetzt, aber DATABASE_URL fehlt.")
    return PostgresEingangsbuch()


@pytest.fixture
def test_paket_id() -> str:
    return f"TEST-{uuid.uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
def aufraeumen(request):
    """Löscht am Ende alle in diesem Lauf angelegten TEST-Pakete."""
    yield
    if os.environ.get("BC2_ECHTE_DB") != "1":
        return
    import psycopg2

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM bc2.eingang WHERE paket_id LIKE 'TEST-%'")


def _paket(pid: str):
    from eingang import Paket

    return Paket(
        paket_id=pid,
        company_id="TEST-MANDANT",
        uebergeben_am=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
        nutzlast={"paket_id": pid, "company_id": "TEST-MANDANT", "teilprozesse": ["TP-1"]},
    )


# --------------------------------------------------------------- Die Zusagen


def test_die_datenbank_setzt_die_idempotenz_durch(buch, test_paket_id):
    """Der Kern von #190: nicht der Code entscheidet, sondern der Primaerschluessel."""
    assert buch.eintragen(_paket(test_paket_id)) is True
    assert buch.eintragen(_paket(test_paket_id)) is False


def test_migration_ist_gelaufen(buch):
    """Ohne bc2.eingang laeuft nichts — das soll deutlich scheitern."""
    import psycopg2

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('bc2.eingang')")
        assert cur.fetchone()[0] is not None, (
            "bc2.eingang fehlt. migration_bc2.1_eingang.sql einspielen."
        )


def test_bc2_darf_nur_in_sein_eigenes_schema_schreiben(buch):
    """Gegenprobe zu ADR-003. Schlaegt sie fehl, erst melden, dann weiterarbeiten."""
    import psycopg2

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_user")
        assert cur.fetchone()[0].startswith("bc2_role")

    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
            cur.execute("UPDATE bitkom_bewertungen SET stufe = stufe")


def test_die_view_von_bc0_traegt_noch_die_erwarteten_spalten(buch):
    """Das Schema gehoert BC0. Aendert es sich, faellt es hier auf, nicht im Betrieb."""
    import psycopg2

    erwartet = {
        "paket_id",
        "company_id",
        "uebergeben_am",
        "hinweis",
        "sub_process_id",
        "anfrage_id",
    }
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='v_uebergabe_offen'"
        )
        vorhanden = {z[0] for z in cur.fetchall()}

    fehlend = erwartet - vorhanden
    assert not fehlend, f"v_uebergabe_offen hat sich geaendert, es fehlen: {fehlend}"


def test_abgleich_laeuft_gegen_die_echte_view_durch(buch):
    """Prueft die Abfrage selbst, nicht ihr Ergebnis.

    Wie viele Pakete offen sind, haengt am Datenbestand und ist keine Zusage —
    dass ``_SQL_OFFEN`` gegen das echte Schema uebersetzt und ausfuehrbar ist,
    schon.
    """
    pakete = buch.offene_pakete_von_bc0()
    assert isinstance(pakete, list)
    for p in pakete:
        assert p.paket_id and p.company_id
        assert p.quelle == "nachgeholt"
        assert isinstance(p.nutzlast.get("teilprozesse"), list)
