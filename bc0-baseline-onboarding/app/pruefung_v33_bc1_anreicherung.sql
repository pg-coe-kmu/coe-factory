-- Pruefung v3.3 — BC1-Anreicherung am Gate (#P4), 18.09.2026
--
-- Rein lesend. Prueft die Abfrage, die _bc1_anreicherung() fuehrt, gegen die
-- Produktion. Die Erwartungswerte stehen VOR dem Lauf fest — eine Gegenprobe
-- taugt nur, wenn sie das tut.
--
-- Aufruf:
--   docker run --rm --env-file /opt/bc0/.env postgres:17 \
--     sh -c 'psql "$DATABASE_URL" -f -' < pruefung_v33_bc1_anreicherung.sql

\echo '--- 1. Gibt es die Quelle ueberhaupt?'
-- ERWARTET: t
SELECT to_regclass('bc1.prozessprofil') IS NOT NULL AS quelle_da,
       to_regclass('bc1.profil_rollen')  IS NOT NULL AS rollen_da;

\echo '--- 2. Die juengste fertige Fassung je Teilprozess (NoroAI)'
-- ERWARTET: genau 3 Zeilen, alle profil_version = 2, erhebung_id = E-2026-08
--   KP-05.TP-1: 260 / 260 /  45 / 25 / geschaetzt / 50
--   KP-06.TP-1:  40 /  40 / 120 / 60 / geschaetzt / 70
--   KP-06.TP-2: 180 / 180 / 180 / 90 / geschaetzt / 60
-- rollen_anzahl ERWARTET: 0 bei allen dreien (bc1.profil_rollen ist leer)
SELECT DISTINCT ON (p.focus_step_id)
       p.focus_step_id, p.profil_version, p.erhebung_id,
       p.frequency_per_year, p.executions_per_run,
       p.total_duration_minutes, p.focus_step_duration_minutes,
       p.focus_step_duration_source, p.focus_step_duration_confidence_pct,
       (SELECT count(*) FROM bc1.profil_rollen r
         WHERE r.company_id = p.company_id
           AND r.focus_step_id = p.focus_step_id
           AND r.profil_version = p.profil_version) AS rollen_anzahl
  FROM bc1.prozessprofil p
 WHERE p.company_id::text = '7c2d5ee9-2a9a-5990-810f-502ea2b2012d'
   AND p.status = 'fertig'
 ORDER BY p.focus_step_id, p.profil_version DESC;

\echo '--- 3. Entwuerfe werden NICHT gelesen'
-- ERWARTET: 0 — es gibt derzeit keine Zeile mit status = in_erhebung.
-- Steht hier spaeter eine, darf sie in Abfrage 2 nicht auftauchen.
SELECT count(*) AS entwuerfe FROM bc1.prozessprofil WHERE status = 'in_erhebung';

\echo '--- 4. Der Uebungsmandant hat keine BC1-Profile'
-- ERWARTET: 0 — dort bleibt am_zug also wartet_bc1 mit dem alten Wortlaut.
SELECT count(*) AS uebungsmandant
  FROM bc1.prozessprofil
 WHERE company_id::text = '3e163e8a-18a2-4bde-b0ba-b7986de670f7';

\echo '--- 5. Leserecht: laeuft die Abfrage unter der Rolle der Anwendung?'
-- ERWARTET: t — sonst faengt _bc1_anreicherung() den Fehler ab und liefert {},
-- das Gate saehe weiterhin wartet_bc1 und niemand wuesste warum.
SELECT has_table_privilege(current_user, 'bc1.prozessprofil', 'SELECT') AS darf_profil,
       has_table_privilege(current_user, 'bc1.profil_rollen',  'SELECT') AS darf_rollen,
       current_user;
