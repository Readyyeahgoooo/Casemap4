-- Casemap: scale-ready case_chunks retrieval (pgvector + FTS + RPC)
--
-- Apply in Supabase SQL editor or via Supabase CLI migrations.
-- Embedding dimension 384 = sentence-transformers/all-MiniLM-L6-v2.
--
-- After apply:
--   1. Re-run ingestion (sync-candidates-supabase / sync-criminal-supabase).
--   2. If GRANT below fails, run: grant execute on function public.match_case_chunks to anon, authenticated, service_role;
--   3. Runtime app: SUPABASE_URL + SUPABASE_PUBLISHABLE_KEY only (no service role in browser).

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE public.case_chunks
  ADD COLUMN IF NOT EXISTS legal_domain text,
  ADD COLUMN IF NOT EXISTS offence_family text,
  ADD COLUMN IF NOT EXISTS topic_label text,
  ADD COLUMN IF NOT EXISTS classification_area text;

ALTER TABLE public.case_chunks
  ADD COLUMN IF NOT EXISTS embedding_vec vector(384);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'case_chunks' AND column_name = 'chunk_tsvector'
  ) THEN
    ALTER TABLE public.case_chunks
      ADD COLUMN chunk_tsvector tsvector
      GENERATED ALWAYS AS (
        to_tsvector(
          'english',
          coalesce(chunk_text, '') || ' ' ||
          coalesce(case_name, '') || ' ' ||
          coalesce(neutral_citation, '') || ' ' ||
          coalesce(legal_principles::text, '')
        )
      ) STORED;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS case_chunks_hklii_id_idx ON public.case_chunks (hklii_id);
CREATE INDEX IF NOT EXISTS case_chunks_case_id_idx ON public.case_chunks (case_id);
CREATE INDEX IF NOT EXISTS case_chunks_legal_domain_idx ON public.case_chunks (legal_domain);
CREATE INDEX IF NOT EXISTS case_chunks_offence_family_idx ON public.case_chunks (offence_family);
CREATE INDEX IF NOT EXISTS case_chunks_topic_label_idx ON public.case_chunks (topic_label);
CREATE INDEX IF NOT EXISTS case_chunks_decision_date_idx ON public.case_chunks (decision_date);

CREATE INDEX IF NOT EXISTS case_chunks_chunk_tsvector_idx
  ON public.case_chunks USING gin (chunk_tsvector);

CREATE INDEX IF NOT EXISTS case_chunks_embedding_vec_hnsw_idx
  ON public.case_chunks USING hnsw (embedding_vec vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE OR REPLACE FUNCTION public.match_case_chunks(
  query_text text,
  query_embedding vector(384),
  p_legal_domain text DEFAULT NULL,
  p_offence_family text DEFAULT NULL,
  p_topic_label text DEFAULT NULL,
  p_classification_area text DEFAULT NULL,
  match_count int DEFAULT 24,
  fts_weight double precision DEFAULT 0.35,
  vec_weight double precision DEFAULT 0.65
)
RETURNS TABLE (
  id bigint,
  case_id bigint,
  hklii_id text,
  chunk_index integer,
  chunk_text text,
  case_name text,
  neutral_citation text,
  court text,
  decision_date timestamptz,
  legal_principles jsonb,
  fts_rank double precision,
  vec_score double precision,
  combined_score double precision
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH cand AS (
    SELECT
      c.id,
      c.case_id,
      c.hklii_id,
      c.chunk_index,
      c.chunk_text,
      c.case_name,
      c.neutral_citation,
      c.court,
      c.decision_date,
      c.legal_principles,
      c.chunk_tsvector,
      c.embedding_vec,
      ts_rank_cd(c.chunk_tsvector, plainto_tsquery('english', query_text)) AS fts_raw,
      CASE
        WHEN query_embedding IS NULL OR c.embedding_vec IS NULL THEN NULL::double precision
        ELSE (1.0::double precision - (c.embedding_vec <=> query_embedding)::double precision)
      END AS vscore
    FROM public.case_chunks c
    WHERE
      (p_legal_domain IS NULL OR c.legal_domain IS NOT DISTINCT FROM p_legal_domain)
      AND (p_offence_family IS NULL OR c.offence_family IS NOT DISTINCT FROM p_offence_family)
      AND (p_topic_label IS NULL OR c.topic_label ILIKE ('%' || p_topic_label || '%'))
      AND (
        p_classification_area IS NULL
        OR c.classification_area IS NULL
        OR c.classification_area = p_classification_area
      )
  ),
  scored AS (
    SELECT
      cand.*,
      COALESCE(cand.fts_raw, 0.0)::double precision AS fts_rank,
      COALESCE(cand.vscore, 0.0)::double precision AS vec_score,
      CASE
        WHEN query_embedding IS NULL OR cand.embedding_vec IS NULL THEN
          fts_weight * COALESCE(cand.fts_raw, 0.0)::double precision
        ELSE
          vec_weight * COALESCE(cand.vscore, 0.0)::double precision
          + fts_weight * COALESCE(cand.fts_raw, 0.0)::double precision
      END AS combined_score
    FROM cand
  )
  SELECT
    s.id,
    s.case_id,
    s.hklii_id,
    s.chunk_index,
    s.chunk_text,
    s.case_name,
    s.neutral_citation,
    s.court,
    s.decision_date,
    s.legal_principles,
    s.fts_rank,
    s.vec_score,
    s.combined_score
  FROM scored s
  WHERE (s.chunk_tsvector @@ plainto_tsquery('english', query_text))
     OR (query_embedding IS NOT NULL AND s.embedding_vec IS NOT NULL)
  ORDER BY s.combined_score DESC NULLS LAST, s.id ASC
  LIMIT greatest(match_count, 1);
$$;

-- Grant RPC to roles your API uses (adjust if you use custom roles):
--   GRANT EXECUTE ON FUNCTION public.match_case_chunks TO anon, authenticated, service_role;
