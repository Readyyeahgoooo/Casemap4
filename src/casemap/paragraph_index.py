from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib import parse as urllib_parse
import json
import math
import re

from .embeddings import create_embedding_backend
from .graphrag import tokenize
from .hklii_crawler import HKLIICrawler
from .supabase_sync import _derive_hklii_id, _derive_public_path


PARAGRAPH_INDEX_COLLECTION = "hk_case_paragraphs"
DEFAULT_INDEX_FILE = "paragraph_chroma_records.json"
DEFAULT_STATE_FILE = "paragraph_index_state.json"
DEFAULT_MANIFEST_FILE = "paragraph_index_manifest.json"


@dataclass
class ParagraphIndexResult:
    manifest: dict
    records: list[dict]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _embedding_batches(texts: list[str], batch_size: int) -> list[tuple[int, int]]:
    return [(start, min(start + batch_size, len(texts))) for start in range(0, len(texts), batch_size)]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size])) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right[:size])) or 1.0
    return dot / (left_norm * right_norm)


def _lexical_score(query_tokens: list[str], text: str, label: str = "") -> float:
    if not query_tokens:
        return 0.0
    text_tokens = tokenize(f"{label} {text}")
    if not text_tokens:
        return 0.0
    text_counts = Counter(text_tokens)
    query_counts = Counter(query_tokens)
    score = 0.0
    for token, query_count in query_counts.items():
        score += query_count * math.log1p(text_counts.get(token, 0))
    overlap = len(set(query_tokens) & set(text_tokens))
    return score / max(math.sqrt(len(text_tokens)), 1.0) + 0.08 * overlap


def _paragraph_record_id(hklii_id: str, paragraph_span: str, index: int) -> str:
    span = re.sub(r"[^a-z0-9]+", "_", paragraph_span.lower()).strip("_")
    return f"{hklii_id}:{span or f'paragraph_{index}'}"


def _is_indexable_paragraph(text: str) -> bool:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", text)
    if len(words) < 12:
        return False
    lowered = text.lower().strip()
    boilerplate_prefixes = (
        "in the court",
        "in the district court",
        "court of appeal",
        "court of final appeal",
        "before:",
        "date of hearing",
        "date of judgment",
    )
    if lowered.startswith(boilerplate_prefixes):
        return False
    return True


def _topic_context(node: dict, edges_by_target: dict[str, list[dict]], node_lookup: dict[str, dict]) -> list[str]:
    labels: list[str] = []
    for edge in edges_by_target.get(node.get("id", ""), []):
        if edge.get("type") != "discusses_case":
            continue
        topic = node_lookup.get(edge.get("source", ""))
        if topic and topic.get("type") == "topic" and topic.get("label"):
            labels.append(str(topic["label"]))
    return sorted(set(labels))


def _principle_context(node: dict) -> list[str]:
    principles = []
    for principle in node.get("principles", []) or []:
        statement = str(principle.get("statement_en", "")).strip()
        if statement:
            principles.append(statement)
    return principles[:12]


def _case_paths_from_graph(payload: dict) -> list[tuple[str, dict]]:
    case_nodes = [node for node in payload.get("nodes", []) if node.get("type") == "case"]
    paths: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for node in case_nodes:
        public_path = _derive_public_path(node)
        if not public_path or public_path in seen:
            continue
        seen.add(public_path)
        paths.append((public_path, node))
    return paths


def _case_paths_from_file(path: str | Path) -> list[tuple[str, dict]]:
    source_path = Path(path).expanduser()
    paths: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for raw_line in source_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parsed = urllib_parse.urlparse(line)
        public_path = parsed.path if parsed.scheme else line
        if "/en/cases/" not in public_path or public_path in seen:
            continue
        seen.add(public_path)
        paths.append((public_path, {"id": f"external:{len(paths) + 1}", "label": public_path, "type": "case"}))
    return paths


def _build_records_for_case(case_doc, public_path: str, node: dict, topic_labels: list[str], legal_principles: list[str], embedder, batch_size: int) -> list[dict]:
    hklii_id = _derive_hklii_id(public_path)
    populated = [paragraph for paragraph in case_doc.paragraphs if _is_indexable_paragraph(paragraph.text.strip())]
    documents = [paragraph.text.strip() for paragraph in populated]
    embeddings: list[list[float]] = []
    for start, end in _embedding_batches(documents, batch_size):
        embeddings.extend(embedder.embed_documents(documents[start:end]))

    records: list[dict] = []
    for index, (paragraph, embedding) in enumerate(zip(populated, embeddings, strict=True), start=1):
        paragraph_text = paragraph.text.strip()
        metadata = {
            "hklii_id": hklii_id,
            "source_path": public_path,
            "source_url": case_doc.public_url,
            "source_node_id": node.get("id", ""),
            "case_name": case_doc.case_name,
            "neutral_citation": case_doc.neutral_citation,
            "court": case_doc.court_name,
            "court_code": case_doc.court_code,
            "decision_date": case_doc.decision_date,
            "paragraph_span": paragraph.paragraph_span or f"paragraph {index}",
            "paragraph_index": index,
            "topics": topic_labels,
            "legal_principles": legal_principles,
            "cases_cited": [reference.label for reference in case_doc.cited_cases[:25]],
            "legislation_cited": [reference.label for reference in case_doc.cited_statutes[:25]],
            "label": f"{case_doc.neutral_citation or case_doc.case_name} {paragraph.paragraph_span or index}",
        }
        records.append(
            {
                "id": _paragraph_record_id(hklii_id, paragraph.paragraph_span, index),
                "document": paragraph_text,
                "metadata": metadata,
                "embedding": embedding,
            }
        )
    return records


def build_paragraph_index(
    *,
    graph_path: str | Path | None = None,
    case_paths_file: str | Path | None = None,
    output_dir: str | Path,
    max_cases: int = 100,
    batch_size: int = 32,
    embedding_backend: str = "auto",
    embedding_model: str = "",
    embedding_dimensions: int = 0,
    reset: bool = False,
    crawler: HKLIICrawler | None = None,
) -> ParagraphIndexResult:
    output_path = Path(output_dir).expanduser().resolve()
    index_path = output_path / DEFAULT_INDEX_FILE
    state_path = output_path / DEFAULT_STATE_FILE
    manifest_path = output_path / DEFAULT_MANIFEST_FILE
    output_path.mkdir(parents=True, exist_ok=True)

    payload = _read_json(Path(graph_path).expanduser().resolve(), {"nodes": [], "edges": []}) if graph_path else {"nodes": [], "edges": []}
    node_lookup = {node.get("id", ""): node for node in payload.get("nodes", [])}
    edges_by_target: dict[str, list[dict]] = defaultdict(list)
    for edge in payload.get("edges", []):
        edges_by_target[edge.get("target", "")].append(edge)

    candidates: list[tuple[str, dict]] = []
    if graph_path:
        candidates.extend(_case_paths_from_graph(payload))
    if case_paths_file:
        candidates.extend(_case_paths_from_file(case_paths_file))

    deduped: list[tuple[str, dict]] = []
    seen_paths: set[str] = set()
    for public_path, node in candidates:
        if public_path in seen_paths:
            continue
        seen_paths.add(public_path)
        deduped.append((public_path, node))

    previous_index = {} if reset else _read_json(index_path, {})
    existing_records = previous_index.get("records", []) if isinstance(previous_index, dict) else []
    records_by_id = {record["id"]: record for record in existing_records if record.get("id")}
    state = {"processed_paths": [], "errors": []} if reset else _read_json(state_path, {"processed_paths": [], "errors": []})
    processed_paths = set(state.get("processed_paths", []))
    errors: list[dict] = list(state.get("errors", []))

    embedder = create_embedding_backend(
        backend=embedding_backend,
        model=embedding_model,
        dimensions=embedding_dimensions,
    )
    crawler = crawler or HKLIICrawler()

    selected = [item for item in deduped if item[0] not in processed_paths]
    if max_cases > 0:
        selected = selected[:max_cases]

    indexed_cases = 0
    indexed_paragraphs = 0
    for public_path, node in selected:
        try:
            case_doc = crawler.fetch_case_document(public_path)
            topic_labels = _topic_context(node, edges_by_target, node_lookup)
            legal_principles = _principle_context(node)
            case_records = _build_records_for_case(
                case_doc,
                public_path,
                node,
                topic_labels,
                legal_principles,
                embedder,
                batch_size=max(1, batch_size),
            )
            for record in case_records:
                records_by_id[record["id"]] = record
            processed_paths.add(public_path)
            indexed_cases += 1
            indexed_paragraphs += len(case_records)
            state_payload = {
                "updated_at": _now_iso(),
                "processed_paths": sorted(processed_paths),
                "errors": errors[-100:],
                "last_path": public_path,
            }
            _write_json(state_path, state_payload)
        except Exception as exc:  # pragma: no cover - network and remote data dependent.
            errors.append({"path": public_path, "error": str(exc), "at": _now_iso()})
            _write_json(
                state_path,
                {
                    "updated_at": _now_iso(),
                    "processed_paths": sorted(processed_paths),
                    "errors": errors[-100:],
                    "last_failed_path": public_path,
                },
            )

    records = sorted(records_by_id.values(), key=lambda item: (item["metadata"].get("hklii_id", ""), item["metadata"].get("paragraph_index", 0)))
    index_payload = {
        "collection": PARAGRAPH_INDEX_COLLECTION,
        "generated_at": _now_iso(),
        "embedding_backend": embedder.manifest(),
        "records": records,
    }
    _write_json(index_path, index_payload)

    case_ids = {record["metadata"].get("hklii_id", "") for record in records}
    manifest = {
        "collection": PARAGRAPH_INDEX_COLLECTION,
        "generated_at": index_payload["generated_at"],
        "index_path": str(index_path),
        "state_path": str(state_path),
        "candidate_case_count": len(deduped),
        "processed_case_count": len(processed_paths),
        "new_case_count": indexed_cases,
        "new_paragraph_count": indexed_paragraphs,
        "indexed_case_count": len(case_ids - {""}),
        "indexed_paragraph_count": len(records),
        "remaining_case_count": max(len(deduped) - len(processed_paths), 0),
        "error_count": len(errors),
        "recent_errors": errors[-10:],
        "embedding_backend": embedder.manifest(),
        "crawler_warnings": list(getattr(crawler, "warnings", [])),
    }
    _write_json(manifest_path, manifest)
    return ParagraphIndexResult(manifest=manifest, records=records)


def search_paragraph_index(
    *,
    index_path: str | Path,
    question: str,
    top_k: int = 8,
    embedding_backend: str = "auto",
    embedding_model: str = "",
    embedding_dimensions: int = 0,
) -> dict:
    path = Path(index_path).expanduser().resolve()
    payload = _read_json(path, {"records": []})
    records = payload.get("records", [])
    query_tokens = tokenize(question)
    index_backend = payload.get("embedding_backend", {}) if isinstance(payload.get("embedding_backend", {}), dict) else {}
    resolved_backend = embedding_backend
    resolved_model = embedding_model
    resolved_dimensions = embedding_dimensions
    if (embedding_backend or "auto").strip().lower() == "auto" and index_backend.get("backend"):
        resolved_backend = str(index_backend.get("backend"))
        resolved_model = embedding_model or str(index_backend.get("model") or "")
        resolved_dimensions = embedding_dimensions or int(index_backend.get("dimensions") or 0)
    embedder = create_embedding_backend(
        backend=resolved_backend,
        model=resolved_model,
        dimensions=resolved_dimensions,
    )
    query_embedding = embedder.embed_documents([question])[0] if question.strip() else []
    scored: list[dict] = []
    for record in records:
        metadata = record.get("metadata", {})
        vector_score = _cosine(query_embedding, record.get("embedding", []))
        lexical = _lexical_score(query_tokens, record.get("document", ""), metadata.get("case_name", ""))
        topic_boost = 0.04 if set(query_tokens) & set(tokenize(" ".join(metadata.get("topics", [])))) else 0.0
        principle_boost = 0.05 if set(query_tokens) & set(tokenize(" ".join(metadata.get("legal_principles", [])))) else 0.0
        score = 0.62 * vector_score + 0.38 * lexical + topic_boost + principle_boost
        if score <= 0:
            continue
        scored.append(
            {
                "score": round(score, 6),
                "vector_score": round(vector_score, 6),
                "lexical_score": round(lexical, 6),
                "id": record.get("id", ""),
                "document": record.get("document", ""),
                "metadata": metadata,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {
        "question": question,
        "top_k": top_k,
        "result_count": min(top_k, len(scored)),
        "collection": payload.get("collection", PARAGRAPH_INDEX_COLLECTION),
        "embedding_backend": embedder.manifest(),
        "results": scored[:top_k],
    }
