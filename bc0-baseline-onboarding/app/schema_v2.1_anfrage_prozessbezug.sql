-- ============================================================
-- BC0 — v2.1: Prozessbezug der Anfrage
-- Stand: 22.08.2026 · Autor: Simeon Ehmer
--
-- ============================================================
--  FREIGEGEBEN AM 27.08.2026 — der Dreier-Termin entfaellt.
--
--  Bis dahin stand hier "erst nach dem Dreier-Termin einspielen".
--  Der Termin stand seit dem 11.08. an und kam nicht zustande; die
--  Entscheidung, auf die er warten sollte, ist inzwischen anders
--  gefallen: Die Anfrage entsteht in der PWA und IST der Trigger fuer
--  BC1. Damit ist der Prozessbezug keine Vorabfrage mehr, sondern
--  Bestandteil der Eingabemaske.
-- ============================================================
--
-- Rein additiv. Nimmt nichts weg, aendert keinen Primaerschluessel,
-- beruehrt keine bestehende Zeile ausser durch das Setzen der neuen
-- Spalten.
--
-- WOZU
--   `ref_anfragen` haelt seit v1.4 die externe Anfrage an das CoE, aber
--   ohne Prozessbezug. Der Bezug Anfrage -> Teilprozess entsteht heute
--   erst in `gate_ereignisse`, also am Ende der Kette. BC1 startet sein
--   Interview damit ohne Vorbelegung und muss den Prozess erfragen.
--
-- DIE REGEL, DIE HIER DURCHGESETZT WIRD
--   Ohne definierten Prozess keine Anfrage. Nicht als Absprache, sondern
--   als NOT NULL mit Fremdschluessel — ADR-003 Regel 4: Verbindliches
--   wird in der Datenbank durchgesetzt, nicht im Weg dorthin.
--
--   Bewusst NICHT durchgesetzt wird der Reifegrad. Die Struktur muss
--   stehen, die Bewertung darf nachkommen: 1.500 Bewertungen mit
--   Belegpflicht als Vorbedingung fuer die erste Anfrage waere im
--   Echtbetrieb keine Antwort. Das Gate sperrt ohnehin, solange ein
--   Teilprozess weniger als 27 von 30 Items traegt — eine zweite Sperre
--   vorne braucht es nicht.
--
-- WARUM DER KERNPROZESS PFLICHT IST UND DER TEILPROZESS NICHT
--   Auf Kernprozessebene ist ein Anliegen formulierbar. Der Teilprozess
--   ist ERGEBNIS des Interviews, nicht seine Voraussetzung — ihn zur
--   Pflicht zu machen hiesse, die Antwort vor der Frage zu verlangen.
--
-- EINE ANFRAGE KANN MEHRERE TEILPROZESSE BETREFFEN
--   `sub_process_id` ist die ERSTZUORDNUNG, nicht die abschliessende.
--   Der Bezug Anfrage -> BC1-Profil ist 1:n; jedes Profil traegt seinen
--   eigenen `focus_step_id`.
--
-- Gegenproben am Dateiende.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Spalten
-- ------------------------------------------------------------
ALTER TABLE ref_anfragen ADD COLUMN IF NOT EXISTS process_id       TEXT;
ALTER TABLE ref_anfragen ADD COLUMN IF NOT EXISTS sub_process_id   TEXT;
ALTER TABLE ref_anfragen ADD COLUMN IF NOT EXISTS zuordnung_quelle TEXT;

COMMENT ON COLUMN ref_anfragen.process_id IS
  'Kernprozess, auf den sich die Anfrage bezieht. PFLICHT: ohne '
  'definierten Prozess keine Anfrage. Ohne ID gibt es nichts, woran ein '
  'Beleg haengen koennte (ADR-005), und keinen Messpunkt fuer das Gate.';

COMMENT ON COLUMN ref_anfragen.sub_process_id IS
  'Teilprozess, falls beim Eingang schon bekannt. ERSTZUORDNUNG, nicht '
  'abschliessend — eine Anfrage kann mehrere Teilprozesse betreffen, und '
  'der Fokus-Schritt entsteht endgueltig im Interview. Leer ist der '
  'Normalfall.';

COMMENT ON COLUMN ref_anfragen.zuordnung_quelle IS
  'Woher die Zuordnung stammt (ADR-005, Herkunftsnachweis): '
  'anfrage = der Annehmende hat sie in der Maske gesetzt · '
  'vorschlag_bc0 = regelbasierter Stichwortabgleich von BC0, bestaetigt · '
  'vorschlag_bc1 = semantisch von BC1 vorgeschlagen und bestaetigt · '
  'interview = im Trichter gewaehlt. '
  'Macht bei einer Fehlzuordnung unterscheidbar, ob jemand sich geirrt '
  'hat oder ob der Vorschlag schlecht war.';

-- ------------------------------------------------------------
-- 2. Fremdschluessel — Verbund, weil unsere Primaerschluessel
--    zusammengesetzt sind. Ein Einzelspalten-FK waere weder anlegbar
--    noch mandantensicher.
-- ------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_anfrage_prozess') THEN
    ALTER TABLE ref_anfragen ADD CONSTRAINT fk_anfrage_prozess
      FOREIGN KEY (company_id, process_id)
      REFERENCES ref_prozesse (company_id, process_id) ON DELETE RESTRICT;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_anfrage_teilprozess') THEN
    ALTER TABLE ref_anfragen ADD CONSTRAINT fk_anfrage_teilprozess
      FOREIGN KEY (company_id, sub_process_id)
      REFERENCES ref_teilprozesse (company_id, sub_process_id) ON DELETE SET NULL;
  END IF;
END $$;

-- ON DELETE RESTRICT beim Kernprozess, SET NULL beim Teilprozess:
-- Ein Kernprozess, auf den eine Anfrage zeigt, darf nicht verschwinden —
-- sonst stuende die Anfrage ohne den Bezug da, der sie erst zulaessig
-- macht. Beim Teilprozess ist das Wegfallen verkraftbar, die Anfrage
-- bleibt am Kernprozess haengen.

-- ------------------------------------------------------------
-- 3. Der Teilprozess muss zum Kernprozess gehoeren
-- ------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_anfrage_tp_gehoert_kp') THEN
    ALTER TABLE ref_anfragen ADD CONSTRAINT ck_anfrage_tp_gehoert_kp
      CHECK (sub_process_id IS NULL
             OR (process_id IS NOT NULL AND sub_process_id LIKE process_id || '.%'));
  END IF;
END $$;

-- Ohne diese Bedingung liessen sich KP-02 und KP-07.TP-3 an dieselbe
-- Anfrage haengen. Beide Fremdschluessel waeren erfuellt, der Datensatz
-- waere trotzdem sinnlos — und niemand wuerde es merken.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_anfrage_zuordnung_quelle') THEN
    ALTER TABLE ref_anfragen ADD CONSTRAINT ck_anfrage_zuordnung_quelle
      CHECK (zuordnung_quelle IS NULL
             OR zuordnung_quelle IN ('anfrage','vorschlag_bc0','vorschlag_bc1','interview'));
  END IF;
END $$;

-- Bewusst CHECK und kein ENUM: Eine weitere Quelle ist eine additive
-- Erweiterung, ein ENUM-Wert waere ein Typumbau. Gleiche Begruendung
-- wie bei BC1s Statusfeld.

-- Nachtrag 27.08.2026 — vierter Wert `vorschlag_bc0`.
--
-- Der Trichter wird als 1+3+4 zusammen gebaut. Stufe 1 ist die Zuordnung in
-- der Anfragemaske (`anfrage`), Stufe 4 die Auswahl im Interview
-- (`interview`). Stufe 3, der Abgleich des Anliegens gegen die
-- Prozessbeschreibungen, findet an ZWEI Stellen statt und muss deshalb
-- unterscheidbar sein:
--
--   vorschlag_bc0  Regelbasierter Stichwortabgleich in BC0 gegen
--                  ref_prozesse.beschreibung, trigger_text und die
--                  Teilprozessnamen DIESES Mandanten. OHNE Sprachmodell —
--                  BC0 bleibt LLM-frei, aus demselben Grund, aus dem die
--                  Befundsaetze des Reifegradberichts regelbasiert entstehen:
--                  Die Herkunft jeder Aussage muss nachweisbar bleiben.
--   vorschlag_bc1  Semantischer Vergleich durch BC1s Bot, der denselben
--                  Mandanten kennt und dieselben Beschreibungen liest.
--
-- Warum die Unterscheidung zaehlt: Bei einer Fehlzuordnung ist sonst nicht
-- erkennbar, OB die Regel zu grob war oder das Sprachmodell danebenlag.
-- Zwei verschiedene Fehlerursachen, zwei verschiedene Reparaturen.
--
-- Beide Vorschlaege sind BESTAETIGUNGSPFLICHTIG. Eine falsche
-- Vorab-Festlegung ist schlechter als gar keine: Dann laeuft ein
-- vollstaendiges Interview auf dem falschen Prozess, und es faellt erst
-- am Gate auf.

-- ------------------------------------------------------------
-- 4. Pflicht — erst wenn der Bestand sie erfuellt
-- ------------------------------------------------------------
DO $$
DECLARE offen INTEGER;
BEGIN
  SELECT count(*) INTO offen FROM ref_anfragen WHERE process_id IS NULL;

  IF offen = 0 THEN
    ALTER TABLE ref_anfragen ALTER COLUMN process_id       SET NOT NULL;
    ALTER TABLE ref_anfragen ALTER COLUMN zuordnung_quelle SET NOT NULL;
    RAISE NOTICE 'process_id und zuordnung_quelle sind jetzt Pflicht.';
  ELSE
    RAISE NOTICE 'NOT NULL NICHT gesetzt: % Anfrage(n) ohne Prozessbezug. '
                 'Erst nachtragen, dann diesen Block erneut ausfuehren.', offen;
  END IF;
END $$;

-- Bewusst kein Backfill mit einem Platzhalter. Ein erfundener
-- Prozessbezug saehe aus wie ein erhobener — genau das, was ADR-003
-- ausschliesst.

-- ------------------------------------------------------------
-- 5. Lesesicht fuer BC1
-- ------------------------------------------------------------
-- `ref_anfragen` bleibt fuer bc_leser gesperrt: der Originaltext kann
-- personenbezogene Daten enthalten. Der Prozessbezug enthaelt keine —
-- er besteht aus IDs. Diese Sicht gibt genau ihn heraus und sonst
-- nichts, damit BC1 sein Interview vorbelegen kann, ohne den Volltext
-- zu sehen.
CREATE OR REPLACE VIEW v_anfrage_prozessbezug AS
SELECT company_id,
       anfrage_id,
       process_id,
       sub_process_id,
       zuordnung_quelle,
       eingang_am
FROM   ref_anfragen;

COMMENT ON VIEW v_anfrage_prozessbezug IS
  'Prozessbezug einer Anfrage ohne Originaltext, ohne steller_id, ohne '
  'hinweis. Fuer BC1 zur Vorbelegung des Interviews. Der Volltext bleibt '
  'in ref_anfragen und dort fuer bc_leser gesperrt.';

GRANT SELECT ON v_anfrage_prozessbezug TO bc_leser;

COMMIT;

-- ============================================================
-- GEGENPROBEN
-- ============================================================
-- Erwartet: drei Spalten
-- SELECT column_name, is_nullable FROM information_schema.columns
--  WHERE table_name = 'ref_anfragen'
--    AND column_name IN ('process_id','sub_process_id','zuordnung_quelle')
--  ORDER BY column_name;
--
-- Erwartet: vier Constraints
-- SELECT conname FROM pg_constraint
--  WHERE conrelid = 'ref_anfragen'::regclass
--    AND conname IN ('fk_anfrage_prozess','fk_anfrage_teilprozess',
--                    'ck_anfrage_tp_gehoert_kp','ck_anfrage_zuordnung_quelle')
--  ORDER BY conname;
--
-- Erwartet: FEHLER (Teilprozess gehoert nicht zum Kernprozess)
-- INSERT INTO ref_anfragen(company_id,anfrage_id,originaltext,eingang_am,
--                          process_id,sub_process_id,zuordnung_quelle)
-- VALUES ('<mandant>','A-2026-99','Probe',current_date,
--         'KP-02','KP-07.TP-3','anfrage');
--
-- Erwartet: Sicht liefert Zeilen, ref_anfragen bleibt gesperrt
-- SET ROLE bc1_role;
-- SELECT count(*) FROM v_anfrage_prozessbezug;   -- geht
-- SELECT count(*) FROM ref_anfragen;             -- permission denied
-- RESET ROLE;
-- ============================================================
