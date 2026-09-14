-- ============================================================
-- BC0 Onboarding — Schema-Nachtrag v1.3 (Teil C): Erhebungen
-- Stand: 13.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- Grundlage: ADR-004, Abschnitt 2.5 · Issue #149 · Vorbereitung für #143
--
-- ============================================================
--  ACHTUNG — DIES IST DER EINZIGE NACHTRAG, DER BESTANDSDATEN ÄNDERT.
--  BACKUP VORHER. Der Primärschlüssel von 600 produktiven Bewertungszeilen
--  wird erweitert, und ein Fremdschlüssel aus bewertung_belege zieht mit.
-- ============================================================
--
-- WARUM
--   Eine Bewertung weiß heute nur, *wann* sie entstand (`bewertet_am`), nicht
--   *zu welcher Erhebung* sie gehört. Die geplante Nacherhebung von KP-05 bis
--   KP-10 (#143) würde deshalb dieselben IDs erzeugen wie im Mai — und der
--   bisherige Stand wäre stillschweigend überschrieben.
--
--   Zwei Folgen daraus, beide untragbar:
--     * Eine Gate-Freigabe ist nicht reproduzierbar. Sie hält in
--       `gate_ereignisse.grundlage` den Datenstand fest, auf den sie sich
--       bezieht — aber ohne Erhebungsbezug lässt sich dieser Stand später nicht
--       mehr herstellen.
--     * Ein Vorher-Nachher-Vergleich ist unmöglich. Genau der ist aber die
--       Voraussetzung jeder Wirkungsmessung nach einer Automatisierung.
--
-- WAS PASSIERT
--   1. Neue Tabelle `ref_erhebungen` (`E-2026-05`, `E-2026-09`, …)
--   2. `bitkom_bewertungen` und `bewertung_belege` bekommen `erhebung_id`
--   3. Der Bestand wird einer Erhebung zugeordnet, abgeleitet aus dem
--      frühesten `bewertet_am` je Mandant
--   4. `erhebung_id` tritt in beide Primärschlüssel ein
--   5. Die sieben auswertenden Views filtern auf die maßgebliche Erhebung —
--      ihre Spalten bleiben unverändert, damit nichts nachgezogen werden muss
--
-- REIHENFOLGE IST ZWINGEND. Das Skript läuft in einer Transaktion; bricht es
--   ab, ist nichts geändert.
--
-- WIEDERHOLBAR. Ein zweiter Lauf erkennt den bereits erfolgten Umbau und
--   überspringt ihn.
--
-- EINSPIELEN (nach dem Backup):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema_v1.3_teil_c_erhebungen.sql
-- ============================================================

BEGIN;

-- ============================================================
-- 25. ERHEBUNGEN
-- ============================================================
-- Eine Erhebung ist ein Messzeitpunkt mit Methode und Stand. Die ID ist
-- sprechend (`E-JJJJ-MM`), weil sie in Gesprächen und Gate-Belegen auftaucht
-- (ADR-004 R1).
--
-- `status` steuert, welche Erhebung maßgeblich ist:
--   offen           — wird gerade erhoben; neue Bewertungen landen hier
--   abgeschlossen   — fertig, Grundlage für Freigaben
--   verworfen       — Fehlversuch, wird von den Auswertungen ignoriert

CREATE TABLE IF NOT EXISTS ref_erhebungen (
  company_id   UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  erhebung_id  TEXT NOT NULL CHECK (erhebung_id ~ '^E-[0-9]{4}-[0-9]{2}$'),
  bezeichnung  TEXT NOT NULL,
  stand        DATE NOT NULL,
  status       TEXT NOT NULL DEFAULT 'offen'
               CHECK (status IN ('offen','abgeschlossen','verworfen')),
  methode      TEXT,
  hinweis      TEXT,
  angelegt_am  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, erhebung_id)
);

COMMENT ON TABLE ref_erhebungen IS
  'Messzeitpunkte je Mandant (ADR-004, 2.5). Jede Einzelbewertung gehoert zu '
  'genau einer Erhebung. Ohne diesen Bezug wuerde eine Nacherhebung den '
  'bisherigen Stand ueberschreiben und eine Gate-Freigabe waere nicht '
  'reproduzierbar.';
COMMENT ON COLUMN ref_erhebungen.status IS
  'offen = neue Bewertungen landen hier · abgeschlossen = Grundlage fuer '
  'Freigaben · verworfen = wird von den Auswertungen ignoriert';

CREATE INDEX IF NOT EXISTS idx_erhebung_company ON ref_erhebungen(company_id, stand DESC);


-- ============================================================
-- 26. BESTAND EINER ERHEBUNG ZUORDNEN
-- ============================================================
-- Je Mandant mit Bewertungen wird eine Erhebung angelegt, deren Kennung sich
-- aus dem *fruehesten* `bewertet_am` ergibt. Fuer NoroAI ist das der Mai 2026.
-- Sie gilt als abgeschlossen — die Erhebung ist vorbei, der Reifegradbericht
-- liegt vor.

INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, stand, status, methode, hinweis)
SELECT q.company_id,
       'E-' || to_char(q.erste, 'YYYY-MM'),
       'Ersterhebung ' || to_char(q.erste, 'TMMonth YYYY'),
       q.letzte::date,
       'abgeschlossen',
       'Self-Rating je Teilprozess, 30 Bitkom-Items, Belegpflicht',
       'Rueckwirkend angelegt am 13.08.2026 beim Umbau auf Erhebungsbezug '
       || '(Schema v1.3 Teil C). Kennung abgeleitet aus dem fruehesten bewertet_am.'
  FROM (SELECT company_id, min(bewertet_am) AS erste, max(bewertet_am) AS letzte
          FROM bitkom_bewertungen
         GROUP BY company_id) q
ON CONFLICT (company_id, erhebung_id) DO NOTHING;


-- ============================================================
-- 27. SPALTE ERGÄNZEN UND FÜLLEN
-- ============================================================
ALTER TABLE bitkom_bewertungen ADD COLUMN IF NOT EXISTS erhebung_id TEXT;
ALTER TABLE bewertung_belege    ADD COLUMN IF NOT EXISTS erhebung_id TEXT;

-- Bewertungen: jede Zeile bekommt die Erhebung ihres Mandanten. Zu diesem
-- Zeitpunkt gibt es je Mandant genau eine, der Zusammenhang ist also eindeutig.
UPDATE bitkom_bewertungen b
   SET erhebung_id = e.erhebung_id
  FROM ref_erhebungen e
 WHERE e.company_id = b.company_id
   AND b.erhebung_id IS NULL;

-- Belege ziehen die Erhebung ihrer Bewertung nach.
UPDATE bewertung_belege bl
   SET erhebung_id = b.erhebung_id
  FROM bitkom_bewertungen b
 WHERE b.company_id = bl.company_id
   AND b.id = bl.bewertung_id
   AND bl.erhebung_id IS NULL;

-- Sicherung: bleibt irgendwo NULL, bricht das Skript hier ab statt einen
-- kaputten Primaerschluessel zu bauen.
DO $$
DECLARE offen_b BIGINT; offen_l BIGINT;
BEGIN
  SELECT count(*) INTO offen_b FROM bitkom_bewertungen WHERE erhebung_id IS NULL;
  SELECT count(*) INTO offen_l FROM bewertung_belege   WHERE erhebung_id IS NULL;
  IF offen_b > 0 OR offen_l > 0 THEN
    RAISE EXCEPTION 'Zuordnung unvollstaendig: % Bewertungen und % Belege ohne '
                    'erhebung_id. Umbau abgebrochen, nichts geaendert.',
                    offen_b, offen_l;
  END IF;
  RAISE NOTICE 'Zuordnung vollstaendig.';
END $$;

ALTER TABLE bitkom_bewertungen ALTER COLUMN erhebung_id SET NOT NULL;
ALTER TABLE bewertung_belege    ALTER COLUMN erhebung_id SET NOT NULL;

COMMENT ON COLUMN bitkom_bewertungen.erhebung_id IS
  'Zu welcher Erhebung diese Bewertung gehoert. Teil des Primaerschluessels — '
  'derselbe Item-Schluessel darf in einer spaeteren Erhebung erneut vorkommen.';


-- ============================================================
-- 28. PRIMÄRSCHLÜSSEL ERWEITERN
-- ============================================================
-- Reihenfolge: erst den Fremdschluessel loesen, dann beide Primaerschluessel
-- umbauen, dann den Fremdschluessel neu setzen. Andernfalls verweigert
-- PostgreSQL das Loeschen des Schluessels, auf den verwiesen wird.
--
-- Der Block laeuft nur, wenn der Umbau noch nicht erfolgt ist — daran erkennbar,
-- dass erhebung_id noch nicht im Primaerschluessel steht.

DO $$
DECLARE
  pk_name  TEXT;
  uq_name  TEXT;
  fk_name  TEXT;
  schon_da BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
      FROM pg_constraint con
      JOIN pg_attribute a
        ON a.attrelid = con.conrelid AND a.attnum = ANY (con.conkey)
     WHERE con.conrelid = 'bitkom_bewertungen'::regclass
       AND con.contype = 'p'
       AND a.attname = 'erhebung_id'
  ) INTO schon_da;

  IF schon_da THEN
    RAISE NOTICE 'Primaerschluessel enthaelt erhebung_id bereits — Umbau uebersprungen.';
    RETURN;
  END IF;

  -- 28.1 Fremdschluessel von bewertung_belege loesen
  SELECT conname INTO fk_name
    FROM pg_constraint
   WHERE conrelid = 'bewertung_belege'::regclass
     AND contype = 'f'
     AND confrelid = 'bitkom_bewertungen'::regclass;
  IF fk_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE bewertung_belege DROP CONSTRAINT %I', fk_name);
    RAISE NOTICE 'Fremdschluessel % geloest.', fk_name;
  END IF;

  -- 28.2 Eindeutigkeit je Teilprozess und Item: gilt kuenftig je Erhebung
  SELECT conname INTO uq_name
    FROM pg_constraint
   WHERE conrelid = 'bitkom_bewertungen'::regclass AND contype = 'u';
  IF uq_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE bitkom_bewertungen DROP CONSTRAINT %I', uq_name);
  END IF;

  -- 28.3 Primaerschluessel bitkom_bewertungen
  SELECT conname INTO pk_name
    FROM pg_constraint
   WHERE conrelid = 'bitkom_bewertungen'::regclass AND contype = 'p';
  EXECUTE format('ALTER TABLE bitkom_bewertungen DROP CONSTRAINT %I', pk_name);
  ALTER TABLE bitkom_bewertungen
    ADD CONSTRAINT bitkom_bewertungen_pkey PRIMARY KEY (company_id, erhebung_id, id);
  ALTER TABLE bitkom_bewertungen
    ADD CONSTRAINT bitkom_bewertungen_je_item UNIQUE (company_id, erhebung_id, sub_process_id, item_nr);
  ALTER TABLE bitkom_bewertungen
    ADD CONSTRAINT bitkom_bewertungen_erhebung_fkey
    FOREIGN KEY (company_id, erhebung_id)
    REFERENCES ref_erhebungen(company_id, erhebung_id) ON DELETE CASCADE;

  -- 28.4 Primaerschluessel bewertung_belege
  SELECT conname INTO pk_name
    FROM pg_constraint
   WHERE conrelid = 'bewertung_belege'::regclass AND contype = 'p';
  EXECUTE format('ALTER TABLE bewertung_belege DROP CONSTRAINT %I', pk_name);
  ALTER TABLE bewertung_belege
    ADD CONSTRAINT bewertung_belege_pkey PRIMARY KEY (company_id, erhebung_id, bewertung_id, doc_id);
  ALTER TABLE bewertung_belege
    ADD CONSTRAINT bewertung_belege_bewertung_fkey
    FOREIGN KEY (company_id, erhebung_id, bewertung_id)
    REFERENCES bitkom_bewertungen(company_id, erhebung_id, id) ON DELETE CASCADE;

  RAISE NOTICE 'Primaerschluessel erweitert, Fremdschluessel neu gesetzt.';
END $$;

CREATE INDEX IF NOT EXISTS idx_bew_erhebung ON bitkom_bewertungen(company_id, erhebung_id);


-- ============================================================
-- 29. DIE MASSGEBLICHE ERHEBUNG
-- ============================================================
-- Alle auswertenden Views arbeiten auf genau einer Erhebung je Mandant. Ohne
-- diese Einschraenkung wuerde eine Nacherhebung neben der alten mitgezaehlt und
-- jeder Mittelwert waere eine Mischung aus zwei Zeitpunkten.
--
-- Maßgeblich ist die jüngste nicht verworfene Erhebung. Bewusst nicht „die
-- jüngste abgeschlossene": Während einer laufenden Erhebung soll die Oberfläche
-- zeigen, was gerade erfasst wird, nicht den Vorstand.

CREATE OR REPLACE VIEW v_erhebung_aktuell AS
SELECT company_id, erhebung_id, bezeichnung, stand, status
  FROM (SELECT e.*,
               row_number() OVER (PARTITION BY e.company_id
                                  ORDER BY e.stand DESC, e.erhebung_id DESC) AS rang
          FROM ref_erhebungen e
         WHERE e.status <> 'verworfen') t
 WHERE rang = 1;

COMMENT ON VIEW v_erhebung_aktuell IS
  'Je Mandant die juengste nicht verworfene Erhebung. Hierhin schreibt die '
  'Anwendung neue Bewertungen. NICHT die Filtergrundlage der Auswertungen — '
  'siehe v_bewertung_aktuell und den Hinweis dort.';


-- ------------------------------------------------------------
-- 29.1 Der maßgebliche Stand je Einzelbewertung
-- ------------------------------------------------------------
-- Naheliegend waere, die Auswertungen auf die juengste Erhebung des Mandanten
-- zu filtern. Das ist falsch, und der Fehler faellt erst bei der ersten
-- Nacherhebung auf:
--
--   Wird im September nur KP-05 bis KP-10 erhoben, hat die September-Erhebung
--   fuer KP-01 bis KP-04 keine Zeilen. Ein Filter auf „juengste Erhebung des
--   Mandanten" liesse diese vier Prozesse aus jeder Auswertung verschwinden —
--   samt Reifegradbericht und Gate-Stand.
--
-- Maßgeblich ist deshalb **je Einzelbewertung** die juengste Erhebung, die
-- diesen Teilprozess und dieses Item tatsaechlich bewertet hat. Der aktuelle
-- Stand ist damit eine Zusammensetzung: nachtraeglich erhobene Prozesse mit
-- neuen Werten, unveraenderte mit ihren alten. Genau das ist gemeint, wenn
-- jemand fragt „wie steht es heute".

CREATE OR REPLACE VIEW v_bewertung_aktuell AS
SELECT company_id, erhebung_id, id, sub_process_id, item_nr,
       stufe, beleg, quelle, bewerter, bewertet_am
  FROM (SELECT b.company_id, b.erhebung_id, b.id, b.sub_process_id, b.item_nr,
               b.stufe, b.beleg, b.quelle, b.bewerter, b.bewertet_am,
               row_number() OVER (PARTITION BY b.company_id, b.sub_process_id, b.item_nr
                                  ORDER BY e.stand DESC, e.erhebung_id DESC) AS rang
          FROM bitkom_bewertungen b
          JOIN ref_erhebungen e
            ON e.company_id = b.company_id AND e.erhebung_id = b.erhebung_id
         WHERE e.status <> 'verworfen') t
 WHERE rang = 1;

COMMENT ON VIEW v_bewertung_aktuell IS
  'Je Mandant, Teilprozess und Item die juengste nicht verworfene Bewertung. '
  'Filtergrundlage aller auswertenden Views. Eine Nacherhebung einzelner '
  'Prozesse ueberschreibt dadurch nur diese — die uebrigen behalten ihren Stand.';


-- ============================================================
-- 30. AUSWERTENDE VIEWS AUF DIE MASSGEBLICHE ERHEBUNG EINSCHRÄNKEN
-- ============================================================
-- Die Spaltenlisten bleiben unveraendert. Wer diese Views liest — die
-- Anwendung, BC1 bis BC4 — muss nichts nachziehen.

CREATE OR REPLACE VIEW v_reifegrad_tp AS
SELECT b.company_id, b.sub_process_id,
       round(avg(b.stufe), 2) AS avg_stufe,
       count(*) AS n_items
  FROM v_bewertung_aktuell b
 GROUP BY b.company_id, b.sub_process_id;

CREATE OR REPLACE VIEW v_reifegrad_kp AS
SELECT b.company_id,
       "left"(b.sub_process_id::text, 5) AS process_id,
       round(avg(b.stufe), 2) AS avg_stufe,
       count(*) AS n_items
  FROM v_bewertung_aktuell b
 GROUP BY b.company_id, ("left"(b.sub_process_id::text, 5));

CREATE OR REPLACE VIEW v_reifegrad_kp_dim AS
SELECT b.company_id,
       "left"(b.sub_process_id::text, 5) AS process_id,
       ri.dimension,
       round(avg(b.stufe), 2) AS avg_stufe
  FROM v_bewertung_aktuell b
  JOIN ref_items ri ON ri.item_nr = b.item_nr
 GROUP BY b.company_id, ("left"(b.sub_process_id::text, 5)), ri.dimension;

-- LEFT JOIN: ein Mandant ohne Bewertungen muss in der Liste bleiben. Die
-- Erhebungsbedingung gehoert deshalb in die Join-Bedingung, nicht in ein WHERE.
CREATE OR REPLACE VIEW v_reifegrad_company AS
SELECT c.company_id, c.name,
       round(avg(b.stufe), 2) AS gesamt_reifegrad,
       count(b.*) AS n_bewertungen,
       round(100.0 * sum(CASE WHEN length(btrim(b.beleg)) > 0 THEN 1 ELSE 0 END)::numeric
             / NULLIF(count(b.*), 0)::numeric, 0) AS beleg_quote_pct
  FROM companies c
  LEFT JOIN v_bewertung_aktuell b ON b.company_id = c.company_id
 GROUP BY c.company_id, c.name;

CREATE OR REPLACE VIEW v_prozessautomatisierung AS
SELECT b.company_id, b.sub_process_id,
       "left"(b.sub_process_id::text, 5) AS process_id,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[1,2])),   2) AS technologiebasis,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[3,4])),   2) AS tools_im_prozess,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[5,6])),   2) AS systemintegration,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[13,14])), 2) AS prozessbeschreibung,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[15,16])), 2) AS ausfuehrung,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[17,18])), 2) AS compliance
  FROM v_bewertung_aktuell b
 GROUP BY b.company_id, b.sub_process_id;

CREATE OR REPLACE VIEW v_crossfunktional AS
SELECT b.company_id,
       "left"(b.sub_process_id::text, 5) AS process_id,
       rp.process_name, rp.owner_name, rp.input_text, rp.output_text,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[1,2])),   2) AS technologiebasis,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[3,4])),   2) AS tools_im_prozess,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[5,6])),   2) AS systemintegration,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[7,8])),   2) AS prozessbeschreibung,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[9,10])),  2) AS ausfuehrung,
       round(avg(b.stufe) FILTER (WHERE b.item_nr = ANY (ARRAY[11,12])), 2) AS compliance
  FROM v_bewertung_aktuell b
  LEFT JOIN ref_prozesse rp
         ON rp.company_id = b.company_id
        AND rp.process_id::text = "left"(b.sub_process_id::text, 5)
 GROUP BY b.company_id, ("left"(b.sub_process_id::text, 5)),
          rp.process_name, rp.owner_name, rp.input_text, rp.output_text;

-- WARNUNG, die bisher nirgends stand: diese View gibt `owner_name` im Klartext
-- aus. Sie ist NICHT fuer bc_leser freigegeben und darf es nicht werden —
-- sonst ist die Pseudonymisierung aus ADR-004 R5 an dieser Stelle umgangen.
-- Sie verschwindet mit Teil D, wenn owner_name entfaellt.
COMMENT ON VIEW v_crossfunktional IS
  'ACHTUNG: enthaelt owner_name im Klartext. NICHT an bc_leser freigeben '
  '(ADR-004 R5). Nur fuer die BC0-Anwendung, die als Eigentuemer verbindet.';


-- ============================================================
-- 31. GATE-VIEW NACHZIEHEN
-- ============================================================
-- Gleiche Einschraenkung, gleicher Grund: Das Gate darf nicht ueber zwei
-- Erhebungen hinweg mitteln. Die Erhebungsbedingung steht in der
-- LEFT-JOIN-Bedingung, damit ein Teilprozess ohne Bewertungen als
-- „nicht erhoben" erhalten bleibt.

CREATE OR REPLACE VIEW v_gate_prozessstand AS
WITH tp AS (
  SELECT rt.company_id, rt.process_id, rt.sub_process_id,
         count(b.id) AS items,
         round(avg(b.stufe), 2) AS reifegrad,
         count(*) FILTER (WHERE b.stufe < 3) AS items_unter_3,
         rt.medienbrueche IS NOT NULL AND length(btrim(rt.medienbrueche)) > 0 AS hat_medienbruch
    FROM ref_teilprozesse rt
    LEFT JOIN v_bewertung_aktuell b
           ON b.company_id = rt.company_id
          AND b.sub_process_id::text = rt.sub_process_id::text
   GROUP BY rt.company_id, rt.process_id, rt.sub_process_id, rt.medienbrueche
)
SELECT rp.company_id, rp.process_id, rp.process_name,
       rp.kategorie::text AS kategorie, rp.beschreibung,
       count(tp.sub_process_id) AS teilprozesse,
       sum(tp.items) AS items_gesamt,
       min(tp.items) AS items_schwaechster_tp,
       round(avg(tp.reifegrad), 2) AS reifegrad_kp,
       min(tp.reifegrad) AS reifegrad_schwaechster_tp,
       sum(tp.items_unter_3) AS items_unter_3,
       count(*) FILTER (WHERE tp.hat_medienbruch) AS tp_mit_medienbruch,
       CASE
         WHEN coalesce(count(tp.sub_process_id), 0::bigint) = 0 THEN 'nicht erhoben'
         WHEN coalesce(sum(tp.items), 0::numeric) = 0::numeric THEN 'nicht erhoben'
         WHEN coalesce(min(tp.items), 0::bigint) < 27 THEN 'unvollstaendig'
         WHEN coalesce(min(tp.reifegrad), 0::numeric) < 3.5 THEN 'reifegrad zu niedrig'
         ELSE 'bc0 ok'
       END AS bc0_sperre,
       coalesce(fs.status, 'offen') AS freigabe_status,
       fs.status_seit AS freigabe_seit,
       fs.benutzer_id AS freigabe_durch
  FROM ref_prozesse rp
  LEFT JOIN tp ON tp.company_id = rp.company_id AND tp.process_id::text = rp.process_id::text
  LEFT JOIN v_gate_freigabestand fs
         ON fs.gate = 'bc0-bc2' AND fs.company_id = rp.company_id
        AND fs.objekt_id = rp.process_id::text
 GROUP BY rp.company_id, rp.process_id, rp.process_name, rp.kategorie,
          rp.beschreibung, fs.status, fs.status_seit, fs.benutzer_id;


-- ============================================================
-- 32. VERLAUF ÜBER ERHEBUNGEN — der eigentliche Gewinn
-- ============================================================
-- Erst mit dieser View wird sichtbar, was der ganze Umbau bringt: derselbe
-- Teilprozess über mehrere Messzeitpunkte, mit der Veränderung.

CREATE OR REPLACE VIEW v_reifegrad_verlauf AS
SELECT b.company_id,
       e.erhebung_id,
       e.stand,
       e.status                          AS erhebung_status,
       "left"(b.sub_process_id::text, 5) AS process_id,
       b.sub_process_id,
       round(avg(b.stufe), 2)            AS avg_stufe,
       count(*)                          AS n_items,
       round(avg(b.stufe), 2) - lag(round(avg(b.stufe), 2)) OVER (
         PARTITION BY b.company_id, b.sub_process_id ORDER BY e.stand
       )                                 AS veraenderung
  FROM bitkom_bewertungen b
  JOIN ref_erhebungen e
    ON e.company_id = b.company_id AND e.erhebung_id = b.erhebung_id
 WHERE e.status <> 'verworfen'
 GROUP BY b.company_id, e.erhebung_id, e.stand, e.status, b.sub_process_id;

COMMENT ON VIEW v_reifegrad_verlauf IS
  'Reifegrad je Teilprozess ueber alle Erhebungen, mit der Veraenderung zur '
  'vorherigen. Grundlage der Wirkungsmessung nach einer Automatisierung.';


-- ============================================================
-- 33. RECHTE
-- ============================================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
    GRANT SELECT ON ref_erhebungen, v_erhebung_aktuell, v_bewertung_aktuell,
                    v_reifegrad_verlauf TO bc_leser;
    RAISE NOTICE 'Leserechte fuer Erhebungen gesetzt.';
  ELSE
    RAISE NOTICE 'Rolle bc_leser nicht vorhanden — Rechteblock uebersprungen.';
  END IF;
END $$;

COMMIT;


-- ============================================================
-- 34. KONTROLLE
-- ============================================================
\echo '--- 34.1 Erhebungen:'
SELECT company_id, erhebung_id, bezeichnung, stand, status FROM ref_erhebungen ORDER BY 1, 3;

\echo '--- 34.2 Bewertungen je Erhebung (muss die Gesamtzahl ergeben):'
SELECT erhebung_id, count(*) AS bewertungen FROM bitkom_bewertungen GROUP BY 1 ORDER BY 1;

\echo '--- 34.3 Primaerschluessel jetzt:'
SELECT conrelid::regclass::text AS tabelle, pg_get_constraintdef(oid) AS schluessel
  FROM pg_constraint
 WHERE conrelid IN ('bitkom_bewertungen'::regclass, 'bewertung_belege'::regclass)
   AND contype = 'p' ORDER BY 1;

\echo '--- 34.4 Reifegrade unveraendert? (Sollwerte KP-01 3.19 · KP-02 3.70 · KP-03 3.77 · KP-04 3.88):'
SELECT process_id, avg_stufe, n_items FROM v_reifegrad_kp ORDER BY 1;

\echo '--- 34.5 Gate-Stand unveraendert?'
SELECT process_id, items_gesamt, reifegrad_kp, reifegrad_schwaechster_tp, bc0_sperre
  FROM v_gate_prozessstand ORDER BY 1;
