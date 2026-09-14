-- Pruefung v2.9 — Vorher / Nachher, gegen eine Testdatenbank mit der Kette v1.1.1 … v2.9.
-- Nie gegen Produktiv. Erwartungswerte stehen als Kommentar an jeder Probe.
BEGIN;
\set C '''11111111-1111-4111-8111-111111111129'''
INSERT INTO companies(company_id, name, status, created_at) VALUES (:C, 'Pruef v2.9', 'laeuft', now());
INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie) VALUES (:C,'KP-01','P','Steuerungsprozess');
INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name)
  VALUES (:C,'KP-01.TP-1','KP-01',1,'T1'), (:C,'KP-01.TP-2','KP-01',2,'T2');
INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) VALUES
  (:C,'E-2026-06','Erst','2026-06-30','offen'),
  (:C,'E-2026-08','Nach','2026-08-24','offen'),
  (:C,'E-2026-09','Offen','2026-09-04','offen'),
  (:C,'E-2026-09-2','Verworfen','2026-09-04','offen');
-- (Status erst nach den Bewertungen — die Sperre aus v2.6 greift sonst, wie sie soll.)
-- E-2026-06: beide TPs, Items 1..4, alles 3
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am)
SELECT :C,'E-2026-06', tp||'.I-0'||i, tp, i, 3, 'b', 'chat', now()
  FROM (VALUES ('KP-01.TP-1'),('KP-01.TP-2')) t(tp), generate_series(1,4) i;
-- E-2026-08: TP-1 Items 1,2 auf 5; Item 3 bleibt 3
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES
  (:C,'E-2026-08','KP-01.TP-1.I-01','KP-01.TP-1',1,5,'b','chat',now()),
  (:C,'E-2026-08','KP-01.TP-1.I-02','KP-01.TP-1',2,5,'b','chat',now()),
  (:C,'E-2026-08','KP-01.TP-1.I-03','KP-01.TP-1',3,3,'b','chat',now());
-- E-2026-09 (offen): TP-2 Item 1 auf 1; verworfene traegt 4 in TP-2 Item 2 (darf nie zaehlen)
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES
  (:C,'E-2026-09','KP-01.TP-2.I-01','KP-01.TP-2',1,1,'b','chat',now()),
  (:C,'E-2026-09-2','KP-01.TP-2.I-02','KP-01.TP-2',2,4,'b','chat',now());

UPDATE ref_erhebungen SET status='abgeschlossen' WHERE company_id=:C AND erhebung_id IN ('E-2026-06','E-2026-08');
UPDATE ref_erhebungen SET status='verworfen' WHERE company_id=:C AND erhebung_id='E-2026-09-2';

-- 1. Reihenfolge und fest                       → E-06 1 t · E-08 2 t · E-09 3 f · E-09-2 4 f
SELECT erhebung_id, rang, fest FROM v_erhebung_reihenfolge WHERE company_id = :C ORDER BY rang;
-- 2. Stand nach E-2026-06: beide TPs 3.00        → TP-1 3.00/4 · TP-2 3.00/4
SELECT * FROM reifegrad_tp_bis(:C, 'E-2026-06') ORDER BY 1;
-- 3. Stand nach E-2026-08: TP-1 = (5+5+3+3)/4 = 4.00, TP-2 unveraendert 3.00
SELECT * FROM reifegrad_tp_bis(:C, 'E-2026-08') ORDER BY 1;
-- 4. Vergleich 06 → 08                           → TP-1 3.00 4.00 +1.00 geaendert 2 · TP-2 3.00 3.00 0 0
SELECT * FROM reifegrad_vergleich(:C, 'E-2026-06', 'E-2026-08');
-- 5. Stand nach der offenen E-2026-09: TP-2 = (1+3+3+3)/4 = 2.50; verworfene 4 zaehlt nicht
SELECT * FROM reifegrad_tp_bis(:C, 'E-2026-09') ORDER BY 1;
-- 6. verworfene als Grenze: leer                → 0
SELECT count(*) FROM bewertung_aktuell_bis(:C, 'E-2026-09-2');
-- 7. v_bewertung_aktuell (aktueller Stand) = Stand nach der juengsten nicht verworfenen  → t
SELECT (SELECT round(avg(stufe),2) FROM v_bewertung_aktuell WHERE company_id = :C)
     = (SELECT round(avg(stufe),2) FROM bewertung_aktuell_bis(:C, 'E-2026-09')) AS probe_7;
ROLLBACK;
