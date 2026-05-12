"""Supabase `case_chunks` runtime retrieval.

Primary path: PostgREST RPC ``match_case_chunks`` (pgvector + full-text + metadata
filters, ranked in SQL). Falls back to legacy PostgREST ``ilike`` scans only when
the RPC is unavailable (migration not applied) or ``CASEMAP_SUPABASE_USE_CHUNK_RPC=0``.

Runtime must use ``SUPABASE_PUBLISHABLE_KEY`` only (never the service role in the
browser). Optional ``CASEMAP_SUPABASE_ALLOW_SERVICE_QUERY=1`` allows the service
role on trusted servers for debugging only.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import ssl

from .graphrag import tokenize

EMBEDDING_VECTOR_DIM = int(os.environ.get("CASEMAP_EMBEDDING_VECTOR_DIM", "384"))
DEFAULT_CHUNK_RPC = os.environ.get("CASEMAP_SUPABASE_CHUNK_RPC", "match_case_chunks").strip() or "match_case_chunks"

_SKIP_NEEDLES = frozenset(
    {
        "hong",
        "kong",
        "what",
        "when",
        "where",
        "which",
        "your",
        "that",
        "this",
        "from",
        "with",
        "have",
        "been",
        "will",
        "does",
        "hksar",
        "criminal",
        "crime",
        "case",
        "cases",
        "charged",
        "charge",
    }
)


@dataclass
class SupabaseRuntimeConfig:
    url: str
    api_key: str

    @classmethod
    def from_env(cls) -> SupabaseRuntimeConfig | None:
        """Prefer publishable key for edge/runtime; never require service role."""
        url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
        publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
        if url and publishable:
            return cls(url=url, api_key=publishable)
        if os.environ.get("CASEMAP_SUPABASE_ALLOW_SERVICE_QUERY", "").strip() == "1":
            service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            if url and service:
                return cls(url=url, api_key=service)
        return None


def _request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str],
    body: bytes | None = None,
    timeout_seconds: int = 45,
) -> list[dict] | dict:
    request = urllib_request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", "ignore")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {detail[:800]}") from exc
    except urllib_error.URLError as exc:
        reason = getattr(exc, "reason", "")
        if "CERTIFICATE_VERIFY_FAILED" not in str(reason):
            raise
        with urllib_request.urlopen(
            request, timeout=timeout_seconds, context=ssl._create_unverified_context()
        ) as response:
            raw = response.read().decode("utf-8", "ignore")
    return json.loads(raw or "null")


def _needles(question: str, classification: dict | None) -> list[str]:
    cl = classification or {}
    needles: list[str] = []
    for cand in cl.get("offence_candidates") or []:
        if not isinstance(cand, dict):
            continue
        needles.extend(str(k) for k in cand.get("keyword_hits") or [] if len(str(k)) >= 3)
    for hit in cl.get("criminal_hits") or []:
        if isinstance(hit, str) and len(hit) >= 3:
            needles.append(hit.lower())
    primary = cl.get("primary_ordinance") or {}
    fam = str(primary.get("offence_family", "") or "")
    if fam:
        needles.extend(tokenize(fam.replace("_", " ")))
    for tok in tokenize(question):
        tl = tok.lower()
        if len(tl) >= 4 and tl not in _SKIP_NEEDLES:
            needles.append(tl)
    out: list[str] = []
    seen: set[str] = set()
    for n in needles:
        n = str(n).lower().strip()
        if len(n) < 3 or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out[:10]


def _lexical_chunk_score(question: str, row: dict) -> float:
    principles = row.get("legal_principles") or []
    if isinstance(principles, str):
        principles = [principles]
    blob = " ".join(
        [
            str(row.get("chunk_text") or ""),
            str(row.get("case_name") or ""),
            str(row.get("neutral_citation") or ""),
            " ".join(str(p) for p in principles if p),
        ]
    )
    qt = set(tokenize(question))
    tt = set(tokenize(blob))
    overlap = len(qt & tt)
    if not qt:
        return 0.0
    return overlap / max(math.sqrt(len(tt) * len(qt)), 1.0)


def _parse_embedding(raw: object) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, list) and raw and isinstance(raw[0], (int, float)):
        return [float(x) for x in raw]
    if isinstance(raw, str) and raw.strip().startswith("["):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], (int, float)):
            return [float(x) for x in parsed]
    return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    ma = math.sqrt(sum(x * x for x in a))
    mb = math.sqrt(sum(y * y for y in b))
    if ma <= 0 or mb <= 0:
        return 0.0
    return max(0.0, dot / (ma * mb))


_query_embedder: Any | None = None


def _embed_query_sentence_transformers(text: str) -> list[float]:
    global _query_embedder
    if _query_embedder is None:
        from .embeddings import create_embedding_backend

        model = os.environ.get("CASEMAP_QUERY_EMBEDDING_MODEL", "").strip()
        backend = os.environ.get(
            "CASEMAP_QUERY_EMBEDDING_BACKEND", "sentence-transformers"
        ).strip()
        _query_embedder = create_embedding_backend(
            backend=backend,
            model=model,
        )
    return _query_embedder.embed(text)


def _rpc_headers(config: SupabaseRuntimeConfig) -> dict[str, str]:
    return {
        "apikey": config.api_key,
        "Authorization": f"Bearer {config.api_key}",
        "Accept": "application/json",
        "Accept-Profile": "public",
        "Content-Profile": "public",
    }


def _classification_rpc_filters(classification: dict | None) -> dict[str, Any]:
    cl = classification or {}
    primary = cl.get("primary_ordinance") or {}
    offence_family = str(primary.get("offence_family") or "").strip() or None
    topic_label = ""
    for cand in cl.get("offence_candidates") or []:
        if isinstance(cand, dict) and cand.get("keyword_hits"):
            topic_label = str(cand["keyword_hits"][0])
            break
    topic_label = topic_label.strip() or None
    area = str(cl.get("area") or "").strip() or None
    return {
        "p_legal_domain": "criminal",
        "p_offence_family": offence_family,
        "p_topic_label": topic_label,
        "p_classification_area": area,
    }


def _fetch_via_rpc(
    config: SupabaseRuntimeConfig,
    *,
    rpc_name: str,
    question: str,
    classification: dict | None,
    match_count: int,
    query_embedding: list[float] | None,
) -> list[dict]:
    filters = _classification_rpc_filters(classification)
    payload: dict[str, Any] = {
        "query_text": question,
        "match_count": match_count,
        "fts_weight": float(os.environ.get("CASEMAP_CHUNK_FTS_WEIGHT", "0.35")),
        "vec_weight": float(os.environ.get("CASEMAP_CHUNK_VEC_WEIGHT", "0.65")),
        **filters,
    }
    if query_embedding is not None and len(query_embedding) == EMBEDDING_VECTOR_DIM:
        payload["query_embedding"] = query_embedding
    else:
        payload["query_embedding"] = None

    url = f"{config.url}/rest/v1/rpc/{urllib_parse.quote(rpc_name)}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {**_rpc_headers(config), "Content-Type": "application/json", "Prefer": "return=representation"}
    result = _request_json(url, method="POST", headers=headers, body=body, timeout_seconds=60)
    if not isinstance(result, list):
        return []
    return result


def _fetch_ranked_ilike_legacy(
    config: SupabaseRuntimeConfig,
    question: str,
    *,
    classification: dict | None,
    limit_per_needle: int,
    max_total_rows: int,
    use_vector: bool,
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    needles = _needles(question, classification)
    if not needles:
        needles = [tok for tok in tokenize(question) if len(tok) >= 5][:3]
    headers = _rpc_headers(config)
    rows_by_id: dict[Any, dict] = {}
    for needle in needles[:5]:
        safe = "".join(ch for ch in needle if ch.isalnum() or ch in {"-", "_"}).strip()
        if len(safe) < 2:
            continue
        query = urllib_parse.urlencode(
            {
                "select": "id,case_id,hklii_id,chunk_index,chunk_text,case_name,neutral_citation,legal_principles,embedding",
                "limit": str(limit_per_needle),
                "chunk_text": f"ilike.*{safe}*",
            }
        )
        url = f"{config.url}/rest/v1/case_chunks?{query}"
        try:
            batch = _request_json(url, headers=headers)
        except Exception as exc:  # pragma: no cover - network
            warnings.append(f"supabase_chunks:{needle}: {exc}")
            continue
        if not isinstance(batch, list):
            continue
        for row in batch:
            rid = row.get("id")
            if rid is not None:
                rows_by_id[rid] = row
            else:
                rows_by_id[id(row)] = row
            if len(rows_by_id) >= max_total_rows:
                break
        if len(rows_by_id) >= max_total_rows:
            break

    rows = list(rows_by_id.values())
    if not rows:
        return [], warnings

    query_vec: list[float] | None = None
    if use_vector:
        try:
            query_vec = _embed_query_sentence_transformers(question)
        except Exception as exc:
            warnings.append(f"query_embed:{exc}")
            query_vec = None
    ranked: list[tuple[float, dict]] = []
    for row in rows:
        lex = _lexical_chunk_score(question, row)
        vec = 0.0
        emb = _parse_embedding(row.get("embedding"))
        if query_vec and emb and len(query_vec) == len(emb):
            vec = _cosine(query_vec, emb)
        score = 0.58 * lex + 0.42 * vec if vec > 0.0 else lex
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [r for _, r in ranked], warnings


def fetch_ranked_case_chunks(
    config: SupabaseRuntimeConfig,
    question: str,
    *,
    classification: dict | None = None,
    limit_per_needle: int = 90,
    max_total_rows: int = 400,
    use_vector: bool | None = None,
    match_count: int | None = None,
) -> tuple[list[dict], list[str]]:
    """Return (ranked_chunk_rows, warnings). Prefer RPC; fall back to ilike + client rerank."""
    warnings: list[str] = []
    if use_vector is None:
        use_vector = os.environ.get("CASEMAP_QUERY_EMBEDDING_BACKEND", "").strip().lower() == "sentence-transformers"
    mc = match_count if match_count is not None else int(os.environ.get("CASEMAP_SUPABASE_CHUNK_MATCH_COUNT", "24"))

    use_rpc = os.environ.get("CASEMAP_SUPABASE_USE_CHUNK_RPC", "1").strip() not in {"0", "false", "off", "no"}
    rpc_name = DEFAULT_CHUNK_RPC

    query_embedding: list[float] | None = None
    if use_vector:
        try:
            query_embedding = _embed_query_sentence_transformers(question)
            if len(query_embedding) != EMBEDDING_VECTOR_DIM:
                warnings.append(
                    f"query embedding dim {len(query_embedding)} != {EMBEDDING_VECTOR_DIM}; RPC vector leg disabled"
                )
                query_embedding = None
        except Exception as exc:
            warnings.append(f"query_embed:{exc}")
            query_embedding = None

    if use_rpc:
        try:
            rows = _fetch_via_rpc(
                config,
                rpc_name=rpc_name,
                question=question,
                classification=classification,
                match_count=mc,
                query_embedding=query_embedding,
            )
            if rows:
                for row in rows:
                    row.setdefault("_retrieval_mode", "rpc")
                return rows, warnings
            warnings.append("chunk_rpc:empty_result")
        except RuntimeError as exc:
            msg = str(exc).lower()
            if "404" in msg or "pgrst" in msg or "42883" in msg or "function" in msg:
                warnings.append(f"chunk_rpc_unavailable:{exc!s}")
            else:
                warnings.append(f"chunk_rpc_error:{exc!s}")

    legacy_rows, lw = _fetch_ranked_ilike_legacy(
        config,
        question,
        classification=classification,
        limit_per_needle=limit_per_needle,
        max_total_rows=max_total_rows,
        use_vector=use_vector,
    )
    warnings.extend(lw)
    for row in legacy_rows:
        row.setdefault("_retrieval_mode", "ilike_legacy")
    return legacy_rows, warnings


def chunks_to_citations(rows: list[dict], *, base_support_score: float = 0.34) -> list[dict]:
    """Shape ranked chunk rows like hybrid graph citations."""
    cites: list[dict] = []
    for position, row in enumerate(rows[:16], start=1):
        quote = str(row.get("chunk_text") or "").strip()
        if len(quote) < 30:
            continue
        combo = float(row.get("combined_score", 0) or 0)
        support = max(base_support_score, min(0.95, base_support_score + min(0.5, combo) * 0.12 + 0.02 / position))
        cites.append(
            {
                "case_id": f"case_chunk:{row.get('hklii_id', '')}:{row.get('chunk_index', '')}",
                "focus_node_id": f"case_chunk:{row.get('hklii_id', '')}",
                "case_name": str(row.get("case_name") or ""),
                "neutral_citation": str(row.get("neutral_citation") or ""),
                "paragraph_span": str(row.get("chunk_index") or ""),
                "principle_label": "Supabase case_chunks",
                "quote": quote[:4000],
                "hklii_deep_link": "",
                "links": [],
                "lineage_titles": [],
                "lineage_ids": [],
                "matched_lineage_ids": [],
                "hklii_verified": True,
                "support_score": round(support, 6),
                "supabase_chunk_id": row.get("id"),
                "hklii_id": str(row.get("hklii_id") or ""),
                "supabase_retrieval_mode": row.get("_retrieval_mode", ""),
            }
        )
    return cites


def merge_remote_chunks_into_result(
    result: dict,
    extra_citations: list[dict],
    *,
    max_citations: int,
) -> dict:
    existing = list(result.get("citations") or [])
    keys = {(c.get("case_id"), (c.get("quote") or "")[:120]) for c in existing}
    merged = list(existing)
    for c in sorted(extra_citations, key=lambda x: x.get("support_score", 0), reverse=True):
        k = (c.get("case_id"), (c.get("quote") or "")[:120])
        if k in keys:
            continue
        keys.add(k)
        merged.append(c)
    merged.sort(key=lambda x: x.get("support_score", 0), reverse=True)
    result = dict(result)
    result["citations"] = merged[:max_citations]
    trace = dict(result.get("retrieval_trace") or {})
    trace["supabase_chunks_added"] = sum(
        1 for c in result["citations"] if str(c.get("case_id", "")).startswith("case_chunk:")
    )
    result["retrieval_trace"] = trace
    return result
