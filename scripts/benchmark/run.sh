#!/usr/bin/env bash
set -euo pipefail

CONFIG="$HOME/.config/opencode/opencode.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
QUESTIONS="$SCRIPT_DIR/questions.json"
N_RUNS=4
MODEL=""
REPO=""

usage() {
  echo "Usage: $0 [--repo raftaar-ai|codepulse] [--runs N] [--model <model>]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --runs) N_RUNS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    *) usage ;;
  esac
done

if [[ -z "$REPO" ]]; then
  echo "Error: --repo is required"
  usage
fi

QUESTION=$(jq -r --arg repo "$REPO" '.[$repo] // empty' "$QUESTIONS")
if [[ -z "$QUESTION" ]]; then
  echo "Error: no question found for repo '$REPO' in $QUESTIONS"
  exit 1
fi

if [[ -z "$MODEL" ]]; then
  MODEL=$(jq -r '.model // empty' "$CONFIG")
  if [[ -z "$MODEL" ]]; then
    echo "Error: no model specified and no model found in $CONFIG"
    exit 1
  fi
fi

mkdir -p "$RESULTS_DIR"

backup="${CONFIG}.bak"
cp "$CONFIG" "$backup"

cleanup() {
  cp "$backup" "$CONFIG"
  rm -f "$backup"
}
trap cleanup EXIT

run_benchmark() {
  local suffix="$1"  # "with" or "without"
  local config_tmp=$(mktemp)
  cp "$CONFIG" "$config_tmp"

  if [[ "$suffix" == "without" ]]; then
    jq 'del(.mcp)' "$config_tmp" > "${config_tmp}.new" && mv "${config_tmp}.new" "$config_tmp"
  else
    local has_mcp
    has_mcp=$(jq 'has("mcp")' "$config_tmp")
    if [[ "$has_mcp" == "false" ]]; then
      CODEPULSE_BIN="${CODEPULSE_BIN:-$(command -v codepulse 2>/dev/null || echo '/home/knamant/codepulse/.venv/bin/codepulse')}"
      jq --arg bin "$CODEPULSE_BIN" '.mcp = {"codepulse":{"type":"local","command":[$bin,"mcp"],"enabled":true}}' "$config_tmp" > "${config_tmp}.new" && mv "${config_tmp}.new" "$config_tmp"
    fi
  fi

  cp "$config_tmp" "$CONFIG"

  for i in $(seq 1 "$N_RUNS"); do
    echo "--- Run $suffix #$i of $N_RUNS ---"
    out="$RESULTS_DIR/${suffix}-${i}.json"
    echo "$QUESTION" | opencode run --format json --dangerously-skip-permissions --model "$MODEL" - > "$out" 2>&1 || true
    echo "Saved to $out"
  done

  rm -f "$config_tmp"
}

run_benchmark "without"
run_benchmark "with"

echo "--- Generating report ---"
bash "$SCRIPT_DIR/report.sh"
