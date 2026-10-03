-- UC2 Etappe 1: nur lesende Suche, 02.10.2026.
-- Voraussetzung: SQL 001/002. Keine bestehenden Dokumente werden geaendert.
BEGIN;
CREATE OR REPLACE FUNCTION public.uc2_search(
  p_query_embedding extensions.vector,
  p_repository text, p_branch text, p_paths text[],
  p_embedding_model text, p_index_config_version text,
  p_match_count integer DEFAULT 12, p_min_similarity double precision DEFAULT 0.20
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY INVOKER
SET search_path = pg_catalog, extensions
AS $$
DECLARE result jsonb;
BEGIN
  IF p_query_embedding IS NULL OR extensions.vector_dims(p_query_embedding) <> 1536
     OR extensions.vector_norm(p_query_embedding) = 0 THEN
    RAISE EXCEPTION 'UC2_INVALID_QUERY_VECTOR';
  END IF;
  IF p_repository IS NULL OR btrim(p_repository) = ''
     OR p_branch IS NULL OR btrim(p_branch) = ''
     OR p_paths IS NULL OR cardinality(p_paths) NOT BETWEEN 1 AND 100
     OR array_position(p_paths, NULL) IS NOT NULL
     OR p_embedding_model IS DISTINCT FROM 'text-embedding-3-small'
     OR p_index_config_version IS NULL OR btrim(p_index_config_version) = ''
     OR p_match_count IS NULL OR p_match_count NOT BETWEEN 1 AND 20
     OR p_min_similarity IS NULL OR NOT (p_min_similarity BETWEEN -1 AND 1) THEN
    RAISE EXCEPTION 'UC2_INVALID_SEARCH_PARAMETERS';
  END IF;
  WITH scoped AS (
    SELECT d.* FROM public.uc2_documents d
    WHERE d.repository = p_repository AND d.branch = p_branch
      AND d.file_path = ANY(p_paths)
      AND d.embedding_model = p_embedding_model AND d.embedding_dimensions = 1536
      AND d.index_config_version = p_index_config_version
  ), ranked AS (
    SELECT c.chunk_id, c.chunk_index, c.section, c.content,
      d.document_code, d.title, d.document_version, d.document_date,
      d.file_path, d.repository, d.branch, d.source_commit_sha,
      1 - (c.embedding OPERATOR(extensions.<=>) p_query_embedding) AS similarity
    FROM scoped d JOIN public.uc2_chunks c ON c.document_id = d.document_id
  ), selected AS (
    SELECT * FROM ranked WHERE similarity >= p_min_similarity
    ORDER BY similarity DESC, document_code, chunk_index LIMIT p_match_count
  )
  SELECT jsonb_build_object(
    'document_count', (SELECT count(*) FROM scoped),
    'chunk_count', (SELECT count(*) FROM ranked),
    'matches', COALESCE((SELECT jsonb_agg(to_jsonb(s)
      ORDER BY s.similarity DESC, s.document_code, s.chunk_index) FROM selected s), '[]'::jsonb)
  ) INTO result;
  RETURN result;
END;
$$;
REVOKE ALL ON FUNCTION public.uc2_search(extensions.vector,text,text,text[],text,text,integer,double precision)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.uc2_search(extensions.vector,text,text,text[],text,text,integer,double precision)
  TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public' AND routine_name = 'uc2_search';
