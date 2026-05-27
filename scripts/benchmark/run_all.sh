#!/usr/bin/env bash
# run_all.sh — Run benchmark across all repos
# Usage: ./run_all.sh [--repos raftaar-ai,gin,tokio] [--runs 3] [--model model]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPOS_FILE="$SCRIPT_DIR/repos.json"
RESULTS_DIR="$SCRIPT_DIR/results"
N_RUNS=3
MODEL="opencode-go/deepseek-v4-flash"
REPO_LIST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repos) REPO_LIST="$2"; shift 2 ;;
    --runs) N_RUNS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    *) echo "Usage: $0 [--repos a,b,c] [--runs 3] [--model m]"; exit 1 ;;
  esac
done

mkdir -p "$RESULTS_DIR"

if [[ -z "$REPO_LIST" ]]; then
  REPO_LIST=$(jq -r 'keys[]' "$REPOS_FILE" | tr '\n' ',' | sed 's/,$//')
fi

TOTAL_REPOS=$(echo "$REPO_LIST" | tr ',' '\n' | wc -l)
CURRENT=0
PASS_COUNT=0
FAIL_COUNT=0

for repo in $(echo "$REPO_LIST" | tr ',' ' '); do
  CURRENT=$((CURRENT + 1))
  echo ""
  echo "═══════════════════════════════════════════════════"
  echo "  [$CURRENT/$TOTAL_REPOS] $repo"
  echo "═══════════════════════════════════════════════════"

  lang=$(jq -r ".[\"$repo\"].lang // \"?\"" "$REPOS_FILE")
  echo "  Language: $lang"

  data_dir=$(jq -r ".[\"$repo\"].data_dir" "$REPOS_FILE")
  if [[ ! -d "$data_dir" ]]; then
    echo "  ⚠  Not indexed — run setup.sh first"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    continue
  fi

  # Get questions
  questions=$(jq -r ".[\"$repo\"].questions[]" "$REPOS_FILE")
  qnum=0

  while IFS= read -r question; do
    qnum=$((qnum + 1))
    echo "  Question $qnum: ${question:0:60}..."
    echo ""

    for arm in without with; do
      outfile="$RESULTS_DIR/${repo}-q${qnum}-${arm}.json"
      echo "    Running ${arm} arm..."

      # Set up MCP config for with arm
      if [[ "$arm" == "with" ]]; then
        CODEPULSE_BIN=$(command -v codepulse || echo "/home/knamant/codepulse/.venv/bin/codepulse")
        cat ~/.config/opencode/opencode.json | \
          jq --arg bin "$CODEPULSE_BIN" \
             '.mcp = {"codepulse":{"type":"local","command":[$bin,"mcp"],"enabled":true}}' \
           > /tmp/bench-config.json
        cp /tmp/bench-config.json ~/.config/opencode/opencode.json
      else
        cat ~/.config/opencode/opencode.json | \
          jq 'del(.mcp)' \
           > /tmp/bench-config.json 2>/dev/null || cat ~/.config/opencode/opencode.json > /tmp/bench-config.json
        # If jq fails (no mcp key), just copy as-is
        cp /tmp/bench-config.json ~/.config/opencode/opencode.json
      fi

      # Run
      echo "$question" | CODEPULSE_DATA_DIR="$data_dir" \
        timeout 300 opencode run --format json --dangerously-skip-permissions \
        --model "$MODEL" - > "$outfile" 2>/dev/null || true

      # Parse
      result=$(cat "$outfile" | python3 -c "
import sys, json
tc=0; cost=0.0; tok=0; ft=None; lt=None
for line in sys.stdin:
    try:
        d=json.loads(line.strip())
        ts=d.get('timestamp',0)
        if ft is None: ft=ts
        lt=ts
        if d.get('type')=='tool_use': tc+=1
        elif d.get('type')=='step_finish':
            p=d.get('part',{})
            cost+=p.get('cost',0) or 0
            tok+=p.get('tokens',{}).get('total',0) or 0
    except: pass
wt=((lt-ft)/1000) if ft and lt else 0
print(f'{tok}|{tc}|{wt:.0f}|{cost:.6f}')
" 2>/dev/null || echo "0|0|0|0")

      IFS='|' read -r tokens tool_calls wall_time cost <<< "$result"
      echo "    → ${tokens}tokens, ${tool_calls}calls, ${wall_time}s, \$${cost}"
    done

    # Compute savings
    without_file="$RESULTS_DIR/${repo}-q${qnum}-without.json"
    with_file="$RESULTS_DIR/${repo}-q${qnum}-with.json"

    wot=$(cat "$without_file" | python3 -c "
import sys,json; tok=0
for line in sys.stdin:
    try:
        d=json.loads(line.strip())
        if d.get('type')=='step_finish':
            tok+=d.get('part',{}).get('tokens',{}).get('total',0) or 0
    except: pass
print(tok)" 2>/dev/null || echo 0)

    wt=$(cat "$with_file" | python3 -c "
import sys,json; tok=0
for line in sys.stdin:
    try:
        d=json.loads(line.strip())
        if d.get('type')=='step_finish':
            tok+=d.get('part',{}).get('tokens',{}).get('total',0) or 0
    except: pass
print(tok)" 2>/dev/null || echo 0)

    if [[ "$wot" -gt 0 ]]; then
      savings=$(( (wot - wt) * 100 / wot ))
    else
      savings=0
    fi

    if [[ "$savings" -ge 30 ]]; then
      echo "    ✅ PASS (${savings}% token reduction)"
      if [[ "$qnum" -eq 1 ]]; then PASS_COUNT=$((PASS_COUNT + 1)); fi
    else
      echo "    ⚠  ${savings}% token reduction (need ≥30%)"
      if [[ "$qnum" -eq 1 ]]; then FAIL_COUNT=$((FAIL_COUNT + 1)); fi
    fi
    echo ""
  done <<< "$questions"
done

# Restore clean config
cat ~/.config/opencode/opencode.json | jq 'del(.mcp)' > /tmp/bench-clean.json 2>/dev/null && cp /tmp/bench-clean.json ~/.config/opencode/opencode.json

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Results: $PASS_COUNT passed, $FAIL_COUNT failed (of $TOTAL_REPOS)"
echo "═══════════════════════════════════════════════════"
