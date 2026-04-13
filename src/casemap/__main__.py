from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from wsgiref.simple_server import make_server

from .criminal_graph import build_criminal_graph_artifacts
from .domain_graph import build_domain_graph_artifacts
from .graphrag import RerankedRetriever, build_artifacts
from .hybrid_graph import HybridGraphStore, build_hybrid_graph_artifacts, merge_with_previous_artifact, write_hybrid_graph_artifacts
from .lineage_discovery import DISCOVERED_LINEAGES_DEFAULT_PATH, discover_lineages_from_file
from .relationship_graph import build_relationship_artifacts, export_public_relationship_artifacts
from .supabase_sync import load_env_file, sync_criminal_artifacts_to_supabase


def build_command(args: argparse.Namespace) -> int:
    manifest = build_artifacts(docx_path=args.input, output_dir=args.output_dir)
    print(json.dumps(manifest, indent=2))
    return 0


def query_command(args: argparse.Namespace) -> int:
    retriever = RerankedRetriever.from_files(args.graph, args.chunks)
    results = retriever.search(args.question, top_k=args.top_k)
    if args.as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    for result in results:
        print(f"[{result['rank']}] {result['title']} | {result['section']} | score={result['score']}")
        print(result["text"])
        if result["citations"]:
            print("Citations:", "; ".join(result["citations"]))
        if result["graph_neighbors"]:
            print("Graph neighbors:", "; ".join(result["graph_neighbors"]))
        print()
    return 0


def build_relationships_command(args: argparse.Namespace) -> int:
    manifest = build_relationship_artifacts(
        taxonomy_docx_path=args.taxonomy,
        source_paths=args.source,
        output_dir=args.output_dir,
        title=args.title,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def export_public_relationships_command(args: argparse.Namespace) -> int:
    manifest = export_public_relationship_artifacts(
        graph_path=args.graph,
        output_dir=args.output_dir,
        title=args.title,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def build_hybrid_graph_command(args: argparse.Namespace) -> int:
    manifest = build_hybrid_graph_artifacts(
        graph_path=args.graph,
        output_dir=args.output_dir,
        title=args.title,
        embedding_backend=args.embedding_backend,
        embedding_model=args.embedding_model,
        embedding_dimensions=args.embedding_dimensions,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def merge_hybrid_graph_command(args: argparse.Namespace) -> int:
    bundle = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    merged = merge_with_previous_artifact(
        bundle,
        args.previous,
        max_total_nodes=args.max_total_nodes,
    )
    manifest = write_hybrid_graph_artifacts(merged, args.output_dir)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def build_criminal_graph_command(args: argparse.Namespace) -> int:
    for candidate in args.env_file:
        load_env_file(candidate)
    manifest = build_criminal_graph_artifacts(
        source_paths=args.source,
        relationship_output_dir=args.output_dir,
        hybrid_output_dir=args.hybrid_output_dir,
        title=args.title,
        per_query_limit=args.per_query_limit,
        max_cases=args.max_cases,
        max_textbook_case_fetches=args.max_textbook_case_fetches,
        max_enrich=args.max_enrich,
        embedding_backend=args.embedding_backend,
        embedding_model=args.embedding_model,
        embedding_dimensions=args.embedding_dimensions,
        discover_lineages=args.discover_lineages,
        lineages_path=args.lineages_path or None,
        enrichment_cache_path=args.enrichment_cache or None,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def build_domain_graph_command(args: argparse.Namespace) -> int:
    for candidate in args.env_file:
        load_env_file(candidate)
    manifest = build_domain_graph_artifacts(
        domain_id=args.domain,
        tree_path=args.tree,
        candidates_path=args.candidates or None,
        source_paths=args.source,
        relationship_output_dir=args.output_dir,
        hybrid_output_dir=args.hybrid_output_dir,
        title=args.title or None,
        per_query_limit=args.per_query_limit,
        max_cases=args.max_cases,
        max_textbook_case_fetches=args.max_textbook_case_fetches,
        max_enrich=args.max_enrich,
        embedding_backend=args.embedding_backend,
        embedding_model=args.embedding_model,
        embedding_dimensions=args.embedding_dimensions,
        discover_lineages=args.discover_lineages,
        lineages_path=args.lineages_path or None,
        enrichment_cache_path=args.enrichment_cache or None,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def sync_criminal_supabase_command(args: argparse.Namespace) -> int:
    for candidate in args.env_file:
        load_env_file(candidate)
    manifest = sync_criminal_artifacts_to_supabase(
        relationship_graph_path=args.graph,
        relationship_output_dir=args.output_dir,
        hybrid_output_dir=args.hybrid_output_dir or None,
        bucket=args.bucket,
        prefix=args.prefix,
        max_cases=args.max_cases,
        embedding_backend=args.embedding_backend,
        embedding_model=args.embedding_model,
        prune_prefix_cases=args.prune_prefix_cases,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def hybrid_query_command(args: argparse.Namespace) -> int:
    store = HybridGraphStore.from_file(args.graph)
    result = store.query(args.question, top_k=args.top_k)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def discover_lineages_command(args: argparse.Namespace) -> int:
    result = discover_lineages_from_file(
        args.graph,
        domain_id=args.domain,
        output_path=args.output,
        max_topics=args.max_topics,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def serve_internal_command(args: argparse.Namespace) -> int:
    internal_module = importlib.import_module("internal_app")
    app = getattr(internal_module, "app")
    with make_server(args.host, args.port, app) as server:
        print(f"Serving internal Casemap explorer on http://{args.host}:{args.port}")
        server.serve_forever()
    return 0


def parser() -> argparse.ArgumentParser:
    main_parser = argparse.ArgumentParser(description="Casemap MVP GraphRAG pipeline")
    subparsers = main_parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build graph and retrieval artifacts")
    build_parser.add_argument("--input", required=True, help="Path to the source .docx file")
    build_parser.add_argument("--output-dir", required=True, help="Directory for generated artifacts")
    build_parser.set_defaults(func=build_command)

    query_parser = subparsers.add_parser("query", help="Run reranked retrieval over built artifacts")
    query_parser.add_argument("--graph", required=True, help="Path to graph.json")
    query_parser.add_argument("--chunks", required=True, help="Path to chunks.json")
    query_parser.add_argument("--question", required=True, help="Question to search for")
    query_parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    query_parser.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")
    query_parser.set_defaults(func=query_command)

    relationship_parser = subparsers.add_parser(
        "build-relationships",
        help="Build a richer multi-source relationship graph from a taxonomy docx and supporting sources",
    )
    relationship_parser.add_argument("--taxonomy", required=True, help="Primary taxonomy .docx path")
    relationship_parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Supplemental source path. Repeat for each .pdf or .docx source.",
    )
    relationship_parser.add_argument("--output-dir", required=True, help="Directory for generated artifacts")
    relationship_parser.add_argument(
        "--title",
        default="Hong Kong Contract Law Relationship Graph",
        help="Display title for the generated graph",
    )
    relationship_parser.set_defaults(func=build_relationships_command)

    public_relationship_parser = subparsers.add_parser(
        "export-public-relationships",
        help="Create a public-safe relationship graph artifact from a richer local graph",
    )
    public_relationship_parser.add_argument("--graph", required=True, help="Path to relationship_graph.json")
    public_relationship_parser.add_argument("--output-dir", required=True, help="Directory for generated artifacts")
    public_relationship_parser.add_argument(
        "--title",
        default="Hong Kong Contract Law Public Relationship Graph",
        help="Display title for the generated graph",
    )
    public_relationship_parser.set_defaults(func=export_public_relationships_command)

    hybrid_parser = subparsers.add_parser(
        "build-hybrid-graph",
        help="Build the hierarchical graph bundle, public projection, and Neo4j-ready artifacts from a relationship graph JSON payload",
    )
    hybrid_parser.add_argument("--graph", required=True, help="Path to relationship_graph.json or public relationship graph JSON")
    hybrid_parser.add_argument("--output-dir", required=True, help="Directory for generated hierarchical graph artifacts")
    hybrid_parser.add_argument(
        "--title",
        default="Casemap Hybrid Hierarchical Graph",
        help="Display title for the generated hybrid graph bundle",
    )
    hybrid_parser.add_argument(
        "--embedding-backend",
        default="auto",
        help="Embedding backend to use for summary vectors: auto, local-hash, sentence-transformers, or openai",
    )
    hybrid_parser.add_argument(
        "--embedding-model",
        default="",
        help="Optional model override for the selected embedding backend",
    )
    hybrid_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=0,
        help="Optional embedding dimension override when supported by the chosen backend",
    )
    hybrid_parser.set_defaults(func=build_hybrid_graph_command)

    merge_hybrid_parser = subparsers.add_parser(
        "merge-hybrid-graph",
        help="Merge a freshly built hierarchical graph with the previous artifact, preserving prior authorities",
    )
    merge_hybrid_parser.add_argument("--graph", required=True, help="Path to the freshly built hierarchical_graph.json")
    merge_hybrid_parser.add_argument("--previous", required=True, help="Path to the previous hierarchical_graph.json")
    merge_hybrid_parser.add_argument("--output-dir", required=True, help="Directory to write merged hybrid artifacts")
    merge_hybrid_parser.add_argument(
        "--max-total-nodes",
        type=int,
        default=10000,
        help="Soft cap for merged graph size; prunes only low-value unenriched case-only shells",
    )
    merge_hybrid_parser.set_defaults(func=merge_hybrid_graph_command)

    criminal_parser = subparsers.add_parser(
        "build-criminal-graph",
        help="Build a Hong Kong criminal-law graph from textbook sources plus HKLII primary materials",
    )
    criminal_parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Supplemental criminal-law source path. Repeat for each .pdf or .docx source.",
    )
    criminal_parser.add_argument("--output-dir", required=True, help="Directory for generated relationship, embedding, and monitor artifacts")
    criminal_parser.add_argument(
        "--hybrid-output-dir",
        default="",
        help="Optional directory for hierarchical graph artifacts. If omitted, only relationship and storage exports are written.",
    )
    criminal_parser.add_argument(
        "--title",
        default="Hong Kong Criminal Law Relationship Graph",
        help="Display title for the generated criminal-law graph",
    )
    criminal_parser.add_argument("--per-query-limit", type=int, default=8, help="Maximum HKLII case hits to retain per seeded topic query")
    criminal_parser.add_argument("--max-cases", type=int, default=400, help="Upper bound on HKLII case documents to fetch")
    criminal_parser.add_argument(
        "--max-textbook-case-fetches",
        type=int,
        default=80,
        help="Upper bound on HKLII backfill fetches triggered by textbook case mentions",
    )
    criminal_parser.add_argument(
        "--max-enrich",
        type=int,
        default=80,
        help="Maximum number of cases to auto-enrich via HKLII + LLM (requires DEEPSEEK_API_KEY or OPENROUTER_API_KEY)",
    )
    criminal_parser.add_argument(
        "--env-file",
        action="append",
        default=[".env.local", ".env"],
        help="Env file to load before building. Repeat to add more files.",
    )
    criminal_parser.add_argument(
        "--embedding-backend",
        default="auto",
        help="Embedding backend to use: auto, local-hash, sentence-transformers, or openai",
    )
    criminal_parser.add_argument(
        "--embedding-model",
        default="",
        help="Optional model override for the selected embedding backend",
    )
    criminal_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=0,
        help="Optional embedding dimension override when supported by the chosen backend",
    )
    criminal_parser.add_argument(
        "--discover-lineages",
        action="store_true",
        help="Ask DeepSeek/OpenRouter to discover authority lineages from existing graph authorities before writing artifacts.",
    )
    criminal_parser.add_argument(
        "--lineages-path",
        default="",
        help="Path for auto-discovered lineage JSON.",
    )
    criminal_parser.add_argument(
        "--enrichment-cache",
        default="",
        help="Path to enrichment cache JSON. Cached paragraph/proposition nodes are injected at build start; new enrichments are saved here after build completes.",
    )
    criminal_parser.set_defaults(func=build_criminal_graph_command)

    domain_parser = subparsers.add_parser(
        "build-domain-graph",
        help="Build a domain-specific Hong Kong legal graph from a domain topic tree plus HKLII primary materials",
    )
    domain_parser.add_argument("--domain", required=True, help="Legal domain id, such as criminal, contract, commercial, family, or probate")
    domain_parser.add_argument(
        "--tree",
        default="",
        help="Optional JSON authority tree path. If omitted, data/batch/domain_trees/{domain}_tree.json is used or generated when DeepSeek is configured.",
    )
    domain_parser.add_argument(
        "--candidates",
        default="",
        help="Optional global candidates.json registry path for callers that keep crawl state outside this graph builder.",
    )
    domain_parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Supplemental domain source path. Repeat for each .pdf or .docx source.",
    )
    domain_parser.add_argument("--output-dir", required=True, help="Directory for generated relationship, embedding, and monitor artifacts")
    domain_parser.add_argument(
        "--hybrid-output-dir",
        default="",
        help="Optional directory for hierarchical graph artifacts. If omitted, only relationship and storage exports are written.",
    )
    domain_parser.add_argument(
        "--title",
        default="",
        help="Display title for the generated domain graph. Defaults to the loaded domain tree label.",
    )
    domain_parser.add_argument("--per-query-limit", type=int, default=8, help="Maximum HKLII case hits to retain per seeded topic query")
    domain_parser.add_argument("--max-cases", type=int, default=400, help="Upper bound on HKLII case documents to fetch")
    domain_parser.add_argument(
        "--max-textbook-case-fetches",
        type=int,
        default=80,
        help="Upper bound on HKLII backfill fetches triggered by textbook case mentions",
    )
    domain_parser.add_argument(
        "--max-enrich",
        type=int,
        default=80,
        help="Maximum number of cases to auto-enrich via HKLII + LLM (requires DEEPSEEK_API_KEY or OPENROUTER_API_KEY)",
    )
    domain_parser.add_argument(
        "--env-file",
        action="append",
        default=[".env.local", ".env"],
        help="Env file to load before building. Repeat to add more files.",
    )
    domain_parser.add_argument(
        "--embedding-backend",
        default="auto",
        help="Embedding backend to use: auto, local-hash, sentence-transformers, or openai",
    )
    domain_parser.add_argument(
        "--embedding-model",
        default="",
        help="Optional model override for the selected embedding backend",
    )
    domain_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=0,
        help="Optional embedding dimension override when supported by the chosen backend",
    )
    domain_parser.add_argument(
        "--discover-lineages",
        action="store_true",
        help="Ask DeepSeek/OpenRouter to discover authority lineages from existing graph authorities before writing artifacts.",
    )
    domain_parser.add_argument(
        "--lineages-path",
        default="",
        help="Path for auto-discovered lineage JSON. Existing lineages are loaded when this flag is supplied.",
    )
    domain_parser.add_argument(
        "--enrichment-cache",
        default="",
        help="Path to enrichment cache JSON. Cached paragraph/proposition nodes are injected at build start; new enrichments are saved here after build completes.",
    )
    domain_parser.set_defaults(func=build_domain_graph_command)

    discover_lineages_parser = subparsers.add_parser(
        "discover-lineages",
        help="Discover authority lineages from an existing relationship or hybrid graph JSON using DeepSeek/OpenRouter.",
    )
    discover_lineages_parser.add_argument("--graph", required=True, help="Path to relationship_graph.json or hierarchical_graph.json")
    discover_lineages_parser.add_argument("--domain", default="", help="Legal domain id, such as criminal or civil")
    discover_lineages_parser.add_argument("--output", default=str(DISCOVERED_LINEAGES_DEFAULT_PATH), help="Output JSON path")
    discover_lineages_parser.add_argument("--max-topics", type=int, default=None, help="Optional cap on topic count for discovery")
    discover_lineages_parser.set_defaults(func=discover_lineages_command)

    sync_parser = subparsers.add_parser(
        "sync-criminal-supabase",
        help="Upload current criminal-law artifacts and a bounded set of HKLII-backed cases into Supabase Storage and Postgres",
    )
    sync_parser.add_argument(
        "--graph",
        default=str(Path("artifacts") / "hk_criminal_relationship" / "relationship_graph.json"),
        help="Path to the criminal relationship_graph.json artifact",
    )
    sync_parser.add_argument(
        "--output-dir",
        default=str(Path("artifacts") / "hk_criminal_relationship"),
        help="Relationship artifact directory to upload",
    )
    sync_parser.add_argument(
        "--hybrid-output-dir",
        default=str(Path("artifacts") / "hk_criminal_hybrid"),
        help="Optional hybrid artifact directory to upload",
    )
    sync_parser.add_argument("--bucket", default="Casebase", help="Supabase Storage bucket name")
    sync_parser.add_argument(
        "--prefix",
        default="casemap/hk_criminal/latest",
        help="Storage prefix for uploaded artifacts and per-case JSON files",
    )
    sync_parser.add_argument("--max-cases", type=int, default=40, help="Maximum number of HKLII-backed cases to sync")
    sync_parser.add_argument(
        "--embedding-backend",
        default="sentence-transformers",
        help="Embedding backend for case chunk vectors",
    )
    sync_parser.add_argument(
        "--embedding-model",
        default="",
        help="Optional model override for the selected embedding backend",
    )
    sync_parser.add_argument(
        "--env-file",
        action="append",
        default=[".env.local", ".env"],
        help="Env file to load before syncing. Repeat to add more files.",
    )
    sync_parser.add_argument(
        "--no-prune-prefix-cases",
        action="store_false",
        dest="prune_prefix_cases",
        help="Keep older cases already stored under the same prefix instead of pruning them after sync",
    )
    sync_parser.add_argument(
        "--prune-prefix-cases",
        action="store_true",
        dest="prune_prefix_cases",
        help="Delete Supabase case JSON files under the prefix that were not uploaded in this sync",
    )
    sync_parser.set_defaults(prune_prefix_cases=False)
    sync_parser.set_defaults(func=sync_criminal_supabase_command)

    hybrid_query_parser = subparsers.add_parser(
        "hybrid-query",
        help="Run a hybrid graph query over hierarchical_graph.json",
    )
    hybrid_query_parser.add_argument("--graph", required=True, help="Path to hierarchical_graph.json")
    hybrid_query_parser.add_argument("--question", required=True, help="Question to ask")
    hybrid_query_parser.add_argument("--top-k", type=int, default=5, help="Number of supporting case cards to return")
    hybrid_query_parser.set_defaults(func=hybrid_query_command)

    serve_internal_parser = subparsers.add_parser(
        "serve-internal",
        help="Serve the internal API-driven hierarchical graph explorer",
    )
    serve_internal_parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    serve_internal_parser.add_argument("--port", type=int, default=8052, help="Port to bind")
    serve_internal_parser.set_defaults(func=serve_internal_command)

    return main_parser


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
