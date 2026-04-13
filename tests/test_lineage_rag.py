from __future__ import annotations

from casemap.hybrid_graph import HybridGraphStore


def _bundle() -> dict:
    return {
        "meta": {"title": "Test", "legal_domain": "criminal", "lineage_count": 1},
        "tree": {"id": "tree", "label_en": "Tree", "label_zh": "", "modules": []},
        "nodes": [
            {"id": "topic:provocation", "type": "Topic", "label": "Provocation", "label_en": "Provocation", "summary": "Provocation defence"},
            {
                "id": "lineage:provocation_chain",
                "type": "AuthorityLineage",
                "label": "Provocation chain",
                "title": "Provocation chain",
                "topic_ids": ["topic:provocation"],
                "topic_labels": ["Provocation"],
                "codes": ["ORIG", "FLLW", "APPD"],
                "source": "auto",
                "confidence_status": "preliminary",
                "confidence_score": 0.7,
            },
            {"id": "case:a", "type": "Case", "label": "A v HKSAR", "case_name": "A v HKSAR", "summary_en": "Original provocation defence case.", "topic_paths": ["Provocation"], "lineage_ids": ["provocation_chain"], "authority_score": 0.8},
            {"id": "case:b", "type": "Case", "label": "B v HKSAR", "case_name": "B v HKSAR", "summary_en": "Followed provocation defence.", "topic_paths": ["Provocation"], "lineage_ids": ["provocation_chain"], "authority_score": 0.7},
            {"id": "case:c", "type": "Case", "label": "C v HKSAR", "case_name": "C v HKSAR", "summary_en": "Applied provocation defence.", "topic_paths": ["Provocation"], "lineage_ids": ["provocation_chain"], "authority_score": 0.6},
        ],
        "edges": [
            {"source": "case:a", "target": "topic:provocation", "type": "BELONGS_TO_TOPIC", "weight": 1.0},
            {"source": "case:b", "target": "topic:provocation", "type": "BELONGS_TO_TOPIC", "weight": 1.0},
            {"source": "case:c", "target": "topic:provocation", "type": "BELONGS_TO_TOPIC", "weight": 1.0},
            {"source": "lineage:provocation_chain", "target": "topic:provocation", "type": "ABOUT_TOPIC", "weight": 1.0},
            {"source": "lineage:provocation_chain", "target": "case:a", "type": "HAS_MEMBER", "position": 1, "code": "ORIG", "treatment": "originating", "weight": 1.0},
            {"source": "lineage:provocation_chain", "target": "case:b", "type": "HAS_MEMBER", "position": 2, "code": "FLLW", "treatment": "followed", "weight": 1.0},
            {"source": "lineage:provocation_chain", "target": "case:c", "type": "HAS_MEMBER", "position": 3, "code": "APPD", "treatment": "applied", "weight": 1.0},
        ],
        "case_cards": {},
    }


def test_query_returns_matched_lineages_and_full_path():
    store = HybridGraphStore(_bundle())
    result = store.query("provocation defence", top_k=3)

    assert result["matched_lineages"]
    assert result["matched_lineages"][0]["id"] == "provocation_chain"
    assert result["authority_lineage_path"][0]["members"]
    assert [member["label"] for member in result["authority_lineage_path"][0]["members"]] == [
        "A v HKSAR",
        "B v HKSAR",
        "C v HKSAR",
    ]
