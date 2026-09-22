-- BC1 — Bestand nachziehen: Spalte step_frequency_per_year in bc1.prozessprofil (#255).
-- BC2 hat Frage D3 am 20.09.2026 gebunden (Vertrag 1.2, Invariante I8); lesen.sql
-- fragt die Spalte ab und brach am Bestand, weil der Wert nur im Profil-JSON lag.
--
-- Warum eine eigene Datei: prozessprofil.sql kennt nur Fall 1 (nichts da -> anlegen)
-- und Fall 2 (alles da und identisch -> No-op). Ein Bestand OHNE die Spalte waere
-- gegen die neue Sollsignatur Fall 3 = Abbruch. Diese Datei bringt den Bestand
-- vorwaerts; danach meldet prozessprofil.sql wieder Fall 2 — das ist der Nachweis
-- (Test: tests/test_ddl_d3_spalte.py). Gleiches Muster wie BC0s schema_v3.x-Dateien.
--
-- Einspielen (EINE Transaktion, Rollback bei jedem Fehler), VOR prozessprofil.sql:
--     psql -v ON_ERROR_STOP=1 -1 -f prozessprofil_d3.sql
-- Die Datei enthaelt bewusst KEIN BEGIN/COMMIT. Auf einer frischen DB ein No-op.
--
-- Vierfallregel dieser Datei:
--   M0  Tabelle fehlt                        -> No-op; prozessprofil.sql legt mit Spalte an
--   M1  Spalte fehlt, CHECK = alte Fassung   -> Spalte anlegen, CHECK erweitern, nachpruefen
--   M2  Spalte da,    CHECK = neue Fassung   -> No-op (schon migriert)
--   M3  alles andere                         -> Abbruch OHNE Aenderung (nichts erraten)

-- ============================================================
-- 0. DETERMINISMUS UND DEPLOYMENT-SPERRE (wie prozessprofil.sql)
-- ============================================================
SET LOCAL search_path = public, pg_temp;
SELECT pg_advisory_xact_lock(hashtext('bc1.prozessprofil.einspielen'));

-- ============================================================
-- 1. VORPRUEFUNG UND MIGRATION
-- ============================================================
DO $$
DECLARE
    -- Die beiden CHECK-Fassungen, wie pg_get_constraintdef sie ausgibt — woertlich
    -- aus den Sollsignaturen von prozessprofil.sql (Stand 136003e bzw. #255).
    check_alt constant text := 'CHECK ((((frequency_per_year IS NULL) OR ((frequency_per_year >= (0)::numeric) AND (frequency_per_year < ''Infinity''::numeric))) AND ((executions_per_run IS NULL) OR ((executions_per_run >= (0)::numeric) AND (executions_per_run < ''Infinity''::numeric))) AND ((total_duration_minutes IS NULL) OR ((total_duration_minutes >= (0)::numeric) AND (total_duration_minutes < ''Infinity''::numeric))) AND ((focus_step_duration_minutes IS NULL) OR ((focus_step_duration_minutes >= (0)::numeric) AND (focus_step_duration_minutes < ''Infinity''::numeric)))))';
    check_neu constant text := 'CHECK ((((frequency_per_year IS NULL) OR ((frequency_per_year >= (0)::numeric) AND (frequency_per_year < ''Infinity''::numeric))) AND ((step_frequency_per_year IS NULL) OR ((step_frequency_per_year >= (0)::numeric) AND (step_frequency_per_year < ''Infinity''::numeric))) AND ((executions_per_run IS NULL) OR ((executions_per_run >= (0)::numeric) AND (executions_per_run < ''Infinity''::numeric))) AND ((total_duration_minutes IS NULL) OR ((total_duration_minutes >= (0)::numeric) AND (total_duration_minutes < ''Infinity''::numeric))) AND ((focus_step_duration_minutes IS NULL) OR ((focus_step_duration_minutes >= (0)::numeric) AND (focus_step_duration_minutes < ''Infinity''::numeric)))))';
    tabelle_da boolean;
    spalte_da  boolean;
    check_ist  text;
BEGIN
    SELECT to_regclass('bc1.prozessprofil') IS NOT NULL INTO tabelle_da;
    IF NOT tabelle_da THEN
        RAISE NOTICE 'M0: bc1.prozessprofil fehlt — nichts zu migrieren. prozessprofil.sql legt mit Spalte an.';
        RETURN;
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
           AND a.attname = 'step_frequency_per_year' AND NOT a.attisdropped) INTO spalte_da;
    SELECT pg_get_constraintdef(con.oid) INTO check_ist
      FROM pg_constraint con
      JOIN pg_class c ON c.oid = con.conrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
       AND con.conname = 'prozessprofil_zahlen_wertebereich';

    IF spalte_da AND check_ist = check_neu THEN
        RAISE NOTICE 'M2: Spalte und CHECK bereits auf Stand #255 — No-op.';
        RETURN;
    END IF;

    IF NOT spalte_da AND check_ist = check_alt THEN
        RAISE NOTICE 'M1: Bestand ohne Spalte — Spalte anlegen und CHECK erweitern.';
        ALTER TABLE bc1.prozessprofil ADD COLUMN step_frequency_per_year numeric;
        ALTER TABLE bc1.prozessprofil DROP CONSTRAINT prozessprofil_zahlen_wertebereich;
        -- Wortgleich mit prozessprofil.sql; ADD CONSTRAINT validiert den Bestand
        -- (alle Zeilen NULL in der neuen Spalte -> geht durch).
        ALTER TABLE bc1.prozessprofil ADD CONSTRAINT prozessprofil_zahlen_wertebereich CHECK (
            (frequency_per_year IS NULL
                OR (frequency_per_year >= 0 AND frequency_per_year < 'Infinity'::numeric))
            AND (step_frequency_per_year IS NULL
                OR (step_frequency_per_year >= 0
                    AND step_frequency_per_year < 'Infinity'::numeric))
            AND (executions_per_run IS NULL
                OR (executions_per_run >= 0 AND executions_per_run < 'Infinity'::numeric))
            AND (total_duration_minutes IS NULL
                OR (total_duration_minutes >= 0 AND total_duration_minutes < 'Infinity'::numeric))
            AND (focus_step_duration_minutes IS NULL
                OR (focus_step_duration_minutes >= 0
                    AND focus_step_duration_minutes < 'Infinity'::numeric)));
        -- Nachpruefung in derselben Transaktion: der neue CHECK muss woertlich der
        -- Sollsignatur entsprechen, sonst Rollback — prozessprofil.sql waere sonst Fall 3.
        SELECT pg_get_constraintdef(con.oid) INTO check_ist
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND c.relname = 'prozessprofil'
           AND con.conname = 'prozessprofil_zahlen_wertebereich';
        IF check_ist IS DISTINCT FROM check_neu THEN
            RAISE EXCEPTION E'M1: Nachpruefung fehlgeschlagen — CHECK entspricht nicht der Sollsignatur. Rollback.\n  ist:  %\n  soll: %',
                            check_ist, check_neu;
        END IF;
        RAISE NOTICE 'M1: erledigt — prozessprofil.sql muss jetzt Fall 2 melden.';
        RETURN;
    END IF;

    RAISE EXCEPTION E'M3: unerwarteter Bestand — Spalte vorhanden: %, CHECK: %. Abbruch OHNE Aenderung.',
                    spalte_da, coalesce(check_ist, '<fehlt>');
END $$;
