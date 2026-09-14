-- ============================================================
-- BC0 — v1.3 (A2): Leserecht auf ref_prozesse entziehen
-- Stand: 12.08.2026 · Autor: Simeon Ehmer
--
-- ============================================================
--  ERST NACH ABSPRACHE MIT BC1 EINSPIELEN.
-- ============================================================
--
-- Dies ist die einzige Anweisung des gesamten Nachtrags v1.3, die etwas
-- WEGNIMMT. Alles andere ist additiv.
--
-- Was passiert:
--   bc_leser (BC1–BC4) verliert das Recht, `ref_prozesse` direkt zu lesen.
--   Ersatz ist die View `v_prozesse_lesen`.
--
-- Warum:
--   `ref_prozesse.owner_name` enthält Klarnamen natürlicher Personen. Nach
--   ADR-004 R5 stehen Klarnamen an genau einer Stelle (`ref_personen`), und
--   die nachgelagerten Kontexte lesen ausschließlich pseudonymisierte Sichten.
--   Solange `owner_name` als Spalte existiert, ist der Rechteentzug der
--   einzige wirksame Weg — eine Spalte lässt sich in PostgreSQL zwar einzeln
--   entziehen, aber ein `SELECT *` liefe dann auf einen Fehler statt auf ein
--   gekürztes Ergebnis, was schwerer zu diagnostizieren ist.
--
-- Was BC1 ändern muss:
--   FROM ref_prozesse            ->   FROM v_prozesse_lesen
--
--   Die View liefert dieselben Spalten mit zwei Ausnahmen:
--     entfällt:      owner_name, owner_role
--     kommt hinzu:   eigner_ids  TEXT[]   (person_id der Eigner)
--                    sponsor_ids TEXT[]   (person_id der Sponsoren)
--   Wer den Namen zu einer person_id braucht, fragt in BC0 nach. Das ist dann
--   eine dokumentierte Weitergabe und keine stille Mitlieferung.
--
-- Rückabwicklung, falls etwas klemmt:
--   GRANT SELECT ON ref_prozesse TO bc_leser;
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v1.3_teil_a2_rechte_umstellung.sql
-- ============================================================

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    RAISE NOTICE 'Rolle bc_leser nicht vorhanden — nichts zu tun.';
    RETURN;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'v_prozesse_lesen') THEN
    RAISE EXCEPTION 'v_prozesse_lesen fehlt. Erst Teil A einspielen, sonst '
                    'steht BC1 ohne Lesequelle da.';
  END IF;

  REVOKE ALL ON ref_prozesse FROM bc_leser;
  RAISE NOTICE 'bc_leser liest ref_prozesse nicht mehr. Ersatz: v_prozesse_lesen.';
END $$;

-- Kontrolle: was darf bc_leser jetzt noch?
SELECT table_name, privilege_type
  FROM information_schema.role_table_grants
 WHERE grantee = 'bc_leser'
   AND table_name IN ('ref_prozesse', 'v_prozesse_lesen',
                      'v_prozess_personen_lesen', 'ref_personen')
 ORDER BY 1, 2;
