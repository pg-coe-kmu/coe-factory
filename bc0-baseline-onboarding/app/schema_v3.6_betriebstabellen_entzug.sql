-- Schema v3.6 — Die Betriebstabellen verlassen die Lesegruppe (22.09.2026)
--
-- ANLASS: Vorgang #216 hatte die Klarnamen-Tabellen im Blick, #214 die Frage
-- dahinter: In pg_default_acl setzt postgres fuer das Schema public dauerhaft
--   bc1_role=r/postgres, bc_leser=r/postgres
-- Jede neue BC0-Tabelle ist damit ab dem Anlegen fuer alle vier Kontexte
-- lesbar, ohne dass jemand sie freigibt. BC1 hat genau das am 15.09.2026
-- gefragt, am Beispiel bc_zustellungen.
--
-- GEMESSEN AM 22.09.2026: nicht nur bc_zustellungen -- ALLE fuenf
-- Betriebstabellen waren fuer bc_leser und fuer bc1_role bis bc4_role lesbar,
-- darunter app_benutzer mit den Passwort-Abdruecken.
--
-- DIE ABGRENZUNG, die diese Datei zieht:
--   Fachdaten     -> jeder liest alles. So will es ADR-003, daran aendert
--                    sich nichts.
--   Betriebsdaten -> gehen den nachgelagerten Kontexten nichts an.
--                    Anmeldung, Sitzungen, Anmeldebremse, Konto-Zuordnung und
--                    das Zustellprotokoll gehoeren zum Betrieb von BC0.
--
-- KEIN RISIKO FUER DIE SICHTEN: Eine Sicht laeuft mit den Rechten ihres
-- Eigentuemers. v_anfrage_steller liest app_benutzer_mandanten und liefert
-- nach dem Entzug unveraendert -- am 22.09. gegengeprueft, 5 Zeilen.
--
-- WAS DIESE DATEI NICHT TUT: Die Voreinstellung selbst bleibt stehen. Die
-- NAECHSTE Betriebstabelle in public ist wieder automatisch lesbar. Das ist
-- die eigentliche Frage aus #214 und noch nicht entschieden.
--
-- Ausfuehren: als Eigentuemer, in einer Transaktion.

BEGIN;

REVOKE SELECT ON app_benutzer, app_sitzungen, app_anmeldeversuche,
                 app_benutzer_mandanten, bc_zustellungen
  FROM bc_leser, bc1_role, bc2_role, bc3_role, bc4_role;

\echo '--- 1. Nach dem Entzug (ERWARTET: alles f)'
SELECT t.tab,
       has_table_privilege('bc_leser', t.tab,'SELECT')  AS bc_leser,
       has_table_privilege('bc1_role', t.tab,'SELECT')  AS bc1,
       has_table_privilege('bc2_role', t.tab,'SELECT')  AS bc2,
       has_table_privilege('bc3_role', t.tab,'SELECT')  AS bc3,
       has_table_privilege('bc4_role', t.tab,'SELECT')  AS bc4
  FROM (VALUES ('app_benutzer'),('app_sitzungen'),('app_anmeldeversuche'),
               ('app_benutzer_mandanten'),('bc_zustellungen')) AS t(tab);

\echo '--- 2. Was bleiben MUSS (ERWARTET: alles t)'
SELECT t.tab, has_table_privilege('bc_leser', t.tab,'SELECT') AS bc_leser
  FROM (VALUES ('bitkom_bewertungen'),('v_anfrage_steller'),('v_prozesse_lesen'),
               ('v_teilprozesse_lesen'),('mandant_rollen'),('companies')) AS t(tab);

\echo '--- 3. Die Sicht liefert trotz entzogener Tabelle (ERWARTET: 5)'
SELECT count(*) AS zeilen_in_v_anfrage_steller FROM v_anfrage_steller;

COMMIT;
