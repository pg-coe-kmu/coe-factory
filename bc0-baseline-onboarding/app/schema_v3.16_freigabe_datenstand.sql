-- Schema v3.16 — Freigabe gilt nur fuer das BC1-Profil der Anfrage (25.10.2026)
--
-- Anlass (Drehbuch S-170): A-2026-05 (KP-05.TP-1) stand "uebergabefaehig", ohne
-- dass fuer sie entschieden wurde. Die Freigabe vom 18.09. (Ereignis 4, ohne
-- Anfrage, bc1_profil_stand NULL) galt weiter, obwohl BC1 am 25.10. fuer
-- A-2026-05 ein neues Profil (Version 3) geschrieben hat — unter derselben
-- Erhebung E-2026-08. Die Erhebungs-ID erkennt das nicht.
--
-- Der Fall: Eine ZWEITE Anfrage trifft einen Teilprozess, der schon freigegeben
-- ist. Je Anfrage gibt es genau ein Interview und damit ein eigenes Profil. Die
-- alte Freigabe beruht auf einem anderen Profil und darf nicht mitzaehlen.
--
-- Regel (nur Weg 1 "Anfrage" in gate_paket_schnueren):
--   * Hat die Anfrage ein fertiges BC1-Profil (bc1.prozessprofil.anfrage_id =
--     diese Anfrage), zaehlt die Freigabe nur, wenn ihr bc1_profil_stand gleich
--     der Version dieses Profils ist. Sonst: freigabe_veraltet = true, Gate 0
--     neu entscheiden.
--   * Hat die Anfrage kein eigenes Profil (Altfaelle vor BC1 B5, z. B. A-2026-02),
--     zaehlt die Freigabe nur, wenn sie NICHT auf dem Profil einer anderen Anfrage
--     beruht (sonst wuerde eine Freigabe fuer A-2026-05 auch A-2026-02 neu oeffnen).
--   * Freigabe bleibt je Teilprozess, anfrage_id bleibt optional.
--   * Weg 2 "Portfolio" (ganze Kern-/Teilprozesse ohne Anfrage, Daten direkt aus
--     der PWA, ohne BC1) liest v_uebergabe_kandidaten und ist NICHT betroffen.
--
-- Aenderung: nur die Sicht v_anfrage_teilprozesse. Bestehende Spalten bleiben in
-- Name und Reihenfolge; vier Spalten kommen hinten dazu. Keine Tabelle, keine
-- Daten. v_anfrage_uebergabe_stand und gate_paket_schnueren lesen die Spalte
-- "freigegeben" und folgen damit ohne eigene Aenderung.
--
-- Ausfuehren als postgres, eine Transaktion. Gegenprobe:
-- pruefung_v3.16_freigabe_datenstand.sql

BEGIN;

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
       -- freigegeben: Freigabe steht UND ihr BC1-Profil passt zur Anfrage.
       --   Anfrage mit eigenem Profil  -> Freigabe auf genau diesem Profil.
       --   Anfrage ohne eigenes Profil -> Freigabe auf keinem Profil einer ANDEREN
       --                                  Anfrage (Altfaelle wie A-2026-02).
       coalesce(f.stand = 'freigegeben'
        AND CASE WHEN pr.profil_version IS NOT NULL
                 THEN f.bc1_profil_stand IS NOT DISTINCT FROM pr.profil_version::text
                 ELSE fp.anfrage_id IS NULL END, false)       AS freigegeben,
       f.ereignis_id                                   AS freigabe_ereignis_id,
       f.entschieden_am,
       EXISTS (SELECT 1 FROM gate_paket_inhalt i
                WHERE i.company_id = b.company_id AND i.anfrage_id = b.anfrage_id
                  AND i.sub_process_id = b.sub_process_id
                  AND i.freigabe_ereignis_id = f.ereignis_id) AS im_paket,
       -- v3.16: neu, hinten angehaengt
       f.bc1_profil_stand                              AS freigabe_bc1_stand,
       pr.profil_version                               AS anfrage_bc1_stand,
       coalesce(f.stand = 'freigegeben'
        AND NOT CASE WHEN pr.profil_version IS NOT NULL
                     THEN f.bc1_profil_stand IS NOT DISTINCT FROM pr.profil_version::text
                     ELSE fp.anfrage_id IS NULL END, false)   AS freigabe_veraltet,
       fp.anfrage_id                                   AS freigabe_bc1_anfrage
  FROM bezuege b
  LEFT JOIN v_gate_freigabe_aktuell f
    ON f.company_id = b.company_id AND f.sub_process_id = b.sub_process_id
  LEFT JOIN LATERAL (
         SELECT w.profil_version
           FROM bc1.prozessprofil w
          WHERE w.company_id = b.company_id
            AND w.focus_step_id = b.sub_process_id
            AND w.anfrage_id = b.anfrage_id
            AND w.status = 'fertig'
          ORDER BY w.profil_version DESC
          LIMIT 1) pr ON TRUE
  -- Das Profil, auf dem die Freigabe beruht, und fuer welche Anfrage es erhoben wurde
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
  'Die SOLL-Liste je Anfrage, aufgeloest auf Teilprozesse. freigegeben: die '
  'aktuelle Freigabe des Teilprozesses steht UND beruht auf dem BC1-Profil DIESER '
  'Anfrage (v3.16; ohne eigenes Profil wie bisher). freigabe_veraltet: freigegeben, '
  'aber auf einem anderen Profil — Gate 0 neu entscheiden. im_paket: liegt schon '
  'in einem Paket dieser Anfrage.';

COMMIT;
