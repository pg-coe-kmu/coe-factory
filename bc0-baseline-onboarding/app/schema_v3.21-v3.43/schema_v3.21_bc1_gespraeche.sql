-- ============================================================
-- BC0 · Schema v3.21 — Gespraechskennung je Anfrage fuer das BC1-Interview
-- Stand: 28.10.2026 · BC0
-- Anlass: Brief BC1 an BC0 „Einbau des Interviews in die Anfrage-App“ (27.10.2026),
--   Teil 2 Abschnitt B Punkt 6: Die session_id wird dauerhaft zur Anfrage gespeichert,
--   nicht nur im Arbeitsspeicher. Sonst entsteht nach einem Neustart des Backends eine
--   zweite BC1-Sitzung zum selben Teilprozess.
-- VORAUSSETZUNG: v1.1.1 … v3.19c eingespielt (ref_anfragen mit PK company_id, anfrage_id).
--
-- WAS DIESES SKRIPT TUT
--   * Neue Tabelle bc1_gespraeche (eine Zeile je Anfrage, session_id eindeutig).
--   * Rechte: nur der Eigentuemer (postgres, Backend). Kein Recht fuer anon,
--     authenticated, bc_leser oder die BC-Rollen — BC1 braucht die Tabelle nicht,
--     es bekommt die Kennung mit jedem Turn.
--
-- WAS ES NICHT TUT
--   Keine Aenderung an ref_anfragen (deren Audit-Trigger bleiben unberuehrt),
--   keine Nachrichtentexte — die speichert BC0 nie.
--
-- EINSPIELEN (nach Backup):
--   cd /opt/bc0 && docker run --rm -i --env-file .env postgres:17 sh -c \
--     'psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -P pager=off' < schema_v3.21_bc1_gespraeche.sql
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.bc1_gespraeche (
  company_id   UUID        NOT NULL,
  anfrage_id   TEXT        NOT NULL,
  session_id   TEXT        NOT NULL CHECK (session_id ~ '^[A-Za-z0-9_-]{1,64}$'),
  angelegt_am  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_bc1_gespraeche PRIMARY KEY (company_id, anfrage_id),
  CONSTRAINT uq_bc1_gespraeche_session UNIQUE (session_id),
  CONSTRAINT fk_bc1_gespraeche_anfrage FOREIGN KEY (company_id, anfrage_id)
    REFERENCES public.ref_anfragen (company_id, anfrage_id) ON DELETE CASCADE
);

COMMENT ON TABLE public.bc1_gespraeche IS
  'v3.21: dauerhafte BC1-Gespraechskennung (session_id) je Anfrage. Setzt nur das '
  'BC0-Backend beim ersten Turn. Keine Nachrichtentexte. Nur Eigentuemer hat Rechte.';

REVOKE ALL ON public.bc1_gespraeche FROM PUBLIC;
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','bc_leser','bc1_role','bc2_role','bc3_role','bc4_role']
  LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON public.bc1_gespraeche FROM %I', r);
    END IF;
  END LOOP;
END $$;

COMMIT;

-- ============================================================
-- KONTROLLE — nach dem Einspielen
-- ============================================================
\echo '--- 1. Tabelle da (ERWARTET: bc1_gespraeche | 0)'
SELECT to_regclass('public.bc1_gespraeche') AS tabelle, count(*) AS zeilen FROM public.bc1_gespraeche;
\echo '--- 2. Rollen mit irgendeinem Recht ausser Eigentuemer (ERWARTET: keine Zeile)'
SELECT grantee, string_agg(privilege_type, ',') AS rechte
  FROM information_schema.role_table_grants
 WHERE table_schema = 'public' AND table_name = 'bc1_gespraeche'
   AND grantee <> (SELECT tableowner FROM pg_tables WHERE tablename = 'bc1_gespraeche')
 GROUP BY grantee;
