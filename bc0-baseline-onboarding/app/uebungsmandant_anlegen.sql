-- ============================================================
-- BC0 — Übungsmandant anlegen
-- Stand: 17.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- ZWECK
--   Dorka und die Projektgruppe sollen die Anwendung ausprobieren können, ohne
--   die Baseline zu gefährden. Die Anwendung kennt nur `benutzer` und `admin` —
--   **beide dürfen schreiben**. Ein Konto auf dem NoroAI-Mandanten könnte im
--   Self-Rating die 600 Bewertungen überschreiben, auf denen Reifegradbericht,
--   Gate und die Übergabe an BC1 und BC2 beruhen.
--
--   Deshalb: ein zweiter Mandant mit denselben Strukturen und Zahlen. Konten für
--   die Projektgruppe werden ausschließlich diesem zugeordnet. Wer nur ihn hat,
--   sieht NoroAI nicht in der Liste, und ein direkter Aufruf endet mit 404.
--
-- WAS KOPIERT WIRD
--   Unternehmensprofil · Kern- und Teilprozesse · Erhebung · alle 600
--   Bewertungen mit Belegen · Rollen und Kostensätze · Personen und ihre
--   Zuordnung · Systeme · Prozess-Schnittstellen
--
-- WAS NICHT KOPIERT WIRD, UND WARUM
--   `beleg_dokumente` und `bewertung_belege` — die Dateien liegen nur einmal im
--       Speicher; ein zweiter Verweis darauf wäre eine Attrappe.
--   `gate_ereignisse` — eine Freigabe gehört zu dem Mandanten, für den sie
--       erteilt wurde. Der Übungsmandant startet mit leerem Gate; das ist
--       fachlich richtig und zum Ausprobieren sogar das Interessantere.
--   `audit_log` — Protokoll, kein Bestand.
--
-- KLARNAMEN WERDEN ERSETZT.
--   `ref_personen.name` und `ref_prozesse.owner_name` bekommen Platzhalter.
--   Nach ADR-004 R5 stehen Klarnamen an genau einer Stelle; eine Kopie wäre
--   eine zweite. Funktion, Rolle und Kostenklasse bleiben erhalten — für das
--   Ausprobieren zählt die Struktur, nicht der Name.
--
-- WIEDERHOLBAR. Existiert der Übungsmandant bereits, passiert nichts.
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f uebungsmandant_anlegen.sql
-- ============================================================

BEGIN;

DO $$
DECLARE
  m_quelle UUID;
  m_ziel   UUID;
  name_ziel CONSTANT TEXT := 'Übungsmandant (Demo) — Testdaten, keine echten Werte';
BEGIN
  -- Vorlage ist der Mandant mit den meisten Bewertungen; das ist NoroAI.
  SELECT company_id INTO m_quelle
    FROM bitkom_bewertungen GROUP BY company_id ORDER BY count(*) DESC LIMIT 1;
  IF m_quelle IS NULL THEN
    RAISE EXCEPTION 'Kein Mandant mit Bewertungen gefunden — nichts zu kopieren.';
  END IF;

  IF EXISTS (SELECT 1 FROM companies WHERE name = name_ziel) THEN
    RAISE NOTICE 'Übungsmandant existiert bereits — nichts geändert.';
    RETURN;
  END IF;

  INSERT INTO companies (name, branche, rechtsform, mitarbeitende, region, status)
  SELECT name_ziel, branche, rechtsform, mitarbeitende, region, 'laeuft'
    FROM companies WHERE company_id = m_quelle
  RETURNING company_id INTO m_ziel;
  RAISE NOTICE 'Übungsmandant angelegt: %', m_ziel;

  INSERT INTO company_profile (company_id, geschaeftsmodell, tech_stack, vision, finanzen, profile_json)
  SELECT m_ziel, geschaeftsmodell, tech_stack, vision, finanzen, profile_json
    FROM company_profile WHERE company_id = m_quelle;

  -- Prozesse. owner_name und owner_role werden nicht mitkopiert: Sie sind seit
  -- v1.3 ohnehin abgelöst, und sie tragen Klarnamen.
  INSERT INTO ref_prozesse (company_id, process_id, process_name, kategorie,
                            beschreibung, trigger_text, input_text, output_text)
  SELECT m_ziel, process_id, process_name, kategorie,
         beschreibung, trigger_text, input_text, output_text
    FROM ref_prozesse WHERE company_id = m_quelle;

  INSERT INTO ref_teilprozesse (company_id, sub_process_id, process_id, step_no,
                                sub_process_name, notation, tools, medienbrueche,
                                schnittstellen, api)
  SELECT m_ziel, sub_process_id, process_id, step_no,
         sub_process_name, notation, tools, medienbrueche, schnittstellen, api
    FROM ref_teilprozesse WHERE company_id = m_quelle;

  INSERT INTO prozess_schnittstellen (company_id, von_process_id, nach_process_id, art, beschreibung)
  SELECT m_ziel, von_process_id, nach_process_id, art, beschreibung
    FROM prozess_schnittstellen WHERE company_id = m_quelle;

  -- Erhebungen zuerst — die Bewertungen verweisen darauf.
  INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, stand, status, methode, hinweis)
  SELECT m_ziel, erhebung_id, bezeichnung, stand, status, methode,
         'Kopie aus dem Referenzmandanten für Übungszwecke.'
    FROM ref_erhebungen WHERE company_id = m_quelle;

  INSERT INTO bitkom_bewertungen (company_id, erhebung_id, id, sub_process_id,
                                  item_nr, stufe, beleg, quelle, bewerter, bewertet_am)
  SELECT m_ziel, erhebung_id, id, sub_process_id,
         item_nr, stufe, beleg, quelle, NULL, bewertet_am
    FROM bitkom_bewertungen WHERE company_id = m_quelle;

  -- Rollen und Kostensätze: die ROI-Achse soll auch zum Ausprobieren dastehen.
  INSERT INTO mandant_rollen (company_id, rolle_id, bezeichnung, klasse, hinweis, aktiv)
  SELECT m_ziel, rolle_id, bezeichnung, klasse, hinweis, aktiv
    FROM mandant_rollen WHERE company_id = m_quelle;

  INSERT INTO rollen_kostensaetze (company_id, klasse, satz_eur_h, quelle, gueltig_ab, bemerkung)
  SELECT m_ziel, klasse, satz_eur_h, quelle, gueltig_ab, bemerkung
    FROM rollen_kostensaetze WHERE company_id = m_quelle;

  -- Personen ohne Klarnamen. Die Funktion bleibt, weil sie die Struktur trägt;
  -- der Name wird durch die ID ersetzt.
  INSERT INTO ref_personen (company_id, person_id, name, funktion, rolle_id,
                            extern, organisation, hinweis, aktiv)
  SELECT m_ziel, person_id,
         'Übungsperson ' || substring(person_id from 3),
         funktion, rolle_id, extern, organisation,
         'Übungsdaten — Name ersetzt (ADR-004 R5).', aktiv
    FROM ref_personen WHERE company_id = m_quelle;

  INSERT INTO prozess_personen (company_id, process_id, person_id, funktion, hinweis)
  SELECT m_ziel, process_id, person_id, funktion, hinweis
    FROM prozess_personen WHERE company_id = m_quelle;

  INSERT INTO mandant_systeme (company_id, system_id, katalog_id, bezeichnung, einsatz, hinweis, aktiv)
  SELECT m_ziel, system_id, katalog_id, bezeichnung, einsatz, hinweis, aktiv
    FROM mandant_systeme WHERE company_id = m_quelle;

  INSERT INTO teilprozess_systeme (company_id, sub_process_id, system_id, nutzung, genauigkeit, hinweis)
  SELECT m_ziel, sub_process_id, system_id, nutzung, genauigkeit, hinweis
    FROM teilprozess_systeme WHERE company_id = m_quelle;

  INSERT INTO medienbrueche (company_id, bruch_id, sub_process_id, von_system_id,
                             nach_system_id, art, beschreibung, aufwand_min, aktiv)
  SELECT m_ziel, bruch_id, sub_process_id, von_system_id,
         nach_system_id, art, beschreibung, aufwand_min, aktiv
    FROM medienbrueche WHERE company_id = m_quelle;

  RAISE NOTICE 'Kopie abgeschlossen.';
END $$;

COMMIT;


-- ============================================================
-- KONTROLLE
-- ============================================================
\echo '--- Mandanten:'
SELECT company_id, name, status FROM companies ORDER BY created_at;

\echo '--- Bewertungen und Reifegrad je Mandant (muessen uebereinstimmen):'
SELECT c.name, count(b.*) AS bewertungen, round(avg(b.stufe), 2) AS reifegrad
  FROM companies c
  LEFT JOIN bitkom_bewertungen b ON b.company_id = c.company_id
 GROUP BY c.name ORDER BY 1;

\echo '--- Keine Klarnamen im Uebungsmandanten (muss leer sein):'
SELECT p.person_id, p.name
  FROM ref_personen p JOIN companies c ON c.company_id = p.company_id
 WHERE c.name LIKE 'Übungsmandant%' AND p.name NOT LIKE 'Übungsperson%';

\echo '--- Gate-Stand im Uebungsmandanten:'
SELECT g.process_id, g.items_gesamt, g.reifegrad_kp, g.bc0_sperre
  FROM v_gate_prozessstand g JOIN companies c ON c.company_id = g.company_id
 WHERE c.name LIKE 'Übungsmandant%' ORDER BY 1;
