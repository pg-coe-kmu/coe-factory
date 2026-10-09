-- Pruefung zu schema_v3.13 — sieben Erwartungswerte (08.10.2026)
--
-- Ausfuehren gegen eine Datenbank, in der v3.13 steht und bc1.prozessprofil
-- (BC1 ab B5, mit Spalte anfrage_id) eingespielt ist. Legt einen eigenen
-- Pruefmandanten an und raeumt am Ende auf (ROLLBACK). Alle sieben Zeilen muessen
-- `ja` liefern, die letzte Abfrage `fehlgeschlagen = 0`.
--
-- Die Profile werden direkt in bc1.prozessprofil geschrieben, mit BC1s
-- Pflichtspalten (Stand B5). profil_version vergibt BC1s Trigger selbst
-- (fortlaufend je Teilprozess); der Wert 1 im INSERT ist nur Platzhalter.
-- Faellt ein INSERT wegen einer neuen Pflichtspalte von BC1 durch, ist das kein
-- Befund an v3.13, sondern an dieser Pruefung.

BEGIN;

CREATE TEMP TABLE p(nr INT, aussage TEXT, ergebnis TEXT);

-- Fixture: ein Mandant, ein Kernprozess mit einem Teilprozess, zwei Anfragen
-- auf denselben Teilprozess.
INSERT INTO companies(company_id, name) VALUES ('31331331-3133-3133-3133-313313313313','Pruefmandant v3.13');
INSERT INTO ref_prozesse(company_id, process_id, process_name, kategorie)
  VALUES ('31331331-3133-3133-3133-313313313313','KP-01','Vertrieb','Kerngeschäftsprozess');
INSERT INTO ref_teilprozesse(company_id, process_id, sub_process_id, step_no, sub_process_name)
  VALUES ('31331331-3133-3133-3133-313313313313','KP-01','KP-01.TP-1',1,'Angebot');
INSERT INTO ref_anfragen(company_id,anfrage_id,originaltext,eingang_am,status,status_seit,
                         process_id,sub_process_id,zuordnung_quelle) VALUES
  ('31331331-3133-3133-3133-313313313313','A-2026-01','Alte Anfrage','2026-10-01',
   'zugeordnet','2026-10-01','KP-01','KP-01.TP-1','anfrage'),
  ('31331331-3133-3133-3133-313313313313','A-2026-02','Neue Anfrage','2026-10-08',
   'zugeordnet','2026-10-08','KP-01','KP-01.TP-1','anfrage');
INSERT INTO anfrage_prozesse(company_id,anfrage_id,process_id,sub_process_id,rolle,zuordnung_quelle) VALUES
  ('31331331-3133-3133-3133-313313313313','A-2026-01','KP-01','KP-01.TP-1','haupt','anfrage'),
  ('31331331-3133-3133-3133-313313313313','A-2026-02','KP-01','KP-01.TP-1','haupt','anfrage');
INSERT INTO ref_erhebungen(company_id, erhebung_id, bezeichnung, stand, status)
  VALUES ('31331331-3133-3133-3133-313313313313','E-2026-01','Pruefung v3.13','2026-10-08','offen');

-- Ein Profil schreiben wie BC1: (Teilprozess, Status, Anfrage).
CREATE FUNCTION pg_temp.profil(p_status TEXT, p_anfrage TEXT) RETURNS VOID AS $f$
  INSERT INTO bc1.prozessprofil(company_id, focus_step_id, profil_version, process_id,
                                status, erhebung_id, paket_version, anfrage_id, profil)
  VALUES ('31331331-3133-3133-3133-313313313313','KP-01.TP-1',1,'KP-01',
          p_status,'E-2026-01','pruefung-v3.13',p_anfrage,'{}'::jsonb);
$f$ LANGUAGE sql;

-- 1. Die Funktion ist v3.13.
INSERT INTO p SELECT 1, 'Funktion steht auf v3.13',
  CASE WHEN obj_description('anfrage_am_gate_nachziehen(uuid,text)'::regprocedure) LIKE '%v3.13%'
       THEN 'ja' ELSE 'NEIN: v3.13 nicht eingespielt' END;

-- 2. Fertiges Profil fuer A-2026-01, nur diese Anfrage gefragt -> A-2026-01 ans Gate.
SELECT pg_temp.profil('fertig','A-2026-01');
INSERT INTO p SELECT 2, 'eigenes fertiges Profil: Anfrage geht ans Gate',
  CASE WHEN status_neu='am_gate' AND hinweis LIKE '1 von 1%' THEN 'ja'
       ELSE 'NEIN: '||status_neu||' / '||hinweis END
  FROM anfrage_am_gate_nachziehen('31331331-3133-3133-3133-313313313313','A-2026-01');

-- 3. KERNBEFUND: A-2026-02 bleibt stehen, obwohl derselbe Teilprozess ein
--    fertiges Profil hat — es gehoert zu A-2026-01.
INSERT INTO p SELECT 3, 'fremdes fertiges Profil zaehlt nicht: neue Anfrage bleibt stehen',
  CASE WHEN status_neu='zugeordnet' AND hinweis LIKE '0 von 1%' THEN 'ja'
       ELSE 'NEIN: '||status_neu||' / '||hinweis END
  FROM anfrage_am_gate_nachziehen('31331331-3133-3133-3133-313313313313','A-2026-02');

-- 4. Mit p_anfrage wird nur diese eine Anfrage betrachtet.
INSERT INTO p SELECT 4, 'mit anfrage_id: genau eine Zeile',
  CASE WHEN (SELECT count(*) FROM anfrage_am_gate_nachziehen(
              '31331331-3133-3133-3133-313313313313','A-2026-02')) = 1
       THEN 'ja' ELSE 'NEIN' END;

-- 5. Profil ohne anfrage_id (vor B5) zaehlt nicht.
SELECT pg_temp.profil('fertig',NULL);
INSERT INTO p SELECT 5, 'Profil ohne anfrage_id zaehlt nicht',
  CASE WHEN status_neu='zugeordnet' AND hinweis LIKE '0 von 1%' THEN 'ja'
       ELSE 'NEIN: '||status_neu||' / '||hinweis END
  FROM anfrage_am_gate_nachziehen('31331331-3133-3133-3133-313313313313','A-2026-02');

-- 6. Eigenes Profil fertig (so friert BC1 ein: in_erhebung -> fertig).
SELECT pg_temp.profil('in_erhebung','A-2026-02');
UPDATE bc1.prozessprofil SET status='fertig'
 WHERE company_id='31331331-3133-3133-3133-313313313313'
   AND anfrage_id='A-2026-02' AND status='in_erhebung';
INSERT INTO p SELECT 6, 'eigenes Profil fertig: neue Anfrage geht ans Gate',
  CASE WHEN status_neu='am_gate' AND hinweis LIKE '1 von 1%' THEN 'ja'
       ELSE 'NEIN: '||status_neu||' / '||hinweis END
  FROM anfrage_am_gate_nachziehen('31331331-3133-3133-3133-313313313313','A-2026-02');

-- 7. Zweiter Lauf ueber den ganzen Mandanten: nichts mehr zu tun, kein Ruecksprung.
INSERT INTO p SELECT 7, 'zweiter Lauf aendert nichts',
  CASE WHEN (SELECT count(*) FROM anfrage_am_gate_nachziehen('31331331-3133-3133-3133-313313313313')) = 0
        AND (SELECT count(*) FROM ref_anfragen
              WHERE company_id='31331331-3133-3133-3133-313313313313' AND status='am_gate') = 2
       THEN 'ja' ELSE 'NEIN' END;

SELECT nr, aussage, ergebnis FROM p ORDER BY nr;
SELECT count(*) FILTER (WHERE ergebnis <> 'ja') AS fehlgeschlagen FROM p;

ROLLBACK;
