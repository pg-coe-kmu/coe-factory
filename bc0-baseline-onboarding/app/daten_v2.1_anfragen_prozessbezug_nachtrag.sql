-- ============================================================
-- BC0 — Nachtrag: Prozessbezug fuer die drei Testdaten-Anfragen
-- Stand: 27.08.2026 · Autor: Simeon Ehmer
-- ============================================================
--
-- WOZU
--   `schema_v2.1` setzt `process_id` auf NOT NULL — aber nur, wenn der
--   Bestand die Bedingung schon erfuellt. Die drei Anfragen vom
--   24.08. (`A-2026-01` bis `-03`) tragen ihren Prozessbezug bisher nur
--   im FREITEXT des Hinweisfelds:
--
--     "Fokus: KP-06.TP-2 Reise- und Einsatzplanung. Testdaten, ..."
--
--   Damit meldet v2.1 beim Einspielen:
--     "NOT NULL NICHT gesetzt: 3 Anfrage(n) ohne Prozessbezug."
--
--   Diese Datei traegt nach, was im Hinweis schon steht — sie erfindet
--   nichts. Danach greift der NOT NULL-Block von v2.1.
--
-- REIHENFOLGE
--   1. schema_v2.1 einspielen  (legt die Spalten an, NOT NULL bleibt aus)
--   2. DIESE DATEI            (traegt die drei Bezuege nach)
--   3. schema_v2.1 erneut     (jetzt greift NOT NULL — das Skript ist
--                              durchgehend wiederholbar)
--
-- WARUM `zuordnung_quelle = 'anfrage'`
--   Der Bezug stammt von dem, der die Anfrage angelegt hat — bei
--   Testdaten also von BC0 selbst. Das ist Stufe 1 des Trichters, nicht
--   ein Vorschlag und nicht das Ergebnis eines Interviews.
-- ============================================================

BEGIN;

DO $$
DECLARE cid uuid; n int;
BEGIN
  SELECT company_id INTO cid FROM companies WHERE name = 'NoroAI Consulting GmbH';
  IF cid IS NULL THEN
    RAISE EXCEPTION 'Mandant "NoroAI Consulting GmbH" nicht gefunden.';
  END IF;

  UPDATE ref_anfragen SET process_id = 'KP-06', sub_process_id = 'KP-06.TP-2',
                          zuordnung_quelle = 'anfrage'
   WHERE company_id = cid AND anfrage_id = 'A-2026-01' AND process_id IS NULL;

  UPDATE ref_anfragen SET process_id = 'KP-05', sub_process_id = 'KP-05.TP-1',
                          zuordnung_quelle = 'anfrage'
   WHERE company_id = cid AND anfrage_id = 'A-2026-02' AND process_id IS NULL;

  UPDATE ref_anfragen SET process_id = 'KP-06', sub_process_id = 'KP-06.TP-1',
                          zuordnung_quelle = 'anfrage'
   WHERE company_id = cid AND anfrage_id = 'A-2026-03' AND process_id IS NULL;

  -- Gegenprobe im selben Vorgang: Bleibt eine Anfrage dieses Mandanten
  -- ohne Bezug, wird zurueckgerollt statt halb fertig zu sein.
  SELECT count(*) INTO n FROM ref_anfragen
   WHERE company_id = cid AND process_id IS NULL;

  IF n > 0 THEN
    RAISE EXCEPTION 'Noch % Anfrage(n) ohne Prozessbezug — nichts geaendert.', n;
  END IF;

  RAISE NOTICE 'Drei Anfragen zugeordnet. schema_v2.1 kann erneut laufen.';
END $$;

COMMIT;

-- ============================================================
-- GEGENPROBEN
-- ============================================================
-- Erwartet: drei Zeilen, alle mit Prozess und Teilprozess
-- SELECT anfrage_id, process_id, sub_process_id, zuordnung_quelle
--   FROM ref_anfragen ORDER BY anfrage_id;
--
-- Erwartet: 0
-- SELECT count(*) FROM ref_anfragen WHERE process_id IS NULL;
--
-- Erwartet: die Hinweistexte stimmen weiter mit den Spalten ueberein
-- SELECT anfrage_id, sub_process_id, substring(hinweis from 'KP-[0-9]{2}\.TP-[0-9]')
--   FROM ref_anfragen ORDER BY anfrage_id;
-- ============================================================
