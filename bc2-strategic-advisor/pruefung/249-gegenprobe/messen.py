#!/usr/bin/env python3
"""Gegenprobe zu #249 — gelten die Auflösungsbefunde aus #194 an der laufenden Datenbank?

#194 hat an BC0s eingefrorenem Snapshot v3 (27.08.2026) gemessen. Dieses Skript
wiederholt dieselben Messungen gegen die laufende Postgres — über die Views, die
BC2 im Betrieb wirklich liest, nicht über die Rohtabellen.

Der wichtigste Unterschied zum Snapshot steht im Schema: seit v3.4 filtert
`v_bewertung_aktuell` auf `tp.aktiv`. Der Snapshot kennt diesen Filter nicht.
Deshalb wird die Feldauflösung HIER ZWEIMAL gemessen — einmal über alle
Teilprozesse (wie der Snapshot) und einmal nur über die aktiven (wie der Betrieb).

Nur lesend. Kein INSERT, kein UPDATE, kein DDL.

Aufruf:
    DATABASE_URL="postgresql://bc2_role...@...:5432/postgres?sslmode=require" \
        python3 messen.py > befund.json
"""
import json
import os
import sys
from collections import defaultdict

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2 fehlt:  pip install psycopg2-binary")

FELDER = ["sub_process_name", "notation", "tools", "medienbrueche", "schnittstellen", "api"]

# Der Snapshot-Befund aus #194, gegen den verglichen wird. Reproduziert am
# 21.09.2026 aus packen.py:aufloesung_messen() — die Zahlen stimmen mit der
# Tabelle im Ticketkopf überein.
SNAPSHOT_194 = {
    "sub_process_name": 0,   # im Snapshot "name"
    "notation": 4,
    "tools": 10,
    "medienbrueche": 10,
    "schnittstellen": 7,
    "api": 10,
}
SNAPSHOT_OHNE_BEWERTUNG = 27
SNAPSHOT_KERNPROZESSE = 10


def hole(cur, sql, args=None):
    cur.execute(sql, args or {})
    return [dict(r) for r in cur.fetchall()]


def spalte_existiert(cur, tabelle, spalte, schema="public"):
    cur.execute(
        """SELECT 1 FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s AND column_name=%s""",
        (schema, tabelle, spalte),
    )
    return cur.fetchone() is not None


def relation_existiert(cur, name, schema="public"):
    cur.execute(
        """SELECT 1 FROM information_schema.tables
            WHERE table_schema=%s AND table_name=%s""",
        (schema, name),
    )
    return cur.fetchone() is not None


# ---------------------------------------------------------------- Messung 1
def feldaufloesung(cur, company_id, nur_aktive):
    """Bei wie vielen Kernprozessen ist ein Feld über ALLE Teilprozesse wortgleich?

    Genau die Frage aus #194. Ein Kernprozess mit nur einem Teilprozess zählt
    dort als »identisch« — das ist keine Wiederholung, sondern ein entarteter
    Fall, und wird deshalb hier zusätzlich getrennt ausgewiesen.
    """
    hat_aktiv = spalte_existiert(cur, "ref_teilprozesse", "aktiv")
    wo = "WHERE company_id = %(c)s" + (" AND aktiv" if (nur_aktive and hat_aktiv) else "")
    zeilen = hole(
        cur,
        f"""SELECT process_id, sub_process_id, {', '.join(FELDER)}
              FROM ref_teilprozesse {wo}
             ORDER BY process_id, step_no""",
        {"c": company_id},
    )

    je_kp = defaultdict(list)
    for z in zeilen:
        je_kp[z["process_id"]].append(z)

    ergebnis, detail = {}, {}
    for feld in FELDER:
        identisch, identisch_ab_zwei = [], []
        for kp, tps in sorted(je_kp.items()):
            werte = {(t.get(feld) or "") for t in tps}
            if len(werte) == 1:
                identisch.append(kp)
                if len(tps) > 1:
                    identisch_ab_zwei.append(kp)
        ergebnis[feld] = len(identisch)
        detail[feld] = {
            "identisch_bei": identisch,
            "identisch_ab_zwei_teilprozessen": identisch_ab_zwei,
        }

    return {
        "aktiv_filter_angewandt": bool(nur_aktive and hat_aktiv),
        "spalte_aktiv_vorhanden": hat_aktiv,
        "kernprozesse": len(je_kp),
        "teilprozesse": len(zeilen),
        "teilprozesse_je_kernprozess": {k: len(v) for k, v in sorted(je_kp.items())},
        "identisch_bei_wievielen_kernprozessen": ergebnis,
        "detail": detail,
    }


# ---------------------------------------------------------------- Messung 2
def belegtexte(cur, company_id):
    """Tragen alle Bitkom-Items über alle Teilprozesse eines Kernprozesses denselben Beleg?

    Gelesen über v_bewertung_aktuell — die View, die BC2 im Betrieb benutzt —,
    NICHT über bitkom_bewertungen. Genau der Unterschied, den #249 benennt.
    """
    zeilen = hole(
        cur,
        """SELECT b.sub_process_id, b.item_nr, b.beleg, b.stufe, t.process_id
             FROM v_bewertung_aktuell b
             JOIN ref_teilprozesse t
               ON t.company_id = b.company_id AND t.sub_process_id = b.sub_process_id
            WHERE b.company_id = %(c)s""",
        {"c": company_id},
    )

    # je Kernprozess: {item_nr: {beleg, ...}} und {item_nr: {stufe, ...}}
    belege = defaultdict(lambda: defaultdict(set))
    stufen = defaultdict(lambda: defaultdict(set))
    tps_je_kp = defaultdict(set)
    for z in zeilen:
        belege[z["process_id"]][z["item_nr"]].add((z["beleg"] or "").strip())
        stufen[z["process_id"]][z["item_nr"]].add(z["stufe"])
        tps_je_kp[z["process_id"]].add(z["sub_process_id"])

    je_kp = {}
    for kp in sorted(belege):
        n_tp = len(tps_je_kp[kp])
        items = belege[kp]
        gleich = [i for i, s in items.items() if len(s) == 1]
        je_kp[kp] = {
            "bewertete_teilprozesse": n_tp,
            "items": len(items),
            "items_mit_identischem_beleg": len(gleich),
            "alle_items_identisch": len(gleich) == len(items) and len(items) > 0,
            # Der Kernbefund aus #194: Stufen unterscheiden sich, Begründungen nicht.
            "items_mit_identischer_stufe": sum(1 for i, s in stufen[kp].items() if len(s) == 1),
        }

    mehrere = {k: v for k, v in je_kp.items() if v["bewertete_teilprozesse"] > 1}
    return {
        "bewertete_kernprozesse": len(je_kp),
        "davon_mit_mehr_als_einem_bewerteten_teilprozess": len(mehrere),
        "alle_belege_identisch_bei": sum(1 for v in mehrere.values() if v["alle_items_identisch"]),
        "je_kernprozess": je_kp,
    }


# ---------------------------------------------------------------- Messung 3
def nullbewertete(cur, company_id):
    """Teilprozesse ohne jede Bewertung, die in der Automatisierungssicht trotzdem 0 tragen.

    Im Snapshot: 27 von 50. Die Falle ist, eine Lücke als Zahl zu lesen.
    """
    hat_view = relation_existiert(cur, "v_prozessautomatisierung")
    hat_aktiv = spalte_existiert(cur, "ref_teilprozesse", "aktiv")

    alle = hole(
        cur,
        f"""SELECT t.sub_process_id, t.process_id
              {', t.aktiv' if hat_aktiv else ''}
              FROM ref_teilprozesse t WHERE t.company_id = %(c)s""",
        {"c": company_id},
    )
    mit = {
        r["sub_process_id"]
        for r in hole(
            cur,
            """SELECT DISTINCT sub_process_id FROM v_bewertung_aktuell
                WHERE company_id = %(c)s""",
            {"c": company_id},
        )
    }
    ohne = [t for t in alle if t["sub_process_id"] not in mit]

    in_sicht = None
    if hat_view:
        sicht = {
            r["sub_process_id"]
            for r in hole(
                cur,
                """SELECT DISTINCT sub_process_id FROM v_prozessautomatisierung
                    WHERE company_id = %(c)s""",
                {"c": company_id},
            )
        }
        in_sicht = sorted(t["sub_process_id"] for t in ohne if t["sub_process_id"] in sicht)

    return {
        "teilprozesse_gesamt": len(alle),
        "ohne_bewertung": len(ohne),
        "ohne_bewertung_ids": sorted(t["sub_process_id"] for t in ohne),
        "davon_aktiv": sum(1 for t in ohne if t.get("aktiv")) if hat_aktiv else None,
        "v_prozessautomatisierung_vorhanden": hat_view,
        "ohne_bewertung_aber_in_v_prozessautomatisierung": in_sicht,
        "anzahl_ohne_bewertung_aber_in_sicht": len(in_sicht) if in_sicht is not None else None,
    }


# ---------------------------------------------------------------- Messung 4
def bc1_abdeckung(cur, company_id):
    """Wie viele freigegebene Teilprozesse eines echten Pakets tragen ein BC1-Profil?

    Frage 2 aus #249. Gelesen nach der vertraglichen Leseregel
    (contracts/bc1-to-bc2/lesen.sql): jüngste profil_version mit status='fertig'.
    """
    if not relation_existiert(cur, "prozessprofil", schema="bc1"):
        return {"bc1_prozessprofil_lesbar": False}

    profile = hole(
        cur,
        """SELECT DISTINCT ON (focus_step_id)
                  focus_step_id, profil_version, process_id, status
             FROM bc1.prozessprofil
            WHERE company_id = %(c)s AND status = 'fertig'
            ORDER BY focus_step_id, profil_version DESC""",
        {"c": company_id},
    )
    mit_profil = {p["focus_step_id"] for p in profile}

    pakete = []
    if relation_existiert(cur, "v_uebergabe_offen"):
        zeilen = hole(
            cur,
            """SELECT paket_id, uebergeben_am, sub_process_id, paket_rang, bc1_profil_stand
                 FROM v_uebergabe_offen WHERE company_id = %(c)s
                ORDER BY uebergeben_am DESC, paket_id, sub_process_id""",
            {"c": company_id},
        )
        je_paket = defaultdict(list)
        for z in zeilen:
            je_paket[(str(z["paket_id"]), str(z["uebergeben_am"]), z["paket_rang"])].append(z)
        for (pid, wann, rang), inhalt in je_paket.items():
            tps = [i["sub_process_id"] for i in inhalt]
            treffer = [t for t in tps if t in mit_profil]
            pakete.append({
                "paket_id": pid,
                "uebergeben_am": wann,
                "paket_rang": rang,
                "teilprozesse": len(tps),
                "teilprozess_ids": tps,
                "mit_bc1_profil": len(treffer),
                "mit_bc1_profil_ids": treffer,
                "abdeckung_prozent": round(100 * len(treffer) / len(tps), 1) if tps else None,
            })

    return {
        "bc1_prozessprofil_lesbar": True,
        "fertige_profile": len(profile),
        "fertige_profil_teilprozesse": sorted(mit_profil),
        "pakete": pakete,
    }


# ---------------------------------------------------------------- Rahmen
def rahmen(cur):
    mandanten = hole(
        cur,
        """SELECT c.company_id, c.name,
                  (SELECT count(*) FROM ref_teilprozesse t WHERE t.company_id=c.company_id) AS teilprozesse,
                  (SELECT count(DISTINCT b.sub_process_id) FROM v_bewertung_aktuell b
                    WHERE b.company_id=c.company_id) AS bewertete_teilprozesse
             FROM companies c ORDER BY c.name""",
    )
    for m in mandanten:
        m["company_id"] = str(m["company_id"])
    return {"mandanten": mandanten}


def main():
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        sys.exit("DATABASE_URL ist nicht gesetzt (Session-Pooler 5432, Rolle bc2_role).")

    with psycopg2.connect(dsn) as conn:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT current_user, version()")
            umgebung = dict(cur.fetchone())
            r = rahmen(cur)

            befunde = {}
            for m in r["mandanten"]:
                cid = m["company_id"]
                befunde[m["name"]] = {
                    "company_id": cid,
                    "feldaufloesung_alle_teilprozesse": feldaufloesung(cur, cid, nur_aktive=False),
                    "feldaufloesung_nur_aktive": feldaufloesung(cur, cid, nur_aktive=True),
                    "belegtexte": belegtexte(cur, cid),
                    "nullbewertete": nullbewertete(cur, cid),
                    "bc1_abdeckung": bc1_abdeckung(cur, cid),
                }

    print(json.dumps({
        "umgebung": {"rolle": umgebung["current_user"], "server": umgebung["version"][:40]},
        "vergleichsmassstab_194_snapshot_v3": {
            "identisch_bei_wievielen_kernprozessen": SNAPSHOT_194,
            "kernprozesse": SNAPSHOT_KERNPROZESSE,
            "ohne_bewertung": SNAPSHOT_OHNE_BEWERTUNG,
        },
        "rahmen": r,
        "befunde": befunde,
    }, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
