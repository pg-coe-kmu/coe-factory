-- Pruefszenario zu schema_v2.6_historie_und_paket.sql — gegen eine LEERE Testdatenbank mit der
-- Schemafolge v1.1.1 … v2.5 (v2.4 nur, wenn bc1_role die zwei Direktrechte hat). NICHT gegen Produktiv:
-- legt Mandant 1111…, KP-01, 30 Items, Benutzer u1 an und loescht den Mandanten am Ende.
-- Ruft v2.6 selbst auf (\i, Pfad anpassen). 20 Erwartungswerte, siehe Ausrollblatt 04.09.2026.
-- Ausgefuehrt 03.09.2026 gegen PostgreSQL 16.13 — alle getroffen.
\set ON_ERROR_STOP off
\pset format unaligned
\pset tuples_only on
\echo === Aufbau (vor v2.6): Mandant, KP, TP, 30 Items, Erhebung E-2026-05
INSERT INTO ref_items(item_nr,dimension,kriterium,frage) SELECT g,'D','K','F'||g FROM generate_series(1,30) g ON CONFLICT DO NOTHING;
INSERT INTO app_benutzer(benutzer_id,email,name,passwort_hash,rolle) VALUES('u1','u1@x','U','h','admin') ON CONFLICT DO NOTHING;
INSERT INTO companies(company_id,name) VALUES('11111111-1111-1111-1111-111111111111','Test');
INSERT INTO ref_prozesse(company_id,process_id,process_name,kategorie) VALUES('11111111-1111-1111-1111-111111111111','KP-01','P1','Kerngeschäftsprozess');
INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name) VALUES('11111111-1111-1111-1111-111111111111','KP-01.TP-1','KP-01',1,'T1 alt');
INSERT INTO ref_personen(company_id,person_id,name,email) VALUES('11111111-1111-1111-1111-111111111111','P-01','Max Mustermann','max@x.de');
INSERT INTO prozess_personen(company_id,process_id,person_id,funktion) VALUES('11111111-1111-1111-1111-111111111111','KP-01','P-01','eigner');
INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) VALUES('11111111-1111-1111-1111-111111111111','E-2026-05','Erst','2026-05-20','offen');
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am)
 SELECT '11111111-1111-1111-1111-111111111111','E-2026-05','KP-01.TP-1.I-'||lpad(g::text,2,'0'),'KP-01.TP-1',g,3,'b','manuell',now() FROM generate_series(1,30) g;
\echo === v2.6 einspielen (mit Bestand)
\i schema_v2.6_historie_und_paket.sql
SELECT 'bestand-zeilen: '||count(*)||' davon ref_personen ohne name: '||count(*) FILTER (WHERE entity='ref_personen' AND NOT (neu ? 'name')) FROM audit_log WHERE action='bestand';
SELECT 'trigger historie auf: '||count(*)||' tabellen' FROM pg_trigger WHERE tgname='historie';
\echo === R9: Zeitreise. t0 merken, Name und Stufe aendern, Stand zu t0 abfragen
SELECT set_config('bc0.benutzer','u1',false);
SELECT pg_sleep(0.2);
CREATE TEMP TABLE t0 AS SELECT now() AS t;
SELECT pg_sleep(0.2);
UPDATE ref_teilprozesse SET sub_process_name='T1 neu' WHERE sub_process_id='KP-01.TP-1';
INSERT INTO ref_erhebungen(company_id,erhebung_id,bezeichnung,stand,status) VALUES('11111111-1111-1111-1111-111111111111','E-2026-09','Nach','2026-09-03','offen');
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES('11111111-1111-1111-1111-111111111111','E-2026-09','KP-01.TP-1.I-01','KP-01.TP-1',1,5,'b','manuell',now());
SELECT 'heute: name='||sub_process_name FROM ref_teilprozesse WHERE sub_process_id='KP-01.TP-1';
SELECT 'zu t0: name='||(s->>'sub_process_name') FROM stand_zum('ref_teilprozesse',(SELECT t FROM t0)) s;
SELECT 'zu t0: bewertungen='||count(*)||' erhebungen='||string_agg(DISTINCT s->>'erhebung_id',',') FROM stand_zum('bitkom_bewertungen',(SELECT t FROM t0),'11111111-1111-1111-1111-111111111111') s;
SELECT 'heute: bewertungen='||count(*) FROM stand_zum('bitkom_bewertungen',now(),'11111111-1111-1111-1111-111111111111');
SELECT 'actor der aenderung: '||actor||' aktion='||action FROM audit_log WHERE entity='ref_teilprozesse' AND action='UPDATE' ORDER BY audit_id DESC LIMIT 1;
\echo === R9: geloeschte Zeile ist zu t0 da, heute nicht
DELETE FROM prozess_personen WHERE person_id='P-01';
SELECT 'zu t0: personen-zuordnungen='||count(*) FROM stand_zum('prozess_personen',(SELECT t FROM t0)) s;
SELECT 'heute: personen-zuordnungen='||count(*) FROM stand_zum('prozess_personen',now()) s;
INSERT INTO prozess_personen(company_id,process_id,person_id,funktion) VALUES('11111111-1111-1111-1111-111111111111','KP-01','P-01','eigner');
\echo === R9: Klarname nie in der Historie; vor Historiebeginn keine Antwort; app_benutzer keine Historie
UPDATE ref_personen SET name='Erika Musterfrau' WHERE person_id='P-01';
SELECT 'klarnamen in historie: '||count(*) FROM audit_log WHERE entity='ref_personen' AND (neu ? 'name' OR alt ? 'name' OR neu ? 'email');
SELECT count(*) FROM stand_zum('ref_teilprozesse', historie_beginn() - interval '1 day');
SELECT count(*) FROM stand_zum('app_benutzer', now());
\echo === A: Erhebung abschliessen, bewerten -> abgewiesen; wieder oeffnen -> abgewiesen
UPDATE ref_erhebungen SET status='abgeschlossen' WHERE erhebung_id='E-2026-05';
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES('11111111-1111-1111-1111-111111111111','E-2026-05','KP-01.TP-1.I-02','KP-01.TP-1',2,5,'b','manuell',now()) ON CONFLICT(company_id,erhebung_id,id) DO UPDATE SET stufe=excluded.stufe;
UPDATE ref_erhebungen SET status='offen' WHERE erhebung_id='E-2026-05';
\echo === B: Freigabe, Paket, Sicht fuer BC2, Zeitreise aus dem Paket heraus
INSERT INTO gate_ereignisse(gate,company_id,objekt_typ,objekt_id,ereignis,benutzer_id,erhebung_id) VALUES('bc0-bc2','11111111-1111-1111-1111-111111111111','teilprozess','KP-01.TP-1','freigegeben','u1','E-2026-09');
SELECT 'kandidaten: '||count(*) FROM v_uebergabe_kandidaten;
SELECT gate_paket_schnueren('11111111-1111-1111-1111-111111111111','u1','Erstes Paket') IS NOT NULL AS paket_angelegt;
SELECT 'kandidaten danach: '||count(*) FROM v_uebergabe_kandidaten;
SELECT 'v_uebergabe_offen: tp='||sub_process_id||' rang='||paket_rang||' anfrage='||coalesce(anfrage_id,'NULL') FROM v_uebergabe_offen;
SELECT 'freigabe unberuehrt: '||stand FROM v_gate_freigabe_aktuell;
SELECT pg_sleep(0.2);
INSERT INTO bitkom_bewertungen(company_id,erhebung_id,id,sub_process_id,item_nr,stufe,beleg,quelle,bewertet_am) VALUES('11111111-1111-1111-1111-111111111111','E-2026-09','KP-01.TP-1.I-10','KP-01.TP-1',10,1,'b','manuell',now());
SELECT 'BC2 liest zum paketdatum: avg='||r.avg_stufe||' n='||r.n_items FROM v_uebergabe_offen p, LATERAL reifegrad_tp_zum(p.company_id,p.uebergeben_am) r WHERE r.sub_process_id=p.sub_process_id;
SELECT 'heute waere avg='||round(avg(stufe),2) FROM v_bewertung_aktuell WHERE sub_process_id='KP-01.TP-1';
\echo === B2: Paket aendern -> abgewiesen; leeres Paket -> abgewiesen
UPDATE gate_pakete SET hinweis='x';
SELECT gate_paket_schnueren('11111111-1111-1111-1111-111111111111','u1','leer');
\echo === D: v_stand_veraltet
SELECT 'veraltet: tp_seit_freigabe='||aenderungen_tp_seit_freigabe||' tp_seit_paket='||aenderungen_tp_seit_paket||' tabellen='||coalesce(geaenderte_tabellen,'-')||' stillgelegt='||stillgelegt FROM v_stand_veraltet;
\echo === F: loeschen -> abgewiesen; stilllegen -> ok; Mandant loeschen -> Kaskade, Historie bleibt
DELETE FROM ref_teilprozesse WHERE sub_process_id='KP-01.TP-1';
UPDATE ref_teilprozesse SET aktiv=false WHERE sub_process_id='KP-01.TP-1';
SELECT 'stillgelegt: '||stillgelegt FROM v_stand_veraltet;
DELETE FROM companies WHERE company_id='11111111-1111-1111-1111-111111111111';
SELECT 'rest: bew='||(SELECT count(*) FROM bitkom_bewertungen)||' pakete='||(SELECT count(*) FROM gate_pakete)||' ereignisse='||(SELECT count(*) FROM gate_ereignisse)||' historie-zeilen mandant='||(SELECT count(*) FROM audit_log WHERE company_id='11111111-1111-1111-1111-111111111111')||' davon DELETE='||(SELECT count(*) FROM audit_log WHERE company_id='11111111-1111-1111-1111-111111111111' AND action='DELETE');
\echo === zweiter Lauf v2.6 (wiederholbar, Bestand nicht doppelt)
\i schema_v2.6_historie_und_paket.sql
SELECT 'bestand-laeufe: '||count(DISTINCT txid) FROM audit_log WHERE action='bestand';
