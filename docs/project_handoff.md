# Project Handoff

Last updated: `2026-04-05`

## Current Goal

Build a deployable Hong Kong criminal-law Casemap with:

- a functional graph of principles, concepts, sub-concepts, statutes, and case lineage
- hosted artifacts for the map and monitor views
- paragraph-level embeddings for HKLII-backed cases
- an AI answer layer that can cite exact nodes and exact stored paragraphs

## Current Artifact Status

Local criminal artifacts:

- relationship graph: `artifacts/hk_criminal_relationship`
- hybrid graph: `artifacts/hk_criminal_hybrid`

Current local build counts:

- relationship nodes: `684`
- relationship edges: `1438`
- retained case nodes: `514`
- retained statute nodes: `133`
- embedding records: `674`
- backend: `sentence-transformers/all-MiniLM-L6-v2`

Monitor:

- uncovered topics: `0`
- low-coverage topics: `0`

## Hosted Supabase Status

Connected project:

- `SUPABASE_URL=https://vzqlwjibtujhrhjgwhhe.supabase.co`
- Storage bucket: `Casebase`

Verified live sync command:

```bash
PYTHONPATH=src .venv/bin/python -m casemap sync-criminal-supabase --max-cases 10 --prefix casemap/hk_criminal/latest
```

What the sync currently does:

- uploads manifest, relationship, monitor, embedding, and hybrid artifacts to Storage
- fetches HKLII case documents for selected criminal-case nodes
- stores per-case JSON under `Casebase/casemap/hk_criminal/latest/cases/...`
- upserts `cases`
- replaces `case_chunks` with paragraph-level embeddings

Current hosted `latest` sync includes 10 cases, including:

- `HKSAR v. CHAN KAM SHING` `[2016] HKCFA 87`
- `HKSAR v. SHUM WAI KEE` `[2019] HKCFA 2`
- `HKSAR v. CHAN SUNG WING` `[2007] HKCA 509`
- `LO KWONG YIN v. HKSAR` `[2010] HKCFA 21`
- `HKSAR v. ALI MUMTAZ` `[2022] HKDC 1083`
- `HKSAR v. GAMMON CONSTRUCTION LTD` `[2021] HKCA 185`

## Important Selection Rule

The hosted sync should use a relevance filter, not a prosecutions-only filter.

Keep:

- primary criminal prosecutions and appeals
- non-criminal authorities that genuinely support criminal-law issues such as evidence, hearsay, burden/standard, procedure, abuse of process, disclosure, sentencing, or statutory interpretation

Exclude:

- generic cited-authority nodes with no clear criminal-law linkage

## DeepSeek / HKLII Cross-Check Notes

Useful verified authorities surfaced during cross-checking include:

- `HKSAR v. ALI MUMTAZ` `[2022] HKDC 1083`
- `HKSAR v. SHUM WAI KEE` `[2019] HKCFA 2`
- `HKSAR v. KANJANAPAS CHONG KWONG DEREK AND OTHERS` `[2009] HKCA 46`
- `PO KOON TAI AND OTHERS v. THE QUEEN` `[1980] HKCA 214`
- `HKSAR v. CHAN KAM SHING` `[2016] HKCFA 87`
- `SZE KWAN LUNG AND OTHERS v. HKSAR` `[2004] HKCFA 85`
- `HKSAR v. CHAN SUNG WING` `[2007] HKCA 509`
- `LO KWONG YIN v. HKSAR` `[2010] HKCFA 21`
- `SIN KAM WAH LAM CHUEN IP AND ANOTHER v. HKSAR` `[2005] HKCFA 29`
- `HKSAR v. ARTHUR JOHN PAYMER AND ANOTHER` `[2004] HKCA 39`

Still uncertain / requires direct verification before promotion:

- `Wong Sau-chuen`
- `Kwan Hin Kee`
- `Chan Wing Hung`
- `Chui Yun Woo`

## Main Commands

Tests:

```bash
PYTHONPATH=src .venv/bin/python -m unittest tests.test_supabase_sync tests.test_criminal_graph tests.test_embeddings tests.test_app_routes tests.test_hybrid_graph tests.test_paragraph_index
```

Build artifacts:

```bash
PYTHONPATH=src .venv/bin/python -m casemap build-criminal-graph --output-dir artifacts/hk_criminal_relationship --hybrid-output-dir artifacts/hk_criminal_hybrid --embedding-backend sentence-transformers
```

Generic domain graph build:

```bash
PYTHONPATH=src .venv/bin/python -m casemap build-domain-graph --domain family --tree data/batch/domain_trees/family_tree.json --output-dir artifacts/hk_family_relationship --hybrid-output-dir artifacts/hk_family_hybrid --embedding-backend sentence-transformers
```

Sync hosted subset:

```bash
PYTHONPATH=src .venv/bin/python -m casemap sync-criminal-supabase --max-cases 10 --prefix casemap/hk_criminal/latest
```

Resume paragraph-level HKLII indexing:

```bash
PYTHONPATH=src .venv/bin/python -m casemap build-paragraph-index --graph artifacts/hk_criminal_relationship/relationship_graph.json --output-dir artifacts/hk_case_paragraph_index --max-cases 50 --embedding-backend sentence-transformers
```

Search exact paragraphs:

```bash
PYTHONPATH=src .venv/bin/python -m casemap paragraph-query --index artifacts/hk_case_paragraph_index/paragraph_chroma_records.json --question "mens rea for assault in Hong Kong" --top-k 8 --embedding-backend sentence-transformers
```

## Next Priorities

1. Refine the relevance filter so evidential/procedural authorities are included when genuinely linked to criminal topics.
2. Increase hosted sync coverage from 10 to a larger reviewed subset.
3. Wire the app query path to Supabase-backed `case_chunks` retrieval.
4. Add answer formatting that cites exact nodes plus exact paragraph snippets.
5. Prepare GitHub push and Vercel deployment cleanup.
