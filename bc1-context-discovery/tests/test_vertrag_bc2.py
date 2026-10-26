"""Vertrag BC1 -> BC2: was der Writer einfriert, liest BC2 schemagerecht (#48/#51).

Gelesen wird mit der Leseregel selbst (contracts/bc1-to-bc2/lesen.sql), nicht mit
einer Kopie der Abfrage. Das JSON baut Postgres mit row_to_json: so ist das Beispiel
im Vertrag entstanden (Export vom 12.09.2026), und so nennt es das Schema bei
erstellt_am. Der Vertrag bindet Feldnamen, Einheiten und Nullbarkeit, nicht
Postgres-Typen (README) -- eine eigene Python-Umwandlung waere erfunden.

Geprueft wird wie in bc2-strategic-advisor/tools/validate.py: Draft 2020-12, ohne
Formatpruefung.
"""
import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from psycopg_pool import ConnectionPool

from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_service.discovery_paket import baue_discovery_paket
from bc1_service.profil_writer import ProfilWriter
from bc1_service.start import lade_kontext
from bc1_service.use_case_testprofile import schreibe_testprofile
from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung
from tests.test_use_case_testprofile import ANFRAGEN, _noro_geruest

VERTRAG = Path(__file__).resolve().parents[2] / "contracts" / "bc1-to-bc2"


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


def _anweisungen() -> list[str]:
    """Die Anweisungen aus lesen.sql; Teile, die nur Kommentar sind, fallen weg."""
    teile = re.split(r";\s*\n", (VERTRAG / "lesen.sql").read_text(encoding="utf-8"))
    return [t for t in teile if re.sub(r"--[^\n]*", "", t).strip()]


def _projektionen(pool, focus_step_ids: list[str]) -> list[dict]:
    """Je Profilzeile das Objekt, das das Schema beschreibt, samt seiner Rollen."""
    profile, rollen = _anweisungen()      # genau zwei: Profile, Rollen
    parameter = {"company_id": MANDANT_A, "focus_step_ids": focus_step_ids}
    als_json = "SELECT row_to_json(t) FROM (\n{}\n) t"
    with pool.connection() as conn:
        objekte = [z[0] for z in conn.execute(als_json.format(profile), parameter)]
        rollen_zeilen = [z[0] for z in conn.execute(als_json.format(rollen), parameter)]
    for o in objekte:
        o["rollen"] = [r for r in rollen_zeilen if r["focus_step_id"] == o["focus_step_id"]]
    return objekte


def _fehler(objekt: dict) -> list[str]:
    schema = json.loads((VERTRAG / "prozessprofil.schema.json").read_text(encoding="utf-8"))
    return [f"{'/'.join(map(str, e.path))}: {e.message}"
            for e in Draft202012Validator(schema).iter_errors(objekt)]


def test_testprofile_erfuellen_das_schema_ueber_die_leseregel(pool):
    schreibe_testprofile(pool, MANDANT_A, ANFRAGEN)
    objekte = _projektionen(pool, list(ANFRAGEN))
    assert [o["focus_step_id"] for o in objekte] == sorted(ANFRAGEN)
    for o in objekte:
        assert o["rollen"] == []
        assert _fehler(o) == []


RECHENGROESSEN = ("frequency_per_year", "executions_per_run",
                  "total_duration_minutes", "focus_step_duration_minutes")


def test_fertiges_profil_mit_ungeloesten_rechengroessen_erfuellt_das_schema(pool):
    # README "Was BC1 zusagt": nach zwei Nachfragen wird das Profil trotzdem fertig,
    # die Spalten sind NULL. Der Stand wird gebaut wie in den Writer-Tests -- den
    # Dialog bis zum Limit zu treiben, pruefte den Dialog, nicht das Format.
    anfrage = ANFRAGEN["KP-06.TP-2"]
    with pool.connection() as conn:
        paket = baue_discovery_paket(kontext=lade_kontext(conn, MANDANT_A, anfrage))
    state = SessionState("s-ungeloest", paket.schema_version, paket_name=paket.name,
                         company_id=MANDANT_A, anfrage_id=anfrage)
    state.values["focus_step"] = FieldValue("KP-06.TP-2", FieldStatus.GUELTIG, "m1")
    for feld in RECHENGROESSEN:
        state.values[feld] = FieldValue(None, FieldStatus.UNGELOEST, "m1",
                                        grund="nachfrage_limit_erreicht")
    ProfilWriter(pool, MANDANT_A, paket).reconcile(state, {"status": "fertig", "payload": {}})

    [o] = _projektionen(pool, ["KP-06.TP-2"])
    assert all(o[feld] is None for feld in RECHENGROESSEN)
    assert set(o["profil"]["ungeloeste_felder"]) == set(RECHENGROESSEN)
    assert _fehler(o) == []
