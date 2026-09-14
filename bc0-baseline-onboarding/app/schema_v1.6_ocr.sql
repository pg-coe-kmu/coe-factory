-- ============================================================
-- BC0 · Schema v1.6 — Beleg-Ingestion Stufe 2: Herkunft und Volltextsuche
-- ============================================================
-- Stand: 18.08.2026 · Simeon Ehmer
--
-- VORAUSSETZUNG: schema_v1.1.1.sql (beleg_dokumente)
--
-- EINSPIELEN:
--   docker run --rm -v /opt/bc0:/sql postgres:17 psql "$DATABASE_URL" -f /sql/schema_v1.6_ocr.sql
--
-- Wiederholbar. Aendert keine Bestandsdaten, entzieht keine Rechte.
--
-- WAS ES LOEST
--   beleg_dokumente haelt seit dem 10.07.2026 die Felder ocr_text, ocr_confidence
--   und extrakt bereit — aber nicht, WIE der Text entstanden ist. Ein verlustfrei
--   aus einer Word-Datei gelesener Text und ein zu 87 % erkannter Scan sehen in
--   der Spalte gleich aus. Nach ADR-005 R2 muss erkennbar bleiben, ob ein Mensch
--   geprueft oder eine Maschine vorgeschlagen hat.
-- ============================================================


-- ============================================================
-- 21. HERKUNFT DES BELEGTEXTES
-- ============================================================

ALTER TABLE beleg_dokumente ADD COLUMN IF NOT EXISTS erkannt_durch TEXT;
ALTER TABLE beleg_dokumente ADD COLUMN IF NOT EXISTS geprueft_von  TEXT;
ALTER TABLE beleg_dokumente ADD COLUMN IF NOT EXISTS geprueft_am   TIMESTAMPTZ;

COMMENT ON COLUMN beleg_dokumente.erkannt_durch IS
  'Was den Text erzeugt hat: office (XML aus docx/xlsx/pptx), pdftotext (PDF mit '
  'vorhandener Textebene) oder der Name samt Version des Erkenners, z. B. '
  'paddleocr-3.0. Die ersten beiden Wege sind VERLUSTFREI, der dritte nicht — '
  'ohne diese Angabe ist der Unterschied spaeter nicht mehr feststellbar.';

COMMENT ON COLUMN beleg_dokumente.geprueft_von IS
  'Wer den erkannten Text bestaetigt hat. Leer heisst: von keinem Menschen '
  'angesehen. Das ist die Mindestanforderung aus ADR-005 R2 — es muss erkennbar '
  'sein, ob ein Mensch geprueft oder eine Maschine vorgeschlagen hat.';

COMMENT ON COLUMN beleg_dokumente.ocr_confidence IS
  'Vertrauenswert des Erkenners, 0.000 bis 1.000. Bei verlustfreier Extraktion '
  'ausdruecklich 1.000 — damit trennt WHERE ocr_confidence = 1.0 die sicheren '
  'Belege von den erkannten, ohne dass ein zweites Feld noetig waere.';

-- Ein Belegtext ohne Angabe, wie er entstand, soll es kuenftig nicht mehr geben.
-- Bestandszeilen bleiben unberuehrt: Die Bedingung greift nur, wenn ocr_text
-- gesetzt ist UND erkannt_durch fehlt — und wird als NOT VALID eingefuehrt,
-- damit vorhandene Zeilen nicht nachtraeglich ungueltig werden.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_beleg_herkunft') THEN
    ALTER TABLE beleg_dokumente ADD CONSTRAINT ck_beleg_herkunft
      CHECK (ocr_text IS NULL OR erkannt_durch IS NOT NULL) NOT VALID;
  END IF;
END $$;


-- ============================================================
-- 22. VOLLTEXTSUCHE
-- ============================================================
-- Deutsche Konfiguration: Stammformenreduktion und Stoppwoerter passen zur
-- Sprache der Belege. Der Index ist eine generierte Spalte, damit er sich bei
-- jedem Schreibvorgang selbst nachzieht — kein Trigger, keine Pflege.

ALTER TABLE beleg_dokumente
  ADD COLUMN IF NOT EXISTS such_vektor tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('german', coalesce(filename, '')), 'A') ||
    setweight(to_tsvector('german', coalesce(ocr_text, '')),  'B')
  ) STORED;

COMMENT ON COLUMN beleg_dokumente.such_vektor IS
  'Volltextindex ueber Dateiname (Gewicht A) und Belegtext (Gewicht B). Der '
  'Dateiname wiegt schwerer, weil er meist absichtlich vergeben wurde und der '
  'Belegtext auch Beiwerk enthaelt.';

CREATE INDEX IF NOT EXISTS idx_beleg_volltext
  ON beleg_dokumente USING GIN (such_vektor);


-- ============================================================
-- 23. WAS AUSWERTBAR WIRD
-- ============================================================

CREATE OR REPLACE VIEW v_beleg_erfassungsstand AS
SELECT
  company_id,
  count(*)                                                        AS belege,
  count(*) FILTER (WHERE ocr_text IS NOT NULL)                    AS mit_text,
  count(*) FILTER (WHERE ocr_confidence = 1.0)                    AS verlustfrei,
  count(*) FILTER (WHERE ocr_confidence < 1.0)                    AS erkannt,
  count(*) FILTER (WHERE ocr_confidence < 0.8)                    AS unsicher,
  count(*) FILTER (WHERE ocr_text IS NOT NULL
                     AND geprueft_von IS NULL)                    AS ungeprueft,
  sum(coalesce(seiten, 0))                                        AS seiten
  FROM beleg_dokumente
 GROUP BY company_id;

COMMENT ON VIEW v_beleg_erfassungsstand IS
  'Wie weit ist die Belegverarbeitung je Mandant. Die Spalte "ungeprueft" ist '
  'die wichtigste: Belege mit Text, auf die noch kein Mensch geschaut hat. Sie '
  'ist der Arbeitsvorrat, nicht ein Fehlerzaehler.';


CREATE OR REPLACE VIEW v_beleg_lesen AS
SELECT
  d.company_id,
  d.doc_id,
  d.ref_id,
  d.filename,
  d.mime_type,
  d.seiten,
  d.ocr_text,
  d.ocr_confidence,
  d.erkannt_durch,
  (d.geprueft_von IS NOT NULL)                                    AS von_mensch_geprueft,
  d.geprueft_am,
  d.status::text                                                  AS status,
  d.uploaded_at,
  CASE
    WHEN d.ocr_text IS NULL              THEN 'kein Text'
    WHEN d.ocr_confidence = 1.0          THEN 'verlustfrei ausgelesen'
    WHEN d.ocr_confidence >= 0.8         THEN 'erkannt'
    ELSE 'erkannt, unsicher — bitte pruefen'
  END                                                             AS belastbarkeit
  FROM beleg_dokumente d;

COMMENT ON VIEW v_beleg_lesen IS
  'Lesesicht fuer BC1 bis BC4. Gibt den Belegtext und seine Belastbarkeit aus, '
  'aber NICHT geprueft_von — wer geprueft hat, ist eine Personenangabe und '
  'bleibt nach ADR-004 R5 in BC0. Dass geprueft wurde, genuegt den anderen.'
  '\n\n'
  'DASS ocr_text HIER STEHT, IST EINE ENTSCHEIDUNG, KEIN VERSEHEN. Der Belegtext '
  'ist Fliesstext und kann Personennamen enthalten, die keine ID traegt. '
  'Vertretbar ist das, weil erstens die Erkennung ausschliesslich lokal laeuft und '
  'nichts den Server verlaesst, und zweitens jede am Prozess beteiligte Person '
  'ohnehin im Entitaetenregister steht (ADR-004): Ein Name im Belegtext ist keine '
  'unbekannte Person, es entsteht kein Zusatzwissen. Siehe die Argumentation in '
  'BC0_OCR_Konzept_Stufe2.md, Abschnitt 6.';


-- ============================================================
-- 24. ENTITAETENERKENNUNG — VORGESEHEN, NICHT AKTIV
-- ============================================================
-- Die KickOff-Vorgabe vom 18.04.2026 nennt "OCR + NER fuer Dokumente". Die
-- Erkennung benannter Entitaeten wird hier VORBEREITET, aber NICHT eingesetzt.
--
-- Warum nicht: siehe BC0_OCR_Konzept_Stufe2.md, Abschnitt 6. Kurz — die
-- Erkennung laeuft lokal, jede beteiligte Person steht im Entitaetenregister,
-- und der einzige verbleibende Fall (ein Dokument, das gar nicht haette
-- hochgeladen werden duerfen) ist organisatorisch besser geloest als durch ein
-- Modell: Hinweis beim Upload, und im Ernstfall loeschen statt markieren.
--
-- Warum trotzdem vorbereitet: Wer die Struktur erst nachtraeglich anlegt, muss
-- ueber bereits verarbeitete Belege migrieren, bei denen niemand mehr weiss, wie
-- sie entstanden sind. Dieselbe Ueberlegung wie beim Pruefpunkt "zulaessigkeit"
-- in Schema v1.4: angelegt mit aktiv = FALSE, Scharfschalten ist ein UPDATE.

ALTER TABLE beleg_dokumente ADD COLUMN IF NOT EXISTS extrakt_durch TEXT;
ALTER TABLE beleg_dokumente ADD COLUMN IF NOT EXISTS extrakt_am    TIMESTAMPTZ;

COMMENT ON COLUMN beleg_dokumente.extrakt_durch IS
  'Was die Befunde in extrakt erzeugt hat, z. B. spacy-de_core_news_lg-3.8. '
  'Bewusst getrennt von erkannt_durch: Texterkennung und Entitaetenerkennung '
  'sind zwei Laeufe, die zu verschiedenen Zeiten und mit verschiedenen '
  'Werkzeugen stattfinden koennen. Bleibt leer, solange NER nicht laeuft.';

COMMENT ON COLUMN beleg_dokumente.extrakt IS
  'Befunde der Entitaetenerkennung, falls sie je aktiviert wird. Festgelegtes '
  'Format, damit spaeter niemand raten muss: '
  '{"person":[{"text":"...","von":123,"bis":140,"score":0.93,"person_id":"P-04"}],'
  '"organisation":[...],"kontakt":[...]} — je Art eine Liste, je Fund die '
  'Fundstelle im ocr_text, der Vertrauenswert und, wenn zuordenbar, die ID aus '
  'dem Entitaetenregister. LEER, solange NER nicht laeuft.';


CREATE TABLE IF NOT EXISTS ref_extrakt_arten (
  art          TEXT    PRIMARY KEY CHECK (art ~ '^[a-z_]{3,20}$'),
  bezeichnung  TEXT    NOT NULL,
  erlaeuterung TEXT,
  aktiv        BOOLEAN NOT NULL DEFAULT FALSE,
  reihenfolge  INTEGER NOT NULL DEFAULT 100
);

COMMENT ON TABLE ref_extrakt_arten IS
  'Welche Arten von Entitaeten in Belegtexten gesucht wuerden. Global, nicht '
  'mandantenbezogen — was gesucht wird, ist eine Methodikfrage. Stand 18.08.2026 '
  'ist KEINE Art aktiv; die Tabelle beschreibt eine Moeglichkeit, keinen Betrieb.';

COMMENT ON COLUMN ref_extrakt_arten.aktiv IS
  'FALSE = vorgesehen, nicht scharf. Vor dem Scharfschalten einer Art ist zu '
  'klaeren, was mit einem Fund geschieht — sperren, schwaerzen, nur kennzeichnen. '
  'Das ist eine Governance-Frage und gehoert zum Datenschutz-Check (#144).';

INSERT INTO ref_extrakt_arten (art, bezeichnung, erlaeuterung, aktiv, reihenfolge) VALUES
  ('person', 'Personenname',
   'Natuerliche Personen im Belegtext. Regelfall: die Person steht bereits im '
   'Entitaetenregister und traegt eine ID — dann ist der Fund eine Zuordnung, '
   'keine neue Information.', FALSE, 10),
  ('organisation', 'Organisation',
   'Firmen, Behoerden, Dienstleister. Fuer sich genommen selten schutzbeduerftig, '
   'in Verbindung mit einer Person schon.', FALSE, 20),
  ('kontakt', 'Kontaktangabe',
   'E-Mail-Adressen und Telefonnummern im Fliesstext. Seit dem 18.08.2026 stehen '
   'dienstliche Kontaktdaten strukturiert in ref_personen — ein Fund hier waere '
   'ein Hinweis auf eine unstrukturierte Dublette.', FALSE, 30),
  ('ort', 'Ort oder Anschrift', NULL, FALSE, 40),
  ('datum', 'Datumsangabe',
   'Nicht schutzbeduerftig, aber nuetzlich: Ein Beleg mit Datum laesst sich einer '
   'Erhebung zuordnen.', FALSE, 50)
ON CONFLICT (art) DO NOTHING;


-- ============================================================
-- RECHTE
-- ============================================================

GRANT SELECT ON v_beleg_lesen             TO bc_leser;
GRANT SELECT ON v_beleg_erfassungsstand   TO bc_leser;
GRANT SELECT ON ref_extrakt_arten         TO bc_leser;

-- beleg_dokumente selbst bleibt zu: storage_key verraet den Ablageort,
-- geprueft_von ist eine Personenangabe.


-- ============================================================
-- KONTROLLE — muss leer bleiben, sobald Stufe 2 laeuft
-- ============================================================
-- Belegtext ohne Angabe, wie er entstand:
--   SELECT doc_id, filename FROM beleg_dokumente
--    WHERE ocr_text IS NOT NULL AND erkannt_durch IS NULL;
--
-- Bestand zaehlen, bevor gebaut wird:
--   SELECT coalesce(mime_type,'(leer)') AS typ, count(*),
--          sum(coalesce(seiten,0)) AS seiten, count(ocr_text) AS mit_text
--     FROM beleg_dokumente GROUP BY 1 ORDER BY 2 DESC;
