-- Schema v3.5 — bc1_role verliert die Direktrechte auf die Klarnamen-Tabellen (21.09.2026)
--
-- ANLASS: BC1 hat am 15.09.2026 schriftlich erklaert, beide Rechte nicht zu
-- brauchen und auch in Etappe 2 nicht zu brauchen:
--   "Das direkte SELECT von bc1_role auf prozess_personen (gemessen 12.09.)
--    nutzen wir nicht [...] Rollen kommen aus mandant_rollen, Eigner und
--    Sponsor aus v_prozesse_lesen, der Steller aus v_anfrage_steller.
--    Ihr koennt es entziehen. Dauerregel bei uns: kein Fremdschluessel von
--    bc1.* auf ref_personen oder prozess_personen."
--
-- WARUM ES UEBERFAELLIG IST: ref_personen traegt Klarnamen und seit v1.5
-- dienstliche E-Mail und Telefon (ADR-004 R5: genau eine Stelle). Das
-- Sichten-Modell haelt Klarnamen von den nachgelagerten Kontexten fern --
-- ein direktes Tabellenrecht umgeht es vollstaendig. Vorgang #216.
--
-- WICHTIG (Befund 23.08.2026, SICHERHEIT.md 3.8): Die Rechte liegen DIREKT
-- an bc1_role, nicht ueber bc_leser. Ein REVOKE ... FROM bc_leser wirkt hier
-- nicht -- es muss bc1_role selbst treffen.
--
-- NICHT ANGETASTET: companies. BC1s Loeschkaskade liest public.companies mit
-- den Rechten von bc1_role (Brief 15.09.). Welcher der beiden Wege bleibt --
-- direktes SELECT oder Mitgliedschaft in bc_leser -- ist vor Etappe 4c
-- gesondert zu entscheiden und NICHT Gegenstand dieser Datei.
--
-- Ausfuehren: als Eigentuemer, in einer Transaktion.

BEGIN;

\echo '--- 1. Ausgangsstand (ERWARTET: je eine Zeile mit has=t)'
SELECT 'ref_personen'     AS tabelle,
       has_table_privilege('bc1_role','ref_personen','SELECT')     AS has
UNION ALL
SELECT 'prozess_personen',
       has_table_privilege('bc1_role','prozess_personen','SELECT');

REVOKE SELECT ON ref_personen     FROM bc1_role;
REVOKE SELECT ON prozess_personen FROM bc1_role;

-- Gegenprobe 1: die beiden Rechte sind weg
\echo '--- 2. Nach dem Entzug (ERWARTET: beide f)'
SELECT 'ref_personen'     AS tabelle,
       has_table_privilege('bc1_role','ref_personen','SELECT')     AS has
UNION ALL
SELECT 'prozess_personen',
       has_table_privilege('bc1_role','prozess_personen','SELECT');

-- Gegenprobe 2: was BC1 wirklich braucht, geht weiter
\echo '--- 3. Die Wege, die BC1 nutzt (ERWARTET: alle t)'
SELECT 'v_prozesse_lesen'          AS objekt, has_table_privilege('bc1_role','v_prozesse_lesen','SELECT')          AS has
UNION ALL SELECT 'v_prozess_personen_lesen', has_table_privilege('bc1_role','v_prozess_personen_lesen','SELECT')
UNION ALL SELECT 'v_anfrage_steller',        has_table_privilege('bc1_role','v_anfrage_steller','SELECT')
UNION ALL SELECT 'mandant_rollen',           has_table_privilege('bc1_role','mandant_rollen','SELECT')
UNION ALL SELECT 'companies',                has_table_privilege('bc1_role','companies','SELECT');

-- Gegenprobe 3: kein Fremdschluessel aus bc1.* auf die beiden Tabellen
-- (ERWARTET: 0 Zeilen -- sonst bricht der Entzug etwas)
\echo '--- 4. Fremdschluessel aus bc1 auf die Klarnamen-Tabellen (ERWARTET: 0 Zeilen)'
SELECT c.conname, c.conrelid::regclass AS von, c.confrelid::regclass AS nach
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
 WHERE c.contype = 'f'
   AND n.nspname = 'bc1'
   AND c.confrelid::regclass::text IN ('ref_personen','prozess_personen');

COMMIT;
