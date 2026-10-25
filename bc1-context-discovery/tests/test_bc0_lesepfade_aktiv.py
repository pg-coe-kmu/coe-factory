"""aktiv-Semantik im BC0-Lesepfad (BC0 v2.2/v3.4: stillgelegt statt geloescht).

Seit v3.4 filtern v_prozesse_lesen und v_bewertung_aktuell selbst; fuer die zwei
Tabellen, die BC1 direkt las, gibt es v_teilprozesse_lesen und v_systeme_lesen
(Simeons Brief 18.09.2026, Punkt 3). Ein stillgelegter Teilprozess ist nicht
interviewbar, ein stillgelegtes System kein gueltiges S-NN, ein stillgelegter
Kernprozess nicht bekannt. Jeder Test hier bekommt eine eigene frische DB, weil
er Bestand stilllegt.
"""
import pytest

from bc1_service import bc0_lesepfade
from tests.db_fixture import DSN, MANDANT_A, frische_db, verbindung

pytestmark = pytest.mark.skipif(not DSN, reason="BC1_TEST_DB_DSN nicht gesetzt")


def _stilllegen(tabelle: str, schluessel: str, wert: str) -> None:
    """Wie BC0 es tut (v2.2): aktiv = false, nichts loeschen. Als Superuser.

    Einen Kernprozess legt BC0 seit v3.8 nicht mehr still (Trigger). Den Zustand gibt es
    nur noch per INSERT ... aktiv = false; BC1s Zusatzschutz "aktiver Elternprozess" bleibt,
    bis BC0 das bestaetigt (Plan-Geruest-BC0-v3.19, E2). Deshalb hier sichtbar abgeschaltet.
    """
    with verbindung(DSN, None) as conn:
        if tabelle == "ref_prozesse":
            conn.execute("ALTER TABLE ref_prozesse DISABLE TRIGGER kernprozess_bleibt_aktiv")
        conn.execute(f"UPDATE {tabelle} SET aktiv = false "
                     f" WHERE company_id = %s AND {schluessel} = %s", (MANDANT_A, wert))
        if tabelle == "ref_prozesse":
            conn.execute("ALTER TABLE ref_prozesse ENABLE TRIGGER kernprozess_bleibt_aktiv")
        conn.commit()


def test_stillgelegter_teilprozess_fehlt_in_der_teilprozessliste():
    frische_db(DSN)
    _stilllegen("ref_teilprozesse", "sub_process_id", "KP-01.TP-2")
    with verbindung(DSN) as conn:
        ids = [tp for tp, _ in bc0_lesepfade.teilprozesse(conn, MANDANT_A)]
    assert "KP-01.TP-2" not in ids
    assert "KP-01.TP-1" in ids                        # der Rest bleibt


def test_stillgelegtes_system_fehlt_in_der_snn_startmenge():
    frische_db(DSN)
    _stilllegen("mandant_systeme", "system_id", "S-02")
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.system_ids(conn, MANDANT_A) == ["S-01"]


def test_stillgelegter_teilprozess_ist_nicht_interviewbar():
    # KP-01.TP-1 hat bei A aktuelle Bewertungen — stillgelegt zaehlt er trotzdem nicht
    # (v_bewertung_aktuell filtert tp.aktiv seit v3.4; Simeon 18.09.: ein stillgelegter
    # Teilprozess zaehlt nicht in den Reifegrad eines aktuellen Berichts).
    frische_db(DSN)
    _stilllegen("ref_teilprozesse", "sub_process_id", "KP-01.TP-1")
    with verbindung(DSN) as conn:
        ids = [tp for tp, _ in bc0_lesepfade.bewertete_teilprozesse(conn, MANDANT_A)]
        assert "KP-01.TP-1" not in ids
        with pytest.raises(bc0_lesepfade.ErhebungFehltError):
            bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-01.TP-1")


def test_stillgelegter_kernprozess_ist_nicht_bekannt():
    # v_prozesse_lesen filtert aktiv seit v3.4 — ein stillgelegter KP ist fuer den
    # upstream/downstream-Abgleich (kp_bekannt im Writer) kein gueltiger Bezug mehr.
    frische_db(DSN)
    _stilllegen("ref_prozesse", "process_id", "KP-02")
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_A, "KP-02") is False
        assert bc0_lesepfade.kp_existiert(conn, MANDANT_A, "KP-01") is True


def test_stillgelegter_kernprozess_fehlt_in_der_kernprozessliste():
    frische_db(DSN)
    _stilllegen("ref_prozesse", "process_id", "KP-02")
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.kernprozesse(conn, MANDANT_A) == [("KP-01", "Auftrag A")]


def test_teilprozesse_eines_stillgelegten_kernprozesses_sind_nicht_interviewbar():
    # BC0s Sichten pruefen nur tp.aktiv (v3.4) — ein stillgelegter Kernprozess mit
    # aktiven Kindern bliebe interviewbar. BC1 verlangt zusaetzlich den aktiven
    # Elternprozess (Codex-Review 22.09., Important 2). Seit v3.8 entsteht der Zustand
    # nur noch per INSERT ... aktiv = false; ob BC0 auch das ausschliesst, ist erfragt.
    frische_db(DSN)
    _stilllegen("ref_prozesse", "process_id", "KP-02")   # KP-02.TP-1 bleibt aktiv
    with verbindung(DSN) as conn:
        assert "KP-02.TP-1" not in [tp for tp, _ in bc0_lesepfade.teilprozesse(conn, MANDANT_A)]
        assert "KP-02.TP-1" not in [
            tp for tp, _ in bc0_lesepfade.bewertete_teilprozesse(conn, MANDANT_A)]
        with pytest.raises(bc0_lesepfade.ErhebungFehltError):
            bc0_lesepfade.erhebung_id(conn, MANDANT_A, "KP-02.TP-1")


def test_kernprozesse_sind_nach_id_sortiert():
    # Spec-Matrix "Sortierung": KP-00 kommt NACH der Fixture dazu und muss trotzdem
    # zuerst stehen — ohne ORDER BY kaeme es in Einfuegereihenfolge zuletzt.
    frische_db(DSN)
    with verbindung(DSN, None) as conn:
        conn.execute("INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie) "
                     "VALUES (%s, 'KP-00', 'Zuerst', 'Steuerungsprozess')", (MANDANT_A,))
        conn.commit()
    with verbindung(DSN) as conn:
        assert bc0_lesepfade.kernprozesse(conn, MANDANT_A)[0] == ("KP-00", "Zuerst")
