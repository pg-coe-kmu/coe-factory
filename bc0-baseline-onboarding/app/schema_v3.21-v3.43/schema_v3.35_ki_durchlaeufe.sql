-- ============================================================
-- BC0 · Schema v3.35 — KI-Reifegrad: Durchläufe 1..x, Prüfprotokoll, Datenstruktur, Erfüllungsgrad
-- Stand: 05.11.2026 · BC0 · PostgreSQL >= 15
-- Grundlage: Datenmodell_v3.35_ENTWURF.md; Entscheidungen BC0 05.11.:
--   D1 Durchlauf = Paket + durchlauf_nr · D2 Gewichte A/K/W = 40/40/20 · D3 fehlender Anteil zählt 0
-- Eigentümer aller Objekte: BC0. BC4 (und für Akzeptanzkriterien BC3) schreibt über die eigene Rolle,
-- nur anhängend (ADR-003 R1, ADR-004 R4, ADR-005 R1/R2). Personen nur als Kennung (ADR-004 R5).
-- Das Agentenblatt (v3.32) wird je Durchlauf geführt. Die vier Tabellen sind bis heute LEER und werden
-- neu angelegt; das Skript bricht ab, wenn darin doch etwas steht.
-- Alles in einer Transaktion. ON_ERROR_STOP=1 verwenden.
-- EINSPIELEN:
--   cd /opt/bc0 && docker run --rm -i --env-file .env postgres:17 sh -c \
--     'psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -P pager=off' < schema_v3.35_ki_durchlaeufe.sql
-- ============================================================

BEGIN;

\echo '--- 0. Vorher: Agentenblatt leer? (ERWARTET: 0 | 0 | 0 | 0)'
SELECT (SELECT count(*) FROM prozess_dokumentation) AS blatt,
       (SELECT count(*) FROM prozess_dok_werkzeuge) AS werkzeuge,
       (SELECT count(*) FROM prozess_dok_agenten)   AS agenten,
       (SELECT count(*) FROM prozess_dok_tests)     AS tests;
DO $c$ BEGIN
  IF (SELECT count(*) FROM prozess_dokumentation) + (SELECT count(*) FROM prozess_dok_werkzeuge)
   + (SELECT count(*) FROM prozess_dok_agenten)   + (SELECT count(*) FROM prozess_dok_tests) > 0 THEN
    RAISE EXCEPTION 'Agentenblatt ist nicht mehr leer – Abbruch, nichts geaendert. Erst sichern und Umbau anpassen.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='bc4_role') THEN
    RAISE EXCEPTION 'bc4_role fehlt – Abbruch.';
  END IF;
END $c$;

-- ------------------------------------------------------------
-- 1. Kennung statt Name (ADR-004 R5)
--    P-NN       Person aus ref_personen des Mandanten
--    UUID       Konto der BC0-Anwendung (app_benutzer.benutzer_id)
--    BCn-XXXX   Kennung eines Projektmitglieds; die Zuordnung zur Person führt der jeweilige BC,
--               nicht diese Datenbank.
-- ------------------------------------------------------------
DO $d$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='ki_kennung') THEN
    CREATE DOMAIN ki_kennung AS TEXT CHECK (VALUE ~ '^(P-[0-9]{2,3}|BC[0-4]-[A-Z0-9]{2,8}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$');
  END IF;
END $d$;

CREATE OR REPLACE FUNCTION ist_kennung(p TEXT) RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $f$
  SELECT p ~ '^(P-[0-9]{2,3}|BC[0-4]-[A-Z0-9]{2,8}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'
$f$;

-- Nur anhängen; Kaskade beim Löschen des Mandanten bleibt möglich (wie trg_nur_anhaengen).
CREATE OR REPLACE FUNCTION trg_ki_nur_anhaengen() RETURNS TRIGGER AS $fn$
BEGIN
  IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN RETURN OLD; END IF;
  RAISE EXCEPTION '% ist nur anhaengend: % nicht erlaubt. Eine neue Fassung ist ein neuer Durchlauf.',
    TG_TABLE_NAME, TG_OP USING ERRCODE = 'check_violation';
END;
$fn$ LANGUAGE plpgsql;

-- ------------------------------------------------------------
-- 2. T1 ki_durchlauf — BC0 legt an, ein Mensch entscheidet am Ende
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ki_durchlauf (
  company_id      UUID        NOT NULL,
  paket_id        UUID        NOT NULL,
  durchlauf_nr    INTEGER     NOT NULL CHECK (durchlauf_nr BETWEEN 1 AND 99),
  use_case        TEXT        NOT NULL CHECK (use_case ~ '^UC[0-9]{1,2}$'),
  anlass          TEXT        NOT NULL CHECK (length(btrim(anlass)) > 0),
  angelegt_am     TIMESTAMPTZ NOT NULL DEFAULT now(),
  angelegt_von    ki_kennung  NOT NULL,
  entscheidung    TEXT        CHECK (entscheidung IN ('weiter','nachbessern','verwerfen')),
  entschieden_am  TIMESTAMPTZ,
  entschieden_von ki_kennung,
  begruendung     TEXT,
  PRIMARY KEY (company_id, paket_id, durchlauf_nr),
  UNIQUE (company_id, paket_id, durchlauf_nr, use_case),
  FOREIGN KEY (company_id, paket_id) REFERENCES gate_pakete(company_id, paket_id) ON DELETE CASCADE,
  CONSTRAINT ck_durchlauf_entscheidung CHECK (
    (entscheidung IS NULL AND entschieden_am IS NULL AND entschieden_von IS NULL)
    OR (entscheidung IS NOT NULL AND entschieden_am IS NOT NULL AND entschieden_von IS NOT NULL
        AND length(btrim(coalesce(begruendung,''))) > 0))
);
COMMENT ON TABLE ki_durchlauf IS
  'Durchlauf = ein Gang eines Pakets durch BC2-BC3-BC4 und Test. 1..x je Paket. BC1 und Gate 0 laufen einmal. '
  'Abschluss nur mit Entscheidung eines Menschen (weiter/nachbessern/verwerfen) und Begruendung.';

CREATE OR REPLACE FUNCTION trg_ki_durchlauf_pruefen() RETURNS TRIGGER AS $fn$
DECLARE v_max INTEGER; v_uc TEXT;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF pg_trigger_depth() > 1 THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'ki_durchlauf: Loeschen nicht erlaubt.' USING ERRCODE='check_violation';
  END IF;
  IF TG_OP = 'INSERT' THEN
    SELECT max(durchlauf_nr), max(use_case) INTO v_max, v_uc FROM ki_durchlauf
     WHERE company_id = NEW.company_id AND paket_id = NEW.paket_id;
    IF NEW.durchlauf_nr <> coalesce(v_max,0) + 1 THEN
      RAISE EXCEPTION 'Durchlauf % passt nicht: als naechster ist % dran.', NEW.durchlauf_nr, coalesce(v_max,0)+1
        USING ERRCODE='check_violation';
    END IF;
    IF v_uc IS NOT NULL AND v_uc <> NEW.use_case THEN
      RAISE EXCEPTION 'Paket gehoert zu %, nicht zu %.', v_uc, NEW.use_case USING ERRCODE='check_violation';
    END IF;
    IF NEW.entscheidung IS NOT NULL THEN
      RAISE EXCEPTION 'Ein Durchlauf wird ohne Entscheidung angelegt.' USING ERRCODE='check_violation';
    END IF;
    RETURN NEW;
  END IF;
  -- UPDATE: nur einmal entscheiden, sonst nichts aendern
  IF OLD.entscheidung IS NOT NULL THEN
    RAISE EXCEPTION 'Durchlauf % ist entschieden (%), Aenderung nicht erlaubt.', OLD.durchlauf_nr, OLD.entscheidung
      USING ERRCODE='check_violation';
  END IF;
  IF (NEW.company_id, NEW.paket_id, NEW.durchlauf_nr, NEW.use_case, NEW.anlass, NEW.angelegt_am, NEW.angelegt_von)
     IS DISTINCT FROM (OLD.company_id, OLD.paket_id, OLD.durchlauf_nr, OLD.use_case, OLD.anlass, OLD.angelegt_am, OLD.angelegt_von) THEN
    RAISE EXCEPTION 'An einem Durchlauf ist nur die Entscheidung nachzutragen.' USING ERRCODE='check_violation';
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS ki_durchlauf_pruefen ON ki_durchlauf;
CREATE TRIGGER ki_durchlauf_pruefen BEFORE INSERT OR UPDATE OR DELETE ON ki_durchlauf
  FOR EACH ROW EXECUTE FUNCTION trg_ki_durchlauf_pruefen();
DO $h$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='trg_historie') THEN
    EXECUTE 'DROP TRIGGER IF EXISTS historie ON ki_durchlauf';
    EXECUTE 'CREATE TRIGGER historie AFTER INSERT OR UPDATE OR DELETE ON ki_durchlauf FOR EACH ROW EXECUTE FUNCTION trg_historie()';
  END IF;
END $h$;

-- ------------------------------------------------------------
-- 3. T2 Agentenblatt je Durchlauf (Neuanlage der leeren Tabellen aus v3.32, Spalten unveraendert + Bezug)
-- ------------------------------------------------------------
DROP VIEW  IF EXISTS v_prozess_dokumentation_stand;
DROP TABLE IF EXISTS prozess_dok_tests, prozess_dok_agenten, prozess_dok_werkzeuge, prozess_dokumentation;

CREATE TABLE prozess_dokumentation (
  company_id      UUID        NOT NULL,
  sub_process_id  VARCHAR(16) NOT NULL,
  paket_id        UUID        NOT NULL,
  durchlauf_nr    INTEGER     NOT NULL,
  bezeichnung     TEXT NOT NULL CHECK (length(btrim(bezeichnung)) > 0),
  zweck           TEXT NOT NULL CHECK (length(btrim(zweck)) > 0),
  ersteller       TEXT NOT NULL CHECK (length(btrim(ersteller)) > 0),
  version         TEXT NOT NULL CHECK (length(btrim(version)) > 0),
  in_betrieb_seit DATE,
  einsatzumgebung TEXT,
  vorgehen        TEXT,
  entscheidungen  TEXT,
  ablauf          TEXT NOT NULL CHECK (length(btrim(ablauf)) > 0),
  grenzen         TEXT NOT NULL CHECK (length(btrim(grenzen)) > 0),
  bekannte_fehler TEXT,
  metriken        TEXT,
  metriken_warum  TEXT,
  ueberwachung    TEXT,
  schwellenwerte  TEXT,
  bei_stoerung    TEXT,
  betriebsmodell  TEXT CHECK (betriebsmodell IS NULL OR betriebsmodell IN ('selbst_gehostet','saas','hybrid','on_premise')),
  standort        TEXT,
  fachlich_person_id  TEXT,
  technisch_person_id TEXT,
  geprueft_am     DATE,
  geprueft_von    ki_kennung,
  aenderbar_durch TEXT,
  angelegt_am     TIMESTAMPTZ NOT NULL DEFAULT now(),
  geaendert_am    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, sub_process_id, paket_id, durchlauf_nr),
  FOREIGN KEY (company_id, sub_process_id) REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, paket_id, durchlauf_nr) REFERENCES ki_durchlauf(company_id, paket_id, durchlauf_nr) ON DELETE CASCADE,
  CONSTRAINT ck_dok_geprueft CHECK ((geprueft_am IS NULL) = (geprueft_von IS NULL))
);
COMMENT ON TABLE prozess_dokumentation IS
  'Agentenblatt (Anhang IV EU-KI-VO) je Teilprozess UND Durchlauf (v3.35). Ein neuer Durchlauf ist ein neues Blatt; '
  'nachtragen darf BC4 nur die Pruefung (geprueft_am, geprueft_von).';

CREATE TABLE prozess_dok_werkzeuge (
  company_id     UUID        NOT NULL,
  sub_process_id VARCHAR(16) NOT NULL,
  paket_id       UUID        NOT NULL,
  durchlauf_nr   INTEGER     NOT NULL,
  lfd            INTEGER     NOT NULL,
  katalog_id     TEXT        REFERENCES ref_systeme_katalog(katalog_id),
  bezeichnung    TEXT        NOT NULL CHECK (length(btrim(bezeichnung)) > 0),
  version        TEXT        NOT NULL CHECK (length(btrim(version)) > 0),
  art            TEXT        NOT NULL CHECK (art IN ('laufzeit','bibliothek','dienst','modell','entwicklung','orchestrierung')),
  anbieter       TEXT,
  quelloffen     BOOLEAN,
  lizenz         TEXT,
  hinweis        TEXT,
  PRIMARY KEY (company_id, sub_process_id, paket_id, durchlauf_nr, lfd),
  FOREIGN KEY (company_id, sub_process_id, paket_id, durchlauf_nr)
    REFERENCES prozess_dokumentation(company_id, sub_process_id, paket_id, durchlauf_nr) ON DELETE CASCADE
);

CREATE TABLE prozess_dok_agenten (
  company_id     UUID        NOT NULL,
  sub_process_id VARCHAR(16) NOT NULL,
  paket_id       UUID        NOT NULL,
  durchlauf_nr   INTEGER     NOT NULL,
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
  PRIMARY KEY (company_id, sub_process_id, paket_id, durchlauf_nr, agent_id),
  FOREIGN KEY (company_id, sub_process_id, paket_id, durchlauf_nr)
    REFERENCES prozess_dokumentation(company_id, sub_process_id, paket_id, durchlauf_nr) ON DELETE CASCADE
);

CREATE TABLE prozess_dok_tests (
  company_id     UUID        NOT NULL,
  sub_process_id VARCHAR(16) NOT NULL,
  paket_id       UUID        NOT NULL,
  durchlauf_nr   INTEGER     NOT NULL,
  lfd            INTEGER     NOT NULL,
  am             DATE        NOT NULL,
  verfahren      TEXT        NOT NULL,
  datengrundlage TEXT,
  ergebnis       TEXT        NOT NULL,
  durchgefuehrt_von ki_kennung,
  PRIMARY KEY (company_id, sub_process_id, paket_id, durchlauf_nr, lfd),
  FOREIGN KEY (company_id, sub_process_id, paket_id, durchlauf_nr)
    REFERENCES prozess_dokumentation(company_id, sub_process_id, paket_id, durchlauf_nr) ON DELETE CASCADE
);
COMMENT ON TABLE prozess_dok_tests IS
  'Kurzvermerk zum Testverfahren im Agentenblatt. Die gezaehlten Testergebnisse stehen in ki_testergebnisse.';

-- Nur die Pruefung darf am Blatt nachgetragen werden, einmal.
CREATE OR REPLACE FUNCTION trg_dok_nur_pruefung() RETURNS TRIGGER AS $fn$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF pg_trigger_depth() > 1 THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'prozess_dokumentation: Loeschen nicht erlaubt.' USING ERRCODE='check_violation';
  END IF;
  IF OLD.geprueft_am IS NOT NULL THEN
    RAISE EXCEPTION 'Blatt ist bereits geprueft (%). Neue Fassung = neuer Durchlauf.', OLD.geprueft_am
      USING ERRCODE='check_violation';
  END IF;
  IF (to_jsonb(NEW) - 'geprueft_am' - 'geprueft_von' - 'geaendert_am')
     IS DISTINCT FROM (to_jsonb(OLD) - 'geprueft_am' - 'geprueft_von' - 'geaendert_am') THEN
    RAISE EXCEPTION 'Am Agentenblatt ist nur die Pruefung nachzutragen.' USING ERRCODE='check_violation';
  END IF;
  NEW.geaendert_am := now();
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;
CREATE TRIGGER dok_nur_pruefung BEFORE UPDATE OR DELETE ON prozess_dokumentation
  FOR EACH ROW EXECUTE FUNCTION trg_dok_nur_pruefung();
CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON prozess_dok_werkzeuge FOR EACH ROW EXECUTE FUNCTION trg_ki_nur_anhaengen();
CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON prozess_dok_agenten   FOR EACH ROW EXECUTE FUNCTION trg_ki_nur_anhaengen();
CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON prozess_dok_tests     FOR EACH ROW EXECUTE FUNCTION trg_ki_nur_anhaengen();

-- ------------------------------------------------------------
-- 4. T3 Kennzahlen je UC, T3a Akzeptanzkriterien, T4 Testfälle
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ki_kennzahlen (
  company_id        UUID       NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  use_case          TEXT       NOT NULL CHECK (use_case ~ '^UC[0-9]{1,2}$'),
  kennzahl_id       TEXT       NOT NULL CHECK (kennzahl_id ~ '^K[0-9]{1,2}$'),
  bezeichnung       TEXT       NOT NULL CHECK (length(btrim(bezeichnung)) > 0),
  einheit           TEXT       NOT NULL CHECK (length(btrim(einheit)) > 0),
  richtung          TEXT       NOT NULL CHECK (richtung IN ('hoeher_besser','niedriger_besser')),
  zielwert          NUMERIC    NOT NULL,
  schwelle          NUMERIC,
  bezug_potenzial_id TEXT,
  quelle_vorher     TEXT,
  festgelegt_am     TIMESTAMPTZ NOT NULL DEFAULT now(),
  festgelegt_von    ki_kennung NOT NULL,
  PRIMARY KEY (company_id, use_case, kennzahl_id)
);
COMMENT ON TABLE ki_kennzahlen IS
  'Kennzahlen je UC, festgelegt VOR dem ersten Test (BC4). Danach gesperrt: kein Zugang, keine Aenderung.';

CREATE TABLE IF NOT EXISTS ki_akzeptanzkriterien (
  company_id     UUID        NOT NULL,
  use_case       TEXT        NOT NULL CHECK (use_case ~ '^UC[0-9]{1,2}$'),
  kriterium_id   TEXT        NOT NULL CHECK (kriterium_id ~ '^AK-[0-9]{2,3}$'),
  sub_process_id VARCHAR(16) NOT NULL,
  text           TEXT        NOT NULL CHECK (length(btrim(text)) > 0),
  quelle         TEXT        NOT NULL CHECK (length(btrim(quelle)) > 0),
  erfasst_durch  TEXT        NOT NULL DEFAULT current_user,
  erfasst_am     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, use_case, kriterium_id),
  FOREIGN KEY (company_id, sub_process_id) REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE
);
COMMENT ON TABLE ki_akzeptanzkriterien IS
  'Akzeptanzkriterien aus BC3, je UC. Schreibt BC3; bis BC3 liefert, darf BC4 sie mit Quelle (lieferung_id/Datei) uebernehmen. '
  'erfasst_durch zeigt, wer es war.';

CREATE TABLE IF NOT EXISTS ki_testfaelle (
  company_id        UUID       NOT NULL,
  use_case          TEXT       NOT NULL,
  testfall_id       TEXT       NOT NULL CHECK (testfall_id ~ '^TF-[0-9]{2,3}$'),
  sub_process_id    VARCHAR(16) NOT NULL,
  kriterium_id      TEXT,
  beschreibung      TEXT       NOT NULL CHECK (length(btrim(beschreibung)) > 0),
  eingabe_ref       TEXT       NOT NULL CHECK (length(btrim(eingabe_ref)) > 0),
  datensatz_version TEXT       NOT NULL CHECK (length(btrim(datensatz_version)) > 0),
  erwartung         TEXT       NOT NULL CHECK (length(btrim(erwartung)) > 0),
  angelegt_am       TIMESTAMPTZ NOT NULL DEFAULT now(),
  angelegt_von      ki_kennung NOT NULL,
  PRIMARY KEY (company_id, use_case, testfall_id),
  FOREIGN KEY (company_id, sub_process_id) REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, use_case, kriterium_id) REFERENCES ki_akzeptanzkriterien(company_id, use_case, kriterium_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 5. T5 Testergebnisse, T6 Messwerte, T7 Abweichungen, T8 verwendete Werkzeuge
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ki_testergebnisse (
  company_id       UUID        NOT NULL,
  paket_id         UUID        NOT NULL,
  durchlauf_nr     INTEGER     NOT NULL,
  use_case         TEXT        NOT NULL,
  testfall_id      TEXT        NOT NULL,
  wiederholung     INTEGER     NOT NULL CHECK (wiederholung BETWEEN 1 AND 20),
  prototyp_version TEXT        NOT NULL CHECK (length(btrim(prototyp_version)) > 0),
  modell           TEXT,
  prompt_fassung   TEXT,
  ergebnis         TEXT        NOT NULL CHECK (ergebnis IN ('bestanden','nicht_bestanden')),
  beobachtung      TEXT,
  herkunft         TEXT        NOT NULL CHECK (herkunft IN ('generiert','generiert_geprueft','mensch')),
  geprueft_von     ki_kennung,
  am               TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, paket_id, durchlauf_nr, testfall_id, wiederholung),
  FOREIGN KEY (company_id, paket_id, durchlauf_nr, use_case)
    REFERENCES ki_durchlauf(company_id, paket_id, durchlauf_nr, use_case) ON DELETE CASCADE,
  FOREIGN KEY (company_id, use_case, testfall_id) REFERENCES ki_testfaelle(company_id, use_case, testfall_id) ON DELETE CASCADE,
  CONSTRAINT ck_test_geprueft CHECK (herkunft = 'generiert' OR geprueft_von IS NOT NULL)
);
COMMENT ON COLUMN ki_testergebnisse.herkunft IS
  'ADR-005 R2: generiert (Maschine, ungeprueft) | generiert_geprueft (Maschine, Mensch hat geprueft) | mensch.';

CREATE TABLE IF NOT EXISTS ki_messwerte (
  company_id   UUID       NOT NULL,
  paket_id     UUID       NOT NULL,
  durchlauf_nr INTEGER    NOT NULL,
  use_case     TEXT       NOT NULL,
  kennzahl_id  TEXT       NOT NULL,
  vorher       NUMERIC,
  nachher      NUMERIC    NOT NULL,
  quelle       TEXT,
  erfasst_von  ki_kennung NOT NULL,
  am           TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, paket_id, durchlauf_nr, kennzahl_id),
  FOREIGN KEY (company_id, paket_id, durchlauf_nr, use_case)
    REFERENCES ki_durchlauf(company_id, paket_id, durchlauf_nr, use_case) ON DELETE CASCADE,
  FOREIGN KEY (company_id, use_case, kennzahl_id) REFERENCES ki_kennzahlen(company_id, use_case, kennzahl_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ki_abweichungen (
  company_id     UUID        NOT NULL,
  paket_id       UUID        NOT NULL,
  durchlauf_nr   INTEGER     NOT NULL,
  lfd            INTEGER     NOT NULL,
  sub_process_id VARCHAR(16),
  soll           TEXT        NOT NULL CHECK (length(btrim(soll)) > 0),
  ist            TEXT        NOT NULL CHECK (length(btrim(ist)) > 0),
  ursache        TEXT        NOT NULL CHECK (length(btrim(ursache)) > 0),
  massnahme      TEXT        NOT NULL CHECK (length(btrim(massnahme)) > 0),
  verantwortlich ki_kennung  NOT NULL,
  am             TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, paket_id, durchlauf_nr, lfd),
  FOREIGN KEY (company_id, paket_id, durchlauf_nr) REFERENCES ki_durchlauf(company_id, paket_id, durchlauf_nr) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ki_werkzeug_nutzung (
  company_id     UUID        NOT NULL,
  paket_id       UUID        NOT NULL,
  durchlauf_nr   INTEGER     NOT NULL,
  sub_process_id VARCHAR(16) NOT NULL,
  werkzeug       TEXT        NOT NULL CHECK (length(btrim(werkzeug)) > 0),
  katalog_id     TEXT        REFERENCES ref_systeme_katalog(katalog_id),
  version        TEXT,
  am             TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, paket_id, durchlauf_nr, sub_process_id, werkzeug),
  FOREIGN KEY (company_id, paket_id, durchlauf_nr) REFERENCES ki_durchlauf(company_id, paket_id, durchlauf_nr) ON DELETE CASCADE
);
COMMENT ON TABLE ki_werkzeug_nutzung IS
  'Tatsaechlich verwendete Werkzeuge je Durchlauf (BC4). Modelle aus ki_laufdaten zaehlen im Abgleich automatisch mit.';

-- Kennzahlen-Katalog schliesst mit dem ersten Messwert oder Testergebnis des UC.
CREATE OR REPLACE FUNCTION trg_ki_kennzahl_vor_test() RETURNS TRIGGER AS $fn$
BEGIN
  IF EXISTS (SELECT 1 FROM ki_messwerte m WHERE m.company_id=NEW.company_id AND m.use_case=NEW.use_case)
  OR EXISTS (SELECT 1 FROM ki_testergebnisse t WHERE t.company_id=NEW.company_id AND t.use_case=NEW.use_case) THEN
    RAISE EXCEPTION 'Kennzahlen fuer % sind festgelegt: Es gibt schon Tests. Kennzahlen vor dem ersten Test festlegen.', NEW.use_case
      USING ERRCODE='check_violation';
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS kennzahl_vor_test ON ki_kennzahlen;
CREATE TRIGGER kennzahl_vor_test BEFORE INSERT ON ki_kennzahlen FOR EACH ROW EXECUTE FUNCTION trg_ki_kennzahl_vor_test();

DO $t$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['ki_kennzahlen','ki_akzeptanzkriterien','ki_testfaelle','ki_testergebnisse',
                           'ki_messwerte','ki_abweichungen','ki_werkzeug_nutzung'] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS nur_anhaengen ON %I', t);
    EXECUTE format('CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION trg_ki_nur_anhaengen()', t);
  END LOOP;
END $t$;

-- ------------------------------------------------------------
-- 6. ki_laufdaten: durchlauf_nr; BC4 darf drei Felder NACHTRAGEN, nie ueberschreiben
-- ------------------------------------------------------------
ALTER TABLE ki_laufdaten ADD COLUMN IF NOT EXISTS durchlauf_nr INTEGER;
DO $f$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_ki_laufdaten_durchlauf') THEN
    ALTER TABLE ki_laufdaten ADD CONSTRAINT fk_ki_laufdaten_durchlauf
      FOREIGN KEY (company_id, paket_id, durchlauf_nr) REFERENCES ki_durchlauf(company_id, paket_id, durchlauf_nr);
  END IF;
END $f$;
CREATE OR REPLACE FUNCTION trg_ki_laufdaten_nachtragen() RETURNS TRIGGER AS $fn$
BEGIN
  IF (OLD.kosten_eur   IS NOT NULL AND NEW.kosten_eur   IS DISTINCT FROM OLD.kosten_eur)
  OR (OLD.anfrage_id   IS NOT NULL AND NEW.anfrage_id   IS DISTINCT FROM OLD.anfrage_id)
  OR (OLD.durchlauf_nr IS NOT NULL AND NEW.durchlauf_nr IS DISTINCT FROM OLD.durchlauf_nr) THEN
    RAISE EXCEPTION 'ki_laufdaten %: kosten_eur, anfrage_id und durchlauf_nr werden nur nachgetragen, nie ueberschrieben.', OLD.id
      USING ERRCODE='check_violation';
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS laufdaten_nachtragen ON ki_laufdaten;
CREATE TRIGGER laufdaten_nachtragen BEFORE UPDATE ON ki_laufdaten FOR EACH ROW EXECUTE FUNCTION trg_ki_laufdaten_nachtragen();

-- ------------------------------------------------------------
-- 7. T9 Gewichte (nur anhaengen, gueltig_ab) — D2: 40/40/20
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_erfuellung_gewichte (
  gueltig_ab DATE    NOT NULL,
  anteil     TEXT    NOT NULL CHECK (anteil IN ('A','K','W')),
  gewicht    NUMERIC NOT NULL CHECK (gewicht >= 0 AND gewicht <= 100),
  PRIMARY KEY (gueltig_ab, anteil)
);
INSERT INTO ref_erfuellung_gewichte VALUES ('2026-11-05','A',40),('2026-11-05','K',40),('2026-11-05','W',20)
  ON CONFLICT DO NOTHING;
DROP TRIGGER IF EXISTS nur_anhaengen ON ref_erfuellung_gewichte;
CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON ref_erfuellung_gewichte FOR EACH ROW EXECUTE FUNCTION trg_ki_nur_anhaengen();

-- ------------------------------------------------------------
-- 8. Sichten
-- ------------------------------------------------------------
-- 8a. Werkzeug-Abgleich: vorhanden beim Mandanten | hinterlegt im Agentenblatt | verwendet im Durchlauf
CREATE OR REPLACE VIEW v_werkzeug_abgleich AS
WITH d AS (
  SELECT k.company_id, k.paket_id, k.durchlauf_nr, i.sub_process_id
    FROM ki_durchlauf k JOIN gate_paket_inhalt i ON i.company_id=k.company_id AND i.paket_id=k.paket_id
), bestand AS (
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, d.sub_process_id,
         coalesce(ms.katalog_id, lower(btrim(ms.bezeichnung))) AS schluessel, ms.bezeichnung AS anzeige
    FROM d JOIN teilprozess_systeme ts ON ts.company_id=d.company_id AND ts.sub_process_id=d.sub_process_id
           JOIN mandant_systeme ms ON ms.company_id=ts.company_id AND ms.system_id=ts.system_id
), hinterlegt AS (
  SELECT w.company_id, w.paket_id, w.durchlauf_nr, w.sub_process_id,
         coalesce(w.katalog_id, lower(btrim(w.bezeichnung))) AS schluessel, w.bezeichnung AS anzeige
    FROM prozess_dok_werkzeuge w
  UNION
  SELECT a.company_id, a.paket_id, a.durchlauf_nr, a.sub_process_id, lower(btrim(a.modell)), a.modell
    FROM prozess_dok_agenten a WHERE a.modell IS NOT NULL AND btrim(a.modell) <> ''
), verwendet AS (
  SELECT n.company_id, n.paket_id, n.durchlauf_nr, n.sub_process_id,
         coalesce(n.katalog_id, lower(btrim(n.werkzeug))) AS schluessel, n.werkzeug AS anzeige
    FROM ki_werkzeug_nutzung n
  UNION
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, d.sub_process_id, lower(btrim(l.modell)), l.modell
    FROM d JOIN ki_laufdaten l ON l.company_id=d.company_id AND l.paket_id=d.paket_id AND l.sub_process_id=d.sub_process_id
     AND (l.durchlauf_nr = d.durchlauf_nr OR (l.durchlauf_nr IS NULL AND d.durchlauf_nr = 1))
), alle AS (
  SELECT company_id, paket_id, durchlauf_nr, sub_process_id, schluessel, min(anzeige) AS anzeige
    FROM (SELECT * FROM bestand UNION ALL SELECT * FROM hinterlegt UNION ALL SELECT * FROM verwendet) x
   GROUP BY 1,2,3,4,5
)
SELECT a.company_id, a.paket_id, a.durchlauf_nr, a.sub_process_id, a.schluessel AS werkzeug, a.anzeige,
       EXISTS (SELECT 1 FROM bestand b    WHERE (b.company_id,b.paket_id,b.durchlauf_nr,b.sub_process_id,b.schluessel)=(a.company_id,a.paket_id,a.durchlauf_nr,a.sub_process_id,a.schluessel)) AS beim_mandanten,
       EXISTS (SELECT 1 FROM hinterlegt h WHERE (h.company_id,h.paket_id,h.durchlauf_nr,h.sub_process_id,h.schluessel)=(a.company_id,a.paket_id,a.durchlauf_nr,a.sub_process_id,a.schluessel)) AS hinterlegt,
       EXISTS (SELECT 1 FROM verwendet v  WHERE (v.company_id,v.paket_id,v.durchlauf_nr,v.sub_process_id,v.schluessel)=(a.company_id,a.paket_id,a.durchlauf_nr,a.sub_process_id,a.schluessel)) AS verwendet
  FROM alle a;

CREATE OR REPLACE VIEW v_werkzeug_abgleich_befund AS
SELECT w.*,
       CASE WHEN verwendet AND hinterlegt THEN 'stimmt'
            WHEN verwendet AND NOT hinterlegt THEN 'verwendet, nicht hinterlegt'
            WHEN hinterlegt AND NOT verwendet THEN 'hinterlegt, nicht verwendet'
            ELSE 'nur beim Mandanten' END
       || CASE WHEN (verwendet OR hinterlegt) AND NOT beim_mandanten THEN ' · neu beim Mandanten' ELSE '' END AS befund
  FROM v_werkzeug_abgleich w;

-- 8b. Erfüllungsgrad je Durchlauf (deterministisch; D2 40/40/20; D3 fehlender Anteil = 0)
CREATE OR REPLACE VIEW v_erfuellungsgrad AS
WITH d AS (SELECT * FROM ki_durchlauf),
tp AS (SELECT company_id, paket_id, sub_process_id FROM gate_paket_inhalt),
kr AS (  -- Akzeptanzkriterien der Teilprozesse dieses Pakets
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, k.kriterium_id,
         EXISTS (SELECT 1 FROM ki_testfaelle f WHERE f.company_id=k.company_id AND f.use_case=k.use_case AND f.kriterium_id=k.kriterium_id)
         AND NOT EXISTS (  -- jeder zugeordnete Testfall: mindestens ein Ergebnis und alle Wiederholungen bestanden
           SELECT 1 FROM ki_testfaelle f WHERE f.company_id=k.company_id AND f.use_case=k.use_case AND f.kriterium_id=k.kriterium_id
              AND (NOT EXISTS (SELECT 1 FROM ki_testergebnisse e WHERE e.company_id=d.company_id AND e.paket_id=d.paket_id
                                AND e.durchlauf_nr=d.durchlauf_nr AND e.testfall_id=f.testfall_id)
                   OR EXISTS (SELECT 1 FROM ki_testergebnisse e WHERE e.company_id=d.company_id AND e.paket_id=d.paket_id
                                AND e.durchlauf_nr=d.durchlauf_nr AND e.testfall_id=f.testfall_id AND e.ergebnis <> 'bestanden'))
         ) AS erfuellt
    FROM d JOIN ki_akzeptanzkriterien k ON k.company_id=d.company_id AND k.use_case=d.use_case
   WHERE EXISTS (SELECT 1 FROM tp WHERE tp.company_id=d.company_id AND tp.paket_id=d.paket_id AND tp.sub_process_id=k.sub_process_id)
),
kz AS (
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, z.kennzahl_id,
         coalesce(CASE WHEN z.richtung='hoeher_besser' THEN m.nachher >= z.zielwert ELSE m.nachher <= z.zielwert END, FALSE) AS erreicht
    FROM d JOIN ki_kennzahlen z ON z.company_id=d.company_id AND z.use_case=d.use_case
    LEFT JOIN ki_messwerte m ON m.company_id=d.company_id AND m.paket_id=d.paket_id AND m.durchlauf_nr=d.durchlauf_nr AND m.kennzahl_id=z.kennzahl_id
),
wz AS (SELECT * FROM v_werkzeug_abgleich WHERE hinterlegt OR verwendet),
g AS (
  SELECT d.company_id, d.paket_id, d.durchlauf_nr,
    (SELECT gewicht FROM ref_erfuellung_gewichte x WHERE x.anteil='A' AND x.gueltig_ab <= d.angelegt_am::date ORDER BY gueltig_ab DESC LIMIT 1) AS g_a,
    (SELECT gewicht FROM ref_erfuellung_gewichte x WHERE x.anteil='K' AND x.gueltig_ab <= d.angelegt_am::date ORDER BY gueltig_ab DESC LIMIT 1) AS g_k,
    (SELECT gewicht FROM ref_erfuellung_gewichte x WHERE x.anteil='W' AND x.gueltig_ab <= d.angelegt_am::date ORDER BY gueltig_ab DESC LIMIT 1) AS g_w
  FROM d
),
z AS (
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, d.use_case, d.entscheidung,
    (SELECT count(*) FILTER (WHERE erfuellt) FROM kr WHERE (kr.company_id,kr.paket_id,kr.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)) AS a_x,
    (SELECT count(*) FROM kr WHERE (kr.company_id,kr.paket_id,kr.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)) AS a_n,
    (SELECT count(*) FILTER (WHERE erreicht) FROM kz WHERE (kz.company_id,kz.paket_id,kz.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)) AS k_x,
    (SELECT count(*) FROM kz WHERE (kz.company_id,kz.paket_id,kz.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)) AS k_n,
    (SELECT count(*) FILTER (WHERE hinterlegt AND verwendet) FROM wz WHERE (wz.company_id,wz.paket_id,wz.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)) AS w_x,
    (SELECT count(*) FROM wz WHERE (wz.company_id,wz.paket_id,wz.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)) AS w_n
  FROM d
)
SELECT z.company_id, z.paket_id, z.durchlauf_nr, z.use_case, z.entscheidung,
       z.a_x, z.a_n, z.k_x, z.k_n, z.w_x, z.w_n,
       g.g_a, g.g_k, g.g_w,
       round( coalesce(g.g_a * z.a_x::numeric / nullif(z.a_n,0), 0)
            + coalesce(g.g_k * z.k_x::numeric / nullif(z.k_n,0), 0)
            + coalesce(g.g_w * z.w_x::numeric / nullif(z.w_n,0), 0), 1) AS erfuellung_pct,
       (z.a_n = 0)::int + (z.k_n = 0)::int + (z.w_n = 0)::int AS anteile_nicht_messbar,
       concat_ws(', ',
         CASE WHEN z.a_n = 0 THEN 'A: keine Akzeptanzkriterien' END,
         CASE WHEN z.k_n = 0 THEN 'K: keine Kennzahlen' END,
         CASE WHEN z.w_n = 0 THEN 'W: keine Werkzeuge hinterlegt/verwendet' END) AS hinweis
  FROM z JOIN g ON (g.company_id,g.paket_id,g.durchlauf_nr)=(z.company_id,z.paket_id,z.durchlauf_nr);
COMMENT ON VIEW v_erfuellungsgrad IS
  'Erfuellungsgrad Anfrage -> Prototyp je Durchlauf. A = Akzeptanzkriterien, deren Testfaelle im Durchlauf in jeder '
  'Wiederholung bestanden sind; K = Kennzahlen mit erreichtem Zielwert; W = Werkzeuge hinterlegt UND verwendet / alle '
  'hinterlegten oder verwendeten. Gewichte aus ref_erfuellung_gewichte zum Anlagetag des Durchlaufs. Fehlender Anteil = 0.';

-- 8c. Stand je Durchlauf (Prozessdokumentation)
CREATE OR REPLACE VIEW v_durchlauf_stand AS
SELECT k.company_id, k.paket_id, k.durchlauf_nr, k.use_case, k.anlass, k.angelegt_am,
       k.entscheidung, k.entschieden_am,
       (SELECT count(*) FROM gate_paket_inhalt i WHERE i.company_id=k.company_id AND i.paket_id=k.paket_id) AS teilprozesse,
       (SELECT count(*) FROM prozess_dokumentation p WHERE (p.company_id,p.paket_id,p.durchlauf_nr)=(k.company_id,k.paket_id,k.durchlauf_nr)) AS agentenblaetter,
       (SELECT count(*) FROM prozess_dokumentation p WHERE (p.company_id,p.paket_id,p.durchlauf_nr)=(k.company_id,k.paket_id,k.durchlauf_nr) AND p.geprueft_am IS NOT NULL) AS blaetter_geprueft,
       (SELECT count(*) FROM ki_testergebnisse e WHERE (e.company_id,e.paket_id,e.durchlauf_nr)=(k.company_id,k.paket_id,k.durchlauf_nr)) AS testergebnisse,
       (SELECT count(*) FROM ki_testergebnisse e WHERE (e.company_id,e.paket_id,e.durchlauf_nr)=(k.company_id,k.paket_id,k.durchlauf_nr) AND e.ergebnis='bestanden') AS bestanden,
       (SELECT count(*) FROM ki_messwerte m WHERE (m.company_id,m.paket_id,m.durchlauf_nr)=(k.company_id,k.paket_id,k.durchlauf_nr)) AS messwerte,
       (SELECT count(*) FROM ki_abweichungen a WHERE (a.company_id,a.paket_id,a.durchlauf_nr)=(k.company_id,k.paket_id,k.durchlauf_nr)) AS abweichungen,
       (SELECT count(*) FROM ki_werkzeug_nutzung n WHERE (n.company_id,n.paket_id,n.durchlauf_nr)=(k.company_id,k.paket_id,k.durchlauf_nr)) AS werkzeuge_verwendet,
       (SELECT count(*) FROM ki_laufdaten l WHERE l.company_id=k.company_id AND l.paket_id=k.paket_id
           AND (l.durchlauf_nr=k.durchlauf_nr OR (l.durchlauf_nr IS NULL AND k.durchlauf_nr=1))) AS laufdaten
  FROM ki_durchlauf k;

-- 8d. Rückschreiben je BC: gefordert / vorhanden / fehlt (KI-Reifegrad -> Datenstruktur)
--     erfuellt NULL = nur zur Information. x von n; n = 0 heisst "nichts vorhanden".
CREATE OR REPLACE VIEW v_rueckschreiben_je_bc AS
WITH d AS (SELECT company_id, paket_id, durchlauf_nr, use_case FROM ki_durchlauf),
tp AS (SELECT d.*, i.sub_process_id, i.anfrage_id FROM d JOIN gate_paket_inhalt i ON i.company_id=d.company_id AND i.paket_id=d.paket_id),
lf AS (SELECT d.company_id, d.paket_id, d.durchlauf_nr, l.id, l.kosten_eur, l.anfrage_id, l.durchlauf_nr AS lauf_durchlauf_nr FROM d JOIN ki_laufdaten l
         ON l.company_id=d.company_id AND l.paket_id=d.paket_id AND (l.durchlauf_nr=d.durchlauf_nr OR (l.durchlauf_nr IS NULL AND d.durchlauf_nr=1))),
b2 AS (SELECT d.company_id, d.paket_id, d.durchlauf_nr, l.priorisierung_id FROM d
         JOIN bc2.lauf l ON l.company_id = d.company_id::text AND l.paket_id = d.paket_id::text AND l.fassung = d.durchlauf_nr),
b3 AS (SELECT d.company_id, d.paket_id, d.durchlauf_nr, x.lieferung_id, x.sub_process_id, x.gate2_von, x.gate2_begruendung, x.anfrage_id FROM d
         JOIN bc3.lieferungen x ON x.company_id = d.company_id AND x.paket_id = d.paket_id),
r AS (
  -- BC0
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC0'::text AS bc, 1 AS nr, 'Freigabe je Teilprozess mit Anfrage'::text AS pruefpunkt,
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND tp.anfrage_id IS NOT NULL) AS x,
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)) AS n, NULL::boolean AS info
    FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC0', 2, 'Systeme je Teilprozess beim Mandanten erfasst (Werkzeug-Abgleich)',
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND EXISTS (SELECT 1 FROM teilprozess_systeme s WHERE s.company_id=tp.company_id AND s.sub_process_id=tp.sub_process_id)),
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL
    FROM d
  UNION ALL
  SELECT k.company_id, k.paket_id, k.durchlauf_nr, 'BC0', 3, 'Durchlauf entschieden (weiter/nachbessern/verwerfen)',
         (k.entscheidung IS NOT NULL)::int, 1, NULL FROM ki_durchlauf k
  -- BC1
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC1', 1, 'Profil fertig je Teilprozess',
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND EXISTS (SELECT 1 FROM bc1.prozessprofil p WHERE p.company_id=tp.company_id AND p.focus_step_id=tp.sub_process_id AND p.status='fertig')),
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL
    FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC1', 2, 'Profil traegt die Anfrage (anfrage_id)',
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND EXISTS (SELECT 1 FROM bc1.prozessprofil p WHERE p.company_id=tp.company_id AND p.focus_step_id=tp.sub_process_id
                          AND p.status='fertig' AND p.anfrage_id = tp.anfrage_id)),
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL
    FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC1', 3, 'Gespraech der Anfrage zugeordnet (Session)',
         (SELECT count(DISTINCT tp.anfrage_id) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND EXISTS (SELECT 1 FROM bc1_gespraeche g WHERE g.company_id=tp.company_id AND g.anfrage_id=tp.anfrage_id)),
         (SELECT count(DISTINCT tp.anfrage_id) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL
    FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC1', 4, 'Vorher-Werte als Zahl im Profil (Dauer, Haeufigkeit)',
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND EXISTS (SELECT 1 FROM bc1.prozessprofil p WHERE p.company_id=tp.company_id AND p.focus_step_id=tp.sub_process_id
                          AND p.status='fertig' AND p.focus_step_duration_minutes IS NOT NULL AND coalesce(p.step_frequency_per_year, p.frequency_per_year) IS NOT NULL)),
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL
    FROM d
  -- BC2
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC2', 1, 'Lauf zum Durchlauf (fassung = durchlauf_nr)',
         (SELECT count(*) FROM b2 WHERE (b2.company_id,b2.paket_id,b2.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), 1, NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC2', 2, 'Gate 1: Entscheider als Kennung',
         (SELECT count(*) FROM b2 JOIN bc2.gate1 g ON g.priorisierung_id=b2.priorisierung_id
           WHERE (b2.company_id,b2.paket_id,b2.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND ist_kennung(g.entscheider)), 1, NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC2', 3, 'Gate 1: Kommentar/Begruendung',
         (SELECT count(*) FROM b2 JOIN bc2.gate1 g ON g.priorisierung_id=b2.priorisierung_id
           WHERE (b2.company_id,b2.paket_id,b2.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND length(btrim(coalesce(g.kommentar,''))) > 0), 1, NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC2', 4, 'Gate 1: Begruendung und finaler Rang je Potenzial',
         (SELECT count(*) FROM b2 JOIN bc2.gate1_potenzial g ON g.priorisierung_id=b2.priorisierung_id
           WHERE (b2.company_id,b2.paket_id,b2.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND length(btrim(coalesce(g.begruendung,''))) > 0 AND g.finaler_rang IS NOT NULL),
         (SELECT count(*) FROM b2 JOIN bc2.gate1_potenzial g ON g.priorisierung_id=b2.priorisierung_id
           WHERE (b2.company_id,b2.paket_id,b2.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC2', 5, 'Messbare Vorgabe je Potenzial (Kennzahl verweist darauf)',
         (SELECT count(*) FROM b2 JOIN bc2.potenzial p ON p.priorisierung_id=b2.priorisierung_id
           WHERE (b2.company_id,b2.paket_id,b2.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND EXISTS (SELECT 1 FROM ki_kennzahlen z WHERE z.company_id=d.company_id AND z.use_case=d.use_case AND z.bezug_potenzial_id=p.potenzial_id)),
         (SELECT count(*) FROM b2 JOIN bc2.potenzial p ON p.priorisierung_id=b2.priorisierung_id
           WHERE (b2.company_id,b2.paket_id,b2.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  -- BC3
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC3', 1, 'Lieferung je Teilprozess',
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND EXISTS (SELECT 1 FROM b3 WHERE (b3.company_id,b3.paket_id,b3.durchlauf_nr)=(tp.company_id,tp.paket_id,tp.durchlauf_nr) AND b3.sub_process_id=tp.sub_process_id)),
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC3', 2, 'Gate 2: Begruendung',
         (SELECT count(*) FROM b3 WHERE (b3.company_id,b3.paket_id,b3.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND length(btrim(coalesce(b3.gate2_begruendung,''))) > 0),
         (SELECT count(*) FROM b3 WHERE (b3.company_id,b3.paket_id,b3.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC3', 3, 'Gate 2: Entscheider als Kennung',
         (SELECT count(*) FROM b3 WHERE (b3.company_id,b3.paket_id,b3.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND ist_kennung(b3.gate2_von)),
         (SELECT count(*) FROM b3 WHERE (b3.company_id,b3.paket_id,b3.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC3', 4, 'anfrage_id mitgefuehrt',
         (SELECT count(*) FROM b3 WHERE (b3.company_id,b3.paket_id,b3.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND b3.anfrage_id IS NOT NULL),
         (SELECT count(*) FROM b3 WHERE (b3.company_id,b3.paket_id,b3.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC3', 5, 'Akzeptanzkriterien in der DB je Teilprozess',
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
             AND EXISTS (SELECT 1 FROM ki_akzeptanzkriterien k WHERE k.company_id=tp.company_id AND k.use_case=tp.use_case AND k.sub_process_id=tp.sub_process_id)),
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  -- BC4 Generator
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 1, 'Laufdaten mit kosten_eur',
         (SELECT count(*) FROM lf WHERE (lf.company_id,lf.paket_id,lf.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND lf.kosten_eur IS NOT NULL),
         (SELECT count(*) FROM lf WHERE (lf.company_id,lf.paket_id,lf.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 2, 'Laufdaten mit anfrage_id',
         (SELECT count(*) FROM lf WHERE (lf.company_id,lf.paket_id,lf.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND lf.anfrage_id IS NOT NULL),
         (SELECT count(*) FROM lf WHERE (lf.company_id,lf.paket_id,lf.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 3, 'Laufdaten mit durchlauf_nr',
         (SELECT count(*) FROM lf WHERE (lf.company_id,lf.paket_id,lf.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND lf.lauf_durchlauf_nr IS NOT NULL),
         (SELECT count(*) FROM lf WHERE (lf.company_id,lf.paket_id,lf.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 4, 'Agentenblatt je Teilprozess',
         (SELECT count(DISTINCT p.sub_process_id) FROM prozess_dokumentation p WHERE (p.company_id,p.paket_id,p.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)),
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  -- BC4 Test
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 5, 'Agentenblatt geprueft (geprueft_von)',
         (SELECT count(*) FROM prozess_dokumentation p WHERE (p.company_id,p.paket_id,p.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND p.geprueft_am IS NOT NULL),
         (SELECT count(*) FROM tp WHERE (tp.company_id,tp.paket_id,tp.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 6, 'Kennzahlen des UC festgelegt',
         least((SELECT count(*) FROM ki_kennzahlen z WHERE z.company_id=d.company_id AND z.use_case=d.use_case), 1), 1, NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 7, 'Testfall je Akzeptanzkriterium',
         (SELECT count(*) FROM ki_akzeptanzkriterien k WHERE k.company_id=d.company_id AND k.use_case=d.use_case
             AND EXISTS (SELECT 1 FROM ki_testfaelle f WHERE f.company_id=k.company_id AND f.use_case=k.use_case AND f.kriterium_id=k.kriterium_id)),
         (SELECT count(*) FROM ki_akzeptanzkriterien k WHERE k.company_id=d.company_id AND k.use_case=d.use_case), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 8, 'Testfaelle im Durchlauf getestet und wiederholt (>= 2)',
         (SELECT count(*) FROM (SELECT testfall_id FROM ki_testergebnisse e WHERE (e.company_id,e.paket_id,e.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)
                                GROUP BY testfall_id HAVING count(*) >= 2) w),
         (SELECT count(*) FROM ki_testfaelle f WHERE f.company_id=d.company_id AND f.use_case=d.use_case), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 9, 'Messwert je Kennzahl (vorher/nachher)',
         (SELECT count(*) FROM ki_messwerte m WHERE (m.company_id,m.paket_id,m.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND m.vorher IS NOT NULL),
         (SELECT count(*) FROM ki_kennzahlen z WHERE z.company_id=d.company_id AND z.use_case=d.use_case), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 10, 'Testergebnisse von einem Menschen geprueft',
         (SELECT count(*) FROM ki_testergebnisse e WHERE (e.company_id,e.paket_id,e.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr) AND e.herkunft <> 'generiert'),
         (SELECT count(*) FROM ki_testergebnisse e WHERE (e.company_id,e.paket_id,e.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 11, 'Verwendete Werkzeuge erfasst',
         least((SELECT count(*) FROM ki_werkzeug_nutzung n WHERE (n.company_id,n.paket_id,n.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), 1), 1, NULL FROM d
  UNION ALL
  SELECT d.company_id, d.paket_id, d.durchlauf_nr, 'BC4', 12, 'Abweichungen erfasst (Anzahl, zur Information)',
         (SELECT count(*) FROM ki_abweichungen a WHERE (a.company_id,a.paket_id,a.durchlauf_nr)=(d.company_id,d.paket_id,d.durchlauf_nr)), 0, TRUE FROM d
)
SELECT company_id, paket_id, durchlauf_nr, bc, nr, pruefpunkt, x AS vorhanden, n AS gefordert,
       CASE WHEN info THEN NULL WHEN n = 0 THEN FALSE ELSE x >= n END AS erfuellt
  FROM r;
COMMENT ON VIEW v_rueckschreiben_je_bc IS
  'KI-Reifegrad -> Datenstruktur: je Durchlauf und BC, was gefordert ist und was in der DB steht. '
  'erfuellt = alle n vorhanden; n = 0 zaehlt als nicht erfuellt (nichts da, woran man pruefen koennte).';

-- Agentenblatt-Stand (Nachfolger der Sicht aus v3.32, jetzt je Durchlauf)
CREATE OR REPLACE VIEW v_prozess_dokumentation_stand AS
SELECT d.company_id, d.sub_process_id, left(d.sub_process_id, 5) AS process_id, d.paket_id, d.durchlauf_nr,
       d.bezeichnung, d.version, d.in_betrieb_seit,
       (SELECT count(*) FROM prozess_dok_werkzeuge w WHERE (w.company_id,w.sub_process_id,w.paket_id,w.durchlauf_nr)=(d.company_id,d.sub_process_id,d.paket_id,d.durchlauf_nr)) AS werkzeuge,
       (SELECT count(*) FROM prozess_dok_agenten a   WHERE (a.company_id,a.sub_process_id,a.paket_id,a.durchlauf_nr)=(d.company_id,d.sub_process_id,d.paket_id,d.durchlauf_nr)) AS agenten,
       (SELECT count(*) FROM prozess_dok_tests t     WHERE (t.company_id,t.sub_process_id,t.paket_id,t.durchlauf_nr)=(d.company_id,d.sub_process_id,d.paket_id,d.durchlauf_nr)) AS tests,
       d.geprueft_am,
       (d.aenderbar_durch IS NULL OR btrim(d.aenderbar_durch) = '') AS niemand_kann_aendern
  FROM prozess_dokumentation d;

-- ------------------------------------------------------------
-- 9. Rechte
-- ------------------------------------------------------------
DO $r$ DECLARE t text;
  alle text[] := ARRAY['ki_durchlauf','prozess_dokumentation','prozess_dok_werkzeuge','prozess_dok_agenten','prozess_dok_tests',
                       'ki_kennzahlen','ki_akzeptanzkriterien','ki_testfaelle','ki_testergebnisse','ki_messwerte',
                       'ki_abweichungen','ki_werkzeug_nutzung','ref_erfuellung_gewichte',
                       'v_werkzeug_abgleich','v_werkzeug_abgleich_befund','v_erfuellungsgrad','v_durchlauf_stand',
                       'v_rueckschreiben_je_bc','v_prozess_dokumentation_stand'];
BEGIN
  FOREACH t IN ARRAY alle LOOP
    EXECUTE format('REVOKE ALL ON %I FROM PUBLIC', t);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN EXECUTE format('REVOKE ALL ON %I FROM anon, authenticated', t); END IF;
  END LOOP;
END $r$;
DO $r2$ DECLARE t text; ro text;
  alle text[] := ARRAY['ki_durchlauf','prozess_dokumentation','prozess_dok_werkzeuge','prozess_dok_agenten','prozess_dok_tests',
                       'ki_kennzahlen','ki_akzeptanzkriterien','ki_testfaelle','ki_testergebnisse','ki_messwerte',
                       'ki_abweichungen','ki_werkzeug_nutzung','ref_erfuellung_gewichte',
                       'v_werkzeug_abgleich','v_werkzeug_abgleich_befund','v_erfuellungsgrad','v_durchlauf_stand',
                       'v_rueckschreiben_je_bc','v_prozess_dokumentation_stand'];
  bc4_ins text[] := ARRAY['prozess_dokumentation','prozess_dok_werkzeuge','prozess_dok_agenten','prozess_dok_tests',
                          'ki_kennzahlen','ki_akzeptanzkriterien','ki_testfaelle','ki_testergebnisse','ki_messwerte',
                          'ki_abweichungen','ki_werkzeug_nutzung'];
BEGIN
  FOREACH ro IN ARRAY ARRAY['bc_leser','bc2_role','bc3_role','bc4_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=ro) THEN
      FOREACH t IN ARRAY alle LOOP EXECUTE format('GRANT SELECT ON %I TO %I', t, ro); END LOOP;
    END IF;
  END LOOP;
  FOREACH t IN ARRAY bc4_ins LOOP EXECUTE format('GRANT INSERT ON %I TO bc4_role', t); END LOOP;
  EXECUTE 'GRANT UPDATE (geprueft_am, geprueft_von, geaendert_am) ON prozess_dokumentation TO bc4_role';
  EXECUTE 'GRANT UPDATE (kosten_eur, anfrage_id, durchlauf_nr) ON ki_laufdaten TO bc4_role';
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='bc3_role') THEN
    EXECUTE 'GRANT INSERT ON ki_akzeptanzkriterien TO bc3_role';
  END IF;
  EXECUTE 'GRANT USAGE ON TYPE ki_kennung TO bc4_role';
  EXECUTE 'GRANT EXECUTE ON FUNCTION ist_kennung(text) TO bc4_role';
END $r2$;

-- ------------------------------------------------------------
-- 10. Durchlauf 1 fuer den UC1-Lauf vom 03.11.2026 (NoroAI), damit BC4 schreiben kann
-- ------------------------------------------------------------
INSERT INTO ki_durchlauf (company_id, paket_id, durchlauf_nr, use_case, anlass, angelegt_von)
SELECT company_id, paket_id, 1, 'UC1', 'Erster Durchlauf UC1 Reisebuchung (Lauf vom 03.11.2026, Vorfuehrung)', '958515eb-a8a6-4b02-a2ac-d4794ad11113'
  FROM gate_pakete
 WHERE company_id = '7c2d5ee9-2a9a-5990-810f-502ea2b2012d' AND paket_id = 'cc7f4d1b-4c71-4cfa-92c3-46a395080e4b'
   AND NOT EXISTS (SELECT 1 FROM ki_durchlauf k WHERE k.company_id = gate_pakete.company_id AND k.paket_id = gate_pakete.paket_id);

-- ------------------------------------------------------------
-- 11. Proben
-- ------------------------------------------------------------
\echo '--- 1. Objekte da (ERWARTET: 19 Zeilen, alle t)'
SELECT x AS objekt, to_regclass('public.'||x) IS NOT NULL AS da
  FROM unnest(ARRAY['ki_durchlauf','prozess_dokumentation','prozess_dok_werkzeuge','prozess_dok_agenten','prozess_dok_tests',
                    'ki_kennzahlen','ki_akzeptanzkriterien','ki_testfaelle','ki_testergebnisse','ki_messwerte',
                    'ki_abweichungen','ki_werkzeug_nutzung','ref_erfuellung_gewichte',
                    'v_werkzeug_abgleich','v_werkzeug_abgleich_befund','v_erfuellungsgrad','v_durchlauf_stand',
                    'v_rueckschreiben_je_bc','v_prozess_dokumentation_stand']) x;
\echo '--- 2. Rechte bc4_role auf ki_testergebnisse (ERWARTET: t | t | f | f)'
SELECT has_table_privilege('bc4_role','ki_testergebnisse','SELECT') AS sel,
       has_table_privilege('bc4_role','ki_testergebnisse','INSERT') AS ins,
       has_table_privilege('bc4_role','ki_testergebnisse','UPDATE') AS upd,
       has_table_privilege('bc4_role','ki_testergebnisse','DELETE') AS del;
\echo '--- 3. bc4_role darf Pruefung am Blatt und drei Felder der Laufdaten nachtragen (ERWARTET: t | t | f)'
SELECT has_column_privilege('bc4_role','prozess_dokumentation','geprueft_von','UPDATE') AS blatt_pruefung,
       has_column_privilege('bc4_role','ki_laufdaten','kosten_eur','UPDATE') AS kosten,
       has_column_privilege('bc4_role','ki_laufdaten','modell','UPDATE') AS modell;
\echo '--- 4. Durchlauf 1 NoroAI (ERWARTET: 1 Zeile, UC1)'
SELECT paket_id, durchlauf_nr, use_case, entscheidung FROM ki_durchlauf;
\echo '--- 5. Gewichte (ERWARTET: A 40, K 40, W 20)'
SELECT anteil, gewicht FROM ref_erfuellung_gewichte ORDER BY anteil;
\echo '--- 6. Erfuellungsgrad heute (ERWARTET: 0.0; A und K nicht messbar; W 0 von 1, weil das Modell aus den Laufdaten verwendet, aber nicht hinterlegt ist)'
SELECT durchlauf_nr, erfuellung_pct, anteile_nicht_messbar, hinweis FROM v_erfuellungsgrad;
\echo '--- 7. Rueckschreiben je BC heute'
SELECT bc, nr, pruefpunkt, vorhanden, gefordert, erfuellt FROM v_rueckschreiben_je_bc ORDER BY bc, nr;

COMMIT;
