-- Vorpruefung fuer v3.17 und v3.18 — NUR LESEND. Ausgabe bitte vollstaendig an Claude.
\pset pager off

\echo '== V1 Spaltentypen (erwartet: aktiv boolean, Namen text)'
SELECT table_name, column_name, data_type
  FROM information_schema.columns
 WHERE table_schema='public'
   AND (table_name, column_name) IN (('ref_teilprozesse','aktiv'),('ref_teilprozesse','sub_process_name'),
                                     ('ref_prozesse','aktiv'),('ref_prozesse','process_name'),
                                     ('audit_log','audit_id'),('gate_ereignisse','datenstand'))
 ORDER BY 1,2;

\echo '== V2 Doppelte ECHTE Teilprozessnamen je Mandant, aktiv (erwartet: 0 Zeilen)'
SELECT company_id, lower(btrim(sub_process_name)) AS name, string_agg(sub_process_id, ', ') AS ids
  FROM ref_teilprozesse
 WHERE aktiv AND sub_process_name IS NOT NULL
   AND btrim(sub_process_name) !~* '^teilprozess[[:space:]]+[0-9]+$'
 GROUP BY 1,2 HAVING count(*) > 1;

\echo '== V3 Doppelte Kernprozessnamen je Mandant, aktiv (erwartet: 0 Zeilen)'
SELECT company_id, lower(btrim(process_name)) AS name, string_agg(process_id, ', ') AS ids
  FROM ref_prozesse
 WHERE aktiv AND process_name IS NOT NULL
 GROUP BY 1,2 HAVING count(*) > 1;

\echo '== V4 Historie: Tabellen mit Teilprozessbezug (zur Abgrenzung, was eine Freigabe veralten laesst)'
SELECT entity, count(*) AS zeilen, max(at)::date AS zuletzt
  FROM v_historie
 WHERE sub_process_id IS NOT NULL AND action <> 'bestand'
 GROUP BY 1 ORDER BY 1;

\echo '== V5 Eigentuemer und Rechte (erwartet: lieferungen -> bc3_role; ki_laufdaten -> postgres, bc4_role INSERT)'
SELECT n.nspname||'.'||c.relname AS tabelle, pg_get_userbyid(c.relowner) AS eigentuemer
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE (n.nspname, c.relname) IN (('bc3','lieferungen'),('public','ki_laufdaten'),('public','gate_ereignisse'));
SELECT grantee, table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) AS rechte
  FROM information_schema.role_table_grants
 WHERE table_name IN ('ki_laufdaten','gate_pakete','ref_anfragen') AND grantee LIKE 'bc%'
 GROUP BY 1,2 ORDER BY 1,2;

\echo '== V6 Trigger auf gate_ereignisse (zur Kenntnis)'
SELECT tgname FROM pg_trigger WHERE tgrelid='gate_ereignisse'::regclass AND NOT tgisinternal ORDER BY 1;

\echo '== V7 Aenderungen an KP-05.TP-1 seit der Freigabe vom 18.09. (NoroAI), ohne Anfrage-/Gate-/BC4-Tabellen'
SELECT entity, action, count(*)
  FROM v_historie
 WHERE company_id='7c2d5ee9-2a9a-5990-810f-502ea2b2012d'
   AND (sub_process_id='KP-05.TP-1' OR (process_id='KP-05' AND sub_process_id IS NULL))
   AND action <> 'bestand' AND entity NOT LIKE 'gate%'
   AND entity NOT IN ('ref_anfragen','anfrage_prozesse','ki_laufdaten','bc_zustellungen')
   AND at > '2026-09-18 07:51:36.097401+00'
 GROUP BY 1,2 ORDER BY 1,2;
