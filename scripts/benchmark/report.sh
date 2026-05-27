#!/usr/bin/env bash
set -euo pipefail

median() {
  local vals=("$@")
  local n=${#vals[@]}
  if (( n == 0 )); then echo 0; return; fi
  local sorted
  sorted=$(printf '%s\n' "${vals[@]}" | sort -n)
  local mid=$(( (n + 1) / 2 ))
  if (( n % 2 == 1 )); then
    echo "$sorted" | sed -n "${mid}p"
  else
    local a b
    a=$(echo "$sorted" | sed -n "${mid}p")
    b=$(echo "$sorted" | sed -n "$((mid + 1))p")
    echo "scale=2; ($a + $b) / 2" | bc
  fi
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "${1:-}" == "--test-median" ]]; then
  shift
  median "$@"
  exit 0
fi

parse_arm() {
  local pattern="$1"
  local files
  files=$(ls $pattern 2>/dev/null || true)
  if [[ -z "$files" ]]; then
    echo "0:0:0:0:0"
    return
  fi
  local all_cost=() all_tokens=() all_tools=() all_time=() all_cache=()
  for f in $files; do
    local metrics
    metrics=$("$SCRIPT_DIR/parse.sh" "$f")
    all_cost+=($(echo "$metrics" | jq -r '.cost'))
    all_tokens+=($(echo "$metrics" | jq -r '.tokens'))
    all_tools+=($(echo "$metrics" | jq -r '.tool_calls'))
    all_time+=($(echo "$metrics" | jq -r '.time_seconds'))
    all_cache+=($(echo "$metrics" | jq -r '.cache_reads'))
  done
  local mc mt mtools mtime mcac
  mc=$(median "${all_cost[@]}")
  mt=$(median "${all_tokens[@]}")
  mtools=$(median "${all_tools[@]}")
  mtime=$(median "${all_time[@]}")
  mcac=$(median "${all_cache[@]}")
  echo "$mc:$mt:$mtools:$mtime:$mcac"
}

fmt_cost() {
  printf "\$%.2f" "$1"
}

fmt_tokens() {
  local t
  t=$(printf "%.0f" "$1" 2>/dev/null || echo "${1%.*}")
  if (( t >= 1000000 )); then
    echo "$(echo "scale=1; $t/1000000" | bc)M"
  elif (( t >= 1000 )); then
    echo "$(echo "scale=1; $t/1000" | bc)k"
  else
    echo "$t"
  fi
}

fmt_time() {
  local seconds
  seconds=$(printf "%.0f" "$1" 2>/dev/null || echo "${1%.*}")
  local m=$(( seconds / 60 ))
  local sec=$(( seconds % 60 ))
  printf "%dm %02ds" "$m" "$sec"
}

fmt_savings() {
  local with=$1 without=$2
  if (( $(echo "$without == 0" | bc -l) )); then
    echo "N/A"
    return
  fi
  local pct
  pct=$(echo "scale=1; (1 - $with / $without) * 100" | bc)
  echo "${pct}% ↓"
}

with_dir="${1:-$SCRIPT_DIR/results}"
without_dir="${2:-$SCRIPT_DIR/results}"

with_metrics=$(parse_arm "$with_dir/with-*.json")
without_metrics=$(parse_arm "$without_dir/without-*.json")

IFS=':' read -r w_cost w_tokens w_tools w_time w_cache <<< "$with_metrics"
IFS=':' read -r wo_cost wo_tokens wo_tools wo_time wo_cache <<< "$without_metrics"

cat <<TABLE
Metrics           WITH Codepulse    WITHOUT           Savings
─────────────────────────────────────────────────────────────────
Cost              $(printf "%-17s" "$(fmt_cost "$w_cost")") $(printf "%-17s" "$(fmt_cost "$wo_cost")") $(fmt_savings "$w_cost" "$wo_cost")
Tokens            $(printf "%-17s" "$(fmt_tokens "$w_tokens")") $(printf "%-17s" "$(fmt_tokens "$wo_tokens")") $(fmt_savings "$w_tokens" "$wo_tokens")
Time              $(printf "%-17s" "$(fmt_time "$w_time")") $(printf "%-17s" "$(fmt_time "$wo_time")") $(fmt_savings "$w_time" "$wo_time")
Tool calls        $(printf "%-17s" "$(printf "%.0f" "$w_tools")") $(printf "%-17s" "$(printf "%.0f" "$wo_tools")") $(fmt_savings "$w_tools" "$wo_tools")
Cache reads       $(printf "%-17s" "$(fmt_tokens "$w_cache")") $(printf "%-17s" "$(fmt_tokens "$wo_cache")") $(fmt_savings "$w_cache" "$wo_cache")
TABLE
