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
-- 2. ANLAGE — idempotent; im No-op-Fall aendert hier nichts etwas
-- ============================================================
CREATE TABLE IF NOT EXISTS bc1.prozessprofil (
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
);

COMMENT ON TABLE bc1.prozessprofil IS
    'BC1-Prozessprofil je Fokus-Schritt und Version. Massgeblich fuer Gate 0 ist die '
    'juengste Zeile mit status=fertig (Brief 2.2). Nur bc1_role schreibt.';

-- Hoechstens EIN laufendes Interview je Fokus-Schritt (Brief 2.3, Regel 2).
CREATE UNIQUE INDEX IF NOT EXISTS prozessprofil_hoechstens_ein_draft
    ON bc1.prozessprofil (company_id, focus_step_id)
    WHERE status = 'in_erhebung';

CREATE TABLE IF NOT EXISTS bc1.profil_rollen (
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
);

CREATE UNIQUE INDEX IF NOT EXISTS profil_rollen_rolle_einmalig
    ON bc1.profil_rollen (company_id, focus_step_id, profil_version, rolle_id)
    WHERE rolle_id IS NOT NULL;

COMMENT ON TABLE bc1.profil_rollen IS
    'Rollen am Fokus-Schritt. Struktur ist abgenommen; befuellt wird sie erst in '
    'Etappe 2 (Rollen-Auswahl im Interview).';

-- Interne Session->Profil-Bindung. Gehoert BC1 allein (kein Fremdzugriff, s. Abschnitt 3).
CREATE TABLE IF NOT EXISTS bc1.profil_write_status (
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
);

COMMENT ON TABLE bc1.profil_write_status IS
    'Bindung Session -> Profilzeile. Lebt und stirbt mit ihrer Profilzeile (CASCADE). '
    'Interne Tabelle: ausschliesslich bc1_role, ausdruecklich NICHT in der '
    'Fremdschema-Lesematrix (siehe REVOKE in Abschnitt 3).';

-- ---------- Trigger-Funktionen ----------
CREATE OR REPLACE FUNCTION bc1.tf_version_vergeben() RETURNS trigger
LANGUAGE plpgsql AS $$
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
END $$;

CREATE OR REPLACE FUNCTION bc1.tf_freeze_profil() RETURNS trigger
LANGUAGE plpgsql AS $$
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
END $$;

CREATE OR REPLACE FUNCTION bc1.tf_freeze_rollen() RETURNS trigger
LANGUAGE plpgsql AS $$
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
END $$;

-- ---------- Trigger (CREATE OR REPLACE = echter No-op im Fall 2, ab PG 14) ----------
CREATE OR REPLACE TRIGGER tr_version_vergeben
    BEFORE INSERT ON bc1.prozessprofil
    FOR EACH ROW EXECUTE FUNCTION bc1.tf_version_vergeben();

CREATE OR REPLACE TRIGGER tr_freeze_profil
    BEFORE UPDATE OR DELETE ON bc1.prozessprofil
    FOR EACH ROW EXECUTE FUNCTION bc1.tf_freeze_profil();

CREATE OR REPLACE TRIGGER tr_freeze_rollen
    BEFORE INSERT OR UPDATE OR DELETE ON bc1.profil_rollen
    FOR EACH ROW EXECUTE FUNCTION bc1.tf_freeze_rollen();
