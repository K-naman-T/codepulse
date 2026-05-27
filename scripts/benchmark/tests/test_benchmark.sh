#!/usr/bin/env bash
set -euo pipefail

export PATH="$PWD/scripts/benchmark:$PATH"
FAILURES=0

setup() {
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
}

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" != "$actual" ]]; then
    echo "FAIL: $desc — expected: $expected, got: $actual"
    ((FAILURES++))
  else
    echo "PASS: $desc"
  fi
}

test_json_parsing() {
  local ndjson="$tmp/test.ndjson"
  cat > "$ndjson" <<'EOF'
{"type":"step_finish","part":{"tokens":{"total":100,"input":50,"output":50,"cache":{"read":10}},"cost":0.002}}
{"type":"tool_use","tool":"read"}
{"type":"text","content":"hello"}
{"type":"step_finish","part":{"tokens":{"total":200,"input":100,"output":100,"cache":{"read":20}},"cost":0.005}}
{"type":"tool_use","tool":"write"}
{"type":"tool_use","tool":"bash"}
EOF
  local result
  result=$(parse.sh "$ndjson")
  local cost tokens tools time cache
  cost=$(echo "$result" | jq -r '.cost')
  tokens=$(echo "$result" | jq -r '.tokens')
  tools=$(echo "$result" | jq -r '.tool_calls')
  cache=$(echo "$result" | jq -r '.cache_reads')
  assert_eq "cost sum" "0.007" "$cost"
  assert_eq "token sum" "300" "$tokens"
  assert_eq "tool calls" "3" "$tools"
  assert_eq "cache reads" "30" "$cache"
}

test_median_odd() {
  local result
  result=$(report.sh --test-median "10" "20" "30" "40" "50")
  assert_eq "median odd" "30" "$result"
}

test_median_even() {
  local arr=("10" "20" "30" "40")
  local result
  result=$(report.sh --test-median "${arr[@]}")
  assert_eq "median even" "25.00" "$result"
}

test_percent_savings() {
  local pct
  pct=$(echo "scale=1; (1 - 50 / 100) * 100" | bc)
  assert_eq "50% savings" "50.0" "$pct"
}

test_empty_input() {
  local empty="$tmp/empty.ndjson"
  touch "$empty"
  local result
  result=$(parse.sh "$empty")
  local cost tokens tools time cache
  cost=$(echo "$result" | jq -r '.cost')
  tokens=$(echo "$result" | jq -r '.tokens')
  tools=$(echo "$result" | jq -r '.tool_calls')
  cache=$(echo "$result" | jq -r '.cache_reads')
  assert_eq "empty cost" "0" "$cost"
  assert_eq "empty tokens" "0" "$tokens"
  assert_eq "empty tools" "0" "$tools"
  assert_eq "empty cache" "0" "$cache"
}

setup
test_json_parsing
test_median_odd
test_median_even
test_percent_savings
test_empty_input

if (( FAILURES > 0 )); then
  echo "--- $FAILURES test(s) FAILED ---"
  exit 1
else
  echo "--- All tests passed ---"
fi
