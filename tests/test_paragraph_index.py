from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from casemap.hklii_crawler import HKLIICaseDocument, HKLIIParagraph, HKLIIReference
from casemap.paragraph_index import build_paragraph_index, search_paragraph_index


class _FakeCrawler:
    warnings: list[str] = []

    def fetch_case_document(self, public_path: str) -> HKLIICaseDocument:
        return HKLIICaseDocument(
            case_name="HKSAR v Test Defendant",
            court_name="Court of Appeal",
            neutral_citation="[2024] HKCA 123",
            decision_date="2024-01-02",
            court_code="HKCA",
            public_url=f"https://www.hklii.hk{public_path}",
            raw_html="",
            paragraphs=[
                HKLIIParagraph("para 1", "The court explains the mens rea for assault and criminal liability in Hong Kong."),
                HKLIIParagraph(
                    "para 2",
                    "Sentencing depends on culpability, harm, mitigation, aggravating features, pleas, and the applicable statutory maximum.",
                ),
            ],
            judges=["Example JA"],
            cited_cases=[HKLIIReference("HKSAR v Authority", "https://www.hklii.hk/en/cases/hkca/2020/1", "case")],
            cited_statutes=[HKLIIReference("Offences against the Person Ordinance", "https://www.hklii.hk/en/legis/ord/212", "statute")],
            title="HKSAR v Test Defendant [2024] HKCA 123",
        )


class ParagraphIndexTests(unittest.TestCase):
    def test_builds_resumable_paragraph_index_and_searches_precise_paragraphs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            graph_path = root / "relationship_graph.json"
            output_dir = root / "index"
            graph_path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {"id": "topic:mens_rea", "type": "topic", "label": "Mens rea"},
                            {
                                "id": "case:test",
                                "type": "case",
                                "label": "HKSAR v Test Defendant",
                                "neutral_citation": "[2024] HKCA 123",
                                "court_code": "HKCA",
                                "links": [{"url": "https://www.hklii.hk/en/cases/hkca/2024/123"}],
                                "principles": [{"statement_en": "Mens rea must be proved for the offence."}],
                            },
                        ],
                        "edges": [{"source": "topic:mens_rea", "target": "case:test", "type": "discusses_case"}],
                    }
                ),
                encoding="utf-8",
            )

            result = build_paragraph_index(
                graph_path=graph_path,
                output_dir=output_dir,
                max_cases=10,
                embedding_backend="local-hash",
                reset=True,
                crawler=_FakeCrawler(),
            )

            self.assertEqual(result.manifest["new_case_count"], 1)
            self.assertEqual(result.manifest["indexed_paragraph_count"], 2)
            self.assertTrue((output_dir / "paragraph_index_state.json").exists())
            self.assertTrue((output_dir / "paragraph_chroma_records.json").exists())

            search = search_paragraph_index(
                index_path=output_dir / "paragraph_chroma_records.json",
                question="mens rea assault criminal liability",
                top_k=1,
            )
            self.assertEqual(search["result_count"], 1)
            self.assertIn("mens rea", search["results"][0]["document"].lower())
            self.assertEqual(search["results"][0]["metadata"]["paragraph_span"], "para 1")

            resumed = build_paragraph_index(
                graph_path=graph_path,
                output_dir=output_dir,
                max_cases=10,
                embedding_backend="local-hash",
                crawler=_FakeCrawler(),
            )
            self.assertEqual(resumed.manifest["new_case_count"], 0)
            self.assertEqual(resumed.manifest["indexed_paragraph_count"], 2)


if __name__ == "__main__":
    unittest.main()
