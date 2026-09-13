"""Signatur-Generator: reine Teile ohne Datenbank, Gesamtlauf gegen den Container."""
import os
import re
from pathlib import Path

import pytest

from tests.db.signatur_erzeugen import baue_block, main, zeilen_aus_fehlertext

DSN = os.environ.get("BC1_TEST_DB_DSN")
_PROJEKT = Path(__file__).parents[1]
_DDL = _PROJEKT / "bc1_service" / "db" / "prozessprofil.sql"
PLATZHALTER_BLOCK = "    ('platzhalter|wird|in|step7|ersetzt');\n"

FEHLERTEXT = """\
psycopg.errors.RaiseException: Nachpruefung fehlgeschlagen — Rollback.
  - fehlt:  platzhalter|wird|in|step7|ersetzt
  + zuviel: acl|sessions|bc1_role|SELECT|f
  + zuviel: spalte|sessions|session_id|text|notnull||-|-
CONTEXT:  PL/pgSQL function inline_code_block line 17 at RAISE
"""


def test_zeilen_aus_fehlertext_trennt_zuviel_und_fehlt():
    zeilen, fehlt = zeilen_aus_fehlertext(FEHLERTEXT)
    assert zeilen == ["acl|sessions|bc1_role|SELECT|f",
                      "spalte|sessions|session_id|text|notnull||-|-"]
    assert fehlt == ["platzhalter|wird|in|step7|ersetzt"]


def test_baue_block_sortiert_verdoppelt_hochkommas_und_schliesst_mit_semikolon():
    # Unsortierte Eingabe, ein CHECK-Ausdruck mit Hochkomma (muss als '' in die DDL).
    block = baue_block(["spalte|s|b|text|null||-|-",
                        "constraint|s|c|CHECK ((x = 'ja'::text))"])
    assert block == (
        "    ('constraint|s|c|CHECK ((x = ''ja''::text))'),\n"
        "    ('spalte|s|b|text|null||-|-');")


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_main_reproduziert_die_committete_sollsignatur_byteidentisch(tmp_path, monkeypatch):
    # Regressionsanker: aus der committeten prozessprofil.sql mit Platzhalter statt
    # Signaturblock muss der Generator GENAU die committete Datei erzeugen. Weicht
    # etwas ab, ist der Generator kaputt — oder die Signatur stimmt nicht mehr zum
    # Container (dann sagt der Diff, was).
    original = _DDL.read_text(encoding="utf-8")
    mit_platzhalter = re.sub(
        r"(-- << HIER die generierte Sollsignatur einsetzen \(Step 7\) >>\n)(?:    \('.*\n)+",
        lambda m: m.group(1) + PLATZHALTER_BLOCK, original, count=1)
    assert mit_platzhalter != original
    kopie = tmp_path / "prozessprofil.sql"
    kopie.write_text(mit_platzhalter, encoding="utf-8")
    monkeypatch.chdir(_PROJEKT)              # main() importiert tests.db_fixture ueber cwd
    assert main(["signatur_erzeugen.py", str(kopie)]) == 0
    assert kopie.read_text(encoding="utf-8") == original


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_main_bricht_ohne_platzhalter_ab_und_laesst_die_datei_in_ruhe(tmp_path, monkeypatch):
    # Die committete Datei traegt ihre echte Signatur — ohne Platzhalter darf der
    # Generator nichts schreiben, sondern muss sagen, was vorher zu tun ist.
    kopie = tmp_path / "prozessprofil.sql"
    kopie.write_text(_DDL.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(_PROJEKT)
    with pytest.raises(SystemExit, match="Platzhalterzeile fehlt"):
        main(["signatur_erzeugen.py", str(kopie)])
    assert kopie.read_text(encoding="utf-8") == _DDL.read_text(encoding="utf-8")


def _kopie_mit_platzhalter(tmp_path) -> Path:
    original = _DDL.read_text(encoding="utf-8")
    mit_platzhalter = re.sub(
        r"(-- << HIER die generierte Sollsignatur einsetzen \(Step 7\) >>\n)(?:    \('.*\n)+",
        lambda m: m.group(1) + PLATZHALTER_BLOCK, original, count=1)
    kopie = tmp_path / "prozessprofil.sql"
    kopie.write_text(mit_platzhalter, encoding="utf-8")
    return kopie


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_main_bricht_bei_fremder_cluster_rolle_ab(tmp_path, monkeypatch):
    # Rollen ueberleben frische_db(). Eine stehengebliebene Proberolle landete am
    # 03.09. ungefragt in der Sollsignatur — deshalb vorher pruefen, nicht hinterher.
    import psycopg

    kopie = _kopie_mit_platzhalter(tmp_path)
    monkeypatch.chdir(_PROJEKT)
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("CREATE ROLE probe_fremd NOLOGIN")
    try:
        with pytest.raises(SystemExit, match="erwarteten Rollen"):
            main(["signatur_erzeugen.py", str(kopie)])
    finally:
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("DROP ROLE probe_fremd")
    assert PLATZHALTER_BLOCK in kopie.read_text(encoding="utf-8")   # nichts geschrieben


def _kunstdatei(tmp_path, fehlertext: str) -> Path:
    # Eine Einspiel-Datei, die den Platzhalter (im Kommentar) traegt und beim
    # Einspielen genau den gewuenschten Nachpruefungs-Fehler wirft.
    datei = tmp_path / "kunst.sql"
    datei.write_text(
        "-- " + PLATZHALTER_BLOCK
        + "DO $$ BEGIN RAISE EXCEPTION E'Nachpruefung fehlgeschlagen — Rollback.\\n"
        + fehlertext + "'; END $$;\n", encoding="utf-8")
    return datei


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_main_bricht_bei_unbekannter_signaturart_ab(tmp_path, monkeypatch):
    # Taucht eine Signaturart auf, die der Generator nicht kennt, ist die Ist-Sicht
    # der DDL gewachsen — das darf nicht still in die Sollsignatur wandern.
    datei = _kunstdatei(tmp_path, "  - fehlt:  platzhalter|wird|in|step7|ersetzt\\n"
                                  "  + zuviel: fremdart|x")
    monkeypatch.chdir(_PROJEKT)
    with pytest.raises(SystemExit, match="Unbekannte Signaturart"):
        main(["signatur_erzeugen.py", str(datei)])


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_main_bricht_ab_wenn_mehr_als_der_platzhalter_fehlt(tmp_path, monkeypatch):
    # Fehlt der Nachpruefung mehr als die Platzhalterzeile, stimmt etwas am Aufbau
    # der Datei — dann darf kein Block geschrieben werden.
    datei = _kunstdatei(tmp_path, "  - fehlt:  platzhalter|wird|in|step7|ersetzt\\n"
                                  "  - fehlt:  spalte|sessions|x|text|null||-|-\\n"
                                  "  + zuviel: spalte|sessions|y|text|null||-|-")
    monkeypatch.chdir(_PROJEKT)
    with pytest.raises(SystemExit, match="Unerwartete 'fehlt'"):
        main(["signatur_erzeugen.py", str(datei)])


@pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")
def test_main_bricht_ohne_zuviel_zeilen_ab_statt_einen_leeren_block_zu_schreiben(
        tmp_path, monkeypatch):
    # Ein Fehler ohne '+ zuviel'-Zeilen ist kein Nachpruefungs-Ergebnis (z. B. ein
    # Syntaxfehler in der DDL) — der Fehlertext gehoert dann auf den Schirm.
    datei = _kunstdatei(tmp_path, "  - fehlt:  platzhalter|wird|in|step7|ersetzt")
    monkeypatch.chdir(_PROJEKT)
    with pytest.raises(SystemExit, match="Keine '\\+ zuviel'"):
        main(["signatur_erzeugen.py", str(datei)])
    assert PLATZHALTER_BLOCK in datei.read_text(encoding="utf-8")   # nichts geschrieben
