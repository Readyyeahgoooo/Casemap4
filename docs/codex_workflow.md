# Codex Workflow For Low-Burn Accuracy

Use this file as the starting brief for new Codex threads so the project does not have to be re-explained each time.

## Recommended Thread Split

- `Thread A`: HKLII crawling, textbook extraction, case-name cleanup
- `Thread B`: criminal-law hierarchy, nodes, edges, monitor report
- `Thread C`: embeddings, Chroma/Supabase sync, retrieval quality
- `Thread D`: app runtime, Vercel deployment, query UX

## Prompt Style

Use bounded requests:

- "Wire Supabase sync for 20 criminal cases and verify counts."
- "Improve criminal-only case selection in the hosted sync."
- "Review monitor gaps and propose only the next 5 missing topics."

Avoid broad prompts like:

- "Finish everything above"
- "Review the whole project and improve it"

## Keep Context In Files

Before starting a fresh thread, point Codex at:

- [project_handoff.md](/Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-/docs/project_handoff.md)
- [README.md](/Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap-/README.md)

That is much cheaper than carrying a long multi-day conversation.

## Default Response Mode

Ask for:

- implementation
- verification
- short summary only

Example:

`Implement the next sync improvement, run tests, and give me a short summary only.`

## Accuracy Guardrails

- Do not accept new criminal authorities into production solely from model suggestion.
- Prefer HKLII, textbook references, or both.
- Keep exact neutral citations and paragraph-level storage.
- Distinguish `primary criminal cases` from `supporting authorities` cited for evidence or procedure.
- Exclude generic cited-authority noise that has no clear criminal-law linkage.

## Bulk Work Strategy

- Use Codex for code changes, verification, and pipeline design.
- Use APIs or scripts for high-volume embedding/crawl work.
- Reuse generated artifacts instead of re-describing them in chat.

## Useful Commands

```bash
PYTHONPATH=src .venv/bin/python -m unittest tests.test_supabase_sync tests.test_criminal_graph tests.test_embeddings tests.test_app_routes tests.test_hybrid_graph tests.test_paragraph_index
PYTHONPATH=src .venv/bin/python -m casemap build-criminal-graph --output-dir artifacts/hk_criminal_relationship --hybrid-output-dir artifacts/hk_criminal_hybrid --embedding-backend sentence-transformers
PYTHONPATH=src .venv/bin/python -m casemap build-domain-graph --domain family --tree data/batch/domain_trees/family_tree.json --output-dir artifacts/hk_family_relationship --hybrid-output-dir artifacts/hk_family_hybrid --embedding-backend sentence-transformers
PYTHONPATH=src .venv/bin/python -m casemap sync-criminal-supabase --max-cases 10 --prefix casemap/hk_criminal/latest
PYTHONPATH=src .venv/bin/python -m casemap build-paragraph-index --graph artifacts/hk_criminal_relationship/relationship_graph.json --output-dir artifacts/hk_case_paragraph_index --max-cases 50 --embedding-backend sentence-transformers
PYTHONPATH=src .venv/bin/python -m casemap paragraph-query --index artifacts/hk_case_paragraph_index/paragraph_chroma_records.json --question "mens rea for assault in Hong Kong" --top-k 8 --embedding-backend sentence-transformers
```
