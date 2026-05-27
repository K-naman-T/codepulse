# Contributing

## Setup

```bash
git clone https://github.com/codepulse/codepulse.git
cd codepulse
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
pip install pytest pytest-asyncio pytest-click
```

## Run tests

```bash
# Python core (140 tests)
python3 -m pytest tests/

# Web UI (18 tests)
cd web && npx vitest run

# TypeScript CLI (29 tests)
cd packages/cli && npx vitest run
```

## Quick demo

```bash
# Analyze a public repo from URL
codepulse analyze https://github.com/gin-gonic/gin

# Search symbols
codepulse search "Route"

# View graph
cd web && CODEPULSE_DB_PATH=~/.codepulse/graph.db npm run dev
```

## Project structure

- `src/codepulse/` — Python core (parser, graph, CLI, MCP)
- `web/` — Next.js dashboard with D3 force graph
- `packages/cli/` — TypeScript CLI shell
- `parsers/` — Per-language tree-sitter query configs
- `tests/` — Python test suite
- `scripts/benchmark/` — A/B benchmark system
