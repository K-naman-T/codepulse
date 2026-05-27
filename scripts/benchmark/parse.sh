#!/usr/bin/env bash
set -euo pipefail

file="$1"

if [[ ! -f "$file" || ! -s "$file" ]]; then
  echo '{"cost":0,"tokens":0,"tool_calls":0,"time_seconds":0,"cache_reads":0}'
  exit 0
fi

if command -v jq &>/dev/null; then
  cost=$(jq -s '[.[] | select(.type == "step_finish") | .part.cost] | add // 0' "$file")
  tokens=$(jq -s '[.[] | select(.type == "step_finish") | .part.tokens.total] | add // 0' "$file")
  tools=$(jq -s '[.[] | select(.type == "tool_use")] | length' "$file")
  cache=$(jq -s '[.[] | select(.type == "step_finish") | .part.tokens.cache.read] | add // 0' "$file")
  first=$(jq -s 'first(.[].timestamp // empty) // 0' "$file")
  last=$(jq -s 'last(.[].timestamp // empty) // 0' "$file")
else
  cost=0; tokens=0; tools=0; cache=0; first=0; last=0
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if echo "$line" | grep -q '"type":"step_finish"'; then
      c=$(echo "$line" | sed 's/.*"part":{[^}]*"cost":\([0-9.]*\).*/\1/')
      t=$(echo "$line" | sed 's/.*"tokens":{"total":\([0-9]*\).*/\1/')
      r=$(echo "$line" | sed 's/.*"cache":{"read":\([0-9]*\).*/\1/')
      cost=$(echo "$cost + $c" | bc)
      tokens=$(echo "$tokens + $t" | bc)
      cache=$(echo "$cache + $r" | bc)
    fi
    if echo "$line" | grep -q '"type":"tool_use"'; then
      tools=$((tools + 1))
    fi
    ts=$(echo "$line" | sed 's/.*"timestamp":\([0-9.]*\).*/\1/')
    if [[ -n "$ts" && "$ts" != "$line" ]]; then
      [[ "$first" == "0" ]] && first=$ts
      last=$ts
    fi
  done < "$file"
fi

time_seconds=$(echo "scale=2; $last - $first" | bc 2>/dev/null || echo "0")

echo "{\"cost\":$cost,\"tokens\":$tokens,\"tool_calls\":$tools,\"time_seconds\":$time_seconds,\"cache_reads\":$cache}"
