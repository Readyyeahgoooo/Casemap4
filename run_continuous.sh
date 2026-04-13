#!/bin/zsh
# Continuous self-improving pipeline for Casemap4
# Runs indefinitely: crawl → enrich → build graph → git push → sleep → repeat
# Vercel auto-redeploys on every push, keeping casemap4.vercel.app live.
#
# Usage:
#   nohup /bin/zsh run_continuous.sh > data/batch/continuous.log 2>&1 &
#
# Stop: kill $(cat data/batch/continuous.pid)

set -e
cd "$(dirname "$0")"

# ── Config ──────────────────────────────────────────────────────────────────
SLEEP_HOURS=6          # pause between full cycles
CRAWL_ROUNDS=2         # batch_enrich rounds per cycle (discover + crawl)
MAX_PER_TOPIC=50       # HKLII cases to pull per topic per round
MAX_ENRICH=120         # max DeepSeek enrichments per graph build
CRIMINAL_CANDIDATES="data/batch/candidates_criminal_clean.json"
CIVIL_CANDIDATES="data/batch/candidates_civil_batch.json"
CIVIL_TREE="data/batch/domain_trees/civil_tree.json"
CRIMINAL_OUT="artifacts/hk_criminal_relationship_v2"
CRIMINAL_HYBRID_OUT="artifacts/hk_criminal_hybrid_v2"
CIVIL_OUT="artifacts/hk_civil_graph"
LOG_DIR="data/batch"

# ── Env ──────────────────────────────────────────────────────────────────────
set -a
source .env 2>/dev/null || true
set +a
export PYTHONPATH=src

if [[ -z "$DEEPSEEK_API_KEY" && -z "$OPENROUTER_API_KEY" ]]; then
  echo "[ERROR] No API key found. Set DEEPSEEK_API_KEY in .env" >&2
  exit 1
fi

mkdir -p "$LOG_DIR" artifacts/hk_civil_graph

# Save PID for easy kill
echo $$ > "$LOG_DIR/continuous.pid"

# ── Helpers ──────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
section() { echo; echo "══════════════════════════════════════════════════"; echo "  $*"; echo "══════════════════════════════════════════════════"; }

# Rotate a log file: keep last MAX_LINES lines (default 5000)
rotate_log() {
  local file="$1" max="${2:-5000}"
  [[ -f "$file" ]] || return 0
  local lines
  lines=$(wc -l < "$file")
  if (( lines > max )); then
    tail -n "$max" "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
    log "Rotated $file (was $lines lines, kept last $max)"
  fi
}

# Trim HKLII cache: delete oldest files when count exceeds MAX_CACHE (default 5000)
trim_hklii_cache() {
  local cache_dir="data/cache/hklii" max="${1:-5000}"
  [[ -d "$cache_dir" ]] || return 0
  local count
  count=$(ls "$cache_dir" | wc -l)
  if (( count > max )); then
    local to_delete=$(( count - max ))
    ls -t "$cache_dir" | tail -n "$to_delete" | xargs -I{} rm -f "$cache_dir/{}"
    log "Trimmed HKLII cache: removed $to_delete oldest files (kept $max)"
  fi
}

snapshot_artifacts() {
  local label="$1"
  local ts
  ts=$(date '+%Y%m%d_%H%M%S')
  local snapshot_dir="$LOG_DIR/snapshots"
  local snapshot_path="$snapshot_dir/${ts}_${label}.tgz"
  mkdir -p "$snapshot_dir"

  local paths=()
  for path in \
    "$CRIMINAL_OUT" \
    "$CRIMINAL_HYBRID_OUT" \
    "$CIVIL_OUT" \
    "$CRIMINAL_CANDIDATES" \
    data/batch/candidates_civil_clean.json \
    data/batch/discovered_lineages.json \
    data/batch/enrichment_cache_criminal.json \
    data/batch/enrichment_cache_civil.json \
    data/batch/hallucination_log.json
  do
    [[ -e "$path" ]] && paths+=("$path")
  done

  if (( ${#paths[@]} == 0 )); then
    log "[WARN] Snapshot skipped; no artifact paths found"
    return 0
  fi

  tar -czf "$snapshot_path" "${paths[@]}" 2>/dev/null \
    && log "Snapshot saved: $snapshot_path" \
    || log "[WARN] Snapshot failed: $snapshot_path"
}

# ── Main loop ────────────────────────────────────────────────────────────────
CYCLE=0

while true; do
  CYCLE=$((CYCLE + 1))
  section "CYCLE ${CYCLE} START"
  log "Cycle ${CYCLE} beginning"
  snapshot_artifacts "cycle_${CYCLE}_prebuild"

  # ────────────────────────────────────────────────────────────────────────────
  # PHASE 1: CRIMINAL — crawl + discover gaps
  # ────────────────────────────────────────────────────────────────────────────
  section "PHASE 1 — CRIMINAL CRAWL (${CRAWL_ROUNDS} rounds)"
  python3 -m casemap.batch_enrich loop \
    --domain criminal \
    --rounds "$CRAWL_ROUNDS" \
    --max-per-topic "$MAX_PER_TOPIC" \
    --candidates "$CRIMINAL_CANDIDATES" \
    >> "$LOG_DIR/criminal_loop.log" 2>&1 \
    && log "Criminal crawl loop done" \
    || log "[WARN] Criminal crawl loop exited non-zero (continuing)"

  # ────────────────────────────────────────────────────────────────────────────
  # PHASE 2: CRIMINAL — rebuild graph & hybrid artifacts
  # ────────────────────────────────────────────────────────────────────────────
  section "PHASE 2 — CRIMINAL GRAPH BUILD"
  python3 -m casemap build-domain-graph \
    --domain criminal \
    --candidates "$CRIMINAL_CANDIDATES" \
    --output-dir "$CRIMINAL_OUT" \
    --hybrid-output-dir "$CRIMINAL_HYBRID_OUT" \
    --max-enrich "$MAX_ENRICH" \
    --max-cases 600 \
    --discover-lineages \
    --lineages-path data/batch/discovered_lineages.json \
    --enrichment-cache data/batch/enrichment_cache_criminal.json \
    >> "$LOG_DIR/criminal_build.log" 2>&1 \
    && log "Criminal graph build done" \
    || log "[WARN] Criminal graph build exited non-zero (continuing)"

  # ────────────────────────────────────────────────────────────────────────────
  # PHASE 3: CIVIL — crawl (if tree exists)
  # ────────────────────────────────────────────────────────────────────────────
  if [[ -f "$CIVIL_TREE" ]]; then
    section "PHASE 3 — CIVIL CRAWL"
    python3 -m casemap.batch_enrich crawl \
      --domain civil \
      --tree "$CIVIL_TREE" \
      --max-per-topic 30 \
      --output "$CIVIL_CANDIDATES" \
      >> "$LOG_DIR/civil_crawl.log" 2>&1 \
      && log "Civil crawl done" \
      || log "[WARN] Civil crawl exited non-zero (continuing)"

    # Classify-domains to produce candidates_civil_clean.json
    if [[ -f "$CIVIL_CANDIDATES" ]]; then
      python3 -m casemap.batch_enrich classify-domains \
        --input "$CIVIL_CANDIDATES" \
        --domain civil \
        --no-trees \
        >> "$LOG_DIR/civil_crawl.log" 2>&1 \
        && log "Civil classify done" \
        || log "[WARN] Civil classify exited non-zero (continuing)"
    fi

    # ────────────────────────────────────────────────────────────────────────────
    # PHASE 4: CIVIL — rebuild graph artifacts
    # ────────────────────────────────────────────────────────────────────────────
    CIVIL_CLEAN="data/batch/candidates_civil_clean.json"
    if [[ -f "$CIVIL_CLEAN" ]]; then
      section "PHASE 4 — CIVIL GRAPH BUILD"
      # Add civil artifact files to gitignore whitelist if not done yet
      python3 -m casemap build-domain-graph \
        --domain civil \
        --tree "$CIVIL_TREE" \
        --candidates "$CIVIL_CLEAN" \
        --output-dir "$CIVIL_OUT" \
        --max-enrich 80 \
        --max-cases 400 \
        --discover-lineages \
        --lineages-path data/batch/discovered_lineages.json \
        --enrichment-cache data/batch/enrichment_cache_civil.json \
        >> "$LOG_DIR/civil_build.log" 2>&1 \
        && log "Civil graph build done" \
        || log "[WARN] Civil graph build exited non-zero (continuing)"
    fi
  else
    log "[SKIP] No civil tree at $CIVIL_TREE — skipping civil phases"
  fi

  # ────────────────────────────────────────────────────────────────────────────
  # PHASE 5: COMMIT + PUSH → triggers Vercel redeploy
  # ────────────────────────────────────────────────────────────────────────────
  section "PHASE 5 — GIT COMMIT + PUSH"

  # Stage all whitelisted artifact files
  git add \
    artifacts/hk_criminal_relationship_v2/ \
    artifacts/hk_criminal_hybrid_v2/ \
    2>/dev/null || true

  # Stage civil if it exists (may not be whitelisted yet)
  if [[ -d "$CIVIL_OUT" ]]; then
    git add -f artifacts/hk_civil_graph/ 2>/dev/null || true
  fi

  # Stage updated candidate files for data persistence
  git add \
    data/batch/candidates_criminal_clean.json \
    data/batch/candidates_civil_clean.json \
    data/batch/discovered_lineages.json \
    data/batch/hallucination_log.json \
    data/batch/domain_trees/ \
    data/batch/enrichment_cache_criminal.json \
    data/batch/enrichment_cache_civil.json \
    2>/dev/null || true

  # Only commit if there are staged changes
  if git diff --cached --quiet; then
    log "No changes to commit this cycle"
  else
    CRIMINAL_COUNT=$(python3 -c "
import json, sys
try:
    d=json.load(open('$CRIMINAL_CANDIDATES'))
    cands=d.get('candidates',[])
    print(len(cands))
except:
    print('?')
" 2>/dev/null)
    git commit -m "auto(cycle ${CYCLE}): graph rebuild — ${CRIMINAL_COUNT} criminal candidates, $(date '+%Y-%m-%d %H:%M')"
    # Try SSH push first; fall back to HTTPS if SSH port is blocked
    if git push 2>&1; then
      log "Pushed via SSH — Vercel will redeploy"
    else
      log "[WARN] SSH push failed — retrying via HTTPS"
      HTTPS_REMOTE="https://github.com/Readyyeahgoooo/Casemap4.git"
      git push "$HTTPS_REMOTE" HEAD:codex/multi-domain-framework 2>&1 \
        && log "Pushed via HTTPS — Vercel will redeploy" \
        || log "[WARN] Both SSH and HTTPS push failed; will retry next cycle"
    fi
  fi

  # ────────────────────────────────────────────────────────────────────────────
  # LOG ROTATION + CACHE TRIM (keep disk usage low)
  # ────────────────────────────────────────────────────────────────────────────
  rotate_log "$LOG_DIR/continuous.log"       5000
  rotate_log "$LOG_DIR/criminal_build.log"   3000
  rotate_log "$LOG_DIR/criminal_loop.log"    3000
  rotate_log "$LOG_DIR/civil_build.log"      3000
  rotate_log "$LOG_DIR/civil_crawl.log"      3000
  trim_hklii_cache 5000

  # ────────────────────────────────────────────────────────────────────────────
  # SLEEP before next cycle
  # ────────────────────────────────────────────────────────────────────────────
  NEXT_RUN=$(date -v+${SLEEP_HOURS}H '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date '+%Y-%m-%d %H:%M:%S')
  log "Cycle ${CYCLE} complete. Sleeping ${SLEEP_HOURS}h. Next run ~${NEXT_RUN}"
  section "SLEEPING ${SLEEP_HOURS}h"
  sleep $((SLEEP_HOURS * 3600))
done
