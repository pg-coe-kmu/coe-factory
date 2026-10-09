-- Schema v3.13 — Gate je Anfrage (08.10.2026)
--
-- Anlass: Review von PR #280 (BC1 B4, Dienst-Anmeldung an BC0). BC1 stoesst nach
-- jedem fertigen Profil `gate_nachziehen` an. Dabei fiel auf:
--
--   anfrage_am_gate_nachziehen() zaehlte ein fertiges BC1-Profil nur ueber
--   (company_id, focus_step_id). Die Anfrage spielte keine Rolle. Ein Teilprozess,
--   der aus einer FRUEHEREN Anfrage schon ein fertiges Profil hatte, galt auch fuer
--   eine NEUE Anfrage als fertig — die neue Anfrage konnte ans Gate springen, ohne
--   dass fuer sie interviewt wurde.
--
--   Seit BC1 B5 (05.10.2026) traegt bc1.prozessprofil die Spalte anfrage_id (aus der
--   Sitzung). Damit laesst sich das Profil der Anfrage zuordnen, fuer die es erhoben
--   wurde.
--
-- Aenderung (nur diese Funktion, keine Tabelle, keine Daten):
--   * Gezaehlt wird nur noch ein Profil MIT DERSELBEN anfrage_id.
--   * Profile ohne anfrage_id (vor B5 erhoben) zaehlen nicht mehr. Eine Anfrage, die
--     nur solche Profile hat, bleibt stehen und wird von Hand ans Gate gesetzt
--     (PUT .../anfragen/{id}/status). Das ist Absicht: lieber stehen bleiben als ein
--     Gate auf fremden Profilen.
--   * Fehlt die Spalte bc1.prozessprofil.anfrage_id (BC1 vor B5), aendert die
--     Funktion nichts und sagt es im Hinweis — wie bisher ohne bc1.prozessprofil.
--   * Signatur und Rueckgabe bleiben gleich: (p_company UUID, p_anfrage TEXT DEFAULT
--     NULL). Neu ist nur, dass die Anwendung p_anfrage jetzt auch weitergibt.
--
-- Ausfuehren als postgres, eine Transaktion. Gegenprobe:
-- pruefung_v3.13_gate_je_anfrage.sql (sieben Erwartungswerte).

BEGIN;

CREATE OR REPLACE FUNCTION anfrage_am_gate_nachziehen(
    p_company UUID, p_anfrage TEXT DEFAULT NULL)
RETURNS TABLE(anfrage_id TEXT, status_alt TEXT, status_neu TEXT, hinweis TEXT) AS $fn$
DECLARE
  v_hat_bc1     BOOLEAN := (to_regclass('bc1.prozessprofil') IS NOT NULL);
  v_hat_anfrage BOOLEAN := EXISTS (
      SELECT 1 FROM information_schema.columns
       WHERE table_schema = 'bc1' AND table_name = 'prozessprofil'
         AND column_name = 'anfrage_id');
BEGIN
  IF NOT v_hat_bc1 OR NOT v_hat_anfrage THEN
    RETURN QUERY
      SELECT a.anfrage_id, a.status, a.status,
             CASE WHEN NOT v_hat_bc1
                  THEN 'bc1.prozessprofil gibt es noch nicht — nichts nachzuziehen.'
                  ELSE 'bc1.prozessprofil hat keine Spalte anfrage_id (BC1 vor B5) — nichts nachzuziehen.'
             END::TEXT
        FROM ref_anfragen a
       WHERE a.company_id = p_company
         AND (p_anfrage IS NULL OR a.anfrage_id = p_anfrage)
         AND a.status IN ('zugeordnet','im_interview');
    RETURN;
  END IF;

  RETURN QUERY
  WITH kandidat AS (
    SELECT a.anfrage_id, a.status
      FROM ref_anfragen a
     WHERE a.company_id = p_company
       AND (p_anfrage IS NULL OR a.anfrage_id = p_anfrage)
       AND a.status IN ('zugeordnet','im_interview')
  ),
  stand AS (
    SELECT k.anfrage_id, k.status,
           count(*)                                            AS soll,
           count(*) FILTER (WHERE pr.stand = 'fertig')          AS fertig
      FROM kandidat k
      JOIN v_anfrage_teilprozesse t
        ON t.company_id = p_company AND t.anfrage_id = k.anfrage_id
      -- Gelesen wird bc1.prozessprofil — NICHT bc1.profil_write_status (bleibt
      -- allein bei bc1_role). v3.13: nur Profile DIESER Anfrage; je Teilprozess
      -- zaehlt die juengste Version.
      LEFT JOIN LATERAL (
             SELECT w.status AS stand
               FROM bc1.prozessprofil w
              WHERE w.company_id = p_company
                AND w.focus_step_id = t.sub_process_id
                AND w.anfrage_id = k.anfrage_id
              ORDER BY w.profil_version DESC
              LIMIT 1) pr ON TRUE
     GROUP BY k.anfrage_id, k.status
  ),
  gesetzt AS (
    UPDATE ref_anfragen a
       SET status = 'am_gate', status_seit = current_date
      FROM stand s
     WHERE a.company_id = p_company AND a.anfrage_id = s.anfrage_id
       AND s.soll > 0 AND s.fertig = s.soll
     RETURNING a.anfrage_id, s.status AS alt
  )
  SELECT s.anfrage_id, s.status,
         CASE WHEN g.anfrage_id IS NOT NULL THEN 'am_gate' ELSE s.status END,
         CASE WHEN g.anfrage_id IS NOT NULL
              THEN format('%s von %s Teilprozessen fertig — ans Gate.', s.fertig, s.soll)
              ELSE format('%s von %s Teilprozessen fertig — bleibt stehen.', s.fertig, s.soll)
         END::TEXT
    FROM stand s LEFT JOIN gesetzt g ON g.anfrage_id = s.anfrage_id;
END;
$fn$ LANGUAGE plpgsql;

COMMENT ON FUNCTION anfrage_am_gate_nachziehen(UUID, TEXT) IS
  'Setzt Anfragen auf am_gate, sobald ALLE ihre Teilprozesse ein fertiges '
  'BC1-Profil DIESER Anfrage haben (v3.13: Verknuepfung ueber anfrage_id). '
  'Kein Ruecksprung. Ohne bc1.prozessprofil oder ohne dessen Spalte anfrage_id '
  'ohne Wirkung. p_anfrage NULL = alle Anfragen des Mandanten.';

COMMIT;

-- Gegenprobe nach dem Einspielen:
--   SELECT obj_description('anfrage_am_gate_nachziehen(uuid,text)'::regprocedure);
--     -> beginnt mit 'Setzt Anfragen auf am_gate ... DIESER Anfrage (v3.13 ...'
--   SELECT * FROM anfrage_am_gate_nachziehen('<uuid>');   -- aendert nur, was fertig ist
