-- ============================================================
-- BC0 — Migration v1.3 (A): Freitext `ref_prozesse.owner_name` -> Personenregister
-- Stand: 12.08.2026 · Autor: Simeon Ehmer
--
-- VORAUSSETZUNG: schema_v1.3_teil_a_personen.sql ist eingespielt.
--
-- WARUM VON HAND?
--   Die neun Werte in owner_name benutzen drei verschiedene Trennzeichen
--   („/", „+", „·"), mischen Personen mit Funktionsbezeichnungen und lassen
--   die Beteiligungsart offen. Eine automatische Zerlegung würde raten. Die
--   Zuordnung unten ist deshalb eine ausdrückliche, prüfbare Entscheidungs-
--   tabelle — sie darf vor dem Einspielen geändert werden.
--
-- ZWEI STELLEN, DIE INTERPRETATION ENTHALTEN (bitte vor dem Lauf prüfen):
--   1. „externer Steuerberater + Sergio"  -> Sergio als `eigner`,
--      der Steuerberater als `mitwirkend`. Begründung: Die Verantwortung für
--      einen Prozess kann nicht bei einem Externen liegen.
--   2. „Sabrina Disimino / externer DSB"  -> Sabrina als `eigner`,
--      der DSB als `mitwirkend`. Gleiche Begründung.
--   Bei „Ozan Kiraz / Mehdi Louali" sind beide intern, also beide `eigner`.
--
-- WIEDERHOLBAR. Alle Anweisungen laufen über ON CONFLICT DO NOTHING und
--   verändern keine bestehende Zeile. Der Freitext bleibt unangetastet.
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f migration_v1.3_personen.sql
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Personen anlegen
-- ------------------------------------------------------------
-- Die IDs sind hier fest vergeben und nicht fortlaufend berechnet. Grund:
-- Die Migration muss wiederholbar sein und beim zweiten Lauf dieselben IDs
-- treffen. Ab hier vergibt die Anwendung fortlaufend (ADR-004 R2), beginnend
-- bei P-11.
--
-- P-10 ist keine natürliche Person, sondern eine rotierend besetzte Funktion.
-- Sie bekommt trotzdem eine ID, weil sonst der Verweis aus dem Prozess
-- verloren ginge. `name` bleibt leer, `funktion` trägt die Bezeichnung —
-- dieselbe Bauart wie bei den unbenannten Externen.

INSERT INTO ref_personen (company_id, person_id, name, funktion, extern, organisation, hinweis)
SELECT c.company_id, v.person_id, v.name, v.funktion, v.extern, v.organisation, v.hinweis
  FROM (SELECT DISTINCT company_id FROM ref_prozesse WHERE owner_name IS NOT NULL) c
 CROSS JOIN (VALUES
   ('P-01', 'Sergio Morazán Irias', 'MD',                                    FALSE, NULL, NULL),
   ('P-02', 'Eike Bischof',         'Sr. Consultant — Requirements & Quality', FALSE, NULL,
            'Stand zweimal in owner_name, einmal mit und einmal ohne Rolle.'),
   ('P-03', 'Zakaria Samih',        'Lead DevOps',                           FALSE, NULL, NULL),
   ('P-04', 'Ozan Kiraz',           NULL,                                    FALSE, NULL, NULL),
   ('P-05', 'Mehdi Louali',         NULL,                                    FALSE, NULL, NULL),
   ('P-06', 'Sabrina Disimino',     NULL,                                    FALSE, NULL, NULL),
   ('P-07', 'Simeon Ehmer',         NULL,                                    FALSE, NULL, NULL),
   ('P-08', NULL,                   'externer Steuerberater',                TRUE,  NULL,
            'Name nicht erhoben. Vor der ersten ROI-Rechnung nachtragen.'),
   ('P-09', NULL,                   'externer Datenschutzbeauftragter',      TRUE,  NULL,
            'Name nicht erhoben. In owner_name als „externer DSB" geführt.'),
   ('P-10', NULL,                   'Engagement Manager (rotierend)',        FALSE, NULL,
            'Keine natürliche Person, sondern eine rotierend besetzte Funktion. '
            'Sobald feststeht, wer sie zum Erhebungszeitpunkt innehatte, durch '
            'die betreffende Person ersetzen.')
 ) AS v(person_id, name, funktion, extern, organisation, hinweis)
ON CONFLICT (company_id, person_id) DO NOTHING;


-- ------------------------------------------------------------
-- 2. Zuordnung zu den Kernprozessen
-- ------------------------------------------------------------
-- Der Abgleich läuft über den normalisierten Freitext: Rand-Leerzeichen
-- entfernt, Mehrfach-Leerzeichen auf eines reduziert. Ohne diese Normalisierung
-- scheitert der Vergleich an einem unsichtbaren Zeichen, und zwar still.

WITH zuordnung(quelltext, person_id, beteiligung) AS (VALUES
  ('Eike Bischof',                                                    'P-02', 'eigner'),
  ('Sergio Morazán Irias',                                            'P-01', 'eigner'),
  ('Simeon Ehmer',                                                    'P-07', 'eigner'),
  ('Zakaria Samih',                                                   'P-03', 'eigner'),
  -- zwei interne Eigner nebeneinander
  ('Ozan Kiraz / Mehdi Louali',                                       'P-04', 'eigner'),
  ('Ozan Kiraz / Mehdi Louali',                                       'P-05', 'eigner'),
  -- Funktion als Eigner, Person als Sponsor
  ('Engagement Manager (rotierend) · Sponsor: Sergio Morazán Irias',   'P-10', 'eigner'),
  ('Engagement Manager (rotierend) · Sponsor: Sergio Morazán Irias',   'P-01', 'sponsor'),
  -- intern verantwortlich, extern mitwirkend (Interpretation, siehe Kopf)
  ('externer Steuerberater + Sergio',                                 'P-01', 'eigner'),
  ('externer Steuerberater + Sergio',                                 'P-08', 'mitwirkend'),
  ('Sabrina Disimino / externer DSB',                                 'P-06', 'eigner'),
  ('Sabrina Disimino / externer DSB',                                 'P-09', 'mitwirkend')
)
INSERT INTO prozess_personen (company_id, process_id, person_id, funktion, hinweis)
SELECT p.company_id, p.process_id, z.person_id, z.beteiligung,
       'aus owner_name übernommen am 12.08.2026'
  FROM ref_prozesse p
  JOIN zuordnung z
    ON regexp_replace(btrim(p.owner_name), '\s+', ' ', 'g') = z.quelltext
ON CONFLICT (company_id, process_id, person_id, funktion) DO NOTHING;


-- ------------------------------------------------------------
-- 3. Rollenzuordnung, soweit sie sich aus owner_role ergibt
-- ------------------------------------------------------------
-- Nur wenn beim Mandanten bereits eine Rolle mit passender Bezeichnung gepflegt
-- ist. Sonst bleibt rolle_id leer und wird in der Oberfläche nachgetragen —
-- ohne Rolle keine Kostenklasse und damit kein ROI-Beitrag.

UPDATE ref_personen pe
   SET rolle_id = r.rolle_id
  FROM mandant_rollen r
 WHERE r.company_id = pe.company_id
   AND pe.rolle_id IS NULL
   AND lower(btrim(r.bezeichnung)) = lower(btrim(pe.funktion));

COMMIT;


-- ============================================================
-- 4. KONTROLLE — was ist NICHT angekommen?
-- ============================================================
-- Diese Abfrage muss null Zeilen liefern. Jede Zeile bedeutet: ein Prozess
-- trägt einen Eigner im Freitext, für den es keine Zuordnung gibt — meist ein
-- Tippfehler in der Entscheidungstabelle oben oder ein Wert, der seit der
-- Bestandsaufnahme dazugekommen ist.

\echo '--- 4.1 Prozesse mit owner_name, aber ohne Zuordnung (muss leer sein):'
SELECT p.process_id, p.owner_name
  FROM ref_prozesse p
 WHERE p.owner_name IS NOT NULL
   AND btrim(p.owner_name) <> ''
   AND NOT EXISTS (SELECT 1 FROM prozess_personen pp
                    WHERE pp.company_id = p.company_id
                      AND pp.process_id = p.process_id)
 ORDER BY 1;

\echo '--- 4.2 Ergebnis je Prozess:'
SELECT process_id, anz_eigner, anz_beteiligt, befund FROM v_personen_abdeckung ORDER BY 1;

\echo '--- 4.3 Personenregister:'
SELECT person_id, coalesce(name, '(ohne Namen)') AS person, funktion, rolle_id, extern
  FROM ref_personen ORDER BY 1;

\echo '--- 4.4 Personen ohne Rollenzuordnung (= ohne Kostenklasse, ROI-relevant):'
SELECT person_id, coalesce(name, funktion) AS person
  FROM ref_personen WHERE rolle_id IS NULL AND aktiv ORDER BY 1;
