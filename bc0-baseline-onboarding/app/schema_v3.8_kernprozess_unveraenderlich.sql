-- ============================================================
-- BC0 · Schema v3.8 — Kernprozess nicht stilllegbar, Teilprozess weiterhin ja
-- Stand: 23.09.2026 · Simeon Ehmer
-- Anlass: Richards Frage (Brief 22.09., Abschnitt 1.4) zur Kaskade
--   Stilllegung Kernprozess -> Teilprozesse. Entscheidung Simeon 23.09.:
--   Ein Kernprozess wird im Unternehmen fachlich nie stillgelegt, nur
--   Teilprozesse. Die Kaskadenfrage stellt sich damit nicht mehr - sie wird
--   durch Unmoeglichkeit beantwortet statt durch eine Regel.
-- VORAUSSETZUNG: schema_v1.1.1 ... schema_v3.7 (PR #259) eingespielt.
--   ref_prozesse.aktiv existiert seit v2.2, DELETE ist seit v2.6 ueber
--   trg_stilllegen_statt_loeschen abgewiesen. Dieses Skript schliesst die
--   verbleibende Luecke: UPDATE ... SET aktiv = false auf ref_prozesse war
--   bislang technisch weiterhin moeglich.
--
-- WAS DIESES SKRIPT TUT
--   Neuer Trigger auf ref_prozesse: jedes UPDATE, das aktiv auf false
--   setzt, wird abgewiesen. ref_teilprozesse bleibt unveraendert - dort
--   bleibt Stilllegen (aktiv = false) der vorgesehene Weg.
--
-- WAS ES NICHT TUT
--   Aendert nichts an bestehenden Zeilen, keine Rechte, kein DELETE-Verhalten
--   (das regelt bereits trg_stilllegen_statt_loeschen aus v2.6).
--
-- EINSPIELEN (nach Backup):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema_v3.8_kernprozess_unveraenderlich.sql
-- ============================================================

BEGIN;

CREATE OR REPLACE FUNCTION trg_kernprozess_bleibt_aktiv() RETURNS TRIGGER AS $fn$
BEGIN
  IF NEW.aktiv = false THEN
    RAISE EXCEPTION
      'Kernprozess % kann nicht stillgelegt werden - nur seine Teilprozesse. '
      'Ein Kernprozess ist eine fachliche Kategorie und wird im Unternehmen '
      'nie ausser Betrieb genommen (Entscheidung Simeon, 23.09.2026).', NEW.process_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS kernprozess_bleibt_aktiv ON ref_prozesse;
CREATE TRIGGER kernprozess_bleibt_aktiv BEFORE UPDATE OF aktiv ON ref_prozesse
  FOR EACH ROW EXECUTE FUNCTION trg_kernprozess_bleibt_aktiv();

COMMENT ON COLUMN ref_prozesse.aktiv IS
  'Immer true. Seit v3.8 technisch erzwungen (kernprozess_bleibt_aktiv) - '
  'ein Kernprozess wird fachlich nie stillgelegt, nur seine Teilprozesse '
  '(ref_teilprozesse.aktiv). Die Spalte bleibt aus Symmetrie mit '
  'ref_teilprozesse und fuer kuenftige Faelle stehen, ist aber gesperrt.';

COMMIT;

-- ============================================================
-- KONTROLLE — nach dem Einspielen
-- ============================================================
-- 1) Bestehende Kernprozesse unveraendert aktiv:
--    SELECT count(*) FROM ref_prozesse WHERE NOT aktiv;  -> 0 (erwartet, vorher schon 0)
-- 2) Sperre greift (muss FEHLSCHLAGEN mit der obigen Meldung):
--    UPDATE ref_prozesse SET aktiv = false WHERE process_id = 'KP-01' LIMIT 1;
-- 3) Teilprozess-Stilllegung weiterhin moeglich (in einer Transaktion testen,
--    dann ROLLBACK):
--    BEGIN;
--    UPDATE ref_teilprozesse SET aktiv = false
--      WHERE sub_process_id = (SELECT sub_process_id FROM ref_teilprozesse LIMIT 1);
--    -- erwartet: UPDATE 1, keine Fehlermeldung
--    ROLLBACK;
