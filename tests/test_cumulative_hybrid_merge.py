from __future__ import annotations

import json

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
