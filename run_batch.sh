#!/bin/bash
# Launch batch enrichment pipeline in background
set -e
cd "$(dirname "$0")"
export PYTHONPATH=src

# Load API key from .env
if [[ -f .env ]]; then
  export $(grep -v '^#' .env | grep -E 'DEEPSEEK_API_KEY|OPENROUTER_API_KEY' | xargs)
fi

if [[ -z "$DEEPSEEK_API_KEY" && -z "$OPENROUTER_API_KEY" ]]; then
  echo "ERROR: No API key found. Set DEEPSEEK_API_KEY in .env"
  exit 1
fi

mkdir -p data/batch
echo "[$(date)] Starting batch enrichment loop (3 rounds, 50/topic)..."
python3 -m casemap.batch_enrich loop --rounds 3 --max-per-topic 50 --candidates data/batch/candidates.json
echo "[$(date)] Pipeline finished."
