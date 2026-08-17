-- ============================================================
-- BC0 — Migration v1.3 (B): Freitext `ref_teilprozesse.tools` -> Systemregister
-- Stand: 12.08.2026 · Autor: Simeon Ehmer
--
-- VORAUSSETZUNG: schema_v1.3_teil_b_systeme.sql ist eingespielt.
--
-- WAS VERWORFEN WIRD (und warum das kein Datenverlust ist):
--   Die vier Freitextwerte enthalten neben Systemen auch Aussagen über den
--   Reifegrad und über die Arbeitsweise:
--     „vollständig digital", „teilautomatisch", „menschzentriert",
--     „BPMN dokumentiert", „Menschenzentrierter Klausur-Prozess"
--   Das sind keine Systeme. Die Reifegradaussagen stehen bereits in
--   bitkom_bewertungen (600 Zeilen, je Item mit Beleg); sie hier ein zweites
--   Mal abzulegen, hieße zwei Wahrheiten zu pflegen. Der Freitext bleibt
--   ohnehin unverändert stehen, es geht also nichts verloren.
--
-- GENAUIGKEIT:
--   Alle Zuordnungen werden als `kernprozess_pauschal` markiert. Der Grund
--   steht in Teil B, Abschnitt 21: Der Text ist je Kernprozess über alle fünf
--   Teilprozesse identisch kopiert, war also nie teilprozessgenau. Wer das
--   später liest, soll es wissen.
--
-- WIEDERHOLBAR. ON CONFLICT DO NOTHING, keine bestehende Zeile wird geändert.
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f migration_v1.3_systeme.sql
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Systeme des Mandanten anlegen
-- ------------------------------------------------------------
-- S-01 und S-02 bleiben ohne Katalogverweis: „Strategie-Cockpit" und
-- „OKR-Tooling" benennen kein Produkt, sondern eine Gattung. Sobald im
-- Interview herauskommt, welches Werkzeug tatsächlich im Einsatz ist, wird der
-- Katalogverweis nachgetragen.

INSERT INTO mandant_systeme (company_id, system_id, katalog_id, bezeichnung, einsatz, hinweis)
SELECT c.company_id, v.system_id, v.katalog_id, v.bezeichnung, v.einsatz, v.hinweis
  FROM (SELECT DISTINCT company_id FROM ref_teilprozesse
         WHERE tools IS NOT NULL AND length(btrim(tools)) > 0) c
 CROSS JOIN (VALUES
   ('S-01', NULL,             'Strategie-Cockpit', 'Strategieplanung und Zielverfolgung',
            'Gattungsbegriff, kein Produkt benannt. Im Interview klären, welches Werkzeug.'),
   ('S-02', NULL,             'OKR-Tooling',       'Zielsystem (Objectives & Key Results)',
            'Gattungsbegriff, kein Produkt benannt. Im Interview klären, welches Werkzeug.'),
   ('S-03', 'SYS-CRM-ESPO',   'EspoCRM',           'Kundendaten, Angebote, Lead-Scoring', NULL),
   ('S-04', 'SYS-DEV-GITLAB', 'GitLab',            'Quellcode, Issues, Projektsteuerung', NULL),
   ('S-05', 'SYS-AUT-N8N',    'n8n',               'Automatisierung, Repo-Setup',         NULL),
   ('S-06', 'SYS-BI-GRAFANA', 'Grafana',           'Engagement-Dashboard',                NULL)
 ) AS v(system_id, katalog_id, bezeichnung, einsatz, hinweis)
ON CONFLICT (company_id, system_id) DO NOTHING;


-- ------------------------------------------------------------
-- 2. Zuordnung zu den Teilprozessen
-- ------------------------------------------------------------
-- Abgleich über den normalisierten Freitext, wie bei den Personen.
-- `nutzung = 'fuehrend'` dort, wo der Text ein System als zentral ausweist
-- („EspoCRM zentral"); sonst 'genutzt'.

WITH zuordnung(quelltext, system_id, nutzung) AS (VALUES
  ('Strategie-Cockpit + OKR-Tooling · Menschenzentrierter Klausur-Prozess',
   'S-01', 'genutzt'),
  ('Strategie-Cockpit + OKR-Tooling · Menschenzentrierter Klausur-Prozess',
   'S-02', 'genutzt'),

  ('EspoCRM zentral, BPMN dokumentiert · Lead-Scoring teilautomatisch',
   'S-03', 'fuehrend'),

  ('GitLab + EspoCRM + n8n vollständig digital · Repo-Setup teilautomatisch via n8n',
   'S-04', 'fuehrend'),
  ('GitLab + EspoCRM + n8n vollständig digital · Repo-Setup teilautomatisch via n8n',
   'S-03', 'genutzt'),
  ('GitLab + EspoCRM + n8n vollständig digital · Repo-Setup teilautomatisch via n8n',
   'S-05', 'genutzt'),

  ('GitLab Issues + Grafana Engagement-Dashboard · Sprint-Reviews + Standups menschzentriert',
   'S-04', 'fuehrend'),
  ('GitLab Issues + Grafana Engagement-Dashboard · Sprint-Reviews + Standups menschzentriert',
   'S-06', 'genutzt')
)
INSERT INTO teilprozess_systeme (company_id, sub_process_id, system_id, nutzung, genauigkeit, hinweis)
SELECT tp.company_id, tp.sub_process_id, z.system_id, z.nutzung, 'kernprozess_pauschal',
       'aus tools übernommen am 12.08.2026'
  FROM ref_teilprozesse tp
  JOIN zuordnung z
    ON regexp_replace(btrim(tp.tools), '\s+', ' ', 'g') = z.quelltext
ON CONFLICT (company_id, sub_process_id, system_id) DO NOTHING;

COMMIT;


-- ============================================================
-- 3. KONTROLLE
-- ============================================================
\echo '--- 3.1 Teilprozesse mit tools, aber ohne Zuordnung (muss leer sein):'
SELECT tp.sub_process_id, tp.tools
  FROM ref_teilprozesse tp
 WHERE tp.tools IS NOT NULL
   AND btrim(tp.tools) <> ''
   AND NOT EXISTS (SELECT 1 FROM teilprozess_systeme ts
                    WHERE ts.company_id = tp.company_id
                      AND ts.sub_process_id = tp.sub_process_id)
 ORDER BY 1;

\echo '--- 3.2 Systemlandschaft:'
SELECT system_id, bezeichnung, katalog_id, kategorie,
       anz_kernprozesse, anz_teilprozesse, nur_pauschal
  FROM v_systemlandschaft ORDER BY 1;

\echo '--- 3.3 Abdeckung je Kernprozess:'
SELECT process_id, anz_systeme, anz_medienbrueche, befund
  FROM v_system_abdeckung ORDER BY 1;
