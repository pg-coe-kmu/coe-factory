-- Schema v3.18 — paket_id und anfrage_id fuer BC3 und BC4 (25.10.2026)
--
-- Anlass (Drehbuch S-169/S-170): BC3-Lieferungen und BC4-Laufdaten tragen nur
-- process_id/sub_process_id. Ob eine Lieferung zu einer Uebergabe gehoert, ist
-- nicht eindeutig (BC3-Testlieferungen vom 23.10. ohne Gate 0 und ohne BC2).
-- ADR-003/ADR-002: Die Reproduzierbarkeits-IDs werden vom Vorgaenger uebergeben
-- und unveraendert mitgeschrieben: company_id, anfrage_id (falls es eine Anfrage
-- gibt), paket_id, process_id, sub_process_id.
--
-- Aenderungen:
--   A. ki_laufdaten (gehoert BC0, BC4 schreibt hinein): Spalten paket_id und
--      anfrage_id, beide mit Fremdschluessel. Alte Zeilen bleiben NULL.
--      bc4_role hat INSERT auf die ganze Tabelle — die neuen Spalten sind
--      damit beschreibbar, kein weiteres Recht noetig.
--   B. bc3.lieferungen gehoert BC3 (bc3_role). Nach ADR-003 aendert BC0 dort nur
--      Rechte: REFERENCES auf gate_pakete und ref_anfragen, damit BC3 die
--      Fremdschluessel auf seiner Tabelle selbst setzt (Vorbild v3.14).
--      Den Befehl fuer BC3 siehe Ende der Datei.
--
-- Ausfuehren als postgres, eine Transaktion. Gegenprobe:
-- pruefung_v3.17_v3.18.sql

BEGIN;

-- A. ki_laufdaten
ALTER TABLE ki_laufdaten ADD COLUMN IF NOT EXISTS paket_id   UUID;
ALTER TABLE ki_laufdaten ADD COLUMN IF NOT EXISTS anfrage_id TEXT;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ki_laufdaten_paket') THEN
    ALTER TABLE ki_laufdaten ADD CONSTRAINT fk_ki_laufdaten_paket
      FOREIGN KEY (company_id, paket_id) REFERENCES gate_pakete(company_id, paket_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ki_laufdaten_anfrage') THEN
    ALTER TABLE ki_laufdaten ADD CONSTRAINT fk_ki_laufdaten_anfrage
      FOREIGN KEY (company_id, anfrage_id) REFERENCES ref_anfragen(company_id, anfrage_id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ki_laufdaten_paket ON ki_laufdaten(company_id, paket_id);

COMMENT ON COLUMN ki_laufdaten.paket_id IS
  'v3.18: Paket der Uebergabe (gate_pakete), vom Vorgaenger uebernommen. NULL = vor v3.18 '
  'oder kein Bezug zu einer Uebergabe (z. B. Betrieb ohne Prozessbezug).';
COMMENT ON COLUMN ki_laufdaten.anfrage_id IS
  'v3.18: Anfrage, falls die Uebergabe aus einer Anfrage kam. Ohne Anfrage (Portfolio) NULL.';

-- B. Recht fuer BC3
GRANT REFERENCES ON gate_pakete  TO bc3_role;
GRANT REFERENCES ON ref_anfragen TO bc3_role;

COMMIT;

-- ----------------------------------------------------------------------------
-- BEFEHL FUER BC3 (fuehrt BC3 als bc3_role auf der eigenen Tabelle aus):
--
--   ALTER TABLE bc3.lieferungen
--     ADD COLUMN IF NOT EXISTS paket_id   UUID,
--     ADD COLUMN IF NOT EXISTS anfrage_id TEXT;
--   ALTER TABLE bc3.lieferungen
--     ADD CONSTRAINT fk_lieferung_paket
--       FOREIGN KEY (company_id, paket_id)   REFERENCES public.gate_pakete(company_id, paket_id),
--     ADD CONSTRAINT fk_lieferung_anfrage
--       FOREIGN KEY (company_id, anfrage_id) REFERENCES public.ref_anfragen(company_id, anfrage_id);
--
-- Danach schreiben BC3 und BC4 bei jeder Lieferung bzw. jedem Lauf paket_id und
-- (falls vorhanden) anfrage_id mit — so, wie sie von BC2 bzw. BC3 kommen.
-- ----------------------------------------------------------------------------
