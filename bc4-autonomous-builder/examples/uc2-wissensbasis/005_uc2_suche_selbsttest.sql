-- Synthetische Vektoren, keine API-Kosten; alle Testdaten werden zurueckgerollt.
BEGIN;
DO $$
DECLARE
  repo text := '__uc2_search_test_' || gen_random_uuid()::text;
  a uuid; b uuid; v extensions.vector; w extensions.vector;
  r jsonb; rejected boolean := false;
BEGIN
  SELECT array_agg(CASE WHEN i=1 THEN 1::real ELSE 0::real END ORDER BY i)::extensions.vector
    INTO v FROM generate_series(1,1536) i;
  SELECT array_agg(CASE WHEN i=2 THEN 1::real ELSE 0::real END ORDER BY i)::extensions.vector
    INTO w FROM generate_series(1,1536) i;
  INSERT INTO public.uc2_documents(document_code,repository,branch,file_path,title,document_version,
    document_date,blob_sha,source_commit_sha,index_config_version)
  VALUES('TEST-A',repo,'test','a.md','Test A','1.0','2026-10-02',repeat('a',40),repeat('b',40),'test-v1')
  RETURNING document_id INTO a;
  INSERT INTO public.uc2_documents(document_code,repository,branch,file_path,title,document_version,
    document_date,blob_sha,source_commit_sha,index_config_version)
  VALUES('TEST-B',repo,'test','b.md','Test B','1.0','2026-10-02',repeat('a',40),repeat('b',40),'test-v1')
  RETURNING document_id INTO b;
  INSERT INTO public.uc2_chunks(document_id,chunk_index,section,content,embedding)
    VALUES(a,0,'A','Testinhalt A',v),(a,1,'A2','Testinhalt A2',w),(b,0,'B','Testinhalt B',v);
  r := public.uc2_search(v,repo,'test',ARRAY['a.md'],'text-embedding-3-small','test-v1',12,0.5);
  IF (r->>'document_count')::int <> 1 OR (r->>'chunk_count')::int <> 2
     OR jsonb_array_length(r->'matches') <> 1 OR r#>>'{matches,0,document_code}' <> 'TEST-A'
     OR (r#>>'{matches,0,similarity}')::float < 0.999 THEN
    RAISE EXCEPTION 'TEST FAIL: ranking, threshold or path scope';
  END IF;
  r := public.uc2_search(v,repo,'other',ARRAY['a.md'],'text-embedding-3-small','test-v1',12,0);
  IF r->'matches' <> '[]'::jsonb OR (r->>'document_count')::int <> 0 THEN
    RAISE EXCEPTION 'TEST FAIL: branch isolation'; END IF;
  r := public.uc2_search(v,repo||'other','test',ARRAY['a.md'],'text-embedding-3-small','test-v1',12,0);
  IF (r->>'document_count')::int <> 0 THEN RAISE EXCEPTION 'TEST FAIL: repository isolation'; END IF;
  r := public.uc2_search(v,repo,'test',ARRAY['a.md'],'text-embedding-3-small','other-config',12,0);
  IF (r->>'document_count')::int <> 0 THEN RAISE EXCEPTION 'TEST FAIL: config isolation'; END IF;
  BEGIN
    PERFORM public.uc2_search('[1,0]'::extensions.vector,repo,'test',ARRAY['a.md'],
      'text-embedding-3-small','test-v1',12,0);
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE 'UC2_INVALID_QUERY_VECTOR%' THEN RAISE; END IF;
    rejected := true;
  END;
  IF NOT rejected THEN RAISE EXCEPTION 'TEST FAIL: wrong dimensions accepted'; END IF;
  IF has_function_privilege('anon','public.uc2_search(extensions.vector,text,text,text[],text,text,integer,double precision)','EXECUTE')
     OR has_function_privilege('authenticated','public.uc2_search(extensions.vector,text,text,text[],text,text,integer,double precision)','EXECUTE')
     OR NOT has_function_privilege('service_role','public.uc2_search(extensions.vector,text,text,text[],text,text,integer,double precision)','EXECUTE') THEN
    RAISE EXCEPTION 'TEST FAIL: function permissions';
  END IF;
END;
$$;
ROLLBACK;
SELECT 'OK: Suche, Ranking, Schwelle, Bereichsfilter, Dimensionen, Funktionsrechte; Testdaten entfernt' AS ergebnis;
