-- ============================================================
-- BC0 Onboarding — PostgreSQL-Schema (mandantenfähig)  ·  v1.1
-- PROJEKT-VORGABE: PostgreSQL ist der verbindliche Standard für alle BCs.
-- Zweck: Erfassung + Persistenz + rechnerische Reifegrad-Feststellung.
-- Stand: 22.06.2026 · Autor: Simeon Ehmer · Postgres >= 15
--
-- Änderungen ggü. v1.0 (Review-Punkte):
--   [1] beleg_source-ENUM um 'baseline' und 'yaml' erweitert (App/Snapshot-Quellen)
--   [2] company_profile.profile_json JSONB (volles Unternehmensprofil / Reiter "Unternehmensdaten")
--   [3] process_category: kanonische Werte MIT Umlaut (YAML-Vorlage angeglichen)
--   [4] updated_at wird per Trigger automatisch gepflegt
--   [5] Enrichment-/Provenance-Layer (BC1 Write-back) als geplanter Abschnitt dokumentiert
--   [6] ref_teilprozesse: tools / medienbrueche / schnittstellen / api (optional, CSV) ergänzt
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
-- Für den Vektor-Layer (BC1, Embeddings) – erschlägt #6:
-- CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector (aktivieren, sobald BC1 startet)

-- ---------- ENUMs ----------
CREATE TYPE onboarding_status AS ENUM ('neu','laeuft','abgeschlossen');
-- [3] Kanonische Kategorien MIT Umlaut – exakt diese Werte verwenden:
CREATE TYPE process_category  AS ENUM ('Steuerungsprozess','Kerngeschäftsprozess','Unterstützungsprozess');
-- [1] Quellen inkl. 'baseline' (Seed) und 'yaml' (Import):
CREATE TYPE beleg_source      AS ENUM ('chat','doc','xlsx','interview','manuell','baseline','yaml');

-- ---------- Hilfsfunktion: updated_at automatisch [4] ----------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 1. MANDANTEN (Tenants)
-- ============================================================
CREATE TABLE companies (
  company_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name           TEXT        NOT NULL,
  branche        TEXT,
  rechtsform     TEXT,
  mitarbeitende  INTEGER     CHECK (mitarbeitende >= 0),
  region         TEXT,
  status         onboarding_status NOT NULL DEFAULT 'neu',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_companies_updated BEFORE UPDATE ON companies
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 1:1 Unternehmensprofil (Detailfelder + volles Profil als JSONB)
CREATE TABLE company_profile (
  company_id       UUID PRIMARY KEY REFERENCES companies(company_id) ON DELETE CASCADE,
  geschaeftsmodell TEXT,
  tech_stack       TEXT,
  vision           TEXT,
  finanzen         JSONB,
  profile_json     JSONB,           -- [2] volles Unternehmensprofil (frei strukturiert) -> RAG-Quelle BC1
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_company_profile_updated BEFORE UPDATE ON company_profile
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Profil-/Beleg-Dokumente (Binär liegt in MinIO, hier nur Referenz)
CREATE TABLE profile_documents (
  doc_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id   UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  filename     TEXT NOT NULL,
  minio_key    TEXT NOT NULL,           -- Objekt-Schlüssel im Bucket
  mime_type    TEXT,
  uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_docs_company ON profile_documents(company_id);

-- ============================================================
-- 2. BITKOM-REFERENZ (statisch, mandantenübergreifend)
-- ============================================================
CREATE TABLE ref_items (
  item_nr    INTEGER PRIMARY KEY CHECK (item_nr BETWEEN 1 AND 30),
  dimension  TEXT NOT NULL,   -- z.B. '1) Technologie'
  kriterium  TEXT NOT NULL,
  frage      TEXT NOT NULL
);

-- ============================================================
-- 3. PROZESS-STAMMDATEN (mandantenscharf)
-- ============================================================
CREATE TABLE ref_prozesse (
  company_id     UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  process_id     VARCHAR(8)  NOT NULL CHECK (process_id ~ '^KP-[0-9]{2}$'),
  process_name   TEXT        NOT NULL,
  kategorie      process_category NOT NULL,
  owner_name     TEXT,
  owner_role     TEXT,
  trigger_text   TEXT,        -- Prozessauslöser
  input_text     TEXT,
  output_text    TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, process_id)
);

CREATE TABLE ref_teilprozesse (
  company_id        UUID        NOT NULL,
  sub_process_id    VARCHAR(16) NOT NULL CHECK (sub_process_id ~ '^KP-[0-9]{2}\.TP-[0-9]+$'),
  process_id        VARCHAR(8)  NOT NULL,
  step_no           INTEGER     NOT NULL CHECK (step_no BETWEEN 1 AND 5),
  sub_process_name  TEXT        NOT NULL,
  notation          TEXT,        -- A → B → C
  tools             TEXT,        -- [6] eingesetzte Tools (CSV), optional
  medienbrueche     TEXT,        -- [6] Medienbrüche (CSV), optional (ergänzt Item-6-Bewertung)
  schnittstellen    TEXT,        -- [6] Schnittstellen (CSV), optional
  api               TEXT,        -- [6] API-Endpunkt/Hinweis, optional
  PRIMARY KEY (company_id, sub_process_id),
  FOREIGN KEY (company_id, process_id) REFERENCES ref_prozesse(company_id, process_id) ON DELETE CASCADE,
  UNIQUE (company_id, process_id, step_no)
);
CREATE INDEX idx_tp_company_kp ON ref_teilprozesse(company_id, process_id);

-- ============================================================
-- 4. BEWERTUNGEN (Reifegrad-Erfassung) — Beleg ist PFLICHT
--    Hinweis: Item 6 = "ohne unnötige Medienbrüche" -> Medienbruch-Indikator je Teilprozess.
-- ============================================================
CREATE TABLE bitkom_bewertungen (
  company_id      UUID        NOT NULL,
  id              VARCHAR(28) NOT NULL CHECK (id ~ '^KP-[0-9]{2}\.TP-[0-9]+\.I-[0-9]{2}$'),
  sub_process_id  VARCHAR(16) NOT NULL,
  item_nr         INTEGER     NOT NULL REFERENCES ref_items(item_nr),
  stufe           INTEGER     NOT NULL CHECK (stufe BETWEEN 1 AND 5),
  beleg           TEXT        NOT NULL CHECK (length(btrim(beleg)) > 0),  -- Beleg-Pflicht
  quelle          beleg_source NOT NULL DEFAULT 'manuell',
  bewerter        TEXT,
  bewertet_am     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, id),
  FOREIGN KEY (company_id, sub_process_id) REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE,
  UNIQUE (company_id, sub_process_id, item_nr)
);
CREATE INDEX idx_bew_company_sub ON bitkom_bewertungen(company_id, sub_process_id);
CREATE INDEX idx_bew_item        ON bitkom_bewertungen(item_nr);

-- ============================================================
-- 5. AUDIT-TRAIL (append-only)
-- ============================================================
CREATE TABLE audit_log (
  audit_id    BIGSERIAL PRIMARY KEY,
  company_id  UUID,
  entity      TEXT NOT NULL,      -- z.B. 'bitkom_bewertungen'
  entity_id   TEXT,
  action      TEXT NOT NULL,      -- INSERT/UPDATE/DELETE
  actor       TEXT,
  payload     JSONB,
  at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 6. REIFEGRAD-FESTSTELLUNG (Views — rein rechnerisch)
-- ============================================================

-- 6.1 Ø-Stufe je Teilprozess
CREATE VIEW v_reifegrad_tp AS
SELECT company_id, sub_process_id,
       ROUND(AVG(stufe)::numeric, 2) AS avg_stufe,
       COUNT(*) AS n_items
FROM bitkom_bewertungen
GROUP BY company_id, sub_process_id;

-- 6.2 Ø-Stufe je Kernprozess × Dimension
CREATE VIEW v_reifegrad_kp_dim AS
SELECT b.company_id,
       left(b.sub_process_id, 5) AS process_id,   -- 'KP-02'
       ri.dimension,
       ROUND(AVG(b.stufe)::numeric, 2) AS avg_stufe
FROM bitkom_bewertungen b
JOIN ref_items ri ON ri.item_nr = b.item_nr
GROUP BY b.company_id, left(b.sub_process_id, 5), ri.dimension;

-- 6.3 Ø-Stufe je Kernprozess
CREATE VIEW v_reifegrad_kp AS
SELECT company_id,
       left(sub_process_id, 5) AS process_id,
       ROUND(AVG(stufe)::numeric, 2) AS avg_stufe,
       COUNT(*) AS n_items
FROM bitkom_bewertungen
GROUP BY company_id, left(sub_process_id, 5);

-- 6.4 Gesamt-Reifegrad + Beleg-Quote je Mandant
CREATE VIEW v_reifegrad_company AS
SELECT c.company_id, c.name,
       ROUND(AVG(b.stufe)::numeric, 2) AS gesamt_reifegrad,
       COUNT(b.*) AS n_bewertungen,
       ROUND(100.0 * SUM(CASE WHEN length(btrim(b.beleg))>0 THEN 1 ELSE 0 END)/NULLIF(COUNT(b.*),0), 0) AS beleg_quote_pct
FROM companies c
LEFT JOIN bitkom_bewertungen b ON b.company_id = c.company_id
GROUP BY c.company_id, c.name;

-- 6.5 Prozessautomatisierungs-Matrix (intern pro KP, je Teilprozess × 6 Kriterien)
--     Item-Zuordnung wie Baseline: Items 1-6 + 13-18. Systemintegration (5,6) = Medienbruch-Indikator.
CREATE VIEW v_prozessautomatisierung AS
SELECT company_id, sub_process_id, left(sub_process_id,5) AS process_id,
  ROUND(AVG(stufe) FILTER (WHERE item_nr IN (1,2)) ::numeric,2)   AS technologiebasis,
  ROUND(AVG(stufe) FILTER (WHERE item_nr IN (3,4)) ::numeric,2)   AS tools_im_prozess,
  ROUND(AVG(stufe) FILTER (WHERE item_nr IN (5,6)) ::numeric,2)   AS systemintegration,
  ROUND(AVG(stufe) FILTER (WHERE item_nr IN (13,14))::numeric,2)  AS prozessbeschreibung,
  ROUND(AVG(stufe) FILTER (WHERE item_nr IN (15,16))::numeric,2)  AS ausfuehrung,
  ROUND(AVG(stufe) FILTER (WHERE item_nr IN (17,18))::numeric,2)  AS compliance
FROM bitkom_bewertungen
GROUP BY company_id, sub_process_id;

-- 6.6 Cross-funktionale Matrix (prozessübergreifend, je KP × 6 Kriterien)
--     Item-Zuordnung wie Baseline: Items 1-12. Schnittstellen aus ref_prozesse (input/output).
CREATE VIEW v_crossfunktional AS
SELECT b.company_id, left(b.sub_process_id,5) AS process_id,
  rp.process_name, rp.owner_name, rp.input_text, rp.output_text,
  ROUND(AVG(b.stufe) FILTER (WHERE b.item_nr IN (1,2)) ::numeric,2)   AS technologiebasis,
  ROUND(AVG(b.stufe) FILTER (WHERE b.item_nr IN (3,4)) ::numeric,2)   AS tools_im_prozess,
  ROUND(AVG(b.stufe) FILTER (WHERE b.item_nr IN (5,6)) ::numeric,2)   AS systemintegration,
  ROUND(AVG(b.stufe) FILTER (WHERE b.item_nr IN (7,8)) ::numeric,2)   AS prozessbeschreibung,
  ROUND(AVG(b.stufe) FILTER (WHERE b.item_nr IN (9,10))::numeric,2)   AS ausfuehrung,
  ROUND(AVG(b.stufe) FILTER (WHERE b.item_nr IN (11,12))::numeric,2)  AS compliance
FROM bitkom_bewertungen b
LEFT JOIN ref_prozesse rp
  ON rp.company_id = b.company_id AND rp.process_id = left(b.sub_process_id,5)
GROUP BY b.company_id, left(b.sub_process_id,5), rp.process_name, rp.owner_name, rp.input_text, rp.output_text;

-- ============================================================
-- 7. Datenintegrität (Application-Level, da nicht rein SQL)
-- ============================================================
-- * Vollständigkeit: pro bewertetem Teilprozess sollten 30 Items vorliegen (Soft-Check via Report).
-- * Beleg-Pflicht: hart erzwungen (NOT NULL + CHECK auf bitkom_bewertungen.beleg).
-- * Mandantentrennung: alle Fachtabellen tragen company_id; Row-Level-Security empfohlen:
--     ALTER TABLE bitkom_bewertungen ENABLE ROW LEVEL SECURITY;
--     CREATE POLICY tenant_isolation ON bitkom_bewertungen
--       USING (company_id = current_setting('app.company_id')::uuid);

-- ============================================================
-- 8. GEPLANT (v1.2): Enrichment-/Provenance-Layer (BC1 Write-back) [5]
--    Additiv, belegpflichtig, mit Freigabe (HitL-Gate). Baseline bleibt unverändert.
--    Endgültiges Modell hängt an der Klärung "Layer in BC0 oder je BC".
-- ------------------------------------------------------------
-- CREATE TYPE enrichment_status AS ENUM ('vorgeschlagen','bestaetigt','verworfen');
-- CREATE TABLE enrichment (
--   enrichment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--   company_id    UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
--   ref_id        TEXT NOT NULL,           -- stabile ID (KP-XX / KP-XX.TP-Y / ...I-NN)
--   feld          TEXT NOT NULL,
--   wert          JSONB,
--   herkunft      TEXT NOT NULL,           -- 'bc1' + source_ref (Provenance, Pflicht)
--   source_ref    TEXT NOT NULL,
--   status        enrichment_status NOT NULL DEFAULT 'vorgeschlagen',
--   created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
-- );

-- ============================================================
-- Ende v1.1. Projekt-Stack: PostgreSQL (Vorgabe) + MinIO (Belege) + optional NocoDB (Form-Layer).
-- ============================================================
