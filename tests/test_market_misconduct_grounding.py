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


def test_offence_family_penalty_demotes_sexual_case_for_fraud_query(monkeypatch):
    """A fraud query should not return sexual-offence cases even when
    they accidentally share some lexical overlap."""
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
                "id": "case:sexual",
                "type": "Case",
                "label": "Sexual Case",
                "case_name": "R v Wong",
                "summary_en": "The accused obtained sexual gratification by deception and fraud against the victim.",
                "topic_paths": ["Sexual offences/Indecent Assault"],
                "offence_family": "sexual_offences",
                "authority_score": 0.8,
            },
            {
                "id": "case:fraud",
                "type": "Case",
                "label": "Fraud Case",
                "case_name": "HKSAR v Chan",
                "summary_en": "The defendant committed fraud and deception by obtaining property dishonestly from the company.",
                "topic_paths": ["Property and Dishonesty Offences/Fraud"],
                "offence_family": "fraud",
                "authority_score": 0.7,
            },
            {
                "id": "paragraph:fraud",
                "type": "Paragraph",
                "label": "Fraud [10]",
                "case_id": "case:fraud",
                "paragraph_span": "[10]",
                "public_excerpt": "Fraud by deception requires dishonest intent and a false representation to obtain property or pecuniary advantage.",
                "hklii_deep_link": "https://example.com#p10",
            },
            {
                "id": "proposition:fraud",
                "type": "Proposition",
                "label": "Fraud elements",
                "label_en": "Elements of fraud by deception",
                "statement_en": "Fraud by deception requires dishonest intent and a false representation to obtain property or pecuniary advantage.",
            },
        ],
        "edges": [
            {"source": "paragraph:fraud", "target": "case:fraud", "type": "PART_OF", "weight": 1.0},
            {"source": "paragraph:fraud", "target": "proposition:fraud", "type": "SUPPORTS", "weight": 1.0},
        ],
        "case_cards": {},
    }
    store = HybridGraphStore(bundle)
    classification = DeterminatorPipeline()._classify("what are the elements of fraud")
    result = store.query(
        "what are the elements of fraud",
        top_k=5,
        mode="extractive",
        max_citations=8,
        classification_area=classification["area"],
        offence_keywords=classification["criminal_hits"],
    )
    # The sexual offence case must NOT appear in citations
    cited_names = [c["case_name"] for c in result["citations"]]
    assert "R v Wong" not in cited_names


def test_score_cliff_detector_truncates_noise_citations(monkeypatch):
    """When top citation scores 0.50 and later ones score <0.15 (below
    30% cliff), the low-scoring citations should be dropped."""
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
                "id": "case:strong",
                "type": "Case",
                "label": "Strong Case",
                "case_name": "HKSAR v Li",
                "summary_en": "The defendant was convicted of theft of property from a retail store under the Theft Ordinance.",
                "topic_paths": ["Property and Dishonesty Offences/Theft"],
                "offence_family": "theft",
                "authority_score": 0.8,
            },
            {
                "id": "paragraph:strong",
                "type": "Paragraph",
                "label": "Strong [5]",
                "case_id": "case:strong",
                "paragraph_span": "[5]",
                "public_excerpt": "Theft requires dishonest appropriation of property belonging to another with intention to permanently deprive.",
                "hklii_deep_link": "https://example.com#p5",
            },
            {
                "id": "proposition:strong",
                "type": "Proposition",
                "label": "Theft elements",
                "label_en": "Elements of theft under Cap 210",
                "statement_en": "Theft requires dishonest appropriation of property belonging to another with intention to permanently deprive.",
            },
            {
                "id": "case:noise",
                "type": "Case",
                "label": "Noise Case",
                "case_name": "HKSAR v Unrelated",
                "summary_en": "The court considered general principles of criminal liability in this unrelated public order matter.",
                "topic_paths": ["Public Order Offences"],
                "offence_family": "public_order",
                "authority_score": 0.3,
            },
        ],
        "edges": [
            {"source": "paragraph:strong", "target": "case:strong", "type": "PART_OF", "weight": 1.0},
            {"source": "paragraph:strong", "target": "proposition:strong", "type": "SUPPORTS", "weight": 1.0},
        ],
        "case_cards": {},
    }
    store = HybridGraphStore(bundle)
    classification = DeterminatorPipeline()._classify("what is the penalty for theft")
    result = store.query(
        "what is the penalty for theft",
        top_k=5,
        mode="extractive",
        max_citations=8,
        classification_area=classification["area"],
        offence_keywords=classification["criminal_hits"],
    )
    cited_names = [c["case_name"] for c in result["citations"]]
    # The noise case should not appear
    assert "HKSAR v Unrelated" not in cited_names


def test_localhash_semantic_boost_disabled():
    """LocalHash backend should NOT be used for semantic scoring."""
    from casemap.embeddings import HashEmbeddingBackend
    bundle = {
        "meta": {"title": "Test", "legal_domain": "criminal"},
        "tree": {"id": "tree", "label_en": "Tree", "label_zh": "", "modules": []},
        "nodes": [],
        "edges": [],
        "case_cards": {},
    }
    store = HybridGraphStore(bundle)
    assert isinstance(store._embedding_backend, HashEmbeddingBackend)
    assert store._use_semantic_boost is False
