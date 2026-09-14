-- ============================================================
-- BC0 Onboarding — Schema-Nachtrag v1.5: Dienstliche Kontaktdaten
-- Stand: 18.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- Grundlage: Entscheidung des Auftraggebers vom 17.08.2026 · ADR-004 R5
--
-- Anlass: Wer im Interview eine Rückfrage hat, findet heute keinen Weg zur
--   Person. Der Prozess kennt eine person_id, das Register einen Namen — und
--   damit endet die Spur. Die Angabe wurde bisher außerhalb der Anwendung
--   geführt, in Verteilerlisten, die niemand pflegt.
--
-- ERFASST WIRD NUR DAS DIENSTLICHE. Keine private Mailadresse, keine
--   Privatnummer, auch nicht bei Externen: Die dienstliche Erreichbarkeit ist
--   für die Durchführung des Auftrags erforderlich, die private nicht. Eine
--   Datenbank, die beides aufnehmen kann, nimmt über kurz oder lang beides auf.
--
-- ADDITIV und wiederholbar (ADD COLUMN IF NOT EXISTS). Beide Spalten sind
--   NULLABLE — wie `name`. „Externer Steuerberater" ohne erhobene Nummer bleibt
--   ein gültiger Eintrag; ein Pflichtfeld erzeugte hier nur Erfindungen.
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v1.5_kontaktdaten.sql
-- ============================================================


-- ============================================================
-- 21. KONTAKTDATEN AM PERSONENREGISTER
-- ============================================================
-- Die Spalten stehen in ref_personen und nirgends sonst. Das ist dieselbe
-- Entscheidung wie bei `name` (ADR-004 R5) und aus demselben Grund: Auskunft,
-- Berichtigung und Löschung nach DSGVO greifen an genau einer Stelle. Stünde
-- die Mailadresse zusätzlich in einer Zuordnungstabelle, wäre eine Löschung
-- eine Suche statt eines UPDATE.

ALTER TABLE ref_personen ADD COLUMN IF NOT EXISTS email   TEXT;
ALTER TABLE ref_personen ADD COLUMN IF NOT EXISTS telefon TEXT;

COMMENT ON COLUMN ref_personen.email IS
  'DIENSTLICHE Mailadresse. Keine private Adresse — auch bei Externen nicht. '
  'Personenbezogen und deshalb nach ADR-004 R5 an derselben Stelle wie der '
  'Klarname: ausschliesslich hier. Geht NICHT in die pseudonymisierten Sichten '
  'und damit nicht an BC1-BC4. NULL erlaubt, wenn nicht erhoben.';
COMMENT ON COLUMN ref_personen.telefon IS
  'DIENSTLICHE Rufnummer (Durchwahl, Zentrale oder Diensthandy). Bewusst ohne '
  'Formatzwang: Durchwahl, Landesvorwahl und Mobilnummer stehen im Haus in '
  'mehreren Schreibweisen, und keine davon ist falsch. Sonst wie email — '
  'ADR-004 R5, nicht in den Sichten, NULL erlaubt.';

COMMENT ON TABLE ref_personen IS
  'Personenregister je Mandant (ADR-004). Klarname UND dienstliche Kontaktdaten '
  'stehen ausschliesslich hier; alle anderen Tabellen verweisen ueber person_id. '
  'BC1-BC4 lesen die Views ohne Namen und ohne Kontaktdaten.';


-- ============================================================
-- 22. DIE SICHTEN BLEIBEN, WIE SIE SIND — NACHGEZOGEN ZUM BEWEIS
-- ============================================================
-- Keine der drei Leseansichten aus v1.3 Teil A verwendet `SELECT *` auf
-- ref_personen; sie zählen ihre Spalten auf und hätten sich durch die beiden
-- neuen Spalten von selbst nicht erweitert. Sie werden hier trotzdem erneut
-- angelegt — nicht weil sie sich ändern, sondern damit dieses Skript die
-- Zusicherung selbst trägt: Wer v1.5 einspielt, hat danach nachweislich
-- Sichten ohne Kontaktdaten, auch wenn dazwischen jemand eine Sicht von Hand
-- ersetzt hat. CREATE OR REPLACE ist wiederholbar.
--
-- v_prozesse_lesen liest ref_personen gar nicht und bleibt deshalb unberührt.

-- 22.1 Zuordnung mit Funktion und Kostenklasse — ohne Namen, ohne Kontakt.
CREATE OR REPLACE VIEW v_prozess_personen_lesen AS
SELECT pp.company_id,
       pp.process_id,
       pp.person_id,
       pp.funktion        AS beteiligung,
       pe.funktion        AS funktionsbezeichnung,   -- 'MD', 'Lead DevOps' — kein Name
       pe.rolle_id,
       r.klasse           AS kostenklasse,
       pe.extern,
       pe.organisation,
       pe.aktiv
  FROM prozess_personen pp
  JOIN ref_personen pe
    ON pe.company_id = pp.company_id AND pe.person_id = pp.person_id
  LEFT JOIN mandant_rollen r
    ON r.company_id = pe.company_id AND r.rolle_id = pe.rolle_id;

COMMENT ON VIEW v_prozess_personen_lesen IS
  'Beteiligung je Kernprozess mit Kostenklasse, ohne Klarnamen und ohne '
  'Kontaktdaten. Traegt die Kostenachse fuer BC2 (K1-K5), ohne personenbezogene '
  'Daten weiterzugeben. Wer eine Rueckfrage hat, fragt in BC0 nach — das ist '
  'dann eine dokumentierte Weitergabe und keine stille Mitlieferung.';

-- 22.2 Abdeckungsuebersicht — zaehlt nur, liest keine Personenspalten.
CREATE OR REPLACE VIEW v_personen_abdeckung AS
SELECT p.company_id,
       p.process_id,
       p.process_name,
       coalesce(z.anz_eigner, 0)     AS anz_eigner,
       coalesce(z.anz_beteiligt, 0)  AS anz_beteiligt,
       CASE
         WHEN coalesce(z.anz_eigner, 0) = 0 THEN 'kein eigner benannt'
         WHEN coalesce(z.anz_eigner, 0) > 1 THEN 'mehrere eigner'
         ELSE 'ok'
       END AS befund
  FROM ref_prozesse p
  LEFT JOIN (
        SELECT company_id, process_id,
               count(*) FILTER (WHERE funktion = 'eigner') AS anz_eigner,
               count(DISTINCT person_id)                   AS anz_beteiligt
          FROM prozess_personen
         GROUP BY company_id, process_id
       ) z ON z.company_id = p.company_id AND z.process_id = p.process_id;

COMMENT ON VIEW v_personen_abdeckung IS
  'Je Kernprozess: ist ein Eigner benannt? Ein Prozess ohne Eigner ist nicht '
  'interviewfaehig — BC1 wuesste nicht, wen es befragen soll.';


-- ============================================================
-- 23. RECHTE
-- ============================================================
-- Unverändert gegenüber v1.3 Teil A, hier nur wiederholt: Das Leserecht liegt
-- auf den Sichten, nicht auf ref_personen. Mit den Kontaktdaten wiegt der
-- Unterschied schwerer als vorher — ein SELECT auf die Tabelle lieferte jetzt
-- einen vollständigen Verteiler.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    GRANT SELECT ON v_prozesse_lesen,
                    v_prozess_personen_lesen,
                    v_personen_abdeckung
          TO bc_leser;
    REVOKE ALL ON ref_personen     FROM bc_leser;
    REVOKE ALL ON prozess_personen FROM bc_leser;
    RAISE NOTICE 'Rechte fuer bc_leser bestaetigt: Lesen nur ueber die Views.';
  ELSE
    RAISE NOTICE 'Rolle bc_leser nicht vorhanden — Rechteblock uebersprungen.';
  END IF;
END $$;


-- ============================================================
-- KONTROLLE — muss leer bleiben
-- ============================================================
-- Keine Sicht darf die beiden Spalten führen. Die Abfrage prüft das an der
-- Quelle (pg_attribute über alle Views des Schemas) und nicht an einer Liste
-- von Namen, die beim nächsten View wieder veraltet wäre.
--
--   SELECT c.relname AS sicht, a.attname AS spalte
--     FROM pg_class c
--     JOIN pg_namespace n ON n.oid = c.relnamespace
--     JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
--    WHERE c.relkind = 'v' AND n.nspname = 'public'
--      AND a.attname IN ('email', 'telefon')
--    ORDER BY 1, 2;
--
-- Ende v1.5.
-- ============================================================
