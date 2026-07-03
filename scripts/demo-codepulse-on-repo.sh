#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-https://github.com/pallets/flask}"
DATA_DIR="${CODEPULSE_DEMO_DATA_DIR:-$(pwd)/.codepulse-demo}"

rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"

echo "== CodePulse demo =="
echo "Target: $TARGET"
echo "Data dir: $DATA_DIR"
echo

codepulse --data-dir "$DATA_DIR" analyze "$TARGET"
echo

echo "== Graph stats =="
codepulse --data-dir "$DATA_DIR" validate
echo

echo "== Symbol search =="
codepulse --data-dir "$DATA_DIR" search Flask --limit 5 || true
echo

echo "== Symbol notes roundtrip =="
codepulse --data-dir "$DATA_DIR" note add "demo:Flask" "Central application object; inspect before changing routing or config." --source demo
codepulse --data-dir "$DATA_DIR" note list "demo:Flask"
codepulse --data-dir "$DATA_DIR" note search routing

echo
echo "Next: cd web && CODEPULSE_DB_PATH=$DATA_DIR/graph.db npm run dev"
