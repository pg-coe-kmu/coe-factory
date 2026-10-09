-- ============================================================
-- BC2 · Migration bc2.2 — Lauf, Ergebnis und Gate-1-Entscheidung
-- Ticket #290 · Entwurf #250 (ADR-008 · BC2) · Karte #158 · Stand 09.10.2026
-- ============================================================
--
-- Holt die Gate-1-Entscheidung aus dem Arbeitsspeicher. Seit #243 lag sie
-- dort und war nach jedem Neustart weg — an ihr hängt die ganze Lieferung an
-- BC3. Dazu kommt der Ort, an dem sie hängen kann: der Lauf selbst, seine
-- Konzepte und Potenziale.
--
-- Ausführen mit der BC2-Rolle, wie bc2.1 (ADR-003: CREATE nur auf `bc2`):
--
--     psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migration_bc2.2_lauf.sql
--
-- Setzt bc2.1 voraus (Schema `bc2` und `bc2.eingang`). Wiederholbar: Tabellen
-- und Indizes mit IF NOT EXISTS, Funktionen und Sicht mit OR REPLACE, Trigger
-- mit DROP … IF EXISTS davor.
--
-- **Wo die Regeln liegen.** Alles, was zwei gleichzeitige Schreiber nicht
-- überholen dürfen, steht hier und nicht im Python — dieselbe Lehre wie beim
-- Briefkasten (#190): Fassungsvergabe (UNIQUE), höchstens ein offener Lauf je
-- Paket (partieller Index), ein unveränderliches Ergebnis und eine endgültige
-- Gate-1-Entscheidung (Trigger). Der Doppelgänger im Arbeitsspeicher ahmt das
-- nach; die Garantie gibt nur diese Datei, geprüft in
-- tests/test_vertrag_postgres.py.

-- ------------------------------------------------------------
-- bc2.lauf — ein Analyselauf ist (paket_id, fassung)  (ADR-008 · BC2, 2.1)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bc2.lauf (
  priorisierung_id  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Als Werte, nicht als Fremdschlüssel nach `public` (ADR-008 · BC2, 2.7).
  -- `text` wie in bc2.eingang, aus demselben Grund (#190).
  company_id        text        NOT NULL,
  paket_id          text        NOT NULL,
  uebergeben_am     timestamptz NOT NULL,

  fassung           integer     NOT NULL CHECK (fassung >= 1),

  -- in_arbeit     gerechnet wird; noch kein Ergebnis
  -- offen         Ergebnis liegt, Gate 1 steht aus (auch: Entwurf `pending`)
  -- abgeschlossen Gate 1 hat `approved` oder `rejected` entschieden
  -- fehler        technisch gescheitert — **keine Fassung**: der Neuversuch
  --               läuft unter derselben Nummer (ADR-008 · BC2, 2.1)
  zustand           text        NOT NULL DEFAULT 'in_arbeit'
                                CHECK (zustand IN ('in_arbeit', 'offen', 'abgeschlossen', 'fehler')),

  begonnen_am       timestamptz NOT NULL DEFAULT now(),
  gerechnet_am      timestamptz,
  abgeschlossen_am  timestamptz,
  fehler            text,

  -- Warum dieser Lauf nicht nachrechenbar ist, falls er es nicht ist — etwa
  -- weil er aus einem Messsatz kommt statt aus stand_zum(uebergeben_am).
  -- Gehört nicht in den Vertrag, darf aber nicht verloren gehen: die
  -- Oberfläche zeigt es in der Kopfzeile.
  warnung           text,

  -- Das Priorisierungsdokument in Vertragsform — **ohne** den gate1-Block,
  -- der liegt zerlegt in bc2.gate1* und kommt erst beim Ausliefern dazu.
  -- Nach dem Schreiben unveränderlich (Trigger unten).
  dokument          jsonb,

  -- Ein Ergebnis gibt es genau dann, wenn gerechnet wurde. Ohne diese Klammer
  -- könnte ein Lauf `offen` sein und nichts zum Entscheiden tragen.
  CONSTRAINT lauf_ergebnis_passt_zum_zustand
    CHECK ((zustand IN ('offen', 'abgeschlossen')) = (dokument IS NOT NULL)),

  -- Die Fassungsnummer vergibt die Datenbank: die höchste plus eins, und
  -- dieser Schlüssel lässt keine zweite gleiche zu (ADR-008 · BC2, 2.4).
  CONSTRAINT lauf_fassung_je_paket UNIQUE (paket_id, fassung)
);

-- Höchstens **ein** nicht abgeschlossener Lauf je Paket. Ein Doppelklick auf
-- „neu rechnen“ erzeugt damit keine zwei Fassungen — der zweite Schreiber
-- läuft hier auf, nicht in einen Wettlauf im Python.
CREATE UNIQUE INDEX IF NOT EXISTS lauf_ein_offener_je_paket
  ON bc2.lauf (paket_id) WHERE zustand IN ('in_arbeit', 'offen');

CREATE INDEX IF NOT EXISTS lauf_company_idx
  ON bc2.lauf (company_id, uebergeben_am DESC);

COMMENT ON TABLE bc2.lauf IS
  'Ein Analyselauf (#164, ADR-005 · BC2) je (paket_id, fassung). f2, f3 … stoesst '
  'BC2 selbst an, nur nach Gate-1-Reject (ADR-008 · BC2, 2.1).';
COMMENT ON COLUMN bc2.lauf.dokument IS
  'Priorisierung in Vertragsform v3 ohne gate1-Block. Unveraenderlich, sobald '
  'geschrieben. Ausgeliefert wird dieses Dokument, nie eine Rekonstruktion aus Spalten.';

-- ------------------------------------------------------------
-- bc2.konzept und bc2.potenzial — das Ergebnis  (ADR-008 · BC2, 2.2)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bc2.konzept (
  konzept_id          uuid PRIMARY KEY,
  priorisierung_id    uuid NOT NULL REFERENCES bc2.lauf ON DELETE CASCADE,
  company_id          text NOT NULL,
  paket_id            text NOT NULL,
  -- Pflicht: die Kernprozess-ID ist der Bezug, auf den BC0 seit dem
  -- 17.08.2026 besteht und den diese Karte seit dem 30.08. festhält.
  kp_id               text NOT NULL,
  -- Klartextname aus public.ref_kernprozesse, soweit gelesen. Steht nicht im
  -- Vertrag (kontext kennt ihn nicht) und darum hier als Spalte.
  kp_name             text,
  -- Verkettet nur **innerhalb** eines Pakets, über Fassungen (ADR-008 · BC2,
  -- 2.1). Über Pakete hinweg veraltet ein Konzept, es wird nicht ersetzt.
  ersetzt_konzept_id  uuid REFERENCES bc2.konzept,
  dokument            jsonb NOT NULL,

  CONSTRAINT konzept_ein_kp_je_lauf UNIQUE (priorisierung_id, kp_id)
);

CREATE INDEX IF NOT EXISTS konzept_kp_idx ON bc2.konzept (company_id, kp_id);

CREATE TABLE IF NOT EXISTS bc2.potenzial (
  -- Schlüssel mit dem Lauf, nicht allein die potenzial_id: dieselbe Rechnung
  -- über dasselbe Paket schneidet unter Umständen dieselben Kennungen, und
  -- eine zweite Fassung darf daran nicht scheitern.
  priorisierung_id       uuid    NOT NULL REFERENCES bc2.lauf ON DELETE CASCADE,
  potenzial_id           text    NOT NULL,
  konzept_id             uuid    NOT NULL REFERENCES bc2.konzept ON DELETE CASCADE,
  kp_id                  text    NOT NULL,
  teilprozess_ids        text[]  NOT NULL,
  score                  integer,
  potenzialrang          integer,
  prioritaetsgruppe      text,
  -- Vorgehalten für #291 (Verknüpfung über Pakete hinweg). Bis dort
  -- entschieden ist, bleibt sie leer — und das heißt „nicht verknüpft“,
  -- nicht „ersetzt nichts“.
  ersetzt_potenzial_ids  text[],

  PRIMARY KEY (priorisierung_id, potenzial_id)
);

CREATE INDEX IF NOT EXISTS potenzial_kp_idx ON bc2.potenzial (kp_id);

COMMENT ON TABLE bc2.potenzial IS
  'Projektion aus dem Konzeptdokument zum Filtern und Verknuepfen, in derselben '
  'Transaktion geschrieben. Die Quelle ist das Dokument, nicht diese Tabelle.';

-- Das Ergebnis eines Laufs ist nach dem Schreiben unveränderlich
-- (ADR-008 · BC2, 2.2). Löschen bleibt möglich — für das Aufräumen der
-- Vertragstests und weil eine Löschung kein stilles Umschreiben ist.
CREATE OR REPLACE FUNCTION bc2.ergebnis_unveraenderlich() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'lauf' THEN
    IF OLD.dokument IS NOT NULL AND NEW.dokument IS DISTINCT FROM OLD.dokument THEN
      RAISE EXCEPTION 'bc2.lauf %: das Ergebnis ist geschrieben und unveraenderlich',
        OLD.priorisierung_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'bc2.%: das Ergebnis eines Laufs ist unveraenderlich', TG_TABLE_NAME
    USING ERRCODE = 'check_violation';
END
$$;

DROP TRIGGER IF EXISTS lauf_ergebnis_fest ON bc2.lauf;
CREATE TRIGGER lauf_ergebnis_fest BEFORE UPDATE ON bc2.lauf
  FOR EACH ROW EXECUTE FUNCTION bc2.ergebnis_unveraenderlich();

DROP TRIGGER IF EXISTS konzept_fest ON bc2.konzept;
CREATE TRIGGER konzept_fest BEFORE UPDATE ON bc2.konzept
  FOR EACH ROW EXECUTE FUNCTION bc2.ergebnis_unveraenderlich();

DROP TRIGGER IF EXISTS potenzial_fest ON bc2.potenzial;
CREATE TRIGGER potenzial_fest BEFORE UPDATE ON bc2.potenzial
  FOR EACH ROW EXECUTE FUNCTION bc2.ergebnis_unveraenderlich();

-- ------------------------------------------------------------
-- bc2.gate1* — die Entscheidung  (ADR-008 · BC2, 2.3)
-- ------------------------------------------------------------
--
-- Getrennt vom Ergebnis, weil sie danach entsteht und sich bis zum Abschluss
-- ändert. Zerlegt in Spalten, weil sie in keinem Dokument ankommt —
-- `Gate1Entscheidung.als_vertrag()` baut den Vertragsblock daraus.

CREATE TABLE IF NOT EXISTS bc2.gate1 (
  priorisierung_id        uuid        PRIMARY KEY REFERENCES bc2.lauf ON DELETE CASCADE,
  status                  text        NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
  entscheider             text,
  kommentar               text,
  abweichungsbegruendung  text,
  entschieden_am          timestamptz,
  geschrieben_am          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bc2.gate1_potenzial (
  priorisierung_id  uuid    NOT NULL REFERENCES bc2.gate1 ON DELETE CASCADE,
  potenzial_id      text    NOT NULL,
  -- NULL: weder freigegeben noch herausgenommen — kommt vor, wenn nur die
  -- Reihenfolge gesetzt ist (Entwurf) oder der ganze Lauf abgelehnt wurde.
  freigegeben       boolean,
  begruendung       text,
  -- Die gesetzte Reihenfolge als Rang statt als ID-Liste. NULL heißt: es gilt
  -- der gerechnete Rang (so liest der Vertrag ein fehlendes
  -- finale_reihenfolge_potenzial_ids).
  finaler_rang      integer CHECK (finaler_rang >= 1),

  PRIMARY KEY (priorisierung_id, potenzial_id),
  -- Entschieden wird nur über Potenziale, die dieser Lauf trägt.
  FOREIGN KEY (priorisierung_id, potenzial_id)
    REFERENCES bc2.potenzial (priorisierung_id, potenzial_id) ON DELETE CASCADE,
  CONSTRAINT gate1_potenzial_rang_einmal UNIQUE (priorisierung_id, finaler_rang)
);

CREATE TABLE IF NOT EXISTS bc2.gate1_prozess (
  priorisierung_id  uuid    NOT NULL REFERENCES bc2.gate1 ON DELETE CASCADE,
  kp_id             text    NOT NULL,
  -- Eigene Tabelle, weil das Konzept unveränderlich ist und der finale
  -- Prozessrang nicht hineingeschrieben werden darf.
  finaler_rang      integer NOT NULL CHECK (finaler_rang >= 1),

  PRIMARY KEY (priorisierung_id, kp_id),
  CONSTRAINT gate1_prozess_rang_einmal UNIQUE (priorisierung_id, finaler_rang)
);

-- `pending` ist überschreibbar, `approved` und `rejected` sind endgültig.
-- Der Anwendungscode schreibt ohnehin nur `… WHERE status = 'pending'`; der
-- Trigger macht daraus eine Regel, die auch ein Handgriff in psql nicht
-- umgeht. Löschen bleibt möglich (Aufräumen, Kaskade vom Lauf).
CREATE OR REPLACE FUNCTION bc2.gate1_endgueltig() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  bisher text;
BEGIN
  IF TG_TABLE_NAME = 'gate1' THEN
    bisher := OLD.status;
  ELSE
    SELECT g.status INTO bisher FROM bc2.gate1 g
     WHERE g.priorisierung_id = NEW.priorisierung_id;
  END IF;
  IF bisher IN ('approved', 'rejected') THEN
    RAISE EXCEPTION 'Gate 1 fuer % ist entschieden (%) und endgueltig',
      NEW.priorisierung_id, bisher USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS gate1_fest ON bc2.gate1;
CREATE TRIGGER gate1_fest BEFORE UPDATE ON bc2.gate1
  FOR EACH ROW EXECUTE FUNCTION bc2.gate1_endgueltig();

DROP TRIGGER IF EXISTS gate1_potenzial_fest ON bc2.gate1_potenzial;
CREATE TRIGGER gate1_potenzial_fest BEFORE INSERT OR UPDATE ON bc2.gate1_potenzial
  FOR EACH ROW EXECUTE FUNCTION bc2.gate1_endgueltig();

DROP TRIGGER IF EXISTS gate1_prozess_fest ON bc2.gate1_prozess;
CREATE TRIGGER gate1_prozess_fest BEFORE INSERT OR UPDATE ON bc2.gate1_prozess
  FOR EACH ROW EXECUTE FUNCTION bc2.gate1_endgueltig();

-- ------------------------------------------------------------
-- bc2.eingang.status — abgelöst  (ADR-008 · BC2, 2.5)
-- ------------------------------------------------------------

COMMENT ON COLUMN bc2.eingang.status IS
  'ABGELOEST seit bc2.2 (ADR-008 · BC2, 2.5): wird nicht mehr geschrieben. Der Zustand '
  'des Rechnens haengt am Lauf (bc2.lauf.zustand), weil ein Paket mehrere Fassungen '
  'haben kann. Nicht geloescht, damit alte Zeilen lesbar bleiben.';

-- ------------------------------------------------------------
-- bc2.v_ergebnis_je_paket — der Vertrag mit BC0  (ADR-008 · BC2, 2.6)
-- ------------------------------------------------------------
--
-- Je Paket die jüngste Fassung. BC0 liest diese Sicht, nicht die Tabellen —
-- die bleiben BC2-intern und umbaubar.

CREATE OR REPLACE VIEW bc2.v_ergebnis_je_paket AS
SELECT DISTINCT ON (l.paket_id)
       l.company_id,
       l.paket_id,
       l.fassung,
       l.priorisierung_id,
       l.zustand                                         AS lauf_zustand,
       -- Nur wo es etwas zu entscheiden gibt; ein Lauf in Arbeit hat keinen
       -- Gate-1-Zustand, auch nicht `pending`.
       CASE WHEN l.zustand IN ('offen', 'abgeschlossen')
            THEN coalesce(g.status, 'pending') END        AS gate1_status,
       g.entschieden_am,
       (SELECT array_agg(k.kp_id ORDER BY k.kp_id)
          FROM bc2.konzept k
         WHERE k.priorisierung_id = l.priorisierung_id)  AS kp_ids,
       -- Nur nach Freigabe: ein Entwurf zählt nicht als freigegeben.
       CASE WHEN g.status = 'approved' THEN
         (SELECT count(*) FROM bc2.gate1_potenzial gp
           WHERE gp.priorisierung_id = l.priorisierung_id AND gp.freigegeben)
       END                                               AS anzahl_freigegeben
  FROM bc2.lauf l
  LEFT JOIN bc2.gate1 g USING (priorisierung_id)
 ORDER BY l.paket_id, l.fassung DESC;

COMMENT ON VIEW bc2.v_ergebnis_je_paket IS
  'Rueckkanal an BC0 (ADR-007 · BC2 §4.3, ADR-008 · BC2 2.6): je Paket die juengste '
  'Fassung, Gate-1-Zustand und die beruehrten Kernprozesse.';

-- SELECT vergibt BC2 selbst — die Sicht gehört bc2_role. Das USAGE auf Schema
-- `bc2` kann nur BC0 vergeben (ADR-003); bis dahin ist die Sicht für
-- `bc_leser` zwar freigegeben, aber unerreichbar. Fehlt die Rolle ganz, wird
-- das gemeldet statt abgebrochen.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    EXECUTE 'GRANT SELECT ON bc2.v_ergebnis_je_paket TO bc_leser';
  ELSE
    RAISE NOTICE 'Rolle bc_leser fehlt — GRANT auf bc2.v_ergebnis_je_paket uebersprungen.';
  END IF;
END
$$;
