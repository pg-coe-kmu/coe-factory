-- UC2: Zustandsabfrage und atomarer Dokumentaustausch.
-- Voraussetzung: 001 bereits ausgefuehrt. Keine vorhandenen Daten loeschen.
BEGIN;

CREATE OR REPLACE FUNCTION public.uc2_index_state(
  p_repository text, p_branch text, p_paths text[]
) RETURNS jsonb
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = pg_catalog
AS $$
  SELECT jsonb_build_object('documents', COALESCE(jsonb_agg(
    jsonb_build_object(
      'file_path', d.file_path, 'document_code', d.document_code,
      'blob_sha', d.blob_sha, 'embedding_model', d.embedding_model,
      'embedding_dimensions', d.embedding_dimensions,
      'index_config_version', d.index_config_version,
      'indexed_at', d.indexed_at,
      'chunk_count', (SELECT count(*) FROM public.uc2_chunks c
                      WHERE c.document_id = d.document_id)
    ) ORDER BY d.file_path
  ), '[]'::jsonb))
  FROM public.uc2_documents d
  WHERE d.repository = p_repository AND d.branch = p_branch
    AND d.file_path = ANY(p_paths);
$$;

CREATE OR REPLACE FUNCTION public.uc2_replace_document(
  p_document jsonb, p_chunks jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, extensions
AS $$
DECLARE
  v_old public.uc2_documents%ROWTYPE;
  v_id uuid;
  v_chunk jsonb;
  v_count integer;
  v_index integer := 0;
  v_vector extensions.vector(1536);
  v_model text := 'text-embedding-3-small';
  v_field text;
BEGIN
  IF jsonb_typeof(p_document) IS DISTINCT FROM 'object'
     OR jsonb_typeof(p_chunks) IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION 'UC2_INVALID_PAYLOAD: object and chunk array required';
  END IF;
  FOREACH v_field IN ARRAY ARRAY['repository','branch','file_path','document_code',
      'title','document_version','document_date','blob_sha','source_commit_sha',
      'embedding_model','index_config_version'] LOOP
    IF jsonb_typeof(p_document->v_field) IS DISTINCT FROM 'string'
       OR btrim(p_document->>v_field) = '' THEN
      RAISE EXCEPTION 'UC2_INVALID_METADATA: %', v_field;
    END IF;
  END LOOP;
  IF NOT (p_document ? 'expected_indexed_at') THEN
    RAISE EXCEPTION 'UC2_MISSING_EXPECTED_STATE';
  END IF;
  IF p_document->>'embedding_model' IS DISTINCT FROM v_model
     OR (p_document->>'embedding_dimensions')::integer IS DISTINCT FROM 1536 THEN
    RAISE EXCEPTION 'UC2_MODEL_MISMATCH';
  END IF;
  v_count := jsonb_array_length(p_chunks);
  IF v_count < 1 OR v_count > 100 THEN
    RAISE EXCEPTION 'UC2_INVALID_CHUNK_COUNT';
  END IF;

  -- Serialisiert konkurrierende Ersetzungen desselben Dokumentpfads.
  PERFORM pg_advisory_xact_lock(hashtextextended(
    jsonb_build_array(p_document->>'repository', p_document->>'branch',
                     p_document->>'file_path')::text, 0));
  SELECT * INTO v_old FROM public.uc2_documents
  WHERE repository = p_document->>'repository'
    AND branch = p_document->>'branch'
    AND file_path = p_document->>'file_path'
  FOR UPDATE;

  IF FOUND THEN
    IF v_old.indexed_at IS DISTINCT FROM
       (p_document->>'expected_indexed_at')::timestamptz THEN
      RAISE EXCEPTION 'UC2_CONCURRENT_CHANGE: restart complete workflow';
    END IF;
    v_id := v_old.document_id;
  ELSE
    IF p_document->>'expected_indexed_at' IS NOT NULL THEN
      RAISE EXCEPTION 'UC2_CONCURRENT_DELETE: restart complete workflow';
    END IF;
    v_id := gen_random_uuid();
  END IF;

  -- Die gesamte Funktion ist eine Transaktion: auch spaetere Fehler rollen
  -- Dokumentaenderung und Chunk-Austausch vollstaendig zurueck.
  INSERT INTO public.uc2_documents (
    document_id, document_code, repository, branch, file_path, title,
    document_version, document_date, blob_sha, source_commit_sha,
    embedding_model, embedding_dimensions, index_config_version, indexed_at
  ) VALUES (
    v_id, p_document->>'document_code', p_document->>'repository',
    p_document->>'branch', p_document->>'file_path', p_document->>'title',
    p_document->>'document_version', (p_document->>'document_date')::date,
    p_document->>'blob_sha', p_document->>'source_commit_sha',
    v_model, 1536, p_document->>'index_config_version', clock_timestamp()
  ) ON CONFLICT (document_id) DO UPDATE SET
    document_code = EXCLUDED.document_code, title = EXCLUDED.title,
    document_version = EXCLUDED.document_version,
    document_date = EXCLUDED.document_date, blob_sha = EXCLUDED.blob_sha,
    source_commit_sha = EXCLUDED.source_commit_sha,
    embedding_model = EXCLUDED.embedding_model,
    embedding_dimensions = EXCLUDED.embedding_dimensions,
    index_config_version = EXCLUDED.index_config_version,
    indexed_at = EXCLUDED.indexed_at;

  DELETE FROM public.uc2_chunks WHERE document_id = v_id;
  FOR v_chunk IN SELECT value FROM jsonb_array_elements(p_chunks) LOOP
    IF jsonb_typeof(v_chunk) IS DISTINCT FROM 'object'
       OR jsonb_typeof(v_chunk->'chunk_index') IS DISTINCT FROM 'number'
       OR (v_chunk->>'chunk_index')::numeric IS DISTINCT FROM v_index::numeric
       OR jsonb_typeof(v_chunk->'content') IS DISTINCT FROM 'string'
       OR jsonb_typeof(v_chunk->'section') IS DISTINCT FROM 'string' THEN
      RAISE EXCEPTION 'UC2_INVALID_CHUNK: %', v_index;
    END IF;
    IF jsonb_typeof(v_chunk->'embedding') IS DISTINCT FROM 'array' THEN
      RAISE EXCEPTION 'UC2_INVALID_VECTOR';
    END IF;
    IF jsonb_array_length(v_chunk->'embedding') <> 1536
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(v_chunk->'embedding') x
                  WHERE jsonb_typeof(x.value) <> 'number') THEN
      RAISE EXCEPTION 'UC2_INVALID_VECTOR_DIMENSION_OR_VALUES';
    END IF;
    v_vector := (v_chunk->'embedding')::text::extensions.vector(1536);
    IF extensions.vector_norm(v_vector) = 0 THEN
      RAISE EXCEPTION 'UC2_ZERO_VECTOR';
    END IF;
    INSERT INTO public.uc2_chunks(document_id, chunk_index, section, content, embedding)
    VALUES (v_id, v_index, v_chunk->>'section', v_chunk->>'content', v_vector);
    v_index := v_index + 1;
  END LOOP;

  RETURN jsonb_build_object('status', 'indexed', 'document_id', v_id,
    'document_code', p_document->>'document_code',
    'file_path', p_document->>'file_path', 'chunk_count', v_count,
    'blob_sha', p_document->>'blob_sha',
    'source_commit_sha', p_document->>'source_commit_sha');
END;
$$;

REVOKE ALL ON FUNCTION public.uc2_index_state(text,text,text[]) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.uc2_replace_document(jsonb,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.uc2_index_state(text,text,text[]) TO service_role;
GRANT EXECUTE ON FUNCTION public.uc2_replace_document(jsonb,jsonb) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;

SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN ('uc2_index_state','uc2_replace_document')
ORDER BY routine_name;
