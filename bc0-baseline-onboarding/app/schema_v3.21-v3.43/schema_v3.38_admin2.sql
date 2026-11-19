-- BC0 · Schema v3.38 — Rolle admin2 zulassen (10.11.2026)
-- Anlass: BC0 10.11.: statt Klon bc0-4 ein zweiter Admin, der nur Mandantendaten,
-- HitL Gate 0 / Uebergabe Gate 0 (ohne Verlauf ueber die BCs) und KI-Reifegrad sieht,
-- lesen und aendern darf.
-- Aenderung: nur die Pruefregel der Spalte app_benutzer.rolle wird um 'admin2' erweitert.
-- Keine Daten werden geaendert, kein Benutzer angelegt. Eine Transaktion.
BEGIN;
\echo '--- vorher: Pruefregeln auf app_benutzer'
SELECT conname, pg_get_constraintdef(oid) AS regel
  FROM pg_constraint WHERE conrelid = 'app_benutzer'::regclass AND contype = 'c' ORDER BY conname;
DO $$
DECLARE r record; n int := 0;
BEGIN
  FOR r IN SELECT conname FROM pg_constraint
            WHERE conrelid = 'app_benutzer'::regclass AND contype = 'c'
              AND pg_get_constraintdef(oid) ILIKE '%rolle%'
  LOOP
    EXECUTE format('ALTER TABLE app_benutzer DROP CONSTRAINT %I', r.conname); n := n + 1;
  END LOOP;
  IF n <> 1 THEN RAISE EXCEPTION 'Erwartet genau 1 Pruefregel auf rolle, gefunden: %', n; END IF;
END $$;
ALTER TABLE app_benutzer ADD CONSTRAINT app_benutzer_rolle_check
  CHECK (rolle IN ('benutzer','admin','leser','admin2'));
\echo '--- nachher: Pruefregeln auf app_benutzer (ERWARTET: rolle IN benutzer, admin, leser, admin2)'
SELECT conname, pg_get_constraintdef(oid) AS regel
  FROM pg_constraint WHERE conrelid = 'app_benutzer'::regclass AND contype = 'c' ORDER BY conname;
\echo '--- Bestand der Rollen (unveraendert, nur Anzahl)'
SELECT rolle, count(*) AS konten FROM app_benutzer GROUP BY rolle ORDER BY rolle;
COMMIT;
