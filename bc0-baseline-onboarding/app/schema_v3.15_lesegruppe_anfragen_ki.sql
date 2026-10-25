-- ============================================================================
-- schema_v3.15 — ref_anfragen und die vier offenen ki_*-Tabellen verlassen
--                die Lesegruppe
-- BC0 · Simeon Ehmer · 08.10.2026
-- ============================================================================
--
-- ANLASS: Vertrauliche Nachricht BC1 an BC0 vom 06.10.2026 (zwei Rechte-Befunde
-- aus dem Bau von B5, bewusst nicht im Repo). Am 08.10.2026 LIVE GEMESSEN —
-- beide Befunde treffen zu:
--
--   1. ref_anfragen: laut v1.4 fuer bc_leser bewusst geschlossen (originaltext
--      kann personenbezogene Angaben tragen) — tatsaechlich lesbar fuer
--      bc_leser und bc1_role (Voreinstellung pg_default_acl, #214), von
--      keinem spaeteren Skript entzogen.
--   2. v3.11 hat nur ki_schulungen, ki_research_bereiche, ki_research_notizen
--      entzogen. ki_wissensdb und ki_strategie (beide mit person_id),
--      ki_meilensteine und ki_laufdaten waren ueber die Voreinstellung fuer
--      bc_leser und bc1_role lesbar.
--
-- WAS BLEIBT: BC1 liest Anfragen ausschliesslich ueber v_anfrage_prozessbezug
-- und v_anfrage_teilprozesse (bc0_lesepfade.py). Eine Sicht laeuft mit den
-- Rechten ihres Eigentuemers (v3.6, am 22.09. gegengeprueft) — die Sichten
-- liefern nach dem Entzug unveraendert. BC4 behaelt SELECT, INSERT auf
-- ki_laufdaten (v3.11): BC4 schreibt die Laufdaten.
--
-- WAS DIESE DATEI NICHT TUT: Die Voreinstellung selbst (pg_default_acl auf
-- public) bleibt stehen — die naechste neue Tabelle ist wieder automatisch
-- lesbar. Das bleibt die offene Frage aus #214/#262.
--
-- Ausfuehren als Eigentuemer, eine Transaktion. Bricht die Gegenprobe ab,
-- ist nichts geaendert.
-- ============================================================================

BEGIN;

REVOKE SELECT ON ref_anfragen
  FROM bc_leser, bc1_role, bc2_role, bc3_role, bc4_role;

REVOKE ALL ON ki_wissensdb, ki_strategie, ki_meilensteine
  FROM bc_leser, bc1_role, bc2_role, bc3_role, bc4_role;

REVOKE ALL ON ki_laufdaten
  FROM bc_leser, bc1_role, bc2_role, bc3_role;
-- BC4 behaelt, was v3.11 ihm gegeben hat (ausdruecklich erneut, falls der
-- Entzug oben eine Gruppen-Vergabe beruehrt haette):
GRANT SELECT, INSERT ON ki_laufdaten TO bc4_role;

-- Gegenprobe im selben Vorgang — bricht mit RAISE ab, dann kein COMMIT.
DO $$
DECLARE
  offen TEXT;
BEGIN
  -- 1. Niemand aus der Lesegruppe liest die fuenf Tabellen (ausser BC4 die Laufdaten)
  SELECT string_agg(r || ':' || t, ', ' ORDER BY r, t) INTO offen
    FROM unnest(ARRAY['bc_leser','bc1_role','bc2_role','bc3_role','bc4_role']) r,
         unnest(ARRAY['ref_anfragen','ki_wissensdb','ki_strategie','ki_meilensteine','ki_laufdaten']) t
   WHERE has_table_privilege(r, t, 'SELECT')
     AND NOT (r = 'bc4_role' AND t = 'ki_laufdaten');
  IF offen IS NOT NULL THEN
    RAISE EXCEPTION 'Noch lesbar: %', offen;
  END IF;

  -- 2. BC4 darf Laufdaten weiter schreiben und lesen
  IF NOT (has_table_privilege('bc4_role','ki_laufdaten','INSERT')
          AND has_table_privilege('bc4_role','ki_laufdaten','SELECT')) THEN
    RAISE EXCEPTION 'bc4_role hat SELECT/INSERT auf ki_laufdaten verloren';
  END IF;

  -- 3. Die Anfrage-Sichten, die BC1 liest, bleiben lesbar
  IF NOT (has_table_privilege('bc1_role','v_anfrage_prozessbezug','SELECT')
          AND has_table_privilege('bc1_role','v_anfrage_teilprozesse','SELECT')) THEN
    RAISE EXCEPTION 'BC1 kann die Anfrage-Sichten nicht mehr lesen';
  END IF;

  RAISE NOTICE 'v3.15: ref_anfragen + ki_wissensdb/_strategie/_meilensteine/_laufdaten aus der Lesegruppe entzogen; Sichten und BC4-Laufdaten unveraendert';
END $$;

COMMIT;

-- ----------------------------------------------------------------------------
-- Gegenprobe nach dem Einspielen (ERWARTET: Tabellen f, Sichten t)
--   SELECT t, has_table_privilege('bc_leser',t,'SELECT') bc_leser,
--             has_table_privilege('bc1_role',t,'SELECT') bc1
--     FROM unnest(ARRAY['ref_anfragen','ki_wissensdb','ki_strategie',
--          'ki_meilensteine','ki_laufdaten','v_anfrage_prozessbezug',
--          'v_anfrage_teilprozesse']) t;
-- Die Sicht liefert weiter (ERWARTET: dieselbe Zahl wie vorher):
--   SELECT count(*) FROM v_anfrage_prozessbezug;
-- ----------------------------------------------------------------------------
