from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote_plus
import json
import math
import re

from .authority_tree_data import CURATED_AUTHORITY_TREE
from .docx_parser import extract_paragraphs
from .graphrag import (
    CASE_RE,
    STATUTE_RE,
    extract_authorities,
    parse_sections,
    slugify,
    split_topic,
    tokenize,
    top_keywords,
)
from .lineage_data import CURATED_LINEAGES
from .source_parser import Passage, SourceDocument, load_source_document
from .viewer import render_relationship_family_tree, render_relationship_map, render_relationship_tree

CASE_SEARCH_TEMPLATE = 'https://www.google.com/search?q={query}'
CASE_NAME_CONNECTORS = {
    "&",
    "and",
    "co",
    "co.",
    "company",
    "contractors",
    "corp",
    "corporation",
    "de",
    "east",
    "far",
    "for",
    "ltd",
    "ltd.",
    "mbh",
    "nicholls",
    "of",
    "plc",
    "pty",
    "sa",
    "stahl",
    "stahag",
    "the",
    "und",
    "van",
    "von",
}


@dataclass
class TopicProfile:
    topic_id: str
    label: str
    domain_id: str
    domain_label: str
    summary: str
    token_set: set[str]


def _normalize_case_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip(" ,.;:")
    normalized = re.sub(r"\s+\(\d{4}\)$", "", normalized)
    tokens = normalized.split()
    v_index = next((index for index, token in enumerate(tokens) if token.lower().rstrip(".") == "v"), None)
    if v_index is None:
        return normalized

    def is_name_token(token: str) -> bool:
        cleaned = token.strip(" ,.;:()[]")
        if not cleaned:
            return False
        if cleaned.lower() in CASE_NAME_CONNECTORS:
            return True
        return bool(re.match(r"^[A-Z][A-Za-z0-9'&.\-]*$", cleaned))

    left: list[str] = []
    cursor = v_index - 1
    while cursor >= 0 and is_name_token(tokens[cursor]):
        left.append(tokens[cursor].strip(" ,.;:()[]"))
        cursor -= 1
    left.reverse()

    right: list[str] = []
    cursor = v_index + 1
    while cursor < len(tokens) and is_name_token(tokens[cursor]):
        right.append(tokens[cursor].strip(" ,.;:()[]"))
        cursor += 1

    if not left or not right:
        return normalized
    return " ".join(left + ["v"] + right).strip()


def _normalize_statute_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip(" ,.;:")
    normalized = re.sub(r"^(Under|under|Pursuant to|pursuant to)\s+", "", normalized)
    normalized = re.sub(r"^(The|the)\s+", "", normalized)
    return normalized


def _sentence_split(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _make_snippet(text: str, anchors: list[str], max_chars: int = 420) -> str:
    lowered = text.lower()
    for anchor in anchors:
        if not anchor:
            continue
        position = lowered.find(anchor.lower())
        if position == -1:
            continue
        start = max(position - (max_chars // 3), 0)
        end = min(start + max_chars, len(text))
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[: max_chars - 3] + "..." if len(compact) > max_chars else compact


def _build_taxonomy(taxonomy_docx_path: str | Path) -> tuple[list[dict], list[TopicProfile]]:
    paragraphs = extract_paragraphs(taxonomy_docx_path)
    sections = parse_sections(paragraphs)
    domains: list[dict] = []
    topics: list[TopicProfile] = []
    seen_domains: set[str] = set()

    for section in sections:
        if section.number < 1 or section.number > 11:
            continue
        domain_id = f"domain:{slugify(section.title)}"
        if domain_id in seen_domains:
            continue
        seen_domains.add(domain_id)
        section_summary = " ".join(section.paragraphs[:2]).strip()
        domains.append(
            {
                "id": domain_id,
                "label": section.title,
                "type": "domain",
                "summary": section_summary or section.title,
                "keywords": top_keywords(section.title + " " + section_summary),
            }
        )

        seen_topic_labels: set[str] = set()
        for index, paragraph in enumerate(section.paragraphs, start=1):
            title, body = split_topic(paragraph)
            cleaned_title = re.sub(r"\s+", " ", title).strip(" ,.;:")
            if cleaned_title.lower() in seen_topic_labels:
                continue
            if CASE_RE.search(cleaned_title) or STATUTE_RE.search(cleaned_title):
                continue
            if len(tokenize(cleaned_title)) < 1:
                continue
            seen_topic_labels.add(cleaned_title.lower())

            summary = body or paragraph
            token_set = set(tokenize(cleaned_title + " " + section.title + " " + summary))
            topics.append(
                TopicProfile(
                    topic_id=f"topic:{slugify(section.title)}:{index:02d}:{slugify(cleaned_title)[:36]}",
                    label=cleaned_title,
                    domain_id=domain_id,
                    domain_label=section.title,
                    summary=summary[:500],
                    token_set=token_set,
                )
            )
    return domains, topics


def _topic_scores(text: str, topics: list[TopicProfile]) -> list[tuple[TopicProfile, float]]:
    token_set = set(tokenize(text))
    if not token_set:
        return []

    scored: list[tuple[TopicProfile, float]] = []
    lowered = text.lower()
    for topic in topics:
        overlap = token_set & topic.token_set
        lexical = len(overlap) / max(math.sqrt(len(token_set) * len(topic.token_set)), 1)
        if topic.label.lower() in lowered:
            lexical += 0.85
        if topic.domain_label.lower() in lowered:
            lexical += 0.18
        if lexical >= 0.12:
            scored.append((topic, lexical))
    return sorted(scored, key=lambda item: item[1], reverse=True)[:3]


def _select_references(references: list[dict], limit: int = 6) -> list[dict]:
    selected: list[dict] = []
    seen_sources: set[tuple[str, str]] = set()
    for reference in sorted(references, key=lambda item: item["score"], reverse=True):
        key = (reference["source_id"], reference["location"])
        if key in seen_sources:
            continue
        payload = dict(reference)
        payload.pop("score", None)
        selected.append(payload)
        seen_sources.add(key)
        if len(selected) >= limit:
            break
    return selected


def _summarize_authority(name: str, references: list[dict], fallback: str) -> str:
    candidates: list[str] = []
    ranked = sorted(
        references,
        key=lambda item: (item["score"], len(item["snippet"])),
        reverse=True,
    )
    for reference in ranked:
        for sentence in _sentence_split(reference["snippet"]):
            cleaned = sentence.strip()
            if len(cleaned) < 55:
                continue
            if cleaned.count(";") >= 2:
                continue
            if name.lower() in sentence.lower() or any(
                marker in sentence.lower()
                for marker in ("held", "held that", "principle", "applies", "means", "effective", "requires")
            ):
                candidates.append(cleaned)
        if len(candidates) >= 3:
            break

    if not candidates:
        return fallback

    unique_sentences: list[str] = []
    seen: set[str] = set()
    for sentence in candidates:
        normalized = sentence.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_sentences.append(sentence)
        if len(unique_sentences) >= 2:
            break
    summary = " ".join(unique_sentences).strip()
    return summary[:560] + "..." if len(summary) > 560 else summary


def _case_links(case_name: str) -> list[dict]:
    query = quote_plus(f'site:hklii.hk "{case_name}"')
    return [
        {
            "label": "Find on HKLII",
            "url": CASE_SEARCH_TEMPLATE.format(query=query),
        }
    ]


def _statute_links(statute_name: str) -> list[dict]:
    match = re.search(r"Cap\. (\d+[A-Z]?)", statute_name)
    if not match:
        return []
    cap_number = match.group(1).lower()
    return [
        {
            "label": "HKLII legislation",
            "url": f"https://hklii.hk/en/legis/ord/{cap_number}",
        }
    ]


def _write_relationship_payload(payload: dict, output_path: Path) -> dict:
    output_path.mkdir(parents=True, exist_ok=True)
    graph_file = output_path / "relationship_graph.json"
    viewer_file = output_path / "relationship_map.html"
    tree_file = output_path / "relationship_tree.html"
    manifest_file = output_path / "manifest.json"

    graph_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    viewer_file.write_text(render_relationship_map(payload), encoding="utf-8")
    tree_file.write_text(render_relationship_family_tree(payload), encoding="utf-8")
    manifest_file.write_text(json.dumps(payload["meta"], indent=2, ensure_ascii=False), encoding="utf-8")
    return payload["meta"]


def _infer_treatment_label(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in ("not adopted", "not adopt", "declined", "not followed", "rejected")):
        return "not adopted"
    if any(marker in lowered for marker in ("qualified", "distinguished", "limited", "refined")):
        return "qualified"
    if any(marker in lowered for marker in ("adopted", "followed", "applied", "affirmed", "accepted")):
        return "adopted"
    return "relevant authority"


def _build_public_case_profile(node: dict) -> dict:
    references = node.get("references", [])
    docx_reference = next((reference for reference in references if reference.get("source_kind") == "docx"), None)
    treatment_basis = ""
    if docx_reference:
        treatment_basis = docx_reference.get("snippet", "")
    elif node.get("summary"):
        treatment_basis = node["summary"]
    treatment = _infer_treatment_label(treatment_basis)
    quote = ""
    if docx_reference and docx_reference.get("snippet"):
        quote = docx_reference["snippet"]
    return {
        "treatment": treatment,
        "quote": quote,
    }


def _clean_public_source_label(value: str) -> str:
    cleaned = value.replace("_", " ").strip()
    cleaned = re.sub(r"\s*\(?(?:Z[- ]?Library)\)?\s*", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" -_,")


def _lineage_authority_type(label: str) -> str:
    lowered = label.lower()
    if "ordinance" in lowered or "(cap." in lowered:
        return "statute"
    return "case"


def _lineage_node_id(label: str, authority_type: str | None = None) -> str:
    node_type = authority_type or _lineage_authority_type(label)
    return f"{node_type}:{slugify(label)[:64]}"


def _match_lineage_topics(lineage: dict, topics: list[dict], domain_lookup: dict[str, dict]) -> list[dict]:
    scored: list[tuple[float, dict]] = []
    title_tokens = set(tokenize(lineage.get("title", "")))
    for topic in topics:
        haystack = f"{topic['label']} {topic.get('summary', '')}".lower()
        topic_tokens = set(tokenize(f"{topic['label']} {topic.get('summary', '')}"))
        domain_label = domain_lookup.get(topic.get("domain_id", ""), {}).get("label", "")
        domain_tokens = set(tokenize(domain_label))
        score = 0.0
        for hint in lineage.get("topic_hints", []):
            hint_tokens = set(tokenize(hint))
            if not hint_tokens:
                continue
            if hint.lower() in haystack:
                score += 2.4
            score += len(topic_tokens & hint_tokens) / max(len(hint_tokens), 1)
        if title_tokens:
            score += 0.15 * len(topic_tokens & title_tokens)
            score += 0.28 * len(domain_tokens & title_tokens)
        if score >= 1.0:
            scored.append((score, topic))

    if not scored:
        return []
    scored.sort(key=lambda item: (-item[0], item[1]["label"]))
    return [scored[0][1]]


def _append_unique_reference(references: list[dict], reference: dict) -> None:
    key = (
        reference["source_id"],
        reference["location"],
        reference.get("snippet", ""),
    )
    existing_keys = {
        (item["source_id"], item["location"], item.get("snippet", ""))
        for item in references
    }
    if key not in existing_keys:
        references.append(reference)


def _recompute_public_connectivity(public_payload: dict) -> None:
    node_lookup = {node["id"]: node for node in public_payload["nodes"]}
    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    valid_edges: list[dict] = []
    edge_keys: set[tuple[str, str, str, str, str]] = set()

    for edge in public_payload["edges"]:
        source = edge["source"]
        target = edge["target"]
        if source not in node_lookup or target not in node_lookup:
            continue
        key = (
            source,
            target,
            edge["type"],
            edge.get("lineage_id", ""),
            edge.get("code", ""),
        )
        if key in edge_keys:
            continue
        edge_keys.add(key)
        valid_edges.append(edge)
        adjacency[source].add(target)
        adjacency[target].add(source)

    public_payload["edges"] = valid_edges

    for node in public_payload["nodes"]:
        node["neighbors"] = sorted(adjacency.get(node["id"], set()))
        node["degree"] = len(node["neighbors"])

    meta = public_payload["meta"]
    meta["node_count"] = len(public_payload["nodes"])
    meta["edge_count"] = len(public_payload["edges"])
    meta["retained_case_count"] = sum(1 for node in public_payload["nodes"] if node["type"] == "case")
    meta["retained_statute_count"] = sum(1 for node in public_payload["nodes"] if node["type"] == "statute")
    meta["source_count"] = len(meta.get("source_documents", []))


def _augment_public_payload_with_lineages(public_payload: dict) -> None:
    node_lookup = {node["id"]: node for node in public_payload["nodes"]}
    topic_nodes = [node for node in public_payload["nodes"] if node["type"] == "topic"]
    domain_lookup = {
        node["id"]: node
        for node in public_payload["nodes"]
        if node["type"] == "domain"
    }
    source_node_id = "source:curated_authority_lineages"
    source_label = "Curated Authority Lineages"
    source_reference_label = "Curated lineage note"

    if source_node_id not in node_lookup:
        source_node = {
            "id": source_node_id,
            "label": source_label,
            "type": "source",
            "summary": "Curated Hong Kong and UK authority lineages used to structure stare decisis paths in the public tree.",
            "references": [],
            "links": [],
            "metrics": {"kind": "note"},
        }
        public_payload["nodes"].append(source_node)
        node_lookup[source_node_id] = source_node

    source_documents = public_payload["meta"].setdefault("source_documents", [])
    if not any(source.get("label") == source_label for source in source_documents):
        source_documents.append({"label": source_label, "kind": "note"})

    edge_keys = {
        (
            edge["source"],
            edge["target"],
            edge["type"],
            edge.get("lineage_id", ""),
            edge.get("code", ""),
        )
        for edge in public_payload["edges"]
    }

    def add_edge(source: str, target: str, edge_type: str, **extra: object) -> None:
        key = (source, target, edge_type, str(extra.get("lineage_id", "")), str(extra.get("code", "")))
        if source not in node_lookup or target not in node_lookup or key in edge_keys:
            return
        edge_keys.add(key)
        edge = {
            "source": source,
            "target": target,
            "type": edge_type,
            "weight": float(extra.pop("weight", 1.0)),
            "mentions": int(extra.pop("mentions", 1)),
        }
        edge.update(extra)
        public_payload["edges"].append(edge)

    meta_lineages: list[dict] = []
    for lineage in CURATED_LINEAGES:
        matched_topics = _match_lineage_topics(lineage, topic_nodes, domain_lookup)
        matched_topic_ids = [topic["id"] for topic in matched_topics]
        matched_topic_labels = [topic["label"] for topic in matched_topics]
        members: list[dict] = []

        for position, authority in enumerate(lineage["cases"], start=1):
            authority_type = _lineage_authority_type(authority["label"])
            node_id = _lineage_node_id(authority["label"], authority_type)
            node = node_lookup.get(node_id)
            default_summary = (
                f"Curated authority in the lineage '{lineage['title']}'. {authority.get('note', '')}".strip()
            )
            if authority_type == "statute":
                default_summary = (
                    f"Curated statutory authority in the lineage '{lineage['title']}'. {authority.get('note', '')}".strip()
                )

            if node is None:
                node = {
                    "id": node_id,
                    "label": authority["label"],
                    "type": authority_type,
                    "summary": default_summary,
                    "references": [],
                    "links": _statute_links(authority["label"]) if authority_type == "statute" else _case_links(authority["label"]),
                    "metrics": {"mentions": 0, "sources": 1},
                }
                if authority_type == "case":
                    node["case_profile"] = {
                        "treatment": authority.get("treatment", "relevant authority"),
                        "code": authority.get("code", ""),
                        "quote": authority.get("note", ""),
                        "note": authority.get("note", ""),
                    }
                public_payload["nodes"].append(node)
                node_lookup[node_id] = node
            else:
                if authority.get("note") and (
                    not node.get("summary")
                    or node["summary"].startswith("Case linked to")
                    or node["summary"].startswith("Statute linked to")
                ):
                    node["summary"] = default_summary
                if authority_type == "case":
                    profile = dict(node.get("case_profile", {}))
                    if authority.get("treatment") and (
                        profile.get("treatment") in {"", None, "relevant authority"}
                        or authority["treatment"] not in {"", "relevant authority"}
                    ):
                        profile["treatment"] = authority["treatment"]
                    if authority.get("code"):
                        profile["code"] = authority["code"]
                    if authority.get("note"):
                        profile.setdefault("note", authority["note"])
                        profile.setdefault("quote", authority["note"])
                    node["case_profile"] = profile
                if authority_type == "statute" and authority.get("note") and not node.get("references"):
                    node["summary"] = default_summary
                metrics = dict(node.get("metrics", {}))
                metrics["sources"] = max(int(metrics.get("sources", 0)), 1)
                node["metrics"] = metrics
                if authority_type == "case" and not node.get("links"):
                    node["links"] = _case_links(authority["label"])
                if authority_type == "statute" and not node.get("links"):
                    node["links"] = _statute_links(authority["label"])

            reference = {
                "source_id": source_node_id,
                "source_label": source_label,
                "source_kind": "note",
                "location": lineage["title"],
                "snippet": authority.get("note", source_reference_label),
            }
            _append_unique_reference(node.setdefault("references", []), reference)

            memberships = node.setdefault("lineage_memberships", [])
            if not any(item["lineage_id"] == lineage["id"] for item in memberships):
                memberships.append(
                    {
                        "lineage_id": lineage["id"],
                        "lineage_title": lineage["title"],
                        "position": position,
                        "code": authority.get("code", ""),
                        "treatment": authority.get("treatment", ""),
                        "note": authority.get("note", ""),
                        "topic_ids": matched_topic_ids,
                        "topic_labels": matched_topic_labels,
                    }
                )

            members.append(
                {
                    "node_id": node_id,
                    "label": authority["label"],
                    "type": authority_type,
                    "position": position,
                    "code": authority.get("code", ""),
                    "treatment": authority.get("treatment", ""),
                    "note": authority.get("note", ""),
                }
            )

            source_edge_type = "discusses_case" if authority_type == "case" else "discusses_statute"
            add_edge(
                source_node_id,
                node_id,
                source_edge_type,
                lineage_id=lineage["id"],
                code=authority.get("code", ""),
                label="curated lineage note",
            )
            for topic in matched_topics:
                add_edge(
                    topic["id"],
                    node_id,
                    "lineage_case" if authority_type == "case" else "lineage_statute",
                    lineage_id=lineage["id"],
                    lineage_title=lineage["title"],
                    code=authority.get("code", ""),
                    label=authority.get("treatment", "") or lineage["title"],
                )
                if topic.get("domain_id"):
                    add_edge(
                        topic["domain_id"],
                        node_id,
                        "domain_case" if authority_type == "case" else "domain_statute",
                        lineage_id=lineage["id"],
                        code=authority.get("code", ""),
                        label="curated lineage branch",
                    )

        for edge in lineage.get("edges", []):
            from_id = _lineage_node_id(edge["from"])
            to_id = _lineage_node_id(edge["to"])
            add_edge(
                from_id,
                to_id,
                "lineage_step",
                lineage_id=lineage["id"],
                lineage_title=lineage["title"],
                code=edge.get("code", ""),
                label=edge.get("label", ""),
            )

        meta_lineages.append(
            {
                "id": lineage["id"],
                "title": lineage["title"],
                "topic_ids": matched_topic_ids,
                "topic_labels": matched_topic_labels,
                "members": members,
                "codes": sorted({member["code"] for member in members if member.get("code")}),
            }
        )

    for node in public_payload["nodes"]:
        memberships = node.get("lineage_memberships", [])
        if memberships:
            memberships.sort(key=lambda item: (item["lineage_title"], item["position"], item["lineage_id"]))
            metrics = dict(node.get("metrics", {}))
            metrics["lineages"] = len({item["lineage_id"] for item in memberships})
            node["metrics"] = metrics

    notes = public_payload["meta"].setdefault("notes", [])
    lineage_note = "Curated lineage paths add Hong Kong and UK authority sequences with FLLW, APPD, DIST, and CODI edges."
    if lineage_note not in notes:
        notes.append(lineage_note)
    public_payload["meta"]["lineages"] = meta_lineages
    public_payload["meta"]["curated_lineage_count"] = len(meta_lineages)
    public_payload["meta"]["lineage_codes"] = {
        "CODI": "Codified by Hong Kong ordinance",
        "APPD": "Applied on the same principle",
        "FLLW": "Followed or adopted in Hong Kong",
        "DIST": "Distinguished or qualified",
        "DPRT": "Departed from prior authority",
        "ORIG": "Originating authority in the lineage",
    }
    _recompute_public_connectivity(public_payload)


def _normalized_public_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _resolve_curated_topic_ids(topic_labels: list[str], topic_nodes: list[dict]) -> list[str]:
    normalized_lookup: defaultdict[str, list[dict]] = defaultdict(list)
    token_lookup = {topic["id"]: set(tokenize(topic["label"])) for topic in topic_nodes}
    for topic in topic_nodes:
        normalized_lookup[_normalized_public_label(topic["label"])].append(topic)

    matched_ids: list[str] = []
    seen: set[str] = set()
    for label in topic_labels:
        normalized = _normalized_public_label(label)
        direct_matches = normalized_lookup.get(normalized, [])
        candidates = list(direct_matches)
        if not candidates and normalized:
            for topic in topic_nodes:
                topic_normalized = _normalized_public_label(topic["label"])
                if normalized in topic_normalized or topic_normalized in normalized:
                    candidates.append(topic)
        if not candidates:
            label_tokens = set(tokenize(label))
            scored: list[tuple[float, dict]] = []
            for topic in topic_nodes:
                overlap = label_tokens & token_lookup[topic["id"]]
                if not overlap:
                    continue
                score = len(overlap) / max(len(label_tokens | token_lookup[topic["id"]]), 1)
                if score >= 0.32:
                    scored.append((score, topic))
            candidates = [topic for _, topic in sorted(scored, key=lambda item: item[0], reverse=True)]

        if candidates:
            topic = candidates[0]
            if topic["id"] not in seen:
                seen.add(topic["id"])
                matched_ids.append(topic["id"])
    return matched_ids


def _augment_public_payload_with_authority_tree(public_payload: dict) -> None:
    node_lookup = {node["id"]: node for node in public_payload["nodes"]}
    topic_nodes = [node for node in public_payload["nodes"] if node["type"] == "topic"]
    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    for edge in public_payload["edges"]:
        adjacency[edge["source"]].add(edge["target"])
        adjacency[edge["target"]].add(edge["source"])

    lineage_lookup = {
        lineage["id"]: dict(lineage)
        for lineage in public_payload["meta"].get("lineages", [])
    }
    topic_lineages: defaultdict[str, set[str]] = defaultdict(set)
    for lineage in lineage_lookup.values():
        for topic_id in lineage.get("topic_ids", []):
            topic_lineages[topic_id].add(lineage["id"])

    modules: list[dict] = []
    module_index: dict[str, dict] = {}
    subground_index: dict[str, dict] = {}

    for module in CURATED_AUTHORITY_TREE:
        module_topics: set[str] = set()
        module_cases: set[str] = set()
        module_statutes: set[str] = set()
        module_sources: set[str] = set()
        module_lineages: set[str] = set()
        curated_subgrounds: list[dict] = []

        for subground in module.get("subgrounds", []):
            topic_ids = _resolve_curated_topic_ids(subground.get("topic_labels", []), topic_nodes)
            topic_labels = [node_lookup[topic_id]["label"] for topic_id in topic_ids if topic_id in node_lookup]
            lineage_ids = list(dict.fromkeys(subground.get("lineage_ids", [])))
            for topic_id in topic_ids:
                for lineage_id in sorted(topic_lineages.get(topic_id, set())):
                    if lineage_id not in lineage_ids:
                        lineage_ids.append(lineage_id)

            case_ids: set[str] = set()
            statute_ids: set[str] = set()
            source_ids: set[str] = set()
            for topic_id in topic_ids:
                for neighbor_id in adjacency.get(topic_id, set()):
                    neighbor = node_lookup.get(neighbor_id)
                    if not neighbor:
                        continue
                    if neighbor["type"] == "case":
                        case_ids.add(neighbor_id)
                    elif neighbor["type"] == "statute":
                        statute_ids.add(neighbor_id)
                    elif neighbor["type"] == "source":
                        source_ids.add(neighbor_id)

            for lineage_id in lineage_ids:
                lineage = lineage_lookup.get(lineage_id)
                if not lineage:
                    continue
                for member in lineage.get("members", []):
                    member_node = node_lookup.get(member["node_id"])
                    if not member_node:
                        continue
                    if member_node["type"] == "case":
                        case_ids.add(member_node["id"])
                    elif member_node["type"] == "statute":
                        statute_ids.add(member_node["id"])

            subground_payload = {
                "id": f"subground:{module['id']}:{subground['id']}",
                "module_id": f"module:{module['id']}",
                "slug": subground["id"],
                "type": "subground",
                "label_en": subground["label_en"],
                "label_zh": subground["label_zh"],
                "label": f"{subground['label_en']} / {subground['label_zh']}",
                "secondary_label": subground["label_zh"],
                "summary_en": subground["summary_en"],
                "summary_zh": subground["summary_zh"],
                "summary": subground["summary_en"],
                "children": list(subground.get("children", [])),
                "topic_ids": topic_ids,
                "topic_labels": topic_labels,
                "lineage_ids": [lineage_id for lineage_id in lineage_ids if lineage_id in lineage_lookup],
                "lineage_titles": [
                    lineage_lookup[lineage_id]["title"]
                    for lineage_id in lineage_ids
                    if lineage_id in lineage_lookup
                ],
                "case_ids": sorted(case_ids, key=lambda node_id: node_lookup[node_id]["label"]),
                "statute_ids": sorted(statute_ids, key=lambda node_id: node_lookup[node_id]["label"]),
                "source_ids": sorted(source_ids, key=lambda node_id: node_lookup[node_id]["label"]),
                "metrics": {
                    "topics": len(topic_ids),
                    "cases": len(case_ids),
                    "statutes": len(statute_ids),
                    "sources": len(source_ids),
                    "lineages": len([lineage_id for lineage_id in lineage_ids if lineage_id in lineage_lookup]),
                },
                "coverage": "mapped" if topic_ids or lineage_ids else "placeholder",
            }
            curated_subgrounds.append(subground_payload)
            subground_index[subground_payload["id"]] = subground_payload

            module_topics.update(topic_ids)
            module_cases.update(case_ids)
            module_statutes.update(statute_ids)
            module_sources.update(source_ids)
            module_lineages.update(subground_payload["lineage_ids"])

        module_payload = {
            "id": f"module:{module['id']}",
            "slug": module["id"],
            "type": "module",
            "label_en": module["label_en"],
            "label_zh": module["label_zh"],
            "label": f"{module['label_en']} / {module['label_zh']}",
            "secondary_label": module["label_zh"],
            "summary_en": module["summary_en"],
            "summary_zh": module["summary_zh"],
            "summary": module["summary_en"],
            "subgrounds": curated_subgrounds,
            "metrics": {
                "subgrounds": len(curated_subgrounds),
                "topics": len(module_topics),
                "cases": len(module_cases),
                "statutes": len(module_statutes),
                "sources": len(module_sources),
                "lineages": len(module_lineages),
            },
        }
        modules.append(module_payload)
        module_index[module_payload["id"]] = module_payload

    notes = public_payload["meta"].setdefault("notes", [])
    authority_note = "The authority tree is arranged by the contract lifecycle: formation, contents, vitiating factors, termination, remedies, privity, special contracts, and cross-cutting issues."
    if authority_note not in notes:
        notes.append(authority_note)
    public_payload["meta"]["authority_tree"] = {
        "id": "authority_tree:hk_contract_lifecycle",
        "label_en": "Hong Kong Contract Law Knowledge Graph",
        "label_zh": "香港合同法知識圖譜",
        "summary_en": "Lifecycle-structured authority tree: formation, contents, vitiating factors, termination, remedies, privity, special contracts, and cross-cutting issues.",
        "summary_zh": "按合同生命週期整理的權威樹：形成、內容、效力瑕疵、終止、救濟、相對性、特殊合同類型與跨界議題。",
        "modules": modules,
    }


def export_public_relationship_payload(payload: dict, title: str | None = None) -> dict:
    source_id_map: dict[str, str] = {}
    source_label_map: dict[str, str] = {}
    for node in payload["nodes"]:
        if node["type"] != "source":
            continue
        clean_label = _clean_public_source_label(node["label"])
        source_label_map[node["id"]] = clean_label
        source_id_map[node["id"]] = f"source:{slugify(clean_label)}"

    public_payload = {
        "meta": {
            "title": title or payload["meta"]["title"],
            "generated_at": payload["meta"]["generated_at"],
            "source_documents": [
                {"label": _clean_public_source_label(source["label"]), "kind": source["kind"]}
                for source in payload["meta"].get("source_documents", [])
            ],
            "source_count": payload["meta"]["source_count"],
            "passage_count": payload["meta"]["passage_count"],
            "node_count": payload["meta"]["node_count"],
            "edge_count": payload["meta"]["edge_count"],
            "retained_case_count": payload["meta"]["retained_case_count"],
            "retained_statute_count": payload["meta"]["retained_statute_count"],
            "public_mode": True,
            "notes": [
                "This public export preserves graph structure and authority links.",
                "Third-party source snippets are replaced with bibliographic references.",
                "Follow HKLII-oriented links for public primary materials.",
            ],
        },
        "nodes": [],
        "edges": [
            {
                **dict(edge),
                "source": source_id_map.get(edge["source"], edge["source"]),
                "target": source_id_map.get(edge["target"], edge["target"]),
            }
            for edge in payload["edges"]
        ],
    }

    node_lookup = {node["id"]: node for node in payload["nodes"]}

    for node in payload["nodes"]:
        public_node = dict(node)
        if node["type"] == "source":
            public_node["id"] = source_id_map.get(node["id"], node["id"])
            public_node["label"] = source_label_map.get(node["id"], node["label"])
        public_references = []
        for reference in node.get("references", []):
            is_user_note = reference.get("source_kind") == "docx"
            clean_source_label = source_label_map.get(
                reference["source_id"],
                _clean_public_source_label(reference["source_label"]),
            )
            public_references.append(
                {
                    "source_id": source_id_map.get(reference["source_id"], reference["source_id"]),
                    "source_label": clean_source_label,
                    "source_kind": reference.get("source_kind", "unknown"),
                    "location": reference["location"],
                    "snippet": (
                        reference["snippet"]
                        if is_user_note
                        else f"Referenced in {clean_source_label} ({reference['location']}). Full passage omitted in public deployment."
                    ),
                }
            )
        public_node["references"] = public_references

        if node["type"] == "source":
            kind = node.get("metrics", {}).get("kind", "source").upper()
            public_node["summary"] = (
                f"{kind} source retained as bibliographic metadata only in the public deployment."
            )
        elif node["type"] in {"case", "statute"}:
            neighbors = [node_lookup[neighbor_id] for neighbor_id in node.get("neighbors", []) if neighbor_id in node_lookup]
            topic_count = sum(1 for neighbor in neighbors if neighbor["type"] == "topic")
            domain_count = sum(1 for neighbor in neighbors if neighbor["type"] == "domain")
            source_count = sum(1 for neighbor in neighbors if neighbor["type"] == "source")
            public_node["summary"] = (
                f"{node['type'].title()} linked to {topic_count} topic node(s), "
                f"{domain_count} domain node(s), and {source_count} source node(s). "
                "Use the public authority links for primary text."
            )
        elif node["type"] == "topic":
            public_node["summary"] = node.get("summary", "")
        elif node["type"] == "domain":
            public_node["summary"] = node.get("summary", "")

        if node["type"] == "case":
            public_node["case_profile"] = _build_public_case_profile(node)

        public_payload["nodes"].append(public_node)

    _augment_public_payload_with_lineages(public_payload)
    _augment_public_payload_with_authority_tree(public_payload)
    return public_payload


def export_public_relationship_artifacts(
    graph_path: str | Path,
    output_dir: str | Path,
    title: str | None = None,
) -> dict:
    payload = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    public_payload = export_public_relationship_payload(payload, title=title)
    return _write_relationship_payload(public_payload, Path(output_dir).expanduser().resolve())


def build_relationship_artifacts(
    taxonomy_docx_path: str | Path,
    source_paths: list[str | Path],
    output_dir: str | Path,
    title: str = "Hong Kong Contract Law Relationship Graph",
) -> dict:
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    domains, topics = _build_taxonomy(taxonomy_docx_path)
    domain_lookup = {domain["id"]: domain for domain in domains}

    sources: list[SourceDocument] = []
    passages: list[Passage] = []
    loaded_source_ids: set[str] = set()

    for path in [taxonomy_docx_path, *source_paths]:
        source, source_passages = load_source_document(path)
        if source.source_id in loaded_source_ids:
            continue
        loaded_source_ids.add(source.source_id)
        sources.append(source)
        passages.extend(source_passages)

    nodes: list[dict] = []
    node_ids: set[str] = set()
    edges_counter: Counter[tuple[str, str, str]] = Counter()
    edge_weights: defaultdict[tuple[str, str, str], float] = defaultdict(float)

    def add_node(node: dict) -> None:
        if node["id"] in node_ids:
            return
        node_ids.add(node["id"])
        nodes.append(node)

    for source in sources:
        add_node(
            {
                "id": source.source_id,
                "label": source.label,
                "type": "source",
                "summary": f"{source.kind.upper()} source document used to enrich the Hong Kong contract-law graph.",
                "references": [],
                "links": [],
                "metrics": {"kind": source.kind},
            }
        )

    for domain in domains:
        add_node(
            {
                "id": domain["id"],
                "label": domain["label"],
                "type": "domain",
                "summary": domain["summary"],
                "references": [],
                "links": [],
                "metrics": {},
                "keywords": domain["keywords"],
            }
        )

    topic_lookup: dict[str, TopicProfile] = {}
    for topic in topics:
        topic_lookup[topic.topic_id] = topic
        add_node(
            {
                "id": topic.topic_id,
                "label": topic.label,
                "type": "topic",
                "summary": topic.summary,
                "references": [],
                "links": [],
                "metrics": {},
                "domain_id": topic.domain_id,
                "keywords": top_keywords(topic.label + " " + topic.summary),
            }
        )
        edges_counter[(topic.domain_id, topic.topic_id, "contains")] += 1
        edge_weights[(topic.domain_id, topic.topic_id, "contains")] += 1.0

    source_topic_counts: Counter[tuple[str, str]] = Counter()
    source_case_counts: Counter[tuple[str, str]] = Counter()
    source_statute_counts: Counter[tuple[str, str]] = Counter()
    topic_case_counts: Counter[tuple[str, str]] = Counter()
    topic_statute_counts: Counter[tuple[str, str]] = Counter()
    domain_case_counts: Counter[tuple[str, str]] = Counter()
    domain_statute_counts: Counter[tuple[str, str]] = Counter()
    case_statute_counts: Counter[tuple[str, str]] = Counter()
    case_case_counts: Counter[tuple[str, str]] = Counter()

    domain_references: defaultdict[str, list[dict]] = defaultdict(list)
    topic_references: defaultdict[str, list[dict]] = defaultdict(list)
    case_references: defaultdict[str, list[dict]] = defaultdict(list)
    statute_references: defaultdict[str, list[dict]] = defaultdict(list)

    for passage in passages:
        assigned_topics = _topic_scores(passage.text, topics)
        assigned_domains = {topic.domain_id for topic, _ in assigned_topics}
        authorities = extract_authorities(passage.text)
        cases = sorted({_normalize_case_name(case) for case in authorities["cases"]})
        statutes = sorted({_normalize_statute_name(statute) for statute in authorities["statutes"]})

        for topic, score in assigned_topics:
            source_topic_counts[(passage.source_id, topic.topic_id)] += 1
            topic_references[topic.topic_id].append(
                {
                    "source_id": passage.source_id,
                    "source_label": passage.source_label,
                    "source_kind": passage.source_kind,
                    "location": passage.location,
                    "snippet": _make_snippet(passage.text, [topic.label, topic.domain_label]),
                    "score": score + min(len(passage.text), 700) / 1400,
                }
            )

        for domain_id in assigned_domains:
            domain_references[domain_id].append(
                {
                    "source_id": passage.source_id,
                    "source_label": passage.source_label,
                    "source_kind": passage.source_kind,
                    "location": passage.location,
                    "snippet": _make_snippet(passage.text, [domain_lookup[domain_id]["label"]]),
                    "score": 0.3 + min(len(passage.text), 700) / 2000,
                }
            )

        for case_name in cases:
            source_case_counts[(passage.source_id, case_name)] += 1
            reference = {
                "source_id": passage.source_id,
                "source_label": passage.source_label,
                "source_kind": passage.source_kind,
                "location": passage.location,
                "snippet": _make_snippet(passage.text, [case_name]),
                "score": 1.0 + (0.05 if passage.source_kind == "docx" else 0.0) + min(len(passage.text), 700) / 900,
            }
            case_references[case_name].append(reference)
            for topic, score in assigned_topics:
                topic_case_counts[(topic.topic_id, case_name)] += 1
                edge_weights[(topic.topic_id, f"case:{slugify(case_name)[:64]}", "explains_case")] += score
            for domain_id in assigned_domains:
                domain_case_counts[(domain_id, case_name)] += 1

        for statute_name in statutes:
            source_statute_counts[(passage.source_id, statute_name)] += 1
            reference = {
                "source_id": passage.source_id,
                "source_label": passage.source_label,
                "source_kind": passage.source_kind,
                "location": passage.location,
                "snippet": _make_snippet(passage.text, [statute_name]),
                "score": 1.0 + (0.05 if passage.source_kind == "docx" else 0.0) + min(len(passage.text), 700) / 900,
            }
            statute_references[statute_name].append(reference)
            for topic, score in assigned_topics:
                topic_statute_counts[(topic.topic_id, statute_name)] += 1
                edge_weights[(topic.topic_id, f"statute:{slugify(statute_name)[:64]}", "cites_statute")] += score
            for domain_id in assigned_domains:
                domain_statute_counts[(domain_id, statute_name)] += 1

        for case_name in cases:
            for statute_name in statutes:
                pair = (case_name, statute_name)
                case_statute_counts[pair] += 1

        for left_index, left_case in enumerate(cases):
            for right_case in cases[left_index + 1 :]:
                pair = tuple(sorted((left_case, right_case)))
                case_case_counts[pair] += 1

    case_priority: list[tuple[str, int, int, int]] = []
    for case_name, references in case_references.items():
        mention_count = len(references)
        source_count = len({reference["source_id"] for reference in references})
        topic_count = sum(1 for (_, case_key), count in topic_case_counts.items() if case_key == case_name and count)
        priority = (source_count * 4) + mention_count + topic_count
        case_priority.append((case_name, priority, mention_count, source_count))

    keep_cases = {
        case_name
        for case_name, _, mention_count, source_count in sorted(
        case_priority, key=lambda item: (item[1], item[2], item[3], item[0]), reverse=True
        )
        if mention_count >= 3 or source_count >= 2 or any(
            reference["source_kind"] == "docx" for reference in case_references[case_name]
        )
    }

    statute_priority: list[tuple[str, int, int, int]] = []
    for statute_name, references in statute_references.items():
        mention_count = len(references)
        source_count = len({reference["source_id"] for reference in references})
        topic_count = sum(
            1 for (_, statute_key), count in topic_statute_counts.items() if statute_key == statute_name and count
        )
        priority = (source_count * 4) + mention_count + topic_count
        statute_priority.append((statute_name, priority, mention_count, source_count))

    keep_statutes = {
        statute_name
        for statute_name, _, mention_count, source_count in sorted(
            statute_priority, key=lambda item: (item[1], item[2], item[3], item[0]), reverse=True
        )
        if mention_count >= 2 or source_count >= 2 or any(
            reference["source_id"] == sources[0].source_id for reference in statute_references[statute_name]
        )
    }

    for case_name in sorted(keep_cases):
        node_id = f"case:{slugify(case_name)[:64]}"
        references = case_references[case_name]
        mention_count = len(references)
        source_count = len({reference["source_id"] for reference in references})
        add_node(
            {
                "id": node_id,
                "label": case_name,
                "type": "case",
                "summary": _summarize_authority(
                    case_name,
                    references,
                    fallback=f"Case authority mentioned across {source_count} source(s) and {mention_count} relevant passage(s).",
                ),
                "references": _select_references(references),
                "links": _case_links(case_name),
                "metrics": {"mentions": mention_count, "sources": source_count},
            }
        )

    for statute_name in sorted(keep_statutes):
        node_id = f"statute:{slugify(statute_name)[:64]}"
        references = statute_references[statute_name]
        mention_count = len(references)
        source_count = len({reference["source_id"] for reference in references})
        add_node(
            {
                "id": node_id,
                "label": statute_name,
                "type": "statute",
                "summary": _summarize_authority(
                    statute_name,
                    references,
                    fallback=f"Statutory authority mentioned across {source_count} source(s) and {mention_count} relevant passage(s).",
                ),
                "references": _select_references(references),
                "links": _statute_links(statute_name),
                "metrics": {"mentions": mention_count, "sources": source_count},
            }
        )

    node_lookup = {node["id"]: node for node in nodes}

    for (source_id, topic_id), count in source_topic_counts.items():
        if topic_id in node_lookup:
            edges_counter[(source_id, topic_id, "covers_topic")] += count
            edge_weights[(source_id, topic_id, "covers_topic")] += count

    for (source_id, case_name), count in source_case_counts.items():
        case_id = f"case:{slugify(case_name)[:64]}"
        if case_name not in keep_cases or case_id not in node_lookup:
            continue
        edges_counter[(source_id, case_id, "discusses_case")] += count
        edge_weights[(source_id, case_id, "discusses_case")] += count

    for (source_id, statute_name), count in source_statute_counts.items():
        statute_id = f"statute:{slugify(statute_name)[:64]}"
        if statute_name not in keep_statutes or statute_id not in node_lookup:
            continue
        edges_counter[(source_id, statute_id, "discusses_statute")] += count
        edge_weights[(source_id, statute_id, "discusses_statute")] += count

    for (topic_id, case_name), count in topic_case_counts.items():
        case_id = f"case:{slugify(case_name)[:64]}"
        if case_name not in keep_cases or topic_id not in node_lookup or case_id not in node_lookup:
            continue
        edges_counter[(topic_id, case_id, "explains_case")] += count

    for (topic_id, statute_name), count in topic_statute_counts.items():
        statute_id = f"statute:{slugify(statute_name)[:64]}"
        if statute_name not in keep_statutes or topic_id not in node_lookup or statute_id not in node_lookup:
            continue
        edges_counter[(topic_id, statute_id, "cites_statute")] += count

    for (domain_id, case_name), count in domain_case_counts.items():
        case_id = f"case:{slugify(case_name)[:64]}"
        if case_name not in keep_cases or case_id not in node_lookup or domain_id not in node_lookup:
            continue
        edges_counter[(domain_id, case_id, "domain_case")] += count
        edge_weights[(domain_id, case_id, "domain_case")] += count

    for (domain_id, statute_name), count in domain_statute_counts.items():
        statute_id = f"statute:{slugify(statute_name)[:64]}"
        if statute_name not in keep_statutes or statute_id not in node_lookup or domain_id not in node_lookup:
            continue
        edges_counter[(domain_id, statute_id, "domain_statute")] += count
        edge_weights[(domain_id, statute_id, "domain_statute")] += count

    for (left_name, right_name), count in case_statute_counts.items():
        case_name, statute_name = left_name, right_name
        case_id = f"case:{slugify(case_name)[:64]}"
        statute_id = f"statute:{slugify(statute_name)[:64]}"
        if case_name not in keep_cases or statute_name not in keep_statutes:
            continue
        if case_id not in node_lookup or statute_id not in node_lookup:
            continue
        edges_counter[(case_id, statute_id, "co_mentioned")] += count
        edge_weights[(case_id, statute_id, "co_mentioned")] += count

    for (left_case, right_case), count in case_case_counts.items():
        left_id = f"case:{slugify(left_case)[:64]}"
        right_id = f"case:{slugify(right_case)[:64]}"
        if left_case not in keep_cases or right_case not in keep_cases:
            continue
        if left_id not in node_lookup or right_id not in node_lookup or count < 2:
            continue
        edges_counter[(left_id, right_id, "co_discussed")] += count
        edge_weights[(left_id, right_id, "co_discussed")] += count

    edges: list[dict] = []
    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    for (source_id, target_id, edge_type), count in edges_counter.items():
        if source_id not in node_lookup or target_id not in node_lookup:
            continue
        weight = round(edge_weights[(source_id, target_id, edge_type)], 3)
        edge = {
            "source": source_id,
            "target": target_id,
            "type": edge_type,
            "weight": weight,
            "mentions": int(count),
        }
        edges.append(edge)
        adjacency[source_id].add(target_id)
        adjacency[target_id].add(source_id)

    for node in nodes:
        neighbors = sorted(adjacency.get(node["id"], set()))
        node["neighbors"] = neighbors
        node["degree"] = len(neighbors)
        if node["type"] == "domain":
            node["references"] = _select_references(domain_references[node["id"]])
        if node["type"] == "topic":
            node["references"] = _select_references(topic_references[node["id"]])

    payload = {
        "meta": {
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "taxonomy_document": str(Path(taxonomy_docx_path).expanduser().resolve()),
            "source_documents": [
                {"label": source.label, "path": source.path, "kind": source.kind} for source in sources
            ],
            "source_count": len(sources),
            "passage_count": len(passages),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "retained_case_count": len(keep_cases),
            "retained_statute_count": len(keep_statutes),
        },
        "nodes": nodes,
        "edges": edges,
    }
    return _write_relationship_payload(payload, output_path)
