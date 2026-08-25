-- BC1 Etappe 1 — Profil-Fundament. Zielstruktur nach Brief BC1->BC0 vom 22.08.
-- (Abschnitte 2 + 3) und BC0-Antwort vom 23.08. (Abschnitt 1).
--
-- Einspielen (EINE Transaktion, Rollback bei jedem Fehler):
--     psql -v ON_ERROR_STOP=1 -1 -f prozessprofil.sql
-- Die Datei enthaelt bewusst KEIN BEGIN/COMMIT.
--
-- Aufbau: 0 Voraussetzungen | 1 Vorpruefung (Task 4) | 2 Anlage
--         3 Rechte (Task 4)  | 4 Nachpruefung (Task 4)

-- ============================================================
-- 0a. DETERMINISMUS UND DEPLOYMENT-SPERRE
-- ============================================================
-- Deterministischer Suchpfad (Codex N10-I6): ohne ihn koennen die pg_get_*def-
-- Ausgaben je nach search_path unterschiedlich qualifiziert sein — die Signatur
-- meldete dann Fall 3 ohne echten Unterschied. pg_temp steht bewusst HINTEN:
-- sonst koennte eine gleichnamige TEMP-Tabelle eine BC0-Tabelle beschatten.
-- Muss VOR Abschnitt 0 stehen, weil has_table_privilege(current_user, 'companies',
-- ...) den Suchpfad benutzt. SET LOCAL gilt nur fuer diese Transaktion.
SET LOCAL search_path = public, pg_temp;

-- Deployment-Sperre (Codex N10-I5): serialisiert zwei GLEICHZEITIGE Einspielungen
-- dieser Datei — sonst koennte zwischen Vorpruefung und Commit ein zweiter Lauf
-- dazwischenfunken. Sie schuetzt AUSDRUECKLICH NICHT gegen fremde, manuelle DDL
-- waehrend des Laufs; dass waehrend des Einspielens niemand von Hand am Schema
-- arbeitet, bleibt eine Betriebsannahme (gehoert in SMOKE.md, Task 16).
SELECT pg_advisory_xact_lock(hashtext('bc1.prozessprofil.einspielen'));

-- ============================================================
-- 0. VORAUSSETZUNGEN — lieber eine klare Ansage als "permission denied"
-- ============================================================
DO $$
DECLARE fehlend text[] := '{}';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'bc1') THEN
        RAISE EXCEPTION 'Schema bc1 fehlt. BC0 legt es an (ROLLEN.md, Schritt 5).';
    END IF;
    IF NOT has_schema_privilege(current_user, 'bc1', 'CREATE') THEN
        RAISE EXCEPTION 'Rolle % darf im Schema bc1 nichts anlegen.', current_user;
    END IF;

    SELECT array_agg(t) INTO fehlend FROM unnest(ARRAY[
        'companies', 'ref_prozesse', 'ref_teilprozesse', 'mandant_rollen', 'ref_erhebungen'
    ]) AS t WHERE NOT has_table_privilege(current_user, t, 'REFERENCES');
    IF fehlend IS NOT NULL THEN
        RAISE EXCEPTION 'GRANT REFERENCES fehlt auf: %. Das ist das GRANT-Signal an BC0 '
                        '(Buendel-Frage #3).', array_to_string(fehlend, ', ');
    END IF;

    SELECT array_agg(t) INTO fehlend FROM unnest(ARRAY[
        'v_bewertung_aktuell', 'mandant_systeme', 'ref_teilprozesse', 'companies',
        'v_prozesse_lesen'
    ]) AS t WHERE NOT has_table_privilege(current_user, t, 'SELECT');
    IF fehlend IS NOT NULL THEN
        RAISE EXCEPTION 'GRANT SELECT fehlt auf: %.', array_to_string(fehlend, ', ');
    END IF;
END $$;

-- ============================================================
-- 0b. SOLLSIGNATUR — was "identisch" bedeutet (Spec K1, Geltungsbereich: NUR bc1)
-- ============================================================
-- Erfasst alle semantisch wirksamen Definitionen unserer drei Vertragstabellen:
-- Spalten (Typ, Nullability, Default) · Constraints (inkl. CHECK-Ausdruck und
-- FK-Aktionen inkl. DEFERRABLE-Modus) · Indizes (inkl. Partialpraedikat) ·
-- Trigger (eigene UND Aktivierungszustand der internen) · Trigger-Funktionsrumpf ·
-- Eigentuemer · Tabellen- UND Spaltenrechte · effektive Rechte ALLER Rollen ·
-- Mitgliedschaften in bc1_role · RLS, Policies, Regeln · Tabellenkommentare.
-- Rechte auf BC0-Tabellen sind ausdruecklich NICHT Teil der Signatur — die vergibt
-- BC0; sonst haenge unser No-op-Fall an fremden Aenderungen.
-- Kein vorheriges DROP (Codex R2-N-C3): ein unqualifiziertes
-- 'DROP TABLE IF EXISTS bc1_soll_signatur' koennte eine gleichnamige PERMANENTE
-- Tabelle aus dem Suchpfad loeschen — also eine Aenderung VOR der Pruefung, genau
-- das, was die Dreifallregel verbietet.
-- Lebensdauer: die beiden TEMP-TABELLEN verschwinden mit dem Commit
-- (ON COMMIT DROP), die TEMP VIEW erst mit der Session — Views kennen kein
-- ON COMMIT DROP. Deshalb OR REPLACE (Codex N10-I4): ohne das scheiterte ein
-- zweiter Lauf in DERSELBEN Session an 'relation already exists'.
CREATE TEMP TABLE bc1_soll_signatur (zeile text PRIMARY KEY) ON COMMIT DROP;

INSERT INTO pg_temp.bc1_soll_signatur (zeile) VALUES
-- << HIER die generierte Sollsignatur einsetzen (Step 7) >>
    ('acl|profil_rollen|bc1_role|DELETE|f'),
    ('acl|profil_rollen|bc1_role|INSERT|f'),
    ('acl|profil_rollen|bc1_role|REFERENCES|f'),
    ('acl|profil_rollen|bc1_role|SELECT|f'),
    ('acl|profil_rollen|bc1_role|TRIGGER|f'),
    ('acl|profil_rollen|bc1_role|TRUNCATE|f'),
    ('acl|profil_rollen|bc1_role|UPDATE|f'),
    ('acl|profil_write_status|bc1_role|DELETE|f'),
    ('acl|profil_write_status|bc1_role|INSERT|f'),
    ('acl|profil_write_status|bc1_role|REFERENCES|f'),
    ('acl|profil_write_status|bc1_role|SELECT|f'),
    ('acl|profil_write_status|bc1_role|TRIGGER|f'),
    ('acl|profil_write_status|bc1_role|TRUNCATE|f'),
    ('acl|profil_write_status|bc1_role|UPDATE|f'),
    ('acl|prozessprofil|bc1_role|DELETE|f'),
    ('acl|prozessprofil|bc1_role|INSERT|f'),
    ('acl|prozessprofil|bc1_role|REFERENCES|f'),
    ('acl|prozessprofil|bc1_role|SELECT|f'),
    ('acl|prozessprofil|bc1_role|TRIGGER|f'),
    ('acl|prozessprofil|bc1_role|TRUNCATE|f'),
    ('acl|prozessprofil|bc1_role|UPDATE|f'),
    ('constraint|profil_rollen|profil_rollen_genau_eine_quelle|CHECK (((rolle_id IS NOT NULL) <> (btrim(COALESCE(rolle_freitext, ''''::text)) <> ''''::text)))'),
    ('constraint|profil_rollen|profil_rollen_pkey|PRIMARY KEY (company_id, focus_step_id, profil_version, pos)'),
    ('constraint|profil_rollen|profil_rollen_pos_positiv|CHECK ((pos > 0))'),
    ('constraint|profil_rollen|profil_rollen_profil_fk|FOREIGN KEY (company_id, focus_step_id, profil_version) REFERENCES bc1.prozessprofil(company_id, focus_step_id, profil_version) ON DELETE CASCADE'),
    ('constraint|profil_rollen|profil_rollen_rolle_fk|FOREIGN KEY (company_id, rolle_id) REFERENCES mandant_rollen(company_id, rolle_id) DEFERRABLE INITIALLY DEFERRED'),
    ('constraint|profil_rollen|profil_rollen_zeitanteil_bereich|CHECK (((zeitanteil_pct IS NULL) OR ((zeitanteil_pct >= 0) AND (zeitanteil_pct <= 100))))'),
    ('constraint|profil_write_status|profil_write_status_je_zeile|UNIQUE (company_id, focus_step_id, profil_version)'),
    ('constraint|profil_write_status|profil_write_status_pkey|PRIMARY KEY (session_id)'),
    ('constraint|profil_write_status|profil_write_status_profil_fk|FOREIGN KEY (company_id, focus_step_id, profil_version) REFERENCES bc1.prozessprofil(company_id, focus_step_id, profil_version) ON DELETE CASCADE'),
    ('constraint|prozessprofil|prozessprofil_company_fk|FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE'),
    ('constraint|prozessprofil|prozessprofil_confidence_bereich|CHECK (((focus_step_duration_confidence_pct IS NULL) OR ((focus_step_duration_confidence_pct >= 0) AND (focus_step_duration_confidence_pct <= 100))))'),
    ('constraint|prozessprofil|prozessprofil_downstream_fk|FOREIGN KEY (company_id, downstream_process_id) REFERENCES ref_prozesse(company_id, process_id)'),
    ('constraint|prozessprofil|prozessprofil_downstream_kein_selbstbezug|CHECK (((downstream_process_id IS NULL) OR ((downstream_process_id)::text <> (process_id)::text)))'),
    ('constraint|prozessprofil|prozessprofil_duration_source_werte|CHECK (((focus_step_duration_source IS NULL) OR (focus_step_duration_source = ANY (ARRAY[''gemessen''::text, ''geschaetzt''::text, ''aus_system''::text]))))'),
    ('constraint|prozessprofil|prozessprofil_erhebung_fk|FOREIGN KEY (company_id, erhebung_id) REFERENCES ref_erhebungen(company_id, erhebung_id)'),
    ('constraint|prozessprofil|prozessprofil_focus_step_muster|CHECK (((focus_step_id)::text ~ ''^KP-[0-9]{2}\.TP-[0-9]+$''::text))'),
    ('constraint|prozessprofil|prozessprofil_owner_rolle_fk|FOREIGN KEY (company_id, process_owner_rolle_id) REFERENCES mandant_rollen(company_id, rolle_id)'),
    ('constraint|prozessprofil|prozessprofil_pkey|PRIMARY KEY (company_id, focus_step_id, profil_version)'),
    ('constraint|prozessprofil|prozessprofil_process_muster|CHECK (((process_id)::text ~ ''^KP-[0-9]{2}$''::text))'),
    ('constraint|prozessprofil|prozessprofil_prozess_fk|FOREIGN KEY (company_id, process_id) REFERENCES ref_prozesse(company_id, process_id)'),
    ('constraint|prozessprofil|prozessprofil_status_werte|CHECK ((status = ANY (ARRAY[''in_erhebung''::text, ''fertig''::text])))'),
    ('constraint|prozessprofil|prozessprofil_teilprozess_fk|FOREIGN KEY (company_id, focus_step_id) REFERENCES ref_teilprozesse(company_id, sub_process_id)'),
    ('constraint|prozessprofil|prozessprofil_tp_gehoert_zu_kp|CHECK (((focus_step_id)::text ~~ ((process_id)::text || ''.%''::text)))'),
    ('constraint|prozessprofil|prozessprofil_upstream_fk|FOREIGN KEY (company_id, upstream_process_id) REFERENCES ref_prozesse(company_id, process_id)'),
    ('constraint|prozessprofil|prozessprofil_upstream_kein_selbstbezug|CHECK (((upstream_process_id IS NULL) OR ((upstream_process_id)::text <> (process_id)::text)))'),
    ('constraint|prozessprofil|prozessprofil_version_positiv|CHECK ((profil_version >= 1))'),
    ('constraint|prozessprofil|prozessprofil_zahlen_wertebereich|CHECK ((((frequency_per_year IS NULL) OR ((frequency_per_year >= (0)::numeric) AND (frequency_per_year < ''Infinity''::numeric))) AND ((executions_per_run IS NULL) OR ((executions_per_run >= (0)::numeric) AND (executions_per_run < ''Infinity''::numeric))) AND ((total_duration_minutes IS NULL) OR ((total_duration_minutes >= (0)::numeric) AND (total_duration_minutes < ''Infinity''::numeric))) AND ((focus_step_duration_minutes IS NULL) OR ((focus_step_duration_minutes >= (0)::numeric) AND (focus_step_duration_minutes < ''Infinity''::numeric)))))'),
    ('effektiv_spalte|profil_rollen|bc1_role|INSERT'),
    ('effektiv_spalte|profil_rollen|bc1_role|REFERENCES'),
    ('effektiv_spalte|profil_rollen|bc1_role|SELECT'),
    ('effektiv_spalte|profil_rollen|bc1_role|UPDATE'),
    ('effektiv_spalte|profil_write_status|bc1_role|INSERT'),
    ('effektiv_spalte|profil_write_status|bc1_role|REFERENCES'),
    ('effektiv_spalte|profil_write_status|bc1_role|SELECT'),
    ('effektiv_spalte|profil_write_status|bc1_role|UPDATE'),
    ('effektiv_spalte|prozessprofil|bc1_role|INSERT'),
    ('effektiv_spalte|prozessprofil|bc1_role|REFERENCES'),
    ('effektiv_spalte|prozessprofil|bc1_role|SELECT'),
    ('effektiv_spalte|prozessprofil|bc1_role|UPDATE'),
    ('effektiv|profil_rollen|bc1_role|DELETE'),
    ('effektiv|profil_rollen|bc1_role|INSERT'),
    ('effektiv|profil_rollen|bc1_role|REFERENCES'),
    ('effektiv|profil_rollen|bc1_role|SELECT'),
    ('effektiv|profil_rollen|bc1_role|TRIGGER'),
    ('effektiv|profil_rollen|bc1_role|TRUNCATE'),
    ('effektiv|profil_rollen|bc1_role|UPDATE'),
    ('effektiv|profil_write_status|bc1_role|DELETE'),
    ('effektiv|profil_write_status|bc1_role|INSERT'),
    ('effektiv|profil_write_status|bc1_role|REFERENCES'),
    ('effektiv|profil_write_status|bc1_role|SELECT'),
    ('effektiv|profil_write_status|bc1_role|TRIGGER'),
    ('effektiv|profil_write_status|bc1_role|TRUNCATE'),
    ('effektiv|profil_write_status|bc1_role|UPDATE'),
    ('effektiv|prozessprofil|bc1_role|DELETE'),
    ('effektiv|prozessprofil|bc1_role|INSERT'),
    ('effektiv|prozessprofil|bc1_role|REFERENCES'),
    ('effektiv|prozessprofil|bc1_role|SELECT'),
    ('effektiv|prozessprofil|bc1_role|TRIGGER'),
    ('effektiv|prozessprofil|bc1_role|TRUNCATE'),
    ('effektiv|prozessprofil|bc1_role|UPDATE'),
    ('eigentuemer|profil_rollen|bc1_role'),
    ('eigentuemer|profil_write_status|bc1_role'),
    ('eigentuemer|prozessprofil|bc1_role'),
    ('funktion_acl|tf_freeze_profil|PUBLIC|EXECUTE|f'),
    ('funktion_acl|tf_freeze_profil|bc1_role|EXECUTE|f'),
    ('funktion_acl|tf_freeze_rollen|PUBLIC|EXECUTE|f'),
    ('funktion_acl|tf_freeze_rollen|bc1_role|EXECUTE|f'),
    ('funktion_acl|tf_version_vergeben|PUBLIC|EXECUTE|f'),
    ('funktion_acl|tf_version_vergeben|bc1_role|EXECUTE|f'),
    ('funktion|tf_freeze_profil()->trigger|plpgsql|f|f|f|v|f|f|u|bc1_role|-|1bd26ac612f96c378e8fce272e28a910'),
    ('funktion|tf_freeze_rollen()->trigger|plpgsql|f|f|f|v|f|f|u|bc1_role|-|71919b4ea68bd801864cfa538cf915d9'),
    ('funktion|tf_version_vergeben()->trigger|plpgsql|f|f|f|v|f|f|u|bc1_role|-|abcc553e45c07ae889282c4c2bdb7b81'),
    ('index|profil_rollen|profil_rollen_pkey|CREATE UNIQUE INDEX profil_rollen_pkey ON bc1.profil_rollen USING btree (company_id, focus_step_id, profil_version, pos)'),
    ('index|profil_rollen|profil_rollen_rolle_einmalig|CREATE UNIQUE INDEX profil_rollen_rolle_einmalig ON bc1.profil_rollen USING btree (company_id, focus_step_id, profil_version, rolle_id) WHERE (rolle_id IS NOT NULL)'),
    ('index|profil_write_status|profil_write_status_je_zeile|CREATE UNIQUE INDEX profil_write_status_je_zeile ON bc1.profil_write_status USING btree (company_id, focus_step_id, profil_version)'),
    ('index|profil_write_status|profil_write_status_pkey|CREATE UNIQUE INDEX profil_write_status_pkey ON bc1.profil_write_status USING btree (session_id)'),
    ('index|prozessprofil|prozessprofil_hoechstens_ein_draft|CREATE UNIQUE INDEX prozessprofil_hoechstens_ein_draft ON bc1.prozessprofil USING btree (company_id, focus_step_id) WHERE (status = ''in_erhebung''::text)'),
    ('index|prozessprofil|prozessprofil_pkey|CREATE UNIQUE INDEX prozessprofil_pkey ON bc1.prozessprofil USING btree (company_id, focus_step_id, profil_version)'),
    ('kommentar|profil_rollen|1378f4711b6e6f58a59cffb1b7392dd3'),
    ('kommentar|profil_write_status|75c6e87e6d74711c6b16fd790e298dee'),
    ('kommentar|prozessprofil|6be0061585449300b03b396462ce68c5'),
    ('rls|profil_rollen|f|f'),
    ('rls|profil_write_status|f|f'),
    ('rls|prozessprofil|f|f'),
    ('spalte|profil_rollen|company_id|uuid|notnull||-|-'),
    ('spalte|profil_rollen|focus_step_id|character varying(16)|notnull||-|-'),
    ('spalte|profil_rollen|pos|smallint|notnull||-|-'),
    ('spalte|profil_rollen|profil_version|integer|notnull||-|-'),
    ('spalte|profil_rollen|rolle_freitext|text|null||-|-'),
    ('spalte|profil_rollen|rolle_id|text|null||-|-'),
    ('spalte|profil_rollen|zeitanteil_pct|integer|null||-|-'),
    ('spalte|profil_write_status|company_id|uuid|notnull||-|-'),
    ('spalte|profil_write_status|erstellt_am|timestamp with time zone|notnull|now()|-|-'),
    ('spalte|profil_write_status|focus_step_id|character varying(16)|notnull||-|-'),
    ('spalte|profil_write_status|profil_version|integer|notnull||-|-'),
    ('spalte|profil_write_status|session_id|text|notnull||-|-'),
    ('spalte|prozessprofil|aktualisiert_am|timestamp with time zone|notnull|now()|-|-'),
    ('spalte|prozessprofil|company_id|uuid|notnull||-|-'),
    ('spalte|prozessprofil|downstream_process_id|character varying(8)|null||-|-'),
    ('spalte|prozessprofil|erhebung_id|text|notnull||-|-'),
    ('spalte|prozessprofil|erstellt_am|timestamp with time zone|notnull|now()|-|-'),
    ('spalte|prozessprofil|executions_per_run|numeric|null||-|-'),
    ('spalte|prozessprofil|focus_step_duration_confidence_pct|integer|null||-|-'),
    ('spalte|prozessprofil|focus_step_duration_minutes|numeric|null||-|-'),
    ('spalte|prozessprofil|focus_step_duration_source|text|null||-|-'),
    ('spalte|prozessprofil|focus_step_id|character varying(16)|notnull||-|-'),
    ('spalte|prozessprofil|frequency_per_year|numeric|null||-|-'),
    ('spalte|prozessprofil|paket_version|text|notnull||-|-'),
    ('spalte|prozessprofil|process_id|character varying(8)|notnull||-|-'),
    ('spalte|prozessprofil|process_owner_rolle_id|text|null||-|-'),
    ('spalte|prozessprofil|profil_version|integer|notnull||-|-'),
    ('spalte|prozessprofil|profil|jsonb|notnull||-|-'),
    ('spalte|prozessprofil|status|text|notnull||-|-'),
    ('spalte|prozessprofil|total_duration_minutes|numeric|null||-|-'),
    ('spalte|prozessprofil|upstream_process_id|character varying(8)|null||-|-'),
    ('trigger_intern|profil_rollen|profil_rollen_profil_fk|O'),
    ('trigger_intern|profil_rollen|profil_rollen_rolle_fk|O'),
    ('trigger_intern|profil_write_status|profil_write_status_profil_fk|O'),
    ('trigger_intern|prozessprofil|profil_rollen_profil_fk|O'),
    ('trigger_intern|prozessprofil|profil_write_status_profil_fk|O'),
    ('trigger_intern|prozessprofil|prozessprofil_company_fk|O'),
    ('trigger_intern|prozessprofil|prozessprofil_downstream_fk|O'),
    ('trigger_intern|prozessprofil|prozessprofil_erhebung_fk|O'),
    ('trigger_intern|prozessprofil|prozessprofil_owner_rolle_fk|O'),
    ('trigger_intern|prozessprofil|prozessprofil_prozess_fk|O'),
    ('trigger_intern|prozessprofil|prozessprofil_teilprozess_fk|O'),
    ('trigger_intern|prozessprofil|prozessprofil_upstream_fk|O'),
    ('trigger|profil_rollen|tr_freeze_rollen|CREATE TRIGGER tr_freeze_rollen BEFORE INSERT OR DELETE OR UPDATE ON bc1.profil_rollen FOR EACH ROW EXECUTE FUNCTION bc1.tf_freeze_rollen()|O'),
    ('trigger|prozessprofil|tr_freeze_profil|CREATE TRIGGER tr_freeze_profil BEFORE DELETE OR UPDATE ON bc1.prozessprofil FOR EACH ROW EXECUTE FUNCTION bc1.tf_freeze_profil()|O'),
    ('trigger|prozessprofil|tr_version_vergeben|CREATE TRIGGER tr_version_vergeben BEFORE INSERT ON bc1.prozessprofil FOR EACH ROW EXECUTE FUNCTION bc1.tf_version_vergeben()|O');

CREATE OR REPLACE TEMP VIEW bc1_ist_signatur AS
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
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND a.attnum > 0 AND NOT a.attisdropped
UNION ALL
SELECT format('constraint|%s|%s|%s', c.relname, con.conname,
              pg_get_constraintdef(con.oid))
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
SELECT format('index|%s|%s|%s', tablename, indexname, indexdef)
  FROM pg_indexes
 WHERE schemaname = 'bc1' AND tablename IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
SELECT format('trigger|%s|%s|%s|%s', c.relname, t.tgname,
              pg_get_triggerdef(t.oid), t.tgenabled)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND NOT t.tgisinternal
UNION ALL
-- Codex N10-I3: die INTERNEN RI-Trigger werden oben ausgeschlossen, weil ihre
-- Namen OIDs tragen und zwischen Installationen verschieden sind. Ihr
-- AKTIVIERUNGSZUSTAND gehoert aber in die Signatur — ein deaktivierter RI-Trigger
-- laesst die Constraint-Definition unveraendert und erzwingt den FK trotzdem
-- nicht mehr. Schluessel ist deshalb der Constraint-Name, nicht der Triggername.
SELECT format('trigger_intern|%s|%s|%s', c.relname, con.conname, t.tgenabled)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_constraint con ON con.oid = t.tgconstraint
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND t.tgisinternal
UNION ALL
-- Nicht nur der Rumpf: Sprache, SECURITY-Modus, Volatilitaet und die
-- Funktionskonfiguration gehoeren zur Semantik (Codex R1-I2).
SELECT format('funktion|%s(%s)->%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s',
              p.proname, pg_get_function_identity_arguments(p.oid),
              format_type(p.prorettype, NULL), l.lanname, p.prokind,
              p.prosecdef, p.proleakproof, p.provolatile, p.proisstrict,
              p.proretset, p.proparallel, pg_get_userbyid(p.proowner),
              coalesce(array_to_string(p.proconfig, ','), '-'), md5(p.prosrc))
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  JOIN pg_language l ON l.oid = p.prolang
 WHERE n.nspname = 'bc1'
   AND p.proname IN ('tf_version_vergeben', 'tf_freeze_profil', 'tf_freeze_rollen')
UNION ALL
-- Auch die Funktionsrechte gehoeren zur Signatur: EXECUTE liegt per Default bei
-- PUBLIC (Codex R3-N-I2). Fuer Trigger-Funktionen ist das folgenlos — direkt
-- aufrufen laesst sich eine Trigger-Funktion nicht —, aber es gehoert sichtbar in
-- die Sollsignatur statt unbemerkt zu driften. Codex N10-M8 zu Recht: "nur
-- bc1_role, alles andere nichts" gilt fuer TABELLEN, nicht fuer diese ACL-Zeilen.
SELECT format('funktion_acl|%s|%s|%s|%s', p.proname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  CROSS JOIN LATERAL aclexplode(
      coalesce(p.proacl, acldefault('f', p.proowner))) AS acl
 WHERE n.nspname = 'bc1'
   AND p.proname IN ('tf_version_vergeben', 'tf_freeze_profil', 'tf_freeze_rollen')
UNION ALL
SELECT format('eigentuemer|%s|%s', c.relname, pg_get_userbyid(c.relowner))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
-- Gesetzte Rechte VOLLSTAENDIG (Codex R1-I2): aclexplode listet JEDEN Grantee,
-- auch unerwartete und PUBLIC — eine feste Rollenliste haette zusaetzliche
-- Empfaenger uebersehen.
SELECT format('acl|%s|%s|%s|%s', c.relname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(
      coalesce(c.relacl, acldefault('r', c.relowner))) AS acl
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
-- Codex N10-C1: SPALTENRECHTE liegen in pg_attribute.attacl, nicht in relacl.
-- Ein 'GRANT SELECT (profil) ON bc1.prozessprofil TO bc2_role' war vorher fuer
-- Signatur UND Rechte-Test unsichtbar.
SELECT format('spalte_acl|%s|%s|%s|%s|%s', c.relname, a.attname,
              CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                   ELSE pg_get_userbyid(acl.grantee) END,
              acl.privilege_type, acl.is_grantable)
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(a.attacl) AS acl
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND a.attnum > 0 AND NOT a.attisdropped AND a.attacl IS NOT NULL
UNION ALL
-- Codex N10-C2: 'GRANT bc1_role TO <irgendwer>' gibt volle Rechte, OHNE dass sich
-- eine Tabellen-ACL aendert. Die Mitgliederliste gehoert deshalb in die Signatur.
SELECT format('mitglied|bc1_role|%s', pg_get_userbyid(m.member))
  FROM pg_auth_members m
 WHERE m.roleid = (SELECT oid FROM pg_roles WHERE rolname = 'bc1_role')
UNION ALL
-- Codex N10-I3: RLS-Zustand und Policies — eine nachtraeglich aktivierte Policy
-- aenderte die Sichtbarkeit, ohne eine der obigen Zeilen zu beruehren.
SELECT format('rls|%s|%s|%s', c.relname, c.relrowsecurity, c.relforcerowsecurity)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
SELECT format('policy|%s|%s|%s|%s', c.relname, pol.polname, pol.polcmd,
              coalesce(pg_get_expr(pol.polqual, pol.polrelid), '-'))
  FROM pg_policy pol
  JOIN pg_class c ON c.oid = pol.polrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
-- Codex N10-I3: Regeln (pg_rewrite) koennen ein INSERT/UPDATE stillschweigend
-- umleiten, ohne Constraint oder Trigger anzufassen.
SELECT format('regel|%s|%s', c.relname, r.rulename)
  FROM pg_rewrite r
  JOIN pg_class c ON c.oid = r.ev_class
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
UNION ALL
-- Codex N10-I3: die drei COMMENT ON TABLE sind Teil der Anlage — dann gehoeren
-- sie auch zur Signatur, sonst pruefen wir etwas nicht, das wir selbst schreiben.
SELECT format('kommentar|%s|%s', c.relname, md5(d.description))
  FROM pg_description d
  JOIN pg_class c ON c.oid = d.objoid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status') AND d.objsubid = 0
UNION ALL
-- EFFEKTIVE Sicht, jetzt ueber ALLE Rollen statt einer festen Liste (Codex
-- N10-C2). Bewusst ausgenommen: Superuser (sie duerfen per Definition alles —
-- das ist die administrative Vertrauensgrenze, keine Drift) und die pg_*-
-- Systemrollen (Cluster-Konstanten; sie wuerden die Signatur zwischen
-- Installationen unterscheiden, ohne etwas ueber UNSER Schema auszusagen).
-- Eine normale Rolle, die MITGLIED einer pg_*-Rolle ist, taucht trotzdem auf —
-- has_table_privilege loest die Vererbung auf.
SELECT format('effektiv|%s|%s|%s', c.relname, r.rolname, priv)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace,
       pg_roles r,
       unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) AS priv
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND NOT r.rolsuper AND r.rolname NOT LIKE 'pg\_%'
   AND has_table_privilege(r.oid, c.oid, priv)
UNION ALL
-- Und dasselbe auf SPALTENEBENE (Codex N10-C1): has_any_column_privilege sieht
-- auch Rechte, die NUR auf einzelnen Spalten liegen.
SELECT format('effektiv_spalte|%s|%s|%s', c.relname, r.rolname, priv)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace,
       pg_roles r,
       unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']) AS priv
 WHERE n.nspname = 'bc1' AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
   AND NOT r.rolsuper AND r.rolname NOT LIKE 'pg\_%'
   AND has_any_column_privilege(r.oid, c.oid, priv);

-- ============================================================
-- 1. VORPRUEFUNG — Dreifallregel, VOR jeder Aenderung (Spec K1)
-- ============================================================
CREATE TEMP TABLE bc1_einspiel_modus (modus text NOT NULL) ON COMMIT DROP;

DO $$
DECLARE vorhanden integer; abweichung text;
BEGIN
    -- Existenz ueber ALLE neun Vertragsobjekte, nicht nur die Tabellen
    -- (Codex R1-I2: drei verwaiste Triggerfunktionen bei null Tabellen waeren
    -- sonst als "nichts vorhanden" durchgegangen und still ergaenzt worden).
    SELECT count(*) INTO vorhanden FROM (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND c.relkind = 'r'
           AND c.relname IN ('prozessprofil', 'profil_rollen', 'profil_write_status')
        UNION ALL
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'bc1'
           AND p.proname IN ('tf_version_vergeben', 'tf_freeze_profil',
                             'tf_freeze_rollen')
        UNION ALL
        SELECT 1 FROM pg_trigger t
          JOIN pg_class c ON c.oid = t.tgrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'bc1' AND NOT t.tgisinternal
           AND t.tgname IN ('tr_version_vergeben', 'tr_freeze_profil',
                            'tr_freeze_rollen')) alle;

    IF vorhanden = 0 THEN
        INSERT INTO pg_temp.bc1_einspiel_modus VALUES ('anlegen');
        RAISE NOTICE 'Fall 1: kein Vertragsobjekt vorhanden — vollstaendige Anlage.';
        RETURN;
    END IF;

    IF vorhanden <> 9 THEN
        -- Auch MEHR als neun ist Fall 3 (z. B. ein zusaetzliches Overload,
        -- Codex R2-N-I2) — nicht nur Teilbestand.
        RAISE EXCEPTION 'Fall 3: Teilbestand oder Mehrbestand — % statt 9 '
                        'Vertragsobjekte. Abbruch OHNE Aenderung.', vorhanden;
    END IF;

    SELECT string_agg(zeile, E'\n' ORDER BY zeile) INTO abweichung FROM (
        SELECT format('  - fehlt:  %s', zeile) AS zeile
          FROM (SELECT zeile FROM bc1_soll_signatur
                EXCEPT SELECT zeile FROM bc1_ist_signatur) a
        UNION ALL
        SELECT format('  + zuviel: %s', zeile)
          FROM (SELECT zeile FROM bc1_ist_signatur
                EXCEPT SELECT zeile FROM bc1_soll_signatur) b) diff;

    IF abweichung IS NOT NULL THEN
        RAISE EXCEPTION E'Fall 3: Bestand weicht von der Sollsignatur ab. Abbruch OHNE Aenderung.\n%',
                        abweichung;
    END IF;
    INSERT INTO pg_temp.bc1_einspiel_modus VALUES ('noop');
    RAISE NOTICE 'Fall 2: Bestand ist identisch zur Sollsignatur — No-op.';
END $$;

-- ============================================================
-- 2. ANLAGE + 3. RECHTE — NUR im Fall 1 (Spec K1)
-- ============================================================
-- Die Klammer ist der eigentliche No-op-Nachweis (Codex R1-C1 / R2-N-C2):
-- CREATE OR REPLACE, COMMENT, GRANT und REVOKE sind KEINE No-ops — sie schreiben
-- den Katalog neu und nehmen Sperren. Im Fall 2 darf deshalb nichts davon laufen.
-- Innerhalb der Klammer stehen bewusst nackte CREATEs ohne IF NOT EXISTS und ohne
-- OR REPLACE: im Fall 1 ist garantiert nichts da, ein unerwarteter Restbestand
-- soll zum Fehler werden statt zur stillen Ersetzung.
-- Drei Quoting-Ebenen, drei Tags: aussen $einspielen$, je Statement $ddl$,
-- Funktionsrumpf $fn$.
DO $einspielen$
BEGIN
    IF (SELECT modus FROM pg_temp.bc1_einspiel_modus) <> 'anlegen' THEN
        RAISE NOTICE 'Fall 2: Bestand identisch — es wird NICHTS ausgefuehrt.';
        RETURN;
    END IF;

    -- ---------- Abschnitt 2: Anlage ----------
    EXECUTE $ddl$ CREATE TABLE bc1.prozessprofil (
        company_id                          uuid        NOT NULL,
        focus_step_id                       varchar(16) NOT NULL,
        profil_version                      integer     NOT NULL,
        process_id                          varchar(8)  NOT NULL,
        status                              text        NOT NULL,
        process_owner_rolle_id              text,
        upstream_process_id                 varchar(8),
        downstream_process_id               varchar(8),
        frequency_per_year                  numeric,
        executions_per_run                  numeric,
        total_duration_minutes              numeric,
        focus_step_duration_minutes         numeric,
        focus_step_duration_source          text,
        focus_step_duration_confidence_pct  integer,
        erhebung_id                         text        NOT NULL,
        paket_version                       text        NOT NULL,
        profil                              jsonb       NOT NULL,
        erstellt_am                         timestamptz NOT NULL DEFAULT now(),
        aktualisiert_am                     timestamptz NOT NULL DEFAULT now(),

        CONSTRAINT prozessprofil_pkey
            PRIMARY KEY (company_id, focus_step_id, profil_version),
        CONSTRAINT prozessprofil_version_positiv
            CHECK (profil_version >= 1),
        CONSTRAINT prozessprofil_status_werte
            CHECK (status IN ('in_erhebung', 'fertig')),
        CONSTRAINT prozessprofil_focus_step_muster
            CHECK (focus_step_id ~ '^KP-[0-9]{2}\.TP-[0-9]+$'),
        CONSTRAINT prozessprofil_process_muster
            CHECK (process_id ~ '^KP-[0-9]{2}$'),
        CONSTRAINT prozessprofil_tp_gehoert_zu_kp
            CHECK (focus_step_id LIKE process_id || '.%'),
        CONSTRAINT prozessprofil_upstream_kein_selbstbezug
            CHECK (upstream_process_id IS NULL OR upstream_process_id <> process_id),
        CONSTRAINT prozessprofil_downstream_kein_selbstbezug
            CHECK (downstream_process_id IS NULL OR downstream_process_id <> process_id),
        CONSTRAINT prozessprofil_duration_source_werte
            CHECK (focus_step_duration_source IS NULL
                   OR focus_step_duration_source IN ('gemessen', 'geschaetzt', 'aus_system')),
        CONSTRAINT prozessprofil_confidence_bereich
            CHECK (focus_step_duration_confidence_pct IS NULL
                   OR focus_step_duration_confidence_pct BETWEEN 0 AND 100),
        -- Weiche Zahlenpruefung (Klaerpunkt K-C mit BC2 offen): nicht negativ und
        -- endlich. In PostgreSQLs numeric-Ordnung sortiert NaN UEBER Infinity —
        -- '< Infinity' schliesst NaN damit mit aus; explizit dokumentiert, weil das
        -- gegenlaeufig zu float ist.
        CONSTRAINT prozessprofil_zahlen_wertebereich CHECK (
            (frequency_per_year IS NULL
                OR (frequency_per_year >= 0 AND frequency_per_year < 'Infinity'::numeric))
            AND (executions_per_run IS NULL
                OR (executions_per_run >= 0 AND executions_per_run < 'Infinity'::numeric))
            AND (total_duration_minutes IS NULL
                OR (total_duration_minutes >= 0 AND total_duration_minutes < 'Infinity'::numeric))
            AND (focus_step_duration_minutes IS NULL
                OR (focus_step_duration_minutes >= 0
                    AND focus_step_duration_minutes < 'Infinity'::numeric))),

        CONSTRAINT prozessprofil_company_fk FOREIGN KEY (company_id)
            REFERENCES companies (company_id) ON DELETE CASCADE,
        CONSTRAINT prozessprofil_teilprozess_fk FOREIGN KEY (company_id, focus_step_id)
            REFERENCES ref_teilprozesse (company_id, sub_process_id),
        CONSTRAINT prozessprofil_prozess_fk FOREIGN KEY (company_id, process_id)
            REFERENCES ref_prozesse (company_id, process_id),
        CONSTRAINT prozessprofil_upstream_fk FOREIGN KEY (company_id, upstream_process_id)
            REFERENCES ref_prozesse (company_id, process_id),
        CONSTRAINT prozessprofil_downstream_fk FOREIGN KEY (company_id, downstream_process_id)
            REFERENCES ref_prozesse (company_id, process_id),
        CONSTRAINT prozessprofil_owner_rolle_fk FOREIGN KEY (company_id, process_owner_rolle_id)
            REFERENCES mandant_rollen (company_id, rolle_id),
        CONSTRAINT prozessprofil_erhebung_fk FOREIGN KEY (company_id, erhebung_id)
            REFERENCES ref_erhebungen (company_id, erhebung_id)
    ) $ddl$;

    EXECUTE $ddl$ COMMENT ON TABLE bc1.prozessprofil IS
        'BC1-Prozessprofil je Fokus-Schritt und Version. Massgeblich fuer Gate 0 ist die '
        'juengste Zeile mit status=fertig (Brief 2.2). Nur bc1_role schreibt.' $ddl$;

    -- Hoechstens EIN laufendes Interview je Fokus-Schritt (Brief 2.3, Regel 2).
    EXECUTE $ddl$ CREATE UNIQUE INDEX prozessprofil_hoechstens_ein_draft
        ON bc1.prozessprofil (company_id, focus_step_id)
        WHERE status = 'in_erhebung' $ddl$;

    EXECUTE $ddl$ CREATE TABLE bc1.profil_rollen (
        company_id     uuid        NOT NULL,
        focus_step_id  varchar(16) NOT NULL,
        profil_version integer     NOT NULL,
        pos            smallint    NOT NULL,
        rolle_id       text,
        rolle_freitext text,
        zeitanteil_pct integer,

        CONSTRAINT profil_rollen_pkey
            PRIMARY KEY (company_id, focus_step_id, profil_version, pos),
        CONSTRAINT profil_rollen_pos_positiv CHECK (pos > 0),
        CONSTRAINT profil_rollen_zeitanteil_bereich
            CHECK (zeitanteil_pct IS NULL OR zeitanteil_pct BETWEEN 0 AND 100),
        -- Brief Abschnitt 3 woertlich: "genau eine Quelle je Zeile — rolle_id
        -- gesetzt ODER rolle_freitext nicht-leer (getrimmt), nicht beides".
        -- Ein leerer/Whitespace-Freitext ist KEINE zweite Quelle und macht eine
        -- ID-Zeile deshalb nicht ungueltig (Codex R1-I6).
        CONSTRAINT profil_rollen_genau_eine_quelle CHECK (
            (rolle_id IS NOT NULL) <> (btrim(coalesce(rolle_freitext, '')) <> '')),
        CONSTRAINT profil_rollen_profil_fk
            FOREIGN KEY (company_id, focus_step_id, profil_version)
            REFERENCES bc1.prozessprofil (company_id, focus_step_id, profil_version)
            ON DELETE CASCADE,
        -- DEFERRABLE INITIALLY DEFERRED ist hier PFLICHT, nicht Geschmack — am
        -- Container gemessen (postgres:16, 25.08.): ohne die Verzoegerung blockiert
        -- dieser FK die DSGVO-Loeschkaskade. Grund: bei DELETE FROM companies wird
        -- mandant_rollen auf Kaskadentiefe 1 geraeumt und seine NO-ACTION-Pruefung
        -- sofort ausgewertet, waehrend profil_rollen erst auf Tiefe 2 verschwindet
        -- (companies -> prozessprofil -> profil_rollen). Die Verletzung ist also nur
        -- transient innerhalb der Loeschtransaktion. Gemessen:
        --   NO ACTION                     -> Kaskade BLOCKIERT
        --   DEFERRABLE INITIALLY IMMEDIATE-> Kaskade BLOCKIERT
        --   DEFERRABLE INITIALLY DEFERRED -> Kaskade laeuft, beide Schutzwirkungen bleiben
        -- Die Schutzwirkung kostet das nichts: eine einzelne mandant_rollen-Zeile,
        -- auf die ein Profil zeigt, bleibt unloeschbar (dann eben beim COMMIT), und
        -- eine unbekannte rolle_id wird weiterhin abgewiesen.
        -- FOLGE FUER ETAPPE 2 (Rollen-Writer): FK-Fehler schlagen beim COMMIT zu,
        -- nicht beim INSERT. Wer sie frueher sehen will, setzt nach dem Einfuegen
        -- SET CONSTRAINTS bc1.profil_rollen_rolle_fk IMMEDIATE.
        CONSTRAINT profil_rollen_rolle_fk FOREIGN KEY (company_id, rolle_id)
            REFERENCES mandant_rollen (company_id, rolle_id)
            DEFERRABLE INITIALLY DEFERRED
    ) $ddl$;

    EXECUTE $ddl$ CREATE UNIQUE INDEX profil_rollen_rolle_einmalig
        ON bc1.profil_rollen (company_id, focus_step_id, profil_version, rolle_id)
        WHERE rolle_id IS NOT NULL $ddl$;

    EXECUTE $ddl$ COMMENT ON TABLE bc1.profil_rollen IS
        'Rollen am Fokus-Schritt. Struktur ist abgenommen; befuellt wird sie erst in '
        'Etappe 2 (Rollen-Auswahl im Interview).' $ddl$;

    -- Interne Session->Profil-Bindung. Gehoert BC1 allein (kein Fremdzugriff, s. Abschnitt 3).
    EXECUTE $ddl$ CREATE TABLE bc1.profil_write_status (
        session_id     text        NOT NULL,
        company_id     uuid        NOT NULL,
        focus_step_id  varchar(16) NOT NULL,
        profil_version integer     NOT NULL,
        erstellt_am    timestamptz NOT NULL DEFAULT now(),

        CONSTRAINT profil_write_status_pkey PRIMARY KEY (session_id),
        CONSTRAINT profil_write_status_je_zeile
            UNIQUE (company_id, focus_step_id, profil_version),
        CONSTRAINT profil_write_status_profil_fk
            FOREIGN KEY (company_id, focus_step_id, profil_version)
            REFERENCES bc1.prozessprofil (company_id, focus_step_id, profil_version)
            ON DELETE CASCADE
    ) $ddl$;

    EXECUTE $ddl$ COMMENT ON TABLE bc1.profil_write_status IS
        'Bindung Session -> Profilzeile. Lebt und stirbt mit ihrer Profilzeile (CASCADE). '
        'Interne Tabelle: ausschliesslich bc1_role, ausdruecklich NICHT in der '
        'Fremdschema-Lesematrix (siehe REVOKE in Abschnitt 3).' $ddl$;

    -- ---------- Trigger-Funktionen ----------
    EXECUTE $ddl$ CREATE FUNCTION bc1.tf_version_vergeben() RETURNS trigger
    LANGUAGE plpgsql AS $fn$
    DECLARE max_version integer;
    BEGIN
        -- Serialisiert zwei gleichzeitige Writer je (Mandant, Fokus-Schritt), bevor
        -- sie dasselbe Maximum lesen koennen (R3-I7). Der Partialindex bleibt als
        -- zweite Verteidigungslinie.
        PERFORM pg_advisory_xact_lock(
            hashtext(NEW.company_id::text || '|' || NEW.focus_step_id));
        SELECT coalesce(max(profil_version), 0) INTO max_version
          FROM bc1.prozessprofil
         WHERE company_id = NEW.company_id AND focus_step_id = NEW.focus_step_id;
        NEW.profil_version := max_version + 1;    -- vergibt die DB, nicht der Writer
        NEW.erstellt_am := now();
        NEW.aktualisiert_am := now();
        RETURN NEW;
    END $fn$ $ddl$;

    EXECUTE $ddl$ CREATE FUNCTION bc1.tf_freeze_profil() RETURNS trigger
    LANGUAGE plpgsql AS $fn$
    BEGIN
        -- Definierte Ausnahme, ZWEI Bedingungen (Codex R1-C2 + R5-N5-I2):
        -- (1) verschachteltes DELETE — pg_trigger_depth() benennt aber nur die
        --     Verschachtelung, nicht die Ursache; ohne TG_OP wuerde sonst jedes
        --     triggerinduzierte UPDATE den Freeze umgehen;
        -- (2) der Elternsatz in companies ist bereits weg. Das ist der fehlende
        --     Ursachen-Nachweis: bei der DSGVO-Loeschkaskade ist die companies-Zeile
        --     im selben Statement schon geloescht, bei jedem anderen Trigger-DELETE
        --     steht sie noch. Ein fremdes Trigger-DELETE prallt damit am Freeze ab.
        --     AM CONTAINER GEMESSEN (postgres:16): Kaskade depth=2/eltern=weg,
        --     fremder Trigger depth=2/eltern=da, direkter DELETE depth=1.
        IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
           AND NOT EXISTS (SELECT 1 FROM companies
                            WHERE company_id = OLD.company_id) THEN
            RETURN OLD;
        END IF;

        IF TG_OP = 'DELETE' THEN
            IF OLD.status = 'fertig' THEN
                RAISE EXCEPTION 'bc1.prozessprofil %/% ist eingefroren (DELETE abgewiesen)',
                    OLD.focus_step_id, OLD.profil_version USING ERRCODE = 'restrict_violation';
            END IF;
            RETURN OLD;                                   -- Draft loeschen ist erlaubt (K5)
        END IF;

        IF OLD.status = 'fertig' THEN
            RAISE EXCEPTION 'bc1.prozessprofil %/% ist eingefroren (UPDATE abgewiesen)',
                OLD.focus_step_id, OLD.profil_version USING ERRCODE = 'restrict_violation';
        END IF;
        IF NEW.company_id <> OLD.company_id
           OR NEW.focus_step_id <> OLD.focus_step_id
           OR NEW.profil_version <> OLD.profil_version THEN
            RAISE EXCEPTION 'Identitaet einer Profilzeile ist unveraenderlich'
                USING ERRCODE = 'restrict_violation';
        END IF;
        NEW.aktualisiert_am := now();
        RETURN NEW;
    END $fn$ $ddl$;

    EXECUTE $ddl$ CREATE FUNCTION bc1.tf_freeze_rollen() RETURNS trigger
    LANGUAGE plpgsql AS $fn$
    DECLARE v_company uuid; v_step varchar(16); v_version integer; eltern_status text;
    BEGIN
        -- Wie bei prozessprofil zwei Bedingungen: verschachteltes DELETE UND die
        -- referenzierte Profilzeile ist bereits weg (Kaskade Mandant bzw. Profil).
        -- INSERT/UPDATE aus einem Trigger heraus bleibt gesperrt (R1-C2, R5-N5-I2).
        -- RECHTE-FRAGE GEMESSEN (postgres:16, R6-N6-C1): Bei der FK-Kaskade fuehrt
        -- PostgreSQL die Aktion mit den Rechten des EIGENTUEMERS der referenzierenden
        -- Tabelle aus — der Trigger laeuft also als bc1_role, nicht als BC0s
        -- Loeschkonto. Ein Loeschkonto ohne jedes Recht auf bc1.* hat die Kaskade
        -- vollstaendig durchlaufen (0 Restzeilen); der SELECT hier scheitert nicht.
        IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
           AND NOT EXISTS (SELECT 1 FROM bc1.prozessprofil
                            WHERE company_id = OLD.company_id
                              AND focus_step_id = OLD.focus_step_id
                              AND profil_version = OLD.profil_version) THEN
            RETURN OLD;
        END IF;

        IF TG_OP = 'DELETE' THEN
            v_company := OLD.company_id; v_step := OLD.focus_step_id;
            v_version := OLD.profil_version;
        ELSE
            v_company := NEW.company_id; v_step := NEW.focus_step_id;
            v_version := NEW.profil_version;
        END IF;

        -- Elternzeile SPERREN, bevor ihr Status gelesen wird (R4-I7): sonst koennte
        -- eine Rollenzeile zwischen Statuspruefung und Freeze durchrutschen.
        SELECT status INTO eltern_status FROM bc1.prozessprofil
         WHERE company_id = v_company AND focus_step_id = v_step
           AND profil_version = v_version
           FOR UPDATE;

        IF eltern_status = 'fertig' THEN
            RAISE EXCEPTION 'bc1.profil_rollen zu %/%: Version ist eingefroren',
                v_step, v_version USING ERRCODE = 'restrict_violation';
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $fn$ $ddl$;

    -- ---------- Trigger ----------
    EXECUTE $ddl$ CREATE TRIGGER tr_version_vergeben
        BEFORE INSERT ON bc1.prozessprofil
        FOR EACH ROW EXECUTE FUNCTION bc1.tf_version_vergeben() $ddl$;

    EXECUTE $ddl$ CREATE TRIGGER tr_freeze_profil
        BEFORE UPDATE OR DELETE ON bc1.prozessprofil
        FOR EACH ROW EXECUTE FUNCTION bc1.tf_freeze_profil() $ddl$;

    EXECUTE $ddl$ CREATE TRIGGER tr_freeze_rollen
        BEFORE INSERT OR UPDATE OR DELETE ON bc1.profil_rollen
        FOR EACH ROW EXECUTE FUNCTION bc1.tf_freeze_rollen() $ddl$;

    -- ---------- Abschnitt 3: Rechte — nur bc1_role; alles andere ausdruecklich
    -- weg, bis Klaerpunkt K-B beantwortet ist (Spec K1, R14-I1) ----------
    EXECUTE $ddl$ REVOKE ALL ON bc1.prozessprofil, bc1.profil_rollen, bc1.profil_write_status
        FROM PUBLIC $ddl$;

    EXECUTE $ddl$ GRANT SELECT, INSERT, UPDATE, DELETE
        ON bc1.prozessprofil, bc1.profil_rollen, bc1.profil_write_status TO bc1_role $ddl$;
    -- bc_leser bekommt SELECT ueber BC0s ALTER DEFAULT PRIVILEGES automatisch — ein
    -- REVOKE nur von PUBLIC entfernt das NICHT (R14-I1). Deshalb explizit, und fuer
    -- ALLE drei Tabellen (die Lese-Wertemenge ist Buendel-Frage #3, K-B).
    -- Als reines plpgsql-IF statt als geschachtelter DO-Block: ein zweiter
    -- DO-Block mit demselben Quoting-Tag wuerde den aeusseren vorzeitig schliessen.
    -- (ACHTUNG, hier selbst passiert: auch KOMMENTARE zaehlen. Innerhalb eines
    -- Dollar-Quotes ist alles Rohtext — ein Tagname im Kommentar beendet den Block.
    -- Deshalb steht in dieser Datei innerhalb der Klammer kein Tagname im Klartext.)
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
        EXECUTE $ddl$ REVOKE ALL ON bc1.prozessprofil, bc1.profil_rollen,
                      bc1.profil_write_status FROM bc_leser $ddl$;
    END IF;
END
$einspielen$;

-- ============================================================
-- 4. NACHPRUEFUNG — der Bestand MUSS jetzt exakt der Sollsignatur entsprechen
-- ============================================================
DO $$
DECLARE abweichung text;
BEGIN
    IF (SELECT modus FROM pg_temp.bc1_einspiel_modus) <> 'anlegen' THEN
        RETURN;              -- Fall 2: die Vorpruefung hat schon verglichen
    END IF;
    SELECT string_agg(zeile, E'\n' ORDER BY zeile) INTO abweichung FROM (
        SELECT format('  - fehlt:  %s', zeile) AS zeile
          FROM (SELECT zeile FROM bc1_soll_signatur
                EXCEPT SELECT zeile FROM bc1_ist_signatur) a
        UNION ALL
        SELECT format('  + zuviel: %s', zeile)
          FROM (SELECT zeile FROM bc1_ist_signatur
                EXCEPT SELECT zeile FROM bc1_soll_signatur) b) diff;

    IF abweichung IS NOT NULL THEN
        RAISE EXCEPTION E'Nachpruefung fehlgeschlagen — Rollback.\n%', abweichung;
    END IF;
    RAISE NOTICE 'Sollsignatur bestaetigt.';
END $$;
