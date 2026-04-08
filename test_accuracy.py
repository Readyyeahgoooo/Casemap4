#!/usr/bin/env python3
"""Test retrieval accuracy with area-aware scoring."""
import time, json, sys, os
sys.path.insert(0, "src")
from casemap.hybrid_graph import HybridGraphStore, DeterminatorPipeline

store = HybridGraphStore.from_file("artifacts/hk_criminal_hybrid_v2/hierarchical_graph.json")
pipeline = DeterminatorPipeline()

queries = [
    "What is the sentence for murder in Hong Kong?",
    "What are the elements of theft?",
    "Can intoxication be a defence to a crime?",
    "Can I get bail for a murder charge?",
    "What is the sentence for burglary?",
    "If i get other USDT without verifying, is it illegal in HK?",
    "Can I be charged for drug trafficking?",
    "Is stabbing a dog a crime?",
    "What happens if I stab someone?",
]
for q in queries:
    cl = pipeline._classify(q)
    t0 = time.time()
    r = store.query(
        q, top_k=5,
        classification_area=cl["area"],
        offence_keywords=cl.get("criminal_hits", []),
    )
    t1 = time.time()
    cites = r.get("citations", [])
    top2 = ", ".join(c["case_name"][:35] for c in cites[:2])
    labels = ", ".join(c.get("principle_label", "")[:25] for c in cites[:2])
    print(f'{t1-t0:.2f}s | area={cl["area"]:18s} | {len(cites)} cites | {q[:45]:45s}')
    print(f'       top: {top2}')
    print(f'       labels: {labels}')
    print()
