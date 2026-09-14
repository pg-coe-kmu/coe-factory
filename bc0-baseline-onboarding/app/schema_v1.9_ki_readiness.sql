-- ============================================================
-- BC0 Onboarding — Schema-Nachtrag v1.9: KI-Readiness (Ergebnisuebernahme)
-- Stand: 19.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- ZWECK
--   Nach etwa sechs Monaten soll geprueft werden, wie es um Skills,
--   Prozessverstaendnis und KI-Verstaendnis steht. Dafuer gibt es ein
--   fertiges, oeffentlich zugaengliches Werkzeug: den KI-Readiness-Selbstcheck
--   des Mittelstand-Digital Zentrums Chemnitz, einer Initiative des
--   Bundesministeriums fuer Wirtschaft. Vier Dimensionen, 21 Fragen, Skala 0
--   bis 4, mit Ist- und Soll-Erfassung im Werkzeug selbst.
--
-- WARUM NUR DAS ERGEBNIS UND NICHT DER BOGEN
--   Zwei Gruende, beide geprueft.
--
--   Erstens rechtlich: Auf der Seite des Zentrums steht nichts zu Lizenz,
--   Creative Commons oder Weiterverwendung. Ein Fragebogen ist in Deutschland
--   urheberrechtlich schutzfaehig. Ihn woertlich in unsere Anwendung zu
--   kopieren, die in einem OEFFENTLICHEN Repository liegt, waere eine
--   Uebernahme ohne erkennbare Erlaubnis. Ein Ergebnis zu erfassen ist es
--   nicht — Zahlen sind keine Werke.
--
--   Zweitens fachlich, und das wiegt schwerer: Der Bogen misst, ob ein
--   Unternehmen KI strategisch betreibt ("Verfuegen Sie ueber ein dediziertes
--   KI-Team?", "Sind Ihre KI-Systeme skalierbar?"). Ein KMU, das gerade
--   seinen ersten Teilprozess automatisiert hat, antwortet darauf zehnmal mit
--   0 oder 1. Der Nachbau haette viel Aufwand fuer wenig Auskunft bedeutet.
--
--   Deshalb: Die Gruppe fuellt den Selbstcheck online aus, wir erfassen die
--   vier Dimensionswerte mit Datum, Quelle und den Personen, die ihn
--   ausgefuellt haben. Das genuegt fuer den Zeitvergleich, um den es geht.
--
-- ABGRENZUNG ZUM BITKOM-MODELL
--   Bitkom bewertet den PROZESS, dieser Check das UNTERNEHMEN. Die beiden
--   Zahlen duerfen nie vermischt oder gegeneinander gerechnet werden. Der
--   Reifegradbericht weist die KI-Readiness deshalb getrennt aus, nicht als
--   sechste Dimension.
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v1.9_ki_readiness.sql
-- ============================================================

BEGIN;

-- ============================================================
-- 30. DIMENSIONEN DES FREMDMODELLS
-- ============================================================
-- Nur die Bezeichnungen der vier Dimensionen und der fuenf Stufen. Die
-- einundzwanzig Fragen stehen bewusst NICHT hier — siehe Kopf.

CREATE TABLE IF NOT EXISTS ref_ki_readiness_dimensionen (
  dim_nr      INTEGER PRIMARY KEY CHECK (dim_nr BETWEEN 1 AND 4),
  bezeichnung TEXT NOT NULL,
  fragen      INTEGER NOT NULL
);

INSERT INTO ref_ki_readiness_dimensionen (dim_nr, bezeichnung, fragen) VALUES
  (1, 'Strategie und Planung', 5),
  (2, 'Daten und Technologie', 6),
  (3, 'Ethik, Compliance und Sicherheit', 5),
  (4, 'Anwendungsorientierung und Kundennutzen', 5)
ON CONFLICT (dim_nr) DO NOTHING;

COMMENT ON TABLE ref_ki_readiness_dimensionen IS
  'Die vier Dimensionen des KI-Readiness-Selbstchecks des Mittelstand-Digital '
  'Zentrums Chemnitz. Nur Bezeichnungen, keine Fragen — der Fragebogen wird '
  'nicht nachgebaut, sondern extern ausgefuellt.';


-- ============================================================
-- 31. ERGEBNISSE JE MANDANT UND ZEITPUNKT
-- ============================================================

CREATE TABLE IF NOT EXISTS ki_readiness_erhebungen (
  company_id      UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  readiness_id    TEXT NOT NULL CHECK (readiness_id ~ '^KR-[0-9]{4}-[0-9]{2}$'),
  stand           DATE NOT NULL,
  anlass          TEXT NOT NULL CHECK (anlass IN
                    ('baseline','nachschau','sonstige')),
  quelle          TEXT NOT NULL DEFAULT
                    'KI-Readiness-Selbstcheck, Mittelstand-Digital Zentrum Chemnitz',
  quelle_url      TEXT NOT NULL DEFAULT 'https://digitalzentrum-chemnitz.de/wissen/ki-readiness/',
  ausgefuellt_von TEXT NOT NULL,
  hinweis         TEXT,
  angelegt_am     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, readiness_id)
);

COMMENT ON COLUMN ki_readiness_erhebungen.ausgefuellt_von IS
  'person_id oder Rolle. Wer den Check ausgefuellt hat, faellt beim '
  'Zeitvergleich ins Gewicht: Ein anderer Personenkreis misst teils die '
  'Personen und nicht die Organisation.';

COMMENT ON COLUMN ki_readiness_erhebungen.quelle IS
  'Pflichtangabe und Vorbelegung. Das Ergebnis stammt aus einem fremden '
  'Werkzeug; das gehoert an jeder Stelle dazu, an der es ausgewiesen wird.';


CREATE TABLE IF NOT EXISTS ki_readiness_werte (
  company_id   UUID    NOT NULL,
  readiness_id TEXT    NOT NULL,
  dim_nr       INTEGER NOT NULL REFERENCES ref_ki_readiness_dimensionen(dim_nr),
  wert_ist     NUMERIC(3,2) NOT NULL CHECK (wert_ist  BETWEEN 0 AND 4),
  wert_soll    NUMERIC(3,2) CHECK (wert_soll BETWEEN 0 AND 4),
  hinweis      TEXT,
  PRIMARY KEY (company_id, readiness_id, dim_nr),
  FOREIGN KEY (company_id, readiness_id)
    REFERENCES ki_readiness_erhebungen(company_id, readiness_id) ON DELETE CASCADE,
  -- Das Soll darf nicht unter dem Ist liegen; im Werkzeug selbst prueft das
  -- eine Plausibilitaetskontrolle, hier ebenso.
  CONSTRAINT ck_kr_soll CHECK (wert_soll IS NULL OR wert_soll >= wert_ist)
);

COMMENT ON TABLE ki_readiness_werte IS
  'Vier Zeilen je Erhebung. Nachkommastellen sind zugelassen, weil das '
  'Werkzeug je Dimension ueber mehrere Fragen mittelt.';


-- ============================================================
-- 32. LESESICHTEN
-- ============================================================

CREATE OR REPLACE VIEW v_ki_readiness_aktuell AS
SELECT e.company_id, e.readiness_id, e.stand, e.anlass,
       d.dim_nr, d.bezeichnung, w.wert_ist, w.wert_soll,
       (w.wert_soll - w.wert_ist) AS luecke
  FROM ki_readiness_erhebungen e
  JOIN ki_readiness_werte w
    ON w.company_id = e.company_id AND w.readiness_id = e.readiness_id
  JOIN ref_ki_readiness_dimensionen d ON d.dim_nr = w.dim_nr
 WHERE e.stand = (SELECT max(stand) FROM ki_readiness_erhebungen x
                   WHERE x.company_id = e.company_id)
 ORDER BY d.dim_nr;


CREATE OR REPLACE VIEW v_ki_readiness_verlauf AS
SELECT w.company_id, d.dim_nr, d.bezeichnung, e.stand, e.anlass, w.wert_ist,
       w.wert_ist - lag(w.wert_ist) OVER (
         PARTITION BY w.company_id, w.dim_nr ORDER BY e.stand) AS veraenderung
  FROM ki_readiness_werte w
  JOIN ki_readiness_erhebungen e
    ON e.company_id = w.company_id AND e.readiness_id = w.readiness_id
  JOIN ref_ki_readiness_dimensionen d ON d.dim_nr = w.dim_nr
 ORDER BY w.company_id, d.dim_nr, e.stand;

COMMENT ON VIEW v_ki_readiness_verlauf IS
  'Der eigentliche Zweck: die Veraenderung ueber die Zeit. Bei nur einer '
  'Erhebung steht in veraenderung NULL — und das ist die richtige Auskunft.';

COMMIT;


-- ============================================================
-- GEGENPROBE
-- ============================================================
-- Erwartet: 4 Dimensionen.
--   SELECT count(*) FROM ref_ki_readiness_dimensionen;
--
-- Beispiel fuer eine Erfassung (Werte aus dem Online-Werkzeug uebertragen):
--   INSERT INTO ki_readiness_erhebungen
--     (company_id, readiness_id, stand, anlass, ausgefuellt_von)
--   VALUES ('<uuid>', 'KR-2026-08', DATE '2026-08-19', 'baseline', 'P-01');
--   INSERT INTO ki_readiness_werte (company_id, readiness_id, dim_nr, wert_ist, wert_soll)
--   VALUES ('<uuid>','KR-2026-08',1,1.20,3.00),
--          ('<uuid>','KR-2026-08',2,0.80,2.50),
--          ('<uuid>','KR-2026-08',3,1.60,3.00),
--          ('<uuid>','KR-2026-08',4,1.00,2.50);
-- ============================================================
