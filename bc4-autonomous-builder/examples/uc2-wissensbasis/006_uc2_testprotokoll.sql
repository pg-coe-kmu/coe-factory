-- UC2 Weiterentwicklung: nur neue Protokolltabelle und Funktion.
-- Bestehende Wissensdokumente, Chunks und Suchfunktionen bleiben unveraendert.
BEGIN;
CREATE TABLE IF NOT EXISTS public.uc2_query_runs (
  run_id text PRIMARY KEY CHECK (length(run_id) BETWEEN 1 AND 160),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  status text NOT NULL CHECK (status IN ('answered','partially_answered','conflict',
    'abstained_model','abstained_retrieval','model_validation_error','technical_error','input_error')),
  question text NOT NULL CHECK (length(question)<=2000),
  workflow_version text NOT NULL,
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=150000)
);
ALTER TABLE public.uc2_query_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.uc2_query_runs FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.uc2_query_runs TO service_role;

CREATE OR REPLACE FUNCTION public.uc2_log_run(p_run jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE k text; old_payload jsonb;
BEGIN
  IF p_run IS NULL OR jsonb_typeof(p_run) IS DISTINCT FROM 'object'
    OR octet_length(p_run::text)>150000 THEN RAISE EXCEPTION 'UC2_INVALID_LOG'; END IF;
  FOREACH k IN ARRAY ARRAY['run_id','status','question','workflow_version','prompt_version',
    'schema_version','validator_version','started_at','finished_at','output'] LOOP
    IF jsonb_typeof(p_run->k) IS DISTINCT FROM 'string' THEN
      RAISE EXCEPTION 'UC2_INVALID_LOG_FIELD: %',k; END IF;
  END LOOP;
  IF btrim(p_run->>'workflow_version')='' OR btrim(p_run->>'prompt_version')=''
    OR btrim(p_run->>'schema_version')='' OR btrim(p_run->>'validator_version')=''
    OR jsonb_typeof(p_run->'retrieval_log') IS DISTINCT FROM 'array'
    OR jsonb_typeof(p_run->'cited_ids') IS DISTINCT FROM 'array'
    OR jsonb_typeof(p_run->'evidence') IS DISTINCT FROM 'array'
    OR jsonb_typeof(p_run->'conflicts') IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION 'UC2_INVALID_LOG_FIELDS'; END IF;
  -- Immutable audit: replay of the same payload is idempotent, altered replay fails.
  PERFORM pg_advisory_xact_lock(hashtextextended('uc2-log:'||(p_run->>'run_id'),0));
  SELECT payload INTO old_payload FROM public.uc2_query_runs WHERE run_id=p_run->>'run_id';
  IF FOUND THEN
    IF old_payload IS DISTINCT FROM p_run THEN RAISE EXCEPTION 'UC2_LOG_CONFLICT'; END IF;
    RETURN jsonb_build_object('status','logged','run_id',p_run->>'run_id','replayed',true);
  END IF;
  INSERT INTO public.uc2_query_runs(run_id,status,question,workflow_version,payload)
  VALUES(p_run->>'run_id',p_run->>'status',p_run->>'question',p_run->>'workflow_version',p_run);
  RETURN jsonb_build_object('status','logged','run_id',p_run->>'run_id','replayed',false);
END;
$$;
REVOKE ALL ON FUNCTION public.uc2_log_run(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.uc2_log_run(jsonb) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
SELECT 'uc2_query_runs' AS tabelle, c.relrowsecurity AS rls_aktiv
FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid
WHERE n.nspname='public' AND c.relname='uc2_query_runs';
