#!/bin/zsh
cd "$(dirname "$0")"
set -a
source .env 2>/dev/null || true
set +a
export PYTHONPATH=src

mkdir -p data/batch

echo "[$(date)] Starting CRIMINAL loop — domain=criminal, rounds=3, max-per-topic=50" >> data/batch/criminal_loop.log
python3 -m casemap.batch_enrich loop \
  --domain criminal \
  --rounds 3 \
  --max-per-topic 50 \
  --candidates data/batch/candidates_criminal_clean.json \
  >> data/batch/criminal_loop.log 2>&1

echo "[$(date)] CRIMINAL loop finished." >> data/batch/criminal_loop.log
