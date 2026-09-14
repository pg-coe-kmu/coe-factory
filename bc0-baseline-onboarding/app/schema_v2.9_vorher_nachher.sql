-- Schema v2.9 — Vorher / Nachher: der Stand nach einer Erhebung (04.09.2026)
--
-- Simeon, nach v2.8: "Werden die Items geaendert, aendert sich auch der
-- Reifegrad je Prozess. Und immer auf aktuellem Stand — wie machen wir eine
-- Vor-/Nachher-Betrachtung?"
--
-- Der Bericht liest heute immer die Zusammensetzung aus ALLEN nicht
-- verworfenen Erhebungen (v_bewertung_aktuell): je Teilprozess und Item die
-- Zeile aus der juengsten Erhebung, die das Item bewertet hat. Er hat keinen
-- Stichtag. Eine Nacherhebung veraendert ihn — und das Vorher ist weg.
--
-- Loesung, ohne Historie: Die Erhebungen sind geordnet (stand, erhebung_id).
-- "Stand nach X" = dieselbe Zusammensetzungsregel, aber nur ueber die
-- Erhebungen bis einschliesslich X. Damit gibt es fuer jede Erhebung seit
-- Juni ein Vorher und ein Nachher, und der Abschluss bekommt seine Rolle fuer
-- den Bericht: Der "Stand nach X" ist genau dann fest, wenn X und alle
-- Erhebungen davor abgeschlossen (oder verworfen) sind. Abschliessen heisst:
-- "Dieses Vorher steht."
--
-- Nicht dabei: ein Stichtag per Datum (bewertung_aktuell_zum, v2.6) — das
-- bleibt der Weg fuer BC2 und das Paketdatum.
--
-- Wiederholbar. Nur Funktionen und eine Sicht, keine Tabellenaenderung.

BEGIN;

-- ============================================================
-- 1. REIHENFOLGE DER ERHEBUNGEN — eine Stelle fuer die Ordnung
-- ============================================================
CREATE OR REPLACE VIEW v_erhebung_reihenfolge AS
SELECT company_id, erhebung_id, bezeichnung, stand, status,
       row_number() OVER (PARTITION BY company_id ORDER BY stand, erhebung_id) AS rang,
       -- fest = diese und alle frueheren Erhebungen sind nicht mehr offen
       bool_and(status <> 'offen') OVER (PARTITION BY company_id ORDER BY stand, erhebung_id
                                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS fest,
       (SELECT count(*) FROM bitkom_bewertungen b
         WHERE b.company_id = e.company_id AND b.erhebung_id = e.erhebung_id) AS bewertungen
  FROM ref_erhebungen e;

COMMENT ON VIEW v_erhebung_reihenfolge IS
  'Erhebungen je Mandant in ihrer Reihenfolge (stand, erhebung_id) — dieselbe Ordnung, '
  'die v_bewertung_aktuell benutzt. fest = der Stand nach dieser Erhebung kann sich '
  'nicht mehr aendern (sie und alle davor sind abgeschlossen oder verworfen).';

-- ============================================================
-- 2. STAND NACH EINER ERHEBUNG
-- ============================================================
CREATE OR REPLACE FUNCTION bewertung_aktuell_bis(p_company UUID, p_erhebung TEXT)
RETURNS TABLE (sub_process_id TEXT, item_nr INTEGER, erhebung_id TEXT, stufe INTEGER,
               beleg TEXT, quelle TEXT, bewertet_am TIMESTAMPTZ) AS $fn$
  WITH grenze AS (
    SELECT stand, erhebung_id FROM ref_erhebungen
     WHERE company_id = p_company AND erhebung_id = p_erhebung AND status <> 'verworfen')
  SELECT t.sub_process_id::text, t.item_nr, t.erhebung_id, t.stufe, t.beleg, t.quelle::text, t.bewertet_am
    FROM (SELECT b.sub_process_id, b.item_nr, b.erhebung_id, b.stufe, b.beleg, b.quelle, b.bewertet_am,
                 row_number() OVER (PARTITION BY b.sub_process_id, b.item_nr
                                    ORDER BY e.stand DESC, e.erhebung_id DESC) AS rang
            FROM bitkom_bewertungen b
            JOIN ref_erhebungen e ON e.company_id = b.company_id AND e.erhebung_id = b.erhebung_id
            JOIN grenze g ON (e.stand, e.erhebung_id) <= (g.stand, g.erhebung_id)
           WHERE b.company_id = p_company AND e.status <> 'verworfen') t
   WHERE t.rang = 1;
$fn$ LANGUAGE sql STABLE;

COMMENT ON FUNCTION bewertung_aktuell_bis(UUID, TEXT) IS
  'v_bewertung_aktuell, aber nur ueber die Erhebungen bis einschliesslich p_erhebung '
  '(Ordnung: stand, erhebung_id). Leer, wenn die Erhebung unbekannt oder verworfen ist. '
  'Das "Vorher" einer Vor-/Nachher-Betrachtung.';

CREATE OR REPLACE FUNCTION reifegrad_tp_bis(p_company UUID, p_erhebung TEXT)
RETURNS TABLE (sub_process_id TEXT, avg_stufe NUMERIC, n_items BIGINT) AS $fn$
  SELECT b.sub_process_id, round(avg(b.stufe), 2), count(*)
    FROM bewertung_aktuell_bis(p_company, p_erhebung) b
   GROUP BY b.sub_process_id;
$fn$ LANGUAGE sql STABLE;

-- ============================================================
-- 3. VERGLEICH ZWEIER STAENDE — je Teilprozess
-- ============================================================
CREATE OR REPLACE FUNCTION reifegrad_vergleich(p_company UUID, p_von TEXT, p_bis TEXT)
RETURNS TABLE (sub_process_id TEXT, vorher NUMERIC, nachher NUMERIC, delta NUMERIC,
               geaendert BIGINT, neu_bewertet BIGINT) AS $fn$
  WITH v AS (SELECT * FROM bewertung_aktuell_bis(p_company, p_von)),
       n AS (SELECT * FROM bewertung_aktuell_bis(p_company, p_bis)),
       je_item AS (
         SELECT coalesce(n.sub_process_id, v.sub_process_id) AS sub_process_id,
                v.stufe AS alt, n.stufe AS neu
           FROM n FULL JOIN v ON v.sub_process_id = n.sub_process_id AND v.item_nr = n.item_nr)
  SELECT sub_process_id,
         round(avg(alt), 2)                                   AS vorher,
         round(avg(neu), 2)                                   AS nachher,
         round(avg(neu), 2) - round(avg(alt), 2)              AS delta,
         count(*) FILTER (WHERE alt IS NOT NULL AND neu IS NOT NULL AND alt <> neu) AS geaendert,
         count(*) FILTER (WHERE alt IS NULL AND neu IS NOT NULL)                    AS neu_bewertet
    FROM je_item
   GROUP BY sub_process_id
   ORDER BY sub_process_id;
$fn$ LANGUAGE sql STABLE;

COMMENT ON FUNCTION reifegrad_vergleich(UUID, TEXT, TEXT) IS
  'Vorher (Stand nach p_von) gegen Nachher (Stand nach p_bis) je Teilprozess: '
  'Mittelwerte, Differenz, Zahl der geaenderten und der erstmals bewerteten Items. '
  'Die App rechnet dasselbe in Python (SQLite-Betrieb) — Regel hier, Ergebnis dort.';

GRANT SELECT ON v_erhebung_reihenfolge TO bc_leser;
GRANT EXECUTE ON FUNCTION bewertung_aktuell_bis(UUID, TEXT), reifegrad_tp_bis(UUID, TEXT),
                          reifegrad_vergleich(UUID, TEXT, TEXT) TO bc_leser;

COMMIT;

-- Kontrolle:
--   SELECT erhebung_id, rang, fest, bewertungen FROM v_erhebung_reihenfolge WHERE company_id = '…' ORDER BY rang;
--   SELECT * FROM reifegrad_vergleich('…', 'E-2026-06', 'E-2026-08');   -- NoroAI: drei Zeilen mit delta <> 0
