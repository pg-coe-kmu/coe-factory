\set ON_ERROR_STOP on
-- NUR TESTGERUEST: SIM-Mandant wie in Produktion (Stand Inventur 15.11.)
INSERT INTO app_benutzer (benutzer_id,email,name,passwort_hash,rolle) VALUES ('958515eb-a8a6-4b02-a2ac-d4794ad11113','admin@test.invalid','Admin Test','x','admin') ON CONFLICT DO NOTHING;
INSERT INTO companies (company_id,name) VALUES ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','SIMULATION - NoroAI Consulting GmbH');
INSERT INTO ref_prozesse (company_id,process_id,process_name,kategorie) VALUES
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','KP-01','Strategie','Kerngeschäftsprozess'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','KP-02','Auftragserfassung','Kerngeschäftsprozess');
INSERT INTO ref_teilprozesse (company_id,sub_process_id,process_id,step_no,sub_process_name) VALUES
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','KP-01.TP-1','KP-01',1,'Klausur'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','KP-01.TP-2','KP-01',2,'Teilprozess 2'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','KP-02.TP-1','KP-02',1,'Bestellung sichten');
INSERT INTO ref_erhebungen (company_id,erhebung_id,bezeichnung,stand,status,methode) VALUES
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','E-2026-10','Erhebung 10/2026','2026-10-01','offen','Self-Rating je Teilprozess, 30 Bitkom-Items, Belegpflicht');
INSERT INTO mandant_rollen (company_id,rolle_id,bezeichnung,klasse) VALUES
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','R-01','Geschäftsführung','K1'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','R-02','Sachbearbeitung','K3');
