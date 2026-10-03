-- Optionaler SQL-Selbsttest nach Migration 002. Keine echten API-Aufrufe.
-- Alle Testdaten werden am Ende zurueckgerollt. In separater SQL-Abfrage ausfuehren.
BEGIN;
DO $$
DECLARE
  d jsonb;
  chunks jsonb;
  vec jsonb;
  result jsonb;
  old_time text;
  test_path text := 'selftest/' || gen_random_uuid()::text || '.md';
  rejected boolean;
BEGIN
  SELECT jsonb_agg(CASE WHEN i = 1 THEN 1.0 ELSE 0.0 END ORDER BY i)
  INTO vec FROM generate_series(1,1536) i;
  d := jsonb_build_object(
    'repository','__uc2_selftest__','branch','test','file_path',test_path,
    'document_code',test_path,'title','Selbsttest','document_version','1.0',
    'document_date','2026-10-01','blob_sha',repeat('a',40),
    'source_commit_sha',repeat('b',40),'embedding_model','text-embedding-3-small',
    'embedding_dimensions',1536,'index_config_version','selftest-v1',
    'expected_indexed_at',NULL);
  chunks := jsonb_build_array(
    jsonb_build_object('chunk_index',0,'section','Test','content','Alter Stand 0','embedding',vec),
    jsonb_build_object('chunk_index',1,'section','Test','content','Alter Stand 1','embedding',vec));

  result := public.uc2_replace_document(d,chunks);
  IF result->>'status' <> 'indexed' OR (result->>'chunk_count')::integer <> 2 THEN
    RAISE EXCEPTION 'TEST FAIL: Erstindexierung';
  END IF;
  result := public.uc2_index_state('__uc2_selftest__','test',ARRAY[test_path]);
  old_time := result->'documents'->0->>'indexed_at';
  IF old_time IS NULL OR (result->'documents'->0->>'chunk_count')::integer <> 2 THEN
    RAISE EXCEPTION 'TEST FAIL: Indexstatus';
  END IF;

  -- Zweiter Chunk ungueltig: erster Insert und vorausgehendes Delete muessen
  -- ebenfalls zurueckgerollt werden. Exception-Block ist eine Subtransaktion.
  rejected := false;
  BEGIN
    PERFORM public.uc2_replace_document(
      d || jsonb_build_object('blob_sha',repeat('c',40),'expected_indexed_at',old_time),
      jsonb_set(chunks,'{1,embedding}','[1,0]'::jsonb));
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE 'UC2_INVALID_VECTOR_DIMENSION_OR_VALUES%' THEN RAISE; END IF;
    rejected := true;
  END;
  IF NOT rejected THEN RAISE EXCEPTION 'TEST FAIL: falsche Dimension akzeptiert'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.uc2_documents
    WHERE repository='__uc2_selftest__' AND file_path=test_path
      AND blob_sha=repeat('a',40) AND indexed_at=old_time::timestamptz) THEN
    RAISE EXCEPTION 'TEST FAIL: alter Dokumentstand verloren';
  END IF;
  IF (SELECT count(*) FROM public.uc2_chunks c JOIN public.uc2_documents doc
      ON doc.document_id=c.document_id WHERE doc.file_path=test_path
      AND c.content IN ('Alter Stand 0','Alter Stand 1')) <> 2 THEN
    RAISE EXCEPTION 'TEST FAIL: alte Chunks verloren';
  END IF;

  rejected := false;
  BEGIN
    PERFORM public.uc2_replace_document(d,chunks);
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE 'UC2_CONCURRENT_CHANGE%' THEN RAISE; END IF;
    rejected := true;
  END;
  IF NOT rejected THEN RAISE EXCEPTION 'TEST FAIL: veralteter Zustand akzeptiert'; END IF;

  result := public.uc2_replace_document(
    d || jsonb_build_object('blob_sha',repeat('c',40),'expected_indexed_at',old_time),chunks);
  IF result->>'blob_sha' <> repeat('c',40) THEN RAISE EXCEPTION 'TEST FAIL: Update'; END IF;
END;
$$;
ROLLBACK;
SELECT 'OK: Erstindexierung, Indexstatus, Fehler-Rollback, Konkurrenzschutz, Update; Testdaten entfernt' AS ergebnis;
