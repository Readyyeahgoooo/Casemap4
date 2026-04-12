#!/bin/zsh
cd /Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap4
export PYTHONPATH=/Users/puiyuenwong/PolymarketCorrelationStrategy/Casemap4/src
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi
caffeinate -s &
echo $! > data/batch/caffeinate.pid
echo "[$(date)] Pipeline starting (PID $$, caffeinate PID $(cat data/batch/caffeinate.pid))" > data/batch/run.log
python3 -u -m casemap.batch_enrich loop \
  --rounds 3 \
  --max-per-topic 50 \
  --candidates data/batch/candidates.json >> data/batch/run.log 2>&1
echo "[$(date)] Pipeline finished" >> data/batch/run.log
