-- Schema v3.17 — Datenstand je Freigabe, eindeutige Prozessnamen (25.10.2026)
--
-- Anlass (Drehbuch S-170/S-171): Eine Freigabe merkt sich bisher die Erhebung
-- (nur Bitkom-Bewertungen) und seit v3.3.2 die BC1-Profilversion. Aendert sich
-- danach etwas an den uebrigen BC0-Daten des Teilprozesses — Name, Werkzeuge,
-- Eigner, Rollen, Bewertungen —, merkt die Freigabe das nicht. Das gilt vor
-- allem fuer den Weg OHNE Anfrage (Portfolio, Daten direkt aus der PWA, ohne BC1).
--
-- Grundsaetze (Simeon, 25.10.2026):
--   * Keine Anfrage, kein BC1-Interview.
--   * Jeden Prozess gibt es je Mandant nur einmal. Eine zweite Anfrage verweist
--     auf den bestehenden Teilprozess; es entsteht kein zweiter.
--   * Die Erhebungs-ID bleibt der Bitkom-Messzeitpunkt (ADR-004). Fuer "Stand aller
--     Daten" gibt es eine eigene Kennung: den DATENSTAND.
--
-- Aenderungen:
--   A. gate_ereignisse.datenstand (BIGINT): die hoechste audit_id zum Zeitpunkt der
--      Entscheidung. Setzt ein Trigger — die Anwendung muss nichts tun.
--      Reproduzierbar ueber stand_zum() bzw. audit_log bis zu dieser Nummer.
--   B. Freigabe nur fuer benannte Teilprozesse: "Teilprozess N" gilt als noch nicht
--      benannt und kann an Gate 0 nicht freigegeben werden (Trigger, wie A).
--   C. Sicht v_freigabe_datenstand: je aktueller Freigabe, wie viele Zeilen des
--      Teilprozesses (und seines Kernprozesses ohne Teilprozessbezug) sich SEITHER
--      TATSAECHLICH geaendert haben. Gezaehlt wird die Nettoaenderung je Zeile:
--      Loeschen und identisch neu Anlegen (Speichern ohne Aenderung) zaehlt nicht.
--      Nicht gezaehlt: Gate-, Anfrage-, Zustell- und KI-Laufdaten — das ist
--      Buchfuehrung, keine Aenderung am Prozess. Freigaben vor v3.17 (datenstand
--      NULL) werden ueber den Zeitpunkt der Entscheidung verglichen.
--   D. v_anfrage_teilprozesse (Weg Anfrage) und v_uebergabe_kandidaten (Weg
--      Portfolio): eine Freigabe mit Datenstand-Aenderung zaehlt nicht mehr.
--      Spalten bleiben, je eine kommt hinten dazu.
--   E. Eindeutige Namen je Mandant (aktiv, ohne Gross/Klein, ohne Rand-Leerzeichen)
--      fuer Kern- und Teilprozesse; Platzhalter "Teilprozess N" ausgenommen.
--
-- Vorpruefung 25.10.2026: keine doppelten echten Namen (V2/V3 = 0), aktiv boolean.
-- Setzt v3.16 voraus. Ausfuehren als postgres, eine Transaktion.
-- Gegenprobe: pruefung_v3.17_datenstand_und_namen.sql

BEGIN;

DO $$
BEGIN
  IF obj_description('v_anfrage_teilprozesse'::regclass) NOT LIKE '%v3.16%' THEN
    RAISE EXCEPTION 'v3.16 ist nicht eingespielt — erst schema_v3.16_freigabe_datenstand.sql.';
  END IF;
END $$;

-- ---------------------------------------------------------------- A + B
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS datenstand BIGINT;
COMMENT ON COLUMN gate_ereignisse.datenstand IS
  'v3.17: hoechste audit_id zum Zeitpunkt der Entscheidung — der Stand ALLER BC0-Daten, '
  'auf dem sie beruht. Gesetzt vom Trigger gate_datenstand. NULL = vor v3.17.';

CREATE OR REPLACE FUNCTION teilprozess_unbenannt(p_name TEXT) RETURNS BOOLEAN AS $fn$
  SELECT p_name IS NULL OR btrim(p_name) = ''
         OR btrim(p_name) ~* '^teilprozess[[:space:]]+[0-9]+$';
$fn$ LANGUAGE sql IMMUTABLE;

CREATE OR REPLACE FUNCTION trg_gate_datenstand() RETURNS TRIGGER AS $fn$
DECLARE v_name TEXT;
BEGIN
  IF NEW.gate = 'bc0-bc2' AND NEW.objekt_typ = 'teilprozess' AND NEW.ereignis = 'freigegeben' THEN
    SELECT sub_process_name INTO v_name FROM ref_teilprozesse
     WHERE company_id = NEW.company_id AND sub_process_id = NEW.objekt_id;
    IF teilprozess_unbenannt(v_name) THEN
      RAISE EXCEPTION 'Teilprozess % ist noch nicht benannt ("%"). Freigabe erst mit eindeutigem Namen.',
                      NEW.objekt_id, coalesce(v_name, '')
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  IF NEW.datenstand IS NULL THEN
    NEW.datenstand := (SELECT max(audit_id) FROM audit_log);
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS gate_datenstand ON gate_ereignisse;
CREATE TRIGGER gate_datenstand BEFORE INSERT ON gate_ereignisse
  FOR EACH ROW EXECUTE FUNCTION trg_gate_datenstand();

-- ---------------------------------------------------------------- C
CREATE OR REPLACE VIEW v_freigabe_datenstand AS
WITH f AS (
  SELECT a.company_id, a.sub_process_id, a.process_id, a.ereignis_id, a.entschieden_am,
         g.datenstand
    FROM v_gate_freigabe_aktuell a
    JOIN gate_ereignisse g ON g.ereignis_id = a.ereignis_id
   WHERE a.stand = 'freigegeben'
),
beruehrt AS (                     -- jede Zeile, die seit der Freigabe angefasst wurde
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
netto AS (                        -- Zeilenbild damals gegen Zeilenbild jetzt
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
)
SELECT f.company_id, f.sub_process_id, f.process_id, f.ereignis_id, f.entschieden_am,
       f.datenstand,
       count(n.entity) FILTER (WHERE n.damals IS DISTINCT FROM n.jetzt)      AS aenderungen,
       string_agg(DISTINCT n.entity, ', ' ORDER BY n.entity)
         FILTER (WHERE n.damals IS DISTINCT FROM n.jetzt)                    AS geaenderte_tabellen,
       coalesce(count(n.entity) FILTER (WHERE n.damals IS DISTINCT FROM n.jetzt) > 0, false)
                                                                             AS veraltet
  FROM f LEFT JOIN netto n ON n.ereignis_id = f.ereignis_id
 GROUP BY f.company_id, f.sub_process_id, f.process_id, f.ereignis_id, f.entschieden_am, f.datenstand;

COMMENT ON VIEW v_freigabe_datenstand IS
  'v3.17: je aktueller Freigabe die Nettoaenderungen an den BC0-Daten des Teilprozesses '
  '(und seines Kernprozesses) seit dem Datenstand der Freigabe. veraltet = t: Gate 0 neu '
  'entscheiden. Ohne Gate-, Anfrage-, Zustell- und KI-Laufdaten.';

-- ---------------------------------------------------------------- D
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
       -- v3.17: neu, hinten angehaengt
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
  'Die SOLL-Liste je Anfrage, aufgeloest auf Teilprozesse. freigegeben: die aktuelle '
  'Freigabe steht, beruht auf dem BC1-Profil DIESER Anfrage (v3.16) und ihr Datenstand '
  'ist unveraendert (v3.17). freigabe_veraltet: anderes Profil. datenstand_veraltet: '
  'BC0-Daten seit der Freigabe geaendert. Beides: Gate 0 neu entscheiden.';

CREATE OR REPLACE VIEW v_uebergabe_kandidaten AS
SELECT f.company_id, f.sub_process_id, f.process_id, f.ereignis_id AS freigabe_ereignis_id,
       f.entschieden_am, f.anfrage_id, f.bc0_stand, f.bc1_profil_stand, f.hinweis_an_bc2,
       -- v3.17: neu, hinten angehaengt (hier immer false — veraltete fallen heraus)
       coalesce(d.veraltet, false) AS datenstand_veraltet
  FROM v_gate_freigabe_aktuell f
  LEFT JOIN v_freigabe_datenstand d ON d.ereignis_id = f.ereignis_id
 WHERE f.stand = 'freigegeben'
   AND NOT coalesce(d.veraltet, false)
   AND NOT EXISTS (SELECT 1 FROM gate_paket_inhalt i
                    WHERE i.company_id = f.company_id AND i.freigabe_ereignis_id = f.ereignis_id);
COMMENT ON VIEW v_uebergabe_kandidaten IS
  'Freigegebene Teilprozesse, deren aktuelle Freigabe noch in keinem Paket steckt und '
  'deren Datenstand unveraendert ist (v3.17): Vorschau vor dem Knopf, Nachzuegler, Portfolio-Weg.';

-- ---------------------------------------------------------------- E
CREATE UNIQUE INDEX IF NOT EXISTS ux_teilprozess_name_je_mandant
  ON ref_teilprozesse (company_id, lower(btrim(sub_process_name)))
  WHERE aktiv AND NOT teilprozess_unbenannt(sub_process_name);
COMMENT ON INDEX ux_teilprozess_name_je_mandant IS
  'v3.17: Jeden Teilprozess gibt es je Mandant nur einmal (aktiv, Name ohne Gross/Klein '
  'und Rand-Leerzeichen). Platzhalter "Teilprozess N" ausgenommen.';

CREATE UNIQUE INDEX IF NOT EXISTS ux_prozess_name_je_mandant
  ON ref_prozesse (company_id, lower(btrim(process_name)))
  WHERE aktiv AND process_name IS NOT NULL AND btrim(process_name) <> '';
COMMENT ON INDEX ux_prozess_name_je_mandant IS
  'v3.17: Jeden Kernprozess gibt es je Mandant nur einmal (aktiv, Name ohne Gross/Klein '
  'und Rand-Leerzeichen).';

-- Rechte: BC2 und Leser lesen die neue Sicht wie v_gate_freigabe_aktuell
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    GRANT SELECT ON v_freigabe_datenstand TO bc_leser;
  END IF;
END $$;

COMMIT;
