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


def test_market_misconduct_live_grounding_filter_requires_sfo_context():
    assert hg._is_market_misconduct_grounding(
        "The SFC alleged false trading under the Securities and Futures Ordinance."
    )
    assert not hg._is_market_misconduct_grounding(
        "There are overseas proceedings for market manipulation and fraud."
    )


def test_options_query_maps_to_sfo_licensing_context():
    classification = DeterminatorPipeline()._classify("How to trade options without breaching law")
    assert classification["is_criminal"] is True
    assert "options" in classification["criminal_hits"]
    assert classification["primary_ordinance"]["ordinance"] == "Securities and Futures Ordinance (Cap. 571)"


def test_weak_fallback_offtopic_citations_are_suppressed_for_options_query(monkeypatch):
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
                "id": "case:irrelevant",
                "type": "Case",
                "label": "Irrelevant Case",
                "case_name": "Irrelevant Case",
                "summary_en": "A defendant cannot be guilty of rape if belief in consent is honest.",
                "topic_paths": ["Sexual offences"],
                "authority_score": 0.9,
            },
            {
                "id": "paragraph:irrelevant",
                "type": "Paragraph",
                "label": "Irrelevant [22]",
                "case_id": "case:irrelevant",
                "paragraph_span": "[22]",
                "public_excerpt": "The court considered options after probation failure in sentencing.",
                "hklii_deep_link": "https://example.com#p22",
            },
            {
                "id": "proposition:irrelevant",
                "type": "Proposition",
                "label": "Honest belief in consent",
                "label_en": "Honest belief in consent",
                "statement_en": "The court considered options after probation failure in sentencing.",
            },
        ],
        "edges": [
            {"source": "paragraph:irrelevant", "target": "case:irrelevant", "type": "PART_OF", "weight": 1.0},
            {"source": "paragraph:irrelevant", "target": "proposition:irrelevant", "type": "SUPPORTS", "weight": 1.0},
        ],
        "case_cards": {},
    }
    store = HybridGraphStore(bundle)
    result = store.query("How to trade options without breaching law", top_k=5, mode="extractive", max_citations=8)
    assert result["citations"] == []
    assert any("No reliable local citations" in warning for warning in result["warnings"])
