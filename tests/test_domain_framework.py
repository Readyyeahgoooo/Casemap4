#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import casemap.batch_enrich as batch_enrich
import casemap.domain_graph as domain_graph
from casemap.hklii_crawler import HKLIICaseDocument, HKLIIParagraph, HKLIISearchResult


def _family_tree() -> dict:
    return {
        "id": "authority_tree:hk_family_law",
        "domain_id": "family",
        "label_en": "Hong Kong Family Law",
        "summary_en": "Family-law tree for custody and children matters.",
        "modules": [
            {
                "id": "children",
                "label_en": "Children",
                "summary_en": "Children and custody matters.",
                "subgrounds": [
                    {
                        "id": "custody",
                        "label_en": "Custody",
                        "summary_en": "Custody and care arrangements.",
                        "topics": [
                            {
                                "id": "child_custody",
                                "label_en": "Child Custody",
                                "summary_en": "Custody disputes and welfare principles.",
                                "search_queries": ["child custody welfare"],
                            }
                        ],
                    }
                ],
            }
        ],
    }


class FakeFamilyCrawler:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.max_workers = 2

    def simple_search(self, query: str, limit: int = 10) -> list[HKLIISearchResult]:
        if "custody" not in query.lower():
            return []
        return [
            HKLIISearchResult(
                title="Re Child A",
                subtitle="Family Court",
                path="/en/cases/hkfc/2024/1",
                db="Hong Kong Family Court",
            )
        ][:limit]

    def crawl_paths(self, public_paths: list[str]) -> list[HKLIICaseDocument]:
        return [
            HKLIICaseDocument(
                case_name="Re Child A",
                court_name="Hong Kong Family Court",
                neutral_citation="[2024] HKFC 1",
                decision_date="2024-01-15",
                court_code="HKFC",
                public_url="https://www.hklii.hk/en/cases/hkfc/2024/1",
                raw_html="",
                paragraphs=[
                    HKLIIParagraph(
                        paragraph_span="para 1",
                        text=(
                            "The court considered child custody, welfare, care and control, "
                            "and the best interests of the child."
                        ),
                    )
                ],
            )
            for _path in public_paths
        ]


def test_build_domain_graph_uses_domain_id_for_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(domain_graph, "HKLIICrawler", FakeFamilyCrawler)

    output_dir = tmp_path / "family_relationship"
    manifest = domain_graph.build_domain_graph_artifacts(
        domain_id="family",
        tree=_family_tree(),
        source_paths=[],
        relationship_output_dir=output_dir,
        max_cases=1,
        per_query_limit=1,
        embedding_backend="local-hash",
    )

    payload = json.loads((output_dir / "relationship_graph.json").read_text(encoding="utf-8"))
    chroma = json.loads((output_dir / "chroma_records.json").read_text(encoding="utf-8"))

    assert manifest["legal_domain"] == "family"
    assert payload["meta"]["legal_domain"] == "family"
    assert chroma["collection"] == "hk_family_cases"
    assert any(
        node["type"] == "case" and node["label"] == "Re Child A" and node["legal_domain"] == "family"
        for node in payload["nodes"]
    )


def test_cross_domain_registry_helpers_preserve_secondary_domains(tmp_path):
    candidate = {
        "neutral_citation": "[2024] HKCFI 123",
        "case_name": "Example Ltd v Director",
        "domain_classification": {
            "domain": "commercial",
            "secondary_domains": ["contract"],
            "confidence": 0.82,
        },
    }

    assert not batch_enrich._is_quarantined(candidate, target_domain="contract")
    assert not batch_enrich._is_classified_non_target(candidate, target_domain="contract")
    assert batch_enrich._is_quarantined(candidate, target_domain="criminal")

    topic = {"id": "sale_of_goods", "label_en": "Sale of Goods"}
    assert batch_enrich._add_cross_reference(
        candidate,
        domain_id="contract",
        module_id="commercial_contracts",
        subground_id="sale",
        topic=topic,
        query="sale of goods",
    )
    assert not batch_enrich._add_cross_reference(
        candidate,
        domain_id="contract",
        module_id="commercial_contracts",
        subground_id="sale",
        topic=topic,
        query="sale of goods",
    )

    output_path = tmp_path / "candidates.json"
    batch_enrich._save_candidates([candidate], {"target_domain": "contract"}, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["meta"]["neutral_citation_index"] == {"[2024] HKCFI 123": 0}
    assert payload["candidates"][0]["cross_references"][0]["domain"] == "contract"
