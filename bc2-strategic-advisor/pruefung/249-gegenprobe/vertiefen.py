#!/usr/bin/env python3
"""Vertiefung zu #249 — den drei Abweichungen aus dem ersten Lauf nachgehen.

1. `v_prozessautomatisierung` führt die unbewerteten Teilprozesse NICHT — der
   Snapshot führte sie mit avg 0. Wo genau entsteht der Unterschied?
2. Die echten Pakete tragen einen Teilprozess, nicht sechzehn. Wie sieht der
   Gate-0-Bestand insgesamt aus?
3. Gleicher Beleg, verschiedene Stufe — ein Beispiel zum Zeigen.

Nur lesend.
"""
import json
import os
import sys
from collections import defaultdict

import psycopg2
import psycopg2.extras

NOROAI = None  # wird ermittelt


def hole(cur, sql, args=None):
    cur.execute(sql, args or {})
    return [dict(r) for r in cur.fetchall()]


def main():
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        sys.exit("DATABASE_URL fehlt.")

    out = {}
    with psycopg2.connect(dsn) as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cid = hole(cur, "SELECT company_id FROM companies WHERE name LIKE 'NoroAI%%'")[0]["company_id"]

        # --- 1. Die View selbst ------------------------------------------
        out["view_definition"] = hole(
            cur,
            """SELECT pg_get_viewdef('v_prozessautomatisierung'::regclass, true) AS def""",
        )[0]["def"]

        zeilen = hole(
            cur,
            """SELECT * FROM v_prozessautomatisierung WHERE company_id = %(c)s""",
            {"c": cid},
        )
        out["v_prozessautomatisierung"] = {
            "zeilen": len(zeilen),
            "spalten": sorted(zeilen[0].keys()) if zeilen else [],
            "teilprozesse": sorted({z.get("sub_process_id") for z in zeilen if z.get("sub_process_id")}),
        }
        # Gibt es Zeilen, die eine 0 tragen, wo in Wahrheit nichts erhoben ist?
        nullen = [
            {k: (str(v) if not isinstance(v, (int, float, type(None))) else v) for k, v in z.items()}
            for z in zeilen
            if any(
                isinstance(v, (int, float)) and v == 0
                for k, v in z.items()
                if k not in ("company_id",)
            )
        ]
        out["v_prozessautomatisierung"]["zeilen_mit_einer_null"] = len(nullen)
        out["v_prozessautomatisierung"]["beispiel_null"] = nullen[:3]

        # --- 2. Gate-0-Bestand und Pakete ---------------------------------
        out["gate"] = {}
        for rel, sql in [
            ("v_gate_freigabe_aktuell",
             """SELECT stand, count(*) AS n FROM v_gate_freigabe_aktuell
                 WHERE company_id = %(c)s GROUP BY stand ORDER BY stand"""),
            ("gate_pakete",
             """SELECT p.paket_id::text, p.uebergeben_am::text, p.uebergeben_von,
                       count(i.sub_process_id) AS teilprozesse,
                       count(DISTINCT left(i.sub_process_id, 5)) AS kernprozesse
                  FROM gate_pakete p
                  LEFT JOIN gate_paket_inhalt i
                    ON i.company_id = p.company_id AND i.paket_id = p.paket_id
                 WHERE p.company_id = %(c)s
                 GROUP BY p.paket_id, p.uebergeben_am, p.uebergeben_von
                 ORDER BY p.uebergeben_am"""),
        ]:
            try:
                out["gate"][rel] = hole(cur, sql, {"c": cid})
            except psycopg2.Error as e:
                conn.rollback()
                out["gate"][rel] = {"fehler": str(e).strip().splitlines()[0]}

        # Alle Pakete aller Mandanten — wie groß werden sie überhaupt?
        try:
            out["paketgroessen_alle_mandanten"] = hole(
                cur,
                """SELECT c.name, p.paket_id::text, p.uebergeben_am::text,
                          count(i.sub_process_id) AS teilprozesse,
                          count(DISTINCT left(i.sub_process_id, 5)) AS kernprozesse
                     FROM gate_pakete p
                     JOIN companies c ON c.company_id = p.company_id
                     LEFT JOIN gate_paket_inhalt i
                       ON i.company_id = p.company_id AND i.paket_id = p.paket_id
                    GROUP BY c.name, p.paket_id, p.uebergeben_am
                    ORDER BY p.uebergeben_am""",
            )
        except psycopg2.Error as e:
            conn.rollback()
            out["paketgroessen_alle_mandanten"] = {"fehler": str(e).strip().splitlines()[0]}

        # --- 3. Gleicher Beleg, verschiedene Stufe ------------------------
        bew = hole(
            cur,
            """SELECT b.sub_process_id, b.item_nr, b.stufe, b.beleg, t.process_id
                 FROM v_bewertung_aktuell b
                 JOIN ref_teilprozesse t
                   ON t.company_id = b.company_id AND t.sub_process_id = b.sub_process_id
                WHERE b.company_id = %(c)s AND t.process_id = 'KP-01'
                ORDER BY b.item_nr, b.sub_process_id""",
            {"c": cid},
        )
        je_item = defaultdict(list)
        for z in bew:
            je_item[z["item_nr"]].append(z)
        beispiele = []
        for item, zs in sorted(je_item.items()):
            stufen = {z["stufe"] for z in zs}
            belege = {(z["beleg"] or "").strip() for z in zs}
            if len(stufen) > 1 and len(belege) == 1:
                beispiele.append({
                    "item_nr": item,
                    "stufen_je_teilprozess": {z["sub_process_id"]: z["stufe"] for z in zs},
                    "der_eine_beleg": next(iter(belege))[:300],
                })
        out["gleicher_beleg_verschiedene_stufe_KP01"] = {
            "betroffene_items": len(beispiele),
            "von_items": len(je_item),
            "beispiele": beispiele[:3],
        }

        # --- 4. Wie unterscheidbar macht ein BC1-Profil? -------------------
        prof = hole(
            cur,
            """SELECT DISTINCT ON (focus_step_id)
                      focus_step_id, profil_version, status,
                      frequency_per_year, focus_step_duration_minutes,
                      focus_step_duration_source, total_duration_minutes
                 FROM bc1.prozessprofil
                WHERE company_id = %(c)s AND status = 'fertig'
                ORDER BY focus_step_id, profil_version DESC""",
            {"c": cid},
        )
        out["bc1_profile_inhalt"] = prof

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
