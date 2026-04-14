// Requires APOC for dynamic labels.
// Load hierarchical_graph.json externally and pass {nodes: [...], edges: [...]} as parameters.
UNWIND $nodes AS node
CALL apoc.merge.node([node.type], {id: node.id}, node, node) YIELD node AS merged_node
RETURN count(merged_node) AS merged_nodes;

UNWIND $edges AS edge
MATCH (source {id: edge.source})
MATCH (target {id: edge.target})
CALL apoc.merge.relationship(source, edge.type, {source: edge.source, target: edge.target}, edge, target)
YIELD rel
RETURN count(rel) AS merged_relationships;
