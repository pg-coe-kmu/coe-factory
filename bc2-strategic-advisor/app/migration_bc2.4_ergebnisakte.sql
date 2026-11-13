-- ============================================================
-- BC2 · Migration bc2.4 — die Ergebnisakte
-- Ticket #378 · Entscheidung #376 (ADR-007 · BC2, Nachtrag vom 13.11.2026) · Karte #158
-- Stand 13.11.2026
-- ============================================================
--
-- Jede Freigabe an Gate 1 friert eine **Ergebnisakte** ein, in derselben
-- Transaktion wie `approved`: die Dateien, die an BC3 gehen (sofern der Lauf
-- lieferbar ist), und die Präsentation für den Mandanten, Byte für Byte. Bis
-- hierher stand der `gate1`-Block nur in der gezogenen Datei, die Nachricht nur
-- im Repo, und die Präsentation entstand bei jedem Klick neu.
--
-- Ausführen mit der BC2-Rolle, wie bc2.1 bis bc2.3 (ADR-003: CREATE nur auf `bc2`):
--
--     psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migration_bc2.4_ergebnisakte.sql
--
-- Setzt bc2.3 voraus. **Vor** dem Neubau des Dienstes einspielen: der neue
-- Dienst schreibt die Akte beim Freigeben, und ohne die Tabellen scheitert jede
-- Freigabe. Umgekehrt nimmt diese Migration dem **alten** Dienst das Freigeben:
-- die Regel „keine Freigabe ohne Akte“ (unten) gilt ab hier, und der alte Dienst
-- schreibt keine. Zwischen Migration und Neubau wird darum nicht freigegeben.
--
-- Wiederholbar: Tabellen mit IF NOT EXISTS, Funktionen und Sicht mit OR
-- REPLACE, Trigger mit DROP … IF EXISTS davor.
--
-- **Was die Datenbank hier durchsetzt** (geprüft in tests/test_vertrag_postgres.py):
--
--   1. Die Akte ist nach dem Schreiben unveränderlich, Kopf wie Dateien. Einzige
--      Ausnahme ist `link_gesperrt_am` (ADR-007 · BC2, Nachtrag 13.11., Punkt 4).
--   2. Eine Datei kommt nur in der Transaktion dazu, in der die Akte entsteht —
--      danach nicht mehr, und einzeln löschen lässt sie sich auch nicht.
--   3. Eine Akte gibt es nur zu einer Freigabe, und eine Freigabe nur mit Akte
--      (Punkt 1: „freigegeben, aber ohne Akte“ ist der stille Zwischenzustand,
--      den die Entscheidung abschaffen sollte). Geprüft am Ende der Transaktion.
--   4. Dateien an BC3 trägt nur eine Akte ohne Sperrgrund: ein Lauf mit
--      Sperrgrund hat eine Akte, aber keine Lieferung.
--   5. Die Prüfsumme ist die SHA-256 des Inhalts.
--
-- **Kein Löschschutz.** Wird der Lauf gelöscht, fällt die Akte per Kaskade mit,
-- wie Konzepte und Gate 1 (Nachtrag 13.11., Punkt 4; Anlass war #379). Auch die
-- Akte als Ganzes lässt sich löschen — dann ist der Lauf wieder „freigegeben
-- ohne Akte“ und wird mit `python -m ergebnisakte nachtragen` neu eingefroren.

-- ------------------------------------------------------------
-- bc2.ergebnisakte — der Kopf, eine Zeile je freigegebenem Lauf
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bc2.ergebnisakte (
  priorisierung_id  uuid        PRIMARY KEY REFERENCES bc2.lauf ON DELETE CASCADE,

  -- Doppelt zum Lauf, damit die Sicht für BC0 und das Ziehen ohne Join
  -- auskommen. Dass sie zum Lauf passen, prüft der Trigger beim Einfügen.
  company_id        text        NOT NULL,
  paket_id          text        NOT NULL,
  fassung           integer     NOT NULL CHECK (fassung >= 1),

  -- `<company>-<paket_id>-f<n>` (ADR-007 · BC2, 2.2): der Lieferordner, wenn es
  -- eine Lieferung gibt — sonst der Name, unter dem sie läge.
  ordner            text        NOT NULL,

  -- Der Sperrgrund des Laufs zum Zeitpunkt der Freigabe. NULL heißt lieferbar.
  sperrgrund        text,

  -- Der Link auf die Präsentation führt zu BC2, mit diesem Token und ohne den
  -- Schlüssel der Oberfläche (Nachtrag 13.11., Punkt 5). Zufällig erzeugt im
  -- Dienst (secrets.token_urlsafe); unbefristet, sperrbar.
  link_token        text        NOT NULL UNIQUE CHECK (link_token ~ '^[A-Za-z0-9_-]{20,}$'),

  -- Setzt der Trigger auf now(), gleich was mitkommt: an diesem Zeitpunkt hängt
  -- die Regel, dass Dateien nur in der Transaktion des Einfrierens dazukommen.
  eingefroren_am    timestamptz NOT NULL DEFAULT now(),

  -- Nur beim nachträglichen Einfrieren eines schon freigegebenen Laufs
  -- (cc7f4d1b f1, #378 Punkt 6): wer, wann, warum nachträglich.
  vermerk           text,

  -- Die einzige veränderliche Spalte. NULL heißt: der Link gilt.
  link_gesperrt_am  timestamptz,

  CONSTRAINT ergebnisakte_je_fassung UNIQUE (paket_id, fassung)
);

COMMENT ON TABLE bc2.ergebnisakte IS
  'Ergebnisakte (#376, ADR-007 · BC2 Nachtrag 13.11.2026): was bei der Freigabe aus einem '
  'Lauf festgehalten wird. Unveraenderlich bis auf link_gesperrt_am. BC0 liest '
  'bc2.v_ergebnisakte, nicht diese Tabelle.';
COMMENT ON COLUMN bc2.ergebnisakte.vermerk IS
  'Nur beim nachtraeglichen Einfrieren eines vor bc2.4 freigegebenen Laufs.';
COMMENT ON COLUMN bc2.ergebnisakte.link_gesperrt_am IS
  'Gesetzt: der Link auf die Praesentation liefert 404. Die Bytes bleiben in der Akte.';

-- ------------------------------------------------------------
-- bc2.ergebnisakte_datei — die Dateien, Byte für Byte
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bc2.ergebnisakte_datei (
  priorisierung_id  uuid  NOT NULL REFERENCES bc2.ergebnisakte ON DELETE CASCADE,
  -- Ein Dateiname, kein Pfad: `prozesspriorisierung.json`, `konzept_<KP>.json`,
  -- `NACHRICHT_AN_BC3.md`, `praesentation.pptx`.
  name              text  NOT NULL CHECK (name ~ '^[A-Za-z0-9][A-Za-z0-9_.-]*$'),
  -- bc3: Teil der Lieferung, das Werkzeug schreibt sie in den Lieferordner.
  -- mandant: die Präsentation, kein Teil der Lieferung (Nachtrag #305, Punkt 4).
  empfaenger        text  NOT NULL CHECK (empfaenger IN ('bc3', 'mandant')),
  inhalt            bytea NOT NULL,
  pruefsumme        text  NOT NULL,

  PRIMARY KEY (priorisierung_id, name),
  CONSTRAINT ergebnisakte_datei_pruefsumme
    CHECK (pruefsumme = encode(sha256(inhalt), 'hex'))
);

COMMENT ON TABLE bc2.ergebnisakte_datei IS
  'Die Dateien einer Ergebnisakte, wie sie an BC3 (empfaenger bc3) bzw. an den Mandanten '
  '(mandant) gehen. Unveraenderlich; Pruefsumme = SHA-256 des Inhalts.';

-- ------------------------------------------------------------
-- Einfügen: passt die Akte zum Lauf, und ist der Lauf freigegeben?
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION bc2.ergebnisakte_einfuegen() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  l bc2.lauf%ROWTYPE;
BEGIN
  SELECT * INTO l FROM bc2.lauf WHERE priorisierung_id = NEW.priorisierung_id;
  IF NEW.company_id IS DISTINCT FROM l.company_id
     OR NEW.paket_id IS DISTINCT FROM l.paket_id
     OR NEW.fassung IS DISTINCT FROM l.fassung THEN
    RAISE EXCEPTION 'bc2.ergebnisakte: % f% passt nicht zum Lauf %',
      NEW.paket_id, NEW.fassung, NEW.priorisierung_id USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM bc2.gate1 g
                  WHERE g.priorisierung_id = NEW.priorisierung_id AND g.status = 'approved') THEN
    RAISE EXCEPTION 'bc2.ergebnisakte: Lauf % ist an Gate 1 nicht freigegeben',
      NEW.priorisierung_id USING ERRCODE = 'check_violation';
  END IF;
  NEW.eingefroren_am := now();
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS ergebnisakte_neu ON bc2.ergebnisakte;
CREATE TRIGGER ergebnisakte_neu BEFORE INSERT ON bc2.ergebnisakte
  FOR EACH ROW EXECUTE FUNCTION bc2.ergebnisakte_einfuegen();

CREATE OR REPLACE FUNCTION bc2.ergebnisakte_datei_einfuegen() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  a bc2.ergebnisakte%ROWTYPE;
BEGIN
  SELECT * INTO a FROM bc2.ergebnisakte WHERE priorisierung_id = NEW.priorisierung_id;
  -- now() ist der Beginn der Transaktion, und eingefroren_am hat der Trigger
  -- oben genau darauf gesetzt: gleich heißt „dieselbe Transaktion“.
  IF a.eingefroren_am IS DISTINCT FROM now() THEN
    RAISE EXCEPTION 'bc2.ergebnisakte %: die Akte ist eingefroren, es kommt keine Datei dazu',
      NEW.priorisierung_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.empfaenger = 'bc3' AND a.sperrgrund IS NOT NULL THEN
    RAISE EXCEPTION 'bc2.ergebnisakte %: ein Lauf mit Sperrgrund hat keine Lieferung an BC3',
      NEW.priorisierung_id USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS ergebnisakte_datei_neu ON bc2.ergebnisakte_datei;
CREATE TRIGGER ergebnisakte_datei_neu BEFORE INSERT ON bc2.ergebnisakte_datei
  FOR EACH ROW EXECUTE FUNCTION bc2.ergebnisakte_datei_einfuegen();

-- ------------------------------------------------------------
-- Unveränderlich — außer der Sperre des Links
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION bc2.ergebnisakte_unveraenderlich() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'ergebnisakte' AND TG_OP = 'UPDATE' THEN
    IF to_jsonb(NEW) - 'link_gesperrt_am' IS DISTINCT FROM to_jsonb(OLD) - 'link_gesperrt_am' THEN
      RAISE EXCEPTION 'bc2.ergebnisakte %: die Akte ist unveraenderlich, nur der Link laesst sich sperren',
        OLD.priorisierung_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_TABLE_NAME = 'ergebnisakte_datei' AND TG_OP = 'DELETE' THEN
    -- Mit der Akte darf die Datei gehen (Kaskade vom Lauf oder vom Kopf),
    -- allein nicht: sonst fehlte der Akte still ein Teil.
    IF NOT EXISTS (SELECT 1 FROM bc2.ergebnisakte a
                    WHERE a.priorisierung_id = OLD.priorisierung_id) THEN
      RETURN OLD;
    END IF;
    RAISE EXCEPTION 'bc2.ergebnisakte %: eine Datei geht nur mit der ganzen Akte',
      OLD.priorisierung_id USING ERRCODE = 'check_violation';
  END IF;
  RAISE EXCEPTION 'bc2.ergebnisakte %: die Dateien einer Akte sind unveraenderlich',
    OLD.priorisierung_id USING ERRCODE = 'check_violation';
END
$$;

DROP TRIGGER IF EXISTS ergebnisakte_fest ON bc2.ergebnisakte;
CREATE TRIGGER ergebnisakte_fest BEFORE UPDATE ON bc2.ergebnisakte
  FOR EACH ROW EXECUTE FUNCTION bc2.ergebnisakte_unveraenderlich();

DROP TRIGGER IF EXISTS ergebnisakte_datei_fest ON bc2.ergebnisakte_datei;
CREATE TRIGGER ergebnisakte_datei_fest BEFORE UPDATE OR DELETE ON bc2.ergebnisakte_datei
  FOR EACH ROW EXECUTE FUNCTION bc2.ergebnisakte_unveraenderlich();

-- ------------------------------------------------------------
-- Keine Freigabe ohne Akte — geprüft am Ende der Transaktion
-- ------------------------------------------------------------
--
-- Ein Constraint-Trigger, aufgeschoben bis zum COMMIT: der Dienst schreibt
-- erst `approved` und dann die Akte (der Einfüge-Trigger oben verlangt die
-- Freigabe), beides in einer Transaktion. Fehlt die Akte am Ende, scheitert das
-- COMMIT, und `approved` gilt nicht. Feuert nur beim Wechsel auf `approved` —
-- ein vor bc2.4 freigegebener Lauf bleibt, wie er ist, und wird nachträglich
-- eingefroren (#378, Punkt 6).

CREATE OR REPLACE FUNCTION bc2.freigabe_hat_akte() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  -- In derselben Transaktion wieder gelöscht (Kaskade, Aufräumen): nichts zu prüfen.
  IF NOT EXISTS (SELECT 1 FROM bc2.gate1 g
                  WHERE g.priorisierung_id = NEW.priorisierung_id AND g.status = 'approved') THEN
    RETURN NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM bc2.ergebnisakte a
                  WHERE a.priorisierung_id = NEW.priorisierung_id) THEN
    RAISE EXCEPTION 'Gate 1 fuer %: eine Freigabe ohne Ergebnisakte gilt nicht',
      NEW.priorisierung_id USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS gate1_freigabe_mit_akte ON bc2.gate1;
CREATE CONSTRAINT TRIGGER gate1_freigabe_mit_akte
  AFTER INSERT OR UPDATE OF status ON bc2.gate1
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW WHEN (NEW.status = 'approved')
  EXECUTE FUNCTION bc2.freigabe_hat_akte();

-- ------------------------------------------------------------
-- bc2.v_ergebnisakte — was BC0 liest  (Nachtrag 13.11., Punkt 6)
-- ------------------------------------------------------------
--
-- Eine Zeile je Datei, der Kopf der Akte daneben. `v_ergebnis_je_paket` zeigt
-- nur die jüngste Fassung je Paket; eine Akte gehört zu genau einer Fassung,
-- darum eine eigene Sicht. `inhalt_text` und `dokument` sind Bequemlichkeit für
-- die Textdateien — die Quelle bleibt `inhalt`, Byte für Byte.

CREATE OR REPLACE VIEW bc2.v_ergebnisakte AS
SELECT a.company_id,
       a.paket_id,
       a.fassung,
       a.priorisierung_id,
       a.ordner,
       (a.sperrgrund IS NULL)                                  AS lieferbar,
       a.sperrgrund,
       a.eingefroren_am,
       a.vermerk,
       -- Relativ zur Adresse von BC2 (im Betrieb https://bc2.02da.de). NULL,
       -- solange der Link gesperrt ist.
       CASE WHEN a.link_gesperrt_am IS NULL
            THEN '/praesentation/' || a.link_token END         AS link_pfad,
       a.link_gesperrt_am,
       d.name,
       d.empfaenger,
       d.pruefsumme,
       octet_length(d.inhalt)                                  AS groesse,
       d.inhalt,
       CASE WHEN d.name ~ '\.(json|md)$'
            THEN convert_from(d.inhalt, 'UTF8') END             AS inhalt_text,
       CASE WHEN d.name ~ '\.json$'
            THEN convert_from(d.inhalt, 'UTF8')::jsonb END      AS dokument
  FROM bc2.ergebnisakte a
  JOIN bc2.ergebnisakte_datei d USING (priorisierung_id);

COMMENT ON VIEW bc2.v_ergebnisakte IS
  'Fuer BC0 (ADR-007 · BC2, Nachtrag 13.11.2026, Punkt 6): je Ergebnisakte ihre Dateien, '
  'Byte fuer Byte, mit Empfaenger (bc3/mandant), Pruefsumme und dem Link auf die Praesentation.';

-- SELECT vergibt BC2 selbst, wie für v_ergebnis_je_paket (bc2.2). Fehlt die
-- Rolle, wird das gemeldet statt abgebrochen.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    EXECUTE 'GRANT SELECT ON bc2.v_ergebnisakte TO bc_leser';
  ELSE
    RAISE NOTICE 'Rolle bc_leser fehlt — GRANT auf bc2.v_ergebnisakte uebersprungen.';
  END IF;
END
$$;
