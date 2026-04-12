"""Batch enrichment orchestrator for scaling to 50K+ cases.

Workflow:
  1. Crawl HKLII en-masse per topic from CRIMINAL_AUTHORITY_TREE
  2. Send candidate paragraphs to DeepSeek for principle extraction
  3. Write enrichment candidates to JSON for Codex review
  4. After Codex review, merge verified enrichments into the build
  5. **Discover** — ask DeepSeek what topics/sub-concepts are missing, auto-expand

Usage:
  # Phase 0: discover gaps (DeepSeek reviews tree, suggests missing areas)
  python -m casemap.batch_enrich discover --output data/batch/gap_report.json

  # Phase 1: crawl + DeepSeek enrichment (token-heavy, delegated to DeepSeek)
  python -m casemap.batch_enrich crawl --max-per-topic 50 --output data/batch/candidates.json

  # Phase 2: Codex review (run via Codex task)
  python -m casemap.batch_enrich review --input data/batch/candidates.json --output data/batch/reviewed.json

  # Phase 3: merge verified into enrichment data
  python -m casemap.batch_enrich merge --input data/batch/reviewed.json

  # Full loop: discover → crawl → review → merge (repeat)
  python -m casemap.batch_enrich loop --rounds 3 --max-per-topic 30
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
from datetime import datetime, UTC
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from casemap.criminal_law_data import CRIMINAL_AUTHORITY_TREE
from casemap.hklii_crawler import HKLIICrawler
from casemap.hybrid_graph import _auto_enrich_case_via_llm, _extract_json_payload


# Words to strip from topic search queries before sending to HKLII simplesearch.
# HKLII simplesearch works best with concise legal terms, not full-phrase queries.
_HKLII_NOISE_WORDS = {
    "hksar", "hong", "kong", "criminal", "appeal", "court", "sentence",
    "sentencing", "case", "cases", "law", "ordinance", "section", "cap",
    "judgment", "judgment", "offence", "offences", "offense", "prosecution",
    "conviction", "defendant", "applicant", "respondent", "sfc", "icac",
    "hkcfa", "hkca", "hkcfi", "dc", "v", "vs", "re",
}

def _clean_search_query(query: str) -> str:
    """Strip noise words, keeping the core legal concept (2-3 words max)."""
    words = [w.strip("().,") for w in query.lower().split()]
    core = [w for w in words if w and w not in _HKLII_NOISE_WORDS and len(w) > 2]
    # Return first 2 meaningful words to keep query focused
    return " ".join(core[:2]) if core else query.split()[0]


# ── DeepSeek helper ────────────────────────────────────────────

def _call_deepseek(prompt: str, temperature: float = 0) -> str:
    """Send a prompt to DeepSeek and return the text response."""
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not deepseek_key and not openrouter_key:
        raise RuntimeError("Set DEEPSEEK_API_KEY or OPENROUTER_API_KEY")

    if deepseek_key:
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        api_key = deepseek_key
        model = "deepseek-chat"
    else:
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        api_key = openrouter_key
        model = os.environ.get("OPENROUTER_MODEL", "").strip() or "deepseek/deepseek-chat"

    payload = json.dumps({
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib_request.Request(
        endpoint, data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    def _do(ctx=None):
        kw = {"timeout": 60}
        if ctx is not None:
            kw["context"] = ctx
        with urllib_request.urlopen(req, **kw) as resp:
            return resp.read().decode("utf-8")

    try:
        try:
            raw = _do()
        except (ssl.SSLError, urllib_error.URLError):
            raw = _do(ssl._create_unverified_context())
    except Exception as e:
        raise RuntimeError(f"DeepSeek API call failed: {e}") from e

    parsed = json.loads(raw)
    return parsed.get("choices", [{}])[0].get("message", {}).get("content", "")


# ── Gap discovery ──────────────────────────────────────────────

_DISCOVER_PROMPT = """You are a Hong Kong criminal law expert reviewing a knowledge-graph topic tree.

Below is the CURRENT topic tree (each topic with its case count from HKLII).
Your job: identify MISSING areas of Hong Kong criminal law that should be added.

## Current Topic Tree
{tree_summary}

## Current Coverage Stats
- Total topics: {topic_count}
- Total enriched cases: {case_count}
- Topics with 0 cases: {empty_topics}

## Instructions
1. Identify 5-15 MISSING sub-topics, offence types, or doctrines NOT covered above.
2. For each, provide: a topic ID (snake_case), English label, Chinese label, which existing module/subground it belongs under (or suggest a new one), and 2-3 HKLII search queries.
3. Also identify any existing topics that should be SPLIT into finer sub-concepts.
4. Focus on Hong Kong criminal law. Include: financial crimes, regulatory offences, national security, immigration, intellectual property, triads, gambling, prostitution, perjury, perverting justice, etc.

Return ONLY a JSON object:
{{
  "missing_topics": [
    {{
      "id": "topic_id",
      "label_en": "English Label",
      "label_zh": "中文標籤",
      "parent_module": "existing_module_id or NEW:suggested_module_name",
      "parent_subground": "existing_subground_id or NEW:suggested_subground_name",
      "search_queries": ["query1", "query2"],
      "rationale": "Why this is important and missing"
    }}
  ],
  "split_suggestions": [
    {{
      "existing_topic_id": "id",
      "suggested_splits": ["Sub-topic A", "Sub-topic B"],
      "rationale": "Why this should be split"
    }}
  ]
}}
"""


def _build_tree_summary(candidates_path: str | None = None) -> tuple[str, int, int, list[str]]:
    """Build a text summary of the current topic tree with case counts."""
    # Count cases per topic from candidates file if available
    topic_cases: dict[str, int] = {}
    total_cases = 0
    if candidates_path and Path(candidates_path).exists():
        try:
            data = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
            for c in data.get("candidates", []):
                tid = c.get("topic_id", "unknown")
                topic_cases[tid] = topic_cases.get(tid, 0) + 1
                total_cases += 1
        except Exception:
            pass

    lines = []
    topic_count = 0
    empty_topics = []

    for module in CRIMINAL_AUTHORITY_TREE:
        lines.append(f"\n### {module['label_en']} ({module['id']})")
        for sg in module.get("subgrounds", []):
            lines.append(f"  #### {sg['label_en']} ({sg['id']})")
            for topic in sg.get("topics", []):
                count = topic_cases.get(topic["id"], 0)
                lines.append(f"    - {topic['label_en']} [{topic['id']}] — {count} cases")
                topic_count += 1
                if count == 0:
                    empty_topics.append(topic["label_en"])

    return "\n".join(lines), topic_count, total_cases, empty_topics


def discover_gaps(
    candidates_path: str = "data/batch/candidates.json",
    output_path: str = "data/batch/gap_report.json",
) -> dict:
    """Ask DeepSeek to identify missing topics/areas in the current tree."""
    tree_summary, topic_count, case_count, empty_topics = _build_tree_summary(candidates_path)

    prompt = _DISCOVER_PROMPT.format(
        tree_summary=tree_summary,
        topic_count=topic_count,
        case_count=case_count,
        empty_topics=", ".join(empty_topics[:20]) if empty_topics else "(none)",
    )

    print(f"[discover] Asking DeepSeek to review {topic_count} topics ({case_count} cases)...")
    content = _call_deepseek(prompt)

    # Parse JSON from response
    report = _extract_json_payload(content)
    if not isinstance(report, dict):
        report = {"missing_topics": [], "split_suggestions": [], "raw_response": content}

    report["meta"] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "topic_count": topic_count,
        "case_count": case_count,
        "empty_topics_count": len(empty_topics),
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    missing = report.get("missing_topics", [])
    splits = report.get("split_suggestions", [])
    print(f"[discover] Found {len(missing)} missing topics, {len(splits)} split suggestions")
    for m in missing:
        print(f"  + {m.get('label_en', '?')} → {m.get('parent_module', '?')}/{m.get('parent_subground', '?')}")
    for s in splits:
        print(f"  ✂ {s.get('existing_topic_id', '?')} → {s.get('suggested_splits', [])}")

    print(f"[discover] Report written to {output_path}")
    return report


def apply_discovered_topics(
    gap_report_path: str = "data/batch/gap_report.json",
    output_path: str = "data/batch/new_topics_applied.json",
) -> list[dict]:
    """Apply discovered missing topics as synthetic entries for the next crawl round.

    This does NOT modify criminal_law_data.py directly — it writes a supplementary
    topics file that the crawler reads alongside the main tree. Codex reviews the
    gap report and decides which to keep permanently.
    """
    report = json.loads(Path(gap_report_path).read_text(encoding="utf-8"))
    missing = report.get("missing_topics", [])

    if not missing:
        print("[apply] No missing topics to apply")
        return []

    # Validate each suggested topic has minimum required fields
    valid = []
    for m in missing:
        if not m.get("id") or not m.get("label_en") or not m.get("search_queries"):
            continue
        valid.append({
            "id": m["id"],
            "label_en": m["label_en"],
            "label_zh": m.get("label_zh", ""),
            "search_queries": m["search_queries"][:3],
            "parent_module": m.get("parent_module", ""),
            "parent_subground": m.get("parent_subground", ""),
            "source": "deepseek_discovery",
            "discovered_at": datetime.now(UTC).isoformat(),
        })

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(valid, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[apply] {len(valid)} new topics ready for next crawl round → {output_path}")
    return valid


def run_loop(
    rounds: int = 3,
    max_per_topic: int = 30,
    candidates_path: str = "data/batch/candidates.json",
    gap_report_path: str = "data/batch/gap_report.json",
):
    """Full self-improving loop: discover → crawl → discover → crawl ..."""
    for r in range(1, rounds + 1):
        print(f"\n{'='*60}")
        print(f"  ROUND {r}/{rounds}")
        print(f"{'='*60}")

        # Step 1: Discover gaps
        print(f"\n[round {r}] Phase: DISCOVER")
        report = discover_gaps(candidates_path=candidates_path, output_path=gap_report_path)

        # Step 2: Apply discovered topics as supplementary search targets
        new_topics = apply_discovered_topics(gap_report_path=gap_report_path)

        # Step 3: Crawl — both existing tree topics AND newly discovered ones
        print(f"\n[round {r}] Phase: CRAWL ({len(new_topics)} new topics added)")
        crawl_and_enrich(
            max_per_topic=max_per_topic,
            output_path=candidates_path,
            extra_topics=new_topics,
        )

        # Summary
        if Path(candidates_path).exists():
            data = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
            total = len(data.get("candidates", []))
            print(f"\n[round {r}] Total candidates after round: {total}")

    print(f"\n{'='*60}")
    print(f"  LOOP COMPLETE — {rounds} rounds finished")
    print(f"  Run 'review' to generate Codex task, then 'merge' after review.")
    print(f"{'='*60}")


def _iter_topics():
    """Yield (module_id, subground_id, topic) for every topic in the tree."""
    for module in CRIMINAL_AUTHORITY_TREE:
        for subground in module.get("subgrounds", []):
            for topic in subground.get("topics", []):
                yield module["id"], subground["id"], topic


def crawl_and_enrich(
    max_per_topic: int = 50,
    output_path: str = "data/batch/candidates.json",
    delay_between_topics: float = 1.0,
    skip_existing: bool = True,
    extra_topics: list[dict] | None = None,
) -> dict:
    """Phase 1: Crawl HKLII for each topic, enrich via DeepSeek, write candidates."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Load existing to allow incremental runs
    existing: dict[str, dict] = {}
    if skip_existing and output.exists():
        try:
            data = json.loads(output.read_text(encoding="utf-8"))
            existing = {c["neutral_citation"]: c for c in data.get("candidates", []) if c.get("neutral_citation")}
            print(f"[resume] Loaded {len(existing)} existing candidates from {output_path}")
        except Exception:
            pass

    crawler = HKLIICrawler()
    candidates: list[dict] = list(existing.values())
    stats = {"topics_processed": 0, "cases_crawled": 0, "cases_enriched": 0, "errors": 0}

    topics = list(_iter_topics())

    # Append any dynamically discovered topics from the discover phase
    if extra_topics:
        for et in extra_topics:
            module_id = et.get("parent_module", "discovered")
            subground_id = et.get("parent_subground", "discovered")
            topics.append((module_id, subground_id, et))

    print(f"[batch] Processing {len(topics)} topics, max {max_per_topic} cases each")

    for module_id, subground_id, topic in topics:
        topic_id = topic["id"]
        topic_label = topic["label_en"]
        queries = topic.get("search_queries", [])
        if not queries:
            continue

        print(f"\n--- Topic: {topic_label} ({topic_id}) ---")
        stats["topics_processed"] += 1

        # Crawl HKLII for this topic
        seen_citations: set[str] = set()
        topic_cases: list = []

        for query in queries:
            if len(topic_cases) >= max_per_topic:
                break
            clean_query = _clean_search_query(query)
            try:
                results = crawler.simple_search(clean_query, limit=max_per_topic)
                for result in results:
                    path = result.path
                    if not path or path in seen_citations:
                        continue
                    seen_citations.add(path)
                    if len(topic_cases) >= max_per_topic:
                        break

                    # Check if already enriched
                    title = result.title
                    if title in existing or path in existing:
                        continue

                    topic_cases.append({"path": path, "title": title, "query": query})
                    stats["cases_crawled"] += 1
            except Exception as e:
                print(f"  [warn] Search failed for '{query}': {e}")
                stats["errors"] += 1
                continue

        # Fetch and enrich each case via DeepSeek
        for case_info in topic_cases:
            path = case_info["path"]
            try:
                docs = crawler.crawl_paths([path])
                if not docs:
                    continue

                doc = docs[0]
                nc = doc.neutral_citation or ""
                if nc in existing:
                    continue

                # Send to DeepSeek for enrichment
                paragraphs = [{"text": p.text, "paragraph_span": p.paragraph_span} for p in doc.paragraphs]
                if not paragraphs:
                    continue

                enrichment = _auto_enrich_case_via_llm(
                    case_name=doc.case_name,
                    neutral_citation=nc,
                    paragraphs=paragraphs,
                )

                candidate = {
                    "neutral_citation": nc,
                    "case_name": doc.case_name,
                    "court_code": doc.court_name or "",
                    "decision_date": doc.decision_date or "",
                    "judges": doc.judges or [],
                    "source_url": f"https://www.hklii.hk{path}" if path.startswith("/") else path,
                    "topic_id": topic_id,
                    "topic_label": topic_label,
                    "module_id": module_id,
                    "subground_id": subground_id,
                    "principles": enrichment.get("principles", []),
                    "relationships": enrichment.get("relationships", []),
                    "assignment_confidence": 0.6,
                    "assignment_status": "candidate",
                    "review_status": "pending",  # pending / verified / rejected
                    "review_notes": "",
                    "enriched_at": datetime.now(UTC).isoformat(),
                    "paragraph_count": len(paragraphs),
                }

                candidates.append(candidate)
                existing[nc] = candidate
                stats["cases_enriched"] += 1
                print(f"  [ok] {nc}: {doc.case_name[:50]} -> {len(enrichment.get('principles', []))} principles")

            except Exception as e:
                print(f"  [err] {path}: {e}")
                stats["errors"] += 1
                continue

        # Save after each topic (crash-safe)
        _save_candidates(candidates, stats, output)
        time.sleep(delay_between_topics)

    _save_candidates(candidates, stats, output)
    print(f"\n[done] {json.dumps(stats, indent=2)}")
    return stats


def _save_candidates(candidates: list[dict], stats: dict, output: Path):
    """Write candidates to disk atomically."""
    payload = {
        "meta": {
            "generated_at": datetime.now(UTC).isoformat(),
            "stats": stats,
        },
        "candidates": candidates,
    }
    tmp = output.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(output)


def generate_codex_review(
    input_path: str = "data/batch/candidates.json",
    output_path: str = "data/batch/codex_review_task.md",
    batch_size: int = 30,
):
    """Phase 2: Generate a Codex task markdown that reviews candidate enrichments."""
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    candidates = [c for c in data.get("candidates", []) if c.get("review_status") == "pending"]

    if not candidates:
        print("[review] No pending candidates to review")
        return

    # Take a batch
    batch = candidates[:batch_size]
    print(f"[review] Generating Codex review task for {len(batch)} candidates")

    lines = [
        "# Codex Review Task: Batch Enrichment Validation",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}",
        f"**Batch size:** {len(batch)} candidates",
        "",
        "## Instructions",
        "",
        "For each case below, verify:",
        "1. **Topic assignment** — Does the case genuinely belong to the assigned topic?",
        "2. **Principles** — Are the extracted legal principles accurate and non-hallucinated?",
        "3. **Paragraph spans** — Do the paragraph references exist in the case?",
        "4. **Relationships** — Are case-law relationships (FOLLOWS, APPLIES, etc.) correct?",
        "",
        "For each case, set `review_status` to `verified` or `rejected` and add `review_notes`.",
        "",
        "## Output Format",
        "",
        "Write a JSON file `data/batch/reviewed.json` with the same structure as the input,",
        "but with `review_status` and `review_notes` updated for each candidate.",
        "",
        "---",
        "",
    ]

    for i, c in enumerate(batch):
        lines.append(f"### Case {i+1}: {c.get('case_name', 'Unknown')}")
        lines.append(f"- **Citation:** {c.get('neutral_citation', '')}")
        lines.append(f"- **Assigned Topic:** {c.get('topic_label', '')} (`{c.get('topic_id', '')}`)")
        lines.append(f"- **Source:** {c.get('source_url', '')}")
        lines.append(f"- **Principles ({len(c.get('principles', []))}):**")
        for j, p in enumerate(c.get("principles", [])[:5]):
            label = p.get("principle_label", p.get("label_en", ""))
            span = p.get("paragraph_span", "")
            lines.append(f"  {j+1}. `{label}` (para {span})")
        if c.get("relationships"):
            lines.append(f"- **Relationships ({len(c.get('relationships', []))}):**")
            for r in c.get("relationships", [])[:3]:
                lines.append(f"  - {r.get('type', '')}: {r.get('target_label', '')}")
        lines.append(f"- **review_status:** `pending`")
        lines.append(f"- **review_notes:** ")
        lines.append("")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"[review] Written Codex task to {output_path}")


def merge_reviewed(
    input_path: str = "data/batch/reviewed.json",
    enrichment_file: str = "src/casemap/criminal_enrichment_data.py",
):
    """Phase 3: Merge verified enrichments into curated data."""
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    verified = [c for c in data.get("candidates", []) if c.get("review_status") == "verified"]

    if not verified:
        print("[merge] No verified candidates to merge")
        return

    # Generate Python dict entries for each verified case
    entries = []
    for c in verified:
        entry = {
            "neutral_citation": c["neutral_citation"],
            "case_name": c.get("case_name", ""),
            "court_code": c.get("court_code", ""),
            "decision_date": c.get("decision_date", ""),
            "summary_en": "",
            "summary_zh": "",
            "topic_hints": [c.get("topic_label", "")],
            "principles": c.get("principles", []),
            "relationships": c.get("relationships", []),
            "source": "batch_enrichment_verified",
        }
        entries.append(entry)

    # Write to a separate file that can be imported
    output_path = "src/casemap/batch_enrichment_data.py"
    lines = [
        "\"\"\"Auto-generated verified batch enrichments. Do not edit manually.\"\"\"",
        "from __future__ import annotations",
        "",
        f"# Generated: {datetime.now(UTC).isoformat()}",
        f"# Verified cases: {len(entries)}",
        "",
        "BATCH_ENRICHMENTS: list[dict] = " + json.dumps(entries, indent=4, ensure_ascii=False),
    ]
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"[merge] Written {len(entries)} verified enrichments to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch enrichment pipeline")
    sub = parser.add_subparsers(dest="command")

    # discover
    disc_p = sub.add_parser("discover", help="Ask DeepSeek to find missing topics")
    disc_p.add_argument("--candidates", default="data/batch/candidates.json")
    disc_p.add_argument("--output", default="data/batch/gap_report.json")

    # apply
    apply_p = sub.add_parser("apply", help="Apply discovered topics for next crawl")
    apply_p.add_argument("--input", default="data/batch/gap_report.json")
    apply_p.add_argument("--output", default="data/batch/new_topics_applied.json")

    # crawl
    crawl_p = sub.add_parser("crawl", help="Crawl HKLII + enrich via DeepSeek")
    crawl_p.add_argument("--max-per-topic", type=int, default=50)
    crawl_p.add_argument("--output", default="data/batch/candidates.json")
    crawl_p.add_argument("--delay", type=float, default=1.0)
    crawl_p.add_argument("--extra-topics", default="", help="Path to extra topics JSON from discover phase")

    # review
    review_p = sub.add_parser("review", help="Generate Codex review task")
    review_p.add_argument("--input", default="data/batch/candidates.json")
    review_p.add_argument("--output", default="data/batch/codex_review_task.md")
    review_p.add_argument("--batch-size", type=int, default=30)

    # merge
    merge_p = sub.add_parser("merge", help="Merge Codex-reviewed enrichments")
    merge_p.add_argument("--input", default="data/batch/reviewed.json")

    # loop
    loop_p = sub.add_parser("loop", help="Full self-improving loop: discover → crawl → repeat")
    loop_p.add_argument("--rounds", type=int, default=3)
    loop_p.add_argument("--max-per-topic", type=int, default=30)
    loop_p.add_argument("--candidates", default="data/batch/candidates.json")

    args = parser.parse_args()
    if args.command == "discover":
        discover_gaps(candidates_path=args.candidates, output_path=args.output)
    elif args.command == "apply":
        apply_discovered_topics(gap_report_path=args.input, output_path=args.output)
    elif args.command == "crawl":
        extra = []
        if args.extra_topics and Path(args.extra_topics).exists():
            extra = json.loads(Path(args.extra_topics).read_text(encoding="utf-8"))
        crawl_and_enrich(
            max_per_topic=args.max_per_topic,
            output_path=args.output,
            delay_between_topics=args.delay,
            extra_topics=extra or None,
        )
    elif args.command == "review":
        generate_codex_review(
            input_path=args.input,
            output_path=args.output,
            batch_size=args.batch_size,
        )
    elif args.command == "merge":
        merge_reviewed(input_path=args.input)
    elif args.command == "loop":
        run_loop(
            rounds=args.rounds,
            max_per_topic=args.max_per_topic,
            candidates_path=args.candidates,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
