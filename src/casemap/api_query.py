"""Shared HTTP handlers for hybrid graph + optional Supabase chunk retrieval."""
from __future__ import annotations

import os
from typing import Any

from .hybrid_graph import DeterminatorPipeline, HybridGraphStore, _infer_legal_domain
from .supabase_chunk_query import (
    SupabaseRuntimeConfig,
    chunks_to_citations,
    fetch_ranked_case_chunks,
    merge_remote_chunks_into_result,
)


def _supabase_query_enabled() -> bool:
    flag = os.environ.get("CASEMAP_SUPABASE_QUERY", "0").strip().lower()
    if flag in {"0", "false", "off", "no"}:
        return False
    if flag in {"auto", "1", "true", "on", "yes"}:
        return SupabaseRuntimeConfig.from_env() is not None
    return False


def run_hybrid_post_query(
    hybrid_store: HybridGraphStore,
    question: str,
    *,
    top_k: int,
    mode: str,
    model: str,
    max_citations: int,
) -> dict[str, Any]:
    """POST /api/query body: classify criminal queries, run hybrid retrieval, merge Supabase chunks."""
    legal_domain = _infer_legal_domain(hybrid_store.bundle.get("meta"))
    if legal_domain == "criminal":
        pipeline = DeterminatorPipeline()
        classification = pipeline._classify(question)
        if not classification["is_criminal"]:
            return {
                "question": question,
                "is_criminal": False,
                "answer": (
                    "This query does not appear to relate to Hong Kong criminal law. "
                    "Please rephrase your question or consult a general legal resource."
                ),
                "answer_mode": "classification_reject",
                "citations": [],
                "sources": [],
                "offence_candidates": classification["offence_candidates"],
                "primary_ordinance": classification["primary_ordinance"],
                "retrieval_trace": {"classification": classification},
            }
        result = hybrid_store.query(
            question,
            top_k=top_k,
            mode=mode,
            model=model,
            max_citations=max_citations,
            classification_area=classification.get("area", ""),
            offence_keywords=classification.get("criminal_hits", []),
        )
        trace = dict(result.get("retrieval_trace") or {})
        trace["classification"] = classification
        result["retrieval_trace"] = trace
    else:
        result = hybrid_store.query(
            question,
            top_k=top_k,
            mode=mode,
            model=model,
            max_citations=max_citations,
        )

    if _supabase_query_enabled():
        cfg = SupabaseRuntimeConfig.from_env()
        if cfg is not None:
            warnings = list(result.get("warnings") or [])
            try:
                rows, w = fetch_ranked_case_chunks(
                    cfg,
                    question,
                    classification=(result.get("retrieval_trace") or {}).get("classification"),
                )
                warnings.extend(w)
                extra = chunks_to_citations(rows)
                if extra:
                    result = merge_remote_chunks_into_result(result, extra, max_citations=max_citations)
            except Exception as exc:  # pragma: no cover - network
                warnings.append(f"supabase_query:{exc}")
            if warnings:
                result["warnings"] = warnings
    return result
