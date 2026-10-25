-- ============================================================
-- BC0 · Schema v3.9 — Direktes, dauerhaftes SELECT auf companies fuer bc1_role
-- Stand: 23.09.2026 · Simeon Ehmer
-- Anlass: P-07 / Richards Befund in PR #201 (14.09.2026, Punkt 2):
--   DELETE FROM companies kaskadiert nach bc1.sessions und bc1.prozessprofil.
--   BC1s Freeze-Trigger laesst nur los, weil er prueft, ob die companies-Zeile
--   im selben Statement schon weg ist - und liest dafuer public.companies MIT
--   DEN RECHTEN VON bc1_role. Verliert bc1_role dieses SELECT, bricht die
--   Loeschung an einer Stelle, die BC1 nicht testen kann und BC0 nicht sieht.
--   Richard bat ausdruecklich um eine Zusicherung, keine Nebenwirkung einer
--   Gruppenmitgliedschaft: "wir nehmen es als harte Nebenbedingung in
--   Etappe 4c auf und fassen das Recht beim Aufraeumen der direkten Grants
--   nicht an."
--
-- STAND VOR DIESEM SKRIPT: bc1_role hat SELECT auf companies ausschliesslich
--   indirekt, ueber die Mitgliedschaft in bc_leser (gemessen 18.09., traegt).
--   Waehrend R-06/#262 gerade bc_leser-Rechte beschneidet (Betriebstabellen),
--   ist eine nur indirekte Abhaengigkeit die falsche Grundlage fuer eine
--   Dauerzusage.
--
-- ENTSCHEIDUNG SIMEON, 23.09.2026: explizites GRANT statt impliziter
--   Gruppenmitgliedschaft — sichtbar, kommentiert, und beim Aufraeumen der
--   direkten Grants in Etappe 4c nicht versehentlich zu entziehen.
--
-- WAS DIESES SKRIPT TUT
--   GRANT SELECT ON companies TO bc1_role — direkt, zusaetzlich zur
--   bestehenden Mitgliedschaft in bc_leser (die bleibt unangetastet).
--
-- WAS ES NICHT TUT
--   Aendert nichts an bc_leser, an anderen BC-Rollen, an keiner anderen
--   Tabelle.
--
-- EINSPIELEN (nach Backup):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema_v3.9_companies_dauerrecht_bc1.sql
-- ============================================================

BEGIN;

GRANT SELECT ON companies TO bc1_role;

COMMENT ON TABLE companies IS
  'Mandantentabelle. bc1_role hat seit v3.9 (23.09.2026) ein EXPLIZITES, '
  'DAUERHAFTES SELECT hier - unabhaengig von der Mitgliedschaft in bc_leser. '
  'Grund: BC1s Freeze-Trigger prueft beim Loeschen eines Mandanten, ob die '
  'companies-Zeile im selben Statement schon weg ist, und liest dafuer mit '
  'den Rechten von bc1_role. Verliert bc1_role dieses SELECT, bricht die '
  'DSGVO-Loeschkaskade bei BC1 lautlos (P-07, PR #201). Dieses Recht bleibt '
  'beim Aufraeumen direkter Grants in Etappe 4c ausdruecklich UNANGETASTET.';

COMMIT;

-- ============================================================
-- KONTROLLE — nach dem Einspielen
-- ============================================================
-- 1) Direktes Recht vorhanden (Herkunft "GRANT", nicht nur Gruppe):
--    SELECT has_table_privilege('bc1_role','companies','SELECT');  -> t
-- 2) Weiterhin ueber die Gruppe abgedeckt (unveraendert, zur Kontrolle):
--    SELECT pg_has_role('bc1_role','bc_leser','MEMBER');  -> t
-- 3) Keine andere Rolle/Tabelle beruehrt:
--    SELECT grantee, privilege_type FROM information_schema.role_table_grants
--      WHERE table_name = 'companies' ORDER BY 1,2;
