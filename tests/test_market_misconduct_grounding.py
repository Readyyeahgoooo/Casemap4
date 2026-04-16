from __future__ import annotations

import casemap.hybrid_graph as hg
from casemap.hybrid_graph import DeterminatorPipeline, HybridGraphStore


def test_market_manipulation_is_classified_as_criminal_market_misconduct():
    classification = DeterminatorPipeline()._classify("market manipulation")

    assert classification["is_criminal"] is True
    assert {"market", "manipulation"} <= set(classification["criminal_hits"])
    assert classification["primary_ordinance"]["ordinance"] == "Securities and Futures Ordinance (Cap. 571)"


def test_placeholder_case_summaries_are_not_presented_as_citations(monkeypatch):
    monkeypatch.setattr(
        hg,
        "_live_hklii_grounding",
        lambda *args, **kwargs: {"citations": [], "sources": [], "warnings": [], "search_trace": []},
    )
    bundle = {
        "meta": {"title": "Test", "legal_domain": "criminal"},
        "tree": {"id": "tree", "label_en": "Tree", "label_zh": "", "modules": []},
        "nodes": [
            {
                "id": "topic:market",
                "type": "Topic",
                "label": "Market Manipulation and False Trading",
                "label_en": "Market Manipulation and False Trading",
                "summary": "Securities and Futures Ordinance market misconduct topic.",
            },
            {
                "id": "case:shell",
                "type": "Case",
                "label": "Shell Case",
                "case_name": "Shell Case",
                "summary_en": "Authority cited inside an HKLII Hong Kong Criminal Law judgment.",
                "topic_paths": ["Market Manipulation and False Trading"],
                "authority_score": 0.4,
            },
        ],
        "edges": [
            {"source": "case:shell", "target": "topic:market", "type": "BELONGS_TO_TOPIC", "weight": 1.0},
        ],
        "case_cards": {},
    }
    store = HybridGraphStore(bundle)
    classification = DeterminatorPipeline()._classify("market manipulation")

    result = store.query(
        "market manipulation",
        top_k=5,
        mode="extractive",
        max_citations=8,
        classification_area=classification["area"],
        offence_keywords=classification["criminal_hits"],
    )

    assert result["citations"] == []
    assert "Authority cited inside" not in result["answer"]
    assert "paragraph-level verified authority" in result["answer"]
    assert result["warnings"]
