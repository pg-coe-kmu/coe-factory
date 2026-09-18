-- Schema v3.4 — Der aktiv-Filter und der eindeutige Eigner (18.09.2026)
--
-- Zwei Befunde aus Richards Brief vom 15.09., beide am 18.09. an der
-- Produktion nachgemessen:
--
-- (1) DIE SICHTEN FILTERN `aktiv` NICHT. Bei uns wird nichts geloescht,
--     sondern stillgelegt (v2.2). `v_prozesse_lesen` und `v_bewertung_aktuell`
--     kennen den Unterschied bisher nicht — ein stillgelegter Prozess sieht
--     fuer BC1 aus wie ein gueltiger. Heute harmlos (null stillgelegte Zeilen,
--     gemessen 18.09.), beim ersten Mal nicht mehr.
--
-- (2) EIN PROZESS HATTE DREI EIGNER. Simeons Festlegung vom 18.09.: genau
--     einer. KP-05 trug drei, KP-04 einen ohne Rolle. Die Daten sind am
--     18.09. ueber die Oberflaeche bereinigt; hier wird die Regel erzwungen.
--
-- DIE TRENNLINIE, die diese Datei zieht:
--   "Woran arbeiten wir JETZT?"  -> gefiltert auf aktiv = true
--   "Wie war es DAMALS?"          -> ungefiltert; stand_zum() und
--                                    bewertung_aktuell_zum() bleiben unberuehrt
-- Wuerde der historische Weg mitfiltern, verschwaenden Prozesse rueckwirkend
-- aus Berichten, die es damals anders gab. Das waere das Gegenteil von R9.
--
-- Rein additiv: keine Spalte entfaellt, keine Zeile wird geaendert.
-- Ausfuehren: als Eigentuemer, in einer Transaktion.

BEGIN;

-- ============================================================
-- 1. v_prozesse_lesen — gefiltert, und um die Owner-Rolle ergaenzt
-- ============================================================
-- Die neue Spalte steht am ENDE. CREATE OR REPLACE VIEW erlaubt nur das
-- Anhaengen; eine Spalte in der Mitte erzwaenge ein DROP und damit den
-- Verlust aller abhaengigen Sichten und Rechte.
--
-- owner_rolle_id beantwortet Richards Frage aus dem Brief vom 15.09.: Seine
-- Spalte `process_owner_rolle_id` nimmt genau eine Rolle. Die Kette dorthin
-- war schon modelliert, nur nirgends ausgeliefert:
--   ref_prozesse -> prozess_personen (eigner) -> ref_personen.rolle_id
-- Mit Punkt 2 dieser Datei ist der Eigner eindeutig, also ist auch die
-- Ableitung eindeutig. Bleibt sie NULL, hat die Eignerperson keine Rolle
-- zugeordnet — das ist eine Auskunft, kein Fehler.

CREATE OR REPLACE VIEW v_prozesse_lesen AS
SELECT p.company_id,
       p.process_id,
       p.process_name,
       p.beschreibung,
       p.trigger_text,
       p.input_text,
       p.output_text,
       p.created_at,
       (SELECT array_agg(pp.person_id ORDER BY pp.person_id)
          FROM prozess_personen pp
         WHERE pp.company_id = p.company_id
           AND pp.process_id = p.process_id
           AND pp.funktion = 'eigner')   AS eigner_ids,
       (SELECT array_agg(pp.person_id ORDER BY pp.person_id)
          FROM prozess_personen pp
         WHERE pp.company_id = p.company_id
           AND pp.process_id = p.process_id
           AND pp.funktion = 'sponsor')  AS sponsor_ids,
       (SELECT r.rolle_id
          FROM prozess_personen pp
          JOIN ref_personen r
            ON r.company_id = pp.company_id AND r.person_id = pp.person_id
         WHERE pp.company_id = p.company_id
           AND pp.process_id = p.process_id
           AND pp.funktion = 'eigner'
         LIMIT 1)                        AS owner_rolle_id
  FROM ref_prozesse p
 WHERE p.aktiv;

COMMENT ON VIEW v_prozesse_lesen IS
  'Prozesse ohne Klarnamen, fuer BC1 bis BC4. Seit v3.4 nur AKTIVE Prozesse — '
  'wer den Stand von damals braucht, nimmt stand_zum(''ref_prozesse'', datum). '
  'owner_rolle_id ist die Rolle der Eignerperson; der Eigner ist seit v3.4 '
  'eindeutig, die Ableitung damit auch.';

-- ============================================================
-- 2. Genau ein Eigner je Prozess
-- ============================================================
-- Simeons Festlegung vom 18.09.2026, auf Richards Frage (a) aus dem Brief vom
-- 15.09. Vorher war es eine Absicht, jetzt ist es eine Bedingung: Ein zweiter
-- Eigner scheitert beim Anlegen, statt unbemerkt zu entstehen.
--
-- Partiell, nicht generell: sponsor, mitwirkend und vertretung duerfen
-- weiterhin mehrfach vorkommen. Wer die Eignerrolle abgibt, wird nicht
-- geloescht, sondern auf mitwirkend gesetzt — die Beteiligung bleibt wahr.

CREATE UNIQUE INDEX IF NOT EXISTS ux_prozess_eigner_eindeutig
  ON prozess_personen (company_id, process_id)
  WHERE funktion = 'eigner';

COMMENT ON INDEX ux_prozess_eigner_eindeutig IS
  'Genau ein Eigner je Prozess (Festlegung 18.09.2026). Andere '
  'Beteiligungsarten bleiben mehrfach moeglich.';

-- ============================================================
-- 3. v_bewertung_aktuell — stillgelegte Teilprozesse zaehlen nicht mehr
-- ============================================================
-- Simeons Entscheidung vom 18.09.: Ein stillgelegter Teilprozess geht NICHT
-- in den Reifegrad-Mittelwert eines aktuellen Berichts ein. Sonst zieht ein
-- Prozess, den es nicht mehr gibt, den Schnitt des Unternehmens.
--
-- Die Spalten bleiben unveraendert — sonst braechen die abhaengigen Sichten
-- (v_reifegrad_*). Nur der Join kommt dazu.
--
-- ACHTUNG, die Doppelfuehrung: Dieselbe Regel steht ein zweites Mal in
-- app.py als _bew_aktuell(), weil der SQLite-Entwicklungsmodus keine Sichten
-- hat. Beide Stellen sind mit v3.4 geaendert.

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
          JOIN ref_teilprozesse tp
            ON tp.company_id = b.company_id AND tp.sub_process_id = b.sub_process_id
         WHERE e.status <> 'verworfen'
           AND tp.aktiv) t
 WHERE rang = 1;

COMMENT ON VIEW v_bewertung_aktuell IS
  'Je Mandant, Teilprozess und Item die juengste nicht verworfene Bewertung. '
  'Filtergrundlage aller auswertenden Views. Seit v3.4 nur AKTIVE '
  'Teilprozesse — der Stand von damals kommt aus bewertung_aktuell_zum(), '
  'das auf stand_zum() ruht und bewusst NICHT filtert.';

-- ============================================================
-- 4. Zwei Lesesichten fuer die Tabellen, die BC1 direkt liest
-- ============================================================
-- Richard liest heute vier Objekte: die beiden Sichten oben und die beiden
-- Tabellen ref_teilprozesse und mandant_systeme. Eine Tabelle laesst sich
-- nicht filtern — also bekommt er zwei Sichten und kann seinen eigenen
-- Filter sparen. Die Tabellen selbst bleiben unveraendert lesbar.

CREATE OR REPLACE VIEW v_teilprozesse_lesen AS
SELECT t.company_id, t.sub_process_id, t.process_id, t.step_no,
       t.sub_process_name, t.notation, t.tools, t.medienbrueche,
       t.schnittstellen, t.api
  FROM ref_teilprozesse t
 WHERE t.aktiv;

COMMENT ON VIEW v_teilprozesse_lesen IS
  'Aktive Teilprozesse fuer BC1 bis BC4 (v3.4). Ersetzt den direkten Zugriff '
  'auf ref_teilprozesse, wo der aktiv-Filter fehlte.';

CREATE OR REPLACE VIEW v_systeme_lesen AS
SELECT s.company_id, s.system_id, s.katalog_id, s.bezeichnung,
       s.einsatz, s.hinweis
  FROM mandant_systeme s
 WHERE s.aktiv;

COMMENT ON VIEW v_systeme_lesen IS
  'Aktive Systeme fuer BC1 bis BC4 (v3.4). Ersetzt den direkten Zugriff auf '
  'mandant_systeme.';

GRANT SELECT ON v_teilprozesse_lesen, v_systeme_lesen TO bc_leser;

-- ============================================================
-- 5. Das Recht, das v3.0 vergessen hat
-- ============================================================
-- v_anfrage_steller wurde am 08.09. fuer BC1 gebaut — schema_v3.0 enthaelt
-- kein einziges GRANT. Richard waere beim ersten Zugriff auf einen
-- Rechtefehler gelaufen. Am 18.09. von Hand nachgezogen; hier steht es
-- dauerhaft, damit es beim naechsten Aufsetzen nicht wieder fehlt.

GRANT SELECT ON v_anfrage_steller TO bc_leser;

COMMIT;

-- ============================================================
-- GEGENPROBEN
-- ============================================================
-- Rein lesend, nach dem Einspielen zu fahren.
--
-- ERWARTET: t · t · t · t
-- SELECT has_table_privilege('bc_leser','v_teilprozesse_lesen','SELECT') AS tp,
--        has_table_privilege('bc_leser','v_systeme_lesen','SELECT')      AS sys,
--        has_table_privilege('bc_leser','v_anfrage_steller','SELECT')    AS steller,
--        to_regclass('ux_prozess_eigner_eindeutig') IS NOT NULL          AS index_da;
--
-- ERWARTET: zehn Zeilen, owner_rolle_id ueberall gefuellt
-- SELECT process_id, eigner_ids, owner_rolle_id FROM v_prozesse_lesen
--  WHERE company_id::text = '7c2d5ee9-2a9a-5990-810f-502ea2b2012d'
--  ORDER BY process_id;
--
-- ERWARTET: 690 (heute ist nichts stillgelegt, die Zahl darf sich nicht aendern)
-- SELECT count(*) FROM v_bewertung_aktuell
--  WHERE company_id::text = '7c2d5ee9-2a9a-5990-810f-502ea2b2012d';
--
-- ERWARTET: Fehler "duplicate key value violates unique constraint"
-- BEGIN; INSERT INTO prozess_personen(company_id,process_id,person_id,funktion)
--   VALUES ('7c2d5ee9-2a9a-5990-810f-502ea2b2012d','KP-05','P-04','eigner'); ROLLBACK;
