-- v3.43 (17.11.2026): KI-Reifegrad nach SEI (AI Adoption Maturity Model v1.0)
-- Teil A: Tabellen kia_* und Stammdaten (8 Dimensionen, 25 Faehigkeitsbereiche, Eintrittsstufe nach Tabelle 2 S. 85).
-- Teil B: Mockdaten NUR fuer den Mandanten "SIMULATION - NoroAI Consulting GmbH" (Kontext, Zielstufen, 16 Bewertungen).
-- Ausfuehren als bc0_app (DATABASE_URL der App), damit die Tabellen bc0_app gehoeren.
--   Probelauf: -v commit=0  -> ROLLBACK      Echter Lauf: -v commit=1 -> COMMIT
\set ON_ERROR_STOP on
BEGIN;
\echo '== Vorpruefung'
DO $v0$ BEGIN
  IF current_user <> 'bc0_app' THEN RAISE EXCEPTION 'als bc0_app ausfuehren, nicht als %', current_user; END IF;
  IF to_regclass('public.kia_bereiche') IS NOT NULL OR to_regclass('public.kia_bewertung') IS NOT NULL
  THEN RAISE EXCEPTION 'Tabellen existieren bereits'; END IF;
  IF NOT EXISTS (SELECT 1 FROM companies WHERE company_id='05abe89c-b2a6-4db6-9b22-66b9fb320b1d' AND name LIKE 'SIMULATION%')
  THEN RAISE EXCEPTION 'SIM-Mandant nicht gefunden'; END IF;
END $v0$;

\echo '== A. Tabellen'

CREATE TABLE kia_dimensionen (
  dim_nr  INTEGER PRIMARY KEY CHECK (dim_nr BETWEEN 1 AND 8),
  name    TEXT NOT NULL,
  gruppe  TEXT NOT NULL
);
CREATE TABLE kia_bereiche (
  bereich_id     TEXT PRIMARY KEY,
  dim_nr         INTEGER NOT NULL REFERENCES kia_dimensionen(dim_nr),
  name           TEXT NOT NULL,
  eintrittsstufe INTEGER NOT NULL CHECK (eintrittsstufe BETWEEN 1 AND 5),
  seite          INTEGER,
  menue          TEXT
);
CREATE TABLE kia_kontext (
  company_id         UUID PRIMARY KEY REFERENCES companies(company_id) ON DELETE CASCADE,
  umfang             TEXT NOT NULL DEFAULT 'mandant' CHECK (umfang IN ('mandant','bereich','kernprozess','team')),
  regulierung        TEXT CHECK (regulierung IN ('reguliert','teilweise','nicht_reguliert')),
  planungshorizont   TEXT CHECK (planungshorizont IN ('unter_6_monate','6_12_monate','1_3_jahre','ueber_3_jahre')),
  entwicklungsansatz TEXT CHECK (entwicklungsansatz IN ('selbst_bauen','kaufen','anpassen','gemischt')),
  risikobereitschaft TEXT CHECK (risikobereitschaft IN ('hoch','mittel','niedrig')),
  geaendert_von      TEXT,
  geaendert_am       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE kia_zielstufe (
  id          BIGSERIAL PRIMARY KEY,
  company_id  UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  dim_nr      INTEGER NOT NULL REFERENCES kia_dimensionen(dim_nr),
  zielstufe   INTEGER NOT NULL CHECK (zielstufe BETWEEN 1 AND 5),
  begruendung TEXT NOT NULL CHECK (length(btrim(begruendung)) > 0),
  gesetzt_von TEXT,
  gesetzt_am  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE kia_bewertung (
  id                 BIGSERIAL PRIMARY KEY,
  company_id         UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  bereich_id         TEXT NOT NULL REFERENCES kia_bereiche(bereich_id),
  ziele              TEXT NOT NULL CHECK (ziele IN ('erfuellt','teilweise','nein','zurueckgestellt')),
  nachweis           TEXT NOT NULL CHECK (nachweis IN ('messung','beleg','einschaetzung')),
  ind_verantwortung  INTEGER NOT NULL CHECK (ind_verantwortung BETWEEN 1 AND 5),
  ind_planung        INTEGER NOT NULL CHECK (ind_planung BETWEEN 1 AND 5),
  ind_ressourcen     INTEGER NOT NULL CHECK (ind_ressourcen BETWEEN 1 AND 5),
  beleg              TEXT,
  begruendung        TEXT NOT NULL CHECK (length(btrim(begruendung)) > 0),
  bewertet_von       TEXT,
  bewertet_am        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_kia_bewertung_co ON kia_bewertung(company_id, bereich_id, bewertet_am);
CREATE INDEX idx_kia_zielstufe_co ON kia_zielstufe(company_id, dim_nr, gesetzt_am);

-- Wie die uebrigen ki_-Tabellen: keine Rechte fuer andere Rollen (v3.11, v3.15, v3.42)
DO $r$ DECLARE r text; BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','bc_leser','bc1_role','bc2_role','bc3_role','bc4_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format('REVOKE ALL ON kia_dimensionen, kia_bereiche, kia_kontext, kia_zielstufe, kia_bewertung FROM %I', r);
      EXECUTE format('REVOKE ALL ON SEQUENCE kia_zielstufe_id_seq, kia_bewertung_id_seq FROM %I', r);
    END IF;
  END LOOP;
END $r$;

\echo '== A2. Stammdaten'
INSERT INTO kia_dimensionen(dim_nr, name, gruppe) VALUES
 (1,'Organisationsstrategie','Organisatorischer Wandel'),
 (2,'Belegschaft und Kultur','Organisatorischer Wandel'),
 (3,'Neugestaltung der Arbeitsabläufe','Organisatorischer Wandel'),
 (4,'Risiko und Governance','Organisatorischer Wandel'),
 (5,'Daten','KI-Lebenszyklus'),
 (6,'Engineering','KI-Lebenszyklus'),
 (7,'Betrieb','KI-Lebenszyklus'),
 (8,'Technologie-Ökosystem','KI-Lebenszyklus');
INSERT INTO kia_bereiche(bereich_id, dim_nr, name, eintrittsstufe, seite, menue) VALUES
 ('4.4.1',1,'Strategieentwicklung',2,33,'5 KI-Strategie'),
 ('4.4.2',1,'Partnerschaften',3,34,'5 KI-Strategie'),
 ('4.4.3',1,'Organisationsstruktur anpassen',3,36,'5 KI-Strategie'),
 ('4.4.4',1,'Zukunftsplanung',5,37,'5 KI-Strategie'),
 ('4.5.1',2,'KI-kompetente Belegschaft',1,41,'3 LongLife Learning'),
 ('4.5.2',2,'Wandel der Kultur',3,42,'3 LongLife Learning'),
 ('4.6.1',3,'Experimente',1,45,'Prozessdoku & Verantwortung'),
 ('4.6.2',3,'Neue Arbeitsabläufe',3,46,'Prozessdoku & Verantwortung'),
 ('4.6.3',3,'Mensch führt die Automatisierung',3,48,'Prozessdoku & Verantwortung'),
 ('4.6.4',3,'Messung und Analyse',3,49,'Prozessdoku & Verantwortung'),
 ('4.7.1',4,'Risikomanagement',2,52,'Risiko und Governance (neu)'),
 ('4.7.2',4,'Richtlinien und Compliance',2,54,'Risiko und Governance (neu)'),
 ('4.7.3',4,'Verantwortungsvolle KI',2,55,'Risiko und Governance (neu)'),
 ('4.8.1',5,'Lebenszyklus der Daten',2,58,'Daten und Sicherung (neu)'),
 ('4.8.2',5,'Datenqualität',2,60,'Daten und Sicherung (neu)'),
 ('4.9.1',6,'KI-Architektur',2,63,'Prozessdoku & Verantwortung'),
 ('4.9.2',6,'Test und Evaluation',2,64,'Prozessdoku & Verantwortung'),
 ('4.9.3',6,'Einbindung von Altsystemen',3,66,'Prozessdoku & Verantwortung'),
 ('4.9.4',6,'Transparenz und Erklärbarkeit',3,67,'4 Wissensdatenbank'),
 ('4.10.1',7,'Modellverwaltung',2,70,'5 KI-Strategie (Modellregister)'),
 ('4.10.2',7,'Sicherheit von Modellen und Agenten',2,71,'Test und Sicherheit (neu)'),
 ('4.10.3',7,'Überwachung',3,72,'1 Modell-Drift'),
 ('4.11.1',8,'Technische Infrastruktur',2,75,'2 MLOps · Tokenverbrauch'),
 ('4.11.2',8,'Lieferkette',3,76,'5 KI-Strategie (Modellregister)'),
 ('4.11.3',8,'Einsatz in der Breite',4,77,'Übersicht');

\echo '== B. Mockdaten SIMULATION (Bewertungen angenommen, an den SIM-Laufdaten ausgerichtet)'
INSERT INTO kia_kontext(company_id, umfang, regulierung, planungshorizont, entwicklungsansatz, risikobereitschaft, geaendert_von) VALUES
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','mandant','teilweise','1_3_jahre','gemischt','mittel','SIMULATION');
INSERT INTO kia_zielstufe(company_id, dim_nr, zielstufe, begruendung, gesetzt_von) VALUES
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d',1,3,'SIMULATION: KI für interne Produktivität – Stufe 3 (Aligned AI) genügt (SEI S. 15).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d',2,3,'SIMULATION: KI für interne Produktivität – Stufe 3 (Aligned AI) genügt (SEI S. 15).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d',3,3,'SIMULATION: KI für interne Produktivität – Stufe 3 (Aligned AI) genügt (SEI S. 15).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d',4,3,'SIMULATION: KI für interne Produktivität – Stufe 3 (Aligned AI) genügt (SEI S. 15).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d',5,3,'SIMULATION: KI für interne Produktivität – Stufe 3 (Aligned AI) genügt (SEI S. 15).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d',6,3,'SIMULATION: KI für interne Produktivität – Stufe 3 (Aligned AI) genügt (SEI S. 15).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d',7,3,'SIMULATION: KI für interne Produktivität – Stufe 3 (Aligned AI) genügt (SEI S. 15).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d',8,3,'SIMULATION: KI für interne Produktivität – Stufe 3 (Aligned AI) genügt (SEI S. 15).','SIMULATION');
INSERT INTO kia_bewertung(company_id, bereich_id, ziele, nachweis, ind_verantwortung, ind_planung, ind_ressourcen, beleg, begruendung, bewertet_von) VALUES
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.4.1','erfuellt','messung',3,2,2,NULL,'SIMULATION: KI-Strategie beschlossen; UC1 mit 5 Kennzahlen und Zielwerten (kir_kennzahlen).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.4.2','teilweise','einschaetzung',2,1,1,NULL,'SIMULATION: Markt wird beobachtet, aber ohne festen Takt und ohne Partnerbewertung.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.4.3','nein','einschaetzung',1,1,1,NULL,'SIMULATION: Keine Rollen für KI festgelegt.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.5.1','teilweise','einschaetzung',2,2,1,NULL,'SIMULATION: Grundschulung geplant, Lückenanalyse je Rolle fehlt.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.5.2','nein','einschaetzung',1,1,1,NULL,'SIMULATION: Noch keine Erhebung, wie die Beteiligten die KI-Vorhaben wahrnehmen.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.6.1','erfuellt','messung',3,3,2,NULL,'SIMULATION: 3 Durchläufe UC1 mit Entscheidung (kir_durchlauf).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.6.3','teilweise','beleg',2,2,2,'Agentenblätter D1–D3, Abschnitt Kontrollpunkte','SIMULATION: Kontrollpunkte beschrieben, Korrekturen werden aber nicht je Lauf erfasst.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.6.4','erfuellt','messung',3,3,3,NULL,'SIMULATION: Alle 5 Kennzahlen mit Messwerten vorher/nachher (kir_messwerte).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.7.1','nein','einschaetzung',1,1,1,NULL,'SIMULATION: Keine Risikoeinstufung je Teilprozess.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.9.1','erfuellt','beleg',2,2,2,'Agentenblätter D1–D3 (Werkzeuge, Agenten)','SIMULATION: Architektur je Teilprozess im Agentenblatt beschrieben.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.9.2','erfuellt','messung',3,3,3,NULL,'SIMULATION: 28 Kriterien mit Testfall; letzter Durchlauf 26 von 28 bestanden.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.10.1','erfuellt','messung',2,2,2,NULL,'SIMULATION: Beide verwendeten Modelle im Modellregister (v3.42).','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.10.2','erfuellt','beleg',2,2,2,'Agentenblätter geprüft (geprueft_am)','SIMULATION: Agentenverzeichnis vorhanden; Interaktionsprotokoll über ki_laufdaten.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.10.3','teilweise','messung',2,2,1,NULL,'SIMULATION: Korrektur für claude-opus-5-5 nicht erfasst (0 von 18 Läufen) – Drift dort nicht messbar.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.11.1','erfuellt','messung',2,2,2,NULL,'SIMULATION: Token und Kosten je Lauf vollständig erfasst.','SIMULATION'),
 ('05abe89c-b2a6-4db6-9b22-66b9fb320b1d','4.11.2','erfuellt','messung',3,2,2,NULL,'SIMULATION: Beide Modelle mit Abschaltdatum haben einen Wechselplan.','SIMULATION');

\echo '== Gegenprobe 1: Stammdaten (ERWARTET 8 | 25 | Eintrittsstufen 1:2 2:11 3:10 4:1 5:1)'
SELECT (SELECT count(*) FROM kia_dimensionen) AS dimensionen, (SELECT count(*) FROM kia_bereiche) AS bereiche,
       (SELECT string_agg(e||':'||n, ' ' ORDER BY e) FROM (SELECT eintrittsstufe e, count(*) n FROM kia_bereiche GROUP BY 1) x) AS eintrittsstufen;
\echo '== Gegenprobe 2: Mockdaten je Mandant (ERWARTET nur SIM: Kontext 1, Zielstufen 8, Bewertungen 16)'
SELECT c.name, (SELECT count(*) FROM kia_kontext k WHERE k.company_id=c.company_id) AS kontext,
       (SELECT count(*) FROM kia_zielstufe z WHERE z.company_id=c.company_id) AS zielstufen,
       (SELECT count(*) FROM kia_bewertung b WHERE b.company_id=c.company_id) AS bewertungen
  FROM companies c ORDER BY 1;
\echo '== Gegenprobe 3: Rechte anderer Rollen auf kia_* (ERWARTET 0 Zeilen)'
SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants
 WHERE table_name LIKE 'kia_%' AND grantee NOT IN ('bc0_app','postgres','supabase_admin');

\if :commit
  COMMIT;
  \echo '== COMMIT: v3.43 KI-Reifegrad nach SEI angelegt'
\else
  ROLLBACK;
  \echo '== PROBELAUF: ROLLBACK – nichts geaendert'
\endif
