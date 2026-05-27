#!/usr/bin/env bash
set -euo pipefail

REPO="codepulse/codepulse"
BIN="${CODEPULSE_BIN:-codepulse}"

echo "==> Installing CodePulse..."

# Detect OS/Arch
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in
  x86_64) ARCH="x86_64" ;;
  aarch64|arm64) ARCH="aarch64" ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Check for Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3.9+ is required. Install it first."
  echo "  macOS: brew install python"
  echo "  Ubuntu: sudo apt install python3 python3-pip python3-venv"
  exit 1
fi

# Check Python version
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]); then
  echo "ERROR: Python 3.9+ required (found $PY_VER)"
  exit 1
fi

# Install via pip
echo "==> Installing codepulse via pip..."
pip3 install --upgrade codepulse 2>/dev/null || pip install --upgrade codepulse 2>/dev/null || {
  echo "==> Full install with all language support..."
  pip3 install "codepulse[all]" 2>/dev/null || pip install "codepulse[all]" 2>/dev/null
}

echo ""
echo "==> CodePulse installed! Quick start:"
echo ""
echo "  cd your-project"
echo "  codepulse init"
echo "  codepulse index ."
echo "  codepulse search 'MyClass'"
echo ""
echo "Web dashboard:"
echo "  cd web && CODEPULSE_DB_PATH=~/.codepulse/graph.db npm run dev"
echo ""
