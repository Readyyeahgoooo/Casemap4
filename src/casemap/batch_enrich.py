"""Batch enrichment orchestrator for scaling to 50K+ cases.

Workflow:
  1. Crawl HKLII en-masse per topic from a domain authority tree
  2. Send candidate paragraphs to DeepSeek for principle extraction
  3. Write enrichment candidates to JSON for Codex review
  4. After Codex review, merge verified enrichments into the build
  5. **Discover** — ask DeepSeek what topics/sub-concepts are missing, auto-expand

Usage:
  # Phase 0: discover gaps (DeepSeek reviews tree, suggests missing areas)
  python -m casemap.batch_enrich discover --domain criminal --output data/batch/gap_report.json

  # Phase 1: crawl + DeepSeek enrichment (token-heavy, delegated to DeepSeek)
  python -m casemap.batch_enrich crawl --domain criminal --max-per-topic 50 --output data/batch/candidates.json

  # Phase 2: Codex review (run via Codex task)
  python -m casemap.batch_enrich review --domain criminal --input data/batch/candidates.json --output data/batch/reviewed.json

  # Phase 3: merge verified into enrichment data
  python -m casemap.batch_enrich merge --domain criminal --input data/batch/reviewed.json

  # Full loop: discover → crawl → review → merge (repeat)
  python -m casemap.batch_enrich loop --domain criminal --rounds 3 --max-per-topic 30
"""
from __future__ import annotations

import argparse
import json
import os
import re
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

from casemap.domain_classifier import classification_matches_target, classify_domain_rules
from casemap.domain_filter import run_domain_filter
from casemap.domain_graph import default_domain_label, iter_domain_topics, load_domain_tree, normalize_domain_id
from casemap.hklii_crawler import HKLIICrawler
from casemap.hybrid_graph import _auto_enrich_case_via_llm, _extract_json_payload


# Words to strip from topic search queries before sending to HKLII simplesearch.
# HKLII simplesearch works best with concise legal terms, not full-phrase queries.
_HKLII_NOISE_WORDS = {
    "a", "an", "and", "are", "be", "been", "being", "by", "for", "from",
    "how", "i", "if", "in", "is", "it", "its", "my", "of", "on", "one",
    "or", "own", "s", "the", "their", "to", "was", "were", "what", "when",
    "where", "which", "who", "why", "with",
    "hksar", "hong", "kong", "criminal", "appeal", "court", "sentence",
    "sentencing", "case", "cases", "law", "ordinance", "section", "cap",
    "judgment", "judgment", "legal", "liability", "consequence", "penalty",
    "offence", "offences", "offense", "prosecution",
    "conviction", "defendant", "applicant", "respondent", "sfc", "icac",
    "hkcfa", "hkca", "hkcfi", "dc", "v", "vs", "re",
}


def _clean_search_query(query: str) -> str:
    """Strip noise words, keeping the core legal concept (2-3 words max)."""
    words = re.findall(r"[a-z0-9]+", query.lower())
    core = [w for w in words if w and w not in _HKLII_NOISE_WORDS and len(w) > 2]
    return " ".join(core[:2]) if core else query.split()[0]


def _search_query_variants(query: str) -> list[str]:
    """Return concise HKLII search variants, most-specific first."""
    clean_query = _clean_search_query(query)
    variants = [clean_query]
    lowered = query.lower()

    if any(term in lowered for term in ("animal", "dog", "cat", "pet", "cruelty")):
        variants.extend(["animal cruelty", "unnecessary suffering"])

    first_word = clean_query.split()[0] if clean_query else ""
    if first_word:
        variants.append(first_word)

    deduped: list[str] = []
    for variant in variants:
        if variant and variant not in deduped:
            deduped.append(variant)
    return deduped


def _domain_text_snippet(case_name: str, paragraphs: list[dict], principles: list[dict] | None = None) -> str:
    """Build a small rule-classifier snippet without sending extra LLM calls."""
    parts = [case_name]
    for principle in (principles or [])[:3]:
        parts.append(principle.get("principle_label", ""))
        parts.append(principle.get("label_en", ""))
        parts.append(principle.get("paraphrase_en", ""))
        parts.append(principle.get("public_excerpt", ""))
    for paragraph in paragraphs[:5]:
        parts.append(paragraph.get("text", ""))
    return " ".join(part for part in parts if part)[:5000]


def _classify_candidate_domain(
    case_name: str,
    neutral_citation: str,
    paragraphs: list[dict],
    principles: list[dict] | None = None,
) -> dict:
    statutes_cited: list[str] = []
    for principle in principles or []:
        statutes_cited.extend(str(item) for item in principle.get("cited_statutes", []) or [])
    return classify_domain_rules(
        case_name=case_name,
        neutral_citation=neutral_citation,
        text_snippet=_domain_text_snippet(case_name, paragraphs, principles),
        statutes_cited=statutes_cited,
    )


def _is_quarantined(candidate: dict, target_domain: str = "criminal") -> bool:
    if candidate.get("enrichment_status") == "quarantined":
        classification = candidate.get("domain_classification") or {}
        return not classification_matches_target(classification, target_domain)
    classification = candidate.get("domain_classification") or {}
    domain = classification.get("domain")
    confidence = float(classification.get("confidence") or 0)
    return bool(domain and not classification_matches_target(classification, target_domain) and confidence >= 0.6)


def _is_classified_non_target(candidate: dict, target_domain: str = "criminal") -> bool:
    if candidate.get("enrichment_status") == "quarantined":
        classification = candidate.get("domain_classification") or {}
        return not classification_matches_target(classification, target_domain)
    classification = candidate.get("domain_classification") or {}
    domain = classification.get("domain")
    return bool(domain and not classification_matches_target(classification, target_domain))


def _summarize_domains(candidates: list[dict]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for candidate in candidates:
        classification = candidate.get("domain_classification") or {}
        domain = classification.get("domain") or "unclassified"
        summary[domain] = summary.get(domain, 0) + 1
    return dict(sorted(summary.items(), key=lambda item: (-item[1], item[0])))


# ── DeepSeek helper ────────────────────────────────────────────

def _call_deepseek(prompt: str, temperature: float = 0, timeout: int = 180, retries: int = 3) -> str:
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
        kw = {"timeout": timeout}
        if ctx is not None:
            kw["context"] = ctx
        with urllib_request.urlopen(req, **kw) as resp:
            return resp.read().decode("utf-8")

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            try:
                raw = _do()
            except (ssl.SSLError, urllib_error.URLError):
                raw = _do(ssl._create_unverified_context())
            break
        except Exception as e:
            last_error = e
            if attempt >= retries:
                raise RuntimeError(f"DeepSeek API call failed after {retries} attempts: {e}") from e
            wait_seconds = min(10 * attempt, 30)
            print(f"[warn] DeepSeek call failed on attempt {attempt}/{retries}: {e}; retrying in {wait_seconds}s")
            time.sleep(wait_seconds)
    else:
        raise RuntimeError(f"DeepSeek API call failed: {last_error}")

    parsed = json.loads(raw)
    return parsed.get("choices", [{}])[0].get("message", {}).get("content", "")


# ── Gap discovery ──────────────────────────────────────────────

_DISCOVER_PROMPT = """You are a {domain_label} expert reviewing a knowledge-graph topic tree.

Below is the CURRENT topic tree (each topic with its case count from HKLII).
Your job: identify MISSING areas of {domain_label} that should be added.

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
4. Focus only on the {domain_label} domain (`{domain_id}`). Avoid turning this into a general legal-domain catch-all.

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


def _build_tree_summary(
    candidates_path: str | None = None,
    *,
    domain_id: str = "criminal",
    tree_path: str | Path | None = None,
) -> tuple[str, int, int, list[str]]:
    """Build a text summary of the current topic tree with case counts."""
    domain_id = normalize_domain_id(domain_id)
    tree = load_domain_tree(domain_id, tree_path)

    # Count cases per topic from candidates file if available
    topic_cases: dict[str, int] = {}
    total_cases = 0
    if candidates_path and Path(candidates_path).exists():
        try:
            data = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
            for c in data.get("candidates", []):
                if _is_classified_non_target(c, target_domain=domain_id):
                    continue
                tid = c.get("topic_id", "unknown")
                topic_cases[tid] = topic_cases.get(tid, 0) + 1
                total_cases += 1
        except Exception:
            pass

    lines = []
    topic_count = 0
    empty_topics = []

    for module in tree["modules"]:
        module_id = module.get("id", "")
        lines.append(f"\n### {module.get('label_en', module_id)} ({module_id})")
        for sg in module.get("subgrounds", []):
            subground_id = sg.get("id", "")
            lines.append(f"  #### {sg.get('label_en', subground_id)} ({subground_id})")
            for topic in sg.get("topics", []):
                topic_id = topic.get("id", "")
                count = topic_cases.get(topic_id, 0)
                lines.append(f"    - {topic.get('label_en', topic_id)} [{topic_id}] — {count} cases")
                topic_count += 1
                if count == 0:
                    empty_topics.append(topic.get("label_en", topic_id))

    return "\n".join(lines), topic_count, total_cases, empty_topics


def discover_gaps(
    candidates_path: str = "data/batch/candidates.json",
    output_path: str = "data/batch/gap_report.json",
    domain_id: str = "criminal",
    tree_path: str | Path | None = None,
) -> dict:
    """Ask DeepSeek to identify missing topics/areas in the current tree."""
    domain_id = normalize_domain_id(domain_id)
    domain_label = default_domain_label(domain_id)
    tree_summary, topic_count, case_count, empty_topics = _build_tree_summary(
        candidates_path,
        domain_id=domain_id,
        tree_path=tree_path,
    )

    prompt = _DISCOVER_PROMPT.format(
        domain_id=domain_id,
        domain_label=domain_label,
        tree_summary=tree_summary,
        topic_count=topic_count,
        case_count=case_count,
        empty_topics=", ".join(empty_topics[:20]) if empty_topics else "(none)",
    )

    # Skip if a fresh report already exists (generated within last 12 hours).
    if Path(output_path).exists():
        try:
            existing = json.loads(Path(output_path).read_text(encoding="utf-8"))
            generated_at = existing.get("meta", {}).get("generated_at", "")
            if generated_at:
                age = (datetime.now(UTC) - datetime.fromisoformat(generated_at)).total_seconds()
                if age < 43200:
                    print(f"[discover] Reusing existing report (generated {int(age/60)} min ago) — {output_path}")
                    return existing
        except Exception:
            pass

    print(f"[discover] Asking DeepSeek to review {topic_count} topics ({case_count} cases)...")
    content = _call_deepseek(prompt)

    # Parse JSON from response
    report = _extract_json_payload(content)
    if not isinstance(report, dict):
        report = {"missing_topics": [], "split_suggestions": [], "raw_response": content}

    report["meta"] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": domain_id,
        "tree_path": str(tree_path) if tree_path else "",
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

    This does NOT modify source authority-tree data directly — it writes a supplementary
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
    domain_id: str = "criminal",
    tree_path: str | Path | None = None,
):
    """Full self-improving loop: discover → crawl → discover → crawl ..."""
    domain_id = normalize_domain_id(domain_id)
    for r in range(1, rounds + 1):
        print(f"\n{'='*60}")
        print(f"  ROUND {r}/{rounds}")
        print(f"{'='*60}")

        # Step 1: Discover gaps
        print(f"\n[round {r}] Phase: DISCOVER")
        try:
            report = discover_gaps(
                candidates_path=candidates_path,
                output_path=gap_report_path,
                domain_id=domain_id,
                tree_path=tree_path,
            )
        except RuntimeError as e:
            if not Path(gap_report_path).exists():
                raise
            print(f"[warn] Discovery failed: {e}")
            print(f"[warn] Reusing existing gap report: {gap_report_path}")
            report = json.loads(Path(gap_report_path).read_text(encoding="utf-8"))

        # Step 2: Apply discovered topics as supplementary search targets
        new_topics = apply_discovered_topics(gap_report_path=gap_report_path)

        # Step 3: Crawl — both existing tree topics AND newly discovered ones
        print(f"\n[round {r}] Phase: CRAWL ({len(new_topics)} new topics added)")
        crawl_and_enrich(
            max_per_topic=max_per_topic,
            output_path=candidates_path,
            domain_id=domain_id,
            tree_path=tree_path,
            extra_topics=new_topics,
        )

        # Summary
        if Path(candidates_path).exists():
            data = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
            candidates = data.get("candidates", [])
            total = len(candidates)
            print(f"\n[round {r}] Total candidates after round: {total}")
            print(f"[round {r}] Domain distribution: {json.dumps(_summarize_domains(candidates), ensure_ascii=False)}")

    print(f"\n{'='*60}")
    print(f"  LOOP COMPLETE — {rounds} rounds finished")
    print(f"  Run 'review' to generate Codex task, then 'merge' after review.")
    print(f"{'='*60}")


def _iter_topics(tree: dict | None = None, domain_id: str = "criminal", tree_path: str | Path | None = None):
    """Yield (module_id, subground_id, topic) for every topic in the tree."""
    tree = tree or load_domain_tree(domain_id, tree_path)
    for topic in iter_domain_topics(tree):
        yield topic["module_id"], topic["subground_id"], topic


def _candidate_index_keys(candidate: dict) -> set[str]:
    keys: set[str] = set()
    for key in ("neutral_citation", "case_name", "source_url"):
        value = str(candidate.get(key) or "").strip()
        if value:
            keys.add(value)
            keys.add(value.lower())
            if value.startswith("https://www.hklii.hk/"):
                keys.add(value.replace("https://www.hklii.hk", "", 1))
    return keys


def _add_cross_reference(candidate: dict, *, domain_id: str, module_id: str, subground_id: str, topic: dict, query: str = "") -> bool:
    refs = candidate.setdefault("cross_references", [])
    ref = {
        "domain": normalize_domain_id(domain_id),
        "module_id": module_id,
        "subground_id": subground_id,
        "topic_id": topic.get("id", ""),
        "topic_label": topic.get("label_en", ""),
        "query": query,
    }
    key = (ref["domain"], ref["topic_id"], ref["query"])
    for existing in refs:
        if (existing.get("domain"), existing.get("topic_id"), existing.get("query", "")) == key:
            return False
    refs.append(ref)
    return True


def crawl_and_enrich(
    max_per_topic: int = 50,
    output_path: str = "data/batch/candidates.json",
    delay_between_topics: float = 1.0,
    skip_existing: bool = True,
    extra_topics: list[dict] | None = None,
    domain_id: str = "criminal",
    tree_path: str | Path | None = None,
) -> dict:
    """Phase 1: Crawl HKLII for each topic, enrich via DeepSeek, write candidates."""
    domain_id = normalize_domain_id(domain_id)
    tree = load_domain_tree(domain_id, tree_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Load existing to allow incremental runs
    existing: dict[str, dict] = {}
    existing_by_key: dict[str, dict] = {}
    loaded_candidates: list[dict] = []
    if skip_existing and output.exists():
        try:
            data = json.loads(output.read_text(encoding="utf-8"))
            loaded_candidates = list(data.get("candidates", []))
            existing = {c["neutral_citation"]: c for c in loaded_candidates if c.get("neutral_citation")}
            for candidate in loaded_candidates:
                for key in _candidate_index_keys(candidate):
                    existing_by_key[key] = candidate
            print(f"[resume] Loaded {len(existing)} existing candidates from {output_path}")
        except Exception:
            pass

    crawler = HKLIICrawler()
    candidates: list[dict] = loaded_candidates or list(existing.values())
    stats = {
        "topics_processed": 0,
        "cases_crawled": 0,
        "cases_enriched": 0,
        "quarantined_count": 0,
        "cross_references_added": 0,
        "target_domain": domain_id,
        "domain_breakdown": {},
        "errors": 0,
    }

    topics = list(_iter_topics(tree=tree, domain_id=domain_id, tree_path=tree_path))

    # Append any dynamically discovered topics from the discover phase
    if extra_topics:
        for et in extra_topics:
            module_id = et.get("parent_module", "discovered")
            subground_id = et.get("parent_subground", "discovered")
            topics.append((module_id, subground_id, et))

    print(f"[batch] Processing {len(topics)} {domain_id} topics, max {max_per_topic} cases each")

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
            try:
                results = []
                for search_query in _search_query_variants(query):
                    results.extend(crawler.simple_search(search_query, limit=max_per_topic))
                for result in results:
                    path = result.path
                    if not path or path in seen_citations:
                        continue
                    seen_citations.add(path)
                    if len(topic_cases) >= max_per_topic:
                        break

                    # Check if already enriched
                    title = result.title
                    existing_candidate = (
                        existing_by_key.get(title)
                        or existing_by_key.get(title.lower())
                        or existing_by_key.get(path)
                        or existing_by_key.get(f"https://www.hklii.hk{path}")
                    )
                    if existing_candidate:
                        if _add_cross_reference(
                            existing_candidate,
                            domain_id=domain_id,
                            module_id=module_id,
                            subground_id=subground_id,
                            topic=topic,
                            query=query,
                        ):
                            stats["cross_references_added"] += 1
                        continue
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
                existing_candidate = (
                    (existing.get(nc) if nc else None)
                    or (existing_by_key.get(nc) if nc else None)
                    or existing_by_key.get(doc.case_name.lower())
                )
                if existing_candidate:
                    if _add_cross_reference(
                        existing_candidate,
                        domain_id=domain_id,
                        module_id=module_id,
                        subground_id=subground_id,
                        topic=topic,
                        query=case_info.get("query", ""),
                    ):
                        stats["cross_references_added"] += 1
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
                principles = enrichment.get("principles", [])
                domain_classification = _classify_candidate_domain(
                    case_name=doc.case_name,
                    neutral_citation=nc,
                    paragraphs=paragraphs,
                    principles=principles,
                )
                domain = domain_classification.get("domain", "unknown")
                stats["domain_breakdown"][domain] = stats["domain_breakdown"].get(domain, 0) + 1
                is_quarantined = (
                    not classification_matches_target(domain_classification, domain_id)
                    and float(domain_classification.get("confidence") or 0) >= 0.6
                )
                if is_quarantined:
                    stats["quarantined_count"] += 1
                    domain_classification["quarantine_reason"] = "non_target_inline_rule"

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
                    "principles": principles,
                    "relationships": enrichment.get("relationships", []),
                    "assignment_confidence": 0.6,
                    "assignment_status": "candidate",
                    "enrichment_status": "quarantined" if is_quarantined else "candidate",
                    "domain_classification": domain_classification,
                    "target_domain": domain_id,
                    "cross_references": [],
                    "review_status": "pending",  # pending / verified / rejected
                    "review_notes": "",
                    "enriched_at": datetime.now(UTC).isoformat(),
                    "paragraph_count": len(paragraphs),
                }

                candidates.append(candidate)
                if nc:
                    existing[nc] = candidate
                for key in _candidate_index_keys(candidate):
                    existing_by_key[key] = candidate
                stats["cases_enriched"] += 1
                status = "quarantine" if is_quarantined else "ok"
                print(f"  [{status}] {nc}: {doc.case_name[:50]} -> {len(principles)} principles ({domain})")
                _save_candidates(candidates, stats, output)

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
    neutral_citation_index = {
        c["neutral_citation"]: index
        for index, c in enumerate(candidates)
        if c.get("neutral_citation")
    }
    payload = {
        "meta": {
            "generated_at": datetime.now(UTC).isoformat(),
            "stats": stats,
            "neutral_citation_index": neutral_citation_index,
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
    target_domain: str = "criminal",
):
    """Phase 2: Generate a Codex task markdown that reviews candidate enrichments."""
    target_domain = normalize_domain_id(target_domain)
    if input_path == "data/batch/candidates.json":
        clean_path = Path(f"data/batch/candidates_{target_domain}_clean.json")
        if clean_path.exists():
            input_path = str(clean_path)
            print(f"[review] Using domain-filtered input: {input_path}")

    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    all_candidates = data.get("candidates", [])
    quarantined = [c for c in all_candidates if _is_quarantined(c, target_domain=target_domain)]
    candidates = [
        c for c in all_candidates
        if c.get("review_status") == "pending" and not _is_quarantined(c, target_domain=target_domain)
    ]
    if quarantined:
        print(f"[review] Skipping {len(quarantined)} quarantined/non-{target_domain} candidates")

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
    enrichment_file: str | None = None,
    target_domain: str = "criminal",
):
    """Phase 3: Merge verified enrichments into curated data."""
    target_domain = normalize_domain_id(target_domain)
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    verified = []
    skipped_domain = 0
    for candidate in data.get("candidates", []):
        if candidate.get("review_status") != "verified":
            continue
        if _is_quarantined(candidate, target_domain=target_domain):
            skipped_domain += 1
            continue
        classification = candidate.get("domain_classification") or {}
        if classification.get("domain") and not classification_matches_target(classification, target_domain):
            skipped_domain += 1
            continue
        verified.append(candidate)

    if not verified:
        if skipped_domain:
            print(f"[merge] Skipped {skipped_domain} verified candidates outside {target_domain} domain")
        print("[merge] No verified candidates to merge")
        return
    if skipped_domain:
        print(f"[merge] Skipped {skipped_domain} verified candidates outside {target_domain} domain")

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

    # Write to a separate file that can be imported. Do not clobber curated
    # hand-written enrichment modules unless the caller explicitly passes a path.
    output_path = enrichment_file or f"src/casemap/{target_domain}_enrichment_data.py"
    output = Path(output_path)
    if enrichment_file is None and output.exists():
        existing_text = output.read_text(encoding="utf-8")
        if "Auto-generated verified batch enrichments" not in existing_text:
            output_path = f"src/casemap/{target_domain}_batch_enrichment_data.py"
            output = Path(output_path)
    lines = [
        "\"\"\"Auto-generated verified batch enrichments. Do not edit manually.\"\"\"",
        "from __future__ import annotations",
        "",
        f"# Generated: {datetime.now(UTC).isoformat()}",
        f"# Domain: {target_domain}",
        f"# Verified cases: {len(entries)}",
        "",
        "BATCH_ENRICHMENTS: list[dict] = " + json.dumps(entries, indent=4, ensure_ascii=False),
    ]
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"[merge] Written {len(entries)} verified enrichments to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch enrichment pipeline")
    sub = parser.add_subparsers(dest="command")

    # discover
    disc_p = sub.add_parser("discover", help="Ask DeepSeek to find missing topics")
    disc_p.add_argument("--candidates", default="data/batch/candidates.json")
    disc_p.add_argument("--output", default="data/batch/gap_report.json")
    disc_p.add_argument("--domain", default="criminal", help="Target legal domain to analyze")
    disc_p.add_argument("--tree", default="", help="Optional JSON authority tree path")

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
    crawl_p.add_argument("--domain", default="criminal", help="Target legal domain to crawl")
    crawl_p.add_argument("--tree", default="", help="Optional JSON authority tree path")

    # review
    review_p = sub.add_parser("review", help="Generate Codex review task")
    review_p.add_argument("--input", default="data/batch/candidates.json")
    review_p.add_argument("--output", default="data/batch/codex_review_task.md")
    review_p.add_argument("--batch-size", type=int, default=30)
    review_p.add_argument("--domain", default="criminal", help="Target legal domain to review")

    # merge
    merge_p = sub.add_parser("merge", help="Merge Codex-reviewed enrichments")
    merge_p.add_argument("--input", default="data/batch/reviewed.json")
    merge_p.add_argument("--domain", default="criminal", help="Target legal domain to merge")
    merge_p.add_argument("--output", default="", help="Optional enrichment Python output path")

    # classify-domains
    classify_p = sub.add_parser("classify-domains", help="Classify and quarantine candidates by legal domain")
    classify_p.add_argument("--input", default="data/batch/candidates.json")
    classify_p.add_argument("--domain", default="criminal", help="Target domain to keep")
    classify_p.add_argument("--use-llm", action="store_true", help="Use DeepSeek for ambiguous cases")
    classify_p.add_argument("--force-reclassify", action="store_true", help="Ignore existing high-confidence classifications")
    classify_p.add_argument("--no-trees", action="store_true", help="Skip topic-tree generation for non-criminal domains (trees generated by default)")

    # loop
    loop_p = sub.add_parser("loop", help="Full self-improving loop: discover → crawl → repeat")
    loop_p.add_argument("--rounds", type=int, default=3)
    loop_p.add_argument("--max-per-topic", type=int, default=30)
    loop_p.add_argument("--candidates", default="data/batch/candidates.json")
    loop_p.add_argument("--gap-report", default="data/batch/gap_report.json")
    loop_p.add_argument("--domain", default="criminal", help="Target legal domain to crawl")
    loop_p.add_argument("--tree", default="", help="Optional JSON authority tree path")

    args = parser.parse_args()
    if args.command == "discover":
        discover_gaps(
            candidates_path=args.candidates,
            output_path=args.output,
            domain_id=args.domain,
            tree_path=args.tree or None,
        )
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
            domain_id=args.domain,
            tree_path=args.tree or None,
        )
    elif args.command == "review":
        generate_codex_review(
            input_path=args.input,
            output_path=args.output,
            batch_size=args.batch_size,
            target_domain=args.domain,
        )
    elif args.command == "merge":
        merge_reviewed(
            input_path=args.input,
            enrichment_file=args.output or None,
            target_domain=args.domain,
        )
    elif args.command == "classify-domains":
        run_domain_filter(
            input_path=args.input,
            target_domain=args.domain,
            use_llm=args.use_llm,
            generate_trees=not args.no_trees,
            force_reclassify=args.force_reclassify,
        )
    elif args.command == "loop":
        run_loop(
            rounds=args.rounds,
            max_per_topic=args.max_per_topic,
            candidates_path=args.candidates,
            gap_report_path=args.gap_report,
            domain_id=args.domain,
            tree_path=args.tree or None,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
