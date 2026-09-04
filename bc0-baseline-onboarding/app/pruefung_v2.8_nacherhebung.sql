-- Pruefung v2.8 — Nacherhebung, gegen eine Testdatenbank mit der Kette v1.1.1 … v2.8.
-- Nie gegen Produktiv. Erwartungswerte stehen als Kommentar an jeder Probe.
\set ON_ERROR_STOP off
BEGIN;
SELECT set_config('bc0.benutzer', (SELECT benutzer_id::text FROM app_benutzer LIMIT 1), false) \gset
INSERT INTO companies(company_id, name, status, created_at) VALUES ('11111111-1111-4111-8111-111111111128','Pruef v2.8','laeuft',now());
-- 1. erste Kennung des Monats                                   → E-JJJJ-MM
SELECT erhebung_naechste_kennung('11111111-1111-4111-8111-111111111128') = 'E-'||to_char(current_date,'YYYY-MM') AS probe_1;
INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) VALUES ('11111111-1111-4111-8111-111111111128', erhebung_naechste_kennung('11111111-1111-4111-8111-111111111128'), 'Erst', current_date, 'offen');
-- 2. zweite Kennung                                             → …-2
SELECT erhebung_naechste_kennung('11111111-1111-4111-8111-111111111128') = 'E-'||to_char(current_date,'YYYY-MM')||'-2' AS probe_2;
-- 3. CHECK: -1 ist keine gueltige Kennung                       → ERROR check constraint
SAVEPOINT p3;
INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) VALUES ('11111111-1111-4111-8111-111111111128', 'E-'||to_char(current_date,'YYYY-MM')||'-1', 'falsch', current_date, 'offen');
ROLLBACK TO SAVEPOINT p3;
-- 4. CHECK: -2 ist gueltig                                      → INSERT 0 1
INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) VALUES ('11111111-1111-4111-8111-111111111128', 'E-'||to_char(current_date,'YYYY-MM')||'-2', 'Nach', current_date, 'verworfen');
-- 5. verworfene zaehlt mit                                      → …-3
SELECT erhebung_naechste_kennung('11111111-1111-4111-8111-111111111128') = 'E-'||to_char(current_date,'YYYY-MM')||'-3' AS probe_5;
-- 6. Sperre aus v2.6 bleibt: Bewertung in abgeschlossene        → ERROR erhebung … abgeschlossen
UPDATE ref_erhebungen SET status='abgeschlossen' WHERE company_id='11111111-1111-4111-8111-111111111128' AND erhebung_id='E-'||to_char(current_date,'YYYY-MM');
INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie) VALUES ('11111111-1111-4111-8111-111111111128','KP-01','P','Steuerungsprozess');
INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name) VALUES ('11111111-1111-4111-8111-111111111128','KP-01.TP-1','KP-01',1,'T');
SAVEPOINT p6;
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am)
 VALUES ('11111111-1111-4111-8111-111111111128','E-'||to_char(current_date,'YYYY-MM'),'KP-01.TP-1.I-01','KP-01.TP-1',1,3,'b','chat',now());
ROLLBACK TO SAVEPOINT p6;
-- 7. anderer Monat: wieder Basis                                → E-2030-01
SELECT erhebung_naechste_kennung('11111111-1111-4111-8111-111111111128', DATE '2030-01-15') = 'E-2030-01' AS probe_7;
ROLLBACK;
