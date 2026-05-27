#!/usr/bin/env bash
# setup.sh — Clone and index benchmark repos one at a time
# Usage: ./setup.sh [--repo repo-name] [--cleanup]
#   --repo: only clone/index one specific repo
#   --cleanup: remove cloned repos after indexing (saves space)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPOS_FILE="$SCRIPT_DIR/repos.json"
CACHE_DIR="/tmp/bench-repos"

mkdir -p "$CACHE_DIR"

setup_repo() {
  local name="$1"
  local url
  local clone_to
  local data_dir

  url=$(jq -r ".[\"$name\"].url // empty" "$REPOS_FILE")
  clone_to=$(jq -r ".[\"$name\"].clone_to // empty" "$REPOS_FILE")
  data_dir=$(jq -r ".[\"$name\"].data_dir // empty" "$REPOS_FILE")
  local_path=$(jq -r ".[\"$name\"].local_path // empty" "$REPOS_FILE")

  # Skip if no URL (already local)
  if [[ -z "$url" && -n "$local_path" ]]; then
    echo "[$name] Already local at $local_path — indexing..."
    CODEPULSE_DATA_DIR="$data_dir" codepulse index "$local_path" 2>/dev/null || true
    echo "[$name] ✅ Indexed"
    return
  fi

  # Skip if no URL and no local path
  if [[ -z "$url" ]]; then
    echo "[$name] No URL or local path — skipping"
    return
  fi

  # Clone if not already cloned
  if [[ ! -d "$clone_to" ]]; then
    echo "[$name] Cloning ($(jq -r ".[\"$name\"].size_mb // \"?\"" "$REPOS_FILE") MB)..."
    git clone --depth 1 "$url" "$clone_to" 2>/dev/null
    echo "[$name] ✅ Cloned"
  else
    echo "[$name] Already cloned"
  fi

  # Index
  if [[ -d "$clone_to" ]]; then
    local db_dir
    db_dir=$(dirname "$data_dir")
    mkdir -p "$db_dir"
    echo "[$name] Indexing..."
    CODEPULSE_DATA_DIR="$data_dir" codepulse index "$clone_to" 2>/dev/null || true
    echo "[$name] ✅ Indexed"
  fi
}

# Main
if [[ "${1:-}" == "--repo" ]]; then
  setup_repo "${2:-}"
elif [[ "${1:-}" == "--cleanup" ]]; then
  echo "Cleaning up cloned repos from $CACHE_DIR..."
  rm -rf "$CACHE_DIR"
  echo "Done"
else
  for name in $(jq -r 'keys[]' "$REPOS_FILE"); do
    echo "======== $name ========"
    setup_repo "$name"
    echo ""
  done
  echo "===== All repos setup ====="
fi
