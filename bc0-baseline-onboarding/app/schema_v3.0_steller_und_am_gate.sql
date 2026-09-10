-- Schema v3.0 — Wer hat die Anfrage gestellt, und wann geht sie ans Gate (07.09.2026)
--
-- Zwei Befunde aus Richards Brief vom 03.09.2026, Abschnitt 5, beide am 07.09.
-- am Quelltext nachgeprueft:
--
-- (1) "Wer ist der Interviewpartner — und wie bekommen wir seine P-ID?"
--     Die Anfragemaske verlangt eine Anmeldung (POST .../anfragen haengt an
--     Depends(angemeldeter_benutzer)). Die Anmeldung wird geprueft — und dann
--     vergessen: `ref_anfragen` speichert den Benutzer nicht. Wer die Anfrage
--     gestellt hat, ist hinterher nur bekannt, wenn jemand `steller_id` von Hand
--     ausgefuellt hat, und die ist optional.
--     Und selbst dann fehlte der zweite Schritt: `app_benutzer` (ein Konto) und
--     `ref_personen` (eine Person mit P-ID) sind zwei getrennte Welten. Das ist
--     der offene Punkt 64.
--     Simeon am 07.09.: "Eigentlich sollte das mit der Anfragemaske — E-Mail und
--     Passwort, damit ist die klare Zuordnung doch gegeben." Richtig gedacht,
--     nur nicht gebaut. Hier wird es gebaut.
--
-- (2) "Darf BC1 nach Abschluss des Profils auch am_gate setzen?"
--     Befund: `am_gate` steht seit v2.2 in der Wertemenge — und **keine Zeile
--     Code setzt ihn.** Weder die Anwendung noch eine Funktion; der einzige Weg
--     ist PUT .../status von Hand, und gate_paket_schnueren() springt am Ende
--     direkt auf `uebergeben`.
--     Simeon am 07.09.: "Wenn er abgeschlossen hat, sollte es automatisch ins
--     Gate 0 zur Freigabe HitL gehen." Damit erledigt sich Richards Frage: BC1
--     muss es nicht setzen duerfen, weil BC0 es selbst nachzieht.
--
-- Rein additiv. Keine Spalte wird entfernt, keine Regel gelockert.
-- Ausfuehren: als Eigentuemer, in einer Transaktion.

BEGIN;

-- ---------------------------------------------------------------------------
-- Teil A — Wer hat die Anfrage gestellt
-- ---------------------------------------------------------------------------

-- A1. Das Konto an der Anfrage. Nicht Ersatz fuer `steller_id`, sondern die
--     Rueckfallebene: `steller_id` sagt, WER GEMEINT ist (auch wenn ein Dritter
--     die Maske bedient hat), `angelegt_von` sagt, WER SIE ABGESCHICKT hat.
--     Beides kann auseinanderfallen, deshalb zwei Spalten.
ALTER TABLE ref_anfragen
  ADD COLUMN IF NOT EXISTS angelegt_von TEXT;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_anfrage_angelegt_von') THEN
    ALTER TABLE ref_anfragen ADD CONSTRAINT fk_anfrage_angelegt_von
      FOREIGN KEY (angelegt_von) REFERENCES app_benutzer(benutzer_id) ON DELETE SET NULL;
  END IF;
END $$;

COMMENT ON COLUMN ref_anfragen.angelegt_von IS
  'Konto, das die Anfrage in der Maske abgeschickt hat (app_benutzer). '
  'NULL bei Anfragen aus der Zeit vor v3.0 und bei Eingang ueber andere Wege.';

-- A2. Konto <-> Person, je Mandant. Das ist Punkt 64.
--     Warum an `app_benutzer_mandanten` und nicht an `app_benutzer`: Ein Konto
--     kann mehreren Mandanten zugeordnet sein, `ref_personen` ist je Mandant.
--     Dieselbe Person hat bei zwei Mandanten zwei P-IDs.
--     MATCH SIMPLE: ist `person_id` NULL, greift der Fremdschluessel nicht —
--     genau wie bei ref_personen.rolle_id. Die Zuordnung ist optional und wird
--     nachgetragen, nicht erzwungen.
ALTER TABLE app_benutzer_mandanten
  ADD COLUMN IF NOT EXISTS person_id TEXT;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_konto_person') THEN
    ALTER TABLE app_benutzer_mandanten ADD CONSTRAINT fk_konto_person
      FOREIGN KEY (company_id, person_id) REFERENCES ref_personen(company_id, person_id)
      ON DELETE SET NULL;
  END IF;
END $$;

COMMENT ON COLUMN app_benutzer_mandanten.person_id IS
  'P-ID dieses Kontos bei diesem Mandanten (ref_personen). Optional; '
  'ohne sie ist das Konto eine Anmeldung, aber keine benannte Person.';

-- A3. Die Aufloesung, die BC1 braucht. Eine Sicht, kein zweiter Speicherort.
--     Reihenfolge: was ausdruecklich an der Anfrage steht, schlaegt das Konto.
--     `herkunft` sagt, worauf die P-ID beruht — vier Spalten je Wert (ADR-005 R2)
--     stehen an der Anfrage selbst; hier zaehlt nur, dass die Herkunft sichtbar
--     ist und nicht geraten wird.
CREATE OR REPLACE VIEW v_anfrage_steller AS
SELECT a.company_id,
       a.anfrage_id,
       a.steller_id                          AS steller_formular,
       a.angelegt_von                        AS konto_id,
       m.person_id                           AS steller_konto,
       coalesce(a.steller_id, m.person_id)   AS person_id,
       CASE WHEN a.steller_id IS NOT NULL THEN 'formular'
            WHEN m.person_id  IS NOT NULL THEN 'konto'
            ELSE 'unbekannt' END             AS herkunft,
       p.name                                AS person_name,
       p.funktion                            AS person_funktion
  FROM ref_anfragen a
  LEFT JOIN app_benutzer_mandanten m
    ON m.benutzer_id = a.angelegt_von AND m.company_id = a.company_id
  LEFT JOIN ref_personen p
    ON p.company_id = a.company_id
   AND p.person_id  = coalesce(a.steller_id, m.person_id);

COMMENT ON VIEW v_anfrage_steller IS
  'Wer hinter einer Anfrage steht: ausdruecklich gesetzte steller_id, sonst die '
  'Person des abschickenden Kontos. `herkunft` = formular | konto | unbekannt. '
  'Fuer BC1: Ansprache im Interview und Quelle der Interviewangaben im Profil.';

-- ---------------------------------------------------------------------------
-- Teil B — Die Anfrage geht von selbst ans Gate
-- ---------------------------------------------------------------------------

-- B1. Nachziehen des Status auf `am_gate`.
--
--     Bedingung: ALLE Teilprozesse der Anfrage tragen ein abgeschlossenes
--     BC1-Profil. Dieselbe Vollstaendigkeitsregel wie bei der Uebergabe aus
--     v2.7 ("uebergeben wird nur vollstaendig") — ein Gate-Bogen auf einem
--     Ausschnitt waere derselbe Fehler wie ein ROI auf einem Ausschnitt.
--
--     Kein Ruecksprung: nur aus `zugeordnet` und `im_interview` heraus.
--     `am_gate`, `uebergeben`, `bewertet`, `beauftragt`, `erledigt` und
--     `abgelehnt` bleiben unberuehrt.
--
--     Solange BC1 nicht eingespielt hat, gibt es bc1.prozessprofil nicht.
--     to_regclass() faengt das ab: die Funktion laeuft, tut nichts und sagt es.
--     Deshalb ist sie schon heute einspielbar und faengt von selbst an zu
--     arbeiten, sobald Richards Tabelle steht.
CREATE OR REPLACE FUNCTION anfrage_am_gate_nachziehen(
    p_company UUID, p_anfrage TEXT DEFAULT NULL)
RETURNS TABLE(anfrage_id TEXT, status_alt TEXT, status_neu TEXT, hinweis TEXT) AS $fn$
DECLARE
  v_hat_bc1 BOOLEAN := (to_regclass('bc1.prozessprofil') IS NOT NULL);
BEGIN
  IF NOT v_hat_bc1 THEN
    RETURN QUERY
      SELECT a.anfrage_id, a.status, a.status,
             'bc1.prozessprofil gibt es noch nicht — nichts nachzuziehen.'::TEXT
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
      -- Gelesen wird bc1.prozessprofil — NICHT bc1.profil_write_status:
      -- die bleibt laut Richard (03.09.) allein bei bc1_role, bc_leser hat
      -- darauf kein Recht. Die Felder stammen aus der Vereinbarung vom
      -- 22.08.2026: Identitaet (company_id, focus_step_id, profil_version),
      -- Statusfeld in_erhebung | fertig. **Die genauen Spaltennamen sind vor
      -- dem Einspielen bei BC1 zu bestaetigen** — sie stehen in keinem Papier,
      -- nur in seinem Schema. Steht die Tabelle anders, aendert sich hier
      -- genau dieser Block.
      LEFT JOIN LATERAL (
             SELECT w.status AS stand
               FROM bc1.prozessprofil w
              WHERE w.company_id = p_company
                AND w.focus_step_id = t.sub_process_id
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
  'BC1-Profil haben. Kein Ruecksprung. Ohne bc1.prozessprofil ohne Wirkung. '
  'Damit muss BC1 den Status nicht selbst setzen (Richards Frage vom 03.09.).';

COMMIT;

-- Gegenprobe nach dem Einspielen:
--   \d ref_anfragen                       -> Spalte angelegt_von
--   \d app_benutzer_mandanten             -> Spalte person_id
--   SELECT * FROM v_anfrage_steller WHERE company_id = '<uuid>';
--   SELECT * FROM anfrage_am_gate_nachziehen('<uuid>');
