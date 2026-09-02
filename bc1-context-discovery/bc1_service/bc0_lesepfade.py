"""Lesende Zugriffe auf BC0-Objekte — die sechs, die Etappe 1 braucht.

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
    """(TP-ID, Schrittname) des Mandanten — ALLE, auch unbewertete. Seit Rev. 11 nur
    noch die Strukturpruefung beim Start; die Interview-Auswahl liefert
    bewertete_teilprozesse()."""
    return [(zeile[0], zeile[1]) for zeile in conn.execute(
        "SELECT sub_process_id, sub_process_name FROM ref_teilprozesse "
        "WHERE company_id = %s ORDER BY sub_process_id", (company_id,)).fetchall()]


def bewertete_teilprozesse(conn, company_id: str) -> list[tuple[str, str]]:
    """Teilprozesse mit mindestens einer AKTUELLEN Bewertung — nur diese sind
    interviewbar (Rev. 11). Ohne aktuelle Bewertung gibt es keine erhebung_id, und zu
    einem unbewerteten Teilprozess entsteht kein Profil (BC0-Antwort 1b, 02.09.).
    'Aktuell' im Sinn der Sicht v_bewertung_aktuell: verworfene Erhebungen zaehlen
    nicht. Die 27-von-30-Regel prueft das Gate, nicht BC1."""
    return [(zeile[0], zeile[1]) for zeile in conn.execute(
        "SELECT t.sub_process_id, t.sub_process_name FROM ref_teilprozesse t "
        " WHERE t.company_id = %s AND EXISTS ("
        "       SELECT 1 FROM v_bewertung_aktuell v "
        "        WHERE v.company_id = t.company_id "
        "          AND v.sub_process_id = t.sub_process_id) "
        " ORDER BY t.sub_process_id", (company_id,)).fetchall()]


def system_ids(conn, company_id: str) -> list[str]:
    """S-NN-Startmenge des Mandanten (Feldtyp-Grundlage und Sweep-Referenz)."""
    return [zeile[0] for zeile in conn.execute(
        "SELECT system_id FROM mandant_systeme "
        "WHERE company_id = %s ORDER BY system_id", (company_id,)).fetchall()]


class ErhebungFehltError(RuntimeError):
    """Zum Teilprozess gibt es keine aktuelle Bewertung — es kann kein Profil entstehen."""


def erhebung_id(conn, company_id: str, focus_step_id: str) -> str:
    """Die juengste unter den aktuellen Erhebungen des Teilprozesses (BC0-Antwort 1a,
    02.09.). 'Juengste' = groesster ref_erhebungen.stand, bei Gleichstand die groessere
    erhebung_id — exakt die Rangfolge, mit der v_bewertung_aktuell selbst rankt.
    NICHT bewertet_am: eine Korrektur innerhalb einer alten Erhebung setzt bewertet_am
    neu (save_rating, ON CONFLICT), aendert aber nicht, welche Erhebung aktuell ist.

    Keine aktuelle Bewertung => ErhebungFehltError (unsere Spalte ist NOT NULL). Seit
    Task 10b bietet der Dienst nur bewertete Teilprozesse an; der Fehler faengt den
    Wettlauf 'Bewertung nach Sitzungsstart verworfen'.

    Zwei Festlegungen, die aus der Sicht folgen und BC0/BC2 noch bestaetigen muessen:
    * Eine OFFENE Erhebung gilt als aktuell — v_bewertung_aktuell schliesst nur
      'verworfen' aus. Das Profil kann sich damit an eine laufende Erhebung binden,
      die BC0 spaeter verwirft; der FK merkt das nicht (K-K).
    * Geliefert wird die Erhebung mit dem juengsten Stand, NICHT die Erhebung, aus der
      alle aktuellen Items stammen. Bei itemweiser Aktualitaet stehen aktuelle
      Bewertungen aus aelteren Erhebungen daneben. Wer die Bewertungen ueber diese
      eine ID laedt statt ueber v_bewertung_aktuell, sieht zu wenig (K-L)."""
    zeile = conn.execute(
        "SELECT v.erhebung_id FROM v_bewertung_aktuell v "
        "  JOIN ref_erhebungen e ON e.company_id = v.company_id "
        "                       AND e.erhebung_id = v.erhebung_id "
        " WHERE v.company_id = %s AND v.sub_process_id = %s "
        " ORDER BY e.stand DESC, e.erhebung_id DESC LIMIT 1",
        (company_id, focus_step_id)).fetchone()
    if zeile is None:
        raise ErhebungFehltError(
            f"Teilprozess {focus_step_id} hat keine aktuelle Bewertung — "
            "ohne erhebung_id kann kein Profil entstehen.")
    return zeile[0]


def kp_existiert(conn, company_id: str, process_id: str) -> bool:
    """Existenzpruefung ueber v_prozesse_lesen — direktes SELECT auf ref_prozesse
    hat BC0 entzogen (R14-I2). Nur Existenz, kein Baseline-Lesepfad."""
    return conn.execute(
        "SELECT 1 FROM v_prozesse_lesen WHERE company_id = %s AND process_id = %s",
        (company_id, process_id)).fetchone() is not None
