-- ============================================================
-- BC0 Onboarding — Schema-Nachtrag v1.3 (Teil B): Systemregister
-- Stand: 12.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- Grundlage: ADR-004 „Identität der Entitäten in BC0" · Issue #149
--
-- Anlass (Bestandsaufnahme vom 12.08.2026):
--   SELECT sub_process_id, tools FROM ref_teilprozesse ...  -> 20 Zeilen,
--   darin nur VIER verschiedene Werte. Der Text ist je Kernprozess über alle
--   fünf Teilprozesse identisch kopiert. Die Teilprozess-Granularität ist
--   Schein: erhoben wurde auf Kernprozessebene.
--
--   Zudem vermischen die Werte Systeme mit Bewertungsaussagen:
--     „GitLab + EspoCRM + n8n vollständig digital · Repo-Setup teilautomatisch via n8n"
--   Das sind drei Systeme und zwei Reifegradaussagen in einem Feld. Die
--   Aussagen sind über bitkom_bewertungen bereits erfasst und werden bei der
--   Migration verworfen, nicht kopiert (ADR-004, 2.4).
--
-- ZWEISTUFIG (Entscheidung vom 12.08.2026):
--   ref_systeme_katalog  — global, das Produkt („EspoCRM" ist überall dasselbe")
--   mandant_systeme      — je Mandant, die Instanz mit der Hausbezeichnung
--   Damit kann BC2 später über Mandanten hinweg auswerten, ohne dass
--   „EspoCRM", „Espo CRM" und „Espo" nachträglich zusammengeführt werden müssen.
--
-- ADDITIV. `ref_teilprozesse.tools` bleibt vorerst bestehen und wird nicht
--   verändert.
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v1.3_teil_b_systeme.sql
-- Wiederholbar.
-- ============================================================


-- ============================================================
-- 19. SYSTEMKATALOG (global)
-- ============================================================
-- Sprechende ID nach dem Muster SYS-<Kategorie>-<Kurzname>. Sie taucht in
-- Abstimmungen und Tickets auf, deshalb lesbar und nicht als UUID (ADR-004 R1).

CREATE TABLE IF NOT EXISTS ref_systeme_katalog (
  katalog_id  TEXT PRIMARY KEY CHECK (katalog_id ~ '^SYS-[A-Z0-9]{2,4}-[A-Z0-9]{2,10}$'),
  bezeichnung TEXT NOT NULL,
  kategorie   TEXT NOT NULL CHECK (kategorie IN (
                'crm','erp','dms','pm','bi','automatisierung','kommunikation',
                'entwicklung','buchhaltung','hr','fachanwendung','office','sonstiges')),
  hersteller  TEXT,
  quelloffen  BOOLEAN,
  hinweis     TEXT,
  aktiv       BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE ref_systeme_katalog IS
  'Mandantenuebergreifender Produktkatalog (ADR-004, 2.4). Startbestand unten; '
  'waechst mit jedem erfassten Unternehmen. Der Verweis aus mandant_systeme ist '
  'optional — ein Eigenbau ohne Produktentsprechung bleibt katalogfrei.';

-- Startbestand. Die ersten vier stammen aus dem NoroAI-Bestand, die uebrigen
-- sind im deutschen Mittelstand haeufig und ersparen dem naechsten Mandanten
-- das Anlegen. Die Liste ist ausdruecklich unvollstaendig.
INSERT INTO ref_systeme_katalog (katalog_id, bezeichnung, kategorie, hersteller, quelloffen) VALUES
  ('SYS-CRM-ESPO',   'EspoCRM',            'crm',             'EspoCRM',        TRUE),
  ('SYS-DEV-GITLAB', 'GitLab',             'entwicklung',     'GitLab Inc.',    TRUE),
  ('SYS-AUT-N8N',    'n8n',                'automatisierung', 'n8n GmbH',       TRUE),
  ('SYS-BI-GRAFANA', 'Grafana',            'bi',              'Grafana Labs',   TRUE),
  ('SYS-OFF-M365',   'Microsoft 365',      'office',          'Microsoft',      FALSE),
  ('SYS-BUC-DATEV',  'DATEV',              'buchhaltung',     'DATEV eG',       FALSE),
  ('SYS-BUC-LEX',    'Lexware',            'buchhaltung',     'Haufe-Lexware',  FALSE),
  ('SYS-ERP-SAPB1',  'SAP Business One',   'erp',             'SAP',            FALSE),
  ('SYS-KOM-TEAMS',  'Microsoft Teams',    'kommunikation',   'Microsoft',      FALSE),
  ('SYS-DMS-SHARE',  'SharePoint',         'dms',             'Microsoft',      FALSE)
ON CONFLICT (katalog_id) DO NOTHING;


-- ============================================================
-- 20. SYSTEME BEIM MANDANTEN
-- ============================================================
CREATE TABLE IF NOT EXISTS mandant_systeme (
  company_id  UUID    NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  system_id   TEXT    NOT NULL CHECK (system_id ~ '^S-[0-9]{2}$'),
  katalog_id  TEXT    REFERENCES ref_systeme_katalog(katalog_id),
  bezeichnung TEXT    NOT NULL,   -- wie das Haus es nennt
  einsatz     TEXT,               -- wofuer es verwendet wird
  hinweis     TEXT,
  aktiv       BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (company_id, system_id)
);

COMMENT ON COLUMN mandant_systeme.katalog_id IS
  'Optionaler Verweis auf das Produkt. NULL bei Eigenbauten und bei Angaben, '
  'die kein Produkt benennen (z. B. „Strategie-Cockpit").';

CREATE INDEX IF NOT EXISTS idx_mandsys_katalog ON mandant_systeme(katalog_id);


-- ============================================================
-- 21. ZUORDNUNG SYSTEM <-> TEILPROZESS (n:m)
-- ============================================================
-- `genauigkeit` ist der ehrliche Teil dieser Tabelle. Die Erhebung 2026-05 hat
-- Systeme auf KERNPROZESSEBENE erfasst und den Text über alle fünf Teilprozesse
-- kopiert. Wer die Zuordnung später liest, muss wissen, dass sie nicht je
-- Teilprozess erhoben wurde — sonst hält BC1 sie für belastbarer, als sie ist.

CREATE TABLE IF NOT EXISTS teilprozess_systeme (
  company_id     UUID        NOT NULL,
  sub_process_id VARCHAR(16) NOT NULL,
  system_id      TEXT        NOT NULL,
  nutzung        TEXT        NOT NULL DEFAULT 'genutzt'
                 CHECK (nutzung IN ('fuehrend','genutzt','abgeloest','geplant')),
  genauigkeit    TEXT        NOT NULL DEFAULT 'teilprozess'
                 CHECK (genauigkeit IN ('teilprozess','kernprozess_pauschal')),
  hinweis        TEXT,
  PRIMARY KEY (company_id, sub_process_id, system_id),
  FOREIGN KEY (company_id, sub_process_id)
    REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, system_id)
    REFERENCES mandant_systeme(company_id, system_id) ON DELETE CASCADE
);

COMMENT ON COLUMN teilprozess_systeme.genauigkeit IS
  'kernprozess_pauschal = die Angabe stammt aus einer Erhebung auf '
  'Kernprozessebene und wurde auf alle Teilprozesse verteilt. Nicht als '
  'teilprozessgenaue Aussage verwenden.';

CREATE INDEX IF NOT EXISTS idx_tpsys_system ON teilprozess_systeme(company_id, system_id);


-- ============================================================
-- 22. MEDIENBRUECHE
-- ============================================================
-- Ein Medienbruch ist der Übergang zwischen zwei Systemen ohne durchgehende
-- Datenverbindung. Er war bisher Freitext in `ref_teilprozesse.medienbrueche`.
-- Mit Systemen als Entitäten lässt er sich benennen: von welchem System in
-- welches, auf welche Art.
--
-- Das ist die direkte Grundlage für Bitkom-Item 6 („ohne unnötige
-- Medienbrüche") und für die Gate-Kennzahl `mb`, die bislang aus dem Freitext
-- gezählt wurde. Beide Systemangaben dürfen NULL sein — oft ist nur die eine
-- Seite bekannt („wird ausgedruckt und abgeheftet").

CREATE TABLE IF NOT EXISTS medienbrueche (
  company_id     UUID        NOT NULL,
  bruch_id       TEXT        NOT NULL CHECK (bruch_id ~ '^MB-[0-9]{3}$'),
  sub_process_id VARCHAR(16) NOT NULL,
  von_system_id  TEXT,
  nach_system_id TEXT,
  art            TEXT        NOT NULL CHECK (art IN (
                   'manuelle_uebertragung','druck_scan','mail_anhang',
                   'doppelerfassung','telefon_zuruf','sonstiges')),
  beschreibung   TEXT,
  aufwand_min    NUMERIC(6,1) CHECK (aufwand_min IS NULL OR aufwand_min >= 0),
  aktiv          BOOLEAN     NOT NULL DEFAULT TRUE,
  PRIMARY KEY (company_id, bruch_id),
  FOREIGN KEY (company_id, sub_process_id)
    REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, von_system_id)
    REFERENCES mandant_systeme(company_id, system_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, nach_system_id)
    REFERENCES mandant_systeme(company_id, system_id) ON DELETE CASCADE,
  CONSTRAINT ck_mb_richtung CHECK (von_system_id IS DISTINCT FROM nach_system_id
                                   OR von_system_id IS NULL)
);

COMMENT ON COLUMN medienbrueche.aufwand_min IS
  'Geschaetzter Zeitverlust je Durchlauf in Minuten. BC0 erhebt das nicht — '
  'das Feld wird von BC1 im Interview gefuellt und traegt die ROI-Zeitachse.';

CREATE INDEX IF NOT EXISTS idx_mb_sub ON medienbrueche(company_id, sub_process_id);


-- ============================================================
-- 23. SICHTEN
-- ============================================================

-- 23.1 Systemlandschaft je Mandant: wo wird was eingesetzt?
CREATE OR REPLACE VIEW v_systemlandschaft AS
SELECT ms.company_id,
       ms.system_id,
       ms.bezeichnung,
       ms.katalog_id,
       k.kategorie,
       k.hersteller,
       ms.aktiv,
       count(DISTINCT ts.sub_process_id)                       AS anz_teilprozesse,
       count(DISTINCT substring(ts.sub_process_id from 1 for 5)) AS anz_kernprozesse,
       bool_or(ts.genauigkeit = 'kernprozess_pauschal')        AS nur_pauschal
  FROM mandant_systeme ms
  LEFT JOIN ref_systeme_katalog k ON k.katalog_id = ms.katalog_id
  LEFT JOIN teilprozess_systeme ts
         ON ts.company_id = ms.company_id AND ts.system_id = ms.system_id
 GROUP BY ms.company_id, ms.system_id, ms.bezeichnung, ms.katalog_id,
          k.kategorie, k.hersteller, ms.aktiv;

COMMENT ON VIEW v_systemlandschaft IS
  'Je System: Kategorie, Hersteller und in wie vielen Teilprozessen es vorkommt. '
  'nur_pauschal = TRUE bedeutet, dass keine teilprozessgenaue Angabe vorliegt.';

-- 23.2 Systemabdeckung je Kernprozess — Gegenstueck zu v_personen_abdeckung.
-- Ein Prozess ohne benanntes System ist fuer die Automatisierungsbewertung
-- blind: BC2 kann nicht sagen, woran eine Automatisierung ansetzen wuerde.
CREATE OR REPLACE VIEW v_system_abdeckung AS
SELECT p.company_id,
       p.process_id,
       p.process_name,
       coalesce(z.anz_systeme, 0)      AS anz_systeme,
       coalesce(z.anz_brueche, 0)      AS anz_medienbrueche,
       CASE WHEN coalesce(z.anz_systeme, 0) = 0 THEN 'kein system benannt'
            WHEN coalesce(z.nur_pauschal, FALSE) THEN 'nur pauschal je kernprozess'
            ELSE 'ok' END              AS befund
  FROM ref_prozesse p
  LEFT JOIN (
        SELECT tp.company_id, tp.process_id,
               count(DISTINCT ts.system_id)                      AS anz_systeme,
               count(DISTINCT mb.bruch_id)                       AS anz_brueche,
               bool_and(coalesce(ts.genauigkeit, 'teilprozess')
                        = 'kernprozess_pauschal')                AS nur_pauschal
          FROM ref_teilprozesse tp
          LEFT JOIN teilprozess_systeme ts
                 ON ts.company_id = tp.company_id AND ts.sub_process_id = tp.sub_process_id
          LEFT JOIN medienbrueche mb
                 ON mb.company_id = tp.company_id AND mb.sub_process_id = tp.sub_process_id
                AND mb.aktiv
         GROUP BY tp.company_id, tp.process_id
       ) z ON z.company_id = p.company_id AND z.process_id = p.process_id;


-- ============================================================
-- 24. RECHTE
-- ============================================================
-- Systeme und Medienbrüche enthalten keine personenbezogenen Daten. Sie werden
-- deshalb direkt freigegeben und nicht über Views verschattet.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    GRANT SELECT ON ref_systeme_katalog,
                    mandant_systeme,
                    teilprozess_systeme,
                    medienbrueche,
                    v_systemlandschaft,
                    v_system_abdeckung
          TO bc_leser;
    RAISE NOTICE 'Leserechte fuer Systemregister gesetzt.';
  ELSE
    RAISE NOTICE 'Rolle bc_leser nicht vorhanden — Rechteblock uebersprungen.';
  END IF;
END $$;


-- ============================================================
-- Ende v1.3 Teil B.
--
-- Nicht enthalten und bewusst offen gelassen:
--   * ref_teilprozesse.schnittstellen und .api bleiben Freitext. Schnittstellen
--     zwischen KERNprozessen sind seit v1.2 in prozess_schnittstellen erfasst;
--     die Teilprozessspalte beschreibt etwas anderes (technische Endpunkte) und
--     braucht erst dann ein Register, wenn sie tatsaechlich gepflegt wird.
--   * `medienbrueche` wird von BC0 nur angelegt, nicht gefuellt. Die Erhebung
--     laeuft ueber BC1 (Interview), weil dort die Zeitwerte entstehen.
-- ============================================================
