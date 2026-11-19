-- v3.41 Stufe 1: Sicht v_bc2_vorgabe — die in Gate 1 freigegebenen Potenziale von BC2 als Vorgabe fuer BC3/BC4
-- Nur lesend auf bc2.v_ergebnisakte, keine Kopie (ADR-003). Eine Zeile je freigegebenem Potenzial und Teilprozess.
-- Ausfuehren als bc0_app (DATABASE_URL der App), damit die Sicht bc0_app gehoert.
\set ON_ERROR_STOP on
BEGIN;
DO $v0$ BEGIN
  IF current_user <> 'bc0_app' THEN RAISE EXCEPTION 'als bc0_app ausfuehren, nicht als %', current_user; END IF;
  IF to_regclass('bc2.v_ergebnisakte') IS NULL THEN RAISE EXCEPTION 'bc2.v_ergebnisakte fehlt'; END IF;
  IF to_regclass('public.v_bc2_vorgabe') IS NOT NULL THEN RAISE EXCEPTION 'v_bc2_vorgabe existiert bereits'; END IF;
END $v0$;

CREATE VIEW public.v_bc2_vorgabe AS
WITH akte AS (
  SELECT company_id, paket_id, fassung, priorisierung_id, eingefroren_am, lieferbar, name, dokument
    FROM bc2.v_ergebnisakte
   WHERE dokument IS NOT NULL
), prio AS (
  SELECT * FROM akte WHERE name = 'prozesspriorisierung.json'
), konz AS (
  SELECT a.priorisierung_id, a.dokument->>'konzept_id' AS konzept_id, p AS pot
    FROM akte a CROSS JOIN LATERAL jsonb_array_elements(a.dokument->'potenziale') p
   WHERE a.name LIKE 'konzept\_%.json'
)
SELECT pr.company_id,
       pr.paket_id,
       pr.fassung,
       pr.priorisierung_id,
       pr.eingefroren_am,
       pr.lieferbar,
       pr.dokument->'gate1'->>'status'                                   AS gate1_status,
       e->>'potenzial_id'                                                AS potenzial_id,
       k.konzept_id,
       (e->>'potenzialrang')::int                                        AS potenzialrang,
       array_position(ARRAY(SELECT jsonb_array_elements_text(pr.dokument->'gate1'->'finale_reihenfolge_potenzial_ids')),
                      e->>'potenzial_id')                                AS finaler_rang,
       e->>'prioritaetsgruppe'                                           AS prioritaetsgruppe,
       (e->>'score')::numeric                                            AS score,
       e->>'kp_id'                                                       AS kp_id,
       tp.sub_process_id,
       EXISTS (SELECT 1 FROM public.ref_teilprozesse r
                WHERE r.company_id::text = pr.company_id AND r.sub_process_id = tp.sub_process_id) AS teilprozess_bekannt,
       k.pot->>'titel'                                                   AS titel,
       k.pot->>'user_story'                                              AS user_story,
       k.pot->'akzeptanzkriterien_geschaeftlich'                         AS akzeptanzkriterien,
       COALESCE(jsonb_array_length(k.pot->'akzeptanzkriterien_geschaeftlich'), 0) AS anzahl_akzeptanzkriterien,
       (k.pot->'automatisierungsgrad'->>'angesetzt_min_pct')::numeric    AS automatisierung_min_pct,
       (k.pot->'automatisierungsgrad'->>'angesetzt_max_pct')::numeric    AS automatisierung_max_pct,
       (k.pot->'manueller_aufwand_heute'->>'stunden_jahr')::numeric      AS stunden_jahr_heute,
       (k.pot->>'aufwand_schaetzung_pt')::numeric                        AS aufwand_pt,
       k.pot->'value'->'einsparung_eur_jahr'                             AS einsparung_eur_jahr,
       (k.pot->'value'->>'investition_eur_richtwert')::numeric           AS investition_eur_richtwert,
       k.pot->'value'->'ist_kosten_eur_jahr'                             AS ist_kosten_eur_jahr,
       k.pot->'value'->'ersparnis_prozent'                               AS ersparnis_prozent,
       k.pot->'value'->'amortisation_monate'                             AS amortisation_monate,
       k.pot->'value'->>'value_quelle'                                   AS value_quelle,
       (k.pot->>'impact')::int                                           AS impact,
       (k.pot->>'umsetzungskomplexitaet')::int                           AS umsetzungskomplexitaet,
       k.pot->>'kategorie'                                               AS kategorie
  FROM prio pr
  CROSS JOIN LATERAL jsonb_array_elements(pr.dokument->'eintraege') e
  JOIN konz k ON k.priorisierung_id = pr.priorisierung_id AND k.pot->>'potenzial_id' = e->>'potenzial_id'
  CROSS JOIN LATERAL jsonb_array_elements_text(e->'betroffene_teilprozess_ids') AS tp(sub_process_id)
 WHERE pr.dokument->'gate1'->>'status' = 'approved'
   AND (pr.dokument->'gate1'->'approved_potenzial_ids') ? (e->>'potenzial_id');

COMMENT ON VIEW public.v_bc2_vorgabe IS
  'v3.41: In Gate 1 freigegebene Potenziale von BC2 als Vorgabe fuer BC3/BC4, je Teilprozess. Liest bc2.v_ergebnisakte (eingefroren), keine Kopie.';

\echo '== Gegenprobe'
SELECT priorisierung_id, count(DISTINCT potenzial_id) AS potenziale, count(*) AS zeilen,
       count(*) FILTER (WHERE NOT teilprozess_bekannt) AS teilprozess_unbekannt,
       sum(anzahl_akzeptanzkriterien) AS akzeptanzkriterien
  FROM public.v_bc2_vorgabe GROUP BY 1 ORDER BY 1;
SELECT company_id, sub_process_id, potenzialrang, finaler_rang, left(titel,50) AS titel, anzahl_akzeptanzkriterien,
       automatisierung_min_pct, stunden_jahr_heute, aufwand_pt
  FROM public.v_bc2_vorgabe ORDER BY company_id, potenzialrang, sub_process_id;

\if :{?commit}
\else
  \set commit 0
\endif
\if :commit
  COMMIT;
  \echo '== COMMIT: v_bc2_vorgabe angelegt'
\else
  ROLLBACK;
  \echo '== PROBELAUF: ROLLBACK'
\endif
