from __future__ import annotations

from casemap.hybrid_graph import HybridGraphStore


def test_find_similar_cases_uses_embeddings_and_excludes_same_lineage():
    bundle = {
        "meta": {"title": "Test", "legal_domain": "criminal"},
        "tree": {"id": "tree", "label_en": "Tree", "label_zh": "", "modules": []},
        "nodes": [
            {"id": "case:source", "type": "Case", "label": "Source v HKSAR", "case_name": "Source v HKSAR", "summary_en": "robbery store weapon", "summary_embedding": [1.0, 0.0], "lineage_ids": ["same"]},
            {"id": "case:same", "type": "Case", "label": "Same v HKSAR", "case_name": "Same v HKSAR", "summary_en": "robbery same lineage", "summary_embedding": [0.99, 0.01], "lineage_ids": ["same"]},
            {"id": "case:similar", "type": "Case", "label": "Similar v HKSAR", "case_name": "Similar v HKSAR", "summary_en": "robbery shop weapon", "summary_embedding": [0.9, 0.1], "lineage_ids": []},
            {"id": "case:different", "type": "Case", "label": "Different v HKSAR", "case_name": "Different v HKSAR", "summary_en": "tax evasion", "summary_embedding": [0.0, 1.0], "lineage_ids": []},
        ],
        "edges": [],
        "case_cards": {},
    }
    store = HybridGraphStore(bundle)

    similar = store.find_similar_cases("case:source", top_k=2)

    assert [case["case_id"] for case in similar] == ["case:similar", "case:different"]
    assert all(case["case_id"] != "case:same" for case in similar)


def test_find_similar_cases_for_text_falls_back_to_lexical():
    bundle = {
        "meta": {"title": "Test", "legal_domain": "criminal"},
        "tree": {"id": "tree", "label_en": "Tree", "label_zh": "", "modules": []},
        "nodes": [
            {"id": "case:robbery", "type": "Case", "label": "Robbery v HKSAR", "case_name": "Robbery v HKSAR", "summary_en": "robbery store weapon", "summary_embedding": []},
            {"id": "case:tax", "type": "Case", "label": "Tax v HKSAR", "case_name": "Tax v HKSAR", "summary_en": "tax return", "summary_embedding": []},
        ],
        "edges": [],
        "case_cards": {},
    }
    store = HybridGraphStore(bundle)
    store._embedding_backend = None

    similar = store.find_similar_cases_for_text("weapon robbery in a store", top_k=1)

    assert similar[0]["case_id"] == "case:robbery"
