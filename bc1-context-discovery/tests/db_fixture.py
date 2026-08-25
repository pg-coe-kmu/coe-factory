"""Fixture-Helfer für alle DB-Tests: BC0-Gerüst + unsere DDL + zwei Mandanten.

Zwei Mandanten sind Pflicht (Spec R5-I5): BC0-IDs wie 'KP-01.TP-1' oder 'S-01'
wiederholen sich über Mandanten hinweg — ein vergessener company_id-Filter fällt
nur mit einem zweiten Mandanten auf.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg

DSN = os.environ.get("BC1_TEST_DB_DSN")

MANDANT_A = "11111111-1111-1111-1111-111111111111"
MANDANT_B = "22222222-2222-2222-2222-222222222222"

_GERUEST = Path(__file__).parent / "db" / "bc0_geruest.sql"
_DDL = Path(__file__).parents[1] / "bc1_service" / "db" / "prozessprofil.sql"


def frische_db(dsn: str, *, mit_ddl: bool = True) -> None:
    """Setzt public + bc1 zurueck, baut das Geruest, spielt (optional) unsere DDL ein.

    ACHTUNG: raeumt auch bc1.sessions weg — einen PostgresStateStore erst NACH
    diesem Aufruf anlegen (sein Konstruktor legt die Tabelle wieder an).
    """
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS bc1 CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(_GERUEST.read_text(encoding="utf-8"))
        _testdaten(conn)
    if mit_ddl:
        spiele_ddl_ein(dsn)


def spiele_ddl_ein(dsn: str) -> None:
    """Spielt prozessprofil.sql genau wie im Betrieb ein: EINE Transaktion, als bc1_role."""
    with psycopg.connect(dsn) as conn:          # autocommit=False => eine Transaktion
        conn.execute("SET ROLE bc1_role")
        conn.execute(_DDL.read_text(encoding="utf-8"))
        conn.commit()


@contextmanager
def verbindung(dsn: str, rolle: str | None = "bc1_role"):
    """Verbindung mit optionalem SET ROLE (None = postgres/Superuser)."""
    with psycopg.connect(dsn) as conn:
        if rolle:
            conn.execute(f"SET ROLE {rolle}")
        yield conn


def _testdaten(conn) -> None:
    for mandant, kuerzel in ((MANDANT_A, "A"), (MANDANT_B, "B")):
        conn.execute("INSERT INTO companies (company_id, name) VALUES (%s, %s)",
                     (mandant, f"Demo {kuerzel}"))
        conn.execute(
            "INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) "
            "VALUES (%s, 'KP-01', %s, 'Kerngeschäftsprozess'), "
            "       (%s, 'KP-02', %s, 'Unterstützungsprozess')",
            (mandant, f"Auftrag {kuerzel}", mandant, f"Einkauf {kuerzel}"))
        # Namen bewusst mandantenspezifisch: gleiche IDs, verschiedene Inhalte —
        # nur so faellt ein fehlender company_id-Filter im Test auf.
        conn.execute(
            "INSERT INTO ref_teilprozesse "
            "(company_id, sub_process_id, process_id, step_no, sub_process_name) VALUES "
            "(%s, 'KP-01.TP-1', 'KP-01', 1, %s), "
            "(%s, 'KP-01.TP-2', 'KP-01', 2, %s), "
            "(%s, 'KP-02.TP-1', 'KP-02', 1, %s)",
            (mandant, f"Erfassen {kuerzel}", mandant, f"Pruefen {kuerzel}",
             mandant, f"Bestellen {kuerzel}"))
        conn.execute(
            "INSERT INTO mandant_rollen (company_id, rolle_id, bezeichnung, klasse) "
            "VALUES (%s, 'R-01', 'Sachbearbeitung', 'K2')", (mandant,))
    # Nur bei Mandant B: damit lassen sich Verbund-FK und Mandantenfilter gezielt
    # verletzen — eine ID, die es beim anderen Mandanten NICHT gibt.
    conn.execute(
        "INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) "
        "VALUES (%s, 'KP-03', 'Nur bei B', 'Steuerungsprozess')", (MANDANT_B,))
    conn.execute(
        "INSERT INTO ref_teilprozesse "
        "(company_id, sub_process_id, process_id, step_no, sub_process_name) "
        "VALUES (%s, 'KP-02.TP-2', 'KP-02', 2, 'Nur bei B')", (MANDANT_B,))
    # Systeme: S-01 gibt es in BEIDEN Mandanten (verschiedene Bedeutung),
    # S-02 nur in A, S-03 nur in B — genau der Fall, den ein fehlender Filter frisst.
    conn.execute("INSERT INTO mandant_systeme (company_id, system_id, bezeichnung) "
                 "VALUES (%s, 'S-01', 'SAP A'), (%s, 'S-02', 'DATEV A')",
                 (MANDANT_A, MANDANT_A))
    conn.execute("INSERT INTO mandant_systeme (company_id, system_id, bezeichnung) "
                 "VALUES (%s, 'S-01', 'Navision B'), (%s, 'S-03', 'Lexware B')",
                 (MANDANT_B, MANDANT_B))
    conn.execute(
        "INSERT INTO ref_items (item_nr, dimension, kriterium, frage) VALUES "
        "(1, '1) Technologie', 'Systemunterstuetzung', 'Wie digital laeuft der Schritt?'), "
        "(2, '2) Daten', 'Datenqualitaet', 'Wie strukturiert liegen die Daten vor?')")
    conn.execute(
        "INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, stand, status) "
        "VALUES (%s, 'E-2026-01', 'Erst', '2026-01-15', 'abgeschlossen'), "
        "       (%s, 'E-2026-02', 'Nach',  '2026-06-01', 'abgeschlossen')",
        (MANDANT_A, MANDANT_A))
    conn.execute(
        "INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, stand, status) "
        "VALUES (%s, 'E-2026-09', 'B-Erhebung', '2026-03-01', 'abgeschlossen')",
        (MANDANT_B,))
    # A: KP-01.TP-1 wurde in E-2026-01 bewertet und in E-2026-02 teilweise nacherhoben
    # (genau die 1.2-Logik: je Item die juengste nicht verworfene Erhebung).
    # id folgt BC0s Muster '^KP-\d{2}\.TP-\d+\.I-\d{2}$'; beleg ist Pflicht.
    # A: Item 1 wurde in E-2026-02 nacherhoben, Item 2 steht noch auf E-2026-01 —
    # genau die 1.2-Logik "je Einzelbewertung die juengste nicht verworfene".
    conn.execute(
        "INSERT INTO bitkom_bewertungen "
        "(company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg, "
        " bewertet_am) VALUES "
        "(%s, 'E-2026-01', 'KP-01.TP-1.I-01', 'KP-01.TP-1', 1, 2, 'Erstaufnahme', "
        " '2026-01-15'), "
        "(%s, 'E-2026-01', 'KP-01.TP-1.I-02', 'KP-01.TP-1', 2, 3, 'Erstaufnahme', "
        " '2026-01-15')",
        (MANDANT_A, MANDANT_A))
    conn.execute(
        "UPDATE bitkom_bewertungen SET erhebung_id = 'E-2026-02', "
        "       stufe = 4, beleg = 'Nacherhebung', bewertet_am = '2026-06-01' "
        " WHERE company_id = %s AND id = 'KP-01.TP-1.I-01'", (MANDANT_A,))
    # B: gleicher Teilprozess-Schluessel, andere Erhebung — Kollisionsfalle.
    conn.execute(
        "INSERT INTO bitkom_bewertungen "
        "(company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg) VALUES "
        "(%s, 'E-2026-09', 'KP-01.TP-1.I-01', 'KP-01.TP-1', 1, 5, 'B-Aufnahme')",
        (MANDANT_B,))
