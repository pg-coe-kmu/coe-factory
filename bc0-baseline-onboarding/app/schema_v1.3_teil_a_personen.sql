-- ============================================================
-- BC0 Onboarding — Schema-Nachtrag v1.3 (Teil A): Personenregister
-- Stand: 12.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- Grundlage: ADR-004 „Identität der Entitäten in BC0" · Issue #149
--
-- Anlass (Bestandsaufnahme vom 12.08.2026 auf der Produktivdatenbank):
--   SELECT DISTINCT owner_name, owner_role FROM ref_prozesse ...  -> 9 Zeilen
--   Darin: sieben reale Personen, zwei unbenannte Externe, eine rotierende
--   Funktion. Verbunden mit „/", „+" und „·". Eike Bischof steht zweimal,
--   einmal mit und einmal ohne Rolle.
--   Ursache: n:m in ein Textfeld gepresst — derselbe Konstruktionsfehler wie
--   zuvor bei den Rollen (S-070).
--
-- Zweiter Anlass: `owner_name` enthält Klarnamen natürlicher Personen und steht
--   in genau der Tabelle, auf die BC1–BC4 Leserechte bekommen sollen (M2).
--   Nach ADR-004 R5 stehen Klarnamen an genau einer Stelle, und die Leserechte
--   laufen über Views ohne Namen.
--
-- ADDITIV. `ref_prozesse.owner_name` und `.owner_role` bleiben vorerst bestehen
--   und werden NICHT verändert. Sie werden erst entfernt, wenn die Migration
--   abgeschlossen und geprüft ist (Teil D, frühestens nach dem Ausrollen).
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v1.3_teil_a_personen.sql
-- Alle Anweisungen sind wiederholbar (IF NOT EXISTS / OR REPLACE).
-- ============================================================


-- ============================================================
-- 15. PERSONENREGISTER
-- ============================================================
-- Personen sind MANDANTENBEZOGEN, nicht global (ADR-004, 2.3). Dieselbe
-- natürliche Person bei zwei Auftraggebern bekommt zwei IDs. Eine
-- mandantenübergreifende Personenidentität wäre eine Zusammenführung
-- personenbezogener Daten über Auftraggeber hinweg — dafür gibt es keine
-- Rechtsgrundlage.
--
-- `name` ist bewusst NULLABLE. „externer Steuerberater" und „externer DSB" sind
-- reale Beteiligte, deren Name nicht erhoben wurde. Sie bekommen trotzdem eine
-- ID — sonst geht der Verweis verloren und die Rolle im Prozess wird unsichtbar.
-- Gefüllt sein muss mindestens eines von `name` oder `funktion`.

CREATE TABLE IF NOT EXISTS ref_personen (
  company_id   UUID    NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  person_id    TEXT    NOT NULL CHECK (person_id ~ '^P-[0-9]{2}$'),
  name         TEXT,                  -- Klarname; EINZIGES personenbezogenes Feld
  funktion     TEXT,                  -- 'Sr. Consultant', 'externer Steuerberater', 'MD'
  rolle_id     TEXT,                  -- optionaler Bezug auf mandant_rollen -> Kostenklasse
  extern       BOOLEAN NOT NULL DEFAULT FALSE,
  organisation TEXT,                  -- bei extern: Kanzlei, Dienstleister, Behörde
  hinweis      TEXT,
  aktiv        BOOLEAN NOT NULL DEFAULT TRUE,
  angelegt_am  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, person_id),
  CONSTRAINT ck_person_bezeichnet
    CHECK (coalesce(btrim(name), '') <> '' OR coalesce(btrim(funktion), '') <> ''),
  -- MATCH SIMPLE: ist rolle_id NULL, greift der Fremdschlüssel nicht. Genau so
  -- gewollt — die Rollenzuordnung ist optional und kommt oft erst mit BC1.
  CONSTRAINT fk_person_rolle
    FOREIGN KEY (company_id, rolle_id) REFERENCES mandant_rollen(company_id, rolle_id)
    ON DELETE CASCADE
);

COMMENT ON TABLE ref_personen IS
  'Personenregister je Mandant (ADR-004). Klarnamen stehen ausschliesslich hier; '
  'alle anderen Tabellen verweisen ueber person_id. BC1-BC4 lesen die Views ohne Namen.';
COMMENT ON COLUMN ref_personen.name IS
  'Klarname. NULL erlaubt fuer unbenannte Externe. Einziges personenbezogenes Feld '
  'im gesamten BC0-Schema — Auskunft und Loeschung nach DSGVO greifen hier.';
COMMENT ON COLUMN ref_personen.aktiv IS
  'FALSE = ausgeschieden. Es wird gesperrt, nicht geloescht (ADR-004 R4), damit '
  'Verweise aus BC1 und aus Gate-Belegen aufloesbar bleiben.';

CREATE INDEX IF NOT EXISTS idx_person_company ON ref_personen(company_id);


-- ============================================================
-- 16. ZUORDNUNG PERSON <-> KERNPROZESS (n:m, mit Funktion)
-- ============================================================
-- Das ist der eigentliche Punkt. `owner_name` konnte nur einen Wert aufnehmen,
-- deshalb stand dort „Ozan Kiraz / Mehdi Louali" (zwei Eigner) und
-- „Engagement Manager (rotierend) · Sponsor: Sergio Morazán Irias" (eine
-- Funktion als Eigner, eine Person als Sponsor). Mit der Funktionsspalte lassen
-- sich beide Fälle korrekt abbilden.
--
-- Die Funktion steht im Primärschlüssel: Dieselbe Person darf in einem Prozess
-- zugleich Eigner und Sponsor sein — das kommt in kleinen Unternehmen vor.

CREATE TABLE IF NOT EXISTS prozess_personen (
  company_id UUID       NOT NULL,
  process_id VARCHAR(8) NOT NULL,
  person_id  TEXT       NOT NULL,
  funktion   TEXT       NOT NULL
    CHECK (funktion IN ('eigner','sponsor','mitwirkend','vertretung')),
  hinweis    TEXT,
  PRIMARY KEY (company_id, process_id, person_id, funktion),
  FOREIGN KEY (company_id, process_id)
    REFERENCES ref_prozesse(company_id, process_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, person_id)
    REFERENCES ref_personen(company_id, person_id) ON DELETE CASCADE
);

COMMENT ON TABLE prozess_personen IS
  'Wer wirkt in welcher Funktion an einem Kernprozess mit (n:m). Loest '
  'ref_prozesse.owner_name ab, das nur einen Wert aufnehmen konnte.';
COMMENT ON COLUMN prozess_personen.funktion IS
  'eigner = verantwortlich · sponsor = traegt die Entscheidung · '
  'mitwirkend = arbeitet mit · vertretung = springt ein';

CREATE INDEX IF NOT EXISTS idx_pp_person ON prozess_personen(company_id, person_id);


-- ============================================================
-- 17. PSEUDONYMISIERTE LESEANSICHTEN FUER BC1-BC4
-- ============================================================
-- ADR-004, 2.6: Das Leserecht wird von den Tabellen auf Views verlagert, soweit
-- personenbezogene Daten betroffen sind. Wer den Namen zu einer person_id
-- braucht, fragt in BC0 nach — das ist dann eine dokumentierte Weitergabe und
-- keine stille Mitlieferung.

-- 17.1 Prozesse ohne Klarnamen. Ersetzt ref_prozesse als Lesequelle.
CREATE OR REPLACE VIEW v_prozesse_lesen AS
SELECT p.company_id,
       p.process_id,
       p.process_name,
       p.beschreibung,
       p.trigger_text,
       p.input_text,
       p.output_text,
       p.created_at,
       -- Der Eigner erscheint nur noch als ID. Mehrere Eigner sind moeglich,
       -- deshalb als sortiertes Array und nicht als Einzelwert.
       (SELECT array_agg(pp.person_id ORDER BY pp.person_id)
          FROM prozess_personen pp
         WHERE pp.company_id = p.company_id
           AND pp.process_id = p.process_id
           AND pp.funktion = 'eigner')   AS eigner_ids,
       (SELECT array_agg(pp.person_id ORDER BY pp.person_id)
          FROM prozess_personen pp
         WHERE pp.company_id = p.company_id
           AND pp.process_id = p.process_id
           AND pp.funktion = 'sponsor')  AS sponsor_ids
  FROM ref_prozesse p;

COMMENT ON VIEW v_prozesse_lesen IS
  'Lesequelle fuer BC1-BC4 anstelle von ref_prozesse. Ohne owner_name und '
  'owner_role — Personen erscheinen ausschliesslich als person_id (ADR-004 R5).';

-- 17.2 Zuordnung mit Funktion und Kostenklasse, ohne Namen.
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
  'Beteiligung je Kernprozess mit Kostenklasse, ohne Klarnamen. Traegt die '
  'Kostenachse fuer BC2 (K1-K5), ohne personenbezogene Daten weiterzugeben.';

-- 17.3 Abdeckungsuebersicht — welcher Prozess hat ueberhaupt einen Eigner?
-- Wird im Gate-Dashboard gebraucht: ein Prozess ohne benannten Eigner ist nicht
-- interviewfaehig, weil BC1 nicht weiss, wen es befragen soll.
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
-- 18. RECHTE
-- ============================================================
-- Die Rolle bc_leser existiert seit dem 08.08.2026 (#148). Falls dieses Skript
-- auf einer Datenbank ohne sie laeuft — etwa im lokalen Testcluster —, wird der
-- Block uebersprungen statt abzubrechen.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN

    -- Lesen erlaubt: die pseudonymisierten Sichten.
    GRANT SELECT ON v_prozesse_lesen,
                    v_prozess_personen_lesen,
                    v_personen_abdeckung
          TO bc_leser;

    -- Lesen NICHT erlaubt: das Register selbst und die Zuordnungstabelle.
    -- ref_personen traegt die Klarnamen (ADR-004 R5). prozess_personen ist
    -- ohne Namen zwar harmlos, wird aber trotzdem gesperrt, damit es genau
    -- einen Lesepfad gibt und nicht zwei.
    REVOKE ALL ON ref_personen     FROM bc_leser;
    REVOKE ALL ON prozess_personen FROM bc_leser;

    -- HINWEIS: Der Entzug des Leserechts auf ref_prozesse steht NICHT hier,
    -- sondern in schema_v1.3_teil_a2_rechte_umstellung.sql. Er ist die einzige
    -- Anweisung des ganzen Nachtrags, die etwas Bestehendes wegnimmt, und
    -- laesst BC1 in „permission denied" laufen, wenn Richard nicht vorher
    -- umgestellt hat. Deshalb getrennt und erst nach Absprache einspielen.

    RAISE NOTICE 'Rechte fuer bc_leser gesetzt: Lesen ueber die neuen Views.';
  ELSE
    RAISE NOTICE 'Rolle bc_leser nicht vorhanden — Rechteblock uebersprungen.';
  END IF;
END $$;


-- ============================================================
-- Ende v1.3 Teil A.
--
-- ACHTUNG, BEVOR BC1 UMGESTELLT WIRD:
--   Der REVOKE auf ref_prozesse aendert eine bestehende Leseberechtigung.
--   Richard muss von ref_prozesse auf v_prozesse_lesen wechseln. Die View
--   enthaelt dieselben Spalten mit Ausnahme von owner_name und owner_role,
--   dafuer zusaetzlich eigner_ids und sponsor_ids.
--   -> vor dem Einspielen ankuendigen, sonst laeuft BC1 in „permission denied".
--
-- Naechster Schritt: Migration der neun Freitextwerte in das Register
--   (migration_v1.3_personen.sql — von Hand erstellt, weil die Trennzeichen
--   uneinheitlich sind).
-- ============================================================
