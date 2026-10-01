-- UC2 Basis, Version 1, 01.10.2026
-- Voraussetzung: vector ist im Schema extensions installiert.
-- Startkonfiguration: text-embedding-3-small, 1536 Dimensionen.
-- Einmalig als Projektadministrator im Supabase SQL Editor ausfuehren.
-- Noch keine Suchfunktion, Austauschfunktion oder Protokolltabellen.
BEGIN;

CREATE TABLE public.uc2_documents (
  document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_code text NOT NULL CHECK (btrim(document_code) <> ''),
  repository text NOT NULL CHECK (btrim(repository) <> ''),
  branch text NOT NULL CHECK (btrim(branch) <> ''),
  file_path text NOT NULL CHECK (btrim(file_path) <> ''),
  title text NOT NULL CHECK (btrim(title) <> ''),
  document_version text NOT NULL,
  document_date date NOT NULL,
  blob_sha text NOT NULL CHECK (blob_sha ~ '^[0-9a-f]{40}$'),
  source_commit_sha text NOT NULL
    CHECK (source_commit_sha ~ '^[0-9a-f]{40}$'),
  embedding_model text NOT NULL DEFAULT 'text-embedding-3-small'
    CHECK (embedding_model = 'text-embedding-3-small'),
  embedding_dimensions integer NOT NULL DEFAULT 1536
    CHECK (embedding_dimensions = 1536),
  index_config_version text NOT NULL
    CHECK (btrim(index_config_version) <> ''),
  indexed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (repository, branch, file_path),
  UNIQUE (repository, branch, document_code)
);

CREATE TABLE public.uc2_chunks (
  chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL
    REFERENCES public.uc2_documents(document_id) ON DELETE CASCADE,
  chunk_index integer NOT NULL CHECK (chunk_index >= 0),
  section text NOT NULL CHECK (btrim(section) <> ''),
  content text NOT NULL CHECK (btrim(content) <> ''),
  embedding extensions.vector(1536) NOT NULL,
  UNIQUE (document_id, chunk_index)
);

-- Zugriff erfolgt spaeter serverseitig ueber n8n.
ALTER TABLE public.uc2_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.uc2_chunks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.uc2_documents, public.uc2_chunks
  FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON public.uc2_documents, public.uc2_chunks TO service_role;

COMMIT;

-- Nachweis: zwei Tabellen mit aktivierter Zugriffskontrolle.
SELECT c.relname AS tabelle, c.relrowsecurity AS rls_aktiv
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('uc2_documents', 'uc2_chunks')
  AND c.relkind = 'r'
ORDER BY c.relname;
