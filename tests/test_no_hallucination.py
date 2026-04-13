from __future__ import annotations

import casemap.hybrid_graph as hybrid_graph
from casemap.hybrid_graph import validate_grounded_answer


def test_unknown_citations_and_cases_are_logged(monkeypatch):
    logged = []

    def fake_append(entries, path=None):
        logged.extend(entries)

    monkeypatch.setattr(hybrid_graph, "append_hallucination_log", fake_append)

    warnings, entries = validate_grounded_answer(
        "The answer cites [C9] and Imaginary v HKSAR.",
        allowed_citation_ids={"C1"},
        allowed_case_names={"Real v HKSAR"},
    )

    assert warnings
    assert entries
    assert logged
    assert any(entry["type"] == "unknown_citation_marker" for entry in logged)
    assert any(entry["type"] == "unknown_case_name" for entry in logged)
