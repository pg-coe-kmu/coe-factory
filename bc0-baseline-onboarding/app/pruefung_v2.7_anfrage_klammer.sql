-- Pruefszenario zu schema_v2.7_anfrage_prozesse_und_uebergabe.sql — gegen eine LEERE Testdatenbank mit der
-- Schemafolge v1.1.1 … v2.6. NICHT gegen Produktiv: legt Mandant 2222…, KP-01/KP-02, Anfragen A-2026-01/02 an
-- und loescht den Mandanten am Ende. Ruft v2.7 selbst auf (\i, Pfad anpassen). 17 Erwartungswerte.
-- Ausgefuehrt 04.09.2026 (nachts) gegen PostgreSQL 16.13 — alle getroffen, nach einer Korrektur (FKs CASCADE).
\set ON_ERROR_STOP off
\pset format unaligned
\pset tuples_only on
\echo === Aufbau: Mandant, KP-01 (TP-1, TP-2), KP-02 (TP-1), Eigner, 30 Items je TP, Anfrage A-2026-01 -> KP-01 (Erstzuordnung)
INSERT INTO ref_items(item_nr,dimension,kriterium,frage) SELECT g,'D','K','F'||g FROM generate_series(1,30) g ON CONFLICT DO NOTHING;
INSERT INTO app_benutzer(benutzer_id,email,name,passwort_hash,rolle) VALUES('u1','u1@x','U','h','admin') ON CONFLICT DO NOTHING;
INSERT INTO companies(company_id,name) VALUES('22222222-2222-2222-2222-222222222222','Test2');
INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie) VALUES('22222222-2222-2222-2222-222222222222','KP-01','P1','Kerngeschäftsprozess'),('22222222-2222-2222-2222-222222222222','KP-02','P2','Kerngeschäftsprozess');
INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name) VALUES
 ('22222222-2222-2222-2222-222222222222','KP-01.TP-1','KP-01',1,'T1'),('22222222-2222-2222-2222-222222222222','KP-01.TP-2','KP-01',2,'T2'),('22222222-2222-2222-2222-222222222222','KP-02.TP-1','KP-02',1,'T3');
INSERT INTO ref_personen(company_id,person_id,name) VALUES('22222222-2222-2222-2222-222222222222','P-01','X');
INSERT INTO prozess_personen(company_id,process_id,person_id,funktion) VALUES('22222222-2222-2222-2222-222222222222','KP-01','P-01','eigner'),('22222222-2222-2222-2222-222222222222','KP-02','P-01','eigner');
INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) VALUES('22222222-2222-2222-2222-222222222222','E-2026-09','E','2026-09-03','offen');
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am)
 SELECT '22222222-2222-2222-2222-222222222222','E-2026-09',tp||'.I-'||lpad(g::text,2,'0'),tp,g,4,'b','manuell',now() FROM generate_series(1,30) g, unnest(ARRAY['KP-01.TP-1','KP-01.TP-2','KP-02.TP-1']) tp;
INSERT INTO ref_anfragen(company_id,anfrage_id,originaltext,eingang_am,process_id,zuordnung_quelle,status) VALUES('22222222-2222-2222-2222-222222222222','A-2026-01','Alles langsam','2026-09-01','KP-01','anfrage','zugeordnet');
\echo === v2.7 einspielen
\i schema_v2.7_anfrage_prozesse_und_uebergabe.sql
SELECT 'status-check: '||pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_anfrage_status';
SELECT 'uebernahme: '||rolle||' '||process_id||' tp='||coalesce(sub_process_id,'NULL') FROM anfrage_prozesse WHERE anfrage_id='A-2026-01';
SELECT 'soll aufgeloest: '||string_agg(sub_process_id,',' ORDER BY sub_process_id) FROM v_anfrage_teilprozesse WHERE anfrage_id='A-2026-01';
\echo === Beteiligt: KP-02.TP-1 dazu; zweiter haupt -> abgewiesen; TP nicht zum KP -> abgewiesen
INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,rolle,zuordnung_quelle) VALUES('22222222-2222-2222-2222-222222222222','A-2026-01','KP-02','KP-02.TP-1','beteiligt','interview');
INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,rolle,zuordnung_quelle) VALUES('22222222-2222-2222-2222-222222222222','A-2026-01','KP-02',NULL,'haupt','interview');
INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,rolle,zuordnung_quelle) VALUES('22222222-2222-2222-2222-222222222222','A-2026-01','KP-02','KP-01.TP-1','beteiligt','interview');
SELECT 'stand: soll='||soll||' frei='||freigegeben||' fehlend='||array_to_string(fehlend,',')||' faehig='||uebergabefaehig FROM v_anfrage_uebergabe_stand WHERE anfrage_id='A-2026-01';
\echo === Paket vor Vollstaendigkeit -> abgewiesen mit Liste
INSERT INTO gate_ereignisse(gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,erhebung_id,anfrage_id) VALUES('bc0-bc2','22222222-2222-2222-2222-222222222222','teilprozess','KP-01.TP-1','freigegeben','u1','E-2026-09','A-2026-01');
SELECT gate_paket_schnueren('22222222-2222-2222-2222-222222222222','u1','zu frueh','A-2026-01');
\echo === alle drei freigeben -> Paket, Status uebergeben; zweites identisches -> abgewiesen
INSERT INTO gate_ereignisse(gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,erhebung_id,anfrage_id) VALUES
 ('bc0-bc2','22222222-2222-2222-2222-222222222222','teilprozess','KP-01.TP-2','freigegeben','u1','E-2026-09','A-2026-01'),
 ('bc0-bc2','22222222-2222-2222-2222-222222222222','teilprozess','KP-02.TP-1','freigegeben','u1','E-2026-09','A-2026-01');
SELECT 'stand: soll='||soll||' frei='||freigegeben||' faehig='||uebergabefaehig FROM v_anfrage_uebergabe_stand WHERE anfrage_id='A-2026-01';
SELECT gate_paket_schnueren('22222222-2222-2222-2222-222222222222','u1','Komplett','A-2026-01') IS NOT NULL AS paket1;
SELECT 'status: '||status||' seit '||status_seit FROM ref_anfragen WHERE anfrage_id='A-2026-01';
SELECT 'paketinhalt: '||count(*)||' tps, anfrage='||string_agg(DISTINCT coalesce(anfrage_id,'NULL'),',') FROM v_uebergabe_offen WHERE paket_rang=1;
SELECT 'ereignis: '||objekt_typ||' '||objekt_id FROM gate_ereignisse WHERE ereignis='uebergeben' ORDER BY ereignis_id DESC LIMIT 1;
SELECT gate_paket_schnueren('22222222-2222-2222-2222-222222222222','u1','nochmal','A-2026-01');
\echo === Widerruf + neue Freigabe -> wieder faehig -> zweites Paket
INSERT INTO gate_ereignisse(gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,grund) VALUES('bc0-bc2','22222222-2222-2222-2222-222222222222','teilprozess','KP-01.TP-2','widerrufen','u1','Nacherhebung');
SELECT 'nach widerruf: frei='||freigegeben||' faehig='||uebergabefaehig||' fehlend='||array_to_string(fehlend,',') FROM v_anfrage_uebergabe_stand WHERE anfrage_id='A-2026-01';
INSERT INTO gate_ereignisse(gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,erhebung_id,anfrage_id) VALUES('bc0-bc2','22222222-2222-2222-2222-222222222222','teilprozess','KP-01.TP-2','freigegeben','u1','E-2026-09','A-2026-01');
SELECT 'nach neuer freigabe: faehig='||uebergabefaehig FROM v_anfrage_uebergabe_stand WHERE anfrage_id='A-2026-01';
SELECT gate_paket_schnueren('22222222-2222-2222-2222-222222222222','u1','Umfang neu','A-2026-01') IS NOT NULL AS paket2;
SELECT 'pakete der anfrage: '||count(DISTINCT paket_id) FROM v_uebergabe_offen WHERE anfrage_id='A-2026-01';
\echo === Portfolio: ohne Liste -> abgewiesen; mit TP ausserhalb der Anfrage
INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name) VALUES ('22222222-2222-2222-2222-222222222222','KP-02.TP-2','KP-02',2,'T4');
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am) SELECT '22222222-2222-2222-2222-222222222222','E-2026-09','KP-02.TP-2.I-'||lpad(g::text,2,'0'),'KP-02.TP-2',g,4,'b','manuell',now() FROM generate_series(1,30) g;
INSERT INTO gate_ereignisse(gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,erhebung_id) VALUES('bc0-bc2','22222222-2222-2222-2222-222222222222','teilprozess','KP-02.TP-2','freigegeben','u1','E-2026-09');
SELECT gate_paket_schnueren('22222222-2222-2222-2222-222222222222','u1','portfolio ohne liste');
SELECT gate_paket_schnueren('22222222-2222-2222-2222-222222222222','u1','portfolio',NULL,ARRAY['KP-02.TP-2','KP-01.TP-1']);
SELECT gate_paket_schnueren('22222222-2222-2222-2222-222222222222','u1','portfolio',NULL,ARRAY['KP-02.TP-2']) IS NOT NULL AS paket3;
SELECT 'portfolio-paket: tp='||sub_process_id||' anfrage='||coalesce(anfrage_id,'NULL') FROM v_uebergabe_offen WHERE paket_rang=1;
\echo === Haupt spiegeln: neue Anfrage ohne Bezug, haupt einfuegen -> ref_anfragen.process_id gesetzt
INSERT INTO ref_anfragen(company_id,anfrage_id,originaltext,eingang_am) VALUES('22222222-2222-2222-2222-222222222222','A-2026-02','weiss nicht','2026-09-03');
INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,rolle,zuordnung_quelle) VALUES('22222222-2222-2222-2222-222222222222','A-2026-02','KP-02','KP-02.TP-2','haupt','interview');
SELECT 'gespiegelt: '||process_id||' '||sub_process_id||' '||zuordnung_quelle FROM ref_anfragen WHERE anfrage_id='A-2026-02';
\echo === zweiter Lauf v2.7 (wiederholbar)
\i schema_v2.7_anfrage_prozesse_und_uebergabe.sql
SELECT 'bezuege A-2026-01 nach zweitem Lauf: '||count(*) FROM anfrage_prozesse WHERE anfrage_id='A-2026-01';
\echo === Mandant loeschen -> Kaskade
DELETE FROM companies WHERE company_id='22222222-2222-2222-2222-222222222222';
SELECT 'rest: bezuege='||(SELECT count(*) FROM anfrage_prozesse)||' pakete='||(SELECT count(*) FROM gate_pakete);
