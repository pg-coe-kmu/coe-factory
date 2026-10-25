-- Gegenprobe v3.16 / v3.17 / v3.18 — nur lesend. Erwartungswerte NoroAI, 25.10.2026.
\pset pager off
\set cid '7c2d5ee9-2a9a-5990-810f-502ea2b2012d'

\echo '== P1 Kommentare (erwartet: v3.17 in beiden)'
SELECT left(obj_description('v_anfrage_teilprozesse'::regclass), 60) AS anfrage_tp,
       left(obj_description('v_freigabe_datenstand'::regclass), 40)  AS datenstand;

\echo '== P2 Trigger und Indizes (erwartet: gate_datenstand, historie; zwei ux_-Indizes)'
SELECT tgname FROM pg_trigger WHERE tgrelid='gate_ereignisse'::regclass AND NOT tgisinternal ORDER BY 1;
SELECT indexname FROM pg_indexes WHERE indexname LIKE 'ux_%name_je_mandant' ORDER BY 1;

\echo '== P3 Datenstand der Freigabe KP-05.TP-1 (erwartet: veraltet f, wenn V7 nur Speichern ohne Aenderung war; sonst t mit prozess_personen)'
SELECT sub_process_id, ereignis_id, datenstand, aenderungen, geaenderte_tabellen, veraltet
  FROM v_freigabe_datenstand WHERE company_id = :'cid' ORDER BY 1;

\echo '== P4 Je Anfrage (erwartet: A-05 freigegeben f, freigabe_veraltet t; A-02 freigegeben t; A-01/-03 f)'
SELECT anfrage_id, sub_process_id, freigegeben, freigabe_veraltet, datenstand_veraltet, im_paket
  FROM v_anfrage_teilprozesse
 WHERE company_id = :'cid' AND anfrage_id IN ('A-2026-01','A-2026-02','A-2026-03','A-2026-05')
 ORDER BY 1;

\echo '== P5 Uebergabestand (erwartet: A-05 uebergabefaehig f — war t)'
SELECT anfrage_id, status, soll, freigegeben, fehlend, uebergabefaehig
  FROM v_anfrage_uebergabe_stand WHERE company_id = :'cid' ORDER BY 1;

\echo '== P6 Portfolio-Kandidaten (erwartet: 0 Zeilen)'
SELECT sub_process_id FROM v_uebergabe_kandidaten WHERE company_id = :'cid';

\echo '== P7 v3.18 Spalten und Rechte (erwartet: paket_id uuid, anfrage_id text; bc3_role REFERENCES t t)'
SELECT column_name, data_type FROM information_schema.columns
 WHERE table_name='ki_laufdaten' AND column_name IN ('paket_id','anfrage_id') ORDER BY 1;
SELECT has_table_privilege('bc3_role','gate_pakete','REFERENCES')  AS pakete,
       has_table_privilege('bc3_role','ref_anfragen','REFERENCES') AS anfragen;
