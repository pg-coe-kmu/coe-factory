"""Lesende Zugriffe auf BC0-Objekte. Vier von den fuenf, die Etappe 1 braucht — die
fuenfte (Erhebungs-Lookup) folgt mit Task 13, sobald die offene externe Klaerung steht.

Normativ (Spec R5-I5): JEDER Lookup filtert ueber company_id. BC0 nutzt
zusammengesetzte Schluessel — IDs wie 'KP-01.TP-1' oder 'S-01' wiederholen sich
ueber Mandanten hinweg; ein fehlender Filter ist ein Datenleck.

Die Funktionen nehmen die VERBINDUNG als ersten Parameter: der S-NN-Sweep und der
Erhebungs-Lookup muessen in derselben Transaktion laufen wie der Profil-Write.
Kein voller Baseline-Lesepfad — der kommt in Etappe 2 (#148).
"""
from __future__ import annotations


def mandant_existiert(conn, company_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM companies WHERE company_id = %s", (company_id,)
    ).fetchone() is not None


def teilprozesse(conn, company_id: str) -> list[tuple[str, str]]:
    """(TP-ID, Schrittname) des Mandanten — Grundlage der statischen Auswahl (K2)."""
    return [(zeile[0], zeile[1]) for zeile in conn.execute(
        "SELECT sub_process_id, sub_process_name FROM ref_teilprozesse "
        "WHERE company_id = %s ORDER BY sub_process_id", (company_id,)).fetchall()]


def system_ids(conn, company_id: str) -> list[str]:
    """S-NN-Startmenge des Mandanten (Feldtyp-Grundlage und Sweep-Referenz)."""
    return [zeile[0] for zeile in conn.execute(
        "SELECT system_id FROM mandant_systeme "
        "WHERE company_id = %s ORDER BY system_id", (company_id,)).fetchall()]


def kp_existiert(conn, company_id: str, process_id: str) -> bool:
    """Existenzpruefung ueber v_prozesse_lesen — direktes SELECT auf ref_prozesse
    hat BC0 entzogen (R14-I2). Nur Existenz, kein Baseline-Lesepfad."""
    return conn.execute(
        "SELECT 1 FROM v_prozesse_lesen WHERE company_id = %s AND process_id = %s",
        (company_id, process_id)).fetchone() is not None
