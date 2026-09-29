-- Schema v3.10 — Supabase-Rollen anon/authenticated verlieren alle Rechte in public (29.09.2026)
--
-- Vorgang 912. Eingespielt und behoben am 29.09.2026 (Ergebnis siehe SICHERHEIT.md 3.9).
--
-- BEFUND (gemessen 29.09.2026): alle 36 Tabellen in public ohne Zeilensperre,
-- anon und authenticated mit SELECT/INSERT/UPDATE/DELETE/TRUNCATE -- auch auf
-- app_benutzer, app_sitzungen, ref_personen. Ursache: Supabase-Voreinstellung
-- (Default Privileges fuer die Data-API-Rollen). Die Data API war eingeschaltet
-- und gab public frei; am 29.09.2026 abgeschaltet (Sofortmassnahme).
--
-- WER BRAUCHT anon/authenticated? Niemand. BC0 nutzt nur Supabase Storage mit dem
-- Service-Schluessel; BC1-BC4 verbinden sich ueber eigene Postgres-Rollen.
-- Geprueft im ganzen Repo: kein rest/v1, kein supabase-js.
--
-- DAZU: person_rollen (v3.9) war fuer bc1_role ueber die Gruppe bc_leser lesbar.
-- v3.9 hatte nur das Direktrecht entzogen. Wie bei ref_personen/prozess_personen
-- (beide fuer bc1_role = f) hier auch bc_leser entziehen.
--
-- Ausfuehren: als Eigentuemer (postgres), in einer Transaktion.

BEGIN;

\echo '--- 0. Vorher: Tabellen/Sichten in public mit irgendeinem Recht fuer anon (ERWARTET: > 0)'
SELECT count(*) AS mit_anon_recht
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r','v','m','p')
   AND (has_table_privilege('anon', c.oid, 'SELECT') OR has_table_privilege('anon', c.oid, 'INSERT')
     OR has_table_privilege('anon', c.oid, 'UPDATE') OR has_table_privilege('anon', c.oid, 'DELETE'));

\echo '--- 0b. Eigentuemer der Tabellen in public (fuer die Voreinstellung unten)'
SELECT pg_get_userbyid(c.relowner) AS eigentuemer, count(*)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r','v','m','p')
 GROUP BY 1 ORDER BY 1;

REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

-- Voreinstellung fuer kuenftige Objekte, die postgres anlegt (BC0 legt als postgres an).
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON TABLES    FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated;

REVOKE ALL ON person_rollen FROM bc_leser;

\echo '--- 1. Nachher: Tabellen/Sichten mit Recht fuer anon oder authenticated (ERWARTET: 0)'
SELECT count(*) AS noch_offen
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r','v','m','p')
   AND (has_table_privilege('anon', c.oid, 'SELECT') OR has_table_privilege('anon', c.oid, 'INSERT')
     OR has_table_privilege('anon', c.oid, 'UPDATE') OR has_table_privilege('anon', c.oid, 'DELETE')
     OR has_table_privilege('authenticated', c.oid, 'SELECT') OR has_table_privilege('authenticated', c.oid, 'INSERT')
     OR has_table_privilege('authenticated', c.oid, 'UPDATE') OR has_table_privilege('authenticated', c.oid, 'DELETE'));

\echo '--- 2. person_rollen fuer bc1_role (ERWARTET: f), wie ref_personen und prozess_personen (ERWARTET: f, f)'
SELECT has_table_privilege('bc1_role','person_rollen','SELECT')    AS person_rollen,
       has_table_privilege('bc1_role','ref_personen','SELECT')     AS ref_personen,
       has_table_privilege('bc1_role','prozess_personen','SELECT') AS prozess_personen;

\echo '--- 3. Was BC1 braucht, geht weiter (ERWARTET: alle t)'
SELECT 'v_prozesse_lesen' AS objekt, has_table_privilege('bc1_role','v_prozesse_lesen','SELECT') AS has
UNION ALL SELECT 'v_prozess_personen_lesen', has_table_privilege('bc1_role','v_prozess_personen_lesen','SELECT')
UNION ALL SELECT 'v_anfrage_steller',        has_table_privilege('bc1_role','v_anfrage_steller','SELECT')
UNION ALL SELECT 'mandant_rollen',           has_table_privilege('bc1_role','mandant_rollen','SELECT')
UNION ALL SELECT 'companies',                has_table_privilege('bc1_role','companies','SELECT');

\echo '--- 4. BC2 bis BC4 lesen v_prozesse_lesen weiter (ERWARTET: Zeilen mit t, sofern die Rolle es vorher durfte)'
SELECT r AS rolle, has_table_privilege(r,'v_prozesse_lesen','SELECT') AS has
  FROM unnest(ARRAY['bc2_role','bc3_role','bc4_role']) AS r
 WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r);

\echo '--- 5. Supabase-Dienstrolle unberuehrt (ERWARTET: t)'
SELECT has_table_privilege('service_role','companies','SELECT') AS service_role_liest;

COMMIT;
