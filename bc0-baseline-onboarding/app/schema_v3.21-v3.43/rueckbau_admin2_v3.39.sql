-- v3.39 Rueckbau Admin2 (13.11.2026). Entscheidung BC0: "Admin2 findet nicht statt."
-- 1. Konten mit Rolle admin2 werden auf 'benutzer' gesetzt und gesperrt (nicht geloescht).
-- 2. Pruefregel der Rolle wieder ohne admin2 (Stand vor v3.38).
BEGIN;
\echo '--- vorher: Konten je Rolle'
SELECT rolle, aktiv, count(*) FROM app_benutzer GROUP BY rolle, aktiv ORDER BY rolle, aktiv;
UPDATE app_benutzer SET rolle='benutzer', aktiv=false WHERE rolle='admin2';
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM app_benutzer WHERE rolle='admin2') THEN
    RAISE EXCEPTION 'Es gibt noch Konten mit rolle admin2.';
  END IF; END $$;
ALTER TABLE app_benutzer DROP CONSTRAINT app_benutzer_rolle_check;
ALTER TABLE app_benutzer ADD CONSTRAINT app_benutzer_rolle_check CHECK (rolle IN ('benutzer','admin','leser'));
\echo '--- nachher: Konten je Rolle'
SELECT rolle, aktiv, count(*) FROM app_benutzer GROUP BY rolle, aktiv ORDER BY rolle, aktiv;
\echo '--- nachher: Pruefregel'
SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='app_benutzer_rolle_check';
COMMIT;
