from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
import json
import os
import re

from .graphrag import slugify, tokenize

DISCOVERED_LINEAGES_DEFAULT_PATH = Path("data") / "batch" / "discovered_lineages.json"
HALLUCINATION_LOG_DEFAULT_PATH = Path("data") / "batch" / "hallucination_log.json"

_DISCOVER_LINEAGE_PROMPT = """You are organizing a Hong Kong legal knowledge graph.

You will receive ONE legal topic, existing cases/statutes already in the graph, and existing graph edges.
Identify doctrine evolution chains only from the supplied authorities.

Rules:
- Do not invent cases, statutes, citations, or principles.
- Use only labels that appear in the supplied authorities.
- Return at most 3 lineages.
- Each lineage must have at least 3 authorities.
- Prefer Hong Kong authorities where possible.
- Use codes only from: ORIG, FLLW, APPD, DIST, DPRT, CODI.

Return strict JSON:
{{
  "lineages": [
    {{
      "title": "short lineage title",
      "topic_hints": ["topic words"],
      "cases": [
        {{"label": "exact supplied label", "code": "ORIG", "treatment": "originating authority", "note": "short paraphrase"}},
        {{"label": "exact supplied label", "code": "FLLW", "treatment": "followed", "note": "short paraphrase"}}
      ],
      "edges": [
        {{"from": "exact supplied label", "to": "exact supplied label", "code": "FLLW", "label": "short edge label"}}
      ]
    }}
  ]
}}

Topic:
{topic}

Authorities:
{authorities}

Existing edges:
{edges}

JSON only:"""


def _extract_json_payload(raw_text: str):
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw_text or ""):
        if char not in "[{":
            continue
        try:
            payload, _end = decoder.raw_decode(raw_text[index:])
            return payload
        except json.JSONDecodeError:
            continue
    return None


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _lineage_member_labels(lineage: dict) -> set[str]:
    raw_members = lineage.get("cases", lineage.get("members", []))
    return {
        _normalize_label(str(member.get("label", "")))
        for member in raw_members
        if isinstance(member, dict) and member.get("label")
    }


def _is_duplicate_lineage(candidate: dict, existing_lineages: list[dict], threshold: float = 0.6) -> bool:
    candidate_labels = _lineage_member_labels(candidate)
    if not candidate_labels:
        return True
    for existing in existing_lineages:
        existing_labels = _lineage_member_labels(existing)
        if not existing_labels:
            continue
        overlap = len(candidate_labels & existing_labels) / max(len(candidate_labels), 1)
        if overlap >= threshold:
            return True
    return False


def _call_deepseek(prompt: str, *, timeout: int = 120) -> str:
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if deepseek_key:
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        api_key = deepseek_key
        model = "deepseek-chat"
    elif openrouter_key:
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        api_key = openrouter_key
        model = os.environ.get("OPENROUTER_MODEL", "").strip() or "deepseek/deepseek-chat"
    else:
        raise RuntimeError("No DEEPSEEK_API_KEY or OPENROUTER_API_KEY configured.")

    request = urllib_request.Request(
        endpoint,
        data=json.dumps(
            {
                "model": model,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "ignore")
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"Lineage discovery HTTP {exc.code}: {body[:240]}") from exc
    parsed = json.loads(raw)
    choices = parsed.get("choices", [])
    if not choices:
        raise RuntimeError("Lineage discovery returned no choices.")
    return str(choices[0].get("message", {}).get("content", ""))


def load_discovered_lineages(path: str | Path | None = None) -> list[dict]:
    lineage_path = Path(path or DISCOVERED_LINEAGES_DEFAULT_PATH)
    if not lineage_path.exists():
        return []
    try:
        payload = json.loads(lineage_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [item for item in payload.get("lineages", []) if isinstance(item, dict)]
    return []


def _payload_legal_domain(payload: dict, fallback: str = "") -> str:
    return str(payload.get("meta", {}).get("legal_domain") or fallback or "").strip().lower()


def _case_authorities_for_topic(payload: dict) -> tuple[dict[str, dict], dict[str, list[dict]], list[dict]]:
    nodes = {node["id"]: node for node in payload.get("nodes", [])}
    topic_cases: defaultdict[str, list[dict]] = defaultdict(list)
    relevant_edges: list[dict] = []
    for edge in payload.get("edges", []):
        source = nodes.get(edge.get("source"))
        target = nodes.get(edge.get("target"))
        edge_type = edge.get("type")
        if not source or not target:
            continue
        if source.get("type") in {"topic", "Topic"} and target.get("type") in {"case", "Case", "statute", "Statute"}:
            if edge_type in {"discusses_case", "lineage_case", "domain_case", "discusses_statute", "lineage_statute", "domain_statute"}:
                topic_cases[source["id"]].append(target)
        elif target.get("type") in {"topic", "Topic"} and source.get("type") in {"case", "Case", "statute", "Statute"}:
            if edge_type == "BELONGS_TO_TOPIC":
                topic_cases[target["id"]].append(source)
        if source.get("type") in {"case", "Case"} and target.get("type") in {"case", "Case"}:
            relevant_edges.append(edge)
    topics = {node_id: node for node_id, node in nodes.items() if node.get("type") in {"topic", "Topic"}}
    return topics, topic_cases, relevant_edges


def _authority_type_from_node(node: dict) -> str:
    node_type = str(node.get("type", "")).lower()
    return "statute" if node_type == "statute" else "case"


def _validate_discovered_lineage(
    raw_lineage: dict,
    *,
    topic: dict,
    authority_lookup: dict[str, dict],
    domain_id: str,
    now: str,
) -> dict | None:
    title = str(raw_lineage.get("title", "")).strip()
    raw_members = raw_lineage.get("cases", raw_lineage.get("members", []))
    if not title or not isinstance(raw_members, list):
        return None
    members: list[dict] = []
    seen_labels: set[str] = set()
    for raw_member in raw_members:
        if not isinstance(raw_member, dict):
            continue
        normalized = _normalize_label(str(raw_member.get("label", "")))
        matched = authority_lookup.get(normalized)
        if not matched or normalized in seen_labels:
            continue
        seen_labels.add(normalized)
        members.append(
            {
                "label": matched["label"],
                "type": _authority_type_from_node(matched),
                "code": str(raw_member.get("code", "APPD")).strip().upper() or "APPD",
                "treatment": str(raw_member.get("treatment", "relevant authority")).strip() or "relevant authority",
                "note": str(raw_member.get("note", "")).strip(),
            }
        )
    if len(members) < 3:
        return None

    member_labels = {member["label"] for member in members}
    edges: list[dict] = []
    for raw_edge in raw_lineage.get("edges", []):
        if not isinstance(raw_edge, dict):
            continue
        from_label = authority_lookup.get(_normalize_label(str(raw_edge.get("from", ""))), {}).get("label", "")
        to_label = authority_lookup.get(_normalize_label(str(raw_edge.get("to", ""))), {}).get("label", "")
        if from_label in member_labels and to_label in member_labels and from_label != to_label:
            edges.append(
                {
                    "from": from_label,
                    "to": to_label,
                    "code": str(raw_edge.get("code", "APPD")).strip().upper() or "APPD",
                    "label": str(raw_edge.get("label", "")).strip(),
                }
            )

    confidence_score = min(0.92, 0.45 + (0.08 * len(members)) + (0.03 * len(edges)))
    return {
        "id": f"auto_{slugify(domain_id or 'domain')}_{slugify(topic.get('label', topic.get('label_en', title)))[:32]}_{slugify(title)[:36]}",
        "title": title,
        "topic_hints": raw_lineage.get("topic_hints") or [topic.get("label", topic.get("label_en", ""))],
        "topic_ids": [topic["id"]],
        "topic_labels": [topic.get("label", topic.get("label_en", topic["id"]))],
        "cases": members,
        "edges": edges,
        "source": "auto",
        "domain_tags": [domain_id] if domain_id else [],
        "confidence_status": "established" if confidence_score >= 0.75 and len(members) >= 4 else "preliminary",
        "confidence_score": round(confidence_score, 3),
        "created_at": now,
        "last_updated": now,
        "discovery_rounds": [{"at": now, "topic_id": topic["id"], "member_count": len(members)}],
    }


def discover_lineages_from_payload(
    payload: dict,
    *,
    domain_id: str = "",
    output_path: str | Path | None = None,
    existing_lineages: list[dict] | None = None,
    llm_call=None,
    max_topics: int | None = None,
) -> dict:
    """Ask an LLM to organize existing graph authorities into lineages."""
    normalized_domain = _payload_legal_domain(payload, fallback=domain_id)
    topics, topic_cases, graph_edges = _case_authorities_for_topic(payload)
    llm = llm_call or _call_deepseek
    existing = list(existing_lineages or []) + load_discovered_lineages(output_path)
    now = datetime.now(UTC).isoformat()
    discovered: list[dict] = []
    rejected: list[dict] = []
    processed_topics = 0

    ranked_topics = sorted(
        topics.values(),
        key=lambda topic: len(topic_cases.get(topic["id"], [])),
        reverse=True,
    )
    for topic in ranked_topics:
        authorities = topic_cases.get(topic["id"], [])
        if len(authorities) < 4:
            continue
        if max_topics is not None and processed_topics >= max_topics:
            break
        processed_topics += 1

        authority_lookup = {_normalize_label(node.get("label", node.get("case_name", ""))): node for node in authorities}
        authority_lines = []
        for node in authorities[:80]:
            label = node.get("label", node.get("case_name", ""))
            citation = node.get("neutral_citation", "")
            summary = node.get("summary") or node.get("summary_en", "")
            authority_lines.append(f"- {label} {citation}: {summary[:220]}")
        edge_lines = []
        authority_ids = {node["id"] for node in authorities}
        for edge in graph_edges:
            if edge.get("source") in authority_ids and edge.get("target") in authority_ids:
                source = next((node for node in authorities if node["id"] == edge.get("source")), {})
                target = next((node for node in authorities if node["id"] == edge.get("target")), {})
                edge_lines.append(f"- {source.get('label', '')} -> {target.get('label', '')}: {edge.get('type', '')}")

        prompt = _DISCOVER_LINEAGE_PROMPT.format(
            topic=topic.get("label", topic.get("label_en", topic["id"])),
            authorities="\n".join(authority_lines[:80]),
            edges="\n".join(edge_lines[:60]) or "(none supplied)",
        )
        try:
            content = llm(prompt)
        except Exception as exc:
            rejected.append({"topic_id": topic["id"], "reason": f"llm_error: {exc}"})
            continue
        parsed = _extract_json_payload(content)
        raw_lineages = parsed.get("lineages", []) if isinstance(parsed, dict) else parsed if isinstance(parsed, list) else []
        for raw_lineage in raw_lineages[:3]:
            if not isinstance(raw_lineage, dict):
                continue
            lineage = _validate_discovered_lineage(
                raw_lineage,
                topic=topic,
                authority_lookup=authority_lookup,
                domain_id=normalized_domain,
                now=now,
            )
            if not lineage:
                rejected.append({"topic_id": topic["id"], "reason": "invalid_or_unresolved_lineage", "raw": raw_lineage})
                continue
            if _is_duplicate_lineage(lineage, existing + discovered):
                rejected.append({"topic_id": topic["id"], "reason": "duplicate_lineage", "lineage_id": lineage["id"]})
                continue
            discovered.append(lineage)

    merged = existing + discovered
    result = {
        "meta": {
            "generated_at": now,
            "legal_domain": normalized_domain,
            "processed_topic_count": processed_topics,
            "discovered_count": len(discovered),
            "total_count": len(merged),
            "rejected_count": len(rejected),
        },
        "lineages": merged,
        "rejected": rejected,
    }
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def discover_lineages_from_file(
    graph_path: str | Path,
    *,
    domain_id: str = "",
    output_path: str | Path = DISCOVERED_LINEAGES_DEFAULT_PATH,
    max_topics: int | None = None,
) -> dict:
    payload = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    return discover_lineages_from_payload(
        payload,
        domain_id=domain_id,
        output_path=output_path,
        max_topics=max_topics,
    )


def append_hallucination_log(entries: list[dict], path: str | Path | None = None) -> None:
    if not entries:
        return
    log_path = Path(path or HALLUCINATION_LOG_DEFAULT_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload: list[dict] = []
    if log_path.exists():
        try:
            existing = json.loads(log_path.read_text(encoding="utf-8"))
            if isinstance(existing, list):
                payload = existing
        except (json.JSONDecodeError, OSError):
            payload = []
    timestamp = datetime.now(UTC).isoformat()
    payload.extend({**entry, "logged_at": timestamp} for entry in entries)
    log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
