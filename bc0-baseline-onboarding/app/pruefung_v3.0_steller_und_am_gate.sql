-- Pruefung zu schema_v3.0 — neun Erwartungswerte (07.09.2026)
--
-- Ausfuehren gegen eine Datenbank, in der die Schemafolge bis v3.0 steht.
-- Legt einen eigenen Pruefmandanten an und raeumt am Ende auf (ROLLBACK).
-- Alle neun Zeilen muessen `ja` liefern.
--
-- Proben 5 bis 9 brauchen einen Stellvertreter fuer bc1.prozessprofil, weil
-- Richard am 07.09.2026 noch nicht eingespielt hatte. Er traegt die am
-- 22.08.2026 vereinbarten Felder: (company_id, focus_step_id, profil_version,
-- status). **Stehen sie bei BC1 anders, aendert sich der LATERAL-Block in
-- anfrage_am_gate_nachziehen() — und diese Pruefung mit.**

BEGIN;

CREATE TEMP TABLE p(nr INT, aussage TEXT, ergebnis TEXT);

-- Fixture
INSERT INTO companies(company_id, name) VALUES ('30303030-3030-3030-3030-303030303030','Pruefmandant v3.0');
INSERT INTO ref_prozesse(company_id, process_id, process_name, kategorie)
  VALUES ('30303030-3030-3030-3030-303030303030','KP-01','Vertrieb','Kerngeschäftsprozess');
INSERT INTO ref_teilprozesse(company_id, process_id, sub_process_id, step_no, sub_process_name) VALUES
  ('30303030-3030-3030-3030-303030303030','KP-01','KP-01.TP-1',1,'Angebot'),
  ('30303030-3030-3030-3030-303030303030','KP-01','KP-01.TP-2',2,'Nachfassen');
INSERT INTO ref_personen(company_id, person_id, name, funktion) VALUES
  ('30303030-3030-3030-3030-303030303030','P-07','Pruefperson','Leitung'),
  ('30303030-3030-3030-3030-303030303030','P-09','Andere Person','Sachbearbeitung');
INSERT INTO app_benutzer(benutzer_id,email,name,passwort_hash,rolle)
  VALUES ('pruef-v30','pruef-v30@bc0.test','Pruefkonto','x','benutzer');
INSERT INTO app_benutzer_mandanten(benutzer_id,company_id,person_id)
  VALUES ('pruef-v30','30303030-3030-3030-3030-303030303030','P-07');
INSERT INTO ref_anfragen(company_id,anfrage_id,originaltext,eingang_am,status,status_seit,
                         angelegt_von,process_id,sub_process_id,zuordnung_quelle)
  VALUES ('30303030-3030-3030-3030-303030303030','A-2026-01','Pruefanfrage','2026-09-07',
          'zugeordnet','2026-09-07','pruef-v30','KP-01','KP-01.TP-1','anfrage');
INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,rolle,zuordnung_quelle)
  VALUES ('30303030-3030-3030-3030-303030303030','A-2026-01','KP-01','KP-01.TP-1','haupt','anfrage');

-- 1. Ohne steller_id kommt die P-ID aus dem Konto.
INSERT INTO p SELECT 1, 'P-ID aus dem Konto, Herkunft konto',
  CASE WHEN person_id='P-07' AND herkunft='konto' AND person_name='Pruefperson'
       THEN 'ja' ELSE 'NEIN: '||coalesce(person_id,'-')||'/'||herkunft END
  FROM v_anfrage_steller WHERE company_id='30303030-3030-3030-3030-303030303030';

-- 2. Die ausdrueckliche Angabe am Formular schlaegt das Konto.
UPDATE ref_anfragen SET steller_id='P-09'
 WHERE company_id='30303030-3030-3030-3030-303030303030' AND anfrage_id='A-2026-01';
INSERT INTO p SELECT 2, 'steller_id schlaegt das Konto',
  CASE WHEN person_id='P-09' AND herkunft='formular' AND steller_konto='P-07'
       THEN 'ja' ELSE 'NEIN: '||coalesce(person_id,'-')||'/'||herkunft END
  FROM v_anfrage_steller WHERE company_id='30303030-3030-3030-3030-303030303030';

-- 3. Weder noch: unbekannt, keine erfundene ID.
UPDATE ref_anfragen SET steller_id=NULL, angelegt_von=NULL
 WHERE company_id='30303030-3030-3030-3030-303030303030' AND anfrage_id='A-2026-01';
INSERT INTO p SELECT 3, 'ohne beides: unbekannt, keine erfundene P-ID',
  CASE WHEN person_id IS NULL AND herkunft='unbekannt' THEN 'ja'
       ELSE 'NEIN: '||coalesce(person_id,'-')||'/'||herkunft END
  FROM v_anfrage_steller WHERE company_id='30303030-3030-3030-3030-303030303030';
UPDATE ref_anfragen SET angelegt_von='pruef-v30'
 WHERE company_id='30303030-3030-3030-3030-303030303030' AND anfrage_id='A-2026-01';

-- 4. Ohne bc1.prozessprofil passiert nichts, und die Funktion sagt es.
INSERT INTO p SELECT 4, 'ohne bc1.prozessprofil: kein Statuswechsel, mit Hinweis',
  CASE WHEN to_regclass('bc1.prozessprofil') IS NOT NULL THEN 'entfaellt (bc1 steht bereits)'
       WHEN (SELECT count(*) FROM anfrage_am_gate_nachziehen('30303030-3030-3030-3030-303030303030') g
              WHERE g.hinweis LIKE 'bc1.prozessprofil gibt es noch nicht%') = 1
        AND (SELECT status FROM ref_anfragen
              WHERE company_id='30303030-3030-3030-3030-303030303030'
                AND anfrage_id='A-2026-01') = 'zugeordnet'
       THEN 'ja' ELSE 'NEIN' END;

-- Stellvertreter fuer Richards Tabelle, nur fuer diese Pruefung.
CREATE SCHEMA IF NOT EXISTS bc1;
CREATE TABLE IF NOT EXISTS bc1.prozessprofil(
  company_id UUID NOT NULL, focus_step_id TEXT NOT NULL,
  profil_version INTEGER NOT NULL, status TEXT NOT NULL,
  PRIMARY KEY (company_id, focus_step_id, profil_version));

-- 5. Profil auf in_erhebung -> die Anfrage bleibt stehen.
INSERT INTO bc1.prozessprofil VALUES ('30303030-3030-3030-3030-303030303030','KP-01.TP-1',1,'in_erhebung');
INSERT INTO p SELECT 5, 'in_erhebung: 0 von 1 fertig, bleibt stehen',
  CASE WHEN status_neu='zugeordnet' AND hinweis LIKE '0 von 1%' THEN 'ja'
       ELSE 'NEIN: '||status_neu||' / '||hinweis END
  FROM anfrage_am_gate_nachziehen('30303030-3030-3030-3030-303030303030');

-- 6. Zweiter Teilprozess dazu, nur einer fertig -> bleibt stehen.
INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,rolle,zuordnung_quelle)
  VALUES ('30303030-3030-3030-3030-303030303030','A-2026-01','KP-01','KP-01.TP-2','beteiligt','interview');
INSERT INTO bc1.prozessprofil VALUES ('30303030-3030-3030-3030-303030303030','KP-01.TP-1',2,'fertig');
INSERT INTO p SELECT 6, 'einer von zwei fertig: kein Gate auf einem Ausschnitt',
  CASE WHEN status_neu='zugeordnet' AND hinweis LIKE '1 von 2%' THEN 'ja'
       ELSE 'NEIN: '||status_neu||' / '||hinweis END
  FROM anfrage_am_gate_nachziehen('30303030-3030-3030-3030-303030303030');

-- 7. Beide fertig -> am_gate.
INSERT INTO bc1.prozessprofil VALUES ('30303030-3030-3030-3030-303030303030','KP-01.TP-2',1,'fertig');
INSERT INTO p SELECT 7, 'beide fertig: Anfrage geht ans Gate',
  CASE WHEN status_neu='am_gate' AND hinweis LIKE '2 von 2%' THEN 'ja'
       ELSE 'NEIN: '||status_neu||' / '||hinweis END
  FROM anfrage_am_gate_nachziehen('30303030-3030-3030-3030-303030303030');

-- 8. Zweiter Lauf: kein Ruecksprung, keine Doppelung.
INSERT INTO p SELECT 8, 'zweiter Lauf aendert nichts',
  CASE WHEN (SELECT count(*) FROM anfrage_am_gate_nachziehen('30303030-3030-3030-3030-303030303030')) = 0
        AND (SELECT status FROM ref_anfragen
              WHERE company_id='30303030-3030-3030-3030-303030303030'
                AND anfrage_id='A-2026-01') = 'am_gate'
       THEN 'ja' ELSE 'NEIN' END;

-- 9. Nachschreiben: die juengste Profilversion zaehlt.
UPDATE ref_anfragen SET status='im_interview'
 WHERE company_id='30303030-3030-3030-3030-303030303030' AND anfrage_id='A-2026-01';
INSERT INTO bc1.prozessprofil VALUES ('30303030-3030-3030-3030-303030303030','KP-01.TP-2',2,'in_erhebung');
INSERT INTO p SELECT 9, 'Nachschreiben: juengste Version zaehlt, bleibt stehen',
  CASE WHEN status_neu='im_interview' AND hinweis LIKE '1 von 2%' THEN 'ja'
       ELSE 'NEIN: '||status_neu||' / '||hinweis END
  FROM anfrage_am_gate_nachziehen('30303030-3030-3030-3030-303030303030');

SELECT nr, aussage, ergebnis FROM p ORDER BY nr;
SELECT count(*) FILTER (WHERE ergebnis <> 'ja') AS fehlgeschlagen FROM p;

ROLLBACK;
