from __future__ import annotations

import json

from casemap.lineage_discovery import discover_lineages_from_payload


def test_discover_lineages_rejects_unresolved_members(tmp_path):
    payload = {
        "meta": {"legal_domain": "criminal"},
        "nodes": [
            {"id": "topic:provocation", "type": "topic", "label": "Provocation"},
            {"id": "case:a", "type": "case", "label": "A v HKSAR", "summary": "Provocation origin."},
            {"id": "case:b", "type": "case", "label": "B v HKSAR", "summary": "Followed provocation."},
            {"id": "case:c", "type": "case", "label": "C v HKSAR", "summary": "Applied provocation."},
            {"id": "case:d", "type": "case", "label": "D v HKSAR", "summary": "Distinguished provocation."},
        ],
        "edges": [
            {"source": "topic:provocation", "target": "case:a", "type": "discusses_case"},
            {"source": "topic:provocation", "target": "case:b", "type": "discusses_case"},
            {"source": "topic:provocation", "target": "case:c", "type": "discusses_case"},
            {"source": "topic:provocation", "target": "case:d", "type": "discusses_case"},
        ],
    }

    def fake_llm(_prompt: str) -> str:
        return json.dumps(
            {
                "lineages": [
                    {
                        "title": "Provocation chain",
                        "topic_hints": ["provocation"],
                        "cases": [
                            {"label": "A v HKSAR", "code": "ORIG", "treatment": "originating"},
                            {"label": "B v HKSAR", "code": "FLLW", "treatment": "followed"},
                            {"label": "Imaginary v HKSAR", "code": "APPD", "treatment": "invented"},
                            {"label": "C v HKSAR", "code": "APPD", "treatment": "applied"},
                        ],
                    }
                ]
            }
        )

    result = discover_lineages_from_payload(
        payload,
        domain_id="criminal",
        output_path=tmp_path / "discovered_lineages.json",
        llm_call=fake_llm,
    )

    assert result["meta"]["discovered_count"] == 1
    lineage = result["lineages"][0]
    assert lineage["source"] == "auto"
    assert lineage["topic_ids"] == ["topic:provocation"]
    assert [member["label"] for member in lineage["cases"]] == ["A v HKSAR", "B v HKSAR", "C v HKSAR"]
    assert all(member["label"] != "Imaginary v HKSAR" for member in lineage["cases"])
