-- ============================================================
-- BC0 · Schema v1.4 — Gate 0 (Human in the Loop)
-- ============================================================
-- Stand: 17.08.2026 · Simeon Ehmer
--
-- VORAUSSETZUNG: schema_v1.2_stammdaten_und_gate.sql (gate_ereignisse),
-- schema_v1.3_teil_a/b/c (ref_personen, prozess_personen, ref_erhebungen).
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v1.4_gate0.sql
--
-- Alle Anweisungen sind wiederholbar. Es werden KEINE Bestandsdaten geaendert
-- und keine Rechte entzogen — dieses Skript ergaenzt nur.
--
-- WAS ES LOEST
--   Der Gate-0-Entwurf prueft heute Vollstaendigkeit ("Angabe in %"). Ein
--   Befuellungsgrad sagt aber nicht, ob eine Zahl belegt oder geraten ist.
--   Genau die Scheingenauigkeit, die das Gate abfangen soll, geht dadurch
--   ungebremst durch. Dieses Schema fuehrt neben dem Befuellungsgrad eine
--   GUETE je Angabe ein und gibt sie an BC2 weiter.
-- ============================================================


-- ============================================================
-- 14. DIE ANFRAGE — der Ausloeser der Kette
-- ============================================================
-- Bis heute hat die Datenbank keinen Ort fuer die Frage, die der Kunde
-- gestellt hat. Sie ist aber der Anker der gesamten Kette: Nach vier
-- Bounded Contexts laesst sich sonst nicht mehr pruefen, ob die Empfehlung
-- von BC2 ueberhaupt die gestellte Frage beantwortet.
--
-- ADR-004 kennt Personen, Systeme und Erhebungen — die Anfrage fehlte.

CREATE TABLE IF NOT EXISTS ref_anfragen (
  company_id     UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  anfrage_id     TEXT        NOT NULL CHECK (anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}$'),
  originaltext   TEXT        NOT NULL CHECK (length(btrim(originaltext)) > 0),
  eingang_am     DATE        NOT NULL,
  eingang_weg    TEXT,
  steller_id     TEXT,
  hinweis        TEXT,
  angelegt_am    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, anfrage_id),
  CONSTRAINT fk_anfrage_steller FOREIGN KEY (company_id, steller_id)
    REFERENCES ref_personen(company_id, person_id) ON DELETE SET NULL
);

COMMENT ON TABLE ref_anfragen IS
  'Die externe Anfrage an das CoE — der Ausloeser von BC1. BC0 loest BC1 nicht '
  'aus; der Aufruf kommt von aussen und steht hier.';

COMMENT ON COLUMN ref_anfragen.originaltext IS
  'Wortlaut wie eingegangen. WIRD NIE VERAENDERT — weder gekuerzt noch '
  'umformuliert noch zusammengefasst. Eine Zusammenfassung gehoert in hinweis. '
  'Nur der Originaltext erlaubt am Ende der Kette die Pruefung, ob die '
  'Empfehlung die gestellte Frage beantwortet.';

COMMENT ON COLUMN ref_anfragen.steller_id IS
  'Wer gefragt hat, als Verweis auf das Personenregister (ADR-004 R6). '
  'Kein Klarname in dieser Tabelle.';


-- ============================================================
-- 15. KATALOG DER PRUEFPUNKTE
-- ============================================================
-- Global, nicht mandantenbezogen: Welche Angaben am Gate geprueft werden,
-- ist eine Methodikfrage, keine Kundenfrage.
--
-- Ueber aktiv=FALSE laesst sich ein Pruefpunkt vorsehen, ohne ihn scharf zu
-- schalten. Aktivieren ist dann ein UPDATE, keine Migration.

CREATE TABLE IF NOT EXISTS ref_gate_pruefpunkte (
  pruefpunkt     TEXT        PRIMARY KEY CHECK (pruefpunkt ~ '^[a-z_]{3,30}$'),
  bezeichnung    TEXT        NOT NULL,
  erlaeuterung   TEXT,
  quelle_bc      TEXT        NOT NULL CHECK (quelle_bc IN ('BC0','BC1','BC0/BC1')),
  guete_noetig   BOOLEAN     NOT NULL DEFAULT FALSE,
  pflicht        BOOLEAN     NOT NULL DEFAULT TRUE,
  aktiv          BOOLEAN     NOT NULL DEFAULT TRUE,
  reihenfolge    INTEGER     NOT NULL DEFAULT 100
);

COMMENT ON COLUMN ref_gate_pruefpunkte.guete_noetig IS
  'TRUE fuer alles, was in eine Rechnung eingeht. Eine Prozessbeschreibung ist '
  'da oder nicht; eine Dauer ist gemessen, geschaetzt oder geraten — und der '
  'Unterschied entscheidet, ob BC2 einen Punktwert oder eine Bandbreite rechnet.';

COMMENT ON COLUMN ref_gate_pruefpunkte.aktiv IS
  'FALSE = vorgesehen, aber nicht scharf. Erscheint nicht in der Maske und '
  'blockiert keine Freigabe.';

INSERT INTO ref_gate_pruefpunkte
  (pruefpunkt, bezeichnung, erlaeuterung, quelle_bc, guete_noetig, pflicht, aktiv, reihenfolge)
VALUES
  ('dauer', 'Dauer je Ausfuehrung',
   'Bearbeitungszeit eines Durchlaufs. Ohne sie gibt es keinen Jahresaufwand und damit keinen ROI.',
   'BC1', TRUE, TRUE, TRUE, 10),

  ('haeufigkeit', 'Ausfuehrungen je Zeitraum',
   'Wie oft der Prozess laeuft. Meist aus einem System zaehlbar und damit oft besser belegt als die Dauer.',
   'BC1', TRUE, TRUE, TRUE, 20),

  ('menge', 'Menge je Ausfuehrung',
   'Stueckzahl oder Volumen je Durchlauf — Zahl der Positionen, Datensaetze, Dokumente.',
   'BC1', TRUE, TRUE, TRUE, 30),

  ('rollen', 'Beteiligte Rollen mit Zeitanteil',
   'Welche Rolle wie lange beteiligt ist. Paare (rolle_id, zeitanteil), nicht Namensliste.',
   'BC1', TRUE, TRUE, TRUE, 40),

  ('kosten', 'Kostensatz je beteiligter Rolle',
   'Vollkostensatz aus mandant_rollen und rollen_kostensaetze. Guete unterscheidet Buchhaltungswert von Branchenreferenz.',
   'BC0', TRUE, TRUE, TRUE, 50),

  ('prozessbeschreibung', 'Prozessbeschreibung',
   'Ein bis zwei Saetze, was der Prozess umfasst. Grundlage der Erklaerung durch den BC1-Bot.',
   'BC0', FALSE, TRUE, TRUE, 60),

  ('medienbrueche', 'Medienbrueche erfasst',
   'Register aus Schema v1.3 Teil B. Leer kann richtig sein — dann bestaetigt der Mensch die Null.',
   'BC0', FALSE, TRUE, TRUE, 70),

  ('ansprechpartner', 'Ansprechpartner bei Rueckfragen',
   'Wer Auskunft geben kann, wenn BC1 oder BC2 nachfragt. Verweis ins Personenregister.',
   'BC0', FALSE, TRUE, TRUE, 80),

  ('zulaessigkeit', 'Zulaessigkeit der Automatisierung',
   'Personenbezogene Daten, Mitbestimmung, Vier-Augen-Prinzip, regulatorische Bindung. '
   'VORGESEHEN, NICHT AKTIV — vor dem Scharfschalten ist zu klaeren, wer das beurteilt.',
   'BC0', FALSE, TRUE, FALSE, 90)
ON CONFLICT (pruefpunkt) DO NOTHING;


-- ============================================================
-- 16. GATE-EREIGNIS: ERGAENZUNGEN
-- ============================================================

-- FREIGEGEBEN WIRD DER TEILPROZESS, NICHT DER KERNPROZESS.
-- Automatisiert wird auf Teilprozessebene; ein Kernprozess ist die Klammer,
-- nicht der Gegenstand. Entsprechend traegt objekt_id kuenftig eine
-- Teilprozess-ID (KP-XX.TP-Y) und objekt_typ den Wert 'teilprozess'.
-- Der Kernprozess wird nicht mitgespeichert — er steht in ref_teilprozesse
-- und ist jederzeit joinbar. Zweimal abgelegt hiesse: irgendwann widersprechen
-- sie sich.

ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS anfrage_id       TEXT;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS erhebung_id      TEXT;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS bc1_profil_stand TEXT;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS kette_bestaetigt BOOLEAN;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS kette_ergaenzung TEXT;
ALTER TABLE gate_ereignisse ADD COLUMN IF NOT EXISTS massnahme        TEXT;

COMMENT ON COLUMN gate_ereignisse.erhebung_id IS
  'BC0-Erhebung, auf die sich die Entscheidung bezieht — ALS WERT KOPIERT, '
  'bewusst ohne Fremdschluessel. Ein Verweis wanderte mit: schriebe BC1 danach '
  'nach, behauptete die Freigabe rueckwirkend, etwas geprueft zu haben, das es '
  'damals nicht gab. Und ein Protokoll darf nicht verschwinden, weil die Daten, '
  'die es bezeugt, verworfen wurden.';

COMMENT ON COLUMN gate_ereignisse.bc1_profil_stand IS
  'Versionskennung des BC1-Profils zum Zeitpunkt der Entscheidung, ebenfalls '
  'kopiert. Feldname und Wertemenge sind bei BC1 noch offen (Frage 1 an Richard) '
  '— bis dahin bleibt die Spalte leer.';

COMMENT ON COLUMN gate_ereignisse.kette_bestaetigt IS
  'Der Mensch ERFASST die Prozessverflechtung nicht, er BESTAETIGT sie. Sie steht '
  'bereits in prozess_schnittstellen (BC0) und in den upstream/downstream-Feldern '
  '(BC1). Ein drittes Mal erfasst hiesse: beim ersten Widerspruch weiss niemand, '
  'welche gilt.';

COMMENT ON COLUMN gate_ereignisse.kette_ergaenzung IS
  'Was in der angezeigten Kette fehlt, im Klartext — z. B. "KP-07 liefert zu, '
  'steht nicht drin". Wird nicht automatisch nachgetragen, sondern ist ein '
  'Auftrag an die Pflege.';

COMMENT ON COLUMN gate_ereignisse.massnahme IS
  'Pflicht bei Zurueckweisung: Was passiert jetzt? Bei Freigabe leer — '
  'freigegeben heisst, es ist nichts zu tun.';

-- Fremdschluessel nur dort, wo das Protokoll ihn vertraegt.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_gate_anfrage') THEN
    ALTER TABLE gate_ereignisse ADD CONSTRAINT fk_gate_anfrage
      FOREIGN KEY (company_id, anfrage_id)
      REFERENCES ref_anfragen(company_id, anfrage_id) ON DELETE SET NULL;
  END IF;
END $$;

-- Massnahme bei Zurueckweisung erzwingen (Punkt 7 der Abstimmung:
-- "Ja => keine Massnahme; NEIN = Massnahme").
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_gate_massnahme') THEN
    ALTER TABLE gate_ereignisse ADD CONSTRAINT ck_gate_massnahme
      CHECK (ereignis <> 'zurueckgewiesen'
             OR (massnahme IS NOT NULL AND length(btrim(massnahme)) > 0));
  END IF;
END $$;

-- Wertemenge von objekt_typ festschreiben. 'prozess' bleibt zulaessig, damit
-- bereits protokollierte Ereignisse gueltig bleiben — neue Entscheidungen
-- werden aber auf 'teilprozess' geschrieben.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_gate_objekt_typ') THEN
    ALTER TABLE gate_ereignisse ADD CONSTRAINT ck_gate_objekt_typ
      CHECK (objekt_typ IN ('prozess','teilprozess'));
  END IF;
END $$;

COMMENT ON COLUMN gate_ereignisse.objekt_id IS
  'Bei objekt_typ = ''teilprozess'' die Teilprozess-ID (KP-XX.TP-Y) — das ist '
  'der Regelfall seit 17.08.2026. Bewusst OHNE Fremdschluessel, aus demselben '
  'Grund wie erhebung_id: Das Protokoll darf nicht verschwinden, weil der '
  'Gegenstand, ueber den es Auskunft gibt, geloescht wurde.';


-- ============================================================
-- 17. DIE GEPRUEFTEN ANGABEN — je Entscheidung, mit Guete
-- ============================================================
-- Eigene Tabelle statt eines JSONB-Feldes in gate_ereignisse.grundlage.
--
-- Grund: Es ist eine 1:n-Beziehung. In ein Feld gepresst waere es derselbe
-- Konstruktionsfehler wie "Ozan Kiraz / Mehdi Louali" in owner_name — und
-- BC2 koennte nicht mit SQL fragen "welche Freigaben beruhen auf geratenen
-- Dauern?". Genau diese Frage ist der Zweck der Guete.

CREATE TABLE IF NOT EXISTS gate_pruefpunkt_werte (
  ereignis_id    BIGINT      NOT NULL REFERENCES gate_ereignisse(ereignis_id) ON DELETE CASCADE,
  pruefpunkt     TEXT        NOT NULL REFERENCES ref_gate_pruefpunkte(pruefpunkt),
  vorhanden_pct  NUMERIC(5,2) CHECK (vorhanden_pct BETWEEN 0 AND 100),
  guete          TEXT        CHECK (guete IN ('belegt','geschaetzt','geraten','entfaellt')),
  bestaetigt     BOOLEAN     NOT NULL,
  anmerkung      TEXT,
  PRIMARY KEY (ereignis_id, pruefpunkt)
);

COMMENT ON TABLE gate_pruefpunkt_werte IS
  'Was am Gate tatsaechlich geprueft wurde. Wird zusammen mit dem Ereignis in '
  'einer Transaktion geschrieben — ein halb ausgefuellter Pruefbogen wird '
  'bewusst nicht gespeichert, er haette keinen Beweiswert.';

COMMENT ON COLUMN gate_pruefpunkt_werte.vorhanden_pct IS
  'Befuellungsgrad, von der Maschine vorbelegt. Sagt WIE VIEL dasteht, '
  'nicht ob es stimmt.';

COMMENT ON COLUMN gate_pruefpunkt_werte.guete IS
  'Die Angabe des Menschen: belegt (Messwert, Systemauszug, Buchhaltung) · '
  'geschaetzt (begruendete Naeherung durch jemanden, der den Prozess macht) · '
  'geraten (Zahl ohne Grundlage) · entfaellt (trifft auf diesen Prozess nicht zu). '
  'Entspricht duration_confidence_pct 95 / 70 / 30 aus BC1.';

COMMENT ON COLUMN gate_pruefpunkt_werte.bestaetigt IS
  'Haken oder Kreuz. Ein Kreuz verhindert die Freigabe nicht — es macht sie '
  'begruendungspflichtig.';

-- Guete dort erzwingen, wo der Katalog sie verlangt, und nur bei Freigabe:
-- eine Zurueckweisung darf abbrechen, ohne jeden Punkt zu bewerten.
CREATE OR REPLACE FUNCTION trg_gate_guete_pflicht() RETURNS TRIGGER AS $fn$
DECLARE
  v_ereignis TEXT;
  v_noetig   BOOLEAN;
BEGIN
  SELECT ereignis INTO v_ereignis FROM gate_ereignisse WHERE ereignis_id = NEW.ereignis_id;
  SELECT guete_noetig INTO v_noetig FROM ref_gate_pruefpunkte WHERE pruefpunkt = NEW.pruefpunkt;

  IF v_ereignis = 'freigegeben' AND v_noetig AND NEW.guete IS NULL THEN
    RAISE EXCEPTION
      'Pruefpunkt "%" geht in die Rechnung ein und braucht bei einer Freigabe eine Guete '
      '(belegt/geschaetzt/geraten/entfaellt).', NEW.pruefpunkt;
  END IF;
  RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS gate_guete_pflicht ON gate_pruefpunkt_werte;
CREATE TRIGGER gate_guete_pflicht
  BEFORE INSERT OR UPDATE ON gate_pruefpunkt_werte
  FOR EACH ROW EXECUTE FUNCTION trg_gate_guete_pflicht();


-- ============================================================
-- 18. VORBEDINGUNGEN — was vor dem Ausfuellen erfuellt sein muss
-- ============================================================
-- Owner und Bewertung sind keine Prozentwerte, sondern Abbruchkriterien.
-- Ohne benannten Eigner verantwortet niemand die Angaben und niemand nimmt
-- spaeter eine Automatisierung ab.
--
-- Gegenstand ist der TEILPROZESS. Eigner und Ansprechpartner haengen im
-- Datenmodell am Kernprozess und werden vererbt — ein eigener Eigner je
-- Teilprozess waere eine Genauigkeit, die es in der Wirklichkeit nicht gibt.

CREATE OR REPLACE VIEW v_gate_vorbedingungen AS
SELECT
  t.company_id,
  t.sub_process_id,
  t.process_id,
  t.sub_process_name,
  p.process_name,
  EXISTS (SELECT 1 FROM prozess_personen pp
           WHERE pp.company_id = t.company_id
             AND pp.process_id = t.process_id
             AND pp.funktion   = 'eigner')                       AS eigner_benannt,
  EXISTS (SELECT 1 FROM prozess_personen pp
           WHERE pp.company_id = t.company_id
             AND pp.process_id = t.process_id
             AND pp.funktion IN ('mitwirkend','vertretung','sponsor')) AS ansprechpartner_benannt,
  coalesce(r.n_items, 0)                                         AS items_bewertet,
  (coalesce(r.n_items, 0) >= 27)                                 AS vollstaendig_bewertet,
  round(r.avg_stufe::numeric, 2)                                 AS reifegrad,
  (r.avg_stufe >= 3.5)                                           AS ueber_schwelle
  FROM ref_teilprozesse t
  JOIN ref_prozesse p
    ON p.company_id = t.company_id AND p.process_id = t.process_id
  LEFT JOIN v_reifegrad_tp r
    ON r.company_id = t.company_id AND r.sub_process_id = t.sub_process_id;

COMMENT ON VIEW v_gate_vorbedingungen IS
  'Die harten Vorbedingungen fuer Gate 0, je Teilprozess: Eigner benannt, '
  'Ansprechpartner benannt, mindestens 27 von 30 Items bewertet. Sind sie nicht '
  'erfuellt, ist der Pruefbogen gar nicht erst auszufuellen. Der Reifegrad steht '
  'daneben, ist aber KEINE Vorbedingung — die 3,5 ist eine Projektsetzung.';


-- ============================================================
-- 19. WAS BC2 LIEST — Freigabe MIT Guete
-- ============================================================
-- Der entscheidende View dieses Schemas. Ein blosses "freigegeben: ja" wuerde
-- die Guete am Gate verfallen lassen: Der Mensch saehe "Dauer: geschaetzt",
-- gaebe vertretbar frei — und BC2 rechnete mit einem Punktwert, ohne je
-- erfahren zu haben, worauf er beruht.

CREATE OR REPLACE VIEW v_gate_freigabe_aktuell AS
WITH letzte AS (
  SELECT g.*,
         row_number() OVER (PARTITION BY g.company_id, g.objekt_id
                            ORDER BY g.am DESC, g.ereignis_id DESC) AS rang
    FROM gate_ereignisse g
   WHERE g.gate = 'bc0-bc2' AND g.objekt_typ = 'teilprozess'
)
SELECT
  l.company_id,
  l.objekt_id                       AS sub_process_id,
  t.process_id,
  l.ereignis                        AS stand,
  l.am                              AS entschieden_am,
  l.benutzer_id                     AS entschieden_von,
  l.anfrage_id,
  l.erhebung_id                     AS bc0_stand,
  l.bc1_profil_stand,
  l.kette_bestaetigt,
  l.kette_ergaenzung,
  l.grund,
  l.massnahme,
  (SELECT count(*) FROM gate_pruefpunkt_werte w
    WHERE w.ereignis_id = l.ereignis_id AND w.guete = 'geraten')     AS punkte_geraten,
  (SELECT count(*) FROM gate_pruefpunkt_werte w
    WHERE w.ereignis_id = l.ereignis_id AND w.guete = 'geschaetzt')  AS punkte_geschaetzt,
  (SELECT count(*) FROM gate_pruefpunkt_werte w
    WHERE w.ereignis_id = l.ereignis_id AND NOT w.bestaetigt)        AS punkte_ohne_haken,
  (SELECT jsonb_object_agg(w.pruefpunkt,
            jsonb_build_object('guete', w.guete,
                               'vorhanden_pct', w.vorhanden_pct,
                               'bestaetigt', w.bestaetigt))
     FROM gate_pruefpunkt_werte w WHERE w.ereignis_id = l.ereignis_id) AS gueten,
  CASE
    WHEN l.ereignis <> 'freigegeben' THEN 'nicht freigegeben'
    WHEN EXISTS (SELECT 1 FROM gate_pruefpunkt_werte w
                  WHERE w.ereignis_id = l.ereignis_id AND w.guete = 'geraten')
      THEN 'Bandbreite rechnen — mindestens eine Angabe ist geraten'
    WHEN EXISTS (SELECT 1 FROM gate_pruefpunkt_werte w
                  WHERE w.ereignis_id = l.ereignis_id AND w.guete = 'geschaetzt')
      THEN 'Bandbreite empfohlen — mindestens eine Angabe ist geschaetzt'
    ELSE 'Punktwert vertretbar — alle rechnungsrelevanten Angaben belegt'
  END                               AS hinweis_an_bc2,
  l.ereignis_id
  FROM letzte l
  LEFT JOIN ref_teilprozesse t
    ON t.company_id = l.company_id AND t.sub_process_id = l.objekt_id
 WHERE l.rang = 1;

COMMENT ON VIEW v_gate_freigabe_aktuell IS
  'Die Lesesicht fuer BC2, je Teilprozess. Enthaelt die Freigabe UND die Guete '
  'der Angaben, auf denen sie beruht. hinweis_an_bc2 ist eine Ableitung, keine '
  'Vorschrift — ob mit Bandbreite gerechnet wird, entscheidet BC2. Der Punkt ist, '
  'dass BC2 es ueberhaupt entscheiden KANN.';


-- ============================================================
-- 20. WAS DIE MASKE ANZEIGT
-- ============================================================

CREATE OR REPLACE VIEW v_gate_bogen AS
SELECT
  v.company_id,
  v.sub_process_id,
  v.process_id,
  v.sub_process_name,
  v.process_name,
  v.eigner_benannt,
  v.ansprechpartner_benannt,
  v.items_bewertet,
  v.vollstaendig_bewertet,
  v.reifegrad,
  v.ueber_schwelle,
  (v.eigner_benannt AND v.ansprechpartner_benannt AND v.vollstaendig_bewertet) AS bogen_ausfuellbar,
  (SELECT array_agg(DISTINCT s.nach_process_id ORDER BY s.nach_process_id)
     FROM prozess_schnittstellen s
    WHERE s.company_id = v.company_id AND s.von_process_id = v.process_id)  AS liefert_an,
  (SELECT array_agg(DISTINCT s.von_process_id ORDER BY s.von_process_id)
     FROM prozess_schnittstellen s
    WHERE s.company_id = v.company_id AND s.nach_process_id = v.process_id) AS empfaengt_von,
  f.stand,
  f.entschieden_am,
  f.hinweis_an_bc2
  FROM v_gate_vorbedingungen v
  LEFT JOIN v_gate_freigabe_aktuell f
    ON f.company_id = v.company_id AND f.sub_process_id = v.sub_process_id;

COMMENT ON VIEW v_gate_bogen IS
  'Vorbelegung der Gate-0-Maske aus dem, was BC0 weiss, plus dem letzten Stand '
  'der Entscheidung. Die BC1-Anteile (Dauer, Haeufigkeit, Menge, Rollen mit '
  'Zeitanteil) stehen im Schema bc1 und werden erst ergaenzt, wenn dessen '
  'Feldnamen benannt sind.';


-- Die Kernprozess-Sicht bleibt bestehen, ihre Freigabespalten laufen aber leer:
COMMENT ON VIEW v_gate_prozessstand IS
  'Kennzahlen je Kernprozess. ACHTUNG: Die Spalten freigabe_status/-seit/-durch '
  'beziehen sich auf Ereignisse mit objekt_typ = ''prozess'' und bleiben seit '
  'dem 17.08.2026 leer — freigegeben wird der Teilprozess. Fuer den Freigabestand '
  'ist v_gate_freigabe_aktuell massgeblich.';


-- ============================================================
-- RECHTE
-- ============================================================
-- Nur Lesen, und nur auf die Sichten. Kein Recht auf die Ereignistabelle:
-- Ein Protokoll, das der Gelesene aendern kann, ist keines.

GRANT SELECT ON v_gate_freigabe_aktuell TO bc_leser;
GRANT SELECT ON ref_gate_pruefpunkte    TO bc_leser;

-- ref_anfragen bewusst NICHT an bc_leser: der Originaltext kann personen-
-- bezogene Angaben enthalten, die niemand geprueft hat.


-- ============================================================
-- KONTROLLE — beide Abfragen muessen leer bleiben
-- ============================================================
-- 1) Freigaben ohne festgehaltenen BC0-Stand
--    SELECT ereignis_id, objekt_id FROM gate_ereignisse
--     WHERE ereignis = 'freigegeben' AND erhebung_id IS NULL;
--
-- 2) Freigaben ohne jeden Pruefpunkt
--    SELECT g.ereignis_id, g.objekt_id FROM gate_ereignisse g
--     WHERE g.ereignis = 'freigegeben'
--       AND NOT EXISTS (SELECT 1 FROM gate_pruefpunkt_werte w
--                        WHERE w.ereignis_id = g.ereignis_id);
