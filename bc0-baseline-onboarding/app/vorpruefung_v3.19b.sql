-- Vorpruefung v3.19b (25.10.2026) — NUR LESEND, aendert nichts.
-- Ausfuehren als postgres auf der Produktion, Ausgabe an Claude.
\echo '--- V1 v3.17 eingespielt? (ERWARTET: t | t)'
SELECT to_regclass('v_freigabe_datenstand') IS NOT NULL AS sicht_da,
       to_regproc('teilprozess_unbenannt') IS NOT NULL AS funktion_da;

\echo '--- V2 Erhebungen je Status (ERWARTET: nur offen/abgeschlossen/verworfen)'
SELECT status, count(*) FROM ref_erhebungen GROUP BY status ORDER BY status;

\echo '--- V3 Aktuelle Freigaben, deren Erhebung verworfen ist (ERWARTET: 0 Zeilen)'
SELECT f.company_id, f.sub_process_id, f.ereignis_id, f.bc0_stand, e.status
  FROM v_gate_freigabe_aktuell f
  JOIN ref_erhebungen e ON e.company_id = f.company_id AND e.erhebung_id = f.bc0_stand
 WHERE f.stand = 'freigegeben' AND e.status = 'verworfen';

\echo '--- V4 Anfrage-Bezuege direkt auf unbenannte Teilprozesse (ERWARTET: 0 Zeilen)'
SELECT p.company_id, p.anfrage_id, p.sub_process_id, t.sub_process_name
  FROM anfrage_prozesse p
  JOIN ref_teilprozesse t ON t.company_id = p.company_id AND t.sub_process_id = p.sub_process_id
 WHERE teilprozess_unbenannt(t.sub_process_name);

\echo '--- V5 Kernprozess-Bezuege mit unbenannten aktiven Teilprozessen (Info: fallen kuenftig aus der SOLL-Liste)'
SELECT p.company_id, p.anfrage_id, p.process_id, t.sub_process_id, t.sub_process_name
  FROM anfrage_prozesse p
  JOIN ref_teilprozesse t ON t.company_id = p.company_id AND t.process_id = p.process_id AND t.aktiv
 WHERE p.sub_process_id IS NULL AND teilprozess_unbenannt(t.sub_process_name);

\echo '--- V6 Trigger auf anfrage_prozesse (Info, ERWARTET: kein anfrage_prozesse_benannt)'
SELECT tgname FROM pg_trigger WHERE tgrelid = 'anfrage_prozesse'::regclass AND NOT tgisinternal ORDER BY 1;
