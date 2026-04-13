from __future__ import annotations

import json
from pathlib import Path

from casemap.hybrid_graph import merge_with_previous_artifact


def _bundle(nodes: list[dict], edges: list[dict], case_cards: dict | None = None) -> dict:
    return {
        "meta": {"title": "Test", "generated_at": "fresh", "legal_domain": "criminal"},
        "tree": {"id": "tree", "label_en": "Tree", "label_zh": "", "modules": []},
        "nodes": nodes,
        "edges": edges,
        "case_cards": case_cards or {},
    }


def test_merge_with_previous_artifact_keeps_previous_only_enrichment(tmp_path):
    previous = _bundle(
        [
            {"id": "topic:old", "type": "Topic", "label": "Old Topic", "path": "Old/Topic"},
            {"id": "case:old", "type": "Case", "label": "Old", "case_name": "Old", "enrichment_status": "auto_enriched", "authority_score": 0.8, "topic_paths": ["Old/Topic"]},
            {"id": "paragraph:old", "type": "Paragraph", "label": "Old para", "case_id": "case:old", "public_excerpt": "Old principle"},
            {"id": "proposition:old", "type": "Proposition", "label": "Old proposition", "statement_en": "Old principle"},
        ],
        [
            {"source": "case:old", "target": "topic:old", "type": "BELONGS_TO_TOPIC"},
            {"source": "paragraph:old", "target": "case:old", "type": "PART_OF"},
            {"source": "paragraph:old", "target": "proposition:old", "type": "SUPPORTS"},
        ],
        {"case:old": {"id": "case:old", "metadata": {"enrichment_status": "auto_enriched", "topic_paths": ["Old/Topic"]}}},
    )
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    fresh = _bundle(
        [
            {"id": "topic:new", "type": "Topic", "label": "New Topic", "path": "New/Topic"},
            {"id": "case:new", "type": "Case", "label": "New", "case_name": "New", "enrichment_status": "case_only", "authority_score": 0.2, "topic_paths": ["New/Topic"]},
        ],
        [{"source": "case:new", "target": "topic:new", "type": "BELONGS_TO_TOPIC"}],
    )

    merged = merge_with_previous_artifact(fresh, previous_path, max_total_nodes=100)

    node_ids = {node["id"] for node in merged["nodes"]}
    assert {"case:old", "paragraph:old", "proposition:old", "case:new"} <= node_ids
    assert merged["meta"]["paragraph_count"] == 1
    assert merged["meta"]["proposition_count"] == 1
    assert merged["meta"]["cumulative_merge"]["retained_previous_only_nodes"] == 4
    assert "case:old" in merged["case_cards"]


def test_merge_prunes_only_low_value_case_only_shells(tmp_path):
    previous = _bundle(
        [
            {"id": "case:enriched", "type": "Case", "label": "Enriched", "case_name": "Enriched", "enrichment_status": "auto_enriched", "authority_score": 0.9},
            {"id": "paragraph:enriched", "type": "Paragraph", "label": "Para", "case_id": "case:enriched"},
            {"id": "proposition:enriched", "type": "Proposition", "label": "Prop"},
            {"id": "case:shell_low", "type": "Case", "label": "Low", "case_name": "Low", "enrichment_status": "case_only", "authority_score": 0.01},
            {"id": "case:shell_high", "type": "Case", "label": "High", "case_name": "High", "enrichment_status": "case_only", "authority_score": 0.5},
        ],
        [
            {"source": "paragraph:enriched", "target": "case:enriched", "type": "PART_OF"},
            {"source": "paragraph:enriched", "target": "proposition:enriched", "type": "SUPPORTS"},
        ],
    )
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    fresh = _bundle([
        {"id": "case:new", "type": "Case", "label": "New", "case_name": "New", "enrichment_status": "case_only", "authority_score": 0.2}
    ], [])

    merged = merge_with_previous_artifact(fresh, previous_path, max_total_nodes=5)

    node_ids = {node["id"] for node in merged["nodes"]}
    assert "case:enriched" in node_ids
    assert "paragraph:enriched" in node_ids
    assert "proposition:enriched" in node_ids
    assert "case:shell_low" not in node_ids
    assert merged["meta"]["cumulative_merge"]["pruned_case_only_nodes"] == 1


def test_merge_repairs_orphaned_topic_paths_after_topic_rename(tmp_path):
    previous = _bundle(
        [
            {"id": "topic:fraud", "type": "Topic", "label": "Fraud", "path": "Old/Fraud"},
            {"id": "case:fraud", "type": "Case", "label": "Fraud Case", "case_name": "Fraud Case", "enrichment_status": "case_only", "topic_paths": ["Old/Fraud"]},
        ],
        [{"source": "case:fraud", "target": "topic:fraud", "type": "BELONGS_TO_TOPIC"}],
    )
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")
    fresh = _bundle(
        [{"id": "topic:fraud", "type": "Topic", "label": "Fraud", "path": "New/Fraud"}],
        [],
    )

    merged = merge_with_previous_artifact(fresh, previous_path, max_total_nodes=100)
    case = next(node for node in merged["nodes"] if node["id"] == "case:fraud")

    assert case["topic_paths"] == ["New/Fraud"]
    assert merged["meta"]["cumulative_merge"]["removed_orphan_topic_paths"] == 1


# ── Edge-case tests ──────────────────────────────────────────────────────────

def test_merge_deduplicates_edges(tmp_path):
    """Truly identical edges (same source/target/type/metadata) must appear exactly once."""
    # _edge_merge_key includes all metadata, so identical edges deduplicate; edges with
    # different metadata (e.g. different explanation) are intentionally kept as separate records.
    identical_edge = {"source": "case:a", "target": "case:b", "type": "FOLLOWS", "curated": True}
    previous = _bundle(
        [
            {"id": "case:a", "type": "Case", "label": "A", "case_name": "A", "enrichment_status": "case_only", "authority_score": 0.5},
            {"id": "case:b", "type": "Case", "label": "B", "case_name": "B", "enrichment_status": "case_only", "authority_score": 0.5},
        ],
        [identical_edge],
    )
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    # Fresh has the exact same edge — should not be duplicated
    fresh = _bundle(
        [
            {"id": "case:a", "type": "Case", "label": "A", "case_name": "A", "enrichment_status": "case_only", "authority_score": 0.5},
            {"id": "case:b", "type": "Case", "label": "B", "case_name": "B", "enrichment_status": "case_only", "authority_score": 0.5},
        ],
        [identical_edge],
    )

    merged = merge_with_previous_artifact(fresh, previous_path, max_total_nodes=100)

    follows_edges = [e for e in merged["edges"] if e["type"] == "FOLLOWS" and e["source"] == "case:a"]
    assert len(follows_edges) == 1, f"Identical edge appeared {len(follows_edges)} times — should be exactly 1"


def test_merge_drops_case_card_when_node_pruned(tmp_path):
    """When a node is pruned by the soft cap, its case_card must also be removed."""
    previous = _bundle(
        [
            {"id": "case:keep", "type": "Case", "label": "Keep", "case_name": "Keep",
             "enrichment_status": "auto_enriched", "authority_score": 0.9},
            {"id": "case:prune", "type": "Case", "label": "Prune", "case_name": "Prune",
             "enrichment_status": "case_only", "authority_score": 0.01},
        ],
        [],
        {
            "case:keep":  {"id": "case:keep",  "metadata": {"enrichment_status": "auto_enriched"}},
            "case:prune": {"id": "case:prune", "metadata": {"enrichment_status": "case_only"}},
        },
    )
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    # Fresh has only two new nodes; merged total = 4; cap=3 forces one pruning
    fresh = _bundle(
        [
            {"id": "case:new1", "type": "Case", "label": "New1", "case_name": "New1",
             "enrichment_status": "case_only", "authority_score": 0.2},
            {"id": "case:new2", "type": "Case", "label": "New2", "case_name": "New2",
             "enrichment_status": "case_only", "authority_score": 0.3},
        ],
        [],
        {
            "case:new1": {"id": "case:new1", "metadata": {"enrichment_status": "case_only"}},
            "case:new2": {"id": "case:new2", "metadata": {"enrichment_status": "case_only"}},
        },
    )

    merged = merge_with_previous_artifact(fresh, previous_path, max_total_nodes=3)

    node_ids = {n["id"] for n in merged["nodes"]}
    card_ids = set(merged["case_cards"].keys())
    # case:prune should be gone
    assert "case:prune" not in node_ids
    assert "case:prune" not in card_ids, "case_card must be removed when its node is pruned"
    # case:keep must survive (enriched)
    assert "case:keep" in node_ids
    assert "case:keep" in card_ids


def test_merge_with_missing_previous_returns_fresh_unchanged(tmp_path):
    """When no previous artifact exists, merged result equals the fresh bundle."""
    fresh = _bundle(
        [
            {"id": "case:only", "type": "Case", "label": "Only", "case_name": "Only",
             "enrichment_status": "case_only", "authority_score": 0.4},
        ],
        [],
    )

    nonexistent = tmp_path / "does_not_exist.json"
    merged = merge_with_previous_artifact(fresh, nonexistent, max_total_nodes=100)

    node_ids = {n["id"] for n in merged["nodes"]}
    assert "case:only" in node_ids
    assert merged["meta"]["node_count"] == 1
    assert merged["meta"]["cumulative_merge"]["previous_found"] is False
    assert merged["meta"]["cumulative_merge"]["enabled"] is True


def test_merge_removes_edges_whose_nodes_were_pruned(tmp_path):
    """Edges referencing pruned nodes must not appear in the merged output.

    CITES/FOLLOWS/etc (CASE_EDGE_TYPES) protect both endpoints from pruning.
    So we use a BELONGS_TO_TOPIC edge (not in CASE_EDGE_TYPES) to attach the shell
    to a topic without granting it protection — then verify the edge is cleaned up.
    """
    previous = _bundle(
        [
            {"id": "case:rich", "type": "Case", "label": "Rich", "case_name": "Rich",
             "enrichment_status": "auto_enriched", "authority_score": 0.9},
            {"id": "case:shell", "type": "Case", "label": "Shell", "case_name": "Shell",
             "enrichment_status": "case_only", "authority_score": 0.01},
            {"id": "topic:t", "type": "Topic", "label": "T", "path": "T/T"},
        ],
        [
            # BELONGS_TO_TOPIC does NOT protect case:shell from pruning
            {"source": "case:shell", "target": "topic:t", "type": "BELONGS_TO_TOPIC"},
        ],
    )
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    # Fresh has only one new case; merged total = 4 nodes; cap=3 prunes the shell
    fresh = _bundle(
        [{"id": "case:new", "type": "Case", "label": "New", "case_name": "New",
          "enrichment_status": "case_only", "authority_score": 0.5}],
        [],
    )

    merged = merge_with_previous_artifact(fresh, previous_path, max_total_nodes=3)

    node_ids = {n["id"] for n in merged["nodes"]}
    assert "case:shell" not in node_ids, "Low-value unconnected shell should be pruned"

    stale_edges = [
        e for e in merged["edges"]
        if e.get("source") == "case:shell" or e.get("target") == "case:shell"
    ]
    assert stale_edges == [], f"Edges referencing pruned node must be removed, found: {stale_edges}"
