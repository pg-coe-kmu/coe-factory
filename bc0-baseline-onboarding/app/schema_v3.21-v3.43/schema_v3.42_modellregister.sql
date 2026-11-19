-- v3.42 (15.11.2026): Modellregister und Wechselplan je Modell (KI-Strategie)
-- Teil A: zwei neue Tabellen (fuer alle Mandanten, leer).
-- Teil B: Mockdaten NUR fuer den Mandanten "SIMULATION - NoroAI Consulting GmbH".
-- Ausfuehren als bc0_app (DATABASE_URL der App), damit die Tabellen bc0_app gehoeren.
--   Probelauf: -v commit=0  -> ROLLBACK      Echter Lauf: -v commit=1 -> COMMIT
\set ON_ERROR_STOP on
BEGIN;
\echo '== Vorpruefung'
DO $v0$ BEGIN
  IF current_user <> 'bc0_app' THEN RAISE EXCEPTION 'als bc0_app ausfuehren, nicht als %', current_user; END IF;
  IF to_regclass('public.ki_modellregister') IS NOT NULL OR to_regclass('public.ki_modellwechsel_schritte') IS NOT NULL
  THEN RAISE EXCEPTION 'Tabellen existieren bereits'; END IF;
  IF NOT EXISTS (SELECT 1 FROM companies WHERE company_id='05abe89c-b2a6-4db6-9b22-66b9fb320b1d' AND name LIKE 'SIMULATION%')
  THEN RAISE EXCEPTION 'SIM-Mandant nicht gefunden'; END IF;
  IF NOT EXISTS (SELECT 1 FROM ki_strategie WHERE company_id='05abe89c-b2a6-4db6-9b22-66b9fb320b1d')
  THEN RAISE EXCEPTION 'SIM-Mandant hat keine KI-Strategie'; END IF;
END $v0$;

\echo '== A. Tabellen'
CREATE TABLE ki_modellregister (
  id              BIGSERIAL PRIMARY KEY,
  company_id      UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  modell          TEXT NOT NULL,
  anbieter        TEXT,
  betriebsart     TEXT NOT NULL DEFAULT 'cloud' CHECK (betriebsart IN ('cloud','lokal')),
  status          TEXT NOT NULL DEFAULT 'im_einsatz' CHECK (status IN ('im_einsatz','abgekuendigt','wechsel_laeuft','abgeloest')),
  abgekuendigt_am DATE,
  abschaltung_am  DATE,
  nachfolger      TEXT,
  person_id       TEXT,
  bemerkung       TEXT,
  UNIQUE (company_id, modell)
);
CREATE TABLE ki_modellwechsel_schritte (
  id          BIGSERIAL PRIMARY KEY,
  company_id  UUID NOT NULL,
  modell      TEXT NOT NULL,
  schritt_nr  INTEGER NOT NULL CHECK (schritt_nr BETWEEN 1 AND 20),
  titel       TEXT NOT NULL,
  kriterium   TEXT,
  zieldatum   DATE NOT NULL,
  erledigt_am DATE,
  UNIQUE (company_id, modell, schritt_nr),
  FOREIGN KEY (company_id, modell) REFERENCES ki_modellregister(company_id, modell) ON DELETE CASCADE ON UPDATE CASCADE
);
-- Wie die uebrigen ki_-Tabellen: keine Rechte fuer andere Rollen (v3.11, v3.15)
DO $r$ DECLARE r text; BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','bc_leser','bc1_role','bc4_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format('REVOKE ALL ON ki_modellregister, ki_modellwechsel_schritte FROM %I', r);
      EXECUTE format('REVOKE ALL ON SEQUENCE ki_modellregister_id_seq, ki_modellwechsel_schritte_id_seq FROM %I', r);
    END IF;
  END LOOP;
END $r$;

\echo '== B. Mockdaten SIMULATION (Abkuendigung und Abschaltdaten ANGENOMMEN, keine echte Ankuendigung eines Anbieters)'
INSERT INTO ki_modellregister(company_id, modell, anbieter, betriebsart, status, abgekuendigt_am, abschaltung_am, nachfolger, bemerkung) VALUES
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','claude-opus-5-5','Anthropic','cloud','wechsel_laeuft','2026-11-10','2027-05-31',NULL,
  'SIMULATION: Abkündigung und Abschaltdatum sind angenommen, keine echte Ankündigung des Anbieters. Nachfolger wird in Schritt 3 gewählt.'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','mistral:7b','Mistral AI','lokal','im_einsatz',NULL,'2028-03-31',NULL,
  'SIMULATION: lokal betrieben (Anbieterintegration). Geplante Ablösung angenommen, weil das Modell keine Updates mehr erhält; keine Ankündigung des Anbieters.');

INSERT INTO ki_modellwechsel_schritte(company_id, modell, schritt_nr, titel, kriterium, zieldatum, erledigt_am)
SELECT '05abe89c-b2a6-4db6-9b22-66b9fb320b1d', m, nr, t, k, z::date, e::date FROM (VALUES
 ('claude-opus-5-5',1,'Abkündigung erkannt, Abschaltdatum notiert','Datum steht fest','2026-11-10','2026-11-10'),
 ('claude-opus-5-5',2,'Inventur: betroffene Agents und Teilprozesse','Liste aus den Laufdaten: KP-06.TP-2 bis TP-5','2026-11-13','2026-11-13'),
 ('claude-opus-5-5',3,'Nachfolger wählen, Regressionstest gegen die 28 BC4-Testfälle (Durchlauf 4)','Erfüllungsgrad ≥ 75,5 % (Stand Durchlauf 3)','2027-01-15',NULL),
 ('claude-opus-5-5',4,'Agentenblätter anpassen, Abnahme durch die Prozessverantwortlichen','Agentenblatt geprüft','2027-02-05',NULL),
 ('claude-opus-5-5',5,'Schattenbetrieb, neue Einlaufphase der Drift-Karte','0 Punkte außerhalb ±3σ','2027-03-05',NULL),
 ('claude-opus-5-5',6,'Umschaltung, kurze Schulung (LongLife Learning)','Kosten ≤ Investitions-Richtwert aus BC2','2027-04-09',NULL),
 ('claude-opus-5-5',7,'Altmodell abgeschaltet','keine Läufe mehr auf dem Altmodell','2027-05-03',NULL),
 ('mistral:7b',1,'Abkündigung erkannt, Abschaltdatum notiert','Datum steht fest','2028-01-03',NULL),
 ('mistral:7b',2,'Inventur: betroffene Agents und Teilprozesse','Liste aus den Laufdaten','2028-01-10',NULL),
 ('mistral:7b',3,'Nachfolger wählen, Regressionstest gegen die BC4-Testfälle','Erfüllungsgrad ≥ letzter Stand','2028-01-31',NULL),
 ('mistral:7b',4,'Agentenblätter anpassen, Abnahme durch die Prozessverantwortlichen','Agentenblatt geprüft','2028-02-14',NULL),
 ('mistral:7b',5,'Schattenbetrieb, neue Einlaufphase der Drift-Karte','0 Punkte außerhalb ±3σ','2028-02-28',NULL),
 ('mistral:7b',6,'Umschaltung, kurze Schulung (LongLife Learning)','Kosten ≤ Investitions-Richtwert aus BC2','2028-03-13',NULL),
 ('mistral:7b',7,'Altmodell abgeschaltet','keine Läufe mehr auf dem Altmodell','2028-03-27',NULL)
) v(m,nr,t,k,z,e);

UPDATE ki_strategie
   SET beschreibung = coalesce(nullif(beschreibung,'') || E'\n\n','') ||
       'Modellwechsel (SIMULATION): Jeder Modellwechsel ist ein eigener BC4-Durchlauf. Umgeschaltet wird nur, wenn der Erfüllungsgrad mindestens den letzten Stand erreicht, die Drift-Karte in der neuen Einlaufphase keinen Punkt außerhalb ±3σ zeigt und die Generatorkosten unter dem Investitions-Richtwert aus BC2 bleiben. Abschaltdaten der Anbieter stehen im Modellregister und werden mit der Strategie halbjährlich überprüft.'
 WHERE company_id='05abe89c-b2a6-4db6-9b22-66b9fb320b1d'
   AND position('Modellwechsel (SIMULATION)' IN coalesce(beschreibung,'')) = 0;

\echo '== Gegenprobe 1: Zeilen je Mandant (ERWARTET nur SIM: 2 Modelle, 14 Schritte, 2 erledigt)'
SELECT c.name, (SELECT count(*) FROM ki_modellregister r WHERE r.company_id=c.company_id) AS modelle,
       (SELECT count(*) FROM ki_modellwechsel_schritte s WHERE s.company_id=c.company_id) AS schritte,
       (SELECT count(*) FROM ki_modellwechsel_schritte s WHERE s.company_id=c.company_id AND s.erledigt_am IS NOT NULL) AS erledigt
  FROM companies c ORDER BY c.name;
\echo '== Gegenprobe 2: Modelle im Register gegen Laufdaten SIM (ERWARTET je Modell laeufe > 0)'
SELECT r.modell, r.status, r.abschaltung_am, count(l.id) AS laeufe,
       string_agg(DISTINCT l.sub_process_id, ', ' ORDER BY l.sub_process_id) AS teilprozesse
  FROM ki_modellregister r LEFT JOIN ki_laufdaten l ON l.company_id=r.company_id AND l.modell=r.modell
 GROUP BY 1,2,3 ORDER BY 3;
\echo '== Gegenprobe 3: Rechte anderer Rollen auf den neuen Tabellen (ERWARTET 0 Zeilen)'
SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants
 WHERE table_schema='public' AND table_name IN ('ki_modellregister','ki_modellwechsel_schritte')
   AND grantee NOT IN ('bc0_app','postgres');
\echo '== Gegenprobe 4: Strategie SIM ergaenzt (ERWARTET t), andere Mandanten unveraendert (ERWARTET 0)'
SELECT position('Modellwechsel (SIMULATION)' IN beschreibung) > 0 AS sim_ergaenzt FROM ki_strategie
 WHERE company_id='05abe89c-b2a6-4db6-9b22-66b9fb320b1d';
SELECT count(*) AS andere_mit_text FROM ki_strategie
 WHERE company_id<>'05abe89c-b2a6-4db6-9b22-66b9fb320b1d' AND position('Modellwechsel (SIMULATION)' IN coalesce(beschreibung,'')) > 0;

\if :commit
COMMIT;
\echo '== COMMIT: v3.42 Modellregister angelegt'
\else
ROLLBACK;
\echo '== PROBELAUF: ROLLBACK - nichts geaendert'
\endif
