-- Schema v3.19b — Anfrage nur mit benannten Teilprozessen; verworfene Erhebung
-- macht die Freigabe veraltet (25.10.2026)
--
-- Anlass: Rueckfragen BC1 (Richard, 25.10.), Punkte 2 und 4; Drehbuch S-175 ff.
--
--   A. Unbenannte Teilprozesse ("Teilprozess N", leer) koennen seit v3.17 an Gate 0
--      nicht freigegeben werden. Bisher liessen sie sich aber einer Anfrage zuordnen —
--      die Anfrage waere dann nie uebergabefaehig geworden.
--        * Direkter Bezug (anfrage_prozesse.sub_process_id gesetzt): Trigger weist ab.
--        * Bezug auf den ganzen Kernprozess: unbenannte Teilprozesse gehoeren nicht
--          zur SOLL-Liste (v_anfrage_teilprozesse). Kein Abweisen, damit das Anlegen
--          neuer Teilprozesse in der PWA ("Teilprozess N") weiter geht.
--   B. Eine Freigabe merkt sich ihre Erhebung (gate_ereignisse.erhebung_id = bc0_stand).
--      Wird diese Erhebung verworfen, ist die Freigabe veraltet (v_freigabe_datenstand).
--      Massgeblich ist nur die Erhebung der Freigabe, nicht die des BC1-Profils
--      (Entscheidung 25.10.: abweichende Erhebung im Profil verlangt kein neues Interview).
--      Die Begruendung erscheint in geaenderte_tabellen ("Erhebung E-… verworfen") —
--      das Backend zeigt sie ohne Aenderung im Gate an.
--
-- Spalten der Sichten bleiben, neu nur hinten: v_freigabe_datenstand.erhebung_verworfen.
-- Setzt v3.17 voraus. Ausfuehren als postgres, eine Transaktion.
-- Gegenprobe: pruefung_v3.19b.sql

BEGIN;

DO $$
BEGIN
  IF to_regclass('v_freigabe_datenstand') IS NULL OR to_regproc('teilprozess_unbenannt') IS NULL THEN
    RAISE EXCEPTION 'v3.17 ist nicht eingespielt — erst schema_v3.17_datenstand_und_namen.sql.';
  END IF;
END $$;

-- ---------------------------------------------------------------- A1 Trigger
CREATE OR REPLACE FUNCTION trg_anfrage_prozesse_benannt() RETURNS TRIGGER AS $fn$
DECLARE v_name TEXT;
BEGIN
  IF NEW.sub_process_id IS NOT NULL THEN
    SELECT sub_process_name INTO v_name FROM ref_teilprozesse
     WHERE company_id = NEW.company_id AND sub_process_id = NEW.sub_process_id;
    IF teilprozess_unbenannt(v_name) THEN
      RAISE EXCEPTION 'Teilprozess % ist noch nicht benannt ("%"). Erst benennen, dann der Anfrage zuordnen.',
                      NEW.sub_process_id, coalesce(v_name, '')
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS anfrage_prozesse_benannt ON anfrage_prozesse;
CREATE TRIGGER anfrage_prozesse_benannt
  BEFORE INSERT OR UPDATE OF process_id, sub_process_id ON anfrage_prozesse
  FOR EACH ROW EXECUTE FUNCTION trg_anfrage_prozesse_benannt();

-- ---------------------------------------------------------------- B Sicht Datenstand
CREATE OR REPLACE VIEW v_freigabe_datenstand AS
WITH f AS (
  SELECT a.company_id, a.sub_process_id, a.process_id, a.ereignis_id, a.entschieden_am,
         g.datenstand, a.bc0_stand
    FROM v_gate_freigabe_aktuell a
    JOIN gate_ereignisse g ON g.ereignis_id = a.ereignis_id
   WHERE a.stand = 'freigegeben'
),
beruehrt AS (
  SELECT DISTINCT f.ereignis_id, h.entity, h.pk
    FROM f
    JOIN v_historie h
      ON h.company_id = f.company_id
     AND (h.sub_process_id = f.sub_process_id
          OR (h.process_id = f.process_id AND h.sub_process_id IS NULL))
     AND h.action <> 'bestand'
     AND h.entity NOT LIKE 'gate%'
     AND h.entity NOT IN ('ref_anfragen','anfrage_prozesse','bc_zustellungen','ki_laufdaten')
     AND CASE WHEN f.datenstand IS NOT NULL THEN h.audit_id > f.datenstand
              ELSE h.at > f.entschieden_am END
),
netto AS (
  SELECT b.ereignis_id, b.entity,
         (SELECT CASE WHEN l.action = 'DELETE' THEN NULL ELSE l.neu END
            FROM audit_log l, f
           WHERE f.ereignis_id = b.ereignis_id
             AND l.entity = b.entity AND l.pk = b.pk
             AND CASE WHEN f.datenstand IS NOT NULL THEN l.audit_id <= f.datenstand
                      ELSE l.at <= f.entschieden_am END
           ORDER BY l.audit_id DESC LIMIT 1) AS damals,
         (SELECT CASE WHEN l.action = 'DELETE' THEN NULL ELSE l.neu END
            FROM audit_log l
           WHERE l.entity = b.entity AND l.pk = b.pk
           ORDER BY l.audit_id DESC LIMIT 1) AS jetzt
    FROM beruehrt b
),
verworfen AS (                    -- v3.19b: Erhebung der Freigabe verworfen
  SELECT f.ereignis_id, e.erhebung_id
    FROM f
    JOIN ref_erhebungen e
      ON e.company_id = f.company_id AND e.erhebung_id = f.bc0_stand
   WHERE e.status = 'verworfen'
),
zaehlung AS (
  SELECT f.company_id, f.sub_process_id, f.process_id, f.ereignis_id, f.entschieden_am,
         f.datenstand,
         count(n.entity) FILTER (WHERE n.damals IS DISTINCT FROM n.jetzt)      AS aenderungen,
         string_agg(DISTINCT n.entity, ', ' ORDER BY n.entity)
           FILTER (WHERE n.damals IS DISTINCT FROM n.jetzt)                    AS tabellen
    FROM f LEFT JOIN netto n ON n.ereignis_id = f.ereignis_id
   GROUP BY f.company_id, f.sub_process_id, f.process_id, f.ereignis_id, f.entschieden_am, f.datenstand
)
SELECT z.company_id, z.sub_process_id, z.process_id, z.ereignis_id, z.entschieden_am,
       z.datenstand,
       z.aenderungen,
       nullif(concat_ws(', ', z.tabellen,
                        CASE WHEN v.erhebung_id IS NOT NULL
                             THEN 'Erhebung ' || v.erhebung_id || ' verworfen' END), '')
                                                                   AS geaenderte_tabellen,
       (z.aenderungen > 0 OR v.erhebung_id IS NOT NULL)            AS veraltet,
       v.erhebung_id                                               AS erhebung_verworfen
  FROM zaehlung z LEFT JOIN verworfen v ON v.ereignis_id = z.ereignis_id;

COMMENT ON VIEW v_freigabe_datenstand IS
  'v3.17/v3.19b: je aktueller Freigabe die Nettoaenderungen an den BC0-Daten des Teilprozesses '
  '(und seines Kernprozesses) seit dem Datenstand der Freigabe. veraltet = t: Gate 0 neu '
  'entscheiden — auch wenn die Erhebung der Freigabe verworfen wurde (erhebung_verworfen). '
  'Ohne Gate-, Anfrage-, Zustell- und KI-Laufdaten.';

-- ---------------------------------------------------------------- A2 SOLL-Liste
CREATE OR REPLACE VIEW v_anfrage_teilprozesse AS
WITH bezuege AS (
  SELECT p.company_id, p.anfrage_id, p.process_id, p.rolle, p.zuordnung_quelle,
         coalesce(p.sub_process_id, t.sub_process_id) AS sub_process_id,
         (p.sub_process_id IS NULL) AS aus_kernprozess
    FROM anfrage_prozesse p
    LEFT JOIN ref_teilprozesse t
      ON p.sub_process_id IS NULL
     AND t.company_id = p.company_id AND t.process_id = p.process_id AND t.aktiv
     AND NOT teilprozess_unbenannt(t.sub_process_name)          -- v3.19b
)
SELECT DISTINCT ON (b.company_id, b.anfrage_id, b.sub_process_id)
       b.company_id, b.anfrage_id, b.process_id, b.sub_process_id, b.rolle,
       b.zuordnung_quelle, b.aus_kernprozess,
       coalesce(f.stand = 'freigegeben'
        AND CASE WHEN pr.profil_version IS NOT NULL
                 THEN f.bc1_profil_stand IS NOT DISTINCT FROM pr.profil_version::text
                 ELSE fp.anfrage_id IS NULL END
        AND NOT coalesce(d.veraltet, false), false)    AS freigegeben,
       f.ereignis_id                                   AS freigabe_ereignis_id,
       f.entschieden_am,
       EXISTS (SELECT 1 FROM gate_paket_inhalt i
                WHERE i.company_id = b.company_id AND i.anfrage_id = b.anfrage_id
                  AND i.sub_process_id = b.sub_process_id
                  AND i.freigabe_ereignis_id = f.ereignis_id) AS im_paket,
       f.bc1_profil_stand                              AS freigabe_bc1_stand,
       pr.profil_version                               AS anfrage_bc1_stand,
       coalesce(f.stand = 'freigegeben'
        AND NOT CASE WHEN pr.profil_version IS NOT NULL
                     THEN f.bc1_profil_stand IS NOT DISTINCT FROM pr.profil_version::text
                     ELSE fp.anfrage_id IS NULL END, false)   AS freigabe_veraltet,
       fp.anfrage_id                                   AS freigabe_bc1_anfrage,
       coalesce(d.veraltet, false)                     AS datenstand_veraltet
  FROM bezuege b
  LEFT JOIN v_gate_freigabe_aktuell f
    ON f.company_id = b.company_id AND f.sub_process_id = b.sub_process_id
  LEFT JOIN v_freigabe_datenstand d
    ON d.ereignis_id = f.ereignis_id
  LEFT JOIN LATERAL (
         SELECT w.profil_version
           FROM bc1.prozessprofil w
          WHERE w.company_id = b.company_id
            AND w.focus_step_id = b.sub_process_id
            AND w.anfrage_id = b.anfrage_id
            AND w.status = 'fertig'
          ORDER BY w.profil_version DESC
          LIMIT 1) pr ON TRUE
  LEFT JOIN LATERAL (
         SELECT w.anfrage_id
           FROM bc1.prozessprofil w
          WHERE w.company_id = b.company_id
            AND w.focus_step_id = b.sub_process_id
            AND w.profil_version::text = f.bc1_profil_stand
          LIMIT 1) fp ON TRUE
 WHERE b.sub_process_id IS NOT NULL
 ORDER BY b.company_id, b.anfrage_id, b.sub_process_id,
          (b.rolle = 'haupt') DESC, b.aus_kernprozess;

COMMENT ON VIEW v_anfrage_teilprozesse IS
  'Die SOLL-Liste je Anfrage, aufgeloest auf Teilprozesse (v3.19b: ohne unbenannte '
  'Teilprozesse eines zugeordneten Kernprozesses). freigegeben: die aktuelle '
  'Freigabe steht, beruht auf dem BC1-Profil DIESER Anfrage (v3.16) und ihr Datenstand '
  'ist unveraendert (v3.17, inkl. verworfener Erhebung v3.19b). freigabe_veraltet: anderes '
  'Profil. datenstand_veraltet: BC0-Daten geaendert oder Erhebung verworfen. Beides: Gate 0 neu entscheiden.';

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    GRANT SELECT ON v_freigabe_datenstand TO bc_leser;
  END IF;
END $$;

COMMIT;
