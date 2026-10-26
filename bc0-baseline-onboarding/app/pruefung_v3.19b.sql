-- Gegenprobe v3.19b (25.10.2026). Laeuft in EINER Transaktion und rollt am Ende
-- ZURUECK — an den Daten aendert sich nichts. Ausfuehren als postgres.
BEGIN;

\echo '--- P1 Eingespielt? (ERWARTET: t | t)'
SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'anfrage_prozesse_benannt') AS trigger_da,
       EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_name = 'v_freigabe_datenstand' AND column_name = 'erhebung_verworfen') AS spalte_da;

\echo '--- P2 Unbenannter Teilprozess an Anfrage (ERWARTET: abgewiesen)'
DO $$
DECLARE r RECORD; ergebnis TEXT;
BEGIN
  SELECT a.company_id, a.anfrage_id, t.process_id, t.sub_process_id INTO r
    FROM ref_anfragen a
    JOIN ref_teilprozesse t ON t.company_id = a.company_id
   ORDER BY a.anfrage_id, t.sub_process_id LIMIT 1;
  UPDATE ref_teilprozesse SET sub_process_name = 'Teilprozess 99'
   WHERE company_id = r.company_id AND sub_process_id = r.sub_process_id;
  BEGIN
    DELETE FROM anfrage_prozesse WHERE company_id = r.company_id AND anfrage_id = r.anfrage_id
       AND sub_process_id = r.sub_process_id;
    INSERT INTO anfrage_prozesse(company_id, anfrage_id, process_id, sub_process_id, rolle, zuordnung_quelle)
    VALUES (r.company_id, r.anfrage_id, r.process_id, r.sub_process_id, 'beteiligt', 'anfrage');
    ergebnis := 'NICHT abgewiesen — FEHLER';
  EXCEPTION WHEN check_violation THEN
    ergebnis := 'abgewiesen: ' || SQLERRM;
  END;
  RAISE NOTICE 'P2 %', ergebnis;
END $$;

\echo '--- P3 Benannter Teilprozess an Anfrage (ERWARTET: angenommen)'
DO $$
DECLARE r RECORD; ergebnis TEXT;
BEGIN
  SELECT a.company_id, a.anfrage_id, t.process_id, t.sub_process_id INTO r
    FROM ref_anfragen a
    JOIN ref_teilprozesse t ON t.company_id = a.company_id
   WHERE NOT teilprozess_unbenannt(t.sub_process_name)
     AND NOT EXISTS (SELECT 1 FROM anfrage_prozesse p WHERE p.company_id = a.company_id
                        AND p.anfrage_id = a.anfrage_id AND p.process_id = t.process_id
                        AND coalesce(p.sub_process_id,'') = t.sub_process_id)
   ORDER BY a.anfrage_id, t.sub_process_id LIMIT 1;
  BEGIN
    INSERT INTO anfrage_prozesse(company_id, anfrage_id, process_id, sub_process_id, rolle, zuordnung_quelle)
    VALUES (r.company_id, r.anfrage_id, r.process_id, r.sub_process_id, 'beteiligt', 'anfrage');
    ergebnis := 'angenommen (' || r.anfrage_id || ' / ' || r.sub_process_id || ')';
  EXCEPTION WHEN check_violation THEN
    ergebnis := 'abgewiesen — FEHLER: ' || SQLERRM;
  END;
  RAISE NOTICE 'P3 %', ergebnis;
END $$;

\echo '--- P4 Stand vor dem Verwerfen: aktuelle Freigaben mit Erhebung (Info)'
SELECT d.sub_process_id, f.bc0_stand, d.veraltet, d.geaenderte_tabellen
  FROM v_freigabe_datenstand d JOIN v_gate_freigabe_aktuell f ON f.ereignis_id = d.ereignis_id
 ORDER BY 1;

\echo '--- P5 Erhebung einer Freigabe verwerfen (ERWARTET: veraltet t, "Erhebung … verworfen")'
UPDATE ref_erhebungen e SET status = 'verworfen'
  FROM (SELECT f.company_id, f.bc0_stand FROM v_gate_freigabe_aktuell f
         WHERE f.stand = 'freigegeben' AND f.bc0_stand IS NOT NULL
         ORDER BY f.entschieden_am DESC LIMIT 1) x
 WHERE e.company_id = x.company_id AND e.erhebung_id = x.bc0_stand;
SELECT d.sub_process_id, d.veraltet, d.erhebung_verworfen, d.geaenderte_tabellen
  FROM v_freigabe_datenstand d WHERE d.erhebung_verworfen IS NOT NULL ORDER BY 1;

\echo '--- P6 Anfrage-Sicht dazu (ERWARTET: freigegeben f, datenstand_veraltet t)'
SELECT a.anfrage_id, a.sub_process_id, a.freigegeben, a.datenstand_veraltet
  FROM v_anfrage_teilprozesse a
  JOIN v_freigabe_datenstand d ON d.ereignis_id = a.freigabe_ereignis_id
 WHERE d.erhebung_verworfen IS NOT NULL ORDER BY 1, 2;

ROLLBACK;
\echo '--- Zurueckgerollt. Nichts geaendert.'
