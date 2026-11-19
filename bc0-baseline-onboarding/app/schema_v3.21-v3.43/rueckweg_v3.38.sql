-- Rueckweg v3.38: Pruefregel ohne admin2. Bricht ab, solange ein Konto admin2 hat.
BEGIN;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM app_benutzer WHERE rolle='admin2') THEN
    RAISE EXCEPTION 'Es gibt noch Konten mit rolle admin2 — erst umstellen oder deaktivieren.';
  END IF; END $$;
ALTER TABLE app_benutzer DROP CONSTRAINT app_benutzer_rolle_check;
ALTER TABLE app_benutzer ADD CONSTRAINT app_benutzer_rolle_check CHECK (rolle IN ('benutzer','admin','leser'));
COMMIT;
