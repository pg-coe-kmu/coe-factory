-- ============================================================
-- BC0 — v2.3: "Weiss ich nicht" wird moeglich,
--             ohne dass die Prozesspflicht faellt
-- Stand: 28.08.2026 · Autor: Simeon Ehmer
-- ============================================================
--
-- WOZU
--   v2.1 hat am 27.08. `process_id` und `zuordnung_quelle` auf NOT NULL
--   gesetzt. Der Satz dahinter stammt aus dem Papier vom 22.08.:
--   "Ohne Prozess keine Anfrage."
--
--   Beim Bau der Anfragemaske am 28.08. hat sich gezeigt, dass dieser
--   Satz zwei verschiedene Dinge meint, die auseinanderfallen:
--
--     (a) Eine Anfrage darf nicht OHNE Prozessbezug WEITERLAUFEN.
--         Ein Interview auf einem unbekannten Prozess ist sinnlos.
--     (b) Eine Anfrage darf nicht ohne Prozessbezug ENTSTEHEN.
--
--   (a) ist richtig. (b) ist es nicht — und war so auch nie entschieden.
--   Wer aus dem Fachbereich kommt, weiss nicht, was `KP-06.TP-2` ist.
--   Das Konzept vom 26.08. sagt es ausdruecklich:
--
--     "Ein Fachbereichsmensch, der auf gut Glueck einen Kernprozess
--      anklickt, ist schlechter als ein leeres Feld — dann laeuft ein
--      vollstaendiges Interview auf dem falschen Prozess."
--
--   Und ToDo-Punkt 58 verlangt woertlich: "weiss ich nicht" erlaubt.
--
--   NOT NULL setzt (b) durch und erzwingt damit genau das Raten, vor dem
--   das Konzept warnt. Zwei Tage nach dem Einspielen war die Folge
--   ausserdem, dass der Endpunkt `POST .../anfragen` gar nicht mehr
--   schreiben konnte: Er kennt die beiden Spalten nicht (app.py 3587).
--
-- WAS DIESE DATEI TUT
--   Sie ersetzt NOT NULL durch eine Bedingung, die (a) durchsetzt und
--   (b) freigibt:
--
--     process_id IS NOT NULL  ODER  status = 'eingegangen'
--
--   Aus "ohne Prozess keine Anfrage" wird "ohne Prozess kein
--   Fortschritt". Eine Anfrage darf ohne Bezug ENTSTEHEN, aber sie
--   kommt keinen Schritt weiter — kein 'zugeordnet', kein
--   'im_interview', kein Gate — bevor der Bezug steht. Die Datenbank
--   haelt die Regel, nicht die Maske.
--
--   Entschieden von Simeon am 28.08.2026, Variante 1 von dreien.
--
-- WAS SIE AUSDRUECKLICH NICHT TUT
--   Sie traegt keinen Platzhalter nach. Ein erfundener Prozessbezug
--   saehe aus wie ein erhobener — dieselbe Begruendung, mit der v2.1
--   auf einen Backfill verzichtet hat.
--
-- Rein additiv im Sinne der Daten: keine Zeile wird angefasst, kein
-- Primaerschluessel geaendert. Zurueckgenommen wird nur eine
-- Einschraenkung, und zwar in Richtung WEITER — jede Bestandszeile
-- erfuellt die neue Bedingung, weil alle drei einen Bezug tragen.
-- ============================================================


-- ------------------------------------------------------------
-- 1. Die Pflicht faellt — aber nur die auf Spaltenebene
-- ------------------------------------------------------------
ALTER TABLE ref_anfragen ALTER COLUMN process_id       DROP NOT NULL;
ALTER TABLE ref_anfragen ALTER COLUMN zuordnung_quelle DROP NOT NULL;


-- ------------------------------------------------------------
-- 2. Und wird durch die Bedingung ersetzt, die sie meinte
-- ------------------------------------------------------------
-- Gegenprobe vor dem Anlegen: Gaebe es eine Bestandszeile, die die
-- Bedingung verletzt, wuerde das ADD CONSTRAINT scheitern und die
-- ganze Datei zurueckrollen. Der Block meldet den Fall vorher lesbar,
-- statt ihn als Constraint-Fehler erscheinen zu lassen.
DO $$
DECLARE offen INTEGER;
BEGIN
  SELECT count(*) INTO offen FROM ref_anfragen
   WHERE process_id IS NULL AND status <> 'eingegangen';
  IF offen > 0 THEN
    RAISE EXCEPTION 'Abbruch: % Anfrage(n) stehen ohne Prozessbezug jenseits '
                    'von ''eingegangen''. Erst den Bezug nachtragen oder den '
                    'Status zuruecksetzen.', offen;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conname = 'ck_anfrage_fortschritt_braucht_prozess') THEN
    ALTER TABLE ref_anfragen ADD CONSTRAINT ck_anfrage_fortschritt_braucht_prozess
      CHECK (process_id IS NOT NULL OR status = 'eingegangen');
  END IF;
END $$;

-- Bezug und Herkunft gehoeren zusammen: Ein Prozessbezug ohne Angabe,
-- woher er stammt, ist nach ADR-005 nicht verwendbar — und eine
-- Herkunftsangabe ohne Bezug beschreibt nichts. Deshalb beide oder
-- keiner, nicht das eine ohne das andere.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conname = 'ck_anfrage_bezug_paarweise') THEN
    ALTER TABLE ref_anfragen ADD CONSTRAINT ck_anfrage_bezug_paarweise
      CHECK ((process_id IS NULL) = (zuordnung_quelle IS NULL));
  END IF;
END $$;

COMMENT ON COLUMN ref_anfragen.process_id IS
  'Kernprozess, auf den sich die Anfrage bezieht. DARF beim Eingang '
  'leer bleiben ("weiss ich nicht") — dann bleibt die Anfrage im '
  'Status ''eingegangen'' liegen, bis BC1 den Bezug im Interview '
  'herstellt. Erzwungen durch ck_anfrage_fortschritt_braucht_prozess.';


-- ------------------------------------------------------------
-- 3. Groessenordnung — als Text, damit sie kein Messwert wird
-- ------------------------------------------------------------
-- Punkt 3 aus dem Konzept vom 26.08.: "Wie viele Menschen betrifft es,
-- wie oft im Monat?" — als Groessenordnung fuer die Reihenfolge, NICHT
-- als Ersatz fuer BC1s Zeiterhebung.
--
-- Bewusst EIN Freitextfeld und keine Zahlenspalten. Eine Spalte
-- `betroffene INTEGER` sieht aus wie eine Messung und landet frueher
-- oder spaeter in einer Rechnung; ein Satz wie "etwa 12 Leute, jeden
-- Monatsanfang" kann das nicht. Die Guete steckt hier im Datentyp
-- statt in einem Merkmal, das jemand uebersehen kann.
ALTER TABLE ref_anfragen ADD COLUMN IF NOT EXISTS umfang_geschaetzt TEXT;

COMMENT ON COLUMN ref_anfragen.umfang_geschaetzt IS
  'Groessenordnung in eigenen Worten, IMMER geschaetzt. Dient allein '
  'der Reihenfolge. Kein Eingang in eine ROI-Rechnung — Haeufigkeit '
  'und Dauer erhebt BC1 im Interview, mit Guetegrad.';


-- ------------------------------------------------------------
-- 4. Die Lesesicht fuer BC1 zeigt jetzt auch den Stand
-- ------------------------------------------------------------
-- Ohne den Status sieht BC1 nicht, ob eine Anfrage auf ihn wartet
-- oder laengst durch ist. Der Status enthaelt keine personenbezogenen
-- Daten; der Originaltext bleibt ausgeschlossen wie bisher.
-- Spalte wird HINTEN angehaengt — CREATE OR REPLACE VIEW erlaubt kein
-- Umstellen bestehender Spalten.
CREATE OR REPLACE VIEW v_anfrage_prozessbezug AS
SELECT company_id,
       anfrage_id,
       process_id,
       sub_process_id,
       zuordnung_quelle,
       eingang_am,
       status
  FROM ref_anfragen;

GRANT SELECT ON v_anfrage_prozessbezug TO bc_leser;


-- ============================================================
-- KONTROLLE — nach dem Einspielen von Hand
-- ============================================================
-- 1) Beide Bedingungen stehen (erwartet: 2 Zeilen)
--    SELECT conname FROM pg_constraint
--     WHERE conrelid = 'ref_anfragen'::regclass
--       AND conname IN ('ck_anfrage_fortschritt_braucht_prozess',
--                       'ck_anfrage_bezug_paarweise');
--
-- 2) NOT NULL ist weg (erwartet: beide 'f')
--    SELECT attname, attnotnull FROM pg_attribute
--     WHERE attrelid = 'ref_anfragen'::regclass
--       AND attname IN ('process_id','zuordnung_quelle');
--
-- 3) Die drei Bestandsanfragen sind unveraendert (erwartet: 3, alle mit Bezug)
--    SELECT count(*) AS gesamt, count(process_id) AS mit_bezug FROM ref_anfragen;
--
-- 4) Probe, die scheitern MUSS — ohne Bezug jenseits von 'eingegangen':
--    UPDATE ref_anfragen SET status='zugeordnet', process_id=NULL,
--           zuordnung_quelle=NULL WHERE anfrage_id='A-2026-01';
--    -> erwartet: ERROR ck_anfrage_fortschritt_braucht_prozess. Danach ROLLBACK.
