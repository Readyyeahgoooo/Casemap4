"""Unit tests for Supabase chunk RPC wiring (no live network)."""
from __future__ import annotations

import os
from unittest import mock

from casemap.supabase_chunk_query import (
    SupabaseRuntimeConfig,
    _classification_rpc_filters,
    fetch_ranked_case_chunks,
    merge_remote_chunks_into_result,
)


def test_classification_rpc_filters_maps_area_and_family():
    cl = {
        "area": "sentencing",
        "primary_ordinance": {"offence_family": "homicide"},
        "offence_candidates": [{"keyword_hits": ["murder", "sentence"]}],
    }
    f = _classification_rpc_filters(cl)
    assert f["p_legal_domain"] == "criminal"
    assert f["p_offence_family"] == "homicide"
    assert f["p_topic_label"] == "murder"
    assert f["p_classification_area"] == "sentencing"


def test_merge_remote_chunks_dedup_and_cap():
    base = {
        "citations": [
            {"case_id": "a", "quote": "hello world " * 5, "support_score": 0.9},
        ],
        "retrieval_trace": {},
    }
    extra = [
        {"case_id": "case_chunk:x:1", "quote": "new chunk " * 6, "support_score": 0.5},
        {"case_id": "case_chunk:x:1", "quote": "new chunk " * 6, "support_score": 0.6},
    ]
    out = merge_remote_chunks_into_result(base, extra, max_citations=2)
    assert len(out["citations"]) == 2
    quotes = [c["quote"][:20] for c in out["citations"]]
    assert any("new chunk" in q for q in quotes)


@mock.patch.dict(os.environ, {"CASEMAP_SUPABASE_USE_CHUNK_RPC": "1", "CASEMAP_QUERY_EMBEDDING_BACKEND": ""})
@mock.patch("casemap.supabase_chunk_query._fetch_via_rpc", return_value=[{"id": 1, "hklii_id": "t", "chunk_index": 1, "chunk_text": "x" * 40, "combined_score": 0.5}])
@mock.patch("casemap.supabase_chunk_query._fetch_ranked_ilike_legacy")
def test_fetch_ranked_prefers_rpc_when_rows(mock_legacy, mock_rpc):
    cfg = SupabaseRuntimeConfig(url="https://example.supabase.co", api_key="pk_test")
    rows, w = fetch_ranked_case_chunks(cfg, "What is theft?", classification=None)
    assert len(rows) == 1
    assert rows[0].get("_retrieval_mode") == "rpc"
    mock_legacy.assert_not_called()


@mock.patch.dict(os.environ, {"CASEMAP_SUPABASE_USE_CHUNK_RPC": "1", "CASEMAP_QUERY_EMBEDDING_BACKEND": ""})
@mock.patch(
    "casemap.supabase_chunk_query._fetch_via_rpc",
    side_effect=RuntimeError("HTTP 404 for https://example.supabase.co/rest/v1/rpc/match_case_chunks: not found"),
)
@mock.patch(
    "casemap.supabase_chunk_query._fetch_ranked_ilike_legacy",
    return_value=([{"id": 2, "hklii_id": "y", "chunk_index": 1, "chunk_text": "y" * 40}], []),
)
def test_fetch_ranked_falls_back_when_rpc_missing(mock_legacy, mock_rpc):
    cfg = SupabaseRuntimeConfig(url="https://example.supabase.co", api_key="pk_test")
    rows, w = fetch_ranked_case_chunks(cfg, "What is theft?", classification=None)
    assert rows[0].get("_retrieval_mode") == "ilike_legacy"
    mock_legacy.assert_called_once()
    assert any("chunk_rpc_unavailable" in x for x in w)
