#!/bin/zsh
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap4
export PYTHONPATH=src
# Load API key from .env file — NEVER hardcode secrets in scripts
if [[ -f .env ]]; then
  export $(grep -v '^#' .env | grep DEEPSEEK_API_KEY | xargs)
fi
if [[ -z "$DEEPSEEK_API_KEY" ]]; then
  echo "ERROR: DEEPSEEK_API_KEY not set. Add it to .env" >&2
  exit 1
fi
python3 -m casemap build-criminal-graph \
  --source "Crim books/Butterworths Hong Kong Criminal Law and Procedure Handbook - Third Edition (Various authors) (z-library.sk, 1lib.sk, z-lib.sk).pdf" \
  --source "Crim books/Criminal Law In Hong Kong (Simon SY So) (z-library.sk, 1lib.sk, z-lib.sk).pdf" \
  --output-dir artifacts/hk_criminal_relationship_v2 \
  --hybrid-output-dir artifacts/hk_criminal_hybrid_v2 \
  --per-query-limit 8 \
  --max-cases 400 \
  --max-textbook-case-fetches 80 \
  --max-enrich 200 \
  --embedding-backend local-hash
