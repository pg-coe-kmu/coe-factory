-- Pruefung v3.36 am Testgeruest (nicht fuer Produktion). Jede Zeile in "p" ist ein Befund ja/NEIN.
\set ON_ERROR_STOP 1
\set c '''7c2d5ee9-2a9a-5990-810f-502ea2b2012d'''
\set p '''cc7f4d1b-4c71-4cfa-92c3-46a395080e4b'''
CREATE TEMP TABLE p(nr int, was text, ok text);
GRANT ALL ON p TO bc4_role, bc3_role;

-- Hilfsfunktion: Anweisung muss scheitern
CREATE OR REPLACE FUNCTION pg_temp.muss_scheitern(sql text) RETURNS text LANGUAGE plpgsql AS $f$
BEGIN EXECUTE sql; RETURN 'NEIN (lief durch)'; EXCEPTION WHEN OTHERS THEN RETURN 'ja: '||left(SQLERRM,70); END $f$;
GRANT EXECUTE ON FUNCTION pg_temp.muss_scheitern(text) TO bc4_role, bc3_role;

SET ROLE bc4_role;
-- 1. Agentenblatt fuer Durchlauf 1 anlegen (BC4)
INSERT INTO kir_agentenblatt(company_id,sub_process_id,paket_id,durchlauf_nr,bezeichnung,zweck,ersteller,version,ablauf,grenzen)
VALUES (:c,'KP-06.TP-2',:p,1,'Reiseanfrage-Extraktion','Daten aus E-Mail','BC4','0.1','Mail lesen, Felder fuellen','nur deutsch');
INSERT INTO kir_agentenblatt_werkzeuge VALUES (:c,'KP-06.TP-2',:p,1,1,NULL,'FastAPI','0.115','laufzeit',NULL,true,'MIT',NULL);
INSERT INTO kir_agentenblatt_agenten(company_id,sub_process_id,paket_id,durchlauf_nr,agent_id,bezeichnung,aufgabe,eskalation,modell)
VALUES (:c,'KP-06.TP-2',:p,1,'A01','Extraktor','Felder erkennen','an Mensch','claude-opus-5-5');
INSERT INTO p VALUES (1,'BC4 legt Agentenblatt je Durchlauf an','ja');
-- 2. Pruefung nachtragen geht einmal, Inhalt aendern nicht
UPDATE kir_agentenblatt SET geprueft_am=current_date, geprueft_von='BC4-T1' WHERE sub_process_id='KP-06.TP-2';
INSERT INTO p VALUES (2,'Pruefung am Blatt nachgetragen','ja');
INSERT INTO p SELECT 3,'zweite Pruefung abgewiesen', pg_temp.muss_scheitern($$UPDATE kir_agentenblatt SET geprueft_von='BC4-T2'$$);
INSERT INTO p SELECT 4,'Inhalt des Blatts aendern abgewiesen', pg_temp.muss_scheitern($$UPDATE kir_agentenblatt SET zweck='x'$$);
INSERT INTO p SELECT 5,'Blatt loeschen abgewiesen', pg_temp.muss_scheitern($$DELETE FROM kir_agentenblatt$$);
-- 3. Kennzahl, Kriterium (BC4 uebernimmt aus Datei), Testfall
INSERT INTO kir_kennzahlen(company_id,use_case,kennzahl_id,bezeichnung,einheit,richtung,zielwert,bezug_potenzial_id,festgelegt_von)
VALUES (:c,'UC1','K1','Durchlaufzeit je Anfrage','min','niedriger_besser',5,'p1','BC4-T1'),
       (:c,'UC1','K2','Pflichtfelder richtig','%','hoeher_besser',95,'p2','BC4-T1');
INSERT INTO kir_akzeptanzkriterien(company_id,use_case,kriterium_id,sub_process_id,text,quelle)
VALUES (:c,'UC1','AK-01','KP-06.TP-2','Ziel, Termin, Zweck werden erkannt','del-kp-06-2026-11-03-184824');
INSERT INTO kir_testfaelle(company_id,use_case,testfall_id,sub_process_id,kriterium_id,beschreibung,eingabe_ref,datensatz_version,erwartung,angelegt_von)
VALUES (:c,'UC1','TF-01','KP-06.TP-2','AK-01','Standard-Mail','mail_01.eml','v1','Ziel=Berlin','BC4-T1');
INSERT INTO p SELECT 6,'Klarname als Kennung abgewiesen',
  pg_temp.muss_scheitern($$INSERT INTO kir_kennzahlen(company_id,use_case,kennzahl_id,bezeichnung,einheit,richtung,zielwert,festgelegt_von)
                           VALUES ('7c2d5ee9-2a9a-5990-810f-502ea2b2012d','UC1','K3','x','x','hoeher_besser',1,'Mehdi')$$);
-- 4. Testergebnisse: 2 Wiederholungen bestanden
INSERT INTO kir_testergebnisse(company_id,paket_id,durchlauf_nr,use_case,testfall_id,wiederholung,prototyp_version,modell,ergebnis,herkunft,geprueft_von)
VALUES (:c,:p,1,'UC1','TF-01',1,'95750c4','claude-opus-5-5','bestanden','generiert_geprueft','BC4-T2'),
       (:c,:p,1,'UC1','TF-01',2,'95750c4','claude-opus-5-5','bestanden','generiert_geprueft','BC4-T2');
INSERT INTO p SELECT 7,'falscher UC zum Durchlauf abgewiesen',
  pg_temp.muss_scheitern($$INSERT INTO kir_testergebnisse(company_id,paket_id,durchlauf_nr,use_case,testfall_id,wiederholung,prototyp_version,ergebnis,herkunft)
     VALUES ('7c2d5ee9-2a9a-5990-810f-502ea2b2012d','cc7f4d1b-4c71-4cfa-92c3-46a395080e4b',1,'UC2','TF-01',3,'x','bestanden','generiert')$$);
INSERT INTO p SELECT 8,'gepruefter Test ohne Pruefer abgewiesen',
  pg_temp.muss_scheitern($$INSERT INTO kir_testergebnisse(company_id,paket_id,durchlauf_nr,use_case,testfall_id,wiederholung,prototyp_version,ergebnis,herkunft)
     VALUES ('7c2d5ee9-2a9a-5990-810f-502ea2b2012d','cc7f4d1b-4c71-4cfa-92c3-46a395080e4b',1,'UC1','TF-01',3,'x','bestanden','mensch')$$);
INSERT INTO p SELECT 9,'Testergebnis aendern abgewiesen', pg_temp.muss_scheitern($$UPDATE kir_testergebnisse SET ergebnis='nicht_bestanden'$$);
INSERT INTO p SELECT 10,'Kennzahl nach dem ersten Test abgewiesen',
  pg_temp.muss_scheitern($$INSERT INTO kir_kennzahlen(company_id,use_case,kennzahl_id,bezeichnung,einheit,richtung,zielwert,festgelegt_von)
                           VALUES ('7c2d5ee9-2a9a-5990-810f-502ea2b2012d','UC1','K3','x','x','hoeher_besser',1,'BC4-T1')$$);
-- 5. Messwerte: K1 erreicht (4 <= 5), K2 nicht (90 < 95); Werkzeuge verwendet
INSERT INTO kir_messwerte(company_id,paket_id,durchlauf_nr,use_case,kennzahl_id,vorher,nachher,erfasst_von)
VALUES (:c,:p,1,'UC1','K1',15,4,'BC4-T1'),(:c,:p,1,'UC1','K2',60,90,'BC4-T1');
INSERT INTO kir_werkzeug_nutzung(company_id,paket_id,durchlauf_nr,sub_process_id,werkzeug,version)
VALUES (:c,:p,1,'KP-06.TP-2','FastAPI','0.115'),(:c,:p,1,'KP-06.TP-2','Playwright','1.48');
INSERT INTO kir_abweichungen(company_id,paket_id,durchlauf_nr,lfd,sub_process_id,soll,ist,ursache,massnahme,verantwortlich)
VALUES (:c,:p,1,1,'KP-06.TP-2','95 %','90 %','Datumsformate','Parser erweitern','BC4-T1');
-- 6. Laufdaten nachtragen ja, ueberschreiben nein, andere Spalte nein
UPDATE ki_laufdaten SET kosten_eur=0.42, anfrage_id='A-2026-01' WHERE kosten_eur IS NULL AND paket_id IS NOT NULL;
INSERT INTO kir_lauf_zuordnung(ki_laufdaten_id,company_id,paket_id,durchlauf_nr) SELECT id, company_id, paket_id, 1 FROM ki_laufdaten WHERE paket_id IS NOT NULL;
INSERT INTO p SELECT 11,'Laufdaten nachgetragen und Durchlauf zugeordnet (8 Zeilen)', CASE WHEN (SELECT count(*) FROM ki_laufdaten WHERE kosten_eur=0.42)=8 AND (SELECT count(*) FROM kir_lauf_zuordnung)=8 THEN 'ja' ELSE 'NEIN' END;
INSERT INTO p SELECT 12,'Laufdaten ueberschreiben abgewiesen', pg_temp.muss_scheitern($$UPDATE ki_laufdaten SET kosten_eur=0.5 WHERE paket_id IS NOT NULL$$);
INSERT INTO p SELECT 13,'Laufdaten Modell aendern abgewiesen', pg_temp.muss_scheitern($$UPDATE ki_laufdaten SET modell='x'$$);
INSERT INTO p SELECT 14,'BC4 legt keinen Durchlauf an', pg_temp.muss_scheitern($$INSERT INTO kir_durchlauf(company_id,paket_id,durchlauf_nr,use_case,anlass,angelegt_von)
     VALUES ('7c2d5ee9-2a9a-5990-810f-502ea2b2012d','cc7f4d1b-4c71-4cfa-92c3-46a395080e4b',2,'UC1','x','BC4-T1')$$);
RESET ROLE;

-- 7. BC3 darf Kriterien schreiben, sonst nichts
SET ROLE bc3_role;
INSERT INTO kir_akzeptanzkriterien(company_id,use_case,kriterium_id,sub_process_id,text,quelle)
VALUES (:c,'UC1','AK-02','KP-06.TP-3','Reservierung ohne Abtippen','del-x');
INSERT INTO p SELECT 15,'BC3 darf kein Testergebnis schreiben', pg_temp.muss_scheitern($$INSERT INTO kir_abweichungen VALUES ('7c2d5ee9-2a9a-5990-810f-502ea2b2012d','cc7f4d1b-4c71-4cfa-92c3-46a395080e4b',1,9,NULL,'a','b','c','d','BC3-X1')$$);
RESET ROLE;

-- 8. Erfuellungsgrad (ERWARTET: A 1 von 2 [AK-02 ohne Testfall], K 1 von 2, W 2 von 3 [FastAPI, Modell stimmen; Playwright nicht hinterlegt]
--    => 40*0.5 + 40*0.5 + 20*2/3 = 53.3)
INSERT INTO p SELECT 16,'Erfuellungsgrad 53.3 %', CASE WHEN (SELECT erfuellung_pct FROM v_kir_erfuellungsgrad)=53.3 THEN 'ja' ELSE 'NEIN: '||(SELECT erfuellung_pct||' A'||a_x||'/'||a_n||' K'||k_x||'/'||k_n||' W'||w_x||'/'||w_n FROM v_kir_erfuellungsgrad) END;
-- 9. Durchlauf 2 durch BC0: nur fortlaufend, Entscheidung einmal
INSERT INTO p SELECT 17,'Durchlauf 3 vor 2 abgewiesen', pg_temp.muss_scheitern($$INSERT INTO kir_durchlauf(company_id,paket_id,durchlauf_nr,use_case,anlass,angelegt_von)
     VALUES ('7c2d5ee9-2a9a-5990-810f-502ea2b2012d','cc7f4d1b-4c71-4cfa-92c3-46a395080e4b',3,'UC1','x','P-07')$$);
INSERT INTO p SELECT 18,'Entscheidung ohne Begruendung abgewiesen', pg_temp.muss_scheitern($$UPDATE kir_durchlauf SET entscheidung='nachbessern', entschieden_am=now(), entschieden_von='P-07' WHERE durchlauf_nr=1$$);
UPDATE kir_durchlauf SET entscheidung='nachbessern', entschieden_am=now(), entschieden_von='P-07', begruendung='K2 unter Ziel' WHERE durchlauf_nr=1;
INSERT INTO p SELECT 19,'zweite Entscheidung abgewiesen', pg_temp.muss_scheitern($$UPDATE kir_durchlauf SET entscheidung='weiter' WHERE durchlauf_nr=1$$);
INSERT INTO kir_durchlauf(company_id,paket_id,durchlauf_nr,use_case,anlass,angelegt_von) VALUES (:c,:p,2,'UC1','Nachbessern K2','P-07');
INSERT INTO p SELECT 20,'Durchlauf 2 angelegt, Blatt 1 bleibt', CASE WHEN (SELECT count(*) FROM kir_agentenblatt WHERE durchlauf_nr=1)=1 AND (SELECT count(*) FROM kir_durchlauf)=2 THEN 'ja' ELSE 'NEIN' END;
INSERT INTO p SELECT 21,'Durchlauf 2 startet bei 0 %', CASE WHEN (SELECT erfuellung_pct FROM v_kir_erfuellungsgrad WHERE durchlauf_nr=2)=0 THEN 'ja' ELSE 'NEIN' END;
INSERT INTO p SELECT 22,'Historie fuer kir_durchlauf', CASE WHEN (SELECT count(*) FROM audit_log WHERE tabelle='kir_durchlauf')>=3 THEN 'ja' ELSE 'NEIN' END;
-- 10. Mandant loeschen raeumt alles mit (Kaskade trotz nur_anhaengen)
DELETE FROM ki_laufdaten WHERE company_id=:c;  -- (in Produktion: Kaskade companies -> ki_laufdaten)
DELETE FROM companies WHERE company_id=:c;
INSERT INTO p SELECT 23,'Mandantenloeschung raeumt Durchlaeufe und Tests mit',
  CASE WHEN (SELECT count(*) FROM kir_durchlauf)+(SELECT count(*) FROM kir_testergebnisse)+(SELECT count(*) FROM kir_agentenblatt)
           +(SELECT count(*) FROM kir_kennzahlen)+(SELECT count(*) FROM kir_akzeptanzkriterien)=0 THEN 'ja' ELSE 'NEIN' END;

INSERT INTO p SELECT 24,'Agentenblatt v3.32 unveraendert (ohne paket_id/durchlauf_nr)',
  CASE WHEN NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='prozess_dokumentation' AND column_name IN ('paket_id','durchlauf_nr')) THEN 'ja' ELSE 'NEIN' END;
INSERT INTO p SELECT 25,'App-Abfrage KI-Transformation Prozessdoku laeuft',
  CASE WHEN (SELECT count(*) FROM (SELECT sub_process_id,tage_seit_pruefung,pruefung_faellig,niemand_kann_aendern FROM v_prozess_dokumentation_stand) x) >= 0 THEN 'ja' ELSE 'NEIN' END;
INSERT INTO p SELECT 26,'ki_laufdaten ohne neue Spalte', CASE WHEN NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='ki_laufdaten' AND column_name='durchlauf_nr') THEN 'ja' ELSE 'NEIN' END;
SELECT nr, was, ok FROM p ORDER BY nr;
SELECT count(*) FILTER (WHERE ok LIKE 'ja%') AS ja, count(*) FILTER (WHERE ok NOT LIKE 'ja%') AS nein FROM p;
