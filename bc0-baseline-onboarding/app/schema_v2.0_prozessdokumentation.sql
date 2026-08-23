-- ============================================================
-- BC0 Onboarding — Schema v2.0: Dokumentation automatisierter Prozesse
-- Stand: 19.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- ANLASS
--   "Skills und Wissen um einen automatisierten Prozess verlieren sich im
--   Laufe der Zeit." Dagegen hilft kein Reifegradmodell, sondern eine
--   Dokumentation, die aktuell gehalten wird.
--
-- WOHER DAS RASTER STAMMT
--   Sechs der neun Bereiche aus Anhang IV der KI-Verordnung. Die drei
--   uebrigen — Risikomanagement im Sinne der Verordnung, angewandte Normen,
--   Konformitaetserklaerung — setzen ein Konformitaetsverfahren voraus, das
--   wir nicht fuehren, und bleiben deshalb aussen vor.
--
--   Wir uebernehmen ein verbindliches Raster, statt eines zu erfinden. Wer
--   den Prozess in zwei Jahren uebernimmt, findet eine Struktur vor, die er
--   anderswo schon gesehen hat.
--
-- WAS DER ANHANG NICHT ABDECKT UND HIER DAZUKOMMT
--   Erstens die Agenten: "was macht welcher Agent" ist bei einem
--   Mehr-Agenten-System eine eigene Angabe. Zweitens die AKTUALITAET — der
--   Anhang verlangt, dass dokumentiert IST, nicht dass es noch STIMMT. Eine
--   Dokumentation, die zwei Jahre niemand gelesen hat, ist in aller Regel
--   falsch: Der Prompt wurde geaendert, eine Bibliothek getauscht, ein
--   Schwellenwert nachjustiert. Deshalb die Felder geprueft_am/geprueft_von
--   und die Frage, wer den Prozess heute noch aendern koennte.
--
-- EBENE: TEILPROZESS
--   Wir automatisieren Teilprozesse, nicht Kernprozesse. Die Dokumentation
--   haengt deshalb an sub_process_id.
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v2.0_prozessdokumentation.sql
-- ============================================================

BEGIN;

-- ============================================================
-- 33. DOKUMENTATIONSBLATT JE TEILPROZESS
-- ============================================================

CREATE TABLE IF NOT EXISTS prozess_dokumentation (
  company_id      UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  sub_process_id  VARCHAR(16) NOT NULL,

  -- Anhang IV Nr. 1 — Allgemeine Beschreibung
  bezeichnung     TEXT NOT NULL CHECK (length(btrim(bezeichnung)) > 0),
  zweck           TEXT NOT NULL CHECK (length(btrim(zweck)) > 0),
  ersteller       TEXT NOT NULL CHECK (length(btrim(ersteller)) > 0),
  version         TEXT NOT NULL CHECK (length(btrim(version)) > 0),
  in_betrieb_seit DATE,
  einsatzumgebung TEXT,

  -- Anhang IV Nr. 2 — Entwicklung und Design
  vorgehen        TEXT,
  entscheidungen  TEXT,

  -- Anhang IV Nr. 3 — Funktionsweise, Leistung, Grenzen
  ablauf          TEXT NOT NULL CHECK (length(btrim(ablauf)) > 0),
  grenzen         TEXT NOT NULL CHECK (length(btrim(grenzen)) > 0),
  bekannte_fehler TEXT,

  -- Anhang IV Nr. 4 — Leistungsmetriken
  metriken        TEXT,
  metriken_warum  TEXT,

  -- Anhang IV Nr. 9 — Beobachtung im Betrieb
  ueberwachung    TEXT,
  schwellenwerte  TEXT,
  bei_stoerung    TEXT,

  -- Betrieb und Verantwortung
  betriebsmodell  TEXT CHECK (betriebsmodell IS NULL OR betriebsmodell IN
                    ('selbst_gehostet','saas','hybrid','on_premise')),
  standort        TEXT,
  fachlich_person_id  TEXT,
  technisch_person_id TEXT,

  -- Aktualitaet — nicht aus Anhang IV, sondern gegen den Wissensverlust
  geprueft_am     DATE,
  geprueft_von    TEXT,
  aenderbar_durch TEXT,

  angelegt_am     TIMESTAMPTZ NOT NULL DEFAULT now(),
  geaendert_am    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, sub_process_id),
  FOREIGN KEY (company_id, sub_process_id)
    REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE
);

COMMENT ON TABLE prozess_dokumentation IS
  'Ein Blatt je automatisiertem Teilprozess, Raster aus Anhang IV der '
  'KI-Verordnung (Bereiche 1, 2, 3, 4 und 9).';

COMMENT ON COLUMN prozess_dokumentation.grenzen IS
  'Pflichtfeld. Was der Prozess NICHT kann und wo er falsch liegt, ist die '
  'Angabe, die im Betrieb am meisten wert ist — und die zuerst weggelassen '
  'wird.';

COMMENT ON COLUMN prozess_dokumentation.aenderbar_durch IS
  'Wer diesen Prozess heute aendern koennte — Personen-IDs, keine Rollen. '
  'Die haerteste der Aktualitaetsfragen: Steht hier niemand, ist der Prozess '
  'nicht mehr beherrschbar, gleichgueltig wie gut er dokumentiert ist.';

COMMENT ON COLUMN prozess_dokumentation.geprueft_am IS
  'Wann die Dokumentation zuletzt gegen den laufenden Stand gehalten wurde. '
  'Nicht wann sie geschrieben wurde.';


-- ============================================================
-- 34. WERKZEUGE — ANHANG IV NR. 2
-- ============================================================
-- Kein Freitext: Anschluss an den Systemkatalog, wo vorhanden.

CREATE TABLE IF NOT EXISTS prozess_dok_werkzeuge (
  company_id     UUID        NOT NULL,
  sub_process_id VARCHAR(16) NOT NULL,
  lfd            INTEGER     NOT NULL,
  katalog_id     TEXT        REFERENCES ref_systeme_katalog(katalog_id),
  bezeichnung    TEXT        NOT NULL CHECK (length(btrim(bezeichnung)) > 0),
  version        TEXT        NOT NULL CHECK (length(btrim(version)) > 0),
  art            TEXT        NOT NULL CHECK (art IN
                   ('laufzeit','bibliothek','dienst','modell','entwicklung','orchestrierung')),
  anbieter       TEXT,
  quelloffen     BOOLEAN,
  lizenz         TEXT,
  hinweis        TEXT,
  PRIMARY KEY (company_id, sub_process_id, lfd),
  FOREIGN KEY (company_id, sub_process_id)
    REFERENCES prozess_dokumentation(company_id, sub_process_id) ON DELETE CASCADE
);

COMMENT ON COLUMN prozess_dok_werkzeuge.version IS
  'Pflicht. Ein Werkzeug ohne Version ist keine Angabe.';


-- ============================================================
-- 35. AGENTEN
-- ============================================================
-- Nicht aus Anhang IV. "Was macht welcher Agent" ist bei einem
-- Mehr-Agenten-System die Auskunft, auf die es ankommt.

CREATE TABLE IF NOT EXISTS prozess_dok_agenten (
  company_id     UUID        NOT NULL,
  sub_process_id VARCHAR(16) NOT NULL,
  agent_id       TEXT        NOT NULL CHECK (agent_id ~ '^A[0-9]{2}$'),
  bezeichnung    TEXT        NOT NULL CHECK (length(btrim(bezeichnung)) > 0),
  aufgabe        TEXT        NOT NULL CHECK (length(btrim(aufgabe)) > 0),
  nicht_aufgabe  TEXT,
  werkzeugzugriff TEXT,
  bekommt_von    TEXT,
  gibt_an        TEXT,
  eskalation     TEXT        NOT NULL CHECK (length(btrim(eskalation)) > 0),
  modell         TEXT,
  modell_version TEXT,
  prompt_fassung TEXT,
  deterministisch BOOLEAN,
  PRIMARY KEY (company_id, sub_process_id, agent_id),
  FOREIGN KEY (company_id, sub_process_id)
    REFERENCES prozess_dokumentation(company_id, sub_process_id) ON DELETE CASCADE
);

COMMENT ON COLUMN prozess_dok_agenten.nicht_aufgabe IS
  'Was der Agent ausdruecklich NICHT tut. Bei mehreren Agenten die Angabe, '
  'die Zustaendigkeitsluecken sichtbar macht.';

COMMENT ON COLUMN prozess_dok_agenten.eskalation IS
  'Pflicht. Wann der Agent abbricht und an einen Menschen uebergibt. Ein '
  'Agent ohne Ausstieg ist der Fall, in dem hinterher niemand erklaeren '
  'kann, warum etwas passiert ist.';

COMMENT ON COLUMN prozess_dok_agenten.prompt_fassung IS
  'Bei einem sprachmodellgestuetzten Agenten IST der Prompt die '
  'Geschaeftsregel. Er aendert den Prozess ohne Deployment, ohne '
  'Codeaenderung und ohne Spur — deshalb gehoert seine Fassung hierher.';


-- ============================================================
-- 36. TESTS — ANHANG IV NR. 6
-- ============================================================

CREATE TABLE IF NOT EXISTS prozess_dok_tests (
  company_id     UUID        NOT NULL,
  sub_process_id VARCHAR(16) NOT NULL,
  lfd            INTEGER     NOT NULL,
  am             DATE        NOT NULL,
  verfahren      TEXT        NOT NULL,
  datengrundlage TEXT,
  ergebnis       TEXT        NOT NULL,
  durchgefuehrt_von TEXT,
  PRIMARY KEY (company_id, sub_process_id, lfd),
  FOREIGN KEY (company_id, sub_process_id)
    REFERENCES prozess_dokumentation(company_id, sub_process_id) ON DELETE CASCADE
);


-- ============================================================
-- 37. LESESICHT — WIE VOLLSTAENDIG UND WIE ALT
-- ============================================================

CREATE OR REPLACE VIEW v_prozess_dokumentation_stand AS
SELECT d.company_id, d.sub_process_id, left(d.sub_process_id, 5) AS process_id,
       d.bezeichnung, d.version, d.in_betrieb_seit,
       (SELECT count(*) FROM prozess_dok_werkzeuge w
         WHERE w.company_id = d.company_id AND w.sub_process_id = d.sub_process_id) AS werkzeuge,
       (SELECT count(*) FROM prozess_dok_agenten a
         WHERE a.company_id = d.company_id AND a.sub_process_id = d.sub_process_id) AS agenten,
       (SELECT count(*) FROM prozess_dok_tests t
         WHERE t.company_id = d.company_id AND t.sub_process_id = d.sub_process_id) AS tests,
       d.geprueft_am,
       CASE WHEN d.geprueft_am IS NULL THEN NULL
            ELSE (CURRENT_DATE - d.geprueft_am) END AS tage_seit_pruefung,
       -- Eine Dokumentation, die laenger als ein halbes Jahr nicht gegen den
       -- laufenden Stand gehalten wurde, gilt als ueberpruefungsbeduerftig.
       CASE WHEN d.geprueft_am IS NULL THEN TRUE
            ELSE (CURRENT_DATE - d.geprueft_am) > 183 END AS pruefung_faellig,
       (d.aenderbar_durch IS NULL OR btrim(d.aenderbar_durch) = '') AS niemand_kann_aendern
  FROM prozess_dokumentation d;

COMMENT ON VIEW v_prozess_dokumentation_stand IS
  'Vollstaendigkeit und Alter je Blatt. niemand_kann_aendern ist der Befund, '
  'auf den es ankommt — ein Prozess, den niemand mehr aendern kann, ist '
  'nicht beherrschbar, gleichgueltig wie gut er beschrieben ist.';

COMMIT;


-- ============================================================
-- GEGENPROBE
-- ============================================================
--   SELECT count(*) FROM prozess_dokumentation;
--   SELECT sub_process_id, werkzeuge, agenten, tests, pruefung_faellig,
--          niemand_kann_aendern FROM v_prozess_dokumentation_stand ORDER BY 1;
-- ============================================================
