from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import os


VISIBLE_NODE_LABELS = ("Module", "Subground", "Topic", "Case", "Statute", "AuthorityLineage")
VISIBLE_EDGE_TYPES = ("CONTAINS", "BELONGS_TO_TOPIC", "CITES", "FOLLOWS", "APPLIES", "DISTINGUISHES", "HAS_MEMBER", "ABOUT_TOPIC")


@dataclass
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> "Neo4jConfig | None":
        uri = os.environ.get("NEO4J_URI", "").strip()
        username = os.environ.get("NEO4J_USERNAME", "").strip()
        password = os.environ.get("NEO4J_PASSWORD", "").strip()
        database = os.environ.get("NEO4J_DATABASE", "").strip() or "neo4j"
        if not (uri and username and password):
            return None
        return cls(uri=uri, username=username, password=password, database=database)


class Neo4jGraphStore:
    def __init__(self, driver: Any, database: str) -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def from_env(cls) -> "Neo4jGraphStore | None":
        config = Neo4jConfig.from_env()
        if config is None:
            return None
        try:
            from neo4j import GraphDatabase
        except ImportError:
            return None
        driver = GraphDatabase.driver(config.uri, auth=(config.username, config.password))
        try:
            with driver.session(database=config.database) as session:
                session.run("RETURN 1 AS ok").single()
        except Exception:
            try:
                driver.close()
            except Exception:
                pass
            return None
        return cls(driver, config.database)

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception:
            pass

    def _run(self, query: str, **params: Any) -> list[dict]:
        with self._driver.session(database=self._database) as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def status(self) -> dict:
        return {
            "enabled": True,
            "database": self._database,
            "uri": os.environ.get("NEO4J_URI", "").strip(),
        }

    def manifest(self) -> dict:
        query = """
        CALL {
          MATCH (n)
          RETURN count(n) AS node_count
        }
        CALL {
          MATCH ()-[r]->()
          RETURN count(r) AS edge_count
        }
        CALL {
          MATCH (c:Case)
          RETURN count(c) AS case_count
        }
        CALL {
          MATCH (s:Statute)
          RETURN count(s) AS statute_count
        }
        RETURN node_count, edge_count, case_count, statute_count
        """
        row = self._run(query)[0]
        return {
            "title": "Hong Kong Criminal Law Neo4j Knowledge Graph",
            "viewer_heading_public": "Hong Kong Criminal Law Neo4j Knowledge Graph",
            "legal_domain": "criminal",
            "node_count": row.get("node_count", 0),
            "edge_count": row.get("edge_count", 0),
            "case_count": row.get("case_count", 0),
            "statute_count": row.get("statute_count", 0),
            "data_source": "neo4j",
            "database": self._database,
        }

    def project_bundle(self) -> dict:
        nodes_query = """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN $visible_labels)
        RETURN
          n.id AS id,
          CASE
            WHEN 'Module' IN labels(n) THEN 'Module'
            WHEN 'Subground' IN labels(n) THEN 'Subground'
            WHEN 'Topic' IN labels(n) THEN 'Topic'
            WHEN 'Case' IN labels(n) THEN 'Case'
            WHEN 'Statute' IN labels(n) THEN 'Statute'
            WHEN 'AuthorityLineage' IN labels(n) THEN 'AuthorityLineage'
            ELSE head(labels(n))
          END AS type,
          coalesce(n.label_en, n.case_name, n.label, n.id) AS label,
          coalesce(n.summary_en, n.summary, '') AS summary
        """
        node_rows = self._run(nodes_query, visible_labels=list(VISIBLE_NODE_LABELS))
        node_ids = [row["id"] for row in node_rows if row.get("id")]
        edge_rows: list[dict] = []
        if node_ids:
            edges_query = """
            MATCH (source)-[r]->(target)
            WHERE source.id IN $node_ids
              AND target.id IN $node_ids
              AND type(r) IN $visible_edge_types
            RETURN DISTINCT source.id AS source, target.id AS target, type(r) AS type
            """
            edge_rows = self._run(
                edges_query,
                node_ids=node_ids,
                visible_edge_types=list(VISIBLE_EDGE_TYPES),
            )
        return {
            "meta": self.manifest(),
            "nodes": node_rows,
            "edges": edge_rows,
            "case_cards": {},
            "tree": {"id": "neo4j_runtime", "label_en": "Neo4j Runtime Projection", "modules": []},
        }

    def focus_graph(self, node_id: str, depth: int = 1) -> dict:
        bounded_depth = max(1, min(int(depth), 2))
        node_query = """
        MATCH (anchor {id: $node_id})
        RETURN anchor.id AS id
        LIMIT 1
        """
        if not self._run(node_query, node_id=node_id):
            raise KeyError(node_id)
        focus_nodes_query = f"""
        MATCH (anchor {{id: $node_id}})
        MATCH p=(anchor)-[*0..{bounded_depth}]-(n)
        UNWIND nodes(p) AS member
        WITH DISTINCT member
        RETURN
          member.id AS id,
          CASE
            WHEN 'Module' IN labels(member) THEN 'Module'
            WHEN 'Subground' IN labels(member) THEN 'Subground'
            WHEN 'Topic' IN labels(member) THEN 'Topic'
            WHEN 'Case' IN labels(member) THEN 'Case'
            WHEN 'Statute' IN labels(member) THEN 'Statute'
            WHEN 'AuthorityLineage' IN labels(member) THEN 'AuthorityLineage'
            ELSE head(labels(member))
          END AS type,
          coalesce(member.label_en, member.case_name, member.label, member.id) AS label,
          coalesce(member.summary_en, member.summary, '') AS summary
        """
        nodes = self._run(focus_nodes_query, node_id=node_id)
        node_ids = [row["id"] for row in nodes if row.get("id")]
        edges: list[dict] = []
        if node_ids:
            focus_edges_query = """
            MATCH (source)-[r]->(target)
            WHERE source.id IN $node_ids
              AND target.id IN $node_ids
            RETURN DISTINCT source.id AS source, target.id AS target, type(r) AS type
            """
            edges = self._run(focus_edges_query, node_ids=node_ids)
        facets: dict[str, int] = {}
        for node in nodes:
            node_type = node.get("type", "Unknown")
            facets[node_type] = facets.get(node_type, 0) + 1
        return {
            "focus": node_id,
            "nodes": nodes,
            "edges": edges,
            "facets": facets,
            "data_source": "neo4j",
        }
