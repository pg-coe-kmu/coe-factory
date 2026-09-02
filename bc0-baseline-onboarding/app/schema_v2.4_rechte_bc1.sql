-- ============================================================================
-- schema_v2.4 — Rechte für BC1: REFERENCES erteilen, Doppelvergaben lösen
-- BC0 · Simeon Ehmer · 02.09.2026
-- ============================================================================
--
-- ANLASS
--   BC1 kann seine Profil-Tabelle nicht einspielen: Für die Fremdschlüssel
--   braucht `bc1_role` das Recht REFERENCES, und davon ist am 02.09.2026
--   **kein einziges** vergeben. Gemessen an information_schema — 50 Objekte
--   mit SELECT, null mit REFERENCES.
--
--   Zugleich hat `bc1_role` 48 Objekte DOPPELT: direkt und über die
--   Gruppenrolle `bc_leser`. Solange das so ist, steuert `bc_leser` die
--   Leserechte faktisch nicht — ein Entzug über die Gruppenrolle liefe ins
--   Leere, weil die direkte Vergabe daneben stehen bleibt.
--
-- WAS ES NICHT ANFASST
--   `ref_personen` und `prozess_personen`. Diese beiden hat `bc1_role` als
--   einzige NUR direkt, `bc_leser` hat sie nicht — das ist die
--   Pseudonymisierungsgrenze, und sie sitzt richtig. Der Entzug wäre hier
--   kein Aufräumen, sondern eine fachliche Änderung: Ohne `ref_personen`
--   könnte der BC1-Bot die befragte Person keiner P-ID zuordnen, und die
--   Spalte `bewerter` bliebe leer. Entschieden am 22.08.2026: Die Grenze
--   verläuft hinter BC1, nicht davor.
--
--   Der Block unten entzieht deshalb nur, was `bc_leser` nachweislich selbst
--   hat. Die beiden fallen dadurch von allein heraus — die Ausnahme ist eine
--   Folge der Regel, kein Sonderfall in einer Liste.
--
-- REIHENFOLGE
--   Erst prüfen, dann erteilen, dann entziehen. Ein Entzug vor der Prüfung
--   wäre die Wiederholung des Fehlers vom 27.08.: eine Einschränkung setzen,
--   ohne den Weg daneben zu kontrollieren.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 0. Vorbedingungen. Ohne sie richtet der Rest Schaden an.
-- ----------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc1_role') THEN
    RAISE EXCEPTION 'Rolle bc1_role fehlt.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    RAISE EXCEPTION 'Rolle bc_leser fehlt.';
  END IF;

  -- Der entscheidende Punkt: Ist bc1_role ueberhaupt Mitglied von bc_leser?
  -- Wenn nicht, naehme der Entzug unten BC1 saemtliche Leserechte auf einen
  -- Schlag. Lieber hier abbrechen als danach suchen.
  IF NOT EXISTS (
    SELECT 1 FROM pg_auth_members m
      JOIN pg_roles r ON r.oid = m.roleid
      JOIN pg_roles g ON g.oid = m.member
     WHERE r.rolname = 'bc_leser' AND g.rolname = 'bc1_role') THEN
    RAISE EXCEPTION
      'bc1_role ist nicht Mitglied von bc_leser. Der Entzug wuerde BC1 '
      'alle Leserechte nehmen. Erst: GRANT bc_leser TO bc1_role;';
  END IF;

  RAISE NOTICE 'Vorbedingungen erfuellt.';
END $$;

-- ----------------------------------------------------------------------------
-- 1. REFERENCES — das, was BC1 blockiert
-- ----------------------------------------------------------------------------
--   Gezielt auf die fuenf Zieltabellen der BC1-Fremdschluessel, nicht pauschal.
--   REFERENCES erlaubt Fremdschluessel und sonst nichts: kein Schreibrecht,
--   keine neuen Lesewege.
GRANT REFERENCES ON companies        TO bc1_role;
GRANT REFERENCES ON ref_prozesse     TO bc1_role;
GRANT REFERENCES ON ref_teilprozesse TO bc1_role;
GRANT REFERENCES ON mandant_rollen   TO bc1_role;
GRANT REFERENCES ON ref_erhebungen   TO bc1_role;

-- ----------------------------------------------------------------------------
-- 2. Doppelvergaben loesen
-- ----------------------------------------------------------------------------
--   Entzogen wird ausschliesslich, was bc_leser selbst besitzt. Damit
--   verliert bc1_role kein Recht — es kommt danach ueber die Gruppenrolle
--   statt zweimal.
DO $$
DECLARE
  r        RECORD;
  anzahl   INTEGER := 0;
BEGIN
  FOR r IN
    SELECT DISTINCT d.table_schema, d.table_name
      FROM information_schema.role_table_grants d
     WHERE d.grantee = 'bc1_role'
       AND d.privilege_type = 'SELECT'
       AND EXISTS (
             SELECT 1 FROM information_schema.role_table_grants g
              WHERE g.grantee = 'bc_leser'
                AND g.privilege_type = 'SELECT'
                AND g.table_schema = d.table_schema
                AND g.table_name   = d.table_name)
     ORDER BY 1, 2
  LOOP
    EXECUTE format('REVOKE SELECT ON %I.%I FROM bc1_role',
                   r.table_schema, r.table_name);
    anzahl := anzahl + 1;
  END LOOP;

  RAISE NOTICE 'Direkte SELECT-Rechte entzogen: % Objekte', anzahl;
END $$;

-- ----------------------------------------------------------------------------
-- 3. Gegenprobe im selben Vorgang
-- ----------------------------------------------------------------------------
DO $$
DECLARE
  n_ref     INTEGER;
  n_direkt  INTEGER;
  fehlend   TEXT;
BEGIN
  SELECT count(*) INTO n_ref
    FROM information_schema.role_table_grants
   WHERE grantee = 'bc1_role' AND privilege_type = 'REFERENCES';
  IF n_ref <> 5 THEN
    RAISE EXCEPTION 'REFERENCES: % statt 5 erwartet.', n_ref;
  END IF;

  -- Was bleibt direkt stehen, muss genau die Pseudonymisierungsgrenze sein.
  SELECT count(*), string_agg(DISTINCT table_name, ', ' ORDER BY table_name)
    INTO n_direkt, fehlend
    FROM information_schema.role_table_grants
   WHERE grantee = 'bc1_role' AND privilege_type = 'SELECT';
  RAISE NOTICE 'Direkt verbliebene SELECT-Rechte: % (%)', n_direkt, fehlend;

  IF fehlend IS DISTINCT FROM 'prozess_personen, ref_personen' THEN
    RAISE EXCEPTION
      'Erwartet waren genau prozess_personen und ref_personen, gefunden: %',
      coalesce(fehlend, '(keine)');
  END IF;

  RAISE NOTICE 'Alles wie erwartet.';
END $$;

COMMIT;

-- ============================================================================
-- Kontrolle nach dem Lauf
-- ============================================================================
SELECT privilege_type, count(*) AS objekte
  FROM information_schema.role_table_grants
 WHERE grantee = 'bc1_role'
 GROUP BY privilege_type
 ORDER BY 1;
