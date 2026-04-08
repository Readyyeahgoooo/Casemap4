from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from casemap.hybrid_graph import HybridGraphStore
from casemap.viewer import render_hybrid_hierarchy

HYBRID_ARTIFACT_DIR = BASE_DIR / "artifacts" / "hybrid_graph"
HYBRID_GRAPH_PATH = HYBRID_ARTIFACT_DIR / "hierarchical_graph.json"

_store: HybridGraphStore | None = None


def _load_store() -> HybridGraphStore | None:
    global _store
    if _store is None and HYBRID_GRAPH_PATH.exists():
        _store = HybridGraphStore.from_file(HYBRID_GRAPH_PATH)
    return _store


def _respond(start_response, status: str, body: bytes, content_type: str) -> list[bytes]:
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    start_response(status, headers)
    return [body]


def _json_response(start_response, payload: dict | list, status: str = "200 OK") -> list[bytes]:
    return _respond(start_response, status, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8")


def _html_response(start_response, html: str, status: str = "200 OK") -> list[bytes]:
    return _respond(start_response, status, html.encode("utf-8"), "text/html; charset=utf-8")


def _read_json_body(environ) -> dict:
    try:
        length = int(environ.get("CONTENT_LENGTH", "0") or "0")
    except ValueError:
        length = 0
    if length <= 0:
        return {}
    body = environ["wsgi.input"].read(length)
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()
    store = _load_store()

    if store is None:
        return _json_response(
            start_response,
            {
                "error": "hierarchical_graph.json not found",
                "expected_path": str(HYBRID_GRAPH_PATH),
            },
            status="503 Service Unavailable",
        )

    if method == "GET" and path in {"/", "/index.html"}:
        return _html_response(start_response, render_hybrid_hierarchy(store.bundle, page_mode="internal"))

    if method == "GET" and path == "/health":
        return _json_response(start_response, {"ok": True, "graph_present": HYBRID_GRAPH_PATH.exists(), "manifest": store.manifest()})

    if method == "GET" and path == "/api/manifest":
        return _json_response(start_response, store.manifest())

    if method == "GET" and path == "/api/tree":
        return _json_response(start_response, store.tree_counts())

    if method == "GET" and path.startswith("/api/topic/"):
        topic_id = unquote(path.removeprefix("/api/topic/"))
        try:
            return _json_response(start_response, store.topic_detail(topic_id))
        except KeyError:
            return _json_response(start_response, {"error": "Topic not found", "topic_id": topic_id}, status="404 Not Found")

    if method == "GET" and path.startswith("/api/case/"):
        case_id = unquote(path.removeprefix("/api/case/"))
        try:
            return _json_response(start_response, store.case_card(case_id))
        except KeyError:
            return _json_response(start_response, {"error": "Case not found", "case_id": case_id}, status="404 Not Found")

    if method == "GET" and path == "/api/graph/focus":
        params = parse_qs(environ.get("QUERY_STRING", ""))
        node_id = params.get("id", [""])[0].strip()
        try:
            depth = max(1, min(int(params.get("depth", ["1"])[0]), 2))
        except ValueError:
            depth = 1
        if not node_id:
            return _json_response(start_response, {"error": "Missing query string parameter 'id'"}, status="400 Bad Request")
        try:
            return _json_response(start_response, store.focus_graph(node_id, depth=depth))
        except KeyError:
            return _json_response(start_response, {"error": "Node not found", "id": node_id}, status="404 Not Found")

    if path == "/api/query" and method in {"GET", "POST"}:
        if method == "POST":
            body = _read_json_body(environ)
            question = str(body.get("question", "")).strip()
            top_k = body.get("top_k", 5)
            mode = str(body.get("mode", "extractive")).strip() or "extractive"
            model = str(body.get("model", "")).strip()
            max_citations = body.get("max_citations", 8)
        else:
            params = parse_qs(environ.get("QUERY_STRING", ""))
            question = params.get("q", [""])[0].strip()
            top_k = params.get("top_k", ["5"])[0]
            mode = params.get("mode", ["extractive"])[0].strip() or "extractive"
            model = params.get("model", [""])[0].strip()
            max_citations = params.get("max_citations", ["8"])[0]
        try:
            bounded_top_k = max(1, min(int(top_k), 10))
        except (TypeError, ValueError):
            bounded_top_k = 5
        try:
            bounded_max_citations = max(2, min(int(max_citations), 20))
        except (TypeError, ValueError):
            bounded_max_citations = 8
        if not question:
            return _json_response(start_response, {"error": "Missing question"}, status="400 Bad Request")
        return _json_response(
            start_response,
            store.query(
                question,
                top_k=bounded_top_k,
                mode=mode,
                model=model,
                max_citations=bounded_max_citations,
            ),
        )

    return _json_response(
        start_response,
        {
            "error": "Not found",
            "routes": [
                "/",
                "/health",
                "/api/manifest",
                "/api/tree",
                "/api/topic/{topic_id}",
                "/api/case/{case_id}",
                "/api/graph/focus?id=node_id&depth=1",
                "/api/query",
            ],
        },
        status="404 Not Found",
    )
