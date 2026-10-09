-- Schema v3.11 — KI-Controlling (04.10.2026, Vorgang 915)
--
-- Fachkonzept: 13_Konzepte_Architektur/BC0_Konzept_KI-Transformation_KI-Controlling_v1_04-10-2026.md (S-153)
--
-- Bausteine 3-6, erfasst von BC0:
--   ki_schulungen          LongLife Learning: Schulung je Person, Termin, erledigt
--   ki_research_bereiche   Verantwortliche/r je Bereich fuer den Stand der Technik
--   ki_research_notizen    monatliche Notiz je Bereich
--   ki_wissensdb           Wissensdatenbank des Mandanten (vorhanden, Stand, Verantwortung)
--   ki_strategie           KI-Strategie (Sachstand, Verantwortung, Ueberarbeitung)
--   ki_meilensteine        Meilensteine der Strategie (max. 3 Jahre)
--
-- Bausteine 1-2, GESCHRIEBEN VON BC4 (Entscheidung Simeon 04.10.2026: "BC4 wird und
-- MUSS es zurueckschreiben"):
--   ki_laufdaten           eine Zeile je Modellaufruf: Prozess, Modell, Token, Kosten,
--                          Status, korrigiert (Mensch hat das Ergebnis geaendert/verworfen)
--   Daraus: Tokenverbrauch je Modell/Prozess, Regelkarte (Korrekturquote je Tag).
--
-- RECHTE
--   * bc4_role: SELECT, INSERT auf ki_laufdaten (+ Sequenz) — BC4 schreibt, aendert nicht.
--   * Personenbezug (ki_schulungen, ki_research_*): wie prozess_personen/person_rollen
--     KEIN Lesen fuer bc_leser/bc1_role (pg_default_acl wuerde es vergeben, #214/#262).
--   * anon/authenticated: seit v3.10 ohne Voreinstellung; hier zur Sicherheit erneut entzogen.
--
-- Die Anwendung legt die Tabellen beim Start selbst an (KIC_DDL_PG); diese Datei ist
-- deckungsgleich und traegt Rechte und Gegenproben. Ausfuehren als postgres, eine Transaktion.

BEGIN;

CREATE TABLE IF NOT EXISTS ki_schulungen (
  id          BIGSERIAL PRIMARY KEY,
  company_id  UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  person_id   TEXT,
  thema       TEXT NOT NULL,
  termin      DATE,
  erledigt_am DATE,
  nachweis    TEXT
);
CREATE TABLE IF NOT EXISTS ki_research_bereiche (
  company_id  UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  bereich     TEXT NOT NULL,
  person_id   TEXT,
  PRIMARY KEY (company_id, bereich)
);
CREATE TABLE IF NOT EXISTS ki_research_notizen (
  id          BIGSERIAL PRIMARY KEY,
  company_id  UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  bereich     TEXT NOT NULL,
  datum       DATE NOT NULL,
  person_id   TEXT,
  notiz       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ki_wissensdb (
  company_id      UUID PRIMARY KEY REFERENCES companies(company_id) ON DELETE CASCADE,
  vorhanden       TEXT NOT NULL CHECK (vorhanden IN ('ja','nein','im_aufbau')),
  system          TEXT,
  ort             TEXT,
  person_id       TEXT,
  aktualisiert_am DATE,
  takt_tage       INTEGER
);
CREATE TABLE IF NOT EXISTS ki_strategie (
  company_id       UUID PRIMARY KEY REFERENCES companies(company_id) ON DELETE CASCADE,
  sachstand        TEXT NOT NULL CHECK (sachstand IN ('keine','entwurf','beschlossen','in_umsetzung')),
  beschreibung     TEXT,
  person_id        TEXT,
  beschlossen_am   DATE,
  ueberarbeitet_am DATE
);
CREATE TABLE IF NOT EXISTS ki_meilensteine (
  id          BIGSERIAL PRIMARY KEY,
  company_id  UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  titel       TEXT NOT NULL,
  zieldatum   DATE NOT NULL,
  erreicht_am DATE
);
CREATE TABLE IF NOT EXISTS ki_laufdaten (
  id             BIGSERIAL PRIMARY KEY,
  company_id     UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  zeitpunkt      TIMESTAMPTZ NOT NULL DEFAULT now(),
  process_id     TEXT,
  sub_process_id TEXT,
  kontext        TEXT NOT NULL DEFAULT 'betrieb',
  modell         TEXT NOT NULL,
  input_tokens   INTEGER,
  output_tokens  INTEGER,
  kosten_eur     NUMERIC(12,6),
  status         TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','fehler','abgebrochen')),
  korrigiert     BOOLEAN,
  dauer_ms       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ki_laufdaten_co_zeit ON ki_laufdaten(company_id, zeitpunkt);

REVOKE ALL ON ki_schulungen, ki_research_bereiche, ki_research_notizen FROM bc_leser, bc1_role;
REVOKE ALL ON ki_schulungen, ki_research_bereiche, ki_research_notizen, ki_wissensdb,
              ki_strategie, ki_meilensteine, ki_laufdaten FROM anon, authenticated;
GRANT SELECT, INSERT ON ki_laufdaten TO bc4_role;
GRANT USAGE ON SEQUENCE ki_laufdaten_id_seq TO bc4_role;

\echo '--- 1. Tabellen vorhanden (ERWARTET: 7)'
SELECT count(*) FROM information_schema.tables
 WHERE table_schema='public' AND table_name IN ('ki_schulungen','ki_research_bereiche','ki_research_notizen',
       'ki_wissensdb','ki_strategie','ki_meilensteine','ki_laufdaten');

\echo '--- 2. BC4 darf Laufdaten schreiben und lesen, nicht aendern (ERWARTET: t t f f)'
SELECT has_table_privilege('bc4_role','ki_laufdaten','INSERT') AS ins,
       has_table_privilege('bc4_role','ki_laufdaten','SELECT') AS sel,
       has_table_privilege('bc4_role','ki_laufdaten','UPDATE') AS upd,
       has_table_privilege('bc4_role','ki_laufdaten','DELETE') AS del;

\echo '--- 3. Personenbezug nicht fuer BC1 (ERWARTET: f f f)'
SELECT has_table_privilege('bc1_role','ki_schulungen','SELECT'),
       has_table_privilege('bc1_role','ki_research_bereiche','SELECT'),
       has_table_privilege('bc1_role','ki_research_notizen','SELECT');

\echo '--- 4. Supabase-Rollen ohne Recht (ERWARTET: 0)'
SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname LIKE 'ki\_%'
   AND (has_table_privilege('anon',c.oid,'SELECT') OR has_table_privilege('authenticated',c.oid,'SELECT'));

COMMIT;
