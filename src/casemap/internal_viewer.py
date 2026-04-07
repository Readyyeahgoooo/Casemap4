from __future__ import annotations


def render_internal_graph_explorer(title: str) -> str:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root {
      --bg: #f5f0e4;
      --panel: rgba(255, 250, 242, 0.9);
      --panel-strong: rgba(255, 255, 255, 0.92);
      --ink: #1f2328;
      --muted: #6a665e;
      --line: rgba(31, 35, 40, 0.12);
      --line-strong: rgba(31, 35, 40, 0.28);
      --accent: #8f3b1b;
      --soft: #d9cbb2;
      --case: #4d6b57;
      --topic: #b78424;
      --lineage: #205072;
      --module: #5c4a3d;
      --source: #7d6b5f;
      --statute: #6b7280;
      --shadow: 0 18px 44px rgba(31, 35, 40, 0.08);
      --shadow-soft: 0 10px 24px rgba(31, 35, 40, 0.06);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: "Georgia", "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(186, 139, 46, 0.15), transparent 28%),
        radial-gradient(circle at top right, rgba(32, 80, 114, 0.14), transparent 24%),
        linear-gradient(180deg, #f8f3ea 0%, var(--bg) 100%);
    }

    .shell {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr) 420px;
      min-height: 100vh;
    }

    .panel {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 24px 20px;
      overflow-y: auto;
    }

    .panel:last-child {
      border-right: 0;
      border-left: 1px solid var(--line);
    }

    .canvas {
      padding: 28px;
      overflow-y: auto;
    }

    .meta {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    h1, h2, h3 { margin: 0 0 12px; }

    .query {
      display: grid;
      gap: 10px;
      margin: 18px 0 24px;
    }

    input, button {
      font: inherit;
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 12px 14px;
      background: rgba(255, 255, 255, 0.72);
      color: var(--ink);
    }

    button {
      cursor: pointer;
      background: linear-gradient(180deg, rgba(143, 59, 27, 0.96), rgba(124, 45, 18, 0.96));
      color: white;
      border: 0;
    }

    .section {
      margin-bottom: 24px;
    }

    .tree-item, .card, .edge, .focus-card {
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.58);
      border-radius: 16px;
      padding: 12px 14px;
      margin-bottom: 10px;
      box-shadow: var(--shadow-soft);
    }

    .chip {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: rgba(31, 35, 40, 0.08);
      color: var(--muted);
      margin-right: 6px;
      margin-bottom: 6px;
    }

    .chip.case { background: rgba(77, 107, 87, 0.15); color: var(--case); }
    .chip.topic { background: rgba(183, 132, 36, 0.15); color: var(--topic); }
    .chip.lineage { background: rgba(32, 80, 114, 0.12); color: var(--lineage); }
    .chip.module { background: rgba(92, 74, 61, 0.14); color: var(--module); }
    .chip.source { background: rgba(125, 107, 95, 0.15); color: var(--source); }
    .chip.statute { background: rgba(107, 114, 128, 0.14); color: var(--statute); }

    .small {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }

    .list {
      display: grid;
      gap: 10px;
    }

    .empty {
      color: var(--muted);
      font-style: italic;
    }

    .topic-link, .node-link {
      color: var(--accent);
      text-decoration: none;
      border-bottom: 1px solid rgba(143, 59, 27, 0.3);
      cursor: pointer;
    }

    .topic-link:hover, .node-link:hover {
      border-color: rgba(143, 59, 27, 0.7);
    }

    .focus-wrap {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(248, 243, 234, 0.92));
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .focus-topbar {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
      padding: 16px 18px 0;
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .legend span {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
    }

    .swatch {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
    }

    .graph-stage {
      padding: 8px 14px 18px;
    }

    svg {
      width: 100%;
      min-height: 560px;
      display: block;
      overflow: visible;
    }

    .graph-node {
      cursor: pointer;
    }

    .graph-node rect,
    .graph-node ellipse {
      stroke: rgba(31, 35, 40, 0.18);
      stroke-width: 1.4;
      fill: rgba(255, 255, 255, 0.92);
      transition: stroke-width 120ms ease, stroke 120ms ease, transform 120ms ease;
    }

    .graph-node.active rect,
    .graph-node.active ellipse {
      stroke: var(--accent);
      stroke-width: 3;
    }

    .graph-node.case rect,
    .graph-node.case ellipse { fill: rgba(77, 107, 87, 0.14); }
    .graph-node.topic rect,
    .graph-node.topic ellipse { fill: rgba(183, 132, 36, 0.16); }
    .graph-node.lineage rect,
    .graph-node.lineage ellipse { fill: rgba(32, 80, 114, 0.14); }
    .graph-node.module rect,
    .graph-node.module ellipse { fill: rgba(92, 74, 61, 0.14); }
    .graph-node.subground rect,
    .graph-node.subground ellipse { fill: rgba(143, 59, 27, 0.12); }
    .graph-node.source rect,
    .graph-node.source ellipse { fill: rgba(125, 107, 95, 0.12); }
    .graph-node.statute rect,
    .graph-node.statute ellipse { fill: rgba(107, 114, 128, 0.15); }

    .graph-node text {
      fill: var(--ink);
      pointer-events: none;
    }

    .graph-label {
      font-size: 14px;
      font-weight: 600;
    }

    .graph-subtitle {
      font-size: 11px;
      fill: var(--muted);
    }

    .graph-edge {
      fill: none;
      stroke: rgba(31, 35, 40, 0.2);
      stroke-width: 1.5;
      marker-end: url(#arrowhead);
    }

    .graph-edge.active {
      stroke: rgba(143, 59, 27, 0.55);
      stroke-width: 2.2;
    }

    .edge-label {
      font-size: 10px;
      fill: var(--muted);
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .supplement-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }

    .focus-card h3 {
      margin-bottom: 8px;
      font-size: 16px;
    }

    @media (max-width: 1400px) {
      .shell { grid-template-columns: 300px minmax(0, 1fr) 380px; }
      .supplement-grid { grid-template-columns: 1fr; }
    }

    @media (max-width: 1200px) {
      .shell { grid-template-columns: 1fr; }
      .panel, .panel:last-child {
        border-right: 0;
        border-left: 0;
        border-bottom: 1px solid var(--line);
      }
      svg { min-height: 460px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside class="panel">
      <div class="meta">Internal Explorer</div>
      <h1>__TITLE__</h1>
      <p class="small">This explorer now renders a real internal case graph. It still uses the API endpoints, but the center panel draws a structured graph instead of leaving the focus area blank.</p>
      <form id="queryForm" class="query">
        <input id="queryInput" type="search" placeholder="Ask about implied terms, penalties, vacant possession...">
        <button type="submit">Run Graph Query</button>
      </form>
      <div class="section">
        <div class="meta">Modules</div>
        <div id="treePanel" class="list"><div class="empty">Loading tree...</div></div>
      </div>
    </aside>
    <main class="canvas">
      <div class="section">
        <div class="meta">Focus Graph</div>
        <div class="focus-topbar">
          <div>
            <h2 id="focusTitle">Loading graph...</h2>
            <div id="focusSummary" class="small">Preparing the internal graph canvas.</div>
          </div>
          <div class="legend">
            <span><i class="swatch" style="background: rgba(183, 132, 36, 0.8)"></i>Topic</span>
            <span><i class="swatch" style="background: rgba(77, 107, 87, 0.8)"></i>Case</span>
            <span><i class="swatch" style="background: rgba(32, 80, 114, 0.8)"></i>Lineage</span>
            <span><i class="swatch" style="background: rgba(107, 114, 128, 0.8)"></i>Statute</span>
          </div>
        </div>
        <div class="focus-wrap">
          <div class="graph-stage">
            <svg id="graphCanvas" viewBox="0 0 1440 760" preserveAspectRatio="xMidYMid meet" aria-label="Internal case graph"></svg>
          </div>
        </div>
        <div class="supplement-grid">
          <div class="focus-card">
            <div class="meta">Visible Nodes</div>
            <h3>Nodes</h3>
            <div id="graphNodes" class="list"><div class="empty">No graph loaded.</div></div>
          </div>
          <div class="focus-card">
            <div class="meta">Visible Links</div>
            <h3>Edges</h3>
            <div id="graphEdges" class="list"><div class="empty">No graph loaded.</div></div>
          </div>
        </div>
      </div>
    </main>
    <aside class="panel">
      <div class="meta">Details</div>
      <h2 id="detailTitle">Awaiting selection</h2>
      <div id="detailBody" class="small">Pick a topic to inspect lead cases and lineages, or run a graph query.</div>
    </aside>
  </div>
  <script>
    const treePanel = document.getElementById("treePanel");
    const focusTitle = document.getElementById("focusTitle");
    const focusSummary = document.getElementById("focusSummary");
    const graphCanvas = document.getElementById("graphCanvas");
    const graphNodes = document.getElementById("graphNodes");
    const graphEdges = document.getElementById("graphEdges");
    const detailTitle = document.getElementById("detailTitle");
    const detailBody = document.getElementById("detailBody");
    const queryForm = document.getElementById("queryForm");
    const queryInput = document.getElementById("queryInput");

    let activeNodeId = "";
    let initialTopicLoaded = false;

    const TYPE_CLASS = {
      Topic: "topic",
      Case: "case",
      AuthorityLineage: "lineage",
      Module: "module",
      Subground: "subground",
      SourceDocument: "source",
      Statute: "statute",
      Judge: "source",
      Paragraph: "source",
      Proposition: "source",
    };

    function escapeHtml(value) {
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function classifyNode(node) {
      return TYPE_CLASS[node.type] || "source";
    }

    function prettyEdgeType(value) {
      return String(value || "").replaceAll("_", " ").toLowerCase();
    }

    function shortenLabel(value, max = 28) {
      const clean = String(value || "").trim();
      return clean.length > max ? `${clean.slice(0, max - 1)}...` : clean;
    }

    function labelForNode(node) {
      return node.label || node.case_name || node.title || node.name || node.id;
    }

    function secondaryForNode(node) {
      return node.neutral_citation || node.path || node.summary_en || node.summary || node.kind || "";
    }

    function multilineLabel(value, width = 18) {
      const words = String(value || "").split(/\\s+/).filter(Boolean);
      if (!words.length) return [""];
      const lines = [];
      let current = "";
      words.forEach((word) => {
        const candidate = current ? `${current} ${word}` : word;
        if (candidate.length > width && current) {
          lines.push(current);
          current = word;
        } else {
          current = candidate;
        }
      });
      if (current) lines.push(current);
      return lines.slice(0, 3);
    }

    function renderNodeLists(payload) {
      graphNodes.innerHTML = "";
      payload.nodes.forEach((node) => {
        const el = document.createElement("div");
        el.className = "card";
        el.innerHTML = `<div class="chip ${classifyNode(node)}">${escapeHtml(node.type)}</div><strong>${escapeHtml(labelForNode(node))}</strong><div class="small">${escapeHtml(secondaryForNode(node))}</div>`;
        el.addEventListener("click", () => handleNodeSelection(node));
        graphNodes.appendChild(el);
      });

      graphEdges.innerHTML = "";
      payload.edges.forEach((edge) => {
        const el = document.createElement("div");
        el.className = "edge";
        el.innerHTML = `<strong>${escapeHtml(edge.type)}</strong><div class="small">${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}</div>`;
        graphEdges.appendChild(el);
      });
    }

    function layoutGraph(payload, anchorId) {
      const nodeMap = new Map(payload.nodes.map((node) => [node.id, node]));
      const neighbors = new Map();
      payload.nodes.forEach((node) => neighbors.set(node.id, new Set()));
      payload.edges.forEach((edge) => {
        if (!neighbors.has(edge.source)) neighbors.set(edge.source, new Set());
        if (!neighbors.has(edge.target)) neighbors.set(edge.target, new Set());
        neighbors.get(edge.source).add(edge.target);
        neighbors.get(edge.target).add(edge.source);
      });

      const startId = anchorId && nodeMap.has(anchorId)
        ? anchorId
        : payload.nodes.find((node) => node.type === "Topic" || node.type === "Case")?.id || payload.nodes[0]?.id;

      if (!startId) {
        return { positions: new Map(), layers: [] };
      }

      const distances = new Map([[startId, 0]]);
      const queue = [startId];
      while (queue.length) {
        const current = queue.shift();
        const currentDistance = distances.get(current);
        (neighbors.get(current) || []).forEach((next) => {
          if (distances.has(next)) return;
          distances.set(next, currentDistance + 1);
          queue.push(next);
        });
      }

      const layers = [];
      payload.nodes.forEach((node) => {
        const distance = distances.get(node.id) ?? 99;
        if (!layers[distance]) layers[distance] = [];
        layers[distance].push(node);
      });

      layers.forEach((layer) => {
        layer.sort((left, right) => {
          const typeOrder = ["Topic", "AuthorityLineage", "Case", "Statute", "SourceDocument", "Judge", "Paragraph", "Proposition", "Module", "Subground"];
          return typeOrder.indexOf(left.type) - typeOrder.indexOf(right.type)
            || labelForNode(left).localeCompare(labelForNode(right));
        });
      });

      const maxLayerSize = Math.max(...layers.filter(Boolean).map((layer) => layer.length), 1);
      const baseHeight = Math.max(760, 170 + maxLayerSize * 118);
      const layerGap = 250;
      const topPad = 90;
      const positions = new Map();

      layers.forEach((layer, layerIndex) => {
        if (!layer) return;
        const x = 140 + layerIndex * layerGap;
        const gap = Math.max(100, Math.min(132, (baseHeight - topPad * 2) / Math.max(layer.length, 1)));
        const totalHeight = gap * Math.max(layer.length - 1, 0);
        const startY = (baseHeight - totalHeight) / 2;
        layer.forEach((node, index) => {
          positions.set(node.id, {
            x,
            y: startY + index * gap,
            width: node.id === startId ? 210 : 180,
            height: node.id === startId ? 78 : 68,
          });
        });
      });

      return { positions, layers, height: baseHeight, anchorId: startId };
    }

    function edgePath(source, target) {
      const sourceX = source.x + source.width / 2;
      const targetX = target.x - target.width / 2;
      const delta = Math.max(80, (targetX - sourceX) * 0.55);
      return `M ${sourceX} ${source.y} C ${sourceX + delta} ${source.y}, ${targetX - delta} ${target.y}, ${targetX} ${target.y}`;
    }

    function handleNodeSelection(node) {
      if (node.type === "Case") {
        loadCase(node.id);
        return;
      }
      if (node.type === "Topic") {
        loadTopic(node.id);
        return;
      }
      loadFocus(node.id, 1, { updateDetail: true });
    }

    function renderGenericNodeDetail(node, payload) {
      detailTitle.textContent = labelForNode(node);
      const matchingEdges = (payload.edges || []).filter((edge) => edge.source === node.id || edge.target === node.id);
      const edgeMarkup = matchingEdges.map((edge) => `
        <div class="card">
          <div class="chip">${escapeHtml(edge.type)}</div>
          <div class="small">${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}</div>
        </div>
      `).join("");
      detailBody.innerHTML = `
        <div class="chip ${classifyNode(node)}">${escapeHtml(node.type)}</div>
        <div class="small">${escapeHtml(secondaryForNode(node))}</div>
        <h3>Linked Edges</h3>
        ${edgeMarkup || "<div class='empty'>No linked edges in this focus graph.</div>"}
      `;
    }

    function renderFocusGraph(payload, anchorId, options = {}) {
      activeNodeId = anchorId && payload.nodes.some((node) => node.id === anchorId) ? anchorId : activeNodeId;
      if (!activeNodeId || !payload.nodes.some((node) => node.id === activeNodeId)) {
        activeNodeId = payload.nodes.find((node) => node.type === "Topic" || node.type === "Case")?.id || payload.nodes[0]?.id || "";
      }

      focusTitle.textContent = payload.focus;
      focusSummary.textContent = `${payload.nodes.length} nodes, ${payload.edges.length} edges, facets: `
        + Object.entries(payload.facets || {}).map(([key, count]) => `${key} ${count}`).join(" · ");

      renderNodeLists(payload);

      const layout = layoutGraph(payload, activeNodeId);
      const width = Math.max(1440, 280 + (layout.layers.length || 1) * 250);
      const height = layout.height || 760;
      graphCanvas.setAttribute("viewBox", `0 0 ${width} ${height}`);

      const defs = `
        <defs>
          <marker id="arrowhead" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
            <path d="M0,0 L9,4.5 L0,9 z" fill="rgba(31, 35, 40, 0.38)"></path>
          </marker>
        </defs>
      `;

      const edgeMarkup = payload.edges.map((edge) => {
        const source = layout.positions.get(edge.source);
        const target = layout.positions.get(edge.target);
        if (!source || !target) return "";
        const active = edge.source === activeNodeId || edge.target === activeNodeId ? " active" : "";
        const midX = (source.x + target.x) / 2;
        const midY = (source.y + target.y) / 2 - 8;
        return `
          <path class="graph-edge${active}" d="${edgePath(source, target)}"></path>
          <text class="edge-label" x="${midX}" y="${midY}" text-anchor="middle">${escapeHtml(prettyEdgeType(edge.type))}</text>
        `;
      }).join("");

      const nodeMarkup = payload.nodes.map((node) => {
        const pos = layout.positions.get(node.id);
        if (!pos) return "";
        const active = node.id === activeNodeId ? " active" : "";
        const lines = multilineLabel(labelForNode(node));
        const secondary = shortenLabel(secondaryForNode(node), 24);
        const textY = pos.y - (lines.length > 1 ? 9 : 2);
        const textLines = lines.map((line, index) =>
          `<tspan x="${pos.x}" y="${textY + index * 16}">${escapeHtml(line)}</tspan>`
        ).join("");
        const subtitle = secondary
          ? `<text class="graph-subtitle" x="${pos.x}" y="${pos.y + 24}" text-anchor="middle">${escapeHtml(secondary)}</text>`
          : "";
        return `
          <g class="graph-node ${classifyNode(node)}${active}" data-node-id="${escapeHtml(node.id)}" transform="translate(0 0)">
            <rect x="${pos.x - pos.width / 2}" y="${pos.y - pos.height / 2}" rx="26" ry="26" width="${pos.width}" height="${pos.height}"></rect>
            <text class="graph-label" x="${pos.x}" y="${textY}" text-anchor="middle">${textLines}</text>
            ${subtitle}
          </g>
        `;
      }).join("");

      graphCanvas.innerHTML = defs + edgeMarkup + nodeMarkup;
      graphCanvas.querySelectorAll("[data-node-id]").forEach((el) => {
        el.addEventListener("click", () => {
          const node = payload.nodes.find((entry) => entry.id === el.dataset.nodeId);
          if (node) handleNodeSelection(node);
        });
      });

      if (options.updateDetail) {
        const node = payload.nodes.find((entry) => entry.id === activeNodeId);
        if (node) renderGenericNodeDetail(node, payload);
      }
    }

    async function loadFocus(id, depth = 1, options = {}) {
      const response = await fetch(`/api/graph/focus?id=${encodeURIComponent(id)}&depth=${depth}`);
      const payload = await response.json();
      renderFocusGraph(payload, id, options);
    }

    async function loadTopic(topicId) {
      const response = await fetch(`/api/topic/${encodeURIComponent(topicId)}`);
      const payload = await response.json();
      activeNodeId = topicId;
      detailTitle.textContent = payload.topic.label;
      const leadCases = (payload.lead_cases || []).map((card) => `
        <div class="card">
          <div class="chip case">${escapeHtml(card.metadata.court_code || "CASE")}</div>
          <strong>${escapeHtml(card.metadata.case_name)}</strong>
          <div class="small">${escapeHtml(card.metadata.neutral_citation || card.metadata.summary_en || "")}</div>
        </div>
      `).join("");
      const lineages = (payload.lineages || []).map((lineage) => `
        <div class="card">
          <div class="chip lineage">Lineage</div>
          <strong>${escapeHtml(lineage.title)}</strong>
          <div class="small">${escapeHtml((lineage.codes || []).join(" · "))}</div>
        </div>
      `).join("");
      detailBody.innerHTML = `
        <div class="chip topic">Topic</div>
        <div class="small">${escapeHtml(payload.topic.summary || payload.topic.path || "")}</div>
        <h3>Lead Cases</h3>
        ${leadCases || "<div class='empty'>No lead cases mapped.</div>"}
        <h3>Lineages</h3>
        ${lineages || "<div class='empty'>No lineages attached.</div>"}
      `;
      renderFocusGraph(payload.focus_graph, topicId);
    }

    async function loadCase(caseId) {
      const response = await fetch(`/api/case/${encodeURIComponent(caseId)}`);
      const payload = await response.json();
      activeNodeId = caseId;
      detailTitle.textContent = payload.metadata.case_name;
      const principles = (payload.principles || []).map((principle) => `
        <div class="card">
          <div class="chip case">${escapeHtml(principle.paragraph_span || "Principle")}</div>
          <strong>${escapeHtml(principle.label_en)}</strong>
          <div class="small">${escapeHtml(principle.statement_en)}</div>
        </div>
      `).join("");
      const relationships = (payload.relationships || []).map((relationship) => `
        <div class="card">
          <div class="chip">${escapeHtml(relationship.type)}</div>
          <strong>${escapeHtml(relationship.target_label)}</strong>
          <div class="small">${escapeHtml(relationship.explanation || relationship.direction)}</div>
        </div>
      `).join("");
      detailBody.innerHTML = `
        <div class="chip case">Case</div>
        <div class="small">${escapeHtml(payload.metadata.neutral_citation || "")} · ${escapeHtml(payload.metadata.court_name || "")}</div>
        <div class="small">${escapeHtml(payload.metadata.summary_en || "")}</div>
        <h3>Principles</h3>
        ${principles || "<div class='empty'>No enriched principles for this case.</div>"}
        <h3>Relationships</h3>
        ${relationships || "<div class='empty'>No typed relationships found.</div>"}
      `;
      await loadFocus(caseId, 1);
    }

    async function loadTree() {
      const response = await fetch("/api/tree");
      const payload = await response.json();
      treePanel.innerHTML = "";

      let firstTopicId = "";
      payload.modules.forEach((module) => {
        const moduleEl = document.createElement("div");
        moduleEl.className = "tree-item";
        const subgrounds = (module.subgrounds || []).map((subground) => {
          if (!firstTopicId && subground.topic_ids && subground.topic_ids.length) {
            firstTopicId = subground.topic_ids[0];
          }
          return `
            <div class="card">
              <div class="chip module">Subground</div>
              <strong>${escapeHtml(subground.label_en)}</strong>
              <div class="small">${subground.metrics.topics} topics · ${subground.metrics.cases} cases</div>
              <div class="small">${(subground.topic_ids || []).map((topicId) => `<a href="#" class="topic-link" data-topic="${escapeHtml(topicId)}">${escapeHtml(topicId.split(":").slice(-1)[0].replaceAll("_", " "))}</a>`).join("<br>") || "<span class='empty'>No topics</span>"}</div>
            </div>
          `;
        }).join("");
        moduleEl.innerHTML = `<div class="chip module">Module</div><strong>${escapeHtml(module.label_en)}</strong><div class="small">${module.metrics.cases} cases · ${module.metrics.lineages} lineages</div>${subgrounds}`;
        treePanel.appendChild(moduleEl);
      });

      treePanel.querySelectorAll("[data-topic]").forEach((link) => {
        link.addEventListener("click", (event) => {
          event.preventDefault();
          loadTopic(link.dataset.topic);
        });
      });

      if (!initialTopicLoaded && firstTopicId) {
        initialTopicLoaded = true;
        loadTopic(firstTopicId);
      }
    }

    queryForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = queryInput.value.trim();
      if (!question) return;
      const response = await fetch("/api/query", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({question})
      });
      const payload = await response.json();
      detailTitle.textContent = "Graph Query";
      detailBody.innerHTML = `
        <div class="small">${escapeHtml(payload.answer || "")}</div>
        <h3>Sources</h3>
        ${
          (payload.sources || []).map((source) => `
            <div class="card">
              <strong>${escapeHtml(source.case_name)}</strong>
              <div class="small">${escapeHtml(source.neutral_citation || source.paragraph_span || "")}</div>
            </div>
          `).join("") || "<div class='empty'>No sources returned.</div>"
        }
      `;
      const focusId = payload.supporting_nodes && payload.supporting_nodes.length ? payload.supporting_nodes[0].id : "";
      if (focusId) {
        loadFocus(focusId, 1, { updateDetail: true });
      }
    });

    loadTree();
  </script>
</body>
</html>
"""
    return html.replace("__TITLE__", title)
