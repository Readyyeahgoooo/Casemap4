#!/usr/bin/env python3
"""Post-harvest domain classification and quarantine.

Run AFTER the batch pipeline finishes to:
1. Classify every candidate by legal domain
2. Quarantine non-criminal cases
3. Generate domain trees for discovered non-criminal domains
4. Output clean criminal-only candidates + separated domain files

Usage:
  PYTHONPATH=src python3 -m casemap.domain_filter \
    --input data/batch/candidates.json \
    --use-llm-for-ambiguous

This does NOT modify candidates.json — it writes new files alongside it.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from casemap.domain_classifier import (
    classify_domain,
    filter_candidates_by_domain,
    generate_domain_tree,
    LEGAL_DOMAINS,
)


def run_domain_filter(
    input_path: str = "data/batch/candidates.json",
    target_domain: str = "criminal",
    use_llm: bool = False,
    generate_trees: bool = True,
    force_reclassify: bool = False,
):
    """Classify all candidates, quarantine non-criminal, generate domain trees."""
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])
    print(f"[filter] Classifying {len(candidates)} candidates (target: {target_domain})")

    matched, cross_domain, out_of_domain = filter_candidates_by_domain(
        candidates,
        target_domain=target_domain,
        use_llm_for_ambiguous=use_llm,
        force_reclassify=force_reclassify,
    )

    print(f"  ✓ {len(matched)} matched ({target_domain})")
    print(f"  ⚠ {len(cross_domain)} cross-domain")
    print(f"  ✗ {len(out_of_domain)} out-of-domain")

    # Domain distribution of out-of-domain cases
    ood_domains = Counter()
    for c in out_of_domain + cross_domain:
        dc = c.get("domain_classification", {})
        ood_domains[dc.get("domain", "unknown")] += 1
    if ood_domains:
        print(f"\n  Out-of-domain breakdown:")
        for domain, count in ood_domains.most_common():
            label = LEGAL_DOMAINS.get(domain, {}).get("label_en", domain)
            print(f"    {label}: {count}")

    # Write outputs
    base = Path(input_path).parent

    # 1. Clean criminal-only candidates
    clean_path = base / f"candidates_{target_domain}_clean.json"
    clean_data = {
        "meta": {
            "generated_at": datetime.now(UTC).isoformat(),
            "source": input_path,
            "domain": target_domain,
            "total_candidates": len(candidates),
            "matched": len(matched),
            "cross_domain": len(cross_domain),
            "out_of_domain": len(out_of_domain),
        },
        "candidates": matched,
    }
    clean_path.write_text(json.dumps(clean_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  → {clean_path} ({len(matched)} cases)")

    # 2. Cross-domain candidates (needs manual review)
    if cross_domain:
        xd_path = base / "candidates_cross_domain.json"
        xd_data = {"meta": {"generated_at": datetime.now(UTC).isoformat()}, "candidates": cross_domain}
        xd_path.write_text(json.dumps(xd_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  → {xd_path} ({len(cross_domain)} cases)")

    # 3. Out-of-domain candidates grouped by domain
    if out_of_domain:
        by_domain: dict[str, list] = {}
        for c in out_of_domain:
            d = c.get("domain_classification", {}).get("domain", "unknown")
            by_domain.setdefault(d, []).append(c)

        for domain, cases in by_domain.items():
            ood_path = base / f"candidates_{domain}.json"
            ood_data = {"meta": {"generated_at": datetime.now(UTC).isoformat(), "domain": domain}, "candidates": cases}
            ood_path.write_text(json.dumps(ood_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  → {ood_path} ({len(cases)} cases)")

    # 4. Generate topic trees for non-criminal domains with enough cases
    if generate_trees:
        print(f"\n[trees] Generating topic trees for non-criminal domains...")
        trees_dir = base / "domain_trees"
        trees_dir.mkdir(exist_ok=True)

        for domain, count in ood_domains.most_common():
            if domain in ("unknown", target_domain) or count < 3:
                continue

            label = LEGAL_DOMAINS.get(domain, {}).get("label_en", domain)
            print(f"  Generating tree for {label} ({count} cases)...")

            tree = generate_domain_tree(domain)
            if tree:
                tree_path = trees_dir / f"{domain}_tree.json"
                tree_path.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
                topic_count = sum(
                    len(sg.get("topics", []))
                    for m in tree for sg in m.get("subgrounds", [])
                )
                print(f"    ✓ {tree_path} ({topic_count} topics)")
            else:
                print(f"    ✗ Failed to generate tree for {label}")

    # 5. Summary report
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input": input_path,
        "target_domain": target_domain,
        "total_candidates": len(candidates),
        "matched": len(matched),
        "cross_domain": len(cross_domain),
        "out_of_domain": len(out_of_domain),
        "domain_breakdown": dict(ood_domains.most_common()),
        "use_llm": use_llm,
        "force_reclassify": force_reclassify,
    }
    report_path = base / "domain_filter_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[done] Report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Post-harvest domain classification")
    parser.add_argument("--input", default="data/batch/candidates.json")
    parser.add_argument("--domain", default="criminal", help="Target domain to keep")
    parser.add_argument("--use-llm-for-ambiguous", action="store_true", help="Use DeepSeek for uncertain cases")
    parser.add_argument("--force-reclassify", action="store_true", help="Ignore existing high-confidence classifications")
    parser.add_argument("--generate-trees", action="store_true", default=True, help="Generate topic trees for other domains")
    parser.add_argument("--no-trees", action="store_true", help="Skip tree generation")

    args = parser.parse_args()
    run_domain_filter(
        input_path=args.input,
        target_domain=args.domain,
        use_llm=args.use_llm_for_ambiguous,
        generate_trees=not args.no_trees,
        force_reclassify=args.force_reclassify,
    )


if __name__ == "__main__":
    main()
