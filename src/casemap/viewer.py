from __future__ import annotations

import base64
import json


def render_knowledge_map(graph_payload: dict) -> str:
    data = json.dumps(graph_payload, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Casemap Knowledge Map</title>
  <style>
    :root {{
      --bg: #f4efe3;
      --panel: #fffaf0;
      --ink: #1c1d21;
      --muted: #6d6658;
      --line: rgba(28, 29, 33, 0.18);
      --section: #205072;
      --concept: #f4b942;
      --statute: #d95d39;
      --case: #5f7c4f;
      --accent: #7c2d12;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: "Georgia", "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(244, 185, 66, 0.22), transparent 32%),
        radial-gradient(circle at top right, rgba(32, 80, 114, 0.18), transparent 28%),
        linear-gradient(180deg, #f7f1e5 0%, var(--bg) 100%);
      min-height: 100vh;
    }}

    .shell {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      min-height: 100vh;
    }}

    .canvas-panel {{
      padding: 28px;
    }}

    .header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin-bottom: 18px;
    }}

    h1 {{
      margin: 0;
      font-size: clamp(30px, 4vw, 44px);
      line-height: 0.95;
      letter-spacing: -0.03em;
    }}

    .subtitle {{
      max-width: 720px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.5;
    }}

    .search {{
      display: grid;
      gap: 8px;
      align-self: start;
    }}

    .search input {{
      width: min(320px, 100%);
      padding: 12px 14px;
      border: 1px solid rgba(28, 29, 33, 0.2);
      border-radius: 999px;
      background: rgba(255, 250, 240, 0.9);
      color: var(--ink);
      font-size: 14px;
    }}

    .legend {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 12px;
    }}

    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}

    .swatch {{
      width: 11px;
      height: 11px;
      border-radius: 999px;
      display: inline-block;
    }}

    .board {{
      background: rgba(255, 250, 240, 0.82);
      border: 1px solid rgba(28, 29, 33, 0.1);
      border-radius: 24px;
      box-shadow: 0 26px 80px rgba(28, 29, 33, 0.08);
      overflow: hidden;
      min-height: calc(100vh - 120px);
    }}

    svg {{
      width: 100%;
      height: calc(100vh - 120px);
      display: block;
    }}

    .side-panel {{
      border-left: 1px solid rgba(28, 29, 33, 0.08);
      background: linear-gradient(180deg, rgba(255, 250, 240, 0.92), rgba(244, 239, 227, 0.98));
      padding: 24px 22px;
      overflow-y: auto;
    }}

    .meta {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-bottom: 10px;
    }}

    .node-title {{
      margin: 0 0 10px;
      font-size: 28px;
      line-height: 1.05;
    }}

    .node-type {{
      display: inline-block;
      margin-bottom: 16px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      background: rgba(28, 29, 33, 0.06);
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .node-copy {{
      margin: 0 0 18px;
      color: var(--ink);
      line-height: 1.6;
    }}

    .list-block {{
      margin: 0 0 20px;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 8px;
    }}

    .list-block li {{
      padding: 10px 12px;
      border: 1px solid rgba(28, 29, 33, 0.08);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.5);
      font-size: 14px;
      line-height: 1.45;
    }}

    .empty {{
      color: var(--muted);
      font-style: italic;
    }}

    .node {{
      cursor: pointer;
      transition: opacity 120ms ease;
    }}

    .node-label {{
      font-size: 11px;
      fill: var(--ink);
      pointer-events: none;
    }}

    .edge {{
      stroke: rgba(28, 29, 33, 0.14);
      stroke-width: 1.2;
    }}

    .faded {{
      opacity: 0.13;
    }}

    .active-node circle {{
      stroke: var(--accent);
      stroke-width: 4;
    }}

    .active-edge {{
      stroke: rgba(124, 45, 18, 0.72);
      stroke-width: 2.4;
    }}

    @media (max-width: 1024px) {{
      .shell {{
        grid-template-columns: 1fr;
      }}

      .side-panel {{
        border-left: 0;
        border-top: 1px solid rgba(28, 29, 33, 0.08);
      }}

      svg {{
        height: 70vh;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="canvas-panel">
      <div class="header">
        <div>
          <div class="meta">Casemap MVP GraphRAG</div>
          <h1>Contract Big Knowledge Map</h1>
          <p class="subtitle">Sections, concepts, statutes, and cases are clustered into a legal knowledge map. Select a node to inspect the summary, cited authorities, and graph neighbors.</p>
          <div class="legend">
            <span><i class="swatch" style="background: var(--section)"></i>Section</span>
            <span><i class="swatch" style="background: var(--concept)"></i>Concept</span>
            <span><i class="swatch" style="background: var(--statute)"></i>Statute</span>
            <span><i class="swatch" style="background: var(--case)"></i>Case</span>
          </div>
        </div>
        <label class="search">
          <span class="meta">Find a node</span>
          <input id="searchInput" type="search" placeholder="Search concepts, statutes, cases">
        </label>
      </div>
      <div class="board">
        <svg id="graph" viewBox="0 0 1280 920" preserveAspectRatio="xMidYMid meet"></svg>
      </div>
    </section>
    <aside class="side-panel">
      <div class="meta">Selection</div>
      <h2 class="node-title" id="nodeTitle">Overview</h2>
      <div class="node-type" id="nodeType">Graph</div>
      <p class="node-copy" id="nodeSummary">The graph groups the contract outline into numbered sections, concept nodes, and cited legal authorities. Search or click on a node to inspect its local neighborhood.</p>
      <div class="meta">Citations</div>
      <ul class="list-block" id="citationList"><li class="empty">No node selected.</li></ul>
      <div class="meta">Neighbors</div>
      <ul class="list-block" id="neighborList"><li class="empty">No node selected.</li></ul>
    </aside>
  </div>
  <script>
    const payload = {data};
    const nodes = payload.nodes.map((node) => ({{ ...node }}));
    const edges = payload.edges.map((edge, index) => ({{ ...edge, id: `edge-${{index}}` }}));
    const svg = document.getElementById("graph");
    const titleEl = document.getElementById("nodeTitle");
    const typeEl = document.getElementById("nodeType");
    const summaryEl = document.getElementById("nodeSummary");
    const citationList = document.getElementById("citationList");
    const neighborList = document.getElementById("neighborList");
    const searchInput = document.getElementById("searchInput");

    const colors = {{
      section: getComputedStyle(document.documentElement).getPropertyValue("--section").trim(),
      concept: getComputedStyle(document.documentElement).getPropertyValue("--concept").trim(),
      statute: getComputedStyle(document.documentElement).getPropertyValue("--statute").trim(),
      case: getComputedStyle(document.documentElement).getPropertyValue("--case").trim(),
    }};

    const index = new Map(nodes.map((node) => [node.id, node]));
    const neighbors = new Map(nodes.map((node) => [node.id, new Set()]));
    edges.forEach((edge) => {{
      neighbors.get(edge.source)?.add(edge.target);
      neighbors.get(edge.target)?.add(edge.source);
    }});

    function radiusFor(node) {{
      if (node.type === "section") return 18;
      if (node.type === "concept") return 10;
      return 9;
    }}

    function layout() {{
      const width = 1280;
      const height = 920;
      const centerX = width / 2;
      const centerY = height / 2;
      const sections = nodes.filter((node) => node.type === "section");
      const concepts = nodes.filter((node) => node.type === "concept");
      const authorities = nodes.filter((node) => node.type !== "section" && node.type !== "concept");

      sections.forEach((section, idx) => {{
        const angle = (Math.PI * 2 * idx) / Math.max(sections.length, 1) - Math.PI / 2;
        section.x = centerX + Math.cos(angle) * 240;
        section.y = centerY + Math.sin(angle) * 220;
      }});

      const groupedConcepts = new Map();
      concepts.forEach((concept) => {{
        const bucket = groupedConcepts.get(concept.section_id) || [];
        bucket.push(concept);
        groupedConcepts.set(concept.section_id, bucket);
      }});

      groupedConcepts.forEach((group, sectionId) => {{
        const parent = index.get(sectionId);
        if (!parent) return;
        group.forEach((concept, idx) => {{
          const angle = (Math.PI * 2 * idx) / Math.max(group.length, 1);
          const distance = 74 + (idx % 3) * 18;
          concept.x = parent.x + Math.cos(angle) * distance;
          concept.y = parent.y + Math.sin(angle) * distance;
        }});
      }});

      authorities.forEach((authority, idx) => {{
        const angle = (Math.PI * 2 * idx) / Math.max(authorities.length, 1) - Math.PI / 2;
        const ring = authority.type === "statute" ? 380 : 430;
        authority.x = centerX + Math.cos(angle) * ring;
        authority.y = centerY + Math.sin(angle) * (ring * 0.72);
      }});
    }}

    layout();

    const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svg.append(edgeLayer, nodeLayer);

    const edgeEls = new Map();
    edges.forEach((edge) => {{
      const source = index.get(edge.source);
      const target = index.get(edge.target);
      if (!source || !target) return;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("class", "edge");
      line.setAttribute("x1", source.x);
      line.setAttribute("y1", source.y);
      line.setAttribute("x2", target.x);
      line.setAttribute("y2", target.y);
      edgeLayer.appendChild(line);
      edgeEls.set(edge.id, line);
    }});

    const nodeEls = new Map();
    nodes.forEach((node) => {{
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "node");
      group.dataset.id = node.id;

      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", node.x);
      circle.setAttribute("cy", node.y);
      circle.setAttribute("r", radiusFor(node));
      circle.setAttribute("fill", colors[node.type] || colors.concept);
      circle.setAttribute("fill-opacity", node.type === "section" ? "0.96" : "0.9");

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", "node-label");
      label.setAttribute("x", node.x + radiusFor(node) + 6);
      label.setAttribute("y", node.y + 4);
      label.textContent = node.label;

      group.append(circle, label);
      group.addEventListener("click", () => selectNode(node.id));
      nodeLayer.appendChild(group);
      nodeEls.set(node.id, group);
    }});

    function renderList(element, values) {{
      element.innerHTML = "";
      if (!values.length) {{
        const item = document.createElement("li");
        item.className = "empty";
        item.textContent = "None";
        element.appendChild(item);
        return;
      }}
      values.forEach((value) => {{
        const item = document.createElement("li");
        item.textContent = value;
        element.appendChild(item);
      }});
    }}

    function selectNode(nodeId) {{
      const node = index.get(nodeId);
      if (!node) return;
      const localNeighbors = [...(neighbors.get(nodeId) || [])].map((id) => index.get(id)).filter(Boolean);
      titleEl.textContent = node.label;
      typeEl.textContent = node.type;
      summaryEl.textContent = node.summary || "No summary available.";
      renderList(citationList, node.citations || []);
      renderList(
        neighborList,
        localNeighbors
          .sort((left, right) => left.label.localeCompare(right.label))
          .map((item) => `${{item.label}} (${{item.type}})`)
      );

      nodeEls.forEach((element, id) => {{
        const isNeighbor = id === nodeId || (neighbors.get(nodeId)?.has(id));
        element.classList.toggle("faded", !isNeighbor);
        element.classList.toggle("active-node", id === nodeId);
      }});

      edges.forEach((edge) => {{
        const active = edge.source === nodeId || edge.target === nodeId;
        const edgeEl = edgeEls.get(edge.id);
        if (!edgeEl) return;
        edgeEl.classList.toggle("faded", !active);
        edgeEl.classList.toggle("active-edge", active);
      }});
    }}

    function clearSelection() {{
      titleEl.textContent = "Overview";
      typeEl.textContent = "Graph";
      summaryEl.textContent = "The graph groups the contract outline into numbered sections, concept nodes, and cited legal authorities. Search or click on a node to inspect its local neighborhood.";
      citationList.innerHTML = '<li class="empty">No node selected.</li>';
      neighborList.innerHTML = '<li class="empty">No node selected.</li>';
      nodeEls.forEach((element) => {{
        element.classList.remove("faded", "active-node");
      }});
      edgeEls.forEach((element) => {{
        element.classList.remove("faded", "active-edge");
      }});
    }}

    function searchNode(value) {{
      const query = value.trim().toLowerCase();
      if (!query) {{
        clearSelection();
        return;
      }}
      const match = nodes.find((node) => {{
        const haystack = `${{node.label}} ${{node.summary || ""}} ${{(node.citations || []).join(" ")}}`.toLowerCase();
        return haystack.includes(query);
      }});
      if (match) {{
        selectNode(match.id);
      }}
    }}

    searchInput.addEventListener("input", (event) => searchNode(event.target.value));
    clearSelection();
  </script>
</body>
</html>
"""


def render_relationship_map(graph_payload: dict) -> str:
    data = json.dumps(graph_payload, ensure_ascii=False)
    meta = graph_payload.get("meta", {})
    legal_domain = str(meta.get("legal_domain", "")).strip().lower()
    inferred_criminal = legal_domain == "criminal" or "criminal" in str(meta.get("title", "")).lower()
    heading = meta.get("relationship_heading_public") or ("Hong Kong Criminal Law" if inferred_criminal else "Hong Kong Contract Law")
    intro = meta.get("relationship_intro_public") or (
        "A node-first research map for criminal topics, case authorities, statutes, and source passages. Start with the graph, then pivot into the hierarchy when you want a doctrinal spine."
        if inferred_criminal
        else "A node-first research map for doctrine, authorities, statutes, and source passages. Start with the graph, then pivot into the hierarchy when you want a doctrinal spine."
    )
    canvas_copy = (
        "The main surface stays graph-native: topic hubs connect outward to criminal authorities, statutes, and source support so retrieval remains specific to the criminal domain."
        if inferred_criminal
        else "The main surface stays graph-native: doctrinal hubs connect outward to authorities, statutes, and source support so retrieval remains specific to the selected legal domain."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Casemap Relationship Graph</title>
  <style>
    :root {{
      --bg: #edf1f5;
      --bg-deep: #dde3ea;
      --panel: rgba(255, 255, 255, 0.84);
      --panel-strong: rgba(255, 255, 255, 0.94);
      --line: rgba(15, 18, 22, 0.08);
      --line-strong: rgba(15, 18, 22, 0.16);
      --ink: #101317;
      --muted: #69727d;
      --domain: #0f4c5c;
      --topic: #d28d2d;
      --case: #7f5539;
      --statute: #bc4749;
      --source: #52796f;
      --accent: #0f1216;
      --shadow: 0 26px 80px rgba(15, 18, 22, 0.09);
      --shadow-soft: 0 16px 38px rgba(15, 18, 22, 0.06);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.86), transparent 24%),
        radial-gradient(circle at bottom right, rgba(173, 181, 192, 0.24), transparent 28%),
        linear-gradient(180deg, #f7f9fb 0%, var(--bg) 54%, var(--bg-deep) 100%);
    }}

    .shell {{
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr) 400px;
      min-height: 100vh;
    }}

    .panel {{
      background: var(--panel);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      border-right: 1px solid var(--line);
      padding: 24px 22px;
      overflow-y: auto;
    }}

    .details {{
      border-right: 0;
      border-left: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(242, 245, 248, 0.96));
    }}

    .canvas-panel {{
      padding: 24px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 16px;
    }}

    .meta {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      margin-bottom: 8px;
    }}

    h1, h2 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      font-weight: 600;
    }}

    h1 {{
      font-size: clamp(34px, 4vw, 46px);
      line-height: 0.92;
      letter-spacing: -0.05em;
      margin-bottom: 12px;
    }}

    .intro {{
      color: var(--muted);
      font-size: 14px;
      line-height: 1.62;
      margin: 0 0 20px;
      max-width: 28rem;
    }}

    .nav {{
      display: inline-flex;
      gap: 8px;
      padding: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.72);
      box-shadow: var(--shadow-soft);
      margin-bottom: 20px;
    }}

    .nav a {{
      padding: 10px 14px;
      border-radius: 999px;
      color: var(--ink);
      text-decoration: none;
      font-size: 13px;
      letter-spacing: 0.01em;
    }}

    .nav a.active {{
      background: var(--accent);
      color: white;
    }}

    .counts {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }}

    .count-card {{
      padding: 14px 16px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(244, 247, 250, 0.82));
      box-shadow: var(--shadow-soft);
    }}

    .count-card strong {{
      display: block;
      font-size: 24px;
      line-height: 1;
      margin-bottom: 5px;
      letter-spacing: -0.03em;
    }}

    .count-card span {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}

    .control-block {{
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.7);
      box-shadow: var(--shadow-soft);
      margin-bottom: 16px;
    }}

    .search-box input {{
      width: 100%;
      padding: 13px 14px;
      border-radius: 16px;
      border: 1px solid var(--line-strong);
      font-size: 14px;
      background: rgba(255, 255, 255, 0.92);
      color: var(--ink);
      font: inherit;
    }}

    .filters {{
      display: grid;
      gap: 10px;
    }}

    .filter-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      font-size: 13px;
      color: var(--ink);
      padding: 10px 12px;
      border: 1px solid rgba(15, 18, 22, 0.06);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.58);
    }}

    .filter-row input {{
      accent-color: var(--accent);
    }}

    .results {{
      display: grid;
      gap: 10px;
    }}

    .result-btn {{
      width: 100%;
      text-align: left;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-left-width: 4px;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(245, 247, 250, 0.84));
      cursor: pointer;
      font: inherit;
      color: inherit;
      box-shadow: var(--shadow-soft);
    }}

    .result-btn.domain {{ border-left-color: var(--domain); }}
    .result-btn.topic {{ border-left-color: var(--topic); }}
    .result-btn.case {{ border-left-color: var(--case); }}
    .result-btn.statute {{ border-left-color: var(--statute); }}
    .result-btn.source {{ border-left-color: var(--source); }}

    .result-btn small {{
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 12px;
    }}

    .result-btn strong {{
      display: block;
      font-size: 14px;
      line-height: 1.4;
    }}

    .canvas-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 18px;
      flex-wrap: wrap;
    }}

    .canvas-title {{
      font-size: 26px;
      line-height: 1;
      letter-spacing: -0.04em;
      margin-bottom: 8px;
    }}

    .canvas-copy {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.56;
      max-width: 42rem;
    }}

    .board {{
      position: relative;
      border-radius: 28px;
      border: 1px solid var(--line);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(243, 246, 250, 0.96)),
        repeating-linear-gradient(0deg, rgba(15, 18, 22, 0.03) 0 1px, transparent 1px 34px),
        repeating-linear-gradient(90deg, rgba(15, 18, 22, 0.03) 0 1px, transparent 1px 34px);
      box-shadow: var(--shadow);
      overflow: hidden;
      min-height: calc(100vh - 112px);
    }}

    svg {{
      width: 100%;
      height: calc(100vh - 112px);
      display: block;
    }}

    .legend {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      font-size: 11px;
      color: var(--muted);
    }}

    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.76);
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}

    .swatch {{
      width: 10px;
      height: 10px;
      border-radius: 2px;
      display: inline-block;
    }}

    .node {{
      cursor: pointer;
      transition: opacity 120ms ease;
    }}

    .node circle {{
      stroke: rgba(255, 255, 255, 0.92);
      stroke-width: 1.4;
      filter: drop-shadow(0 10px 22px rgba(15, 18, 22, 0.12));
      transition: stroke-width 140ms ease, stroke 140ms ease;
    }}

    .edge {{
      stroke: rgba(15, 18, 22, 0.1);
      stroke-width: 1.1;
    }}

    .node-label {{
      fill: var(--ink);
      font-size: 10.5px;
      font-family: "SFMono-Regular", "Menlo", "Monaco", monospace;
      letter-spacing: 0.02em;
      pointer-events: none;
    }}

    .suppressed {{
      display: none;
    }}

    .faded {{
      opacity: 0.12;
    }}

    .active-edge {{
      stroke: rgba(15, 18, 22, 0.55);
      stroke-width: 2.2;
    }}

    .active-node circle {{
      stroke: var(--accent);
      stroke-width: 3.8;
    }}

    .pill {{
      display: inline-block;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(15, 18, 22, 0.06);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 14px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}

    .pill.domain {{
      background: rgba(15, 76, 92, 0.12);
      color: var(--domain);
      border-color: rgba(15, 76, 92, 0.18);
    }}

    .pill.topic {{
      background: rgba(210, 141, 45, 0.14);
      color: #8a5a11;
      border-color: rgba(210, 141, 45, 0.2);
    }}

    .pill.case {{
      background: rgba(127, 85, 57, 0.14);
      color: var(--case);
      border-color: rgba(127, 85, 57, 0.2);
    }}

    .pill.statute {{
      background: rgba(188, 71, 73, 0.12);
      color: var(--statute);
      border-color: rgba(188, 71, 73, 0.18);
    }}

    .pill.source {{
      background: rgba(82, 121, 111, 0.12);
      color: var(--source);
      border-color: rgba(82, 121, 111, 0.18);
    }}

    .summary {{
      font-size: 15px;
      line-height: 1.64;
      margin: 0 0 18px;
      color: var(--ink);
    }}

    .metric-list, .link-list, .ref-list, .neighbor-list {{
      list-style: none;
      margin: 0 0 18px;
      padding: 0;
      display: grid;
      gap: 10px;
    }}

    .metric-list li, .link-list li, .ref-list li, .neighbor-list li {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.72);
      padding: 12px 14px;
      font-size: 14px;
      line-height: 1.5;
      box-shadow: var(--shadow-soft);
    }}

    .ref-meta {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}

    a {{
      color: var(--ink);
      text-decoration: none;
      border-bottom: 1px solid rgba(15, 18, 22, 0.16);
    }}

    a:hover {{
      border-color: rgba(15, 18, 22, 0.36);
    }}

    @media (hover: hover) and (pointer: fine) {{
      .result-btn:hover {{
        border-color: var(--line-strong);
        box-shadow: 0 20px 42px rgba(15, 18, 22, 0.08);
      }}

      .node:hover circle {{
        stroke-width: 2.2;
      }}
    }}

    @media (max-width: 1200px) {{
      .shell {{
        grid-template-columns: 1fr;
      }}

      .panel, .details {{
        border: 0;
      }}

      svg {{
        height: 72vh;
      }}

      .board {{
        min-height: 72vh;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="panel">
      <nav class="nav">
        <a href="/" class="active">Node Graph</a>
        <a href="/tree">Hierarchy</a>
        <a href="/mvp">MVP GraphRAG</a>
      </nav>
      <div class="meta">Casemap Relationship Graph</div>
      <h1>{heading}</h1>
      <p class="intro">{intro}</p>
      <div class="counts">
        <div class="count-card"><strong>{graph_payload["meta"]["node_count"]}</strong><span>Nodes</span></div>
        <div class="count-card"><strong>{graph_payload["meta"]["edge_count"]}</strong><span>Edges</span></div>
        <div class="count-card"><strong>{graph_payload["meta"]["source_count"]}</strong><span>Sources</span></div>
        <div class="count-card"><strong>{graph_payload["meta"]["passage_count"]}</strong><span>Passages</span></div>
      </div>
      <div class="control-block search-box">
        <div class="meta">Search</div>
        <input id="searchInput" type="search" placeholder="Case, topic, statute, source">
      </div>
      <div class="control-block">
        <div class="meta">Scope</div>
        <div class="filters">
          <label class="filter-row"><span>Domains</span><input type="checkbox" data-type="domain" checked></label>
          <label class="filter-row"><span>Topics</span><input type="checkbox" data-type="topic" checked></label>
          <label class="filter-row"><span>Cases</span><input type="checkbox" data-type="case" checked></label>
          <label class="filter-row"><span>Statutes</span><input type="checkbox" data-type="statute" checked></label>
          <label class="filter-row"><span>Sources</span><input type="checkbox" data-type="source" checked></label>
        </div>
      </div>
      <div class="control-block">
        <div class="meta">Matches</div>
        <div id="results" class="results"></div>
      </div>
    </aside>
    <section class="canvas-panel">
      <div class="canvas-header">
        <div>
          <div class="meta">Authority Network</div>
          <h2 class="canvas-title">Doctrinal Relationship Map</h2>
          <p class="canvas-copy">{canvas_copy}</p>
        </div>
        <div class="legend">
          <span><i class="swatch" style="background: var(--domain)"></i>Domain</span>
          <span><i class="swatch" style="background: var(--topic)"></i>Topic</span>
          <span><i class="swatch" style="background: var(--case)"></i>Case</span>
          <span><i class="swatch" style="background: var(--statute)"></i>Statute</span>
          <span><i class="swatch" style="background: var(--source)"></i>Source</span>
        </div>
      </div>
      <div class="board">
        <svg id="graph" viewBox="0 0 1440 980" preserveAspectRatio="xMidYMid meet"></svg>
      </div>
    </section>
    <aside class="panel details">
      <div class="meta">Selection</div>
      <h2 id="nodeTitle">Overview</h2>
      <div id="nodeType" class="pill">Authority Network</div>
      <p id="nodeSummary" class="summary">Select a node to inspect its role in the network, linked authorities, supporting source passages, and any available public-facing links.</p>
      <div class="meta">Metrics</div>
      <ul id="metricList" class="metric-list"><li>Choose a node to view counts and metadata.</li></ul>
      <div class="meta">External Links</div>
      <ul id="linkList" class="link-list"><li>No node selected.</li></ul>
      <div class="meta">Relevant Passages</div>
      <ul id="referenceList" class="ref-list"><li>No node selected.</li></ul>
      <div class="meta">Related Nodes</div>
      <ul id="neighborList" class="neighbor-list"><li>No node selected.</li></ul>
    </aside>
  </div>
  <script>
    const payload = {data};
    const nodes = payload.nodes.map((node) => ({{ ...node }}));
    const edges = payload.edges.map((edge, index) => ({{ ...edge, id: `edge-${{index}}` }}));
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const adjacency = new Map(nodes.map((node) => [node.id, new Set()]));
    edges.forEach((edge) => {{
      adjacency.get(edge.source)?.add(edge.target);
      adjacency.get(edge.target)?.add(edge.source);
    }});

    const svg = document.getElementById("graph");
    const resultsEl = document.getElementById("results");
    const searchInput = document.getElementById("searchInput");
    const typeInputs = [...document.querySelectorAll("input[data-type]")];
    const titleEl = document.getElementById("nodeTitle");
    const typeEl = document.getElementById("nodeType");
    const summaryEl = document.getElementById("nodeSummary");
    const metricList = document.getElementById("metricList");
    const linkList = document.getElementById("linkList");
    const referenceList = document.getElementById("referenceList");
    const neighborList = document.getElementById("neighborList");

    const colors = {{
      domain: getComputedStyle(document.documentElement).getPropertyValue("--domain").trim(),
      topic: getComputedStyle(document.documentElement).getPropertyValue("--topic").trim(),
      case: getComputedStyle(document.documentElement).getPropertyValue("--case").trim(),
      statute: getComputedStyle(document.documentElement).getPropertyValue("--statute").trim(),
      source: getComputedStyle(document.documentElement).getPropertyValue("--source").trim(),
    }};

    function hashCode(value) {{
      let hash = 0;
      for (let index = 0; index < value.length; index += 1) {{
        hash = ((hash << 5) - hash) + value.charCodeAt(index);
        hash |= 0;
      }}
      return Math.abs(hash);
    }}

    function radiusFor(node) {{
      if (node.type === "domain") return 18;
      if (node.type === "topic") return 11;
      if (node.type === "source") return 10;
      return 8;
    }}

    function layoutNodes() {{
      const width = 1440;
      const height = 980;
      const centerX = width / 2;
      const centerY = height / 2;
      const domains = nodes.filter((node) => node.type === "domain");
      const topics = nodes.filter((node) => node.type === "topic");
      const sources = nodes.filter((node) => node.type === "source");
      const authorities = nodes.filter((node) => node.type === "case" || node.type === "statute");

      domains.forEach((domain, index) => {{
        const angle = (Math.PI * 2 * index) / Math.max(domains.length, 1) - Math.PI / 2;
        domain.x = centerX + Math.cos(angle) * 250;
        domain.y = centerY + Math.sin(angle) * 220;
      }});

      const topicsByDomain = new Map();
      topics.forEach((topic) => {{
        const bucket = topicsByDomain.get(topic.domain_id) || [];
        bucket.push(topic);
        topicsByDomain.set(topic.domain_id, bucket);
      }});

      topicsByDomain.forEach((bucket, domainId) => {{
        const domain = nodeMap.get(domainId);
        if (!domain) return;
        bucket.forEach((topic, index) => {{
          const angle = (Math.PI * 2 * index) / Math.max(bucket.length, 1);
          const distance = 88 + ((index % 4) * 18);
          topic.x = domain.x + Math.cos(angle) * distance;
          topic.y = domain.y + Math.sin(angle) * distance;
        }});
      }});

      sources.forEach((source, index) => {{
        source.x = 126;
        source.y = 170 + (index * 120);
      }});

      authorities.forEach((node, index) => {{
        const neighbors = [...(adjacency.get(node.id) || [])]
          .map((id) => nodeMap.get(id))
          .filter((item) => item && (item.type === "topic" || item.type === "domain"));
        let baseX = centerX;
        let baseY = centerY;
        if (neighbors.length) {{
          baseX = neighbors.reduce((sum, item) => sum + item.x, 0) / neighbors.length;
          baseY = neighbors.reduce((sum, item) => sum + item.y, 0) / neighbors.length;
        }}
        const hash = hashCode(node.id);
        const angle = ((hash % 360) / 180) * Math.PI;
        const distance = node.type === "statute" ? 160 + (hash % 60) : 220 + (hash % 110);
        node.x = Math.max(70, Math.min(width - 70, baseX + Math.cos(angle) * distance));
        node.y = Math.max(70, Math.min(height - 70, baseY + Math.sin(angle) * distance * 0.75));
      }});
    }}

    layoutNodes();

    const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svg.append(edgeLayer, nodeLayer);

    const edgeEls = new Map();
    edges.forEach((edge) => {{
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      if (!source || !target) return;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("class", "edge");
      line.setAttribute("x1", source.x);
      line.setAttribute("y1", source.y);
      line.setAttribute("x2", target.x);
      line.setAttribute("y2", target.y);
      edgeLayer.appendChild(line);
      edgeEls.set(edge.id, line);
    }});

    const nodeEls = new Map();
    const labelEls = new Map();
    nodes.forEach((node) => {{
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "node");
      group.dataset.id = node.id;

      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", node.x);
      circle.setAttribute("cy", node.y);
      circle.setAttribute("r", radiusFor(node));
      circle.setAttribute("fill", colors[node.type] || colors.topic);
      circle.setAttribute("fill-opacity", node.type === "domain" ? "0.95" : "0.88");

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", "node-label");
      if (node.type === "case" || node.type === "statute") {{
        label.classList.add("suppressed");
      }}
      label.setAttribute("x", node.x + radiusFor(node) + 6);
      label.setAttribute("y", node.y + 4);
      label.textContent = node.label;

      group.append(circle, label);
      group.addEventListener("click", () => selectNode(node.id));
      nodeLayer.appendChild(group);
      nodeEls.set(node.id, group);
      labelEls.set(node.id, label);
    }});

    function visibleTypes() {{
      return new Set(typeInputs.filter((input) => input.checked).map((input) => input.dataset.type));
    }}

    function filteredNodes(query) {{
      const allowedTypes = visibleTypes();
      const lowered = query.trim().toLowerCase();
      return nodes
        .filter((node) => allowedTypes.has(node.type))
        .filter((node) => {{
          if (!lowered) return true;
          const haystack = `${{node.label}} ${{node.summary || ""}}`.toLowerCase();
          return haystack.includes(lowered);
        }})
        .sort((left, right) => {{
          const leftScore = (left.degree || 0) + ((left.type === "domain" || left.type === "topic") ? 3 : 0);
          const rightScore = (right.degree || 0) + ((right.type === "domain" || right.type === "topic") ? 3 : 0);
          return rightScore - leftScore;
        }});
    }}

    function renderResults(query) {{
      const matches = filteredNodes(query).slice(0, 12);
      resultsEl.innerHTML = "";
      if (!matches.length) {{
        resultsEl.innerHTML = "<div class='intro'>No matching nodes for the current search and scope.</div>";
        return;
      }}
      matches.forEach((node) => {{
        const button = document.createElement("button");
        button.className = `result-btn ${{node.type}}`;
        button.type = "button";
        button.innerHTML = `<strong>${{node.label}}</strong><small>${{node.type}} · degree ${{node.degree || 0}}</small>`;
        button.addEventListener("click", () => selectNode(node.id));
        resultsEl.appendChild(button);
      }});
    }}

    function renderMetrics(metrics) {{
      metricList.innerHTML = "";
      const entries = Object.entries(metrics || {{}});
      if (!entries.length) {{
        metricList.innerHTML = "<li>No metrics available.</li>";
        return;
      }}
      entries.forEach(([key, value]) => {{
        const item = document.createElement("li");
        item.textContent = `${{key}}: ${{value}}`;
        metricList.appendChild(item);
      }});
    }}

    function renderLinks(links) {{
      linkList.innerHTML = "";
      if (!links || !links.length) {{
        linkList.innerHTML = "<li>No external links available.</li>";
        return;
      }}
      links.forEach((link) => {{
        const item = document.createElement("li");
        item.innerHTML = `<a href="${{link.url}}" target="_blank" rel="noreferrer">${{link.label}}</a>`;
        linkList.appendChild(item);
      }});
    }}

    function renderReferences(references) {{
      referenceList.innerHTML = "";
      if (!references || !references.length) {{
        referenceList.innerHTML = "<li>No supporting passages captured for this node.</li>";
        return;
      }}
      references.forEach((reference) => {{
        const item = document.createElement("li");
        item.innerHTML = `<div class="ref-meta">${{reference.source_label}} · ${{reference.location}}</div><div>${{reference.snippet}}</div>`;
        referenceList.appendChild(item);
      }});
    }}

    function renderNeighbors(nodeId) {{
      neighborList.innerHTML = "";
      const ids = [...(adjacency.get(nodeId) || [])]
        .map((id) => nodeMap.get(id))
        .filter(Boolean)
        .sort((left, right) => left.label.localeCompare(right.label));
      if (!ids.length) {{
        neighborList.innerHTML = "<li>No related nodes.</li>";
        return;
      }}
      ids.slice(0, 16).forEach((neighbor) => {{
        const item = document.createElement("li");
        item.innerHTML = `<strong>${{neighbor.label}}</strong><div class="ref-meta">${{neighbor.type}}</div>`;
        item.addEventListener("click", () => selectNode(neighbor.id));
        neighborList.appendChild(item);
      }});
    }}

    function resetDetail() {{
      titleEl.textContent = "Overview";
      typeEl.textContent = "Authority Network";
      typeEl.className = "pill";
      summaryEl.textContent = "Select a node to inspect its role in the network, linked authorities, supporting source passages, and any available public-facing links.";
      metricList.innerHTML = "<li>Choose a node to view counts and metadata.</li>";
      linkList.innerHTML = "<li>No node selected.</li>";
      referenceList.innerHTML = "<li>No node selected.</li>";
      neighborList.innerHTML = "<li>No node selected.</li>";
    }}

    let selectedNodeId = null;

    function applyVisibility() {{
      const allowedTypes = visibleTypes();
      nodeEls.forEach((element, id) => {{
        const node = nodeMap.get(id);
        const allowed = allowedTypes.has(node.type);
        element.classList.toggle("suppressed", !allowed);
      }});
      edgeEls.forEach((element, edgeId) => {{
        const edge = edges.find((item) => item.id === edgeId);
        const sourceAllowed = edge && allowedTypes.has(nodeMap.get(edge.source).type);
        const targetAllowed = edge && allowedTypes.has(nodeMap.get(edge.target).type);
        element.classList.toggle("suppressed", !(sourceAllowed && targetAllowed));
      }});
    }}

    function selectNode(nodeId) {{
      const node = nodeMap.get(nodeId);
      if (!node) return;
      selectedNodeId = nodeId;
      titleEl.textContent = node.label;
      typeEl.textContent = node.type;
      typeEl.className = `pill ${{node.type}}`;
      summaryEl.textContent = node.summary || "No summary available.";
      renderMetrics(node.metrics || {{}});
      renderLinks(node.links || []);
      renderReferences(node.references || []);
      renderNeighbors(nodeId);

      nodeEls.forEach((element, id) => {{
        const neighbor = adjacency.get(nodeId)?.has(id);
        const active = id === nodeId;
        element.classList.toggle("active-node", active);
        element.classList.toggle("faded", !(active || neighbor));
      }});

      labelEls.forEach((element, id) => {{
        const alwaysVisible = ["domain", "topic", "source"].includes(nodeMap.get(id).type);
        const neighbor = adjacency.get(nodeId)?.has(id);
        element.classList.toggle("suppressed", !(alwaysVisible || neighbor || id === nodeId));
      }});

      edges.forEach((edge) => {{
        const edgeEl = edgeEls.get(edge.id);
        if (!edgeEl) return;
        const active = edge.source === nodeId || edge.target === nodeId;
        edgeEl.classList.toggle("faded", !active);
        edgeEl.classList.toggle("active-edge", active);
      }});
    }}

    function clearSelection() {{
      selectedNodeId = null;
      resetDetail();
      nodeEls.forEach((element) => element.classList.remove("active-node", "faded"));
      edges.forEach((edge) => {{
        const edgeEl = edgeEls.get(edge.id);
        if (edgeEl) edgeEl.classList.remove("active-edge", "faded");
      }});
      labelEls.forEach((element, id) => {{
        const alwaysVisible = ["domain", "topic", "source"].includes(nodeMap.get(id).type);
        element.classList.toggle("suppressed", !alwaysVisible);
      }});
    }}

    searchInput.addEventListener("input", (event) => {{
      const query = event.target.value;
      renderResults(query);
      if (!query.trim()) {{
        clearSelection();
      }}
    }});

    typeInputs.forEach((input) => input.addEventListener("change", () => {{
      applyVisibility();
      renderResults(searchInput.value);
      if (selectedNodeId && !visibleTypes().has(nodeMap.get(selectedNodeId).type)) {{
        clearSelection();
      }}
    }}));

    applyVisibility();
    renderResults("");
    const initialDomain = nodes.find((node) => node.type === "domain");
    if (initialDomain) {{
      selectNode(initialDomain.id);
    }} else {{
      resetDetail();
    }}
  </script>
</body>
</html>
"""


def render_relationship_tree(graph_payload: dict) -> str:
    data = json.dumps(graph_payload, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Casemap Relationship Tree</title>
  <style>
    :root {{
      --bg: #f7f0e4;
      --panel: rgba(255, 251, 244, 0.96);
      --ink: #232427;
      --muted: #666055;
      --line: rgba(35, 36, 39, 0.1);
      --domain: #0f4c5c;
      --topic: #f4a261;
      --case: #7f5539;
      --statute: #bc4749;
      --source: #52796f;
      --accent: #283618;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: "Georgia", "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(244, 162, 97, 0.16), transparent 26%),
        linear-gradient(180deg, #faf5eb 0%, var(--bg) 100%);
      min-height: 100vh;
    }}

    .shell {{
      display: grid;
      grid-template-columns: 440px minmax(0, 1fr);
      min-height: 100vh;
    }}

    .tree-panel, .detail-panel {{
      padding: 22px 20px;
      overflow-y: auto;
    }}

    .tree-panel {{
      border-right: 1px solid var(--line);
      background: var(--panel);
    }}

    .detail-panel {{
      background: linear-gradient(180deg, rgba(255, 251, 244, 0.78), rgba(247, 240, 228, 0.92));
    }}

    .meta {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      margin-bottom: 8px;
    }}

    h1, h2, h3 {{
      margin: 0;
    }}

    h1 {{
      font-size: 36px;
      line-height: 0.96;
      letter-spacing: -0.04em;
      margin-bottom: 8px;
    }}

    .intro {{
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
      margin-bottom: 18px;
    }}

    .nav {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }}

    .nav a {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 9px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.58);
      color: var(--ink);
      text-decoration: none;
      font-size: 13px;
    }}

    .nav a.active {{
      background: rgba(15, 76, 92, 0.12);
      border-color: rgba(15, 76, 92, 0.24);
    }}

    .search-box {{
      margin-bottom: 18px;
    }}

    .search-box input {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid rgba(35, 36, 39, 0.14);
      font-size: 14px;
      background: rgba(255, 255, 255, 0.86);
    }}

    .result-list, .ref-list, .neighbor-list, .metric-list, .link-list {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 10px;
    }}

    .result-list {{
      margin-bottom: 22px;
    }}

    .result-btn, .node-btn {{
      width: 100%;
      text-align: left;
      border: 1px solid rgba(35, 36, 39, 0.08);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.56);
      padding: 10px 12px;
      cursor: pointer;
      font: inherit;
      color: inherit;
    }}

    .node-btn small, .result-btn small {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }}

    details {{
      border-left: 2px solid rgba(35, 36, 39, 0.08);
      padding-left: 12px;
      margin-bottom: 12px;
    }}

    details > summary {{
      list-style: none;
      cursor: pointer;
      margin-left: -12px;
      padding-left: 12px;
    }}

    details > summary::-webkit-details-marker {{
      display: none;
    }}

    .domain-summary {{
      padding: 10px 12px;
      border-radius: 16px;
      background: rgba(15, 76, 92, 0.08);
      border: 1px solid rgba(15, 76, 92, 0.18);
    }}

    .topic-summary {{
      padding: 8px 10px;
      border-radius: 12px;
      background: rgba(244, 162, 97, 0.12);
      border: 1px solid rgba(244, 162, 97, 0.18);
    }}

    .group-block {{
      margin: 10px 0 16px;
      padding-left: 8px;
      display: grid;
      gap: 8px;
    }}

    .group-title {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-top: 2px;
    }}

    .chip {{
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      margin-bottom: 8px;
      color: white;
    }}

    .chip.domain {{ background: var(--domain); }}
    .chip.topic {{ background: var(--topic); color: var(--ink); }}
    .chip.case {{ background: var(--case); }}
    .chip.statute {{ background: var(--statute); }}
    .chip.source {{ background: var(--source); }}

    .summary {{
      font-size: 15px;
      line-height: 1.6;
      margin: 0 0 18px;
    }}

    .metric-list li, .link-list li, .ref-list li, .neighbor-list li {{
      border: 1px solid rgba(35, 36, 39, 0.08);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.54);
      padding: 12px 14px;
      font-size: 14px;
      line-height: 1.5;
    }}

    .ref-meta {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}

    a {{
      color: var(--domain);
      text-decoration: none;
    }}

    a:hover {{
      text-decoration: underline;
    }}

    .empty {{
      color: var(--muted);
      font-style: italic;
    }}

    @media (max-width: 1080px) {{
      .shell {{
        grid-template-columns: 1fr;
      }}
      .tree-panel {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="tree-panel">
      <div class="meta">Casemap Tree</div>
      <h1>Hierarchical Contract Law Tree</h1>
      <p class="intro">Read the legal picture top-down: doctrinal domains, their sub-topics, and the related authorities and sources attached to each branch.</p>
      <nav class="nav">
        <a href="/" class="active">Tree</a>
        <a href="/relationships">Graph</a>
        <a href="/mvp">MVP</a>
      </nav>
      <div class="search-box">
        <div class="meta">Jump To Node</div>
        <input id="searchInput" type="search" placeholder="Case, topic, statute, source">
      </div>
      <ul id="resultList" class="result-list"></ul>
      <div class="meta">Tree</div>
      <div id="treeRoot"></div>
    </aside>
    <main class="detail-panel">
      <div class="meta">Selection</div>
      <h2 id="nodeTitle">Overview</h2>
      <div id="nodeChip" class="chip domain">tree</div>
      <p id="nodeSummary" class="summary">Select a domain, topic, case, statute, or source to inspect its details, public links, and graph neighbors.</p>
      <div class="meta">Metrics</div>
      <ul id="metricList" class="metric-list"><li class="empty">Choose a node to view metrics.</li></ul>
      <div class="meta">External Links</div>
      <ul id="linkList" class="link-list"><li class="empty">No node selected.</li></ul>
      <div class="meta">Supporting References</div>
      <ul id="referenceList" class="ref-list"><li class="empty">No node selected.</li></ul>
      <div class="meta">Related Nodes</div>
      <ul id="neighborList" class="neighbor-list"><li class="empty">No node selected.</li></ul>
    </main>
  </div>
  <script>
    const payload = {data};
    const nodes = payload.nodes;
    const edges = payload.edges;
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const adjacency = new Map(nodes.map((node) => [node.id, new Set()]));
    const byType = {{
      domain: nodes.filter((node) => node.type === "domain").sort((a, b) => a.label.localeCompare(b.label)),
    }};

    edges.forEach((edge) => {{
      adjacency.get(edge.source)?.add(edge.target);
      adjacency.get(edge.target)?.add(edge.source);
    }});

    const treeRoot = document.getElementById("treeRoot");
    const resultList = document.getElementById("resultList");
    const searchInput = document.getElementById("searchInput");
    const titleEl = document.getElementById("nodeTitle");
    const chipEl = document.getElementById("nodeChip");
    const summaryEl = document.getElementById("nodeSummary");
    const metricList = document.getElementById("metricList");
    const linkList = document.getElementById("linkList");
    const referenceList = document.getElementById("referenceList");
    const neighborList = document.getElementById("neighborList");

    function neighborsByType(nodeId, type) {{
      return [...(adjacency.get(nodeId) || [])]
        .map((id) => nodeMap.get(id))
        .filter((node) => node && node.type === type)
        .sort((a, b) => a.label.localeCompare(b.label));
    }}

    function makeNodeButton(node, context) {{
      const button = document.createElement("button");
      button.type = "button";
      button.className = "node-btn";
      button.innerHTML = `<strong>${{node.label}}</strong><small>${{node.type}}${{context ? " · " + context : ""}}</small>`;
      button.addEventListener("click", () => selectNode(node.id));
      return button;
    }}

    function renderTree() {{
      treeRoot.innerHTML = "";
      byType.domain.forEach((domain) => {{
        const domainDetails = document.createElement("details");
        domainDetails.open = true;

        const domainSummary = document.createElement("summary");
        domainSummary.className = "domain-summary";
        domainSummary.appendChild(makeNodeButton(domain, `${{neighborsByType(domain.id, "topic").length}} topics`));
        domainDetails.appendChild(domainSummary);

        const topicIds = edges
          .filter((edge) => edge.type === "contains" && edge.source === domain.id)
          .map((edge) => nodeMap.get(edge.target))
          .filter(Boolean)
          .sort((a, b) => a.label.localeCompare(b.label));

        topicIds.forEach((topic) => {{
          const topicDetails = document.createElement("details");
          const topicSummary = document.createElement("summary");
          topicSummary.className = "topic-summary";
          topicSummary.appendChild(makeNodeButton(topic, `${{neighborsByType(topic.id, "case").length}} cases · ${{neighborsByType(topic.id, "statute").length}} statutes`));
          topicDetails.appendChild(topicSummary);

          const blocks = [
            ["Cases", neighborsByType(topic.id, "case")],
            ["Statutes", neighborsByType(topic.id, "statute")],
            ["Sources", neighborsByType(topic.id, "source")],
          ];

          blocks.forEach(([label, items]) => {{
            if (!items.length) return;
            const block = document.createElement("div");
            block.className = "group-block";
            const heading = document.createElement("div");
            heading.className = "group-title";
            heading.textContent = label;
            block.appendChild(heading);
            items.slice(0, 16).forEach((item) => block.appendChild(makeNodeButton(item, topic.label)));
            topicDetails.appendChild(block);
          }});

          domainDetails.appendChild(topicDetails);
        }});

        const domainAuthorities = [
          ...neighborsByType(domain.id, "case"),
          ...neighborsByType(domain.id, "statute"),
        ]
          .filter((node, index, arr) => arr.findIndex((item) => item.id === node.id) === index)
          .slice(0, 12);

        if (domainAuthorities.length) {{
          const crossBlock = document.createElement("div");
          crossBlock.className = "group-block";
          const heading = document.createElement("div");
          heading.className = "group-title";
          heading.textContent = "Cross-cutting Authorities";
          crossBlock.appendChild(heading);
          domainAuthorities.forEach((item) => crossBlock.appendChild(makeNodeButton(item, domain.label)));
          domainDetails.appendChild(crossBlock);
        }}

        treeRoot.appendChild(domainDetails);
      }});
    }}

    function renderResults(query) {{
      const lowered = query.trim().toLowerCase();
      resultList.innerHTML = "";
      if (!lowered) return;
      const matches = nodes
        .filter((node) => `${{node.label}} ${{node.summary || ""}}`.toLowerCase().includes(lowered))
        .sort((a, b) => (b.degree || 0) - (a.degree || 0))
        .slice(0, 10);
      matches.forEach((node) => {{
        const item = document.createElement("li");
        item.appendChild(makeNodeButton(node, `degree ${{node.degree || 0}}`));
        resultList.appendChild(item);
      }});
      if (!matches.length) {{
        resultList.innerHTML = "<li class='empty'>No matching nodes.</li>";
      }}
    }}

    function renderMetrics(node) {{
      metricList.innerHTML = "";
      const metrics = Object.entries(node.metrics || {{}});
      const degreeItem = document.createElement("li");
      degreeItem.textContent = `degree: ${{node.degree || 0}}`;
      metricList.appendChild(degreeItem);
      if (!metrics.length) return;
      metrics.forEach(([key, value]) => {{
        const item = document.createElement("li");
        item.textContent = `${{key}}: ${{value}}`;
        metricList.appendChild(item);
      }});
    }}

    function renderLinks(node) {{
      linkList.innerHTML = "";
      if (!node.links || !node.links.length) {{
        linkList.innerHTML = "<li class='empty'>No external links available.</li>";
        return;
      }}
      node.links.forEach((link) => {{
        const item = document.createElement("li");
        item.innerHTML = `<a href="${{link.url}}" target="_blank" rel="noreferrer">${{link.label}}</a>`;
        linkList.appendChild(item);
      }});
    }}

    function renderReferences(node) {{
      referenceList.innerHTML = "";
      if (!node.references || !node.references.length) {{
        referenceList.innerHTML = "<li class='empty'>No references attached.</li>";
        return;
      }}
      node.references.forEach((reference) => {{
        const item = document.createElement("li");
        item.innerHTML = `<div class="ref-meta">${{reference.source_label}} · ${{reference.location}}</div><div>${{reference.snippet}}</div>`;
        referenceList.appendChild(item);
      }});
    }}

    function renderNeighbors(node) {{
      neighborList.innerHTML = "";
      const neighbors = [...(adjacency.get(node.id) || [])]
        .map((id) => nodeMap.get(id))
        .filter(Boolean)
        .sort((a, b) => a.label.localeCompare(b.label))
        .slice(0, 18);
      if (!neighbors.length) {{
        neighborList.innerHTML = "<li class='empty'>No related nodes.</li>";
        return;
      }}
      neighbors.forEach((neighbor) => {{
        const item = document.createElement("li");
        item.innerHTML = `<strong>${{neighbor.label}}</strong><div class="ref-meta">${{neighbor.type}}</div>`;
        item.addEventListener("click", () => selectNode(neighbor.id));
        neighborList.appendChild(item);
      }});
    }}

    function selectNode(nodeId) {{
      const node = nodeMap.get(nodeId);
      if (!node) return;
      titleEl.textContent = node.label;
      chipEl.textContent = node.type;
      chipEl.className = `chip ${{node.type}}`;
      summaryEl.textContent = node.summary || "No summary available.";
      renderMetrics(node);
      renderLinks(node);
      renderReferences(node);
      renderNeighbors(node);
    }}

    searchInput.addEventListener("input", (event) => renderResults(event.target.value));

    renderTree();
    const firstDomain = byType.domain[0];
    if (firstDomain) {{
      selectNode(firstDomain.id);
    }}
  </script>
</body>
</html>
"""


def render_relationship_family_tree(graph_payload: dict) -> str:
    data = json.dumps(graph_payload, ensure_ascii=False)
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Casemap Authority Tree</title>
  <style>
    :root {
      --bg: #edf0f4;
      --bg-deep: #dfe4ea;
      --ink: #101216;
      --muted: #6c727c;
      --line: rgba(16, 18, 22, 0.1);
      --line-strong: rgba(16, 18, 22, 0.16);
      --shadow: 0 24px 80px rgba(16, 18, 22, 0.08);
      --shadow-soft: 0 14px 32px rgba(16, 18, 22, 0.06);
      --glass: blur(22px);
      --root: #0f1114;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.8), transparent 28%),
        radial-gradient(circle at top right, rgba(199, 205, 214, 0.34), transparent 24%),
        linear-gradient(180deg, #f8f9fb 0%, var(--bg) 48%, var(--bg-deep) 100%);
    }

    .shell {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 390px;
      min-height: 100vh;
    }

    .workspace {
      padding: 28px;
      overflow: auto;
    }

    .detail-panel {
      border-left: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(242, 244, 247, 0.94));
      backdrop-filter: var(--glass);
      -webkit-backdrop-filter: var(--glass);
      padding: 24px 22px 32px;
      overflow-y: auto;
    }

    .meta {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      margin-bottom: 10px;
    }

    h1, h2, h3 {
      margin: 0;
      font-weight: 600;
    }

    h1 {
      font-size: clamp(34px, 4vw, 52px);
      letter-spacing: -0.05em;
      line-height: 0.92;
      margin-bottom: 12px;
    }

    .intro {
      max-width: 920px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.62;
      margin: 0 0 18px;
    }

    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }

    .nav {
      display: inline-flex;
      gap: 8px;
      padding: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.56);
      backdrop-filter: var(--glass);
      -webkit-backdrop-filter: var(--glass);
      box-shadow: var(--shadow-soft);
    }

    .nav a {
      padding: 10px 14px;
      border-radius: 999px;
      color: var(--ink);
      text-decoration: none;
      font-size: 13px;
      letter-spacing: 0.01em;
    }

    .nav a.active {
      background: var(--root);
      color: white;
    }

    .search-box {
      width: min(360px, 100%);
      display: grid;
      gap: 8px;
    }

    .search-box input {
      width: 100%;
      border: 1px solid rgba(16, 18, 22, 0.12);
      border-radius: 18px;
      padding: 13px 15px;
      background: rgba(255, 255, 255, 0.82);
      box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.8);
      font: inherit;
      color: var(--ink);
    }

    .breadcrumbs {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 14px;
    }

    .crumb,
    .result-pill {
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.66);
      border-radius: 999px;
      padding: 9px 13px;
      font: inherit;
      font-size: 13px;
      color: var(--ink);
      cursor: pointer;
      box-shadow: var(--shadow-soft);
      touch-action: manipulation;
    }

    .results {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 16px;
      min-height: 18px;
    }

    .stack-view {
      display: grid;
      gap: 18px;
      padding-bottom: 22px;
    }

    .tree-section {
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 18px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(250, 251, 253, 0.72));
      backdrop-filter: var(--glass);
      -webkit-backdrop-filter: var(--glass);
      box-shadow: var(--shadow);
    }

    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }

    .section-title {
      font-size: 18px;
      letter-spacing: -0.02em;
    }

    .section-caption {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    .root-wrap,
    .domain-row,
    .topic-grid,
    .node-grid {
      display: flex;
      justify-content: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .topic-grid,
    .node-grid {
      justify-content: flex-start;
    }

    .tree-node {
      min-width: 200px;
      max-width: 300px;
      border: 1px solid rgba(16, 18, 22, 0.1);
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.84));
      box-shadow: var(--shadow-soft);
      padding: 14px 15px;
      text-align: left;
      cursor: pointer;
      transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
      touch-action: manipulation;
      font: inherit;
      color: var(--ink);
    }

    .tree-node.active {
      border-color: rgba(15, 17, 20, 0.28);
      box-shadow: 0 22px 54px rgba(15, 17, 20, 0.14);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(242, 244, 248, 0.92));
    }

    .tree-node.root {
      min-width: 320px;
      background: linear-gradient(180deg, #14171b, #0f1114);
      color: white;
      border-color: rgba(15, 17, 20, 0.66);
    }

    .tree-node.module {
      background: linear-gradient(180deg, rgba(248, 249, 251, 0.94), rgba(229, 233, 239, 0.88));
    }

    .tree-node.subground {
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(239, 242, 246, 0.88));
    }

    .tree-node.case,
    .tree-node.statute,
    .tree-node.source,
    .tree-node.topic {
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(245, 247, 250, 0.92));
    }

    .node-kicker {
      display: inline-flex;
      margin-bottom: 10px;
      padding: 5px 9px;
      border-radius: 999px;
      font-size: 10px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.54);
      border: 1px solid rgba(16, 18, 22, 0.08);
    }

    .tree-node.root .node-kicker {
      color: rgba(255, 255, 255, 0.76);
      background: rgba(255, 255, 255, 0.08);
      border-color: rgba(255, 255, 255, 0.14);
    }

    .node-name {
      display: block;
      font-size: 16px;
      line-height: 1.24;
      letter-spacing: -0.02em;
    }

    .node-subtitle {
      display: block;
      margin-top: 6px;
      font-size: 12px;
      line-height: 1.45;
      color: var(--muted);
      letter-spacing: 0.01em;
    }

    .tree-node.root .node-name {
      font-size: 20px;
    }

    .tree-node.root .node-subtitle {
      color: rgba(255, 255, 255, 0.78);
    }

    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    .micro-chip,
    .signal-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid rgba(16, 18, 22, 0.1);
      border-radius: 999px;
      padding: 6px 9px;
      font-size: 11px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.76);
    }

    .tree-node.root .micro-chip {
      color: rgba(255, 255, 255, 0.76);
      background: rgba(255, 255, 255, 0.08);
      border-color: rgba(255, 255, 255, 0.14);
    }

    .micro-chip.code,
    .signal-chip.code {
      color: var(--ink);
      background: rgba(199, 205, 214, 0.28);
    }

    .signal-chip.adopted,
    .signal-chip.followed,
    .signal-chip.applied {
      color: white;
      background: var(--root);
      border-color: rgba(15, 17, 20, 0.3);
    }

    .signal-chip.qualified,
    .signal-chip.originating-authority,
    .signal-chip.relevant-authority {
      color: var(--ink);
      background: rgba(199, 205, 214, 0.32);
    }

    .signal-chip.not-adopted,
    .signal-chip.codified {
      color: var(--ink);
      background: rgba(149, 157, 168, 0.24);
    }

    .authority-stack {
      display: grid;
      gap: 16px;
    }

    .lineage-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
      align-items: start;
    }

    .lineage-panel,
    .aux-panel {
      border: 1px solid rgba(16, 18, 22, 0.08);
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(246, 248, 251, 0.82));
      padding: 16px;
      box-shadow: var(--shadow-soft);
    }

    .branch-head {
      margin-bottom: 14px;
    }

    .branch-head h3 {
      font-size: 16px;
      line-height: 1.2;
      letter-spacing: -0.02em;
      margin-bottom: 6px;
    }

    .branch-meta {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    .lineage-track {
      position: relative;
      display: grid;
      gap: 14px;
      justify-items: center;
      padding: 4px 0;
    }

    .lineage-track::before {
      content: "";
      position: absolute;
      top: 8px;
      bottom: 8px;
      left: calc(50% - 1px);
      width: 2px;
      border-radius: 999px;
      background: linear-gradient(180deg, rgba(199, 205, 214, 0.15), rgba(149, 157, 168, 0.5), rgba(199, 205, 214, 0.15));
    }

    .lineage-step {
      width: 100%;
      display: flex;
      justify-content: center;
      position: relative;
      z-index: 1;
    }

    .lineage-step .tree-node {
      width: min(100%, 260px);
    }

    .aux-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }

    .detail-type {
      display: inline-flex;
      margin-bottom: 14px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.86);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }

    .detail-summary {
      font-size: 15px;
      line-height: 1.64;
      margin: 0 0 16px;
    }

    .detail-summary .secondary-copy,
    .detail-title-sub {
      display: block;
      color: var(--muted);
    }

    .detail-summary .secondary-copy {
      margin-top: 8px;
      font-size: 14px;
      line-height: 1.6;
    }

    .detail-title-sub {
      margin-top: 5px;
      font-size: 15px;
      line-height: 1.5;
      letter-spacing: 0.01em;
    }

    .signal-panel {
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 14px;
      background: rgba(255, 255, 255, 0.66);
      box-shadow: var(--shadow-soft);
      margin-bottom: 18px;
    }

    .signal-panel.empty-state {
      color: var(--muted);
      font-style: italic;
    }

    .signal-panel p {
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.58;
    }

    .data-list {
      list-style: none;
      padding: 0;
      margin: 0 0 18px;
      display: grid;
      gap: 10px;
    }

    .data-list li {
      border: 1px solid rgba(16, 18, 22, 0.08);
      border-radius: 18px;
      padding: 12px 14px;
      background: rgba(255, 255, 255, 0.6);
      line-height: 1.5;
      font-size: 14px;
      box-shadow: var(--shadow-soft);
    }

    .data-list li.clickable {
      cursor: pointer;
      touch-action: manipulation;
    }

    .list-meta {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 5px;
    }

    .empty {
      color: var(--muted);
      font-style: italic;
    }

    a {
      color: var(--ink);
      text-decoration: none;
      border-bottom: 1px solid rgba(16, 18, 22, 0.16);
    }

    a:hover {
      border-color: rgba(16, 18, 22, 0.36);
    }

    @media (hover: hover) and (pointer: fine) {
      .tree-node:hover {
        border-color: var(--line-strong);
        box-shadow: 0 20px 44px rgba(16, 18, 22, 0.08);
      }
    }

    @media (max-width: 1120px) {
      .shell {
        grid-template-columns: 1fr;
      }

      .detail-panel {
        border-left: 0;
        border-top: 1px solid var(--line);
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="workspace">
      <div class="meta">Casemap Vertical Tree</div>
      <h1>Hong Kong Contract Law Authority Tree</h1>
      <p class="intro">A top-down lifecycle tree for Hong Kong contract law. The structural cards stay compact so the full map remains readable. Hover or click a ground, sub-ground, topic, case, or statute to open bilingual summaries, mapped topics, and authority paths in the side panel.</p>
      <div class="toolbar">
        <nav class="nav">
          <a href="/" class="active">Authority Tree</a>
          <a href="/relationships">Relationship Graph</a>
          <a href="/mvp">MVP GraphRAG</a>
        </nav>
        <label class="search-box">
          <span class="meta">Jump To Node</span>
          <input id="searchInput" type="search" placeholder="Module, sub-ground, case, statute, source">
        </label>
      </div>
      <div id="breadcrumbs" class="breadcrumbs"></div>
      <div id="results" class="results"></div>
      <div id="treeStack" class="stack-view"></div>
    </section>
    <aside class="detail-panel">
      <div class="meta">Selection</div>
      <h2 id="detailTitle">Overview</h2>
      <div id="detailType" class="detail-type">Root</div>
      <div id="detailSummary" class="detail-summary">Hover or click a branch to inspect bilingual summaries, lineage paths, mapped topics, public notes, and linked authorities.</div>
      <div id="detailSignal" class="signal-panel empty-state">Treatment notes and short quotations appear here when a node carries them.</div>
      <div class="meta">Metrics</div>
      <ul id="metricList" class="data-list"><li class="empty">Choose a node to view metrics.</li></ul>
      <div class="meta">External Links</div>
      <ul id="linkList" class="data-list"><li class="empty">No node selected.</li></ul>
      <div class="meta">Lineage Paths</div>
      <ul id="lineageList" class="data-list"><li class="empty">No lineage path selected.</li></ul>
      <div class="meta">Topic Mapping</div>
      <ul id="topicList" class="data-list"><li class="empty">No mapping selected.</li></ul>
      <div class="meta">References</div>
      <ul id="referenceList" class="data-list"><li class="empty">No references attached.</li></ul>
      <div class="meta">Related Authorities</div>
      <ul id="neighborList" class="data-list"><li class="empty">No related nodes.</li></ul>
    </aside>
  </div>
  <script>
    const payload = __CASEMAP_DATA__;
    const nodes = payload.nodes || [];
    const edges = payload.edges || [];
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const adjacency = new Map();
    edges.forEach((edge) => {
      if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set());
      if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set());
      adjacency.get(edge.source).add(edge.target);
      adjacency.get(edge.target).add(edge.source);
    });

    const authorityTree = payload.meta.authority_tree || {};
    const modules = (authorityTree.modules || []).map((module) => ({
      ...module,
      type: "module",
      subgrounds: (module.subgrounds || []).map((subground) => ({
        ...subground,
        type: "subground",
        module_id: module.id,
      })),
    }));
    const moduleMap = new Map(modules.map((module) => [module.id, module]));
    const subgrounds = modules.flatMap((module) => module.subgrounds);
    const subgroundMap = new Map(subgrounds.map((subground) => [subground.id, subground]));

    const lineages = (payload.meta.lineages || [])
      .map((lineage) => ({
        ...lineage,
        members: (lineage.members || []).filter((member) => nodeMap.has(member.node_id)),
      }))
      .sort((left, right) => left.title.localeCompare(right.title));
    const lineageMap = new Map(lineages.map((lineage) => [lineage.id, lineage]));

    const subgroundsByTopic = new Map();
    subgrounds.forEach((subground) => {
      (subground.topic_ids || []).forEach((topicId) => {
        const current = subgroundsByTopic.get(topicId) || [];
        current.push(subground);
        subgroundsByTopic.set(topicId, current);
      });
    });

    const searchables = [
      ...modules,
      ...subgrounds,
      ...nodes.filter((node) => node.type !== "domain"),
    ];

    const treeStack = document.getElementById("treeStack");
    const breadcrumbsEl = document.getElementById("breadcrumbs");
    const resultsEl = document.getElementById("results");
    const searchInput = document.getElementById("searchInput");
    const detailTitle = document.getElementById("detailTitle");
    const detailType = document.getElementById("detailType");
    const detailSummary = document.getElementById("detailSummary");
    const detailSignal = document.getElementById("detailSignal");
    const metricList = document.getElementById("metricList");
    const linkList = document.getElementById("linkList");
    const lineageList = document.getElementById("lineageList");
    const topicList = document.getElementById("topicList");
    const referenceList = document.getElementById("referenceList");
    const neighborList = document.getElementById("neighborList");
    const hoverPreviewEnabled = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

    const rootNode = {
      id: "__root__",
      label: authorityTree.label_en || payload.meta.title || "Hong Kong Contract Law",
      secondary_label: authorityTree.label_zh || "香港合同法知識圖譜",
      type: "root",
      summary: authorityTree.summary_en || "Lifecycle-based doctrinal overview. Choose a module, then a sub-ground, then an authority branch.",
      summary_zh: authorityTree.summary_zh || "按合同生命週期組織的總覽。先選模組，再選子議題，再展開權威路徑。",
      metrics: {
        modules: modules.length,
        subgrounds: subgrounds.length,
        topics: nodes.filter((node) => node.type === "topic").length,
        authorities: nodes.filter((node) => node.type === "case" || node.type === "statute").length,
        lineages: payload.meta.curated_lineage_count || lineages.length,
      },
      links: [],
      references: [],
      lineage_memberships: [],
    };

    const state = {
      moduleId: null,
      subgroundId: null,
      selectedId: rootNode.id,
    };

    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char]));
    }

    function getNode(nodeId) {
      if (nodeId === rootNode.id) return rootNode;
      if (moduleMap.has(nodeId)) return moduleMap.get(nodeId);
      if (subgroundMap.has(nodeId)) return subgroundMap.get(nodeId);
      return nodeMap.get(nodeId) || null;
    }

    function labelForType(type) {
      const labels = {
        root: "Root",
        module: "Ground",
        subground: "Sub-ground",
        topic: "Mapped Topic",
        case: "Case",
        statute: "Statute",
        source: "Source",
      };
      return labels[type] || type;
    }

    function statusClass(value) {
      return String(value || "relevant authority").toLowerCase().replace(/[^a-z0-9]+/g, "-");
    }

    function sortByLabel(items) {
      return items.slice().sort((left, right) => (left.label || "").localeCompare(right.label || ""));
    }

    function neighborsByType(nodeId, type) {
      return sortByLabel(
        [...(adjacency.get(nodeId) || [])]
          .map((neighborId) => getNode(neighborId))
          .filter((node) => node && node.type === type)
      );
    }

    function relatedLineagesForIds(lineageIds) {
      return [...new Set(lineageIds || [])]
        .map((lineageId) => lineageMap.get(lineageId))
        .filter(Boolean)
        .sort((left, right) => left.title.localeCompare(right.title));
    }

    function preferredSubgroundForNode(node) {
      if (!node || node.type === "root" || node.type === "module" || node.type === "subground") {
        return null;
      }

      const topicIds = new Set();
      if (node.type === "topic") {
        topicIds.add(node.id);
      }
      neighborsByType(node.id, "topic").forEach((topic) => topicIds.add(topic.id));
      (node.lineage_memberships || []).forEach((membership) => {
        (membership.topic_ids || []).forEach((topicId) => topicIds.add(topicId));
      });

      if (state.subgroundId) {
        const current = subgroundMap.get(state.subgroundId);
        if (current && (current.topic_ids || []).some((topicId) => topicIds.has(topicId))) {
          return current;
        }
      }

      const scored = subgrounds
        .map((subground) => {
          let score = 0;
          (subground.topic_ids || []).forEach((topicId) => {
            if (topicIds.has(topicId)) score += 3;
          });
          (node.lineage_memberships || []).forEach((membership) => {
            if ((subground.lineage_ids || []).includes(membership.lineage_id)) score += 2;
          });
          if (node.type === "topic" && (subground.topic_ids || []).includes(node.id)) score += 2;
          return { subground, score };
        })
        .filter((item) => item.score > 0)
        .sort((left, right) => right.score - left.score || left.subground.label.localeCompare(right.subground.label));
      return scored.length ? scored[0].subground : null;
    }

    function relatedLineagesForNode(node) {
      if (!node) return [];
      if (node.type === "module") {
        return relatedLineagesForIds(node.subgrounds.flatMap((subground) => subground.lineage_ids || []));
      }
      if (node.type === "subground") {
        return relatedLineagesForIds(node.lineage_ids || []);
      }
      if (node.type === "topic") {
        return relatedLineagesForIds(
          ((subgroundsByTopic.get(node.id) || []).flatMap((subground) => subground.lineage_ids || []))
        );
      }
      const lineageIds = new Set((node.lineage_memberships || []).map((membership) => membership.lineage_id));
      return [...lineageIds]
        .map((lineageId) => lineageMap.get(lineageId))
        .filter(Boolean)
        .sort((left, right) => left.title.localeCompare(right.title));
    }

    function setSelection(node) {
      if (!node) return;
      if (node.type === "root") {
        state.moduleId = null;
        state.subgroundId = null;
        state.selectedId = rootNode.id;
        return;
      }
      if (node.type === "module") {
        state.moduleId = node.id;
        state.subgroundId = null;
        state.selectedId = node.id;
        return;
      }
      if (node.type === "subground") {
        state.moduleId = node.module_id;
        state.subgroundId = node.id;
        state.selectedId = node.id;
        return;
      }
      const subground = preferredSubgroundForNode(node);
      if (subground) {
        state.moduleId = subground.module_id;
        state.subgroundId = subground.id;
      }
      state.selectedId = node.id;
    }

    function makeSection(title, caption) {
      const section = document.createElement("section");
      section.className = "tree-section";
      const head = document.createElement("div");
      head.className = "section-head";
      head.innerHTML = `<h3 class="section-title">${escapeHtml(title)}</h3><div class="section-caption">${escapeHtml(caption || "")}</div>`;
      section.appendChild(head);
      return section;
    }

    function bindNodeInteractions(element, node) {
      if (hoverPreviewEnabled) {
        element.addEventListener("mouseenter", () => renderDetails(node, true));
        element.addEventListener("mouseleave", () => renderDetails(getNode(state.selectedId) || rootNode));
      }
      element.addEventListener("click", () => {
        setSelection(node);
        render();
      });
    }

    function createNodeCard(node, extra = {}) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `tree-node ${node.type}`;
      if (state.selectedId === node.id) {
        button.classList.add("active");
      }

      const chips = [];
      if (extra.countLabel) chips.push(`<span class="micro-chip">${escapeHtml(extra.countLabel)}</span>`);
      if (extra.code) chips.push(`<span class="micro-chip code">${escapeHtml(extra.code)}</span>`);
      if (extra.treatment) chips.push(`<span class="signal-chip ${statusClass(extra.treatment)}">${escapeHtml(extra.treatment)}</span>`);
      if (extra.coverage === "placeholder") chips.push(`<span class="micro-chip code">HKLII refine</span>`);

      button.title = extra.preview || node.summary || node.label;
      button.innerHTML = `
        <span class="node-kicker">${escapeHtml(extra.kicker || labelForType(node.type))}</span>
        <span class="node-name">${escapeHtml(node.label)}</span>
        ${(extra.secondaryLabel || node.secondary_label || node.label_zh) ? `<span class="node-subtitle">${escapeHtml(extra.secondaryLabel || node.secondary_label || node.label_zh)}</span>` : ""}
        <span class="chip-row">${chips.join("")}</span>
      `;
      bindNodeInteractions(button, node);
      return button;
    }

    function fillList(listEl, items, emptyText) {
      listEl.innerHTML = "";
      if (!items.length) {
        listEl.innerHTML = `<li class="empty">${escapeHtml(emptyText)}</li>`;
        return;
      }
      items.forEach((item) => listEl.appendChild(item));
    }

    function dualSummary(node) {
      const en = node.summary_en || node.summary || "";
      const zh = node.summary_zh || "";
      if (!zh) return `<span>${escapeHtml(en || "No summary available.")}</span>`;
      return `<span>${escapeHtml(en || "No summary available.")}</span><span class="secondary-copy">${escapeHtml(zh)}</span>`;
    }

    function renderDetails(node, preview = false) {
      const target = node || rootNode;
      const profile = target.case_profile || {};
      const memberships = target.lineage_memberships || [];

      detailTitle.innerHTML = `${escapeHtml(target.label)}${target.secondary_label ? `<span class="detail-title-sub">${escapeHtml(target.secondary_label)}</span>` : ""}`;
      detailType.textContent = preview ? `${labelForType(target.type)} Preview` : labelForType(target.type);
      if (target.type === "case" || target.type === "statute" || target.type === "source" || target.type === "topic") {
        detailSummary.innerHTML = `<span>${escapeHtml(profile.note || profile.quote || target.summary || "No summary available.")}</span>`;
      } else {
        detailSummary.innerHTML = dualSummary(target);
      }

      const signalBits = [];
      if (profile.treatment) signalBits.push(`<span class="signal-chip ${statusClass(profile.treatment)}">${escapeHtml(profile.treatment)}</span>`);
      if (profile.code) signalBits.push(`<span class="signal-chip code">${escapeHtml(profile.code)}</span>`);
      if (memberships.length) signalBits.push(`<span class="signal-chip code">${memberships.length} lineage path(s)</span>`);
      if (target.type === "subground" && target.coverage === "placeholder") signalBits.push(`<span class="signal-chip code">HKLII refinement suggested</span>`);
      const noteText = profile.quote || profile.note || "";
      const childText = (target.children || []).map((child) => `${child.en} / ${child.zh}`).join(" · ");

      if (!signalBits.length && !noteText && !childText) {
        detailSignal.className = "signal-panel empty-state";
        detailSignal.textContent = "Hover or click a node to surface treatment notes, short quotations, mapped sub-branches, and lineage codes.";
      } else {
        detailSignal.className = "signal-panel";
        detailSignal.innerHTML = `${signalBits.join("")}${noteText ? `<p>${escapeHtml(noteText)}</p>` : ""}${childText ? `<p>${escapeHtml(childText)}</p>` : ""}`;
      }

      const metricItems = [];
      if (!["module", "subground"].includes(target.type)) {
        const degree = target.id === rootNode.id ? 0 : (target.degree || 0);
        const degreeItem = document.createElement("li");
        degreeItem.textContent = `degree: ${degree}`;
        metricItems.push(degreeItem);
      }
      Object.entries(target.metrics || {}).forEach(([key, value]) => {
        const item = document.createElement("li");
        item.textContent = `${key}: ${value}`;
        metricItems.push(item);
      });
      fillList(metricList, metricItems, "No extra metrics available.");

      const linkItems = (target.links || []).map((link) => {
        const item = document.createElement("li");
        item.innerHTML = `<a href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.label)}</a>`;
        return item;
      });
      fillList(linkList, linkItems, "No external links available.");

      const lineageItems = [];
      if (target.id === rootNode.id) {
        Object.entries(payload.meta.lineage_codes || {}).forEach(([code, meaning]) => {
          const item = document.createElement("li");
          item.innerHTML = `<div class="list-meta">${escapeHtml(code)}</div><div>${escapeHtml(meaning)}</div>`;
          lineageItems.push(item);
        });
      } else if (target.type === "module" || target.type === "subground" || target.type === "topic") {
        relatedLineagesForNode(target).forEach((lineage) => {
          const item = document.createElement("li");
          item.innerHTML = `<div class="list-meta">${escapeHtml((lineage.codes || []).join(" · ") || "authority path")}</div><strong>${escapeHtml(lineage.title)}</strong>`;
          lineageItems.push(item);
        });
      } else {
        memberships.forEach((membership) => {
          const item = document.createElement("li");
          item.className = "clickable";
          item.innerHTML = `
            <div class="list-meta">${escapeHtml(membership.code || "lineage")} · ${escapeHtml(membership.treatment || "authority")}</div>
            <strong>${escapeHtml(membership.lineage_title)}</strong>
            <div>${escapeHtml(membership.note || "No additional note attached.")}</div>
          `;
          item.addEventListener("click", () => {
            const subground = (membership.topic_ids || [])
              .flatMap((topicId) => subgroundsByTopic.get(topicId) || [])
              .find(Boolean);
            if (subground) {
              setSelection(subground);
              render();
            }
          });
          lineageItems.push(item);
        });
      }
      fillList(lineageList, lineageItems, "No lineage path attached.");

      const topicItems = [];
      if (target.type === "module") {
        target.subgrounds.forEach((subground) => {
          const item = document.createElement("li");
          item.className = "clickable";
          item.innerHTML = `<div class="list-meta">Sub-ground / 子議題</div><strong>${escapeHtml(subground.label)}</strong><div>${escapeHtml((subground.topic_labels || []).join(" · ") || "Awaiting mapped topic refinement.")}</div>`;
          bindNodeInteractions(item, subground);
          topicItems.push(item);
        });
      } else if (target.type === "subground") {
        (target.topic_ids || []).map((topicId) => getNode(topicId)).filter(Boolean).forEach((topic) => {
          const item = document.createElement("li");
          item.className = "clickable";
          item.innerHTML = `<div class="list-meta">Mapped topic</div><strong>${escapeHtml(topic.label)}</strong>`;
          bindNodeInteractions(item, topic);
          topicItems.push(item);
        });
      } else if (target.type === "topic") {
        (subgroundsByTopic.get(target.id) || []).forEach((subground) => {
          const item = document.createElement("li");
          item.className = "clickable";
          item.innerHTML = `<div class="list-meta">Lifecycle branch</div><strong>${escapeHtml(subground.label)}</strong>`;
          bindNodeInteractions(item, subground);
          topicItems.push(item);
        });
      } else if (target.type !== "root") {
        neighborsByType(target.id, "topic").forEach((topic) => {
          const item = document.createElement("li");
          item.className = "clickable";
          item.innerHTML = `<div class="list-meta">Mapped topic</div><strong>${escapeHtml(topic.label)}</strong>`;
          bindNodeInteractions(item, topic);
          topicItems.push(item);
        });
      }
      fillList(topicList, topicItems, "No mapped topic information.");

      const referenceItems = (target.references || []).map((reference) => {
        const item = document.createElement("li");
        item.innerHTML = `<div class="list-meta">${escapeHtml(reference.source_label)} · ${escapeHtml(reference.location)}</div><div>${escapeHtml(reference.snippet)}</div>`;
        return item;
      });
      if (!referenceItems.length && target.type === "subground" && (target.children || []).length) {
        target.children.forEach((child) => {
          const item = document.createElement("li");
          item.innerHTML = `<div class="list-meta">Doctrinal branch</div><div>${escapeHtml(child.en)} / ${escapeHtml(child.zh)}</div>`;
          referenceItems.push(item);
        });
      }
      fillList(referenceList, referenceItems, "No references attached.");

      const neighborItems = [];
      if (target.type === "subground") {
        [...(target.case_ids || []), ...(target.statute_ids || []), ...(target.source_ids || [])]
          .map((nodeId) => getNode(nodeId))
          .filter(Boolean)
          .slice(0, 16)
          .forEach((neighbor) => {
            const item = document.createElement("li");
            item.className = "clickable";
            item.innerHTML = `<div class="list-meta">${escapeHtml(labelForType(neighbor.type))}</div><strong>${escapeHtml(neighbor.label)}</strong>`;
            bindNodeInteractions(item, neighbor);
            neighborItems.push(item);
          });
      } else if (target.id !== rootNode.id && target.type !== "module") {
        neighborsByType(target.id, "topic")
          .concat(neighborsByType(target.id, "case"))
          .concat(neighborsByType(target.id, "statute"))
          .concat(neighborsByType(target.id, "source"))
          .filter((neighbor, index, values) => values.findIndex((item) => item.id === neighbor.id) === index)
          .slice(0, 14)
          .forEach((neighbor) => {
            const item = document.createElement("li");
            item.className = "clickable";
            item.innerHTML = `<div class="list-meta">${escapeHtml(labelForType(neighbor.type))}</div><strong>${escapeHtml(neighbor.label)}</strong>`;
            bindNodeInteractions(item, neighbor);
            neighborItems.push(item);
          });
      }
      fillList(neighborList, neighborItems, "No related nodes.");
    }

    function renderBreadcrumbs() {
      breadcrumbsEl.innerHTML = "";
      const trail = [rootNode];
      if (state.moduleId) trail.push(getNode(state.moduleId));
      if (state.subgroundId) trail.push(getNode(state.subgroundId));
      const selectedNode = getNode(state.selectedId);
      if (selectedNode && ![rootNode.id, state.moduleId, state.subgroundId].includes(selectedNode.id)) {
        trail.push(selectedNode);
      }

      trail.filter(Boolean).forEach((node) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "crumb";
        button.textContent = node.label;
        bindNodeInteractions(button, node);
        breadcrumbsEl.appendChild(button);
      });
    }

    function renderResults(query) {
      const lowered = query.trim().toLowerCase();
      resultsEl.innerHTML = "";
      if (!lowered) return;
      const matches = searchables
        .filter((node) => `${node.label || ""} ${node.secondary_label || ""} ${node.summary || ""} ${node.summary_zh || ""}`.toLowerCase().includes(lowered))
        .sort((left, right) => (right.degree || 0) - (left.degree || 0) || (left.label || "").localeCompare(right.label || ""))
        .slice(0, 12);

      if (!matches.length) {
        resultsEl.innerHTML = "<div class='empty'>No matching nodes.</div>";
        return;
      }

      matches.forEach((node) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "result-pill";
        button.textContent = `${node.label} · ${labelForType(node.type)}`;
        bindNodeInteractions(button, node);
        resultsEl.appendChild(button);
      });
    }

    function renderAuthorityLineage(lineage) {
      const panel = document.createElement("article");
      panel.className = "lineage-panel";
      panel.innerHTML = `<div class="branch-head"><h3>${escapeHtml(lineage.title)}</h3><div class="branch-meta">${escapeHtml((lineage.codes || []).join(" · ") || "authority path")}</div></div>`;
      const track = document.createElement("div");
      track.className = "lineage-track";
      (lineage.members || []).forEach((member) => {
        const node = getNode(member.node_id);
        if (!node) return;
        const step = document.createElement("div");
        step.className = "lineage-step";
        step.appendChild(
          createNodeCard(node, {
            kicker: member.type === "statute" ? "statute" : "case",
            code: member.code,
            treatment: member.treatment,
            preview: member.note || node.summary,
          })
        );
        track.appendChild(step);
      });
      panel.appendChild(track);
      return panel;
    }

    function renderAuxPanel(title, caption, items, cardBuilder) {
      if (!items.length) return null;
      const panel = document.createElement("article");
      panel.className = "aux-panel";
      panel.innerHTML = `<div class="branch-head"><h3>${escapeHtml(title)}</h3><div class="branch-meta">${escapeHtml(caption)}</div></div>`;
      const grid = document.createElement("div");
      grid.className = "aux-grid";
      items.forEach((item) => grid.appendChild(cardBuilder(item)));
      panel.appendChild(grid);
      return panel;
    }

    function selectedSubground() {
      return state.subgroundId ? getNode(state.subgroundId) : null;
    }

    function renderTree() {
      treeStack.innerHTML = "";

      const rootSection = makeSection("Overview", "start here");
      const rootWrap = document.createElement("div");
      rootWrap.className = "root-wrap";
      rootWrap.appendChild(
        createNodeCard(rootNode, {
          kicker: "root",
          countLabel: `${modules.length} modules · ${subgrounds.length} sub-grounds · ${lineages.length} lineages`,
          preview: rootNode.summary,
          secondaryLabel: rootNode.secondary_label,
        })
      );
      rootSection.appendChild(rootWrap);
      treeStack.appendChild(rootSection);

      const moduleSection = makeSection("Lifecycle Modules", "合同生命週期模組");
      const moduleRow = document.createElement("div");
      moduleRow.className = "domain-row";
      modules.forEach((module) => {
        moduleRow.appendChild(
          createNodeCard(module, {
            countLabel: `${module.metrics.subgrounds} sub-grounds · ${module.metrics.lineages} lineages`,
            secondaryLabel: module.label_zh,
          })
        );
      });
      moduleSection.appendChild(moduleRow);
      treeStack.appendChild(moduleSection);

      if (!state.moduleId || !getNode(state.moduleId)) return;
      const selectedModule = getNode(state.moduleId);
      const subgroundSection = makeSection(selectedModule.label, "子議題 / sub-grounds");
      const subgroundGrid = document.createElement("div");
      subgroundGrid.className = "topic-grid";
      selectedModule.subgrounds.forEach((subground) => {
        subgroundGrid.appendChild(
          createNodeCard(subground, {
            countLabel: `${subground.metrics.cases} cases · ${subground.metrics.statutes} statutes · ${subground.metrics.lineages} lineages`,
            secondaryLabel: subground.label_zh,
            coverage: subground.coverage,
          })
        );
      });
      subgroundSection.appendChild(subgroundGrid);
      treeStack.appendChild(subgroundSection);

      const currentSubground = selectedSubground();
      if (!currentSubground) return;

      const cases = (currentSubground.case_ids || []).map((nodeId) => getNode(nodeId)).filter(Boolean);
      const statutes = (currentSubground.statute_ids || []).map((nodeId) => getNode(nodeId)).filter(Boolean);
      const sources = (currentSubground.source_ids || []).map((nodeId) => getNode(nodeId)).filter(Boolean);
      const matchedLineages = relatedLineagesForIds(currentSubground.lineage_ids || []);
      const lineageNodeIds = new Set(matchedLineages.flatMap((lineage) => (lineage.members || []).map((member) => member.node_id)));

      const authoritySection = makeSection(currentSubground.label, "authority branches");
      const authorityStack = document.createElement("div");
      authorityStack.className = "authority-stack";

      if (matchedLineages.length) {
        const lineageGrid = document.createElement("div");
        lineageGrid.className = "lineage-grid";
        matchedLineages.forEach((lineage) => lineageGrid.appendChild(renderAuthorityLineage(lineage)));
        authorityStack.appendChild(lineageGrid);
      }

      const auxPanels = [];
      const extraCases = cases.filter((node) => !lineageNodeIds.has(node.id));
      const extraStatutes = statutes.filter((node) => !lineageNodeIds.has(node.id));

      const otherCasesPanel = renderAuxPanel("Other Cases", "same branch but outside the curated lineage", extraCases, (caseNode) =>
        createNodeCard(caseNode, {
          kicker: "case",
          treatment: (caseNode.case_profile || {}).treatment,
          code: (caseNode.case_profile || {}).code,
        })
      );
      if (otherCasesPanel) auxPanels.push(otherCasesPanel);

      const statutePanel = renderAuxPanel("Statutes", "public primary materials", extraStatutes, (statuteNode) =>
        createNodeCard(statuteNode, { kicker: "statute" })
      );
      if (statutePanel) auxPanels.push(statutePanel);

      const sourcePanel = renderAuxPanel("Sources", "supporting materials and bibliography", sources, (sourceNode) =>
        createNodeCard(sourceNode, { kicker: "source" })
      );
      if (sourcePanel) auxPanels.push(sourcePanel);

      if (auxPanels.length) {
        const auxGrid = document.createElement("div");
        auxGrid.className = "lineage-grid";
        auxPanels.forEach((panel) => auxGrid.appendChild(panel));
        authorityStack.appendChild(auxGrid);
      }

      authoritySection.appendChild(authorityStack);
      treeStack.appendChild(authoritySection);

      const selectedNode = getNode(state.selectedId);
      if (!selectedNode || [rootNode.id, state.moduleId, state.subgroundId].includes(selectedNode.id)) return;
      const focusedLineages = relatedLineagesForNode(selectedNode).filter((lineage) => {
        const lineageTopicIds = lineage.topic_ids || [];
        return (currentSubground.topic_ids || []).some((topicId) => lineageTopicIds.includes(topicId))
          || (lineage.members || []).some((member) => member.node_id === selectedNode.id);
      });
      if (!focusedLineages.length && selectedNode.type === "topic") return;

      const focusSection = makeSection("Focused Authority Path", "zoomed branch");
      if (focusedLineages.length) {
        const focusGrid = document.createElement("div");
        focusGrid.className = "lineage-grid";
        focusedLineages.forEach((lineage) => focusGrid.appendChild(renderAuthorityLineage(lineage)));
        focusSection.appendChild(focusGrid);
      } else {
        const relatedPanel = renderAuxPanel(
          "Related Authorities",
          "same branch connections",
          neighborsByType(selectedNode.id, "case")
            .concat(neighborsByType(selectedNode.id, "statute"))
            .filter((neighbor, index, values) => values.findIndex((item) => item.id === neighbor.id) === index)
            .slice(0, 12),
          (neighbor) => createNodeCard(neighbor, {
            kicker: labelForType(neighbor.type).toLowerCase(),
            treatment: (neighbor.case_profile || {}).treatment,
            code: (neighbor.case_profile || {}).code,
          })
        );
        if (relatedPanel) focusSection.appendChild(relatedPanel);
      }
      treeStack.appendChild(focusSection);
    }

    function render() {
      renderBreadcrumbs();
      renderTree();
      renderDetails(getNode(state.selectedId) || rootNode);
      renderResults(searchInput.value);
    }

    searchInput.addEventListener("input", (event) => renderResults(event.target.value));
    render();
  </script>
</body>
</html>
"""
    return html.replace("__CASEMAP_DATA__", data)


def render_hybrid_hierarchy(graph_payload: dict, page_mode: str = "hierarchy") -> str:
    data = json.dumps(graph_payload, ensure_ascii=False)
    is_internal = page_mode == "internal"
    meta = graph_payload.get("meta", {})
    meta_label = "Internal Explorer" if is_internal else "Casemap Hybrid Hierarchy"
    heading = (
        meta.get("viewer_heading_internal", "Hong Kong Contract Law Internal Hierarchy Explorer")
        if is_internal
        else meta.get("viewer_heading_public", "Hong Kong Contract Law Hierarchical Knowledge Graph")
    )
    intro = (
        meta.get(
            "viewer_intro_internal",
            "This internal route now uses the same visual hierarchy graph so the doctrinal tree is complete and explorable here as well. "
            "Start at the lifecycle modules, drill into subgrounds and topics, then inspect linked cases, statutes, and curated authority lineages.",
        )
        if is_internal
        else meta.get(
            "viewer_intro_public",
            "The graph is back as a visual hierarchy. Start at the lifecycle modules, drill into subgrounds and topics, then inspect the linked cases, statutes, and curated authority lineages for each branch.",
        )
    )
    graph_copy = (
        "Zoom, pan, and expand the internal hierarchy tree. The doctrinal spine stays hierarchical while topic branches reveal linked cases, statutes, and authority lineages."
        if is_internal
        else "Zoom, pan, and expand the doctrinal tree. Modules, subgrounds, and topics stay hierarchical; topic branches reveal linked cases, statutes, and authority lineages."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{graph_payload["meta"].get("title", "Casemap Hybrid Hierarchical Graph")}</title>
  <style>
    :root {{
      --bg: #f3ede2;
      --bg-deep: #ebe2d2;
      --panel: rgba(255, 250, 242, 0.88);
      --panel-strong: rgba(255, 255, 255, 0.92);
      --ink: #1f2328;
      --muted: #6e675d;
      --line: rgba(31, 35, 40, 0.12);
      --shadow: 0 20px 60px rgba(31, 35, 40, 0.08);
      --shadow-soft: 0 12px 28px rgba(31, 35, 40, 0.06);
      --module: #204e5f;
      --subground: #d08c34;
      --topic: #5b7f63;
      --lineage: #7c2d12;
      --case: #355c7d;
      --statute: #6b7280;
      --accent: #8f3b1b;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      background:
        radial-gradient(circle at top left, rgba(208, 140, 52, 0.18), transparent 26%),
        radial-gradient(circle at top right, rgba(32, 78, 95, 0.14), transparent 24%),
        linear-gradient(180deg, #faf5ec 0%, var(--bg) 42%, var(--bg-deep) 100%);
    }}

    .shell {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 380px;
      min-height: 100vh;
    }}

    .workspace {{
      padding: 28px;
      overflow-y: auto;
    }}

    .detail-panel {{
      border-left: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255, 252, 247, 0.95), rgba(244, 238, 228, 0.98));
      padding: 24px 22px 30px;
      overflow-y: auto;
    }}

    .meta {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      margin-bottom: 10px;
    }}

    h1, h2, h3 {{
      margin: 0;
      font-weight: 600;
    }}

    h1 {{
      font-size: clamp(34px, 4vw, 54px);
      line-height: 0.92;
      letter-spacing: -0.05em;
      margin-bottom: 12px;
    }}

    .intro {{
      max-width: 960px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.62;
      margin: 0 0 18px;
    }}

    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }}

    .nav {{
      display: inline-flex;
      gap: 8px;
      padding: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.58);
      box-shadow: var(--shadow-soft);
    }}

    .nav a {{
      padding: 10px 14px;
      border-radius: 999px;
      color: var(--ink);
      text-decoration: none;
      font-size: 13px;
      letter-spacing: 0.01em;
      border-bottom: 0;
    }}

    .nav a.active {{
      background: var(--ink);
      color: white;
    }}

    .search-box {{
      width: min(360px, 100%);
      display: grid;
      gap: 8px;
    }}

    .search-box input {{
      width: 100%;
      border: 1px solid rgba(31, 35, 40, 0.12);
      border-radius: 18px;
      padding: 13px 15px;
      background: rgba(255, 255, 255, 0.84);
      font: inherit;
      color: var(--ink);
    }}

    .graph-shell {{
      border: 1px solid var(--line);
      border-radius: 30px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(244, 238, 228, 0.82));
      box-shadow: var(--shadow);
      margin-bottom: 20px;
      overflow: hidden;
    }}

    .graph-toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
      padding: 16px 18px 0;
    }}

    .graph-copy {{
      display: grid;
      gap: 5px;
    }}

    .graph-copy strong {{
      font-size: 19px;
      letter-spacing: -0.02em;
    }}

    .graph-copy span {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}

    .graph-controls {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .graph-controls button {{
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.82);
      color: var(--ink);
      font: inherit;
      padding: 9px 13px;
      cursor: pointer;
      box-shadow: var(--shadow-soft);
    }}

    .graph-controls label {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.82);
      color: var(--muted);
      font-size: 12px;
      padding: 4px 8px 4px 12px;
      box-shadow: var(--shadow-soft);
    }}

    .graph-controls select {{
      border: 0;
      background: transparent;
      color: var(--ink);
      font: inherit;
      padding: 5px 8px;
      cursor: pointer;
    }}

    .graph-status {{
      padding: 0 18px 10px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }}

    .graph-board {{
      position: relative;
      padding: 0 10px 12px;
    }}

    .graph-wrap {{
      position: relative;
      min-height: 680px;
      border-top: 1px solid rgba(31, 35, 40, 0.08);
      background:
        radial-gradient(circle at top left, rgba(208, 140, 52, 0.09), transparent 24%),
        radial-gradient(circle at bottom right, rgba(32, 78, 95, 0.08), transparent 24%),
        linear-gradient(180deg, rgba(251, 248, 242, 0.96), rgba(240, 233, 222, 0.88));
      border-radius: 24px;
      overflow: hidden;
    }}

    .graph-canvas {{
      width: 100%;
      height: 680px;
      display: block;
      touch-action: none;
      cursor: grab;
    }}

    .graph-canvas.dragging {{
      cursor: grabbing;
    }}

    .graph-edge-link {{
      fill: none;
      stroke: rgba(31, 35, 40, 0.15);
      stroke-width: 2;
      stroke-linecap: round;
    }}

    .graph-edge-link.active {{
      stroke: rgba(143, 59, 27, 0.44);
      stroke-width: 2.6;
    }}

    .graph-node {{
      cursor: pointer;
    }}

    .graph-node-surface {{
      fill: rgba(255, 255, 255, 0.94);
      stroke: rgba(31, 35, 40, 0.16);
      stroke-width: 1.5;
      filter: drop-shadow(0 12px 22px rgba(31, 35, 40, 0.1));
      transition: stroke 140ms ease, stroke-width 140ms ease, transform 140ms ease;
    }}

    .graph-node.root .graph-node-surface {{
      fill: #182029;
      stroke: rgba(17, 22, 28, 0.78);
    }}

    .graph-node.module .graph-node-surface {{
      fill: rgba(32, 78, 95, 0.94);
      stroke: rgba(32, 78, 95, 0.95);
    }}

    .graph-node.subground .graph-node-surface {{
      fill: rgba(208, 140, 52, 0.15);
      stroke: rgba(208, 140, 52, 0.4);
    }}

    .graph-node.topic .graph-node-surface {{
      fill: rgba(91, 127, 99, 0.14);
      stroke: rgba(91, 127, 99, 0.34);
    }}

    .graph-node.authoritylineage .graph-node-surface {{
      fill: rgba(124, 45, 18, 0.14);
      stroke: rgba(124, 45, 18, 0.35);
    }}

    .graph-node.case .graph-node-surface {{
      fill: rgba(53, 92, 125, 0.14);
      stroke: rgba(53, 92, 125, 0.34);
    }}

    .graph-node.statute .graph-node-surface {{
      fill: rgba(107, 114, 128, 0.14);
      stroke: rgba(107, 114, 128, 0.34);
    }}

    .graph-node.sourcedocument .graph-node-surface,
    .graph-node.paragraph .graph-node-surface,
    .graph-node.proposition .graph-node-surface {{
      fill: rgba(255, 255, 255, 0.9);
      stroke: rgba(31, 35, 40, 0.18);
    }}

    .graph-node.active .graph-node-surface {{
      stroke: var(--accent);
      stroke-width: 3;
    }}

    .graph-node.related .graph-node-surface {{
      stroke: rgba(143, 59, 27, 0.42);
      stroke-width: 2.1;
    }}

    .graph-node-label {{
      fill: var(--ink);
      font-size: 13px;
      font-weight: 600;
      pointer-events: none;
    }}

    .graph-node-subtitle {{
      fill: var(--muted);
      font-size: 10px;
      pointer-events: none;
    }}

    .graph-node-meta {{
      fill: var(--muted);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      pointer-events: none;
    }}

    .graph-node.root .graph-node-label,
    .graph-node.root .graph-node-subtitle,
    .graph-node.root .graph-node-meta,
    .graph-node.module .graph-node-label,
    .graph-node.module .graph-node-subtitle,
    .graph-node.module .graph-node-meta {{
      fill: rgba(255, 255, 255, 0.92);
    }}

    .graph-toggle {{
      cursor: pointer;
    }}

    .graph-toggle circle {{
      fill: rgba(255, 255, 255, 0.96);
      stroke: rgba(31, 35, 40, 0.18);
      stroke-width: 1.2;
    }}

    .graph-toggle text {{
      fill: var(--ink);
      font-size: 14px;
      font-weight: 700;
      dominant-baseline: middle;
      text-anchor: middle;
      pointer-events: none;
    }}

    .metric-strip,
    .breadcrumbs,
    .results,
    .node-grid,
    .lineage-grid,
    .detail-chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .metric-strip {{
      margin-bottom: 18px;
    }}

    .metric-card,
    .crumb,
    .result-pill,
    .detail-chip {{
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 13px;
      color: var(--ink);
      box-shadow: var(--shadow-soft);
    }}

    .metric-card strong {{
      display: block;
      font-size: 18px;
      letter-spacing: -0.03em;
    }}

    .metric-card span {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}

    .crumb,
    .result-pill {{
      cursor: pointer;
      font: inherit;
    }}

    .stack-view {{
      display: grid;
      gap: 18px;
      padding-bottom: 24px;
    }}

    .tree-section {{
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 18px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(247, 243, 236, 0.74));
      box-shadow: var(--shadow);
    }}

    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}

    .section-title {{
      font-size: 20px;
      letter-spacing: -0.02em;
    }}

    .section-caption {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}

    .root-wrap {{
      display: flex;
      justify-content: center;
    }}

    .tree-node {{
      min-width: 220px;
      max-width: 320px;
      border: 1px solid rgba(31, 35, 40, 0.1);
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 243, 236, 0.9));
      box-shadow: var(--shadow-soft);
      padding: 15px;
      text-align: left;
      cursor: pointer;
      transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
      font: inherit;
      color: var(--ink);
    }}

    .tree-node.active {{
      border-color: rgba(31, 35, 40, 0.3);
      box-shadow: 0 24px 58px rgba(31, 35, 40, 0.14);
      transform: translateY(-1px);
    }}

    .tree-node.root {{
      min-width: 360px;
      background: linear-gradient(180deg, #1d242c, #11161c);
      color: white;
      border-color: rgba(17, 22, 28, 0.75);
    }}

    .tree-node.module {{
      background: linear-gradient(180deg, rgba(32, 78, 95, 0.95), rgba(38, 92, 112, 0.88));
      color: white;
    }}

    .tree-node.subground {{
      background: linear-gradient(180deg, rgba(208, 140, 52, 0.18), rgba(255, 248, 235, 0.95));
    }}

    .tree-node.topic {{
      background: linear-gradient(180deg, rgba(91, 127, 99, 0.16), rgba(249, 252, 249, 0.95));
    }}

    .tree-node.lineage {{
      background: linear-gradient(180deg, rgba(124, 45, 18, 0.14), rgba(255, 248, 244, 0.96));
    }}

    .tree-node.case {{
      background: linear-gradient(180deg, rgba(53, 92, 125, 0.15), rgba(247, 250, 252, 0.95));
    }}

    .tree-node.statute {{
      background: linear-gradient(180deg, rgba(107, 114, 128, 0.14), rgba(249, 249, 251, 0.96));
    }}

    .node-kicker {{
      display: inline-flex;
      margin-bottom: 10px;
      padding: 5px 9px;
      border-radius: 999px;
      font-size: 10px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.62);
      border: 1px solid rgba(31, 35, 40, 0.08);
    }}

    .tree-node.root .node-kicker,
    .tree-node.module .node-kicker {{
      color: rgba(255, 255, 255, 0.78);
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.16);
    }}

    .node-name {{
      display: block;
      font-size: 17px;
      line-height: 1.24;
      letter-spacing: -0.02em;
    }}

    .node-subtitle {{
      display: block;
      margin-top: 6px;
      font-size: 12px;
      line-height: 1.45;
      color: var(--muted);
    }}

    .tree-node.root .node-name {{
      font-size: 22px;
    }}

    .tree-node.root .node-subtitle,
    .tree-node.module .node-subtitle {{
      color: rgba(255, 255, 255, 0.78);
    }}

    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}

    .micro-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid rgba(31, 35, 40, 0.1);
      border-radius: 999px;
      padding: 6px 9px;
      font-size: 11px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.76);
    }}

    .tree-node.root .micro-chip,
    .tree-node.module .micro-chip {{
      color: rgba(255, 255, 255, 0.78);
      background: rgba(255, 255, 255, 0.08);
      border-color: rgba(255, 255, 255, 0.14);
    }}

    .lineage-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }}

    .lineage-panel,
    .aux-panel {{
      border: 1px solid rgba(31, 35, 40, 0.08);
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(247, 243, 236, 0.82));
      padding: 16px;
      box-shadow: var(--shadow-soft);
    }}

    .branch-head {{
      margin-bottom: 14px;
    }}

    .branch-head h3 {{
      font-size: 16px;
      line-height: 1.2;
      letter-spacing: -0.02em;
      margin-bottom: 6px;
    }}

    .branch-meta {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}

    .lineage-track {{
      position: relative;
      display: grid;
      gap: 14px;
      justify-items: center;
      padding: 4px 0;
    }}

    .lineage-track::before {{
      content: "";
      position: absolute;
      top: 10px;
      bottom: 10px;
      left: calc(50% - 1px);
      width: 2px;
      border-radius: 999px;
      background: linear-gradient(180deg, rgba(124, 45, 18, 0.1), rgba(124, 45, 18, 0.42), rgba(124, 45, 18, 0.1));
    }}

    .lineage-step {{
      width: 100%;
      display: flex;
      justify-content: center;
      position: relative;
      z-index: 1;
    }}

    .lineage-step .tree-node {{
      width: min(100%, 260px);
    }}

    .aux-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}

    .detail-type {{
      display: inline-flex;
      margin-bottom: 14px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.86);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}

    .detail-summary {{
      font-size: 15px;
      line-height: 1.64;
      margin: 0 0 16px;
    }}

    .data-list {{
      list-style: none;
      padding: 0;
      margin: 0 0 18px;
      display: grid;
      gap: 10px;
    }}

    .data-list li {{
      border: 1px solid rgba(31, 35, 40, 0.08);
      border-radius: 18px;
      padding: 12px 14px;
      background: rgba(255, 255, 255, 0.64);
      line-height: 1.5;
      font-size: 14px;
      box-shadow: var(--shadow-soft);
    }}

    .data-list li.clickable {{
      cursor: pointer;
    }}

    .graphrag-shell {{
      border-radius: 26px;
      padding: 10px 14px 14px;
    }}

    .chat-shell {{
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.78);
      overflow: hidden;
    }}

    .chat-shell summary {{
      cursor: pointer;
      list-style: none;
      font-size: 14px;
      letter-spacing: 0.01em;
      padding: 14px 16px;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.7);
      border-bottom: 1px solid rgba(31, 35, 40, 0.06);
    }}

    .chat-shell summary::-webkit-details-marker {{
      display: none;
    }}

    .chat-body {{
      padding: 14px 16px 16px;
      display: grid;
      gap: 12px;
    }}

    .chat-form {{
      display: grid;
      gap: 10px;
    }}

    .chat-form textarea {{
      width: 100%;
      min-height: 88px;
      max-height: 220px;
      resize: vertical;
      border-radius: 16px;
      border: 1px solid var(--line);
      padding: 12px;
      font: inherit;
      background: rgba(255, 255, 255, 0.9);
      color: var(--ink);
    }}

    .chat-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .chat-actions label {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.84);
    }}

    .chat-actions select,
    .chat-actions input {{
      border: 0;
      background: transparent;
      color: var(--ink);
      font: inherit;
      min-width: 84px;
    }}

    .chat-actions input {{
      min-width: 180px;
    }}

    .chat-actions button {{
      border: 0;
      border-radius: 999px;
      padding: 9px 14px;
      cursor: pointer;
      background: linear-gradient(180deg, rgba(32, 78, 95, 0.96), rgba(27, 62, 75, 0.96));
      color: white;
      font: inherit;
    }}

    .chat-history {{
      display: grid;
      gap: 10px;
    }}

    .chat-entry {{
      border: 1px solid rgba(31, 35, 40, 0.1);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.86);
      padding: 12px 13px;
      box-shadow: var(--shadow-soft);
    }}

    .chat-entry.user {{
      border-color: rgba(32, 78, 95, 0.24);
      background: rgba(232, 243, 247, 0.86);
    }}

    .chat-entry h4 {{
      margin: 0 0 8px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}

    .chat-answer {{
      margin: 0;
      line-height: 1.58;
      font-size: 14px;
      white-space: pre-wrap;
    }}

    .chat-citation-grid {{
      margin-top: 10px;
      display: grid;
      gap: 8px;
    }}

    .chat-citation {{
      border: 1px solid rgba(31, 35, 40, 0.1);
      border-radius: 12px;
      padding: 10px 11px;
      background: rgba(255, 255, 255, 0.74);
    }}

    .chat-citation strong {{
      display: block;
      font-size: 13px;
      margin-bottom: 5px;
    }}

    .chat-citation p {{
      margin: 0 0 7px;
      font-size: 13px;
      line-height: 1.55;
    }}

    .chat-citation button {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      background: rgba(255, 255, 255, 0.86);
      cursor: pointer;
      font: inherit;
      font-size: 12px;
      color: var(--ink);
    }}

    .chat-meta {{
      margin-top: 9px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.5;
    }}

    .empty {{
      color: var(--muted);
      font-style: italic;
    }}

    a {{
      color: var(--ink);
    }}

    @media (hover: hover) and (pointer: fine) {{
      .tree-node:hover {{
        border-color: rgba(31, 35, 40, 0.28);
        box-shadow: 0 18px 38px rgba(31, 35, 40, 0.1);
      }}
    }}

    @media (max-width: 1120px) {{
      .shell {{
        grid-template-columns: 1fr;
      }}

      .detail-panel {{
        border-left: 0;
        border-top: 1px solid var(--line);
      }}

      .graph-wrap {{
        min-height: 560px;
      }}

      .graph-canvas {{
        height: 560px;
      }}

      .chat-actions input {{
        min-width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="workspace">
      <div class="meta">{meta_label}</div>
      <h1>{heading}</h1>
      <p class="intro">{intro}</p>
      <div class="toolbar">
        <nav class="nav">
          <a href="/">Node Graph</a>
          <a href="/tree"{" class=\"active\"" if not is_internal else ""}>Hierarchy</a>
          <a href="/mvp">MVP GraphRAG</a>
          <a href="/internal"{" class=\"active\"" if is_internal else ""}>Internal Explorer</a>
        </nav>
        <label class="search-box">
          <span class="meta">Jump To Node</span>
          <input id="searchInput" type="search" placeholder="Module, topic, case, statute, lineage">
        </label>
      </div>
      <div id="metricStrip" class="metric-strip"></div>
      <div id="breadcrumbs" class="breadcrumbs"></div>
      <div id="results" class="results"></div>
      <section class="graph-shell">
        <div class="graph-toolbar">
          <div class="graph-copy">
            <strong>Visual Hierarchy Graph</strong>
            <span>{graph_copy}</span>
          </div>
          <div class="graph-controls">
            <label>
              <span>Case Rank</span>
              <select id="caseRankLimitSelect">
                <option value="5">Top 5</option>
                <option value="10" selected>Top 10</option>
                <option value="20">Top 20</option>
                <option value="40">Top 40</option>
              </select>
            </label>
            <button id="zoomOutButton" type="button">Zoom Out</button>
            <button id="zoomInButton" type="button">Zoom In</button>
            <button id="resetViewButton" type="button">Reset View</button>
            <button id="collapseGraphButton" type="button">Collapse Topics</button>
          </div>
        </div>
        <div id="graphStatus" class="graph-status">Loading hierarchy graph...</div>
        <div class="graph-board">
          <div class="graph-wrap">
            <svg id="hierarchyCanvas" class="graph-canvas" viewBox="0 0 1800 960" preserveAspectRatio="xMidYMid meet" aria-label="Hierarchical knowledge graph">
              <defs>
                <pattern id="graphGrid" width="32" height="32" patternUnits="userSpaceOnUse">
                  <path d="M 32 0 L 0 0 0 32" fill="none" stroke="rgba(31, 35, 40, 0.04)" stroke-width="1"></path>
                </pattern>
              </defs>
              <rect x="0" y="0" width="100%" height="100%" fill="url(#graphGrid)"></rect>
              <g id="graphViewport"></g>
            </svg>
          </div>
        </div>
      </section>
      <section class="graph-shell graphrag-shell">
        <details id="graphRagDetails" class="chat-shell" open>
          <summary>GraphRAG Inquiry Panel (Evidence-Linked)</summary>
          <div class="chat-body">
            <form id="graphRagForm" class="chat-form">
              <textarea id="graphRagInput" placeholder="Ask a legal question for grounded analysis (for example: When can terms be implied into a Hong Kong contract?)"></textarea>
              <div class="chat-actions">
                <label>Mode
                  <select id="graphRagMode">
                    <option value="extractive" selected>Extractive</option>
                    <option value="openrouter">OpenRouter</option>
                  </select>
                </label>
                <label>Top Cases
                  <select id="graphRagTopK">
                    <option value="3">3</option>
                    <option value="5" selected>5</option>
                    <option value="8">8</option>
                  </select>
                </label>
                <label>Citations
                  <select id="graphRagCitationLimit">
                    <option value="4">4</option>
                    <option value="6" selected>6</option>
                    <option value="10">10</option>
                  </select>
                </label>
                <label>Model
                  <input id="graphRagModel" type="text" placeholder="openrouter/auto">
                </label>
                <button id="graphRagSubmit" type="submit">Ask GraphRAG</button>
              </div>
            </form>
            <div id="graphRagStatus" class="small">This panel answers only from graph-linked evidence and returns direct case/paragraph citations.</div>
            <div id="graphRagHistory" class="chat-history"><div class="empty">No inquiries yet.</div></div>
          </div>
        </details>
      </section>
      <div id="treeStack" class="stack-view"></div>
    </section>
    <aside class="detail-panel">
      <div class="meta">Selection</div>
      <h2 id="detailTitle">Overview</h2>
      <div id="detailType" class="detail-type">Root</div>
      <p id="detailSummary" class="detail-summary">Choose a module, subground, topic, case, statute, or lineage to inspect how the hierarchy connects to the authority network.</p>
      <div id="detailChips" class="detail-chip-row"></div>
      <div class="meta">Key Facts</div>
      <ul id="detailFacts" class="data-list"><li class="empty">Select a node to inspect its metrics and graph context.</li></ul>
      <div class="meta">Related Authorities</div>
      <ul id="detailNeighbors" class="data-list"><li class="empty">No related authorities selected.</li></ul>
      <div class="meta">Principles / Lineage</div>
      <ul id="detailSupport" class="data-list"><li class="empty">No principle or lineage data selected.</li></ul>
    </aside>
  </div>
  <script>
    const payload = {data};
    const nodes = payload.nodes || [];
    const edges = payload.edges || [];
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const outgoing = new Map();
    const incoming = new Map();

    edges.forEach((edge) => {{
      if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
      if (!incoming.has(edge.target)) incoming.set(edge.target, []);
      outgoing.get(edge.source).push(edge);
      incoming.get(edge.target).push(edge);
    }});

    const tree = payload.tree || {{}};
    const modules = (tree.modules || []).map((module) => {{
      const moduleNode = nodeMap.get(module.id) || {{}};
      return {{
        ...module,
        ...moduleNode,
        type: "Module",
        subgrounds: (module.subgrounds || []).map((subground) => {{
          const subgroundNode = nodeMap.get(subground.id) || {{}};
          return {{
            ...subground,
            ...subgroundNode,
            type: "Subground",
            module_id: module.id,
          }};
        }}),
      }};
    }});

    const moduleMap = new Map(modules.map((module) => [module.id, module]));
    const subgrounds = modules.flatMap((module) => module.subgrounds);
    const subgroundMap = new Map(subgrounds.map((subground) => [subground.id, subground]));
    const topics = nodes.filter((node) => node.type === "Topic");
    const cases = nodes.filter((node) => node.type === "Case");
    const statutes = nodes.filter((node) => node.type === "Statute");
    const lineages = nodes.filter((node) => node.type === "AuthorityLineage");
    const caseCards = payload.case_cards || {{}};

    const rootNode = {{
      id: "__root__",
      type: "Root",
      label: tree.label_en || payload.meta.title || "Casemap Hybrid Hierarchy",
      summary: "Visual hierarchy for the hybrid graph. Modules anchor the doctrinal structure; topics connect that structure to cases, statutes, and authority lineages.",
      secondary: tree.label_zh || "香港合同法分層知識圖譜",
    }};

    const treeStack = document.getElementById("treeStack");
    const metricStrip = document.getElementById("metricStrip");
    const breadcrumbsEl = document.getElementById("breadcrumbs");
    const resultsEl = document.getElementById("results");
    const searchInput = document.getElementById("searchInput");
    const graphCanvas = document.getElementById("hierarchyCanvas");
    const graphViewport = document.getElementById("graphViewport");
    const graphStatus = document.getElementById("graphStatus");
    const zoomOutButton = document.getElementById("zoomOutButton");
    const zoomInButton = document.getElementById("zoomInButton");
    const resetViewButton = document.getElementById("resetViewButton");
    const collapseGraphButton = document.getElementById("collapseGraphButton");
    const caseRankLimitSelect = document.getElementById("caseRankLimitSelect");
    const detailTitle = document.getElementById("detailTitle");
    const detailType = document.getElementById("detailType");
    const detailSummary = document.getElementById("detailSummary");
    const detailFacts = document.getElementById("detailFacts");
    const detailNeighbors = document.getElementById("detailNeighbors");
    const detailSupport = document.getElementById("detailSupport");
    const detailChips = document.getElementById("detailChips");
    const graphRagForm = document.getElementById("graphRagForm");
    const graphRagInput = document.getElementById("graphRagInput");
    const graphRagMode = document.getElementById("graphRagMode");
    const graphRagTopK = document.getElementById("graphRagTopK");
    const graphRagCitationLimit = document.getElementById("graphRagCitationLimit");
    const graphRagModel = document.getElementById("graphRagModel");
    const graphRagStatus = document.getElementById("graphRagStatus");
    const graphRagHistory = document.getElementById("graphRagHistory");

    const state = {{
      moduleId: modules[0]?.id || null,
      subgroundId: modules[0]?.subgrounds?.[0]?.id || null,
      selectedId: "__root__",
      caseRankLimit: 10,
      expandedViewIds: new Set(),
      graph: {{
        scale: 1,
        translateX: 0,
        translateY: 0,
        width: 1800,
        height: 960,
        viewportWidth: 1800,
        viewportHeight: 960,
        worldWidth: 1800,
        worldHeight: 960,
        pendingCenterActualId: "",
      }},
    }};

    function escapeHtml(value) {{
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }}

    function labelForType(type) {{
      return {{
        Root: "Root",
        Module: "Module",
        Subground: "Subground",
        Topic: "Topic",
        Case: "Case",
        Statute: "Statute",
        AuthorityLineage: "Lineage",
        Paragraph: "Paragraph",
        Proposition: "Proposition",
      }}[type] || type;
    }}

    function labelForNode(node) {{
      return node?.label || node?.case_name || node?.title || node?.id || "";
    }}

    function shortText(value, max = 60) {{
      const clean = String(value || "").trim();
      return clean.length > max ? `${{clean.slice(0, max - 3)}}...` : clean;
    }}

    function graphSubtitleForNode(node) {{
      if (!node) return "";
      if (node.type === "Root") return node.secondary || "";
      if (node.type === "Module" || node.type === "Subground") return node.label_zh || node.summary || "";
      if (node.type === "Topic") return node.path || node.summary || "";
      if (node.type === "Case") return node.neutral_citation || `Authority ${{(node.authority_score || 0).toFixed(2)}}`;
      if (node.type === "AuthorityLineage") return (node.codes || []).join(" · ");
      if (node.type === "Statute") return node.summary_en || node.label || "";
      return node.summary_en || node.summary || "";
    }}

    function multiLineText(value, maxLineLength = 24, maxLines = 3) {{
      const words = String(value || "").trim().split(/\\s+/).filter(Boolean);
      if (!words.length) return [""];
      const lines = [];
      let current = "";
      words.forEach((word) => {{
        const candidate = current ? `${{current}} ${{word}}` : word;
        if (candidate.length > maxLineLength && current) {{
          lines.push(current);
          current = word;
        }} else {{
          current = candidate;
        }}
      }});
      if (current) lines.push(current);
      if (lines.length <= maxLines) return lines;
      const trimmed = lines.slice(0, maxLines);
      trimmed[maxLines - 1] = shortText(trimmed[maxLines - 1], maxLineLength);
      return trimmed;
    }}

    function getNode(id) {{
      if (!id) return null;
      if (id === rootNode.id) return rootNode;
      return moduleMap.get(id) || subgroundMap.get(id) || nodeMap.get(id) || null;
    }}

    function makeSection(title, caption) {{
      const section = document.createElement("section");
      section.className = "tree-section";
      section.innerHTML = `<div class="section-head"><div class="section-title">${{escapeHtml(title)}}</div><div class="section-caption">${{escapeHtml(caption)}}</div></div>`;
      return section;
    }}

    function microChip(label) {{
      return `<span class="micro-chip">${{escapeHtml(label)}}</span>`;
    }}

    function createNodeCard(node, options = {{}}) {{
      const button = document.createElement("button");
      button.type = "button";
      const typeClass = (node.type || "").toLowerCase();
      button.className = `tree-node ${{typeClass}}${{state.selectedId === node.id ? " active" : ""}}`;
      const subtitle = options.subtitle || node.label_zh || node.secondary || node.neutral_citation || "";
      const chips = [];
      if (options.metrics) chips.push(...options.metrics.map(microChip));
      if (options.path) chips.push(microChip(options.path));
      button.innerHTML = `
        <span class="node-kicker">${{escapeHtml(options.kicker || labelForType(node.type || ""))}}</span>
        <strong class="node-name">${{escapeHtml(node.label || node.case_name || node.title || node.id)}}</strong>
        ${{subtitle ? `<span class="node-subtitle">${{escapeHtml(subtitle)}}</span>` : ""}}
        ${{chips.length ? `<div class="chip-row">${{chips.join("")}}</div>` : ""}}
      `;
      button.addEventListener("click", () => selectNode(node.id));
      return button;
    }}

    function topicIdsForNode(node) {{
      if (!node) return [];
      if (node.type === "Topic") return [node.id];
      if (node.type === "Subground") return node.topic_ids || [];
      if (node.type === "Module") return (node.subgrounds || []).flatMap((subground) => subground.topic_ids || []);
      if (node.type === "AuthorityLineage") {{
        return (outgoing.get(node.id) || []).filter((edge) => edge.type === "ABOUT_TOPIC").map((edge) => edge.target);
      }}
      if (node.type === "Case" || node.type === "Statute") {{
        return (outgoing.get(node.id) || []).filter((edge) => edge.type === "BELONGS_TO_TOPIC").map((edge) => edge.target);
      }}
      if (node.type === "Paragraph") {{
        const caseEdge = (outgoing.get(node.id) || []).find((edge) => edge.type === "PART_OF");
        return caseEdge ? topicIdsForNode(nodeMap.get(caseEdge.target)) : [];
      }}
      if (node.type === "Proposition") {{
        const paragraphEdge = (incoming.get(node.id) || []).find((edge) => edge.type === "SUPPORTS");
        return paragraphEdge ? topicIdsForNode(nodeMap.get(paragraphEdge.source)) : [];
      }}
      return [];
    }}

    function inferContext(node) {{
      if (!node) return {{ moduleId: state.moduleId, subgroundId: state.subgroundId }};
      if (node.type === "Module") {{
        return {{ moduleId: node.id, subgroundId: node.subgrounds?.[0]?.id || null }};
      }}
      if (node.type === "Subground") {{
        return {{ moduleId: node.module_id, subgroundId: node.id }};
      }}
      if (node.type === "Topic") {{
        return {{ moduleId: node.module_id, subgroundId: node.subground_id }};
      }}
      const topicId = topicIdsForNode(node)[0];
      const topic = topicId ? nodeMap.get(topicId) : null;
      if (topic) {{
        return {{ moduleId: topic.module_id, subgroundId: topic.subground_id }};
      }}
      return {{ moduleId: state.moduleId, subgroundId: state.subgroundId }};
    }}

    function selectNode(id) {{
      const node = getNode(id);
      const context = inferContext(node);
      state.moduleId = context.moduleId;
      state.subgroundId = context.subgroundId;
      state.selectedId = id;
      expandGraphPathForNode(node);
      state.graph.pendingCenterActualId = id;
      render();
    }}

    function neighborsByType(id, types) {{
      const wanted = new Set(Array.isArray(types) ? types : [types]);
      const neighbors = [];
      (outgoing.get(id) || []).forEach((edge) => {{
        const target = nodeMap.get(edge.target);
        if (target && wanted.has(target.type)) neighbors.push(target);
      }});
      (incoming.get(id) || []).forEach((edge) => {{
        const source = nodeMap.get(edge.source);
        if (source && wanted.has(source.type)) neighbors.push(source);
      }});
      return neighbors.filter((node, index, list) => list.findIndex((candidate) => candidate.id === node.id) === index);
    }}

    function relatedCasesForTopic(topicId) {{
      return (incoming.get(topicId) || [])
        .filter((edge) => edge.type === "BELONGS_TO_TOPIC")
        .map((edge) => nodeMap.get(edge.source))
        .filter((node) => node && node.type === "Case")
        .sort((left, right) => (right.authority_score || 0) - (left.authority_score || 0) || (left.label || "").localeCompare(right.label || ""));
    }}

    function relatedStatutesForTopic(topicId) {{
      return (incoming.get(topicId) || [])
        .filter((edge) => edge.type === "BELONGS_TO_TOPIC")
        .map((edge) => nodeMap.get(edge.source))
        .filter((node) => node && node.type === "Statute")
        .sort((left, right) => (left.label || "").localeCompare(right.label || ""));
    }}

    function relatedLineagesForTopic(topicId) {{
      return (incoming.get(topicId) || [])
        .filter((edge) => edge.type === "ABOUT_TOPIC")
        .map((edge) => nodeMap.get(edge.source))
        .filter(Boolean)
        .sort((left, right) => (left.label || "").localeCompare(right.label || ""));
    }}

    function relatedSourcesForTopic(topicId) {{
      return (incoming.get(topicId) || [])
        .filter((edge) => edge.type === "MENTIONS")
        .map((edge) => nodeMap.get(edge.source))
        .filter(Boolean);
    }}

    function renderMetricStrip() {{
      const metrics = [
        ["Modules", modules.length],
        ["Topics", payload.meta.topic_count || topics.length],
        ["Cases", payload.meta.case_count || cases.length],
        ["Statutes", payload.meta.statute_count || statutes.length],
        ["Lineages", payload.meta.lineage_count || lineages.length],
      ];
      metricStrip.innerHTML = metrics.map(([label, value]) => `<div class="metric-card"><strong>${{value}}</strong><span>${{escapeHtml(label)}}</span></div>`).join("");
    }}

    function renderBreadcrumbs() {{
      breadcrumbsEl.innerHTML = "";
      const trail = [rootNode];
      const module = state.moduleId ? getNode(state.moduleId) : null;
      const subground = state.subgroundId ? getNode(state.subgroundId) : null;
      const selected = getNode(state.selectedId);
      if (module) trail.push(module);
      if (subground && subground.id !== module?.id) trail.push(subground);
      if (selected && !trail.some((item) => item.id === selected.id)) trail.push(selected);

      trail.forEach((node) => {{
        const button = document.createElement("button");
        button.type = "button";
        button.className = "crumb";
        button.textContent = node.label || node.case_name || node.title || node.id;
        button.addEventListener("click", () => selectNode(node.id));
        breadcrumbsEl.appendChild(button);
      }});
    }}

    function renderResults(query) {{
      const lowered = query.trim().toLowerCase();
      resultsEl.innerHTML = "";
      if (!lowered) return;
      const searchables = [
        ...modules,
        ...subgrounds,
        ...topics,
        ...cases,
        ...statutes,
        ...lineages,
      ];
      const matches = searchables
        .filter((node) => `${{node.label || ""}} ${{node.case_name || ""}} ${{node.summary || ""}}`.toLowerCase().includes(lowered))
        .sort((left, right) => (right.degree || 0) - (left.degree || 0) || (left.label || "").localeCompare(right.label || ""))
        .slice(0, 12);

      if (!matches.length) {{
        resultsEl.innerHTML = "<div class='empty'>No matching nodes.</div>";
        return;
      }}

      matches.forEach((node) => {{
        const button = document.createElement("button");
        button.type = "button";
        button.className = "result-pill";
        button.textContent = `${{node.label || node.case_name}} · ${{labelForType(node.type)}}`;
        button.addEventListener("click", () => selectNode(node.id));
        resultsEl.appendChild(button);
      }});
    }}

    function clearGraphRagEmptyState() {{
      const emptyState = graphRagHistory.querySelector(".empty");
      if (emptyState) emptyState.remove();
    }}

    function appendGraphRagEntry(role, html) {{
      clearGraphRagEmptyState();
      const card = document.createElement("article");
      card.className = `chat-entry ${{role}}`;
      card.innerHTML = html;
      graphRagHistory.prepend(card);
      card.querySelectorAll("[data-focus-node-id]").forEach((button) => {{
        button.addEventListener("click", () => {{
          selectNode(button.dataset.focusNodeId);
        }});
      }});
    }}

    function renderGraphRagCitationGrid(citations) {{
      if (!citations.length) {{
        return "<div class='empty'>No direct citations were returned.</div>";
      }}
      return `
        <div class="chat-citation-grid">
          ${{
            citations.map((citation) => `
              <div class="chat-citation">
                <strong>[${{escapeHtml(citation.citation_id || "")}}] ${{escapeHtml(citation.case_name || "Unknown Case")}}</strong>
                <p>${{escapeHtml(citation.quote || "")}}</p>
                <div class="chat-meta">${{escapeHtml((citation.neutral_citation || "") + (citation.paragraph_span ? " · " + citation.paragraph_span : ""))}}</div>
                ${{
                  citation.focus_node_id || citation.case_id
                    ? `<button type="button" data-focus-node-id="${{escapeHtml(citation.focus_node_id || citation.case_id)}}">Focus Node</button>`
                    : ""
                }}
              </div>
            `).join("")
          }}
        </div>
      `;
    }}

    function graphRagTraceLine(payload) {{
      const mode = payload.answer_mode || "extractive";
      const citationCount = (payload.citations || []).length;
      const supportingCount = (payload.supporting_nodes || []).length;
      return `Mode: ${{mode}} · citations: ${{citationCount}} · supporting nodes: ${{supportingCount}}`;
    }}

    function renderAuthorityLineage(lineage) {{
      const panel = document.createElement("article");
      panel.className = "lineage-panel";
      panel.innerHTML = `<div class="branch-head"><h3>${{escapeHtml(lineage.title || lineage.label)}}</h3><div class="branch-meta">${{escapeHtml((lineage.codes || []).join(" · ") || "authority lineage")}}</div></div>`;
      const track = document.createElement("div");
      track.className = "lineage-track";
      const members = (outgoing.get(lineage.id) || [])
        .filter((edge) => edge.type === "HAS_MEMBER")
        .sort((left, right) => (left.position || 0) - (right.position || 0));
      members.forEach((edge) => {{
        const node = nodeMap.get(edge.target);
        if (!node) return;
        const step = document.createElement("div");
        step.className = "lineage-step";
        step.appendChild(createNodeCard(node, {{
          kicker: edge.code || labelForType(node.type),
          subtitle: edge.note || node.neutral_citation || node.summary_en || "",
          metrics: node.type === "Case"
            ? [`Authority ${{(node.authority_score || 0).toFixed(2)}}`]
            : [],
        }}));
        track.appendChild(step);
      }});
      panel.appendChild(track);
      return panel;
    }}

    function renderAuxPanel(title, caption, items, builder) {{
      if (!items.length) return null;
      const panel = document.createElement("article");
      panel.className = "aux-panel";
      panel.innerHTML = `<div class="branch-head"><h3>${{escapeHtml(title)}}</h3><div class="branch-meta">${{escapeHtml(caption)}}</div></div>`;
      const grid = document.createElement("div");
      grid.className = "aux-grid";
      items.forEach((item) => grid.appendChild(builder(item)));
      panel.appendChild(grid);
      return panel;
    }}

    function currentModule() {{
      return state.moduleId ? getNode(state.moduleId) : null;
    }}

    function currentSubground() {{
      return state.subgroundId ? getNode(state.subgroundId) : null;
    }}

    function createDefaultExpandedIds() {{
      const expanded = new Set([rootNode.id]);
      modules.forEach((module) => expanded.add(module.id));
      subgrounds.forEach((subground) => expanded.add(subground.id));
      return expanded;
    }}

    function memberNodesForLineage(lineageId) {{
      return (outgoing.get(lineageId) || [])
        .filter((edge) => edge.type === "HAS_MEMBER")
        .sort((left, right) => (left.position || 0) - (right.position || 0))
        .map((edge) => ({{
          edge,
          node: nodeMap.get(edge.target),
        }}))
        .filter((entry) => entry.node);
    }}

    function graphChildrenForNode(node, viewId) {{
      if (!node) return [];
      if (node.type === "Root") {{
        return modules.map((module) => ({{
          viewId: module.id,
          actualId: module.id,
          parentViewId: viewId,
          node: module,
        }}));
      }}
      if (node.type === "Module") {{
        return (node.subgrounds || []).map((subground) => ({{
          viewId: subground.id,
          actualId: subground.id,
          parentViewId: viewId,
          node: subground,
        }}));
      }}
      if (node.type === "Subground") {{
        return (node.topic_ids || [])
          .map((topicId) => nodeMap.get(topicId))
          .filter(Boolean)
          .sort((left, right) => labelForNode(left).localeCompare(labelForNode(right)))
          .map((topic) => ({{
            viewId: topic.id,
            actualId: topic.id,
            parentViewId: viewId,
            node: topic,
          }}));
      }}
      if (node.type === "Topic") {{
        const topicLineages = relatedLineagesForTopic(node.id).map((lineage) => ({{
          viewId: `${{node.id}}::lineage::${{lineage.id}}`,
          actualId: lineage.id,
          parentViewId: viewId,
          node: lineage,
          relationLabel: "Lineage",
        }}));
        const topicCases = relatedCasesForTopic(node.id).slice(0, state.caseRankLimit).map((caseNode) => ({{
          viewId: `${{node.id}}::case::${{caseNode.id}}`,
          actualId: caseNode.id,
          parentViewId: viewId,
          node: caseNode,
          relationLabel: "Case",
        }}));
        const topicStatutes = relatedStatutesForTopic(node.id).map((statuteNode) => ({{
          viewId: `${{node.id}}::statute::${{statuteNode.id}}`,
          actualId: statuteNode.id,
          parentViewId: viewId,
          node: statuteNode,
          relationLabel: "Statute",
        }}));
        return [...topicLineages, ...topicCases, ...topicStatutes];
      }}
      if (node.type === "AuthorityLineage") {{
        return memberNodesForLineage(node.id).map((entry, index) => ({{
          viewId: `${{viewId}}::member::${{index}}::${{entry.node.id}}`,
          actualId: entry.node.id,
          parentViewId: viewId,
          node: entry.node,
          relationLabel: entry.edge.code || entry.edge.treatment || entry.edge.note || "Member",
        }}));
      }}
      return [];
    }}

    function buildGraphBranch(viewId, actualId, parentViewId = "", relationLabel = "") {{
      const node = actualId === rootNode.id ? rootNode : getNode(actualId);
      if (!node) return null;
      const childrenSeed = graphChildrenForNode(node, viewId);
      const isExpanded = state.expandedViewIds.has(viewId);
      const children = isExpanded
        ? childrenSeed.map((child) => buildGraphBranch(child.viewId, child.actualId, viewId, child.relationLabel || "")).filter(Boolean)
        : [];
      return {{
        viewId,
        actualId,
        parentViewId,
        relationLabel,
        node,
        childCount: childrenSeed.length,
        children,
      }};
    }}

    function layoutGraphTree(root) {{
      const positions = new Map();
      let nextY = 120;
      let maxDepth = 0;
      const columnGap = 270;
      const rowGap = 88;

      function sizeForType(type) {{
        if (type === "Root") return {{ width: 260, height: 92 }};
        if (type === "Module") return {{ width: 230, height: 86 }};
        if (type === "Subground") return {{ width: 214, height: 80 }};
        if (type === "Topic") return {{ width: 220, height: 80 }};
        if (type === "AuthorityLineage") return {{ width: 214, height: 80 }};
        if (type === "Case") return {{ width: 208, height: 78 }};
        if (type === "Statute") return {{ width: 202, height: 76 }};
        return {{ width: 198, height: 72 }};
      }}

      function visit(branch, depth) {{
        maxDepth = Math.max(maxDepth, depth);
        const size = sizeForType(branch.node.type);
        const x = 150 + depth * columnGap;
        if (!branch.children.length) {{
          const y = nextY;
          nextY += rowGap;
          positions.set(branch.viewId, {{ x, y, ...size }});
          return {{ top: y, bottom: y, center: y }};
        }}

        const childBounds = branch.children.map((child) => visit(child, depth + 1));
        const first = childBounds[0];
        const last = childBounds[childBounds.length - 1];
        const y = (first.center + last.center) / 2;
        positions.set(branch.viewId, {{ x, y, ...size }});
        return {{ top: first.top, bottom: last.bottom, center: y }};
      }}

      visit(root, 0);
      return {{
        positions,
        width: Math.max(1800, 360 + (maxDepth + 1) * columnGap),
        height: Math.max(960, nextY + 120),
      }};
    }}

    function flattenGraph(root) {{
      const visibleNodes = [];
      const visibleEdges = [];
      function walk(branch) {{
        visibleNodes.push(branch);
        branch.children.forEach((child) => {{
          visibleEdges.push({{ source: branch, target: child }});
          walk(child);
        }});
      }}
      walk(root);
      return {{ visibleNodes, visibleEdges }};
    }}

    function graphEdgePath(source, target) {{
      const startX = source.x + source.width / 2;
      const endX = target.x - target.width / 2;
      const delta = Math.max(72, (endX - startX) * 0.45);
      return `M ${{startX}} ${{source.y}} C ${{startX + delta}} ${{source.y}}, ${{endX - delta}} ${{target.y}}, ${{endX}} ${{target.y}}`;
    }}

    function isGraphNodeRelated(actualId) {{
      if (!state.selectedId || state.selectedId === rootNode.id || actualId === state.selectedId) return false;
      return (outgoing.get(state.selectedId) || []).some((edge) => edge.target === actualId)
        || (incoming.get(state.selectedId) || []).some((edge) => edge.source === actualId)
        || topicIdsForNode(getNode(state.selectedId)).includes(actualId)
        || topicIdsForNode(getNode(actualId)).includes(state.selectedId);
    }}

    function toggleGraphNodeExpansion(viewId) {{
      if (state.expandedViewIds.has(viewId)) {{
        state.expandedViewIds.delete(viewId);
      }} else {{
        state.expandedViewIds.add(viewId);
      }}
      render();
    }}

    function expandGraphPathForNode(node) {{
      state.expandedViewIds.add(rootNode.id);
      if (!node) return;
      const context = inferContext(node);
      if (context.moduleId) state.expandedViewIds.add(context.moduleId);
      if (context.subgroundId) state.expandedViewIds.add(context.subgroundId);
      const topicIds = topicIdsForNode(node);
      if (node.type === "Topic") topicIds.unshift(node.id);
      topicIds.filter((topicId, index, list) => list.indexOf(topicId) === index).forEach((topicId) => {{
        state.expandedViewIds.add(topicId);
        if (node.type === "AuthorityLineage") {{
          state.expandedViewIds.add(`${{topicId}}::lineage::${{node.id}}`);
        }}
      }});
    }}

    function applyGraphTransform() {{
      graphViewport.setAttribute("transform", `translate(${{state.graph.translateX}} ${{state.graph.translateY}}) scale(${{state.graph.scale}})`);
      const zoomPercent = Math.round(state.graph.scale * 100);
      graphStatus.textContent = `${{zoomPercent}}% zoom. Topic branches currently show the top ${{state.caseRankLimit}} ranked cases. Click a node to inspect it, use the small +/- control to expand or collapse branches, and drag the canvas to pan.`;
    }}

    function zoomGraph(multiplier) {{
      const nextScale = Math.max(0.55, Math.min(2.4, state.graph.scale * multiplier));
      state.graph.scale = Number(nextScale.toFixed(3));
      applyGraphTransform();
    }}

    function resetGraphView() {{
      state.graph.scale = 1;
      state.graph.translateX = 0;
      state.graph.translateY = 0;
      applyGraphTransform();
    }}

    function centerGraphOnActualId(actualId, positions, branches) {{
      const match = branches.find((branch) => branch.actualId === actualId);
      if (!match) return;
      const position = positions.get(match.viewId);
      if (!position) return;
      const targetX = state.graph.width * 0.34 - position.x * state.graph.scale;
      const targetY = state.graph.height * 0.5 - position.y * state.graph.scale;
      state.graph.translateX = Number(targetX.toFixed(2));
      state.graph.translateY = Number(targetY.toFixed(2));
      applyGraphTransform();
    }}

    function renderGraph() {{
      const graphRoot = buildGraphBranch(rootNode.id, rootNode.id);
      if (!graphRoot) return;
      const layout = layoutGraphTree(graphRoot);
      const flattened = flattenGraph(graphRoot);
      state.graph.width = state.graph.viewportWidth;
      state.graph.height = state.graph.viewportHeight;
      state.graph.worldWidth = layout.width;
      state.graph.worldHeight = layout.height;
      graphCanvas.setAttribute("viewBox", `0 0 ${{state.graph.viewportWidth}} ${{state.graph.viewportHeight}}`);

      const edgeMarkup = flattened.visibleEdges.map((edge) => {{
        const source = layout.positions.get(edge.source.viewId);
        const target = layout.positions.get(edge.target.viewId);
        if (!source || !target) return "";
        const active = edge.source.actualId === state.selectedId || edge.target.actualId === state.selectedId ? " active" : "";
        return `<path class="graph-edge-link${{active}}" d="${{graphEdgePath(source, target)}}"></path>`;
      }}).join("");

      const nodeMarkup = flattened.visibleNodes.map((branch) => {{
        const pos = layout.positions.get(branch.viewId);
        if (!pos) return "";
        const node = branch.node;
        const typeClass = (node.type || "").toLowerCase();
        const active = branch.actualId === state.selectedId ? " active" : "";
        const related = isGraphNodeRelated(branch.actualId) ? " related" : "";
        const titleLines = multiLineText(labelForNode(node), node.type === "Root" ? 26 : 22, node.type === "Case" ? 3 : 2);
        const subtitle = shortText(branch.relationLabel || graphSubtitleForNode(node), 34);
        const yStart = pos.y - (titleLines.length > 1 ? 12 : 4);
        const titleMarkup = titleLines.map((line, index) =>
          `<tspan x="${{pos.x}}" y="${{yStart + index * 15}}">${{escapeHtml(line)}}</tspan>`
        ).join("");
        const nodeMeta = branch.childCount ? `${{branch.childCount}} child${{branch.childCount === 1 ? "" : "ren"}}` : labelForType(node.type);
        const toggleMarkup = branch.childCount
          ? `
            <g class="graph-toggle" data-toggle-view-id="${{escapeHtml(branch.viewId)}}">
              <circle cx="${{pos.x + pos.width / 2 - 14}}" cy="${{pos.y - pos.height / 2 + 14}}" r="12"></circle>
              <text x="${{pos.x + pos.width / 2 - 14}}" y="${{pos.y - pos.height / 2 + 14}}">${{state.expandedViewIds.has(branch.viewId) ? "-" : "+"}}</text>
            </g>
          `
          : "";
        return `
          <g class="graph-node ${{typeClass}}${{active}}${{related}}" data-view-id="${{escapeHtml(branch.viewId)}}" data-actual-id="${{escapeHtml(branch.actualId)}}">
            <rect class="graph-node-surface" x="${{pos.x - pos.width / 2}}" y="${{pos.y - pos.height / 2}}" rx="24" ry="24" width="${{pos.width}}" height="${{pos.height}}"></rect>
            <text class="graph-node-meta" x="${{pos.x}}" y="${{pos.y - pos.height / 2 + 18}}" text-anchor="middle">${{escapeHtml(nodeMeta)}}</text>
            <text class="graph-node-label" x="${{pos.x}}" y="${{yStart}}" text-anchor="middle">${{titleMarkup}}</text>
            ${{subtitle ? `<text class="graph-node-subtitle" x="${{pos.x}}" y="${{pos.y + pos.height / 2 - 16}}" text-anchor="middle">${{escapeHtml(subtitle)}}</text>` : ""}}
            ${{toggleMarkup}}
          </g>
        `;
      }}).join("");

      graphViewport.innerHTML = edgeMarkup + nodeMarkup;
      graphViewport.querySelectorAll("[data-actual-id]").forEach((element) => {{
        element.addEventListener("click", (event) => {{
          if (event.target.closest("[data-toggle-view-id]")) return;
          selectNode(element.dataset.actualId);
        }});
      }});
      graphViewport.querySelectorAll("[data-toggle-view-id]").forEach((element) => {{
        element.addEventListener("click", (event) => {{
          event.stopPropagation();
          toggleGraphNodeExpansion(element.dataset.toggleViewId);
        }});
      }});

      applyGraphTransform();
      if (state.graph.pendingCenterActualId) {{
        centerGraphOnActualId(state.graph.pendingCenterActualId, layout.positions, flattened.visibleNodes);
        state.graph.pendingCenterActualId = "";
      }}
    }}

    function renderTree() {{
      treeStack.innerHTML = "";

      const rootSection = makeSection("Overview", "hybrid hierarchy");
      const rootWrap = document.createElement("div");
      rootWrap.className = "root-wrap";
      rootWrap.appendChild(createNodeCard(rootNode, {{
        kicker: "Root",
        subtitle: rootNode.secondary,
        metrics: [`${{modules.length}} modules`, `${{topics.length}} topics`, `${{cases.length}} cases`],
      }}));
      rootSection.appendChild(rootWrap);
      treeStack.appendChild(rootSection);

      const moduleSection = makeSection("Lifecycle Modules", "module layer");
      const moduleRow = document.createElement("div");
      moduleRow.className = "node-grid";
      modules.forEach((module) => {{
        moduleRow.appendChild(createNodeCard(module, {{
          kicker: "Module",
          subtitle: module.label_zh || module.summary || "",
          metrics: [
            `${{module.metrics?.subgrounds || module.subgrounds.length}} subgrounds`,
            `${{module.metrics?.cases || 0}} cases`,
            `${{module.metrics?.lineages || 0}} lineages`,
          ],
        }}));
      }});
      moduleSection.appendChild(moduleRow);
      treeStack.appendChild(moduleSection);

      const module = currentModule();
      if (!module) return;

      const subgroundSection = makeSection(module.label, "subground layer");
      const subgroundGrid = document.createElement("div");
      subgroundGrid.className = "node-grid";
      (module.subgrounds || []).forEach((subground) => {{
        subgroundGrid.appendChild(createNodeCard(subground, {{
          kicker: "Subground",
          subtitle: subground.label_zh || subground.summary || "",
          metrics: [
            `${{subground.metrics?.topics || (subground.topic_ids || []).length}} topics`,
            `${{subground.metrics?.cases || 0}} cases`,
            `${{subground.metrics?.lineages || 0}} lineages`,
          ],
        }}));
      }});
      subgroundSection.appendChild(subgroundGrid);
      treeStack.appendChild(subgroundSection);

      const subground = currentSubground();
      if (!subground) return;

      const subgroundTopics = (subground.topic_ids || [])
        .map((topicId) => nodeMap.get(topicId))
        .filter(Boolean)
        .sort((left, right) => (left.label || "").localeCompare(right.label || ""));

      const topicSection = makeSection(subground.label, "topic layer");
      const topicGrid = document.createElement("div");
      topicGrid.className = "node-grid";
      subgroundTopics.forEach((topic) => {{
        topicGrid.appendChild(createNodeCard(topic, {{
          kicker: "Topic",
          subtitle: topic.summary || "",
          metrics: [
            `${{relatedCasesForTopic(topic.id).length}} cases`,
            `${{relatedStatutesForTopic(topic.id).length}} statutes`,
            `${{relatedLineagesForTopic(topic.id).length}} lineages`,
          ],
          path: topic.path || "",
        }}));
      }});
      topicSection.appendChild(topicGrid);
      treeStack.appendChild(topicSection);

      const selected = getNode(state.selectedId);
      const focusTopicIds = selected?.type === "Topic"
        ? [selected.id]
        : topicIdsForNode(selected).filter((topicId, index, list) => list.indexOf(topicId) === index);
      const focusTopics = focusTopicIds.length ? focusTopicIds.map((topicId) => nodeMap.get(topicId)).filter(Boolean) : subgroundTopics.slice(0, 1);
      if (!focusTopics.length) return;

      const authoritySection = makeSection("Authority Branches", "graph-native authorities under the chosen hierarchy branch");
      const authorityGrid = document.createElement("div");
      authorityGrid.className = "lineage-grid";

      focusTopics.slice(0, 2).forEach((topic) => {{
        const lineagesForTopic = relatedLineagesForTopic(topic.id);
        const topicCases = relatedCasesForTopic(topic.id).slice(0, 10);
        const topicStatutes = relatedStatutesForTopic(topic.id).slice(0, 8);
        const topicSources = relatedSourcesForTopic(topic.id).slice(0, 6);

        const topicPanel = document.createElement("article");
        topicPanel.className = "aux-panel";
        topicPanel.innerHTML = `<div class="branch-head"><h3>${{escapeHtml(topic.label)}}</h3><div class="branch-meta">${{escapeHtml(topic.path || "topic branch")}}</div></div>`;
        const grid = document.createElement("div");
        grid.className = "aux-grid";
        topicCases.slice(0, 4).forEach((caseNode) => {{
          grid.appendChild(createNodeCard(caseNode, {{
            kicker: "Case",
            subtitle: caseNode.neutral_citation || caseNode.summary_en || "",
            metrics: [`Authority ${{(caseNode.authority_score || 0).toFixed(2)}}`],
          }}));
        }});
        if (!topicCases.length) {{
          grid.innerHTML = "<div class='empty'>No cases mapped to this topic.</div>";
        }}
        topicPanel.appendChild(grid);
        authorityGrid.appendChild(topicPanel);

        lineagesForTopic.forEach((lineage) => authorityGrid.appendChild(renderAuthorityLineage(lineage)));

        const statutesPanel = renderAuxPanel("Statutes", "statutory authorities", topicStatutes, (statuteNode) =>
          createNodeCard(statuteNode, {{
            kicker: "Statute",
            subtitle: statuteNode.summary_en || statuteNode.label,
          }})
        );
        if (statutesPanel) authorityGrid.appendChild(statutesPanel);

        const sourcesPanel = renderAuxPanel("Sources", "source documents mentioning this topic", topicSources, (sourceNode) =>
          createNodeCard(sourceNode, {{
            kicker: "Source",
            subtitle: sourceNode.kind || sourceNode.path || "",
          }})
        );
        if (sourcesPanel) authorityGrid.appendChild(sourcesPanel);
      }});

      authoritySection.appendChild(authorityGrid);
      treeStack.appendChild(authoritySection);
    }}

    function renderList(target, items, emptyText, clickable = false) {{
      target.innerHTML = "";
      if (!items.length) {{
        target.innerHTML = `<li class="empty">${{escapeHtml(emptyText)}}</li>`;
        return;
      }}
      items.forEach((item) => {{
        const li = document.createElement("li");
        if (clickable && item.id) li.className = "clickable";
        li.innerHTML = item.html;
        if (clickable && item.id) li.addEventListener("click", () => selectNode(item.id));
        target.appendChild(li);
      }});
    }}

    function renderDetails(node) {{
      const selected = node || rootNode;
      detailTitle.textContent = selected.label || selected.case_name || selected.title || selected.id;
      detailType.textContent = labelForType(selected.type);
      detailSummary.textContent = selected.summary || selected.summary_en || rootNode.summary;
      detailChips.innerHTML = "";

      const facts = [];
      const neighbors = [];
      const support = [];

      if (selected.type === "Root") {{
        detailChips.innerHTML = [
          `<span class="detail-chip">${{modules.length}} modules</span>`,
          `<span class="detail-chip">${{topics.length}} topics</span>`,
          `<span class="detail-chip">${{cases.length}} cases</span>`,
        ].join("");
        facts.push({{ html: `${{payload.meta.edge_count || edges.length}} graph edges across the hybrid bundle.` }});
        facts.push({{ html: `${{payload.meta.enriched_case_count || Object.keys(caseCards).length}} enriched case cards are available for drill-down.` }});
      }} else if (selected.type === "Module") {{
        detailChips.innerHTML = `<span class="detail-chip">${{selected.label_zh || "Module"}}</span>`;
        facts.push({{ html: `${{selected.subgrounds?.length || 0}} subgrounds in this module.` }});
        (selected.subgrounds || []).forEach((subground) => neighbors.push({{
          id: subground.id,
          html: `<strong>${{escapeHtml(subground.label)}}</strong><div>${{escapeHtml((subground.topic_ids || []).length + " topics")}}</div>`,
        }}));
      }} else if (selected.type === "Subground") {{
        detailChips.innerHTML = `<span class="detail-chip">${{selected.label_zh || "Subground"}}</span>`;
        facts.push({{ html: `${{(selected.topic_ids || []).length}} topics are grouped under this branch.` }});
        (selected.topic_ids || []).map((topicId) => nodeMap.get(topicId)).filter(Boolean).forEach((topic) => neighbors.push({{
          id: topic.id,
          html: `<strong>${{escapeHtml(topic.label)}}</strong><div>${{escapeHtml(topic.path || "")}}</div>`,
        }}));
      }} else if (selected.type === "Topic") {{
        detailChips.innerHTML = `<span class="detail-chip">${{selected.path || "Topic branch"}}</span>`;
        facts.push({{ html: `${{relatedCasesForTopic(selected.id).length}} cases linked to this topic.` }});
        facts.push({{ html: `${{relatedStatutesForTopic(selected.id).length}} statutes linked to this topic.` }});
        facts.push({{ html: `${{relatedLineagesForTopic(selected.id).length}} curated lineages linked to this topic.` }});
        relatedCasesForTopic(selected.id).slice(0, 10).forEach((caseNode) => neighbors.push({{
          id: caseNode.id,
          html: `<strong>${{escapeHtml(caseNode.case_name || caseNode.label)}}</strong><div>${{escapeHtml(caseNode.neutral_citation || ("Authority score " + (caseNode.authority_score || 0).toFixed(2)))}}</div>`,
        }}));
        relatedLineagesForTopic(selected.id).forEach((lineage) => support.push({{
          id: lineage.id,
          html: `<strong>${{escapeHtml(lineage.title || lineage.label)}}</strong><div>${{escapeHtml((lineage.codes || []).join(" · "))}}</div>`,
        }}));
      }} else if (selected.type === "Case") {{
        const card = caseCards[selected.id];
        detailSummary.textContent = selected.summary_en || selected.summary || selected.case_name || selected.label;
        detailChips.innerHTML = [
          selected.neutral_citation ? `<span class="detail-chip">${{escapeHtml(selected.neutral_citation)}}</span>` : "",
          `<span class="detail-chip">Authority ${{(selected.authority_score || 0).toFixed(2)}}</span>`,
        ].join("");
        facts.push({{ html: `${{selected.topic_paths?.length || 0}} topic paths attached to this case.` }});
        facts.push({{ html: `${{selected.lineage_ids?.length || 0}} curated lineage memberships.` }});
        selected.topic_paths?.slice(0, 8).forEach((path) => support.push({{ html: `<strong>Topic Path</strong><div>${{escapeHtml(path)}}</div>` }}));
        (card?.relationships || []).slice(0, 10).forEach((relationship) => neighbors.push({{
          id: relationship.target_id,
          html: `<strong>${{escapeHtml(relationship.target_label)}}</strong><div>${{escapeHtml(relationship.type + (relationship.explanation ? " · " + relationship.explanation : ""))}}</div>`,
        }}));
        (card?.principles || []).slice(0, 8).forEach((principle) => support.push({{
          html: `<strong>${{escapeHtml(principle.label_en || principle.paragraph_span || "Principle")}}</strong><div>${{escapeHtml(principle.statement_en || principle.public_excerpt || "")}}</div>`,
        }}));
      }} else if (selected.type === "AuthorityLineage") {{
        detailChips.innerHTML = `<span class="detail-chip">${{escapeHtml((selected.codes || []).join(" · ") || "Lineage")}}</span>`;
        const members = (outgoing.get(selected.id) || []).filter((edge) => edge.type === "HAS_MEMBER");
        facts.push({{ html: `${{members.length}} members in this authority path.` }});
        members.forEach((edge) => {{
          const member = nodeMap.get(edge.target);
          if (!member) return;
          support.push({{
            id: member.id,
            html: `<strong>${{escapeHtml(member.label || member.case_name)}}</strong><div>${{escapeHtml(edge.code || edge.treatment || edge.note || labelForType(member.type))}}</div>`,
          }});
        }});
      }} else if (selected.type === "Statute") {{
        detailSummary.textContent = selected.summary_en || selected.label;
        facts.push({{ html: `${{topicIdsForNode(selected).length}} topic links from this statute.` }});
        topicIdsForNode(selected).forEach((topicId) => {{
          const topic = nodeMap.get(topicId);
          if (!topic) return;
          neighbors.push({{
            id: topic.id,
            html: `<strong>${{escapeHtml(topic.label)}}</strong><div>${{escapeHtml(topic.path || "")}}</div>`,
          }});
        }});
      }}

      renderList(detailFacts, facts, "No metrics available for this node.");
      renderList(detailNeighbors, neighbors, "No related authorities for this node.", true);
      renderList(detailSupport, support, "No principles or lineage data for this node.", true);
    }}

    function render() {{
      renderMetricStrip();
      renderBreadcrumbs();
      renderGraph();
      renderTree();
      renderDetails(getNode(state.selectedId));
      renderResults(searchInput.value);
    }}

    state.expandedViewIds = createDefaultExpandedIds();
    expandGraphPathForNode(getNode(state.selectedId));

    searchInput.addEventListener("input", (event) => renderResults(event.target.value));
    caseRankLimitSelect.addEventListener("change", (event) => {{
      const nextValue = Number(event.target.value);
      state.caseRankLimit = Number.isFinite(nextValue) ? nextValue : 10;
      state.graph.pendingCenterActualId = state.selectedId;
      render();
    }});
    zoomOutButton.addEventListener("click", () => zoomGraph(0.86));
    zoomInButton.addEventListener("click", () => zoomGraph(1.16));
    resetViewButton.addEventListener("click", () => {{
      resetGraphView();
      state.graph.pendingCenterActualId = state.selectedId;
      renderGraph();
    }});
    collapseGraphButton.addEventListener("click", () => {{
      state.expandedViewIds = createDefaultExpandedIds();
      expandGraphPathForNode(getNode(state.selectedId));
      render();
    }});

    graphRagForm.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const question = graphRagInput.value.trim();
      if (!question) return;

      const requestBody = {{
        question,
        top_k: Number(graphRagTopK.value || 5),
        mode: graphRagMode.value || "extractive",
        max_citations: Number(graphRagCitationLimit.value || 6),
        model: graphRagModel.value.trim(),
      }};

      appendGraphRagEntry("user", `
        <h4>Inquiry</h4>
        <p class="chat-answer">${{escapeHtml(question)}}</p>
      `);
      graphRagStatus.textContent = "Running grounded query...";

      try {{
        const response = await fetch("/api/query", {{
          method: "POST",
          headers: {{
            "Content-Type": "application/json",
          }},
          body: JSON.stringify(requestBody),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          throw new Error(payload.error || "GraphRAG query failed");
        }}

        const warningMarkup = (payload.warnings || []).length
          ? `<div class="chat-meta">${{escapeHtml(payload.warnings.join(" | "))}}</div>`
          : "";
        appendGraphRagEntry("assistant", `
          <h4>Grounded Answer</h4>
          <p class="chat-answer">${{escapeHtml(payload.answer || "")}}</p>
          <div class="chat-meta">${{escapeHtml(graphRagTraceLine(payload))}}</div>
          ${{renderGraphRagCitationGrid(payload.citations || [])}}
          ${{warningMarkup}}
        `);
        graphRagStatus.textContent = "Grounded query completed.";

        const firstFocusId = (payload.citations || []).find((citation) => citation.focus_node_id)?.focus_node_id;
        if (firstFocusId) {{
          selectNode(firstFocusId);
        }}
      }} catch (error) {{
        appendGraphRagEntry("assistant", `
          <h4>Grounded Answer</h4>
          <p class="chat-answer">${{escapeHtml(String(error?.message || error || "Unknown error"))}}</p>
        `);
        graphRagStatus.textContent = "Query failed. Check API settings and try again.";
      }}
    }});

    let pointerState = null;
    graphCanvas.addEventListener("pointerdown", (event) => {{
      if (event.target.closest("[data-actual-id]") || event.target.closest("[data-toggle-view-id]")) return;
      pointerState = {{
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        translateX: state.graph.translateX,
        translateY: state.graph.translateY,
      }};
      graphCanvas.classList.add("dragging");
      graphCanvas.setPointerCapture(event.pointerId);
    }});
    graphCanvas.addEventListener("pointermove", (event) => {{
      if (!pointerState || event.pointerId !== pointerState.pointerId) return;
      state.graph.translateX = pointerState.translateX + (event.clientX - pointerState.startX);
      state.graph.translateY = pointerState.translateY + (event.clientY - pointerState.startY);
      applyGraphTransform();
    }});
    graphCanvas.addEventListener("pointerup", (event) => {{
      if (!pointerState || event.pointerId !== pointerState.pointerId) return;
      pointerState = null;
      graphCanvas.classList.remove("dragging");
      graphCanvas.releasePointerCapture(event.pointerId);
    }});
    graphCanvas.addEventListener("pointerleave", () => {{
      if (!pointerState) return;
      graphCanvas.classList.remove("dragging");
    }});
    graphCanvas.addEventListener("wheel", (event) => {{
      event.preventDefault();
      zoomGraph(event.deltaY > 0 ? 0.94 : 1.08);
    }}, {{ passive: false }});

    render();
  </script>
</body>
</html>"""


def render_knowledge_graph(bundle: dict) -> str:
    """Render an interactive D3.js force-directed knowledge graph from a hybrid graph bundle."""
    meta = bundle.get("meta", {})
    heading = meta.get("viewer_heading_public") or meta.get("title") or "HK Legal Knowledge Graph"
    node_count = meta.get("node_count", 0)
    edge_count = meta.get("edge_count", 0)

    # Build a lightweight node/edge payload for the browser
    # Only include fields needed for rendering to keep payload small
    VISIBLE_TYPES = {"Module", "Subground", "Topic", "Case", "Statute", "AuthorityLineage"}
    graph_nodes = []
    for n in bundle.get("nodes", []):
        if n.get("type") not in VISIBLE_TYPES:
            continue
        graph_nodes.append({
            "id": n["id"],
            "type": n["type"],
            "label": n.get("label_en") or n.get("case_name") or n.get("label") or n["id"],
            "summary": (n.get("summary_en") or n.get("summary") or "")[:280],
        })

    visible_ids = {n["id"] for n in graph_nodes}
    VISIBLE_EDGE_TYPES = {"CONTAINS", "BELONGS_TO_TOPIC", "CITES", "FOLLOWS", "APPLIES", "DISTINGUISHES", "HAS_MEMBER", "ABOUT_TOPIC"}
    graph_edges = [
        {"source": e["source"], "target": e["target"], "type": e["type"]}
        for e in bundle.get("edges", [])
        if e.get("type") in VISIBLE_EDGE_TYPES
        and e["source"] in visible_ids
        and e["target"] in visible_ids
    ]

    import json as _json
    nodes_json = _json.dumps(graph_nodes, ensure_ascii=False)
    edges_json = _json.dumps(graph_edges, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Casemap Knowledge Graph</title>
  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <style>
    :root {{
      --bg: #f0f4f8;
      --panel: rgba(255,255,255,0.92);
      --ink: #101317;
      --muted: #6b7280;
      --line: rgba(16,19,23,0.1);
      --module: #0f4c5c;
      --subground: #2d6a8a;
      --topic: #d28d2d;
      --case: #7f5539;
      --statute: #bc4749;
      --lineage: #52796f;
      --accent: #0f1216;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: "Avenir Next","Helvetica Neue",sans-serif; background: var(--bg); color: var(--ink); height: 100vh; display: flex; flex-direction: column; }}
    .toolbar {{ display: flex; align-items: center; gap: 12px; padding: 10px 18px; background: var(--panel); border-bottom: 1px solid var(--line); flex-shrink: 0; }}
    .toolbar h1 {{ font-size: 16px; font-weight: 600; letter-spacing: -0.02em; }}
    .toolbar .counts {{ color: var(--muted); font-size: 12px; }}
    .toolbar input {{ padding: 7px 12px; border: 1px solid var(--line); border-radius: 999px; font-size: 13px; background: white; width: 220px; }}
    nav.nav {{ display: inline-flex; gap: 6px; padding: 4px; border: 1px solid var(--line); border-radius: 999px; background: rgba(255,255,255,0.7); margin-left: auto; }}
    nav.nav a {{ padding: 7px 12px; border-radius: 999px; color: var(--ink); text-decoration: none; font-size: 12px; }}
    nav.nav a.active {{ background: var(--accent); color: white; }}
    .legend {{ display: flex; gap: 10px; flex-wrap: wrap; font-size: 11px; color: var(--muted); }}
    .legend span {{ display: inline-flex; align-items: center; gap: 5px; }}
    .swatch {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}
    .main {{ display: flex; flex: 1; overflow: hidden; }}
    #graph-container {{ flex: 1; overflow: hidden; position: relative; }}
    svg {{ width: 100%; height: 100%; }}
    .side {{ width: 320px; border-left: 1px solid var(--line); background: var(--panel); padding: 20px 18px; overflow-y: auto; flex-shrink: 0; }}
    .side .meta {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--muted); margin-bottom: 6px; }}
    .side h2 {{ font-size: 20px; line-height: 1.1; margin-bottom: 8px; }}
    .side .pill {{ display: inline-block; padding: 5px 10px; border-radius: 999px; font-size: 11px; background: rgba(16,19,23,0.06); color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; }}
    .side p {{ font-size: 14px; line-height: 1.6; color: var(--ink); margin-bottom: 14px; }}
    .side ul {{ list-style: none; display: grid; gap: 8px; margin-bottom: 14px; }}
    .side ul li {{ border: 1px solid var(--line); border-radius: 12px; padding: 9px 12px; font-size: 13px; background: rgba(255,255,255,0.6); }}
    .node circle {{ stroke: rgba(255,255,255,0.9); stroke-width: 1.5; cursor: pointer; transition: stroke-width 120ms; }}
    .node circle:hover {{ stroke-width: 3; }}
    .node text {{ font-size: 10px; fill: var(--ink); pointer-events: none; font-family: "SFMono-Regular",monospace; }}
    .link {{ stroke: rgba(16,19,23,0.12); stroke-width: 1; }}
    .link.CITES, .link.FOLLOWS, .link.APPLIES {{ stroke: rgba(16,19,23,0.22); stroke-width: 1.4; }}
    .faded {{ opacity: 0.1; }}
    .active circle {{ stroke: var(--accent) !important; stroke-width: 3.5 !important; }}
  </style>
</head>
<body>
  <div class="toolbar">
    <h1>{heading}</h1>
    <span class="counts">{node_count} nodes · {edge_count} edges</span>
    <input id="search" type="search" placeholder="Search nodes…">
    <div class="legend">
      <span><i class="swatch" style="background:var(--module)"></i>Module</span>
      <span><i class="swatch" style="background:var(--subground)"></i>Subground</span>
      <span><i class="swatch" style="background:var(--topic)"></i>Topic</span>
      <span><i class="swatch" style="background:var(--case)"></i>Case</span>
      <span><i class="swatch" style="background:var(--statute)"></i>Statute</span>
      <span><i class="swatch" style="background:var(--lineage)"></i>Lineage</span>
    </div>
    <nav class="nav">
      <a href="/">Graph</a>
      <a href="/tree">Hierarchy</a>
      <a href="/graph" class="active">Force Graph</a>
    </nav>
  </div>
  <div class="main">
    <div id="graph-container">
      <svg id="svg"></svg>
    </div>
    <aside class="side">
      <div class="meta">Selection</div>
      <h2 id="nodeTitle">Overview</h2>
      <div id="nodeType" class="pill">Knowledge Graph</div>
      <p id="nodeSummary">Click any node to inspect its details, type, and connected neighbours.</p>
      <div class="meta">Neighbours</div>
      <ul id="neighbourList"><li>No node selected.</li></ul>
    </aside>
  </div>
  <script>
    const NODES = {nodes_json};
    const EDGES = {edges_json};

    const COLOR = {{
      Module: getComputedStyle(document.documentElement).getPropertyValue("--module").trim(),
      Subground: getComputedStyle(document.documentElement).getPropertyValue("--subground").trim(),
      Topic: getComputedStyle(document.documentElement).getPropertyValue("--topic").trim(),
      Case: getComputedStyle(document.documentElement).getPropertyValue("--case").trim(),
      Statute: getComputedStyle(document.documentElement).getPropertyValue("--statute").trim(),
      AuthorityLineage: getComputedStyle(document.documentElement).getPropertyValue("--lineage").trim(),
    }};
    const RADIUS = {{ Module: 22, Subground: 15, Topic: 11, Case: 9, Statute: 8, AuthorityLineage: 8 }};

    const nodeIndex = new Map(NODES.map(n => [n.id, n]));
    const neighbours = new Map(NODES.map(n => [n.id, new Set()]));
    EDGES.forEach(e => {{ neighbours.get(e.source)?.add(e.target); neighbours.get(e.target)?.add(e.source); }});

    const container = document.getElementById("graph-container");
    const svg = d3.select("#svg");
    const width = () => container.clientWidth;
    const height = () => container.clientHeight;

    const zoom = d3.zoom().scaleExtent([0.05, 4]).on("zoom", (event) => g.attr("transform", event.transform));
    svg.call(zoom);
    const g = svg.append("g");

    const sim = d3.forceSimulation(NODES)
      .force("link", d3.forceLink(EDGES).id(d => d.id).distance(d => {{
        const types = [d.source.type || "", d.target.type || ""];
        if (types.includes("Module")) return 180;
        if (types.includes("Subground")) return 120;
        if (types.includes("Topic")) return 80;
        return 60;
      }}).strength(0.6))
      .force("charge", d3.forceManyBody().strength(d => {{
        if (d.type === "Module") return -800;
        if (d.type === "Subground") return -400;
        if (d.type === "Topic") return -200;
        return -120;
      }}))
      .force("center", d3.forceCenter(0, 0))
      .force("collision", d3.forceCollide().radius(d => (RADIUS[d.type] || 9) + 4));

    const link = g.append("g").selectAll("line")
      .data(EDGES).join("line")
      .attr("class", d => `link ${{d.type}}`)
      .attr("marker-end", null);

    const node = g.append("g").selectAll("g")
      .data(NODES).join("g")
      .attr("class", "node")
      .call(d3.drag()
        .on("start", (event, d) => {{ if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
        .on("drag", (event, d) => {{ d.fx = event.x; d.fy = event.y; }})
        .on("end", (event, d) => {{ if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }}))
      .on("click", (event, d) => selectNode(d.id));

    node.append("circle")
      .attr("r", d => RADIUS[d.type] || 9)
      .attr("fill", d => COLOR[d.type] || "#888")
      .attr("fill-opacity", 0.88);

    node.append("text")
      .attr("dx", d => (RADIUS[d.type] || 9) + 4)
      .attr("dy", "0.35em")
      .text(d => d.label.length > 28 ? d.label.slice(0, 26) + "…" : d.label);

    sim.on("tick", () => {{
      link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
      node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    // Centre view after initial layout
    sim.on("end", () => {{
      const bounds = g.node().getBBox();
      const w = width(), h = height();
      const scale = Math.min(0.9, 0.9 / Math.max(bounds.width / w, bounds.height / h));
      svg.call(zoom.transform, d3.zoomIdentity
        .translate(w / 2 - scale * (bounds.x + bounds.width / 2), h / 2 - scale * (bounds.y + bounds.height / 2))
        .scale(scale));
    }});

    const titleEl = document.getElementById("nodeTitle");
    const typeEl = document.getElementById("nodeType");
    const summaryEl = document.getElementById("nodeSummary");
    const neighbourList = document.getElementById("neighbourList");

    function selectNode(id) {{
      const n = nodeIndex.get(id);
      if (!n) return;
      const nbs = [...(neighbours.get(id) || [])].map(nid => nodeIndex.get(nid)).filter(Boolean);
      titleEl.textContent = n.label;
      typeEl.textContent = n.type;
      summaryEl.textContent = n.summary || "No summary available.";
      neighbourList.innerHTML = "";
      if (!nbs.length) {{
        neighbourList.innerHTML = "<li>No neighbours.</li>";
      }} else {{
        nbs.sort((a, b) => a.label.localeCompare(b.label)).forEach(nb => {{
          const li = document.createElement("li");
          li.textContent = `${{nb.label}} (${{nb.type}})`;
          li.style.cursor = "pointer";
          li.addEventListener("click", () => selectNode(nb.id));
          neighbourList.appendChild(li);
        }});
      }}
      node.classed("faded", d => d.id !== id && !neighbours.get(id)?.has(d.id));
      node.classed("active", d => d.id === id);
      link.classed("faded", d => d.source.id !== id && d.target.id !== id);
    }}

    document.getElementById("search").addEventListener("input", e => {{
      const q = e.target.value.trim().toLowerCase();
      if (!q) {{ node.classed("faded", false).classed("active", false); link.classed("faded", false); return; }}
      const match = NODES.find(n => n.label.toLowerCase().includes(q) || n.summary.toLowerCase().includes(q));
      if (match) selectNode(match.id);
    }});
  </script>
</body>
</html>"""


def render_determinator_page(bundle: dict, hierarchy_html: str) -> str:
    """Render a graph-first criminal-law workspace with a hierarchy backup and determiner search."""
    meta = bundle.get("meta", {})
    heading = meta.get("viewer_heading_public") or meta.get("title") or "HK Criminal Law Knowledge Graph"
    legal_domain = meta.get("legal_domain", "criminal")
    node_count = meta.get("node_count", 0)
    edge_count = meta.get("edge_count", 0)
    case_count = meta.get("case_count", 0)
    statute_count = meta.get("statute_count", 0)
    hierarchy_payload = json.dumps(base64.b64encode(hierarchy_html.encode("utf-8")).decode("ascii"))

    # Build inline graph data (same logic as render_knowledge_graph)
    VISIBLE_TYPES = {"Module", "Subground", "Topic", "Case", "Statute", "AuthorityLineage"}
    graph_nodes = []
    for n in bundle.get("nodes", []):
        if n.get("type") not in VISIBLE_TYPES:
            continue
        graph_nodes.append({
            "id": n["id"],
            "type": n["type"],
            "label": (n.get("label_en") or n.get("case_name") or n.get("label") or n["id"])[:32],
            "summary": (n.get("summary_en") or n.get("summary") or "")[:240],
        })
    visible_ids = {n["id"] for n in graph_nodes}
    VISIBLE_EDGE_TYPES = {"CONTAINS", "BELONGS_TO_TOPIC", "CITES", "FOLLOWS", "APPLIES", "DISTINGUISHES", "HAS_MEMBER", "ABOUT_TOPIC"}
    graph_edges = [
        {"source": e["source"], "target": e["target"], "type": e["type"]}
        for e in bundle.get("edges", [])
        if e.get("type") in VISIBLE_EDGE_TYPES
        and e["source"] in visible_ids
        and e["target"] in visible_ids
    ]
    nodes_json = json.dumps(graph_nodes, ensure_ascii=False)
    edges_json = json.dumps(graph_edges, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Casemap Determinator</title>
  <style>
    :root {{
      --bg: #091017;
      --panel: rgba(11, 18, 26, 0.92);
      --panel-2: rgba(17, 27, 39, 0.9);
      --ink: #f3f7fb;
      --muted: #99a7b8;
      --line: rgba(255, 255, 255, 0.12);
      --accent: #f1a238;
      --accent-2: #4dc0b5;
      --danger: #d36b6b;
      --shadow: 0 30px 80px rgba(0, 0, 0, 0.28);
    }}
    html {{ scroll-behavior: smooth; }}
    * {{ box-sizing: border-box; }}
    .hidden {{ display: none !important; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(77, 192, 181, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(241, 162, 56, 0.18), transparent 24%),
        linear-gradient(180deg, #081018 0%, #0b141f 48%, #081018 100%);
    }}
    .shell {{
      width: min(1480px, calc(100vw - 32px));
      margin: 16px auto;
      display: grid;
      gap: 16px;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      gap: 20px;
      padding: 14px 22px;
      flex-wrap: wrap;
    }}
    .topbar-left {{ flex: 1; min-width: 0; }}
    .topbar-left h1 {{ margin: 4px 0 0; font-size: 20px; letter-spacing: -0.02em; line-height: 1.1; }}
    .topbar-stats {{ display: flex; gap: 16px; }}
    .topbar-nav {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .mode-btn {{
      padding: 8px 16px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: transparent;
      color: var(--muted);
      font: inherit;
      font-size: 13px;
      cursor: pointer;
      transition: background 120ms, color 120ms;
    }}
    .mode-btn.active {{ background: var(--accent); color: #0b121a; border-color: var(--accent); font-weight: 600; }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.8fr);
      gap: 16px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .hero-copy {{
      padding: 24px 28px;
      display: grid;
      gap: 14px;
    }}
    .eyebrow {{
      font-size: 11px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--accent-2);
    }}
    h1 {{
      margin: 0;
      font-size: clamp(34px, 4vw, 56px);
      line-height: 0.92;
      letter-spacing: -0.04em;
      max-width: 12ch;
    }}
    .lede {{
      margin: 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.65;
      max-width: 68ch;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }}
    .stat {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.04);
      padding: 14px 16px;
    }}
    .stat strong {{
      display: block;
      font-size: 24px;
      line-height: 1;
      letter-spacing: -0.04em;
    }}
    .stat span {{
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .hero-side {{
      padding: 22px;
      display: grid;
      gap: 14px;
      align-content: start;
    }}
    .mode-switch {{
      display: inline-flex;
      gap: 8px;
      padding: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.04);
      width: fit-content;
    }}
    .mode-switch button,
    .inline-link {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(255, 255, 255, 0.04);
      color: var(--ink);
      cursor: pointer;
      font-size: 13px;
      text-decoration: none;
    }}
    .mode-switch button.active {{
      background: var(--accent);
      color: #101317;
      font-weight: 600;
    }}
    .helper {{
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }}
    .workspace {{
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(360px, 0.9fr);
      gap: 16px;
      align-items: start;
    }}
    .canvas {{
      overflow: hidden;
      min-height: 780px;
    }}
    .section-anchor {{ scroll-margin-top: 18px; }}
    .canvas-header {{
      padding: 18px 20px 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .canvas-header h2 {{
      margin: 0;
      font-size: 18px;
      letter-spacing: -0.03em;
    }}
    .canvas-header .sub {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }}
    .canvas-stage {{
      padding: 16px;
      height: 720px;
    }}
    .canvas-pane {{
      width: 100%;
      height: 100%;
      border: 1px solid var(--line);
      border-radius: 20px;
      overflow: hidden;
      background: rgba(0, 0, 0, 0.18);
    }}
    .canvas-pane.hidden {{ display: none; }}
    iframe {{
      width: 100%;
      height: 100%;
      border: 0;
      background: #0b121a;
    }}
    #mainGraph {{
      width: 100%;
      height: 100%;
      display: block;
      background: #0b121a;
    }}
    .graph-note {{
      padding: 0 20px 16px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    .hierarchy-shell {{
      width: 100%;
      height: 100%;
      overflow: auto;
      background: #f5efe5;
      color: #111827;
    }}
    .search-panel {{
      padding: 20px;
      display: grid;
      gap: 14px;
      align-content: start;
    }}
    .search-panel h2 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: -0.03em;
    }}
    .label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: var(--muted);
    }}
    .controls {{
      display: grid;
      gap: 10px;
    }}
    textarea,
    select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.04);
      color: var(--ink);
      padding: 14px 16px;
      font: inherit;
    }}
    textarea {{
      min-height: 132px;
      resize: vertical;
      line-height: 1.55;
    }}
    .actions {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .primary {{
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      background: linear-gradient(135deg, var(--accent) 0%, #ffd08a 100%);
      color: #111827;
      font-weight: 700;
      cursor: pointer;
    }}
    .status {{
      color: var(--muted);
      font-size: 13px;
    }}
    .result {{
      border-top: 1px solid var(--line);
      padding-top: 16px;
      display: grid;
      gap: 14px;
    }}
    .result.hidden {{ display: none; }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(19, 28, 40, 0.98);
      padding: 14px 16px;
    }}
    .card h3 {{
      margin: 0 0 8px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--accent-2);
    }}
    .answer {{
      white-space: pre-wrap;
      font-size: 14px;
      line-height: 1.75;
      color: #e8edf3;
    }}
    .answer,
    .answer p,
    .answer div,
    .answer span,
    .answer li,
    .answer td {{
      color: #e8edf3 !important;
    }}
    .answer strong {{ color: #f3f7fb !important; font-weight: 600; }}
    .answer em {{ color: #c8d8e8 !important; font-style: italic; }}
    .answer h4 {{ margin: 12px 0 4px; color: var(--accent) !important; font-size: 13px; text-transform: uppercase; letter-spacing: 0.1em; }}
    .answer table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }}
    .answer th {{ background: rgba(255,255,255,0.08); color: var(--accent-2) !important; padding: 6px 10px; text-align: left; border: 1px solid var(--line); }}
    .answer td {{ padding: 6px 10px; border: 1px solid var(--line); vertical-align: top; }}
    .answer ul, .answer ol {{ padding-left: 20px; margin: 6px 0; }}
    .answer li {{ margin: 3px 0; }}
    .answer hr {{ border: 0; border-top: 1px solid var(--line); margin: 12px 0; }}
    .citations {{
      display: grid;
      gap: 10px;
    }}
    .citation {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      background: rgba(255, 255, 255, 0.03);
    }}
    .citation strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 14px;
    }}
    .citation .meta {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .citation p {{
      margin: 0;
      color: #dbe5ef;
      font-size: 13px;
      line-height: 1.6;
    }}
    .warning {{
      color: #ffd5a6;
      font-size: 13px;
      line-height: 1.55;
    }}
    .error {{
      color: #ffd3d3;
      background: rgba(211, 107, 107, 0.12);
      border: 1px solid rgba(211, 107, 107, 0.25);
      border-radius: 14px;
      padding: 12px 14px;
      font-size: 13px;
      line-height: 1.6;
    }}
    @media (max-width: 1160px) {{
      .hero,
      .workspace {{
        grid-template-columns: 1fr;
      }}
      .canvas {{
        min-height: 640px;
      }}
      .canvas-stage {{
        height: 580px;
      }}
    }}
    @media (max-width: 760px) {{
      .shell {{
        width: min(100vw - 16px, 100%);
        margin: 8px auto 16px;
      }}
      .hero-copy,
      .hero-side,
      .search-panel {{
        padding: 18px;
      }}
      .stats {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .canvas-stage {{
        padding: 10px;
        height: 420px;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar panel">
      <div class="topbar-left">
        <span class="eyebrow">{legal_domain} · GraphRAG</span>
        <h1>{heading}</h1>
      </div>
      <div class="topbar-stats">
        <div class="stat"><strong>{node_count}</strong><span>Nodes</span></div>
        <div class="stat"><strong>{case_count}</strong><span>Cases</span></div>
        <div class="stat"><strong>{statute_count}</strong><span>Statutes</span></div>
      </div>
      <div class="topbar-nav">
        <a class="inline-link" href="#graphSection">Jump to Graph</a>
        <a class="inline-link" href="#inquirySection">Jump to Inquiry</a>
        <button id="graphModeBtn" class="mode-btn active" type="button">Knowledge Graph</button>
        <button id="hierarchyModeBtn" class="mode-btn" type="button">Hierarchy Tree</button>
        <a class="inline-link" href="/tree">Full Tree</a>
      </div>
    </header>

    <section class="workspace">
      <section id="graphSection" class="panel canvas section-anchor">
        <div class="canvas-header">
          <div class="sub">Doctrinal Relationship Map</div>
          <h2 id="canvasTitle">Graph Workspace</h2>
        </div>
        <div class="canvas-stage">
          <div id="graphPane" class="canvas-pane">
            <svg id="mainGraph"></svg>
          </div>
          <div id="hierarchyPane" class="canvas-pane hidden">
            <div class="hierarchy-shell" id="hierarchyMount"></div>
          </div>
        </div>
      </section>

      <aside id="inquirySection" class="panel search-panel section-anchor">
        <div class="label">Determinator</div>
        <h2>Structured Criminal RAG</h2>
        <p class="helper">This panel queries the existing graph and embeddings first, then uses the determiner pipeline to synthesize a tighter answer. When available, fallback LLM synthesis stays grounded against the local citations.</p>
        <div class="controls">
          <label class="label" for="question">Question</label>
          <textarea id="question" placeholder="Ask about offences, defences, procedure, evidence, sentencing, or a specific Hong Kong criminal-law topic."></textarea>
          <label class="label" for="mode">Model Path</label>
          <select id="mode">
            <option value="openrouter">OpenRouter</option>
            <option value="deepseek">DeepSeek</option>
          </select>
          <div class="actions">
            <button id="runBtn" class="primary" type="button">Run Determinator</button>
            <span id="status" class="status">Ready.</span>
          </div>
        </div>

        <section id="result" class="result hidden">
          <div class="card">
            <h3>Grounded Answer</h3>
            <div id="answer" class="answer"></div>
          </div>
          <div class="card">
            <h3>Mode</h3>
            <div id="meta" class="answer"></div>
          </div>
          <div class="card">
            <h3>Disclaimer</h3>
            <div id="disclaimer" class="answer"></div>
          </div>
          <div class="card">
            <h3>Supporting Citations</h3>
            <div id="citations" class="citations"></div>
          </div>
          <div id="warningsCard" class="card hidden">
            <h3>Warnings</h3>
            <div id="warnings" class="warning"></div>
          </div>
        </section>

        <div id="errorBox" class="error hidden"></div>
      </aside>
    </section>
  </main>

  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <script>
    // ── Inline force-directed graph ──────────────────────────────────────
    const GNODES = {nodes_json};
    const GEDGES = {edges_json};
    const GCOLOR = {{
      Module:"#4a9eff", Subground:"#7b68ee", Topic:"#ffa500",
      Case:"#ff6b6b", Statute:"#50c878", AuthorityLineage:"#dda0dd"
    }};
    const GRADIUS = {{Module:22,Subground:15,Topic:11,Case:9,Statute:8,AuthorityLineage:8}};
    const gNeighbours = new Map(GNODES.map(n=>[n.id,new Set()]));
    GEDGES.forEach(e=>{{gNeighbours.get(e.source)?.add(e.target);gNeighbours.get(e.target)?.add(e.source);}});
    const gIndex = new Map(GNODES.map(n=>[n.id,n]));
    let gSvg = null;
    let gZoom = null;
    let gG = null;
    let gNode = null;
    let gLink = null;
    let gViewport = {{ w: 900, h: 700 }};

    function renderGraphFallback(message) {{
      const graphPaneEl = document.getElementById("graphPane");
      graphPaneEl.innerHTML = `
        <div style="display:grid;gap:12px;height:100%;padding:16px;background:#0b121a;color:#e8edf3;align-content:start;">
          <div>
            <strong>Inline graph did not finish loading.</strong>
            <p style="margin:8px 0 0;color:#99a7b8;line-height:1.6;">${{message || "Falling back to the dedicated graph viewer so the node map still stays accessible."}}</p>
          </div>
          <iframe src="/graph" title="Casemap graph workspace" style="width:100%;height:100%;min-height:520px;border:0;border-radius:14px;"></iframe>
        </div>
      `;
    }}

    try {{
      if (!window.d3 || !GNODES.length) {{
        renderGraphFallback("The browser could not initialise the inline renderer.");
      }} else {{
        gSvg = d3.select("#mainGraph");
        const gSvgEl = gSvg.node();
        gG = gSvg.append("g");
        gZoom = d3.zoom().scaleExtent([0.04,4]).on("zoom",ev=>gG.attr("transform",ev.transform));
        gSvg.call(gZoom);

        function viewport() {{
          const rect = gSvgEl.getBoundingClientRect();
          return {{
            w: Math.max(640, rect.width || 0),
            h: Math.max(420, rect.height || 0),
          }};
        }}

        function fitGraph() {{
          try {{
            const bbox = gG.node().getBBox();
            const {{ w, h }} = viewport();
            gViewport = {{ w, h }};
            const widthRatio = bbox.width / Math.max(w, 1);
            const heightRatio = bbox.height / Math.max(h, 1);
            const scale = Math.min(0.9, 0.9 / Math.max(widthRatio, heightRatio, 0.01));
            const tx = w / 2 - scale * (bbox.x + bbox.width / 2);
            const ty = h / 2 - scale * (bbox.y + bbox.height / 2);
            gSvg.transition().duration(250).call(gZoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
          }} catch (error) {{
            console.warn("graph-fit-failed", error);
          }}
        }}

        const {{ w, h }} = viewport();
        gViewport = {{ w, h }};
        gSvg.attr("viewBox", `0 0 ${{w}} ${{h}}`);
        GNODES.forEach((node, index) => {{
          const angle = (Math.PI * 2 * index) / Math.max(GNODES.length, 1);
          const radius = Math.min(w, h) * 0.24 + (index % 11) * 6;
          node.x = w / 2 + Math.cos(angle) * radius;
          node.y = h / 2 + Math.sin(angle) * radius;
        }});

        gSvg.append("defs").append("marker")
          .attr("id","arrow").attr("viewBox","0 -4 8 8").attr("refX",14).attr("refY",0)
          .attr("markerWidth",6).attr("markerHeight",6).attr("orient","auto")
          .append("path").attr("d","M0,-4L8,0L0,4").attr("fill","rgba(255,255,255,0.25)");

        const gSim = d3.forceSimulation(GNODES)
          .force("link",d3.forceLink(GEDGES).id(d=>d.id).distance(d=>{{
            const t=[d.source.type||"",d.target.type||""];
            if(t.includes("Module"))return 220;if(t.includes("Subground"))return 150;if(t.includes("Topic"))return 104;return 72;
          }}).strength(0.5))
          .force("charge",d3.forceManyBody().strength(d=>{{
            if(d.type==="Module")return -960;if(d.type==="Subground")return -520;if(d.type==="Topic")return -260;return -150;
          }}))
          .force("center",d3.forceCenter(w/2,h/2))
          .force("collision",d3.forceCollide().radius(d=>(GRADIUS[d.type]||9)+8));

        gLink = gG.append("g").selectAll("line").data(GEDGES).join("line")
          .attr("stroke","rgba(255,255,255,0.12)").attr("stroke-width",1)
          .attr("marker-end","url(#arrow)");

        gNode = gG.append("g").selectAll("g").data(GNODES).join("g")
          .attr("cursor","pointer")
          .call(d3.drag()
            .on("start",(ev,d)=>{{if(!ev.active)gSim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}})
            .on("drag",(ev,d)=>{{d.fx=ev.x;d.fy=ev.y;}})
            .on("end",(ev,d)=>{{if(!ev.active)gSim.alphaTarget(0);d.fx=null;d.fy=null;}}))
          .on("click",(ev,d)=>{{
            const q=document.getElementById("question");
            if(q)q.value=d.label+(d.type==="Topic"?" — what are the key legal principles and cases?":"");
            gNode.attr("opacity",n=>n.id===d.id||gNeighbours.get(d.id)?.has(n.id)?1:0.15);
            gLink.attr("opacity",e=>e.source.id===d.id||e.target.id===d.id?1:0.08);
          }});

        gNode.append("circle")
          .attr("r",d=>GRADIUS[d.type]||9)
          .attr("fill",d=>GCOLOR[d.type]||"#888")
          .attr("fill-opacity",0.88)
          .attr("stroke","rgba(255,255,255,0.72)").attr("stroke-width",1.2);

        gNode.append("text")
          .attr("dx",d=>(GRADIUS[d.type]||9)+4).attr("dy","0.35em")
          .attr("fill","#e8edf3").attr("font-size","9.5px")
          .attr("font-family","'SFMono-Regular',monospace")
          .text(d=>d.label.length>26?d.label.slice(0,24)+"…":d.label);

        // Paint an immediate static frame so the graph is visible
        // even before force-simulation ticks fire in slower browsers.
        const initialPos = new Map(GNODES.map(n => [n.id, n]));
        gLink
          .attr("x1", d => (initialPos.get(typeof d.source === "string" ? d.source : d.source.id)?.x ?? w / 2))
          .attr("y1", d => (initialPos.get(typeof d.source === "string" ? d.source : d.source.id)?.y ?? h / 2))
          .attr("x2", d => (initialPos.get(typeof d.target === "string" ? d.target : d.target.id)?.x ?? w / 2))
          .attr("y2", d => (initialPos.get(typeof d.target === "string" ? d.target : d.target.id)?.y ?? h / 2));
        gNode.attr("transform", d => `translate(${{d.x}},${{d.y}})`);

        let fitted = false;
        gSim.on("tick",()=>{{
          gLink.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
               .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
          gNode.attr("transform",d=>`translate(${{d.x}},${{d.y}})`);
          if (!fitted && gSim.alpha() < 0.28) {{
            fitted = true;
            fitGraph();
          }}
        }});

        gSim.on("end", fitGraph);
        window.addEventListener("resize", () => {{
          const next = viewport();
          gViewport = next;
          gSvg.attr("viewBox", `0 0 ${{next.w}} ${{next.h}}`);
          gSim.force("center", d3.forceCenter(next.w/2, next.h/2));
          fitGraph();
        }});

        setTimeout(() => {{
          if (!fitted) fitGraph();
        }}, 700);

        gSvg.on("click",ev=>{{
          if(ev.target===gSvg.node()||ev.target===gG.node()){{
            gNode.attr("opacity",1);gLink.attr("opacity",1);
          }}
        }});
      }}
    }} catch (error) {{
      console.error("inline-graph-init-failed", error);
      renderGraphFallback("The inline graph renderer failed in this browser session.");
    }}
    // ── End inline graph ─────────────────────────────────────────────────

    const hierarchyHtml = new TextDecoder().decode(
      Uint8Array.from(atob({hierarchy_payload}), (char) => char.charCodeAt(0))
    );
    const hierarchyMount = document.getElementById("hierarchyMount");
    hierarchyMount.innerHTML = hierarchyHtml;

    const graphPane = document.getElementById("graphPane");
    const hierarchyPane = document.getElementById("hierarchyPane");
    const graphModeBtn = document.getElementById("graphModeBtn");
    const hierarchyModeBtn = document.getElementById("hierarchyModeBtn");
    const canvasTitle = document.getElementById("canvasTitle");
    const resultEl = document.getElementById("result");
    const answerEl = document.getElementById("answer");
    const metaEl = document.getElementById("meta");
    const disclaimerEl = document.getElementById("disclaimer");
    const citationsEl = document.getElementById("citations");
    const warningsCard = document.getElementById("warningsCard");
    const warningsEl = document.getElementById("warnings");
    const errorBox = document.getElementById("errorBox");
    const statusEl = document.getElementById("status");

    function switchMode(mode) {{
      const showGraph = mode === "graph";
      graphPane.classList.toggle("hidden", !showGraph);
      hierarchyPane.classList.toggle("hidden", showGraph);
      graphModeBtn.classList.toggle("active", showGraph);
      hierarchyModeBtn.classList.toggle("active", !showGraph);
      canvasTitle.textContent = showGraph ? "Graph Workspace" : "Hierarchy Backup";
    }}

    graphModeBtn.addEventListener("click", () => switchMode("graph"));
    hierarchyModeBtn.addEventListener("click", () => switchMode("hierarchy"));

    function markdownToHtml(text) {{
      // Minimal markdown renderer: bold, italic, headers, tables, lists, hr
      let html = text
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        // Tables: | col | col |
        .replace(/^\\|(.+)\\|\\s*$/gm, (_, row) => `<tr>${{row.split("|").map(c => `<td>${{c.trim()}}</td>`).join("")}}</tr>`)
        .replace(/(<tr>.*<\\/tr>\\n?)+/gs, match => `<table>${{match}}</table>`)
        // Headers
        .replace(/^#{1,3}\\s+(.+)$/gm, (_, t) => `<h4>${{t}}</h4>`)
        // Bold
        .replace(/\\*\\*(.+?)\\*\\*/g, "<strong>$1</strong>")
        // Italic
        .replace(/\\*(.+?)\\*/g, "<em>$1</em>")
        // HR
        .replace(/^---+$/gm, "<hr>")
        // Unordered list items
        .replace(/^[\\-\\*]\\s+(.+)$/gm, "<li>$1</li>")
        .replace(/(<li>.*<\\/li>\\n?)+/gs, match => `<ul>${{match}}</ul>`)
        // Numbered list items
        .replace(/^\\d+\\.\\s+(.+)$/gm, "<li>$1</li>")
        // Paragraphs: double newline
        .replace(/\\n{{2,}}/g, "</p><p>")
        // Single newlines
        .replace(/\\n/g, "<br>");
      return `<p>${{html}}</p>`;
    }}

    function setBusy(isBusy, message) {{
      document.getElementById("runBtn").disabled = isBusy;
      statusEl.textContent = message;
    }}

    // Focus the graph on a node by case_id or case_name match
    function focusGraphNode(caseId, caseName) {{
      if (!gSvg || !gZoom || !gNode || !gLink) return;
      // Try exact id match first, then label match
      let target = gIndex.get(caseId);
      if (!target && caseName) {{
        const lower = caseName.toLowerCase();
        target = GNODES.find(n => (n.label||"").toLowerCase().includes(lower) || lower.includes((n.label||"").toLowerCase().slice(0,12)));
      }}
      if (!target) return;
      // Highlight
      gNode.attr("opacity", n => n.id === target.id || gNeighbours.get(target.id)?.has(n.id) ? 1 : 0.15);
      gLink.attr("opacity", e => e.source.id === target.id || e.target.id === target.id ? 1 : 0.08);
      // Zoom to node
      const w = gSvg.node().clientWidth || gViewport.w;
      const h = gSvg.node().clientHeight || gViewport.h;
      gSvg.transition().duration(600).call(gZoom.transform,
        d3.zoomIdentity.translate(w/2 - target.x * 1.4, h/2 - target.y * 1.4).scale(1.4)
      );
    }}

    function citationMarkup(citation) {{
      const title = citation.case_name || citation.label || citation.citation_id || "Citation";
      const meta = [citation.neutral_citation, citation.paragraph_span].filter(Boolean).join(" · ");
      const quote = citation.quote || citation.summary || "No summary available.";
      const caseId = citation.case_id || citation.focus_node_id || "";
      const hkliiLinks = (citation.links || []).map(l => `<a href="${{l.url}}" target="_blank" rel="noopener">${{l.label || "HKLII"}}</a>`).join(" ");
      return `
        <article class="citation" data-case-id="${{caseId}}" data-case-name="${{title}}" style="cursor:pointer" onclick="focusGraphNode('${{caseId}}','${{title.replace(/'/g,"\\'")}}')" title="Click to focus in graph">
          <strong>${{title}}</strong>
          <div class="meta">${{meta || "Local grounding"}}${{hkliiLinks ? " · " + hkliiLinks : ""}}</div>
          <p>${{quote}}</p>
          ${{caseId ? `<div class="meta" style="color:var(--accent-2);font-size:11px">▶ Click to focus in graph</div>` : ""}}
        </article>
      `;
    }}

    async function runDeterminator() {{
      const question = document.getElementById("question").value.trim();
      const mode = document.getElementById("mode").value;
      if (!question) {{
        errorBox.textContent = "Enter a question before running the determiner.";
        errorBox.classList.remove("hidden");
        return;
      }}
      errorBox.classList.add("hidden");
      setBusy(true, "Querying graph and determiner pipeline...");
      try {{
        const response = await fetch("/api/determinator", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ question, mode }})
        }});
        const data = await response.json();
        if (!response.ok) {{
          throw new Error(data.error || "Determinator request failed.");
        }}
        answerEl.innerHTML = markdownToHtml(data.answer || "No answer returned.");
        metaEl.textContent = [
          data.answer_mode ? `Mode: ${{data.answer_mode}}` : "",
          data.model_used ? `Model: ${{data.model_used}}` : "",
          data.classification_area ? `Area: ${{data.classification_area}}` : "",
          data.used_fallback ? "Fallback used" : "Local grounding only"
        ].filter(Boolean).join(" · ");
        disclaimerEl.textContent = data.disclaimer || "";
        citationsEl.innerHTML = (data.citations || []).length
          ? data.citations.map(citationMarkup).join("")
          : "<div class='citation'><strong>No local citations</strong><p>The determiner did not return any supporting local citation blocks for this query.</p></div>";
        const warnings = data.warnings || [];
        warningsCard.classList.toggle("hidden", !warnings.length);
        warningsEl.textContent = warnings.join("\\n");
        resultEl.classList.remove("hidden");
        setBusy(false, "Completed.");
      }} catch (error) {{
        resultEl.classList.add("hidden");
        errorBox.textContent = error.message || "Unexpected error while querying the determiner.";
        errorBox.classList.remove("hidden");
        setBusy(false, "Failed.");
      }}
    }}

    document.getElementById("runBtn").addEventListener("click", runDeterminator);
    document.getElementById("question").addEventListener("keydown", (event) => {{
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {{
        runDeterminator();
      }}
    }});
  </script>
</body>
</html>"""
