-- v3.40 Teil B: eigene Datenbankrolle bc0_app, Eigentum der BC0-Objekte in public
-- Aufruf: psql -v pw=<passwort> -v commit=0   (Probelauf, ROLLBACK)
--         psql -v pw=<passwort> -v commit=1   (echter Lauf, COMMIT)
-- Das Passwort kommt aus einer Shell-Variable des Verfassers und wird nie angezeigt.
\set ON_ERROR_STOP on
\if :{?pw}
\else
  \echo 'Abbruch: Variable pw fehlt'
  \quit
\endif
\if :{?commit}
\else
  \echo 'Abbruch: Variable commit (0 oder 1) fehlt'
  \quit
\endif
BEGIN;

\echo '== B0 Vorbedingungen'
DO $b0$ BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'B0: als postgres ausfuehren, nicht als %', current_user; END IF;
  IF NOT has_schema_privilege('postgres','public','CREATE') THEN RAISE EXCEPTION 'B0: postgres hat kein CREATE auf public'; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='bc0_app') THEN RAISE EXCEPTION 'B0: Rolle bc0_app existiert bereits'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE roleid='bc_leser'::regrole AND member='postgres'::regrole AND admin_option)
  THEN RAISE EXCEPTION 'B0: postgres darf bc_leser nicht weitergeben (keine ADMIN-Option)'; END IF;
END $b0$;
SELECT count(*) FILTER (WHERE c.relforcerowsecurity) AS force_rls,
       count(*) FILTER (WHERE c.relrowsecurity) AS rls_an
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r';

\echo '== B1 Rechte anderer Rollen vorher festhalten'
CREATE TEMP TABLE b1_vorher ON COMMIT DROP AS
  SELECT grantee::text, table_name::text, privilege_type::text
    FROM information_schema.role_table_grants
   WHERE table_schema='public' AND grantee NOT IN ('postgres','bc0_app');
SELECT count(*) AS rechte_vorher FROM b1_vorher;

\echo '== B2 Rolle anlegen'
CREATE ROLE bc0_app LOGIN PASSWORD :'pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT;
GRANT bc0_app TO postgres;
GRANT bc_leser TO bc0_app;
GRANT USAGE, CREATE ON SCHEMA public TO bc0_app;

\echo '== B3 Eigentum uebertragen (ohne Objekte von Erweiterungen)'
DO $b3$ DECLARE r record; n_rel int := 0; n_seq int := 0; n_fn int := 0; n_typ int := 0; BEGIN
  FOR r IN SELECT c.oid::regclass AS obj, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f') AND c.relowner='postgres'::regrole
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype='e')
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO bc0_app',
      CASE r.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW' WHEN 'f' THEN 'FOREIGN TABLE' ELSE 'TABLE' END, r.obj);
    n_rel := n_rel + 1;
  END LOOP;
  FOR r IN SELECT c.oid::regclass AS obj FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind='S' AND c.relowner='postgres'::regrole
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype IN ('e','a','i'))
  LOOP EXECUTE format('ALTER SEQUENCE %s OWNER TO bc0_app', r.obj); n_seq := n_seq + 1; END LOOP;
  FOR r IN SELECT p.oid::regprocedure AS fn, p.prokind FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND p.proowner='postgres'::regrole
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e')
  LOOP EXECUTE format('ALTER %s %s OWNER TO bc0_app', CASE r.prokind WHEN 'p' THEN 'PROCEDURE' WHEN 'a' THEN 'AGGREGATE' ELSE 'FUNCTION' END, r.fn);
       n_fn := n_fn + 1; END LOOP;
  FOR r IN SELECT t.oid::regtype AS typ, t.typtype FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
            WHERE n.nspname='public' AND t.typowner='postgres'::regrole AND t.typtype IN ('e','d','r','m')
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_type'::regclass AND d.objid=t.oid AND d.deptype='e')
  LOOP EXECUTE format('ALTER %s %s OWNER TO bc0_app', CASE r.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END, r.typ);
       n_typ := n_typ + 1; END LOOP;
  RAISE NOTICE 'B3 uebertragen: Tabellen/Sichten %, Sequenzen %, Funktionen %, Typen %', n_rel, n_seq, n_fn, n_typ;
END $b3$;

\echo '== B4 Gegenproben'
SELECT pg_get_userbyid(c.relowner) AS eigentuemer, c.relkind, count(*)
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind IN ('r','v','m','S') GROUP BY 1,2 ORDER BY 1,2;
DO $b4$ DECLARE n int; v record; t text; BEGIN
  -- a) Rechte anderer Rollen unveraendert
  SELECT count(*) INTO n FROM (
    (SELECT * FROM b1_vorher EXCEPT
     SELECT grantee::text, table_name::text, privilege_type::text FROM information_schema.role_table_grants
      WHERE table_schema='public' AND grantee NOT IN ('postgres','bc0_app'))
    UNION ALL
    (SELECT grantee::text, table_name::text, privilege_type::text FROM information_schema.role_table_grants
      WHERE table_schema='public' AND grantee NOT IN ('postgres','bc0_app') EXCEPT SELECT * FROM b1_vorher)) x;
  IF n <> 0 THEN RAISE EXCEPTION 'B4a: % Rechte anderer Rollen veraendert', n; END IF;
  -- b) nichts mehr bei postgres ausser Erweiterungen
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
   WHERE ns.nspname='public' AND c.relowner='postgres'::regrole AND c.relkind IN ('r','v','m','S')
     AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype='e');
  IF n <> 0 THEN RAISE EXCEPTION 'B4b: % Objekte gehoeren noch postgres', n; END IF;
  -- c) Lesen fremder Schemata wie bisher, Aendern nicht
  FOREACH t IN ARRAY ARRAY['bc1.prozessprofil','bc1.profil_rollen','bc2.eingang','bc2.lauf','bc2.gate1','bc3.lieferungen','bc2.v_ergebnisakte'] LOOP
    IF to_regclass(t) IS NOT NULL THEN
      IF NOT has_table_privilege('bc0_app', t, 'SELECT') THEN RAISE EXCEPTION 'B4c: bc0_app kann % nicht lesen', t; END IF;
      IF has_table_privilege('bc0_app', t, 'INSERT') OR has_table_privilege('bc0_app', t, 'UPDATE')
         OR has_table_privilege('bc0_app', t, 'DELETE') OR has_table_privilege('bc0_app', t, 'TRUNCATE')
      THEN RAISE EXCEPTION 'B4c: bc0_app darf % aendern', t; END IF;
    END IF;
  END LOOP;
  -- d) jede Sicht in public laesst sich als bc0_app abfragen
  SET LOCAL ROLE bc0_app;
  FOR v IN SELECT c.oid::regclass AS obj FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
            WHERE ns.nspname='public' AND c.relkind IN ('v','m') LOOP
    EXECUTE format('SELECT 1 FROM %s LIMIT 0', v.obj);
  END LOOP;
  -- e) Start-DDL der App: Eigentuemerin darf aendern, Rolle darf anlegen
  EXECUTE 'CREATE TABLE IF NOT EXISTS public.v340_probe(x int)';
  EXECUTE 'ALTER TABLE public.v340_probe ADD COLUMN IF NOT EXISTS y int';
  EXECUTE 'DROP TABLE public.v340_probe';
  RESET ROLE;
  RAISE NOTICE 'B4 bestanden: Rechte unveraendert, Eigentum vollstaendig, Lesen fremder Schemata ja, Aendern nein, alle Sichten abfragbar, Start-DDL moeglich';
END $b4$;

\if :commit
  COMMIT;
  \echo '== COMMIT: v3.40 Teil B eingespielt'
\else
  ROLLBACK;
  \echo '== PROBELAUF: ROLLBACK, nichts geaendert'
\endif
