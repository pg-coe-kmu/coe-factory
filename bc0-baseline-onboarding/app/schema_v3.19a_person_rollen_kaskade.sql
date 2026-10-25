-- Schema v3.19 — DSGVO-Loeschung trotz person_rollen (25.10.2026)
--
-- Befund (BC1-Hinweis vom 24.10., Wortlaut bei BC0 nicht angekommen; von BC0
-- nachgestellt, Drehbuch S-175): person_rollen (v3.9) verweist auf
-- mandant_rollen ohne ON DELETE (NO ACTION). Loescht man einen Mandanten,
-- raeumt die Kaskade mandant_rollen auf Tiefe 1, person_rollen aber erst auf
-- Tiefe 2 (ueber ref_personen). Die Pruefung auf mandant_rollen schlaegt vorher
-- zu: "still referenced from table person_rollen" — der Mandant bleibt stehen.
--
-- Aenderung: Der Fremdschluessel person_rollen -> mandant_rollen wird
-- DEFERRABLE INITIALLY DEFERRED (Vorbild: BC1 profil_rollen_rolle_fk). Die
-- Pruefung laeuft erst beim COMMIT; dann ist person_rollen schon geraeumt.
-- Eine einzelne Rolle, die noch einer Person zugeordnet ist, bleibt
-- unloeschbar (Abbruch beim COMMIT).
--
-- Ausfuehren als postgres, eine Transaktion. Gegenprobe am Ende (ROLLBACK).

BEGIN;

DO $$
DECLARE v_name TEXT;
BEGIN
  SELECT conname INTO v_name FROM pg_constraint
   WHERE conrelid = 'person_rollen'::regclass AND contype = 'f'
     AND confrelid = 'mandant_rollen'::regclass;
  IF v_name IS NULL THEN
    RAISE EXCEPTION 'Fremdschluessel person_rollen -> mandant_rollen nicht gefunden.';
  END IF;
  EXECUTE format('ALTER TABLE person_rollen DROP CONSTRAINT %I', v_name);
END $$;

ALTER TABLE person_rollen
  ADD CONSTRAINT person_rollen_rolle_fk
  FOREIGN KEY (company_id, rolle_id) REFERENCES mandant_rollen(company_id, rolle_id)
  DEFERRABLE INITIALLY DEFERRED;

COMMENT ON CONSTRAINT person_rollen_rolle_fk ON person_rollen IS
  'v3.19: DEFERRABLE INITIALLY DEFERRED, damit die DSGVO-Loeschung eines Mandanten '
  'durchlaeuft. Eine noch zugeordnete Rolle bleibt beim COMMIT geschuetzt.';

COMMIT;

-- Gegenprobe (nur lesend): erwartet eine Zeile, condeferrable t, condeferred t
--   SELECT conname, condeferrable, condeferred FROM pg_constraint
--    WHERE conrelid='person_rollen'::regclass AND confrelid='mandant_rollen'::regclass;
