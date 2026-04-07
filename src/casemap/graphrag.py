from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import json
import math
import re

from .docx_parser import extract_paragraphs
from .viewer import render_knowledge_map

SECTION_RE = re.compile(r"^(?P<number>\d+)\.\s+(?P<title>.+)$")
STATUTE_RE = re.compile(r"([A-Z][A-Za-z0-9'()\-&,.\s]+ Ordinance \(Cap\. \d+\))")
CASE_RE = re.compile(r"([A-Z][A-Za-z.'&\-\s]+ v [A-Z][A-Za-z0-9.'&\-\s]+)")
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9()\-]{1,}")

STOPWORDS = {
    "a",
    "all",
    "an",
    "and",
    "any",
    "apply",
    "as",
    "at",
    "be",
    "been",
    "being",
    "both",
    "but",
    "by",
    "can",
    "claim",
    "contexts",
    "contract",
    "contracts",
    "court",
    "courts",
    "damages",
    "for",
    "from",
    "general",
    "generally",
    "give",
    "gives",
    "has",
    "have",
    "if",
    "in",
    "include",
    "includes",
    "into",
    "is",
    "it",
    "its",
    "law",
    "legal",
    "made",
    "make",
    "may",
    "must",
    "not",
    "of",
    "on",
    "or",
    "party",
    "parties",
    "rule",
    "section",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "under",
    "unless",
    "voidable",
    "where",
    "which",
    "will",
    "with",
}


@dataclass
class Section:
    number: int
    title: str
    paragraphs: list[str]

    @property
    def slug(self) -> str:
        return slugify(self.title)

    @property
    def node_id(self) -> str:
        return f"section:{self.slug}"


def slugify(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = lowered.strip("_")
    return lowered or "item"


def tokenize(text: str) -> list[str]:
    tokens = [match.group(0).lower() for match in TOKEN_RE.finditer(text.lower())]
    return [token for token in tokens if token not in STOPWORDS and not token.isdigit()]


def split_topic(paragraph: str) -> tuple[str, str]:
    if ":" not in paragraph:
        words = paragraph.split()
        if len(words) <= 10:
            return paragraph.strip(), ""
        title = " ".join(words[:8]).strip()
        return title, paragraph.strip()

    head, tail = paragraph.split(":", 1)
    head = head.strip()
    tail = tail.strip()
    if 1 <= len(head.split()) <= 12:
        return head, tail
    words = paragraph.split()
    title = " ".join(words[:8]).strip()
    return title, paragraph.strip()


def extract_authorities(text: str) -> dict[str, list[str]]:
    statutes = sorted({match.strip(" ,.;") for match in STATUTE_RE.findall(text)})
    cases = sorted({match.strip(" ,.;") for match in CASE_RE.findall(text)})
    return {"statutes": statutes, "cases": cases}


def top_keywords(text: str, limit: int = 6) -> list[str]:
    counts = Counter(tokenize(text))
    return [token for token, _ in counts.most_common(limit)]


def parse_sections(paragraphs: list[str]) -> list[Section]:
    sections: list[Section] = []
    current: Section | None = None

    for paragraph in paragraphs:
        match = SECTION_RE.match(paragraph)
        if match:
            if current is not None:
                sections.append(current)
            current = Section(
                number=int(match.group("number")),
                title=match.group("title").strip(),
                paragraphs=[],
            )
            continue

        if current is None:
            current = Section(number=0, title="Overview", paragraphs=[])
        current.paragraphs.append(paragraph)

    if current is not None:
        sections.append(current)

    return sections


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    minimum = min(values)
    maximum = max(values)
    if math.isclose(minimum, maximum):
        return {key: (1.0 if value > 0 else 0.0) for key, value in scores.items()}
    spread = maximum - minimum
    return {key: (value - minimum) / spread for key, value in scores.items()}


def build_graph_payload(docx_path: str | Path) -> tuple[dict, list[dict], list[str], list[Section]]:
    source_path = Path(docx_path).expanduser().resolve()
    paragraphs = extract_paragraphs(source_path)
    sections = parse_sections(paragraphs)

    nodes: list[dict] = []
    edges: list[dict] = []
    chunks: list[dict] = []

    nodes_by_id: dict[str, dict] = {}
    authority_node_ids: dict[str, str] = {}
    concept_records: list[dict] = []

    def add_node(node: dict) -> None:
        if node["id"] in nodes_by_id:
            return
        nodes_by_id[node["id"]] = node
        nodes.append(node)

    for section in sections:
        section_summary = " ".join(section.paragraphs[:2]).strip()
        add_node(
            {
                "id": section.node_id,
                "label": section.title,
                "type": "section",
                "section_id": section.node_id,
                "summary": section_summary or section.title,
                "citations": [],
                "keywords": top_keywords(section.title + " " + section_summary),
            }
        )

        previous_concept_id: str | None = None
        for index, paragraph in enumerate(section.paragraphs, start=1):
            title, body = split_topic(paragraph)
            description = body or f"Grouping node inside {section.title}."
            authorities = extract_authorities(paragraph)
            concept_id = f"concept:{section.slug}:{index:02d}:{slugify(title)[:36]}"
            keywords = top_keywords(title + " " + paragraph)
            citations = authorities["statutes"] + authorities["cases"]
            summary = description if len(description) < 420 else description[:417] + "..."
            concept_node = {
                "id": concept_id,
                "label": title,
                "type": "concept",
                "section_id": section.node_id,
                "summary": summary,
                "citations": citations,
                "keywords": keywords,
                "text": paragraph,
            }
            add_node(concept_node)
            edges.append(
                {
                    "source": section.node_id,
                    "target": concept_id,
                    "type": "contains",
                    "weight": 1.0,
                    "reason": "section membership",
                }
            )
            if previous_concept_id is not None:
                edges.append(
                    {
                        "source": previous_concept_id,
                        "target": concept_id,
                        "type": "adjacent",
                        "weight": 0.35,
                        "reason": "consecutive concepts inside the same section",
                    }
                )
            previous_concept_id = concept_id

            for statute in authorities["statutes"]:
                node_id = authority_node_ids.setdefault(
                    statute, f"statute:{slugify(statute)[:56]}"
                )
                add_node(
                    {
                        "id": node_id,
                        "label": statute,
                        "type": "statute",
                        "section_id": section.node_id,
                        "summary": f"Statutory authority cited by concepts in {section.title}.",
                        "citations": [statute],
                        "keywords": top_keywords(statute),
                    }
                )
                edges.append(
                    {
                        "source": concept_id,
                        "target": node_id,
                        "type": "cites",
                        "weight": 1.0,
                        "reason": "statutory citation",
                    }
                )

            for case_name in authorities["cases"]:
                node_id = authority_node_ids.setdefault(case_name, f"case:{slugify(case_name)[:56]}")
                add_node(
                    {
                        "id": node_id,
                        "label": case_name,
                        "type": "case",
                        "section_id": section.node_id,
                        "summary": f"Case authority cited by concepts in {section.title}.",
                        "citations": [case_name],
                        "keywords": top_keywords(case_name),
                    }
                )
                edges.append(
                    {
                        "source": concept_id,
                        "target": node_id,
                        "type": "cites",
                        "weight": 1.0,
                        "reason": "case citation",
                    }
                )

            token_frequency = Counter(tokenize(f"{title} {paragraph}"))
            chunk = {
                "id": f"chunk:{section.slug}:{index:02d}",
                "node_id": concept_id,
                "section_id": section.node_id,
                "section_title": section.title,
                "title": title,
                "text": paragraph,
                "summary": summary,
                "citations": citations,
                "keywords": keywords,
                "token_freq": dict(token_frequency),
                "token_count": sum(token_frequency.values()),
            }
            chunks.append(chunk)
            concept_records.append(
                {
                    "node_id": concept_id,
                    "section_id": section.node_id,
                    "token_set": set(token_frequency),
                    "citations": set(citations),
                    "keywords": set(keywords),
                }
            )

    edge_keys: set[tuple[str, str, str]] = {
        (edge["source"], edge["target"], edge["type"]) for edge in edges
    }
    for left_index, left in enumerate(concept_records):
        for right in concept_records[left_index + 1 :]:
            if left["section_id"] == right["section_id"]:
                continue
            shared_citations = left["citations"] & right["citations"]
            shared_keywords = left["keywords"] & right["keywords"]
            shared_tokens = left["token_set"] & right["token_set"]
            jaccard = len(shared_tokens) / max(len(left["token_set"] | right["token_set"]), 1)
            if not shared_citations and len(shared_keywords) < 2 and jaccard < 0.12:
                continue

            weight = min(1.8, 0.35 + (0.45 * len(shared_citations)) + (0.2 * len(shared_keywords)) + jaccard)
            edge = {
                "source": left["node_id"],
                "target": right["node_id"],
                "type": "cross_reference",
                "weight": round(weight, 4),
                "reason": "shared authorities or overlapping legal vocabulary",
            }
            key = (edge["source"], edge["target"], edge["type"])
            if key not in edge_keys:
                edges.append(edge)
                edge_keys.add(key)

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge["source"]].add(edge["target"])
        adjacency[edge["target"]].add(edge["source"])

    node_count = max(len(nodes) - 1, 1)
    for node in nodes:
        neighbor_ids = sorted(adjacency.get(node["id"], set()))
        node["neighbors"] = neighbor_ids
        node["centrality"] = round(len(neighbor_ids) / node_count, 4)

    graph_payload = {
        "meta": {
            "source_document": str(source_path),
            "generated_at": datetime.now(UTC).isoformat(),
            "paragraph_count": len(paragraphs),
            "section_count": len(sections),
        },
        "nodes": nodes,
        "edges": edges,
    }
    return graph_payload, chunks, paragraphs, sections


class RerankedRetriever:
    def __init__(self, graph_payload: dict, chunks: list[dict]) -> None:
        self.graph_payload = graph_payload
        self.chunks = chunks
        self.nodes = {node["id"]: node for node in graph_payload["nodes"]}
        self.adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in graph_payload["edges"]:
            self.adjacency[edge["source"]].add(edge["target"])
            self.adjacency[edge["target"]].add(edge["source"])
        self.idf = self._build_idf()

    @classmethod
    def from_files(cls, graph_path: str | Path, chunk_path: str | Path) -> "RerankedRetriever":
        graph_payload = json.loads(Path(graph_path).read_text(encoding="utf-8"))
        chunks = json.loads(Path(chunk_path).read_text(encoding="utf-8"))
        return cls(graph_payload=graph_payload, chunks=chunks)

    def _build_idf(self) -> dict[str, float]:
        document_frequency: Counter[str] = Counter()
        total_documents = len(self.chunks)
        for chunk in self.chunks:
            document_frequency.update(chunk["token_freq"].keys())
        return {
            token: math.log((1 + total_documents) / (1 + frequency)) + 1.0
            for token, frequency in document_frequency.items()
        }

    def _lexical_scores(self, question: str) -> dict[str, float]:
        query_tokens = tokenize(question)
        query_counts = Counter(query_tokens)
        scores: dict[str, float] = {}
        for chunk in self.chunks:
            token_freq = chunk["token_freq"]
            chunk_total = max(chunk["token_count"], 1)
            score = 0.0
            for token, query_count in query_counts.items():
                if token not in token_freq:
                    continue
                tf = token_freq[token] / chunk_total
                score += query_count * tf * self.idf.get(token, 0.0)
            title_text = chunk["title"].lower()
            if any(token in title_text for token in query_tokens):
                score += 0.18
            scores[chunk["id"]] = score
        return scores

    def _graph_scores(self, candidate_chunk_ids: list[str]) -> dict[str, float]:
        seed_nodes = [self._chunk_by_id(chunk_id)["node_id"] for chunk_id in candidate_chunk_ids[:4]]
        propagated: defaultdict[str, float] = defaultdict(float)
        for seed in seed_nodes:
            propagated[seed] += 1.0
            for neighbor in self.adjacency.get(seed, set()):
                propagated[neighbor] += 0.55
                for second_hop in self.adjacency.get(neighbor, set()):
                    if second_hop != seed:
                        propagated[second_hop] += 0.2

        chunk_scores: dict[str, float] = {}
        for chunk in self.chunks:
            node = self.nodes.get(chunk["node_id"], {})
            chunk_scores[chunk["id"]] = propagated.get(chunk["node_id"], 0.0) + float(node.get("centrality", 0.0))
        return chunk_scores

    def _authority_scores(self, question: str) -> dict[str, float]:
        authorities = extract_authorities(question)
        authority_terms = set(authorities["statutes"] + authorities["cases"])
        chunk_scores: dict[str, float] = {}
        for chunk in self.chunks:
            overlap = authority_terms & set(chunk["citations"])
            chunk_scores[chunk["id"]] = 1.0 * len(overlap)
        return chunk_scores

    def _chunk_by_id(self, chunk_id: str) -> dict:
        for chunk in self.chunks:
            if chunk["id"] == chunk_id:
                return chunk
        raise KeyError(chunk_id)

    def search(self, question: str, top_k: int = 5) -> list[dict]:
        lexical = self._lexical_scores(question)
        ranked_candidates = sorted(lexical, key=lexical.get, reverse=True)
        graph_scores = self._graph_scores(ranked_candidates)
        authority_scores = self._authority_scores(question)

        lexical_norm = normalize_scores(lexical)
        graph_norm = normalize_scores(graph_scores)
        authority_norm = normalize_scores(authority_scores)

        final_scores: dict[str, float] = {}
        for chunk in self.chunks:
            chunk_id = chunk["id"]
            node = self.nodes.get(chunk["node_id"], {})
            final_scores[chunk_id] = (
                0.62 * lexical_norm.get(chunk_id, 0.0)
                + 0.25 * graph_norm.get(chunk_id, 0.0)
                + 0.08 * authority_norm.get(chunk_id, 0.0)
                + 0.05 * float(node.get("centrality", 0.0))
            )

        best_ids = sorted(final_scores, key=final_scores.get, reverse=True)[:top_k]
        results: list[dict] = []
        for rank, chunk_id in enumerate(best_ids, start=1):
            chunk = self._chunk_by_id(chunk_id)
            node = self.nodes.get(chunk["node_id"], {})
            neighbor_labels = [
                self.nodes[neighbor_id]["label"]
                for neighbor_id in node.get("neighbors", [])
                if neighbor_id in self.nodes
            ][:8]
            results.append(
                {
                    "rank": rank,
                    "chunk_id": chunk_id,
                    "score": round(final_scores[chunk_id], 4),
                    "score_breakdown": {
                        "lexical": round(lexical_norm.get(chunk_id, 0.0), 4),
                        "graph": round(graph_norm.get(chunk_id, 0.0), 4),
                        "authority": round(authority_norm.get(chunk_id, 0.0), 4),
                        "centrality": round(float(node.get("centrality", 0.0)), 4),
                    },
                    "section": chunk["section_title"],
                    "title": chunk["title"],
                    "text": chunk["text"],
                    "citations": chunk["citations"],
                    "keywords": chunk["keywords"],
                    "graph_neighbors": neighbor_labels,
                }
            )
        return results


def build_artifacts(docx_path: str | Path, output_dir: str | Path) -> dict:
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    graph_payload, chunks, paragraphs, sections = build_graph_payload(docx_path)

    graph_file = output_path / "graph.json"
    chunk_file = output_path / "chunks.json"
    viewer_file = output_path / "knowledge_map.html"
    manifest_file = output_path / "manifest.json"
    sample_query_file = output_path / "sample_queries.json"

    graph_file.write_text(json.dumps(graph_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    chunk_file.write_text(json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8")
    viewer_file.write_text(render_knowledge_map(graph_payload), encoding="utf-8")

    retriever = RerankedRetriever(graph_payload=graph_payload, chunks=chunks)
    sample_queries = {
        "When can a third party enforce a contract term?": retriever.search(
            "When can a third party enforce a contract term?"
        ),
        "How are exemption clauses controlled?": retriever.search(
            "How are exemption clauses controlled?"
        ),
        "What formalities apply to land sale contracts?": retriever.search(
            "What formalities apply to land sale contracts?"
        ),
    }
    sample_query_file.write_text(
        json.dumps(sample_queries, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    manifest = {
        "source_document": graph_payload["meta"]["source_document"],
        "generated_at": graph_payload["meta"]["generated_at"],
        "paragraph_count": len(paragraphs),
        "section_count": len(sections),
        "node_count": len(graph_payload["nodes"]),
        "edge_count": len(graph_payload["edges"]),
        "chunk_count": len(chunks),
        "files": {
            "graph": str(graph_file),
            "chunks": str(chunk_file),
            "viewer": str(viewer_file),
            "samples": str(sample_query_file),
        },
    }
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
