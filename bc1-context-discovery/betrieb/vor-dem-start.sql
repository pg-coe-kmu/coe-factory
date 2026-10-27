-- Prüfung vor jedem Start von BC1 mit neuer Anfrage oder neuem Stand — NUR LESEND.
-- Aufruf (als bc1_role):
--   psql "$BC1_DB_DSN" -v mandant=<uuid> -v anfrage=A-JJJJ-NN -f betrieb/vor-dem-start.sql
-- Erwartung je Block steht in der Überschrift. Herkunft: Vorbedingung aus B8 und C1a (4a);
-- die Paketkennung wechselt mit jeder Anfrage, offene Sitzungen liefen danach ins Leere.
SET default_transaction_read_only = on;
\pset pager off
\pset null '(null)'

\echo '=== M0  Wer misst? (erwartet: bc1_role, read_only = on) ==='
SELECT current_user AS benutzer, current_setting('default_transaction_read_only') AS read_only;

\echo '=== M1  Sitzungen nach Paketfassung und Status (erwartet: keine Zeile mit aktiv / wartet_auf_antwort / fehler_fortsetzbar) ==='
SELECT state->>'schema_version' AS paketfassung,
       state->>'status'         AS status,
       count(*)                 AS anzahl,
       max(aktualisiert_am)     AS zuletzt
  FROM bc1.sessions
 WHERE company_id = :'mandant'
 GROUP BY 1, 2
 ORDER BY 1, 2;

\echo '=== M2  Offene Entwürfe in bc1.prozessprofil (erwartet: 0 Zeilen) ==='
SELECT focus_step_id, profil_version, paket_version, erstellt_am
  FROM bc1.prozessprofil
 WHERE company_id = :'mandant' AND status = 'in_erhebung'
 ORDER BY focus_step_id;

\echo '=== M3  Ausstehender Abschluss: Sitzung fertig, Profil nicht fertig (erwartet: 0 Zeilen) ==='
SELECT s.session_id, s.state->>'schema_version' AS paketfassung,
       p.status AS profilstatus, s.aktualisiert_am
  FROM bc1.sessions s
  LEFT JOIN bc1.profil_write_status w
         ON w.session_id = s.session_id AND w.company_id = s.company_id
  LEFT JOIN bc1.prozessprofil p
         ON p.company_id = w.company_id AND p.focus_step_id = w.focus_step_id
        AND p.profil_version = w.profil_version
 WHERE s.company_id = :'mandant'
   AND s.state->>'status' = 'fertig'
   AND p.status IS DISTINCT FROM 'fertig'
 ORDER BY s.aktualisiert_am;

\echo '=== M4  Leserechte, die Dienst und Start brauchen (erwartet: 0 Zeilen = nichts fehlt) ==='
SELECT t AS fehlendes_select_recht
  FROM unnest(ARRAY[
        'v_bewertung_aktuell', 'v_prozesse_lesen', 'v_teilprozesse_lesen',
        'v_systeme_lesen', 'companies', 'ref_erhebungen',
        'v_anfrage_prozessbezug', 'v_anfrage_teilprozesse', 'mandant_rollen'
       ]) AS t
 WHERE NOT has_table_privilege(current_user, t, 'SELECT');

\echo '=== M5  Die Anfrage für diesen Lauf (erwartet: Status zugeordnet, mindestens ein Teilprozess) ==='
SELECT b.anfrage_id, b.status,
       (SELECT count(*) FROM v_anfrage_teilprozesse t
         WHERE t.company_id = b.company_id AND t.anfrage_id = b.anfrage_id) AS teilprozesse
  FROM v_anfrage_prozessbezug b
 WHERE b.company_id = :'mandant' AND b.anfrage_id = :'anfrage';
