-- ============================================================
-- BC0 — Testdaten v1: die drei Use Cases der Projektgruppe
-- Stand: 24.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- ZWECK
--   BC2 bis BC4 brauchen etwas, woran sie entwickeln koennen. Dieses Skript
--   legt die drei im Team beschlossenen Use Cases als Teilprozesse des
--   Mandanten NoroAI an, benennt einen Eigner und hinterlegt je Teilprozess
--   die 30 Bitkom-Bewertungen.
--
-- WAS DIESE DATEN SIND — UND WAS NICHT
--   Es sind Testdaten. Kein Wert darin ist erhoben oder gemessen; die Stufen
--   sind so gesetzt, dass die drei Teilprozesse die im Team genannten
--   Reifegrade exakt tragen (3,20 · 2,50 · 2,00). Jede Bewertung sagt das in
--   ihrem Belegtext — die Belegpflicht ist als CHECK erzwungen, ein leerer
--   Beleg wuerde abgewiesen. Wiederfinden:  WHERE beleg LIKE 'Testdaten%'
--
--   Sie liegen in einer eigenen Erhebung E-2026-08 und beruehren die
--   Ersterhebung nicht: v_bewertung_aktuell setzt den massgeblichen Stand je
--   Item zusammen, und fuer KP-01 bis KP-04 enthaelt E-2026-08 keine Zeile.
--
-- WAS DAS SKRIPT NICHT TUT
--   Keine Systeme (offen) · keine Medienbrueche (die entscheidet der Mensch
--   am Gate 0) · keine BC1-Angaben (fremdes Schema) · keine Belege, kein OCR.
--
-- WIEDERHOLBAR. Zweimaliges Einspielen aendert nichts.
--
-- RUECKWEG
--   DELETE FROM bitkom_bewertungen WHERE erhebung_id = 'E-2026-08';
--   DELETE FROM ref_erhebungen     WHERE erhebung_id = 'E-2026-08';
--   DELETE FROM ref_anfragen       WHERE anfrage_id IN ('A-2026-01','A-2026-02','A-2026-03');
--   Die Teilprozessnamen sind ueberschrieben; vorher hiessen sie
--   'Teilprozess 1' und 'Teilprozess 2'.
--
-- EINSPIELEN
--   psql "$DATABASE_URL" -f daten_v1_use_cases_testdaten.sql
-- ============================================================

DO $$
DECLARE
  cid        uuid;
  eigner_id  text := 'P-07';
  n          int;
BEGIN
  SELECT company_id INTO cid FROM companies WHERE name = 'NoroAI Consulting GmbH';
  IF cid IS NULL THEN
    RAISE EXCEPTION 'Mandant NoroAI Consulting GmbH nicht gefunden. Abbruch.';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM ref_personen WHERE company_id = cid AND person_id = eigner_id) THEN
    RAISE EXCEPTION 'Person % nicht gefunden. Ohne Eigner keine Gate-Vorbedingung.', eigner_id;
  END IF;

  -- ----------------------------------------------------------
  -- 1. Die Erhebung
  -- ----------------------------------------------------------
  INSERT INTO ref_erhebungen (company_id, erhebung_id, bezeichnung, stand, status, methode, hinweis)
  VALUES (cid, 'E-2026-08',
          'Use-Case-Definition der Projektgruppe (Testdaten)',
          DATE '2026-08-24', 'offen', 'gesetzt',
          'Keine Erhebung im fachlichen Sinn. Die Stufen sind gesetzt, damit die drei '
          'Fokus-Teilprozesse die im Team genannten Reifegrade tragen und BC2 bis BC4 '
          'daran entwickeln koennen.')
  ON CONFLICT (company_id, erhebung_id) DO NOTHING;

  -- ----------------------------------------------------------
  -- 2. Teilprozesse benennen und den Ist-Ablauf hinterlegen
  --    tools und medienbrueche bleiben leer: der Medienbruch-Zaehler im Gate
  --    speist sich aus dem Freitextfeld, und diese Entscheidung gehoert dem
  --    Menschen am Gate, nicht diesem Skript.
  -- ----------------------------------------------------------
  UPDATE ref_teilprozesse SET
    sub_process_name = 'Wissenstransfer',
    notation = 'Frage entsteht -> Mitarbeitende durchsuchen Google-Drive-Ordner manuell -> '
               'Dokumente einzeln oeffnen und lesen -> Antwort zusammentragen -> '
               'muendlich oder per Mail weitergeben'
  WHERE company_id = cid AND sub_process_id = 'KP-05.TP-1';

  UPDATE ref_teilprozesse SET
    sub_process_name = 'Neueinstellung und Onboarding',
    notation = 'Lebenslauf geht unstrukturiert ein -> manuell abgelegt -> '
               'Projektausschreibung wird gelesen -> Lebenslaeufe manuell gesichtet -> '
               'Skills mit Anforderungen abgeglichen -> Personalvorschlag zusammengestellt -> '
               'per Mail an das Team'
  WHERE company_id = cid AND sub_process_id = 'KP-06.TP-1';

  UPDATE ref_teilprozesse SET
    sub_process_name = 'Reise- und Einsatzplanung',
    notation = 'Reiseanfrage per Mail oder Formular -> Verfuegbarkeit wird geprueft -> '
               'Angebot manuell erstellt -> Bestaetigung per Mail -> '
               'Buchung manuell vorgenommen'
  WHERE company_id = cid AND sub_process_id = 'KP-06.TP-2';

  -- ----------------------------------------------------------
  -- 3. Eigner — die erste Vorbedingung des Gates
  -- ----------------------------------------------------------
  INSERT INTO prozess_personen (company_id, process_id, person_id, funktion)
  VALUES (cid, 'KP-05', eigner_id, 'eigner'),
         (cid, 'KP-06', eigner_id, 'eigner')
  ON CONFLICT DO NOTHING;

  -- ----------------------------------------------------------
  -- 4. Die 90 Bewertungen
  -- ----------------------------------------------------------
  INSERT INTO bitkom_bewertungen
        (company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg, quelle, bewerter)
  SELECT cid, 'E-2026-08',
         v.tp || '.I-' || lpad(v.nr::text, 2, '0'),
         v.tp, v.nr, v.stufe,
         'Testdaten zur Use-Case-Definition 24.08.2026 - nicht erhoben, nicht gemessen.',
         'manuell', 'PG KI-CoE-KMU (Testdaten)'
    FROM (VALUES
      ('KP-05.TP-1', 1, 4),
      ('KP-05.TP-1', 2, 4),
      ('KP-05.TP-1', 3, 3),
      ('KP-05.TP-1', 4, 4),
      ('KP-05.TP-1', 5, 3),
      ('KP-05.TP-1', 6, 3),
      ('KP-05.TP-1', 7, 3),
      ('KP-05.TP-1', 8, 4),
      ('KP-05.TP-1', 9, 3),
      ('KP-05.TP-1', 10, 3),
      ('KP-05.TP-1', 11, 4),
      ('KP-05.TP-1', 12, 3),
      ('KP-05.TP-1', 13, 3),
      ('KP-05.TP-1', 14, 3),
      ('KP-05.TP-1', 15, 3),
      ('KP-05.TP-1', 16, 3),
      ('KP-05.TP-1', 17, 3),
      ('KP-05.TP-1', 18, 3),
      ('KP-05.TP-1', 19, 3),
      ('KP-05.TP-1', 20, 3),
      ('KP-05.TP-1', 21, 3),
      ('KP-05.TP-1', 22, 4),
      ('KP-05.TP-1', 23, 3),
      ('KP-05.TP-1', 24, 3),
      ('KP-05.TP-1', 25, 3),
      ('KP-05.TP-1', 26, 4),
      ('KP-05.TP-1', 27, 3),
      ('KP-05.TP-1', 28, 3),
      ('KP-05.TP-1', 29, 3),
      ('KP-05.TP-1', 30, 2),
      ('KP-06.TP-1', 1, 3),
      ('KP-06.TP-1', 2, 3),
      ('KP-06.TP-1', 3, 3),
      ('KP-06.TP-1', 4, 3),
      ('KP-06.TP-1', 5, 3),
      ('KP-06.TP-1', 6, 2),
      ('KP-06.TP-1', 7, 2),
      ('KP-06.TP-1', 8, 3),
      ('KP-06.TP-1', 9, 2),
      ('KP-06.TP-1', 10, 3),
      ('KP-06.TP-1', 11, 2),
      ('KP-06.TP-1', 12, 2),
      ('KP-06.TP-1', 13, 3),
      ('KP-06.TP-1', 14, 2),
      ('KP-06.TP-1', 15, 3),
      ('KP-06.TP-1', 16, 2),
      ('KP-06.TP-1', 17, 3),
      ('KP-06.TP-1', 18, 2),
      ('KP-06.TP-1', 19, 3),
      ('KP-06.TP-1', 20, 3),
      ('KP-06.TP-1', 21, 2),
      ('KP-06.TP-1', 22, 3),
      ('KP-06.TP-1', 23, 3),
      ('KP-06.TP-1', 24, 2),
      ('KP-06.TP-1', 25, 2),
      ('KP-06.TP-1', 26, 2),
      ('KP-06.TP-1', 27, 3),
      ('KP-06.TP-1', 28, 2),
      ('KP-06.TP-1', 29, 2),
      ('KP-06.TP-1', 30, 2),
      ('KP-06.TP-2', 1, 3),
      ('KP-06.TP-2', 2, 2),
      ('KP-06.TP-2', 3, 2),
      ('KP-06.TP-2', 4, 3),
      ('KP-06.TP-2', 5, 2),
      ('KP-06.TP-2', 6, 2),
      ('KP-06.TP-2', 7, 2),
      ('KP-06.TP-2', 8, 2),
      ('KP-06.TP-2', 9, 2),
      ('KP-06.TP-2', 10, 2),
      ('KP-06.TP-2', 11, 2),
      ('KP-06.TP-2', 12, 1),
      ('KP-06.TP-2', 13, 2),
      ('KP-06.TP-2', 14, 2),
      ('KP-06.TP-2', 15, 2),
      ('KP-06.TP-2', 16, 2),
      ('KP-06.TP-2', 17, 2),
      ('KP-06.TP-2', 18, 2),
      ('KP-06.TP-2', 19, 2),
      ('KP-06.TP-2', 20, 2),
      ('KP-06.TP-2', 21, 2),
      ('KP-06.TP-2', 22, 2),
      ('KP-06.TP-2', 23, 2),
      ('KP-06.TP-2', 24, 2),
      ('KP-06.TP-2', 25, 2),
      ('KP-06.TP-2', 26, 2),
      ('KP-06.TP-2', 27, 2),
      ('KP-06.TP-2', 28, 2),
      ('KP-06.TP-2', 29, 2),
      ('KP-06.TP-2', 30, 1)
         ) AS v(tp, nr, stufe)
  ON CONFLICT (company_id, erhebung_id, sub_process_id, item_nr) DO NOTHING;

  -- ----------------------------------------------------------
  -- 5. Die drei Anfragen
  --    Der Prozessbezug steht im Hinweis und nicht in eigenen Spalten:
  --    schema_v2.1 ist geschrieben, aber noch nicht eingespielt.
  -- ----------------------------------------------------------
  INSERT INTO ref_anfragen (company_id, anfrage_id, originaltext, eingang_am, eingang_weg, steller_id, hinweis)
  VALUES
   (cid, 'A-2026-01',
    'Use Case 1 - End-to-End Reisebuchungsprozess automatisieren. Heute: Kunde sendet '
    'Anfrage per E-Mail oder Formular, Mitarbeitende pruefen Verfuegbarkeit, Angebote '
    'werden manuell erstellt, Kunde bestaetigt per E-Mail, Buchungen werden manuell '
    'vorgenommen. Ziel: Bearbeitungszeit von Stunden auf Minuten, hoehere '
    'Angebotsgeschwindigkeit.',
    DATE '2026-08-24', 'Testdaten', 'P-07',
    'Fokus: KP-06.TP-2 Reise- und Einsatzplanung. Testdaten, keine echte Anfrage.'),
   (cid, 'A-2026-02',
    'Use Case 2 - Interne Wissensbasis per RAG durchsuchen. Heute: Mitarbeitende suchen '
    'manuell in Google-Drive-Ordnern, Dokumente muessen einzeln geoeffnet werden, Antworten '
    'auf interne Fragestellungen dauern lange, Wissen ist verstreut und schwer auffindbar. '
    'Ziel: Such- und Recherchezeit von Stunden auf Sekunden, eine zentrale und automatisch '
    'aktualisierte Wissensquelle.',
    DATE '2026-08-24', 'Testdaten', 'P-07',
    'Fokus: KP-05.TP-1 Wissenstransfer. Testdaten, keine echte Anfrage.'),
   (cid, 'A-2026-03',
    'Use Case 3 - Consultant Placement fuer HR. Heute: Berater-Lebenslaeufe werden '
    'unstrukturiert und manuell abgelegt, Projektausschreibungen manuell gelesen, '
    'Lebenslaeufe manuell gesichtet, Skills und Erfahrungen manuell mit den '
    'Projektanforderungen abgeglichen, Personalvorschlaege aufwendig zusammengestellt und '
    'per E-Mail versendet. Ziel: Matching von Stunden auf Minuten, praezisere Auswahl, '
    'aktuelle Datenbasis.',
    DATE '2026-08-24', 'Testdaten', 'P-07',
    'Fokus: KP-06.TP-1 Neueinstellung und Onboarding. Testdaten, keine echte Anfrage.')
  ON CONFLICT (company_id, anfrage_id) DO NOTHING;

  SELECT count(*) INTO n
    FROM bitkom_bewertungen WHERE company_id = cid AND erhebung_id = 'E-2026-08';
  RAISE NOTICE 'E-2026-08 traegt jetzt % Bewertungen (erwartet 90).', n;
END $$;

-- ============================================================
-- GEGENPROBEN
-- ============================================================

-- 1. Reifegrad je Fokus-Teilprozess — erwartet 3.20 / 2.50 / 2.00
SELECT b.sub_process_id,
       t.sub_process_name,
       count(*)                        AS items,
       round(avg(b.stufe)::numeric, 2) AS reifegrad
  FROM bitkom_bewertungen b
  JOIN ref_teilprozesse t
    ON t.company_id = b.company_id AND t.sub_process_id = b.sub_process_id
 WHERE b.erhebung_id = 'E-2026-08'
 GROUP BY 1, 2
 ORDER BY 1;

-- 2. Die Ersterhebung ist unberuehrt — erwartet 3.19 / 3.70 / 3.77 / 3.88
SELECT left(sub_process_id, 5)       AS kernprozess,
       round(avg(stufe)::numeric, 2) AS reifegrad
  FROM v_bewertung_aktuell
 WHERE left(sub_process_id, 5) IN ('KP-01', 'KP-02', 'KP-03', 'KP-04')
 GROUP BY 1
 ORDER BY 1;

-- 3. Erste Gate-Vorbedingung: Eigner benannt — erwartet zwei Zeilen mit P-07
SELECT process_id, person_id, funktion
  FROM prozess_personen
 WHERE process_id IN ('KP-05', 'KP-06') AND funktion = 'eigner'
 ORDER BY 1;

-- 4. Die drei Anfragen — erwartet drei Zeilen
SELECT anfrage_id, eingang_weg, left(hinweis, 44) AS fokus
  FROM ref_anfragen
 WHERE anfrage_id LIKE 'A-2026-0%'
 ORDER BY 1;
