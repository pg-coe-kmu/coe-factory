-- Gegenprobe v3.16 — nur lesend. Erwartungswerte fuer NoroAI (Stand 25.10.2026).
\set cid '7c2d5ee9-2a9a-5990-810f-502ea2b2012d'

-- P1 Kommentar eingespielt -> beginnt mit 'Die SOLL-Liste ... (v3.16'
SELECT left(obj_description('v_anfrage_teilprozesse'::regclass), 120) AS p1;

-- P2 Je Teilprozess der Anfragen 01, 02, 03, 05
--   A-2026-01 KP-06.TP-2  freigegeben f (keine Freigabe)  veraltet f/NULL
--   A-2026-02 KP-05.TP-1  freigegeben t  anfrage_bc1_stand NULL  veraltet f  im_paket t
--   A-2026-03 KP-06.TP-1  freigegeben f (keine Freigabe)  veraltet f/NULL
--   A-2026-05 KP-05.TP-1  freigegeben f  freigabe_bc1_stand NULL  anfrage_bc1_stand 3  veraltet t
SELECT anfrage_id, sub_process_id, freigegeben, freigabe_ereignis_id,
       freigabe_bc1_stand, anfrage_bc1_stand, freigabe_veraltet, im_paket
  FROM v_anfrage_teilprozesse
 WHERE company_id = :'cid'
   AND anfrage_id IN ('A-2026-01','A-2026-02','A-2026-03','A-2026-05')
 ORDER BY anfrage_id, sub_process_id;

-- P3 Uebergabestand
--   A-2026-01  soll 1  freigegeben 0  uebergabefaehig f
--   A-2026-02  soll 1  freigegeben 1  vollstaendig t  uebergabefaehig f (unveraendert)
--   A-2026-03  soll 1  freigegeben 0  uebergabefaehig f
--   A-2026-05  soll 1  freigegeben 0  fehlend {KP-05.TP-1}  uebergabefaehig f   <- war t
SELECT anfrage_id, status, soll, freigegeben, fehlend, vollstaendig, uebergabefaehig
  FROM v_anfrage_uebergabe_stand
 WHERE company_id = :'cid'
 ORDER BY anfrage_id;

-- P4 Portfolio-Weg unberuehrt: Kandidaten wie vorher (erwartet: 0 Zeilen,
--    Ereignis 4 steckt schon in Paket 880f95f7 und 8c7d19c1)
SELECT sub_process_id, freigabe_ereignis_id FROM v_uebergabe_kandidaten
 WHERE company_id = :'cid';
