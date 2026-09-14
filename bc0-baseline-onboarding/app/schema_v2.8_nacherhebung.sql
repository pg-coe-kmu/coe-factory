-- Schema v2.8 — Nacherhebung: mehrere Erhebungen je Monat (04.09.2026)
--
-- Befund vom Ausrollen v2.6: `abgeschlossen` ist seit v2.6 eine echte Sperre
-- (Trigger erhebung_eingefroren) — und die Kennung E-JJJJ-MM erlaubt genau eine
-- Erhebung je Monat. Wer am 4. abschliesst, kann bis zum 1. des Folgemonats auf
-- diesem Mandanten nichts mehr bewerten. Vor v2.6 war das harmlos, weil die
-- Sperre nicht griff; jetzt ist es ein Betriebsproblem.
--
-- Regel (Simeon, 04.09.): dieselbe wie beim Paket — alt bleibt, neu kommt dazu.
--   1. E-JJJJ-MM bleibt die erste Erhebung im Monat; weitere heissen
--      E-JJJJ-MM-2, E-JJJJ-MM-3 …
--   2. Eine Bewertung nach dem Abschluss legt automatisch die naechste Erhebung
--      an ("Nacherhebung") — kein Fehler mehr. Die abgeschlossene bleibt, wie
--      sie war: DAS ist die Sperre. (App: _erhebung_offen)
--   3. Abschliessen bleibt eine bewusste Handlung von BC0 (Admin) — Knopf im
--      Self-Rating-Reiter. Nicht gekoppelt an das Paket: ein Paket betrifft
--      eine Anfrage, eine Erhebung den ganzen Mandanten.
--   4. Nur Bewertungen und Belege haengen an einer Erhebung. Stammdaten
--      (Prozesse, Personen, Systeme, Rollen) brauchen keine — sie stehen in der
--      Historie (v2.6), v_stand_veraltet zeigt BC2 die Bewegung seit dem Paket.
--
-- Was "gilt": je Item der juengste Wert ueber alle nicht verworfenen
-- Erhebungen (unveraendert seit v1.3). Ab dem Paket gilt fuer BC2 der Stand zum
-- Paketdatum (stand_zum), nicht die Erhebung.
--
-- Dieses Blatt aendert nur die Kennungsregel und liefert die Funktion fuer die
-- naechste Kennung. Es ist wiederholbar.

BEGIN;

-- ============================================================
-- 1. KENNUNG: E-JJJJ-MM oder E-JJJJ-MM-N (N >= 2)
-- ============================================================
ALTER TABLE ref_erhebungen DROP CONSTRAINT IF EXISTS ref_erhebungen_erhebung_id_check;
ALTER TABLE ref_erhebungen ADD CONSTRAINT ref_erhebungen_erhebung_id_check
  CHECK (erhebung_id ~ '^E-[0-9]{4}-[0-9]{2}(-[2-9]|-[1-9][0-9]+)?$');

COMMENT ON COLUMN ref_erhebungen.erhebung_id IS
  'E-JJJJ-MM fuer die erste Erhebung des Monats, E-JJJJ-MM-2, -3 … fuer weitere '
  '(v2.8). Monat = Monat der Anlage, nicht der Erhebungszeitraum. Eine '
  'abgeschlossene Erhebung nimmt keine Bewertung mehr an (v2.6); die naechste '
  'Bewertung legt die naechste Kennung an (App).';

-- ============================================================
-- 2. NAECHSTE KENNUNG — eine Stelle fuer die Regel
-- ============================================================
CREATE OR REPLACE FUNCTION erhebung_naechste_kennung(p_company UUID, p_datum DATE DEFAULT current_date)
RETURNS TEXT AS $fn$
DECLARE
  v_basis TEXT := 'E-' || to_char(p_datum, 'YYYY-MM');
  v_max   INTEGER;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM ref_erhebungen WHERE company_id = p_company AND erhebung_id = v_basis) THEN
    RETURN v_basis;
  END IF;
  SELECT coalesce(max(substr(erhebung_id, length(v_basis) + 2)::integer), 1) INTO v_max
    FROM ref_erhebungen
   WHERE company_id = p_company
     AND erhebung_id LIKE v_basis || '-%';
  RETURN v_basis || '-' || (v_max + 1)::text;
END;
$fn$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION erhebung_naechste_kennung(UUID, DATE) IS
  'Die naechste freie Erhebungskennung des Mandanten fuer den Monat von p_datum: '
  'E-JJJJ-MM, wenn es sie noch nicht gibt, sonst E-JJJJ-MM-N mit N = hoechste '
  'vorhandene Nummer + 1 (verworfene zaehlen mit — eine Kennung wird nie neu '
  'vergeben). Die App nutzt dieselbe Regel im SQLite-Betrieb.';

GRANT EXECUTE ON FUNCTION erhebung_naechste_kennung(UUID, DATE) TO bc_leser;

COMMIT;

-- Kontrolle:
--   SELECT erhebung_naechste_kennung(company_id) FROM companies;   -- je Mandant
--   SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ref_erhebungen_erhebung_id_check';
