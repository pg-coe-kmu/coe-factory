-- Schema v3.9 — weitere Rollen je Person (29.09.2026, Vorgang 911)
--
-- ANLASS: Simeon, 29.09.2026: "jede Person kann mehrere Rollen wahrnehmen".
-- Bisher traegt ref_personen genau EIN Feld rolle_id.
--
-- ENTSCHEIDUNG (Simeon, 29.09.2026): Hauptrolle + weitere Rollen.
--   * ref_personen.rolle_id bleibt die HAUPTROLLE. Aus ihr liest
--     v_prozesse_lesen.owner_rolle_id (v3.4) die Rolle des Eigners, und BC1/BC2
--     lesen sie als process_owner_rolle_id (contracts/bc1-to-bc2/lesen.sql).
--     Diese Kette bleibt unveraendert.
--   * Weitere Rollen stehen in der neuen Tabelle person_rollen.
--   Rein additiv: keine Spalte geaendert, keine Sicht geaendert.
--
-- RECHTE: Die Tabelle traegt keine Klarnamen (nur person_id und rolle_id), ist
-- aber Personenbezug wie prozess_personen. Wie dort (v3.5, #216) bekommt
-- bc1_role KEIN Direktrecht; die Voreinstellung in pg_default_acl wuerde es
-- sonst automatisch vergeben (Befund #214, dauerhafter Weg #262).
--
-- Die Anwendung legt die Tabelle beim Start selbst an (ENTITAET_DDL_PG). Diese
-- Datei ist deckungsgleich und traegt die Rechte und die Gegenproben.
--
-- Ausfuehren: als Eigentuemer, in einer Transaktion.

BEGIN;

CREATE TABLE IF NOT EXISTS person_rollen (
  company_id UUID NOT NULL,
  person_id  TEXT NOT NULL,
  rolle_id   TEXT NOT NULL,
  PRIMARY KEY (company_id, person_id, rolle_id),
  FOREIGN KEY (company_id, person_id) REFERENCES ref_personen(company_id, person_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, rolle_id)  REFERENCES mandant_rollen(company_id, rolle_id)
);

COMMENT ON TABLE person_rollen IS
  'Weitere Rollen je Person (v3.9). Die Hauptrolle steht in ref_personen.rolle_id '
  'und bleibt Quelle fuer v_prozesse_lesen.owner_rolle_id.';

REVOKE ALL ON person_rollen FROM bc1_role;

\echo '--- 1. Tabelle vorhanden (ERWARTET: 1)'
SELECT count(*) FROM information_schema.tables WHERE table_name = 'person_rollen';

\echo '--- 2. Kein Direktrecht fuer bc1_role (ERWARTET: f)'
SELECT has_table_privilege('bc1_role','person_rollen','SELECT') AS bc1_liest;

\echo '--- 3. Eigner-Kette unveraendert (ERWARTET: Spalte owner_rolle_id vorhanden)'
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'v_prozesse_lesen' AND column_name = 'owner_rolle_id';

\echo '--- 4. Bestand (ERWARTET: 0 Zeilen direkt nach dem Einspielen)'
SELECT count(*) AS zeilen FROM person_rollen;

COMMIT;
