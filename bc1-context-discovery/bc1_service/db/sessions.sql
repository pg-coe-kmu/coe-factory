-- BC1 Etappe 1, Paket B1 — Sitzungszustand des Interviews: bc1.sessions.
-- Zweite Einspiel-Einheit neben prozessprofil.sql: gleiche Dreifallregel, EIGENE
-- Sollsignatur, Geltungsbereich genau diese eine Tabelle. prozessprofil.sql bleibt
-- unveraendert — seine Signatur ist auf die drei Vertragstabellen eingeschraenkt und
-- sieht diese Tabelle nicht (Entscheidung 13.09.2026, Abschlussplan B1).
--
-- Einspielen (EINE Transaktion, Rollback bei jedem Fehler), NACH prozessprofil.sql:
--     psql -v ON_ERROR_STOP=1 -1 -f sessions.sql
-- Die Datei enthaelt bewusst KEIN BEGIN/COMMIT.
--
-- Was hier NICHT geprueft wird und warum: Mitgliedschafts-Kanten ('mitglied|') und
-- Funktionen sind global bzw. gehoeren zu prozessprofil.sql, das im Betrieb immer
-- zuerst laeuft und beides prueft. Ein GRANT bc1_role TO <irgendwer> bricht also
-- dort ab, bevor diese Datei an der Reihe ist.
--
-- Aufbau: 0 Voraussetzungen | 0b Sollsignatur | 1 Vorpruefung | 2 Anlage + 3 Rechte | 4 Nachpruefung

-- ============================================================
-- 0a. DETERMINISMUS UND DEPLOYMENT-SPERRE (wie prozessprofil.sql)
-- ============================================================
SET LOCAL search_path = public, pg_temp;
SELECT pg_advisory_xact_lock(hashtext('bc1.sessions.einspielen'));

-- ============================================================
-- 0. VORAUSSETZUNGEN
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'bc1') THEN
        RAISE EXCEPTION 'Schema bc1 fehlt. BC0 legt es an (ROLLEN.md, Schritt 5).';
    END IF;
    IF NOT has_schema_privilege(current_user, 'bc1', 'CREATE') THEN
        RAISE EXCEPTION 'Rolle % darf im Schema bc1 nichts anlegen.', current_user;
    END IF;
    IF NOT has_table_privilege(current_user, 'companies', 'REFERENCES') THEN
        RAISE EXCEPTION 'GRANT REFERENCES fehlt auf companies (von BC0 am 02.09. erteilt).';
    END IF;
END $$;

-- ============================================================
-- 0b. SOLLSIGNATUR — Geltungsbereich: NUR bc1.sessions
-- ============================================================
-- Erfasst wie prozessprofil.sql: Spalten · Constraints · Indizes · Trigger (eigene
-- UND Aktivierungszustand der internen FK-Trigger) · Eigentuemer · Tabellen- und
-- Spaltenrechte · effektive Rechte ALLER Rollen · RLS, Policies, Regeln · Kommentar.
-- Temp-Objekte tragen den Praefix bc1_sessions_, damit beide Dateien auch in
-- derselben Session nacheinander laufen koennen.
CREATE TEMP TABLE bc1_sessions_soll_signatur (zeile text PRIMARY KEY) ON COMMIT DROP;

-- BEKANNTE UMGEBUNGSROLLEN — WORTGLEICH zu prozessprofil.sql (Klaerpunkt K-G,
-- gemessen 03.09.2026 in der Ziel-Supabase, EINSPIELEN.md Abschnitt 5). Ein Test
-- haelt beide Listen identisch (tests/test_ddl_sessions.py).
CREATE TEMP TABLE bc1_sessions_umgebungsrollen (rolname text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO pg_temp.bc1_sessions_umgebungsrollen (rolname) VALUES
    -- Keine Semikolons in diesen Begruendungen: der Test liest bis zum ersten Semikolon.
    ('postgres'),                 -- Supabase-Administration, dort KEIN Superuser,
                                  -- Mitglied von bc1_role und bc_leser
    ('supabase_read_only_user'),  -- Supabase-Lesekonto, kommt ueber pg_read_all_data
    ('supabase_etl_admin');       -- Supabase-ETL, kommt ueber pg_read_all_data

INSERT INTO pg_temp.bc1_sessions_soll_signatur (zeile) VALUES
-- << HIER die generierte Sollsignatur einsetzen (tests/db/signatur_erzeugen.py) >>
    ('acl|sessions|bc1_role|DELETE|f'),
    ('acl|sessions|bc1_role|INSERT|f'),
    ('acl|sessions|bc1_role|MAINTAIN|f'),
    ('acl|sessions|bc1_role|REFERENCES|f'),
    ('acl|sessions|bc1_role|SELECT|f'),
    ('acl|sessions|bc1_role|TRIGGER|f'),
    ('acl|sessions|bc1_role|TRUNCATE|f'),
    ('acl|sessions|bc1_role|UPDATE|f'),
    ('constraint|sessions|sessions_company_fk|FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE'),
    ('constraint|sessions|sessions_pkey|PRIMARY KEY (session_id)'),
    ('constraint|sessions|sessions_version_positiv|CHECK ((version >= 1))'),
    ('effektiv_spalte|sessions|bc1_role|INSERT'),
    ('effektiv_spalte|sessions|bc1_role|REFERENCES'),
    ('effektiv_spalte|sessions|bc1_role|SELECT'),
    ('effektiv_spalte|sessions|bc1_role|UPDATE'),
    ('effektiv|sessions|bc1_role|DELETE'),
    ('effektiv|sessions|bc1_role|INSERT'),
    ('effektiv|sessions|bc1_role|REFERENCES'),
    ('effektiv|sessions|bc1_role|SELECT'),
    ('effektiv|sessions|bc1_role|TRIGGER'),
    ('effektiv|sessions|bc1_role|TRUNCATE'),
    ('effektiv|sessions|bc1_role|UPDATE'),
    ('eigentuemer|sessions|bc1_role'),
    ('index|sessions|sessions_pkey|CREATE UNIQUE INDEX sessions_pkey ON bc1.sessions USING btree (session_id)'),
    ('kommentar|sessions|fa9b4c7aecb7751ee161ee80f797fb7e'),
    ('rls|sessions|f|f'),
    ('spalte|sessions|aktualisiert_am|timestamp with time zone|notnull|now()|-|-'),
    ('spalte|sessions|company_id|uuid|notnull||-|-'),
    ('spalte|sessions|session_id|text|notnull||-|-'),
    ('spalte|sessions|state|jsonb|notnull||-|-'),
    ('spalte|sessions|version|integer|notnull||-|-'),
    ('trigger_intern|sessions|sessions_company_fk|O');

CREATE OR REPLACE TEMP VIEW bc1_sessions_ist_signatur AS
SELECT format('spalte|%s|%s|%s|%s|%s|%s|%s', c.relname, a.attname,
              format_type(a.atttypid, a.atttypmod),
              CASE WHEN a.attnotnull THEN 'notnull' ELSE 'null' END,
              coalesce(pg_get_expr(d.adbin, d.adrelid), ''),
              coalesce(nullif(a.attidentity, ''), '-'),
              coalesce(nullif(a.attgenerated, ''), '-')) AS zeile
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND a.attnum > 0 AND NOT a.attisdropped
UNION ALL
SELECT format('constraint|%s|%s|%s', c.relname, con.conname,
              pg_get_constraintdef(con.oid))
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
SELECT format('index|%s|%s|%s', tablename, indexname, indexdef)
  FROM pg_indexes
 WHERE schemaname = 'bc1' AND tablename = 'sessions'
UNION ALL
SELECT format('trigger|%s|%s|%s|%s', c.relname, t.tgname,
              pg_get_triggerdef(t.oid), t.tgenabled)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND NOT t.tgisinternal
UNION ALL
-- Interne RI-Trigger: Name traegt OIDs, deshalb Schluessel = Constraint-Name;
-- der AKTIVIERUNGSZUSTAND gehoert in die Signatur (ein deaktivierter RI-Trigger
-- laesst die Constraint-Definition stehen und erzwingt den FK trotzdem nicht).
SELECT format('trigger_intern|%s|%s|%s', c.relname, con.conname, t.tgenabled)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_constraint con ON con.oid = t.tgconstraint
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND t.tgisinternal
UNION ALL
SELECT format('eigentuemer|%s|%s', c.relname, pg_get_userbyid(c.relowner))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
-- Gesetzte Rechte VOLLSTAENDIG: aclexplode listet JEDEN Grantee, auch PUBLIC.
SELECT format('acl|%s|%s|%s|%s', c.relname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(
      coalesce(c.relacl, acldefault('r', c.relowner))) AS acl
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
-- Spaltenrechte liegen in pg_attribute.attacl, nicht in relacl.
SELECT format('spalte_acl|%s|%s|%s|%s|%s', c.relname, a.attname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(a.attacl) AS acl
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND a.attnum > 0 AND NOT a.attisdropped AND a.attacl IS NOT NULL
UNION ALL
SELECT format('rls|%s|%s|%s', c.relname, c.relrowsecurity, c.relforcerowsecurity)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
SELECT format('policy|%s|%s|%s|%s', c.relname, pol.polname, pol.polcmd,
              coalesce(pg_get_expr(pol.polqual, pol.polrelid), '-'))
  FROM pg_policy pol
  JOIN pg_class c ON c.oid = pol.polrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
SELECT format('regel|%s|%s', c.relname, r.rulename)
  FROM pg_rewrite r
  JOIN pg_class c ON c.oid = r.ev_class
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
UNION ALL
SELECT format('kommentar|%s|%s', c.relname, md5(d.description))
  FROM pg_description d
  JOIN pg_class c ON c.oid = d.objoid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions' AND d.objsubid = 0
UNION ALL
-- EFFEKTIVE Sicht ueber ALLE Rollen; ausgenommen Superuser, pg_*-Systemrollen und
-- die drei Umgebungsrollen (wie prozessprofil.sql).
SELECT format('effektiv|%s|%s|%s', c.relname, r.rolname, priv)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace,
       pg_roles r,
       unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) AS priv
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND NOT r.rolsuper AND r.rolname NOT LIKE 'pg\_%'
   AND r.rolname NOT IN (SELECT rolname FROM pg_temp.bc1_sessions_umgebungsrollen)
   AND has_table_privilege(r.oid, c.oid, priv)
UNION ALL
SELECT format('effektiv_spalte|%s|%s|%s', c.relname, r.rolname, priv)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace,
       pg_roles r,
       unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']) AS priv
 WHERE n.nspname = 'bc1' AND c.relname = 'sessions'
   AND NOT r.rolsuper AND r.rolname NOT LIKE 'pg\_%'
   AND r.rolname NOT IN (SELECT rolname FROM pg_temp.bc1_sessions_umgebungsrollen)
   AND has_any_column_privilege(r.oid, c.oid, priv);

-- ============================================================
-- 1. VORPRUEFUNG — Dreifallregel, VOR jeder Aenderung
-- ============================================================
CREATE TEMP TABLE bc1_sessions_einspiel_modus (modus text NOT NULL) ON COMMIT DROP;

DO $$
DECLARE vorhanden integer; abweichung text;
BEGIN
    SELECT count(*) INTO vorhanden
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'bc1' AND c.relname = 'sessions';

    IF vorhanden = 0 THEN
        INSERT INTO pg_temp.bc1_sessions_einspiel_modus VALUES ('anlegen');
        RAISE NOTICE 'Fall 1: bc1.sessions nicht vorhanden — Anlage.';
        RETURN;
    END IF;

    -- Eine Sicht oder Sequenz dieses Namens ist ebenfalls Fall 3, keine Tabelle.
    IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'bc1' AND c.relname = 'sessions' AND c.relkind = 'r') THEN
        RAISE EXCEPTION 'Fall 3: bc1.sessions existiert, ist aber keine Tabelle. Abbruch OHNE Aenderung.';
    END IF;

    SELECT string_agg(zeile, E'\n' ORDER BY zeile) INTO abweichung FROM (
        SELECT format('  - fehlt:  %s', zeile) AS zeile
          FROM (SELECT zeile FROM bc1_sessions_soll_signatur
                EXCEPT SELECT zeile FROM bc1_sessions_ist_signatur) a
        UNION ALL
        SELECT format('  + zuviel: %s', zeile)
          FROM (SELECT zeile FROM bc1_sessions_ist_signatur
                EXCEPT SELECT zeile FROM bc1_sessions_soll_signatur) b) diff;

    IF abweichung IS NOT NULL THEN
        RAISE EXCEPTION E'Fall 3: Bestand weicht von der Sollsignatur ab. Abbruch OHNE Aenderung.\n%',
                        abweichung;
    END IF;
    INSERT INTO pg_temp.bc1_sessions_einspiel_modus VALUES ('noop');
    RAISE NOTICE 'Fall 2: Bestand ist identisch zur Sollsignatur — No-op.';
END $$;

-- ============================================================
-- 2. ANLAGE + 3. RECHTE — NUR im Fall 1
-- ============================================================
-- Nackte CREATEs ohne IF NOT EXISTS: im Fall 1 ist garantiert nichts da, ein
-- unerwarteter Restbestand soll zum Fehler werden statt zur stillen Ersetzung.
DO $einspielen$
BEGIN
    IF (SELECT modus FROM pg_temp.bc1_sessions_einspiel_modus) <> 'anlegen' THEN
        RAISE NOTICE 'Fall 2: Bestand identisch — es wird NICHTS ausgefuehrt.';
        RETURN;
    END IF;

    -- ---------- Abschnitt 2: Anlage ----------
    -- Schluessel session_id allein (wie profil_write_status, wie StateStore.load);
    -- company_id als Pflichtspalte mit Loeschkaskade: der Interview-Rohtext stirbt
    -- mit dem Mandanten (DSGVO). version >= 1 pinnt den Store-Vertrag (erster save
    -- schreibt 1). Kein Trigger: Sitzungen sind veraenderlich, der Store sperrt
    -- optimistisch per Compare-and-Swap auf version.
    EXECUTE $ddl$ CREATE TABLE bc1.sessions (
        session_id      text        NOT NULL,
        company_id      uuid        NOT NULL,
        version         integer     NOT NULL,
        state           jsonb       NOT NULL,
        aktualisiert_am timestamptz NOT NULL DEFAULT now(),

        CONSTRAINT sessions_pkey PRIMARY KEY (session_id),
        CONSTRAINT sessions_version_positiv CHECK (version >= 1),
        CONSTRAINT sessions_company_fk FOREIGN KEY (company_id)
            REFERENCES companies (company_id) ON DELETE CASCADE
    ) $ddl$;

    EXECUTE $ddl$ COMMENT ON TABLE bc1.sessions IS
        'Sitzungszustand des Interviews (Felder, Gespraechslog mit Rohtext, Antworten). '
        'Interne Tabelle: ausschliesslich bc1_role, ausdruecklich NICHT in der '
        'Fremdschema-Lesematrix (REVOKE in Abschnitt 3). Lebt und stirbt mit dem Mandanten.' $ddl$;

    -- ---------- Abschnitt 3: Rechte ----------
    -- bc1_role: alles. bc_leser (Gruppenrolle; BC2, BC3, BC4 lesen darueber): NICHTS —
    -- das REVOKE ist Pflicht, weil Umgebungen mit ALTER DEFAULT PRIVILEGES
    -- (Test-Geruest; die Supabase bis 08.09.) jede neue Tabelle sonst still oeffnen.
    EXECUTE $ddl$ REVOKE ALL ON bc1.sessions FROM PUBLIC $ddl$;
    EXECUTE $ddl$ GRANT SELECT, INSERT, UPDATE, DELETE ON bc1.sessions TO bc1_role $ddl$;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
        EXECUTE $ddl$ REVOKE ALL ON bc1.sessions FROM bc_leser $ddl$;
    END IF;
END
$einspielen$;

-- ============================================================
-- 4. NACHPRUEFUNG — der Bestand MUSS jetzt exakt der Sollsignatur entsprechen
-- ============================================================
DO $$
DECLARE abweichung text;
BEGIN
    IF (SELECT modus FROM pg_temp.bc1_sessions_einspiel_modus) <> 'anlegen' THEN
        RETURN;              -- Fall 2: die Vorpruefung hat schon verglichen
    END IF;
    SELECT string_agg(zeile, E'\n' ORDER BY zeile) INTO abweichung FROM (
        SELECT format('  - fehlt:  %s', zeile) AS zeile
          FROM (SELECT zeile FROM bc1_sessions_soll_signatur
                EXCEPT SELECT zeile FROM bc1_sessions_ist_signatur) a
        UNION ALL
        SELECT format('  + zuviel: %s', zeile)
          FROM (SELECT zeile FROM bc1_sessions_ist_signatur
                EXCEPT SELECT zeile FROM bc1_sessions_soll_signatur) b) diff;

    IF abweichung IS NOT NULL THEN
        RAISE EXCEPTION E'Nachpruefung fehlgeschlagen — Rollback.\n%', abweichung;
    END IF;
    RAISE NOTICE 'Sollsignatur bestaetigt.';
END $$;
