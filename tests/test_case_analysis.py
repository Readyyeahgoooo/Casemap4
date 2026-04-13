from __future__ import annotations

from casemap.hybrid_graph import HybridGraphStore, analyse_case_facts


def test_analyse_case_returns_citations_lineages_and_similar_cases():
    bundle = {
        "meta": {"title": "Test", "legal_domain": "criminal", "lineage_count": 1},
        "tree": {"id": "tree", "label_en": "Tree", "label_zh": "", "modules": []},
        "nodes": [
            {"id": "topic:robbery", "type": "Topic", "label": "Robbery", "label_en": "Robbery", "summary": "Robbery with force"},
            {"id": "lineage:robbery_chain", "type": "AuthorityLineage", "label": "Robbery chain", "title": "Robbery chain", "topic_ids": ["topic:robbery"], "topic_labels": ["Robbery"], "source": "auto", "confidence_status": "preliminary"},
            {"id": "case:robbery", "type": "Case", "label": "Robbery v HKSAR", "case_name": "Robbery v HKSAR", "summary_en": "Robbery requires theft with force.", "topic_paths": ["Robbery"], "lineage_ids": ["robbery_chain"], "summary_embedding": [1.0, 0.0], "authority_score": 0.8},
            {"id": "paragraph:robbery", "type": "Paragraph", "label": "Robbery [1]", "case_id": "case:robbery", "paragraph_span": "[1]", "public_excerpt": "Robbery requires theft with force.", "hklii_deep_link": "https://www.hklii.hk/en/cases/hkca/2024/1#p1"},
            {"id": "proposition:robbery", "type": "Proposition", "label": "Robbery elements", "label_en": "Robbery elements", "statement_en": "Robbery requires theft with force."},
            {"id": "case:similar", "type": "Case", "label": "Similar v HKSAR", "case_name": "Similar v HKSAR", "summary_en": "Store robbery with force.", "summary_embedding": [0.9, 0.1], "authority_score": 0.7},
        ],
        "edges": [
            {"source": "case:robbery", "target": "topic:robbery", "type": "BELONGS_TO_TOPIC", "weight": 1.0},
            {"source": "lineage:robbery_chain", "target": "topic:robbery", "type": "ABOUT_TOPIC", "weight": 1.0},
            {"source": "lineage:robbery_chain", "target": "case:robbery", "type": "HAS_MEMBER", "position": 1, "code": "APPD", "weight": 1.0},
            {"source": "paragraph:robbery", "target": "case:robbery", "type": "PART_OF", "weight": 1.0},
            {"source": "paragraph:robbery", "target": "proposition:robbery", "type": "SUPPORTS", "weight": 1.0},
        ],
        "case_cards": {},
    }
    store = HybridGraphStore(bundle)

    result = analyse_case_facts(store, "A person uses force during robbery in a store.", mode="extractive", top_k=3)

    assert result["citations"]
    assert result["authority_lineage_path"]
    assert result["factually_similar_cases"]
    assert result["citations"][0]["hklii_deep_link"].endswith("#p1")
