-- BC0 · Schema v3.35a — Korrektur zu v3.35 (05.11.2026)
-- Befund Browserprobe nach v3.35: GET /api/companies/{cid}/prozessdok antwortet 501
-- ("Tabelle prozess_dokumentation nicht vorhanden"). Ursache: v3.35 hat v_prozess_dokumentation_stand neu
-- angelegt und dabei die Spalten tage_seit_pruefung und pruefung_faellig weggelassen, die app.py abfragt.
-- Eigener Fehler: die App-Abfragen wurden vor v3.35 nicht gegen die neue Sicht geprueft.
-- Korrektur: beide Spalten wieder anhaengen (gleiche Regel wie v3.32: >183 Tage = Pruefung faellig).
BEGIN;
CREATE OR REPLACE VIEW v_prozess_dokumentation_stand AS
SELECT d.company_id, d.sub_process_id, left(d.sub_process_id, 5) AS process_id, d.paket_id, d.durchlauf_nr,
       d.bezeichnung, d.version, d.in_betrieb_seit,
       (SELECT count(*) FROM prozess_dok_werkzeuge w WHERE (w.company_id,w.sub_process_id,w.paket_id,w.durchlauf_nr)=(d.company_id,d.sub_process_id,d.paket_id,d.durchlauf_nr)) AS werkzeuge,
       (SELECT count(*) FROM prozess_dok_agenten a   WHERE (a.company_id,a.sub_process_id,a.paket_id,a.durchlauf_nr)=(d.company_id,d.sub_process_id,d.paket_id,d.durchlauf_nr)) AS agenten,
       (SELECT count(*) FROM prozess_dok_tests t     WHERE (t.company_id,t.sub_process_id,t.paket_id,t.durchlauf_nr)=(d.company_id,d.sub_process_id,d.paket_id,d.durchlauf_nr)) AS tests,
       d.geprueft_am,
       (d.aenderbar_durch IS NULL OR btrim(d.aenderbar_durch) = '') AS niemand_kann_aendern,
       CASE WHEN d.geprueft_am IS NULL THEN NULL ELSE (CURRENT_DATE - d.geprueft_am) END AS tage_seit_pruefung,
       CASE WHEN d.geprueft_am IS NULL THEN TRUE ELSE (CURRENT_DATE - d.geprueft_am) > 183 END AS pruefung_faellig
  FROM prozess_dokumentation d;
\echo '--- Probe: die Abfrage der App laeuft (ERWARTET: 0 Zeilen, kein Fehler)'
SELECT sub_process_id,process_id,bezeichnung,version,werkzeuge,agenten,tests,
       geprueft_am::text AS geprueft_am,tage_seit_pruefung,pruefung_faellig,niemand_kann_aendern
  FROM v_prozess_dokumentation_stand WHERE company_id = '7c2d5ee9-2a9a-5990-810f-502ea2b2012d' ORDER BY sub_process_id;
COMMIT;
