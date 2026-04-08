#!/bin/bash
set -e
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap4
export PYTHONPATH=src

# API key is loaded from .env automatically via --env-file flag
SOURCE1="Crim books/Butterworths Hong Kong Criminal Law and Procedure Handbook - Third Edition (Various authors) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
SOURCE2="Crim books/Criminal Law In Hong Kong (Simon SY So) (z-library.sk, 1lib.sk, z-lib.sk).pdf"

python3 -m casemap build-criminal-graph \
  --source "$SOURCE1" \
  --source "$SOURCE2" \
  --output-dir artifacts/hk_criminal_relationship_v2 \
  --hybrid-output-dir artifacts/hk_criminal_hybrid_v2 \
  --per-query-limit 8 \
  --max-cases 400 \
  --max-textbook-case-fetches 80 \
  --max-enrich 200 \
  --embedding-backend local-hash
