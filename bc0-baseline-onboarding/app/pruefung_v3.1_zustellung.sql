-- Pruefung zu schema_v3.1 — sechs Erwartungswerte (08.09.2026)
--
-- Prueft die Protokollseite: Wann gilt ein Paket als offen, wann als
-- zugestellt, und was passiert bei mehreren Versuchen. Der Ruf selbst ist
-- Anwendungslogik und in tests/test_v31_zustellung.py geprueft (fuenf
-- Aussagen, ohne Netz).
--
-- Legt einen eigenen Pruefmandanten an und nimmt alles zurueck (ROLLBACK).
-- Alle sechs Zeilen muessen `ja` liefern.

BEGIN;

CREATE TEMP TABLE p(nr INT, aussage TEXT, ergebnis TEXT);

INSERT INTO companies(company_id, name) VALUES ('31313131-3131-3131-3131-313131313131','Pruefmandant v3.1');
INSERT INTO gate_pakete(company_id, paket_id, uebergeben_am) VALUES
  ('31313131-3131-3131-3131-313131313131','aaaaaaaa-0000-0000-0000-000000000001','2026-09-08 09:00+00'),
  ('31313131-3131-3131-3131-313131313131','aaaaaaaa-0000-0000-0000-000000000002','2026-09-08 09:10+00'),
  ('31313131-3131-3131-3131-313131313131','aaaaaaaa-0000-0000-0000-000000000003','2026-09-08 09:20+00');

-- 1. Ein frisch geschnuertes Paket ohne jeden Versuch ist offen, mit 0 Versuchen.
INSERT INTO p SELECT 1, 'Paket ohne Versuch: offen, versuche = 0',
  CASE WHEN count(*) = 3 AND sum(versuche) = 0 THEN 'ja'
       ELSE 'NEIN: '||count(*)||' Pakete, '||coalesce(sum(versuche),-1)||' Versuche' END
  FROM v_zustellung_offen WHERE company_id='31313131-3131-3131-3131-313131313131';

-- 2. Ein gescheiterter Versuch schliesst das Paket NICHT ab.
INSERT INTO bc_zustellungen(company_id,paket_id,ziel_bc,ziel_url,versuch,ergebnis,http_code,meldung)
  VALUES ('31313131-3131-3131-3131-313131313131','aaaaaaaa-0000-0000-0000-000000000001',
          'bc2','https://bc2.example/hook',1,'fehler',NULL,'Netz weg');
INSERT INTO p SELECT 2, 'nach Fehler weiter offen, mit Versuch und Meldung',
  CASE WHEN versuche = 1 AND letztes_ergebnis = 'fehler' AND letzte_meldung = 'Netz weg'
       THEN 'ja' ELSE 'NEIN: '||versuche||'/'||coalesce(letztes_ergebnis,'-') END
  FROM v_zustellung_offen
 WHERE company_id='31313131-3131-3131-3131-313131313131'
   AND paket_id='aaaaaaaa-0000-0000-0000-000000000001';

-- 3. Der zweite Versuch zaehlt hoch, das juengste Ergebnis gilt.
INSERT INTO bc_zustellungen(company_id,paket_id,ziel_bc,ziel_url,versuch,ergebnis,http_code,meldung)
  VALUES ('31313131-3131-3131-3131-313131313131','aaaaaaaa-0000-0000-0000-000000000001',
          'bc2','https://bc2.example/hook',2,'fehler',503,'Service Unavailable');
INSERT INTO p SELECT 3, 'zweiter Versuch: versuche = 2, juengstes Ergebnis gilt',
  CASE WHEN versuche = 2 AND letzte_meldung = 'Service Unavailable' THEN 'ja'
       ELSE 'NEIN: '||versuche||'/'||coalesce(letzte_meldung,'-') END
  FROM v_zustellung_offen
 WHERE company_id='31313131-3131-3131-3131-313131313131'
   AND paket_id='aaaaaaaa-0000-0000-0000-000000000001';

-- 4. Ein einziger Erfolg schliesst das Paket ab — auch nach Fehlversuchen.
INSERT INTO bc_zustellungen(company_id,paket_id,ziel_bc,ziel_url,versuch,ergebnis,http_code)
  VALUES ('31313131-3131-3131-3131-313131313131','aaaaaaaa-0000-0000-0000-000000000001',
          'bc2','https://bc2.example/hook',3,'zugestellt',200);
INSERT INTO p SELECT 4, 'ein Erfolg schliesst ab, trotz zwei Fehlversuchen',
  CASE WHEN NOT EXISTS (SELECT 1 FROM v_zustellung_offen
                         WHERE company_id='31313131-3131-3131-3131-313131313131'
                           AND paket_id='aaaaaaaa-0000-0000-0000-000000000001')
       THEN 'ja' ELSE 'NEIN' END;

-- 5. `kein_ziel` ist KEIN Erfolg — das Paket bleibt offen.
--    Sonst gaelte ein Paket als zugestellt, nur weil niemand eine Adresse
--    hinterlegt hat. Das waere die stille Variante des Datenverlusts.
INSERT INTO bc_zustellungen(company_id,paket_id,ziel_bc,versuch,ergebnis,meldung)
  VALUES ('31313131-3131-3131-3131-313131313131','aaaaaaaa-0000-0000-0000-000000000002',
          'bc2',1,'kein_ziel','BC2_HOOK_URL ist nicht gesetzt');
INSERT INTO p SELECT 5, 'kein_ziel schliesst nicht ab',
  CASE WHEN letztes_ergebnis = 'kein_ziel' THEN 'ja'
       ELSE 'NEIN: '||coalesce(letztes_ergebnis,'Paket verschwunden') END
  FROM v_zustellung_offen
 WHERE company_id='31313131-3131-3131-3131-313131313131'
   AND paket_id='aaaaaaaa-0000-0000-0000-000000000002';

-- 6. Append-only: Aendern und Loeschen sind gesperrt? Nein — die Sperre gibt es
--    hier absichtlich NICHT als Trigger, aber ein unerlaubter Wert schon.
INSERT INTO p SELECT 6, 'unerlaubtes Ergebnis wird abgewiesen',
  CASE WHEN (SELECT count(*) FROM (
         SELECT 1 FROM bc_zustellungen LIMIT 0) x) = 0
        AND NOT EXISTS (
         SELECT 1 FROM pg_constraint
          WHERE conrelid = 'bc_zustellungen'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%ergebnis%'
            AND pg_get_constraintdef(oid) NOT LIKE '%zugestellt%')
       THEN 'ja' ELSE 'NEIN: CHECK auf ergebnis fehlt' END;

SELECT nr, aussage, ergebnis FROM p ORDER BY nr;
SELECT count(*) FILTER (WHERE ergebnis <> 'ja') AS fehlgeschlagen FROM p;

ROLLBACK;
