-- ============================================================
-- BC0 · Schema v2.7 — Die Anfrage als Klammer: n:m-Prozessbezug,
--                     vollstaendige Uebergabe, Status `uebergeben`
-- Stand: 03.09.2026 (nachts) · Simeon Ehmer · zum Einspielen am 04.09.2026
-- VORAUSSETZUNG: schema_v2.6_historie_und_paket.sql
-- ============================================================
--
-- REGEL (Simeon, 03.09.2026, spaetabends)
--   Uebergeben wird eine Anfrage nur VOLLSTAENDIG: Alle Teilprozesse, die zu
--   ihr gehoeren, sind freigegeben — sonst gibt es kein Paket. Ein ROI auf
--   einem Ausschnitt waere falsch. Nachzuegler gibt es bei einer Anfrage nicht;
--   aendert sich der Umfang nach der Uebergabe, entsteht ein neues Paket der
--   ganzen Anfrage, und BC2 rechnet neu.
--
-- WAS DIESES SKRIPT TUT
--   1. Status `uebergeben` zwischen `am_gate` und `bewertet` (ck_anfrage_status).
--   2. anfrage_prozesse — eine Anfrage betrifft x Kernprozesse und y
--      Teilprozesse (Punkt 115). Genau ein Hauptbezug je Anfrage; der steht
--      weiterhin auch in ref_anfragen.process_id (Trigger haelt es gleich).
--      Bestand wird uebernommen.
--   3. v_anfrage_teilprozesse — die Sollliste je Anfrage, aufgeloest: ein
--      Bezug auf einen Kernprozess ohne Teilprozess heisst "alle aktiven
--      Teilprozesse dieses Kernprozesses".
--   4. v_anfrage_uebergabe_stand — je Anfrage: soll, freigegeben, fehlend,
--      uebergabefaehig, letztes Paket.
--   5. gate_paket_schnueren() neu: je Anfrage (vollstaendig, sonst Abbruch mit
--      Liste der fehlenden) oder als Portfolio mit ausdruecklicher Liste.
--      Ereignis `uebergeben` am Objekt `anfrage`. Setzt den Status.
--
-- Wiederholbar. Keine Bestandsdaten geaendert ausser der Uebernahme der
-- bestehenden Bezuege nach anfrage_prozesse (INSERT, kein UPDATE).
-- ============================================================

BEGIN;

-- ============================================================
-- 1. STATUS `uebergeben`
-- ============================================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_anfrage_status') THEN
    ALTER TABLE ref_anfragen DROP CONSTRAINT ck_anfrage_status;
  END IF;
  ALTER TABLE ref_anfragen ADD CONSTRAINT ck_anfrage_status
    CHECK (status IN ('eingegangen','zugeordnet','im_interview','am_gate','uebergeben',
                      'bewertet','beauftragt','erledigt','abgelehnt'));
END $$;

COMMENT ON COLUMN ref_anfragen.status IS
  'eingegangen -> zugeordnet -> im_interview -> am_gate -> uebergeben -> bewertet -> '
  'beauftragt -> erledigt | abgelehnt. Gate 0 steht ZWISCHEN Interview und '
  'ROI-Rechnung. uebergeben (v2.7) = das Paket an BC2 ist geschnuert, vollstaendig.';

-- ============================================================
-- 2. ANFRAGE_PROZESSE — n:m (Punkt 115)
-- ============================================================
CREATE TABLE IF NOT EXISTS anfrage_prozesse (
  bezug_id         BIGSERIAL PRIMARY KEY,
  company_id       UUID        NOT NULL,
  anfrage_id       TEXT        NOT NULL,
  process_id       VARCHAR(8)  NOT NULL,
  sub_process_id   VARCHAR(16),                         -- NULL = ganzer Kernprozess
  rolle            TEXT        NOT NULL DEFAULT 'beteiligt'
                   CHECK (rolle IN ('haupt','beteiligt')),
  zuordnung_quelle TEXT        NOT NULL
                   CHECK (zuordnung_quelle IN ('anfrage','vorschlag_bc0','vorschlag_bc1','interview')),
  angelegt_am      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_ap_anfrage FOREIGN KEY (company_id, anfrage_id)
    REFERENCES ref_anfragen (company_id, anfrage_id) ON DELETE CASCADE,
  -- CASCADE nur fuer die Mandantenloeschung (DSGVO): Ein einzelner Prozess ist
  -- seit v2.6 ohnehin nicht loeschbar (stilllegen_statt_loeschen). RESTRICT
  -- haette die Kaskade vom Mandanten blockiert — gefunden von der Loeschprobe.
  CONSTRAINT fk_ap_prozess FOREIGN KEY (company_id, process_id)
    REFERENCES ref_prozesse (company_id, process_id) ON DELETE CASCADE,
  CONSTRAINT fk_ap_teilprozess FOREIGN KEY (company_id, sub_process_id)
    REFERENCES ref_teilprozesse (company_id, sub_process_id) ON DELETE CASCADE,
  CONSTRAINT ck_ap_tp_gehoert_kp CHECK (sub_process_id IS NULL OR sub_process_id LIKE process_id || '.%')
);
-- Ein Bezug je Anfrage und Ziel — NULL im Teilprozess zaehlt dabei als Wert.
CREATE UNIQUE INDEX IF NOT EXISTS ux_ap_bezug
  ON anfrage_prozesse (company_id, anfrage_id, process_id, coalesce(sub_process_id, ''));
-- Genau ein Hauptbezug je Anfrage.
CREATE UNIQUE INDEX IF NOT EXISTS ux_ap_haupt
  ON anfrage_prozesse (company_id, anfrage_id) WHERE rolle = 'haupt';

COMMENT ON TABLE anfrage_prozesse IS
  'Welche Kernprozesse und Teilprozesse eine Anfrage betrifft (n:m, v2.7). '
  'Genau ein Bezug ist der Hauptbezug — er steht zusaetzlich in ref_anfragen. '
  'Ein Bezug ohne Teilprozess meint den ganzen Kernprozess. Die Liste ist die '
  'SOLL-Liste der Uebergabe: erst wenn alle Teilprozesse freigegeben sind, '
  'gibt es ein Paket.';

-- Der Hauptbezug spiegelt sich in ref_anfragen — die dortigen Spalten bleiben
-- die Kurzform (Sichten, Anfrageliste, CHECK "kein Fortschritt ohne Prozess").
CREATE OR REPLACE FUNCTION trg_ap_haupt_spiegeln() RETURNS TRIGGER AS $fn$
BEGIN
  IF NEW.rolle = 'haupt' THEN
    UPDATE ref_anfragen
       SET process_id = NEW.process_id, sub_process_id = NEW.sub_process_id,
           zuordnung_quelle = NEW.zuordnung_quelle
     WHERE company_id = NEW.company_id AND anfrage_id = NEW.anfrage_id
       AND (process_id IS DISTINCT FROM NEW.process_id
            OR sub_process_id IS DISTINCT FROM NEW.sub_process_id
            OR zuordnung_quelle IS DISTINCT FROM NEW.zuordnung_quelle);
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS ap_haupt_spiegeln ON anfrage_prozesse;
CREATE TRIGGER ap_haupt_spiegeln AFTER INSERT OR UPDATE ON anfrage_prozesse
  FOR EACH ROW EXECUTE FUNCTION trg_ap_haupt_spiegeln();

-- Historie auch hier (die Tabelle ist neu; der v2.6-Block lief vorher).
DROP TRIGGER IF EXISTS historie ON anfrage_prozesse;
CREATE TRIGGER historie AFTER INSERT OR UPDATE OR DELETE ON anfrage_prozesse
  FOR EACH ROW EXECUTE FUNCTION trg_historie();

-- Bestand uebernehmen: der bisherige Einzelbezug wird der Hauptbezug.
INSERT INTO anfrage_prozesse (company_id, anfrage_id, process_id, sub_process_id, rolle, zuordnung_quelle)
SELECT a.company_id, a.anfrage_id, a.process_id, a.sub_process_id, 'haupt', a.zuordnung_quelle
  FROM ref_anfragen a
 WHERE a.process_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM anfrage_prozesse p
                    WHERE p.company_id = a.company_id AND p.anfrage_id = a.anfrage_id);

-- ============================================================
-- 3. DIE SOLL-LISTE JE ANFRAGE
-- ============================================================
CREATE OR REPLACE VIEW v_anfrage_teilprozesse AS
WITH bezuege AS (
  SELECT p.company_id, p.anfrage_id, p.process_id, p.rolle, p.zuordnung_quelle,
         coalesce(p.sub_process_id, t.sub_process_id) AS sub_process_id,
         (p.sub_process_id IS NULL) AS aus_kernprozess
    FROM anfrage_prozesse p
    LEFT JOIN ref_teilprozesse t
      ON p.sub_process_id IS NULL
     AND t.company_id = p.company_id AND t.process_id = p.process_id AND t.aktiv
)
SELECT DISTINCT ON (b.company_id, b.anfrage_id, b.sub_process_id)
       b.company_id, b.anfrage_id, b.process_id, b.sub_process_id, b.rolle,
       b.zuordnung_quelle, b.aus_kernprozess,
       (f.stand = 'freigegeben')                       AS freigegeben,
       f.ereignis_id                                   AS freigabe_ereignis_id,
       f.entschieden_am,
       EXISTS (SELECT 1 FROM gate_paket_inhalt i
                WHERE i.company_id = b.company_id AND i.anfrage_id = b.anfrage_id
                  AND i.sub_process_id = b.sub_process_id
                  AND i.freigabe_ereignis_id = f.ereignis_id) AS im_paket
  FROM bezuege b
  LEFT JOIN v_gate_freigabe_aktuell f
    ON f.company_id = b.company_id AND f.sub_process_id = b.sub_process_id
 WHERE b.sub_process_id IS NOT NULL
 ORDER BY b.company_id, b.anfrage_id, b.sub_process_id,
          (b.rolle = 'haupt') DESC, b.aus_kernprozess;

COMMENT ON VIEW v_anfrage_teilprozesse IS
  'Die SOLL-Liste je Anfrage, aufgeloest auf Teilprozesse: Ein Bezug ohne '
  'Teilprozess meint alle aktiven Teilprozesse des Kernprozesses. Je Zeile, ob '
  'die aktuelle Freigabe steht und ob sie schon in einem Paket dieser Anfrage '
  'liegt.';

-- ============================================================
-- 4. JE ANFRAGE: SOLL, IST, FEHLT, UEBERGABEFAEHIG
-- ============================================================
CREATE OR REPLACE VIEW v_anfrage_uebergabe_stand AS
SELECT a.company_id, a.anfrage_id, a.status, a.eingang_am,
       count(t.sub_process_id)                                        AS soll,
       count(*) FILTER (WHERE t.freigegeben)                          AS freigegeben,
       array_remove(array_agg(t.sub_process_id ORDER BY t.sub_process_id)
                    FILTER (WHERE NOT coalesce(t.freigegeben, false)), NULL) AS fehlend,
       (count(t.sub_process_id) > 0
        AND count(*) FILTER (WHERE t.freigegeben) = count(t.sub_process_id)) AS vollstaendig,
       -- Uebergabefaehig: vollstaendig UND nicht bereits mit genau diesen
       -- Freigaben uebergeben (sonst entstuende ein identisches zweites Paket).
       (count(t.sub_process_id) > 0
        AND count(*) FILTER (WHERE t.freigegeben) = count(t.sub_process_id)
        AND count(*) FILTER (WHERE NOT coalesce(t.im_paket, false)) > 0)    AS uebergabefaehig,
       (SELECT p.paket_id FROM gate_pakete p JOIN gate_paket_inhalt i
           ON i.company_id = p.company_id AND i.paket_id = p.paket_id
         WHERE i.company_id = a.company_id AND i.anfrage_id = a.anfrage_id
         ORDER BY p.uebergeben_am DESC LIMIT 1)                        AS letztes_paket_id,
       (SELECT max(p.uebergeben_am) FROM gate_pakete p JOIN gate_paket_inhalt i
           ON i.company_id = p.company_id AND i.paket_id = p.paket_id
         WHERE i.company_id = a.company_id AND i.anfrage_id = a.anfrage_id) AS letzte_uebergabe_am
  FROM ref_anfragen a
  LEFT JOIN v_anfrage_teilprozesse t
    ON t.company_id = a.company_id AND t.anfrage_id = a.anfrage_id
 GROUP BY a.company_id, a.anfrage_id, a.status, a.eingang_am;

COMMENT ON VIEW v_anfrage_uebergabe_stand IS
  'Je Anfrage: wie viele Teilprozesse sie betrifft (soll), wie viele freigegeben '
  'sind, welche fehlen, und ob ein Paket geschnuert werden darf. Die Regel: '
  'uebergeben wird nur vollstaendig — ein ROI auf einem Ausschnitt waere falsch.';

-- ============================================================
-- 5. DAS PAKET — je Anfrage vollstaendig, oder als Portfolio mit Liste
-- ============================================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_gate_objekt_typ') THEN
    ALTER TABLE gate_ereignisse DROP CONSTRAINT ck_gate_objekt_typ;
  END IF;
  ALTER TABLE gate_ereignisse ADD CONSTRAINT ck_gate_objekt_typ
    CHECK (objekt_typ IN ('prozess','teilprozess','unternehmen','anfrage'));
END $$;

DROP FUNCTION IF EXISTS gate_paket_schnueren(UUID, TEXT, TEXT);

CREATE OR REPLACE FUNCTION gate_paket_schnueren(
    p_company UUID, p_benutzer TEXT, p_hinweis TEXT,
    p_anfrage TEXT DEFAULT NULL, p_teilprozesse TEXT[] DEFAULT NULL)
RETURNS UUID AS $fn$
DECLARE
  v_paket    UUID := gen_random_uuid();
  v_ereignis BIGINT;
  v_soll     INTEGER; v_frei INTEGER; v_neu INTEGER;
  v_fehlend  TEXT;
  v_status   TEXT;
BEGIN
  IF p_anfrage IS NOT NULL THEN
    -- ---- Weg 1: die Anfrage, vollstaendig ----
    SELECT status INTO v_status FROM ref_anfragen
     WHERE company_id = p_company AND anfrage_id = p_anfrage;
    IF v_status IS NULL THEN
      RAISE EXCEPTION 'Unbekannte Anfrage: %', p_anfrage USING ERRCODE = 'check_violation';
    END IF;
    IF v_status = 'abgelehnt' THEN
      RAISE EXCEPTION 'Anfrage % ist abgelehnt.', p_anfrage USING ERRCODE = 'check_violation';
    END IF;

    SELECT count(*), count(*) FILTER (WHERE freigegeben),
           count(*) FILTER (WHERE NOT coalesce(im_paket, false)),
           string_agg(sub_process_id, ', ' ORDER BY sub_process_id) FILTER (WHERE NOT coalesce(freigegeben, false))
      INTO v_soll, v_frei, v_neu, v_fehlend
      FROM v_anfrage_teilprozesse
     WHERE company_id = p_company AND anfrage_id = p_anfrage;

    IF v_soll = 0 THEN
      RAISE EXCEPTION 'Anfrage % hat keinen Teilprozess — erst zuordnen (anfrage_prozesse).', p_anfrage
        USING ERRCODE = 'check_violation';
    END IF;
    IF v_frei < v_soll THEN
      RAISE EXCEPTION 'Anfrage % ist nicht vollstaendig freigegeben: % von % — es fehlen %. '
                      'Uebergeben wird nur vollstaendig.', p_anfrage, v_frei, v_soll, v_fehlend
        USING ERRCODE = 'check_violation';
    END IF;
    IF v_neu = 0 THEN
      RAISE EXCEPTION 'Anfrage % ist mit genau diesen Freigaben bereits uebergeben. Ein zweites, '
                      'identisches Paket entsteht nicht.', p_anfrage USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO gate_ereignisse (gate, company_id, objekt_typ, objekt_id, ereignis,
                                 benutzer_id, paket_id, anfrage_id, grundlage)
    VALUES ('bc0-bc2', p_company, 'anfrage', p_anfrage, 'uebergeben',
            p_benutzer, v_paket, p_anfrage, jsonb_build_object('teilprozesse', v_soll))
    RETURNING ereignis_id INTO v_ereignis;

    INSERT INTO gate_pakete (company_id, paket_id, uebergeben_von, ereignis_id, hinweis)
    VALUES (p_company, v_paket, p_benutzer, v_ereignis, p_hinweis);

    INSERT INTO gate_paket_inhalt (company_id, paket_id, sub_process_id, freigabe_ereignis_id,
                                   anfrage_id, bc1_profil_stand, hinweis_an_bc2)
    SELECT t.company_id, v_paket, t.sub_process_id, t.freigabe_ereignis_id,
           p_anfrage, f.bc1_profil_stand, f.hinweis_an_bc2
      FROM v_anfrage_teilprozesse t
      JOIN v_gate_freigabe_aktuell f
        ON f.company_id = t.company_id AND f.sub_process_id = t.sub_process_id
     WHERE t.company_id = p_company AND t.anfrage_id = p_anfrage;

    -- Der Status folgt der Uebergabe. Ein Ruecksprung ist kein Fall: wer schon
    -- weiter ist (bewertet …), bleibt es — dann war es ein neues Paket nach
    -- einer Umfangsaenderung, und BC2 rechnet neu.
    UPDATE ref_anfragen SET status = 'uebergeben', status_seit = current_date
     WHERE company_id = p_company AND anfrage_id = p_anfrage
       AND status IN ('zugeordnet','im_interview','am_gate');

  ELSE
    -- ---- Weg 2: Portfolio, mit ausdruecklicher Liste ----
    IF p_teilprozesse IS NULL OR array_length(p_teilprozesse, 1) IS NULL THEN
      RAISE EXCEPTION 'Ohne Anfrage braucht die Uebergabe eine ausdrueckliche Liste der Teilprozesse.'
        USING ERRCODE = 'check_violation';
    END IF;
    SELECT string_agg(x, ', ') INTO v_fehlend
      FROM unnest(p_teilprozesse) x
     WHERE NOT EXISTS (SELECT 1 FROM v_uebergabe_kandidaten k
                        WHERE k.company_id = p_company AND k.sub_process_id = x);
    IF v_fehlend IS NOT NULL THEN
      RAISE EXCEPTION 'Nicht uebergabefaehig (nicht freigegeben oder schon in einem Paket): %', v_fehlend
        USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO gate_ereignisse (gate, company_id, objekt_typ, objekt_id, ereignis,
                                 benutzer_id, paket_id, grundlage)
    VALUES ('bc0-bc2', p_company, 'unternehmen', p_company::text, 'uebergeben',
            p_benutzer, v_paket, jsonb_build_object('teilprozesse', array_length(p_teilprozesse, 1),
                                                     'portfolio', true))
    RETURNING ereignis_id INTO v_ereignis;

    INSERT INTO gate_pakete (company_id, paket_id, uebergeben_von, ereignis_id, hinweis)
    VALUES (p_company, v_paket, p_benutzer, v_ereignis, p_hinweis);

    INSERT INTO gate_paket_inhalt (company_id, paket_id, sub_process_id, freigabe_ereignis_id,
                                   anfrage_id, bc1_profil_stand, hinweis_an_bc2)
    SELECT k.company_id, v_paket, k.sub_process_id, k.freigabe_ereignis_id,
           NULL, k.bc1_profil_stand, k.hinweis_an_bc2
      FROM v_uebergabe_kandidaten k
     WHERE k.company_id = p_company AND k.sub_process_id = ANY (p_teilprozesse);
  END IF;

  RETURN v_paket;
END;
$fn$ LANGUAGE plpgsql;

COMMENT ON FUNCTION gate_paket_schnueren(UUID, TEXT, TEXT, TEXT, TEXT[]) IS
  'Paket an BC2. Mit p_anfrage: nur, wenn ALLE Teilprozesse der Anfrage '
  '(v_anfrage_teilprozesse) freigegeben sind — sonst Abbruch mit der Liste der '
  'fehlenden; setzt den Anfragestatus auf uebergeben. Ohne p_anfrage: '
  'Portfolio-Weg mit ausdruecklicher Liste aus v_uebergabe_kandidaten.';

-- ============================================================
-- RECHTE
-- ============================================================
GRANT SELECT ON v_anfrage_teilprozesse, v_anfrage_uebergabe_stand TO bc_leser;
-- anfrage_prozesse traegt keine Klarnamen; BC1 liest die Zuordnung dort.
GRANT SELECT ON anfrage_prozesse TO bc_leser;

COMMIT;

-- ============================================================
-- KONTROLLE — nach dem Einspielen
-- ============================================================
-- 1) Jede Anfrage mit Bezug hat genau einen Hauptbezug:
--    SELECT a.anfrage_id, count(p.*) FILTER (WHERE p.rolle='haupt')
--      FROM ref_anfragen a LEFT JOIN anfrage_prozesse p USING (company_id, anfrage_id)
--     GROUP BY 1;  → 1 bei allen mit process_id, 0 bei "weiss ich nicht"
-- 2) Sollstand:  SELECT anfrage_id, soll, freigegeben, fehlend, uebergabefaehig FROM v_anfrage_uebergabe_stand;
-- 3) Status-Werteliste enthaelt uebergeben:
--    SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_anfrage_status';
