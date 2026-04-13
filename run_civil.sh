#!/bin/zsh
cd "$(dirname "$0")"
set -a
source .env 2>/dev/null || true
set +a
export PYTHONPATH=src

mkdir -p data/batch

echo "[$(date)] Starting CIVIL crawl — domain=civil, max-per-topic=30" >> data/batch/civil_crawl.log
python3 -m casemap.batch_enrich crawl \
  --domain civil \
  --max-per-topic 30 \
  --output data/batch/candidates_civil_batch.json \
  >> data/batch/civil_crawl.log 2>&1

echo "[$(date)] CIVIL crawl done. Starting classify-domains..." >> data/batch/civil_crawl.log
python3 -m casemap.batch_enrich classify-domains \
  --input data/batch/candidates_civil_batch.json \
  --domain civil \
  --no-trees \
  >> data/batch/civil_crawl.log 2>&1

echo "[$(date)] CIVIL pipeline finished." >> data/batch/civil_crawl.log
