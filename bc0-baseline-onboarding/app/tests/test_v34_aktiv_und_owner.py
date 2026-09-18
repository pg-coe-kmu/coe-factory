# -*- coding: utf-8 -*-
"""v3.4 — Der aktiv-Filter und der eindeutige Eigner.

Zwei Regeln, eine Trennlinie:

* **Jetzt** — ein stillgelegter Teilprozess zaehlt nicht mehr mit.
* **Damals** — er zaehlt weiter, so wie es damals war.

Die zweite ist die wichtigere. Wuerde der Bericht zu einer alten Erhebung auf
das HEUTIGE ``aktiv`` filtern, verschwaenden Prozesse rueckwirkend aus einem
Bericht, den es damals anders gab — das Gegenteil von R9.

Der Eigner-Index braucht PostgreSQL (partieller Index) und wird in
``schema_v3.4_aktiv_und_owner.sql`` gegen die Produktion geprueft.
"""
import app as A


# --- Die Trennlinie ---------------------------------------------------------

def test_aktueller_stand_filtert_stillgelegte():
    sql = A._bew_aktuell("*")
    assert "ref_teilprozesse" in sql
    assert "tp.aktiv" in sql


def test_stand_nach_einer_erhebung_filtert_NICHT():
    """Der Kern von v3.4: Der historische Weg bleibt ungefiltert."""
    sql = A._bew_aktuell("*", grenze=("2026-08-31", "E-2026-08"))
    assert "ref_teilprozesse" not in sql
    assert "tp.aktiv" not in sql


def test_die_grenze_bleibt_erhalten():
    """Der aktiv-Filter darf den v2.9-Filter nicht verdraengen."""
    sql = A._bew_aktuell("*", grenze=("2026-08-31", "E-2026-08"))
    assert "E-2026-08" in sql
    assert "e.stand" in sql


def test_beide_fassungen_bleiben_gueltiges_sql():
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE bitkom_bewertungen (company_id TEXT, erhebung_id TEXT, id TEXT,"
              " sub_process_id TEXT, item_nr INT, stufe INT, beleg TEXT, quelle TEXT,"
              " bewerter TEXT, bewertet_am TEXT)")
    c.execute("CREATE TABLE ref_erhebungen (company_id TEXT, erhebung_id TEXT, stand TEXT,"
              " status TEXT)")
    c.execute("CREATE TABLE ref_teilprozesse (company_id TEXT, sub_process_id TEXT, aktiv INT)")
    for sql in (A._bew_aktuell("*"), A._bew_aktuell("*", grenze=("2026-08-31", "E-2026-08"))):
        c.execute("SELECT count(*) FROM " + sql).fetchone()


def test_stillgelegter_teilprozess_faellt_aus_dem_aktuellen_stand():
    """Gegen echte Zeilen, nicht nur gegen den Text der Abfrage."""
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE bitkom_bewertungen (company_id TEXT, erhebung_id TEXT, id TEXT,"
              " sub_process_id TEXT, item_nr INT, stufe INT, beleg TEXT, quelle TEXT,"
              " bewerter TEXT, bewertet_am TEXT)")
    c.execute("CREATE TABLE ref_erhebungen (company_id TEXT, erhebung_id TEXT, stand TEXT,"
              " status TEXT)")
    c.execute("CREATE TABLE ref_teilprozesse (company_id TEXT, sub_process_id TEXT, aktiv INT)")
    c.execute("INSERT INTO ref_erhebungen VALUES ('C','E-2026-08','2026-08-31','abgeschlossen')")
    c.execute("INSERT INTO ref_teilprozesse VALUES ('C','KP-01.TP-1',1)")
    c.execute("INSERT INTO ref_teilprozesse VALUES ('C','KP-02.TP-1',0)")   # stillgelegt
    for tp in ("KP-01.TP-1", "KP-02.TP-1"):
        c.execute("INSERT INTO bitkom_bewertungen VALUES ('C','E-2026-08','x',?,1,4,'b','manuell','w','t')",
                  (tp,))

    jetzt = [r["sub_process_id"] for r in c.execute(
        "SELECT sub_process_id FROM " + A._bew_aktuell("*")).fetchall()]
    assert jetzt == ["KP-01.TP-1"], jetzt

    damals = sorted(r["sub_process_id"] for r in c.execute(
        "SELECT sub_process_id FROM " + A._bew_aktuell("*", grenze=("2026-08-31", "E-2026-08"))).fetchall())
    assert damals == ["KP-01.TP-1", "KP-02.TP-1"], damals


# --- Das Schemablatt --------------------------------------------------------

def test_schemablatt_traegt_die_fuenf_bausteine():
    """Was v3.4 verspricht, muss auch darin stehen — die Gegenprobe zum
    Ausrollblatt, damit niemand einen Baustein vergisst."""
    import os
    pfad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "schema_v3.4_aktiv_und_owner.sql")
    if not os.path.exists(pfad):
        return
    with open(pfad, encoding="utf-8") as f:
        sql = f.read()
    for baustein in ("CREATE OR REPLACE VIEW v_prozesse_lesen",
                     "owner_rolle_id",
                     "ux_prozess_eigner_eindeutig",
                     "CREATE OR REPLACE VIEW v_bewertung_aktuell",
                     "CREATE OR REPLACE VIEW v_teilprozesse_lesen",
                     "CREATE OR REPLACE VIEW v_systeme_lesen",
                     "GRANT SELECT ON v_anfrage_steller TO bc_leser"):
        assert baustein in sql, baustein


def test_historische_funktion_wird_nicht_angefasst():
    """bewertung_aktuell_zum() ruht auf stand_zum() und darf nicht filtern."""
    import os
    pfad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "schema_v3.4_aktiv_und_owner.sql")
    if not os.path.exists(pfad):
        return
    with open(pfad, encoding="utf-8") as f:
        sql = f.read()
    assert "bewertung_aktuell_zum" not in sql.split("GEGENPROBEN")[0] or \
           "CREATE OR REPLACE FUNCTION bewertung_aktuell_zum" not in sql
