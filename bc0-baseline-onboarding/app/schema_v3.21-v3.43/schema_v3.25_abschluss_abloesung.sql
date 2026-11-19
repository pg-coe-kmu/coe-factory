-- Schema v3.25 — Anfrage abschliessen, alte Prozesse abloesen (31.10.2026)
--
-- Anlass (BC0, 31.10.): Die Verlaufslinie endet bei BC4. Danach fehlen zwei
-- menschliche Schritte:
--   7. Anfrage abgeschlossen  — Haken manuell, = Status 'erledigt' (gibt es seit
--      v2.2). Sperrt KEINEN beteiligten Prozess.
--   8. Prozess(e) alt sperren? Ja / Nein — manuell, mit Begruendung.
--      Ja = "abgeloest durch Folgeprozess": die Teilprozesse der Anfrage werden
--      STILLGELEGT (aktiv = false, wie seit v2.6 statt Loeschen) und
--      EINGEFROREN (keine Aenderung an Stammzeile und Bitkom-Werten mehr).
--      Nein = Entscheidung wird festgehalten, nichts wird gesperrt.
--
-- Neu:
--   * anfrage_abloesung      — die Entscheidung je Anfrage (genau eine, append-only)
--   * teilprozess_abgeloest  — welcher Teilprozess durch welche Anfrage abgeloest ist
--   * Trigger teilprozess_eingefroren auf ref_teilprozesse (UPDATE) und
--     bitkom_bewertungen (INSERT/UPDATE)
--   * Funktion anfrage_alt_entscheiden(company, anfrage, benutzer, sperren, begruendung)
-- Bestehende Tabellen, Sichten und Funktionen bleiben unveraendert.
--
-- Ausfuehren als postgres, eine Transaktion. Gegenprobe: pruefung_v3.25_abschluss_abloesung.sql

BEGIN;

CREATE TABLE IF NOT EXISTS anfrage_abloesung (
  company_id      UUID        NOT NULL,
  anfrage_id      TEXT        NOT NULL,
  alt_sperren     BOOLEAN     NOT NULL,
  begruendung     TEXT        NOT NULL CHECK (length(btrim(begruendung)) > 0),
  teilprozesse    TEXT[]      NOT NULL DEFAULT '{}',
  entschieden_von TEXT        REFERENCES app_benutzer(benutzer_id),
  entschieden_am  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, anfrage_id),
  FOREIGN KEY (company_id, anfrage_id) REFERENCES ref_anfragen(company_id, anfrage_id) ON DELETE CASCADE
);
COMMENT ON TABLE anfrage_abloesung IS
  'v3.25: Entscheidung nach Abschluss einer Anfrage, ob die alten Teilprozesse abgeloest '
  '(stillgelegt + eingefroren) werden. Genau eine je Anfrage, append-only.';

CREATE TABLE IF NOT EXISTS teilprozess_abgeloest (
  company_id     UUID        NOT NULL,
  sub_process_id VARCHAR     NOT NULL,
  anfrage_id     TEXT        NOT NULL,
  abgeloest_am   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, sub_process_id),
  FOREIGN KEY (company_id, sub_process_id) REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, anfrage_id) REFERENCES ref_anfragen(company_id, anfrage_id) ON DELETE CASCADE
);
COMMENT ON TABLE teilprozess_abgeloest IS
  'v3.25: Teilprozess ist durch den Folgeprozess aus dieser Anfrage abgeloest — stillgelegt '
  'und eingefroren (Trigger teilprozess_eingefroren).';

-- append-only (Kaskade vom Mandanten laeuft durch, siehe trg_nur_anhaengen v2.6)
DROP TRIGGER IF EXISTS nur_anhaengen ON anfrage_abloesung;
CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON anfrage_abloesung
  FOR EACH ROW EXECUTE FUNCTION trg_nur_anhaengen();
DROP TRIGGER IF EXISTS nur_anhaengen ON teilprozess_abgeloest;
CREATE TRIGGER nur_anhaengen BEFORE UPDATE OR DELETE ON teilprozess_abgeloest
  FOR EACH ROW EXECUTE FUNCTION trg_nur_anhaengen();

-- Historie wie bei allen Fachtabellen (v2.6)
DROP TRIGGER IF EXISTS historie ON anfrage_abloesung;
CREATE TRIGGER historie AFTER INSERT OR UPDATE OR DELETE ON anfrage_abloesung
  FOR EACH ROW EXECUTE FUNCTION trg_historie();
DROP TRIGGER IF EXISTS historie ON teilprozess_abgeloest;
CREATE TRIGGER historie AFTER INSERT OR UPDATE OR DELETE ON teilprozess_abgeloest
  FOR EACH ROW EXECUTE FUNCTION trg_historie();

-- Einfrieren
CREATE OR REPLACE FUNCTION trg_teilprozess_eingefroren() RETURNS TRIGGER AS $fn$
DECLARE v_anfrage TEXT;
BEGIN
  SELECT anfrage_id INTO v_anfrage FROM teilprozess_abgeloest
   WHERE company_id = NEW.company_id
     AND sub_process_id = (CASE WHEN TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'ref_teilprozesse'
                                THEN OLD.sub_process_id ELSE NEW.sub_process_id END);
  IF v_anfrage IS NOT NULL THEN
    RAISE EXCEPTION 'Teilprozess % ist durch den Folgeprozess aus % abgeloest und eingefroren — '
                    'keine Aenderung mehr (%).', NEW.sub_process_id, v_anfrage, TG_TABLE_NAME
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS teilprozess_eingefroren ON ref_teilprozesse;
CREATE TRIGGER teilprozess_eingefroren BEFORE UPDATE ON ref_teilprozesse
  FOR EACH ROW EXECUTE FUNCTION trg_teilprozess_eingefroren();
DROP TRIGGER IF EXISTS teilprozess_eingefroren ON bitkom_bewertungen;
CREATE TRIGGER teilprozess_eingefroren BEFORE INSERT OR UPDATE ON bitkom_bewertungen
  FOR EACH ROW EXECUTE FUNCTION trg_teilprozess_eingefroren();

-- Die Entscheidung
CREATE OR REPLACE FUNCTION anfrage_alt_entscheiden(
    p_company UUID, p_anfrage TEXT, p_benutzer TEXT, p_sperren BOOLEAN, p_begruendung TEXT
) RETURNS INTEGER
LANGUAGE plpgsql AS $$
DECLARE
  v_status TEXT;
  v_tps    TEXT[];
  v_n      INTEGER := 0;
BEGIN
  SELECT status INTO v_status FROM ref_anfragen WHERE company_id = p_company AND anfrage_id = p_anfrage;
  IF v_status IS NULL THEN
    RAISE EXCEPTION 'Unbekannte Anfrage: %', p_anfrage USING ERRCODE = 'check_violation';
  END IF;
  IF v_status <> 'erledigt' THEN
    RAISE EXCEPTION 'Anfrage % steht auf "%" — erst abschliessen (Status erledigt), dann ueber die '
                    'alten Prozesse entscheiden.', p_anfrage, v_status USING ERRCODE = 'check_violation';
  END IF;
  IF p_sperren IS NULL THEN
    RAISE EXCEPTION 'Ja oder Nein waehlen.' USING ERRCODE = 'check_violation';
  END IF;
  IF p_begruendung IS NULL OR length(btrim(p_begruendung)) = 0 THEN
    RAISE EXCEPTION 'Die Entscheidung braucht eine Begruendung.' USING ERRCODE = 'check_violation';
  END IF;
  IF EXISTS (SELECT 1 FROM anfrage_abloesung WHERE company_id = p_company AND anfrage_id = p_anfrage) THEN
    RAISE EXCEPTION 'Fuer % ist bereits entschieden.', p_anfrage USING ERRCODE = 'check_violation';
  END IF;

  SELECT coalesce(array_agg(DISTINCT sub_process_id ORDER BY sub_process_id), '{}') INTO v_tps
    FROM v_anfrage_teilprozesse
   WHERE company_id = p_company AND anfrage_id = p_anfrage AND sub_process_id IS NOT NULL;

  IF p_sperren THEN
    -- erst stilllegen, dann einfrieren (der Trigger liesse das UPDATE danach nicht mehr zu)
    UPDATE ref_teilprozesse SET aktiv = false
     WHERE company_id = p_company AND sub_process_id = ANY (v_tps) AND aktiv
       AND NOT EXISTS (SELECT 1 FROM teilprozess_abgeloest a
                        WHERE a.company_id = p_company AND a.sub_process_id = ref_teilprozesse.sub_process_id);
    INSERT INTO teilprozess_abgeloest (company_id, sub_process_id, anfrage_id)
    SELECT p_company, x, p_anfrage FROM unnest(v_tps) x
    ON CONFLICT (company_id, sub_process_id) DO NOTHING;
    GET DIAGNOSTICS v_n = ROW_COUNT;
  END IF;

  INSERT INTO anfrage_abloesung (company_id, anfrage_id, alt_sperren, begruendung, teilprozesse, entschieden_von)
  VALUES (p_company, p_anfrage, p_sperren, btrim(p_begruendung), v_tps, p_benutzer);
  RETURN v_n;
END;
$$;

REVOKE ALL ON FUNCTION anfrage_alt_entscheiden(UUID, TEXT, TEXT, BOOLEAN, TEXT) FROM PUBLIC;
DO $r$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON FUNCTION anfrage_alt_entscheiden(UUID, TEXT, TEXT, BOOLEAN, TEXT) FROM anon, authenticated';
    EXECUTE 'REVOKE ALL ON anfrage_abloesung, teilprozess_abgeloest FROM anon, authenticated';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    EXECUTE 'GRANT SELECT ON anfrage_abloesung, teilprozess_abgeloest TO bc_leser';
  END IF;
END $r$;

COMMIT;
