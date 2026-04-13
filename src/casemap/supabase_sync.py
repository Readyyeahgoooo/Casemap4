from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import json
import mimetypes
import os
import re
import ssl

from .embeddings import create_embedding_backend
from .hklii_crawler import HKLIICrawler

HKLII_PATH_RE = re.compile(r"^/en/cases/(?P<court>[^/]+)/(?P<year>\d{4})/(?P<num>\d+)$", re.IGNORECASE)
NEUTRAL_RE = re.compile(r"\[(?P<year>\d{4})\]\s+(?P<court>[A-Z]{2,8})\s+(?P<num>\d+)")
GENERIC_CITED_SUMMARY = "Authority cited inside an HKLII criminal-law judgment."
CRIMINAL_CASE_NAME_RE = re.compile(
    r"\b(HKSAR|THE QUEEN|R\s*v\.?|SECRETARY FOR JUSTICE|DIRECTOR OF PUBLIC PROSECUTIONS|v\.\s*HKSAR)\b",
    re.IGNORECASE,
)
CRIMINAL_RELEVANCE_RE = re.compile(
    r"\b("
    r"evidence|evidential|hearsay|confession|privilege|identification|disclosure|fair trial|"
    r"burden of proof|standard of proof|abuse of process|voir dire|sentence|sentencing|"
    r"prosecution|indictment|charge|mens rea|actus reus|criminal"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class SupabaseConfig:
    url: str
    publishable_key: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
        publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
        service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url:
            raise RuntimeError("SUPABASE_URL is not configured.")
        if not publishable_key:
            raise RuntimeError("SUPABASE_PUBLISHABLE_KEY is not configured.")
        if not service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
        return cls(url=url, publishable_key=publishable_key, service_role_key=service_role_key)


def _request(
    request: urllib_request.Request,
    *,
    timeout_seconds: int = 60,
    expect_json: bool = True,
) -> dict | list | str:
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", "ignore")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {exc.code} for {request.full_url}: {detail}") from exc
    except urllib_error.URLError as exc:
        reason = getattr(exc, "reason", "")
        if "CERTIFICATE_VERIFY_FAILED" not in str(reason):
            raise
        try:
            with urllib_request.urlopen(
                request,
                timeout=timeout_seconds,
                context=ssl._create_unverified_context(),
            ) as response:
                raw = response.read().decode("utf-8", "ignore")
        except urllib_error.HTTPError as inner_exc:
            detail = inner_exc.read().decode("utf-8", "ignore")
            raise RuntimeError(f"HTTP {inner_exc.code} for {request.full_url}: {detail}") from inner_exc
    if not expect_json:
        return raw
    return json.loads(raw or "null")


def _supabase_request(
    config: SupabaseConfig,
    method: str,
    path: str,
    *,
    query: dict[str, str] | None = None,
    json_body: object | None = None,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    expect_json: bool = True,
) -> dict | list | str:
    url = f"{config.url}{path}"
    if query:
        url = f"{url}?{urllib_parse.urlencode(query, doseq=True)}"
    request_headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Accept": "application/json",
    }
    request_headers.update(headers or {})
    request_data = body
    if json_body is not None:
        request_data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib_request.Request(url, data=request_data, method=method, headers=request_headers)
    return _request(request, expect_json=expect_json)


def _derive_hklii_id(public_path: str) -> str:
    match = HKLII_PATH_RE.match(public_path)
    if not match:
        raise ValueError(f"Unsupported HKLII case path: {public_path}")
    return f"{match.group('court').lower()}_{match.group('year')}_{match.group('num')}"


def _derive_public_path(node: dict) -> str | None:
    for link in node.get("links", []):
        url = link.get("url", "")
        parsed = urllib_parse.urlparse(url)
        if "/en/cases/" in parsed.path and "hklii" in parsed.netloc:
            return parsed.path
    citation = node.get("neutral_citation", "") or ""
    court_code = (node.get("court_code", "") or "").lower()
    match = NEUTRAL_RE.match(citation)
    if match and court_code in {"hkdc", "hkcfi", "hkca", "hkcfa"}:
        return f"/en/cases/{court_code}/{match.group('year')}/{match.group('num')}"
    return None


def _is_generic_cited_authority(node: dict) -> bool:
    summary = (node.get("summary_en") or node.get("summary") or "").strip()
    return summary == GENERIC_CITED_SUMMARY and not node.get("topics") and not node.get("principles")


def _case_priority(node: dict) -> tuple[int, int, int, int]:
    label = node.get("label", "")
    summary = (node.get("summary_en") or node.get("summary") or "").strip()
    has_named_label = int(bool(label and not label.startswith("[")))
    has_topics = int(bool(node.get("topics")))
    has_principles = int(bool(node.get("principles")))
    has_descriptive_summary = int(bool(summary and summary != GENERIC_CITED_SUMMARY))
    return (has_principles, has_topics, has_named_label, has_descriptive_summary)


def _looks_criminally_relevant(node: dict, case_name: str, *, title: str = "", sample_text: str = "") -> bool:
    if not _is_generic_cited_authority(node):
        return True
    if CRIMINAL_CASE_NAME_RE.search(case_name or ""):
        return True
    node_summary = (node.get("summary_en") or node.get("summary") or "").strip()
    relevance_text = " ".join(
        part
        for part in (
            "" if node_summary == GENERIC_CITED_SUMMARY else node_summary,
            title,
            sample_text,
        )
        if part
    )
    return bool(CRIMINAL_RELEVANCE_RE.search(relevance_text))


def _artifact_upload_targets(base_prefix: str, relationship_dir: Path, hybrid_dir: Path | None) -> list[tuple[Path, str]]:
    targets = [
        (relationship_dir / "manifest.json", f"{base_prefix}/manifest.json"),
        (relationship_dir / "relationship_graph.json", f"{base_prefix}/relationship_graph.json"),
        (relationship_dir / "monitor_report.json", f"{base_prefix}/monitor_report.json"),
        (relationship_dir / "monitor_report.html", f"{base_prefix}/monitor_report.html"),
        (relationship_dir / "chroma_records.json", f"{base_prefix}/chroma_records.json"),
        (relationship_dir / "embedding_records.json", f"{base_prefix}/embedding_records.json"),
    ]
    if hybrid_dir:
        targets.extend(
            [
                (hybrid_dir / "manifest.json", f"{base_prefix}/hybrid_manifest.json"),
                (hybrid_dir / "hierarchical_graph.json", f"{base_prefix}/hierarchical_graph.json"),
                (hybrid_dir / "public_projection.json", f"{base_prefix}/public_projection.json"),
            ]
        )
    return [(local_path, remote_path) for local_path, remote_path in targets if local_path.exists()]


def _upload_file_to_storage(config: SupabaseConfig, bucket: str, local_path: Path, remote_path: str) -> str:
    content_type, _ = mimetypes.guess_type(str(local_path))
    raw = local_path.read_bytes()
    return _upload_bytes_to_storage(config, bucket, raw, remote_path, content_type=content_type or "application/octet-stream")


def _upload_bytes_to_storage(
    config: SupabaseConfig,
    bucket: str,
    raw: bytes,
    remote_path: str,
    *,
    content_type: str,
) -> str:
    _supabase_request(
        config,
        "POST",
        f"/storage/v1/object/{bucket}/{remote_path}",
        body=raw,
        headers={
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        expect_json=True,
    )
    return f"{bucket}/{remote_path}"


def _fetch_case_id(config: SupabaseConfig, hklii_id: str) -> int | None:
    rows = _supabase_request(
        config,
        "GET",
        "/rest/v1/cases",
        query={"select": "id", "hklii_id": f"eq.{hklii_id}", "limit": "1"},
    )
    if isinstance(rows, list) and rows:
        return int(rows[0]["id"])
    return None


def _upsert_case(config: SupabaseConfig, payload: dict) -> int:
    existing_id = _fetch_case_id(config, payload["hklii_id"])
    if existing_id is None:
        created = _supabase_request(
            config,
            "POST",
            "/rest/v1/cases",
            query={"select": "id"},
            json_body=payload,
            headers={"Prefer": "return=representation"},
        )
        if not isinstance(created, list) or not created:
            raise RuntimeError(f"Supabase did not return a created case row for {payload['hklii_id']}")
        return int(created[0]["id"])
    _supabase_request(
        config,
        "PATCH",
        "/rest/v1/cases",
        query={"id": f"eq.{existing_id}"},
        json_body=payload,
        headers={"Prefer": "return=minimal"},
    )
    return existing_id


def _replace_case_chunks(config: SupabaseConfig, hklii_id: str, rows: list[dict], *, batch_size: int = 50) -> None:
    _supabase_request(
        config,
        "DELETE",
        "/rest/v1/case_chunks",
        query={"hklii_id": f"eq.{hklii_id}"},
        headers={"Prefer": "return=minimal"},
    )
    if not rows:
        return
    for start in range(0, len(rows), batch_size):
        _supabase_request(
            config,
            "POST",
            "/rest/v1/case_chunks",
            json_body=rows[start : start + batch_size],
            headers={"Prefer": "return=minimal"},
        )


def _build_case_chunk_rows(case_id: int, hklii_id: str, case_doc, node_context: dict, embedder) -> list[dict]:
    populated_paragraphs = [paragraph for paragraph in case_doc.paragraphs if paragraph.text]
    chunk_texts = [paragraph.text for paragraph in populated_paragraphs]
    embeddings = embedder.embed_documents(chunk_texts) if chunk_texts else []
    chunk_rows: list[dict] = []
    for index, (paragraph, embedding) in enumerate(zip(populated_paragraphs, embeddings, strict=True), start=1):
        chunk_rows.append(
            {
                "case_id": case_id,
                "hklii_id": hklii_id,
                "chunk_index": index,
                "chunk_text": paragraph.text,
                "section_type": paragraph.paragraph_span or "paragraph",
                "case_name": case_doc.case_name,
                "neutral_citation": case_doc.neutral_citation,
                "court": case_doc.court_name,
                "decision_date": case_doc.decision_date,
                "embedding": json.dumps(embedding),
                "cases_cited": [reference.label for reference in case_doc.cited_cases[:25]],
                "judges_mentioned": case_doc.judges[:10],
                "legislation_cited": [reference.label for reference in case_doc.cited_statutes[:25]],
                "legal_principles": [
                    principle
                    for principle in node_context.get("legal_principles", [])
                    if principle
                ],
            }
        )
    return chunk_rows


def sync_case_document_to_supabase(
    case_doc,
    *,
    bucket: str = "Casebase",
    prefix: str = "casemap/hk_criminal/live_growth",
    catchwords: str = "",
    legal_principles: list[str] | None = None,
    local_path_hint: str = "",
    embedding_backend: str = "auto",
    embedding_model: str = "",
) -> dict:
    config = SupabaseConfig.from_env()
    embedder = create_embedding_backend(backend=embedding_backend, model=embedding_model)
    public_path = urllib_parse.urlparse(case_doc.public_url).path
    hklii_id = _derive_hklii_id(public_path)
    case_storage_path = _upload_bytes_to_storage(
        config,
        bucket,
        json.dumps(
            {
                "hklii_id": hklii_id,
                "public_url": case_doc.public_url,
                "case_name": case_doc.case_name,
                "neutral_citation": case_doc.neutral_citation,
                "court_name": case_doc.court_name,
                "court_code": case_doc.court_code,
                "decision_date": case_doc.decision_date,
                "judges": case_doc.judges,
                "paragraphs": [
                    {"paragraph_span": paragraph.paragraph_span, "text": paragraph.text}
                    for paragraph in case_doc.paragraphs
                ],
                "cited_cases": [{"label": ref.label, "url": ref.url} for ref in case_doc.cited_cases],
                "cited_statutes": [{"label": ref.label, "url": ref.url} for ref in case_doc.cited_statutes],
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        f"{prefix}/cases/{hklii_id}.json",
        content_type="application/json",
    )
    case_json = {
        "hklii_id": hklii_id,
        "case_name": case_doc.case_name,
        "neutral_citation": case_doc.neutral_citation,
        "court": case_doc.court_name,
        "action_number": case_doc.title,
        "decision_date": case_doc.decision_date,
        "judges": "; ".join(case_doc.judges),
        "catchwords": catchwords,
        "legislation_cited": "; ".join(reference.label for reference in case_doc.cited_statutes),
        "cases_cited": "; ".join(reference.label for reference in case_doc.cited_cases),
        "case_url": case_doc.public_url,
        "doc_storage_path": case_storage_path,
        "doc_local_path": local_path_hint,
        "scraped_at": datetime.now(UTC).isoformat(),
    }
    case_id = _upsert_case(config, case_json)
    chunk_rows = _build_case_chunk_rows(
        case_id,
        hklii_id,
        case_doc,
        {"legal_principles": legal_principles or []},
        embedder,
    )
    _replace_case_chunks(config, hklii_id, chunk_rows)
    return {
        "hklii_id": hklii_id,
        "case_id": case_id,
        "case_name": case_doc.case_name,
        "neutral_citation": case_doc.neutral_citation,
        "chunk_count": len(chunk_rows),
        "storage_path": case_storage_path,
        "embedding_backend": embedder.manifest(),
    }


def _prune_prefix_cases(config: SupabaseConfig, bucket: str, prefix: str, keep_hklii_ids: set[str]) -> list[str]:
    rows = _supabase_request(
        config,
        "GET",
        "/rest/v1/cases",
        query={
            "select": "hklii_id,doc_storage_path",
            "doc_storage_path": f"like.{bucket}/{prefix}/cases/%",
        },
    )
    removed: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        hklii_id = row.get("hklii_id", "")
        if not hklii_id or hklii_id in keep_hklii_ids:
            continue
        _supabase_request(
            config,
            "DELETE",
            "/rest/v1/case_chunks",
            query={"hklii_id": f"eq.{hklii_id}"},
            headers={"Prefer": "return=minimal"},
        )
        _supabase_request(
            config,
            "DELETE",
            "/rest/v1/cases",
            query={"hklii_id": f"eq.{hklii_id}"},
            headers={"Prefer": "return=minimal"},
        )
        removed.append(hklii_id)
    return removed


def load_env_file(path: str | Path) -> bool:
    env_path = Path(path).expanduser()
    if not env_path.exists():
        return False
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
    return True


def sync_criminal_artifacts_to_supabase(
    relationship_graph_path: str | Path,
    relationship_output_dir: str | Path,
    *,
    hybrid_output_dir: str | Path | None = None,
    bucket: str = "Casebase",
    prefix: str = "casemap/hk_criminal/latest",
    max_cases: int = 40,
    embedding_backend: str = "sentence-transformers",
    embedding_model: str = "",
    prune_prefix_cases: bool = False,
) -> dict:
    config = SupabaseConfig.from_env()
    relationship_path = Path(relationship_graph_path).expanduser().resolve()
    relationship_dir = Path(relationship_output_dir).expanduser().resolve()
    hybrid_dir = Path(hybrid_output_dir).expanduser().resolve() if hybrid_output_dir else None
    payload = json.loads(relationship_path.read_text(encoding="utf-8"))

    uploaded_files: list[str] = []
    for local_path, remote_path in _artifact_upload_targets(prefix, relationship_dir, hybrid_dir):
        uploaded_files.append(_upload_file_to_storage(config, bucket, local_path, remote_path))

    crawler = HKLIICrawler()
    embedder = create_embedding_backend(backend=embedding_backend, model=embedding_model)
    synced_cases: list[dict] = []
    skipped_cases: list[str] = []
    sync_errors: list[dict] = []
    pruned_cases: list[str] = []
    seen_paths: set[str] = set()

    case_nodes = sorted(
        [node for node in payload.get("nodes", []) if node.get("type") == "case"],
        key=_case_priority,
        reverse=True,
    )
    for node in case_nodes:
        public_path = _derive_public_path(node)
        if not public_path or public_path in seen_paths:
            continue
        seen_paths.add(public_path)
        try:
            case_doc = crawler.fetch_case_document(public_path)
        except Exception:
            skipped_cases.append(node.get("label", public_path))
            continue
        hklii_id = _derive_hklii_id(public_path)
        sample_text = " ".join(paragraph.text for paragraph in case_doc.paragraphs[:8] if paragraph.text)
        if not _looks_criminally_relevant(node, case_doc.case_name, title=case_doc.title, sample_text=sample_text):
            skipped_cases.append(case_doc.case_name or node.get("label", public_path))
            sync_errors.append({"hklii_id": hklii_id, "error": "Skipped non-criminal cited authority"})
            continue
        try:
            case_storage_path = _upload_bytes_to_storage(
                config,
                bucket,
                json.dumps(
                    {
                        "hklii_id": hklii_id,
                        "public_url": case_doc.public_url,
                        "case_name": case_doc.case_name,
                        "neutral_citation": case_doc.neutral_citation,
                        "court_name": case_doc.court_name,
                        "court_code": case_doc.court_code,
                        "decision_date": case_doc.decision_date,
                        "judges": case_doc.judges,
                        "paragraphs": [
                            {"paragraph_span": paragraph.paragraph_span, "text": paragraph.text}
                            for paragraph in case_doc.paragraphs
                        ],
                        "cited_cases": [{"label": ref.label, "url": ref.url} for ref in case_doc.cited_cases],
                        "cited_statutes": [{"label": ref.label, "url": ref.url} for ref in case_doc.cited_statutes],
                    },
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8"),
                f"{prefix}/cases/{hklii_id}.json",
                content_type="application/json",
            )
            case_json = {
                "hklii_id": hklii_id,
                "case_name": case_doc.case_name,
                "neutral_citation": case_doc.neutral_citation,
                "court": case_doc.court_name,
                "action_number": case_doc.title,
                "decision_date": case_doc.decision_date,
                "judges": "; ".join(case_doc.judges),
                "catchwords": node.get("summary_en", node.get("summary", "")),
                "legislation_cited": "; ".join(reference.label for reference in case_doc.cited_statutes),
                "cases_cited": "; ".join(reference.label for reference in case_doc.cited_cases),
                "case_url": case_doc.public_url,
                "doc_storage_path": case_storage_path,
                "doc_local_path": str(relationship_path),
                "scraped_at": datetime.now(UTC).isoformat(),
            }
            case_id = _upsert_case(config, case_json)
            chunk_rows = _build_case_chunk_rows(
                case_id,
                hklii_id,
                case_doc,
                {"legal_principles": [principle.get("statement_en", "") for principle in node.get("principles", []) if principle.get("statement_en")]},
                embedder,
            )
            _replace_case_chunks(config, hklii_id, chunk_rows)
            synced_cases.append(
                {
                    "hklii_id": hklii_id,
                    "case_name": case_doc.case_name,
                    "neutral_citation": case_doc.neutral_citation,
                    "chunk_count": len(chunk_rows),
                }
            )
            if len(synced_cases) >= max_cases:
                break
        except Exception as exc:
            skipped_cases.append(node.get("label", public_path))
            sync_errors.append({"hklii_id": hklii_id, "error": str(exc)})
            continue

    if prune_prefix_cases:
        pruned_cases = _prune_prefix_cases(
            config,
            bucket,
            prefix,
            {case["hklii_id"] for case in synced_cases},
        )

    return {
        "uploaded_file_count": len(uploaded_files),
        "uploaded_files": uploaded_files,
        "synced_case_count": len(synced_cases),
        "synced_cases": synced_cases,
        "pruned_cases": pruned_cases,
        "skipped_cases": skipped_cases,
        "sync_errors": sync_errors,
        "crawler_warnings": crawler.warnings,
        "embedding_backend": embedder.manifest(),
    }
