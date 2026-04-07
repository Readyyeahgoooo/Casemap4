from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from casemap.graphrag import RerankedRetriever
from casemap.hybrid_graph import DeterminatorPipeline, HybridGraphStore, KnowledgeGrowthWriter, _infer_legal_domain
from casemap.neo4j_store import Neo4jGraphStore
from casemap.viewer import render_determinator_page, render_hybrid_hierarchy, render_knowledge_graph, render_relationship_map

MVP_ARTIFACT_DIR = BASE_DIR / "artifacts" / "contract_big"
MVP_GRAPH_PATH = MVP_ARTIFACT_DIR / "graph.json"
MVP_CHUNK_PATH = MVP_ARTIFACT_DIR / "chunks.json"
MVP_MANIFEST_PATH = MVP_ARTIFACT_DIR / "manifest.json"
MVP_SAMPLE_QUERY_PATH = MVP_ARTIFACT_DIR / "sample_queries.json"
MVP_MAP_PATH = MVP_ARTIFACT_DIR / "knowledge_map.html"

PUBLIC_RELATIONSHIP_DIR = BASE_DIR / "artifacts" / "public_relationship_graph"
PUBLIC_RELATIONSHIP_GRAPH_PATH = PUBLIC_RELATIONSHIP_DIR / "relationship_graph.json"
PUBLIC_RELATIONSHIP_MANIFEST_PATH = PUBLIC_RELATIONSHIP_DIR / "manifest.json"
PUBLIC_RELATIONSHIP_MAP_PATH = PUBLIC_RELATIONSHIP_DIR / "relationship_map.html"
PUBLIC_RELATIONSHIP_TREE_PATH = PUBLIC_RELATIONSHIP_DIR / "relationship_tree.html"
PUBLIC_RELATIONSHIP_MONITOR_PATH = PUBLIC_RELATIONSHIP_DIR / "monitor_report.html"
PUBLIC_RELATIONSHIP_MONITOR_JSON_PATH = PUBLIC_RELATIONSHIP_DIR / "monitor_report.json"
PUBLIC_RELATIONSHIP_PROGRESS_PATH = PUBLIC_RELATIONSHIP_DIR / "build_progress.json"

HYBRID_ARTIFACT_DIR = BASE_DIR / "artifacts" / "hybrid_graph"
HYBRID_GRAPH_PATH = HYBRID_ARTIFACT_DIR / "hierarchical_graph.json"
HYBRID_MANIFEST_PATH = HYBRID_ARTIFACT_DIR / "manifest.json"
HYBRID_PUBLIC_PROJECTION_PATH = HYBRID_ARTIFACT_DIR / "public_projection.json"

CRIMINAL_RELATIONSHIP_DIR = BASE_DIR / "artifacts" / "hk_criminal_relationship"
CRIMINAL_RELATIONSHIP_GRAPH_PATH = CRIMINAL_RELATIONSHIP_DIR / "relationship_graph.json"
CRIMINAL_RELATIONSHIP_MANIFEST_PATH = CRIMINAL_RELATIONSHIP_DIR / "manifest.json"
CRIMINAL_RELATIONSHIP_MAP_PATH = CRIMINAL_RELATIONSHIP_DIR / "relationship_map.html"
CRIMINAL_RELATIONSHIP_TREE_PATH = CRIMINAL_RELATIONSHIP_DIR / "relationship_tree.html"
CRIMINAL_RELATIONSHIP_MONITOR_PATH = CRIMINAL_RELATIONSHIP_DIR / "monitor_report.html"
CRIMINAL_RELATIONSHIP_MONITOR_JSON_PATH = CRIMINAL_RELATIONSHIP_DIR / "monitor_report.json"
CRIMINAL_RELATIONSHIP_PROGRESS_PATH = CRIMINAL_RELATIONSHIP_DIR / "build_progress.json"

CRIMINAL_HYBRID_ARTIFACT_DIR = BASE_DIR / "artifacts" / "hk_criminal_hybrid"
CRIMINAL_HYBRID_GRAPH_PATH = CRIMINAL_HYBRID_ARTIFACT_DIR / "hierarchical_graph.json"
CRIMINAL_HYBRID_MANIFEST_PATH = CRIMINAL_HYBRID_ARTIFACT_DIR / "manifest.json"
CRIMINAL_HYBRID_PUBLIC_PROJECTION_PATH = CRIMINAL_HYBRID_ARTIFACT_DIR / "public_projection.json"

_retriever: RerankedRetriever | None = None
_hybrid_store: HybridGraphStore | None = None
_hybrid_store_path: Path | None = None
_neo4j_store: Neo4jGraphStore | None = None
_neo4j_checked = False


def _artifact_profile() -> str:
    profile = os.environ.get("CASEMAP_PROFILE", "").strip().lower()
    if profile in {"criminal", "hk-criminal", "criminal-law"}:
        return "criminal"
    # Default to criminal for the standalone casemap3 deployment package.
    return "criminal"


def _selected_hybrid_paths() -> tuple[Path, Path, Path]:
    if _artifact_profile() == "criminal":
        return (
            CRIMINAL_HYBRID_GRAPH_PATH,
            CRIMINAL_HYBRID_MANIFEST_PATH,
            CRIMINAL_HYBRID_PUBLIC_PROJECTION_PATH,
        )
    return HYBRID_GRAPH_PATH, HYBRID_MANIFEST_PATH, HYBRID_PUBLIC_PROJECTION_PATH


def _selected_relationship_paths() -> tuple[Path, Path, Path]:
    if _artifact_profile() == "criminal":
        return (
            CRIMINAL_RELATIONSHIP_MANIFEST_PATH,
            CRIMINAL_RELATIONSHIP_MAP_PATH,
            CRIMINAL_RELATIONSHIP_TREE_PATH,
        )
    return (
        PUBLIC_RELATIONSHIP_MANIFEST_PATH,
        PUBLIC_RELATIONSHIP_MAP_PATH,
        PUBLIC_RELATIONSHIP_TREE_PATH,
    )


def _selected_relationship_graph_path() -> Path:
    if _artifact_profile() == "criminal":
        return CRIMINAL_RELATIONSHIP_GRAPH_PATH
    return PUBLIC_RELATIONSHIP_GRAPH_PATH


def _selected_monitor_paths() -> tuple[Path, Path, Path]:
    if _artifact_profile() == "criminal":
        return (
            CRIMINAL_RELATIONSHIP_MONITOR_PATH,
            CRIMINAL_RELATIONSHIP_MONITOR_JSON_PATH,
            CRIMINAL_RELATIONSHIP_PROGRESS_PATH,
        )
    return (
        PUBLIC_RELATIONSHIP_MONITOR_PATH,
        PUBLIC_RELATIONSHIP_MONITOR_JSON_PATH,
        PUBLIC_RELATIONSHIP_PROGRESS_PATH,
    )


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict | list:
    return json.loads(_load_text(path))


def _get_retriever() -> RerankedRetriever | None:
    global _retriever
    if _retriever is None and MVP_GRAPH_PATH.exists() and MVP_CHUNK_PATH.exists():
        _retriever = RerankedRetriever.from_files(MVP_GRAPH_PATH, MVP_CHUNK_PATH)
    return _retriever


def _get_hybrid_store() -> HybridGraphStore | None:
    global _hybrid_store, _hybrid_store_path
    graph_path, _, _ = _selected_hybrid_paths()
    if _hybrid_store is not None and _hybrid_store_path != graph_path:
        _hybrid_store = None
    if _hybrid_store is None and graph_path.exists():
        _hybrid_store = HybridGraphStore.from_file(graph_path)
        _hybrid_store_path = graph_path
    return _hybrid_store


def _get_neo4j_store() -> Neo4jGraphStore | None:
    global _neo4j_store, _neo4j_checked
    if not _neo4j_checked:
        _neo4j_store = Neo4jGraphStore.from_env()
        _neo4j_checked = True
    return _neo4j_store


def _respond(start_response, status: str, body: bytes, content_type: str) -> list[bytes]:
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "public, max-age=60"),
    ]
    start_response(status, headers)
    return [body]


def _json_response(start_response, payload: dict | list, status: str = "200 OK") -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return _respond(start_response, status, body, "application/json; charset=utf-8")


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


def _not_found(start_response) -> list[bytes]:
    payload = {
        "error": "Not found",
        "routes": [
            "/",
            "/graph",
            "/tree",
            "/hierarchy",
            "/internal",
            "/mvp",
            "/relationships",
            "/health",
            "/monitor",
            "/api/manifest",
            "/api/monitor",
            "/api/tree",
            "/api/topic/{topic_id}",
            "/api/case/{case_id}",
            "/api/graph/focus?id=node_id&depth=1",
            "/api/relationship-manifest",
            "/api/sample-queries",
            "/api/query?q=offer+acceptance",
        ],
    }
    return _json_response(start_response, payload, status="404 Not Found")


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()
    hybrid_store = _get_hybrid_store()
    neo4j_store = _get_neo4j_store()
    selected_hybrid_graph_path, selected_hybrid_manifest_path, selected_hybrid_public_projection_path = _selected_hybrid_paths()
    (
        selected_relationship_manifest_path,
        selected_relationship_map_path,
        selected_relationship_tree_path,
    ) = _selected_relationship_paths()
    selected_relationship_graph_path = _selected_relationship_graph_path()
    (
        selected_monitor_path,
        selected_monitor_json_path,
        selected_progress_path,
    ) = _selected_monitor_paths()

    if method not in {"GET", "POST"}:
        return _json_response(start_response, {"error": "Method not allowed"}, status="405 Method Not Allowed")

    if path == "/graph":
        graph_bundle = neo4j_store.project_bundle() if neo4j_store is not None else (hybrid_store.bundle if hybrid_store is not None else None)
        if graph_bundle is None:
            return _html_response(
                start_response,
                "<h1>Casemap</h1><p>The knowledge graph is unavailable because the hybrid graph artifact is missing.</p>",
                status="503 Service Unavailable",
            )
        return _html_response(start_response, render_knowledge_graph(graph_bundle))

    if path in {"/", "/index.html", "/relationships"}:
        if hybrid_store is not None:
            if _infer_legal_domain(hybrid_store.bundle.get("meta")) == "criminal":
                hierarchy_html = render_hybrid_hierarchy(hybrid_store.bundle)
                return _html_response(start_response, render_determinator_page(hybrid_store.bundle, hierarchy_html))
        if selected_relationship_graph_path.exists():
            return _html_response(start_response, render_relationship_map(_load_json(selected_relationship_graph_path)))
        if selected_relationship_map_path.exists():
            return _html_response(start_response, _load_text(selected_relationship_map_path))
        if hybrid_store is not None:
            return _html_response(start_response, render_hybrid_hierarchy(hybrid_store.bundle))
        if selected_relationship_tree_path.exists():
            return _html_response(start_response, _load_text(selected_relationship_tree_path))
        if MVP_MAP_PATH.exists():
            return _html_response(start_response, _load_text(MVP_MAP_PATH))
        return _html_response(
            start_response,
            "<h1>Casemap</h1><p>No public artifact is available in this deployment.</p>",
            status="503 Service Unavailable",
        )

    if path in {"/tree", "/hierarchy"}:
        if hybrid_store is not None:
            return _html_response(start_response, render_hybrid_hierarchy(hybrid_store.bundle))
        if selected_relationship_tree_path.exists():
            return _html_response(start_response, _load_text(selected_relationship_tree_path))
        if selected_relationship_graph_path.exists():
            return _html_response(start_response, render_relationship_map(_load_json(selected_relationship_graph_path)))
        if selected_relationship_map_path.exists():
            return _html_response(start_response, _load_text(selected_relationship_map_path))
        if MVP_MAP_PATH.exists():
            return _html_response(start_response, _load_text(MVP_MAP_PATH))
        return _html_response(
            start_response,
            "<h1>Casemap</h1><p>No public artifact is available in this deployment.</p>",
            status="503 Service Unavailable",
        )

    if path in {"/internal", "/explorer"}:
        if hybrid_store is None:
            return _html_response(
                start_response,
                "<h1>Casemap</h1><p>The internal explorer is unavailable because the hybrid graph artifact is missing.</p>",
                status="503 Service Unavailable",
            )
        return _html_response(start_response, render_hybrid_hierarchy(hybrid_store.bundle, page_mode="internal"))

    if path == "/monitor":
        if selected_monitor_path.exists():
            return _html_response(start_response, _load_text(selected_monitor_path))
        return _html_response(
            start_response,
            "<h1>Casemap</h1><p>The monitor dashboard is not available for the current artifact profile yet.</p>",
            status="503 Service Unavailable",
        )

    if path == "/mvp":
        if not MVP_MAP_PATH.exists():
            return _html_response(
                start_response,
                "<h1>Casemap</h1><p>The MVP knowledge map artifact is not available in this deployment.</p>",
                status="503 Service Unavailable",
            )
        return _html_response(start_response, _load_text(MVP_MAP_PATH))

    if path == "/health":
        return _json_response(
            start_response,
            {
                "ok": True,
                "artifacts_present": {
                    "hybrid_graph": HYBRID_GRAPH_PATH.exists(),
                    "hybrid_manifest": HYBRID_MANIFEST_PATH.exists(),
                    "hybrid_public_projection": HYBRID_PUBLIC_PROJECTION_PATH.exists(),
                    "selected_hybrid_graph": selected_hybrid_graph_path.exists(),
                    "selected_hybrid_manifest": selected_hybrid_manifest_path.exists(),
                    "selected_hybrid_public_projection": selected_hybrid_public_projection_path.exists(),
                    "mvp_graph": MVP_GRAPH_PATH.exists(),
                    "mvp_chunks": MVP_CHUNK_PATH.exists(),
                    "mvp_manifest": MVP_MANIFEST_PATH.exists(),
                    "mvp_map": MVP_MAP_PATH.exists(),
                    "public_relationship_graph": PUBLIC_RELATIONSHIP_GRAPH_PATH.exists(),
                    "public_relationship_manifest": PUBLIC_RELATIONSHIP_MANIFEST_PATH.exists(),
                    "public_relationship_map": PUBLIC_RELATIONSHIP_MAP_PATH.exists(),
                    "public_relationship_tree": PUBLIC_RELATIONSHIP_TREE_PATH.exists(),
                    "public_relationship_monitor": PUBLIC_RELATIONSHIP_MONITOR_PATH.exists(),
                    "public_relationship_monitor_json": PUBLIC_RELATIONSHIP_MONITOR_JSON_PATH.exists(),
                    "public_relationship_build_progress": PUBLIC_RELATIONSHIP_PROGRESS_PATH.exists(),
                    "criminal_relationship_graph": CRIMINAL_RELATIONSHIP_GRAPH_PATH.exists(),
                    "criminal_relationship_manifest": CRIMINAL_RELATIONSHIP_MANIFEST_PATH.exists(),
                    "criminal_relationship_map": CRIMINAL_RELATIONSHIP_MAP_PATH.exists(),
                    "criminal_relationship_tree": CRIMINAL_RELATIONSHIP_TREE_PATH.exists(),
                    "criminal_relationship_monitor": CRIMINAL_RELATIONSHIP_MONITOR_PATH.exists(),
                    "criminal_relationship_monitor_json": CRIMINAL_RELATIONSHIP_MONITOR_JSON_PATH.exists(),
                    "criminal_relationship_build_progress": CRIMINAL_RELATIONSHIP_PROGRESS_PATH.exists(),
                    "criminal_hybrid_graph": CRIMINAL_HYBRID_GRAPH_PATH.exists(),
                    "criminal_hybrid_manifest": CRIMINAL_HYBRID_MANIFEST_PATH.exists(),
                    "criminal_hybrid_public_projection": CRIMINAL_HYBRID_PUBLIC_PROJECTION_PATH.exists(),
                    "neo4j_runtime": neo4j_store is not None,
                    "profile": _artifact_profile(),
                },
            },
        )

    if path == "/api/manifest":
        if neo4j_store is not None and _artifact_profile() == "criminal":
            return _json_response(start_response, neo4j_store.manifest())
        if hybrid_store is not None:
            return _json_response(start_response, hybrid_store.manifest())
        if selected_relationship_manifest_path.exists():
            return _json_response(start_response, _load_json(selected_relationship_manifest_path))
        if not MVP_MANIFEST_PATH.exists():
            return _json_response(start_response, {"error": "manifest.json not found"}, status="503 Service Unavailable")
        return _json_response(start_response, _load_json(MVP_MANIFEST_PATH))

    if path == "/api/monitor":
        if selected_monitor_json_path.exists():
            return _json_response(start_response, _load_json(selected_monitor_json_path))
        if selected_progress_path.exists():
            return _json_response(start_response, _load_json(selected_progress_path))
        return _json_response(start_response, {"error": "monitor artifacts not found"}, status="503 Service Unavailable")

    if path == "/api/tree":
        if hybrid_store is None:
            return _json_response(start_response, {"error": "hybrid graph not available"}, status="503 Service Unavailable")
        return _json_response(start_response, hybrid_store.tree_counts())

    if method == "GET" and path.startswith("/api/topic/"):
        if hybrid_store is None:
            return _json_response(start_response, {"error": "hybrid graph not available"}, status="503 Service Unavailable")
        topic_id = unquote(path.removeprefix("/api/topic/"))
        try:
            return _json_response(start_response, hybrid_store.topic_detail(topic_id))
        except KeyError:
            return _json_response(start_response, {"error": "Topic not found", "topic_id": topic_id}, status="404 Not Found")

    if method == "GET" and path.startswith("/api/case/"):
        if hybrid_store is None:
            return _json_response(start_response, {"error": "hybrid graph not available"}, status="503 Service Unavailable")
        case_id = unquote(path.removeprefix("/api/case/"))
        try:
            return _json_response(start_response, hybrid_store.case_card(case_id))
        except KeyError:
            return _json_response(start_response, {"error": "Case not found", "case_id": case_id}, status="404 Not Found")

    if method == "GET" and path == "/api/graph/focus":
        if hybrid_store is None and neo4j_store is None:
            return _json_response(start_response, {"error": "hybrid graph not available"}, status="503 Service Unavailable")
        params = parse_qs(environ.get("QUERY_STRING", ""))
        node_id = params.get("id", [""])[0].strip()
        try:
            depth = max(1, min(int(params.get("depth", ["1"])[0]), 2))
        except ValueError:
            depth = 1
        if not node_id:
            return _json_response(start_response, {"error": "Missing query string parameter 'id'"}, status="400 Bad Request")
        try:
            if neo4j_store is not None and _artifact_profile() == "criminal":
                return _json_response(start_response, neo4j_store.focus_graph(node_id, depth=depth))
            return _json_response(start_response, hybrid_store.focus_graph(node_id, depth=depth))
        except KeyError:
            return _json_response(start_response, {"error": "Node not found", "id": node_id}, status="404 Not Found")

    if path == "/api/relationship-manifest":
        if not selected_relationship_manifest_path.exists():
            return _json_response(
                start_response,
                {"error": "public relationship manifest not found"},
                status="503 Service Unavailable",
            )
        return _json_response(start_response, _load_json(selected_relationship_manifest_path))

    if path == "/api/sample-queries":
        if not MVP_SAMPLE_QUERY_PATH.exists():
            return _json_response(
                start_response,
                {"error": "sample_queries.json not found"},
                status="503 Service Unavailable",
            )
        return _json_response(start_response, _load_json(MVP_SAMPLE_QUERY_PATH))

    if path == "/api/determinator" and method == "POST":
        if hybrid_store is None:
            return _json_response(start_response, {"error": "Graph not available"}, status="503 Service Unavailable")
        body = _read_json_body(environ)
        question = str(body.get("question", "")).strip()
        mode = str(body.get("mode", "openrouter")).strip() or "openrouter"
        model = str(body.get("model", "")).strip()
        if not question:
            return _json_response(start_response, {"error": "Missing question"}, status="400 Bad Request")
        pipeline = DeterminatorPipeline()
        result = pipeline.query(question, hybrid_store, mode=mode, model=model)
        if result.get("new_knowledge"):
            writer = KnowledgeGrowthWriter()
            graph_path, _, _ = _selected_hybrid_paths()
            writer.persist(result["new_knowledge"], hybrid_store, graph_path)
        return _json_response(start_response, result)

    if path == "/api/query":
        if method == "POST" and hybrid_store is not None:
            body = _read_json_body(environ)
            question = str(body.get("question", "")).strip()
            top_k_raw = body.get("top_k", 5)
            mode = str(body.get("mode", "extractive")).strip() or "extractive"
            model = str(body.get("model", "")).strip()
            max_citations_raw = body.get("max_citations", 8)
            try:
                top_k = max(1, min(int(top_k_raw), 10))
            except (TypeError, ValueError):
                top_k = 5
            try:
                max_citations = max(2, min(int(max_citations_raw), 20))
            except (TypeError, ValueError):
                max_citations = 8
            if not question:
                return _json_response(start_response, {"error": "Missing question"}, status="400 Bad Request")
            return _json_response(
                start_response,
                hybrid_store.query(
                    question,
                    top_k=top_k,
                    mode=mode,
                    model=model,
                    max_citations=max_citations,
                ),
            )

        if method != "GET":
            return _json_response(start_response, {"error": "Method not allowed"}, status="405 Method Not Allowed")

        retriever = _get_retriever()
        if retriever is None:
            return _json_response(
                start_response,
                {"error": "graph artifacts are not available for querying"},
                status="503 Service Unavailable",
            )

        params = parse_qs(environ.get("QUERY_STRING", ""))
        question = params.get("q", [""])[0].strip()
        top_k_raw = params.get("top_k", ["5"])[0]
        try:
            top_k = max(1, min(int(top_k_raw), 10))
        except ValueError:
            top_k = 5

        if not question:
            return _json_response(
                start_response,
                {"error": "Missing query string parameter 'q'"},
                status="400 Bad Request",
            )

        return _json_response(
            start_response,
            {
                "question": question,
                "top_k": top_k,
                "results": retriever.search(question, top_k=top_k),
            },
        )

    return _not_found(start_response)
