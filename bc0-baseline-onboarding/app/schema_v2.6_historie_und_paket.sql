-- ============================================================
-- BC0 · Schema v2.6 — Historie (R9), Paket, Einfrieren
-- Stand: 03.09.2026 · Simeon Ehmer · zum Einspielen am 04.09.2026
-- Grundlage: BC0_DB_Ablaufanalyse_03-09-2026.md, Abschnitt 11 · Issue #148 (R9)
-- VORAUSSETZUNG: schema_v1.1.1 … schema_v2.5 in dieser Reihenfolge.
-- ============================================================
--
-- LEITSATZ (Simeon, 03.09.2026)
--   Nicht den Prozess sperren. Nicht ein Foto der Werte ins Paket legen.
--   Sondern: JEDE Aenderung mit Zeitstempel festhalten (R9), dann sagt das
--   Datum am Paket alles — BC2 liest aus dem Paket, WAS er bekommen hat,
--   und aus der Historie, WIE es zu diesem Zeitpunkt aussah. Was er darueber
--   hinaus liest (Systeme, Rollen, Kette, Portfolio), entscheidet er selbst.
--
-- WAS DIESES SKRIPT TUT
--   R9  audit_log wird zur Aenderungshistorie mit ZEILENBILDERN: ein
--       generischer Trigger auf allen Fachtabellen in public, alt/neu als
--       JSON, Benutzer aus der Sitzungsvariable bc0.benutzer, Klarnamen
--       ausgenommen. Beim Einspielen eine Bestandsaufnahme jeder Zeile —
--       ab diesem Moment ist die Historie vollstaendig.
--   ZR  stand_zum(tabelle, datum[, mandant]) — die Zeitreise: jede Zeile,
--       wie sie zu diesem Zeitpunkt war.
--   A   Erhebung: `abgeschlossen` wird eine echte Sperre, kein Wiederoeffnen.
--   B   Paket: Datum + Liste der uebergebenen Teilprozesse, append-only.
--       Kein kopierter Stand — den liefert die Historie.
--   D   v_stand_veraltet: was sich seit Freigabe/Uebergabe geaendert hat,
--       gezaehlt aus der Historie.
--   F   Loeschen: stilllegen statt loeschen, Kaskade (DSGVO) laeuft durch.
--
-- WAS ES NICHT TUT
--   Keine Bestandsdaten geaendert, keine Primaerschluessel, kein Rechteentzug.
--   Wiederholbar. Die Anwendung zieht an vier Stellen nach (Ausrollblatt).
--
-- EINSPIELEN (nach dem Backup):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema_v2.6_historie_und_paket.sql
-- ============================================================

BEGIN;

-- ============================================================
-- R9. DIE HISTORIE — audit_log bekommt Zeilenbilder
-- ============================================================
-- audit_log steht seit v1.1 (audit_id, company_id, entity, entity_id, action,
-- actor, payload, at) und war leer. Es bleibt die eine Tabelle; drei Spalten
-- kommen dazu. payload traegt kuenftig dasselbe wie neu — wer die alte
-- Spalte liest, bekommt weiter etwas.

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS pk   JSONB;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS alt  JSONB;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS neu  JSONB;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS txid BIGINT;

COMMENT ON TABLE audit_log IS
  'Aenderungshistorie (R9, #148): je INSERT/UPDATE/DELETE auf einer Fachtabelle '
  'eine Zeile mit dem ganzen alten und neuen Zeilenbild. Append-only. Beginnt '
  'mit einer Bestandsaufnahme (action = bestand) beim Einspielen von v2.6 — '
  'davor ist nichts rekonstruierbar, und stand_zum() sagt das auch.';
COMMENT ON COLUMN audit_log.actor IS
  'Wer: die Sitzungsvariable bc0.benutzer (setzt die Anwendung je Verbindung), '
  'sonst der Datenbankbenutzer. psql ohne Variable erscheint als postgres — '
  'ADR-005 R3: ein Eingriff von Hand traegt keine Herkunft, aber er ist sichtbar.';
COMMENT ON COLUMN audit_log.pk IS
  'Primaerschluessel der Zeile als JSON. Ueber ihn findet stand_zum() je Zeile '
  'den letzten Eintrag vor einem Datum.';

CREATE INDEX IF NOT EXISTS idx_audit_entity_pk_at ON audit_log(entity, pk, at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_company_at   ON audit_log(company_id, at DESC);

-- Welche Tabellen NICHT protokolliert werden, und warum.
--   app_benutzer         Passwort-Hashes
--   app_sitzungen        Sitzungsschluessel
--   app_anmeldeversuche  Abdruecke von E-Mail und IP
--   audit_log            sich selbst
CREATE OR REPLACE FUNCTION historie_ausgenommen(p_tabelle TEXT) RETURNS BOOLEAN AS $fn$
  SELECT p_tabelle IN ('app_benutzer','app_sitzungen','app_anmeldeversuche','audit_log');
$fn$ LANGUAGE sql IMMUTABLE;

-- Welche Spalten aus dem Zeilenbild entfernt werden: die Klarnamen.
-- ADR-004 R5 — der Name steht an genau einer Stelle, und die Historie ist
-- keine zweite. Eine geloeschte Person bleibt geloescht, auch hier.
CREATE OR REPLACE FUNCTION historie_pii_entfernen(p_tabelle TEXT, p_zeile JSONB) RETURNS JSONB AS $fn$
  SELECT CASE WHEN p_tabelle = 'ref_personen'
              THEN p_zeile - ARRAY['name','email','telefon']
              ELSE p_zeile END;
$fn$ LANGUAGE sql IMMUTABLE;

-- Der eine Trigger fuer alle Tabellen.
CREATE OR REPLACE FUNCTION trg_historie() RETURNS TRIGGER AS $fn$
DECLARE
  j_alt JSONB; j_neu JSONB; j_pk JSONB; v_company UUID; v_actor TEXT;
BEGIN
  IF TG_OP IN ('UPDATE','DELETE') THEN j_alt := to_jsonb(OLD); END IF;
  IF TG_OP IN ('INSERT','UPDATE') THEN j_neu := to_jsonb(NEW); END IF;

  -- Primaerschluessel aus dem Katalog, nicht aus einer Liste: gilt fuer jede
  -- Tabelle, auch fuer kuenftige.
  SELECT jsonb_object_agg(a.attname, coalesce(j_neu, j_alt) -> a.attname)
    INTO j_pk
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
   WHERE i.indrelid = TG_RELID AND i.indisprimary;

  v_company := (coalesce(j_neu, j_alt) ->> 'company_id')::uuid;
  v_actor   := coalesce(nullif(current_setting('bc0.benutzer', true), ''), current_user);

  j_alt := historie_pii_entfernen(TG_TABLE_NAME, j_alt);
  j_neu := historie_pii_entfernen(TG_TABLE_NAME, j_neu);

  INSERT INTO audit_log (company_id, entity, entity_id, action, actor, payload, at, pk, alt, neu, txid)
  VALUES (v_company, TG_TABLE_NAME, j_pk::text, TG_OP, v_actor, j_neu, now(), j_pk, j_alt, j_neu,
          txid_current());

  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

-- An alle Fachtabellen in public haengen — dynamisch, damit nichts fehlt.
-- Bestehende Trigger gleichen Namens werden ersetzt (wiederholbar).
DO $$
DECLARE r RECORD; n INTEGER := 0;
BEGIN
  FOR r IN SELECT c.relname
             FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
            WHERE ns.nspname = 'public' AND c.relkind = 'r'
              AND NOT historie_ausgenommen(c.relname)
            ORDER BY 1
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS historie ON %I', r.relname);
    EXECUTE format('CREATE TRIGGER historie AFTER INSERT OR UPDATE OR DELETE ON %I '
                   'FOR EACH ROW EXECUTE FUNCTION trg_historie()', r.relname);
    n := n + 1;
  END LOOP;
  RAISE NOTICE 'Historie-Trigger gesetzt auf % Tabellen.', n;
END $$;

-- Bestandsaufnahme: jede vorhandene Zeile einmal als 'bestand'. Nur beim
-- ersten Einspielen — ein zweiter Lauf erkennt die vorhandene Aufnahme.
DO $$
DECLARE r RECORD; n BIGINT; gesamt BIGINT := 0;
BEGIN
  IF EXISTS (SELECT 1 FROM audit_log WHERE action = 'bestand') THEN
    RAISE NOTICE 'Bestandsaufnahme vorhanden — uebersprungen.';
    RETURN;
  END IF;
  FOR r IN SELECT c.relname
             FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
            WHERE ns.nspname = 'public' AND c.relkind = 'r'
              AND NOT historie_ausgenommen(c.relname)
            ORDER BY 1
  LOOP
    EXECUTE format(
      'INSERT INTO audit_log (company_id, entity, entity_id, action, actor, payload, at, pk, alt, neu, txid) '
      'SELECT (j ->> ''company_id'')::uuid, %L, pk::text, ''bestand'', ''schema_v2.6'', j, now(), pk, NULL, j, txid_current() '
      '  FROM (SELECT historie_pii_entfernen(%L, to_jsonb(t)) AS j, '
      '               (SELECT jsonb_object_agg(a.attname, to_jsonb(t) -> a.attname) '
      '                  FROM pg_index i JOIN pg_attribute a '
      '                    ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey) '
      '                 WHERE i.indrelid = %L::regclass AND i.indisprimary) AS pk '
      '          FROM %I t) q', r.relname, r.relname, r.relname, r.relname);
    GET DIAGNOSTICS n = ROW_COUNT;
    gesamt := gesamt + n;
  END LOOP;
  RAISE NOTICE 'Bestandsaufnahme: % Zeilen.', gesamt;
END $$;

-- ============================================================
-- ZR. DIE ZEITREISE
-- ============================================================
-- Je Zeile der letzte Eintrag vor dem Datum; geloeschte Zeilen fehlen.
-- Vor Beginn der Historie gibt es keine Antwort — und keine geratene.

CREATE OR REPLACE FUNCTION historie_beginn() RETURNS TIMESTAMPTZ AS $fn$
  SELECT min(at) FROM audit_log WHERE action = 'bestand';
$fn$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION stand_zum(p_tabelle TEXT, p_datum TIMESTAMPTZ, p_company UUID DEFAULT NULL)
RETURNS SETOF JSONB AS $fn$
BEGIN
  IF historie_ausgenommen(p_tabelle) THEN
    RAISE EXCEPTION 'Fuer % gibt es keine Historie.', p_tabelle USING ERRCODE = 'check_violation';
  END IF;
  IF p_datum < historie_beginn() THEN
    RAISE EXCEPTION 'Die Historie beginnt am %. Ein Stand vom % ist nicht rekonstruierbar.',
      historie_beginn(), p_datum USING ERRCODE = 'check_violation';
  END IF;
  RETURN QUERY
    SELECT t.neu
      FROM (SELECT DISTINCT ON (h.pk) h.pk, h.action, h.neu
              FROM audit_log h
             WHERE h.entity = p_tabelle
               AND h.at <= p_datum
               AND (p_company IS NULL OR h.company_id = p_company)
             ORDER BY h.pk, h.at DESC, h.audit_id DESC) t
     WHERE t.action <> 'DELETE';
END;
$fn$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION stand_zum(TEXT, TIMESTAMPTZ, UUID) IS
  'Die Zeitreise: alle Zeilen einer Tabelle, wie sie zum Zeitpunkt p_datum '
  'waren, als JSON. Beispiel fuer BC2: '
  'SELECT * FROM stand_zum(''bitkom_bewertungen'', p.uebergeben_am, p.company_id) '
  'mit p aus v_uebergabe_offen. Klarnamen sind nie enthalten.';

-- Die Regel von v_bewertung_aktuell, auf einen Zeitpunkt angewandt: je
-- Teilprozess und Item die juengste nicht verworfene Erhebung, wie sie zu
-- p_datum bestand. Das ist, was BC2 aus dem Paket heraus liest — und was die
-- Anwendung unter "Stand vom …" anzeigt.
CREATE OR REPLACE FUNCTION bewertung_aktuell_zum(p_company UUID, p_datum TIMESTAMPTZ)
RETURNS TABLE (sub_process_id TEXT, item_nr INTEGER, erhebung_id TEXT, stufe INTEGER,
               quelle TEXT, bewertet_am TIMESTAMPTZ) AS $fn$
  SELECT t.sub_process_id, t.item_nr, t.erhebung_id, t.stufe, t.quelle, t.bewertet_am
    FROM (SELECT b ->> 'sub_process_id' AS sub_process_id, (b ->> 'item_nr')::int AS item_nr,
                 b ->> 'erhebung_id' AS erhebung_id, (b ->> 'stufe')::int AS stufe,
                 b ->> 'quelle' AS quelle, (b ->> 'bewertet_am')::timestamptz AS bewertet_am,
                 row_number() OVER (PARTITION BY b ->> 'sub_process_id', (b ->> 'item_nr')::int
                                    ORDER BY (e ->> 'stand')::date DESC, e ->> 'erhebung_id' DESC) AS rang
            FROM stand_zum('bitkom_bewertungen', p_datum, p_company) b
            JOIN stand_zum('ref_erhebungen', p_datum, p_company) e
              ON e ->> 'erhebung_id' = b ->> 'erhebung_id'
           WHERE e ->> 'status' <> 'verworfen') t
   WHERE t.rang = 1;
$fn$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION reifegrad_tp_zum(p_company UUID, p_datum TIMESTAMPTZ)
RETURNS TABLE (sub_process_id TEXT, avg_stufe NUMERIC, n_items BIGINT) AS $fn$
  SELECT b.sub_process_id, round(avg(b.stufe), 2), count(*)
    FROM bewertung_aktuell_zum(p_company, p_datum) b
   GROUP BY b.sub_process_id;
$fn$ LANGUAGE sql STABLE;

COMMENT ON FUNCTION bewertung_aktuell_zum(UUID, TIMESTAMPTZ) IS
  'v_bewertung_aktuell zu einem Zeitpunkt. Fuer BC2: '
  'SELECT * FROM bewertung_aktuell_zum(p.company_id, p.uebergeben_am) mit p aus v_uebergabe_offen.';

-- Die Historie lesbar, ohne Zeilenbilder — fuer Listen und Zaehlungen.
CREATE OR REPLACE VIEW v_historie AS
SELECT audit_id, at, actor, company_id, entity, action, pk,
       coalesce(neu, alt) ->> 'process_id'     AS process_id,
       coalesce(neu, alt) ->> 'sub_process_id' AS sub_process_id,
       txid
  FROM audit_log;

-- ============================================================
-- A. ERHEBUNG EINFRIEREN
-- ============================================================
-- Befund 03.09.: _erhebung_offen() waehlt die juengste nicht verworfene
-- Erhebung ohne Filter auf `offen`; POST …/rating prueft den Status nicht.
-- Die Regel gehoert in die Datenbank (ADR-003 Regel 4).

CREATE OR REPLACE FUNCTION trg_erhebung_eingefroren() RETURNS TRIGGER AS $fn$
DECLARE v_company UUID; v_erhebung TEXT; v_status TEXT;
BEGIN
  -- Kaskaden (Loeschen des Mandanten) laufen durch: eine Ebene tiefer.
  IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN RETURN OLD; END IF;
  IF TG_OP = 'DELETE' THEN v_company := OLD.company_id; v_erhebung := OLD.erhebung_id;
  ELSE                     v_company := NEW.company_id; v_erhebung := NEW.erhebung_id; END IF;
  SELECT status INTO v_status FROM ref_erhebungen
   WHERE company_id = v_company AND erhebung_id = v_erhebung;
  IF v_status = 'abgeschlossen' THEN
    RAISE EXCEPTION
      'Erhebung % ist abgeschlossen und eingefroren. Fuer neue Werte eine neue '
      'Erhebung beginnen (POST …/erhebungen, aktion=neu).', v_erhebung
      USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS erhebung_eingefroren ON bitkom_bewertungen;
CREATE TRIGGER erhebung_eingefroren BEFORE INSERT OR UPDATE OR DELETE ON bitkom_bewertungen
  FOR EACH ROW EXECUTE FUNCTION trg_erhebung_eingefroren();
DROP TRIGGER IF EXISTS erhebung_eingefroren ON bewertung_belege;
CREATE TRIGGER erhebung_eingefroren BEFORE INSERT OR UPDATE OR DELETE ON bewertung_belege
  FOR EACH ROW EXECUTE FUNCTION trg_erhebung_eingefroren();

CREATE OR REPLACE FUNCTION trg_erhebung_status_vorwaerts() RETURNS TRIGGER AS $fn$
BEGIN
  IF OLD.status = 'abgeschlossen' AND NEW.status = 'offen' THEN
    RAISE EXCEPTION
      'Erhebung % kann nicht wieder geoeffnet werden. Verwerfen und neu beginnen — '
      'eine Freigabe koennte sich auf diesen Stand beziehen.', OLD.erhebung_id
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.status = 'verworfen' AND NEW.status <> 'verworfen' THEN
    RAISE EXCEPTION 'Erhebung % ist verworfen und bleibt es.', OLD.erhebung_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS erhebung_status_vorwaerts ON ref_erhebungen;
CREATE TRIGGER erhebung_status_vorwaerts BEFORE UPDATE OF status ON ref_erhebungen
  FOR EACH ROW EXECUTE FUNCTION trg_erhebung_status_vorwaerts();

COMMENT ON COLUMN ref_erhebungen.status IS
  'offen = neue Bewertungen landen hier · abgeschlossen = EINGEFROREN: kein '
  'INSERT/UPDATE/DELETE mehr auf ihren Bewertungen (Trigger, v2.6), kein '
  'Wiederoeffnen · verworfen = wird von den Auswertungen ignoriert, bleibt stehen.';

-- ============================================================
-- B. DAS PAKET — Datum und Liste, sonst nichts
-- ============================================================
-- Uebergabe-Einheit ist das Unternehmen (22.08., bestaetigt 03.09.); je
-- Teilprozess die anfrage_id oder NULL (Portfolio-Weg). Das Paket sagt, WAS
-- BC2 bekommen hat; die Historie sagt, wie es zu uebergeben_am aussah. Was
-- BC2 darueber hinaus liest, entscheidet BC2 — aus dem Paket heraus.

CREATE TABLE IF NOT EXISTS gate_pakete (
  company_id      UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  paket_id        UUID        NOT NULL DEFAULT gen_random_uuid(),
  uebergeben_am   TIMESTAMPTZ NOT NULL DEFAULT now(),
  uebergeben_von  TEXT        REFERENCES app_benutzer(benutzer_id),
  ereignis_id     BIGINT      REFERENCES gate_ereignisse(ereignis_id) ON DELETE CASCADE,
  hinweis         TEXT,
  PRIMARY KEY (company_id, paket_id)
);
COMMENT ON TABLE gate_pakete IS
  'Eine Uebergabe an BC2. uebergeben_am ist der Zeitpunkt, fuer den '
  'stand_zum() den Datenstand liefert. Append-only; Nachzuegler = neues Paket.';

CREATE TABLE IF NOT EXISTS gate_paket_inhalt (
  company_id           UUID   NOT NULL,
  paket_id             UUID   NOT NULL,
  sub_process_id       TEXT   NOT NULL,
  freigabe_ereignis_id BIGINT NOT NULL REFERENCES gate_ereignisse(ereignis_id) ON DELETE CASCADE,
  anfrage_id           TEXT,
  bc1_profil_stand     TEXT,
  hinweis_an_bc2       TEXT,
  PRIMARY KEY (company_id, paket_id, sub_process_id),
  FOREIGN KEY (company_id, paket_id) REFERENCES gate_pakete(company_id, paket_id) ON DELETE CASCADE,
  CONSTRAINT fk_paket_anfrage FOREIGN KEY (company_id, anfrage_id)
    REFERENCES ref_anfragen(company_id, anfrage_id) ON DELETE SET NULL
);
COMMENT ON COLUMN gate_paket_inhalt.sub_process_id IS
  'Bewusst ohne Fremdschluessel — das Paket ist ein Protokoll und ueberlebt '
  'Teilung und Stilllegung. Die Ursprungs-ID bleibt; prozess_herkunft sagt, '
  'was daraus wurde.';
COMMENT ON COLUMN gate_paket_inhalt.anfrage_id IS
  'Aus welchem Auftrag. NULL = Portfolio-Weg ("schaut mal, was wir automatisieren '
  'koennen"). BC2 gruppiert danach.';

CREATE OR REPLACE FUNCTION trg_nur_anhaengen() RETURNS TRIGGER AS $fn$
BEGIN
  IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN RETURN OLD; END IF;
  RAISE EXCEPTION '% ist append-only: % nicht erlaubt. Nachzuegler bekommen ein neues Paket.',
    TG_TABLE_NAME, TG_OP USING ERRCODE = 'check_violation';
END;
$fn$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS nur_anhaengen ON gate_pakete;
CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON gate_pakete
  FOR EACH ROW EXECUTE FUNCTION trg_nur_anhaengen();
DROP TRIGGER IF EXISTS nur_anhaengen ON gate_paket_inhalt;
CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON gate_paket_inhalt
  FOR EACH ROW EXECUTE FUNCTION trg_nur_anhaengen();

-- Die neuen Tabellen bekommen die Historie ebenfalls (der Block oben lief
-- vor ihrer Anlage).
DROP TRIGGER IF EXISTS historie ON gate_pakete;
CREATE TRIGGER historie AFTER INSERT OR UPDATE OR DELETE ON gate_pakete
  FOR EACH ROW EXECUTE FUNCTION trg_historie();
DROP TRIGGER IF EXISTS historie ON gate_paket_inhalt;
CREATE TRIGGER historie AFTER INSERT OR UPDATE OR DELETE ON gate_paket_inhalt
  FOR EACH ROW EXECUTE FUNCTION trg_historie();

-- Das Uebergabe-Ereignis: eines je Paket, am Unternehmen. v_gate_freigabe_aktuell
-- filtert auf 'teilprozess' und bleibt unberuehrt.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_gate_objekt_typ') THEN
    ALTER TABLE gate_ereignisse DROP CONSTRAINT ck_gate_objekt_typ;
  END IF;
  ALTER TABLE gate_ereignisse ADD CONSTRAINT ck_gate_objekt_typ
    CHECK (objekt_typ IN ('prozess','teilprozess','unternehmen'));
END $$;

CREATE OR REPLACE VIEW v_uebergabe_kandidaten AS
SELECT f.company_id, f.sub_process_id, f.process_id, f.ereignis_id AS freigabe_ereignis_id,
       f.entschieden_am, f.anfrage_id, f.bc0_stand, f.bc1_profil_stand, f.hinweis_an_bc2
  FROM v_gate_freigabe_aktuell f
 WHERE f.stand = 'freigegeben'
   AND NOT EXISTS (SELECT 1 FROM gate_paket_inhalt i
                    WHERE i.company_id = f.company_id AND i.freigabe_ereignis_id = f.ereignis_id);
COMMENT ON VIEW v_uebergabe_kandidaten IS
  'Freigegebene Teilprozesse, deren aktuelle Freigabe noch in keinem Paket steckt: '
  'die Vorschau vor dem Knopf, und nach der ersten Uebergabe die Nachzuegler.';

CREATE OR REPLACE FUNCTION gate_paket_schnueren(p_company UUID, p_benutzer TEXT, p_hinweis TEXT)
RETURNS UUID AS $fn$
DECLARE v_paket UUID := gen_random_uuid(); v_ereignis BIGINT; v_n INTEGER;
BEGIN
  SELECT count(*) INTO v_n FROM v_uebergabe_kandidaten WHERE company_id = p_company;
  IF v_n = 0 THEN
    RAISE EXCEPTION 'Nichts zu uebergeben: keine freigegebenen Teilprozesse ausserhalb eines Pakets.'
      USING ERRCODE = 'check_violation';
  END IF;
  INSERT INTO gate_ereignisse (gate, company_id, objekt_typ, objekt_id, ereignis,
                               benutzer_id, paket_id, grundlage)
  VALUES ('bc0-bc2', p_company, 'unternehmen', p_company::text, 'uebergeben',
          p_benutzer, v_paket, jsonb_build_object('teilprozesse', v_n))
  RETURNING ereignis_id INTO v_ereignis;
  INSERT INTO gate_pakete (company_id, paket_id, uebergeben_von, ereignis_id, hinweis)
  VALUES (p_company, v_paket, p_benutzer, v_ereignis, p_hinweis);
  INSERT INTO gate_paket_inhalt (company_id, paket_id, sub_process_id, freigabe_ereignis_id,
                                 anfrage_id, bc1_profil_stand, hinweis_an_bc2)
  SELECT k.company_id, v_paket, k.sub_process_id, k.freigabe_ereignis_id,
         k.anfrage_id, k.bc1_profil_stand, k.hinweis_an_bc2
    FROM v_uebergabe_kandidaten k WHERE k.company_id = p_company;
  RETURN v_paket;
END;
$fn$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW v_uebergabe_offen AS
SELECT p.company_id, p.paket_id, p.uebergeben_am, p.uebergeben_von, p.hinweis,
       i.sub_process_id, i.anfrage_id, i.freigabe_ereignis_id, i.bc1_profil_stand, i.hinweis_an_bc2,
       rank() OVER (PARTITION BY p.company_id ORDER BY p.uebergeben_am DESC, p.paket_id) AS paket_rang
  FROM gate_pakete p
  JOIN gate_paket_inhalt i ON i.company_id = p.company_id AND i.paket_id = p.paket_id;
COMMENT ON VIEW v_uebergabe_offen IS
  'Die Lesesicht fuer BC2: je Paket und Teilprozess. paket_rang = 1 ist das '
  'juengste. Den Datenstand dazu liefert stand_zum(<tabelle>, uebergeben_am, '
  'company_id) — fuer jede Tabelle, die BC2 lesen will.';

-- ============================================================
-- D. SICHTBAR MACHEN — aus der Historie gezaehlt
-- ============================================================
CREATE OR REPLACE VIEW v_stand_veraltet AS
WITH freigabe AS (
  SELECT f.company_id, f.sub_process_id, f.process_id, f.ereignis_id, f.entschieden_am
    FROM v_gate_freigabe_aktuell f WHERE f.stand = 'freigegeben'
), paket AS (
  SELECT i.company_id, i.sub_process_id, i.paket_id, p.uebergeben_am,
         row_number() OVER (PARTITION BY i.company_id, i.sub_process_id
                            ORDER BY p.uebergeben_am DESC) AS rang
    FROM gate_paket_inhalt i
    JOIN gate_pakete p ON p.company_id = i.company_id AND p.paket_id = i.paket_id
)
SELECT f.company_id, f.sub_process_id, f.process_id,
       f.entschieden_am AS freigegeben_am, pk.uebergeben_am, pk.paket_id,
       (SELECT count(*) FROM v_historie h
         WHERE h.company_id = f.company_id AND h.sub_process_id = f.sub_process_id
           AND h.action <> 'bestand' AND h.entity NOT LIKE 'gate_%' AND h.at > f.entschieden_am) AS aenderungen_tp_seit_freigabe,
       (SELECT count(*) FROM v_historie h
         WHERE h.company_id = f.company_id AND h.process_id = f.process_id
           AND h.action <> 'bestand' AND h.entity NOT LIKE 'gate_%' AND h.at > f.entschieden_am) AS aenderungen_kp_seit_freigabe,
       (SELECT count(*) FROM v_historie h
         WHERE h.company_id = f.company_id AND h.sub_process_id = f.sub_process_id
           AND h.action <> 'bestand' AND h.entity NOT LIKE 'gate_%' AND h.at > pk.uebergeben_am) AS aenderungen_tp_seit_paket,
       (SELECT string_agg(DISTINCT h.entity, ', ' ORDER BY h.entity) FROM v_historie h
         WHERE h.company_id = f.company_id AND h.sub_process_id = f.sub_process_id
           AND h.action <> 'bestand' AND h.entity NOT LIKE 'gate_%' AND h.at > f.entschieden_am) AS geaenderte_tabellen,
       (SELECT NOT t.aktiv FROM ref_teilprozesse t
         WHERE t.company_id = f.company_id AND t.sub_process_id = f.sub_process_id) AS stillgelegt,
       EXISTS (SELECT 1 FROM prozess_herkunft h
                WHERE h.company_id = f.company_id AND h.vorgaenger_id = f.sub_process_id) AS struktur_geaendert
  FROM freigabe f
  LEFT JOIN paket pk ON pk.company_id = f.company_id AND pk.sub_process_id = f.sub_process_id AND pk.rang = 1;
COMMENT ON VIEW v_stand_veraltet IS
  'Je freigegebenem Teilprozess: wie viele Aenderungen die Historie seit Freigabe '
  'bzw. Uebergabe kennt, an welchen Tabellen, und ob der Teilprozess stillgelegt '
  'oder umgebaut wurde. Die Sicht verbietet nichts — sie sagt, dass eine Frage '
  'ansteht. Antwort: widerrufen, neu freigeben, oder BC2 rechnet weiter.';

-- ============================================================
-- F. LOESCHEN — die einzige harte Sperre
-- ============================================================
CREATE OR REPLACE FUNCTION trg_stilllegen_statt_loeschen() RETURNS TRIGGER AS $fn$
BEGIN
  IF pg_trigger_depth() > 1 THEN RETURN OLD; END IF;   -- Kaskade vom Mandanten/Kernprozess
  RAISE EXCEPTION
    'Loeschen in % abgewiesen — stilllegen (aktiv = false). Bewertungen, '
    'Freigaben und BC-Ergebnisse haengen daran (ADR-004 R4).', TG_TABLE_NAME
    USING ERRCODE = 'check_violation';
END;
$fn$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS stilllegen_statt_loeschen ON ref_prozesse;
CREATE TRIGGER stilllegen_statt_loeschen BEFORE DELETE ON ref_prozesse
  FOR EACH ROW EXECUTE FUNCTION trg_stilllegen_statt_loeschen();
DROP TRIGGER IF EXISTS stilllegen_statt_loeschen ON ref_teilprozesse;
CREATE TRIGGER stilllegen_statt_loeschen BEFORE DELETE ON ref_teilprozesse
  FOR EACH ROW EXECUTE FUNCTION trg_stilllegen_statt_loeschen();

-- ============================================================
-- RECHTE
-- ============================================================
-- Lesen: alle. audit_log traegt keine Klarnamen und keine app_*-Tabellen.
GRANT SELECT ON audit_log, v_historie, v_uebergabe_offen, v_uebergabe_kandidaten, v_stand_veraltet
  TO bc_leser;

COMMIT;

-- ============================================================
-- KONTROLLE — nach dem Einspielen
-- ============================================================
-- 1) Trigger auf allen Fachtabellen:
--    SELECT count(*) FROM pg_trigger WHERE tgname = 'historie';   → Zahl der Fachtabellen
-- 2) Bestandsaufnahme vorhanden, je Mandant:
--    SELECT company_id, count(*) FROM audit_log WHERE action='bestand' GROUP BY 1;
-- 3) Zeitreise antwortet:
--    SELECT count(*) FROM stand_zum('bitkom_bewertungen', now(), NULL);  → wie count(*) der Tabelle
-- 4) Keine Klarnamen:
--    SELECT count(*) FROM audit_log WHERE entity='ref_personen' AND (neu ? 'name' OR alt ? 'name'); → 0
-- 5) Keine Pakete: SELECT count(*) FROM gate_pakete; → 0
