#!/usr/bin/env python3
"""Golden-label regression tests for retrieval accuracy.

Each test case specifies:
  - query: the user question
  - expected_topics: topic labels that MUST appear in matched_node_ids
  - expected_cases: substrings of case_name that MUST appear in top citations
  - forbidden_cases: case_name substrings that must NOT appear in top-3 citations
  - min_citations: minimum number of citations returned

Run:  PYTHONPATH=src python3 -m pytest tests/test_golden_retrieval.py -v
"""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import casemap.hybrid_graph as hg
from casemap.hybrid_graph import HybridGraphStore, DeterminatorPipeline

# Disable live HKLII to test local graph ranking only
_orig_live = hg._live_hklii_grounding
hg._live_hklii_grounding = lambda *a, **kw: {
    "citations": [], "sources": [], "warnings": [], "search_trace": []
}

GRAPH_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "hk_criminal_hybrid_v2" / "hierarchical_graph.json"

_store = None
_pipeline = None


def get_store():
    global _store
    if _store is None:
        if not GRAPH_PATH.exists():
            raise FileNotFoundError(f"Graph not found: {GRAPH_PATH}")
        _store = HybridGraphStore.from_file(str(GRAPH_PATH))
    return _store


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = DeterminatorPipeline()
    return _pipeline


def _run_query(query: str):
    store = get_store()
    pipeline = get_pipeline()
    cl = pipeline._classify(query)
    return store.query(
        query, top_k=5, mode="extractive",
        classification_area=cl["area"],
        offence_keywords=cl.get("criminal_hits", []),
    ), cl


# ──────────────────────────────────────────────────────────────
# Golden test cases
# ──────────────────────────────────────────────────────────────

GOLDEN_CASES = [
    {
        "query": "What are the elements of theft?",
        "expected_topics": ["Theft"],
        "expected_cases": [],
        "forbidden_cases": ["rape", "consent", "intoxication"],
        "min_citations": 3,
    },
    {
        "query": "Stealing my friend jacket but returning to him",
        "expected_topics": ["Theft"],
        "expected_cases": [],
        "forbidden_cases": ["rape", "consent", "sexual"],
        "min_citations": 2,
    },
    {
        "query": "Is stabbing a dog a crime?",
        "expected_topics": [],
        "expected_cases": ["Lam Wai Keung"],
        "forbidden_cases": [],
        "min_citations": 2,
    },
    {
        "query": "What happens if I stab someone?",
        "expected_topics": ["Assault"],
        "expected_cases": [],
        "forbidden_cases": ["cruelty", "animal", "Cap. 169"],
        "min_citations": 2,
    },
    {
        "query": "Can intoxication be a defence to a crime?",
        "expected_topics": ["Intoxication"],
        "expected_cases": [],
        "forbidden_cases": ["theft", "Theft Ordinance"],
        "min_citations": 2,
    },
    {
        "query": "USDT money laundering hong kong criminal",
        "expected_topics": ["Money Laundering"],
        "expected_cases": [],
        "forbidden_cases": ["rape", "consent", "animal"],
        "min_citations": 2,
    },
    {
        "query": "What is the sentence for murder in Hong Kong?",
        "expected_topics": ["Murder"],
        "expected_cases": [],
        "forbidden_cases": ["animal", "rape", "drug"],
        "min_citations": 3,
    },
    {
        "query": "What is the sentence for burglary?",
        "expected_topics": [],
        "expected_cases": [],
        "forbidden_cases": ["rape", "consent", "animal"],
        "min_citations": 3,
    },
    {
        "query": "Can I be charged for drug trafficking?",
        "expected_topics": [],
        "expected_cases": [],
        "forbidden_cases": ["rape", "consent", "animal"],
        "min_citations": 3,
    },
    {
        "query": "I stole my classmate phone",
        "expected_topics": ["Theft"],
        "expected_cases": [],
        "forbidden_cases": ["rape", "consent", "sexual"],
        "min_citations": 2,
    },
    {
        "query": "My friend robbed a store",
        "expected_topics": ["Robbery"],
        "expected_cases": [],
        "forbidden_cases": ["rape", "consent", "animal"],
        "min_citations": 2,
    },
]


def _topic_labels(result: dict, store: HybridGraphStore) -> list[str]:
    labels = []
    for nid in result["retrieval_trace"].get("matched_node_ids", [])[:8]:
        node = store.nodes.get(nid, {})
        if node.get("type") == "Topic":
            labels.append(node.get("label_en", node.get("label", "")))
    return labels


class TestGoldenRetrieval:
    """Regression tests that fail the build if retrieval quality drifts."""

    def _run_golden(self, case):
        store = get_store()
        result, cl = _run_query(case["query"])
        citations = result.get("citations", [])
        topic_labels = _topic_labels(result, store)
        errors = []

        # Check minimum citations
        if len(citations) < case["min_citations"]:
            errors.append(
                f"Expected >= {case['min_citations']} citations, got {len(citations)}"
            )

        # Check expected topics appear in matched nodes
        for expected in case.get("expected_topics", []):
            if not any(expected.lower() in label.lower() for label in topic_labels):
                errors.append(
                    f"Expected topic '{expected}' not found in matched topics: {topic_labels}"
                )

        # Check expected case substrings in top citations
        top_case_names = " ".join(c.get("case_name", "") for c in citations[:5])
        top_labels = " ".join(c.get("principle_label", "") for c in citations[:5])
        top_combined = (top_case_names + " " + top_labels).lower()
        for expected in case.get("expected_cases", []):
            if expected.lower() not in top_combined:
                errors.append(
                    f"Expected case substring '{expected}' not in top-5 citations: {top_case_names[:200]}"
                )

        # Check forbidden cases NOT in top-3
        top3_text = " ".join(
            f"{c.get('case_name', '')} {c.get('principle_label', '')} {c.get('quote', '')[:200]}"
            for c in citations[:3]
        ).lower()
        for forbidden in case.get("forbidden_cases", []):
            if forbidden.lower() in top3_text:
                errors.append(
                    f"Forbidden case/topic '{forbidden}' appeared in top-3 citations"
                )

        return errors

    def test_theft_elements(self):
        assert not self._run_golden(GOLDEN_CASES[0])

    def test_stealing_jacket(self):
        assert not self._run_golden(GOLDEN_CASES[1])

    def test_stabbing_dog(self):
        assert not self._run_golden(GOLDEN_CASES[2])

    def test_stab_someone(self):
        assert not self._run_golden(GOLDEN_CASES[3])

    def test_intoxication_defence(self):
        assert not self._run_golden(GOLDEN_CASES[4])

    def test_usdt_laundering(self):
        assert not self._run_golden(GOLDEN_CASES[5])

    def test_murder_sentence(self):
        assert not self._run_golden(GOLDEN_CASES[6])

    def test_burglary_sentence(self):
        assert not self._run_golden(GOLDEN_CASES[7])

    def test_drug_trafficking(self):
        assert not self._run_golden(GOLDEN_CASES[8])

    def test_stole_phone(self):
        assert not self._run_golden(GOLDEN_CASES[9])

    def test_robbed_store(self):
        assert not self._run_golden(GOLDEN_CASES[10])


if __name__ == "__main__":
    # Quick standalone runner
    store = get_store()
    pipeline = get_pipeline()
    passed = 0
    failed = 0
    for i, case in enumerate(GOLDEN_CASES):
        result, cl = _run_query(case["query"])
        t = TestGoldenRetrieval()
        errors = t._run_golden(case)
        status = "PASS" if not errors else "FAIL"
        if errors:
            failed += 1
        else:
            passed += 1
        cites = result.get("citations", [])
        top2 = ", ".join(c["case_name"][:35] for c in cites[:2])
        print(f"  [{status}] {case['query'][:50]:50s} | top: {top2}")
        for err in errors:
            print(f"         ERROR: {err}")
    print(f"\n{passed}/{passed + failed} passed")
    hg._live_hklii_grounding = _orig_live
