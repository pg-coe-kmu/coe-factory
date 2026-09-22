-- Schema v3.7 — Die Rolle „leser" (22.09.2026, Vorgang #211)
--
-- ANLASS: Die Anwendung kannte zwei Rollen, `benutzer` und `admin`. Wer einen
-- Reifegradbericht nur ansehen sollte -- ein Prozessverantwortlicher, ein
-- Kollege aus einem anderen Bounded Context, der Betreuer -- bekam damit
-- zwangslaeufig Schreibrechte. Die Baseline ist aber ein Nachweis, und ein
-- Nachweis, den jeder Betrachter aendern kann, ist keiner.
--
-- ABGRENZUNG ZU DEN DATENBANK-ROLLEN: Diese Datei aendert NICHTS an bc_leser,
-- bc1_role bis bc4_role. Das sind PostgreSQL-Rollen fuer die nachgelagerten
-- Kontexte. `leser` ist eine Rolle der ANWENDUNG, sie steht in
-- app_benutzer.rolle und wird von FastAPI ausgewertet. Die Namensaehnlichkeit
-- ist unguenstig, der Unterschied ist wesentlich:
--   bc_leser  -> ein Kontext liest die Datenbank ueber eine eigene Verbindung
--   leser     -> ein Mensch meldet sich an der PWA an und sieht den Bericht
--
-- WAS DIE ROLLE DARF (festgelegt am 22.09.2026):
--   Bericht, Prozesse, Reifegrad, Historie, Vergleich   ja
--   Belegliste (Dateiname, Datum, Bezug)                ja
--   Beleg oeffnen / Beleg-Volltextsuche                 NEIN
--   Gate-0-Bogen                                        NEIN (war schon Admin)
--   Schreiben, gleich was                               NEIN
--   eigenes Passwort aendern                            ja
--
-- MANDANTEN: wie ein Benutzer. Der Leser bekommt seine Zuordnung in
-- app_benutzer_mandanten und sieht ausschliesslich diese Mandanten. Die Regel
-- in Benutzer.darf_mandanten_sehen() brauchte dafuer keine Zeile.
--
-- WARUM CHECK UND KEINE EIGENE TABELLE: Drei Werte, die sich seit dem
-- 10.08.2026 einmal geaendert haben. Eine Referenztabelle mit Fremdschluessel
-- kostet einen Join in jeder Anmeldung und traegt hier nichts.
--
-- Ausfuehren: als Eigentuemer, in einer Transaktion.

BEGIN;

ALTER TABLE app_benutzer DROP CONSTRAINT IF EXISTS app_benutzer_rolle_check;
ALTER TABLE app_benutzer
  ADD CONSTRAINT app_benutzer_rolle_check
  CHECK (rolle IN ('benutzer','admin','leser'));

\echo '--- 1. Die Bedingung steht (ERWARTET: eine Zeile mit leser darin)'
SELECT conname, pg_get_constraintdef(oid) AS bedingung
  FROM pg_constraint
 WHERE conrelid = 'app_benutzer'::regclass
   AND conname  = 'app_benutzer_rolle_check';

\echo '--- 2. Bestehende Konten unveraendert (ERWARTET: nur benutzer und admin)'
SELECT rolle, count(*) AS konten FROM app_benutzer GROUP BY rolle ORDER BY rolle;

\echo '--- 3. Ein unbekannter Wert wird weiterhin abgewiesen (ERWARTET: Fehler)'
-- Absichtlich in einem Sicherungspunkt, damit die Transaktion weiterlaeuft.
SAVEPOINT probe;
INSERT INTO app_benutzer(benutzer_id,email,name,passwort_hash,rolle)
VALUES ('probe-v37','probe-v37@example.invalid','Probe','x','gast');
ROLLBACK TO SAVEPOINT probe;

\echo '--- 4. leser wird angenommen und sofort wieder zurueckgenommen (ERWARTET: INSERT 0 1)'
SAVEPOINT probe2;
INSERT INTO app_benutzer(benutzer_id,email,name,passwort_hash,rolle)
VALUES ('probe-v37','probe-v37@example.invalid','Probe','x','leser');
ROLLBACK TO SAVEPOINT probe2;

\echo '--- 5. Die Betriebstabelle bleibt entzogen (ERWARTET: alles f, vgl. v3.6)'
SELECT has_table_privilege('bc_leser','app_benutzer','SELECT')  AS bc_leser,
       has_table_privilege('bc1_role','app_benutzer','SELECT')  AS bc1;

COMMIT;

-- Ein Leser wird angelegt wie jedes andere Konto:
--   python benutzer_verwalten.py anlegen --email <adresse> --name "<Name>" \
--          --rolle leser --mandant <company_id>
--   python benutzer_verwalten.py mandanten --email <adresse> --mandant <company_id>
-- Ohne den zweiten Aufruf sieht der Leser keinen einzigen Mandanten -- das ist
-- gewollt und dieselbe Regel wie bei der Rolle `benutzer`.
