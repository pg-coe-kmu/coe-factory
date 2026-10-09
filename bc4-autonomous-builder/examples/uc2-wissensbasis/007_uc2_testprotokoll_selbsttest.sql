BEGIN;
DO $$
DECLARE r jsonb; p jsonb; id text := 'selftest-'||gen_random_uuid()::text; rejected boolean:=false;
BEGIN
  p:=jsonb_build_object('run_id',id,'status','abstained_model','question','Selbsttest',
    'workflow_version','test','prompt_version','test','schema_version','test','validator_version','test',
    'started_at','2026-10-02T12:00:00Z','finished_at','2026-10-02T12:00:01Z','output','Keine Belege',
    'retrieval_log','[]'::jsonb,'cited_ids','[]'::jsonb,'evidence','[]'::jsonb,'conflicts','[]'::jsonb);
  r:=public.uc2_log_run(p);
  IF r->>'status'<>'logged' OR r->>'run_id'<>id THEN RAISE EXCEPTION 'TEST FAIL: logging'; END IF;
  r:=public.uc2_log_run(p);
  IF r->>'replayed'<>'true' OR (SELECT count(*) FROM public.uc2_query_runs WHERE run_id=id)<>1 THEN
    RAISE EXCEPTION 'TEST FAIL: idempotence'; END IF;
  BEGIN
    PERFORM public.uc2_log_run(p||jsonb_build_object('output','changed'));
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE 'UC2_LOG_CONFLICT%' THEN RAISE; END IF;
    rejected:=true;
  END;
  IF NOT rejected THEN RAISE EXCEPTION 'TEST FAIL: conflicting replay'; END IF;
  IF has_table_privilege('anon','public.uc2_query_runs','SELECT')
    OR has_function_privilege('authenticated','public.uc2_log_run(jsonb)','EXECUTE')
    OR NOT has_function_privilege('service_role','public.uc2_log_run(jsonb)','EXECUTE') THEN
    RAISE EXCEPTION 'TEST FAIL: permissions'; END IF;
END;
$$;
ROLLBACK;
SELECT 'OK: Testprotokoll, Wiederholung, Konfliktschutz und Rechte; Testdaten entfernt' AS ergebnis;
