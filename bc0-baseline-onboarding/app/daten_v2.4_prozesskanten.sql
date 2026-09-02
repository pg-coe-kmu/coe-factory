-- ============================================================================
-- daten_v2.4 — Prozesskanten für NoroAI Consulting GmbH
-- BC0 · Simeon Ehmer · 02.09.2026
-- ============================================================================
--
-- ANLASS
--   `prozess_schnittstellen` steht seit Schema v1.2 und war am 02.09.2026 bei
--   allen zehn Kernprozessen **leer**. Der Reifegradbericht liest die Tabelle
--   bereits und sortiert die Prozesskette danach — ohne Kanten steht sie nach
--   ID statt nach Ablauf. Aufgefallen ist es durch Richards Frage 6.
--
-- HERKUNFT JE KANTE (ADR-005 R2)
--   Die Spalte `beschreibung` trägt, woher die Kante stammt. Zwei Stufen:
--
--   "belegt: …"      Der `trigger_text` des ZIELPROZESSES nennt das Ergebnis
--                    des Quellprozesses woertlich. Diese acht Kanten stehen
--                    bereits in den Daten, sie waren nur nie als Kante
--                    hinterlegt.
--
--   "angenommen …"   Fachlich plausibel, aber nirgends belegt. Am 02.09.2026
--                    bewusst ungeprueft uebernommen, um die Kette ueberhaupt
--                    zu haben. **Diese acht gehoeren nachgeprueft.**
--
--   Ohne diese Unterscheidung waere in vier Wochen nicht mehr erkennbar,
--   welche Kante auf einem Beleg steht und welche auf einer Vermutung — und
--   genau das ist der Unterschied, den ADR-005 verlangt.
--
-- IDEMPOTENZ
--   ON CONFLICT DO NOTHING. Ein zweiter Lauf aendert nichts; bereits von Hand
--   berichtigte Kanten werden NICHT ueberschrieben.
-- ============================================================================

BEGIN;

DO $$
DECLARE
  cid       UUID;
  vorher    INTEGER;
  nachher   INTEGER;
BEGIN
  SELECT company_id INTO cid FROM companies WHERE name LIKE 'NoroAI%';
  IF cid IS NULL THEN
    RAISE EXCEPTION 'Mandant NoroAI nicht gefunden.';
  END IF;

  SELECT count(*) INTO vorher FROM prozess_schnittstellen WHERE company_id = cid;
  RAISE NOTICE 'Kanten vorher: %', vorher;

  INSERT INTO prozess_schnittstellen
        (company_id, von_process_id, nach_process_id, art, beschreibung)
  VALUES
  -- ---- belegt durch den trigger_text des Zielprozesses -------------------
  (cid,'KP-02','KP-03','freigabe',
   'belegt: KP-03 nennt als Ausloeser "unterzeichneter Engagement-Vertrag" — Ergebnis von KP-02.TP-5 Vertragsabschluss'),
  (cid,'KP-03','KP-04','freigabe',
   'belegt: KP-04 nennt als Ausloeser "abgeschlossenes Onboarding" — Ergebnis von KP-03.TP-5'),
  (cid,'KP-04','KP-09','information',
   'belegt: KP-09 nennt als Ausloeser "Sprint-Ende · Retro-Termin" — KP-04.TP-2 Sprint durchfuehren'),
  (cid,'KP-04','KP-07','daten',
   'belegt: KP-07 nennt als Ausloeser "Rechnungslauf" — KP-04.TP-4 Phasen-Abschluss + Rechnung'),
  (cid,'KP-04','KP-05','information',
   'belegt: KP-05 nennt als Ausloeser "Wissensbedarf" — KP-04.TP-5 Lessons Learned ableiten'),
  (cid,'KP-03','KP-08','daten',
   'belegt: KP-08 nennt als Ausloeser "Tool-Bereitstellung" — KP-03.TP-3 Tooling einrichten'),
  (cid,'KP-03','KP-10','freigabe',
   'belegt: KP-10 nennt als Ausloeser "Compliance-Pflicht" — KP-03.TP-4 AVV + DSGVO klaeren'),
  (cid,'KP-06','KP-08','daten',
   'belegt: KP-08 nennt als Ausloeser "Tool-Bereitstellung" — KP-06.TP-1 Neueinstellung und Onboarding'),

  -- ---- angenommen, ungeprueft (02.09.2026) -------------------------------
  (cid,'KP-01','KP-02','information',
   'angenommen 02.09.2026, ungeprueft: Strategie gibt Zielkunden und Positionierung vor'),
  (cid,'KP-02','KP-01','information',
   'angenommen 02.09.2026, ungeprueft: Marktrueckmeldung fliesst in die Klausur'),
  (cid,'KP-04','KP-01','daten',
   'angenommen 02.09.2026, ungeprueft: Auslastung und Ergebnisse ins Quartals-Re-Assessment'),
  (cid,'KP-09','KP-01','information',
   'angenommen 02.09.2026, ungeprueft: Retro-Erkenntnisse in die Strategie'),
  (cid,'KP-05','KP-04','information',
   'angenommen 02.09.2026, ungeprueft: Wissensbasis in die Durchfuehrung'),
  (cid,'KP-05','KP-02','information',
   'angenommen 02.09.2026, ungeprueft: Referenzen und Bausteine fuer Angebote'),
  (cid,'KP-06','KP-07','daten',
   'angenommen 02.09.2026, ungeprueft: Personal → Lohn und Reisekosten'),
  (cid,'KP-06','KP-04','daten',
   'angenommen 02.09.2026, ungeprueft: Einsatzplanung → Sprint-Besetzung')
  ON CONFLICT DO NOTHING;

  SELECT count(*) INTO nachher FROM prozess_schnittstellen WHERE company_id = cid;
  RAISE NOTICE 'Kanten nachher: % (neu: %)', nachher, nachher - vorher;

  IF nachher < 16 THEN
    RAISE EXCEPTION 'Erwartet waren mindestens 16 Kanten, gefunden %.', nachher;
  END IF;
END $$;

COMMIT;

-- ============================================================================
-- Kontrolle: wie viele stehen auf einem Beleg, wie viele auf einer Annahme?
-- ============================================================================
SELECT CASE WHEN beschreibung LIKE 'belegt:%' THEN 'belegt' ELSE 'angenommen' END AS herkunft,
       count(*) AS kanten
  FROM prozess_schnittstellen s
  JOIN companies c ON c.company_id = s.company_id
 WHERE c.name LIKE 'NoroAI%'
 GROUP BY 1
 ORDER BY 1;
