CREATE OR REPLACE FUNCTION public.trg_historie()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
  j_alt JSONB; j_neu JSONB; j_pk JSONB; v_company UUID; v_actor TEXT;
BEGIN
  IF TG_OP IN ('UPDATE','DELETE') THEN j_alt := to_jsonb(OLD); END IF;
  IF TG_OP IN ('INSERT','UPDATE') THEN j_neu := to_jsonb(NEW); END IF;

  -- Primaerschluessel aus dem Katalog, nicht aus einer Liste: gilt fuer jede
  -- Tabelle, auch fuer kuenftige.
  SELECT jsonb_object_agg(a.attname, coalesce(j_neu, j_alt) -> a.attname)
    INTO j_pk
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
   WHERE i.indrelid = TG_RELID AND i.indisprimary;

  v_company := (coalesce(j_neu, j_alt) ->> 'company_id')::uuid;
  v_actor   := coalesce(nullif(current_setting('bc0.benutzer', true), ''), current_user);

  j_alt := historie_pii_entfernen(TG_TABLE_NAME, j_alt);
  j_neu := historie_pii_entfernen(TG_TABLE_NAME, j_neu);

  INSERT INTO audit_log (company_id, entity, entity_id, action, actor, payload, at, pk, alt, neu, txid)
  VALUES (v_company, TG_TABLE_NAME, j_pk::text, TG_OP, v_actor, j_neu, now(), j_pk, j_alt, j_neu,
          txid_current());

  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_kernprozess_bleibt_aktiv()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.aktiv = false THEN
    RAISE EXCEPTION
      'Kernprozess % kann nicht stillgelegt werden - nur seine Teilprozesse. '
      'Ein Kernprozess ist eine fachliche Kategorie und wird im Unternehmen '
      'nie ausser Betrieb genommen (Entscheidung BC0, 23.09.2026).', NEW.process_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_stilllegen_statt_loeschen()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF pg_trigger_depth() > 1 THEN RETURN OLD; END IF;   -- Kaskade vom Mandanten/Kernprozess
  RAISE EXCEPTION
    'Loeschen in % abgewiesen — stilllegen (aktiv = false). Bewertungen, '
    'Freigaben und BC-Ergebnisse haengen daran (ADR-004 R4).', TG_TABLE_NAME
    USING ERRCODE = 'check_violation';
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_teilprozess_eingefroren()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE v_anfrage TEXT;
BEGIN
  SELECT anfrage_id INTO v_anfrage FROM teilprozess_abgeloest
   WHERE company_id = NEW.company_id
     AND sub_process_id = (CASE WHEN TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'ref_teilprozesse'
                                THEN OLD.sub_process_id ELSE NEW.sub_process_id END);
  IF v_anfrage IS NOT NULL THEN
    RAISE EXCEPTION 'Teilprozess % ist durch den Folgeprozess aus % abgeloest und eingefroren — '
                    'keine Aenderung mehr (%).', NEW.sub_process_id, v_anfrage, TG_TABLE_NAME
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_erhebung_eingefroren()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE v_company UUID; v_erhebung TEXT; v_status TEXT;
BEGIN
  -- Kaskaden (Loeschen des Mandanten) laufen durch: eine Ebene tiefer.
  IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN RETURN OLD; END IF;
  IF TG_OP = 'DELETE' THEN v_company := OLD.company_id; v_erhebung := OLD.erhebung_id;
  ELSE                     v_company := NEW.company_id; v_erhebung := NEW.erhebung_id; END IF;
  SELECT status INTO v_status FROM ref_erhebungen
   WHERE company_id = v_company AND erhebung_id = v_erhebung;
  IF v_status = 'abgeschlossen' THEN
    RAISE EXCEPTION
      'Erhebung % ist abgeschlossen und eingefroren. Fuer neue Werte eine neue '
      'Erhebung beginnen (POST …/erhebungen, aktion=neu).', v_erhebung
      USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_gate_datenstand()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE v_name TEXT;
BEGIN
  IF NEW.gate = 'bc0-bc2' AND NEW.objekt_typ = 'teilprozess' AND NEW.ereignis = 'freigegeben' THEN
    SELECT sub_process_name INTO v_name FROM ref_teilprozesse
     WHERE company_id = NEW.company_id AND sub_process_id = NEW.objekt_id;
    IF teilprozess_unbenannt(v_name) THEN
      RAISE EXCEPTION 'Teilprozess % ist noch nicht benannt ("%"). Freigabe erst mit eindeutigem Namen.',
                      NEW.objekt_id, coalesce(v_name, '')
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  IF NEW.datenstand IS NULL THEN
    NEW.datenstand := (SELECT max(audit_id) FROM audit_log);
  END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_erhebung_status_vorwaerts()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF OLD.status = 'abgeschlossen' AND NEW.status = 'offen' THEN
    RAISE EXCEPTION
      'Erhebung % kann nicht wieder geoeffnet werden. Verwerfen und neu beginnen — '
      'eine Freigabe koennte sich auf diesen Stand beziehen.', OLD.erhebung_id
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.status = 'verworfen' AND NEW.status <> 'verworfen' THEN
    RAISE EXCEPTION 'Erhebung % ist verworfen und bleibt es.', OLD.erhebung_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_nur_anhaengen()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN RETURN OLD; END IF;
  RAISE EXCEPTION '% ist append-only: % nicht erlaubt. Nachzuegler bekommen ein neues Paket.',
    TG_TABLE_NAME, TG_OP USING ERRCODE = 'check_violation';
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_anfrage_prozesse_benannt()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE v_name TEXT;
BEGIN
  IF NEW.sub_process_id IS NOT NULL THEN
    SELECT sub_process_name INTO v_name FROM ref_teilprozesse
     WHERE company_id = NEW.company_id AND sub_process_id = NEW.sub_process_id;
    IF teilprozess_unbenannt(v_name) THEN
      RAISE EXCEPTION 'Teilprozess % ist noch nicht benannt ("%"). Erst benennen, dann der Anfrage zuordnen.',
                      NEW.sub_process_id, coalesce(v_name, '')
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_ap_haupt_spiegeln()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.rolle = 'haupt' THEN
    UPDATE ref_anfragen
       SET process_id = NEW.process_id, sub_process_id = NEW.sub_process_id,
           zuordnung_quelle = NEW.zuordnung_quelle
     WHERE company_id = NEW.company_id AND anfrage_id = NEW.anfrage_id
       AND (process_id IS DISTINCT FROM NEW.process_id
            OR sub_process_id IS DISTINCT FROM NEW.sub_process_id
            OR zuordnung_quelle IS DISTINCT FROM NEW.zuordnung_quelle);
  END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_kir_durchlauf_pruefen()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE v_max INTEGER; v_uc TEXT;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF pg_trigger_depth() > 1 THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'kir_durchlauf: Loeschen nicht erlaubt.' USING ERRCODE='check_violation';
  END IF;
  IF TG_OP = 'INSERT' THEN
    SELECT max(durchlauf_nr), max(use_case) INTO v_max, v_uc FROM kir_durchlauf
     WHERE company_id = NEW.company_id AND paket_id = NEW.paket_id;
    IF NEW.durchlauf_nr <> coalesce(v_max,0) + 1 THEN
      RAISE EXCEPTION 'Durchlauf % passt nicht: als naechster ist % dran.', NEW.durchlauf_nr, coalesce(v_max,0)+1
        USING ERRCODE='check_violation';
    END IF;
    IF v_uc IS NOT NULL AND v_uc <> NEW.use_case THEN
      RAISE EXCEPTION 'Paket gehoert zu %, nicht zu %.', v_uc, NEW.use_case USING ERRCODE='check_violation';
    END IF;
    IF NEW.entscheidung IS NOT NULL THEN
      RAISE EXCEPTION 'Ein Durchlauf wird ohne Entscheidung angelegt.' USING ERRCODE='check_violation';
    END IF;
    RETURN NEW;
  END IF;
  -- UPDATE: nur einmal entscheiden, sonst nichts aendern
  IF OLD.entscheidung IS NOT NULL THEN
    RAISE EXCEPTION 'Durchlauf % ist entschieden (%), Aenderung nicht erlaubt.', OLD.durchlauf_nr, OLD.entscheidung
      USING ERRCODE='check_violation';
  END IF;
  IF (NEW.company_id, NEW.paket_id, NEW.durchlauf_nr, NEW.use_case, NEW.anlass, NEW.angelegt_am, NEW.angelegt_von)
     IS DISTINCT FROM (OLD.company_id, OLD.paket_id, OLD.durchlauf_nr, OLD.use_case, OLD.anlass, OLD.angelegt_am, OLD.angelegt_von) THEN
    RAISE EXCEPTION 'An einem Durchlauf ist nur die Entscheidung nachzutragen.' USING ERRCODE='check_violation';
  END IF;
  RETURN NEW;
END;
$function$
;
