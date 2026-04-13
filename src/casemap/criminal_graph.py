from __future__ import annotations

from pathlib import Path

from . import domain_graph as _domain_graph
from .criminal_law_data import CRIMINAL_AUTHORITY_TREE, iter_criminal_topics

HKLIICrawler = _domain_graph.HKLIICrawler
load_source_document = _domain_graph.load_source_document


def _sync_patchable_dependencies() -> None:
    _domain_graph.HKLIICrawler = HKLIICrawler
    _domain_graph.load_source_document = load_source_document


def build_criminal_relationship_payload(
    source_paths: list[str | Path],
    title: str = "Hong Kong Criminal Law Relationship Graph",
    per_query_limit: int = 8,
    max_cases: int = 400,
    max_textbook_case_fetches: int = 80,
    progress_callback=None,
) -> tuple:
    _sync_patchable_dependencies()
    return _domain_graph.build_criminal_relationship_payload(
        source_paths=source_paths,
        title=title,
        per_query_limit=per_query_limit,
        max_cases=max_cases,
        max_textbook_case_fetches=max_textbook_case_fetches,
        progress_callback=progress_callback,
    )


def build_criminal_graph_artifacts(
    source_paths: list[str | Path],
    relationship_output_dir: str | Path,
    hybrid_output_dir: str | Path | None = None,
    title: str = "Hong Kong Criminal Law Relationship Graph",
    per_query_limit: int = 8,
    max_cases: int = 400,
    max_textbook_case_fetches: int = 80,
    max_enrich: int = 80,
    embedding_backend: str = "auto",
    embedding_model: str = "",
    embedding_dimensions: int = 0,
    discover_lineages: bool = False,
    lineages_path: str | Path | None = None,
) -> dict:
    _sync_patchable_dependencies()
    return _domain_graph.build_criminal_graph_artifacts(
        source_paths=source_paths,
        relationship_output_dir=relationship_output_dir,
        hybrid_output_dir=hybrid_output_dir,
        title=title,
        per_query_limit=per_query_limit,
        max_cases=max_cases,
        max_textbook_case_fetches=max_textbook_case_fetches,
        max_enrich=max_enrich,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        discover_lineages=discover_lineages,
        lineages_path=lineages_path,
    )


__all__ = [
    "CRIMINAL_AUTHORITY_TREE",
    "HKLIICrawler",
    "build_criminal_graph_artifacts",
    "build_criminal_relationship_payload",
    "iter_criminal_topics",
    "load_source_document",
]
