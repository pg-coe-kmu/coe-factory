-- BC1 — Bestand nachziehen: Spalte anfrage_id in bc1.prozessprofil (B5, 05.10.2026).
-- BC1 interviewt nur noch zu einer BC0-Anfrage; das Profil traegt deren Nummer.
--
-- Warum eine eigene Datei: wie prozessprofil_d3.sql — ein Bestand OHNE die Spalte waere
-- gegen die neue Sollsignatur Fall 3. Danach meldet prozessprofil.sql wieder Fall 2
-- (Test: tests/test_ddl_b5_spalte.py).
--
-- Einspielen (EINE Transaktion), NACH prozessprofil_d3.sql und VOR prozessprofil.sql:
--     psql -v ON_ERROR_STOP=1 -1 -f prozessprofil_d3.sql -f prozessprofil_b5.sql -f prozessprofil.sql
-- Kein BEGIN/COMMIT. Auf einer frischen DB ein No-op.
--
-- Vierfallregel:
--   M0  Tabelle fehlt                 -> No-op; prozessprofil.sql legt mit Spalte an
--   M1  Spalte fehlt, CHECK fehlt     -> Spalte + CHECK anlegen, nachpruefen
--   M2  Spalte da,    CHECK = Soll    -> No-op
--   M3  alles andere                  -> Abbruch OHNE Aenderung
-- Keine Datenvorbedingung: die Spalte ist neu und leer; Bestandszeilen bleiben NULL.

SET LOCAL search_path = public, pg_temp;
SELECT pg_advisory_xact_lock(hashtext('bc1.prozessprofil.einspielen'));

DO $$
DECLARE
    -- Woertlich die Ausgabe von pg_get_constraintdef auf PG 17 (Step 4 gemessen).
    check_soll constant text := 'CHECK (((anfrage_id IS NULL) OR (anfrage_id ~ ''^A-[0-9]{4}-[0-9]{2}$''::text)))';
    tabelle_da boolean;
    spalte_da  boolean;
    check_ist  text;
BEGIN
    SELECT to_regclass('bc1.prozessprofil') IS NOT NULL INTO tabelle_da;
    IF NOT tabelle_da THEN
        RAISE NOTICE 'M0: bc1.prozessprofil fehlt — nichts zu migrieren.';
        RETURN;
    END IF;
    SELECT EXISTS (
        SELECT 1 FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
           AND a.attname = 'anfrage_id' AND NOT a.attisdropped) INTO spalte_da;
    SELECT pg_get_constraintdef(con.oid) INTO check_ist
      FROM pg_constraint con
      JOIN pg_class c ON c.oid = con.conrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
       AND con.conname = 'prozessprofil_anfrage_format';

    IF spalte_da AND check_ist = check_soll THEN
        RAISE NOTICE 'M2: Spalte und CHECK bereits auf Stand B5 — No-op.';
        RETURN;
    END IF;
    IF NOT spalte_da AND check_ist IS NULL THEN
        RAISE NOTICE 'M1: Bestand ohne Spalte — anfrage_id anlegen.';
        ALTER TABLE bc1.prozessprofil ADD COLUMN anfrage_id text;
        ALTER TABLE bc1.prozessprofil ADD CONSTRAINT prozessprofil_anfrage_format
            CHECK (anfrage_id IS NULL OR anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}$');
        SELECT pg_get_constraintdef(con.oid) INTO check_ist
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
           AND con.conname = 'prozessprofil_anfrage_format';
        IF check_ist IS DISTINCT FROM check_soll THEN
            RAISE EXCEPTION E'M1: Nachpruefung fehlgeschlagen — CHECK weicht ab. Rollback.\n  ist:  %\n  soll: %',
                            check_ist, check_soll;
        END IF;
        RAISE NOTICE 'M1: erledigt — prozessprofil.sql muss jetzt Fall 2 melden.';
        RETURN;
    END IF;
    RAISE EXCEPTION E'M3: unerwarteter Bestand — Spalte vorhanden: %, CHECK: %. Abbruch OHNE Aenderung.',
                    spalte_da, coalesce(check_ist, '<fehlt>');
END $$;
