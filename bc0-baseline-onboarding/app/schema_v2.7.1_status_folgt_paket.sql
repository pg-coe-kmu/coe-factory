-- Schema v2.7.1 — Status folgt dem Paket, auch aus `eingegangen` (04.09.2026)
--
-- Befund aus der Browser-Probe beim Ausrollen von v2.6 + v2.7 (Übungsmandant,
-- A-2026-01, Paket fd2e2712): Das Paket entstand, das Ereignis `uebergeben` am
-- Objekt `anfrage` stand in gate_ereignisse — aber ref_anfragen.status blieb
-- `eingegangen`. Grund: gate_paket_schnueren() setzte den Status nur aus
-- zugeordnet / im_interview / am_gate. Eine Anfrage, deren Status nie von Hand
-- weitergezogen wurde (das ist im Betrieb der Regelfall: alle vier
-- NoroAI-Anfragen stehen auf `eingegangen`, obwohl sie einen Prozessbezug
-- tragen), blieb damit hinter ihrem Paket zurueck — ein Widerspruch in der
-- Quelle der Wahrheit.
--
-- Regel: Wer ein Paket hat, ist uebergeben. Ein Ruecksprung bleibt ausgeschlossen
-- (bewertet, beauftragt, erledigt bleiben stehen; abgelehnt kommt gar nicht bis
-- hierher).
--
-- Aendert ausschliesslich den Funktionsrumpf (CREATE OR REPLACE, gleiche
-- Signatur) und zieht die bereits uebergebenen Anfragen nach. Alles andere aus
-- v2.7 bleibt, wie es ist.
--
-- Ausfuehren: als Eigentuemer, in einer Transaktion.

BEGIN;

CREATE OR REPLACE FUNCTION gate_paket_schnueren(
    p_company UUID, p_benutzer TEXT, p_hinweis TEXT,
    p_anfrage TEXT DEFAULT NULL, p_teilprozesse TEXT[] DEFAULT NULL)
RETURNS UUID AS $fn$
DECLARE
  v_paket    UUID := gen_random_uuid();
  v_ereignis BIGINT;
  v_soll     INTEGER; v_frei INTEGER; v_neu INTEGER;
  v_fehlend  TEXT;
  v_status   TEXT;
BEGIN
  IF p_anfrage IS NOT NULL THEN
    -- ---- Weg 1: die Anfrage, vollstaendig ----
    SELECT status INTO v_status FROM ref_anfragen
     WHERE company_id = p_company AND anfrage_id = p_anfrage;
    IF v_status IS NULL THEN
      RAISE EXCEPTION 'Unbekannte Anfrage: %', p_anfrage USING ERRCODE = 'check_violation';
    END IF;
    IF v_status = 'abgelehnt' THEN
      RAISE EXCEPTION 'Anfrage % ist abgelehnt.', p_anfrage USING ERRCODE = 'check_violation';
    END IF;

    SELECT count(*), count(*) FILTER (WHERE freigegeben),
           count(*) FILTER (WHERE NOT coalesce(im_paket, false)),
           string_agg(sub_process_id, ', ' ORDER BY sub_process_id) FILTER (WHERE NOT coalesce(freigegeben, false))
      INTO v_soll, v_frei, v_neu, v_fehlend
      FROM v_anfrage_teilprozesse
     WHERE company_id = p_company AND anfrage_id = p_anfrage;

    IF v_soll = 0 THEN
      RAISE EXCEPTION 'Anfrage % hat keinen Teilprozess — erst zuordnen (anfrage_prozesse).', p_anfrage
        USING ERRCODE = 'check_violation';
    END IF;
    IF v_frei < v_soll THEN
      RAISE EXCEPTION 'Anfrage % ist nicht vollstaendig freigegeben: % von % — es fehlen %. '
                      'Uebergeben wird nur vollstaendig.', p_anfrage, v_frei, v_soll, v_fehlend
        USING ERRCODE = 'check_violation';
    END IF;
    IF v_neu = 0 THEN
      RAISE EXCEPTION 'Anfrage % ist mit genau diesen Freigaben bereits uebergeben. Ein zweites, '
                      'identisches Paket entsteht nicht.', p_anfrage USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO gate_ereignisse (gate, company_id, objekt_typ, objekt_id, ereignis,
                                 benutzer_id, paket_id, anfrage_id, grundlage)
    VALUES ('bc0-bc2', p_company, 'anfrage', p_anfrage, 'uebergeben',
            p_benutzer, v_paket, p_anfrage, jsonb_build_object('teilprozesse', v_soll))
    RETURNING ereignis_id INTO v_ereignis;

    INSERT INTO gate_pakete (company_id, paket_id, uebergeben_von, ereignis_id, hinweis)
    VALUES (p_company, v_paket, p_benutzer, v_ereignis, p_hinweis);

    INSERT INTO gate_paket_inhalt (company_id, paket_id, sub_process_id, freigabe_ereignis_id,
                                   anfrage_id, bc1_profil_stand, hinweis_an_bc2)
    SELECT t.company_id, v_paket, t.sub_process_id, t.freigabe_ereignis_id,
           p_anfrage, f.bc1_profil_stand, f.hinweis_an_bc2
      FROM v_anfrage_teilprozesse t
      JOIN v_gate_freigabe_aktuell f
        ON f.company_id = t.company_id AND f.sub_process_id = t.sub_process_id
     WHERE t.company_id = p_company AND t.anfrage_id = p_anfrage;

    -- v2.7.1: Der Status folgt dem Paket — aus JEDEM Stand vor `uebergeben`,
    -- auch aus `eingegangen`. Ein Ruecksprung ist kein Fall: wer schon weiter
    -- ist (bewertet …), bleibt es — dann war es ein neues Paket nach einer
    -- Umfangsaenderung, und BC2 rechnet neu.
    UPDATE ref_anfragen SET status = 'uebergeben', status_seit = current_date
     WHERE company_id = p_company AND anfrage_id = p_anfrage
       AND status IN ('eingegangen','zugeordnet','im_interview','am_gate');

  ELSE
    -- ---- Weg 2: Portfolio, mit ausdruecklicher Liste ----
    IF p_teilprozesse IS NULL OR array_length(p_teilprozesse, 1) IS NULL THEN
      RAISE EXCEPTION 'Ohne Anfrage braucht die Uebergabe eine ausdrueckliche Liste der Teilprozesse.'
        USING ERRCODE = 'check_violation';
    END IF;
    SELECT string_agg(x, ', ') INTO v_fehlend
      FROM unnest(p_teilprozesse) x
     WHERE NOT EXISTS (SELECT 1 FROM v_uebergabe_kandidaten k
                        WHERE k.company_id = p_company AND k.sub_process_id = x);
    IF v_fehlend IS NOT NULL THEN
      RAISE EXCEPTION 'Nicht uebergabefaehig (nicht freigegeben oder schon in einem Paket): %', v_fehlend
        USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO gate_ereignisse (gate, company_id, objekt_typ, objekt_id, ereignis,
                                 benutzer_id, paket_id, grundlage)
    VALUES ('bc0-bc2', p_company, 'unternehmen', p_company::text, 'uebergeben',
            p_benutzer, v_paket, jsonb_build_object('teilprozesse', array_length(p_teilprozesse, 1),
                                                     'portfolio', true))
    RETURNING ereignis_id INTO v_ereignis;

    INSERT INTO gate_pakete (company_id, paket_id, uebergeben_von, ereignis_id, hinweis)
    VALUES (p_company, v_paket, p_benutzer, v_ereignis, p_hinweis);

    INSERT INTO gate_paket_inhalt (company_id, paket_id, sub_process_id, freigabe_ereignis_id,
                                   anfrage_id, bc1_profil_stand, hinweis_an_bc2)
    SELECT k.company_id, v_paket, k.sub_process_id, k.freigabe_ereignis_id,
           NULL, k.bc1_profil_stand, k.hinweis_an_bc2
      FROM v_uebergabe_kandidaten k
     WHERE k.company_id = p_company AND k.sub_process_id = ANY (p_teilprozesse);
  END IF;

  RETURN v_paket;
END;
$fn$ LANGUAGE plpgsql;

COMMENT ON FUNCTION gate_paket_schnueren(UUID, TEXT, TEXT, TEXT, TEXT[]) IS
  'Paket an BC2. Mit p_anfrage: nur, wenn ALLE Teilprozesse der Anfrage '
  '(v_anfrage_teilprozesse) freigegeben sind — sonst Abbruch mit der Liste der '
  'fehlenden; setzt den Anfragestatus auf uebergeben (v2.7.1: aus jedem Stand '
  'davor, auch eingegangen). Ohne p_anfrage: Portfolio-Weg mit ausdruecklicher '
  'Liste aus v_uebergabe_kandidaten.';

-- Nachziehen: Anfragen, die schon ein Paket haben, aber im Status dahinter
-- zurueckgeblieben sind. Der Historie-Trigger schreibt die Aenderung mit
-- (Akteur: wer dieses Blatt ausfuehrt, ueber bc0.benutzer — sonst 'db').
UPDATE ref_anfragen a
   SET status = 'uebergeben', status_seit = current_date
 WHERE a.status IN ('eingegangen','zugeordnet','im_interview','am_gate')
   AND EXISTS (SELECT 1 FROM gate_paket_inhalt i
                WHERE i.company_id = a.company_id AND i.anfrage_id = a.anfrage_id);

COMMIT;

-- Kontrolle (Erwartung: keine Zeile — jede Anfrage mit Paket ist uebergeben oder weiter):
-- SELECT a.company_id, a.anfrage_id, a.status
--   FROM ref_anfragen a
--  WHERE a.status IN ('eingegangen','zugeordnet','im_interview','am_gate')
--    AND EXISTS (SELECT 1 FROM gate_paket_inhalt i
--                 WHERE i.company_id = a.company_id AND i.anfrage_id = a.anfrage_id);
