-- Schema v3.24 — Sammelpaket: mehrere Anfragen, EINE Paket-ID (31.10.2026)
--
-- Anlass (Drehbuch S-196..S-198): UC1 Reisebuchung lief als vier Anfragen
-- (A-2026-01..04, je ein Teilprozess KP-06.TP-2..5), weil BC1 noch keine
-- mehreren Teilprozesse je Interview fuehrt. Uebergeben wurde je Anfrage ein
-- Paket — BC2 rechnet damit vier Laeufe statt einem (ADR-005: ein Lauf = ein
-- Paket; #194: ein Modellaufruf je Paket, ueber alle Teilprozesse).
--
-- Neu: gate_paket_buendeln(company, benutzer, hinweis, anfragen[]).
--   * Jede genannte Anfrage muss fuer sich VOLLSTAENDIG freigegeben sein
--     (dieselbe Regel wie Weg 1, BC0 03.09.: kein ROI auf einem Ausschnitt).
--   * Alle Teilprozesse aller Anfragen gehen in EIN Paket; jede Zeile behaelt
--     ihre anfrage_id, Freigabe und BC1-Fassung (wie Weg 1).
--   * Ein Teilprozess darf nur einmal im Paket stehen (Schluessel
--     company_id, paket_id, sub_process_id) — gehoeren zwei Anfragen auf
--     denselben Teilprozess, bricht die Funktion lesbar ab.
--   * Kein identisches zweites Paket: Gibt es schon ein Paket mit genau
--     denselben (Teilprozess, Freigabe)-Paaren, entsteht keins. Vier
--     Einzelpakete sind nicht identisch mit dem Buendel — das Nachbuendeln
--     von heute ist erlaubt.
--   * Ereignis `uebergeben` am Unternehmen (Paketereignis) und je Anfrage
--     ein Ereignis `uebergeben` am Objekt `anfrage` mit derselben paket_id
--     (damit der Verlauf jeder Anfrage das Paket zeigt).
--   * Status jeder Anfrage folgt dem Paket wie in v2.7.1.
--
-- gate_paket_schnueren() bleibt UNVERAENDERT (Weg 1 Anfrage, Weg 2 Portfolio).
-- Keine Tabelle, keine Sicht, keine Daten werden geaendert.
--
-- Ausfuehren als postgres, eine Transaktion. Gegenprobe: pruefung_v3.24_sammelpaket.sql

BEGIN;

CREATE OR REPLACE FUNCTION gate_paket_buendeln(
    p_company   UUID,
    p_benutzer  TEXT,
    p_hinweis   TEXT,
    p_anfragen  TEXT[]
) RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  v_paket    UUID := gen_random_uuid();
  v_ereignis BIGINT;
  v_liste    TEXT[];
  v_fehler   TEXT;
  v_doppelt  TEXT;
  v_neu      TEXT[];
  v_anzahl   INTEGER;
  a          TEXT;
BEGIN
  SELECT array_agg(DISTINCT btrim(x) ORDER BY btrim(x)) INTO v_liste
    FROM unnest(coalesce(p_anfragen, ARRAY[]::text[])) x
   WHERE btrim(x) <> '';
  IF v_liste IS NULL OR array_length(v_liste, 1) IS NULL THEN
    RAISE EXCEPTION 'Fuer ein Sammelpaket mindestens eine Anfrage auswaehlen.'
      USING ERRCODE = 'check_violation';
  END IF;

  -- unbekannt / abgelehnt
  SELECT string_agg(x, ', ' ORDER BY x) INTO v_fehler
    FROM unnest(v_liste) x
   WHERE NOT EXISTS (SELECT 1 FROM ref_anfragen r WHERE r.company_id = p_company AND r.anfrage_id = x);
  IF v_fehler IS NOT NULL THEN
    RAISE EXCEPTION 'Unbekannte Anfrage: %', v_fehler USING ERRCODE = 'check_violation';
  END IF;
  SELECT string_agg(anfrage_id, ', ' ORDER BY anfrage_id) INTO v_fehler
    FROM ref_anfragen WHERE company_id = p_company AND anfrage_id = ANY (v_liste) AND status = 'abgelehnt';
  IF v_fehler IS NOT NULL THEN
    RAISE EXCEPTION 'Abgelehnt und damit nicht uebergebbar: %', v_fehler USING ERRCODE = 'check_violation';
  END IF;

  -- je Anfrage vollstaendig (Weg-1-Regel)
  SELECT string_agg(z, '; ' ORDER BY z) INTO v_fehler FROM (
    SELECT x || CASE WHEN count(t.sub_process_id) = 0 THEN ' hat keinen Teilprozess'
                     ELSE ': ' || count(*) FILTER (WHERE t.freigegeben) || ' von ' || count(t.sub_process_id)
                          || ' — es fehlen ' || string_agg(t.sub_process_id, ', ' ORDER BY t.sub_process_id)
                                                 FILTER (WHERE NOT coalesce(t.freigegeben, false)) END AS z
      FROM unnest(v_liste) x
      LEFT JOIN v_anfrage_teilprozesse t ON t.company_id = p_company AND t.anfrage_id = x
     GROUP BY x
    HAVING count(t.sub_process_id) = 0
        OR count(*) FILTER (WHERE t.freigegeben) < count(t.sub_process_id)) q;
  IF v_fehler IS NOT NULL THEN
    RAISE EXCEPTION 'Nicht vollstaendig freigegeben — uebergeben wird nur vollstaendig: %', v_fehler
      USING ERRCODE = 'check_violation';
  END IF;

  -- ein Teilprozess nur einmal im Paket
  SELECT string_agg(sub_process_id || ' (' || anf || ')', '; ' ORDER BY sub_process_id) INTO v_doppelt FROM (
    SELECT sub_process_id, string_agg(anfrage_id, ', ' ORDER BY anfrage_id) AS anf
      FROM v_anfrage_teilprozesse
     WHERE company_id = p_company AND anfrage_id = ANY (v_liste)
     GROUP BY sub_process_id HAVING count(DISTINCT anfrage_id) > 1) d;
  IF v_doppelt IS NOT NULL THEN
    RAISE EXCEPTION 'Derselbe Teilprozess gehoert zu mehreren ausgewaehlten Anfragen: %. '
                    'Ein Paket enthaelt jeden Teilprozess nur einmal — getrennt uebergeben.', v_doppelt
      USING ERRCODE = 'check_violation';
  END IF;

  -- kein identisches zweites Paket
  SELECT array_agg(sub_process_id || '#' || freigabe_ereignis_id ORDER BY sub_process_id) INTO v_neu
    FROM v_anfrage_teilprozesse
   WHERE company_id = p_company AND anfrage_id = ANY (v_liste);
  IF EXISTS (
      SELECT 1 FROM gate_paket_inhalt i
       WHERE i.company_id = p_company
       GROUP BY i.paket_id
      HAVING array_agg(i.sub_process_id || '#' || i.freigabe_ereignis_id ORDER BY i.sub_process_id) = v_neu) THEN
    RAISE EXCEPTION 'Genau diese Freigaben sind bereits als ein Paket uebergeben. Ein zweites, '
                    'identisches Paket entsteht nicht.' USING ERRCODE = 'check_violation';
  END IF;
  v_anzahl := array_length(v_neu, 1);

  INSERT INTO gate_ereignisse (gate, company_id, objekt_typ, objekt_id, ereignis,
                               benutzer_id, paket_id, grundlage)
  VALUES ('bc0-bc2', p_company, 'unternehmen', p_company::text, 'uebergeben',
          p_benutzer, v_paket, jsonb_build_object('teilprozesse', v_anzahl,
                                                   'anfragen', to_jsonb(v_liste),
                                                   'sammelpaket', true))
  RETURNING ereignis_id INTO v_ereignis;

  INSERT INTO gate_pakete (company_id, paket_id, uebergeben_von, ereignis_id, hinweis)
  VALUES (p_company, v_paket, p_benutzer, v_ereignis, p_hinweis);

  INSERT INTO gate_paket_inhalt (company_id, paket_id, sub_process_id, freigabe_ereignis_id,
                                 anfrage_id, bc1_profil_stand, hinweis_an_bc2)
  SELECT t.company_id, v_paket, t.sub_process_id, t.freigabe_ereignis_id,
         t.anfrage_id, f.bc1_profil_stand, f.hinweis_an_bc2
    FROM v_anfrage_teilprozesse t
    JOIN v_gate_freigabe_aktuell f
      ON f.company_id = t.company_id AND f.sub_process_id = t.sub_process_id
   WHERE t.company_id = p_company AND t.anfrage_id = ANY (v_liste);

  FOREACH a IN ARRAY v_liste LOOP
    INSERT INTO gate_ereignisse (gate, company_id, objekt_typ, objekt_id, ereignis,
                                 benutzer_id, paket_id, anfrage_id, grundlage)
    VALUES ('bc0-bc2', p_company, 'anfrage', a, 'uebergeben', p_benutzer, v_paket, a,
            jsonb_build_object('sammelpaket', true, 'anfragen', to_jsonb(v_liste)));
  END LOOP;

  UPDATE ref_anfragen SET status = 'uebergeben', status_seit = current_date
   WHERE company_id = p_company AND anfrage_id = ANY (v_liste)
     AND status IN ('eingegangen','zugeordnet','im_interview','am_gate');

  RETURN v_paket;
END;
$$;

COMMENT ON FUNCTION gate_paket_buendeln(UUID, TEXT, TEXT, TEXT[]) IS
  'v3.24: mehrere vollstaendig freigegebene Anfragen als EIN Paket an BC2 (ein Lauf, ein Modellaufruf). '
  'gate_paket_schnueren() bleibt fuer Weg 1 (eine Anfrage) und Weg 2 (Portfolio).';

REVOKE ALL ON FUNCTION gate_paket_buendeln(UUID, TEXT, TEXT, TEXT[]) FROM PUBLIC;
DO $r$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON FUNCTION gate_paket_buendeln(UUID, TEXT, TEXT, TEXT[]) FROM anon, authenticated';
  END IF;
END $r$;

COMMIT;
