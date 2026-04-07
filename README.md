# Casemap-

Casemap- is a dependency-light MVP for turning Hong Kong contract-law materials into a legal GraphRAG knowledge map. It supports:

- a document-level GraphRAG build from `Contract big .docx`
- a richer multi-source relationship graph that combines `Contract big .docx` with local `.pdf` textbooks
- a hybrid hierarchical graph bundle for case-card APIs, focus-graph queries, and Neo4j export
- a Vercel-ready read-only viewer for the committed sample artifact

## What It Produces

- `graph.json`: knowledge graph nodes and edges
- `chunks.json`: retrieval chunks with lexical and graph metadata
- `manifest.json`: build summary
- `sample_queries.json`: example reranked retrieval output
- `knowledge_map.html`: interactive local viewer
- `hierarchical_graph.json`: internal graph bundle with topic zoom, lineages, and case cards
- `public_projection.json`: public-safe projection without private paragraph text or embeddings

The repository also includes a Vercel-ready `app.py` WSGI entrypoint. When deployed, it serves the knowledge map at `/` and lightweight JSON endpoints such as `/api/manifest`, `/api/sample-queries`, and `/api/query?q=...`.

## Casemap-2 Bootstrap Snapshot

The `Casemap-2` bootstrap snapshot intentionally includes:

- the current criminal-law pipeline code
- local criminal-law generated artifacts under `artifacts/hk_criminal_relationship/` and `artifacts/hk_criminal_hybrid/`
- cached HKLII search/judgment responses under `data/cache/hklii/`

It still excludes live secrets and machine-local credentials:

- `.env`
- `.env.local`
- any service-role or other runtime keys

For hosted refreshes, the current starting command remains:

```bash
PYTHONPATH=src .venv/bin/python -m casemap sync-criminal-supabase --max-cases 10 --prefix casemap/hk_criminal/latest
```

For future low-burn continuation, start with:

- [docs/project_handoff.md](/Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-/docs/project_handoff.md)
- [docs/codex_workflow.md](/Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-/docs/codex_workflow.md)

## Quick Start

```bash
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-
PYTHONPATH=src python3 -m casemap build \
  --input "/Users/puiyuenwong/Desktop/桌面 - Pui的MacBook Air/Real uni (1)/PCLL 2023 /Haldanes demo try /Album /Contract big .docx" \
  --output-dir artifacts/contract_big
```

Open `artifacts/contract_big/knowledge_map.html` in a browser.

Run a reranked query:

```bash
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-
PYTHONPATH=src python3 -m casemap query \
  --graph artifacts/contract_big/graph.json \
  --chunks artifacts/contract_big/chunks.json \
  --question "When can a third party enforce a contract term?" \
  --top-k 5
```

Build the richer relationship graph from a taxonomy docx plus supporting books:

```bash
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-
PYTHONPATH=src .venv/bin/python -m casemap build-relationships \
  --taxonomy "/absolute/path/to/Contract big .docx" \
  --source "/absolute/path/to/Butterworths Hong Kong Contract Law Handbook.pdf" \
  --source "/absolute/path/to/Contract Law in Hong Kong.pdf" \
  --source "/absolute/path/to/Ho  Halls Hong Kong Contract Law.pdf" \
  --output-dir artifacts/hk_contract_relationship
```

Open `artifacts/hk_contract_relationship/relationship_map.html` in a browser.

Create a public-safe deployment artifact from that richer local graph:

```bash
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-
PYTHONPATH=src .venv/bin/python -m casemap export-public-relationships \
  --graph artifacts/hk_contract_relationship/relationship_graph.json \
  --output-dir artifacts/public_relationship_graph \
  --title "Hong Kong Contract Law Public Structure"
```

This produces:

- `relationship_map.html`: graph view
- `relationship_tree.html`: hierarchical tree view
- `relationship_graph.json`: public-safe graph payload with bibliographic references only

Build the hybrid hierarchical graph bundle from the relationship graph:

```bash
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-
PYTHONPATH=src python3 -m casemap build-hybrid-graph \
  --graph artifacts/public_relationship_graph/relationship_graph.json \
  --output-dir artifacts/hybrid_graph
```

This produces:

- `hierarchical_graph.json`: internal graph bundle with `Module`, `Subground`, `Topic`, `AuthorityLineage`, `Case`, `Statute`, `Paragraph`, `Proposition`, `Judge`, and `SourceDocument` nodes
- `public_projection.json`: public-safe graph projection
- `neo4j_constraints.cypher`: constraints, indexes, and vector indexes for Neo4j 5.x
- `neo4j_import.cypher`: import template for loading the bundle into Neo4j

Run a hybrid graph query:

```bash
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-
PYTHONPATH=src python3 -m casemap hybrid-query \
  --graph artifacts/hybrid_graph/hierarchical_graph.json \
  --question "When can terms be implied into a contract in Hong Kong?"
```

Serve the internal API-driven explorer:

```bash
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-
PYTHONPATH=src python3 -m casemap serve-internal --host 127.0.0.1 --port 8052
```

Internal routes:

- `GET /api/manifest`
- `GET /api/tree`
- `GET /api/topic/{topic_id}`
- `GET /api/case/{case_id}`
- `GET /api/graph/focus?id={node_id}&depth=1`
- `POST /api/query` (supports `question`, `top_k`, `max_citations`, `mode`, `model`)

GraphRAG query modes:

- `mode=extractive` returns citation-first answers directly from case/principle evidence.
- `mode=openrouter` attempts grounded synthesis through OpenRouter and falls back to extractive mode when unavailable.

Optional OpenRouter environment variables:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (defaults to `openrouter/auto`)

## Supabase Runtime Split

The repo now includes an env template at [.env.example](/Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-/.env.example).

Use the variables in two layers:

- Public runtime variables for the deployed app:
  - `CASEMAP_PROFILE=criminal`
  - `SUPABASE_URL=https://vzqlwjibtujhrhjgwhhe.supabase.co`
  - `SUPABASE_PUBLISHABLE_KEY=...`
- Server-only ingest variables for bulk uploads, admin imports, and future pipeline writes:
  - `SUPABASE_SERVICE_ROLE_KEY=...`

Important:

- The publishable key is suitable for browser/client access when protected by RLS.
- Do not put the service-role key into client-side code or public Vercel env exposed to the browser.
- Until a service-role key is added, the current repo is still operating in local-export mode for `supabase_export.sql` and related artifacts rather than live Supabase ingestion.

Suggested Vercel env setup:

```bash
CASEMAP_PROFILE=criminal
SUPABASE_URL=https://vzqlwjibtujhrhjgwhhe.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_jbTqB00EEbq-1ukymq5MMA_4Wa6ANpj
```

Keep this unset until you deliberately enable server-side ingest:

```bash
SUPABASE_SERVICE_ROLE_KEY=
```

Hosted criminal-law sync:

```bash
PYTHONPATH=src .venv/bin/python -m casemap sync-criminal-supabase --max-cases 10 --prefix casemap/hk_criminal/latest
```

To keep future Codex sessions cheaper and more accurate, start from:

- [docs/project_handoff.md](/Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-/docs/project_handoff.md)
- [docs/codex_workflow.md](/Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-/docs/codex_workflow.md)

## Design

The project stays light on dependencies:

- `.docx` parsing uses the Office XML inside the archive
- `.pdf` parsing uses `pypdf`
- graph building uses heuristics over headings, concept labels, statutes, and case references
- retrieval uses a TF-IDF style lexical score
- reranking boosts graph neighbors, cited authorities, and structurally central nodes
- the relationship graph attaches source passages, page references, and HKLII-oriented external links
- the hybrid graph bundle converts the public graph into explicit `Module -> Subground -> Topic` hierarchy plus typed authority relationships
- the internal API serves bounded focus graphs instead of shipping the full corpus to the browser
- the public export strips third-party snippets and keeps only structure, bibliographic references, and public-facing links
- both viewers are static HTML files with inline data and client-side interactions

## Vercel Deployment

Vercel's Python runtime requires a top-level ASGI or WSGI application named `app` in files such as `app.py`. This repo ships a root `app.py` that:

- serves the built map at `/`
- exposes `GET /api/manifest`
- exposes `GET /api/sample-queries`
- exposes `GET /api/query?q=third+party+rights&top_k=5`

The committed sample artifacts under `artifacts/contract_big/` let Vercel serve the MVP without access to the original `.docx` file.
The committed public artifact under `artifacts/public_relationship_graph/` lets Vercel serve the richer tree and graph views without exposing textbook passages.

## Local-Only Sources

If you enrich the graph with third-party textbooks or other licensed material, keep the generated artifacts local unless you have clear rights to publish them. The repository is set up so the committed public artifact remains the `Contract big` sample, while book-derived outputs can stay untracked under `artifacts/`.

## Project Layout

```text
Casemap-/
  app.py
  internal_app.py
  src/casemap/
    __init__.py
    __main__.py
    case_enrichment_data.py
    docx_parser.py
    graphrag.py
    hybrid_graph.py
    internal_viewer.py
    relationship_graph.py
    source_parser.py
    viewer.py
  artifacts/
  pyproject.toml
  README.md
```

## Next Step Ideas

- Replace heuristic extraction with LLM-assisted triplet/entity extraction
- Persist the graph in Neo4j, Oracle Database, or another graph-capable backend
- Add embeddings and a cross-encoder reranker
- Layer in answer generation once your cloud backend is ready
- Swap the bundle-backed internal API for a live Neo4j-backed runtime when infrastructure is available
