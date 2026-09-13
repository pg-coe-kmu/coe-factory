#!/usr/bin/env python
"""Erzeugt die Sollsignatur einer Einspiel-Datei neu (prozessprofil.sql oder sessions.sql).

Entwicklungswerkzeug, kein Dienstcode: es braucht das BC0-Test-Geruest aus
tests/db_fixture.py und wischt die Zieldatenbank — deshalb liegt es hier bei den
Tests und nicht unter bc1_service/.

WANN: nach JEDER Aenderung an der jeweiligen DDL und beim Wechsel der PostgreSQL-
Hauptversion — sonst bricht das eigene Einspielen mit "Fall 3" ab. Den Diff LESEN
und bewusst committen, niemals die Pruefung abschalten.

WIE: Der Signaturblock der Datei wird durch die Platzhalterzeile ersetzt, die Datei
gegen den frischen Test-Container eingespielt; die Nachpruefung schlaegt fehl und
listet den kompletten Ist-Bestand als "+ zuviel" — daraus entsteht der Block. Die
Transaktion rollt zurueck, es bleibt nichts stehen. NIE gegen die Supabase laufen
lassen: frische_db() droppt die Schemata public und bc1.

AUFRUF (aus bc1-context-discovery/, Container postgres:17 muss laufen):
    BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" \\
        uv run python tests/db/signatur_erzeugen.py bc1_service/db/sessions.sql
Ohne Argument: prozessprofil.sql. Danach: volle Suite laufen lassen.

HAUPTVERSION (K-H, 03.09.): Container und Ziel laufen PostgreSQL 17. Gegen 16 erzeugt,
fehlen die 'acl|<tabelle>|bc1_role|MAINTAIN|f'-Zeilen und das Einspielen im Ziel
bricht mit Fall 3 ab — an beiden Versionen gemessen.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

PLATZHALTER = "    ('platzhalter|wird|in|step7|ersetzt');"
PLATZHALTER_ZEILE = "platzhalter|wird|in|step7|ersetzt"
STANDARD_DATEI = Path("bc1_service/db/prozessprofil.sql")
# Alle Signaturarten der Ist-Sichten (prozessprofil.sql 0b, sessions.sql 0b). Kommt
# eine neue dazu, ist das eine bewusste DDL-Aenderung — hier ergaenzen, nicht raten.
ERLAUBT = ("spalte|", "spalte_acl|", "constraint|", "index|", "trigger|",
           "trigger_intern|", "funktion|", "funktion_acl|", "eigentuemer|",
           "acl|", "mitglied|", "rls|", "policy|", "regel|", "kommentar|",
           "effektiv|", "effektiv_spalte|")
# Rollen sind CLUSTERWEIT und ueberleben frische_db(). Bleibt aus einer Probe eine
# Rolle stehen, landet sie ungefragt in der Sollsignatur (Review 03.09.) — deshalb
# vorher pruefen, statt es zu merken, wenn die Signatur schon committet ist.
ERWARTETE_ROLLEN = {"bc1_role", "bc2_role", "bc3_role", "bc4_role", "bc_leser"}
# Testrest, kein Geruest-Bestandteil: test_ddl_trigger.py legt bc0_loescher an und
# laesst sie stehen (Rollen ueberleben frische_db). Auf einem frischen Cluster fehlt
# sie — beides ist in Ordnung, sie hat keine Rechte auf bc1.* (Review 13.09., Befund 6).
TOLERIERTE_ROLLEN = {"bc0_loescher"}


def rollen_abweichung(vorhanden: set[str]) -> str | None:
    """Meldung, wenn der Cluster nicht genau die erwarteten Rollen traegt — sonst None."""
    relevant = vorhanden - TOLERIERTE_ROLLEN
    if relevant == ERWARTETE_ROLLEN:
        return None
    return ("Der Cluster enthaelt nicht genau die erwarteten Rollen — Abbruch, sonst\n"
            "landen fremde Rollen in der Sollsignatur.\n"
            f"  zuviel: {sorted(relevant - ERWARTETE_ROLLEN)}\n"
            f"  fehlt:  {sorted(ERWARTETE_ROLLEN - relevant)}\n"
            "Proberollen entfernen (DROP OWNED BY <rolle>; DROP ROLE <rolle>) und\n"
            "erneut starten. Ist die Aenderung gewollt, ERWARTETE_ROLLEN anpassen.")


def zeilen_aus_fehlertext(text: str) -> tuple[list[str], list[str]]:
    """Liest aus dem Nachpruefungs-Fehler die '+ zuviel'- und '- fehlt'-Zeilen."""
    zeilen = re.findall(r"^\s*\+ zuviel: (.*)$", text, re.M)
    fehlt = re.findall(r"^\s*- fehlt:\s+(.*)$", text, re.M)
    return zeilen, fehlt


def baue_block(zeilen: Iterable[str]) -> str:
    """Sortierter VALUES-Block fuer INSERT INTO … soll_signatur; Hochkommas verdoppelt."""
    return ",\n".join("    ('" + z.replace("'", "''") + "')" for z in sorted(zeilen)) + ";"


def main(argv: list[str]) -> int:
    from tests.db_fixture import DSN, frische_db, pruefe_lokal, spiele_datei_ein, verbindung

    datei = Path(argv[1]) if len(argv) > 1 else STANDARD_DATEI
    quelle = datei.read_text(encoding="utf-8")
    if quelle.count(PLATZHALTER) != 1:
        sys.exit(f"Die Platzhalterzeile fehlt in {datei}. Vor dem Erzeugen den alten "
                 "Signaturblock durch genau diese Zeile ersetzen:\n" + PLATZHALTER)

    # Rollen VOR dem Reset pruefen (Review 13.09., Befund 1): der Abbruch darf die
    # Datenbank nicht schon gewischt haben. pruefe_lokal() in frische_db haelt
    # zusaetzlich jede nicht lokale DSN fern — hier ausdruecklich davor, weil die
    # Rollenabfrage selbst schon eine Verbindung oeffnet.
    pruefe_lokal(DSN)
    with verbindung(DSN, None) as conn:
        vorhanden = {r[0] for r in conn.execute(
            "SELECT rolname FROM pg_roles WHERE NOT rolsuper "
            "  AND rolname NOT LIKE 'pg\\_%'").fetchall()}
    abweichung = rollen_abweichung(vorhanden)
    if abweichung:
        sys.exit(abweichung)

    frische_db(DSN, mit_ddl=False)
    try:
        spiele_datei_ein(DSN, datei)
    except Exception as fehler:                   # noqa: BLE001 — der Fehler IST das Ergebnis
        text = str(fehler)
    else:
        sys.exit("Das Einspielen lief durch — der Platzhalter war wohl schon ersetzt.")

    zeilen, fehlt = zeilen_aus_fehlertext(text)
    if not zeilen:
        sys.exit("Keine '+ zuviel'-Zeilen im Fehlertext:\n" + text[:2000])
    if fehlt != [PLATZHALTER_ZEILE]:
        sys.exit(f"Unerwartete 'fehlt'-Zeilen (Signatur unvollstaendig?): {fehlt}")
    fremd = [z for z in zeilen if not z.startswith(ERLAUBT)]
    if fremd:
        sys.exit(f"Unbekannte Signaturarten — ERLAUBT ergaenzen? {fremd[:3]}")
    datei.write_text(quelle.replace(PLATZHALTER, baue_block(zeilen)), encoding="utf-8")
    print(f"Sollsignatur eingesetzt in {datei}: {len(zeilen)} Zeilen")
    for art, n in sorted(Counter(z.split("|")[0] for z in zeilen).items()):
        print(f"    {art:16s} {n}")
    print("\nJetzt die volle Suite laufen lassen.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")        # als Skript: 'tests' liegt im Arbeitsverzeichnis, nicht neben der Datei
    sys.exit(main(sys.argv))
