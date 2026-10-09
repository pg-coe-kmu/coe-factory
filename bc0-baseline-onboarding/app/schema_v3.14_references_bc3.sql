-- ============================================================================
-- schema_v3.14 — Rechte für BC3: REFERENCES auf companies, ref_prozesse,
--                ref_teilprozesse (Issue #279)
-- BC0 · Simeon Ehmer · 08.10.2026
-- ============================================================================
--
-- ANLASS
--   BC3 hat bc3.lieferungen angelegt (ADR-003 Regel 3: jeder BC schreibt in
--   eigene Tabellen). Die Tabelle soll per Fremdschluessel auf BC0 verweisen:
--     (company_id)                 -> companies
--     (company_id, process_id)     -> ref_prozesse
--     (company_id, sub_process_id) -> ref_teilprozesse
--   Beim Anlegen kam "permission denied for table companies": bc3_role hat
--   kein REFERENCES. Das blockiert BC3 beim Rueckschreiben der Lieferungen
--   (Slicer nach Gate 2).
--
-- ENTSCHEIDUNG (Simeon, 08.10.2026): Weg 1 aus #279.
--   BC0 erteilt das Recht, BC3 legt die Fremdschluessel auf seiner Tabelle
--   selbst an. Vorbild: schema_v2.4 fuer bc1_role. Die Tabelle bleibt damit
--   in BC3s Hand, BC0 aendert nur Rechte.
--
-- WAS REFERENCES ERLAUBT — und was nicht
--   Nur Fremdschluessel auf diese drei Tabellen. Kein Lesen, kein Schreiben,
--   kein Loeschen. Eine Nebenwirkung, die man kennen muss: Solange eine
--   bc3.lieferungen-Zeile auf einen Prozess verweist, laesst sich dieser
--   Prozess nicht loeschen (bei ON DELETE RESTRICT/NO ACTION). Prozesse werden
--   bei BC0 ohnehin stillgelegt statt geloescht (stilllegen_statt_loeschen);
--   beim Mandanten entscheidet BC3s ON DELETE-Klausel, ob die Loeschkaskade
--   (DSGVO) durchlaeuft — Empfehlung an BC3: ON DELETE CASCADE auf companies.
--
-- WAS ES NICHT ANFASST
--   bc2_role und bc4_role (Rest von ToDo 121). Erst wenn sie es brauchen.
--
-- Ausfuehren als postgres, eine Transaktion.
-- ============================================================================

BEGIN;

-- 0. Vorbedingungen
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc3_role') THEN
    RAISE EXCEPTION 'Rolle bc3_role fehlt.';
  END IF;
  IF to_regclass('public.companies') IS NULL
     OR to_regclass('public.ref_prozesse') IS NULL
     OR to_regclass('public.ref_teilprozesse') IS NULL THEN
    RAISE EXCEPTION 'Eine der Zieltabellen fehlt (companies, ref_prozesse, ref_teilprozesse).';
  END IF;
END $$;

-- 1. REFERENCES — gezielt auf die drei Zieltabellen, nicht pauschal
GRANT REFERENCES ON companies        TO bc3_role;
GRANT REFERENCES ON ref_prozesse     TO bc3_role;
GRANT REFERENCES ON ref_teilprozesse TO bc3_role;

-- 2. Gegenprobe im selben Vorgang: genau diese drei BC0-Tabellen, nicht mehr.
--    (Erster Lauf in Produktion 08.10.2026 brach hier ab: die Probe zaehlte
--    bc3.lieferungen mit — Eigentuemerrecht, kein Grant. Nichts war geaendert.)
DO $$
DECLARE
  liste TEXT;
BEGIN
  SELECT string_agg(table_name, ', ' ORDER BY table_name) INTO liste
    FROM information_schema.role_table_grants
   WHERE grantee = 'bc3_role' AND privilege_type = 'REFERENCES'
     AND table_schema = 'public';   -- nur BC0-Tabellen: auf die eigenen (bc3.*) hat
                                    -- bc3_role als Eigentuemer REFERENCES ohnehin
  IF liste IS DISTINCT FROM 'companies, ref_prozesse, ref_teilprozesse' THEN
    RAISE EXCEPTION 'REFERENCES fuer bc3_role: erwartet companies, ref_prozesse, '
                    'ref_teilprozesse — gefunden: %', coalesce(liste, '(keine)');
  END IF;
  RAISE NOTICE 'bc3_role: REFERENCES auf %', liste;
END $$;

COMMIT;

-- ----------------------------------------------------------------------------
-- Gegenprobe nach dem Einspielen (ERWARTET: drei Zeilen, alle t)
--   SELECT t, has_table_privilege('bc3_role', t, 'REFERENCES')
--     FROM unnest(ARRAY['companies','ref_prozesse','ref_teilprozesse']) t;
--
-- Nachdem BC3 die Fremdschluessel gesetzt hat (ERWARTET: drei Zeilen):
--   SELECT conname, pg_get_constraintdef(oid)
--     FROM pg_constraint
--    WHERE conrelid = 'bc3.lieferungen'::regclass AND contype = 'f'
--    ORDER BY conname;
-- ----------------------------------------------------------------------------
